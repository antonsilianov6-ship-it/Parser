# -*- coding: utf-8 -*-
"""
Система уведомлений
"""
import requests
import json
from datetime import datetime
from typing import Dict, Optional
from enum import Enum

class NotificationType(Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    SUCCESS = "success"

class NotificationManager:
    def __init__(self):
        self.webhook_urls = {}
        self.email_config = {}
    
    def add_webhook(self, name: str, url: str, webhook_type: str = "slack"):
        """Добавляет webhook для уведомлений"""
        self.webhook_urls[name] = {
            'url': url,
            'type': webhook_type
        }
    
    def send_webhook_notification(self, webhook_name: str, message: str, 
                                notification_type: NotificationType = NotificationType.INFO):
        """Отправляет уведомление через webhook"""
        if webhook_name not in self.webhook_urls:
            print(f"Webhook '{webhook_name}' не найден")
            return False
        
        webhook = self.webhook_urls[webhook_name]
        
        try:
            if webhook['type'] == 'slack':
                payload = {
                    "text": f"AllInclusiveParser: {message}",
                    "username": "AllInclusiveParser",
                    "icon_emoji": self._get_emoji(notification_type)
                }
            elif webhook['type'] == 'discord':
                payload = {
                    "content": f"**AllInclusiveParser** {self._get_emoji(notification_type)}\n{message}",
                    "username": "AllInclusiveParser"
                }
            else:
                payload = {"message": message, "type": notification_type.value}
            
            response = requests.post(webhook['url'], json=payload, timeout=10)
            return response.status_code == 200
            
        except Exception as e:
            print(f"Ошибка отправки webhook уведомления: {e}")
            return False
    
    def _get_emoji(self, notification_type: NotificationType) -> str:
        """Возвращает эмодзи для типа уведомления"""
        emoji_map = {
            NotificationType.INFO: ":information_source:",
            NotificationType.WARNING: ":warning:",
            NotificationType.ERROR: ":x:",
            NotificationType.SUCCESS: ":white_check_mark:"
        }
        return emoji_map.get(notification_type, ":speech_balloon:")
    
    def notify_parse_complete(self, channel: str, messages_count: int):
        """Уведомление о завершении парсинга"""
        message = f"Парсинг канала '{channel}' завершен. Получено сообщений: {messages_count}"
        for webhook_name in self.webhook_urls:
            self.send_webhook_notification(webhook_name, message, NotificationType.SUCCESS)
    
    def notify_error(self, error_message: str, channel: str = None):
        """Уведомление об ошибке"""
        message = f"Ошибка при парсинге"
        if channel:
            message += f" канала '{channel}'"
        message += f": {error_message}"
        
        for webhook_name in self.webhook_urls:
            self.send_webhook_notification(webhook_name, message, NotificationType.ERROR)
    
    def notify_daily_report(self, stats: Dict):
        """Ежедневный отчет"""
        message = f"""Ежедневный отчет AllInclusiveParser:
📊 Всего сообщений: {stats.get('total_messages', 0)}
📺 Каналов: {stats.get('total_channels', 0)}
👀 Всего просмотров: {stats.get('total_views', 0)}
🔄 Всего пересылок: {stats.get('total_forwards', 0)}"""
        
        for webhook_name in self.webhook_urls:
            self.send_webhook_notification(webhook_name, message, NotificationType.INFO)

# Глобальный менеджер уведомлений
notification_manager = NotificationManager()