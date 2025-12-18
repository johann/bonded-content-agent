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
