import os
import asyncio
import threading
from flask import Flask, send_from_directory, request, jsonify
from flask_cors import CORS
import websockets
import json
import uuid
import logging
from typing import Dict, Set

# Flask App Setup
app = Flask(__name__)
CORS(app)

# Get port from environment (Replit sets this automatically)
PORT = int(os.environ.get('PORT', 8080))
WS_PORT = int(os.environ.get('WS_PORT', 8081))

# WebSocket Server Code (from collaboration_server.py)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global state for collaboration
users: Dict[str, dict] = {}
rooms: Dict[str, dict] = {}
user_connections: Dict[str, websockets.WebSocketServerProtocol] = {}

def generate_room_id():
    return ''.join([chr(65 + (int(uuid.uuid4().hex[i], 16) % 26)) for i in range(8)])

async def handle_websocket(websocket, path):
    user_id = None
    try:
        logger.info("WebSocket connection opened")
        async for message in websocket:
            try:
                data = json.loads(message)
                message_type = data.get('type')
                
                if message_type == 'register':
                    user_id = str(uuid.uuid4())
                    users[user_id] = {
                        'id': user_id,
                        'name': data.get('name', 'Anonymous'),
                        'room_id': None
                    }
                    user_connections[user_id] = websocket
                    
                    await websocket.send(json.dumps({
                        'type': 'registered',
                        'user_id': user_id,
                        'name': users[user_id]['name']
                    }))
                    logger.info(f"User registered: {users[user_id]['name']} ({user_id})")
                
                elif message_type == 'create_room':
                    if user_id and user_id in users:
                        room_id = generate_room_id()
                        rooms[room_id] = {
                            'id': room_id,
                            'name': data.get('room_name', f'Room {room_id}'),
                            'users': [user_id],
                            'max_users': data.get('max_users', 10),
                            'canvas_objects': {}
                        }
                        users[user_id]['room_id'] = room_id
                        
                        await websocket.send(json.dumps({
                            'type': 'room_created',
                            'room_id': room_id,
                            'room_name': rooms[room_id]['name']
                        }))
                        logger.info(f"Room created: {room_id} by user {user_id}")
                
                elif message_type == 'join_room':
                    if user_id and user_id in users:
                        room_id = data.get('room_id')
                        if room_id in rooms:
                            if user_id not in rooms[room_id]['users']:
                                rooms[room_id]['users'].append(user_id)
                            users[user_id]['room_id'] = room_id
                            
                            # Send room joined confirmation
                            await websocket.send(json.dumps({
                                'type': 'room_joined',
                                'room_id': room_id,
                                'room_name': rooms[room_id]['name'],
                                'users': [{'id': uid, 'name': users[uid]['name']} for uid in rooms[room_id]['users'] if uid in users]
                            }))
                            
                            # Broadcast to other users
                            for other_user_id in rooms[room_id]['users']:
                                if other_user_id != user_id and other_user_id in user_connections:
                                    try:
                                        await user_connections[other_user_id].send(json.dumps({
                                            'type': 'user_joined',
                                            'user': {'id': user_id, 'name': users[user_id]['name']}
                                        }))
                                    except:
                                        pass
                            
                            logger.info(f"User {user_id} joined room {room_id}")
                
                elif message_type == 'canvas_event':
                    if user_id and user_id in users and users[user_id]['room_id']:
                        room_id = users[user_id]['room_id']
                        if room_id in rooms:
                            # Broadcast to other users in the room
                            for other_user_id in rooms[room_id]['users']:
                                if other_user_id != user_id and other_user_id in user_connections:
                                    try:
                                        await user_connections[other_user_id].send(json.dumps({
                                            'type': 'canvas_event',
                                            'event': data.get('event'),
                                            'user_id': user_id
                                        }))
                                    except:
                                        pass
                            
                            logger.info(f"Canvas event: {data.get('event', {}).get('type')} from user {user_id}")
                
            except json.JSONDecodeError:
                logger.error("Invalid JSON received")
            except Exception as e:
                logger.error(f"Error handling message: {e}")
    
    except websockets.exceptions.ConnectionClosed:
        logger.info("WebSocket connection closed")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        # Cleanup
        if user_id:
            if user_id in user_connections:
                del user_connections[user_id]
            if user_id in users:
                room_id = users[user_id].get('room_id')
                if room_id and room_id in rooms:
                    if user_id in rooms[room_id]['users']:
                        rooms[room_id]['users'].remove(user_id)
                    if not rooms[room_id]['users']:
                        del rooms[room_id]
                        logger.info(f"Room {room_id} deleted (empty)")
                del users[user_id]
            logger.info(f"User unregistered: {user_id}")

# Flask Routes
@app.route('/')
def serve_index():
    return send_from_directory('.', 'frontend.html')

@app.route('/<path:filename>')
def serve_static(filename):
    return send_from_directory('.', filename)

@app.route('/health')
def health_check():
    return jsonify({"status": "healthy", "websocket_port": WS_PORT})

# Start WebSocket server in a separate thread
def start_websocket_server():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    start_server = websockets.serve(handle_websocket, "0.0.0.0", WS_PORT)
    logger.info(f"WebSocket server starting on port {WS_PORT}")
    
    loop.run_until_complete(start_server)
    loop.run_forever()

if __name__ == '__main__':
    # Start WebSocket server in background thread
    ws_thread = threading.Thread(target=start_websocket_server, daemon=True)
    ws_thread.start()
    
    logger.info(f"Starting Flask app on port {PORT}")
    logger.info(f"WebSocket server on port {WS_PORT}")
    
    # Start Flask app
    app.run(host='0.0.0.0', port=PORT, debug=False)
