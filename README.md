# RLBench-DemoGen - 可视化机械臂数据生成工具
在浏览器里选任务、预览真渲染效果、一键生成RLBench操作演示数据集，也可纯命令行运行。Docker命令部署环境。

## 特点
- **可视化操作**：任务点选/参数滑杆/仿真器真渲染预览/进度与日志实时展示/任务中断
- **安装快捷**：`./build.sh` 命令安装
- **数据浏览**：内置查看器，逐集浏览RGB / 深度色带 / 掩码，时间轴回放
- **生成引擎**：并行采集、断点续传、随机种子落盘、16-bit毫米深度、相机内外参、完整性校验

## 使用环境
已验证操作系统 Ubuntu 20.04/22.04；  Docker ≥ 24；
实测：Ubuntu 22.04 + Docker 29.8.1

## 快速开始
```bash
./build.sh     # 1. 构建（自动下载安装包并构建镜像）
docker compose up -d       # 2. 启动Web服务
```

浏览器打开 **http://localhost:8000** 即可打开可视化工具
操作流程：勾选任务→ 调参数 → 点击「渲染预览」看真渲染效果 → 点击「开始生成」→ 右侧看进度日志；
数据输出文件夹 ./output/

## 命令行用法（同可视化界面效果）
```bash
docker compose run --rm demogen generate --tasks reach_and_drag --episodes 25 --workers 2
docker compose run --rm demogen verify /data 
docker compose run --rm demogen generate --help 
```

'--tasks' 默认'all18'任务，逗号分隔任务名 'all'表示任务全集
'--episodes'  每任务集数
'--image-size W H' 相机分辨率，默认 128 128
'--workers'   并行数
'--seed'  随机种子默认值为42
'--layout'  PerAct/RVT/SAM2Act 兼容布局 
'--overwrite'  默认断点续传，跳过完整集

## 使用说明
只需 Docker，以下组件构建时自动获取：
CoppeliaSim Player 4.1；PyRep 4.1.x；RLBench 1.2.x。

## 项目目录
```
├── build.sh / download-coppeliasim.sh / add-benchmark-tasks.sh
├── docker/Dockerfile + entrypoint.sh  
├── docker-compose.yml
├── scripts
├── web/
└── tasks_extra/
```

## 法律与使用限制
本仓库仅含原创代码，不含RLBench / PyRep / CoppeliaSim源码；构建时由用户自行下载并接受其许可。

## 致谢

数据生成基于[RLBench](https://github.com/stepjam/RLBench)与 [PyRep](https://github.com/stepjam/PyRep)，仿真器为
[CoppeliaSim](https://www.coppeliarobotics.com/)。
