# -*- coding: utf-8 -*-
"""
Модуль для управления подключением к Telegram API
"""

import os
import logging
from typing import Optional
from telethon import TelegramClient as TelethonClient
from python_socks import ProxyType
from src.config import SESSION_PATH, get_telegram_config
from src.utils.logger import setup_logger

logger = setup_logger(__name__)


class ConnectionManager:
    """
    Менеджер подключения к Telegram API
    Отвечает за установку соединения, авторизацию и управление клиентом
    """
    
    def __init__(self, session_path: Optional[str] = None):
        """
        Инициализация менеджера подключения
        
        Args:
            session_path: Путь к файлу сессии (если не указан, берется из конфигурации)
        """
        telegram_config = get_telegram_config()
        
        # Параметры API
        self.api_id = telegram_config['API_ID']
        self.api_hash = telegram_config['API_HASH']
        
        # Путь к сессии. Если явный путь не передан — используем
        # ``src.config.SESSION_PATH``, который учитывает
        # ``PARSER_SESSION_PATH`` env override от веб-панели.
        if session_path:
            self.session_path = session_path
        else:
            self.session_path = SESSION_PATH
        
        # Создаем директорию для сессий, если она не существует
        os.makedirs(os.path.dirname(self.session_path), exist_ok=True)
        
        # Настройка прокси
        self.proxy = None
        self.connection_type = None
        
        if telegram_config.get('PROXY_ENABLED', False):
            proxy_type_str = telegram_config.get('PROXY_TYPE', 'SOCKS5')
            proxy_host = telegram_config.get('PROXY_HOST')
            proxy_port = telegram_config.get('PROXY_PORT')
            
            if proxy_type_str == 'MTPROTO':
                # MTProto proxy требует специального connection type
                from telethon import connection
                self.connection_type = connection.ConnectionTcpMTProxyRandomizedIntermediate
                
                # MTProto proxy использует secret вместо username/password
                proxy_secret = telegram_config.get('PROXY_SECRET')
                if proxy_secret:
                    self.proxy = (proxy_host, proxy_port, proxy_secret)
                    logger.info(f"Прокси настроен: MTPROTO://{proxy_host}:{proxy_port}")
                else:
                    logger.error("MTPROTO proxy требует PROXY_SECRET в конфигурации")
                    raise ValueError("MTPROTO proxy требует PROXY_SECRET в конфигурации")
            else:
                # SOCKS5/SOCKS4/HTTP proxy
                proxy_username = telegram_config.get('PROXY_USERNAME')
                proxy_password = telegram_config.get('PROXY_PASSWORD')
                
                # Определяем тип прокси для python-socks
                if proxy_type_str == 'SOCKS5':
                    proxy_type = ProxyType.SOCKS5
                elif proxy_type_str == 'SOCKS4':
                    proxy_type = ProxyType.SOCKS4
                elif proxy_type_str == 'HTTP':
                    proxy_type = ProxyType.HTTP
                else:
                    proxy_type = ProxyType.SOCKS5
                
                # Формируем кортеж прокси для Telethon
                if proxy_username and proxy_password:
                    self.proxy = (proxy_type, proxy_host, proxy_port, True, proxy_username, proxy_password)
                    logger.info(f"Прокси настроен: {proxy_type_str}://{proxy_username}@{proxy_host}:{proxy_port}")
                else:
                    self.proxy = (proxy_type, proxy_host, proxy_port)
                    logger.info(f"Прокси настроен: {proxy_type_str}://{proxy_host}:{proxy_port}")
        
        # Инициализация клиента
        self.client: Optional[TelethonClient] = None
        self._connected = False
        
        logger.info(f"ConnectionManager инициализирован с сессией: {self.session_path}")
    
    async def connect(self) -> None:
        """
        Подключение к Telegram API
        
        Raises:
            Exception: Если не удалось подключиться или пользователь не авторизован
        """
        if self._connected:
            logger.debug("Клиент уже подключен")
            return
        
        try:
            # Создаем клиент, если еще не создан
            if not self.client:
                # Параметры для создания клиента
                client_kwargs = {
                    'proxy': self.proxy,
                    'timeout': 30,
                    'connection_retries': 5
                }
                
                # Для MTProto proxy добавляем connection type
                if self.connection_type:
                    client_kwargs['connection'] = self.connection_type
                
                self.client = TelethonClient(
                    self.session_path,
                    self.api_id,
                    self.api_hash,
                    **client_kwargs
                )
            
            # Подключаемся
            logger.info("Попытка подключения к Telegram API через прокси...")
            await self.client.connect()
            
            # Проверяем авторизацию
            if not await self.client.is_user_authorized():
                logger.error("Необходимо авторизоваться в Telegram! Запустите auth_telegram.py.")
                raise Exception("Необходимо авторизоваться в Telegram! Запустите auth_telegram.py.")
            
            self._connected = True
            logger.info("Успешно подключен к Telegram API")
            
        except Exception as e:
            logger.error(f"Ошибка при подключении к Telegram API: {e}")
            self._connected = False
            raise
    
    async def disconnect(self) -> None:
        """
        Отключение от Telegram API
        """
        if not self._connected:
            logger.debug("Клиент уже отключен")
            return
        
        try:
            if self.client and self.client.is_connected():
                await self.client.disconnect()
                logger.info("Клиент Telegram успешно отключён")
            
            self._connected = False
            
        except Exception as e:
            logger.error(f"Ошибка при отключении от Telegram API: {e}")
            raise
    
    def is_connected(self) -> bool:
        """
        Проверка статуса подключения
        
        Returns:
            True если подключен, False иначе
        """
        return self._connected and self.client is not None and self.client.is_connected()
    
    async def ensure_authorized(self) -> bool:
        """
        Проверка авторизации пользователя
        
        Returns:
            True если авторизован, False иначе
            
        Raises:
            Exception: Если клиент не подключен
        """
        if not self.is_connected():
            raise Exception("Клиент не подключен. Вызовите connect() перед проверкой авторизации.")
        
        try:
            is_authorized = await self.client.is_user_authorized()
            
            if is_authorized:
                logger.debug("Пользователь авторизован")
            else:
                logger.warning("Пользователь не авторизован")
            
            return is_authorized
            
        except Exception as e:
            logger.error(f"Ошибка при проверке авторизации: {e}")
            return False
    
    def get_client(self) -> TelethonClient:
        """
        Получение экземпляра Telethon клиента
        
        Returns:
            Экземпляр TelethonClient
            
        Raises:
            Exception: Если клиент не инициализирован или не подключен
        """
        if not self.client:
            raise Exception("Клиент не инициализирован. Вызовите connect() перед получением клиента.")
        
        if not self.is_connected():
            raise Exception("Клиент не подключен. Вызовите connect() перед получением клиента.")
        
        return self.client
    
    async def __aenter__(self):
        """Контекстный менеджер: вход"""
        await self.connect()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Контекстный менеджер: выход"""
        await self.disconnect()
        return False
