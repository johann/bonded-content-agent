-- ============================================================================
-- FIX MISSING COLUMNS IN MIGRATIONS 004 AND 005
-- Run this after migrations 004 and 005 if tables were created without all columns
-- ============================================================================

-- ============================================================================
-- FIX MIGRATION 004: ENGAGEMENT TABLES
-- ============================================================================

-- Fix engagement_events table: add context column
ALTER TABLE engagement_events 
ADD COLUMN IF NOT EXISTS context JSONB;

COMMENT ON COLUMN engagement_events.context IS 'Additional event metadata as JSON';

-- Fix article_engagement table: add all missing calculated metric columns
ALTER TABLE article_engagement 
ADD COLUMN IF NOT EXISTS save_rate DECIMAL(5,2),
ADD COLUMN IF NOT EXISTS share_rate DECIMAL(5,2),
ADD COLUMN IF NOT EXISTS click_rate DECIMAL(5,2),
ADD COLUMN IF NOT EXISTS discussion_rate DECIMAL(5,2),
ADD COLUMN IF NOT EXISTS engagement_score DECIMAL(5,2),
ADD COLUMN IF NOT EXISTS first_view_at TIMESTAMP WITH TIME ZONE,
ADD COLUMN IF NOT EXISTS last_view_at TIMESTAMP WITH TIME ZONE;

-- Create missing indexes
CREATE INDEX IF NOT EXISTS idx_article_engagement_engagement_score 
ON article_engagement(engagement_score DESC);

CREATE INDEX IF NOT EXISTS idx_article_engagement_last_view_at 
ON article_engagement(last_view_at DESC);

-- Add missing check constraints (if they don't exist)
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'save_rate_range'
  ) THEN
    ALTER TABLE article_engagement
    ADD CONSTRAINT save_rate_range CHECK (save_rate >= 0 AND save_rate <= 100);
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'share_rate_range'
  ) THEN
    ALTER TABLE article_engagement
    ADD CONSTRAINT share_rate_range CHECK (share_rate >= 0 AND share_rate <= 100);
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'click_rate_range'
  ) THEN
    ALTER TABLE article_engagement
    ADD CONSTRAINT click_rate_range CHECK (click_rate >= 0 AND click_rate <= 100);
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'discussion_rate_range'
  ) THEN
    ALTER TABLE article_engagement
    ADD CONSTRAINT discussion_rate_range CHECK (discussion_rate >= 0 AND discussion_rate <= 100);
  END IF;
END $$;

-- Add missing column comments
COMMENT ON COLUMN article_engagement.save_rate IS 'Percentage of viewers who saved (bookmarked) the article';
COMMENT ON COLUMN article_engagement.share_rate IS 'Percentage of viewers who shared the article';
COMMENT ON COLUMN article_engagement.click_rate IS 'Percentage of viewers who clicked through to original article';
COMMENT ON COLUMN article_engagement.discussion_rate IS 'Percentage of viewers who started discussing with partner';
COMMENT ON COLUMN article_engagement.engagement_score IS 'Composite engagement score (higher = more engaging)';


-- ============================================================================
-- FIX MIGRATION 005: LEARNING TABLES
-- ============================================================================

-- Fix agent_learnings table: add missing key column and make it unique
-- The key column is used for upsert conflicts in the application code
ALTER TABLE agent_learnings 
ADD COLUMN IF NOT EXISTS key TEXT;

-- If key column was just added and has NULL values, set defaults
-- This handles the case where the table existed but key column was missing
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.columns 
    WHERE table_name = 'agent_learnings' AND column_name = 'key'
  ) THEN
    UPDATE agent_learnings 
    SET key = 'legacy_' || id::text 
    WHERE key IS NULL;
  END IF;
END $$;

-- Make key column NOT NULL (only if column exists)
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.columns 
    WHERE table_name = 'agent_learnings' AND column_name = 'key'
    AND is_nullable = 'YES'
  ) THEN
    ALTER TABLE agent_learnings 
    ALTER COLUMN key SET NOT NULL;
  END IF;
END $$;

-- Add unique constraint on key (required for upsert on_conflict="key")
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'agent_learnings_key_unique'
  ) THEN
    ALTER TABLE agent_learnings
    ADD CONSTRAINT agent_learnings_key_unique UNIQUE (key);
  END IF;
END $$;

-- Ensure all other columns exist
ALTER TABLE agent_learnings 
ADD COLUMN IF NOT EXISTS learning_type TEXT,
ADD COLUMN IF NOT EXISTS value JSONB,
ADD COLUMN IF NOT EXISTS confidence DECIMAL(3,2),
ADD COLUMN IF NOT EXISTS based_on_period_days INTEGER,
ADD COLUMN IF NOT EXISTS data_points INTEGER,
ADD COLUMN IF NOT EXISTS notes TEXT,
ADD COLUMN IF NOT EXISTS created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
ADD COLUMN IF NOT EXISTS expires_at TIMESTAMP WITH TIME ZONE;

-- Create missing indexes
CREATE INDEX IF NOT EXISTS idx_agent_learnings_type ON agent_learnings(learning_type);
CREATE INDEX IF NOT EXISTS idx_agent_learnings_key ON agent_learnings(key);
CREATE INDEX IF NOT EXISTS idx_agent_learnings_updated_at ON agent_learnings(updated_at DESC);

-- Add missing check constraints (if they don't exist)
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'learning_type_enum'
  ) THEN
    ALTER TABLE agent_learnings
    ADD CONSTRAINT learning_type_enum CHECK (
      learning_type IN (
        'source_performance',
        'category_performance',
        'topic_performance',
        'blurb_effectiveness',
        'content_pattern',
        'user_preference',
        'seasonal_trend'
      )
    );
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'confidence_range'
  ) THEN
    ALTER TABLE agent_learnings
    ADD CONSTRAINT confidence_range CHECK (confidence >= 0 AND confidence <= 1);
  END IF;
END $$;

-- Add missing column comments
COMMENT ON COLUMN agent_learnings.key IS 'Unique identifier for this learning (e.g., "top_sources")';
COMMENT ON COLUMN agent_learnings.value IS 'JSON data containing the actual learning/insight';
COMMENT ON COLUMN agent_learnings.confidence IS 'Confidence score 0-1 based on data quality and sample size';
COMMENT ON COLUMN agent_learnings.data_points IS 'Number of articles/events analyzed to derive this learning';

-- Ensure updated_at trigger exists
CREATE OR REPLACE FUNCTION update_agent_learnings_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS agent_learnings_updated_at ON agent_learnings;
CREATE TRIGGER agent_learnings_updated_at
  BEFORE UPDATE ON agent_learnings
  FOR EACH ROW
  EXECUTE FUNCTION update_agent_learnings_updated_at();

-- Fix agent_decisions table: ensure all columns exist
ALTER TABLE agent_decisions 
ADD COLUMN IF NOT EXISTS article_url TEXT,
ADD COLUMN IF NOT EXISTS article_title TEXT,
ADD COLUMN IF NOT EXISTS source_id UUID REFERENCES sources(id),
ADD COLUMN IF NOT EXISTS decision TEXT,
ADD COLUMN IF NOT EXISTS reasoning TEXT,
ADD COLUMN IF NOT EXISTS relevance_score DECIMAL(3,1),
ADD COLUMN IF NOT EXISTS actionability_score DECIMAL(3,1),
ADD COLUMN IF NOT EXISTS depth_score DECIMAL(3,1),
ADD COLUMN IF NOT EXISTS freshness_score DECIMAL(3,1),
ADD COLUMN IF NOT EXISTS overall_score DECIMAL(3,1),
ADD COLUMN IF NOT EXISTS predicted_engagement_score DECIMAL(5,2),
ADD COLUMN IF NOT EXISTS category TEXT,
ADD COLUMN IF NOT EXISTS tags TEXT[],
ADD COLUMN IF NOT EXISTS agent_run_id UUID,
ADD COLUMN IF NOT EXISTS created_at TIMESTAMP WITH TIME ZONE DEFAULT now();

-- Create missing indexes for agent_decisions
CREATE INDEX IF NOT EXISTS idx_agent_decisions_decision ON agent_decisions(decision);
CREATE INDEX IF NOT EXISTS idx_agent_decisions_source_id ON agent_decisions(source_id);
CREATE INDEX IF NOT EXISTS idx_agent_decisions_category ON agent_decisions(category);
CREATE INDEX IF NOT EXISTS idx_agent_decisions_created_at ON agent_decisions(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_agent_decisions_run_id ON agent_decisions(agent_run_id);

-- Add missing check constraint for decision
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'decision_enum'
  ) THEN
    ALTER TABLE agent_decisions
    ADD CONSTRAINT decision_enum CHECK (decision IN ('save', 'skip'));
  END IF;
END $$;

-- Add missing column comments for agent_decisions
COMMENT ON COLUMN agent_decisions.decision IS 'save (article saved to DB) or skip (rejected)';
COMMENT ON COLUMN agent_decisions.reasoning IS 'Agent explanation for why it saved/skipped this article';
COMMENT ON COLUMN agent_decisions.predicted_engagement_score IS 'Agent predicted engagement (optional - to validate learning)';
COMMENT ON COLUMN agent_decisions.agent_run_id IS 'UUID to group all decisions from a single agent run';

