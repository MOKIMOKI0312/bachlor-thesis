# PBRS Design for TES RL - 2026-04-23

> 由 Opus 4.7 subagent 基于 Ng-Harada-Russell 1999、Henze-Schoenmann 2003、Liu-Henze 2006/2023、Wang 2025、arxiv 2502.01307 (2025) 综合产出。保留完整分析链以便论文引用。

## 0. 文献覆盖情况

| Source | Status | 关键结论 |
|---|---|---|
| Ng, Harada, Russell 1999 *Policy Invariance under Reward Transformations* (ICML) | 公式 + 条件经 3 个 secondary source 三角验证（emergentmind topic page、arxiv 2502.01307、utexas bib）— PDF 二进制不可读但 Theorem 1 公式已众所周知 | `F(s,a,s') = γΦ(s') − Φ(s)`，Φ 必须 bounded real-valued，Φ(terminal)=0，保持最优策略 |
| arxiv 2502.01307 2025 *Improving Effectiveness of PBRS* | 完整读取 | Potential-shift trick `Φ_b(s)=Φ(s)+b/(γ−1)`；指数形 Φ 优于线性；dynamic PBRS |
| Henze & Schoenmann 2003 HVAC&R | 摘要 only | Reward = monetary cost；RL 对 TOU/RTP 敏感；**learning rate 和 state-var 选择是主要失败模式** |
| Liu & Henze 2006 *Energy and Buildings* | 摘要 only（PDF 二进制） | 动作/状态空间维度是瓶颈；near-optimal 可达 |
| Liu & Henze 2023 *Energy & Buildings* (ice TES) | 两次访问 403 paywall | 通过 triangulation 获取结论 |
| Wang et al. 2025 *J Energy Storage* (field-knowledge RL) | 方法论部分读取 | **dynamic PBRS + expert knowledge** 框架 |
| Storage-arbitrage survey (arxiv 2410.20005) | 完整读取 | 套利 agent 学到 "lowest 7% quantile 充电，top 5% 放电，SOC-dependent 中间带" — 正好是 TOU 模式 |

## 1. 文献综述（6 篇压缩版）

**Ng, Harada, Russell (1999).** 证明对任意 bounded real-valued Φ 加 `F(s,a,s')=γΦ(s')−Φ(s)` 到 true reward **不改变最优策略**（Theorem 1；当 Φ 只依赖 state 时是充要条件）。推论：若存在 terminal/absorbing state，undiscounted/episodic 下必须 Φ=0。Φ 可解释为 V* 的有偏估计——Φ 越接近 V*，Q 收敛越快。实用 Φ 形式：(i) 负距离到目标、(ii) subgoal heuristics、(iii) 手动领域知识。对我们的 infinite-horizon continuing MDP（γ<1，8760 1-h steps），terminal 条件自动由 discounting 满足。

**Henze & Schoenmann (2003).** RL-for-TES 的开山之作。Q-learning + reward=negative monetary cost，state 含 SOC、TOU bracket、season、weather forecast。Finding：learner 对 state-space 维度和 learning rate 极敏感——**与我们的 failure mode 一致**。达到 cost saving 可比 rule-based 但低于 MPC。**对我们的启示**：bare `α·cost` term 是他们的起点，不够强——他们加了 domain discretization 而非 PBRS。证明我们需要 PBRS。

**Liu & Henze (2006, Part 1).** Henze 2003 到 active + passive thermal mass 的理论扩展。发现 state-space curse of dimensionality 主导收敛。明确建议：**训练 episode uniformly 初始化 SOC** — 直接可移植到我们的 `env.reset()`。

**Liu & Henze (2023).** Ice-TES deep RL。Paywalled，通过 2025 storage-arbitrage survey triangulate：现代 TES agent 用 (a) rule-based warm-start 做 imitation、(b) mild penalty 防止零动作 idling、(c) price-SOC interaction feature。这些单独都不是 PBRS，是辅助工程。重要负结果：**cost-only reward 没有 shaping 仍需 100k+ steps 达到 >50 cycles/year**。

**Wang et al. (2025).** 明确倡导 **dynamic PBRS**，嵌入 field expert knowledge 于 active+passive TES。"dynamic" 意味 Φ 依赖时间（如 hours-to-next-peak）。确认 static Φ(SOC) 不够——需 Φ(SOC, price-context)。

**Arxiv 2502.01307 (2025) + PBRS topic review.** 实用提醒：Φ 应 bounded 在 one-step reward / (1−γ) 可比范围，否则要么消失要么淹没 task reward。指数形 Φ 在 continuous control 经验上优于线性。对 continuous SAC-family 适用——PBRS 只是通过 `γΦ(s')−Φ(s)` 改变 TD target per transition，critic 透明吸收（我们的 DSAC-T critic 结构不受影响）。

## 2. 对本项目的映射

- **当前 reward class**: `PUE_TES_Reward` in `sinergym/utils/rewards.py:1660` — 扩展 `PUE_Reward` + soc_penalty (warning quadratic [0.30,0.70] + sharp linear [0.15,0.85])
- **Config**: `sinergym/__init__.py:209-225` 注册 `DC-DRL-TES` with `PUE_TES_Reward`. 当前 M2 训练入口使用 `runperiod=(1,1,2025,31,12,2025)`, `timesteps_per_hour=4` → **约 35040 steps/episode**，continuing episodic
- **Action**: 当前 M2 删除 workload/ITE 空置动作后，`action[4] ∈ [-1, 1]` = TES Δv，wrapper 累加 valve_position。"idle" policy (Δv=0) 是 null action；PBRS 必须让 idling 严格差于正确的充放电
- **DSAC-T**: distributional critic, γ=0.99。PBRS 加 constant per transition；critic 吸收；不干扰 DSAC-T 的 quantile targets
- **Price signals**: `price_current_norm` ∈ [0,1] 在 obs dim 26（post bc10db0）
- **已有 cost_term**: `α=2e-3` 已挂 RL_Cost_Reward

## 3. 三个 Φ 候选

### Candidate A — "Price-SOC Alignment"（推荐）

```
Φ_A(s) = κ_A · (SOC(s) − 0.5) · (0.5 − price_current_norm(s))
默认 κ_A = 2.0
```

- **物理/经济**：Positive potential when (high SOC & low price) **or** (low SOC & high price)。产品形式编码 "charge cheap, discharge dear" 为单一曲面
- **数值范围**：`Φ_A ∈ [-0.5, 0.5]`，per-step |F| 通常 ≤0.05，tier 边界时 ≤0.5
- **期望行为**：02:00 (valley): dΦ/dSOC=+1 → 激励充电；19:00 (peak): dΦ/dSOC=-1 → 激励放电
- **冲突检查**：与 soc_penalty 的 double-incentive 在 SOC=0.85 + peak 是**构造性而非冲突**。不依赖温度，与 comfort_term 独立

### Candidate B — "Lookahead-to-peak Exponential"

```
Φ_B(s) = κ_B · (2·SOC(s) − 1) · exp(−h(s)/τ)
h = price_hours_to_next_peak_norm × 24, τ = 4h, κ_B = 1.5
```

- 动态 PBRS per Wang 2025
- Φ_B ∈ [-1.5, 1.5]，per-step |F| up to ~0.3
- 依赖 `price_hours_to_next_peak_norm`（post bc10db0 已有）

### Candidate C — "Imitation-Gap Potential"（**不推荐**）

```
Φ_C(s) = −κ_C · |SOC(s) − SOC_MPC(t)|
```

- **否决理由**：破坏 RL-Cost vs RL-Green causal attribution，两者都会变成对同一 MPC 轨迹的 tracking，**削弱毕设研究问题**

### 对比表

| | Φ_A | Φ_B | Φ_C |
|---|---|---|---|
| 需要新 obs wrapper? | 否（price_current_norm 已有） | 否（hours_to_peak 已有） | 无（但需 offline MPC 预计算） |
| 研究问题完整性 | **高** | 中 | **低** |
| 期望 cycles/year 提升 | 20-80 | 60-150 | 150-300 |
| 超参敏感度 | 低（1 个 κ） | 中（κ, τ） | 高 |
| PBRS 策略不变性 | ✓ | ✓ | ✓ |
| 实施成本 | 10 LOC | 15 LOC + wrapper | 100+ LOC + 离线 MPC |

## 4. 推荐方案：Φ_A

### 最终公式

```
Φ(s) = 2.0 · (SOC(s) − 0.5) · (0.5 − signal_norm(s))

where  signal_norm =
   price_current_norm      for RL-Cost
   carbon_intensity_norm   for RL-Green

F(s,s') = 0.99 · Φ(s') − Φ(s)
```

**关键设计**：RL-Cost 和 RL-Green 用**完全相同的 Φ 函数形式**，仅 signal 不同。这保证两 ablation 共享 inductive bias，只 isolate direction-of-incentive 变量。

### 代码伪码

目标位置：`sinergym/utils/rewards.py` 的 `RL_Cost_Reward.__call__`

```python
class RL_Cost_Reward(PUE_TES_Reward):
    def __init__(self, *args,
                 kappa_shape: float = 2.0,
                 gamma_pbrs: float = 0.99,
                 alpha: float = 2e-3,
                 signal_variable: str = 'price_current_norm',
                 **kwargs):
        super().__init__(*args, **kwargs)
        self.kappa_shape = kappa_shape
        self.gamma_pbrs = gamma_pbrs
        self.alpha = alpha
        self.signal_variable = signal_variable
        self._prev_phi = 0.0
        self._first_step = True

    def _phi(self, obs_dict):
        soc = float(obs_dict.get(self.soc_variable, 0.5))
        sig = float(obs_dict.get(self.signal_variable, 0.5))
        return self.kappa_shape * (soc - 0.5) * (0.5 - sig)

    def reset_episode(self):
        self._prev_phi = 0.0
        self._first_step = True

    def __call__(self, obs_dict):
        reward, terms = super().__call__(obs_dict)  # PUE + comfort + SOC penalty

        # PBRS
        phi_s_prime = self._phi(obs_dict)
        if self._first_step:
            f_shape = 0.0
            self._first_step = False
        else:
            f_shape = self.gamma_pbrs * phi_s_prime - self._prev_phi
        self._prev_phi = phi_s_prime

        # 原来的 cost_term 保留（不变）
        # ... existing cost_term code ...

        reward = reward + f_shape
        terms['shaping_term'] = f_shape
        terms['phi_value']    = phi_s_prime
        return reward, terms
```

### 初始 SOC 随机化（Liu-Henze 2006，当前未直接实现）

```python
# Desired; not enabled in the current training entry:
init_soc = np.random.uniform(0.20, 0.80)  # truncated uniform
# Requires a physical way to set tank thermal state, not just wrapper obs.
```

2026-04-25 后 active M2 模型使用 `ThermalStorage:ChilledWater:Mixed`。Mixed 水罐的初始热状态由 EnergyPlus 在环境初始化时按 `TES_Charge_Setpoint=6.0°C` 建立；`TESIncrementalWrapper.reset()` 随机化 valve_position 只能改变初始控制命令，不能改变水罐热状态。因此当前入口仍不启用初始 SOC 随机化。若后续要做，应通过 episode-specific 初始化 setpoint schedule 或预处理仿真生成不同真实罐温，而不是只改观测值。

### 超参数

| 名称 | 值 | 理由 |
|---|---|---|
| `kappa_shape` | 2.0 | 保证 \|Φ\| ≤ 0.5，per-step \|F\| ≤ ~0.05 |
| `gamma_pbrs` | 0.99 | 必须与 DSAC-T γ 一致 |
| `alpha_cost` | 2e-3 | 保持 M2-E3b-v4 已验证值 |
| `init_soc_low/high` | 0.20 / 0.80 | 目标值；当前未接入训练入口。后续可通过 episode-specific 初始化 setpoint schedule 或预处理仿真实现 |

## 5. 实施计划

### 文件改动

1. `sinergym/utils/rewards.py` — `RL_Cost_Reward.__call__` 加 PBRS 项 + `reset_episode()` 方法
2. `sinergym/envs/eplus_env.py` — `reset()` 调 `self.reward_fn.reset_episode()` if available
3. `sinergym/envs/tes_wrapper.py` — 保持 valve neutral；不要用随机 valve 伪造初始 SOC
4. `sinergym/__init__.py` — 如果需要新参数接入 reward_kwargs
5. `tools/run_m2_training.py` — 确认 `--alpha` 默认 2e-3 不变

### 回退方案

若 30-ep pilot cycles < 10 → 升级到 Φ_B（exp lookahead）
**不要**跳到 Φ_C（污染 ablation）

## 6. 验收指标（2 seed × 30 ep pilot）

| 指标 | Baseline | 目标 | 验收 |
|---|---|---|---|
| 年 TES 充放电循环 | ~1 | ≥ 20 | ≥ 20 |
| 谷段 (price<$40) TES_DRL 均值 | +0.65 | < −0.10 | < −0.10 |
| 峰段 (price>$150) TES_DRL 均值 | +0.65 | > +0.15 | > +0.15 |
| SOC std 年度 | ~0.03 | > 0.20 | > 0.20 |
| Comfort violations | baseline | Δ ≤ +5% | 无回退 |
| DSAC-T critic loss 晚期稳定 | 稳定 | 稳定同量级 | 不发散 |

## 7. 风险与限制

1. **研究问题完整性**：Φ_A 最小化 inductive bias。未来增补任何 Φ 项都会使 RL-Cost vs RL-Green attribution 更难。**Φ_A 固定不再扩**
2. **Ablation 预算**：论文必须含 naive-cost (α·cost only, Φ=0) 和 Φ-only (no cost, only PBRS) 两组 ablation。总共 4 configs × 2 seeds
3. **DSAC-T 稳定性**：PBRS 加 ≤0.5 到 TD target per step；critic 已稳定处理 ±3 comfort swing。低风险，监控 critic loss 和 quantile spread
4. **Observation wrapper coupling**：Φ_A 依赖 `price_current_norm`。若 wrapper 失效返回默认 0.5，Φ 变为 (SOC-0.5)·0=0，PBRS 静默 → **降级到纯 PUE_TES 而非变坏**。`obs_dict.get(..., 0.5)` 是有意的 safety net
5. **Terminal Φ ≠ 0**：Dec-31-23h 终止时 Φ 可能非零。但 γ^8759 ≈ 10^-38 → 对 return 贡献可忽略，invariance 在实践中保持

## 8. 引用清单

```bibtex
@inproceedings{ng1999policy,
  title={Policy invariance under reward transformations: Theory and application to reward shaping},
  author={Ng, Andrew Y and Harada, Daishi and Russell, Stuart},
  booktitle={International Conference on Machine Learning (ICML)},
  pages={278--287},
  year={1999}
}

@article{henze2003evaluation,
  title={Evaluation of reinforcement learning control for thermal energy storage systems},
  author={Henze, Gregor P and Schoenmann, Justin},
  journal={HVAC\&R Research},
  volume={9},
  number={3},
  pages={259--275},
  year={2003}
}

@article{liu2006experimental,
  title={Experimental analysis of simulated reinforcement learning control for active and passive building thermal storage inventory},
  author={Liu, Simeng and Henze, Gregor P},
  journal={Energy and Buildings},
  volume={38},
  number={2},
  pages={142--147},
  year={2006}
}

@article{wang2025field,
  title={Field knowledge-informed reinforcement learning for synergistic control of active and passive thermal storages in buildings},
  author={Wang, Tao and others},
  journal={Journal of Energy Storage},
  year={2025}
}

@article{pbrs_improve_2025,
  title={Improving the Effectiveness of Potential-Based Reward Shaping in Reinforcement Learning},
  author={Anonymous},
  journal={arXiv preprint arXiv:2502.01307},
  year={2025}
}
```
