"""
data_sources/institutional.py — 机构持仓 / 大宗交易 / 融资融券
"""
import akshare as ak
import pandas as pd
from datetime import datetime


def fetch_block_trades(start_date: str | None = None, end_date: str | None = None) -> pd.DataFrame:
    """大宗交易日统计。"""
    today = datetime.now().strftime("%Y%m%d")
    start_date = start_date or today
    end_date = end_date or today
    try:
        df = ak.stock_dzjy_mrtj(start_date=start_date, end_date=end_date)
        return df if df is not None else pd.DataFrame()
    except Exception as e:
        print(f"[大宗交易] 抓取失败: {e}")
        return pd.DataFrame()


def fetch_margin_sse(start_date: str | None = None, end_date: str | None = None) -> pd.DataFrame:
    """沪市融资融券数据。"""
    today = datetime.now().strftime("%Y%m%d")
    start_date = start_date or today
    end_date = end_date or today
    try:
        df = ak.stock_margin_sse(start_date=start_date, end_date=end_date)
        return df if df is not None else pd.DataFrame()
    except Exception as e:
        print(f"[融资融券-沪] 抓取失败: {e}")
        return pd.DataFrame()


def fetch_margin_szse(date: str | None = None) -> pd.DataFrame:
    """深市融资融券数据。"""
    date = date or datetime.now().strftime("%Y%m%d")
    try:
        df = ak.stock_margin_szse(date=date)
        return df if df is not None else pd.DataFrame()
    except Exception as e:
        print(f"[融资融券-深] 抓取失败: {e}")
        return pd.DataFrame()


def check_block_trade_premium(df: pd.DataFrame, code: str) -> bool:
    """
    检测指定股票是否有大宗交易溢价成交（成交价 > 市价）。
    """
    if df.empty:
        return False
    try:
        code_col = next((c for c in df.columns if "代码" in c or "code" in c.lower()), None)
        if code_col is None:
            return False
        sub = df[df[code_col].astype(str).str.contains(code, na=False)]
        if sub.empty:
            return False
        # 溢价率列
        prem_col = next((c for c in sub.columns if "溢" in c or "premium" in c.lower()), None)
        if prem_col is None:
            return False
        val = pd.to_numeric(sub[prem_col].iloc[0], errors="coerce")
        return bool(val > 0)
    except Exception:
        return False
