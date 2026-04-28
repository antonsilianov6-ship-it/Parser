# -*- coding: utf-8 -*-
"""
Unit тесты для модуля DateUtils
"""

import unittest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock
from src.utils.date_utils import DateUtils


class TestDateUtils(unittest.TestCase):
    """Тесты для класса DateUtils"""
    
    def test_parse_date_from_config_valid(self):
        """Тест парсинга корректной даты"""
        date_str = "15-03-2024"
        result = DateUtils.parse_date_from_config(date_str)
        
        self.assertEqual(result.year, 2024)
        self.assertEqual(result.month, 3)
        self.assertEqual(result.day, 15)
        self.assertEqual(result.tzinfo, timezone.utc)
    
    def test_parse_date_from_config_invalid_format(self):
        """Тест парсинга даты с неверным форматом"""
        date_str = "2024-03-15"  # Неверный формат (YYYY-MM-DD вместо DD-MM-YYYY)
        
        with self.assertRaises(ValueError) as context:
            DateUtils.parse_date_from_config(date_str)
        
        self.assertIn("Неверный формат даты", str(context.exception))
    
    def test_parse_date_from_config_invalid_date(self):
        """Тест парсинга несуществующей даты"""
        date_str = "32-13-2024"  # Несуществующая дата
        
        with self.assertRaises(ValueError):
            DateUtils.parse_date_from_config(date_str)
    
    def test_to_utc_naive_datetime(self):
        """Тест конвертации naive datetime в UTC"""
        dt = datetime(2024, 3, 15, 12, 30, 0)
        result = DateUtils.to_utc(dt)
        
        self.assertEqual(result.tzinfo, timezone.utc)
        self.assertEqual(result.year, 2024)
        self.assertEqual(result.month, 3)
        self.assertEqual(result.day, 15)
    
    def test_to_utc_aware_datetime(self):
        """Тест конвертации aware datetime в UTC"""
        # Создаем datetime с другим timezone (UTC+3)
        tz_plus_3 = timezone(timedelta(hours=3))
        dt = datetime(2024, 3, 15, 15, 30, 0, tzinfo=tz_plus_3)
        
        result = DateUtils.to_utc(dt)
        
        self.assertEqual(result.tzinfo, timezone.utc)
        # 15:30 UTC+3 = 12:30 UTC
        self.assertEqual(result.hour, 12)
    
    def test_format_date_default_format(self):
        """Тест форматирования даты с форматом по умолчанию"""
        dt = datetime(2024, 3, 15, 12, 30, 45, tzinfo=timezone.utc)
        result = DateUtils.format_date(dt)
        
        self.assertEqual(result, "2024-03-15 12:30:45")
    
    def test_format_date_custom_format(self):
        """Тест форматирования даты с кастомным форматом"""
        dt = datetime(2024, 3, 15, 12, 30, 45, tzinfo=timezone.utc)
        result = DateUtils.format_date(dt, format='%d/%m/%Y')
        
        self.assertEqual(result, "15/03/2024")
    
    @patch('src.utils.date_utils.get_parser_config')
    def test_get_date_range_with_config_dates(self, mock_get_config):
        """Тест получения диапазона дат из конфигурации"""
        mock_get_config.return_value = {
            'DATE_RANGE_ENABLED': True,
            'START_DATE': '01-03-2024',
            'END_DATE': '15-03-2024',
            'DAYS_FOR_EXPORT': 3
        }
        
        start_date, end_date = DateUtils.get_date_range()
        
        self.assertEqual(start_date.day, 1)
        self.assertEqual(start_date.month, 3)
        self.assertEqual(start_date.year, 2024)
        
        self.assertEqual(end_date.day, 15)
        self.assertEqual(end_date.month, 3)
        self.assertEqual(end_date.year, 2024)
        self.assertEqual(end_date.hour, 23)
        self.assertEqual(end_date.minute, 59)
        self.assertEqual(end_date.second, 59)
    
    @patch('src.utils.date_utils.get_parser_config')
    @patch('src.utils.date_utils.datetime')
    def test_get_date_range_with_days(self, mock_datetime, mock_get_config):
        """Тест получения диапазона дат по количеству дней"""
        # Мокаем текущее время
        fixed_now = datetime(2024, 3, 15, 12, 0, 0, tzinfo=timezone.utc)
        mock_datetime.now.return_value = fixed_now
        
        mock_get_config.return_value = {
            'DATE_RANGE_ENABLED': False,
            'DAYS_FOR_EXPORT': 7
        }
        
        start_date, end_date = DateUtils.get_date_range()
        
        self.assertEqual(end_date, fixed_now)
        expected_start = fixed_now - timedelta(days=7)
        self.assertEqual(start_date, expected_start)
    
    @patch('src.utils.date_utils.get_parser_config')
    @patch('src.utils.date_utils.datetime')
    def test_get_date_range_with_custom_days(self, mock_datetime, mock_get_config):
        """Тест получения диапазона дат с кастомным количеством дней"""
        fixed_now = datetime(2024, 3, 15, 12, 0, 0, tzinfo=timezone.utc)
        mock_datetime.now.return_value = fixed_now
        
        mock_get_config.return_value = {
            'DATE_RANGE_ENABLED': False,
            'DAYS_FOR_EXPORT': 3
        }
        
        start_date, end_date = DateUtils.get_date_range(days=10)
        
        self.assertEqual(end_date, fixed_now)
        expected_start = fixed_now - timedelta(days=10)
        self.assertEqual(start_date, expected_start)
    
    @patch('src.utils.date_utils.get_parser_config')
    @patch('src.utils.date_utils.logger')
    def test_get_date_range_fallback_on_error(self, mock_logger, mock_get_config):
        """Тест fallback на количество дней при ошибке парсинга дат из конфига"""
        mock_get_config.return_value = {
            'DATE_RANGE_ENABLED': True,
            'START_DATE': 'invalid-date',  # Невалидная дата
            'END_DATE': '15-03-2024',
            'DAYS_FOR_EXPORT': 5
        }
        
        start_date, end_date = DateUtils.get_date_range()
        
        # Должен использовать fallback с DAYS_FOR_EXPORT
        # Проверяем, что разница между датами составляет 5 дней
        delta = end_date - start_date
        self.assertEqual(delta.days, 5)
        
        # Проверяем, что была залогирована ошибка
        mock_logger.error.assert_called()


if __name__ == '__main__':
    unittest.main()
