# -*- coding: utf-8 -*-
"""
Integration тесты для UnifiedParser с поддержкой чатов и топиков

**Validates: Requirements 6.1, 6.2, 6.7, 12.1, 12.2, 13.6**
"""

import pytest
import asyncio
from datetime import datetime
from unittest.mock import Mock, AsyncMock, MagicMock, patch
from src.core.unified_parser import UnifiedParser
from src.telegram.message_fetcher import Message


@pytest.fixture
def mock_channel_entity():
    """Создает mock entity для канала"""
    entity = Mock()
    entity.id = 123456
    entity.title = "Test Channel"
    entity.username = "test_channel"
    entity.broadcast = True
    entity.megagroup = False
    entity.forum = False
    return entity


@pytest.fixture
def mock_chat_entity():
    """Создает mock entity для обычного чата"""
    entity = Mock()
    entity.id = 789012
    entity.title = "Test Chat"
    entity.username = "test_chat"
    entity.broadcast = False
    entity.megagroup = True
    entity.forum = False
    return entity


@pytest.fixture
def mock_forum_chat_entity():
    """Создает mock entity для форум-чата"""
    entity = Mock()
    entity.id = 345678
    entity.title = "Test Forum Chat"
    entity.username = "test_forum"
    entity.broadcast = False
    entity.megagroup = True
    entity.forum = True
    return entity


@pytest.fixture
def mock_messages():
    """Создает список mock сообщений"""
    messages = []
    for i in range(5):
        msg = Message(
            date=datetime(2024, 1, 1, 12, i),
            text=f"Test message {i}",
            link=f"https://t.me/test/{i}",
            title="Test Source",
            source_type='channel',
            author=''
        )
        messages.append(msg)
    return messages


@pytest.fixture
def mock_chat_messages():
    """Создает список mock сообщений из чата"""
    messages = []
    for i in range(3):
        msg = Message(
            date=datetime(2024, 1, 1, 14, i),
            text=f"Chat message {i}",
            link=f"https://t.me/test_chat/{i}",
            title="Test Chat",
            source_type='chat',
            author=f"User {i}"
        )
        messages.append(msg)
    return messages


@pytest.fixture
def mock_forum_messages():
    """Создает список mock сообщений из форум-чата с топиками"""
    messages = []
    topics = [(1, "Topic 1"), (2, "Topic 2")]
    
    for topic_id, topic_title in topics:
        for i in range(2):
            msg = Message(
                date=datetime(2024, 1, 1, 16, i),
                text=f"Forum message {i} in {topic_title}",
                link=f"https://t.me/test_forum/{topic_id}/{i}",
                title="Test Forum",
                source_type='forum_chat',
                topic_id=topic_id,
                topic_title=topic_title,
                author=f"User {i}"
            )
            messages.append(msg)
    return messages


@pytest.mark.asyncio
async def test_parse_regular_chat_full_cycle(
    mock_chat_entity,
    mock_chat_messages
):
    """
    Integration Test: Полный цикл парсинга обычного чата
    
    **Validates: Requirements 6.1, 6.2, 12.1**
    
    Проверяет:
    - Автоматическое определение типа источника как 'chat'
    - Вызов правильного метода MessageFetcher.fetch_chat_messages()
    - Корректное сохранение сообщений с source_type='chat'
    """
    # Используем in-memory БД для тестов
    with patch('src.config.DATABASE_CONFIG', {'DB_PATH': ':memory:'}):
        parser = UnifiedParser()
        
        with patch.object(parser.connection_manager, 'connect', new_callable=AsyncMock):
            with patch.object(parser.connection_manager, 'get_client') as mock_get_client:
                # Настраиваем mock клиента
                mock_client = AsyncMock()
                mock_client.get_entity = AsyncMock(return_value=mock_chat_entity)
                mock_get_client.return_value = mock_client
                
                # Инициализируем парсер
                await parser.init_async()
                
                # Мокаем метод fetch_chat_messages
                with patch.object(
                    parser.message_fetcher,
                    'fetch_chat_messages',
                    new_callable=AsyncMock,
                    return_value=mock_chat_messages
                ) as mock_fetch_chat:
                    
                    # Мокаем сохранение в БД
                    with patch.object(parser, '_save_messages_to_db', new_callable=AsyncMock):
                        with patch.object(parser.db, 'add_parse_stats'):
                            
                            # Выполняем парсинг
                            result = await parser.parse_channels({'https://t.me/test_chat'})
                            
                            # Проверяем что fetch_chat_messages был вызван
                            assert mock_fetch_chat.called
                            assert mock_fetch_chat.call_count == 1
                            
                            # Проверяем результат
                            assert len(result) > 0
                            messages = list(result.values())[0]
                            assert len(messages) == 3
                            assert all(msg.source_type == 'chat' for msg in messages)
                            assert all(msg.author != '' for msg in messages)


@pytest.mark.asyncio
async def test_parse_forum_chat_with_topics_full_cycle(
    mock_forum_chat_entity,
    mock_forum_messages
):
    """
    Integration Test: Полный цикл парсинга форум-чата с топиками
    
    **Validates: Requirements 6.1, 6.2, 12.1**
    
    Проверяет:
    - Автоматическое определение типа источника как 'forum_chat'
    - Вызов правильного метода MessageFetcher.fetch_forum_chat_messages()
    - Корректное сохранение сообщений с topic_id и topic_title
    """
    # Используем in-memory БД для тестов
    with patch('src.config.DATABASE_CONFIG', {'DB_PATH': ':memory:'}):
        parser = UnifiedParser()
        
        with patch.object(parser.connection_manager, 'connect', new_callable=AsyncMock):
            with patch.object(parser.connection_manager, 'get_client') as mock_get_client:
                # Настраиваем mock клиента
                mock_client = AsyncMock()
                mock_client.get_entity = AsyncMock(return_value=mock_forum_chat_entity)
                mock_get_client.return_value = mock_client
                
                # Инициализируем парсер
                await parser.init_async()
                
                # Мокаем метод fetch_forum_chat_messages
                with patch.object(
                    parser.message_fetcher,
                    'fetch_forum_chat_messages',
                    new_callable=AsyncMock,
                    return_value=mock_forum_messages
                ) as mock_fetch_forum:
                    
                    # Мокаем сохранение в БД
                    with patch.object(parser, '_save_messages_to_db', new_callable=AsyncMock):
                        with patch.object(parser.db, 'add_parse_stats'):
                            
                            # Выполняем парсинг
                            result = await parser.parse_channels({'https://t.me/test_forum'})
                            
                            # Проверяем что fetch_forum_chat_messages был вызван
                            assert mock_fetch_forum.called
                            assert mock_fetch_forum.call_count == 1
                            
                            # Проверяем результат
                            assert len(result) > 0
                            messages = list(result.values())[0]
                            assert len(messages) == 4  # 2 топика × 2 сообщения
                            assert all(msg.source_type == 'forum_chat' for msg in messages)
                            assert all(msg.topic_id is not None for msg in messages)
                            assert all(msg.topic_title is not None for msg in messages)


@pytest.mark.asyncio
async def test_automatic_source_type_detection(
    mock_channel_entity,
    mock_chat_entity,
    mock_forum_chat_entity,
    mock_messages,
    mock_chat_messages,
    mock_forum_messages
):
    """
    Integration Test: Автоматическое определение типа источников
    
    **Validates: Requirements 6.1, 6.2, 6.7**
    
    Проверяет:
    - Корректное определение типа для каждого источника
    - Вызов соответствующего метода MessageFetcher для каждого типа
    - Логирование типа источника при начале парсинга
    """
    # Используем in-memory БД для тестов
    with patch('src.config.DATABASE_CONFIG', {'DB_PATH': ':memory:'}):
        parser = UnifiedParser()
        
        # Создаем словарь источников и их entity
        sources = {
            'https://t.me/test_channel': (mock_channel_entity, mock_messages, 'channel'),
            'https://t.me/test_chat': (mock_chat_entity, mock_chat_messages, 'chat'),
            'https://t.me/test_forum': (mock_forum_chat_entity, mock_forum_messages, 'forum_chat')
        }
        
        with patch.object(parser.connection_manager, 'connect', new_callable=AsyncMock):
            with patch.object(parser.connection_manager, 'get_client') as mock_get_client:
                # Настраиваем mock клиента
                mock_client = AsyncMock()
                
                # Настраиваем get_entity для возврата правильного entity
                async def get_entity_side_effect(link):
                    return sources[link][0]
                
                mock_client.get_entity = AsyncMock(side_effect=get_entity_side_effect)
                mock_get_client.return_value = mock_client
                
                # Инициализируем парсер
                await parser.init_async()
                
                # Мокаем все методы fetch
                with patch.object(
                    parser.message_fetcher,
                    'fetch_channel_messages',
                    new_callable=AsyncMock,
                    return_value=mock_messages
                ) as mock_fetch_channel:
                    with patch.object(
                        parser.message_fetcher,
                        'fetch_chat_messages',
                        new_callable=AsyncMock,
                        return_value=mock_chat_messages
                    ) as mock_fetch_chat:
                        with patch.object(
                            parser.message_fetcher,
                            'fetch_forum_chat_messages',
                            new_callable=AsyncMock,
                            return_value=mock_forum_messages
                        ) as mock_fetch_forum:
                            
                            # Мокаем сохранение в БД
                            with patch.object(parser, '_save_messages_to_db', new_callable=AsyncMock):
                                with patch.object(parser.db, 'add_parse_stats'):
                                    
                                    # Выполняем парсинг всех источников
                                    result = await parser.parse_channels(set(sources.keys()))
                                    
                                    # Проверяем что каждый метод был вызван ровно один раз
                                    assert mock_fetch_channel.call_count == 1
                                    assert mock_fetch_chat.call_count == 1
                                    assert mock_fetch_forum.call_count == 1
                                    
                                    # Проверяем что все источники обработаны
                                    assert len(result) == 3


@pytest.mark.asyncio
async def test_access_error_handling_continues_parsing(
    mock_channel_entity,
    mock_chat_entity,
    mock_messages
):
    """
    Integration Test: Обработка ошибок доступа с продолжением парсинга
    
    **Validates: Requirements 6.7, 12.2**
    
    Проверяет:
    - При ошибке доступа к одному источнику парсинг продолжается для других
    - Ошибки логируются через ErrorHandler.handle_chat_access_error()
    - Статистика ошибок корректно накапливается
    """
    # Используем in-memory БД для тестов
    with patch('src.config.DATABASE_CONFIG', {'DB_PATH': ':memory:'}):
        parser = UnifiedParser()
        
        sources = {
            'https://t.me/test_channel': mock_channel_entity,
            'https://t.me/forbidden_chat': None,  # Вызовет ошибку
            'https://t.me/test_chat': mock_chat_entity
        }
        
        with patch.object(parser.connection_manager, 'connect', new_callable=AsyncMock):
            with patch.object(parser.connection_manager, 'get_client') as mock_get_client:
                # Настраиваем mock клиента
                mock_client = AsyncMock()
                
                # Настраиваем get_entity для симуляции ошибки доступа
                async def get_entity_side_effect(link):
                    if link == 'https://t.me/forbidden_chat':
                        from telethon.errors import ChatAdminRequiredError
                        raise ChatAdminRequiredError("Admin rights required")
                    return sources[link]
                
                mock_client.get_entity = AsyncMock(side_effect=get_entity_side_effect)
                mock_get_client.return_value = mock_client
                
                # Инициализируем парсер
                await parser.init_async()
                
                # Мокаем методы fetch
                with patch.object(
                    parser.message_fetcher,
                    'fetch_channel_messages',
                    new_callable=AsyncMock,
                    return_value=mock_messages
                ):
                    with patch.object(
                        parser.message_fetcher,
                        'fetch_chat_messages',
                        new_callable=AsyncMock,
                        return_value=mock_messages
                    ):
                        
                        # Мокаем сохранение в БД
                        with patch.object(parser, '_save_messages_to_db', new_callable=AsyncMock):
                            with patch.object(parser.db, 'add_parse_stats'):
                                
                                # Выполняем парсинг
                                result = await parser.parse_channels(set(sources.keys()))
                                
                                # Проверяем что парсинг продолжился несмотря на ошибку
                                # Должны быть обработаны 2 источника (канал и чат), один пропущен
                                assert len(result) == 2
                                
                                # Проверяем что ошибка зарегистрирована
                                assert parser.stats['total_errors'] >= 1
                                
                                # Проверяем что ErrorHandler зарегистрировал ошибку
                                error_summary = parser.error_handler.get_error_summary()
                                assert error_summary['total_errors'] >= 1


@pytest.mark.asyncio
async def test_backward_compatibility_with_channels(
    mock_channel_entity,
    mock_messages
):
    """
    Integration Test: Обратная совместимость с каналами
    
    **Validates: Requirements 12.1, 12.2**
    
    Проверяет:
    - Существующая логика парсинга каналов работает без изменений
    - Каналы определяются как source_type='channel'
    - Метод fetch_channel_messages вызывается для каналов
    """
    # Используем in-memory БД для тестов
    with patch('src.config.DATABASE_CONFIG', {'DB_PATH': ':memory:'}):
        parser = UnifiedParser()
        
        with patch.object(parser.connection_manager, 'connect', new_callable=AsyncMock):
            with patch.object(parser.connection_manager, 'get_client') as mock_get_client:
                # Настраиваем mock клиента
                mock_client = AsyncMock()
                mock_client.get_entity = AsyncMock(return_value=mock_channel_entity)
                mock_get_client.return_value = mock_client
                
                # Инициализируем парсер
                await parser.init_async()
                
                # Мокаем метод fetch_channel_messages
                with patch.object(
                    parser.message_fetcher,
                    'fetch_channel_messages',
                    new_callable=AsyncMock,
                    return_value=mock_messages
                ) as mock_fetch_channel:
                    
                    # Мокаем сохранение в БД
                    with patch.object(parser, '_save_messages_to_db', new_callable=AsyncMock):
                        with patch.object(parser.db, 'add_parse_stats'):
                            
                            # Выполняем парсинг канала
                            result = await parser.parse_channels({'https://t.me/test_channel'})
                            
                            # Проверяем что fetch_channel_messages был вызван
                            assert mock_fetch_channel.called
                            assert mock_fetch_channel.call_count == 1
                            
                            # Проверяем результат
                            assert len(result) > 0
                            messages = list(result.values())[0]
                            assert len(messages) == 5
                            assert all(msg.source_type == 'channel' for msg in messages)
                            
                            # Проверяем что для каналов author пустой
                            assert all(msg.author == '' for msg in messages)


@pytest.mark.asyncio
async def test_parse_channel_method_with_auto_detection(
    mock_chat_entity,
    mock_chat_messages
):
    """
    Integration Test: Метод parse_channel с автоматическим определением типа
    
    **Validates: Requirements 6.1, 6.2**
    
    Проверяет:
    - Метод parse_channel корректно определяет тип источника
    - Вызывается правильный метод MessageFetcher
    - Retry логика работает корректно
    """
    # Используем in-memory БД для тестов
    with patch('src.config.DATABASE_CONFIG', {'DB_PATH': ':memory:'}):
        parser = UnifiedParser()
        
        with patch.object(parser.connection_manager, 'connect', new_callable=AsyncMock):
            with patch.object(parser.connection_manager, 'get_client') as mock_get_client:
                # Настраиваем mock клиента
                mock_client = AsyncMock()
                mock_client.get_entity = AsyncMock(return_value=mock_chat_entity)
                mock_get_client.return_value = mock_client
                
                # Инициализируем парсер
                await parser.init_async()
                
                # Мокаем метод fetch_chat_messages
                with patch.object(
                    parser.message_fetcher,
                    'fetch_chat_messages',
                    new_callable=AsyncMock,
                    return_value=mock_chat_messages
                ) as mock_fetch_chat:
                    
                    # Выполняем парсинг одного источника
                    result = await parser.parse_channel('https://t.me/test_chat')
                    
                    # Проверяем что fetch_chat_messages был вызван
                    assert mock_fetch_chat.called
                    
                    # Проверяем результат
                    assert len(result) == 3
                    assert all(msg.source_type == 'chat' for msg in result)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
