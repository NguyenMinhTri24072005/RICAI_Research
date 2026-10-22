@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
title RICE VISION AI - TERMINATE ALL SERVICES
cd /d "%~dp0"

echo ===============================================================================
echo                HE THONG UOC TINH SO LUONG HAT LUA (RICE VISION AI)
echo                         --- TRINH TAT TOAN BO HE THONG ---
echo ===============================================================================
echo.

echo [*] Dang giai phong cac cong mang (8000, 3000, 5173, 8765)...

for %%P in (8000 3000 5173 8765) do (
    echo     Dang kiem tra cong %%P...
    for /f "tokens=5" %%A in ('netstat -aon ^| findstr /r /c:":%%P[ ]"') do (
        set "PID_FOUND=%%A"
        if not "!PID_FOUND!"=="" if not "!PID_FOUND!"=="0" (
            echo         [x] Dang dung PID !PID_FOUND! tai cong %%P...
            taskkill /f /pid !PID_FOUND! >nul 2>&1
        )
    )
)

echo.
echo ===============================================================================
echo [*] DA TAT HOAN TOAN CAC DICH VU CUA HE THONG!
echo     Cac cong mang da duoc giai phong sach se.
echo ===============================================================================
echo.
pause
