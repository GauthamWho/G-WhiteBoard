<h1 align="center">G WhiteBoard</h1>

<p align="center">
<img src="assets/banner.svg" alt="G WhiteBoard — copy, press the shortcut, it's on your board" width="100%">
</p>

<p align="center">
<a href="#-licence"><img alt="licence" src="https://img.shields.io/badge/licence-Apache%202.0-green"></a>
<a href="#-works-on-windows-and-mac"><img alt="platform" src="https://img.shields.io/badge/platform-Windows%20%7C%20macOS-blue"></a>
<img alt="weight" src="https://img.shields.io/badge/RAM%20~20%20MB-light%20as%20a%20feather-orange">
</p>

---

## The problem it solves

You copy things all day — links, prices, addresses, screenshots. Then you lose them.
They sit in your clipboard for one paste, and disappear.

**G WhiteBoard keeps them, forever, on one neat board.**

1. **Copy anything** — a link, some text, a photo, a screenshot. The normal way.
2. **Press one shortcut** — `Ctrl+Alt+C` (you can change it).
3. **Look at your board** — it's there now, as a card, with the time under it.
4. **It never goes away** — saved on your own computer, survives restarts.

Your clipboard still works normally. Nothing leaves your computer (unless you share a room — below).

## 🖼 How it works, in one picture

<p align="center">
<img src="assets/how-it-works.svg" alt="Four steps: copy anything, press the shortcut, the watcher reads it read-only, it appears on your board saved forever" width="100%">
</p>

Two things run on your computer:

| Name | What it is | What it does |
|---|---|---|
| **The watcher** | a tiny background program, ~20 MB RAM | waits for your shortcut, reads the clipboard |
| **The board** | a browser tab | shows your whiteboard, saves everything to disk |

You start both with **one double-click** (below). Then leave the tab open — that's it.

---

## 🚀 Getting started

### What to install first (one time only)

1. **Python 3** — from [python.org/downloads](https://www.python.org/downloads).
   On Windows, tick ✅ **"Add Python to PATH"** on the first screen of the installer. This matters.
2. **Node.js** — from [nodejs.org](https://nodejs.org). Used once to build the board.

### Windows

Open **PowerShell** (Start button → type `powershell` → Enter). Paste these lines, one at a time:

```powershell
git clone https://github.com/GauthamWho/G-WhiteBoard.git
cd G-WhiteBoard
cd web; npm install; npm run build; cd ..
.venv\Scripts\pip install -r watcher\requirements.txt
.\watcher\start_windows.ps1
```

> Don't have `git`? On the GitHub page click the green **Code** button → **Download ZIP**,
> unzip it anywhere, open the folder, then start from the `cd web` line above.

**What you should see:** a black window with text (the watcher — minimise it, don't close it),
and a new browser tab at `http://localhost:8765`. **That tab is your board.**

### macOS

Open **Terminal** and paste:

```bash
git clone https://github.com/GauthamWho/G-WhiteBoard.git
cd G-WhiteBoard
cd web && npm install && npm run build && cd ..
python3 -m pip install -r watcher/requirements.txt
bash watcher/start_mac.command
```

Mac will ask one time for permission: **System Settings → Privacy & Security →
Accessibility** → allow **Python**. Then open `http://localhost:8765` in your browser.

---

## ✨ Using it every day

### A real example

> 1. You're booking a trip. You select a hotel name and copy it → press `Ctrl+Alt+C`.
> 2. You screenshot a map → press `Ctrl+Alt+C`.
> 3. You copy the booking link → press `Ctrl+Alt+C`.
>
> Your board now shows three cards, each with its own time:
>
> ```
> "Hotel Blue Sky, Kochi"     [ map screenshot ]     https://booking.com/xyz
>  2026-11-10 09:14           2026-11-10 09:15       2026-11-10 09:16
> ```
>
> Tomorrow you open the board — all three are still there.

### Taking screenshots onto the board

Screenshot **to the clipboard** first, then press the shortcut:

- **Windows:** `Win+Shift+S` (Snipping Tool), or [Flameshot](https://flameshot.org) — select region → `Ctrl+C`
- **macOS:** `Cmd+Shift+Ctrl+4` (keep the `Ctrl` — it copies instead of saving a file)

Images are saved **full quality, never compressed again**.

### Good to know

| You do... | What happens |
|---|---|
| Capture the same thing twice | still just **one** card — repeats are removed |
| Paste right after capturing | works normally — your clipboard was only read, never changed |
| Close the tab, shut down the PC | board reloads complete — it auto-saves every change |
| Delete something by mistake | daily backups keep the **last 7 days** (see below) |
| Draw with the pen, drag cards | all saved too — it's a real whiteboard |

---

## ⌨️ Change the shortcut

Open **`watcher/config.json`** in any text editor, change the line, save:

```json
{ "hotkey": "ctrl+alt+c" }
```

Try `"ctrl+shift+9"`, `"alt+f2"`, `"f8"`… It applies **live within 2 seconds** — no restart.
If another app already owns that combo, a clear message appears in `watcher/watcher.log` — pick another one.

---

## 💾 Where your board is saved

On **your disk**, losslessly — images are never re-encoded or shrunk:

```
watcher/data/
├── board.json          ← the live board (auto-loads every time)
├── board.excalidraw    ← portable copy (opens at excalidraw.com too)
└── backups/            ← automatic daily snapshots, last 7 days kept
    └── 2026-11-10/
```

Every save is written **atomically** (the same trick databases use) — a power cut
mid-save can never corrupt your board. Every day, the first save makes a dated
backup copy, and the last 7 days are kept.

Nothing is sent anywhere. No cloud, no account, no internet needed.

---

## 🤝 Two people, one live board

You in one place, a friend in another — work on the **same board at the same time**,
like Google Docs.

<p align="center">
<img src="assets/shared-rooms.svg" alt="You and a friend connect to the same room link and see one shared board live" width="100%">
</p>

### How to share

1. Open your board with a room name in the address:
   `http://localhost:8765/?room=trip-planning`
2. Click **Copy Link** in the room bar at the top and send it to your friend.
3. Everyone with the link sees the same board, live. Every change merges safely —
   nobody overwrites anybody.

The room bar shows who's online. Don't want it always visible? Click the small **–**
and it collapses to a tiny pill in the corner — click the pill to bring it back.

### Your friend is in another city?

Then the board needs to live online, not just on your PC. It's a free, one-time,
10-minute setup — full walkthrough in **[DEPLOY.md](DEPLOY.md)**. After that you get
a permanent link like `https://your-board.onrender.com/?room=our-board` that works
from anywhere, and your PC can even be switched off.

---

## 🧰 Troubleshooting

| Problem | Fix |
|---|---|
| Shortcut does nothing | Is the watcher window open? Is the board tab open? Look at `watcher/watcher.log` — if the combo is taken, change it (above) |
| Screenshot arrives as garbage text | You saved it to a file instead of the clipboard — redo with the copy-to-clipboard shortcuts shown above |
| Board tab is blank | Refresh once. Happens again? Check `watcher/watcher.log` for a `CLIENT-ERROR` line and open an issue with it |
| Mac: shortcut does nothing | Give Python Accessibility permission (System Settings → Privacy & Security → Accessibility) |
| Port already in use | Another app owns 8765 — close it, or change `PORT` in `watcher/server.py` |

---

## 🧱 Under the hood

- [Excalidraw](https://excalidraw.com) — the open-source whiteboard engine
- [aiohttp](https://docs.aiohttp.org) — a tiny Python server
- No Electron. No telemetry. No account. Works fully offline.

## 📄 Licence

[Apache License 2.0](LICENSE) — use it, change it, ship it.
