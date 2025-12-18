"""
Database operations for the Bonded Content Agent.
"""

import logging
from supabase import create_client, Client
from config import SUPABASE_URL, SUPABASE_SERVICE_KEY

logger = logging.getLogger(__name__)


class SupabaseConnectionError(Exception):
    """Raised when Supabase connection check fails."""
    pass


def check_supabase_connection() -> dict:
    """
    Perform a health check on the Supabase connection.
    Returns a dict with connection status and details.
    Raises SupabaseConnectionError if connection fails.
    """
    result = {
        "connected": False,
        "url": SUPABASE_URL,
        "table_accessible": False,
        "article_count": None,
        "error": None
    }
    
    # Check environment variables
    if not SUPABASE_URL:
        result["error"] = "SUPABASE_URL environment variable not set"
        logger.error(f"Health check failed: {result['error']}")
        raise SupabaseConnectionError(result["error"])
    
    if not SUPABASE_SERVICE_KEY:
        result["error"] = "SUPABASE_SERVICE_KEY environment variable not set"
        logger.error(f"Health check failed: {result['error']}")
        raise SupabaseConnectionError(result["error"])
    
    try:
        # Attempt to create client
        logger.info(f"Attempting connection to Supabase: {SUPABASE_URL}")
        client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
        result["connected"] = True
        logger.info("Supabase client created successfully")
        
        # Test table access with a simple query
        logger.info("Testing access to 'articles' table...")
        response = client.table("articles").select("id", count="exact").limit(1).execute()
        result["table_accessible"] = True
        result["article_count"] = response.count
        logger.info(f"Articles table accessible. Current count: {response.count}")
        
        return result
        
    except Exception as e:
        error_msg = str(e)
        result["error"] = error_msg
        
        # Provide more helpful error messages for common issues
        if "Invalid API key" in error_msg or "invalid_api_key" in error_msg.lower():
            result["error"] = "Invalid Supabase API key. Check SUPABASE_SERVICE_KEY."
        elif "relation" in error_msg.lower() and "does not exist" in error_msg.lower():
            result["error"] = "Articles table does not exist. Please create it first."
            result["connected"] = True  # Connection worked, just table missing
        elif "timeout" in error_msg.lower() or "timed out" in error_msg.lower():
            result["error"] = f"Connection timed out. Check network/firewall settings. URL: {SUPABASE_URL}"
        elif "name resolution" in error_msg.lower() or "nodename" in error_msg.lower():
            result["error"] = f"DNS resolution failed for {SUPABASE_URL}. Check the URL."
        elif "connection refused" in error_msg.lower():
            result["error"] = f"Connection refused. Is Supabase accessible from this container? URL: {SUPABASE_URL}"
        
        logger.error(f"Health check failed: {result['error']}")
        logger.debug(f"Full error: {error_msg}")
        raise SupabaseConnectionError(result["error"])


def get_supabase_client() -> Client:
    """Create and return a Supabase client."""
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set")
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)


def check_article_exists(client: Client, url: str) -> bool:
    """Check if an article with the given URL already exists."""
    try:
        result = client.table("articles").select("id").eq("url", url).execute()
        return len(result.data) > 0
    except Exception as e:
        logger.error(f"Error checking if article exists: {e}")
        return False


def save_article(
    client: Client,
    title: str,
    blurb: str,
    url: str,
    image_url: str = None,
    relevance_score: float = None,
    actionability_score: float = None,
    depth_score: float = None,
    freshness_score: float = None,
    category: str = None,
    tags: list = None,
    reading_time_minutes: int = None,
    difficulty: str = None,
    summary_short: str = None,
    summary_detailed: str = None,
    key_takeaways: list = None,
    discussion_questions: list = None
) -> dict:
    """Save a new article to the database with quality scores, metadata, and content transformations."""
    try:
        data = {
            "title": title,
            "blurb": blurb,
            "url": url,
            "is_active": True,
        }

        # Add optional fields if provided
        if image_url:
            data["image_url"] = image_url
        if relevance_score is not None:
            data["relevance_score"] = relevance_score
        if actionability_score is not None:
            data["actionability_score"] = actionability_score
        if depth_score is not None:
            data["depth_score"] = depth_score
        if freshness_score is not None:
            data["freshness_score"] = freshness_score
        if category:
            data["category"] = category
        if tags:
            data["tags"] = tags
        if reading_time_minutes is not None:
            data["reading_time_minutes"] = reading_time_minutes
        if difficulty:
            data["difficulty"] = difficulty
        if summary_short:
            data["summary_short"] = summary_short
        if summary_detailed:
            data["summary_detailed"] = summary_detailed
        if key_takeaways:
            data["key_takeaways"] = key_takeaways
        if discussion_questions:
            data["discussion_questions"] = discussion_questions

        # Calculate overall score as average of the 4 dimension scores
        if all(score is not None for score in [relevance_score, actionability_score, depth_score, freshness_score]):
            data["overall_score"] = (relevance_score + actionability_score + depth_score + freshness_score) / 4

        result = client.table("articles").insert(data).execute()
        logger.info(f"Saved article: {title} (category: {category}, overall_score: {data.get('overall_score', 'N/A')}, takeaways: {len(key_takeaways) if key_takeaways else 0})")
        return {"success": True, "id": result.data[0]["id"] if result.data else None}
    except Exception as e:
        logger.error(f"Error saving article: {e}")
        return {"success": False, "error": str(e)}


def get_existing_urls(client: Client) -> set:
    """Get all existing article URLs to avoid duplicates."""
    try:
        result = client.table("articles").select("url").execute()
        return {row["url"] for row in result.data}
    except Exception as e:
        logger.error(f"Error fetching existing URLs: {e}")
        return set()


def get_article_count(client: Client) -> int:
    """Get total count of articles in database."""
    try:
        result = client.table("articles").select("id", count="exact").execute()
        return result.count or 0
    except Exception as e:
        logger.error(f"Error getting article count: {e}")
        return 0
