# -*- coding: utf-8 -*-
"""
Скрипт для авторизации в Telegram API и сохранения сессии
"""
import os
import sys
import asyncio
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError

# Добавляем путь к корневой директории проекта
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config import get_telegram_config

async def main():
    """Основная функция для авторизации в Telegram"""
    print("=" * 70)
    print("Авторизация в Telegram API")
    print("=" * 70)
    
    telegram_config = get_telegram_config()
    api_id = telegram_config['API_ID']
    api_hash = telegram_config['API_HASH']
    
    if not api_id or not api_hash:
        print("ОШИБКА: API_ID и API_HASH не заданы в config.json.")
        print("Пожалуйста, добавьте эти значения в файл config.json и повторите попытку.")
        return
    
    # Создаем директорию для сессий, если она не существует
    sessions_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'sessions')
    os.makedirs(sessions_dir, exist_ok=True)
    
    session_path = os.path.join(sessions_dir, 'telegram_session')
    
    print(f"Используем API_ID: {api_id}")
    print(f"Используем API_HASH: {api_hash}")
    print(f"Файл сессии будет сохранен в: {session_path}.session")
    print("\nНачинаем процесс авторизации...")
    
    client = TelegramClient(session_path, api_id, api_hash)
    
    try:
        await client.connect()
        
        if await client.is_user_authorized():
            print("\nВы уже авторизованы в Telegram API.")
            print("Текущая сессия действительна и может использоваться для парсинга.")
        else:
            print("\nНеобходима авторизация через номер телефона.")
            phone = input("Введите ваш номер телефона в международном формате (например, +79031234567): ")
            
            try:
                await client.send_code_request(phone)
                code = input("Введите код подтверждения, отправленный в Telegram: ")
                
                try:
                    await client.sign_in(phone, code)
                except SessionPasswordNeededError:
                    print("\nОбнаружена двухфакторная аутентификация.")
                    password = input("Введите пароль двухфакторной аутентификации: ")
                    await client.sign_in(password=password)
                
                print("\nАвторизация успешно завершена!")
                print("Теперь вы можете использовать парсер для получения сообщений из каналов.")
            except Exception as e:
                print(f"\nОшибка при авторизации: {e}")
                print("Пожалуйста, попробуйте снова позже или проверьте правильность вводимых данных.")
    except Exception as e:
        print(f"\nНе удалось подключиться к Telegram API: {e}")
        print("Проверьте ваше подключение к интернету и правильность API_ID/API_HASH.")
    finally:
        await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main()) 