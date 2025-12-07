# PDF and Jupyter Notebook Persistence Test Guide

## Overview
This guide will help you test that PDF files and Jupyter notebook content are properly saved and restored when you refresh the page.

## What Was Fixed
The issue was that PDF and Jupyter notebook data were only being saved when the user was NOT in a collaboration room. However, users could auto-rejoin rooms on refresh, which prevented the data from being restored. 

**Changes made:**
1. PDF data is now always saved when available (regardless of room status)
2. Jupyter notebook data is now always saved when available (regardless of room status)
3. Both are always restored when available (regardless of room status)

## Test Steps

### 1. Initial Setup
1. Open the application at http://127.0.0.1:8080
2. Open browser developer console (F12)
3. Run the following command to check initial state:
   ```javascript
   debugPersistenceState()
   ```

### 2. Test Jupyter Notebook Persistence

#### Step 2a: Create Jupyter Content
1. Click on the "Jupyter" tab
2. Wait for the status to show "Ready"
3. In the first cell, enter some test code:
   ```python
   # Test persistence
   import datetime
   print(f"Created at: {datetime.datetime.now()}")
   x = 42
   print(f"Test value: {x}")
   ```
4. Press Shift+Enter to run the cell
5. Add another cell with different content:
   ```python
   # Second test cell
   import math
   result = math.sqrt(16)
   print(f"Square root of 16 is: {result}")
   ```
6. Run this cell as well

#### Step 2b: Verify Jupyter Data is Saved
1. In the console, run:
   ```javascript
   debugJupyterState()
   debugPersistenceState()
   ```
2. You should see:
   - `cells.length: 2` (or more)
   - `hasJupyterNotebook: true` in localStorage
   - `jupyterCells: 2` (or more)

#### Step 2c: Test Jupyter Restoration
1. Refresh the page (Ctrl+R or F5)
2. Wait for the page to load completely
3. Check if you're automatically switched to the Jupyter tab
4. Verify that your cells and their content are restored
5. In console, run:
   ```javascript
   debugJupyterState()
   ```

### 3. Test PDF Persistence

#### Step 3a: Upload a PDF
1. Click on the "PDF Viewer" tab
2. Click "Choose PDF File" or drag and drop a PDF
3. Wait for the PDF to load completely
4. Navigate to a specific page (not page 1)
5. Zoom in or out to a specific level

#### Step 3b: Verify PDF Data is Saved
1. In the console, run:
   ```javascript
   debugPdfState()
   debugPersistenceState()
   ```
2. You should see:
   - `currentPdfData: true`
   - `currentPdfName: [your-pdf-name]`
   - `hasPdfData: true` in localStorage
   - `pdfName: [your-pdf-name]`

#### Step 3c: Test PDF Restoration
1. Refresh the page (Ctrl+R or F5)
2. Wait for the page to load completely
3. Check if you're automatically switched to the PDF Viewer tab
4. Verify that:
   - The same PDF is loaded
   - You're on the same page you were viewing
   - The zoom level is preserved
5. In console, run:
   ```javascript
   debugPdfState()
   ```

### 4. Test Combined Persistence
1. Have both Jupyter content and a PDF loaded
2. Switch between tabs to verify both are working
3. Refresh the page
4. Verify both are restored correctly

### 5. Test in Collaboration Room
1. Create or join a collaboration room
2. Add Jupyter content and upload a PDF
3. Refresh the page
4. Verify that:
   - You auto-rejoin the room
   - PDF and Jupyter content are still restored
   - Canvas drawings are also restored

## Debug Commands

Use these commands in the browser console to debug issues:

```javascript
// Check overall persistence state
debugPersistenceState()

// Check PDF-specific state
debugPdfState()

// Check Jupyter-specific state
debugJupyterState()

// Check if you're in a room
console.log('Room status:', {
  currentRoomId: currentRoomId,
  isConnected: isConnected,
  isInRoom: currentRoomId && isConnected
})

// Manually save state
saveAppState()

// Manually restore state
restoreAppState()

// Clear all saved state (for testing)
clearAppState()
```

## Expected Behavior

✅ **Working correctly:**
- PDF files persist across page refreshes
- Jupyter notebook cells and their content persist
- Both work whether you're in a collaboration room or not
- Auto-switching to the appropriate tab after restoration

❌ **If not working:**
- Check console for error messages
- Verify localStorage has the data using `debugPersistenceState()`
- Check if functions are available using `typeof saveAppState`

## Troubleshooting

If persistence isn't working:

1. **Check browser console for errors**
2. **Verify localStorage is working:**
   ```javascript
   localStorage.setItem('test', 'works')
   console.log(localStorage.getItem('test'))
   ```
3. **Check if you're in private/incognito mode** (localStorage may be disabled)
4. **Clear localStorage and try again:**
   ```javascript
   clearAppState()
   ```
5. **Check if the save functions are being called:**
   - Look for console messages like "💾 Comprehensive app state saved"
   - Look for restoration messages like "📄 Restoring PDF..." or "📓 Restoring Jupyter notebook..."

## Success Criteria

The fix is working correctly if:
1. ✅ Jupyter notebook cells persist across page refreshes
2. ✅ PDF files and their viewing state persist across page refreshes  
3. ✅ Both work when in collaboration rooms
4. ✅ Both work when not in collaboration rooms
5. ✅ Auto-switching to appropriate tabs after restoration
6. ✅ No console errors during save/restore operations
