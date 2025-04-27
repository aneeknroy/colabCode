import asyncio
import websockets
import json
from collections import defaultdict

rooms = defaultdict(set)
user_sessions = {}

async def handler(websocket, path):
    room_id = path.strip("/")
    rooms[room_id].add(websocket)
    user_id = f"user_{id(websocket)}"
    user_sessions[websocket] = {"id": user_id}
    await broadcast_user_list(room_id)

    try:
        async for message in websocket:
            data = json.loads(message)
            data["sender"] = user_id
            for client in rooms[room_id]:
                if client != websocket:
                    await client.send(json.dumps(data))
    finally:
        rooms[room_id].remove(websocket)
        user_sessions.pop(websocket, None)
        await broadcast_user_list(room_id)

async def broadcast_user_list(room_id):
    user_list = [
        user_sessions[client]["id"]
        for client in rooms[room_id]
        if client in user_sessions
    ]
    message = json.dumps({
        "type": "user_list",
        "users": user_list
    })
    for client in rooms[room_id]:
        await client.send(message)

async def main():
    print("WebSocket server running at ws://localhost:6789/<room_id>")
    async with websockets.serve(handler, "localhost", 6789):
        await asyncio.Future()  # Run forever

if __name__ == "__main__":
    asyncio.run(main())
