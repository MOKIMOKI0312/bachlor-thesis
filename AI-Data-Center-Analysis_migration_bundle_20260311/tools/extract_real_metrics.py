"""
从 evaluation monitor.csv 中提取真实物理指标。

输出:
  - results/e0_real_metrics.json     (汇总)
  - results/e0_hourly_seed02_best.csv (逐时序列示例)
"""

import csv
import json
import sys
from pathlib import Path
from typing import Dict, List, Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]

# Evaluation run → seed mapping
EVAL_RUNS = {
    'seed01-best':   'run-013',
    'seed01-latest': 'run-014',
    'seed02-best':   'run-015',
    'seed02-latest': 'run-016',
    'seed03-best':   'run-017',
    'seed03-latest': 'run-018',
    'seed04-best':   'run-019',
    'seed04-latest': 'run-020',
}


def load_monitor(run_name: str) -> List[Dict[str, float]]:
    """加载 monitor.csv 并解析为 dict 列表"""
    path = ROOT / 'runs' / 'eval' / run_name / 'episode-001' / 'monitor.csv'
    if not path.exists():
        print(f'WARNING: {path} not found')
        return []

    rows = []
    with open(path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            parsed = {}
            for k, v in row.items():
                if v == '' or v is None:
                    parsed[k] = None
                else:
                    try:
                        parsed[k] = float(v)
                    except ValueError:
                        parsed[k] = v
            rows.append(parsed)
    return rows


def extract_metrics(label: str, rows: List[Dict]) -> Dict[str, Any]:
    """从逐时数据中计算真实指标"""
    if not rows:
        return {'label': label, 'error': 'no data'}

    n = len(rows)

    # 基本时序数据提取
    elec_facility = np.array([r.get('Electricity:Facility', 0) or 0 for r in rows])
    ite_elec = np.array([r.get('ITE-CPU:InteriorEquipment:Electricity', 0) or 0 for r in rows])
    water = np.array([r.get('Water:Facility', 0) or 0 for r in rows])
    air_temp = np.array([r.get('air_temperature', 0) or 0 for r in rows])
    outdoor_temp = np.array([r.get('outdoor_temperature', 0) or 0 for r in rows])
    air_humidity = np.array([r.get('air_humidity', 0) or 0 for r in rows])
    ct_temp = np.array([r.get('CT_temperature', 0) or 0 for r in rows])
    cw_temp = np.array([r.get('CW_temperature', 0) or 0 for r in rows])
    crah_out = np.array([r.get('CRAH_temperature_1', 0) or 0 for r in rows])
    crah_in = np.array([r.get('CRAH_temperature_2', 0) or 0 for r in rows])
    fan_flow = np.array([r.get('act_Fan', 0) or 0 for r in rows])
    chiller_t = np.array([r.get('act_Chiller_T', 0) or 0 for r in rows])
    chiller_pump = np.array([r.get('act_Chiller_Pump', 0) or 0 for r in rows])
    ct_pump = np.array([r.get('act_CT_Pump', 0) or 0 for r in rows])
    ite_rate = np.array([r.get('act_ITE', 0) or 0 for r in rows])
    rewards = np.array([r.get('reward', 0) or 0 for r in rows])
    energy_terms = np.array([r.get('energy_term', 0) or 0 for r in rows])
    comfort_terms = np.array([r.get('comfort_term', 0) or 0 for r in rows])
    months = np.array([r.get('month', 0) or 0 for r in rows])

    # ===== PUE 计算 =====
    # EnergyPlus 的 Electricity:Facility 和 ITE-CPU 输出是 Joules (能量，不是功率)
    # 对于 timesteps_per_hour=1，每步 = 1小时 = 3600秒
    # PUE = 总电力设施能耗 / IT 设备能耗

    # 过滤掉 ITE=0 的时步（避免除零）
    valid_mask = ite_elec > 0
    if valid_mask.sum() > 0:
        pue_hourly = np.where(valid_mask, elec_facility / ite_elec, np.nan)
        pue_annual = float(np.nansum(elec_facility[valid_mask]) / np.nansum(ite_elec[valid_mask]))
        pue_hourly_valid = pue_hourly[valid_mask]
        pue_mean = float(np.nanmean(pue_hourly_valid))
        pue_min = float(np.nanmin(pue_hourly_valid))
        pue_max = float(np.nanmax(pue_hourly_valid))
        pue_std = float(np.nanstd(pue_hourly_valid))
    else:
        pue_annual = pue_mean = pue_min = pue_max = pue_std = 0

    # ===== 能耗转换为 kWh =====
    # EnergyPlus 输出 Joules，转 kWh: / 3.6e6
    total_elec_kwh = float(np.sum(elec_facility)) / 3.6e6
    total_ite_kwh = float(np.sum(ite_elec)) / 3.6e6
    cooling_kwh = total_elec_kwh - total_ite_kwh
    total_water_m3 = float(np.sum(water))  # Water:Facility 单位通常是 m3

    # ===== 功率 (kW) =====
    # 每步 1 小时，能量(J) / 3600(s) = 功率(W)，再 /1000 = kW
    power_facility_kw = elec_facility / 3.6e6  # J/step → kWh/step = kW (因为 step=1h)
    power_ite_kw = ite_elec / 3.6e6

    # ===== 温度指标 =====
    comfort_min = 18.0
    comfort_max = 27.0
    temp_violations = np.sum((air_temp < comfort_min) | (air_temp > comfort_max))
    comfort_violation_pct = float(temp_violations / n * 100)

    # ===== 月度分解 =====
    monthly = {}
    for m in range(1, 13):
        mask = months == m
        if mask.sum() > 0:
            m_elec = float(np.sum(elec_facility[mask])) / 3.6e6
            m_ite = float(np.sum(ite_elec[mask])) / 3.6e6
            m_pue = m_elec / m_ite if m_ite > 0 else 0
            m_temp = float(np.mean(air_temp[mask]))
            m_outdoor = float(np.mean(outdoor_temp[mask]))
            monthly[int(m)] = {
                'elec_kwh': round(m_elec, 1),
                'ite_kwh': round(m_ite, 1),
                'cooling_kwh': round(m_elec - m_ite, 1),
                'pue': round(m_pue, 4),
                'indoor_temp_mean': round(m_temp, 2),
                'outdoor_temp_mean': round(m_outdoor, 2),
            }

    result = {
        'label': label,
        'timesteps': n,
        # PUE
        'pue_annual': round(pue_annual, 4),
        'pue_mean': round(pue_mean, 4),
        'pue_min': round(pue_min, 4),
        'pue_max': round(pue_max, 4),
        'pue_std': round(pue_std, 4),
        # 能耗 (kWh)
        'total_elec_kwh': round(total_elec_kwh, 1),
        'total_ite_kwh': round(total_ite_kwh, 1),
        'total_cooling_kwh': round(cooling_kwh, 1),
        'total_water_m3': round(total_water_m3, 2),
        # 功率 (kW)
        'peak_power_kw': round(float(np.max(power_facility_kw)), 1),
        'mean_power_kw': round(float(np.mean(power_facility_kw)), 1),
        'peak_ite_kw': round(float(np.max(power_ite_kw)), 1),
        'mean_ite_kw': round(float(np.mean(power_ite_kw)), 1),
        # 温度 (°C)
        'indoor_temp_mean': round(float(np.mean(air_temp)), 2),
        'indoor_temp_max': round(float(np.max(air_temp)), 2),
        'indoor_temp_min': round(float(np.min(air_temp)), 2),
        'indoor_temp_std': round(float(np.std(air_temp)), 2),
        'outdoor_temp_mean': round(float(np.mean(outdoor_temp)), 2),
        'outdoor_temp_max': round(float(np.max(outdoor_temp)), 2),
        'outdoor_temp_min': round(float(np.min(outdoor_temp)), 2),
        # 湿度
        'indoor_humidity_mean': round(float(np.mean(air_humidity)), 2),
        # HVAC 运行状态
        'fan_flow_mean': round(float(np.mean(fan_flow)), 1),
        'chiller_t_mean': round(float(np.mean(chiller_t)), 2),
        'ct_pump_mean': round(float(np.mean(ct_pump)), 1),
        'crah_supply_temp_mean': round(float(np.mean(crah_out)), 2),
        'crah_return_temp_mean': round(float(np.mean(crah_in)), 2),
        'crah_delta_t_mean': round(float(np.mean(crah_in - crah_out)), 2),
        # Comfort
        'comfort_violation_pct': round(comfort_violation_pct, 2),
        'comfort_range': [comfort_min, comfort_max],
        # Reward
        'total_reward': round(float(np.sum(rewards)), 2),
        'mean_reward': round(float(np.mean(rewards)), 6),
        # 月度分解
        'monthly': monthly,
    }

    return result


def save_hourly_csv(label: str, rows: List[Dict], output_path: Path):
    """保存逐时真实值 CSV"""
    headers = [
        'hour', 'month', 'outdoor_temp_C', 'indoor_temp_C', 'humidity_pct',
        'power_facility_kW', 'power_ite_kW', 'power_cooling_kW', 'pue',
        'fan_flow_kgs', 'chiller_t_C', 'crah_supply_C', 'crah_return_C',
        'ct_pump_kgs', 'ite_utilization', 'reward',
    ]

    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        for i, r in enumerate(rows):
            elec = (r.get('Electricity:Facility', 0) or 0) / 3.6e6
            ite = (r.get('ITE-CPU:InteriorEquipment:Electricity', 0) or 0) / 3.6e6
            pue = elec / ite if ite > 0 else 0
            writer.writerow([
                i + 1,
                r.get('month', 0),
                round(r.get('outdoor_temperature', 0) or 0, 2),
                round(r.get('air_temperature', 0) or 0, 2),
                round(r.get('air_humidity', 0) or 0, 2),
                round(elec, 2),
                round(ite, 2),
                round(elec - ite, 2),
                round(pue, 4),
                round(r.get('act_Fan', 0) or 0, 1),
                round(r.get('act_Chiller_T', 0) or 0, 2),
                round(r.get('CRAH_temperature_1', 0) or 0, 2),
                round(r.get('CRAH_temperature_2', 0) or 0, 2),
                round(r.get('act_CT_Pump', 0) or 0, 1),
                round(r.get('act_ITE', 0) or 0, 4),
                round(r.get('reward', 0) or 0, 4),
            ])


def main():
    results_dir = ROOT / 'results'
    results_dir.mkdir(exist_ok=True)

    all_metrics = {}

    for label, run_name in EVAL_RUNS.items():
        print(f'Processing {label} ({run_name})...')
        rows = load_monitor(run_name)
        if not rows:
            continue
        metrics = extract_metrics(label, rows)
        all_metrics[label] = metrics

        # Save hourly CSV for best seeds
        if label in ('seed02-best', 'seed03-latest'):
            csv_path = results_dir / f'e0_hourly_{label.replace("-", "_")}.csv'
            save_hourly_csv(label, rows, csv_path)
            print(f'  Saved hourly CSV: {csv_path.name}')

    # Print comparison table
    print(f'\n{"=" * 100}')
    print(f'  E0 南京基线 - 真实物理指标对比')
    print(f'{"=" * 100}')
    print(f'\n{"Label":<18} {"PUE":>6} {"电力MWh":>9} {"IT MWh":>9} {"冷却MWh":>9} '
          f'{"室温°C":>8} {"室温Max":>8} {"Comfort%":>9} {"Reward":>10}')
    print('-' * 100)

    for label, m in all_metrics.items():
        if 'error' in m:
            continue
        print(f'{label:<18} {m["pue_annual"]:>6.3f} {m["total_elec_kwh"]/1000:>9.1f} '
              f'{m["total_ite_kwh"]/1000:>9.1f} {m["total_cooling_kwh"]/1000:>9.1f} '
              f'{m["indoor_temp_mean"]:>8.2f} {m["indoor_temp_max"]:>8.2f} '
              f'{m["comfort_violation_pct"]:>9.2f} {m["total_reward"]:>10.1f}')

    # Monthly PUE for best model
    print(f'\n{"=" * 100}')
    print(f'  月度 PUE (seed03-latest)')
    print('-' * 60)
    if 'seed03-latest' in all_metrics:
        m = all_metrics['seed03-latest']
        print(f'{"月份":<6} {"PUE":>6} {"电力kWh":>10} {"冷却kWh":>10} {"室外°C":>8} {"室内°C":>8}')
        for month in range(1, 13):
            if month in m['monthly']:
                md = m['monthly'][month]
                print(f'{month:<6} {md["pue"]:>6.3f} {md["elec_kwh"]:>10.0f} '
                      f'{md["cooling_kwh"]:>10.0f} {md["outdoor_temp_mean"]:>8.1f} {md["indoor_temp_mean"]:>8.1f}')

    # Save
    output_path = results_dir / 'e0_real_metrics.json'
    output_path.write_text(json.dumps(all_metrics, indent=2, ensure_ascii=False), encoding='utf-8')
    print(f'\nSaved: {output_path}')


if __name__ == '__main__':
    main()
