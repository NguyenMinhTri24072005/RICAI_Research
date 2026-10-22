@echo off
chcp 65001 >nul
title RICE VISION AI - MASTER SYSTEM LAUNCHER
cd /d "%~dp0"

echo ===============================================================================
echo                HE THONG UOC TINH SO LUONG HAT LUA (RICE VISION AI)
echo                          --- TRINH KHOI DONG 1-CLICK ---
echo ===============================================================================
echo.
echo [*] Dang khoi dong cac tien trinh theo thu tu chuan...
echo.

echo [1/2] Dang bat AI Inference Service (Port 8000)...
start "[1] AI INFERENCE SERVICE" cmd /k "call 1_START_AI_SERVICE.bat"

echo [*] Dang doi AI Service khoi tao mo hinh va san sang (khoang 10-15 giay)...
set /a ai_count=0

:poll_ai
set /a ai_count+=1
ping -n 3 127.0.0.1 >nul
curl -s http://localhost:8000/health 2>nul | findstr /i "ok" >nul
if not errorlevel 1 goto ai_ready
if %ai_count% geq 15 goto ai_timeout
echo     ... dang nap mo hinh AI Core (lan %ai_count%/15)
goto poll_ai

:ai_timeout
echo [CANH BAO] AI Service mat nhieu thoi gian khoi dong hon du kien.
echo Van tiep tuc bat Web Dashboard...
goto start_web

:ai_ready
echo [OK] AI Service da san sang!

:start_web
echo.
echo [2/2] Dang bat Web Dashboard va Node Gateway (Port 5173 / 3000)...
start "[2] WEB DASHBOARD" cmd /k "call 2_START_WEB_DASHBOARD.bat"
ping -n 6 127.0.0.1 >nul

echo.
echo ===============================================================================
echo [*] HE THONG DA KHOI DONG THANH CONG!
echo     - Giao dien Web Dashboard : http://localhost:5173
echo     - Backend Node Gateway    : http://localhost:3000
echo     - AI Python FastAPI Core  : http://localhost:8000 (Docs: /docs)
echo     - Phone Camera Node       : Tu dong khoi chay boi Gateway khi quet QR
echo ===============================================================================
echo.
echo [*] Dang tu dong mo trinh duyet den Dashboard...
start http://localhost:5173

echo.
echo [Luu y] Khi khong su dung nua, hay chay file 'STOP_ALL_SYSTEM.bat' de tat sach he thong.
echo Cua so nay co the dong lai duoc.
pause