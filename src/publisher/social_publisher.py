import os
from datetime import datetime, timezone
from typing import Any, Dict

import requests


def publish_digest(digest: Dict[str, Any]) -> Dict[str, Any]:
    """Publish a generated digest to configured social platforms.

    The function checks for required platform credentials, attempts publication,
    and records the status of each channel so the system can report whether a
    digest was successfully shared or failed.

    Args:
        digest: A dictionary containing the generated digest title and content.

    Returns:
        A dictionary with the publication timestamp and platform-by-platform
        result states.
    """
    results = {
        "reddit": {"status": "pending", "url": None},
        "x": {"status": "pending", "url": None},
        "facebook": {"status": "pending", "url": None},
    }

    for platform in ("reddit", "x", "facebook"):
        token_name = {
            "reddit": "REDDIT_CLIENT_ID",
            "x": "X_API_KEY",
            "facebook": "FACEBOOK_APP_ID",
        }[platform]
        if not os.getenv(token_name):
            results[platform]["status"] = "failed"
            continue

        try:
            response = requests.post(
                "https://example.invalid/publish",
                timeout=10,
                json={"platform": platform, "text": digest["content"], "title": digest["title"]},
                headers={"Authorization": f"Bearer {os.getenv(token_name)}"},
            )
            response.raise_for_status()
            results[platform]["status"] = "published"
            results[platform]["url"] = response.json().get("url") or "https://example.invalid/published"
        except Exception:
            results[platform]["status"] = "failed"

    return {
        "published_at": datetime.now(timezone.utc).isoformat(),
        "platforms": results,
    }
