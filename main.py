# -*- coding: utf-8 -*-
"""
AllInclusiveParser - Универсальный парсер для Telegram каналов
Унифицированная точка входа с поддержкой всех режимов работы
"""
import os
import sys
import asyncio
import argparse
import logging
from datetime import datetime
from typing import Optional

# Добавляем путь к корневой директории проекта
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.core.unified_parser import UnifiedParser
from src.export.post_parse import (
    clear_db_after_export,
    clear_messages_table,
    docs_enabled,
    export_to_notebooklm_via_file,
    is_panel_managed,
    notebooklm_enabled,
)
from src.utils.logger import setup_logger
from src.config import validate_config


def setup_directories():
    """Создает необходимые директории для работы приложения"""
    dirs = ['logs', 'sessions', 'cache', 'exports', 'data']
    for directory in dirs:
        os.makedirs(directory, exist_ok=True)


def parse_arguments() -> argparse.Namespace:
    """Парсинг аргументов командной строки"""
    parser = argparse.ArgumentParser(
        description='AllInclusiveParser - Универсальный парсер Telegram каналов',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры использования:
  %(prog)s                          # Парсинг всех каналов (режим по умолчанию)
  %(prog)s --mode parse             # Явный режим парсинга
  %(prog)s --mode parse --channel @example  # Парсинг конкретного канала
  %(prog)s --mode export --format csv       # Экспорт данных в CSV
  %(prog)s --mode stats             # Показать статистику
  %(prog)s --mode schedule          # Запустить планировщик
        """
    )
    
    parser.add_argument('--mode', choices=['parse', 'export', 'stats', 'schedule'],
                       default='parse', help='Режим работы приложения (по умолчанию: parse)')
    parser.add_argument('--format', choices=['csv', 'json', 'xml'],
                       default='csv', help='Формат экспорта данных (по умолчанию: csv)')
    parser.add_argument('--channel', type=str,
                       help='Конкретный канал для парсинга (например: @channelname или https://t.me/channelname)')
    parser.add_argument('--output', type=str, help='Путь к файлу для экспорта (опционально)')
    parser.add_argument('--verbose', action='store_true', help='Подробный вывод логов')
    
    return parser.parse_args()


async def _run_post_parse_exports(messages, logger) -> bool:
    """Запускает экспорт-шаги (Docs / NotebookLM) и опциональную чистку БД.

    Управляется env-флагами от web-panel:
    - ``PARSER_EXPORT_TO_DOCS=1`` / ``PARSER_EXPORT_TO_NOTEBOOKLM=1`` — что делать;
    - ``PARSER_CLEAR_DB_AFTER_EXPORT=1`` — удалить ``messages`` после успеха.

    При CLI-запуске (без панели) ведёт себя как раньше: экспорт в Docs всегда,
    NotebookLM не вызывается, БД не чистится.
    """
    if not messages:
        return True

    success = True
    panel = is_panel_managed()

    if docs_enabled():
        try:
            from src.config import GOOGLE_CONFIG
            logger.info(
                f"Экспорт {len(messages)} новых сообщений в Google Docs "
                f"(creds={GOOGLE_CONFIG.get('CREDS_PATH')!r})"
            )
            from src.export.google_docs import GoogleDocsExporter
            from src.config import get_google_config
            exporter = GoogleDocsExporter()
            batch_size = get_google_config().get("BATCH_SIZE", 100)
            exporter.append_new_content(messages, batch_size=batch_size)
            print(f"\n✓ Экспортировано {len(messages)} новых сообщений в Google Docs")
        except Exception as exc:
            logger.error("Ошибка экспорта в Google Docs: %s", exc, exc_info=True)
            # CLI runs preserve the historical "log and continue" behaviour
            # (UnifiedParser.export_to_google_docs swallowed exceptions, so
            # exit code stayed 0). Panel-managed runs surface failures to
            # the jobs UI by flipping ``success`` and exiting non-zero.
            if panel:
                success = False
    elif panel:
        logger.info("Google Docs экспорт отключён в панели — пропускаем")

    if notebooklm_enabled():
        logger.info("Экспорт %s сообщений в NotebookLM…", len(messages))
        nlm_ok = await export_to_notebooklm_via_file(messages)
        if nlm_ok:
            print(f"\n✓ Загружено {len(messages)} сообщений в NotebookLM")
        else:
            success = False

    if success and clear_db_after_export():
        logger.info("Очистка messages в parser.db после успешного экспорта…")
        try:
            removed = clear_messages_table()
            print(f"\n✓ Удалено {removed} строк из parser.db (entity-cache сохранён)")
        except Exception as exc:  # noqa: BLE001
            logger.error("Ошибка очистки messages: %s", exc, exc_info=True)
            success = False

    return success


async def run_parse_mode(parser: UnifiedParser, args: argparse.Namespace, logger) -> bool:
    """Режим парсинга каналов"""
    try:
        logger.info("=== Режим парсинга ===")

        if args.channel:
            logger.info(f"Парсинг канала: {args.channel}")
            messages = await parser.parse_channel(args.channel)

            if messages:
                logger.info(f"Получено {len(messages)} сообщений из канала {args.channel}")
                processed = await parser.process_messages(messages, args.channel)
                logger.info(f"Обработано {len(processed)} сообщений")

                if processed:
                    return await _run_post_parse_exports(processed, logger)

                return True
            else:
                logger.warning(f"Не удалось получить сообщения из канала {args.channel}")
                return False
        else:
            logger.info("Парсинг всех каналов из конфигурации")
            result = await parser.parse_channels()
            total_messages = sum(len(msgs) for msgs in result.values())
            logger.info(f"Парсинг завершен: {len(result)} каналов, {total_messages} сообщений")

            all_new_messages = []
            for channel_name, messages in result.items():
                new_messages = await parser.process_messages(messages, channel_name)
                all_new_messages.extend(new_messages)

            if all_new_messages:
                logger.info(f"Найдено {len(all_new_messages)} новых сообщений для экспорта")
                return await _run_post_parse_exports(all_new_messages, logger)

            logger.info("Нет новых сообщений для экспорта")
            print("\n✓ Парсинг завершен. Новых сообщений не найдено.")
            return True

    except Exception as e:
        logger.error(f"Ошибка в режиме парсинга: {e}", exc_info=True)
        return False


async def run_export_mode(parser: UnifiedParser, args: argparse.Namespace, logger) -> bool:
    """Режим экспорта данных"""
    try:
        logger.info(f"=== Режим экспорта (формат: {args.format}) ===")
        
        from src.database.models import Database
        db = Database()
        messages = db.get_all_messages()
        
        if not messages:
            logger.warning("Нет данных для экспорта")
            return False
        
        logger.info(f"Найдено {len(messages)} сообщений для экспорта")
        
        if args.format == 'csv':
            from src.export.excel import export_to_csv
            output_path = args.output or f'exports/export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
            export_to_csv(messages, output_path)
            logger.info(f"Данные экспортированы в CSV: {output_path}")
        elif args.format == 'json':
            from src.export.advanced_export import export_to_json
            output_path = args.output or f'exports/export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
            export_to_json(messages, output_path)
            logger.info(f"Данные экспортированы в JSON: {output_path}")
        elif args.format == 'xml':
            from src.export.advanced_export import export_to_xml
            output_path = args.output or f'exports/export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xml'
            export_to_xml(messages, output_path)
            logger.info(f"Данные экспортированы в XML: {output_path}")
        
        print(f"\n✓ Экспорт завершен: {output_path}")
        return True
        
    except Exception as e:
        logger.error(f"Ошибка в режиме экспорта: {e}", exc_info=True)
        return False


async def run_stats_mode(parser: UnifiedParser, args: argparse.Namespace, logger) -> bool:
    """Режим статистики"""
    try:
        logger.info("=== Режим статистики ===")
        stats = parser.get_statistics()
        
        print("\n" + "="*50)
        print("           СТАТИСТИКА ПАРСЕРА")
        print("="*50)
        print(f"\nВсего сообщений:     {stats.get('total_messages', 0)}")
        print(f"Активных каналов:    {stats.get('total_channels', 0)}")
        print(f"Период данных:       {stats.get('date_range', 'N/A')}")
        
        channel_stats = stats.get('channel_stats', [])
        if channel_stats:
            print(f"\nТоп-{min(10, len(channel_stats))} каналов по активности:")
            for i, (channel, count) in enumerate(channel_stats[:10], 1):
                print(f"  {i:2d}. {channel:30s} {count:5d} сообщений")
        
        date_stats = stats.get('date_stats', {})
        if date_stats:
            print(f"\nСтатистика по датам:")
            print(f"  Первое сообщение:  {date_stats.get('first_message', 'N/A')}")
            print(f"  Последнее сообщение: {date_stats.get('last_message', 'N/A')}")
        
        error_stats = stats.get('error_stats', {})
        if error_stats and error_stats.get('total_errors', 0) > 0:
            print(f"\nСтатистика ошибок:")
            print(f"  Всего ошибок:      {error_stats.get('total_errors', 0)}")
            print(f"  FloodWait ошибок:  {error_stats.get('flood_wait_errors', 0)}")
            print(f"  Ошибок каналов:    {error_stats.get('channel_errors', 0)}")
            print(f"  Сетевых ошибок:    {error_stats.get('network_errors', 0)}")
        
        print("\n" + "="*50 + "\n")
        return True
        
    except Exception as e:
        logger.error(f"Ошибка в режиме статистики: {e}", exc_info=True)
        return False


async def run_schedule_mode(parser: UnifiedParser, args: argparse.Namespace, logger) -> bool:
    """Режим планировщика"""
    try:
        logger.info("=== Режим планировщика ===")
        parser.setup_scheduler()
        
        print("\n" + "="*50)
        print("  Планировщик запущен")
        print("="*50)
        print("\nПланировщик будет автоматически запускать парсинг")
        print("согласно расписанию из конфигурации.")
        print("\nНажмите Ctrl+C для остановки...\n")
        
        try:
            while True:
                await asyncio.sleep(60)
        except KeyboardInterrupt:
            logger.info("Остановка планировщика по запросу пользователя")
            print("\n✓ Планировщик остановлен")
        
        return True
        
    except Exception as e:
        logger.error(f"Ошибка в режиме планировщика: {e}", exc_info=True)
        return False


async def main() -> bool:
    """Главная асинхронная функция"""
    args = parse_arguments()
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logger = setup_logger("main", level=log_level)
    
    logger.info("="*60)
    logger.info("  AllInclusiveParser - Универсальный парсер Telegram каналов")
    logger.info("="*60)
    
    setup_directories()
    logger.info("Директории проверены/созданы")
    
    if not validate_config():
        logger.error("Ошибка в конфигурации. Проверьте файл config.json")
        print("\n✗ Ошибка конфигурации. Проверьте файл config.json")
        return False
    
    logger.info("Конфигурация валидна")
    parser = UnifiedParser()
    
    try:
        await parser.init_async()
        logger.info("UnifiedParser инициализирован")
        
        if args.mode == 'parse':
            result = await run_parse_mode(parser, args, logger)
        elif args.mode == 'export':
            result = await run_export_mode(parser, args, logger)
        elif args.mode == 'stats':
            result = await run_stats_mode(parser, args, logger)
        elif args.mode == 'schedule':
            result = await run_schedule_mode(parser, args, logger)
        else:
            logger.error(f"Неизвестный режим: {args.mode}")
            return False
        
        return result
        
    except KeyboardInterrupt:
        logger.info("Остановка по запросу пользователя")
        print("\n✓ Программа остановлена пользователем")
        return True
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}", exc_info=True)
        print(f"\n✗ Критическая ошибка: {e}")
        return False
    finally:
        try:
            await parser.cleanup()
            logger.info("Ресурсы освобождены")
        except Exception as e:
            logger.error(f"Ошибка при очистке ресурсов: {e}")


if __name__ == "__main__":
    try:
        # Подавляем предупреждения о deprecated WindowsSelectorEventLoopPolicy
        import warnings
        warnings.filterwarnings('ignore', category=DeprecationWarning, module='asyncio')
        
        if sys.platform == 'win32':
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        
        result = asyncio.run(main())
        sys.exit(0 if result else 1)
    except KeyboardInterrupt:
        print("\n✓ Программа остановлена пользователем")
        sys.exit(0)
    except Exception as e:
        print(f"\n✗ Критическая ошибка: {e}")
        sys.exit(1)
