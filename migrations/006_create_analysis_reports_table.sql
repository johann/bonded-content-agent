-- Migration: Create Content Analysis Reports Table
-- Phase 7: Trend & Gap Analysis
-- Run this in your Supabase SQL editor AFTER running 001-005

-- ============================================================================
-- CONTENT ANALYSIS REPORTS TABLE
-- Stores weekly analysis reports with trends, gaps, and recommendations
-- ============================================================================

CREATE TABLE IF NOT EXISTS content_analysis_reports (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

  -- Report metadata
  report_type TEXT NOT NULL DEFAULT 'weekly',
  period_start TIMESTAMP WITH TIME ZONE NOT NULL,
  period_end TIMESTAMP WITH TIME ZONE NOT NULL,

  -- Analysis results
  trending_topics JSONB, -- Topics with increasing engagement
  top_articles JSONB, -- Best performing articles this period
  top_sources JSONB, -- Best performing sources
  content_gaps JSONB, -- Identified gaps and opportunities
  recommendations JSONB, -- Actionable recommendations

  -- Statistics
  total_articles_published INTEGER,
  total_articles_viewed INTEGER,
  total_engagement_score DECIMAL(10,2),
  avg_save_rate DECIMAL(5,2),

  -- Quality metrics
  avg_overall_score DECIMAL(3,1), -- Average article quality
  category_distribution JSONB, -- Article count by category

  -- Executive summary
  summary TEXT, -- AI-generated summary of key findings

  -- Metadata
  created_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_content_analysis_reports_period_end ON content_analysis_reports(period_end DESC);
CREATE INDEX IF NOT EXISTS idx_content_analysis_reports_report_type ON content_analysis_reports(report_type);
CREATE INDEX IF NOT EXISTS idx_content_analysis_reports_created_at ON content_analysis_reports(created_at DESC);

-- Add check constraint for report_type
ALTER TABLE content_analysis_reports
ADD CONSTRAINT report_type_enum CHECK (
  report_type IN ('weekly', 'monthly', 'quarterly', 'custom')
);

-- Add comments
COMMENT ON TABLE content_analysis_reports IS 'Weekly/periodic analysis reports with trends, gaps, and recommendations';
COMMENT ON COLUMN content_analysis_reports.trending_topics IS 'Topics showing increased engagement or volume';
COMMENT ON COLUMN content_analysis_reports.top_articles IS 'Best performing articles in this period';
COMMENT ON COLUMN content_analysis_reports.top_sources IS 'Sources producing highest engagement';
COMMENT ON COLUMN content_analysis_reports.content_gaps IS 'Identified content gaps and opportunities';
COMMENT ON COLUMN content_analysis_reports.recommendations IS 'Actionable recommendations for next period';
COMMENT ON COLUMN content_analysis_reports.summary IS 'AI-generated executive summary of findings';


-- ============================================================================
-- HELPER VIEWS FOR TREND ANALYSIS
-- ============================================================================

-- View: Recent article performance (last 7 days)
CREATE OR REPLACE VIEW recent_article_performance AS
SELECT
  a.id,
  a.title,
  a.url,
  a.category,
  a.tags,
  a.overall_score,
  a.created_at,
  s.name as source_name,
  COALESCE(ae.engagement_score, 0) as engagement_score,
  COALESCE(ae.view_count, 0) as view_count,
  COALESCE(ae.save_count, 0) as save_count,
  COALESCE(ae.save_rate, 0) as save_rate
FROM articles a
LEFT JOIN sources s ON s.id = a.source_id
LEFT JOIN article_engagement ae ON ae.article_id = a.id
WHERE a.created_at >= now() - interval '7 days'
ORDER BY a.created_at DESC;

COMMENT ON VIEW recent_article_performance IS 'Articles published in last 7 days with engagement metrics';

-- View: Tag trending analysis
CREATE OR REPLACE VIEW tag_trending_analysis AS
WITH recent_tags AS (
  SELECT
    unnest(tags) as tag,
    COUNT(*) as recent_count,
    AVG(overall_score) as recent_avg_score
  FROM articles
  WHERE created_at >= now() - interval '7 days'
    AND tags IS NOT NULL
  GROUP BY tag
),
historical_tags AS (
  SELECT
    unnest(tags) as tag,
    COUNT(*) as historical_count,
    AVG(overall_score) as historical_avg_score
  FROM articles
  WHERE created_at >= now() - interval '30 days'
    AND created_at < now() - interval '7 days'
    AND tags IS NOT NULL
  GROUP BY tag
)
SELECT
  COALESCE(r.tag, h.tag) as tag,
  COALESCE(r.recent_count, 0) as recent_count,
  COALESCE(h.historical_count, 0) as historical_count,
  COALESCE(r.recent_avg_score, 0) as recent_avg_score,
  COALESCE(h.historical_avg_score, 0) as historical_avg_score,
  -- Trending score: (recent_count - historical_count) / historical_count
  CASE
    WHEN h.historical_count > 0 THEN
      ((r.recent_count::DECIMAL - h.historical_count::DECIMAL) / h.historical_count::DECIMAL) * 100
    ELSE 100 -- New tags are 100% trending
  END as trending_percentage
FROM recent_tags r
FULL OUTER JOIN historical_tags h ON r.tag = h.tag
WHERE COALESCE(r.recent_count, 0) >= 2 -- At least 2 recent articles
ORDER BY trending_percentage DESC NULLS LAST
LIMIT 20;

COMMENT ON VIEW tag_trending_analysis IS 'Tags sorted by trending percentage (recent vs historical volume)';


-- ============================================================================
-- HELPER FUNCTION: Identify Content Gaps
-- Analyzes what users want but we haven't covered
-- ============================================================================

CREATE OR REPLACE FUNCTION identify_content_gaps()
RETURNS TABLE (
  gap_type TEXT,
  gap_description TEXT,
  evidence JSONB,
  priority TEXT
) AS $$
BEGIN
  -- Gap 1: Categories with high engagement but low volume
  RETURN QUERY
  SELECT
    'low_volume_high_engagement' as gap_type,
    'Category "' || category || '" has high engagement but few articles' as gap_description,
    jsonb_build_object(
      'category', category,
      'article_count', article_count,
      'avg_engagement', avg_engagement_score
    ) as evidence,
    CASE
      WHEN avg_engagement_score > 40 AND article_count < 10 THEN 'high'
      WHEN avg_engagement_score > 30 AND article_count < 15 THEN 'medium'
      ELSE 'low'
    END as priority
  FROM (
    SELECT
      a.category,
      COUNT(*) as article_count,
      AVG(ae.engagement_score) as avg_engagement_score
    FROM articles a
    LEFT JOIN article_engagement ae ON ae.article_id = a.id
    WHERE a.created_at >= now() - interval '30 days'
      AND a.category IS NOT NULL
    GROUP BY a.category
    HAVING AVG(ae.engagement_score) > 25 AND COUNT(*) < 20
  ) gaps;

  -- Gap 2: Popular tags without recent coverage
  RETURN QUERY
  SELECT
    'stale_popular_topic' as gap_type,
    'Popular topic "' || tag || '" has no recent articles' as gap_description,
    jsonb_build_object(
      'tag', tag,
      'historical_count', historical_count,
      'days_since_last', days_since_last,
      'avg_engagement', avg_engagement
    ) as evidence,
    CASE
      WHEN avg_engagement > 30 AND days_since_last > 14 THEN 'high'
      WHEN avg_engagement > 20 AND days_since_last > 21 THEN 'medium'
      ELSE 'low'
    END as priority
  FROM (
    SELECT
      unnest(a.tags) as tag,
      COUNT(*) as historical_count,
      AVG(ae.engagement_score) as avg_engagement,
      EXTRACT(DAY FROM (now() - MAX(a.created_at))) as days_since_last
    FROM articles a
    LEFT JOIN article_engagement ae ON ae.article_id = a.id
    WHERE a.created_at >= now() - interval '90 days'
      AND a.tags IS NOT NULL
    GROUP BY tag
    HAVING
      COUNT(*) >= 3 -- Was popular (3+ articles)
      AND EXTRACT(DAY FROM (now() - MAX(created_at))) > 14 -- No recent articles
      AND AVG(ae.engagement_score) > 20 -- Had good engagement
  ) stale_topics;

END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION identify_content_gaps IS 'Identifies content opportunities based on engagement patterns';
