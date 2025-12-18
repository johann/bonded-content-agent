-- Migration: Add Content Transformations to Articles Table
-- Phase 2: Content Transformation
-- Run this in your Supabase SQL editor AFTER running 001_add_quality_scores.sql

-- Add content transformation columns
ALTER TABLE articles
ADD COLUMN IF NOT EXISTS summary_short TEXT,
ADD COLUMN IF NOT EXISTS summary_detailed TEXT,
ADD COLUMN IF NOT EXISTS key_takeaways TEXT[],
ADD COLUMN IF NOT EXISTS discussion_questions TEXT[];

-- Add check constraint for short summary length (280 chars max)
ALTER TABLE articles
ADD CONSTRAINT summary_short_length CHECK (char_length(summary_short) <= 280);

-- Add check constraint for key takeaways array (3-5 items)
ALTER TABLE articles
ADD CONSTRAINT key_takeaways_count CHECK (
  array_length(key_takeaways, 1) IS NULL OR
  (array_length(key_takeaways, 1) >= 3 AND array_length(key_takeaways, 1) <= 5)
);

-- Add check constraint for discussion questions array (2-3 items)
ALTER TABLE articles
ADD CONSTRAINT discussion_questions_count CHECK (
  array_length(discussion_questions, 1) IS NULL OR
  (array_length(discussion_questions, 1) >= 2 AND array_length(discussion_questions, 1) <= 3)
);

-- Create GIN indexes for array searching
CREATE INDEX IF NOT EXISTS idx_articles_key_takeaways ON articles USING GIN(key_takeaways);
CREATE INDEX IF NOT EXISTS idx_articles_discussion_questions ON articles USING GIN(discussion_questions);

-- Add comments to columns
COMMENT ON COLUMN articles.summary_short IS 'Tweet-style summary (max 280 chars) - shareable, highlights main benefit';
COMMENT ON COLUMN articles.summary_detailed IS 'Detailed 2-3 paragraph summary (150-250 words) explaining key points and reasoning';
COMMENT ON COLUMN articles.key_takeaways IS 'Array of 3-5 specific, actionable bullet points couples can implement';
COMMENT ON COLUMN articles.discussion_questions IS 'Array of 2-3 open-ended questions for couples to discuss together';
