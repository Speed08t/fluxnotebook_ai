#!/bin/bash

# Collaborative Whiteboard - ngrok Free Plan Script for macOS/Linux
# This script is optimized for ngrok free plan limitations

echo "🌍 Starting Collaborative Whiteboard with ngrok (Free Plan)"
echo ""

# Check if we're in the right directory
if [ ! -f "ngrok_app.py" ]; then
    echo "❌ ERROR: ngrok_app.py not found!"
    echo "Please make sure you're in the correct directory."
    read -p "Press Enter to exit..."
    exit 1
fi

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo "⚠️  WARNING: .env file not found!"
    echo "Creating a template .env file..."
    echo "GEMINI_API_KEY=your_api_key_here" > .env
    echo "Please edit .env file and add your actual API key."
    read -p "Press Enter to continue..."
fi

# Check if ngrok is installed
if ! command -v ngrok &> /dev/null; then
    echo "❌ ERROR: ngrok not found!"
    echo ""
    echo "Quick install with Homebrew:"
    echo "brew install ngrok/ngrok/ngrok"
    echo ""
    echo "Or download from: https://ngrok.com/download"
    read -p "Press Enter to exit..."
    exit 1
fi

# Check if required packages are installed
echo "📦 Checking required packages..."
python3 -c "import flask, flask_socketio, websockets, requests, dotenv" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "📦 Installing required packages..."
    pip3 install flask flask-socketio websockets requests python-dotenv Pillow
fi

echo ""
echo "========================================"
echo "STARTING NGROK FREE PLAN SETUP..."
echo "========================================"
echo ""
echo "ℹ️  Free Plan Limitations:"
echo "   • 1 online ngrok process at a time"
echo "   • 2-hour session limit"
echo "   • 40 connections/minute"
echo ""

echo "🚀 Starting Flask + WebSocket server..."

# Start the Flask server in background
python3 ngrok_app.py &
SERVER_PID=$!

# Wait for server to start
echo "⏳ Waiting for server to start..."
sleep 3

echo ""
echo "🌍 Starting ngrok tunnel..."
echo ""
echo "📋 IMPORTANT: Copy the HTTPS URL from ngrok output below!"
echo "📤 Share that URL with anyone for global access"
echo ""
echo "🔗 Example URL: https://abc123.ngrok-free.app"
echo ""
echo "⏰ Remember: Free plan has 2-hour session limit"
echo "🔄 Restart this script when the session expires"
echo ""

# Start ngrok (this will run in foreground and show the URL)
ngrok http 5002

# When ngrok exits, kill the server
echo ""
echo "🛑 Stopping Flask server..."
kill $SERVER_PID 2>/dev/null

echo ""
echo "========================================"
echo "NGROK SESSION ENDED"
echo "========================================"
echo ""
echo "The ngrok tunnel and server have been stopped."
echo ""
echo "To start a new session:"
echo "1. Wait a moment for cleanup"
echo "2. Run this script again: ./start_ngrok_free.sh"
echo ""
read -p "Press Enter to exit..."
