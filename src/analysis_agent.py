"""
Trend Analysis Agent for the Bonded Content Agent.
Analyzes content performance, identifies trends and gaps.
"""

import logging
from datetime import datetime, timedelta
from supabase import Client

logger = logging.getLogger(__name__)


class TrendAnalysisAgent:
    """Agent that analyzes content trends and identifies gaps."""

    def __init__(self, supabase_client: Client):
        self.supabase = supabase_client

    def analyze_week(self, days: int = 7) -> dict:
        """
        Run complete weekly analysis.

        Returns:
            dict with analysis results and report ID
        """
        try:
            logger.info(f"Starting weekly trend analysis for last {days} days")

            # Define analysis period
            period_end = datetime.now()
            period_start = period_end - timedelta(days=days)

            # Run all analyses
            trending_topics = self._analyze_trending_topics()
            top_articles = self._analyze_top_articles(days)
            top_sources = self._analyze_top_sources(days)
            content_gaps = self._identify_content_gaps()
            statistics = self._calculate_statistics(days)
            recommendations = self._generate_recommendations(
                trending_topics,
                content_gaps,
                top_sources
            )
            summary = self._generate_summary(
                trending_topics,
                top_articles,
                content_gaps,
                statistics
            )

            # Save report
            report_data = {
                "report_type": "weekly",
                "period_start": period_start.isoformat(),
                "period_end": period_end.isoformat(),
                "trending_topics": trending_topics,
                "top_articles": top_articles,
                "top_sources": top_sources,
                "content_gaps": content_gaps,
                "recommendations": recommendations,
                "total_articles_published": statistics["total_articles"],
                "total_articles_viewed": statistics["total_views"],
                "total_engagement_score": statistics["total_engagement"],
                "avg_save_rate": statistics["avg_save_rate"],
                "avg_overall_score": statistics["avg_quality_score"],
                "category_distribution": statistics["category_distribution"],
                "summary": summary
            }

            result = self.supabase.table("content_analysis_reports").insert(report_data).execute()

            if result.data:
                report_id = result.data[0]["id"]
                logger.info(f"✅ Weekly analysis complete. Report saved: {report_id}")

                return {
                    "success": True,
                    "report_id": report_id,
                    "summary": summary,
                    "trending_topics_count": len(trending_topics.get("topics", [])),
                    "content_gaps_count": len(content_gaps.get("gaps", [])),
                    "recommendations_count": len(recommendations.get("recommendations", []))
                }
            else:
                return {"success": False, "error": "Failed to save report"}

        except Exception as e:
            logger.error(f"Error running weekly analysis: {e}")
            return {"success": False, "error": str(e)}

    def _analyze_trending_topics(self) -> dict:
        """Identify trending topics using tag_trending_analysis view."""
        try:
            result = self.supabase.table("tag_trending_analysis").select("*").limit(10).execute()

            if not result.data:
                return {"topics": []}

            trending = [
                {
                    "tag": row["tag"],
                    "recent_count": row["recent_count"],
                    "historical_count": row["historical_count"],
                    "trending_percentage": round(row.get("trending_percentage", 0), 1),
                    "status": "🔥 Hot" if row.get("trending_percentage", 0) > 50 else "📈 Rising"
                }
                for row in result.data if row.get("trending_percentage", 0) > 0
            ]

            logger.info(f"Identified {len(trending)} trending topics")
            return {"topics": trending}

        except Exception as e:
            logger.error(f"Error analyzing trending topics: {e}")
            return {"topics": []}

    def _analyze_top_articles(self, days: int) -> dict:
        """Get top performing articles from the period."""
        try:
            threshold = datetime.now() - timedelta(days=days)

            result = self.supabase.table("recent_article_performance") \
                .select("*") \
                .order("engagement_score", desc=True) \
                .limit(10) \
                .execute()

            if not result.data:
                return {"articles": []}

            top_articles = [
                {
                    "title": row["title"],
                    "url": row["url"],
                    "category": row["category"],
                    "source": row.get("source_name"),
                    "engagement_score": round(row.get("engagement_score", 0), 1),
                    "save_rate": round(row.get("save_rate", 0), 1),
                    "view_count": row.get("view_count", 0)
                }
                for row in result.data
            ]

            logger.info(f"Identified {len(top_articles)} top articles")
            return {"articles": top_articles}

        except Exception as e:
            logger.error(f"Error analyzing top articles: {e}")
            return {"articles": []}

    def _analyze_top_sources(self, days: int) -> dict:
        """Identify best performing sources in the period."""
        try:
            result = self.supabase.table("source_performance_view") \
                .select("*") \
                .limit(5) \
                .execute()

            if not result.data:
                return {"sources": []}

            top_sources = [
                {
                    "name": row["name"],
                    "avg_engagement_score": round(row.get("avg_engagement_score", 0), 1),
                    "acceptance_rate": round(row.get("acceptance_rate", 0), 1),
                    "total_saves": row.get("total_saves", 0)
                }
                for row in result.data[:5]
            ]

            logger.info(f"Identified {len(top_sources)} top sources")
            return {"sources": top_sources}

        except Exception as e:
            logger.error(f"Error analyzing top sources: {e}")
            return {"sources": []}

    def _identify_content_gaps(self) -> dict:
        """Identify content gaps using identify_content_gaps function."""
        try:
            result = self.supabase.rpc("identify_content_gaps").execute()

            if not result.data:
                return {"gaps": []}

            # Group by priority
            high_priority = []
            medium_priority = []

            for gap in result.data:
                gap_info = {
                    "type": gap["gap_type"],
                    "description": gap["gap_description"],
                    "evidence": gap["evidence"],
                    "priority": gap["priority"]
                }

                if gap["priority"] == "high":
                    high_priority.append(gap_info)
                elif gap["priority"] == "medium":
                    medium_priority.append(gap_info)

            logger.info(f"Identified {len(high_priority)} high-priority gaps, {len(medium_priority)} medium-priority")

            return {
                "gaps": high_priority + medium_priority,
                "high_priority_count": len(high_priority),
                "medium_priority_count": len(medium_priority)
            }

        except Exception as e:
            logger.error(f"Error identifying content gaps: {e}")
            return {"gaps": []}

    def _calculate_statistics(self, days: int) -> dict:
        """Calculate overall statistics for the period."""
        try:
            threshold = datetime.now() - timedelta(days=days)

            # Get articles in period
            articles_result = self.supabase.table("articles") \
                .select("*, article_engagement(*)") \
                .gte("created_at", threshold.isoformat()) \
                .execute()

            total_articles = len(articles_result.data) if articles_result.data else 0
            total_views = 0
            total_engagement = 0
            save_rates = []
            quality_scores = []
            category_counts = {}

            if articles_result.data:
                for article in articles_result.data:
                    # Category distribution
                    category = article.get("category")
                    if category:
                        category_counts[category] = category_counts.get(category, 0) + 1

                    # Quality scores
                    if article.get("overall_score"):
                        quality_scores.append(article["overall_score"])

                    # Engagement metrics
                    engagement = article.get("article_engagement")
                    if engagement:
                        if isinstance(engagement, list) and engagement:
                            engagement = engagement[0]

                        total_views += engagement.get("view_count", 0)
                        total_engagement += engagement.get("engagement_score", 0)

                        if engagement.get("save_rate"):
                            save_rates.append(engagement["save_rate"])

            return {
                "total_articles": total_articles,
                "total_views": total_views,
                "total_engagement": round(total_engagement, 2),
                "avg_save_rate": round(sum(save_rates) / len(save_rates), 1) if save_rates else 0,
                "avg_quality_score": round(sum(quality_scores) / len(quality_scores), 1) if quality_scores else 0,
                "category_distribution": category_counts
            }

        except Exception as e:
            logger.error(f"Error calculating statistics: {e}")
            return {
                "total_articles": 0,
                "total_views": 0,
                "total_engagement": 0,
                "avg_save_rate": 0,
                "avg_quality_score": 0,
                "category_distribution": {}
            }

    def _generate_recommendations(self, trending_topics: dict, content_gaps: dict, top_sources: dict) -> dict:
        """Generate actionable recommendations based on analysis."""
        recommendations = []

        # Recommendation 1: Focus on trending topics
        if trending_topics.get("topics"):
            top_trending = trending_topics["topics"][:3]
            trending_tags = ", ".join([t["tag"] for t in top_trending])
            recommendations.append({
                "type": "trending_focus",
                "priority": "high",
                "recommendation": f"Prioritize content covering: {trending_tags}",
                "reasoning": "These topics show increased volume and engagement"
            })

        # Recommendation 2: Address high-priority gaps
        high_priority_gaps = [g for g in content_gaps.get("gaps", []) if g["priority"] == "high"]
        if high_priority_gaps:
            for gap in high_priority_gaps[:2]:  # Top 2 gaps
                recommendations.append({
                    "type": "fill_gap",
                    "priority": "high",
                    "recommendation": gap["description"],
                    "reasoning": f"Gap type: {gap['type']}"
                })

        # Recommendation 3: Leverage top sources
        if top_sources.get("sources"):
            top_3_sources = [s["name"] for s in top_sources["sources"][:3]]
            recommendations.append({
                "type": "source_focus",
                "priority": "medium",
                "recommendation": f"Prioritize articles from: {', '.join(top_3_sources)}",
                "reasoning": "These sources consistently produce high-engagement content"
            })

        # Recommendation 4: Category balance
        # (Would need category distribution analysis - placeholder for now)

        return {"recommendations": recommendations}

    def _generate_summary(
        self,
        trending_topics: dict,
        top_articles: dict,
        content_gaps: dict,
        statistics: dict
    ) -> str:
        """Generate executive summary of findings."""

        summary_parts = []

        # Overview
        summary_parts.append(
            f"📊 **Week in Review**: Published {statistics['total_articles']} articles "
            f"with {statistics['total_views']:,} total views and "
            f"avg save rate of {statistics['avg_save_rate']}%."
        )

        # Trending
        if trending_topics.get("topics"):
            top_3 = ", ".join([t["tag"] for t in trending_topics["topics"][:3]])
            summary_parts.append(f"\n\n🔥 **Trending Topics**: {top_3}")

        # Top performer
        if top_articles.get("articles"):
            top_article = top_articles["articles"][0]
            summary_parts.append(
                f"\n\n⭐ **Top Performer**: \"{top_article['title']}\" "
                f"({top_article['category']}) with {top_article['save_rate']}% save rate"
            )

        # Gaps
        high_priority_gaps = content_gaps.get("high_priority_count", 0)
        if high_priority_gaps > 0:
            summary_parts.append(
                f"\n\n⚠️ **Content Gaps**: {high_priority_gaps} high-priority opportunities identified"
            )

        return "".join(summary_parts)
