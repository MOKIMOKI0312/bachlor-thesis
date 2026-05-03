# M2-F1 TES Planner / MPC / Safety Projection Design

Date: 2026-05-02

Scope: design only. This document does not implement code, does not change EnergyPlus physics, does not change site / TOU / PV data, does not add workload action, and keeps the M2-F1 fixed CRAH fan assumption.

## 1. Evidence Summary

C1, C2, C2b, C3, A-prime, and O1 all failed the 672-step low-price active charging mechanism gate. The repeated pattern is that high-price discharge is learnable, but low-price pre-peak active charge is not reliably learned.

The gate criteria are mechanism-level, not just cost or price-response metrics. A passing policy should show negative actual valve during low-price pre-peak windows, positive `delta_soc_prepeak`, positive actual valve during high-price windows, negative `delta_soc_peak`, and no material comfort or guard regression.

| Branch | Main intervention | 672-step evidence | Interpretation |
|---|---|---|---|
| C1 | Sparse PBRS, wider low-price window, no teacher/alignment | C1 seeds had `charge_window_sign_rate` around `0.068`, `low_price_discharge_fraction` around `0.89-0.91`, and positive low-price valve means. | Reward cleanup did not create active charge behavior. |
| C2 | Short teacher/curriculum | One seed stayed at `charge_window_sign_rate=0.0`, `low_price_discharge_fraction=1.0`; the other improved only partially. | Short teacher signal did not persist as a learned low-price charge policy. |
| C2b | State augmentation | 672 mean `charge_window_sign_rate=0.306`, `low_price_discharge_fraction=0.634`, `delta_soc_prepeak=+0.032`, with low-price valve still positive. | Extra TES state helps diagnosis and timing visibility, but the low-price sign remains wrong too often. |
| C3 | Entropy ablation | Entropy `-4.0` and `-2.0` both failed; 672 mean charge sign stayed near `0.23-0.25`, low-price discharge near `0.71-0.72`. | Exploration level changes did not fix the mode-selection problem. |
| A-prime | Explicit direction/amplitude action semantics | 672 mean `charge_window_sign_rate=0.214`, `low_price_discharge_fraction=0.654`, `delta_soc_prepeak=-0.014`, charge-window valve mean positive. | Explicit direction/amplitude did not create sustained low-price charging. |
| O1 | Direction/amplitude with 4-step hold | 672 mean `charge_window_sign_rate=0.071`, `low_price_discharge_fraction=0.679`, `delta_soc_prepeak=-0.0086`, `delta_soc_peak=+0.020`, charge-window valve mean positive. | Time abstraction by itself worsened low-price charge behavior; action smoothing is not enough. |

The first-principles diagnosis is now narrow: the agent has access to price, SOC, and optional recent SOC dynamics; it can move TES and can discharge at high price; but the reinforcement signal still does not reliably teach the inventory decision "charge now for later". Reward, teacher reward, state features, entropy, explicit direction/amplitude, and hold-mode smoothing have all been tested at short-horizon mechanism scale. Continuing small reward or deadband tuning is unlikely to address the missing delayed-inventory prior.

The next route should introduce an offline planner or MPC only as a training signal, oracle, or safety feasibility layer, with a clear boundary between training guidance and final runtime policy.

## 2. Target Boundaries

Hard boundaries:

- Do not change EnergyPlus physical plant, schedules, TES model, or simulator internals.
- Do not change site, weather, TOU, PV, or workload assumptions.
- Do not add workload action.
- Keep M2-F1 fixed fan.
- Do not present a runtime economic rule as the final RL policy.
- Do not add persistent price-conditioned reward terms for final claims.

Allowed:

- Offline labels generated from a rule, planner, or small MPC for training-time curriculum.
- TES-head-only behavioral cloning or warm-start that decays to exactly zero before final evaluation.
- Safety projection that enforces physical or comfort feasibility without encoding "low price means charge" or "high price means discharge".
- MPC or rule baselines as oracle/gate comparators, as long as they are labeled as non-learned baselines.

The scientific target remains: evaluate whether a learned policy, after any removable training curriculum is off, can execute TES arbitrage in the unchanged simulation environment.

## 3. Scheme S1: Safety Projection

S1 is a runtime feasibility layer, not an economic controller.

It may project the actor's proposed TES command into a physically safer command using only constraints such as:

- SOC bounds:
  - block or reduce charge near upper SOC;
  - block or reduce discharge near lower SOC.
- Valve rate limit:
  - preserve or consolidate the existing target-to-actual rate limit.
- Charge/discharge mutual exclusivity:
  - one signed TES valve target only; no simultaneous charge and discharge representation.
- Comfort margin:
  - optionally reduce TES behavior that would erode measured comfort margin, for example when temperatures are already close to a hard comfort boundary.
- Numerical safety:
  - clamp invalid action values and emit explicit monitor fields.

S1 must not include rules such as:

- if price is low, force charge;
- if price is high, force discharge;
- if near peak, fill TES;
- if PV is high, charge TES.

Useful S1 monitor fields:

- `tes_projection_applied`
- `tes_projection_reason`
- `tes_raw_signed_target_before_projection`
- `tes_signed_target_after_projection`
- `tes_projection_delta`
- `tes_projection_soc_bound_active`
- `tes_projection_rate_limit_active`
- `tes_projection_comfort_margin_active`

Why S1 should not be the first implementation:

The current failure is not mainly unsafe raw intent. Existing guard/rate limiting already prevents many infeasible TES actions, and O1 still failed with guard clipping near zero in key rows. A safety projection can reduce bad or infeasible actions, but it will not teach the actor to choose sustained low-price charge. It should be used after or alongside planner-guided learning, not as the primary mechanism fix.

## 4. Scheme P1: Planner-Guided / BC Warm-Start

P1 uses a planner, rule, or MPC only to generate training labels. The planner is not called during final evaluation.

Minimum concept:

- Keep the current actor and environment.
- Use the current best TES action semantics for labels, likely `direction_amp_hold`.
- Generate TES-only desired labels:
  - `tes_mode_label`: charge, idle, discharge;
  - `tes_amp_label`: continuous amplitude in `[0, 1]`;
  - optional `tes_signed_target_label`.
- Apply supervised loss only to the TES head or TES action dimensions.
- Do not supervise HVAC actions.
- Decay the BC weight to exactly zero after 1-2 episodes.
- Save status/manifest evidence that final evaluation checkpoint has `tes_bc_weight=0`.

Candidate loss for `direction_amp_hold`:

```text
L_actor_total = L_rl
              + lambda_bc(t) * mask_label_available(t) * L_tes_bc

lambda_bc(t) = lambda0 * max(0, 1 - episode / bc_decay_episodes)
```

For the 5D direction/amplitude interface, `L_tes_bc` can be split into:

- direction component: push `TES_direction_DRL` below `-deadband` for charge, above `+deadband` for discharge, and inside deadband for idle;
- amplitude component: MSE to `TES_amplitude_raw_label`, or MSE after mapping to `[0, 1]`;
- optional mode classification only if a hybrid/discrete head is later introduced.

Label source options:

- simple rule labels for initial smoke:
  - charge in low-price pre-peak windows when SOC has headroom;
  - discharge in high-price windows when SOC has inventory;
  - idle otherwise.
- TES-only MPC labels for the main experiment:
  - optimize a short horizon over a simplified TES inventory model and known TOU prices;
  - include SOC bounds and rate limits;
  - output only labels, not runtime commands.

The key distinction from prior teacher reward is that P1 should be a direct TES-head behavioral warm-start or actor regularizer, not another persistent reward term that competes with energy/comfort cost. The final evaluated actor must run without planner calls and with the BC coefficient at zero.

## 5. Scheme M1: TES-Only Small MPC Oracle

M1 is a small oracle used for labels, diagnostics, and upper-bound comparison. It is not the final controller.

MPC state and inputs:

- current TES SOC;
- current actual or target valve state if rate limit matters;
- known future TOU price over a short horizon;
- approximate charge/discharge SOC efficiency;
- SOC lower/upper bounds;
- valve amplitude/rate constraints.

MPC objective:

- minimize expected TES-related energy cost proxy over the horizon;
- reward inventory before high-price periods only through the optimization objective;
- penalize excessive valve movement if needed;
- preserve feasibility constraints.

What makes M1 different from a runtime rule controller:

- M1 can be run offline on recorded or generated state trajectories to produce labels.
- M1 can be run as a separate oracle baseline for evaluation.
- M1 should not be called inside the final learned policy rollout that is claimed as RL.
- If M1 is evaluated online, it must be reported as "MPC oracle" or "planner baseline", not as the learned RL controller.

Useful M1 artifacts:

- `analysis/m2f1_tes_mpc_oracle_labels_*.csv`
- per-step columns:
  - `tes_mpc_mode_label`
  - `tes_mpc_amp_label`
  - `tes_mpc_signed_target_label`
  - `tes_mpc_objective_value`
  - `tes_mpc_feasible`
  - `tes_mpc_infeasible_reason`
- summary columns:
  - charge-window label fraction;
  - peak-window label fraction;
  - expected SOC lift before peak;
  - expected SOC drawdown during peak.

## 6. Recommended Next Minimum Implementation

Recommended next step: implement planner-guided TES-head BC warm-start first, using O1 `direction_amp_hold` as the agent-facing TES action semantics.

Reasoning:

- The repeated failure is behavioral: the actor does not choose sustained charge during low-price pre-peak windows.
- S1 safety projection only constrains or clips actions; it cannot introduce the missing delayed-inventory behavior unless it becomes an economic rule, which is outside the boundary.
- O1 already provides a clean 5D mode/amplitude surface for TES labels.
- A short BC warm-start tests the most direct hypothesis: the policy needs an initial inventory-action prior, then pure RL can keep or reject it.
- The intervention is removable and paper-clean if the final checkpoint is evaluated with `tes_bc_weight=0` and no planner calls.

Minimum P1 implementation shape:

- Keep base config from O1:
  - state augmentation on;
  - `tes_action_semantics=direction_amp_hold`;
  - `tes_option_hold_steps=4`;
  - neutral PBRS zero;
  - short teacher/alignment reward off unless intentionally comparing to C2b/O1 base.
- Add an offline label generator or label provider for TES mode/amplitude only.
- Add training-time TES-head BC loss with:
  - `lambda_bc0` small enough not to dominate all HVAC learning;
  - `bc_decay_episodes=1` and `2` as the first matrix;
  - hard assert that final eval sees `lambda_bc=0`.
- Do not call planner/MPC in `evaluate_m2.py` or `m2_validate_tes_failure_modes.py` for learned-policy rows.

S1 should follow as a separate implementation only if:

- BC produces correct raw TES intent but actual valve remains blocked by guard/rate/comfort constraints; or
- comfort/guard risks appear once charge behavior is learned.

## 7. Interface Sketch

Potential new tooling:

- `tools/generate_tes_planner_labels.py`
  - reads monitor-like trajectories or design profiles;
  - emits CSV labels keyed by episode step/time index;
  - supports `rule` and `tes_mpc` label sources.
- training path additions:
  - `--tes-bc-labels <csv>`;
  - `--tes-bc-weight`;
  - `--tes-bc-decay-episodes`;
  - `--tes-bc-target {direction_amp,direction_amp_hold,signed_scalar}`;
  - `--tes-bc-label-source {rule,tes_mpc}`;
  - `--tes-bc-final-weight-required-zero`.
- optional projection path later:
  - `--enable-tes-safety-projection`;
  - `--tes-projection-comfort-margin-c`;
  - no price/TOU flags inside projection.

Wrapper / training order:

1. Actor emits HVAC plus TES action.
2. TES action semantics wrapper maps TES head to signed target.
3. Optional safety projection, if enabled, applies physical feasibility only.
4. Existing `TESTargetValveWrapper` applies rate limit / SOC guard and logs actual valve.
5. Reward and monitor stack record both raw intent and actual TES effect.
6. Actor update receives `L_rl`; if BC is active for the current episode, add TES-head-only BC loss.

Monitor/status fields for P1:

- `tes_bc_enabled`
- `tes_bc_label_source`
- `tes_bc_weight_current`
- `tes_bc_decay_episodes`
- `tes_bc_loss`
- `tes_bc_mode_label`
- `tes_bc_amp_label`
- `tes_bc_signed_target_label`
- `tes_bc_mode_match`
- `tes_bc_amp_error`
- `tes_bc_final_weight_zero`
- `planner_called_in_runtime_eval` should be absent or `false` for learned-policy eval rows.

Monitor/status fields for S1:

- `tes_safety_projection_enabled`
- `tes_projection_applied`
- `tes_projection_reason`
- `tes_projection_delta`
- `tes_projection_constraint_set`

Evaluation/counterfactual synchronization:

- Paired evaluation must record whether BC was active during training and confirm it is inactive during evaluation.
- Counterfactual rows must not describe planner-guided runs as same-HVAC action replay unless strict replay is implemented.
- Learned policy eval should fail loud if a runtime planner/projection flag is accidentally enabled when the intended artifact is "policy only".
- MPC oracle eval should be tagged separately, for example `tes_controller_type=mpc_oracle`.

Documentation artifacts:

- label generation manifest;
- training status with BC schedule;
- eval manifest proving no runtime planner;
- P0.2 summary CSV/JSON with mechanism metrics;
- short reviewer note explaining rule-informed curriculum vs runtime rule controller.

## 8. Experiment Matrix

All rows are short mechanism tests, not final thesis-scale evidence.

| ID | Config | Seeds | Episodes | Eval | Comparison |
|---|---|---:|---:|---|---|
| B0 | C2b baseline, signed scalar, state augmentation | 1, 4 | existing 5 | 96/672 | existing `analysis/m2f1_c2b_5ep_eval_summary_20260502.*` |
| B1 | O1 baseline, `direction_amp_hold`, no BC | 1, 4 | existing 5 | 96/672 | existing `analysis/m2f1_o1_diramp_hold4_5ep_eval_summary_20260502.*` |
| P1a | O1 + TES-head BC, rule labels, decay 1 episode | 1, 4 | 5 | 96/672 | B0/B1 |
| P1b | O1 + TES-head BC, rule labels, decay 2 episodes | 1, 4 | 5 | 96/672 | B0/B1 |
| P1c | O1 + TES-head BC, TES-only MPC labels, decay 2 episodes | 1, 4 | 5 | 96/672 | P1a/P1b |
| S1a | O1 + safety projection only, no economic labels | 1, 4 | 5 | 96/672 | shows projection alone does or does not help |
| M1 | TES-only MPC oracle baseline | deterministic oracle | no RL training | 96/672 | upper-bound and label sanity check |

Primary P0.2 gate:

- `charge_window_sign_rate` materially higher than C2b/O1 and ideally `>= 0.80`;
- `low_price_discharge_fraction <= 0.10`;
- `delta_soc_prepeak > 0`;
- `delta_soc_peak < 0`;
- `charge_window_valve_mean < -0.05`;
- `discharge_window_valve_mean > 0.05`;
- `discharge_window_sign_rate >= 0.80`;
- comfort and guard metrics non-regressive;
- paired cost not materially worse.

Run 96-step first. Run 672-step only if 96-step has no severe/fatal/traceback/NaN and monitor fields prove BC/projection provenance is correct.

## 9. Scientific Boundary and Paper Language

Allowed language:

- "rule-informed curriculum";
- "planner-guided warm-start";
- "TES-only MPC oracle used for labels";
- "final learned actor evaluated without planner calls";
- "safety projection enforces physical feasibility only".

Avoid:

- "the RL policy learned arbitrage" if runtime price rules are active;
- "same-HVAC counterfactual" unless exact HVAC action replay is implemented;
- hiding rule/MPC labels inside reward and presenting them as pure RL;
- using an online MPC controller as the final learned policy row.

Paper-facing framing:

The clean claim is not that no planning exists anywhere in the research pipeline. The clean claim is that any rule or MPC is used either as a baseline/oracle or as removable training curriculum; final learned-policy rollouts do not call that planner and do not contain runtime economic if-else overrides.

## 10. Stop Conditions and Longer-Run Criteria

Stop P1 planner-guided warm-start if, after 2 seeds x 5 episodes:

- `charge_window_sign_rate` does not improve over O1 and C2b;
- `low_price_discharge_fraction` remains above `0.50`;
- `delta_soc_prepeak` is not positive in both seeds;
- BC monitor shows the actor matched labels early but lost the behavior immediately after decay;
- final checkpoint still has nonzero BC weight;
- evaluation requires runtime planner calls to look good.

Stop S1 safety projection if:

- it improves only by clipping into a hidden economic controller;
- it causes material comfort regression;
- projection is active on most TES steps, leaving little learned control authority.

Escalate to planner/MPC as a reported controller baseline, not RL, if:

- TES-only MPC oracle passes the mechanism gate but learned actor with removable BC cannot retain behavior;
- evidence shows the task requires explicit lookahead that the current feed-forward RL setup cannot approximate at short horizon.

Allow reconsidering 10-episode, 30-episode, or full-year training only after:

- 2 seeds x 5 episodes pass the 672-step mechanism gate with final BC weight zero;
- no runtime planner is active in learned-policy evaluation;
- comfort and guard metrics are acceptable;
- paired cost is non-worse or the mechanism gain is strong enough to justify a longer validation run;
- Review Worker confirms provenance and P0.2 metrics from raw monitors.

## 11. Checklist Update

This design closes the reward/entropy/action-smoothing exploration loop for the current short-run evidence set:

- reward/PBRS branch: completed for short mechanism testing and failed the 672-step gate;
- entropy branch: completed for short mechanism testing and failed the 672-step gate;
- action semantics branch: A-prime completed and failed the 672-step gate;
- action smoothing / option hold branch: O1 completed and failed the 672-step gate;
- planner/MPC/safety route: design implemented/pending review.

Recommended next code task: implement P1 planner-guided TES-head BC warm-start behind feature flags, with final-eval guards proving the planner is inactive and BC weight is zero.
