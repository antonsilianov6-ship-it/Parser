# AllInclusiveParser - PowerShell Launcher
# Кодировка: UTF-8

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$Host.UI.RawUI.WindowTitle = "AllInclusiveParser - Лаунчер"

function Show-Menu {
    Clear-Host
    Write-Host "===================================================" -ForegroundColor Green
    Write-Host "            AllInclusiveParser v1.0.0" -ForegroundColor Cyan
    Write-Host "            Универсальный парсер для Telegram" -ForegroundColor Cyan
    Write-Host "===================================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "  [1] Запустить парсер" -ForegroundColor Yellow
    Write-Host "  [2] Запустить авторизацию в Telegram" -ForegroundColor Yellow
    Write-Host "  [3] Исправить кодировку файлов проекта" -ForegroundColor Yellow
    Write-Host "  [4] Открыть справку" -ForegroundColor Yellow
    Write-Host "  [0] Выход" -ForegroundColor Red
    Write-Host ""
    Write-Host "===================================================" -ForegroundColor Green
    Write-Host ""
}

function Start-Parser {
    Clear-Host
    Write-Host "Запуск парсера..." -ForegroundColor Cyan
    Write-Host ""
    
    # Проверка виртуального окружения
    if (-not (Test-Path "venv\Scripts\python.exe")) {
        Write-Host "ОШИБКА: Виртуальное окружение не найдено!" -ForegroundColor Red
        Write-Host "Создайте виртуальное окружение командой: python -m venv venv" -ForegroundColor Yellow
        pause
        return
    }
    
    # Проверка сессии Telegram
    if (-not (Test-Path "sessions\telegram_session.session")) {
        Write-Host "Сессия Telegram не найдена!" -ForegroundColor Yellow
        Write-Host "Перед использованием парсера необходимо авторизоваться в Telegram." -ForegroundColor Yellow
        $response = Read-Host "Запустить авторизацию сейчас? (Y/N)"
        if ($response -eq "Y" -or $response -eq "y") {
            Start-Auth
            return
        }
    }
    
    Write-Host ""
    Write-Host "Доступные режимы:" -ForegroundColor Cyan
    Write-Host "  [1] Парсинг каналов (по умолчанию)"
    Write-Host "  [2] Экспорт данных"
    Write-Host "  [3] Статистика"
    Write-Host "  [4] Планировщик"
    Write-Host ""
    
    $mode = Read-Host "Выберите режим (1-4, Enter для режима по умолчанию)"
    
    Write-Host ""
    switch ($mode) {
        "2" {
            Write-Host "Выберите формат экспорта:" -ForegroundColor Cyan
            Write-Host "  [1] CSV"
            Write-Host "  [2] JSON"
            Write-Host "  [3] XML"
            Write-Host ""
            $format = Read-Host "Выберите формат (1-3)"
            
            $exportFormat = "csv"
            if ($format -eq "2") { $exportFormat = "json" }
            elseif ($format -eq "3") { $exportFormat = "xml" }
            
            Write-Host ""
            Write-Host "===============================================" -ForegroundColor Green
            Write-Host "  Экспорт данных с подробными логами" -ForegroundColor Cyan
            Write-Host "===============================================" -ForegroundColor Green
            Write-Host ""
            & "venv\Scripts\python.exe" main.py --mode export --format $exportFormat --verbose
        }
        "3" {
            Write-Host ""
            Write-Host "===============================================" -ForegroundColor Green
            Write-Host "  Получение статистики с подробными логами" -ForegroundColor Cyan
            Write-Host "===============================================" -ForegroundColor Green
            Write-Host ""
            & "venv\Scripts\python.exe" main.py --mode stats --verbose
        }
        "4" {
            Write-Host ""
            Write-Host "===============================================" -ForegroundColor Green
            Write-Host "  Запуск планировщика с подробными логами" -ForegroundColor Cyan
            Write-Host "===============================================" -ForegroundColor Green
            Write-Host "  Для остановки нажмите Ctrl+C" -ForegroundColor Yellow
            Write-Host ""
            & "venv\Scripts\python.exe" main.py --mode schedule --verbose
        }
        default {
            Write-Host ""
            Write-Host "===============================================" -ForegroundColor Green
            Write-Host "  Запуск режима парсинга с подробными логами" -ForegroundColor Cyan
            Write-Host "===============================================" -ForegroundColor Green
            Write-Host "  Для остановки нажмите Ctrl+C" -ForegroundColor Yellow
            Write-Host ""
            & "venv\Scripts\python.exe" main.py --mode parse --verbose
        }
    }
    
    Write-Host ""
    Write-Host "Работа завершена." -ForegroundColor Green
    pause
}

function Start-Auth {
    Clear-Host
    Write-Host "Запуск авторизации в Telegram..." -ForegroundColor Cyan
    
    if (-not (Test-Path "venv\Scripts\python.exe")) {
        Write-Host "ОШИБКА: Виртуальное окружение не найдено!" -ForegroundColor Red
        Write-Host "Создайте виртуальное окружение командой: python -m venv venv" -ForegroundColor Yellow
        pause
        return
    }
    
    & "venv\Scripts\python.exe" scripts/auth_telegram.py
    pause
}

function Fix-Encoding {
    Clear-Host
    Write-Host "Исправление кодировки файлов проекта..." -ForegroundColor Cyan
    
    if (-not (Test-Path "venv\Scripts\python.exe")) {
        Write-Host "ОШИБКА: Виртуальное окружение не найдено!" -ForegroundColor Red
        pause
        return
    }
    
    & "venv\Scripts\python.exe" scripts/fix_encoding.py
    pause
}

function Show-Help {
    Clear-Host
    Write-Host ""
    Write-Host "===================================================" -ForegroundColor Green
    Write-Host "                    СПРАВКА" -ForegroundColor Cyan
    Write-Host "===================================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "  Запуск парсера - Запуск парсера для сбора сообщений"
    Write-Host "  из Telegram каналов."
    Write-Host ""
    Write-Host "  Авторизация - Необходима для первого запуска или"
    Write-Host "  при изменении учетных данных Telegram."
    Write-Host ""
    Write-Host "  Исправление кодировки - Утилита для исправления"
    Write-Host "  проблем с кодировкой файлов проекта."
    Write-Host ""
    Write-Host "===================================================" -ForegroundColor Green
    Write-Host ""
    pause
}

# Главный цикл
while ($true) {
    Show-Menu
    $choice = Read-Host "Выберите действие (0-4)"
    
    switch ($choice) {
        "1" { Start-Parser }
        "2" { Start-Auth }
        "3" { Fix-Encoding }
        "4" { Show-Help }
        "0" {
            Clear-Host
            Write-Host "Выход из программы..." -ForegroundColor Yellow
            Start-Sleep -Seconds 1
            exit
        }
        default {
            Write-Host "Неверный выбор. Попробуйте снова." -ForegroundColor Red
            Start-Sleep -Seconds 1
        }
    }
}
