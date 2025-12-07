// Test script for host status preservation on refresh
// Run this in the browser console to test the fix

console.log('🧪 Starting host refresh test...');

// Test function to check host status preservation
function testHostRefresh() {
    console.log('=== HOST REFRESH TEST ===');
    
    // Check current state
    console.log('Current state:');
    console.log('- currentUserId:', currentUserId);
    console.log('- currentRoomId:', currentRoomId);
    console.log('- currentRoomHostId:', currentRoomHostId);
    console.log('- Am I the host?:', currentUserId === currentRoomHostId);
    
    // Check saved session
    const savedSession = loadRoomSession();
    console.log('Saved session:');
    console.log('- Session exists:', !!savedSession);
    if (savedSession) {
        console.log('- roomId:', savedSession.roomId);
        console.log('- userId:', savedSession.userId);
        console.log('- userName:', savedSession.userName);
        console.log('- isHost:', savedSession.isHost);
        console.log('- timestamp:', new Date(savedSession.timestamp));
    }
    
    // Check if user should be host
    if (savedSession && savedSession.isHost) {
        if (currentUserId === currentRoomHostId) {
            console.log('✅ HOST STATUS CORRECT: You are the room creator and currently have host privileges');
            return true;
        } else {
            console.log('❌ HOST STATUS ISSUE: You are the room creator but do not have host privileges');
            console.log('💡 This indicates the bug is still present');
            return false;
        }
    } else {
        console.log('ℹ️ You are not the room creator, so host status is not expected');
        return true;
    }
}

// Function to simulate the refresh test
function simulateRefreshTest() {
    console.log('🔄 SIMULATING REFRESH TEST...');
    
    if (!currentRoomId) {
        console.log('❌ Please create or join a room first');
        return;
    }
    
    if (currentUserId !== currentRoomHostId) {
        console.log('❌ You must be the host to test host refresh');
        console.log('💡 Create a new room to become the host');
        return;
    }
    
    console.log('✅ Pre-refresh state looks good');
    console.log('📝 Instructions:');
    console.log('1. You are currently the host of room:', currentRoomId);
    console.log('2. Now refresh the page (F5 or Ctrl+R)');
    console.log('3. After the page loads and auto-rejoin completes, run testHostRefresh() again');
    console.log('4. The test should show "HOST STATUS CORRECT" if the fix works');
    
    // Save current state for comparison
    window.preRefreshState = {
        roomId: currentRoomId,
        userId: currentUserId,
        hostId: currentRoomHostId,
        wasHost: currentUserId === currentRoomHostId
    };
}

// Function to check post-refresh state
function checkPostRefresh() {
    console.log('🔍 CHECKING POST-REFRESH STATE...');
    
    if (!window.preRefreshState) {
        console.log('❌ No pre-refresh state found. Run simulateRefreshTest() first.');
        return;
    }
    
    const pre = window.preRefreshState;
    console.log('Pre-refresh state:');
    console.log('- Room ID:', pre.roomId);
    console.log('- User ID:', pre.userId);
    console.log('- Host ID:', pre.hostId);
    console.log('- Was host:', pre.wasHost);
    
    console.log('Current state:');
    console.log('- Room ID:', currentRoomId);
    console.log('- User ID:', currentUserId);
    console.log('- Host ID:', currentRoomHostId);
    console.log('- Is host:', currentUserId === currentRoomHostId);
    
    // Check if host status was preserved
    if (pre.wasHost && currentUserId === currentRoomHostId) {
        console.log('✅ SUCCESS: Host status was preserved after refresh!');
        return true;
    } else if (pre.wasHost && currentUserId !== currentRoomHostId) {
        console.log('❌ FAILURE: Host status was lost after refresh');
        return false;
    } else {
        console.log('ℹ️ User was not host before refresh, so no host status to preserve');
        return true;
    }
}

// Make functions available globally
window.testHostRefresh = testHostRefresh;
window.simulateRefreshTest = simulateRefreshTest;
window.checkPostRefresh = checkPostRefresh;

console.log('🧪 Host refresh test functions loaded:');
console.log('- testHostRefresh() - Check current host status');
console.log('- simulateRefreshTest() - Prepare for refresh test');
console.log('- checkPostRefresh() - Check status after refresh');
