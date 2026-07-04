@echo off
chcp 65001 >nul 2>&1
title O---O
cd /d "%~dp0"

echo ========================================
echo            O---O
echo ========================================
echo.

REM ---- Python ----
set "PY="

if exist ".venv\Scripts\python.exe" (
    set "PY=.venv\Scripts\python.exe"
    goto :found
)

py -3 --version >nul 2>&1
if %errorlevel%==0 (
    set "PY=py -3"
    goto :found
)

python --version >nul 2>&1
if %errorlevel%==0 (
    set "PY=python"
    goto :found
)

echo [ERROR] Python not found. Please install Python 3.10+
echo Download: https://www.python.org/downloads/
echo.
pause
exit /b 1

:found
echo [1/3] Python: %PY%
echo.

REM ---- pygame ----
%PY% -c "import pygame" >nul 2>&1
if %errorlevel%==0 goto :pygame_ok

echo [2/3] pygame not found, installing...
%PY% -m pip install pygame
if %errorlevel%==0 goto :pygame_ok

echo [ERROR] pygame install failed. Run manually: pip install pygame
echo.
pause
exit /b 1

:pygame_ok
echo [2/3] pygame OK
echo.
echo [3/3] Starting game!
echo.
echo ========================================
echo   SPACE = switch anchor    R = restart
echo   ESC = quit
echo ========================================
echo.

%PY% main.py

if %errorlevel% neq 0 (
    echo.
    echo [!] Game exited with code %errorlevel%
    echo.
    pause
)
