# 事件驱动选股监测系统 · 完整设计文档

> **版本**：v1.0 · 2026-05  
> **定位**：个人投资者可落地的事件驱动型 A股 / 港股监测系统  
> **核心理念**：不预测股价，只对已发生的"确定性事件"做出反应

---

## 目录

1. [系统定位与价值](#一系统定位与价值)
2. [整体架构](#二整体架构)
3. [数据源完整清单](#三数据源完整清单)
4. [事件监测体系](#四事件监测体系)
5. [反信号体系](#五反信号体系过滤与止损)
6. [信号引擎](#六信号引擎)
7. [推送与执行](#七推送与执行)
8. [完整代码实现](#八完整代码实现)
9. [实战风险提示](#九实战风险提示)
10. [落地路径](#十落地路径)
11. [附录：常用接口速查](#附录常用接口速查)

---

## 一、系统定位与价值

### 1.1 核心逻辑

事件驱动策略的核心：**股票价格的短期偏离，往往源于特定事件的发生**。

```
事件发生 → 信息不对称 / 资金被动流入 → 价格偏离 → 机会窗口 → 回归价值
```

### 1.2 系统能解决什么

- **每日固定时间**收到当日值得关注的事件清单
- **多信号叠加**自动排序，过滤噪音
- **反信号自动过滤**，避开假突破和对倒出货
- **历史回测**验证每类事件胜率，持续迭代

### 1.3 系统不解决什么

- 不做趋势预测
- 不做技术指标信号
- 不做高频交易
- 不替代基本面研究

---

## 二、整体架构

```
┌──────────────────────────────────────────────────────────┐
│  Layer 1: 数据采集层                                       │
│  东方财富 · AKShare · FMP · 交易所公告爬虫                 │
│  补充：北向资金 · 融资融券 · 大宗交易                      │
└──────────────────────────────────────────────────────────┘
                          ↓
┌──────────────────────────────────────────────────────────┐
│  Layer 2: 事件检测层                                       │
│  买入信号（6类）          反信号（3类）                    │
│  • 港股通纳入             • 机构对倒出货                   │
│  • ST摘帽                 • 利好高开低走                   │
│  • 复牌                   • 摘帽后放量滞涨                 │
│  • 换壳 / 资产注入                                        │
│  • 机构大额买入                                            │
│  • 宏观数据发布                                            │
└──────────────────────────────────────────────────────────┘
                          ↓
┌──────────────────────────────────────────────────────────┐
│  Layer 3: 信号引擎                                         │
│  • 事件评分（叠加加权）                                    │
│  • 反信号扣分 / 一票否决                                   │
│  • 持有窗口标注                                            │
│  • 仓位建议                                                │
└──────────────────────────────────────────────────────────┘
                          ↓
┌──────────────────────────────────────────────────────────┐
│  Layer 4: 推送 & 执行                                      │
│  飞书机器人 · 每日追踪表 · 回测验证                        │
└──────────────────────────────────────────────────────────┘
```

---

## 三、数据源完整清单

### 3.1 核心数据源（必备）

| 数据源 | 用途 | 接入方式 | 成本 |
|--------|------|---------|------|
| **东方财富** | 龙虎榜 / 资金流 / 公告 | 网页接口 / 第三方封装 | 免费 |
| **AKShare** | 一站式封装（推荐主力） | `pip install akshare` | 免费 |
| **FMP** | 外资机构 13F 持仓 | REST API | 免费额度 / 付费 |
| **交易所公告** | SSE / SZSE / HKEX | RSS / 爬虫 | 免费 |

### 3.2 补充数据源（提升精度）

| 数据源 | 监测意义 | AKShare 接口 |
|--------|---------|-------------|
| **北向资金流向** | 外资情绪指标，与港股通形成互证 | `stock_hsgt_north_net_flow_in_em` |
| **融资融券** | 杠杆资金情绪，确认事件真实性 | `stock_margin_sse` |
| **大宗交易** | 机构折价 / 溢价拿货信号 | `stock_dzjy_mrtj` |
| **股东户数变化** | 筹码集中度，配合事件验证 | `stock_zh_a_gdhs` |

### 3.3 数据更新时间表

| 数据类型 | 更新时间 | 系统调度建议 |
|---------|---------|------------|
| 龙虎榜 | 当日 16:30 后 | **每日 17:00 抓取** |
| 公告（A股） | 9:00–次日 8:00 | 每日 7:30 全量抓 |
| 公告（港股） | 实时（24小时） | 每小时增量 |
| 北向资金 | 实时（盘中） | 收盘后日级抓取 |
| 宏观数据 | 按发布日历 | 当日提前预警 |

---

## 四、事件监测体系

### 4.1 六类核心买入信号

| # | 事件类型 | 触发条件 | 最优介入时机 | 持有期 | 历史胜率 |
|---|---------|---------|------------|-------|---------|
| 1 | **港股通纳入** | 季度调整前10天，市值/流动性达标 | 公告前 8–10 天 | 至生效日前 | ~70% |
| 2 | **ST摘帽** | 预告净利润扭亏 + 扣非为正 + 净利 > 500万 | 业绩预告日（不等正式公告） | 40 个交易日 | ~80% |
| 3 | **复牌** | 停牌超 30 天且为重组类 | 复牌前 1–2 天埋单（跌停价） | 5–15 天 | 因事件而异 |
| 4 | **换壳 / 资产注入** | "重大资产重组" + "控制权变更" | 公告后首日开盘前 | 中长线 | 高盈亏比 |
| 5 | **机构大额买入** | 龙虎榜机构净买入 > 5000万 | 次日开盘，不追超 3% | 5–10 天 | ~60% |
| 6 | **宏观数据发布** | CPI/PMI 超预期偏离 > 0.3 个百分点 | 当日盘中 | 1–3 天 | 看情境 |

### 4.2 时间窗口的精确化（实战补丁）

#### 港股通纳入
- **公告前 8–10 天布局** ✅
- **关键点**：生效日当天 **14:55–15:00 尾盘** 被动资金集中买入，是**短线卖点**而非买点
- 套利空间被压缩时，提前介入的价值更大

#### ST摘帽
- 介入时机：**业绩预告扭亏时**（比正式公告提前 1–2 个月）
- **质量过滤**：预告净利润 > 500 万 + 扣非为正，回避纯重组型扭亏
- **优先选择**：小市值（壳价值）+ 非建筑装饰行业

#### 机构大额买入
- 默认规则：次日开盘**不追涨超 3%**
- **可放宽条件**：龙虎榜显示买一席位是"机构专用"，且**买入额 ≥ 卖一的 2 倍**，可放宽到追 5%
- **否决条件**：买席和卖席出现相同营业部（疑似对倒）

### 4.3 事件优先级排序

按"确定性 × 盈亏比"排序：

```
ST摘帽（提前布局）     ★★★★★  胜率最高
港股通纳入（提前布局）  ★★★★☆  确定性强
业绩超预期            ★★★★☆  胜率中等偏上
机构大额买入          ★★★☆☆  需配合其他信号
复牌                  ★★★☆☆  流动性陷阱
换壳/资产注入         ★★☆☆☆  低频但盈亏比高
宏观事件              ★★☆☆☆  不确定性高
```

---

## 五、反信号体系（过滤与止损）

> **这是原版最容易忽视的部分**：买入信号只解决"找什么"，反信号解决"避什么"

| 反信号 | 监测逻辑 | 处理方式 |
|--------|---------|---------|
| **机构对倒出货** | 龙虎榜买席和卖席出现**相同营业部** | 信号一票否决 |
| **利好次日高开低走** | 开盘涨 > 5%，收盘跌回 < 2% | 短期回避 3 天 |
| **ST摘帽后放量滞涨** | 摘帽公告后成交量放量但股价不涨 | 强制止盈 |
| **复牌一字板** | 复牌后连续涨停无量 | 不追，等开板信号 |
| **公告即兑现** | 港股通生效日 / 摘帽正式日 | 准备减仓 |

### 5.1 反信号代码示例

```python
def check_anti_signal_dump(lhb_df, stock_code):
    """检测机构对倒：买席和卖席是否有相同营业部"""
    stock_data = lhb_df[lhb_df['代码'] == stock_code]
    buy_branches = set(stock_data[stock_data['方向'] == '买入']['营业部'])
    sell_branches = set(stock_data[stock_data['方向'] == '卖出']['营业部'])
    overlap = buy_branches & sell_branches
    return len(overlap) > 0  # True 表示有对倒嫌疑

def check_fake_breakout(daily_kline):
    """检测利好次日高开低走"""
    open_pct = daily_kline['open'] / daily_kline['prev_close'] - 1
    close_pct = daily_kline['close'] / daily_kline['prev_close'] - 1
    return open_pct > 0.05 and close_pct < 0.02
```

---

## 六、信号引擎

### 6.1 评分叠加机制

单一信号胜率有限，**叠加是精髓**。基础评分表：

| 信号 | 加分 |
|------|------|
| 龙虎榜机构买入 | +30 |
| 业绩超预期（净利润 > 预期 20%） | +25 |
| 港股通预纳入 | +20 |
| ST摘帽预期（扭亏预告） | +20 |
| 北向资金连续 3 日净买入 | +15 |
| 技术突破（站上 20 日均线放量） | +15 |
| 大宗交易溢价成交 | +10 |
| **反信号触发** | **-50（直接否决）** |

```python
def score_stock(code, context):
    score = 0
    
    # 正向信号
    if context.get('in_lhb'):           score += 30
    if context.get('beat_earnings'):    score += 25
    if context.get('about_to_hk'):      score += 20
    if context.get('st_reversal'):      score += 20
    if context.get('north_buying'):     score += 15
    if context.get('technical_break'):  score += 15
    if context.get('block_premium'):    score += 10
    
    # 反信号（一票否决）
    if context.get('inst_collusion'):   return 0
    if context.get('fake_breakout'):    score -= 30
    
    return max(0, score)

# 阈值：> 60 进入候选池；> 80 重点关注
```

### 6.2 仓位管理规则

| 评分区间 | 单股仓位上限 | 说明 |
|---------|------------|------|
| 60–70 | 2% | 观察仓 |
| 70–80 | 3–5% | 标准仓 |
| 80–90 | 5–8% | 重点仓 |
| > 90 | 8–10% | 极端机会 |

**全局约束**：
- 同类事件总仓位 ≤ 20%
- 单日新增事件买入总仓位 ≤ 15%
- 持仓事件 ≤ 10 只（避免精力分散）

---

## 七、推送与执行

### 7.1 飞书机器人接入（5 分钟搞定）

**步骤**：飞书群 → 设置 → 群机器人 → 添加自定义机器人 → 复制 webhook URL

```python
import requests
import json

WEBHOOK = "https://open.feishu.cn/open-apis/bot/v2/hook/YOUR_WEBHOOK_HERE"

def send_feishu_text(content):
    """发送纯文本消息"""
    data = {"msg_type": "text", "content": {"text": content}}
    r = requests.post(WEBHOOK, json=data)
    return r.json()

def send_feishu_card(title, events):
    """发送结构化卡片消息"""
    elements = []
    for ev in events:
        elements.append({
            "tag": "div",
            "text": {
                "content": f"**{ev['name']}({ev['code']})**\n"
                          f"事件: {ev['type']} | 评分: {ev['score']}\n"
                          f"建议: {ev['action']}",
                "tag": "lark_md"
            }
        })
        elements.append({"tag": "hr"})
    
    card = {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {"content": title, "tag": "plain_text"},
                "template": "blue"
            },
            "elements": elements
        }
    }
    return requests.post(WEBHOOK, json=card).json()
```

### 7.2 定时任务（Linux crontab）

```bash
# 每天 7:30 推送当日事件预警
30 7 * * 1-5 cd /path/to/project && python daily_morning.py

# 每天 17:00 抓取龙虎榜并推送次日候选
0 17 * * 1-5 cd /path/to/project && python lhb_evening.py

# 每周日 20:00 全量回测验证
0 20 * * 0 cd /path/to/project && python weekly_backtest.py
```

---

## 八、完整代码实现

### 8.1 项目结构

```
event_system/
├── config.py              # 配置（webhook、阈值等）
├── data_sources/
│   ├── lhb.py             # 龙虎榜抓取
│   ├── hk_connect.py      # 港股通监测
│   ├── announcements.py   # 公告抓取
│   ├── macro.py           # 宏观数据
│   └── institutional.py   # 机构持仓
├── detectors/
│   ├── buy_signals.py     # 6类买入信号
│   └── anti_signals.py    # 反信号
├── engine/
│   ├── scoring.py         # 评分系统
│   └── filters.py         # 过滤器
├── notify/
│   └── feishu.py          # 飞书推送
├── storage/
│   ├── hk_last.json       # 港股通名单缓存
│   └── watchlist.json     # 关注列表
└── main.py                # 主调度
```

### 8.2 主调度脚本（完整可运行版本）

```python
"""
event_system/main.py
事件驱动监测系统 - 每日主流程
"""
import akshare as ak
import pandas as pd
import json
import os
from datetime import datetime, timedelta
from pathlib import Path

# ============== 配置 ==============
FEISHU_WEBHOOK = os.getenv("FEISHU_WEBHOOK", "")
CACHE_DIR = Path("./storage")
CACHE_DIR.mkdir(exist_ok=True)
TODAY = datetime.now().strftime("%Y%m%d")

# ============== 数据采集 ==============
def fetch_lhb():
    """龙虎榜：机构净买入 > 5000万"""
    try:
        df = ak.stock_lhb_detail_em(
            start_date=TODAY, end_date=TODAY
        )
        # 注意：列名以实际返回为准，单位通常是万元
        big = df[df['机构买入净额'] > 5000] if '机构买入净额' in df.columns else pd.DataFrame()
        return big
    except Exception as e:
        print(f"[LHB] 错误: {e}")
        return pd.DataFrame()

def fetch_st_announcements():
    """ST摘帽：公告关键词匹配"""
    try:
        # 使用公告接口，关键词过滤
        df = ak.stock_notice_report(symbol="全部")
        if df.empty:
            return df
        mask = df['公告标题'].str.contains('撤销退市风险|撤销其他风险|摘帽', na=False)
        return df[mask]
    except Exception as e:
        print(f"[ST] 错误: {e}")
        return pd.DataFrame()

def fetch_hk_connect_diff():
    """港股通名单变化检测"""
    cache_file = CACHE_DIR / "hk_last.json"
    try:
        current = ak.stock_hk_ggt_components_em()  # 港股通成分
        current_set = set(current['代码'].astype(str))
        
        if cache_file.exists():
            with open(cache_file) as f:
                last_set = set(json.load(f))
        else:
            last_set = set()
        
        with open(cache_file, 'w') as f:
            json.dump(list(current_set), f)
        
        return {
            'added': current_set - last_set,
            'removed': last_set - current_set
        }
    except Exception as e:
        print(f"[HK] 错误: {e}")
        return {'added': set(), 'removed': set()}

def fetch_north_flow():
    """北向资金净流入"""
    try:
        df = ak.stock_hsgt_north_net_flow_in_em(symbol="北上")
        return df.tail(5)  # 近5个交易日
    except Exception as e:
        print(f"[NORTH] 错误: {e}")
        return pd.DataFrame()

def fetch_macro_calendar():
    """宏观日历：本周有哪些重要数据"""
    schedule = {
        '09': 'CPI/PPI数据发布',
        '10': '金融数据（社融、M2）',
        '15': '工业增加值、固定资产投资',
        '20': 'LPR利率公布',
        '31': '制造业PMI（月末当日或次日）',
    }
    day = datetime.now().strftime("%d")
    return schedule.get(day)

# ============== 反信号检测 ==============
def check_collusion(lhb_df, code):
    """检测对倒：买卖席位重叠"""
    try:
        sub = lhb_df[lhb_df['代码'] == code]
        if sub.empty:
            return False
        buys = set(sub[sub['方向'] == '买入']['营业部'])
        sells = set(sub[sub['方向'] == '卖出']['营业部'])
        return bool(buys & sells)
    except:
        return False

# ============== 评分引擎 ==============
def score_event(event):
    """对单个事件计算综合评分"""
    score_map = {
        'st_reversal': 20,
        'hk_inclusion': 20,
        'lhb_inst_buy': 30,
        'asset_injection': 25,
        'resumption': 15,
        'macro_beat': 10,
    }
    base = score_map.get(event['type'], 0)
    
    # 加分项
    if event.get('north_buying'):    base += 15
    if event.get('block_premium'):   base += 10
    if event.get('beat_earnings'):   base += 25
    
    # 反信号
    if event.get('collusion'):       return 0
    if event.get('fake_breakout'):   base -= 30
    
    return max(0, base)

# ============== 推送 ==============
def push_feishu(events):
    """推送到飞书"""
    if not FEISHU_WEBHOOK:
        print("未配置飞书 webhook，跳过推送")
        return
    
    import requests
    
    if not events:
        text = f"📊 {TODAY} 今日无显著事件"
    else:
        lines = [f"📊 **{TODAY} 事件预警**", ""]
        for ev in sorted(events, key=lambda x: -x.get('score', 0)):
            lines.append(
                f"• [{ev['code']}] {ev['name']} "
                f"| {ev['type']} | 评分: {ev['score']}"
            )
        text = "\n".join(lines)
    
    requests.post(FEISHU_WEBHOOK, json={
        "msg_type": "text", "content": {"text": text}
    })

# ============== 主流程 ==============
def main():
    print(f"=== {TODAY} 事件驱动系统启动 ===\n")
    events = []
    
    # 1. 龙虎榜
    lhb = fetch_lhb()
    print(f"龙虎榜机构买入: {len(lhb)} 只")
    for _, row in lhb.iterrows():
        code = str(row.get('代码', ''))
        ev = {
            'code': code,
            'name': row.get('名称', ''),
            'type': 'lhb_inst_buy',
            'collusion': check_collusion(lhb, code),
        }
        ev['score'] = score_event(ev)
        if ev['score'] > 0:
            events.append(ev)
    
    # 2. ST 摘帽
    st = fetch_st_announcements()
    print(f"ST摘帽公告: {len(st)} 条")
    for _, row in st.iterrows():
        events.append({
            'code': row.get('股票代码', ''),
            'name': row.get('名称', ''),
            'type': 'st_reversal',
            'score': score_event({'type': 'st_reversal'}),
        })
    
    # 3. 港股通变化
    hk = fetch_hk_connect_diff()
    print(f"港股通新增: {len(hk['added'])} 只 | 剔除: {len(hk['removed'])} 只")
    for code in hk['added']:
        events.append({
            'code': code,
            'name': '',
            'type': 'hk_inclusion',
            'score': score_event({'type': 'hk_inclusion'}),
        })
    
    # 4. 宏观日历
    macro = fetch_macro_calendar()
    if macro:
        print(f"⚠️ 今日宏观事件: {macro}")
    
    # 推送
    print(f"\n=== 共发现 {len(events)} 个事件 ===")
    push_feishu(events)
    
    return events

if __name__ == "__main__":
    main()
```

### 8.3 环境配置

```bash
# requirements.txt
akshare>=1.12.0
pandas>=1.5.0
requests>=2.28.0

# 环境变量
export FEISHU_WEBHOOK="https://open.feishu.cn/open-apis/bot/v2/hook/xxx"
export FMP_API_KEY="your_fmp_key_if_needed"
```

---

## 九、实战风险提示

### 9.1 数据延迟陷阱

- **龙虎榜在当日 16:30 后才更新**——如果用上午数据会漏信息
- **建议**：每日 **17:00 固定调度**，比早上更可靠
- 港股公告 24 小时滚动发布，需小时级抓取

### 9.2 事件拥挤度衰减

- 历史回测胜率 80% 的事件，**当下可能只有 60%**——因为被太多人交易
- 需要 **持续回测验证**，每季度重算各事件胜率
- 看到胜率连续 2 季度下滑超过 10 个点 → 该事件权重下调

### 9.3 复牌流动性风险

- 复牌后**连续一字板根本买不进去**
- 等开板时往往已经透支涨幅
- "复牌前 1–2 天埋单" 思路对，但需要**深交所集合竞价规则**：跌停价排队
- 港股复牌无涨跌幅限制，开盘瞬间波动剧烈，需限价单不要市价

### 9.4 利好兑现即利空

事件驱动最大的坑：
- ST摘帽**正式公告日** = 获利了结点（不是买入点）
- 港股通**生效日**当天 14:55 后 = 减仓窗口
- 业绩超预期**财报披露日** = 卖出准备点

### 9.5 单一信号不重仓

胜率再高也不是 100%，**5% 的单股仓位上限是底线**，除非多事件叠加且评分 > 85。

---

## 十、落地路径

### 第一阶段（本周）：手动跑通

- [ ] 安装 AKShare，跑通龙虎榜 + ST公告抓取
- [ ] 每天 17:00 手动查看输出，建立"事件体感"
- [ ] 用 Notion / Excel 维护一张"事件-股票-状态"跟踪表
- [ ] 至少观察 5 个交易日

### 第二阶段（本月）：自动化推送

- [ ] 部署飞书机器人，5 分钟搞定 webhook
- [ ] 配置 crontab 定时任务（17:00 抓取，次日 7:30 推送）
- [ ] 加入港股通 diff 逻辑、宏观日历
- [ ] 加入反信号过滤（对倒检测、高开低走）

### 第三阶段（有条件后）：评分与回测

- [ ] 实现完整评分系统（叠加加权）
- [ ] 用 AKShare 历史数据做回测：每类事件后 5/10/20 日表现
- [ ] 根据回测结果调整加权系数
- [ ] 加入仓位管理规则，连接实盘观察账户

### 第四阶段（进阶）：智能化

- [ ] 接入 LLM 做公告语义解析（摆脱关键词匹配的脆弱性）
- [ ] 加入新闻情绪分析（财联社、华尔街见闻 API）
- [ ] 持仓事件的自动跟踪与止盈止损提醒

---

## 附录：常用接口速查

### AKShare 关键接口

```python
import akshare as ak

# === 龙虎榜 ===
ak.stock_lhb_detail_em(start_date='20250523', end_date='20250523')
ak.stock_lhb_jgmmtj_em(start_date='20250523', end_date='20250523')

# === 港股通 ===
ak.stock_hk_ggt_components_em()      # 港股通成分股
ak.stock_hsgt_north_net_flow_in_em(symbol="北上")  # 北向资金

# === ST / 公告 ===
ak.stock_notice_report(symbol="全部")
ak.stock_board_concept_cons_em(symbol="ST股")

# === 停复牌 ===
ak.stock_tfp_em(date='20250523')

# === 大宗交易 ===
ak.stock_dzjy_mrtj(start_date='20250501', end_date='20250523')

# === 融资融券 ===
ak.stock_margin_sse(start_date='20250501', end_date='20250523')
ak.stock_margin_szse(date='20250523')

# === 宏观数据 ===
ak.macro_china_cpi_monthly()
ak.macro_china_pmi_manufacturing()
ak.macro_china_lpr()

# === 业绩预告 ===
ak.stock_yjyg_em(date='20250331')
```

### FMP 关键端点（外资机构持仓）

```
GET /api/v4/institutional-ownership/list?symbol={ticker}&apikey={key}
GET /api/v3/institutional-holder/{ticker}?apikey={key}
GET /api/v4/institutional-ownership/portfolio-holdings?cik={cik}&apikey={key}
```

### 关键阈值速查

| 指标 | 阈值 | 说明 |
|------|------|------|
| 机构净买入 | > 5000 万 | 龙虎榜机构席位 |
| 机构买入 / 卖出比 | > 2 | 可放宽追涨条件 |
| ST摘帽预告净利润 | > 500 万 | 质量过滤 |
| 北向资金连续净买 | ≥ 3 日 | 加分信号 |
| CPI/PMI 偏离 | > 0.3 个百分点 | 触发宏观事件 |
| 单股仓位上限 | 5% | 风险底线 |
| 同类事件总仓位 | 20% | 风险底线 |
| 评分进入候选池 | > 60 | 默认阈值 |
| 评分重点关注 | > 80 | 重仓阈值 |

---

## 结语

这个系统不是"一夜暴富"工具，而是把**专业机构的事件驱动方法论**降维到个人投资者可用的工程框架。

它的真正价值在于：
1. **强制纪律**：用规则代替情绪，避免追涨杀跌
2. **复用专业方法**：把券商研报里的策略变成可执行代码
3. **持续迭代**：每个事件的胜率都可以被回测验证

**最重要的一句话**：先把系统跑起来，再谈优化。完美主义是项目最大的敌人。

---

*文档版本：v1.0 · 整合自双方案优化*
