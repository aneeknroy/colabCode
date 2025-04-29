# main.py - FastAPI server with WebSocket support, user identification, and code execution
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import json
import uvicorn
import subprocess
import sys
import tempfile
import os
import io
import contextlib
import traceback
from typing import Dict
from threading import Timer

app = FastAPI()

# Store for connected clients
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}  # username -> websocket
        self.document: str = "# Write your Python code here\n\nprint('Hello, world!')"
        self.running_processes = {}
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
    
    def register_user(self, username: str, websocket: WebSocket):
        # Check if username already exists
        if username in self.active_connections:
            return False
        
        # Add connection
        self.active_connections[username] = websocket
        return True
    
    def disconnect(self, username: str):
        if username in self.active_connections:
            del self.active_connections[username]
            # Kill any running processes for this user
            if username in self.running_processes:
                try:
                    self.running_processes[username].kill()
                    del self.running_processes[username]
                except:
                    pass
    
    async def broadcast(self, message: Dict, exclude: str = None):
        disconnected_users = []
        
        for username, connection in self.active_connections.items():
            if exclude and username == exclude:
                continue
                
            try:
                await connection.send_json(message)
            except RuntimeError:
                disconnected_users.append(username)
        
        # Clean up any disconnected users
        for username in disconnected_users:
            self.disconnect(username)
    
    def update_document(self, content: str):
        self.document = content
    
    async def execute_code(self, code: str, username: str):
        """Execute Python code safely and return the output"""
        # Create a temporary file for the code
        try:
            with tempfile.NamedTemporaryFile(suffix='.py', delete=False, mode='w') as temp_file:
                temp_file_path = temp_file.name
                temp_file.write(code)
            
            # Set up stdout/stderr capture
            output = io.StringIO()
            error_output = io.StringIO()
            
            # Execute the code in a subprocess with a timeout
            with contextlib.redirect_stdout(output), contextlib.redirect_stderr(error_output):
                try:
                    # Start the process
                    process = subprocess.Popen(
                        [sys.executable, temp_file_path],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True
                    )
                    
                    # Store process for potential termination
                    self.running_processes[username] = process
                    
                    # Set a timeout
                    def kill_process():
                        if process.poll() is None:  # If process is still running
                            process.kill()
                    
                    timer = Timer(5.0, kill_process)  # 5 seconds timeout
                    timer.start()
                    
                    # Get output
                    stdout, stderr = process.communicate()
                    
                    # Cancel timer if process completed
                    timer.cancel()
                    
                    # Remove from running processes
                    if username in self.running_processes:
                        del self.running_processes[username]
                    
                    if process.returncode == 0:
                        return {'success': True, 'output': stdout}
                    else:
                        return {'success': False, 'error': stderr}
                    
                except Exception as e:
                    return {'success': False, 'error': str(e)}
                
        except Exception as e:
            error_traceback = traceback.format_exc()
            return {'success': False, 'error': f"Error executing code: {str(e)}\n{error_traceback}"}
        finally:
            # Clean up the temporary file
            try:
                os.unlink(temp_file_path)
            except:
                pass

manager = ConnectionManager()

# Serve static files
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/", response_class=HTMLResponse)
async def get():
    with open("static/index.html", "r") as f:
        return f.read()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    username = None
    
    try:
        # Wait for registration
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            
            if message["type"] == "register":
                username = message["username"]
                
                # Register the user
                if manager.register_user(username, websocket):
                    # Send current document state to the new client
                    await websocket.send_json({
                        "type": "init",
                        "content": manager.document,
                        "users": list(manager.active_connections.keys())
                    })
                    
                    # Notify all clients about the new user
                    await manager.broadcast({
                        "type": "user_joined",
                        "username": username,
                        "users": list(manager.active_connections.keys())
                    }, exclude=username)
                    
                    break
                else:
                    # Username taken
                    await websocket.send_json({
                        "type": "error",
                        "message": "Username already taken. Please choose another one."
                    })
                    await websocket.close()
                    return
        
        # Main message loop
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            
            if message["type"] == "update":
                # Update the document content
                manager.update_document(message["content"])
                # Broadcast changes to all clients
                await manager.broadcast({
                    "type": "update",
                    "content": message["content"],
                    "from": username
                })
                
            elif message["type"] == "run_code":
                # Execute the code
                result = await manager.execute_code(message["code"], username)
                
                # Send the result back to the client who initiated the run
                await websocket.send_json({
                    "type": "run_result",
                    "result": result
                })
                
                # Notify other users that code was executed
                await manager.broadcast({
                    "type": "code_execution",
                    "username": username,
                    "success": result["success"]
                }, exclude=username)
                
    except WebSocketDisconnect:
        if username:
            manager.disconnect(username)
            # Notify remaining users about the disconnection
            await manager.broadcast({
                "type": "user_left",
                "username": username,
                "users": list(manager.active_connections.keys())
            })

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)