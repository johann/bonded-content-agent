-- Migration: Create Learning and Decision Tracking Tables
-- Phase 6: Feedback Loop & Learning
-- Run this in your Supabase SQL editor AFTER running 001-004

-- ============================================================================
-- AGENT LEARNINGS TABLE
-- Stores insights and patterns learned from engagement data
-- ============================================================================

CREATE TABLE IF NOT EXISTS agent_learnings (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  learning_type TEXT NOT NULL,

  -- Learning content
  key TEXT NOT NULL, -- e.g., "top_sources", "best_categories", "effective_blurb_patterns"
  value JSONB NOT NULL, -- The actual learning data
  confidence DECIMAL(3,2), -- 0-1 confidence score

  -- Context
  based_on_period_days INTEGER, -- Analysis period (e.g., last 30 days)
  data_points INTEGER, -- Number of data points used

  -- Metadata
  notes TEXT,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
  expires_at TIMESTAMP WITH TIME ZONE -- Some learnings may expire
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_agent_learnings_type ON agent_learnings(learning_type);
CREATE INDEX IF NOT EXISTS idx_agent_learnings_key ON agent_learnings(key);
CREATE INDEX IF NOT EXISTS idx_agent_learnings_updated_at ON agent_learnings(updated_at DESC);

-- Add check constraint for learning_type
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

-- Add check constraint for confidence (0-1)
ALTER TABLE agent_learnings
ADD CONSTRAINT confidence_range CHECK (confidence >= 0 AND confidence <= 1);

-- Add comments
COMMENT ON TABLE agent_learnings IS 'Insights learned from engagement data to improve curation';
COMMENT ON COLUMN agent_learnings.learning_type IS 'Category of learning: source_performance, category_performance, topic_performance, etc.';
COMMENT ON COLUMN agent_learnings.key IS 'Unique identifier for this learning (e.g., "top_sources")';
COMMENT ON COLUMN agent_learnings.value IS 'JSON data containing the actual learning/insight';
COMMENT ON COLUMN agent_learnings.confidence IS 'Confidence score 0-1 based on data quality and sample size';
COMMENT ON COLUMN agent_learnings.data_points IS 'Number of articles/events analyzed to derive this learning';

-- Create updated_at trigger
CREATE OR REPLACE FUNCTION update_agent_learnings_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER agent_learnings_updated_at
  BEFORE UPDATE ON agent_learnings
  FOR EACH ROW
  EXECUTE FUNCTION update_agent_learnings_updated_at();


-- ============================================================================
-- AGENT DECISIONS TABLE
-- Logs every save/skip decision with reasoning for analysis
-- ============================================================================

CREATE TABLE IF NOT EXISTS agent_decisions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

  -- Article info
  article_url TEXT NOT NULL,
  article_title TEXT,
  source_id UUID REFERENCES sources(id),

  -- Decision
  decision TEXT NOT NULL, -- 'save' or 'skip'
  reasoning TEXT NOT NULL, -- Why the agent made this decision

  -- Scores (if evaluated)
  relevance_score DECIMAL(3,1),
  actionability_score DECIMAL(3,1),
  depth_score DECIMAL(3,1),
  freshness_score DECIMAL(3,1),
  overall_score DECIMAL(3,1),

  -- Predicted engagement (optional - for learning)
  predicted_engagement_score DECIMAL(5,2),

  -- Context
  category TEXT,
  tags TEXT[],

  -- Metadata
  agent_run_id UUID, -- Group decisions from same run
  created_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_agent_decisions_decision ON agent_decisions(decision);
CREATE INDEX IF NOT EXISTS idx_agent_decisions_source_id ON agent_decisions(source_id);
CREATE INDEX IF NOT EXISTS idx_agent_decisions_category ON agent_decisions(category);
CREATE INDEX IF NOT EXISTS idx_agent_decisions_created_at ON agent_decisions(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_agent_decisions_run_id ON agent_decisions(agent_run_id);

-- Add check constraint for decision
ALTER TABLE agent_decisions
ADD CONSTRAINT decision_enum CHECK (decision IN ('save', 'skip'));

-- Add comments
COMMENT ON TABLE agent_decisions IS 'Log of every article evaluation decision with reasoning';
COMMENT ON COLUMN agent_decisions.decision IS 'save (article saved to DB) or skip (rejected)';
COMMENT ON COLUMN agent_decisions.reasoning IS 'Agent explanation for why it saved/skipped this article';
COMMENT ON COLUMN agent_decisions.predicted_engagement_score IS 'Agent predicted engagement (optional - to validate learning)';
COMMENT ON COLUMN agent_decisions.agent_run_id IS 'UUID to group all decisions from a single agent run';


-- ============================================================================
-- LEARNING ANALYSIS VIEWS
-- Pre-computed views for common learning queries
-- ============================================================================

-- View: Source performance with engagement data
CREATE OR REPLACE VIEW source_performance_view AS
SELECT
  s.id,
  s.name,
  s.acceptance_rate,
  s.avg_article_score,
  s.articles_saved,
  COALESCE(AVG(ae.engagement_score), 0) as avg_engagement_score,
  COALESCE(SUM(ae.save_count), 0) as total_saves,
  COALESCE(SUM(ae.view_count), 0) as total_views
FROM sources s
LEFT JOIN articles a ON a.source_id = s.id
LEFT JOIN article_engagement ae ON ae.article_id = a.id
WHERE s.is_active = true
GROUP BY s.id, s.name, s.acceptance_rate, s.avg_article_score, s.articles_saved
ORDER BY avg_engagement_score DESC NULLS LAST;

COMMENT ON VIEW source_performance_view IS 'Source quality metrics combined with engagement data';

-- View: Category performance
CREATE OR REPLACE VIEW category_performance_view AS
SELECT
  a.category,
  COUNT(*) as article_count,
  AVG(a.overall_score) as avg_overall_score,
  COALESCE(AVG(ae.engagement_score), 0) as avg_engagement_score,
  COALESCE(AVG(ae.save_rate), 0) as avg_save_rate,
  COALESCE(AVG(ae.discussion_rate), 0) as avg_discussion_rate,
  COALESCE(SUM(ae.save_count), 0) as total_saves
FROM articles a
LEFT JOIN article_engagement ae ON ae.article_id = a.id
WHERE a.category IS NOT NULL
  AND a.created_at > now() - interval '90 days' -- Last 90 days
GROUP BY a.category
ORDER BY avg_engagement_score DESC NULLS LAST;

COMMENT ON VIEW category_performance_view IS 'Category performance metrics with engagement data';

-- View: Tag performance
CREATE OR REPLACE VIEW tag_performance_view AS
SELECT
  unnest(a.tags) as tag,
  COUNT(*) as article_count,
  AVG(a.overall_score) as avg_overall_score,
  COALESCE(AVG(ae.engagement_score), 0) as avg_engagement_score,
  COALESCE(AVG(ae.save_rate), 0) as avg_save_rate
FROM articles a
LEFT JOIN article_engagement ae ON ae.article_id = a.id
WHERE a.tags IS NOT NULL
  AND a.created_at > now() - interval '90 days'
GROUP BY tag
HAVING COUNT(*) >= 3 -- At least 3 articles with this tag
ORDER BY avg_engagement_score DESC NULLS LAST
LIMIT 50;

COMMENT ON VIEW tag_performance_view IS 'Tag/topic performance metrics with engagement data';


-- ============================================================================
-- HELPER FUNCTION: Calculate Confidence Score
-- Based on sample size and data quality
-- ============================================================================

CREATE OR REPLACE FUNCTION calculate_confidence(data_points INTEGER, period_days INTEGER)
RETURNS DECIMAL(3,2) AS $$
DECLARE
  v_confidence DECIMAL(3,2);
BEGIN
  -- More data points = higher confidence
  -- Longer period = more reliable
  -- Returns 0-1 confidence score

  IF data_points >= 50 AND period_days >= 30 THEN
    v_confidence := 0.95;
  ELSIF data_points >= 30 AND period_days >= 21 THEN
    v_confidence := 0.85;
  ELSIF data_points >= 20 AND period_days >= 14 THEN
    v_confidence := 0.75;
  ELSIF data_points >= 10 AND period_days >= 7 THEN
    v_confidence := 0.60;
  ELSIF data_points >= 5 THEN
    v_confidence := 0.40;
  ELSE
    v_confidence := 0.20;
  END IF;

  RETURN v_confidence;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION calculate_confidence IS 'Calculate confidence score (0-1) based on sample size and period';
