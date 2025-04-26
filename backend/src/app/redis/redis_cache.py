#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Модуль для работы с Redis кэшем
-------------------------------
Предоставляет функционал для кэширования данных в Redis
- Хранение категорий Wiki
- Кэширование результатов запросов
- Управление TTL кэша
"""

import os
import json
import redis
import pickle
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Union

from src.core.config import settings

# Логгер для модуля redis_cache
logger = logging.getLogger("wiki_api.redis_cache")

class RedisCache:
    """Класс для работы с Redis кэшем"""
    
    def __init__(self):
        """Инициализация подключения к Redis"""
        self.redis_host = settings.REDIS_HOST
        self.redis_port = settings.REDIS_PORT
        self.redis_db = settings.REDIS_DB
        self.redis_password = settings.REDIS_PASSWORD
        
        self.ttl = settings.REDIS_TTL
        self.file_cache_dir = settings.TEMP_DIR
        self.use_redis = settings.USE_REDIS_CACHE
        
        # Инициализация Redis клиента
        if self.use_redis:
            try:
                self.redis_client = redis.Redis(
                    host=self.redis_host,
                    port=self.redis_port,
                    db=self.redis_db,
                    password=self.redis_password,
                    decode_responses=False,  # Важно для pickle
                    socket_timeout=5,
                    socket_connect_timeout=5
                )
                logger.info(f"Инициализировано подключение к Redis: {self.redis_host}:{self.redis_port}")
            except Exception as e:
                logger.error(f"Ошибка подключения к Redis: {str(e)}")
                self.use_redis = False
        
        # Создаем директорию для файлового кэша
        if not self.use_redis:
            os.makedirs(self.file_cache_dir, exist_ok=True)
            logger.info(f"Будет использоваться файловый кэш: {self.file_cache_dir}")
    
    def ping(self) -> bool:
        """Проверка подключения к Redis"""
        if not self.use_redis:
            return False
        
        try:
            return self.redis_client.ping()
        except Exception as e:
            logger.error(f"Ошибка подключения к Redis: {str(e)}")
            self.use_redis = False
            return False
    
    def _get_file_path(self, key: str) -> Path:
        """Получение пути к файлу кэша"""
        # Заменяем запрещенные символы в имени файла
        safe_key = key.replace('/', '_').replace(':', '_').replace('?', '_')
        return Path(self.file_cache_dir) / f"{safe_key}.cache"
    
    def get(self, key: str) -> Any:
        """Получение данных из кэша"""
        if self.use_redis:
            try:
                data = self.redis_client.get(key)
                if data:
                    return pickle.loads(data)
            except Exception as e:
                logger.error(f"Ошибка получения данных из Redis: {str(e)}")
        
        # Если Redis недоступен или данных нет - пробуем из файла
        try:
            file_path = self._get_file_path(key)
            if file_path.exists():
                # Проверяем TTL для файлового кэша
                if self.ttl > 0:
                    modified_time = datetime.fromtimestamp(file_path.stat().st_mtime)
                    if datetime.now() - modified_time > timedelta(seconds=self.ttl):
                        # Кэш устарел
                        file_path.unlink(missing_ok=True)
                        return None
                
                with open(file_path, 'rb') as f:
                    return pickle.load(f)
        except Exception as e:
            logger.error(f"Ошибка получения данных из файлового кэша: {str(e)}")
        
        return None
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Сохранение данных в кэш"""
        if ttl is None:
            ttl = self.ttl
        
        success = False
        
        # Сначала пробуем сохранить в Redis
        if self.use_redis:
            try:
                pickled_value = pickle.dumps(value)
                if ttl > 0:
                    success = self.redis_client.setex(key, ttl, pickled_value)
                else:
                    success = self.redis_client.set(key, pickled_value)
            except Exception as e:
                logger.error(f"Ошибка сохранения данных в Redis: {str(e)}")
        
        # Если Redis недоступен или сохранение не удалось - сохраняем в файл
        try:
            file_path = self._get_file_path(key)
            with open(file_path, 'wb') as f:
                pickle.dump(value, f)
            success = True
        except Exception as e:
            logger.error(f"Ошибка сохранения данных в файловом кэше: {str(e)}")
        
        return success
    
    def delete(self, key: str) -> bool:
        """Удаление данных из кэша"""
        success = False
        
        # Удаляем из Redis
        if self.use_redis:
            try:
                self.redis_client.delete(key)
                success = True
            except Exception as e:
                logger.error(f"Ошибка удаления данных из Redis: {str(e)}")
        
        # Удаляем из файлового кэша
        try:
            file_path = self._get_file_path(key)
            if file_path.exists():
                file_path.unlink()
            success = True
        except Exception as e:
            logger.error(f"Ошибка удаления данных из файлового кэша: {str(e)}")
        
        return success
    
    def flush(self) -> bool:
        """Очистка всего кэша"""
        success = False
        
        # Очищаем Redis
        if self.use_redis:
            try:
                self.redis_client.flushdb()
                success = True
            except Exception as e:
                logger.error(f"Ошибка очистки Redis: {str(e)}")
        
        # Очищаем файловый кэш
        try:
            cache_dir = Path(self.file_cache_dir)
            for cache_file in cache_dir.glob("*.cache"):
                cache_file.unlink()
            success = True
        except Exception as e:
            logger.error(f"Ошибка очистки файлового кэша: {str(e)}")
        
        return success
    
    def set_all_categories(self, categories: Dict[str, Any]) -> bool:
        """Сохранение всех категорий в кэш"""
        return self.set("all_categories", categories)
    
    def get_all_categories(self) -> Dict[str, Any]:
        """Получение всех категорий из кэша"""
        return self.get("all_categories") or {}
    
    def set_category_data(self, category: str, data: List[Dict[str, Any]]) -> bool:
        """Сохранение данных категории в кэш"""
        return self.set(f"category:{category}", data)
    
    def get_category_data(self, category: str) -> List[Dict[str, Any]]:
        """Получение данных категории из кэша"""
        return self.get(f"category:{category}") or []
    
    def set_item_data(self, category: str, item_id: str, data: Dict[str, Any]) -> bool:
        """Сохранение данных элемента в кэш"""
        return self.set(f"item:{category}:{item_id}", data)
    
    def get_item_data(self, category: str, item_id: str) -> Dict[str, Any]:
        """Получение данных элемента из кэша"""
        return self.get(f"item:{category}:{item_id}") or {}
    
    def set_search_results(self, query: str, results: List[Dict[str, Any]]) -> bool:
        """Сохранение результатов поиска в кэш"""
        # Для поиска используем меньший TTL
        return self.set(f"search:{query}", results, ttl=settings.SEARCH_CACHE_TTL)
    
    def get_search_results(self, query: str) -> List[Dict[str, Any]]:
        """Получение результатов поиска из кэша"""
        return self.get(f"search:{query}") or []

# Создаем экземпляр RedisCache для использования в приложении
redis_cache = RedisCache()