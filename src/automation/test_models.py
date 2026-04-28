"""
Unit tests for automation data models
"""

import pytest
from datetime import datetime, timedelta
from src.automation.models import NotebookInfo, SummaryResult, AutomationStats


class TestNotebookInfo:
    """Тесты для модели NotebookInfo"""
    
    def test_notebook_info_creation_with_required_fields(self):
        """Тест создания NotebookInfo с обязательными полями"""
        notebook = NotebookInfo(
            notebook_id="nb_123",
            title="Test Notebook"
        )
        
        assert notebook.notebook_id == "nb_123"
        assert notebook.title == "Test Notebook"
        assert notebook.source_id is None
        assert notebook.status == "active"
        assert isinstance(notebook.created_at, datetime)
    
    def test_notebook_info_creation_with_all_fields(self):
        """Тест создания NotebookInfo со всеми полями"""
        created_time = datetime.now()
        notebook = NotebookInfo(
            notebook_id="nb_456",
            title="Full Notebook",
            source_id="src_789",
            created_at=created_time,
            status="processing"
        )
        
        assert notebook.notebook_id == "nb_456"
        assert notebook.title == "Full Notebook"
        assert notebook.source_id == "src_789"
        assert notebook.created_at == created_time
        assert notebook.status == "processing"
    
    def test_notebook_info_default_status(self):
        """Тест значения статуса по умолчанию"""
        notebook = NotebookInfo(
            notebook_id="nb_default",
            title="Default Status"
        )
        
        assert notebook.status == "active"
    
    def test_notebook_info_status_values(self):
        """Тест различных значений статуса"""
        statuses = ["active", "processing", "completed", "error"]
        
        for status in statuses:
            notebook = NotebookInfo(
                notebook_id=f"nb_{status}",
                title=f"Notebook {status}",
                status=status
            )
            assert notebook.status == status


class TestSummaryResult:
    """Тесты для модели SummaryResult"""
    
    def test_summary_result_creation(self):
        """Тест создания SummaryResult"""
        summary = SummaryResult(
            summary_type="negative",
            content="This is a test summary with multiple words"
        )
        
        assert summary.summary_type == "negative"
        assert summary.content == "This is a test summary with multiple words"
        assert isinstance(summary.generated_at, datetime)
        assert summary.sent_to_telegram is False
    
    def test_summary_result_word_count_auto_calculation(self):
        """Тест автоматического подсчета слов в __post_init__"""
        summary = SummaryResult(
            summary_type="positive",
            content="One two three four five"
        )
        
        assert summary.word_count == 5
    
    def test_summary_result_word_count_empty_content(self):
        """Тест подсчета слов для пустого контента"""
        summary = SummaryResult(
            summary_type="negative",
            content=""
        )
        
        # Пустая строка split() возвращает [], поэтому word_count = 0
        assert summary.word_count == 0
    
    def test_summary_result_word_count_single_word(self):
        """Тест подсчета слов для одного слова"""
        summary = SummaryResult(
            summary_type="positive",
            content="Word"
        )
        
        assert summary.word_count == 1
    
    def test_summary_result_word_count_multiline(self):
        """Тест подсчета слов для многострочного текста"""
        content = """First line with words
        Second line with more words
        Third line"""
        
        summary = SummaryResult(
            summary_type="negative",
            content=content
        )
        
        # split() разбивает по всем пробельным символам, включая переносы строк
        # В данном случае: First, line, with, words, Second, line, with, more, words, Third, line = 11 слов
        assert summary.word_count == 11
    
    def test_summary_result_sent_to_telegram_flag(self):
        """Тест флага отправки в Telegram"""
        summary = SummaryResult(
            summary_type="positive",
            content="Test content",
            sent_to_telegram=True
        )
        
        assert summary.sent_to_telegram is True
    
    def test_summary_result_types(self):
        """Тест различных типов сводок"""
        negative = SummaryResult(
            summary_type="negative",
            content="Negative summary"
        )
        positive = SummaryResult(
            summary_type="positive",
            content="Positive summary"
        )
        
        assert negative.summary_type == "negative"
        assert positive.summary_type == "positive"


class TestAutomationStats:
    """Тесты для модели AutomationStats"""
    
    def test_automation_stats_creation(self):
        """Тест создания AutomationStats"""
        start = datetime.now()
        stats = AutomationStats(start_time=start)
        
        assert stats.start_time == start
        assert stats.end_time is None
        assert stats.messages_processed == 0
        assert stats.notebook_id is None
        assert stats.negative_summary_length == 0
        assert stats.positive_summary_length == 0
        assert stats.telegram_sent is False
        assert stats.errors == []
    
    def test_automation_stats_duration_not_completed(self):
        """Тест вычисления длительности для незавершенного выполнения"""
        start = datetime.now()
        stats = AutomationStats(start_time=start)
        
        assert stats.duration_seconds == 0.0
    
    def test_automation_stats_duration_completed(self):
        """Тест вычисления длительности для завершенного выполнения"""
        start = datetime.now()
        end = start + timedelta(seconds=120)
        
        stats = AutomationStats(
            start_time=start,
            end_time=end
        )
        
        assert stats.duration_seconds == 120.0
    
    def test_automation_stats_duration_property(self):
        """Тест property duration_seconds"""
        start = datetime(2024, 1, 1, 10, 0, 0)
        end = datetime(2024, 1, 1, 10, 5, 30)
        
        stats = AutomationStats(
            start_time=start,
            end_time=end
        )
        
        expected_duration = 330.0  # 5 минут 30 секунд
        assert stats.duration_seconds == expected_duration
    
    def test_automation_stats_to_dict_not_completed(self):
        """Тест сериализации незавершенной статистики"""
        start = datetime(2024, 1, 1, 10, 0, 0)
        stats = AutomationStats(
            start_time=start,
            messages_processed=100
        )
        
        result = stats.to_dict()
        
        assert result['start_time'] == start.isoformat()
        assert result['end_time'] is None
        assert result['duration_seconds'] == 0.0
        assert result['messages_processed'] == 100
        assert result['notebook_id'] is None
        assert result['negative_summary_length'] == 0
        assert result['positive_summary_length'] == 0
        assert result['telegram_sent'] is False
        assert result['errors_count'] == 0
        assert result['errors'] == []
    
    def test_automation_stats_to_dict_completed(self):
        """Тест сериализации завершенной статистики"""
        start = datetime(2024, 1, 1, 10, 0, 0)
        end = datetime(2024, 1, 1, 10, 5, 0)
        
        stats = AutomationStats(
            start_time=start,
            end_time=end,
            messages_processed=150,
            notebook_id="nb_test_123",
            negative_summary_length=500,
            positive_summary_length=450,
            telegram_sent=True,
            errors=["Error 1", "Error 2"]
        )
        
        result = stats.to_dict()
        
        assert result['start_time'] == start.isoformat()
        assert result['end_time'] == end.isoformat()
        assert result['duration_seconds'] == 300.0
        assert result['messages_processed'] == 150
        assert result['notebook_id'] == "nb_test_123"
        assert result['negative_summary_length'] == 500
        assert result['positive_summary_length'] == 450
        assert result['telegram_sent'] is True
        assert result['errors_count'] == 2
        assert result['errors'] == ["Error 1", "Error 2"]
    
    def test_automation_stats_errors_list(self):
        """Тест работы со списком ошибок"""
        start = datetime.now()
        stats = AutomationStats(start_time=start)
        
        # Добавляем ошибки
        stats.errors.append("First error")
        stats.errors.append("Second error")
        
        assert len(stats.errors) == 2
        assert stats.errors[0] == "First error"
        assert stats.errors[1] == "Second error"
        
        result = stats.to_dict()
        assert result['errors_count'] == 2
    
    def test_automation_stats_all_fields(self):
        """Тест создания статистики со всеми полями"""
        start = datetime(2024, 1, 1, 9, 0, 0)
        end = datetime(2024, 1, 1, 9, 10, 0)
        
        stats = AutomationStats(
            start_time=start,
            end_time=end,
            messages_processed=200,
            notebook_id="nb_full_test",
            negative_summary_length=1000,
            positive_summary_length=950,
            telegram_sent=True,
            errors=["Network timeout", "API rate limit"]
        )
        
        assert stats.start_time == start
        assert stats.end_time == end
        assert stats.messages_processed == 200
        assert stats.notebook_id == "nb_full_test"
        assert stats.negative_summary_length == 1000
        assert stats.positive_summary_length == 950
        assert stats.telegram_sent is True
        assert len(stats.errors) == 2
        assert stats.duration_seconds == 600.0
