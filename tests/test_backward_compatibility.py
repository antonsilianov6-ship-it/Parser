# -*- coding: utf-8 -*-
"""
Regression-тесты для обратной совместимости
Проверяют что существующая функциональность парсинга каналов работает без изменений
"""
import pytest
import sqlite3
import tempfile
import os
from datetime import datetime
from unittest.mock import Mock, MagicMock
from hypothesis import given, settings, strategies as st
from src.database.models import Database, Message
from src.telegram.link_formatter import LinkFormatter


class TestBackwardCompatibility:
    """Regression-тесты для обратной совместимости"""
    
    @pytest.fixture
    def temp_db(self):
        """Создает временную базу данных для тестов"""
        fd, path = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        
        db = Database(path)
        yield db, path
        
        # Очистка после теста
        try:
            import time
            time.sleep(0.1)
            if os.path.exists(path):
                os.unlink(path)
        except PermissionError:
            pass
    
    # ========== Property 16: Backward compatibility for untyped messages ==========
    
    @given(
        message_id=st.integers(min_value=1, max_value=999999),
        channel_name=st.text(min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=('Ll', 'Lu', 'Nd', 'Pd')))
    )
    @settings(max_examples=100)
    def test_property_16_untyped_messages_treated_as_channel(self, message_id, channel_name):
        """
        Property 16: Backward compatibility for untyped messages
        
        For any existing message in the database without a source_type value (NULL),
        the system SHALL treat it as a 'channel' type by default, ensuring backward
        compatibility with existing data.
        
        Validates: Requirements 12.2
        """
        fd, path = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        
        try:
            db = Database(path)
            
            # Вставляем сообщение напрямую в БД без source_type (имитация старых данных)
            with sqlite3.connect(path) as conn:
                conn.execute(
                    """INSERT INTO messages 
                    (channel, message_id, text, date, author, views, forwards, replies)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (channel_name, message_id, 'Old message', datetime.now(), 
                     'Author', 0, 0, 0)
                )
                conn.commit()
                
                # Устанавливаем source_type в NULL (имитация старых данных)
                conn.execute(
                    "UPDATE messages SET source_type = NULL WHERE message_id = ?",
                    (message_id,)
                )
                conn.commit()
            
            # Выполняем миграцию
            db.migrate_existing_data()
            
            # Проверяем что source_type установлен в 'channel'
            with sqlite3.connect(path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(
                    "SELECT source_type FROM messages WHERE message_id = ?",
                    (message_id,)
                )
                row = cursor.fetchone()
                
                assert row is not None, "Сообщение должно быть в базе"
                assert row['source_type'] == 'channel', \
                    "Сообщения без source_type должны обрабатываться как 'channel'"
        
        finally:
            try:
                import time
                time.sleep(0.1)
                if os.path.exists(path):
                    os.unlink(path)
            except PermissionError:
                pass
    
    def test_untyped_messages_default_to_channel_on_read(self, temp_db):
        """
        Regression: Сообщения без source_type читаются как 'channel'
        Requirements: 12.2
        """
        db, db_path = temp_db
        
        # Вставляем сообщение напрямую в БД без source_type
        with sqlite3.connect(db_path) as conn:
            conn.execute(
                """INSERT INTO messages 
                (channel, message_id, text, date, author, views, forwards, replies)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                ('old_channel', 999, 'Legacy message', datetime.now(), 
                 'Legacy Author', 100, 10, 5)
            )
            conn.commit()
            
            # Устанавливаем source_type в NULL
            conn.execute(
                "UPDATE messages SET source_type = NULL WHERE message_id = ?",
                (999,)
            )
            conn.commit()
        
        # Выполняем миграцию
        db.migrate_existing_data()
        
        # Читаем сообщение через API базы данных
        messages = db.get_messages(channel='old_channel')
        
        assert len(messages) == 1, "Должно быть одно сообщение"
        msg = messages[0]
        assert msg.source_type == 'channel', "source_type должен быть 'channel' после миграции"
        assert msg.message_id == 999
        assert msg.text == 'Legacy message'
    
    def test_migration_idempotent(self, temp_db):
        """
        Regression: Миграция может быть выполнена несколько раз без побочных эффектов
        Requirements: 12.5, 12.6
        """
        db, db_path = temp_db
        
        # Вставляем сообщение без source_type
        with sqlite3.connect(db_path) as conn:
            conn.execute(
                """INSERT INTO messages 
                (channel, message_id, text, date, author, views, forwards, replies)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                ('test_channel', 1, 'Test', datetime.now(), 'Author', 0, 0, 0)
            )
            conn.commit()
            
            conn.execute(
                "UPDATE messages SET source_type = NULL WHERE message_id = ?",
                (1,)
            )
            conn.commit()
        
        # Выполняем миграцию первый раз
        db.migrate_existing_data()
        
        # Проверяем результат
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT source_type FROM messages WHERE message_id = 1")
            row = cursor.fetchone()
            assert row['source_type'] == 'channel'
        
        # Выполняем миграцию второй раз
        db.migrate_existing_data()
        
        # Проверяем что ничего не изменилось
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT source_type FROM messages WHERE message_id = 1")
            row = cursor.fetchone()
            assert row['source_type'] == 'channel', "Повторная миграция не должна изменять данные"
    
    # ========== Property 17: Channel link format preservation ==========
    
    @given(
        channel_name=st.text(min_size=1, max_size=32, alphabet=st.characters(whitelist_categories=('Ll', 'Lu', 'Nd', 'Pc'))),
        message_id=st.integers(min_value=1, max_value=999999)
    )
    @settings(max_examples=100)
    def test_property_17_channel_link_format_preserved(self, channel_name, message_id):
        """
        Property 17: Channel link format preservation
        
        For any channel entity, the LinkFormatter SHALL generate links using the same
        format and logic as before the changes, ensuring existing channel link generation
        remains unchanged.
        
        Validates: Requirements 12.4
        """
        # Создаем mock entity для публичного канала
        channel_entity = Mock()
        channel_entity.username = channel_name
        channel_entity.id = 1234567890
        
        # Формируем ссылку на сообщение в канале
        link = LinkFormatter.format_message_link(
            f"https://t.me/{channel_name}",
            channel_entity,
            message_id
        )
        
        # Проверяем что формат ссылки соответствует ожидаемому
        assert link is not None, "Ссылка не должна быть None"
        assert link.startswith('https://t.me/'), "Ссылка должна начинаться с https://t.me/"
        assert f"/{message_id}" in link, "Ссылка должна содержать message_id"
        assert 'None' not in link, "Ссылка не должна содержать 'None'"
        
        # Проверяем что формат точно такой же как раньше
        expected_link = f"https://t.me/{channel_name}/{message_id}"
        assert link == expected_link, \
            f"Формат ссылки должен быть {expected_link}, получено {link}"
    
    def test_channel_link_format_public_channel(self):
        """
        Regression: Формат ссылок для публичных каналов не изменился
        Requirements: 12.4
        """
        # Создаем mock entity для публичного канала
        channel_entity = Mock()
        channel_entity.username = 'test_channel'
        channel_entity.id = 1234567890
        
        # Формируем ссылку
        link = LinkFormatter.format_message_link(
            "https://t.me/test_channel",
            channel_entity,
            123
        )
        
        # Проверяем формат
        assert link == "https://t.me/test_channel/123", \
            "Формат ссылки для публичного канала должен быть https://t.me/channel/message_id"
    
    def test_channel_link_format_private_channel(self):
        """
        Regression: Формат ссылок для приватных каналов не изменился
        Requirements: 12.4
        """
        # Создаем mock entity для приватного канала
        channel_entity = Mock()
        channel_entity.username = None
        channel_entity.id = -1001234567890
        
        # Формируем ссылку
        link = LinkFormatter.format_message_link(
            "https://t.me/c/1234567890",
            channel_entity,
            456
        )
        
        # Проверяем формат
        assert link == "https://t.me/c/1234567890/456", \
            "Формат ссылки для приватного канала должен быть https://t.me/c/CHAT_ID/message_id"
    
    def test_channel_link_uses_original_username(self):
        """
        Regression: LinkFormatter использует оригинальный username из ссылки
        Requirements: 12.4
        """
        # Создаем mock entity
        channel_entity = Mock()
        channel_entity.username = 'different_name'
        channel_entity.id = 1234567890
        
        # Формируем ссылку с оригинальным username
        link = LinkFormatter.format_message_link(
            "https://t.me/original_channel",
            channel_entity,
            789
        )
        
        # Проверяем что используется оригинальный username
        assert link == "https://t.me/original_channel/789", \
            "Должен использоваться оригинальный username из ссылки"
    
    def test_channel_link_fallback_to_entity_username(self):
        """
        Regression: LinkFormatter использует username из entity если оригинальная ссылка приватная
        Requirements: 12.4
        """
        # Создаем mock entity
        channel_entity = Mock()
        channel_entity.username = 'entity_channel'
        channel_entity.id = 1234567890
        
        # Формируем ссылку для приватного канала (без username в ссылке)
        link = LinkFormatter.format_message_link(
            "https://t.me/c/1234567890",
            channel_entity,
            111
        )
        
        # Проверяем что используется username из entity
        assert link == "https://t.me/entity_channel/111", \
            "Должен использоваться username из entity для приватных каналов"
    
    def test_existing_channel_parsing_logic_unchanged(self, temp_db):
        """
        Regression: Существующая логика парсинга каналов работает без изменений
        Requirements: 12.1, 12.3
        """
        db, db_path = temp_db
        
        # Создаем сообщение из канала (как раньше)
        message = Message(
            id=0,
            channel='test_channel',
            message_id=1,
            text='Channel message',
            date=datetime.now(),
            author='Channel Author',
            views=100,
            forwards=10,
            replies=5,
            comments='Some comments',
            media_type='photo',
            media_url='https://example.com/photo.jpg'
        )
        
        # Добавляем в БД
        success = db.add_message(message)
        assert success, "Сообщение должно быть добавлено"
        
        # Читаем обратно
        messages = db.get_messages(channel='test_channel')
        
        assert len(messages) == 1
        msg = messages[0]
        
        # Проверяем что все поля сохранились
        assert msg.channel == 'test_channel'
        assert msg.message_id == 1
        assert msg.text == 'Channel message'
        assert msg.author == 'Channel Author'
        assert msg.views == 100
        assert msg.forwards == 10
        assert msg.replies == 5
        assert msg.comments == 'Some comments'
        assert msg.media_type == 'photo'
        assert msg.media_url == 'https://example.com/photo.jpg'
        
        # Проверяем что source_type установлен в 'channel' по умолчанию
        assert msg.source_type == 'channel'
    
    def test_channel_messages_have_null_topic_fields(self, temp_db):
        """
        Regression: Сообщения из каналов имеют NULL в полях топиков
        Requirements: 12.1, 12.3
        """
        db, db_path = temp_db
        
        # Создаем сообщение из канала
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
            source_type='channel'
        )
        
        db.add_message(message)
        
        # Проверяем что topic_id и topic_title равны NULL
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT topic_id, topic_title FROM messages WHERE message_id = 1"
            )
            row = cursor.fetchone()
            
            assert row['topic_id'] is None, "topic_id должен быть NULL для каналов"
            assert row['topic_title'] is None, "topic_title должен быть NULL для каналов"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
