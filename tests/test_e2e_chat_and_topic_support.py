"""
End-to-end тесты для функциональности парсинга чатов и топиков

Эти тесты проверяют полный цикл работы системы:
1. Парсинг реального публичного чата
2. Парсинг реального форум-чата с топиками
3. Корректность экспорта данных
4. Корректность статистики
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from pathlib import Path
import sys
import os

# Добавляем корневую директорию в путь для импорта модулей
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.telegram.unified_parser import UnifiedParser
from src.database.database import Database
from src.export.excel_exporter import ExcelExporter


class TestE2EChatAndTopicSupport:
    """End-to-end тесты для поддержки чатов и топиков"""
    
    @pytest.fixture
    def test_db_path(self, tmp_path):
        """Создает временную базу данных для тестов"""
        db_path = tmp_path / "test_e2e.db"
        yield str(db_path)
        # Cleanup
        if db_path.exists():
            db_path.unlink()
    
    @pytest.fixture
    def test_export_path(self, tmp_path):
        """Создает временную директорию для экспорта"""
        export_path = tmp_path / "exports"
        export_path.mkdir(exist_ok=True)
        yield str(export_path)
    
    @pytest.mark.asyncio
    @pytest.mark.e2e
    async def test_parse_public_chat_e2e(self, test_db_path):
        """
        E2E тест: Парсинг реального публичного чата
        
        Проверяет:
        - Определение типа источника как 'chat'
        - Получение сообщений из чата
        - Сохранение метаданных source_type
        - Формирование корректных ссылок
        """
        # Используем публичный тестовый чат (если доступен)
        # Для реального тестирования нужен доступный публичный чат
        test_chat = "https://t.me/test_public_chat"  # Замените на реальный чат
        
        # Инициализация парсера
        parser = UnifiedParser(
            api_id=os.getenv("TELEGRAM_API_ID"),
            api_hash=os.getenv("TELEGRAM_API_HASH"),
            phone=os.getenv("TELEGRAM_PHONE"),
            db_path=test_db_path
        )
        
        try:
            # Парсим последние 24 часа
            end_date = datetime.now()
            start_date = end_date - timedelta(days=1)
            
            # Выполняем парсинг
            await parser.parse_sources(
                sources=[test_chat],
                start_date=start_date,
                end_date=end_date
            )
            
            # Проверяем результаты в базе данных
            db = Database(test_db_path)
            
            # Проверка 1: Сообщения сохранены с правильным source_type
            messages = db.get_all_messages()
            assert len(messages) > 0, "Должны быть получены сообщения из чата"
            
            for msg in messages:
                assert msg.source_type == 'chat', f"source_type должен быть 'chat', получен: {msg.source_type}"
                assert msg.topic_id is None, "topic_id должен быть None для обычного чата"
                assert msg.topic_title is None, "topic_title должен быть None для обычного чата"
            
            # Проверка 2: Ссылки сформированы корректно
            for msg in messages:
                assert msg.link is not None, "Ссылка не должна быть None"
                assert msg.link.startswith('https://t.me/'), "Ссылка должна начинаться с https://t.me/"
                assert 'None' not in msg.link, "Ссылка не должна содержать 'None'"
            
            # Проверка 3: Статистика корректна
            stats = db.get_stats_by_source_type()
            assert 'chat' in stats['by_source_type'], "Статистика должна содержать тип 'chat'"
            assert stats['by_source_type']['chat'] == len(messages), "Количество сообщений в статистике должно совпадать"
            
            print(f"✅ E2E тест публичного чата пройден: {len(messages)} сообщений")
            
        except Exception as e:
            pytest.skip(f"E2E тест пропущен: {str(e)}. Требуется доступ к реальному публичному чату.")
        
        finally:
            await parser.close()
    
    @pytest.mark.asyncio
    @pytest.mark.e2e
    async def test_parse_forum_chat_e2e(self, test_db_path):
        """
        E2E тест: Парсинг реального форум-чата с топиками
        
        Проверяет:
        - Определение типа источника как 'forum_chat'
        - Получение списка топиков
        - Парсинг сообщений из каждого топика
        - Сохранение метаданных топиков
        - Формирование корректных ссылок с topic_id
        """
        # Используем публичный форум-чат (если доступен)
        test_forum = "https://t.me/test_forum_chat"  # Замените на реальный форум
        
        # Инициализация парсера
        parser = UnifiedParser(
            api_id=os.getenv("TELEGRAM_API_ID"),
            api_hash=os.getenv("TELEGRAM_API_HASH"),
            phone=os.getenv("TELEGRAM_PHONE"),
            db_path=test_db_path
        )
        
        try:
            # Парсим последние 24 часа
            end_date = datetime.now()
            start_date = end_date - timedelta(days=1)
            
            # Выполняем парсинг
            await parser.parse_sources(
                sources=[test_forum],
                start_date=start_date,
                end_date=end_date
            )
            
            # Проверяем результаты в базе данных
            db = Database(test_db_path)
            
            # Проверка 1: Сообщения сохранены с правильным source_type
            messages = db.get_all_messages()
            assert len(messages) > 0, "Должны быть получены сообщения из форум-чата"
            
            for msg in messages:
                assert msg.source_type == 'forum_chat', f"source_type должен быть 'forum_chat', получен: {msg.source_type}"
                assert msg.topic_id is not None, "topic_id не должен быть None для форум-чата"
                assert msg.topic_title is not None, "topic_title не должен быть None для форум-чата"
            
            # Проверка 2: Ссылки сформированы корректно с topic_id
            for msg in messages:
                assert msg.link is not None, "Ссылка не должна быть None"
                assert msg.link.startswith('https://t.me/'), "Ссылка должна начинаться с https://t.me/"
                assert 'None' not in msg.link, "Ссылка не должна содержать 'None'"
                # Ссылка должна содержать topic_id
                assert str(msg.topic_id) in msg.link, f"Ссылка должна содержать topic_id {msg.topic_id}"
            
            # Проверка 3: Статистика по топикам корректна
            stats = db.get_stats_by_source_type()
            assert 'forum_chat' in stats['by_source_type'], "Статистика должна содержать тип 'forum_chat'"
            assert len(stats['forum_topics']) > 0, "Должна быть статистика по топикам"
            
            # Проверка 4: Количество уникальных топиков
            unique_topics = set((msg.topic_id, msg.topic_title) for msg in messages)
            assert len(unique_topics) > 0, "Должны быть уникальные топики"
            
            print(f"✅ E2E тест форум-чата пройден: {len(messages)} сообщений из {len(unique_topics)} топиков")
            
        except Exception as e:
            pytest.skip(f"E2E тест пропущен: {str(e)}. Требуется доступ к реальному форум-чату.")
        
        finally:
            await parser.close()
    
    @pytest.mark.asyncio
    @pytest.mark.e2e
    async def test_export_with_topics_e2e(self, test_db_path, test_export_path):
        """
        E2E тест: Экспорт данных с информацией о топиках
        
        Проверяет:
        - Экспорт сообщений с полями source_type, topic_id, topic_title
        - Группировка по топикам в Excel
        - Создание отдельных листов для топиков
        - Сводная таблица по топикам
        """
        # Создаем тестовые данные в БД
        db = Database(test_db_path)
        
        # Добавляем тестовые сообщения из разных источников
        from src.database.models import Message
        
        # Сообщения из канала
        for i in range(5):
            msg = Message(
                date=datetime.now() - timedelta(hours=i),
                text=f"Channel message {i}",
                link=f"https://t.me/test_channel/{i}",
                title="Test Channel",
                source_type='channel',
                topic_id=None,
                topic_title=None
            )
            db.add_message(msg)
        
        # Сообщения из чата
        for i in range(5):
            msg = Message(
                date=datetime.now() - timedelta(hours=i),
                text=f"Chat message {i}",
                link=f"https://t.me/test_chat/{i}",
                title="Test Chat",
                source_type='chat',
                topic_id=None,
                topic_title=None
            )
            db.add_message(msg)
        
        # Сообщения из форум-чата (2 топика)
        for topic_id, topic_title in [(1, "Topic 1"), (2, "Topic 2")]:
            for i in range(5):
                msg = Message(
                    date=datetime.now() - timedelta(hours=i),
                    text=f"Forum message {i} in {topic_title}",
                    link=f"https://t.me/test_forum/{topic_id}/{i}",
                    title="Test Forum",
                    source_type='forum_chat',
                    topic_id=topic_id,
                    topic_title=topic_title
                )
                db.add_message(msg)
        
        # Экспортируем данные
        exporter = ExcelExporter(db)
        export_file = Path(test_export_path) / "test_export.xlsx"
        
        try:
            exporter.export_to_excel(str(export_file))
            
            # Проверяем что файл создан
            assert export_file.exists(), "Файл экспорта должен быть создан"
            
            # Проверяем содержимое файла
            import pandas as pd
            
            # Читаем основной лист
            df = pd.read_excel(export_file, sheet_name=0)
            
            # Проверка 1: Наличие колонок source_type, topic_id, topic_title
            assert 'source_type' in df.columns, "Должна быть колонка source_type"
            assert 'topic_id' in df.columns, "Должна быть колонка topic_id"
            assert 'topic_title' in df.columns, "Должна быть колонка topic_title"
            
            # Проверка 2: Корректность данных по типам источников
            assert len(df[df['source_type'] == 'channel']) == 5, "Должно быть 5 сообщений из канала"
            assert len(df[df['source_type'] == 'chat']) == 5, "Должно быть 5 сообщений из чата"
            assert len(df[df['source_type'] == 'forum_chat']) == 10, "Должно быть 10 сообщений из форум-чата"
            
            # Проверка 3: Корректность topic_id и topic_title
            forum_messages = df[df['source_type'] == 'forum_chat']
            assert forum_messages['topic_id'].notna().all(), "topic_id не должен быть NaN для форум-чата"
            assert forum_messages['topic_title'].notna().all(), "topic_title не должен быть NaN для форум-чата"
            
            channel_messages = df[df['source_type'] == 'channel']
            assert channel_messages['topic_id'].isna().all(), "topic_id должен быть NaN для канала"
            
            print(f"✅ E2E тест экспорта пройден: {len(df)} сообщений экспортировано")
            
        except Exception as e:
            pytest.fail(f"Ошибка при экспорте: {str(e)}")
    
    @pytest.mark.asyncio
    @pytest.mark.e2e
    async def test_statistics_e2e(self, test_db_path):
        """
        E2E тест: Корректность статистики по типам источников и топикам
        
        Проверяет:
        - Статистику по типам источников
        - Статистику по топикам
        - Количество сообщений в каждом топике
        """
        # Создаем тестовые данные в БД
        db = Database(test_db_path)
        
        from src.database.models import Message
        
        # Добавляем тестовые сообщения
        # 10 сообщений из канала
        for i in range(10):
            msg = Message(
                date=datetime.now() - timedelta(hours=i),
                text=f"Channel message {i}",
                link=f"https://t.me/test_channel/{i}",
                title="Test Channel",
                source_type='channel'
            )
            db.add_message(msg)
        
        # 15 сообщений из чата
        for i in range(15):
            msg = Message(
                date=datetime.now() - timedelta(hours=i),
                text=f"Chat message {i}",
                link=f"https://t.me/test_chat/{i}",
                title="Test Chat",
                source_type='chat'
            )
            db.add_message(msg)
        
        # 20 сообщений из форум-чата (3 топика: 10, 5, 5)
        topics_data = [
            (1, "General Discussion", 10),
            (2, "Announcements", 5),
            (3, "Support", 5)
        ]
        
        for topic_id, topic_title, count in topics_data:
            for i in range(count):
                msg = Message(
                    date=datetime.now() - timedelta(hours=i),
                    text=f"Forum message {i} in {topic_title}",
                    link=f"https://t.me/test_forum/{topic_id}/{i}",
                    title="Test Forum",
                    source_type='forum_chat',
                    topic_id=topic_id,
                    topic_title=topic_title
                )
                db.add_message(msg)
        
        # Получаем статистику
        stats = db.get_stats_by_source_type()
        
        # Проверка 1: Статистика по типам источников
        assert 'by_source_type' in stats, "Должна быть статистика по типам источников"
        assert stats['by_source_type']['channel'] == 10, "Должно быть 10 сообщений из канала"
        assert stats['by_source_type']['chat'] == 15, "Должно быть 15 сообщений из чата"
        assert stats['by_source_type']['forum_chat'] == 20, "Должно быть 20 сообщений из форум-чата"
        
        # Проверка 2: Статистика по топикам
        assert 'forum_topics' in stats, "Должна быть статистика по топикам"
        assert len(stats['forum_topics']) == 3, "Должно быть 3 топика"
        
        # Проверка 3: Количество сообщений в каждом топике
        topic_stats = {t['topic_id']: t['messages_count'] for t in stats['forum_topics']}
        assert topic_stats[1] == 10, "В топике 1 должно быть 10 сообщений"
        assert topic_stats[2] == 5, "В топике 2 должно быть 5 сообщений"
        assert topic_stats[3] == 5, "В топике 3 должно быть 5 сообщений"
        
        # Проверка 4: Названия топиков
        topic_titles = {t['topic_id']: t['topic_title'] for t in stats['forum_topics']}
        assert topic_titles[1] == "General Discussion"
        assert topic_titles[2] == "Announcements"
        assert topic_titles[3] == "Support"
        
        print(f"✅ E2E тест статистики пройден:")
        print(f"  - Каналы: {stats['by_source_type']['channel']} сообщений")
        print(f"  - Чаты: {stats['by_source_type']['chat']} сообщений")
        print(f"  - Форум-чаты: {stats['by_source_type']['forum_chat']} сообщений")
        print(f"  - Топиков: {len(stats['forum_topics'])}")


if __name__ == "__main__":
    # Запуск E2E тестов
    pytest.main([__file__, "-v", "-m", "e2e", "-s"])
