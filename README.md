# Bonded Content Agent

An autonomous Claude agent that curates relationship and couples therapy content for the Bonded app. It monitors 12 trusted blogs daily, evaluates content relevance, and saves quality articles to your Supabase database.

## How It Works

1. **Daily Trigger**: Render Cron Job runs the agent at 8 AM UTC
2. **RSS Fetch**: Agent fetches recent posts from all configured blogs
3. **Deduplication**: Checks existing URLs to skip duplicates
4. **Evaluation**: Claude evaluates each article against Bonded's content criteria
5. **Curation**: Writes compelling blurbs for relevant articles
6. **Storage**: Saves approved articles to Supabase

## Deploy to Render

### Option 1: One-Click Deploy

1. Push this repo to GitHub
2. Go to [Render Dashboard](https://dashboard.render.com)
3. Click **New** → **Blueprint**
4. Connect your repo — Render will detect `render.yaml`
5. Add your environment variables when prompted

### Option 2: Manual Setup

1. Go to [Render Dashboard](https://dashboard.render.com)
2. Click **New** → **Cron Job**
3. Connect your GitHub repo
4. Configure:
   - **Name**: `bonded-content-agent`
   - **Runtime**: Docker
   - **Schedule**: `0 8 * * *` (8 AM UTC daily)
5. Add environment variables:
   ```
   ANTHROPIC_API_KEY=sk-ant-xxxxx
   SUPABASE_URL=https://xxxxx.supabase.co
   SUPABASE_SERVICE_KEY=eyJhbGci...
   MAX_ARTICLES_PER_RUN=20
   LOG_LEVEL=INFO
   ```
6. Click **Create Cron Job**

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `ANTHROPIC_API_KEY` | Yes | Your Anthropic API key |
| `SUPABASE_URL` | Yes | Your Supabase project URL |
| `SUPABASE_SERVICE_KEY` | Yes | Supabase service_role key (not anon) |
| `MAX_ARTICLES_PER_RUN` | No | Max articles to save per run (default: 20) |
| `LOG_LEVEL` | No | Logging level (default: INFO) |

## Local Development

```bash
# Clone the repo
git clone https://github.com/you/bonded-content-agent.git
cd bonded-content-agent

# Create .env file
cp .env.example .env
# Edit .env with your credentials

# Option 1: Run with Docker
docker build -t bonded-agent .
docker run --env-file .env bonded-agent

# Option 2: Run directly with Python
pip install -r requirements.txt
python src/main.py
```

## Testing

```bash
# Run health check
python src/healthcheck.py

# Run the agent
python src/main.py
```

## Startup Health Checks

The agent runs automatic health checks before each execution:

1. **Environment Variables** - Verifies `SUPABASE_URL` and `SUPABASE_SERVICE_KEY` are set
2. **Supabase Connection** - Tests actual connectivity to your database
3. **Table Access** - Confirms the `articles` table exists and is accessible

If any check fails, the agent logs detailed error messages and exits with code 2.

## Monitoring

Render captures all stdout/stderr automatically. View logs in the Render dashboard under your cron job → **Logs**.

Example successful run:
```
============================================================
Bonded Content Agent - Starting Run
============================================================
------------------------------------------------------------
STARTUP HEALTH CHECKS
------------------------------------------------------------
[1/1] Checking Supabase connection...
  ✓ Connected to: https://xxx.supabase.co
  ✓ Articles table accessible
  ✓ Current article count: 42
------------------------------------------------------------
ALL STARTUP CHECKS PASSED
------------------------------------------------------------
Starting Bonded Content Agent
Agent iteration 1
Fetching RSS feed: The Gottman Institute Blog
...
============================================================
Run Complete
Success: True
Articles saved: 5
============================================================
```

## Configuration

### Blog Sources

Edit `src/config.py` to add or remove blog sources:

```python
BLOG_SOURCES = [
    {
        "name": "Blog Name",
        "url": "https://example.com/blog",
        "rss": "https://example.com/feed",
        "notes": "Description"
    },
    # ...
]
```

### Schedule

Edit `render.yaml` to change the cron schedule:

```yaml
schedule: "0 8 * * *"    # Daily at 8 AM UTC
schedule: "0 8,20 * * *" # Twice daily
schedule: "0 */6 * * *"  # Every 6 hours
```

### Content Criteria

Edit `SYSTEM_PROMPT` in `src/config.py` to adjust what content Claude looks for.

## Cost Estimation

- **Render Cron Job**: Free tier includes 100 cron job hours/month (plenty for daily runs)
- **Anthropic API**: ~$0.10-0.50 per run depending on article volume
- **Supabase**: Free tier is sufficient

## File Structure

```
bonded-content-agent/
├── render.yaml           # Render deployment config
├── Dockerfile            # Container build
├── docker-compose.yml    # Local Docker development
├── requirements.txt      # Python dependencies
├── .env.example          # Template for local dev
├── src/
│   ├── main.py          # Entry point
│   ├── agent.py         # Claude agent logic
│   ├── tools.py         # Tool implementations
│   ├── config.py        # Blog sources & settings
│   ├── database.py      # Supabase operations
│   └── healthcheck.py   # Standalone health check
└── cron/
    └── crontab          # For self-hosted Docker (not used on Render)
```

## Extending

### Add New Tools

Edit `src/tools.py` to add new capabilities:

```python
# Add to TOOL_DEFINITIONS list
{
    "name": "your_new_tool",
    "description": "What it does",
    "input_schema": {...}
}

# Implement the function
def your_new_tool(param: str) -> dict:
    # Your logic
    return {"result": "..."}

# Add to execute_tool()
elif tool_name == "your_new_tool":
    result = your_new_tool(tool_input["param"])
```

### Add Notifications

You could extend the agent to send notifications (Slack, email, etc.) when new content is added. Add a notification tool and update the system prompt to use it.
