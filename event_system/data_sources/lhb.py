"""
data_sources/lhb.py — 龙虎榜数据抓取

两张表：
  stock_lhb_jgmmtj_em  — 机构买卖统计（机构买入净额，单位：元）
  stock_lhb_detail_em  — 全市场龙虎榜明细（用于对倒检测备用）
"""
import akshare as ak
import pandas as pd
from datetime import datetime

from config import LHB_INST_NET_BUY_MIN  # 单位：万元


def fetch_lhb(date: str | None = None) -> pd.DataFrame:
    """
    抓取机构买卖统计表，返回机构净买入 > 阈值 的记录。
    字段：代码 / 名称 / 机构买入净额(元) / 机构买入总额(元) / 机构卖出总额(元)
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
    """
    全市场龙虎榜明细（含营业部方向），用于对倒检测。
    注意：该接口不含营业部名称，对倒检测降级为 False。
    """
    date = date or datetime.now().strftime("%Y%m%d")
    try:
        df = ak.stock_lhb_detail_em(start_date=date, end_date=date)
        return df if df is not None else pd.DataFrame()
    except Exception as e:
        print(f"[LHB detail] 抓取失败: {e}")
        return pd.DataFrame()
