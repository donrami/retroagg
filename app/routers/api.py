"""
API Routes - JSON API endpoints
"""
from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, Query, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy import select, desc, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Article, Source
from app.schemas import ArticleResponse, ArticleList, SourceResponse, SourceList
from app.scheduler import manual_fetch
from app.config import settings
from app.services.article_extractor import extract_article


router = APIRouter(prefix="/api", tags=["api"])


@router.get("/articles", response_model=ArticleList)
async def get_articles(
    region: Optional[str] = Query(None, description="Filter by region (Asia, Africa, MENA, Europe, Americas, Global)"),
    include_duplicates: bool = Query(False, description="Include duplicate articles"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(settings.PAGE_SIZE, ge=1, le=100, description="Items per page"),
    db: AsyncSession = Depends(get_db)
):
    """Get articles with optional filtering"""
    

    # Build query
    query = select(Article, Source).join(Source, Article.source_id == Source.id)
    
    # Apply filters
    if not include_duplicates:
        query = query.where(Article.is_duplicate == False)
    
    if region:
        query = query.where(Source.region == region)
    

    # Order by published date (newest first), fallback to fetched_at
    query = query.order_by(desc(Article.published_at or Article.fetched_at))
    
    # Get total count
    count_query = select(func.count(Article.id)).select_from(Article).join(Source)
    if not include_duplicates:
        count_query = count_query.where(Article.is_duplicate == False)
    if region:
        count_query = count_query.where(Source.region == region)

    total_result = await db.execute(count_query)
    total = total_result.scalar()
    
    # Apply pagination
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)
    
    result = await db.execute(query)
    rows = result.all()
    
    # Build response
    articles = []
    for article, source in rows:
        article_dict = {
            "id": article.id,
            "title": article.title,
            "url": article.url,
            "summary": article.summary,
            "published_at": article.published_at,
            "author": article.author,
            "image_url": article.image_url,
            "fetched_at": article.fetched_at,
            "is_duplicate": article.is_duplicate,
            "source_id": article.source_id,
            "source_name": source.name,
            "source_region": source.region,
        }
        articles.append(ArticleResponse.model_validate(article_dict))
    
    return ArticleList(
        articles=articles,
        total=total,
        page=page,
        page_size=page_size
    )


@router.get("/sources", response_model=SourceList)
async def get_sources(
    region: Optional[str] = Query(None, description="Filter by region"),
    is_active: Optional[bool] = Query(True, description="Filter by active status"),
    db: AsyncSession = Depends(get_db)
):
    """Get all news sources"""
    
    query = select(Source)
    
    if region:
        query = query.where(Source.region == region)
    
    if is_active is not None:
        query = query.where(Source.is_active == is_active)
    
    query = query.order_by(Source.region, Source.name)
    
    result = await db.execute(query)
    sources = result.scalars().all()
    
    return SourceList(sources=[SourceResponse.model_validate(s) for s in sources])


@router.post("/refresh")
async def refresh_feeds():
    """Manually trigger RSS feed refresh"""
    try:
        count = await manual_fetch()
        return {
            "status": "success",
            "message": f"Refresh complete. New articles: {count}",
            "new_articles": count
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Refresh failed: {str(e)}"
        }


@router.get("/stats")
async def get_stats(db: AsyncSession = Depends(get_db)):
    """Get basic statistics"""
    
    # Article counts
    articles_result = await db.execute(select(func.count(Article.id)))
    total_articles = articles_result.scalar()
    
    unique_result = await db.execute(
        select(func.count(Article.id)).where(Article.is_duplicate == False)
    )
    unique_articles = unique_result.scalar()
    
    # Source counts
    sources_result = await db.execute(select(func.count(Source.id)))
    total_sources = sources_result.scalar()
    
    active_result = await db.execute(
        select(func.count(Source.id)).where(Source.is_active == True)
    )
    active_sources = active_result.scalar()
    
    # Region breakdown
    region_result = await db.execute(
        select(Source.region, func.count(Source.id))
        .group_by(Source.region)
        .order_by(desc(func.count(Source.id)))
    )
    regions = {row[0]: row[1] for row in region_result.all()}
    
    return {
        "articles": {
            "total": total_articles,
            "unique": unique_articles,
            "duplicates": total_articles - unique_articles
        },
        "sources": {
            "total": total_sources,
            "active": active_sources
        },
        "regions": regions
    }


import logging
logger = logging.getLogger(__name__)

# Cache TTL configuration - use settings for consistency
CONTENT_CACHE_TTL_HOURS = settings.CONTENT_CACHE_TTL_HOURS


@router.get("/read")
async def read_article(url: str = Query(..., description="URL of the article to read"), db: AsyncSession = Depends(get_db)):
    """
    Fetch and extract article content from an external URL.
    Uses Mozilla Readability to parse the page and return clean content.
    Content is cached in the database for 24 hours to reduce external requests.
    """
    if not url:
        raise HTTPException(status_code=400, detail="URL is required")
    
    # Validate URL
    if not url.startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="Invalid URL format")
    
    try:
        # Check if we have cached content in the database
        db_result = await db.execute(
            select(Article, Source).join(Source, Article.source_id == Source.id).where(Article.url == url)
        )
        db_row = db_result.one_or_none()
        article = db_row[0] if db_row else None
        source = db_row[1] if db_row else None
        
        if article and article.full_content and article.is_content_cache_valid(CONTENT_CACHE_TTL_HOURS):
            logger.info(f"[API_READ] Returning cached content for: {url}, source_name='{source.name if source else 'None'}'")
            return {
                "title": article.title,
                "content": article.full_content,
                "byline": article.author,
                "excerpt": "",
                "original_url": url,
                "site_name": source.name if source else "",
                "image_url": article.image_url,
                "inline_media": [],
                "cached": True,
                "cached_at": article.content_fetched_at.isoformat() if article.content_fetched_at else None,
            }
        
        # Fetch fresh content if not cached or cache expired
        logger.info(f"[API_READ] Extracting article from: {url}, source_name='{source.name if source else 'None'}'")
        result = await extract_article(url)
        
        if result is None:
            raise HTTPException(
                status_code=502,
                detail="Failed to fetch or parse the article. The site may be blocking requests or the URL is invalid."
            )
        
        # Use source name from database if available, fallback to extracted site_name
        if source:
            result["site_name"] = source.name
            logger.info(f"[API_READ] Using source name from DB: {source.name}")
        else:
            logger.warning(f"[API_READ] No source found for URL: {url}, using extracted: {result.get('site_name')}")
        
        logger.info(f"[API_READ] Extracted image_url for {url}: {result.get('image_url')}")
        
        # Get author and image from database as fallback
        db_author = None
        db_image_url = None
        if article:
            if article.author:
                db_author = article.author
            if article.image_url:
                db_image_url = article.image_url
                logger.info(f"[API_READ] Found article in DB with image_url: {article.image_url}")
        
        # Use database author as fallback if byline is empty
        if not result.get("byline") and db_author:
            result["byline"] = db_author
        
        # Use database image_url as fallback if no extracted image
        if not result.get("image_url") and db_image_url:
            logger.info(f"[API_READ] Using DB image_url as fallback: {db_image_url}")
            result["image_url"] = db_image_url
        
        # Cache the extracted content in the database
        if article:
            article.full_content = result.get("content", "")
            article.content_fetched_at = datetime.utcnow()
            article.content_cache_expires_at = datetime.utcnow() + timedelta(hours=CONTENT_CACHE_TTL_HOURS)
            await db.commit()
            logger.info(f"[API_READ] Cached content for article ID {article.id}")
        
        result["cached"] = False
        result["cached_at"] = None
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing article: {str(e)}")


@router.get("/read/{article_id}")
async def read_article_by_id(article_id: int, db: AsyncSession = Depends(get_db)):
    """
    Fetch and extract article content by database ID.
    Looks up the article URL and extracts its content.
    Content is cached in the database for 24 hours to reduce external requests.
    """
    result = await db.execute(
        select(Article, Source).join(Source, Article.source_id == Source.id).where(Article.id == article_id)
    )
    db_row = result.one_or_none()
    article = db_row[0] if db_row else None
    source = db_row[1] if db_row else None
    
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    
    if not article.url:
        raise HTTPException(status_code=400, detail="Article has no URL")
    
    # Check if we have cached content
    if article.full_content and article.is_content_cache_valid(CONTENT_CACHE_TTL_HOURS):
        logger.info(f"[API_READ] Returning cached content for article ID: {article_id}, source_name='{source.name if source else 'None'}'")
        return {
            "title": article.title,
            "content": article.full_content,
            "byline": article.author,
            "excerpt": "",
            "original_url": article.url,
            "site_name": source.name if source else "",
            "image_url": article.image_url,
            "inline_media": [],
            "cached": True,
            "cached_at": article.content_fetched_at.isoformat() if article.content_fetched_at else None,
        }
    
    try:
        result = await extract_article(article.url)
        
        if result is None:
            raise HTTPException(
                status_code=502,
                detail="Failed to fetch or parse the article"
            )
        
        # Use source name from database if available, fallback to extracted site_name
        if source:
            result["site_name"] = source.name
            logger.info(f"[API_READ] Using source name from DB: {source.name}")
        else:
            logger.warning(f"[API_READ] No source found for article ID: {article_id}, using extracted: {result.get('site_name')}")
        
        # Use database author as fallback if byline is empty
        if not result.get("byline") and article.author:
            result["byline"] = article.author
        
        # Use database image_url as fallback if no extracted image
        if not result.get("image_url") and article.image_url:
            logger.info(f"[API_READ] Using DB image_url as fallback: {article.image_url}")
            result["image_url"] = article.image_url
        
        # Cache the extracted content
        article.full_content = result.get("content", "")
        article.content_fetched_at = datetime.utcnow()
        article.content_cache_expires_at = datetime.utcnow() + timedelta(hours=CONTENT_CACHE_TTL_HOURS)
        await db.commit()
        logger.info(f"[API_READ] Cached content for article ID {article.id}")
        
        result["cached"] = False
        result["cached_at"] = None
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing article: {str(e)}")


@router.post("/read/{article_id}/refresh")
async def refresh_article_content(article_id: int, db: AsyncSession = Depends(get_db)):
    """
    Force refresh article content, bypassing the cache.
    Clears cached content and re-fetches from the source.
    """
    result = await db.execute(
        select(Article, Source).join(Source, Article.source_id == Source.id).where(Article.id == article_id)
    )
    db_row = result.one_or_none()
    article = db_row[0] if db_row else None
    source = db_row[1] if db_row else None
    
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    
    if not article.url:
        raise HTTPException(status_code=400, detail="Article has no URL")
    
    try:
        # Clear cached content first
        article.full_content = None
        article.content_fetched_at = None
        article.content_cache_expires_at = None
        await db.commit()
        
        # Fetch fresh content
        logger.info(f"[API_READ] Force refreshing article ID: {article_id}, source_name='{source.name if source else 'None'}'")
        result = await extract_article(article.url)
        
        if result is None:
            raise HTTPException(
                status_code=502,
                detail="Failed to fetch or parse the article"
            )
        
        # Use source name from database if available
        if source:
            result["site_name"] = source.name
            logger.info(f"[API_READ] Using source name from DB: {source.name}")
        
        # Cache the new content
        article.full_content = result.get("content", "")
        article.content_fetched_at = datetime.utcnow()
        article.content_cache_expires_at = datetime.utcnow() + timedelta(hours=CONTENT_CACHE_TTL_HOURS)
        await db.commit()
        
        result["cached"] = False
        result["cached_at"] = article.content_fetched_at.isoformat()
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error refreshing article: {str(e)}")
