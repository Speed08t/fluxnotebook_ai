@echo off
echo Installing required packages...
pip install flask-sock

echo.
echo Starting Collaborative Whiteboard with Ngrok (Free Plan)
echo.

echo Step 1: Starting the unified server...
start "Whiteboard Server" cmd /k "python ngrok_app.py"

echo.
echo Step 2: Waiting for server to start...
timeout /t 5 /nobreak > nul

echo.
echo Step 3: Starting ngrok tunnel for HTTP (port 5002)...
start "Ngrok HTTP" cmd /k "ngrok.exe http 5002"

echo.
echo ========================================
echo SETUP COMPLETE!
echo ========================================
echo.
echo 1. Wait for both windows to show "online" status
echo 2. Copy the ngrok HTTPS URL (like https://abc123.ngrok.io)
echo 3. Open that URL in your browser
echo 4. Share the URL with others for collaboration!
echo.
echo Note: Everything (HTTP + WebSocket + AI) works through ONE tunnel!
echo.
pause
