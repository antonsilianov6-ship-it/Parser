# -*- coding: utf-8 -*-
"""
Тесты для валидатора конфигурации
"""
import pytest
import os
import tempfile
from src.automation.config_validator import ConfigValidator


class TestConfigValidator:
    """Тесты для ConfigValidator"""
    
    def test_validate_notebooklm_config_valid(self):
        """Тест валидации корректной конфигурации NotebookLM"""
        config = {
            'email': 'test@example.com',
            'password': 'password123',
            'prompts_config': 'config/prompts.json',
            'timeout': 120,
            'max_retries': 3,
            'retry_delay_base': 2
        }
        
        validated, warnings = ConfigValidator.validate_notebooklm_config(config)
        
        assert validated['email'] == 'test@example.com'
        assert validated['password'] == 'password123'
        assert validated['timeout'] == 120
        assert validated['max_retries'] == 3
        assert validated['retry_delay_base'] == 2
    
    def test_validate_notebooklm_config_missing_required(self):
        """Тест валидации конфигурации NotebookLM с отсутствующими обязательными полями"""
        config = {
            'timeout': 120
        }
        
        validated, warnings = ConfigValidator.validate_notebooklm_config(config)
        
        # Проверяем, что есть предупреждения об отсутствующих полях
        assert any('email' in w for w in warnings)
        assert any('password' in w for w in warnings)
    
    def test_validate_notebooklm_config_invalid_timeout(self):
        """Тест валидации конфигурации NotebookLM с невалидным timeout"""
        config = {
            'email': 'test@example.com',
            'password': 'password123',
            'timeout': -10
        }
        
        validated, warnings = ConfigValidator.validate_notebooklm_config(config)
        
        # Проверяем, что timeout заменен на значение по умолчанию
        assert validated['timeout'] == ConfigValidator.NOTEBOOKLM_DEFAULTS['timeout']
        assert any('timeout' in w for w in warnings)
    
    def test_validate_notebooklm_config_invalid_max_retries(self):
        """Тест валидации конфигурации NotebookLM с невалидным max_retries"""
        config = {
            'email': 'test@example.com',
            'password': 'password123',
            'max_retries': -1
        }
        
        validated, warnings = ConfigValidator.validate_notebooklm_config(config)
        
        # Проверяем, что max_retries заменен на значение по умолчанию
        assert validated['max_retries'] == ConfigValidator.NOTEBOOKLM_DEFAULTS['max_retries']
        assert any('max_retries' in w for w in warnings)
    
    def test_validate_notebooklm_config_invalid_retry_delay_base(self):
        """Тест валидации конфигурации NotebookLM с невалидным retry_delay_base"""
        config = {
            'email': 'test@example.com',
            'password': 'password123',
            'retry_delay_base': 1
        }
        
        validated, warnings = ConfigValidator.validate_notebooklm_config(config)
        
        # Проверяем, что retry_delay_base заменен на значение по умолчанию
        assert validated['retry_delay_base'] == ConfigValidator.NOTEBOOKLM_DEFAULTS['retry_delay_base']
        assert any('retry_delay_base' in w for w in warnings)
    
    def test_validate_automation_config_valid(self):
        """Тест валидации корректной конфигурации Automation"""
        config = {
            'enabled': True,
            'target_chat_id': '@test_channel',
            'schedule_enabled': True,
            'schedule_time': '09:00',
            'schedule_days': ['monday', 'tuesday', 'wednesday', 'thursday', 'friday'],
            'export_format': 'csv',
            'export_dir': 'exports',
            'cleanup_temp_files': True,
            'cleanup_notebooks': True,
            'parallel_generation': True,
            'send_error_notifications': True,
            'telegram_retry_delay': 5,
            'telegram_max_retries': 3,
            'telegram_message_max_length': 4096
        }
        
        validated, warnings = ConfigValidator.validate_automation_config(config)
        
        assert validated['enabled'] is True
        assert validated['target_chat_id'] == '@test_channel'
        assert validated['schedule_time'] == '09:00'
        assert validated['export_format'] == 'csv'
        assert validated['telegram_max_retries'] == 3
    
    def test_validate_automation_config_missing_target_chat_id(self):
        """Тест валидации конфигурации Automation с отсутствующим target_chat_id"""
        config = {
            'enabled': True
        }
        
        validated, warnings = ConfigValidator.validate_automation_config(config)
        
        # Проверяем, что есть предупреждение об отсутствующем target_chat_id
        assert any('target_chat_id' in w for w in warnings)
    
    def test_validate_automation_config_invalid_export_format(self):
        """Тест валидации конфигурации Automation с невалидным форматом экспорта"""
        config = {
            'target_chat_id': '@test_channel',
            'export_format': 'xml'
        }
        
        validated, warnings = ConfigValidator.validate_automation_config(config)
        
        # Отладочный вывод
        print(f"Warnings: {warnings}")
        print(f"Validated export_format: {validated['export_format']}")
        
        # Проверяем, что export_format заменен на значение по умолчанию
        assert validated['export_format'] == ConfigValidator.AUTOMATION_DEFAULTS['export_format']
        assert any('Невалидный формат экспорта' in w for w in warnings)
    
    def test_validate_automation_config_invalid_schedule_time(self):
        """Тест валидации конфигурации Automation с невалидным временем расписания"""
        config = {
            'target_chat_id': '@test_channel',
            'schedule_time': '25:00'
        }
        
        validated, warnings = ConfigValidator.validate_automation_config(config)
        
        # Проверяем, что schedule_time заменен на значение по умолчанию
        assert validated['schedule_time'] == ConfigValidator.AUTOMATION_DEFAULTS['schedule_time']
        assert any('schedule_time' in w for w in warnings)
    
    def test_validate_automation_config_invalid_schedule_days(self):
        """Тест валидации конфигурации Automation с невалидными днями недели"""
        config = {
            'target_chat_id': '@test_channel',
            'schedule_days': ['monday', 'invalid_day', 'friday']
        }
        
        validated, warnings = ConfigValidator.validate_automation_config(config)
        
        # Проверяем, что schedule_days заменен на значение по умолчанию
        assert validated['schedule_days'] == ConfigValidator.AUTOMATION_DEFAULTS['schedule_days']
        assert any('invalid_day' in w for w in warnings)
    
    def test_validate_automation_config_invalid_telegram_retry_delay(self):
        """Тест валидации конфигурации Automation с невалидным telegram_retry_delay"""
        config = {
            'target_chat_id': '@test_channel',
            'telegram_retry_delay': -5
        }
        
        validated, warnings = ConfigValidator.validate_automation_config(config)
        
        # Проверяем, что telegram_retry_delay заменен на значение по умолчанию
        assert validated['telegram_retry_delay'] == ConfigValidator.AUTOMATION_DEFAULTS['telegram_retry_delay']
        assert any('telegram_retry_delay' in w for w in warnings)
    
    def test_validate_automation_config_invalid_telegram_max_retries(self):
        """Тест валидации конфигурации Automation с невалидным telegram_max_retries"""
        config = {
            'target_chat_id': '@test_channel',
            'telegram_max_retries': -1
        }
        
        validated, warnings = ConfigValidator.validate_automation_config(config)
        
        # Проверяем, что telegram_max_retries заменен на значение по умолчанию
        assert validated['telegram_max_retries'] == ConfigValidator.AUTOMATION_DEFAULTS['telegram_max_retries']
        assert any('telegram_max_retries' in w for w in warnings)
    
    def test_validate_automation_config_invalid_message_max_length(self):
        """Тест валидации конфигурации Automation с невалидным telegram_message_max_length"""
        config = {
            'target_chat_id': '@test_channel',
            'telegram_message_max_length': 0
        }
        
        validated, warnings = ConfigValidator.validate_automation_config(config)
        
        # Проверяем, что telegram_message_max_length заменен на значение по умолчанию
        assert validated['telegram_message_max_length'] == ConfigValidator.AUTOMATION_DEFAULTS['telegram_message_max_length']
        assert any('telegram_message_max_length' in w for w in warnings)
    
    def test_validate_automation_config_creates_export_dir(self):
        """Тест валидации конфигурации Automation с несуществующей директорией экспорта"""
        with tempfile.TemporaryDirectory() as tmpdir:
            export_dir = os.path.join(tmpdir, 'test_exports')
            config = {
                'target_chat_id': '@test_channel',
                'export_dir': export_dir
            }
            
            # Проверяем, что директория не существует
            assert not os.path.exists(export_dir)
            
            validated, warnings = ConfigValidator.validate_automation_config(config)
            
            # Проверяем, что директория создана
            assert os.path.exists(export_dir)
            assert any('не существует' in w for w in warnings)
    
    def test_validate_and_apply_full_config(self):
        """Тест валидации полной конфигурации"""
        config = {
            'NOTEBOOKLM': {
                'email': 'test@example.com',
                'password': 'password123'
            },
            'AUTOMATION': {
                'target_chat_id': '@test_channel'
            }
        }
        
        validated = ConfigValidator.validate_and_apply(config)
        
        # Проверяем, что обе секции присутствуют
        assert 'NOTEBOOKLM' in validated
        assert 'AUTOMATION' in validated
        
        # Проверяем, что применены значения по умолчанию
        assert validated['NOTEBOOKLM']['timeout'] == ConfigValidator.NOTEBOOKLM_DEFAULTS['timeout']
        assert validated['AUTOMATION']['export_format'] == ConfigValidator.AUTOMATION_DEFAULTS['export_format']
    
    def test_validate_and_apply_missing_sections(self):
        """Тест валидации конфигурации с отсутствующими секциями"""
        config = {}
        
        validated = ConfigValidator.validate_and_apply(config)
        
        # Проверяем, что секции созданы со значениями по умолчанию
        assert 'NOTEBOOKLM' in validated
        assert 'AUTOMATION' in validated
        assert validated['NOTEBOOKLM']['timeout'] == ConfigValidator.NOTEBOOKLM_DEFAULTS['timeout']
        assert validated['AUTOMATION']['export_format'] == ConfigValidator.AUTOMATION_DEFAULTS['export_format']
