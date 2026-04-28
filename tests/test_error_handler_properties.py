# -*- coding: utf-8 -*-
"""Property-based тесты для ErrorHandler"""

import pytest
from unittest.mock import Mock
from hypothesis import given, settings, strategies as st
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


# Стратегии для генерации данных
chat_error_types = st.sampled_from([
    'ChatAdminRequiredError',
    'UserNotParticipantError',
    'ChatWriteForbiddenError',
    'ChannelPrivateError',
    'UsernameNotOccupiedError'
])

all_error_types = st.sampled_from([
    'ChatAdminRequiredError',
    'UserNotParticipantError',
    'ChatWriteForbiddenError',
    'ChannelPrivateError',
    'UsernameNotOccupiedError',
    'FloodWaitError',
    'NetworkError',
    'TimeoutError',
    'UnknownError'
])

chat_links = st.text(
    min_size=10,
    max_size=50,
    alphabet=st.characters(whitelist_categories=('Ll', 'Lu', 'Nd'), whitelist_characters='/_-.')
).map(lambda x: f"https://t.me/{x}")


# Feature: chat-and-topic-support, Property 11: Error recommendations completeness
@given(error_type=chat_error_types)
@settings(max_examples=100)
def test_error_recommendations_completeness_property(error_type):
    """
    Property 11: Error recommendations completeness
    
    For any chat access error type (ChatAdminRequiredError, UserNotParticipantError, 
    ChatWriteForbiddenError, ChannelPrivateError, UsernameNotOccupiedError), 
    the ErrorHandler SHALL provide specific recommendations for resolution.
    
    Validates: Requirements 8.5
    """
    error_handler = ErrorHandler()
    
    # Получаем рекомендации для типа ошибки
    recommendations = error_handler.get_access_error_recommendations(error_type)
    
    # Проверяем что рекомендации не пустые
    assert recommendations is not None
    assert isinstance(recommendations, str)
    assert len(recommendations) > 0
    
    # Проверяем что рекомендации содержат полезную информацию
    assert 'Рекомендации:' in recommendations or 'рекомендаци' in recommendations.lower()
    
    # Проверяем специфичность рекомендаций для каждого типа ошибки
    if error_type == 'ChatAdminRequiredError':
        assert 'администратор' in recommendations.lower()
    elif error_type == 'UserNotParticipantError':
        assert 'участник' in recommendations.lower() or 'присоедин' in recommendations.lower()
    elif error_type == 'ChatWriteForbiddenError':
        assert 'приватност' in recommendations.lower() or 'доступ' in recommendations.lower()
    elif error_type == 'ChannelPrivateError':
        assert 'приватн' in recommendations.lower()
    elif error_type == 'UsernameNotOccupiedError':
        assert 'username' in recommendations.lower() or 'существует' in recommendations.lower()


# Feature: chat-and-topic-support, Property 12: Error statistics accumulation
@given(
    error_sequence=st.lists(
        st.tuples(all_error_types, chat_links),
        min_size=1,
        max_size=50
    )
)
@settings(max_examples=100)
def test_error_statistics_accumulation_property(error_sequence):
    """
    Property 12: Error statistics accumulation
    
    For any sequence of errors during parsing, the ErrorHandler SHALL correctly 
    accumulate error statistics, ensuring the count and categorization of errors 
    (by type and by source) is accurate and complete.
    
    Validates: Requirements 8.7
    """
    error_handler = ErrorHandler()
    
    # Создаем маппинг типов ошибок на классы исключений
    error_classes = {
        'ChatAdminRequiredError': ChatAdminRequiredError,
        'UserNotParticipantError': UserNotParticipantError,
        'ChatWriteForbiddenError': ChatWriteForbiddenError,
        'ChannelPrivateError': ChannelPrivateError,
        'UsernameNotOccupiedError': UsernameNotOccupiedError
    }
    
    # Типы ошибок, которые считаются как chat_access_errors в summary
    chat_access_error_types = {
        'ChatAdminRequiredError',
        'UserNotParticipantError',
        'ChatWriteForbiddenError'
    }
    
    # Подсчитываем ожидаемую статистику
    expected_by_type = {}
    expected_by_source = {}
    
    for error_type, chat_link in error_sequence:
        # Обрабатываем только ошибки доступа к чатам
        if error_type in error_classes:
            error_instance = create_telethon_error(error_classes[error_type])
            error_handler.handle_chat_access_error(error_instance, chat_link)
            
            # Обновляем ожидаемую статистику по типам
            if error_type not in expected_by_type:
                expected_by_type[error_type] = 0
            expected_by_type[error_type] += 1
            
            # Обновляем ожидаемую статистику по источникам
            if chat_link not in expected_by_source:
                expected_by_source[chat_link] = []
            expected_by_source[chat_link].append(error_type)
    
    # Проверяем накопленную статистику по типам
    assert error_handler.chat_access_errors == expected_by_type
    
    # Проверяем накопленную статистику по источникам
    assert error_handler.errors_by_source == expected_by_source
    
    # Проверяем что общее количество ошибок корректно
    total_chat_errors = sum(expected_by_type.values())
    assert len(error_handler.errors) >= total_chat_errors
    
    # Проверяем что get_error_summary возвращает корректную статистику
    summary = error_handler.get_error_summary()
    assert summary['chat_access_errors_by_type'] == expected_by_type
    assert summary['errors_by_source'] == expected_by_source
    
    # Подсчитываем только те ошибки, которые считаются chat_access_errors в summary
    expected_chat_access_count = sum(
        count for error_type, count in expected_by_type.items()
        if error_type in chat_access_error_types
    )
    assert summary['chat_access_errors'] == expected_chat_access_count


# Дополнительный property-тест для консистентности статистики
@given(
    chat_link=chat_links,
    error_count=st.integers(min_value=1, max_value=20)
)
@settings(max_examples=100)
def test_error_statistics_consistency_property(chat_link, error_count):
    """
    Property: Error statistics consistency
    
    For any source and number of errors, the accumulated statistics SHALL be 
    consistent across different views (by_type, by_source, total_errors).
    """
    error_handler = ErrorHandler()
    
    # Генерируем последовательность ошибок одного типа для одного источника
    error = create_telethon_error(ChatAdminRequiredError)
    
    for _ in range(error_count):
        error_handler.handle_chat_access_error(error, chat_link)
    
    # Проверяем консистентность статистики
    assert error_handler.chat_access_errors['ChatAdminRequiredError'] == error_count
    assert len(error_handler.errors_by_source[chat_link]) == error_count
    assert all(
        err_type == 'ChatAdminRequiredError' 
        for err_type in error_handler.errors_by_source[chat_link]
    )
    
    # Проверяем что summary корректно отражает статистику
    summary = error_handler.get_error_summary()
    assert summary['chat_access_errors'] == error_count
    assert summary['chat_access_errors_by_type']['ChatAdminRequiredError'] == error_count
    assert chat_link in summary['errors_by_source']
    assert len(summary['errors_by_source'][chat_link]) == error_count


# Property-тест для проверки что рекомендации всегда возвращаются
@given(error_type=st.text(min_size=1, max_size=50))
@settings(max_examples=100)
def test_recommendations_always_returned_property(error_type):
    """
    Property: Recommendations always returned
    
    For any error type (even unknown), the ErrorHandler SHALL always return 
    a non-empty recommendation string (default recommendation for unknown types).
    """
    error_handler = ErrorHandler()
    
    recommendations = error_handler.get_access_error_recommendations(error_type)
    
    # Проверяем что всегда возвращается строка
    assert recommendations is not None
    assert isinstance(recommendations, str)
    assert len(recommendations) > 0
    
    # Проверяем что есть хоть какая-то полезная информация
    assert len(recommendations) >= 10  # Минимальная длина осмысленной рекомендации
