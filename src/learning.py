"""
Learning and analysis functions for the Bonded Content Agent.
Analyzes engagement data to derive insights and improve curation.
"""

import logging
from datetime import datetime, timedelta
from supabase import Client

logger = logging.getLogger(__name__)


def analyze_source_performance(client: Client, days: int = 30) -> dict:
    """
    Analyze which sources produce the most engaging content.
    Returns top sources to prioritize.
    """
    try:
        result = client.table("source_performance_view").select("*").execute()

        if not result.data:
            return {"top_sources": [], "data_points": 0}

        # Filter sources with enough data
        sources_with_data = [s for s in result.data if s.get("total_views", 0) > 10]

        top_sources = [
            {
                "name": s["name"],
                "avg_engagement_score": round(s.get("avg_engagement_score", 0), 1),
                "avg_article_score": round(s.get("avg_article_score", 0), 1),
                "acceptance_rate": round(s.get("acceptance_rate", 0), 1),
                "total_saves": s.get("total_saves", 0)
            }
            for s in sources_with_data[:5]  # Top 5 sources
        ]

        logger.info(f"Analyzed {len(sources_with_data)} sources with engagement data")

        return {
            "top_sources": top_sources,
            "data_points": len(sources_with_data)
        }

    except Exception as e:
        logger.error(f"Error analyzing source performance: {e}")
        return {"top_sources": [], "data_points": 0}


def analyze_category_performance(client: Client, days: int = 90) -> dict:
    """
    Analyze which categories have highest engagement.
    Returns top categories to prioritize.
    """
    try:
        result = client.table("category_performance_view").select("*").execute()

        if not result.data:
            return {"top_categories": [], "data_points": 0}

        # Filter categories with enough data
        categories_with_data = [c for c in result.data if c.get("article_count", 0) >= 5]

        top_categories = [
            {
                "category": c["category"],
                "avg_engagement_score": round(c.get("avg_engagement_score", 0), 1),
                "avg_save_rate": round(c.get("avg_save_rate", 0), 1),
                "avg_discussion_rate": round(c.get("avg_discussion_rate", 0), 1),
                "article_count": c.get("article_count", 0)
            }
            for c in categories_with_data[:5]  # Top 5 categories
        ]

        logger.info(f"Analyzed {len(categories_with_data)} categories with engagement data")

        return {
            "top_categories": top_categories,
            "data_points": sum(c.get("article_count", 0) for c in categories_with_data)
        }

    except Exception as e:
        logger.error(f"Error analyzing category performance: {e}")
        return {"top_categories": [], "data_points": 0}


def analyze_topic_performance(client: Client, days: int = 90) -> dict:
    """
    Analyze which topics/tags have highest engagement.
    Returns trending topics.
    """
    try:
        result = client.table("tag_performance_view").select("*").limit(20).execute()

        if not result.data:
            return {"top_topics": [], "data_points": 0}

        top_topics = [
            {
                "tag": t["tag"],
                "avg_engagement_score": round(t.get("avg_engagement_score", 0), 1),
                "avg_save_rate": round(t.get("avg_save_rate", 0), 1),
                "article_count": t.get("article_count", 0)
            }
            for t in result.data[:10]  # Top 10 topics
        ]

        logger.info(f"Analyzed {len(result.data)} topics with engagement data")

        return {
            "top_topics": top_topics,
            "data_points": sum(t.get("article_count", 0) for t in result.data)
        }

    except Exception as e:
        logger.error(f"Error analyzing topic performance: {e}")
        return {"top_topics": [], "data_points": 0}


def update_learnings(client: Client, days: int = 30) -> dict:
    """
    Run all analyses and save learnings to database.
    Call this periodically (e.g., weekly) to keep learnings fresh.
    """
    try:
        logger.info(f"Running learning analysis for last {days} days")

        # Analyze each dimension
        source_analysis = analyze_source_performance(client, days)
        category_analysis = analyze_category_performance(client, days)
        topic_analysis = analyze_topic_performance(client, days)

        # Calculate confidence based on data points
        def calc_confidence(data_points: int) -> float:
            if data_points >= 50:
                return 0.95
            elif data_points >= 30:
                return 0.85
            elif data_points >= 20:
                return 0.75
            elif data_points >= 10:
                return 0.60
            elif data_points >= 5:
                return 0.40
            else:
                return 0.20

        learnings_saved = 0

        # Save source performance learning
        if source_analysis["top_sources"]:
            client.table("agent_learnings").upsert({
                "learning_type": "source_performance",
                "key": "top_sources",
                "value": source_analysis,
                "confidence": calc_confidence(source_analysis["data_points"]),
                "based_on_period_days": days,
                "data_points": source_analysis["data_points"]
            }, on_conflict="key").execute()
            learnings_saved += 1
            logger.info(f"Saved source performance learning ({source_analysis['data_points']} data points)")

        # Save category performance learning
        if category_analysis["top_categories"]:
            client.table("agent_learnings").upsert({
                "learning_type": "category_performance",
                "key": "top_categories",
                "value": category_analysis,
                "confidence": calc_confidence(len(category_analysis["top_categories"])),
                "based_on_period_days": days,
                "data_points": category_analysis["data_points"]
            }, on_conflict="key").execute()
            learnings_saved += 1
            logger.info(f"Saved category performance learning ({len(category_analysis['top_categories'])} categories)")

        # Save topic performance learning
        if topic_analysis["top_topics"]:
            client.table("agent_learnings").upsert({
                "learning_type": "topic_performance",
                "key": "top_topics",
                "value": topic_analysis,
                "confidence": calc_confidence(len(topic_analysis["top_topics"])),
                "based_on_period_days": days,
                "data_points": topic_analysis["data_points"]
            }, on_conflict="key").execute()
            learnings_saved += 1
            logger.info(f"Saved topic performance learning ({len(topic_analysis['top_topics'])} topics)")

        logger.info(f"✅ Learning analysis complete. Saved {learnings_saved} learnings.")

        return {
            "success": True,
            "learnings_saved": learnings_saved,
            "source_analysis": source_analysis,
            "category_analysis": category_analysis,
            "topic_analysis": topic_analysis
        }

    except Exception as e:
        logger.error(f"Error updating learnings: {e}")
        return {"success": False, "error": str(e)}


def get_current_learnings(client: Client) -> dict:
    """
    Get all current learnings to inject into system prompt.
    Returns dict with learning categories.
    """
    try:
        result = client.table("agent_learnings") \
            .select("*") \
            .order("updated_at", desc=True) \
            .execute()

        if not result.data:
            return {}

        learnings = {}
        for learning in result.data:
            key = learning["key"]
            value = learning["value"]
            confidence = learning.get("confidence", 0)

            # Only include high-confidence learnings
            if confidence >= 0.60:
                learnings[key] = {
                    "data": value,
                    "confidence": confidence,
                    "updated_at": learning["updated_at"]
                }

        logger.info(f"Retrieved {len(learnings)} high-confidence learnings")
        return learnings

    except Exception as e:
        logger.error(f"Error getting current learnings: {e}")
        return {}


def log_decision(
    client: Client,
    article_url: str,
    decision: str,
    reasoning: str,
    article_title: str = None,
    source_id: str = None,
    scores: dict = None,
    category: str = None,
    tags: list = None,
    agent_run_id: str = None
) -> dict:
    """
    Log an agent decision (save or skip) with reasoning.
    Used for later analysis and learning.
    """
    try:
        data = {
            "article_url": article_url,
            "decision": decision,
            "reasoning": reasoning,
            "article_title": article_title,
            "source_id": source_id,
            "category": category,
            "tags": tags,
            "agent_run_id": agent_run_id
        }

        if scores:
            data["relevance_score"] = scores.get("relevance_score")
            data["actionability_score"] = scores.get("actionability_score")
            data["depth_score"] = scores.get("depth_score")
            data["freshness_score"] = scores.get("freshness_score")
            data["overall_score"] = scores.get("overall_score")

        result = client.table("agent_decisions").insert(data).execute()
        return {"success": True, "id": result.data[0]["id"] if result.data else None}

    except Exception as e:
        logger.error(f"Error logging decision: {e}")
        return {"success": False, "error": str(e)}
