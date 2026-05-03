# M2-F1 TES Learning Problem Handoff

日期：2026-05-01

## 我要请你判断的问题

这个项目正在做数据中心冷却系统的强化学习控制。当前阶段是 M2-F1：不加入 workload action，只验证 TES 在分时电价下是否能学到“低价充冷、高价放冷”的峰谷策略。

现在的核心问题是：物理链路和 rule-based TOU baseline 已经证明可行，但 RL agent 仍没有真正学会低价充冷。最近加入的 `tes_tou_alignment_weight=0.05` 只让高价放冷比低价放冷更强，没有让低价动作变成负阀位充冷。

我想请你重点判断：

1. 现在的 reward / curriculum 设计哪里最可能阻碍 agent 学会低价充冷？
2. 如何让 agent 自己学到 TES 跨时段调度，而不是直接退化成规则控制器？
3. 下一步最小验证实验应如何设计，才能区分 reward 问题、探索问题、信用分配问题和评价指标问题？

## 当前 M2-F1 设置

- 观测空间：32 维。
- agent 动作空间：4 维。
- agent 动作顺序：

```text
[CT_Pump_DRL, CRAH_T_DRL, Chiller_T_DRL, TES_DRL]
```

- EnergyPlus 底层 actuator 仍是 5 维，但 `CRAH_Fan_DRL` 被 wrapper 固定为 `1.0`，不再由 agent 控制。
- 没有 workload action。
- 主 reward：`rl_cost`。
- 主评估协议：`trainlike`，使用 `DRL_DC_training.epJSON`，`ITE_Set=0.45`。
- `DRL_DC_evaluation.epJSON` 的 `ITE_Set=1.0` 现在只作为 high-load / official OOD stress test，不作为 M2-F1 主成败 gate。

## TES 动作语义

TES action 先被解释为目标阀位，再由 wrapper 限速到实际阀位：

```text
TES_DRL < 0  => 充冷
TES_DRL > 0  => 放冷
TES_DRL = 0  => 空闲
```

当前 `TESTargetValveWrapper`：

- `v_target = action[TES]`
- `v_next = v_prev + clip(v_target - v_prev, -0.25, 0.25)`
- SOC guard：
  - `SOC >= 0.90` 禁止继续充冷
  - `SOC <= 0.10` 禁止继续放冷

## 已经排除或基本确认的事项

1. TES 物理链路不是主因。
   - rule TOU baseline 能做到低价充冷、高价放冷。
   - sign check 已验证：charge policy 阀位为负且 SOC 上升；discharge policy 阀位为正且 SOC 下降。

2. `official` evaluation 负载错位不是 M2-F1 当前主问题。
   - 训练域 `DRL_DC_training.epJSON`: `ITE_Set=0.45`。
   - official eval `DRL_DC_evaluation.epJSON`: `ITE_Set=1.0`。
   - 所以 M2-F1 主 gate 已改成 trainlike / `ITE_Set=0.45`。

3. fixed fan 之后 comfort collapse 基本解决。
   - fan 固定为 `1.0`，agent 不再控制 fan。

4. trainlike 672-step 下 guard masking 不是主要失败原因。
   - 新 A/B 结果中 guard clipping 通常为 0 或低个位数百分比。

5. 当前不是 action_dim 混淆。
   - 只使用 4D fixed-fan checkpoint。
   - 旧 5D 结果只作历史背景，不参与当前结论。

## 当前 reward / shaping

`TESPriceShapingWrapper` 中目前包含：

1. target-SOC PBRS：

```text
Phi(s,t) = -kappa * (TES_SOC - SOC_target(t))^2
F_t = gamma * Phi(s_{t+1}, t+1) - Phi(s_t, t)
```

默认目标：

```text
高价: SOC_target = 0.30
低价且峰前: SOC_target = 0.85
其他: SOC_target = 0.50
```

2. teacher/curriculum 项：

```text
tes_teacher_weight = 0.10
tes_teacher_decay_episodes = 30
```

3. 二次阀门正则：

```text
tes_valve_penalty_weight = 0.005
```

4. 新增非 PBRS 的 TOU alignment 项：

```text
desired_sign = +1  if high price and SOC > discharge_limit
             = -1  if low price and near peak and SOC < charge_limit
             =  0  otherwise

r_tou_alignment = weight * desired_sign * tes_valve_target
```

`tes_valve_target > 0` 表示放冷，`< 0` 表示充冷。

本轮测试显式使用：

```text
tes_tou_alignment_weight = 0.05
```

## 关键结果摘要

### Rule baseline 说明

在 trainlike 672-step 下，rule TOU baseline 能正确工作：

- TOU low price valve mean 为负。
- TOU high price valve mean 为正。
- `price_response_high_minus_low` 大幅为正。
- comfort 和 guard 正常。

这说明物理系统、动作符号、评估指标大体可用。

### A/B 3ep, 672-step trainlike eval

| run | seed | tou weight | price response | SOC daily amp | valve saturation | guard clip | comfort violation | low price valve | high price valve |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| w000 seed1 | 1 | 0.00 | 0.1958 | 0.5113 | 0.0000 | 0.0000 | 1.486% | +0.3093 | +0.5051 |
| w005 seed1 | 1 | 0.05 | 0.1593 | 0.4355 | 0.0000 | 0.0000 | 0.297% | +0.3621 | +0.5214 |
| w000 seed4 | 4 | 0.00 | 0.1288 | 0.4654 | 0.0015 | 0.0669 | 0.297% | +0.1714 | +0.3002 |
| w005 seed4 | 4 | 0.05 | 0.1923 | 0.4867 | 0.0000 | 0.0624 | 2.080% | +0.1316 | +0.3239 |

结论：

- `w=0.05` 没有稳定优于 `w=0.0`。
- seed4 有改善，但 seed1 变差。
- 更关键的是：低价阀位仍为正，说明 agent 在低价仍然放冷，只是低价放得少、高价放得多。
- 这不满足“低价充冷、高价放冷”的 TES 峰谷策略。

### 当前失败模式

最准确的描述不是“agent 完全不用 TES”，而是：

```text
agent 学到了高价多放冷、低价少放冷，但没有学到低价主动充冷。
```

也就是说，当前策略仍像一个“持续放冷 + 价格调制强度”的策略，而不是储能套利策略。

## 我担心的科学性问题

如果继续加更强的 action teacher 或更强的 TOU alignment，会不会变成“规则控制器伪装成 RL”？

我希望区分：

- 规则控制：运行时直接 if price high then discharge, if price low then charge。
- rule-informed RL：训练时使用文献合理的辅助 reward / curriculum / imitation，最终运行时 actor 只根据观测输出连续动作。

希望你给出一个更严谨的实验设计，让论文里可以说明 agent 不是简单复刻规则，而是在合理先验下学会跨时段 TES 调度。

## 约束

- 不改变 EnergyPlus TES 物理模型。
- 不改变站点、TOU/PV 数据。
- 不把 workload action 加回 M2-F1。
- 不使用旧 5D checkpoint/replay。
- 不用 `SubprocVecEnv` / `DummyVecEnv` 多 env 包装，Sinergym workspace 文件锁有历史冲突。
- 训练使用 CPU，短训优先，4 seed 以内并发。
- 当前不跑 long 30ep / full-year，先定位机制。

## 文件阅读建议

请优先阅读：

1. `sinergym/envs/tes_wrapper.py`
2. `tools/run_m2_training.py`
3. `tools/evaluate_m2_rule_baseline.py`
4. `tools/m2_reward_audit.py`
5. `tools/m2_validate_tes_failure_modes.py`
6. `analysis/m2f1_toualign_ab3ep_20260501_status.md`
7. `analysis/m2f1_toualign_w005_3ep_seed4_672_audit.json`
8. `runs/m2_validate_tes_failure_modes/paired_eval/action_dim_4/*/summary.json`

## 希望你输出

请不要泛泛建议“继续训练更久”。请优先回答：

1. 当前最可能的失败原因排序。
2. 最小代码改动或配置改动建议。
3. 如何设计 reward/curriculum 才不会被认为是 rule controller。
4. 下一轮 2 seed x 5-10ep 的具体参数和 gate。
5. 是否应该改低价充冷窗口、PBRS 目标、teacher 衰减、alignment 权重或探索噪声。
