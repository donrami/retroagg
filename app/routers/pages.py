"""
Page Routes - HTML frontend with brutalist 90s aesthetic
"""
from typing import Optional
from datetime import datetime, timedelta
from fastapi import APIRouter, Request, Depends, Query
from fastapi.templating import Jinja2Templates
from sqlalchemy import select, desc, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Article, Source
from app.config import settings


router = APIRouter()
templates = Jinja2Templates(directory=str(settings.TEMPLATES_DIR))


@router.get("/")
async def index(
    request: Request,
    regions: Optional[list[str]] = Query(None, description="Filter by regions"),
    source_id: Optional[str] = Query(None, description="Filter by source ID"),
    date_filter: Optional[str] = Query(None, description="Date filter: 0=Today, 1=3 days, 2=1 week, 3=2 weeks, 4=1 month, 5=3 months, 6=1 year, 7=All time"),
    page: int = Query(1, ge=1),
    db: AsyncSession = Depends(get_db)
):
    """Main page with article feed"""
    
    page_size = settings.PAGE_SIZE
    
    # Handle empty string for source_id (form submits "All Sources" as empty string)
    parsed_source_id: Optional[int] = None
    if source_id and source_id.strip():
        try:
            parsed_source_id = int(source_id)
        except ValueError:
            parsed_source_id = None
    
    # regions is already a list when multiple checkboxes are selected
    region_list = regions if regions else []
    
    # Parse date filter (default to 1 week = 2)
    # 0 = Today, 1 = 3 days, 2 = 1 week
    date_filter_value = 2  # Default to 1 week
    if date_filter is not None:
        try:
            date_filter_value = int(date_filter)
        except ValueError:
            date_filter_value = 2
    
    # Calculate the cutoff date based on filter
    # 0=Today, 1=3 days, 2=1 week, 3=2 weeks, 4=1 month, 5=3 months, 6=1 year, 7=All time
    now = datetime.utcnow()
    if date_filter_value == 0:
        # Today - filter to articles published today
        cutoff_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif date_filter_value == 1:
        # Past 3 days
        cutoff_date = now - timedelta(days=3)
    elif date_filter_value == 2:
        # Past week (default)
        cutoff_date = now - timedelta(days=7)
    elif date_filter_value == 3:
        # Past 2 weeks
        cutoff_date = now - timedelta(days=14)
    elif date_filter_value == 4:
        # Past month
        cutoff_date = now - timedelta(days=30)
    elif date_filter_value == 5:
        # Past 3 months
        cutoff_date = now - timedelta(days=90)
    elif date_filter_value == 6:
        # Past year
        cutoff_date = now - timedelta(days=365)
    else:
        # 7 = All time, no date filter
        cutoff_date = None
    
    # Build article query
    query = select(Article, Source).join(Source, Article.source_id == Source.id)
    
    # Only show non-duplicates by default
    query = query.where(Article.is_duplicate == False)
    
    # Filter by regions (multiple selection support)
    if region_list:
        query = query.where(Source.region.in_(region_list))
    
    if parsed_source_id:
        query = query.where(Article.source_id == parsed_source_id)
    
    # Filter by date (published_at or fetched_at)
    # Only apply date filter if cutoff_date is not None (All time)
    if cutoff_date is not None:
        query = query.where(
            (Article.published_at >= cutoff_date) |
            ((Article.published_at == None) & (Article.fetched_at >= cutoff_date))
        )
    
    query = query.order_by(desc(Article.published_at or Article.fetched_at))
    
    # Count total
    count_query = select(func.count(Article.id)).select_from(Article).join(Source)
    count_query = count_query.where(Article.is_duplicate == False)
    if region_list:
        count_query = count_query.where(Source.region.in_(region_list))
    if parsed_source_id:
        count_query = count_query.where(Article.source_id == parsed_source_id)
    # Apply date filter to count query (only if not All time)
    if cutoff_date is not None:
        count_query = count_query.where(
            (Article.published_at >= cutoff_date) |
            ((Article.published_at == None) & (Article.fetched_at >= cutoff_date))
        )
    
    total_result = await db.execute(count_query)
    total = total_result.scalar()
    
    # Pagination
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)
    
    result = await db.execute(query)
    articles = []
    for article, source in result.all():
        article_dict = {
            "id": article.id,
            "title": article.title,
            "url": article.url,
            "summary": article.summary,
            "published_at": article.published_at,
            "author": article.author,
            "image_url": article.image_url,
            "source_name": source.name,
            "source_region": source.region,
            "source_bias": source.bias_indicator,
        }
        # Debug logging for source names
        print(f"[PAGE_DEBUG] Article {article.id}: source_id={article.source_id}, source_name='{source.name}', title='{article.title[:50]}...'")
        articles.append(article_dict)
    
    # Get all regions for filter
    regions_result = await db.execute(
        select(Source.region).distinct().order_by(Source.region)
    )
    all_regions = [r[0] for r in regions_result.all()]
    
    # Get all sources for filter
    sources_result = await db.execute(
        select(Source).where(Source.is_active == True).order_by(Source.name)
    )
    sources = sources_result.scalars().all()
    
    total_pages = (total + page_size - 1) // page_size
    
    return templates.TemplateResponse("index.html", {
        "request": request,
        "articles": articles,
        "regions": all_regions,
        "selected_regions": region_list,
        "sources": sources,
        "current_source": parsed_source_id,
        "date_filter": date_filter,
        "page": page,
        "total_pages": total_pages,
        "total_articles": total,
        "app_name": settings.APP_NAME,
    })


@router.get("/sources")
async def sources_page(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Sources list page"""
    
    result = await db.execute(
        select(Source).order_by(Source.region, Source.name)
    )
    sources = result.scalars().all()
    
    # Group by region
    sources_by_region = {}
    for source in sources:
        if source.region not in sources_by_region:
            sources_by_region[source.region] = []
        sources_by_region[source.region].append(source)
    
    return templates.TemplateResponse("sources.html", {
        "request": request,
        "sources_by_region": sources_by_region,
        "total_sources": len(sources),
        "app_name": settings.APP_NAME,
    })


@router.get("/api/sources")
async def get_sources_api(
    db: AsyncSession = Depends(get_db)
):
    """API endpoint to get sources data for modal"""
    
    result = await db.execute(
        select(Source).order_by(Source.region, Source.name)
    )
    sources = result.scalars().all()
    
    # Group by region
    sources_by_region = {}
    for source in sources:
        if source.region not in sources_by_region:
            sources_by_region[source.region] = []
        sources_by_region[source.region].append(source)
    
    # Convert to serializable format
    sources_data = {}
    for region, region_sources in sources_by_region.items():
        sources_data[region] = [
            {
                "name": s.name,
                "url": s.url,
                "description": s.description,
                "region": s.region,
                "is_active": s.is_active,
                "bias_indicator": s.bias_indicator,
            }
            for s in region_sources
        ]
    
    return {
        "total_sources": len(sources),
        "regions_count": len(sources_by_region),
        "sources_by_region": sources_data,
    }