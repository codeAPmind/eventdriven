"""
engine/filters.py — 全局过滤器（仓位约束、持仓数量）
"""
from config import MAX_SAME_EVENT_POSITION, MAX_DAILY_NEW_POSITION, MAX_HOLDINGS


def apply_portfolio_constraints(
    ranked_events: list[dict],
    existing_holdings: list[dict] | None = None,
) -> list[dict]:
    """
    按全局仓位约束过滤候选事件列表：
    1. 同类事件总仓位 ≤ 20%
    2. 单日新增仓位 ≤ 15%
    3. 持仓事件 ≤ 10 只

    existing_holdings: 当前已持仓事件列表（含 type / position_limit 字段）
    """
    existing_holdings = existing_holdings or []

    # 统计已有同类仓位
    type_used: dict[str, int] = {}
    for h in existing_holdings:
        t = h.get("type", "")
        type_used[t] = type_used.get(t, 0) + h.get("position_limit", 0)

    holding_count = len(existing_holdings)
    daily_new = 0
    result = []

    for ev in ranked_events:
        ev_type = ev.get("type", "")
        pos = ev.get("position_limit", 2)

        if holding_count >= MAX_HOLDINGS:
            ev = {**ev, "filter_reason": f"持仓已满 {MAX_HOLDINGS} 只"}
            ev["filtered"] = True
            result.append(ev)
            continue

        if type_used.get(ev_type, 0) + pos > MAX_SAME_EVENT_POSITION:
            ev = {**ev, "filter_reason": f"同类事件仓位超限 {MAX_SAME_EVENT_POSITION}%"}
            ev["filtered"] = True
            result.append(ev)
            continue

        if daily_new + pos > MAX_DAILY_NEW_POSITION:
            ev = {**ev, "filter_reason": f"单日新增仓位超限 {MAX_DAILY_NEW_POSITION}%"}
            ev["filtered"] = True
            result.append(ev)
            continue

        # 通过过滤
        type_used[ev_type] = type_used.get(ev_type, 0) + pos
        daily_new += pos
        holding_count += 1
        ev = {**ev, "filtered": False}
        result.append(ev)

    return result
