@echo off
chcp 65001 > nul
echo ===============================================
echo    AllInclusiveParser - Консольный режим
echo ===============================================
echo.

REM Сохраняем текущую директорию и переходим в корень проекта
set SCRIPT_DIR=%~dp0
cd /d "%SCRIPT_DIR%.."

REM Проверяем наличие Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ОШИБКА: Python не найден!
    echo Установите Python 3.8+ с официального сайта: https://python.org
    pause
    exit /b 1
)
echo Python найден.

REM Проверяем наличие виртуального окружения
if not exist "venv\Scripts\activate.bat" (
    echo Виртуальное окружение не найдено. Создаем...
    python -m venv venv
    call venv\Scripts\activate.bat
    echo Устанавливаем зависимости...
    pip install -r requirements.txt
) else (
    call venv\Scripts\activate.bat
)

REM Проверяем наличие сессии Telegram
if not exist "sessions\telegram_session.session" (
    echo.
    echo ===============================================
    echo   Сессия Telegram не найдена!
    echo ===============================================
    echo.
    echo Перед использованием парсера необходимо
    echo авторизоваться в Telegram.
    echo.
    choice /C YN /M "Запустить авторизацию сейчас?"
    if errorlevel 2 goto run_parser
    if errorlevel 1 goto auth
) else (
    echo Сессия Telegram найдена.
)

goto run_parser

:auth
echo.
echo Запуск авторизации в Telegram...
venv\Scripts\python.exe scripts/auth_telegram.py
if errorlevel 1 (
    echo Ошибка при авторизации в Telegram.
    echo Попробуйте запустить scripts/auth_telegram.py вручную.
    pause
    exit /b 1
)
echo Авторизация успешно завершена!
echo.

:run_parser
echo.
echo ===============================================
echo   Запуск парсера в консольном режиме
echo ===============================================
echo.
echo ВАЖНО: Все режимы запускаются с подробными логами
echo для отслеживания процесса работы парсера.
echo.
echo Доступные режимы:
echo   [1] Парсинг каналов (по умолчанию)
echo   [2] Экспорт данных
echo   [3] Статистика
echo   [4] Планировщик
echo.
set /p mode_choice="Выберите режим (1-4, Enter для режима по умолчанию): "

if "%mode_choice%"=="2" goto export_mode
if "%mode_choice%"=="3" goto stats_mode
if "%mode_choice%"=="4" goto schedule_mode

:parse_mode
echo.
echo ===============================================
echo   Запуск режима парсинга с подробными логами
echo ===============================================
echo.
venv\Scripts\python.exe main.py --mode parse --verbose
goto end_parser

:export_mode
echo.
echo Выберите формат экспорта:
echo   [1] CSV
echo   [2] JSON
echo   [3] XML
echo.
set /p format_choice="Выберите формат (1-3): "

echo.
echo ===============================================
echo   Экспорт данных с подробными логами
echo ===============================================
echo.
if "%format_choice%"=="2" (
    venv\Scripts\python.exe main.py --mode export --format json --verbose
) else if "%format_choice%"=="3" (
    venv\Scripts\python.exe main.py --mode export --format xml --verbose
) else (
    venv\Scripts\python.exe main.py --mode export --format csv --verbose
)
goto end_parser

:stats_mode
echo.
echo ===============================================
echo   Получение статистики с подробными логами
echo ===============================================
echo.
venv\Scripts\python.exe main.py --mode stats --verbose
goto end_parser

:schedule_mode
echo.
echo ===============================================
echo   Запуск планировщика с подробными логами
echo ===============================================
echo   Для остановки нажмите Ctrl+C
echo.
venv\Scripts\python.exe main.py --mode schedule --verbose
goto end_parser

:end_parser
echo.
echo ===============================================
echo   Работа завершена
echo ===============================================
pause
