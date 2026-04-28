# -*- coding: utf-8 -*-
"""
Property-based тесты для TopicManager
Используется библиотека Hypothesis для генерации тестовых данных
"""

import pytest
from hypothesis import given, settings, strategies as st
from unittest.mock import Mock, AsyncMock, MagicMock
from src.telegram.topic_manager import TopicManager


# ============================================================================
# Стратегии для генерации тестовых данных
# ============================================================================

@st.composite
def forum_topic_strategy(draw):
    """
    Стратегия для генерации ForumTopic объектов
    
    Генерирует объекты с различными комбинациями:
    - topic_id: положительные целые числа
    - topic_title: непустые строки различной длины
    """
    topic_id = draw(st.integers(min_value=1, max_value=999999))
    topic_title = draw(st.text(min_size=1, max_size=100, alphabet=st.characters(
        whitelist_categories=('Lu', 'Ll', 'Nd', 'Zs'),
        blacklist_characters='\x00\n\r\t'
    )))
    
    # Создаем мок объекта ForumTopic
    topic = Mock()
    topic.id = topic_id
    topic.title = topic_title
    
    return topic


@st.composite
def forum_topics_list_strategy(draw):
    """
    Стратегия для генерации списка ForumTopic объектов
    """
    topics_count = draw(st.integers(min_value=0, max_value=20))
    topics = [draw(forum_topic_strategy()) for _ in range(topics_count)]
    return topics


# ============================================================================
# Property 4: Topic metadata extraction
# Validates: Requirements 3.3, 3.4, 3.5
# ============================================================================

@given(topic=forum_topic_strategy())
@settings(max_examples=100)
@pytest.mark.asyncio
async def test_property_topic_metadata_extraction(topic):
    """
    Property 4: Topic metadata extraction
    
    Для любого ForumTopic объекта, TopicManager должен корректно извлекать
    topic_id и topic_title, возвращая их как кортеж (int, str) с non-null значениями.
    
    Validates: Requirements 3.3, 3.4, 3.5
    """
    # Arrange: Создаем мок ConnectionManager и TopicManager
    mock_connection_manager = Mock()
    mock_client = AsyncMock()
    mock_connection_manager.get_client.return_value = mock_client
    
    # Создаем мок chat_entity
    mock_chat_entity = Mock()
    mock_chat_entity.id = 123456
    
    # Настраиваем мок клиента для возврата одного топика
    async def mock_iter_dialogs(*args, **kwargs):
        mock_dialog = Mock()
        mock_dialog.entity = topic
        mock_dialog.title = topic.title
        yield mock_dialog
    
    mock_client.iter_dialogs = mock_iter_dialogs
    
    topic_manager = TopicManager(mock_connection_manager)
    
    # Act: Получаем топики
    topics = await topic_manager.get_forum_topics(mock_chat_entity)
    
    # Assert: Проверяем корректность извлечения метаданных
    assert len(topics) == 1, "Должен быть извлечен ровно один топик"
    
    extracted_id, extracted_title = topics[0]
    
    # Проверяем типы
    assert isinstance(extracted_id, int), "topic_id должен быть int"
    assert isinstance(extracted_title, str), "topic_title должен быть str"
    
    # Проверяем non-null значения
    assert extracted_id is not None, "topic_id не должен быть None"
    assert extracted_title is not None, "topic_title не должен быть None"
    
    # Проверяем корректность значений
    assert extracted_id == topic.id, "topic_id должен совпадать с оригинальным"
    assert extracted_title == topic.title, "topic_title должен совпадать с оригинальным"
    
    # Проверяем что topic_id положительный
    assert extracted_id > 0, "topic_id должен быть положительным числом"
    
    # Проверяем что topic_title непустой
    assert len(extracted_title) > 0, "topic_title не должен быть пустой строкой"


@given(topics_list=forum_topics_list_strategy())
@settings(max_examples=100)
@pytest.mark.asyncio
async def test_property_multiple_topics_metadata_extraction(topics_list):
    """
    Property 4 (расширенный): Topic metadata extraction для множества топиков
    
    Для любого списка ForumTopic объектов, TopicManager должен корректно извлекать
    метаданные всех топиков.
    
    Validates: Requirements 3.3, 3.4, 3.5
    """
    # Arrange
    mock_connection_manager = Mock()
    mock_client = AsyncMock()
    mock_connection_manager.get_client.return_value = mock_client
    
    mock_chat_entity = Mock()
    mock_chat_entity.id = 123456
    
    # Настраиваем мок клиента для возврата списка топиков
    async def mock_iter_dialogs(*args, **kwargs):
        for topic in topics_list:
            mock_dialog = Mock()
            mock_dialog.entity = topic
            mock_dialog.title = topic.title
            yield mock_dialog
    
    mock_client.iter_dialogs = mock_iter_dialogs
    
    topic_manager = TopicManager(mock_connection_manager)
    
    # Act
    extracted_topics = await topic_manager.get_forum_topics(mock_chat_entity)
    
    # Assert: Проверяем количество
    assert len(extracted_topics) == len(topics_list), \
        "Количество извлеченных топиков должно совпадать с оригинальным"
    
    # Проверяем каждый топик
    for i, (extracted_id, extracted_title) in enumerate(extracted_topics):
        original_topic = topics_list[i]
        
        # Проверяем типы
        assert isinstance(extracted_id, int), f"topic_id[{i}] должен быть int"
        assert isinstance(extracted_title, str), f"topic_title[{i}] должен быть str"
        
        # Проверяем non-null
        assert extracted_id is not None, f"topic_id[{i}] не должен быть None"
        assert extracted_title is not None, f"topic_title[{i}] не должен быть None"
        
        # Проверяем корректность
        assert extracted_id == original_topic.id, \
            f"topic_id[{i}] должен совпадать с оригинальным"
        assert extracted_title == original_topic.title, \
            f"topic_title[{i}] должен совпадать с оригинальным"


# ============================================================================
# Property 5: Topic caching consistency
# Validates: Requirements 3.7, 11.3, 11.4
# ============================================================================

@given(
    chat_link=st.text(min_size=10, max_size=100),
    topics_list=forum_topics_list_strategy()
)
@settings(max_examples=100)
@pytest.mark.asyncio
async def test_property_topic_caching_consistency(chat_link, topics_list):
    """
    Property 5: Topic caching consistency
    
    Для любого форум-чата, при повторных вызовах TopicManager должен возвращать
    закэшированные данные без дополнительных API вызовов, и закэшированные данные
    должны совпадать с оригинальными.
    
    Validates: Requirements 3.7, 11.3, 11.4
    """
    # Arrange
    mock_connection_manager = Mock()
    mock_client = AsyncMock()
    mock_connection_manager.get_client.return_value = mock_client
    
    mock_chat_entity = Mock()
    mock_chat_entity.id = 123456
    
    # Счетчик вызовов API
    api_call_count = 0
    
    async def mock_iter_dialogs(*args, **kwargs):
        nonlocal api_call_count
        api_call_count += 1
        for topic in topics_list:
            mock_dialog = Mock()
            mock_dialog.entity = topic
            mock_dialog.title = topic.title
            yield mock_dialog
    
    mock_client.iter_dialogs = mock_iter_dialogs
    
    topic_manager = TopicManager(mock_connection_manager)
    
    # Act: Первый вызов - получаем топики и кэшируем
    first_call_topics = await topic_manager.get_forum_topics(mock_chat_entity)
    topic_manager.cache_topics(chat_link, first_call_topics)
    
    first_api_calls = api_call_count
    
    # Второй вызов - получаем из кэша
    cached_topics = topic_manager.get_cached_topics(chat_link)
    
    second_api_calls = api_call_count
    
    # Assert: Проверяем что API вызывался только один раз
    assert first_api_calls == 1, "API должен быть вызван один раз при первом запросе"
    assert second_api_calls == 1, "API не должен вызываться при получении из кэша"
    
    # Проверяем что кэшированные данные не None
    assert cached_topics is not None, "Кэшированные данные не должны быть None"
    
    # Проверяем что кэшированные данные совпадают с оригинальными
    assert len(cached_topics) == len(first_call_topics), \
        "Количество кэшированных топиков должно совпадать с оригинальным"
    
    for i, (cached_id, cached_title) in enumerate(cached_topics):
        original_id, original_title = first_call_topics[i]
        
        assert cached_id == original_id, \
            f"Кэшированный topic_id[{i}] должен совпадать с оригинальным"
        assert cached_title == original_title, \
            f"Кэшированный topic_title[{i}] должен совпадать с оригинальным"


@given(
    chat_links=st.lists(
        st.text(min_size=10, max_size=50),
        min_size=1,
        max_size=10,
        unique=True
    )
)
@settings(max_examples=100)
def test_property_cache_isolation(chat_links):
    """
    Property 5 (расширенный): Cache isolation
    
    Кэш для разных чатов должен быть изолирован - изменение кэша одного чата
    не должно влиять на кэш других чатов.
    
    Validates: Requirements 3.7, 11.3, 11.4
    """
    # Arrange
    mock_connection_manager = Mock()
    topic_manager = TopicManager(mock_connection_manager)
    
    # Создаем уникальные топики для каждого чата
    chat_topics = {}
    for i, chat_link in enumerate(chat_links):
        topics = [(i * 100 + j, f"Topic {i}-{j}") for j in range(3)]
        chat_topics[chat_link] = topics
        topic_manager.cache_topics(chat_link, topics)
    
    # Act & Assert: Проверяем изоляцию кэша
    for chat_link in chat_links:
        cached = topic_manager.get_cached_topics(chat_link)
        expected = chat_topics[chat_link]
        
        assert cached is not None, f"Кэш для {chat_link} не должен быть None"
        assert cached == expected, \
            f"Кэшированные данные для {chat_link} должны совпадать с ожидаемыми"
        
        # Проверяем что кэш других чатов не затронут
        for other_link in chat_links:
            if other_link != chat_link:
                other_cached = topic_manager.get_cached_topics(other_link)
                assert other_cached == chat_topics[other_link], \
                    f"Кэш для {other_link} не должен быть изменен"


@given(
    chat_link=st.text(min_size=10, max_size=100),
    topics_list=forum_topics_list_strategy()
)
@settings(max_examples=100)
def test_property_cache_clear_consistency(chat_link, topics_list):
    """
    Property 5 (расширенный): Cache clear consistency
    
    После очистки кэша, get_cached_topics должен возвращать None.
    
    Validates: Requirements 3.7, 11.3, 11.4
    """
    # Arrange
    mock_connection_manager = Mock()
    topic_manager = TopicManager(mock_connection_manager)
    
    # Преобразуем моки в кортежи
    topics_tuples = [(topic.id, topic.title) for topic in topics_list]
    
    # Кэшируем топики
    topic_manager.cache_topics(chat_link, topics_tuples)
    
    # Проверяем что топики в кэше
    assert topic_manager.get_cached_topics(chat_link) is not None
    
    # Act: Очищаем кэш
    topic_manager.clear_cache(chat_link)
    
    # Assert: Проверяем что кэш очищен
    assert topic_manager.get_cached_topics(chat_link) is None, \
        "После очистки кэша get_cached_topics должен возвращать None"
