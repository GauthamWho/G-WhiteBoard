#!/usr/bin/env python3
"""
Whiteboard Catcher — clipboard watcher + web server (single process).

- Serves the Excalidraw front-end from ../web/dist (port 8765)
- Saves / serves board scene JSON (data/board.json + data/board.excalidraw)
- WebSocket hub (WS /ws) that broadcasts clipboard captures
- Global hotkey Ctrl+Alt+C triggers a READ-ONLY clipboard capture
  (image first, then text). The clipboard is never written or cleared.

Designed to be light (~20 MB RAM): aiohttp + pynput + Pillow + pyperclip.
Python 3.10+ (tested on 3.14, Windows).
"""

from __future__ import annotations

import asyncio
import base64
import io
import json
import logging
import os
import platform
import re
import subprocess
import sys
import threading
import time
import uuid
import webbrowser
from datetime import datetime
from pathlib import Path

from aiohttp import WSMsgType, web

try:
    from pynput import keyboard
except Exception:  # pragma: no cover - keeps the web server usable without pynput
    keyboard = None

# ----------------------------------------------------------------------------
# Paths & logging
# ----------------------------------------------------------------------------

WATCHER_DIR = Path(__file__).resolve().parent
PROJECT_DIR = WATCHER_DIR.parent
WEB_DIST = PROJECT_DIR / "web" / "dist"
DATA_DIR = WATCHER_DIR / "data"
BOARD_JSON = DATA_DIR / "board.json"
BOARD_EXCALIDRAW = DATA_DIR / "board.excalidraw"

# Render/other hosts set PORT and expect a public bind; local default stays private.
HOST = "0.0.0.0" if os.environ.get("PORT") else "127.0.0.1"
PORT = int(os.environ.get("PORT", "8765"))
_IS_MAC = platform.system() == "Darwin"
# Defaults per platform: Windows Ctrl+Shift+C, Mac Fn+Cmd+C (user's pick).
DEFAULT_HOTKEY = "cmd+fn+c" if _IS_MAC else "ctrl+shift+c"
DEBOUNCE_SECONDS = 0.5
CONFIG_PATH = WATCHER_DIR / "config.json"
_MOD_NAMES = {"ctrl", "control", "alt", "option", "shift", "win", "cmd", "super", "meta", "fn"}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler(WATCHER_DIR / "watcher.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("whiteboard-catcher")

# ----------------------------------------------------------------------------
# Hotkey config (user-changeable, Windows + Mac)
# ----------------------------------------------------------------------------
# config.json: {"hotkey": "ctrl+alt+c"} — change the file or POST /config and
# it applies live, no restart needed. Syntax: mods+key, e.g. "ctrl+alt+c",
# "ctrl+shift+b", "f8" (single function key). Same file works on Mac.

_IS_MAC = platform.system() == "Darwin"
_MOD_NAMES = {"ctrl", "control", "alt", "option", "shift", "win", "cmd", "super", "meta"}
_KEY_TOKENS = set("abcdefghijklmnopqrstuvwxyz0123456789") | {f"f{i}" for i in range(1, 25)} | {
    "space", "enter", "tab", "esc", "backspace", "up", "down", "left", "right",
    "home", "end", "pageup", "pagedown", "insert", "delete",
}


def _read_hotkey() -> str:
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as fh:
            cfg = json.load(fh)
        hk = _normalize_hotkey(str(cfg.get("hotkey") or "").strip())
        if hk:
            return hk
    except FileNotFoundError:
        pass
    except Exception as exc:
        log.warning("config.json unreadable (%s) — using default hotkey", exc)
    return DEFAULT_HOTKEY


def _write_hotkey(hotkey: str) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = CONFIG_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps({"hotkey": hotkey}, indent=2) + "\n", encoding="utf-8")
    tmp.replace(CONFIG_PATH)


def _normalize_hotkey(hotkey: str) -> str:
    """Validate + normalize 'ctrl+alt+c' style. Raises ValueError if bad."""
    parts = [p.strip().lower() for p in hotkey.split("+") if p.strip()]
    if not parts:
        raise ValueError("hotkey is empty")
    *mods, key = parts
    if key not in _KEY_TOKENS:
        raise ValueError(f"unsupported key '{key}' (use a letter, digit, F1-F12, or a named key)")
    if any(m not in _MOD_NAMES for m in mods):
        raise ValueError(f"unsupported modifier in '{hotkey}' (use ctrl/alt/shift/win)")
    mods = ["ctrl" if m == "control" else "alt" if m == "option" else "cmd" if m in ("super", "meta") else m for m in mods]
    if not mods and not key.startswith("f"):
        raise ValueError("a bare single key would block typing everywhere — use a function key like 'f8', or add modifiers")
    return "+".join(mods + [key])


def _display_hotkey(hotkey: str) -> str:
    return "+".join(p.capitalize() if len(p) > 1 else p.upper() for p in hotkey.split("+"))


def _pynput_combo(hotkey: str) -> str:
    """'ctrl+alt+c' -> pynput '<ctrl>+<alt>+c' (for the Mac listener).
    'win' means the Command key on Mac; 'fn' maps to pynput's <fn>."""
    mods = hotkey.split("+")[:-1]
    names = {m: {"win": "cmd", "super": "cmd", "meta": "cmd"}.get(m, m) for m in mods}
    return "".join(f"<{names[m]}>+" for m in mods) + hotkey.split("+")[-1]


class HotkeyManager:
    """Starts/stops/re-registers the global hotkey. Windows uses
    RegisterHotKey (OS-guaranteed delivery, survives elevated windows);
    macOS uses a pynput GlobalHotKeys listener."""

    def __init__(self) -> None:
        self._stop: threading.Event | None = None
        self._thread: threading.Thread | None = None
        self.hotkey: str = _read_hotkey()

    def start(self, hotkey: str) -> bool:
        self.stop()
        self.hotkey = hotkey
        if platform.system() == "Linux":
            # Headless (e.g. Render deploy): no clipboard/hotkey here — the
            # cloud copy only serves the board + room relay. Local watchers
            # on the user's PC do the capturing.
            log.info("Headless host: global hotkey disabled (board + relay only)")
            return False
        self._stop = threading.Event()
        target = self._run_mac if _IS_MAC else self._run_windows
        self._thread = threading.Thread(target=target, args=(hotkey, self._stop), daemon=True, name="hotkey")
        self._thread.start()
        return True  # registration failure is logged inside the thread

    def stop(self) -> None:
        if self._stop is not None:
            self._stop.set()
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=3)
        self._stop, self._thread = None, None

    def restart(self, hotkey: str) -> bool:
        self.start(hotkey)
        return True

    # -- Windows: RegisterHotKey + message pump ------------------------------
    def _run_windows(self, hotkey: str, stop: threading.Event) -> None:
        import ctypes as ct
        from ctypes import wintypes as wt

        mod_bits = {"ctrl": 0x0002, "alt": 0x0001, "shift": 0x0004, "win": 0x0008}
        parts = hotkey.split("+")
        bad = [p for p in parts[:-1] if p not in mod_bits]
        if bad:
            # e.g. cmd/fn are Mac-only modifiers
            log.error("Hotkey %s uses modifier(s) %s that don't exist on Windows — pick ctrl/alt/shift/win",
                      _display_hotkey(hotkey), "/".join(bad))
            return
        mods = sum(mod_bits[p] for p in parts[:-1])
        key = parts[-1]
        vk = 0x70 + int(key[1:]) - 1 if key.startswith("f") and key[1:].isdigit() else ord(key.upper())
        atom = 1
        user32 = ct.windll.user32
        if not user32.RegisterHotKey(None, atom, mods, vk):
            log.error("Hotkey %s could not be registered — already taken by another app. Pick another.", _display_hotkey(hotkey))
            return
        log.info("Global hotkey active: %s", _display_hotkey(hotkey))
        msg = wt.MSG()
        WM_HOTKEY, WM_QUIT, QS_ALLINPUT = 0x0312, 0x0012, 0x0100
        try:
            while not stop.is_set():
                # wait up to 200 ms for a message so we can also watch stop
                if user32.MsgWaitForMultipleObjects(0, None, False, 200, QS_ALLINPUT) == 0:
                    while user32.PeekMessageW(ct.byref(msg), None, 0, 0, 1):
                        if msg.message == WM_HOTKEY:
                            log.info("Hotkey fired (%s)", _display_hotkey(hotkey))
                            on_hotkey()
                        elif msg.message == WM_QUIT:
                            return
        finally:
            user32.UnregisterHotKey(None, atom)
            log.info("Hotkey %s unregistered", _display_hotkey(hotkey))

    # -- macOS: pynput GlobalHotKeys -----------------------------------------
    def _run_mac(self, hotkey: str, stop: threading.Event) -> None:
        if keyboard is None:
            log.warning("pynput unavailable — global hotkey disabled (web server only)")
            return
        try:
            listener = keyboard.GlobalHotKeys({_pynput_combo(hotkey): on_hotkey})
            listener.start()
            log.info("Global hotkey active: %s", _display_hotkey(hotkey))
            stop.wait()
        except Exception as exc:
            log.error("Hotkey listener failed: %s", exc)
            log.error("On macOS, grant Accessibility permission (System Settings > Privacy & Security > Accessibility).")
            return
        finally:
            try:
                listener.stop()
            except Exception:
                pass


HOTKEY_MANAGER = HotkeyManager()


def _config_watcher() -> None:
    """Watch config.json; apply hotkey changes live."""
    hotkey = HOTKEY_MANAGER.hotkey
    last = CONFIG_PATH.stat().st_mtime if CONFIG_PATH.exists() else 0.0
    while True:
        time.sleep(2)
        try:
            mtime = CONFIG_PATH.stat().st_mtime if CONFIG_PATH.exists() else 0.0
            if mtime != last:
                last = mtime
                new = _read_hotkey()
                if new != hotkey:
                    log.info("Hotkey changed via config.json: %s -> %s", _display_hotkey(hotkey), _display_hotkey(new))
                    hotkey = new
                    HOTKEY_MANAGER.start(new)
        except Exception as exc:
            log.warning("config watcher: %s", exc)


# ----------------------------------------------------------------------------
# WebSocket hub
# ----------------------------------------------------------------------------

clients: set = set()
_loop: asyncio.AbstractEventLoop | None = None


async def ws_handler(request: web.Request) -> web.WebSocketResponse:
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    clients.add(ws)
    log.info("WS client connected (%d total)", len(clients))
    try:
        async for msg in ws:
            if msg.type == WSMsgType.ERROR:
                log.warning("WS error: %s", msg.exception)
    finally:
        clients.discard(ws)
        log.info("WS client disconnected (%d total)", len(clients))
    return ws


async def broadcast(message: dict) -> None:
    """Send a JSON message to every connected WS client. Never raises."""
    if not clients:
        log.info("Broadcast skipped: no clients connected (%s)", message.get("type"))
        return
    dead = []
    payload = json.dumps(message)
    for ws in list(clients):
        try:
            await ws.send_str(payload)
        except Exception as exc:
            log.warning("Broadcast to a client failed: %s", exc)
            dead.append(ws)
    for ws in dead:
        clients.discard(ws)


def broadcast_threadsafe(message: dict) -> None:
    """Safe to call from the pynput hotkey thread."""
    if _loop is None:
        log.warning("Event loop not ready; capture dropped")
        return
    asyncio.run_coroutine_threadsafe(broadcast(message), _loop)

# ----------------------------------------------------------------------------
# Room relay (shared boards)
# ----------------------------------------------------------------------------
# Clients connect to GET /room/<room_id> (any number of rooms). Every JSON
# message a client sends is relayed, wrapped, to the others in the room:
#   {"type": "change", "from": <client_id>, "payload": <original message>}
# The client id arrives as the first message: {"type": "hello", "id": "..."}.
# Non-JSON frames are ignored silently. Same protocol as relay/relay.py
# (the standalone deployable relay).

ROOM_ID_RE = re.compile(r"^[a-z0-9-]{3,64}$")

rooms: dict[str, set] = {}  # room_id -> sockets currently in the room
room_client_ids: dict = {}  # socket -> client id (set via the hello message)


async def room_send(room: set, message: dict, exclude=None) -> None:
    """Send a JSON message to every socket in a room (optionally except one)."""
    payload = json.dumps(message)
    dead = []
    for ws in list(room):
        if ws is exclude:
            continue
        try:
            await ws.send_str(payload)
        except Exception as exc:
            log.warning("Room send failed: %s", exc)
            dead.append(ws)
    for ws in dead:
        room.discard(ws)


async def room_handler(request: web.Request) -> web.WebSocketResponse:
    room_id = request.match_info["room_id"]
    if not ROOM_ID_RE.match(room_id):
        return web.json_response({"ok": False, "error": "invalid room id"}, status=400)
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    room = rooms.setdefault(room_id, set())
    room.add(ws)
    log.info("Room %s: peer joined (%d in room)", room_id, len(room))
    await room_send(room, {"type": "peers", "count": len(room)})
    try:
        async for msg in ws:
            if msg.type == WSMsgType.ERROR:
                log.warning("Room WS error: %s", msg.exception)
            elif msg.type == WSMsgType.TEXT:
                try:
                    data = json.loads(msg.data)
                except Exception:
                    continue  # non-JSON frames are ignored silently
                if not isinstance(data, dict):
                    continue
                if data.get("type") == "hello":
                    if isinstance(data.get("id"), str) and data["id"]:
                        room_client_ids[ws] = data["id"]
                    continue
                client_id = room_client_ids.get(ws)
                if client_id is None:
                    continue  # messages before hello are ignored
                await room_send(
                    room, {"type": "change", "from": client_id, "payload": data}, exclude=ws
                )
    finally:
        room.discard(ws)
        room_client_ids.pop(ws, None)
        await room_send(room, {"type": "peers", "count": len(room)})
        if not room:
            rooms.pop(room_id, None)  # prune empty rooms
        log.info("Room %s: peer left", room_id)
    return ws

# ----------------------------------------------------------------------------
# HTTP handlers
# ----------------------------------------------------------------------------

NO_BUILD_PAGE = """<!DOCTYPE html>
<html><head><title>Whiteboard Catcher</title></head>
<body style="font-family: system-ui, sans-serif; padding: 2rem;">
<h1>Whiteboard web app not built yet</h1>
<p>Run the build in <code>web/</code> so that <code>web/dist</code> exists,
then restart this server or just reload this page.</p>
</body></html>"""


async def index_handler(request: web.Request) -> web.StreamResponse:
    index = WEB_DIST / "index.html"
    if index.is_file():
        return web.FileResponse(index)
    return web.Response(text=NO_BUILD_PAGE, content_type="text/html")


def _empty_scene() -> dict:
    return {"elements": [], "appState": {}, "files": {}}


async def scene_handler(request: web.Request) -> web.Response:
    try:
        scene = json.loads(BOARD_JSON.read_text(encoding="utf-8"))
        return web.json_response(scene)
    except FileNotFoundError:
        return web.json_response(_empty_scene())
    except Exception as exc:
        log.error("Failed to read board.json: %s", exc)
        return web.json_response(_empty_scene())


def _atomic_write_json(path: Path, payload: bytes) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(payload)
    tmp.replace(path)


BACKUP_DIR = DATA_DIR / "backups"
BACKUPS_TO_KEEP = 7
_last_backup_day: str | None = None


def _maybe_daily_backup() -> None:
    """Once per day (on the first save of that day), snapshot the board and
    keep the last BACKUPS_TO_KEEP days. A bad day becomes recoverable."""
    global _last_backup_day
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        if today == _last_backup_day or not BOARD_JSON.exists():
            return
        _last_backup_day = today
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        day_dir = BACKUP_DIR / today
        if day_dir.exists():  # manual rerun / clock jump — refresh, don't nest
            _atomic_write_json(day_dir / "board.json", BOARD_JSON.read_bytes())
        else:
            day_dir.mkdir(parents=True, exist_ok=False)
            _atomic_write_json(day_dir / "board.json", BOARD_JSON.read_bytes())
            if BOARD_EXCALIDRAW.exists():
                _atomic_write_json(day_dir / "board.excalidraw", BOARD_EXCALIDRAW.read_bytes())
        days = sorted(d.name for d in BACKUP_DIR.iterdir() if d.is_dir())
        for old in days[:-BACKUPS_TO_KEEP]:
            for f in (BACKUP_DIR / old).iterdir():
                f.unlink(missing_ok=True)
            (BACKUP_DIR / old).rmdir()
        log.info("Daily backup saved: %s (keeping %d days)", today, BACKUPS_TO_KEEP)
    except Exception as exc:
        # a backup hiccup must never fail the save itself
        log.error("Daily backup failed: %s", exc)


async def save_handler(request: web.Request) -> web.Response:
    try:
        body = await request.read()
        scene = json.loads(body)  # validate it's JSON; keep bytes untouched
        if not isinstance(scene, dict):
            raise ValueError("scene must be a JSON object")
        # Lossless archive: bytes are stored exactly as received (base64
        # PNG dataURLs inside "files" are never re-encoded).
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        _atomic_write_json(BOARD_JSON, body)
        _atomic_write_json(BOARD_EXCALIDRAW, body)
        _maybe_daily_backup()
        log.info(
            "Saved scene: %d elements, %d files (%d bytes)",
            len(scene.get("elements", [])),
            len(scene.get("files", {})),
            len(body),
        )
        return web.json_response({"ok": True})
    except Exception as exc:
        log.error("Save failed: %s", exc)
        return web.json_response({"ok": False, "error": str(exc)}, status=400)


async def test_capture_handler(request: web.Request) -> web.Response:
    try:
        message = await request.json()
        if not isinstance(message, dict):
            raise ValueError("body must be a JSON object")
        message.setdefault("type", "capture")
        await broadcast(message)
        return web.json_response({"ok": True, "clients": len(clients)})
    except Exception as exc:
        log.error("test-capture failed: %s", exc)
        return web.json_response({"ok": False, "error": str(exc)}, status=400)

# ----------------------------------------------------------------------------
# Clipboard capture (READ-ONLY — never write, never clear)
# ----------------------------------------------------------------------------

_IS_MAC = platform.system() == "Darwin"


def _image_to_data_url(img) -> str:
    """PIL Image -> lossless PNG base64 dataURL."""
    buf = io.BytesIO()
    img.save(buf, "PNG")
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/png;base64,{b64}"


def _capture_image_windows():
    """Return a PIL Image from the Windows clipboard, or None."""
    try:
        from PIL import ImageGrab
    except ImportError:
        return None
    result = ImageGrab.grabclipboard()
    if result is None:
        return None
    if isinstance(result, list) and result:  # list of file paths
        for path in result:
            try:
                from PIL import Image
                return Image.open(path)
            except Exception as exc:
                log.warning("Could not open clipboard file %s: %s", path, exc)
        return None
    return result  # already a PIL Image


def _capture_image_macos():
    """Read PNG/TIFF off the macOS NSPasteboard via pyobjc. Untested."""
    try:
        import AppKit  # pyobjc
    except ImportError:
        log.warning("macOS: pyobjc (AppKit) not installed; image capture unavailable")
        return None
    try:
        pb = AppKit.NSPasteboard.generalPasteboard()
        data = pb.dataForType_(AppKit.NSPasteboardTypePNG)
        if data is None:
            tiff = pb.dataForType_(AppKit.NSPasteboardTypeTIFF)
            if tiff is None:
                return None
            from PIL import Image, ImageFile
            import io as _io
            img = Image.open(_io.BytesIO(bytes(tiff)))
            return img
        from PIL import Image
        return Image.open(io.BytesIO(bytes(data)))
    except Exception as exc:
        log.error("macOS clipboard image read failed: %s", exc)
        return None


def capture_clipboard() -> dict | None:
    """Read the clipboard once. Image first, then text. Never writes it."""
    img = _capture_image_windows() if not _IS_MAC else _capture_image_macos()
    if img is not None:
        try:
            data_url = _image_to_data_url(img)
            return {
                "type": "capture",
                "kind": "image",
                "text": None,
                "dataUrl": data_url,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "id": str(uuid.uuid4()),
            }
        except Exception as exc:
            log.error("Image -> PNG conversion failed: %s", exc)

    try:
        import pyperclip
        text = pyperclip.paste()
    except Exception as exc:
        log.error("Text clipboard read failed: %s", exc)
        return None
    if not text or not text.strip():
        return None
    return {
        "type": "capture",
        "kind": "text",
        "text": text,
        "dataUrl": None,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "id": str(uuid.uuid4()),
    }


_last_capture_at = 0.0
_debounce_lock = threading.Lock()


def _send_native_copy() -> None:
    """Send Ctrl+C on Windows or Cmd+C on macOS to copy the current selection."""
    if keyboard is None:
        return
    try:
        ctrl = keyboard.Key.cmd if _IS_MAC else keyboard.Key.ctrl
        with keyboard.Controller() as ctrlr:
            ctrlr.press(ctrl)
            ctrlr.press('c')
            ctrlr.release('c')
            ctrlr.release(ctrl)
        # Give the OS a moment to update the clipboard
        time.sleep(0.08)
    except Exception as exc:
        log.debug("Native copy send failed: %s", exc)

def on_hotkey() -> None:
    """pynput callback (its own thread). Debounce, capture, broadcast."""
    global _last_capture_at
    with _debounce_lock:
        now = time.monotonic()
        if now - _last_capture_at < DEBOUNCE_SECONDS:
            log.info("Hotkey debounced (within %.0f ms)", DEBOUNCE_SECONDS * 1000)
            return
        _last_capture_at = now
    try:
        # Copy first, then capture — Ctrl+Shift+C becomes copy+send
        _send_native_copy()
        message = capture_clipboard()
        if message is None:
            log.info("Capture: clipboard empty or unsupported content — skipped")
            return
        size = len(message.get("text") or message.get("dataUrl") or "")
        log.info("Capture: kind=%s size=%d chars", message["kind"], size)
        broadcast_threadsafe(message)
    except Exception as exc:
        log.error("Capture failed (process keeps running): %s", exc)


# ----------------------------------------------------------------------------
# Startup
# ----------------------------------------------------------------------------


async def config_get_handler(request: web.Request) -> web.Response:
    return web.json_response({"hotkey": HOTKEY_MANAGER.hotkey, "display": _display_hotkey(HOTKEY_MANAGER.hotkey)})


async def client_log_handler(request: web.Request) -> web.Response:
    """Browser crashes land here so a blank page is never a mystery."""
    try:
        body = await request.json()
        log.error("CLIENT-ERROR [%s] %s", body.get("kind"), str(body.get("detail", ""))[:1000])
    except Exception:
        pass
    return web.json_response({"ok": True})


async def config_post_handler(request: web.Request) -> web.Response:
    try:
        body = await request.json()
        hotkey = _normalize_hotkey(str(body.get("hotkey", "")))
    except Exception as exc:
        return web.json_response({"ok": False, "error": f"invalid hotkey: {exc}"}, status=400)
    HOTKEY_MANAGER.start(hotkey)  # live re-register, no restart needed
    _write_hotkey(hotkey)
    log.info("Hotkey set via /config: %s", _display_hotkey(hotkey))
    return web.json_response({"ok": True, "hotkey": hotkey, "display": _display_hotkey(hotkey)})



# ----------------------------------------------------------------------------
# Update check: is a newer commit on GitHub than the copy running here?
# If yes, the board shows a small "Update available" pill. Installing stays
# one double-click on the UPDATE file — never automatic mid-use.
# ----------------------------------------------------------------------------

REPO_API_URL = "https://api.github.com/repos/GauthamWho/G-WhiteBoard/commits/master"
UPDATE_CHECK_INTERVAL = 6 * 3600  # seconds
_update_status: dict = {"update_available": False, "local": None, "remote": None}


def _local_version_sha() -> str | None:
    """The installed copy's git commit (None if not a git clone)."""
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=PROJECT_DIR, capture_output=True, text=True, timeout=10,
        )
        sha = out.stdout.strip()
        return sha if out.returncode == 0 and sha else None
    except Exception:
        return None


async def _update_check_loop() -> None:
    import aiohttp  # already a dependency of the server itself

    global _update_status
    while True:
        remote = None
        try:
            async with aiohttp.ClientSession() as sess:
                async with sess.get(
                    REPO_API_URL, timeout=aiohttp.ClientTimeout(total=15),
                    headers={"Accept": "application/vnd.github+json"},
                ) as resp:
                    if resp.status == 200:
                        remote = (await resp.json()).get("sha")
        except Exception:
            pass  # offline / rate-limited — try again next cycle, never nag
        local = await asyncio.to_thread(_local_version_sha)
        _update_status = {
            "update_available": bool(local and remote and local != remote),
            "local": local[:7] if local else None,
            "remote": remote[:7] if remote else None,
        }
        if _update_status["update_available"]:
            log.info("Update available: installed %s, GitHub has %s (run the UPDATE file)",
                     _update_status["local"], _update_status["remote"])
        await asyncio.sleep(UPDATE_CHECK_INTERVAL)


async def update_status_handler(request: web.Request) -> web.Response:
    return web.json_response(_update_status)


def make_app() -> web.Application:
    app = web.Application()

    async def _on_startup(app: web.Application) -> None:
        global _loop
        _loop = asyncio.get_running_loop()
        app["update_task"] = asyncio.create_task(_update_check_loop())

    app.on_startup.append(_on_startup)
    app.router.add_get("/", index_handler)
    app.router.add_get("/scene", scene_handler)
    app.router.add_post("/save", save_handler)
    app.router.add_get("/ws", ws_handler)
    app.router.add_get("/room/{room_id}", room_handler)
    app.router.add_post("/test-capture", test_capture_handler)
    app.router.add_get("/config", config_get_handler)
    app.router.add_post("/config", config_post_handler)
    app.router.add_post("/client-log", client_log_handler)
    app.router.add_get("/update-status", update_status_handler)
    app.router.add_get("/favicon.ico", lambda r: web.FileResponse(WEB_DIST / "favicon.ico", content_type="image/x-icon"))
    app.router.add_get("/favicon.svg", lambda r: web.FileResponse(WEB_DIST / "favicon.svg", content_type="image/svg+xml"))
    app.router.add_get("/apple-touch-icon.png", lambda r: web.FileResponse(WEB_DIST / "apple-touch-icon.png", content_type="image/png"))
    app.router.add_get("/favicon.png", lambda r: web.FileResponse(WEB_DIST / "favicon.png", content_type="image/png"))

    if WEB_DIST.is_dir():
        # Serve built assets (JS/CSS/fonts) — static files win over nothing;
        # the routes above were registered first so they take priority.
        app.router.add_static("/assets/", WEB_DIST / "assets")
        app.router.add_static("/", WEB_DIST)
    return app


def main() -> None:
    hotkey = HOTKEY_MANAGER.hotkey
    log.info("Whiteboard Catcher starting on http://%s:%d", HOST, PORT)
    log.info("Web dist: %s", WEB_DIST if WEB_DIST.is_dir() else "NOT BUILT (fallback page will be served)")
    print(f"\n  Whiteboard Catcher  ->  http://localhost:{PORT}")
    print(f"  press {_display_hotkey(hotkey)} anywhere to capture  (change it in config.json — applies live)")
    print("  Ctrl+C to quit\n")

    HOTKEY_MANAGER.start(hotkey)
    threading.Thread(target=_config_watcher, daemon=True, name="config-watch").start()
    try:
        web.run_app(make_app(), host=HOST, port=PORT, print=None)
    except KeyboardInterrupt:
        log.info("Ctrl+C received — shutting down")
    finally:
        HOTKEY_MANAGER.stop()


if __name__ == "__main__":
    main()
