import pytest

import main as app_module
import src.collector.news_collector as collector_module
import src.publisher.social_publisher as publisher_module
from src.agents.news_agent import summarize_news
from src.collector.news_collector import collect_news_batch, fetch_news_from_sources, normalize_item, save_scraped_items
from src.db.connection import get_database_url, get_db_connection
from src.db.schema import load_schema_sql
from src.publisher.social_publisher import publish_digest


class FakeCursor:
    def __init__(self, rows=None):
        self._rows = rows or [(1,)]

    def execute(self, *args, **kwargs):
        return None

    def fetchone(self):
        if self._rows:
            return self._rows.pop(0)
        return None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return False


class FakeConnection:
    def __init__(self, rows=None):
        self._rows = rows or [(1,)]

    def cursor(self):
        return FakeCursor(self._rows)

    def execute(self, *args, **kwargs):
        return None

    def commit(self):
        return None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return False


class FakeResponse:
    def __init__(self, payload=None):
        self.payload = payload or {"url": "https://example.com/published"}

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


def test_database_schema_includes_required_tables():
    sql = load_schema_sql()

    assert "CREATE TABLE scraped_items" in sql
    assert "CREATE TABLE digests" in sql
    assert "reddit_status" in sql
    assert "discord_status" in sql
    assert "telegram_status" in sql
    assert "UNIQUE (source, external_id)" in sql


def test_database_connection_uses_env_and_default(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@db:5432/app")
    assert get_database_url() == "postgresql://user:pass@db:5432/app"

    monkeypatch.delenv("DATABASE_URL", raising=False)
    url = get_database_url()
    assert "localhost" in url or "db:5432" in url

    monkeypatch.setattr("src.db.connection.psycopg.connect", lambda value: value)
    assert get_db_connection() == "postgresql://agent_user:hackathon_secure_password@localhost:5432/agent_data"


def test_collector_returns_standardized_news_items():
    sample_items = [
        {
            "source": "reddit",
            "external_id": "r1",
            "title": "AI policy update sparks debate",
            "url": "https://example.com/ai",
            "author": "alice",
            "content": "A new AI policy is causing discussion.",
            "score": 220,
            "comment_count": 45,
            "published_at": "2026-09-13T09:00:00Z",
        },
        {
            "source": "x",
            "external_id": "x1",
            "title": "AI policy update sparks debate",
            "url": "https://example.com/ai-x",
            "author": "bob",
            "content": "The policy is controversial.",
            "score": 800,
            "comment_count": 12,
            "published_at": "2026-09-13T10:00:00Z",
        },
    ]

    collected = collect_news_batch(sample_items)

    assert len(collected) == 2
    assert collected[0]["source"] in {"reddit", "x"}
    assert collected[0]["title"]
    assert collected[0]["url"]
    assert collected[0]["published_at"]


def test_normalize_item_handles_unknown_sources_and_missing_fields():
    item = {
        "source": "unknown",
        "title": "   Example story   ",
        "url": "",
        "content": None,
        "published_at": "not-a-date",
    }

    normalized = normalize_item(item)

    assert normalized["source"] == "rss"
    assert normalized["title"] == "Example story"
    assert normalized["url"] == "https://example.invalid"
    assert normalized["content"] == ""
    assert normalized["published_at"]


def test_fetch_news_from_sources_uses_provider_data(monkeypatch):
    monkeypatch.delenv("REDDIT_CLIENT_ID", raising=False)
    monkeypatch.delenv("X_API_KEY", raising=False)
    monkeypatch.delenv("FACEBOOK_APP_ID", raising=False)

    monkeypatch.setattr(collector_module, "_fetch_reddit", lambda: [{"source": "reddit", "external_id": "r1", "title": "A", "url": "https://example.com/a", "author": "a", "content": "A", "score": 1, "comment_count": 2, "published_at": "2026-09-13T00:00:00Z"}])
    monkeypatch.setattr(collector_module, "_fetch_x", lambda: [{"source": "x", "external_id": "x1", "title": "B", "url": "https://example.com/b", "author": "b", "content": "B", "score": 3, "comment_count": 4, "published_at": "2026-09-13T01:00:00Z"}])
    monkeypatch.setattr(collector_module, "_fetch_facebook", lambda: [{"source": "facebook", "external_id": "f1", "title": "C", "url": "https://example.com/c", "author": "c", "content": "C", "score": 5, "comment_count": 6, "published_at": "2026-09-13T02:00:00Z"}])

    items = fetch_news_from_sources()

    assert len(items) == 3
    assert {item["source"] for item in items} == {"reddit", "x", "facebook"}


def test_save_scraped_items_inserts_and_returns_ids(monkeypatch):
    fake_conn = FakeConnection(rows=[(7,)])
    monkeypatch.setattr(collector_module, "get_db_connection", lambda: fake_conn)

    items = [{
        "source": "reddit",
        "external_id": "r-7",
        "title": "Story seven",
        "url": "https://example.com/story7",
        "author": "author7",
        "content": "Text seven",
        "score": 70,
        "comment_count": 8,
        "published_at": "2026-09-13T08:00:00Z",
    }]

    saved = save_scraped_items(items)

    assert len(saved) == 1
    assert saved[0]["id"] == 7
    assert saved[0]["source"] == "reddit"


def test_agent_summarizes_multiple_sources_with_bias_and_facts():
    items = [
        {
            "id": 1,
            "title": "City launches clean-energy plan",
            "source": "reddit",
            "content": "Officials say the plan cuts emissions by 15%. Critics argue costs remain high.",
            "score": 10,
        },
        {
            "id": 2,
            "title": "City launches clean-energy plan",
            "source": "x",
            "content": "Analysts praise the policy while opponents warn of long-term costs.",
            "score": 25,
        },
        {
            "id": 3,
            "title": "City launches clean-energy plan",
            "source": "facebook",
            "content": "Residents are split; supporters cite resilience and jobs, skeptics focus on affordability.",
            "score": 15,
        },
    ]

    digest = summarize_news(items)

    assert digest["title"]
    assert "bias" in digest["content"].lower()
    assert "factual" in digest["content"].lower()
    assert digest["story_ids"] == [1, 2, 3]


def test_agent_raises_on_empty_news():
    with pytest.raises(ValueError):
        summarize_news([])


def test_publisher_fails_without_tokens(monkeypatch):
    for name in ["REDDIT_CLIENT_ID", "X_API_KEY", "FACEBOOK_APP_ID"]:
        monkeypatch.delenv(name, raising=False)

    result = publish_digest({"title": "Digest", "content": "Content"})

    assert result["platforms"]["reddit"]["status"] == "failed"
    assert result["platforms"]["x"]["status"] == "failed"
    assert result["platforms"]["facebook"]["status"] == "failed"


def test_publisher_success_when_tokens_are_present(monkeypatch):
    for name, value in {
        "REDDIT_CLIENT_ID": "reddit-token",
        "X_API_KEY": "x-token",
        "FACEBOOK_APP_ID": "facebook-token",
    }.items():
        monkeypatch.setenv(name, value)

    monkeypatch.setattr(publisher_module.requests, "post", lambda *args, **kwargs: FakeResponse({"url": "https://example.com/live"}))

    result = publish_digest({"title": "Digest", "content": "Content"})

    assert result["platforms"]["reddit"]["status"] == "published"
    assert result["platforms"]["x"]["status"] == "published"
    assert result["platforms"]["facebook"]["status"] == "published"
    assert result["platforms"]["reddit"]["url"] == "https://example.com/live"


def test_main_run_pipeline_uses_real_workflow(monkeypatch):
    calls = {}

    def fake_db_connection():
        return FakeConnection()

    def fake_fetch():
        calls["fetch"] = True
        return [{"source": "reddit", "external_id": "r1", "title": "A", "url": "https://example.com/a", "author": "a", "content": "A", "score": 1, "comment_count": 2, "published_at": "2026-09-13T00:00:00Z"}]

    def fake_save(items):
        calls["save"] = items
        return [{"id": 1, "source": "reddit", "title": "A", "url": "https://example.com/a", "author": "a", "content": "A", "score": 1, "comment_count": 2, "published_at": "2026-09-13T00:00:00Z"}]

    def fake_summarize(items):
        calls["summarize"] = items
        return {"title": "Digest title", "content": "Bias and factual review", "story_ids": [1], "llm_model": "mock-model"}

    def fake_publish(digest):
        calls["publish"] = digest
        return {"published_at": "2026-09-13T00:00:00Z", "platforms": {"reddit": {"status": "published", "url": "https://example.com/published"}}}

    monkeypatch.setattr(app_module, "get_db_connection", fake_db_connection)
    monkeypatch.setattr(app_module, "fetch_news_from_sources", fake_fetch)
    monkeypatch.setattr(app_module, "save_scraped_items", fake_save)
    monkeypatch.setattr(app_module, "summarize_news", fake_summarize)
    monkeypatch.setattr(app_module, "publish_digest", fake_publish)

    result = app_module.run_pipeline()

    assert result["stored_items"] == 1
    assert result["digest"]["title"] == "Digest title"
    assert result["publish_result"]["platforms"]["reddit"]["status"] == "published"
    assert calls["fetch"] is True
    assert calls["summarize"]
