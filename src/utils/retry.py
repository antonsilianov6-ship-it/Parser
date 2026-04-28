# -*- coding: utf-8 -*-
"""
Модуль для повторных попыток выполнения операций
"""
import asyncio
import random
from typing import Callable, Any, Optional
from telethon.errors import FloodWaitError, ServerError, NetworkError

class RetryManager:
    def __init__(self, max_retries: int = 3, base_delay: float = 1.0):
        self.max_retries = max_retries
        self.base_delay = base_delay
    
    async def retry_async(self, func: Callable, *args, **kwargs) -> Any:
        """Выполняет асинхронную функцию с повторными попытками"""
        last_exception = None
        
        for attempt in range(self.max_retries + 1):
            try:
                return await func(*args, **kwargs)
            except FloodWaitError as e:
                if attempt == self.max_retries:
                    raise e
                wait_time = e.seconds + random.uniform(1, 5)
                print(f"FloodWait: ожидание {wait_time} секунд")
                await asyncio.sleep(wait_time)
                last_exception = e
            except (ServerError, NetworkError, ConnectionError) as e:
                if attempt == self.max_retries:
                    raise e
                delay = self.base_delay * (2 ** attempt) + random.uniform(0, 1)
                print(f"Ошибка сети (попытка {attempt + 1}): {e}. Повтор через {delay:.1f}с")
                await asyncio.sleep(delay)
                last_exception = e
            except Exception as e:
                print(f"Неожиданная ошибка: {e}")
                raise e
        
        if last_exception:
            raise last_exception

# Глобальный экземпляр
retry_manager = RetryManager()