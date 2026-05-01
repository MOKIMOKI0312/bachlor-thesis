# PBRS 升级设计 — Dynamic Price-Aware DPBA（2026-04-23）

## 摘要

Φ_A (κ(SOC-0.5)(0.5-price)) ep15 pilot 停滞：pk-tr 差值 0.02-0.05（目标 ≥0.25），SOC cycles 从 ep8 peak 20 回落到 ep15 5-7，ent_coef 过早塌缩到 0.011。诊断：Φ_A 只看当前 price，15:00 时 dΦ/dSOC 方向**反向**（鼓励放电），无法引导 agent 为 19:00 峰段提前充电。

**升级至 Candidate 2（Dynamic Price-Aware DPBA）**：
```
Φ(s, t) = κ · (SOC(s) − 0.5) · spread(t)
spread(t) = (p̂_peak_ref − p_curr(t)) · exp(−h(t) / τ)
```
基于 Devlin-Kudenko 2012 AAMAS DPBA 理论（policy invariance proof for time-dependent Φ）+ Cao 2024 arxiv 2410.20005 实证（battery arbitrage 加 forecast horizon 后 cycles +74%, reward +60%）。

## 文献证据链

### Level 1：理论基础
- **Ng-Harada-Russell 1999 ICML**：`F = γΦ(s') − Φ(s)` 保持最优策略不变
- **Devlin-Kudenko 2012 AAMAS**：扩展到 dynamic / time-dependent Φ，证明 `F = γΦ(s',t+1) − Φ(s,t)` 同样保持 policy invariance
  - URL: https://www.ifaamas.org/Proceedings/aamas2012/papers/2C_3.pdf

### Level 2：同类场景实证
- **Cao et al. 2024 arxiv 2410.20005** *Enhancing Battery Storage Energy Arbitrage with DRL and Time-Series Forecasting*（ASME Int Conf Energy Sustainability 2025 accepted）
  - Li-ion battery arbitrage + $/MWh TOU
  - 7 个 forecaster (1h/2h/3h/6h/12h/18h/24h horizons)
  - **DQN + forecast**: accumulated reward CA$547k vs CA$341k (+60%)
  - **Battery cycles**: 1,179 → 2,056 (**+74%**)
  - PPO 同配置 +14%
  - 和我们 "cycles 5→20+" 目标**完全同构**
  - URL: https://arxiv.org/abs/2410.20005

### Level 3：κ 调参 / ent_coef 处理
- **Simpson 2025 arxiv 2502.01307** *Improving PBRS Effectiveness*
  - Φ 必须在 `[r_∞ − (1-γ)Q_init, r_g − (1-γ)Q_init]` 内
  - 我们 γ=0.99, Q_init≈0, r_∞≈-0.25, r_g≈+0.5 → Φ 上限 ≈0.50
  - 取 κ=0.8 使 |Φ|≤0.40（20% 安全余量）
- **Xu et al. 2023 OpenReview** *Revisiting Discrete SAC*
  - `target_entropy = -dim(A)/3` 对 discrete-price-tier 表现好于默认 `-dim(A)`
  - 我们 dim(A)=6 → 默认 -6 过强 → 改 **-2.0**
- **Haarnoja SAC v2**：log_alpha clip ≥ log(0.05) 作 entropy floor（Cao 2024 codebase 惯用 tweak）

## 最终设计

### Φ 公式
```python
Φ(s, t) = KAPPA · (soc - 0.5) · spread
spread = (P_PEAK_REF - price_current_norm) · exp(-max(h, 0.1) / TAU_DECAY)

KAPPA        = 0.8
TAU_DECAY    = 4.0   # hours (与 PriceSignalWrapper 的 lookahead_hours=6 一致)
P_PEAK_REF   = 0.80  # Jiangsu 峰段 price_current_norm 均值 ($160-200 / 250)
H_NORM_SCALE = 24.0  # price_hours_to_next_peak_norm ∈ [0,1] → h ∈ [0, 24]
```

### 量级验算（Jiangsu TOU 实测）

| 时刻 | price | h | spread | SOC=0.3 Φ | SOC=0.7 Φ | dΦ/dSOC |
|------|-------|---|--------|-----------|-----------|---------|
| 02:00 谷段 (距峰远) | 0.116 | 17h | 0.010 | −0.002 | +0.002 | +0.008（弱）|
| 15:00 距峰 4h | 0.332 | 4h | 0.172 | **−0.041** | **+0.041** | **+0.137**（强-充电）|
| 17:00 距峰 2h | 0.332 | 2h | 0.284 | −0.068 | +0.068 | +0.227（更强）|
| 19:00 峰段开始 | 0.80 | 0h (下个峰 24h 后) | 0.00 | 0 | 0 | 0（放弃 shaping，cost_term 主导）|
| 19:30 峰段内 | 0.64 | 23.5h | 0.001 | 0 | 0 | 0 |

**关键改进**：15:00 时 dΦ/dSOC = +0.137 强烈激励充电（Φ_A 是 −0.1 反向激励放电）。这直接解决 ep15 停滞根因。

典型 |F| per step ≈ 0.05，边界 tier 切换时 ≤ 0.20（在 DSAC-T ±3 comfort swing 内安全）。

### 并行改动：防 ent_coef collapse

```python
# 在 run_m2_training.py 的 model 构造前:
DSAC_T(
    ...,
    target_entropy = -float(action_dim) / 3.0,  # now -1.3333 for 4-dim M2-F1 action
    # log_alpha clip 在 DSAC-T 训练内加 (需 code-fixer 改 dsac_t.py):
    #   self.log_ent_coef.clamp_(min=math.log(0.05))
)
```

## 实施清单

| # | 文件 | 改动 | 行数 |
|---|------|------|------|
| 1 | `sinergym/utils/rewards.py` | `RL_Cost_Reward.__init__` 新增 `tau_decay`, `p_peak_ref` 参数；`_phi()` 重写按新公式 | +20 |
| 2 | `tools/run_m2_training.py` | CLI `--tau-decay` / `--p-peak-ref`；M2-F1 固定 fan 后 model 构造时传 `target_entropy=-4/3`（4 维 agent action） | +5 |
| 3 | `tools/dsac_t.py` | ent_coef optimizer step 后加 `log_alpha.clamp_(min=log(0.05))` | +3 |
| 4 | `tools/smoke_pbrs.py` | 更新量级断言 |Φ|≤0.40, 验证 15:00 时 dΦ/dSOC>0 | +10 |

## 验收指标（4 seed × 30 ep pilot）

| 指标 | Φ_A 当前 (ep15) | 目标 | Cao 2024 对应 |
|------|-----------------|------|--------------|
| 年 SOC cycles | 5-7/ep | **≥ 30** | +74% |
| pk-tr 差值 | 0.02-0.05 | **≥ 0.15** | 方向正确 |
| SOC std | 0.20-0.25 | ≥ 0.20 | 维持 |
| ent_coef (late) | 0.011 | 0.05-0.15 | floor 生效 |
| reward | -2.1 | -2.0 ± 0.2 | 无退化 |
| critic omega | 13 | < 100 | 不发散 |

若仍不达标，回退路径：Candidate 1 (Shifted-exp) 或 Candidate 3 (Schelke imitation-gap)，但后者破坏 PBRS 不变性，仅作最后兜底。

## 引用清单

```bibtex
@inproceedings{devlin2012dynamic,
  title={Dynamic potential-based reward shaping},
  author={Devlin, Sam and Kudenko, Daniel},
  booktitle={AAMAS}, year={2012},
  url={https://www.ifaamas.org/Proceedings/aamas2012/papers/2C_3.pdf}
}

@article{cao2024enhancing,
  title={Enhancing Battery Storage Energy Arbitrage with Deep Reinforcement Learning and Time-Series Forecasting},
  author={Cao, Manuel and others},
  journal={arXiv preprint arXiv:2410.20005},
  year={2024}
}

@article{simpson2025improving,
  title={Improving the Effectiveness of Potential-Based Reward Shaping in Reinforcement Learning},
  journal={arXiv preprint arXiv:2502.01307},
  year={2025}
}

@article{xu2023discrete,
  title={Revisiting Discrete Soft Actor-Critic},
  author={Xu, Haibin and others},
  journal={OpenReview EUF2R6VBeU},
  year={2023}
}
```
