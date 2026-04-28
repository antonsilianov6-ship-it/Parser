# -*- coding: utf-8 -*-
"""
Модуль для работы с датами
Предоставляет утилиты для парсинга, форматирования и работы с диапазонами дат
"""

from datetime import datetime, timezone, timedelta
from typing import Tuple, Optional
from src.config import get_parser_config
from src.utils.logger import setup_logger

logger = setup_logger(__name__)


class DateUtils:
    """Утилиты для работы с датами"""
    
    @staticmethod
    def parse_date_from_config(date_str: str) -> datetime:
        """
        Парсит дату из конфигурации в формате DD-MM-YYYY
        
        Args:
            date_str: Строка с датой в формате DD-MM-YYYY
            
        Returns:
            datetime объект в UTC
            
        Raises:
            ValueError: Если формат даты неверный
        """
        try:
            parsed_date = datetime.strptime(date_str, '%d-%m-%Y')
            return parsed_date.replace(tzinfo=timezone.utc)
        except ValueError as e:
            logger.error(f"Ошибка при парсинге даты '{date_str}': {e}")
            raise ValueError(f"Неверный формат даты '{date_str}'. Ожидается формат DD-MM-YYYY") from e
    
    @staticmethod
    def to_utc(dt: datetime) -> datetime:
        """
        Конвертирует datetime в UTC
        
        Args:
            dt: datetime объект
            
        Returns:
            datetime объект в UTC
        """
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    
    @staticmethod
    def format_date(dt: datetime, format: str = '%Y-%m-%d %H:%M:%S') -> str:
        """
        Форматирует дату в строку
        
        Args:
            dt: datetime объект
            format: Формат строки (по умолчанию '%Y-%m-%d %H:%M:%S')
            
        Returns:
            Отформатированная строка с датой
        """
        return dt.strftime(format)
    
    @staticmethod
    def get_date_range(days: Optional[int] = None) -> Tuple[datetime, datetime]:
        """
        Получает диапазон дат для выгрузки сообщений на основе конфигурации
        
        Args:
            days: Количество дней для выгрузки сообщений (если не указано, берется из конфигурации)
            
        Returns:
            Кортеж (start_date, end_date) в UTC
        """
        parser_config = get_parser_config()
        
        if parser_config['DATE_RANGE_ENABLED']:
            try:
                start_date = DateUtils.parse_date_from_config(parser_config['START_DATE'])
                end_date = DateUtils.parse_date_from_config(parser_config['END_DATE'])
                end_date = end_date.replace(hour=23, minute=59, second=59, tzinfo=timezone.utc)
                
                logger.info(f"Используется заданный диапазон дат: с {start_date} по {end_date}")
                return start_date, end_date
            except (ValueError, KeyError) as e:
                logger.error(f"Ошибка при парсинге дат из конфигурации: {e}. Используем резервный вариант.")
        
        if days is None:
            days = parser_config['DAYS_FOR_EXPORT']
        
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=days)
        
        logger.info(f"Используется диапазон дат на основе дней ({days}): с {start_date} по {end_date}")
        return start_date, end_date

