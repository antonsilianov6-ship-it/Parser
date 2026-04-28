# Requirements Document

## Introduction

Расширение функциональности Telegram парсера для поддержки парсинга обычных чатов (private/group chats) и чатов с топиками (forum/supergroup with topics). В настоящее время система поддерживает только парсинг каналов (channels), где используется односторонняя коммуникация. Новая функциональность добавит возможность парсить двусторонние чаты и чаты с организацией сообщений по темам/топикам, что расширит область применения парсера.

## Glossary

- **Channel**: Telegram канал с односторонней коммуникацией, где только администраторы могут публиковать сообщения
- **Chat**: Обычный Telegram чат (private или group) с двусторонней коммуникацией, где все участники могут писать сообщения
- **Forum_Chat**: Чат с топиками (supergroup с атрибутом forum=True), где сообщения организованы по темам
- **Topic**: Тема/топик в форум-чате, содержащая группу связанных сообщений
- **Source_Type**: Тип источника сообщений (channel, chat, forum_chat)
- **Message_Fetcher**: Компонент для получения сообщений из различных источников через Telethon
- **Topic_Manager**: Компонент для управления топиками в форум-чатах
- **Source_Detector**: Компонент для определения типа источника (канал, чат, форум-чат)
- **Unified_Parser**: Основной класс парсера, координирующий работу всех компонентов
- **Entity**: Объект Telegram API, представляющий канал, чат или пользователя
- **Reply_To**: Атрибут сообщения, содержащий информацию о том, на что отвечает сообщение
- **Forum_Topic_ID**: Идентификатор топика в форум-чате (reply_to_top_id)

## Requirements

### Requirement 1: Определение типа источника

**User Story:** Как пользователь системы, я хочу автоматически определять тип источника (канал, чат, форум-чат), чтобы система могла применить правильную стратегию парсинга.

#### Acceptance Criteria

1. THE Source_Detector SHALL определять тип источника на основе entity объекта из Telegram API
2. WHEN entity имеет атрибут broadcast=True, THE Source_Detector SHALL классифицировать источник как Channel
3. WHEN entity имеет атрибут megagroup=True и forum=False, THE Source_Detector SHALL классифицировать источник как Chat
4. WHEN entity имеет атрибут forum=True, THE Source_Detector SHALL классифицировать источник как Forum_Chat
5. WHEN entity является объектом User, THE Source_Detector SHALL классифицировать источник как Chat
6. THE Source_Detector SHALL возвращать Source_Type как строковое значение (channel, chat, forum_chat)
7. WHEN тип источника не может быть определен, THE Source_Detector SHALL возвращать значение по умолчанию "channel" и логировать предупреждение

### Requirement 2: Парсинг обычных чатов

**User Story:** Как пользователь системы, я хочу парсить сообщения из обычных Telegram чатов, чтобы получать данные из двусторонних коммуникаций.

#### Acceptance Criteria

1. THE Message_Fetcher SHALL поддерживать получение сообщений из обычных чатов через метод iter_messages
2. WHEN источник определен как Chat, THE Message_Fetcher SHALL использовать ту же логику получения сообщений, что и для каналов
3. THE Message_Fetcher SHALL извлекать автора сообщения из атрибута sender для чатов
4. THE Message_Fetcher SHALL формировать ссылки на сообщения в чатах с учетом типа чата (публичный или приватный)
5. WHEN чат является приватным, THE Message_Fetcher SHALL использовать ID чата для формирования ссылок
6. THE Message_Fetcher SHALL сохранять информацию о типе источника вместе с сообщением в базе данных
7. THE Message_Fetcher SHALL применять те же настройки задержек и ограничений, что и для каналов

### Requirement 3: Получение списка топиков в форум-чатах

**User Story:** Как пользователь системы, я хочу получать список всех топиков в форум-чате, чтобы парсить сообщения из каждого топика отдельно.

#### Acceptance Criteria

1. THE Topic_Manager SHALL получать список топиков через метод get_forum_topics из Telethon API
2. WHEN источник определен как Forum_Chat, THE Topic_Manager SHALL вызывать get_forum_topics для получения списка топиков
3. THE Topic_Manager SHALL извлекать ID топика (topic_id) из каждого объекта ForumTopic
4. THE Topic_Manager SHALL извлекать название топика (title) из каждого объекта ForumTopic
5. THE Topic_Manager SHALL возвращать список кортежей (topic_id, topic_title) для всех активных топиков
6. WHEN get_forum_topics возвращает ошибку доступа, THE Topic_Manager SHALL логировать ошибку и возвращать пустой список
7. THE Topic_Manager SHALL кэшировать список топиков на время сессии парсинга для избежания повторных API вызовов

### Requirement 4: Парсинг сообщений из топиков

**User Story:** Как пользователь системы, я хочу парсить сообщения из конкретных топиков форум-чата, чтобы получать структурированные данные по темам.

#### Acceptance Criteria

1. THE Message_Fetcher SHALL поддерживать фильтрацию сообщений по топикам через параметр reply_to в iter_messages
2. WHEN парсится форум-чат, THE Message_Fetcher SHALL получать сообщения для каждого топика отдельно
3. THE Message_Fetcher SHALL использовать reply_to_top_id для фильтрации сообщений конкретного топика
4. THE Message_Fetcher SHALL проверять атрибут reply_to.forum_topic=True для подтверждения принадлежности к топику
5. THE Message_Fetcher SHALL сохранять информацию о топике (topic_id, topic_title) вместе с сообщением
6. THE Message_Fetcher SHALL формировать ссылки на сообщения в топиках с учетом структуры форум-чата
7. THE Message_Fetcher SHALL применять задержки между парсингом разных топиков согласно конфигурации

### Requirement 5: Расширение модели данных

**User Story:** Как разработчик системы, я хочу хранить информацию о типе источника и топиках в базе данных, чтобы различать сообщения из разных типов источников.

#### Acceptance Criteria

1. THE Database SHALL добавить поле source_type в таблицу messages для хранения типа источника
2. THE Database SHALL добавить поле topic_id в таблицу messages для хранения идентификатора топика
3. THE Database SHALL добавить поле topic_title в таблицу messages для хранения названия топика
4. WHEN сообщение из канала или обычного чата, THE Database SHALL сохранять topic_id и topic_title как NULL
5. WHEN сообщение из форум-чата, THE Database SHALL сохранять соответствующие значения topic_id и topic_title
6. THE Database SHALL создавать индекс на поле source_type для оптимизации запросов
7. THE Database SHALL создавать индекс на поле topic_id для оптимизации запросов по топикам

### Requirement 6: Конфигурация источников

**User Story:** Как пользователь системы, я хочу указывать чаты и форум-чаты в конфигурации так же, как каналы, чтобы система автоматически определяла их тип.

#### Acceptance Criteria

1. THE Unified_Parser SHALL поддерживать загрузку ссылок на чаты из того же файла channels.txt
2. THE Unified_Parser SHALL автоматически определять тип каждого источника при инициализации
3. THE Unified_Parser SHALL поддерживать ссылки формата https://t.me/chatname для публичных чатов
4. THE Unified_Parser SHALL поддерживать ссылки формата https://t.me/c/CHAT_ID для приватных чатов
5. THE Unified_Parser SHALL поддерживать ссылки формата @chatname для публичных чатов
6. THE Unified_Parser SHALL логировать тип каждого источника при начале парсинга
7. WHEN источник недоступен или тип не может быть определен, THE Unified_Parser SHALL логировать ошибку и пропускать этот источник

### Requirement 7: Формирование ссылок для чатов и топиков

**User Story:** Как пользователь системы, я хочу получать корректные ссылки на сообщения в чатах и топиках, чтобы иметь возможность перейти к оригинальному сообщению.

#### Acceptance Criteria

1. THE Link_Formatter SHALL расширить метод format_message_link для поддержки чатов и топиков
2. WHEN источник является обычным чатом, THE Link_Formatter SHALL формировать ссылку формата https://t.me/chatname/message_id
3. WHEN источник является приватным чатом, THE Link_Formatter SHALL формировать ссылку формата https://t.me/c/CHAT_ID/message_id
4. WHEN источник является форум-чатом, THE Link_Formatter SHALL формировать ссылку с учетом топика
5. THE Link_Formatter SHALL добавить метод format_topic_message_link для формирования ссылок на сообщения в топиках
6. THE Link_Formatter SHALL валидировать сформированные ссылки на отсутствие None и корректность формата
7. WHEN ссылка не может быть сформирована, THE Link_Formatter SHALL возвращать None и логировать предупреждение

### Requirement 8: Обработка ошибок доступа

**User Story:** Как пользователь системы, я хочу получать информативные сообщения об ошибках доступа к чатам, чтобы понимать причины неудачного парсинга.

#### Acceptance Criteria

1. THE Error_Handler SHALL обрабатывать ошибку ChatAdminRequiredError для чатов, требующих прав администратора
2. THE Error_Handler SHALL обрабатывать ошибку UserNotParticipantError для чатов, где пользователь не является участником
3. THE Error_Handler SHALL обрабатывать ошибку ChatWriteForbiddenError для чатов с ограниченным доступом
4. WHEN возникает ошибка доступа к чату, THE Error_Handler SHALL логировать тип ошибки и название чата
5. THE Error_Handler SHALL предоставлять рекомендации по устранению ошибок доступа в логах
6. THE Error_Handler SHALL продолжать парсинг других источников после ошибки доступа к одному чату
7. THE Error_Handler SHALL собирать статистику ошибок доступа для отчетности

### Requirement 9: Статистика по типам источников

**User Story:** Как пользователь системы, я хочу видеть статистику по типам источников, чтобы понимать распределение данных.

#### Acceptance Criteria

1. THE Database SHALL добавить метод get_stats_by_source_type для получения статистики по типам источников
2. THE Database SHALL возвращать количество сообщений для каждого типа источника (channel, chat, forum_chat)
3. THE Database SHALL возвращать количество уникальных топиков в форум-чатах
4. THE Database SHALL возвращать список топиков с количеством сообщений в каждом
5. THE Unified_Parser SHALL включать статистику по типам источников в метод get_statistics
6. THE Unified_Parser SHALL логировать статистику по типам источников после завершения парсинга
7. WHEN запрашивается статистика, THE Database SHALL группировать данные по source_type и topic_id

### Requirement 10: Экспорт данных с информацией о топиках

**User Story:** Как пользователь системы, я хочу экспортировать данные с информацией о топиках, чтобы анализировать сообщения в контексте тем.

#### Acceptance Criteria

1. THE Excel_Exporter SHALL добавить колонки source_type, topic_id и topic_title в экспортируемые файлы
2. THE Excel_Exporter SHALL группировать сообщения по топикам при экспорте из форум-чатов
3. THE Google_Docs_Exporter SHALL включать информацию о топике в заголовок сообщения при экспорте
4. WHEN экспортируются сообщения из форум-чата, THE Excel_Exporter SHALL создавать отдельные листы для каждого топика
5. THE Excel_Exporter SHALL добавлять сводную таблицу с количеством сообщений по топикам
6. THE Google_Docs_Exporter SHALL форматировать сообщения из топиков с визуальным разделением по темам
7. WHEN topic_id равен NULL, THE Excel_Exporter SHALL отображать source_type как "channel" или "chat"

### Requirement 11: Кэширование entity для чатов

**User Story:** Как пользователь системы, я хочу использовать кэширование entity для чатов, чтобы минимизировать количество API вызовов.

#### Acceptance Criteria

1. THE Cache_Manager SHALL поддерживать кэширование entity для чатов так же, как для каналов
2. THE Cache_Manager SHALL сохранять тип источника вместе с entity в кэше
3. THE Cache_Manager SHALL сохранять список топиков для форум-чатов в кэше
4. WHEN entity чата запрашивается повторно, THE Cache_Manager SHALL возвращать закэшированное значение
5. THE Cache_Manager SHALL проверять актуальность закэшированных топиков на основе времени кэширования
6. WHEN кэш топиков устарел, THE Cache_Manager SHALL запрашивать обновленный список топиков
7. THE Cache_Manager SHALL использовать те же настройки времени жизни кэша для чатов, что и для каналов

### Requirement 12: Обратная совместимость

**User Story:** Как пользователь системы, я хочу сохранить работоспособность существующего функционала парсинга каналов, чтобы избежать регрессии.

#### Acceptance Criteria

1. THE Unified_Parser SHALL сохранять существующую логику парсинга каналов без изменений
2. WHEN source_type не указан в базе данных, THE Unified_Parser SHALL считать источник каналом для обратной совместимости
3. THE Message_Fetcher SHALL использовать существующую логику для источников типа Channel
4. THE Link_Formatter SHALL сохранять существующую логику формирования ссылок для каналов
5. THE Database SHALL поддерживать миграцию существующих данных с добавлением новых полей
6. WHEN выполняется миграция, THE Database SHALL устанавливать source_type="channel" для всех существующих записей
7. THE Unified_Parser SHALL проходить все существующие тесты без изменений

### Requirement 13: Тестирование новой функциональности

**User Story:** Как разработчик системы, я хочу иметь автоматические тесты для новой функциональности, чтобы гарантировать корректность работы.

#### Acceptance Criteria

1. THE Source_Detector SHALL иметь unit-тесты для определения всех типов источников
2. THE Topic_Manager SHALL иметь unit-тесты для получения списка топиков с моками Telethon API
3. THE Message_Fetcher SHALL иметь unit-тесты для парсинга чатов и форум-чатов с моками
4. THE Link_Formatter SHALL иметь unit-тесты для формирования ссылок на сообщения в чатах и топиках
5. THE Database SHALL иметь unit-тесты для новых полей и методов статистики
6. THE Unified_Parser SHALL иметь integration-тесты для полного цикла парсинга чатов и форум-чатов
7. FOR ALL компонентов с внешними зависимостями, тесты SHALL использовать моки для изоляции

