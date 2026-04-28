# -*- coding: utf-8 -*-
"""Property-based тесты для FileManager"""

import os
import json
import csv
import tempfile
from pathlib import Path
from hypothesis import given, strategies as st, assume, settings
from hypothesis.strategies import composite
from src.notebooklm.file_manager import FileManager
from src.notebooklm.client import NotebookLMClient


# Стратегии для генерации тестовых данных

@composite
def valid_csv_content(draw):
    """Генерирует валидное содержимое CSV файла"""
    num_rows = draw(st.integers(min_value=1, max_value=20))
    num_cols = draw(st.integers(min_value=1, max_value=10))
    
    # Генерируем заголовки
    headers = [f"column_{i}" for i in range(num_cols)]
    
    # Генерируем строки данных
    rows = []
    for _ in range(num_rows):
        row = [
            draw(st.text(
                alphabet=st.characters(
                    blacklist_categories=('Cs', 'Cc'),
                    blacklist_characters='\n\r,'
                ),
                min_size=0,
                max_size=50
            ))
            for _ in range(num_cols)
        ]
        rows.append(row)
    
    return headers, rows


@composite
def valid_json_content(draw):
    """Генерирует валидное содержимое JSON файла"""
    # Генерируем простую JSON структуру
    num_items = draw(st.integers(min_value=1, max_value=20))
    
    items = []
    for _ in range(num_items):
        item = {
            "id": draw(st.integers(min_value=1, max_value=10000)),
            "name": draw(st.text(min_size=1, max_size=50)),
            "value": draw(st.one_of(
                st.integers(),
                st.floats(allow_nan=False, allow_infinity=False),
                st.text(max_size=100),
                st.booleans()
            ))
        }
        items.append(item)
    
    return items


@composite
def invalid_csv_content(draw):
    """Генерирует невалидное содержимое CSV файла"""
    # Генерируем строки с несовместимым количеством колонок
    num_rows = draw(st.integers(min_value=2, max_value=10))
    
    rows = []
    for i in range(num_rows):
        # Каждая строка имеет разное количество колонок
        num_cols = draw(st.integers(min_value=1, max_value=10))
        row = [f"value_{i}_{j}" for j in range(num_cols)]
        rows.append(row)
    
    return rows


# Property 1: Валидация формата файлов
# For any файла с расширением .csv или .json и валидной структурой данных,
# метод FileManager.validate_file_format() должен возвращать True

@given(csv_data=valid_csv_content())
@settings(max_examples=50, deadline=None)
def test_property_validate_csv_format(csv_data):
    """
    Property Test: Валидация CSV формата
    
    Property: For any валидного CSV файла с корректной структурой,
    validate_file_format() должен возвращать True
    """
    headers, rows = csv_data
    
    # Создаем временный CSV файл
    with tempfile.NamedTemporaryFile(
        mode='w',
        suffix='.csv',
        delete=False,
        encoding='utf-8',
        newline=''
    ) as f:
        temp_file = f.name
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(rows)
    
    try:
        # Создаем mock клиента (не используется в validate_file_format)
        mock_client = None
        file_manager = FileManager(mock_client)
        
        # Property: валидный CSV файл должен пройти валидацию
        result = file_manager.validate_file_format(temp_file)
        assert result is True, f"Валидный CSV файл не прошел валидацию: {temp_file}"
        
    finally:
        # Очистка
        if os.path.exists(temp_file):
            os.remove(temp_file)


@given(json_data=valid_json_content())
@settings(max_examples=50, deadline=None)
def test_property_validate_json_format(json_data):
    """
    Property Test: Валидация JSON формата
    
    Property: For any валидного JSON файла с корректной структурой,
    validate_file_format() должен возвращать True
    """
    # Создаем временный JSON файл
    with tempfile.NamedTemporaryFile(
        mode='w',
        suffix='.json',
        delete=False,
        encoding='utf-8'
    ) as f:
        temp_file = f.name
        json.dump(json_data, f, ensure_ascii=False, indent=2)
    
    try:
        # Создаем mock клиента (не используется в validate_file_format)
        mock_client = None
        file_manager = FileManager(mock_client)
        
        # Property: валидный JSON файл должен пройти валидацию
        result = file_manager.validate_file_format(temp_file)
        assert result is True, f"Валидный JSON файл не прошел валидацию: {temp_file}"
        
    finally:
        # Очистка
        if os.path.exists(temp_file):
            os.remove(temp_file)


@given(extension=st.sampled_from(['.txt', '.xml', '.pdf', '.doc', '.xlsx', '.py']))
@settings(max_examples=20, deadline=None)
def test_property_reject_unsupported_formats(extension):
    """
    Property Test: Отклонение неподдерживаемых форматов
    
    Property: For any файла с неподдерживаемым расширением,
    validate_file_format() должен возвращать False
    """
    # Создаем временный файл с неподдерживаемым расширением
    with tempfile.NamedTemporaryFile(
        mode='w',
        suffix=extension,
        delete=False,
        encoding='utf-8'
    ) as f:
        temp_file = f.name
        f.write("some content")
    
    try:
        # Создаем mock клиента
        mock_client = None
        file_manager = FileManager(mock_client)
        
        # Property: файл с неподдерживаемым расширением должен быть отклонен
        result = file_manager.validate_file_format(temp_file)
        assert result is False, (
            f"Файл с неподдерживаемым расширением {extension} "
            f"не был отклонен: {temp_file}"
        )
        
    finally:
        # Очистка
        if os.path.exists(temp_file):
            os.remove(temp_file)


@given(st.text(min_size=1, max_size=100))
@settings(max_examples=30, deadline=None)
def test_property_reject_nonexistent_files(filename):
    """
    Property Test: Отклонение несуществующих файлов
    
    Property: For any несуществующего файла,
    validate_file_format() должен возвращать False
    """
    # Убеждаемся, что файл не существует
    assume(not os.path.exists(filename))
    
    # Создаем mock клиента
    mock_client = None
    file_manager = FileManager(mock_client)
    
    # Property: несуществующий файл должен быть отклонен
    result = file_manager.validate_file_format(filename)
    assert result is False, f"Несуществующий файл не был отклонен: {filename}"


# Property 2: Очистка временных файлов
# For any списка путей к временным файлам, после вызова
# FileManager.cleanup_temp_files() все указанные файлы должны быть
# удалены из файловой системы

@given(
    num_files=st.integers(min_value=1, max_value=10),
    file_content=st.text(max_size=1000)
)
@settings(max_examples=30, deadline=None)
def test_property_cleanup_temp_files(num_files, file_content):
    """
    Property Test: Очистка временных файлов
    
    Property: For any списка временных файлов, после вызова cleanup_temp_files()
    все файлы должны быть удалены из файловой системы
    """
    # Создаем временные файлы
    temp_files = []
    for i in range(num_files):
        with tempfile.NamedTemporaryFile(
            mode='w',
            delete=False,
            encoding='utf-8',
            suffix=f'_test_{i}.tmp'
        ) as f:
            f.write(file_content)
            temp_files.append(f.name)
    
    try:
        # Проверяем, что все файлы существуют
        for temp_file in temp_files:
            assert os.path.exists(temp_file), f"Файл не был создан: {temp_file}"
        
        # Создаем mock клиента
        mock_client = None
        file_manager = FileManager(mock_client)
        
        # Вызываем cleanup_temp_files
        file_manager.cleanup_temp_files(temp_files)
        
        # Property: все файлы должны быть удалены
        for temp_file in temp_files:
            assert not os.path.exists(temp_file), (
                f"Файл не был удален после cleanup_temp_files: {temp_file}"
            )
            
    finally:
        # Дополнительная очистка на случай ошибки теста
        for temp_file in temp_files:
            if os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                except:
                    pass


@given(num_files=st.integers(min_value=0, max_value=5))
@settings(max_examples=20, deadline=None)
def test_property_cleanup_empty_or_nonexistent_files(num_files):
    """
    Property Test: Очистка пустого списка или несуществующих файлов
    
    Property: cleanup_temp_files() должен корректно обрабатывать
    пустые списки и несуществующие файлы без ошибок
    """
    # Генерируем список несуществующих файлов
    nonexistent_files = [f"/tmp/nonexistent_file_{i}.tmp" for i in range(num_files)]
    
    # Убеждаемся, что файлы не существуют
    for file_path in nonexistent_files:
        assume(not os.path.exists(file_path))
    
    # Создаем mock клиента
    mock_client = None
    file_manager = FileManager(mock_client)
    
    # Property: cleanup_temp_files не должен вызывать ошибок
    # для несуществующих файлов
    try:
        file_manager.cleanup_temp_files(nonexistent_files)
        # Если дошли сюда без исключений - тест пройден
        assert True
    except Exception as e:
        assert False, f"cleanup_temp_files вызвал исключение для несуществующих файлов: {e}"


@given(
    num_existing=st.integers(min_value=1, max_value=5),
    num_nonexistent=st.integers(min_value=1, max_value=5)
)
@settings(max_examples=20, deadline=None)
def test_property_cleanup_mixed_files(num_existing, num_nonexistent):
    """
    Property Test: Очистка смешанного списка файлов
    
    Property: cleanup_temp_files() должен удалить существующие файлы
    и корректно обработать несуществующие без ошибок
    """
    # Создаем существующие файлы
    existing_files = []
    for i in range(num_existing):
        with tempfile.NamedTemporaryFile(
            mode='w',
            delete=False,
            suffix=f'_existing_{i}.tmp'
        ) as f:
            f.write("test content")
            existing_files.append(f.name)
    
    # Генерируем несуществующие файлы
    nonexistent_files = [
        f"/tmp/nonexistent_mixed_{i}.tmp" 
        for i in range(num_nonexistent)
    ]
    
    # Убеждаемся, что несуществующие файлы действительно не существуют
    for file_path in nonexistent_files:
        assume(not os.path.exists(file_path))
    
    # Смешиваем списки
    mixed_files = existing_files + nonexistent_files
    
    try:
        # Создаем mock клиента
        mock_client = None
        file_manager = FileManager(mock_client)
        
        # Вызываем cleanup_temp_files
        file_manager.cleanup_temp_files(mixed_files)
        
        # Property: существующие файлы должны быть удалены
        for existing_file in existing_files:
            assert not os.path.exists(existing_file), (
                f"Существующий файл не был удален: {existing_file}"
            )
        
        # Property: несуществующие файлы не должны вызывать ошибок
        # (проверяется отсутствием исключений)
        
    finally:
        # Дополнительная очистка
        for existing_file in existing_files:
            if os.path.exists(existing_file):
                try:
                    os.remove(existing_file)
                except:
                    pass
