"""
Tool implementations for the Bonded Content Agent.
These are the functions Claude can call to interact with the world.
"""

import logging
import feedparser
import httpx
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from typing import Optional
from urllib.parse import urljoin, urlparse
import re
from supabase import Client

from database import (
    check_article_exists, save_article, get_existing_urls,
    get_top_performing_articles, get_engagement_stats,
    get_latest_analysis_report, get_trending_topics, get_content_gaps,
    get_related_articles, get_article_with_related
)

logger = logging.getLogger(__name__)

# Tool definitions for the Anthropic API
TOOL_DEFINITIONS = [
    {
        "name": "fetch_rss_feed",
        "description": "Fetch and parse an RSS feed to get recent blog posts. Returns a list of posts with title, url, published date, and summary.",
        "input_schema": {
            "type": "object",
            "properties": {
                "feed_url": {
                    "type": "string",
                    "description": "The URL of the RSS feed to fetch"
                },
                "source_name": {
                    "type": "string",
                    "description": "Name of the blog source for logging"
                }
            },
            "required": ["feed_url", "source_name"]
        }
    },
    {
        "name": "fetch_article_content",
        "description": "Fetch the full content of an article to better understand it. Use this when the RSS summary isn't enough to evaluate the article.",
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "The URL of the article to fetch"
                }
            },
            "required": ["url"]
        }
    },
    {
        "name": "check_url_exists",
        "description": "Check if an article URL already exists in the Bonded database to avoid duplicates.",
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "The article URL to check"
                }
            },
            "required": ["url"]
        }
    },
    {
        "name": "save_article_to_database",
        "description": "Save a curated article to the Bonded database. Only call this for articles that meet the content criteria.",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "The article title"
                },
                "blurb": {
                    "type": "string",
                    "description": "A compelling 2-3 sentence blurb about the article (under 200 chars ideal)"
                },
                "url": {
                    "type": "string",
                    "description": "The article URL"
                },
                "image_url": {
                    "type": "string",
                    "description": "Image URL for the article"
                },
                "relevance_score": {
                    "type": "number",
                    "description": "Score 0-10: How relevant is this to Bonded's audience (committed couples seeking relationship improvement)"
                },
                "actionability_score": {
                    "type": "number",
                    "description": "Score 0-10: How actionable is the advice (concrete steps vs abstract concepts)"
                },
                "depth_score": {
                    "type": "number",
                    "description": "Score 0-10: Depth of content (superficial listicle vs evidence-based insights)"
                },
                "freshness_score": {
                    "type": "number",
                    "description": "Score 0-10: Novelty and timeliness (evergreen content scores 5-7, trending topics 8-10)"
                },
                "category": {
                    "type": "string",
                    "enum": ["communication", "conflict", "intimacy", "trust", "parenting", "finances", "growth", "wellness"],
                    "description": "Primary category that best describes the article's main topic"
                },
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "3-5 relevant tags for the article (e.g., 'active listening', 'date night', 'emotional intelligence')"
                },
                "reading_time_minutes": {
                    "type": "integer",
                    "description": "Estimated reading time in minutes"
                },
                "difficulty": {
                    "type": "string",
                    "enum": ["beginner", "intermediate", "advanced"],
                    "description": "Difficulty level: beginner (simple concepts), intermediate (some relationship knowledge), advanced (complex issues/therapy concepts)"
                },
                "summary_short": {
                    "type": "string",
                    "maxLength": 280,
                    "description": "Short tweet-style summary (max 280 chars) highlighting the main benefit or insight"
                },
                "summary_detailed": {
                    "type": "string",
                    "description": "Detailed 2-3 paragraph summary of the article's key points and advice"
                },
                "key_takeaways": {
                    "type": "array",
                    "items": {"type": "string"},
                    "minItems": 3,
                    "maxItems": 5,
                    "description": "3-5 actionable bullet points couples can implement (be specific and practical)"
                },
                "discussion_questions": {
                    "type": "array",
                    "items": {"type": "string"},
                    "minItems": 2,
                    "maxItems": 3,
                    "description": "2-3 thought-provoking questions for couples to discuss together"
                },
                "source_id": {
                    "type": "string",
                    "description": "The UUID of the source this article came from (provided in the source list)"
                }
            },
            "required": ["title", "blurb", "url", "image_url", "relevance_score", "actionability_score", "depth_score", "freshness_score", "category", "tags", "reading_time_minutes", "difficulty", "summary_short", "summary_detailed", "key_takeaways", "discussion_questions", "source_id"]
        }
    },
    {
        "name": "get_all_existing_urls",
        "description": "Get all article URLs currently in the database. Use this at the start to efficiently filter out duplicates.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "get_top_performing_articles",
        "description": "Get top performing articles by user engagement from the last N days. Use this BEFORE curating to understand what content resonates with users.",
        "input_schema": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Number of top articles to retrieve (default: 10)",
                    "default": 10
                },
                "days": {
                    "type": "integer",
                    "description": "Look back period in days (default: 30)",
                    "default": 30
                }
            },
            "required": []
        }
    },
    {
        "name": "get_engagement_stats",
        "description": "Get overall engagement statistics (views, saves, rates) from the last N days to understand user behavior patterns.",
        "input_schema": {
            "type": "object",
            "properties": {
                "days": {
                    "type": "integer",
                    "description": "Look back period in days (default: 30)",
                    "default": 30
                }
            },
            "required": []
        }
    },
    {
        "name": "get_latest_analysis_report",
        "description": "Get the most recent weekly trend analysis report with trending topics, top articles, content gaps, and recommendations.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "get_trending_topics",
        "description": "Get currently trending topics/tags based on recent vs historical volume. Shows what topics are gaining traction with users.",
        "input_schema": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Number of trending topics to retrieve (default: 10)",
                    "default": 10
                }
            },
            "required": []
        }
    },
    {
        "name": "get_content_gaps",
        "description": "Identify content gaps and opportunities - topics with high engagement but low coverage, or popular topics without recent articles.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "get_related_articles",
        "description": "Get related articles for a given article based on category, tags, and topic similarity. Useful for understanding content relationships.",
        "input_schema": {
            "type": "object",
            "properties": {
                "article_id": {
                    "type": "string",
                    "description": "The UUID of the article to find related content for"
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of related articles to return (default: 5)",
                    "default": 5
                }
            },
            "required": ["article_id"]
        }
    },
    {
        "name": "get_article_with_related",
        "description": "Get a complete article with its related articles embedded. Shows the article plus up to 5 most similar articles.",
        "input_schema": {
            "type": "object",
            "properties": {
                "article_id": {
                    "type": "string",
                    "description": "The UUID of the article to retrieve with related content"
                }
            },
            "required": ["article_id"]
        }
    }
]


# ============================================================================
# IMAGE EXTRACTION HELPER FUNCTIONS
# ============================================================================

def _is_valid_image_url(url: str) -> bool:
    """Check if a URL looks like a valid image."""
    if not url or not isinstance(url, str):
        return False

    # Remove query parameters for extension check
    url_path = urlparse(url).path.lower()

    # Check for common image extensions
    image_extensions = ('.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg', '.bmp')
    if any(url_path.endswith(ext) for ext in image_extensions):
        return True

    # Check if URL contains image-related patterns
    image_patterns = ['/image/', '/img/', '/photo/', '/picture/', '/media/']
    if any(pattern in url.lower() for pattern in image_patterns):
        return True

    return False


def _make_absolute_url(url: str, base_url: str) -> str:
    """Convert a relative URL to absolute using the base URL."""
    if not url:
        return ""

    # Already absolute
    if url.startswith(('http://', 'https://')):
        return url

    # Protocol-relative URL
    if url.startswith('//'):
        return 'https:' + url

    # Relative URL - join with base
    return urljoin(base_url, url)


def _verify_image_url(url: str) -> bool:
    """Verify that an image URL is accessible and returns HTTP 200."""
    if not url:
        return False

    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; BondedBot/1.0; +https://bonded.app)"
        }

        with httpx.Client(timeout=10, follow_redirects=True) as client:
            response = client.head(url, headers=headers)

            # Some servers don't support HEAD, try GET if HEAD fails
            if response.status_code == 405 or response.status_code == 404:
                response = client.get(url, headers=headers)

            if response.status_code == 200:
                logger.debug(f"Image URL verified: {url}")
                return True
            else:
                logger.debug(f"Image URL returned {response.status_code}: {url}")
                return False

    except Exception as e:
        logger.debug(f"Failed to verify image URL {url}: {e}")
        return False


def _extract_first_image_from_html(html: str) -> Optional[str]:
    """Extract the first image from HTML content."""
    if not html:
        return None

    try:
        soup = BeautifulSoup(html, "lxml")
        img_tag = soup.find('img')
        if img_tag:
            return img_tag.get('src') or img_tag.get('data-src')
    except Exception as e:
        logger.debug(f"Error extracting image from HTML: {e}")

    return None


def _extract_image_from_entry(entry: dict) -> Optional[str]:
    """
    Extract image URL from RSS entry with comprehensive fallback chain.
    Verifies each URL returns HTTP 200 before accepting it.

    Checks in order:
    1. media:content
    2. media:thumbnail
    3. enclosures
    4. <img> tags in content
    5. <img> tags in summary
    6. image field
    """
    image_url = None

    # 1. Check media:content
    if hasattr(entry, 'media_content') and entry.media_content:
        try:
            image_url = entry.media_content[0].get('url')
            if image_url and _verify_image_url(image_url):
                logger.debug(f"Found and verified image in media_content: {image_url}")
                return image_url
        except (IndexError, AttributeError, KeyError):
            pass

    # 2. Check media:thumbnail
    if hasattr(entry, 'media_thumbnail') and entry.media_thumbnail:
        try:
            image_url = entry.media_thumbnail[0].get('url')
            if image_url and _verify_image_url(image_url):
                logger.debug(f"Found and verified image in media_thumbnail: {image_url}")
                return image_url
        except (IndexError, AttributeError, KeyError):
            pass

    # 3. Check enclosures
    if hasattr(entry, 'enclosures') and entry.enclosures:
        for enclosure in entry.enclosures:
            enc_type = enclosure.get('type', '')
            enc_url = enclosure.get('href') or enclosure.get('url')
            if enc_url and ('image' in enc_type or _is_valid_image_url(enc_url)):
                if _verify_image_url(enc_url):
                    logger.debug(f"Found and verified image in enclosures: {enc_url}")
                    return enc_url

    # 4. Check <img> tags in content
    if hasattr(entry, 'content') and entry.content:
        try:
            html_content = entry.content[0].get('value', '')
            image_url = _extract_first_image_from_html(html_content)
            if image_url and _verify_image_url(image_url):
                logger.debug(f"Found and verified image in content HTML: {image_url}")
                return image_url
        except (IndexError, AttributeError, KeyError):
            pass

    # 5. Check <img> tags in summary/description
    summary = entry.get('summary') or entry.get('description', '')
    if summary:
        image_url = _extract_first_image_from_html(summary)
        if image_url and _verify_image_url(image_url):
            logger.debug(f"Found and verified image in summary HTML: {image_url}")
            return image_url

    # 6. Check direct image field
    if hasattr(entry, 'image') and entry.image:
        if isinstance(entry.image, dict):
            image_url = entry.image.get('href') or entry.image.get('url')
        else:
            image_url = str(entry.image)
        if image_url and _verify_image_url(image_url):
            logger.debug(f"Found and verified image in image field: {image_url}")
            return image_url

    return None


def _extract_best_image(soup: BeautifulSoup, base_url: str) -> Optional[str]:
    """
    Extract the best image from an article page with comprehensive fallback chain.
    Verifies each URL returns HTTP 200 before accepting it.

    Checks in order:
    1. og:image meta tag
    2. twitter:image meta tag
    3. article:image meta tag
    4. WordPress featured image classes
    5. First <img> in article content
    6. Any reasonably sized image (skip icons/avatars/logos)
    """
    image_url = None

    # 1. Check og:image
    og_image = soup.find('meta', property='og:image')
    if og_image and og_image.get('content'):
        image_url = _make_absolute_url(og_image.get('content'), base_url)
        if _verify_image_url(image_url):
            logger.debug(f"Found and verified image in og:image: {image_url}")
            return image_url

    # 2. Check twitter:image
    twitter_image = soup.find('meta', attrs={'name': 'twitter:image'})
    if twitter_image and twitter_image.get('content'):
        image_url = _make_absolute_url(twitter_image.get('content'), base_url)
        if _verify_image_url(image_url):
            logger.debug(f"Found and verified image in twitter:image: {image_url}")
            return image_url

    # 3. Check article:image
    article_image = soup.find('meta', property='article:image')
    if article_image and article_image.get('content'):
        image_url = _make_absolute_url(article_image.get('content'), base_url)
        if _verify_image_url(image_url):
            logger.debug(f"Found and verified image in article:image: {image_url}")
            return image_url

    # 4. Check WordPress featured image classes
    wp_featured = soup.find('img', class_=re.compile(r'wp-post-image|featured-image|post-thumbnail'))
    if wp_featured:
        image_url = wp_featured.get('src') or wp_featured.get('data-src')
        if image_url:
            image_url = _make_absolute_url(image_url, base_url)
            if _verify_image_url(image_url):
                logger.debug(f"Found and verified WordPress featured image: {image_url}")
                return image_url

    # 5. First <img> in article content
    for selector in ['article', 'main', '.post-content', '.entry-content', '.content']:
        content = soup.select_one(selector)
        if content:
            img = content.find('img')
            if img:
                image_url = img.get('src') or img.get('data-src')
                if image_url:
                    image_url = _make_absolute_url(image_url, base_url)
                    if _verify_image_url(image_url):
                        logger.debug(f"Found and verified image in article content ({selector}): {image_url}")
                        return image_url

    # 6. Any reasonably sized image (skip small icons/avatars)
    all_images = soup.find_all('img')
    for img in all_images:
        # Skip if has avatar/icon/logo indicators
        img_class = ' '.join(img.get('class', []))
        img_id = img.get('id', '')
        skip_keywords = ['avatar', 'icon', 'logo', 'gravatar', 'author', 'profile']

        if any(keyword in img_class.lower() or keyword in img_id.lower() for keyword in skip_keywords):
            continue

        # Check size attributes if available
        width = img.get('width')
        height = img.get('height')
        if width and height:
            try:
                if int(width) < 200 or int(height) < 200:
                    continue
            except (ValueError, TypeError):
                pass

        image_url = img.get('src') or img.get('data-src')
        if image_url and _is_valid_image_url(image_url):
            image_url = _make_absolute_url(image_url, base_url)
            if _verify_image_url(image_url):
                logger.debug(f"Found and verified reasonably sized image: {image_url}")
                return image_url

    logger.debug("No suitable image found on page")
    return None


def fetch_rss_feed(feed_url: str, source_name: str) -> dict:
    """Fetch and parse an RSS feed."""
    try:
        logger.info(f"Fetching RSS feed: {source_name} ({feed_url})")
        feed = feedparser.parse(feed_url)
        
        if feed.bozo and feed.bozo_exception:
            logger.warning(f"Feed parse warning for {source_name}: {feed.bozo_exception}")
        
        posts = []
        for entry in feed.entries[:15]:  # Limit to 15 most recent
            post = {
                "title": entry.get("title", "Untitled"),
                "url": entry.get("link", ""),
                "published": entry.get("published", entry.get("updated", "")),
                "summary": _clean_html(entry.get("summary", entry.get("description", "")))[:500]
            }

            # Try to extract image using comprehensive fallback chain
            image_url = _extract_image_from_entry(entry)
            if image_url:
                # Make sure it's an absolute URL
                post["image_url"] = _make_absolute_url(image_url, post["url"])

            posts.append(post)
        
        return {
            "success": True,
            "source": source_name,
            "post_count": len(posts),
            "posts": posts
        }
    except Exception as e:
        logger.error(f"Error fetching RSS feed {source_name}: {e}")
        return {
            "success": False,
            "source": source_name,
            "error": str(e),
            "posts": []
        }


def fetch_article_content(url: str) -> dict:
    """Fetch the full content of an article."""
    try:
        logger.info(f"Fetching article content: {url}")

        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; BondedBot/1.0; +https://bonded.app)"
        }

        with httpx.Client(timeout=30, follow_redirects=True) as client:
            response = client.get(url, headers=headers)
            response.raise_for_status()

        soup = BeautifulSoup(response.text, "lxml")

        # Try to find the best image using comprehensive fallback chain
        image_url = _extract_best_image(soup, url)
        image_found = image_url is not None

        # Remove script, style, nav, footer elements for content extraction
        for element in soup(["script", "style", "nav", "footer", "header", "aside"]):
            element.decompose()

        # Try to find main content
        content = None
        for selector in ["article", "main", ".post-content", ".entry-content", ".content"]:
            content = soup.select_one(selector)
            if content:
                break

        if not content:
            content = soup.body or soup

        text = content.get_text(separator="\n", strip=True)

        # Truncate to reasonable length
        text = text[:3000] + "..." if len(text) > 3000 else text

        return {
            "success": True,
            "url": url,
            "content": text,
            "image_url": image_url,
            "image_found": image_found
        }
    except Exception as e:
        logger.error(f"Error fetching article {url}: {e}")
        return {
            "success": False,
            "url": url,
            "error": str(e),
            "image_found": False
        }


def check_url_exists(url: str, supabase_client: Client) -> dict:
    """Check if a URL exists in the database."""
    exists = check_article_exists(supabase_client, url)
    return {
        "url": url,
        "exists": exists
    }


def save_article_to_database(
    title: str,
    blurb: str,
    url: str,
    supabase_client: Client,
    image_url: Optional[str] = None,
    relevance_score: Optional[float] = None,
    actionability_score: Optional[float] = None,
    depth_score: Optional[float] = None,
    freshness_score: Optional[float] = None,
    category: Optional[str] = None,
    tags: Optional[list] = None,
    reading_time_minutes: Optional[int] = None,
    difficulty: Optional[str] = None,
    summary_short: Optional[str] = None,
    summary_detailed: Optional[str] = None,
    key_takeaways: Optional[list] = None,
    discussion_questions: Optional[list] = None,
    source_id: Optional[str] = None
) -> dict:
    """Save an article to the database with quality scores, metadata, and content transformations."""
    # Double-check it doesn't exist
    if check_article_exists(supabase_client, url):
        return {
            "success": False,
            "error": "Article already exists",
            "url": url
        }

    result = save_article(
        supabase_client,
        title,
        blurb,
        url,
        image_url,
        relevance_score,
        actionability_score,
        depth_score,
        freshness_score,
        category,
        tags,
        reading_time_minutes,
        difficulty,
        summary_short,
        summary_detailed,
        key_takeaways,
        discussion_questions,
        source_id
    )
    result["url"] = url
    result["title"] = title
    result["source_id"] = source_id
    return result


def get_all_existing_urls_tool(supabase_client: Client) -> dict:
    """Get all existing URLs from the database."""
    urls = get_existing_urls(supabase_client)
    return {
        "count": len(urls),
        "urls": list(urls)
    }


def execute_tool(tool_name: str, tool_input: dict, supabase_client: Client) -> str:
    """Execute a tool and return the result as a string."""
    import json
    
    try:
        if tool_name == "fetch_rss_feed":
            result = fetch_rss_feed(tool_input["feed_url"], tool_input["source_name"])
        elif tool_name == "fetch_article_content":
            result = fetch_article_content(tool_input["url"])
        elif tool_name == "check_url_exists":
            result = check_url_exists(tool_input["url"], supabase_client)
        elif tool_name == "save_article_to_database":
            result = save_article_to_database(
                title=tool_input["title"],
                blurb=tool_input["blurb"],
                url=tool_input["url"],
                supabase_client=supabase_client,
                image_url=tool_input.get("image_url"),
                relevance_score=tool_input.get("relevance_score"),
                actionability_score=tool_input.get("actionability_score"),
                depth_score=tool_input.get("depth_score"),
                freshness_score=tool_input.get("freshness_score"),
                category=tool_input.get("category"),
                tags=tool_input.get("tags"),
                reading_time_minutes=tool_input.get("reading_time_minutes"),
                difficulty=tool_input.get("difficulty"),
                summary_short=tool_input.get("summary_short"),
                summary_detailed=tool_input.get("summary_detailed"),
                key_takeaways=tool_input.get("key_takeaways"),
                discussion_questions=tool_input.get("discussion_questions"),
                source_id=tool_input.get("source_id")
            )
        elif tool_name == "get_all_existing_urls":
            result = get_all_existing_urls_tool(supabase_client)
        elif tool_name == "get_top_performing_articles":
            result = {
                "articles": get_top_performing_articles(
                    supabase_client,
                    limit=tool_input.get("limit", 10),
                    days=tool_input.get("days", 30)
                )
            }
        elif tool_name == "get_engagement_stats":
            result = get_engagement_stats(
                supabase_client,
                days=tool_input.get("days", 30)
            )
        elif tool_name == "get_latest_analysis_report":
            result = get_latest_analysis_report(supabase_client)
        elif tool_name == "get_trending_topics":
            result = {
                "trending_topics": get_trending_topics(
                    supabase_client,
                    limit=tool_input.get("limit", 10)
                )
            }
        elif tool_name == "get_content_gaps":
            result = {
                "content_gaps": get_content_gaps(supabase_client)
            }
        elif tool_name == "get_related_articles":
            result = {
                "related_articles": get_related_articles(
                    supabase_client,
                    article_id=tool_input["article_id"],
                    limit=tool_input.get("limit", 5)
                )
            }
        elif tool_name == "get_article_with_related":
            result = get_article_with_related(
                supabase_client,
                article_id=tool_input["article_id"]
            )
        else:
            result = {"error": f"Unknown tool: {tool_name}"}
            
        return json.dumps(result, indent=2)
    except Exception as e:
        logger.error(f"Error executing tool {tool_name}: {e}")
        return json.dumps({"error": str(e)})


def _clean_html(html_content: str) -> str:
    """Remove HTML tags from content."""
    if not html_content:
        return ""
    soup = BeautifulSoup(html_content, "lxml")
    return soup.get_text(separator=" ", strip=True)
