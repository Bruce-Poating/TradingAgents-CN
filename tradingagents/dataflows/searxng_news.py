"""Chinese news data source using SearXNG.

Provides A-share related news in Chinese from a self-hosted SearXNG instance.
"""

import os
from datetime import datetime
from typing import Annotated

import requests

from .errors import NoMarketDataError

SEARXNG_URL = os.getenv("SEARXNG_URL", "http://100.66.66.66:8889")

# Alternative: use Tavily if available
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")


def _is_a_share(symbol: str) -> bool:
    s = symbol.strip().upper()
    if "." in s:
        return s.split(".")[-1] in ("SS", "SH", "SZ")
    code = s.replace("SH", "").replace("SZ", "")
    return code.isdigit() and len(code) == 6


def _extract_code(symbol: str) -> str:
    s = symbol.strip().upper()
    if "." in s:
        return s.split(".")[0]
    return s.replace("SH", "").replace("SZ", "")


def get_news_searxng(
    ticker: Annotated[str, "ticker symbol"],
    curr_date: Annotated[str, "current date YYYY-mm-dd"] = None,
    max_results: Annotated[int, "max articles"] = 10,
) -> str:
    """Get stock-related news using SearXNG search.
    
    Searches Chinese financial news sources for the given stock.
    """
    code = _extract_code(ticker)
    
    # Build search queries for this stock
    queries = [
        f"{code} 股票 新闻",
        f"{code} A股 最新消息",
    ]
    
    all_articles = []
    
    for query in queries:
        try:
            resp = requests.get(
                f"{SEARXNG_URL}/search",
                params={
                    "q": query,
                    "format": "json",
                    "categories": "news",
                    "language": "zh",
                    "time_range": "week",
                },
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            
            results = data.get("results", [])
            for r in results[:max_results]:
                all_articles.append({
                    "title": r.get("title", ""),
                    "summary": r.get("content", ""),
                    "url": r.get("url", ""),
                    "source": r.get("engine", "unknown"),
                    "date": r.get("publishedDate", ""),
                })
        except Exception:
            continue
    
    if not all_articles:
        # Fallback: try Tavily search if configured
        if TAVILY_API_KEY:
            try:
                resp = requests.post(
                    "https://api.tavily.com/search",
                    json={
                        "api_key": TAVILY_API_KEY,
                        "query": f"{code} stock news A股",
                        "max_results": max_results,
                        "search_depth": "basic",
                    },
                    timeout=15,
                )
                resp.raise_for_status()
                data = resp.json()
                for r in data.get("results", [])[:max_results]:
                    all_articles.append({
                        "title": r.get("title", ""),
                        "summary": r.get("content", ""),
                        "url": r.get("url", ""),
                        "source": "tavily",
                        "date": r.get("published_date", ""),
                    })
            except Exception:
                pass
        
        # Fallback: try general web search
        if not all_articles:
            try:
                resp = requests.get(
                    f"{SEARXNG_URL}/search",
                    params={
                        "q": f"{code} stock news",
                        "format": "json",
                        "time_range": "week",
                    },
                    timeout=15,
                )
                resp.raise_for_status()
                data = resp.json()
                for r in data.get("results", [])[:max_results]:
                    all_articles.append({
                        "title": r.get("title", ""),
                        "summary": r.get("content", ""),
                        "url": r.get("url", ""),
                        "source": r.get("engine", "unknown"),
                        "date": r.get("publishedDate", ""),
                    })
            except Exception:
                pass
    
    if not all_articles:
        return f"No recent news found for stock {code}"
    
    # Deduplicate by title
    seen = set()
    unique = []
    for a in all_articles:
        if a["title"] not in seen:
            seen.add(a["title"])
            unique.append(a)
    
    # Format output
    header = f"# Recent News for {code}\n"
    header += f"# Data source: SearXNG (Chinese financial news)\n"
    header += f"# Total articles: {len(unique)}\n"
    header += f"# Retrieved: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    
    body = ""
    for i, a in enumerate(unique[:max_results], 1):
        body += f"## Article {i}: {a['title']}\n"
        if a["date"]:
            body += f"Date: {a['date']}\n"
        if a["source"]:
            body += f"Source: {a['source']}\n"
        if a["summary"]:
            body += f"Summary: {a['summary']}\n"
        if a["url"]:
            body += f"URL: {a['url']}\n"
        body += "\n"
    
    return header + body


def get_global_news_searxng(
    curr_date: Annotated[str, "current date"] = None,
    max_results: Annotated[int, "max articles"] = 10,
) -> str:
    """Get global Chinese financial news using SearXNG."""
    
    queries = [
        "A股 大盘 今日行情",
        "中国经济 最新消息",
        "股市 宏观经济",
    ]
    
    all_articles = []
    
    for query in queries:
        try:
            resp = requests.get(
                f"{SEARXNG_URL}/search",
                params={
                    "q": query,
                    "format": "json",
                    "categories": "news",
                    "language": "zh",
                    "time_range": "day",
                },
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            
            for r in data.get("results", [])[:5]:
                all_articles.append({
                    "title": r.get("title", ""),
                    "summary": r.get("content", ""),
                    "url": r.get("url", ""),
                    "source": r.get("engine", "unknown"),
                    "date": r.get("publishedDate", ""),
                })
        except Exception:
            continue
    
    if not all_articles:
        return "No recent global financial news available"
    
    # Deduplicate
    seen = set()
    unique = []
    for a in all_articles:
        if a["title"] not in seen:
            seen.add(a["title"])
            unique.append(a)
    
    header = f"# Global Financial News (Chinese Sources)\n"
    header += f"# Data source: SearXNG\n"
    header += f"# Total articles: {len(unique)}\n"
    header += f"# Retrieved: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    
    body = ""
    for i, a in enumerate(unique[:max_results], 1):
        body += f"## Article {i}: {a['title']}\n"
        if a["date"]:
            body += f"Date: {a['date']}\n"
        if a["summary"]:
            body += f"Summary: {a['summary']}\n"
        if a["url"]:
            body += f"URL: {a['url']}\n"
        body += "\n"
    
    return header + body
