#!/usr/bin/env python3
"""
Generate collections for Bonded content.
This script generates curated collections based on:
- All 8 categories (communication, conflict, intimacy, trust, etc.)
- High engagement (top performing articles)
- Trending topics (from analysis reports)
- Custom tags

Run this periodically (e.g., weekly after new content is curated)
to keep collections fresh with the latest articles.
"""

import sys
import os
import logging

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database import (
    get_supabase_client,
    check_supabase_connection,
    generate_all_category_collections,
    generate_high_engagement_collection,
    generate_tag_collection,
    get_trending_topics
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def generate_all_collections(client):
    """Generate all collections."""
    logger.info("=" * 60)
    logger.info("GENERATING ALL COLLECTIONS")
    logger.info("=" * 60)

    collections_generated = 0

    # 1. Generate category collections
    logger.info("\n1. Generating category-based collections...")
    result = generate_all_category_collections(client)
    if result.get("success"):
        logger.info(f"✅ Generated {result['count']} category collections:")
        for coll in result.get("collections", []):
            logger.info(f"   - {coll['category']}: {coll['article_count']} articles")
        collections_generated += result['count']
    else:
        logger.error(f"❌ Failed to generate category collections: {result.get('error')}")

    # 2. Generate high engagement collection
    logger.info("\n2. Generating high engagement collection...")
    result = generate_high_engagement_collection(client, days=30, limit=10)
    if result.get("success"):
        logger.info(f"✅ Generated 'Most Popular Articles' collection")
        collections_generated += 1
    else:
        logger.error(f"❌ Failed to generate high engagement collection: {result.get('error')}")

    # 3. Generate collections for trending topics
    logger.info("\n3. Generating collections for trending topics...")
    trending = get_trending_topics(client, limit=5)
    if trending:
        logger.info(f"Found {len(trending)} trending topics")
        for topic in trending[:3]:  # Top 3 trending
            tag = topic["tag"]
            logger.info(f"   Generating collection for trending topic: {tag}")
            result = generate_tag_collection(
                client,
                tag=tag,
                title=f"Trending: {tag.replace('-', ' ').title()}",
                description=f"Articles about {tag.replace('-', ' ')} - currently trending with {topic['recent_count']} recent articles.",
                limit=8
            )
            if result.get("success"):
                logger.info(f"   ✅ Generated collection for '{tag}'")
                collections_generated += 1
            else:
                logger.error(f"   ❌ Failed to generate collection for '{tag}': {result.get('error')}")
    else:
        logger.info("No trending topics found")

    # 4. Generate special collections for popular tags
    logger.info("\n4. Generating collections for popular tags...")
    popular_tags = [
        {
            "tag": "active-listening",
            "title": "Active Listening Skills",
            "description": "Learn to truly hear and understand your partner through active listening techniques."
        },
        {
            "tag": "love-languages",
            "title": "Love Languages",
            "description": "Discover and speak your partner's love language for deeper connection."
        },
        {
            "tag": "emotional-intelligence",
            "title": "Emotional Intelligence",
            "description": "Build emotional awareness and intelligence in your relationship."
        },
        {
            "tag": "date-night",
            "title": "Date Night Ideas",
            "description": "Keep the spark alive with creative date night ideas and quality time together."
        }
    ]

    for tag_info in popular_tags:
        result = generate_tag_collection(
            client,
            tag=tag_info["tag"],
            title=tag_info["title"],
            description=tag_info["description"],
            limit=8
        )
        if result.get("success"):
            logger.info(f"   ✅ Generated collection: {tag_info['title']}")
            collections_generated += 1
        else:
            logger.warning(f"   ⚠️  Could not generate collection for '{tag_info['tag']}': {result.get('error')}")

    logger.info("\n" + "=" * 60)
    logger.info(f"COLLECTION GENERATION COMPLETE")
    logger.info(f"Total collections generated: {collections_generated}")
    logger.info("=" * 60)

    return collections_generated


def main():
    """Main entry point."""
    try:
        # Check database connection
        logger.info("Checking Supabase connection...")
        check_supabase_connection()
        logger.info("✅ Connected to Supabase\n")

        # Get Supabase client
        client = get_supabase_client()

        # Generate all collections
        count = generate_all_collections(client)

        if count > 0:
            logger.info("\n✅ Success! Collections are ready for the app.")
            return 0
        else:
            logger.error("\n❌ No collections were generated.")
            return 1

    except Exception as e:
        logger.error(f"\n❌ Error generating collections: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
