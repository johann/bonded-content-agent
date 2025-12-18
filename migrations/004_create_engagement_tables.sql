-- Migration: Create Engagement Tracking Tables
-- Phase 5: Engagement Tracking Integration
-- Run this in your Supabase SQL editor AFTER running 001, 002, and 003

-- ============================================================================
-- ENGAGEMENT EVENTS TABLE
-- Raw event tracking from the Bonded app
-- ============================================================================

CREATE TABLE IF NOT EXISTS engagement_events (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  article_id UUID NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
  user_id UUID, -- Optional: can track per-user or anonymously
  event_type TEXT NOT NULL,

  -- Event metadata
  session_id UUID, -- Group events from same session
  context JSONB, -- Additional context (e.g., scroll depth, time on page)

  -- Timestamps
  created_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);

-- Create indexes for querying
CREATE INDEX IF NOT EXISTS idx_engagement_events_article_id ON engagement_events(article_id);
CREATE INDEX IF NOT EXISTS idx_engagement_events_event_type ON engagement_events(event_type);
CREATE INDEX IF NOT EXISTS idx_engagement_events_created_at ON engagement_events(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_engagement_events_user_id ON engagement_events(user_id) WHERE user_id IS NOT NULL;

-- Add check constraint for event_type
ALTER TABLE engagement_events
ADD CONSTRAINT event_type_enum CHECK (
  event_type IN ('view', 'save', 'share', 'click_through', 'unsave', 'discussion_start')
);

-- Add comments
COMMENT ON TABLE engagement_events IS 'Raw engagement events from Bonded app';
COMMENT ON COLUMN engagement_events.event_type IS 'Type: view, save, share, click_through, unsave, discussion_start';
COMMENT ON COLUMN engagement_events.context IS 'Additional event metadata as JSON';


-- ============================================================================
-- ARTICLE ENGAGEMENT TABLE
-- Aggregated engagement metrics per article
-- Refreshed periodically (e.g., hourly or daily)
-- ============================================================================

CREATE TABLE IF NOT EXISTS article_engagement (
  article_id UUID PRIMARY KEY REFERENCES articles(id) ON DELETE CASCADE,

  -- Engagement counts
  view_count INTEGER DEFAULT 0,
  save_count INTEGER DEFAULT 0,
  share_count INTEGER DEFAULT 0,
  click_through_count INTEGER DEFAULT 0,
  discussion_start_count INTEGER DEFAULT 0,

  -- Calculated metrics
  save_rate DECIMAL(5,2), -- (saves / views) * 100
  share_rate DECIMAL(5,2), -- (shares / views) * 100
  click_rate DECIMAL(5,2), -- (clicks / views) * 100
  discussion_rate DECIMAL(5,2), -- (discussion_starts / views) * 100

  -- Engagement score (composite metric)
  engagement_score DECIMAL(5,2), -- Weighted score based on all metrics

  -- Time-based metrics
  first_view_at TIMESTAMP WITH TIME ZONE,
  last_view_at TIMESTAMP WITH TIME ZONE,

  -- Update tracking
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_article_engagement_save_count ON article_engagement(save_count DESC);
CREATE INDEX IF NOT EXISTS idx_article_engagement_engagement_score ON article_engagement(engagement_score DESC);
CREATE INDEX IF NOT EXISTS idx_article_engagement_last_view_at ON article_engagement(last_view_at DESC);

-- Add check constraints for rates (0-100)
ALTER TABLE article_engagement
ADD CONSTRAINT save_rate_range CHECK (save_rate >= 0 AND save_rate <= 100),
ADD CONSTRAINT share_rate_range CHECK (share_rate >= 0 AND share_rate <= 100),
ADD CONSTRAINT click_rate_range CHECK (click_rate >= 0 AND click_rate <= 100),
ADD CONSTRAINT discussion_rate_range CHECK (discussion_rate >= 0 AND discussion_rate <= 100);

-- Add comments
COMMENT ON TABLE article_engagement IS 'Aggregated engagement metrics per article';
COMMENT ON COLUMN article_engagement.save_rate IS 'Percentage of viewers who saved (bookmarked) the article';
COMMENT ON COLUMN article_engagement.share_rate IS 'Percentage of viewers who shared the article';
COMMENT ON COLUMN article_engagement.click_rate IS 'Percentage of viewers who clicked through to original article';
COMMENT ON COLUMN article_engagement.discussion_rate IS 'Percentage of viewers who started discussing with partner';
COMMENT ON COLUMN article_engagement.engagement_score IS 'Composite engagement score (higher = more engaging)';


-- ============================================================================
-- HELPER FUNCTION TO REFRESH ARTICLE ENGAGEMENT
-- Call this periodically to update aggregated metrics
-- ============================================================================

CREATE OR REPLACE FUNCTION refresh_article_engagement(p_article_id UUID)
RETURNS VOID AS $$
DECLARE
  v_view_count INTEGER;
  v_save_count INTEGER;
  v_share_count INTEGER;
  v_click_count INTEGER;
  v_discussion_count INTEGER;
  v_save_rate DECIMAL(5,2);
  v_share_rate DECIMAL(5,2);
  v_click_rate DECIMAL(5,2);
  v_discussion_rate DECIMAL(5,2);
  v_engagement_score DECIMAL(5,2);
  v_first_view TIMESTAMP WITH TIME ZONE;
  v_last_view TIMESTAMP WITH TIME ZONE;
BEGIN
  -- Count events by type
  SELECT
    COUNT(*) FILTER (WHERE event_type = 'view'),
    COUNT(*) FILTER (WHERE event_type = 'save'),
    COUNT(*) FILTER (WHERE event_type = 'share'),
    COUNT(*) FILTER (WHERE event_type = 'click_through'),
    COUNT(*) FILTER (WHERE event_type = 'discussion_start'),
    MIN(created_at) FILTER (WHERE event_type = 'view'),
    MAX(created_at) FILTER (WHERE event_type = 'view')
  INTO
    v_view_count,
    v_save_count,
    v_share_count,
    v_click_count,
    v_discussion_count,
    v_first_view,
    v_last_view
  FROM engagement_events
  WHERE article_id = p_article_id;

  -- Calculate rates (avoid division by zero)
  IF v_view_count > 0 THEN
    v_save_rate := (v_save_count::DECIMAL / v_view_count) * 100;
    v_share_rate := (v_share_count::DECIMAL / v_view_count) * 100;
    v_click_rate := (v_click_count::DECIMAL / v_view_count) * 100;
    v_discussion_rate := (v_discussion_count::DECIMAL / v_view_count) * 100;

    -- Calculate engagement score (weighted)
    -- Save: 3x, Share: 2x, Click: 1.5x, Discussion: 4x (most valuable)
    v_engagement_score := (
      (v_save_rate * 3) +
      (v_share_rate * 2) +
      (v_click_rate * 1.5) +
      (v_discussion_rate * 4)
    ) / 10.5; -- Normalize to 0-100 scale
  ELSE
    v_save_rate := 0;
    v_share_rate := 0;
    v_click_rate := 0;
    v_discussion_rate := 0;
    v_engagement_score := 0;
  END IF;

  -- Upsert into article_engagement
  INSERT INTO article_engagement (
    article_id,
    view_count,
    save_count,
    share_count,
    click_through_count,
    discussion_start_count,
    save_rate,
    share_rate,
    click_rate,
    discussion_rate,
    engagement_score,
    first_view_at,
    last_view_at
  ) VALUES (
    p_article_id,
    v_view_count,
    v_save_count,
    v_share_count,
    v_click_count,
    v_discussion_count,
    v_save_rate,
    v_share_rate,
    v_click_rate,
    v_discussion_rate,
    v_engagement_score,
    v_first_view,
    v_last_view
  )
  ON CONFLICT (article_id) DO UPDATE SET
    view_count = EXCLUDED.view_count,
    save_count = EXCLUDED.save_count,
    share_count = EXCLUDED.share_count,
    click_through_count = EXCLUDED.click_through_count,
    discussion_start_count = EXCLUDED.discussion_start_count,
    save_rate = EXCLUDED.save_rate,
    share_rate = EXCLUDED.share_rate,
    click_rate = EXCLUDED.click_rate,
    discussion_rate = EXCLUDED.discussion_rate,
    engagement_score = EXCLUDED.engagement_score,
    first_view_at = EXCLUDED.first_view_at,
    last_view_at = EXCLUDED.last_view_at,
    updated_at = now();
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION refresh_article_engagement IS 'Recalculate engagement metrics for a specific article from raw events';


-- ============================================================================
-- FUNCTION TO REFRESH ALL ARTICLE ENGAGEMENT
-- Run this periodically (e.g., via cron) to keep metrics up to date
-- ============================================================================

CREATE OR REPLACE FUNCTION refresh_all_article_engagement()
RETURNS INTEGER AS $$
DECLARE
  v_count INTEGER := 0;
  v_article RECORD;
BEGIN
  FOR v_article IN
    SELECT DISTINCT article_id
    FROM engagement_events
  LOOP
    PERFORM refresh_article_engagement(v_article.article_id);
    v_count := v_count + 1;
  END LOOP;

  RETURN v_count;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION refresh_all_article_engagement IS 'Refresh engagement metrics for all articles that have events';
