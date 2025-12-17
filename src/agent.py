"""
Claude Agent for curating relationship content for Bonded.
"""

import logging
import json
from anthropic import Anthropic
from supabase import Client

from config import ANTHROPIC_API_KEY, BLOG_SOURCES, SYSTEM_PROMPT, MAX_ARTICLES_PER_RUN
from tools import TOOL_DEFINITIONS, execute_tool

logger = logging.getLogger(__name__)


class BondedContentAgent:
    """Agent that curates relationship content from blogs."""
    
    def __init__(self, supabase_client: Client):
        self.client = Anthropic(api_key=ANTHROPIC_API_KEY)
        self.supabase = supabase_client
        self.messages = []
        self.articles_saved = 0
        self.articles_skipped = 0
        
    def run(self) -> dict:
        """Run the content curation agent."""
        logger.info("Starting Bonded Content Agent")
        
        # Prepare the initial message with blog sources
        sources_info = "\n".join([
            f"- {s['name']}: RSS at {s['rss']}" 
            for s in BLOG_SOURCES
        ])
        
        initial_message = f"""Please curate new relationship content for Bonded from these blog sources:

{sources_info}

Instructions:
1. First, call get_all_existing_urls to see what's already in the database
2. Then fetch each RSS feed and identify new articles (not in existing URLs)
3. For promising articles, evaluate if they fit Bonded's content criteria
4. Save relevant articles with compelling blurbs (max {MAX_ARTICLES_PER_RUN} new articles this run)
5. Provide a summary when done

Focus on quality over quantity. Skip promotional content and articles that don't provide actionable value for couples."""

        self.messages = [{"role": "user", "content": initial_message}]
        
        # Run the agentic loop
        max_iterations = 50  # Safety limit
        iteration = 0
        
        while iteration < max_iterations:
            iteration += 1
            logger.info(f"Agent iteration {iteration}")
            
            # Call Claude
            response = self.client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=4096,
                system=SYSTEM_PROMPT,
                tools=TOOL_DEFINITIONS,
                messages=self.messages
            )
            
            logger.debug(f"Response stop_reason: {response.stop_reason}")
            
            # Check if we're done
            if response.stop_reason == "end_turn":
                # Extract final message
                final_text = ""
                for block in response.content:
                    if hasattr(block, "text"):
                        final_text = block.text
                        break
                
                logger.info("Agent completed successfully")
                return {
                    "success": True,
                    "articles_saved": self.articles_saved,
                    "articles_skipped": self.articles_skipped,
                    "iterations": iteration,
                    "summary": final_text
                }
            
            # Process tool calls
            if response.stop_reason == "tool_use":
                # Add assistant's response to messages
                self.messages.append({
                    "role": "assistant",
                    "content": response.content
                })
                
                # Execute each tool call
                tool_results = []
                for block in response.content:
                    if block.type == "tool_use":
                        logger.info(f"Executing tool: {block.name}")
                        
                        result = execute_tool(
                            block.name, 
                            block.input, 
                            self.supabase
                        )
                        
                        # Track saved articles
                        if block.name == "save_article_to_database":
                            result_data = json.loads(result)
                            if result_data.get("success"):
                                self.articles_saved += 1
                            else:
                                self.articles_skipped += 1
                        
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": result
                        })
                
                # Add tool results to messages
                self.messages.append({
                    "role": "user",
                    "content": tool_results
                })
            else:
                # Unexpected stop reason
                logger.warning(f"Unexpected stop_reason: {response.stop_reason}")
                break
        
        logger.warning(f"Agent reached max iterations ({max_iterations})")
        return {
            "success": False,
            "error": "Max iterations reached",
            "articles_saved": self.articles_saved,
            "iterations": iteration
        }
