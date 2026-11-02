# tasks_extra/tasks/ — 基准任务补全区（drop-in）

把 **官方 RLBench 没有、但 PerAct/SAM2Act 基准需要** 的任务 `.py` 放在这里
（配套 `.ttm` 场景文件放 `../task_ttms/`），重新 `./build.sh` 即会装进镜像。

当前缺的三个基准任务（用 `../add-benchmark-tasks.sh` 一键补全）：

- `slide_block_to_color_target`
- `place_wine_at_rack_location`
- `sweep_to_dustpan_of_size`

⚠️ 这些任务文件来自你自己的 SAM2Act/PerAct 安装，仅限学术非商业用途，
**不要把它们提交到 git 仓库**（见 .gitignore 与 THIRD_PARTY_NOTICES.md）。
