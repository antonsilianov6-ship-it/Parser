# -*- coding: utf-8 -*-
"""
Unit-тесты для TelegramSender
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from src.telegram.telegram_sender import TelegramSender


class TestTelegramSender:
    """Unit-тесты для TelegramSender"""
    
    @pytest.fixture
    def config(self):
        """Фикстура для конфигурации"""
        return {
            'API_ID': 12345,
            'API_HASH': 'test_hash'
        }
    
    @pytest.fixture
    def sender(self, config):
        """Фикстура для создания TelegramSender"""
        return TelegramSender(config)
    
    def test_init(self, sender, config):
        """Тест инициализации TelegramSender"""
        assert sender.config == config
        assert sender.max_retries == 3
        assert sender.retry_delay == 5
        assert sender.max_message_length == 4096
    
    def test_split_short_message(self, sender):
        """Тест разбиения короткого сообщения"""
        message = "Это короткое сообщение"
        parts = sender.split_long_message(message)
        
        assert len(parts) == 1
        assert parts[0] == message
    
    def test_split_long_message_by_sentences(self, sender):
        """Тест разбиения длинного сообщения по предложениям"""
        # Создаем сообщение из 200 предложений (чтобы гарантированно превысить 4096 символов)
        sentences = [f"Предложение номер {i} с дополнительным текстом для увеличения длины" for i in range(200)]
        message = '. '.join(sentences) + '.'
        
        parts = sender.split_long_message(message)
        
        # Проверяем, что сообщение разбито на несколько частей
        assert len(parts) > 1
        
        # Проверяем, что каждая часть не превышает лимит
        for part in parts:
            assert len(part) <= 4096
        
        # Проверяем, что конкатенация частей дает исходное сообщение (с учетом пробелов)
        reconstructed = ' '.join(parts)
        original_normalized = ' '.join(message.split())
        reconstructed_normalized = ' '.join(reconstructed.split())
        assert original_normalized == reconstructed_normalized
    
    def test_split_long_message_by_words(self, sender):
        """Тест разбиения длинного сообщения по словам (без точек)"""
        # Создаем сообщение из 1000 слов без точек
        words = [f"слово{i}" for i in range(1000)]
        message = ' '.join(words)
        
        parts = sender.split_long_message(message)
        
        # Проверяем, что сообщение разбито на несколько частей
        assert len(parts) > 1
        
        # Проверяем, что каждая часть не превышает лимит
        for part in parts:
            assert len(part) <= 4096
    
    def test_split_very_long_word(self, sender):
        """Тест разбиения очень длинного слова"""
        # Создаем слово длиннее лимита
        long_word = 'a' * 5000
        
        parts = sender.split_long_message(long_word)
        
        # Проверяем, что слово разбито на части
        assert len(parts) > 1
        
        # Проверяем, что каждая часть не превышает лимит
        for part in parts:
            assert len(part) <= 4096
        
        # Проверяем, что конкатенация частей дает исходное слово
        assert ''.join(parts) == long_word
    
    def test_split_message_with_custom_max_length(self, sender):
        """Тест разбиения сообщения с пользовательским лимитом"""
        message = 'a' * 500
        max_length = 100
        
        parts = sender.split_long_message(message, max_length)
        
        # Проверяем, что каждая часть не превышает пользовательский лимит
        for part in parts:
            assert len(part) <= max_length
    
    def test_format_message_with_header_negative(self, sender):
        """Тест форматирования негативной сводки"""
        summary = "Тестовая негативная сводка"
        formatted = sender._format_message_with_header(summary, 'negative')
        
        assert "📉" in formatted
        assert "Негативная аналитическая сводка" in formatted
        assert summary in formatted
    
    def test_format_message_with_header_positive(self, sender):
        """Тест форматирования позитивной сводки"""
        summary = "Тестовая позитивная сводка"
        formatted = sender._format_message_with_header(summary, 'positive')
        
        assert "📈" in formatted
        assert "Позитивная аналитическая сводка" in formatted
        assert summary in formatted
    
    def test_format_message_with_header_unknown(self, sender):
        """Тест форматирования сводки неизвестного типа"""
        summary = "Тестовая сводка"
        formatted = sender._format_message_with_header(summary, 'unknown')
        
        assert "📊" in formatted
        assert "Аналитическая сводка" in formatted
        assert summary in formatted
    
    @pytest.mark.asyncio
    async def test_send_message_with_retry_success(self, sender):
        """Тест успешной отправки сообщения с первой попытки"""
        chat_id = "test_chat"
        message = "Тестовое сообщение"
        
        # Мокаем ConnectionManager и клиент
        with patch.object(sender.connection_manager, 'connect', new_callable=AsyncMock) as mock_connect, \
             patch.object(sender.connection_manager, 'disconnect', new_callable=AsyncMock) as mock_disconnect, \
             patch.object(sender.connection_manager, 'get_client') as mock_get_client:
            
            # Настраиваем мок клиента
            mock_client = AsyncMock()
            mock_client.send_message = AsyncMock()
            mock_get_client.return_value = mock_client
            
            # Вызываем метод
            result = await sender._send_message_with_retry(chat_id, message, 1, 1)
            
            # Проверяем результат
            assert result is True
            mock_connect.assert_called_once()
            mock_client.send_message.assert_called_once_with(chat_id, message, parse_mode='markdown')
            mock_disconnect.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_send_message_with_retry_failure_then_success(self, sender):
        """Тест отправки сообщения с ошибкой на первой попытке и успехом на второй"""
        chat_id = "test_chat"
        message = "Тестовое сообщение"
        
        # Мокаем ConnectionManager и клиент
        with patch.object(sender.connection_manager, 'connect', new_callable=AsyncMock) as mock_connect, \
             patch.object(sender.connection_manager, 'disconnect', new_callable=AsyncMock) as mock_disconnect, \
             patch.object(sender.connection_manager, 'get_client') as mock_get_client:
            
            # Настраиваем мок клиента
            mock_client = AsyncMock()
            # Первая попытка - ошибка, вторая - успех
            mock_client.send_message = AsyncMock(side_effect=[Exception("Network error"), None])
            mock_get_client.return_value = mock_client
            
            # Вызываем метод
            result = await sender._send_message_with_retry(chat_id, message, 1, 1)
            
            # Проверяем результат
            assert result is True
            assert mock_connect.call_count == 2
            assert mock_client.send_message.call_count == 2
    
    @pytest.mark.asyncio
    async def test_send_message_with_retry_all_failures(self, sender):
        """Тест отправки сообщения с ошибками на всех попытках"""
        chat_id = "test_chat"
        message = "Тестовое сообщение"
        
        # Мокаем ConnectionManager и клиент
        with patch.object(sender.connection_manager, 'connect', new_callable=AsyncMock) as mock_connect, \
             patch.object(sender.connection_manager, 'disconnect', new_callable=AsyncMock) as mock_disconnect, \
             patch.object(sender.connection_manager, 'get_client') as mock_get_client:
            
            # Настраиваем мок клиента
            mock_client = AsyncMock()
            mock_client.send_message = AsyncMock(side_effect=Exception("Network error"))
            mock_get_client.return_value = mock_client
            
            # Вызываем метод
            result = await sender._send_message_with_retry(chat_id, message, 1, 1)
            
            # Проверяем результат
            assert result is False
            assert mock_connect.call_count == 3  # max_retries = 3
            assert mock_client.send_message.call_count == 3
    
    @pytest.mark.asyncio
    async def test_send_summary_short_message(self, sender):
        """Тест отправки короткой сводки"""
        chat_id = "test_chat"
        summary = "Короткая сводка"
        summary_type = "negative"
        
        # Мокаем _send_message_with_retry
        with patch.object(sender, '_send_message_with_retry', new_callable=AsyncMock) as mock_send:
            mock_send.return_value = True
            
            # Вызываем метод
            result = await sender.send_summary(chat_id, summary, summary_type)
            
            # Проверяем результат
            assert result is True
            mock_send.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_send_summary_long_message(self, sender):
        """Тест отправки длинной сводки (разбивается на части)"""
        chat_id = "test_chat"
        # Создаем длинную сводку
        summary = "Длинная сводка. " * 500  # Больше 4096 символов
        summary_type = "positive"
        
        # Мокаем _send_message_with_retry
        with patch.object(sender, '_send_message_with_retry', new_callable=AsyncMock) as mock_send:
            mock_send.return_value = True
            
            # Вызываем метод
            result = await sender.send_summary(chat_id, summary, summary_type)
            
            # Проверяем результат
            assert result is True
            # Должно быть несколько вызовов (сообщение разбито на части)
            assert mock_send.call_count > 1
    
    @pytest.mark.asyncio
    async def test_send_summaries(self, sender):
        """Тест отправки обеих сводок"""
        chat_id = "test_chat"
        negative_summary = "Негативная сводка"
        positive_summary = "Позитивная сводка"
        
        # Мокаем send_summary
        with patch.object(sender, 'send_summary', new_callable=AsyncMock) as mock_send:
            mock_send.return_value = True
            
            # Вызываем метод
            negative_sent, positive_sent = await sender.send_summaries(
                chat_id, negative_summary, positive_summary
            )
            
            # Проверяем результат
            assert negative_sent is True
            assert positive_sent is True
            assert mock_send.call_count == 2
    
    @pytest.mark.asyncio
    async def test_send_error_notification(self, sender):
        """Тест отправки уведомления об ошибке"""
        chat_id = "test_chat"
        error_message = "Произошла критическая ошибка"
        
        # Мокаем _send_message_with_retry
        with patch.object(sender, '_send_message_with_retry', new_callable=AsyncMock) as mock_send:
            mock_send.return_value = True
            
            # Вызываем метод
            result = await sender.send_error_notification(chat_id, error_message)
            
            # Проверяем результат
            assert result is True
            mock_send.assert_called_once()
            
            # Проверяем, что сообщение содержит эмодзи и текст ошибки
            call_args = mock_send.call_args[0]
            message_sent = call_args[1]
            assert "🚨" in message_sent
            assert error_message in message_sent
