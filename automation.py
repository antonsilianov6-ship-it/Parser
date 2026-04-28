# -*- coding: utf-8 -*-
"""
NotebookLM Telegram Automation - Точка входа
Автоматизация создания аналитических сводок через NotebookLM с отправкой в Telegram
"""
import os
import sys
import asyncio
import argparse
import signal
from datetime import datetime, timedelta
from typing import Optional, Tuple

# Добавляем путь к корневой директории проекта
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.automation.orchestrator import AutomationOrchestrator, AutomationError
from src.config import validate_config

# Глобальная переменная для graceful shutdown
shutdown_requested = False
orchestrator: Optional[AutomationOrchestrator] = None
logger = None  # Инициализируется в main()


def setup_directories():
    """Создает необходимые директории для работы приложения"""
    dirs = ['logs', 'sessions', 'cache', 'exports', 'data', 'config']
    for directory in dirs:
        os.makedirs(directory, exist_ok=True)


def signal_handler(signum, frame):
    """
    Обработчик сигналов для graceful shutdown
    
    Args:
        signum: Номер сигнала
        frame: Текущий stack frame
    """
    global shutdown_requested, logger
    
    signal_name = 'SIGINT' if signum == signal.SIGINT else 'SIGTERM'
    
    if logger:
        logger.info(f"\n{'=' * 60}")
        logger.info(f"Получен сигнал {signal_name}. Инициирование graceful shutdown...")
        logger.info(f"{'=' * 60}")
    else:
        print(f"\n{'=' * 60}")
        print(f"Получен сигнал {signal_name}. Инициирование graceful shutdown...")
        print(f"{'=' * 60}")
    
    shutdown_requested = True
    
    # Если оркестратор инициализирован, запускаем очистку ресурсов
    if orchestrator:
        if logger:
            logger.info("Очистка ресурсов перед завершением...")
        else:
            print("Очистка ресурсов перед завершением...")
        try:
            # Создаем новый event loop для синхронного вызова
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(orchestrator.cleanup_resources())
            loop.close()
            if logger:
                logger.info("✓ Ресурсы очищены")
            else:
                print("✓ Ресурсы очищены")
        except Exception as e:
            if logger:
                logger.error(f"Ошибка при очистке ресурсов: {str(e)}")
            else:
                print(f"Ошибка при очистке ресурсов: {str(e)}")
    
    if logger:
        logger.info("Завершение работы...")
    else:
        print("Завершение работы...")
    sys.exit(0)


def setup_signal_handlers():
    """Настраивает обработчики сигналов для graceful shutdown"""
    signal.signal(signal.SIGINT, signal_handler)
    
    # SIGTERM доступен только на Unix-подобных системах
    if hasattr(signal, 'SIGTERM'):
        signal.signal(signal.SIGTERM, signal_handler)
    
    # Логирование только если logger инициализирован
    if logger:
        logger.info("✓ Обработчики сигналов настроены (SIGINT, SIGTERM)")


def parse_arguments() -> argparse.Namespace:
    """
    Парсинг аргументов командной строки
    
    Returns:
        Объект с аргументами командной строки
    """
    parser = argparse.ArgumentParser(
        description='NotebookLM Telegram Automation - Автоматизация аналитических сводок',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры использования:

  Режим manual (ручной запуск с указанием дат):
    %(prog)s --mode manual --start-date 2024-04-20 --end-date 2024-04-21
    %(prog)s --mode manual --days 7  # Последние 7 дней
    %(prog)s --mode manual --yesterday  # Вчерашний день
    
  Режим scheduled (автоматический запуск по расписанию):
    %(prog)s --mode scheduled
    %(prog)s  # По умолчанию используется scheduled режим
    
  Дополнительные опции:
    %(prog)s --mode manual --yesterday --verbose  # Подробные логи
    %(prog)s --mode scheduled --config custom_config.json  # Кастомная конфигурация

Логика расписания (scheduled режим):
  - Понедельник: анализ пятницы-воскресенья (последние 3 дня)
  - Вторник-пятница: анализ предыдущего дня
  - Суббота-воскресенье: автоматизация не запускается
        """
    )
    
    # Основные аргументы
    parser.add_argument(
        '--mode',
        choices=['manual', 'scheduled'],
        default='scheduled',
        help='Режим работы: manual (ручной с указанием дат) или scheduled (автоматический по расписанию). По умолчанию: scheduled'
    )
    
    parser.add_argument(
        '--config',
        type=str,
        default='config.json',
        help='Путь к файлу конфигурации. По умолчанию: config.json'
    )
    
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Подробный вывод логов (уровень DEBUG)'
    )
    
    # Аргументы для manual режима
    manual_group = parser.add_argument_group('Аргументы для manual режима')
    
    manual_group.add_argument(
        '--start-date',
        type=str,
        help='Начальная дата для анализа в формате YYYY-MM-DD (например: 2024-04-20)'
    )
    
    manual_group.add_argument(
        '--end-date',
        type=str,
        help='Конечная дата для анализа в формате YYYY-MM-DD (например: 2024-04-21)'
    )
    
    manual_group.add_argument(
        '--days',
        type=int,
        help='Количество последних дней для анализа (например: 7 для последней недели)'
    )
    
    manual_group.add_argument(
        '--yesterday',
        action='store_true',
        help='Анализировать только вчерашний день'
    )
    
    return parser.parse_args()


def parse_date(date_str: str) -> datetime:
    """
    Парсит строку даты в объект datetime
    
    Args:
        date_str: Строка даты в формате YYYY-MM-DD
    
    Returns:
        Объект datetime
    
    Raises:
        ValueError: При невалидном формате даты
    """
    try:
        return datetime.strptime(date_str, '%Y-%m-%d')
    except ValueError:
        raise ValueError(
            f"Невалидный формат даты: {date_str}. "
            f"Ожидается формат YYYY-MM-DD (например: 2024-04-20)"
        )


def get_date_range_from_args(args: argparse.Namespace) -> Optional[Tuple[datetime, datetime]]:
    """
    Определяет диапазон дат на основе аргументов командной строки
    
    Args:
        args: Аргументы командной строки
    
    Returns:
        Кортеж (start_date, end_date) или None для scheduled режима
    
    Raises:
        ValueError: При невалидных аргументах
    """
    if args.mode == 'scheduled':
        # В scheduled режиме диапазон дат определяется автоматически
        return None
    
    # Manual режим - требуется указание дат
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    
    if args.yesterday:
        # Вчерашний день
        start_date = today - timedelta(days=1)
        end_date = today - timedelta(days=1)
        end_date = end_date.replace(hour=23, minute=59, second=59, microsecond=999999)
        logger.info(f"Режим: вчерашний день ({start_date.strftime('%Y-%m-%d')})")
        return (start_date, end_date)
    
    if args.days:
        # Последние N дней
        if args.days <= 0:
            raise ValueError("Количество дней должно быть положительным числом")
        
        start_date = today - timedelta(days=args.days)
        end_date = today - timedelta(days=1)
        end_date = end_date.replace(hour=23, minute=59, second=59, microsecond=999999)
        logger.info(
            f"Режим: последние {args.days} дней "
            f"({start_date.strftime('%Y-%m-%d')} - {end_date.strftime('%Y-%m-%d')})"
        )
        return (start_date, end_date)
    
    if args.start_date and args.end_date:
        # Указанный диапазон дат
        start_date = parse_date(args.start_date)
        end_date = parse_date(args.end_date)
        
        if start_date > end_date:
            raise ValueError("Начальная дата не может быть позже конечной даты")
        
        if end_date > today:
            raise ValueError("Конечная дата не может быть в будущем")
        
        end_date = end_date.replace(hour=23, minute=59, second=59, microsecond=999999)
        logger.info(
            f"Режим: указанный диапазон "
            f"({start_date.strftime('%Y-%m-%d')} - {end_date.strftime('%Y-%m-%d')})"
        )
        return (start_date, end_date)
    
    if args.start_date or args.end_date:
        raise ValueError(
            "Необходимо указать обе даты: --start-date и --end-date, "
            "или использовать --days / --yesterday"
        )
    
    # Если ничего не указано в manual режиме - используем вчерашний день по умолчанию
    logger.warning(
        "В manual режиме не указаны даты. "
        "Используется вчерашний день по умолчанию"
    )
    start_date = today - timedelta(days=1)
    end_date = today - timedelta(days=1)
    end_date = end_date.replace(hour=23, minute=59, second=59, microsecond=999999)
    return (start_date, end_date)


async def run_manual_mode(
    orchestrator: AutomationOrchestrator,
    date_range: Tuple[datetime, datetime]
) -> bool:
    """
    Запускает автоматизацию в ручном режиме
    
    Args:
        orchestrator: Экземпляр AutomationOrchestrator
        date_range: Диапазон дат для анализа
    
    Returns:
        True если выполнение успешно, False иначе
    """
    global shutdown_requested
    
    logger.info("=" * 60)
    logger.info("=== РЕЖИМ: MANUAL (ручной запуск) ===")
    logger.info("=" * 60)
    
    start_date, end_date = date_range
    logger.info(
        f"Период анализа: {start_date.strftime('%Y-%m-%d')} - "
        f"{end_date.strftime('%Y-%m-%d')}"
    )
    
    try:
        # Проверка на прерывание перед запуском
        if shutdown_requested:
            logger.info("Запуск отменен: получен сигнал завершения")
            return False
        
        # Запуск автоматизации
        stats = await orchestrator.run_automation(date_range=date_range)
        
        # Вывод итоговой статистики
        print("\n" + "=" * 60)
        print("           ИТОГОВАЯ СТАТИСТИКА")
        print("=" * 60)
        print(f"\nДлительность:        {stats['duration_seconds']:.2f} секунд")
        print(f"Обработано сообщений: {stats['messages_processed']}")
        print(f"Негативная сводка:   {stats['negative_summary_length']} символов")
        print(f"Позитивная сводка:   {stats['positive_summary_length']} символов")
        print(f"Отправлено в Telegram: {'✓ Да' if stats['telegram_sent'] else '✗ Нет'}")
        
        if stats.get('errors'):
            print(f"\nОшибки ({len(stats['errors'])}):")
            for i, error in enumerate(stats['errors'], 1):
                print(f"  {i}. {error}")
        
        print("\n" + "=" * 60)
        
        return stats['telegram_sent']
        
    except AutomationError as e:
        logger.error(f"Ошибка автоматизации: {str(e)}")
        print(f"\n✗ Ошибка автоматизации: {str(e)}")
        return False
    except Exception as e:
        logger.error(f"Неожиданная ошибка: {str(e)}", exc_info=True)
        print(f"\n✗ Неожиданная ошибка: {str(e)}")
        return False


async def run_scheduled_mode(orchestrator: AutomationOrchestrator) -> bool:
    """
    Запускает автоматизацию в режиме планировщика
    
    Args:
        orchestrator: Экземпляр AutomationOrchestrator
    
    Returns:
        True если выполнение успешно, False иначе
    """
    global shutdown_requested
    
    logger.info("=" * 60)
    logger.info("=== РЕЖИМ: SCHEDULED (автоматический по расписанию) ===")
    logger.info("=" * 60)
    
    try:
        # Настройка расписания
        orchestrator.setup_schedule()
        
        print("\n" + "=" * 60)
        print("  Планировщик NotebookLM Automation запущен")
        print("=" * 60)
        print("\nПланировщик будет автоматически запускать анализ")
        print("в будние дни согласно расписанию из конфигурации.")
        print("\nЛогика расписания:")
        print("  • Понедельник: анализ пятницы-воскресенья")
        print("  • Вторник-пятница: анализ предыдущего дня")
        print("  • Суббота-воскресенье: автоматизация не запускается")
        print("\nНажмите Ctrl+C для остановки...\n")
        
        # Бесконечный цикл ожидания
        try:
            while not shutdown_requested:
                await asyncio.sleep(60)
        except KeyboardInterrupt:
            logger.info("Остановка планировщика по запросу пользователя")
            print("\n✓ Планировщик остановлен")
        
        return True
        
    except Exception as e:
        logger.error(f"Ошибка в режиме планировщика: {str(e)}", exc_info=True)
        print(f"\n✗ Ошибка планировщика: {str(e)}")
        return False


async def main() -> bool:
    """
    Главная асинхронная функция
    
    Returns:
        True если выполнение успешно, False иначе
    """
    global orchestrator, logger
    
    # Парсинг аргументов
    args = parse_arguments()
    
    # Настройка логирования
    from src.utils.logger import setup_logger
    log_level = 'DEBUG' if args.verbose else 'INFO'
    logger = setup_logger("automation", level=log_level)
    
    # Заголовок
    print("\n" + "=" * 60)
    print("  NotebookLM Telegram Automation")
    print("  Автоматизация аналитических сводок")
    print("=" * 60 + "\n")
    
    # Создание директорий
    setup_directories()
    logger.info("✓ Директории проверены/созданы")
    
    # Настройка обработчиков сигналов
    setup_signal_handlers()
    
    # Валидация конфигурации
    if not validate_config():
        logger.error("Ошибка в конфигурации. Проверьте файл config.json")
        print("✗ Ошибка конфигурации. Проверьте файл config.json")
        return False
    
    logger.info("✓ Конфигурация валидна")
    
    # Определение диапазона дат для manual режима
    try:
        date_range = get_date_range_from_args(args)
    except ValueError as e:
        logger.error(f"Ошибка в аргументах: {str(e)}")
        print(f"\n✗ Ошибка в аргументах: {str(e)}")
        print("Используйте --help для справки")
        return False
    
    # Инициализация оркестратора
    try:
        logger.info("Инициализация AutomationOrchestrator...")
        orchestrator = AutomationOrchestrator(config_path=args.config)
        logger.info("✓ AutomationOrchestrator инициализирован")
    except AutomationError as e:
        logger.error(f"Ошибка инициализации: {str(e)}")
        print(f"\n✗ Ошибка инициализации: {str(e)}")
        return False
    except Exception as e:
        logger.error(f"Неожиданная ошибка инициализации: {str(e)}", exc_info=True)
        print(f"\n✗ Неожиданная ошибка: {str(e)}")
        return False
    
    # Запуск в соответствующем режиме
    try:
        if args.mode == 'manual':
            result = await run_manual_mode(orchestrator, date_range)
        else:  # scheduled
            result = await run_scheduled_mode(orchestrator)
        
        return result
        
    except KeyboardInterrupt:
        logger.info("Остановка по запросу пользователя")
        print("\n✓ Программа остановлена пользователем")
        return True
    except Exception as e:
        logger.error(f"Критическая ошибка: {str(e)}", exc_info=True)
        print(f"\n✗ Критическая ошибка: {str(e)}")
        return False
    finally:
        # Очистка ресурсов при завершении
        if orchestrator:
            try:
                logger.info("Финальная очистка ресурсов...")
                await orchestrator.cleanup_resources()
                logger.info("✓ Ресурсы освобождены")
            except Exception as e:
                logger.error(f"Ошибка при финальной очистке ресурсов: {str(e)}")


if __name__ == "__main__":
    try:
        # Настройка event loop для Windows
        if sys.platform == 'win32':
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        
        # Запуск главной функции
        result = asyncio.run(main())
        
        # Завершение с соответствующим кодом
        sys.exit(0 if result else 1)
        
    except KeyboardInterrupt:
        print("\n✓ Программа остановлена пользователем")
        sys.exit(0)
    except Exception as e:
        print(f"\n✗ Критическая ошибка: {str(e)}")
        sys.exit(1)
