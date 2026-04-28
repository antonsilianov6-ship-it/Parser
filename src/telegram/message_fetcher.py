# -*- coding: utf-8 -*-
"""
Модуль для получения сообщений из Telegram-каналов
"""

import asyncio
import random
from typing import List, Dict, Set, Optional, Any
from datetime import datetime
from dataclasses import dataclass, field
from telethon.errors import FloodWaitError, ChannelPrivateError, UsernameNotOccupiedError
from src.telegram.connection_manager import ConnectionManager
from src.telegram.link_formatter import LinkFormatter
from src.telegram.source_detector import SourceDetector
from src.telegram.topic_manager import TopicManager
from src.telegram.chat_message_fetcher import ChatMessageFetcher
from src.cache.cache_manager import CacheManager
from src.utils.date_utils import DateUtils
from src.utils.error_handler import ErrorHandler
from src.utils.logger import setup_logger
from src.config import get_telegram_config, get_parser_config

logger = setup_logger(__name__)


@dataclass
class Comment:
    """Класс для представления комментария к посту"""
    author: str
    link: str
    text: str


@dataclass
class Message:
    """Класс для представления сообщения из канала"""
    date: datetime
    text: str
    link: str
    title: str = ''
    previous_post: Optional[str] = None
    comments: List[Comment] = field(default_factory=list)
    source_type: str = 'channel'  # 'channel', 'chat', 'forum_chat'
    topic_id: Optional[int] = None
    topic_title: Optional[str] = None
    author: str = ''  # Автор сообщения (для чатов)


class MessageFetcher:
    """
    Класс для получения сообщений из Telegram-каналов
    Поддерживает ленивую загрузку entity и пакетное получение сообщений
    """
    
    def __init__(
        self,
        connection_manager: ConnectionManager,
        cache_manager: CacheManager,
        error_handler: ErrorHandler,
        topic_manager: Optional[TopicManager] = None
    ):
        """
        Инициализация MessageFetcher
        
        Args:
            connection_manager: Менеджер подключения к Telegram
            cache_manager: Менеджер кэширования
            error_handler: Обработчик ошибок
            topic_manager: Менеджер топиков (опционально, создается автоматически)
        """
        self.connection_manager = connection_manager
        self.cache_manager = cache_manager
        self.error_handler = error_handler
        self.topic_manager = topic_manager or TopicManager(connection_manager)
        
        # Создаем ChatMessageFetcher для работы с чатами
        self.chat_fetcher = ChatMessageFetcher(self)
        
        # Получаем конфигурацию
        telegram_config = get_telegram_config()
        self.max_concurrent_connections = telegram_config.get('MAX_CONCURRENT_CONNECTIONS', 1)
        self.delay_between_channels = telegram_config.get('DELAY_BETWEEN_CHANNELS', 2)
        self.delay_between_messages = telegram_config.get('DELAY_BETWEEN_MESSAGES', 0.01)
        self.randomize_delay = telegram_config.get('RANDOMIZE_DELAY', False)
        self.delay_min = telegram_config.get('DELAY_BETWEEN_CHANNELS_MIN', self.delay_between_channels)
        self.delay_max = telegram_config.get('DELAY_BETWEEN_CHANNELS_MAX', self.delay_between_channels)
        self.lazy_entity_loading = telegram_config.get('LAZY_ENTITY_LOADING', True)
        self.prefetch_entities = telegram_config.get('PREFETCH_ENTITIES', False)
        
        # Семафор для ограничения параллельных подключений
        self.semaphore = asyncio.Semaphore(self.max_concurrent_connections)
        
        logger.info("MessageFetcher инициализирован")
    
    def _extract_username(self, channel_link: str) -> str:
        """
        Извлекает username из ссылки на канал
        
        Args:
            channel_link: Ссылка на канал (https://t.me/channel или @channel)
            
        Returns:
            Username канала
        """
        if channel_link.startswith('@'):
            return channel_link
        
        # Убираем протокол и домен
        username = channel_link.replace('https://t.me/', '').replace('http://t.me/', '')
        
        # Убираем trailing slash и параметры
        username = username.split('/')[0].split('?')[0]
        
        # Добавляем @ если нужно
        if not username.startswith('@'):
            username = f'@{username}'
        
        return username
    
    async def get_entity_lazy(self, channel_link: str) -> Optional[Any]:
        """
        Ленивое получение entity из первого сообщения (без дополнительных API вызовов)
        
        Args:
            channel_link: Ссылка на канал
            
        Returns:
            Entity канала или None
        """
        # Проверяем кэш
        cached_entity = self.cache_manager.get_entity(channel_link)
        if cached_entity:
            logger.debug(f"Entity для {channel_link} взят из кэша")
            return cached_entity
        
        # Если не в кэше, вернем None - entity будет получен из первого сообщения
        logger.debug(f"Entity для {channel_link} будет получен лениво из первого сообщения")
        return None
    
    async def prefetch_entities(self, channel_links: Set[str]) -> None:
        """
        Предзагрузка entity батчами (опциональный режим)
        
        Args:
            channel_links: Список ссылок на каналы
        """
        logger.info(f"Предзагрузка entity для {len(channel_links)} каналов")
        
        # Фильтруем каналы, которые нужно обновить
        channels_to_fetch = []
        for link in channel_links:
            if not self.cache_manager.is_entity_valid(link):
                channels_to_fetch.append(link)
        
        if not channels_to_fetch:
            logger.info("Все entity уже в кэше и актуальны")
            return
        
        logger.info(f"Нужно обновить {len(channels_to_fetch)} entity")
        
        # Получаем клиент
        client = self.connection_manager.get_client()
        
        # Загружаем батчами по 5 каналов с задержкой
        batch_size = 5
        for i in range(0, len(channels_to_fetch), batch_size):
            batch = channels_to_fetch[i:i+batch_size]
            
            # Параллельная загрузка батча
            for link in batch:
                try:
                    entity = await client.get_entity(link)
                    self.cache_manager.save_entity(link, entity)
                    logger.debug(f"Entity для {link} предзагружен")
                except Exception as e:
                    logger.warning(f"Не удалось предзагрузить entity для {link}: {e}")
            
            # Задержка между батчами
            if i + batch_size < len(channels_to_fetch):
                await asyncio.sleep(random.uniform(2, 4))
        
        logger.info("Предзагрузка entity завершена")
    
    async def fetch_channel_messages(
        self,
        channel_link: str,
        start_date: datetime,
        end_date: datetime
    ) -> List[Message]:
        """
        Получение сообщений из одного канала
        
        Args:
            channel_link: Ссылка на канал
            start_date: Начальная дата
            end_date: Конечная дата
            
        Returns:
            Список сообщений
        """
        async with self.semaphore:
            logger.info(f"=== НАЧАЛО обработки канала: {channel_link} ===")
            
            try:
                # Получаем клиент
                client = self.connection_manager.get_client()
                
                # Извлекаем username
                channel_username = self._extract_username(channel_link)
                
                # Проверяем кэш для метаданных, но не используем entity напрямую
                cached_entity_data = self.cache_manager.get_entity(channel_link)
                if cached_entity_data:
                    logger.debug(f"Метаданные entity для {channel_link} найдены в кэше")
                
                logger.info(f"Получение сообщений с {start_date} по {end_date} для канала {channel_link}")
                
                # Получаем сообщения
                all_messages = []
                channel_entity = None
                
                try:
                    # Всегда используем username для iter_messages (Telethon сам получит entity)
                    async for msg in client.iter_messages(
                        channel_username,
                        offset_date=end_date,
                        limit=None
                    ):
                        if not hasattr(msg, 'date') or not msg.date:
                            continue
                        
                        if msg.date < start_date:
                            break
                        
                        # Получаем entity из первого сообщения (если еще не получен)
                        if not channel_entity and hasattr(msg, '_chat'):
                            channel_entity = msg._chat
                            self.cache_manager.save_entity(channel_link, channel_entity)
                            logger.debug(f"Entity для {channel_link} получен из первого сообщения")
                        
                        all_messages.append(msg)
                        
                        # Минимальная задержка между сообщениями
                        await asyncio.sleep(self.delay_between_messages)
                    
                except FloodWaitError as e:
                    await self.error_handler.handle_flood_wait(e, f"fetch_messages:{channel_link}")
                    # Повторяем попытку после ожидания
                    return await self.fetch_channel_messages(channel_link, start_date, end_date)
                
                except (ChannelPrivateError, UsernameNotOccupiedError) as e:
                    self.error_handler.handle_channel_error(e, channel_link)
                    return []
                
                # Если не получили entity, создаем заглушку
                if not channel_entity:
                    channel_entity = type('obj', (object,), {
                        'title': channel_username,
                        'username': channel_username.replace('@', ''),
                        'id': 0
                    })()
                
                # Определяем тип источника
                source_type = SourceDetector.detect_source_type(channel_entity)
                
                # Извлекаем метаданные канала
                channel_title = getattr(channel_entity, 'title', str(channel_link))
                channel_username_clean = getattr(channel_entity, 'username', None)
                
                # Обрабатываем сообщения
                result = []
                for msg in all_messages:
                    if not msg.message:
                        continue
                    
                    # Формируем ссылку на сообщение
                    message_link = LinkFormatter.format_message_link(
                        channel_link,
                        channel_entity,
                        msg.id
                    )
                    
                    if not message_link:
                        logger.warning(f"Не удалось сформировать ссылку для сообщения {msg.id}")
                        continue
                    
                    result.append(Message(
                        date=msg.date,
                        text=msg.message,
                        link=message_link,
                        title=channel_title,
                        previous_post=None,
                        comments=[],
                        source_type=source_type,
                        topic_id=None,
                        topic_title=None,
                        author=''
                    ))
                
                logger.info(f"Получено {len(result)} сообщений из канала {channel_link}")
                logger.info(f"=== КОНЕЦ обработки канала: {channel_link} ===")
                return result
                
            except Exception as e:
                self.error_handler.log_error(e, {
                    'channel': channel_link,
                    'operation': 'fetch_channel_messages'
                })
                logger.info(f"=== КОНЕЦ обработки канала (с ошибкой): {channel_link} ===")
                return []
    
    def _extract_message_author(self, message: Any) -> str:
        """
        Извлекает автора сообщения
        
        Args:
            message: Объект сообщения из Telegram API
            
        Returns:
            Имя автора или 'Unknown'
        """
        try:
            if not hasattr(message, 'sender') or message.sender is None:
                return 'Unknown'
            
            sender = message.sender
            
            # Для пользователей
            if hasattr(sender, 'first_name') or hasattr(sender, 'last_name'):
                first_name = getattr(sender, 'first_name', '')
                last_name = getattr(sender, 'last_name', '')
                full_name = f"{first_name} {last_name}".strip()
                return full_name if full_name else 'Unknown'
            
            # Для каналов/чатов
            if hasattr(sender, 'title'):
                return sender.title
            
            # Для username
            if hasattr(sender, 'username') and sender.username:
                return f"@{sender.username}"
            
            return 'Unknown'
            
        except Exception as e:
            logger.warning(f"Ошибка при извлечении автора сообщения: {e}")
            return 'Unknown'
    
    async def fetch_chat_messages(
        self,
        chat_link: str,
        start_date: datetime,
        end_date: datetime
    ) -> List[Message]:
        """
        Получение сообщений из обычного чата
        
        Args:
            chat_link: Ссылка на чат
            start_date: Начальная дата
            end_date: Конечная дата
            
        Returns:
            Список сообщений с метаданными о типе источника
        """
        async with self.semaphore:
            logger.info(f"=== НАЧАЛО обработки чата: {chat_link} ===")
            
            try:
                # Получаем клиент
                client = self.connection_manager.get_client()
                
                # Извлекаем username
                chat_username = self._extract_username(chat_link)
                
                # Проверяем кэш для метаданных, но не используем entity напрямую
                cached_entity_data = self.cache_manager.get_entity(chat_link)
                if cached_entity_data:
                    logger.debug(f"Метаданные entity для {chat_link} найдены в кэше")
                
                logger.info(f"Получение сообщений с {start_date} по {end_date} для чата {chat_link}")
                
                # Получаем сообщения
                all_messages = []
                chat_entity = None
                
                try:
                    # Всегда используем username для iter_messages (Telethon сам получит entity)
                    async for msg in client.iter_messages(
                        chat_username,
                        offset_date=end_date,
                        limit=None
                    ):
                        if not hasattr(msg, 'date') or not msg.date:
                            continue
                        
                        if msg.date < start_date:
                            break
                        
                        # Получаем entity из первого сообщения (если еще не получен)
                        if not chat_entity and hasattr(msg, '_chat'):
                            chat_entity = msg._chat
                            self.cache_manager.save_entity(chat_link, chat_entity)
                            logger.debug(f"Entity для {chat_link} получен из первого сообщения")
                        
                        all_messages.append(msg)
                        
                        # Минимальная задержка между сообщениями
                        await asyncio.sleep(self.delay_between_messages)
                    
                except FloodWaitError as e:
                    await self.error_handler.handle_flood_wait(e, f"fetch_chat_messages:{chat_link}")
                    # Повторяем попытку после ожидания
                    return await self.fetch_chat_messages(chat_link, start_date, end_date)
                
                except (ChannelPrivateError, UsernameNotOccupiedError) as e:
                    self.error_handler.handle_channel_error(e, chat_link)
                    return []
                
                # Если не получили entity, создаем заглушку
                if not chat_entity:
                    # Пытаемся определить тип из ссылки
                    # Для чатов создаем заглушку с megagroup=True
                    chat_entity = type('obj', (object,), {
                        'title': chat_username,
                        'username': chat_username.replace('@', ''),
                        'id': 0,
                        'broadcast': False,
                        'megagroup': True,
                        'forum': False
                    })()
                
                # Определяем тип источника
                source_type = SourceDetector.detect_source_type(chat_entity)
                
                # Извлекаем метаданные чата
                chat_title = getattr(chat_entity, 'title', str(chat_link))
                
                # Обрабатываем сообщения
                result = []
                for msg in all_messages:
                    if not msg.message:
                        continue
                    
                    # Извлекаем автора сообщения
                    author = self._extract_message_author(msg)
                    
                    # Формируем ссылку на сообщение
                    message_link = LinkFormatter.format_chat_message_link(
                        chat_link,
                        chat_entity,
                        msg.id
                    )
                    
                    if not message_link:
                        logger.warning(f"Не удалось сформировать ссылку для сообщения {msg.id}")
                        continue
                    
                    result.append(Message(
                        date=msg.date,
                        text=msg.message,
                        link=message_link,
                        title=chat_title,
                        previous_post=None,
                        comments=[],
                        source_type=source_type,
                        topic_id=None,
                        topic_title=None,
                        author=author
                    ))
                
                logger.info(f"Получено {len(result)} сообщений из чата {chat_link}")
                logger.info(f"=== КОНЕЦ обработки чата: {chat_link} ===")
                return result
                
            except Exception as e:
                self.error_handler.log_error(e, {
                    'chat': chat_link,
                    'operation': 'fetch_chat_messages'
                })
                logger.info(f"=== КОНЕЦ обработки чата (с ошибкой): {chat_link} ===")
                return []
    
    async def fetch_topic_messages(
        self,
        chat_entity: Any,
        chat_link: str,
        topic_id: int,
        topic_title: str,
        start_date: datetime,
        end_date: datetime
    ) -> List[Message]:
        """
        Получение сообщений из конкретного топика
        
        Args:
            chat_entity: Entity форум-чата
            chat_link: Ссылка на чат (для логирования)
            topic_id: ID топика
            topic_title: Название топика
            start_date: Начальная дата
            end_date: Конечная дата
            
        Returns:
            Список сообщений с метаданными о топике
        """
        logger.info(f"Получение сообщений из топика '{topic_title}' (ID: {topic_id})")
        
        try:
            # Получаем клиент
            client = self.connection_manager.get_client()
            
            # Получаем сообщения из топика
            all_messages = []
            
            try:
                # Используем reply_to для фильтрации по топику
                async for msg in client.iter_messages(
                    chat_entity,
                    offset_date=end_date,
                    limit=None,
                    reply_to=topic_id
                ):
                    if not hasattr(msg, 'date') or not msg.date:
                        continue
                    
                    if msg.date < start_date:
                        break
                    
                    # Проверяем что сообщение действительно из этого топика
                    if hasattr(msg, 'reply_to') and msg.reply_to:
                        # Проверяем reply_to_top_id (ID топика)
                        if hasattr(msg.reply_to, 'reply_to_top_id'):
                            if msg.reply_to.reply_to_top_id != topic_id:
                                continue
                        # Проверяем forum_topic флаг
                        if hasattr(msg.reply_to, 'forum_topic'):
                            if not msg.reply_to.forum_topic:
                                continue
                    
                    all_messages.append(msg)
                    
                    # Минимальная задержка между сообщениями
                    await asyncio.sleep(self.delay_between_messages)
                
            except FloodWaitError as e:
                await self.error_handler.handle_flood_wait(e, f"fetch_topic_messages:{chat_link}:{topic_id}")
                # Повторяем попытку после ожидания
                return await self.fetch_topic_messages(
                    chat_entity, chat_link, topic_id, topic_title, start_date, end_date
                )
            
            # Извлекаем метаданные чата
            chat_title = getattr(chat_entity, 'title', str(chat_link))
            
            # Обрабатываем сообщения
            result = []
            for msg in all_messages:
                if not msg.message:
                    continue
                
                # Извлекаем автора сообщения
                author = self._extract_message_author(msg)
                
                # Формируем ссылку на сообщение в топике
                message_link = LinkFormatter.format_topic_message_link(
                    chat_entity,
                    topic_id,
                    msg.id
                )
                
                if not message_link:
                    logger.warning(f"Не удалось сформировать ссылку для сообщения {msg.id} в топике {topic_id}")
                    continue
                
                result.append(Message(
                    date=msg.date,
                    text=msg.message,
                    link=message_link,
                    title=chat_title,
                    previous_post=None,
                    comments=[],
                    source_type='forum_chat',
                    topic_id=topic_id,
                    topic_title=topic_title,
                    author=author
                ))
            
            logger.info(f"Получено {len(result)} сообщений из топика '{topic_title}'")
            return result
            
        except Exception as e:
            self.error_handler.log_error(e, {
                'chat': chat_link,
                'topic_id': topic_id,
                'topic_title': topic_title,
                'operation': 'fetch_topic_messages'
            })
            return []
    
    async def fetch_forum_chat_messages(
        self,
        chat_link: str,
        start_date: datetime,
        end_date: datetime
    ) -> List[Message]:
        """
        Получение сообщений из форум-чата (со всеми топиками)
        
        Args:
            chat_link: Ссылка на форум-чат
            start_date: Начальная дата
            end_date: Конечная дата
            
        Returns:
            Список сообщений из всех топиков
        """
        async with self.semaphore:
            logger.info(f"=== НАЧАЛО обработки форум-чата: {chat_link} ===")
            
            try:
                # Получаем клиент
                client = self.connection_manager.get_client()
                
                # Получаем entity форум-чата
                chat_entity = None
                try:
                    chat_entity = await client.get_entity(chat_link)
                    self.cache_manager.save_entity(chat_link, chat_entity)
                except Exception as e:
                    logger.error(f"Не удалось получить entity для форум-чата {chat_link}: {e}")
                    return []
                
                # Проверяем что это действительно форум-чат
                if not SourceDetector.is_forum_chat(chat_entity):
                    logger.warning(f"{chat_link} не является форум-чатом")
                    # Пробуем парсить как обычный чат
                    return await self.fetch_chat_messages(chat_link, start_date, end_date)
                
                # Получаем список топиков
                topics = await self.topic_manager.get_forum_topics(chat_entity)
                
                if not topics:
                    logger.warning(f"Не удалось получить топики для форум-чата {chat_link}")
                    return []
                
                logger.info(f"Найдено {len(topics)} топиков в форум-чате {chat_link}")
                
                # Получаем сообщения из каждого топика
                all_messages = []
                for topic_id, topic_title in topics:
                    try:
                        topic_messages = await self.fetch_topic_messages(
                            chat_entity,
                            chat_link,
                            topic_id,
                            topic_title,
                            start_date,
                            end_date
                        )
                        all_messages.extend(topic_messages)
                        
                        # Задержка между топиками
                        if self.randomize_delay:
                            delay = random.uniform(self.delay_min, self.delay_max)
                        else:
                            delay = self.delay_between_channels  # Используем ту же задержку
                        
                        logger.info(f"Задержка {delay:.2f} секунд перед следующим топиком")
                        await asyncio.sleep(delay)
                        
                    except Exception as e:
                        logger.error(f"Ошибка при парсинге топика '{topic_title}': {e}")
                        continue
                
                logger.info(f"Получено {len(all_messages)} сообщений из форум-чата {chat_link}")
                logger.info(f"=== КОНЕЦ обработки форум-чата: {chat_link} ===")
                return all_messages
                
            except Exception as e:
                self.error_handler.log_error(e, {
                    'chat': chat_link,
                    'operation': 'fetch_forum_chat_messages'
                })
                logger.info(f"=== КОНЕЦ обработки форум-чата (с ошибкой): {chat_link} ===")
                return []
    
    async def fetch_messages_batch(
        self,
        channel_links: Set[str],
        days: Optional[int] = None
    ) -> Dict[str, List[Message]]:
        """
        Пакетное получение сообщений из нескольких каналов
        
        Args:
            channel_links: Список ссылок на каналы
            days: Количество дней для выгрузки (если не указано, берется из конфигурации)
            
        Returns:
            Словарь вида {channel_name: [messages]}
        """
        logger.info(f"Начало получения сообщений из {len(channel_links)} каналов")
        
        # Получаем диапазон дат
        start_date, end_date = DateUtils.get_date_range(days)
        
        # Опциональная предзагрузка entity
        if self.prefetch_entities:
            logger.info("Предзагрузка entity включена")
            await self.prefetch_entities(channel_links)
        else:
            logger.info("Используется ленивая загрузка entity")
        
        # Получаем сообщения из каждого канала
        result_dict = {}
        for link in channel_links:
            try:
                messages = await self.fetch_channel_messages(link, start_date, end_date)
                if messages:
                    channel_name = link.split('/')[-1]
                    result_dict[channel_name] = messages
                
                # Задержка между каналами
                if self.randomize_delay:
                    delay = random.uniform(self.delay_min, self.delay_max)
                else:
                    delay = self.delay_between_channels
                
                logger.info(f"Задержка {delay:.2f} секунд перед следующим каналом")
                await asyncio.sleep(delay)
                
            except Exception as e:
                self.error_handler.log_error(e, {
                    'channel': link,
                    'operation': 'fetch_messages_batch'
                })
        
        logger.info(f"Успешно получены сообщения из {len(result_dict)} каналов")
        return result_dict
