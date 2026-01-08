"""Sentiment analysis adapter for news content."""

import logging
import re
from typing import Optional
import asyncio

from ..contracts import NewsItem, SentimentAnalyzer

logger = logging.getLogger(__name__)


class BasicSentimentAnalyzer(SentimentAnalyzer):
    """Basic rule-based sentiment analyzer for financial news."""

    def __init__(self):
        """Initialize with sentiment dictionaries."""
        self.positive_words = self._load_positive_words()
        self.negative_words = self._load_negative_words()
        self.intensifiers = {"very", "extremely", "highly", "strongly", "significantly"}

    def _load_positive_words(self) -> set:
        """Load positive sentiment words."""
        return {
            # Financial positive
            "gain", "gains", "rise", "rises", "rising", "up", "higher", "increase", "increased",
            "growth", "growing", "profit", "profitable", "bullish", "rally", "surge", "surges",
            "boost", "boosts", "strong", "record", "breakthrough", "upgrade", "upgraded",

            # General positive
            "good", "great", "excellent", "positive", "success", "successful", "win", "wins",
            "winning", "improvement", "improved", "better", "best", "outperform", "outperforms"
        }

    def _load_negative_words(self) -> set:
        """Load negative sentiment words."""
        return {
            # Financial negative
            "loss", "losses", "fall", "falls", "falling", "down", "lower", "decrease", "decreased",
            "decline", "declining", "drop", "drops", "crash", "crashes", "bearish", "slump", "slumps",
            "weak", "weaken", "pressure", "pressures", "downgrade", "downgraded", "panic", "panics",

            # General negative
            "bad", "poor", "terrible", "negative", "fail", "fails", "failure", "worst",
            "worse", "decline", "declining", "crisis", "problem", "problems", "issue", "issues"
        }

    async def analyze_sentiment(self, text: str) -> float:
        """Analyze sentiment of text. Returns score from -1.0 (negative) to 1.0 (positive)."""
        if not text or not text.strip():
            return 0.0

        # Clean and tokenize text
        text = text.lower()
        text = re.sub(r'[^\w\s]', ' ', text)  # Remove punctuation
        words = text.split()

        if not words:
            return 0.0

        # Count sentiment words
        positive_count = 0
        negative_count = 0

        for i, word in enumerate(words):
            if word in self.positive_words:
                # Check for intensifier before this word
                multiplier = 1.5 if i > 0 and words[i-1] in self.intensifiers else 1.0
                positive_count += multiplier
            elif word in self.negative_words:
                # Check for intensifier before this word
                multiplier = 1.5 if i > 0 and words[i-1] in self.intensifiers else 1.0
                negative_count += multiplier

        # Calculate sentiment score
        total_sentiment_words = positive_count + negative_count

        if total_sentiment_words == 0:
            return 0.0

        # Normalize to -1.0 to 1.0 range
        raw_score = (positive_count - negative_count) / total_sentiment_words
        return max(-1.0, min(1.0, raw_score))

    async def analyze_news_item(self, news_item: NewsItem) -> NewsItem:
        """Analyze sentiment of a news item and update its sentiment_score."""
        try:
            # Combine title and content for analysis
            text_to_analyze = f"{news_item.title} {news_item.content}"

            sentiment_score = await self.analyze_sentiment(text_to_analyze)

            # Create a new NewsItem with updated sentiment
            updated_item = NewsItem(
                title=news_item.title,
                content=news_item.content,
                summary=news_item.summary,
                source=news_item.source,
                url=news_item.url,
                published_at=news_item.published_at,
                sentiment_score=sentiment_score,
                relevance_score=news_item.relevance_score,
                instruments=news_item.instruments.copy(),
                tags=news_item.tags.copy(),
                author=news_item.author,
                language=news_item.language
            )

            logger.debug(f"Analyzed sentiment for '{news_item.title[:50]}...': {sentiment_score:.3f}")
            return updated_item

        except Exception as e:
            logger.error(f"Failed to analyze sentiment for news item: {e}")
            return news_item


class AdvancedSentimentAnalyzer(SentimentAnalyzer):
    """Advanced sentiment analyzer using external NLP services."""

    def __init__(self, api_key: Optional[str] = None, provider: str = "openai"):
        """Initialize with external NLP service.

        Args:
            api_key: API key for the sentiment analysis service
            provider: Service provider ("openai", "anthropic", etc.)
        """
        self.api_key = api_key
        self.provider = provider

    async def analyze_sentiment(self, text: str) -> float:
        """Analyze sentiment using external NLP service."""
        try:
            if self.provider == "openai":
                return await self._analyze_with_openai(text)
            elif self.provider == "anthropic":
                return await self._analyze_with_anthropic(text)
            else:
                logger.warning(f"Unknown provider {self.provider}, falling back to basic analysis")
                basic_analyzer = BasicSentimentAnalyzer()
                return await basic_analyzer.analyze_sentiment(text)
        except Exception as e:
            logger.error(f"External sentiment analysis failed: {e}")
            # Fallback to basic analysis
            basic_analyzer = BasicSentimentAnalyzer()
            return await basic_analyzer.analyze_sentiment(text)

    async def analyze_news_item(self, news_item: NewsItem) -> NewsItem:
        """Analyze sentiment using external service."""
        try:
            text_to_analyze = f"{news_item.title} {news_item.content}"
            sentiment_score = await self.analyze_sentiment(text_to_analyze)

            updated_item = NewsItem(
                title=news_item.title,
                content=news_item.content,
                summary=news_item.summary,
                source=news_item.source,
                url=news_item.url,
                published_at=news_item.published_at,
                sentiment_score=sentiment_score,
                relevance_score=news_item.relevance_score,
                instruments=news_item.instruments.copy(),
                tags=news_item.tags.copy(),
                author=news_item.author,
                language=news_item.language
            )

            return updated_item

        except Exception as e:
            logger.error(f"Failed to analyze news item with external service: {e}")
            return news_item

    async def _analyze_with_openai(self, text: str) -> float:
        """Analyze sentiment using OpenAI API."""
        try:
            import openai

            if not self.api_key:
                raise ValueError("OpenAI API key required")

            client = openai.AsyncOpenAI(api_key=self.api_key)

            prompt = f"""
            Analyze the sentiment of this financial news text. Return only a number between -1.0 and 1.0,
            where -1.0 is very negative, 0.0 is neutral, and 1.0 is very positive.

            Text: {text[:1000]}  # Limit text length

            Sentiment score:"""

            response = await client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=10,
                temperature=0.1
            )

            score_text = response.choices[0].message.content.strip()
            return float(score_text)

        except Exception as e:
            logger.error(f"OpenAI sentiment analysis failed: {e}")
            raise

    async def _analyze_with_anthropic(self, text: str) -> float:
        """Analyze sentiment using Anthropic API."""
        # Placeholder for Anthropic implementation
        logger.warning("Anthropic sentiment analysis not implemented yet")
        basic_analyzer = BasicSentimentAnalyzer()
        return await basic_analyzer.analyze_sentiment(text)