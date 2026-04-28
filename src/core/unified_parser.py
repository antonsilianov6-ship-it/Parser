# -*- coding: utf-8 -*-
"""Унифицированный парсер сообщений из Telegram-каналов"""

import asyncio
from typing import List, Dict, Set, Optional
from datetime import datetime
from telethon.errors import ChatAdminRequiredError, UserNotParticipantError, ChatWriteForbiddenError
from src.telegram.connection_manager import ConnectionManager
from src.telegram.message_fetcher import MessageFetcher, Message
from src.telegram.comment_fetcher import CommentFetcher
from src.telegram.source_detector import SourceDetector
from src.telegram.topic_manager import TopicManager
from src.cache.cache_manager import CacheManager
from src.database.models import Database, Message as DBMessage
from src.export.google_docs import GoogleDocsExporter
from src.utils.error_handler import ErrorHandler
from src.utils.channels_loader import load_channels_as_set
from src.utils.date_utils import DateUtils
from src.utils.logger import setup_logger
from src.utils.scheduler import scheduler
from src.utils.notifications import notification_manager
from src.config import get_parser_config, get_database_config, get_google_config, DATABASE_CONFIG

logger = setup_logger(__name__)


class UnifiedParser:
    """Унифицированный парсер с функциональностью MessageParser и EnhancedParser"""
    
    def __init__(self):
        logger.info("Инициализация UnifiedParser")
        self.connection_manager = ConnectionManager()
        self.cache_manager = CacheManager()
        self.error_handler = ErrorHandler()
        self.db = Database(DATABASE_CONFIG['DB_PATH'])
        self.docs_exporter = GoogleDocsExporter()
        self.message_fetcher: Optional[MessageFetcher] = None
        self.comment_fetcher: Optional[CommentFetcher] = None
        self.topic_manager: Optional[TopicManager] = None
        self.processed_links: Set[str] = set()
        self.stats = {
            'total_messages': 0, 'total_errors': 0, 'channels_processed': 0,
            'start_time': None, 'end_time': None
        }
        self.is_running = False
    
    async def init_async(self) -> None:
        """Асинхронная инициализация парсера"""
        logger.info("Асинхронная инициализация UnifiedParser")
        try:
            await self.connection_manager.connect()
            self.topic_manager = TopicManager(self.connection_manager)
            self.message_fetcher = MessageFetcher(
                self.connection_manager, self.cache_manager, self.error_handler, self.topic_manager
            )
            self.comment_fetcher = CommentFetcher(self.connection_manager)
            await self.cache_manager.load_async()
            self.processed_links = self.cache_manager.get_processed_links()
            logger.info(f"Загружено {len(self.processed_links)} ссылок из кэша")
        except Exception as e:
            logger.error(f"Ошибка инициализации: {e}", exc_info=True)
            raise
    
    async def parse_channels(self, channel_links: Optional[Set[str]] = None) -> Dict[str, List[Message]]:
        """Парсинг списка каналов, чатов и форум-чатов с автоматическим определением типа"""
        logger.info("=== НАЧАЛО парсинга источников ===")
        self.stats['start_time'] = datetime.now()
        self.is_running = True
        
        try:
            if channel_links is None:
                channel_links = load_channels_as_set()
            if not channel_links:
                logger.error("Список источников пуст")
                return {}
            
            logger.info(f"Парсинг {len(channel_links)} источников")
            parser_config = get_parser_config()
            days = parser_config.get('DAYS_FOR_EXPORT', 3)
            start_date, end_date = DateUtils.get_date_range(days)
            
            messages_dict = {}
            client = self.connection_manager.get_client()
            
            for link in channel_links:
                try:
                    # Получаем entity для определения типа источника
                    logger.info(f"Обработка источника: {link}")
                    
                    try:
                        entity = await client.get_entity(link)
                        self.cache_manager.save_entity(link, entity)
                    except Exception as e:
                        logger.error(f"Не удалось получить entity для {link}: {e}")
                        # Обрабатываем ошибки доступа к чатам
                        if isinstance(e, (ChatAdminRequiredError, UserNotParticipantError, ChatWriteForbiddenError)):
                            self.error_handler.handle_chat_access_error(e, link)
                        else:
                            self.error_handler.log_error(e, {'operation': 'get_entity', 'link': link})
                        self.stats['total_errors'] += 1
                        continue
                    
                    # Определяем тип источника
                    source_type = SourceDetector.detect_source_type(entity)
                    logger.info(f"Источник {link} определен как: {source_type}")
                    
                    # Парсим в зависимости от типа источника
                    messages = []
                    
                    if source_type == 'forum_chat':
                        # Парсинг форум-чата с топиками
                        logger.info(f"Парсинг форум-чата: {link}")
                        messages = await self.message_fetcher.fetch_forum_chat_messages(
                            link, start_date, end_date
                        )
                    elif source_type == 'chat':
                        # Парсинг обычного чата
                        logger.info(f"Парсинг чата: {link}")
                        messages = await self.message_fetcher.fetch_chat_messages(
                            link, start_date, end_date
                        )
                    else:  # source_type == 'channel'
                        # Парсинг канала (существующая логика)
                        logger.info(f"Парсинг канала: {link}")
                        messages = await self.message_fetcher.fetch_channel_messages(
                            link, start_date, end_date
                        )
                    
                    if messages:
                        channel_name = link.split('/')[-1]
                        messages_dict[channel_name] = messages
                        self.stats['channels_processed'] += 1
                        await self._save_messages_to_db(messages, channel_name)
                        self.db.add_parse_stats(channel_name, len(messages))
                        notification_manager.notify_parse_complete(channel_name, len(messages))
                        logger.info(f"Успешно обработано {len(messages)} сообщений из {link}")
                    else:
                        logger.warning(f"Не получено сообщений из {link}")
                    
                    # Задержка между источниками
                    await asyncio.sleep(2)
                    
                except Exception as e:
                    logger.error(f"Ошибка при обработке источника {link}: {e}", exc_info=True)
                    # Обрабатываем ошибки доступа к чатам
                    if isinstance(e, (ChatAdminRequiredError, UserNotParticipantError, ChatWriteForbiddenError)):
                        self.error_handler.handle_chat_access_error(e, link)
                    else:
                        self.error_handler.log_error(e, {'operation': 'parse_source', 'link': link})
                    self.stats['total_errors'] += 1
                    # Продолжаем парсинг других источников
                    continue
            
            logger.info(f"Получены сообщения из {len(messages_dict)} источников")
            self.stats['end_time'] = datetime.now()
            self.is_running = False
            
            # Логируем статистику после завершения парсинга
            stats = self.get_statistics()
            logger.info("=== ИТОГОВАЯ СТАТИСТИКА ПАРСИНГА ===")
            logger.info(f"Обработано источников: {self.stats['channels_processed']}")
            logger.info(f"Всего сообщений: {self.stats['total_messages']}")
            logger.info(f"Ошибок: {self.stats['total_errors']}")
            if 'duration_seconds' in stats['current_session']:
                logger.info(f"Длительность: {stats['current_session']['duration_seconds']:.2f} секунд")
            
            logger.info("=== КОНЕЦ парсинга источников ===")
            return messages_dict
            
        except Exception as e:
            self.error_handler.log_error(e, {'operation': 'parse_channels'})
            self.stats['total_errors'] += 1
            self.is_running = False
            logger.error(f"Ошибка парсинга: {e}", exc_info=True)
            return {}
    
    async def parse_channel(self, channel_link: str, retry_count: int = 3) -> List[Message]:
        """Парсинг одного источника (канал/чат/форум-чат) с автоматическим определением типа и retry логикой"""
        logger.info(f"Парсинг {channel_link} (max {retry_count} попыток)")
        
        for attempt in range(1, retry_count + 1):
            try:
                days = get_parser_config().get('DAYS_FOR_EXPORT', 3)
                start_date, end_date = DateUtils.get_date_range(days)
                
                # Получаем entity и определяем тип источника
                client = self.connection_manager.get_client()
                
                try:
                    entity = await client.get_entity(channel_link)
                    self.cache_manager.save_entity(channel_link, entity)
                except Exception as e:
                    logger.error(f"Не удалось получить entity для {channel_link}: {e}")
                    self.error_handler.handle_chat_access_error(e, channel_link)
                    return []
                
                # Определяем тип источника
                source_type = SourceDetector.detect_source_type(entity)
                logger.info(f"Источник {channel_link} определен как: {source_type}")
                
                # Парсим в зависимости от типа
                messages = []
                
                if source_type == 'forum_chat':
                    messages = await self.message_fetcher.fetch_forum_chat_messages(
                        channel_link, start_date, end_date
                    )
                elif source_type == 'chat':
                    messages = await self.message_fetcher.fetch_chat_messages(
                        channel_link, start_date, end_date
                    )
                else:  # 'channel'
                    messages = await self.message_fetcher.fetch_channel_messages(
                        channel_link, start_date, end_date
                    )
                
                logger.info(f"Получено {len(messages)} сообщений из {channel_link}")
                return messages
                
            except Exception as e:
                logger.warning(f"Попытка {attempt}/{retry_count} не удалась: {e}")
                if attempt == retry_count:
                    self.error_handler.log_error(e, {
                        'operation': 'parse_channel', 'channel': channel_link, 'attempts': retry_count
                    })
                    self.stats['total_errors'] += 1
                    return []
                await asyncio.sleep(2 ** attempt)
        
        return []
    
    async def process_messages(self, messages: List[Message], channel_name: str) -> List[Dict]:
        """Обрабатывает сообщения: фильтрует новые, формирует структуру для экспорта"""
        logger.info(f"Обработка {len(messages)} сообщений из {channel_name}")
        new_messages = []
        for message in messages:
            if message.link not in self.processed_links:
                message_data = {
                    'date': message.date.strftime('%Y-%m-%d %H:%M:%S'),
                    'channel': message.title if message.title else channel_name,
                    'link': message.link,
                    'title': message.title,
                    'text': message.text,
                    'previous_post': message.previous_post,
                    'comments': [
                        {'author': c.author, 'link': c.link, 'text': c.text}
                        for c in message.comments
                    ]
                }
                new_messages.append(message_data)
                self.processed_links.add(message.link)
                self.cache_manager.add_processed_link(message.link)
        
        logger.info(f"Найдено {len(new_messages)} новых сообщений")
        if new_messages:
            await self.cache_manager.save_async()
        return new_messages
    
    async def export_to_google_docs(self, messages: List[Dict]) -> None:
        """Экспортирует сообщения в Google Docs"""
        if not messages:
            logger.info("Нет сообщений для экспорта")
            return
        try:
            logger.info(f"Экспорт {len(messages)} сообщений в Google Docs")
            
            # Получаем размер батча из конфигурации (по умолчанию 100)
            batch_size = get_google_config().get('BATCH_SIZE', 100)
            
            self.docs_exporter.append_new_content(messages, batch_size=batch_size)
            logger.info("Экспорт завершен успешно")
        except Exception as e:
            self.error_handler.log_error(e, {'operation': 'export_to_google_docs'})
            logger.error(f"Ошибка экспорта: {e}", exc_info=True)
    
    def get_statistics(self) -> Dict:
        """Получает статистику парсинга с информацией о типах источников и топиках"""
        db_stats = self.db.get_stats()
        source_type_stats = self.db.get_stats_by_source_type()
        
        result = {
            'current_session': self.stats.copy(),
            'database': db_stats,
            'source_types': source_type_stats['by_source_type'],
            'forum_topics': source_type_stats['forum_topics'],
            'errors': self.error_handler.get_error_summary(),
            'cache': self.cache_manager.get_cache_stats()
        }
        
        if self.stats['start_time'] and self.stats['end_time']:
            duration = (self.stats['end_time'] - self.stats['start_time']).total_seconds()
            result['current_session']['duration_seconds'] = duration
        
        # Логируем статистику по типам источников
        logger.info("=== Статистика по типам источников ===")
        for source_type, count in source_type_stats['by_source_type'].items():
            logger.info(f"  {source_type}: {count} сообщений")
        
        # Логируем статистику по топикам
        if source_type_stats['forum_topics']:
            logger.info(f"=== Статистика по топикам ({len(source_type_stats['forum_topics'])} уникальных топиков) ===")
            for topic in source_type_stats['forum_topics'][:10]:  # Показываем топ-10 топиков
                logger.info(f"  Топик '{topic['topic_title']}' (ID: {topic['topic_id']}): {topic['messages_count']} сообщений")
            if len(source_type_stats['forum_topics']) > 10:
                logger.info(f"  ... и еще {len(source_type_stats['forum_topics']) - 10} топиков")
        
        return result
    
    def setup_scheduler(self) -> None:
        """Настройка планировщика задач"""
        logger.info("Настройка планировщика")
        scheduler.add_daily_task(
            "daily_parse", lambda: asyncio.run(self.run_once()), "09:00"
        )
        scheduler.add_daily_task(
            "weekly_report",
            lambda: notification_manager.notify_daily_report(self.get_statistics()),
            "18:00"
        )
        scheduler.start()
        logger.info("Планировщик запущен")
    
    async def run_once(self) -> List[Dict]:
        """Выполняет один цикл парсинга и экспорта"""
        logger.info("=== ЗАПУСК цикла парсинга ===")
        try:
            await self.init_async()
            messages_dict = await self.parse_channels()
            all_new_messages = []
            for channel_name, messages in messages_dict.items():
                new_messages = await self.process_messages(messages, channel_name)
                all_new_messages.extend(new_messages)
            if all_new_messages:
                await self.export_to_google_docs(all_new_messages)
            logger.info(f"=== ЗАВЕРШЕНИЕ: {len(all_new_messages)} новых сообщений ===")
            return all_new_messages
        except Exception as e:
            self.error_handler.log_error(e, {'operation': 'run_once'})
            logger.error(f"Ошибка цикла: {e}", exc_info=True)
            return []
        finally:
            await self.connection_manager.disconnect()
    
    async def cleanup(self) -> None:
        """Очистка ресурсов"""
        logger.info("Очистка ресурсов")
        try:
            if self.connection_manager.is_connected():
                await self.connection_manager.disconnect()
            await self.cache_manager.save_async()
            scheduler.stop()
            logger.info("Ресурсы очищены")
        except Exception as e:
            logger.error(f"Ошибка очистки: {e}", exc_info=True)
    
    async def _save_messages_to_db(self, messages: List[Message], channel_name: str) -> None:
        """Сохраняет сообщения в БД с батчингом"""
        if not messages:
            return
        logger.info(f"Сохранение {len(messages)} сообщений в БД")
        try:
            db_messages = [
                DBMessage(
                    id=0, channel=channel_name, message_id=0, text=msg.text,
                    date=msg.date, author='', views=0, forwards=0, replies=0,
                    comments='', media_type='', media_url=''
                )
                for msg in messages
            ]
            batch_size = get_database_config().get('BATCH_SIZE', 100)
            inserted_count = self.db.batch_insert_messages(db_messages, batch_size)
            self.stats['total_messages'] += inserted_count
            logger.info(f"Сохранено {inserted_count} сообщений")
        except Exception as e:
            self.error_handler.log_error(e, {
                'operation': 'save_messages_to_db',
                'channel': channel_name,
                'messages_count': len(messages)
            })
            logger.error(f"Ошибка сохранения: {e}", exc_info=True)
