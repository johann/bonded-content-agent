-- Migration: Create Sources Table
-- Phase 3: Source Management
-- Run this in your Supabase SQL editor AFTER running 001 and 002

-- Create sources table
CREATE TABLE IF NOT EXISTS sources (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT NOT NULL,
  website_url TEXT NOT NULL,
  rss_url TEXT NOT NULL UNIQUE,
  description TEXT,

  -- Status
  is_active BOOLEAN DEFAULT true,
  discovered_by TEXT DEFAULT 'manual', -- 'manual', 'discovery_agent', 'suggestion'

  -- Fetching stats
  last_fetch_at TIMESTAMP WITH TIME ZONE,
  last_fetch_success BOOLEAN,
  total_fetches INTEGER DEFAULT 0,
  successful_fetches INTEGER DEFAULT 0,
  failed_fetches INTEGER DEFAULT 0,
  consecutive_failures INTEGER DEFAULT 0,

  -- Article stats
  articles_found INTEGER DEFAULT 0,
  articles_saved INTEGER DEFAULT 0,
  articles_rejected INTEGER DEFAULT 0,

  -- Quality metrics (calculated)
  acceptance_rate DECIMAL(5,2), -- Percentage of found articles that were saved
  avg_article_score DECIMAL(3,1), -- Average overall_score of articles from this source

  -- Metadata
  created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_sources_is_active ON sources(is_active);
CREATE INDEX IF NOT EXISTS idx_sources_acceptance_rate ON sources(acceptance_rate DESC);
CREATE INDEX IF NOT EXISTS idx_sources_avg_article_score ON sources(avg_article_score DESC);
CREATE INDEX IF NOT EXISTS idx_sources_last_fetch_at ON sources(last_fetch_at DESC);

-- Add check constraint for acceptance_rate (0-100)
ALTER TABLE sources
ADD CONSTRAINT acceptance_rate_range CHECK (acceptance_rate >= 0 AND acceptance_rate <= 100);

-- Add check constraint for avg_article_score (0-10)
ALTER TABLE sources
ADD CONSTRAINT avg_article_score_range CHECK (avg_article_score >= 0 AND avg_article_score <= 10);

-- Add comments
COMMENT ON TABLE sources IS 'Blog sources for content curation with quality tracking';
COMMENT ON COLUMN sources.name IS 'Human-readable name of the blog/source';
COMMENT ON COLUMN sources.website_url IS 'Main website URL';
COMMENT ON COLUMN sources.rss_url IS 'RSS feed URL (unique identifier)';
COMMENT ON COLUMN sources.is_active IS 'Whether to fetch from this source';
COMMENT ON COLUMN sources.discovered_by IS 'How this source was added: manual, discovery_agent, suggestion';
COMMENT ON COLUMN sources.consecutive_failures IS 'Number of consecutive failed fetches (used to auto-disable unreliable sources)';
COMMENT ON COLUMN sources.acceptance_rate IS 'Percentage of articles that passed quality filters (articles_saved / articles_found * 100)';
COMMENT ON COLUMN sources.avg_article_score IS 'Average overall_score of articles from this source';

-- Create updated_at trigger
CREATE OR REPLACE FUNCTION update_sources_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER sources_updated_at
  BEFORE UPDATE ON sources
  FOR EACH ROW
  EXECUTE FUNCTION update_sources_updated_at();

-- Add source_id to articles table to track which source each article came from
ALTER TABLE articles
ADD COLUMN IF NOT EXISTS source_id UUID REFERENCES sources(id);

-- Create index on articles.source_id
CREATE INDEX IF NOT EXISTS idx_articles_source_id ON articles(source_id);

-- Add comment
COMMENT ON COLUMN articles.source_id IS 'The source (blog) this article was curated from';
