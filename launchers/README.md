# Лаунчеры и скрипты запуска

Эта папка содержит bat-файлы для запуска различных режимов работы AllInclusiveParser.

## Файлы

### setup_enhanced.bat
Скрипт установки и настройки проекта.

**Что делает:**
- Проверяет наличие Python
- Создает виртуальное окружение
- Устанавливает зависимости из requirements.txt
- Создает необходимые директории (logs, sessions, cache, exports, data)
- Создает базовый config.json (если отсутствует)
- Создает channels.txt (если отсутствует)

**Использование:**
```bash
launchers\setup_enhanced.bat
```

**Когда использовать:**
- При первой установке проекта
- После клонирования репозитория
- При переустановке зависимостей

---

### run.bat
Основной лаунчер для запуска парсера Telegram каналов.

**Режимы работы:**
1. **Парсинг каналов** - сбор сообщений из Telegram каналов
2. **Экспорт данных** - экспорт в CSV/JSON/XML
3. **Статистика** - просмотр статистики по собранным данным
4. **Планировщик** - автоматический запуск по расписанию

**Использование:**
```bash
launchers\run.bat
```

**Что делает:**
- Проверяет наличие Python и виртуального окружения
- Активирует виртуальное окружение
- Проверяет наличие Telegram сессии (предлагает авторизацию)
- Запускает main.py с выбранным режимом

---

### run_automation.bat
Универсальный лаунчер для NotebookLM Telegram Automation.

**Режимы:**
- **manual** - ручной запуск с указанием дат
- **scheduled** - автоматический запуск по расписанию

**Использование:**
```bash
# Manual режим - вчерашний день
launchers\run_automation.bat --mode manual --yesterday

# Manual режим - последние 7 дней
launchers\run_automation.bat --mode manual --days 7

# Manual режим - указанный диапазон
launchers\run_automation.bat --mode manual --start-date 2024-04-20 --end-date 2024-04-21

# Scheduled режим
launchers\run_automation.bat --mode scheduled

# С подробными логами
launchers\run_automation.bat --mode manual --yesterday --verbose
```

**Параметры:**
- `--mode manual|scheduled` - режим работы
- `--yesterday` - анализ вчерашнего дня
- `--days N` - анализ последних N дней
- `--start-date YYYY-MM-DD` - начальная дата
- `--end-date YYYY-MM-DD` - конечная дата
- `--verbose` - подробные логи
- `--help` - справка

---

### run_automation_yesterday.bat
Быстрый запуск анализа за вчерашний день.

**Использование:**
```bash
launchers\run_automation_yesterday.bat
```

**Эквивалентно:**
```bash
launchers\run_automation.bat --mode manual --yesterday
```

---

### run_automation_scheduled.bat
Быстрый запуск в режиме планировщика.

**Использование:**
```bash
launchers\run_automation_scheduled.bat
```

**Эквивалентно:**
```bash
launchers\run_automation.bat --mode scheduled
```

**Логика расписания:**
- **Понедельник**: анализ пятницы-воскресенья (последние 3 дня)
- **Вторник-пятница**: анализ предыдущего дня
- **Суббота-воскресенье**: автоматизация не запускается

---

## Общие примечания

### Виртуальное окружение
Все скрипты автоматически активируют виртуальное окружение перед запуском. Если виртуальное окружение не найдено, скрипт выдаст ошибку.

### Пути
Все скрипты должны запускаться из корневой директории проекта или напрямую:
```bash
# Правильно
launchers\run.bat
launchers\run_automation.bat

# Также правильно (из корня)
cd launchers
run.bat
```

### Логи
Все логи сохраняются в папке `logs/` в корне проекта.

### Ошибки
При возникновении ошибок:
1. Проверьте наличие виртуального окружения
2. Проверьте config.json
3. Проверьте логи в папке logs/
4. Убедитесь, что все зависимости установлены

## Быстрый старт

1. **Первая установка:**
   ```bash
   launchers\setup_enhanced.bat
   ```

2. **Настройка:**
   - Отредактируйте `config.json` (API ключи)
   - Добавьте каналы в `channels.txt`

3. **Авторизация:**
   ```bash
   python scripts\auth_telegram.py
   ```

4. **Запуск парсера:**
   ```bash
   launchers\run.bat
   ```

5. **Запуск автоматизации:**
   ```bash
   launchers\run_automation_yesterday.bat
   ```

## Автоматизация через Task Scheduler

Для автоматического запуска по расписанию можно использовать Windows Task Scheduler:

1. Откройте Task Scheduler
2. Создайте новую задачу
3. В качестве действия укажите:
   ```
   Program: cmd.exe
   Arguments: /c "cd /d D:\path\to\project && launchers\run_automation_scheduled.bat"
   ```
4. Настройте расписание (например, ежедневно в 09:00)

## Troubleshooting

### Ошибка "Виртуальное окружение не найдено"
Запустите `launchers\setup_enhanced.bat`

### Ошибка "Python не найден"
Установите Python 3.8+ с https://python.org

### Ошибка "Сессия Telegram не найдена"
Запустите `python scripts\auth_telegram.py`

### Ошибка "config.json не найден"
Запустите `launchers\setup_enhanced.bat` или создайте config.json вручную
