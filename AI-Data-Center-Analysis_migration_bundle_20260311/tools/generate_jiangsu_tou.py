"""
Generate Jiangsu 2025 TOU (Time-of-Use) tariff 8760-hour CSV.

Based on:
  - Jiangsu DRC decree 苏发改价格发 [2025] 426号
  - Effective 2025-06-01
  - 4-tier: 尖峰 (super-peak) / 高峰 (peak) / 平段 (shoulder) / 谷段 (off-peak)
  - 3-season modulation: 夏季迎峰 (Jul-Aug), 冬季迎峰 (Jan/Feb/Dec), 过渡季

Base pricing (CNY/kWh → USD/MWh, FX 1 USD = 7 CNY):
  平段 base:    0.58 CNY/kWh  →   83 USD/MWh
  高峰 (80% up): 1.04 CNY/kWh  →  150 USD/MWh
  尖峰 (+20%):   1.25 CNY/kWh  →  179 USD/MWh
  谷段 (-65%):   0.20 CNY/kWh  →   29 USD/MWh

Seasonal modulation applied to peak/super-peak only:
  Summer (Jul-Aug): super-peak 200, peak 165
  Winter (Jan/Feb/Dec): super-peak 190, peak 158
  Shoulder (Mar-Jun, Sep-Nov): super-peak 180, peak 150 (base)

Time slots (24h, weekday/weekend uniform for simplicity):
  谷段 off-peak:      00-08, 12-13
  平段 shoulder:      11-12, 13-17, 22-24
  高峰 peak:          08-11, 17-19, 21-22
  尖峰 super-peak:    19-21

Output schema: timestamp, price_usd_per_mwh  (8760 rows)
Output path: Data/prices/Jiangsu_TOU_2025_hourly.csv
"""

import csv
import pathlib
from datetime import datetime, timedelta

# ---- Price tiers (USD/MWh) ----
BASE = {
    "offpeak": 29,
    "shoulder": 83,
    "peak": 150,
    "superpeak": 180,
}

SEASONAL_ADJUST = {
    # (month set) -> override for peak / superpeak
    "summer":   {"peak": 165, "superpeak": 200},
    "winter":   {"peak": 158, "superpeak": 190},
    "shoulder": {"peak": 150, "superpeak": 180},
}


def get_season(month: int) -> str:
    if month in (7, 8):
        return "summer"
    if month in (1, 2, 12):
        return "winter"
    return "shoulder"


def get_slot(hour: int) -> str:
    """Return time-slot tag for a given 0-23 hour."""
    if 19 <= hour < 21:
        return "superpeak"
    if (8 <= hour < 11) or (17 <= hour < 19) or (21 <= hour < 22):
        return "peak"
    if (11 <= hour < 12) or (13 <= hour < 17) or (22 <= hour < 24):
        return "shoulder"
    # 0-8 and 12-13 → offpeak
    return "offpeak"


def price_at(year: int, month: int, day: int, hour: int) -> int:
    slot = get_slot(hour)
    season = get_season(month)
    adj = SEASONAL_ADJUST[season]
    if slot == "peak":
        return adj["peak"]
    if slot == "superpeak":
        return adj["superpeak"]
    # offpeak / shoulder not seasonally adjusted
    return BASE[slot]


def main() -> None:
    repo_root = pathlib.Path(__file__).resolve().parent.parent
    out_path = repo_root / "Data" / "prices" / "Jiangsu_TOU_2025_hourly.csv"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    start = datetime(2025, 1, 1, 0, 0, 0)
    rows = []
    for h in range(8760):
        ts = start + timedelta(hours=h)
        price = price_at(ts.year, ts.month, ts.day, ts.hour)
        rows.append((ts.strftime("%Y-%m-%d %H:%M:%S"), price))

    with out_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["timestamp", "price_usd_per_mwh"])
        w.writerows(rows)

    # ---- Assertions & stats ----
    prices = [r[1] for r in rows]
    n = len(prices)
    assert n == 8760, f"expected 8760 rows, got {n}"

    from statistics import median, mean, pstdev
    p_min = min(prices)
    p_max = max(prices)
    p_med = median(prices)
    p_mean = mean(prices)
    p_std = pstdev(prices)
    # kurtosis (excess)
    if p_std > 0:
        m4 = sum((p - p_mean) ** 4 for p in prices) / n
        kurtosis_excess = m4 / (p_std ** 4) - 3.0
    else:
        kurtosis_excess = 0.0

    # spot-check known samples
    # 2025-07-15 18:00 → Jul summer, 17-19 peak → 165
    # 2025-03-15 03:00 → shoulder, 0-8 offpeak → 29
    # 2025-01-15 20:00 → winter, 19-21 superpeak → 190
    idx_0715_18 = int((datetime(2025, 7, 15, 18) - start).total_seconds() // 3600)
    idx_0315_03 = int((datetime(2025, 3, 15, 3) - start).total_seconds() // 3600)
    idx_0115_20 = int((datetime(2025, 1, 15, 20) - start).total_seconds() // 3600)
    assert prices[idx_0715_18] == 165, f"summer peak check failed: {prices[idx_0715_18]}"
    assert prices[idx_0315_03] == 29, f"shoulder offpeak check failed: {prices[idx_0315_03]}"
    assert prices[idx_0115_20] == 190, f"winter superpeak check failed: {prices[idx_0115_20]}"

    # distinct count
    distinct = sorted(set(prices))

    print(f"[OK] Wrote {n} hourly rows to {out_path}")
    print(f"     min={p_min}  max={p_max}  median={p_med:.1f}  mean={p_mean:.2f}  std={p_std:.2f}")
    print(f"     kurtosis(excess)={kurtosis_excess:.3f}  (CAISO ≈ 120, target ≈ 2)")
    print(f"     distinct prices: {distinct}")
    print(f"     spot-checks: 2025-07-15 18:00={prices[idx_0715_18]}  "
          f"2025-03-15 03:00={prices[idx_0315_03]}  "
          f"2025-01-15 20:00={prices[idx_0115_20]}")

    # kurtosis gate: TOU 4-tier should be very leptokurtic-free (< 10 excess)
    # With our distribution it's likely negative (bimodal-ish) which is great for RL
    assert abs(kurtosis_excess) < 10, f"kurtosis out of expected range: {kurtosis_excess}"
    assert 70 <= p_med <= 100, f"median should be near 83: got {p_med}"


if __name__ == "__main__":
    main()
