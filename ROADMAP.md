# Whiteboard Catcher — Roadmap

**End goal:** Press `Ctrl+Alt+C` anywhere in Windows or Mac → whatever is on my clipboard
(text, image, or a fresh screenshot) lands on my personal whiteboard as a card with a tiny
timestamp. My normal clipboard is never touched. The board auto-saves everything losslessly,
forever, and works like a normal whiteboard (pan, zoom, drag, arrange).

**Decisions locked (2026-11-10):**
- Engine: **Excalidraw** (open-source whiteboard) running as a local browser page (Edge)
- Listener: tiny Python watcher (~20 MB RAM) — chosen over Electron for "light as feather"
- Hotkey: `Ctrl+Alt+C` — same key for screenshots (Win+Shift+S first, then the hotkey)
- Clipboard stays intact · Auto-grid placement, no overlaps · Timestamps small + gray
- Auto-save to disk as full scene JSON with lossless PNG data — restart-safe

## Steps

| # | Step | State |
|---|------|-------|
| 0 | Decisions + roadmap | ✅ Done |
| 1 | Whiteboard web app (Excalidraw + capture insert + timestamps + auto-grid + autosave) | ✅ Done |
| 2 | Python watcher (hotkey + clipboard read + local server + disk save) | ✅ Done |
| 3 | Wire together + live test on this PC (real Edge, real hotkey, screenshot flow) | ✅ Done — hotkey fires, image + text land, auto-save + restart-restore proven |
| 4 | Hotkey fix + user-changeable hotkey (both OSes) | ✅ Done — replaced flaky key-hook with OS-registered hotkey; change live via `watcher/config.json` or POST `/config` |
| 5 | Launchers (double-click start on Windows), README | ✅ Built — `watcher\start_windows.ps1` |
| 6 | **User retest: Flameshot copy → Ctrl+Alt+C** | 🔄 Waiting on Gautham |
| 7 | Public GitHub repo **G-WhiteBoard** (Apache-2.0, README, Mac-ready) | ✅ READY locally — repo committed at `Projects\Tools\2026-11-whiteboard-catcher`, **waiting for your "go" to push** (I can't create public repos; you create the empty repo at github.com/new, I push) |
| 8 | **Shared boards** — you in place A, friend in place B, one live board | 🔄 Building now (room links + live sync + merge-by-item-id) |
| 9 | Mac setup + permission steps (built, **not run on the Mac yet**) | ⬜ |

**WE ARE HERE →** Step 6 (your Flameshot retest) + Step 7 ready to push on your word.

### Step 8 plan — Shared boards (kept ready, built when you say go)

- Every board gets a **room**: same room link = same board, like other whiteboard platforms.
- The watcher (or one tiny relay file) passes each change to everyone in the room; changes
  merge by element id, so two people never erase each other.
- Run it two ways: on your own machine for a quick share, or one free-tier deploy for always-on.
- Your captures still land with timestamps; your friend sees them appear live.

## Parked / not now
- Multi-board tabs (one board for now)
- Nickname picker for the tool (options offered at delivery: *Palaka* (school slate), *Petti* (box))
