# Design Document: Chat and Topic Support

## Overview

Данный дизайн описывает расширение функциональности Telegram парсера для поддержки парсинга обычных чатов (private/group chats) и чатов с топиками (forum/supergroup with topics). В настоящее время система поддерживает только парсинг каналов (channels), где используется односторонняя коммуникация.

### Цели дизайна

1. **Расширение типов источников**: Добавить поддержку обычных чатов и форум-чатов с топиками
2. **Автоматическое определение типа**: Система должна автоматически определять тип источника (канал, чат, форум-чат)
3. **Структурированное хранение**: Сохранять информацию о типе источника и топиках в базе данных
4. **Обратная совместимость**: Сохранить работоспособность существующего функционала парсинга каналов
5. **Масштабируемость**: Архитектура должна легко расширяться для новых типов источников

### Ключевые изменения

- Новый компонент `SourceDetector` для определения типа источника
- Новый компонент `TopicManager` для управления топиками в форум-чатах
- Расширение `MessageFetcher` для поддержки чатов и топиков
- Расширение `LinkFormatter` для формирования ссылок на сообщения в чатах и топиках
- Расширение модели данных БД с новыми полями: `source_type`, `topic_id`, `topic_title`
- Расширение `ErrorHandler` для обработки специфичных ошибок доступа к чатам

## Architecture

### Общая архитектура

```
┌─────────────────────────────────────────────────────────────┐
│                      UnifiedParser                          │
│  (Координирует работу всех компонентов)                     │
└────────────────────┬────────────────────────────────────────┘
                     │
        ┌────────────┼────────────┐
        │            │            │
        ▼            ▼            ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│SourceDetector│ │MessageFetcher│ │ TopicManager │
│              │ │              │ │              │
│ Определяет   │ │ Получает     │ │ Управляет    │
│ тип источника│ │ сообщения    │ │ топиками     │
└──────┬───────┘ └──────┬───────┘ └──────┬───────┘
       │                │                │
       │                │                │
       ▼                ▼                ▼
┌─────────────────────────────────────────────────┐
│           ConnectionManager                      │
│      (Управление подключением к Telegram)        │
└─────────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────┐
│              Telegram API                        │
│         (Telethon Client)                        │
└─────────────────────────────────────────────────┘
```

### Поток данных

```
1. Загрузка источников из channels.txt
   ↓
2. SourceDetector определяет тип каждого источника
   ↓
3. Для форум-чатов: TopicManager получает список топиков
   ↓
4. MessageFetcher получает сообщения с учетом типа источника
   ↓
5. LinkFormatter формирует корректные ссылки
   ↓
6. Database сохраняет сообщения с метаданными (source_type, topic_id)
   ↓
7. Экспорт данных с информацией о топиках
```

### Стратегия парсинга по типам источников

| Тип источника | Метод получения | Особенности |
|--------------|----------------|-------------|
| Channel | `iter_messages(channel)` | Односторонняя коммуникация, публичные посты |
| Chat | `iter_messages(chat)` | Двусторонняя коммуникация, все участники могут писать |
| Forum_Chat | `iter_messages(chat, reply_to=topic_id)` | Сообщения организованы по топикам |

## Components and Interfaces

### 1. SourceDetector

**Назначение**: Определение типа источника на основе entity объекта из Telegram API.

**Интерфейс**:

```python
class SourceDetector:
    """Определяет тип источника Telegram (канал, чат, форум-чат)"""
    
    @staticmethod
    def detect_source_type(entity: Any) -> str:
        """
        Определяет тип источника на основе entity
        
        Args:
            entity: Entity объект из Telegram API (Channel, Chat, User)
            
        Returns:
            Тип источника: 'channel', 'chat', 'forum_chat'
            
        Logic:
            - Если entity.broadcast=True → 'channel'
            - Если entity.megagroup=True и entity.forum=False → 'chat'
            - Если entity.forum=True → 'forum_chat'
            - Если entity является User → 'chat'
            - По умолчанию → 'channel' (с предупреждением в логах)
        """
        pass
    
    @staticmethod
    def is_forum_chat(entity: Any) -> bool:
        """
        Проверяет, является ли источник форум-чатом
        
        Args:
            entity: Entity объект из Telegram API
            
        Returns:
            True если форум-чат, False иначе
        """
        pass
```

**Зависимости**:
- Нет внешних зависимостей (чистая функция)

**Обработка ошибок**:
- Если entity не содержит необходимых атрибутов, возвращает 'channel' по умолчанию
- Логирует предупреждение при невозможности определить тип

### 2. TopicManager

**Назначение**: Управление топиками в форум-чатах.

**Интерфейс**:

```python
class TopicManager:
    """Управляет топиками в форум-чатах"""
    
    def __init__(self, connection_manager: ConnectionManager):
        """
        Инициализация менеджера топиков
        
        Args:
            connection_manager: Менеджер подключения к Telegram
        """
        self.connection_manager = connection_manager
        self.topic_cache: Dict[str, List[Tuple[int, str]]] = {}
    
    async def get_forum_topics(
        self, 
        chat_entity: Any
    ) -> List[Tuple[int, str]]:
        """
        Получает список топиков из форум-чата
        
        Args:
            chat_entity: Entity форум-чата
            
        Returns:
            Список кортежей (topic_id, topic_title)
            
        Raises:
            ChatAdminRequiredError: Если нет прав доступа
        """
        pass
    
    def get_cached_topics(self, chat_link: str) -> Optional[List[Tuple[int, str]]]:
        """
        Получает закэшированный список топиков
        
        Args:
            chat_link: Ссылка на чат
            
        Returns:
            Список топиков или None если не в кэше
        """
        pass
    
    def cache_topics(
        self, 
        chat_link: str, 
        topics: List[Tuple[int, str]]
    ) -> None:
        """
        Кэширует список топиков
        
        Args:
            chat_link: Ссылка на чат
            topics: Список топиков для кэширования
        """
        pass
```

**Зависимости**:
- `ConnectionManager`: для доступа к Telegram API
- `telethon.tl.functions.channels.GetForumTopicsRequest`: для получения топиков

**Обработка ошибок**:
- `ChatAdminRequiredError`: логирует и возвращает пустой список
- `UserNotParticipantError`: логирует и возвращает пустой список
- Другие ошибки: логирует и пробрасывает выше

### 3. MessageFetcher (расширение)

**Назначение**: Получение сообщений из различных типов источников.

**Новые методы**:

```python
class MessageFetcher:
    # ... существующие методы ...
    
    async def fetch_chat_messages(
        self,
        chat_link: str,
        start_date: datetime,
        end_date: datetime,
        source_type: str
    ) -> List[Message]:
        """
        Получение сообщений из чата
        
        Args:
            chat_link: Ссылка на чат
            start_date: Начальная дата
            end_date: Конечная дата
            source_type: Тип источника ('chat' или 'forum_chat')
            
        Returns:
            Список сообщений с метаданными о типе источника
        """
        pass
    
    async def fetch_topic_messages(
        self,
        chat_entity: Any,
        topic_id: int,
        topic_title: str,
        start_date: datetime,
        end_date: datetime
    ) -> List[Message]:
        """
        Получение сообщений из конкретного топика
        
        Args:
            chat_entity: Entity форум-чата
            topic_id: ID топика
            topic_title: Название топика
            start_date: Начальная дата
            end_date: Конечная дата
            
        Returns:
            Список сообщений с метаданными о топике
        """
        pass
    
    def _extract_message_author(self, message: Any) -> str:
        """
        Извлекает автора сообщения
        
        Args:
            message: Объект сообщения из Telegram API
            
        Returns:
            Имя автора или 'Unknown'
        """
        pass
```

**Изменения в существующих методах**:
- `fetch_channel_messages`: добавить параметр `source_type` в возвращаемые `Message` объекты
- Добавить логику определения типа источника перед парсингом

### 4. LinkFormatter (расширение)

**Назначение**: Форматирование ссылок на сообщения в чатах и топиках.

**Новые методы**:

```python
class LinkFormatter:
    # ... существующие методы ...
    
    @staticmethod
    def format_chat_message_link(
        chat_link: str,
        chat_entity: Any,
        message_id: int,
        is_private: bool = False
    ) -> Optional[str]:
        """
        Форматирует ссылку на сообщение в чате
        
        Args:
            chat_link: Оригинальная ссылка на чат
            chat_entity: Entity чата
            message_id: ID сообщения
            is_private: True если приватный чат
            
        Returns:
            Отформатированная ссылка или None
            
        Format:
            - Публичный чат: https://t.me/chatname/message_id
            - Приватный чат: https://t.me/c/CHAT_ID/message_id
        """
        pass
    
    @staticmethod
    def format_topic_message_link(
        chat_entity: Any,
        topic_id: int,
        message_id: int
    ) -> Optional[str]:
        """
        Форматирует ссылку на сообщение в топике
        
        Args:
            chat_entity: Entity форум-чата
            topic_id: ID топика
            message_id: ID сообщения
            
        Returns:
            Отформатированная ссылка или None
            
        Format:
            - Публичный форум: https://t.me/chatname/topic_id/message_id
            - Приватный форум: https://t.me/c/CHAT_ID/topic_id/message_id
        """
        pass
    
    @staticmethod
    def is_private_chat(chat_link: str) -> bool:
        """
        Определяет, является ли чат приватным
        
        Args:
            chat_link: Ссылка на чат
            
        Returns:
            True если приватный чат (содержит /c/), False иначе
        """
        pass
```

### 5. Database (расширение)

**Назначение**: Хранение сообщений с метаданными о типе источника и топиках.

**Изменения в схеме**:

```sql
-- Добавление новых полей в таблицу messages
ALTER TABLE messages ADD COLUMN source_type TEXT DEFAULT 'channel';
ALTER TABLE messages ADD COLUMN topic_id INTEGER DEFAULT NULL;
ALTER TABLE messages ADD COLUMN topic_title TEXT DEFAULT NULL;

-- Создание индексов для оптимизации запросов
CREATE INDEX IF NOT EXISTS idx_messages_source_type ON messages(source_type);
CREATE INDEX IF NOT EXISTS idx_messages_topic_id ON messages(topic_id);
CREATE INDEX IF NOT EXISTS idx_messages_source_topic ON messages(source_type, topic_id);
```

**Новые методы**:

```python
class Database:
    # ... существующие методы ...
    
    def get_stats_by_source_type(self) -> Dict[str, Any]:
        """
        Получает статистику по типам источников
        
        Returns:
            Словарь со статистикой:
            {
                'by_source_type': {
                    'channel': count,
                    'chat': count,
                    'forum_chat': count
                },
                'forum_topics': [
                    {'topic_id': id, 'topic_title': title, 'messages_count': count},
                    ...
                ]
            }
        """
        pass
    
    def get_messages_by_topic(
        self, 
        topic_id: int, 
        limit: int = 1000
    ) -> List[Message]:
        """
        Получает сообщения из конкретного топика
        
        Args:
            topic_id: ID топика
            limit: Максимальное количество сообщений
            
        Returns:
            Список сообщений из топика
        """
        pass
    
    def migrate_existing_data(self) -> None:
        """
        Миграция существующих данных
        
        Устанавливает source_type='channel' для всех существующих записей
        где source_type равен NULL
        """
        pass
```

### 6. ErrorHandler (расширение)

**Назначение**: Обработка специфичных ошибок доступа к чатам.

**Новые методы**:

```python
class ErrorHandler:
    # ... существующие методы ...
    
    def handle_chat_access_error(
        self, 
        error: Exception, 
        chat_link: str
    ) -> None:
        """
        Обработка ошибок доступа к чатам
        
        Args:
            error: Исключение
            chat_link: Ссылка на чат
            
        Handles:
            - ChatAdminRequiredError: требуются права администратора
            - UserNotParticipantError: пользователь не является участником
            - ChatWriteForbiddenError: ограниченный доступ
        """
        pass
    
    def get_access_error_recommendations(
        self, 
        error_type: str
    ) -> str:
        """
        Получает рекомендации по устранению ошибок доступа
        
        Args:
            error_type: Тип ошибки
            
        Returns:
            Текст с рекомендациями
        """
        pass
```

## Data Models

### Message (расширение)

```python
@dataclass
class Message:
    """Класс для представления сообщения"""
    date: datetime
    text: str
    link: str
    title: str = ''
    previous_post: Optional[str] = None
    comments: List[Comment] = field(default_factory=list)
    
    # Новые поля
    source_type: str = 'channel'  # 'channel', 'chat', 'forum_chat'
    topic_id: Optional[int] = None
    topic_title: Optional[str] = None
    author: str = ''  # Автор сообщения (для чатов)
```

### SourceType (новый enum)

```python
from enum import Enum

class SourceType(Enum):
    """Типы источников Telegram"""
    CHANNEL = 'channel'
    CHAT = 'chat'
    FORUM_CHAT = 'forum_chat'
```

### Topic (новый dataclass)

```python
@dataclass
class Topic:
    """Класс для представления топика в форум-чате"""
    topic_id: int
    topic_title: str
    messages_count: int = 0
    last_message_date: Optional[datetime] = None
```

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system-essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*


### Property 1: Source type classification correctness

*For any* Telegram entity object with attributes (broadcast, megagroup, forum, or User type), the SourceDetector SHALL correctly classify it as one of three valid source types ('channel', 'chat', 'forum_chat') according to the classification rules: broadcast=True → 'channel', megagroup=True and forum=False → 'chat', forum=True → 'forum_chat', User type → 'chat'.

**Validates: Requirements 1.1, 1.2, 1.3, 1.4, 1.5, 1.6**

### Property 2: Message author extraction

*For any* message object from a chat source, the Message_Fetcher SHALL correctly extract the author name from the sender attribute, returning a non-empty string or 'Unknown' if sender is not available.

**Validates: Requirements 2.3**

### Property 3: Source type preservation in messages

*For any* message being processed, the Message_Fetcher SHALL preserve the source_type field correctly in the Message object, ensuring it matches the detected source type.

**Validates: Requirements 2.6**

### Property 4: Topic metadata extraction

*For any* ForumTopic object, the Topic_Manager SHALL correctly extract both topic_id and topic_title, returning them as a tuple (int, str) with non-null values.

**Validates: Requirements 3.3, 3.4, 3.5**

### Property 5: Topic caching consistency

*For any* forum chat, when Topic_Manager is called multiple times with the same chat link during a session, it SHALL return the cached topic list without making additional API calls, ensuring the cached data matches the original data.

**Validates: Requirements 3.7, 11.3, 11.4**

### Property 6: Topic metadata preservation in messages

*For any* message from a forum chat topic, the Message_Fetcher SHALL correctly preserve topic_id and topic_title in the Message object, ensuring they match the topic being parsed.

**Validates: Requirements 4.5**

### Property 7: Database topic field nullability

*For any* message from a channel or regular chat (source_type='channel' or 'chat'), the Database SHALL store topic_id and topic_title as NULL, while for messages from forum chats (source_type='forum_chat'), these fields SHALL contain non-null values.

**Validates: Requirements 5.4, 5.5**

### Property 8: Link format correctness for chats

*For any* chat message (public or private), the LinkFormatter SHALL generate a valid link in the correct format: 'https://t.me/chatname/message_id' for public chats or 'https://t.me/c/CHAT_ID/message_id' for private chats, where the link passes validation and contains no None values.

**Validates: Requirements 7.2, 7.3, 7.4, 7.5**

### Property 9: Link format correctness for topics

*For any* forum chat message with topic_id, the LinkFormatter SHALL generate a valid link that includes the topic identifier in the correct format, ensuring the link is properly structured for both public and private forum chats.

**Validates: Requirements 7.4, 7.5**

### Property 10: Link validation consistency

*For any* generated link, the LinkFormatter SHALL validate it for correctness (no None values, proper format, minimum length), returning None only when the link cannot be properly formed, and logging a warning in such cases.

**Validates: Requirements 7.6, 7.7**

### Property 11: Error recommendations completeness

*For any* chat access error type (ChatAdminRequiredError, UserNotParticipantError, ChatWriteForbiddenError), the ErrorHandler SHALL provide specific recommendations for resolution, ensuring every error type has associated guidance.

**Validates: Requirements 8.5**

### Property 12: Error statistics accumulation

*For any* sequence of errors during parsing, the ErrorHandler SHALL correctly accumulate error statistics, ensuring the count and categorization of errors (by type and by channel) is accurate and complete.

**Validates: Requirements 8.7**

### Property 13: Export topic field handling

*For any* message being exported, when topic_id is NULL, the Excel_Exporter SHALL display only the source_type ('channel' or 'chat'), while for non-NULL topic_id, it SHALL display the topic information.

**Validates: Requirements 10.7**

### Property 14: Entity caching with metadata

*For any* entity (channel, chat, or forum_chat), the Cache_Manager SHALL cache it along with its source_type metadata, and subsequent retrievals SHALL return both the entity and its type without additional API calls.

**Validates: Requirements 11.1, 11.2**

### Property 15: Cache TTL consistency

*For any* cached entity or topic list, the Cache_Manager SHALL apply the same TTL (time-to-live) settings regardless of source type, ensuring consistent cache expiration behavior across channels, chats, and forum chats.

**Validates: Requirements 11.5, 11.7**

### Property 16: Backward compatibility for untyped messages

*For any* existing message in the database without a source_type value (NULL), the system SHALL treat it as a 'channel' type by default, ensuring backward compatibility with existing data.

**Validates: Requirements 12.2**

### Property 17: Channel link format preservation

*For any* channel entity, the LinkFormatter SHALL generate links using the same format and logic as before the changes, ensuring existing channel link generation remains unchanged.

**Validates: Requirements 12.4**

## Error Handling

### Error Categories

1. **Access Errors** (новые для чатов):
   - `ChatAdminRequiredError`: Требуются права администратора
   - `UserNotParticipantError`: Пользователь не является участником чата
   - `ChatWriteForbiddenError`: Ограниченный доступ к чату

2. **Existing Errors** (сохраняются):
   - `FloodWaitError`: Превышение лимита запросов
   - `ChannelPrivateError`: Приватный канал/чат
   - `UsernameNotOccupiedError`: Несуществующий username

### Error Handling Strategy

```python
# Псевдокод обработки ошибок для чатов
try:
    messages = await fetch_chat_messages(chat_link)
except ChatAdminRequiredError as e:
    logger.warning(f"Требуются права администратора для {chat_link}")
    error_handler.handle_chat_access_error(e, chat_link)
    # Рекомендация: "Получите права администратора или попросите администратора добавить бота"
    continue  # Пропускаем этот чат, продолжаем с другими
    
except UserNotParticipantError as e:
    logger.warning(f"Пользователь не является участником {chat_link}")
    error_handler.handle_chat_access_error(e, chat_link)
    # Рекомендация: "Присоединитесь к чату перед парсингом"
    continue
    
except ChatWriteForbiddenError as e:
    logger.warning(f"Ограниченный доступ к {chat_link}")
    error_handler.handle_chat_access_error(e, chat_link)
    # Рекомендация: "Проверьте настройки приватности чата"
    continue
```

### Error Recovery

- **Graceful Degradation**: При ошибке доступа к одному чату, парсинг продолжается для остальных источников
- **Error Logging**: Все ошибки логируются с полным контекстом (тип ошибки, источник, рекомендации)
- **Statistics Collection**: Ошибки накапливаются в статистике для последующего анализа
- **User Notifications**: Информативные сообщения об ошибках с рекомендациями по устранению

## Testing Strategy

### Testing Approach

Данная функциональность использует **комбинированный подход к тестированию**:

1. **Property-Based Testing (PBT)**: Для чистых функций с универсальными свойствами
2. **Unit Testing**: Для конкретных примеров и edge cases
3. **Integration Testing**: Для компонентов с внешними зависимостями (Telegram API, БД)
4. **Smoke Testing**: Для проверки схемы БД и конфигурации

### PBT Applicability Assessment

**PBT ПРИМЕНИМ для:**
- ✅ `SourceDetector.detect_source_type()` - чистая функция классификации
- ✅ `LinkFormatter.format_chat_message_link()` - чистая функция форматирования
- ✅ `LinkFormatter.format_topic_message_link()` - чистая функция форматирования
- ✅ `LinkFormatter.validate_link()` - чистая функция валидации
- ✅ `TopicManager` - извлечение данных из объектов (с моками API)
- ✅ `CacheManager` - логика кэширования (чистая логика)
- ✅ `ErrorHandler` - накопление статистики (чистая логика)

**PBT НЕ ПРИМЕНИМ для:**
- ❌ Интеграция с Telegram API (`iter_messages`, `get_forum_topics`) - внешний сервис
- ❌ Схема БД (миграции, индексы) - конфигурация
- ❌ Экспорт данных - side effects и форматирование файлов
- ❌ Логирование - side effects

### Test Structure

#### 1. Property-Based Tests (Hypothesis для Python)

**Библиотека**: `hypothesis` (стандарт для Python PBT)

**Конфигурация**:
```python
from hypothesis import given, settings
import hypothesis.strategies as st

# Минимум 100 итераций для каждого property теста
@settings(max_examples=100)
```

**Примеры property тестов**:

```python
# Feature: chat-and-topic-support, Property 1: Source type classification correctness
@given(
    broadcast=st.booleans(),
    megagroup=st.booleans(),
    forum=st.booleans()
)
@settings(max_examples=100)
def test_source_type_classification_property(broadcast, megagroup, forum):
    """
    Property: For any entity attributes, classification returns valid source type
    """
    entity = create_mock_entity(broadcast=broadcast, megagroup=megagroup, forum=forum)
    result = SourceDetector.detect_source_type(entity)
    
    assert result in ['channel', 'chat', 'forum_chat']
    
    # Verify classification rules
    if broadcast:
        assert result == 'channel'
    elif forum:
        assert result == 'forum_chat'
    elif megagroup:
        assert result == 'chat'

# Feature: chat-and-topic-support, Property 8: Link format correctness for chats
@given(
    chatname=st.text(min_size=1, max_size=32, alphabet=st.characters(whitelist_categories=('Ll', 'Lu', 'Nd'))),
    message_id=st.integers(min_value=1, max_value=999999),
    is_private=st.booleans()
)
@settings(max_examples=100)
def test_chat_link_format_property(chatname, message_id, is_private):
    """
    Property: For any chat parameters, link format is correct
    """
    entity = create_mock_chat_entity(chatname=chatname, is_private=is_private)
    link = LinkFormatter.format_chat_message_link(
        f"https://t.me/{chatname}", entity, message_id, is_private
    )
    
    if link is not None:
        assert link.startswith('https://t.me/')
        assert str(message_id) in link
        assert 'None' not in link
        
        if is_private:
            assert '/c/' in link
        else:
            assert chatname in link

# Feature: chat-and-topic-support, Property 14: Entity caching with metadata
@given(
    source_type=st.sampled_from(['channel', 'chat', 'forum_chat']),
    entity_id=st.integers(min_value=1, max_value=999999)
)
@settings(max_examples=100)
def test_entity_caching_with_metadata_property(source_type, entity_id):
    """
    Property: For any entity, caching preserves entity and metadata
    """
    cache_manager = CacheManager()
    entity = create_mock_entity(id=entity_id, source_type=source_type)
    link = f"https://t.me/test_{entity_id}"
    
    # Cache entity with metadata
    cache_manager.save_entity(link, entity, source_type)
    
    # Retrieve from cache
    cached_entity, cached_type = cache_manager.get_entity_with_type(link)
    
    assert cached_entity is not None
    assert cached_entity.id == entity_id
    assert cached_type == source_type
```

#### 2. Unit Tests (pytest)

**Для конкретных примеров и edge cases**:

```python
def test_source_detector_with_user_entity():
    """Example: User entity should be classified as chat"""
    user_entity = create_user_entity()
    result = SourceDetector.detect_source_type(user_entity)
    assert result == 'chat'

def test_source_detector_with_missing_attributes():
    """Edge case: Entity without attributes defaults to channel"""
    entity = create_entity_without_attributes()
    result = SourceDetector.detect_source_type(entity)
    assert result == 'channel'

def test_link_formatter_with_none_entity():
    """Edge case: None entity returns None link"""
    link = LinkFormatter.format_chat_message_link("https://t.me/test", None, 123)
    assert link is None

def test_error_handler_chat_admin_required():
    """Example: ChatAdminRequiredError is handled correctly"""
    error_handler = ErrorHandler()
    error = ChatAdminRequiredError()
    error_handler.handle_chat_access_error(error, "test_chat")
    
    recommendations = error_handler.get_access_error_recommendations('ChatAdminRequiredError')
    assert 'администратора' in recommendations.lower()
```

#### 3. Integration Tests (pytest с моками)

**Для компонентов с внешними зависимостями**:

```python
@pytest.mark.asyncio
async def test_message_fetcher_chat_integration(mock_telegram_client):
    """Integration: MessageFetcher correctly fetches chat messages"""
    # Mock Telegram API
    mock_telegram_client.iter_messages.return_value = create_mock_messages(count=10)
    
    fetcher = MessageFetcher(connection_manager, cache_manager, error_handler)
    messages = await fetcher.fetch_chat_messages(
        "https://t.me/test_chat",
        datetime(2024, 1, 1),
        datetime(2024, 1, 31),
        source_type='chat'
    )
    
    assert len(messages) == 10
    assert all(msg.source_type == 'chat' for msg in messages)

@pytest.mark.asyncio
async def test_topic_manager_get_topics_integration(mock_telegram_client):
    """Integration: TopicManager correctly retrieves forum topics"""
    # Mock get_forum_topics API call
    mock_topics = [
        create_mock_forum_topic(id=1, title="Topic 1"),
        create_mock_forum_topic(id=2, title="Topic 2")
    ]
    mock_telegram_client.get_forum_topics.return_value = mock_topics
    
    topic_manager = TopicManager(connection_manager)
    topics = await topic_manager.get_forum_topics(mock_chat_entity)
    
    assert len(topics) == 2
    assert topics[0] == (1, "Topic 1")
    assert topics[1] == (2, "Topic 2")

def test_database_stats_by_source_type_integration():
    """Integration: Database correctly calculates stats by source type"""
    db = Database(":memory:")
    
    # Insert test data
    db.add_message(create_message(source_type='channel'))
    db.add_message(create_message(source_type='chat'))
    db.add_message(create_message(source_type='forum_chat', topic_id=1))
    
    stats = db.get_stats_by_source_type()
    
    assert stats['by_source_type']['channel'] == 1
    assert stats['by_source_type']['chat'] == 1
    assert stats['by_source_type']['forum_chat'] == 1
```

#### 4. Smoke Tests

**Для проверки схемы БД и конфигурации**:

```python
def test_database_schema_has_source_type_field():
    """Smoke: Database schema includes source_type field"""
    db = Database(":memory:")
    cursor = db.conn.execute("PRAGMA table_info(messages)")
    columns = [row[1] for row in cursor.fetchall()]
    assert 'source_type' in columns

def test_database_schema_has_topic_fields():
    """Smoke: Database schema includes topic_id and topic_title fields"""
    db = Database(":memory:")
    cursor = db.conn.execute("PRAGMA table_info(messages)")
    columns = [row[1] for row in cursor.fetchall()]
    assert 'topic_id' in columns
    assert 'topic_title' in columns

def test_database_indexes_exist():
    """Smoke: Required indexes are created"""
    db = Database(":memory:")
    cursor = db.conn.execute("PRAGMA index_list(messages)")
    indexes = [row[1] for row in cursor.fetchall()]
    assert 'idx_messages_source_type' in indexes
    assert 'idx_messages_topic_id' in indexes
```

### Test Coverage Goals

- **Property Tests**: 17 properties × 100 iterations = 1700+ test cases
- **Unit Tests**: ~30 конкретных примеров и edge cases
- **Integration Tests**: ~15 тестов с моками внешних зависимостей
- **Smoke Tests**: ~10 тестов схемы и конфигурации

**Общее покрытие**: >95% для новых компонентов, 100% для критических путей (SourceDetector, LinkFormatter)

### Backward Compatibility Testing

**Критически важно**: Все существующие тесты для парсинга каналов должны проходить без изменений.

```python
def test_backward_compatibility_channel_parsing():
    """Regression: Existing channel parsing works unchanged"""
    # Запускаем все существующие тесты для каналов
    # Они должны проходить без модификаций
    pass

def test_backward_compatibility_channel_links():
    """Regression: Channel link format unchanged"""
    entity = create_channel_entity()
    link = LinkFormatter.format_message_link(
        "https://t.me/test_channel", entity, 123
    )
    # Формат должен быть таким же, как до изменений
    assert link == "https://t.me/test_channel/123"

def test_backward_compatibility_database_migration():
    """Regression: Existing data migrates correctly"""
    db = Database(":memory:")
    # Вставляем данные без source_type (как старые данные)
    db.conn.execute("INSERT INTO messages (channel, message_id, text, date) VALUES (?, ?, ?, ?)",
                    ("test", 1, "text", datetime.now()))
    
    # Выполняем миграцию
    db.migrate_existing_data()
    
    # Проверяем что source_type установлен в 'channel'
    cursor = db.conn.execute("SELECT source_type FROM messages WHERE message_id = 1")
    assert cursor.fetchone()[0] == 'channel'
```

## Implementation Notes

### Migration Path

1. **Phase 1: Database Schema**
   - Добавить новые поля в таблицу messages
   - Создать индексы
   - Выполнить миграцию существующих данных (source_type='channel')

2. **Phase 2: Core Components**
   - Реализовать SourceDetector
   - Реализовать TopicManager
   - Расширить LinkFormatter

3. **Phase 3: Integration**
   - Расширить MessageFetcher
   - Интегрировать с UnifiedParser
   - Обновить ErrorHandler

4. **Phase 4: Export & Statistics**
   - Обновить экспортеры
   - Добавить методы статистики
   - Обновить CacheManager

5. **Phase 5: Testing & Validation**
   - Написать property-based тесты
   - Написать unit и integration тесты
   - Проверить backward compatibility

### Performance Considerations

1. **API Rate Limiting**:
   - Применять те же задержки для чатов, что и для каналов
   - Для форум-чатов: добавить задержку между парсингом топиков
   - Использовать кэширование entity и топиков

2. **Database Performance**:
   - Индексы на source_type и topic_id для быстрых запросов
   - Batch insert для массовой вставки сообщений
   - Оптимизация запросов статистики с GROUP BY

3. **Memory Usage**:
   - Кэширование топиков только на время сессии
   - Очистка кэша entity по TTL
   - Streaming обработка больших объемов сообщений

### Security Considerations

1. **Access Control**:
   - Проверка прав доступа к чатам перед парсингом
   - Graceful handling ошибок доступа
   - Логирование попыток доступа к приватным чатам

2. **Data Privacy**:
   - Сохранение информации об авторах только для чатов (не для каналов)
   - Соблюдение настроек приватности чатов
   - Не сохранять чувствительные данные в логах

### Scalability Considerations

1. **Horizontal Scaling**:
   - Архитектура позволяет распределить парсинг разных источников по воркерам
   - Независимая обработка топиков в форум-чатах
   - Stateless компоненты (SourceDetector, LinkFormatter)

2. **Vertical Scaling**:
   - Оптимизация запросов к БД с индексами
   - Кэширование часто используемых данных
   - Batch processing для массовых операций

## Appendix

### Telegram API References

- **Entity Types**: [Telethon Entities](https://docs.telethon.dev/en/stable/concepts/entities.html)
- **Forum Topics**: [Forum Topics API](https://docs.telethon.dev/en/stable/modules/client.html#telethon.client.chats.ChatMethods.get_forum_topics)
- **Message Iteration**: [iter_messages](https://docs.telethon.dev/en/stable/modules/client.html#telethon.client.messages.MessageMethods.iter_messages)

### Database Schema

```sql
-- Полная схема таблицы messages после изменений
CREATE TABLE messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    channel TEXT NOT NULL,
    message_id INTEGER NOT NULL,
    text TEXT,
    date TIMESTAMP NOT NULL,
    author TEXT,
    views INTEGER DEFAULT 0,
    forwards INTEGER DEFAULT 0,
    replies INTEGER DEFAULT 0,
    comments TEXT DEFAULT '',
    media_type TEXT DEFAULT '',
    media_url TEXT DEFAULT '',
    source_type TEXT DEFAULT 'channel',  -- NEW
    topic_id INTEGER DEFAULT NULL,        -- NEW
    topic_title TEXT DEFAULT NULL,        -- NEW
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(channel, message_id)
);

-- Индексы
CREATE INDEX idx_messages_channel ON messages(channel);
CREATE INDEX idx_messages_date ON messages(date);
CREATE INDEX idx_messages_source_type ON messages(source_type);  -- NEW
CREATE INDEX idx_messages_topic_id ON messages(topic_id);        -- NEW
CREATE INDEX idx_messages_source_topic ON messages(source_type, topic_id);  -- NEW
```

### Configuration Example

```json
{
  "telegram": {
    "DELAY_BETWEEN_CHANNELS": 2,
    "DELAY_BETWEEN_TOPICS": 1,
    "LAZY_ENTITY_LOADING": true,
    "CACHE_TTL_SECONDS": 3600
  },
  "parser": {
    "SUPPORT_CHATS": true,
    "SUPPORT_FORUM_CHATS": true,
    "PARSE_ALL_TOPICS": true
  }
}
```

### Link Format Examples

```
# Публичный канал
https://t.me/channel_name/123

# Приватный канал
https://t.me/c/1234567890/123

# Публичный чат
https://t.me/chat_name/456

# Приватный чат
https://t.me/c/9876543210/456

# Публичный форум-чат, топик
https://t.me/forum_name/789/1011

# Приватный форум-чат, топик
https://t.me/c/1122334455/789/1011
```
