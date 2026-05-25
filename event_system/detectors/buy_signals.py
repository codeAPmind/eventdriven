"""
detectors/buy_signals.py — 6 类买入信号检测
每个函数返回 list[dict]，每个 dict 代表一个候选事件。
"""
import pandas as pd
from datetime import datetime

from config import LHB_INST_NET_BUY_MIN, LHB_BUY_SELL_RATIO_RELAX, ST_MIN_NET_PROFIT


def _base_event(code: str, name: str, event_type: str, extra: dict | None = None) -> dict:
    ev = {
        "code": code,
        "name": name,
        "type": event_type,
        "date": datetime.now().strftime("%Y-%m-%d"),
    }
    if extra:
        ev.update(extra)
    return ev


# ── 1. 龙虎榜机构大额买入 ────────────────────────────────────────────────────

def detect_lhb_inst_buy(lhb_df: pd.DataFrame) -> list[dict]:
    """
    从机构买卖统计表（stock_lhb_jgmmtj_em）识别机构净买入超阈值的标的。
    已在 fetch_lhb 中按阈值过滤，此处直接遍历即可。
    宽松追涨条件：机构买入总额 / 卖出总额 ≥ LHB_BUY_SELL_RATIO_RELAX
    """
    if lhb_df.empty:
        return []

    events = []
    for _, row in lhb_df.iterrows():
        code = str(row.get("代码", "")).strip()
        name = str(row.get("名称", ""))
        net_buy = float(row.get("机构买入净额", 0))  # 元

        buy_amt = float(row.get("机构买入总额", 0))
        sell_amt = float(row.get("机构卖出总额", 0)) or 1
        relax = (buy_amt / sell_amt) >= LHB_BUY_SELL_RATIO_RELAX

        events.append(_base_event(code, name, "lhb_inst_buy", {
            "net_buy_yuan": net_buy,
            "chase_relax": relax,
        }))

    return events


# ── 2. ST 摘帽 ───────────────────────────────────────────────────────────────

def detect_st_reversal(st_df: pd.DataFrame) -> list[dict]:
    """
    从公告中识别 ST 摘帽 / 业绩扭亏预告信号。
    质量过滤：净利润预告 > ST_MIN_NET_PROFIT 万（若能解析到）。
    """
    if st_df.empty:
        return []

    events = []
    code_col = next((c for c in st_df.columns if "代码" in c), None)
    name_col = next((c for c in st_df.columns if "名称" in c or "简称" in c), None)
    title_col = next((c for c in st_df.columns if "标题" in c), None)

    for _, row in st_df.iterrows():
        code = str(row.get(code_col, "")).strip() if code_col else ""
        name = str(row.get(name_col, "")) if name_col else ""
        title = str(row.get(title_col, "")) if title_col else ""

        events.append(_base_event(code, name, "st_reversal", {
            "announcement_title": title,
        }))

    return events


# ── 3. 港股通纳入 ────────────────────────────────────────────────────────────

def detect_hk_inclusion(hk_diff: dict[str, set]) -> list[dict]:
    """
    将港股通新增标的转为事件。
    """
    return [
        _base_event(code, "", "hk_inclusion")
        for code in hk_diff.get("added", set())
    ]


# ── 4. 复牌 ─────────────────────────────────────────────────────────────────

def detect_resumption(resumption_df: pd.DataFrame) -> list[dict]:
    """
    识别今日复牌标的（停牌 ≥ 30 天，重组类优先）。
    """
    if resumption_df.empty:
        return []

    events = []
    code_col = next((c for c in resumption_df.columns if "代码" in c), None)
    name_col = next((c for c in resumption_df.columns if "名称" in c or "简称" in c), None)
    days_col = next((c for c in resumption_df.columns if "天" in c or "day" in c.lower()), None)
    reason_col = next((c for c in resumption_df.columns if "原因" in c or "类型" in c), None)

    for _, row in resumption_df.iterrows():
        code = str(row.get(code_col, "")).strip() if code_col else ""
        name = str(row.get(name_col, "")) if name_col else ""
        days = int(row.get(days_col, 0)) if days_col else 0
        reason = str(row.get(reason_col, "")) if reason_col else ""
        is_restructure = "重组" in reason or "资产" in reason

        events.append(_base_event(code, name, "resumption", {
            "stop_days": days,
            "is_restructure": is_restructure,
            "reason": reason,
        }))

    return events


# ── 5. 换壳 / 资产注入 ────────────────────────────────────────────────────────

def detect_asset_injection(restructure_df: pd.DataFrame) -> list[dict]:
    """
    识别重大资产重组 / 控制权变更公告。
    """
    if restructure_df.empty:
        return []

    events = []
    code_col = next((c for c in restructure_df.columns if "代码" in c), None)
    name_col = next((c for c in restructure_df.columns if "名称" in c or "简称" in c), None)
    title_col = next((c for c in restructure_df.columns if "标题" in c), None)

    for _, row in restructure_df.iterrows():
        code = str(row.get(code_col, "")).strip() if code_col else ""
        name = str(row.get(name_col, "")) if name_col else ""
        title = str(row.get(title_col, "")) if title_col else ""

        events.append(_base_event(code, name, "asset_injection", {
            "announcement_title": title,
        }))

    return events


# ── 6. 宏观数据发布 ──────────────────────────────────────────────────────────

def detect_macro_event(macro_event: str | None, cpi_beat: bool, pmi_beat: bool) -> list[dict]:
    """
    今日有宏观数据发布，且数据超预期偏离时，生成事件。
    """
    if not macro_event:
        return []
    if not (cpi_beat or pmi_beat):
        return []

    return [_base_event("MACRO", "宏观事件", "macro_beat", {
        "description": macro_event,
        "cpi_beat": cpi_beat,
        "pmi_beat": pmi_beat,
    })]
