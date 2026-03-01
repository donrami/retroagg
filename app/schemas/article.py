"""
Article Pydantic schemas
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict


class ArticleBase(BaseModel):
    title: str
    url: str
    summary: Optional[str] = None
    published_at: Optional[datetime] = None
    author: Optional[str] = None
    image_url: Optional[str] = None


class ArticleCreate(ArticleBase):
    source_id: int
    content_hash: Optional[str] = None


class ArticleResponse(ArticleBase):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    source_id: int
    source_name: Optional[str] = None
    source_region: Optional[str] = None
    fetched_at: datetime
    is_duplicate: bool


class ArticleList(BaseModel):
    articles: list[ArticleResponse]
    total: int
    page: int
    page_size: int
