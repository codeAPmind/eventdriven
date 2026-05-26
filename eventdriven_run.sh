#!/usr/bin/env bash
# EventDriven 定时任务入口（cron 专用）
set -euo pipefail

PROJECT_DIR="/Users/openclaw/openclaw_workspace/EventDriven"
RUNTIME_DIR="/Users/openclaw/openclaw_workspace/eventdriven_runtime"
LOG_FILE="${RUNTIME_DIR}/eventdriven_cron.log"
CONDA_BIN="/Users/openclaw/miniforge3/bin/conda"
CONDA_ENV="eventdriven"
NOW="$(date '+%Y-%m-%d %H:%M:%S')"

mkdir -p "$RUNTIME_DIR"

{
  echo "============================================================"
  echo "[INFO] Task start: ${NOW}"
  echo "[INFO] Project dir: ${PROJECT_DIR}"
} >> "$LOG_FILE"

cd "${PROJECT_DIR}/event_system"

if [ -f "${PROJECT_DIR}/.env" ]; then
  set -a
  # shellcheck disable=SC1091
  source "${PROJECT_DIR}/.env"
  set +a
fi

export PYTHONUNBUFFERED=1
export PATH="${HOME}/miniforge3/bin:${HOME}/miniconda3/bin:/opt/homebrew/bin:/usr/local/bin:${PATH:-}"

"${CONDA_BIN}" run -n "${CONDA_ENV}" python main.py >> "$LOG_FILE" 2>&1
