# -*- coding: utf-8 -*-
"""Unit-тесты для SummaryGenerator"""

import pytest
import json
import asyncio
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch, mock_open
from src.notebooklm.summary_generator import (
    SummaryGenerator, 
    PromptValidationError
)
from src.notebooklm.client import NotebookLMAPIError


class TestSummaryGeneratorInit:
    """Тесты инициализации SummaryGenerator"""
    
    def test_init_with_valid_config(self):
        """Тест успешной инициализации с валидным конфигом"""
        # Arrange
        mock_client = Mock()
        
        # Act
        generator = SummaryGenerator(mock_client, config_path="config/prompts.json")
        
        # Assert
        assert generator.client == mock_client
        assert generator.config_path == "config/prompts.json"
        assert 'negative' in generator.prompts
        assert 'positive' in generator.prompts
        assert 'timeout' in generator.defaults
        assert 'max_retries' in generator.defaults
    
    def test_init_with_missing_config_uses_defaults(self):
        """Тест инициализации с отсутствующим конфигом использует промпты по умолчанию"""
        # Arrange
        mock_client = Mock()
        
        # Act
        generator = SummaryGenerator(
            mock_client, 
            config_path="nonexistent_config.json"
        )
        
        # Assert
        assert generator.client == mock_client
        assert 'negative' in generator.prompts
        assert 'positive' in generator.prompts
        assert generator.prompts['negative']['template'] is not None
        assert generator.prompts['positive']['template'] is not None


class TestLoadPrompts:
    """Тесты загрузки промптов"""
    
    def test_load_prompts_success(self):
        """Тест успешной загрузки промптов из файла"""
        # Arrange
        mock_client = Mock()
        generator = SummaryGenerator(mock_client, config_path="config/prompts.json")
        
        # Act
        prompts, defaults = generator.load_prompts("config/prompts.json")
        
        # Assert
        assert 'negative' in prompts
        assert 'positive' in prompts
        assert 'timeout' in defaults
        assert 'max_retries' in defaults
    
    def test_load_prompts_file_not_found(self):
        """Тест ошибки при отсутствии файла конфигурации"""
        # Arrange
        mock_client = Mock()
        generator = SummaryGenerator(mock_client, config_path="config/prompts.json")
        
        # Act & Assert
        with pytest.raises(FileNotFoundError):
            generator.load_prompts("nonexistent.json")
    
    def test_load_prompts_invalid_json(self):
        """Тест ошибки при невалидном JSON"""
        # Arrange
        mock_client = Mock()
        generator = SummaryGenerator(mock_client, config_path="config/prompts.json")
        invalid_json = "{ invalid json }"
        
        # Act & Assert
        with patch('pathlib.Path.exists', return_value=True):
            with patch('builtins.open', mock_open(read_data=invalid_json)):
                with pytest.raises(PromptValidationError, match="Невалидный JSON"):
                    generator.load_prompts("test.json")
    
    def test_load_prompts_missing_prompts_field(self):
        """Тест ошибки при отсутствии поля 'prompts'"""
        # Arrange
        mock_client = Mock()
        generator = SummaryGenerator(mock_client, config_path="config/prompts.json")
        config = json.dumps({"defaults": {}})
        
        # Act & Assert
        with patch('pathlib.Path.exists', return_value=True):
            with patch('builtins.open', mock_open(read_data=config)):
                with pytest.raises(PromptValidationError, match="Отсутствует обязательное поле 'prompts'"):
                    generator.load_prompts("test.json")
    
    def test_load_prompts_missing_negative_prompt(self):
        """Тест ошибки при отсутствии негативного промпта"""
        # Arrange
        mock_client = Mock()
        generator = SummaryGenerator(mock_client, config_path="config/prompts.json")
        config = json.dumps({
            "prompts": {
                "positive": {
                    "template": "test",
                    "required_fields": ["template"],
                    "variables": []
                }
            }
        })
        
        # Act & Assert
        with patch('pathlib.Path.exists', return_value=True):
            with patch('builtins.open', mock_open(read_data=config)):
                with pytest.raises(PromptValidationError, match="Отсутствует обязательный промпт 'negative'"):
                    generator.load_prompts("test.json")
    
    def test_load_prompts_missing_positive_prompt(self):
        """Тест ошибки при отсутствии позитивного промпта"""
        # Arrange
        mock_client = Mock()
        generator = SummaryGenerator(mock_client, config_path="config/prompts.json")
        config = json.dumps({
            "prompts": {
                "negative": {
                    "template": "test",
                    "required_fields": ["template"],
                    "variables": []
                }
            }
        })
        
        # Act & Assert
        with patch('pathlib.Path.exists', return_value=True):
            with patch('builtins.open', mock_open(read_data=config)):
                with pytest.raises(PromptValidationError, match="Отсутствует обязательный промпт 'positive'"):
                    generator.load_prompts("test.json")
    
    def test_load_prompts_invalid_timeout_uses_default(self):
        """Тест использования значения по умолчанию при невалидном timeout"""
        # Arrange
        mock_client = Mock()
        generator = SummaryGenerator(mock_client, config_path="config/prompts.json")
        config = json.dumps({
            "prompts": {
                "negative": {
                    "template": "test",
                    "required_fields": ["template"],
                    "variables": []
                },
                "positive": {
                    "template": "test",
                    "required_fields": ["template"],
                    "variables": []
                }
            },
            "defaults": {
                "timeout": -10,
                "max_retries": 3
            }
        })
        
        # Act
        with patch('pathlib.Path.exists', return_value=True):
            with patch('builtins.open', mock_open(read_data=config)):
                prompts, defaults = generator.load_prompts("test.json")
        
        # Assert
        assert defaults['timeout'] == 120  # Значение по умолчанию


class TestValidatePrompt:
    """Тесты валидации промптов"""
    
    def test_validate_prompt_valid(self):
        """Тест валидации корректного промпта"""
        # Arrange
        mock_client = Mock()
        generator = SummaryGenerator(mock_client, config_path="config/prompts.json")
        prompt = {
            'template': 'Test template',
            'required_fields': ['template'],
            'variables': []
        }
        
        # Act
        result = generator.validate_prompt(prompt)
        
        # Assert
        assert result is True
    
    def test_validate_prompt_missing_template(self):
        """Тест валидации промпта без поля template"""
        # Arrange
        mock_client = Mock()
        generator = SummaryGenerator(mock_client, config_path="config/prompts.json")
        prompt = {
            'required_fields': ['template'],
            'variables': []
        }
        
        # Act
        result = generator.validate_prompt(prompt)
        
        # Assert
        assert result is False
    
    def test_validate_prompt_empty_template(self):
        """Тест валидации промпта с пустым template"""
        # Arrange
        mock_client = Mock()
        generator = SummaryGenerator(mock_client, config_path="config/prompts.json")
        prompt = {
            'template': '',
            'required_fields': ['template'],
            'variables': []
        }
        
        # Act
        result = generator.validate_prompt(prompt)
        
        # Assert
        assert result is False


class TestGenerateNegativeSummary:
    """Тесты генерации негативной сводки"""
    
    @pytest.mark.asyncio
    async def test_generate_negative_summary_success(self):
        """Тест успешной генерации негативной сводки"""
        # Arrange
        mock_client = Mock()
        mock_client.query_notebook = AsyncMock(
            return_value="Негативная сводка: проблемы с качеством"
        )
        generator = SummaryGenerator(mock_client, config_path="config/prompts.json")
        notebook_id = "test_notebook_123"
        
        # Act
        result = await generator.generate_negative_summary(notebook_id)
        
        # Assert
        assert result == "Негативная сводка: проблемы с качеством"
        mock_client.query_notebook.assert_called_once()
        call_args = mock_client.query_notebook.call_args
        assert call_args[1]['notebook_id'] == notebook_id
        assert 'prompt' in call_args[1]
    
    @pytest.mark.asyncio
    async def test_generate_negative_summary_with_custom_timeout(self):
        """Тест генерации негативной сводки с кастомным таймаутом"""
        # Arrange
        mock_client = Mock()
        mock_client.query_notebook = AsyncMock(return_value="Test summary")
        generator = SummaryGenerator(mock_client, config_path="config/prompts.json")
        notebook_id = "test_notebook_123"
        custom_timeout = 60
        
        # Act
        result = await generator.generate_negative_summary(
            notebook_id, 
            timeout=custom_timeout
        )
        
        # Assert
        call_args = mock_client.query_notebook.call_args
        assert call_args[1]['timeout'] == custom_timeout
    
    @pytest.mark.asyncio
    async def test_generate_negative_summary_timeout_error(self):
        """Тест обработки таймаута при генерации негативной сводки"""
        # Arrange
        mock_client = Mock()
        mock_client.query_notebook = AsyncMock(side_effect=TimeoutError("Timeout"))
        generator = SummaryGenerator(mock_client, config_path="config/prompts.json")
        notebook_id = "test_notebook_123"
        
        # Act & Assert
        with pytest.raises(TimeoutError):
            await generator.generate_negative_summary(notebook_id)
    
    @pytest.mark.asyncio
    async def test_generate_negative_summary_api_error(self):
        """Тест обработки ошибки API при генерации негативной сводки"""
        # Arrange
        mock_client = Mock()
        mock_client.query_notebook = AsyncMock(
            side_effect=NotebookLMAPIError("API Error")
        )
        generator = SummaryGenerator(mock_client, config_path="config/prompts.json")
        notebook_id = "test_notebook_123"
        
        # Act & Assert
        with pytest.raises(NotebookLMAPIError):
            await generator.generate_negative_summary(notebook_id)


class TestGeneratePositiveSummary:
    """Тесты генерации позитивной сводки"""
    
    @pytest.mark.asyncio
    async def test_generate_positive_summary_success(self):
        """Тест успешной генерации позитивной сводки"""
        # Arrange
        mock_client = Mock()
        mock_client.query_notebook = AsyncMock(
            return_value="Позитивная сводка: отличное качество"
        )
        generator = SummaryGenerator(mock_client, config_path="config/prompts.json")
        notebook_id = "test_notebook_456"
        
        # Act
        result = await generator.generate_positive_summary(notebook_id)
        
        # Assert
        assert result == "Позитивная сводка: отличное качество"
        mock_client.query_notebook.assert_called_once()
        call_args = mock_client.query_notebook.call_args
        assert call_args[1]['notebook_id'] == notebook_id
    
    @pytest.mark.asyncio
    async def test_generate_positive_summary_timeout_error(self):
        """Тест обработки таймаута при генерации позитивной сводки"""
        # Arrange
        mock_client = Mock()
        mock_client.query_notebook = AsyncMock(side_effect=TimeoutError("Timeout"))
        generator = SummaryGenerator(mock_client, config_path="config/prompts.json")
        notebook_id = "test_notebook_456"
        
        # Act & Assert
        with pytest.raises(TimeoutError):
            await generator.generate_positive_summary(notebook_id)


class TestGenerateSummariesParallel:
    """Тесты параллельной генерации сводок"""
    
    @pytest.mark.asyncio
    async def test_generate_summaries_parallel_success(self):
        """Тест успешной параллельной генерации обеих сводок"""
        # Arrange
        mock_client = Mock()
        
        async def mock_query(notebook_id, prompt, timeout):
            if "негатив" in prompt.lower() or "жалоб" in prompt.lower():
                return "Негативная сводка"
            else:
                return "Позитивная сводка"
        
        mock_client.query_notebook = AsyncMock(side_effect=mock_query)
        generator = SummaryGenerator(mock_client, config_path="config/prompts.json")
        notebook_id = "test_notebook_789"
        
        # Act
        negative, positive = await generator.generate_summaries_parallel(notebook_id)
        
        # Assert
        assert negative == "Негативная сводка"
        assert positive == "Позитивная сводка"
        assert mock_client.query_notebook.call_count == 2
    
    @pytest.mark.asyncio
    async def test_generate_summaries_parallel_negative_error(self):
        """Тест обработки ошибки в негативной сводке при параллельной генерации"""
        # Arrange
        mock_client = Mock()
        
        async def mock_query(notebook_id, prompt, timeout):
            if "негатив" in prompt.lower() or "жалоб" in prompt.lower():
                raise NotebookLMAPIError("API Error")
            else:
                return "Позитивная сводка"
        
        mock_client.query_notebook = AsyncMock(side_effect=mock_query)
        generator = SummaryGenerator(mock_client, config_path="config/prompts.json")
        notebook_id = "test_notebook_789"
        
        # Act & Assert
        with pytest.raises(NotebookLMAPIError):
            await generator.generate_summaries_parallel(notebook_id)
    
    @pytest.mark.asyncio
    async def test_generate_summaries_parallel_positive_error(self):
        """Тест обработки ошибки в позитивной сводке при параллельной генерации"""
        # Arrange
        mock_client = Mock()
        
        async def mock_query(notebook_id, prompt, timeout):
            if "негатив" in prompt.lower() or "жалоб" in prompt.lower():
                return "Негативная сводка"
            else:
                raise TimeoutError("Timeout")
        
        mock_client.query_notebook = AsyncMock(side_effect=mock_query)
        generator = SummaryGenerator(mock_client, config_path="config/prompts.json")
        notebook_id = "test_notebook_789"
        
        # Act & Assert
        with pytest.raises(TimeoutError):
            await generator.generate_summaries_parallel(notebook_id)


class TestFormatSummaryForTelegram:
    """Тесты форматирования сводок для Telegram"""
    
    def test_format_negative_summary(self):
        """Тест форматирования негативной сводки"""
        # Arrange
        mock_client = Mock()
        generator = SummaryGenerator(mock_client, config_path="config/prompts.json")
        summary = "Проблемы с качеством продукта"
        
        # Act
        result = generator.format_summary_for_telegram(summary, 'negative')
        
        # Assert
        assert 'НЕГАТИВНАЯ СВОДКА' in result
        assert summary in result
        assert '⚠️' in result
        assert '=' in result
    
    def test_format_positive_summary(self):
        """Тест форматирования позитивной сводки"""
        # Arrange
        mock_client = Mock()
        generator = SummaryGenerator(mock_client, config_path="config/prompts.json")
        summary = "Отличное качество обслуживания"
        
        # Act
        result = generator.format_summary_for_telegram(summary, 'positive')
        
        # Assert
        assert 'ПОЗИТИВНАЯ СВОДКА' in result
        assert summary in result
        assert '✅' in result
        assert '=' in result
    
    def test_format_unknown_type_summary(self):
        """Тест форматирования сводки неизвестного типа"""
        # Arrange
        mock_client = Mock()
        generator = SummaryGenerator(mock_client, config_path="config/prompts.json")
        summary = "Общая аналитическая сводка"
        
        # Act
        result = generator.format_summary_for_telegram(summary, 'unknown')
        
        # Assert
        assert 'АНАЛИТИЧЕСКАЯ СВОДКА' in result
        assert summary in result
        assert '📊' in result
    
    def test_format_summary_case_insensitive(self):
        """Тест форматирования с разным регистром типа"""
        # Arrange
        mock_client = Mock()
        generator = SummaryGenerator(mock_client, config_path="config/prompts.json")
        summary = "Test summary"
        
        # Act
        result_lower = generator.format_summary_for_telegram(summary, 'negative')
        result_upper = generator.format_summary_for_telegram(summary, 'NEGATIVE')
        result_mixed = generator.format_summary_for_telegram(summary, 'Negative')
        
        # Assert
        assert 'НЕГАТИВНАЯ СВОДКА' in result_lower
        assert 'НЕГАТИВНАЯ СВОДКА' in result_upper
        assert 'НЕГАТИВНАЯ СВОДКА' in result_mixed
