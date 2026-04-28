# -*- coding: utf-8 -*-
"""Unit-тесты для CacheManager"""

import pytest
import os
import tempfile
from datetime import datetime, timedelta
from unittest.mock import Mock
from src.cache.cache_manager import CacheManager, CacheEntry


class TestCacheManagerEntityCaching:
    """Тесты кэширования entity для чатов"""
    
    def test_save_entity_for_chat(self):
        """
        Тест кэширования entity для чата
        
        **Validates: Requirements 11.1, 11.2**
        """
        cache_manager = CacheManager(cache_file=":memory:")
        
        # Создаем mock entity для чата
        entity = Mock()
        entity.id = 123456789
        entity.title = "Test Chat"
        entity.username = "test_chat"
        
        # Сохраняем entity с типом 'chat'
        cache_manager.save_entity("https://t.me/test_chat", entity, source_type='chat')
        
        # Проверяем что entity сохранен
        cached_data = cache_manager.get_entity("https://t.me/test_chat")
        
        assert cached_data is not None
        assert cached_data['channel_id'] == 123456789
        assert cached_data['title'] == "Test Chat"
        assert cached_data['username'] == "test_chat"
        assert cached_data['source_type'] == 'chat'
    
    def test_save_entity_for_forum_chat(self):
        """
        Тест кэширования entity для форум-чата
        
        **Validates: Requirements 11.1, 11.2**
        """
        cache_manager = CacheManager(cache_file=":memory:")
        
        # Создаем mock entity для форум-чата
        entity = Mock()
        entity.id = 987654321
        entity.title = "Test Forum Chat"
        entity.username = "test_forum"
        
        # Сохраняем entity с типом 'forum_chat'
        cache_manager.save_entity("https://t.me/test_forum", entity, source_type='forum_chat')
        
        # Проверяем что entity сохранен с правильным типом
        cached_data, source_type = cache_manager.get_entity_with_type("https://t.me/test_forum")
        
        assert cached_data is not None
        assert source_type == 'forum_chat'
        assert cached_data['channel_id'] == 987654321
    
    def test_save_entity_default_source_type(self):
        """
        Тест кэширования entity с дефолтным source_type='channel'
        
        **Validates: Requirements 11.2**
        """
        cache_manager = CacheManager(cache_file=":memory:")
        
        entity = Mock()
        entity.id = 111222333
        entity.title = "Test Channel"
        entity.username = "test_channel"
        
        # Сохраняем без указания source_type (должен быть 'channel' по умолчанию)
        cache_manager.save_entity("https://t.me/test_channel", entity)
        
        cached_data, source_type = cache_manager.get_entity_with_type("https://t.me/test_channel")
        
        assert source_type == 'channel'
    
    def test_get_entity_nonexistent(self):
        """
        Тест получения несуществующего entity
        
        **Validates: Requirements 11.4**
        """
        cache_manager = CacheManager(cache_file=":memory:")
        
        cached_data = cache_manager.get_entity("https://t.me/nonexistent")
        
        assert cached_data is None
    
    def test_get_entity_with_type_nonexistent(self):
        """
        Тест получения несуществующего entity с типом
        
        **Validates: Requirements 11.4**
        """
        cache_manager = CacheManager(cache_file=":memory:")
        
        cached_data, source_type = cache_manager.get_entity_with_type("https://t.me/nonexistent")
        
        assert cached_data is None
        assert source_type is None


class TestCacheManagerTopicsCaching:
    """Тесты кэширования топиков для форум-чатов"""
    
    def test_save_topics_for_forum_chat(self):
        """
        Тест кэширования топиков для форум-чата
        
        **Validates: Requirements 11.3**
        """
        cache_manager = CacheManager(cache_file=":memory:")
        
        topics = [
            (1, "General Discussion"),
            (2, "Announcements"),
            (3, "Off-topic")
        ]
        
        # Сохраняем топики
        cache_manager.save_topics("https://t.me/test_forum", topics)
        
        # Получаем топики из кэша
        cached_topics = cache_manager.get_topics("https://t.me/test_forum")
        
        assert cached_topics is not None
        assert len(cached_topics) == 3
        assert cached_topics[0] == (1, "General Discussion")
        assert cached_topics[1] == (2, "Announcements")
        assert cached_topics[2] == (3, "Off-topic")
    
    def test_save_empty_topics_list(self):
        """
        Тест кэширования пустого списка топиков
        
        **Validates: Requirements 11.3**
        """
        cache_manager = CacheManager(cache_file=":memory:")
        
        # Сохраняем пустой список топиков
        cache_manager.save_topics("https://t.me/test_forum", [])
        
        # Получаем топики из кэша
        cached_topics = cache_manager.get_topics("https://t.me/test_forum")
        
        assert cached_topics is not None
        assert len(cached_topics) == 0
    
    def test_get_topics_nonexistent(self):
        """
        Тест получения несуществующих топиков
        
        **Validates: Requirements 11.3**
        """
        cache_manager = CacheManager(cache_file=":memory:")
        
        cached_topics = cache_manager.get_topics("https://t.me/nonexistent")
        
        assert cached_topics is None
    
    def test_update_topics(self):
        """
        Тест обновления списка топиков
        
        **Validates: Requirements 11.3**
        """
        cache_manager = CacheManager(cache_file=":memory:")
        
        # Сохраняем первоначальный список топиков
        topics1 = [(1, "Topic 1"), (2, "Topic 2")]
        cache_manager.save_topics("https://t.me/test_forum", topics1)
        
        # Обновляем список топиков
        topics2 = [(1, "Topic 1"), (2, "Topic 2"), (3, "Topic 3")]
        cache_manager.save_topics("https://t.me/test_forum", topics2)
        
        # Проверяем что список обновлен
        cached_topics = cache_manager.get_topics("https://t.me/test_forum")
        
        assert len(cached_topics) == 3
        assert (3, "Topic 3") in cached_topics


class TestCacheManagerValidity:
    """Тесты проверки актуальности кэша"""
    
    def test_is_entity_valid_fresh_cache(self):
        """
        Тест проверки актуальности свежего кэша entity
        
        **Validates: Requirements 11.5**
        """
        cache_manager = CacheManager(cache_file=":memory:")
        
        entity = Mock()
        entity.id = 123
        entity.title = "Test"
        entity.username = "test"
        
        # Сохраняем entity
        cache_manager.save_entity("https://t.me/test", entity, source_type='chat')
        
        # Проверяем что entity валиден
        is_valid = cache_manager.is_entity_valid("https://t.me/test", max_age_days=7)
        
        assert is_valid is True
    
    def test_is_entity_valid_expired_cache(self):
        """
        Тест проверки актуальности устаревшего кэша entity
        
        **Validates: Requirements 11.5, 11.6**
        """
        cache_manager = CacheManager(cache_file=":memory:")
        
        entity = Mock()
        entity.id = 123
        entity.title = "Test"
        entity.username = "test"
        
        # Сохраняем entity
        cache_manager.save_entity("https://t.me/test", entity, source_type='chat')
        
        # Симулируем устаревание кэша (8 дней назад)
        cached_data = cache_manager.get_entity("https://t.me/test")
        old_cached_at = (datetime.now() - timedelta(days=8)).isoformat()
        cached_data['cached_at'] = old_cached_at
        cache_manager.data['entity_cache']["https://t.me/test"] = cached_data
        
        # Проверяем что entity невалиден
        is_valid = cache_manager.is_entity_valid("https://t.me/test", max_age_days=7)
        
        assert is_valid is False
    
    def test_is_entity_valid_nonexistent(self):
        """
        Тест проверки актуальности несуществующего entity
        
        **Validates: Requirements 11.5**
        """
        cache_manager = CacheManager(cache_file=":memory:")
        
        is_valid = cache_manager.is_entity_valid("https://t.me/nonexistent", max_age_days=7)
        
        assert is_valid is False
    
    def test_is_topics_valid_fresh_cache(self):
        """
        Тест проверки актуальности свежего кэша топиков
        
        **Validates: Requirements 11.5**
        """
        cache_manager = CacheManager(cache_file=":memory:")
        
        topics = [(1, "Topic 1"), (2, "Topic 2")]
        
        # Сохраняем топики
        cache_manager.save_topics("https://t.me/test_forum", topics)
        
        # Проверяем что топики валидны
        is_valid = cache_manager.is_topics_valid("https://t.me/test_forum", max_age_days=7)
        
        assert is_valid is True
    
    def test_is_topics_valid_expired_cache(self):
        """
        Тест проверки актуальности устаревшего кэша топиков
        
        **Validates: Requirements 11.5, 11.6**
        """
        cache_manager = CacheManager(cache_file=":memory:")
        
        topics = [(1, "Topic 1"), (2, "Topic 2")]
        
        # Сохраняем топики
        cache_manager.save_topics("https://t.me/test_forum", topics)
        
        # Симулируем устаревание кэша (8 дней назад)
        topics_data = cache_manager.data['topics_cache']["https://t.me/test_forum"]
        old_cached_at = (datetime.now() - timedelta(days=8)).isoformat()
        topics_data['cached_at'] = old_cached_at
        cache_manager.data['topics_cache']["https://t.me/test_forum"] = topics_data
        
        # Проверяем что топики невалидны
        is_valid = cache_manager.is_topics_valid("https://t.me/test_forum", max_age_days=7)
        
        assert is_valid is False
    
    def test_is_topics_valid_nonexistent(self):
        """
        Тест проверки актуальности несуществующих топиков
        
        **Validates: Requirements 11.5**
        """
        cache_manager = CacheManager(cache_file=":memory:")
        
        is_valid = cache_manager.is_topics_valid("https://t.me/nonexistent", max_age_days=7)
        
        assert is_valid is False
    
    def test_ttl_consistency_across_types(self):
        """
        Тест одинакового применения TTL для всех типов источников
        
        **Validates: Requirements 11.7**
        """
        cache_manager = CacheManager(cache_file=":memory:")
        
        # Создаем entities разных типов
        entity_channel = Mock()
        entity_channel.id = 1
        entity_channel.title = "Channel"
        entity_channel.username = "channel"
        
        entity_chat = Mock()
        entity_chat.id = 2
        entity_chat.title = "Chat"
        entity_chat.username = "chat"
        
        entity_forum = Mock()
        entity_forum.id = 3
        entity_forum.title = "Forum"
        entity_forum.username = "forum"
        
        # Сохраняем entities
        cache_manager.save_entity("https://t.me/channel", entity_channel, source_type='channel')
        cache_manager.save_entity("https://t.me/chat", entity_chat, source_type='chat')
        cache_manager.save_entity("https://t.me/forum", entity_forum, source_type='forum_chat')
        
        # Проверяем что все entities валидны с одинаковым TTL
        assert cache_manager.is_entity_valid("https://t.me/channel", max_age_days=7) is True
        assert cache_manager.is_entity_valid("https://t.me/chat", max_age_days=7) is True
        assert cache_manager.is_entity_valid("https://t.me/forum", max_age_days=7) is True
        
        # Симулируем устаревание всех entities
        for link in ["https://t.me/channel", "https://t.me/chat", "https://t.me/forum"]:
            cached_data = cache_manager.get_entity(link)
            old_cached_at = (datetime.now() - timedelta(days=8)).isoformat()
            cached_data['cached_at'] = old_cached_at
            cache_manager.data['entity_cache'][link] = cached_data
        
        # Проверяем что все entities невалидны (TTL применяется одинаково)
        assert cache_manager.is_entity_valid("https://t.me/channel", max_age_days=7) is False
        assert cache_manager.is_entity_valid("https://t.me/chat", max_age_days=7) is False
        assert cache_manager.is_entity_valid("https://t.me/forum", max_age_days=7) is False


class TestCacheManagerEdgeCases:
    """Тесты граничных случаев"""
    
    def test_entity_without_username(self):
        """
        Тест кэширования entity без username
        
        **Validates: Requirements 11.1**
        """
        cache_manager = CacheManager(cache_file=":memory:")
        
        entity = Mock()
        entity.id = 123
        entity.title = "Test"
        entity.username = ""  # Пустой username
        
        cache_manager.save_entity("https://t.me/c/123", entity, source_type='chat')
        
        cached_data = cache_manager.get_entity("https://t.me/c/123")
        
        assert cached_data is not None
        assert cached_data['username'] == ""
    
    def test_entity_with_special_characters_in_title(self):
        """
        Тест кэширования entity со специальными символами в названии
        
        **Validates: Requirements 11.1**
        """
        cache_manager = CacheManager(cache_file=":memory:")
        
        entity = Mock()
        entity.id = 123
        entity.title = "Test 🚀 Chat & Forum"
        entity.username = "test"
        
        cache_manager.save_entity("https://t.me/test", entity, source_type='chat')
        
        cached_data = cache_manager.get_entity("https://t.me/test")
        
        assert cached_data is not None
        assert cached_data['title'] == "Test 🚀 Chat & Forum"
    
    def test_topics_with_special_characters(self):
        """
        Тест кэширования топиков со специальными символами
        
        **Validates: Requirements 11.3**
        """
        cache_manager = CacheManager(cache_file=":memory:")
        
        topics = [
            (1, "Общее обсуждение 💬"),
            (2, "Объявления & Новости"),
            (3, "Off-topic 🎉")
        ]
        
        cache_manager.save_topics("https://t.me/test_forum", topics)
        
        cached_topics = cache_manager.get_topics("https://t.me/test_forum")
        
        assert cached_topics is not None
        assert len(cached_topics) == 3
        assert cached_topics[0][1] == "Общее обсуждение 💬"
    
    def test_cache_with_invalid_cached_at(self):
        """
        Тест обработки невалидного cached_at
        
        **Validates: Requirements 11.5**
        """
        cache_manager = CacheManager(cache_file=":memory:")
        
        entity = Mock()
        entity.id = 123
        entity.title = "Test"
        entity.username = "test"
        
        cache_manager.save_entity("https://t.me/test", entity, source_type='chat')
        
        # Портим cached_at
        cached_data = cache_manager.get_entity("https://t.me/test")
        cached_data['cached_at'] = None
        cache_manager.data['entity_cache']["https://t.me/test"] = cached_data
        
        # Должен вернуть False при невалидном cached_at
        is_valid = cache_manager.is_entity_valid("https://t.me/test", max_age_days=7)
        
        assert is_valid is False
