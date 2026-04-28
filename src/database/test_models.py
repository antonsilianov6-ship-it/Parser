# -*- coding: utf-8 -*-
"""
Unit тесты для модуля database/models.py
Тестирование батчинга и транзакций
"""
import pytest
import sqlite3
import os
from datetime import datetime
from src.database.models import Database, Message


@pytest.fixture
def test_db_path(tmp_path):
    """Создает временную базу данных для тестов"""
    db_path = tmp_path / "test_parser.db"
    return str(db_path)


@pytest.fixture
def database(test_db_path):
    """Создает экземпляр Database для тестов"""
    db = Database(test_db_path)
    yield db
    # Cleanup - закрываем все соединения перед удалением
    if hasattr(db, 'conn') and db.conn:
        db.conn.close()
    # Даем время на освобождение файла
    import time
    time.sleep(0.1)
    if os.path.exists(test_db_path):
        try:
            os.remove(test_db_path)
        except PermissionError:
            # На Windows файл может быть заблокирован - игнорируем
            pass


@pytest.fixture
def sample_messages():
    """Создает набор тестовых сообщений"""
    messages = []
    for i in range(1, 251):  # 250 сообщений для тестирования батчинга
        messages.append(Message(
            id=0,  # Будет автоматически назначен БД
            channel="test_channel",
            message_id=i,
            text=f"Test message {i}",
            date=datetime(2024, 1, 1, 12, 0, i % 60),
            author=f"Author {i % 10}",
            views=i * 10,
            forwards=i,
            replies=i % 5,
            comments="",
            media_type="",
            media_url=""
        ))
    return messages


class TestBatchInsert:
    """Тесты для batch_insert_messages"""
    
    def test_batch_insert_empty_list(self, database):
        """Тест вставки пустого списка"""
        result = database.batch_insert_messages([])
        assert result == 0
    
    def test_batch_insert_single_message(self, database, sample_messages):
        """Тест вставки одного сообщения"""
        result = database.batch_insert_messages([sample_messages[0]])
        assert result == 1
        
        # Проверяем, что сообщение действительно вставлено
        messages = database.get_messages(channel="test_channel")
        assert len(messages) == 1
        assert messages[0].message_id == 1
    
    def test_batch_insert_default_batch_size(self, database, sample_messages):
        """Тест вставки с размером батча по умолчанию (100)"""
        result = database.batch_insert_messages(sample_messages)
        assert result == 250
        
        # Проверяем количество вставленных сообщений
        messages = database.get_messages(channel="test_channel", limit=300)
        assert len(messages) == 250
    
    def test_batch_insert_custom_batch_size(self, database, sample_messages):
        """Тест вставки с кастомным размером батча"""
        result = database.batch_insert_messages(sample_messages, batch_size=50)
        assert result == 250
        
        messages = database.get_messages(channel="test_channel", limit=300)
        assert len(messages) == 250
    
    def test_batch_insert_small_batch_size(self, database, sample_messages):
        """Тест вставки с маленьким размером батча (10)"""
        result = database.batch_insert_messages(sample_messages[:100], batch_size=10)
        assert result == 100
        
        messages = database.get_messages(channel="test_channel", limit=150)
        assert len(messages) == 100
    
    def test_batch_insert_replace_duplicates(self, database, sample_messages):
        """Тест замены дубликатов при повторной вставке"""
        # Первая вставка
        result1 = database.batch_insert_messages(sample_messages[:10])
        assert result1 == 10
        
        # Изменяем текст сообщений
        for msg in sample_messages[:10]:
            msg.text = "Updated text"
        
        # Повторная вставка (должна заменить существующие)
        result2 = database.batch_insert_messages(sample_messages[:10])
        assert result2 == 10
        
        # Проверяем, что текст обновился
        messages = database.get_messages(channel="test_channel", limit=20)
        assert len(messages) == 10
        assert all(msg.text == "Updated text" for msg in messages)
    
    def test_batch_insert_data_integrity(self, database, sample_messages):
        """Тест целостности данных после батчинга"""
        database.batch_insert_messages(sample_messages)
        
        # Проверяем несколько случайных сообщений
        messages = database.get_messages(channel="test_channel", limit=300)
        
        # Проверяем первое сообщение
        first_msg = next(msg for msg in messages if msg.message_id == 1)
        assert first_msg.text == "Test message 1"
        assert first_msg.author == "Author 1"
        assert first_msg.views == 10
        
        # Проверяем последнее сообщение
        last_msg = next(msg for msg in messages if msg.message_id == 250)
        assert last_msg.text == "Test message 250"
        assert last_msg.author == "Author 0"
        assert last_msg.views == 2500


class TestTransactionManagement:
    """Тесты для управления транзакциями"""
    
    def test_begin_transaction(self, database):
        """Тест начала транзакции"""
        database.begin_transaction()
        assert database.transaction_active is True
        assert database.conn is not None
        database.rollback_transaction()
    
    def test_commit_transaction(self, database, sample_messages):
        """Тест коммита транзакции"""
        database.begin_transaction()
        
        # Вставляем данные в рамках транзакции
        database.batch_insert_messages(sample_messages[:10])
        
        database.commit_transaction()
        assert database.transaction_active is False
        assert database.conn is None
        
        # Проверяем, что данные сохранились
        messages = database.get_messages(channel="test_channel")
        assert len(messages) == 10
    
    def test_rollback_transaction(self, database, sample_messages):
        """Тест отката транзакции"""
        database.begin_transaction()
        
        # Вставляем данные в рамках транзакции
        database.batch_insert_messages(sample_messages[:10])
        
        database.rollback_transaction()
        assert database.transaction_active is False
        assert database.conn is None
        
        # Проверяем, что данные НЕ сохранились
        messages = database.get_messages(channel="test_channel")
        assert len(messages) == 0
    
    def test_nested_transaction_error(self, database):
        """Тест ошибки при попытке начать вложенную транзакцию"""
        database.begin_transaction()
        
        with pytest.raises(RuntimeError, match="Transaction already active"):
            database.begin_transaction()
        
        database.rollback_transaction()
    
    def test_commit_without_transaction_error(self, database):
        """Тест ошибки при попытке коммита без активной транзакции"""
        with pytest.raises(RuntimeError, match="No active transaction to commit"):
            database.commit_transaction()
    
    def test_rollback_without_transaction_error(self, database):
        """Тест ошибки при попытке отката без активной транзакции"""
        with pytest.raises(RuntimeError, match="No active transaction to rollback"):
            database.rollback_transaction()
    
    def test_transaction_with_multiple_batches(self, database, sample_messages):
        """Тест транзакции с несколькими батчами"""
        database.begin_transaction()
        
        # Вставляем несколько батчей в одной транзакции
        database.batch_insert_messages(sample_messages[:100], batch_size=50)
        database.batch_insert_messages(sample_messages[100:200], batch_size=50)
        
        database.commit_transaction()
        
        # Проверяем, что все данные сохранились
        messages = database.get_messages(channel="test_channel", limit=250)
        assert len(messages) == 200


class TestBatchInsertWithErrors:
    """Тесты для обработки ошибок при батчинге"""
    
    def test_batch_insert_with_invalid_data(self, database):
        """Тест обработки невалидных данных"""
        invalid_messages = [
            Message(
                id=0,
                channel="test_channel",
                message_id=1,
                text="Valid message",
                date=datetime(2024, 1, 1),
                author="Author",
                views=10,
                forwards=1,
                replies=0
            ),
            # Сообщение с невалидной датой будет обработано SQLite
            Message(
                id=0,
                channel="test_channel",
                message_id=2,
                text="Message with None date",
                date=None,  # Невалидная дата
                author="Author",
                views=10,
                forwards=1,
                replies=0
            )
        ]
        
        # Ожидаем исключение при вставке невалидных данных
        with pytest.raises(Exception):
            database.batch_insert_messages(invalid_messages)
    
    def test_batch_insert_rollback_on_error(self, database, sample_messages):
        """Тест отката при ошибке в середине батчинга"""
        # Создаем список с валидными и невалидными сообщениями
        messages = sample_messages[:5].copy()
        
        # Добавляем невалидное сообщение
        messages.append(Message(
            id=0,
            channel="test_channel",
            message_id=6,
            text="Invalid",
            date=None,  # Невалидная дата
            author="Author",
            views=10,
            forwards=1,
            replies=0
        ))
        
        # Пытаемся вставить - должна произойти ошибка и откат
        with pytest.raises(Exception):
            database.batch_insert_messages(messages)
        
        # Проверяем, что транзакция не активна после ошибки
        assert database.transaction_active is False
        
        # Проверяем, что данные НЕ сохранились (откат произошел)
        saved_messages = database.get_messages(channel="test_channel")
        assert len(saved_messages) == 0


class TestBatchInsertPerformance:
    """Тесты производительности батчинга"""
    
    def test_batch_vs_individual_insert(self, database, sample_messages):
        """Сравнение производительности батчинга vs индивидуальных вставок"""
        import time
        
        # Тест индивидуальных вставок
        start_individual = time.time()
        for msg in sample_messages[:50]:
            database.add_message(msg)
        time_individual = time.time() - start_individual
        
        # Очищаем БД
        with sqlite3.connect(database.db_path) as conn:
            conn.execute('DELETE FROM messages')
        
        # Тест батчинга
        start_batch = time.time()
        database.batch_insert_messages(sample_messages[:50])
        time_batch = time.time() - start_batch
        
        # Батчинг должен быть быстрее
        assert time_batch < time_individual
        print(f"\nИндивидуальные вставки: {time_individual:.4f}s")
        print(f"Батчинг: {time_batch:.4f}s")
        print(f"Ускорение: {time_individual/time_batch:.2f}x")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
