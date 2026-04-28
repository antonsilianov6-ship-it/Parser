# -*- coding: utf-8 -*-
"""
Integration-тесты для AutomationOrchestrator
"""

import pytest
import asyncio
import json
import os
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from pathlib import Path

from src.automation.orchestrator import AutomationOrchestrator, AutomationError
from src.automation.models import AutomationStats
from src.notebooklm.client import AuthenticationError, NotebookLMAPIError


@pytest.fixture
def temp_config_file(tmp_path):
    """Создает временный файл конфигурации для тестов"""
    config = {
        "NOTEBOOKLM": {
            "email": "test@example.com",
            "password": "test_password",
            "prompts_config": "config/prompts.json"
        },
        "AUTOMATION": {
            "target_chat_id": "test_chat_123",
            "schedule_time": "09:00",
            "timeout": 120,
            "max_retries": 3,
            "export_format": "csv"
        },
        "TELEGRAM": {
            "API_ID": "12345",
            "API_HASH": "test_hash"
        },
        "DATABASE": {
            "DB_PATH": str(tmp_path / "test.db")
        }
    }
    
    config_file = tmp_path / "test_config.json"
    with open(config_file, 'w', encoding='utf-8') as f:
        json.dump(config, f)
    
    return str(config_file)


@pytest.fixture
def mock_components():
    """Создает моки для всех компонентов"""
    with patch('src.automation.orchestrator.NotebookLMClient') as mock_client, \
         patch('src.automation.orchestrator.FileManager') as mock_file_manager, \
         patch('src.automation.orchestrator.SummaryGenerator') as mock_summary_gen, \
         patch('src.automation.orchestrator.TelegramSender') as mock_telegram, \
         patch('src.automation.orchestrator.UnifiedParser') as mock_parser, \
         patch('src.automation.orchestrator.ExcelExporter') as mock_exporter, \
         patch('src.automation.orchestrator.Database') as mock_db:
        
        # Настройка моков
        mock_client_instance = Mock()
        mock_client_instance.is_authenticated.return_value = True
        mock_client.return_value = mock_client_instance
        
        mock_file_manager_instance = Mock()
        mock_file_manager_instance.create_notebook_with_source = AsyncMock(
            return_value=("notebook_123", "source_456")
        )
        mock_file_manager_instance.cleanup_notebook = AsyncMock()
        mock_file_manager_instance.cleanup_temp_files = Mock()
        mock_file_manager.return_value = mock_file_manager_instance
        
        mock_summary_gen_instance = Mock()
        mock_summary_gen_instance.generate_summaries_parallel = AsyncMock(
            return_value=("Негативная сводка", "Позитивная сводка")
        )
        mock_summary_gen_instance.format_summary_for_telegram = Mock(
            side_effect=lambda text, type: f"[{type}] {text}"
        )
        mock_summary_gen.return_value = mock_summary_gen_instance
        
        mock_telegram_instance = Mock()
        mock_telegram_instance.send_summaries = AsyncMock(return_value=(True, True))
        mock_telegram_instance.send_error_notification = AsyncMock(return_value=True)
        mock_telegram.return_value = mock_telegram_instance
        
        mock_parser_instance = Mock()
        mock_parser.return_value = mock_parser_instance
        
        mock_exporter_instance = Mock()
        mock_exporter_instance.export_to_excel = Mock(
            return_value="/tmp/export_test.xlsx"
        )
        mock_exporter.return_value = mock_exporter_instance
        
        mock_db_instance = Mock()
        # Создаем сообщение с датой, которая будет в диапазоне тестов
        test_message_date = datetime.now() - timedelta(hours=12)
        mock_db_instance.get_messages = Mock(return_value=[
            Mock(
                date=test_message_date,
                channel="test_channel",
                message_id=1,
                text="Test message"
            )
        ])
        mock_db.return_value = mock_db_instance
        
        yield {
            'client': mock_client_instance,
            'file_manager': mock_file_manager_instance,
            'summary_generator': mock_summary_gen_instance,
            'telegram_sender': mock_telegram_instance,
            'parser': mock_parser_instance,
            'exporter': mock_exporter_instance,
            'database': mock_db_instance
        }


class TestAutomationOrchestratorInitialization:
    """Тесты инициализации AutomationOrchestrator"""
    
    def test_initialization_success(self, temp_config_file, mock_components):
        """Тест успешной инициализации оркестратора"""
        orchestrator = AutomationOrchestrator(config_path=temp_config_file)
        
        assert orchestrator.config is not None
        assert orchestrator.config['NOTEBOOKLM']['email'] == "test@example.com"
        assert orchestrator.config['AUTOMATION']['target_chat_id'] == "test_chat_123"
    
    def test_initialization_missing_config_file(self):
        """Тест инициализации с отсутствующим файлом конфигурации"""
        with pytest.raises(AutomationError, match="Файл конфигурации не найден"):
            AutomationOrchestrator(config_path="/nonexistent/config.json")
    
    def test_initialization_missing_notebooklm_credentials(self, tmp_path):
        """Тест инициализации без учетных данных NotebookLM"""
        config = {
            "NOTEBOOKLM": {},
            "AUTOMATION": {"target_chat_id": "test"}
        }
        config_file = tmp_path / "invalid_config.json"
        with open(config_file, 'w') as f:
            json.dump(config, f)
        
        with pytest.raises(AutomationError, match="Отсутствуют учетные данные NotebookLM"):
            AutomationOrchestrator(config_path=str(config_file))
    
    def test_initialization_with_default_automation_config(self, tmp_path, mock_components):
        """Тест инициализации с отсутствующей секцией AUTOMATION"""
        config = {
            "NOTEBOOKLM": {
                "email": "test@example.com",
                "password": "test_password"
            },
            "TELEGRAM": {"API_ID": "12345", "API_HASH": "test"},
            "DATABASE": {"DB_PATH": str(tmp_path / "test.db")}
        }
        config_file = tmp_path / "config.json"
        with open(config_file, 'w') as f:
            json.dump(config, f)
        
        orchestrator = AutomationOrchestrator(config_path=str(config_file))
        
        # Проверяем, что используются значения по умолчанию
        assert orchestrator.config['AUTOMATION']['timeout'] == 120
        assert orchestrator.config['AUTOMATION']['max_retries'] == 3


class TestAutomationOrchestratorExportData:
    """Тесты метода export_data"""
    
    @pytest.mark.asyncio
    async def test_export_data_success(self, temp_config_file, mock_components):
        """Тест успешного экспорта данных"""
        orchestrator = AutomationOrchestrator(config_path=temp_config_file)
        
        start_date = datetime.now() - timedelta(days=2)
        end_date = datetime.now()
        
        file_path = await orchestrator.export_data((start_date, end_date))
        
        assert file_path == "/tmp/export_test.xlsx"
        mock_components['database'].get_messages.assert_called_once()
        mock_components['exporter'].export_to_excel.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_export_data_no_messages(self, temp_config_file, mock_components):
        """Тест экспорта при отсутствии сообщений"""
        orchestrator = AutomationOrchestrator(config_path=temp_config_file)
        
        # Мокируем пустой результат из БД
        mock_components['database'].get_messages.return_value = []
        
        start_date = datetime.now() - timedelta(days=2)
        end_date = datetime.now()
        
        with pytest.raises(AutomationError, match="Нет сообщений для экспорта"):
            await orchestrator.export_data((start_date, end_date))


class TestAutomationOrchestratorProcessSummaries:
    """Тесты метода process_summaries"""
    
    @pytest.mark.asyncio
    async def test_process_summaries_success(self, temp_config_file, mock_components):
        """Тест успешной обработки сводок"""
        orchestrator = AutomationOrchestrator(config_path=temp_config_file)
        
        negative, positive = await orchestrator.process_summaries("/tmp/test.csv")
        
        assert negative == "Негативная сводка"
        assert positive == "Позитивная сводка"
        mock_components['file_manager'].create_notebook_with_source.assert_called_once()
        mock_components['summary_generator'].generate_summaries_parallel.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_process_summaries_cleanup_on_error(self, temp_config_file, mock_components):
        """Тест очистки ноутбука при ошибке генерации сводок"""
        orchestrator = AutomationOrchestrator(config_path=temp_config_file)
        
        # Мокируем ошибку при генерации сводок
        mock_components['summary_generator'].generate_summaries_parallel.side_effect = \
            NotebookLMAPIError("API Error")
        
        with pytest.raises(AutomationError, match="Ошибка обработки сводок"):
            await orchestrator.process_summaries("/tmp/test.csv")
        
        # Проверяем, что cleanup был вызван
        mock_components['file_manager'].cleanup_notebook.assert_called_once()


class TestAutomationOrchestratorSendResults:
    """Тесты метода send_results"""
    
    @pytest.mark.asyncio
    async def test_send_results_success(self, temp_config_file, mock_components):
        """Тест успешной отправки результатов"""
        orchestrator = AutomationOrchestrator(config_path=temp_config_file)
        
        result = await orchestrator.send_results("Негативная", "Позитивная")
        
        assert result is True
        mock_components['telegram_sender'].send_summaries.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_send_results_partial_failure(self, temp_config_file, mock_components):
        """Тест частичной отправки (только одна сводка)"""
        orchestrator = AutomationOrchestrator(config_path=temp_config_file)
        
        # Мокируем частичную отправку
        mock_components['telegram_sender'].send_summaries.return_value = (True, False)
        
        result = await orchestrator.send_results("Негативная", "Позитивная")
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_send_results_no_chat_id(self, temp_config_file, mock_components):
        """Тест отправки без указанного chat_id"""
        orchestrator = AutomationOrchestrator(config_path=temp_config_file)
        orchestrator.config['AUTOMATION']['target_chat_id'] = None
        
        with pytest.raises(AutomationError, match="Не указан target_chat_id"):
            await orchestrator.send_results("Негативная", "Позитивная")


class TestAutomationOrchestratorCleanupResources:
    """Тесты метода cleanup_resources"""
    
    @pytest.mark.asyncio
    async def test_cleanup_resources_success(self, temp_config_file, mock_components):
        """Тест успешной очистки ресурсов"""
        orchestrator = AutomationOrchestrator(config_path=temp_config_file)
        
        await orchestrator.cleanup_resources(
            notebook_id="notebook_123",
            temp_files=["/tmp/file1.csv", "/tmp/file2.csv"]
        )
        
        mock_components['file_manager'].cleanup_notebook.assert_called_once_with("notebook_123")
        mock_components['file_manager'].cleanup_temp_files.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_cleanup_resources_graceful_degradation(self, temp_config_file, mock_components):
        """Тест graceful degradation при ошибках очистки"""
        orchestrator = AutomationOrchestrator(config_path=temp_config_file)
        
        # Мокируем ошибку при очистке ноутбука
        mock_components['file_manager'].cleanup_notebook.side_effect = Exception("Cleanup error")
        
        # Не должно выбрасывать исключение
        await orchestrator.cleanup_resources(notebook_id="notebook_123")
        
        mock_components['file_manager'].cleanup_notebook.assert_called_once()


class TestAutomationOrchestratorRunAutomation:
    """Тесты основного метода run_automation"""
    
    @pytest.mark.asyncio
    async def test_run_automation_full_cycle_success(self, temp_config_file, mock_components, tmp_path):
        """Тест полного цикла автоматизации"""
        orchestrator = AutomationOrchestrator(config_path=temp_config_file)
        
        # Создаем временный файл для экспорта
        export_file = tmp_path / "export.csv"
        export_file.write_text("test,data\n1,2")
        mock_components['exporter'].export_to_excel.return_value = str(export_file)
        
        start_date = datetime.now() - timedelta(days=1)
        end_date = datetime.now()
        
        stats = await orchestrator.run_automation((start_date, end_date))
        
        # Проверяем, что все этапы выполнены
        assert stats['telegram_sent'] is True
        assert stats['end_time'] is not None
        assert len(stats['errors']) == 0
        
        # Проверяем вызовы компонентов
        mock_components['database'].get_messages.assert_called()
        mock_components['file_manager'].create_notebook_with_source.assert_called_once()
        mock_components['summary_generator'].generate_summaries_parallel.assert_called_once()
        mock_components['telegram_sender'].send_summaries.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_run_automation_error_handling(self, temp_config_file, mock_components):
        """Тест обработки ошибок в run_automation"""
        orchestrator = AutomationOrchestrator(config_path=temp_config_file)
        
        # Мокируем ошибку при экспорте
        mock_components['database'].get_messages.return_value = []
        
        start_date = datetime.now() - timedelta(days=1)
        end_date = datetime.now()
        
        with pytest.raises(AutomationError):
            await orchestrator.run_automation((start_date, end_date))
        
        # Проверяем, что уведомление об ошибке было отправлено
        mock_components['telegram_sender'].send_error_notification.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_run_automation_cleanup_on_error(self, temp_config_file, mock_components, tmp_path):
        """Тест очистки ресурсов при ошибке"""
        orchestrator = AutomationOrchestrator(config_path=temp_config_file)
        
        # Создаем временный файл
        export_file = tmp_path / "export.csv"
        export_file.write_text("test,data\n1,2")
        mock_components['exporter'].export_to_excel.return_value = str(export_file)
        
        # Мокируем ошибку при генерации сводок
        mock_components['summary_generator'].generate_summaries_parallel.side_effect = \
            NotebookLMAPIError("API Error")
        
        # Создаем сообщение с датой в диапазоне теста
        test_message_date = datetime.now() - timedelta(hours=12)
        mock_components['database'].get_messages.return_value = [
            Mock(
                date=test_message_date,
                channel="test_channel",
                message_id=1,
                text="Test message"
            )
        ]
        
        start_date = datetime.now() - timedelta(days=1)
        end_date = datetime.now()
        
        with pytest.raises(AutomationError):
            await orchestrator.run_automation((start_date, end_date))
        
        # Проверяем, что cleanup был вызван в finally блоке
        # cleanup_temp_files должен быть вызван с файлом экспорта
        assert mock_components['file_manager'].cleanup_temp_files.called


class TestAutomationOrchestratorDateRange:
    """Тесты метода get_date_range_for_schedule"""
    
    def test_get_date_range_monday(self, temp_config_file, mock_components):
        """Тест диапазона дат для понедельника (пятница-воскресенье)"""
        orchestrator = AutomationOrchestrator(config_path=temp_config_file)
        
        # Мокируем понедельник
        with patch('src.automation.orchestrator.datetime') as mock_datetime:
            mock_now = datetime(2024, 1, 8, 9, 0)  # Понедельник, 8 января 2024
            mock_datetime.now.return_value = mock_now
            mock_datetime.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)
            
            start_date, end_date = orchestrator.get_date_range_for_schedule()
            
            # Проверяем, что диапазон - пятница-воскресенье
            assert start_date.day == 5  # Пятница
            assert end_date.day == 7    # Воскресенье
    
    def test_get_date_range_weekday(self, temp_config_file, mock_components):
        """Тест диапазона дат для будних дней (предыдущий день)"""
        orchestrator = AutomationOrchestrator(config_path=temp_config_file)
        
        # Мокируем вторник
        with patch('src.automation.orchestrator.datetime') as mock_datetime:
            mock_now = datetime(2024, 1, 9, 9, 0)  # Вторник, 9 января 2024
            mock_datetime.now.return_value = mock_now
            mock_datetime.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)
            
            start_date, end_date = orchestrator.get_date_range_for_schedule()
            
            # Проверяем, что диапазон - предыдущий день
            assert start_date.day == 8  # Понедельник
            assert end_date.day == 8    # Понедельник


class TestAutomationOrchestratorSchedule:
    """Тесты метода setup_schedule"""
    
    def test_setup_schedule_success(self, temp_config_file, mock_components):
        """Тест успешной настройки расписания"""
        orchestrator = AutomationOrchestrator(config_path=temp_config_file)
        
        with patch('src.automation.orchestrator.scheduler') as mock_scheduler:
            orchestrator.setup_schedule()
            
            mock_scheduler.add_daily_task.assert_called_once()
            mock_scheduler.start.assert_called_once()
    
    def test_setup_schedule_invalid_time_format(self, temp_config_file, mock_components):
        """Тест настройки расписания с невалидным форматом времени"""
        orchestrator = AutomationOrchestrator(config_path=temp_config_file)
        orchestrator.config['AUTOMATION']['schedule_time'] = "invalid_time"
        
        with patch('src.automation.orchestrator.scheduler') as mock_scheduler:
            orchestrator.setup_schedule()
            
            # Проверяем, что используется время по умолчанию
            call_args = mock_scheduler.add_daily_task.call_args
            assert call_args[1]['time_str'] == '09:00'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
