# LeRobot 导出说明

把本工具生成的原生数据集转换为 **LeRobot v2.1** 格式（HuggingFace `lerobot`
生态的事实标准，可直接用于 ACT / Diffusion Policy 等训练管线）。

## 用法

```bash
docker compose run --rm demogen convert \
  --src /data --out /data/lerobot --name my_dataset \
  --action-space eef-pose --state pose --fps 30
```

输出目录（`./output/lerobot/`）为标准 LeRobot 数据集：

```
lerobot/
├── meta/
│   ├── info.json          # 特征定义 / 分片 / 统计入口
│   ├── stats.json         # state/action/timestamp 的 min/max/mean/std
│   ├── tasks.jsonl        # 语言指令 → task_index
│   └── episodes.jsonl     # 每集路径与长度
├── data/chunk-000/episode_000000.parquet ...
└── videos/chunk-000/observation.images.<cam>/episode_000000.mp4 ...
```

## 参数

| 参数 | 默认 | 说明 |
|---|---|---|
| `--src` | `/data` | 原生数据根目录 |
| `--out` | `/data/lerobot` | 输出目录 |
| `--tasks` | 全部 | 逗号分隔任务名 |
| `--cameras` | 全部 5 个 | 导出为视频的相机（如 `front,wrist`） |
| `--image-size W H` | 保持原尺寸 | 缩放帧（如 `224 224`，OpenVLA 常用） |
| `--state` | `pose` | 观测状态预设（见下） |
| `--action-space` | `eef-pose` | 动作空间预设（见下） |
| `--fps` | 30 | 标称帧率（原生为步进数据，无真实时间戳） |
| `--val-ratio` | 0.0 | 划出该比例为 `test` split |

## 状态与动作预设

| 预设 | 维度 | 内容 |
|---|---|---|
| state `pose` | 8 | 末端位姿(7) + 夹爪开合(1) |
| state `full` | 17 | 上述 + 夹爪两指(2) + 关节位置(7) |
| action `eef-pose` | 8 | 下一步绝对末端位姿(7) + 开合(1)，末帧重复 |
| action `eef-delta` | 7 | 位置增量(3) + 旋转轴角增量(3) + 开合增量(1) |
| action `joint` | 8 | 下一步关节位置(7) + 开合(1) |

四元数为 PyRep 约定 `(Qx,Qy,Qz,Qw)`；`eef-delta` 的旋转增量经符号规范化
（q 与 -q 双覆盖处理）。

## 与训练的衔接

- **lerobot 训练**（ACT / Diffusion Policy）：`pip install lerobot`（建议
  0.2.x，匹配 v2.1 格式），`LeRobotDataset` 直接加载本目录；
- **图像尺寸**：ACT/DP 常用 128 或 224；OpenVLA 用 `--image-size 224 224 --cameras front`；
- 语言指令取每集 `language_instructions` 第一条作为 task 字符串。

> 格式兼容性说明：导出器输出 `codebase_version: "v2.1"`（每集一个 parquet +
> 每相机一个 mp4）。若使用仅支持其他版本的 lerobot，装对应旧版加载。
