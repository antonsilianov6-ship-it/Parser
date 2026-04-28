# -*- coding: utf-8 -*-
"""
Модуль для форматирования ссылок на сообщения и комментарии в Telegram
"""

import logging
from typing import Optional, Any
from src.utils.logger import setup_logger

logger = setup_logger(__name__)


class LinkFormatter:
    """
    Утилитарный класс для форматирования ссылок на Telegram-сообщения и комментарии
    """
    
    @staticmethod
    def extract_username(channel_link: str) -> str:
        """
        Извлекает username из ссылки на канал
        
        Args:
            channel_link: Ссылка на канал (https://t.me/channel или @channel)
            
        Returns:
            Username канала с префиксом @
            
        Examples:
            >>> LinkFormatter.extract_username('https://t.me/channel')
            '@channel'
            >>> LinkFormatter.extract_username('@channel')
            '@channel'
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
    
    @staticmethod
    def format_private_channel_id(channel_id: int) -> str:
        """
        Форматирует ID приватного канала для использования в ссылках
        
        Telegram использует ID формата 100XXXXXXXXX для приватных каналов.
        Для ссылок нужно убрать префикс '100'.
        
        Args:
            channel_id: ID канала (может быть отрицательным)
            
        Returns:
            Отформатированный ID для использования в ссылке
            
        Examples:
            >>> LinkFormatter.format_private_channel_id(-1001234567890)
            '1234567890'
            >>> LinkFormatter.format_private_channel_id(1001234567890)
            '1234567890'
        """
        # Берем абсолютное значение
        channel_id_abs = abs(channel_id)
        channel_id_str = str(channel_id_abs)
        
        # Убираем префикс '100' если есть
        if channel_id_str.startswith('100'):
            return channel_id_str[3:]
        
        return channel_id_str
    
    @staticmethod
    def validate_link(link: str) -> bool:
        """
        Валидирует ссылку на Telegram
        
        Args:
            link: Ссылка для проверки
            
        Returns:
            True если ссылка валидна, False иначе
        """
        if not link:
            return False
        
        # Проверяем, что ссылка содержит базовый паттерн
        if not link.startswith('https://t.me/'):
            return False
        
        # Проверяем, что нет None в ссылке
        if 'None' in link:
            logger.warning(f"Ссылка содержит None: {link}")
            return False
        
        # Проверяем минимальную длину
        if len(link) < 15:  # https://t.me/x/1
            return False
        
        return True
    
    @staticmethod
    def format_message_link(
        channel_link: str,
        channel_entity: Any,
        message_id: int
    ) -> Optional[str]:
        """
        Форматирует ссылку на сообщение в канале
        
        Приоритет формирования ссылки:
        1. Использовать username из оригинальной ссылки (если публичный канал)
        2. Использовать username из entity канала
        3. Использовать ID канала для приватных каналов
        
        Args:
            channel_link: Оригинальная ссылка на канал
            channel_entity: Entity канала из Telegram API
            message_id: ID сообщения
            
        Returns:
            Отформатированная ссылка или None при ошибке
            
        Examples:
            >>> format_message_link('https://t.me/channel', entity, 123)
            'https://t.me/channel/123'
        """
        try:
            # Приоритет 1: оригинальная ссылка канала (публичный канал)
            if channel_link.startswith('https://t.me/') and '/c/' not in channel_link:
                original_username = channel_link.replace('https://t.me/', '').split('/')[0]
                link = f"https://t.me/{original_username}/{message_id}"
                logger.debug(f"Использую оригинальный username: {original_username}")
                
                if LinkFormatter.validate_link(link):
                    return link
            
            # Приоритет 2: username из entity
            channel_username = getattr(channel_entity, 'username', None)
            if channel_username:
                link = f"https://t.me/{channel_username}/{message_id}"
                logger.debug(f"Использую channel_username: {channel_username}")
                
                if LinkFormatter.validate_link(link):
                    return link
            
            # Приоритет 3: ID для приватных каналов
            if hasattr(channel_entity, 'id') and channel_entity.id:
                formatted_id = LinkFormatter.format_private_channel_id(channel_entity.id)
                link = f"https://t.me/c/{formatted_id}/{message_id}"
                logger.debug(f"Использую приватный ID: {formatted_id}")
                
                if LinkFormatter.validate_link(link):
                    return link
            
            logger.warning(f"Не удалось сформировать ссылку для сообщения {message_id}")
            return None
            
        except Exception as e:
            logger.error(f"Ошибка при форматировании ссылки на сообщение: {e}")
            return None
    
    @staticmethod
    def format_comment_link(
        channel_entity: Any,
        message_id: int,
        comment_id: int,
        is_discussion: bool = False
    ) -> Optional[str]:
        """
        Форматирует ссылку на комментарий к посту
        
        Args:
            channel_entity: Entity канала или discussion chat
            message_id: ID сообщения
            comment_id: ID комментария
            is_discussion: True если это discussion chat, False если комментарий в канале
            
        Returns:
            Отформатированная ссылка или None при ошибке
            
        Examples:
            >>> format_comment_link(entity, 123, 456, False)
            'https://t.me/channel/123?comment=456'
            >>> format_comment_link(entity, 123, 789, True)
            'https://t.me/c/1234567890/789'
        """
        try:
            channel_username = getattr(channel_entity, 'username', None)
            
            # Для публичных каналов/чатов
            if channel_username:
                if is_discussion:
                    # Discussion chat: прямая ссылка на комментарий
                    link = f"https://t.me/{channel_username}/{comment_id}"
                else:
                    # Комментарий в канале: ссылка с параметром comment
                    link = f"https://t.me/{channel_username}/{message_id}?comment={comment_id}"
                
                if LinkFormatter.validate_link(link):
                    return link
            
            # Для приватных каналов/чатов
            if hasattr(channel_entity, 'id') and channel_entity.id:
                formatted_id = LinkFormatter.format_private_channel_id(channel_entity.id)
                
                if is_discussion:
                    # Discussion chat: прямая ссылка на комментарий
                    link = f"https://t.me/c/{formatted_id}/{comment_id}"
                else:
                    # Комментарий в канале: ссылка с параметром comment
                    link = f"https://t.me/c/{formatted_id}/{message_id}?comment={comment_id}"
                
                if LinkFormatter.validate_link(link):
                    return link
            
            logger.warning(
                f"Не удалось сформировать ссылку на комментарий "
                f"(msg_id={message_id}, comment_id={comment_id})"
            )
            return None
            
        except Exception as e:
            logger.error(f"Ошибка при форматировании ссылки на комментарий: {e}")
            return None
    
    @staticmethod
    def is_private_chat(chat_link: str) -> bool:
        """
        Определяет, является ли чат приватным
        
        Args:
            chat_link: Ссылка на чат
            
        Returns:
            True если приватный чат (содержит /c/), False иначе
            
        Examples:
            >>> LinkFormatter.is_private_chat('https://t.me/c/1234567890')
            True
            >>> LinkFormatter.is_private_chat('https://t.me/publicchat')
            False
        """
        if not chat_link:
            return False
        return '/c/' in chat_link
    
    @staticmethod
    def format_chat_message_link(
        chat_link: str,
        chat_entity: Any,
        message_id: int
    ) -> Optional[str]:
        """
        Форматирует ссылку на сообщение в чате
        
        Приоритет формирования ссылки:
        1. Использовать username из оригинальной ссылки (если публичный чат)
        2. Использовать username из entity чата
        3. Использовать ID чата для приватных чатов
        
        Args:
            chat_link: Оригинальная ссылка на чат
            chat_entity: Entity чата из Telegram API
            message_id: ID сообщения
            
        Returns:
            Отформатированная ссылка или None при ошибке
            
        Examples:
            >>> format_chat_message_link('https://t.me/chat', entity, 123)
            'https://t.me/chat/123'
            >>> format_chat_message_link('https://t.me/c/1234567890', entity, 123)
            'https://t.me/c/1234567890/123'
        """
        try:
            # Если entity равен None, возвращаем None
            if chat_entity is None:
                logger.warning(f"Entity чата равен None для ссылки {chat_link}")
                return None
            
            # Приоритет 1: оригинальная ссылка чата (публичный чат)
            if chat_link.startswith('https://t.me/') and '/c/' not in chat_link:
                original_username = chat_link.replace('https://t.me/', '').split('/')[0]
                link = f"https://t.me/{original_username}/{message_id}"
                logger.debug(f"Использую оригинальный username чата: {original_username}")
                
                if LinkFormatter.validate_link(link):
                    return link
            
            # Приоритет 2: username из entity
            chat_username = getattr(chat_entity, 'username', None)
            if chat_username:
                link = f"https://t.me/{chat_username}/{message_id}"
                logger.debug(f"Использую chat_username: {chat_username}")
                
                if LinkFormatter.validate_link(link):
                    return link
            
            # Приоритет 3: ID для приватных чатов
            if hasattr(chat_entity, 'id') and chat_entity.id:
                formatted_id = LinkFormatter.format_private_channel_id(chat_entity.id)
                link = f"https://t.me/c/{formatted_id}/{message_id}"
                logger.debug(f"Использую приватный ID чата: {formatted_id}")
                
                if LinkFormatter.validate_link(link):
                    return link
            
            logger.warning(f"Не удалось сформировать ссылку для сообщения {message_id} в чате")
            return None
            
        except Exception as e:
            logger.error(f"Ошибка при форматировании ссылки на сообщение в чате: {e}")
            return None
    
    @staticmethod
    def format_topic_message_link(
        chat_entity: Any,
        topic_id: int,
        message_id: int
    ) -> Optional[str]:
        """
        Форматирует ссылку на сообщение в топике
        
        Args:
            chat_entity: Entity форум-чата
            topic_id: ID топика
            message_id: ID сообщения
            
        Returns:
            Отформатированная ссылка или None при ошибке
            
        Examples:
            >>> format_topic_message_link(entity, 5, 123)
            'https://t.me/forumchat/5/123'
            >>> format_topic_message_link(private_entity, 5, 123)
            'https://t.me/c/1234567890/5/123'
        """
        try:
            # Если entity равен None, возвращаем None
            if chat_entity is None:
                logger.warning("Entity форум-чата равен None")
                return None
            
            chat_username = getattr(chat_entity, 'username', None)
            
            # Для публичных форум-чатов
            if chat_username:
                link = f"https://t.me/{chat_username}/{topic_id}/{message_id}"
                logger.debug(f"Использую username форум-чата: {chat_username}")
                
                if LinkFormatter.validate_link(link):
                    return link
            
            # Для приватных форум-чатов
            if hasattr(chat_entity, 'id') and chat_entity.id:
                formatted_id = LinkFormatter.format_private_channel_id(chat_entity.id)
                link = f"https://t.me/c/{formatted_id}/{topic_id}/{message_id}"
                logger.debug(f"Использую приватный ID форум-чата: {formatted_id}")
                
                if LinkFormatter.validate_link(link):
                    return link
            
            logger.warning(
                f"Не удалось сформировать ссылку для сообщения {message_id} "
                f"в топике {topic_id}"
            )
            return None
            
        except Exception as e:
            logger.error(f"Ошибка при форматировании ссылки на сообщение в топике: {e}")
            return None
