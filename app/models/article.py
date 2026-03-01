"""
Article model with deduplication support
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean, ForeignKey
from sqlalchemy.orm import relationship

from app.database import Base


class Article(Base):
    """News article model with deduplication fields"""
    __tablename__ = "articles"
    
    id = Column(Integer, primary_key=True, index=True)
    source_id = Column(Integer, ForeignKey("sources.id"), nullable=False, index=True)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=True, index=True)
    
    # Article content
    title = Column(String(500), nullable=False, index=True)
    url = Column(String(1000), nullable=False)
    summary = Column(Text, nullable=True)
    
    # Timestamps
    published_at = Column(DateTime, nullable=True, index=True)
    fetched_at = Column(DateTime, default=datetime.utcnow, index=True)
    
    # Deduplication
    content_hash = Column(String(64), nullable=True, index=True)
    is_duplicate = Column(Boolean, default=False, index=True)
    duplicate_of_id = Column(Integer, ForeignKey("articles.id"), nullable=True)
    
    # Additional metadata
    author = Column(String(200), nullable=True)
    image_url = Column(String(500), nullable=True)
    
    # Cached full article content (for multi-user deployment)
    full_content = Column(Text, nullable=True)  # Extracted HTML content
    content_fetched_at = Column(DateTime, nullable=True)  # When content was cached
    content_cache_expires_at = Column(DateTime, nullable=True)  # Cache expiration
    
    # Relationships
    source = relationship("Source", back_populates="articles")
    category = relationship("Category", back_populates="articles")
    
    def __repr__(self):
        return f"<Article(id={self.id}, title='{self.title[:50]}...', source_id={self.source_id})>"
    
    def is_content_cache_valid(self, cache_ttl_hours: int = 24) -> bool:
        """Check if cached content is still valid"""
        if not self.full_content or not self.content_cache_expires_at:
            return False
        return datetime.utcnow() < self.content_cache_expires_at
