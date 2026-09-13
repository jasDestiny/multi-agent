SCHEMA_SQL = """
CREATE TABLE scraped_items (
    id              BIGSERIAL PRIMARY KEY,
    source          VARCHAR(20) NOT NULL
                    CHECK (source IN ('reddit', 'hacker_news', 'rss', 'x', 'facebook')),
    external_id     VARCHAR(255),
    title           TEXT NOT NULL,
    url             TEXT NOT NULL,
    author          TEXT,
    content         TEXT,
    score           INTEGER,
    comment_count   INTEGER,
    published_at    TIMESTAMPTZ,
    scraped_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE (source, external_id),
    UNIQUE (url)
);

CREATE INDEX idx_scraped_items_trending
    ON scraped_items (score DESC, published_at DESC);

CREATE TABLE digests (
    id              BIGSERIAL PRIMARY KEY,
    title           TEXT NOT NULL,
    content         TEXT NOT NULL,
    story_ids       BIGINT[] NOT NULL,
    llm_model       VARCHAR(100),
    generated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    reddit_status   VARCHAR(20) NOT NULL DEFAULT 'pending'
                    CHECK (reddit_status IN ('pending', 'published', 'failed')),
    reddit_post_url TEXT,

    discord_status  VARCHAR(20) NOT NULL DEFAULT 'pending'
                    CHECK (discord_status IN ('pending', 'published', 'failed')),
    discord_message_id VARCHAR(255),

    telegram_status VARCHAR(20) NOT NULL DEFAULT 'pending'
                    CHECK (telegram_status IN ('pending', 'published', 'failed')),
    telegram_message_id VARCHAR(255),

    publish_error   TEXT,
    published_at    TIMESTAMPTZ
);
"""


def load_schema_sql() -> str:
    """Return the SQL used to create the project’s application tables.

    Returns:
        A string containing the database schema for scraped_items and digests.
    """
    return SCHEMA_SQL
