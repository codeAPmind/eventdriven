"""
main.py — 事件驱动监测系统每日主流程
用法：python main.py [--date YYYYMMDD] [--dry-run]
"""
import argparse
import sys
import os
from datetime import datetime
from pathlib import Path

# 确保包内相对导入能找到 config
sys.path.insert(0, str(Path(__file__).parent))

# 自动加载项目根目录的 .env 文件
_env_file = Path(__file__).parent.parent / ".env"
if _env_file.exists():
    for _line in _env_file.read_text().splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _v = _line.split("=", 1)
            if _v.strip():
                os.environ.setdefault(_k.strip(), _v.strip())

# Clash 代理：仅用于境外接口（FMP 等），国内 akshare 域名直连
_use_proxy = os.getenv("USE_PROXY", "true").lower() == "true"
if _use_proxy:
    _proxy = f"http://{os.getenv('CLASH_HOST', '127.0.0.1')}:{os.getenv('CLASH_HTTP_PORT', '7890')}"
    os.environ.setdefault("HTTP_PROXY", _proxy)
    os.environ.setdefault("HTTPS_PROXY", _proxy)
    os.environ.setdefault("http_proxy", _proxy)
    os.environ.setdefault("https_proxy", _proxy)
    # 国内域名直连，避免 Clash CONNECT 隧道被目标服务器拒绝
    _no_proxy = (
        "localhost,127.0.0.1,::1,"
        ".eastmoney.com,.akshare.com,.sina.com,.sina.com.cn,"
        ".hexun.com,.10jqka.com.cn,.jqka.com.cn,"
        ".szse.cn,.sse.com.cn,.csindex.com.cn,.hkex.com.hk,"
        ".gtimg.com,.qq.com,.163.com,.ifeng.com"
    )
    os.environ.setdefault("NO_PROXY", _no_proxy)
    os.environ.setdefault("no_proxy", _no_proxy)

import pandas as pd
from config import NORTH_FLOW_DAYS
from data_sources.lhb import fetch_lhb, fetch_lhb_detail, enrich_lhb_with_seats
from data_sources.hk_connect import fetch_hk_connect_diff, fetch_north_flow
from data_sources.announcements import (
    fetch_st_announcements,
    fetch_resumption,
    fetch_restructuring_announcements,
)
from data_sources.macro import get_today_macro_event, check_cpi_beat, check_pmi_beat
from data_sources.institutional import fetch_block_trades, check_block_trade_premium

from detectors.buy_signals import (
    detect_lhb_inst_buy,
    detect_st_reversal,
    detect_hk_inclusion,
    detect_resumption,
    detect_asset_injection,
    detect_macro_event,
)
from detectors.anti_signals import check_collusion, check_fake_breakout

from engine.scoring import rank_events
from engine.filters import apply_portfolio_constraints

from notify.feishu import send_daily_report


def run(date: str | None = None, dry_run: bool = False, verbose: bool = False) -> list[dict]:
    date = date or datetime.now().strftime("%Y%m%d")
    print(f"\n{'='*60}")
    print(f"  事件驱动系统启动  {date}")
    print(f"{'='*60}")

    # ── 1. 数据采集 ──────────────────────────────────────────────────────────
    print("\n[1/5] 数据采集中...")

    lhb = fetch_lhb(date)
    lhb_detail = fetch_lhb_detail(date)
    # 上榜日期直接从数据中读取（格式 YYYY-MM-DD）
    lhb_date_display = date[:4] + "-" + date[4:6] + "-" + date[6:]
    if "上榜日期" in lhb.columns:
        lhb_date_display = str(lhb["上榜日期"].iloc[0]) if not lhb.empty else lhb_date_display
    print(f"  龙虎榜机构净买入: {len(lhb)} 只  上榜日: {lhb_date_display}")

    st_df = fetch_st_announcements()
    print(f"  ST摘帽/扭亏公告:  {len(st_df)} 条")

    hk_diff = fetch_hk_connect_diff()
    if not hk_diff["added"] and not hk_diff["removed"]:
        print("  港股通: 0 变化（若看到 ProxyError，请在 Clash 规则中将 *.push2.eastmoney.com 加入直连）")
    else:
        print(f"  港股通新增: {len(hk_diff['added'])} 只 | 剔除: {len(hk_diff['removed'])} 只")

    resumption_df = fetch_resumption(date)
    print(f"  今日复牌:         {len(resumption_df)} 只")

    restructure_df = fetch_restructuring_announcements()
    print(f"  重组/换壳公告:    {len(restructure_df)} 条")

    north_df = fetch_north_flow()
    block_df = fetch_block_trades(date, date)

    macro_event = get_today_macro_event()
    cpi_beat = check_cpi_beat()
    pmi_beat = check_pmi_beat()
    if macro_event:
        print(f"  [宏观] {macro_event}  CPI超预期={cpi_beat}  PMI超预期={pmi_beat}")

    # ── 2. 北向连续净买入判断 ─────────────────────────────────────────────────
    north_consecutive = False
    if not north_df.empty:
        flow_col = next(
            (c for c in north_df.columns if "净买额" in c or "net" in c.lower()),
            next((c for c in north_df.columns if "净" in c), None),
        )
        if flow_col and len(north_df) >= NORTH_FLOW_DAYS:
            last_n = pd.to_numeric(north_df[flow_col].tail(NORTH_FLOW_DAYS), errors="coerce").dropna()
            north_consecutive = len(last_n) >= NORTH_FLOW_DAYS and all(v > 0 for v in last_n)
            if north_consecutive:
                print(f"  北向资金连续 {NORTH_FLOW_DAYS} 日净买入 ✅")

    # ── 3. 信号检测 ──────────────────────────────────────────────────────────
    print("\n[2/5] 信号检测...")

    raw_events: list[dict] = []
    raw_events += detect_lhb_inst_buy(lhb)
    raw_events += detect_st_reversal(st_df)
    raw_events += detect_hk_inclusion(hk_diff)
    raw_events += detect_resumption(resumption_df)
    raw_events += detect_asset_injection(restructure_df)
    raw_events += detect_macro_event(macro_event, cpi_beat, pmi_beat)

    print(f"  原始事件数: {len(raw_events)}")

    # ── 4. 反信号注入 ─────────────────────────────────────────────────────────
    print("\n[3/5] 反信号检测...")

    enriched: list[dict] = []
    for ev in raw_events:
        code = ev.get("code", "")
        ev = dict(ev)

        # 对倒检测
        ev["collusion"] = check_collusion(lhb_detail, code)

        # 北向资金加成
        ev["north_buying"] = north_consecutive

        # 大宗溢价加成
        ev["block_premium"] = check_block_trade_premium(block_df, code)

        enriched.append(ev)

    collusion_count = sum(1 for e in enriched if e.get("collusion"))
    print(f"  对倒嫌疑: {collusion_count} 只（已一票否决）")

    # ── 4b. 席位明细抓取（仅 lhb_inst_buy 类型，逐股调用）────────────────────
    print("\n[3b/5] 席位识别...")
    enriched = enrich_lhb_with_seats(enriched, date)
    # 注入上榜日期
    for ev in enriched:
        if ev.get("type") == "lhb_inst_buy":
            ev.setdefault("lhb_date", lhb_date_display)
    named_cnt = sum(1 for e in enriched if e.get("has_named_inst"))
    anon_cnt  = sum(1 for e in enriched if e.get("has_anon_inst"))
    print(f"  具名顶级机构: {named_cnt} 只  |  匿名机构/北向席位: {anon_cnt} 只")

    # ── 5. 评分 & 过滤 ────────────────────────────────────────────────────────
    print("\n[4/5] 评分与过滤...")

    from engine.scoring import merge_events_by_code
    merged_events = merge_events_by_code(enriched)   # 保存供 verbose 使用
    ranked = rank_events(enriched)
    final = apply_portfolio_constraints(ranked)

    active = [e for e in final if not e.get("filtered")]
    print(f"  候选标的: {len(active)} 只 | 已过滤: {len(final)-len(active)} 只")

    # ── verbose：打印所有原始事件得分（含未过阈值的）────────────────────────
    if verbose and merged_events:
        print("\n[详细] 所有检测事件得分（含未达阈值）:")
        from engine.scoring import score_event
        from notify.feishu import _fmt_amount
        for ev in sorted(merged_events, key=lambda x: -score_event(x)):
            s = score_event(ev)
            extra = "/".join(ev.get("extra_types", []))
            label = f"+[{extra}]" if extra else ""
            print(f"  [{ev['code']}] {ev.get('name',''):8s} 类型:{ev['type']}{label:20s} 得分:{s:3d}  {ev.get('lhb_date','')}")
            for seat in ev.get("seat_named", []):
                print(f"      🏦 【顶级席位】{seat['name']}  买入 {_fmt_amount(seat['buy_yuan'])}")
            for seat in ev.get("seat_anon", []):
                print(f"      🏢 【机构席位】{seat['name']}  买入 {_fmt_amount(seat['buy_yuan'])}")

    # ── 6. 推送 ───────────────────────────────────────────────────────────────
    print("\n[5/5] 推送结果...")

    if dry_run:
        print("  [dry-run] 本地预览，不推送飞书:")
        send_daily_report(final, macro_event, local_only=True)
    else:
        send_daily_report(final, macro_event)

    return final


def main():
    parser = argparse.ArgumentParser(description="事件驱动股票监测系统")
    parser.add_argument("--date", type=str, default=None, help="指定日期 YYYYMMDD，默认今日")
    parser.add_argument("--dry-run", action="store_true", help="不推送飞书，仅本地打印")
    parser.add_argument("--verbose", action="store_true", help="打印所有检测事件及得分（含未达阈值）")
    args = parser.parse_args()
    run(date=args.date, dry_run=args.dry_run, verbose=args.verbose)


if __name__ == "__main__":
    main()
