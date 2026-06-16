from datetime import date, timedelta
from fastapi import APIRouter
from db import rows, one

router = APIRouter()
SCHEMA = "options"


@router.get("/summary/{symbol}")
def get_summary(symbol: str, start: str | None = None, end: str | None = None):
    if not end:
        end = str(date.today())
    if not start:
        start = str(date.today() - timedelta(days=30))
    return rows(f"""
        SELECT
            collect_date::text,
            stock_price::float,
            stock_change_pct::float,
            total_call_oi,
            total_put_oi,
            oi_pc_ratio::float,
            total_call_volume,
            total_put_volume,
            vol_pc_ratio::float,
            avg_call_iv::float,
            avg_put_iv::float,
            max_call_oi_strike::float,
            max_put_oi_strike::float
        FROM {SCHEMA}.daily_summary
        WHERE symbol = %s AND collect_date BETWEEN %s AND %s
        ORDER BY collect_date
    """, (symbol, start, end))


@router.get("/moneyness/{symbol}")
def get_moneyness(symbol: str, date: str | None = None):
    if not date:
        row = one(f"SELECT MAX(collect_date)::text AS d FROM {SCHEMA}.daily_summary WHERE symbol = %s", (symbol,))
        date = row["d"] if row else None
    if not date:
        return {}

    price_row = one(f"SELECT stock_price::float FROM {SCHEMA}.daily_summary WHERE symbol=%s AND collect_date=%s", (symbol, date))
    price = price_row["stock_price"] if price_row else 0
    atm_low = price * 0.95
    atm_high = price * 1.05

    result = rows(f"""
        SELECT
            side,
            SUM(CASE WHEN in_the_money THEN open_interest ELSE 0 END) AS itm_oi,
            SUM(CASE WHEN NOT in_the_money
                          AND strike::float BETWEEN %s AND %s
                     THEN open_interest ELSE 0 END) AS atm_oi,
            SUM(CASE WHEN NOT in_the_money
                          AND (strike::float < %s OR strike::float > %s)
                     THEN open_interest ELSE 0 END) AS otm_oi
        FROM {SCHEMA}.options_snapshots
        WHERE symbol = %s AND collect_date = %s
        GROUP BY side
    """, (atm_low, atm_high, atm_low, atm_high, symbol, date))

    out = {}
    for r in result:
        out[r["side"]] = {
            "itm": int(r["itm_oi"] or 0),
            "atm": int(r["atm_oi"] or 0),
            "otm": int(r["otm_oi"] or 0),
        }
    return out
