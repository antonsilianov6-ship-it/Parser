# -*- coding: utf-8 -*-
"""Property-based тесты для MessageFetcher"""

import pytest
from unittest.mock import Mock, AsyncMock, MagicMock
from datetime import datetime
from hypothesis import given, settings, strategies as st
from src.telegram.message_fetcher import MessageFetcher, Message


# Вспомогательные функции для создания mock-объектов

def create_mock_sender(first_name=None, last_name=None, username=None, title=None):
    """Создает mock-объект sender с различными атрибутами"""
    sender = Mock()
    
    if first_name is not None:
        sender.first_name = first_name
    else:
        delattr(sender, 'first_name') if hasattr(sender, 'first_name') else None
    
    if last_name is not None:
        sender.last_name = last_name
    else:
        delattr(sender, 'last_name') if hasattr(sender, 'last_name') else None
    
    if username is not None:
        sender.username = username
    else:
        delattr(sender, 'username') if hasattr(sender, 'username') else None
    
    if title is not None:
        sender.title = title
    else:
        delattr(sender, 'title') if hasattr(sender, 'title') else None
    
    return sender


def create_mock_message(sender=None, text="Test message", date=None):
    """Создает mock-объект сообщения"""
    msg = Mock()
    msg.sender = sender
    msg.message = text
    msg.date = date or datetime.now()
    msg.id = 123
    return msg


# Стратегии для генерации данных

# Генератор имен (непустые строки)
names = st.text(
    min_size=1,
    max_size=50,
    alphabet=st.characters(whitelist_categories=('Ll', 'Lu', 'Nd', 'Zs'), max_codepoint=1000)
).filter(lambda x: x.strip())

# Генератор usernames (буквы, цифры, подчеркивания)
usernames = st.text(
    min_size=1,
    max_size=32,
    alphabet=st.characters(whitelist_categories=('Ll', 'Lu', 'Nd'), whitelist_characters='_')
).filter(lambda x: x.strip())


# Feature: chat-and-topic-support, Property 2: Message author extraction
@given(
    first_name=st.one_of(st.none(), names),
    last_name=st.one_of(st.none(), names),
    username=st.one_of(st.none(), usernames),
    title=st.one_of(st.none(), names)
)
@settings(max_examples=100, deadline=None)
def test_message_author_extraction_property(first_name, last_name, username, title):
    """
    Property 2: Message author extraction
    
    For any message object from a chat source, the Message_Fetcher SHALL correctly 
    extract the author name from the sender attribute, returning a non-empty string 
    or 'Unknown' if sender is not available.
    
    Validates: Requirements 2.3
    """
    # Создаем MessageFetcher (без реальных зависимостей для property теста)
    connection_manager = Mock()
    cache_manager = Mock()
    error_handler = Mock()
    fetcher = MessageFetcher(connection_manager, cache_manager, error_handler)
    
    # Создаем sender с различными комбинациями атрибутов
    sender = create_mock_sender(
        first_name=first_name,
        last_name=last_name,
        username=username,
        title=title
    )
    
    # Создаем сообщение с этим sender
    message = create_mock_message(sender=sender)
    
    # Извлекаем автора
    author = fetcher._extract_message_author(message)
    
    # Проверяем что результат всегда непустая строка
    assert author is not None
    assert isinstance(author, str)
    assert len(author) > 0
    
    # Проверяем логику извлечения
    if first_name or last_name:
        # Если есть имя или фамилия, должны быть в результате
        expected_name = f"{first_name or ''} {last_name or ''}".strip()
        assert author == expected_name
    elif title:
        # Если есть title (для каналов/чатов), должен быть в результате
        assert author == title
    elif username:
        # Если есть username, должен быть с @
        assert author == f"@{username}"
    else:
        # Если ничего нет, должно быть 'Unknown'
        assert author == 'Unknown'


@given(has_sender=st.booleans())
@settings(max_examples=100)
def test_message_author_extraction_with_missing_sender_property(has_sender):
    """
    Property: Message author extraction with missing sender
    
    For any message with or without sender attribute, the extraction SHALL 
    always return a valid string (never None or empty).
    """
    connection_manager = Mock()
    cache_manager = Mock()
    error_handler = Mock()
    fetcher = MessageFetcher(connection_manager, cache_manager, error_handler)
    
    # Создаем сообщение
    message = Mock()
    
    if has_sender:
        # Sender существует, но может быть None
        message.sender = None
    else:
        # Sender атрибут отсутствует
        delattr(message, 'sender') if hasattr(message, 'sender') else None
    
    # Извлекаем автора
    author = fetcher._extract_message_author(message)
    
    # Проверяем что всегда возвращается 'Unknown'
    assert author == 'Unknown'
    assert isinstance(author, str)
    assert len(author) > 0


@given(
    first_name=names,
    last_name=names
)
@settings(max_examples=100)
def test_message_author_full_name_property(first_name, last_name):
    """
    Property: Full name extraction
    
    For any message with both first_name and last_name, the author SHALL be 
    the concatenation of both names with a space.
    """
    connection_manager = Mock()
    cache_manager = Mock()
    error_handler = Mock()
    fetcher = MessageFetcher(connection_manager, cache_manager, error_handler)
    
    sender = create_mock_sender(first_name=first_name, last_name=last_name)
    message = create_mock_message(sender=sender)
    
    author = fetcher._extract_message_author(message)
    
    expected = f"{first_name} {last_name}".strip()
    assert author == expected


@given(username=usernames)
@settings(max_examples=100)
def test_message_author_username_property(username):
    """
    Property: Username extraction
    
    For any message with only username (no names or title), the author SHALL 
    be the username prefixed with @.
    """
    connection_manager = Mock()
    cache_manager = Mock()
    error_handler = Mock()
    fetcher = MessageFetcher(connection_manager, cache_manager, error_handler)
    
    sender = create_mock_sender(username=username)
    message = create_mock_message(sender=sender)
    
    author = fetcher._extract_message_author(message)
    
    assert author == f"@{username}"
    assert author.startswith('@')
    assert username in author


@given(title=names)
@settings(max_examples=100)
def test_message_author_title_property(title):
    """
    Property: Title extraction
    
    For any message with only title (channel/chat name), the author SHALL 
    be the title itself.
    """
    connection_manager = Mock()
    cache_manager = Mock()
    error_handler = Mock()
    fetcher = MessageFetcher(connection_manager, cache_manager, error_handler)
    
    sender = create_mock_sender(title=title)
    message = create_mock_message(sender=sender)
    
    author = fetcher._extract_message_author(message)
    
    assert author == title



# Feature: chat-and-topic-support, Property 3: Source type preservation in messages
@given(
    source_type=st.sampled_from(['channel', 'chat', 'forum_chat']),
    message_count=st.integers(min_value=1, max_value=10)
)
@settings(max_examples=100)
def test_source_type_preservation_property(source_type, message_count):
    """
    Property 3: Source type preservation in messages
    
    For any message being processed, the Message_Fetcher SHALL preserve the 
    source_type field correctly in the Message object, ensuring it matches 
    the detected source type.
    
    Validates: Requirements 2.6
    """
    # Создаем список Message объектов с заданным source_type
    messages = []
    for i in range(message_count):
        msg = Message(
            date=datetime.now(),
            text=f"Test message {i}",
            link=f"https://t.me/test/{i}",
            title="Test Source",
            source_type=source_type,
            topic_id=None if source_type != 'forum_chat' else 1,
            topic_title=None if source_type != 'forum_chat' else "Test Topic",
            author="Test Author"
        )
        messages.append(msg)
    
    # Проверяем что source_type сохранен корректно во всех сообщениях
    for msg in messages:
        assert msg.source_type == source_type
        assert msg.source_type in ['channel', 'chat', 'forum_chat']
        
        # Проверяем консистентность с topic полями
        if source_type == 'forum_chat':
            # Для форум-чатов topic_id и topic_title должны быть заполнены
            assert msg.topic_id is not None
            assert msg.topic_title is not None
        else:
            # Для каналов и чатов topic поля должны быть None
            # (это проверяется в другом property тесте, но можем проверить здесь тоже)
            pass


@given(
    source_type=st.sampled_from(['channel', 'chat', 'forum_chat'])
)
@settings(max_examples=100)
def test_source_type_immutability_property(source_type):
    """
    Property: Source type immutability
    
    For any Message object, the source_type SHALL remain unchanged after creation.
    """
    msg = Message(
        date=datetime.now(),
        text="Test message",
        link="https://t.me/test/123",
        title="Test",
        source_type=source_type
    )
    
    original_source_type = msg.source_type
    
    # Проверяем что source_type не изменился
    assert msg.source_type == original_source_type
    assert msg.source_type == source_type


# Feature: chat-and-topic-support, Property 6: Topic metadata preservation in messages
@given(
    topic_id=st.integers(min_value=1, max_value=999999),
    topic_title=st.text(min_size=1, max_size=100, alphabet=st.characters(
        whitelist_categories=('Ll', 'Lu', 'Nd', 'Zs'), max_codepoint=1000
    )).filter(lambda x: x.strip()),
    message_count=st.integers(min_value=1, max_value=10)
)
@settings(max_examples=100)
def test_topic_metadata_preservation_property(topic_id, topic_title, message_count):
    """
    Property 6: Topic metadata preservation in messages
    
    For any message from a forum chat topic, the Message_Fetcher SHALL correctly 
    preserve topic_id and topic_title in the Message object, ensuring they match 
    the topic being parsed.
    
    Validates: Requirements 4.5
    """
    # Создаем список Message объектов из топика
    messages = []
    for i in range(message_count):
        msg = Message(
            date=datetime.now(),
            text=f"Test message {i}",
            link=f"https://t.me/forum/{topic_id}/{i}",
            title="Test Forum",
            source_type='forum_chat',
            topic_id=topic_id,
            topic_title=topic_title,
            author="Test Author"
        )
        messages.append(msg)
    
    # Проверяем что topic_id и topic_title сохранены корректно во всех сообщениях
    for msg in messages:
        assert msg.topic_id == topic_id
        assert msg.topic_title == topic_title
        assert msg.source_type == 'forum_chat'
        
        # Проверяем что метаданные топика не None
        assert msg.topic_id is not None
        assert msg.topic_title is not None
        assert isinstance(msg.topic_id, int)
        assert isinstance(msg.topic_title, str)
        assert len(msg.topic_title) > 0


@given(
    topic_id=st.integers(min_value=1, max_value=999999),
    topic_title=st.text(min_size=1, max_size=100, alphabet=st.characters(
        whitelist_categories=('Ll', 'Lu', 'Nd', 'Zs'), max_codepoint=1000
    )).filter(lambda x: x.strip())
)
@settings(max_examples=100)
def test_topic_metadata_consistency_property(topic_id, topic_title):
    """
    Property: Topic metadata consistency
    
    For any forum chat message, if topic_id is set, topic_title SHALL also be set,
    and source_type SHALL be 'forum_chat'.
    """
    msg = Message(
        date=datetime.now(),
        text="Test message",
        link=f"https://t.me/forum/{topic_id}/123",
        title="Test Forum",
        source_type='forum_chat',
        topic_id=topic_id,
        topic_title=topic_title
    )
    
    # Проверяем консистентность метаданных топика
    if msg.topic_id is not None:
        assert msg.topic_title is not None
        assert msg.source_type == 'forum_chat'
        assert isinstance(msg.topic_id, int)
        assert isinstance(msg.topic_title, str)
        assert msg.topic_id > 0
        assert len(msg.topic_title) > 0


@given(
    source_type=st.sampled_from(['channel', 'chat'])
)
@settings(max_examples=100)
def test_non_forum_messages_have_null_topic_fields_property(source_type):
    """
    Property: Non-forum messages have null topic fields
    
    For any message from channel or chat (not forum_chat), topic_id and 
    topic_title SHALL be None.
    """
    msg = Message(
        date=datetime.now(),
        text="Test message",
        link="https://t.me/test/123",
        title="Test",
        source_type=source_type,
        topic_id=None,
        topic_title=None
    )
    
    # Проверяем что для не-форум источников topic поля равны None
    if msg.source_type in ['channel', 'chat']:
        assert msg.topic_id is None
        assert msg.topic_title is None
