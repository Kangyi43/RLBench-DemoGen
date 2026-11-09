# 发布投放清单（M2 传播节点用）

目标：把「生成 → 导出 → 训练 → 回放」闭环作为传播素材，冲击 GitHub 星标。

## 一、发布前检查

- [ ] README 演示 GIF（训练回放）已嵌入且 < 10MB
- [ ] README 中英双语就绪；对比表、快速开始、法律声明在位
- [ ] `docker compose build && docker compose up -d` 在干净机器可复现（或已知偏差写明）
- [ ] HuggingFace 数据集已发布（见下）并从 README 链接
- [ ] 教程 `docs/train-act.md` 按步骤走通一遍
- [ ] 仓库 Topics 标签：`robot-learning` `imitation-learning` `simulation` `vla` `dataset` `rlbench` `lerobot` `docker`

## 二、HuggingFace 数据集发布（需你的 HF 账号）

1. 用本站生成：`reach_and_drag` 等任务 × 50 集，导出 LeRobot 格式；
2. `huggingface-cli upload <user>/rlbench-demogen-data ./output/lerobot --repo-type dataset`；
3. 数据集卡片写明：来源（RLBench DemoGen 生成）、格式（LeRobot）、许可（学术非商业，注明 RLBench 约束）、用途（ACT/DP/VLA 训练）；
4. README「适用场景」区加数据集链接。

## 三、渠道与文案要点

| 渠道 | 标题方向 | 要点 |
|---|---|---|
| GitHub Release v1.0 | Visual dataset factory for robot manipulation learning | 附 GIF + 30s 视频 + 快速开始 |
| X / Twitter（中英各一） | 一条命令：仿真数据 → LeRobot → 会动的策略 | GIF 前置；@提及 lerobot/HF 生态 |
| Reddit r/MachineLearning / r/robotics | Showoff: I built a visual sim-data factory with training loop | 强调对比表与上手时间 |
| Hacker News | Show HN: RLBench DemoGen – visual dataset generation for robot learning | 强调 Docker 一键、真渲染预览 |
| 知乎 / 微信公众号 | 具身智能数据生成工具教程（长文） | 中文教程 + 踩坑记录引流 |
| LeRobot Discord / 相关 Discord | 分享 LeRobot 导出功能 | 社区反馈入口 |

## 四、时间安排建议

1. D0：GitHub Release + X 双语；
2. D1：Reddit / HN；
3. D3：知乎长文 + 公众号；
4. D7：数据集发布 + 第二波（训练结果对比、社区 issue 互动）。

## 五、素材清单

- [ ] 训练回放 GIF（成功案例 + 1 个失败案例）
- [ ] 30s 演示视频：界面操作 → 生成 → 导出 → 训练曲线 → 回放
- [ ] 截图：预览面板、导出页、数据浏览页
- [ ] 数字：上手时间 10 分钟、生成速率、训练耗时、成功率
