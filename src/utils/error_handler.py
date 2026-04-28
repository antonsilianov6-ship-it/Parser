# -*- coding: utf-8 -*-
"""Модуль для централизованной обработки ошибок"""

import asyncio
import random
from dataclasses import dataclass
from datetime import datetime
from typing import List, Dict, Any, Optional, Callable
from telethon.errors import (
    FloodWaitError, 
    ChannelPrivateError, 
    UsernameNotOccupiedError,
    ChatAdminRequiredError,
    UserNotParticipantError,
    ChatWriteForbiddenError
)
from src.utils.logger import setup_logger

logger = setup_logger(__name__)


@dataclass
class ErrorRecord:
    """Запись об ошибке"""
    timestamp: datetime
    error_type: str
    error_message: str
    context: Dict[str, Any]
    channel: Optional[str] = None
    message_id: Optional[int] = None


class ErrorHandler:
    """Централизованный обработчик ошибок"""
    
    def __init__(self):
        self.errors: List[ErrorRecord] = []
        self.chat_access_errors: Dict[str, int] = {}  # Статистика ошибок доступа по типам
        self.errors_by_source: Dict[str, List[str]] = {}  # Ошибки по источникам
    
    async def handle_flood_wait(
        self, 
        error: FloodWaitError, 
        context: str,
        channel: Optional[str] = None
    ) -> None:
        """Обработка FloodWaitError с автоматическим retry"""
        wait_time = error.seconds
        additional_delay = random.uniform(1, 5)
        total_wait = wait_time + additional_delay
        
        error_msg = f"FloodWait {wait_time}с для {context}"
        if channel:
            error_msg += f" (канал: {channel})"
        
        logger.warning(f"{error_msg}. Ожидание {total_wait:.1f}с...")
        
        self.log_error(error, {
            'operation': context,
            'channel': channel,
            'wait_seconds': wait_time,
            'total_wait': total_wait
        })
        
        await asyncio.sleep(total_wait)
        logger.info(f"Возобновление работы после FloodWait для {context}")
    
    def handle_channel_error(self, error: Exception, channel: str) -> None:
        """Обработка ошибок каналов (private, not found)"""
        if isinstance(error, ChannelPrivateError):
            error_msg = f"Канал {channel} является приватным или недоступным"
            logger.warning(error_msg)
        elif isinstance(error, UsernameNotOccupiedError):
            error_msg = f"Канал {channel} не найден (username не существует)"
            logger.warning(error_msg)
        else:
            error_msg = f"Ошибка доступа к каналу {channel}: {str(error)}"
            logger.error(error_msg)
        
        self.log_error(error, {
            'operation': 'channel_access',
            'channel': channel,
            'error_type': type(error).__name__
        })
    
    def handle_chat_access_error(self, error: Exception, chat_link: str) -> None:
        """
        Обработка специфичных ошибок доступа к чатам
        
        Args:
            error: Исключение (ChatAdminRequiredError, UserNotParticipantError, ChatWriteForbiddenError)
            chat_link: Ссылка на чат
            
        Handles:
            - ChatAdminRequiredError: требуются права администратора
            - UserNotParticipantError: пользователь не является участником
            - ChatWriteForbiddenError: ограниченный доступ
        """
        error_type = type(error).__name__
        
        # Накопление статистики по типам ошибок
        if error_type not in self.chat_access_errors:
            self.chat_access_errors[error_type] = 0
        self.chat_access_errors[error_type] += 1
        
        # Накопление статистики по источникам
        if chat_link not in self.errors_by_source:
            self.errors_by_source[chat_link] = []
        self.errors_by_source[chat_link].append(error_type)
        
        # Получение рекомендаций
        recommendations = self.get_access_error_recommendations(error_type)
        
        # Логирование с рекомендациями
        if isinstance(error, ChatAdminRequiredError):
            error_msg = f"Требуются права администратора для чата {chat_link}"
            logger.warning(f"{error_msg}. {recommendations}")
        elif isinstance(error, UserNotParticipantError):
            error_msg = f"Пользователь не является участником чата {chat_link}"
            logger.warning(f"{error_msg}. {recommendations}")
        elif isinstance(error, ChatWriteForbiddenError):
            error_msg = f"Ограниченный доступ к чату {chat_link}"
            logger.warning(f"{error_msg}. {recommendations}")
        else:
            error_msg = f"Ошибка доступа к чату {chat_link}: {str(error)}"
            logger.error(f"{error_msg}. {recommendations}")
        
        # Логирование ошибки с полным контекстом
        self.log_error(error, {
            'operation': 'chat_access',
            'chat_link': chat_link,
            'error_type': error_type,
            'recommendations': recommendations
        })
    
    def get_access_error_recommendations(self, error_type: str) -> str:
        """
        Получает рекомендации по устранению ошибок доступа
        
        Args:
            error_type: Тип ошибки
            
        Returns:
            Текст с рекомендациями
        """
        recommendations = {
            'ChatAdminRequiredError': (
                "Рекомендации: Получите права администратора в чате или "
                "попросите администратора добавить бота с необходимыми правами."
            ),
            'UserNotParticipantError': (
                "Рекомендации: Присоединитесь к чату перед началом парсинга. "
                "Убедитесь, что аккаунт является участником чата."
            ),
            'ChatWriteForbiddenError': (
                "Рекомендации: Проверьте настройки приватности чата. "
                "Возможно, чат ограничил доступ для ботов или внешних приложений."
            ),
            'ChannelPrivateError': (
                "Рекомендации: Канал является приватным. "
                "Получите приглашение или права доступа к каналу."
            ),
            'UsernameNotOccupiedError': (
                "Рекомендации: Проверьте правильность написания username канала/чата. "
                "Убедитесь, что канал/чат существует."
            )
        }
        
        return recommendations.get(
            error_type, 
            "Рекомендации: Проверьте права доступа и настройки приватности источника."
        )
    
    async def handle_network_error(
        self,
        error: Exception,
        retry_func: Callable,
        context: str,
        max_retries: int = 3,
        channel: Optional[str] = None
    ) -> Any:
        """Обработка сетевых ошибок с exponential backoff (до 3 попыток)"""
        base_delay = 2
        
        for attempt in range(1, max_retries + 1):
            delay = base_delay ** attempt
            
            error_msg = f"Сетевая ошибка при {context}"
            if channel:
                error_msg += f" (канал: {channel})"
            error_msg += f". Попытка {attempt}/{max_retries}"
            
            logger.warning(f"{error_msg}. Ожидание {delay}с перед повтором...")
            
            self.log_error(error, {
                'operation': context,
                'channel': channel,
                'attempt': attempt,
                'max_retries': max_retries,
                'delay': delay
            })
            
            await asyncio.sleep(delay)
            
            try:
                result = await retry_func()
                logger.info(f"Успешное выполнение {context} после {attempt} попытки")
                return result
            except Exception as e:
                if attempt == max_retries:
                    logger.error(
                        f"Не удалось выполнить {context} после {max_retries} попыток. "
                        f"Последняя ошибка: {str(e)}"
                    )
                    self.log_error(e, {
                        'operation': context,
                        'channel': channel,
                        'final_attempt': True,
                        'attempts_made': max_retries
                    })
                    return None
                error = e
        
        return None
    
    def log_error(self, error: Exception, context: Dict[str, Any]) -> None:
        """Логирование ошибки с полным контекстом"""
        error_record = ErrorRecord(
            timestamp=datetime.now(),
            error_type=type(error).__name__,
            error_message=str(error),
            context=context,
            channel=context.get('channel'),
            message_id=context.get('message_id')
        )
        
        self.errors.append(error_record)
        
        logger.error(
            f"Ошибка: {error_record.error_type} - {error_record.error_message}. "
            f"Контекст: {context}"
        )
    
    def get_error_summary(self) -> Dict[str, Any]:
        """Получение сводки по ошибкам"""
        if not self.errors:
            return {
                'total_errors': 0,
                'flood_wait_errors': 0,
                'channel_errors': 0,
                'chat_access_errors': 0,
                'network_errors': 0,
                'other_errors': 0,
                'failed_channels': [],
                'chat_access_errors_by_type': {},
                'errors_by_source': {},
                'details': []
            }
        
        flood_wait_count = sum(1 for e in self.errors if e.error_type == 'FloodWaitError')
        channel_error_count = sum(
            1 for e in self.errors 
            if e.error_type in ['ChannelPrivateError', 'UsernameNotOccupiedError']
        )
        chat_access_error_count = sum(
            1 for e in self.errors
            if e.error_type in ['ChatAdminRequiredError', 'UserNotParticipantError', 'ChatWriteForbiddenError']
        )
        network_error_count = sum(
            1 for e in self.errors 
            if 'network' in e.error_type.lower() or 'timeout' in e.error_type.lower()
        )
        other_errors_count = (
            len(self.errors) - flood_wait_count - channel_error_count 
            - chat_access_error_count - network_error_count
        )
        
        failed_channels = list(set(e.channel for e in self.errors if e.channel is not None))
        
        details = [
            {
                'timestamp': e.timestamp.isoformat(),
                'type': e.error_type,
                'message': e.error_message,
                'channel': e.channel,
                'context': e.context
            }
            for e in self.errors[-10:]
        ]
        
        return {
            'total_errors': len(self.errors),
            'flood_wait_errors': flood_wait_count,
            'channel_errors': channel_error_count,
            'chat_access_errors': chat_access_error_count,
            'network_errors': network_error_count,
            'other_errors': other_errors_count,
            'failed_channels': failed_channels,
            'chat_access_errors_by_type': dict(self.chat_access_errors),
            'errors_by_source': dict(self.errors_by_source),
            'details': details
        }
