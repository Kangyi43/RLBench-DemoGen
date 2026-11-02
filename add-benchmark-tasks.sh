#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

SRC="${1:-$HOME/Project/EmbodiedAI/sam2act/sam2act/libs/RLBench}"
TASKS="slide_block_to_color_target place_wine_at_rack_location sweep_to_dustpan_of_size"

if [ ! -d "$SRC/rlbench/tasks" ]; then
  echo "错误: $SRC 不是 RLBench 安装目录（缺 rlbench/tasks/）" >&2
  echo "用法: $0 <SAM2Act/PerAct 安装中的 RLBench 目录>" >&2
  exit 1
fi

echo "[..] 从 $SRC 补全基准任务（学术用途，须遵守上游许可条款）"
for t in $TASKS; do
  if [ -f "$SRC/rlbench/tasks/$t.py" ] && [ -f "$SRC/rlbench/task_ttms/$t.ttm" ]; then
    cp "$SRC/rlbench/tasks/$t.py" "tasks_extra/tasks/"
    cp "$SRC/rlbench/task_ttms/$t.ttm" "tasks_extra/task_ttms/"
    echo "    + $t"
  else
    echo "    - $t 未找到（跳过）" >&2
  fi
done
echo "[ok] 完成。重新构建镜像生效: ./build.sh"
