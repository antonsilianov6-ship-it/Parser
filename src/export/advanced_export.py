# -*- coding: utf-8 -*-
"""
Расширенный экспорт данных в различные форматы
"""
import json
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import List, Dict, Optional
import pandas as pd
from src.database.models import Message

class AdvancedExporter:
    def __init__(self, export_dir: str):
        self.export_dir = export_dir
    
    def export_to_json(self, messages: List[Message], filename: str = None) -> str:
        """Экспорт в JSON"""
        if not filename:
            filename = f"export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        filepath = f"{self.export_dir}/{filename}"
        data = []
        
        for msg in messages:
            data.append({
                'channel': msg.channel,
                'message_id': msg.message_id,
                'text': msg.text,
                'date': msg.date.isoformat(),
                'author': msg.author,
                'views': msg.views,
                'forwards': msg.forwards,
                'replies': msg.replies,
                'comments': msg.comments,
                'media_type': msg.media_type,
                'media_url': msg.media_url
            })
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        return filepath
    
    def export_to_xml(self, messages: List[Message], filename: str = None) -> str:
        """Экспорт в XML"""
        if not filename:
            filename = f"export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xml"
        
        filepath = f"{self.export_dir}/{filename}"
        root = ET.Element("messages")
        
        for msg in messages:
            msg_elem = ET.SubElement(root, "message")
            ET.SubElement(msg_elem, "channel").text = msg.channel
            ET.SubElement(msg_elem, "message_id").text = str(msg.message_id)
            ET.SubElement(msg_elem, "text").text = msg.text or ""
            ET.SubElement(msg_elem, "date").text = msg.date.isoformat()
            ET.SubElement(msg_elem, "author").text = msg.author or ""
            ET.SubElement(msg_elem, "views").text = str(msg.views)
            ET.SubElement(msg_elem, "forwards").text = str(msg.forwards)
            ET.SubElement(msg_elem, "replies").text = str(msg.replies)
        
        tree = ET.ElementTree(root)
        tree.write(filepath, encoding='utf-8', xml_declaration=True)
        
        return filepath
    
    def export_filtered(self, messages: List[Message], filters: Dict, format: str = 'csv') -> str:
        """Экспорт с фильтрами"""
        filtered_messages = []
        
        for msg in messages:
            include = True
            
            # Фильтр по ключевым словам
            if 'keywords' in filters and filters['keywords']:
                keywords = [kw.lower().strip() for kw in filters['keywords'].split(',')]
                if not any(kw in msg.text.lower() for kw in keywords if msg.text):
                    include = False
            
            # Фильтр по каналу
            if 'channel' in filters and filters['channel']:
                if msg.channel != filters['channel']:
                    include = False
            
            # Фильтр по дате
            if 'date_from' in filters and filters['date_from']:
                if msg.date < filters['date_from']:
                    include = False
            
            if 'date_to' in filters and filters['date_to']:
                if msg.date > filters['date_to']:
                    include = False
            
            # Фильтр по минимальным просмотрам
            if 'min_views' in filters and filters['min_views']:
                if msg.views < filters['min_views']:
                    include = False
            
            if include:
                filtered_messages.append(msg)
        
        # Экспорт в выбранном формате
        if format == 'json':
            return self.export_to_json(filtered_messages)
        elif format == 'xml':
            return self.export_to_xml(filtered_messages)
        else:  # csv по умолчанию
            return self.export_to_csv(filtered_messages)
    
    def export_to_csv(self, messages: List[Message], filename: str = None) -> str:
        """Экспорт в CSV"""
        if not filename:
            filename = f"export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        
        filepath = f"{self.export_dir}/{filename}"
        data = []
        
        for msg in messages:
            data.append({
                'Канал': msg.channel,
                'ID сообщения': msg.message_id,
                'Текст': msg.text,
                'Дата': msg.date.strftime('%Y-%m-%d %H:%M:%S'),
                'Автор': msg.author,
                'Просмотры': msg.views,
                'Пересылки': msg.forwards,
                'Ответы': msg.replies,
                'Комментарии': msg.comments,
                'Тип медиа': msg.media_type,
                'URL медиа': msg.media_url
            })
        
        df = pd.DataFrame(data)
        df.to_csv(filepath, index=False, encoding='utf-8')
        
        return filepath
    
    def generate_report(self, messages: List[Message]) -> Dict:
        """Генерирует отчет по сообщениям"""
        if not messages:
            return {'error': 'Нет данных для отчета'}
        
        df = pd.DataFrame([{
            'channel': msg.channel,
            'date': msg.date,
            'views': msg.views,
            'forwards': msg.forwards,
            'replies': msg.replies,
            'text_length': len(msg.text) if msg.text else 0
        } for msg in messages])
        
        report = {
            'total_messages': len(messages),
            'channels_count': df['channel'].nunique(),
            'date_range': {
                'from': df['date'].min().isoformat(),
                'to': df['date'].max().isoformat()
            },
            'stats': {
                'total_views': int(df['views'].sum()),
                'total_forwards': int(df['forwards'].sum()),
                'total_replies': int(df['replies'].sum()),
                'avg_views': float(df['views'].mean()),
                'avg_text_length': float(df['text_length'].mean())
            },
            'top_channels': df.groupby('channel').size().sort_values(ascending=False).head(10).to_dict(),
            'daily_stats': df.groupby(df['date'].dt.date).size().to_dict()
        }
        
        return report