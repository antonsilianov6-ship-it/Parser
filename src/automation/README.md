# Automation Module

Модуль для автоматизации создания аналитических сводок через NotebookLM с отправкой результатов в Telegram.

## Компоненты

### AutomationOrchestrator

Главный оркестратор процесса автоматизации. Координирует все этапы:
1. Экспорт данных из Telegram-парсера
2. Создание ноутбука NotebookLM и загрузка данных
3. Генерация негативных и позитивных аналитических сводок
4. Отправка сводок в Telegram
5. Очистка временных ресурсов

### Модели данных

- **NotebookInfo**: Информация о ноутбуке NotebookLM
- **SummaryResult**: Результат генерации аналитической сводки
- **AutomationStats**: Статистика выполнения автоматизации

## Конфигурация

Добавьте следующие секции в `config.json`:

```json
{
  "NOTEBOOKLM": {
    "email": "your_email@example.com",
    "password": "your_password",
    "prompts_config": "config/prompts.json"
  },
  "AUTOMATION": {
    "target_chat_id": "your_telegram_chat_id",
    "schedule_time": "09:00",
    "timeout": 120,
    "max_retries": 3,
    "export_format": "csv"
  }
}
```

### Параметры конфигурации

#### NOTEBOOKLM
- `email`: Email для входа в NotebookLM
- `password`: Пароль для входа в NotebookLM
- `prompts_config`: Путь к файлу с промптами для анализа

#### AUTOMATION
- `target_chat_id`: ID или username Telegram чата для отправки сводок
- `schedule_time`: Время запуска по расписанию (формат HH:MM)
- `timeout`: Таймаут для запросов к NotebookLM (секунды)
- `max_retries`: Максимальное количество повторных попыток при ошибках
- `export_format`: Формат экспорта данных ('csv' или 'json')

## Использование

### Ручной запуск

```python
import asyncio
from datetime import datetime, timedelta
from src.automation import AutomationOrchestrator

async def main():
    # Инициализация оркестратора
    orchestrator = AutomationOrchestrator(config_path="config.json")
    
    # Определение диапазона дат
    end_date = datetime.now()
    start_date = end_date - timedelta(days=1)
    
    # Запуск автоматизации
    stats = await orchestrator.run_automation((start_date, end_date))
    
    print(f"Обработано сообщений: {stats['messages_processed']}")
    print(f"Длительность: {stats['duration_seconds']:.2f} секунд")
    print(f"Отправлено в Telegram: {stats['telegram_sent']}")

if __name__ == "__main__":
    asyncio.run(main())
```

### Автоматический запуск по расписанию

```python
from src.automation import AutomationOrchestrator

# Инициализация оркестратора
orchestrator = AutomationOrchestrator(config_path="config.json")

# Настройка расписания (запуск в будние дни в указанное время)
orchestrator.setup_schedule()

# Планировщик будет работать в фоновом режиме
# Для остановки используйте Ctrl+C
```

### Логика определения диапазона дат

При автоматическом запуске по расписанию:
- **Понедельник**: Анализируются сообщения за пятницу-воскресенье (3 дня)
- **Вторник-пятница**: Анализируются сообщения за предыдущий день

## Workflow выполнения

```
1. Экспорт данных
   ├─ Получение сообщений из БД за указанный период
   ├─ Фильтрация по диапазону дат
   └─ Экспорт в CSV/JSON

2. Обработка сводок
   ├─ Создание ноутбука NotebookLM
   ├─ Загрузка файла как источника данных
   └─ Параллельная генерация негативной и позитивной сводок

3. Отправка результатов
   ├─ Форматирование сводок для Telegram
   ├─ Разбиение длинных сообщений на части
   └─ Отправка обеих сводок в указанный чат

4. Очистка ресурсов
   ├─ Удаление ноутбука NotebookLM
   └─ Удаление временных файлов
```

## Обработка ошибок

Оркестратор реализует следующие механизмы обработки ошибок:

1. **Retry-логика**: Автоматические повторные попытки при сетевых ошибках и таймаутах
2. **Graceful degradation**: Продолжение работы при некритических ошибках (например, ошибки удаления ресурсов)
3. **Уведомления об ошибках**: Отправка уведомлений в Telegram при критических ошибках
4. **Гарантированная очистка**: Очистка ресурсов выполняется даже при ошибках (finally блок)

## Тестирование

Запуск всех тестов модуля:

```bash
pytest src/automation/ -v
```

Запуск только integration-тестов:

```bash
pytest src/automation/test_orchestrator.py -v
```

## Логирование

Все операции логируются в файл `logs/parser.log` с использованием существующего логгера проекта.

Уровни логирования:
- **INFO**: Начало и завершение этапов, успешные операции
- **WARNING**: Некритические ошибки, использование значений по умолчанию
- **ERROR**: Критические ошибки, прерывание выполнения

## Зависимости

- `notebooklm-py`: Библиотека для работы с NotebookLM API
- `telethon`: Библиотека для работы с Telegram API
- `pandas`: Для работы с экспортированными данными
- Все существующие компоненты проекта (UnifiedParser, ExcelExporter, Database, и т.д.)
