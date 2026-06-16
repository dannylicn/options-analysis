"""
期权 Put/Call Ratio 分析器
==========================
数据源: Yahoo Finance (完全免费, 无需 API Key)

功能:
  1. 拉取完整期权链 (所有到期日, 含 OI, Volume, IV)
  2. 计算 Put/Call OI Ratio 和 Volume Ratio
  3. 找出最大 OI 的行权价 (市场共识价位)
  4. 计算 Max Pain (做市商锚定价位)
  5. 按到期日分组分析 (短期 vs 长期情绪)
  6. 导出 CSV + 打印分析报告

安装: pip install yfinance pandas
运行: python put_call_analyzer.py
"""

import yfinance as yf
import pandas as pd
import math
import warnings
from datetime import datetime

warnings.filterwarnings("ignore")


def fetch_full_options_chain(symbol: str) -> pd.DataFrame:
    """
    拉取某只股票所有到期日的完整期权链.
    
    返回 DataFrame 包含:
      expiry, side(call/put), strike, lastPrice, bid, ask, 
      volume, openInterest, impliedVolatility
    """
    print(f"\n{'='*60}")
    print(f"拉取 {symbol} 完整期权链...")
    print(f"{'='*60}")
    
    ticker = yf.Ticker(symbol)
    expirations = ticker.options
    
    if not expirations:
        print(f"  [错误] {symbol} 没有可用的期权数据")
        return pd.DataFrame()
    
    print(f"  可用到期日: {len(expirations)} 个")
    print(f"  范围: {expirations[0]} ~ {expirations[-1]}")
    
    all_chains = []
    for exp in expirations:
        try:
            chain = ticker.option_chain(exp)
            
            calls = chain.calls.copy()
            calls["expiry"] = exp
            calls["side"] = "call"
            
            puts = chain.puts.copy()
            puts["expiry"] = exp
            puts["side"] = "put"
            
            all_chains.extend([calls, puts])
        except Exception as e:
            print(f"  [警告] {exp} 拉取失败: {e}")
            continue
    
    if not all_chains:
        return pd.DataFrame()
    
    df = pd.concat(all_chains, ignore_index=True)
    
    # 清理数据
    df["volume"] = df["volume"].fillna(0).astype(int)
    df["openInterest"] = df["openInterest"].fillna(0).astype(int)
    df["impliedVolatility"] = df["impliedVolatility"].fillna(0)
    
    print(f"  总合约数: {len(df)} ({len(df[df.side=='call'])} calls, {len(df[df.side=='put'])} puts)")
    
    return df


def compute_put_call_ratios(df: pd.DataFrame) -> dict:
    """
    计算整体的 Put/Call Ratio.
    """
    calls = df[df["side"] == "call"]
    puts = df[df["side"] == "put"]
    
    total_call_oi = calls["openInterest"].sum()
    total_put_oi = puts["openInterest"].sum()
    total_call_vol = calls["volume"].sum()
    total_put_vol = puts["volume"].sum()
    
    # 加权平均 IV (按 OI 加权)
    avg_call_iv = 0
    avg_put_iv = 0
    if total_call_oi > 0:
        avg_call_iv = (calls["impliedVolatility"] * calls["openInterest"]).sum() / total_call_oi
    if total_put_oi > 0:
        avg_put_iv = (puts["impliedVolatility"] * puts["openInterest"]).sum() / total_put_oi
    
    # 最大 OI 行权价
    max_call_oi_row = calls.loc[calls["openInterest"].idxmax()] if total_call_oi > 0 else None
    max_put_oi_row = puts.loc[puts["openInterest"].idxmax()] if total_put_oi > 0 else None
    
    return {
        "total_call_oi": int(total_call_oi),
        "total_put_oi": int(total_put_oi),
        "oi_pc_ratio": round(total_put_oi / total_call_oi, 4) if total_call_oi > 0 else None,
        "total_call_volume": int(total_call_vol),
        "total_put_volume": int(total_put_vol),
        "vol_pc_ratio": round(total_put_vol / total_call_vol, 4) if total_call_vol > 0 else None,
        "avg_call_iv": round(avg_call_iv * 100, 2),  # 转为百分比
        "avg_put_iv": round(avg_put_iv * 100, 2),
        "max_call_oi_strike": max_call_oi_row["strike"] if max_call_oi_row is not None else None,
        "max_call_oi_expiry": max_call_oi_row["expiry"] if max_call_oi_row is not None else None,
        "max_call_oi_value": int(max_call_oi_row["openInterest"]) if max_call_oi_row is not None else 0,
        "max_put_oi_strike": max_put_oi_row["strike"] if max_put_oi_row is not None else None,
        "max_put_oi_expiry": max_put_oi_row["expiry"] if max_put_oi_row is not None else None,
        "max_put_oi_value": int(max_put_oi_row["openInterest"]) if max_put_oi_row is not None else 0,
    }


def compute_ratios_by_expiry(df: pd.DataFrame) -> pd.DataFrame:
    """
    按到期日分组计算 Put/Call Ratio (看短期 vs 长期情绪差异).
    """
    results = []
    for exp in sorted(df["expiry"].unique()):
        sub = df[df["expiry"] == exp]
        calls = sub[sub["side"] == "call"]
        puts = sub[sub["side"] == "put"]
        
        call_oi = calls["openInterest"].sum()
        put_oi = puts["openInterest"].sum()
        call_vol = calls["volume"].sum()
        put_vol = puts["volume"].sum()
        
        results.append({
            "expiry": exp,
            "call_oi": int(call_oi),
            "put_oi": int(put_oi),
            "oi_pc_ratio": round(put_oi / call_oi, 3) if call_oi > 0 else None,
            "call_volume": int(call_vol),
            "put_volume": int(put_vol),
            "vol_pc_ratio": round(put_vol / call_vol, 3) if call_vol > 0 else None,
        })
    
    return pd.DataFrame(results)


def compute_max_pain(df: pd.DataFrame, expiry: str = None) -> float:
    """
    计算 Max Pain (所有期权持有者亏损最大的价格).
    
    如果不指定 expiry, 用最近的到期日.
    """
    if expiry is None:
        expiry = sorted(df["expiry"].unique())[0]
    
    sub = df[df["expiry"] == expiry]
    calls = sub[sub["side"] == "call"]
    puts = sub[sub["side"] == "put"]
    
    strikes = sorted(sub["strike"].unique())
    
    min_pain = float("inf")
    max_pain_strike = None
    
    for s in strikes:
        # Call holders 的亏损: sum of OI * max(0, strike - s) for all call strikes < s
        call_pain = sum(
            row["openInterest"] * max(0, s - row["strike"])
            for _, row in calls.iterrows()
        )
        # Put holders 的亏损: sum of OI * max(0, s - strike) for all put strikes > s
        put_pain = sum(
            row["openInterest"] * max(0, row["strike"] - s)
            for _, row in puts.iterrows()
        )
        
        total_pain = call_pain + put_pain
        if total_pain < min_pain:
            min_pain = total_pain
            max_pain_strike = s
    
    return max_pain_strike


def find_top_oi_strikes(df: pd.DataFrame, top_n: int = 10) -> pd.DataFrame:
    """
    找出 OI 最大的前 N 个行权价 (分 call/put).
    """
    top = df.nlargest(top_n, "openInterest")[
        ["expiry", "side", "strike", "openInterest", "volume", "impliedVolatility", "lastPrice"]
    ].copy()
    top["impliedVolatility"] = (top["impliedVolatility"] * 100).round(1)
    return top.reset_index(drop=True)


def print_analysis_report(symbol: str, ratios: dict, by_expiry: pd.DataFrame, 
                           max_pain: float, top_oi: pd.DataFrame, current_price: float):
    """
    打印完整的分析报告.
    """
    print(f"\n{'='*60}")
    print(f"  {symbol} 期权情绪分析报告")
    print(f"  当前股价: ${current_price:.2f}")
    print(f"  生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*60}")
    
    # 情绪判断
    oi_ratio = ratios["oi_pc_ratio"]
    if oi_ratio is not None:
        if oi_ratio < 0.7:
            sentiment = "偏多 (Bullish)"
        elif oi_ratio < 1.0:
            sentiment = "中性偏多"
        elif oi_ratio < 1.3:
            sentiment = "中性偏空"
        else:
            sentiment = "偏空 (Bearish)"
    else:
        sentiment = "无数据"
    
    print(f"\n  整体情绪: {sentiment}")
    
    print(f"\n  --- Put/Call Ratio ---")
    print(f"  OI  Put/Call Ratio:     {ratios['oi_pc_ratio']}")
    print(f"  Vol Put/Call Ratio:     {ratios['vol_pc_ratio']}")
    print(f"  (< 0.7 = 偏多, 0.7-1.0 = 中性, > 1.0 = 偏空)")
    
    print(f"\n  --- 未平仓量 (Open Interest) ---")
    print(f"  总 Call OI:  {ratios['total_call_oi']:>12,}")
    print(f"  总 Put OI:   {ratios['total_put_oi']:>12,}")
    
    print(f"\n  --- 成交量 (Volume) ---")
    print(f"  总 Call Vol: {ratios['total_call_volume']:>12,}")
    print(f"  总 Put Vol:  {ratios['total_put_volume']:>12,}")
    
    print(f"\n  --- 隐含波动率 IV (OI加权平均) ---")
    print(f"  Call 平均 IV: {ratios['avg_call_iv']}%")
    print(f"  Put 平均 IV:  {ratios['avg_put_iv']}%")
    
    print(f"\n  --- 关键价位 ---")
    print(f"  最大 Call OI: ${ratios['max_call_oi_strike']} "
          f"({ratios['max_call_oi_value']:,} 张, 到期 {ratios['max_call_oi_expiry']})")
    print(f"  最大 Put OI:  ${ratios['max_put_oi_strike']} "
          f"({ratios['max_put_oi_value']:,} 张, 到期 {ratios['max_put_oi_expiry']})")
    print(f"  Max Pain:     ${max_pain}")
    print(f"  当前价距 Max Pain: {((current_price - max_pain) / max_pain * 100):+.1f}%")
    
    print(f"\n  --- 按到期日的 Put/Call Ratio ---")
    print(f"  (短期高 = 近期看空, 长期低 = 远期看多)")
    print(by_expiry.head(10).to_string(index=False))
    
    print(f"\n  --- OI 最大的合约 (资金集中区) ---")
    print(top_oi.to_string(index=False))
    
    print(f"\n{'='*60}")


def analyze(symbol: str, save_csv: bool = True):
    """
    一键分析某只股票的期权情绪.
    
    用法:
        analyze("NIO")
        analyze("TIGR")
        analyze("TSLA")
    """
    # 拉取期权链
    df = fetch_full_options_chain(symbol)
    if len(df) == 0:
        print("无数据, 退出")
        return
    
    # 当前股价
    ticker = yf.Ticker(symbol)
    current_price = ticker.history(period="1d")["Close"].iloc[-1]
    
    # 计算各项指标
    ratios = compute_put_call_ratios(df)
    by_expiry = compute_ratios_by_expiry(df)
    nearest_expiry = sorted(df["expiry"].unique())[0]
    max_pain = compute_max_pain(df, nearest_expiry)
    top_oi = find_top_oi_strikes(df, top_n=10)
    
    # 打印报告
    print_analysis_report(symbol, ratios, by_expiry, max_pain, top_oi, current_price)
    
    # 保存 CSV
    if save_csv:
        df.to_csv(f"{symbol}_options_chain.csv", index=False)
        by_expiry.to_csv(f"{symbol}_pc_ratio_by_expiry.csv", index=False)
        print(f"\n  已保存:")
        print(f"    {symbol}_options_chain.csv (完整期权链)")
        print(f"    {symbol}_pc_ratio_by_expiry.csv (按到期日的P/C Ratio)")
    
    return {
        "chain": df,
        "ratios": ratios,
        "by_expiry": by_expiry,
        "max_pain": max_pain,
        "top_oi": top_oi,
        "current_price": current_price,
    }


# ============================================================
# 主程序: 分析 NIO 和 TIGR
# ============================================================
if __name__ == "__main__":
    
    print("期权 Put/Call Ratio 分析器")
    print("数据源: Yahoo Finance (免费)")
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    
    # 分析 NIO
    nio_result = analyze("NIO")
    
    print("\n" + "="*60)
    print("  接下来分析 TIGR...")
    print("="*60)
    
    # 分析 TIGR
    tigr_result = analyze("TIGR")
    
    # 对比总结
    if nio_result and tigr_result:
        print(f"\n{'='*60}")
        print(f"  NIO vs TIGR 期权情绪对比")
        print(f"{'='*60}")
        print(f"{'指标':<25} {'NIO':>12} {'TIGR':>12}")
        print(f"{'-'*49}")
        print(f"{'股价':<25} ${nio_result['current_price']:>10.2f} ${tigr_result['current_price']:>10.2f}")
        print(f"{'OI Put/Call Ratio':<25} {nio_result['ratios']['oi_pc_ratio']:>12} {tigr_result['ratios']['oi_pc_ratio']:>12}")
        print(f"{'Vol Put/Call Ratio':<25} {nio_result['ratios']['vol_pc_ratio']:>12} {tigr_result['ratios']['vol_pc_ratio']:>12}")
        print(f"{'Call 平均 IV':<25} {nio_result['ratios']['avg_call_iv']:>10}% {tigr_result['ratios']['avg_call_iv']:>10}%")
        print(f"{'Put 平均 IV':<25} {nio_result['ratios']['avg_put_iv']:>10}% {tigr_result['ratios']['avg_put_iv']:>10}%")
        print(f"{'Max Pain':<25} ${nio_result['max_pain']:>10} ${tigr_result['max_pain']:>10}")
        print(f"{'最大 Call OI 行权价':<25} ${nio_result['ratios']['max_call_oi_strike']:>10} ${tigr_result['ratios']['max_call_oi_strike']:>10}")
        print(f"{'最大 Put OI 行权价':<25} ${nio_result['ratios']['max_put_oi_strike']:>10} ${tigr_result['ratios']['max_put_oi_strike']:>10}")
    
    print(f"\n{'='*60}")
    print("使用提示:")
    print(f"{'='*60}")
    print("""
1. 分析其他股票: 
   在 Python 里直接调用 analyze("TSLA") 或 analyze("AAPL")

2. 只拉数据不打印报告:
   df = fetch_full_options_chain("NIO")  # 拿到完整期权链 DataFrame

3. 单独计算某个到期日的 Max Pain:
   max_pain = compute_max_pain(df, "2026-06-20")

4. 看某个到期日的 OI 分布:
   sub = df[(df.expiry == "2026-06-20") & (df.side == "call")]
   sub.sort_values("openInterest", ascending=False).head(10)

5. 定时跑 (每天收盘后跑一次, 积累历史趋势):
   - 每天运行一次, CSV 文件会覆盖 (当日快照)
   - 如果要积累历史, 改文件名加上日期:
     df.to_csv(f"NIO_chain_{datetime.now().strftime('%Y%m%d')}.csv")
   - 然后用另一个脚本读取所有历史 CSV, 画 Put/Call Ratio 趋势图

6. 注意: yfinance 给的是当前快照, 不是历史数据.
   要积累历史, 需要每天跑一次并保存.
""")
