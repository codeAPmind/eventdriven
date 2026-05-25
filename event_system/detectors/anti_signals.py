"""
detectors/anti_signals.py — 反信号检测
返回 True 表示反信号触发，需要否决或扣分。
"""
import pandas as pd


def check_collusion(lhb_detail_df: pd.DataFrame, code: str) -> bool:
    """
    对倒检测：同一股票的买席与卖席出现相同营业部。
    """
    if lhb_detail_df.empty:
        return False
    try:
        code_col = next((c for c in lhb_detail_df.columns if "代码" in c), None)
        dir_col = next((c for c in lhb_detail_df.columns if "方向" in c or "买卖" in c), None)
        branch_col = next((c for c in lhb_detail_df.columns if "营业部" in c or "席位" in c), None)

        if not all([code_col, dir_col, branch_col]):
            return False

        sub = lhb_detail_df[lhb_detail_df[code_col].astype(str).str.strip() == code.strip()]
        if sub.empty:
            return False

        buy_branches = set(sub[sub[dir_col].str.contains("买", na=False)][branch_col])
        sell_branches = set(sub[sub[dir_col].str.contains("卖", na=False)][branch_col])
        return bool(buy_branches & sell_branches)
    except Exception:
        return False


def check_fake_breakout(daily_kline: pd.Series | dict) -> bool:
    """
    高开低走检测：开盘涨幅 > 5%，收盘涨幅 < 2%。
    daily_kline 需包含 open / close / prev_close 字段。
    """
    try:
        prev = float(daily_kline.get("prev_close", 0) or daily_kline.get("昨收", 0))
        open_p = float(daily_kline.get("open", 0) or daily_kline.get("开盘", 0))
        close_p = float(daily_kline.get("close", 0) or daily_kline.get("收盘", 0))
        if prev <= 0:
            return False
        open_pct = (open_p - prev) / prev
        close_pct = (close_p - prev) / prev
        return open_pct > 0.05 and close_pct < 0.02
    except Exception:
        return False


def check_st_stagnation(kline_df: pd.DataFrame, announcement_date: str) -> bool:
    """
    ST摘帽后放量滞涨：公告后若干日成交量放量但股价未涨。
    kline_df 需包含 date / volume / close 列，按日期升序。
    """
    if kline_df.empty or len(kline_df) < 3:
        return False
    try:
        date_col = next((c for c in kline_df.columns if "date" in c.lower() or "日期" in c), None)
        vol_col = next((c for c in kline_df.columns if "vol" in c.lower() or "成交量" in c), None)
        close_col = next((c for c in kline_df.columns if "close" in c.lower() or "收盘" in c), None)

        if not all([date_col, vol_col, close_col]):
            return False

        after = kline_df[kline_df[date_col] >= announcement_date].head(5)
        if len(after) < 2:
            return False

        avg_vol_before = kline_df[kline_df[date_col] < announcement_date][vol_col].tail(5).mean()
        avg_vol_after = after[vol_col].mean()
        price_chg = (after[close_col].iloc[-1] - after[close_col].iloc[0]) / after[close_col].iloc[0]

        # 成交量放大 50% 但股价涨幅不足 3%
        volume_surge = avg_vol_before > 0 and (avg_vol_after / avg_vol_before) > 1.5
        price_stagnant = price_chg < 0.03
        return volume_surge and price_stagnant
    except Exception:
        return False


def check_ipo_day_realization(event_type: str) -> bool:
    """
    利好兑现即利空：港股通生效日 / 摘帽正式日 / 财报披露日，提醒减仓。
    此处仅标记，具体日期由调度层判断。
    """
    realization_types = {"hk_inclusion_effective", "st_reversal_effective", "earnings_release"}
    return event_type in realization_types
