"""
notify/feishu.py — 飞书机器人推送
"""
import requests
from datetime import datetime

from config import FEISHU_WEBHOOK

_TYPE_LABELS = {
    "lhb_inst_buy":    "龙虎榜机构买入",
    "st_reversal":     "ST摘帽预期",
    "hk_inclusion":    "港股通纳入",
    "asset_injection": "换壳/资产注入",
    "resumption":      "复牌",
    "macro_beat":      "宏观超预期",
}


def _event_to_line(ev: dict) -> str:
    label = _TYPE_LABELS.get(ev.get("type", ""), ev.get("type", ""))
    filtered = ev.get("filtered", False)
    status = f"⚠️ [过滤:{ev.get('filter_reason','')}]" if filtered else "✅"
    return (
        f"{status} [{ev['code']}] {ev.get('name', '')}  "
        f"| {label}  "
        f"| 评分:{ev.get('score', 0)}  "
        f"| 仓位上限:{ev.get('position_limit', 2)}%  "
        f"| 追涨上限:{int(ev.get('chase_limit_pct', 0.03)*100)}%  "
        f"| {ev.get('priority', '')}"
    )


def send_text(text: str) -> dict:
    if not FEISHU_WEBHOOK:
        print("[飞书] 未配置 FEISHU_WEBHOOK，跳过推送")
        return {}
    r = requests.post(FEISHU_WEBHOOK, json={"msg_type": "text", "content": {"text": text}}, timeout=10)
    return r.json()


def send_daily_report(events: list[dict], macro_event: str | None = None) -> dict:
    """
    发送每日事件报告卡片。
    """
    today = datetime.now().strftime("%Y-%m-%d")

    if not FEISHU_WEBHOOK:
        # 本地打印代替推送
        print(f"\n{'='*60}")
        print(f"  {today} 事件驱动系统日报")
        print(f"{'='*60}")
        if macro_event:
            print(f"[宏观提示] {macro_event}")
        if not events:
            print("  今日无显著事件")
        else:
            active = [e for e in events if not e.get("filtered")]
            filtered = [e for e in events if e.get("filtered")]
            if active:
                print(f"\n--- 候选标的 ({len(active)} 只) ---")
                for ev in active:
                    print(f"  {_event_to_line(ev)}")
            if filtered:
                print(f"\n--- 已过滤 ({len(filtered)} 只) ---")
                for ev in filtered:
                    print(f"  {_event_to_line(ev)}")
        print(f"{'='*60}\n")
        return {}

    elements = []
    if macro_event:
        elements.append({
            "tag": "div",
            "text": {"content": f"⚠️ **宏观提示**: {macro_event}", "tag": "lark_md"},
        })
        elements.append({"tag": "hr"})

    active = [e for e in events if not e.get("filtered")]
    filtered_ev = [e for e in events if e.get("filtered")]

    if not active and not filtered_ev:
        elements.append({
            "tag": "div",
            "text": {"content": "今日无显著事件", "tag": "lark_md"},
        })
    else:
        for ev in active:
            elements.append({
                "tag": "div",
                "text": {"content": _event_to_line(ev), "tag": "lark_md"},
            })
        if filtered_ev:
            elements.append({"tag": "hr"})
            elements.append({
                "tag": "div",
                "text": {
                    "content": f"**已过滤 {len(filtered_ev)} 只**（仓位约束）",
                    "tag": "lark_md",
                },
            })
            for ev in filtered_ev:
                elements.append({
                    "tag": "div",
                    "text": {"content": _event_to_line(ev), "tag": "lark_md"},
                })

    card = {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {"content": f"📊 {today} 事件驱动日报  共 {len(active)} 只候选", "tag": "plain_text"},
                "template": "blue",
            },
            "elements": elements,
        },
    }
    r = requests.post(FEISHU_WEBHOOK, json=card, timeout=10)
    return r.json()
