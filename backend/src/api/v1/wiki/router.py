"""
Маршруты для Cyberpunk 2077 Wiki API
"""

import os
import json
import logging
import asyncio
from typing import List, Dict, Any, Optional, Union
from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException, Query, Path, BackgroundTasks, Depends
from fastapi.responses import JSONResponse, ORJSONResponse

from src.app.scraper.wiki_scraper import scrape_category, get_all_wiki_categories, initialize_wiki, CATEGORIES, get_page_metadata
from src.app.redis.redis_cache import redis_cache, get_redis_sync, get_redis_async
from src.api.schemas import CategoryList, WikiItem, SearchResult, CategoryResult, APIStatus
from src.core.config import settings

# Настройки
API_VERSION = settings.API_V1_STR.strip("/")
DATA_DIR = settings.TEMP_DIR
DEBUG_MODE = settings.DEBUG_MODE

# Создаем API Router
router = APIRouter(
    prefix="/wiki",
    tags=["Wiki"],
    responses={404: {"description": "Элемент не найден"}},
)

# Настройка логирования
logger = logging.getLogger("wiki_api")

@router.get("/", tags=["Info"])
async def root():
    """Корневой эндпоинт с информацией об API"""
    return {
        "name": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "description": "API для получения данных из Cyberpunk 2077 Wiki",
        "endpoints": {
            "categories": f"/api/{API_VERSION}/wiki/categories",
            "search": f"/api/{API_VERSION}/wiki/search?q=your_query",
            "category_items": f"/api/{API_VERSION}/wiki/categories/name",
            "item_details": f"/api/{API_VERSION}/wiki/items/item_title"
        },
        "documentation": "/docs"
    }

@router.get("/status", response_model=APIStatus, tags=["System"])
async def get_api_status():
    """Получить статус API и подключенных сервисов"""
    # Проверяем Wiki Scraper
    wiki_ready = True
    try:
        initialize_wiki()
    except:
        wiki_ready = False
    
    # Проверяем Redis
    redis_ready = redis_cache.ping()
    
    # Получаем список кэшированных категорий
    cached = []
    try:
        for cat_key, cat_name in CATEGORIES.items():
            if redis_cache.get_category_data(cat_key):
                cached.append(cat_key)
    except:
        pass
    
    return APIStatus(
        status="online",
        version=settings.VERSION,
        wiki_scraper_ready=wiki_ready,
        redis_ready=redis_ready,
        cached_categories=cached
    )

async def scrape_category_async(category_name: str, background_tasks: BackgroundTasks):
    """Асинхронно запускает скрапинг категории и сохраняет в Redis"""
    def _scrape():
        try:
            # Запускаем скрапинг
            result = scrape_category(category_name)
            
            # Сохраняем в Redis
            if result:
                redis_cache.set_category_data(category_name, result)
                
                # Сохраняем каждый элемент отдельно для быстрого доступа
                for title, item_data in result.items():
                    redis_cache.set_item_data(title, item_data)
                
                logger.info(f"Категория {category_name} успешно загружена в кэш ({len(result)} элементов)")
            else:
                logger.warning(f"Скрапинг категории {category_name} не вернул данных")
                
            # Также сохраняем на диск как резервную копию
            try:
                category_dir = os.path.join(DATA_DIR, category_name)
                os.makedirs(category_dir, exist_ok=True)
                
                # Сохраняем полный файл категории
                filepath = os.path.join(DATA_DIR, f"{category_name}.json")
                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(result, f, ensure_ascii=False, indent=2)
                
                # Сохраняем каждый элемент в отдельный файл
                for title, item_data in result.items():
                    # Используем безопасное имя файла
                    safe_title = "".join(c if c.isalnum() else "_" for c in title)
                    item_path = os.path.join(category_dir, f"{safe_title}.json")
                    with open(item_path, 'w', encoding='utf-8') as f:
                        json.dump(item_data, f, ensure_ascii=False, indent=2)
                
                logger.info(f"Категория {category_name} сохранена на диск")
            except Exception as e:
                logger.error(f"Ошибка сохранения категории {category_name} на диск: {str(e)}")
                
        except Exception as e:
            logger.error(f"Ошибка скрапинга категории {category_name}: {str(e)}")
    
    # Добавляем задачу в фоновый поток
    background_tasks.add_task(_scrape)
    return {"status": "Скрапинг запущен в фоновом режиме"}

@router.get("/categories", response_model=CategoryList)
async def get_categories(
    redis: Any = Depends(get_redis_sync)
):
    """Получить список всех доступных категорий"""
    # Получаем категории
    try:
        # Сначала из кэша Redis
        categories = redis.get_all_categories()
        
        if not categories:
            # Если нет в кэше, получаем из API
            categories = get_all_wiki_categories()
            
            # И сохраняем в кэш
            if categories:
                redis.set_all_categories(categories)
        
        # Добавляем встроенные категории из конфигурации
        if not categories:
            categories = []
        
        # Добавляем ключи из CATEGORIES, если их нет в списке 
        for cat_key in CATEGORIES.keys():
            if cat_key not in categories:
                categories.append(cat_key)
        
        return {"categories": categories}
    except Exception as e:
        logger.error(f"Ошибка получения категорий: {str(e)}")
        raise HTTPException(status_code=500, detail="Не удалось получить категории")

@router.get("/categories/{category_name}", response_model=CategoryResult)
async def get_category_items(
    background_tasks: BackgroundTasks,
    category_name: str = Path(..., description="Название категории"),
    limit: int = Query(settings.DEFAULT_ITEMS_LIMIT, description="Ограничение количества элементов"),
    offset: int = Query(0, description="Смещение для пагинации"),
    refresh: bool = Query(False, description="Принудительно обновить данные"),
    redis: Any = Depends(get_redis_sync)
):
    """Получить элементы определенной категории"""
    # Проверяем существование категории
    if category_name not in CATEGORIES:
        raise HTTPException(status_code=404, detail=f"Категория '{category_name}' не найдена")
    
    # Проверяем наличие категории в кэше
    category_data = None
    need_refresh = refresh
    
    if not need_refresh:
        # Получаем из Redis если не требуется обновление
        category_data = redis.get_category_data(category_name)
    
    # Если данных нет или требуется обновление
    if not category_data or need_refresh:
        try:
            # Запускаем скрапинг в фоновом режиме
            await scrape_category_async(category_name, background_tasks)
            
            # Если данных вообще нет, пробуем загрузить с диска
            if not category_data:
                try:
                    filepath = os.path.join(DATA_DIR, f"{category_name}.json")
                    if os.path.exists(filepath):
                        with open(filepath, 'r', encoding='utf-8') as f:
                            category_data = json.load(f)
                            logger.info(f"Категория {category_name} загружена с диска")
                except Exception as e:
                    logger.error(f"Ошибка загрузки категории {category_name} с диска: {str(e)}")
            
            # Если всё еще нет данных, возвращаем что обработка началась
            if not category_data:
                return JSONResponse(
                    status_code=202,
                    content={"message": f"Данные для категории '{category_name}' обрабатываются. Пожалуйста, повторите запрос позже."}
                )
        except Exception as e:
            logger.error(f"Ошибка скрапинга категории {category_name}: {str(e)}")
            # Если не удалось обновить, но данные есть - используем их
            if not category_data:
                raise HTTPException(status_code=500, detail=f"Не удалось получить данные для категории '{category_name}'")
    
    # Применяем пагинацию
    items_list = list(category_data.values())
    total_items = len(items_list)
    
    # Если запрошенный offset больше общего количества элементов, возвращаем пустой список
    if offset >= total_items:
        return CategoryResult(
            category=category_name,
            total=total_items,
            items=[]
        )
    
    # Получаем подмножество элементов
    paginated_items = items_list[offset:offset + limit]
    
    # Форматируем в WikiItem
    formatted_items = []
    for item_data in paginated_items:
        try:
            wiki_item = WikiItem(**item_data)
            formatted_items.append(wiki_item)
        except Exception as e:
            logger.error(f"Ошибка форматирования WikiItem: {str(e)}")
    
    return CategoryResult(
        category=category_name,
        total=total_items,
        items=formatted_items
    )

@router.get("/items/{item_title}", response_model=WikiItem)
async def get_item_details(
    background_tasks: BackgroundTasks,
    item_title: str = Path(..., description="Название элемента"),
    redis: Any = Depends(get_redis_sync)
):
    """Получить детальную информацию по элементу"""
    try:
        # Пробуем получить из кэша Redis
        item_data = redis.get_item_data(item_title)
        
        if not item_data:
            # Если нет в кэше, запускаем поиск во всех категориях
            for cat_key, cat_name in CATEGORIES.items():
                category_data = redis.get_category_data(cat_key)
                
                if category_data and item_title in category_data:
                    item_data = category_data[item_title]
                    redis.set_item_data(item_title, item_data)
                    break
        
        if not item_data:
            # Если всё еще нет, пробуем получить напрямую из Wiki
            try:
                item_data = get_page_metadata(item_title)
                
                if item_data:
                    # Кэшируем полученные данные
                    redis.set_item_data(item_title, item_data)
                    
                    # Сохраняем в файл для каждой возможной категории
                    for category in CATEGORIES.keys():
                        category_dir = os.path.join(DATA_DIR, category)
                        os.makedirs(category_dir, exist_ok=True)
                        
                        # Используем безопасное имя файла
                        safe_title = "".join(c if c.isalnum() else "_" for c in item_title)
                        item_path = os.path.join(category_dir, f"{safe_title}.json")
                        with open(item_path, 'w', encoding='utf-8') as f:
                            json.dump(item_data, f, ensure_ascii=False, indent=2)
            except Exception as e:
                logger.error(f"Ошибка получения метаданных для {item_title}: {str(e)}")
        
        if not item_data:
            raise HTTPException(status_code=404, detail=f"Элемент '{item_title}' не найден")
        
        return WikiItem(**item_data)
    except HTTPException:
        # Передаем исключение дальше
        raise
    except Exception as e:
        logger.error(f"Ошибка получения детальной информации для {item_title}: {str(e)}")
        raise HTTPException(status_code=500, detail="Ошибка получения детальной информации")

def search_in_cache(query: str, categories: Optional[List[str]] = None, 
                    redis: Any = get_redis_sync()) -> List[Dict[str, Any]]:
    """Поиск в кэше Redis"""
    results = []
    
    # Нормализуем запрос
    normalized_query = query.lower().strip()
    
    # Проверяем наличие кэшированных результатов поиска
    cache_results = redis.get_search_results(normalized_query)
    if cache_results:
        # Фильтруем по категориям, если указаны
        if categories:
            return [item for item in cache_results if any(cat in item.get("categories", []) for cat in categories)]
        return cache_results
    
    # Перебираем все категории в кэше
    for cat_key, cat_name in CATEGORIES.items():
        # Если фильтр по категориям и текущая категория не в списке, пропускаем
        if categories and cat_key not in categories and cat_name not in categories:
            continue
            
        category_data = redis.get_category_data(cat_key)
        if not category_data:
            continue
            
        # Ищем в данных категории
        for title, item_data in category_data.items():
            item_matched = False
            
            # Проверяем название
            if normalized_query in title.lower():
                item_matched = True
            # Проверяем описание
            elif item_data.get("description") and normalized_query in item_data["description"].lower():
                item_matched = True
            # Проверяем секции
            elif item_data.get("sections"):
                for section in item_data["sections"]:
                    if normalized_query in section.get("title", "").lower() or normalized_query in section.get("content", "").lower():
                        item_matched = True
                        break
            
            if item_matched:
                # Добавляем категорию в элемент, если она отсутствует
                if "categories" not in item_data:
                    item_data["categories"] = []
                if cat_key not in item_data["categories"]:
                    item_data["categories"].append(cat_key)
                
                results.append(item_data)
    
    # Ограничиваем количество результатов чтобы не перегружать кэш
    results = results[:settings.MAX_SEARCH_RESULTS]
    
    # Кэшируем результаты поиска
    redis.set_search_results(normalized_query, results)
    
    return results

@router.get("/search", response_model=SearchResult)
async def search_items(
    q: str = Query(..., description="Поисковый запрос"),
    categories: Optional[List[str]] = Query(None, description="Фильтр по категориям"),
    limit: int = Query(settings.SEARCH_ITEMS_LIMIT, description="Ограничение количества результатов"),
    offset: int = Query(0, description="Смещение для пагинации"),
    redis: Any = Depends(get_redis_sync)
):
    """Поиск элементов по запросу"""
    if not q or len(q.strip()) < 2:
        raise HTTPException(status_code=400, detail="Поисковый запрос должен содержать не менее 2 символов")
    
    try:
        # Ищем в кэше
        results = search_in_cache(q, categories, redis)
        
        # Применяем пагинацию
        total_results = len(results)
        paginated_results = results[offset:offset + limit]
        
        # Форматируем результаты
        formatted_results = []
        for item_data in paginated_results:
            try:
                wiki_item = WikiItem(**item_data)
                formatted_results.append(wiki_item)
            except Exception as e:
                logger.error(f"Ошибка форматирования результата поиска: {str(e)}")
        
        return SearchResult(
            query=q,
            total=total_results,
            results=formatted_results
        )
    except Exception as e:
        logger.error(f"Ошибка поиска: {str(e)}")
        raise HTTPException(status_code=500, detail="Ошибка выполнения поиска")

@router.get("/refresh/{category_name}", tags=["Admin"])
async def refresh_category(
    background_tasks: BackgroundTasks,
    category_name: str = Path(..., description="Название категории для обновления"),
    force: bool = Query(False, description="Принудительно обновить даже если данные недавно обновлялись")
):
    """Принудительно обновить данные категории"""
    # Проверяем, существует ли категория
    if category_name not in CATEGORIES.keys() and category_name != "all":
        raise HTTPException(status_code=404, detail=f"Категория '{category_name}' не найдена")
    
    if category_name == "all":
        # Обновляем все категории
        for cat_key in CATEGORIES.keys():
            await scrape_category_async(cat_key, background_tasks)
        return {"status": "success", "message": "Обновление всех категорий запущено в фоновом режиме"}
    else:
        # Обновляем одну категорию
        await scrape_category_async(category_name, background_tasks)
        return {"status": "success", "message": f"Обновление категории '{category_name}' запущено в фоновом режиме"}

@router.delete("/cache", tags=["Admin"])
async def clear_cache(
    categories: Optional[List[str]] = Query(None, description="Список категорий для очистки (если не указано, будет очищен весь кэш)")
):
    """Очистить кэш данных"""
    try:
        if not categories:
            # Очищаем весь кэш
            result = redis_cache.clear_all_cache()
            message = "Весь кэш успешно очищен"
        else:
            # Очищаем только указанные категории
            cleared = []
            for cat in categories:
                if redis_cache.invalidate_category(cat):
                    cleared.append(cat)
            
            message = f"Кэш категорий [{', '.join(cleared)}] успешно очищен" if cleared else "Ни одна категория не была очищена"
            result = bool(cleared)
        
        return {"status": "success" if result else "warning", "message": message}
    except Exception as e:
        logger.error(f"Ошибка очистки кэша: {str(e)}")
        raise HTTPException(status_code=500, detail="Ошибка очистки кэша")
