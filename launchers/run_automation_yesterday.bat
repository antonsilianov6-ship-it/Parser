@echo off
chcp 65001 > nul
REM ============================================================
REM NotebookLM Telegram Automation - Quick Launcher (Yesterday)
REM Быстрый запуск анализа за вчерашний день
REM ============================================================

echo.
echo ============================================================
echo   NotebookLM Telegram Automation - Yesterday Analysis
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
python automation.py --mode manual --yesterday
cd launchers
call ..\venv\Scripts\deactivate.bat 2>nul

pause
exit /b 0
