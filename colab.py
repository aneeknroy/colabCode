import asyncio
import json
import logging
import uuid
import os
from pathlib import Path
from aiohttp import web
import aiohttp_cors
from cryptography.fernet import Fernet

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Generate a secret key for the session
SECRET_KEY = Fernet.generate_key().decode()

# Store active connections and code content
clients = {}
code_content = "# Write your Python code here\nprint('Hello, collaborative world!')"
execution_results = {}

# HTML/CSS/JS for the web interface
STATIC_DIR = Path(__file__).parent / "static"
os.makedirs(STATIC_DIR, exist_ok=True)

# In your HTML file section, modify the index.html creation to ensure CodeMirror is loaded correctly
# Find this line in the HTML:
with open(STATIC_DIR / "index.html", "w") as f:
    f.write("""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Collaborative Code Editor</title>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.2/codemirror.min.css">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.2/theme/dracula.min.css">
    <style>
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            margin: 0;
            padding: 0;
            background-color: #f5f5f5;
            display: flex;
            flex-direction: column;
            height: 100vh;
        }
        header {
            background-color: #4a4a4a;
            color: white;
            padding: 1rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        header h1 {
            margin: 0;
            font-size: 1.5rem;
        }
        main {
            display: flex;
            flex: 1;
            overflow: hidden;
        }
        .editor-container {
            flex: 1;
            display: flex;
            flex-direction: column;
            border-right: 1px solid #ddd;
            background-color: white;  /* Add explicit background color */
        }
        .CodeMirror {
            height: 100% !important;
            font-size: 15px;
            border: 1px solid #ddd;  /* Add border to make editor visible */
        }
        .output-container {
            flex: 1;
            display: flex;
            flex-direction: column;
            background-color: #282a36;
            color: #f8f8f2;
        }
        .output-header {
            padding: 0.5rem 1rem;
            background-color: #44475a;
            color: #f8f8f2;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .output-content {
            flex: 1;
            padding: 1rem;
            font-family: 'Courier New', monospace;
            overflow: auto;
            white-space: pre-wrap;
        }
        .action-buttons {
            display: flex;
            gap: 10px;
        }
        button {
            background-color: #6272a4;
            color: white;
            border: none;
            padding: 0.5rem 1rem;
            border-radius: 4px;
            cursor: pointer;
            font-size: 14px;
            transition: background-color 0.2s;
        }
        button:hover {
            background-color: #7b8bbd;
        }
        .run-button {
            background-color: #50fa7b;
            color: #282a36;
        }
        .run-button:hover {
            background-color: #73ffa0;
        }
        .users-container {
            padding: 0.5rem 1rem;
            background-color: #f8f8f2;
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
        }
        .user-badge {
            background-color: #bd93f9;
            color: white;
            border-radius: 12px;
            padding: 2px 10px;
            font-size: 12px;
            display: inline-block;
        }
        .status-message {
            color: #8be9fd;
            margin-left: 10px;
            font-size: 14px;
        }
        .loader {
            border: 3px solid #f3f3f3;
            border-radius: 50%;
            border-top: 3px solid #50fa7b;
            width: 20px;
            height: 20px;
            animation: spin 1s linear infinite;
            display: none;
            margin-left: 10px;
        }
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        /* Add fallback for editor if CodeMirror fails to load */
        #codeEditor {
            width: 100%;
            height: 100%;
            min-height: 400px;
            font-family: 'Courier New', monospace;
            font-size: 15px;
            padding: 8px;
            display: block;
            border: none;
            resize: none;
        }
    </style>
</head>
<body>
    <header>
        <h1>Collaborative Code Editor</h1>
        <div class="action-buttons">
            <button id="clearBtn">Clear Editor</button>
            <button id="runBtn" class="run-button">Run Code</button>
        </div>
    </header>
    
    <div class="users-container" id="usersContainer">
        <span>Active Users:</span>
    </div>
    
    <main>
        <div class="editor-container">
            <textarea id="codeEditor"># Write your Python code here
print('Hello, collaborative world!')</textarea>
        </div>
        <div class="output-container">
            <div class="output-header">
                <span>Output</span>
                <div style="display: flex; align-items: center;">
                    <span id="statusMessage" class="status-message"></span>
                    <div id="loader" class="loader"></div>
                </div>
            </div>
            <div class="output-content" id="outputContent"></div>
        </div>
    </main>

    <script src="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.2/codemirror.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.2/mode/python/python.min.js"></script>
    <script>
        // Initialize CodeMirror editor
        let codeEditor;
        
        // Try-catch for CodeMirror initialization
        try {
            // Only initialize if CodeMirror exists
            if (window.CodeMirror) {
                codeEditor = CodeMirror.fromTextArea(document.getElementById('codeEditor'), {
                    mode: 'python',
                    theme: 'dracula',
                    lineNumbers: true,
                    indentUnit: 4,
                    indentWithTabs: false,
                    autoCloseBrackets: true,
                    matchBrackets: true,
                    lineWrapping: true
                });
                console.log("CodeMirror initialized successfully");
            } else {
                console.error("CodeMirror library not found");
                // Use the textarea as fallback
                codeEditor = {
                    getValue: function() {
                        return document.getElementById('codeEditor').value;
                    },
                    setValue: function(value) {
                        document.getElementById('codeEditor').value = value;
                    },
                    on: function(event, callback) {
                        if (event === 'change') {
                            document.getElementById('codeEditor').addEventListener('input', function() {
                                callback(this);
                            });
                        }
                    }
                };
            }
        } catch (e) {
            console.error("Error initializing CodeMirror:", e);
            // Use the textarea as fallback
            codeEditor = {
                getValue: function() {
                    return document.getElementById('codeEditor').value;
                },
                setValue: function(value) {
                    document.getElementById('codeEditor').value = value;
                },
                on: function(event, callback) {
                    if (event === 'change') {
                        document.getElementById('codeEditor').addEventListener('input', function() {
                            callback(this);
                        });
                    }
                }
            };
        }

        // Get DOM elements
        const runBtn = document.getElementById('runBtn');
        const clearBtn = document.getElementById('clearBtn');
        const outputContent = document.getElementById('outputContent');
        const usersContainer = document.getElementById('usersContainer');
        const statusMessage = document.getElementById('statusMessage');
        const loader = document.getElementById('loader');

        // User information
        const username = "User_" + Math.floor(Math.random() * 1000);
        const userColor = '#' + Math.floor(Math.random()*16777215).toString(16);
        let users = {};
        let ws;
        let isConnected = false;
        let isSendingChanges = false;

        // Connect to WebSocket
        function connectWebSocket() {
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            ws = new WebSocket(`${protocol}//${window.location.host}/ws`);
            
            ws.onopen = () => {
                isConnected = true;
                statusMessage.textContent = "Connected";
                // Send user info when connected
                ws.send(JSON.stringify({
                    type: 'join',
                    username: username
                }));
            };
            
            ws.onclose = () => {
                isConnected = false;
                statusMessage.textContent = "Disconnected. Reconnecting...";
                setTimeout(connectWebSocket, 2000);
            };
            
            ws.onerror = (error) => {
                console.error('WebSocket error:', error);
                statusMessage.textContent = "Connection error";
            };
            
            ws.onmessage = (event) => {
                const message = JSON.parse(event.data);
                
                switch (message.type) {
                    case 'init':
                        // Initialize the editor with current code
                        isSendingChanges = true;
                        codeEditor.setValue(message.code);
                        isSendingChanges = false;
                        
                        // Update users list
                        users = message.users;
                        updateUsersList();
                        break;
                        
                    case 'code_change':
                        // Update code without triggering the change event
                        if (message.username !== username) {
                            isSendingChanges = true;
                            codeEditor.setValue(message.code);
                            isSendingChanges = false;
                        }
                        break;
                        
                    case 'execution_result':
                        // Display execution result in output pane
                        outputContent.textContent = message.output;
                        loader.style.display = 'none';
                        statusMessage.textContent = "Execution complete";
                        break;
                        
                    case 'user_joined':
                        // Add new user to the list
                        users[message.username] = message.username;
                        updateUsersList();
                        break;
                        
                    case 'user_left':
                        // Remove user from the list
                        delete users[message.username];
                        updateUsersList();
                        break;
                }
            };
        }

        // Update the displayed list of users
        function updateUsersList() {
            const usersList = Object.keys(users);
            
            // Clear current list (except the "Active Users:" text)
            while (usersContainer.childNodes.length > 1) {
                usersContainer.removeChild(usersContainer.lastChild);
            }
            
            // Add user badges
            usersList.forEach(user => {
                const userBadge = document.createElement('span');
                userBadge.className = 'user-badge';
                userBadge.textContent = user;
                usersContainer.appendChild(userBadge);
            });
        }

        // Event listener for code changes
        codeEditor.on('change', (editor) => {
            if (!isSendingChanges && isConnected) {
                const code = editor.getValue();
                ws.send(JSON.stringify({
                    type: 'code_change',
                    username: username,
                    code: code
                }));
            }
        });

        // Event listener for running code
        runBtn.addEventListener('click', () => {
            if (isConnected) {
                const code = codeEditor.getValue();
                ws.send(JSON.stringify({
                    type: 'run_code',
                    username: username,
                    code: code
                }));
                
                // Show loading indicator
                loader.style.display = 'inline-block';
                statusMessage.textContent = "Running code...";
            } else {
                statusMessage.textContent = "Not connected. Cannot run code.";
            }
        });

        // Event listener for clearing code
        clearBtn.addEventListener('click', () => {
            if (isConnected) {
                codeEditor.setValue('# Write your Python code here\n');
            }
        });

        // Initialize connection
        connectWebSocket();
        
        // Add debugging info
        console.log("Page loaded. Editor setup complete.");
        document.addEventListener('DOMContentLoaded', () => {
            console.log("DOM fully loaded");
        });
    </script>
</body>
</html>
    """)

    
# Function to handle WebSocket connections
async def websocket_handler(request):
    global code_content  # Declare global before using it
    # global clients  # Declare global before using it
    # global isConnected  # Declare global before using it

    ws = web.WebSocketResponse()
    await ws.prepare(request)
    
    # Generate client ID and add to clients
    client_id = str(uuid.uuid4())
    clients[client_id] = {
        'ws': ws,
        'username': None
    }
    
    logger.info(f"New client connected: {client_id}")
    
    try:
        async for msg in ws:
            if msg.type == web.WSMsgType.TEXT:
                data = json.loads(msg.data)
                
                if data['type'] == 'join':
                    # User joins with a username
                    username = data['username']
                    clients[client_id]['username'] = username
                    logger.info(f"User {username} joined")
                    
                    # Send initial state to the new client
                    await ws.send_json({
                        'type': 'init',
                        'code': code_content,
                        'users': {c_id: info['username'] for c_id, info in clients.items() if info['username']}
                    })
                    
                    # Notify other clients about the new user
                    for cid, client in clients.items():
                        if cid != client_id and client['ws'].closed is False:
                            await client['ws'].send_json({
                                'type': 'user_joined',
                                'username': username
                            })
                
                elif data['type'] == 'code_change':
                    # Update code content for all clients
                    code_content = data['code']
                    
                    # Broadcast code change to all clients
                    for cid, client in clients.items():
                        if client['ws'].closed is False:
                            await client['ws'].send_json({
                                'type': 'code_change',
                                'username': data['username'],
                                'code': code_content
                            })
                
                elif data['type'] == 'run_code':
                    # Execute the Python code
                    code_to_run = data['code']
                    result = await execute_code(code_to_run)
                    
                    # Send execution result to all clients
                    for cid, client in clients.items():
                        if client['ws'].closed is False:
                            await client['ws'].send_json({
                                'type': 'execution_result',
                                'output': result
                            })
            
            elif msg.type == web.WSMsgType.ERROR:
                logger.error(f"WebSocket error: {ws.exception()}")
    
    finally:
        # Clean up when connection is closed
        if client_id in clients:
            username = clients[client_id]['username']
            del clients[client_id]
            
            # Notify other clients about user leaving
            if username:
                for cid, client in clients.items():
                    if client['ws'].closed is False:
                        await client['ws'].send_json({
                            'type': 'user_left',
                            'username': username
                        })
        
        logger.info(f"Client disconnected: {client_id}")
    
    return ws

# Execute Python code safely using asyncio.create_subprocess_exec
async def execute_code(code):
    # Create a temporary file
    tmp_file = f"/tmp/code_{uuid.uuid4()}.py"
    try:
        with open(tmp_file, "w") as f:
            f.write(code)
        
        # Run the code with a timeout
        proc = await asyncio.create_subprocess_exec(
            "python3", tmp_file,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=5.0)
            
            if stderr:
                result = f"Error:\n{stderr.decode()}"
            else:
                result = stdout.decode()
                
            # Limit output to prevent excessive data
            if len(result) > 10000:
                result = result[:10000] + "\n... (output truncated)"
                
            return result
        except asyncio.TimeoutError:
            proc.kill()
            return "Execution timed out after 5 seconds"
    
    except Exception as e:
        return f"Error executing code: {str(e)}"
    
    finally:
        # Clean up the temporary file
        if os.path.exists(tmp_file):
            os.remove(tmp_file)

# Set up routes
async def index(request):
    return web.FileResponse(STATIC_DIR / "index.html")

async def on_startup(app):
    logger.info("Server starting up")

async def on_shutdown(app):
    # Close all WebSocket connections
    for client_id, client in clients.items():
        if not client['ws'].closed:
            await client['ws'].close()
    logger.info("Server shutting down")

# Create and configure the web application
app = web.Application()
app.on_startup.append(on_startup)
app.on_shutdown.append(on_shutdown)

# Add routes
app.router.add_get("/", index)
app.router.add_get("/ws", websocket_handler)
app.router.add_static("/static", STATIC_DIR)

# Configure CORS
cors = aiohttp_cors.setup(app, defaults={
    "*": aiohttp_cors.ResourceOptions(
        allow_credentials=True,
        expose_headers="*",
        allow_headers="*"
    )
})

# Apply CORS to all routes
for route in list(app.router.routes()):
    cors.add(route)

if __name__ == "__main__":
    web.run_app(app, host="0.0.0.0", port=8080)
    logger.info("Server started on http://localhost:8080")