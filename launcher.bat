@echo off
chcp 65001 > nul
color 0A
title AllInclusiveParser - Лаунчер

:menu
cls
echo ===================================================
echo             AllInclusiveParser v1.0.0
echo             Универсальный парсер для Telegram
echo ===================================================
echo.
echo  [1] Запустить парсер
echo  [2] Запустить авторизацию в Telegram
echo  [3] Исправить кодировку файлов проекта
echo  [4] Открыть справку
echo  [0] Выход
echo.
echo ===================================================
set /p choice="Выберите действие (0-4): "

if "%choice%"=="1" goto console
if "%choice%"=="2" goto auth
if "%choice%"=="3" goto fix_encoding
if "%choice%"=="4" goto help
if "%choice%"=="0" goto exit
goto menu

:console
cls
echo Запуск парсера...
echo.
call launchers\run.bat
echo.
echo Нажмите любую клавишу для возврата в меню...
pause >nul
goto menu

:auth
cls
echo Запуск авторизации в Telegram...
venv\Scripts\python.exe scripts/auth_telegram.py
pause
goto menu

:fix_encoding
cls
echo Исправление кодировки файлов проекта...
venv\Scripts\python.exe scripts/fix_encoding.py
pause
goto menu

:help
cls
echo.
echo ===================================================
echo                     СПРАВКА
echo ===================================================
echo.
echo  Запуск парсера - Запуск парсера для сбора сообщений
echo  из Telegram каналов.
echo.
echo  Авторизация - Необходима для первого запуска или
echo  при изменении учетных данных Telegram.
echo.
echo  Исправление кодировки - Утилита для исправления
echo  проблем с кодировкой файлов проекта.
echo.
echo ===================================================
echo.
pause
goto menu

:exit
cls
echo Выход из программы...
timeout /t 2 >nul
exit
