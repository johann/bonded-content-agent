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
    discussion_questions: list = None,
    source_id: str = None
) -> dict:
    """Save a new article to the database with quality scores, metadata, and content transformations."""
    try:
        data = {
            "title": title,
            "blurb": blurb,
            "url": url,
            "is_active": True,
        }

        # Add source tracking
        if source_id:
            data["source_id"] = source_id

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


# ============================================================================
# SOURCE MANAGEMENT FUNCTIONS
# ============================================================================

def get_active_sources(client: Client) -> list:
    """Get all active sources from the database."""
    try:
        result = client.table("sources").select("*").eq("is_active", True).order("name").execute()
        logger.info(f"Loaded {len(result.data)} active sources from database")
        return result.data
    except Exception as e:
        logger.error(f"Error fetching active sources: {e}")
        return []


def update_source_stats(
    client: Client,
    source_id: str,
    fetch_success: bool,
    articles_found: int = 0,
    articles_saved: int = 0
) -> dict:
    """Update source statistics after a fetch operation."""
    try:
        # Get current source data
        source_result = client.table("sources").select("*").eq("id", source_id).execute()
        if not source_result.data:
            return {"success": False, "error": "Source not found"}

        source = source_result.data[0]

        # Calculate new stats
        total_fetches = source.get("total_fetches", 0) + 1
        successful_fetches = source.get("successful_fetches", 0) + (1 if fetch_success else 0)
        failed_fetches = source.get("failed_fetches", 0) + (0 if fetch_success else 1)
        consecutive_failures = 0 if fetch_success else source.get("consecutive_failures", 0) + 1

        total_articles_found = source.get("articles_found", 0) + articles_found
        total_articles_saved = source.get("articles_saved", 0) + articles_saved
        total_articles_rejected = total_articles_found - total_articles_saved

        # Calculate acceptance rate
        acceptance_rate = None
        if total_articles_found > 0:
            acceptance_rate = (total_articles_saved / total_articles_found) * 100

        # Auto-disable sources with too many consecutive failures
        is_active = source.get("is_active", True)
        if consecutive_failures >= 5:
            is_active = False
            logger.warning(f"Auto-disabling source {source['name']} after {consecutive_failures} consecutive failures")

        # Update source
        update_data = {
            "last_fetch_at": "now()",
            "last_fetch_success": fetch_success,
            "total_fetches": total_fetches,
            "successful_fetches": successful_fetches,
            "failed_fetches": failed_fetches,
            "consecutive_failures": consecutive_failures,
            "articles_found": total_articles_found,
            "articles_saved": total_articles_saved,
            "articles_rejected": total_articles_rejected,
            "is_active": is_active
        }

        if acceptance_rate is not None:
            update_data["acceptance_rate"] = round(acceptance_rate, 2)

        result = client.table("sources").update(update_data).eq("id", source_id).execute()

        acceptance_display = f"{acceptance_rate:.1f}%" if acceptance_rate is not None else "N/A"
        logger.info(
            f"Updated source stats: {source['name']} "
            f"(fetches: {total_fetches}, acceptance: {acceptance_display})"
        )

        return {"success": True, "source_id": source_id}

    except Exception as e:
        logger.error(f"Error updating source stats: {e}")
        return {"success": False, "error": str(e)}


def update_source_avg_score(client: Client, source_id: str) -> dict:
    """Recalculate and update the average article score for a source."""
    try:
        # Get all articles from this source
        result = client.table("articles").select("overall_score").eq("source_id", source_id).execute()

        if not result.data:
            return {"success": True, "avg_score": None}

        # Calculate average score
        scores = [article["overall_score"] for article in result.data if article.get("overall_score") is not None]

        if not scores:
            return {"success": True, "avg_score": None}

        avg_score = sum(scores) / len(scores)

        # Update source
        client.table("sources").update({"avg_article_score": round(avg_score, 1)}).eq("id", source_id).execute()

        logger.info(f"Updated source average score: {avg_score:.1f} (from {len(scores)} articles)")

        return {"success": True, "avg_score": avg_score}

    except Exception as e:
        logger.error(f"Error updating source average score: {e}")
        return {"success": False, "error": str(e)}


# ============================================================================
# ENGAGEMENT TRACKING FUNCTIONS
# ============================================================================

def get_top_performing_articles(client: Client, limit: int = 10, days: int = 30) -> list:
    """Get top performing articles by engagement score in the last N days."""
    try:
        # Calculate date threshold
        from datetime import datetime, timedelta
        threshold = datetime.now() - timedelta(days=days)

        # Query top articles with engagement data
        result = client.table("article_engagement") \
            .select("*, articles!inner(id, title, url, category, overall_score)") \
            .gte("last_view_at", threshold.isoformat()) \
            .order("engagement_score", desc=True) \
            .limit(limit) \
            .execute()

        articles = []
        for row in result.data:
            article = row.get("articles", {})
            articles.append({
                "title": article.get("title"),
                "url": article.get("url"),
                "category": article.get("category"),
                "overall_score": article.get("overall_score"),
                "engagement_score": row.get("engagement_score"),
                "save_count": row.get("save_count"),
                "view_count": row.get("view_count"),
                "save_rate": row.get("save_rate"),
                "discussion_rate": row.get("discussion_rate")
            })

        logger.info(f"Retrieved {len(articles)} top performing articles from last {days} days")
        return articles

    except Exception as e:
        logger.error(f"Error fetching top performing articles: {e}")
        return []


def get_engagement_stats(client: Client, days: int = 30) -> dict:
    """Get overall engagement statistics for the last N days."""
    try:
        from datetime import datetime, timedelta
        threshold = datetime.now() - timedelta(days=days)

        # Get aggregated stats
        result = client.table("article_engagement") \
            .select("*") \
            .gte("last_view_at", threshold.isoformat()) \
            .execute()

        if not result.data:
            return {
                "period_days": days,
                "total_articles": 0,
                "total_views": 0,
                "total_saves": 0,
                "avg_save_rate": 0,
                "avg_engagement_score": 0
            }

        total_views = sum(row.get("view_count", 0) for row in result.data)
        total_saves = sum(row.get("save_count", 0) for row in result.data)
        save_rates = [row.get("save_rate", 0) for row in result.data if row.get("save_rate")]
        engagement_scores = [row.get("engagement_score", 0) for row in result.data if row.get("engagement_score")]

        stats = {
            "period_days": days,
            "total_articles": len(result.data),
            "total_views": total_views,
            "total_saves": total_saves,
            "avg_save_rate": round(sum(save_rates) / len(save_rates), 1) if save_rates else 0,
            "avg_engagement_score": round(sum(engagement_scores) / len(engagement_scores), 1) if engagement_scores else 0
        }

        logger.info(f"Retrieved engagement stats for last {days} days: {stats['total_views']} views, {stats['total_saves']} saves")
        return stats

    except Exception as e:
        logger.error(f"Error fetching engagement stats: {e}")
        return {"error": str(e)}
