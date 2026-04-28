# -*- coding: utf-8 -*-
"""
Integration и unit тесты для TopicManager
Тестирование с моками Telethon API
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from telethon.errors import ChatAdminRequiredError, UserNotParticipantError
from src.telegram.topic_manager import TopicManager


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_connection_manager():
    """Фикстура для мока ConnectionManager"""
    mock_cm = Mock()
    mock_client = AsyncMock()
    mock_cm.get_client.return_value = mock_client
    return mock_cm


@pytest.fixture
def mock_chat_entity():
    """Фикстура для мока chat entity"""
    mock_entity = Mock()
    mock_entity.id = 123456789
    mock_entity.title = "Test Forum Chat"
    return mock_entity


@pytest.fixture
def topic_manager(mock_connection_manager):
    """Фикстура для создания TopicManager"""
    return TopicManager(mock_connection_manager)


# ============================================================================
# Integration тесты с моками Telethon API
# ============================================================================

@pytest.mark.asyncio
async def test_get_forum_topics_success(topic_manager, mock_connection_manager, mock_chat_entity):
    """
    Integration: Успешное получение списка топиков с моком get_forum_topics
    
    Validates: Requirements 3.1, 3.2
    """
    # Arrange: Создаем моки топиков
    mock_topic_1 = Mock()
    mock_topic_1.id = 1
    mock_topic_1.title = "General Discussion"
    
    mock_topic_2 = Mock()
    mock_topic_2.id = 2
    mock_topic_2.title = "Technical Support"
    
    mock_topic_3 = Mock()
    mock_topic_3.id = 3
    mock_topic_3.title = "Announcements"
    
    # Настраиваем мок клиента
    mock_client = mock_connection_manager.get_client.return_value
    
    async def mock_iter_dialogs(*args, **kwargs):
        for topic in [mock_topic_1, mock_topic_2, mock_topic_3]:
            mock_dialog = Mock()
            mock_dialog.entity = topic
            mock_dialog.title = topic.title
            yield mock_dialog
    
    mock_client.iter_dialogs = mock_iter_dialogs
    
    # Act: Получаем топики
    topics = await topic_manager.get_forum_topics(mock_chat_entity)
    
    # Assert: Проверяем результат
    assert len(topics) == 3, "Должно быть получено 3 топика"
    
    assert topics[0] == (1, "General Discussion")
    assert topics[1] == (2, "Technical Support")
    assert topics[2] == (3, "Announcements")
    
    # Проверяем что клиент был вызван
    mock_connection_manager.get_client.assert_called_once()


@pytest.mark.asyncio
async def test_get_forum_topics_empty_list(topic_manager, mock_connection_manager, mock_chat_entity):
    """
    Integration: Получение пустого списка топиков (форум-чат без топиков)
    
    Validates: Requirements 3.1, 3.2
    """
    # Arrange: Настраиваем мок для возврата пустого списка
    mock_client = mock_connection_manager.get_client.return_value
    
    async def mock_iter_dialogs(*args, **kwargs):
        return
        yield  # Пустой генератор
    
    mock_client.iter_dialogs = mock_iter_dialogs
    
    # Act
    topics = await topic_manager.get_forum_topics(mock_chat_entity)
    
    # Assert
    assert topics == [], "Должен быть возвращен пустой список"


@pytest.mark.asyncio
async def test_get_forum_topics_chat_admin_required_error(
    topic_manager, 
    mock_connection_manager, 
    mock_chat_entity
):
    """
    Integration: Обработка ошибки ChatAdminRequiredError
    
    Validates: Requirements 3.6
    """
    # Arrange: Настраиваем мок для выброса ChatAdminRequiredError
    mock_client = mock_connection_manager.get_client.return_value
    
    async def mock_iter_dialogs(*args, **kwargs):
        raise ChatAdminRequiredError("Admin rights required")
        yield
    
    mock_client.iter_dialogs = mock_iter_dialogs
    
    # Act: Вызываем метод (не должен выбросить исключение)
    topics = await topic_manager.get_forum_topics(mock_chat_entity)
    
    # Assert: Должен вернуть пустой список
    assert topics == [], "При ChatAdminRequiredError должен вернуться пустой список"


@pytest.mark.asyncio
async def test_get_forum_topics_user_not_participant_error(
    topic_manager, 
    mock_connection_manager, 
    mock_chat_entity
):
    """
    Integration: Обработка ошибки UserNotParticipantError
    
    Validates: Requirements 3.6
    """
    # Arrange: Настраиваем мок для выброса UserNotParticipantError
    mock_client = mock_connection_manager.get_client.return_value
    
    async def mock_iter_dialogs(*args, **kwargs):
        raise UserNotParticipantError("User is not a participant")
        yield
    
    mock_client.iter_dialogs = mock_iter_dialogs
    
    # Act
    topics = await topic_manager.get_forum_topics(mock_chat_entity)
    
    # Assert
    assert topics == [], "При UserNotParticipantError должен вернуться пустой список"


@pytest.mark.asyncio
async def test_get_forum_topics_none_entity(topic_manager):
    """
    Integration: Обработка None entity
    
    Validates: Requirements 3.1
    """
    # Act
    topics = await topic_manager.get_forum_topics(None)
    
    # Assert
    assert topics == [], "При None entity должен вернуться пустой список"


@pytest.mark.asyncio
async def test_get_forum_topics_critical_error_propagation(
    topic_manager, 
    mock_connection_manager, 
    mock_chat_entity
):
    """
    Integration: Критические ошибки должны пробрасываться выше
    
    Validates: Requirements 3.6
    """
    # Arrange: Настраиваем мок для выброса критической ошибки
    mock_client = mock_connection_manager.get_client.return_value
    
    async def mock_iter_dialogs(*args, **kwargs):
        raise RuntimeError("Critical error")
        yield
    
    mock_client.iter_dialogs = mock_iter_dialogs
    
    # Act & Assert: Критическая ошибка должна быть выброшена
    with pytest.raises(RuntimeError, match="Critical error"):
        await topic_manager.get_forum_topics(mock_chat_entity)


# ============================================================================
# Unit тесты для кэширования
# ============================================================================

def test_cache_topics_and_get_cached(topic_manager):
    """
    Unit: Кэширование и получение топиков из кэша
    
    Validates: Requirements 3.7, 11.3
    """
    # Arrange
    chat_link = "https://t.me/test_forum"
    topics = [(1, "Topic 1"), (2, "Topic 2"), (3, "Topic 3")]
    
    # Act: Кэшируем топики
    topic_manager.cache_topics(chat_link, topics)
    
    # Assert: Получаем из кэша
    cached = topic_manager.get_cached_topics(chat_link)
    assert cached == topics, "Кэшированные топики должны совпадать с оригинальными"


def test_get_cached_topics_not_in_cache(topic_manager):
    """
    Unit: Получение топиков, которых нет в кэше
    
    Validates: Requirements 11.3
    """
    # Act
    cached = topic_manager.get_cached_topics("https://t.me/nonexistent")
    
    # Assert
    assert cached is None, "Для несуществующего чата должен вернуться None"


def test_clear_cache_specific_chat(topic_manager):
    """
    Unit: Очистка кэша для конкретного чата
    
    Validates: Requirements 11.3
    """
    # Arrange: Кэшируем топики для двух чатов
    chat_link_1 = "https://t.me/forum1"
    chat_link_2 = "https://t.me/forum2"
    topics_1 = [(1, "Topic 1")]
    topics_2 = [(2, "Topic 2")]
    
    topic_manager.cache_topics(chat_link_1, topics_1)
    topic_manager.cache_topics(chat_link_2, topics_2)
    
    # Act: Очищаем кэш для первого чата
    topic_manager.clear_cache(chat_link_1)
    
    # Assert: Первый чат очищен, второй остался
    assert topic_manager.get_cached_topics(chat_link_1) is None
    assert topic_manager.get_cached_topics(chat_link_2) == topics_2


def test_clear_cache_all(topic_manager):
    """
    Unit: Очистка всего кэша
    
    Validates: Requirements 11.3
    """
    # Arrange: Кэшируем топики для нескольких чатов
    topic_manager.cache_topics("https://t.me/forum1", [(1, "Topic 1")])
    topic_manager.cache_topics("https://t.me/forum2", [(2, "Topic 2")])
    topic_manager.cache_topics("https://t.me/forum3", [(3, "Topic 3")])
    
    # Act: Очищаем весь кэш
    topic_manager.clear_cache()
    
    # Assert: Все чаты очищены
    assert topic_manager.get_cached_topics("https://t.me/forum1") is None
    assert topic_manager.get_cached_topics("https://t.me/forum2") is None
    assert topic_manager.get_cached_topics("https://t.me/forum3") is None
    assert topic_manager.get_cache_size() == 0


def test_get_cache_size(topic_manager):
    """
    Unit: Получение размера кэша
    
    Validates: Requirements 11.3
    """
    # Arrange: Изначально кэш пустой
    assert topic_manager.get_cache_size() == 0
    
    # Act: Добавляем топики в кэш
    topic_manager.cache_topics("https://t.me/forum1", [(1, "Topic 1")])
    assert topic_manager.get_cache_size() == 1
    
    topic_manager.cache_topics("https://t.me/forum2", [(2, "Topic 2")])
    assert topic_manager.get_cache_size() == 2
    
    topic_manager.cache_topics("https://t.me/forum3", [(3, "Topic 3")])
    assert topic_manager.get_cache_size() == 3
    
    # Очищаем один чат
    topic_manager.clear_cache("https://t.me/forum1")
    assert topic_manager.get_cache_size() == 2
    
    # Очищаем весь кэш
    topic_manager.clear_cache()
    assert topic_manager.get_cache_size() == 0


def test_cache_overwrite(topic_manager):
    """
    Unit: Перезапись кэша для одного и того же чата
    
    Validates: Requirements 11.3, 11.4
    """
    # Arrange
    chat_link = "https://t.me/test_forum"
    topics_v1 = [(1, "Topic 1"), (2, "Topic 2")]
    topics_v2 = [(3, "Topic 3"), (4, "Topic 4"), (5, "Topic 5")]
    
    # Act: Кэшируем первую версию
    topic_manager.cache_topics(chat_link, topics_v1)
    cached_v1 = topic_manager.get_cached_topics(chat_link)
    
    # Кэшируем вторую версию (перезапись)
    topic_manager.cache_topics(chat_link, topics_v2)
    cached_v2 = topic_manager.get_cached_topics(chat_link)
    
    # Assert: Вторая версия должна перезаписать первую
    assert cached_v1 == topics_v1
    assert cached_v2 == topics_v2
    assert cached_v2 != cached_v1


# ============================================================================
# Edge cases
# ============================================================================

@pytest.mark.asyncio
async def test_get_forum_topics_with_special_characters_in_title(
    topic_manager, 
    mock_connection_manager, 
    mock_chat_entity
):
    """
    Integration: Топики с специальными символами в названии
    
    Validates: Requirements 3.4, 3.5
    """
    # Arrange: Создаем топики со специальными символами
    mock_topic_1 = Mock()
    mock_topic_1.id = 1
    mock_topic_1.title = "Тест 🚀 Эмодзи"
    
    mock_topic_2 = Mock()
    mock_topic_2.id = 2
    mock_topic_2.title = "Test with \"quotes\" and 'apostrophes'"
    
    mock_topic_3 = Mock()
    mock_topic_3.id = 3
    mock_topic_3.title = "Символы: @#$%^&*()"
    
    mock_client = mock_connection_manager.get_client.return_value
    
    async def mock_iter_dialogs(*args, **kwargs):
        for topic in [mock_topic_1, mock_topic_2, mock_topic_3]:
            mock_dialog = Mock()
            mock_dialog.entity = topic
            mock_dialog.title = topic.title
            yield mock_dialog
    
    mock_client.iter_dialogs = mock_iter_dialogs
    
    # Act
    topics = await topic_manager.get_forum_topics(mock_chat_entity)
    
    # Assert: Специальные символы должны быть сохранены
    assert len(topics) == 3
    assert topics[0] == (1, "Тест 🚀 Эмодзи")
    assert topics[1] == (2, "Test with \"quotes\" and 'apostrophes'")
    assert topics[2] == (3, "Символы: @#$%^&*()")


def test_clear_cache_nonexistent_chat(topic_manager):
    """
    Unit: Очистка кэша для несуществующего чата не должна вызывать ошибку
    
    Validates: Requirements 11.3
    """
    # Act & Assert: Не должно быть исключения
    topic_manager.clear_cache("https://t.me/nonexistent")
    
    # Проверяем что кэш остался пустым
    assert topic_manager.get_cache_size() == 0
