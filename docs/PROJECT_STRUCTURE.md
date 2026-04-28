# Структура проекта AllInclusiveParser

## Корневая директория

```
AllInclusiveParser/
├── main.py                          # Основная точка входа - парсер Telegram
├── automation.py                    # Автоматизация NotebookLM + Telegram
├── launcher.bat                     # Интерактивный лаунчер (главный)
├── config.json                      # Основная конфигурация
├── channels.txt                     # Список каналов для парсинга
├── requirements.txt                 # Python зависимости
├── google-credentials.json          # Credentials для Google API
│
├── launchers/                       # Bat-файлы для запуска
│   ├── run.bat                     # Запуск парсера
│   ├── run_automation.bat          # Запуск автоматизации (универсальный)
│   ├── run_automation_yesterday.bat # Запуск за вчерашний день
│   ├── run_automation_scheduled.bat # Запуск планировщика
│   ├── setup_enhanced.bat          # Установка и настройка
│   └── README.md                   # Документация лаунчеров
│
├── scripts/                         # Вспомогательные скрипты
│   ├── auth_telegram.py            # Авторизация в Telegram
│   ├── check_config.py             # Проверка конфигурации
│   ├── fix_encoding.py             # Исправление кодировки
│   └── README.md                   # Документация скриптов
│
├── docs/                           # Документация проекта
│   └── PROJECT_STRUCTURE.md        # Структура проекта (этот файл)
│
├── src/                            # Исходный код приложения
│   ├── automation/                 # Модуль автоматизации
│   ├── cache/                      # Модуль кэширования
│   ├── core/                       # Ядро парсера
│   ├── database/                   # Работа с БД
│   ├── export/                     # Экспорт данных
│   ├── notebooklm/                 # Интеграция с NotebookLM
│   ├── telegram/                   # Работа с Telegram API
│   └── utils/                      # Утилиты
│
├── config/                         # Конфигурационные файлы
│   ├── prompts.json               # Промпты для NotebookLM
│   └── CONFIG_README.md           # Документация конфигурации
│
├── data/                           # База данных
│   └── parser.db                  # SQLite база данных
│
├── logs/                           # Логи приложения
├── sessions/                       # Telegram сессии
├── cache/                          # Кэш данных
├── exports/                        # Экспортированные данные
│
└── .kiro/                          # Конфигурация Kiro
    ├── specs/                      # Спецификации проекта
    └── steering/                   # Правила разработки
```

## Основные точки входа

### 1. main.py
Универсальный парсер Telegram каналов с поддержкой различных режимов:
- **parse** - парсинг каналов
- **export** - экспорт данных (CSV/JSON/XML)
- **stats** - статистика
- **schedule** - планировщик

**Использование:**
```bash
python main.py --mode parse
python main.py --mode export --format csv
python main.py --mode stats
```

### 2. automation.py
Автоматизация создания аналитических сводок через NotebookLM с отправкой в Telegram.

**Режимы:**
- **manual** - ручной запуск с указанием дат
- **scheduled** - автоматический запуск по расписанию

**Использование:**
```bash
# Manual режим
python automation.py --mode manual --yesterday
python automation.py --mode manual --days 7
python automation.py --mode manual --start-date 2024-04-20 --end-date 2024-04-21

# Scheduled режим
python automation.py --mode scheduled
```

### 3. launcher.bat
Интерактивный лаунчер с меню для удобного запуска всех функций.

## Модули src/

### automation/
Оркестрация автоматизации NotebookLM + Telegram:
- `orchestrator.py` - главный оркестратор
- `models.py` - модели данных
- `config_validator.py` - валидация конфигурации

### cache/
Кэширование данных для оптимизации:
- `cache_manager.py` - управление кэшем

### core/
Ядро парсера:
- `unified_parser.py` - унифицированный парсер

### database/
Работа с SQLite базой данных:
- `models.py` - модели БД и ORM

### export/
Экспорт данных в различные форматы:
- `excel.py` - экспорт в CSV/Excel
- `google_docs.py` - экспорт в Google Docs
- `advanced_export.py` - расширенный экспорт (JSON/XML)

### notebooklm/
Интеграция с NotebookLM:
- `client.py` - клиент NotebookLM
- `file_manager.py` - управление файлами
- `summary_generator.py` - генерация сводок

### telegram/
Работа с Telegram API:
- `auth.py` - авторизация
- `message_fetcher.py` - получение сообщений
- `comment_fetcher.py` - получение комментариев
- `telegram_sender.py` - отправка сообщений
- `connection_manager.py` - управление соединениями
- `link_formatter.py` - форматирование ссылок

### utils/
Утилиты:
- `logger.py` - логирование
- `error_handler.py` - обработка ошибок
- `retry.py` - повторные попытки
- `date_utils.py` - работа с датами
- `channels_loader.py` - загрузка списка каналов
- `notifications.py` - уведомления
- `scheduler.py` - планировщик задач
- `encryption.py` - шифрование

## Вспомогательные скрипты (scripts/)

### auth_telegram.py
Авторизация в Telegram API. Создает сессию в `sessions/telegram_session.session`.

### check_config.py
Проверяет корректность конфигурации перед запуском.

### fix_encoding.py
Исправляет кодировку файлов проекта в UTF-8.

## Конфигурация

### config.json
Основная конфигурация проекта:
- `TELEGRAM` - настройки Telegram API
- `GOOGLE` - настройки Google API
- `PARSER` - настройки парсера
- `DATABASE` - настройки БД
- `NOTEBOOKLM` - настройки NotebookLM
- `AUTOMATION` - настройки автоматизации
- `NOTIFICATIONS` - настройки уведомлений
- `SCHEDULER` - настройки планировщика

### config/prompts.json
Промпты для генерации сводок в NotebookLM.

### channels.txt
Список каналов для парсинга (один канал на строку).

## Данные

### data/parser.db
SQLite база данных с таблицами:
- `messages` - сообщения из каналов
- `channels` - информация о каналах
- `comments` - комментарии к сообщениям

### logs/
Логи приложения с ротацией.

### sessions/
Telegram сессии для авторизации.

### cache/
Кэш данных для оптимизации.

### exports/
Экспортированные данные в различных форматах.

## Тестирование

Все модули содержат unit-тесты:
- `test_*.py` - обычные unit-тесты
- `test_*_properties.py` - property-based тесты (Hypothesis)

**Запуск тестов:**
```bash
# Все тесты
pytest

# Конкретный модуль
pytest src/automation/test_orchestrator.py

# С покрытием
pytest --cov=src
```

## Быстрый старт

1. **Установка:**
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

4. **Запуск:**
   ```bash
   launcher.bat
   ```

## Разработка

### Правила разработки
См. `.kiro/steering/project-rules.md`

### Спецификации
См. `.kiro/specs/`

### Добавление нового модуля
1. Создайте модуль в `src/`
2. Добавьте тесты `test_*.py`
3. Обновите документацию
4. Запустите тесты

## Лицензия

Проект использует следующие зависимости:
- Telethon - Telegram API
- NotebookLM-py - NotebookLM интеграция
- Google API - Google Docs экспорт
- Hypothesis - Property-based тестирование
