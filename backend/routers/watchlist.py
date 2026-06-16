from fastapi import APIRouter
from db import rows, one

router = APIRouter()

SCHEMA = "options"


@router.get("/watchlist")
def get_watchlist():
    return rows(f"""
        SELECT DISTINCT ON (s.symbol)
            s.symbol,
            s.name,
            ds.stock_price::float,
            ds.stock_change_pct::float,
            ds.collect_date::text AS last_date
        FROM {SCHEMA}.symbols s
        LEFT JOIN {SCHEMA}.daily_summary ds ON s.symbol = ds.symbol
        WHERE s.is_active = TRUE
        ORDER BY s.symbol, ds.collect_date DESC NULLS LAST
    """)


@router.get("/sentiment/{symbol}")
def get_sentiment(symbol: str, date: str | None = None):
    if date:
        row = one(f"""
            SELECT oi_pc_ratio::float, vol_pc_ratio::float, stock_price::float,
                   collect_date::text
            FROM {SCHEMA}.daily_summary
            WHERE symbol = %s AND collect_date = %s
        """, (symbol, date))
    else:
        row = one(f"""
            SELECT oi_pc_ratio::float, vol_pc_ratio::float, stock_price::float,
                   collect_date::text
            FROM {SCHEMA}.daily_summary
            WHERE symbol = %s
            ORDER BY collect_date DESC
            LIMIT 1
        """, (symbol,))

    if not row:
        return {"pressure": None, "flow": None, "legacy": None}

    itm = one(f"""
        SELECT
            COUNT(*)::float AS total,
            SUM(CASE WHEN in_the_money THEN 1 ELSE 0 END)::float AS itm
        FROM {SCHEMA}.options_snapshots
        WHERE symbol = %s AND collect_date = %s AND side = 'put'
    """, (symbol, row["collect_date"]))

    oi_pc = row.get("oi_pc_ratio") or 0
    vol_pc = row.get("vol_pc_ratio") or 0

    if oi_pc >= 3.0:
        pressure = {"label": "极度空头压制", "val": f"oi_pc = {oi_pc:.2f}", "cls": "red"}
    elif oi_pc >= 1.5:
        pressure = {"label": "空头施压",     "val": f"oi_pc = {oi_pc:.2f}", "cls": "red"}
    elif oi_pc >= 1.0:
        pressure = {"label": "偏空",         "val": f"oi_pc = {oi_pc:.2f}", "cls": "yellow"}
    elif oi_pc >= 0.7:
        pressure = {"label": "中性",         "val": f"oi_pc = {oi_pc:.2f}", "cls": "yellow"}
    elif oi_pc >= 0.5:
        pressure = {"label": "偏多",         "val": f"oi_pc = {oi_pc:.2f}", "cls": "green"}
    else:
        pressure = {"label": "极度看多",     "val": f"oi_pc = {oi_pc:.2f}", "cls": "green"}

    if vol_pc < 0.1:
        flow = {"label": "强看多", "val": f"vol_pc = {vol_pc:.2f}", "cls": "green"}
    elif vol_pc < 0.5:
        flow = {"label": "看多",   "val": f"vol_pc = {vol_pc:.2f}", "cls": "green"}
    elif vol_pc < 1.0:
        flow = {"label": "偏多",   "val": f"vol_pc = {vol_pc:.2f}", "cls": "green"}
    elif vol_pc < 1.5:
        flow = {"label": "中性",   "val": f"vol_pc = {vol_pc:.2f}", "cls": "yellow"}
    elif vol_pc < 2.5:
        flow = {"label": "偏空",   "val": f"vol_pc = {vol_pc:.2f}", "cls": "red"}
    else:
        flow = {"label": "强看空", "val": f"vol_pc = {vol_pc:.2f}", "cls": "red"}

    if itm and itm["total"] and itm["total"] > 0:
        itm_pct = itm["itm"] / itm["total"] * 100
        if itm_pct > 80:
            legacy = {"label": "⚠ ITM Dominated", "val": f"{itm_pct:.1f}% puts ITM", "cls": "yellow"}
        else:
            legacy = {"label": "✓ Normal",         "val": f"OTM puts dominant",        "cls": "green"}
    else:
        legacy = {"label": "—", "val": "no data", "cls": "yellow"}

    return {"pressure": pressure, "flow": flow, "legacy": legacy}
