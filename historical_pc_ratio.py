"""
历史 Put/Call Volume Ratio 分析器
==================================
用 Polygon 免费 tier 拉取上周每个期权合约的日K线,
还原每天的 Put/Call Volume Ratio 变化.

特别适合分析: TIGR 5月22日处罚前后的情绪翻转

使用:
  1. export POLYGON_API_KEY="你的key"
  2. pip install requests pandas
  3. python historical_pc_ratio.py
"""

import requests
import pandas as pd
import time
import datetime
import os
import sys
import json

# ============================================================
# 配置
# ============================================================
API_KEY = os.environ.get("POLYGON_API_KEY", "jyOY7VIGftJCnCAi3RXw5kuCB7E4m1ja")
BASE_URL = "https://api.polygon.io"

# 免费 tier: 5次/分钟, 间隔 13 秒比较安全
REQUEST_INTERVAL = 13

# 要分析的股票和日期范围
TICKERS = ["TIGR", "NIO"]
START_DATE = "2026-05-12"  # 处罚前一周
END_DATE = "2026-05-24"    # 到今天

# 行权价范围 (缩小范围, 减少请求次数)
STRIKE_RANGES = {
    "TIGR": {"gte": 3.0, "lte": 12.0},
    "NIO":  {"gte": 3.0, "lte": 12.0},
}


def api_get(url, params=None):
    """带限速和错误处理的 GET 请求"""
    if params is None:
        params = {}
    params["apiKey"] = API_KEY
    
    try:
        resp = requests.get(url, params=params, timeout=30)
    except requests.exceptions.RequestException as e:
        print(f"    [网络错误] {e}")
        return None
    
    if resp.status_code == 429:
        print(f"    [限速] 等待 60 秒...")
        time.sleep(60)
        return api_get(url, params)
    elif resp.status_code == 403:
        print(f"    [403] 需要付费 plan: {url[:80]}")
        return None
    elif resp.status_code != 200:
        print(f"    [HTTP {resp.status_code}] {resp.text[:100]}")
        return None
    
    time.sleep(REQUEST_INTERVAL)
    return resp.json()


def list_contracts(underlying, expiration_gte, expiration_lte,
                   contract_type=None, strike_gte=None, strike_lte=None):
    """查询期权合约列表"""
    params = {
        "underlying_ticker": underlying,
        "expiration_date.gte": expiration_gte,
        "expiration_date.lte": expiration_lte,
        "limit": 1000,
        "order": "asc",
        "sort": "expiration_date",
    }
    if contract_type:
        params["contract_type"] = contract_type
    if strike_gte is not None:
        params["strike_price.gte"] = strike_gte
    if strike_lte is not None:
        params["strike_price.lte"] = strike_lte
    
    all_results = []
    url = f"{BASE_URL}/v3/reference/options/contracts"
    page = 0
    
    while url:
        data = api_get(url, params if page == 0 else None)
        if data is None:
            break
        
        results = data.get("results", [])
        for c in results:
            all_results.append({
                "option_ticker": c.get("ticker"),
                "contract_type": c.get("contract_type"),
                "strike_price": c.get("strike_price"),
                "expiration_date": c.get("expiration_date"),
            })
        
        next_url = data.get("next_url")
        if next_url and len(results) > 0:
            url = next_url
            page += 1
        else:
            break
    
    return pd.DataFrame(all_results)


def get_contract_daily_bars(option_ticker, start_date, end_date):
    """拉取单个合约的日K线"""
    url = f"{BASE_URL}/v2/aggs/ticker/{option_ticker}/range/1/day/{start_date}/{end_date}"
    params = {"adjusted": "true", "sort": "asc", "limit": 50000}
    
    data = api_get(url, params)
    if data is None:
        return pd.DataFrame()
    
    results = data.get("results", [])
    if not results:
        return pd.DataFrame()
    
    records = []
    for bar in results:
        ts = bar.get("t", 0)
        records.append({
            "date": datetime.datetime.fromtimestamp(ts / 1000).strftime("%Y-%m-%d"),
            "open": bar.get("o"),
            "high": bar.get("h"),
            "low": bar.get("l"),
            "close": bar.get("c"),
            "volume": bar.get("v", 0),
            "vwap": bar.get("vw"),
            "transactions": bar.get("n", 0),
        })
    
    return pd.DataFrame(records)


def analyze_ticker(underlying, start_date, end_date, strike_gte, strike_lte):
    """
    对一只股票:
    1. 查出所有相关期权合约
    2. 批量拉取每个合约的日K线
    3. 按日期汇总 call/put 成交量
    4. 计算每日 Put/Call Volume Ratio
    """
    print(f"\n{'='*60}")
    print(f"  分析 {underlying} 期权历史")
    print(f"  日期范围: {start_date} ~ {end_date}")
    print(f"  行权价范围: ${strike_gte} ~ ${strike_lte}")
    print(f"{'='*60}")
    
    # 1. 查合约 (到期日在分析区间之后的, 即分析期间还活着的合约)
    # 用一个宽一点的到期日范围
    exp_start = start_date  # 到期日 >= 分析开始日
    exp_end_dt = datetime.datetime.strptime(end_date, "%Y-%m-%d") + datetime.timedelta(days=120)
    exp_end = exp_end_dt.strftime("%Y-%m-%d")
    
    print(f"\n  [1/3] 查询合约列表...")
    
    # 分别查 call 和 put
    calls_df = list_contracts(underlying, exp_start, exp_end, "call", strike_gte, strike_lte)
    puts_df = list_contracts(underlying, exp_start, exp_end, "put", strike_gte, strike_lte)
    
    all_contracts = pd.concat([calls_df, puts_df], ignore_index=True)
    
    if len(all_contracts) == 0:
        print("  未找到合约, 跳过")
        return None
    
    n_calls = len(all_contracts[all_contracts.contract_type == "call"])
    n_puts = len(all_contracts[all_contracts.contract_type == "put"])
    print(f"  找到 {len(all_contracts)} 个合约 ({n_calls} calls, {n_puts} puts)")
    
    # 2. 限制合约数量 (免费 tier 太慢, 每个合约要 13 秒)
    # 策略: 每种 type 取最活跃的到期日 (最近的2-3个到期日)
    unique_expiries = sorted(all_contracts["expiration_date"].unique())
    
    # 取最近的到期日 (这些通常成交量最大, 最能反映情绪)
    selected_expiries = unique_expiries[:6]  # 最近6个到期日
    filtered = all_contracts[all_contracts["expiration_date"].isin(selected_expiries)]
    
    print(f"  选择最近 {len(selected_expiries)} 个到期日, 共 {len(filtered)} 个合约")
    print(f"  到期日: {', '.join(selected_expiries)}")
    
    # 估算时间
    est_minutes = len(filtered) * REQUEST_INTERVAL / 60
    print(f"  预计耗时: {est_minutes:.0f} 分钟 (免费 tier 限速 {REQUEST_INTERVAL}秒/请求)")
    print(f"\n  [2/3] 批量拉取合约历史K线...")
    
    # 3. 批量拉取
    all_bars = []
    total = len(filtered)
    
    for i, (_, row) in enumerate(filtered.iterrows()):
        ticker = row["option_ticker"]
        ct = row["contract_type"]
        strike = row["strike_price"]
        exp = row["expiration_date"]
        
        bars = get_contract_daily_bars(ticker, start_date, end_date)
        
        if len(bars) > 0:
            bars["option_ticker"] = ticker
            bars["contract_type"] = ct
            bars["strike_price"] = strike
            bars["expiration_date"] = exp
            all_bars.append(bars)
        
        # 进度显示
        pct = (i + 1) / total * 100
        status = f"有数据({len(bars)}天)" if len(bars) > 0 else "无数据"
        if (i + 1) % 5 == 0 or (i + 1) == total:
            print(f"    进度: {i+1}/{total} ({pct:.0f}%) | 最新: {ct} ${strike} {exp} -> {status}")
    
    if not all_bars:
        print("  未获取到任何K线数据")
        return None
    
    combined = pd.concat(all_bars, ignore_index=True)
    print(f"  总计 {len(combined)} 条K线记录")
    
    # 4. 按日期汇总
    print(f"\n  [3/3] 计算每日 Put/Call Volume Ratio...")
    
    daily_summary = []
    
    for date in sorted(combined["date"].unique()):
        day_data = combined[combined["date"] == date]
        
        call_data = day_data[day_data["contract_type"] == "call"]
        put_data = day_data[day_data["contract_type"] == "put"]
        
        call_vol = call_data["volume"].sum()
        put_vol = put_data["volume"].sum()
        call_txn = call_data["transactions"].sum()
        put_txn = put_data["transactions"].sum()
        
        # 活跃合约数
        call_active = len(call_data[call_data["volume"] > 0])
        put_active = len(put_data[put_data["volume"] > 0])
        
        # 成交量最大的 call 和 put
        top_call = call_data.loc[call_data["volume"].idxmax()] if len(call_data) > 0 and call_vol > 0 else None
        top_put = put_data.loc[put_data["volume"].idxmax()] if len(put_data) > 0 and put_vol > 0 else None
        
        daily_summary.append({
            "date": date,
            "call_volume": int(call_vol),
            "put_volume": int(put_vol),
            "total_volume": int(call_vol + put_vol),
            "pc_vol_ratio": round(put_vol / call_vol, 3) if call_vol > 0 else None,
            "call_transactions": int(call_txn),
            "put_transactions": int(put_txn),
            "call_active_contracts": call_active,
            "put_active_contracts": put_active,
            "top_call_strike": top_call["strike_price"] if top_call is not None else None,
            "top_call_vol": int(top_call["volume"]) if top_call is not None else 0,
            "top_put_strike": top_put["strike_price"] if top_put is not None else None,
            "top_put_vol": int(top_put["volume"]) if top_put is not None else 0,
        })
    
    result_df = pd.DataFrame(daily_summary)
    
    return {
        "daily_summary": result_df,
        "raw_bars": combined,
        "contracts": filtered,
    }


def print_report(underlying, result):
    """打印分析报告"""
    if result is None:
        return
    
    df = result["daily_summary"]
    
    print(f"\n{'='*60}")
    print(f"  {underlying} 每日 Put/Call Volume Ratio")
    print(f"{'='*60}")
    
    # 表头
    print(f"\n  {'日期':<12} {'Call量':>8} {'Put量':>8} {'总量':>8} {'P/C Ratio':>10} {'情绪':>8} {'最活跃Call':>12} {'最活跃Put':>12}")
    print(f"  {'-'*88}")
    
    for _, row in df.iterrows():
        # 情绪判断
        ratio = row["pc_vol_ratio"]
        if ratio is None:
            mood = "---"
        elif ratio < 0.5:
            mood = "极度看多"
        elif ratio < 0.7:
            mood = "偏多"
        elif ratio < 1.0:
            mood = "中性"
        elif ratio < 1.5:
            mood = "偏空"
        elif ratio < 3.0:
            mood = "看空"
        else:
            mood = "极度看空"
        
        # 高亮处罚日
        date_str = row["date"]
        if date_str == "2026-05-22":
            date_str = ">>> 5/22 <<<"
        
        top_call = f"${row['top_call_strike']}({row['top_call_vol']:,})" if row['top_call_vol'] > 0 else "---"
        top_put = f"${row['top_put_strike']}({row['top_put_vol']:,})" if row['top_put_vol'] > 0 else "---"
        
        ratio_str = f"{ratio:.3f}" if ratio is not None else "N/A"
        
        print(f"  {date_str:<12} {row['call_volume']:>8,} {row['put_volume']:>8,} {row['total_volume']:>8,} {ratio_str:>10} {mood:>8} {top_call:>12} {top_put:>12}")
    
    # 汇总
    if len(df) > 0:
        total_call = df["call_volume"].sum()
        total_put = df["put_volume"].sum()
        overall_ratio = round(total_put / total_call, 3) if total_call > 0 else None
        
        print(f"\n  --- 期间汇总 ---")
        print(f"  期间总 Call 成交量:  {total_call:>12,}")
        print(f"  期间总 Put 成交量:   {total_put:>12,}")
        print(f"  期间总 P/C Ratio:    {overall_ratio}")
        
        # 找出 ratio 最高和最低的日期
        valid = df[df["pc_vol_ratio"].notna()]
        if len(valid) > 0:
            max_day = valid.loc[valid["pc_vol_ratio"].idxmax()]
            min_day = valid.loc[valid["pc_vol_ratio"].idxmin()]
            print(f"  最看空的一天: {max_day['date']} (P/C={max_day['pc_vol_ratio']:.3f})")
            print(f"  最看多的一天: {min_day['date']} (P/C={min_day['pc_vol_ratio']:.3f})")


# ============================================================
# 主程序
# ============================================================
if __name__ == "__main__":
    
    if API_KEY == "YOUR_API_KEY_HERE":
        print("请先设置 Polygon API Key:")
        print("  export POLYGON_API_KEY='你的key'")
        print("  注册: https://polygon.io")
        sys.exit(1)
    
    print("="*60)
    print("  历史 Put/Call Volume Ratio 分析器")
    print(f"  分析期间: {START_DATE} ~ {END_DATE}")
    print(f"  标的: {', '.join(TICKERS)}")
    print("="*60)
    print(f"\n  注意: 免费 tier 限速 5次/分钟, 每个合约需要 ~{REQUEST_INTERVAL}秒")
    print(f"  完整分析可能需要 15-30 分钟, 请耐心等待")
    
    results = {}
    
    for ticker in TICKERS:
        strike_range = STRIKE_RANGES.get(ticker, {"gte": 1.0, "lte": 20.0})
        
        result = analyze_ticker(
            underlying=ticker,
            start_date=START_DATE,
            end_date=END_DATE,
            strike_gte=strike_range["gte"],
            strike_lte=strike_range["lte"],
        )
        
        if result is not None:
            results[ticker] = result
            print_report(ticker, result)
            
            # 保存 CSV
            csv_name = f"{ticker}_daily_pc_ratio_{START_DATE}_to_{END_DATE}.csv"
            result["daily_summary"].to_csv(csv_name, index=False)
            print(f"\n  已保存: {csv_name}")
            
            raw_csv = f"{ticker}_raw_bars_{START_DATE}_to_{END_DATE}.csv"
            result["raw_bars"].to_csv(raw_csv, index=False)
            print(f"  已保存: {raw_csv}")
    
    # 对比
    if len(results) == 2 and "TIGR" in results and "NIO" in results:
        print(f"\n{'='*60}")
        print(f"  TIGR vs NIO 处罚期间 Put/Call Ratio 对比")
        print(f"{'='*60}")
        
        tigr_df = results["TIGR"]["daily_summary"]
        nio_df = results["NIO"]["daily_summary"]
        
        merged = pd.merge(
            tigr_df[["date", "pc_vol_ratio", "total_volume"]].rename(
                columns={"pc_vol_ratio": "TIGR_PC", "total_volume": "TIGR_Vol"}),
            nio_df[["date", "pc_vol_ratio", "total_volume"]].rename(
                columns={"pc_vol_ratio": "NIO_PC", "total_volume": "NIO_Vol"}),
            on="date", how="outer"
        ).sort_values("date")
        
        print(f"\n  {'日期':<12} {'TIGR P/C':>10} {'TIGR成交':>10} {'NIO P/C':>10} {'NIO成交':>10}")
        print(f"  {'-'*52}")
        for _, row in merged.iterrows():
            tigr_pc = f"{row['TIGR_PC']:.3f}" if pd.notna(row['TIGR_PC']) else "---"
            nio_pc = f"{row['NIO_PC']:.3f}" if pd.notna(row['NIO_PC']) else "---"
            tigr_v = f"{int(row['TIGR_Vol']):,}" if pd.notna(row['TIGR_Vol']) else "---"
            nio_v = f"{int(row['NIO_Vol']):,}" if pd.notna(row['NIO_Vol']) else "---"
            
            marker = " <<<" if row["date"] == "2026-05-22" else ""
            print(f"  {row['date']:<12} {tigr_pc:>10} {tigr_v:>10} {nio_pc:>10} {nio_v:>10}{marker}")
    
    print(f"\n{'='*60}")
    print("完成!")
    print(f"{'='*60}")
    print("""
提示:
  - 如果合约太多导致太慢, 可以缩小 STRIKE_RANGES 的范围
  - 也可以减少 selected_expiries 的数量 (脚本里改 [:6] 为 [:3])
  - 或者只分析一只: 改 TICKERS = ["TIGR"]
  - 想看更长的历史: 改 START_DATE / END_DATE
""")
