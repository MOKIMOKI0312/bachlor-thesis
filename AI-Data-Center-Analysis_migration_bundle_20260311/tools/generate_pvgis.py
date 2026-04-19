"""Generate hourly PV output time series via PVGIS for M2 training.

Singapore Changi site, 6 MWp crystalline-Si, free-standing array.
Output: Data/pv/SGP_PV_6MWp_hourly.csv (8760 rows, Asia/Singapore timezone).
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
import pvlib

# ---- Site & system config (M3 can override for Huaibei via CLI) -------------
CONFIG = dict(
    latitude=1.35,             # Singapore Changi
    longitude=103.82,
    peakpower_kw=6000,         # 6 MWp
    pv_tech="crystSi",
    mounting="free",
    loss_pct=14,               # PVGIS default system loss
    surface_tilt=10,           # Low tilt near equator
    surface_azimuth=180,       # pvlib convention: 180 = due south
    source_year=2020,          # Most recent PVGIS-SARAH2 coverage year
    target_year=2023,          # Align with USEP/EPW TMY
    tz="Asia/Singapore",
)


def fetch_pvgis(cfg: dict) -> pd.DataFrame:
    data, _ = pvlib.iotools.get_pvgis_hourly(
        latitude=cfg["latitude"],
        longitude=cfg["longitude"],
        start=cfg["source_year"],
        end=cfg["source_year"],
        components=False,
        surface_tilt=cfg["surface_tilt"],
        surface_azimuth=cfg["surface_azimuth"],
        pvcalculation=True,
        peakpower=cfg["peakpower_kw"],
        pvtechchoice=cfg["pv_tech"],
        mountingplace=cfg["mounting"],
        loss=cfg["loss_pct"],
        timeout=60,
    )
    return data


def remap_to_target_year(df: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """Convert UTC index to Asia/Singapore local time, then shift year-labels
    to target_year while preserving month-day-hour alignment.

    Leap-day handling: PVGIS 2020 is a leap year (8784 h). When remapping to
    2023 (non-leap, 8760 h), drop Feb 29.
    """
    local = df.tz_convert(cfg["tz"])

    # Drop leap day if present (Feb 29)
    local = local[~((local.index.month == 2) & (local.index.day == 29))]

    # Re-index to target year with identical month/day/hour/minute
    new_index = pd.DatetimeIndex(
        [ts.replace(year=cfg["target_year"]) for ts in local.index],
        name="time",
    )
    out = local.copy()
    out.index = new_index

    # Snap minute offsets: PVGIS samples at :30 within each hour. Shift to :00.
    out.index = out.index.floor("H")

    return out


def to_output_frame(df: pd.DataFrame) -> pd.DataFrame:
    # P column is in W (per PVGIS pvcalculation=True output)
    power_kw = df["P"] / 1000.0
    out = pd.DataFrame({
        "timestamp": df.index.strftime("%Y-%m-%d %H:%M:%S"),
        "power_kw": power_kw.round(2).values,
    })
    return out


def validate(df: pd.DataFrame, cfg: dict) -> None:
    assert len(df) == 8760, f"Expected 8760 rows, got {len(df)}"
    assert df["power_kw"].min() >= 0, f"Negative power: {df['power_kw'].min()}"
    annual_gwh = df["power_kw"].sum() / 1e6
    assert 6.0 <= annual_gwh <= 10.0, (
        f"Annual generation {annual_gwh:.2f} GWh outside expected range for "
        f"{cfg['peakpower_kw']} kW peak in Singapore"
    )
    # Specific yield check (kWh per kWp)
    yield_per_kwp = df["power_kw"].sum() / cfg["peakpower_kw"]
    assert 1100 <= yield_per_kwp <= 1600, f"Yield {yield_per_kwp:.0f} kWh/kWp outside Singapore norm"
    print(f"  rows: {len(df)}, annual: {annual_gwh:.2f} GWh, yield: {yield_per_kwp:.0f} kWh/kWp")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path,
                        default=Path("Data/pv/SGP_PV_6MWp_hourly.csv"))
    parser.add_argument("--latitude", type=float, default=CONFIG["latitude"])
    parser.add_argument("--longitude", type=float, default=CONFIG["longitude"])
    parser.add_argument("--peakpower-kw", type=float, default=CONFIG["peakpower_kw"])
    parser.add_argument("--target-year", type=int, default=CONFIG["target_year"])
    args = parser.parse_args()

    cfg = dict(CONFIG,
               latitude=args.latitude,
               longitude=args.longitude,
               peakpower_kw=args.peakpower_kw,
               target_year=args.target_year)

    print(f"Fetching PVGIS for ({cfg['latitude']}, {cfg['longitude']}), "
          f"{cfg['peakpower_kw']} kWp, source year {cfg['source_year']}...")
    raw = fetch_pvgis(cfg)
    print(f"  PVGIS returned {len(raw)} rows.")

    remapped = remap_to_target_year(raw, cfg)
    out = to_output_frame(remapped)

    print("Validating...")
    validate(out, cfg)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(args.output, index=False)
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
