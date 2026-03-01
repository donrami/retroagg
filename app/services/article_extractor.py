"""
Article extraction service using Mozilla Readability.
Fetches and parses external web pages to extract clean article content.
"""
import logging
import re
from typing import Optional, Dict
from urllib.parse import urljoin, urlparse
import httpx
from bs4 import BeautifulSoup
from readability import Document
logger = logging.getLogger(__name__)


class ArticleExtractor:
    """Extracts clean article content from external web pages with proper resource management."""
    
   # Class-level client for connection reuse
    _client: Optional[httpx.AsyncClient] = None
    _default_timeout = 30  # Class-level default timeout
    
    def __init__(self, timeout: int = 30):
        self.timeout = timeout
    
    @classmethod
    def get_client(cls) -> httpx.AsyncClient:
        """Get or create the shared HTTP client with proper configuration."""
        if cls._client is None or cls._client.is_closed:
            cls._client = httpx.AsyncClient(
                timeout=cls._default_timeout,
                follow_redirects=True,
                verify=True,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64 x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    "Accept":"text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                    "Accept-Language":"en-US,en;q=0.9",
                },
                limits=httpx.Limits(
                    max_keepalive_connections=10,
                    max_connections=20,
                    keepalive_expiry=30.0,
                ),
            )
        return cls._client
    
    @classmethod
    async def close_client(cls):
        """Close the shared HTTP client."""
        if cls._client is not None and not cls._client.is_closed:
            await cls._client.aclose()
            cls._client = None
    
    async def extract(self, url: str) -> Optional[dict]:
        """Extract article content from a URL."""
        if not self._is_safe_url(url):
            logger.warning(f"Blocked unsafe URL: {url}")
            return None
        
        try:
            logger.info(f"[EXTRACT] Starting extraction for: {url}")
            client = self.get_client()
            
            # Log client state for debugging
            logger.info(f"[EXTRACT] Client is closed: {client.is_closed}, timeout: {client.timeout}")
            
            response = await client.get(url)
            logger.info(f"[EXTRACT] Response status: {response.status_code}, content-length: {len(response.text)}")
            response.raise_for_status()
        
            doc = Document(response.text)
            raw_content = doc.summary()
            
            # Check if this is a video page
            is_aljazeera_video = "aljazeera" in url.lower() and "/video/" in url.lower()
            video_media = []
            
            # Special handling for Al Jazeera - their content may need direct extraction
            # Also trigger for video pages since they often have minimal Readability output
            if "aljazeera" in url.lower() and (is_aljazeera_video or not raw_content or len(raw_content.strip()) < 200):
                logger.info(f"[ALJAZEERA] Readability returned minimal content, attempting direct extraction for: {url}")
                raw_content = self._extract_aljazeera_content(response.text)
                logger.info(f"[ALJAZEERA] Direct extraction result length: {len(raw_content) if raw_content else 0}")
            
            # Special handling for Al Jazeera video pages - extract video embeds
            if is_aljazeera_video:
                logger.info(f"[ALJAZEERA_VIDEO] Processing video page: {url}")
                video_media = self._extract_aljazeera_video(response.text, url)
                logger.info(f"[ALJAZEERA_VIDEO] Found {len(video_media)} videos")
            
            cleaned_content, inline_media = self._process_content(raw_content, url)
            
            # For Al Jazeera video pages, also add the extracted video embeds
            if is_aljazeera_video and video_media:
                # Add any videos found that aren't already in inline_media
                for vm in video_media:
                    if vm not in inline_media:
                        inline_media.append(vm)
                logger.info(f"[ALJAZEERA_VIDEO] Total inline media: {len(inline_media)}")
            
            # Extract author and filter out "[no-author]" placeholder from Readability
            raw_byline = doc.author()
            byline = raw_byline if raw_byline and raw_byline != "[no-author]" else None
        
            result = {
                "title": doc.title(),
                "content": cleaned_content,
                "byline": byline,
                "excerpt": doc.short_title() or "",
                "original_url": url,
                "site_name": self._extract_site_name(url, response.text),
                "image_url": self._extract_image(url, response.text),
                "inline_media": inline_media,
            }

            logger.info(f"Successfully extracted article: {result.get('title', 'Untitled')}")
            return result

        except httpx.TimeoutException as e:
            logger.error(f"[EXTRACT] Timeout fetching article: {url} - {e}")
            return None
        except httpx.HTTPStatusError as e:
            logger.error(f"[EXTRACT] HTTP status error fetching article: {url} - status: {e.response.status_code}, response: {e.response.text[:500] if e.response.text else 'empty'}")
            return None
        except httpx.HTTPError as e:
            logger.error(f"[EXTRACT] HTTP error fetching article: {url} - {e}")
            return None
        except Exception as e:
            logger.error(f"[EXTRACT] Error extracting article: {url} - {e}", exc_info=True)
            return None
    
    def _is_safe_url(self, url: str) -> bool:
        """Validate URL to prevent SSRF and other security issues."""
        try:
            parsed = urlparse(url)
            if parsed.scheme not in ('http', 'https'):
                return False

            hostname = parsed.hostname or ""
            hostname_lower = hostname.lower()

            if hostname_lower in ('localhost', '127.0.0.1', '0.0.0.0', '::1'):
                return False

            if hostname_lower.startswith(('10.', '192.168.', '172.16.', '172.17.',
                    '172.18.', '172.19.', '172.20.', '172.21.',
                     '172.22.', '172.23.', '172.24.', '172.25.',
                    '172.26.', '172.27.', '172.28.', '172.29.',
                     '172.30.', '172.31.')):
                return False

            if hostname_lower in ('169.254.169.254', 'metadata.google.internal'):
                return False

            return True
        except Exception:
            return False
    
    def _process_content(self, html_content: str, base_url: str) -> tuple:
        """Process article content: clean HTML and extract inline media."""
        inline_media = []

        if not html_content:
            return "", []

        try:
            soup = BeautifulSoup(html_content, "lxml")

            for img in soup.find_all("img"):
                media_info = self._process_image(img, base_url)
                if media_info:
                    inline_media.append(media_info)

            for video in soup.find_all("video"):
                media_info = self._process_video(video, base_url)
                if media_info:
                    inline_media.append(media_info)

            for iframe in soup.find_all("iframe"):
                media_info = self._process_iframe(iframe, base_url)
                if media_info:
                    inline_media.append(media_info)

            for figure in soup.find_all("figure"):
                img = figure.find("img")
                if img:
                    media_info = self._process_image(img, base_url)
                    if media_info and media_info not in inline_media:
                        inline_media.append(media_info)

            cleaned_soup = self._clean_content(soup)
            return str(cleaned_soup), inline_media

        except Exception as e:
            logger.debug(f"Error processing content: {e}")
            return html_content, []
    
    def _process_image(self, img_tag, base_url: str) -> Optional[Dict]:
        """Process an image tag and extract metadata."""
        try:
            src = img_tag.get("src") or img_tag.get("data-src") or img_tag.get("data-lazy-src")
            if not src:
                return None
            
            if not self._is_valid_image_url(src):
                return None
            
            absolute_url = self._make_absolute_url(base_url, src)
            alt = img_tag.get("alt", "")
            width = img_tag.get("width")
            height = img_tag.get("height")
            
            return {
                "type": "image",
                "url": absolute_url,
                "alt": alt,
                "width": width,
                "height": height,
            }
        except Exception as e:
            logger.debug(f"Error processing image: {e}")
            return None
    
    def _process_video(self, video_tag, base_url: str) -> Optional[Dict]:
        """Process a video tag and extract metadata."""
        try:
            sources = video_tag.find_all("source")
            video_url = None
            
            for source in sources:
                src = source.get("src")
                if src:
                    video_url = src
                    break
            
            if not video_url:
                video_url = video_tag.get("src")
            
            if not video_url:
                return None
            
            absolute_url = self._make_absolute_url(base_url, video_url)
            poster = video_tag.get("poster")
            if poster:
                poster = self._make_absolute_url(base_url, poster)
            
            return {
                "type": "video",
                "url": absolute_url,
                "poster": poster,
            }
        except Exception as e:
            logger.debug(f"Error processing video: {e}")
            return None
    
    def _clean_content(self, soup: BeautifulSoup) -> BeautifulSoup:
        """Clean content by removing problematic elements including social embeds, buttons, voice readers."""
        # Remove script, style, noscript tags
        for tag in soup.find_all(["script", "style", "noscript"]):
            tag.decompose()
        
        # Remove elements by class names indicating ads, sponsors, popups, etc.
        for tag in soup.find_all(class_=lambda x: x and any(y in x.lower() for y in [
            "ad", "sponsor", "promo", "cookie", "popup", "modal", "newsletter",
            "social", "share", "sharing", "follow", "subscribe", "subscription",
            "button", "btn", "cta", "call-to-action",
            "voice", "audio-player", "read-aloud", "text-to-speech", "tts",
            "embed", "widget", "sidebar", "related", "recommended",
            "comment", "comments", "discussion", "forum",
            "facebook", "twitter", "instagram", "tiktok", "youtube-channel",
            "footer", "header", "nav", "navigation", "menu",
            "breadcrumb", "pagination", "tags", "meta", "author-info",
            "published", "date", "timestamp", "read-time",
            "video-ad", "preroll", "banner", "sticky", "floating"
        ])):
            tag.decompose()
        
        # Remove elements by id patterns
        for tag in soup.find_all(id=lambda x: x and any(y in str(x).lower() for y in [
            "social", "share", "follow", "subscribe", "comment", "ad", "sidebar",
            "related", "recommended", "footer", "header", "voice", "audio"
        ])):
            tag.decompose()
        
        # Remove social media embed containers
        social_patterns = [
            "facebook.com/plugins", "facebook.com/sharer",
            "twitter.com", "x.com",
            "instagram.com", "tiktok.com",
            "linkedin.com/share", "pinterest.com",
            "reddit.com", "whatsapp.com",
            "telegram.me", "signal.app"
        ]
        for iframe in soup.find_all("iframe"):
            src = iframe.get("src", "")
            if any(pattern in src.lower() for pattern in social_patterns):
                iframe.decompose()
        
        # Remove share buttons and social links
        for tag in soup.find_all(["a", "button", "span", "div"], class_=lambda x: x and any(
            y in str(x).lower() for y in ["share", "social", "follow", "like", "tweet", "post", "repost"]
        )):
            tag.decompose()
        
        # Remove voice reader / text-to-speech elements
        voice_patterns = ["voice", "read-aloud", "text-to-speech", "tts", "audio-player", "listen"]
        for tag in soup.find_all(class_=lambda x: x and any(y in str(x).lower() for y in voice_patterns)):
            tag.decompose()
        for tag in soup.find_all(id=lambda x: x and any(y in str(x).lower() for y in voice_patterns)):
            tag.decompose()
        
        # Remove data attributes related to social tracking
        for tag in soup.find_all(True):
            attrs_to_remove = []
            for attr in tag.attrs:
                attr_lower = attr.lower()
                if any(x in attr_lower for x in ["data-social", "data-share", "data-tracking",
                    "data-analytics", "data-gtm", "data-ga", "data-facebook", "data-twitter"]):
                    attrs_to_remove.append(attr)
            for attr in attrs_to_remove:
                del tag[attr]
        
        # Remove elements with display:none
        for tag in soup.find_all(style=lambda x: x and "display:none" in x.replace(" ", "").lower()):
            tag.decompose()
        
        # Remove empty tags that are not meaningful
        for tag in soup.find_all(lambda t: t.string and not t.string.strip() and not t.find_all(["img", "br", "hr"])):
            if not tag.find_all(["img", "br", "hr", "a"]):
                tag.decompose()
        
        # Remove tracking pixels and invalid images
        for img in soup.find_all("img"):
            src = img.get("src") or img.get("data-src")
            if src and src.startswith("javascript:"):
                img.decompose()
            elif src and "undefined" in src.lower():
                img.decompose()
            # Remove 1x1 tracking pixels
            elif img.get("width") == "1" and img.get("height") == "1":
                img.decompose()
        
        # Remove event handlers from all tags
        for tag in soup.find_all(True):
            if tag.string:
                tag.string = tag.string.strip()
            if tag.name not in ["pre", "code"]:
                tag.attrs = {k: v for k, v in tag.attrs.items() if k not in [
                    "onclick", "onload", "onerror", "onmouseover", "onmouseout",
                    "onfocus", "onblur", "onchange", "onsubmit", "onkeydown", "onkeyup"
                ]}
        
        return soup
    
    def _extract_aljazeera_content(self, html: str) -> str:
        """Extract content directly from Al Jazeera pages when Readability fails."""
        try:
            soup = BeautifulSoup(html, "lxml")
            
            # Try to find the main article content container
            # Al Jazeera typically uses these selectors
            article_selectors = [
                "article",
                "[class*='article-body']",
                "[class*='article__body']",
                "[class*='story-body']",
                "[class*='post-content']",
                "[class*='entry-content']",
                "main article",
                ".article-content",
                ".article__content",
                ".story-content",
                "#article-body",
                ".article-body",
            ]
            
            article_content = None
            for selector in article_selectors:
                elements = soup.select(selector)
                if elements:
                    # Get the one with the most text content
                    best_element = max(elements, key=lambda e: len(e.get_text(strip=True)))
                    if len(best_element.get_text(strip=True)) > 200:
                        article_content = best_element
                        break
            
            if article_content:
                # Clean the extracted content
                cleaned = self._clean_content(article_content)
                return str(cleaned)
            
            # Fallback: try to find all paragraph tags in the body
            paragraphs = soup.find_all("p")
            if paragraphs:
                content_parts = []
                for p in paragraphs:
                    text = p.get_text(strip=True)
                    if len(text) > 50:  # Filter out short fragments
                        content_parts.append(f"<p>{text}</p>")
                if content_parts:
                    return "".join(content_parts)
            
            return ""
            
        except Exception as e:
            logger.debug(f"Error extracting Al Jazeera content: {e}")
            return ""
    
    def _extract_aljazeera_video(self, html: str, base_url: str) -> list:
        """Extract video embed information from Al Jazeera video pages."""
        video_media = []
        try:
            soup = BeautifulSoup(html, "lxml")
            
            # Get the poster image from og:image for video thumbnail
            poster_url = None
            og_image = soup.find("meta", property="og:image")
            if og_image and og_image.get("content"):
                poster_url = self._make_absolute_url(base_url, og_image["content"])
            
            # Method 0: Look for Brightcove player embeds (common for Al Jazeera)
            for script in soup.find_all("script"):
                script_text = script.string or ""
                # Look for Brightcove player URLs
                if "brightcove" in script_text.lower() or "players.brightcove" in script_text:
                    import re
                    
                    # Find Brightcove player URLs
                    brightcove_urls = re.findall(r'https://players\.brightcove\.net/[^\s"\'<>]+', script_text)
                    for url in brightcove_urls:
                        # Extract videoId if present
                        video_id_match = re.search(r'videoId=(\d+)', script_text)
                        video_id = video_id_match.group(1) if video_id_match else None
                        
                        # Build Brightcove embed URL
                        if video_id:
                            embed_url = f"https://players.brightcove.net/665003303001/default_default/index.html?videoId={video_id}"
                        else:
                            embed_url = url
                        
                        if embed_url not in [v.get("url") for v in video_media]:
                            video_media.append({
                                "type": "brightcove",
                                "url": embed_url,
                                "video_id": video_id,
                                "poster": poster_url,
                            })
                    
                    # Also look for video ID directly
                    video_id_match = re.search(r'videoId["\']?\s*[:=]\s*["\']?(\d+)', script_text)
                    if video_id_match:
                        video_id = video_id_match.group(1)
                        embed_url = f"https://players.brightcove.net/665003303001/default_default/index.html?videoId={video_id}"
                        if embed_url not in [v.get("url") for v in video_media]:
                            video_media.append({
                                "type": "brightcove",
                                "url": embed_url,
                                "video_id": video_id,
                                "poster": poster_url,
                            })
            
            # Method 1: Look for oEmbed JSON in script tags
            for script in soup.find_all("script"):
                script_text = script.string or ""
                # Look for oEmbed response
                if "oembed" in script_text.lower() or '"type":"video"' in script_text:
                    # Try to extract JSON data
                    import json
                    import re
                    
                    # Find JSON objects in the script
                    json_matches = re.findall(r'\{[^{}]*"embedUrl"[^{}]*\}', script_text)
                    for match in json_matches:
                        try:
                            data = json.loads(match)
                            if data.get("embedUrl"):
                                video_media.append({
                                    "type": "video",
                                    "url": data.get("embedUrl"),
                                    "poster": data.get("thumbnailUrl"),
                                    "title": data.get("title", ""),
                                })
                        except:
                            pass
                    
                    # Also try to find any video URLs in the script
                    video_urls = re.findall(r'https?://[^\s"\'<>]+\.(?:mp4|webm|m3u8)[^\s"\'<>]*', script_text)
                    for url in video_urls:
                        if url not in [v.get("url") for v in video_media]:
                            video_media.append({
                                "type": "video",
                                "url": url,
                            })
            
            # Method 2: Look for video meta tags
            video_meta_selectors = [
                ("meta", {"property": "og:video"}),
                ("meta", {"property": "og:video:url"}),
                ("meta", {"name": "twitter:player"}),
            ]
            for tag_name, attrs in video_meta_selectors:
                meta = soup.find(tag_name, attrs=attrs)
                if meta and meta.get("content"):
                    content = meta["content"]
                    if content.startswith("http"):
                        # Check if it's a YouTube or other embed
                        if "youtube" in content.lower() or "youtu.be" in content.lower():
                            video_media.append({
                                "type": "youtube",
                                "url": content,
                            })
                        else:
                            video_media.append({
                                "type": "video",
                                "url": content,
                            })
            
            # Method 3: Look for iframe embeds (common for video players)
            for iframe in soup.find_all("iframe"):
                src = iframe.get("src") or iframe.get("data-src")
                if src and ("video" in src.lower() or "player" in src.lower() or
                           "embed" in src.lower() or "aljazeera" in src.lower()):
                    absolute_url = self._make_absolute_url(base_url, src)
                    embed_type = "iframe"
                    if "youtube" in src.lower():
                        embed_type = "youtube"
                    elif "vimeo" in src.lower():
                        embed_type = "vimeo"
                    
                    # Avoid duplicates
                    if absolute_url not in [v.get("url") for v in video_media]:
                        video_media.append({
                            "type": embed_type,
                            "url": absolute_url,
                        })
            
            # Method 4: Look for video tags with source elements
            for video in soup.find_all("video"):
                sources = video.find_all("source")
                for source in sources:
                    src = source.get("src")
                    if src:
                        absolute_url = self._make_absolute_url(base_url, src)
                        poster = video.get("poster")
                        if poster:
                            poster = self._make_absolute_url(base_url, poster)
                        
                        if absolute_url not in [v.get("url") for v in video_media]:
                            video_media.append({
                                "type": "video",
                                "url": absolute_url,
                                "poster": poster,
                            })
            
            logger.info(f"[ALJAZEERA_VIDEO] Found {len(video_media)} videos for {base_url}")
            return video_media
            
        except Exception as e:
            logger.debug(f"Error extracting Al Jazeera video: {e}")
            return []
    
    def _extract_site_name(self, url: str, html: str) -> str:
        """Extract site name from the page."""
        try:
            soup = BeautifulSoup(html, "lxml")
            
            og_site = soup.find("meta", property="og:site_name")
            if og_site and og_site.get("content"):
                return og_site["content"]
            
            parsed = urlparse(url)
            return parsed.netloc.replace("www.", "")
            
        except Exception:
            parsed = urlparse(url)
            return parsed.netloc.replace("www.", "")
    
    def _extract_image(self, url: str, html: str) -> Optional[str]:
        """Extract the main article image from the page."""
        try:
            soup = BeautifulSoup(html, "lxml")
            
            og_image = soup.find("meta", property="og:image")
            if og_image and og_image.get("content"):
                image_url = self._make_absolute_url(url, og_image["content"])
                logger.info(f"[IMAGE_DEBUG] OG image found for {url}: {image_url}")
                return image_url
            
            twitter_image = soup.find("meta", attrs={"name": "twitter:image"})
            if twitter_image and twitter_image.get("content"):
                image_url = self._make_absolute_url(url, twitter_image["content"])
                logger.info(f"[IMAGE_DEBUG] Twitter image found for {url}: {image_url}")
                return image_url
            
            article_image = soup.find("meta", attrs={"name": "article:image"})
            if article_image and article_image.get("content"):
                image_url = self._make_absolute_url(url, article_image["content"])
                logger.info(f"[IMAGE_DEBUG] Article image found for {url}: {image_url}")
                return image_url
            
            content_soup = BeautifulSoup(html, "lxml")
            article_tag = content_soup.find("article")
            if article_tag:
                imgs = article_tag.find_all("img")
                for img in imgs:
                    src = img.get("src") or img.get("data-src")
                    if src and self._is_valid_image_url(src):
                        image_url = self._make_absolute_url(url, src)
                        logger.info(f"[IMAGE_DEBUG] Content image found for {url}: {image_url}")
                        return image_url
            
            logger.info(f"[IMAGE_DEBUG] No image found for {url}")
            return None
            
        except Exception as e:
            logger.debug(f"Error extracting image: {e}")
            return None
    
    def _make_absolute_url(self, base_url: str, image_url: str) -> str:
        """Convert relative image URLs to absolute URLs."""
        if not image_url:
            return ""
        if image_url.startswith(("http://", "https://", "data:")):
            return image_url
        return urljoin(base_url, image_url)
    
    def _is_valid_image_url(self, url: str) -> bool:
        """Check if a URL looks like a valid image."""
        if not url or url.startswith("data:"):
            return False
        if any(x in url.lower() for x in ["pixel", "1x1", "spacer", "blank"]):
            return False
        return True
    
    async def close(self):
        """Close the HTTP client."""
        await self.close_client()


_extractor: Optional[ArticleExtractor] = None


async def get_extractor() -> ArticleExtractor:
    """Get or create the article extractor instance."""
    global _extractor
    if _extractor is None:
        _extractor = ArticleExtractor()
    return _extractor


async def extract_article(url: str) -> Optional[dict]:
    """Convenience function to extract article content."""
    extractor = await get_extractor()
    return await extractor.extract(url)
    
    def _process_iframe(self, iframe_tag, base_url: str) -> Optional[Dict]:
        """Process an iframe tag and extract embed info."""
        try:
            src = iframe_tag.get("src")
            if not src:
                return None
            
            src_lower = src.lower()
            if any(x in src_lower for x in ["facebook.com/plugins", "twitter.com", "ads", "tracking"]):
                return None
            
            absolute_url = self._make_absolute_url(base_url, src)
            
            embed_type = "iframe"
            if "youtube.com" in src_lower or "youtu.be" in src_lower:
                embed_type = "youtube"
            elif "vimeo.com" in src_lower:
                embed_type = "vimeo"
            
            return {
                "type": embed_type,
                "url": absolute_url,
            }
        except Exception as e:
            logger.debug(f"Error processing iframe: {e}")
            return None