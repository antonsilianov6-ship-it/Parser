# Requirements Document

## Introduction

Система автоматизации создания аналитических сводок через NotebookLM с последующей отправкой результатов в Telegram. Система предназначена для автоматизации ежедневного процесса анализа сообщений из Telegram-каналов, который в настоящее время выполняется вручную. Система должна интегрироваться с существующим Telegram-парсером и использовать библиотеку notebooklm-py для программного взаимодействия с NotebookLM API.

## Glossary

- **NotebookLM_Client**: Клиент для взаимодействия с NotebookLM API через библиотеку notebooklm-py
- **Telegram_Sender**: Компонент для отправки сообщений в Telegram чат
- **Summary_Generator**: Генератор аналитических сводок на основе данных из NotebookLM
- **File_Manager**: Менеджер для управления файлами данных и очистки кеша
- **Automation_Orchestrator**: Оркестратор для координации всего процесса автоматизации
- **Export_Data**: Данные, экспортированные из Telegram-парсера в формате CSV/JSON
- **Negative_Summary**: Аналитическая сводка с негативными отзывами (жалобы и проблемы)
- **Positive_Summary**: Аналитическая сводка с позитивными отзывами (похвалы и плюсы)
- **Morning_Report**: Утренняя сводка для директора, содержащая обе аналитические сводки
- **Notebook**: Ноутбук в NotebookLM, содержащий источники данных и историю запросов
- **Source**: Источник данных в NotebookLM (файл с экспортированными сообщениями)

## Requirements

### Requirement 1: Интеграция с NotebookLM API

**User Story:** Как пользователь системы, я хочу программно взаимодействовать с NotebookLM, чтобы автоматизировать процесс создания аналитических сводок.

#### Acceptance Criteria

1. THE NotebookLM_Client SHALL инициализироваться с валидными учетными данными для доступа к NotebookLM API
2. WHEN инициализация выполнена успешно, THE NotebookLM_Client SHALL возвращать объект клиента с активной сессией
3. WHEN учетные данные невалидны, THE NotebookLM_Client SHALL возвращать ошибку аутентификации с описательным сообщением
4. THE NotebookLM_Client SHALL поддерживать создание новых ноутбуков программно
5. THE NotebookLM_Client SHALL поддерживать добавление источников данных в ноутбук
6. THE NotebookLM_Client SHALL поддерживать отправку запросов к ноутбуку и получение ответов

### Requirement 2: Управление ноутбуками и источниками данных

**User Story:** Как пользователь системы, я хочу автоматически управлять ноутбуками и источниками данных в NotebookLM, чтобы избежать ручной очистки и загрузки файлов.

#### Acceptance Criteria

1. THE File_Manager SHALL создавать новый ноутбук в NotebookLM перед каждым запуском анализа
2. WHEN ноутбук создан, THE File_Manager SHALL добавлять файл с экспортированными данными как источник
3. THE File_Manager SHALL поддерживать загрузку файлов в форматах CSV и JSON
4. WHEN файл загружен успешно, THE File_Manager SHALL возвращать идентификатор источника данных
5. WHEN загрузка файла завершена, THE File_Manager SHALL удалять временные файлы из локального кеша
6. THE File_Manager SHALL удалять старые ноутбуки после успешного завершения анализа
7. WHEN удаление ноутбука не удается, THE File_Manager SHALL логировать предупреждение и продолжать работу

### Requirement 3: Генерация аналитических сводок

**User Story:** Как пользователь системы, я хочу автоматически генерировать негативные и позитивные аналитические сводки, чтобы получать структурированный анализ сообщений из Telegram-каналов.

#### Acceptance Criteria

1. THE Summary_Generator SHALL генерировать негативную сводку на основе промпта для анализа жалоб и проблем
2. THE Summary_Generator SHALL генерировать позитивную сводку на основе промпта для анализа похвал и плюсов
3. WHEN запрос к NotebookLM отправлен, THE Summary_Generator SHALL ожидать ответ с таймаутом 120 секунд
4. WHEN ответ получен, THE Summary_Generator SHALL извлекать текст сводки из ответа
5. WHEN таймаут превышен, THE Summary_Generator SHALL повторять запрос до 3 раз с экспоненциальной задержкой
6. WHEN все попытки исчерпаны, THE Summary_Generator SHALL возвращать ошибку с описанием проблемы
7. THE Summary_Generator SHALL форматировать сводки в читаемый текстовый формат для отправки в Telegram

### Requirement 4: Конфигурация промптов для анализа

**User Story:** Как пользователь системы, я хочу настраивать промпты для анализа, чтобы адаптировать систему под изменяющиеся требования к аналитике.

#### Acceptance Criteria

1. THE Summary_Generator SHALL загружать промпты из конфигурационного файла при инициализации
2. THE Summary_Generator SHALL поддерживать два типа промптов: негативный и позитивный
3. WHEN конфигурационный файл отсутствует, THE Summary_Generator SHALL использовать промпты по умолчанию
4. THE Summary_Generator SHALL валидировать промпты на наличие обязательных полей при загрузке
5. WHEN промпт невалиден, THE Summary_Generator SHALL возвращать ошибку валидации с указанием проблемы
6. THE Summary_Generator SHALL поддерживать переменные в промптах для динамической подстановки параметров

### Requirement 5: Отправка результатов в Telegram

**User Story:** Как пользователь системы, я хочу автоматически получать готовые сводки в Telegram чат, чтобы не выполнять ручную отправку результатов.

#### Acceptance Criteria

1. THE Telegram_Sender SHALL инициализироваться с учетными данными из существующей конфигурации парсера
2. THE Telegram_Sender SHALL отправлять сообщения в указанный Telegram чат по его ID
3. WHEN сводка готова, THE Telegram_Sender SHALL форматировать сообщение с заголовком и текстом сводки
4. THE Telegram_Sender SHALL отправлять негативную и позитивную сводки как отдельные сообщения
5. WHEN сообщение превышает лимит Telegram в 4096 символов, THE Telegram_Sender SHALL разбивать сообщение на части
6. WHEN отправка сообщения не удается, THE Telegram_Sender SHALL повторять попытку до 3 раз с задержкой 5 секунд
7. WHEN все попытки отправки исчерпаны, THE Telegram_Sender SHALL логировать ошибку и возвращать статус неудачи

### Requirement 6: Оркестрация процесса автоматизации

**User Story:** Как пользователь системы, я хочу запускать весь процесс одной командой, чтобы минимизировать ручное вмешательство.

#### Acceptance Criteria

1. THE Automation_Orchestrator SHALL координировать выполнение всех этапов процесса в правильной последовательности
2. THE Automation_Orchestrator SHALL экспортировать данные из парсера перед началом анализа
3. WHEN экспорт данных завершен, THE Automation_Orchestrator SHALL создавать ноутбук и загружать файл
4. WHEN файл загружен, THE Automation_Orchestrator SHALL генерировать обе аналитические сводки параллельно
5. WHEN обе сводки готовы, THE Automation_Orchestrator SHALL отправлять их в Telegram
6. WHEN любой этап завершается с ошибкой, THE Automation_Orchestrator SHALL логировать ошибку и останавливать процесс
7. THE Automation_Orchestrator SHALL очищать временные файлы и ресурсы после завершения процесса

### Requirement 7: Интеграция с существующим парсером

**User Story:** Как пользователь системы, я хочу использовать существующую функциональность парсера, чтобы не дублировать код и сохранить совместимость.

#### Acceptance Criteria

1. THE Automation_Orchestrator SHALL использовать существующий UnifiedParser для получения данных
2. THE Automation_Orchestrator SHALL использовать существующий ExcelExporter для экспорта данных в CSV
3. THE Automation_Orchestrator SHALL использовать существующую конфигурацию Telegram из config.json
4. THE Automation_Orchestrator SHALL использовать существующий логгер для записи логов
5. THE Automation_Orchestrator SHALL сохранять экспортированные файлы в существующую директорию exports
6. THE Automation_Orchestrator SHALL использовать существующий Database для получения сообщений

### Requirement 8: Расписание и автоматический запуск

**User Story:** Как пользователь системы, я хочу настроить автоматический запуск утренней сводки, чтобы получать отчеты без ручного запуска.

#### Acceptance Criteria

1. THE Automation_Orchestrator SHALL поддерживать запуск по расписанию через существующий Scheduler
2. THE Automation_Orchestrator SHALL запускаться в будние дни в настраиваемое время
3. WHEN день недели - понедельник, THE Automation_Orchestrator SHALL парсить сообщения с пятницы по воскресенье
4. WHEN день недели - вторник-пятница, THE Automation_Orchestrator SHALL парсить сообщения за предыдущий день
5. THE Automation_Orchestrator SHALL загружать расписание из конфигурационного файла
6. WHEN расписание не настроено, THE Automation_Orchestrator SHALL использовать режим ручного запуска
7. THE Automation_Orchestrator SHALL логировать каждый запуск по расписанию с временной меткой

### Requirement 9: Обработка ошибок и восстановление

**User Story:** Как пользователь системы, я хочу получать информативные сообщения об ошибках, чтобы быстро диагностировать и устранять проблемы.

#### Acceptance Criteria

1. THE Automation_Orchestrator SHALL использовать существующий ErrorHandler для обработки ошибок
2. WHEN возникает ошибка API NotebookLM, THE Automation_Orchestrator SHALL логировать детали ошибки и контекст
3. WHEN возникает ошибка сети, THE Automation_Orchestrator SHALL повторять операцию с экспоненциальной задержкой
4. WHEN возникает ошибка аутентификации, THE Automation_Orchestrator SHALL останавливать процесс и уведомлять пользователя
5. THE Automation_Orchestrator SHALL сохранять промежуточные результаты для возможности восстановления
6. WHEN процесс прерван, THE Automation_Orchestrator SHALL очищать частично созданные ресурсы
7. THE Automation_Orchestrator SHALL отправлять уведомление в Telegram при критических ошибках

### Requirement 10: Конфигурация и настройки

**User Story:** Как пользователь системы, я хочу настраивать параметры автоматизации через конфигурационный файл, чтобы адаптировать систему под свои нужды.

#### Acceptance Criteria

1. THE Automation_Orchestrator SHALL загружать настройки из конфигурационного файла при инициализации
2. THE Automation_Orchestrator SHALL поддерживать настройку ID целевого Telegram чата
3. THE Automation_Orchestrator SHALL поддерживать настройку времени запуска по расписанию
4. THE Automation_Orchestrator SHALL поддерживать настройку таймаутов для запросов к NotebookLM
5. THE Automation_Orchestrator SHALL поддерживать настройку количества повторных попыток при ошибках
6. THE Automation_Orchestrator SHALL поддерживать настройку формата экспорта данных (CSV или JSON)
7. WHEN конфигурационный файл содержит невалидные значения, THE Automation_Orchestrator SHALL использовать значения по умолчанию и логировать предупреждение

### Requirement 11: Логирование и мониторинг

**User Story:** Как пользователь системы, я хочу отслеживать выполнение процесса автоматизации, чтобы контролировать его работу и диагностировать проблемы.

#### Acceptance Criteria

1. THE Automation_Orchestrator SHALL логировать начало и завершение каждого этапа процесса
2. THE Automation_Orchestrator SHALL логировать время выполнения каждого этапа
3. THE Automation_Orchestrator SHALL логировать количество обработанных сообщений
4. THE Automation_Orchestrator SHALL логировать размер сгенерированных сводок
5. THE Automation_Orchestrator SHALL логировать статус отправки сообщений в Telegram
6. THE Automation_Orchestrator SHALL сохранять логи в существующую директорию logs
7. THE Automation_Orchestrator SHALL использовать существующий формат логов для совместимости

### Requirement 12: Тестирование и валидация

**User Story:** Как разработчик системы, я хочу иметь автоматические тесты для всех компонентов, чтобы гарантировать корректность работы системы.

#### Acceptance Criteria

1. THE NotebookLM_Client SHALL иметь unit-тесты для всех публичных методов
2. THE Summary_Generator SHALL иметь unit-тесты для генерации сводок с моками NotebookLM API
3. THE Telegram_Sender SHALL иметь unit-тесты для отправки сообщений с моками Telegram API
4. THE File_Manager SHALL иметь unit-тесты для управления файлами и ноутбуками
5. THE Automation_Orchestrator SHALL иметь integration-тесты для полного цикла автоматизации
6. FOR ALL компонентов с внешними зависимостями, тесты SHALL использовать моки для изоляции
7. THE Automation_Orchestrator SHALL иметь тест для проверки корректной обработки ошибок на каждом этапе
