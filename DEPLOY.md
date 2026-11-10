# Putting your board online (free) — so a distant friend can join

Your board normally runs only on your PC. To work on **one shared board with
someone in another city**, the board needs to live on the internet. This guide
puts it on [Render](https://render.com)'s free tier — no credit card, ~10 minutes, once.

## How the pieces work after this

```
Your PC                                  Your friend
┌──────────────────────────┐             ┌──────────────────┐
│ Watcher (hotkey +        │             │                  │
│ clipboard) + board tab   │             │   Just a browser │
└────────────┬─────────────┘             └────────┬─────────┘
             │  your captures flow up             │
             ▼                                    ▼
        ┌─────────────────────────────────────────────┐
        │  Your board on Render (free, always on)     │
        │  https://your-board.onrender.com/?room=X    │
        └─────────────────────────────────────────────┘
```

- **You** keep using your PC exactly as before: copy → `Ctrl+Shift+C` (Mac: `Fn+Cmd+C`). Your capture
  appears on your local board **and** flows up to the shared online board.
- **Your friend** only needs a browser and the room link.
- **Your PC can be off.** The online board is always up.

## One-time setup

**Step 1 — the code must be on GitHub.** If you followed the README, you already
cloned it. Push it to your own GitHub repo (public or private both work on Render):

```bash
git remote add origin https://github.com/<your-username>/G-WhiteBoard.git
git push -u origin master
```

**Step 2 — create a free Render account.** Go to [render.com](https://render.com)
→ Sign up with email (no card needed).

**Step 3 — create the service (3 clicks).**

1. Dashboard → **New +** → **Web Service**
2. Pick **Build and deploy from a Git repository** → connect your GitHub →
   choose your `G-WhiteBoard` repo. Render reads the included `render.yaml`
   automatically — you don't fill in any settings.
3. Click **Apply**. Wait ~2 minutes for the first build.

You'll get a link like `https://g-whiteboard-xxxx.onrender.com`.

**Step 4 — share the room.** Open `<your-link>/?room=whatever-name`, click
**Copy Link** in the room bar, and send it to your friend. You're both on the
same live board.

## Honest limits of the free tier

- The online board **sleeps after 15 idle minutes**; the first visitor of the
  day waits ~30 seconds for it to wake. After that it's instant.
- The online copy of the board is stored on a **temporary disk**: if Render
  restarts the service (rare, or on a redeploy), the online board starts empty
  and refills live from whoever is in the room. Your own PC's board is never
  affected — that one is saved on your disk permanently.
- One free instance is plenty for a small group of friends.

## Local vs online — which board is which?

| URL | What it is |
|---|---|
| `http://localhost:8765` | Your **private** board on your PC (captures land here) |
| `https://...onrender.com/?room=X` | The **shared** board in the cloud (room sync) |

A capture with `Ctrl+Shift+C` (Mac: `Fn+Cmd+C`) always lands on your private board, and — while
your browser tab has a room open — flows to everyone in that room too.
