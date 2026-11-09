# 训练闭环教程：生成 → 导出 → 训练 ACT → 仿真回放

一条闭环把仿真数据变成**会动的策略**：用本工具生成演示数据，导出 LeRobot
格式，微调 ACT，再把训练好的策略放回仿真器回放并输出 GIF。

## 前置条件

- RLBench DemoGen 已构建（`./build.sh && docker compose up -d`）；
- 训练环境（二选一）：
  - **A. 宿主机 conda（本文验证路径，需 NVIDIA GPU）**：见下方"训练环境准备"；
  - **B. Docker `demogen-train`（便携路径）**：`docker compose -f docker-compose.yml -f docker-compose.train.yml run --rm demogen-train bash`，
    容器内命令与下文相同（跳过 `conda run -n demogen-train` 前缀）。GPU 直通需主机安装
    nvidia-container-toolkit，否则为 CPU 训练（慢）。

### 训练环境准备（路径 A，一次性）

```bash
conda create -n demogen-train python=3.12 -y
conda run -n demogen-train pip install "lerobot[dataset,training]==0.7.0"
conda run -n demogen-train pip install cffi natsort pyquaternion
```

回放需要 PyRep/RLBench（复用本机 SAM2Act 项目的安装即可）：

```bash
export COPPELIASIM_ROOT="$HOME/Project/EmbodiedAI/CoppeliaSim_Player_V4_1_0_Ubuntu20_04"
export LD_LIBRARY_PATH="$COPPELIASIM_ROOT:$COPPELIASIM_ROOT/platforms"
export QT_QPA_PLATFORM_PLUGIN_PATH="$COPPELIASIM_ROOT/platforms"
export QT_PLUGIN_PATH="$COPPELIASIM_ROOT"
export PYTHONPATH="$HOME/Project/EmbodiedAI/sam2act/sam2act/libs/RLBench"
conda run -n demogen-train pip install --no-build-isolation "$HOME/Project/EmbodiedAI/sam2act/sam2act/libs/PyRep"
```

⚠️ 这些 export 只在当前终端生效（⛔ 勿写入 `~/.bashrc`，Qt 冲突风险）。

## Step 1 · 生成演示数据（约 20 分钟，15 集）

```bash
docker compose run --rm demogen generate --tasks reach_and_drag --episodes 15 --workers 2
```

## Step 2 · 导出 LeRobot 训练集（官方写入器）

```bash
conda run -n demogen-train python scripts/convert_lerobot.py \
  --src output --out train_data/lerobot --name reach_and_drag_act \
  --tasks reach_and_drag --cameras front --image-size 224 224 \
  --state pose --action-space eef-pose --writer official
```

`--writer official` 用 lerobot 自家 API 写盘，与安装的 lerobot 版本格式永远一致。

## Step 3 · 训练 ACT（RTX 4060 约 15 分钟 / 2000 步）

```bash
conda run -n demogen-train lerobot-train \
  --policy.type=act --policy.repo_id=local/reach_act \
  --dataset.repo_id=reach_and_drag_act --dataset.root=train_data/lerobot \
  --steps=2000 --batch_size=8 --save_freq=1000 --output_dir=outputs/train_act
```

检查点在 `outputs/train_act/checkpoints/`（`last/pretrained_model` 为最终策略）。
显存不足（8GB 卡偶发）时把 `--batch_size` 降为 4。

## Step 4 · 仿真回放评估 + GIF

```bash
conda run -n demogen-train xvfb-run -a python3 scripts/rollout_eval.py \
  --ckpt outputs/train_act --task reach_and_drag --episodes 5 \
  --action-space eef-pose --state pose --cameras front --image-size 224 224 \
  --max-steps 180 --gif-dir rollouts --report rollouts/report.json
```

产出：`rollouts/<task>_success_*.gif` / `_fail_*.gif` 与 `report.json`
（成功率、每集步数、指令文本）。动作空间映射：`eef-pose/joint` 直接驱动
`EndEffectorPoseViaPlanning/JointPosition`，`eef-delta` 在脚本内换算为绝对位姿。

## 实测参考结果

15 集 reach_and_drag 训练 2000 步后回放 5 集：**见 `rollouts/report.json`**
（本机 RTX 4060 + ACT + 单相机 front 224）。任务越难/数据越少成功率越低，
加数据（25–50 集）或步数可继续提升。

## 换任务 / 换策略

- 换任务：Step 1 的 `--tasks` 换成目标任务（建议先用 `close_jar`、`push_buttons`
  这类高成功率任务试水），后续命令的 `--task`/`--name` 同步替换；
- 换 Diffusion Policy：Step 3 的 `--policy.type=act` 换 `--policy.type=diffusion`，
  训练更慢但通常更稳；
- 换动作空间：`joint`（关节角，回放用 JointPosition）或 `eef-delta` 与导出参数保持一致即可。

## 排障

| 现象 | 处理 |
|---|---|
| `lerobot-train` 报 `'repo_id' argument missing` | 补 `--policy.repo_id=local/<任意名>` |
| `libcoppeliaSim.so.1` 找不到 | 检查 `LD_LIBRARY_PATH`（见训练环境准备） |
| 导出报 `Permission denied` | `output/` 为容器 root 属主，`--out` 用 `train_data/` 等用户目录 |
| OOM（显存） | `--batch_size=4`；仍不足则 `--image-size 128 128` 重导出 |
| 回放成功率很低 | 先看 GIF 里策略行为：数据 <15 集或训练 <2000 步常见；增加数据/步数 |
