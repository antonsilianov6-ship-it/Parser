# -*- coding: utf-8 -*-
"""Unit-тесты для NotebookLM Client"""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from src.notebooklm.client import (
    NotebookLMClient,
    NotebookLMAPIError,
    AuthenticationError
)


class TestNotebookLMClientInitialization:
    """Тесты инициализации клиента"""
    
    def test_successful_initialization(self):
        """Тест успешной инициализации с валидными учетными данными"""
        credentials = {
            'email': 'test@example.com',
            'password': 'test_password'
        }
        
        with patch('src.notebooklm.client.NLMClient') as mock_nlm:
            mock_nlm.return_value = Mock()
            
            client = NotebookLMClient(credentials)
            
            assert client.is_authenticated() is True
            mock_nlm.assert_called_once_with(
                email='test@example.com',
                password='test_password'
            )
    
    def test_initialization_missing_email(self):
        """Тест ошибки при отсутствии email"""
        credentials = {
            'password': 'test_password'
        }
        
        with pytest.raises(AuthenticationError) as exc_info:
            NotebookLMClient(credentials)
        
        assert "Отсутствуют обязательные учетные данные" in str(exc_info.value)
    
    def test_initialization_missing_password(self):
        """Тест ошибки при отсутствии password"""
        credentials = {
            'email': 'test@example.com'
        }
        
        with pytest.raises(AuthenticationError) as exc_info:
            NotebookLMClient(credentials)
        
        assert "Отсутствуют обязательные учетные данные" in str(exc_info.value)
    
    def test_initialization_empty_credentials(self):
        """Тест ошибки при пустых учетных данных"""
        credentials = {
            'email': '',
            'password': ''
        }
        
        with pytest.raises(AuthenticationError) as exc_info:
            NotebookLMClient(credentials)
        
        assert "Отсутствуют обязательные учетные данные" in str(exc_info.value)
    
    def test_initialization_api_error(self):
        """Тест ошибки при проблемах с API во время инициализации"""
        credentials = {
            'email': 'test@example.com',
            'password': 'test_password'
        }
        
        with patch('src.notebooklm.client.NLMClient') as mock_nlm:
            mock_nlm.side_effect = Exception("API connection failed")
            
            with pytest.raises(AuthenticationError) as exc_info:
                NotebookLMClient(credentials)
            
            assert "Ошибка инициализации NotebookLM клиента" in str(exc_info.value)


class TestNotebookLMClientAuthentication:
    """Тесты проверки аутентификации"""
    
    def test_is_authenticated_true(self):
        """Тест is_authenticated возвращает True для аутентифицированного клиента"""
        credentials = {
            'email': 'test@example.com',
            'password': 'test_password'
        }
        
        with patch('src.notebooklm.client.NLMClient') as mock_nlm:
            mock_nlm.return_value = Mock()
            client = NotebookLMClient(credentials)
            
            assert client.is_authenticated() is True
    
    def test_is_authenticated_false_after_failed_init(self):
        """Тест is_authenticated возвращает False после неудачной инициализации"""
        # Создаем клиент с невалидными данными
        credentials = {'email': '', 'password': ''}
        
        try:
            NotebookLMClient(credentials)
        except AuthenticationError:
            pass  # Ожидаемая ошибка


class TestNotebookLMClientCreateNotebook:
    """Тесты создания ноутбука"""
    
    @pytest.mark.asyncio
    async def test_create_notebook_success(self):
        """Тест успешного создания ноутбука"""
        credentials = {
            'email': 'test@example.com',
            'password': 'test_password'
        }
        
        mock_notebook = Mock()
        mock_notebook.id = 'notebook_123'
        
        with patch('src.notebooklm.client.NLMClient') as mock_nlm:
            mock_client = Mock()
            mock_client.create_notebook = Mock(return_value=mock_notebook)
            mock_nlm.return_value = mock_client
            
            client = NotebookLMClient(credentials)
            
            with patch('asyncio.to_thread', new_callable=AsyncMock) as mock_to_thread:
                mock_to_thread.return_value = mock_notebook
                
                notebook_id = await client.create_notebook("Test Notebook")
                
                assert notebook_id == 'notebook_123'
                mock_to_thread.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_create_notebook_not_authenticated(self):
        """Тест ошибки создания ноутбука без аутентификации"""
        credentials = {
            'email': 'test@example.com',
            'password': 'test_password'
        }
        
        with patch('src.notebooklm.client.NLMClient') as mock_nlm:
            mock_nlm.return_value = Mock()
            client = NotebookLMClient(credentials)
            client._client = None  # Симулируем отсутствие аутентификации
            
            with pytest.raises(AuthenticationError) as exc_info:
                await client.create_notebook("Test Notebook")
            
            assert "Клиент не аутентифицирован" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_create_notebook_retry_logic(self):
        """Тест retry-логики при создании ноутбука"""
        credentials = {
            'email': 'test@example.com',
            'password': 'test_password'
        }
        
        mock_notebook = Mock()
        mock_notebook.id = 'notebook_123'
        
        with patch('src.notebooklm.client.NLMClient') as mock_nlm:
            mock_client = Mock()
            mock_nlm.return_value = mock_client
            
            client = NotebookLMClient(credentials)
            
            # Первые 2 попытки - ошибка, третья - успех
            call_count = 0
            async def mock_to_thread_func(*args, **kwargs):
                nonlocal call_count
                call_count += 1
                if call_count < 3:
                    raise Exception("Network error")
                return mock_notebook
            
            with patch('asyncio.to_thread', side_effect=mock_to_thread_func):
                with patch('asyncio.sleep', new_callable=AsyncMock):
                    notebook_id = await client.create_notebook("Test Notebook")
                    
                    assert notebook_id == 'notebook_123'
                    assert call_count == 3
    
    @pytest.mark.asyncio
    async def test_create_notebook_max_retries_exceeded(self):
        """Тест исчерпания попыток при создании ноутбука"""
        credentials = {
            'email': 'test@example.com',
            'password': 'test_password'
        }
        
        with patch('src.notebooklm.client.NLMClient') as mock_nlm:
            mock_client = Mock()
            mock_nlm.return_value = mock_client
            
            client = NotebookLMClient(credentials)
            
            with patch('asyncio.to_thread', side_effect=Exception("Persistent error")):
                with patch('asyncio.sleep', new_callable=AsyncMock):
                    with pytest.raises(NotebookLMAPIError) as exc_info:
                        await client.create_notebook("Test Notebook")
                    
                    assert "Ошибка создания ноутбука" in str(exc_info.value)


class TestNotebookLMClientDeleteNotebook:
    """Тесты удаления ноутбука"""
    
    @pytest.mark.asyncio
    async def test_delete_notebook_success(self):
        """Тест успешного удаления ноутбука"""
        credentials = {
            'email': 'test@example.com',
            'password': 'test_password'
        }
        
        with patch('src.notebooklm.client.NLMClient') as mock_nlm:
            mock_client = Mock()
            mock_client.delete_notebook = Mock()
            mock_nlm.return_value = mock_client
            
            client = NotebookLMClient(credentials)
            
            with patch('asyncio.to_thread', new_callable=AsyncMock) as mock_to_thread:
                mock_to_thread.return_value = None
                
                result = await client.delete_notebook('notebook_123')
                
                assert result is True
                mock_to_thread.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_delete_notebook_not_authenticated(self):
        """Тест удаления ноутбука без аутентификации"""
        credentials = {
            'email': 'test@example.com',
            'password': 'test_password'
        }
        
        with patch('src.notebooklm.client.NLMClient') as mock_nlm:
            mock_nlm.return_value = Mock()
            client = NotebookLMClient(credentials)
            client._client = None  # Симулируем отсутствие аутентификации
            
            result = await client.delete_notebook('notebook_123')
            
            assert result is False
    
    @pytest.mark.asyncio
    async def test_delete_notebook_retry_and_fail(self):
        """Тест retry-логики с финальной неудачей при удалении ноутбука"""
        credentials = {
            'email': 'test@example.com',
            'password': 'test_password'
        }
        
        with patch('src.notebooklm.client.NLMClient') as mock_nlm:
            mock_client = Mock()
            mock_nlm.return_value = mock_client
            
            client = NotebookLMClient(credentials)
            
            with patch('asyncio.to_thread', side_effect=Exception("Persistent error")):
                with patch('asyncio.sleep', new_callable=AsyncMock):
                    result = await client.delete_notebook('notebook_123')
                    
                    # Должен вернуть False после исчерпания попыток
                    assert result is False


class TestNotebookLMClientAddSource:
    """Тесты добавления источника данных"""
    
    @pytest.mark.asyncio
    async def test_add_source_success(self):
        """Тест успешного добавления источника"""
        credentials = {
            'email': 'test@example.com',
            'password': 'test_password'
        }
        
        mock_source = Mock()
        mock_source.id = 'source_456'
        
        with patch('src.notebooklm.client.NLMClient') as mock_nlm:
            mock_client = Mock()
            mock_client.upload_source = Mock(return_value=mock_source)
            mock_nlm.return_value = mock_client
            
            client = NotebookLMClient(credentials)
            
            with patch('os.path.exists', return_value=True):
                with patch('asyncio.to_thread', new_callable=AsyncMock) as mock_to_thread:
                    mock_to_thread.return_value = mock_source
                    
                    source_id = await client.add_source(
                        'notebook_123',
                        'test.csv',
                        'csv'
                    )
                    
                    assert source_id == 'source_456'
                    mock_to_thread.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_add_source_file_not_found(self):
        """Тест ошибки при отсутствии файла"""
        credentials = {
            'email': 'test@example.com',
            'password': 'test_password'
        }
        
        with patch('src.notebooklm.client.NLMClient') as mock_nlm:
            mock_nlm.return_value = Mock()
            client = NotebookLMClient(credentials)
            
            with patch('os.path.exists', return_value=False):
                with pytest.raises(FileNotFoundError) as exc_info:
                    await client.add_source(
                        'notebook_123',
                        'nonexistent.csv',
                        'csv'
                    )
                
                assert "Файл не найден" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_add_source_not_authenticated(self):
        """Тест ошибки добавления источника без аутентификации"""
        credentials = {
            'email': 'test@example.com',
            'password': 'test_password'
        }
        
        with patch('src.notebooklm.client.NLMClient') as mock_nlm:
            mock_nlm.return_value = Mock()
            client = NotebookLMClient(credentials)
            client._client = None
            
            with pytest.raises(AuthenticationError) as exc_info:
                await client.add_source('notebook_123', 'test.csv', 'csv')
            
            assert "Клиент не аутентифицирован" in str(exc_info.value)


class TestNotebookLMClientQueryNotebook:
    """Тесты запросов к ноутбуку"""
    
    @pytest.mark.asyncio
    async def test_query_notebook_success(self):
        """Тест успешного запроса к ноутбуку"""
        credentials = {
            'email': 'test@example.com',
            'password': 'test_password'
        }
        
        mock_response = Mock()
        mock_response.text = "Test response from NotebookLM"
        
        with patch('src.notebooklm.client.NLMClient') as mock_nlm:
            mock_client = Mock()
            mock_client.query_notebook = Mock(return_value=mock_response)
            mock_nlm.return_value = mock_client
            
            client = NotebookLMClient(credentials)
            
            with patch('asyncio.to_thread', new_callable=AsyncMock) as mock_to_thread:
                mock_to_thread.return_value = mock_response
                
                response = await client.query_notebook(
                    'notebook_123',
                    'Test prompt',
                    timeout=120
                )
                
                assert response == "Test response from NotebookLM"
                mock_to_thread.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_query_notebook_timeout(self):
        """Тест таймаута при запросе к ноутбуку"""
        credentials = {
            'email': 'test@example.com',
            'password': 'test_password'
        }
        
        with patch('src.notebooklm.client.NLMClient') as mock_nlm:
            mock_client = Mock()
            mock_nlm.return_value = mock_client
            
            client = NotebookLMClient(credentials)
            
            # Симулируем таймаут через asyncio.TimeoutError
            with patch('asyncio.wait_for', side_effect=asyncio.TimeoutError):
                with patch('asyncio.sleep', new_callable=AsyncMock):
                    with pytest.raises(TimeoutError) as exc_info:
                        await client.query_notebook(
                            'notebook_123',
                            'Test prompt',
                            timeout=0.1
                        )
                    
                    assert "Таймаут запроса" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_query_notebook_not_authenticated(self):
        """Тест ошибки запроса без аутентификации"""
        credentials = {
            'email': 'test@example.com',
            'password': 'test_password'
        }
        
        with patch('src.notebooklm.client.NLMClient') as mock_nlm:
            mock_nlm.return_value = Mock()
            client = NotebookLMClient(credentials)
            client._client = None
            
            with pytest.raises(AuthenticationError) as exc_info:
                await client.query_notebook('notebook_123', 'Test prompt')
            
            assert "Клиент не аутентифицирован" in str(exc_info.value)
