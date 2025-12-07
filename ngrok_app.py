import os
import asyncio
import threading
import json
import uuid
import logging
import base64
import io
import time
import socket
import requests
from datetime import datetime
from typing import Dict, Set
from flask import Flask, send_from_directory, request, jsonify
from flask_cors import CORS
from flask_sock import Sock
import google.generativeai as genai

class RateLimitError(Exception):
    """Raised when Gemini returns a 429 rate limit response."""
    def __init__(self, message, retry_after=None):
        super().__init__(message)
        self.retry_after = retry_after
try:
    from PIL import Image
except ImportError:
    print("PIL (Pillow) not found. Installing...")
    import subprocess
    subprocess.check_call(["pip", "install", "Pillow"])
    from PIL import Image

# Import bandwidth monitor
try:
    from bandwidth_monitor import BandwidthMonitor, create_bandwidth_middleware
    BANDWIDTH_MONITORING = True
except ImportError:
    print("Bandwidth monitoring not available. Run without monitoring.")
    BANDWIDTH_MONITORING = False



def mask_key(api_key: str) -> str:
    """Return a lightly masked key for logging."""
    if not api_key or len(api_key) < 8:
        return "unset"
    return f"{api_key[:4]}…{api_key[-4:]}"

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Flask App Setup
app = Flask(__name__)
CORS(app)
sock = Sock(app)

# Initialize bandwidth monitoring
if BANDWIDTH_MONITORING:
    bandwidth_monitor = BandwidthMonitor()
    app = create_bandwidth_middleware(app, bandwidth_monitor)
    print("✅ Bandwidth monitoring enabled for ngrok Pro plan")

# Configuration
PORT = int(os.environ.get('PORT', 5002))
API_KEY = (
    os.environ.get('GEMINI_API_KEY')
    or os.environ.get('API_KEY')
    or 'AIzaSyBdH-Gig7TYSJvT8eGpi8dDtGMGtoY1tTE'
)

if not (os.environ.get('GEMINI_API_KEY') or os.environ.get('API_KEY')):
    logger.warning("⚠️ No GEMINI_API_KEY/API_KEY env var found. Using bundled demo key (shared & likely rate-limited).")
else:
    logger.info(f"Using API key: {mask_key(API_KEY)}")

# Configure Gemini AI
genai.configure(api_key=API_KEY)
model = genai.GenerativeModel('gemini-2.5-flash')

# Global state for collaboration
users: Dict[str, dict] = {}
rooms: Dict[str, dict] = {}
user_connections: Dict[str, dict] = {}

# Room persistence - track empty rooms for grace period before deletion
empty_rooms: Dict[str, float] = {}  # room_id -> timestamp when room became empty
ROOM_GRACE_PERIOD = 300  # 5 minutes grace period before deleting empty rooms

# Global state for group messaging
group_rooms: Dict[str, dict] = {}
group_users: Dict[str, dict] = {}
group_connections: Dict[str, dict] = {}
uploaded_files: Dict[str, dict] = {}  # Store file metadata and data

def generate_room_id():
    return ''.join([chr(65 + (int(uuid.uuid4().hex[i], 16) % 26)) for i in range(8)])

def cleanup_empty_rooms():
    """Clean up rooms that have been empty for longer than the grace period"""
    current_time = time.time()
    rooms_to_delete = []

    for room_id, empty_time in empty_rooms.items():
        if current_time - empty_time > ROOM_GRACE_PERIOD:
            rooms_to_delete.append(room_id)

    for room_id in rooms_to_delete:
        if room_id in rooms:
            del rooms[room_id]
            logger.info(f"Room {room_id} deleted after {ROOM_GRACE_PERIOD}s grace period")
        if room_id in group_rooms:
            del group_rooms[room_id]
            logger.info(f"Group room {room_id} deleted after {ROOM_GRACE_PERIOD}s grace period")
        del empty_rooms[room_id]

def start_cleanup_timer():
    """Start a background timer to periodically clean up empty rooms"""
    cleanup_empty_rooms()
    # Schedule next cleanup in 60 seconds
    timer = threading.Timer(60.0, start_cleanup_timer)
    timer.daemon = True
    timer.start()

# Start the cleanup timer
start_cleanup_timer()

# Network connectivity and DNS resolution helpers for mobile hotspot compatibility
def check_internet_connectivity():
    """Check if we can reach Google's servers, with fallback DNS resolution"""
    test_hosts = [
        ('8.8.8.8', 53),  # Google DNS
        ('1.1.1.1', 53),  # Cloudflare DNS
        ('208.67.222.222', 53),  # OpenDNS
    ]

    for host, port in test_hosts:
        try:
            socket.create_connection((host, port), timeout=5)
            return True
        except (socket.timeout, socket.error):
            continue
    return False

def is_online(check_timeout=2):
    """Very fast connectivity probe (works even on hotspot)"""
    for host in [("8.8.8.8", 53), ("1.1.1.1", 53)]:
        try:
            s = socket.create_connection(host, timeout=check_timeout)
            s.close()
            return True
        except OSError:
            continue
    return False

def resolve_google_api_host():
    """Try to resolve Google API hostname with fallback methods"""
    hostname = 'generativelanguage.googleapis.com'

    # Try standard resolution first
    try:
        socket.gethostbyname(hostname)
        return True
    except socket.gaierror:
        pass

    # Try with different DNS servers for mobile hotspots
    dns_servers = ['8.8.8.8', '1.1.1.1', '208.67.222.222']

    for dns in dns_servers:
        try:
            # Use requests with custom DNS (simplified approach)
            response = requests.get(f'https://{hostname}', timeout=10)
            return True
        except:
            continue

    return False

@app.route('/api/network-diagnostic', methods=['GET'])
def network_diagnostic():
    """Diagnostic endpoint to help troubleshoot mobile hotspot connectivity issues"""
    try:
        results = {
            'timestamp': time.time(),
            'internet_connectivity': False,
            'google_api_accessible': False,
            'dns_resolution': False,
            'recommendations': []
        }

        # Test basic internet connectivity
        results['internet_connectivity'] = check_internet_connectivity()
        if not results['internet_connectivity']:
            results['recommendations'].append("No internet connectivity detected. Check your mobile hotspot connection.")

        # Test Google API accessibility
        results['google_api_accessible'] = resolve_google_api_host()
        if not results['google_api_accessible']:
            results['recommendations'].append("Cannot reach Google AI API. Try using a VPN or changing DNS settings.")

        # Test DNS resolution
        try:
            socket.gethostbyname('google.com')
            results['dns_resolution'] = True
        except:
            results['dns_resolution'] = False
            results['recommendations'].append("DNS resolution issues detected. Try changing DNS to 8.8.8.8 or 1.1.1.1")

        # Add mobile hotspot specific recommendations
        if not results['google_api_accessible'] or not results['dns_resolution']:
            results['recommendations'].extend([
                "Mobile hotspot detected issues. Try:",
                "1. Move closer to your phone",
                "2. Restart the mobile hotspot",
                "3. Switch to WiFi if available",
                "4. Use a VPN service",
                "5. Change DNS settings on your device"
            ])

        return jsonify(results)

    except Exception as e:
        return jsonify({
            'error': f'Diagnostic failed: {str(e)}',
            'recommendations': ['Unable to run diagnostics. Check your network connection.']
        }), 500

# Gemini REST API helpers for mobile hotspot compatibility
GEMINI_API_URL_TMPL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

def build_gemini_rest_payload(message: str, base64_image: str = None):
    """Builds a GenerateContentRequest payload for REST API"""
    parts = []
    if message:
        parts.append({"text": message})

    if base64_image:
        # Strip data URL prefix if present
        if base64_image.startswith("data:"):
            base64_image = base64_image.split(",", 1)[-1]

        # Detect mime type from common prefixes or default to PNG
        mime_type = "image/png"
        if "jpeg" in base64_image[:50] or "jpg" in base64_image[:50]:
            mime_type = "image/jpeg"

        parts.append({
            "inline_data": {
                "mime_type": mime_type,
                "data": base64_image
            }
        })

    return {
        "contents": [
            {
                "parts": parts
            }
        ]
    }

def call_gemini_rest(api_key: str, model: str, payload: dict, timeout_sec=300, max_retries=2):
    """Plain REST call to Gemini with simple retries and clear 429 handling"""
    params = {"key": api_key}
    url = GEMINI_API_URL_TMPL.format(model=model)
    last_exc = None
    last_response = None

    for attempt in range(max_retries + 1):
        try:
            logger.info(f"🌐 Calling Gemini REST API (attempt {attempt + 1}/{max_retries + 1})")
            resp = requests.post(
                url,
                params=params,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=timeout_sec,
            )

            last_response = resp

            if resp.status_code == 200:
                logger.info("✅ Gemini REST API call successful")
                return resp.json()

            # Do not hammer on rate limits; surface immediately
            if resp.status_code == 429:
                retry_after = resp.headers.get("Retry-After")
                logger.warning(f"⚠️ Gemini API returned 429 Too Many Requests (Retry-After: {retry_after})")
                raise RateLimitError("Gemini API rate limit reached", retry_after)

            # Retry on transient server/network issues
            if resp.status_code in (500, 502, 503, 504):
                retry_after = resp.headers.get("Retry-After")
                logger.warning(f"⚠️ Gemini API returned {resp.status_code}, retrying... (Retry-After: {retry_after})")

                backoff = 1.5 * (attempt + 1)
                time.sleep(backoff)
                continue

            # Non-retryable error
            logger.error(f"❌ Gemini API error {resp.status_code}: {resp.text}")
            resp.raise_for_status()

        except requests.exceptions.RequestException as e:
            last_exc = e
            logger.warning(f"⚠️ Network error on attempt {attempt + 1}: {e}")
            # Retry common transient errors (timeouts, DNS hiccups)
            if attempt < max_retries:
                time.sleep(1.5 * (attempt + 1))
                continue
            raise

    if last_response and last_response.status_code == 429:
        raise RateLimitError("Gemini API rate limit reached", last_response.headers.get("Retry-After"))

    raise last_exc or RuntimeError("Gemini REST call failed without details")

def extract_text_from_response(data: dict) -> str:
    """Extract text from Gemini REST API response"""
    try:
        candidates = data.get("candidates", [])
        for candidate in candidates:
            content = candidate.get("content", {})
            parts = content.get("parts", [])
            for part in parts:
                if "text" in part:
                    return part["text"]

        # Fallback: try first candidate or stringify
        if candidates:
            return str(candidates[0])
        return "No content returned from Gemini."

    except Exception as e:
        logger.error(f"Error extracting text from response: {e}")
        return "Error parsing Gemini response."

@sock.route('/ws')
def handle_websocket(ws):
    user_id = None
    try:
        logger.info("WebSocket connection opened")
        while True:
            try:
                message = ws.receive()
                data = json.loads(message)
                message_type = data.get('type')

                if message_type == 'register':
                    user_id = str(uuid.uuid4())
                    users[user_id] = {
                        'id': user_id,
                        'name': data.get('name', 'Anonymous'),
                        'room_id': None
                    }
                    user_connections[user_id] = ws

                    ws.send(json.dumps({
                        'type': 'registered',
                        'user_id': user_id,
                        'name': users[user_id]['name']
                    }))
                    logger.info(f"User registered: {users[user_id]['name']} ({user_id})")
                
                elif message_type == 'create_room':
                    if user_id and user_id in users:
                        room_id = generate_room_id()

                        # Get initial canvas state from the request
                        initial_canvas_state = data.get('initial_canvas_state', {
                            'objects': [],
                            'background': '#ffffff'
                        })

                        logger.info(f"Creating room {room_id} with initial canvas state: {len(initial_canvas_state.get('objects', []))} objects")

                        rooms[room_id] = {
                            'id': room_id,
                            'name': data.get('room_name', f'Room {room_id}'),
                            'users': [user_id],
                            'max_users': data.get('max_users', 10),
                            'canvas_state': initial_canvas_state,
                            'host_id': user_id,  # Set the room creator as host
                            'creator_id': user_id,  # Store the original room creator
                            'broadcast_enabled': False,
                            'broadcast_pdf': None
                        }
                        users[user_id]['room_id'] = room_id

                        # Send room created confirmation
                        ws.send(json.dumps({
                            'type': 'room_created',
                            'success': True,
                            'room_id': room_id,
                            'room_name': rooms[room_id]['name']
                        }))

                        # Also send the canvas state back to the creator
                        ws.send(json.dumps({
                            'type': 'canvas_state',
                            'state': rooms[room_id]['canvas_state'],
                            'room': {
                                'id': room_id,
                                'name': rooms[room_id]['name'],
                                'user_count': len(rooms[room_id]['users']),
                                'host_id': rooms[room_id]['host_id'],
                                'broadcast_enabled': rooms[room_id].get('broadcast_enabled', False),
                                'broadcast_pdf': rooms[room_id].get('broadcast_pdf')
                            },
                            'users': [{'id': user_id, 'name': users[user_id]['name']}]
                        }))

                        logger.info(f"Room created: {room_id} by user {user_id} with {len(initial_canvas_state.get('objects', []))} initial objects")
                
                elif message_type == 'join_room':
                    if user_id and user_id in users:
                        room_id = data.get('room_id')
                        was_host = data.get('was_host', False)  # Check if user was previously the host

                        if room_id in rooms:
                            if user_id not in rooms[room_id]['users']:
                                rooms[room_id]['users'].append(user_id)
                            users[user_id]['room_id'] = room_id

                            # Remove room from empty rooms list if it was marked for deletion
                            if room_id in empty_rooms:
                                del empty_rooms[room_id]
                                logger.info(f"Room {room_id} no longer empty - removed from deletion queue")

                            # NEW: Automatic host restoration for original room creator
                            if was_host:
                                current_host_id = rooms[room_id].get('host_id')
                                original_creator_id = rooms[room_id].get('creator_id', rooms[room_id].get('host_id'))  # Fallback to host_id if creator_id not set

                                # Check if this user is the original room creator
                                if user_id == original_creator_id:
                                    # Always restore host to original creator, regardless of current host
                                    if current_host_id != user_id:
                                        old_host_name = users.get(current_host_id, {}).get('name', 'Unknown') if current_host_id else 'Unknown'
                                        new_host_name = users[user_id]['name']

                                        # Transfer host back to original creator
                                        rooms[room_id]['host_id'] = user_id
                                        logger.info(f"Host privileges automatically restored to original creator {user_id} ({new_host_name}) in room {room_id}")

                                        # Broadcast host restoration to all users in the room
                                        for uid in rooms[room_id]['users']:
                                            if uid in user_connections:
                                                try:
                                                    user_connections[uid].send(json.dumps({
                                                        'type': 'host_transferred',
                                                        'new_host_id': user_id,
                                                        'new_host_name': new_host_name,
                                                        'old_host_name': old_host_name,
                                                        'reason': 'original_creator_restoration'
                                                    }))
                                                except Exception as e:
                                                    logger.error(f"Failed to send host restoration notification to user {uid}: {e}")
                                    else:
                                        logger.info(f"Original creator {user_id} rejoined and is already the host in room {room_id}")
                                else:
                                    # Fallback: Old logic for non-creator hosts (if current host doesn't exist)
                                    current_host_exists = current_host_id and current_host_id in users and users[current_host_id].get('room_id') == room_id
                                    if not current_host_exists:
                                        old_host_name = users.get(current_host_id, {}).get('name', 'Unknown') if current_host_id else 'Unknown'
                                        new_host_name = users[user_id]['name']

                                        rooms[room_id]['host_id'] = user_id
                                        logger.info(f"Host privileges restored to {user_id} ({new_host_name}) in room {room_id} (fallback restoration)")

                                        # Broadcast host restoration to all users in the room
                                        for uid in rooms[room_id]['users']:
                                            if uid in user_connections:
                                                try:
                                                    user_connections[uid].send(json.dumps({
                                                        'type': 'host_transferred',
                                                        'new_host_id': user_id,
                                                        'new_host_name': new_host_name,
                                                        'old_host_name': old_host_name,
                                                        'reason': 'auto_rejoin_restoration'
                                                    }))
                                                except Exception as e:
                                                    logger.error(f"Failed to send host restoration notification to user {uid}: {e}")

                            # Send room joined confirmation with canvas state
                            ws.send(json.dumps({
                                'type': 'room_joined',
                                'success': True,
                                'room_id': room_id,
                                'room_name': rooms[room_id]['name'],
                                'host_id': rooms[room_id]['host_id'],  # Include host_id in room_joined response
                                'users': [{'id': uid, 'name': users[uid]['name']} for uid in rooms[room_id]['users'] if uid in users]
                            }))

                            # Send current canvas state to the new user
                            ws.send(json.dumps({
                                'type': 'canvas_state',
                                'state': rooms[room_id]['canvas_state'],
                                'room': {
                                    'id': room_id,
                                    'name': rooms[room_id]['name'],
                                    'user_count': len(rooms[room_id]['users']),
                                    'host_id': rooms[room_id]['host_id'],
                                    'broadcast_enabled': rooms[room_id].get('broadcast_enabled', False),
                                    'broadcast_pdf': rooms[room_id].get('broadcast_pdf')
                                },
                                'users': [{'id': uid, 'name': users[uid]['name']} for uid in rooms[room_id]['users'] if uid in users]
                            }))

                            # Broadcast to other users
                            for other_user_id in rooms[room_id]['users']:
                                if other_user_id != user_id and other_user_id in user_connections:
                                    try:
                                        user_connections[other_user_id].send(json.dumps({
                                            'type': 'user_joined',
                                            'user': {'id': user_id, 'name': users[user_id]['name']}
                                        }))
                                    except:
                                        pass

                            logger.info(f"User {user_id} joined room {room_id}")
                        else:
                            # Room doesn't exist
                            ws.send(json.dumps({
                                'type': 'room_joined',
                                'success': False,
                                'error': 'Room not found'
                            }))
                            logger.warning(f"User {user_id} tried to join non-existent room {room_id}")
                
                elif message_type == 'canvas_event':
                    if user_id and user_id in users and users[user_id]['room_id']:
                        room_id = users[user_id]['room_id']
                        if room_id in rooms:
                            event_data = data.get('event', {})
                            event_type = event_data.get('type')

                            # Update canvas state based on event type
                            room = rooms[room_id]
                            canvas_state = room['canvas_state']

                            logger.info(f"Canvas event: {event_type} from user {user_id} in room {room_id}")

                            # Handle different canvas operations
                            if event_type in ['object_added', 'path_created']:
                                obj_data = event_data.get('object') or event_data.get('path')
                                if obj_data:
                                    canvas_state['objects'].append(obj_data)
                                    logger.info(f"Added object to canvas state. Total objects: {len(canvas_state['objects'])}")

                            elif event_type == 'object_modified':
                                obj_id = event_data.get('object_id')
                                obj_data = event_data.get('object')
                                if obj_id and obj_data:
                                    # Find and update the object
                                    for i, obj in enumerate(canvas_state['objects']):
                                        if obj.get('id') == obj_id:
                                            canvas_state['objects'][i] = obj_data
                                            logger.info(f"Modified object {obj_id} in canvas state")
                                            break

                            elif event_type == 'object_removed':
                                obj_id = event_data.get('object_id')
                                if obj_id:
                                    initial_count = len(canvas_state['objects'])
                                    canvas_state['objects'] = [
                                        obj for obj in canvas_state['objects']
                                        if obj.get('id') != obj_id
                                    ]
                                    final_count = len(canvas_state['objects'])
                                    logger.info(f"Removed object {obj_id}. Objects: {initial_count} -> {final_count}")

                            elif event_type == 'canvas_cleared':
                                canvas_state['objects'] = []
                                if 'background' in event_data:
                                    canvas_state['background'] = event_data['background']
                                logger.info("Canvas cleared and state updated")

                            elif event_type == 'background_changed':
                                canvas_state['background'] = event_data.get('background', '#ffffff')
                                # Store pattern data if it's a CSS pattern
                                if event_data.get('background') == 'css_pattern' and event_data.get('pattern'):
                                    canvas_state['pattern'] = event_data.get('pattern')
                                    logger.info(f"Stored CSS pattern: {event_data.get('pattern', {}).get('type', 'unknown')}")
                                elif event_data.get('background') != 'css_pattern':
                                    # Clear pattern data for solid backgrounds
                                    canvas_state.pop('pattern', None)
                                logger.info(f"Background changed to: {canvas_state['background']}")

                            # Broadcast to other users in the room
                            for other_user_id in rooms[room_id]['users']:
                                if other_user_id != user_id and other_user_id in user_connections:
                                    try:
                                        user_connections[other_user_id].send(json.dumps({
                                            'type': 'canvas_event',
                                            'event': event_data,
                                            'user_id': user_id
                                        }))
                                    except:
                                        pass

                elif message_type == 'cursor_move':
                    if user_id and user_id in users and users[user_id]['room_id']:
                        room_id = users[user_id]['room_id']
                        if room_id in rooms:
                            logger.info(f"Cursor move from user {user_id}: x={data.get('x')}, y={data.get('y')}")
                            # Broadcast cursor position to other users in the room
                            for other_user_id in rooms[room_id]['users']:
                                if other_user_id != user_id and other_user_id in user_connections:
                                    try:
                                        user_connections[other_user_id].send(json.dumps({
                                            'type': 'cursor_move',
                                            'user_id': user_id,
                                            'x': data.get('x'),
                                            'y': data.get('y')
                                        }))
                                        logger.info(f"Sent cursor position to user {other_user_id}")
                                    except Exception as e:
                                        logger.error(f"Failed to send cursor to user {other_user_id}: {e}")
                    else:
                        logger.warning(f"Cursor move ignored - user_id: {user_id}, in_users: {user_id in users if user_id else False}, room_id: {users.get(user_id, {}).get('room_id') if user_id else None}")

                elif message_type == 'update_name':
                    if user_id and user_id in users:
                        new_name = data.get('name', 'Anonymous')
                        old_name = users[user_id]['name']
                        users[user_id]['name'] = new_name

                        # Broadcast name update to room members
                        room_id = users[user_id].get('room_id')
                        if room_id and room_id in rooms:
                            for other_user_id in rooms[room_id]['users']:
                                if other_user_id != user_id and other_user_id in user_connections:
                                    try:
                                        user_connections[other_user_id].send(json.dumps({
                                            'type': 'user_name_updated',
                                            'user_id': user_id,
                                            'old_name': old_name,
                                            'new_name': new_name
                                        }))
                                    except Exception as e:
                                        logger.error(f"Failed to send name update to user {other_user_id}: {e}")

                        logger.info(f"User {user_id} updated name from '{old_name}' to '{new_name}'")

                elif message_type == 'leave_room':
                    if user_id and user_id in users:
                        room_id = users[user_id].get('room_id')
                        if room_id and room_id in rooms:
                            # Remove user from room
                            if user_id in rooms[room_id]['users']:
                                rooms[room_id]['users'].remove(user_id)

                            if rooms[room_id].get('host_id') == user_id:
                                rooms[room_id]['broadcast_enabled'] = False
                                rooms[room_id]['broadcast_pdf'] = None
                                broadcast_payload = {
                                    'type': 'host_broadcast_state',
                                    'enabled': False,
                                    'host_id': user_id
                                }
                                for uid in rooms[room_id]['users']:
                                    if uid in user_connections:
                                        try:
                                            user_connections[uid].send(json.dumps(broadcast_payload))
                                        except Exception as e:
                                            logger.error(f"Failed to send broadcast reset to user {uid}: {e}")

                            # Broadcast user left to other room members
                            for other_user_id in rooms[room_id]['users']:
                                if other_user_id in user_connections:
                                    try:
                                        user_connections[other_user_id].send(json.dumps({
                                            'type': 'user_left',
                                            'user_id': user_id,
                                            'user_name': users[user_id]['name']
                                        }))
                                    except Exception as e:
                                        logger.error(f"Failed to send user left to user {other_user_id}: {e}")

                            # Mark room as empty for grace period instead of immediate deletion
                            if not rooms[room_id]['users']:
                                empty_rooms[room_id] = time.time()
                                logger.info(f"Room {room_id} marked as empty - will be deleted after {ROOM_GRACE_PERIOD}s grace period")

                            # Clear user's room
                            users[user_id]['room_id'] = None

                            # Send confirmation to leaving user
                            ws.send(json.dumps({
                                'type': 'room_left',
                                'success': True
                            }))

                            logger.info(f"User {user_id} left room {room_id}")

                elif message_type == 'kick_user':
                    if user_id and user_id in users:
                        target_user_id = data.get('target_user_id')
                        if target_user_id and target_user_id in users:
                            room_id = users[user_id].get('room_id')
                            if room_id and room_id in rooms:
                                # Check if the requesting user is the host
                                if rooms[room_id].get('host_id') != user_id:
                                    ws.send(json.dumps({
                                        'type': 'kick_result',
                                        'success': False,
                                        'target_user_id': target_user_id
                                    }))
                                    logger.warning(f"User {user_id} attempted to kick {target_user_id} but is not the host of room {room_id}")
                                    continue

                                # Check if target user is in the same room
                                if users[target_user_id].get('room_id') != room_id:
                                    ws.send(json.dumps({
                                        'type': 'kick_result',
                                        'success': False,
                                        'target_user_id': target_user_id
                                    }))
                                    continue

                                # Cannot kick the host (themselves)
                                if target_user_id == user_id:
                                    ws.send(json.dumps({
                                        'type': 'kick_result',
                                        'success': False,
                                        'target_user_id': target_user_id
                                    }))
                                    continue

                                # Notify the kicked user
                                if target_user_id in user_connections:
                                    try:
                                        user_connections[target_user_id].send(json.dumps({
                                            'type': 'kicked',
                                            'room_id': room_id,
                                            'kicked_by': users[user_id]['name']
                                        }))
                                    except Exception as e:
                                        logger.error(f"Failed to notify kicked user {target_user_id}: {e}")

                                # Remove user from collaboration room
                                if target_user_id in rooms[room_id]['users']:
                                    rooms[room_id]['users'].remove(target_user_id)
                                users[target_user_id]['room_id'] = None

                                # Force disconnect from group messaging
                                if target_user_id in group_users:
                                    group_user_room = group_users[target_user_id].get('room_id')
                                    if group_user_room and group_user_room in group_rooms:
                                        # Remove from group room
                                        if target_user_id in group_rooms[group_user_room]['users']:
                                            group_rooms[group_user_room]['users'].remove(target_user_id)

                                        # Don't send redundant leave message - kick message is sent later

                                    # Close group messaging WebSocket connection
                                    if target_user_id in group_connections:
                                        try:
                                            group_connections[target_user_id].close()
                                            logger.info(f"Closed group messaging connection for kicked user {target_user_id}")
                                        except Exception as e:
                                            logger.error(f"Failed to close group connection for {target_user_id}: {e}")

                                    # Clean up group user data
                                    group_users[target_user_id]['room_id'] = None

                                # Force disconnect from video call
                                # Send video call events to all other users in the room
                                for other_user_id in rooms[room_id]['users']:
                                    if other_user_id in user_connections:
                                        try:
                                            # Notify about video call disconnection
                                            user_connections[other_user_id].send(json.dumps({
                                                'type': 'video_call_ended',
                                                'user_id': target_user_id,
                                                'reason': 'kicked'
                                            }))

                                            # Also send participant_left event for video call cleanup
                                            user_connections[other_user_id].send(json.dumps({
                                                'type': 'video_call_event',
                                                'event_type': 'participant_left',
                                                'data': {'userId': target_user_id, 'reason': 'kicked'},
                                                'user_id': target_user_id,
                                                'room_id': room_id,
                                                'timestamp': time.time()
                                            }))
                                        except Exception as e:
                                            logger.error(f"Failed to send video call events to user {other_user_id}: {e}")

                                # Notify other users in the room about the kick
                                for other_user_id in rooms[room_id]['users']:
                                    if other_user_id in user_connections:
                                        try:
                                            user_connections[other_user_id].send(json.dumps({
                                                'type': 'user_kicked',
                                                'user_id': target_user_id,
                                                'user_name': users[target_user_id]['name'],
                                                'kicked_by': users[user_id]['name']
                                            }))
                                        except Exception as e:
                                            logger.error(f"Failed to notify user {other_user_id} about kick: {e}")

                                # Send kick message to group chat - find the group room based on collaboration room
                                # Look for group users who are in the same collaboration room
                                group_room_id = room_id  # Group rooms use same ID as collaboration rooms
                                logger.info(f"Attempting to send kick message to group room {group_room_id}")
                                logger.info(f"Available group rooms: {list(group_rooms.keys())}")

                                if group_room_id in group_rooms:
                                    kick_message = {
                                        'id': str(uuid.uuid4()),
                                        'type': 'system',
                                        'content': f"{users[target_user_id]['name']} was kicked from the room by {users[user_id]['name']}",
                                        'timestamp': datetime.now().isoformat(),
                                        'room_id': group_room_id
                                    }
                                    group_rooms[group_room_id]['messages'].append(kick_message)

                                    # Remove kicked user from group chat if they're in it
                                    if target_user_id in group_users and group_users[target_user_id].get('room_id') == group_room_id:
                                        if target_user_id in group_rooms[group_room_id]['users']:
                                            group_rooms[group_room_id]['users'].remove(target_user_id)
                                        group_users[target_user_id]['room_id'] = None
                                        logger.info(f"Removed kicked user {target_user_id} from group chat")

                                    # Broadcast kick message to all remaining users in group chat
                                    users_notified = 0
                                    for group_user_id in group_rooms[group_room_id]['users']:
                                        if group_user_id in group_connections:
                                            try:
                                                group_connections[group_user_id].send(json.dumps({
                                                    'type': 'message',
                                                    'data': kick_message
                                                }))
                                                users_notified += 1
                                            except Exception as e:
                                                logger.error(f"Failed to send kick message to group user {group_user_id}: {e}")

                                    logger.info(f"Kick message sent to {users_notified} users in group chat room {group_room_id}")
                                else:
                                    logger.warning(f"Group room {group_room_id} not found for kick message broadcast")

                                # Complete session cleanup - schedule connection closure
                                def close_connections():
                                    import threading
                                    import time

                                    def delayed_close():
                                        time.sleep(0.5)  # Give time for messages to be sent

                                        # Close group messaging connection
                                        if target_user_id in group_connections:
                                            try:
                                                group_connections[target_user_id].close()
                                                logger.info(f"Closed group messaging connection for kicked user {target_user_id}")
                                            except Exception as e:
                                                logger.error(f"Failed to close group connection for {target_user_id}: {e}")

                                        # Close main collaboration WebSocket
                                        if target_user_id in user_connections:
                                            try:
                                                user_connections[target_user_id].close()
                                                logger.info(f"Closed main WebSocket connection for kicked user {target_user_id}")
                                            except Exception as e:
                                                logger.error(f"Failed to close main connection for {target_user_id}: {e}")

                                    thread = threading.Thread(target=delayed_close)
                                    thread.daemon = True
                                    thread.start()

                                close_connections()

                                # Send success response to host
                                ws.send(json.dumps({
                                    'type': 'kick_result',
                                    'success': True,
                                    'target_user_id': target_user_id
                                }))

                                logger.info(f"User {target_user_id} ({users[target_user_id]['name']}) was kicked from room {room_id} by host {user_id} ({users[user_id]['name']}) - FULLY DISCONNECTED")

                elif message_type == 'host_mute_user':
                    if user_id and user_id in users:
                        target_user_id = data.get('target_user_id')
                        mute_type = data.get('mute_type')  # 'video' or 'audio'
                        action = data.get('action', 'mute')  # 'mute' or 'unmute'
                        room_id = users[user_id].get('room_id')

                        if not target_user_id or not mute_type or not room_id or room_id not in rooms:
                            ws.send(json.dumps({
                                'type': 'error',
                                'message': 'Invalid mute request'
                            }))
                            continue

                        # Check if user is the host
                        if rooms[room_id].get('host_id') != user_id:
                            ws.send(json.dumps({
                                'type': 'error',
                                'message': 'Only the host can mute users'
                            }))
                            continue

                        # Check if target user exists and is in the room
                        if target_user_id not in users or users[target_user_id].get('room_id') != room_id:
                            ws.send(json.dumps({
                                'type': 'error',
                                'message': 'Target user not found in room'
                            }))
                            continue

                        # Cannot mute yourself
                        if target_user_id == user_id:
                            ws.send(json.dumps({
                                'type': 'error',
                                'message': 'Cannot mute yourself'
                            }))
                            continue

                        logger.info(f"Host {user_id} ({users[user_id]['name']}) is {action}ing {mute_type} for user {target_user_id} ({users[target_user_id]['name']}) in room {room_id}")

                        # Send mute command to target user
                        if target_user_id in user_connections:
                            try:
                                user_connections[target_user_id].send(json.dumps({
                                    'type': 'host_mute_command',
                                    'mute_type': mute_type,
                                    'action': action,
                                    'host_name': users[user_id]['name']
                                }))
                                logger.info(f"Sent {action} {mute_type} command to user {target_user_id}")
                            except Exception as e:
                                logger.error(f"Failed to send mute command to user {target_user_id}: {e}")

                        # Send confirmation to host
                        ws.send(json.dumps({
                            'type': 'host_mute_result',
                            'success': True,
                            'target_user_id': target_user_id,
                            'mute_type': mute_type,
                            'action': action
                        }))

                elif message_type == 'video_call_started':
                    if user_id and user_id in users:
                        room_id = users[user_id].get('room_id')
                        if room_id and room_id in rooms:
                            user_name = data.get('user_name', users[user_id]['name'])

                            # Broadcast video call start to other room members
                            for other_user_id in rooms[room_id]['users']:
                                if other_user_id != user_id and other_user_id in user_connections:
                                    try:
                                        user_connections[other_user_id].send(json.dumps({
                                            'type': 'video_call_started',
                                            'user_id': user_id,
                                            'user_name': user_name
                                        }))
                                    except Exception as e:
                                        logger.error(f"Failed to send video call start to user {other_user_id}: {e}")

                            logger.info(f"User {user_id} started video call in room {room_id}")

                elif message_type == 'video_call_ended':
                    if user_id and user_id in users:
                        room_id = users[user_id].get('room_id')
                        if room_id and room_id in rooms:
                            # Broadcast video call end to other room members
                            for other_user_id in rooms[room_id]['users']:
                                if other_user_id != user_id and other_user_id in user_connections:
                                    try:
                                        user_connections[other_user_id].send(json.dumps({
                                            'type': 'video_call_ended',
                                            'user_id': user_id
                                        }))
                                    except Exception as e:
                                        logger.error(f"Failed to send video call end to user {other_user_id}: {e}")

                            logger.info(f"User {user_id} ended video call in room {room_id}")

                elif message_type == 'media_status':
                    if user_id and user_id in users:
                        room_id = users[user_id].get('room_id')
                        if room_id and room_id in rooms:
                            video_enabled = data.get('video_enabled', False)
                            audio_enabled = data.get('audio_enabled', False)

                            # Broadcast media status to other room members
                            for other_user_id in rooms[room_id]['users']:
                                if other_user_id != user_id and other_user_id in user_connections:
                                    try:
                                        user_connections[other_user_id].send(json.dumps({
                                            'type': 'media_status',
                                            'user_id': user_id,
                                            'video_enabled': video_enabled,
                                            'audio_enabled': audio_enabled
                                        }))
                                    except Exception as e:
                                        logger.error(f"Failed to send media status to user {other_user_id}: {e}")

                            logger.info(f"User {user_id} updated media status - video: {video_enabled}, audio: {audio_enabled}")

                elif message_type == 'host_broadcast_control':
                    if user_id and user_id in users:
                        room_id = users[user_id].get('room_id')
                        if room_id and room_id in rooms and rooms[room_id]['host_id'] == user_id:
                            enabled = bool(data.get('enabled'))
                            rooms[room_id]['broadcast_enabled'] = enabled
                            if not enabled:
                                rooms[room_id]['broadcast_pdf'] = None
                            broadcast_payload = {
                                'type': 'host_broadcast_state',
                                'enabled': enabled,
                                'host_id': user_id,
                                'pdf': rooms[room_id].get('broadcast_pdf')
                            }
                            for uid in rooms[room_id]['users']:
                                if uid in user_connections:
                                    try:
                                        user_connections[uid].send(json.dumps(broadcast_payload))
                                    except Exception as e:
                                        logger.error(f"Failed to send broadcast state to user {uid}: {e}")

                elif message_type == 'host_broadcast_ai_message':
                    if user_id and user_id in users:
                        room_id = users[user_id].get('room_id')
                        message_payload = data.get('message')
                        if (room_id and room_id in rooms and rooms[room_id]['host_id'] == user_id and
                                rooms[room_id].get('broadcast_enabled') and message_payload):
                            for uid in rooms[room_id]['users']:
                                if uid != user_id and uid in user_connections:
                                    try:
                                        user_connections[uid].send(json.dumps({
                                            'type': 'host_broadcast_ai_message',
                                            'host_id': user_id,
                                            'message': message_payload
                                        }))
                                    except Exception as e:
                                        logger.error(f"Failed to send broadcast chat to user {uid}: {e}")

                elif message_type == 'host_broadcast_pdf':
                    if user_id and user_id in users:
                        room_id = users[user_id].get('room_id')
                        payload = data.get('data', {})
                        if (room_id and room_id in rooms and rooms[room_id]['host_id'] == user_id and
                                rooms[room_id].get('broadcast_enabled')):
                            action = payload.get('action')
                            pdf_data = payload.get('data', {})
                            if action == 'load':
                                rooms[room_id]['broadcast_pdf'] = pdf_data
                            elif action == 'page_change' and rooms[room_id].get('broadcast_pdf'):
                                rooms[room_id]['broadcast_pdf']['current_page'] = pdf_data.get('current_page')
                                rooms[room_id]['broadcast_pdf']['timestamp'] = pdf_data.get('timestamp')
                            elif action == 'close':
                                rooms[room_id]['broadcast_pdf'] = None

                            event_payload = {
                                'type': 'host_broadcast_pdf',
                                'host_id': user_id,
                                'action': action,
                                'data': pdf_data
                            }

                            for uid in rooms[room_id]['users']:
                                if uid != user_id and uid in user_connections:
                                    try:
                                        user_connections[uid].send(json.dumps(event_payload))
                                    except Exception as e:
                                        logger.error(f"Failed to send broadcast PDF event to user {uid}: {e}")

                elif message_type == 'video_call_event':
                    if user_id and user_id in users:
                        room_id = users[user_id].get('room_id')
                        if room_id and room_id in rooms:
                            event_type = data.get('event_type')
                            event_data = data.get('data', {})

                            # Broadcast video call event to other room members
                            for other_user_id in rooms[room_id]['users']:
                                if other_user_id != user_id and other_user_id in user_connections:
                                    try:
                                        user_connections[other_user_id].send(json.dumps({
                                            'type': 'video_call_event',
                                            'event_type': event_type,
                                            'data': event_data,
                                            'user_id': user_id,
                                            'room_id': room_id,
                                            'timestamp': time.time()
                                        }))
                                    except Exception as e:
                                        logger.error(f"Failed to send video call event to user {other_user_id}: {e}")

                            logger.info(f"Video call event '{event_type}' from user {user_id} in room {room_id}")

                elif message_type == 'webrtc_signal':
                    if user_id and user_id in users:
                        room_id = users[user_id].get('room_id')
                        to_user_id = data.get('toUserId')
                        from_user_id = data.get('fromUserId')
                        signal_type = data.get('signalType')
                        signal_data = data.get('signalData')

                        logger.info(f"WebRTC signal '{signal_type}' from {from_user_id} to {to_user_id} in room {room_id}")

                        if room_id and room_id in rooms and to_user_id and to_user_id in user_connections:
                            # Verify both users are in the same room
                            if to_user_id in users and users[to_user_id].get('room_id') == room_id:
                                try:
                                    # Forward WebRTC signaling message to target user
                                    signal_message = {
                                        'type': 'webrtc_signal',
                                        'fromUserId': from_user_id,
                                        'signalType': signal_type,
                                        'signalData': signal_data
                                    }
                                    user_connections[to_user_id].send(json.dumps(signal_message))
                                    logger.info(f"WebRTC signal '{signal_type}' successfully forwarded from {from_user_id} to {to_user_id}")
                                except Exception as e:
                                    logger.error(f"Failed to forward WebRTC signal to user {to_user_id}: {e}")
                            else:
                                logger.warning(f"Target user {to_user_id} not in same room {room_id} for WebRTC signal")
                        else:
                            logger.warning(f"Cannot forward WebRTC signal - missing room/user: room_id={room_id}, to_user_id={to_user_id}, user_exists={to_user_id in user_connections if to_user_id else False}")

                elif message_type == 'transfer_host':
                    if user_id and user_id in users:
                        target_user_id = data.get('target_user_id')
                        room_id = users[user_id].get('room_id')

                        if not target_user_id or target_user_id not in users:
                            ws.send(json.dumps({
                                'type': 'transfer_host_result',
                                'success': False,
                                'message': 'Target user not found'
                            }))
                            continue

                        if not room_id or room_id not in rooms:
                            ws.send(json.dumps({
                                'type': 'transfer_host_result',
                                'success': False,
                                'message': 'Room not found'
                            }))
                            continue

                        # Check if user is the current host
                        if rooms[room_id].get('host_id') != user_id:
                            ws.send(json.dumps({
                                'type': 'transfer_host_result',
                                'success': False,
                                'message': 'Only the host can transfer host privileges'
                            }))
                            continue

                        # Check if target user is in the same room
                        if users[target_user_id].get('room_id') != room_id:
                            ws.send(json.dumps({
                                'type': 'transfer_host_result',
                                'success': False,
                                'message': 'Target user is not in the same room'
                            }))
                            continue

                        # Check if target user is not the current host
                        if target_user_id == user_id:
                            ws.send(json.dumps({
                                'type': 'transfer_host_result',
                                'success': False,
                                'message': 'You are already the host'
                            }))
                            continue

                        # Transfer host privileges
                        old_host_name = users[user_id]['name']
                        new_host_name = users[target_user_id]['name']

                        # Update room host
                        rooms[room_id]['host_id'] = target_user_id

                        logger.info(f"Host transferred in room {room_id} from {user_id} ({old_host_name}) to {target_user_id} ({new_host_name})")

                        # Send confirmation to the old host
                        ws.send(json.dumps({
                            'type': 'transfer_host_result',
                            'success': True,
                            'new_host_name': new_host_name
                        }))

                        # Broadcast host transfer to all users in the room
                        for uid in rooms[room_id]['users']:
                            if uid in user_connections:
                                try:
                                    user_connections[uid].send(json.dumps({
                                        'type': 'host_transferred',
                                        'new_host_id': target_user_id,
                                        'new_host_name': new_host_name,
                                        'old_host_name': old_host_name
                                    }))
                                except Exception as e:
                                    logger.error(f"Failed to send host transfer notification to user {uid}: {e}")

                        rooms[room_id]['broadcast_enabled'] = False
                        rooms[room_id]['broadcast_pdf'] = None
                        broadcast_payload = {
                            'type': 'host_broadcast_state',
                            'enabled': False,
                            'host_id': target_user_id
                        }
                        for uid in rooms[room_id]['users']:
                            if uid in user_connections:
                                try:
                                    user_connections[uid].send(json.dumps(broadcast_payload))
                                except Exception as e:
                                    logger.error(f"Failed to send broadcast reset after host transfer to user {uid}: {e}")

            except json.JSONDecodeError:
                logger.error("Invalid JSON received")
            except Exception as e:
                logger.error(f"Error handling message: {e}")
                break

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
                        empty_rooms[room_id] = time.time()
                        logger.info(f"Room {room_id} marked as empty - will be deleted after {ROOM_GRACE_PERIOD}s grace period")
                del users[user_id]
            logger.info(f"User unregistered: {user_id}")

# Group Messaging WebSocket Handler
@sock.route('/group-ws')
def handle_group_websocket(ws):
    user_id = None
    try:
        logger.info("Group messaging WebSocket connection opened")
        while True:
            try:
                message = ws.receive()
                data = json.loads(message)
                message_type = data.get('type')

                if message_type == 'register':
                    user_id = str(uuid.uuid4())
                    display_name = data.get('display_name', 'Anonymous')

                    group_users[user_id] = {
                        'id': user_id,
                        'display_name': display_name,
                        'room_id': None,
                        'connected_at': datetime.now().isoformat()
                    }
                    group_connections[user_id] = ws

                    ws.send(json.dumps({
                        'type': 'registered',
                        'user_id': user_id,
                        'display_name': display_name
                    }))
                    logger.info(f"Group user registered: {display_name} ({user_id})")

                elif message_type == 'join_room':
                    if user_id and user_id in group_users:
                        room_id = data.get('room_id', '').upper()

                        if not room_id:
                            ws.send(json.dumps({
                                'type': 'error',
                                'message': 'Room ID is required'
                            }))
                            continue

                        # Create room if it doesn't exist
                        if room_id not in group_rooms:
                            group_rooms[room_id] = {
                                'id': room_id,
                                'users': [],
                                'messages': []
                            }

                        # Leave current room if in one
                        current_room = group_users[user_id].get('room_id')
                        if current_room and current_room in group_rooms:
                            if user_id in group_rooms[current_room]['users']:
                                group_rooms[current_room]['users'].remove(user_id)

                        # Join new room
                        group_rooms[room_id]['users'].append(user_id)
                        group_users[user_id]['room_id'] = room_id

                        # Remove room from empty rooms list if it was marked for deletion
                        if room_id in empty_rooms:
                            del empty_rooms[room_id]
                            logger.info(f"Group room {room_id} no longer empty - removed from deletion queue")

                        # Send confirmation to user
                        ws.send(json.dumps({
                            'type': 'room_joined',
                            'room_id': room_id,
                            'success': True
                        }))

                        # Send recent messages to new user (including deleted messages for context)
                        recent_messages = group_rooms[room_id]['messages'][-50:]  # Last 50 messages
                        for msg in recent_messages:
                            ws.send(json.dumps({
                                'type': 'message',
                                'data': msg
                            }))

                        # Notify other users in room
                        user_name = group_users[user_id]['display_name']
                        join_message = {
                            'id': str(uuid.uuid4()),
                            'type': 'system',
                            'content': f"{user_name} joined the room",
                            'timestamp': datetime.now().isoformat(),
                            'room_id': room_id
                        }
                        group_rooms[room_id]['messages'].append(join_message)

                        for other_user_id in group_rooms[room_id]['users']:
                            if other_user_id != user_id and other_user_id in group_connections:
                                try:
                                    group_connections[other_user_id].send(json.dumps({
                                        'type': 'message',
                                        'data': join_message
                                    }))
                                except Exception as e:
                                    logger.error(f"Failed to send join message to user {other_user_id}: {e}")

                        logger.info(f"User {user_name} joined room {room_id}")

                elif message_type == 'send_message':
                    if user_id and user_id in group_users:
                        room_id = group_users[user_id].get('room_id')
                        if not room_id or room_id not in group_rooms:
                            ws.send(json.dumps({
                                'type': 'error',
                                'message': 'Not in a room'
                            }))
                            continue

                        content = data.get('content', '').strip()
                        if not content:
                            continue

                        message_data = {
                            'id': str(uuid.uuid4()),
                            'type': 'user',
                            'content': content,
                            'sender_id': user_id,
                            'sender_name': group_users[user_id]['display_name'],
                            'timestamp': datetime.now().isoformat(),
                            'room_id': room_id
                        }

                        # Add reply data if present
                        reply_to = data.get('replyTo')
                        if reply_to:
                            message_data['replyTo'] = reply_to

                        # Store message
                        group_rooms[room_id]['messages'].append(message_data)

                        # Broadcast to all users in room
                        for room_user_id in group_rooms[room_id]['users']:
                            if room_user_id in group_connections:
                                try:
                                    group_connections[room_user_id].send(json.dumps({
                                        'type': 'message',
                                        'data': message_data
                                    }))
                                except Exception as e:
                                    logger.error(f"Failed to send message to user {room_user_id}: {e}")

                        logger.info(f"Message sent in room {room_id} by {group_users[user_id]['display_name']}")

                elif message_type == 'upload_file':
                    if user_id and user_id in group_users:
                        room_id = group_users[user_id].get('room_id')
                        if not room_id or room_id not in group_rooms:
                            ws.send(json.dumps({
                                'type': 'error',
                                'message': 'Not in a room'
                            }))
                            continue

                        file_data = data.get('file_data')
                        file_name = data.get('file_name')
                        file_type = data.get('file_type', 'application/octet-stream')

                        if not file_data or not file_name:
                            ws.send(json.dumps({
                                'type': 'error',
                                'message': 'File data and name are required'
                            }))
                            continue

                        file_id = str(uuid.uuid4())
                        uploaded_files[file_id] = {
                            'id': file_id,
                            'name': file_name,
                            'type': file_type,
                            'data': file_data,
                            'uploaded_by': user_id,
                            'uploaded_at': datetime.now().isoformat(),
                            'room_id': room_id
                        }

                        file_message = {
                            'id': str(uuid.uuid4()),
                            'type': 'file',
                            'content': f"📎 {file_name}",
                            'file_id': file_id,
                            'file_name': file_name,
                            'file_type': file_type,
                            'sender_id': user_id,
                            'sender_name': group_users[user_id]['display_name'],
                            'timestamp': datetime.now().isoformat(),
                            'room_id': room_id
                        }

                        # Store message
                        group_rooms[room_id]['messages'].append(file_message)

                        # Broadcast to all users in room
                        for room_user_id in group_rooms[room_id]['users']:
                            if room_user_id in group_connections:
                                try:
                                    group_connections[room_user_id].send(json.dumps({
                                        'type': 'message',
                                        'data': file_message
                                    }))
                                except Exception as e:
                                    logger.error(f"Failed to send file message to user {room_user_id}: {e}")

                        logger.info(f"File {file_name} uploaded in room {room_id} by {group_users[user_id]['display_name']}")

                elif message_type == 'edit_message':
                    if user_id and user_id in group_users:
                        room_id = group_users[user_id].get('room_id')
                        if not room_id or room_id not in group_rooms:
                            ws.send(json.dumps({
                                'type': 'error',
                                'message': 'Not in a room'
                            }))
                            continue

                        message_id = data.get('message_id')
                        new_content = data.get('new_content', '').strip()

                        if not message_id or not new_content:
                            ws.send(json.dumps({
                                'type': 'error',
                                'message': 'Invalid edit request'
                            }))
                            continue

                        # Find and update the message (with authorization check)
                        message_found = False
                        for i, msg in enumerate(group_rooms[room_id]['messages']):
                            if msg.get('id') == message_id:
                                # Authorization check: Only message sender can edit
                                if msg.get('sender_id') != user_id:
                                    logger.warning(f"Unauthorized edit attempt: User {user_id} tried to edit message {message_id} by {msg.get('sender_id')}")
                                    ws.send(json.dumps({
                                        'type': 'error',
                                        'message': 'Not authorized to edit this message'
                                    }))
                                    break

                                # Authorized edit
                                # Update the message content
                                group_rooms[room_id]['messages'][i]['content'] = new_content
                                group_rooms[room_id]['messages'][i]['edited'] = True
                                group_rooms[room_id]['messages'][i]['edited_at'] = datetime.now().isoformat()

                                # Broadcast edit to all users in room
                                edit_data = {
                                    'message_id': message_id,
                                    'new_content': new_content,
                                    'sender_name': group_users[user_id]['display_name'],
                                    'edited_at': group_rooms[room_id]['messages'][i]['edited_at']
                                }

                                for room_user_id in group_rooms[room_id]['users']:
                                    if room_user_id in group_connections:
                                        try:
                                            group_connections[room_user_id].send(json.dumps({
                                                'type': 'message_edited',
                                                **edit_data
                                            }))
                                        except Exception as e:
                                            logger.error(f"Failed to send edit notification to user {room_user_id}: {e}")

                                message_found = True
                                logger.info(f"Message {message_id} edited by {group_users[user_id]['display_name']}")
                                break

                        if not message_found:
                            ws.send(json.dumps({
                                'type': 'error',
                                'message': 'Message not found or not authorized to edit'
                            }))

                elif message_type == 'delete_message':
                    if user_id and user_id in group_users:
                        room_id = group_users[user_id].get('room_id')
                        if not room_id or room_id not in group_rooms:
                            ws.send(json.dumps({
                                'type': 'error',
                                'message': 'Not in a room'
                            }))
                            continue

                        message_id = data.get('message_id')

                        if not message_id:
                            ws.send(json.dumps({
                                'type': 'error',
                                'message': 'Invalid delete request'
                            }))
                            continue

                        # Find and mark message as deleted (with authorization check)
                        message_found = False
                        for i, msg in enumerate(group_rooms[room_id]['messages']):
                            if msg.get('id') == message_id:
                                # Authorization check: Only message sender can delete
                                if msg.get('sender_id') != user_id:
                                    logger.warning(f"Unauthorized delete attempt: User {user_id} tried to delete message {message_id} by {msg.get('sender_id')}")
                                    ws.send(json.dumps({
                                        'type': 'error',
                                        'message': 'Not authorized to delete this message'
                                    }))
                                    break

                                # Authorized deletion
                                # Mark message as deleted
                                group_rooms[room_id]['messages'][i]['deleted'] = True
                                group_rooms[room_id]['messages'][i]['deleted_at'] = datetime.now().isoformat()

                                # Broadcast deletion to all users in room
                                delete_data = {
                                    'message_id': message_id,
                                    'sender_name': group_users[user_id]['display_name'],
                                    'deleted_at': group_rooms[room_id]['messages'][i]['deleted_at']
                                }

                                for room_user_id in group_rooms[room_id]['users']:
                                    if room_user_id in group_connections:
                                        try:
                                            group_connections[room_user_id].send(json.dumps({
                                                'type': 'message_deleted',
                                                **delete_data
                                            }))
                                        except Exception as e:
                                            logger.error(f"Failed to send delete notification to user {room_user_id}: {e}")

                                message_found = True
                                logger.info(f"Message {message_id} deleted by {group_users[user_id]['display_name']}")
                                break

                        if not message_found:
                            ws.send(json.dumps({
                                'type': 'error',
                                'message': 'Message not found or not authorized to delete'
                            }))

                elif message_type == 'leave_room':
                    if user_id and user_id in group_users:
                        room_id = group_users[user_id].get('room_id')
                        if room_id and room_id in group_rooms:
                            # Remove user from room
                            if user_id in group_rooms[room_id]['users']:
                                group_rooms[room_id]['users'].remove(user_id)

                            user_name = group_users[user_id]['display_name']
                            group_users[user_id]['room_id'] = None

                            # Send confirmation
                            ws.send(json.dumps({
                                'type': 'room_left',
                                'success': True
                            }))

                            # Notify other users
                            leave_message = {
                                'id': str(uuid.uuid4()),
                                'type': 'system',
                                'content': f"{user_name} left the room",
                                'timestamp': datetime.now().isoformat(),
                                'room_id': room_id
                            }
                            group_rooms[room_id]['messages'].append(leave_message)

                            for other_user_id in group_rooms[room_id]['users']:
                                if other_user_id in group_connections:
                                    try:
                                        group_connections[other_user_id].send(json.dumps({
                                            'type': 'message',
                                            'data': leave_message
                                        }))
                                    except Exception as e:
                                        logger.error(f"Failed to send leave message to user {other_user_id}: {e}")

                            # Mark group room as empty for grace period instead of immediate deletion
                            if not group_rooms[room_id]['users']:
                                empty_rooms[room_id] = time.time()
                                logger.info(f"Group room {room_id} marked as empty - will be deleted after {ROOM_GRACE_PERIOD}s grace period")

                            logger.info(f"User {user_name} left room {room_id}")

            except json.JSONDecodeError:
                logger.error("Invalid JSON received in group messaging")
            except Exception as e:
                logger.error(f"Error handling group message: {e}")
                break

    except Exception as e:
        logger.error(f"Group WebSocket error: {e}")
    finally:
        # Cleanup
        if user_id:
            if user_id in group_connections:
                del group_connections[user_id]
            if user_id in group_users:
                room_id = group_users[user_id].get('room_id')
                if room_id and room_id in group_rooms:
                    if user_id in group_rooms[room_id]['users']:
                        group_rooms[room_id]['users'].remove(user_id)

                    # Notify other users
                    user_name = group_users[user_id]['display_name']
                    disconnect_message = {
                        'id': str(uuid.uuid4()),
                        'type': 'system',
                        'content': f"{user_name} disconnected",
                        'timestamp': datetime.now().isoformat(),
                        'room_id': room_id
                    }
                    group_rooms[room_id]['messages'].append(disconnect_message)

                    for other_user_id in group_rooms[room_id]['users']:
                        if other_user_id in group_connections:
                            try:
                                group_connections[other_user_id].send(json.dumps({
                                    'type': 'message',
                                    'data': disconnect_message
                                }))
                            except Exception as e:
                                logger.error(f"Failed to send disconnect message to user {other_user_id}: {e}")

                    # Mark group room as empty for grace period instead of immediate deletion
                    if not group_rooms[room_id]['users']:
                        empty_rooms[room_id] = time.time()
                        logger.info(f"Group room {room_id} marked as empty - will be deleted after {ROOM_GRACE_PERIOD}s grace period")

                del group_users[user_id]
            logger.info(f"Group user unregistered: {user_id}")

# File download endpoint for group messaging
@app.route('/download/<file_id>')
def download_file(file_id):
    if file_id not in uploaded_files:
        return jsonify({'error': 'File not found'}), 404

    file_info = uploaded_files[file_id]
    try:
        file_data = base64.b64decode(file_info['data'])
        response = app.response_class(
            file_data,
            mimetype=file_info['type'],
            headers={
                'Content-Disposition': f'attachment; filename="{file_info["name"]}"'
            }
        )
        return response
    except Exception as e:
        logger.error(f"Error serving file {file_id}: {e}")
        return jsonify({'error': 'Error serving file'}), 500

# Endpoint to get all uploaded files for session export
@app.route('/api/uploaded-files')
def get_uploaded_files():
    try:
        return jsonify({'files': uploaded_files})
    except Exception as e:
        logger.error(f"Error getting uploaded files: {e}")
        return jsonify({'error': 'Error getting uploaded files'}), 500

# Endpoint to restore uploaded files for session import
@app.route('/api/uploaded-files', methods=['POST'])
def restore_uploaded_files():
    try:
        data = request.get_json()
        files_data = data.get('files', {})

        # Clear existing files and restore from session
        global uploaded_files
        uploaded_files.clear()
        uploaded_files.update(files_data)

        logger.info(f"Restored {len(files_data)} uploaded files from session")
        return jsonify({'success': True, 'restored_count': len(files_data)})
    except Exception as e:
        logger.error(f"Error restoring uploaded files: {e}")
        return jsonify({'error': 'Error restoring uploaded files'}), 500



# Flask Routes
@app.route('/')
def serve_index():
    return send_from_directory('.', 'frontend.html')

@app.route('/<path:filename>')
def serve_static(filename):
    return send_from_directory('.', filename)

@app.route('/api/chat', methods=['POST'])
def chat_with_ai():
    try:
        logger.info("🔥 API /api/chat endpoint hit!")
        data = request.get_json()
        logger.info(f"📥 Received data keys: {list(data.keys()) if data else 'None'}")

        message = data.get('message', '')
        image_data = data.get('image_data', None)
        custom_api_key = data.get('customApiKey', None)
        selected_model = data.get('model', 'gemini-2.5-flash')

        logger.info(f"📝 Message length: {len(message) if message else 0}")
        logger.info(f"🖼️ Image data present: {bool(image_data)}")
        logger.info(f"🔑 Custom API key provided: {bool(custom_api_key)} ({mask_key(custom_api_key) if custom_api_key else 'default'})")
        logger.info(f"🤖 Selected model: {selected_model}")

        # Quick connectivity check
        if not is_online():
            logger.warning("❌ No internet connectivity detected")
            return jsonify({
                "error": "No internet connectivity detected. Check your connection and try again.",
                "status": "error"
            }), 503

        # Determine API key to use
        api_key = custom_api_key if custom_api_key else API_KEY

        # Process message content and add math instructions if needed
        processed_message = message
        if message and (any(keyword in message.lower() for keyword in ['solve', 'calculate', 'compute', 'find', 'answer', 'integral', 'derivative', 'equation']) or any(char in message for char in ['+', '-', '*', '/', '=', '^', '∫', '∑', '√'])):
            math_instructions = """

IMPORTANT MATH SOLVING INSTRUCTIONS:
- If this is a math problem, SOLVE IT STEP BY STEP with actual calculations
- Show your work clearly with numbered steps
- Provide the final numerical answer
- Use LaTeX formatting: $inline$ for inline math, $$display$$ for equations
- Don't just explain concepts - actually compute the solution
- For integrals, derivatives, equations: show the complete solution process
- For word problems: set up equations and solve them numerically

"""
            processed_message = math_instructions + message

        # Handle image processing if present
        processed_image_data = None
        if image_data:
            logger.info(f"🖼️ Image data length: {len(image_data)}")

        if not message and not image_data:
            logger.warning("❌ No message or image provided")
            return jsonify({'error': 'No message or image provided'}), 400

        # Prepare content for Gemini

        if image_data:
            logger.info(f"Processing image with message: {message[:100]}...")

            try:
                # Decode base64 image
                image_bytes = base64.b64decode(image_data)
                image = Image.open(io.BytesIO(image_bytes))

                # Convert to RGB if necessary
                if image.mode != 'RGB':
                    image = image.convert('RGB')

                logger.info(f"Image processed: {image.size}, mode: {image.mode}")

                # Create content with both text and image for Gemini Vision
                if message:
                    # Add math solving instructions if the message contains mathematical content
                    enhanced_message = message
                    if any(keyword in message.lower() for keyword in ['solve', 'calculate', 'compute', 'find', 'answer', 'integral', 'derivative', 'equation']) or any(char in message for char in ['+', '-', '*', '/', '=', '^', '∫', '∑', '√']):
                        math_instructions = """

IMPORTANT MATH SOLVING INSTRUCTIONS:
- If this is a math problem, SOLVE IT STEP BY STEP with actual calculations
- Show your work clearly with numbered steps
- Provide the final numerical answer
- Use LaTeX formatting: $inline$ for inline math, $$display$$ for equations
- Don't just explain concepts - actually compute the solution
- For integrals, derivatives, equations: show the complete solution process
- For word problems: set up equations and solve them numerically

"""
                        enhanced_message = math_instructions + message
                    content = [enhanced_message, image]
                else:
                    default_prompt = "Analyze this image and solve any mathematical problems shown step by step with actual calculations. Use LaTeX formatting for math. Show your work clearly with numbered steps and provide the final numerical answer."
                    content = [default_prompt, image]

                logger.info(f"Content prepared for Gemini: text + image")

            except Exception as img_error:
                logger.error(f"Image processing error: {img_error}")
                return jsonify({
                    'error': f'Failed to process image: {str(img_error)}',
                    'status': 'error'
                }), 400
        else:
            # Text-only content - enhance with math solving instructions if needed
            content = message
            if any(keyword in message.lower() for keyword in ['solve', 'calculate', 'compute', 'find', 'answer', 'integral', 'derivative', 'equation']) or any(char in message for char in ['+', '-', '*', '/', '=', '^', '∫', '∑', '√']):
                math_instructions = """

IMPORTANT MATH SOLVING INSTRUCTIONS:
- If this is a math problem, SOLVE IT STEP BY STEP with actual calculations
- Show your work clearly with numbered steps
- Provide the final numerical answer
- Use LaTeX formatting: $inline$ for inline math, $$display$$ for equations
- Don't just explain concepts - actually compute the solution
- For integrals, derivatives, equations: show the complete solution process
- For word problems: set up equations and solve them numerically

"""
                content = math_instructions + message
            else:
                content = message
            logger.info(f"Processing text-only message: {message[:100]}...")

        # Use REST API instead of SDK for better mobile hotspot compatibility
        logger.info(f"🌐 Using Gemini REST API with model: {selected_model}")

        # Build REST payload
        if image_data:
            # For image + text, use the processed message and image data
            payload = build_gemini_rest_payload(processed_message if message else "Analyze this image and solve any mathematical problems shown step by step with actual calculations. Use LaTeX formatting for math. Show your work clearly with numbered steps and provide the final numerical answer.", image_data)
        else:
            # For text-only, use the enhanced content
            payload = build_gemini_rest_payload(content)

        # Call Gemini REST API
        response_data = call_gemini_rest(api_key, selected_model, payload, timeout_sec=300, max_retries=2)

        # Extract text from response
        response_text = extract_text_from_response(response_data)

        logger.info("✅ Gemini REST API response received and processed")

        return jsonify({
            'response': response_text,
            'status': 'success'
        })

    except requests.exceptions.ConnectionError as e:
        logger.error(f"Connection error: {e}")
        return jsonify({
            "error": "Network/DNS connectivity issue reaching Gemini. This commonly happens with mobile hotspots. Try switching to WiFi or using a VPN.",
            "status": "error"
        }), 502
    except RateLimitError as e:
        retry_after = e.retry_after or "a few seconds"
        logger.warning(f"Rate limit hit. Suggested retry after: {retry_after}")
        return jsonify({
            "error": f"Gemini rate limit hit. Please wait {retry_after} and try again.",
            "status": "error"
        }), 429
    except requests.exceptions.Timeout as e:
        logger.error(f"Timeout error: {e}")
        return jsonify({
            "error": "Request to Gemini timed out. Try again or move closer to your hotspot.",
            "status": "error"
        }), 504
    except requests.exceptions.HTTPError as e:
        logger.error(f"HTTP error: {e}")
        status_code = e.response.status_code if e.response else 500
        return jsonify({
            "error": f"Gemini API HTTP error: {status_code}",
            "status": "error"
        }), status_code
    except Exception as e:
        error_str = str(e)
        logger.error(f"AI chat error: {e}")

        # Provide helpful error messages for mobile hotspot issues
        if "DNS resolution failed" in error_str or "generativelanguage.googleapis.com" in error_str:
            error_message = (
                "Network connectivity issue detected. This commonly happens with mobile hotspots. "
                "Try: 1) Switch to WiFi, 2) Use a VPN, 3) Change DNS settings to 8.8.8.8, "
                "or 4) Restart your mobile hotspot connection."
            )
        elif "Timeout" in error_str or "timeout" in error_str:
            error_message = (
                "Request timeout - likely due to slow mobile hotspot connection. "
                "Try moving closer to your phone or switching to a faster network."
            )
        elif "503" in error_str or "502" in error_str:
            error_message = (
                "Service temporarily unavailable. This can happen with mobile hotspots. "
                "Please try again in a few moments or switch to a different network."
            )
        else:
            error_message = f'Failed to generate response: {error_str}'

        return jsonify({
            'error': error_message,
            'status': 'error'
        }), 500

@app.route('/health')
def health_check():
    health_data = {
        "status": "healthy",
        "websocket_endpoint": "/ws",
        "ai_enabled": True,
        "port": PORT
    }

    # Add bandwidth monitoring info if available
    if BANDWIDTH_MONITORING:
        usage = bandwidth_monitor.get_current_usage()
        health_data["bandwidth_monitoring"] = {
            "enabled": True,
            "current_usage": usage
        }

    return jsonify(health_data)

@app.route('/usage-report')
def usage_report():
    """Endpoint to get bandwidth usage report"""
    if not BANDWIDTH_MONITORING:
        return jsonify({"error": "Bandwidth monitoring not enabled"}), 404

    usage = bandwidth_monitor.get_current_usage()
    projection = bandwidth_monitor.estimate_monthly_usage()

    return jsonify({
        "current_usage": usage,
        "projection": projection,
        "limits": {
            "data_transfer_gb": 5,
            "requests_per_month": 20000,
            "rate_limit_per_minute": 20000
        }
    })

if __name__ == '__main__':
    import sys

    # Check if running with local network access
    local_network = '--local-network' in sys.argv or '--network' in sys.argv

    if local_network:
        logger.info(f"Starting unified Flask app with LOCAL NETWORK ACCESS on port {PORT}")
        logger.info("This will be accessible from other devices on your local network")

        # Get local IP address
        import socket
        try:
            # Connect to a remote address to determine local IP
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
            logger.info(f"Your local IP address: {local_ip}")
            logger.info(f"Other devices can access at: http://{local_ip}:{PORT}")
        except Exception as e:
            logger.warning(f"Could not determine local IP: {e}")
            logger.info(f"Other devices can access at: http://[YOUR_IP]:{PORT}")
    else:
        logger.info(f"Starting unified Flask app with WebSocket on port {PORT}")
        logger.info("This will only be accessible from localhost (this device)")

    logger.info(f"AI features enabled with API key: {API_KEY[:10]}...")
    logger.info("WebSocket endpoint: /ws")

    # Start Flask app with WebSocket support
    host = '0.0.0.0' if local_network else '127.0.0.1'
    app.run(host=host, port=PORT, debug=False)
