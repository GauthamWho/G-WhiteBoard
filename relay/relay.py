#!/usr/bin/env python3
"""Whiteboard Catcher — standalone room relay.

Deploys to any Python host (Render free tier / Fly.io — see README.md).
Serves ONLY the WebSocket room relay: clients connect to /room/<room_id>,
every JSON message is relayed, wrapped, to everyone else in the same room.
No board serving, no hotkey. PORT comes from the environment (default 8787).
"""

import json
import os
import re

from aiohttp import WSMsgType, web

ROOM_ID_RE = re.compile(r"^[a-z0-9-]{3,64}$")
rooms: dict[str, set] = {}  # room_id -> sockets currently in the room
client_ids: dict = {}  # socket -> client id (set via {"type": "hello", "id": "..."})


async def send_all(room: set, message: dict, exclude=None) -> None:
    payload = json.dumps(message)
    for ws in list(room):
        if ws is exclude:
            continue
        try:
            await ws.send_str(payload)
        except Exception:
            room.discard(ws)


async def room_handler(request: web.Request) -> web.WebSocketResponse:
    room_id = request.match_info["room_id"]
    if not ROOM_ID_RE.match(room_id):
        return web.json_response({"ok": False, "error": "invalid room id"}, status=400)
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    room = rooms.setdefault(room_id, set())
    room.add(ws)
    await send_all(room, {"type": "peers", "count": len(room)})
    try:
        async for msg in ws:
            if msg.type != WSMsgType.TEXT:
                continue
            try:
                data = json.loads(msg.data)
            except Exception:
                continue  # non-JSON frames are ignored silently
            if not isinstance(data, dict):
                continue
            if data.get("type") == "hello":
                if isinstance(data.get("id"), str) and data["id"]:
                    client_ids[ws] = data["id"]
                continue
            cid = client_ids.get(ws)
            if cid is None:
                continue  # messages before hello are ignored
            await send_all(room, {"type": "change", "from": cid, "payload": data}, exclude=ws)
    finally:
        room.discard(ws)
        client_ids.pop(ws, None)
        await send_all(room, {"type": "peers", "count": len(room)})
        if not room:
            rooms.pop(room_id, None)  # prune empty rooms
    return ws


def make_app() -> web.Application:
    app = web.Application()
    app.router.add_get("/room/{room_id}", room_handler)
    return app


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8787"))
    web.run_app(make_app(), host="0.0.0.0", port=port, print=None)
