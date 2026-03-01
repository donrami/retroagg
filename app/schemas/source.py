"""
Source Pydantic schemas
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, HttpUrl


class SourceBase(BaseModel):
    name: str
    url: str
    rss_url: str
    region: str
    language: str = "en"
    bias_indicator: str = "Unknown"
    description: Optional[str] = None


class SourceCreate(SourceBase):
    pass


class SourceResponse(SourceBase):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    is_active: bool
    last_fetched: Optional[datetime] = None
    created_at: datetime


class SourceList(BaseModel):
    sources: list[SourceResponse]
