"""Chinese stock forum sentiment data from EastMoney Guba (东方财富股吧).

Scrapes post titles, view counts, and reply counts from the guba forum.
Performs simple keyword-based sentiment analysis.
"""

import os
import re
from datetime import datetime
from typing import Annotated

import requests

GUBA_BASE_URL = "https://guba.eastmoney.com"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
}

# Sentiment keywords
POSITIVE_KEYWORDS = [
    "加仓", "买入", "看好", "反弹", "上涨", "突破", "利好", "支持",
    "满上", "安心", "牛", "起飞", "暴涨", "涨停", "底部", "抄底",
    "持有", "坚定", "看多", "做多", "补仓", "建仓",
]
NEGATIVE_KEYWORDS = [
    "出货", "暴跌", "割肉", "逃命", "做空", "风险", "下跌", "破位",
    "止损", "清仓", "跑路", "套牢", "坑", "垃圾", "跌停", "崩盘",
    "看空", "减仓", "抛售", "踩雷", "暴雷", "烂",
]


def _extract_code(symbol: str) -> str:
    """Extract 6-digit code from symbol."""
    s = symbol.strip().upper()
    if "." in s:
        return s.split(".")[0]
    return s.replace("SH", "").replace("SZ", "")


def fetch_guba_posts(symbol: str, max_pages: int = 1) -> list[dict]:
    """Fetch posts from EastMoney Guba for a given stock.
    
    Returns list of dicts with keys: title, views, replies, time, author.
    """
    code = _extract_code(symbol)
    all_posts = []
    
    for page in range(1, max_pages + 1):
        if page == 1:
            url = f"{GUBA_BASE_URL}/list,{code}.html"
        else:
            url = f"{GUBA_BASE_URL}/list,{code}_{page}.html"
        
        try:
            resp = requests.get(url, headers=HEADERS, timeout=10)
            resp.encoding = "utf-8"
            html = resp.text
        except requests.RequestException:
            continue
        
        # Extract posts: read count, reply count, title
        pattern = (
            r'<div class="read">(\d+)</div></td>'
            r'<td><div class="reply">(\d+)</div></td>'
            r'<td><div class="title"><a[^>]*>(.*?)</a>'
        )
        matches = re.findall(pattern, html, re.DOTALL)
        
        for views, replies, title in matches:
            title = re.sub(r"<[^>]+>", "", title).strip()
            if title:
                all_posts.append({
                    "title": title,
                    "views": int(views),
                    "replies": int(replies),
                })
    
    return all_posts


def analyze_sentiment(posts: list[dict]) -> dict:
    """Analyze sentiment from post titles using keyword matching.
    
    Returns dict with: total_posts, total_views, total_replies,
    positive_count, negative_count, sentiment_ratio, top_posts.
    """
    if not posts:
        return {
            "total_posts": 0,
            "total_views": 0,
            "total_replies": 0,
            "positive_count": 0,
            "negative_count": 0,
            "sentiment_ratio": "N/A",
            "top_posts": [],
        }
    
    total_views = sum(p["views"] for p in posts)
    total_replies = sum(p["replies"] for p in posts)
    
    # Keyword-based sentiment
    pos_count = 0
    neg_count = 0
    for p in posts:
        title = p["title"]
        if any(w in title for w in POSITIVE_KEYWORDS):
            pos_count += 1
        if any(w in title for w in NEGATIVE_KEYWORDS):
            neg_count += 1
    
    # Top posts by engagement (views + replies * 10)
    sorted_posts = sorted(
        posts,
        key=lambda x: x["views"] + x["replies"] * 10,
        reverse=True,
    )
    top_posts = sorted_posts[:10]
    
    # Sentiment ratio
    total_sentiment = pos_count + neg_count
    if total_sentiment > 0:
        ratio = f"{pos_count}/{neg_count} ({pos_count/total_sentiment*100:.0f}%多/{neg_count/total_sentiment*100:.0f}%空)"
    else:
        ratio = "中性"
    
    return {
        "total_posts": len(posts),
        "total_views": total_views,
        "total_replies": total_replies,
        "positive_count": pos_count,
        "negative_count": neg_count,
        "sentiment_ratio": ratio,
        "top_posts": top_posts,
    }


def get_guba_sentiment(
    symbol: Annotated[str, "ticker symbol"],
    max_pages: Annotated[int, "max pages to scrape"] = 1,
) -> str:
    """Get stock forum sentiment from EastMoney Guba.
    
    Returns formatted text with sentiment analysis results.
    """
    code = _extract_code(symbol)
    
    posts = fetch_guba_posts(symbol, max_pages=max_pages)
    if not posts:
        return f"东方财富股吧未找到 {code} 的帖子数据"
    
    analysis = analyze_sentiment(posts)
    
    # Format output
    header = f"# 东方财富股吧情绪分析: {code}\n"
    header += f"# 数据来源: guba.eastmoney.com\n"
    header += f"# 分析时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    
    header += "## 概览\n"
    header += f"- 总帖子数: {analysis['total_posts']}\n"
    header += f"- 总阅读量: {analysis['total_views']:,}\n"
    header += f"- 总评论数: {analysis['total_replies']:,}\n"
    header += f"- 多空比: {analysis['sentiment_ratio']}\n\n"
    
    header += "## 热门帖子（按互动量排序）\n"
    for i, p in enumerate(analysis["top_posts"], 1):
        header += f"{i}. [{p['views']}阅读/{p['replies']}评论] {p['title']}\n"
    
    header += "\n## 全部帖子标题\n"
    for i, p in enumerate(posts, 1):
        header += f"{i}. {p['title']}\n"
    
    return header


def get_guba_sentiment_for_llm(symbol: str) -> str:
    """Get guba sentiment formatted for LLM prompt injection.
    
    Returns concise summary suitable for sentiment analyst prompt.
    """
    code = _extract_code(symbol)
    
    posts = fetch_guba_posts(symbol, max_pages=1)
    if not posts:
        return f"东方财富股吧: 无数据"
    
    analysis = analyze_sentiment(posts)
    
    result = f"东方财富股吧 ({code}) - {analysis['total_posts']}条帖子\n"
    result += f"阅读量: {analysis['total_views']:,}, 评论: {analysis['total_replies']:,}\n"
    result += f"多空关键词比: {analysis['sentiment_ratio']}\n\n"
    
    result += "热门帖子:\n"
    for i, p in enumerate(analysis["top_posts"][:5], 1):
        result += f"  {i}. [{p['views']}阅读] {p['title']}\n"
    
    return result
