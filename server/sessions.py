sessions = {}

def register_user(websocket, user_id):
    sessions[websocket] = user_id

def get_user(websocket):
    return sessions.get(websocket)

def unregister_user(websocket):
    sessions.pop(websocket, None)
