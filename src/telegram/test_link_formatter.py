# -*- coding: utf-8 -*-
"""
Unit-тесты для модуля LinkFormatter
"""

import pytest
from src.telegram.link_formatter import LinkFormatter


class MockEntity:
    """Мок-объект для entity канала"""
    def __init__(self, username=None, channel_id=None):
        self.username = username
        self.id = channel_id


class TestExtractUsername:
    """Тесты для метода extract_username"""
    
    def test_extract_from_https_link(self):
        """Извлечение username из https ссылки"""
        result = LinkFormatter.extract_username('https://t.me/testchannel')
        assert result == '@testchannel'
    
    def test_extract_from_http_link(self):
        """Извлечение username из http ссылки"""
        result = LinkFormatter.extract_username('http://t.me/testchannel')
        assert result == '@testchannel'
    
    def test_extract_from_at_username(self):
        """Извлечение username, который уже начинается с @"""
        result = LinkFormatter.extract_username('@testchannel')
        assert result == '@testchannel'
    
    def test_extract_with_trailing_slash(self):
        """Извлечение username со слэшем в конце"""
        result = LinkFormatter.extract_username('https://t.me/testchannel/')
        assert result == '@testchannel'
    
    def test_extract_with_query_params(self):
        """Извлечение username с параметрами запроса"""
        result = LinkFormatter.extract_username('https://t.me/testchannel?param=value')
        assert result == '@testchannel'


class TestFormatPrivateChannelId:
    """Тесты для метода format_private_channel_id"""
    
    def test_format_negative_id_with_100_prefix(self):
        """Форматирование отрицательного ID с префиксом 100"""
        result = LinkFormatter.format_private_channel_id(-1001234567890)
        assert result == '1234567890'
    
    def test_format_positive_id_with_100_prefix(self):
        """Форматирование положительного ID с префиксом 100"""
        result = LinkFormatter.format_private_channel_id(1001234567890)
        assert result == '1234567890'
    
    def test_format_id_without_100_prefix(self):
        """Форматирование ID без префикса 100"""
        result = LinkFormatter.format_private_channel_id(1234567890)
        assert result == '1234567890'
    
    def test_format_negative_id_without_100_prefix(self):
        """Форматирование отрицательного ID без префикса 100"""
        result = LinkFormatter.format_private_channel_id(-1234567890)
        assert result == '1234567890'


class TestValidateLink:
    """Тесты для метода validate_link"""
    
    def test_valid_public_channel_link(self):
        """Валидация корректной ссылки на публичный канал"""
        assert LinkFormatter.validate_link('https://t.me/channel/123') is True
    
    def test_valid_private_channel_link(self):
        """Валидация корректной ссылки на приватный канал"""
        assert LinkFormatter.validate_link('https://t.me/c/1234567890/123') is True
    
    def test_valid_comment_link(self):
        """Валидация корректной ссылки на комментарий"""
        assert LinkFormatter.validate_link('https://t.me/channel/123?comment=456') is True
    
    def test_invalid_empty_link(self):
        """Валидация пустой ссылки"""
        assert LinkFormatter.validate_link('') is False
    
    def test_invalid_none_link(self):
        """Валидация None ссылки"""
        assert LinkFormatter.validate_link(None) is False
    
    def test_invalid_link_with_none_string(self):
        """Валидация ссылки содержащей 'None'"""
        assert LinkFormatter.validate_link('https://t.me/None/123') is False
    
    def test_invalid_wrong_protocol(self):
        """Валидация ссылки с неправильным протоколом"""
        assert LinkFormatter.validate_link('http://example.com/channel') is False
    
    def test_invalid_too_short_link(self):
        """Валидация слишком короткой ссылки"""
        assert LinkFormatter.validate_link('https://t.me/') is False


class TestFormatMessageLink:
    """Тесты для метода format_message_link"""
    
    def test_format_with_original_public_link(self):
        """Форматирование ссылки с использованием оригинального username"""
        entity = MockEntity(username='entity_channel', channel_id=1001234567890)
        result = LinkFormatter.format_message_link(
            'https://t.me/original_channel',
            entity,
            123
        )
        assert result == 'https://t.me/original_channel/123'
    
    def test_format_with_entity_username(self):
        """Форматирование ссылки с использованием username из entity"""
        entity = MockEntity(username='testchannel', channel_id=1001234567890)
        result = LinkFormatter.format_message_link(
            '@testchannel',
            entity,
            123
        )
        assert result == 'https://t.me/testchannel/123'
    
    def test_format_with_private_channel_id(self):
        """Форматирование ссылки для приватного канала"""
        entity = MockEntity(username=None, channel_id=-1001234567890)
        result = LinkFormatter.format_message_link(
            'https://t.me/c/1234567890',
            entity,
            123
        )
        assert result == 'https://t.me/c/1234567890/123'
    
    def test_format_returns_none_for_invalid_entity(self):
        """Возврат None для невалидного entity"""
        entity = MockEntity(username=None, channel_id=None)
        result = LinkFormatter.format_message_link(
            '@invalid',
            entity,
            123
        )
        assert result is None


class TestFormatCommentLink:
    """Тесты для метода format_comment_link"""
    
    def test_format_comment_in_public_channel(self):
        """Форматирование ссылки на комментарий в публичном канале"""
        entity = MockEntity(username='testchannel', channel_id=1001234567890)
        result = LinkFormatter.format_comment_link(entity, 123, 456, is_discussion=False)
        assert result == 'https://t.me/testchannel/123?comment=456'
    
    def test_format_comment_in_discussion_chat(self):
        """Форматирование ссылки на комментарий в discussion chat"""
        entity = MockEntity(username='discussion_chat', channel_id=1001234567890)
        result = LinkFormatter.format_comment_link(entity, 123, 789, is_discussion=True)
        assert result == 'https://t.me/discussion_chat/789'
    
    def test_format_comment_in_private_channel(self):
        """Форматирование ссылки на комментарий в приватном канале"""
        entity = MockEntity(username=None, channel_id=-1001234567890)
        result = LinkFormatter.format_comment_link(entity, 123, 456, is_discussion=False)
        assert result == 'https://t.me/c/1234567890/123?comment=456'
    
    def test_format_comment_in_private_discussion(self):
        """Форматирование ссылки на комментарий в приватном discussion chat"""
        entity = MockEntity(username=None, channel_id=-1001234567890)
        result = LinkFormatter.format_comment_link(entity, 123, 789, is_discussion=True)
        assert result == 'https://t.me/c/1234567890/789'
    
    def test_format_returns_none_for_invalid_entity(self):
        """Возврат None для невалидного entity"""
        entity = MockEntity(username=None, channel_id=None)
        result = LinkFormatter.format_comment_link(entity, 123, 456, is_discussion=False)
        assert result is None


if __name__ == '__main__':
    pytest.main([__file__, '-v'])


# Property-based тесты с использованием Hypothesis
from hypothesis import given, strategies as st, settings, assume


class TestChatLinkFormatProperties:
    """Property-based тесты для формирования ссылок на чаты"""
    
    @given(
        username=st.text(
            alphabet=st.characters(whitelist_categories=('Ll', 'Lu', 'Nd'), min_codepoint=48, max_codepoint=122),
            min_size=5,
            max_size=32
        ).filter(lambda x: x.isalnum() and not x.startswith('c')),
        message_id=st.integers(min_value=1, max_value=999999999),
        chat_id=st.integers(min_value=1000000000, max_value=9999999999),
        is_private=st.booleans()
    )
    @settings(max_examples=100)
    def test_property_8_link_format_correctness_for_chats(self, username, message_id, chat_id, is_private):
        """
        Property 8: Link format correctness for chats
        **Validates: Requirements 7.2, 7.3, 7.4, 7.5**
        
        Проверяет, что ссылки на сообщения в чатах формируются корректно:
        - Публичные чаты: https://t.me/chatname/message_id
        - Приватные чаты: https://t.me/c/CHAT_ID/message_id
        - Ссылки не содержат None
        - Ссылки имеют корректный формат
        """
        if is_private:
            # Генерируем приватный чат с ID
            entity = MockEntity(username=None, channel_id=-100 * 10**10 - chat_id)
            chat_link = f"https://t.me/c/{chat_id}"
            
            result = LinkFormatter.format_chat_message_link(chat_link, entity, message_id)
            
            # Проверяем корректность формата приватного чата
            assert result is not None, "Ссылка не должна быть None для приватного чата"
            assert result.startswith('https://t.me/c/'), "Приватный чат должен начинаться с https://t.me/c/"
            assert 'None' not in result, "Ссылка не должна содержать 'None'"
            assert str(message_id) in result, "Ссылка должна содержать message_id"
            
            # Проверяем структуру: https://t.me/c/CHAT_ID/message_id
            parts = result.replace('https://t.me/c/', '').split('/')
            assert len(parts) == 2, "Приватная ссылка должна иметь формат /c/CHAT_ID/message_id"
            assert parts[0].isdigit(), "CHAT_ID должен быть числом"
            assert parts[1] == str(message_id), "Второй параметр должен быть message_id"
        else:
            # Генерируем публичный чат с username
            entity = MockEntity(username=username, channel_id=-1001234567890)
            chat_link = f"https://t.me/{username}"
            
            result = LinkFormatter.format_chat_message_link(chat_link, entity, message_id)
            
            # Проверяем корректность формата публичного чата
            assert result is not None, "Ссылка не должна быть None для публичного чата"
            assert result.startswith('https://t.me/'), "Публичный чат должен начинаться с https://t.me/"
            assert '/c/' not in result, "Публичный чат не должен содержать /c/"
            assert 'None' not in result, "Ссылка не должна содержать 'None'"
            assert username in result, "Ссылка должна содержать username"
            assert str(message_id) in result, "Ссылка должна содержать message_id"
            
            # Проверяем структуру: https://t.me/chatname/message_id
            expected = f"https://t.me/{username}/{message_id}"
            assert result == expected, f"Ожидалась ссылка {expected}, получена {result}"
    
    @given(
        message_id=st.integers(min_value=1, max_value=999999999)
    )
    @settings(max_examples=100)
    def test_property_8_none_entity_returns_none(self, message_id):
        """
        Property 8: Link format correctness for chats - None entity case
        **Validates: Requirements 7.2, 7.3, 7.4, 7.5**
        
        Проверяет, что при None entity возвращается None
        """
        result = LinkFormatter.format_chat_message_link('https://t.me/chat', None, message_id)
        assert result is None, "При None entity должен возвращаться None"
    
    @given(
        username=st.text(
            alphabet=st.characters(whitelist_categories=('Ll', 'Lu', 'Nd'), min_codepoint=48, max_codepoint=122),
            min_size=5,
            max_size=32
        ).filter(lambda x: x.isalnum()),
        message_id=st.integers(min_value=1, max_value=999999999)
    )
    @settings(max_examples=100)
    def test_property_8_is_private_chat_detection(self, username, message_id):
        """
        Property 8: Link format correctness for chats - private chat detection
        **Validates: Requirements 7.2, 7.3, 7.4, 7.5**
        
        Проверяет корректность определения приватных чатов
        """
        # Публичный чат не должен определяться как приватный
        public_link = f"https://t.me/{username}"
        assert LinkFormatter.is_private_chat(public_link) is False, "Публичный чат не должен быть приватным"
        
        # Приватный чат должен определяться как приватный
        private_link = f"https://t.me/c/{message_id}"
        assert LinkFormatter.is_private_chat(private_link) is True, "Приватный чат должен быть приватным"
        
        # Пустая ссылка не должна быть приватной
        assert LinkFormatter.is_private_chat('') is False, "Пустая ссылка не должна быть приватной"
        assert LinkFormatter.is_private_chat(None) is False, "None не должен быть приватным"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])



class TestTopicLinkFormatProperties:
    """Property-based тесты для формирования ссылок на топики"""
    
    @given(
        username=st.text(
            alphabet=st.characters(whitelist_categories=('Ll', 'Lu', 'Nd'), min_codepoint=48, max_codepoint=122),
            min_size=5,
            max_size=32
        ).filter(lambda x: x.isalnum() and not x.startswith('c')),
        topic_id=st.integers(min_value=1, max_value=999999),
        message_id=st.integers(min_value=1, max_value=999999999),
        chat_id=st.integers(min_value=1000000000, max_value=9999999999),
        is_private=st.booleans()
    )
    @settings(max_examples=100)
    def test_property_9_link_format_correctness_for_topics(self, username, topic_id, message_id, chat_id, is_private):
        """
        Property 9: Link format correctness for topics
        **Validates: Requirements 7.4, 7.5**
        
        Проверяет, что ссылки на сообщения в топиках формируются корректно:
        - Публичный форум: https://t.me/chatname/topic_id/message_id
        - Приватный форум: https://t.me/c/CHAT_ID/topic_id/message_id
        - Ссылки не содержат None
        - Ссылки имеют корректный формат с topic_id
        """
        if is_private:
            # Генерируем приватный форум-чат с ID
            entity = MockEntity(username=None, channel_id=-100 * 10**10 - chat_id)
            
            result = LinkFormatter.format_topic_message_link(entity, topic_id, message_id)
            
            # Проверяем корректность формата приватного форум-чата
            assert result is not None, "Ссылка не должна быть None для приватного форум-чата"
            assert result.startswith('https://t.me/c/'), "Приватный форум должен начинаться с https://t.me/c/"
            assert 'None' not in result, "Ссылка не должна содержать 'None'"
            assert str(topic_id) in result, "Ссылка должна содержать topic_id"
            assert str(message_id) in result, "Ссылка должна содержать message_id"
            
            # Проверяем структуру: https://t.me/c/CHAT_ID/topic_id/message_id
            parts = result.replace('https://t.me/c/', '').split('/')
            assert len(parts) == 3, "Приватная ссылка на топик должна иметь формат /c/CHAT_ID/topic_id/message_id"
            assert parts[0].isdigit(), "CHAT_ID должен быть числом"
            assert parts[1] == str(topic_id), "Второй параметр должен быть topic_id"
            assert parts[2] == str(message_id), "Третий параметр должен быть message_id"
        else:
            # Генерируем публичный форум-чат с username
            entity = MockEntity(username=username, channel_id=-1001234567890)
            
            result = LinkFormatter.format_topic_message_link(entity, topic_id, message_id)
            
            # Проверяем корректность формата публичного форум-чата
            assert result is not None, "Ссылка не должна быть None для публичного форум-чата"
            assert result.startswith('https://t.me/'), "Публичный форум должен начинаться с https://t.me/"
            assert '/c/' not in result, "Публичный форум не должен содержать /c/"
            assert 'None' not in result, "Ссылка не должна содержать 'None'"
            assert username in result, "Ссылка должна содержать username"
            assert str(topic_id) in result, "Ссылка должна содержать topic_id"
            assert str(message_id) in result, "Ссылка должна содержать message_id"
            
            # Проверяем структуру: https://t.me/chatname/topic_id/message_id
            expected = f"https://t.me/{username}/{topic_id}/{message_id}"
            assert result == expected, f"Ожидалась ссылка {expected}, получена {result}"
    
    @given(
        topic_id=st.integers(min_value=1, max_value=999999),
        message_id=st.integers(min_value=1, max_value=999999999)
    )
    @settings(max_examples=100)
    def test_property_9_none_entity_returns_none(self, topic_id, message_id):
        """
        Property 9: Link format correctness for topics - None entity case
        **Validates: Requirements 7.4, 7.5**
        
        Проверяет, что при None entity возвращается None
        """
        result = LinkFormatter.format_topic_message_link(None, topic_id, message_id)
        assert result is None, "При None entity должен возвращаться None"
    
    @given(
        username=st.text(
            alphabet=st.characters(whitelist_categories=('Ll', 'Lu', 'Nd'), min_codepoint=48, max_codepoint=122),
            min_size=5,
            max_size=32
        ).filter(lambda x: x.isalnum()),
        topic_id=st.integers(min_value=1, max_value=999999),
        message_id=st.integers(min_value=1, max_value=999999999)
    )
    @settings(max_examples=100)
    def test_property_9_topic_link_contains_all_ids(self, username, topic_id, message_id):
        """
        Property 9: Link format correctness for topics - all IDs present
        **Validates: Requirements 7.4, 7.5**
        
        Проверяет, что ссылка на топик содержит все необходимые идентификаторы
        """
        entity = MockEntity(username=username, channel_id=-1001234567890)
        result = LinkFormatter.format_topic_message_link(entity, topic_id, message_id)
        
        assert result is not None, "Ссылка не должна быть None"
        
        # Проверяем наличие всех компонентов
        parts = result.split('/')
        assert len(parts) >= 5, "Ссылка на топик должна содержать минимум 5 частей"
        assert parts[-2] == str(topic_id), "Предпоследняя часть должна быть topic_id"
        assert parts[-1] == str(message_id), "Последняя часть должна быть message_id"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])



class TestLinkValidationProperties:
    """Property-based тесты для валидации ссылок"""
    
    @given(
        username=st.text(
            alphabet=st.characters(whitelist_categories=('Ll', 'Lu', 'Nd'), min_codepoint=48, max_codepoint=122),
            min_size=5,
            max_size=32
        ).filter(lambda x: x.isalnum() and 'None' not in x),
        message_id=st.integers(min_value=1, max_value=999999999),
        chat_id=st.integers(min_value=1000000000, max_value=9999999999),
        comment_id=st.integers(min_value=1, max_value=999999999)
    )
    @settings(max_examples=100)
    def test_property_10_valid_links_pass_validation(self, username, message_id, chat_id, comment_id):
        """
        Property 10: Link validation consistency - valid links
        **Validates: Requirements 7.6, 7.7**
        
        Проверяет, что валидация принимает корректные ссылки
        """
        # Публичная ссылка на канал/чат
        public_link = f"https://t.me/{username}/{message_id}"
        assert LinkFormatter.validate_link(public_link) is True, \
            f"Корректная публичная ссылка должна проходить валидацию: {public_link}"
        
        # Приватная ссылка на канал/чат
        private_link = f"https://t.me/c/{chat_id}/{message_id}"
        assert LinkFormatter.validate_link(private_link) is True, \
            f"Корректная приватная ссылка должна проходить валидацию: {private_link}"
        
        # Ссылка с комментарием
        comment_link = f"https://t.me/{username}/{message_id}?comment={comment_id}"
        assert LinkFormatter.validate_link(comment_link) is True, \
            f"Корректная ссылка с комментарием должна проходить валидацию: {comment_link}"
    
    @given(
        username=st.text(
            alphabet=st.characters(whitelist_categories=('Ll', 'Lu', 'Nd'), min_codepoint=48, max_codepoint=122),
            min_size=5,
            max_size=32
        ).filter(lambda x: x.isalnum()),
        topic_id=st.integers(min_value=1, max_value=999999),
        message_id=st.integers(min_value=1, max_value=999999999),
        chat_id=st.integers(min_value=1000000000, max_value=9999999999)
    )
    @settings(max_examples=100)
    def test_property_10_topic_links_pass_validation(self, username, topic_id, message_id, chat_id):
        """
        Property 10: Link validation consistency - topic links
        **Validates: Requirements 7.6, 7.7**
        
        Проверяет, что валидация принимает корректные ссылки на топики
        """
        # Публичная ссылка на топик
        public_topic_link = f"https://t.me/{username}/{topic_id}/{message_id}"
        assert LinkFormatter.validate_link(public_topic_link) is True, \
            f"Корректная ссылка на топик должна проходить валидацию: {public_topic_link}"
        
        # Приватная ссылка на топик
        private_topic_link = f"https://t.me/c/{chat_id}/{topic_id}/{message_id}"
        assert LinkFormatter.validate_link(private_topic_link) is True, \
            f"Корректная приватная ссылка на топик должна проходить валидацию: {private_topic_link}"
    
    @given(
        invalid_content=st.one_of(
            st.just(''),
            st.just(None),
            st.just('http://example.com/channel'),
            st.just('https://t.me/'),
            st.just('https://t.me/None/123'),
            st.just('https://t.me/channel/None'),
            st.text(max_size=10).filter(lambda x: not x.startswith('https://t.me/'))
        )
    )
    @settings(max_examples=100)
    def test_property_10_invalid_links_fail_validation(self, invalid_content):
        """
        Property 10: Link validation consistency - invalid links
        **Validates: Requirements 7.6, 7.7**
        
        Проверяет, что валидация отклоняет некорректные ссылки
        """
        result = LinkFormatter.validate_link(invalid_content)
        assert result is False, \
            f"Некорректная ссылка должна не проходить валидацию: {invalid_content}"
    
    @given(
        username=st.text(
            alphabet=st.characters(whitelist_categories=('Ll', 'Lu', 'Nd'), min_codepoint=48, max_codepoint=122),
            min_size=5,
            max_size=32
        ).filter(lambda x: x.isalnum()),
        message_id=st.integers(min_value=1, max_value=999999999)
    )
    @settings(max_examples=100)
    def test_property_10_links_with_none_fail_validation(self, username, message_id):
        """
        Property 10: Link validation consistency - links with None
        **Validates: Requirements 7.6, 7.7**
        
        Проверяет, что ссылки содержащие 'None' отклоняются валидацией
        """
        # Ссылка с None в username
        link_with_none_username = f"https://t.me/None/{message_id}"
        assert LinkFormatter.validate_link(link_with_none_username) is False, \
            "Ссылка с 'None' в username должна не проходить валидацию"
        
        # Ссылка с None в message_id
        link_with_none_message = f"https://t.me/{username}/None"
        assert LinkFormatter.validate_link(link_with_none_message) is False, \
            "Ссылка с 'None' в message_id должна не проходить валидацию"
        
        # Ссылка с None в chat_id
        link_with_none_chat = f"https://t.me/c/None/{message_id}"
        assert LinkFormatter.validate_link(link_with_none_chat) is False, \
            "Ссылка с 'None' в chat_id должна не проходить валидацию"
    
    @given(
        username=st.text(
            alphabet=st.characters(whitelist_categories=('Ll', 'Lu', 'Nd'), min_codepoint=48, max_codepoint=122),
            min_size=5,
            max_size=32
        ).filter(lambda x: x.isalnum()),
        message_id=st.integers(min_value=1, max_value=999999999),
        topic_id=st.integers(min_value=1, max_value=999999)
    )
    @settings(max_examples=100)
    def test_property_10_validation_consistency_with_formatters(self, username, message_id, topic_id):
        """
        Property 10: Link validation consistency - formatter output validation
        **Validates: Requirements 7.6, 7.7**
        
        Проверяет, что ссылки созданные форматтерами всегда проходят валидацию
        """
        # Тестируем format_chat_message_link
        entity = MockEntity(username=username, channel_id=-1001234567890)
        chat_link = f"https://t.me/{username}"
        result = LinkFormatter.format_chat_message_link(chat_link, entity, message_id)
        
        if result is not None:
            assert LinkFormatter.validate_link(result) is True, \
                f"Ссылка созданная format_chat_message_link должна проходить валидацию: {result}"
        
        # Тестируем format_topic_message_link
        topic_result = LinkFormatter.format_topic_message_link(entity, topic_id, message_id)
        
        if topic_result is not None:
            assert LinkFormatter.validate_link(topic_result) is True, \
                f"Ссылка созданная format_topic_message_link должна проходить валидацию: {topic_result}"
        
        # Тестируем format_message_link (для обратной совместимости)
        message_result = LinkFormatter.format_message_link(chat_link, entity, message_id)
        
        if message_result is not None:
            assert LinkFormatter.validate_link(message_result) is True, \
                f"Ссылка созданная format_message_link должна проходить валидацию: {message_result}"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])



class TestChatMessageLinkFormatting:
    """Unit-тесты для метода format_chat_message_link"""
    
    def test_none_entity_returns_none(self):
        """
        Тест для None entity (должен возвращать None)
        **Validates: Requirements 7.7, 12.4, 13.4**
        """
        result = LinkFormatter.format_chat_message_link('https://t.me/chat', None, 123)
        assert result is None, "При None entity должен возвращаться None"
    
    def test_public_chat_with_original_link(self):
        """
        Тест для публичного чата с оригинальной ссылкой
        **Validates: Requirements 7.2, 7.7, 12.4, 13.4**
        """
        entity = MockEntity(username='testchat', channel_id=-1001234567890)
        result = LinkFormatter.format_chat_message_link('https://t.me/originalchat', entity, 123)
        assert result == 'https://t.me/originalchat/123'
    
    def test_public_chat_with_entity_username(self):
        """
        Тест для публичного чата с username из entity
        **Validates: Requirements 7.2, 7.7, 12.4, 13.4**
        """
        entity = MockEntity(username='testchat', channel_id=-1001234567890)
        result = LinkFormatter.format_chat_message_link('@testchat', entity, 456)
        assert result == 'https://t.me/testchat/456'
    
    def test_private_chat_with_id(self):
        """
        Тест для приватного чата с ID
        **Validates: Requirements 7.3, 7.7, 12.4, 13.4**
        """
        entity = MockEntity(username=None, channel_id=-1001234567890)
        result = LinkFormatter.format_chat_message_link('https://t.me/c/1234567890', entity, 789)
        assert result == 'https://t.me/c/1234567890/789'
    
    def test_is_private_chat_detection(self):
        """
        Тест для метода is_private_chat
        **Validates: Requirements 7.3, 7.7, 12.4, 13.4**
        """
        assert LinkFormatter.is_private_chat('https://t.me/c/1234567890') is True
        assert LinkFormatter.is_private_chat('https://t.me/publicchat') is False
        assert LinkFormatter.is_private_chat('') is False
        assert LinkFormatter.is_private_chat(None) is False


class TestTopicMessageLinkFormatting:
    """Unit-тесты для метода format_topic_message_link"""
    
    def test_none_entity_returns_none(self):
        """
        Тест для None entity (должен возвращать None)
        **Validates: Requirements 7.7, 12.4, 13.4**
        """
        result = LinkFormatter.format_topic_message_link(None, 5, 123)
        assert result is None, "При None entity должен возвращаться None"
    
    def test_public_forum_chat_link(self):
        """
        Тест для публичного форум-чата
        **Validates: Requirements 7.4, 7.5, 7.7, 12.4, 13.4**
        """
        entity = MockEntity(username='forumchat', channel_id=-1001234567890)
        result = LinkFormatter.format_topic_message_link(entity, 5, 123)
        assert result == 'https://t.me/forumchat/5/123'
    
    def test_private_forum_chat_link(self):
        """
        Тест для приватного форум-чата
        **Validates: Requirements 7.4, 7.5, 7.7, 12.4, 13.4**
        """
        entity = MockEntity(username=None, channel_id=-1001234567890)
        result = LinkFormatter.format_topic_message_link(entity, 10, 456)
        assert result == 'https://t.me/c/1234567890/10/456'
    
    def test_topic_link_with_large_ids(self):
        """
        Тест для топика с большими ID
        **Validates: Requirements 7.4, 7.5, 7.7, 12.4, 13.4**
        """
        entity = MockEntity(username='bigforum', channel_id=-1009876543210)
        result = LinkFormatter.format_topic_message_link(entity, 999999, 999999999)
        assert result == 'https://t.me/bigforum/999999/999999999'


class TestBackwardCompatibility:
    """Unit-тесты для обратной совместимости с каналами"""
    
    def test_format_message_link_still_works_for_channels(self):
        """
        Тест для обратной совместимости format_message_link с каналами
        **Validates: Requirements 7.7, 12.4, 13.4**
        """
        entity = MockEntity(username='testchannel', channel_id=-1001234567890)
        result = LinkFormatter.format_message_link('https://t.me/testchannel', entity, 123)
        assert result == 'https://t.me/testchannel/123'
    
    def test_format_comment_link_still_works(self):
        """
        Тест для обратной совместимости format_comment_link
        **Validates: Requirements 7.7, 12.4, 13.4**
        """
        entity = MockEntity(username='testchannel', channel_id=-1001234567890)
        result = LinkFormatter.format_comment_link(entity, 123, 456, is_discussion=False)
        assert result == 'https://t.me/testchannel/123?comment=456'
    
    def test_validate_link_works_for_all_formats(self):
        """
        Тест для валидации всех форматов ссылок
        **Validates: Requirements 7.6, 7.7, 12.4, 13.4**
        """
        # Канал
        assert LinkFormatter.validate_link('https://t.me/channel/123') is True
        
        # Чат
        assert LinkFormatter.validate_link('https://t.me/chat/456') is True
        
        # Приватный чат
        assert LinkFormatter.validate_link('https://t.me/c/1234567890/789') is True
        
        # Топик в публичном форуме
        assert LinkFormatter.validate_link('https://t.me/forum/5/123') is True
        
        # Топик в приватном форуме
        assert LinkFormatter.validate_link('https://t.me/c/1234567890/5/456') is True
        
        # Комментарий
        assert LinkFormatter.validate_link('https://t.me/channel/123?comment=456') is True


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
