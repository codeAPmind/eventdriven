"""
data_sources/macro.py — 宏观数据日历与超预期检测
"""
import akshare as ak
import pandas as pd
from datetime import datetime


# 按月内日期预设的重要宏观事件（固定发布规律）
_MONTHLY_SCHEDULE: dict[str, str] = {
    "09": "CPI/PPI数据发布",
    "10": "金融数据（社融、M2）",
    "15": "工业增加值、固定资产投资",
    "20": "LPR利率公布",
    "31": "制造业PMI（月末当日或次日）",
    "01": "制造业PMI（月初公布前月数据）",
}


def get_today_macro_event() -> str | None:
    """返回今日宏观事件描述，无则返回 None。"""
    day = datetime.now().strftime("%d")
    return _MONTHLY_SCHEDULE.get(day)


def fetch_cpi() -> pd.DataFrame:
    """拉取最近 CPI 月度数据。"""
    try:
        return ak.macro_china_cpi_monthly()
    except Exception as e:
        print(f"[Macro CPI] 抓取失败: {e}")
        return pd.DataFrame()


def _discover_pmi_func():
    """运行时扫描 ak 模块找制造业 PMI 函数。"""
    candidates = [
        "macro_china_pmi_manufacturing",
        "macro_china_nbs_pmi",
        "macro_china_official_pmi",
        "macro_china_pmi",
        "macro_china_manufacturing_pmi",
    ]
    for name in candidates:
        fn = getattr(ak, name, None)
        if fn is not None:
            return fn
    # 动态扫描
    for name in dir(ak):
        if "macro" in name and "pmi" in name.lower():
            return getattr(ak, name)
    return None


def fetch_pmi() -> pd.DataFrame:
    """拉取最近制造业 PMI 数据，运行时自动发现接口。"""
    fn = _discover_pmi_func()
    if fn is None:
        print("[Macro PMI] akshare 中未找到 PMI 接口，跳过")
        return pd.DataFrame()
    try:
        df = fn()
        if df is not None and not df.empty:
            return df
    except Exception as e:
        print(f"[Macro PMI] {fn.__name__} 调用失败: {e}")
    return pd.DataFrame()


def check_cpi_beat(threshold: float = 0.3) -> bool:
    """
    检测最新 CPI 是否超预期偏离 threshold 个百分点。
    简化实现：对比当月与上月的同比变化绝对值。
    """
    df = fetch_cpi()
    if df.empty or len(df) < 2:
        return False
    try:
        col = next((c for c in df.columns if "同比" in c or "yoy" in c.lower()), None)
        if col is None:
            return False
        vals = pd.to_numeric(df[col].tail(2), errors="coerce").dropna().values
        if len(vals) < 2:
            return False
        return abs(float(vals[-1]) - float(vals[-2])) > threshold
    except Exception:
        return False


def check_pmi_beat(threshold: float = 0.3) -> bool:
    """检测最新 PMI 是否超预期偏离。"""
    df = fetch_pmi()
    if df.empty or len(df) < 2:
        return False
    try:
        val_col = next(
            (c for c in df.columns if "值" in c or "pmi" in c.lower()),
            df.columns[-1],
        )
        vals = pd.to_numeric(df[val_col].tail(2), errors="coerce").dropna().values
        if len(vals) < 2:
            return False
        return abs(float(vals[-1]) - float(vals[-2])) > threshold
    except Exception:
        return False
