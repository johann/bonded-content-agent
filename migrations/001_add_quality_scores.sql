-- Migration: Add Quality Scores and Categorization to Articles Table
-- Phase 1: Content Quality & Categorization
-- Run this in your Supabase SQL editor

-- Add quality score columns
ALTER TABLE articles
ADD COLUMN IF NOT EXISTS relevance_score DECIMAL(3,1),
ADD COLUMN IF NOT EXISTS actionability_score DECIMAL(3,1),
ADD COLUMN IF NOT EXISTS depth_score DECIMAL(3,1),
ADD COLUMN IF NOT EXISTS freshness_score DECIMAL(3,1),
ADD COLUMN IF NOT EXISTS overall_score DECIMAL(3,1);

-- Add categorization columns
ALTER TABLE articles
ADD COLUMN IF NOT EXISTS category TEXT,
ADD COLUMN IF NOT EXISTS tags TEXT[],
ADD COLUMN IF NOT EXISTS reading_time_minutes INTEGER,
ADD COLUMN IF NOT EXISTS difficulty TEXT;

-- Add check constraints for scores (0-10 range)
ALTER TABLE articles
ADD CONSTRAINT relevance_score_range CHECK (relevance_score >= 0 AND relevance_score <= 10),
ADD CONSTRAINT actionability_score_range CHECK (actionability_score >= 0 AND actionability_score <= 10),
ADD CONSTRAINT depth_score_range CHECK (depth_score >= 0 AND depth_score <= 10),
ADD CONSTRAINT freshness_score_range CHECK (freshness_score >= 0 AND freshness_score <= 10),
ADD CONSTRAINT overall_score_range CHECK (overall_score >= 0 AND overall_score <= 10);

-- Add check constraint for category enum
ALTER TABLE articles
ADD CONSTRAINT category_enum CHECK (
  category IN ('communication', 'conflict', 'intimacy', 'trust', 'parenting', 'finances', 'growth', 'wellness')
);

-- Add check constraint for difficulty enum
ALTER TABLE articles
ADD CONSTRAINT difficulty_enum CHECK (
  difficulty IN ('beginner', 'intermediate', 'advanced')
);

-- Create index on category for filtering
CREATE INDEX IF NOT EXISTS idx_articles_category ON articles(category);

-- Create index on overall_score for sorting
CREATE INDEX IF NOT EXISTS idx_articles_overall_score ON articles(overall_score DESC);

-- Create GIN index on tags for array searching
CREATE INDEX IF NOT EXISTS idx_articles_tags ON articles USING GIN(tags);

-- Add comment to table
COMMENT ON COLUMN articles.relevance_score IS 'How relevant is this to Bonded audience (committed couples) - 0-10';
COMMENT ON COLUMN articles.actionability_score IS 'How actionable is the advice (concrete steps vs abstract) - 0-10';
COMMENT ON COLUMN articles.depth_score IS 'Depth of content (superficial vs evidence-based) - 0-10';
COMMENT ON COLUMN articles.freshness_score IS 'Novelty and timeliness (evergreen=5-7, trending=8-10) - 0-10';
COMMENT ON COLUMN articles.overall_score IS 'Average of the 4 quality scores - automatically calculated';
COMMENT ON COLUMN articles.category IS 'Primary category: communication, conflict, intimacy, trust, parenting, finances, growth, wellness';
COMMENT ON COLUMN articles.tags IS 'Array of 3-5 specific tags describing the article';
COMMENT ON COLUMN articles.reading_time_minutes IS 'Estimated reading time in minutes';
COMMENT ON COLUMN articles.difficulty IS 'Difficulty level: beginner, intermediate, advanced';
