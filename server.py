from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import asyncio
import subprocess

app = FastAPI()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            code = await websocket.receive_text()
            process = subprocess.Popen(
                ['python3', '-u', '-c', code],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )

            async def stream_output(stream, label):
                for line in iter(stream.readline, ''):
                    await websocket.send_text(f"{label}: {line}")
                stream.close()

            await asyncio.gather(
                stream_output(process.stdout, "stdout"),
                stream_output(process.stderr, "stderr")
            )
            await websocket.send_text("done")

    except WebSocketDisconnect:
        pass
