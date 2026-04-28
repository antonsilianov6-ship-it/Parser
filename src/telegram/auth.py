# -*- coding: utf-8 -*-
"""
Модуль для аутентификации в Telegram API
"""
import asyncio
import os
import sys
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError
from src.config import get_telegram_config, SESSION_PATH
from src.utils.logger import setup_logger

logger = setup_logger(__name__)

async def authenticate():
    """
    Интерактивная аутентификация в Telegram API
    """
    telegram_config = get_telegram_config()
    api_id = telegram_config['API_ID']
    api_hash = telegram_config['API_HASH']
    
    if not api_id or not api_hash:
        logger.error("API_ID или API_HASH не указаны в конфигурации.")
        print("Пожалуйста, укажите API_ID и API_HASH в конфигурационном файле.")
        return False
    
    # Создаем директорию для сессий, если она не существует
    os.makedirs(os.path.dirname(SESSION_PATH), exist_ok=True)
    
    logger.info(f"Начало аутентификации с сессией {SESSION_PATH}")
    client = TelegramClient(SESSION_PATH, api_id, api_hash)
    
    try:
        await client.connect()
        
        if await client.is_user_authorized():
            logger.info("Уже авторизован, сессия действительна.")
            print("Вы уже авторизованы в Telegram.")
            await client.disconnect()
            return True
        
        print("Требуется авторизация в Telegram.")
        
        # Запрашиваем номер телефона
        phone = input("Введите ваш номер телефона в международном формате (например, +7XXXXXXXXXX): ")
        
        # Отправляем код подтверждения
        await client.send_code_request(phone)
        
        # Запрашиваем код подтверждения
        code = input("Введите полученный код подтверждения: ")
        
        try:
            # Пытаемся войти с полученным кодом
            await client.sign_in(phone, code)
        except SessionPasswordNeededError:
            # Если аккаунт защищен двухфакторной аутентификацией
            password = input("Введите пароль двухфакторной аутентификации: ")
            await client.sign_in(password=password)
        
        logger.info("Аутентификация успешно завершена")
        print("Аутентификация успешно завершена!")
        
        await client.disconnect()
        return True
        
    except Exception as e:
        logger.error(f"Ошибка при аутентификации: {e}")
        print(f"Ошибка при аутентификации: {e}")
        
        # Пытаемся отключиться, если клиент был подключен
        try:
            await client.disconnect()
        except:
            pass
            
        return False

def main():
    """
    Точка входа для запуска скрипта аутентификации
    """
    print("Запуск процесса аутентификации в Telegram...")
    result = asyncio.run(authenticate())
    
    if result:
        print("Аутентификация успешно завершена. Теперь вы можете запустить парсер.")
        sys.exit(0)
    else:
        print("Аутентификация не удалась. Проверьте логи для получения дополнительной информации.")
        sys.exit(1)

if __name__ == "__main__":
    main() 