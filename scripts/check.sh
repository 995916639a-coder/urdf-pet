#!/usr/bin/env bash
# L0–L3 一把梭。改完任何代码先跑这条,再说话(见 CLAUDE.md)。
#
#   bash scripts/check.sh          # 全跑
#   bash scripts/check.sh fast     # 只跑 L0 + L1(不碰渲染,秒级)
#
# 环境:先 conda activate urdf-pet;没激活时脚本会退回到该环境的绝对路径。
set -euo pipefail
cd "$(dirname "$0")/.."

ENV_DIR="${CONDA_PREFIX:-$HOME/miniforge3/envs/urdf-pet}"
PY="$ENV_DIR/bin/python"
[ -x "$PY" ] || PY="$(command -v python)"

# pip 装的 PySide6 需要 libxcb-cursor.so.0,系统里没有(装它要 root)。
# conda activate 时 activate.d 会加这个路径;这里对没激活的情况兜底。
if [ -d "$ENV_DIR/x11compat" ]; then
  export LD_LIBRARY_PATH="$ENV_DIR/x11compat${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
fi

FAST="${1:-}"

step() { printf '\n\033[1m=== %s ===\033[0m\n' "$1"; }

step "L0 ruff check"
"$PY" -m ruff check .

step "L0 ruff format --check"
"$PY" -m ruff format --check .

if [ "$FAST" = "fast" ]; then
  step "L1 运动学(fast 模式,跳过 L2/L3)"
  "$PY" -m pytest tests/test_kinematics.py -q
  printf '\n\033[32m✓ fast 检查通过(未覆盖渲染与 Qt)\033[0m\n'
  exit 0
fi

# L2 离屏渲染不需要显示器(VTK 退回 EGL/OSMesa);
# L3 的 QtInteractor 需要一个真实 X 显示,本机用 :0,CI 里用 xvfb-run。
step "L1 + L2 + L3 全量测试"
"$PY" -m pytest tests -q

printf '\n\033[32m✓ L0–L3 全部通过\033[0m\n'
