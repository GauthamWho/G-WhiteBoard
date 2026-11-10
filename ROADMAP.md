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
| 8 | **Shared boards** — you in place A, friend in place B, one live board | ✅ Built + tested on this PC — room link, live two-window sync proven, merge-by-id; room bar is collapsible (tiny pill top-left). **Not yet tested across two real locations** — needs the free relay deploy (manual account step) |
| 9 | Mac setup + permission steps (built, **not run on the Mac yet**) | ⬜ |
| 10 | **Cloud deploy (Render free)** — always-on shared board, PC can be off | 🔄 Deploy prep committed (`render.yaml`, public bind + headless-safe hotkey). **Waiting on Gautham:** empty repo at github.com/new → push → 3 clicks on Render |
| 11 | **Daily auto-backups** — last 7 days in `watcher/data/backups/YYYY-MM-DD/` | ✅ Done + live-tested (fires on first save of each day, atomic copies, auto-prune) |

**WE ARE HERE →** Step 6 (your Flameshot retest) + Step 7 ready to push on your word.

### Step 8 — how shared boards work (built)

- Add `?room=anything` to the board URL → the page joins that room; share the link (Copy Link).
- A room relay (`watcher/server.py` `/room/<id>`, or the standalone `relay/relay.py` for free-host
  deploy) passes every change between all peers; changes merge by element id, so nobody erases
  anybody. Snapshots on join keep newcomers up to date.
- The room bar (link + who's online) has a **– button** to hide it — it collapses to a tiny
  pill in the top-left; click the pill to bring it back. Your choice is remembered.
- **Tested here:** two Edge windows in one room, both show "2 online", a capture sent to one
  lands on both (saved 30 elements on each). **Not yet tested:** two real locations (needs the
  relay deployed — see `relay/README.md`, manual free-host account step).

## Parked / not now
- Multi-board tabs (one board for now)
- Nickname picker for the tool (options offered at delivery: *Palaka* (school slate), *Petti* (box))
