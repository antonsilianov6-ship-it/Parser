# -*- coding: utf-8 -*-
"""Унифицированный модуль для управления кэшем"""

import os
import json
import aiofiles
from typing import Dict, Set, Any, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from src.config import CACHE_FILE
from src.utils.logger import setup_logger

logger = setup_logger(__name__)


@dataclass
class CacheEntry:
    """Запись в кэше entity"""
    channel_id: int
    title: str
    username: str
    cached_at: str
    source_type: str = 'channel'  # NEW: тип источника (channel, chat, forum_chat)
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CacheEntry':
        return cls(**data)


class CacheManager:
    """Унифицированный менеджер кэша для entity и processed links"""
    
    def __init__(self, cache_file: str = None):
        self.cache_file = cache_file or CACHE_FILE
        self.data: Dict[str, Any] = {
            'entity_cache': {},
            'processed_links': [],
            'topics_cache': {},  # NEW: кэш топиков для форум-чатов
            'metadata': {'version': '1.0', 'last_updated': None}
        }
        self.loaded = False
        
        cache_dir = os.path.dirname(self.cache_file)
        if cache_dir and not os.path.exists(cache_dir):
            os.makedirs(cache_dir, exist_ok=True)
            logger.info(f"Создана директория для кэша: {cache_dir}")
    
    def get_entity(self, channel_link: str) -> Optional[Dict[str, Any]]:
        """Получает entity из кэша"""
        entity_cache = self.data.get('entity_cache', {})
        entry_data = entity_cache.get(channel_link)
        
        if entry_data:
            logger.debug(f"Entity для {channel_link} найден в кэше")
        else:
            logger.debug(f"Entity для {channel_link} не найден в кэше")
        
        return entry_data
    
    def get_entity_with_type(self, channel_link: str) -> tuple[Optional[Dict[str, Any]], Optional[str]]:
        """
        Получает entity из кэша вместе с его типом
        
        Args:
            channel_link: Ссылка на канал/чат
            
        Returns:
            Кортеж (entity_data, source_type) или (None, None) если не найдено
        """
        entity_data = self.get_entity(channel_link)
        if entity_data:
            source_type = entity_data.get('source_type', 'channel')
            return entity_data, source_type
        return None, None
    
    def save_entity(self, channel_link: str, entity: Any, source_type: str = 'channel') -> None:
        """Сохраняет entity в кэш с метаданными source_type"""
        try:
            cache_entry = CacheEntry(
                channel_id=getattr(entity, 'id', 0),
                title=getattr(entity, 'title', ''),
                username=getattr(entity, 'username', ''),
                cached_at=datetime.now().isoformat(),
                source_type=source_type
            )
            
            if 'entity_cache' not in self.data:
                self.data['entity_cache'] = {}
            
            self.data['entity_cache'][channel_link] = cache_entry.to_dict()
            logger.debug(f"Entity для {channel_link} сохранен в кэш с типом {source_type}")
            
        except Exception as e:
            logger.error(f"Ошибка при сохранении entity в кэш: {e}")
    
    def is_entity_valid(self, channel_link: str, max_age_days: int = 7) -> bool:
        """Проверяет актуальность entity в кэше"""
        entity_data = self.get_entity(channel_link)
        if not entity_data:
            return False
        
        try:
            cached_at_str = entity_data.get('cached_at')
            if not cached_at_str:
                return False
            
            cached_at = datetime.fromisoformat(cached_at_str)
            age = datetime.now() - cached_at
            is_valid = age < timedelta(days=max_age_days)
            
            if is_valid:
                logger.debug(f"Entity для {channel_link} актуален ({age.days} дней)")
            else:
                logger.debug(f"Entity для {channel_link} устарел ({age.days} дней)")
            
            return is_valid
            
        except Exception as e:
            logger.error(f"Ошибка при проверке актуальности entity: {e}")
            return False
    
    def get_all_entities(self) -> Dict[str, Dict[str, Any]]:
        """Получает все entity из кэша"""
        return self.data.get('entity_cache', {})
    
    def clear_entity_cache(self) -> None:
        """Очищает кэш entity"""
        self.data['entity_cache'] = {}
        logger.info("Кэш entity очищен")
    
    def save_topics(self, chat_link: str, topics: list[tuple[int, str]]) -> None:
        """
        Сохраняет список топиков для форум-чата в кэш
        
        Args:
            chat_link: Ссылка на форум-чат
            topics: Список кортежей (topic_id, topic_title)
        """
        try:
            if 'topics_cache' not in self.data:
                self.data['topics_cache'] = {}
            
            self.data['topics_cache'][chat_link] = {
                'topics': topics,
                'cached_at': datetime.now().isoformat()
            }
            logger.debug(f"Топики для {chat_link} сохранены в кэш ({len(topics)} топиков)")
            
        except Exception as e:
            logger.error(f"Ошибка при сохранении топиков в кэш: {e}")
    
    def get_topics(self, chat_link: str) -> Optional[list[tuple[int, str]]]:
        """
        Получает закэшированные топики для форум-чата
        
        Args:
            chat_link: Ссылка на форум-чат
            
        Returns:
            Список кортежей (topic_id, topic_title) или None если не найдено
        """
        topics_cache = self.data.get('topics_cache', {})
        topics_data = topics_cache.get(chat_link)
        
        if topics_data:
            logger.debug(f"Топики для {chat_link} найдены в кэше")
            return topics_data.get('topics')
        else:
            logger.debug(f"Топики для {chat_link} не найдены в кэше")
            return None
    
    def is_topics_valid(self, chat_link: str, max_age_days: int = 7) -> bool:
        """
        Проверяет актуальность закэшированных топиков
        
        Args:
            chat_link: Ссылка на форум-чат
            max_age_days: Максимальный возраст кэша в днях
            
        Returns:
            True если топики актуальны, False иначе
        """
        topics_cache = self.data.get('topics_cache', {})
        topics_data = topics_cache.get(chat_link)
        
        if not topics_data:
            return False
        
        try:
            cached_at_str = topics_data.get('cached_at')
            if not cached_at_str:
                return False
            
            cached_at = datetime.fromisoformat(cached_at_str)
            age = datetime.now() - cached_at
            is_valid = age < timedelta(days=max_age_days)
            
            if is_valid:
                logger.debug(f"Топики для {chat_link} актуальны ({age.days} дней)")
            else:
                logger.debug(f"Топики для {chat_link} устарели ({age.days} дней)")
            
            return is_valid
            
        except Exception as e:
            logger.error(f"Ошибка при проверке актуальности топиков: {e}")
            return False
    
    def get_processed_links(self) -> Set[str]:
        """Получает множество обработанных ссылок"""
        links = self.data.get('processed_links', [])
        return set(links)
    
    def add_processed_link(self, link: str) -> None:
        """Добавляет ссылку в множество обработанных"""
        if 'processed_links' not in self.data:
            self.data['processed_links'] = []
        
        if link not in self.data['processed_links']:
            self.data['processed_links'].append(link)
            logger.debug(f"Ссылка {link} добавлена в обработанные")
    
    def remove_processed_link(self, link: str) -> bool:
        """Удаляет ссылку из обработанных"""
        if 'processed_links' in self.data and link in self.data['processed_links']:
            self.data['processed_links'].remove(link)
            logger.debug(f"Ссылка {link} удалена из обработанных")
            return True
        return False
    
    def clear_processed_links(self) -> None:
        """Очищает список обработанных ссылок"""
        self.data['processed_links'] = []
        logger.info("Список обработанных ссылок очищен")
    
    def load(self) -> Dict[str, Any]:
        """Загружает данные из файла кэша"""
        try:
            if os.path.exists(self.cache_file):
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    loaded_data = json.load(f)
                    
                    if 'entity_cache' not in loaded_data:
                        loaded_data = self._migrate_old_format(loaded_data)
                    
                    self.data = loaded_data
                    logger.info(f"Кэш успешно загружен из {self.cache_file}")
            else:
                logger.info(f"Файл кэша не найден, создан пустой кэш")
                self._init_empty_cache()
            
            self.loaded = True
            return self.data
            
        except json.JSONDecodeError as e:
            logger.error(f"Ошибка при декодировании JSON: {e}")
            self._backup_corrupted_cache()
            self._init_empty_cache()
            self.loaded = True
            return self.data
            
        except Exception as e:
            logger.error(f"Ошибка при загрузке кэша: {e}", exc_info=True)
            self._init_empty_cache()
            self.loaded = True
            return self.data
    
    def save(self) -> bool:
        """Сохраняет данные в файл кэша"""
        try:
            if 'metadata' not in self.data:
                self.data['metadata'] = {}
            self.data['metadata']['last_updated'] = datetime.now().isoformat()
            
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"Кэш успешно сохранен в {self.cache_file}")
            return True
            
        except (NameError, AttributeError):
            # Встроенные функции недоступны (завершение интерпретатора)
            return False
        except Exception as e:
            logger.error(f"Ошибка при сохранении кэша: {e}", exc_info=True)
            return False
    
    async def load_async(self) -> Dict[str, Any]:
        """Асинхронно загружает данные из файла кэша"""
        try:
            if os.path.exists(self.cache_file):
                async with aiofiles.open(self.cache_file, 'r', encoding='utf-8') as f:
                    content = await f.read()
                    try:
                        loaded_data = json.loads(content)
                        
                        if 'entity_cache' not in loaded_data:
                            loaded_data = self._migrate_old_format(loaded_data)
                        
                        self.data = loaded_data
                        logger.info(f"Кэш успешно загружен из {self.cache_file}")
                    except json.JSONDecodeError as e:
                        logger.error(f"Ошибка при декодировании JSON: {e}")
                        self._backup_corrupted_cache()
                        self._init_empty_cache()
            else:
                logger.info(f"Файл кэша не найден, создан пустой кэш")
                self._init_empty_cache()
            
            self.loaded = True
            return self.data
            
        except Exception as e:
            logger.error(f"Ошибка при асинхронной загрузке кэша: {e}", exc_info=True)
            self._init_empty_cache()
            return self.data
    
    async def save_async(self) -> bool:
        """Асинхронно сохраняет данные в файл кэша"""
        try:
            if 'metadata' not in self.data:
                self.data['metadata'] = {}
            self.data['metadata']['last_updated'] = datetime.now().isoformat()
            
            temp_file = f"{self.cache_file}.tmp"
            
            async with aiofiles.open(temp_file, 'w', encoding='utf-8') as f:
                await f.write(json.dumps(self.data, ensure_ascii=False, indent=2))
            
            if os.path.exists(self.cache_file):
                os.replace(temp_file, self.cache_file)
            else:
                os.rename(temp_file, self.cache_file)
            
            logger.info(f"Кэш успешно сохранен в {self.cache_file}")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка при асинхронном сохранении кэша: {e}", exc_info=True)
            return False
    
    def clear(self) -> None:
        """Очищает весь кэш"""
        self._init_empty_cache()
        self.data['metadata']['last_updated'] = datetime.now().isoformat()
        logger.info("Весь кэш очищен")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Получает статистику по кэшу"""
        return {
            'entity_count': len(self.data.get('entity_cache', {})),
            'processed_links_count': len(self.data.get('processed_links', [])),
            'topics_cache_count': len(self.data.get('topics_cache', {})),
            'last_updated': self.data.get('metadata', {}).get('last_updated', 'Никогда'),
            'cache_file': self.cache_file,
            'loaded': self.loaded
        }
    
    def _init_empty_cache(self) -> None:
        """Инициализирует пустой кэш"""
        self.data = {
            'entity_cache': {},
            'processed_links': [],
            'topics_cache': {},
            'metadata': {'version': '1.0', 'last_updated': None}
        }
    
    def _migrate_old_format(self, old_data: Dict[str, Any]) -> Dict[str, Any]:
        """Мигрирует старый формат кэша в новый"""
        logger.info("Миграция старого формата кэша в новый")
        
        # Мигрируем entity_cache, добавляя source_type='channel' для старых записей
        entity_cache = old_data.get('entity_cache', {})
        for link, entry in entity_cache.items():
            if 'source_type' not in entry:
                entry['source_type'] = 'channel'
        
        return {
            'entity_cache': entity_cache,
            'processed_links': old_data.get('processed_links', []),
            'topics_cache': old_data.get('topics_cache', {}),
            'metadata': {
                'version': '1.0',
                'last_updated': datetime.now().isoformat(),
                'migrated_from_old_format': True
            }
        }
    
    def _backup_corrupted_cache(self) -> None:
        """Создает резервную копию поврежденного файла кэша"""
        if os.path.exists(self.cache_file):
            backup_file = f"{self.cache_file}.bak.{datetime.now().strftime('%Y%m%d%H%M%S')}"
            try:
                os.rename(self.cache_file, backup_file)
                logger.info(f"Создана резервная копия: {backup_file}")
            except Exception as e:
                logger.error(f"Не удалось создать резервную копию: {e}")
    
    def __del__(self):
        """Автоматически сохраняет кэш при уничтожении объекта"""
        # При завершении интерпретатора встроенные функции могут быть недоступны,
        # поэтому оборачиваем в try/except с минимальными зависимостями
        try:
            if hasattr(self, 'loaded') and getattr(self, 'loaded', False):
                # Проверяем доступность необходимых модулей
                if hasattr(self, 'save'):
                    self.save()
        except (NameError, AttributeError, TypeError):
            # Игнорируем ошибки при завершении интерпретатора
            pass
        except Exception:
            pass
