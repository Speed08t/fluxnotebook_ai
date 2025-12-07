# Auto-Rejoin & State Persistence

This document describes the automatic room rejoin functionality and comprehensive state persistence that has been implemented in FluxNotebook.

## Overview

The enhanced persistence system includes:
1. **Auto-rejoin**: Automatically reconnects users to their previous collaboration room
2. **State persistence**: Saves and restores canvas, UI, and application state
3. **Room preservation**: Prevents rooms from being deleted during page refreshes
4. **Comprehensive restoration**: Restores all user preferences and work state

## How It Works

### Session Storage
- When a user successfully joins a room, their session data is automatically saved to `localStorage`
- Session data includes:
  - Room ID
  - User ID  
  - User name
  - Timestamp of when the session was saved

### Auto-Rejoin Process
1. When the page loads and the user connects to the collaboration server
2. The system checks for a saved room session in `localStorage`
3. If a valid session exists (not expired), the user is automatically rejoined to the room
4. The UI shows "Rejoining..." status during the process
5. Success/failure messages are displayed to inform the user

### Session Management
- **Session Expiry**: Sessions automatically expire after 24 hours
- **Manual Clear**: Sessions are cleared when users manually leave a room
- **Connection Loss**: Sessions persist through connection losses to enable rejoin after reconnection

## User Experience

### Visual Indicators
- Connection status shows "Rejoining..." during auto-rejoin process
- Success message: "Automatically rejoined room: [ROOM_ID]"
- Failure message: "Failed to automatically rejoin previous room. The room may no longer exist."

### User Control
Users can manually clear their room session by calling `clearRoomSession()` in the browser console, which will prevent auto-rejoin on the next page refresh.

## Technical Implementation

### Key Functions

#### `saveRoomSession(roomId, userId, userName)`
Saves room session data to localStorage with current timestamp.

#### `loadRoomSession()`
Loads and validates room session data, automatically clearing expired sessions.

#### `clearRoomSession()`
Removes room session data from localStorage.

### Integration Points

#### Connection Handler
```javascript
collaborationSocket.onopen = () => {
    // ... registration logic ...
    
    // Check for saved session and auto-rejoin
    const savedSession = loadRoomSession();
    if (savedSession && savedSession.roomId && !isAutoRejoining) {
        isAutoRejoining = true;
        // Attempt to rejoin room
        collaborationSocket.send(JSON.stringify({
            type: 'join_room',
            room_id: savedSession.roomId
        }));
    }
};
```

#### Message Handler
```javascript
case 'room_joined':
    if (data.success) {
        if (isAutoRejoining) {
            console.log('✅ Auto-rejoin successful');
            addChatMessage('System', `Automatically rejoined room: ${data.room_id}`);
            isAutoRejoining = false;
        }
        // ... rest of room join logic ...
    }
```

## Testing

### Manual Testing
1. Join a collaboration room
2. Refresh the page
3. Verify automatic rejoin occurs
4. Check console for debug messages

### Console Testing
Use the browser console to test session management:

```javascript
// Check current session
testAutoRejoin()

// Save a test session  
saveRoomSession('TEST123', 'user-456', 'TestUser')

// Load session
loadRoomSession()

// Clear session
clearRoomSession()
```

### Test Page
A dedicated test page (`test_auto_rejoin.html`) is available for comprehensive testing of the auto-rejoin functionality.

## Configuration

### Session Expiry
The session expiry time is set to 24 hours and can be modified in the `loadRoomSession()` function:

```javascript
const maxAge = 24 * 60 * 60 * 1000; // 24 hours in milliseconds
```

### Auto-Rejoin Delay
There's a 500ms delay before attempting to rejoin to ensure registration is complete:

```javascript
setTimeout(() => {
    collaborationSocket.send(JSON.stringify({
        type: 'join_room',
        room_id: savedSession.roomId
    }));
}, 500);
```

## Error Handling

- **Expired Sessions**: Automatically cleared and user notified
- **Invalid Room**: User notified that room may no longer exist
- **Connection Issues**: Auto-rejoin flag reset on disconnect
- **JSON Parsing Errors**: Session cleared and error logged

## Security Considerations

- Session data is stored in localStorage (client-side only)
- No sensitive information is stored in the session
- Sessions automatically expire to prevent indefinite storage
- Room access is still validated by the server

## New Features Added

### Server-Side Room Preservation
- **Delayed Room Deletion**: Rooms are no longer immediately deleted when empty
- **30-Second Grace Period**: Empty rooms are preserved for 30 seconds to allow auto-rejoin
- **Smart Cleanup**: Rooms are only deleted if they remain empty after the grace period

### Comprehensive State Persistence
- **Canvas State**: All drawings, objects, zoom, and viewport position
- **UI State**: Dark mode, toolbar collapse, sidebar visibility and width
- **User Preferences**: Notification settings, voice settings
- **Automatic Saving**: State saved every 30 seconds and on canvas changes
- **Smart Restoration**: State restored on page load with 24-hour expiry

### Enhanced Debugging
```javascript
// New debugging functions
saveAppState()      // Save complete application state
loadAppState()      // Load saved application state
restoreAppState()   // Restore UI and canvas from saved state
clearAppState()     // Clear all saved state
```

## Testing the Enhanced Features

### Test Room Preservation
1. Create a room (you're the only user)
2. Refresh the page
3. Verify you auto-rejoin the same room (room wasn't deleted)

### Test State Persistence
1. Draw something on canvas
2. Change UI settings (dark mode, sidebar width, etc.)
3. Refresh the page
4. Verify everything is restored exactly as before

### Test Console Commands
```javascript
// Check current state
testAutoRejoin()

// Save current state manually
saveAppState()

// Check what's saved
loadAppState()

// Restore state manually
restoreAppState()
```

## Future Enhancements

Potential improvements to consider:
- Configurable session expiry time
- Multiple room session support
- Server-side session validation
- Encrypted session storage
- Cross-tab session synchronization
- Canvas version history
- Collaborative state synchronization
