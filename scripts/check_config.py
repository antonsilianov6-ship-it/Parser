#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Скрипт для проверки конфигурации NotebookLM Automation
"""
import json
import sys

def check_config():
    """Проверяет конфигурацию на наличие обязательных полей"""
    
    print("\n" + "=" * 60)
    print("  Проверка конфигурации NotebookLM Automation")
    print("=" * 60 + "\n")
    
    try:
        with open('config.json', 'r', encoding='utf-8') as f:
            config = json.load(f)
    except FileNotFoundError:
        print("✗ Файл config.json не найден!")
        return False
    except json.JSONDecodeError as e:
        print(f"✗ Ошибка в JSON формате: {e}")
        return False
    
    errors = []
    warnings = []
    
    # Проверка NotebookLM
    print("1. Проверка NotebookLM настроек...")
    if 'NOTEBOOKLM' not in config:
        errors.append("  ✗ Секция NOTEBOOKLM отсутствует")
    else:
        nlm = config['NOTEBOOKLM']
        if not nlm.get('email'):
            errors.append("  ✗ NotebookLM email не указан")
        else:
            print(f"  ✓ Email: {nlm['email']}")
        
        if not nlm.get('password'):
            errors.append("  ✗ NotebookLM password не указан")
        else:
            print(f"  ✓ Password: {'*' * len(nlm['password'])}")
    
    # Проверка Automation
    print("\n2. Проверка Automation настроек...")
    if 'AUTOMATION' not in config:
        errors.append("  ✗ Секция AUTOMATION отсутствует")
    else:
        auto = config['AUTOMATION']
        
        if not auto.get('enabled'):
            warnings.append("  ⚠ Automation отключена (enabled: false)")
        else:
            print("  ✓ Automation включена")
        
        if not auto.get('target_chat_id'):
            errors.append("  ✗ target_chat_id не указан")
        else:
            print(f"  ✓ Target chat ID: {auto['target_chat_id']}")
        
        if auto.get('schedule_enabled'):
            print(f"  ✓ Расписание включено: {auto.get('schedule_time', '09:00')}")
            print(f"    Дни: {', '.join(auto.get('schedule_days', []))}")
    
    # Проверка Telegram
    print("\n3. Проверка Telegram настроек...")
    if 'TELEGRAM' not in config:
        errors.append("  ✗ Секция TELEGRAM отсутствует")
    else:
        tg = config['TELEGRAM']
        if tg.get('API_ID') and tg.get('API_HASH'):
            print(f"  ✓ API_ID: {tg['API_ID']}")
            print(f"  ✓ API_HASH: {tg['API_HASH'][:10]}...")
        else:
            errors.append("  ✗ API_ID или API_HASH не указаны")
    
    # Проверка промптов
    print("\n4. Проверка файла промптов...")
    try:
        with open('config/prompts.json', 'r', encoding='utf-8') as f:
            prompts = json.load(f)
        
        if 'prompts' in prompts:
            if 'negative' in prompts['prompts'] and 'positive' in prompts['prompts']:
                print("  ✓ Промпты настроены (negative, positive)")
            else:
                warnings.append("  ⚠ Не все промпты настроены")
        else:
            errors.append("  ✗ Секция prompts отсутствует")
    except FileNotFoundError:
        errors.append("  ✗ Файл config/prompts.json не найден")
    except json.JSONDecodeError:
        errors.append("  ✗ Ошибка в формате config/prompts.json")
    
    # Итоги
    print("\n" + "=" * 60)
    print("  РЕЗУЛЬТАТЫ ПРОВЕРКИ")
    print("=" * 60 + "\n")
    
    if errors:
        print("ОШИБКИ (необходимо исправить):")
        for error in errors:
            print(error)
        print()
    
    if warnings:
        print("ПРЕДУПРЕЖДЕНИЯ (рекомендуется проверить):")
        for warning in warnings:
            print(warning)
        print()
    
    if not errors and not warnings:
        print("✓ Все проверки пройдены успешно!")
        print("✓ Конфигурация готова к использованию")
        return True
    elif not errors:
        print("✓ Критических ошибок не найдено")
        print("⚠ Есть предупреждения, но можно продолжать")
        return True
    else:
        print("✗ Найдены критические ошибки")
        print("✗ Исправьте ошибки перед запуском")
        return False

if __name__ == "__main__":
    success = check_config()
    sys.exit(0 if success else 1)
