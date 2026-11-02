# 法律合规方案（决策记录）

> **结论**：采用"零再分发"结构。仓库不含 RLBench/PyRep/CoppeliaSim 的任何
> 源码或补丁文件；第三方组件在 Docker 构建时由用户自行下载安装；我们只发布
> 100% 原创的脚本与文档，并附显著的许可声明。署名声明**只是补充，不是防线**。

## 1. 问题背景

RLBench 的许可证（Imperial College 自定义，原文见其仓库 `LICENSE`）核心条款：

- 许可 **non-transferable、non-sublicensable**（不可转让、不可再授权）；
- 仅限 **non-commercial, internal or academic research**；
- 禁止将源码或衍生品并入用于销售/许可的产品；
- 商业用途需邮件申请（researchcontracts.engineering@imperial.ac.uk）。

常见误区："在 README 里声明源码来自 RLBench、我们不商用"就能合规——
**不能**。声明解决署名与意图问题，但许可证从未授予任何人**再分发** RLBench
源码（含修改版）的权利，声明无法创设这项权利。同理，**patch/diff 文件也不
干净**（内嵌了其源码行，仍属复制）。

## 2. 采用的结构（零再分发）

| 做法 | 判定 | 本项目采用 |
|---|---|---|
| 仓库内嵌 RLBench / fork 源码 | ⛔ 超出授权 | ❌ |
| 仓库发布含 RLBench 源码行的补丁 | ⛔ 灰色偏高 | ❌ |
| Dockerfile 构建时 `git clone` 官方仓库（用户构建 = 用户下载并接受许可） | ✅ 低风险 | ✅ |
| 我们只写原创脚本，调用其公开 API（`Environment`/`get_task`/`get_demos`） | ✅ 低风险 | ✅ |
| README/NOTICES 显著声明第三方许可与使用限制 | ✅ 应做（补充） | ✅ |

技术上此结构**零成本**：生成数据需要复刻的只有保存格式（`all_variations`
布局 + PNG/PKL），约十几行路径逻辑，仓库的 `scripts/generate.py` 已是完整原创实现，
从未复制 RLBench/SAM2Act 代码。

## 3. 各组件处理方式

| 组件 | 许可 | 处理 |
|---|---|---|
| RLBench 1.2.x | Imperial 自定义（学术非商业） | 构建时克隆；不内嵌、不打补丁；NOTICES 摘要条款 + 原文链接 |
| PyRep 4.1.0.3 | MIT | 构建时克隆（MIT 本可内嵌，但仍走克隆保持单一风格） |
| CoppeliaSim Player 4.1 | 专有免费（禁再分发二进制） | Dockerfile 里 `wget` **官方**下载链接；镜像不发布到公网 registry（用户本地构建） |
| numpy/Pillow 等 | 宽松 | pip 安装 |
| HF 数据集（hqfang/rlbench-18-tasks） | 见 HF 页面 | 只给链接，不重传 |

⚠️ **注意**：即使 Docker 镜像在本地构建，也**不要 push 到公共 registry**
（镜像含 CoppeliaSim 二进制与 RLBench 源码，push 即再分发）。

## 4. README 声明模板（随仓库发布）

> **English**: This repository contains only original code. It does NOT
> include RLBench, PyRep or CoppeliaSim source code. RLBench is downloaded at
> Docker build time from its official repository and is licensed by Imperial
> College under a custom license for **non-commercial academic research only**
> (non-transferable, non-sublicensable). By building/using this software you
> agree to comply with the RLBench license terms. See THIRD_PARTY_NOTICES.md.
>
> **中文**：本仓库仅含原创代码，不含 RLBench/PyRep/CoppeliaSim 源码。
> RLBench 在 Docker 构建时从官方仓库下载，其许可方为 Imperial College，
> **仅限非商业学术研究、不可转让/再授权**。构建或使用本软件即表示你同意遵守
> RLBench 许可条款。详见 THIRD_PARTY_NOTICES.md。

## 5. 遗留事项

- [ ] 构建成功后把 `PYREP_REF`/`RLBENCH_REF` 钉到具体 commit（可复现性）；
- [ ] 可选：给 researchcontracts.engineering@imperial.ac.uk 发邮件确认
      "教程仓库以构建时克隆 + 原创封装方式引用 RLBench" 的合规性（一封邮件换确定性）；
- [ ] 发布前核对 `material/` 截图脱敏（本仓库不直接包含截图，如后续引用需替换本地用户名/路径）；
- [ ] 本文件为工程实践判断，**不构成法律意见**。

*决策于 2026-11-02。相关：[survey-visual-tools.md](survey-visual-tools.md)、[plan-visual-tool.md](plan-visual-tool.md)*
