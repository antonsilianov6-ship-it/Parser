# -*- coding: utf-8 -*-
"""
Модуль для отправки сообщений в Telegram
"""

import asyncio
import logging
from typing import Dict, Any, Tuple, List, Optional
from src.telegram.connection_manager import ConnectionManager
from src.utils.logger import setup_logger

logger = setup_logger(__name__)


class TelegramSender:
    """
    Отправитель сообщений в Telegram
    Отвечает за отправку аналитических сводок и уведомлений об ошибках
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Инициализация отправителя
        
        Args:
            config: Конфигурация из config.json (секция TELEGRAM)
        """
        self.config = config
        self.connection_manager = ConnectionManager()
        self.max_retries = 3
        self.retry_delay = 5  # секунд
        self.max_message_length = 4096  # лимит Telegram
        
        logger.info("TelegramSender инициализирован")
    
    async def send_summary(
        self, 
        chat_id: str, 
        summary: str, 
        summary_type: str
    ) -> bool:
        """
        Отправляет сводку в Telegram чат
        
        Args:
            chat_id: ID чата (может быть username с @ или числовой ID)
            summary: Текст сводки
            summary_type: Тип сводки ('negative' или 'positive')
        
        Returns:
            True если отправка успешна, False иначе
        """
        logger.info(f"Начинаем отправку {summary_type} сводки в чат {chat_id}")
        
        # Форматируем сообщение с заголовком
        formatted_message = self._format_message_with_header(summary, summary_type)
        
        # Разбиваем длинное сообщение на части, если необходимо
        message_parts = self.split_long_message(formatted_message)
        
        logger.info(f"Сообщение разбито на {len(message_parts)} частей")
        
        # Отправляем каждую часть с retry-логикой
        for i, part in enumerate(message_parts, 1):
            success = await self._send_message_with_retry(chat_id, part, i, len(message_parts))
            if not success:
                logger.error(
                    f"Не удалось отправить часть {i}/{len(message_parts)}. "
                    f"Контекст: chat_id={chat_id}, summary_type={summary_type}, "
                    f"total_length={len(formatted_message)}"
                )
                return False
        
        logger.info(f"Сводка {summary_type} успешно отправлена")
        return True
    
    async def send_summaries(
        self, 
        chat_id: str, 
        negative_summary: str, 
        positive_summary: str
    ) -> Tuple[bool, bool]:
        """
        Отправляет обе сводки как отдельные сообщения
        
        Args:
            chat_id: ID чата
            negative_summary: Негативная сводка
            positive_summary: Позитивная сводка
        
        Returns:
            Кортеж (negative_sent, positive_sent)
        """
        logger.info(f"Начинаем отправку обеих сводок в чат {chat_id}")
        
        # Отправляем негативную сводку
        negative_sent = await self.send_summary(chat_id, negative_summary, 'negative')
        
        # Небольшая задержка между сообщениями
        await asyncio.sleep(1)
        
        # Отправляем позитивную сводку
        positive_sent = await self.send_summary(chat_id, positive_summary, 'positive')
        
        logger.info(f"Результат отправки: негативная={negative_sent}, позитивная={positive_sent}")
        return (negative_sent, positive_sent)
    
    def split_long_message(self, message: str, max_length: int = 4096) -> List[str]:
        """
        Разбивает длинное сообщение на части
        
        Args:
            message: Текст сообщения
            max_length: Максимальная длина части (лимит Telegram)
        
        Returns:
            Список частей сообщения
        """
        if len(message) <= max_length:
            return [message]
        
        parts = []
        current_part = ""
        
        # Разбиваем по предложениям
        sentences = message.split('. ')
        
        for i, sentence in enumerate(sentences):
            # Добавляем точку обратно (кроме последнего предложения)
            if i < len(sentences) - 1:
                sentence = sentence + '. '
            
            # Если одно предложение больше лимита, разбиваем по словам
            if len(sentence) > max_length:
                words = sentence.split(' ')
                for word in words:
                    # Если одно слово больше лимита, разбиваем посимвольно
                    if len(word) > max_length:
                        # Сохраняем текущую часть, если есть
                        if current_part:
                            parts.append(current_part.strip())
                            current_part = ""
                        
                        # Разбиваем длинное слово на части
                        for j in range(0, len(word), max_length):
                            parts.append(word[j:j + max_length])
                    elif len(current_part) + len(word) + 1 <= max_length:
                        if current_part:
                            current_part += ' ' + word
                        else:
                            current_part = word
                    else:
                        if current_part:
                            parts.append(current_part.strip())
                        current_part = word
            else:
                # Проверяем, поместится ли предложение в текущую часть
                if len(current_part) + len(sentence) <= max_length:
                    current_part += sentence
                else:
                    # Сохраняем текущую часть и начинаем новую
                    if current_part:
                        parts.append(current_part.strip())
                    current_part = sentence
        
        # Добавляем последнюю часть
        if current_part:
            parts.append(current_part.strip())
        
        return parts
    
    async def send_error_notification(
        self, 
        chat_id: str, 
        error_message: str
    ) -> bool:
        """
        Отправляет уведомление об ошибке
        
        Args:
            chat_id: ID чата
            error_message: Описание ошибки
        
        Returns:
            True если отправка успешна, False иначе
        """
        logger.info(f"Отправка уведомления об ошибке в чат {chat_id}")
        
        # Форматируем сообщение об ошибке
        formatted_message = f"🚨 **Ошибка автоматизации NotebookLM**\n\n{error_message}"
        
        # Отправляем с retry-логикой
        success = await self._send_message_with_retry(chat_id, formatted_message, 1, 1)
        
        if success:
            logger.info("Уведомление об ошибке успешно отправлено")
        else:
            logger.error("Не удалось отправить уведомление об ошибке")
        
        return success
    
    def _format_message_with_header(self, summary: str, summary_type: str) -> str:
        """
        Форматирует сообщение с заголовком и эмодзи
        
        Args:
            summary: Текст сводки
            summary_type: Тип сводки ('negative' или 'positive')
        
        Returns:
            Отформатированное сообщение
        """
        if summary_type == 'negative':
            header = "📉 **Негативная аналитическая сводка**\n\n"
        elif summary_type == 'positive':
            header = "📈 **Позитивная аналитическая сводка**\n\n"
        else:
            header = "📊 **Аналитическая сводка**\n\n"
        
        return header + summary
    
    async def _send_message_with_retry(
        self, 
        chat_id: str, 
        message: str, 
        part_num: int, 
        total_parts: int
    ) -> bool:
        """
        Отправляет сообщение с retry-логикой
        
        Args:
            chat_id: ID чата (может быть username с @ или числовой ID)
            message: Текст сообщения
            part_num: Номер части (для логирования)
            total_parts: Общее количество частей (для логирования)
        
        Returns:
            True если отправка успешна, False иначе
        """
        for attempt in range(1, self.max_retries + 1):
            try:
                # Подключаемся к Telegram
                await self.connection_manager.connect()
                
                # Получаем клиент
                client = self.connection_manager.get_client()
                
                # Преобразуем chat_id в правильный формат
                # Если это числовой ID (int или строка с числом), получаем entity
                target_chat = chat_id
                if isinstance(chat_id, int) or (isinstance(chat_id, str) and chat_id.lstrip('-').isdigit()):
                    chat_id_int = int(chat_id)
                    try:
                        # Пытаемся получить entity по ID
                        target_chat = await client.get_entity(chat_id_int)
                        logger.debug(f"Entity получен для chat_id={chat_id_int}")
                    except Exception as entity_error:
                        logger.warning(f"Не удалось получить entity для {chat_id_int}: {entity_error}")
                        # Пробуем использовать ID напрямую
                        target_chat = chat_id_int
                
                # Отправляем сообщение
                await client.send_message(target_chat, message, parse_mode='markdown')
                
                logger.info(f"Часть {part_num}/{total_parts} успешно отправлена (попытка {attempt})")
                
                # Отключаемся
                await self.connection_manager.disconnect()
                
                return True
                
            except Exception as e:
                error_context = {
                    'chat_id': chat_id,
                    'part_num': part_num,
                    'total_parts': total_parts,
                    'attempt': attempt,
                    'max_retries': self.max_retries,
                    'message_length': len(message),
                    'error_type': type(e).__name__
                }
                
                logger.warning(
                    f"Ошибка при отправке части {part_num}/{total_parts} "
                    f"(попытка {attempt}/{self.max_retries}): {e}\n"
                    f"Контекст: {error_context}"
                )
                
                # Пытаемся отключиться в случае ошибки
                try:
                    await self.connection_manager.disconnect()
                except:
                    pass
                
                # Если это не последняя попытка, ждем перед повтором
                if attempt < self.max_retries:
                    logger.info(f"Ожидание {self.retry_delay} секунд перед повтором...")
                    await asyncio.sleep(self.retry_delay)
                else:
                    logger.error(
                        f"Все попытки отправки части {part_num}/{total_parts} исчерпаны. "
                        f"Последняя ошибка: {str(e)}\n"
                        f"Контекст: {error_context}"
                    )
                    return False
        
        return False
