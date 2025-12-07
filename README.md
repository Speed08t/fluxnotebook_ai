# AI Notebook with Real-time Canvas Collaboration

A collaborative drawing application with AI integration that allows multiple users to draw together in real-time using WebSocket and WebRTC technologies.

## Features

### Core Drawing Features
- **Drawing Tools**: Pen, highlighter (rectangle/circle), eraser
- **Canvas Controls**: Zoom in/out, magnifier, clear canvas
- **Customization**: Color picker, brush size adjustment
- **Export**: PDF export functionality
- **AI Integration**: Ask AI about canvas content with image analysis

### Real-time Collaboration Features
- **Room Management**: Create and join collaboration rooms with unique IDs
- **Real-time Synchronization**: All drawing actions sync instantly across users
- **User Presence**: See active users and their cursor positions
- **Canvas State Sync**: New users get the current canvas state when joining
- **User Management**: Support for multiple users per room (configurable limits)

### Technical Features
- **WebSocket Communication**: Real-time bidirectional communication
- **Canvas Event Synchronization**: All drawing operations are shared
- **Cursor Tracking**: See other users' mouse positions in real-time
- **Automatic Reconnection**: Handles connection drops gracefully
- **Edge Case Handling**: Prevents infinite loops and handles user disconnections

## Installation

1. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Set up Gemini API** (for AI features):
   - Get an API key from Google AI Studio
   - Update the `API_KEY` in `app.py` or set as environment variable

## Running the Application

### Option 1: Start Both Servers Automatically
```bash
python start_servers.py
```

### Option 2: Start Servers Manually

1. **Start the main Flask application**:
   ```bash
   python app.py
   ```
   This starts the web server on `http://localhost:5002`

2. **Start the collaboration server** (in a separate terminal):
   ```bash
   python collaboration_server.py
   ```
   This starts the WebSocket server on `ws://localhost:8765`

3. **Open the application**:
   Navigate to `http://localhost:5002` in your web browser

## How to Use Collaboration

### Creating a Room
1. Click the **"Create"** button in the collaboration toolbar
2. Enter an optional room name and select max users
3. Click **"Create Room"**
4. The room ID will be automatically copied to your clipboard
5. Share the room ID with others

### Joining a Room
1. Click the **"Join"** button in the collaboration toolbar
2. Enter the room ID provided by the room creator
3. Enter your display name
4. Click **"Join Room"**

### Collaborating
- All drawing actions are synchronized in real-time
- You can see other users' cursors moving on the canvas
- The user count shows how many people are in the room
- Use the **"Leave"** button to exit the room

## Architecture

### Frontend (`frontend.html`)
- **Fabric.js**: Canvas manipulation and drawing
- **WebSocket Client**: Real-time communication
- **Tailwind CSS**: Modern UI styling
- **MathJax**: Mathematical notation rendering

### Backend
- **Flask App** (`app.py`): Main web server and AI integration
- **Collaboration Server** (`collaboration_server.py`): WebSocket server for real-time features

### Communication Flow
1. **Canvas Events**: Drawing → WebSocket → Other Users
2. **User Management**: Join/Leave → Server → Room Updates
3. **Cursor Tracking**: Mouse Move → WebSocket → Cursor Display
4. **State Sync**: New User → Server → Current Canvas State

## Supported Canvas Operations

All these operations are synchronized in real-time:
- **Drawing**: Pen strokes and paths
- **Shapes**: Rectangles and circles (highlights)
- **Object Manipulation**: Move, resize, rotate objects
- **Object Deletion**: Remove individual objects
- **Canvas Clear**: Clear entire canvas
- **Background Changes**: Theme switching

## Edge Cases Handled

- **Connection Loss**: Automatic reconnection attempts
- **User Disconnection**: Cleanup of user cursors and room state
- **Empty Rooms**: Automatic room deletion when last user leaves
- **Duplicate Events**: Prevention of infinite event loops
- **Canvas State Conflicts**: Last-write-wins approach
- **Invalid Room IDs**: Proper error handling and user feedback

## Browser Compatibility

- **Modern Browsers**: Chrome, Firefox, Safari, Edge (latest versions)
- **WebSocket Support**: Required for collaboration features
- **Canvas Support**: HTML5 Canvas required for drawing

## Troubleshooting

### Collaboration Not Working
1. Check that both servers are running
2. Verify WebSocket connection in browser console
3. Ensure firewall allows connections to port 8765

### AI Features Not Working
1. Verify Gemini API key is set correctly
2. Check internet connection for API calls
3. Review console for API error messages

### Performance Issues
1. Limit number of users per room (default: 10)
2. Clear canvas periodically for better performance
3. Check network latency for real-time features

## Development

### Adding New Canvas Events
1. Add event type to `collaboration_server.py`
2. Implement handler in `handleRemoteCanvasEvent()`
3. Add sender in appropriate canvas event listener

### Extending User Features
1. Update `User` dataclass in server
2. Add UI elements in frontend
3. Implement WebSocket message handlers

## License

This project is open source and available under the MIT License.
