# -*- coding: utf-8 -*-
"""
AllInclusiveParser - Утилита для исправления кодировки файлов
"""
import os
import sys
import re
import logging
from pathlib import Path
from datetime import datetime

# Настраиваем логирование
def setup_logging():
    """Настраивает логирование"""
    if not os.path.exists('logs'):
        os.makedirs('logs', exist_ok=True)
    
    log_file = os.path.join('logs', f'encoding_fix_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    return logging.getLogger(__name__)

# Список расширений файлов для обработки
FILE_EXTENSIONS = ['.py', '.txt', '.md', '.bat', '.json']

# Список путей для исключения
EXCLUDE_PATHS = ['venv', 'logs', '__pycache__', 'sessions', 'cache', 'exports']

def should_process_file(file_path):
    """Проверяет, нужно ли обрабатывать файл"""
    path_obj = Path(file_path)
    
    # Проверяем расширение
    if path_obj.suffix.lower() not in FILE_EXTENSIONS:
        return False
    
    # Проверяем исключаемые пути
    for exclude_path in EXCLUDE_PATHS:
        if exclude_path in str(path_obj):
            return False
            
    return True

def detect_encoding(file_path):
    """Определяет кодировку файла"""
    encodings = ['utf-8', 'cp1251', 'latin-1', 'cp866']
    
    for enc in encodings:
        try:
            with open(file_path, 'r', encoding=enc) as f:
                content = f.read()
                # Проверяем наличие кириллических символов
                if re.search('[а-яА-Я]', content):
                    return enc, content
        except UnicodeDecodeError:
            continue
    
    return None, None

def fix_encoding_in_file(file_path, logger):
    """Исправляет кодировку в файле"""
    original_encoding, content = detect_encoding(file_path)
    
    if original_encoding is None:
        logger.warning(f"Не удалось определить кодировку файла: {file_path}")
        return False
    
    if original_encoding != 'utf-8':
        logger.info(f"Конвертирую файл из {original_encoding} в UTF-8: {file_path}")
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            # Добавляем команду chcp 65001 в .bat файлы, если ее еще нет
            if file_path.endswith('.bat'):
                with open(file_path, 'r', encoding='utf-8') as f:
                    bat_content = f.read()
                
                if 'chcp 65001' not in bat_content:
                    bat_content = re.sub(r'@echo off(\r?\n)', '@echo off\\1chcp 65001 > nul\\1', bat_content)
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(bat_content)
                    logger.info(f"Добавлена команда chcp 65001 в файл: {file_path}")
            
            return True
        except Exception as e:
            logger.error(f"Ошибка при конвертации файла {file_path}: {e}")
            return False
    else:
        # Проверяем bat-файлы даже с utf-8 кодировкой на наличие команды chcp
        if file_path.endswith('.bat'):
            with open(file_path, 'r', encoding='utf-8') as f:
                bat_content = f.read()
            
            if 'chcp 65001' not in bat_content:
                bat_content = re.sub(r'@echo off(\r?\n)', '@echo off\\1chcp 65001 > nul\\1', bat_content)
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(bat_content)
                logger.info(f"Добавлена команда chcp 65001 в файл: {file_path}")
                return True
        
        logger.info(f"Файл уже в UTF-8 кодировке: {file_path}")
        return False

def scan_directory(directory, logger):
    """Сканирует директорию и исправляет кодировку в файлах"""
    fixed_files = 0
    scanned_files = 0
    
    for root, _, files in os.walk(directory):
        for file in files:
            file_path = os.path.join(root, file)
            
            if should_process_file(file_path):
                scanned_files += 1
                if fix_encoding_in_file(file_path, logger):
                    fixed_files += 1
    
    return scanned_files, fixed_files

def main():
    """Основная функция"""
    logger = setup_logging()
    logger.info("Запуск утилиты исправления кодировки...")
    
    try:
        start_time = datetime.now()
        # Получаем корневую директорию проекта (на уровень выше scripts/)
        current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        logger.info(f"Сканирование директории: {current_dir}")
        scanned_files, fixed_files = scan_directory(current_dir, logger)
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        logger.info(f"Обработка завершена за {duration:.2f} секунд")
        logger.info(f"Просканировано файлов: {scanned_files}")
        logger.info(f"Исправлено файлов: {fixed_files}")
        
    except Exception as e:
        logger.error(f"Произошла ошибка: {e}", exc_info=True)
        return False
    
    return True

if __name__ == "__main__":
    success = main()
    print("\nИсправление кодировки завершено.")
    if success:
        print("Все файлы успешно обработаны.")
    else:
        print("При обработке некоторых файлов возникли ошибки. Проверьте лог для получения деталей.")
    
    input("\nНажмите Enter для выхода...")
    sys.exit(0 if success else 1) 