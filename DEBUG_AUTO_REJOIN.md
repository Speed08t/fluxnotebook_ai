# Debug Auto-Rejoin Issue

## Quick Debug Steps

### 1. Test Session Saving
1. Open the FluxNotebook application
2. Join or create a room
3. Open browser console (F12)
4. Run: `testAutoRejoin()`
5. Check if session was saved properly

### 2. Test Session Loading
1. After joining a room, run in console: `loadRoomSession()`
2. Should return session data with roomId, userId, userName, timestamp

### 3. Test Manual Auto-Rejoin
1. While in a room, run in console: `triggerAutoRejoin()`
2. This will manually trigger the auto-rejoin process

### 4. Test Page Refresh
1. Join a room
2. Check console for "💾 Room session saved" message
3. Refresh the page
4. Check console for auto-rejoin messages:
   - "🔍 Checking for saved room session..."
   - "📋 Saved session result: [object]"
   - "🔄 Auto-rejoining room: [ROOM_ID]"
   - "📤 Sending rejoin request for room: [ROOM_ID]"

## Expected Console Output

### When Joining a Room:
```
💾 Attempting to save room session: {roomId: "ABC123", userId: "user-xyz", userName: "YourName"}
✅ Room session saved successfully: {roomId: "ABC123", userId: "user-xyz", userName: "YourName", timestamp: 1234567890}
🔍 Verification - stored data: {"roomId":"ABC123","userId":"user-xyz","userName":"YourName","timestamp":1234567890}
💾 Room session saved for manual join: ABC123
```

### When Page Refreshes:
```
🔍 Checking for saved room session...
📂 Room session loaded: {roomId: "ABC123", userId: "user-xyz", userName: "YourName", timestamp: 1234567890}
📋 Saved session result: {roomId: "ABC123", userId: "user-xyz", userName: "YourName", timestamp: 1234567890}
🔄 Auto-rejoining room: ABC123
📤 Sending rejoin request for room: ABC123
✅ Auto-rejoin successful for room: ABC123
```

## Common Issues & Solutions

### Issue 1: No Session Saved
**Symptoms:** `testAutoRejoin()` shows "No saved session found"
**Causes:**
- `currentUserId` is null when trying to save
- Session save function not called
- localStorage is disabled

**Debug:**
```javascript
// Check if currentUserId exists
console.log('currentUserId:', currentUserId);

// Check localStorage
console.log('localStorage test:', localStorage.getItem('test'));
localStorage.setItem('test', 'works');
console.log('localStorage works:', localStorage.getItem('test') === 'works');
```

### Issue 2: Session Saved But Not Loading
**Symptoms:** Session exists but auto-rejoin doesn't trigger
**Debug:**
```javascript
// Check raw localStorage data
console.log('Raw session data:', localStorage.getItem('roomSession'));

// Test loading function
console.log('Load result:', loadRoomSession());
```

### Issue 3: Auto-Rejoin Triggers But Fails
**Symptoms:** See rejoin messages but still get kicked out
**Causes:**
- Room no longer exists
- Server rejects rejoin request
- WebSocket connection issues

**Debug:**
```javascript
// Check connection state
console.log('WebSocket state:', collaborationSocket?.readyState);
console.log('Expected state (OPEN):', WebSocket.OPEN);

// Check server response
// Look for 'room_joined' message with success: false
```

## Manual Testing Commands

```javascript
// 1. Check current state
testAutoRejoin()

// 2. Save a test session
saveRoomSession('TEST123', 'user-test', 'TestUser')

// 3. Load session
loadRoomSession()

// 4. Clear session
clearRoomSession()

// 5. Trigger manual auto-rejoin
triggerAutoRejoin()

// 6. Check localStorage directly
localStorage.getItem('roomSession')

// 7. Check connection state
console.log({
    currentUserId,
    currentRoomId,
    isAutoRejoining,
    isConnected,
    socketState: collaborationSocket?.readyState
})
```

## If Still Not Working

1. **Check Browser Console** for any JavaScript errors
2. **Check Network Tab** to see if WebSocket messages are being sent/received
3. **Try Different Browser** to rule out localStorage issues
4. **Check Server Logs** if you have access to them

## Quick Fix Attempt

If the issue persists, try this in the console after joining a room:

```javascript
// Force save session
if (currentUserId && currentRoomId) {
    const userName = localStorage.getItem('userName') || 'Anonymous';
    saveRoomSession(currentRoomId, currentUserId, userName);
    console.log('✅ Manually saved session');
} else {
    console.log('❌ Missing currentUserId or currentRoomId');
}
```

Then refresh and check if auto-rejoin works.
