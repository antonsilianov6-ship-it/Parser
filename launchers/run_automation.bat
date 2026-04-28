@echo off
chcp 65001 > nul
REM ============================================================
REM NotebookLM Telegram Automation - Launcher для Windows
REM Автоматизация создания аналитических сводок
REM ============================================================

setlocal enabledelayedexpansion

REM Цвета для вывода (если поддерживается)
set "GREEN=[92m"
set "RED=[91m"
set "YELLOW=[93m"
set "BLUE=[94m"
set "RESET=[0m"

echo.
echo ============================================================
echo   NotebookLM Telegram Automation
echo   Автоматизация аналитических сводок
echo ============================================================
echo.

REM Проверка наличия виртуального окружения
if not exist "..\venv\Scripts\activate.bat" (
    echo %RED%[ОШИБКА]%RESET% Виртуальное окружение не найдено!
    echo.
    echo Пожалуйста, создайте виртуальное окружение:
    echo   python -m venv venv
    echo   venv\Scripts\activate
    echo   pip install -r requirements.txt
    echo.
    pause
    exit /b 1
)

REM Активация виртуального окружения
echo %BLUE%[INFO]%RESET% Активация виртуального окружения...
call ..\venv\Scripts\activate.bat

if errorlevel 1 (
    echo %RED%[ОШИБКА]%RESET% Не удалось активировать виртуальное окружение
    pause
    exit /b 1
)

echo %GREEN%[OK]%RESET% Виртуальное окружение активировано
echo.

REM Проверка наличия automation.py
if not exist "..\automation.py" (
    echo %RED%[ОШИБКА]%RESET% Файл automation.py не найден!
    pause
    exit /b 1
)

REM Проверка наличия config.json
if not exist "..\config.json" (
    echo %YELLOW%[ПРЕДУПРЕЖДЕНИЕ]%RESET% Файл config.json не найден!
    echo Используйте config.example.json как шаблон
    pause
    exit /b 1
)

REM Парсинг аргументов командной строки
set "MODE=scheduled"
set "EXTRA_ARGS="

:parse_args
if "%~1"=="" goto end_parse_args
if /i "%~1"=="--mode" (
    set "MODE=%~2"
    shift
    shift
    goto parse_args
)
if /i "%~1"=="--manual" (
    set "MODE=manual"
    shift
    goto parse_args
)
if /i "%~1"=="--scheduled" (
    set "MODE=scheduled"
    shift
    goto parse_args
)
if /i "%~1"=="--yesterday" (
    set "EXTRA_ARGS=!EXTRA_ARGS! --yesterday"
    shift
    goto parse_args
)
if /i "%~1"=="--verbose" (
    set "EXTRA_ARGS=!EXTRA_ARGS! --verbose"
    shift
    goto parse_args
)
if /i "%~1"=="--days" (
    set "EXTRA_ARGS=!EXTRA_ARGS! --days %~2"
    shift
    shift
    goto parse_args
)
if /i "%~1"=="--start-date" (
    set "EXTRA_ARGS=!EXTRA_ARGS! --start-date %~2"
    shift
    shift
    goto parse_args
)
if /i "%~1"=="--end-date" (
    set "EXTRA_ARGS=!EXTRA_ARGS! --end-date %~2"
    shift
    shift
    goto parse_args
)
if /i "%~1"=="--help" (
    cd ..
    python automation.py --help
    cd launchers
    pause
    exit /b 0
)
REM Неизвестный аргумент - передаем как есть
set "EXTRA_ARGS=!EXTRA_ARGS! %~1"
shift
goto parse_args

:end_parse_args

REM Вывод информации о режиме запуска
echo ============================================================
if /i "%MODE%"=="manual" (
    echo   Режим: MANUAL ^(ручной запуск^)
    echo   Аргументы: %EXTRA_ARGS%
) else (
    echo   Режим: SCHEDULED ^(автоматический по расписанию^)
)
echo ============================================================
echo.

REM Запуск автоматизации
echo %BLUE%[INFO]%RESET% Запуск автоматизации...
echo.

cd ..
python automation.py --mode %MODE% %EXTRA_ARGS%
set ERRORLEVEL_BACKUP=%ERRORLEVEL%
cd launchers

REM Проверка кода возврата
if %ERRORLEVEL_BACKUP% neq 0 (
    echo.
    echo %RED%[ОШИБКА]%RESET% Автоматизация завершилась с ошибкой
    echo Проверьте логи в директории logs/
    echo.
    pause
    exit /b 1
) else (
    echo.
    echo %GREEN%[OK]%RESET% Автоматизация завершена успешно
    echo.
)

REM Деактивация виртуального окружения
call ..\venv\Scripts\deactivate.bat 2>nul

pause
exit /b 0
