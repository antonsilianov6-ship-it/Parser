# -*- coding: utf-8 -*-
"""Property-based тесты для CacheManager с использованием hypothesis"""

import os
import tempfile
from datetime import datetime, timedelta
from unittest.mock import Mock
import pytest
from hypothesis import given, settings, strategies as st
from src.cache.cache_manager import CacheManager


# Стратегии для генерации данных
@st.composite
def entity_strategy(draw, source_type=None):
    """Генерирует mock entity с различными атрибутами"""
    entity = Mock()
    entity.id = draw(st.integers(min_value=1, max_value=999999999))
    entity.title = draw(st.text(min_size=1, max_size=100))
    entity.username = draw(st.text(
        min_size=1, 
        max_size=32, 
        alphabet=st.characters(whitelist_categories=('Ll', 'Lu', 'Nd'), whitelist_characters='_')
    ))
    
    if source_type is None:
        source_type = draw(st.sampled_from(['channel', 'chat', 'forum_chat']))
    
    return entity, source_type


@st.composite
def chat_link_strategy(draw):
    """Генерирует различные форматы ссылок на чаты"""
    link_type = draw(st.sampled_from(['public', 'private', 'username']))
    
    if link_type == 'public':
        chatname = draw(st.text(
            min_size=5, 
            max_size=32, 
            alphabet=st.characters(whitelist_categories=('Ll', 'Lu', 'Nd'), whitelist_characters='_')
        ))
        return f"https://t.me/{chatname}"
    elif link_type == 'private':
        chat_id = draw(st.integers(min_value=1000000000, max_value=9999999999))
        return f"https://t.me/c/{chat_id}"
    else:  # username
        username = draw(st.text(
            min_size=5, 
            max_size=32, 
            alphabet=st.characters(whitelist_categories=('Ll', 'Lu', 'Nd'), whitelist_characters='_')
        ))
        return f"@{username}"


@st.composite
def topics_strategy(draw):
    """Генерирует список топиков для форум-чата"""
    num_topics = draw(st.integers(min_value=0, max_value=20))
    topics = []
    
    for _ in range(num_topics):
        topic_id = draw(st.integers(min_value=1, max_value=999999))
        topic_title = draw(st.text(min_size=1, max_size=100))
        topics.append((topic_id, topic_title))
    
    return topics


class TestEntityCachingProperties:
    """Property-based тесты для кэширования entity с метаданными"""
    
    @given(
        entity_data=entity_strategy(),
        chat_link=chat_link_strategy()
    )
    @settings(max_examples=100)
    def test_property_14_entity_caching_with_metadata(self, entity_data, chat_link):
        """
        Property 14: Entity caching with metadata
        
        **Validates: Requirements 11.1, 11.2**
        
        For any entity (channel, chat, or forum_chat), the Cache_Manager SHALL cache it 
        along with its source_type metadata, and subsequent retrievals SHALL return both 
        the entity and its type without additional API calls.
        """
        entity, source_type = entity_data
        
        # Создаем временный файл для кэша
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            cache_file = f.name
        
        try:
            # Создаем менеджер кэша
            manager = CacheManager(cache_file=cache_file)
            
            # Сохраняем entity с метаданными
            manager.save_entity(chat_link, entity, source_type)
            
            # Проверяем, что entity сохранен
            cached_entity = manager.get_entity(chat_link)
            assert cached_entity is not None, "Entity должен быть сохранен в кэше"
            
            # Проверяем, что все атрибуты сохранены корректно
            assert cached_entity['channel_id'] == entity.id, "ID entity должен совпадать"
            assert cached_entity['title'] == entity.title, "Title entity должен совпадать"
            assert cached_entity['username'] == entity.username, "Username entity должен совпадать"
            assert cached_entity['source_type'] == source_type, "Source_type должен совпадать"
            assert 'cached_at' in cached_entity, "Должна быть метка времени кэширования"
            
            # Проверяем метод get_entity_with_type
            retrieved_entity, retrieved_type = manager.get_entity_with_type(chat_link)
            assert retrieved_entity is not None, "Entity должен быть получен через get_entity_with_type"
            assert retrieved_type == source_type, "Source_type должен быть возвращен корректно"
            assert retrieved_entity['channel_id'] == entity.id, "ID должен совпадать при получении с типом"
        finally:
            # Cleanup
            if os.path.exists(cache_file):
                os.unlink(cache_file)
    
    @given(
        entities=st.lists(entity_strategy(), min_size=1, max_size=10),
        links=st.lists(chat_link_strategy(), min_size=1, max_size=10, unique=True)
    )
    @settings(max_examples=100)
    def test_property_14_multiple_entities_with_different_types(self, entities, links):
        """
        Property 14 (расширенный): Кэширование множества entity с разными типами
        
        **Validates: Requirements 11.1, 11.2**
        
        Проверяет, что система корректно кэширует множество entity с разными source_type
        и каждый entity сохраняет свой тип независимо от других.
        """
        # Создаем временный файл для кэша
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            cache_file = f.name
        
        try:
            # Ограничиваем количество пар до минимума из двух списков
            num_pairs = min(len(entities), len(links))
            
            # Пропускаем тест если нет пар для проверки
            if num_pairs == 0:
                return
            
            manager = CacheManager(cache_file=cache_file)
            
            # Сохраняем все entity (используем только уникальные ссылки)
            saved_pairs = []
            for i in range(num_pairs):
                entity, source_type = entities[i]
                link = links[i]
                manager.save_entity(link, entity, source_type)
                saved_pairs.append((link, entity, source_type))
            
            # Проверяем, что все entity сохранены с правильными типами
            for link, entity, source_type in saved_pairs:
                cached_entity, cached_type = manager.get_entity_with_type(link)
                assert cached_entity is not None, f"Entity для {link} должен быть в кэше"
                assert cached_type == source_type, f"Source_type для {link} должен быть {source_type}"
                assert cached_entity['channel_id'] == entity.id, f"ID для {link} должен совпадать"
        finally:
            # Cleanup
            if os.path.exists(cache_file):
                os.unlink(cache_file)
    
    @given(
        entity_data=entity_strategy(),
        chat_link=chat_link_strategy()
    )
    @settings(max_examples=100)
    def test_property_14_backward_compatibility_default_type(self, entity_data, chat_link):
        """
        Property 14 (обратная совместимость): Дефолтный source_type
        
        **Validates: Requirements 11.1, 11.2, 12.2**
        
        Проверяет, что при сохранении entity без указания source_type,
        используется значение по умолчанию 'channel' для обратной совместимости.
        """
        entity, _ = entity_data  # Игнорируем сгенерированный source_type
        
        # Создаем временный файл для кэша
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            cache_file = f.name
        
        try:
            manager = CacheManager(cache_file=cache_file)
            
            # Сохраняем entity без указания source_type (используется дефолтное значение)
            manager.save_entity(chat_link, entity)
            
            # Проверяем, что source_type установлен в 'channel' по умолчанию
            cached_entity, cached_type = manager.get_entity_with_type(chat_link)
            assert cached_entity is not None, "Entity должен быть сохранен"
            assert cached_type == 'channel', "Дефолтный source_type должен быть 'channel'"
        finally:
            # Cleanup
            if os.path.exists(cache_file):
                os.unlink(cache_file)
    
    @given(
        entity_data=entity_strategy(),
        chat_link=chat_link_strategy()
    )
    @settings(max_examples=100)
    def test_property_14_persistence_after_save_load(self, entity_data, chat_link):
        """
        Property 14 (персистентность): Сохранение метаданных после save/load
        
        **Validates: Requirements 11.1, 11.2**
        
        Проверяет, что entity и его source_type корректно сохраняются в файл
        и восстанавливаются после загрузки.
        """
        entity, source_type = entity_data
        
        # Создаем временный файл для кэша
        fd, cache_file = tempfile.mkstemp(suffix='.json')
        os.close(fd)  # Закрываем файловый дескриптор
        
        try:
            # Создаем менеджер, сохраняем entity и записываем в файл
            manager1 = CacheManager(cache_file=cache_file)
            manager1.save_entity(chat_link, entity, source_type)
            save_result = manager1.save()
            
            # Проверяем, что файл был успешно сохранен
            assert save_result is True, "Файл кэша должен быть успешно сохранен"
            assert os.path.exists(cache_file), "Файл кэша должен существовать после save()"
            
            # Создаем новый менеджер и загружаем из файла
            manager2 = CacheManager(cache_file=cache_file)
            manager2.load()
            
            # Проверяем, что entity и метаданные восстановлены
            cached_entity, cached_type = manager2.get_entity_with_type(chat_link)
            assert cached_entity is not None, "Entity должен быть восстановлен после загрузки"
            assert cached_type == source_type, "Source_type должен быть восстановлен после загрузки"
            assert cached_entity['channel_id'] == entity.id, "ID должен совпадать после загрузки"
        finally:
            # Cleanup
            if os.path.exists(cache_file):
                os.unlink(cache_file)


class TestTopicsCachingProperties:
    """Property-based тесты для кэширования топиков"""
    
    @given(
        chat_link=chat_link_strategy(),
        topics=topics_strategy()
    )
    @settings(max_examples=100)
    def test_property_topics_caching_preserves_data(self, chat_link, topics):
        """
        Property: Кэширование топиков сохраняет все данные
        
        **Validates: Requirements 11.3**
        
        Проверяет, что список топиков корректно сохраняется и восстанавливается из кэша.
        """
        # Создаем временный файл для кэша
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            cache_file = f.name
        
        try:
            manager = CacheManager(cache_file=cache_file)
            
            # Сохраняем топики
            manager.save_topics(chat_link, topics)
            
            # Получаем топики из кэша
            cached_topics = manager.get_topics(chat_link)
            
            if len(topics) > 0:
                assert cached_topics is not None, "Топики должны быть в кэше"
                assert len(cached_topics) == len(topics), "Количество топиков должно совпадать"
                assert cached_topics == topics, "Топики должны полностью совпадать"
            else:
                # Пустой список топиков тоже должен сохраняться
                assert cached_topics is not None, "Пустой список топиков должен быть в кэше"
                assert len(cached_topics) == 0, "Пустой список должен остаться пустым"
        finally:
            # Cleanup
            if os.path.exists(cache_file):
                os.unlink(cache_file)
    
    @given(
        chat_link=chat_link_strategy(),
        topics=topics_strategy()
    )
    @settings(max_examples=100)
    def test_property_topics_validity_check(self, chat_link, topics):
        """
        Property: Проверка актуальности топиков на основе TTL
        
        **Validates: Requirements 11.5, 11.7**
        
        Проверяет, что is_topics_valid корректно определяет актуальность топиков.
        """
        # Создаем временный файл для кэша
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            cache_file = f.name
        
        try:
            manager = CacheManager(cache_file=cache_file)
            
            # Сохраняем топики
            manager.save_topics(chat_link, topics)
            
            # Свежие топики должны быть валидными
            assert manager.is_topics_valid(chat_link, max_age_days=7) is True, \
                "Свежие топики должны быть валидными"
            
            # Изменяем дату кэширования на устаревшую
            if chat_link in manager.data.get('topics_cache', {}):
                old_date = (datetime.now() - timedelta(days=10)).isoformat()
                manager.data['topics_cache'][chat_link]['cached_at'] = old_date
                
                # Устаревшие топики должны быть невалидными
                assert manager.is_topics_valid(chat_link, max_age_days=7) is False, \
                    "Устаревшие топики должны быть невалидными"
        finally:
            # Cleanup
            if os.path.exists(cache_file):
                os.unlink(cache_file)



class TestCacheTTLProperties:
    """Property-based тесты для консистентности TTL кэша"""
    
    @given(
        entity_data=entity_strategy(),
        chat_link=chat_link_strategy(),
        max_age_days=st.integers(min_value=1, max_value=30)
    )
    @settings(max_examples=100)
    def test_property_15_cache_ttl_consistency_for_entities(self, entity_data, chat_link, max_age_days):
        """
        Property 15: Cache TTL consistency для entity
        
        **Validates: Requirements 11.5, 11.7**
        
        Проверяет, что TTL применяется одинаково для всех типов источников (channel, chat, forum_chat).
        """
        entity, source_type = entity_data
        
        # Создаем временный файл для кэша
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            cache_file = f.name
        
        try:
            manager = CacheManager(cache_file=cache_file)
            
            # Сохраняем entity
            manager.save_entity(chat_link, entity, source_type)
            
            # Свежий entity должен быть валидным независимо от source_type
            assert manager.is_entity_valid(chat_link, max_age_days=max_age_days) is True, \
                f"Свежий entity с типом {source_type} должен быть валидным"
            
            # Изменяем дату кэширования на устаревшую (больше max_age_days)
            old_date = (datetime.now() - timedelta(days=max_age_days + 1)).isoformat()
            manager.data['entity_cache'][chat_link]['cached_at'] = old_date
            
            # Устаревший entity должен быть невалидным независимо от source_type
            assert manager.is_entity_valid(chat_link, max_age_days=max_age_days) is False, \
                f"Устаревший entity с типом {source_type} должен быть невалидным"
            
            # Изменяем дату кэширования на граничное значение (ровно max_age_days - 1)
            boundary_date = (datetime.now() - timedelta(days=max_age_days - 1)).isoformat()
            manager.data['entity_cache'][chat_link]['cached_at'] = boundary_date
            
            # Entity на границе TTL должен быть валидным
            assert manager.is_entity_valid(chat_link, max_age_days=max_age_days) is True, \
                f"Entity на границе TTL с типом {source_type} должен быть валидным"
        finally:
            # Cleanup
            if os.path.exists(cache_file):
                os.unlink(cache_file)
    
    @given(
        chat_link=chat_link_strategy(),
        topics=topics_strategy(),
        max_age_days=st.integers(min_value=1, max_value=30)
    )
    @settings(max_examples=100)
    def test_property_15_cache_ttl_consistency_for_topics(self, chat_link, topics, max_age_days):
        """
        Property 15: Cache TTL consistency для топиков
        
        **Validates: Requirements 11.5, 11.7**
        
        Проверяет, что TTL применяется одинаково для топиков форум-чатов.
        """
        # Создаем временный файл для кэша
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            cache_file = f.name
        
        try:
            manager = CacheManager(cache_file=cache_file)
            
            # Сохраняем топики
            manager.save_topics(chat_link, topics)
            
            # Свежие топики должны быть валидными
            assert manager.is_topics_valid(chat_link, max_age_days=max_age_days) is True, \
                "Свежие топики должны быть валидными"
            
            # Изменяем дату кэширования на устаревшую (больше max_age_days)
            old_date = (datetime.now() - timedelta(days=max_age_days + 1)).isoformat()
            manager.data['topics_cache'][chat_link]['cached_at'] = old_date
            
            # Устаревшие топики должны быть невалидными
            assert manager.is_topics_valid(chat_link, max_age_days=max_age_days) is False, \
                "Устаревшие топики должны быть невалидными"
            
            # Изменяем дату кэширования на граничное значение (ровно max_age_days - 1)
            boundary_date = (datetime.now() - timedelta(days=max_age_days - 1)).isoformat()
            manager.data['topics_cache'][chat_link]['cached_at'] = boundary_date
            
            # Топики на границе TTL должны быть валидными
            assert manager.is_topics_valid(chat_link, max_age_days=max_age_days) is True, \
                "Топики на границе TTL должны быть валидными"
        finally:
            # Cleanup
            if os.path.exists(cache_file):
                os.unlink(cache_file)
    
    @given(
        entity_data=entity_strategy(),
        chat_link1=chat_link_strategy(),
        chat_link2=chat_link_strategy(),
        topics=topics_strategy(),
        max_age_days=st.integers(min_value=1, max_value=30)
    )
    @settings(max_examples=100)
    def test_property_15_ttl_consistency_across_cache_types(
        self, entity_data, chat_link1, chat_link2, topics, max_age_days
    ):
        """
        Property 15 (расширенный): TTL консистентность между entity и topics
        
        **Validates: Requirements 11.5, 11.7**
        
        Проверяет, что TTL применяется одинаково для entity и топиков.
        """
        entity, source_type = entity_data
        
        # Создаем временный файл для кэша
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            cache_file = f.name
        
        try:
            manager = CacheManager(cache_file=cache_file)
            
            # Сохраняем entity и топики
            manager.save_entity(chat_link1, entity, source_type)
            manager.save_topics(chat_link2, topics)
            
            # Оба должны быть валидными
            assert manager.is_entity_valid(chat_link1, max_age_days=max_age_days) is True
            assert manager.is_topics_valid(chat_link2, max_age_days=max_age_days) is True
            
            # Устанавливаем одинаковую устаревшую дату для обоих
            old_date = (datetime.now() - timedelta(days=max_age_days + 1)).isoformat()
            manager.data['entity_cache'][chat_link1]['cached_at'] = old_date
            manager.data['topics_cache'][chat_link2]['cached_at'] = old_date
            
            # Оба должны быть невалидными с одинаковым TTL
            assert manager.is_entity_valid(chat_link1, max_age_days=max_age_days) is False
            assert manager.is_topics_valid(chat_link2, max_age_days=max_age_days) is False
        finally:
            # Cleanup
            if os.path.exists(cache_file):
                os.unlink(cache_file)
