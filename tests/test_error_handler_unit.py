# -*- coding: utf-8 -*-
"""Unit-тесты для ErrorHandler"""

import pytest
from unittest.mock import Mock
from telethon.errors import (
    ChatAdminRequiredError,
    UserNotParticipantError,
    ChatWriteForbiddenError,
    ChannelPrivateError,
    UsernameNotOccupiedError
)
from src.utils.error_handler import ErrorHandler


# Вспомогательная функция для создания mock-ошибок Telethon
def create_telethon_error(error_class):
    """Создает mock-объект ошибки Telethon с необходимыми параметрами"""
    mock_request = Mock()
    try:
        return error_class(request=mock_request)
    except TypeError:
        # Если ошибка не требует request, создаем без параметров
        return error_class()


class TestErrorHandlerChatAccess:
    """Тесты для обработки ошибок доступа к чатам"""
    
    def test_handle_chat_admin_required_error(self):
        """
        Тест обработки ChatAdminRequiredError
        
        Requirements: 8.1, 8.2, 8.4, 8.5, 8.7, 13.7
        """
        error_handler = ErrorHandler()
        error = create_telethon_error(ChatAdminRequiredError)
        chat_link = "https://t.me/test_chat"
        
        # Обрабатываем ошибку
        error_handler.handle_chat_access_error(error, chat_link)
        
        # Проверяем что ошибка залогирована
        assert len(error_handler.errors) == 1
        assert error_handler.errors[0].error_type == 'ChatAdminRequiredError'
        assert error_handler.errors[0].context['chat_link'] == chat_link
        
        # Проверяем накопление статистики по типам
        assert 'ChatAdminRequiredError' in error_handler.chat_access_errors
        assert error_handler.chat_access_errors['ChatAdminRequiredError'] == 1
        
        # Проверяем накопление статистики по источникам
        assert chat_link in error_handler.errors_by_source
        assert 'ChatAdminRequiredError' in error_handler.errors_by_source[chat_link]
        
        # Проверяем что рекомендации включены в контекст
        assert 'recommendations' in error_handler.errors[0].context
        assert 'администратор' in error_handler.errors[0].context['recommendations'].lower()
    
    def test_handle_user_not_participant_error(self):
        """
        Тест обработки UserNotParticipantError
        
        Requirements: 8.2, 8.4, 8.5, 8.7, 13.7
        """
        error_handler = ErrorHandler()
        error = create_telethon_error(UserNotParticipantError)
        chat_link = "https://t.me/private_chat"
        
        # Обрабатываем ошибку
        error_handler.handle_chat_access_error(error, chat_link)
        
        # Проверяем что ошибка залогирована
        assert len(error_handler.errors) == 1
        assert error_handler.errors[0].error_type == 'UserNotParticipantError'
        
        # Проверяем статистику
        assert error_handler.chat_access_errors['UserNotParticipantError'] == 1
        assert chat_link in error_handler.errors_by_source
        
        # Проверяем рекомендации
        recommendations = error_handler.errors[0].context['recommendations']
        assert 'участник' in recommendations.lower() or 'присоедин' in recommendations.lower()
    
    def test_handle_chat_write_forbidden_error(self):
        """
        Тест обработки ChatWriteForbiddenError
        
        Requirements: 8.3, 8.4, 8.5, 8.7, 13.7
        """
        error_handler = ErrorHandler()
        error = create_telethon_error(ChatWriteForbiddenError)
        chat_link = "https://t.me/restricted_chat"
        
        # Обрабатываем ошибку
        error_handler.handle_chat_access_error(error, chat_link)
        
        # Проверяем что ошибка залогирована
        assert len(error_handler.errors) == 1
        assert error_handler.errors[0].error_type == 'ChatWriteForbiddenError'
        
        # Проверяем статистику
        assert error_handler.chat_access_errors['ChatWriteForbiddenError'] == 1
        
        # Проверяем рекомендации
        recommendations = error_handler.errors[0].context['recommendations']
        assert 'приватност' in recommendations.lower() or 'доступ' in recommendations.lower()
    
    def test_multiple_errors_same_chat(self):
        """
        Тест обработки нескольких ошибок для одного чата
        
        Requirements: 8.7, 13.7
        """
        error_handler = ErrorHandler()
        chat_link = "https://t.me/problematic_chat"
        
        # Обрабатываем несколько разных ошибок для одного чата
        error_handler.handle_chat_access_error(
            create_telethon_error(ChatAdminRequiredError), 
            chat_link
        )
        error_handler.handle_chat_access_error(
            create_telethon_error(UserNotParticipantError), 
            chat_link
        )
        error_handler.handle_chat_access_error(
            create_telethon_error(ChatAdminRequiredError), 
            chat_link
        )
        
        # Проверяем общее количество ошибок
        assert len(error_handler.errors) == 3
        
        # Проверяем статистику по типам
        assert error_handler.chat_access_errors['ChatAdminRequiredError'] == 2
        assert error_handler.chat_access_errors['UserNotParticipantError'] == 1
        
        # Проверяем статистику по источникам
        assert len(error_handler.errors_by_source[chat_link]) == 3
        assert error_handler.errors_by_source[chat_link].count('ChatAdminRequiredError') == 2
        assert error_handler.errors_by_source[chat_link].count('UserNotParticipantError') == 1
    
    def test_multiple_chats_with_errors(self):
        """
        Тест обработки ошибок для нескольких чатов
        
        Requirements: 8.7, 13.7
        """
        error_handler = ErrorHandler()
        
        chat1 = "https://t.me/chat1"
        chat2 = "https://t.me/chat2"
        chat3 = "https://t.me/chat3"
        
        # Обрабатываем ошибки для разных чатов
        error_handler.handle_chat_access_error(
            create_telethon_error(ChatAdminRequiredError), 
            chat1
        )
        error_handler.handle_chat_access_error(
            create_telethon_error(UserNotParticipantError), 
            chat2
        )
        error_handler.handle_chat_access_error(
            create_telethon_error(ChatWriteForbiddenError), 
            chat3
        )
        error_handler.handle_chat_access_error(
            create_telethon_error(ChatAdminRequiredError), 
            chat1
        )
        
        # Проверяем что все чаты учтены
        assert len(error_handler.errors_by_source) == 3
        assert chat1 in error_handler.errors_by_source
        assert chat2 in error_handler.errors_by_source
        assert chat3 in error_handler.errors_by_source
        
        # Проверяем количество ошибок по чатам
        assert len(error_handler.errors_by_source[chat1]) == 2
        assert len(error_handler.errors_by_source[chat2]) == 1
        assert len(error_handler.errors_by_source[chat3]) == 1
    
    def test_parsing_continues_after_error(self):
        """
        Тест продолжения парсинга после ошибки
        
        Requirements: 8.4, 8.6, 13.7
        
        Проверяет что обработка ошибки не прерывает выполнение программы
        и позволяет продолжить парсинг других источников.
        """
        error_handler = ErrorHandler()
        
        # Симулируем парсинг нескольких чатов с ошибками
        chats = [
            "https://t.me/chat1",
            "https://t.me/chat2",
            "https://t.me/chat3"
        ]
        
        errors_encountered = []
        
        for chat in chats:
            try:
                # Симулируем ошибку доступа
                if chat == "https://t.me/chat2":
                    error = create_telethon_error(UserNotParticipantError)
                    error_handler.handle_chat_access_error(error, chat)
                    errors_encountered.append(chat)
                    continue  # Пропускаем этот чат, продолжаем с другими
                
                # Симулируем успешный парсинг
                # (в реальности здесь был бы код парсинга)
                pass
            except Exception as e:
                # Не должно быть необработанных исключений
                pytest.fail(f"Unexpected exception: {e}")
        
        # Проверяем что парсинг продолжился для всех чатов
        assert len(errors_encountered) == 1
        assert "https://t.me/chat2" in errors_encountered
        
        # Проверяем что ошибка залогирована
        assert len(error_handler.errors) == 1
        assert error_handler.errors[0].context['chat_link'] == "https://t.me/chat2"


class TestErrorHandlerRecommendations:
    """Тесты для рекомендаций по ошибкам"""
    
    def test_recommendations_for_all_error_types(self):
        """
        Тест наличия рекомендаций для всех типов ошибок
        
        Requirements: 8.5, 13.7
        """
        error_handler = ErrorHandler()
        
        error_types = [
            'ChatAdminRequiredError',
            'UserNotParticipantError',
            'ChatWriteForbiddenError',
            'ChannelPrivateError',
            'UsernameNotOccupiedError'
        ]
        
        for error_type in error_types:
            recommendations = error_handler.get_access_error_recommendations(error_type)
            
            # Проверяем что рекомендации не пустые
            assert recommendations is not None
            assert len(recommendations) > 0
            assert 'Рекомендации:' in recommendations
    
    def test_default_recommendation_for_unknown_error(self):
        """
        Тест дефолтной рекомендации для неизвестного типа ошибки
        
        Requirements: 8.5, 13.7
        """
        error_handler = ErrorHandler()
        
        # Запрашиваем рекомендации для неизвестного типа ошибки
        recommendations = error_handler.get_access_error_recommendations('UnknownError')
        
        # Проверяем что возвращается дефолтная рекомендация
        assert recommendations is not None
        assert len(recommendations) > 0
        assert 'доступ' in recommendations.lower() or 'приватност' in recommendations.lower()
    
    def test_recommendations_specificity(self):
        """
        Тест специфичности рекомендаций для каждого типа ошибки
        
        Requirements: 8.5, 13.7
        """
        error_handler = ErrorHandler()
        
        # ChatAdminRequiredError
        rec1 = error_handler.get_access_error_recommendations('ChatAdminRequiredError')
        assert 'администратор' in rec1.lower()
        
        # UserNotParticipantError
        rec2 = error_handler.get_access_error_recommendations('UserNotParticipantError')
        assert 'участник' in rec2.lower() or 'присоедин' in rec2.lower()
        
        # ChatWriteForbiddenError
        rec3 = error_handler.get_access_error_recommendations('ChatWriteForbiddenError')
        assert 'приватност' in rec3.lower()
        
        # Проверяем что рекомендации разные
        assert rec1 != rec2
        assert rec2 != rec3
        assert rec1 != rec3


class TestErrorHandlerSummary:
    """Тесты для сводки по ошибкам"""
    
    def test_error_summary_with_chat_errors(self):
        """
        Тест сводки с ошибками доступа к чатам
        
        Requirements: 8.7, 13.7
        """
        error_handler = ErrorHandler()
        
        # Добавляем различные ошибки
        error_handler.handle_chat_access_error(
            create_telethon_error(ChatAdminRequiredError), 
            "https://t.me/chat1"
        )
        error_handler.handle_chat_access_error(
            create_telethon_error(UserNotParticipantError), 
            "https://t.me/chat2"
        )
        error_handler.handle_chat_access_error(
            create_telethon_error(ChatWriteForbiddenError), 
            "https://t.me/chat3"
        )
        
        # Получаем сводку
        summary = error_handler.get_error_summary()
        
        # Проверяем общее количество ошибок
        assert summary['total_errors'] == 3
        assert summary['chat_access_errors'] == 3
        
        # Проверяем статистику по типам
        assert summary['chat_access_errors_by_type']['ChatAdminRequiredError'] == 1
        assert summary['chat_access_errors_by_type']['UserNotParticipantError'] == 1
        assert summary['chat_access_errors_by_type']['ChatWriteForbiddenError'] == 1
        
        # Проверяем статистику по источникам
        assert len(summary['errors_by_source']) == 3
        assert "https://t.me/chat1" in summary['errors_by_source']
        assert "https://t.me/chat2" in summary['errors_by_source']
        assert "https://t.me/chat3" in summary['errors_by_source']
    
    def test_empty_error_summary(self):
        """
        Тест пустой сводки (без ошибок)
        
        Requirements: 8.7, 13.7
        """
        error_handler = ErrorHandler()
        
        summary = error_handler.get_error_summary()
        
        # Проверяем что все счетчики нулевые
        assert summary['total_errors'] == 0
        assert summary['chat_access_errors'] == 0
        assert summary['flood_wait_errors'] == 0
        assert summary['channel_errors'] == 0
        assert summary['network_errors'] == 0
        assert summary['other_errors'] == 0
        
        # Проверяем что словари пустые
        assert summary['chat_access_errors_by_type'] == {}
        assert summary['errors_by_source'] == {}
        assert summary['failed_channels'] == []
        assert summary['details'] == []
    
    def test_error_summary_mixed_errors(self):
        """
        Тест сводки со смешанными типами ошибок
        
        Requirements: 8.7, 13.7
        """
        error_handler = ErrorHandler()
        
        # Добавляем ошибки доступа к чатам
        error_handler.handle_chat_access_error(
            create_telethon_error(ChatAdminRequiredError), 
            "https://t.me/chat1"
        )
        error_handler.handle_chat_access_error(
            create_telethon_error(ChatAdminRequiredError), 
            "https://t.me/chat1"
        )
        
        # Добавляем ошибки каналов (через старый метод)
        error_handler.handle_channel_error(
            create_telethon_error(ChannelPrivateError), 
            "test_channel"
        )
        
        # Получаем сводку
        summary = error_handler.get_error_summary()
        
        # Проверяем общее количество
        assert summary['total_errors'] == 3
        
        # Проверяем разделение по категориям
        assert summary['chat_access_errors'] == 2
        assert summary['channel_errors'] == 1
        
        # Проверяем детальную статистику
        assert summary['chat_access_errors_by_type']['ChatAdminRequiredError'] == 2
