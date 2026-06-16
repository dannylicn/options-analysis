"""
美股历史期权数据拉取工具
=======================
数据源: Polygon.io (已更名 Massive.com, API 完全兼容)

使用前准备:
1. 注册 https://polygon.io (或 massive.com), 获取免费 API Key
2. pip install polygon-api-client pandas
3. 将下方 API_KEY 替换为你自己的 key

免费 tier 限制:
- 数据延迟 15 分钟
- 每分钟 5 次请求
- 无法访问某些高级端点 (需 $29/月 plan)

本脚本包含 4 个核心功能:
1. 拉取当前期权链快照 (所有行权价/到期日的 OI, IV, Greeks)
2. 拉取单个期权合约的历史 K 线 (OHLCV)
3. 查询可用的期权合约列表 (按到期日/行权价筛选)
4. 计算历史 Put/Call Ratio 和 IV 趋势 (通过每日聚合)
"""

import time
import datetime
from polygon import RESTClient
import pandas as pd

# ============================================================
# 配置区 — 改这里就行
# ============================================================
API_KEY = "jyOY7VIGftJCnCAi3RXw5kuCB7E4m1ja"  # <-- 替换为你的 API Key
TICKER = "TIGER"                    # 标的股票代码 (NIO, TIGR, TSLA 等)

# 初始化客户端
client = RESTClient(api_key=API_KEY)


# ============================================================
# 功能 1: 拉取当前期权链快照
# ============================================================
def get_options_chain_snapshot(ticker: str, expiration_gte: str = None, 
                                expiration_lte: str = None) -> pd.DataFrame:
    """
    获取某只股票当前所有期权合约的快照数据.
    
    参数:
        ticker: 标的代码 (如 "NIO")
        expiration_gte: 最早到期日 (如 "2026-06-01")
        expiration_lte: 最晚到期日 (如 "2026-09-30")
    
    返回:
        DataFrame, 每行是一个期权合约, 包含:
        - contract_type (call/put)
        - strike_price (行权价)
        - expiration_date (到期日)
        - open_interest (未平仓量)
        - volume (当日成交量)
        - implied_volatility (隐含波动率)
        - delta, gamma, theta, vega (Greeks)
        - last_price (最新价)
        - bid, ask (买卖价)
    """
    print(f"正在拉取 {ticker} 期权链快照...")
    
    params = {}
    if expiration_gte:
        params["expiration_date.gte"] = expiration_gte
    if expiration_lte:
        params["expiration_date.lte"] = expiration_lte
    
    records = []
    for contract in client.list_snapshot_options_chain(ticker, params=params):
        detail = contract.details
        greeks = contract.greeks or {}
        day = contract.day or {}
        
        records.append({
            "ticker": detail.ticker if detail else None,
            "contract_type": detail.contract_type if detail else None,
            "strike_price": detail.strike_price if detail else None,
            "expiration_date": detail.expiration_date if detail else None,
            "open_interest": contract.open_interest,
            "volume": day.volume if hasattr(day, 'volume') else None,
            "implied_volatility": contract.implied_volatility,
            "delta": greeks.delta if hasattr(greeks, 'delta') else None,
            "gamma": greeks.gamma if hasattr(greeks, 'gamma') else None,
            "theta": greeks.theta if hasattr(greeks, 'theta') else None,
            "vega": greeks.vega if hasattr(greeks, 'vega') else None,
            "last_price": contract.last_quote.midpoint if contract.last_quote else None,
            "bid": contract.last_quote.bid if contract.last_quote else None,
            "ask": contract.last_quote.ask if contract.last_quote else None,
            "break_even": contract.break_even_price,
        })
        
    df = pd.DataFrame(records)
    print(f"  共获取 {len(df)} 个合约")
    return df


# ============================================================
# 功能 2: 查询可用的期权合约列表
# ============================================================
def list_options_contracts(ticker: str, expiration_date: str = None,
                           contract_type: str = None,
                           strike_price_gte: float = None,
                           strike_price_lte: float = None) -> pd.DataFrame:
    """
    查询某只股票有哪些期权合约可用 (含历史已过期的).
    
    参数:
        ticker: 标的代码
        expiration_date: 精确到期日 (如 "2026-06-20")
        contract_type: "call" 或 "put"
        strike_price_gte: 最低行权价
        strike_price_lte: 最高行权价
    
    返回:
        DataFrame, 包含 option_ticker, strike, expiration, type 等
    """
    print(f"正在查询 {ticker} 的期权合约列表...")
    
    params = {"underlying_ticker": ticker, "limit": 1000}
    if expiration_date:
        params["expiration_date"] = expiration_date
    if contract_type:
        params["contract_type"] = contract_type
    if strike_price_gte:
        params["strike_price.gte"] = strike_price_gte
    if strike_price_lte:
        params["strike_price.lte"] = strike_price_lte
    
    records = []
    for contract in client.list_options_contracts(**params):
        records.append({
            "option_ticker": contract.ticker,
            "underlying": contract.underlying_ticker,
            "contract_type": contract.contract_type,
            "strike_price": contract.strike_price,
            "expiration_date": contract.expiration_date,
            "shares_per_contract": contract.shares_per_contract,
        })
    
    df = pd.DataFrame(records)
    print(f"  共找到 {len(df)} 个合约")
    return df


# ============================================================
# 功能 3: 拉取单个期权合约的历史 K 线
# ============================================================
def get_contract_history(option_ticker: str, start_date: str, 
                          end_date: str, timespan: str = "day") -> pd.DataFrame:
    """
    获取单个期权合约的历史 OHLCV 数据.
    
    参数:
        option_ticker: 期权合约代码 (如 "O:NIO260619C00007000")
                       格式: O:{标的}{到期日YYMMDD}{C/P}{行权价*1000补零}
        start_date: 开始日期 "YYYY-MM-DD"
        end_date: 结束日期 "YYYY-MM-DD"
        timespan: "day" (日线) 或 "hour" / "minute"
    
    返回:
        DataFrame, 包含 date, open, high, low, close, volume, vwap
    """
    print(f"正在拉取 {option_ticker} 从 {start_date} 到 {end_date} 的历史数据...")
    
    records = []
    for bar in client.list_aggs(
        ticker=option_ticker,
        multiplier=1,
        timespan=timespan,
        from_=start_date,
        to=end_date,
        limit=50000,
    ):
        records.append({
            "date": datetime.datetime.fromtimestamp(bar.timestamp / 1000).strftime("%Y-%m-%d"),
            "open": bar.open,
            "high": bar.high,
            "low": bar.low,
            "close": bar.close,
            "volume": bar.volume,
            "vwap": bar.vwap,
            "transactions": bar.transactions,
        })
    
    df = pd.DataFrame(records)
    print(f"  共获取 {len(df)} 条记录")
    return df


# ============================================================
# 功能 4: 计算 Put/Call Ratio 和 IV 汇总
# ============================================================
def compute_put_call_summary(chain_df: pd.DataFrame) -> dict:
    """
    根据期权链快照, 计算 Put/Call Ratio 和 IV 汇总.
    
    参数:
        chain_df: 由 get_options_chain_snapshot() 返回的 DataFrame
    
    返回:
        dict, 包含:
        - total_call_oi, total_put_oi
        - oi_put_call_ratio
        - total_call_volume, total_put_volume  
        - volume_put_call_ratio
        - avg_call_iv, avg_put_iv
        - max_call_oi_strike (call OI 最大的行权价)
        - max_put_oi_strike (put OI 最大的行权价)
    """
    calls = chain_df[chain_df["contract_type"] == "call"]
    puts = chain_df[chain_df["contract_type"] == "put"]
    
    total_call_oi = calls["open_interest"].sum()
    total_put_oi = puts["open_interest"].sum()
    total_call_vol = calls["volume"].sum() if "volume" in calls.columns else 0
    total_put_vol = puts["volume"].sum() if "volume" in puts.columns else 0
    
    # 找 OI 最大的行权价
    max_call_oi_strike = None
    max_put_oi_strike = None
    if len(calls) > 0 and total_call_oi > 0:
        max_call_oi_strike = calls.loc[calls["open_interest"].idxmax(), "strike_price"]
    if len(puts) > 0 and total_put_oi > 0:
        max_put_oi_strike = puts.loc[puts["open_interest"].idxmax(), "strike_price"]
    
    summary = {
        "total_call_oi": int(total_call_oi),
        "total_put_oi": int(total_put_oi),
        "oi_put_call_ratio": round(total_put_oi / total_call_oi, 3) if total_call_oi > 0 else None,
        "total_call_volume": int(total_call_vol) if pd.notna(total_call_vol) else 0,
        "total_put_volume": int(total_put_vol) if pd.notna(total_put_vol) else 0,
        "volume_put_call_ratio": round(total_put_vol / total_call_vol, 3) if total_call_vol > 0 else None,
        "avg_call_iv": round(calls["implied_volatility"].mean(), 4) if len(calls) > 0 else None,
        "avg_put_iv": round(puts["implied_volatility"].mean(), 4) if len(puts) > 0 else None,
        "max_call_oi_strike": max_call_oi_strike,
        "max_put_oi_strike": max_put_oi_strike,
    }
    
    return summary


# ============================================================
# 功能 5: 构建期权代码的辅助函数
# ============================================================
def build_option_ticker(underlying: str, expiration: str, 
                         contract_type: str, strike: float) -> str:
    """
    构建 Polygon 格式的期权代码.
    
    参数:
        underlying: 标的代码 (如 "NIO")
        expiration: 到期日 "YYYY-MM-DD" (如 "2026-06-19")
        contract_type: "call" 或 "put"
        strike: 行权价 (如 7.0)
    
    返回:
        str: 如 "O:NIO260619C00007000"
    
    格式说明:
        O:{标的}{YY}{MM}{DD}{C或P}{行权价*1000, 补零到8位}
    """
    exp_date = datetime.datetime.strptime(expiration, "%Y-%m-%d")
    date_str = exp_date.strftime("%y%m%d")
    cp = "C" if contract_type.lower() == "call" else "P"
    strike_str = str(int(strike * 1000)).zfill(8)
    return f"O:{underlying}{date_str}{cp}{strike_str}"


# ============================================================
# 使用示例
# ============================================================
if __name__ == "__main__":
    
    print("=" * 60)
    print("美股期权数据拉取工具")
    print("=" * 60)
    
    # ----- 示例 1: 拉取 NIO 当前期权链快照 -----
    print("\n[示例 1] 拉取 NIO 期权链快照 (2026年6月到期)")
    chain = get_options_chain_snapshot(
        ticker="NIO",
        expiration_gte="2026-06-01",
        expiration_lte="2026-06-30",
    )
    if len(chain) > 0:
        print(chain[["contract_type", "strike_price", "expiration_date", 
                      "open_interest", "volume", "implied_volatility"]].head(20))
        
        # 计算 Put/Call 汇总
        summary = compute_put_call_summary(chain)
        print(f"\n  Put/Call OI Ratio:     {summary['oi_put_call_ratio']}")
        print(f"  Put/Call Volume Ratio: {summary['volume_put_call_ratio']}")
        print(f"  总 Call OI:            {summary['total_call_oi']:,}")
        print(f"  总 Put OI:             {summary['total_put_oi']:,}")
        print(f"  Call 平均 IV:          {summary['avg_call_iv']}")
        print(f"  Put 平均 IV:           {summary['avg_put_iv']}")
        print(f"  最大 Call OI 行权价:   ${summary['max_call_oi_strike']}")
        print(f"  最大 Put OI 行权价:    ${summary['max_put_oi_strike']}")
    
    time.sleep(15)  # 免费 tier 限速, 等一下
    
    # ----- 示例 2: 查询 TIGR 的 put 合约列表 -----
    print("\n[示例 2] 查询 TIGR 2026年6月到期的 put 合约")
    contracts = list_options_contracts(
        ticker="TIGR",
        expiration_date="2026-06-20",
        contract_type="put",
    )
    if len(contracts) > 0:
        print(contracts.head(10))
    
    time.sleep(15)
    
    # ----- 示例 3: 拉取单个合约的历史 K 线 -----
    print("\n[示例 3] 拉取 NIO $7 Call (2026-06-20到期) 的历史K线")
    option_code = build_option_ticker("NIO", "2026-06-20", "call", 7.0)
    print(f"  期权代码: {option_code}")
    
    history = get_contract_history(
        option_ticker=option_code,
        start_date="2026-01-01",
        end_date="2026-05-24",
    )
    if len(history) > 0:
        print(history.tail(10))
    
    # ----- 示例 4: 保存到 CSV -----
    print("\n[保存数据]")
    if len(chain) > 0:
        chain.to_csv("nio_options_chain.csv", index=False)
        print("  期权链快照 -> nio_options_chain.csv")
    if len(history) > 0:
        history.to_csv("nio_7c_history.csv", index=False)
        print("  合约历史   -> nio_7c_history.csv")
    
    print("\n完成!")
    print("\n" + "=" * 60)
    print("进阶用法提示:")
    print("=" * 60)
    print("""
1. 要拉 TIGR 的数据, 把 TICKER 改成 "TIGR" 即可

2. 要跟踪 "处罚前后 IV 变化":
   - 每天运行一次 get_options_chain_snapshot()
   - 把 avg_call_iv / avg_put_iv 存下来
   - 画时间序列图就能看到 IV 的变化趋势

3. 要回测 "IV 超过 100% 后买入的胜率":
   - 用 get_contract_history() 拉历史价格
   - 结合历史 IV 数据做条件筛选

4. 免费 tier 限速严格 (5次/分钟):
   - 批量拉数据时加 time.sleep(15)
   - 或升级到 $29/月 plan 解除限制

5. 期权代码格式:
   O:{标的}{YYMMDD}{C/P}{行权价*1000补零8位}
   例: O:NIO260619C00007000 = NIO 2026-06-19 $7 Call
   用 build_option_ticker() 函数自动生成
""")
