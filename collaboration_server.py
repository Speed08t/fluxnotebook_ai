#!/usr/bin/env python3
"""
Real-time Canvas Collaboration Server
Handles WebSocket connections, room management, and canvas synchronization
"""

import asyncio
import json
import logging
import uuid
import time
from typing import Dict, Set, Optional, Any
from dataclasses import dataclass, asdict
from datetime import datetime

import websockets
from websockets.server import WebSocketServerProtocol
from websockets.exceptions import ConnectionClosed

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class User:
    """Represents a connected user"""
    id: str
    name: str
    websocket: WebSocketServerProtocol
    room_id: Optional[str] = None
    cursor_x: float = 0
    cursor_y: float = 0
    last_seen: float = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            'id': self.id,
            'name': self.name,
            'room_id': self.room_id,
            'cursor_x': self.cursor_x,
            'cursor_y': self.cursor_y,
            'last_seen': self.last_seen
        }

@dataclass
class Room:
    """Represents a collaboration room"""
    id: str
    name: str
    max_users: int
    created_at: float
    canvas_state: Dict[str, Any]
    users: Set[str]
    host_id: str  # ID of the user who created the room
    last_activity: float = 0
    empty_since: Optional[float] = None
    broadcast_enabled: bool = False
    broadcast_pdf: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            'id': self.id,
            'name': self.name,
            'max_users': self.max_users,
            'created_at': self.created_at,
            'user_count': len(self.users),
            'canvas_state': self.canvas_state,
            'host_id': self.host_id,
            'broadcast_enabled': self.broadcast_enabled,
            'broadcast_pdf': self.broadcast_pdf
        }

class CollaborationServer:
    """Main collaboration server class"""
    
    def __init__(self):
        self.users: Dict[str, User] = {}
        self.rooms: Dict[str, Room] = {}
        self.websocket_to_user: Dict[WebSocketServerProtocol, str] = {}
        
    def generate_room_id(self) -> str:
        """Generate a unique room ID"""
        while True:
            room_id = str(uuid.uuid4())[:8].upper()
            if room_id not in self.rooms:
                return room_id
    
    def generate_user_id(self) -> str:
        """Generate a unique user ID"""
        return str(uuid.uuid4())
    
    async def register_user(self, websocket: WebSocketServerProtocol, name: str) -> str:
        """Register a new user"""
        user_id = self.generate_user_id()
        user = User(
            id=user_id,
            name=name,
            websocket=websocket,
            last_seen=time.time()
        )
        
        self.users[user_id] = user
        self.websocket_to_user[websocket] = user_id
        
        logger.info(f"User registered: {name} ({user_id})")
        return user_id
    
    async def unregister_user(self, websocket: WebSocketServerProtocol):
        """Unregister a user and clean up"""
        if websocket not in self.websocket_to_user:
            return
            
        user_id = self.websocket_to_user[websocket]
        user = self.users.get(user_id)
        
        if user and user.room_id:
            await self.leave_room(user_id)
        
        if user_id in self.users:
            del self.users[user_id]
        if websocket in self.websocket_to_user:
            del self.websocket_to_user[websocket]
            
        logger.info(f"User unregistered: {user_id}")
    
    async def create_room(self, user_id: str, room_name: str, max_users: int) -> str:
        """Create a new collaboration room"""
        room_id = self.generate_room_id()
        current_time = time.time()
        room = Room(
            id=room_id,
            name=room_name or f"Room {room_id}",
            max_users=max_users,
            created_at=current_time,
            canvas_state={'objects': [], 'background': '#ffffff'},
            users=set(),
            host_id=user_id,  # Set the room creator as host
            last_activity=current_time,
            empty_since=None
        )

        self.rooms[room_id] = room
        await self.join_room(user_id, room_id)

        logger.info(f"Room created: {room_id} by user {user_id} (host)")
        return room_id
    
    async def join_room(self, user_id: str, room_id: str) -> bool:
        """Join a user to a room"""
        if room_id not in self.rooms:
            return False

        room = self.rooms[room_id]
        user = self.users.get(user_id)

        if not user or len(room.users) >= room.max_users:
            return False

        # Leave current room if in one
        if user.room_id:
            await self.leave_room(user_id)

        # Join new room
        room.users.add(user_id)
        user.room_id = room_id
        room.last_activity = time.time()

        # Clear empty_since flag if room was marked for deletion
        if room.empty_since:
            room.empty_since = None
            logger.info(f"Room {room_id} no longer empty - cleanup cancelled")

        # Notify other users in the room
        await self.broadcast_to_room(room_id, {
            'type': 'user_joined',
            'user': user.to_dict(),
            'room': room.to_dict()
        }, exclude_user=user_id)

        # Send current canvas state to the new user
        await self.send_to_user(user_id, {
            'type': 'canvas_state',
            'state': room.canvas_state,
            'room': room.to_dict(),
            'users': [self.users[uid].to_dict() for uid in room.users if uid in self.users]
        })

        logger.info(f"User {user_id} joined room {room_id}")
        return True
    
    async def leave_room(self, user_id: str, is_kicked: bool = False):
        """Remove a user from their current room"""
        user = self.users.get(user_id)
        if not user or not user.room_id:
            return

        room_id = user.room_id
        room = self.rooms.get(room_id)

        if room:
            room.users.discard(user_id)
            room.last_activity = time.time()

            if user_id == room.host_id:
                room.broadcast_enabled = False
                room.broadcast_pdf = None
                await self.broadcast_to_room(room_id, {
                    'type': 'host_broadcast_state',
                    'enabled': False,
                    'host_id': room.host_id
                })

            # Only notify other users if this is not a kick (kick has its own notification)
            if not is_kicked:
                await self.broadcast_to_room(room_id, {
                    'type': 'user_left',
                    'user_id': user_id,
                    'room': room.to_dict()
                })

            # Mark room as empty but don't delete immediately (for auto-rejoin)
            if len(room.users) == 0:
                room.empty_since = time.time()
                logger.info(f"Room {room_id} is now empty, marked for delayed cleanup")
                # Schedule cleanup after 30 seconds to allow for auto-rejoin
                asyncio.create_task(self.schedule_room_cleanup(room_id, 30))

        user.room_id = None
        action = "was kicked from" if is_kicked else "left"
        logger.info(f"User {user_id} {action} room {room_id}")

    async def kick_user(self, host_id: str, target_user_id: str) -> bool:
        """Kick a user from the room (host only)"""
        host = self.users.get(host_id)
        target_user = self.users.get(target_user_id)

        if not host or not target_user or not host.room_id:
            return False

        room = self.rooms.get(host.room_id)
        if not room:
            return False

        # Check if the requesting user is the host
        if room.host_id != host_id:
            logger.warning(f"User {host_id} attempted to kick {target_user_id} but is not the host of room {room.id}")
            return False

        # Check if target user is in the same room
        if target_user.room_id != room.id:
            return False

        # Cannot kick the host (themselves)
        if target_user_id == host_id:
            return False

        # Notify the kicked user
        await self.send_to_user(target_user_id, {
            'type': 'kicked',
            'room_id': room.id,
            'kicked_by': host.name
        })

        # Remove user from room (mark as kicked to prevent "left room" message)
        await self.leave_room(target_user_id, is_kicked=True)

        # Notify other users in the room
        await self.broadcast_to_room(room.id, {
            'type': 'user_kicked',
            'user_id': target_user_id,
            'user_name': target_user.name,
            'kicked_by': host.name,
            'room': room.to_dict()
        })

        logger.info(f"User {target_user_id} ({target_user.name}) was kicked from room {room.id} by host {host_id} ({host.name})")
        return True

    async def schedule_room_cleanup(self, room_id: str, delay_seconds: int):
        """Schedule room cleanup after a delay to allow for auto-rejoin"""
        await asyncio.sleep(delay_seconds)

        room = self.rooms.get(room_id)
        if room and len(room.users) == 0 and room.empty_since:
            # Only delete if room is still empty and hasn't been rejoined
            if time.time() - room.empty_since >= delay_seconds:
                del self.rooms[room_id]
                logger.info(f"Room {room_id} deleted after {delay_seconds}s delay (still empty)")
            else:
                logger.info(f"Room {room_id} cleanup cancelled - room was rejoined")
    
    async def send_to_user(self, user_id: str, message: Dict[str, Any]):
        """Send a message to a specific user"""
        user = self.users.get(user_id)
        if user:
            try:
                await user.websocket.send(json.dumps(message))
            except ConnectionClosed:
                await self.unregister_user(user.websocket)
    
    async def broadcast_to_room(self, room_id: str, message: Dict[str, Any], exclude_user: Optional[str] = None):
        """Broadcast a message to all users in a room"""
        room = self.rooms.get(room_id)
        if not room:
            return
            
        for user_id in room.users.copy():
            if user_id != exclude_user:
                await self.send_to_user(user_id, message)
    
    async def handle_canvas_event(self, user_id: str, event_data: Dict[str, Any]):
        """Handle canvas drawing events"""
        user = self.users.get(user_id)
        if not user or not user.room_id:
            logger.warning(f"Canvas event from user {user_id} without room")
            return

        room = self.rooms.get(user.room_id)
        if not room:
            logger.warning(f"Canvas event from user {user_id} for non-existent room {user.room_id}")
            return

        # Update canvas state based on event type
        event_type = event_data.get('type')
        logger.info(f"Handling canvas event: {event_type} from user {user_id} in room {user.room_id}")

        # Handle all canvas operation types
        if event_type in ['object_added', 'path_created']:
            obj_data = event_data.get('object') or event_data.get('path')
            obj_id = event_data.get('object_id')
            if obj_data:
                # ✨ CRITICAL FIX: Ensure stored clone keeps its ID
                # This prevents the issue where third+ users can't move objects
                # because the server stores objects without IDs
                if obj_id and not obj_data.get('id'):
                    obj_data['id'] = obj_id
                    logger.info(f"🔧 Patched missing ID for {event_type}: {obj_id}")
                room.canvas_state['objects'].append(obj_data)
        elif event_type == 'object_modified':
            # Find and update the object
            obj_id = event_data.get('object_id')
            new_obj = event_data.get('object')
            if obj_id and new_obj:
                # ✨ CRITICAL FIX: Ensure replacement object keeps its ID
                if not new_obj.get('id'):
                    new_obj['id'] = obj_id
                    logger.info(f"🔧 Patched missing ID for object_modified: {obj_id}")
                for i, obj in enumerate(room.canvas_state['objects']):
                    if obj.get('id') == obj_id:
                        room.canvas_state['objects'][i] = new_obj
                        break
        elif event_type == 'object_removed':
            obj_id = event_data.get('object_id')
            logger.info(f"Removing object {obj_id} from room {user.room_id}")
            initial_count = len(room.canvas_state['objects'])
            room.canvas_state['objects'] = [
                obj for obj in room.canvas_state['objects']
                if obj.get('id') != obj_id
            ]
            final_count = len(room.canvas_state['objects'])
            logger.info(f"Object removal: {initial_count} -> {final_count} objects")
        elif event_type == 'canvas_cleared':
            room.canvas_state['objects'] = []
            if 'background' in event_data:
                room.canvas_state['background'] = event_data['background']
        elif event_type == 'background_changed':
            room.canvas_state['background'] = event_data.get('background')
            # Store pattern data if it's a CSS pattern
            if event_data.get('background') == 'css_pattern' and event_data.get('pattern'):
                room.canvas_state['pattern'] = event_data.get('pattern')
                logger.info(f"Stored CSS pattern: {event_data.get('pattern', {}).get('type', 'unknown')}")
            elif event_data.get('background') != 'css_pattern':
                # Clear pattern data for solid backgrounds
                room.canvas_state.pop('pattern', None)
        elif event_type in ['object_moving', 'object_scaling', 'object_rotating']:
            # Real-time operations - broadcast immediately without storing state
            # The final state will be captured by object_modified
            logger.info(f"Real-time operation: {event_type} for object {event_data.get('object_id')}")
        elif event_type in ['selection_created', 'selection_updated', 'selection_cleared']:
            # Selection events are for real-time collaboration feedback
            logger.info(f"Selection operation: {event_type} from user {user_id}")

        # Broadcast the event to other users in the room
        other_users = [uid for uid in room.users if uid != user_id]
        logger.info(f"Broadcasting {event_type} event to {len(other_users)} other users: {other_users}")

        await self.broadcast_to_room(user.room_id, {
            'type': 'canvas_event',
            'event': event_data,
            'user_id': user_id
        }, exclude_user=user_id)
    
    async def handle_cursor_move(self, user_id: str, x: float, y: float):
        """Handle cursor movement"""
        user = self.users.get(user_id)
        if not user or not user.room_id:
            return

        user.cursor_x = x
        user.cursor_y = y
        user.last_seen = time.time()

        # Broadcast cursor position to other users in the room
        await self.broadcast_to_room(user.room_id, {
            'type': 'cursor_move',
            'user_id': user_id,
            'x': x,
            'y': y
        }, exclude_user=user_id)

    async def update_broadcast_state(self, user_id: str, enabled: bool):
        """Update host broadcast toggle"""
        user = self.users.get(user_id)
        if not user or not user.room_id:
            return

        room = self.rooms.get(user.room_id)
        if not room or room.host_id != user_id:
            return

        room.broadcast_enabled = bool(enabled)
        if not room.broadcast_enabled:
            room.broadcast_pdf = None

        await self.broadcast_to_room(room.id, {
            'type': 'host_broadcast_state',
            'enabled': room.broadcast_enabled,
            'host_id': room.host_id,
            'pdf': room.broadcast_pdf
        })

    async def handle_host_broadcast_ai_message(self, user_id: str, message: Dict[str, Any]):
        """Forward host AI chat messages to room participants"""
        if not message:
            return

        user = self.users.get(user_id)
        if not user or not user.room_id:
            return

        room = self.rooms.get(user.room_id)
        if not room or room.host_id != user_id or not room.broadcast_enabled:
            return

        await self.broadcast_to_room(room.id, {
            'type': 'host_broadcast_ai_message',
            'host_id': user_id,
            'message': message
        }, exclude_user=user_id)

    async def handle_host_broadcast_pdf(self, user_id: str, payload: Dict[str, Any]):
        """Handle host PDF synchronization"""
        user = self.users.get(user_id)
        if not user or not user.room_id:
            return

        room = self.rooms.get(user.room_id)
        if not room or room.host_id != user_id or not room.broadcast_enabled:
            return

        action = payload.get('action')
        data = payload.get('data', {})

        if action == 'load':
            room.broadcast_pdf = {
                'pdf_name': data.get('pdf_name'),
                'pdf_data': data.get('pdf_data'),
                'current_page': data.get('current_page'),
                'total_pages': data.get('total_pages'),
                'timestamp': data.get('timestamp')
            }
        elif action == 'page_change' and room.broadcast_pdf:
            room.broadcast_pdf['current_page'] = data.get('current_page')
            room.broadcast_pdf['timestamp'] = data.get('timestamp')
        elif action == 'close':
            room.broadcast_pdf = None

        await self.broadcast_to_room(room.id, {
            'type': 'host_broadcast_pdf',
            'host_id': user_id,
            'action': action,
            'data': data
        }, exclude_user=user_id)

    async def update_user_name(self, user_id: str, new_name: str):
        """Update a user's display name"""
        user = self.users.get(user_id)
        if not user:
            return False

        old_name = user.name
        user.name = new_name

        # If user is in a room, notify other users about the name change
        if user.room_id:
            await self.broadcast_to_room(user.room_id, {
                'type': 'user_name_updated',
                'user_id': user_id,
                'old_name': old_name,
                'new_name': new_name,
                'user': user.to_dict()
            }, exclude_user=user_id)

        logger.info(f"User {user_id} changed name from '{old_name}' to '{new_name}'")
        return True

    async def handle_video_call_event(self, user_id: str, event_type: str, event_data: Dict[str, Any], room_id: str = None):
        """Handle video call events and broadcast to room members"""
        user = self.users.get(user_id)
        if not user:
            return

        # Use user's current room if room_id not specified
        target_room_id = room_id or user.room_id
        if not target_room_id or target_room_id not in self.rooms:
            return

        room = self.rooms[target_room_id]

        # Log the video call event
        logger.info(f"Video call event '{event_type}' from user {user_id} in room {target_room_id}")

        # Broadcast video call event to all users in the room
        await self.broadcast_to_room(target_room_id, {
            'type': 'video_call_event',
            'event_type': event_type,
            'data': event_data,
            'user_id': user_id,
            'room_id': target_room_id,
            'timestamp': time.time()
        }, exclude_user=user_id)

        # Handle specific event types if needed
        if event_type == 'call_started':
            logger.info(f"Video call started in room {target_room_id} by user {user_id}")
        elif event_type == 'call_ended':
            logger.info(f"Video call ended in room {target_room_id} by user {user_id}")
        elif event_type == 'participant_joined':
            logger.info(f"Participant joined video call in room {target_room_id}")
        elif event_type == 'participant_left':
            logger.info(f"Participant left video call in room {target_room_id}")

# Global server instance
server = CollaborationServer()

async def handle_websocket(websocket: WebSocketServerProtocol, path: str = "/ws"):
    """Handle WebSocket connections (can be used with flask-sock adapter)"""
    user_id = None
    
    try:
        async for message in websocket:
            try:
                data = json.loads(message)
                message_type = data.get('type')
                
                if message_type == 'register':
                    user_id = await server.register_user(websocket, data.get('name', 'Anonymous'))
                    await websocket.send(json.dumps({
                        'type': 'registered',
                        'user_id': user_id,
                        'success': True
                    }))
                
                elif message_type == 'create_room':
                    if user_id:
                        room_id = await server.create_room(
                            user_id, 
                            data.get('room_name', ''), 
                            data.get('max_users', 10)
                        )
                        await websocket.send(json.dumps({
                            'type': 'room_created',
                            'room_id': room_id,
                            'success': True
                        }))
                
                elif message_type == 'join_room':
                    if user_id:
                        success = await server.join_room(user_id, data.get('room_id'))
                        await websocket.send(json.dumps({
                            'type': 'room_joined',
                            'success': success,
                            'room_id': data.get('room_id') if success else None
                        }))
                
                elif message_type == 'leave_room':
                    if user_id:
                        await server.leave_room(user_id)
                        await websocket.send(json.dumps({
                            'type': 'room_left',
                            'success': True
                        }))
                
                elif message_type == 'canvas_event':
                    if user_id:
                        await server.handle_canvas_event(user_id, data.get('event', {}))
                
                elif message_type == 'cursor_move':
                    if user_id:
                        await server.handle_cursor_move(
                            user_id,
                            data.get('x', 0),
                            data.get('y', 0)
                        )

                elif message_type == 'update_name':
                    if user_id:
                        new_name = data.get('name', 'Anonymous')
                        success = await server.update_user_name(user_id, new_name)
                        await websocket.send(json.dumps({
                            'type': 'name_updated',
                            'success': success,
                            'new_name': new_name
                        }))

                elif message_type == 'kick_user':
                    if user_id:
                        target_user_id = data.get('target_user_id')
                        if target_user_id:
                            success = await server.kick_user(user_id, target_user_id)
                            await websocket.send(json.dumps({
                                'type': 'kick_result',
                                'success': success,
                                'target_user_id': target_user_id
                            }))

                elif message_type == 'video_call_event':
                    if user_id:
                        await server.handle_video_call_event(
                            user_id,
                            data.get('event_type'),
                            data.get('data', {}),
                            data.get('room_id')
                        )
                
                elif message_type == 'host_broadcast_control':
                    if user_id:
                        await server.update_broadcast_state(user_id, data.get('enabled', False))

                elif message_type == 'host_broadcast_ai_message':
                    if user_id:
                        await server.handle_host_broadcast_ai_message(user_id, data.get('message', {}))

                elif message_type == 'host_broadcast_pdf':
                    if user_id:
                        await server.handle_host_broadcast_pdf(user_id, data.get('data', {}))

                elif message_type == 'ping':
                    await websocket.send(json.dumps({'type': 'pong'}))
                
            except json.JSONDecodeError:
                logger.error("Invalid JSON received from websocket client")
            except Exception as e:
                logger.error(f"Error handling message: {e}")
                
    except ConnectionClosed:
        logger.info("WebSocket connection closed")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        if user_id:
            await server.unregister_user(websocket)

def main():
    """Start the collaboration server"""
    host = "0.0.0.0"  # Accept connections from any device on the network
    port = 8765

    logger.info(f"Starting collaboration server on {host}:{port}")
    logger.info("Server will accept connections from any device on the network")

    start_server = websockets.serve(handle_websocket, host, port)
    
    asyncio.get_event_loop().run_until_complete(start_server)
    asyncio.get_event_loop().run_forever()

if __name__ == "__main__":
    main()
