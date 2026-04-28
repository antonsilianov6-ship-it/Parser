# -*- coding: utf-8 -*-
"""Клиент для взаимодействия с NotebookLM API"""

import asyncio
from typing import Dict, Optional, Any
from pathlib import Path
from notebooklm import NotebookLMClient as NLMClient
from src.utils.error_handler import ErrorHandler
from src.utils.logger import setup_logger

logger = setup_logger(__name__)


class NotebookLMAPIError(Exception):
    """Ошибка при работе с NotebookLM API"""
    pass


class AuthenticationError(Exception):
    """Ошибка аутентификации NotebookLM"""
    pass


class NotebookLMClient:
    """Клиент для взаимодействия с NotebookLM API"""
    
    def __init__(self, credentials: Dict[str, str]):
        """
        Инициализация клиента
        
        Args:
            credentials: Словарь с учетными данными (не используется, оставлен для совместимости)
        
        Raises:
            AuthenticationError: При невалидных учетных данных
        
        Note:
            Клиент использует сохраненные данные аутентификации из ~/.notebooklm/storage_state.json
            Для первоначальной аутентификации выполните: notebooklm login
        """
        self.error_handler = ErrorHandler()
        self._client: Optional[NLMClient] = None
        self._credentials = credentials
        self._initialized = False
        self._context_entered = False
        
        logger.info("Инициализация NotebookLM клиента...")
        logger.info("Используются сохраненные данные аутентификации из ~/.notebooklm/storage_state.json")
        
        # Клиент будет инициализирован асинхронно при первом использовании
        # Это необходимо, так как from_storage() - асинхронная функция
    
    async def _ensure_initialized(self):
        """
        Обеспечивает инициализацию клиента (вызывается автоматически при первом использовании)
        
        Raises:
            AuthenticationError: При ошибке инициализации
        """
        if self._initialized:
            return
        
        try:
            # Используем from_storage() для загрузки сохраненных данных аутентификации
            self._client = await NLMClient.from_storage()
            self._initialized = True
            logger.info("✓ NotebookLM клиент успешно инициализирован")
        except FileNotFoundError as e:
            error_msg = (
                "Файл аутентификации не найден. "
                "Выполните команду 'notebooklm login' для первоначальной аутентификации."
            )
            logger.error(error_msg)
            self.error_handler.log_error(e, {
                'operation': 'client_initialization',
                'error_type': 'FileNotFoundError'
            })
            raise AuthenticationError(error_msg) from e
        except Exception as e:
            error_msg = f"Ошибка инициализации NotebookLM клиента: {str(e)}"
            logger.error(error_msg)
            self.error_handler.log_error(e, {
                'operation': 'client_initialization',
                'error_type': type(e).__name__
            })
            raise AuthenticationError(error_msg) from e
    
    async def __aenter__(self):
        """Вход в асинхронный контекстный менеджер"""
        await self._ensure_initialized()
        if self._client:
            await self._client.__aenter__()
            self._context_entered = True
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Выход из асинхронного контекстного менеджера"""
        if self._client and self._context_entered:
            await self._client.__aexit__(exc_type, exc_val, exc_tb)
            self._context_entered = False
        return False
    
    def is_authenticated(self) -> bool:
        """
        Проверяет наличие активной сессии
        
        Returns:
            True если клиент инициализирован, False иначе
        """
        return self._initialized
    
    async def create_notebook(self, title: str) -> str:
        """
        Создает новый ноутбук
        
        Args:
            title: Название ноутбука
        
        Returns:
            ID созданного ноутбука
        
        Raises:
            NotebookLMAPIError: При ошибке API
            RuntimeError: Если клиент не инициализирован в контексте async with
        """
        if not self._context_entered:
            raise RuntimeError("Client not initialized. Use 'async with' context.")
        
        max_retries = 3
        base_delay = 2
        
        for attempt in range(1, max_retries + 1):
            try:
                logger.info(f"Создание ноутбука '{title}' (попытка {attempt}/{max_retries})...")
                
                # Используем API библиотеки notebooklm-py
                notebook = await self._client.notebooks.create(title)
                
                logger.info(f"✓ Ноутбук создан: {notebook.id}")
                return notebook.id
                
            except Exception as e:
                if attempt < max_retries:
                    delay = base_delay ** attempt
                    logger.warning(
                        f"Ошибка при создании ноутбука (попытка {attempt}/{max_retries}): {str(e)}. "
                        f"Повтор через {delay} секунд..."
                    )
                    await asyncio.sleep(delay)
                else:
                    error_msg = f"Не удалось создать ноутбук после {max_retries} попыток: {str(e)}"
                    logger.error(error_msg)
                    self.error_handler.log_error(e, {
                        'operation': 'create_notebook',
                        'title': title,
                        'attempts': max_retries
                    })
                    raise NotebookLMAPIError(error_msg) from e
    
    async def delete_notebook(self, notebook_id: str) -> bool:
        """
        Удаляет ноутбук
        
        Args:
            notebook_id: ID ноутбука
        
        Returns:
            True если удаление успешно, False иначе
        """
        if not self._context_entered:
            raise RuntimeError("Client not initialized. Use 'async with' context.")
        
        max_retries = 3
        base_delay = 2
        
        for attempt in range(1, max_retries + 1):
            try:
                logger.info(f"Удаление ноутбука {notebook_id} (попытка {attempt}/{max_retries})...")
                
                # Используем API библиотеки notebooklm-py
                await self._client.notebooks.delete(notebook_id)
                
                logger.info(f"✓ Ноутбук {notebook_id} успешно удален")
                return True
                
            except Exception as e:
                if attempt < max_retries:
                    delay = base_delay ** attempt
                    logger.warning(
                        f"Ошибка при удалении ноутбука (попытка {attempt}/{max_retries}): {str(e)}. "
                        f"Повтор через {delay} секунд..."
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.warning(
                        f"Не удалось удалить ноутбук после {max_retries} попыток: {str(e)}"
                    )
                    self.error_handler.log_error(e, {
                        'operation': 'delete_notebook',
                        'notebook_id': notebook_id,
                        'attempts': max_retries
                    })
                    return False
    
    async def add_source(
        self, 
        notebook_id: str, 
        file_path: str, 
        file_type: str
    ) -> str:
        """
        Добавляет источник данных в ноутбук
        
        Args:
            notebook_id: ID ноутбука
            file_path: Путь к файлу
            file_type: Тип файла ('csv' или 'json')
        
        Returns:
            ID источника данных
        
        Raises:
            NotebookLMAPIError: При ошибке API
            FileNotFoundError: Если файл не найден
            RuntimeError: Если клиент не инициализирован в контексте async with
        """
        if not self._context_entered:
            raise RuntimeError("Client not initialized. Use 'async with' context.")
        
        # Проверка существования файла
        if not Path(file_path).exists():
            raise FileNotFoundError(f"Файл не найден: {file_path}")
        
        max_retries = 3
        base_delay = 2
        
        for attempt in range(1, max_retries + 1):
            try:
                logger.info(
                    f"Добавление источника {file_type} в ноутбук {notebook_id} "
                    f"(попытка {attempt}/{max_retries})..."
                )
                
                # Используем API библиотеки notebooklm-py
                source = await self._client.sources.add_file(
                    notebook_id=notebook_id,
                    file_path=file_path,
                    wait=True  # Ждем завершения загрузки
                )
                
                logger.info(f"✓ Источник добавлен: {source.id}")
                return source.id
                
            except FileNotFoundError:
                raise
            except Exception as e:
                if attempt < max_retries:
                    delay = base_delay ** attempt
                    logger.warning(
                        f"Ошибка при добавлении источника (попытка {attempt}/{max_retries}): {str(e)}. "
                        f"Повтор через {delay} секунд..."
                    )
                    await asyncio.sleep(delay)
                else:
                    error_msg = f"Не удалось добавить источник после {max_retries} попыток: {str(e)}"
                    logger.error(error_msg)
                    self.error_handler.log_error(e, {
                        'operation': 'add_source',
                        'notebook_id': notebook_id,
                        'file_path': file_path,
                        'attempts': max_retries
                    })
                    raise NotebookLMAPIError(error_msg) from e
    
    async def query_notebook(
        self, 
        notebook_id: str, 
        prompt: str, 
        timeout: int = 120
    ) -> str:
        """
        Отправляет запрос к ноутбуку
        
        Args:
            notebook_id: ID ноутбука
            prompt: Текст промпта
            timeout: Таймаут в секундах
        
        Returns:
            Текст ответа от NotebookLM
        
        Raises:
            TimeoutError: При превышении таймаута
            NotebookLMAPIError: При ошибке API
            RuntimeError: Если клиент не инициализирован в контексте async with
        """
        if not self._context_entered:
            raise RuntimeError("Client not initialized. Use 'async with' context.")
        
        max_retries = 3
        base_delay = 2
        
        for attempt in range(1, max_retries + 1):
            try:
                logger.info(
                    f"Отправка запроса к ноутбуку {notebook_id} "
                    f"(попытка {attempt}/{max_retries}, таймаут {timeout}с)..."
                )
                
                # Используем API библиотеки notebooklm-py с таймаутом
                response = await asyncio.wait_for(
                    self._client.chat.ask(
                        notebook_id=notebook_id,
                        question=prompt
                    ),
                    timeout=timeout
                )
                
                # Извлечение текста из ответа
                response_text = response.answer if hasattr(response, 'answer') else str(response)
                
                logger.info(f"✓ Получен ответ (длина: {len(response_text)} символов)")
                return response_text
                
            except asyncio.TimeoutError as e:
                if attempt < max_retries:
                    delay = base_delay ** attempt
                    logger.warning(
                        f"Таймаут запроса (попытка {attempt}/{max_retries}). "
                        f"Повтор через {delay} секунд..."
                    )
                    await asyncio.sleep(delay)
                else:
                    error_msg = f"Таймаут запроса после {max_retries} попыток ({timeout}с)"
                    logger.error(error_msg)
                    self.error_handler.log_error(e, {
                        'operation': 'query_notebook',
                        'notebook_id': notebook_id,
                        'timeout': timeout,
                        'attempts': max_retries
                    })
                    raise TimeoutError(error_msg) from e
                    
            except Exception as e:
                if attempt < max_retries:
                    delay = base_delay ** attempt
                    logger.warning(
                        f"Ошибка при запросе (попытка {attempt}/{max_retries}): {str(e)}. "
                        f"Повтор через {delay} секунд..."
                    )
                    await asyncio.sleep(delay)
                else:
                    error_msg = f"Не удалось выполнить запрос после {max_retries} попыток: {str(e)}"
                    logger.error(error_msg)
                    self.error_handler.log_error(e, {
                        'operation': 'query_notebook',
                        'notebook_id': notebook_id,
                        'attempts': max_retries
                    })
                    raise NotebookLMAPIError(error_msg) from e
