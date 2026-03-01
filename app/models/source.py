"""
Source model for news outlets
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text
from sqlalchemy.orm import relationship

from app.database import Base


class Source(Base):
    """News source/outlet model with geographic and bias indicators"""
    __tablename__ = "sources"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False, index=True)
    url = Column(String(500), nullable=False)
    rss_url = Column(String(500), nullable=False, unique=True)
    region = Column(String(50), nullable=False, index=True)  # Asia, Africa, MENA, Europe, Americas, Global
    language = Column(String(10), default="en")
    bias_indicator = Column(String(20), default="Unknown")  # Left, Center-Left, Center, Center-Right, Right, Unknown
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    last_fetched = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    articles = relationship("Article", back_populates="source")
    
    def __repr__(self):
        return f"<Source(id={self.id}, name='{self.name}', region='{self.region}')>"
