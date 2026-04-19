# SustainDC Vendor 引用说明

## 来源

- Repository: https://github.com/HewlettPackard/dc-rl
- License: MIT（核心代码）+ CC BY-NC 4.0（部分数据 / 文档）
- Clone 时间：2026-04-19
- Clone 命令：`git clone --depth=1 https://github.com/HewlettPackard/dc-rl.git vendor/SustainDC`

## 用途

本项目（毕业设计）仅**移植** SustainDC 中 `sustaindc_env.py` 的 `_create_ls_state()` 函数和任务队列管理（Workload_Manager）核心逻辑到 `sinergym/envs/workload_wrapper.py`，以实现弹性 IT 负荷的时间调度。移植部分严格限定在 MIT 许可的代码段。

## 不入库

`vendor/SustainDC/` 目录已加入仓库根 `.gitignore`，不随本项目入库。重新克隆用上方命令。

## 引用（必须）

若论文发表，"弹性 IT 调度"相关章节需引用：

> Sarkar, S., Naug, A., Gundecha, A. et al. **SustainDC: Benchmarking for Sustainable Data Center Control.** *NeurIPS 2024.*

以及本移植文件中的顶部注释须保留 "Adapted from SustainDC (HewlettPackard/dc-rl, MIT License)"。
