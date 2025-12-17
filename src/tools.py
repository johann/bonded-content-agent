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
from supabase import Client

from database import check_article_exists, save_article, get_existing_urls

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
                    "description": "Optional image URL for the article"
                }
            },
            "required": ["title", "blurb", "url"]
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
    }
]


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
            
            # Try to extract image
            if "media_content" in entry:
                post["image_url"] = entry.media_content[0].get("url", "")
            elif "enclosures" in entry and entry.enclosures:
                post["image_url"] = entry.enclosures[0].get("href", "")
                
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
        
        # Remove script, style, nav, footer elements
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
        
        # Try to find the main image
        image_url = None
        og_image = soup.find("meta", property="og:image")
        if og_image:
            image_url = og_image.get("content")
        
        return {
            "success": True,
            "url": url,
            "content": text,
            "image_url": image_url
        }
    except Exception as e:
        logger.error(f"Error fetching article {url}: {e}")
        return {
            "success": False,
            "url": url,
            "error": str(e)
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
    image_url: Optional[str] = None
) -> dict:
    """Save an article to the database."""
    # Double-check it doesn't exist
    if check_article_exists(supabase_client, url):
        return {
            "success": False,
            "error": "Article already exists",
            "url": url
        }
    
    result = save_article(supabase_client, title, blurb, url, image_url)
    result["url"] = url
    result["title"] = title
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
                image_url=tool_input.get("image_url")
            )
        elif tool_name == "get_all_existing_urls":
            result = get_all_existing_urls_tool(supabase_client)
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
