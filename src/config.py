# -*- coding: utf-8 -*-
"""
Конфигурация проекта: все пути и настройки централизованы здесь.
"""
import os
from pathlib import Path
from typing import Optional, Dict, Any
import json

# Базовый путь к проекту
BASE_DIR = Path(__file__).parent.parent.absolute()

# Пути к файлам и директориям
SESSIONS_DIR = os.path.join(BASE_DIR, 'sessions')
CACHE_DIR = os.path.join(BASE_DIR, 'cache')
LOG_DIR = os.path.join(BASE_DIR, 'logs')
EXPORT_DIR = os.path.join(BASE_DIR, 'exports')

# Создаем директории, если они не существуют
for directory in [SESSIONS_DIR, CACHE_DIR, LOG_DIR, EXPORT_DIR]:
    os.makedirs(directory, exist_ok=True)

# Файлы
SESSION_NAME = 'telegram_session'
SESSION_PATH = os.path.join(SESSIONS_DIR, f'{SESSION_NAME}.session')
CACHE_FILE = os.path.join(CACHE_DIR, 'cache.json')
LOG_FILE = os.path.join(LOG_DIR, 'parser.log')
CHANNELS_FILE = os.path.join(BASE_DIR, 'channels.txt')
CONFIG_FILE = os.path.join(BASE_DIR, 'config.json')

# Настройки Telegram API (по умолчанию, будут перезаписаны из config.json)
TELEGRAM_CONFIG = {
    'API_ID': None,
    'API_HASH': None,
    'MAX_CONCURRENT_CONNECTIONS': 1,
    'DELAY_BETWEEN_CHANNELS': 2,
    'RANDOMIZE_DELAY': False,  # Включить рандомизацию задержки между каналами
    'DELAY_BETWEEN_CHANNELS_MIN': 2,  # Минимальная задержка (сек)
    'DELAY_BETWEEN_CHANNELS_MAX': 5,  # Максимальная задержка (сек)
    # Оптимизация задержек
    'DELAY_BETWEEN_MESSAGES': 0.01,  # Задержка между сообщениями (сек)
    'DELAY_BETWEEN_COMMENTS': 0.1,  # Задержка между комментариями (сек)
    # Entity loading
    'LAZY_ENTITY_LOADING': True,  # Ленивая загрузка entity из первого сообщения
    'PREFETCH_ENTITIES': False,  # Предзагрузка entity батчами (опционально)
    'ENTITY_CACHE_MAX_AGE_DAYS': 7,  # Максимальный возраст кэша entity (дни)
}

# Настройки экспорта в Google Docs (по умолчанию, будут перезаписаны из config.json)
GOOGLE_CONFIG = {
    'CREDS_PATH': os.path.join(BASE_DIR, 'google-credentials.json'),
    'DOC_ID': None,
}

# Настройки парсинга (по умолчанию, будут перезаписаны из config.json)
PARSER_CONFIG = {
    'CHECK_INTERVAL': 3600,  # интервал проверки в секундах
    'DATE_RANGE_ENABLED': False,  # использовать ли диапазон дат вместо кол-ва дней
    'DAYS_FOR_EXPORT': 3,  # количество дней для выгрузки сообщений
    'START_DATE': None,  # начальная дата выгрузки (формат: 'DD-MM-YYYY')
    'END_DATE': None,  # конечная дата выгрузки (формат: 'DD-MM-YYYY')
    'FETCH_COMMENTS': True,  # получать ли комментарии к постам
    'FETCH_PREVIOUS_POSTS': True,  # получать ли ссылки на предыдущие посты
    'MAX_COMMENTS_PER_POST': 50,  # максимальное количество комментариев на пост
}

# Настройки интерфейса
UI_CONFIG = {
    'THEME': 'light',
    'LANGUAGE': 'ru',
}

# Настройки базы данных
DATABASE_CONFIG = {
    'DB_PATH': os.path.join(BASE_DIR, 'data', 'parser.db'),
    'BACKUP_ENABLED': True,
    'BACKUP_INTERVAL': 24,  # часы
    # Батчинг операций
    'BATCH_SIZE': 100,  # размер батча для вставки сообщений
    'USE_TRANSACTIONS': True,  # использовать транзакции для батчинга
}

# Настройки уведомлений
NOTIFICATIONS_CONFIG = {
    'ENABLED': False,
    'WEBHOOKS': {},
    'EMAIL_ENABLED': False
}

# Настройки кэша
CACHE_CONFIG = {
    'ENTITY_MAX_AGE_DAYS': 7,  # максимальный возраст кэша entity (дни)
    'AUTO_SAVE_INTERVAL': 10,  # интервал автосохранения кэша (количество операций)
}

# Настройки обработки ошибок
ERROR_HANDLING_CONFIG = {
    'MAX_RETRIES': 3,  # максимальное количество повторных попыток
    'EXPONENTIAL_BACKOFF_BASE': 2,  # база для экспоненциального backoff
    'LOG_FULL_CONTEXT': True,  # логировать полный контекст ошибок
}

# Настройки планировщика
SCHEDULER_CONFIG = {
    'ENABLED': False,
    'TASKS': []
}

# Настройки NotebookLM
NOTEBOOKLM_CONFIG = {
    'email': '',
    'password': '',
    'prompts_config': 'config/prompts.json',
    'timeout': 120,
    'max_retries': 3,
    'retry_delay_base': 2
}

# Настройки автоматизации
AUTOMATION_CONFIG = {
    'enabled': False,
    'target_chat_id': '',
    'schedule_enabled': True,
    'schedule_time': '09:00',
    'schedule_days': ['monday', 'tuesday', 'wednesday', 'thursday', 'friday'],
    'export_format': 'csv',
    'export_dir': 'exports',
    'cleanup_temp_files': True,
    'cleanup_notebooks': True,
    'parallel_generation': True,
    'send_error_notifications': True,
    'telegram_retry_delay': 5,
    'telegram_max_retries': 3,
    'telegram_message_max_length': 4096
}

# Объединенный словарь конфигурации
CONFIG: Dict[str, Any] = {
    'TELEGRAM': TELEGRAM_CONFIG,
    'GOOGLE': GOOGLE_CONFIG,
    'PARSER': PARSER_CONFIG,
    'UI': UI_CONFIG,
    'DATABASE': DATABASE_CONFIG,
    'NOTIFICATIONS': NOTIFICATIONS_CONFIG,
    'SCHEDULER': SCHEDULER_CONFIG,
    'CACHE': CACHE_CONFIG,
    'ERROR_HANDLING': ERROR_HANDLING_CONFIG,
    'NOTEBOOKLM': NOTEBOOKLM_CONFIG,
    'AUTOMATION': AUTOMATION_CONFIG,
}

def load_config() -> None:
    """Загружает настройки из JSON-файла конфигурации"""
    global CONFIG
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                user_config = json.load(f)
            
            # Валидация и применение значений по умолчанию
            from src.automation.config_validator import ConfigValidator
            validated_config = ConfigValidator.validate_and_apply(user_config)
            
            # Обновляем конфигурацию из файла
            for section in CONFIG:
                if section in validated_config:
                    CONFIG[section].update(validated_config[section])
                    
            print(f"Конфигурация загружена из {CONFIG_FILE}")
        except Exception as e:
            print(f"Ошибка при загрузке конфигурации из {CONFIG_FILE}: {e}")
    else:
        save_config()
        print(f"Создан новый файл конфигурации: {CONFIG_FILE}")

def save_config() -> None:
    """Сохраняет текущую конфигурацию в JSON-файл"""
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(CONFIG, f, ensure_ascii=False, indent=4)
    print(f"Конфигурация сохранена в {CONFIG_FILE}")

# Загружаем конфигурацию при импорте модуля
# load_config()  # Отложено - вызывается вручную при необходимости

# Функции для доступа к конфигурации
def get_telegram_config() -> Dict[str, Any]:
    """Возвращает настройки Telegram API"""
    if CONFIG['TELEGRAM']['API_ID'] is None:
        load_config()
    return CONFIG['TELEGRAM']

def get_google_config() -> Dict[str, Any]:
    """Возвращает настройки Google Docs API"""
    if CONFIG['TELEGRAM']['API_ID'] is None:
        load_config()
    return CONFIG['GOOGLE']

def get_parser_config() -> Dict[str, Any]:
    """Возвращает настройки парсинга"""
    if CONFIG['TELEGRAM']['API_ID'] is None:
        load_config()
    return CONFIG['PARSER']

def get_ui_config() -> Dict[str, Any]:
    """Возвращает настройки интерфейса"""
    if CONFIG['TELEGRAM']['API_ID'] is None:
        load_config()
    return CONFIG['UI']

def get_cache_config() -> Dict[str, Any]:
    """Возвращает настройки кэша"""
    if CONFIG['TELEGRAM']['API_ID'] is None:
        load_config()
    return CONFIG['CACHE']

def get_error_handling_config() -> Dict[str, Any]:
    """Возвращает настройки обработки ошибок"""
    if CONFIG['TELEGRAM']['API_ID'] is None:
        load_config()
    return CONFIG['ERROR_HANDLING']

def get_database_config() -> Dict[str, Any]:
    """Возвращает настройки базы данных"""
    if CONFIG['TELEGRAM']['API_ID'] is None:
        load_config()
    return CONFIG['DATABASE']

def get_notebooklm_config() -> Dict[str, Any]:
    """Возвращает настройки NotebookLM"""
    if CONFIG['TELEGRAM']['API_ID'] is None:
        load_config()
    return CONFIG['NOTEBOOKLM']

def get_automation_config() -> Dict[str, Any]:
    """Возвращает настройки автоматизации"""
    if CONFIG['TELEGRAM']['API_ID'] is None:
        load_config()
    return CONFIG['AUTOMATION']

def validate_config() -> bool:
    """Проверяет наличие всех необходимых настроек в конфигурации"""
    if CONFIG['TELEGRAM']['API_ID'] is None:
        load_config()
    
    # Проверка Telegram API
    if not CONFIG['TELEGRAM']['API_ID'] or not CONFIG['TELEGRAM']['API_HASH']:
        print("ОШИБКА: Не заданы API_ID или API_HASH для Telegram API")
        return False
    
    # Проверка Google API (только если используется экспорт в Google Docs)
    # Для автоматизации NotebookLM это не обязательно
    # if not CONFIG['GOOGLE']['DOC_ID']:
    #     print("ПРЕДУПРЕЖДЕНИЕ: Не задан DOC_ID для Google Docs API")
    
    # if not os.path.exists(CONFIG['GOOGLE']['CREDS_PATH']):
    #     print(f"ПРЕДУПРЕЖДЕНИЕ: Файл с учетными данными Google API не найден: {CONFIG['GOOGLE']['CREDS_PATH']}")
    
    # Проверка формата дат, если они указаны
    if CONFIG['PARSER']['DATE_RANGE_ENABLED']:
        if not CONFIG['PARSER']['START_DATE'] or not CONFIG['PARSER']['END_DATE']:
            print("ОШИБКА: При включенном DATE_RANGE_ENABLED должны быть указаны START_DATE и END_DATE")
            return False
        
        try:
            from datetime import datetime
            if CONFIG['PARSER']['START_DATE']:
                datetime.strptime(CONFIG['PARSER']['START_DATE'], '%d-%m-%Y')
            if CONFIG['PARSER']['END_DATE']:
                datetime.strptime(CONFIG['PARSER']['END_DATE'], '%d-%m-%Y')
        except ValueError:
            print("ОШИБКА: Неверный формат даты в конфигурации. Используйте формат 'ДД-ММ-ГГГГ'")
            return False
    
    # Проверка параметров оптимизации
    if CONFIG['TELEGRAM']['DELAY_BETWEEN_MESSAGES'] < 0:
        print("ОШИБКА: DELAY_BETWEEN_MESSAGES не может быть отрицательным")
        return False
    
    if CONFIG['TELEGRAM']['DELAY_BETWEEN_COMMENTS'] < 0:
        print("ОШИБКА: DELAY_BETWEEN_COMMENTS не может быть отрицательным")
        return False
    
    # Проверка параметров батчинга
    if CONFIG['DATABASE']['BATCH_SIZE'] <= 0:
        print("ОШИБКА: BATCH_SIZE должен быть положительным числом")
        return False
    
    # Проверка параметров кэша
    if CONFIG['CACHE']['ENTITY_MAX_AGE_DAYS'] <= 0:
        print("ОШИБКА: ENTITY_MAX_AGE_DAYS должен быть положительным числом")
        return False
    
    # Проверка параметров обработки ошибок
    if CONFIG['ERROR_HANDLING']['MAX_RETRIES'] < 0:
        print("ОШИБКА: MAX_RETRIES не может быть отрицательным")
        return False
    
    if CONFIG['ERROR_HANDLING']['EXPONENTIAL_BACKOFF_BASE'] <= 1:
        print("ОШИБКА: EXPONENTIAL_BACKOFF_BASE должен быть больше 1")
        return False
    
    # Проверка NotebookLM конфигурации
    if CONFIG.get('NOTEBOOKLM'):
        if not CONFIG['NOTEBOOKLM'].get('email') or not CONFIG['NOTEBOOKLM'].get('password'):
            print("ПРЕДУПРЕЖДЕНИЕ: Учетные данные NotebookLM не заданы (email или password)")
        
        if CONFIG['NOTEBOOKLM'].get('timeout', 0) <= 0:
            print("ОШИБКА: NotebookLM timeout должен быть положительным числом")
            return False
        
        if CONFIG['NOTEBOOKLM'].get('max_retries', -1) < 0:
            print("ОШИБКА: NotebookLM max_retries не может быть отрицательным")
            return False
    
    # Проверка Automation конфигурации
    if CONFIG.get('AUTOMATION'):
        if CONFIG['AUTOMATION'].get('enabled', False):
            if not CONFIG['AUTOMATION'].get('target_chat_id'):
                print("ОШИБКА: target_chat_id должен быть задан при включенной автоматизации")
                return False
        
        export_format = CONFIG['AUTOMATION'].get('export_format', 'csv')
        if export_format not in ['csv', 'json']:
            print(f"ОШИБКА: Невалидный формат экспорта: {export_format}")
            return False
        
        if CONFIG['AUTOMATION'].get('telegram_max_retries', -1) < 0:
            print("ОШИБКА: telegram_max_retries не может быть отрицательным")
            return False
        
        if CONFIG['AUTOMATION'].get('telegram_message_max_length', 0) <= 0:
            print("ОШИБКА: telegram_message_max_length должен быть положительным числом")
            return False
    
    return True
