"""
config.py — 全局配置
"""
import os
from pathlib import Path

# ── 路径 ──────────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
STORAGE_DIR = BASE_DIR / "storage"
STORAGE_DIR.mkdir(exist_ok=True)

# ── 代理（Clash 默认 HTTP 端口 7890）────────────────────────────────────────
CLASH_HOST = os.getenv("CLASH_HOST", "127.0.0.1")
CLASH_HTTP_PORT = int(os.getenv("CLASH_HTTP_PORT", "7890"))
USE_PROXY = os.getenv("USE_PROXY", "true").lower() == "true"

# ── 飞书 Webhook ──────────────────────────────────────────────────────────────
FEISHU_WEBHOOK = os.getenv("FEISHU_WEBHOOK", "")

# ── FMP API ───────────────────────────────────────────────────────────────────
FMP_API_KEY = os.getenv("FMP_API_KEY", "")

# ── 信号阈值 ──────────────────────────────────────────────────────────────────
LHB_INST_NET_BUY_MIN = 5000          # 万元，龙虎榜机构净买入下限
LHB_BUY_SELL_RATIO_RELAX = 2.0      # 买/卖倍数宽松条件（可追 5%）
ST_MIN_NET_PROFIT = 500              # 万元，ST摘帽业绩预告净利润下限
NORTH_FLOW_DAYS = 3                  # 北向资金连续净买入天数
CPI_PMI_DEVIATION = 0.3             # CPI/PMI 超预期偏离阈值（百分点）

# ── 评分阈值 ──────────────────────────────────────────────────────────────────
# 单信号底分：lhb=30 / asset_injection=25 / st=20 / hk=20 / resumption=15
# 多信号叠加后才能突破 60；北向/大宗等补充数据失效时单信号仍可见
SCORE_CANDIDATE = 20                 # 进入候选池（单个信号即可见）
SCORE_FOCUS = 60                     # 多信号叠加重点关注

# ── 仓位上限（%） ────────────────────────────────────────────────────────────
POSITION_LIMITS = {
    (60, 70): 2,
    (70, 80): 5,
    (80, 90): 8,
    (90, 101): 10,
}
MAX_SAME_EVENT_POSITION = 20         # 同类事件总仓位上限（%）
MAX_DAILY_NEW_POSITION = 15          # 单日新增事件买入总仓位上限（%）
MAX_HOLDINGS = 10                    # 最大持仓事件数

# ── 追涨上限 ─────────────────────────────────────────────────────────────────
CHASE_LIMIT_DEFAULT = 0.03           # 默认不追超 3%
CHASE_LIMIT_RELAX = 0.05             # 宽松条件下追 5%
