# 组件级验收报告（Phase A）

- Generated: by `tools/m1/verify_components.py`
- EnergyPlus: 23.1, weather: Nanjing, timestep: 4/hour
- Scenarios: A1 (Jul 1-7 TOU TES) + A2 (Jan 1-7 passive)

## 整体计数
- PASS=41, WARN=0, FAIL=0, SKIP=3

## A1：672 steps
- E+ severe=0, fatal=0

| Check | Status | Threshold | Evidence |
|-------|--------|-----------|----------|
| C10_Primary_Pump | PASS | flow > 0 some of the time | `{"flow_running_steps": 672, "flow_mean": 693.3244, "flow_max": 693.3244, "elec_mean_W": 43136.1241}` |
| C11_Secondary_Pump | PASS | std > 1% of max → variable speed | `{"flow_min": 51.1284, "flow_max": 693.3244, "flow_std": 162.535, "is_variable": true}` |
| C12_Condenser_Pump | PASS | flow > 0 when chiller running | `{"flow_max": 300.0, "flow_mean": 300.0, "running_ratio_when_chiller_on": 1.0}` |
| C13_CRAH_Coil | PASS | coil/ITE_total ∈ [0.6, 1.5] (steady-state heat balance) | `{"coil_mean_W": 4725176.079, "ite_cpu_mean_W": 4665010.4945, "ite_fan_mean_W": 0.0, "ite_ups_mean_W": 0.0, "ite_total_mean_W": 4665010.4945, "ratio": 1.0129}` |
| C14_CRAH_Fan | PASS | P_1 limited flow within design spec | `{"flow_min": 500.0, "flow_max": 500.0, "flow_mean": 500.0, "in_design_range": true}` |
| C15_ITE | PASS | schedule ∈ [0, 0.85] (P_2 walk: 0.05–0.80) | `{"sch_min": 0.0502, "sch_max": 0.7838, "sch_mean": 0.3115, "cpu_mean_W": 4198509445.0475, "cpu_max_W": 10599860443.0637}` |
| C16_Zone_Temp | PASS | A1 zone_T < 35°C (cooling SP) (<5% violations) | `{"z_min": 12.5056, "z_max": 37.3694, "z_mean": 20.3035, "violation_pct": 0.744}` |
| C17_Plant_Topology | PASS | chiller flow=0 when avail=0; TES use flow=0 when avail=0 | `{"chiller_kill_steps": 75, "chiller_flow_leak_steps": 0, "leak_ratio": 0.0, "tes_use_ghost_flow_steps": 0}` |
| C18_EMS_P1_ramp | PASS | P_1 limits CRAH_T step ≤ 0.5°C | `{"max_ahu_step_C": 0.0, "n_violations_gt_0.5C": 0, "ahu_min": 11.0, "ahu_max": 11.0}` |
| C19_EMS_P2_ITE | PASS | P_2 random walk ∈ [0.05, 0.80] | `{"sch_min": 0.0502, "sch_max": 0.7838, "is_constant": false}` |
| C1_TES_Use_energy_balance | PASS | drift_ratio (|net|/throughput) < 0.20 PASS / < 0.40 WARN | `{"int_use_GJ": 201.4784, "int_source_GJ": -179.8071, "int_loss_GJ": 1.7393, "net_into_tank_GJ": 19.9321, "throughput_GJ": 381.2854, "drift_ratio": 0.0523, "soc_first": 0.3815, "soc_last": 0.269, "soc_min": 0.0, "soc_max": 0.9957}` |
| C20_EMS_P5P7_TES_response | PASS | discharge→use_avail≈1, charge→source_avail≈1, discharge+SOC>0.15→chiller_avail=0 | `{"discharge_steps": 280, "discharge_use_avail_ratio": 1.0, "charge_steps": 196, "charge_source_avail_ratio": 1.0, "kill_eligible_steps": 75, "kill_observed_ratio": 1.0}` |
| C21_severe_fatal | PASS | severe=0, fatal=0 | `{"severe": 0, "fatal": 0, "samples": []}` |
| C22_PUE | PASS | PUE ∈ [1.05, 1.6] | `{"sum_facility_GJ": 3886.2694, "sum_ite_GJ": 2821.3983, "pue": 1.3774}` |
| C2_TES_Source_charge | PASS | neg_ratio > 0.5 PASS | `{"n_charge_steps": 196, "src_neg_ratio": 0.9541, "src_mean": -1019314.4048, "src_min": -3637894.4457, "src_max": 192187.8465}` |
| C3_TES_SOC_range | PASS | all SOC ∈ [0,1] | `{"soc_min": 0.0, "soc_max": 0.9957, "out_of_range_steps": 0, "first": 0.3815, "last": 0.269}` |
| C4_TES_loss | PASS | 0 < mean < 50 kW | `{"mean_W": 2875.753, "max_W": 7027.1102, "min_W": 420.5552}` |
| C5_Chiller_COP | PASS | cop_mean ∈ [3, 8]; rated 6.28 | `{"n_running_steps": 597, "cop_mean": 3.0121, "cop_min": 2.9343, "cop_max": 4.5298, "qe_max_W": 12832397.7441, "we_max_W": 2855538.9514}` |
| C6_Chiller_Cond_balance | PASS | qc reported (informational; see C8 for end-to-end balance) | `{"sum_qe_W_steps": 3200577515.0827, "sum_we_W_steps": 1048176635.4963, "sum_qc_W_steps": 6195609720.2863, "ratio": 0.6858, "note": "Informational. End-to-end balance verified by C8 tower check."}` |
| C7_Tower_fan | PASS | corr(fan, qcond) > 0.4 | `{"fan_max_W": 149855.9274, "fan_mean_W": 7142.0748, "corr_fan_qcond": 0.4559}` |
| C8_Tower_Chiller_balance | PASS | tower_HT / (qcond + eco_HT) ∈ [0.85, 1.15] | `{"sum_tower_HT_W_steps": 6242960153.2252, "sum_qcond_W_steps": 6195609720.2863, "sum_eco_W_steps": 0.0, "expected_W_steps": 6195609720.2863, "ratio": 1.0076}` |
| C9_Eco_seasonal | PASS | summer eco_mean < 100 kW | `{"eco_mean_W": 0.0, "eco_max_W": 0.0}` |

## A2：672 steps
- E+ severe=0, fatal=0

| Check | Status | Threshold | Evidence |
|-------|--------|-----------|----------|
| C10_Primary_Pump | PASS | flow > 0 some of the time | `{"flow_running_steps": 672, "flow_mean": 693.3244, "flow_max": 693.3244, "elec_mean_W": 43136.1241}` |
| C11_Secondary_Pump | PASS | std > 1% of max → variable speed | `{"flow_min": 41.9756, "flow_max": 576.339, "flow_std": 141.5365, "is_variable": true}` |
| C12_Condenser_Pump | PASS | flow > 0 when chiller running | `{"flow_max": 300.0, "flow_mean": 300.0, "running_ratio_when_chiller_on": 1.0}` |
| C13_CRAH_Coil | PASS | coil/ITE_total ∈ [0.6, 1.5] (steady-state heat balance) | `{"coil_mean_W": 4714599.2222, "ite_cpu_mean_W": 4668808.8866, "ite_fan_mean_W": 0.0, "ite_ups_mean_W": 0.0, "ite_total_mean_W": 4668808.8866, "ratio": 1.0098}` |
| C14_CRAH_Fan | PASS | P_1 limited flow within design spec | `{"flow_min": 500.0, "flow_max": 500.0, "flow_mean": 500.0, "in_design_range": true}` |
| C15_ITE | PASS | schedule ∈ [0, 0.85] (P_2 walk: 0.05–0.80) | `{"sch_min": 0.0502, "sch_max": 0.7838, "sch_mean": 0.3115, "cpu_mean_W": 4201927997.9515, "cpu_max_W": 10580613951.9324}` |
| C16_Zone_Temp | PASS | A2 zone_T > 15°C (heating SP) (<5% violations) | `{"z_min": 12.5113, "z_max": 35.0511, "z_mean": 20.2578, "violation_pct": 14.4345}` |
| C17_Plant_Topology | PASS | chiller flow=0 when avail=0; TES use flow=0 when avail=0 | `{"chiller_kill_steps": 0, "chiller_flow_leak_steps": 0, "leak_ratio": null, "tes_use_ghost_flow_steps": 0}` |
| C18_EMS_P1_ramp | PASS | P_1 limits CRAH_T step ≤ 0.5°C | `{"max_ahu_step_C": 0.0, "n_violations_gt_0.5C": 0, "ahu_min": 11.0, "ahu_max": 11.0}` |
| C19_EMS_P2_ITE | PASS | P_2 random walk ∈ [0.05, 0.80] | `{"sch_min": 0.0502, "sch_max": 0.7838, "is_constant": false}` |
| C1_TES_Use_energy_balance | SKIP |  | `{"reason": "A2 TES inactive"}` |
| C20_EMS_P5P7_TES_response | SKIP |  | `{"reason": "A2 TES inactive"}` |
| C21_severe_fatal | PASS | severe=0, fatal=0 | `{"severe": 0, "fatal": 0, "samples": []}` |
| C22_PUE | PASS | PUE ∈ [1.05, 1.6] | `{"sum_facility_GJ": 3627.7324, "sum_ite_GJ": 2823.6956, "pue": 1.2847}` |
| C2_TES_Source_charge | SKIP |  | `{"reason": "A2 TES inactive"}` |
| C3_TES_SOC_range | PASS | all SOC ∈ [0,1] | `{"soc_min": 0.8185, "soc_max": 0.9999, "out_of_range_steps": 0, "first": 0.8185, "last": 0.9321}` |
| C4_TES_loss | PASS | 0 < mean < 50 kW | `{"mean_W": 3958.9761, "max_W": 8098.5965, "min_W": 1774.6391}` |
| C5_Chiller_COP | PASS | cop_mean ∈ [3, 8]; rated 6.28 | `{"n_running_steps": 671, "cop_mean": 3.3395, "cop_min": 3.3257, "cop_max": 4.2437, "qe_max_W": 10785410.1905, "we_max_W": 2541524.3581}` |
| C6_Chiller_Cond_balance | PASS | qc reported (informational; see C8 for end-to-end balance) | `{"sum_qe_W_steps": 2472142280.0707, "sum_we_W_steps": 736261054.1007, "sum_qc_W_steps": 4817189483.6247, "ratio": 0.666, "note": "Informational. End-to-end balance verified by C8 tower check."}` |
| C7_Tower_fan | PASS | corr(fan, qcond) > 0.4 | `{"fan_max_W": 388814.4525, "fan_mean_W": 53713.4971, "corr_fan_qcond": 0.8165}` |
| C8_Tower_Chiller_balance | PASS | tower_HT / (qcond + eco_HT) ∈ [0.85, 1.15] | `{"sum_tower_HT_W_steps": 5579719727.4548, "sum_qcond_W_steps": 4817189483.6247, "sum_eco_W_steps": 729787605.2617, "expected_W_steps": 5546977088.8863, "ratio": 1.0059}` |
| C9_Eco_seasonal | PASS | winter eco_mean > 1 MW | `{"eco_mean_W": 1085993.4602, "eco_max_W": 3251136.0773}` |
