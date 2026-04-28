# -*- coding: utf-8 -*-
"""Integration тесты для UnifiedParser"""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from src.core.unified_parser import UnifiedParser
from src.telegram.message_fetcher import Message, Comment
from telethon.errors import FloodWaitError, ChannelPrivateError


@pytest.fixture
def mock_config():
    """Мок конфигурации"""
    with patch('src.core.unified_parser.get_parser_config') as mock_parser, \
         patch('src.core.unified_parser.get_database_config') as mock_db, \
         patch('src.core.unified_parser.DATABASE_CONFIG', {'DB_PATH': ':memory:'}):
        
        mock_parser.return_value = {
            'DAYS_FOR_EXPORT': 3,
            'FETCH_COMMENTS': True,
            'MAX_COMMENTS_PER_POST': 50
        }
        mock_db.return_value = {
            'BATCH_SIZE': 100,
            'USE_TRANSACTIONS': True
        }
        yield


@pytest.fixture
def sample_messages():
    """Примеры сообщений для тестов"""
    return [
        Message(
            date=datetime.now() - timedelta(days=1),
            text="Тестовое сообщение 1",
            link="https://t.me/testchannel/1",
            title="Test Channel",
            previous_post=None,
            comments=[]
        ),
        Message(
            date=datetime.now() - timedelta(days=2),
            text="Тестовое сообщение 2",
            link="https://t.me/testchannel/2",
            title="Test Channel",
            previous_post=None,
            comments=[
                Comment(author="User1", link="https://t.me/testchannel/2/c1", text="Комментарий 1")
            ]
        )
    ]


@pytest.mark.asyncio
async def test_init_async(mock_config):
    """Тест асинхронной инициализации"""
    parser = UnifiedParser()
    
    with patch.object(parser.connection_manager, 'connect', new_callable=AsyncMock) as mock_connect, \
         patch.object(parser.cache_manager, 'load_async', new_callable=AsyncMock) as mock_load, \
         patch.object(parser.cache_manager, 'get_processed_links', return_value=set()):
        
        await parser.init_async()
        
        mock_connect.assert_called_once()
        mock_load.assert_called_once()
        assert parser.message_fetcher is not None
        assert parser.comment_fetcher is not None


@pytest.mark.asyncio
async def test_parse_channel_success(mock_config, sample_messages):
    """Тест успешного парсинга канала"""
    parser = UnifiedParser()
    
    with patch.object(parser.connection_manager, 'connect', new_callable=AsyncMock), \
         patch.object(parser.cache_manager, 'load_async', new_callable=AsyncMock), \
         patch.object(parser.cache_manager, 'get_processed_links', return_value=set()):
        
        await parser.init_async()
        
        with patch.object(
            parser.message_fetcher,
            'fetch_channel_messages',
            new_callable=AsyncMock,
            return_value=sample_messages
        ):
            messages = await parser.parse_channel("https://t.me/testchannel")
            
            assert len(messages) == 2
            assert messages[0].text == "Тестовое сообщение 1"
            assert messages[1].text == "Тестовое сообщение 2"


@pytest.mark.asyncio
async def test_parse_channel_with_retry(mock_config):
    """Тест парсинга канала с retry при ошибке"""
    parser = UnifiedParser()
    
    with patch.object(parser.connection_manager, 'connect', new_callable=AsyncMock), \
         patch.object(parser.cache_manager, 'load_async', new_callable=AsyncMock), \
         patch.object(parser.cache_manager, 'get_processed_links', return_value=set()):
        
        await parser.init_async()
        
        # Первая попытка - ошибка, вторая - успех
        call_count = 0
        async def mock_fetch(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("Network error")
            return []
        
        with patch.object(
            parser.message_fetcher,
            'fetch_channel_messages',
            side_effect=mock_fetch
        ):
            messages = await parser.parse_channel("https://t.me/testchannel", retry_count=3)
            
            assert call_count == 2
            assert messages == []


@pytest.mark.asyncio
async def test_parse_channel_flood_wait_error(mock_config):
    """Тест обработки FloodWaitError с автоматическим retry"""
    parser = UnifiedParser()
    
    with patch.object(parser.connection_manager, 'connect', new_callable=AsyncMock), \
         patch.object(parser.cache_manager, 'load_async', new_callable=AsyncMock), \
         patch.object(parser.cache_manager, 'get_processed_links', return_value=set()):
        
        await parser.init_async()
        
        # Создаем мок FloodWaitError
        flood_error = FloodWaitError(request=None, capture=1)
        
        with patch.object(
            parser.message_fetcher,
            'fetch_channel_messages',
            new_callable=AsyncMock,
            side_effect=flood_error
        ):
            messages = await parser.parse_channel("https://t.me/testchannel", retry_count=1)
            
            # Должен вернуть пустой список после исчерпания попыток
            assert messages == []
            assert parser.stats['total_errors'] == 1


@pytest.mark.asyncio
async def test_parse_channel_private_error(mock_config):
    """Тест обработки приватного/недоступного канала"""
    parser = UnifiedParser()
    
    with patch.object(parser.connection_manager, 'connect', new_callable=AsyncMock), \
         patch.object(parser.cache_manager, 'load_async', new_callable=AsyncMock), \
         patch.object(parser.cache_manager, 'get_processed_links', return_value=set()):
        
        await parser.init_async()
        
        # Создаем мок ChannelPrivateError
        private_error = ChannelPrivateError(request=None)
        
        with patch.object(
            parser.message_fetcher,
            'fetch_channel_messages',
            new_callable=AsyncMock,
            side_effect=private_error
        ):
            messages = await parser.parse_channel("https://t.me/privatechannel", retry_count=1)
            
            # Должен вернуть пустой список и не падать
            assert messages == []
            assert parser.stats['total_errors'] == 1


@pytest.mark.asyncio
async def test_process_messages(mock_config, sample_messages):
    """Тест обработки сообщений и фильтрации новых"""
    parser = UnifiedParser()
    
    with patch.object(parser.cache_manager, 'save_async', new_callable=AsyncMock):
        # Первый раз - все сообщения новые
        new_messages = await parser.process_messages(sample_messages, "Test Channel")
        assert len(new_messages) == 2
        assert len(parser.processed_links) == 2
        
        # Второй раз - все сообщения уже обработаны
        new_messages = await parser.process_messages(sample_messages, "Test Channel")
        assert len(new_messages) == 0


@pytest.mark.asyncio
async def test_export_to_google_docs(mock_config):
    """Тест экспорта в Google Docs"""
    parser = UnifiedParser()
    
    messages_data = [
        {
            'date': '2024-01-01 12:00:00',
            'channel': 'Test Channel',
            'link': 'https://t.me/testchannel/1',
            'title': 'Test',
            'text': 'Test message',
            'previous_post': None,
            'comments': []
        }
    ]
    
    with patch.object(
        parser.docs_exporter,
        'append_new_content',
        new_callable=Mock
    ) as mock_export:
        await parser.export_to_google_docs(messages_data)
        mock_export.assert_called_once_with(messages_data)


@pytest.mark.asyncio
async def test_export_to_google_docs_empty(mock_config):
    """Тест экспорта пустого списка сообщений"""
    parser = UnifiedParser()
    
    with patch.object(
        parser.docs_exporter,
        'append_new_content',
        new_callable=Mock
    ) as mock_export:
        await parser.export_to_google_docs([])
        mock_export.assert_not_called()


@pytest.mark.asyncio
async def test_parse_channels(mock_config, sample_messages):
    """Тест парсинга списка каналов"""
    parser = UnifiedParser()
    
    with patch.object(parser.connection_manager, 'connect', new_callable=AsyncMock), \
         patch.object(parser.cache_manager, 'load_async', new_callable=AsyncMock), \
         patch.object(parser.cache_manager, 'get_processed_links', return_value=set()):
        
        await parser.init_async()
        
        with patch.object(
            parser.message_fetcher,
            'fetch_messages_batch',
            new_callable=AsyncMock,
            return_value={'testchannel': sample_messages}
        ), patch.object(parser.db, 'add_parse_stats'):
            
            result = await parser.parse_channels({'https://t.me/testchannel'})
            
            assert 'testchannel' in result
            assert len(result['testchannel']) == 2
            assert parser.stats['channels_processed'] == 1


def test_get_statistics(mock_config):
    """Тест получения статистики"""
    parser = UnifiedParser()
    
    parser.stats['start_time'] = datetime.now()
    parser.stats['end_time'] = datetime.now() + timedelta(seconds=10)
    
    mock_db_stats = {'total_messages': 100}
    mock_source_type_stats = {
        'by_source_type': {'channel': 100},
        'forum_topics': []
    }
    
    with patch.object(parser.db, 'get_stats', return_value=mock_db_stats), \
         patch.object(parser.db, 'get_stats_by_source_type', return_value=mock_source_type_stats):
        stats = parser.get_statistics()
        
        assert 'current_session' in stats
        assert 'database' in stats
        assert 'source_types' in stats
        assert 'forum_topics' in stats
        assert 'errors' in stats
        assert 'cache' in stats
        assert 'duration_seconds' in stats['current_session']


def test_setup_scheduler(mock_config):
    """Тест настройки планировщика"""
    parser = UnifiedParser()
    
    with patch('src.core.unified_parser.scheduler') as mock_scheduler:
        parser.setup_scheduler()
        
        assert mock_scheduler.add_daily_task.call_count == 2
        mock_scheduler.start.assert_called_once()


@pytest.mark.asyncio
async def test_cleanup(mock_config):
    """Тест очистки ресурсов"""
    parser = UnifiedParser()
    
    with patch.object(parser.connection_manager, 'is_connected', return_value=True), \
         patch.object(parser.connection_manager, 'disconnect', new_callable=AsyncMock) as mock_disconnect, \
         patch.object(parser.cache_manager, 'save_async', new_callable=AsyncMock) as mock_save, \
         patch('src.core.unified_parser.scheduler') as mock_scheduler:
        
        await parser.cleanup()
        
        mock_disconnect.assert_called_once()
        mock_save.assert_called_once()
        mock_scheduler.stop.assert_called_once()


def test_get_statistics_with_source_types(mock_config):
    """
    Тест корректности подсчета сообщений по типам источников
    Requirements: 9.5, 9.6, 13.7
    """
    parser = UnifiedParser()
    
    parser.stats['start_time'] = datetime.now()
    parser.stats['end_time'] = datetime.now() + timedelta(seconds=10)
    
    # Мокаем статистику БД
    mock_db_stats = {
        'total_messages': 150,
        'total_channels': 5,
        'channel_stats': []
    }
    
    mock_source_type_stats = {
        'by_source_type': {
            'channel': 50,
            'chat': 60,
            'forum_chat': 40
        },
        'forum_topics': []
    }
    
    with patch.object(parser.db, 'get_stats', return_value=mock_db_stats), \
         patch.object(parser.db, 'get_stats_by_source_type', return_value=mock_source_type_stats):
        
        stats = parser.get_statistics()
        
        # Проверяем наличие статистики по типам источников
        assert 'source_types' in stats
        assert 'forum_topics' in stats
        
        # Проверяем корректность подсчета по типам
        assert stats['source_types']['channel'] == 50
        assert stats['source_types']['chat'] == 60
        assert stats['source_types']['forum_chat'] == 40
        
        # Проверяем общее количество
        total = sum(stats['source_types'].values())
        assert total == 150


def test_get_statistics_with_forum_topics(mock_config):
    """
    Тест корректности подсчета топиков и сообщений в них
    Requirements: 9.5, 9.6, 13.7
    """
    parser = UnifiedParser()
    
    parser.stats['start_time'] = datetime.now()
    parser.stats['end_time'] = datetime.now() + timedelta(seconds=10)
    
    # Мокаем статистику БД с топиками
    mock_db_stats = {
        'total_messages': 100,
        'total_channels': 3,
        'channel_stats': []
    }
    
    mock_source_type_stats = {
        'by_source_type': {
            'channel': 30,
            'chat': 20,
            'forum_chat': 50
        },
        'forum_topics': [
            {'topic_id': 1, 'topic_title': 'Общие вопросы', 'messages_count': 25},
            {'topic_id': 2, 'topic_title': 'Технические проблемы', 'messages_count': 15},
            {'topic_id': 3, 'topic_title': 'Новости', 'messages_count': 10}
        ]
    }
    
    with patch.object(parser.db, 'get_stats', return_value=mock_db_stats), \
         patch.object(parser.db, 'get_stats_by_source_type', return_value=mock_source_type_stats):
        
        stats = parser.get_statistics()
        
        # Проверяем наличие информации о топиках
        assert 'forum_topics' in stats
        assert len(stats['forum_topics']) == 3
        
        # Проверяем корректность данных топиков
        assert stats['forum_topics'][0]['topic_id'] == 1
        assert stats['forum_topics'][0]['topic_title'] == 'Общие вопросы'
        assert stats['forum_topics'][0]['messages_count'] == 25
        
        assert stats['forum_topics'][1]['topic_id'] == 2
        assert stats['forum_topics'][1]['topic_title'] == 'Технические проблемы'
        assert stats['forum_topics'][1]['messages_count'] == 15
        
        assert stats['forum_topics'][2]['topic_id'] == 3
        assert stats['forum_topics'][2]['topic_title'] == 'Новости'
        assert stats['forum_topics'][2]['messages_count'] == 10
        
        # Проверяем что сумма сообщений в топиках соответствует forum_chat
        total_topic_messages = sum(t['messages_count'] for t in stats['forum_topics'])
        assert total_topic_messages == 50
        assert stats['source_types']['forum_chat'] == 50


def test_get_statistics_empty_topics(mock_config):
    """
    Тест статистики когда нет форум-чатов с топиками
    Requirements: 9.5, 9.6, 13.7
    """
    parser = UnifiedParser()
    
    parser.stats['start_time'] = datetime.now()
    parser.stats['end_time'] = datetime.now() + timedelta(seconds=10)
    
    # Мокаем статистику БД без топиков
    mock_db_stats = {
        'total_messages': 80,
        'total_channels': 4,
        'channel_stats': []
    }
    
    mock_source_type_stats = {
        'by_source_type': {
            'channel': 50,
            'chat': 30
        },
        'forum_topics': []
    }
    
    with patch.object(parser.db, 'get_stats', return_value=mock_db_stats), \
         patch.object(parser.db, 'get_stats_by_source_type', return_value=mock_source_type_stats):
        
        stats = parser.get_statistics()
        
        # Проверяем что forum_topics пустой
        assert 'forum_topics' in stats
        assert len(stats['forum_topics']) == 0
        
        # Проверяем что forum_chat отсутствует в source_types
        assert 'forum_chat' not in stats['source_types']
        
        # Проверяем корректность других типов
        assert stats['source_types']['channel'] == 50
        assert stats['source_types']['chat'] == 30


def test_get_statistics_logging(mock_config):
    """
    Тест логирования статистики по типам источников и топикам
    Requirements: 9.5, 9.6, 13.7
    
    Примечание: Этот тест проверяет что метод get_statistics() вызывает logger.info
    с правильными сообщениями. Фактическое логирование проверяется визуально при запуске.
    """
    parser = UnifiedParser()
    
    parser.stats['start_time'] = datetime.now()
    parser.stats['end_time'] = datetime.now() + timedelta(seconds=10)
    
    # Мокаем статистику БД с топиками
    mock_db_stats = {
        'total_messages': 100,
        'total_channels': 3,
        'channel_stats': []
    }
    
    mock_source_type_stats = {
        'by_source_type': {
            'channel': 30,
            'chat': 20,
            'forum_chat': 50
        },
        'forum_topics': [
            {'topic_id': 1, 'topic_title': 'Топик 1', 'messages_count': 25},
            {'topic_id': 2, 'topic_title': 'Топик 2', 'messages_count': 15},
            {'topic_id': 3, 'topic_title': 'Топик 3', 'messages_count': 10}
        ]
    }
    
    with patch.object(parser.db, 'get_stats', return_value=mock_db_stats), \
         patch.object(parser.db, 'get_stats_by_source_type', return_value=mock_source_type_stats), \
         patch('src.core.unified_parser.logger') as mock_logger:
        
        stats = parser.get_statistics()
        
        # Проверяем что logger.info был вызван с правильными сообщениями
        info_calls = [call[0][0] for call in mock_logger.info.call_args_list]
        
        # Проверяем заголовок статистики по типам источников
        assert any('Статистика по типам источников' in msg for msg in info_calls)
        
        # Проверяем логирование каждого типа источника
        assert any('channel: 30 сообщений' in msg for msg in info_calls)
        assert any('chat: 20 сообщений' in msg for msg in info_calls)
        assert any('forum_chat: 50 сообщений' in msg for msg in info_calls)
        
        # Проверяем заголовок статистики по топикам
        assert any('Статистика по топикам' in msg and '3 уникальных топиков' in msg for msg in info_calls)
        
        # Проверяем логирование топиков
        assert any('Топик 1' in msg and '25 сообщений' in msg for msg in info_calls)
        assert any('Топик 2' in msg and '15 сообщений' in msg for msg in info_calls)
        assert any('Топик 3' in msg and '10 сообщений' in msg for msg in info_calls)


def test_get_statistics_many_topics_truncation(mock_config):
    """
    Тест логирования статистики когда топиков больше 10 (проверка усечения)
    Requirements: 9.5, 9.6, 13.7
    """
    parser = UnifiedParser()
    
    parser.stats['start_time'] = datetime.now()
    parser.stats['end_time'] = datetime.now() + timedelta(seconds=10)
    
    # Создаем 15 топиков
    forum_topics = [
        {'topic_id': i, 'topic_title': f'Топик {i}', 'messages_count': 10 - i % 10}
        for i in range(1, 16)
    ]
    
    mock_db_stats = {
        'total_messages': 150,
        'total_channels': 1,
        'channel_stats': []
    }
    
    mock_source_type_stats = {
        'by_source_type': {
            'forum_chat': 150
        },
        'forum_topics': forum_topics
    }
    
    with patch.object(parser.db, 'get_stats', return_value=mock_db_stats), \
         patch.object(parser.db, 'get_stats_by_source_type', return_value=mock_source_type_stats), \
         patch('src.core.unified_parser.logger') as mock_logger:
        
        stats = parser.get_statistics()
        
        # Проверяем что все 15 топиков в статистике
        assert len(stats['forum_topics']) == 15
        
        # Проверяем логирование
        info_calls = [call[0][0] for call in mock_logger.info.call_args_list]
        
        # Проверяем что логируется информация о 15 топиках
        assert any('15 уникальных топиков' in msg for msg in info_calls)
        
        # Проверяем что есть сообщение об усечении
        assert any('и еще 5 топиков' in msg for msg in info_calls)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
