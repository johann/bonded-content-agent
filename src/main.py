#!/usr/bin/env python3
"""
Main entry point for the Bonded Content Agent.
Run this script to execute the content curation process.
"""

import sys
import logging
from datetime import datetime
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from config import LOG_LEVEL, SUPABASE_URL
from database import (
    get_supabase_client, 
    get_article_count, 
    check_supabase_connection,
    SupabaseConnectionError
)
from agent import BondedContentAgent


def setup_logging():
    """Configure logging for the application."""
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    handlers = [logging.StreamHandler(sys.stdout)]
    
    # Only add file handler if /app/logs exists and is writable
    # (Render has ephemeral filesystem, so we primarily use stdout)
    log_dir = Path("/app/logs")
    try:
        log_dir.mkdir(exist_ok=True)
        handlers.append(
            logging.FileHandler(
                log_dir / f"agent_{datetime.now().strftime('%Y%m%d')}.log"
            )
        )
    except (PermissionError, OSError):
        pass  # Running on Render or similar - just use stdout
    
    # Configure root logger
    logging.basicConfig(
        level=getattr(logging, LOG_LEVEL.upper(), logging.INFO),
        format=log_format,
        handlers=handlers
    )


def run_startup_checks(logger) -> bool:
    """
    Run startup health checks before proceeding with the agent.
    Returns True if all checks pass, False otherwise.
    """
    logger.info("-" * 60)
    logger.info("STARTUP HEALTH CHECKS")
    logger.info("-" * 60)
    
    # Check 1: Supabase Connection
    logger.info("[1/1] Checking Supabase connection...")
    try:
        result = check_supabase_connection()
        logger.info(f"  ✓ Connected to: {result['url']}")
        logger.info(f"  ✓ Articles table accessible")
        logger.info(f"  ✓ Current article count: {result['article_count']}")
        logger.info("-" * 60)
        logger.info("ALL STARTUP CHECKS PASSED")
        logger.info("-" * 60)
        return True
        
    except SupabaseConnectionError as e:
        logger.error(f"  ✗ Supabase connection failed: {e}")
        logger.error("-" * 60)
        logger.error("STARTUP CHECKS FAILED - Agent will not proceed")
        logger.error("-" * 60)
        logger.error("")
        logger.error("Troubleshooting tips:")
        logger.error("  1. Verify SUPABASE_URL is correct in your .env file")
        logger.error("  2. Verify SUPABASE_SERVICE_KEY is the service_role key (not anon)")
        logger.error("  3. Check if Supabase is accessible from this container")
        logger.error("  4. If using Dokploy, ensure containers can communicate")
        logger.error(f"  5. Try: curl -I {SUPABASE_URL}/rest/v1/")
        logger.error("")
        return False


def main():
    """Main function to run the content agent."""
    setup_logging()
    logger = logging.getLogger(__name__)
    
    logger.info("=" * 60)
    logger.info("Bonded Content Agent - Starting Run")
    logger.info(f"Timestamp: {datetime.now().isoformat()}")
    logger.info("=" * 60)
    
    # Run startup health checks first
    if not run_startup_checks(logger):
        logger.error("Exiting due to failed startup checks")
        return 2  # Exit code 2 for configuration/connection issues
    
    try:
        # Initialize Supabase client (we know it works from health check)
        logger.info("Initializing Supabase client...")
        supabase = get_supabase_client()
        
        # Get current article count
        current_count = get_article_count(supabase)
        logger.info(f"Current articles in database: {current_count}")
        
        # Run the agent
        agent = BondedContentAgent(supabase)
        result = agent.run()
        
        # Log results
        logger.info("=" * 60)
        logger.info("Run Complete")
        logger.info(f"Success: {result.get('success')}")
        logger.info(f"Articles saved: {result.get('articles_saved', 0)}")
        logger.info(f"Articles skipped: {result.get('articles_skipped', 0)}")
        logger.info(f"Agent iterations: {result.get('iterations', 0)}")
        
        if result.get('summary'):
            logger.info(f"Agent summary: {result['summary'][:500]}...")
        
        if result.get('error'):
            logger.error(f"Error: {result['error']}")
            
        # Get new article count
        new_count = get_article_count(supabase)
        logger.info(f"New total articles in database: {new_count}")
        logger.info("=" * 60)
        
        return 0 if result.get('success') else 1
        
    except Exception as e:
        logger.exception(f"Fatal error running agent: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
