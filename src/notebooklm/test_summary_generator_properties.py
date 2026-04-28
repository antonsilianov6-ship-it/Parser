# -*- coding: utf-8 -*-
"""Property-based тесты для SummaryGenerator"""

import pytest
from hypothesis import given, strategies as st, assume
from unittest.mock import Mock, AsyncMock, patch
from src.notebooklm.summary_generator import SummaryGenerator


# Property 3: Извлечение текста из ответа API
# For any валидного ответа от NotebookLM API (содержащего поле с текстом сводки), 
# метод SummaryGenerator должен корректно извлечь текст сводки без потери данных


@given(response_text=st.text(min_size=1))
@pytest.mark.asyncio
async def test_property_extract_text_from_api_response(response_text):
    """
    Property: Текст из ответа API должен извлекаться без потери данных
    
    Validates: Requirements 3.4
    """
    # Arrange
    mock_client = Mock()
    mock_client.query_notebook = AsyncMock(return_value=response_text)
    
    generator = SummaryGenerator(mock_client, config_path="config/prompts.json")
    notebook_id = "test_notebook_123"
    
    # Act
    result = await generator.generate_negative_summary(notebook_id)
    
    # Assert
    assert result == response_text, (
        f"Извлеченный текст должен совпадать с исходным. "
        f"Ожидалось: {response_text!r}, получено: {result!r}"
    )
    assert len(result) == len(response_text), (
        f"Длина извлеченного текста должна совпадать с исходной. "
        f"Ожидалось: {len(response_text)}, получено: {len(result)}"
    )


@given(response_text=st.text(min_size=1))
@pytest.mark.asyncio
async def test_property_extract_text_from_positive_summary(response_text):
    """
    Property: Текст из ответа API для позитивной сводки должен извлекаться без потери данных
    
    Validates: Requirements 3.4
    """
    # Arrange
    mock_client = Mock()
    mock_client.query_notebook = AsyncMock(return_value=response_text)
    
    generator = SummaryGenerator(mock_client, config_path="config/prompts.json")
    notebook_id = "test_notebook_456"
    
    # Act
    result = await generator.generate_positive_summary(notebook_id)
    
    # Assert
    assert result == response_text, (
        f"Извлеченный текст должен совпадать с исходным. "
        f"Ожидалось: {response_text!r}, получено: {result!r}"
    )
    assert len(result) == len(response_text), (
        f"Длина извлеченного текста должна совпадать с исходной. "
        f"Ожидалось: {len(response_text)}, получено: {len(result)}"
    )


# Property 6: Валидация структуры промптов
# For any промпта, содержащего все обязательные поля (template), 
# метод validate_prompt() должен возвращать True; 
# для промптов без обязательных полей должен возвращать False


@given(
    template=st.text(min_size=1),
    required_fields=st.lists(st.text(min_size=1), min_size=1),
    variables=st.lists(st.text())
)
def test_property_validate_prompt_with_all_required_fields(
    template, required_fields, variables
):
    """
    Property: Промпт с полем 'template' в required_fields должен быть валидным
    
    Validates: Requirements 4.4
    """
    # Arrange
    mock_client = Mock()
    generator = SummaryGenerator(mock_client, config_path="config/prompts.json")
    
    # Убедимся, что 'template' есть в required_fields
    if 'template' not in required_fields:
        required_fields.append('template')
    
    prompt = {
        'template': template,
        'required_fields': required_fields,
        'variables': variables
    }
    
    # Act
    result = generator.validate_prompt(prompt)
    
    # Assert
    assert result is True, (
        f"Промпт с обязательными полями должен быть валидным. "
        f"Промпт: {prompt}"
    )


@given(
    required_fields=st.lists(st.text(min_size=1)),
    variables=st.lists(st.text())
)
def test_property_validate_prompt_without_template_field(required_fields, variables):
    """
    Property: Промпт без поля 'template' должен быть невалидным
    
    Validates: Requirements 4.4
    """
    # Arrange
    mock_client = Mock()
    generator = SummaryGenerator(mock_client, config_path="config/prompts.json")
    
    prompt = {
        'required_fields': required_fields,
        'variables': variables
    }
    # Намеренно не добавляем 'template'
    
    # Act
    result = generator.validate_prompt(prompt)
    
    # Assert
    assert result is False, (
        f"Промпт без поля 'template' должен быть невалидным. "
        f"Промпт: {prompt}"
    )


@given(
    template=st.text(min_size=1),
    variables=st.lists(st.text())
)
def test_property_validate_prompt_without_required_fields(template, variables):
    """
    Property: Промпт без поля 'required_fields' должен быть невалидным
    
    Validates: Requirements 4.4
    """
    # Arrange
    mock_client = Mock()
    generator = SummaryGenerator(mock_client, config_path="config/prompts.json")
    
    prompt = {
        'template': template,
        'variables': variables
    }
    # Намеренно не добавляем 'required_fields'
    
    # Act
    result = generator.validate_prompt(prompt)
    
    # Assert
    assert result is False, (
        f"Промпт без поля 'required_fields' должен быть невалидным. "
        f"Промпт: {prompt}"
    )


@given(
    template=st.text(min_size=1),
    required_fields=st.lists(st.text(min_size=1))
)
def test_property_validate_prompt_without_variables(template, required_fields):
    """
    Property: Промпт без поля 'variables' должен быть невалидным
    
    Validates: Requirements 4.4
    """
    # Arrange
    mock_client = Mock()
    generator = SummaryGenerator(mock_client, config_path="config/prompts.json")
    
    # Убедимся, что 'template' есть в required_fields
    if 'template' not in required_fields:
        required_fields.append('template')
    
    prompt = {
        'template': template,
        'required_fields': required_fields
    }
    # Намеренно не добавляем 'variables'
    
    # Act
    result = generator.validate_prompt(prompt)
    
    # Assert
    assert result is False, (
        f"Промпт без поля 'variables' должен быть невалидным. "
        f"Промпт: {prompt}"
    )


@given(
    required_fields=st.lists(st.text(min_size=1), min_size=1),
    variables=st.lists(st.text())
)
def test_property_validate_prompt_with_empty_template(required_fields, variables):
    """
    Property: Промпт с пустым 'template' должен быть невалидным
    
    Validates: Requirements 4.4
    """
    # Arrange
    mock_client = Mock()
    generator = SummaryGenerator(mock_client, config_path="config/prompts.json")
    
    # Убедимся, что 'template' есть в required_fields
    if 'template' not in required_fields:
        required_fields.append('template')
    
    prompt = {
        'template': '',  # Пустая строка
        'required_fields': required_fields,
        'variables': variables
    }
    
    # Act
    result = generator.validate_prompt(prompt)
    
    # Assert
    assert result is False, (
        f"Промпт с пустым 'template' должен быть невалидным. "
        f"Промпт: {prompt}"
    )


@given(
    template=st.text(min_size=1),
    required_fields=st.lists(st.text(min_size=1)),
    variables=st.lists(st.text())
)
def test_property_validate_prompt_without_template_in_required_fields(
    template, required_fields, variables
):
    """
    Property: Промпт без 'template' в required_fields должен быть невалидным
    
    Validates: Requirements 4.4
    """
    # Arrange
    mock_client = Mock()
    generator = SummaryGenerator(mock_client, config_path="config/prompts.json")
    
    # Убедимся, что 'template' НЕТ в required_fields
    required_fields = [f for f in required_fields if f != 'template']
    assume(len(required_fields) > 0)  # Должен быть хотя бы один элемент
    
    prompt = {
        'template': template,
        'required_fields': required_fields,
        'variables': variables
    }
    
    # Act
    result = generator.validate_prompt(prompt)
    
    # Assert
    assert result is False, (
        f"Промпт без 'template' в required_fields должен быть невалидным. "
        f"Промпт: {prompt}"
    )


@given(
    template=st.integers() | st.floats() | st.booleans(),
    required_fields=st.lists(st.text(min_size=1), min_size=1),
    variables=st.lists(st.text())
)
def test_property_validate_prompt_with_non_string_template(
    template, required_fields, variables
):
    """
    Property: Промпт с не-строковым 'template' должен быть невалидным
    
    Validates: Requirements 4.4
    """
    # Arrange
    mock_client = Mock()
    generator = SummaryGenerator(mock_client, config_path="config/prompts.json")
    
    # Убедимся, что 'template' есть в required_fields
    if 'template' not in required_fields:
        required_fields.append('template')
    
    prompt = {
        'template': template,  # Не строка
        'required_fields': required_fields,
        'variables': variables
    }
    
    # Act
    result = generator.validate_prompt(prompt)
    
    # Assert
    assert result is False, (
        f"Промпт с не-строковым 'template' должен быть невалидным. "
        f"Промпт: {prompt}"
    )


@given(
    template=st.text(min_size=1),
    required_fields=st.text() | st.integers() | st.booleans(),
    variables=st.lists(st.text())
)
def test_property_validate_prompt_with_non_list_required_fields(
    template, required_fields, variables
):
    """
    Property: Промпт с не-списком 'required_fields' должен быть невалидным
    
    Validates: Requirements 4.4
    """
    # Arrange
    mock_client = Mock()
    generator = SummaryGenerator(mock_client, config_path="config/prompts.json")
    
    prompt = {
        'template': template,
        'required_fields': required_fields,  # Не список
        'variables': variables
    }
    
    # Act
    result = generator.validate_prompt(prompt)
    
    # Assert
    assert result is False, (
        f"Промпт с не-списком 'required_fields' должен быть невалидным. "
        f"Промпт: {prompt}"
    )


@given(
    template=st.text(min_size=1),
    required_fields=st.lists(st.text(min_size=1), min_size=1),
    variables=st.text() | st.integers() | st.booleans()
)
def test_property_validate_prompt_with_non_list_variables(
    template, required_fields, variables
):
    """
    Property: Промпт с не-списком 'variables' должен быть невалидным
    
    Validates: Requirements 4.4
    """
    # Arrange
    mock_client = Mock()
    generator = SummaryGenerator(mock_client, config_path="config/prompts.json")
    
    # Убедимся, что 'template' есть в required_fields
    if 'template' not in required_fields:
        required_fields.append('template')
    
    prompt = {
        'template': template,
        'required_fields': required_fields,
        'variables': variables  # Не список
    }
    
    # Act
    result = generator.validate_prompt(prompt)
    
    # Assert
    assert result is False, (
        f"Промпт с не-списком 'variables' должен быть невалидным. "
        f"Промпт: {prompt}"
    )


# Property 4: Форматирование сводок для Telegram
# For any сводки (негативной или позитивной), отформатированное сообщение 
# должно содержать заголовок соответствующего типа и полный текст сводки


@given(summary=st.text(min_size=1))
def test_property_format_negative_summary_contains_title_and_content(summary):
    """
    Property: Отформатированная негативная сводка должна содержать заголовок и полный текст
    
    Validates: Requirements 3.7, 5.3
    """
    # Arrange
    mock_client = Mock()
    generator = SummaryGenerator(mock_client, config_path="config/prompts.json")
    summary_type = 'negative'
    
    # Act
    formatted = generator.format_summary_for_telegram(summary, summary_type)
    
    # Assert
    assert 'НЕГАТИВНАЯ СВОДКА' in formatted, (
        f"Отформатированная негативная сводка должна содержать заголовок. "
        f"Результат: {formatted}"
    )
    assert summary in formatted, (
        f"Отформатированная сводка должна содержать полный исходный текст. "
        f"Исходный текст: {summary!r}, результат: {formatted}"
    )
    assert '⚠️' in formatted, (
        f"Отформатированная негативная сводка должна содержать эмодзи. "
        f"Результат: {formatted}"
    )


@given(summary=st.text(min_size=1))
def test_property_format_positive_summary_contains_title_and_content(summary):
    """
    Property: Отформатированная позитивная сводка должна содержать заголовок и полный текст
    
    Validates: Requirements 3.7, 5.3
    """
    # Arrange
    mock_client = Mock()
    generator = SummaryGenerator(mock_client, config_path="config/prompts.json")
    summary_type = 'positive'
    
    # Act
    formatted = generator.format_summary_for_telegram(summary, summary_type)
    
    # Assert
    assert 'ПОЗИТИВНАЯ СВОДКА' in formatted, (
        f"Отформатированная позитивная сводка должна содержать заголовок. "
        f"Результат: {formatted}"
    )
    assert summary in formatted, (
        f"Отформатированная сводка должна содержать полный исходный текст. "
        f"Исходный текст: {summary!r}, результат: {formatted}"
    )
    assert '✅' in formatted, (
        f"Отформатированная позитивная сводка должна содержать эмодзи. "
        f"Результат: {formatted}"
    )


@given(
    summary=st.text(min_size=1),
    summary_type=st.sampled_from(['negative', 'positive', 'NEGATIVE', 'POSITIVE', 'Negative', 'Positive'])
)
def test_property_format_summary_preserves_content_length(summary, summary_type):
    """
    Property: Форматирование не должно изменять длину исходного текста сводки
    
    Validates: Requirements 3.7, 5.3
    """
    # Arrange
    mock_client = Mock()
    generator = SummaryGenerator(mock_client, config_path="config/prompts.json")
    
    # Act
    formatted = generator.format_summary_for_telegram(summary, summary_type)
    
    # Assert
    assert summary in formatted, (
        f"Отформатированная сводка должна содержать полный исходный текст. "
        f"Исходный текст: {summary!r}, результат: {formatted}"
    )
    # Проверяем, что исходный текст присутствует полностью
    assert len(formatted) >= len(summary), (
        f"Длина отформатированной сводки должна быть не меньше исходной. "
        f"Исходная длина: {len(summary)}, результат: {len(formatted)}"
    )


@given(summary=st.text(min_size=1))
def test_property_format_unknown_type_uses_default_title(summary):
    """
    Property: Неизвестный тип сводки должен использовать заголовок по умолчанию
    
    Validates: Requirements 3.7, 5.3
    """
    # Arrange
    mock_client = Mock()
    generator = SummaryGenerator(mock_client, config_path="config/prompts.json")
    summary_type = 'unknown_type'
    
    # Act
    formatted = generator.format_summary_for_telegram(summary, summary_type)
    
    # Assert
    assert 'АНАЛИТИЧЕСКАЯ СВОДКА' in formatted, (
        f"Неизвестный тип должен использовать заголовок по умолчанию. "
        f"Результат: {formatted}"
    )
    assert summary in formatted, (
        f"Отформатированная сводка должна содержать полный исходный текст. "
        f"Исходный текст: {summary!r}, результат: {formatted}"
    )
    assert '📊' in formatted, (
        f"Неизвестный тип должен использовать эмодзи по умолчанию. "
        f"Результат: {formatted}"
    )

