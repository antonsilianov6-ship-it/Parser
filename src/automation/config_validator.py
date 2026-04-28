# -*- coding: utf-8 -*-
"""
Валидатор конфигурации для системы автоматизации NotebookLM
"""
import os
from typing import Dict, Any, List, Tuple
from datetime import datetime
from src.utils.logger import setup_logger

logger = setup_logger(__name__)


class ConfigValidator:
    """Валидатор конфигурации с поддержкой значений по умолчанию"""
    
    # Значения по умолчанию для NotebookLM
    NOTEBOOKLM_DEFAULTS = {
        'prompts_config': 'config/prompts.json',
        'timeout': 120,
        'max_retries': 3,
        'retry_delay_base': 2
    }
    
    # Значения по умолчанию для Automation
    AUTOMATION_DEFAULTS = {
        'enabled': False,
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
    
    # Обязательные поля
    NOTEBOOKLM_REQUIRED = ['email', 'password']
    AUTOMATION_REQUIRED = ['target_chat_id']
    
    # Допустимые форматы экспорта
    VALID_EXPORT_FORMATS = ['csv', 'json']
    
    # Допустимые дни недели
    VALID_DAYS = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
    
    @staticmethod
    def validate_notebooklm_config(config: Dict[str, Any]) -> Tuple[Dict[str, Any], List[str]]:
        """
        Валидирует конфигурацию NotebookLM
        
        Args:
            config: Словарь с конфигурацией NotebookLM
        
        Returns:
            Кортеж (validated_config, warnings)
        """
        validated = config.copy()
        warnings = []
        
        # Проверка обязательных полей
        for field in ConfigValidator.NOTEBOOKLM_REQUIRED:
            if field not in validated or not validated[field]:
                warnings.append(f"NotebookLM: Обязательное поле '{field}' не задано или пустое")
        
        # Применение значений по умолчанию для опциональных полей
        for field, default_value in ConfigValidator.NOTEBOOKLM_DEFAULTS.items():
            if field not in validated or validated[field] is None:
                validated[field] = default_value
                warnings.append(
                    f"NotebookLM: Поле '{field}' не задано, используется значение по умолчанию: {default_value}"
                )
        
        # Валидация timeout
        if not isinstance(validated['timeout'], (int, float)) or validated['timeout'] <= 0:
            warnings.append(
                f"NotebookLM: Невалидное значение timeout ({validated['timeout']}), "
                f"используется значение по умолчанию: {ConfigValidator.NOTEBOOKLM_DEFAULTS['timeout']}"
            )
            validated['timeout'] = ConfigValidator.NOTEBOOKLM_DEFAULTS['timeout']
        
        # Валидация max_retries
        if not isinstance(validated['max_retries'], int) or validated['max_retries'] < 0:
            warnings.append(
                f"NotebookLM: Невалидное значение max_retries ({validated['max_retries']}), "
                f"используется значение по умолчанию: {ConfigValidator.NOTEBOOKLM_DEFAULTS['max_retries']}"
            )
            validated['max_retries'] = ConfigValidator.NOTEBOOKLM_DEFAULTS['max_retries']
        
        # Валидация retry_delay_base
        if not isinstance(validated['retry_delay_base'], (int, float)) or validated['retry_delay_base'] <= 1:
            warnings.append(
                f"NotebookLM: Невалидное значение retry_delay_base ({validated['retry_delay_base']}), "
                f"используется значение по умолчанию: {ConfigValidator.NOTEBOOKLM_DEFAULTS['retry_delay_base']}"
            )
            validated['retry_delay_base'] = ConfigValidator.NOTEBOOKLM_DEFAULTS['retry_delay_base']
        
        # Валидация пути к файлу промптов
        if not os.path.exists(validated['prompts_config']):
            warnings.append(
                f"NotebookLM: Файл промптов не найден: {validated['prompts_config']}"
            )
        
        return validated, warnings
    
    @staticmethod
    def validate_automation_config(config: Dict[str, Any]) -> Tuple[Dict[str, Any], List[str]]:
        """
        Валидирует конфигурацию автоматизации
        
        Args:
            config: Словарь с конфигурацией автоматизации
        
        Returns:
            Кортеж (validated_config, warnings)
        """
        validated = config.copy()
        warnings = []
        
        # Проверка обязательных полей (только если автоматизация включена)
        if validated.get('enabled', False):
            for field in ConfigValidator.AUTOMATION_REQUIRED:
                if field not in validated or not validated[field]:
                    warnings.append(
                        f"Automation: Обязательное поле '{field}' не задано или пустое "
                        f"(требуется при enabled=true)"
                    )
        
        # Применение значений по умолчанию для опциональных полей
        for field, default_value in ConfigValidator.AUTOMATION_DEFAULTS.items():
            if field not in validated or validated[field] is None:
                validated[field] = default_value
                warnings.append(
                    f"Automation: Поле '{field}' не задано, используется значение по умолчанию: {default_value}"
                )
        
        # Валидация export_format
        if validated['export_format'] not in ConfigValidator.VALID_EXPORT_FORMATS:
            old_format = validated['export_format']
            validated['export_format'] = ConfigValidator.AUTOMATION_DEFAULTS['export_format']
            warnings.append(
                f"Automation: Невалидный формат экспорта ({old_format}), "
                f"используется значение по умолчанию: {ConfigValidator.AUTOMATION_DEFAULTS['export_format']}"
            )
        
        # Валидация schedule_time
        try:
            datetime.strptime(validated['schedule_time'], '%H:%M')
        except (ValueError, TypeError):
            warnings.append(
                f"Automation: Невалидный формат времени schedule_time ({validated['schedule_time']}), "
                f"используется значение по умолчанию: {ConfigValidator.AUTOMATION_DEFAULTS['schedule_time']}"
            )
            validated['schedule_time'] = ConfigValidator.AUTOMATION_DEFAULTS['schedule_time']
        
        # Валидация schedule_days
        if not isinstance(validated['schedule_days'], list):
            warnings.append(
                f"Automation: schedule_days должен быть списком, "
                f"используется значение по умолчанию: {ConfigValidator.AUTOMATION_DEFAULTS['schedule_days']}"
            )
            validated['schedule_days'] = ConfigValidator.AUTOMATION_DEFAULTS['schedule_days']
        else:
            invalid_days = [day for day in validated['schedule_days'] if day not in ConfigValidator.VALID_DAYS]
            if invalid_days:
                warnings.append(
                    f"Automation: Невалидные дни недели: {invalid_days}, "
                    f"используется значение по умолчанию: {ConfigValidator.AUTOMATION_DEFAULTS['schedule_days']}"
                )
                validated['schedule_days'] = ConfigValidator.AUTOMATION_DEFAULTS['schedule_days']
        
        # Валидация telegram_retry_delay
        if not isinstance(validated['telegram_retry_delay'], (int, float)) or validated['telegram_retry_delay'] < 0:
            warnings.append(
                f"Automation: Невалидное значение telegram_retry_delay ({validated['telegram_retry_delay']}), "
                f"используется значение по умолчанию: {ConfigValidator.AUTOMATION_DEFAULTS['telegram_retry_delay']}"
            )
            validated['telegram_retry_delay'] = ConfigValidator.AUTOMATION_DEFAULTS['telegram_retry_delay']
        
        # Валидация telegram_max_retries
        if not isinstance(validated['telegram_max_retries'], int) or validated['telegram_max_retries'] < 0:
            warnings.append(
                f"Automation: Невалидное значение telegram_max_retries ({validated['telegram_max_retries']}), "
                f"используется значение по умолчанию: {ConfigValidator.AUTOMATION_DEFAULTS['telegram_max_retries']}"
            )
            validated['telegram_max_retries'] = ConfigValidator.AUTOMATION_DEFAULTS['telegram_max_retries']
        
        # Валидация telegram_message_max_length
        if not isinstance(validated['telegram_message_max_length'], int) or validated['telegram_message_max_length'] <= 0:
            warnings.append(
                f"Automation: Невалидное значение telegram_message_max_length ({validated['telegram_message_max_length']}), "
                f"используется значение по умолчанию: {ConfigValidator.AUTOMATION_DEFAULTS['telegram_message_max_length']}"
            )
            validated['telegram_message_max_length'] = ConfigValidator.AUTOMATION_DEFAULTS['telegram_message_max_length']
        
        # Валидация export_dir
        if not os.path.exists(validated['export_dir']):
            warnings.append(
                f"Automation: Директория экспорта не существует: {validated['export_dir']}, будет создана автоматически"
            )
            os.makedirs(validated['export_dir'], exist_ok=True)
        
        return validated, warnings
    
    @staticmethod
    def validate_and_apply(config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Валидирует полную конфигурацию и применяет значения по умолчанию
        
        Args:
            config: Полный словарь конфигурации
        
        Returns:
            Валидированная конфигурация
        """
        validated_config = config.copy()
        all_warnings = []
        
        # Валидация NotebookLM
        if 'NOTEBOOKLM' in validated_config:
            validated_notebooklm, notebooklm_warnings = ConfigValidator.validate_notebooklm_config(
                validated_config['NOTEBOOKLM']
            )
            validated_config['NOTEBOOKLM'] = validated_notebooklm
            all_warnings.extend(notebooklm_warnings)
        else:
            logger.warning("Секция NOTEBOOKLM отсутствует в конфигурации, используются значения по умолчанию")
            validated_config['NOTEBOOKLM'] = ConfigValidator.NOTEBOOKLM_DEFAULTS.copy()
            validated_config['NOTEBOOKLM']['email'] = ''
            validated_config['NOTEBOOKLM']['password'] = ''
        
        # Валидация Automation
        if 'AUTOMATION' in validated_config:
            validated_automation, automation_warnings = ConfigValidator.validate_automation_config(
                validated_config['AUTOMATION']
            )
            validated_config['AUTOMATION'] = validated_automation
            all_warnings.extend(automation_warnings)
        else:
            logger.warning("Секция AUTOMATION отсутствует в конфигурации, используются значения по умолчанию")
            validated_config['AUTOMATION'] = ConfigValidator.AUTOMATION_DEFAULTS.copy()
            validated_config['AUTOMATION']['target_chat_id'] = ''
        
        # Логирование всех предупреждений
        for warning in all_warnings:
            logger.warning(warning)
        
        return validated_config
