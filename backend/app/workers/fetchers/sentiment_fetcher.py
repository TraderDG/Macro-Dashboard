"""
Sentiment fetchers:
  1. CNN Fear & Greed Index (scrape)
  2. AAII Investor Sentiment Survey (scrape)
  3. News headlines via GNews free API (no key) or NewsAPI (free tier)
"""
import logging
import re
from datetime import datetime, timezone
from typing import Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)


class FearGreedFetcher:
    """
    CNN Fear & Greed Index via their internal API.
    Returns score 0-100 + label (Extreme Fear / Fear / Neutral / Greed / Extreme Greed).
    """
    URL = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata"

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=10))
    def fetch(self) -> dict[str, Any]:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://www.cnn.com/markets/fear-and-greed",
        }
        resp = httpx.get(self.URL, headers=headers, timeout=15, follow_redirects=True)
        resp.raise_for_status()
        data = resp.json()

        fg = data.get("fear_and_greed", {})
        score = float(fg.get("score", 0))
        rating = fg.get("rating", "")

        # Historical series for chart
        history = []
        for pt in data.get("fear_and_greed_historical", {}).get("data", []):
            history.append({
                "time": datetime.fromtimestamp(pt["x"] / 1000, tz=timezone.utc).isoformat(),
                "score": float(pt["y"]),
                "rating": pt.get("rating", ""),
            })

        return {
            "score": score,
            "rating": rating,
            "time": datetime.now(timezone.utc).isoformat(),
            "history": history[-90:],  # Last 90 days
        }

    def to_db_records(self, data: dict) -> list[dict[str, Any]]:
        records = []
        for pt in data.get("history", []):
            records.append({
                "time": datetime.fromisoformat(pt["time"]),
                "indicator": "fear_greed_index",
                "value": pt["score"],
                "label": pt["rating"],
                "source": "cnn",
            })
        return records


class AAIISentimentFetcher:
    """
    AAII Investor Sentiment Survey — weekly bull/bear/neutral %.
    Scrapes AAII's published CSV data.
    """
    URL = "https://www.aaii.com/files/surveys/sentiment.xls"

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=15))
    def fetch(self) -> list[dict[str, Any]]:
        import pandas as pd
        import io

        headers = {"User-Agent": "Mozilla/5.0"}
        resp = httpx.get(self.URL, headers=headers, timeout=30, follow_redirects=True)
        resp.raise_for_status()

        df = pd.read_excel(io.BytesIO(resp.content), skiprows=3)
        df = df.dropna(subset=[df.columns[0]])

        records = []
        for _, row in df.head(100).iterrows():
            try:
                date_raw = row.iloc[0]
                if hasattr(date_raw, "strftime"):
                    dt = date_raw.replace(tzinfo=timezone.utc)
                else:
                    dt = datetime.strptime(str(date_raw)[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)

                # Columns: Date, Bullish, Neutral, Bearish, Total, Bullish 8-week MA, ...
                bullish = float(str(row.iloc[1]).replace("%", "").strip()) if pd.notna(row.iloc[1]) else None
                neutral = float(str(row.iloc[2]).replace("%", "").strip()) if pd.notna(row.iloc[2]) else None
                bearish = float(str(row.iloc[3]).replace("%", "").strip()) if pd.notna(row.iloc[3]) else None

                if bullish is not None:
                    records.append({
                        "time": dt,
                        "indicator": "aaii_bullish",
                        "value": bullish,
                        "label": "bullish",
                        "source": "aaii",
                    })
                if bearish is not None:
                    records.append({
                        "time": dt,
                        "indicator": "aaii_bearish",
                        "value": bearish,
                        "label": "bearish",
                        "source": "aaii",
                    })
                if neutral is not None:
                    records.append({
                        "time": dt,
                        "indicator": "aaii_neutral",
                        "value": neutral,
                        "label": "neutral",
                        "source": "aaii",
                    })
            except (ValueError, TypeError, IndexError):
                continue

        logger.info(f"AAII: fetched {len(records)} records")
        return records


class NewsFetcher:
    """
    Financial news headlines — GNews free (no key) or NewsAPI free tier.
    """
    GNEWS_URL = "https://gnews.io/api/v4/search"
    QUERIES = [
        "Federal Reserve interest rates",
        "inflation CPI",
        "global economy recession",
        "stock market",
        "US Treasury bonds",
    ]

    def fetch_gnews(self, api_key: str = "") -> list[dict[str, Any]]:
        if not api_key:
            return self._fetch_rss_fallback()

        articles = []
        for q in self.QUERIES[:3]:
            try:
                resp = httpx.get(
                    self.GNEWS_URL,
                    params={"q": q, "lang": "en", "max": 5, "token": api_key},
                    timeout=10,
                )
                resp.raise_for_status()
                for a in resp.json().get("articles", []):
                    articles.append({
                        "title": a["title"],
                        "url": a["url"],
                        "source": a.get("source", {}).get("name", ""),
                        "published_at": a["publishedAt"],
                        "query": q,
                    })
            except Exception as e:
                logger.warning(f"GNews failed for '{q}': {e}")
        return articles

    def _fetch_rss_fallback(self) -> list[dict[str, Any]]:
        """Fallback: parse Yahoo Finance RSS (no key needed)."""
        import xml.etree.ElementTree as ET

        feeds = [
            "https://finance.yahoo.com/news/rssindex",
            "https://feeds.a.dj.com/rss/RSSMarketsMain.xml",
        ]
        articles = []
        for url in feeds:
            try:
                resp = httpx.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
                resp.raise_for_status()
                root = ET.fromstring(resp.text)
                for item in root.findall(".//item")[:8]:
                    title = item.findtext("title", "")
                    link = item.findtext("link", "")
                    pub_date = item.findtext("pubDate", "")
                    articles.append({
                        "title": title.strip(),
                        "url": link.strip(),
                        "source": url.split("/")[2],
                        "published_at": pub_date,
                        "query": "market",
                    })
            except Exception as e:
                logger.warning(f"RSS fallback failed {url}: {e}")
        return articles
