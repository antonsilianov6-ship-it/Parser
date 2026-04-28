# -*- coding: utf-8 -*-
"""
Модели базы данных
"""
import sqlite3
import json
from datetime import datetime
from typing import List, Dict, Optional
from dataclasses import dataclass

@dataclass
class Message:
    id: int
    channel: str
    message_id: int
    text: str
    date: datetime
    author: str
    views: int
    forwards: int
    replies: int
    comments: str = ""
    media_type: str = ""
    media_url: str = ""
    source_type: str = "channel"  # 'channel', 'chat', 'forum_chat'
    topic_id: Optional[int] = None
    topic_title: Optional[str] = None

class Database:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn = None
        self.transaction_active = False
        self.init_db()
    
    def init_db(self):
        """Инициализация базы данных"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    channel TEXT NOT NULL,
                    message_id INTEGER NOT NULL,
                    text TEXT,
                    date TIMESTAMP NOT NULL,
                    author TEXT,
                    views INTEGER DEFAULT 0,
                    forwards INTEGER DEFAULT 0,
                    replies INTEGER DEFAULT 0,
                    comments TEXT DEFAULT '',
                    media_type TEXT DEFAULT '',
                    media_url TEXT DEFAULT '',
                    source_type TEXT DEFAULT 'channel',
                    topic_id INTEGER DEFAULT NULL,
                    topic_title TEXT DEFAULT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(channel, message_id)
                )
            ''')
            
            conn.execute('''
                CREATE TABLE IF NOT EXISTS channels (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    url TEXT,
                    category TEXT DEFAULT '',
                    priority INTEGER DEFAULT 1,
                    last_parsed TIMESTAMP,
                    is_active BOOLEAN DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            conn.execute('''
                CREATE TABLE IF NOT EXISTS parse_stats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    channel TEXT NOT NULL,
                    messages_count INTEGER DEFAULT 0,
                    errors_count INTEGER DEFAULT 0,
                    parse_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Миграция существующих данных (добавляет колонки если их нет)
            self._migrate_existing_data(conn)
            
            # Существующие индексы
            conn.execute('CREATE INDEX IF NOT EXISTS idx_messages_channel ON messages(channel)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_messages_date ON messages(date)')
            
            # Новые индексы для source_type и topic_id (создаются после миграции)
            conn.execute('CREATE INDEX IF NOT EXISTS idx_messages_source_type ON messages(source_type)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_messages_topic_id ON messages(topic_id)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_messages_source_topic ON messages(source_type, topic_id)')
    
    def add_message(self, message: Message) -> bool:
        """Добавляет сообщение в базу"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute('''
                    INSERT OR REPLACE INTO messages 
                    (channel, message_id, text, date, author, views, forwards, replies, comments, media_type, media_url, source_type, topic_id, topic_title)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (message.channel, message.message_id, message.text, message.date, 
                     message.author, message.views, message.forwards, message.replies,
                     message.comments, message.media_type, message.media_url,
                     message.source_type, message.topic_id, message.topic_title))
                return True
        except Exception as e:
            print(f"Ошибка добавления сообщения: {e}")
            return False
    
    def get_messages(self, channel: str = None, limit: int = 1000, offset: int = 0) -> List[Message]:
        """Получает сообщения из базы"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            if channel:
                cursor = conn.execute('''
                    SELECT * FROM messages WHERE channel = ? 
                    ORDER BY date DESC LIMIT ? OFFSET ?
                ''', (channel, limit, offset))
            else:
                cursor = conn.execute('''
                    SELECT * FROM messages ORDER BY date DESC LIMIT ? OFFSET ?
                ''', (limit, offset))
            
            messages = []
            for row in cursor.fetchall():
                # Проверяем наличие новых полей для обратной совместимости
                source_type = row['source_type'] if 'source_type' in row.keys() else 'channel'
                topic_id = row['topic_id'] if 'topic_id' in row.keys() else None
                topic_title = row['topic_title'] if 'topic_title' in row.keys() else None
                
                messages.append(Message(
                    id=row['id'],
                    channel=row['channel'],
                    message_id=row['message_id'],
                    text=row['text'],
                    date=datetime.fromisoformat(row['date']),
                    author=row['author'],
                    views=row['views'],
                    forwards=row['forwards'],
                    replies=row['replies'],
                    comments=row['comments'],
                    media_type=row['media_type'],
                    media_url=row['media_url'],
                    source_type=source_type,
                    topic_id=topic_id,
                    topic_title=topic_title
                ))
            return messages
    
    def add_channel(self, name: str, url: str = "", category: str = "", priority: int = 1):
        """Добавляет канал"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                INSERT OR REPLACE INTO channels (name, url, category, priority)
                VALUES (?, ?, ?, ?)
            ''', (name, url, category, priority))
    
    def get_channels(self) -> List[Dict]:
        """Получает список каналов"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute('SELECT * FROM channels WHERE is_active = 1')
            return [dict(row) for row in cursor.fetchall()]
    
    def add_parse_stats(self, channel: str, messages_count: int, errors_count: int = 0):
        """Добавляет статистику парсинга"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                INSERT INTO parse_stats (channel, messages_count, errors_count)
                VALUES (?, ?, ?)
            ''', (channel, messages_count, errors_count))
    
    def get_stats(self) -> Dict:
        """Получает общую статистику"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            
            # Общее количество сообщений
            total_messages = conn.execute('SELECT COUNT(*) as count FROM messages').fetchone()['count']
            
            # Количество каналов
            total_channels = conn.execute('SELECT COUNT(*) as count FROM channels WHERE is_active = 1').fetchone()['count']
            
            # Статистика по каналам
            channel_stats = conn.execute('''
                SELECT channel, COUNT(*) as messages_count, MAX(date) as last_message
                FROM messages GROUP BY channel ORDER BY messages_count DESC
            ''').fetchall()
            
            return {
                'total_messages': total_messages,
                'total_channels': total_channels,
                'channel_stats': [dict(row) for row in channel_stats]
            }
    
    def get_stats_by_source_type(self) -> Dict:
        """
        Получает статистику по типам источников
        
        Returns:
            Словарь со статистикой:
            {
                'by_source_type': {
                    'channel': count,
                    'chat': count,
                    'forum_chat': count
                },
                'forum_topics': [
                    {'topic_id': id, 'topic_title': title, 'messages_count': count},
                    ...
                ]
            }
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            
            # Статистика по типам источников
            source_type_stats = conn.execute('''
                SELECT source_type, COUNT(*) as count
                FROM messages
                GROUP BY source_type
            ''').fetchall()
            
            # Преобразуем в словарь
            by_source_type = {}
            for row in source_type_stats:
                source_type = row['source_type'] if row['source_type'] else 'channel'
                by_source_type[source_type] = row['count']
            
            # Статистика по топикам в форум-чатах
            forum_topics = conn.execute('''
                SELECT topic_id, topic_title, COUNT(*) as messages_count
                FROM messages
                WHERE source_type = 'forum_chat' AND topic_id IS NOT NULL
                GROUP BY topic_id, topic_title
                ORDER BY messages_count DESC
            ''').fetchall()
            
            return {
                'by_source_type': by_source_type,
                'forum_topics': [dict(row) for row in forum_topics]
            }
    
    def get_messages_by_topic(self, topic_id: int, limit: int = 1000) -> List[Message]:
        """
        Получает сообщения из конкретного топика
        
        Args:
            topic_id: ID топика
            limit: Максимальное количество сообщений
            
        Returns:
            Список сообщений из топика
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute('''
                SELECT * FROM messages 
                WHERE topic_id = ? 
                ORDER BY date DESC 
                LIMIT ?
            ''', (topic_id, limit))
            
            messages = []
            for row in cursor.fetchall():
                messages.append(Message(
                    id=row['id'],
                    channel=row['channel'],
                    message_id=row['message_id'],
                    text=row['text'],
                    date=datetime.fromisoformat(row['date']),
                    author=row['author'],
                    views=row['views'],
                    forwards=row['forwards'],
                    replies=row['replies'],
                    comments=row['comments'],
                    media_type=row['media_type'],
                    media_url=row['media_url'],
                    source_type=row['source_type'],
                    topic_id=row['topic_id'],
                    topic_title=row['topic_title']
                ))
            return messages
    
    def begin_transaction(self):
        """Начинает транзакцию"""
        if self.transaction_active:
            raise RuntimeError("Transaction already active")
        
        self.conn = sqlite3.connect(self.db_path)
        self.conn.execute('BEGIN TRANSACTION')
        self.transaction_active = True
    
    def _migrate_existing_data(self, conn):
        """
        Внутренний метод миграции существующих данных.
        Добавляет новые колонки если их нет и устанавливает source_type='channel' для существующих записей.
        
        Args:
            conn: Активное соединение с базой данных
        """
        try:
            # Проверяем существование колонок
            cursor = conn.execute("PRAGMA table_info(messages)")
            columns = [row[1] for row in cursor.fetchall()]
            
            # Добавляем колонки если их нет
            if 'source_type' not in columns:
                conn.execute("ALTER TABLE messages ADD COLUMN source_type TEXT DEFAULT 'channel'")
            
            if 'topic_id' not in columns:
                conn.execute('ALTER TABLE messages ADD COLUMN topic_id INTEGER DEFAULT NULL')
            
            if 'topic_title' not in columns:
                conn.execute('ALTER TABLE messages ADD COLUMN topic_title TEXT DEFAULT NULL')
            
            # Устанавливаем source_type='channel' для всех существующих записей где source_type IS NULL
            # Это нужно делать всегда, не только при добавлении колонки
            conn.execute("UPDATE messages SET source_type = 'channel' WHERE source_type IS NULL")
            
            conn.commit()
            
        except Exception as e:
            print(f"Ошибка при миграции данных: {e}")
            raise
    
    def migrate_existing_data(self):
        """
        Публичный метод для миграции существующих данных.
        Устанавливает source_type='channel' для всех существующих записей где source_type равен NULL.
        """
        with sqlite3.connect(self.db_path) as conn:
            self._migrate_existing_data(conn)
    
    def commit_transaction(self):
        """Коммитит транзакцию"""
        if not self.transaction_active:
            raise RuntimeError("No active transaction to commit")
        
        try:
            self.conn.commit()
        finally:
            self.conn.close()
            self.conn = None
            self.transaction_active = False
    
    def rollback_transaction(self):
        """Откатывает транзакцию"""
        if not self.transaction_active:
            raise RuntimeError("No active transaction to rollback")
        
        try:
            self.conn.rollback()
        finally:
            self.conn.close()
            self.conn = None
            self.transaction_active = False
    
    def batch_insert_messages(self, messages: List[Message], batch_size: int = 100) -> int:
        """
        Пакетная вставка сообщений в базу данных
        
        Args:
            messages: Список сообщений для вставки
            batch_size: Размер батча (по умолчанию 100)
        
        Returns:
            Количество успешно вставленных сообщений
        """
        if not messages:
            return 0
        
        inserted_count = 0
        total_messages = len(messages)
        
        # Используем внешнюю транзакцию если она активна, иначе создаем свою
        use_external_transaction = self.transaction_active
        
        try:
            if not use_external_transaction:
                self.begin_transaction()
            
            conn = self.conn if self.transaction_active else sqlite3.connect(self.db_path)
            
            # Обрабатываем сообщения батчами
            for i in range(0, total_messages, batch_size):
                batch = messages[i:i + batch_size]
                
                # Подготавливаем данные для executemany
                batch_data = [
                    (msg.channel, msg.message_id, msg.text, msg.date,
                     msg.author, msg.views, msg.forwards, msg.replies,
                     msg.comments, msg.media_type, msg.media_url,
                     msg.source_type, msg.topic_id, msg.topic_title)
                    for msg in batch
                ]
                
                try:
                    conn.executemany('''
                        INSERT OR REPLACE INTO messages 
                        (channel, message_id, text, date, author, views, forwards, replies, comments, media_type, media_url, source_type, topic_id, topic_title)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', batch_data)
                    
                    inserted_count += len(batch)
                    
                except Exception as e:
                    print(f"Ошибка при вставке батча {i//batch_size + 1}: {e}")
                    if not use_external_transaction:
                        self.rollback_transaction()
                    raise
            
            if not use_external_transaction:
                self.commit_transaction()
            
            return inserted_count
            
        except Exception as e:
            if not use_external_transaction and self.transaction_active:
                self.rollback_transaction()
            print(f"Ошибка при пакетной вставке сообщений: {e}")
            raise