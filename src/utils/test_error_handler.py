# -*- coding: utf-8 -*-
"""
Unit тесты для модуля ErrorHandler
**Validates: Requirements 15.3**
"""

import pytest
import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from telethon.errors import FloodWaitError, ChannelPrivateError, UsernameNotOccupiedError
from src.utils.error_handler import ErrorHandler, ErrorRecord


class TestFloodWaitHandling:
    """Тесты для обработки FloodWaitError с автоматическим retry"""
    
    @pytest.mark.asyncio
    async def test_handle_flood_wait_basic(self):
        """Тест базовой обработки FloodWaitError"""
        handler = ErrorHandler()
        # FloodWaitError принимает request как первый аргумент, seconds как атрибут
        error = FloodWaitError(request=None)
        error.seconds = 1
        
        start_time = asyncio.get_event_loop().time()
        await handler.handle_flood_wait(error, "test_operation")
        end_time = asyncio.get_event_loop().time()
        
        # Проверяем, что прошло время ожидания (1 секунда + случайная задержка 1-5 сек)
        elapsed = end_time - start_time
        assert elapsed >= 1.0, "Должна быть задержка минимум 1 секунда"
        assert elapsed < 7.0, "Задержка не должна превышать 6 секунд"
        
        # Проверяем, что ошибка залогирована
        assert len(handler.errors) == 1
        assert handler.errors[0].error_type == "FloodWaitError"
    
    @pytest.mark.asyncio
    async def test_handle_flood_wait_with_channel(self):
        """Тест обработки FloodWaitError с указанием канала"""
        handler = ErrorHandler()
        error = FloodWaitError(request=None)
        error.seconds = 1
        
        await handler.handle_flood_wait(error, "fetch_messages", channel="@testchannel")
        
        # Проверяем контекст ошибки
        assert len(handler.errors) == 1
        error_record = handler.errors[0]
        assert error_record.channel == "@testchannel"
        assert error_record.context['operation'] == "fetch_messages"
        assert error_record.context['wait_seconds'] == 1
    
    @pytest.mark.asyncio
    async def test_handle_flood_wait_logs_correctly(self):
        """Тест корректного логирования FloodWaitError"""
        handler = ErrorHandler()
        error = FloodWaitError(request=None)
        error.seconds = 2
        
        with patch('src.utils.error_handler.logger') as mock_logger:
            await handler.handle_flood_wait(error, "test_op", channel="@channel")
            
            # Проверяем, что были вызваны методы логирования
            assert mock_logger.warning.called
            assert mock_logger.info.called
            
            # Проверяем содержимое логов
            warning_call = mock_logger.warning.call_args[0][0]
            assert "FloodWait" in warning_call
            assert "@channel" in warning_call


class TestExponentialBackoff:
    """Тесты для exponential backoff при сетевых ошибках"""
    
    @pytest.mark.asyncio
    async def test_network_error_retry_success_on_first(self):
        """Тест успешного выполнения с первой попытки"""
        handler = ErrorHandler()
        mock_func = AsyncMock(return_value="success")
        
        result = await handler.handle_network_error(
            Exception("network error"),
            mock_func,
            "test_operation"
        )
        
        assert result == "success"
        assert mock_func.call_count == 1
    
    @pytest.mark.asyncio
    async def test_network_error_retry_success_on_second(self):
        """Тест успешного выполнения со второй попытки"""
        handler = ErrorHandler()
        mock_func = AsyncMock(side_effect=[Exception("error"), "success"])
        
        result = await handler.handle_network_error(
            Exception("network error"),
            mock_func,
            "test_operation"
        )
        
        assert result == "success"
        assert mock_func.call_count == 2
        # Проверяем, что были залогированы ошибки
        assert len(handler.errors) >= 1
    
    @pytest.mark.asyncio
    async def test_network_error_exponential_backoff_delays(self):
        """Тест exponential backoff задержек (2^1, 2^2, 2^3)"""
        handler = ErrorHandler()
        mock_func = AsyncMock(side_effect=Exception("error"))
        
        start_time = asyncio.get_event_loop().time()
        result = await handler.handle_network_error(
            Exception("network error"),
            mock_func,
            "test_operation",
            max_retries=3
        )
        end_time = asyncio.get_event_loop().time()
        
        # Проверяем, что результат None после всех попыток
        assert result is None
        
        # Проверяем общее время: 2^1 + 2^2 + 2^3 = 2 + 4 + 8 = 14 секунд
        elapsed = end_time - start_time
        assert elapsed >= 14.0, f"Ожидалось минимум 14 секунд, получено {elapsed}"
        assert elapsed < 16.0, f"Задержка не должна превышать 16 секунд, получено {elapsed}"
        
        # Проверяем количество попыток
        assert mock_func.call_count == 3
    
    @pytest.mark.asyncio
    async def test_network_error_max_retries_respected(self):
        """Тест соблюдения максимального количества попыток"""
        handler = ErrorHandler()
        mock_func = AsyncMock(side_effect=Exception("error"))
        
        result = await handler.handle_network_error(
            Exception("network error"),
            mock_func,
            "test_operation",
            max_retries=2
        )
        
        assert result is None
        assert mock_func.call_count == 2
    
    @pytest.mark.asyncio
    async def test_network_error_with_channel_context(self):
        """Тест обработки сетевой ошибки с контекстом канала"""
        handler = ErrorHandler()
        mock_func = AsyncMock(side_effect=Exception("timeout"))
        
        await handler.handle_network_error(
            Exception("timeout"),
            mock_func,
            "fetch_data",
            channel="@testchannel"
        )
        
        # Проверяем, что канал сохранен в контексте ошибок
        assert any(e.channel == "@testchannel" for e in handler.errors)


class TestErrorLogging:
    """Тесты для логирования ошибок с контекстом"""
    
    def test_log_error_basic(self):
        """Тест базового логирования ошибки"""
        handler = ErrorHandler()
        error = Exception("test error")
        context = {'operation': 'test_op', 'channel': '@test'}
        
        handler.log_error(error, context)
        
        assert len(handler.errors) == 1
        error_record = handler.errors[0]
        assert error_record.error_type == "Exception"
        assert error_record.error_message == "test error"
        assert error_record.context == context
        assert error_record.channel == '@test'
    
    def test_log_error_with_message_id(self):
        """Тест логирования ошибки с ID сообщения"""
        handler = ErrorHandler()
        error = ValueError("invalid value")
        context = {
            'operation': 'parse_message',
            'channel': '@channel',
            'message_id': 12345
        }
        
        handler.log_error(error, context)
        
        error_record = handler.errors[0]
        assert error_record.message_id == 12345
        assert error_record.channel == '@channel'
    
    def test_log_error_timestamp(self):
        """Тест корректности timestamp в записи об ошибке"""
        handler = ErrorHandler()
        error = Exception("test")
        
        before = datetime.now()
        handler.log_error(error, {'operation': 'test'})
        after = datetime.now()
        
        error_record = handler.errors[0]
        assert before <= error_record.timestamp <= after
    
    def test_log_error_calls_logger(self):
        """Тест вызова logger при логировании ошибки"""
        handler = ErrorHandler()
        error = Exception("test error")
        context = {'operation': 'test_op'}
        
        with patch('src.utils.error_handler.logger') as mock_logger:
            handler.log_error(error, context)
            
            mock_logger.error.assert_called_once()
            call_args = mock_logger.error.call_args[0][0]
            assert "Exception" in call_args
            assert "test error" in call_args


class TestChannelErrorHandling:
    """Тесты для обработки ошибок каналов"""
    
    def test_handle_channel_private_error(self):
        """Тест обработки ChannelPrivateError"""
        handler = ErrorHandler()
        error = ChannelPrivateError(None)
        
        with patch('src.utils.error_handler.logger') as mock_logger:
            handler.handle_channel_error(error, "@privatechannel")
            
            mock_logger.warning.assert_called_once()
            call_args = mock_logger.warning.call_args[0][0]
            assert "приватным" in call_args or "недоступным" in call_args
            assert "@privatechannel" in call_args
        
        # Проверяем запись ошибки
        assert len(handler.errors) == 1
        assert handler.errors[0].error_type == "ChannelPrivateError"
    
    def test_handle_username_not_occupied_error(self):
        """Тест обработки UsernameNotOccupiedError"""
        handler = ErrorHandler()
        error = UsernameNotOccupiedError(None)
        
        with patch('src.utils.error_handler.logger') as mock_logger:
            handler.handle_channel_error(error, "@nonexistent")
            
            mock_logger.warning.assert_called_once()
            call_args = mock_logger.warning.call_args[0][0]
            assert "не найден" in call_args
            assert "@nonexistent" in call_args
    
    def test_handle_generic_channel_error(self):
        """Тест обработки общей ошибки канала"""
        handler = ErrorHandler()
        error = Exception("unknown channel error")
        
        with patch('src.utils.error_handler.logger') as mock_logger:
            handler.handle_channel_error(error, "@channel")
            
            # Проверяем, что logger.error был вызван (может быть вызван дважды - в handle_channel_error и log_error)
            assert mock_logger.error.called
            # Проверяем первый вызов
            first_call_args = mock_logger.error.call_args_list[0][0][0]
            assert "Ошибка доступа" in first_call_args
            assert "@channel" in first_call_args


class TestErrorSummary:
    """Тесты для генерации сводки по ошибкам"""
    
    def test_get_error_summary_empty(self):
        """Тест сводки при отсутствии ошибок"""
        handler = ErrorHandler()
        summary = handler.get_error_summary()
        
        assert summary['total_errors'] == 0
        assert summary['flood_wait_errors'] == 0
        assert summary['channel_errors'] == 0
        assert summary['network_errors'] == 0
        assert summary['other_errors'] == 0
        assert summary['failed_channels'] == []
        assert summary['details'] == []
    
    def test_get_error_summary_with_flood_wait(self):
        """Тест сводки с FloodWaitError"""
        handler = ErrorHandler()
        error = FloodWaitError(request=None)
        error.seconds = 10
        handler.log_error(error, {'operation': 'test', 'channel': '@test'})
        
        summary = handler.get_error_summary()
        
        assert summary['total_errors'] == 1
        assert summary['flood_wait_errors'] == 1
        assert summary['channel_errors'] == 0
        assert '@test' in summary['failed_channels']
    
    def test_get_error_summary_with_channel_errors(self):
        """Тест сводки с ошибками каналов"""
        handler = ErrorHandler()
        
        handler.log_error(
            ChannelPrivateError(None),
            {'operation': 'access', 'channel': '@private'}
        )
        handler.log_error(
            UsernameNotOccupiedError(None),
            {'operation': 'access', 'channel': '@notfound'}
        )
        
        summary = handler.get_error_summary()
        
        assert summary['total_errors'] == 2
        assert summary['channel_errors'] == 2
        assert '@private' in summary['failed_channels']
        assert '@notfound' in summary['failed_channels']
    
    def test_get_error_summary_with_network_errors(self):
        """Тест сводки с сетевыми ошибками"""
        handler = ErrorHandler()
        
        handler.log_error(
            TimeoutError("timeout"),
            {'operation': 'fetch', 'channel': '@channel'}
        )
        handler.log_error(
            ConnectionError("network issue"),
            {'operation': 'connect', 'channel': '@channel2'}
        )
        
        summary = handler.get_error_summary()
        
        assert summary['total_errors'] == 2
        # TimeoutError содержит 'timeout' в имени, ConnectionError не содержит 'network' или 'timeout'
        # Поэтому только TimeoutError будет считаться network error
        assert summary['network_errors'] == 1
        assert summary['other_errors'] == 1
    
    def test_get_error_summary_mixed_errors(self):
        """Тест сводки со смешанными типами ошибок"""
        handler = ErrorHandler()
        
        flood_error = FloodWaitError(request=None)
        flood_error.seconds = 5
        handler.log_error(flood_error, {'operation': 'test', 'channel': '@ch1'})
        handler.log_error(ChannelPrivateError(None), {'operation': 'test', 'channel': '@ch2'})
        handler.log_error(TimeoutError("timeout"), {'operation': 'test', 'channel': '@ch3'})
        handler.log_error(ValueError("value error"), {'operation': 'test', 'channel': '@ch4'})
        
        summary = handler.get_error_summary()
        
        assert summary['total_errors'] == 4
        assert summary['flood_wait_errors'] == 1
        assert summary['channel_errors'] == 1
        assert summary['network_errors'] == 1
        assert summary['other_errors'] == 1
        assert len(summary['failed_channels']) == 4
    
    def test_get_error_summary_details_limit(self):
        """Тест ограничения деталей ошибок (последние 10)"""
        handler = ErrorHandler()
        
        # Создаем 15 ошибок
        for i in range(15):
            handler.log_error(
                Exception(f"error_{i}"),
                {'operation': 'test', 'channel': f'@ch{i}'}
            )
        
        summary = handler.get_error_summary()
        
        assert summary['total_errors'] == 15
        assert len(summary['details']) == 10  # Только последние 10
        
        # Проверяем, что это действительно последние 10
        assert summary['details'][0]['message'] == 'error_5'
        assert summary['details'][-1]['message'] == 'error_14'
    
    def test_get_error_summary_details_structure(self):
        """Тест структуры деталей ошибок"""
        handler = ErrorHandler()
        error = Exception("test error")
        context = {'operation': 'test_op', 'channel': '@test', 'extra': 'data'}
        
        handler.log_error(error, context)
        summary = handler.get_error_summary()
        
        detail = summary['details'][0]
        assert 'timestamp' in detail
        assert detail['type'] == 'Exception'
        assert detail['message'] == 'test error'
        assert detail['channel'] == '@test'
        assert detail['context'] == context


class TestErrorRecord:
    """Тесты для dataclass ErrorRecord"""
    
    def test_error_record_creation(self):
        """Тест создания ErrorRecord"""
        timestamp = datetime.now()
        record = ErrorRecord(
            timestamp=timestamp,
            error_type="TestError",
            error_message="test message",
            context={'key': 'value'},
            channel='@test',
            message_id=123
        )
        
        assert record.timestamp == timestamp
        assert record.error_type == "TestError"
        assert record.error_message == "test message"
        assert record.context == {'key': 'value'}
        assert record.channel == '@test'
        assert record.message_id == 123
    
    def test_error_record_optional_fields(self):
        """Тест создания ErrorRecord с опциональными полями"""
        record = ErrorRecord(
            timestamp=datetime.now(),
            error_type="TestError",
            error_message="test",
            context={}
        )
        
        assert record.channel is None
        assert record.message_id is None


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
