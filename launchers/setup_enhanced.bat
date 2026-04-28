@echo off
chcp 65001 > nul
color 0A
title AllInclusiveParser Enhanced Setup

echo ===================================================
echo     AllInclusiveParser Enhanced v2.0 Setup
echo ===================================================
echo.

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found!
    echo Install Python 3.8+ from: https://python.org
    pause
    exit /b 1
)
echo Python found.

REM Create virtual environment
echo.
echo Creating virtual environment...
cd ..
if not exist venv (
    python -m venv venv
    if errorlevel 1 (
        echo ERROR: Failed to create virtual environment!
        cd launchers
        pause
        exit /b 1
    )
    echo Virtual environment created.
) else (
    echo Virtual environment already exists.
)

REM Activate virtual environment
call venv\Scripts\activate.bat

REM Update pip
echo.
echo Updating pip...
python -m pip install --upgrade pip

REM Install dependencies
echo.
echo Installing dependencies...
pip install -r requirements.txt
if errorlevel 1 (
    echo ERROR: Failed to install dependencies!
    pause
    exit /b 1
)
echo Dependencies installed.

REM Create directories
echo.
echo Creating directories...
mkdir logs 2>nul
mkdir sessions 2>nul
mkdir cache 2>nul
mkdir exports 2>nul
mkdir data 2>nul
echo Directories created.

REM Check configuration
echo.
echo Checking configuration...
if not exist config.json (
    echo Creating basic configuration...
    python -c "import json; config={'TELEGRAM':{'API_ID':0,'API_HASH':'','MAX_CONCURRENT_CONNECTIONS':3,'DELAY_BETWEEN_CHANNELS':2},'GOOGLE':{'DOC_ID':''},'PARSER':{'CHECK_INTERVAL':3600,'DAYS_FOR_EXPORT':7,'DATE_RANGE_ENABLED':False,'START_DATE':'','END_DATE':'','FETCH_COMMENTS':True,'FETCH_PREVIOUS_POSTS':False},'DATABASE':{'DB_PATH':'data/parser.db','BACKUP_ENABLED':True,'BACKUP_INTERVAL':24},'NOTIFICATIONS':{'ENABLED':False,'WEBHOOKS':{},'EMAIL_ENABLED':False},'SCHEDULER':{'ENABLED':False,'TASKS':[]}}; open('config.json','w').write(json.dumps(config,indent=2))"
    echo Basic configuration created.
) else (
    echo Configuration found.
)

REM Create channels file
if not exist channels.txt (
    echo Creating channels file...
    (
        echo # Channel list for parsing ^(one per line^)
        echo # Lines starting with # are comments
        echo # Examples:
        echo # @channel_name
        echo # https://t.me/channel_name
    ) > channels.txt
    echo Channels file created.
)

echo.
echo Setup completed successfully!
echo.
echo Next steps:
echo   1. Configure API keys in config.json
echo   2. Add channels to channels.txt
echo   3. Run authorization: python scripts/auth_telegram.py
echo   4. Start parser: launcher.bat
echo.
echo New features v2.0:
echo   - SQLite database
echo   - Interactive dashboard
echo   - Auto retry system
echo   - Notifications system
echo   - Task scheduler
echo   - Advanced export
echo   - Data encryption
echo.
cd launchers
pause