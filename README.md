# eventdriven

事件驱动股票监测系统 — 基于龙虎榜、ST 摘帽、港股通、复牌、重组等事件信号，自动评分过滤并推送飞书日报。

## 快速开始

```bash
conda create -n eventdriven python=3.11 -y
conda activate eventdriven
pip install -r requirements.txt

# 复制并填写 .env（飞书 Webhook 等）
cp .env.example .env   # 或手动创建 .env

cd event_system
python main.py --dry-run
```

## 配置

在项目根目录创建 `.env`：

- `FEISHU_WEBHOOK` — 飞书群机器人 Webhook（必填）
- `FMP_API_KEY` — Financial Modeling Prep API（可选，外资持仓）

## 定时任务

参考 `crontab.example` 配置每日自动运行。
