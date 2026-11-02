# Third-Party Notices

本仓库（rlbench-demogen）**不包含**任何第三方源码。以下组件在
**Docker 镜像构建时**由用户自行下载安装，即由用户与各权利人之间直接成立许可
关系。本文件仅为说明与署名，不构成对其权利的转授。

| 组件 | 版本（已验证） | 许可证 | 获取方式 | 是否随本仓库分发 |
|---|---|---|---|---|
| RLBench | 1.2.x | Imperial College 自定义许可（**仅限非商业/学术研究，不可转让、不可再授权**） | 构建时 `git clone https://github.com/stepjam/RLBench` | ❌ 否 |
| PyRep | 4.1.0.3 | MIT（Copyright (c) 2019 Stephen James） | 构建时 `git clone https://github.com/stepjam/PyRep` | ❌ 否 |
| CoppeliaSim Player | 4.1（Ubuntu 20.04 版） | 专有免费软件（研究/教育用途免费；**禁止再分发二进制**） | 构建时从 `downloads.coppeliarobotics.com` 官方下载 | ❌ 否 |
| numpy / Pillow / cffi / pyquaternion / scipy | PyPI | BSD/MIT/Apache 等宽松许可 | 构建时 pip 安装 | ❌ 否 |

## RLBench 许可要点（摘要，非法律意见）

原文见 `RLBench` 仓库根目录 `LICENSE` 文件。要点：

- 许可为 worldwide、non-exclusive、**non-transferable、non-sublicensable**；
- 仅限 **non-commercial, internal or academic research** 用途；
- 禁止将源码或其衍生品用于销售/许可给第三方的产品开发；
- 商业用途需联系 researchcontracts.engineering@imperial.ac.uk。

**因此本仓库刻意采用"零再分发"结构**：不内嵌 RLBench 源码、不发布补丁文件
（补丁会内嵌其源码行），而是通过 Dockerfile 在构建时克隆（用户自行接受许可），
我们的脚本仅调用其公开 API（`Environment` / `get_task` / `get_demos`），
保存格式与全部工具代码为原创实现。

使用者须自行确认其用途符合 RLBench 许可条款；本仓库作者对使用者的合规性
不承担责任。

## tasks_extra/（基准任务补全区）

`tasks_extra/` 默认为空。用户可通过 `add-benchmark-tasks.sh` 把**其本人
SAM2Act/PerAct 安装中**的 3 个基准任务变体
（`slide_block_to_color_target`、`place_wine_at_rack_location`、`sweep_to_dustpan_of_size`）
复制到该目录再构建镜像。这些任务文件来自 SAM2Act 仓库（无显式许可证）
或其上游 RLBench fork，**仅限与该基准一致的学术非商业用途**；本仓库不
复制、不分发这些文件，`.gitignore` 已将其排除。使用者自行确保用途合规。

## 数据集链接（不在本仓库内）

- SAM2Act/PerAct 风格 18 任务测试集：https://huggingface.co/datasets/hqfang/rlbench-18-tasks
- SAM2Act 官方数据集：https://huggingface.co/datasets/hqfang/sam2act-datasets

## 致谢

- RLBench: Stephen James et al., Imperial College London — https://github.com/stepjam/RLBench
- PyRep: Stephen James — https://github.com/stepjam/PyRep
- Coppelia Robotics CoppeliaSim — https://www.coppeliarobotics.com/
- 任务定义与数据格式约定参考了 PerAct / RVT / SAM2Act 生态的公开文档
