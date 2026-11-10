# Room Relay

Standalone WebSocket relay for shared rooms (`relay.py`, aiohttp only).
This is the file that gets deployed to a free host — the local watcher server
(`watcher/server.py`) serves the exact same `/room/<id>` endpoint for LAN use,
but the public URL needs a hosted relay.

**Deploying is a manual step** (needs an account on Render or Fly.io).

## What it does

- `GET /room/<room_id>` — WebSocket endpoint. Room ids are lowercase
  `[a-z0-9-]{3,64}`; anything else gets a `400`.
- First message from a client must be `{"type": "hello", "id": "<uuid>"}`;
  messages before hello are ignored.
- Every JSON message a client sends is relayed to **everyone else in the
  room** (never echoed back) wrapped as:
  `{"type": "change", "from": <client_id>, "payload": <original message>}`.
- Join/leave broadcasts `{"type": "peers", "count": N}` to the whole room.
  Empty rooms are pruned. Non-JSON frames are ignored silently.
- Reads `PORT` from the environment (default `8787`), binds `0.0.0.0`.

## Run locally

```sh
pip install aiohttp
python relay.py            # ws://localhost:8787/room/<id>
```

## Deploy (manual, pick one)

### Render free tier
1. Push this repo to GitHub (if not already).
2. On render.com → **New → Web Service** → connect the repo.
3. Settings: Runtime **Python 3**, Build command `pip install aiohttp`,
   Start command `python relay/relay.py`. Render sets `PORT` automatically.
4. Note the URL, e.g. `https://whiteboard-relay-xxxx.onrender.com`.

### Fly.io
1. `fly launch --no-deploy` in `relay/` (internal_port = 8080), then
   `fly deploy`. Fly sets `PORT` to 8080 by default — set
   `fly vars set PORT=8080` if needed.
2. Note the URL, e.g. `https://<app-name>.fly.dev`.

## Connecting the whiteboard page

Once deployed, share a board by adding `?room=<id>` to the page URL hosted
anywhere (the local watcher, or a static host):

```
http://localhost:8765/?room=my-board-1
https://<relay-host>/room/my-board-1   <- what the page will dial (wss)
```

The page connects to `wss://<relay-host>/room/<id>` and syncs elements/files
with everyone who opens the same link. Without `?room=` the page stays in
solo mode (no room traffic at all).

> To point the page at a hosted relay instead of same-origin
> (`location.host`), the room URL would need a config knob — currently the
> page assumes the relay is on the same host as the page. Deploying the
> *whole* watcher (page + relay) as one service on Render is the zero-config
> path; a split deployment needs that small follow-up.
