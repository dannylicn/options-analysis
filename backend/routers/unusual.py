from fastapi import APIRouter
from db import rows

router = APIRouter()
SCHEMA = "options"


@router.get("/unusual")
def get_unusual(symbol: str | None = None, days: int = 14):
    params: list = [days]
    where = f"detect_date >= CURRENT_DATE - %s"
    if symbol:
        where += " AND symbol = %s"
        params.append(symbol)
    return rows(f"""
        SELECT
            detect_date::text,
            symbol,
            alert_type,
            side,
            strike::float,
            expiry::text,
            current_value::float,
            previous_value::float,
            change_pct::float,
            description
        FROM {SCHEMA}.unusual_activity
        WHERE {where}
        ORDER BY detect_date DESC, created_at DESC
        LIMIT 100
    """, params)
