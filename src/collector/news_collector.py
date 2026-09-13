import os
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List

import requests

from src.db.connection import get_db_connection


def normalize_item(item: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize a raw news item into the project’s canonical schema.

    This function ensures consistent field names, default values, and timestamp
    handling so stories from different providers can be stored together.

    Args:
        item: A raw item dictionary from a source such as Reddit, X, or
            Facebook.

    Returns:
        A normalized dictionary with canonical source, title, URL, author,
        content, score, comment count, and published timestamp fields.
    """
    source = (item.get("source") or "reddit").strip().lower()
    if source not in {"reddit", "hacker_news", "rss", "x", "facebook"}:
        source = "rss"

    published_raw = item.get("published_at")
    if published_raw is None:
        published_at = datetime.now(timezone.utc)
    elif isinstance(published_raw, str):
        try:
            published_at = datetime.fromisoformat(published_raw.replace("Z", "+00:00"))
        except ValueError:
            published_at = datetime.now(timezone.utc)
    else:
        published_at = published_raw

    return {
        "source": source,
        "external_id": item.get("external_id") or item.get("id") or f"{source}-{datetime.now(timezone.utc).timestamp()}",
        "title": str(item.get("title") or "Untitled story").strip(),
        "url": str(item.get("url") or "https://example.invalid").strip(),
        "author": item.get("author"),
        "content": item.get("content") or item.get("summary") or "",
        "score": item.get("score"),
        "comment_count": item.get("comment_count"),
        "published_at": published_at,
    }


def collect_news_batch(items: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Normalize a batch of raw news items.

    Args:
        items: An iterable of raw item dictionaries representing a collection of
            articles or posts from one or more sources.

    Returns:
        A list of normalized items ready for insertion into the database.
    """
    normalized = []
    for item in items:
        normalized.append(normalize_item(item))
    return normalized


def _sample_news_items() -> List[Dict[str, Any]]:
    """Return deterministic fallback content for offline or credential-less runs.

    This provides a stable dataset for local development and testing when live
    API credentials are unavailable.

    Returns:
        A list of sample items representing common multi-source coverage.
    """
    return [
        {
            "source": "reddit",
            "external_id": "reddit-1",
            "title": "AI regulation proposal gathers support among policy groups",
            "url": "https://example.com/reddit/ai-regulation",
            "author": "news_club",
            "content": "Policy analysts say a proposed AI oversight framework may improve transparency while critics warn that it could slow down smaller startups.",
            "score": 420,
            "comment_count": 41,
            "published_at": "2026-09-13T07:30:00Z",
        },
        {
            "source": "x",
            "external_id": "x-1",
            "title": "AI regulation proposal gathers support among policy groups",
            "url": "https://example.com/x/ai-regulation",
            "author": "marketwatch",
            "content": "Investors and public advocates are framing the move as a step toward accountable governance. Some commentators argue the proposal is more optics than substance.",
            "score": 860,
            "comment_count": 58,
            "published_at": "2026-09-13T08:15:00Z",
        },
        {
            "source": "facebook",
            "external_id": "fb-1",
            "title": "AI regulation proposal gathers support among policy groups",
            "url": "https://example.com/facebook/ai-regulation",
            "author": "commmunitywire",
            "content": "Residents see the policy as a balancing act between safety and innovation, but local employers are concerned about compliance costs.",
            "score": 310,
            "comment_count": 19,
            "published_at": "2026-09-13T09:10:00Z",
        },
    ]


def _fetch_reddit() -> List[Dict[str, Any]]:
    """Fetch trending Reddit items when credentials are configured.

    If the app does not have a Reddit client id configured, this method returns a
    small sample dataset to keep the pipeline working in local or demo mode.

    Returns:
        A list of Reddit-style news items.
    """
    if not os.getenv("REDDIT_CLIENT_ID"):
        return _sample_news_items()[:1]

    response = requests.get(
        "https://www.reddit.com/r/worldnews/top.json?limit=5",
        timeout=10,
        headers={"User-Agent": "multi-agent-news-bot/0.1"},
    )
    response.raise_for_status()
    payload = response.json()
    items = []
    for entry in payload.get("data", {}).get("children", []):
        item = entry.get("data", {})
        items.append({
            "source": "reddit",
            "external_id": str(item.get("id")),
            "title": item.get("title"),
            "url": item.get("url"),
            "author": item.get("author"),
            "content": item.get("selftext") or item.get("title"),
            "score": item.get("score"),
            "comment_count": item.get("num_comments"),
            "published_at": item.get("created_utc"),
        })
    return items


def _fetch_x() -> List[Dict[str, Any]]:
    """Fetch recent X posts when a bearer token is configured.

    Returns:
        A list of X-style content items or a fallback sample item when the token
        is missing.
    """
    if not os.getenv("X_API_KEY"):
        return _sample_news_items()[1:2]

    response = requests.get(
        "https://api.x.com/2/tweets/search/recent?max_results=5",
        timeout=10,
        headers={"Authorization": f"Bearer {os.getenv('X_API_KEY')}"},
    )
    response.raise_for_status()
    payload = response.json()
    items = []
    for entry in payload.get("data", []):
        items.append({
            "source": "x",
            "external_id": entry.get("id"),
            "title": entry.get("text", "")[:100],
            "url": f"https://x.com/i/web/status/{entry.get('id')}",
            "author": "x_user",
            "content": entry.get("text"),
            "score": 0,
            "comment_count": 0,
            "published_at": entry.get("created_at"),
        })
    return items


def _fetch_facebook() -> List[Dict[str, Any]]:
    """Fetch recent Facebook feed items when app credentials are configured.

    Returns:
        A list of Facebook-like items or a stable fallback dataset.
    """
    if not os.getenv("FACEBOOK_APP_ID"):
        return _sample_news_items()[2:3]

    response = requests.get(
        "https://graph.facebook.com/v19.0/me/feed?limit=5",
        timeout=10,
        headers={"Authorization": f"Bearer {os.getenv('FACEBOOK_APP_ID')}"},
    )
    response.raise_for_status()
    payload = response.json()
    items = []
    for entry in payload.get("data", []):
        items.append({
            "source": "facebook",
            "external_id": entry.get("id"),
            "title": entry.get("message", "")[:100],
            "url": entry.get("permalink_url") or "https://facebook.com",
            "author": "facebook_user",
            "content": entry.get("message"),
            "score": 0,
            "comment_count": 0,
            "published_at": entry.get("created_time"),
        })
    return items


def fetch_news_from_sources() -> List[Dict[str, Any]]:
    """Collect headlines from all configured social sources.

    The function iterates through each source provider, ignores provider failures,
    and returns a normalized list of all successfully retrieved items.

    Returns:
        A list of normalized items collected from Reddit, X, and Facebook.
    """
    items: List[Dict[str, Any]] = []
    for provider in (_fetch_reddit, _fetch_x, _fetch_facebook):
        try:
            items.extend(provider())
        except Exception:
            continue
    return collect_news_batch(items)


def save_scraped_items(items: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Insert or update collected items into the scraped_items table.

    The function writes each normalized item to PostgreSQL and returns the saved
    records with their database ids attached for downstream processing.

    Args:
        items: A collection of normalized items ready to be persisted.

    Returns:
        The saved item records including generated database ids.
    """
    stored_items: List[Dict[str, Any]] = []
    with get_db_connection() as conn:
        for item in items:
            normalized = normalize_item(item)
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO scraped_items (
                        source, external_id, title, url, author, content, score, comment_count, published_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (source, external_id) DO UPDATE SET
                        title = EXCLUDED.title,
                        url = EXCLUDED.url,
                        author = EXCLUDED.author,
                        content = EXCLUDED.content,
                        score = EXCLUDED.score,
                        comment_count = EXCLUDED.comment_count,
                        published_at = EXCLUDED.published_at
                    RETURNING id
                    """,
                    (
                        normalized["source"],
                        normalized["external_id"],
                        normalized["title"],
                        normalized["url"],
                        normalized["author"],
                        normalized["content"],
                        normalized["score"],
                        normalized["comment_count"],
                        normalized["published_at"],
                    ),
                )
                result = cursor.fetchone()
                if result:
                    normalized["id"] = result[0]
                stored_items.append(normalized)
        conn.commit()
    return stored_items
