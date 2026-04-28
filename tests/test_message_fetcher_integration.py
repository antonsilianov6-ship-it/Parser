# -*- coding: utf-8 -*-
"""Integration-тесты для MessageFetcher с моками"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, MagicMock, patch
from datetime import datetime, timedelta
from src.telegram.message_fetcher import MessageFetcher, Message
from src.telegram.connection_manager import ConnectionManager
from src.telegram.topic_manager import TopicManager
from src.cache.cache_manager import CacheManager
from src.utils.error_handler import ErrorHandler


# Вспомогательные функции для создания mock-объектов

def create_mock_entity(entity_type='channel', entity_id=123456, username='test', title='Test'):
    """Создает mock entity с нужными атрибутами"""
    entity = Mock()
    entity.id = entity_id
    entity.username = username
    entity.title = title
    
    if entity_type == 'channel':
        entity.broadcast = True
        entity.megagroup = False
        entity.forum = False
    elif entity_type == 'chat':
        entity.broadcast = False
        entity.megagroup = True
        entity.forum = False
    elif entity_type == 'forum_chat':
        entity.broadcast = False
        entity.megagroup = True
        entity.forum = True
    
    return entity


def create_mock_message(msg_id=1, text="Test", date=None, sender=None, reply_to=None):
    """Создает mock сообщение"""
    msg = Mock()
    msg.id = msg_id
    msg.message = text
    msg.date = date or datetime.now()
    msg.sender = sender
    msg.reply_to = reply_to
    msg._chat = None
    return msg


def create_mock_sender(first_name="Test", last_name="User"):
    """Создает mock sender"""
    sender = Mock()
    sender.first_name = first_name
    sender.last_name = last_name
    return sender


def create_mock_reply_to(topic_id=None, forum_topic=False):
    """Создает mock reply_to для топиков"""
    reply_to = Mock()
    if topic_id is not None:
        reply_to.reply_to_top_id = topic_id
    reply_to.forum_topic = forum_topic
    return reply_to


# Фикстуры

@pytest.fixture
def mock_connection_manager():
    """Mock ConnectionManager"""
    manager = Mock(spec=ConnectionManager)
    manager.get_client = Mock(return_value=AsyncMock())
    return manager


@pytest.fixture
def mock_cache_manager():
    """Mock CacheManager"""
    manager = Mock(spec=CacheManager)
    manager.get_entity = Mock(return_value=None)
    manager.save_entity = Mock()
    manager.is_entity_valid = Mock(return_value=False)
    return manager


@pytest.fixture
def mock_error_handler():
    """Mock ErrorHandler"""
    handler = Mock(spec=ErrorHandler)
    handler.log_error = Mock()
    handler.handle_channel_error = Mock()
    handler.handle_flood_wait = AsyncMock()
    return handler


@pytest.fixture
def mock_topic_manager():
    """Mock TopicManager"""
    manager = Mock(spec=TopicManager)
    manager.get_forum_topics = AsyncMock(return_value=[])
    return manager


@pytest.fixture
def message_fetcher(mock_connection_manager, mock_cache_manager, mock_error_handler, mock_topic_manager):
    """Создает MessageFetcher с моками"""
    fetcher = MessageFetcher(
        mock_connection_manager,
        mock_cache_manager,
        mock_error_handler,
        mock_topic_manager
    )
    return fetcher


# Integration-тесты

@pytest.mark.asyncio
async def test_fetch_chat_messages_integration(message_fetcher, mock_connection_manager):
    """
    Integration: Тест парсинга обычного чата с моком iter_messages
    
    Validates: Requirements 2.1, 2.2
    """
    # Настраиваем mock клиента
    mock_client = mock_connection_manager.get_client()
    
    # Создаем mock entity для чата
    chat_entity = create_mock_entity(entity_type='chat', username='testchat')
    
    # Создаем mock сообщения
    start_date = datetime.now() - timedelta(days=7)
    end_date = datetime.now()
    
    mock_messages = [
        create_mock_message(
            msg_id=i,
            text=f"Message {i}",
            date=start_date + timedelta(days=i),
            sender=create_mock_sender(first_name=f"User{i}")
        )
        for i in range(1, 6)
    ]
    
    # Настраиваем iter_messages для возврата mock сообщений
    async def mock_iter_messages(*args, **kwargs):
        for msg in mock_messages:
            yield msg
    
    mock_client.iter_messages = mock_iter_messages
    mock_client.get_entity = AsyncMock(return_value=chat_entity)
    
    # Вызываем fetch_chat_messages
    messages = await message_fetcher.fetch_chat_messages(
        "https://t.me/testchat",
        start_date,
        end_date
    )
    
    # Проверяем результаты
    assert len(messages) == 5
    assert all(isinstance(msg, Message) for msg in messages)
    assert all(msg.source_type == 'chat' for msg in messages)
    assert all(msg.author.startswith('User') for msg in messages)
    assert all(msg.topic_id is None for msg in messages)
    assert all(msg.topic_title is None for msg in messages)


@pytest.mark.asyncio
async def test_fetch_forum_chat_messages_integration(message_fetcher, mock_connection_manager, mock_topic_manager):
    """
    Integration: Тест парсинга форум-чата с моком iter_messages и reply_to
    
    Validates: Requirements 4.1, 4.2
    """
    # Настраиваем mock клиента
    mock_client = mock_connection_manager.get_client()
    
    # Создаем mock entity для форум-чата
    forum_entity = create_mock_entity(entity_type='forum_chat', username='testforum')
    
    # Настраиваем топики
    topics = [
        (1, "Topic 1"),
        (2, "Topic 2")
    ]
    mock_topic_manager.get_forum_topics = AsyncMock(return_value=topics)
    
    # Создаем mock сообщения для каждого топика
    start_date = datetime.now() - timedelta(days=7)
    end_date = datetime.now()
    
    topic1_messages = [
        create_mock_message(
            msg_id=i,
            text=f"Topic1 Message {i}",
            date=start_date + timedelta(days=i),
            sender=create_mock_sender(first_name=f"User{i}"),
            reply_to=create_mock_reply_to(topic_id=1, forum_topic=True)
        )
        for i in range(1, 4)
    ]
    
    topic2_messages = [
        create_mock_message(
            msg_id=i+10,
            text=f"Topic2 Message {i}",
            date=start_date + timedelta(days=i),
            sender=create_mock_sender(first_name=f"User{i+10}"),
            reply_to=create_mock_reply_to(topic_id=2, forum_topic=True)
        )
        for i in range(1, 3)
    ]
    
    # Настраиваем iter_messages для возврата сообщений по топикам
    call_count = [0]
    
    async def mock_iter_messages(*args, **kwargs):
        reply_to = kwargs.get('reply_to')
        if reply_to == 1:
            for msg in topic1_messages:
                yield msg
        elif reply_to == 2:
            for msg in topic2_messages:
                yield msg
    
    mock_client.iter_messages = mock_iter_messages
    mock_client.get_entity = AsyncMock(return_value=forum_entity)
    
    # Вызываем fetch_forum_chat_messages
    messages = await message_fetcher.fetch_forum_chat_messages(
        "https://t.me/testforum",
        start_date,
        end_date
    )
    
    # Проверяем результаты
    assert len(messages) == 5  # 3 из топика 1 + 2 из топика 2
    assert all(isinstance(msg, Message) for msg in messages)
    assert all(msg.source_type == 'forum_chat' for msg in messages)
    assert all(msg.topic_id is not None for msg in messages)
    assert all(msg.topic_title is not None for msg in messages)
    
    # Проверяем что сообщения из разных топиков
    topic1_msgs = [msg for msg in messages if msg.topic_id == 1]
    topic2_msgs = [msg for msg in messages if msg.topic_id == 2]
    assert len(topic1_msgs) == 3
    assert len(topic2_msgs) == 2


@pytest.mark.asyncio
async def test_fetch_forum_chat_with_delays_integration(message_fetcher, mock_connection_manager, mock_topic_manager):
    """
    Integration: Тест применения задержек между топиками
    
    Validates: Requirements 4.7
    """
    # Настраиваем задержки
    message_fetcher.delay_between_channels = 0.1  # Короткая задержка для теста
    message_fetcher.randomize_delay = False
    
    # Настраиваем mock клиента
    mock_client = mock_connection_manager.get_client()
    
    # Создаем mock entity для форум-чата
    forum_entity = create_mock_entity(entity_type='forum_chat', username='testforum')
    
    # Настраиваем топики
    topics = [
        (1, "Topic 1"),
        (2, "Topic 2"),
        (3, "Topic 3")
    ]
    mock_topic_manager.get_forum_topics = AsyncMock(return_value=topics)
    
    # Создаем пустые сообщения для каждого топика
    async def mock_iter_messages(*args, **kwargs):
        return
        yield  # Пустой генератор
    
    mock_client.iter_messages = mock_iter_messages
    mock_client.get_entity = AsyncMock(return_value=forum_entity)
    
    # Засекаем время выполнения
    start_time = datetime.now()
    
    messages = await message_fetcher.fetch_forum_chat_messages(
        "https://t.me/testforum",
        datetime.now() - timedelta(days=7),
        datetime.now()
    )
    
    end_time = datetime.now()
    elapsed = (end_time - start_time).total_seconds()
    
    # Проверяем что были задержки между топиками
    # 3 топика = 2 задержки по 0.1 секунды = минимум 0.2 секунды
    assert elapsed >= 0.2, f"Expected at least 0.2s delay, got {elapsed}s"


@pytest.mark.asyncio
async def test_backward_compatibility_with_channels_integration(message_fetcher, mock_connection_manager):
    """
    Integration: Тест обратной совместимости с каналами
    
    Validates: Requirements 12.3
    """
    # Настраиваем mock клиента
    mock_client = mock_connection_manager.get_client()
    
    # Создаем mock entity для канала
    channel_entity = create_mock_entity(entity_type='channel', username='testchannel')
    
    # Создаем mock сообщения
    start_date = datetime.now() - timedelta(days=7)
    end_date = datetime.now()
    
    mock_messages = [
        create_mock_message(
            msg_id=i,
            text=f"Channel Message {i}",
            date=start_date + timedelta(days=i)
        )
        for i in range(1, 6)
    ]
    
    # Настраиваем iter_messages
    async def mock_iter_messages(*args, **kwargs):
        for msg in mock_messages:
            yield msg
    
    mock_client.iter_messages = mock_iter_messages
    mock_client.get_entity = AsyncMock(return_value=channel_entity)
    
    # Вызываем fetch_channel_messages (старый метод)
    messages = await message_fetcher.fetch_channel_messages(
        "https://t.me/testchannel",
        start_date,
        end_date
    )
    
    # Проверяем результаты
    assert len(messages) == 5
    assert all(isinstance(msg, Message) for msg in messages)
    assert all(msg.source_type == 'channel' for msg in messages)
    assert all(msg.topic_id is None for msg in messages)
    assert all(msg.topic_title is None for msg in messages)
    assert all(msg.author == '' for msg in messages)  # Для каналов автор пустой


@pytest.mark.asyncio
async def test_extract_message_author_integration(message_fetcher):
    """
    Integration: Тест извлечения автора из различных типов sender
    
    Validates: Requirements 2.3
    """
    # Тест 1: Пользователь с именем и фамилией
    sender1 = create_mock_sender(first_name="John", last_name="Doe")
    msg1 = create_mock_message(sender=sender1)
    author1 = message_fetcher._extract_message_author(msg1)
    assert author1 == "John Doe"
    
    # Тест 2: Пользователь только с именем
    sender2 = Mock()
    sender2.first_name = "Alice"
    delattr(sender2, 'last_name') if hasattr(sender2, 'last_name') else None
    msg2 = create_mock_message(sender=sender2)
    author2 = message_fetcher._extract_message_author(msg2)
    assert author2 == "Alice"
    
    # Тест 3: Канал/чат с title
    sender3 = Mock()
    sender3.title = "Test Channel"
    delattr(sender3, 'first_name') if hasattr(sender3, 'first_name') else None
    delattr(sender3, 'last_name') if hasattr(sender3, 'last_name') else None
    msg3 = create_mock_message(sender=sender3)
    author3 = message_fetcher._extract_message_author(msg3)
    assert author3 == "Test Channel"
    
    # Тест 4: Пользователь с username
    sender4 = Mock()
    sender4.username = "testuser"
    delattr(sender4, 'first_name') if hasattr(sender4, 'first_name') else None
    delattr(sender4, 'last_name') if hasattr(sender4, 'last_name') else None
    delattr(sender4, 'title') if hasattr(sender4, 'title') else None
    msg4 = create_mock_message(sender=sender4)
    author4 = message_fetcher._extract_message_author(msg4)
    assert author4 == "@testuser"
    
    # Тест 5: Нет sender
    msg5 = Mock()
    msg5.sender = None
    author5 = message_fetcher._extract_message_author(msg5)
    assert author5 == "Unknown"


@pytest.mark.asyncio
async def test_fetch_topic_messages_with_filtering_integration(message_fetcher, mock_connection_manager):
    """
    Integration: Тест фильтрации сообщений по топику
    
    Validates: Requirements 4.3, 4.4
    """
    # Настраиваем mock клиента
    mock_client = mock_connection_manager.get_client()
    
    # Создаем mock entity для форум-чата
    forum_entity = create_mock_entity(entity_type='forum_chat', username='testforum')
    
    # Создаем сообщения из разных топиков
    start_date = datetime.now() - timedelta(days=7)
    end_date = datetime.now()
    
    # Сообщения из топика 1
    topic1_msg1 = create_mock_message(
        msg_id=1,
        text="Topic1 Message 1",
        date=start_date + timedelta(days=1),
        reply_to=create_mock_reply_to(topic_id=1, forum_topic=True)
    )
    
    topic1_msg2 = create_mock_message(
        msg_id=2,
        text="Topic1 Message 2",
        date=start_date + timedelta(days=2),
        reply_to=create_mock_reply_to(topic_id=1, forum_topic=True)
    )
    
    # Сообщение из топика 2 (должно быть отфильтровано)
    topic2_msg = create_mock_message(
        msg_id=3,
        text="Topic2 Message",
        date=start_date + timedelta(days=3),
        reply_to=create_mock_reply_to(topic_id=2, forum_topic=True)
    )
    
    # Сообщение не из топика (должно быть отфильтровано)
    non_topic_msg = create_mock_message(
        msg_id=4,
        text="Non-topic Message",
        date=start_date + timedelta(days=4),
        reply_to=create_mock_reply_to(topic_id=1, forum_topic=False)
    )
    
    # Настраиваем iter_messages для возврата всех сообщений
    async def mock_iter_messages(*args, **kwargs):
        for msg in [topic1_msg1, topic1_msg2, topic2_msg, non_topic_msg]:
            yield msg
    
    mock_client.iter_messages = mock_iter_messages
    
    # Вызываем fetch_topic_messages для топика 1
    messages = await message_fetcher.fetch_topic_messages(
        forum_entity,
        "https://t.me/testforum",
        topic_id=1,
        topic_title="Topic 1",
        start_date=start_date,
        end_date=end_date
    )
    
    # Проверяем что получили только сообщения из топика 1
    assert len(messages) == 2
    assert all(msg.topic_id == 1 for msg in messages)
    assert all(msg.topic_title == "Topic 1" for msg in messages)
    assert all(msg.source_type == 'forum_chat' for msg in messages)
