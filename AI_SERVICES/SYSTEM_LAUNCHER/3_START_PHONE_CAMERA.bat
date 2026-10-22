@echo off
chcp 65001 >nul
title [3/3] RICE VISION AI - PHONE CAMERA NODE (PORT 8765 HTTPS)
cd /d "%~dp0"
cd ..

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Moi truong ao .venv chua duoc tao!
    echo Hay chay file 0_SETUP_AI_SERVICE.bat truoc.
    pause
    exit /b 1
)

echo ===============================================================================
echo [*] DANG KHOI DONG PHONE CAMERA CAPTURE SERVER...
echo     Cong may chu: 8765 (HTTPS)
echo ===============================================================================
echo.

".venv\Scripts\python.exe" "capture_server\start.py" 8765
if errorlevel 1 (
    echo.
    echo [ERROR] Capture Server gap su co khi chay!
    pause
)
