@echo off
chcp 65001 >nul
title [2/3] RICE VISION AI - WEB DASHBOARD (PORT 5173 & 3000)
cd /d "%~dp0"
cd ..\RICE_ESTIMATION_APPLICATION

echo ===============================================================================
echo [*] DANG KHOI DONG RICE ESTIMATION APPLICATION (BACKEND + FRONTEND)...
echo     Backend  : http://localhost:3000 (Node.js + Express)
echo     Frontend : http://localhost:5173 (React + Vite)
echo ===============================================================================
echo.

call npm run dev
if errorlevel 1 (
    echo.
    echo [THONG BAO] Ung dung da dung hoac xay ra loi.
    pause
)
