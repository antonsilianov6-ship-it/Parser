# -*- coding: utf-8 -*-
"""
Property-based тесты для TelegramSender
"""

import pytest
from hypothesis import given, strategies as st, assume, settings, HealthCheck
from src.telegram.telegram_sender import TelegramSender


class TestTelegramSenderProperties:
    """Property-based тесты для TelegramSender"""
    
    def _create_sender(self):
        """Вспомогательный метод для создания TelegramSender"""
        config = {
            'API_ID': 12345,
            'API_HASH': 'test_hash'
        }
        return TelegramSender(config)
    
    @given(
        message=st.text(min_size=4097, max_size=6000, alphabet=st.characters(blacklist_categories=('Cs', 'Cc'))),
        max_length=st.integers(min_value=2000, max_value=4096)
    )
    @settings(
        suppress_health_check=[
            HealthCheck.function_scoped_fixture,
            HealthCheck.large_base_example,
            HealthCheck.data_too_large,
            HealthCheck.too_slow
        ],
        max_examples=10,
        deadline=None
    )
    def test_split_long_message_parts_within_limit(self, message, max_length):
        """
        Property 5.1: Каждая часть не превышает максимальную длину
        
        For any сообщения длиннее max_length, каждая часть после разбиения
        должна быть не длиннее max_length символов
        """
        sender = self._create_sender()
        parts = sender.split_long_message(message, max_length)
        
        # Проверяем, что каждая часть не превышает лимит
        for i, part in enumerate(parts):
            assert len(part) <= max_length, (
                f"Часть {i+1} превышает лимит: {len(part)} > {max_length}"
            )
    
    @given(
        message=st.text(min_size=1, max_size=20000)
    )
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_split_long_message_concatenation_preserves_content(self, message):
        """
        Property 5.2: Конкатенация частей восстанавливает исходное сообщение
        
        For any сообщения, конкатенация всех частей (с учетом удаленных пробелов)
        должна давать исходный текст
        """
        sender = self._create_sender()
        parts = sender.split_long_message(message)
        
        # Объединяем части обратно
        # Учитываем, что split_long_message может добавлять/удалять пробелы
        reconstructed = ' '.join(parts)
        
        # Нормализуем пробелы для сравнения
        original_normalized = ' '.join(message.split())
        reconstructed_normalized = ' '.join(reconstructed.split())
        
        assert original_normalized == reconstructed_normalized, (
            "Конкатенация частей не восстанавливает исходное сообщение"
        )
    
    @given(
        message=st.text(min_size=1, max_size=4096)
    )
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_split_short_message_returns_single_part(self, message):
        """
        Property 5.3: Короткие сообщения не разбиваются
        
        For any сообщения длиной <= 4096 символов, метод должен вернуть
        список из одного элемента
        """
        sender = self._create_sender()
        parts = sender.split_long_message(message)
        
        assert len(parts) == 1, (
            f"Короткое сообщение ({len(message)} символов) было разбито на {len(parts)} частей"
        )
        assert parts[0].strip() == message.strip(), (
            "Содержимое единственной части не совпадает с исходным сообщением"
        )
    
    @given(
        message=st.text(min_size=4097, max_size=6000, alphabet=st.characters(blacklist_categories=('Cs', 'Cc')))
    )
    @settings(
        suppress_health_check=[
            HealthCheck.function_scoped_fixture,
            HealthCheck.large_base_example,
            HealthCheck.data_too_large,
            HealthCheck.too_slow
        ],
        max_examples=10,
        deadline=None
    )
    def test_split_long_message_returns_multiple_parts(self, message):
        """
        Property 5.4: Длинные сообщения разбиваются на несколько частей
        
        For any сообщения длиной > 4096 символов, метод должен вернуть
        список из более чем одного элемента
        """
        sender = self._create_sender()
        parts = sender.split_long_message(message)
        
        assert len(parts) > 1, (
            f"Длинное сообщение ({len(message)} символов) не было разбито на части"
        )
    
    @given(
        message=st.text(min_size=1, max_size=20000)
    )
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_split_long_message_no_empty_parts(self, message):
        """
        Property 5.5: Разбиение не создает пустых частей
        
        For any сообщения, ни одна часть после разбиения не должна быть пустой
        """
        # Пропускаем пустые или состоящие только из пробелов сообщения
        assume(message.strip())
        
        sender = self._create_sender()
        parts = sender.split_long_message(message)
        
        # Проверяем, что нет пустых частей
        for i, part in enumerate(parts):
            assert part.strip(), (
                f"Часть {i+1} пустая или содержит только пробелы"
            )
    
    @given(
        sentence_count=st.integers(min_value=120, max_value=200)
    )
    @settings(
        suppress_health_check=[
            HealthCheck.function_scoped_fixture,
            HealthCheck.filter_too_much,
            HealthCheck.too_slow,
            HealthCheck.data_too_large
        ],
        max_examples=10,
        deadline=None
    )
    def test_split_long_message_preserves_sentence_boundaries(self, sentence_count):
        """
        Property 5.6: Разбиение старается сохранять границы предложений
        
        For any сообщения, состоящего из предложений, разбиение должно
        стараться не разрывать предложения (когда это возможно)
        """
        # Создаем сообщение из предложений фиксированной длины
        # чтобы гарантировать, что сообщение будет длиннее 4096 символов
        sentences = [f"Sentence number {i} with some text" for i in range(sentence_count)]
        message = '. '.join(sentences) + '.'
        
        # Проверяем, что сообщение действительно длинное
        assert len(message) > 4096, f"Сообщение слишком короткое: {len(message)}"
        
        sender = self._create_sender()
        parts = sender.split_long_message(message)
        
        # Проверяем, что большинство частей заканчиваются на точку или начинаются с начала предложения
        # (это эвристическая проверка, так как не всегда возможно сохранить границы)
        parts_ending_with_period = sum(1 for part in parts[:-1] if part.rstrip().endswith('.'))
        
        # Хотя бы 20% частей (кроме последней) должна заканчиваться на точку
        # если это возможно (т.е. если предложения не слишком длинные)
        if len(parts) > 1:
            ratio = parts_ending_with_period / (len(parts) - 1)
            # Проверяем, что хотя бы 20% частей заканчиваются на точку
            # (низкий порог, так как могут быть очень длинные предложения)
            assert ratio >= 0.2 or all(len(s) > 4096 for s in sentences), (
                f"Только {ratio*100:.1f}% частей заканчиваются на точку, "
                f"что может указывать на разрыв предложений"
            )
    
    @given(
        message=st.text(min_size=1, max_size=20000),
        max_length=st.integers(min_value=100, max_value=4096)
    )
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_split_long_message_total_length_preserved(self, message, max_length):
        """
        Property 5.7: Общая длина всех частей примерно равна исходной длине
        
        For any сообщения, сумма длин всех частей (с учетом пробелов)
        должна быть близка к длине исходного сообщения
        """
        # Пропускаем пустые или состоящие только из пробелов сообщения
        assume(message.strip())
        
        sender = self._create_sender()
        parts = sender.split_long_message(message, max_length)
        
        # Считаем общую длину всех частей
        total_length = sum(len(part) for part in parts)
        
        # Нормализуем исходное сообщение (удаляем лишние пробелы)
        normalized_message = ' '.join(message.split())
        
        # Вычисляем разницу в длине
        length_diff = abs(total_length - len(normalized_message))
        
        # Общая длина должна быть близка к длине нормализованного сообщения
        # Допускаем разницу до 15% из-за возможных изменений в пробелах и strip()
        # Для очень коротких сообщений (< 10 символов) допускаем большую разницу
        if len(normalized_message) < 10:
            max_allowed_diff = len(normalized_message)  # Для коротких сообщений допускаем 100% разницу
        else:
            max_allowed_diff = max(len(normalized_message) * 0.15, 2)  # Минимум 2 символа разницы
        
        assert length_diff <= max_allowed_diff, (
            f"Разница в длине слишком большая: {length_diff} > {max_allowed_diff} "
            f"(исходная: {len(normalized_message)}, итоговая: {total_length})"
        )
