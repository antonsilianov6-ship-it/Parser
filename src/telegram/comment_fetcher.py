# -*- coding: utf-8 -*-
"""
Модуль для получения комментариев к постам в Telegram-каналах
"""

import asyncio
from typing import List, Optional, Any
from dataclasses import dataclass
from src.telegram.connection_manager import ConnectionManager
from src.telegram.link_formatter import LinkFormatter
from src.utils.logger import setup_logger
from src.config import get_parser_config, get_telegram_config

logger = setup_logger(__name__)


@dataclass
class Comment:
    """Класс для представления комментария к посту"""
    author: str
    link: str
    text: str


class CommentFetcher:
    """
    Класс для получения комментариев к постам в Telegram-каналах
    Поддерживает получение комментариев из discussion chat и из самого канала
    """
    
    def __init__(self, connection_manager: ConnectionManager):
        """
        Инициализация CommentFetcher
        
        Args:
            connection_manager: Менеджер подключения к Telegram
        """
        self.connection_manager = connection_manager
        
        # Получаем конфигурацию
        parser_config = get_parser_config()
        telegram_config = get_telegram_config()
        
        self.fetch_comments = parser_config.get('FETCH_COMMENTS', True)
        self.max_comments = parser_config.get('MAX_COMMENTS_PER_POST', 50)
        self.delay_between_comments = telegram_config.get('DELAY_BETWEEN_COMMENTS', 0.1)
        
        logger.info("CommentFetcher инициализирован")
    
    async def fetch_post_comments(
        self,
        channel: Any,
        message: Any,
        max_comments: Optional[int] = None
    ) -> List[Comment]:
        """
        Получение комментариев к посту
        
        Args:
            channel: Entity канала
            message: Сообщение
            max_comments: Максимальное количество комментариев (если не указано, берется из конфигурации)
            
        Returns:
            Список комментариев
        """
        if not self.fetch_comments:
            return []
        
        if max_comments is None:
            max_comments = self.max_comments
        
        comments = []
        
        # 1. Сначала ищем в discussion_chat (если есть)
        linked_chat_id = getattr(channel, 'linked_chat_id', None)
        if linked_chat_id and hasattr(message, 'id'):
            discussion_comments = await self.fetch_discussion_comments(
                linked_chat_id,
                message.id,
                max_comments
            )
            comments.extend(discussion_comments)
        
        # 2. Теперь ищем комментарии в самом канале (reply_to_msg_id)
        if hasattr(message, 'id'):
            channel_comments = await self.fetch_channel_comments(
                channel,
                message.id,
                max_comments
            )
            comments.extend(channel_comments)
        
        return comments
    
    async def fetch_discussion_comments(
        self,
        linked_chat_id: int,
        message_id: int,
        max_comments: int
    ) -> List[Comment]:
        """
        Получение комментариев из discussion chat
        
        Args:
            linked_chat_id: ID связанного чата для обсуждений
            message_id: ID сообщения
            max_comments: Максимальное количество комментариев
            
        Returns:
            Список комментариев
        """
        comments = []
        
        try:
            client = self.connection_manager.get_client()
            
            # Получаем entity discussion chat
            discussion_chat = await client.get_entity(linked_chat_id)
            await asyncio.sleep(1.5)  # Задержка для избежания FloodWait
            
            discussion_username = getattr(discussion_chat, 'username', None)
            
            # Получаем комментарии
            comment_count = 0
            async for comment in client.iter_messages(
                linked_chat_id,
                reply_to=message_id,
                limit=max_comments
            ):
                await asyncio.sleep(self.delay_between_comments)
                
                if not comment.message:
                    continue
                
                # Определяем автора
                if comment.sender:
                    author = (
                        getattr(comment.sender, 'first_name', None) or
                        getattr(comment.sender, 'title', None) or
                        "Аноним"
                    )
                else:
                    author = "Аноним"
                
                # Формируем ссылку на комментарий
                link = LinkFormatter.format_comment_link(
                    discussion_chat,
                    message_id,
                    comment.id,
                    is_discussion=True
                )
                
                if link:
                    comments.append(Comment(
                        author=author,
                        link=link,
                        text=comment.message
                    ))
                
                comment_count += 1
                if comment_count >= max_comments:
                    break
                    
        except Exception as e:
            if 'The message ID used in the peer was invalid' in str(e):
                logger.warning(f"Комментариев нет или ID невалиден для поста {message_id}: {e}")
            else:
                logger.error(f"Ошибка при получении комментариев из discussion chat для поста {message_id}: {e}")
        
        return comments
    
    async def fetch_channel_comments(
        self,
        channel: Any,
        message_id: int,
        max_comments: int
    ) -> List[Comment]:
        """
        Получение комментариев из самого канала
        
        Args:
            channel: Entity канала
            message_id: ID сообщения
            max_comments: Максимальное количество комментариев
            
        Returns:
            Список комментариев
        """
        comments = []
        
        try:
            client = self.connection_manager.get_client()
            channel_username = getattr(channel, 'username', None)
            
            # Получаем комментарии
            comment_count = 0
            async for comment in client.iter_messages(
                channel.id,
                reply_to=message_id,
                limit=max_comments
            ):
                await asyncio.sleep(self.delay_between_comments)
                
                if not comment.message:
                    continue
                
                # Определяем автора
                if comment.sender:
                    author = (
                        getattr(comment.sender, 'first_name', None) or
                        getattr(comment.sender, 'title', None) or
                        "Аноним"
                    )
                else:
                    author = "Аноним"
                
                # Формируем ссылку на комментарий
                link = LinkFormatter.format_comment_link(
                    channel,
                    message_id,
                    comment.id,
                    is_discussion=False
                )
                
                if link:
                    comments.append(Comment(
                        author=author,
                        link=link,
                        text=comment.message
                    ))
                
                comment_count += 1
                if comment_count >= max_comments:
                    break
                    
        except Exception as e:
            if 'The message ID used in the peer was invalid' in str(e):
                logger.warning(f"Комментариев нет или ID невалиден для поста {message_id} в канале: {e}")
            else:
                logger.error(f"Ошибка при получении комментариев к посту {message_id} в канале: {e}")
        
        return comments
    
    async def find_previous_post(self, message: Any, text: str) -> Optional[str]:
        """
        Поиск ссылки на предыдущий пост, если текст содержит продолжение
        
        Args:
            message: Сообщение
            text: Текст сообщения
            
        Returns:
            Ссылка на предыдущий пост или None
        """
        parser_config = get_parser_config()
        if not parser_config.get('FETCH_PREVIOUS_POSTS', True):
            return None
        
        # Проверяем, есть ли в тексте указание на продолжение
        continuation_markers = [
            "продолжение", "часть 2", "часть II", "part 2",
            "thread", "тред продолжается", "далее", "см. ранее"
        ]
        
        has_continuation = False
        for marker in continuation_markers:
            if marker.lower() in text.lower():
                has_continuation = True
                break
        
        if not has_continuation:
            return None
        
        # Если пост является продолжением, проверим, есть ли цитированный пост
        if hasattr(message, 'reply_to') and message.reply_to:
            try:
                # Получаем ID сообщения, на которое ссылается текущее
                reply_msg_id = message.reply_to.reply_to_msg_id
                if not reply_msg_id:
                    return None
                
                # Получаем информацию о канале
                channel_id = message.peer_id.channel_id
                client = self.connection_manager.get_client()
                channel_entity = await client.get_entity(channel_id)
                
                # Формируем ссылку
                channel_username = getattr(channel_entity, 'username', None)
                
                if channel_username:
                    return f"https://t.me/{channel_username}/{reply_msg_id}"
                else:
                    # Правильное формирование ID для приватных каналов
                    channel_id = abs(channel_id)
                    if str(channel_id).startswith('100'):
                        channel_id = str(channel_id)[3:]
                    return f"https://t.me/c/{channel_id}/{reply_msg_id}"
                    
            except Exception as e:
                logger.error(f"Ошибка при получении предыдущего поста: {e}")
        
        return None
