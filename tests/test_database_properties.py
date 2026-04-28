# -*- coding: utf-8 -*-
"""
Property-based тесты для Database
Проверяют универсальные свойства корректности работы с БД
"""
import pytest
import sqlite3
import tempfile
import os
from datetime import datetime
from contextlib import contextmanager
from hypothesis import given, settings, strategies as st, HealthCheck
from src.database.models import Database, Message


@contextmanager
def create_temp_db():
    """Контекстный менеджер для создания временной БД"""
    fd, path = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    
    try:
        db = Database(path)
        yield db, path
    finally:
        # Очистка после теста
        try:
            import time
            time.sleep(0.1)
            if os.path.exists(path):
                os.unlink(path)
        except PermissionError:
            pass


class TestDatabaseProperties:
    """Property-based тесты для Database"""
    
    @given(
        source_type=st.sampled_from(['channel', 'chat']),
        message_id=st.integers(min_value=1, max_value=999999),
        channel_name=st.text(min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=('Ll', 'Lu', 'Nd', 'Pd')))
    )
    @settings(max_examples=100)
    def test_property_7_topic_fields_null_for_channels_and_chats(self, source_type, message_id, channel_name):
        """
        Property 7: Database topic field nullability
        
        For any message from a channel or regular chat (source_type='channel' or 'chat'),
        the Database SHALL store topic_id and topic_title as NULL.
        
        Validates: Requirements 5.4, 5.5
        """
        with create_temp_db() as (db, db_path):
            # Создаем сообщение из канала или чата (без топиков)
            message = Message(
                id=0,
                channel=channel_name,
                message_id=message_id,
                text=f'Test message {message_id}',
                date=datetime.now(),
                author='Test Author',
                views=0,
                forwards=0,
                replies=0,
                source_type=source_type,
                topic_id=None,
                topic_title=None
            )
            
            # Добавляем сообщение в БД
            success = db.add_message(message)
            assert success, "Сообщение должно быть успешно добавлено"
            
            # Проверяем что topic_id и topic_title равны NULL в БД
            with sqlite3.connect(db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(
                    "SELECT topic_id, topic_title FROM messages WHERE channel = ? AND message_id = ?",
                    (channel_name, message_id)
                )
                row = cursor.fetchone()
                
                assert row is not None, "Сообщение должно быть в базе"
                assert row['topic_id'] is None, f"topic_id должен быть NULL для source_type='{source_type}'"
                assert row['topic_title'] is None, f"topic_title должен быть NULL для source_type='{source_type}'"
    
    @given(
        topic_id=st.integers(min_value=1, max_value=999999),
        topic_title=st.text(min_size=1, max_size=100, alphabet=st.characters(whitelist_categories=('Ll', 'Lu', 'Nd', 'Zs', 'Pd'))),
        message_id=st.integers(min_value=1, max_value=999999),
        channel_name=st.text(min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=('Ll', 'Lu', 'Nd', 'Pd')))
    )
    @settings(max_examples=100)
    def test_property_7_topic_fields_not_null_for_forum_chats(self, topic_id, topic_title, message_id, channel_name):
        """
        Property 7: Database topic field nullability (part 2)
        
        For any message from forum chats (source_type='forum_chat'),
        topic_id and topic_title SHALL contain non-null values.
        
        Validates: Requirements 5.4, 5.5
        """
        with create_temp_db() as (db, db_path):
            # Создаем сообщение из форум-чата с топиком
            message = Message(
                id=0,
                channel=channel_name,
                message_id=message_id,
                text=f'Forum message {message_id}',
                date=datetime.now(),
                author='Test Author',
                views=0,
                forwards=0,
                replies=0,
                source_type='forum_chat',
                topic_id=topic_id,
                topic_title=topic_title
            )
            
            # Добавляем сообщение в БД
            success = db.add_message(message)
            assert success, "Сообщение должно быть успешно добавлено"
            
            # Проверяем что topic_id и topic_title сохранились в БД
            with sqlite3.connect(db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(
                    "SELECT topic_id, topic_title FROM messages WHERE channel = ? AND message_id = ?",
                    (channel_name, message_id)
                )
                row = cursor.fetchone()
                
                assert row is not None, "Сообщение должно быть в базе"
                assert row['topic_id'] is not None, "topic_id НЕ должен быть NULL для forum_chat"
                assert row['topic_title'] is not None, "topic_title НЕ должен быть NULL для forum_chat"
                assert row['topic_id'] == topic_id, "topic_id должен совпадать с исходным значением"
                assert row['topic_title'] == topic_title, "topic_title должен совпадать с исходным значением"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
