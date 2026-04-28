# -*- coding: utf-8 -*-
"""Unit тесты для CacheManager"""

import os
import json
import pytest
import tempfile
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
from src.cache.cache_manager import CacheManager, CacheEntry


class TestCacheEntry:
    """Тесты для dataclass CacheEntry"""
    
    def test_cache_entry_creation(self):
        """Тест создания CacheEntry"""
        entry = CacheEntry(
            channel_id=123456,
            title="Test Channel",
            username="testchannel",
            cached_at="2024-01-01T12:00:00"
        )
        
        assert entry.channel_id == 123456
        assert entry.title == "Test Channel"
        assert entry.username == "testchannel"
        assert entry.cached_at == "2024-01-01T12:00:00"
    
    def test_cache_entry_to_dict(self):
        """Тест конвертации CacheEntry в словарь"""
        entry = CacheEntry(
            channel_id=123456,
            title="Test Channel",
            username="testchannel",
            cached_at="2024-01-01T12:00:00"
        )
        
        entry_dict = entry.to_dict()
        
        assert isinstance(entry_dict, dict)
        assert entry_dict['channel_id'] == 123456
        assert entry_dict['title'] == "Test Channel"
        assert entry_dict['username'] == "testchannel"
        assert entry_dict['cached_at'] == "2024-01-01T12:00:00"
    
    def test_cache_entry_from_dict(self):
        """Тест создания CacheEntry из словаря"""
        data = {
            'channel_id': 123456,
            'title': "Test Channel",
            'username': "testchannel",
            'cached_at': "2024-01-01T12:00:00"
        }
        
        entry = CacheEntry.from_dict(data)
        
        assert entry.channel_id == 123456
        assert entry.title == "Test Channel"
        assert entry.username == "testchannel"
        assert entry.cached_at == "2024-01-01T12:00:00"


class TestCacheManagerInit:
    """Тесты инициализации CacheManager"""
    
    def test_init_with_default_cache_file(self):
        """Тест инициализации с дефолтным файлом кэша"""
        with patch('src.cache.cache_manager.CACHE_FILE', 'test_cache.json'):
            manager = CacheManager()
            assert manager.cache_file == 'test_cache.json'
            assert manager.loaded is False
            assert 'entity_cache' in manager.data
            assert 'processed_links' in manager.data
            assert 'metadata' in manager.data
    
    def test_init_with_custom_cache_file(self):
        """Тест инициализации с кастомным файлом кэша"""
        manager = CacheManager(cache_file='custom_cache.json')
        assert manager.cache_file == 'custom_cache.json'
    
    def test_init_creates_cache_directory(self):
        """Тест создания директории для кэша при инициализации"""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_file = os.path.join(tmpdir, 'subdir', 'cache.json')
            manager = CacheManager(cache_file=cache_file)
            
            assert os.path.exists(os.path.dirname(cache_file))


class TestEntityCache:
    """Тесты для работы с entity cache"""
    
    @pytest.fixture
    def manager(self):
        """Фикстура для создания CacheManager с временным файлом"""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            cache_file = f.name
        
        manager = CacheManager(cache_file=cache_file)
        yield manager
        
        # Cleanup
        if os.path.exists(cache_file):
            os.unlink(cache_file)
    
    def test_save_entity(self, manager):
        """Тест сохранения entity в кэш"""
        mock_entity = Mock()
        mock_entity.id = 123456
        mock_entity.title = "Test Channel"
        mock_entity.username = "testchannel"
        
        manager.save_entity("https://t.me/testchannel", mock_entity)
        
        entity_data = manager.get_entity("https://t.me/testchannel")
        assert entity_data is not None
        assert entity_data['channel_id'] == 123456
        assert entity_data['title'] == "Test Channel"
        assert entity_data['username'] == "testchannel"
        assert 'cached_at' in entity_data
    
    def test_get_entity_not_found(self, manager):
        """Тест получения несуществующего entity"""
        entity_data = manager.get_entity("https://t.me/nonexistent")
        assert entity_data is None
    
    def test_get_entity_found(self, manager):
        """Тест получения существующего entity"""
        mock_entity = Mock()
        mock_entity.id = 123456
        mock_entity.title = "Test Channel"
        mock_entity.username = "testchannel"
        
        manager.save_entity("https://t.me/testchannel", mock_entity)
        entity_data = manager.get_entity("https://t.me/testchannel")
        
        assert entity_data is not None
        assert entity_data['channel_id'] == 123456
    
    def test_is_entity_valid_fresh(self, manager):
        """Тест валидации свежего entity"""
        mock_entity = Mock()
        mock_entity.id = 123456
        mock_entity.title = "Test Channel"
        mock_entity.username = "testchannel"
        
        manager.save_entity("https://t.me/testchannel", mock_entity)
        
        is_valid = manager.is_entity_valid("https://t.me/testchannel", max_age_days=7)
        assert is_valid is True
    
    def test_is_entity_valid_expired(self, manager):
        """Тест валидации устаревшего entity"""
        mock_entity = Mock()
        mock_entity.id = 123456
        mock_entity.title = "Test Channel"
        mock_entity.username = "testchannel"
        
        manager.save_entity("https://t.me/testchannel", mock_entity)
        
        # Изменяем дату кэширования на 10 дней назад
        old_date = (datetime.now() - timedelta(days=10)).isoformat()
        manager.data['entity_cache']["https://t.me/testchannel"]['cached_at'] = old_date
        
        is_valid = manager.is_entity_valid("https://t.me/testchannel", max_age_days=7)
        assert is_valid is False
    
    def test_is_entity_valid_not_found(self, manager):
        """Тест валидации несуществующего entity"""
        is_valid = manager.is_entity_valid("https://t.me/nonexistent")
        assert is_valid is False
    
    def test_is_entity_valid_custom_max_age(self, manager):
        """Тест валидации с кастомным max_age"""
        mock_entity = Mock()
        mock_entity.id = 123456
        mock_entity.title = "Test Channel"
        mock_entity.username = "testchannel"
        
        manager.save_entity("https://t.me/testchannel", mock_entity)
        
        # Изменяем дату кэширования на 5 дней назад
        old_date = (datetime.now() - timedelta(days=5)).isoformat()
        manager.data['entity_cache']["https://t.me/testchannel"]['cached_at'] = old_date
        
        # С max_age=7 должен быть валидным
        assert manager.is_entity_valid("https://t.me/testchannel", max_age_days=7) is True
        
        # С max_age=3 должен быть невалидным
        assert manager.is_entity_valid("https://t.me/testchannel", max_age_days=3) is False
    
    def test_get_all_entities(self, manager):
        """Тест получения всех entity"""
        mock_entity1 = Mock()
        mock_entity1.id = 111
        mock_entity1.title = "Channel 1"
        mock_entity1.username = "channel1"
        
        mock_entity2 = Mock()
        mock_entity2.id = 222
        mock_entity2.title = "Channel 2"
        mock_entity2.username = "channel2"
        
        manager.save_entity("https://t.me/channel1", mock_entity1)
        manager.save_entity("https://t.me/channel2", mock_entity2)
        
        all_entities = manager.get_all_entities()
        
        assert len(all_entities) == 2
        assert "https://t.me/channel1" in all_entities
        assert "https://t.me/channel2" in all_entities
    
    def test_clear_entity_cache(self, manager):
        """Тест очистки entity cache"""
        mock_entity = Mock()
        mock_entity.id = 123456
        mock_entity.title = "Test Channel"
        mock_entity.username = "testchannel"
        
        manager.save_entity("https://t.me/testchannel", mock_entity)
        assert len(manager.get_all_entities()) == 1
        
        manager.clear_entity_cache()
        assert len(manager.get_all_entities()) == 0


class TestProcessedLinks:
    """Тесты для работы с processed links"""
    
    @pytest.fixture
    def manager(self):
        """Фикстура для создания CacheManager с временным файлом"""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            cache_file = f.name
        
        manager = CacheManager(cache_file=cache_file)
        yield manager
        
        # Cleanup
        if os.path.exists(cache_file):
            os.unlink(cache_file)
    
    def test_get_processed_links_empty(self, manager):
        """Тест получения пустого списка обработанных ссылок"""
        links = manager.get_processed_links()
        assert isinstance(links, set)
        assert len(links) == 0
    
    def test_add_processed_link(self, manager):
        """Тест добавления обработанной ссылки"""
        manager.add_processed_link("https://t.me/channel1/123")
        
        links = manager.get_processed_links()
        assert "https://t.me/channel1/123" in links
        assert len(links) == 1
    
    def test_add_multiple_processed_links(self, manager):
        """Тест добавления нескольких обработанных ссылок"""
        manager.add_processed_link("https://t.me/channel1/123")
        manager.add_processed_link("https://t.me/channel2/456")
        manager.add_processed_link("https://t.me/channel3/789")
        
        links = manager.get_processed_links()
        assert len(links) == 3
        assert "https://t.me/channel1/123" in links
        assert "https://t.me/channel2/456" in links
        assert "https://t.me/channel3/789" in links
    
    def test_add_duplicate_processed_link(self, manager):
        """Тест добавления дублирующейся ссылки"""
        manager.add_processed_link("https://t.me/channel1/123")
        manager.add_processed_link("https://t.me/channel1/123")
        
        links = manager.get_processed_links()
        assert len(links) == 1
    
    def test_remove_processed_link(self, manager):
        """Тест удаления обработанной ссылки"""
        manager.add_processed_link("https://t.me/channel1/123")
        manager.add_processed_link("https://t.me/channel2/456")
        
        result = manager.remove_processed_link("https://t.me/channel1/123")
        
        assert result is True
        links = manager.get_processed_links()
        assert len(links) == 1
        assert "https://t.me/channel1/123" not in links
        assert "https://t.me/channel2/456" in links
    
    def test_remove_nonexistent_processed_link(self, manager):
        """Тест удаления несуществующей ссылки"""
        result = manager.remove_processed_link("https://t.me/nonexistent/999")
        assert result is False
    
    def test_clear_processed_links(self, manager):
        """Тест очистки списка обработанных ссылок"""
        manager.add_processed_link("https://t.me/channel1/123")
        manager.add_processed_link("https://t.me/channel2/456")
        
        assert len(manager.get_processed_links()) == 2
        
        manager.clear_processed_links()
        
        links = manager.get_processed_links()
        assert len(links) == 0


class TestCachePersistence:
    """Тесты для сохранения и загрузки кэша"""
    
    @pytest.fixture
    def cache_file(self):
        """Фикстура для создания временного файла кэша"""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            cache_file = f.name
        
        yield cache_file
        
        # Cleanup
        if os.path.exists(cache_file):
            os.unlink(cache_file)
    
    def test_save_and_load(self, cache_file):
        """Тест сохранения и загрузки кэша"""
        # Создаем менеджер и добавляем данные
        manager1 = CacheManager(cache_file=cache_file)
        
        mock_entity = Mock()
        mock_entity.id = 123456
        mock_entity.title = "Test Channel"
        mock_entity.username = "testchannel"
        
        manager1.save_entity("https://t.me/testchannel", mock_entity)
        manager1.add_processed_link("https://t.me/channel1/123")
        
        # Сохраняем
        result = manager1.save()
        assert result is True
        
        # Создаем новый менеджер и загружаем
        manager2 = CacheManager(cache_file=cache_file)
        manager2.load()
        
        # Проверяем, что данные загрузились
        entity_data = manager2.get_entity("https://t.me/testchannel")
        assert entity_data is not None
        assert entity_data['channel_id'] == 123456
        
        links = manager2.get_processed_links()
        assert "https://t.me/channel1/123" in links
    
    def test_load_nonexistent_file(self, cache_file):
        """Тест загрузки несуществующего файла"""
        # Удаляем файл, если он существует
        if os.path.exists(cache_file):
            os.unlink(cache_file)
        
        manager = CacheManager(cache_file=cache_file)
        data = manager.load()
        
        assert manager.loaded is True
        assert 'entity_cache' in data
        assert 'processed_links' in data
        assert 'metadata' in data
    
    def test_load_corrupted_file(self, cache_file):
        """Тест загрузки поврежденного файла"""
        # Создаем поврежденный JSON файл
        with open(cache_file, 'w') as f:
            f.write("{ invalid json }")
        
        manager = CacheManager(cache_file=cache_file)
        data = manager.load()
        
        # Должен создать пустой кэш
        assert manager.loaded is True
        assert 'entity_cache' in data
        assert len(data['entity_cache']) == 0
        
        # Должна быть создана резервная копия
        backup_files = [f for f in os.listdir(os.path.dirname(cache_file)) 
                       if f.startswith(os.path.basename(cache_file) + '.bak')]
        assert len(backup_files) > 0
    
    def test_save_updates_metadata(self, cache_file):
        """Тест обновления метаданных при сохранении"""
        manager = CacheManager(cache_file=cache_file)
        manager.save()
        
        assert 'last_updated' in manager.data['metadata']
        assert manager.data['metadata']['last_updated'] is not None
    
    def test_multiple_save_load_cycles(self, cache_file):
        """Тест множественных циклов сохранения/загрузки"""
        manager = CacheManager(cache_file=cache_file)
        
        # Цикл 1
        mock_entity1 = Mock()
        mock_entity1.id = 111
        mock_entity1.title = "Channel 1"
        mock_entity1.username = "channel1"
        manager.save_entity("https://t.me/channel1", mock_entity1)
        manager.save()
        
        # Цикл 2
        manager.load()
        mock_entity2 = Mock()
        mock_entity2.id = 222
        mock_entity2.title = "Channel 2"
        mock_entity2.username = "channel2"
        manager.save_entity("https://t.me/channel2", mock_entity2)
        manager.save()
        
        # Цикл 3
        manager.load()
        all_entities = manager.get_all_entities()
        
        assert len(all_entities) == 2
        assert "https://t.me/channel1" in all_entities
        assert "https://t.me/channel2" in all_entities


class TestCacheClear:
    """Тесты для очистки кэша"""
    
    @pytest.fixture
    def manager(self):
        """Фикстура для создания CacheManager с временным файлом"""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            cache_file = f.name
        
        manager = CacheManager(cache_file=cache_file)
        yield manager
        
        # Cleanup
        if os.path.exists(cache_file):
            os.unlink(cache_file)
    
    def test_clear_all_cache(self, manager):
        """Тест полной очистки кэша"""
        # Добавляем данные
        mock_entity = Mock()
        mock_entity.id = 123456
        mock_entity.title = "Test Channel"
        mock_entity.username = "testchannel"
        
        manager.save_entity("https://t.me/testchannel", mock_entity)
        manager.add_processed_link("https://t.me/channel1/123")
        
        # Очищаем
        manager.clear()
        
        # Проверяем, что все очищено
        assert len(manager.get_all_entities()) == 0
        assert len(manager.get_processed_links()) == 0
        assert 'last_updated' in manager.data['metadata']


class TestCacheStats:
    """Тесты для статистики кэша"""
    
    @pytest.fixture
    def manager(self):
        """Фикстура для создания CacheManager с временным файлом"""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            cache_file = f.name
        
        manager = CacheManager(cache_file=cache_file)
        yield manager
        
        # Cleanup
        if os.path.exists(cache_file):
            os.unlink(cache_file)
    
    def test_get_cache_stats_empty(self, manager):
        """Тест получения статистики пустого кэша"""
        stats = manager.get_cache_stats()
        
        assert stats['entity_count'] == 0
        assert stats['processed_links_count'] == 0
        assert stats['loaded'] is False
        assert 'cache_file' in stats
    
    def test_get_cache_stats_with_data(self, manager):
        """Тест получения статистики кэша с данными"""
        mock_entity1 = Mock()
        mock_entity1.id = 111
        mock_entity1.title = "Channel 1"
        mock_entity1.username = "channel1"
        
        mock_entity2 = Mock()
        mock_entity2.id = 222
        mock_entity2.title = "Channel 2"
        mock_entity2.username = "channel2"
        
        manager.save_entity("https://t.me/channel1", mock_entity1)
        manager.save_entity("https://t.me/channel2", mock_entity2)
        manager.add_processed_link("https://t.me/channel1/123")
        manager.add_processed_link("https://t.me/channel2/456")
        manager.add_processed_link("https://t.me/channel3/789")
        
        stats = manager.get_cache_stats()
        
        assert stats['entity_count'] == 2
        assert stats['processed_links_count'] == 3


@pytest.mark.asyncio
class TestAsyncOperations:
    """Тесты для асинхронных операций"""
    
    @pytest.fixture
    def cache_file(self):
        """Фикстура для создания временного файла кэша"""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            cache_file = f.name
        
        yield cache_file
        
        # Cleanup
        if os.path.exists(cache_file):
            os.unlink(cache_file)
    
    async def test_async_save_and_load(self, cache_file):
        """Тест асинхронного сохранения и загрузки"""
        # Создаем менеджер и добавляем данные
        manager1 = CacheManager(cache_file=cache_file)
        
        mock_entity = Mock()
        mock_entity.id = 123456
        mock_entity.title = "Test Channel"
        mock_entity.username = "testchannel"
        
        manager1.save_entity("https://t.me/testchannel", mock_entity)
        
        # Асинхронно сохраняем
        result = await manager1.save_async()
        assert result is True
        
        # Создаем новый менеджер и асинхронно загружаем
        manager2 = CacheManager(cache_file=cache_file)
        await manager2.load_async()
        
        # Проверяем, что данные загрузились
        entity_data = manager2.get_entity("https://t.me/testchannel")
        assert entity_data is not None
        assert entity_data['channel_id'] == 123456
    
    async def test_async_load_nonexistent_file(self, cache_file):
        """Тест асинхронной загрузки несуществующего файла"""
        # Удаляем файл, если он существует
        if os.path.exists(cache_file):
            os.unlink(cache_file)
        
        manager = CacheManager(cache_file=cache_file)
        data = await manager.load_async()
        
        assert manager.loaded is True
        assert 'entity_cache' in data
        assert 'processed_links' in data
