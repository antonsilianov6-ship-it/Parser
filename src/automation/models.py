"""
Data models for NotebookLM Telegram Automation

This module contains dataclass models for managing automation workflow data.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Any


@dataclass
class NotebookInfo:
    """
    Информация о ноутбуке NotebookLM
    
    Attributes:
        notebook_id: Уникальный идентификатор ноутбука
        title: Название ноутбука
        source_id: Идентификатор источника данных (опционально)
        created_at: Время создания ноутбука
        status: Статус ноутбука (active, processing, completed, error)
    """
    notebook_id: str
    title: str
    source_id: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    status: str = "active"


@dataclass
class SummaryResult:
    """
    Результат генерации аналитической сводки
    
    Attributes:
        summary_type: Тип сводки ('negative' или 'positive')
        content: Текст сводки
        generated_at: Время генерации сводки
        word_count: Количество слов в сводке (вычисляется автоматически)
        sent_to_telegram: Флаг успешной отправки в Telegram
    """
    summary_type: str
    content: str
    generated_at: datetime = field(default_factory=datetime.now)
    word_count: int = 0
    sent_to_telegram: bool = False
    
    def __post_init__(self):
        """Автоматический подсчет количества слов в сводке"""
        self.word_count = len(self.content.split())


@dataclass
class AutomationStats:
    """
    Статистика выполнения автоматизации
    
    Attributes:
        start_time: Время начала выполнения
        end_time: Время завершения выполнения (опционально)
        messages_processed: Количество обработанных сообщений
        notebook_id: ID созданного ноутбука (опционально)
        negative_summary_length: Длина негативной сводки в символах
        positive_summary_length: Длина позитивной сводки в символах
        telegram_sent: Флаг успешной отправки в Telegram
        errors: Список ошибок, возникших во время выполнения
    """
    start_time: datetime
    end_time: Optional[datetime] = None
    messages_processed: int = 0
    notebook_id: Optional[str] = None
    negative_summary_length: int = 0
    positive_summary_length: int = 0
    telegram_sent: bool = False
    errors: List[str] = field(default_factory=list)
    
    @property
    def duration_seconds(self) -> float:
        """
        Вычисляет длительность выполнения в секундах
        
        Returns:
            Длительность в секундах, или 0.0 если выполнение не завершено
        """
        if self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Сериализует статистику в словарь
        
        Returns:
            Словарь с полями статистики
        """
        return {
            'start_time': self.start_time.isoformat(),
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'duration_seconds': self.duration_seconds,
            'messages_processed': self.messages_processed,
            'notebook_id': self.notebook_id,
            'negative_summary_length': self.negative_summary_length,
            'positive_summary_length': self.positive_summary_length,
            'telegram_sent': self.telegram_sent,
            'errors_count': len(self.errors),
            'errors': self.errors
        }
