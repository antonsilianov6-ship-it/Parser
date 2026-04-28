# -*- coding: utf-8 -*-
"""Генератор аналитических сводок на основе NotebookLM"""

import asyncio
import json
from pathlib import Path
from typing import Dict, Any, Tuple, Optional
from src.notebooklm.client import NotebookLMClient, NotebookLMAPIError
from src.utils.logger import setup_logger

logger = setup_logger(__name__)


class PromptValidationError(Exception):
    """Ошибка валидации промпта"""
    pass


class SummaryGenerator:
    """Генератор аналитических сводок"""
    
    def __init__(
        self, 
        notebooklm_client: NotebookLMClient,
        config_path: str = "config/prompts.json"
    ):
        """
        Инициализация генератора
        
        Args:
            notebooklm_client: Клиент NotebookLM
            config_path: Путь к файлу с промптами
        
        Raises:
            PromptValidationError: При невалидных промптах
        """
        self.client = notebooklm_client
        self.config_path = config_path
        self.prompts: Dict[str, Any] = {}
        self.defaults: Dict[str, Any] = {}
        
        # Загрузка промптов при инициализации
        try:
            self.prompts, self.defaults = self.load_prompts(config_path)
            logger.info(f"Промпты успешно загружены из {config_path}")
        except Exception as e:
            logger.warning(
                f"Не удалось загрузить промпты из {config_path}: {str(e)}. "
                f"Используются промпты по умолчанию"
            )
            self._load_default_prompts()
    
    def _load_default_prompts(self) -> None:
        """Загружает промпты по умолчанию"""
        self.prompts = {
            'negative': {
                'template': (
                    'Проанализируй сообщения и выдели основные жалобы, '
                    'проблемы и негативные отзывы. Структурируй ответ по категориям.'
                ),
                'required_fields': ['template'],
                'variables': []
            },
            'positive': {
                'template': (
                    'Проанализируй сообщения и выдели основные похвалы, '
                    'положительные отзывы и плюсы. Структурируй ответ по категориям.'
                ),
                'required_fields': ['template'],
                'variables': []
            }
        }
        self.defaults = {
            'timeout': 120,
            'max_retries': 3,
            'retry_delay_base': 2
        }
        logger.info("Загружены промпты по умолчанию")
    
    def load_prompts(self, config_path: str) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """
        Загружает промпты из конфигурационного файла
        
        Args:
            config_path: Путь к файлу конфигурации
        
        Returns:
            Кортеж (промпты, настройки по умолчанию)
        
        Raises:
            PromptValidationError: При невалидных промптах
            FileNotFoundError: Если файл не найден
        """
        config_file = Path(config_path)
        
        if not config_file.exists():
            raise FileNotFoundError(f"Файл конфигурации не найден: {config_path}")
        
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
        except json.JSONDecodeError as e:
            raise PromptValidationError(
                f"Невалидный JSON в файле {config_path}: {str(e)}"
            ) from e
        
        # Валидация структуры конфигурации
        if 'prompts' not in config:
            raise PromptValidationError(
                "Отсутствует обязательное поле 'prompts' в конфигурации"
            )
        
        prompts = config['prompts']
        
        # Валидация негативного промпта
        if 'negative' not in prompts:
            raise PromptValidationError(
                "Отсутствует обязательный промпт 'negative'"
            )
        if not self.validate_prompt(prompts['negative']):
            raise PromptValidationError(
                "Невалидная структура негативного промпта"
            )
        
        # Валидация позитивного промпта
        if 'positive' not in prompts:
            raise PromptValidationError(
                "Отсутствует обязательный промпт 'positive'"
            )
        if not self.validate_prompt(prompts['positive']):
            raise PromptValidationError(
                "Невалидная структура позитивного промпта"
            )
        
        # Загрузка настроек по умолчанию
        defaults = config.get('defaults', {
            'timeout': 120,
            'max_retries': 3,
            'retry_delay_base': 2
        })
        
        # Валидация настроек по умолчанию
        if defaults.get('timeout', 0) <= 0:
            logger.warning(
                f"Невалидное значение timeout: {defaults.get('timeout')}. "
                f"Используется значение по умолчанию: 120"
            )
            defaults['timeout'] = 120
        
        if defaults.get('max_retries', 0) <= 0:
            logger.warning(
                f"Невалидное значение max_retries: {defaults.get('max_retries')}. "
                f"Используется значение по умолчанию: 3"
            )
            defaults['max_retries'] = 3
        
        if defaults.get('retry_delay_base', 0) <= 0:
            logger.warning(
                f"Невалидное значение retry_delay_base: {defaults.get('retry_delay_base')}. "
                f"Используется значение по умолчанию: 2"
            )
            defaults['retry_delay_base'] = 2
        
        return prompts, defaults
    
    def validate_prompt(self, prompt: Dict[str, Any]) -> bool:
        """
        Валидирует структуру промпта
        
        Args:
            prompt: Словарь с промптом
        
        Returns:
            True если промпт валиден, False иначе
        """
        # Проверка наличия обязательного поля 'template'
        if 'template' not in prompt:
            logger.error("Отсутствует обязательное поле 'template' в промпте")
            return False
        
        # Проверка, что template не пустой
        if not prompt['template'] or not isinstance(prompt['template'], str):
            logger.error("Поле 'template' должно быть непустой строкой")
            return False
        
        # Проверка наличия поля 'required_fields'
        if 'required_fields' not in prompt:
            logger.error("Отсутствует обязательное поле 'required_fields' в промпте")
            return False
        
        # Проверка, что required_fields - это список
        if not isinstance(prompt['required_fields'], list):
            logger.error("Поле 'required_fields' должно быть списком")
            return False
        
        # Проверка, что 'template' указан в required_fields
        if 'template' not in prompt['required_fields']:
            logger.error("Поле 'template' должно быть в списке required_fields")
            return False
        
        # Проверка наличия поля 'variables'
        if 'variables' not in prompt:
            logger.error("Отсутствует обязательное поле 'variables' в промпте")
            return False
        
        # Проверка, что variables - это список
        if not isinstance(prompt['variables'], list):
            logger.error("Поле 'variables' должно быть списком")
            return False
        
        return True
    
    async def generate_negative_summary(
        self, 
        notebook_id: str,
        timeout: Optional[int] = None
    ) -> str:
        """
        Генерирует негативную аналитическую сводку
        
        Args:
            notebook_id: ID ноутбука с данными
            timeout: Таймаут в секундах (если None, используется из конфигурации)
        
        Returns:
            Текст негативной сводки
        
        Raises:
            TimeoutError: При превышении таймаута
            NotebookLMAPIError: При ошибке API
        """
        if timeout is None:
            timeout = self.defaults.get('timeout', 120)
        
        prompt_template = self.prompts['negative']['template']
        
        logger.info(f"Генерация негативной сводки для ноутбука {notebook_id}...")
        
        try:
            response = await self.client.query_notebook(
                notebook_id=notebook_id,
                prompt=prompt_template,
                timeout=timeout
            )
            
            logger.info(
                f"Негативная сводка успешно сгенерирована "
                f"(длина: {len(response)} символов)"
            )
            return response
            
        except (TimeoutError, NotebookLMAPIError) as e:
            logger.error(f"Ошибка генерации негативной сводки: {str(e)}")
            raise
    
    async def generate_positive_summary(
        self, 
        notebook_id: str,
        timeout: Optional[int] = None
    ) -> str:
        """
        Генерирует позитивную аналитическую сводку
        
        Args:
            notebook_id: ID ноутбука с данными
            timeout: Таймаут в секундах (если None, используется из конфигурации)
        
        Returns:
            Текст позитивной сводки
        
        Raises:
            TimeoutError: При превышении таймаута
            NotebookLMAPIError: При ошибке API
        """
        if timeout is None:
            timeout = self.defaults.get('timeout', 120)
        
        prompt_template = self.prompts['positive']['template']
        
        logger.info(f"Генерация позитивной сводки для ноутбука {notebook_id}...")
        
        try:
            response = await self.client.query_notebook(
                notebook_id=notebook_id,
                prompt=prompt_template,
                timeout=timeout
            )
            
            logger.info(
                f"Позитивная сводка успешно сгенерирована "
                f"(длина: {len(response)} символов)"
            )
            return response
            
        except (TimeoutError, NotebookLMAPIError) as e:
            logger.error(f"Ошибка генерации позитивной сводки: {str(e)}")
            raise
    
    async def generate_summaries_parallel(
        self, 
        notebook_id: str,
        timeout: Optional[int] = None
    ) -> Tuple[str, str]:
        """
        Генерирует обе сводки параллельно
        
        Args:
            notebook_id: ID ноутбука с данными
            timeout: Таймаут в секундах (если None, используется из конфигурации)
        
        Returns:
            Кортеж (negative_summary, positive_summary)
        
        Raises:
            Exception: При ошибке генерации любой из сводок
        """
        logger.info(
            f"Запуск параллельной генерации сводок для ноутбука {notebook_id}..."
        )
        
        try:
            # Запуск обеих генераций параллельно
            results = await asyncio.gather(
                self.generate_negative_summary(notebook_id, timeout),
                self.generate_positive_summary(notebook_id, timeout),
                return_exceptions=True
            )
            
            negative_summary = results[0]
            positive_summary = results[1]
            
            # Проверка на ошибки в негативной сводке
            if isinstance(negative_summary, Exception):
                logger.error(
                    f"Ошибка генерации негативной сводки: {str(negative_summary)}"
                )
                raise negative_summary
            
            # Проверка на ошибки в позитивной сводке
            if isinstance(positive_summary, Exception):
                logger.error(
                    f"Ошибка генерации позитивной сводки: {str(positive_summary)}"
                )
                raise positive_summary
            
            logger.info(
                f"Обе сводки успешно сгенерированы параллельно "
                f"(негативная: {len(negative_summary)} символов, "
                f"позитивная: {len(positive_summary)} символов)"
            )
            
            return negative_summary, positive_summary
            
        except Exception as e:
            logger.error(f"Ошибка параллельной генерации сводок: {str(e)}")
            raise
    
    def format_summary_for_telegram(
        self, 
        summary: str, 
        summary_type: str
    ) -> str:
        """
        Форматирует сводку для отправки в Telegram
        
        Args:
            summary: Текст сводки
            summary_type: Тип сводки ('negative' или 'positive')
        
        Returns:
            Отформатированный текст с заголовком
        """
        # Определение заголовка и эмодзи в зависимости от типа
        if summary_type.lower() == 'negative':
            emoji = '⚠️'
            title = 'НЕГАТИВНАЯ СВОДКА'
        elif summary_type.lower() == 'positive':
            emoji = '✅'
            title = 'ПОЗИТИВНАЯ СВОДКА'
        else:
            emoji = '📊'
            title = 'АНАЛИТИЧЕСКАЯ СВОДКА'
        
        # Форматирование сообщения
        formatted_message = (
            f"{emoji} **{title}** {emoji}\n"
            f"{'=' * 40}\n\n"
            f"{summary}\n\n"
            f"{'=' * 40}"
        )
        
        logger.debug(
            f"Сводка отформатирована для Telegram "
            f"(тип: {summary_type}, длина: {len(formatted_message)} символов)"
        )
        
        return formatted_message
