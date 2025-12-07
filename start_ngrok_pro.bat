@echo off
echo.
echo ========================================
echo Collaborative Whiteboard - ngrok Pro Plan
echo 24/7 Hosting with Permanent URL
echo ========================================
echo.

REM Configuration - UPDATE THESE VALUES
set RESERVED_DOMAIN=your-app-name.ngrok.io
set CUSTOM_DOMAIN=

echo Configuration:
echo   Reserved Domain: %RESERVED_DOMAIN%
if not "%CUSTOM_DOMAIN%"=="" echo   Custom Domain: %CUSTOM_DOMAIN%
echo.

REM Check if ngrok.exe exists
if not exist "ngrok.exe" (
    echo ERROR: ngrok.exe not found!
    echo.
    echo Please download ngrok.exe from https://ngrok.com/download
    echo and place it in this directory.
    echo.
    pause
    exit /b 1
)

REM Check if ngrok is authenticated
echo Checking ngrok authentication...
ngrok.exe config check >nul 2>&1
if errorlevel 1 (
    echo ERROR: ngrok not authenticated!
    echo.
    echo Please authenticate ngrok first:
    echo 1. Sign up for ngrok Personal plan ($8/month) at https://ngrok.com/pricing
    echo 2. Get your auth token from https://dashboard.ngrok.com/get-started/your-authtoken
    echo 3. Run: ngrok.exe config add-authtoken YOUR_AUTH_TOKEN
    echo.
    pause
    exit /b 1
)

echo Installing required packages...
pip install -r requirements.txt

echo.
echo ========================================
echo STARTING NGROK PRO PLAN SETUP...
echo ========================================
echo.
echo Pro Plan Benefits:
echo   * Permanent URL (no more random URLs!)
echo   * 24/7 hosting (no 2-hour session limit)
echo   * 5 GB data transfer/month
echo   * 20,000 requests/month
echo   * Custom domain support
echo.

echo Step 1: Starting the unified server...
start "Whiteboard Server" cmd /k "python ngrok_app.py"

echo.
echo Step 2: Waiting for server to start...
timeout /t 5 /nobreak > nul

echo.
echo Step 3: Starting ngrok tunnel with permanent URL...

REM Determine which domain to use
if not "%CUSTOM_DOMAIN%"=="" (
    set DOMAIN_TO_USE=%CUSTOM_DOMAIN%
    echo Using custom domain: https://%CUSTOM_DOMAIN%
) else (
    set DOMAIN_TO_USE=%RESERVED_DOMAIN%
    echo Using reserved domain: https://%RESERVED_DOMAIN%
    echo.
    echo IMPORTANT: Make sure you have reserved the domain '%RESERVED_DOMAIN%'
    echo If not, reserve it at: https://dashboard.ngrok.com/cloud-edge/domains
)

echo.
echo 24/7 hosting enabled - no session limits!
echo Share this permanent URL with anyone for global access
echo Monitor usage at: https://dashboard.ngrok.com
echo.

REM Start ngrok with the configured domain
if not "%CUSTOM_DOMAIN%"=="" (
    start "Ngrok Pro Tunnel" cmd /k "ngrok.exe http --domain=%CUSTOM_DOMAIN% 5002"
) else (
    start "Ngrok Pro Tunnel" cmd /k "ngrok.exe http --domain=%RESERVED_DOMAIN% 5002"
)

echo.
echo ========================================
echo SETUP COMPLETE!
echo ========================================
echo.
echo 1. Wait for the ngrok window to show "online" status
echo 2. Your permanent URL is ready: https://%DOMAIN_TO_USE%
echo 3. Share this URL with others for collaboration!
echo 4. The server will run 24/7 until you stop it
echo.
echo To stop the servers:
echo 1. Close the ngrok window
echo 2. Close the server window
echo.
echo Monitor your usage at: https://dashboard.ngrok.com
echo.
pause
