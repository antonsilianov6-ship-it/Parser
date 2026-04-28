# -*- coding: utf-8 -*-
"""
Модуль для работы с кэшированием данных
"""
import json
import os
import asyncio
import aiofiles
from typing import Dict, Set, Any, Optional, Union
from src.config import CACHE_FILE
from src.utils.logger import setup_logger
from datetime import datetime

logger = setup_logger(__name__)

class Cache:
    """
    Класс для работы с кэшем
    
    Поддерживает синхронное и асинхронное API для работы с кэшем
    """
    def __init__(self, cache_file: str = CACHE_FILE):
        self.cache_file = cache_file
        self.data: Dict[str, Any] = {}
        self.loaded = False
        
        # Создаем директорию для кэша, если ее нет
        cache_dir = os.path.dirname(self.cache_file)
        if not os.path.exists(cache_dir):
            os.makedirs(cache_dir, exist_ok=True)
            logger.info(f"Создана директория для кэша: {cache_dir}")
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Получает значение из кэша по ключу
        
        Args:
            key: Ключ для получения значения
            default: Значение по умолчанию, если ключ не найден
            
        Returns:
            Значение из кэша или значение по умолчанию
        """
        return self.data.get(key, default)
    
    def set(self, key: str, value: Any) -> None:
        """
        Устанавливает значение в кэш по ключу
        
        Args:
            key: Ключ для установки значения
            value: Значение для установки
        """
        self.data[key] = value
    
    def delete(self, key: str) -> bool:
        """
        Удаляет значение из кэша по ключу
        
        Args:
            key: Ключ для удаления
            
        Returns:
            True, если ключ был удален, иначе False
        """
        if key in self.data:
            del self.data[key]
            return True
        return False
    
    def has_key(self, key: str) -> bool:
        """
        Проверяет наличие ключа в кэше
        
        Args:
            key: Ключ для проверки
            
        Returns:
            True, если ключ существует, иначе False
        """
        return key in self.data
    
    def clear(self) -> None:
        """Очищает кэш"""
        self.data = {}
        logger.info("Кэш очищен")
    
    def load(self) -> Dict[str, Any]:
        """
        Загружает данные из файла кэша
        
        Returns:
            Словарь с данными кэша
        """
        try:
            if os.path.exists(self.cache_file):
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    self.data = json.load(f)
                logger.info(f"Кэш успешно загружен из {self.cache_file}")
            else:
                logger.info(f"Файл кэша {self.cache_file} не найден, создан пустой кэш")
                self.data = {}
            
            self.loaded = True
            return self.data
        except json.JSONDecodeError:
            logger.error(f"Ошибка при декодировании JSON из файла кэша {self.cache_file}. Создан новый кэш.")
            self.data = {}
            # Создаем резервную копию поврежденного файла
            if os.path.exists(self.cache_file):
                backup_file = f"{self.cache_file}.bak.{datetime.now().strftime('%Y%m%d%H%M%S')}"
                try:
                    os.rename(self.cache_file, backup_file)
                    logger.info(f"Создана резервная копия поврежденного файла кэша: {backup_file}")
                except Exception as e:
                    logger.error(f"Не удалось создать резервную копию файла кэша: {e}")
            return self.data
        except Exception as e:
            logger.error(f"Ошибка при загрузке кэша: {e}", exc_info=True)
            self.data = {}
            return self.data
    
    def save(self) -> bool:
        """
        Сохраняет данные в файл кэша
        
        Returns:
            True, если сохранение прошло успешно, иначе False
        """
        try:
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, ensure_ascii=False, indent=4)
            logger.info(f"Кэш успешно сохранен в {self.cache_file}")
            return True
        except Exception as e:
            logger.error(f"Ошибка при сохранении кэша: {e}", exc_info=True)
            return False
    
    async def load_async(self) -> Dict[str, Any]:
        """
        Асинхронно загружает данные из файла кэша
        
        Returns:
            Словарь с данными кэша
        """
        try:
            if os.path.exists(self.cache_file):
                async with aiofiles.open(self.cache_file, 'r', encoding='utf-8') as f:
                    content = await f.read()
                    try:
                        self.data = json.loads(content)
                    except json.JSONDecodeError:
                        logger.error(f"Ошибка при декодировании JSON из файла кэша {self.cache_file}. Создан новый кэш.")
                        self.data = {}
                        # Создаем резервную копию поврежденного файла
                        backup_file = f"{self.cache_file}.bak.{datetime.now().strftime('%Y%m%d%H%M%S')}"
                        try:
                            os.rename(self.cache_file, backup_file)
                            logger.info(f"Создана резервная копия поврежденного файла кэша: {backup_file}")
                        except Exception as e:
                            logger.error(f"Не удалось создать резервную копию файла кэша: {e}")
                logger.info(f"Кэш успешно загружен из {self.cache_file}")
            else:
                logger.info(f"Файл кэша {self.cache_file} не найден, создан пустой кэш")
                self.data = {}
            
            self.loaded = True
            return self.data
        except Exception as e:
            logger.error(f"Ошибка при асинхронной загрузке кэша: {e}", exc_info=True)
            self.data = {}
            return self.data
    
    async def save_async(self) -> bool:
        """
        Асинхронно сохраняет данные в файл кэша
        
        Returns:
            True, если сохранение прошло успешно, иначе False
        """
        try:
            # Создаем временный файл для безопасного сохранения
            temp_file = f"{self.cache_file}.tmp"
            
            # Сохраняем во временный файл
            async with aiofiles.open(temp_file, 'w', encoding='utf-8') as f:
                await f.write(json.dumps(self.data, ensure_ascii=False, indent=4))
            
            # Переименовываем временный файл в основной
            if os.path.exists(self.cache_file):
                os.replace(temp_file, self.cache_file)
            else:
                os.rename(temp_file, self.cache_file)
                
            logger.info(f"Кэш успешно сохранен в {self.cache_file}")
            return True
        except Exception as e:
            logger.error(f"Ошибка при асинхронном сохранении кэша: {e}", exc_info=True)
            return False
    
    def add_to_set(self, key: str, value: Any) -> None:
        """
        Добавляет значение в множество по ключу
        
        Args:
            key: Ключ множества
            value: Значение для добавления
        """
        if key not in self.data:
            self.data[key] = []
        
        if value not in self.data[key]:
            self.data[key].append(value)
    
    def remove_from_set(self, key: str, value: Any) -> bool:
        """
        Удаляет значение из множества по ключу
        
        Args:
            key: Ключ множества
            value: Значение для удаления
            
        Returns:
            True, если значение было удалено, иначе False
        """
        if key in self.data and value in self.data[key]:
            self.data[key].remove(value)
            return True
        return False
    
    def get_set(self, key: str) -> Set[Any]:
        """
        Получает множество по ключу
        
        Args:
            key: Ключ множества
            
        Returns:
            Множество значений
        """
        return set(self.data.get(key, []))
    
    def auto_save(self) -> None:
        """
        Автоматически сохраняет кэш, если он был изменен
        """
        if self.loaded:
            self.save()
    
    def __del__(self):
        """
        Автоматически сохраняет кэш при уничтожении объекта
        """
        if hasattr(self, 'loaded') and self.loaded:
            self.save()
    
    def get_processed_links(self) -> Set[str]:
        """
        Получает множество обработанных ссылок
        
        Returns:
            Множество обработанных ссылок
        """
        return set(self.get('processed_links', []))
    
    def add_processed_link(self, link: str) -> None:
        """
        Добавляет ссылку в множество обработанных
        
        Args:
            link: Ссылка для добавления
        """
        processed_links = self.get_processed_links()
        processed_links.add(link)
        self.set('processed_links', list(processed_links))
        
    def get_entity_cache(self) -> Dict[str, Any]:
        """
        Получает кэш entity для Telegram
        
        Returns:
            Словарь с кэшем entity
        """
        return self.get('entity_cache', {}) 