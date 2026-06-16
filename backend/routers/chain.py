from fastapi import APIRouter
from db import rows, one

router = APIRouter()
SCHEMA = "options"


@router.get("/chain/{symbol}")
def get_chain(symbol: str, date: str | None = None):
    if not date:
        row = one(f"SELECT MAX(collect_date)::text AS d FROM {SCHEMA}.options_snapshots WHERE symbol=%s", (symbol,))
        date = row["d"] if row else None
    if not date:
        return []
    return rows(f"""
        SELECT
            expiry::text,
            side,
            strike::float,
            open_interest,
            volume,
            ROUND((implied_volatility * 100)::numeric, 2)::float AS iv_pct,
            in_the_money,
            last_price::float,
            bid::float,
            ask::float
        FROM {SCHEMA}.options_snapshots
        WHERE symbol = %s AND collect_date = %s AND open_interest > 0
        ORDER BY expiry, strike, side
    """, (symbol, date))
