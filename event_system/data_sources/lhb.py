"""
data_sources/lhb.py — 龙虎榜数据抓取

三张表：
  stock_lhb_jgmmtj_em        — 机构买卖统计（机构买入净额，单位：元）
  stock_lhb_detail_em        — 全市场龙虎榜明细（上榜日 / 净买额 / 上榜原因）
  stock_lhb_stock_detail_em  — 单股席位明细（交易营业部名称 / 买入金额）
"""
import akshare as ak
import pandas as pd
from datetime import datetime

from config import (
    LHB_INST_NET_BUY_MIN,
    TOP_NAMED_INSTITUTIONS,
    TOP_ANON_INSTITUTIONS,
)


def fetch_lhb(date: str | None = None) -> pd.DataFrame:
    """
    抓取机构买卖统计表，返回机构净买入 > 阈值的记录。
    字段：代码 / 名称 / 机构买入净额(元) / 机构买入总额(元) / 机构卖出总额(元) / 上榜日期
    """
    date = date or datetime.now().strftime("%Y%m%d")
    threshold_yuan = LHB_INST_NET_BUY_MIN * 10_000  # 万元 → 元
    try:
        df = ak.stock_lhb_jgmmtj_em(start_date=date, end_date=date)
        if df is None or df.empty:
            return pd.DataFrame()
        df["机构买入净额"] = pd.to_numeric(df["机构买入净额"], errors="coerce").fillna(0)
        return df[df["机构买入净额"] > threshold_yuan].copy()
    except Exception as e:
        print(f"[LHB] 抓取失败: {e}")
        return pd.DataFrame()


def fetch_lhb_detail(date: str | None = None) -> pd.DataFrame:
    """全市场龙虎榜明细（用于对倒检测备用）。"""
    date = date or datetime.now().strftime("%Y%m%d")
    try:
        df = ak.stock_lhb_detail_em(start_date=date, end_date=date)
        return df if df is not None else pd.DataFrame()
    except Exception as e:
        print(f"[LHB detail] 抓取失败: {e}")
        return pd.DataFrame()


def fetch_lhb_seat_detail(code: str, date: str) -> pd.DataFrame:
    """
    获取单只股票的席位明细（买入方向）。
    返回字段：交易营业部名称 / 买入金额 / 卖出金额 / 净额
    """
    try:
        df = ak.stock_lhb_stock_detail_em(symbol=code, date=date, flag="买入")
        return df if df is not None else pd.DataFrame()
    except Exception as e:
        return pd.DataFrame()


def get_top_institution_seats(seat_df: pd.DataFrame) -> dict:
    """
    从席位明细中识别顶级机构买入情况。

    返回:
    {
        "named":  [{"name": "摩根大通...", "buy_yuan": 12345678}],  # 具名机构
        "anon":   [{"name": "机构专用",   "buy_yuan": 45678901}],  # 匿名席位
        "has_named": bool,
        "has_anon":  bool,
    }
    """
    result = {"named": [], "anon": [], "has_named": False, "has_anon": False}
    if seat_df.empty:
        return result

    name_col = "交易营业部名称"
    buy_col  = "买入金额"
    if name_col not in seat_df.columns:
        return result

    for _, row in seat_df.iterrows():
        seat = str(row.get(name_col, "")).strip()
        buy_amt = float(row.get(buy_col, 0) or 0)
        if buy_amt <= 0:
            continue

        # 具名顶级机构
        matched_named = next(
            (kw for kw in TOP_NAMED_INSTITUTIONS if kw in seat), None
        )
        if matched_named:
            result["named"].append({"name": seat, "buy_yuan": buy_amt})
            result["has_named"] = True
            continue

        # 匿名机构/北向专用席位
        matched_anon = next(
            (kw for kw in TOP_ANON_INSTITUTIONS if kw in seat), None
        )
        if matched_anon:
            result["anon"].append({"name": seat, "buy_yuan": buy_amt})
            result["has_anon"] = True

    return result


def enrich_lhb_with_seats(events: list[dict], date: str) -> list[dict]:
    """
    对 lhb_inst_buy 类型的事件批量抓取席位明细并注入。
    只对本类型事件调用，控制接口调用次数。
    """
    enriched = []
    for ev in events:
        ev = dict(ev)
        if ev.get("type") != "lhb_inst_buy":
            enriched.append(ev)
            continue

        code = ev.get("code", "")
        seat_df = fetch_lhb_seat_detail(code, date)
        seats   = get_top_institution_seats(seat_df)

        ev["seat_named"]     = seats["named"]    # [{name, buy_yuan}, ...]
        ev["seat_anon"]      = seats["anon"]
        ev["has_named_inst"] = seats["has_named"]
        ev["has_anon_inst"]  = seats["has_anon"]
        enriched.append(ev)

    return enriched
