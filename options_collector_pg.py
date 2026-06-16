"""
期权数据每日采集器 (PostgreSQL 版)
===================================
每天收盘后运行, 用 yfinance 采集期权链快照, 存入 PostgreSQL.

安装: pip install yfinance pandas psycopg2-binary
配置: 设置环境变量或修改下方 DB 配置
运行: python options_collector_pg.py
定时: crontab -e (见文件末尾)
"""

import yfinance as yf
import pandas as pd
import psycopg2
from psycopg2.extras import execute_values
import os
import sys
import math
import time
import warnings
from datetime import datetime, date
from dotenv import load_dotenv

warnings.filterwarnings("ignore")

load_dotenv()

# ============================================================
# 配置
# ============================================================
WATCHLIST = ["NIO", "TIGR"]

# PostgreSQL 连接 (优先用环境变量)
DB_CONFIG = {
    "host":     os.environ.get("PG_HOST", "localhost"),
    "port":     int(os.environ.get("PG_PORT", 5432)),
    "dbname":   os.environ.get("PG_DB", "options"),
    "user":     os.environ.get("PG_USER"),
    "password": os.environ.get("PG_PASSWORD"),
}

# 也支持 DATABASE_URL 格式 (如 Supabase, Railway 等)
DATABASE_URL = os.environ.get("DATABASE_URL", None)

SCHEMA = "options"
LOG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "collector_pg.log")


def log(msg):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {msg}"
    print(line)
    with open(LOG_PATH, "a") as f:
        f.write(line + "\n")


def get_conn():
    """获取数据库连接"""
    if DATABASE_URL:
        return psycopg2.connect(DATABASE_URL)
    else:
        return psycopg2.connect(**DB_CONFIG)


def safe_val(val, default=None):
    if val is None:
        return default
    if isinstance(val, float) and (math.isnan(val) or math.isinf(val)):
        return default
    return val


def safe_int(val):
    v = safe_val(val, 0)
    return int(v) if v is not None else 0


def safe_float(val):
    v = safe_val(val, None)
    return float(v) if v is not None else None


# ============================================================
# 采集逻辑
# ============================================================
def collect_stock_price(ticker_obj, symbol, conn, collect_date):
    """采集并存储当日股价"""
    try:
        hist = ticker_obj.history(period="5d")
        if len(hist) == 0:
            return None
        
        latest = hist.iloc[-1]
        price_data = {
            "open": safe_float(latest.get("Open")),
            "high": safe_float(latest.get("High")),
            "low": safe_float(latest.get("Low")),
            "close": safe_float(latest.get("Close")),
            "volume": safe_int(latest.get("Volume")),
        }
        
        with conn.cursor() as cur:
            cur.execute(f"""
                INSERT INTO {SCHEMA}.stock_prices 
                    (symbol, trade_date, open, high, low, close, volume)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (symbol, trade_date) 
                DO UPDATE SET open=%s, high=%s, low=%s, close=%s, volume=%s
            """, (symbol, collect_date,
                  price_data["open"], price_data["high"], price_data["low"],
                  price_data["close"], price_data["volume"],
                  price_data["open"], price_data["high"], price_data["low"],
                  price_data["close"], price_data["volume"]))
        
        return price_data["close"]
    except Exception as e:
        log(f"    [警告] 股价采集失败: {e}")
        return None


def collect_options_chain(ticker_obj, symbol, conn, collect_date):
    """采集完整期权链并写入数据库"""
    
    try:
        expirations = ticker_obj.options
    except Exception as e:
        log(f"    [错误] 获取到期日失败: {e}")
        return None
    
    if not expirations:
        log(f"    [警告] 无可用期权")
        return None
    
    log(f"    到期日: {len(expirations)} 个 ({expirations[0]} ~ {expirations[-1]})")
    
    # 逐个到期日拉取
    snapshot_rows = []
    expiry_stats = []
    
    for exp in expirations:
        try:
            chain = ticker_obj.option_chain(exp)
        except Exception as e:
            log(f"    [警告] {exp} 失败: {e}")
            continue
        
        exp_call_oi = 0
        exp_put_oi = 0
        exp_call_vol = 0
        exp_put_vol = 0
        exp_call_iv_sum = 0
        exp_put_iv_sum = 0
        
        days_to_exp = (datetime.strptime(exp, "%Y-%m-%d").date() - 
                       datetime.strptime(collect_date, "%Y-%m-%d").date()).days
        
        for side_name, data in [("call", chain.calls), ("put", chain.puts)]:
            for _, row in data.iterrows():
                oi = safe_int(row.get("openInterest"))
                vol = safe_int(row.get("volume"))
                iv = safe_float(row.get("impliedVolatility")) or 0
                
                snapshot_rows.append((
                    collect_date, symbol, row.get("contractSymbol", ""),
                    exp, side_name, float(row.get("strike", 0)),
                    safe_float(row.get("lastPrice")),
                    safe_float(row.get("bid")),
                    safe_float(row.get("ask")),
                    vol, oi, iv,
                    bool(row.get("inTheMoney", False)),
                    days_to_exp,
                ))
                
                if side_name == "call":
                    exp_call_oi += oi
                    exp_call_vol += vol
                    exp_call_iv_sum += iv * oi
                else:
                    exp_put_oi += oi
                    exp_put_vol += vol
                    exp_put_iv_sum += iv * oi
        
        # 按到期日的汇总
        avg_c_iv = round(exp_call_iv_sum / exp_call_oi * 100, 2) if exp_call_oi > 0 else None
        avg_p_iv = round(exp_put_iv_sum / exp_put_oi * 100, 2) if exp_put_oi > 0 else None
        
        expiry_stats.append((
            symbol, collect_date, exp,
            exp_call_oi, exp_put_oi,
            round(exp_put_oi / exp_call_oi, 4) if exp_call_oi > 0 else None,
            exp_call_vol, exp_put_vol,
            round(exp_put_vol / exp_call_vol, 4) if exp_call_vol > 0 else None,
            avg_c_iv, avg_p_iv, days_to_exp,
        ))
    
    if not snapshot_rows:
        log(f"    [警告] 未获取到数据")
        return None
    
    # 批量写入 options_snapshots
    with conn.cursor() as cur:
        execute_values(cur, f"""
            INSERT INTO {SCHEMA}.options_snapshots 
                (collect_date, symbol, contract_symbol, expiry, side, strike,
                 last_price, bid, ask, volume, open_interest, implied_volatility,
                 in_the_money, days_to_expiry)
            VALUES %s
            ON CONFLICT (collect_date, contract_symbol) DO UPDATE SET
                last_price = EXCLUDED.last_price,
                bid = EXCLUDED.bid,
                ask = EXCLUDED.ask,
                volume = EXCLUDED.volume,
                open_interest = EXCLUDED.open_interest,
                implied_volatility = EXCLUDED.implied_volatility,
                in_the_money = EXCLUDED.in_the_money
        """, snapshot_rows)
        
        inserted = cur.rowcount
    
    # 写入 expiry_summary
    with conn.cursor() as cur:
        execute_values(cur, f"""
            INSERT INTO {SCHEMA}.expiry_summary
                (symbol, collect_date, expiry, call_oi, put_oi, oi_pc_ratio,
                 call_volume, put_volume, vol_pc_ratio, avg_call_iv, avg_put_iv,
                 days_to_expiry)
            VALUES %s
            ON CONFLICT (symbol, collect_date, expiry) DO UPDATE SET
                call_oi = EXCLUDED.call_oi,
                put_oi = EXCLUDED.put_oi,
                oi_pc_ratio = EXCLUDED.oi_pc_ratio,
                call_volume = EXCLUDED.call_volume,
                put_volume = EXCLUDED.put_volume,
                vol_pc_ratio = EXCLUDED.vol_pc_ratio,
                avg_call_iv = EXCLUDED.avg_call_iv,
                avg_put_iv = EXCLUDED.avg_put_iv
        """, expiry_stats)
    
    log(f"    写入 {inserted} 条快照, {len(expiry_stats)} 个到期日汇总")
    
    return snapshot_rows


def compute_and_store_summary(symbol, conn, collect_date, stock_price):
    """从快照数据计算并写入每日汇总"""
    
    with conn.cursor() as cur:
        # 计算汇总
        cur.execute(f"""
            SELECT 
                side,
                SUM(open_interest) AS total_oi,
                SUM(volume) AS total_vol,
                CASE WHEN SUM(open_interest) > 0 
                    THEN SUM(implied_volatility * open_interest) / SUM(open_interest) * 100 
                    ELSE NULL 
                END AS weighted_avg_iv,
                COUNT(*) AS cnt
            FROM {SCHEMA}.options_snapshots
            WHERE symbol = %s AND collect_date = %s
            GROUP BY side
        """, (symbol, collect_date))
        
        rows = cur.fetchall()
        
        call_oi = 0; put_oi = 0
        call_vol = 0; put_vol = 0
        call_iv = None; put_iv = None
        total_contracts = 0
        
        for row in rows:
            side, oi, vol, iv, cnt = row
            total_contracts += cnt
            if side == "call":
                call_oi = int(oi or 0)
                call_vol = int(vol or 0)
                call_iv = round(float(iv), 2) if iv else None
            else:
                put_oi = int(oi or 0)
                put_vol = int(vol or 0)
                put_iv = round(float(iv), 2) if iv else None
        
        oi_pc = round(put_oi / call_oi, 4) if call_oi > 0 else None
        vol_pc = round(put_vol / call_vol, 4) if call_vol > 0 else None
        
        # 最大 OI 行权价
        cur.execute(f"""
            SELECT strike FROM {SCHEMA}.options_snapshots
            WHERE symbol = %s AND collect_date = %s AND side = 'call'
            ORDER BY open_interest DESC LIMIT 1
        """, (symbol, collect_date))
        max_call_strike = cur.fetchone()
        max_call_strike = float(max_call_strike[0]) if max_call_strike else None
        
        cur.execute(f"""
            SELECT strike FROM {SCHEMA}.options_snapshots
            WHERE symbol = %s AND collect_date = %s AND side = 'put'
            ORDER BY open_interest DESC LIMIT 1
        """, (symbol, collect_date))
        max_put_strike = cur.fetchone()
        max_put_strike = float(max_put_strike[0]) if max_put_strike else None
        
        # 计算股价日变化
        stock_change = None
        cur.execute(f"""
            SELECT stock_price FROM {SCHEMA}.daily_summary
            WHERE symbol = %s AND collect_date < %s
            ORDER BY collect_date DESC LIMIT 1
        """, (symbol, collect_date))
        prev = cur.fetchone()
        if prev and prev[0] and stock_price:
            stock_change = round((stock_price - float(prev[0])) / float(prev[0]) * 100, 4)
        
        # 到期日数量
        cur.execute(f"""
            SELECT COUNT(DISTINCT expiry) FROM {SCHEMA}.options_snapshots
            WHERE symbol = %s AND collect_date = %s
        """, (symbol, collect_date))
        total_expiries = cur.fetchone()[0]
        
        # 写入汇总
        cur.execute(f"""
            INSERT INTO {SCHEMA}.daily_summary
                (symbol, collect_date, stock_price, stock_change_pct,
                 total_call_oi, total_put_oi, oi_pc_ratio,
                 total_call_volume, total_put_volume, vol_pc_ratio,
                 avg_call_iv, avg_put_iv,
                 max_call_oi_strike, max_put_oi_strike,
                 total_contracts, total_expiries)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (symbol, collect_date) DO UPDATE SET
                stock_price = EXCLUDED.stock_price,
                stock_change_pct = EXCLUDED.stock_change_pct,
                total_call_oi = EXCLUDED.total_call_oi,
                total_put_oi = EXCLUDED.total_put_oi,
                oi_pc_ratio = EXCLUDED.oi_pc_ratio,
                total_call_volume = EXCLUDED.total_call_volume,
                total_put_volume = EXCLUDED.total_put_volume,
                vol_pc_ratio = EXCLUDED.vol_pc_ratio,
                avg_call_iv = EXCLUDED.avg_call_iv,
                avg_put_iv = EXCLUDED.avg_put_iv,
                max_call_oi_strike = EXCLUDED.max_call_oi_strike,
                max_put_oi_strike = EXCLUDED.max_put_oi_strike,
                total_contracts = EXCLUDED.total_contracts,
                total_expiries = EXCLUDED.total_expiries
        """, (symbol, collect_date, stock_price, stock_change,
              call_oi, put_oi, oi_pc, call_vol, put_vol, vol_pc,
              call_iv, put_iv, max_call_strike, max_put_strike,
              total_contracts, total_expiries))
    
    log(f"    汇总: Call OI={call_oi:,} Put OI={put_oi:,} "
        f"P/C={oi_pc} IV(C/P)={call_iv}/{put_iv}%")


def log_collection(conn, collect_date, symbol, status, count, duration, error=None):
    """记录采集日志"""
    with conn.cursor() as cur:
        cur.execute(f"""
            INSERT INTO {SCHEMA}.collection_log
                (collect_date, symbol, status, contracts_count, duration_secs, error_message)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (collect_date, symbol, status, count, duration, error))


def detect_unusual_activity(conn, symbol, collect_date):
    """检测异常活动 (OI 或 Volume 突变)"""
    with conn.cursor() as cur:
        # 比较今天 vs 前一天的 OI
        cur.execute(f"""
            SELECT 
                curr.total_call_oi, curr.total_put_oi, curr.oi_pc_ratio,
                prev.total_call_oi, prev.total_put_oi, prev.oi_pc_ratio,
                curr.avg_call_iv, prev.avg_call_iv
            FROM {SCHEMA}.daily_summary curr
            LEFT JOIN (
                SELECT * FROM {SCHEMA}.daily_summary 
                WHERE symbol = %s AND collect_date < %s 
                ORDER BY collect_date DESC LIMIT 1
            ) prev ON curr.symbol = prev.symbol
            WHERE curr.symbol = %s AND curr.collect_date = %s
        """, (symbol, collect_date, symbol, collect_date))
        
        row = cur.fetchone()
        if not row or row[3] is None:
            return  # 没有前一天的数据, 跳过
        
        curr_call_oi, curr_put_oi, curr_pc = row[0], row[1], row[2]
        prev_call_oi, prev_put_oi, prev_pc = row[3], row[4], row[5]
        curr_iv, prev_iv = row[6], row[7]
        
        alerts = []
        
        # Put OI 暴增 > 50%
        if prev_put_oi > 0 and curr_put_oi > 0:
            put_change = (curr_put_oi - prev_put_oi) / prev_put_oi * 100
            if abs(put_change) > 50:
                alerts.append(("oi_spike", "put", put_change, curr_put_oi, prev_put_oi,
                    f"Put OI {'暴增' if put_change > 0 else '暴降'} {put_change:.1f}%"))
        
        # Call OI 暴增 > 50%
        if prev_call_oi > 0 and curr_call_oi > 0:
            call_change = (curr_call_oi - prev_call_oi) / prev_call_oi * 100
            if abs(call_change) > 50:
                alerts.append(("oi_spike", "call", call_change, curr_call_oi, prev_call_oi,
                    f"Call OI {'暴增' if call_change > 0 else '暴降'} {call_change:.1f}%"))
        
        # P/C Ratio 极端值
        if curr_pc is not None:
            if curr_pc > 2.0:
                alerts.append(("pc_ratio_extreme", None, None, curr_pc, prev_pc,
                    f"P/C Ratio 极度偏空: {curr_pc:.3f}"))
            elif curr_pc < 0.3:
                alerts.append(("pc_ratio_extreme", None, None, curr_pc, prev_pc,
                    f"P/C Ratio 极度偏多: {curr_pc:.3f}"))
        
        # IV 暴涨 > 30%
        if prev_iv and curr_iv and prev_iv > 0:
            iv_change = (curr_iv - prev_iv) / prev_iv * 100
            if iv_change > 30:
                alerts.append(("iv_spike", None, iv_change, curr_iv, prev_iv,
                    f"IV 暴涨 {iv_change:.1f}% ({prev_iv:.1f}% -> {curr_iv:.1f}%)"))
        
        # 写入异常记录
        for alert in alerts:
            alert_type, side, change, curr_val, prev_val, desc = alert
            cur.execute(f"""
                INSERT INTO {SCHEMA}.unusual_activity
                    (detect_date, symbol, alert_type, side, 
                     current_value, previous_value, change_pct, description)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (collect_date, symbol, alert_type, side,
                  curr_val, prev_val, change, desc))
            log(f"    [异常] {desc}")


# ============================================================
# 主入口
# ============================================================
def collect_all():
    """采集所有 watchlist"""
    collect_date = date.today().strftime("%Y-%m-%d")
    
    log(f"{'='*50}")
    log(f"开始采集 | 日期: {collect_date} | 标的: {', '.join(WATCHLIST)}")
    log(f"{'='*50}")
    
    conn = get_conn()
    conn.autocommit = False
    
    success = 0
    
    for symbol in WATCHLIST:
        start_time = time.time()
        try:
            log(f"\n  采集 {symbol}...")
            ticker = yf.Ticker(symbol)
            
            # 股价
            stock_price = collect_stock_price(ticker, symbol, conn, collect_date)
            log(f"    股价: ${stock_price:.2f}" if stock_price else "    股价: 无数据")
            
            # 期权链
            result = collect_options_chain(ticker, symbol, conn, collect_date)
            
            if result:
                # 汇总
                compute_and_store_summary(symbol, conn, collect_date, stock_price)
                
                # 异常检测
                detect_unusual_activity(conn, symbol, collect_date)
                
                duration = round(time.time() - start_time, 2)
                log_collection(conn, collect_date, symbol, "success", len(result), duration)
                conn.commit()
                success += 1
            else:
                duration = round(time.time() - start_time, 2)
                log_collection(conn, collect_date, symbol, "failed", 0, duration, "无数据")
                conn.commit()
                
        except Exception as e:
            duration = round(time.time() - start_time, 2)
            log(f"    [异常] {e}")
            conn.rollback()
            try:
                log_collection(conn, collect_date, symbol, "failed", 0, duration, str(e))
                conn.commit()
            except:
                pass
    
    conn.close()
    log(f"\n采集完成: {success}/{len(WATCHLIST)} 成功")
    log(f"{'='*50}\n")


def print_history(symbol, start_date=None, end_date=None):
    """打印历史趋势"""
    conn = get_conn()
    
    query = f"SELECT * FROM {SCHEMA}.v_daily_sentiment WHERE symbol = %s"
    params = [symbol]
    
    if start_date:
        query += " AND collect_date >= %s"
        params.append(start_date)
    if end_date:
        query += " AND collect_date <= %s"
        params.append(end_date)
    
    query += " ORDER BY collect_date"
    
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    
    if len(df) == 0:
        print(f"无 {symbol} 的历史数据. 先运行 collect 采集几天.")
        return
    
    print(f"\n{'='*90}")
    print(f"  {symbol} 历史情绪趋势 ({len(df)} 天)")
    print(f"{'='*90}")
    print(f"\n  {'日期':<12} {'股价':>8} {'涨跌%':>7} {'OI P/C':>8} {'Vol P/C':>8} {'Call IV':>8} {'Put IV':>8} {'情绪':<10} {'事件':<20}")
    print(f"  {'-'*100}")
    
    for _, row in df.iterrows():
        price = f"${row['stock_price']:.2f}" if pd.notna(row['stock_price']) else "---"
        chg = f"{row['stock_change_pct']:+.2f}%" if pd.notna(row['stock_change_pct']) else "---"
        oi_pc = f"{row['oi_pc_ratio']:.3f}" if pd.notna(row['oi_pc_ratio']) else "---"
        vol_pc = f"{row['vol_pc_ratio']:.3f}" if pd.notna(row['vol_pc_ratio']) else "---"
        c_iv = f"{row['avg_call_iv']:.1f}%" if pd.notna(row['avg_call_iv']) else "---"
        p_iv = f"{row['avg_put_iv']:.1f}%" if pd.notna(row['avg_put_iv']) else "---"
        sentiment = row.get('sentiment', '---')
        event = row.get('event_title', '') or ''
        
        print(f"  {row['collect_date']:<12} {price:>8} {chg:>7} {oi_pc:>8} {vol_pc:>8} {c_iv:>8} {p_iv:>8} {sentiment:<10} {event[:20]}")


def print_unusual(symbol=None, days=7):
    """打印近期异常活动"""
    conn = get_conn()
    
    query = f"""
        SELECT detect_date, symbol, alert_type, description
        FROM {SCHEMA}.unusual_activity
        WHERE detect_date >= CURRENT_DATE - %s
    """
    params = [days]
    
    if symbol:
        query += " AND symbol = %s"
        params.append(symbol)
    
    query += " ORDER BY detect_date DESC, symbol"
    
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    
    if len(df) == 0:
        print("近期无异常活动")
        return
    
    print(f"\n{'='*70}")
    print(f"  近 {days} 天异常活动 ({len(df)} 条)")
    print(f"{'='*70}")
    for _, row in df.iterrows():
        print(f"  {row['detect_date']} | {row['symbol']:<6} | {row['alert_type']:<18} | {row['description']}")


def db_stats():
    """数据库统计"""
    conn = get_conn()
    cur = conn.cursor()
    
    cur.execute(f"SELECT COUNT(*) FROM {SCHEMA}.options_snapshots")
    total_rows = cur.fetchone()[0]
    
    cur.execute(f"SELECT COUNT(DISTINCT collect_date) FROM {SCHEMA}.daily_summary")
    total_days = cur.fetchone()[0]
    
    cur.execute(f"""
        SELECT symbol, COUNT(DISTINCT collect_date) AS days, 
               MIN(collect_date) AS first_date, MAX(collect_date) AS last_date
        FROM {SCHEMA}.daily_summary 
        GROUP BY symbol ORDER BY symbol
    """)
    symbols = cur.fetchall()
    
    print(f"\n{'='*50}")
    print(f"  数据库统计")
    print(f"{'='*50}")
    print(f"  总快照记录: {total_rows:,}")
    print(f"  采集天数:   {total_days}")
    print(f"\n  {'标的':<8} {'天数':>6} {'起始日期':<12} {'最近日期':<12}")
    print(f"  {'-'*40}")
    for s in symbols:
        print(f"  {s[0]:<8} {s[1]:>6} {s[2]!s:<12} {s[3]!s:<12}")
    
    # 异常活动统计
    cur.execute(f"SELECT COUNT(*) FROM {SCHEMA}.unusual_activity")
    alerts = cur.fetchone()[0]
    print(f"\n  累计异常活动: {alerts} 条")
    
    conn.close()


# ============================================================
# CLI
# ============================================================
if __name__ == "__main__":
    
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        
        if cmd == "collect":
            collect_all()
        
        elif cmd == "history":
            sym = sys.argv[2] if len(sys.argv) > 2 else "NIO"
            s = sys.argv[3] if len(sys.argv) > 3 else None
            e = sys.argv[4] if len(sys.argv) > 4 else None
            print_history(sym, s, e)
        
        elif cmd == "unusual":
            sym = sys.argv[2] if len(sys.argv) > 2 else None
            days = int(sys.argv[3]) if len(sys.argv) > 3 else 7
            print_unusual(sym, days)
        
        elif cmd == "stats":
            db_stats()
        
        elif cmd == "export":
            sym = sys.argv[2] if len(sys.argv) > 2 else "NIO"
            conn = get_conn()
            df = pd.read_sql_query(
                f"SELECT * FROM {SCHEMA}.daily_summary WHERE symbol = %s ORDER BY collect_date",
                conn, params=[sym])
            conn.close()
            fname = f"{sym}_history_export.csv"
            df.to_csv(fname, index=False)
            print(f"已导出: {fname} ({len(df)} 行)")
        
        else:
            print(f"未知命令: {cmd}")
            print("可用: collect, history, unusual, stats, export")
    
    else:
        collect_all()
        print()
        db_stats()
        
        for symbol in WATCHLIST:
            print_history(symbol)
        
        print_unusual()
        
        print(f"""
{'='*60}
使用说明:
{'='*60}

数据库连接 (二选一):
  方式1 - 环境变量:
    export PG_HOST=localhost
    export PG_PORT=5432
    export PG_DB=options
    export PG_USER=postgres
    export PG_PASSWORD=your_password

  方式2 - DATABASE_URL:
    export DATABASE_URL="postgresql://user:pass@host:5432/dbname"

命令:
  python options_collector_pg.py collect              # 采集
  python options_collector_pg.py history NIO           # 查看历史
  python options_collector_pg.py history TIGR 2026-05-01 2026-05-31
  python options_collector_pg.py unusual               # 查看异常活动
  python options_collector_pg.py unusual TIGR 14       # TIGR近14天异常
  python options_collector_pg.py stats                 # 数据库统计
  python options_collector_pg.py export NIO            # 导出CSV

Cronjob (新加坡时间, 美东收盘后):
  30 4 * * 2-6 cd /你的路径 && python options_collector_pg.py collect

建库:
  先运行 schema.sql 创建表结构:
    psql -U postgres -d options -f schema.sql
  
  然后运行本脚本开始采集:
    python options_collector_pg.py collect
""")
