"""
data_sources/hk_connect.py — 港股通成分股变化监测 + 北向资金
"""
import json
import akshare as ak
import pandas as pd
from pathlib import Path

from config import STORAGE_DIR, NORTH_FLOW_DAYS

_CACHE = STORAGE_DIR / "hk_last.json"


def fetch_hk_connect_diff() -> dict[str, set]:
    """
    返回 {'added': set, 'removed': set}。
    stock_hk_ggt_components_em 使用 33.push2.eastmoney.com，
    该接口偶发连接重置（服务端行为），失败时静默跳过。
    """
    try:
        df = ak.stock_hk_ggt_components_em()
        if df is None or df.empty:
            return {"added": set(), "removed": set()}

        current_set: set[str] = set(df.iloc[:, 0].astype(str))

        if _CACHE.exists():
            with open(_CACHE) as f:
                last_set: set[str] = set(json.load(f))
        else:
            last_set = set()

        with open(_CACHE, "w") as f:
            json.dump(sorted(current_set), f, ensure_ascii=False)

        return {
            "added": current_set - last_set,
            "removed": last_set - current_set,
        }
    except Exception:
        # 接口不稳定，失败时不打印堆栈，主流程已有提示
        return {"added": set(), "removed": set()}


def fetch_north_flow(days: int = NORTH_FLOW_DAYS + 2) -> pd.DataFrame:
    """
    北向资金历史净买额。
    主接口：stock_hsgt_hist_em(symbol='北向资金')
    列：日期 / 当日成交净买额（亿元）
    """
    # 主接口
    try:
        df = ak.stock_hsgt_hist_em(symbol="北向资金")
        if df is not None and not df.empty:
            # 过滤掉净买额为 NaN 的行（数据有 1-2 日延迟）
            col = "当日成交净买额"
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
                valid = df.dropna(subset=[col])
                if not valid.empty:
                    return valid.tail(days).reset_index(drop=True)
    except Exception:
        pass

    # 备用：汇总沪股通 + 深股通
    try:
        sh = ak.stock_hsgt_hist_em(symbol="沪股通")
        sz = ak.stock_hsgt_hist_em(symbol="深股通")
        if sh is not None and sz is not None and not sh.empty and not sz.empty:
            date_col = "日期"
            flow_col = "当日成交净买额"
            if date_col in sh.columns and flow_col in sh.columns:
                sh[flow_col] = pd.to_numeric(sh[flow_col], errors="coerce")
                sz[flow_col] = pd.to_numeric(sz[flow_col], errors="coerce")
                merged = sh[[date_col, flow_col]].merge(
                    sz[[date_col, flow_col]], on=date_col, suffixes=("_sh", "_sz")
                )
                merged["net"] = merged[f"{flow_col}_sh"].fillna(0) + merged[f"{flow_col}_sz"].fillna(0)
                valid = merged.dropna(subset=[f"{flow_col}_sh", f"{flow_col}_sz"])
                if not valid.empty:
                    return valid.tail(days).rename(columns={"net": flow_col}).reset_index(drop=True)
    except Exception:
        pass

    print("[North Flow] 北向资金接口均不可用，跳过")
    return pd.DataFrame()
