# 可视化数据生成工具调研

> **方法说明**：本调研基于截至 2026 年初的公开资料整理；成文时本机网络受限
> （Web 检索不可用），**发布到 GitHub 前建议对 2025–2026 新工具做一轮复核**
> （关键词建议见文末）。核心结论——"点击配置场景/物品/任务 → 生成 RLBench
> 格式演示数据集"是空白——在已知生态内成立。

## 1. 现有工具分类对照

### A. 全功能仿真平台（自带 GUI 场景编辑）

| 工具 | 场景编辑 | 任务定义 | 演示数据输出 | 局限 |
|---|---|---|---|---|
| **NVIDIA Isaac Sim / Isaac Lab** | ✅ Omniverse/USD 拖拽式编辑器，最接近"点击造场景" | 代码 + GUI | 自定义管线 | 重（GPU/显存要求高）、无 RLBench 任务库、生态互不兼容 |
| **CoppeliaSim 原生 GUI** | ✅ 内置 .ttt 场景编辑（拖物体、摆位姿、设航点） | .ttt + Lua/脚本 | 需自己写（RLBench 就是这么来的） | 编辑器与"数据生成"之间缺一层自动化 |
| **Gazebo（新 GUI）** | ✅ SDF 拖拽 | SDF + 插件 | 操作数据集极少 | 操作技能生态弱 |

### B. 程序化场景/任务组合（代码驱动，无 GUI）

| 工具 | 特点 | 可借鉴点 |
|---|---|---|
| **robosuite / RoboCasa** | 代码组合机器人+物体+任务；RoboCasa 程序化生成厨房场景（布局/材质/干扰物随机化） | 场景随机化参数设计、资产清单化管理 |
| **ManiSkill3** | GPU 并行、资产包、代码定义任务 | 并行采集架构 |
| **Habitat-Sim** | 场景数据集配置化 | 场景配置 schema 设计 |
| **LIBERO** | 任务 DSL（spatial / goal / object 三个变体维度） | **任务变体 DSL 设计**，可直接借鉴到我们的 YAML schema |
| **MuJoCo Playground / Menagerie** | 纯代码 | 资产仓库组织方式 |

### C. 数据生成管线（demo 增广 / 自动生成）

| 工具 | 思路 | 与我们的关系 |
|---|---|---|
| **MimicGen（NVIDIA 2023）** | 从少量人类演示 + 程序化场景增广，自动重定向生成海量数据 | 数据增广流水线思想可作为远期增强 |
| **DexMimicGen（2024）** | 同上，双臂灵巧手 | 同上 |
| **GenSim / GenSim2（Stanford）** | **LLM 生成机器人任务代码**（含 RLBench 任务），自动扩任务库 | 任务脚手架之后的 LLM 辅助造任务路线 |
| **RoboGen（2023）** | LLM 生成任务 + 场景 + 奖励 | 同上 |
| **Eureka（NVIDIA 2023）** | LLM 生成奖励函数 | 相关方向，非数据生成 |

### D. 数据格式与可视化（只管"看"，不管"造"）

| 工具 | 功能 | 空缺 |
|---|---|---|
| **LeRobot（HuggingFace）** | 数据集格式（parquet + 视频）、Web 查看器、遥操作录制 | 有查看/录制，**无场景配置与自动生成** |
| **RLDS / OpenX** | TFDS 格式生态、统计工具 | 同上 |
| **robomimic** | HDF5 工具链 | 同上 |

### E. RLBench 生态现状（我们的直接竞品/前身）

| 工具 | 形态 | 缺什么 |
|---|---|---|
| RLBench `tools/dataset_generator.py` | 纯 CLI，任务内置，PNG+PKL 输出 | 无 GUI、无配置、无预览、无格式导出、all_variations 模式单进程 |
| PerAct / RVT / SAM2Act | 数据消费方（训练+评估） | 不生成、不配置 |

## 2. 差距分析（我们的定位）

**生态空白**：没有任何工具提供
"**点击式配置场景/物品/任务 → 生成 RLBench 多视角 RGB-D 演示数据集**（带语言指令、可导出 LeRobot 等现代格式）"。

- 最接近的 Isaac Sim 有完整 GUI，但换了一套仿真器/资产/任务生态，且门槛重；
- LeRobot 有漂亮的查看/录制体验，但不做生成侧；
- RLBench 侧 100+ 任务库 + 脚本专家是最成熟的"演示数据来源"，却只有 CLI。

**我们的差异化组合**：RLBench 成熟任务库（数据质量）+ Docker 一键
+ 可视化配置（已实现）+ 场景编辑与任务脚手架（路线图）+ 现代格式导出。

## 3. 对路线图的直接启示

| 借鉴 | 来源 | 落到哪一版 |
|---|---|---|
| 任务变体用 DSL/配置表达（物体 × 空间 × 目标三个维度） | LIBERO | 配置 schema（已实现） |
| 资产清单化（缩略图、碰撞几何、抓取先验） | robosuite/Menagerie | 场景编辑器资产面板 |
| 程序化随机化（干扰物、材质、光照、布局范围） | RoboCasa | 配置器 / 场景编辑器 |
| 预览 = 调用仿真器真实渲染截图回传 | （各家皆无，我们自研） | 可视化配置器核心卖点（已实现） |
| 查看器交互（时间轴、成败标注、逐步 obs 浏览） | LeRobot | 数据浏览页（已实现） / 场景编辑器 |
| LLM 辅助生成任务定义 | GenSim/RoboGen | 任务脚手架扩展路线 |
| 场景增广（从少量 demo 泛化新场景） | MimicGen | 远期 |

## 4. 发布前复核清单

- [ ] 搜 "RLBench GUI task editor"、"robot manipulation dataset generation tool GUI 2025 2026" 确认无新竞品；
- [ ] 查 LeRobot 是否新增 scene/task 配置能力；
- [ ] 查 GenSim2 / RoboGen 后续（LLM 造任务是否已有 GUI 产品化）；
- [ ] 查 NVIDIA Isaac Lab 是否出现"数据集导出 RLBench 格式"的桥。

*成文 2026-11-02。下一步：[plan-visual-tool.md](plan-visual-tool.md)*
