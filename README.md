# AllInclusiveParser

Универсальный парсер для Telegram каналов с автоматизацией аналитических сводок через NotebookLM.

## 🚀 Возможности

### Парсинг Telegram
- ✅ Сбор сообщений из публичных Telegram каналов
- ✅ Получение комментариев к постам
- ✅ Поддержка прокси (MTProto)
- ✅ SQLite база данных для хранения
- ✅ Кэширование для оптимизации
- ✅ Обработка ошибок и автоматические повторы

### Автоматизация NotebookLM
- ✅ Автоматическая генерация аналитических сводок
- ✅ Негативная и позитивная аналитика
- ✅ Отправка результатов в Telegram
- ✅ Планировщик для автоматического запуска
- ✅ Настраиваемые промпты

### Экспорт данных
- ✅ CSV, JSON, XML форматы
- ✅ Экспорт в Google Docs
- ✅ Фильтрация и группировка данных
- ✅ Статистика и отчеты

## 📋 Требования

- Python 3.8+
- Windows (для bat-файлов) или Linux/Mac
- Telegram API ключи (API_ID, API_HASH)
- NotebookLM аккаунт (для автоматизации)

## 🔧 Установка

### 1. Клонирование репозитория
```bash
git clone <repository-url>
cd AllInclusiveParser
```

### 2. Запуск установки
```bash
launchers\setup_enhanced.bat
```

Скрипт автоматически:
- Создаст виртуальное окружение
- Установит все зависимости
- Создаст необходимые директории
- Создаст базовые конфигурационные файлы

### 3. Настройка

#### config.json
Отредактируйте `config.json` и укажите:
```json
{
  "TELEGRAM": {
    "API_ID": "ваш_api_id",
    "API_HASH": "ваш_api_hash"
  },
  "NOTEBOOKLM": {
    "email": "ваш_email",
    "password": "ваш_пароль"
  },
  "AUTOMATION": {
    "target_chat_id": "@ваш_канал"
  }
}
```

**Получение Telegram API ключей:**
1. Перейдите на https://my.telegram.org
2. Войдите с вашим номером телефона
3. Перейдите в "API development tools"
4. Создайте приложение и получите API_ID и API_HASH

#### channels.txt
Добавьте каналы для парсинга (один на строку):
```
@channel_name
https://t.me/another_channel
```

### 4. Авторизация в Telegram
```bash
python scripts\auth_telegram.py
```

Следуйте инструкциям для авторизации через номер телефона.

## 🎯 Использование

### Интерактивный лаунчер
```bash
launcher.bat
```

Откроется меню с опциями:
1. Запустить парсер
2. Запустить авторизацию в Telegram
3. Исправить кодировку файлов проекта
4. Открыть справку

### Парсинг каналов

#### Через лаунчер
```bash
launchers\run.bat
```

#### Напрямую
```bash
# Парсинг всех каналов
python main.py --mode parse

# Парсинг конкретного канала
python main.py --mode parse --channel @channelname

# Экспорт данных
python main.py --mode export --format csv

# Статистика
python main.py --mode stats

# Планировщик
python main.py --mode schedule
```

### Автоматизация NotebookLM

#### Быстрый запуск

**Анализ за вчерашний день:**
```bash
launchers\run_automation_yesterday.bat
```

**Режим планировщика:**
```bash
launchers\run_automation_scheduled.bat
```

#### Расширенное использование

**Manual режим:**
```bash
# Вчерашний день
launchers\run_automation.bat --mode manual --yesterday

# Последние 7 дней
launchers\run_automation.bat --mode manual --days 7

# Указанный диапазон
launchers\run_automation.bat --mode manual --start-date 2024-04-20 --end-date 2024-04-21

# С подробными логами
launchers\run_automation.bat --mode manual --yesterday --verbose
```

**Scheduled режим:**
```bash
launchers\run_automation.bat --mode scheduled
```

Логика расписания:
- **Понедельник**: анализ пятницы-воскресенья (3 дня)
- **Вторник-пятница**: анализ предыдущего дня
- **Суббота-воскресенье**: автоматизация не запускается

## 📁 Структура проекта

```
AllInclusiveParser/
├── main.py                 # Основной парсер
├── automation.py           # Автоматизация NotebookLM
├── launcher.bat            # Главный лаунчер
├── config.json             # Конфигурация
├── channels.txt            # Список каналов
│
├── launchers/              # Скрипты запуска
├── scripts/                # Вспомогательные скрипты
├── docs/                   # Документация
├── src/                    # Исходный код
├── config/                 # Конфигурационные файлы
├── data/                   # База данных
├── logs/                   # Логи
├── sessions/               # Telegram сессии
├── cache/                  # Кэш
└── exports/                # Экспортированные данные
```

Подробная структура: [docs/PROJECT_STRUCTURE.md](docs/PROJECT_STRUCTURE.md)

## 🔍 Вспомогательные скрипты

### Проверка конфигурации
```bash
python scripts\check_config.py
```

Проверяет корректность всех настроек перед запуском.

### Исправление кодировки
```bash
python scripts\fix_encoding.py
```

Конвертирует все файлы проекта в UTF-8.

## 📊 Примеры использования

### Пример 1: Ежедневный мониторинг каналов
```bash
# Настройте channels.txt с нужными каналами
# Запустите планировщик
python main.py --mode schedule
```

### Пример 2: Разовый анализ за неделю
```bash
launchers\run_automation.bat --mode manual --days 7
```

### Пример 3: Экспорт данных в CSV
```bash
python main.py --mode export --format csv --output exports/report.csv
```

## 🛠️ Разработка

### Запуск тестов
```bash
# Активировать виртуальное окружение
venv\Scripts\activate

# Все тесты
pytest

# Конкретный модуль
pytest src/automation/test_orchestrator.py

# С покрытием
pytest --cov=src
```

### Правила разработки
См. `.kiro/steering/project-rules.md`

### Добавление нового модуля
1. Создайте модуль в `src/`
2. Добавьте тесты `test_*.py`
3. Обновите документацию
4. Запустите тесты

## 📝 Конфигурация

### Основные секции config.json

#### TELEGRAM
Настройки Telegram API:
- `API_ID`, `API_HASH` - ключи API
- `MAX_CONCURRENT_CONNECTIONS` - количество одновременных подключений
- `DELAY_BETWEEN_CHANNELS` - задержка между каналами (сек)
- `PROXY_ENABLED` - использовать прокси
- `PROXY_TYPE`, `PROXY_HOST`, `PROXY_PORT`, `PROXY_SECRET` - настройки прокси

#### PARSER
Настройки парсинга:
- `CHECK_INTERVAL` - интервал проверки (сек)
- `DAYS_FOR_EXPORT` - количество дней для экспорта
- `FETCH_COMMENTS` - получать комментарии
- `MAX_COMMENTS_PER_POST` - максимум комментариев на пост

#### NOTEBOOKLM
Настройки NotebookLM:
- `email`, `password` - учетные данные
- `prompts_config` - путь к файлу промптов
- `timeout` - таймаут операций (сек)
- `max_retries` - максимум повторов

#### AUTOMATION
Настройки автоматизации:
- `enabled` - включить автоматизацию
- `target_chat_id` - ID чата для отправки
- `schedule_enabled` - включить расписание
- `schedule_time` - время запуска
- `schedule_days` - дни недели
- `export_format` - формат экспорта (csv/json)

### Промпты (config/prompts.json)

Настройте промпты для генерации сводок:
```json
{
  "prompts": {
    "negative": {
      "template": "Ваш промпт для негативной аналитики...",
      "required_fields": ["template", "variables"],
      "variables": ["messages"]
    },
    "positive": {
      "template": "Ваш промпт для позитивной аналитики...",
      "required_fields": ["template", "variables"],
      "variables": ["messages"]
    }
  }
}
```

## 🐛 Troubleshooting

### Ошибка "Python не найден"
Установите Python 3.8+ с https://python.org

### Ошибка "Виртуальное окружение не найдено"
Запустите `launchers\setup_enhanced.bat`

### Ошибка "Сессия Telegram не найдена"
Запустите `python scripts\auth_telegram.py`

### Ошибка "API_ID или API_HASH не заданы"
Отредактируйте `config.json` и укажите ваши Telegram API ключи

### Проблемы с кодировкой
Запустите `python scripts\fix_encoding.py`

### Ошибки при парсинге
1. Проверьте логи в `logs/parser.log`
2. Убедитесь, что сессия Telegram активна
3. Проверьте настройки прокси (если используется)
4. Проверьте права доступа к каналам

## 📚 Документация

- [Структура проекта](docs/PROJECT_STRUCTURE.md)
- [Документация лаунчеров](launchers/README.md)
- [Документация скриптов](scripts/README.md)
- [Конфигурация](config/CONFIG_README.md)

## 🔐 Безопасность

- **Не коммитьте** `config.json` с реальными ключами
- **Не коммитьте** `google-credentials.json`
- **Не коммитьте** файлы сессий из `sessions/`
- Используйте `.gitignore` для исключения чувствительных данных

## 📄 Лицензия

Проект использует следующие зависимости:
- Telethon - Telegram API
- NotebookLM-py - NotebookLM интеграция
- Google API - Google Docs экспорт
- Hypothesis - Property-based тестирование

## 🤝 Вклад

Contributions are welcome! Please read the development guidelines in `.kiro/steering/project-rules.md`

## 📞 Поддержка

При возникновении проблем:
1. Проверьте [Troubleshooting](#-troubleshooting)
2. Проверьте логи в `logs/`
3. Запустите `python scripts\check_config.py`
4. Создайте issue с описанием проблемы

---

**Версия:** 2.0  
**Последнее обновление:** Апрель 2026
