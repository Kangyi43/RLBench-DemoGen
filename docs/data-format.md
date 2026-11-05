# 数据格式说明（RLBench DemoGen）

生成器输出目录结构（默认 `--layout all_variations`，与 PerAct/RVT/SAM2Act
数据布局兼容）：

```
<data root>/
└── <task>/                          # 例如 close_jar
    └── all_variations/
        └── episodes/
            └── episode0/
                ├── front_rgb/0.png ... N-1.png           # 8-bit RGB
                ├── front_depth/0.png ... N-1.png         # 16-bit 灰度，毫米
                ├── front_mask/0.png ... N-1.png          # 16-bit 实例标签
                ├── left_shoulder_rgb|depth|mask/ ...
                ├── right_shoulder_rgb|depth|mask/ ...
                ├── overhead_rgb|depth|mask/ ...
                ├── wrist_rgb|depth|mask/ ...
                ├── low_dim_obs.pkl                       # 每步本体感知
                └── meta.json                             # 元数据
```

共 5 个相机视角：`front`、`left_shoulder`、`right_shoulder`、`overhead`、`wrist`。

## 图像流

| 流 | 格式 | 解码 |
|---|---|---|
| `<cam>_rgb` | 8-bit RGB PNG | 直接读取 |
| `<cam>_depth` | **16-bit 灰度 PNG，单位毫米** | `depth_m = png_value / 1000.0` |
| `<cam>_mask` | 16-bit PNG，像素值为物体实例 ID（0 = 背景） | 直接读取 |

> ⚠️ 与 RLBench 原版 `dataset_generator` 不同：原版把深度编码成 8-bit
> 三通道图像（有损）。本格式直接存 16-bit 毫米深度，精度更高、解码更简单。

## low_dim_obs.pkl

`pickle.load` 得到一个 **list[dict]**，每个 dict 对应一步：

| 字段 | 类型 | 含义 |
|---|---|---|
| `gripper_pose` | float32[7] | 夹爪位姿：`[x,y,z]` + 四元数（分量顺序见 RLBench `Observation.gripper_pose` 约定） |
| `gripper_open` | float | 1.0 开 / 0.0 合 |
| `gripper_joint_positions` | float32[2] | 两指关节位置 |
| `joint_positions` | float32[7] | 机械臂 7 关节位置 |
| `joint_velocities` | float32[7] | 关节速度 |
| `joint_forces` | float32[7] | 关节力矩 |
| `task_low_dim_state` | float32[] | 任务自定义低维状态 |

**动作可以从这里推导**：相邻步 `gripper_pose` 差分 = 末端位姿增量；
`gripper_open` 跳变 = 夹爪开合事件（即模仿学习里的"关键帧"）。

## meta.json

| 字段 | 含义 |
|---|---|
| `schema_version` | 格式版本（当前 "1.1"；1.1 起相机内外参为真实值并新增 `camera_clipping`） |
| `task` / `episode_index` / `variation_number` | 标识与任务变体编号 |
| `language_instructions` | 语言指令列表（同一任务不同表述） |
| `seed` | 该集生成用的随机种子（**best-effort 可复现**：物理引擎可能引入非确定性） |
| `num_steps` / `image_size` / `cameras` | 规模信息 |
| `depth_encoding` / `mask_encoding` | 编码说明（自描述，工具链应以此为准） |
| `camera_intrinsics` / `camera_extrinsics` | 每相机 3×3 内参 / 4×4 外参（`<cam>_camera_*` 源自 `obs.misc`，可把像素反投影回 3D） |
| `camera_clipping` | 每相机 `near`/`far` 裁剪面（配合深度做度量重建） |
| `expert_success` | 脚本专家校验通过（RLBench demo 必为成功轨迹） |
| `provenance` | 生成时 RLBench / PyRep 的 ref（溯源） |

## 与 RLBench 原版格式的差异

| 项 | RLBench 原版 | 本格式 |
|---|---|---|
| 深度 | 8-bit ×3 通道编码 | 16-bit 毫米 PNG ✅ |
| mask | 8-bit 彩色 | 16-bit 实例标签 ✅ |
| low_dim_obs.pkl | pickle 整个 Observation 对象（图像置空） | 纯 dict list，字段显式、跨版本稳定 ✅ |
| meta.json | 无 | 有（种子/内参/外参/溯源）✅ |
| 目录布局 | `variation<N>/episodes/` | `all_variations/episodes/`（兼容 PerAct/RVT/SAM2Act）|

需要与只吃原版格式的旧代码对接时，按上表写一个转换即可（欢迎提交 PR）。
