# Options Flow — Local Setup Guide

## Prerequisites

| Tool | Version | Notes |
|------|---------|-------|
| Python | 3.9+ | `python3 --version` |
| PostgreSQL | 14+ | Running locally or remote |
| Polygon API Key | Free tier | [polygon.io](https://polygon.io) — needed for historical data |

---

## 1. Install Dependencies

```bash
pip install -r requirements.txt
```

For the dashboard backend, also install Flask:

```bash
pip install flask flask-cors
```

---

## 2. Database Setup

### Connect to PostgreSQL and create the schema

```bash
psql -U your_user -d your_db -f schema.sql
```

This creates the `options` schema with all tables, indexes, and views including:
- `options_snapshots` — raw options chain data
- `daily_summary` — aggregated daily metrics
- `expiry_summary` — OI/volume by expiration
- `unusual_activity` — auto-detected alerts
- `v_daily_sentiment` — sentiment dashboard view

---

## 3. Environment Variables

Set these before running any script. Add to `~/.zshrc` or `~/.bashrc` for persistence.

```bash
# PostgreSQL
export PG_HOST=localhost
export PG_PORT=5432
export PG_DB=options
export PG_USER=your_user
export PG_PASSWORD=your_password

# Polygon.io (for historical data)
export POLYGON_API_KEY=your_key_here
```

Alternatively, use a single `DATABASE_URL`:

```bash
export DATABASE_URL=postgresql://your_user:your_password@localhost:5432/options
```

---

## 4. Scripts

### `put_call_analyzer.py` — Quick options chain snapshot
Fetches live options chain from Yahoo Finance (no API key needed) and exports CSVs.

```bash
python put_call_analyzer.py
```

**Output files:**
- `{SYMBOL}_options_chain.csv`
- `{SYMBOL}_pc_ratio_by_expiry.csv`
- `{SYMBOL}_daily_pc_ratio_*.csv`

---

### `options_collector_pg.py` — Daily collector (writes to PostgreSQL)
Fetches options chain via yfinance and persists snapshots to the database.

```bash
python options_collector_pg.py
```

Run this daily after market close. To schedule it:

```bash
# crontab -e
0 17 * * 1-5 cd /path/to/options-analysis && python options_collector_pg.py
```

---

### `historical_pc_ratio.py` — Historical P/C ratios via Polygon
Pulls per-contract daily bars to reconstruct historical put/call volume ratios.

```bash
export POLYGON_API_KEY=your_key
python historical_pc_ratio.py
```

> **Note:** Free tier is limited to 5 requests/minute. The script adds a 13-second delay between calls automatically.

---

### `options_data_fetcher-v2.py` — Bulk historical options data
Fetches historical options data via Polygon.io free tier.

```bash
python options_data_fetcher-v2.py
```

---

## 5. Dashboard

### Option A — Static (mock data, no backend needed)

Just open the file directly in your browser:

```bash
open dashboard.html
```

All charts render from embedded mock data. Use this to verify the UI layout.

---

### Option B — Live (connected to PostgreSQL)

**Step 1:** Create `backend.py` in the project root:

```python
from flask import Flask, jsonify
from flask_cors import CORS
import psycopg2, psycopg2.extras, os

app = Flask(__name__)
CORS(app)

def get_conn():
    url = os.environ.get("DATABASE_URL")
    if url:
        return psycopg2.connect(url)
    return psycopg2.connect(
        host=os.environ.get("PG_HOST", "localhost"),
        port=int(os.environ.get("PG_PORT", 5432)),
        dbname=os.environ.get("PG_DB", "options"),
        user=os.environ.get("PG_USER", "postgres"),
        password=os.environ.get("PG_PASSWORD", ""),
    )

@app.route("/api/sentiment/<symbol>")
def sentiment(symbol):
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SET search_path TO options, public;
                SELECT * FROM v_daily_sentiment
                WHERE symbol = %s ORDER BY collect_date DESC LIMIT 30
            """, (symbol.upper(),))
            return jsonify(cur.fetchall())

@app.route("/api/expiry/<symbol>")
def expiry(symbol):
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SET search_path TO options, public;
                SELECT * FROM expiry_summary
                WHERE symbol = %s
                AND collect_date = (SELECT MAX(collect_date) FROM expiry_summary WHERE symbol = %s)
                ORDER BY expiry
            """, (symbol.upper(), symbol.upper()))
            return jsonify(cur.fetchall())

@app.route("/api/unusual/<symbol>")
def unusual(symbol):
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SET search_path TO options, public;
                SELECT * FROM unusual_activity
                WHERE symbol = %s ORDER BY detect_date DESC LIMIT 50
            """, (symbol.upper(),))
            return jsonify(cur.fetchall())

@app.route("/api/top_oi/<symbol>")
def top_oi(symbol):
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SET search_path TO options, public;
                SELECT * FROM v_top_oi_contracts
                WHERE symbol = %s
                AND collect_date = (SELECT MAX(collect_date) FROM options_snapshots WHERE symbol = %s)
                ORDER BY oi_rank
            """, (symbol.upper(), symbol.upper()))
            return jsonify(cur.fetchall())

if __name__ == "__main__":
    app.run(port=5050, debug=True)
```

**Step 2:** Start the backend:

```bash
python backend.py
```

Backend runs at `http://localhost:5050`. Test it:

```bash
curl http://localhost:5050/api/sentiment/TIGR
curl http://localhost:5050/api/expiry/NIO
```

**Step 3:** Open the dashboard:

```bash
open dashboard.html
```

---

## 6. Verify Database Has Data

```sql
-- Connect
psql -U your_user -d your_db

-- Check data
SET search_path TO options, public;
SELECT symbol, COUNT(*), MIN(collect_date), MAX(collect_date)
FROM options_snapshots
GROUP BY symbol;

-- Check sentiment view
SELECT * FROM v_daily_sentiment ORDER BY collect_date DESC LIMIT 5;

-- Check unusual activity
SELECT * FROM unusual_activity ORDER BY detect_date DESC LIMIT 10;
```

---

## Project Structure

```
options-analysis/
├── schema.sql                        # PostgreSQL schema + views
├── requirements.txt                  # Python dependencies
├── dashboard.html                    # Frontend dashboard
│
├── put_call_analyzer.py              # Quick snapshot → CSV (yfinance)
├── options_collector_pg.py           # Daily collector → PostgreSQL
├── historical_pc_ratio.py            # Historical P/C via Polygon
├── options_data_fetcher-v2.py        # Bulk historical data
│
└── data/                             # CSV outputs
    ├── TIGR_options_chain.csv
    ├── NIO_options_chain.csv
    └── ...
```

---

## Troubleshooting

**`psycopg2` connection refused**
```bash
# Check PostgreSQL is running
pg_isready -h localhost -p 5432
# Start if needed (macOS)
brew services start postgresql
```

**`yfinance` returns empty data**
```bash
# yfinance occasionally rate-limits; wait 60s and retry
# Or test with a different symbol first
```

**Polygon free tier 429 errors**
The `historical_pc_ratio.py` script uses a 13-second delay between requests. If you still hit rate limits, increase `REQUEST_INTERVAL` to `15`.

**Schema not found**
```sql
-- Make sure schema was applied
\dn  -- list schemas, should show 'options'
SET search_path TO options, public;
\dt  -- list tables
```
