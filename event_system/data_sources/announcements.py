"""
data_sources/announcements.py — 公告抓取（ST摘帽 / 停复牌 / 重组）
"""
import akshare as ak
import pandas as pd
from datetime import datetime


def fetch_st_announcements() -> pd.DataFrame:
    """
    A股全量公告，过滤摘帽 / 撤销退市风险 / 撤销其他风险相关公告。
    """
    try:
        df = ak.stock_notice_report(symbol="全部")
        if df is None or df.empty:
            return pd.DataFrame()
        mask = df["公告标题"].str.contains(
            "撤销退市风险|撤销其他风险|摘帽|摘星|业绩预增|业绩扭亏",
            na=False,
            regex=True,
        )
        return df[mask].copy()
    except Exception as e:
        print(f"[ST公告] 抓取失败: {e}")
        return pd.DataFrame()


def fetch_resumption(date: str | None = None) -> pd.DataFrame:
    """
    停复牌信息，返回今日复牌标的（停牌 ≥ 30 天）。
    akshare stock_tfp_em 返回的是停牌中的股票列表，不是复牌事件；
    用 stock_zh_a_stop_em 或公告关键词做补充。
    """
    date = date or datetime.now().strftime("%Y%m%d")
    try:
        df = ak.stock_tfp_em(date=date)
        if df is None or df.empty:
            return pd.DataFrame()

        # 打印列名帮助调试（首次运行后可删）
        # print(f"  [复牌列名] {list(df.columns)}")

        # 优先按"类型"列过滤复牌；若列不存在则看"停牌原因"/"状态"
        type_col = next((c for c in df.columns if c in ("类型", "状态", "停复牌类型")), None)
        if type_col:
            mask = df[type_col].astype(str).str.contains("复牌", na=False)
            result = df[mask].copy()
        else:
            # 无法区分时直接返回空，避免误报 551 条
            return pd.DataFrame()

        # 仅保留停牌 ≥ 30 天
        days_col = next((c for c in result.columns if "天" in c or "day" in c.lower()), None)
        if days_col:
            result[days_col] = pd.to_numeric(result[days_col], errors="coerce").fillna(0)
            result = result[result[days_col] >= 30]

        return result.reset_index(drop=True)
    except Exception as e:
        print(f"[停复牌] 抓取失败: {e}")
        return pd.DataFrame()


def fetch_restructuring_announcements() -> pd.DataFrame:
    """
    从公告中筛选换壳 / 资产注入类（重大资产重组 + 控制权变更）。
    """
    try:
        df = ak.stock_notice_report(symbol="全部")
        if df is None or df.empty:
            return pd.DataFrame()
        mask = df["公告标题"].str.contains(
            "重大资产重组|控制权变更|资产注入|借壳",
            na=False,
            regex=True,
        )
        return df[mask].copy()
    except Exception as e:
        print(f"[重组公告] 抓取失败: {e}")
        return pd.DataFrame()
