-- Migration: Create Auto-Generated Collections
-- Phase 9: Auto-Generated Collections
-- Run this in your Supabase SQL editor AFTER running 001-007

-- ============================================================================
-- COLLECTIONS TABLE
-- Stores curated collections of articles grouped by theme/topic
-- ============================================================================

CREATE TABLE IF NOT EXISTS collections (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

  -- Collection metadata
  title TEXT NOT NULL,
  description TEXT NOT NULL,
  slug TEXT NOT NULL UNIQUE,

  -- Collection type
  collection_type TEXT NOT NULL CHECK (
    collection_type IN (
      'category_based',      -- All articles in a category
      'tag_based',           -- Articles with specific tag(s)
      'curated_theme',       -- Hand-picked theme
      'trending_topic',      -- Based on trending analysis
      'high_engagement',     -- Top performing articles
      'related_cluster',     -- Related articles cluster
      'beginner_friendly',   -- Beginner difficulty articles
      'deep_dive'            -- Advanced/in-depth articles
    )
  ),

  -- Generation details
  generation_method TEXT NOT NULL DEFAULT 'auto' CHECK (
    generation_method IN ('auto', 'manual', 'hybrid')
  ),

  -- Criteria used to generate this collection
  generation_criteria JSONB,

  -- Display metadata
  cover_image_url TEXT,
  icon TEXT,  -- Emoji or icon identifier
  color_theme TEXT,  -- Hex color for UI theming

  -- Stats
  article_count INTEGER DEFAULT 0,
  avg_engagement_score DECIMAL(5,2),
  total_views INTEGER DEFAULT 0,
  total_saves INTEGER DEFAULT 0,

  -- Status
  is_active BOOLEAN DEFAULT true,
  is_featured BOOLEAN DEFAULT false,
  display_order INTEGER DEFAULT 0,

  -- Metadata
  created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
  last_generated_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);

-- Ensure all columns exist (in case table was created without them)
ALTER TABLE collections
ADD COLUMN IF NOT EXISTS collection_type TEXT,
ADD COLUMN IF NOT EXISTS generation_method TEXT DEFAULT 'auto',
ADD COLUMN IF NOT EXISTS generation_criteria JSONB,
ADD COLUMN IF NOT EXISTS cover_image_url TEXT,
ADD COLUMN IF NOT EXISTS icon TEXT,
ADD COLUMN IF NOT EXISTS color_theme TEXT,
ADD COLUMN IF NOT EXISTS article_count INTEGER DEFAULT 0,
ADD COLUMN IF NOT EXISTS avg_engagement_score DECIMAL(5,2),
ADD COLUMN IF NOT EXISTS total_views INTEGER DEFAULT 0,
ADD COLUMN IF NOT EXISTS total_saves INTEGER DEFAULT 0,
ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT true,
ADD COLUMN IF NOT EXISTS is_featured BOOLEAN DEFAULT false,
ADD COLUMN IF NOT EXISTS display_order INTEGER DEFAULT 0,
ADD COLUMN IF NOT EXISTS last_generated_at TIMESTAMP WITH TIME ZONE DEFAULT now();

-- Add CHECK constraints if they don't exist (for columns that might have been added above)
DO $$
BEGIN
  -- Add collection_type constraint if it doesn't exist
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'collections_collection_type_check'
  ) THEN
    ALTER TABLE collections
    ADD CONSTRAINT collections_collection_type_check CHECK (
      collection_type IN (
        'category_based', 'tag_based', 'curated_theme', 'trending_topic',
        'high_engagement', 'related_cluster', 'beginner_friendly', 'deep_dive'
      )
    );
  END IF;

  -- Add generation_method constraint if it doesn't exist
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'collections_generation_method_check'
  ) THEN
    ALTER TABLE collections
    ADD CONSTRAINT collections_generation_method_check CHECK (
      generation_method IN ('auto', 'manual', 'hybrid')
    );
  END IF;
END $$;

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_collections_collection_type ON collections(collection_type);
CREATE INDEX IF NOT EXISTS idx_collections_is_active ON collections(is_active);
CREATE INDEX IF NOT EXISTS idx_collections_is_featured ON collections(is_featured);
CREATE INDEX IF NOT EXISTS idx_collections_display_order ON collections(display_order);
CREATE INDEX IF NOT EXISTS idx_collections_slug ON collections(slug);
CREATE INDEX IF NOT EXISTS idx_collections_avg_engagement_score ON collections(avg_engagement_score DESC);

-- Add comments
COMMENT ON TABLE collections IS 'Curated collections of articles grouped by theme, topic, or criteria';
COMMENT ON COLUMN collections.collection_type IS 'Type of collection: category_based, tag_based, trending_topic, etc.';
COMMENT ON COLUMN collections.generation_method IS 'How collection was created: auto, manual, hybrid';
COMMENT ON COLUMN collections.generation_criteria IS 'Criteria used to generate (e.g., tags, category, score thresholds)';


-- ============================================================================
-- COLLECTION ARTICLES TABLE (Junction table)
-- Links articles to collections with ordering
-- ============================================================================

CREATE TABLE IF NOT EXISTS collection_articles (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

  collection_id UUID NOT NULL REFERENCES collections(id) ON DELETE CASCADE,
  article_id UUID NOT NULL REFERENCES articles(id) ON DELETE CASCADE,

  -- Display order within collection
  display_order INTEGER NOT NULL DEFAULT 0,

  -- Why this article is in this collection
  inclusion_reason TEXT,

  -- When added
  added_at TIMESTAMP WITH TIME ZONE DEFAULT now(),

  -- Prevent duplicates
  UNIQUE(collection_id, article_id)
);

-- Ensure all columns exist (in case table was created without them)
ALTER TABLE collection_articles
ADD COLUMN IF NOT EXISTS display_order INTEGER NOT NULL DEFAULT 0,
ADD COLUMN IF NOT EXISTS inclusion_reason TEXT,
ADD COLUMN IF NOT EXISTS added_at TIMESTAMP WITH TIME ZONE DEFAULT now();

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_collection_articles_collection_id ON collection_articles(collection_id);
CREATE INDEX IF NOT EXISTS idx_collection_articles_article_id ON collection_articles(article_id);
CREATE INDEX IF NOT EXISTS idx_collection_articles_display_order ON collection_articles(display_order);

-- Add comments
COMMENT ON TABLE collection_articles IS 'Junction table linking articles to collections';
COMMENT ON COLUMN collection_articles.display_order IS 'Order of article within the collection';
COMMENT ON COLUMN collection_articles.inclusion_reason IS 'Why this article was included';


-- ============================================================================
-- TRIGGER: Update collection updated_at timestamp
-- ============================================================================

CREATE OR REPLACE FUNCTION update_collection_timestamp()
RETURNS TRIGGER AS $$
BEGIN
  UPDATE collections
  SET updated_at = now()
  WHERE id = NEW.collection_id;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER after_collection_article_insert
  AFTER INSERT ON collection_articles
  FOR EACH ROW
  EXECUTE FUNCTION update_collection_timestamp();

CREATE TRIGGER after_collection_article_delete
  AFTER DELETE ON collection_articles
  FOR EACH ROW
  EXECUTE FUNCTION update_collection_timestamp();

COMMENT ON TRIGGER after_collection_article_insert ON collection_articles IS 'Update collection timestamp when articles are added';
COMMENT ON TRIGGER after_collection_article_delete ON collection_articles IS 'Update collection timestamp when articles are removed';


-- ============================================================================
-- FUNCTION: Refresh Collection Stats
-- Recalculate stats for a collection (article count, engagement, views)
-- ============================================================================

CREATE OR REPLACE FUNCTION refresh_collection_stats(p_collection_id UUID)
RETURNS VOID AS $$
DECLARE
  v_article_count INTEGER;
  v_avg_engagement DECIMAL(5,2);
  v_total_views INTEGER;
  v_total_saves INTEGER;
BEGIN
  -- Count articles
  SELECT COUNT(*)
  INTO v_article_count
  FROM collection_articles
  WHERE collection_id = p_collection_id;

  -- Calculate average engagement and totals
  SELECT
    COALESCE(AVG(ae.engagement_score), 0)::DECIMAL(5,2),
    COALESCE(SUM(ae.view_count), 0)::INTEGER,
    COALESCE(SUM(ae.save_count), 0)::INTEGER
  INTO v_avg_engagement, v_total_views, v_total_saves
  FROM collection_articles ca
  JOIN articles a ON a.id = ca.article_id
  LEFT JOIN article_engagement ae ON ae.article_id = a.id
  WHERE ca.collection_id = p_collection_id;

  -- Update collection
  UPDATE collections
  SET
    article_count = v_article_count,
    avg_engagement_score = v_avg_engagement,
    total_views = v_total_views,
    total_saves = v_total_saves,
    updated_at = now()
  WHERE id = p_collection_id;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION refresh_collection_stats IS 'Recalculate statistics for a collection';


-- ============================================================================
-- VIEW: Collections with Articles
-- Convenient view showing collections with their articles
-- ============================================================================

CREATE OR REPLACE VIEW collections_with_articles AS
SELECT
  c.id,
  c.title,
  c.description,
  c.slug,
  c.collection_type,
  c.generation_method,
  c.cover_image_url,
  c.icon,
  c.color_theme,
  c.article_count,
  c.avg_engagement_score,
  c.total_views,
  c.total_saves,
  c.is_active,
  c.is_featured,
  c.display_order,
  c.created_at,
  c.updated_at,
  (
    SELECT jsonb_agg(
      jsonb_build_object(
        'id', a.id,
        'title', a.title,
        'url', a.url,
        'blurb', a.blurb,
        'image_url', a.image_url,
        'category', a.category,
        'tags', a.tags,
        'overall_score', a.overall_score,
        'reading_time_minutes', a.reading_time_minutes,
        'difficulty', a.difficulty,
        'display_order', ca.display_order
      )
      ORDER BY ca.display_order ASC
    )
    FROM collection_articles ca
    JOIN articles a ON a.id = ca.article_id
    WHERE ca.collection_id = c.id
      AND a.is_active = true
  ) as articles
FROM collections c
WHERE c.is_active = true;

COMMENT ON VIEW collections_with_articles IS 'Collections with their articles embedded as JSON';


-- ============================================================================
-- FUNCTION: Generate Category-Based Collection
-- Creates a collection for a specific category
-- ============================================================================

CREATE OR REPLACE FUNCTION generate_category_collection(
  p_category TEXT,
  p_limit INTEGER DEFAULT 10
)
RETURNS UUID AS $$
DECLARE
  v_collection_id UUID;
  v_title TEXT;
  v_description TEXT;
  v_slug TEXT;
  v_icon TEXT;
  v_color TEXT;
BEGIN
  -- Generate collection metadata based on category
  v_slug := 'category-' || p_category;

  CASE p_category
    WHEN 'communication' THEN
      v_title := 'Communication Essentials';
      v_description := 'Master the art of expressing needs, active listening, and having difficult conversations with your partner.';
      v_icon := '💬';
      v_color := '#4A90E2';
    WHEN 'conflict' THEN
      v_title := 'Conflict Resolution';
      v_description := 'Learn to fight fair, resolve disagreements, and turn conflicts into opportunities for growth.';
      v_icon := '🤝';
      v_color := '#E24A4A';
    WHEN 'intimacy' THEN
      v_title := 'Building Intimacy';
      v_description := 'Deepen physical and emotional closeness, vulnerability, and connection with your partner.';
      v_icon := '❤️';
      v_color := '#E24A90';
    WHEN 'trust' THEN
      v_title := 'Trust & Security';
      v_description := 'Build and rebuild trust, create transparency, and establish emotional security in your relationship.';
      v_icon := '🔒';
      v_color := '#50C878';
    WHEN 'parenting' THEN
      v_title := 'Parenting Together';
      v_description := 'Navigate co-parenting, balance couple time with parenting, and strengthen your partnership.';
      v_icon := '👨‍👩‍👧‍👦';
      v_color := '#FFB347';
    WHEN 'finances' THEN
      v_title := 'Money & Finance';
      v_description := 'Have productive money conversations, plan finances together, and align on financial goals.';
      v_icon := '💰';
      v_color := '#50C878';
    WHEN 'growth' THEN
      v_title := 'Growing Together';
      v_description := 'Focus on personal development, shared goals, and growing as individuals and as a couple.';
      v_icon := '🌱';
      v_color := '#8FBC8F';
    WHEN 'wellness' THEN
      v_title := 'Mental Health & Wellness';
      v_description := 'Manage stress, prioritize self-care, and support each other''s mental health and wellbeing.';
      v_icon := '🧘';
      v_color := '#9370DB';
    ELSE
      v_title := initcap(p_category) || ' Articles';
      v_description := 'Curated articles about ' || p_category || ' in relationships.';
      v_icon := '📚';
      v_color := '#808080';
  END CASE;

  -- Create or update collection
  INSERT INTO collections (
    title,
    description,
    slug,
    collection_type,
    generation_method,
    generation_criteria,
    icon,
    color_theme
  )
  VALUES (
    v_title,
    v_description,
    v_slug,
    'category_based',
    'auto',
    jsonb_build_object('category', p_category, 'limit', p_limit),
    v_icon,
    v_color
  )
  ON CONFLICT (slug) DO UPDATE SET
    title = EXCLUDED.title,
    description = EXCLUDED.description,
    icon = EXCLUDED.icon,
    color_theme = EXCLUDED.color_theme,
    last_generated_at = now()
  RETURNING id INTO v_collection_id;

  -- Clear existing articles
  DELETE FROM collection_articles WHERE collection_id = v_collection_id;

  -- Add top articles from this category
  INSERT INTO collection_articles (collection_id, article_id, display_order, inclusion_reason)
  SELECT
    v_collection_id,
    a.id,
    ROW_NUMBER() OVER (ORDER BY COALESCE(ae.engagement_score, 0) DESC, a.overall_score DESC, a.created_at DESC),
    'Top performing article in ' || p_category || ' category'
  FROM articles a
  LEFT JOIN article_engagement ae ON ae.article_id = a.id
  WHERE a.category = p_category
    AND a.is_active = true
  ORDER BY COALESCE(ae.engagement_score, 0) DESC, a.overall_score DESC, a.created_at DESC
  LIMIT p_limit;

  -- Refresh stats
  PERFORM refresh_collection_stats(v_collection_id);

  RETURN v_collection_id;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION generate_category_collection IS 'Generate a collection for a specific category';


-- ============================================================================
-- FUNCTION: Generate Tag-Based Collection
-- Creates a collection for a specific tag
-- ============================================================================

CREATE OR REPLACE FUNCTION generate_tag_collection(
  p_tag TEXT,
  p_title TEXT DEFAULT NULL,
  p_description TEXT DEFAULT NULL,
  p_limit INTEGER DEFAULT 8
)
RETURNS UUID AS $$
DECLARE
  v_collection_id UUID;
  v_title TEXT;
  v_description TEXT;
  v_slug TEXT;
BEGIN
  v_slug := 'tag-' || regexp_replace(p_tag, '[^a-z0-9-]', '', 'gi');
  v_title := COALESCE(p_title, initcap(replace(p_tag, '-', ' ')));
  v_description := COALESCE(p_description, 'Articles about ' || replace(p_tag, '-', ' ') || ' in relationships.');

  -- Create or update collection
  INSERT INTO collections (
    title,
    description,
    slug,
    collection_type,
    generation_method,
    generation_criteria,
    icon
  )
  VALUES (
    v_title,
    v_description,
    v_slug,
    'tag_based',
    'auto',
    jsonb_build_object('tag', p_tag, 'limit', p_limit),
    '🏷️'
  )
  ON CONFLICT (slug) DO UPDATE SET
    title = EXCLUDED.title,
    description = EXCLUDED.description,
    last_generated_at = now()
  RETURNING id INTO v_collection_id;

  -- Clear existing articles
  DELETE FROM collection_articles WHERE collection_id = v_collection_id;

  -- Add articles with this tag
  INSERT INTO collection_articles (collection_id, article_id, display_order, inclusion_reason)
  SELECT
    v_collection_id,
    a.id,
    ROW_NUMBER() OVER (ORDER BY COALESCE(ae.engagement_score, 0) DESC, a.overall_score DESC, a.created_at DESC),
    'Tagged with ' || p_tag
  FROM articles a
  LEFT JOIN article_engagement ae ON ae.article_id = a.id
  WHERE a.tags @> ARRAY[p_tag]
    AND a.is_active = true
  ORDER BY COALESCE(ae.engagement_score, 0) DESC, a.overall_score DESC, a.created_at DESC
  LIMIT p_limit;

  -- Refresh stats
  PERFORM refresh_collection_stats(v_collection_id);

  RETURN v_collection_id;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION generate_tag_collection IS 'Generate a collection for a specific tag';


-- ============================================================================
-- FUNCTION: Generate High Engagement Collection
-- Creates a "Best of" collection with top performing articles
-- ============================================================================

CREATE OR REPLACE FUNCTION generate_high_engagement_collection(
  p_days INTEGER DEFAULT 30,
  p_limit INTEGER DEFAULT 10
)
RETURNS UUID AS $$
DECLARE
  v_collection_id UUID;
  v_threshold TIMESTAMP;
BEGIN
  v_threshold := now() - (p_days || ' days')::interval;

  -- Create or update collection
  INSERT INTO collections (
    title,
    description,
    slug,
    collection_type,
    generation_method,
    generation_criteria,
    icon,
    color_theme,
    is_featured
  )
  VALUES (
    'Most Popular Articles',
    'The most loved and saved articles by couples like you in the last ' || p_days || ' days.',
    'high-engagement',
    'high_engagement',
    'auto',
    jsonb_build_object('days', p_days, 'limit', p_limit),
    '⭐',
    '#FFD700',
    true
  )
  ON CONFLICT (slug) DO UPDATE SET
    description = EXCLUDED.description,
    last_generated_at = now()
  RETURNING id INTO v_collection_id;

  -- Clear existing articles
  DELETE FROM collection_articles WHERE collection_id = v_collection_id;

  -- Add top articles by engagement
  INSERT INTO collection_articles (collection_id, article_id, display_order, inclusion_reason)
  SELECT
    v_collection_id,
    a.id,
    ROW_NUMBER() OVER (ORDER BY ae.engagement_score DESC),
    'Engagement score: ' || ROUND(ae.engagement_score::numeric, 1)
  FROM articles a
  JOIN article_engagement ae ON ae.article_id = a.id
  WHERE a.is_active = true
    AND ae.last_view_at >= v_threshold
    AND ae.engagement_score > 0
  ORDER BY ae.engagement_score DESC
  LIMIT p_limit;

  -- Refresh stats
  PERFORM refresh_collection_stats(v_collection_id);

  RETURN v_collection_id;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION generate_high_engagement_collection IS 'Generate a "Best of" collection with top performing articles';


-- ============================================================================
-- FUNCTION: Generate All Category Collections
-- Creates collections for all 8 categories
-- ============================================================================

CREATE OR REPLACE FUNCTION generate_all_category_collections()
RETURNS TABLE (
  category TEXT,
  collection_id UUID,
  article_count INTEGER
) AS $$
BEGIN
  RETURN QUERY
  SELECT
    cat.category,
    generate_category_collection(cat.category, 10) as collection_id,
    (SELECT article_count FROM collections WHERE id = generate_category_collection(cat.category, 10)) as article_count
  FROM (
    VALUES
      ('communication'),
      ('conflict'),
      ('intimacy'),
      ('trust'),
      ('parenting'),
      ('finances'),
      ('growth'),
      ('wellness')
  ) AS cat(category);
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION generate_all_category_collections IS 'Generate collections for all 8 categories';
