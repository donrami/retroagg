"""
RSS Fetcher Service - Async RSS feed fetching and parsing
"""
import asyncio
import hashlib
import logging
from datetime import datetime, timezone
from typing import List, Dict, Optional
from urllib.parse import urlparse

import httpx
import feedparser
from dateutil import parser as date_parser
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import AsyncSessionLocal
from app.models import Source, Article

# Diagnostic logger for fetch timing issues
diag_logger = logging.getLogger("app.rss_fetcher.diagnostics")


class RSSFetcher:
    """Async RSS feed fetcher with retry logic"""
    
    def __init__(self):
        self.timeout = settings.REQUEST_TIMEOUT
        self.max_retries = settings.MAX_RETRIES
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        ]
    
    async def fetch_feed(self, url: str, retries: int = 0) -> Optional[str]:
        """Fetch RSS feed content with retry logic"""
        import random
        
        headers = {
            "User-Agent": random.choice(self.user_agents),
            "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, */*",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
        }
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                response = await client.get(url, headers=headers)
                response.raise_for_status()
                return response.text
        except httpx.HTTPStatusError as e:
            if retries < self.max_retries and e.response.status_code in [429, 500, 502, 503, 504]:
                await asyncio.sleep(2 ** retries)  # Exponential backoff
                return await self.fetch_feed(url, retries + 1)
            print(f"HTTP error fetching {url}: {e}")
            return None
        except httpx.RequestError as e:
            if retries < self.max_retries:
                await asyncio.sleep(2 ** retries)
                return await self.fetch_feed(url, retries + 1)
            print(f"Request error fetching {url}: {e}")
            return None
        except Exception as e:
            print(f"Unexpected error fetching {url}: {e}")
            return None
    
    def parse_feed(self, content: str) -> List[Dict]:
        """Parse RSS/Atom feed content"""
        feed = feedparser.parse(content)
        entries = []
        
        for entry in feed.entries:
            parsed_entry = self._normalize_entry(entry)
            if parsed_entry:
                entries.append(parsed_entry)
        
        return entries
    
    def _extract_image_from_entry(self, entry) -> Optional[str]:
        """Extract image URL from RSS entry using multiple methods."""
        # Method 1: Try media:content
        if hasattr(entry, 'media_content') and entry.media_content:
            for media in entry.media_content:
                if media.get('type', '').startswith('image/'):
                    url = media.get('url')
                    if url:
                        return url
        
        # Method 2: Try media:thumbnail
        if hasattr(entry, 'media_thumbnails') and entry.media_thumbnails:
            for thumb in entry.media_thumbnails:
                url = thumb.get('url')
                if url:
                    return url
        
        # Method 3: Try enclosure tag
        if hasattr(entry, 'enclosures') and entry.enclosures:
            for enc in entry.enclosures:
                if enc.get('type', '').startswith('image/'):
                    url = enc.get('href')
                    if url:
                        return url
        
        # Method 4: Try itunes:image
        if hasattr(entry, 'itunes_image') and entry.itunes_image:
            url = entry.itunes_image.get('href')
            if url:
                return url
        
        # Method 5: Try to find image in content (summary/description)
        summary = entry.get('summary', '') or entry.get('description', '')
        if summary:
            import re
            # Match img src attributes
            img_matches = re.findall(r'<img[^>]+src=["\']([^"\']+)["\']', summary, re.IGNORECASE)
            for img_url in img_matches:
                if not any(x in img_url.lower() for x in ['pixel', '1x1', 'spacer', 'blank', 'icon', 'logo']):
                    return img_url
        
        return None
    
    def _normalize_entry(self, entry) -> Optional[Dict]:
        """Normalize a feed entry to standard format"""
        try:
            # Extract title
            title = entry.get('title', '').strip()
            if not title:
                return None
            
            # Extract URL
            link = entry.get('link', '')
            if not link:
                # Try alternative link formats
                if 'links' in entry and entry.links:
                    for l in entry.links:
                        if l.get('rel') == 'alternate' or l.get('type') == 'text/html':
                            link = l.get('href', '')
                            break
            
            if not link:
                return None
            
            # Extract summary/description
            summary = entry.get('summary', '') or entry.get('description', '')
            # Clean up HTML if present
            if summary:
                summary = self._clean_html(summary)
                if len(summary) > settings.MAX_SUMMARY_LENGTH:
                    summary = summary[:settings.MAX_SUMMARY_LENGTH] + '...'
            
            # Extract published date
            published = None
            date_fields = ['published_parsed', 'updated_parsed', 'created_parsed', 'date_parsed']
            for field in date_fields:
                if hasattr(entry, field) and getattr(entry, field):
                    try:
                        ts = getattr(entry, field)
                        published = datetime(*ts[:6])
                        break
                    except (TypeError, ValueError):
                        continue
            
            # Try string date fields
            if not published:
                date_str_fields = ['published', 'updated', 'created', 'date']
                for field in date_str_fields:
                    if hasattr(entry, field) and getattr(entry, field):
                        try:
                            raw_date = getattr(entry, field)
                            published = date_parser.parse(raw_date)
                            break
                        except (ValueError, TypeError):
                            continue
            
            # Extract author
            author = entry.get('author', '')
            if not author and 'authors' in entry:
                authors = [a.get('name', '') for a in entry.authors if a.get('name')]
                author = ', '.join(authors)
            
            # Extract image URL from RSS entry
            image_url = self._extract_image_from_entry(entry)
            
            # Generate content hash for deduplication
            content_for_hash = f"{title.lower().strip()}"
            content_hash = hashlib.sha256(content_for_hash.encode()).hexdigest()
            
            return {
                'title': title,
                'url': link,
                'summary': summary,
                'published_at': published,
                'author': author,
                'image_url': image_url,
                'content_hash': content_hash,
            }
        
        except Exception as e:
            print(f"Error normalizing entry: {e}")
            return None
    
    def _clean_html(self, html: str) -> str:
        """Basic HTML cleaning"""
        import re
        # Remove script and style elements
        html = re.sub(r'<(script|style)[^>]*>[^<]*</\1>', '', html, flags=re.IGNORECASE | re.DOTALL)
        # Remove HTML tags
        html = re.sub(r'<[^>]+>', ' ', html)
        # Normalize whitespace
        html = re.sub(r'\s+', ' ', html).strip()
        # Decode common HTML entities
        html = html.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
        html = html.replace('&quot;', '"').replace('&#39;', "'").replace('&nbsp;', ' ')
        return html
    
    async def fetch_source(self, source: Source) -> List[Dict]:
        """Fetch and parse a single source"""
        print(f"Fetching: {source.name}")
        content = await self.fetch_feed(source.rss_url)
        
        if content:
            entries = self.parse_feed(content)
            print(f"  -> Found {len(entries)} entries")
            return entries
        
        return []
    
    async def fetch_all_sources(self) -> Dict[int, List[Dict]]:
        """Fetch all active sources concurrently"""
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(Source).where(Source.is_active == True)
            )
            sources = result.scalars().all()
        
        # Fetch all sources concurrently
        tasks = [self.fetch_source(source) for source in sources]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        source_entries = {}
        for source, entries in zip(sources, results):
            if isinstance(entries, Exception):
                print(f"Error fetching {source.name}: {entries}")
                source_entries[source.id] = []
            else:
                source_entries[source.id] = entries
                # Update last_fetched timestamp
                async with AsyncSessionLocal() as session:
                    source.last_fetched = datetime.utcnow()
                    await session.commit()
        
        return source_entries


class ArticleStore:
    """Store articles in database with deduplication"""
    
    async def store_article(self, session: AsyncSession, source_id: int, entry: Dict) -> Optional[Article]:
        """Store a single article, checking for duplicates"""
        # Check for existing article by URL
        result = await session.execute(
            select(Article).where(Article.url == entry['url'])
        )
        if result.scalar_one_or_none():
            return None
        
        # Check for duplicate by content hash
        result = await session.execute(
            select(Article).where(
                and_(
                    Article.content_hash == entry['content_hash'],
                    Article.is_duplicate == False
                )
            )
        )
        existing = result.scalar_one_or_none()
        
        is_duplicate = existing is not None
        duplicate_of_id = existing.id if existing else None
        
        article = Article(
            source_id=source_id,
            title=entry['title'],
            url=entry['url'],
            summary=entry['summary'],
            published_at=entry['published_at'],
            author=entry['author'],
            image_url=entry.get('image_url'),
            content_hash=entry['content_hash'],
            is_duplicate=is_duplicate,
            duplicate_of_id=duplicate_of_id,
        )
        
        session.add(article)
        return article
    
    async def store_entries(self, source_id: int, entries: List[Dict]) -> int:
        """Store multiple entries from a source"""
        count = 0
        async with AsyncSessionLocal() as session:
            for entry in entries:
                article = await self.store_article(session, source_id, entry)
                if article:
                    count += 1
            
            await session.commit()
        
        return count


async def fetch_and_store_all():
    """Main function to fetch all sources and store articles"""
    fetcher = RSSFetcher()
    store = ArticleStore()
    
    print("Starting RSS fetch...")
    source_entries = await fetcher.fetch_all_sources()
    
    total_stored = 0
    for source_id, entries in source_entries.items():
        if entries:
            stored = await store.store_entries(source_id, entries)
            total_stored += stored
            print(f"Stored {stored} new articles from source {source_id}")
    
    print(f"\nFetch complete. Total new articles: {total_stored}")
    return total_stored


if __name__ == "__main__":
    asyncio.run(fetch_and_store_all())
