# mpc_v2 工作区规则

## 当前用途

- `mpc_v2/` 是 synthetic/replay MILP-MPC 验证框架。
- 本目录用于 MPC 算法验证、固定输入算法验算、SOC-neutral 复核、中国 TOU/DR 矩阵和相关统计分析。
- 本目录不是 EnergyPlus online co-simulation 入口；涉及 EnergyPlus 模型、EPW、epJSON、runner 时，应回到 `../Nanjing-DataCenter-TES-EnergyPlus/`。

## MPC 固定验证情景

当用户要求创建或使用 “MPC 算法验证”“固定点位”“固定环境输入”“算法验算” 情景时，默认写入一个解析夹具，而不是复用真实 PV/电价 CSV 或长矩阵配置。

固定验证情景的默认口径：

- 时间步长：15 min。
- 闭环长度：24 h = 96 steps。
- 预测时域：默认 96 steps，并在 episode 末端截断。
- IT 负荷：恒定。
- 室外温度和湿球温度：恒定。
- PV：固定为 0。
- 电价：人工阶梯电价，用低价/中价/高价测试 MPC 价格响应。
- DR、peak-cap、demand charge：默认关闭。
- SOC：`initial_soc = 0.5`，`soc_target = 0.5`。
- 终端权重：`w_terminal = 50000`。
- `truncate_horizon_to_episode = true`。

这个情景必须足够简单，使人工能够判断 MPC 的动作方向是否合理：低价段优先充冷，高价段优先放冷，episode 结束时回到初始 SOC 附近。

## 使用边界

- 用于验证 MPC 动作、SOC 递推、终端 SOC、价格响应、可行性、物理一致性和 solver 行为。
- 不用于论文主线收益结论。
- 不用于真实中国 TOU/DR 政策收益判断。
- 不应把该情景的成本节省解释为真实项目收益；它只是算法验算夹具。

## 输出与验收

- 默认运行目录：`runs/mpc_algorithm_validation_<YYYYMMDD>/`。
- 如果冻结结果，使用：`results/mpc_algorithm_validation_<YYYYMMDD>/`。
- 每次保存验证结果时，必须同步检查并更新根目录 `CHANGELOG.md`。
- 若验证结果进入论文事实基础，必须同步检查 `../docs/project_management/毕业设计论文/thesis_draft.tex`。

核心验收指标：

- `fallback_count = 0`。
- `feasible_rate = 1.0`。
- `optimal_rate >= 0.99`。
- `soc_violation_count = 0`。
- `physical_consistency_violation_count = 0`。
- `abs(final_soc_after_last_update - initial_soc) <= 1e-3`。
- 阶梯电价情景中 `tes_discharge_weighted_avg_price > tes_charge_weighted_avg_price`。
- 平价情景中的 TES 充放电量应显著低于阶梯电价情景，除非正在专门测试其它约束。

## 结果解释规则

- 结论必须区分：
  - 已由固定夹具验证的算法性质。
  - 基于固定夹具的推断。
  - 仍需真实天气、PV、电价或 EnergyPlus online co-simulation 验证的假设。
- 报告中应明确写出该结果不是 TOU/DR 主线收益矩阵，也不是 EnergyPlus 联合仿真结果。
