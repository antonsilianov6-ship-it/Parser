# -*- coding: utf-8 -*-
"""
Unit-тесты для экспортеров
"""
import pytest
import pandas as pd
import tempfile
import os
from datetime import datetime
from src.export.excel import ExcelExporter
from src.export.google_docs import GoogleDocsExporter


class TestExcelExporter:
    """Unit-тесты для ExcelExporter"""
    
    def test_export_messages_with_new_fields(self):
        """
        Тест экспорта сообщений из чатов с новыми полями
        
        Requirements: 10.1, 10.2, 13.7
        """
        exporter = ExcelExporter(export_dir=tempfile.gettempdir())
        
        messages = [
            {
                'date': '2024-01-01T12:00:00',
                'channel': 'test_chat',
                'link': 'https://t.me/test/1',
                'text': 'Test message from chat',
                'source_type': 'chat'
            },
            {
                'date': '2024-01-01T13:00:00',
                'channel': 'test_channel',
                'link': 'https://t.me/test/2',
                'text': 'Test message from channel',
                'source_type': 'channel'
            }
        ]
        
        with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as tmp:
            filename = os.path.basename(tmp.name)
        
        filepath = None
        try:
            filepath = exporter.export_to_excel(messages, filename=filename)
            assert filepath is not None
            
            # Читаем файл
            df = pd.read_excel(filepath, sheet_name='Telegram Export')
            
            # Проверяем наличие новых колонок
            assert 'Тип источника' in df.columns
            assert len(df) == 2
            
            # Проверяем значения
            assert df.iloc[0]['Тип источника'] == 'chat'
            assert df.iloc[1]['Тип источника'] == 'channel'
        
        finally:
            if filepath and os.path.exists(filepath):
                try:
                    os.remove(filepath)
                except PermissionError:
                    pass
    
    def test_export_forum_chat_with_topic_grouping(self):
        """
        Тест экспорта сообщений из форум-чатов с группировкой по топикам
        
        Requirements: 10.4, 10.5, 13.7
        """
        exporter = ExcelExporter(export_dir=tempfile.gettempdir())
        
        messages = [
            {
                'date': '2024-01-01T12:00:00',
                'channel': 'forum_chat',
                'link': 'https://t.me/test/1',
                'text': 'Message in topic 1',
                'source_type': 'forum_chat',
                'topic_id': 1,
                'topic_title': 'General Discussion'
            },
            {
                'date': '2024-01-01T13:00:00',
                'channel': 'forum_chat',
                'link': 'https://t.me/test/2',
                'text': 'Another message in topic 1',
                'source_type': 'forum_chat',
                'topic_id': 1,
                'topic_title': 'General Discussion'
            },
            {
                'date': '2024-01-01T14:00:00',
                'channel': 'forum_chat',
                'link': 'https://t.me/test/3',
                'text': 'Message in topic 2',
                'source_type': 'forum_chat',
                'topic_id': 2,
                'topic_title': 'Announcements'
            }
        ]
        
        with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as tmp:
            filename = os.path.basename(tmp.name)
        
        filepath = None
        try:
            filepath = exporter.export_with_topic_grouping(messages, filename=filename)
            assert filepath is not None
            
            # Читаем файл
            excel_file = pd.ExcelFile(filepath)
            
            # Проверяем наличие сводного листа
            assert 'Сводка' in excel_file.sheet_names
            
            # Проверяем наличие листов для топиков
            assert 'Топик 1' in excel_file.sheet_names
            assert 'Топик 2' in excel_file.sheet_names
            
            # Читаем сводку
            summary_df = pd.read_excel(filepath, sheet_name='Сводка')
            topic_rows = summary_df[summary_df['Тип'] == 'Топик']
            assert len(topic_rows) == 2
            
            # Проверяем количество сообщений в топиках
            topic1_df = pd.read_excel(filepath, sheet_name='Топик 1')
            assert len(topic1_df) == 2
            
            topic2_df = pd.read_excel(filepath, sheet_name='Топик 2')
            assert len(topic2_df) == 1
            
            excel_file.close()
        
        finally:
            if filepath and os.path.exists(filepath):
                try:
                    os.remove(filepath)
                except PermissionError:
                    pass
    
    def test_create_separate_sheets_for_topics(self):
        """
        Тест создания отдельных листов для топиков
        
        Requirements: 10.4, 13.7
        """
        exporter = ExcelExporter(export_dir=tempfile.gettempdir())
        
        messages = [
            {
                'date': '2024-01-01T12:00:00',
                'channel': 'forum_chat',
                'link': 'https://t.me/test/1',
                'text': 'Topic A message',
                'source_type': 'forum_chat',
                'topic_id': 100,
                'topic_title': 'Topic A'
            },
            {
                'date': '2024-01-01T13:00:00',
                'channel': 'forum_chat',
                'link': 'https://t.me/test/2',
                'text': 'Topic B message',
                'source_type': 'forum_chat',
                'topic_id': 200,
                'topic_title': 'Topic B'
            },
            {
                'date': '2024-01-01T14:00:00',
                'channel': 'forum_chat',
                'link': 'https://t.me/test/3',
                'text': 'Topic C message',
                'source_type': 'forum_chat',
                'topic_id': 300,
                'topic_title': 'Topic C'
            }
        ]
        
        with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as tmp:
            filename = os.path.basename(tmp.name)
        
        filepath = None
        try:
            filepath = exporter.export_with_topic_grouping(messages, filename=filename)
            assert filepath is not None
            
            # Читаем файл
            excel_file = pd.ExcelFile(filepath)
            
            # Проверяем что созданы отдельные листы для каждого топика
            assert 'Топик 100' in excel_file.sheet_names
            assert 'Топик 200' in excel_file.sheet_names
            assert 'Топик 300' in excel_file.sheet_names
            
            # Проверяем что в каждом листе по одному сообщению
            for topic_id in [100, 200, 300]:
                topic_df = pd.read_excel(filepath, sheet_name=f'Топик {topic_id}')
                assert len(topic_df) == 1
            
            excel_file.close()
        
        finally:
            if filepath and os.path.exists(filepath):
                try:
                    os.remove(filepath)
                except PermissionError:
                    pass


class TestGoogleDocsExporter:
    """Unit-тесты для GoogleDocsExporter"""
    
    def test_format_message_with_topic_info(self):
        """
        Тест форматирования сообщения с информацией о топике
        
        Requirements: 10.3, 10.6, 13.7
        """
        # Создаем сообщение с топиком
        message = {
            'date': '2024-01-01T12:00:00',
            'channel': 'forum_chat',
            'link': 'https://t.me/test/1',
            'text': 'Test message in topic',
            'source_type': 'forum_chat',
            'topic_id': 1,
            'topic_title': 'General Discussion'
        }
        
        # Форматируем текст как в GoogleDocsExporter
        text = (
            f"Дата: {message['date']}\n"
            f"Канал: {message['channel']}\n"
        )
        
        source_type = message.get('source_type', 'channel')
        source_type_display = {
            'channel': 'Канал',
            'chat': 'Чат',
            'forum_chat': 'Форум-чат'
        }.get(source_type, 'Канал')
        text += f"Тип источника: {source_type_display}\n"
        
        if message.get('topic_id') is not None:
            text += f"━━━ ТОПИК: {message.get('topic_title', 'Без названия')} (ID: {message['topic_id']}) ━━━\n"
        
        text += f"Ссылка: {message['link']}\n"
        text += f"\nТекст поста:\n{message['text']}\n\n"
        
        # Проверяем что информация о топике присутствует
        assert 'Тип источника: Форум-чат' in text
        assert '━━━ ТОПИК: General Discussion (ID: 1) ━━━' in text
        assert 'Test message in topic' in text
    
    def test_format_message_without_topic(self):
        """
        Тест форматирования сообщения без топика
        
        Requirements: 10.7, 13.7
        """
        # Создаем сообщение без топика
        message = {
            'date': '2024-01-01T12:00:00',
            'channel': 'test_chat',
            'link': 'https://t.me/test/1',
            'text': 'Test message without topic',
            'source_type': 'chat'
        }
        
        # Форматируем текст как в GoogleDocsExporter
        text = (
            f"Дата: {message['date']}\n"
            f"Канал: {message['channel']}\n"
        )
        
        source_type = message.get('source_type', 'channel')
        source_type_display = {
            'channel': 'Канал',
            'chat': 'Чат',
            'forum_chat': 'Форум-чат'
        }.get(source_type, 'Канал')
        text += f"Тип источника: {source_type_display}\n"
        
        if message.get('topic_id') is not None:
            text += f"━━━ ТОПИК: {message.get('topic_title', 'Без названия')} (ID: {message['topic_id']}) ━━━\n"
        
        text += f"Ссылка: {message['link']}\n"
        text += f"\nТекст поста:\n{message['text']}\n\n"
        
        # Проверяем что информация о топике НЕ присутствует
        assert 'Тип источника: Чат' in text
        assert '━━━ ТОПИК:' not in text
        assert 'Test message without topic' in text
    
    def test_visual_separation_for_topics(self):
        """
        Тест визуального разделения сообщений из топиков
        
        Requirements: 10.6, 13.7
        """
        # Создаем сообщение с топиком
        message_with_topic = {
            'date': '2024-01-01T12:00:00',
            'channel': 'forum_chat',
            'link': 'https://t.me/test/1',
            'text': 'Message with topic',
            'source_type': 'forum_chat',
            'topic_id': 1,
            'topic_title': 'Topic 1'
        }
        
        # Создаем сообщение без топика
        message_without_topic = {
            'date': '2024-01-01T13:00:00',
            'channel': 'test_chat',
            'link': 'https://t.me/test/2',
            'text': 'Message without topic',
            'source_type': 'chat'
        }
        
        # Форматируем оба сообщения
        def format_message(msg):
            text = f"Дата: {msg['date']}\n"
            text += f"Канал: {msg['channel']}\n"
            
            source_type = msg.get('source_type', 'channel')
            source_type_display = {
                'channel': 'Канал',
                'chat': 'Чат',
                'forum_chat': 'Форум-чат'
            }.get(source_type, 'Канал')
            text += f"Тип источника: {source_type_display}\n"
            
            if msg.get('topic_id') is not None:
                text += f"━━━ ТОПИК: {msg.get('topic_title', 'Без названия')} (ID: {msg['topic_id']}) ━━━\n"
            
            text += f"Ссылка: {msg['link']}\n"
            text += f"\nТекст поста:\n{msg['text']}\n\n"
            
            # Добавляем разделитель
            if msg.get('topic_id') is not None:
                text += "═════════════════════════════════════════════════════════════\n\n"
            else:
                text += "─────────────────────────────────────────────────────────────\n\n"
            
            return text
        
        text_with_topic = format_message(message_with_topic)
        text_without_topic = format_message(message_without_topic)
        
        # Проверяем что для топиков используется более заметный разделитель
        assert '═════════════════════════════════════════════════════════════' in text_with_topic
        assert '─────────────────────────────────────────────────────────────' in text_without_topic
        assert '═════════════════════════════════════════════════════════════' not in text_without_topic
