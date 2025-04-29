from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
import uvicorn
import json

app = FastAPI()
# Shared document state
shared_text = ""
app.user_connections = set()

@app.get("/")
async def get_index():
    return FileResponse("index.html")

@app.websocket("/ws")
async def collab_ws(websocket: WebSocket):
    global shared_text
    await websocket.accept()
    client_id = id(websocket)
    app.user_connections.add(websocket)
    # Send initial text
    await websocket.send_text(json.dumps({ 'type': 'init', 'text': shared_text }))
    try:
        while True:
            data = await websocket.receive_text()
            msg = json.loads(data)
            if msg['type'] == 'update':
                shared_text = msg['text']
                # Broadcast to others
                broadcast = json.dumps({ 'type': 'update', 'text': shared_text, 'client': client_id })
                for conn in list(app.user_connections):
                    if conn is not websocket:
                        await conn.send_text(broadcast)
    except WebSocketDisconnect:
        app.user_connections.discard(websocket)

@app.websocket("/exec")
async def exec_ws(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            code = await websocket.receive_text()
            # Execute user code
            import subprocess
            proc = subprocess.Popen([ 'python3', '-u', '-c', code ],
                                     stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE,
                                     text=True)
            for line in proc.stdout:
                await websocket.send_text(f"stdout: {line.rstrip()}" )
            for line in proc.stderr:
                await websocket.send_text(f"stderr: {line.rstrip()}" )
            await websocket.send_text('done')
    except WebSocketDisconnect:
        pass

if __name__ == "__main__":
    uvicorn.run("server:app", host="0.0.0.0", port=8000)