# M2-F1 TES Option / Hold-Mode Design

Date: 2026-05-02

Scope: design only. This document does not implement code, does not change EnergyPlus physics, does not change site / TOU / PV data, does not add workload action, and keeps the fixed CRAH fan assumption.

## 1. Evidence Summary

C1, C2, C2b, C3, and A-prime all failed the 672-step low-price active charging mechanism gate. The repeated failure mode is not "TES never moves"; TES moves, but the learned policy still prefers discharge or positive valve bias inside the low-price pre-peak charging window.

Latest A-prime evidence is from `analysis/m2f1_aprime_diramp_5ep_eval_summary_20260502.json`, comparing C2b state augmentation against A-prime `direction_amp`.

672-step mean comparison:

| Experiment | action_dim | charge_window_sign_rate | low_price_discharge_fraction | delta_soc_prepeak | charge_window_valve_mean | discharge_window_sign_rate | delta_soc_peak |
|---|---:|---:|---:|---:|---:|---:|---:|
| C2b baseline | 4 | 0.306 | 0.634 | +0.0320 | +0.148 | 0.858 | -0.0008 |
| A-prime direction_amp | 5 | 0.214 | 0.654 | -0.0140 | +0.261 | 0.879 | -0.0017 |

A-prime made the direction sign explicit, but did not create sustained low-price charging. In 672-step evaluation:

- seed 1: `charge_window_sign_rate=0.183`, `low_price_discharge_fraction=0.655`, `delta_soc_prepeak=-0.0083`, `charge_window_valve_mean=+0.292`.
- seed 4: `charge_window_sign_rate=0.245`, `low_price_discharge_fraction=0.653`, `delta_soc_prepeak=-0.0198`, `charge_window_valve_mean=+0.230`.

This means simple direction/amplitude semantics reduce one ambiguity, but do not solve the temporal commitment problem. The actor can still change TES intent every 15-minute step, and short-horizon critic noise can favor the easier local optimum: positive valve use during many low-price windows, with only transient or inconsistent charge attempts. The mechanism problem is now better described as missing time abstraction / option persistence, not as a missing reward scalar, deadband, or amplitude transform.

## 2. Design Goal

Introduce an agent-facing temporal abstraction for TES action semantics:

- TES mode should persist for at least 4 steps, i.e. 1 hour at the current 15-minute timestep.
- The persistent mode is chosen by the actor, not by a runtime price/SOC rule.
- The wrapper must not inspect TOU price, PV, workload, comfort, or SOC to decide when to charge or discharge.
- The wrapper may keep internal option state: current mode, held amplitude, hold counter, elapsed steps since last mode acceptance.
- EnergyPlus TES physics, `TESTargetValveWrapper`, SOC guard rails, fixed fan, site data, TOU/PV signals, and reward definitions remain unchanged.

The intended learning effect is to make "charge for an hour" and "discharge for an hour" easier for DSAC-T to represent than four independent 15-minute sign decisions.

## 3. Scheme O1: Direction/Amplitude Option Hold

Actor output each step:

`[CT_Pump_DRL, CRAH_T_DRL, Chiller_T_DRL, TES_direction_DRL, TES_amplitude_DRL]`

Wrapper behavior:

- Map `TES_direction_DRL` to a proposed mode using the A-prime convention:
  - `direction_raw > deadband`: `discharge`
  - `direction_raw < -deadband`: `charge`
  - otherwise: `idle`
- Map `TES_amplitude_DRL` from `[-1, 1]` to `[0, 1]`.
- Only when `hold_counter == 0` does the wrapper accept a new mode.
- For the next 4 steps, it keeps the accepted mode.
- Convert held mode and amplitude into signed target:
  - `charge`: `-amp`
  - `idle`: `0`
  - `discharge`: `+amp`
- The signed target is then passed to the existing fixed-fan / `TESTargetValveWrapper` chain.

Amplitude handling choices:

- Option A: mode hold, amp updates every step.
- Option B: mode and amp are both held for 4 steps.

Recommended for the minimum experiment: hold both mode and amplitude for 4 steps. If amplitude can update every step, the actor can pick `charge` at the option boundary and then immediately reduce amplitude toward zero, which weakens the intended temporal abstraction. Holding both mode and amp creates a clearer option interface and a cleaner experiment. If this is too rigid, a later ablation can keep mode held while allowing amplitude updates within the same mode.

No runtime economic rule is introduced: the actor chooses the option, and the wrapper only enforces persistence.

## 4. Scheme O2: Signed Scalar With Hold Hysteresis

Actor output remains legacy 4D:

`[CT_Pump_DRL, CRAH_T_DRL, Chiller_T_DRL, TES_DRL]`

Wrapper maps signed scalar into mode and amplitude:

- `TES_DRL < -deadband`: proposed `charge`, amplitude `abs(TES_DRL)`.
- `TES_DRL > deadband`: proposed `discharge`, amplitude `abs(TES_DRL)`.
- deadband: proposed `idle`.

Then it applies the same 4-step mode hold.

Why O2 may be weaker than O1:

- It preserves the original signed scalar coupling between sign and magnitude.
- Small signed noise around zero still changes both mode evidence and amplitude evidence.
- It is harder to monitor whether the actor intended an explicit mode or merely produced a scalar residual.
- It does not use the A-prime evidence that explicit direction/amplitude instrumentation is useful for diagnosis, even if insufficient alone.

O2 is lower-risk for checkpoint compatibility because it keeps action_dim 4, but it is less aligned with the current diagnosis.

## 5. Scheme O3: Training-Time Option Curriculum / BC Warm Start

O3 is not a runtime controller. It is a training aid that can be removed before final evaluation.

Candidate uses:

- Pretrain or warm-start the TES option head on simple charge/idle/discharge demonstrations generated offline.
- Add a short-lived actor regularizer for the TES mode logits or direction head during the first 1-2 episodes.
- Decay curriculum weight to exactly zero before the final evaluation checkpoint.

Scientific boundary:

- Rule-derived labels are allowed only as removable training curriculum or as evaluation baselines.
- They must not be active in the runtime environment used for final gate evaluation.
- Final monitor/status must record that the curriculum weight is zero at evaluation.

O3 should follow O1 only if O1 fails to discover stable options by itself.

## 6. Recommended Minimum Implementation

Implement O1 as a default-off wrapper, because it directly tests the time-abstraction hypothesis while reusing the A-prime 5D action shape.

Recommended CLI:

- `--tes-action-semantics direction_amp_hold`
- `--tes-direction-deadband 0.15`
- `--tes-option-hold-steps 4`
- Optional later flag: `--tes-option-hold-amp {hold,update}`, default `hold`.

Action dimension:

- Existing default: `signed_scalar`, action_dim 4.
- Existing A-prime: `direction_amp`, action_dim 5.
- New O1: `direction_amp_hold`, action_dim 5.

Action order for O1:

`[CT_Pump_DRL, CRAH_T_DRL, Chiller_T_DRL, TES_direction_DRL, TES_amplitude_DRL]`

Wrapper order:

1. Base EnergyPlus env.
2. `TESTargetValveWrapper` on full action index 4.
3. `FixedActionInsertWrapper` to keep CRAH fan fixed at 1.0.
4. New option/hold wrapper on the reduced fixed-fan action.
5. Time / temperature trend / price / PV / energy scale / optional state augmentation / reward shaping / normalization / logger wrappers as currently configured.

The option wrapper should sit outside `FixedActionInsertWrapper` and inside observation/reward wrappers. The actor sees the held-action action space, while the inner fixed-fan + TES target stack continues to receive the legacy signed TES target.

Mode-hold state:

- `current_mode`: one of `charge`, `idle`, `discharge`.
- `current_amp`: held amplitude in `[0, 1]`.
- `hold_counter_remaining`: number of future steps before a new mode can be accepted.
- `accepted_direction_raw`: raw direction value at the last accepted option boundary.
- `accepted_amplitude_raw`: raw amplitude value at the last accepted option boundary.
- `proposed_mode`: actor's current proposal, recorded even when ignored.
- `mode_change_accepted`: boolean for whether this step accepted a new mode.

Reset behavior:

- Reset `current_mode` to `idle`.
- Reset `current_amp` to `0`.
- Reset `hold_counter_remaining` to `0`, so the first post-reset actor action can open a new option.
- Emit reset info fields with neutral values.

Monitor/info fields:

- `tes_action_semantics`: `direction_amp_hold`
- `tes_option_hold_steps`
- `tes_option_hold_amp_mode`
- `tes_option_current_mode`
- `tes_option_current_amp`
- `tes_option_hold_counter_remaining`
- `tes_option_mode_change_accepted`
- `tes_option_proposed_mode`
- `tes_option_proposed_amp`
- `tes_option_accepted_direction_raw`
- `tes_option_accepted_amplitude_raw`
- Keep A-prime fields:
  - `tes_direction_raw`
  - `tes_amplitude_raw`
  - `tes_amplitude_mapped`
  - `tes_direction_mode`
  - `tes_signed_target_from_semantics`

Status/manifest/result compatibility:

- Training status must record `action_dim=5`, `tes_action_semantics=direction_amp_hold`, `tes_option_hold_steps=4`, and `tes_option_hold_amp_mode=hold`.
- Evaluation tools must reject mismatched checkpoints rather than silently loading a 4D or non-hold 5D checkpoint.
- `paired-eval` and `counterfactual-eval` must support `--tes-action-semantics direction_amp_hold`.
- `learned_hvac_tes_zero` under O1 should force `TES_direction_DRL=0` and `TES_amplitude_DRL=-1` or equivalent neutral signed target, with fields clearly documenting that this is a neutral TES option.

## 7. Risks

Comfort risk:

- Holding a TES mode for 1 hour can keep discharging or charging through a short comfort transient.
- Mitigation: keep existing HVAC actions continuous every step; do not hold CT/CRAH/chiller controls.

SOC guard interaction:

- If the actor holds charge near high SOC or discharge near low SOC, `TESTargetValveWrapper` guard rails will clip actual valve toward neutral.
- This is acceptable safety behavior, but monitor must separate actor option intent from actual guarded valve effect.

Over-persistence:

- A 4-step option may be too long near window boundaries.
- This is a deliberate test: previous per-step actions failed to sustain charging. Later ablation can use 2 or 8 steps, but the first implementation should keep 4 steps because it corresponds to 1 hour and the checklist already names hourly options.

Unable to stop immediately:

- The actor cannot stop a bad TES mode until the next option boundary.
- Mitigation: keep default off, use short 5ep experiments first, and rely on guard rails. Do not proceed to 10ep until comfort and guard metrics are acceptable.

Rate-limit stacking:

- `TESTargetValveWrapper` already rate-limits target-to-actual valve changes by 0.25 per step.
- Option hold plus rate limit may make actual valve transitions slower. This can be beneficial for sustained behavior but may increase raw/actual divergence near option boundaries. Gate summaries must keep `raw_actual_divergence_switch_mean` and `raw_actual_divergence_switch_p95`.

Learning credit:

- Holding options reduces action frequency but does not by itself solve sparse delayed cost credit.
- If O1 improves sign persistence but not paired cost, a planner/projection route may still be needed.

## 8. Test Matrix

Static and smoke:

- `python -m py_compile sinergym\envs\tes_wrapper.py tools\run_m2_training.py tools\smoke_m2_env.py tools\evaluate_m2.py tools\m2_validate_tes_failure_modes.py`
- Help checks for training/smoke/evaluate/m2_validate:
  - `--tes-action-semantics direction_amp_hold`
  - `--tes-option-hold-steps`
  - optional `--tes-option-hold-amp`
- Default smoke:
  - `obs_dim=32`, `action_dim=4`, fixed fan `1.0`.
- O1 smoke:
  - `--enable-tes-state-augmentation`
  - `--tes-action-semantics direction_amp_hold`
  - `--tes-option-hold-steps 4`
  - expected `obs_dim=34`, `action_dim=5`, fixed fan `1.0`.
  - monitor/info contains option hold fields.

Short training:

- O1: 2 seeds x 5 episodes, seeds 1 and 4.
- Base config should match C2b/A-prime reward settings:
  - neutral PBRS zero;
  - low threshold `-0.10`;
  - near-peak threshold `0.60`;
  - target SOC high `0.90`;
  - target SOC low `0.25`;
  - valve penalty `0.001`;
  - short teacher `0.10` with decay 2 episodes if keeping the same base as C2b/A-prime;
  - state augmentation enabled.

Evaluation:

- 96-step `trainlike_soc05 paired-eval`.
- 672-step `trainlike_soc05 paired-eval`.
- Include:
  - `--enable-tes-state-augmentation`
  - `--tes-action-semantics direction_amp_hold`
  - `--tes-option-hold-steps 4`
  - `--tes-direction-deadband 0.15`

Compare against:

- C2b baseline: `analysis/m2f1_c2b_5ep_eval_summary_20260502.json`
- A-prime baseline: `analysis/m2f1_aprime_diramp_5ep_eval_summary_20260502.json`

Primary gate:

- `charge_window_sign_rate` materially improves versus C2b and A-prime.
- `low_price_discharge_fraction` materially decreases.
- `delta_soc_prepeak` is positive in both seeds over 672 steps.
- `charge_window_valve_mean` is negative or near-zero with clear negative sign fraction.
- `discharge_window_sign_rate` remains high.
- `delta_soc_peak` is non-positive in peak windows.
- comfort violations do not regress materially.
- paired cost is not worse enough to invalidate mechanism gains.

## 9. Stop Conditions

Stop option/hold-mode tuning if O1 2 seed x 5ep fails the 672-step mechanism gate:

- low-price active charging does not improve versus C2b/A-prime;
- `low_price_discharge_fraction` remains high;
- `delta_soc_prepeak` remains zero or negative in both seeds;
- option monitor shows actor is selecting charge but actual valve is blocked by guard/rate limit most of the time;
- comfort or guard clipping becomes materially worse.

If these hold, do not continue reward, entropy, deadband, or amplitude tuning. Move to a planner/MPC or safety-projection route:

- RL controls HVAC and proposes TES intent;
- a small TES planner/projection enforces inventory feasibility, SOC bounds, and mode consistency;
- rule logic is evaluated as a planner/projection layer, not disguised as reward shaping.

## 10. Handoff Recommendation

Proceed to code implementation of O1 only. Do not implement O2 or O3 in the first pass.

The minimum useful experiment is:

- default-off `direction_amp_hold`;
- 5D action space matching A-prime;
- mode and amplitude held for 4 steps;
- no runtime price/SOC rule;
- existing `TESTargetValveWrapper` remains the only safety guard;
- 2 seed x 5ep short training followed by 96/672 P0.2 gate.
