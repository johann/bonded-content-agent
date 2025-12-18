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
