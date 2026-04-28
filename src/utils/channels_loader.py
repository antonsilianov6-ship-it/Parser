# -*- coding: utf-8 -*-
"""
Модуль для загрузки списка каналов из файла
"""
import os
from typing import List, Set
from src.config import CHANNELS_FILE
from src.utils.logger import setup_logger

logger = setup_logger(__name__)

def load_channels(file_path: str = CHANNELS_FILE) -> List[str]:
    """
    Загружает список каналов из файла
    
    Args:
        file_path: Путь к файлу со списком каналов
        
    Returns:
        Список каналов
    """
    logger.info(f"Загрузка списка каналов из файла {file_path}")
    
    if not os.path.exists(file_path):
        logger.error(f"Файл {file_path} не существует")
        return []
    
    try:
        with open(file_path, encoding='utf-8') as f:
            channels = [
                line.strip().replace('"', '').replace("'", '')
                for line in f
                if line.strip() and not line.strip().startswith('#')
            ]
        logger.info(f"Загружено {len(channels)} каналов из файла {file_path}")
        return channels
    except Exception as e:
        logger.error(f"Ошибка при загрузке списка каналов: {e}", exc_info=True)
        return []
    
def load_channels_as_set(file_path: str = CHANNELS_FILE) -> Set[str]:
    """
    Загружает множество каналов из файла
    
    Args:
        file_path: Путь к файлу со списком каналов
        
    Returns:
        Множество каналов
    """
    return set(load_channels(file_path))

def create_default_channels_file(file_path: str = CHANNELS_FILE) -> None:
    """
    Создает файл со списком каналов по умолчанию, если он не существует
    
    Args:
        file_path: Путь к файлу со списком каналов
    """
    if not os.path.exists(file_path):
        logger.info(f"Создание файла каналов по умолчанию: {file_path}")
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write("# Список каналов для парсинга (по одному на строку)\n")
                f.write("# Строки, начинающиеся с # - комментарии и игнорируются\n")
                f.write("# Примеры:\n")
                f.write("# https://t.me/channel1\n")
                f.write("# https://t.me/channel2\n")
            logger.info(f"Файл каналов по умолчанию создан: {file_path}")
        except Exception as e:
            logger.error(f"Ошибка при создании файла каналов: {e}", exc_info=True) 