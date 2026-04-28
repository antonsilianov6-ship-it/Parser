# -*- coding: utf-8 -*-
"""
Модуль для получения сообщений из Telegram чатов и форум-чатов
"""

import asyncio
import random
from typing import List, Any, Optional
from datetime import datetime
from telethon.errors import FloodWaitError, ChannelPrivateError, UsernameNotOccupiedError
from src.telegram.link_formatter import LinkFormatter
from src.telegram.source_detector import SourceDetector
from src.utils.logger import setup_logger

logger = setup_logger(__name__)


class ChatMessageFetcher:
    """
    Класс для получения сообщений из чатов и форум-чатов
    Расширяет функциональность MessageFetcher для работы с чатами
    """
    
    def __init__(self, message_fetcher):
        """
        Инициализация ChatMessageFetcher
        
        Args:
            message_fetcher: Экземпляр MessageFetcher для доступа к общим методам
        """
        self.fetcher = message_fetcher
    
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
    ):
        """
        Получение сообщений из обычного чата
        
        Args:
            chat_link: Ссылка на чат
            start_date: Начальная дата
            end_date: Конечная дата
            
        Returns:
            Список сообщений с метаданными о типе источника
        """
        from src.telegram.message_fetcher import Message
        
        async with self.fetcher.semaphore:
            logger.info(f"=== НАЧАЛО обработки чата: {chat_link} ===")
            
            try:
                # Получаем клиент
                client = self.fetcher.connection_manager.get_client()
                
                # Извлекаем username
                chat_username = self.fetcher._extract_username(chat_link)
                
                # Пробуем получить entity из кэша (ленивая загрузка)
                chat_entity = None
                if self.fetcher.lazy_entity_loading:
                    chat_entity = await self.fetcher.get_entity_lazy(chat_link)
                else:
                    # Явная загрузка entity
                    try:
                        chat_entity = await client.get_entity(chat_link)
                        self.fetcher.cache_manager.save_entity(chat_link, chat_entity)
                    except Exception as e:
                        logger.warning(f"Не удалось получить entity для {chat_link}: {e}")
                
                logger.info(f"Получение сообщений с {start_date} по {end_date} для чата {chat_link}")
                
                # Получаем сообщения
                all_messages = []
                
                try:
                    # iter_messages принимает username напрямую (ленивая загрузка entity)
                    async for msg in client.iter_messages(
                        chat_username if not chat_entity else chat_entity,
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
                            self.fetcher.cache_manager.save_entity(chat_link, chat_entity)
                            logger.debug(f"Entity для {chat_link} получен из первого сообщения")
                        
                        all_messages.append(msg)
                        
                        # Минимальная задержка между сообщениями
                        await asyncio.sleep(self.fetcher.delay_between_messages)
                    
                except FloodWaitError as e:
                    await self.fetcher.error_handler.handle_flood_wait(e, f"fetch_chat_messages:{chat_link}")
                    # Повторяем попытку после ожидания
                    return await self.fetch_chat_messages(chat_link, start_date, end_date)
                
                except (ChannelPrivateError, UsernameNotOccupiedError) as e:
                    self.fetcher.error_handler.handle_channel_error(e, chat_link)
                    return []
                
                # Если не получили entity, создаем заглушку
                if not chat_entity:
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
                self.fetcher.error_handler.log_error(e, {
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
    ):
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
        from src.telegram.message_fetcher import Message
        
        logger.info(f"Получение сообщений из топика '{topic_title}' (ID: {topic_id})")
        
        try:
            # Получаем клиент
            client = self.fetcher.connection_manager.get_client()
            
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
                    await asyncio.sleep(self.fetcher.delay_between_messages)
                
            except FloodWaitError as e:
                await self.fetcher.error_handler.handle_flood_wait(e, f"fetch_topic_messages:{chat_link}:{topic_id}")
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
            self.fetcher.error_handler.log_error(e, {
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
    ):
        """
        Получение сообщений из форум-чата (со всеми топиками)
        
        Args:
            chat_link: Ссылка на форум-чат
            start_date: Начальная дата
            end_date: Конечная дата
            
        Returns:
            Список сообщений из всех топиков
        """
        async with self.fetcher.semaphore:
            logger.info(f"=== НАЧАЛО обработки форум-чата: {chat_link} ===")
            
            try:
                # Получаем клиент
                client = self.fetcher.connection_manager.get_client()
                
                # Получаем entity форум-чата
                chat_entity = None
                try:
                    chat_entity = await client.get_entity(chat_link)
                    self.fetcher.cache_manager.save_entity(chat_link, chat_entity)
                except Exception as e:
                    logger.error(f"Не удалось получить entity для форум-чата {chat_link}: {e}")
                    return []
                
                # Проверяем что это действительно форум-чат
                if not SourceDetector.is_forum_chat(chat_entity):
                    logger.warning(f"{chat_link} не является форум-чатом")
                    # Пробуем парсить как обычный чат
                    return await self.fetch_chat_messages(chat_link, start_date, end_date)
                
                # Получаем список топиков
                topics = await self.fetcher.topic_manager.get_forum_topics(chat_entity)
                
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
                        if self.fetcher.randomize_delay:
                            delay = random.uniform(self.fetcher.delay_min, self.fetcher.delay_max)
                        else:
                            delay = self.fetcher.delay_between_channels  # Используем ту же задержку
                        
                        logger.info(f"Задержка {delay:.2f} секунд перед следующим топиком")
                        await asyncio.sleep(delay)
                        
                    except Exception as e:
                        logger.error(f"Ошибка при парсинге топика '{topic_title}': {e}")
                        continue
                
                logger.info(f"Получено {len(all_messages)} сообщений из форум-чата {chat_link}")
                logger.info(f"=== КОНЕЦ обработки форум-чата: {chat_link} ===")
                return all_messages
                
            except Exception as e:
                self.fetcher.error_handler.log_error(e, {
                    'chat': chat_link,
                    'operation': 'fetch_forum_chat_messages'
                })
                logger.info(f"=== КОНЕЦ обработки форум-чата (с ошибкой): {chat_link} ===")
                return []
