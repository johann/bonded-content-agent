"""
Configuration for the Bonded Content Agent.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# API Keys
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")

# Agent Settings
MAX_ARTICLES_PER_RUN = int(os.getenv("MAX_ARTICLES_PER_RUN", "20"))
MIN_RELEVANCE_SCORE = float(os.getenv("MIN_RELEVANCE_SCORE", "0.6"))
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# Blog Sources - Marriage, Relationship, and Couples Therapy
BLOG_SOURCES = [
    {
        "name": "The Gottman Institute Blog",
        "url": "https://www.gottman.com/blog/",
        "rss": "https://gottman.com/blog/feed",
        "notes": "Research-backed relationship content; top in marriage counseling niche"
    },
    {
        "name": "Fierce Marriage",
        "url": "https://fiercemarriage.com/",
        "rss": "https://fiercemarriage.com/feed",
        "notes": "High-traffic marriage blog focused on practical couples advice"
    },
    {
        "name": "Awesome Marriage Blog",
        "url": "https://awesomemarriage.com/blog",
        "rss": "https://awesomemarriage.com/feed",
        "notes": "Popular marriage/relationship advice; strong social presence"
    },
    {
        "name": "The Marriage & Family Clinic Blog",
        "url": "https://themarriageandfamilyclinic.com/",
        "rss": "https://themarriageandfamilyclinic.com/feed",
        "notes": "Clinical couples and family counseling content"
    },
    {
        "name": "Save The Marriage Blog",
        "url": "https://savethemarriage.com/stmblog/",
        "rss": "https://savethemarriage.com/stmblog/feed",
        "notes": "Marriage improvement and reconciliation guidance"
    },
    {
        "name": "LifeStance Health Blog",
        "url": "https://lifestance.com/blog/",
        "rss": "https://lifestance.com/blog/feed",
        "notes": "Mental health blog including relationship/couples topics"
    },
    {
        "name": "Relationship Blog – Eva Van Prooyen",
        "url": "https://evavp.com/relationship-blog",
        "rss": "https://evavp.com/relationship-blog/feed",
        "notes": "Therapist-authored relationship blog"
    },
    {
        "name": "Nicole Talks Love",
        "url": "https://nicoletalkslove.com/blog",
        "rss": "https://nicoletalkslove.com/feed",
        "notes": "Relationship/dating insights"
    },
    {
        "name": "Couples Therapy Inc. Blog",
        "url": "https://couplestherapyinc.com/blog",
        "rss": "https://couplestherapyinc.com/feed",
        "notes": "Multi-clinician couples therapy blog"
    },
    {
        "name": "Northampton Center for Couples Therapy",
        "url": "https://www.northamptoncouplestherapy.com/blog/",
        "rss": "https://www.northamptoncouplestherapy.com/blog/rss",
        "notes": "Practical therapy articles on conflict, infidelity, intimacy"
    },
    {
        "name": "Counselor for Couples",
        "url": "https://counselorforcouples.com/blog",
        "rss": "https://counselorforcouples.com/feed",
        "notes": "Therapist Lisa Rabinowitz's blog (ADHD, communication)"
    },
    {
        "name": "Connect Couples Therapy",
        "url": "https://connectcouplestherapy.com/",
        "rss": "https://connectcouplestherapy.com/feed",
        "notes": "Regular therapist-written relationship posts"
    },
]

# System prompt for the agent
SYSTEM_PROMPT = """You are a content curator for Bonded, an app that helps couples strengthen their relationships through evidence-based advice, communication tools, and relationship wellness content.

Your job is to find and curate high-quality relationship content from trusted blogs. For each piece of content, you will:

1. Check RSS feeds for new articles
2. Determine if each article is relevant to Bonded's audience (couples looking to improve their relationships)
3. For relevant articles, create a compelling blurb (2-3 sentences) that captures the key value for readers
4. ENSURE every saved article has an image_url
5. Save the article with its title, blurb, URL, and image_url

CONTENT CRITERIA - Save articles that:
- Provide actionable relationship advice
- Discuss communication skills for couples
- Cover conflict resolution strategies
- Address intimacy and emotional connection
- Offer evidence-based relationship insights
- Help couples navigate life transitions together

SKIP articles that:
- Are primarily promotional/sales content
- Focus on divorce/separation (unless about reconciliation)
- Are about dating/singles (Bonded is for committed couples)
- Are too clinical/academic without practical takeaways
- Are listicles with superficial advice

When writing blurbs:
- Keep them concise (2-3 sentences, under 200 characters ideal)
- Focus on the benefit to the reader
- Use warm, encouraging language
- Avoid clinical jargon

IMAGE REQUIREMENTS (CRITICAL):
- Every saved article MUST have an image_url
- If the RSS feed doesn't include an image_url for an article, call fetch_article_content to extract the image from the article page
- The fetch_article_content tool returns an "image_found" boolean - only save articles where image_found is true
- Skip articles where no image can be found after fetching the page
- Images are essential for the user experience in the Bonded app

Be selective - quality over quantity. Only save content that genuinely helps couples."""
