#!/usr/bin/env python3
"""
One-time migration script to move hardcoded blog sources to the database.
Run this once after creating the sources table (migration 003).

Usage:
    python scripts/migrate_sources_to_db.py
"""

import sys
import os

# Add parent directory to path so we can import from src
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.config import BLOG_SOURCES
from src.database import get_supabase_client
import logging

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


def migrate_sources():
    """Migrate hardcoded blog sources to the sources table."""
    try:
        client = get_supabase_client()
        logger.info(f"Migrating {len(BLOG_SOURCES)} sources to database...")

        migrated = 0
        skipped = 0

        for source in BLOG_SOURCES:
            # Check if source already exists
            existing = client.table("sources").select("id").eq("rss_url", source["rss"]).execute()

            if existing.data:
                logger.info(f"  ⏭️  Skipping {source['name']} (already exists)")
                skipped += 1
                continue

            # Insert source
            data = {
                "name": source["name"],
                "website_url": source["url"],
                "rss_url": source["rss"],
                "description": source.get("notes"),
                "discovered_by": "manual",
                "is_active": True
            }

            result = client.table("sources").insert(data).execute()
            logger.info(f"  ✅ Migrated {source['name']}")
            migrated += 1

        logger.info(f"\n📊 Migration complete!")
        logger.info(f"  • Migrated: {migrated}")
        logger.info(f"  • Skipped: {skipped}")
        logger.info(f"  • Total: {len(BLOG_SOURCES)}")

        return True

    except Exception as e:
        logger.error(f"❌ Migration failed: {e}")
        return False


if __name__ == "__main__":
    success = migrate_sources()
    sys.exit(0 if success else 1)
