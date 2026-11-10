# Whiteboard Catcher — watcher (back half)

One lightweight Python process (~20 MB RAM) that serves the Excalidraw web app,
stores the board, and turns a global hotkey into clipboard captures pushed to
the browser over WebSocket. No Electron, no heavy frameworks.

## Parts

| File | What it does |
|---|---|
| `server.py` | The whole process: HTTP server on port 8765, WebSocket hub, static file serving, global hotkey (Ctrl+Alt+C), read-only clipboard capture |
| `requirements.txt` | Minimal deps: `aiohttp`, `pynput`, `Pillow`, `pyperclip` |
| `start_windows.ps1` | One-click Windows launcher: venv → pip install → server → open Edge |
| `start_mac.command` | Same for macOS (**untested** — see comment block inside; needs Accessibility permission) |
| `watcher.log` | Every capture, hotkey start/stop, and error lands here |
| `data/board.json` | The saved scene (written by `POST /save`) |
| `data/board.excalidraw` | Identical copy in the standard `.excalidraw` format — open it at excalidraw.com |

## Install

```powershell
cd watcher
python -m venv ..\.venv
..\.venv\Scripts\python -m pip install -r requirements.txt
```

## Run

```powershell
# easiest
powershell -ExecutionPolicy Bypass -File start_windows.ps1
# or manually
..\.venv\Scripts\python server.py
```

Console shows: the URL (http://localhost:8765), "press Ctrl+Alt+C anywhere to
capture", and "Ctrl+C to quit".

## HTTP API

| Route | Method | Meaning |
|---|---|---|
| `/` | GET | Serves the built front-end from `../web/dist` (index.html + `/assets/...`). If not built: a plain "not built yet — run build in web/" page |
| `/scene` | GET | Saved scene `{"elements":[...],"appState":{...},"files":{...}}`, or the empty scene if none |
| `/save` | POST | Full scene JSON. Atomic write (temp file + replace) to `board.json` **and** `board.excalidraw`. Base64 PNG dataURLs are stored byte-for-byte — never re-encoded |
| `/ws` | WS | Connect here; all captures are broadcast as JSON |
| `/test-capture` | POST | Send a capture JSON (same schema below); broadcasts it without touching the hotkey — for testing |
| `/config` | GET | Current hotkey: `{"hotkey":"ctrl+alt+c","display":"Ctrl+Alt+C"}` |
| `/config` | POST | `{"hotkey":"ctrl+shift+9"}` → changes the global hotkey **live** (writes `config.json`, re-registers instantly, no restart) |

## Changing the hotkey (Windows + Mac)

Same way on both systems — any of these:

- **Edit `watcher/config.json`** → `{"hotkey": "ctrl+alt+c"}` — save the file; it applies within 2 seconds, no restart.
- **POST to `http://localhost:8765/config`** with `{"hotkey": "..."}` (a settings box in the web page uses this).

Syntax: modifiers + key, e.g. `ctrl+alt+c`, `ctrl+shift+b`, `alt+f2`. A bare single key is only
allowed for function keys (`f8`), otherwise it would block normal typing everywhere.
On macOS the hotkey needs the Accessibility permission (one time): System Settings →
Privacy & Security → Accessibility. On Windows the hotkey is registered with the OS itself
(RegisterHotKey), so it fires reliably in every app — including over elevated windows —
and prints an error in `watcher.log` if another app already took the combo.

## Capture flow (the hotkey)

1. Debounce: triggers within 500 ms of the previous one are ignored (held key).
2. Clipboard is read **read-only** — never written, never cleared.
3. Image first: `PIL.ImageGrab.grabclipboard()` on Windows. A PIL Image → PNG
   losslessly → `data:image/png;base64,...`. A list of file paths → the first
   image file is loaded the same way. (macOS: pyobjc/AppKit NSPasteboard reader,
   structured but untested.)
4. Else text via `pyperclip.paste()`; empty/whitespace is skipped silently.
5. Broadcast message shape:

```json
{
  "type": "capture",
  "kind": "image" | "text",
  "text": "…or null…",
  "dataUrl": "data:image/png;base64,…or null…",
  "timestamp": "YYYY-MM-DD HH:MM:SS",
  "id": "uuid4"
}
```

Errors anywhere in the capture path are logged and swallowed — the process
never crashes because of one bad clipboard read.

## Data locations

- Board: `watcher/data/board.json` + `watcher/data/board.excalidraw`
- Log: `watcher/watcher.log`
