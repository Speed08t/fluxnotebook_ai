#!/usr/bin/env python3
"""
Startup script to run both the main Flask app and the collaboration server
"""

import subprocess
import sys
import time
import threading
import os

def run_flask_app():
    """Run the main Flask application"""
    print("Starting Flask app on port 5002...")
    try:
        subprocess.run([sys.executable, "app.py"], check=True)
    except KeyboardInterrupt:
        print("Flask app stopped")
    except Exception as e:
        print(f"Error running Flask app: {e}")

def run_collaboration_server():
    """Run the collaboration WebSocket server"""
    print("Starting collaboration server on port 8765...")
    try:
        subprocess.run([sys.executable, "collaboration_server.py"], check=True)
    except KeyboardInterrupt:
        print("Collaboration server stopped")
    except Exception as e:
        print(f"Error running collaboration server: {e}")

def main():
    """Start both servers"""
    print("Starting AI Notebook with Real-time Collaboration...")
    print("=" * 50)
    
    # Check if required files exist
    required_files = ["app.py", "collaboration_server.py", "frontend.html"]
    for file in required_files:
        if not os.path.exists(file):
            print(f"Error: Required file '{file}' not found!")
            return
    
    try:
        # Start Flask app in a separate thread
        flask_thread = threading.Thread(target=run_flask_app, daemon=True)
        flask_thread.start()
        
        # Give Flask a moment to start
        time.sleep(2)
        
        # Start collaboration server in main thread
        run_collaboration_server()
        
    except KeyboardInterrupt:
        print("\nShutting down servers...")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
