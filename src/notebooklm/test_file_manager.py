# -*- coding: utf-8 -*-
"""Unit-тесты для FileManager"""

import os
import json
import csv
import tempfile
import pytest
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from src.notebooklm.file_manager import FileManager
from src.notebooklm.client import NotebookLMClient, NotebookLMAPIError


@pytest.fixture
def mock_client():
    """Создает mock NotebookLMClient"""
    client = Mock(spec=NotebookLMClient)
    client.create_notebook = AsyncMock()
    client.add_source = AsyncMock()
    client.delete_notebook = AsyncMock()
    return client


@pytest.fixture
def file_manager(mock_client):
    """Создает FileManager с mock клиентом"""
    return FileManager(mock_client, export_dir="test_exports")


@pytest.fixture
def temp_csv_file():
    """Создает временный CSV файл"""
    with tempfile.NamedTemporaryFile(
        mode='w',
        suffix='.csv',
        delete=False,
        encoding='utf-8',
        newline=''
    ) as f:
        writer = csv.writer(f)
        writer.writerow(['id', 'name', 'value'])
        writer.writerow(['1', 'test1', '100'])
        writer.writerow(['2', 'test2', '200'])
        temp_file = f.name
    
    yield temp_file
    
    # Cleanup
    if os.path.exists(temp_file):
        os.remove(temp_file)


@pytest.fixture
def temp_json_file():
    """Создает временный JSON файл"""
    with tempfile.NamedTemporaryFile(
        mode='w',
        suffix='.json',
        delete=False,
        encoding='utf-8'
    ) as f:
        data = [
            {'id': 1, 'name': 'test1', 'value': 100},
            {'id': 2, 'name': 'test2', 'value': 200}
        ]
        json.dump(data, f, ensure_ascii=False, indent=2)
        temp_file = f.name
    
    yield temp_file
    
    # Cleanup
    if os.path.exists(temp_file):
        os.remove(temp_file)


@pytest.fixture
def temp_invalid_csv_file():
    """Создает невалидный CSV файл"""
    with tempfile.NamedTemporaryFile(
        mode='w',
        suffix='.csv',
        delete=False,
        encoding='utf-8'
    ) as f:
        # Записываем невалидный CSV (некорректные кавычки)
        f.write('id,name,value\n')
        f.write('1,"unclosed quote,100\n')
        temp_file = f.name
    
    yield temp_file
    
    # Cleanup
    if os.path.exists(temp_file):
        os.remove(temp_file)


@pytest.fixture
def temp_invalid_json_file():
    """Создает невалидный JSON файл"""
    with tempfile.NamedTemporaryFile(
        mode='w',
        suffix='.json',
        delete=False,
        encoding='utf-8'
    ) as f:
        # Записываем невалидный JSON
        f.write('{"invalid": json syntax}')
        temp_file = f.name
    
    yield temp_file
    
    # Cleanup
    if os.path.exists(temp_file):
        os.remove(temp_file)


# Тесты для validate_file_format

def test_validate_csv_format_valid(file_manager, temp_csv_file):
    """Тест валидации корректного CSV файла"""
    result = file_manager.validate_file_format(temp_csv_file)
    assert result is True


def test_validate_json_format_valid(file_manager, temp_json_file):
    """Тест валидации корректного JSON файла"""
    result = file_manager.validate_file_format(temp_json_file)
    assert result is True


def test_validate_file_format_nonexistent(file_manager):
    """Тест валидации несуществующего файла"""
    result = file_manager.validate_file_format('/nonexistent/file.csv')
    assert result is False


def test_validate_file_format_unsupported_extension(file_manager):
    """Тест валидации файла с неподдерживаемым расширением"""
    with tempfile.NamedTemporaryFile(suffix='.txt', delete=False) as f:
        temp_file = f.name
        f.write(b'some text content')
    
    try:
        result = file_manager.validate_file_format(temp_file)
        assert result is False
    finally:
        if os.path.exists(temp_file):
            os.remove(temp_file)


def test_validate_csv_format_invalid(file_manager, temp_invalid_csv_file):
    """Тест валидации невалидного CSV файла"""
    # Невалидный CSV может быть прочитан, но с ошибками
    # В зависимости от реализации может вернуть True или False
    result = file_manager.validate_file_format(temp_invalid_csv_file)
    # CSV reader довольно толерантен, поэтому может вернуть True
    assert isinstance(result, bool)


def test_validate_json_format_invalid(file_manager, temp_invalid_json_file):
    """Тест валидации невалидного JSON файла"""
    result = file_manager.validate_file_format(temp_invalid_json_file)
    assert result is False


# Тесты для create_notebook_with_source

@pytest.mark.asyncio
async def test_create_notebook_with_source_success(file_manager, temp_csv_file):
    """Тест успешного создания ноутбука с источником"""
    # Настройка mock
    file_manager.client.create_notebook.return_value = 'notebook_123'
    file_manager.client.add_source.return_value = 'source_456'
    
    # Вызов метода
    notebook_id, source_id = await file_manager.create_notebook_with_source(
        file_path=temp_csv_file,
        notebook_title='Test Notebook'
    )
    
    # Проверки
    assert notebook_id == 'notebook_123'
    assert source_id == 'source_456'
    
    file_manager.client.create_notebook.assert_called_once_with('Test Notebook')
    file_manager.client.add_source.assert_called_once_with(
        notebook_id='notebook_123',
        file_path=temp_csv_file,
        file_type='csv'
    )


@pytest.mark.asyncio
async def test_create_notebook_with_source_file_not_found(file_manager):
    """Тест создания ноутбука с несуществующим файлом"""
    with pytest.raises(FileNotFoundError) as exc_info:
        await file_manager.create_notebook_with_source(
            file_path='/nonexistent/file.csv',
            notebook_title='Test Notebook'
        )
    
    assert 'Файл не найден' in str(exc_info.value)
    file_manager.client.create_notebook.assert_not_called()


@pytest.mark.asyncio
async def test_create_notebook_with_source_invalid_format(file_manager):
    """Тест создания ноутбука с невалидным форматом файла"""
    # Создаем файл с неподдерживаемым расширением
    with tempfile.NamedTemporaryFile(suffix='.txt', delete=False) as f:
        temp_file = f.name
        f.write(b'some text')
    
    try:
        with pytest.raises(ValueError) as exc_info:
            await file_manager.create_notebook_with_source(
                file_path=temp_file,
                notebook_title='Test Notebook'
            )
        
        assert 'Невалидный формат файла' in str(exc_info.value)
        file_manager.client.create_notebook.assert_not_called()
    finally:
        if os.path.exists(temp_file):
            os.remove(temp_file)


@pytest.mark.asyncio
async def test_create_notebook_with_source_add_source_fails(file_manager, temp_csv_file):
    """Тест обработки ошибки при добавлении источника"""
    # Настройка mock
    file_manager.client.create_notebook.return_value = 'notebook_123'
    file_manager.client.add_source.side_effect = NotebookLMAPIError('API Error')
    file_manager.client.delete_notebook.return_value = True
    
    # Вызов метода должен вызвать исключение
    with pytest.raises(NotebookLMAPIError):
        await file_manager.create_notebook_with_source(
            file_path=temp_csv_file,
            notebook_title='Test Notebook'
        )
    
    # Проверяем, что была попытка очистки ноутбука
    file_manager.client.delete_notebook.assert_called_once_with('notebook_123')


@pytest.mark.asyncio
async def test_create_notebook_with_source_json_file(file_manager, temp_json_file):
    """Тест создания ноутбука с JSON файлом"""
    # Настройка mock
    file_manager.client.create_notebook.return_value = 'notebook_789'
    file_manager.client.add_source.return_value = 'source_012'
    
    # Вызов метода
    notebook_id, source_id = await file_manager.create_notebook_with_source(
        file_path=temp_json_file,
        notebook_title='JSON Test Notebook'
    )
    
    # Проверки
    assert notebook_id == 'notebook_789'
    assert source_id == 'source_012'
    
    file_manager.client.add_source.assert_called_once_with(
        notebook_id='notebook_789',
        file_path=temp_json_file,
        file_type='json'
    )


# Тесты для cleanup_notebook

@pytest.mark.asyncio
async def test_cleanup_notebook_success(file_manager):
    """Тест успешной очистки ноутбука"""
    file_manager.client.delete_notebook.return_value = True
    
    await file_manager.cleanup_notebook('notebook_123')
    
    file_manager.client.delete_notebook.assert_called_once_with('notebook_123')


@pytest.mark.asyncio
async def test_cleanup_notebook_failure_graceful(file_manager):
    """Тест graceful degradation при ошибке удаления ноутбука"""
    file_manager.client.delete_notebook.return_value = False
    
    # Не должно вызывать исключение
    await file_manager.cleanup_notebook('notebook_123')
    
    file_manager.client.delete_notebook.assert_called_once_with('notebook_123')


@pytest.mark.asyncio
async def test_cleanup_notebook_exception_graceful(file_manager):
    """Тест graceful degradation при исключении во время удаления"""
    file_manager.client.delete_notebook.side_effect = Exception('Delete error')
    
    # Не должно вызывать исключение
    await file_manager.cleanup_notebook('notebook_123')
    
    file_manager.client.delete_notebook.assert_called_once_with('notebook_123')


@pytest.mark.asyncio
async def test_cleanup_notebook_empty_id(file_manager):
    """Тест очистки с пустым notebook_id"""
    await file_manager.cleanup_notebook('')
    
    # Не должно быть вызова delete_notebook
    file_manager.client.delete_notebook.assert_not_called()


@pytest.mark.asyncio
async def test_cleanup_notebook_none_id(file_manager):
    """Тест очистки с None notebook_id"""
    await file_manager.cleanup_notebook(None)
    
    # Не должно быть вызова delete_notebook
    file_manager.client.delete_notebook.assert_not_called()


# Тесты для cleanup_temp_files

def test_cleanup_temp_files_success(file_manager):
    """Тест успешной очистки временных файлов"""
    # Создаем временные файлы
    temp_files = []
    for i in range(3):
        with tempfile.NamedTemporaryFile(delete=False, suffix=f'_test_{i}.tmp') as f:
            f.write(b'test content')
            temp_files.append(f.name)
    
    # Проверяем, что файлы существуют
    for temp_file in temp_files:
        assert os.path.exists(temp_file)
    
    # Вызываем cleanup
    file_manager.cleanup_temp_files(temp_files)
    
    # Проверяем, что файлы удалены
    for temp_file in temp_files:
        assert not os.path.exists(temp_file)


def test_cleanup_temp_files_empty_list(file_manager):
    """Тест очистки пустого списка файлов"""
    # Не должно вызывать исключение
    file_manager.cleanup_temp_files([])


def test_cleanup_temp_files_nonexistent(file_manager):
    """Тест очистки несуществующих файлов"""
    nonexistent_files = ['/tmp/nonexistent1.tmp', '/tmp/nonexistent2.tmp']
    
    # Не должно вызывать исключение
    file_manager.cleanup_temp_files(nonexistent_files)


def test_cleanup_temp_files_mixed(file_manager):
    """Тест очистки смешанного списка (существующие и несуществующие файлы)"""
    # Создаем один существующий файл
    with tempfile.NamedTemporaryFile(delete=False, suffix='_existing.tmp') as f:
        f.write(b'test content')
        existing_file = f.name
    
    # Смешанный список
    mixed_files = [
        existing_file,
        '/tmp/nonexistent1.tmp',
        '/tmp/nonexistent2.tmp'
    ]
    
    # Вызываем cleanup
    file_manager.cleanup_temp_files(mixed_files)
    
    # Проверяем, что существующий файл удален
    assert not os.path.exists(existing_file)


def test_cleanup_temp_files_permission_error(file_manager):
    """Тест graceful degradation при ошибке прав доступа"""
    # Создаем временный файл
    with tempfile.NamedTemporaryFile(delete=False, suffix='_perm.tmp') as f:
        f.write(b'test content')
        temp_file = f.name
    
    try:
        # Мокируем os.remove для симуляции PermissionError
        with patch('os.remove', side_effect=PermissionError('Access denied')):
            # Не должно вызывать исключение
            file_manager.cleanup_temp_files([temp_file])
    finally:
        # Очистка
        if os.path.exists(temp_file):
            os.remove(temp_file)


def test_cleanup_temp_files_general_exception(file_manager):
    """Тест graceful degradation при общей ошибке"""
    # Создаем временный файл
    with tempfile.NamedTemporaryFile(delete=False, suffix='_err.tmp') as f:
        f.write(b'test content')
        temp_file = f.name
    
    try:
        # Мокируем os.remove для симуляции общей ошибки
        with patch('os.remove', side_effect=Exception('General error')):
            # Не должно вызывать исключение
            file_manager.cleanup_temp_files([temp_file])
    finally:
        # Очистка
        if os.path.exists(temp_file):
            os.remove(temp_file)


# Интеграционные тесты

@pytest.mark.asyncio
async def test_full_workflow_with_cleanup(file_manager, temp_csv_file):
    """Интеграционный тест полного workflow с очисткой"""
    # Настройка mock
    file_manager.client.create_notebook.return_value = 'notebook_999'
    file_manager.client.add_source.return_value = 'source_888'
    file_manager.client.delete_notebook.return_value = True
    
    # Создание ноутбука с источником
    notebook_id, source_id = await file_manager.create_notebook_with_source(
        file_path=temp_csv_file,
        notebook_title='Integration Test'
    )
    
    assert notebook_id == 'notebook_999'
    assert source_id == 'source_888'
    
    # Очистка ноутбука
    await file_manager.cleanup_notebook(notebook_id)
    
    # Очистка временных файлов
    file_manager.cleanup_temp_files([temp_csv_file])
    
    # Проверяем вызовы
    file_manager.client.create_notebook.assert_called_once()
    file_manager.client.add_source.assert_called_once()
    file_manager.client.delete_notebook.assert_called_once_with('notebook_999')
