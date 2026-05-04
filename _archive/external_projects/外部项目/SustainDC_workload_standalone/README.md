# SustainDC Workload 模块拆解

本目录用于单独分析并运行 SustainDC 的 Workload 模块，不依赖 EnergyPlus、Battery 或完整多智能体训练流程。

## 上游项目位置

- 官方仓库已下载到：`../SustainDC`
- 仓库来源：`https://github.com/HewlettPackard/dc-rl`

## Workload 模块的实际结构

SustainDC 里的 “Workload” 不是一个单独包，而是两层结构：

1. `utils/managers.py` 中的 `Workload_Manager`
   - 负责读取 `data/Workload/*.csv`
   - 把 8760 个小时级负载点插值到 15 分钟粒度
   - 负责 `reset()`、`step()`、`get_current_workload()`、`get_next_workload()`
   - 输出的是归一化后的 CPU 工作负载曲线

2. `envs/carbon_ls.py` 中的 `CarbonLoadEnv`
   - 负责“延迟/立即执行/清空队列”这类调度逻辑
   - 内部维护 `tasks_queue`
   - 根据动作把一部分 shiftable workload 延后或出队执行
   - 输出 `ls_shifted_workload`、队列长度、任务年龄分布等信息

上层整合位置：

- `sustaindc_env.py`
  - 用 `Workload_Manager` 产生时间序列负载
  - 用 `ls_env.update_workload(...)` 把负载喂给 `CarbonLoadEnv`
  - 再把 `ls_shifted_workload` 传给数据中心环境

## 关键结论

- `Workload_Manager` 可以单独运行
- `CarbonLoadEnv` 也可以单独运行
- 两者串联后可以脱离 SustainDC 的其余模块单独验证
- 但 `CarbonLoadEnv` 自身不是完整观测封装，它只返回 workload 和队列相关状态
- `sustaindc_env.py` 中看到的 26 维 workload agent 状态，是它在 `CarbonLoadEnv` 输出基础上额外拼接了时间、碳强度、天气等特征后的结果

## 已验证的最小运行链路

已验证如下链路可运行：

`Time_Manager -> Workload_Manager -> CarbonLoadEnv`

运行脚本：

```powershell
python run_workload_standalone.py
```

## 运行输出说明

脚本会：

1. 初始化时间管理器
2. 从 Alibaba 工作负载样本读取 CPU 负载
3. 把每个时刻的 workload 喂给 `CarbonLoadEnv`
4. 用一组固定动作模拟延迟和处理任务
5. 输出每一步的：
   - 当前时间
   - 原始 workload
   - shifted workload
   - 队列长度
   - overdue penalty

## 当前发现

### 1. `CarbonLoadEnv.observation_space` 与 `reset()/step()` 返回的状态维度不一致

- `envs/carbon_ls.py` 中声明的 `observation_space.shape == (26,)`
- 但它实际返回的是：
  - 当前 workload
  - 队列占比
  - 最老任务年龄
  - 平均任务年龄
  - 5 维任务年龄直方图
- 合计只有 `9` 维

这说明 `26` 维观测是面向整套系统设计的接口遗留，而不是 `CarbonLoadEnv` 独立运行时的真实维度。

### 2. Workload 真实可拆的最小单元不是整个 `agent_ls`

如果你后面想把 SustainDC 的 Workload 能力迁移到你的毕设中，最应该复用的是：

- `Workload_Manager`
- `CarbonLoadEnv` 的队列与任务年龄逻辑

而不是直接搬完整的 `agent_ls` 状态定义，因为完整状态强依赖：

- 碳强度 forecast
- 外部温度
- Battery 状态
- 上层联合奖励设计

## 建议的后续改造方向

如果你的目标是把它接到“数据中心冷却-蓄冷-算力联合优化”课题里，建议按这个顺序拆：

1. 保留 `Workload_Manager` 作为外生负载发生器
2. 精简 `CarbonLoadEnv`，只保留任务延迟队列和动作逻辑
3. 把 `ls_shifted_workload` 作为你自己冷却模型的 IT 负载输入
4. 再决定是否引入碳强度/电价作为奖励项，而不是先复用它整套 RL 接口
