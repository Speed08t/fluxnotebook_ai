#!/bin/bash

# Collaborative Whiteboard - ngrok Pro Plan Script for 24/7 Hosting
# This script uses ngrok Personal/Pro plan for permanent URLs and unlimited sessions

echo "🌍 Starting Collaborative Whiteboard with ngrok Pro (24/7 Hosting)"
echo ""

# Check if we're in the right directory
if [ ! -f "ngrok_app.py" ]; then
    echo "❌ ERROR: ngrok_app.py not found!"
    echo "Please make sure you're in the correct directory."
    read -p "Press Enter to exit..."
    exit 1
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

# Check if ngrok is authenticated
echo "🔐 Checking ngrok authentication..."
if ! ngrok config check &> /dev/null; then
    echo "❌ ERROR: ngrok not authenticated!"
    echo ""
    echo "Please authenticate ngrok first:"
    echo "1. Sign up for ngrok Personal plan ($8/month) at https://ngrok.com/pricing"
    echo "2. Get your auth token from https://dashboard.ngrok.com/get-started/your-authtoken"
    echo "3. Run: ngrok config add-authtoken YOUR_AUTH_TOKEN"
    echo ""
    read -p "Press Enter to exit..."
    exit 1
fi

# Configuration - UPDATE THESE VALUES
RESERVED_DOMAIN="your-app-name.ngrok.io"  # Replace with your reserved domain
CUSTOM_DOMAIN=""  # Optional: your custom domain (e.g., app.yourdomain.com)

echo "⚙️  Configuration:"
echo "   Reserved Domain: $RESERVED_DOMAIN"
if [ ! -z "$CUSTOM_DOMAIN" ]; then
    echo "   Custom Domain: $CUSTOM_DOMAIN"
fi
echo ""

# Check if required packages are installed
echo "📦 Checking required packages..."
python3 -c "import flask, flask_sock, google.generativeai" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "📦 Installing required packages..."
    pip3 install -r requirements.txt
fi

echo ""
echo "========================================"
echo "STARTING NGROK PRO PLAN SETUP..."
echo "========================================"
echo ""
echo "✅ Pro Plan Benefits:"
echo "   • Permanent URL (no more random URLs!)"
echo "   • 24/7 hosting (no 2-hour session limit)"
echo "   • 5 GB data transfer/month"
echo "   • 20,000 requests/month"
echo "   • Custom domain support"
echo ""

echo "🚀 Starting Flask + WebSocket server..."

# Start the Flask server in background
python3 ngrok_app.py &
SERVER_PID=$!

# Wait for server to start
echo "⏳ Waiting for server to start..."
sleep 3

echo ""
echo "🌍 Starting ngrok tunnel with permanent URL..."

# Determine which domain to use
if [ ! -z "$CUSTOM_DOMAIN" ]; then
    DOMAIN_TO_USE=$CUSTOM_DOMAIN
    echo "🔗 Using custom domain: https://$CUSTOM_DOMAIN"
else
    DOMAIN_TO_USE=$RESERVED_DOMAIN
    echo "🔗 Using reserved domain: https://$RESERVED_DOMAIN"
fi

echo ""
echo "✅ 24/7 hosting enabled - no session limits!"
echo "📤 Share this permanent URL with anyone for global access"
echo "📊 Monitor usage at: https://dashboard.ngrok.com"
echo ""

# Function to handle cleanup
cleanup() {
    echo ""
    echo "🛑 Stopping Flask server..."
    kill $SERVER_PID 2>/dev/null
    echo "✅ Cleanup complete"
    exit 0
}

# Set up signal handlers
trap cleanup SIGINT SIGTERM

# Start ngrok with the configured domain
if [ ! -z "$CUSTOM_DOMAIN" ]; then
    echo "Starting ngrok with custom domain: $CUSTOM_DOMAIN"
    ngrok http --domain=$CUSTOM_DOMAIN 5002
else
    echo "Starting ngrok with reserved domain: $RESERVED_DOMAIN"
    echo ""
    echo "⚠️  IMPORTANT: Make sure you have reserved the domain '$RESERVED_DOMAIN'"
    echo "   If not, reserve it at: https://dashboard.ngrok.com/cloud-edge/domains"
    echo ""
    ngrok http --domain=$RESERVED_DOMAIN 5002
fi

# This will only execute if ngrok exits
cleanup
