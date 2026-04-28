# -*- coding: utf-8 -*-
"""
Property-based тесты для SourceDetector
Используется библиотека Hypothesis для генерации тестовых данных
"""

import pytest
from hypothesis import given, settings, strategies as st
from src.telegram.source_detector import SourceDetector


# Стратегия для создания mock entity с различными атрибутами
@st.composite
def entity_strategy(draw):
    """
    Генерирует mock entity с различными комбинациями атрибутов
    """
    broadcast = draw(st.booleans())
    megagroup = draw(st.booleans())
    forum = draw(st.booleans())
    
    # Создаем mock объект с атрибутами
    class MockEntity:
        def __init__(self, broadcast, megagroup, forum):
            self.broadcast = broadcast
            self.megagroup = megagroup
            self.forum = forum
    
    return MockEntity(broadcast, megagroup, forum)


@st.composite
def user_entity_strategy(draw):
    """
    Генерирует mock User entity
    """
    class MockUser:
        def __init__(self):
            self.id = draw(st.integers(min_value=1, max_value=999999999))
            self.first_name = draw(st.text(min_size=1, max_size=50))
            self.username = draw(st.one_of(st.none(), st.text(min_size=1, max_size=32)))
    
    return MockUser()


# Feature: chat-and-topic-support, Property 1: Source type classification correctness
@given(entity=entity_strategy())
@settings(max_examples=100)
def test_source_type_classification_property(entity):
    """
    Property: For any entity attributes, classification returns valid source type
    
    Validates: Requirements 1.1, 1.2, 1.3, 1.4, 1.5, 1.6
    
    Проверяет:
    - Результат всегда является одним из допустимых типов
    - Классификация соответствует правилам приоритета
    """
    result = SourceDetector.detect_source_type(entity)
    
    # Проверяем, что результат является допустимым типом источника
    assert result in ['channel', 'chat', 'forum_chat'], \
        f"Недопустимый тип источника: {result}"
    
    # Проверяем правила классификации с учетом приоритета
    # Приоритет: broadcast > forum > megagroup
    
    if entity.broadcast:
        # Если broadcast=True, должен быть 'channel' независимо от других атрибутов
        assert result == 'channel', \
            f"Entity с broadcast=True должен быть 'channel', получено: {result}"
    
    elif entity.forum:
        # Если forum=True и broadcast=False, должен быть 'forum_chat'
        assert result == 'forum_chat', \
            f"Entity с forum=True (и broadcast=False) должен быть 'forum_chat', получено: {result}"
    
    elif entity.megagroup:
        # Если megagroup=True и broadcast=False и forum=False, должен быть 'chat'
        assert result == 'chat', \
            f"Entity с megagroup=True (и broadcast=False, forum=False) должен быть 'chat', получено: {result}"
    
    else:
        # Если все атрибуты False, по умолчанию 'channel'
        assert result == 'channel', \
            f"Entity без специальных атрибутов должен быть 'channel', получено: {result}"


@given(user=user_entity_strategy())
@settings(max_examples=100)
def test_user_entity_classification_property(user):
    """
    Property: For any User entity, classification returns 'chat'
    
    Validates: Requirements 1.5
    
    Проверяет:
    - User entity всегда классифицируется как 'chat'
    """
    result = SourceDetector.detect_source_type(user)
    
    assert result == 'chat', \
        f"User entity должен быть классифицирован как 'chat', получено: {result}"


@given(
    broadcast=st.booleans(),
    megagroup=st.booleans(),
    forum=st.booleans()
)
@settings(max_examples=100)
def test_is_forum_chat_property(broadcast, megagroup, forum):
    """
    Property: is_forum_chat returns True only when forum=True
    
    Validates: Requirements 1.4
    
    Проверяет:
    - is_forum_chat возвращает True только когда forum=True
    - is_forum_chat возвращает False для всех остальных случаев
    """
    class MockEntity:
        def __init__(self, broadcast, megagroup, forum):
            self.broadcast = broadcast
            self.megagroup = megagroup
            self.forum = forum
    
    entity = MockEntity(broadcast, megagroup, forum)
    result = SourceDetector.is_forum_chat(entity)
    
    # Проверяем, что результат соответствует значению атрибута forum
    assert result == forum, \
        f"is_forum_chat должен возвращать {forum}, получено: {result}"


@given(
    broadcast=st.booleans(),
    megagroup=st.booleans(),
    forum=st.booleans()
)
@settings(max_examples=100)
def test_classification_consistency_property(broadcast, megagroup, forum):
    """
    Property: Classification is consistent across multiple calls
    
    Validates: Requirements 1.1, 1.2, 1.3, 1.4, 1.5, 1.6
    
    Проверяет:
    - Повторные вызовы с одинаковыми параметрами возвращают одинаковый результат
    """
    class MockEntity:
        def __init__(self, broadcast, megagroup, forum):
            self.broadcast = broadcast
            self.megagroup = megagroup
            self.forum = forum
    
    entity = MockEntity(broadcast, megagroup, forum)
    
    # Вызываем несколько раз
    result1 = SourceDetector.detect_source_type(entity)
    result2 = SourceDetector.detect_source_type(entity)
    result3 = SourceDetector.detect_source_type(entity)
    
    # Проверяем консистентность
    assert result1 == result2 == result3, \
        f"Классификация должна быть консистентной: {result1}, {result2}, {result3}"


@given(entity=entity_strategy())
@settings(max_examples=100)
def test_source_type_and_forum_check_consistency_property(entity):
    """
    Property: detect_source_type and is_forum_chat are consistent
    
    Validates: Requirements 1.4
    
    Проверяет:
    - Если detect_source_type возвращает 'forum_chat', то is_forum_chat должен вернуть True
    - Если is_forum_chat возвращает True, то detect_source_type должен вернуть 'forum_chat' (если broadcast=False)
    """
    source_type = SourceDetector.detect_source_type(entity)
    is_forum = SourceDetector.is_forum_chat(entity)
    
    # Если тип источника 'forum_chat', то is_forum_chat должен быть True
    if source_type == 'forum_chat':
        assert is_forum is True, \
            f"Если source_type='forum_chat', то is_forum_chat должен быть True"
    
    # Если is_forum_chat=True и broadcast=False, то source_type должен быть 'forum_chat'
    if is_forum and not entity.broadcast:
        assert source_type == 'forum_chat', \
            f"Если is_forum_chat=True и broadcast=False, то source_type должен быть 'forum_chat'"


# Тесты для граничных случаев с None
def test_none_entity_property():
    """
    Property: None entity returns default 'channel'
    
    Validates: Requirements 1.7
    
    Проверяет:
    - None entity возвращает 'channel' по умолчанию
    """
    result = SourceDetector.detect_source_type(None)
    assert result == 'channel', \
        f"None entity должен возвращать 'channel', получено: {result}"


def test_none_entity_is_not_forum():
    """
    Property: None entity is not a forum chat
    
    Validates: Requirements 1.7
    
    Проверяет:
    - None entity не является форум-чатом
    """
    result = SourceDetector.is_forum_chat(None)
    assert result is False, \
        f"None entity не должен быть форум-чатом, получено: {result}"
