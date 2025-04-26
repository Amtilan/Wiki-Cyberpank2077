#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
API роутеры для Cyberpunk 2077 Wiki
----------------------------------
- Роутеры для каждой категории данных
- Основные эндпоинты API
- Объединение всех роутеров в один
"""

import os
import json
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Dict, Any, Optional

from src.app.redis.redis_cache import redis_cache
from src.core.config import settings
from src.api.v1 import characters, vehicles, locations, items, search, weapons, perks

# Создаем основной роутер API
api_router = APIRouter()

# Версия API
API_VERSION = os.getenv("API_VERSION", "v1")

# Добавляем все подроутеры
api_router.include_router(
    characters.router,
    prefix=f"/{API_VERSION}/characters",
    tags=["characters"],
)

api_router.include_router(
    vehicles.router,
    prefix=f"/{API_VERSION}/vehicles",
    tags=["vehicles"],
)

api_router.include_router(
    locations.router,
    prefix=f"/{API_VERSION}/locations",
    tags=["locations"],
)

api_router.include_router(
    weapons.router,
    prefix=f"/{API_VERSION}/weapons",
    tags=["weapons"],
)

api_router.include_router(
    perks.router,
    prefix=f"/{API_VERSION}/perks",
    tags=["perks"],
)

api_router.include_router(
    items.router,
    prefix=f"/{API_VERSION}/items",
    tags=["items"],
)

api_router.include_router(
    search.router,
    prefix=f"/{API_VERSION}/search",
    tags=["search"],
)

# Корневой эндпоинт API
@api_router.get("/")
async def api_root():
    """Корневой эндпоинт API"""
    return {
        "api": "Cyberpunk 2077 Wiki API",
        "version": API_VERSION,
        "docs_url": "/docs",
        "endpoints": [
            f"/api/{API_VERSION}/characters",
            f"/api/{API_VERSION}/vehicles",
            f"/api/{API_VERSION}/locations",
            f"/api/{API_VERSION}/weapons",
            f"/api/{API_VERSION}/perks",
            f"/api/{API_VERSION}/items",
            f"/api/{API_VERSION}/search",
        ]
    }

# Список всех категорий
@api_router.get("/categories")
async def list_categories():
    """Получение списка всех категорий"""
    # Сначала проверяем кэш
    cached_categories = redis_cache.get_all_categories()
    if cached_categories:
        return {
            "source": "cache",
            "categories": cached_categories
        }
    
    # Если в кэше нет, возвращаем категории из настроек
    return {
        "source": "config",
        "categories": settings.CATEGORIES
    }

# Эндпоинт для проверки статуса API
@api_router.get("/status")
async def api_status():
    """Проверка статуса API"""
    # Проверка подключения к кэшу
    cache_status = redis_cache.ping()
    
    return {
        "status": "operational",
        "version": API_VERSION,
        "cache": {
            "type": "redis" if settings.USE_REDIS_CACHE else "file",
            "status": "connected" if cache_status else "disconnected"
        },
        "wiki": {
            "base_url": settings.WIKI_URL
        }
    }
