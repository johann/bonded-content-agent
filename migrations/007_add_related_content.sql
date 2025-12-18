-- Migration: Add Related Content Linking
-- Phase 8: Related Content Linking
-- Run this in your Supabase SQL editor AFTER running 001-006

-- ============================================================================
-- RELATED ARTICLES TABLE
-- Stores calculated relationships between articles
-- ============================================================================

CREATE TABLE IF NOT EXISTS article_relationships (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

  -- The source article
  article_id UUID NOT NULL REFERENCES articles(id) ON DELETE CASCADE,

  -- The related article
  related_article_id UUID NOT NULL REFERENCES articles(id) ON DELETE CASCADE,

  -- Similarity score (0-100)
  similarity_score DECIMAL(5,2) NOT NULL,

  -- Why they're related
  relationship_type TEXT NOT NULL CHECK (
    relationship_type IN (
      'same_category',
      'overlapping_tags',
      'same_source',
      'similar_topics',
      'complementary'
    )
  ),

  -- Details about the relationship
  relationship_details JSONB,

  -- When calculated
  calculated_at TIMESTAMP WITH TIME ZONE DEFAULT now(),

  -- Prevent duplicate relationships
  UNIQUE(article_id, related_article_id)
);

-- Create indexes for fast lookups
CREATE INDEX IF NOT EXISTS idx_article_relationships_article_id
  ON article_relationships(article_id);
CREATE INDEX IF NOT EXISTS idx_article_relationships_related_article_id
  ON article_relationships(related_article_id);
CREATE INDEX IF NOT EXISTS idx_article_relationships_similarity_score
  ON article_relationships(similarity_score DESC);
CREATE INDEX IF NOT EXISTS idx_article_relationships_relationship_type
  ON article_relationships(relationship_type);

-- Add comments
COMMENT ON TABLE article_relationships IS 'Calculated relationships between articles for "Related Content" features';
COMMENT ON COLUMN article_relationships.similarity_score IS 'Similarity score 0-100 based on tags, category, topics';
COMMENT ON COLUMN article_relationships.relationship_type IS 'Type of relationship: same_category, overlapping_tags, same_source, similar_topics, complementary';
COMMENT ON COLUMN article_relationships.relationship_details IS 'Additional details like shared tags, overlap percentage, etc.';


-- ============================================================================
-- FUNCTION: Calculate Related Articles
-- Finds related articles based on tags, category, and topic similarity
-- ============================================================================

CREATE OR REPLACE FUNCTION calculate_related_articles(
  p_article_id UUID,
  p_limit INTEGER DEFAULT 5
)
RETURNS TABLE (
  related_article_id UUID,
  title TEXT,
  category TEXT,
  similarity_score DECIMAL(5,2),
  relationship_type TEXT,
  shared_tags TEXT[]
) AS $$
BEGIN
  RETURN QUERY
  WITH source_article AS (
    SELECT id, category, tags, source_id
    FROM articles
    WHERE id = p_article_id
  ),
  candidate_articles AS (
    SELECT
      a.id,
      a.title,
      a.category,
      a.tags,
      a.source_id,
      sa.category as source_category,
      sa.tags as source_tags,
      sa.source_id as source_source_id
    FROM articles a
    CROSS JOIN source_article sa
    WHERE a.id != p_article_id
      AND a.is_active = true
  ),
  scored_articles AS (
    SELECT
      ca.id,
      ca.title,
      ca.category,
      -- Calculate similarity score
      (
        -- Same category: +30 points
        CASE WHEN ca.category = ca.source_category THEN 30 ELSE 0 END
        +
        -- Tag overlap: up to 50 points based on Jaccard similarity
        CASE
          WHEN ca.tags IS NOT NULL AND ca.source_tags IS NOT NULL THEN
            LEAST(50, (
              SELECT COUNT(*)::DECIMAL
              FROM unnest(ca.tags) t1
              WHERE t1 = ANY(ca.source_tags)
            ) * 50.0 / (
              SELECT COUNT(DISTINCT t)
              FROM unnest(ca.tags || ca.source_tags) t
            ))
          ELSE 0
        END
        +
        -- Same source: +20 points
        CASE WHEN ca.source_id = ca.source_source_id THEN 20 ELSE 0 END
      )::DECIMAL(5,2) as similarity_score,
      -- Determine primary relationship type
      CASE
        WHEN ca.category = ca.source_category
          AND EXISTS (
            SELECT 1 FROM unnest(ca.tags) t1
            WHERE t1 = ANY(ca.source_tags)
          ) THEN 'similar_topics'
        WHEN ca.category = ca.source_category THEN 'same_category'
        WHEN EXISTS (
          SELECT 1 FROM unnest(ca.tags) t1
          WHERE t1 = ANY(ca.source_tags)
        ) THEN 'overlapping_tags'
        WHEN ca.source_id = ca.source_source_id THEN 'same_source'
        ELSE 'complementary'
      END as relationship_type,
      -- Calculate shared tags
      CASE
        WHEN ca.tags IS NOT NULL AND ca.source_tags IS NOT NULL THEN
          ARRAY(
            SELECT t1
            FROM unnest(ca.tags) t1
            WHERE t1 = ANY(ca.source_tags)
          )
        ELSE ARRAY[]::TEXT[]
      END as shared_tags
    FROM candidate_articles ca
  )
  SELECT
    sa.id,
    sa.title,
    sa.category,
    sa.similarity_score,
    sa.relationship_type,
    sa.shared_tags
  FROM scored_articles sa
  WHERE sa.similarity_score > 10 -- Minimum threshold
  ORDER BY sa.similarity_score DESC, sa.title ASC
  LIMIT p_limit;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION calculate_related_articles IS 'Finds related articles based on category, tags, and source similarity';


-- ============================================================================
-- FUNCTION: Refresh Related Articles for One Article
-- Recalculates and stores relationships for a single article
-- ============================================================================

CREATE OR REPLACE FUNCTION refresh_related_articles(p_article_id UUID)
RETURNS INTEGER AS $$
DECLARE
  v_inserted_count INTEGER;
BEGIN
  -- Delete existing relationships for this article
  DELETE FROM article_relationships WHERE article_id = p_article_id;

  -- Calculate and insert new relationships
  INSERT INTO article_relationships (
    article_id,
    related_article_id,
    similarity_score,
    relationship_type,
    relationship_details
  )
  SELECT
    p_article_id,
    r.related_article_id,
    r.similarity_score,
    r.relationship_type,
    jsonb_build_object(
      'shared_tags', r.shared_tags,
      'related_title', r.title,
      'related_category', r.category
    )
  FROM calculate_related_articles(p_article_id, 10) r;

  GET DIAGNOSTICS v_inserted_count = ROW_COUNT;

  RETURN v_inserted_count;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION refresh_related_articles IS 'Recalculate and store related articles for one article';


-- ============================================================================
-- FUNCTION: Refresh All Related Articles
-- Recalculates relationships for all active articles (run periodically)
-- ============================================================================

CREATE OR REPLACE FUNCTION refresh_all_related_articles()
RETURNS TABLE (
  article_id UUID,
  relationships_found INTEGER
) AS $$
BEGIN
  RETURN QUERY
  SELECT
    a.id,
    refresh_related_articles(a.id)
  FROM articles a
  WHERE a.is_active = true
  ORDER BY a.created_at DESC;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION refresh_all_related_articles IS 'Recalculate related articles for all active articles';


-- ============================================================================
-- VIEW: Article with Related Content
-- Convenient view showing articles with their related articles
-- ============================================================================

CREATE OR REPLACE VIEW articles_with_related AS
SELECT
  a.id,
  a.title,
  a.url,
  a.category,
  a.tags,
  a.overall_score,
  a.created_at,
  (
    SELECT jsonb_agg(
      jsonb_build_object(
        'id', ra.id,
        'title', ra.title,
        'url', ra.url,
        'category', ra.category,
        'similarity_score', ar.similarity_score,
        'relationship_type', ar.relationship_type
      )
      ORDER BY ar.similarity_score DESC
    )
    FROM article_relationships ar
    JOIN articles ra ON ra.id = ar.related_article_id
    WHERE ar.article_id = a.id
      AND ra.is_active = true
    LIMIT 5
  ) as related_articles
FROM articles a
WHERE a.is_active = true;

COMMENT ON VIEW articles_with_related IS 'Articles with their top 5 related articles embedded as JSON';


-- ============================================================================
-- TRIGGER: Auto-refresh related articles on new article
-- Automatically calculate relationships when a new article is added
-- ============================================================================

CREATE OR REPLACE FUNCTION trigger_calculate_related_on_insert()
RETURNS TRIGGER AS $$
BEGIN
  -- Calculate relationships for the new article
  PERFORM refresh_related_articles(NEW.id);

  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER after_article_insert_calculate_related
  AFTER INSERT ON articles
  FOR EACH ROW
  EXECUTE FUNCTION trigger_calculate_related_on_insert();

COMMENT ON TRIGGER after_article_insert_calculate_related ON articles IS 'Auto-calculate related articles when new article is added';


-- ============================================================================
-- NOTES
-- ============================================================================

-- To manually refresh related articles for all content:
-- SELECT * FROM refresh_all_related_articles();

-- To get related articles for a specific article:
-- SELECT * FROM calculate_related_articles('article-uuid-here', 5);

-- To view articles with their related content:
-- SELECT * FROM articles_with_related WHERE id = 'article-uuid-here';
