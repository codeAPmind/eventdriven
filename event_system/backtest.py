"""
backtest.py — 事件后表现回测
验证每类事件在发生后 5 / 10 / 20 个交易日的收益表现。

用法:
    python backtest.py --event lhb_inst_buy --start 20240101 --end 20241231
"""
import argparse
import sys
from pathlib import Path
import pandas as pd
import akshare as ak
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).parent))

HOLD_WINDOWS = [5, 10, 20]  # 持有期（交易日）


def get_trade_dates(start: str, end: str) -> list[str]:
    """获取指定区间的交易日列表（A股）。"""
    try:
        df = ak.tool_trade_date_hist_sina()
        df.columns = ["date"]
        df["date"] = df["date"].astype(str).str.replace("-", "")
        dates = df[(df["date"] >= start) & (df["date"] <= end)]["date"].tolist()
        return sorted(dates)
    except Exception as e:
        print(f"[交易日历] 获取失败: {e}")
        return []


def get_stock_prices(code: str, start: str, end: str) -> pd.DataFrame:
    """
    获取个股日 K 线数据。
    """
    try:
        df = ak.stock_zh_a_hist(
            symbol=code,
            period="daily",
            start_date=start,
            end_date=end,
            adjust="hfq",
        )
        if df is None or df.empty:
            return pd.DataFrame()
        df = df.rename(columns={
            "日期": "date",
            "开盘": "open",
            "收盘": "close",
            "最高": "high",
            "最低": "low",
            "成交量": "volume",
        })
        df["date"] = df["date"].astype(str).str.replace("-", "")
        return df.sort_values("date").reset_index(drop=True)
    except Exception as e:
        print(f"[K线] {code} 获取失败: {e}")
        return pd.DataFrame()


def calc_return(prices: pd.DataFrame, entry_date: str, hold_days: int) -> float | None:
    """
    计算从 entry_date 开盘买入，持有 hold_days 交易日后收盘卖出的收益率。
    """
    after = prices[prices["date"] > entry_date].reset_index(drop=True)
    if len(after) < hold_days:
        return None
    entry_price = float(after.iloc[0]["open"])
    exit_price = float(after.iloc[hold_days - 1]["close"])
    if entry_price <= 0:
        return None
    return (exit_price - entry_price) / entry_price


def backtest_events(
    events: list[dict],
    start: str,
    end: str,
) -> pd.DataFrame:
    """
    对事件列表进行批量回测，返回结果 DataFrame。
    每个 event 需包含 code / type / date 字段。
    """
    records = []
    trade_dates = get_trade_dates(start, end)
    price_cache: dict[str, pd.DataFrame] = {}

    for ev in events:
        code = ev.get("code", "")
        ev_date = ev.get("date", "").replace("-", "")
        ev_type = ev.get("type", "")

        if not code or not ev_date or code == "MACRO":
            continue

        if code not in price_cache:
            # 多取 40 个交易日以覆盖持有期
            end_ext = (
                datetime.strptime(end, "%Y%m%d") + timedelta(days=60)
            ).strftime("%Y%m%d")
            price_cache[code] = get_stock_prices(code, start, end_ext)

        prices = price_cache[code]
        if prices.empty:
            continue

        row = {"code": code, "type": ev_type, "date": ev_date}
        for h in HOLD_WINDOWS:
            ret = calc_return(prices, ev_date, h)
            row[f"ret_{h}d"] = round(ret * 100, 2) if ret is not None else None
        records.append(row)

    df = pd.DataFrame(records)
    return df


def print_summary(df: pd.DataFrame):
    """按事件类型打印胜率和平均收益。"""
    if df.empty:
        print("无回测数据")
        return
    print(f"\n{'='*60}")
    print(f"  回测结果汇总  共 {len(df)} 个事件")
    print(f"{'='*60}")
    for ev_type, grp in df.groupby("type"):
        print(f"\n[{ev_type}]  样本数: {len(grp)}")
        for h in HOLD_WINDOWS:
            col = f"ret_{h}d"
            valid = grp[col].dropna()
            if valid.empty:
                continue
            win_rate = (valid > 0).mean() * 100
            avg_ret = valid.mean()
            print(f"  {h:>2}日持有  胜率: {win_rate:.1f}%  平均收益: {avg_ret:+.2f}%")


def main():
    parser = argparse.ArgumentParser(description="事件驱动回测")
    parser.add_argument("--start", default="20240101", help="回测起始日 YYYYMMDD")
    parser.add_argument("--end", default=datetime.now().strftime("%Y%m%d"), help="回测结束日 YYYYMMDD")
    parser.add_argument("--events-file", default=None, help="事件 JSON 文件路径（可选）")
    args = parser.parse_args()

    if args.events_file:
        import json
        with open(args.events_file) as f:
            events = json.load(f)
    else:
        print("未提供事件文件，使用示例数据（仅用于测试函数）")
        events = [
            {"code": "600519", "type": "lhb_inst_buy", "date": "2024-03-01"},
            {"code": "000858", "type": "st_reversal", "date": "2024-06-01"},
        ]

    result = backtest_events(events, args.start, args.end)
    print_summary(result)

    out = Path(__file__).parent / "storage" / "backtest_result.csv"
    result.to_csv(out, index=False, encoding="utf-8-sig")
    print(f"\n结果已保存: {out}")


if __name__ == "__main__":
    main()
