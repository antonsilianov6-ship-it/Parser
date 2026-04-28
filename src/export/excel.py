# -*- coding: utf-8 -*-
"""
Модуль для экспорта данных в Excel
"""
import os
import re
import pandas as pd
from typing import List, Dict, Any
from datetime import datetime
from src.config import EXPORT_DIR
from src.utils.logger import setup_logger

logger = setup_logger(__name__)


def sanitize_for_excel(text: str) -> str:
    """
    Очищает текст от недопустимых символов для Excel
    
    Args:
        text: Исходный текст
        
    Returns:
        Очищенный текст
    """
    if not isinstance(text, str):
        return text
    
    # Удаляем управляющие символы и недопустимые Unicode символы
    # Excel не поддерживает символы из диапазонов:
    # - 0x00-0x08, 0x0B-0x0C, 0x0E-0x1F (управляющие символы)
    # - Surrogate pairs и некоторые другие Unicode символы
    
    # Регулярное выражение для удаления недопустимых символов
    illegal_chars_pattern = re.compile(
        r'[\x00-\x08\x0B-\x0C\x0E-\x1F'  # Управляющие символы
        r'\uD800-\uDFFF'  # Surrogate pairs
        r'\uFFFE\uFFFF]'  # Недопустимые Unicode символы
    )
    
    # Удаляем недопустимые символы
    cleaned = illegal_chars_pattern.sub('', text)
    
    # Дополнительно удаляем символы вне BMP (Basic Multilingual Plane)
    # которые могут вызывать проблемы в openpyxl
    cleaned = ''.join(char for char in cleaned if ord(char) < 0x10000 or 0x20000 <= ord(char) < 0x30000)
    
    return cleaned

class ExcelExporter:
    """
    Экспортёр для сохранения данных в Excel файл
    """
    def __init__(self, export_dir: str = EXPORT_DIR):
        self.export_dir = export_dir
        os.makedirs(export_dir, exist_ok=True)
        logger.info(f"ExcelExporter инициализирован с директорией {export_dir}")
    
    def _build_dataframe(self, messages: List[Dict[str, Any]]) -> 'pd.DataFrame':
        """Преобразует список сообщений в DataFrame (включая комментарии)"""
        data = []
        for msg in messages:
            message_data = {
                'Дата': msg.get('date'),
                'Канал': sanitize_for_excel(str(msg.get('channel', ''))),
                'Тип источника': sanitize_for_excel(str(msg.get('source_type', 'channel'))),
                'Ссылка': sanitize_for_excel(str(msg.get('link', ''))),
                'Текст': sanitize_for_excel(str(msg.get('text', '')))
            }
            
            # Добавляем информацию о топике если есть
            if msg.get('topic_id') is not None:
                message_data['ID топика'] = msg.get('topic_id')
                message_data['Название топика'] = sanitize_for_excel(str(msg.get('topic_title', '')))
            
            if msg.get('title'):
                message_data['Заголовок'] = sanitize_for_excel(str(msg.get('title')))
            if msg.get('previous_post'):
                message_data['Предыдущий пост'] = sanitize_for_excel(str(msg.get('previous_post')))
            data.append(message_data)

            if msg.get('comments'):
                for i, comment in enumerate(msg['comments'], 1):
                    comment_data = {
                        'Дата': msg.get('date'),
                        'Канал': sanitize_for_excel(str(msg.get('channel', ''))),
                        'Тип источника': sanitize_for_excel(str(msg.get('source_type', 'channel'))),
                        'Ссылка': sanitize_for_excel(str(comment.link)),
                        'Текст': sanitize_for_excel(f"[КОММЕНТАРИЙ {i}]: {comment.text}"),
                        'Автор комментария': sanitize_for_excel(str(comment.author)),
                        'Ссылка на пост': sanitize_for_excel(str(msg.get('link', '')))
                    }
                    # Добавляем информацию о топике для комментариев
                    if msg.get('topic_id') is not None:
                        comment_data['ID топика'] = msg.get('topic_id')
                        comment_data['Название топика'] = sanitize_for_excel(str(msg.get('topic_title', '')))
                    data.append(comment_data)
        return pd.DataFrame(data)

    def export_to_excel(self, messages: List[Dict[str, Any]], filename: str = None) -> str:
        """
        Экспортирует сообщения в Excel (.xlsx) или CSV файл в зависимости от расширения filename.
        
        Args:
            messages: Список словарей с данными сообщений
            filename: Имя файла (если не указано, генерируется .xlsx)
            
        Returns:
            Путь к созданному файлу
        """
        if not messages:
            logger.info("Нет сообщений для экспорта")
            return None

        if not filename:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"telegram_export_{timestamp}.xlsx"

        filepath = os.path.join(self.export_dir, filename)
        ext = os.path.splitext(filename)[1].lower()

        try:
            df = self._build_dataframe(messages)

            if ext == '.csv':
                df.to_csv(filepath, index=False, encoding='utf-8-sig')
                logger.info(f"Экспортировано {len(messages)} сообщений в CSV: {filepath}")
            else:
                # Нормализуем расширение до .xlsx
                if ext != '.xlsx':
                    filepath = os.path.splitext(filepath)[0] + '.xlsx'
                with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
                    df.to_excel(writer, index=False, sheet_name='Telegram Export')
                    self._adjust_column_widths(writer, 'Telegram Export', df)
                logger.info(f"Экспортировано {len(messages)} сообщений в Excel: {filepath}")

            return filepath

        except Exception as e:
            logger.error(f"Ошибка при экспорте в Excel: {e}", exc_info=True)
            return None
    
    def export_comments_to_excel(self, messages: List[Dict[str, Any]], filename: str = None) -> str:
        """
        Экспортирует только комментарии в отдельный Excel (.xlsx) или CSV файл.
        
        Args:
            messages: Список словарей с данными сообщений
            filename: Имя файла (если не указано, генерируется .xlsx)
            
        Returns:
            Путь к созданному файлу
        """
        if not messages:
            logger.info("Нет сообщений для экспорта комментариев")
            return None

        if not filename:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"telegram_comments_{timestamp}.xlsx"

        filepath = os.path.join(self.export_dir, filename)
        ext = os.path.splitext(filename)[1].lower()

        try:
            comments_data = []
            for msg in messages:
                if not msg.get('comments'):
                    continue
                text = msg.get('text', '')
                short_text = text[:100] + '...' if len(text) > 100 else text
                for comment in msg['comments']:
                    comments_data.append({
                        'Дата поста': msg.get('date'),
                        'Канал': msg.get('channel'),
                        'Ссылка на пост': msg.get('link'),
                        'Текст поста': short_text,
                        'Автор комментария': comment.author,
                        'Ссылка на комментарий': comment.link,
                        'Текст комментария': comment.text
                    })

            if not comments_data:
                logger.info("Нет комментариев для экспорта")
                return None

            df = pd.DataFrame(comments_data)

            if ext == '.csv':
                df.to_csv(filepath, index=False, encoding='utf-8-sig')
                logger.info(f"Экспортировано {len(comments_data)} комментариев в CSV: {filepath}")
            else:
                if ext != '.xlsx':
                    filepath = os.path.splitext(filepath)[0] + '.xlsx'
                with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
                    df.to_excel(writer, index=False, sheet_name='Comments')
                    self._adjust_column_widths(writer, 'Comments', df)
                logger.info(f"Экспортировано {len(comments_data)} комментариев в Excel: {filepath}")

            return filepath

        except Exception as e:
            logger.error(f"Ошибка при экспорте комментариев: {e}", exc_info=True)
            return None
    
    def export_with_topic_grouping(self, messages: List[Dict[str, Any]], filename: str = None) -> str:
        """
        Экспортирует сообщения с группировкой по топикам для форум-чатов.
        Создает отдельные листы для каждого топика и сводную таблицу.
        
        Args:
            messages: Список словарей с данными сообщений
            filename: Имя файла (если не указано, генерируется .xlsx)
            
        Returns:
            Путь к созданному файлу
        """
        if not messages:
            logger.info("Нет сообщений для экспорта")
            return None

        if not filename:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"telegram_export_topics_{timestamp}.xlsx"

        filepath = os.path.join(self.export_dir, filename)
        
        # Нормализуем расширение до .xlsx
        if not filepath.endswith('.xlsx'):
            filepath = os.path.splitext(filepath)[0] + '.xlsx'

        try:
            # Группируем сообщения по топикам
            topics_data = {}
            general_messages = []
            
            for msg in messages:
                topic_id = msg.get('topic_id')
                if topic_id is not None:
                    topic_title = sanitize_for_excel(str(msg.get('topic_title', f'Topic {topic_id}')))
                    if topic_id not in topics_data:
                        topics_data[topic_id] = {
                            'title': topic_title,
                            'messages': []
                        }
                    topics_data[topic_id]['messages'].append(msg)
                else:
                    general_messages.append(msg)
            
            with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
                # Создаем сводную таблицу
                summary_data = []
                
                # Добавляем общие сообщения (не из топиков)
                if general_messages:
                    summary_data.append({
                        'Тип': 'Общие сообщения',
                        'Название': 'Без топика',
                        'Количество сообщений': len(general_messages)
                    })
                
                # Добавляем информацию о топиках
                for topic_id, topic_info in sorted(topics_data.items()):
                    summary_data.append({
                        'Тип': 'Топик',
                        'ID топика': topic_id,
                        'Название': topic_info['title'],
                        'Количество сообщений': len(topic_info['messages'])
                    })
                
                # Записываем сводную таблицу
                if summary_data:
                    summary_df = pd.DataFrame(summary_data)
                    summary_df.to_excel(writer, index=False, sheet_name='Сводка')
                    self._adjust_column_widths(writer, 'Сводка', summary_df)
                
                # Экспортируем общие сообщения
                if general_messages:
                    df_general = self._build_dataframe(general_messages)
                    df_general.to_excel(writer, index=False, sheet_name='Общие сообщения')
                    self._adjust_column_widths(writer, 'Общие сообщения', df_general)
                
                # Экспортируем каждый топик на отдельный лист
                for topic_id, topic_info in sorted(topics_data.items()):
                    # Ограничиваем длину названия листа (Excel limit 31 символ)
                    sheet_name = f"Топик {topic_id}"
                    if len(sheet_name) > 31:
                        sheet_name = sheet_name[:28] + '...'
                    
                    df_topic = self._build_dataframe(topic_info['messages'])
                    df_topic.to_excel(writer, index=False, sheet_name=sheet_name)
                    self._adjust_column_widths(writer, sheet_name, df_topic)
            
            total_topics = len(topics_data)
            total_messages = len(messages)
            logger.info(f"Экспортировано {total_messages} сообщений ({total_topics} топиков) в Excel: {filepath}")
            return filepath

        except Exception as e:
            logger.error(f"Ошибка при экспорте с группировкой по топикам: {e}", exc_info=True)
            return None
    
    def _adjust_column_widths(self, writer: 'pd.ExcelWriter', sheet_name: str, df: 'pd.DataFrame') -> None:
        """
        Настраивает ширину колонок в Excel листе
        
        Args:
            writer: ExcelWriter объект
            sheet_name: Название листа
            df: DataFrame с данными
        """
        try:
            worksheet = writer.sheets[sheet_name]
            for i, column in enumerate(df.columns):
                try:
                    # Вычисляем максимальную длину с обработкой разных типов данных
                    col_values = df[column].astype(str)
                    max_length = max(
                        col_values.str.len().max(),
                        len(str(column))
                    )
                    # Ограничиваем максимальную ширину колонки
                    column_width = min(max_length + 2, 100)
                    # Excel использует буквы для колонок (A, B, C, ...)
                    column_letter = chr(65 + i) if i < 26 else f"A{chr(65 + i - 26)}"
                    worksheet.column_dimensions[column_letter].width = column_width
                except Exception as col_error:
                    # Пропускаем колонку если не удалось вычислить ширину
                    logger.debug(f"Не удалось настроить ширину для колонки {column}: {col_error}")
                    continue
        except Exception as e:
            logger.warning(f"Не удалось настроить ширину колонок для листа {sheet_name}: {e}")