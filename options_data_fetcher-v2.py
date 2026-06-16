"""
美股历史期权数据拉取工具 (免费 tier 版)
========================================
数据源: Polygon.io / Massive.com

只使用免费 tier 可访问的端点:
  - /v3/reference/options/contracts  (合约列表)
  - /v2/aggs/ticker/{optionsTicker}/range/...  (历史K线)
  - /v1/open-close/{optionsTicker}/{date}  (每日开收盘)

使用前准备:
  1. 注册 https://polygon.io 获取免费 API Key
  2. pip install requests pandas
  3. 将下方 API_KEY 替换为你自己的 key

免费 tier 限制: 每分钟 5 次请求, 数据延迟 15 分钟
"""

import requests
import pandas as pd
import time
import datetime
import json
import os

# ============================================================
# 配置区
# ============================================================
API_KEY = os.environ.get("POLYGON_API_KEY", "jyOY7VIGftJCnCAi3RXw5kuCB7E4m1ja")
BASE_URL = "https://api.polygon.io"

# 限速控制 (免费 tier: 5 次/分钟)
REQUEST_INTERVAL = 13  # 每次请求间隔秒数, 保守设为 13 秒


def _rate_limited_get(url, params=None):
    """带限速的 GET 请求"""
    if params is None:
        params = {}
    params["apiKey"] = API_KEY
    
    resp = requests.get(url, params=params, timeout=30)
    
    if resp.status_code == 403:
        print(f"  [错误] 403 Forbidden - 该端点需要付费 plan")
        print(f"  URL: {url}")
        return None
    elif resp.status_code == 429:
        print(f"  [限速] 等待 60 秒后重试...")
        time.sleep(60)
        return _rate_limited_get(url, params)
    elif resp.status_code != 200:
        print(f"  [错误] HTTP {resp.status_code}: {resp.text[:200]}")
        return None
    
    time.sleep(REQUEST_INTERVAL)
    return resp.json()


# ============================================================
# 功能 1: 查询期权合约列表 (免费 tier 可用)
# ============================================================
def list_contracts(underlying: str,
                   expiration_date: str = None,
                   expiration_gte: str = None,
                   expiration_lte: str = None,
                   contract_type: str = None,
                   strike_price_gte: float = None,
                   strike_price_lte: float = None,
                   expired: bool = None,
                   limit: int = 100) -> pd.DataFrame:
    """
    查询某只股票的期权合约列表.
    
    参数:
        underlying: 标的代码 (如 "NIO", "TIGR", "TSLA")
        expiration_date: 精确到期日 "YYYY-MM-DD"
        expiration_gte/lte: 到期日范围
        contract_type: "call" 或 "put"
        strike_price_gte/lte: 行权价范围
        expired: True=只看已过期, False=只看未过期, None=全部
        limit: 每页数量 (最大 1000)
    
    返回: DataFrame
    """
    print(f"查询 {underlying} 的期权合约列表...")
    
    params = {
        "underlying_ticker": underlying,
        "limit": min(limit, 1000),
        "order": "asc",
        "sort": "expiration_date",
    }
    if expiration_date:
        params["expiration_date"] = expiration_date
    if expiration_gte:
        params["expiration_date.gte"] = expiration_gte
    if expiration_lte:
        params["expiration_date.lte"] = expiration_lte
    if contract_type:
        params["contract_type"] = contract_type
    if strike_price_gte is not None:
        params["strike_price.gte"] = strike_price_gte
    if strike_price_lte is not None:
        params["strike_price.lte"] = strike_price_lte
    if expired is not None:
        params["expired"] = str(expired).lower()
    
    all_records = []
    url = f"{BASE_URL}/v3/reference/options/contracts"
    
    while url:
        data = _rate_limited_get(url, params if not all_records else None)
        if data is None:
            break
        
        results = data.get("results", [])
        for c in results:
            all_records.append({
                "option_ticker": c.get("ticker"),
                "underlying": c.get("underlying_ticker"),
                "contract_type": c.get("contract_type"),
                "strike_price": c.get("strike_price"),
                "expiration_date": c.get("expiration_date"),
                "exercise_style": c.get("exercise_style"),
                "shares_per_contract": c.get("shares_per_contract", 100),
            })
        
        # 分页
        next_url = data.get("next_url")
        if next_url:
            url = next_url
            params = None  # next_url 已包含参数
        else:
            break
    
    df = pd.DataFrame(all_records)
    print(f"  找到 {len(df)} 个合约")
    return df


# ============================================================
# 功能 2: 拉取单个期权合约的历史 K 线 (免费 tier 可用)
# ============================================================
def get_option_bars(option_ticker: str, 
                    start_date: str, 
                    end_date: str,
                    timespan: str = "day",
                    multiplier: int = 1) -> pd.DataFrame:
    """
    获取单个期权合约的历史 OHLCV.
    
    参数:
        option_ticker: 期权合约代码 (如 "O:NIO260619C00007000")
        start_date: "YYYY-MM-DD"
        end_date: "YYYY-MM-DD"
        timespan: "day", "hour", "minute"
        multiplier: 时间窗口倍数
    
    返回: DataFrame with date, open, high, low, close, volume, vwap
    """
    print(f"拉取 {option_ticker} 历史K线 ({start_date} ~ {end_date})...")
    
    url = f"{BASE_URL}/v2/aggs/ticker/{option_ticker}/range/{multiplier}/{timespan}/{start_date}/{end_date}"
    params = {"adjusted": "true", "sort": "asc", "limit": 50000}
    
    data = _rate_limited_get(url, params)
    if data is None:
        return pd.DataFrame()
    
    results = data.get("results", [])
    records = []
    for bar in results:
        ts = bar.get("t", 0)
        records.append({
            "date": datetime.datetime.fromtimestamp(ts / 1000).strftime("%Y-%m-%d"),
            "open": bar.get("o"),
            "high": bar.get("h"),
            "low": bar.get("l"),
            "close": bar.get("c"),
            "volume": bar.get("v"),
            "vwap": bar.get("vw"),
            "transactions": bar.get("n"),
        })
    
    df = pd.DataFrame(records)
    print(f"  获取 {len(df)} 条K线记录")
    return df


# ============================================================
# 功能 3: 拉取每日开收盘数据 (免费 tier 可用)
# ============================================================
def get_daily_open_close(option_ticker: str, date: str) -> dict:
    """
    获取某个期权合约在某天的开盘/收盘价.
    
    参数:
        option_ticker: 期权合约代码 (如 "O:NIO260619C00007000")
        date: "YYYY-MM-DD"
    
    返回: dict with open, close, high, low, volume 等
    """
    url = f"{BASE_URL}/v1/open-close/{option_ticker}/{date}"
    data = _rate_limited_get(url)
    return data


# ============================================================
# 功能 4: 构建期权代码
# ============================================================
def build_option_ticker(underlying: str, expiration: str,
                        contract_type: str, strike: float) -> str:
    """
    构建 Polygon 格式的期权代码.
    
    示例:
        build_option_ticker("NIO", "2026-06-19", "call", 7.0)
        -> "O:NIO260619C00007000"
    
    格式: O:{标的}{YYMMDD}{C/P}{行权价*1000, 补零到8位}
    """
    exp = datetime.datetime.strptime(expiration, "%Y-%m-%d")
    date_str = exp.strftime("%y%m%d")
    cp = "C" if contract_type.lower() == "call" else "P"
    strike_str = str(int(strike * 1000)).zfill(8)
    return f"O:{underlying}{date_str}{cp}{strike_str}"


# ============================================================
# 功能 5: 批量拉取多个合约的历史数据, 计算 OI/Volume 趋势
# ============================================================
def batch_fetch_history(contracts_df: pd.DataFrame,
                        start_date: str,
                        end_date: str,
                        max_contracts: int = 20) -> pd.DataFrame:
    """
    对合约列表中的前 N 个合约, 批量拉取历史 K 线.
    
    参数:
        contracts_df: list_contracts() 返回的 DataFrame
        start_date: 开始日期
        end_date: 结束日期
        max_contracts: 最多拉取多少个合约 (免费 tier 限速, 建议 <=20)
    
    返回: 汇总的 DataFrame, 包含 option_ticker, contract_type, 
          strike_price, date, close, volume 等
    """
    print(f"\n批量拉取 {min(len(contracts_df), max_contracts)} 个合约的历史数据...")
    
    all_bars = []
    count = 0
    
    for _, row in contracts_df.head(max_contracts).iterrows():
        ticker = row["option_ticker"]
        bars = get_option_bars(ticker, start_date, end_date)
        
        if len(bars) > 0:
            bars["option_ticker"] = ticker
            bars["contract_type"] = row["contract_type"]
            bars["strike_price"] = row["strike_price"]
            bars["expiration_date"] = row["expiration_date"]
            all_bars.append(bars)
        
        count += 1
        if count % 5 == 0:
            print(f"  已完成 {count}/{min(len(contracts_df), max_contracts)}")
    
    if all_bars:
        result = pd.concat(all_bars, ignore_index=True)
        print(f"  总计 {len(result)} 条记录")
        return result
    else:
        print("  未获取到数据")
        return pd.DataFrame()


# ============================================================
# 功能 6: 从批量数据计算每日 Put/Call Volume Ratio
# ============================================================
def compute_daily_put_call_ratio(batch_df: pd.DataFrame) -> pd.DataFrame:
    """
    从批量拉取的历史数据中, 按日期计算 Put/Call Volume Ratio.
    
    参数:
        batch_df: batch_fetch_history() 返回的 DataFrame
    
    返回: DataFrame with date, call_volume, put_volume, pc_ratio
    """
    if len(batch_df) == 0:
        return pd.DataFrame()
    
    daily = batch_df.groupby(["date", "contract_type"])["volume"].sum().unstack(fill_value=0)
    
    result = pd.DataFrame({
        "date": daily.index,
        "call_volume": daily.get("call", 0).values,
        "put_volume": daily.get("put", 0).values,
    })
    
    result["pc_volume_ratio"] = result.apply(
        lambda r: round(r["put_volume"] / r["call_volume"], 3) 
        if r["call_volume"] > 0 else None, axis=1
    )
    
    return result.sort_values("date").reset_index(drop=True)


# ============================================================
# 使用示例
# ============================================================
if __name__ == "__main__":
    
    if API_KEY == "YOUR_API_KEY_HERE":
        print("=" * 60)
        print("请先设置 API Key!")
        print("方法 1: 修改脚本顶部的 API_KEY 变量")
        print("方法 2: export POLYGON_API_KEY='你的key'")
        print("注册地址: https://polygon.io")
        print("=" * 60)
        exit(1)
    
    print("=" * 60)
    print("美股期权数据拉取工具 (免费 tier 版)")
    print("=" * 60)
    
    # ----- 示例 1: 查询 NIO 2026年6-8月到期的 call 合约 -----
    print("\n[1] 查询 NIO 的 call 合约 (2026年6-8月到期)")
    nio_calls = list_contracts(
        underlying="NIO",
        expiration_gte="2026-06-01",
        expiration_lte="2026-08-31",
        contract_type="call",
        strike_price_gte=5.0,
        strike_price_lte=10.0,
    )
    if len(nio_calls) > 0:
        print(nio_calls.head(15).to_string(index=False))
    
    # ----- 示例 2: 查询 NIO 同期的 put 合约 -----
    print("\n[2] 查询 NIO 的 put 合约 (2026年6-8月到期)")
    nio_puts = list_contracts(
        underlying="NIO",
        expiration_gte="2026-06-01",
        expiration_lte="2026-08-31",
        contract_type="put",
        strike_price_gte=3.0,
        strike_price_lte=7.0,
    )
    if len(nio_puts) > 0:
        print(nio_puts.head(15).to_string(index=False))
    
    # ----- 示例 3: 拉取单个合约的历史 K 线 -----
    print("\n[3] 拉取 NIO $7 Call (2026-06-20到期) 的历史K线")
    option_code = build_option_ticker("NIO", "2026-06-20", "call", 7.0)
    print(f"  期权代码: {option_code}")
    
    history = get_option_bars(
        option_ticker=option_code,
        start_date="2026-03-01",
        end_date="2026-05-24",
    )
    if len(history) > 0:
        print(history.tail(10).to_string(index=False))
    
    # ----- 示例 4: 批量拉取, 计算历史 Put/Call Ratio -----
    print("\n[4] 批量拉取 NIO 期权历史, 计算 Put/Call Volume Ratio")
    
    # 先合并 call 和 put 合约列表
    all_contracts = pd.concat([
        nio_calls.head(5),  # 取前5个call
        nio_puts.head(5),   # 取前5个put
    ], ignore_index=True)
    
    if len(all_contracts) > 0:
        batch_data = batch_fetch_history(
            all_contracts,
            start_date="2026-04-01",
            end_date="2026-05-24",
            max_contracts=10,  # 免费tier建议不超过20
        )
        
        if len(batch_data) > 0:
            pc_ratio = compute_daily_put_call_ratio(batch_data)
            print("\n  每日 Put/Call Volume Ratio:")
            print(pc_ratio.tail(15).to_string(index=False))
    
    # ----- 示例 5: TIGR 的期权 -----
    print("\n[5] 查询 TIGR 的期权合约")
    tigr_contracts = list_contracts(
        underlying="TIGR",
        expiration_gte="2026-05-01",
        expiration_lte="2026-07-31",
        limit=50,
    )
    if len(tigr_contracts) > 0:
        print(tigr_contracts.head(15).to_string(index=False))
        
        # 拉一个 TIGR 合约的历史
        if len(tigr_contracts) > 0:
            first_ticker = tigr_contracts.iloc[0]["option_ticker"]
            tigr_hist = get_option_bars(first_ticker, "2026-04-01", "2026-05-24")
            if len(tigr_hist) > 0:
                print(f"\n  {first_ticker} 最近K线:")
                print(tigr_hist.tail(5).to_string(index=False))
    
    # ----- 保存数据 -----
    print("\n[保存数据到 CSV]")
    output_dir = os.path.dirname(os.path.abspath(__file__))
    
    if len(nio_calls) > 0:
        path = os.path.join(output_dir, "nio_call_contracts.csv")
        nio_calls.to_csv(path, index=False)
        print(f"  NIO call 合约列表 -> {path}")
    
    if len(nio_puts) > 0:
        path = os.path.join(output_dir, "nio_put_contracts.csv")
        nio_puts.to_csv(path, index=False)
        print(f"  NIO put 合约列表  -> {path}")
    
    if len(history) > 0:
        path = os.path.join(output_dir, "nio_7c_history.csv")
        history.to_csv(path, index=False)
        print(f"  NIO $7 call 历史  -> {path}")
    
    if len(tigr_contracts) > 0:
        path = os.path.join(output_dir, "tigr_contracts.csv")
        tigr_contracts.to_csv(path, index=False)
        print(f"  TIGR 合约列表     -> {path}")
    
    print("\n完成!")
    print("\n" + "=" * 60)
    print("使用提示:")
    print("=" * 60)
    print(f"""
1. 设置 API Key 的两种方式:
   - 直接改脚本顶部: API_KEY = "你的key"
   - 环境变量: export POLYGON_API_KEY="你的key"

2. 期权代码格式:
   O:{{标的}}{{YYMMDD}}{{C/P}}{{行权价*1000补零8位}}
   例: O:NIO260619C00007000 = NIO 2026-06-19 $7 Call
   用 build_option_ticker("NIO", "2026-06-19", "call", 7.0) 自动生成

3. 免费 tier 限速 (5次/分钟):
   - 脚本已内置 13 秒间隔
   - 批量拉取时耐心等待
   - 或设 POLYGON_API_KEY 为付费 key 后改小 REQUEST_INTERVAL

4. 要拉更多数据:
   - 改 list_contracts() 的 limit 参数 (最大 1000)
   - 改 batch_fetch_history() 的 max_contracts 参数
   - 改日期范围拉更长的历史

5. 免费 tier 不支持的功能 (需 $29/月):
   - 期权链快照 (snapshot) — 含实时 OI, IV, Greeks
   - 如果需要 OI 和 IV 数据, 建议:
     a) 升级到付费 plan, 或
     b) 用 barchart.com / Yahoo Finance 手动查看
""")
