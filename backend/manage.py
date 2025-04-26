#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Утилита для управления проектом Cyberpunk 2077 Wiki API
Запуск: python manage.py <команда>

Доступные команды:
- run: Запуск API сервера
- scrape_all: Сбор данных для всех категорий
- scrape <категория>: Сбор данных для определенной категории
- clear_cache: Очистка кэша
- create_superuser: Создание администратора
"""

import os
import sys
import argparse
import logging
from pathlib import Path

# Добавляем директорию проекта в PATH
BASE_DIR = Path(__file__).resolve().parent
sys.path.append(str(BASE_DIR))
sys.path.append(str(BASE_DIR / "src"))

def setup_logging():
    """Настройка логирования"""
    log_dir = BASE_DIR / "logs"
    log_dir.mkdir(exist_ok=True)
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        handlers=[
            logging.FileHandler(log_dir / "manage.log", encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    
    return logging.getLogger("manage")

def run_server(args):
    """Запуск сервера API"""
    from src.main import app
    import uvicorn
    
    host = args.host or "0.0.0.0"
    port = args.port or 8000
    
    logger.info(f"Запуск сервера на {host}:{port}")
    uvicorn.run(
        "src.main:app",
        host=host,
        port=port,
        reload=args.reload
    )

def scrape_data(args):
    """Сбор данных из Wiki"""
    from src.app.scraper.wiki_scraper import scrape_category, get_all_wiki_categories, initialize_wiki, CATEGORIES
    
    initialize_wiki()
    
    if args.category == "all":
        logger.info("Сбор данных для всех категорий")
        for cat_key, cat_name in CATEGORIES.items():
            logger.info(f"Обработка категории: {cat_key}")
            result = scrape_category(cat_key)
            logger.info(f"Собрано {len(result)} элементов для категории {cat_key}")
    else:
        if args.category not in CATEGORIES:
            logger.error(f"Категория '{args.category}' не найдена. Доступные категории: {', '.join(CATEGORIES.keys())}")
            return
        
        logger.info(f"Сбор данных для категории: {args.category}")
        result = scrape_category(args.category)
        logger.info(f"Собрано {len(result)} элементов для категории {args.category}")

def clear_cache(args):
    """Очистка кэша Redis"""
    from src.app.redis.redis_cache import redis_cache
    
    if args.category:
        if args.category == "all":
            logger.info("Очистка всего кэша")
            redis_cache.clear_all_cache()
        else:
            logger.info(f"Очистка кэша для категории: {args.category}")
            redis_cache.invalidate_category(args.category)
    else:
        logger.info("Очистка всего кэша")
        redis_cache.clear_all_cache()
    
    logger.info("Кэш успешно очищен")

def create_superuser(args):
    """Создание пользователя-администратора"""
    # Здесь будет код для создания администратора, когда будет добавлена 
    # система аутентификации
    logger.info("Функция создания администратора будет добавлена в будущих версиях")

def main():
    """Основная функция"""
    parser = argparse.ArgumentParser(description="Утилита управления Cyberpunk 2077 Wiki API")
    subparsers = parser.add_subparsers(dest="command", help="Команда для выполнения")
    
    # Команда запуска сервера
    run_parser = subparsers.add_parser("run", help="Запуск API сервера")
    run_parser.add_argument("--host", help="Хост для запуска (по умолчанию 0.0.0.0)")
    run_parser.add_argument("--port", type=int, help="Порт для запуска (по умолчанию 8000)")
    run_parser.add_argument("--reload", action="store_true", help="Автоматическая перезагрузка при изменении файлов")
    
    # Команда сбора данных
    scrape_parser = subparsers.add_parser("scrape", help="Сбор данных из Wiki")
    scrape_parser.add_argument("category", help="Категория для сбора данных ('all' для всех категорий)")
    
    # Команда очистки кэша
    cache_parser = subparsers.add_parser("clear_cache", help="Очистка кэша")
    cache_parser.add_argument("--category", help="Категория для очистки кэша (по умолчанию все)")
    
    # Команда создания администратора
    admin_parser = subparsers.add_parser("create_superuser", help="Создание администратора")
    
    args = parser.parse_args()
    
    if args.command == "run":
        run_server(args)
    elif args.command == "scrape":
        scrape_data(args)
    elif args.command == "clear_cache":
        clear_cache(args)
    elif args.command == "create_superuser":
        create_superuser(args)
    else:
        parser.print_help()

if __name__ == "__main__":
    logger = setup_logging()
    main()
