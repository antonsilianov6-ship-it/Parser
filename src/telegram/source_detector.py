# -*- coding: utf-8 -*-
"""
Модуль для определения типа источника Telegram (канал, чат, форум-чат)
"""

import logging
from typing import Any
from src.utils.logger import setup_logger

logger = setup_logger(__name__)


class SourceDetector:
    """
    Определяет тип источника Telegram на основе entity объекта
    
    Поддерживаемые типы источников:
    - 'channel': Telegram канал с односторонней коммуникацией
    - 'chat': Обычный чат (private или group) с двусторонней коммуникацией
    - 'forum_chat': Форум-чат (supergroup с топиками)
    """
    
    @staticmethod
    def detect_source_type(entity: Any) -> str:
        """
        Определяет тип источника на основе entity
        
        Args:
            entity: Entity объект из Telegram API (Channel, Chat, User)
            
        Returns:
            Тип источника: 'channel', 'chat', 'forum_chat'
            
        Logic:
            - Если entity.broadcast=True → 'channel'
            - Если entity.forum=True → 'forum_chat'
            - Если entity.megagroup=True и entity.forum=False → 'chat'
            - Если entity является User → 'chat'
            - По умолчанию → 'channel' (с предупреждением в логах)
        """
        if entity is None:
            logger.warning("Entity is None, возвращаем 'channel' по умолчанию")
            return 'channel'
        
        try:
            # Проверяем, является ли entity объектом User
            # User entity определяется по наличию атрибутов first_name или last_name
            # и отсутствию атрибутов broadcast, megagroup, forum
            entity_type = type(entity).__name__
            
            has_user_attrs = (hasattr(entity, 'first_name') or hasattr(entity, 'last_name'))
            has_channel_attrs = (hasattr(entity, 'broadcast') or 
                                hasattr(entity, 'megagroup') or 
                                hasattr(entity, 'forum'))
            
            if entity_type == 'User' or (has_user_attrs and not has_channel_attrs):
                logger.debug(f"Entity является User, возвращаем 'chat'")
                return 'chat'
            
            # Проверяем атрибут broadcast (каналы)
            if hasattr(entity, 'broadcast') and entity.broadcast:
                logger.debug(f"Entity имеет broadcast=True, возвращаем 'channel'")
                return 'channel'
            
            # Проверяем атрибут forum (форум-чаты)
            if hasattr(entity, 'forum') and entity.forum:
                logger.debug(f"Entity имеет forum=True, возвращаем 'forum_chat'")
                return 'forum_chat'
            
            # Проверяем атрибут megagroup (обычные чаты/супергруппы)
            if hasattr(entity, 'megagroup') and entity.megagroup:
                logger.debug(f"Entity имеет megagroup=True, возвращаем 'chat'")
                return 'chat'
            
            # Если не удалось определить тип, возвращаем 'channel' по умолчанию
            logger.warning(
                f"Не удалось определить тип источника для entity типа {entity_type}. "
                f"Атрибуты: broadcast={getattr(entity, 'broadcast', None)}, "
                f"megagroup={getattr(entity, 'megagroup', None)}, "
                f"forum={getattr(entity, 'forum', None)}. "
                f"Возвращаем 'channel' по умолчанию."
            )
            return 'channel'
            
        except Exception as e:
            logger.error(
                f"Ошибка при определении типа источника: {e}. "
                f"Возвращаем 'channel' по умолчанию."
            )
            return 'channel'
    
    @staticmethod
    def is_forum_chat(entity: Any) -> bool:
        """
        Проверяет, является ли источник форум-чатом
        
        Args:
            entity: Entity объект из Telegram API
            
        Returns:
            True если форум-чат, False иначе
        """
        if entity is None:
            return False
        
        try:
            # Проверяем наличие атрибута forum и его значение
            return hasattr(entity, 'forum') and entity.forum is True
            
        except Exception as e:
            logger.error(f"Ошибка при проверке форум-чата: {e}")
            return False
