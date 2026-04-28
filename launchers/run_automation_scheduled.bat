@echo off
chcp 65001 > nul
REM ============================================================
REM NotebookLM Telegram Automation - Quick Launcher (Scheduled)
REM Быстрый запуск в режиме планировщика
REM ============================================================

echo.
echo ============================================================
echo   NotebookLM Telegram Automation - Scheduled Mode
echo ============================================================
echo.

REM Активация виртуального окружения
if not exist "..\venv\Scripts\activate.bat" (
    echo [ОШИБКА] Виртуальное окружение не найдено!
    pause
    exit /b 1
)

call ..\venv\Scripts\activate.bat
cd ..
python automation.py --mode scheduled
cd launchers
call ..\venv\Scripts\deactivate.bat 2>nul

pause
exit /b 0
