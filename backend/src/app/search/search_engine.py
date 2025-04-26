#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Модуль поискового движка для Wiki-Cyberpunk2077
----------------------------------------------
Предоставляет класс SearchEngine для обработки поисковых запросов
и получения релевантных результатов из базы данных.
"""

from typing import List, Dict, Any, Optional, Tuple
import asyncio
import re
import json
import logging
from datetime import datetime

import aioredis

from src.core.config import settings

# Настройка логгера
logger = logging.getLogger(__name__)

class SearchEngine:
    """
    Класс, отвечающий за поиск по wiki-контенту.
    Поддерживает поиск по всем категориям или в пределах одной категории,
    а также предоставляет функциональность автодополнения.
    """
    
    def __init__(self):
        """
        Инициализирует экземпляр поискового движка с настройками из конфигурации.
        """
        self.max_results = settings.SEARCH_MAX_RESULTS
        self.min_query_length = settings.SEARCH_MIN_QUERY_LENGTH
        self.categories = settings.CATEGORIES
        self.redis = None
        self.search_cache_ttl = settings.SEARCH_CACHE_TTL
    
    async def initialize(self):
        """
        Асинхронная инициализация соединения с Redis.
        """
        if not self.redis:
            self.redis = await aioredis.from_url(settings.REDIS_URL)
    
    async def close(self):
        """
        Закрывает соединение с Redis при завершении работы.
        """
        if self.redis:
            await self.redis.close()

    async def search_all(self, query: str, limit: Optional[int] = None) -> Dict[str, List[Dict[str, Any]]]:
        """
        Выполняет поиск по всем категориям данных.
        
        Args:
            query: Поисковый запрос
            limit: Максимальное количество результатов (опционально)
        
        Returns:
            Словарь с результатами поиска по категориям
        """
        await self.initialize()
        
        # Проверяем минимальную длину запроса
        if len(query.strip()) < self.min_query_length:
            return {
                "error": f"Поисковый запрос должен содержать не менее {self.min_query_length} символов",
                "results": {}
            }
        
        # Задаем лимит результатов
        actual_limit = limit if limit is not None else self.max_results
        
        # Проверяем кэш
        cache_key = f"search:all:{query.lower()}:{actual_limit}"
        cached_results = await self.redis.get(cache_key)
        if cached_results:
            return json.loads(cached_results)
        
        # Выполняем поиск по всем категориям параллельно
        tasks = []
        for category in self.categories:
            tasks.append(self.search_in_category(query, category, actual_limit))
        
        # Собираем результаты
        results = {}
        category_results = await asyncio.gather(*tasks)
        
        for i, category in enumerate(self.categories):
            if category_results[i].get("results"):
                results[category] = category_results[i]["results"]
        
        # Кэшируем результаты
        await self.redis.set(
            cache_key, 
            json.dumps({"results": results}), 
            ex=self.search_cache_ttl
        )
        
        return {"results": results}

    async def search_in_category(self, query: str, category: str, limit: Optional[int] = None) -> Dict[str, Any]:
        """
        Выполняет поиск по конкретной категории.
        
        Args:
            query: Поисковый запрос
            category: Категория для поиска
            limit: Максимальное количество результатов (опционально)
        
        Returns:
            Словарь с результатами поиска в указанной категории
        """
        await self.initialize()
        
        # Проверяем минимальную длину запроса
        if len(query.strip()) < self.min_query_length:
            return {
                "error": f"Поисковый запрос должен содержать не менее {self.min_query_length} символов",
                "results": []
            }
        
        # Проверяем существование категории
        if category not in self.categories:
            return {
                "error": f"Категория '{category}' не существует",
                "results": []
            }
        
        # Задаем лимит результатов
        actual_limit = limit if limit is not None else self.max_results
        
        # Проверяем кэш
        cache_key = f"search:{category}:{query.lower()}:{actual_limit}"
        cached_results = await self.redis.get(cache_key)
        if cached_results:
            return json.loads(cached_results)
        
        # Нормализуем запрос
        normalized_query = normalize_text(query)
        
        # Создаем SQL-запрос
        # Используем полнотекстовый поиск PostgreSQL для эффективного поиска
        sql_query = f"""
        SELECT id, title, description, content, url, image_url, metadata
        FROM {category}
        WHERE 
            to_tsvector('russian', title || ' ' || coalesce(description, '') || ' ' || coalesce(content, '')) @@ 
            plainto_tsquery('russian', :query)
        ORDER BY 
            ts_rank(to_tsvector('russian', title), plainto_tsquery('russian', :query)) * 2.0 +
            ts_rank(to_tsvector('russian', coalesce(description, '')), plainto_tsquery('russian', :query)) * 1.5 +
            ts_rank(to_tsvector('russian', coalesce(content, '')), plainto_tsquery('russian', :query))
        DESC LIMIT :limit
        """
        
        # Получаем сессию базы данных
        async with get_session() as session:
            result = await session.execute(
                text(sql_query),
                {"query": normalized_query, "limit": actual_limit}
            )
            rows = result.fetchall()
        
        # Обрабатываем результаты
        results = []
        for row in rows:
            item = {
                "id": row.id,
                "title": row.title,
                "description": row.description,
                "url": row.url,
                "image_url": row.image_url,
                "category": category
            }
            
            # Добавляем метаданные, если они есть
            if row.metadata:
                if isinstance(row.metadata, str):
                    metadata = json.loads(row.metadata)
                else:
                    metadata = row.metadata
                item.update({"metadata": metadata})
            
            # Добавляем выдержку из контента, если он есть
            if row.content:
                # Находим фрагмент, содержащий поисковый запрос
                content = row.content.lower()
                query_pos = content.find(query.lower())
                
                if query_pos >= 0:
                    start = max(0, query_pos - 50)
                    end = min(len(content), query_pos + len(query) + 50)
                    
                    # Создаем выдержку
                    if start > 0:
                        excerpt = "..." + content[start:end] + "..."
                    else:
                        excerpt = content[start:end] + "..."
                    
                    item["excerpt"] = excerpt
            
            results.append(item)
        
        # Кэшируем результаты
        response = {"results": results}
        await self.redis.set(
            cache_key, 
            json.dumps(response), 
            ex=self.search_cache_ttl
        )
        
        return response

    async def get_suggestions(self, query: str, limit: int = 10) -> Dict[str, List[str]]:
        """
        Получает предложения для автодополнения на основе запроса.
        
        Args:
            query: Начало поискового запроса
            limit: Максимальное количество предложений
        
        Returns:
            Список предложений для автодополнения
        """
        await self.initialize()
        
        # Проверяем минимальную длину запроса
        if len(query.strip()) < 2:  # Для автодополнения используем минимум 2 символа
            return {"suggestions": []}
        
        # Проверяем кэш
        cache_key = f"suggestions:{query.lower()}:{limit}"
        cached_suggestions = await self.redis.get(cache_key)
        if cached_suggestions:
            return json.loads(cached_suggestions)
        
        # Нормализуем запрос
        normalized_query = normalize_text(query)
        
        # Создаем SQL-запрос для получения предложений из всех категорий
        suggestions = set()
        
        # Получаем сессию базы данных
        async with get_session() as session:
            for category in self.categories:
                # Строим SQL-запрос для автодополнения
                sql_query = f"""
                SELECT title 
                FROM {category}
                WHERE 
                    to_tsvector('russian', title) @@ 
                    to_tsquery('russian', :query || ':*')
                LIMIT :limit
                """
                
                try:
                    result = await session.execute(
                        text(sql_query),
                        {"query": normalized_query, "limit": limit}
                    )
                    
                    for row in result.fetchall():
                        suggestions.add(row.title)
                        
                        # Если достигли лимита, прерываем поиск
                        if len(suggestions) >= limit:
                            break
                            
                except Exception as e:
                    logger.error(f"Ошибка при получении предложений из категории {category}: {str(e)}")
                    continue
                    
                # Если достигли лимита, прерываем поиск по категориям
                if len(suggestions) >= limit:
                    break
        
        # Преобразуем в список и сортируем
        suggestions_list = sorted(list(suggestions))[:limit]
        
        # Кэшируем результаты на более короткое время
        response = {"suggestions": suggestions_list}
        await self.redis.set(
            cache_key, 
            json.dumps(response), 
            ex=self.search_cache_ttl // 2  # Используем половину TTL для поиска
        )
        
        return response 