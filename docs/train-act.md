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

## Step 1 · 生成演示数据（约 90 分钟，100 集）

```bash
docker compose run --rm demogen generate --tasks push_buttons --episodes 100 --workers 1
```

## Step 2 · 导出 LeRobot 训练集（官方写入器）

```bash
conda run -n demogen-train python scripts/convert_lerobot.py \
  --src output --out train_data/lerobot --name push_buttons_act \
  --tasks push_buttons --cameras front --image-size 224 224 \
  --state pose --action-space eef-pose --writer official
```

`--writer official` 用 lerobot 自家 API 写盘，与安装的 lerobot 版本格式永远一致。

## Step 3 · 训练 ACT（RTX 4060 约 10 分钟 / 6000 步）

```bash
conda run -n demogen-train lerobot-train \
  --policy.type=act --policy.repo_id=local/push_act \
  --dataset.repo_id=push_buttons_act --dataset.root=train_data/lerobot \
  --steps=6000 --batch_size=8 --save_freq=2000 --output_dir=outputs/train_act \
  --save_checkpoint_to_hub=false --trackio.enable=false --policy.push_to_hub=false
```

检查点在 `outputs/train_act/checkpoints/`（`last/pretrained_model` 为最终策略）。
显存不足（8GB 卡偶发）时把 `--batch_size` 降为 4。

## Step 4 · 仿真回放评估 + GIF

```bash
conda run -n demogen-train xvfb-run -a python3 scripts/rollout_eval.py \
  --ckpt outputs/train_act/checkpoints/006000/pretrained_model --task push_buttons --episodes 10 \
  --action-space eef-pose --state pose --cameras front --image-size 224 224 \
  --max-steps 200 --gif-dir rollouts --report rollouts/report.json
```

产出：`rollouts/<task>_success_*.gif` / `_fail_*.gif` 与 `report.json`
（成功率、每集步数、指令文本）。动作空间映射：`eef-pose/joint` 直接驱动
`EndEffectorPoseViaPlanning/JointPosition`，`eef-delta` 在脚本内换算为绝对位姿。
规划失败时自动向当前位姿收缩目标重试（1.0/0.7/0.45 三档），提升弱策略的回放鲁棒性。

## 实测参考结果与调参经验

本机（RTX 4060）实测两条任务线，配方均为上文步骤：

| 任务 | 数据 | 训练 | 回放成功率（10 集） | 备注 |
|---|---|---|---|---|
| `push_buttons` | 100 集 | 6000 步 | **60%**（成功集 51–67 步） | 本文配方，推荐首选 |
| `reach_and_drag` | 200 集 | 10000 步 ×5 检查点 | 0% | 见下方"任务形态"经验 |

经验要点：

- **任务形态是第一位的**：无抓取的点按/推移类任务（`push_buttons`、`slide_block`）
  ACT 小数据即可出成功率；抓取-放置类任务（`reach_and_drag`）对目标位姿 ×
  摆放碰撞极敏感，小规模数据 + ACT 配方上限明显，换更大模型（Diffusion Policy）
  或 ≥500 集再战；
- **短训练/早期检查点往往更稳**：小数据上长训练会退化——200 集 reach_and_drag
  实测 2000 步检查点行为连贯、8000 步起完全退化（起步即卡）；每 2000 步存档，
  用 `rollout_eval.py` 逐检查点快筛（各 5 集）再选最优正式评估；
- **回放鲁棒性**（已内置）：目标收缩重试（1.0/0.7/0.45）+ 起始卡住时换摆
  放重种（每集最多 3 次）——弱策略与场景随机性叠加时的标配缓冲；
- 显存不足把 `--batch_size` 降为 4；`--policy.push_to_hub=false` 等开关
  可避免训练收尾时的联网推送超时。

## 换任务 / 换策略

- 换任务：Step 1 的 `--tasks` 换成目标任务，后续命令的 `--task`/`--name` 同步
  替换；难度预期见上文"任务形态"经验（点按/推移类易出成功率，抓取类需大
  数据或更强模型）；
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
