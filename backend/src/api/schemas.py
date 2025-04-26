# Модели данных для API
from typing import Dict, List, Any, Optional
from pydantic import BaseModel, Field

class CategoryList(BaseModel):
    """Список доступных категорий"""
    categories: List[str] = Field(..., description="Список доступных категорий")

class WikiItem(BaseModel):
    """Элемент из Wiki (персонаж, локация, оружие и т.д.)"""
    id: Optional[int] = Field(None, description="ID страницы в Wiki")
    title: str = Field(..., description="Название страницы")
    url: str = Field(..., description="URL страницы в Wiki")
    description: Optional[str] = Field(None, description="Описание")
    categories: List[str] = Field(default_factory=list, description="Категории")
    images: List[Dict[str, str]] = Field(default_factory=list, description="Изображения")
    sections: List[Dict[str, str]] = Field(default_factory=list, description="Разделы")
    related_pages: List[str] = Field(default_factory=list, description="Связанные страницы")
    infobox: Dict[str, Any] = Field(default_factory=dict, description="Данные из инфобокса")

class SearchResult(BaseModel):
    """Результаты поиска"""
    query: str = Field(..., description="Поисковый запрос")
    total: int = Field(..., description="Общее количество результатов")
    results: List[WikiItem] = Field(..., description="Результаты поиска")

class CategoryResult(BaseModel):
    """Результаты для категории"""
    category: str = Field(..., description="Название категории")
    total: int = Field(..., description="Общее количество элементов")
    items: List[WikiItem] = Field(..., description="Элементы категории")

class APIStatus(BaseModel):
    """Статус API и его компонентов"""
    status: str = Field(..., description="Статус API")
    version: str = Field(..., description="Версия API")
    wiki_scraper_ready: bool = Field(..., description="Доступность Wiki Scraper")
    redis_ready: bool = Field(..., description="Доступность Redis")
    cached_categories: List[str] = Field(..., description="Кэшированные категории")

