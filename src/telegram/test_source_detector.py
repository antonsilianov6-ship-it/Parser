# -*- coding: utf-8 -*-
"""
Unit-тесты для SourceDetector
Проверяют конкретные примеры и граничные случаи
"""

import pytest
from src.telegram.source_detector import SourceDetector


# Mock классы для тестирования
class MockChannel:
    """Mock объект для канала"""
    def __init__(self):
        self.broadcast = True
        self.megagroup = False
        self.forum = False
        self.title = "Test Channel"
        self.username = "testchannel"


class MockChat:
    """Mock объект для обычного чата"""
    def __init__(self):
        self.broadcast = False
        self.megagroup = True
        self.forum = False
        self.title = "Test Chat"


class MockForumChat:
    """Mock объект для форум-чата"""
    def __init__(self):
        self.broadcast = False
        self.megagroup = True
        self.forum = True
        self.title = "Test Forum Chat"


class MockUser:
    """Mock объект для пользователя"""
    def __init__(self):
        self.id = 123456789
        self.first_name = "Test"
        self.last_name = "User"
        self.username = "testuser"


class MockEntityWithoutAttributes:
    """Mock объект без специальных атрибутов"""
    def __init__(self):
        self.title = "Unknown Entity"


# Тесты для detect_source_type
class TestDetectSourceType:
    """Тесты для метода detect_source_type"""
    
    def test_channel_detection(self):
        """
        Тест: Entity с broadcast=True должен определяться как 'channel'
        Validates: Requirements 1.2
        """
        entity = MockChannel()
        result = SourceDetector.detect_source_type(entity)
        assert result == 'channel', "Канал должен определяться как 'channel'"
    
    def test_chat_detection(self):
        """
        Тест: Entity с megagroup=True и forum=False должен определяться как 'chat'
        Validates: Requirements 1.3
        """
        entity = MockChat()
        result = SourceDetector.detect_source_type(entity)
        assert result == 'chat', "Обычный чат должен определяться как 'chat'"
    
    def test_forum_chat_detection(self):
        """
        Тест: Entity с forum=True должен определяться как 'forum_chat'
        Validates: Requirements 1.4
        """
        entity = MockForumChat()
        result = SourceDetector.detect_source_type(entity)
        assert result == 'forum_chat', "Форум-чат должен определяться как 'forum_chat'"
    
    def test_user_entity_detection(self):
        """
        Тест: User entity должен определяться как 'chat'
        Validates: Requirements 1.5
        """
        entity = MockUser()
        result = SourceDetector.detect_source_type(entity)
        assert result == 'chat', "User entity должен определяться как 'chat'"
    
    def test_entity_without_attributes(self):
        """
        Тест: Entity без атрибутов должен возвращать 'channel' по умолчанию
        Validates: Requirements 1.7
        """
        entity = MockEntityWithoutAttributes()
        result = SourceDetector.detect_source_type(entity)
        assert result == 'channel', "Entity без атрибутов должен возвращать 'channel' по умолчанию"
    
    def test_none_entity(self):
        """
        Тест: None entity должен возвращать 'channel' по умолчанию
        Validates: Requirements 1.7
        """
        result = SourceDetector.detect_source_type(None)
        assert result == 'channel', "None entity должен возвращать 'channel' по умолчанию"
    
    def test_broadcast_priority_over_forum(self):
        """
        Тест: broadcast=True имеет приоритет над forum=True
        Validates: Requirements 1.2
        """
        class MockBroadcastForum:
            def __init__(self):
                self.broadcast = True
                self.megagroup = False
                self.forum = True
        
        entity = MockBroadcastForum()
        result = SourceDetector.detect_source_type(entity)
        assert result == 'channel', "broadcast=True должен иметь приоритет над forum=True"
    
    def test_broadcast_priority_over_megagroup(self):
        """
        Тест: broadcast=True имеет приоритет над megagroup=True
        Validates: Requirements 1.2
        """
        class MockBroadcastMegagroup:
            def __init__(self):
                self.broadcast = True
                self.megagroup = True
                self.forum = False
        
        entity = MockBroadcastMegagroup()
        result = SourceDetector.detect_source_type(entity)
        assert result == 'channel', "broadcast=True должен иметь приоритет над megagroup=True"
    
    def test_forum_priority_over_megagroup(self):
        """
        Тест: forum=True имеет приоритет над megagroup=True (когда broadcast=False)
        Validates: Requirements 1.4
        """
        entity = MockForumChat()
        result = SourceDetector.detect_source_type(entity)
        assert result == 'forum_chat', "forum=True должен иметь приоритет над megagroup=True"
    
    def test_all_false_attributes(self):
        """
        Тест: Entity со всеми атрибутами False должен возвращать 'channel'
        Validates: Requirements 1.7
        """
        class MockAllFalse:
            def __init__(self):
                self.broadcast = False
                self.megagroup = False
                self.forum = False
        
        entity = MockAllFalse()
        result = SourceDetector.detect_source_type(entity)
        assert result == 'channel', "Entity со всеми False атрибутами должен возвращать 'channel'"


# Тесты для is_forum_chat
class TestIsForumChat:
    """Тесты для метода is_forum_chat"""
    
    def test_forum_chat_is_forum(self):
        """
        Тест: Форум-чат должен определяться как форум
        Validates: Requirements 1.4
        """
        entity = MockForumChat()
        result = SourceDetector.is_forum_chat(entity)
        assert result is True, "Форум-чат должен определяться как форум"
    
    def test_channel_is_not_forum(self):
        """
        Тест: Канал не должен определяться как форум
        Validates: Requirements 1.4
        """
        entity = MockChannel()
        result = SourceDetector.is_forum_chat(entity)
        assert result is False, "Канал не должен определяться как форум"
    
    def test_chat_is_not_forum(self):
        """
        Тест: Обычный чат не должен определяться как форум
        Validates: Requirements 1.4
        """
        entity = MockChat()
        result = SourceDetector.is_forum_chat(entity)
        assert result is False, "Обычный чат не должен определяться как форум"
    
    def test_user_is_not_forum(self):
        """
        Тест: User entity не должен определяться как форум
        Validates: Requirements 1.4
        """
        entity = MockUser()
        result = SourceDetector.is_forum_chat(entity)
        assert result is False, "User entity не должен определяться как форум"
    
    def test_none_entity_is_not_forum(self):
        """
        Тест: None entity не должен определяться как форум
        Validates: Requirements 1.7
        """
        result = SourceDetector.is_forum_chat(None)
        assert result is False, "None entity не должен определяться как форум"
    
    def test_entity_without_forum_attribute(self):
        """
        Тест: Entity без атрибута forum не должен определяться как форум
        Validates: Requirements 1.7
        """
        entity = MockEntityWithoutAttributes()
        result = SourceDetector.is_forum_chat(entity)
        assert result is False, "Entity без атрибута forum не должен определяться как форум"
    
    def test_forum_false_is_not_forum(self):
        """
        Тест: Entity с forum=False не должен определяться как форум
        Validates: Requirements 1.4
        """
        class MockForumFalse:
            def __init__(self):
                self.forum = False
        
        entity = MockForumFalse()
        result = SourceDetector.is_forum_chat(entity)
        assert result is False, "Entity с forum=False не должен определяться как форум"


# Интеграционные тесты
class TestSourceDetectorIntegration:
    """Интеграционные тесты для проверки согласованности методов"""
    
    def test_consistency_channel(self):
        """
        Тест: Согласованность методов для канала
        Validates: Requirements 1.2, 1.4
        """
        entity = MockChannel()
        source_type = SourceDetector.detect_source_type(entity)
        is_forum = SourceDetector.is_forum_chat(entity)
        
        assert source_type == 'channel', "Канал должен определяться как 'channel'"
        assert is_forum is False, "Канал не должен быть форумом"
    
    def test_consistency_chat(self):
        """
        Тест: Согласованность методов для чата
        Validates: Requirements 1.3, 1.4
        """
        entity = MockChat()
        source_type = SourceDetector.detect_source_type(entity)
        is_forum = SourceDetector.is_forum_chat(entity)
        
        assert source_type == 'chat', "Чат должен определяться как 'chat'"
        assert is_forum is False, "Обычный чат не должен быть форумом"
    
    def test_consistency_forum_chat(self):
        """
        Тест: Согласованность методов для форум-чата
        Validates: Requirements 1.4
        """
        entity = MockForumChat()
        source_type = SourceDetector.detect_source_type(entity)
        is_forum = SourceDetector.is_forum_chat(entity)
        
        assert source_type == 'forum_chat', "Форум-чат должен определяться как 'forum_chat'"
        assert is_forum is True, "Форум-чат должен быть форумом"
    
    def test_consistency_user(self):
        """
        Тест: Согласованность методов для пользователя
        Validates: Requirements 1.5, 1.4
        """
        entity = MockUser()
        source_type = SourceDetector.detect_source_type(entity)
        is_forum = SourceDetector.is_forum_chat(entity)
        
        assert source_type == 'chat', "User должен определяться как 'chat'"
        assert is_forum is False, "User не должен быть форумом"


# Тесты для edge cases
class TestEdgeCases:
    """Тесты для граничных случаев"""
    
    def test_entity_with_extra_attributes(self):
        """
        Тест: Entity с дополнительными атрибутами должен корректно обрабатываться
        """
        class MockEntityWithExtra:
            def __init__(self):
                self.broadcast = False
                self.megagroup = True
                self.forum = False
                self.extra_attr = "extra"
                self.another_attr = 123
        
        entity = MockEntityWithExtra()
        result = SourceDetector.detect_source_type(entity)
        assert result == 'chat', "Entity с дополнительными атрибутами должен корректно классифицироваться"
    
    def test_entity_with_none_attributes(self):
        """
        Тест: Entity с None атрибутами должен возвращать 'channel' по умолчанию
        """
        class MockEntityWithNone:
            def __init__(self):
                self.broadcast = None
                self.megagroup = None
                self.forum = None
        
        entity = MockEntityWithNone()
        result = SourceDetector.detect_source_type(entity)
        assert result == 'channel', "Entity с None атрибутами должен возвращать 'channel'"
    
    def test_multiple_calls_same_entity(self):
        """
        Тест: Множественные вызовы с одним entity должны возвращать одинаковый результат
        """
        entity = MockChat()
        
        result1 = SourceDetector.detect_source_type(entity)
        result2 = SourceDetector.detect_source_type(entity)
        result3 = SourceDetector.detect_source_type(entity)
        
        assert result1 == result2 == result3 == 'chat', \
            "Множественные вызовы должны возвращать одинаковый результат"
