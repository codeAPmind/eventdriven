"""
engine/scoring.py — 事件评分与仓位建议

设计关键：评分是「叠加制」，同一只股票触发多个信号时分数累加。
因此 rank_events 调用前先 merge_events_by_code 合并同股多信号。
"""
from config import (
    SCORE_CANDIDATE,
    SCORE_FOCUS,
    POSITION_LIMITS,
    CHASE_LIMIT_DEFAULT,
    CHASE_LIMIT_RELAX,
)

# 基础评分表（每个信号类型的底分）
_BASE_SCORES: dict[str, int] = {
    "lhb_inst_buy":    30,
    "st_reversal":     20,
    "hk_inclusion":    20,
    "asset_injection": 25,
    "resumption":      15,
    "macro_beat":      10,
}

# 加分项（context flag → 分值）
_BONUS_SCORES: dict[str, int] = {
    "north_buying":    15,
    "block_premium":   10,
    "beat_earnings":   25,
    "technical_break": 15,
}

# 事件类型优先级（用于合并后选主类型展示）
_TYPE_PRIORITY = [
    "lhb_inst_buy", "asset_injection", "st_reversal",
    "hk_inclusion", "resumption", "macro_beat",
]


def merge_events_by_code(raw_events: list[dict]) -> list[dict]:
    """
    将同一股票的多个信号合并为一个富 context 事件，确保分数能叠加。

    合并规则：
    - 所有触发的 type 记入 _all_types
    - 主 type 取优先级最高的
    - boolean flag 取 OR（任一为 True 即计入）
    - 字符串字段取首个非空值
    """
    by_code: dict[str, dict] = {}
    for ev in raw_events:
        code = ev.get("code", "")
        if not code:
            continue
        if code not in by_code:
            merged = dict(ev)
            merged["_all_types"] = {ev["type"]}
            by_code[code] = merged
        else:
            merged = by_code[code]
            merged["_all_types"].add(ev["type"])
            for k, v in ev.items():
                if k == "type":
                    continue
                if isinstance(v, bool):
                    merged[k] = merged.get(k, False) or v
                elif k not in merged or not merged[k]:
                    merged[k] = v

    result = []
    for ev in by_code.values():
        all_types = ev.pop("_all_types", {ev["type"]})
        # 选最高优先级 type 作为主类型
        for t in _TYPE_PRIORITY:
            if t in all_types:
                ev["type"] = t
                break
        # 次级信号记录（用于展示和额外加分）
        ev["extra_types"] = sorted(all_types - {ev["type"]})
        result.append(ev)

    return result


def score_event(event: dict) -> int:
    """
    计算单个（已合并）事件的综合评分。
    反信号：对倒 → 直接 0；高开低走 → -30。
    """
    if event.get("collusion"):
        return 0

    # 主信号底分
    base = _BASE_SCORES.get(event.get("type", ""), 0)

    # 次级信号叠加底分
    for extra in event.get("extra_types", []):
        base += _BASE_SCORES.get(extra, 0)

    # 加分项
    for key, bonus in _BONUS_SCORES.items():
        if event.get(key):
            base += bonus

    # 复牌且是重组类
    if event.get("type") == "resumption" and event.get("is_restructure"):
        base += 10

    # 反信号扣分
    if event.get("fake_breakout"):
        base -= 30

    return max(0, base)


def get_position_limit(score: int) -> int:
    """根据评分返回单股仓位上限（%）。"""
    for (lo, hi), limit in POSITION_LIMITS.items():
        if lo <= score < hi:
            return limit
    return 2


def get_chase_limit(event: dict) -> float:
    return CHASE_LIMIT_RELAX if event.get("chase_relax") else CHASE_LIMIT_DEFAULT


def get_priority_label(score: int) -> str:
    if score >= 80:
        return "★★★ 极强信号"
    if score >= SCORE_FOCUS:   # 60
        return "★★ 重点关注"
    if score >= 40:
        return "★ 候选池"
    return "观察"


def rank_events(events: list[dict]) -> list[dict]:
    """
    1. 先按股票代码合并多信号
    2. 评分
    3. 过滤低于 SCORE_CANDIDATE 的
    4. 降序排列
    """
    merged = merge_events_by_code(events)
    result = []
    for ev in merged:
        score = score_event(ev)
        if score < SCORE_CANDIDATE:
            continue
        ev = dict(ev)
        ev["score"] = score
        ev["position_limit"] = get_position_limit(score)
        ev["chase_limit_pct"] = get_chase_limit(ev)
        ev["priority"] = get_priority_label(score)
        result.append(ev)

    return sorted(result, key=lambda x: -x["score"])
