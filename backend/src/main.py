#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
API для Cyberpunk 2077 Wiki Scraper
-----------------------------------
REST API для доступа к данным из Cyberpunk 2077 Wiki
- Получение данных о персонажах, локациях, транспорте и др.
- Поиск информации по категориям
- Кэширование в Redis для повышения производительности
"""

import os
import sys
import json
import logging
from pathlib import Path
from datetime import datetime

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import ORJSONResponse
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.staticfiles import StaticFiles

# Импортируем API роутер
from src.api.router import api_router
from src.app.scraper.wiki_scraper import initialize_wiki
from src.app.redis.redis_cache import redis_cache
from src.core.config import settings

# Настройки API
API_VERSION = os.getenv("API_VERSION", "v1")
DEBUG_MODE = settings.DEBUG_MODE

# Создаем FastAPI приложение
app = FastAPI(
    title="Cyberpunk 2077 Wiki API",
    description="API для получения данных из Cyberpunk 2077 Wiki",
    version=API_VERSION,
    default_response_class=ORJSONResponse,
    docs_url=None,  # Отключаем стандартный путь к документации
    redoc_url=None,  # Отключаем ReDoc
)

# Настраиваем CORS для взаимодействия с фронтендом
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS_LIST,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Настройка логирования
def setup_api_logging():
    """Настройка логирования для API"""
    log_dir = settings.LOG_DIR
    os.makedirs(log_dir, exist_ok=True)
    
    log_file = os.path.join(log_dir, f"api_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
    
    logging.basicConfig(
        level=logging.DEBUG if DEBUG_MODE else logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    
    # Отключаем излишние логи от библиотек
    if not DEBUG_MODE:
        logging.getLogger("requests").setLevel(logging.WARNING)
        logging.getLogger("urllib3").setLevel(logging.WARNING)
    
    return logging.getLogger("wiki_api")

# Создаем логгер
logger = setup_api_logging()

# Подключаем API роутер
app.include_router(api_router, prefix="/api")

# Инициализация API
@app.on_event("startup")
async def startup_event():
    """Инициализация при запуске API"""
    logger.info("Запуск API")
    
    
    # Инициализируем wiki_scraper
    try:
        initialize_wiki()
        logger.info("Wiki Scraper инициализирован")
    except Exception as e:
        logger.error(f"Ошибка инициализации Wiki Scraper: {str(e)}")
    
    # Проверяем подключение к Redis cache
    if redis_cache.ping():
        logger.info("Подключение к Redis cache успешно")
    else:
        logger.warning("Не удалось подключиться к Redis cache, будет использовано файловое кэширование")
    
    # Предварительная загрузка категорий в фоновом режиме
    try:
        from src.app.scraper.wiki_scraper import get_all_wiki_categories
        categories = get_all_wiki_categories()
        if categories:
            redis_cache.set_all_categories(categories)
            logger.info(f"Предварительно загружено {len(categories)} категорий")
    except Exception as e:
        logger.error(f"Ошибка предварительной загрузки категорий: {str(e)}")
    
    logger.info("API инициализирован и готов к работе")

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("API остановлен")

# Корневой маршрут
@app.get("/")
async def root():
    """Корневой эндпоинт с редиректом на документацию"""
    return {
        "name": "Cyberpunk 2077 Wiki API",
        "version": API_VERSION,
        "docs_url": "/docs",
        "api_url": f"/api/{API_VERSION}"
    }

# Кастомные страницы документации
@app.get("/docs", include_in_schema=False)
async def custom_swagger_ui_html():
    """Кастомная страница Swagger UI"""
    return get_swagger_ui_html(
        openapi_url="/openapi.json",
        title="Cyberpunk 2077 Wiki API",
        swagger_js_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js",
        swagger_css_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css",
    )

# Запуск приложения (если запускается напрямую, а не через uvicorn)
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app", 
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=DEBUG_MODE
    ) 