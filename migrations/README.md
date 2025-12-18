# Database Migrations

This directory contains SQL migration scripts for the Bonded Content Agent database schema.

## How to Apply Migrations

1. Log into your Supabase dashboard
2. Navigate to the SQL Editor
3. Copy and paste the migration SQL
4. Run the query

## Migration History

### 001_add_quality_scores.sql
**Date:** 2025-01-XX
**Phase:** Phase 1 - Content Quality & Categorization

Adds quality scoring and categorization capabilities:
- 4 quality score dimensions (relevance, actionability, depth, freshness)
- Auto-calculated overall_score
- Category classification (8 categories)
- Tags array for detailed labeling
- Reading time estimation
- Difficulty level (beginner, intermediate, advanced)

**New Columns:**
- `relevance_score` (DECIMAL 3,1)
- `actionability_score` (DECIMAL 3,1)
- `depth_score` (DECIMAL 3,1)
- `freshness_score` (DECIMAL 3,1)
- `overall_score` (DECIMAL 3,1)
- `category` (TEXT with enum constraint)
- `tags` (TEXT[] array)
- `reading_time_minutes` (INTEGER)
- `difficulty` (TEXT with enum constraint)

**Indexes:**
- `idx_articles_category` - For filtering by category
- `idx_articles_overall_score` - For sorting by quality
- `idx_articles_tags` - GIN index for tag searches

### 002_add_content_transformations.sql
**Date:** 2025-01-XX
**Phase:** Phase 2 - Content Transformation
**Dependencies:** Requires 001_add_quality_scores.sql

Adds AI-generated content transformations for richer user experience:
- Short tweet-style summary (280 chars max)
- Detailed 2-3 paragraph summary
- 3-5 actionable takeaways
- 2-3 discussion questions for couples

**New Columns:**
- `summary_short` (TEXT, max 280 chars)
- `summary_detailed` (TEXT)
- `key_takeaways` (TEXT[] array, 3-5 items)
- `discussion_questions` (TEXT[] array, 2-3 items)

**Indexes:**
- `idx_articles_key_takeaways` - GIN index for takeaway searches
- `idx_articles_discussion_questions` - GIN index for question searches

**Constraints:**
- `summary_short_length` - Ensures short summary <= 280 chars
- `key_takeaways_count` - Ensures 3-5 takeaways
- `discussion_questions_count` - Ensures 2-3 questions

###003_create_sources_table.sql
**Date:** 2025-01-XX
**Phase:** Phase 3 - Source Management
**Dependencies:** None (but runs after 001 and 002)

Moves blog sources from hardcoded config to database with quality tracking:
- Source metadata (name, URLs, description)
- Fetch statistics (success/failure counts, last fetch time)
- Article statistics (found, saved, rejected counts)
- Quality metrics (acceptance rate, avg article score)
- Auto-disable sources after 5 consecutive failures
- Links articles to their sources via source_id

**New Table:**
- `sources` - Blog sources with quality tracking

**New Column on articles:**
- `source_id` (UUID) - Foreign key to sources table

**Indexes:**
- `idx_sources_is_active` - Filter active sources
- `idx_sources_acceptance_rate` - Sort by quality
- `idx_sources_avg_article_score` - Sort by article quality
- `idx_sources_last_fetch_at` - Track freshness
- `idx_articles_source_id` - Link articles to sources

**Constraints:**
- `acceptance_rate_range` - Ensures 0-100%
- `avg_article_score_range` - Ensures 0-10

**Post-Migration:**
After running this migration, populate sources from hardcoded config:
```bash
python scripts/migrate_sources_to_db.py
```

### 004_create_engagement_tables.sql
**Date:** 2025-01-XX
**Phase:** Phase 5 - Engagement Tracking Integration
**Dependencies:** Requires 001_add_quality_scores.sql

Enables data-driven curation by tracking user engagement:
- Raw event tracking (views, saves, shares, click-throughs, discussions)
- Aggregated engagement metrics per article
- Automated metric calculation functions
- Agent learns from what content performs best

**New Tables:**
- `engagement_events` - Raw engagement events from app
- `article_engagement` - Aggregated metrics per article

**Event Types:**
- `view` - Article card shown to user
- `save` - User bookmarked article
- `share` - User shared article
- `click_through` - User opened original article
- `discussion_start` - User started discussing with partner
- `unsave` - User removed bookmark

**Calculated Metrics:**
- Save rate (% of viewers who saved)
- Share rate (% of viewers who shared)
- Click rate (% of viewers who clicked through)
- Discussion rate (% of viewers who started discussion)
- Engagement score (weighted composite: discussion 4x, save 3x, share 2x, click 1.5x)

**Functions:**
- `refresh_article_engagement(article_id)` - Recalculate metrics for one article
- `refresh_all_article_engagement()` - Recalculate all (run periodically)

**Indexes:**
- `idx_engagement_events_article_id` - Fast event lookup
- `idx_engagement_events_event_type` - Filter by event type
- `idx_engagement_events_created_at` - Time-based queries
- `idx_article_engagement_engagement_score` - Sort by engagement
- `idx_article_engagement_save_count` - Popular content

**Agent Integration:**
- Agent calls `get_top_performing_articles` before curating
- Agent calls `get_engagement_stats` to understand patterns
- Agent learns which categories/topics/formats work best
- Curation becomes data-driven over time

**App Implementation Required:**
Your Bonded app needs to track events:
```javascript
// When article card is shown
await supabase.from('engagement_events').insert({
  article_id: article.id,
  event_type: 'view',
  user_id: user.id // optional
})

// When user saves/shares/etc
await supabase.from('engagement_events').insert({
  article_id: article.id,
  event_type: 'save', // or 'share', 'click_through', 'discussion_start'
  user_id: user.id
})
```

Then refresh metrics periodically (cron job or edge function):
```sql
SELECT refresh_all_article_engagement();
```

### 005_create_learning_tables.sql
**Date:** 2025-01-XX
**Phase:** Phase 6 - Feedback Loop & Learning
**Dependencies:** Requires 004_create_engagement_tables.sql

Closes the learning loop - agent learns from engagement data and improves over time:
- Stores learned insights (top sources, categories, topics)
- Logs all agent decisions with reasoning
- Dynamic system prompt incorporates learnings
- Automated learning analysis
- Confidence scoring based on data quality

**New Tables:**
- `agent_learnings` - Stored insights from engagement analysis
- `agent_decisions` - Log of every save/skip decision with reasoning

**Learning Types:**
- `source_performance` - Which sources produce engaging content
- `category_performance` - Which categories users engage with most
- `topic_performance` - Trending topics/tags
- `blurb_effectiveness` - What blurb styles work best (future)
- `content_pattern` - Common patterns in high-performing content (future)
- `user_preference` - User segment preferences (future)
- `seasonal_trend` - Time-based patterns (future)

**Views:**
- `source_performance_view` - Sources ranked by engagement
- `category_performance_view` - Categories ranked by engagement
- `tag_performance_view` - Tags/topics ranked by engagement

**Functions:**
- `calculate_confidence(data_points, period_days)` - Confidence scoring

**Agent Integration:**
- Agent loads learnings at startup
- System prompt dynamically enhanced with learned insights
- Agent prioritizes proven high-performing content
- Decisions logged for future analysis

**Learning Workflow:**
1. Run `update_learnings()` weekly via cron or manually
2. Analyzes engagement data to derive insights
3. Saves learnings to database with confidence scores
4. Next agent run automatically incorporates learnings
5. Agent becomes smarter over time

**Example Learnings:**
```json
{
  "learning_type": "category_performance",
  "key": "top_categories",
  "value": {
    "top_categories": [
      {"category": "communication", "avg_engagement_score": 42.5},
      {"category": "conflict", "avg_engagement_score": 38.2}
    ]
  },
  "confidence": 0.85,
  "data_points": 127
}
```

**Running Learning Analysis:**
```python
from src.learning import update_learnings
from src.database import get_supabase_client

client = get_supabase_client()
result = update_learnings(client, days=30)
# Analyzes last 30 days, saves learnings
```

Or create a cron job/edge function:
```sql
-- Custom function to run weekly
CREATE OR REPLACE FUNCTION run_weekly_learning_analysis()
RETURNS JSON AS $$
  -- Call Python function via pg_python extension or external service
  -- Or implement learning logic in PL/pgSQL
$$ LANGUAGE plpgsql;
```

### 006_create_analysis_reports_table.sql
**Date:** 2025-01-XX
**Phase:** Phase 7 - Trend & Gap Analysis
**Dependencies:** Requires 005_create_learning_tables.sql

Enables automated weekly trend analysis with content gap identification:
- Weekly analysis reports with trends, gaps, and recommendations
- Trending topic detection (recent vs historical volume)
- Top article and source identification
- Content gap analysis (underserved topics, stale popular topics)
- Actionable recommendations for next curation cycle
- Executive summaries for stakeholders

**New Table:**
- `content_analysis_reports` - Weekly analysis reports with insights

**New Views:**
- `recent_article_performance` - Articles from last 7 days with engagement
- `tag_trending_analysis` - Tags ranked by trending percentage

**New Functions:**
- `identify_content_gaps()` - Finds content opportunities

**Report Fields:**
- `trending_topics` - Topics with increasing engagement/volume
- `top_articles` - Best performers in the period
- `top_sources` - Best performing sources
- `content_gaps` - Identified gaps and opportunities
- `recommendations` - Actionable next steps
- `summary` - Executive summary of key findings

**Gap Types Identified:**
1. `low_volume_high_engagement` - Categories with high engagement but few articles
2. `stale_popular_topic` - Popular topics without recent coverage

**Agent Integration:**
- Agent can query analysis reports for context
- Tools: `get_latest_analysis_report`, `get_trending_topics`, `get_content_gaps`
- Uses insights to inform curation decisions

**Running Weekly Analysis:**
```bash
# Manual run
python scripts/run_weekly_analysis.py

# Schedule weekly (crontab example - every Monday at 9am)
0 9 * * 1 cd /path/to/bonded-content-agent && python scripts/run_weekly_analysis.py
```

**Example Analysis Report:**
```json
{
  "report_type": "weekly",
  "period_start": "2025-01-13T00:00:00Z",
  "period_end": "2025-01-20T00:00:00Z",
  "trending_topics": {
    "topics": [
      {"tag": "communication", "trending_percentage": 85.2, "status": "🔥 Hot"},
      {"tag": "conflict-resolution", "trending_percentage": 62.1, "status": "🔥 Hot"}
    ]
  },
  "content_gaps": {
    "gaps": [
      {
        "type": "low_volume_high_engagement",
        "description": "Category \"finances\" has high engagement but few articles",
        "priority": "high"
      }
    ]
  },
  "recommendations": {
    "recommendations": [
      {
        "type": "trending_focus",
        "priority": "high",
        "recommendation": "Prioritize content covering: communication, conflict-resolution, intimacy"
      }
    ]
  },
  "summary": "📊 Week in Review: Published 15 articles with 1,234 total views..."
}
```

**Python Integration:**
```python
from src.analysis_agent import TrendAnalysisAgent
from src.database import get_supabase_client

client = get_supabase_client()
agent = TrendAnalysisAgent(client)

# Run weekly analysis
result = agent.analyze_week(days=7)
print(result["summary"])
```

## Verification

After applying a migration, verify the changes:

```sql
-- Check that columns were added
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'articles';

-- Check constraints
SELECT constraint_name, constraint_type
FROM information_schema.table_constraints
WHERE table_name = 'articles';

-- Check indexes
SELECT indexname, indexdef
FROM pg_indexes
WHERE tablename = 'articles';
```
