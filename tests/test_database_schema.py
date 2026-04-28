# -*- coding: utf-8 -*-
"""
Smoke-тесты для схемы базы данных
Проверяют наличие полей source_type, topic_id, topic_title и индексов
"""
import pytest
import sqlite3
import tempfile
import os
from datetime import datetime
from src.database.models import Database, Message


class TestDatabaseSchema:
    """Smoke-тесты для проверки схемы базы данных"""
    
    @pytest.fixture
    def temp_db(self):
        """Создает временную базу данных для тестов"""
        fd, path = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        
        db = Database(path)
        yield db, path
        
        # Очистка после теста - закрываем все соединения перед удалением
        try:
            # Даем время на закрытие соединений
            import time
            time.sleep(0.1)
            if os.path.exists(path):
                os.unlink(path)
        except PermissionError:
            # На Windows файл может быть заблокирован - пропускаем
            pass
    
    def test_source_type_field_exists(self, temp_db):
        """
        Smoke-тест: Проверяет наличие поля source_type в таблице messages
        Requirements: 5.1
        """
        db, db_path = temp_db
        
        with sqlite3.connect(db_path) as conn:
            cursor = conn.execute("PRAGMA table_info(messages)")
            columns = {row[1]: row[2] for row in cursor.fetchall()}
            
            assert 'source_type' in columns, "Поле source_type отсутствует в таблице messages"
            assert columns['source_type'] == 'TEXT', "Поле source_type должно быть типа TEXT"
    
    def test_topic_id_field_exists(self, temp_db):
        """
        Smoke-тест: Проверяет наличие поля topic_id в таблице messages
        Requirements: 5.2
        """
        db, db_path = temp_db
        
        with sqlite3.connect(db_path) as conn:
            cursor = conn.execute("PRAGMA table_info(messages)")
            columns = {row[1]: row[2] for row in cursor.fetchall()}
            
            assert 'topic_id' in columns, "Поле topic_id отсутствует в таблице messages"
            assert columns['topic_id'] == 'INTEGER', "Поле topic_id должно быть типа INTEGER"
    
    def test_topic_title_field_exists(self, temp_db):
        """
        Smoke-тест: Проверяет наличие поля topic_title в таблице messages
        Requirements: 5.3
        """
        db, db_path = temp_db
        
        with sqlite3.connect(db_path) as conn:
            cursor = conn.execute("PRAGMA table_info(messages)")
            columns = {row[1]: row[2] for row in cursor.fetchall()}
            
            assert 'topic_title' in columns, "Поле topic_title отсутствует в таблице messages"
            assert columns['topic_title'] == 'TEXT', "Поле topic_title должно быть типа TEXT"
    
    def test_source_type_index_exists(self, temp_db):
        """
        Smoke-тест: Проверяет создание индекса idx_messages_source_type
        Requirements: 5.6
        """
        db, db_path = temp_db
        
        with sqlite3.connect(db_path) as conn:
            cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='index' AND name='idx_messages_source_type'")
            result = cursor.fetchone()
            
            assert result is not None, "Индекс idx_messages_source_type не создан"
            assert result[0] == 'idx_messages_source_type', "Имя индекса не совпадает"
    
    def test_topic_id_index_exists(self, temp_db):
        """
        Smoke-тест: Проверяет создание индекса idx_messages_topic_id
        Requirements: 5.7
        """
        db, db_path = temp_db
        
        with sqlite3.connect(db_path) as conn:
            cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='index' AND name='idx_messages_topic_id'")
            result = cursor.fetchone()
            
            assert result is not None, "Индекс idx_messages_topic_id не создан"
            assert result[0] == 'idx_messages_topic_id', "Имя индекса не совпадает"
    
    def test_composite_index_exists(self, temp_db):
        """
        Smoke-тест: Проверяет создание композитного индекса idx_messages_source_topic
        Requirements: 5.6, 5.7
        """
        db, db_path = temp_db
        
        with sqlite3.connect(db_path) as conn:
            cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='index' AND name='idx_messages_source_topic'")
            result = cursor.fetchone()
            
            assert result is not None, "Индекс idx_messages_source_topic не создан"
            assert result[0] == 'idx_messages_source_topic', "Имя индекса не совпадает"
    
    def test_migration_sets_default_source_type(self, temp_db):
        """
        Smoke-тест: Проверяет что миграция устанавливает source_type='channel' для существующих записей
        Requirements: 5.1, 12.6
        """
        db, db_path = temp_db
        
        # Создаем сообщение без явного указания source_type
        message = Message(
            id=0,
            channel='test_channel',
            message_id=1,
            text='Test message',
            date=datetime.now(),
            author='Test Author',
            views=0,
            forwards=0,
            replies=0
        )
        
        db.add_message(message)
        
        # Проверяем что source_type установлен в 'channel'
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT source_type FROM messages WHERE message_id = 1")
            row = cursor.fetchone()
            
            assert row is not None, "Сообщение не было добавлено"
            assert row['source_type'] == 'channel', "source_type должен быть 'channel' по умолчанию"
    
    def test_migration_preserves_existing_data(self, temp_db):
        """
        Smoke-тест: Проверяет что миграция не нарушает существующие данные
        Requirements: 12.5
        """
        db, db_path = temp_db
        
        # Добавляем тестовое сообщение
        message = Message(
            id=0,
            channel='test_channel',
            message_id=123,
            text='Test message content',
            date=datetime(2024, 1, 15, 12, 0, 0),
            author='Test Author',
            views=100,
            forwards=10,
            replies=5,
            comments='Test comments',
            media_type='photo',
            media_url='https://example.com/photo.jpg'
        )
        
        db.add_message(message)
        
        # Запускаем миграцию повторно
        db.migrate_existing_data()
        
        # Проверяем что данные сохранились
        messages = db.get_messages(channel='test_channel')
        
        assert len(messages) == 1, "Сообщение должно быть в базе"
        msg = messages[0]
        assert msg.message_id == 123
        assert msg.text == 'Test message content'
        assert msg.author == 'Test Author'
        assert msg.views == 100
        assert msg.forwards == 10
        assert msg.replies == 5
        assert msg.comments == 'Test comments'
        assert msg.media_type == 'photo'
        assert msg.media_url == 'https://example.com/photo.jpg'
        assert msg.source_type == 'channel'
    
    def test_new_fields_accept_null_values(self, temp_db):
        """
        Smoke-тест: Проверяет что topic_id и topic_title могут быть NULL
        Requirements: 5.4, 5.5
        """
        db, db_path = temp_db
        
        # Создаем сообщение из канала (без топиков)
        message = Message(
            id=0,
            channel='test_channel',
            message_id=1,
            text='Channel message',
            date=datetime.now(),
            author='Author',
            views=0,
            forwards=0,
            replies=0,
            source_type='channel',
            topic_id=None,
            topic_title=None
        )
        
        db.add_message(message)
        
        # Проверяем что NULL значения сохранились
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT topic_id, topic_title FROM messages WHERE message_id = 1")
            row = cursor.fetchone()
            
            assert row is not None
            assert row['topic_id'] is None, "topic_id должен быть NULL для каналов"
            assert row['topic_title'] is None, "topic_title должен быть NULL для каналов"
    
    def test_new_fields_accept_values_for_forum_chats(self, temp_db):
        """
        Smoke-тест: Проверяет что topic_id и topic_title сохраняются для форум-чатов
        Requirements: 5.2, 5.3, 5.5
        """
        db, db_path = temp_db
        
        # Создаем сообщение из форум-чата с топиком
        message = Message(
            id=0,
            channel='test_forum',
            message_id=1,
            text='Forum message',
            date=datetime.now(),
            author='Author',
            views=0,
            forwards=0,
            replies=0,
            source_type='forum_chat',
            topic_id=42,
            topic_title='Test Topic'
        )
        
        db.add_message(message)
        
        # Проверяем что значения сохранились
        messages = db.get_messages(channel='test_forum')
        
        assert len(messages) == 1
        msg = messages[0]
        assert msg.source_type == 'forum_chat'
        assert msg.topic_id == 42, "topic_id должен сохраниться"
        assert msg.topic_title == 'Test Topic', "topic_title должен сохраниться"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
