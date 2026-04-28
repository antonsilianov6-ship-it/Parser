# -*- coding: utf-8 -*-
"""
Оркестратор процесса автоматизации NotebookLM Telegram
Координирует все этапы: экспорт данных, создание ноутбука, генерацию сводок, отправку в Telegram
"""

import asyncio
import json
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Tuple
from pathlib import Path

from src.notebooklm.client import NotebookLMClient, AuthenticationError
from src.notebooklm.file_manager import FileManager
from src.notebooklm.summary_generator import SummaryGenerator
from src.telegram.telegram_sender import TelegramSender
from src.core.unified_parser import UnifiedParser
from src.export.excel import ExcelExporter
from src.database.models import Database
from src.automation.models import AutomationStats, NotebookInfo, SummaryResult
from src.utils.error_handler import ErrorHandler
from src.utils.logger import setup_logger
from src.utils.scheduler import scheduler
from src.config import (
    CONFIG_FILE, 
    EXPORT_DIR, 
    get_database_config,
    get_telegram_config
)

logger = setup_logger(__name__)


class AutomationError(Exception):
    """Критическая ошибка автоматизации"""
    pass


class AutomationOrchestrator:
    """
    Оркестратор процесса автоматизации
    Координирует все этапы: экспорт, создание ноутбука, генерацию сводок, отправку
    """
    
    def __init__(self, config_path: str = CONFIG_FILE):
        """
        Инициализация оркестратора
        
        Args:
            config_path: Путь к файлу конфигурации
        
        Raises:
            AutomationError: При ошибке загрузки конфигурации
        """
        logger.info("=== Инициализация AutomationOrchestrator ===")
        
        self.config_path = config_path
        self.config: Dict[str, Any] = {}
        self.error_handler = ErrorHandler()
        
        # Загрузка конфигурации
        try:
            self._load_configuration()
            logger.info("Конфигурация успешно загружена")
        except Exception as e:
            error_msg = f"Ошибка загрузки конфигурации: {str(e)}"
            logger.error(error_msg)
            raise AutomationError(error_msg) from e
        
        # Инициализация компонентов
        try:
            self._initialize_components()
            logger.info("Все компоненты успешно инициализированы")
        except Exception as e:
            error_msg = f"Ошибка инициализации компонентов: {str(e)}"
            logger.error(error_msg)
            self.error_handler.log_error(e, {'operation': 'component_initialization'})
            raise AutomationError(error_msg) from e
        
        logger.info("=== AutomationOrchestrator готов к работе ===")
    
    def _load_configuration(self) -> None:
        """
        Загружает конфигурацию из файла
        
        Raises:
            FileNotFoundError: Если файл конфигурации не найден
            json.JSONDecodeError: Если файл содержит невалидный JSON
        """
        config_file = Path(self.config_path)
        
        if not config_file.exists():
            raise FileNotFoundError(f"Файл конфигурации не найден: {self.config_path}")
        
        with open(config_file, 'r', encoding='utf-8') as f:
            self.config = json.load(f)
        
        # Валидация обязательных секций
        self._validate_configuration()
    
    def _validate_configuration(self) -> None:
        """
        Валидирует конфигурацию на наличие обязательных полей
        
        Raises:
            AutomationError: При отсутствии обязательных полей
        """
        # Проверка секции NotebookLM
        if 'NOTEBOOKLM' not in self.config:
            raise AutomationError("Отсутствует секция 'NOTEBOOKLM' в конфигурации")
        
        notebooklm_config = self.config['NOTEBOOKLM']
        if not notebooklm_config.get('email') or not notebooklm_config.get('password'):
            raise AutomationError(
                "Отсутствуют учетные данные NotebookLM (email, password)"
            )
        
        # Проверка секции Automation
        if 'AUTOMATION' not in self.config:
            logger.warning(
                "Отсутствует секция 'AUTOMATION' в конфигурации. "
                "Используются значения по умолчанию"
            )
            self.config['AUTOMATION'] = {
                'target_chat_id': None,
                'schedule_time': '09:00',
                'timeout': 120,
                'max_retries': 3,
                'export_format': 'csv'
            }
        
        # Проверка ID целевого чата
        if not self.config['AUTOMATION'].get('target_chat_id'):
            logger.warning(
                "Не указан target_chat_id. "
                "Отправка в Telegram будет недоступна"
            )
        
        # Валидация значений с использованием значений по умолчанию
        automation_config = self.config['AUTOMATION']
        
        if automation_config.get('timeout', 0) <= 0:
            logger.warning(
                f"Невалидное значение timeout: {automation_config.get('timeout')}. "
                f"Используется значение по умолчанию: 120"
            )
            automation_config['timeout'] = 120
        
        if automation_config.get('max_retries', 0) < 0:
            logger.warning(
                f"Невалидное значение max_retries: {automation_config.get('max_retries')}. "
                f"Используется значение по умолчанию: 3"
            )
            automation_config['max_retries'] = 3
        
        if automation_config.get('export_format') not in ['csv', 'json']:
            logger.warning(
                f"Невалидное значение export_format: {automation_config.get('export_format')}. "
                f"Используется значение по умолчанию: csv"
            )
            automation_config['export_format'] = 'csv'
    
    def _initialize_components(self) -> None:
        """
        Инициализирует все компоненты системы
        
        Raises:
            AuthenticationError: При ошибке аутентификации NotebookLM
            Exception: При ошибке инициализации любого компонента
        """
        # NotebookLM Client
        notebooklm_credentials = {
            'email': self.config['NOTEBOOKLM']['email'],
            'password': self.config['NOTEBOOKLM']['password']
        }
        self.notebooklm_client = NotebookLMClient(notebooklm_credentials)
        logger.info("✓ NotebookLM Client инициализирован")
        
        # File Manager
        self.file_manager = FileManager(
            notebooklm_client=self.notebooklm_client,
            export_dir=EXPORT_DIR
        )
        logger.info("✓ File Manager инициализирован")
        
        # Summary Generator
        prompts_config_path = self.config.get('NOTEBOOKLM', {}).get(
            'prompts_config', 
            'config/prompts.json'
        )
        self.summary_generator = SummaryGenerator(
            notebooklm_client=self.notebooklm_client,
            config_path=prompts_config_path
        )
        logger.info("✓ Summary Generator инициализирован")
        
        # Telegram Sender
        telegram_config = get_telegram_config()
        self.telegram_sender = TelegramSender(telegram_config)
        logger.info("✓ Telegram Sender инициализирован")
        
        # UnifiedParser
        self.parser = UnifiedParser()
        logger.info("✓ Unified Parser инициализирован")
        
        # ExcelExporter
        self.excel_exporter = ExcelExporter(export_dir=EXPORT_DIR)
        logger.info("✓ Excel Exporter инициализирован")
        
        # Database
        db_config = get_database_config()
        self.database = Database(db_config['DB_PATH'])
        logger.info("✓ Database инициализирован")
    
    async def export_data(self, date_range: Tuple[datetime, datetime]) -> str:
        """
        Экспортирует данные из парсера (прямой поток без БД)
        
        Args:
            date_range: Диапазон дат для экспорта (start_date, end_date)
        
        Returns:
            Путь к экспортированному файлу
        
        Raises:
            AutomationError: При ошибке экспорта
        """
        from datetime import timezone
        
        start_date, end_date = date_range
        
        # Добавляем timezone к датам, если его нет
        if start_date.tzinfo is None:
            start_date = start_date.replace(tzinfo=timezone.utc)
        if end_date.tzinfo is None:
            end_date = end_date.replace(tzinfo=timezone.utc)
        
        stage_start_time = datetime.now()
        
        logger.info(
            f"=== ЭТАП 1: Парсинг и экспорт данных ===\n"
            f"Начало: {stage_start_time.strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"Период: {start_date.strftime('%Y-%m-%d')} - {end_date.strftime('%Y-%m-%d')}"
        )
        
        try:
            # Инициализация парсера
            logger.info("Инициализация парсера...")
            await self.parser.init_async()
            
            # Парсинг каналов за указанный период
            logger.info("Запуск парсинга каналов...")
            parsed_data = await self.parser.parse_channels()
            
            # Собираем все сообщения из всех каналов
            all_messages = []
            for channel, messages in parsed_data.items():
                for msg in messages:
                    # Фильтруем по диапазону дат
                    if start_date <= msg.date <= end_date:
                        all_messages.append(msg)
            
            logger.info(
                f"Найдено {len(all_messages)} сообщений за указанный период "
                f"(всего спарсено: {sum(len(msgs) for msgs in parsed_data.values())})"
            )
            
            if not all_messages:
                logger.warning("Нет сообщений для экспорта за указанный период")
                raise AutomationError(
                    f"Нет сообщений для экспорта за период "
                    f"{start_date.strftime('%Y-%m-%d')} - {end_date.strftime('%Y-%m-%d')}"
                )
            
            # Преобразование сообщений в формат для экспорта
            messages_for_export = []
            for msg in all_messages:
                # Извлекаем название канала из ссылки (формат: https://t.me/channel_name/message_id)
                channel_name = ''
                if msg.link:
                    parts = msg.link.split('/')
                    if len(parts) >= 4:
                        channel_name = parts[3]  # https://t.me/CHANNEL_NAME/message_id
                
                message_data = {
                    'date': msg.date.strftime('%Y-%m-%d %H:%M:%S'),
                    'channel': channel_name,
                    'link': msg.link,
                    'text': msg.text,
                    'title': msg.title if hasattr(msg, 'title') else '',
                    'previous_post': msg.previous_post if hasattr(msg, 'previous_post') else '',
                    'comments': msg.comments if hasattr(msg, 'comments') else []
                }
                messages_for_export.append(message_data)
            
            # Определение формата экспорта
            export_format = self.config['AUTOMATION'].get('export_format', 'csv')
            
            # Генерация имени файла
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"telegram_export_{timestamp}.{export_format}"
            
            # Экспорт в Excel (CSV)
            if export_format == 'csv':
                logger.info(f"Экспорт в Excel (CSV): {filename}")
                file_path = self.excel_exporter.export_to_excel(
                    messages_for_export, 
                    filename
                )
            else:
                # Экспорт в JSON
                logger.info(f"Экспорт в JSON: {filename}")
                file_path = self._export_to_json(messages_for_export, filename)
            
            if not file_path:
                raise AutomationError("Не удалось экспортировать данные")
            
            stage_duration = (datetime.now() - stage_start_time).total_seconds()
            logger.info(
                f"✓ Парсинг и экспорт завершены успешно\n"
                f"Время выполнения: {stage_duration:.2f} секунд\n"
                f"Файл: {file_path}\n"
                f"Сообщений обработано: {len(all_messages)}\n"
                f"Размер файла: {self._get_file_size(file_path)}"
            )
            
            return file_path
            
        except AutomationError:
            raise
        except Exception as e:
            error_msg = f"Ошибка парсинга и экспорта данных: {str(e)}"
            logger.error(error_msg)
            self.error_handler.log_error(e, {
                'operation': 'export_data',
                'date_range': (start_date.isoformat(), end_date.isoformat())
            })
            raise AutomationError(error_msg) from e
        finally:
            # Очистка ресурсов парсера
            try:
                await self.parser.cleanup()
            except Exception as e:
                logger.warning(f"Ошибка при очистке ресурсов парсера: {e}")
    
    def _export_to_json(self, messages: list, filename: str) -> str:
        """
        Экспортирует сообщения в JSON файл
        
        Args:
            messages: Список сообщений для экспорта
            filename: Имя файла
        
        Returns:
            Путь к созданному файлу
        """
        import os
        file_path = os.path.join(EXPORT_DIR, filename)
        
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(messages, f, ensure_ascii=False, indent=2)
            
            logger.info(f"JSON файл создан: {file_path}")
            return file_path
            
        except Exception as e:
            logger.error(f"Ошибка создания JSON файла: {str(e)}")
            return None
    
    async def process_summaries(self, file_path: str) -> Tuple[str, str]:
        """
        Обрабатывает файл и генерирует сводки
        
        Args:
            file_path: Путь к файлу с данными
        
        Returns:
            Кортеж (negative_summary, positive_summary)
        
        Raises:
            AutomationError: При ошибке обработки
        """
        stage_start_time = datetime.now()
        logger.info(
            f"=== ЭТАП 2: Обработка сводок ===\n"
            f"Начало: {stage_start_time.strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"Файл: {file_path}"
        )
        
        notebook_id = None
        
        try:
            # Используем NotebookLM клиент в контексте async with
            async with self.notebooklm_client:
                # Создание ноутбука с источником
                logger.info("Создание ноутбука NotebookLM с источником данных...")
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                notebook_title = f"Telegram Analysis {timestamp}"
                
                notebook_id, source_id = await self.file_manager.create_notebook_with_source(
                    file_path=file_path,
                    notebook_title=notebook_title
                )
                
                logger.info(
                    f"✓ Ноутбук создан\n"
                    f"Notebook ID: {notebook_id}\n"
                    f"Source ID: {source_id}"
                )
                
                # Параллельная генерация сводок
                logger.info("Генерация аналитических сводок (параллельно)...")
                timeout = self.config['AUTOMATION'].get('timeout', 120)
                
                negative_summary, positive_summary = await self.summary_generator.generate_summaries_parallel(
                    notebook_id=notebook_id,
                    timeout=timeout
                )
                
                stage_duration = (datetime.now() - stage_start_time).total_seconds()
                negative_word_count = len(negative_summary.split())
                positive_word_count = len(positive_summary.split())
                
                logger.info(
                    f"✓ Сводки сгенерированы\n"
                    f"Время выполнения: {stage_duration:.2f} секунд\n"
                    f"Негативная сводка:\n"
                    f"  - Символов: {len(negative_summary)}\n"
                    f"  - Слов: {negative_word_count}\n"
                    f"Позитивная сводка:\n"
                    f"  - Символов: {len(positive_summary)}\n"
                    f"  - Слов: {positive_word_count}"
                )
                
                return (negative_summary, positive_summary)
            
        except Exception as e:
            error_msg = f"Ошибка обработки сводок: {str(e)}"
            logger.error(error_msg)
            self.error_handler.log_error(e, {
                'operation': 'process_summaries',
                'file_path': file_path,
                'notebook_id': notebook_id
            })
            
            # Очистка ноутбука при ошибке
            if notebook_id:
                logger.info("Очистка ноутбука после ошибки...")
                # Нужно снова открыть контекст для очистки
                try:
                    async with self.notebooklm_client:
                        await self.file_manager.cleanup_notebook(notebook_id)
                except Exception as cleanup_error:
                    logger.warning(f"Ошибка при очистке ноутбука: {cleanup_error}")
            
            raise AutomationError(error_msg) from e
    
    async def send_results(
        self, 
        negative_summary: str, 
        positive_summary: str
    ) -> bool:
        """
        Отправляет результаты в Telegram
        
        Args:
            negative_summary: Негативная сводка
            positive_summary: Позитивная сводка
        
        Returns:
            True если отправка успешна, False иначе
        
        Raises:
            AutomationError: При критической ошибке отправки
        """
        stage_start_time = datetime.now()
        logger.info(
            f"=== ЭТАП 3: Отправка результатов в Telegram ===\n"
            f"Начало: {stage_start_time.strftime('%Y-%m-%d %H:%M:%S')}"
        )
        
        # Проверка наличия target_chat_id
        target_chat_id = self.config['AUTOMATION'].get('target_chat_id')
        
        if not target_chat_id:
            error_msg = "Не указан target_chat_id в конфигурации. Отправка невозможна"
            logger.error(error_msg)
            raise AutomationError(error_msg)
        
        try:
            # Форматирование сводок для Telegram
            logger.info("Форматирование сводок для Telegram...")
            formatted_negative = self.summary_generator.format_summary_for_telegram(
                negative_summary, 
                'negative'
            )
            formatted_positive = self.summary_generator.format_summary_for_telegram(
                positive_summary, 
                'positive'
            )
            
            # Отправка обеих сводок
            logger.info(f"Отправка сводок в чат {target_chat_id}...")
            negative_sent, positive_sent = await self.telegram_sender.send_summaries(
                chat_id=target_chat_id,
                negative_summary=formatted_negative,
                positive_summary=formatted_positive
            )
            
            # Проверка результатов отправки
            stage_duration = (datetime.now() - stage_start_time).total_seconds()
            
            if negative_sent and positive_sent:
                logger.info(
                    f"✓ Обе сводки успешно отправлены в Telegram\n"
                    f"Время выполнения: {stage_duration:.2f} секунд\n"
                    f"Целевой чат: {target_chat_id}\n"
                    f"Статус:\n"
                    f"  - Негативная сводка: ✓ Отправлена\n"
                    f"  - Позитивная сводка: ✓ Отправлена"
                )
                return True
            elif negative_sent:
                logger.warning(
                    f"⚠ Отправлена только негативная сводка\n"
                    f"Время выполнения: {stage_duration:.2f} секунд\n"
                    f"Статус:\n"
                    f"  - Негативная сводка: ✓ Отправлена\n"
                    f"  - Позитивная сводка: ✗ Ошибка"
                )
                return False
            elif positive_sent:
                logger.warning(
                    f"⚠ Отправлена только позитивная сводка\n"
                    f"Время выполнения: {stage_duration:.2f} секунд\n"
                    f"Статус:\n"
                    f"  - Негативная сводка: ✗ Ошибка\n"
                    f"  - Позитивная сводка: ✓ Отправлена"
                )
                return False
            else:
                logger.error(
                    f"✗ Не удалось отправить ни одну сводку\n"
                    f"Время выполнения: {stage_duration:.2f} секунд\n"
                    f"Статус:\n"
                    f"  - Негативная сводка: ✗ Ошибка\n"
                    f"  - Позитивная сводка: ✗ Ошибка"
                )
                return False
                
        except Exception as e:
            error_msg = f"Ошибка отправки результатов: {str(e)}"
            logger.error(error_msg)
            self.error_handler.log_error(e, {
                'operation': 'send_results',
                'target_chat_id': target_chat_id
            })
            raise AutomationError(error_msg) from e
    
    async def cleanup_resources(
        self, 
        notebook_id: Optional[str] = None, 
        temp_files: Optional[list] = None
    ) -> None:
        """
        Очищает временные ресурсы
        
        Args:
            notebook_id: ID ноутбука для удаления (опционально)
            temp_files: Список временных файлов для удаления (опционально)
        
        Note:
            Метод гарантирует выполнение даже при ошибках (graceful degradation)
        """
        stage_start_time = datetime.now()
        logger.info(
            f"=== ЭТАП 4: Очистка ресурсов ===\n"
            f"Начало: {stage_start_time.strftime('%Y-%m-%d %H:%M:%S')}"
        )
        
        # Очистка ноутбука
        if notebook_id:
            try:
                logger.info(f"Удаление ноутбука {notebook_id}...")
                await self.file_manager.cleanup_notebook(notebook_id)
                logger.info("✓ Ноутбук удален")
            except Exception as e:
                logger.warning(
                    f"Не удалось удалить ноутбук {notebook_id}: {str(e)}. "
                    f"Возможно, потребуется ручная очистка."
                )
                self.error_handler.log_error(e, {
                    'operation': 'cleanup_notebook',
                    'notebook_id': notebook_id
                })
        
        # Очистка временных файлов
        if temp_files:
            try:
                logger.info(f"Удаление {len(temp_files)} временных файлов...")
                self.file_manager.cleanup_temp_files(temp_files)
                logger.info("✓ Временные файлы удалены")
            except Exception as e:
                logger.warning(
                    f"Не удалось удалить временные файлы: {str(e)}. "
                    f"Возможно, потребуется ручная очистка."
                )
                self.error_handler.log_error(e, {
                    'operation': 'cleanup_temp_files',
                    'files_count': len(temp_files)
                })
        
        stage_duration = (datetime.now() - stage_start_time).total_seconds()
        logger.info(
            f"✓ Очистка ресурсов завершена\n"
            f"Время выполнения: {stage_duration:.2f} секунд"
        )
    
    async def run_automation(
        self, 
        date_range: Optional[Tuple[datetime, datetime]] = None
    ) -> Dict[str, Any]:
        """
        Выполняет полный цикл автоматизации
        
        Args:
            date_range: Опциональный диапазон дат для парсинга (start_date, end_date)
                       Если не указан, используется get_date_range_for_schedule()
        
        Returns:
            Словарь со статистикой выполнения
        
        Raises:
            AutomationError: При критических ошибках
        """
        logger.info("=" * 60)
        logger.info("=== ЗАПУСК АВТОМАТИЗАЦИИ NOTEBOOKLM TELEGRAM ===")
        logger.info("=" * 60)
        
        # Создание объекта статистики
        stats = AutomationStats(start_time=datetime.now())
        
        # Определение диапазона дат
        if date_range is None:
            date_range = self.get_date_range_for_schedule()
        
        start_date, end_date = date_range
        logger.info(
            f"Период анализа: {start_date.strftime('%Y-%m-%d')} - "
            f"{end_date.strftime('%Y-%m-%d')}"
        )
        
        file_path = None
        notebook_id = None
        negative_summary = None
        positive_summary = None
        
        try:
            # ЭТАП 1: Экспорт данных
            logger.info("\n" + "=" * 60)
            stage_start = datetime.now()
            logger.info(f"[ЭТАП 1] Начало экспорта данных: {stage_start.strftime('%Y-%m-%d %H:%M:%S')}")
            
            file_path = await self.export_data(date_range)
            stats.messages_processed = self._count_messages_in_file(file_path)
            
            stage_duration = (datetime.now() - stage_start).total_seconds()
            logger.info(
                f"[ЭТАП 1] Экспорт завершен за {stage_duration:.2f} секунд\n"
                f"  - Обработано сообщений: {stats.messages_processed}\n"
                f"  - Файл: {file_path}"
            )
            
            # ЭТАП 2: Обработка сводок
            logger.info("\n" + "=" * 60)
            stage_start = datetime.now()
            logger.info(f"[ЭТАП 2] Начало обработки сводок: {stage_start.strftime('%Y-%m-%d %H:%M:%S')}")
            
            negative_summary, positive_summary = await self.process_summaries(file_path)
            
            # Сохранение информации о сводках в статистику
            stats.negative_summary_length = len(negative_summary)
            stats.positive_summary_length = len(positive_summary)
            
            stage_duration = (datetime.now() - stage_start).total_seconds()
            logger.info(
                f"[ЭТАП 2] Обработка сводок завершена за {stage_duration:.2f} секунд\n"
                f"  - Негативная сводка: {stats.negative_summary_length} символов "
                f"({len(negative_summary.split())} слов)\n"
                f"  - Позитивная сводка: {stats.positive_summary_length} символов "
                f"({len(positive_summary.split())} слов)"
            )
            
            # Извлечение notebook_id из контекста (сохраняем для очистки)
            # Получаем notebook_id из последнего созданного ноутбука
            # (в реальности он создается в process_summaries)
            
            # ЭТАП 3: Отправка результатов
            logger.info("\n" + "=" * 60)
            stage_start = datetime.now()
            logger.info(f"[ЭТАП 3] Начало отправки в Telegram: {stage_start.strftime('%Y-%m-%d %H:%M:%S')}")
            
            telegram_sent = await self.send_results(negative_summary, positive_summary)
            stats.telegram_sent = telegram_sent
            
            stage_duration = (datetime.now() - stage_start).total_seconds()
            logger.info(
                f"[ЭТАП 3] Отправка завершена за {stage_duration:.2f} секунд\n"
                f"  - Статус: {'✓ Успешно' if telegram_sent else '✗ Ошибка'}"
            )
            
            # Завершение
            stats.end_time = datetime.now()
            
            logger.info("\n" + "=" * 60)
            logger.info("=== АВТОМАТИЗАЦИЯ ЗАВЕРШЕНА УСПЕШНО ===")
            logger.info("=" * 60)
            logger.info(
                f"Общая статистика:\n"
                f"  - Длительность: {stats.duration_seconds:.2f} секунд\n"
                f"  - Обработано сообщений: {stats.messages_processed}\n"
                f"  - Негативная сводка: {stats.negative_summary_length} символов "
                f"({len(negative_summary.split())} слов)\n"
                f"  - Позитивная сводка: {stats.positive_summary_length} символов "
                f"({len(positive_summary.split())} слов)\n"
                f"  - Отправлено в Telegram: {'✓ Да' if stats.telegram_sent else '✗ Нет'}"
            )
            logger.info("=" * 60)
            
            return stats.to_dict()
            
        except AutomationError as e:
            # Критическая ошибка автоматизации
            stats.errors.append(str(e))
            stats.end_time = datetime.now()
            
            logger.error("\n" + "=" * 60)
            logger.error("=== АВТОМАТИЗАЦИЯ ЗАВЕРШЕНА С ОШИБКОЙ ===")
            logger.error("=" * 60)
            logger.error(
                f"Детали ошибки:\n"
                f"  - Ошибка: {str(e)}\n"
                f"  - Длительность до ошибки: {stats.duration_seconds:.2f} секунд\n"
                f"  - Обработано сообщений: {stats.messages_processed}\n"
                f"  - Негативная сводка: {stats.negative_summary_length} символов\n"
                f"  - Позитивная сводка: {stats.positive_summary_length} символов"
            )
            logger.error("=" * 60)
            
            # Отправка уведомления об ошибке в Telegram
            await self._send_error_notification(str(e))
            
            raise
            
        except Exception as e:
            # Неожиданная ошибка
            error_msg = f"Неожиданная ошибка автоматизации: {str(e)}"
            stats.errors.append(error_msg)
            stats.end_time = datetime.now()
            
            logger.error("\n" + "=" * 60)
            logger.error("=== АВТОМАТИЗАЦИЯ ЗАВЕРШЕНА С НЕОЖИДАННОЙ ОШИБКОЙ ===")
            logger.error("=" * 60)
            logger.error(
                f"Детали ошибки:\n"
                f"  - Ошибка: {error_msg}\n"
                f"  - Длительность до ошибки: {stats.duration_seconds:.2f} секунд\n"
                f"  - Обработано сообщений: {stats.messages_processed}\n"
                f"  - Негативная сводка: {stats.negative_summary_length} символов\n"
                f"  - Позитивная сводка: {stats.positive_summary_length} символов",
                exc_info=True
            )
            logger.error("=" * 60)
            
            self.error_handler.log_error(e, {
                'operation': 'run_automation',
                'date_range': (start_date.isoformat(), end_date.isoformat()),
                'messages_processed': stats.messages_processed,
                'duration_seconds': stats.duration_seconds
            })
            
            # Отправка уведомления об ошибке в Telegram
            await self._send_error_notification(error_msg)
            
            raise AutomationError(error_msg) from e
            
        finally:
            # ЭТАП 4: Очистка ресурсов (выполняется всегда)
            logger.info("\n" + "=" * 60)
            temp_files = [file_path] if file_path else []
            await self.cleanup_resources(
                notebook_id=notebook_id,
                temp_files=temp_files
            )
    
    def _count_messages_in_file(self, file_path: str) -> int:
        """
        Подсчитывает количество сообщений в экспортированном файле
        
        Args:
            file_path: Путь к файлу
        
        Returns:
            Количество сообщений
        """
        try:
            if file_path.endswith('.json'):
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return len(data) if isinstance(data, list) else 0
            elif file_path.endswith('.xlsx') or file_path.endswith('.csv'):
                import pandas as pd
                df = pd.read_excel(file_path) if file_path.endswith('.xlsx') else pd.read_csv(file_path)
                return len(df)
            else:
                return 0
        except Exception as e:
            logger.warning(f"Не удалось подсчитать сообщения в файле: {str(e)}")
            return 0
    
    def _get_file_size(self, file_path: str) -> str:
        """
        Получает размер файла в читаемом формате
        
        Args:
            file_path: Путь к файлу
        
        Returns:
            Размер файла в формате "X.XX MB" или "X.XX KB"
        """
        try:
            import os
            size_bytes = os.path.getsize(file_path)
            
            if size_bytes >= 1024 * 1024:  # >= 1 MB
                size_mb = size_bytes / (1024 * 1024)
                return f"{size_mb:.2f} MB"
            elif size_bytes >= 1024:  # >= 1 KB
                size_kb = size_bytes / 1024
                return f"{size_kb:.2f} KB"
            else:
                return f"{size_bytes} bytes"
        except Exception as e:
            logger.warning(f"Не удалось получить размер файла: {str(e)}")
            return "неизвестно"
    
    async def _send_error_notification(self, error_message: str) -> None:
        """
        Отправляет уведомление об ошибке в Telegram
        
        Args:
            error_message: Описание ошибки
        """
        target_chat_id = self.config['AUTOMATION'].get('target_chat_id')
        
        if not target_chat_id:
            logger.warning("Не указан target_chat_id. Уведомление об ошибке не отправлено")
            return
        
        try:
            logger.info("Отправка уведомления об ошибке в Telegram...")
            await self.telegram_sender.send_error_notification(
                chat_id=target_chat_id,
                error_message=error_message
            )
            logger.info("✓ Уведомление об ошибке отправлено")
        except Exception as e:
            logger.error(f"Не удалось отправить уведомление об ошибке: {str(e)}")
    
    def get_date_range_for_schedule(self) -> Tuple[datetime, datetime]:
        """
        Определяет диапазон дат на основе текущего дня недели
        
        Логика:
        - Понедельник: пятница-воскресенье (последние 3 дня)
        - Вторник-пятница: предыдущий день
        
        Returns:
            Кортеж (start_date, end_date)
        """
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        weekday = today.weekday()  # 0 = понедельник, 6 = воскресенье
        
        if weekday == 0:  # Понедельник
            # Пятница-воскресенье (последние 3 дня)
            start_date = today - timedelta(days=3)  # Пятница
            end_date = today - timedelta(days=1)    # Воскресенье
            logger.info(
                f"Понедельник: анализ выходных (пятница-воскресенье)\n"
                f"Период: {start_date.strftime('%Y-%m-%d')} - {end_date.strftime('%Y-%m-%d')}"
            )
        else:  # Вторник-пятница
            # Предыдущий день
            start_date = today - timedelta(days=1)
            end_date = today - timedelta(days=1)
            logger.info(
                f"Будний день: анализ предыдущего дня\n"
                f"Период: {start_date.strftime('%Y-%m-%d')}"
            )
        
        # Устанавливаем время для end_date на конец дня
        end_date = end_date.replace(hour=23, minute=59, second=59, microsecond=999999)
        
        return (start_date, end_date)
    
    def setup_schedule(self) -> None:
        """
        Настраивает автоматический запуск по расписанию
        
        Использует существующий Scheduler для запуска автоматизации
        в будние дни в настраиваемое время
        """
        logger.info("=== Настройка расписания автоматизации ===")
        
        # Получение времени запуска из конфигурации
        schedule_time = self.config['AUTOMATION'].get('schedule_time', '09:00')
        
        # Валидация формата времени
        try:
            datetime.strptime(schedule_time, '%H:%M')
        except ValueError:
            logger.warning(
                f"Невалидный формат времени: {schedule_time}. "
                f"Используется значение по умолчанию: 09:00"
            )
            schedule_time = '09:00'
        
        # Создание функции для запуска автоматизации
        def run_scheduled_automation():
            """Обертка для запуска автоматизации по расписанию"""
            current_day = datetime.now().strftime('%A')
            logger.info(
                f"\n{'=' * 60}\n"
                f"=== ЗАПУСК ПО РАСПИСАНИЮ ===\n"
                f"Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"День недели: {current_day}\n"
                f"{'=' * 60}"
            )
            
            # Проверка, что сегодня будний день (понедельник-пятница)
            weekday = datetime.now().weekday()
            if weekday >= 5:  # Суббота (5) или воскресенье (6)
                logger.info(
                    f"Сегодня выходной день ({current_day}). "
                    f"Автоматизация не запускается."
                )
                return
            
            # Запуск автоматизации
            try:
                asyncio.run(self.run_automation())
            except Exception as e:
                logger.error(f"Ошибка при запуске автоматизации по расписанию: {str(e)}")
                self.error_handler.log_error(e, {
                    'operation': 'scheduled_automation',
                    'schedule_time': schedule_time
                })
        
        # Добавление задачи в планировщик
        scheduler.add_daily_task(
            name='notebooklm_automation',
            func=run_scheduled_automation,
            time_str=schedule_time
        )
        
        logger.info(
            f"✓ Расписание настроено\n"
            f"Время запуска: {schedule_time} (будние дни)\n"
            f"Следующий запуск: {self._get_next_run_time(schedule_time)}"
        )
        
        # Запуск планировщика
        scheduler.start()
        logger.info("✓ Планировщик запущен")
    
    def _get_next_run_time(self, schedule_time: str) -> str:
        """
        Вычисляет время следующего запуска
        
        Args:
            schedule_time: Время запуска в формате HH:MM
        
        Returns:
            Строка с датой и временем следующего запуска
        """
        now = datetime.now()
        hour, minute = map(int, schedule_time.split(':'))
        
        # Создаем datetime для сегодняшнего запуска
        today_run = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        
        # Если время уже прошло сегодня, берем завтрашний день
        if now >= today_run:
            next_run = today_run + timedelta(days=1)
        else:
            next_run = today_run
        
        # Пропускаем выходные
        while next_run.weekday() >= 5:  # Суббота или воскресенье
            next_run += timedelta(days=1)
        
        return next_run.strftime('%Y-%m-%d %H:%M:%S')
