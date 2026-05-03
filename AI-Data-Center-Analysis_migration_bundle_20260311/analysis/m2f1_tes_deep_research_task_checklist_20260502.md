# M2-F1 TES Deep Research Task Checklist

Date: 2026-05-02

Source report: `C:\Users\18430\Desktop\毕业设计代码\deep-research-report (1).md`

Scope: convert the deep-research report into an executable checklist for M2-F1 TES time-of-use arbitrage recovery. This file is a planning and handoff artifact only. Docs Worker does not modify code.

## Global Constraints

- [ ] Treat the current repository as a shared worktree. Do not revert other people's edits.
- [ ] Do not delete or overwrite untracked evidence directories or result files under `analysis/`, `runs/`, or related experiment folders.
- [ ] Do not change code as part of this document task.
- [ ] Do not commit.
- [ ] Do not push.
- [ ] Keep old evidence intact; new evidence must go into new timestamped files/directories.
- [ ] Every code-related task below must be executed by `Implementation Worker` and reviewed by `Review Worker`.
- [ ] Main agent / Docs Worker must not directly edit code files.
- [ ] Final paper-facing checkpoints must not rely on persistent non-PBRS rule rewards, teacher rewards, or action-dependent alignment rewards.
- [ ] Training-time rule guidance is allowed only as a removable curriculum/regularizer and must be fully off in final evaluation checkpoints.

## Current Baseline

- [ ] M2-F1 objective: validate TES time-of-use arbitrage only; no workload action.
- [ ] Observation dimension: 32.
- [ ] Agent action dimension: 4, ordered as `[CT_Pump_DRL, CRAH_T_DRL, Chiller_T_DRL, TES_DRL]`.
- [ ] TES action semantics: negative valve charges TES; positive valve discharges TES.
- [ ] TES action is a target valve command, rate-limited by `0.25/step`.
- [ ] SOC guard rails: stop charging at `SOC >= 0.90`; stop discharging at `SOC <= 0.10`.
- [ ] Main reward baseline: `rl_cost`.
- [ ] Current target-SOC PBRS baseline:
  - high price: `price_current_norm >= 0.75`, target SOC `0.30`;
  - low price near peak: `price_current_norm <= -0.50` and `hours_to_next_peak_norm <= 0.40`, target SOC `0.85`;
  - neutral: target SOC `0.50`.
- [ ] Existing A/B evidence: agent does use TES, but mainly learns "high-price more discharge / low-price less discharge"; it has not reliably learned low-price active charging.
- [ ] Existing warning: `price_response_high_minus_low > 0` is insufficient evidence of arbitrage.
- [ ] Current suspected primary cause: reward/target structure and action semantics create an easier local optimum than inventory-style arbitrage.

## P0 - Highest Priority

### P0.1 Reward Decomposition Audit - implemented/pending review

- [x] **Code task | Implementation Worker executes | Review Worker reviews | Main agent does not edit code:** add or verify reward-monitor fields around key TOU windows. Status: implemented/pending review.
- [ ] Emit the following fields for each inspected step:
  - `TES_SOC`
  - `tes_valve_target`
  - `TES_valve_wrapper_position`
  - `price_current_norm`
  - `price_hours_to_next_peak_norm`
  - `reward`
  - `cost_term`
  - `energy_term`
  - `comfort_term`
  - `tes_pbrs_term`
  - `tes_teacher_term`
  - `tes_tou_alignment_term`
  - `tes_valve_penalty`
  - `tes_invalid_action_penalty`
- [ ] Audit windows:
  - low-price window start: previous 8 steps through next 8 steps;
  - peak-price window start: previous 8 steps through next 8 steps.
- [ ] Acceptance check: identify which reward component pulls against charge sign during the first hour when the policy should flip from discharge/idle to charge.
- [ ] Stop if `cost_term + energy_term + valve_penalty` consistently overwhelms `tes_pbrs_term`; fix reward structure before longer training.

### P0.2 Evaluation Gate Upgrade - implemented/pending review

- [x] **Code task | Implementation Worker executes | Review Worker reviews | Main agent does not edit code:** add evaluation metrics that directly test real arbitrage, not only price response. Status: implemented/pending review.
- [ ] Required metrics:
  - `charge_window_sign_rate`: fraction of low-price near-peak steps where actual valve `< -0.05`;
  - `discharge_window_sign_rate`: fraction of peak-price steps where actual valve `> 0.05`;
  - `delta_soc_prepeak`: SOC at end of pre-peak charge window minus SOC at start of that window;
  - `delta_soc_peak`: SOC at end of peak window minus SOC at start of that window;
  - `low_price_valve_mean`;
  - `high_price_valve_mean`;
  - `tes_marginal_profit` or clearly named equivalent cost delta using paired counterfactual evaluation.
- [x] Current implemented counterfactual cost delta uses matched independent deterministic rollouts, not strict same-HVAC action replay. `tes_marginal_saving_usd = cost(learned_hvac_tes_zero) - cost(full_learned)` compares:
  - `full_learned`;
  - `learned_hvac_tes_zero`.
- [ ] Acceptance check: a policy is not considered successful unless it shows negative low-price valve use, positive pre-peak SOC lift, and non-worse paired cost.

### P0.3 Baseline Preservation

- [ ] Record current C0 configuration before code changes.
- [ ] Preserve existing evidence files:
  - `analysis/m2f1_toualign_ab3ep_20260501_status.md`;
  - `analysis/m2f1_toualign_ab3ep_20260501_status.json`;
  - existing `m2f1_toualign_*_audit.json`;
  - existing `m2f1_tes_reward_audit_20260501*.json`;
  - existing failed-run and diagnostic directories.
- [ ] New results must use a new label, for example `m2f1_sparsepbrs_20260502_*`.

## P1 - Reward Structure Repair

### P1.1 Sparse Arbitrage PBRS - implemented/pending review

- [x] **Code task | Implementation Worker executes | Review Worker reviews | Main agent does not edit code:** change target-SOC PBRS so neutral periods have no shaping. Status: implemented/pending review via `--tes-neutral-pbrs-mode zero`.
- [ ] Required behavior:
  - high-price window: keep low SOC target;
  - low-price near-peak window: keep high SOC target;
  - all other periods: `phi = 0`, not target SOC `0.50`.
- [ ] Recommended parameters:
  - `soc_charge_target = 0.90`;
  - `soc_discharge_target = 0.25`;
  - `kappa = 1.0` initially, with `2.0` as later ablation only;
  - `gamma = 0.99`.
- [ ] Acceptance check: monitor output must show `tes_pbrs_term = 0` or equivalent no-shaping behavior in neutral periods.

### P1.2 Wider Low-Price Charge Window

- [ ] **Code task | Implementation Worker executes | Review Worker reviews | Main agent does not edit code:** widen the low-price near-peak charge window.
- [ ] Required default change:
  - `tes_low_price_threshold`: `-0.50 -> -0.10`;
  - `tes_near_peak_threshold`: `0.40 -> 0.60`.
- [ ] Acceptance check: low-price near-peak mask covers roughly the intended pre-peak charge window and is visible in audit output.

### P1.3 Valve Regularization Default

- [ ] **Code task | Implementation Worker executes | Review Worker reviews | Main agent does not edit code:** set or expose a lower default valve penalty for C1.
- [ ] Recommended C1 value: `tes_valve_penalty_weight = 0.001`.
- [ ] Acceptance check: charge/discharge sign flips are not suppressed by excessive quadratic valve penalty.

### P1.4 C0 vs C1 Short Training

- [ ] Run C0 and C1 as a mechanism test, not as final thesis evidence.
- [ ] Use `2 seeds x 5 episodes`.
- [ ] Suggested seeds: `1` and `4`, matching recent evidence where possible.
- [ ] C0: current configuration.
- [ ] C1: sparse PBRS + widened low-price window + no teacher + no alignment.
- [ ] Store each run under a new label and write summary artifacts into `analysis/`.
- [ ] Acceptance check: C1 should improve `charge_window_sign_rate`, `delta_soc_prepeak`, and paired cost delta versus C0.

## P2 - Credit Assignment and Removable Guidance

### P2.1 TES-Head Short-Term Regularizer

- [ ] **Code task | Implementation Worker executes | Review Worker reviews | Main agent does not edit code:** implement TES-head-only regularization as training-time curriculum, not as persistent reward.
- [ ] Regularizer form:
  - `L_actor = L_rl + lambda_reg(t) * mask_tou(t) * (a_tes - a_rule_tes)^2`.
- [ ] Decay:
  - `lambda_reg(t) = lambda0 * max(0, 1 - episode / bc_decay_episodes)`.
- [ ] Defaults:
  - `lambda_bc0 = 0.2`;
  - `bc_decay_episodes = 2`;
  - active only when desired TES sign is nonzero;
  - fully off from episode 3 onward in a 5-episode run.
- [ ] Acceptance check: final checkpoint used for evaluation must have regularization weight exactly `0`.

### P2.2 State Feature Additions - implemented/pending review

- [x] **Code task | Implementation Worker executes | Review Worker reviews | Main agent does not edit code:** add low-cost TES learning features only if C1 does not produce sign flip. Status: implemented/pending review via `--enable-tes-state-augmentation`.
- [ ] Candidate features:
  - `delta_soc_1step = SOC_t - SOC_{t-1}`;
  - `time_in_tou_window_norm` from continuous TOU charge/discharge/neutral phase duration.
- [ ] Default compatibility: feature flag remains off, so baseline observation dimension stays 32; C2b runs must enable the flag explicitly and use 34D normalization/checkpoints.
- [ ] Acceptance check: observation schema, normalization, training, and evaluation stacks remain aligned.

### P2.3 Raw Target to Actual Valve Transition Audit

- [ ] **Code task | Implementation Worker executes | Review Worker reviews | Main agent does not edit code:** add focused diagnostics for window-switch transition points if missing.
- [ ] Required diagnostics:
  - `raw_actual_divergence`;
  - `raw_actual_divergence_p95`;
  - `tes_intent_to_effect_ratio`;
  - divergence conditioned on TOU window transitions.
- [ ] Acceptance check: report whether sign-flip failures cluster near low-price or peak window boundaries.

### P2.4 C2 Short Training

- [ ] Run C2 only if C1 does not clearly produce low-price charging.
- [ ] C2 configuration:
  - base = C1;
  - TES-head regularizer enabled for first 2 episodes only;
  - pure RL fine-tune for episodes 3-5;
  - teacher/alignment reward terms remain off.
- [ ] Acceptance check: if C2 works and C1 does not, classify the main remaining issue as exploration/credit assignment rather than physical infeasibility.

## P3 - Third Priority and Medium-Term Route

### P3.0 Action Semantics Predesign - implemented/pending review

- [x] **Design/docs task | Design/Docs Worker executes | Review Worker reviews | Main agent does not edit training code:** create TES action semantics predesign after C1/C2/C2b/C3 all failed the 672-step low-price active charge mechanism gate. Status: implemented/pending review.
- [x] Design artifact: `analysis/m2f1_tes_action_semantics_predesign_20260502.md`.
- [x] Recommended minimum route: default-off continuous direction-plus-amplitude TES semantics, preserving SB3/DSAC-T continuous action machinery while making charge/idle/discharge explicit to the agent.
- [ ] Review acceptance check: confirm the design does not introduce a runtime economic rule controller and keeps EnergyPlus/site/TOU/PV/workload/fixed-fan assumptions intact.

### P3.1 Entropy Ablation - completed/failed

- [x] **Code task | Implementation Worker executes | Review Worker reviews | Main agent does not edit code:** expose or verify target entropy override for a small ablation only after P1/P2. Status: completed for short mechanism testing; failed the 672-step P0.2 mechanism gate.
- [ ] Grid:
  - `target_entropy = -4.0`;
  - `target_entropy = -2.0`;
  - `target_entropy = -1.33`.
- [ ] Run each with 2 seeds and 5 episodes, holding all other settings fixed.
- [ ] Acceptance check: use this only to decide whether charge behavior appears only under higher exploration.
- [x] Branch outcome 2026-05-02: C3 entropy `-4.0` and `-2.0`, with C2b `-1.3333333333333333` baseline, did not produce any passing 672-step mechanism row. Stop reward/entropy tuning for this branch.

### P3.2 TES Discrete or Hybrid Action Head - A-prime implemented/pending review

- [x] **Code task | Implementation Worker executes | Review Worker reviews | Main agent does not edit code:** implement default-off A-prime TES action semantics if C2/C2b/C3 still fail. Status: implemented/pending review via `--tes-action-semantics direction_amp`.
- [x] A-prime route keeps SB3/DSAC-T continuous action support by exposing `[TES_direction_DRL, TES_amplitude_DRL]` and mapping it to the legacy signed TES target before `TESTargetValveWrapper`.
- [x] Default compatibility: `--tes-action-semantics signed_scalar` remains the default 4D action path; `direction_amp` is opt-in and requires 5D checkpoints/eval.
- [x] **Design/docs task | Design/Docs Worker executes | Review Worker reviews | Main agent does not edit training code:** create option / hold-mode design after A-prime failed the 672-step low-price active charge mechanism gate. Status: implemented/pending review.
- [x] Option / hold-mode design artifact: `analysis/m2f1_tes_option_holdmode_design_20260502.md`.
- [x] Recommended next route: O1 `direction_amp_hold`, a default-off 5D action wrapper that holds actor-selected TES mode and amplitude for 4 steps without reading runtime price/SOC.
- [x] **Code task | Implementation Worker executes | Review Worker reviews | Main agent does not edit code:** implement default-off O1 `direction_amp_hold` action semantics. Status: implemented/pending review via `--tes-action-semantics direction_amp_hold --tes-option-hold-steps 4`.
- [x] A-prime evidence outcome 2026-05-02: 2 seed x 5ep `direction_amp` completed and failed the 672-step low-price active charging gate.
- [x] O1 evidence outcome 2026-05-02: 2 seed x 5ep `direction_amp_hold` completed and failed the 672-step low-price active charging gate. Stop action-smoothing/deadband/amplitude small tuning and move to planner/MPC/safety design.
- [ ] Version A:
  - high-level mode: `{charge, idle, discharge}`;
  - continuous amplitude: `[0, 1]`;
  - final target: `sign(mode) * amp`.
- [x] Version B:
  - option-style TES mode updated every 4 steps;
  - mode persists for 1 hour;
  - lower layer handles smooth execution.
- [ ] Suggested defaults:
  - minimum mode duration: 4 steps;
  - amplitude initialization range: `[0.4, 1.0]`;
  - mode switching penalty: `1e-3`.
- [ ] Acceptance check: compare against continuous TES target with identical reward and evaluation gates.

### P3.3 TES Small Planner, MPC, or Safety Projection - design implemented/pending review

- [x] **Design/docs task | Design/Docs Worker executes | Review Worker reviews | Main agent does not edit training code:** create planner/MPC/safety projection design after C1/C2/C2b/C3/A-prime/O1 all failed the 672-step low-price active charge mechanism gate. Status: implemented/pending review.
- [x] Design artifact: `analysis/m2f1_tes_planner_mpc_safety_design_20260502.md`.
- [x] Recommended next route: planner-guided TES-head BC warm-start with final evaluation proving no runtime planner calls and BC weight exactly zero.
- [x] **Code task | Implementation Worker executes | Review Worker reviews | Main agent does not edit code:** implement default-off planner-guided TES-head BC warm-start. Status: implemented/pending review via `--tes-bc-weight`, DSAC-T actor-loss integration only, with no runtime planner in evaluation.
- [x] P1a execution outcome 2026-05-02: `--tes-bc-weight 0.10 --tes-bc-decay-episodes 1`, 2 seeds x 5 episodes, `direction_amp_hold`, completed. Final training metadata proves `tes_bc_current_weight=0.0`, `tes_bc_final_weight_zero=true`, and `tes_bc_runtime_planner_enabled=false`. 96/672 trainlike evaluation summary: `analysis/m2f1_bc_warmstart_5ep_eval_summary_20260502.json`.
- [x] P1a gate outcome 2026-05-02: failed the 672-step P0.2 mechanism gate. Mean 672 metrics: `charge_window_sign_rate=0.103`, `low_price_discharge_fraction=0.655`, `delta_soc_prepeak=+0.0236`, `delta_soc_peak=+0.0108`, `low_price_valve_mean=+0.323`, `high_price_valve_mean=+0.376`.
- [x] P1a counterfactual cost note 2026-05-02: mean `tes_marginal_saving_usd=+9320.83`, computed as `cost_usd(learned_hvac_tes_zero) - cost_usd(full_learned)` from separate deterministic rollouts matched by checkpoint/design/workspace, not strict same-HVAC-actions counterfactual evidence.
- [ ] P1b `--tes-bc-decay-episodes 2` remains not run in this execution pass because P1a runtime was high and P1a already failed the strict 672-step gate; run only if Review Worker wants a decay-length ablation before moving to stronger planner/MPC routes.
- [ ] **Code task | Implementation Worker executes | Review Worker reviews | Main agent does not edit code:** evaluate a medium-term projection/planner route only after reward and action-head evidence is available.
- [ ] Minimum projection constraints:
  - SOC lower/upper bounds;
  - max valve change rate;
  - charge/discharge mutual exclusivity;
  - optional comfort margin.
- [ ] Lightweight alternative:
  - one-hour rolling TES planner selects charge/idle/discharge;
  - RL still controls HVAC fine actions.
- [ ] Acceptance check: compare with current wrapper clipping on `raw_actual_divergence`, `charge_window_sign_rate`, comfort violations, and training stability.

### P3.4 Recurrent or Frame-Stack Follow-Up

- [ ] **Code task | Implementation Worker executes | Review Worker reviews | Main agent does not edit code:** consider recurrent TES head or frame stack only if evidence points to partial observability after P1-P3.3.
- [ ] Acceptance check: do not add recurrent complexity until reward, removable guidance, and action semantics have been tested.

## Experiment Matrix

| ID | Purpose | Config Delta | Seeds | Episodes | Required Gate |
|---|---|---|---:|---:|---|
| C0 | Preserve current baseline | current config | 1, 4 | 5 | baseline metrics only |
| C1 | Test reward-structure hypothesis | neutral `phi=0`; low threshold `-0.10`; near-peak `0.60`; charge target `0.90`; discharge target `0.25`; valve penalty `0.001`; teacher `0`; alignment `0` | 1, 4 | 5 | sign rate, pre-peak SOC lift, paired cost |
| C2 | Test removable guidance | C1 + TES-head regularizer for episodes 1-2 only | 1, 4 | 5 | effect persists after regularizer is off |
| E1 | Test exploration only if needed | C1 or C2 base + entropy grid | 1, 4 | 5 | charge behavior sensitivity to entropy |
| A1 | Test action semantics | C1 base + hybrid/discrete TES head | 1, 4 | 5-10 | sign flip without comfort regression |
| O1 | Test time abstraction | C1 base + hourly TES option | 1, 4 | 5-10 | smoother pre-peak charge and peak discharge |
| M1 | Test projection/planner route | RL suggestion + TES safety projection or small rolling planner | 1, 4 | 5-10 | lower divergence and better stability |

## Test Matrix

| Test | Owner | When | Pass Criteria |
|---|---|---|---|
| Git/worktree preflight | Implementation Worker | before code changes | dirty state recorded; unrelated changes untouched |
| Static import / syntax check | Implementation Worker | after code changes | changed Python files import or compile without syntax errors |
| Wrapper smoke test | Implementation Worker | after wrapper/reward changes | one short environment run emits expected TES fields |
| Reward audit test | Implementation Worker | after P0/P1 | key-window CSV/JSON contains all required reward components |
| Evaluation metric test | Implementation Worker | after P0.2 | metrics are present for learned and counterfactual policies |
| Training/evaluation stack alignment check | Review Worker | after P1/P2 | wrappers and normalization are consistent between train/eval |
| Evidence preservation check | Review Worker | before handoff | old files/directories still exist; only new artifacts added |
| Result review | Review Worker | after each matrix row | gates computed from raw evidence, not only summary prose |

## Training Defaults

- [ ] Use 15-minute steps and annual episode semantics already present in M2.
- [ ] Use 2 seeds for short mechanism tests: `1` and `4`.
- [ ] Use 5 episodes for C0/C1/C2 short tests unless a runtime failure occurs.
- [ ] Keep network architecture and algorithm defaults fixed for C0/C1/C2 unless the task explicitly changes them.
- [ ] Keep observation normalization protocol fixed unless testing state feature changes.
- [ ] C1 defaults:
  - `low_price_threshold = -0.10`;
  - `near_peak_threshold = 0.60`;
  - `soc_charge_target = 0.90`;
  - `soc_discharge_target = 0.25`;
  - neutral PBRS disabled with `phi=0`;
  - `kappa = 1.0`;
  - `gamma = 0.99`;
  - `tes_valve_penalty_weight = 0.001`;
  - `teacher = 0`;
  - `alignment = 0`.
- [ ] C2 defaults:
  - base = C1;
  - `lambda_bc0 = 0.2`;
  - `bc_decay_episodes = 2`;
  - regularizer active only in desired-sign TOU windows;
  - no persistent teacher/alignment reward.

## Evaluation Gate

- [ ] Do not use `price_response_high_minus_low` as a success gate by itself.
- [ ] Required behavior gate:
  - low-price near-peak actual valve mean should be negative or at least contain material negative-valve usage;
  - `charge_window_sign_rate` should be reported and should improve over C0;
  - `delta_soc_prepeak` should be positive for candidate-success runs;
  - peak window should show discharge behavior and SOC drawdown.
- [ ] Required economic gate:
  - paired counterfactual cost delta must be non-worse, and preferably show lower cost for full learned TES;
  - current `tes_marginal_saving_usd` sign is `cost(learned_hvac_tes_zero) - cost(full_learned)`, using matched independent deterministic rollouts rather than strict same-HVAC action replay; successful TES marginal saving should be `> 0`.
- [ ] Required comfort/safety gate:
  - comfort violations must not worsen materially versus C0 or TES-zero counterfactual;
  - guard clipping fraction must be reported;
  - raw-to-actual divergence must be reported, especially near TOU transitions.
- [ ] Required statistical summary:
  - use `seed x day` as paired units where possible;
  - report paired bootstrap 95% CI for `tes_marginal_profit`, `delta_soc_prepeak`, and `charge_window_sign_rate`;
  - optionally add paired permutation test or Wilcoxon signed-rank.

## Stop Conditions

- [ ] Stop long training if P0 audit shows the reward components structurally oppose low-price charge and P1 has not been implemented.
- [ ] Stop using persistent teacher/alignment rewards for final claims; they can only be used as training-time curriculum and must decay to zero.
- [ ] Stop escalating to action-head or MPC work if C1 already passes behavior and economic gates; instead proceed to longer validation.
- [ ] Stop entropy ablations if C1/C2 already explain the failure mode.
- [ ] Stop C2 if regularization remains nonzero in final evaluation checkpoint.
- [ ] Stop claiming "TES arbitrage learned" if low-price negative-valve usage and pre-peak SOC lift are absent.
- [ ] Stop any experiment that overwrites previous evidence or requires deleting untracked result folders.

## Execution Protocol

1. [ ] Docs Worker creates this checklist only and does not edit code.
2. [ ] Implementation Worker records `git status --short` before code work.
3. [ ] Implementation Worker implements the smallest next code task from this checklist.
4. [ ] Implementation Worker writes new evidence under a new timestamped label.
5. [ ] Review Worker reviews the code diff, confirms role boundaries, and checks that unrelated dirty files were not reverted.
6. [ ] Review Worker verifies that each code-related task includes tests or explicit no-test rationale.
7. [ ] Review Worker confirms no old evidence files/directories were deleted.
8. [ ] Only after review, run the next experiment matrix row.
9. [ ] After each experiment row, update an analysis summary with raw metrics, gate result, and decision: continue, stop, or escalate.

## Recommended First Code Task

- [ ] **Code task | Implementation Worker executes | Review Worker reviews | Main agent does not edit code:** implement P0.2 evaluation gate metrics first, especially `charge_window_sign_rate`, `delta_soc_prepeak`, and paired counterfactual TES cost delta.
- [ ] Rationale: without these gates, later reward or action changes can look better on price response while still failing the real objective: low-price charge, peak discharge, and actual TES marginal value.
