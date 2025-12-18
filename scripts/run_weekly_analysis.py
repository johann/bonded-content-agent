#!/usr/bin/env python3
"""
Run weekly trend analysis for Bonded content.
This script should be run weekly (via cron or scheduler) to:
1. Analyze trending topics and top articles
2. Identify content gaps
3. Generate recommendations for the next week
4. Save analysis report to database
"""

import sys
import os
import logging

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database import get_supabase_client, check_supabase_connection
from src.analysis_agent import TrendAnalysisAgent

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """Run weekly trend analysis."""
    logger.info("=" * 60)
    logger.info("BONDED WEEKLY TREND ANALYSIS")
    logger.info("=" * 60)

    try:
        # Check database connection
        logger.info("Checking Supabase connection...")
        check_supabase_connection()
        logger.info("✅ Connected to Supabase")

        # Get Supabase client
        client = get_supabase_client()

        # Initialize analysis agent
        logger.info("\nInitializing Trend Analysis Agent...")
        agent = TrendAnalysisAgent(client)

        # Run weekly analysis (last 7 days)
        logger.info("\nRunning weekly analysis...")
        result = agent.analyze_week(days=7)

        if result.get("success"):
            logger.info("\n" + "=" * 60)
            logger.info("ANALYSIS COMPLETE")
            logger.info("=" * 60)
            logger.info(f"Report ID: {result.get('report_id')}")
            logger.info(f"Trending Topics: {result.get('trending_topics_count')}")
            logger.info(f"Content Gaps: {result.get('content_gaps_count')}")
            logger.info(f"Recommendations: {result.get('recommendations_count')}")
            logger.info("\nSummary:")
            logger.info(result.get("summary", "No summary available"))
            logger.info("=" * 60)

            return 0
        else:
            logger.error(f"\n❌ Analysis failed: {result.get('error')}")
            return 1

    except Exception as e:
        logger.error(f"\n❌ Error running weekly analysis: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
