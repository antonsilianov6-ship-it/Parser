# Requirements Document: Telegram Parser Refactoring

## Introduction

Данный документ описывает требования к рефакторингу и оптимизации проекта парсера Telegram-каналов с экспортом в Google Docs. Проект был написан полгода назад начинающим разработчиком и имеет серьезные архитектурные проблемы: дублирование кода, нарушение принципов SOLID, модули превышающие 350 строк, неэффективную работу с БД и отсутствие единой точки входа.

Цель рефакторинга - привести код к архитектурным стандартам, устранить дублирование, оптимизировать производительность, обновить зависимости и улучшить обработку ошибок.

## Glossary

- **Parser**: Система парсинга сообщений из Telegram-каналов
- **TelegramClient**: Клиент для взаимодействия с Telegram API
- **MessageParser**: Основной парсер сообщений (старая версия)
- **EnhancedParser**: Улучшенный парсер сообщений (новая версия)
- **Cache_Manager**: Менеджер кэширования данных
- **Entity_Cache**: Кэш для хранения информации о Telegram-каналах
- **Database**: База данных SQLite для хранения сообщений
- **Exporter**: Модуль экспорта данных в различные форматы
- **Module**: Файл с кодом, не должен превышать 350 строк
- **Entry_Point**: Единая точка входа в приложение
- **Batch_Operation**: Пакетная операция с базой данных
- **Dependency**: Внешняя библиотека из requirements.txt

## Requirements

### Requirement 1: Устранение дублирования главных файлов

**User Story:** Как разработчик, я хочу иметь единую точку входа в приложение, чтобы не было путаницы при запуске и поддержке кода.

#### Acceptance Criteria

1. THE Parser SHALL have exactly one main entry point file
2. WHEN the user runs the application, THE Entry_Point SHALL provide a unified interface for all modes (parse, export, stats, schedule)
3. THE Parser SHALL merge functionality from main.py and enhanced_main.py into a single entry point
4. THE Entry_Point SHALL support command-line arguments for mode selection
5. THE Parser SHALL remove duplicate main.py and enhanced_main.py files after migration

### Requirement 2: Объединение парсеров

**User Story:** Как разработчик, я хочу иметь единый парсер с полным функционалом, чтобы избежать дублирования логики и упростить поддержку.

#### Acceptance Criteria

1. THE Parser SHALL merge MessageParser and EnhancedParser into a single unified parser class
2. THE Parser SHALL preserve all functionality from both parsers (basic parsing, retry logic, statistics, scheduling)
3. WHEN merging parsers, THE Parser SHALL eliminate duplicate code for message processing
4. THE Parser SHALL maintain backward compatibility with existing database schema
5. THE Parser SHALL remove duplicate MessageParser and EnhancedParser files after migration

### Requirement 3: Разделение TelegramClient на компоненты

**User Story:** Как разработчик, я хочу разбить большой TelegramClient на отдельные компоненты по принципу единственной ответственности, чтобы код был читаемым и поддерживаемым.

#### Acceptance Criteria

1. THE Parser SHALL split TelegramClient into separate modules, each not exceeding 350 lines
2. THE Parser SHALL create a TelegramConnectionManager module responsible only for connection and authentication
3. THE Parser SHALL create a MessageFetcher module responsible only for fetching messages from channels
4. THE Parser SHALL create a CommentFetcher module responsible only for fetching comments to posts
5. THE Parser SHALL create a LinkFormatter module responsible only for formatting message and comment links
6. THE Parser SHALL create an EntityCacheManager module responsible only for entity caching operations
7. WHEN splitting modules, THE Parser SHALL preserve all existing functionality
8. THE Parser SHALL ensure each module follows the Single Responsibility Principle

### Requirement 4: Унификация системы кэширования

**User Story:** Как разработчик, я хочу иметь единую систему кэширования, чтобы избежать дублирования логики и упростить управление кэшем.

#### Acceptance Criteria

1. THE Cache_Manager SHALL provide a unified interface for all caching operations
2. THE Parser SHALL migrate entity caching from TelegramClient to Cache_Manager
3. THE Cache_Manager SHALL support both in-memory and persistent caching
4. THE Cache_Manager SHALL provide methods for cache validation and expiration
5. WHEN caching entities, THE Cache_Manager SHALL use the same persistence mechanism as other cached data
6. THE Parser SHALL remove duplicate entity cache files (entity_cache.pkl, entity_metadata.json) after migration
7. THE Cache_Manager SHALL consolidate all cache data into a single storage location

### Requirement 5: Оптимизация работы с базой данных

**User Story:** Как пользователь, я хочу, чтобы парсер работал быстрее при сохранении большого количества сообщений, чтобы сократить время обработки каналов.

#### Acceptance Criteria

1. THE Database SHALL support batch insert operations for messages
2. WHEN saving multiple messages, THE Database SHALL use batch operations instead of individual inserts
3. THE Database SHALL commit transactions in batches of 100 messages
4. THE Database SHALL provide a method for bulk message insertion
5. WHEN performing batch operations, THE Database SHALL maintain data integrity and handle errors gracefully

### Requirement 6: Оптимизация задержек

**User Story:** Как пользователь, я хочу, чтобы парсер работал быстрее, устраняя избыточные задержки, чтобы сократить общее время парсинга.

#### Acceptance Criteria

1. THE Parser SHALL analyze all asyncio.sleep() calls and remove unnecessary delays
2. THE Parser SHALL reduce delay between fetching individual messages from 0.1s to 0.01s
3. THE Parser SHALL reduce delay between fetching comments from 0.5s to 0.1s
4. THE Parser SHALL keep delay between channels as configurable parameter
5. WHEN reducing delays, THE Parser SHALL ensure compliance with Telegram API rate limits
6. THE Parser SHALL implement adaptive delay based on FloodWait errors

### Requirement 7: Обновление зависимостей

**User Story:** Как разработчик, я хочу использовать актуальные версии библиотек, чтобы получить исправления безопасности и новые возможности.

#### Acceptance Criteria

1. THE Parser SHALL update all dependencies in requirements.txt to latest compatible versions
2. THE Parser SHALL verify compatibility of updated dependencies with existing code
3. THE Parser SHALL test all functionality after dependency updates
4. WHEN updating dependencies, THE Parser SHALL document any breaking changes
5. THE Parser SHALL ensure telethon version is at least 1.34.0
6. THE Parser SHALL ensure all google-api libraries are compatible with each other

### Requirement 8: Улучшение обработки ошибок

**User Story:** Как пользователь, я хочу получать понятные сообщения об ошибках и автоматическое восстановление после сбоев, чтобы парсер работал стабильнее.

#### Acceptance Criteria

1. THE Parser SHALL implement centralized error handling for all modules
2. WHEN a FloodWaitError occurs, THE Parser SHALL log the wait time and retry automatically
3. WHEN a ChannelPrivateError occurs, THE Parser SHALL log the channel name and continue with next channel
4. WHEN a network error occurs, THE Parser SHALL retry with exponential backoff up to 3 times
5. THE Parser SHALL log all errors with full context (channel name, message ID, timestamp)
6. THE Parser SHALL continue processing remaining channels when one channel fails
7. THE Parser SHALL provide a summary report of all errors at the end of parsing session

### Requirement 9: Соблюдение лимита строк в модулях

**User Story:** Как разработчик, я хочу, чтобы все модули не превышали 350 строк, чтобы код был читаемым и легко поддерживаемым.

#### Acceptance Criteria

1. THE Parser SHALL ensure no module exceeds 350 lines of code
2. WHEN a module exceeds 350 lines, THE Parser SHALL split it into multiple modules
3. THE Parser SHALL extract reusable functions into utility modules
4. THE Parser SHALL group related functionality into separate modules
5. THE Parser SHALL maintain clear module boundaries and dependencies

### Requirement 10: Устранение дублирования кода

**User Story:** Как разработчик, я хочу устранить все дублирование кода, чтобы следовать принципу DRY и упростить поддержку.

#### Acceptance Criteria

1. THE Parser SHALL identify all duplicate code blocks across modules
2. THE Parser SHALL extract duplicate logic into reusable functions
3. THE Parser SHALL create utility modules for common operations (link formatting, date parsing, entity extraction)
4. WHEN extracting duplicate code, THE Parser SHALL ensure all callers use the new shared functions
5. THE Parser SHALL verify no duplicate implementations exist after refactoring

### Requirement 11: Создание единого конфигурационного модуля

**User Story:** Как пользователь, я хочу иметь единое место для всех настроек приложения, чтобы легко управлять конфигурацией.

#### Acceptance Criteria

1. THE Parser SHALL consolidate all configuration parameters in src/config.py
2. THE Parser SHALL validate all required configuration parameters on startup
3. THE Parser SHALL provide default values for optional configuration parameters
4. THE Parser SHALL support environment variables for sensitive configuration (API keys)
5. WHEN configuration is invalid, THE Parser SHALL provide clear error messages indicating missing or incorrect parameters

### Requirement 12: Оптимизация предзагрузки entity

**User Story:** Как пользователь, я хочу, чтобы парсер использовал оптимальную стратегию загрузки информации о каналах, чтобы минимизировать количество запросов к API.

#### Acceptance Criteria

1. THE Parser SHALL use lazy entity loading by default (extract from messages)
2. THE Parser SHALL provide optional prefetch mode for entity loading
3. WHEN using lazy loading, THE Parser SHALL extract entity from the first message without additional API calls
4. WHEN using prefetch mode, THE Parser SHALL load entities in batches of 5 with delays
5. THE Parser SHALL cache loaded entities for future runs

### Requirement 13: Создание модуля для работы с ссылками

**User Story:** Как разработчик, я хочу иметь единый модуль для форматирования всех типов ссылок, чтобы избежать дублирования логики форматирования.

#### Acceptance Criteria

1. THE LinkFormatter SHALL provide methods for formatting message links
2. THE LinkFormatter SHALL provide methods for formatting comment links
3. THE LinkFormatter SHALL handle both public channels (with username) and private channels (with ID)
4. THE LinkFormatter SHALL correctly format channel IDs starting with '100'
5. THE LinkFormatter SHALL validate generated links before returning them
6. WHEN a link cannot be formatted, THE LinkFormatter SHALL return None and log a warning

### Requirement 14: Создание модуля для работы с датами

**User Story:** Как разработчик, я хочу иметь единый модуль для работы с датами, чтобы избежать дублирования логики парсинга и форматирования дат.

#### Acceptance Criteria

1. THE Parser SHALL create a DateUtils module for all date operations
2. THE DateUtils SHALL provide a method for parsing date ranges from configuration
3. THE DateUtils SHALL provide a method for calculating date ranges based on days count
4. THE DateUtils SHALL handle timezone conversions consistently (UTC)
5. THE DateUtils SHALL validate date formats and provide clear error messages for invalid dates

### Requirement 15: Тестирование после рефакторинга

**User Story:** Как разработчик, я хочу убедиться, что рефакторинг не сломал существующую функциональность, чтобы гарантировать стабильность приложения.

#### Acceptance Criteria

1. THE Parser SHALL successfully parse messages from at least 3 test channels
2. THE Parser SHALL successfully export parsed messages to Google Docs
3. THE Parser SHALL correctly handle FloodWait errors with automatic retry
4. THE Parser SHALL correctly handle private/unavailable channels without crashing
5. THE Parser SHALL verify all modules are under 350 lines after refactoring
6. THE Parser SHALL verify no duplicate code exists after refactoring
7. THE Parser SHALL verify database operations work correctly with batch inserts
8. THE Parser SHALL verify cache operations work correctly with unified cache manager
