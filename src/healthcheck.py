#!/usr/bin/env python3
"""
Standalone health check script.
Run this to verify connectivity before the agent runs.

Usage:
    python src/healthcheck.py
    docker exec bonded-content-agent python src/healthcheck.py
"""

import sys
import os
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
load_dotenv()

def main():
    print("=" * 60)
    print("Bonded Content Agent - Health Check")
    print("=" * 60)
    print()
    
    # Check environment variables
    print("[1] Checking environment variables...")
    
    env_vars = {
        "ANTHROPIC_API_KEY": os.getenv("ANTHROPIC_API_KEY"),
        "SUPABASE_URL": os.getenv("SUPABASE_URL"),
        "SUPABASE_SERVICE_KEY": os.getenv("SUPABASE_SERVICE_KEY"),
    }
    
    all_env_ok = True
    for var, value in env_vars.items():
        if value:
            # Mask sensitive values
            if "KEY" in var:
                display = value[:10] + "..." + value[-4:] if len(value) > 14 else "***"
            else:
                display = value
            print(f"    ✓ {var}: {display}")
        else:
            print(f"    ✗ {var}: NOT SET")
            all_env_ok = False
    
    if not all_env_ok:
        print()
        print("FAILED: Missing environment variables")
        print("Please set them in your .env file")
        return 1
    
    print()
    
    # Check Supabase connection
    print("[2] Checking Supabase connection...")
    
    try:
        from database import check_supabase_connection, SupabaseConnectionError
        
        result = check_supabase_connection()
        print(f"    ✓ Connected to Supabase")
        print(f"    ✓ URL: {result['url']}")
        print(f"    ✓ Articles table accessible")
        print(f"    ✓ Current article count: {result['article_count']}")
        
    except SupabaseConnectionError as e:
        print(f"    ✗ Connection failed: {e}")
        print()
        print("FAILED: Cannot connect to Supabase")
        return 1
    except Exception as e:
        print(f"    ✗ Unexpected error: {e}")
        return 1
    
    print()
    
    # Check Anthropic API (just validate key format, don't make a call)
    print("[3] Checking Anthropic API key format...")
    
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if api_key.startswith("sk-ant-"):
        print(f"    ✓ API key format looks valid")
    else:
        print(f"    ⚠ API key doesn't start with 'sk-ant-' - may be invalid")
    
    print()
    
    # Check RSS feed accessibility (test one feed)
    print("[4] Testing RSS feed accessibility...")
    
    try:
        import feedparser
        test_feed = "https://gottman.com/blog/feed"
        feed = feedparser.parse(test_feed)
        
        if feed.entries:
            print(f"    ✓ Can fetch RSS feeds")
            print(f"    ✓ Test feed has {len(feed.entries)} entries")
        else:
            print(f"    ⚠ RSS feed returned no entries (may be temporary)")
            
    except Exception as e:
        print(f"    ⚠ Could not test RSS feed: {e}")
    
    print()
    print("=" * 60)
    print("ALL HEALTH CHECKS PASSED")
    print("=" * 60)
    print()
    print("You can now run the agent:")
    print("    python src/main.py")
    print()
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
