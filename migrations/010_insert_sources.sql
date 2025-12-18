-- Migration: Insert Blog Sources
-- Phase 3: Source Management
-- Run this in your Supabase SQL editor AFTER running migration 003 (create_sources_table.sql)
-- This inserts all sources from src/config.py into the sources table

-- Insert sources (skipping duplicates if already exists)
INSERT INTO sources (name, website_url, rss_url, description, is_active, discovered_by)
SELECT * FROM (VALUES
  (
    'The Gottman Institute Blog',
    'https://www.gottman.com/blog/',
    'https://gottman.com/blog/feed',
    'Research-backed relationship content; top in marriage counseling niche',
    true,
    'manual'
  ),
  (
    'Fierce Marriage',
    'https://fiercemarriage.com/',
    'https://fiercemarriage.com/feed',
    'High-traffic marriage blog focused on practical couples advice',
    true,
    'manual'
  ),
  (
    'Awesome Marriage Blog',
    'https://awesomemarriage.com/blog',
    'https://awesomemarriage.com/feed',
    'Popular marriage/relationship advice; strong social presence',
    true,
    'manual'
  ),
  (
    'The Marriage & Family Clinic Blog',
    'https://themarriageandfamilyclinic.com/',
    'https://themarriageandfamilyclinic.com/feed',
    'Clinical couples and family counseling content',
    true,
    'manual'
  ),
  (
    'Save The Marriage Blog',
    'https://savethemarriage.com/stmblog/',
    'https://savethemarriage.com/stmblog/feed',
    'Marriage improvement and reconciliation guidance',
    true,
    'manual'
  ),
  (
    'LifeStance Health Blog',
    'https://lifestance.com/blog/',
    'https://lifestance.com/blog/feed',
    'Mental health blog including relationship/couples topics',
    true,
    'manual'
  ),
  (
    'Relationship Blog – Eva Van Prooyen',
    'https://evavp.com/relationship-blog',
    'https://evavp.com/relationship-blog/feed',
    'Therapist-authored relationship blog',
    true,
    'manual'
  ),
  (
    'Nicole Talks Love',
    'https://nicoletalkslove.com/blog',
    'https://nicoletalkslove.com/feed',
    'Relationship/dating insights',
    true,
    'manual'
  ),
  (
    'Couples Therapy Inc. Blog',
    'https://couplestherapyinc.com/blog',
    'https://couplestherapyinc.com/feed',
    'Multi-clinician couples therapy blog',
    true,
    'manual'
  ),
  (
    'Northampton Center for Couples Therapy',
    'https://www.northamptoncouplestherapy.com/blog/',
    'https://www.northamptoncouplestherapy.com/blog/rss',
    'Practical therapy articles on conflict, infidelity, intimacy',
    true,
    'manual'
  ),
  (
    'Counselor for Couples',
    'https://counselorforcouples.com/blog',
    'https://counselorforcouples.com/feed',
    'Therapist Lisa Rabinowitz''s blog (ADHD, communication)',
    true,
    'manual'
  ),
  (
    'Connect Couples Therapy',
    'https://connectcouplestherapy.com/',
    'https://connectcouplestherapy.com/feed',
    'Regular therapist-written relationship posts',
    true,
    'manual'
  )
) AS v(name, website_url, rss_url, description, is_active, discovered_by)
WHERE NOT EXISTS (
  SELECT 1 FROM sources WHERE sources.rss_url = v.rss_url
);

-- Verify inserts
SELECT 
  COUNT(*) as total_sources,
  COUNT(*) FILTER (WHERE is_active = true) as active_sources
FROM sources;

