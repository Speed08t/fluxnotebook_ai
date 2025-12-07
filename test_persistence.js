// Test script for PDF and Jupyter notebook persistence
// Run this in the browser console to test the persistence functionality

console.log('🧪 Starting PDF and Jupyter persistence test...');

// Test function to check current state
function checkCurrentState() {
    console.log('📊 Current State Check:');
    console.log('- currentPdfData:', !!currentPdfData);
    console.log('- currentPdfName:', currentPdfName);
    console.log('- cells.length:', cells.length);
    console.log('- currentRoomId:', currentRoomId);
    console.log('- isConnected:', isConnected);
    console.log('- isInRoom:', currentRoomId && isConnected);
    
    // Check localStorage
    const appState = localStorage.getItem('appState');
    if (appState) {
        const parsed = JSON.parse(appState);
        console.log('📦 localStorage appState:');
        console.log('- hasPdfData:', !!parsed.pdfData);
        console.log('- hasJupyterNotebook:', !!parsed.jupyterNotebook);
        console.log('- jupyterCells:', parsed.jupyterNotebook?.cells?.length || 0);
        console.log('- isInRoom (saved):', parsed.isInRoom);
    } else {
        console.log('❌ No appState found in localStorage');
    }
}

// Test function to simulate adding Jupyter content
function testJupyterPersistence() {
    console.log('📓 Testing Jupyter persistence...');
    
    // Switch to Jupyter tab
    if (typeof switchTab === 'function') {
        switchTab('jupyter');
        console.log('✅ Switched to Jupyter tab');
    }
    
    // Wait for tab to load, then add a test cell
    setTimeout(() => {
        if (typeof createCell === 'function') {
            const testCode = `# Test cell for persistence
print("Hello from test cell!")
import datetime
print(f"Created at: {datetime.datetime.now()}")`;
            
            const cell = createCell(testCode);
            console.log('✅ Created test cell');
            
            // Trigger save
            setTimeout(() => {
                if (typeof saveAppState === 'function') {
                    saveAppState();
                    console.log('✅ Triggered saveAppState');
                    
                    // Check if it was saved
                    setTimeout(() => {
                        checkCurrentState();
                    }, 500);
                }
            }, 500);
        } else {
            console.error('❌ createCell function not available');
        }
    }, 1000);
}

// Test function to simulate PDF upload
function testPdfPersistence() {
    console.log('📄 Testing PDF persistence...');
    console.log('ℹ️ To test PDF persistence:');
    console.log('1. Switch to PDF Viewer tab');
    console.log('2. Upload a PDF file');
    console.log('3. Wait for it to load');
    console.log('4. Run checkCurrentState() to verify it\'s saved');
    console.log('5. Refresh the page');
    console.log('6. Check if PDF is restored');
}

// Test function to simulate page refresh
function testPageRefresh() {
    console.log('🔄 Testing page refresh...');
    console.log('ℹ️ About to refresh the page in 3 seconds...');
    console.log('ℹ️ After refresh, run checkCurrentState() to see if data was restored');
    
    setTimeout(() => {
        window.location.reload();
    }, 3000);
}

// Test function to clear all state
function clearTestState() {
    console.log('🗑️ Clearing test state...');
    if (typeof clearAppState === 'function') {
        clearAppState();
        console.log('✅ App state cleared');
    }
    
    // Clear PDF
    if (typeof closePdf === 'function') {
        closePdf();
        console.log('✅ PDF closed');
    }
    
    // Clear Jupyter cells
    if (typeof clearAllCells === 'function') {
        clearAllCells();
        console.log('✅ Jupyter cells cleared');
    }
}

// Main test function
function runPersistenceTest() {
    console.log('🚀 Running comprehensive persistence test...');
    
    // Step 1: Check initial state
    console.log('\n📊 Step 1: Initial state check');
    checkCurrentState();
    
    // Step 2: Test Jupyter persistence
    console.log('\n📓 Step 2: Testing Jupyter persistence');
    testJupyterPersistence();
    
    // Step 3: Instructions for PDF test
    console.log('\n📄 Step 3: PDF test instructions');
    testPdfPersistence();
}

// Export functions to global scope
window.checkCurrentState = checkCurrentState;
window.testJupyterPersistence = testJupyterPersistence;
window.testPdfPersistence = testPdfPersistence;
window.testPageRefresh = testPageRefresh;
window.clearTestState = clearTestState;
window.runPersistenceTest = runPersistenceTest;

console.log('✅ Test functions loaded. Available commands:');
console.log('- runPersistenceTest() - Run full test');
console.log('- checkCurrentState() - Check current state');
console.log('- testJupyterPersistence() - Test Jupyter persistence');
console.log('- testPdfPersistence() - Get PDF test instructions');
console.log('- testPageRefresh() - Refresh page to test restoration');
console.log('- clearTestState() - Clear all test data');
