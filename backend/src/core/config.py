#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Модуль конфигурации для Wiki-Cyberpunk2077
-----------------------------------------
Содержит настройки приложения, загружаемые из переменных окружения
"""

import os
from typing import Any, Dict, List, Optional
from pydantic import BaseSettings, validator, Field
import json


class Settings(BaseSettings):
    """
    Класс настроек приложения, загружаемых из переменных окружения
    """
    # Основные настройки приложения
    PROJECT_NAME: str = "Wiki Cyberpunk 2077"
    API_PREFIX: str = "/api"
    DEBUG: bool = False
    VERSION: str = "0.1.0"
    
    # Настройки хоста API
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    
    # Настройки директорий
    TEMP_DIR: str = "data/temp"
    LOG_DIR: str = "logs"

    # Настройки Redis для кэширования
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: Optional[str] = None
    REDIS_URL: Optional[str] = None
    REDIS_TTL: int = 3600
    USE_REDIS_CACHE: bool = False

    @validator("REDIS_URL", pre=True)
    def assemble_redis_connection(cls, v: Optional[str], values: Dict[str, Any]) -> str:
        """Собирает URL подключения к Redis из компонентов"""
        if isinstance(v, str):
            return v
        password_part = f":{values.get('REDIS_PASSWORD')}@" if values.get("REDIS_PASSWORD") else ""
        return f"redis://{password_part}{values.get('REDIS_HOST')}:{values.get('REDIS_PORT')}/{values.get('REDIS_DB')}"

    # Настройки поискового движка
    SEARCH_MIN_QUERY_LENGTH: int = 3
    SEARCH_MAX_RESULTS: int = 20
    SEARCH_CACHE_TTL: int = 300  # время жизни кэша поисковых запросов в секундах
    
    # Настройки Wiki URL
    WIKI_URL: str = "https://cyberpunk.fandom.com/wiki/"
    
    # Категории Wiki
    CATEGORIES: Dict[str, str] = {
        "characters": "Cyberpunk 2077 Characters",
        "vehicles": "Cyberpunk 2077 Vehicles",
        "weapons": "Weapons in Cyberpunk 2077",
        "locations": "Cyberpunk 2077 Locations",
        "perks": "Perks in Cyberpunk 2077",
        "items": "Items in Cyberpunk 2077"
    }

    # Настройки CORS
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:8000", "https://wiki-cyberpunk2077.com"]
    
    @property
    def CORS_ORIGINS_LIST(self) -> List[str]:
        """Список разрешенных CORS origins"""
        if isinstance(self.CORS_ORIGINS, str):
            try:
                return json.loads(self.CORS_ORIGINS)
            except:
                return [self.CORS_ORIGINS]
        return self.CORS_ORIGINS

    class Config:
        """Pydantic настройки для класса Settings"""
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


# Создаем экземпляр настроек
settings = Settings()

# Создаем директории, необходимые для работы приложения
os.makedirs(settings.TEMP_DIR, exist_ok=True)
os.makedirs(settings.LOG_DIR, exist_ok=True)

# Создаем директории для категорий
for category in settings.CATEGORIES.keys():
    os.makedirs(os.path.join(settings.TEMP_DIR, category), exist_ok=True)