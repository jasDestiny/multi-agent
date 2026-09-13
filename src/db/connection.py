import os

import psycopg


def get_database_url() -> str:
    """Return the configured PostgreSQL connection string.

    The value is read from the environment when available; otherwise the default
    local Docker-compatible URL is used for development.

    Returns:
        A PostgreSQL connection string.
    """
    return os.getenv("DATABASE_URL", "postgresql://agent_user:hackathon_secure_password@localhost:5432/agent_data")


def get_db_connection():
    """Open a PostgreSQL connection using the configured environment settings.

    Returns:
        A psycopg database connection object.
    """
    return psycopg.connect(get_database_url())
