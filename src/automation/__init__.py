"""
Automation Module

Модуль для оркестрации процесса автоматизации создания аналитических сводок.
"""

from .models import NotebookInfo, SummaryResult, AutomationStats
from .orchestrator import AutomationOrchestrator, AutomationError

__version__ = "0.1.0"

__all__ = [
    'NotebookInfo',
    'SummaryResult',
    'AutomationStats',
    'AutomationOrchestrator',
    'AutomationError',
]
