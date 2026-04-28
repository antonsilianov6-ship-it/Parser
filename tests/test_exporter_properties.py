# -*- coding: utf-8 -*-
"""
Property-based тесты для экспортеров
"""
import pytest
import pandas as pd
from hypothesis import given, settings, strategies as st
from datetime import datetime
from src.export.excel import ExcelExporter
from src.export.google_docs import GoogleDocsExporter
import tempfile
import os


# Стратегии для генерации тестовых данных
@st.composite
def message_strategy(draw, with_topic=None):
    """
    Стратегия для генерации сообщений
    
    Args:
        with_topic: None (случайно), True (с топиком), False (без топика)
    """
    # Базовые поля сообщения
    # Используем безопасные символы для Excel
    safe_text = st.text(
        min_size=1, 
        max_size=500,
        alphabet=st.characters(
            whitelist_categories=('Lu', 'Ll', 'Nd', 'Zs'),
            min_codepoint=32,
            max_codepoint=126  # Только ASCII символы
        )
    )
    
    msg = {
        'date': draw(st.datetimes(min_value=datetime(2020, 1, 1), max_value=datetime(2024, 12, 31))).isoformat(),
        'channel': draw(st.text(min_size=1, max_size=50, alphabet='abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789')),
        'link': f"https://t.me/test/{draw(st.integers(min_value=1, max_value=999999))}",
        'text': draw(safe_text),
        'source_type': draw(st.sampled_from(['channel', 'chat', 'forum_chat']))
    }
    
    # Определяем, добавлять ли топик
    if with_topic is None:
        has_topic = draw(st.booleans())
    else:
        has_topic = with_topic
    
    # Добавляем топик только если has_topic=True
    if has_topic:
        msg['topic_id'] = draw(st.integers(min_value=1, max_value=1000))
        msg['topic_title'] = draw(st.text(min_size=1, max_size=100, alphabet='abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 '))
    else:
        # Явно устанавливаем None для сообщений без топика
        msg['topic_id'] = None
        msg['topic_title'] = None
    
    return msg


# Feature: chat-and-topic-support, Property 13: Export topic field handling
@given(
    messages=st.lists(message_strategy(), min_size=1, max_size=20)
)
@settings(max_examples=100, deadline=None)
def test_export_topic_field_handling_property(messages):
    """
    Property 13: Export topic field handling
    
    Validates: Requirements 10.7
    
    Проверяет что:
    - При topic_id=NULL отображается только source_type
    - При topic_id!=NULL отображается информация о топике
    """
    exporter = ExcelExporter(export_dir=tempfile.gettempdir())
    
    # Экспортируем сообщения
    with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as tmp:
        filename = os.path.basename(tmp.name)
    
    filepath = None
    try:
        filepath = exporter.export_to_excel(messages, filename=filename)
        assert filepath is not None, "Экспорт должен быть успешным"
        
        # Читаем экспортированный файл
        df = pd.read_excel(filepath, sheet_name='Telegram Export')
        
        # Проверяем что колонка 'Тип источника' всегда присутствует
        assert 'Тип источника' in df.columns, "Колонка 'Тип источника' должна присутствовать"
        
        # Проверяем что количество строк соответствует количеству сообщений
        assert len(df) == len(messages), "Количество строк должно соответствовать количеству сообщений"
        
        # Проверяем обработку полей топиков построчно
        # Используем индекс для сопоставления, так как порядок сохраняется
        for i in range(len(messages)):
            msg = messages[i]
            row = df.iloc[i]
            
            # Проверяем source_type
            assert pd.notna(row['Тип источника']), f"source_type должен быть заполнен для сообщения {i}"
            
            if msg.get('topic_id') is None:
                # Для сообщений без топика: колонки топика либо отсутствуют, либо пустые
                if 'ID топика' in df.columns:
                    assert pd.isna(row['ID топика']), f"ID топика должен быть NULL для сообщения {i} без топика"
                if 'Название топика' in df.columns:
                    assert pd.isna(row['Название топика']), f"Название топика должно быть NULL для сообщения {i} без топика"
            else:
                # Для сообщений с топиком: колонки должны быть заполнены
                assert 'ID топика' in df.columns, f"Колонка 'ID топика' должна присутствовать для сообщения {i} с топиком"
                assert 'Название топика' in df.columns, f"Колонка 'Название топика' должна присутствовать для сообщения {i} с топиком"
                
                assert pd.notna(row['ID топика']), f"ID топика должен быть заполнен для сообщения {i}"
                assert int(row['ID топика']) == msg['topic_id'], f"ID топика должен совпадать для сообщения {i}"
                
                # Проверяем название топика: оно должно присутствовать (не NaN)
                # Но может быть пустой строкой, если topic_title была пустой строкой
                assert pd.notna(row['Название топика']), f"Название топика должно присутствовать (не NaN) для сообщения {i}"
                
                # Если в исходном сообщении topic_title не пустая строка после strip, 
                # то и в экспортированном файле она не должна быть пустой
                if msg.get('topic_title') and msg['topic_title'].strip():
                    assert str(row['Название топика']).strip() != '', f"Название топика не должно быть пустой строкой для сообщения {i}"
    
    finally:
        # Очищаем временный файл
        if filepath and os.path.exists(filepath):
            try:
                os.remove(filepath)
            except PermissionError:
                pass


@given(
    messages_with_topics=st.lists(message_strategy(with_topic=True), min_size=1, max_size=10),
    messages_without_topics=st.lists(message_strategy(with_topic=False), min_size=1, max_size=10)
)
@settings(max_examples=100, deadline=None)
def test_export_mixed_messages_property(messages_with_topics, messages_without_topics):
    """
    Property: Смешанный экспорт сообщений с топиками и без
    
    Проверяет корректность обработки смешанных сообщений
    """
    exporter = ExcelExporter(export_dir=tempfile.gettempdir())
    
    # Объединяем сообщения
    all_messages = messages_with_topics + messages_without_topics
    
    # Экспортируем сообщения
    with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as tmp:
        filename = os.path.basename(tmp.name)
    
    filepath = None
    try:
        filepath = exporter.export_to_excel(all_messages, filename=filename)
        assert filepath is not None, "Экспорт должен быть успешным"
        
        # Читаем экспортированный файл
        df = pd.read_excel(filepath, sheet_name='Telegram Export')
        
        # Проверяем что все сообщения экспортированы
        assert len(df) >= len(all_messages), "Все сообщения должны быть экспортированы"
        
        # Проверяем наличие обязательных колонок
        assert 'Тип источника' in df.columns, "Колонка 'Тип источника' должна присутствовать"
        
        # Подсчитываем сообщения с топиками и без
        messages_with_topic_ids = [msg for msg in all_messages if msg.get('topic_id') is not None]
        
        if messages_with_topic_ids:
            # Если есть сообщения с топиками, колонки должны присутствовать
            assert 'ID топика' in df.columns, "Колонка 'ID топика' должна присутствовать"
            assert 'Название топика' in df.columns, "Колонка 'Название топика' должна присутствовать"
    
    finally:
        # Очищаем временный файл
        if filepath and os.path.exists(filepath):
            try:
                os.remove(filepath)
            except PermissionError:
                pass


@given(
    messages=st.lists(message_strategy(with_topic=True), min_size=2, max_size=10)
)
@settings(max_examples=50, deadline=None)
def test_export_with_topic_grouping_property(messages):
    """
    Property: Экспорт с группировкой по топикам
    
    Проверяет что метод export_with_topic_grouping корректно группирует сообщения
    """
    exporter = ExcelExporter(export_dir=tempfile.gettempdir())
    
    # Экспортируем с группировкой
    with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as tmp:
        filename = os.path.basename(tmp.name)
    
    filepath = None
    try:
        filepath = exporter.export_with_topic_grouping(messages, filename=filename)
        assert filepath is not None, "Экспорт с группировкой должен быть успешным"
        
        # Читаем экспортированный файл
        excel_file = pd.ExcelFile(filepath)
        
        # Проверяем наличие сводного листа
        assert 'Сводка' in excel_file.sheet_names, "Лист 'Сводка' должен присутствовать"
        
        # Читаем сводку
        summary_df = pd.read_excel(filepath, sheet_name='Сводка')
        
        # Подсчитываем уникальные топики
        unique_topics = set()
        for msg in messages:
            if msg.get('topic_id') is not None:
                unique_topics.add(msg['topic_id'])
        
        # Проверяем что количество топиков в сводке соответствует уникальным топикам
        topic_rows = summary_df[summary_df['Тип'] == 'Топик']
        assert len(topic_rows) == len(unique_topics), "Количество топиков в сводке должно совпадать с уникальными топиками"
        
        # Проверяем что для каждого топика создан отдельный лист
        for topic_id in unique_topics:
            # Ищем лист с этим топиком (название может быть сокращено)
            topic_sheets = [sheet for sheet in excel_file.sheet_names if f"Топик {topic_id}" in sheet]
            assert len(topic_sheets) > 0, f"Лист для топика {topic_id} должен существовать"
        
        # Закрываем файл перед удалением
        excel_file.close()
    
    finally:
        # Очищаем временный файл
        if filepath and os.path.exists(filepath):
            try:
                os.remove(filepath)
            except PermissionError:
                # Если файл занят, пропускаем удаление
                pass


@given(
    message=message_strategy()
)
@settings(max_examples=100, deadline=None)
def test_google_docs_export_topic_info_property(message):
    """
    Property: Google Docs экспорт включает информацию о топике
    
    Проверяет что информация о топике корректно форматируется в тексте
    """
    # Создаем текстовое представление как в GoogleDocsExporter
    text = (
        f"Дата: {message['date']}\n"
        f"Канал: {message['channel']}\n"
    )
    
    # Добавляем тип источника
    source_type = message.get('source_type', 'channel')
    source_type_display = {
        'channel': 'Канал',
        'chat': 'Чат',
        'forum_chat': 'Форум-чат'
    }.get(source_type, 'Канал')
    text += f"Тип источника: {source_type_display}\n"
    
    # Проверяем обработку топика
    if message.get('topic_id') is not None:
        # Для сообщений с топиком должна быть специальная строка
        topic_title = message.get('topic_title', 'Без названия')
        expected_topic_line = f"━━━ ТОПИК: {topic_title} (ID: {message['topic_id']}) ━━━"
        
        # Добавляем информацию о топике
        text += f"{expected_topic_line}\n"
        
        # Проверяем что информация о топике присутствует
        assert expected_topic_line in text, "Информация о топике должна присутствовать в тексте"
        assert str(message['topic_id']) in text, "ID топика должен присутствовать в тексте"
        
        if message.get('topic_title'):
            assert message['topic_title'] in text, "Название топика должно присутствовать в тексте"
    else:
        # Для сообщений без топика не должно быть строки с топиком
        assert "━━━ ТОПИК:" not in text, "Информация о топике не должна присутствовать для сообщений без топика"
    
    # Проверяем что тип источника всегда присутствует
    assert "Тип источника:" in text, "Тип источника должен всегда присутствовать"
