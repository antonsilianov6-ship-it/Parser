# -*- coding: utf-8 -*-
"""Property-based тесты для CacheManager"""

import pytest
from hypothesis import given, settings, strategies as st
from datetime import datetime, timedelta
from src.cache.cache_manager import CacheManager, CacheEntry
from unittest.mock import Mock


# Стратегии для генерации данных
@st.composite
def entity_strategy(draw):
    """Генерирует mock entity с различными атрибутами"""
    entity = Mock()
    entity.id = draw(st.integers(min_value=1, max_value=999999999))
    entity.title = draw(st.text(min_size=1, max_size=100))
    entity.username = draw(st.text(min_size=0, max_size=32, 
                                   alphabet=st.characters(whitelist_categories=('Ll', 'Lu', 'Nd', 'P'))))
    return entity


@st.composite
def channel_link_strategy(draw):
    """Генерирует различные форматы ссылок на каналы/чаты"""
    link_type = draw(st.sampled_from(['public', 'private', 'username']))
    
    if link_type == 'public':
        name = draw(st.text(min_size=5, max_size=32, 
                           alphabet=st.characters(whitelist_categories=('Ll', 'Lu', 'Nd'))))
        return f"https://t.me/{name}"
    elif link_type == 'private':
        chat_id = draw(st.integers(min_value=1000000000, max_value=9999999999))
        return f"https://t.me/c/{chat_id}"
    else:
        name = draw(st.text(min_size=5, max_size=32, 
                           alphabet=st.characters(whitelist_categories=('Ll', 'Lu', 'Nd'))))
        return f"@{name}"


# Feature: chat-and-topic-support, Property 14: Entity caching with metadata
@given(
    source_type=st.sampled_from(['channel', 'chat', 'forum_chat']),
    entity=entity_strategy(),
    channel_link=channel_link_strategy()
)
@settings(max_examples=100)
def test_entity_caching_with_metadata_property(source_type, entity, channel_link):
    """
    Property 14: Entity caching with metadata
    
    For any entity (channel, chat, or forum_chat), the Cache_Manager SHALL cache it 
    along with its source_type metadata, and subsequent retrievals SHALL return both 
    the entity and its type without additional API calls.
    
    **Validates: Requirements 11.1, 11.2, 11.4**
    """
    # Создаем новый экземпляр CacheManager для изоляции теста
    cache_manager = CacheManager(cache_file=":memory:")
    
    # Сохраняем entity с метаданными
    cache_manager.save_entity(channel_link, entity, source_type)
    
    # Получаем entity из кэша
    cached_entity_data = cache_manager.get_entity(channel_link)
    
    # Проверяем что entity сохранен
    assert cached_entity_data is not None, "Entity должен быть сохранен в кэше"
    
    # Проверяем что все поля сохранены корректно
    assert cached_entity_data['channel_id'] == entity.id, "ID entity должен совпадать"
    assert cached_entity_data['title'] == entity.title, "Title entity должен совпадать"
    assert cached_entity_data['username'] == entity.username, "Username entity должен совпадать"
    assert cached_entity_data['source_type'] == source_type, "Source type должен совпадать"
    
    # Проверяем что cached_at установлен
    assert 'cached_at' in cached_entity_data, "Должна быть метка времени кэширования"
    cached_at = datetime.fromisoformat(cached_entity_data['cached_at'])
    assert isinstance(cached_at, datetime), "cached_at должен быть datetime"
    
    # Проверяем метод get_entity_with_type
    cached_entity_data2, cached_type = cache_manager.get_entity_with_type(channel_link)
    
    assert cached_entity_data2 is not None, "Entity должен быть получен через get_entity_with_type"
    assert cached_type == source_type, "Source type должен совпадать при получении через get_entity_with_type"
    assert cached_entity_data2 == cached_entity_data, "Данные должны совпадать при разных методах получения"


# Feature: chat-and-topic-support, Property 14: Entity caching with metadata (multiple entities)
@given(
    entities_data=st.lists(
        st.tuples(
            st.sampled_from(['channel', 'chat', 'forum_chat']),
            entity_strategy(),
            channel_link_strategy()
        ),
        min_size=1,
        max_size=10,
        unique_by=lambda x: x[2]  # Уникальность по channel_link
    )
)
@settings(max_examples=100)
def test_multiple_entities_caching_property(entities_data):
    """
    Property 14 (extended): Multiple entities caching
    
    For any set of entities, the Cache_Manager SHALL correctly cache and retrieve 
    each entity with its metadata independently.
    
    **Validates: Requirements 11.1, 11.2, 11.4**
    """
    cache_manager = CacheManager(cache_file=":memory:")
    
    # Сохраняем все entities
    for source_type, entity, channel_link in entities_data:
        cache_manager.save_entity(channel_link, entity, source_type)
    
    # Проверяем что все entities сохранены корректно
    for source_type, entity, channel_link in entities_data:
        cached_entity_data, cached_type = cache_manager.get_entity_with_type(channel_link)
        
        assert cached_entity_data is not None, f"Entity для {channel_link} должен быть в кэше"
        assert cached_entity_data['channel_id'] == entity.id
        assert cached_entity_data['source_type'] == source_type
        assert cached_type == source_type


# Feature: chat-and-topic-support, Property 14: Entity caching - cache miss
@given(
    channel_link=channel_link_strategy()
)
@settings(max_examples=100)
def test_entity_cache_miss_property(channel_link):
    """
    Property 14 (cache miss): Cache miss handling
    
    For any non-cached entity, the Cache_Manager SHALL return None.
    
    **Validates: Requirements 11.4**
    """
    cache_manager = CacheManager(cache_file=":memory:")
    
    # Пытаемся получить несуществующий entity
    cached_entity_data = cache_manager.get_entity(channel_link)
    assert cached_entity_data is None, "Несуществующий entity должен возвращать None"
    
    cached_entity_data2, cached_type = cache_manager.get_entity_with_type(channel_link)
    assert cached_entity_data2 is None, "Несуществующий entity должен возвращать None"
    assert cached_type is None, "Source type для несуществующего entity должен быть None"


# Feature: chat-and-topic-support, Property 14: Entity update
@given(
    source_type1=st.sampled_from(['channel', 'chat', 'forum_chat']),
    source_type2=st.sampled_from(['channel', 'chat', 'forum_chat']),
    entity1=entity_strategy(),
    entity2=entity_strategy(),
    channel_link=channel_link_strategy()
)
@settings(max_examples=100)
def test_entity_update_property(source_type1, source_type2, entity1, entity2, channel_link):
    """
    Property 14 (update): Entity update handling
    
    When an entity is updated in cache, the Cache_Manager SHALL store the new data 
    and return it on subsequent retrievals.
    
    **Validates: Requirements 11.1, 11.2, 11.4**
    """
    cache_manager = CacheManager(cache_file=":memory:")
    
    # Сохраняем первый entity
    cache_manager.save_entity(channel_link, entity1, source_type1)
    
    # Проверяем что первый entity сохранен
    cached_data1, cached_type1 = cache_manager.get_entity_with_type(channel_link)
    assert cached_data1['channel_id'] == entity1.id
    assert cached_type1 == source_type1
    
    # Обновляем entity
    cache_manager.save_entity(channel_link, entity2, source_type2)
    
    # Проверяем что entity обновлен
    cached_data2, cached_type2 = cache_manager.get_entity_with_type(channel_link)
    assert cached_data2['channel_id'] == entity2.id, "ID должен обновиться"
    assert cached_type2 == source_type2, "Source type должен обновиться"
    assert cached_data2['title'] == entity2.title, "Title должен обновиться"
    assert cached_data2['username'] == entity2.username, "Username должен обновиться"



# Feature: chat-and-topic-support, Property 15: Cache TTL consistency
@given(
    source_type=st.sampled_from(['channel', 'chat', 'forum_chat']),
    entity=entity_strategy(),
    channel_link=channel_link_strategy(),
    max_age_days=st.integers(min_value=1, max_value=30)
)
@settings(max_examples=100)
def test_cache_ttl_consistency_property(source_type, entity, channel_link, max_age_days):
    """
    Property 15: Cache TTL consistency
    
    For any cached entity or topic list, the Cache_Manager SHALL apply the same TTL 
    (time-to-live) settings regardless of source type, ensuring consistent cache 
    expiration behavior across channels, chats, and forum chats.
    
    **Validates: Requirements 11.5, 11.7**
    """
    cache_manager = CacheManager(cache_file=":memory:")
    
    # Сохраняем entity
    cache_manager.save_entity(channel_link, entity, source_type)
    
    # Проверяем что entity валиден сразу после сохранения
    is_valid = cache_manager.is_entity_valid(channel_link, max_age_days=max_age_days)
    assert is_valid is True, "Только что сохраненный entity должен быть валидным"
    
    # Получаем cached_at
    cached_entity_data = cache_manager.get_entity(channel_link)
    cached_at = datetime.fromisoformat(cached_entity_data['cached_at'])
    
    # Проверяем что TTL применяется одинаково независимо от source_type
    # Симулируем устаревание кэша, изменяя cached_at
    old_cached_at = (datetime.now() - timedelta(days=max_age_days + 1)).isoformat()
    cached_entity_data['cached_at'] = old_cached_at
    cache_manager.data['entity_cache'][channel_link] = cached_entity_data
    
    # Проверяем что entity теперь невалиден
    is_valid_after = cache_manager.is_entity_valid(channel_link, max_age_days=max_age_days)
    assert is_valid_after is False, f"Entity старше {max_age_days} дней должен быть невалидным"


# Feature: chat-and-topic-support, Property 15: Topics cache TTL consistency
@given(
    channel_link=channel_link_strategy(),
    topics=st.lists(
        st.tuples(
            st.integers(min_value=1, max_value=999999),
            st.text(min_size=1, max_size=100)
        ),
        min_size=1,
        max_size=20
    ),
    max_age_days=st.integers(min_value=1, max_value=30)
)
@settings(max_examples=100)
def test_topics_cache_ttl_consistency_property(channel_link, topics, max_age_days):
    """
    Property 15 (topics): Topics cache TTL consistency
    
    For any cached topics list, the Cache_Manager SHALL apply the same TTL settings 
    as for entities, ensuring consistent cache expiration behavior.
    
    **Validates: Requirements 11.5, 11.7**
    """
    cache_manager = CacheManager(cache_file=":memory:")
    
    # Сохраняем топики
    cache_manager.save_topics(channel_link, topics)
    
    # Проверяем что топики валидны сразу после сохранения
    is_valid = cache_manager.is_topics_valid(channel_link, max_age_days=max_age_days)
    assert is_valid is True, "Только что сохраненные топики должны быть валидными"
    
    # Симулируем устаревание кэша топиков
    topics_data = cache_manager.data['topics_cache'][channel_link]
    old_cached_at = (datetime.now() - timedelta(days=max_age_days + 1)).isoformat()
    topics_data['cached_at'] = old_cached_at
    cache_manager.data['topics_cache'][channel_link] = topics_data
    
    # Проверяем что топики теперь невалидны
    is_valid_after = cache_manager.is_topics_valid(channel_link, max_age_days=max_age_days)
    assert is_valid_after is False, f"Топики старше {max_age_days} дней должны быть невалидными"


# Feature: chat-and-topic-support, Property 15: TTL boundary testing
@given(
    source_type=st.sampled_from(['channel', 'chat', 'forum_chat']),
    entity=entity_strategy(),
    channel_link=channel_link_strategy()
)
@settings(max_examples=100)
def test_cache_ttl_boundary_property(source_type, entity, channel_link):
    """
    Property 15 (boundary): Cache TTL boundary testing
    
    The Cache_Manager SHALL correctly handle TTL boundary conditions (exactly at TTL limit).
    
    **Validates: Requirements 11.5, 11.7**
    """
    cache_manager = CacheManager(cache_file=":memory:")
    max_age_days = 7
    
    # Сохраняем entity
    cache_manager.save_entity(channel_link, entity, source_type)
    
    # Симулируем кэш ровно на границе TTL (7 дней - 1 секунда)
    cached_entity_data = cache_manager.get_entity(channel_link)
    boundary_cached_at = (datetime.now() - timedelta(days=max_age_days, seconds=-1)).isoformat()
    cached_entity_data['cached_at'] = boundary_cached_at
    cache_manager.data['entity_cache'][channel_link] = cached_entity_data
    
    # Должен быть валидным (еще не истек TTL)
    is_valid_before = cache_manager.is_entity_valid(channel_link, max_age_days=max_age_days)
    assert is_valid_before is True, "Entity на границе TTL (чуть меньше) должен быть валидным"
    
    # Симулируем кэш ровно на границе TTL (7 дней + 1 секунда)
    boundary_cached_at2 = (datetime.now() - timedelta(days=max_age_days, seconds=1)).isoformat()
    cached_entity_data['cached_at'] = boundary_cached_at2
    cache_manager.data['entity_cache'][channel_link] = cached_entity_data
    
    # Должен быть невалидным (истек TTL)
    is_valid_after = cache_manager.is_entity_valid(channel_link, max_age_days=max_age_days)
    assert is_valid_after is False, "Entity на границе TTL (чуть больше) должен быть невалидным"


# Feature: chat-and-topic-support, Property 15: TTL consistency across source types
@given(
    entities_data=st.lists(
        st.tuples(
            st.sampled_from(['channel', 'chat', 'forum_chat']),
            entity_strategy(),
            channel_link_strategy()
        ),
        min_size=2,
        max_size=5,
        unique_by=lambda x: x[2]  # Уникальность по channel_link
    ),
    max_age_days=st.integers(min_value=1, max_value=30)
)
@settings(max_examples=100)
def test_ttl_consistency_across_source_types_property(entities_data, max_age_days):
    """
    Property 15 (cross-type): TTL consistency across different source types
    
    The Cache_Manager SHALL apply the same TTL logic to all source types 
    (channel, chat, forum_chat) without discrimination.
    
    **Validates: Requirements 11.5, 11.7**
    """
    cache_manager = CacheManager(cache_file=":memory:")
    
    # Сохраняем все entities
    for source_type, entity, channel_link in entities_data:
        cache_manager.save_entity(channel_link, entity, source_type)
    
    # Проверяем что все entities валидны
    for source_type, entity, channel_link in entities_data:
        is_valid = cache_manager.is_entity_valid(channel_link, max_age_days=max_age_days)
        assert is_valid is True, f"Entity типа {source_type} должен быть валидным после сохранения"
    
    # Симулируем устаревание всех entities
    for source_type, entity, channel_link in entities_data:
        cached_entity_data = cache_manager.get_entity(channel_link)
        old_cached_at = (datetime.now() - timedelta(days=max_age_days + 1)).isoformat()
        cached_entity_data['cached_at'] = old_cached_at
        cache_manager.data['entity_cache'][channel_link] = cached_entity_data
    
    # Проверяем что все entities невалидны (TTL применяется одинаково)
    for source_type, entity, channel_link in entities_data:
        is_valid = cache_manager.is_entity_valid(channel_link, max_age_days=max_age_days)
        assert is_valid is False, f"Устаревший entity типа {source_type} должен быть невалидным"


# Feature: chat-and-topic-support, Property 15: Default TTL value
@given(
    source_type=st.sampled_from(['channel', 'chat', 'forum_chat']),
    entity=entity_strategy(),
    channel_link=channel_link_strategy()
)
@settings(max_examples=100)
def test_default_ttl_value_property(source_type, entity, channel_link):
    """
    Property 15 (default): Default TTL value consistency
    
    The Cache_Manager SHALL use the same default TTL value (7 days) for all source types 
    when max_age_days is not specified.
    
    **Validates: Requirements 11.5, 11.7**
    """
    cache_manager = CacheManager(cache_file=":memory:")
    
    # Сохраняем entity
    cache_manager.save_entity(channel_link, entity, source_type)
    
    # Проверяем с дефолтным TTL (7 дней)
    is_valid_default = cache_manager.is_entity_valid(channel_link)  # Без параметра max_age_days
    assert is_valid_default is True, "Entity должен быть валидным с дефолтным TTL"
    
    # Симулируем устаревание (8 дней)
    cached_entity_data = cache_manager.get_entity(channel_link)
    old_cached_at = (datetime.now() - timedelta(days=8)).isoformat()
    cached_entity_data['cached_at'] = old_cached_at
    cache_manager.data['entity_cache'][channel_link] = cached_entity_data
    
    # Проверяем что entity невалиден с дефолтным TTL
    is_valid_after = cache_manager.is_entity_valid(channel_link)  # Без параметра max_age_days
    assert is_valid_after is False, "Entity старше 7 дней должен быть невалидным с дефолтным TTL"
