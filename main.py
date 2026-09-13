import json
import os
from datetime import datetime, timezone

from src.agents.news_agent import summarize_news
from src.collector.news_collector import fetch_news_from_sources, save_scraped_items
from src.db.connection import get_db_connection
from src.db.schema import load_schema_sql
from src.publisher.social_publisher import publish_digest


def ensure_database() -> None:
    with get_db_connection() as conn:
        conn.execute(load_schema_sql())
        conn.commit()


def run_pipeline() -> dict:
    ensure_database()
    items = fetch_news_from_sources()
    stored_items = save_scraped_items(items)

    digest = summarize_news(stored_items)

    with get_db_connection() as conn:
        conn.execute(
            """
            INSERT INTO digests (title, content, story_ids, llm_model, generated_at)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (
                digest["title"],
                digest["content"],
                digest["story_ids"],
                digest["llm_model"],
                datetime.now(timezone.utc),
            ),
        )
        conn.commit()

    publish_result = publish_digest(digest)

    return {
        "stored_items": len(stored_items),
        "digest": digest,
        "publish_result": publish_result,
    }


if __name__ == "__main__":
    print(json.dumps(run_pipeline(), default=str, indent=2))
