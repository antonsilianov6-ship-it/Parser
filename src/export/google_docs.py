# -*- coding: utf-8 -*-
"""
Модуль для экспорта данных в Google Docs
"""
import os
import logging
from typing import List, Dict, Set, Any
from googleapiclient.discovery import build
from google.oauth2.service_account import Credentials
from src.config import get_google_config
from src.utils.logger import setup_logger

logger = setup_logger(__name__)

class GoogleDocsExporter:
    """
    Класс для экспорта данных в Google Docs
    """
    def __init__(self):
        google_config = get_google_config()
        self.creds_path = google_config['CREDS_PATH']
        self.doc_id = google_config['DOC_ID']
        self.service = self._build_service()
        logger.info(f"GoogleDocsExporter инициализирован для документа {self.doc_id}")
    
    def _build_service(self) -> Any:
        """
        Создает сервис для работы с Google Docs API
        
        Returns:
            Экземпляр сервиса Google Docs API
        """
        try:
            creds = Credentials.from_service_account_file(self.creds_path, scopes=[
                'https://www.googleapis.com/auth/documents',
                'https://www.googleapis.com/auth/drive',
            ])
            service = build('docs', 'v1', credentials=creds)
            logger.info("Сервис Google Docs API успешно создан")
            return service
        except Exception as e:
            logger.error(f"Ошибка при создании сервиса Google Docs API: {e}", exc_info=True)
            raise
    
    def append_new_content(self, messages: List[Dict], batch_size: int = 100) -> None:
        """
        Добавляет новые сообщения в Google Docs с батчингом и rate limiting
        
        Args:
            messages: Список словарей с данными сообщений
            batch_size: Количество сообщений в одном батче (по умолчанию 100)
        """
        if not messages:
            logger.info("Нет новых сообщений для добавления в Google Docs")
            return
        
        try:
            import time
            total_messages = len(messages)
            logger.info(f"Начало экспорта {total_messages} сообщений в Google Docs (батчами по {batch_size})")
            
            # Получаем текущий размер документа для вставки в конец
            doc = self.service.documents().get(documentId=self.doc_id).execute()
            doc_end_index = doc.get('body', {}).get('content', [{}])[-1].get('endIndex', 1)
            
            logger.info(f"Текущий размер документа: {doc_end_index} символов")
            
            # Разбиваем сообщения на батчи
            successful_batches = 0
            failed_batches = 0
            current_batch_size = batch_size
            
            for batch_num, i in enumerate(range(0, total_messages, current_batch_size), 1):
                batch = messages[i:i + current_batch_size]
                batch_start = i + 1
                batch_end = min(i + current_batch_size, total_messages)
                
                logger.info(f"Обработка батча {batch_num}: сообщения {batch_start}-{batch_end} из {total_messages}")
                
                # Формируем один большой текст для всего батча
                combined_text = ""
                for msg in batch:
                    # Основная информация о посте
                    text = (
                        f"Дата: {msg['date']}\n"
                        f"Канал: {msg['channel']}\n"
                    )
                    
                    # Добавляем тип источника
                    source_type = msg.get('source_type', 'channel')
                    source_type_display = {
                        'channel': 'Канал',
                        'chat': 'Чат',
                        'forum_chat': 'Форум-чат'
                    }.get(source_type, 'Канал')
                    text += f"Тип источника: {source_type_display}\n"
                    
                    # Добавляем информацию о топике если есть
                    if msg.get('topic_id') is not None:
                        text += f"━━━ ТОПИК: {msg.get('topic_title', 'Без названия')} (ID: {msg['topic_id']}) ━━━\n"
                    
                    text += f"Ссылка: {msg['link']}\n"
                    
                    # Добавляем заголовок, если есть
                    if msg.get('title'):
                        text += f"Заголовок: {msg['title']}\n"
                    
                    # Добавляем информацию о предыдущем посте, если есть
                    if msg.get('previous_post'):
                        text += f"Продолжение поста: {msg['previous_post']}\n"
                    
                    # Добавляем основной текст
                    text += f"\nТекст поста:\n{msg['text']}\n\n"
                    
                    # Добавляем комментарии, если есть
                    if msg.get('comments'):
                        text += "Комментарии к посту:\n"
                        for j, comment in enumerate(msg['comments'], 1):
                            text += f"{j}. От: {comment.get('author', 'Неизвестно')}\n"
                            text += f"   Ссылка: {comment.get('link', '')}\n"
                            text += f"   Текст: {comment.get('text', '')}\n\n"
                    
                    # Добавляем разделитель между постами
                    if msg.get('topic_id') is not None:
                        text += "═════════════════════════════════════════════════════════════\n\n"
                    else:
                        text += "─────────────────────────────────────────────────────────────\n\n"
                    
                    combined_text += text
                
                # Создаем ОДИН запрос для всего батча
                # Вставляем в КОНЕЦ документа вместо начала
                requests = [{
                    'insertText': {
                        'location': {'index': doc_end_index - 1},
                        'text': combined_text
                    }
                }]
                
                # Выполняем запрос пакетного обновления с retry логикой
                max_retries = 3
                retry_delay = 2
                
                for attempt in range(max_retries):
                    try:
                        self.service.documents().batchUpdate(
                            documentId=self.doc_id,
                            body={'requests': requests}
                        ).execute()
                        
                        logger.info(f"✓ Батч {batch_num} успешно добавлен ({len(batch)} сообщений)")
                        successful_batches += 1
                        
                        # Обновляем индекс конца документа
                        doc_end_index += len(combined_text)
                        
                        # Rate limiting: задержка между батчами
                        if batch_end < total_messages:
                            delay = 1 if failed_batches == 0 else 3  # Увеличиваем задержку при ошибках
                            logger.info(f"Задержка {delay} секунд перед следующим батчем...")
                            time.sleep(delay)
                        
                        break  # Успешно, выходим из retry цикла
                        
                    except Exception as batch_error:
                        error_msg = str(batch_error)
                        
                        if "Precondition check failed" in error_msg or "quota" in error_msg.lower():
                            # Ошибка лимитов или размера документа
                            if attempt < max_retries - 1:
                                logger.warning(
                                    f"Ошибка лимитов в батче {batch_num} (попытка {attempt + 1}/{max_retries}). "
                                    f"Повтор через {retry_delay} секунд..."
                                )
                                time.sleep(retry_delay)
                                retry_delay *= 2  # Экспоненциальная задержка
                                
                                # Уменьшаем размер батча для следующих попыток
                                if current_batch_size > 20:
                                    current_batch_size = max(20, current_batch_size // 2)
                                    logger.info(f"Уменьшаем размер батча до {current_batch_size}")
                            else:
                                logger.error(f"Батч {batch_num} пропущен после {max_retries} попыток: {batch_error}")
                                failed_batches += 1
                                break
                        else:
                            # Другая ошибка
                            logger.error(f"Ошибка при обработке батча {batch_num}: {batch_error}")
                            failed_batches += 1
                            break
            
            logger.info(
                f"✓ Экспорт завершен: {successful_batches} батчей успешно, "
                f"{failed_batches} батчей с ошибками из {batch_num} всего"
            )
            
            if failed_batches > 0:
                logger.warning(
                    f"⚠ {failed_batches} батчей не были добавлены из-за ошибок. "
                    f"Возможно, документ достиг максимального размера."
                )
            
        except Exception as e:
            logger.error(f"Критическая ошибка при добавлении сообщений в Google Docs: {e}", exc_info=True)
            raise
    
    def get_existing_links(self) -> Set[str]:
        """
        Получает существующие ссылки из документа
        
        Returns:
            Множество ссылок на посты, которые уже есть в документе
        """
        logger.info("Получение существующих ссылок из документа")
        
        try:
            doc = self.service.documents().get(documentId=self.doc_id).execute()
            content = doc.get('body', {}).get('content', [])
            links = set()
            
            for element in content:
                if 'paragraph' in element:
                    for para_element in element['paragraph']['elements']:
                        if 'textRun' in para_element:
                            text = para_element['textRun']['content']
                            if 'https://t.me/' in text:
                                # Извлекаем ссылку из текста
                                start = text.find('https://t.me/')
                                end = text.find('\n', start)
                                if end == -1:
                                    end = len(text)
                                link = text[start:end].strip()
                                links.add(link)
            
            logger.info(f"Найдено {len(links)} существующих ссылок в документе")
            return links
        except Exception as e:
            logger.error(f"Ошибка при получении существующих ссылок из документа: {e}", exc_info=True)
            return set() 