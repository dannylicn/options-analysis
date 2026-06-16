from fastapi import APIRouter
from db import rows, one

router = APIRouter()
SCHEMA = "options"


@router.get("/expiry/{symbol}")
def get_expiry(symbol: str, date: str | None = None):
    if not date:
        row = one(f"SELECT MAX(collect_date)::text AS d FROM {SCHEMA}.expiry_summary WHERE symbol=%s", (symbol,))
        date = row["d"] if row else None
    if not date:
        return []
    return rows(f"""
        SELECT
            expiry::text,
            call_oi,
            put_oi,
            oi_pc_ratio::float,
            call_volume,
            put_volume,
            vol_pc_ratio::float,
            avg_call_iv::float,
            avg_put_iv::float,
            days_to_expiry
        FROM {SCHEMA}.expiry_summary
        WHERE symbol = %s AND collect_date = %s
        ORDER BY expiry
    """, (symbol, date))
