import os
from decimal import Decimal
from datetime import date, datetime
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

DB_CONFIG = {
    "host":     os.environ.get("PG_HOST", "localhost"),
    "port":     int(os.environ.get("PG_PORT", 5432)),
    "dbname":   os.environ.get("PG_DB", "options"),
    "user":     os.environ.get("PG_USER"),
    "password": os.environ.get("PG_PASSWORD", ""),
}


def get_conn():
    url = os.environ.get("DATABASE_URL")
    if url:
        return psycopg2.connect(url, cursor_factory=RealDictCursor)
    return psycopg2.connect(**DB_CONFIG, cursor_factory=RealDictCursor)


def _cast(v):
    if isinstance(v, Decimal):
        return float(v)
    if isinstance(v, (date, datetime)):
        return str(v)
    return v


def rows(sql: str, params=None) -> list[dict]:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return [{k: _cast(v) for k, v in row.items()} for row in cur.fetchall()]


def one(sql: str, params=None) -> dict | None:
    result = rows(sql, params)
    return result[0] if result else None
