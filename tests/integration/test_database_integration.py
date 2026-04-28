# -*- coding: utf-8 -*-
"""
Integration-тесты для Database
Проверяют работу новых методов для статистики и запросов по топикам
"""
import pytest
import tempfile
import os
from datetime import datetime
from src.database.models import Database, Message


class TestDatabaseIntegration:
    """Integration-тесты для Database"""
    
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
    
    def test_get_stats_by_source_type_with_different_types(self, temp_db):
        """
        Integration-тест: get_stats_by_source_type() с различными типами источников
        
        Проверяет корректность подсчета сообщений по типам источников.
        Requirements: 9.1, 9.2
        """
        db, db_path = temp_db
        
        # Добавляем сообщения разных типов
        # 3 сообщения из канала
        for i in range(3):
            message = Message(
                id=0,
                channel='test_channel',
                message_id=i + 1,
                text=f'Channel message {i + 1}',
                date=datetime.now(),
                author='Channel Author',
                views=100,
                forwards=10,
                replies=5,
                source_type='channel',
                topic_id=None,
                topic_title=None
            )
            db.add_message(message)
        
        # 2 сообщения из обычного чата
        for i in range(2):
            message = Message(
                id=0,
                channel='test_chat',
                message_id=i + 1,
                text=f'Chat message {i + 1}',
                date=datetime.now(),
                author='Chat Author',
                views=50,
                forwards=5,
                replies=2,
                source_type='chat',
                topic_id=None,
                topic_title=None
            )
            db.add_message(message)
        
        # 4 сообщения из форум-чата (2 топика по 2 сообщения)
        for topic_num in range(1, 3):
            for msg_num in range(1, 3):
                message = Message(
                    id=0,
                    channel='test_forum',
                    message_id=topic_num * 10 + msg_num,
                    text=f'Forum message {msg_num} in topic {topic_num}',
                    date=datetime.now(),
                    author='Forum Author',
                    views=75,
                    forwards=7,
                    replies=3,
                    source_type='forum_chat',
                    topic_id=topic_num,
                    topic_title=f'Topic {topic_num}'
                )
                db.add_message(message)
        
        # Получаем статистику
        stats = db.get_stats_by_source_type()
        
        # Проверяем статистику по типам источников
        assert 'by_source_type' in stats, "Должна быть статистика по типам источников"
        assert stats['by_source_type']['channel'] == 3, "Должно быть 3 сообщения из каналов"
        assert stats['by_source_type']['chat'] == 2, "Должно быть 2 сообщения из чатов"
        assert stats['by_source_type']['forum_chat'] == 4, "Должно быть 4 сообщения из форум-чатов"
        
        # Проверяем статистику по топикам
        assert 'forum_topics' in stats, "Должна быть статистика по топикам"
        assert len(stats['forum_topics']) == 2, "Должно быть 2 топика"
        
        # Проверяем детали топиков
        topics_dict = {t['topic_id']: t for t in stats['forum_topics']}
        assert 1 in topics_dict, "Должен быть топик с ID 1"
        assert 2 in topics_dict, "Должен быть топик с ID 2"
        assert topics_dict[1]['topic_title'] == 'Topic 1', "Название топика 1 должно совпадать"
        assert topics_dict[1]['messages_count'] == 2, "В топике 1 должно быть 2 сообщения"
        assert topics_dict[2]['topic_title'] == 'Topic 2', "Название топика 2 должно совпадать"
        assert topics_dict[2]['messages_count'] == 2, "В топике 2 должно быть 2 сообщения"
    
    def test_get_stats_by_source_type_empty_database(self, temp_db):
        """
        Integration-тест: get_stats_by_source_type() с пустой базой
        
        Проверяет корректность работы метода на пустой базе.
        Requirements: 9.1
        """
        db, db_path = temp_db
        
        # Получаем статистику из пустой базы
        stats = db.get_stats_by_source_type()
        
        assert 'by_source_type' in stats, "Должна быть статистика по типам источников"
        assert len(stats['by_source_type']) == 0, "Статистика должна быть пустой"
        assert 'forum_topics' in stats, "Должна быть статистика по топикам"
        assert len(stats['forum_topics']) == 0, "Список топиков должен быть пустым"
    
    def test_get_messages_by_topic(self, temp_db):
        """
        Integration-тест: get_messages_by_topic() для получения сообщений из топика
        
        Проверяет корректность получения сообщений из конкретного топика.
        Requirements: 9.3, 9.4
        """
        db, db_path = temp_db
        
        # Добавляем сообщения в разные топики
        # Топик 1: 3 сообщения
        for i in range(1, 4):
            message = Message(
                id=0,
                channel='test_forum',
                message_id=10 + i,
                text=f'Message {i} in topic 1',
                date=datetime(2024, 1, i, 12, 0, 0),
                author='Author 1',
                views=100,
                forwards=10,
                replies=5,
                source_type='forum_chat',
                topic_id=1,
                topic_title='Topic 1'
            )
            db.add_message(message)
        
        # Топик 2: 2 сообщения
        for i in range(1, 3):
            message = Message(
                id=0,
                channel='test_forum',
                message_id=20 + i,
                text=f'Message {i} in topic 2',
                date=datetime(2024, 1, i, 14, 0, 0),
                author='Author 2',
                views=50,
                forwards=5,
                replies=2,
                source_type='forum_chat',
                topic_id=2,
                topic_title='Topic 2'
            )
            db.add_message(message)
        
        # Получаем сообщения из топика 1
        messages_topic_1 = db.get_messages_by_topic(topic_id=1)
        
        assert len(messages_topic_1) == 3, "Должно быть 3 сообщения из топика 1"
        assert all(msg.topic_id == 1 for msg in messages_topic_1), "Все сообщения должны быть из топика 1"
        assert all(msg.topic_title == 'Topic 1' for msg in messages_topic_1), "Все сообщения должны иметь название топика 1"
        
        # Получаем сообщения из топика 2
        messages_topic_2 = db.get_messages_by_topic(topic_id=2)
        
        assert len(messages_topic_2) == 2, "Должно быть 2 сообщения из топика 2"
        assert all(msg.topic_id == 2 for msg in messages_topic_2), "Все сообщения должны быть из топика 2"
        assert all(msg.topic_title == 'Topic 2' for msg in messages_topic_2), "Все сообщения должны иметь название топика 2"
    
    def test_get_messages_by_topic_with_limit(self, temp_db):
        """
        Integration-тест: get_messages_by_topic() с ограничением количества
        
        Проверяет корректность работы параметра limit.
        Requirements: 9.3
        """
        db, db_path = temp_db
        
        # Добавляем 10 сообщений в топик
        for i in range(1, 11):
            message = Message(
                id=0,
                channel='test_forum',
                message_id=i,
                text=f'Message {i}',
                date=datetime(2024, 1, i, 12, 0, 0),
                author='Author',
                views=100,
                forwards=10,
                replies=5,
                source_type='forum_chat',
                topic_id=1,
                topic_title='Test Topic'
            )
            db.add_message(message)
        
        # Получаем только 5 сообщений
        messages = db.get_messages_by_topic(topic_id=1, limit=5)
        
        assert len(messages) == 5, "Должно быть получено только 5 сообщений"
        assert all(msg.topic_id == 1 for msg in messages), "Все сообщения должны быть из топика 1"
    
    def test_get_messages_by_topic_nonexistent_topic(self, temp_db):
        """
        Integration-тест: get_messages_by_topic() для несуществующего топика
        
        Проверяет корректность работы метода для несуществующего топика.
        Requirements: 9.3
        """
        db, db_path = temp_db
        
        # Добавляем сообщения в топик 1
        message = Message(
            id=0,
            channel='test_forum',
            message_id=1,
            text='Message in topic 1',
            date=datetime.now(),
            author='Author',
            views=100,
            forwards=10,
            replies=5,
            source_type='forum_chat',
            topic_id=1,
            topic_title='Topic 1'
        )
        db.add_message(message)
        
        # Пытаемся получить сообщения из несуществующего топика 999
        messages = db.get_messages_by_topic(topic_id=999)
        
        assert len(messages) == 0, "Должен вернуться пустой список для несуществующего топика"
    
    def test_save_messages_with_new_fields(self, temp_db):
        """
        Integration-тест: Сохранение сообщений с новыми полями
        
        Проверяет корректность сохранения и извлечения сообщений с полями source_type, topic_id, topic_title.
        Requirements: 9.4, 13.5
        """
        db, db_path = temp_db
        
        # Создаем сообщение из форум-чата с полным набором полей
        original_message = Message(
            id=0,
            channel='test_forum',
            message_id=123,
            text='Test forum message',
            date=datetime(2024, 1, 15, 12, 30, 0),
            author='Test Author',
            views=150,
            forwards=15,
            replies=7,
            comments='Test comments',
            media_type='photo',
            media_url='https://example.com/photo.jpg',
            source_type='forum_chat',
            topic_id=42,
            topic_title='Important Topic'
        )
        
        # Сохраняем сообщение
        success = db.add_message(original_message)
        assert success, "Сообщение должно быть успешно сохранено"
        
        # Извлекаем сообщение обратно
        messages = db.get_messages(channel='test_forum')
        
        assert len(messages) == 1, "Должно быть одно сообщение"
        retrieved_message = messages[0]
        
        # Проверяем все поля
        assert retrieved_message.channel == 'test_forum'
        assert retrieved_message.message_id == 123
        assert retrieved_message.text == 'Test forum message'
        assert retrieved_message.author == 'Test Author'
        assert retrieved_message.views == 150
        assert retrieved_message.forwards == 15
        assert retrieved_message.replies == 7
        assert retrieved_message.comments == 'Test comments'
        assert retrieved_message.media_type == 'photo'
        assert retrieved_message.media_url == 'https://example.com/photo.jpg'
        
        # Проверяем новые поля
        assert retrieved_message.source_type == 'forum_chat', "source_type должен сохраниться"
        assert retrieved_message.topic_id == 42, "topic_id должен сохраниться"
        assert retrieved_message.topic_title == 'Important Topic', "topic_title должен сохраниться"
    
    def test_get_messages_backward_compatibility(self, temp_db):
        """
        Integration-тест: Обратная совместимость метода get_messages
        
        Проверяет что метод get_messages корректно работает с новыми полями.
        Requirements: 12.2, 13.5
        """
        db, db_path = temp_db
        
        # Добавляем сообщения разных типов
        messages_to_add = [
            Message(
                id=0, channel='channel1', message_id=1, text='Channel msg',
                date=datetime.now(), author='Author1', views=100, forwards=10, replies=5,
                source_type='channel', topic_id=None, topic_title=None
            ),
            Message(
                id=0, channel='chat1', message_id=2, text='Chat msg',
                date=datetime.now(), author='Author2', views=50, forwards=5, replies=2,
                source_type='chat', topic_id=None, topic_title=None
            ),
            Message(
                id=0, channel='forum1', message_id=3, text='Forum msg',
                date=datetime.now(), author='Author3', views=75, forwards=7, replies=3,
                source_type='forum_chat', topic_id=1, topic_title='Topic 1'
            )
        ]
        
        for msg in messages_to_add:
            db.add_message(msg)
        
        # Получаем все сообщения
        all_messages = db.get_messages()
        
        assert len(all_messages) == 3, "Должно быть 3 сообщения"
        
        # Проверяем что все сообщения имеют корректные значения новых полей
        channel_msg = next(m for m in all_messages if m.source_type == 'channel')
        assert channel_msg.topic_id is None
        assert channel_msg.topic_title is None
        
        chat_msg = next(m for m in all_messages if m.source_type == 'chat')
        assert chat_msg.topic_id is None
        assert chat_msg.topic_title is None
        
        forum_msg = next(m for m in all_messages if m.source_type == 'forum_chat')
        assert forum_msg.topic_id == 1
        assert forum_msg.topic_title == 'Topic 1'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
