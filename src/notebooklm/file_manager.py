# -*- coding: utf-8 -*-
"""Менеджер для управления файлами и ноутбуками NotebookLM"""

import os
import json
import csv
from pathlib import Path
from typing import Tuple, List, Optional
from src.notebooklm.client import NotebookLMClient, NotebookLMAPIError
from src.utils.logger import setup_logger

logger = setup_logger(__name__)


class FileManager:
    """Менеджер для управления файлами и ноутбуками"""
    
    def __init__(
        self, 
        notebooklm_client: NotebookLMClient,
        export_dir: str = "exports"
    ):
        """
        Инициализация менеджера
        
        Args:
            notebooklm_client: Клиент NotebookLM
            export_dir: Директория для экспортированных файлов
        """
        self.client = notebooklm_client
        self.export_dir = export_dir
        logger.info(f"FileManager инициализирован с директорией экспорта: {export_dir}")
    
    def validate_file_format(self, file_path: str) -> bool:
        """
        Валидирует формат файла (CSV или JSON)
        
        Args:
            file_path: Путь к файлу
        
        Returns:
            True если формат поддерживается, False иначе
        """
        if not os.path.exists(file_path):
            logger.warning(f"Файл не существует: {file_path}")
            return False
        
        file_extension = Path(file_path).suffix.lower()
        
        # Проверка расширения
        if file_extension not in ['.csv', '.json']:
            logger.warning(f"Неподдерживаемое расширение файла: {file_extension}")
            return False
        
        try:
            # Валидация CSV
            if file_extension == '.csv':
                with open(file_path, 'r', encoding='utf-8') as f:
                    csv_reader = csv.reader(f)
                    # Проверяем, что можем прочитать хотя бы первую строку
                    next(csv_reader, None)
                logger.info(f"CSV файл валиден: {file_path}")
                return True
            
            # Валидация JSON
            elif file_extension == '.json':
                with open(file_path, 'r', encoding='utf-8') as f:
                    json.load(f)
                logger.info(f"JSON файл валиден: {file_path}")
                return True
                
        except csv.Error as e:
            logger.error(f"Ошибка валидации CSV файла {file_path}: {str(e)}")
            return False
        except json.JSONDecodeError as e:
            logger.error(f"Ошибка валидации JSON файла {file_path}: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Ошибка валидации файла {file_path}: {str(e)}")
            return False
        
        return False
    
    async def create_notebook_with_source(
        self, 
        file_path: str, 
        notebook_title: str
    ) -> Tuple[str, str]:
        """
        Создает ноутбук и добавляет файл как источник
        
        Args:
            file_path: Путь к файлу с данными
            notebook_title: Название ноутбука
        
        Returns:
            Кортеж (notebook_id, source_id)
        
        Raises:
            FileNotFoundError: Если файл не найден
            NotebookLMAPIError: При ошибке API
        """
        # Проверка существования файла
        if not os.path.exists(file_path):
            error_msg = f"Файл не найден: {file_path}"
            logger.error(error_msg)
            raise FileNotFoundError(error_msg)
        
        # Валидация формата файла
        if not self.validate_file_format(file_path):
            error_msg = f"Невалидный формат файла: {file_path}"
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        # Определение типа файла
        file_extension = Path(file_path).suffix.lower()
        file_type = file_extension[1:]  # Убираем точку
        
        logger.info(
            f"Создание ноутбука '{notebook_title}' с источником {file_type}: {file_path}"
        )
        
        # Создание ноутбука
        notebook_id = await self.client.create_notebook(notebook_title)
        
        try:
            # Добавление источника
            source_id = await self.client.add_source(
                notebook_id=notebook_id,
                file_path=file_path,
                file_type=file_type
            )
            
            logger.info(
                f"Ноутбук '{notebook_title}' создан с источником. "
                f"Notebook ID: {notebook_id}, Source ID: {source_id}"
            )
            
            return (notebook_id, source_id)
            
        except Exception as e:
            # При ошибке добавления источника пытаемся удалить созданный ноутбук
            logger.error(
                f"Ошибка добавления источника в ноутбук {notebook_id}. "
                f"Попытка очистки ноутбука..."
            )
            await self.cleanup_notebook(notebook_id)
            raise
    
    async def cleanup_notebook(self, notebook_id: str) -> None:
        """
        Удаляет ноутбук с обработкой ошибок (graceful degradation)
        
        Args:
            notebook_id: ID ноутбука для удаления
        
        Note:
            При ошибке удаления логирует предупреждение и продолжает работу
        """
        if not notebook_id:
            logger.warning("Пустой notebook_id, пропуск очистки")
            return
        
        logger.info(f"Очистка ноутбука {notebook_id}...")
        
        try:
            success = await self.client.delete_notebook(notebook_id)
            
            if success:
                logger.info(f"Ноутбук {notebook_id} успешно удален")
            else:
                logger.warning(
                    f"Не удалось удалить ноутбук {notebook_id}. "
                    f"Возможно, потребуется ручная очистка."
                )
                
        except Exception as e:
            logger.warning(
                f"Ошибка при удалении ноутбука {notebook_id}: {str(e)}. "
                f"Продолжаем работу. Возможно, потребуется ручная очистка."
            )
    
    def cleanup_temp_files(self, file_paths: List[str]) -> None:
        """
        Удаляет временные файлы из локального кеша
        
        Args:
            file_paths: Список путей к файлам для удаления
        """
        if not file_paths:
            logger.info("Нет временных файлов для удаления")
            return
        
        logger.info(f"Очистка {len(file_paths)} временных файлов...")
        
        for file_path in file_paths:
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
                    logger.info(f"Временный файл удален: {file_path}")
                else:
                    logger.warning(f"Файл не найден для удаления: {file_path}")
                    
            except PermissionError as e:
                logger.warning(
                    f"Нет прав для удаления файла {file_path}: {str(e)}. "
                    f"Возможно, файл используется другим процессом."
                )
            except Exception as e:
                logger.warning(
                    f"Ошибка при удалении файла {file_path}: {str(e)}. "
                    f"Продолжаем работу."
                )
        
        logger.info("Очистка временных файлов завершена")
