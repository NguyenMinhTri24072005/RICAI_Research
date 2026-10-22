@echo off
chcp 65001 >nul
title [1/3] RICE VISION AI - INFERENCE ENGINE (PORT 8000)
cd /d "%~dp0"
cd ..
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"

if not exist ".venv\Scripts\python.exe" (
    echo ===============================================================================
    echo [CANH BAO] Chua co moi truong ao AI_SERVICES\.venv
    echo Vui long double click vao file 0_SETUP_AI_SERVICE.bat truoc de cai dat.
    echo ===============================================================================
    echo.
    pause
    exit /b 1
)

echo ===============================================================================
echo [*] DANG KHOI DONG RICE VISION AI INFERENCE SERVICE...
echo     Dia chi may chu  : http://localhost:8000
echo     Swagger API Docs : http://localhost:8000/docs
echo     Kiem tra Status  : http://localhost:8000/api/status
echo ===============================================================================
echo.

".venv\Scripts\python.exe" app.py
if errorlevel 1 (
    echo.
    echo [THONG BAO] Server da dung hoac xay ra loi.
    pause
)
