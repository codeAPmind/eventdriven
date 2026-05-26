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

_YUAN_TO_YI  = 1e8   # 元 → 亿
_YUAN_TO_WAN = 1e4   # 元 → 万


def _fmt_amount(yuan: float) -> str:
    if yuan >= _YUAN_TO_YI:
        return f"{yuan / _YUAN_TO_YI:.2f}亿"
    return f"{yuan / _YUAN_TO_WAN:.0f}万"


def _seat_lines(ev: dict) -> list[str]:
    """生成席位信息行（仅 lhb_inst_buy 类型）。"""
    lines = []
    named = ev.get("seat_named", [])
    anon  = ev.get("seat_anon",  [])
    if named:
        for s in named:
            lines.append(
                f"    🏦 【顶级席位】{s['name']}  买入 {_fmt_amount(s['buy_yuan'])}"
            )
    if anon:
        total_anon = sum(s["buy_yuan"] for s in anon)
        seat_names = " + ".join(s["name"] for s in anon)
        lines.append(
            f"    🏢 【机构席位】{seat_names}  合计买入 {_fmt_amount(total_anon)}"
        )
    return lines


def _event_to_lines(ev: dict) -> list[str]:
    """将单个事件转为多行文本（含席位、日期）。"""
    label     = _TYPE_LABELS.get(ev.get("type", ""), ev.get("type", ""))
    filtered  = ev.get("filtered", False)
    status    = f"⚠️ [过滤:{ev.get('filter_reason','')}]" if filtered else "✅"
    lhb_date  = ev.get("lhb_date", "")
    date_str  = f"  上榜日:{lhb_date}" if lhb_date else ""
    extra     = "/".join(ev.get("extra_types", []))
    extra_str = f"  +[{extra}]" if extra else ""

    main = (
        f"{status} **[{ev['code']}] {ev.get('name', '')}**"
        f"  | {label}{extra_str}"
        f"  | 评分:{ev.get('score', 0)}"
        f"  | 仓位:{ev.get('position_limit', 2)}%"
        f"  | 追涨:{int(ev.get('chase_limit_pct', 0.03)*100)}%"
        f"  | {ev.get('priority', '')}"
        f"{date_str}"
    )
    lines = [main]
    lines.extend(_seat_lines(ev))
    return lines


def send_text(text: str) -> dict:
    if not FEISHU_WEBHOOK:
        print("[飞书] 未配置 FEISHU_WEBHOOK，跳过推送")
        return {}
    r = requests.post(
        FEISHU_WEBHOOK,
        json={"msg_type": "text", "content": {"text": text}},
        timeout=10,
    )
    return r.json()


def send_daily_report(
    events: list[dict],
    macro_event: str | None = None,
    local_only: bool = False,
) -> dict:
    """
    发送每日事件报告。
    local_only=True 时强制本地打印（dry-run 模式），忽略 Webhook 配置。
    """
    today = datetime.now().strftime("%Y-%m-%d")

    # ── 本地打印模式 ─────────────────────────────────────────────────────────
    if local_only or not FEISHU_WEBHOOK:
        sep = "=" * 62
        print(f"\n{sep}")
        print(f"  {today}  事件驱动系统日报")
        print(sep)
        if macro_event:
            print(f"  ⚠️  宏观提示: {macro_event}")
        if not events:
            print("  今日无显著事件")
        else:
            active   = [e for e in events if not e.get("filtered")]
            filtered = [e for e in events if e.get("filtered")]
            if active:
                print(f"\n  ── 候选标的 ({len(active)} 只) ──")
                for ev in active:
                    for line in _event_to_lines(ev):
                        print(f"  {line}")
                    print()
            if filtered:
                print(f"  ── 已过滤 ({len(filtered)} 只，仓位约束） ──")
                for ev in filtered:
                    main_line = _event_to_lines(ev)[0]
                    print(f"  {main_line}")
        print(f"{sep}\n")
        return {}

    # ── 飞书卡片模式 ─────────────────────────────────────────────────────────
    elements = []
    if macro_event:
        elements.append({
            "tag": "div",
            "text": {"content": f"⚠️ **宏观提示**: {macro_event}", "tag": "lark_md"},
        })
        elements.append({"tag": "hr"})

    active     = [e for e in events if not e.get("filtered")]
    filtered_e = [e for e in events if e.get("filtered")]

    if not active and not filtered_e:
        elements.append({
            "tag": "div",
            "text": {"content": "今日无显著事件", "tag": "lark_md"},
        })
    else:
        for ev in active:
            content = "\n".join(_event_to_lines(ev))
            elements.append({
                "tag": "div",
                "text": {"content": content, "tag": "lark_md"},
            })
            elements.append({"tag": "hr"})

        if filtered_e:
            elements.append({
                "tag": "div",
                "text": {
                    "content": f"**已过滤 {len(filtered_e)} 只**（仓位约束）",
                    "tag": "lark_md",
                },
            })
            for ev in filtered_e:
                elements.append({
                    "tag": "div",
                    "text": {
                        "content": _event_to_lines(ev)[0],
                        "tag": "lark_md",
                    },
                })

    card = {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {
                    "content": f"📊 {today} 事件驱动日报  候选 {len(active)} 只",
                    "tag": "plain_text",
                },
                "template": "blue",
            },
            "elements": elements,
        },
    }
    r = requests.post(FEISHU_WEBHOOK, json=card, timeout=10)
    return r.json()
