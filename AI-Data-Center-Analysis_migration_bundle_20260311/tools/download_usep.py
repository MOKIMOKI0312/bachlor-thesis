"""Generate hourly Singapore USEP (Uniform Singapore Energy Price) series for M2.

DATA PROVENANCE & LIMITATION
----------------------------
Singapore EMC (https://www.emcsg.com/marketdata/priceinformation) requires
SAML SSO authentication for bulk half-hourly USEP export, so automated
download is not feasible without credentials. Public APIs (data.gov.sg)
do not expose USEP at sub-monthly granularity.

This script therefore *synthesises* 8760 hourly USEP values from two
authoritative public sources:

1. **Monthly average USEP** (EMA "Average-Monthly-USEP.pdf", 2005-2024 table).
   2023 monthly means hard-coded in MONTHLY_MEAN_2023 below.
2. **Typical Singapore wholesale diurnal profile** (EMC market reports):
   night valley 02:00-06:00, morning shoulder 09:00-12:00, evening peak
   19:00-22:00. Shape multipliers in DIURNAL_PROFILE.

Log-normal noise (sigma=0.22) is applied per hour, then each month is
re-normalised so the hourly series has exactly the EMA published monthly
mean (preserves ground-truth aggregates). Seed is fixed for reproducibility.

If the user later obtains the real EMC half-hourly CSV, replacing this
synthetic series is a one-line edit (load + aggregate to hourly).

Output: Data/prices/SGP_USEP_2023_hourly.csv (8760 rows, Asia/Singapore).
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

# EMA 2023 monthly average USEP in SGD/MWh (source: Average-Monthly-USEP.pdf)
MONTHLY_MEAN_2023 = {
    1: 221.0, 2: 222.0, 3: 339.3, 4: 324.0,  5: 492.1, 6: 305.2,
    7: 167.5, 8: 158.8, 9: 208.6, 10: 221.3, 11: 177.7, 12: 131.4,
}

# Typical Singapore USEP diurnal shape (multiplier on the daily mean).
# Derived from EMC 2023 market reports: single evening peak 19-22, no
# morning peak (because SG has minimal residential heating / cooking surge,
# and commercial HVAC ramp is gradual); night valley 02-06.
DIURNAL_PROFILE = np.array([
    0.78, 0.72, 0.68, 0.68, 0.70, 0.78,  # 00-05 night valley
    0.88, 1.00, 1.08, 1.12, 1.14, 1.10,  # 06-11 morning ramp + shoulder
    1.05, 1.00, 0.98, 1.00, 1.08, 1.18,  # 12-17 midday to pre-peak
    1.28, 1.32, 1.30, 1.22, 1.08, 0.92,  # 18-23 evening peak + tail
])
assert abs(DIURNAL_PROFILE.mean() - 1.0) < 0.01, \
    f"diurnal profile must avg to 1 (got {DIURNAL_PROFILE.mean():.3f})"

NOISE_SIGMA = 0.22   # log-normal sigma; yields ~22% CoV at hourly scale
CLAMP_MIN = 30.0     # SGD/MWh floor (historical USEP low)
CLAMP_MAX = 1500.0   # SGD/MWh ceiling (USEP scarcity cap)
TARGET_YEAR = 2023
TZ = "Asia/Singapore"
RANDOM_SEED = 20260419


def synthesize_hourly_usep(
    monthly_means: dict[int, float],
    diurnal: np.ndarray,
    target_year: int,
    noise_sigma: float,
    seed: int,
) -> pd.DataFrame:
    rng = np.random.default_rng(seed)

    idx = pd.date_range(
        start=f"{target_year}-01-01 00:00",
        end=f"{target_year}-12-31 23:00",
        freq="h",
        tz=TZ,
    )
    assert len(idx) == 8760, f"Expected 8760 hours, got {len(idx)}"

    hours = idx.hour.to_numpy()
    months = idx.month.to_numpy()

    # Base: monthly mean × diurnal shape
    monthly_vec = np.array([monthly_means[m] for m in months])
    shape_vec = diurnal[hours]
    base = monthly_vec * shape_vec

    # Log-normal multiplicative noise (centered so E[noise]=1)
    raw_noise = rng.normal(0, noise_sigma, size=len(idx))
    noise = np.exp(raw_noise - 0.5 * noise_sigma ** 2)

    prices = base * noise
    prices = np.clip(prices, CLAMP_MIN, CLAMP_MAX)

    # Re-normalise per month so monthly means exactly match EMA published
    df = pd.DataFrame({"price_sgd_per_mwh": prices}, index=idx)
    for m, target_mean in monthly_means.items():
        mask = months == m
        current_mean = df.loc[mask, "price_sgd_per_mwh"].mean()
        df.loc[mask, "price_sgd_per_mwh"] *= target_mean / current_mean

    # Re-clamp after renormalisation (rare edge case)
    df["price_sgd_per_mwh"] = df["price_sgd_per_mwh"].clip(CLAMP_MIN, CLAMP_MAX)
    return df


def to_output_frame(df: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame({
        "timestamp": df.index.strftime("%Y-%m-%d %H:%M:%S"),
        "price_sgd_per_mwh": df["price_sgd_per_mwh"].round(2).values,
    })


def validate(df: pd.DataFrame) -> None:
    assert len(df) == 8760, f"Expected 8760 rows, got {len(df)}"
    prices = df["price_sgd_per_mwh"]
    assert prices.min() >= CLAMP_MIN, f"Below floor: {prices.min()}"
    assert prices.max() <= CLAMP_MAX, f"Above ceiling: {prices.max()}"
    annual_mean = prices.mean()
    expected_annual = np.mean(list(MONTHLY_MEAN_2023.values()))
    assert abs(annual_mean - expected_annual) < 2.0, (
        f"Annual mean {annual_mean:.2f} drifted from EMA {expected_annual:.2f}"
    )
    print(f"  rows: {len(df)}, annual mean: {annual_mean:.1f} SGD/MWh, "
          f"min: {prices.min():.1f}, max: {prices.max():.1f}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--output", type=Path,
                        default=Path("Data/prices/SGP_USEP_2023_hourly.csv"))
    parser.add_argument("--seed", type=int, default=RANDOM_SEED)
    parser.add_argument("--noise-sigma", type=float, default=NOISE_SIGMA)
    args = parser.parse_args()

    print(f"Synthesising 2023 hourly USEP (seed={args.seed}, sigma={args.noise_sigma})...")
    raw = synthesize_hourly_usep(
        MONTHLY_MEAN_2023, DIURNAL_PROFILE, TARGET_YEAR,
        args.noise_sigma, args.seed,
    )
    out = to_output_frame(raw)

    print("Validating...")
    validate(out)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(args.output, index=False)
    print(f"Wrote {args.output}")

    # Companion README documenting provenance
    readme = args.output.parent / "README.md"
    readme.write_text(
        "# Singapore USEP hourly series\n\n"
        "`SGP_USEP_2023_hourly.csv` is **synthesised** from:\n\n"
        "1. EMA published monthly USEP averages for 2023 (see "
        "`Average-Monthly-USEP.pdf`).\n"
        "2. Typical Singapore wholesale diurnal profile (night valley 02-06, "
        "evening peak 19-22).\n"
        "3. Log-normal hourly noise (sigma=0.22), monthly-mean preserved.\n\n"
        "EMC's real half-hourly USEP requires SAML SSO authentication and is "
        "not accessible via automated download. If genuine EMC half-hourly "
        "CSVs are later obtained, replace this file with a simple aggregation "
        "to hourly means.\n\n"
        "Produced by `tools/download_usep.py`.\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
