# -*- coding: utf-8 -*-
"""
Модуль для настройки логирования
"""
import logging
import sys
import os
from logging.handlers import RotatingFileHandler
from datetime import datetime

# Константы для логирования (избегаем циклического импорта)
LOG_DIR = "logs"
LOG_FILE = os.path.join(LOG_DIR, "parser.log")


class SafeRotatingFileHandler(RotatingFileHandler):
    """
    Безопасный RotatingFileHandler для Windows, который обрабатывает ошибки блокировки файлов
    """
    def doRollover(self):
        """
        Выполняет ротацию файла с обработкой ошибок блокировки на Windows
        """
        try:
            super().doRollover()
        except (OSError, PermissionError) as e:
            # Если файл заблокирован другим процессом, просто продолжаем писать в текущий файл
            # Это безопасно, так как файл просто станет немного больше
            pass


def setup_logger(name: str = None, level: int = logging.INFO) -> logging.Logger:
    """
    Настройка и получение логгера
    
    Args:
        name: Имя логгера (если None, используется корневой логгер)
        level: Уровень логирования
        
    Returns:
        Настроенный логгер
    """
    # Создаем директорию для логов, если она не существует
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    
    # Настраиваем форматирование
    formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
    
    # Настраиваем обработчик файла с безопасной ротацией
    file_handler = SafeRotatingFileHandler(
        LOG_FILE, 
        maxBytes=5*1024*1024,  # 5 МБ
        backupCount=3,  # хранить до 3 файлов ротации
        encoding='utf-8',
        delay=True  # Отложенное открытие файла для уменьшения блокировок
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(level)
    
    # Настраиваем обработчик для вывода в консоль
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(level)
    
    # Получаем логгер
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Проверяем, есть ли уже обработчики (избегаем дублирования)
    if not logger.handlers:
        # Добавляем обработчики только если их еще нет
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
    
    # Предотвращаем распространение логов к родительскому логгеру
    logger.propagate = False
    
    return logger

# Настраиваем корневой логгер при импорте модуля
root_logger = setup_logger() 