# -*- coding: utf-8 -*-
"""
Модуль для управления топиками в форум-чатах Telegram
"""

import logging
from typing import Any, Dict, List, Optional, Tuple
from telethon.errors import ChatAdminRequiredError, UserNotParticipantError
from src.utils.logger import setup_logger

logger = setup_logger(__name__)


class TopicManager:
    """
    Управляет топиками в форум-чатах
    
    Предоставляет функциональность для:
    - Получения списка топиков из форум-чата
    - Кэширования топиков для минимизации API вызовов
    - Обработки ошибок доступа к форум-чатам
    """
    
    def __init__(self, connection_manager):
        """
        Инициализация менеджера топиков
        
        Args:
            connection_manager: Менеджер подключения к Telegram (ConnectionManager)
        """
        self.connection_manager = connection_manager
        self.topic_cache: Dict[str, List[Tuple[int, str]]] = {}
        logger.debug("TopicManager инициализирован")
    
    async def get_forum_topics(
        self, 
        chat_entity: Any
    ) -> List[Tuple[int, str]]:
        """
        Получает список топиков из форум-чата
        
        Args:
            chat_entity: Entity форум-чата из Telegram API
            
        Returns:
            Список кортежей (topic_id, topic_title)
            Возвращает пустой список при ошибках доступа
            
        Raises:
            Exception: При критических ошибках (не связанных с доступом)
        """
        if chat_entity is None:
            logger.warning("chat_entity is None, возвращаем пустой список топиков")
            return []
        
        try:
            # Получаем клиент Telegram
            client = self.connection_manager.get_client()
            
            # Получаем список топиков через Telethon API
            logger.info(f"Получение списка топиков для форум-чата {chat_entity.id}")
            
            topics = []
            
            # Используем правильный метод для получения топиков форума
            # Telethon использует GetForumTopicsRequest для форум-чатов
            try:
                from telethon.tl.functions.channels import GetForumTopicsRequest
                from telethon.tl.types import ForumTopic
                
                # Получаем топики через GetForumTopicsRequest
                result = await client(GetForumTopicsRequest(
                    channel=chat_entity,
                    offset_date=0,
                    offset_id=0,
                    offset_topic=0,
                    limit=100
                ))
                
                # Обрабатываем результат
                for topic in result.topics:
                    if isinstance(topic, ForumTopic):
                        topic_id = topic.id
                        topic_title = topic.title
                        topics.append((topic_id, topic_title))
                        logger.debug(f"Найден топик: id={topic_id}, title={topic_title}")
                
                logger.info(f"Получено {len(topics)} топиков из форум-чата {chat_entity.id}")
                return topics
                
            except ImportError:
                logger.warning("GetForumTopicsRequest недоступен в текущей версии Telethon")
                # Fallback: пробуем получить через iter_messages с разными topic_id
                logger.info("Используем fallback метод для получения топиков")
                return await self._get_topics_fallback(client, chat_entity)
            
        except ChatAdminRequiredError as e:
            logger.warning(
                f"Требуются права администратора для получения топиков форум-чата {chat_entity.id}. "
                f"Ошибка: {e}"
            )
            return []
            
        except UserNotParticipantError as e:
            logger.warning(
                f"Пользователь не является участником форум-чата {chat_entity.id}. "
                f"Ошибка: {e}"
            )
            return []
            
        except Exception as e:
            logger.error(
                f"Ошибка при получении топиков из форум-чата {chat_entity.id}: {e}",
                exc_info=True
            )
            # Возвращаем пустой список вместо пробрасывания ошибки
            return []
    
    async def _get_topics_fallback(self, client: Any, chat_entity: Any) -> List[Tuple[int, str]]:
        """
        Fallback метод для получения топиков (если основной метод недоступен)
        
        Args:
            client: Telegram клиент
            chat_entity: Entity форум-чата
            
        Returns:
            Список кортежей (topic_id, topic_title)
        """
        logger.info("Используем fallback метод для получения топиков")
        topics = []
        
        try:
            # Пробуем получить несколько последних сообщений и извлечь из них топики
            seen_topics = set()
            async for message in client.iter_messages(chat_entity, limit=100):
                if hasattr(message, 'reply_to') and message.reply_to:
                    if hasattr(message.reply_to, 'forum_topic') and message.reply_to.forum_topic:
                        topic_id = message.reply_to.reply_to_top_id
                        if topic_id and topic_id not in seen_topics:
                            seen_topics.add(topic_id)
                            # Пытаемся получить название топика
                            topic_title = f"Topic {topic_id}"
                            topics.append((topic_id, topic_title))
                            logger.debug(f"Найден топик через fallback: id={topic_id}")
            
            logger.info(f"Fallback метод нашел {len(topics)} топиков")
            return topics
            
        except Exception as e:
            logger.error(f"Ошибка в fallback методе: {e}")
            return []
    
    def get_cached_topics(self, chat_link: str) -> Optional[List[Tuple[int, str]]]:
        """
        Получает закэшированный список топиков
        
        Args:
            chat_link: Ссылка на чат (используется как ключ кэша)
            
        Returns:
            Список топиков или None если не в кэше
        """
        cached = self.topic_cache.get(chat_link)
        
        if cached is not None:
            logger.debug(f"Топики для {chat_link} найдены в кэше ({len(cached)} топиков)")
        else:
            logger.debug(f"Топики для {chat_link} не найдены в кэше")
        
        return cached
    
    def cache_topics(
        self, 
        chat_link: str, 
        topics: List[Tuple[int, str]]
    ) -> None:
        """
        Кэширует список топиков
        
        Args:
            chat_link: Ссылка на чат (используется как ключ кэша)
            topics: Список топиков для кэширования
        """
        self.topic_cache[chat_link] = topics
        logger.debug(f"Закэшировано {len(topics)} топиков для {chat_link}")
    
    def clear_cache(self, chat_link: Optional[str] = None) -> None:
        """
        Очищает кэш топиков
        
        Args:
            chat_link: Ссылка на конкретный чат для очистки.
                      Если None, очищается весь кэш.
        """
        if chat_link is None:
            self.topic_cache.clear()
            logger.debug("Весь кэш топиков очищен")
        elif chat_link in self.topic_cache:
            del self.topic_cache[chat_link]
            logger.debug(f"Кэш топиков для {chat_link} очищен")
        else:
            logger.debug(f"Кэш для {chat_link} не найден, нечего очищать")
    
    def get_cache_size(self) -> int:
        """
        Возвращает количество закэшированных чатов
        
        Returns:
            Количество чатов в кэше
        """
        return len(self.topic_cache)
