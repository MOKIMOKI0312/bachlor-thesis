"""Generate hourly PV output time series via PVGIS for M2 training.

Default site: Palo Alto, California (M2 primary). Singapore Changi preset
preserved for M3 / legacy compatibility.

Output filename is derived from the site preset's `output_stem`.
  palo-alto → Data/pv/CAISO_PaloAlto_PV_6MWp_hourly.csv
  singapore → Data/pv/SGP_PV_6MWp_hourly.csv
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
import pvlib

# ---- Site & system presets --------------------------------------------------
# Shared defaults across sites
SHARED = dict(
    peakpower_kw=6000,         # 6 MWp (技术路线.md §4.2)
    pv_tech="crystSi",
    mounting="free",
    loss_pct=14,               # PVGIS default system loss
    surface_azimuth=180,       # pvlib convention: 180 = due south
    source_year=2020,          # Most recent PVGIS-SARAH2 coverage year
    target_year=2023,          # Align with LMP / EPW TMY
)

SITE_PRESETS = {
    "palo-alto": dict(
        latitude=37.44,
        longitude=-122.14,
        surface_tilt=30,       # NorCal fixed-tilt optimum (~latitude-5)
        tz="America/Los_Angeles",
        output_stem="CAISO_PaloAlto",
        yield_min=1300,        # kWh / kWp; NorCal typical 1500-1900
        yield_max=2100,
    ),
    "singapore": dict(
        latitude=1.35,
        longitude=103.82,
        surface_tilt=10,       # Low tilt near equator
        tz="Asia/Singapore",
        output_stem="SGP",
        yield_min=1100,        # Singapore typical 1100-1600
        yield_max=1600,
    ),
    "nanjing": dict(
        latitude=32.0584,      # Nanjing 32°03′30″N
        longitude=118.7965,    # Nanjing 118°47′47″E
        surface_tilt=27,       # Eastern-China fixed-tilt optimum (~latitude-5)
        tz="Asia/Shanghai",
        output_stem="CHN_Nanjing",
        yield_min=950,         # Nanjing typical 1000-1300; PVGIS sometimes reports lower
        yield_max=1400,
    ),
}

# Legacy CONFIG kept for backward compat with any caller that still imports it.
CONFIG = dict(SHARED, **SITE_PRESETS["palo-alto"])


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
    """Convert UTC index to local wall-clock time (DST-naive), shift year-labels
    to target_year, align to complete 8760 hourly grid.

    Leap-day handling: PVGIS 2020 is a leap year (8784 h). When remapping to
    2023 (non-leap, 8760 h), drop Feb 29.

    DST handling: after tz_convert we drop tz info (tz-naive local wall-clock),
    which sidesteps DST ambiguity for regions like America/Los_Angeles. Any
    fall-back duplicate hour is kept once; spring-forward gap is forward-filled
    from the neighbor hour. This simplification is consistent with the SGP
    version's treatment and standard TMY-in-RL practice (the wrapper aligns
    by ordinal hour, not UTC offset).
    """
    # Step 1: UTC → local wall-clock, then drop tz info
    local = df.tz_convert(cfg["tz"]).tz_localize(None)

    # Step 2: drop source leap day (Feb 29)
    local = local[~((local.index.month == 2) & (local.index.day == 29))]

    # Step 3: relabel year (source 2020 → target 2023)
    local.index = pd.DatetimeIndex(
        [ts.replace(year=cfg["target_year"]) for ts in local.index],
        name="time",
    )

    # Step 4: snap to hour (PVGIS samples at :30 — naive so no DST ambiguity)
    local.index = local.index.floor("h")

    # Step 5: dedupe DST fall-back duplicates (keep first occurrence)
    local = local[~local.index.duplicated(keep="first")]

    # Step 6: reindex to complete 8760 naive target-year grid, ffill/bfill
    #         any DST spring-forward gap
    full_idx = pd.date_range(
        start=f"{cfg['target_year']}-01-01 00:00",
        end=f"{cfg['target_year']}-12-31 23:00",
        freq="h",
    )
    assert len(full_idx) == 8760, f"target-year grid should be 8760h, got {len(full_idx)}"
    local = local.reindex(full_idx).ffill().bfill()
    return local


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
    annual_kwh = df["power_kw"].sum()
    annual_gwh = annual_kwh / 1e6
    yield_per_kwp = annual_kwh / cfg["peakpower_kw"]
    ymin, ymax = cfg["yield_min"], cfg["yield_max"]
    assert ymin <= yield_per_kwp <= ymax, (
        f"Yield {yield_per_kwp:.0f} kWh/kWp outside [{ymin}, {ymax}] "
        f"expected for {cfg['output_stem']}"
    )
    print(f"  rows: {len(df)}, annual: {annual_gwh:.2f} GWh, "
          f"yield: {yield_per_kwp:.0f} kWh/kWp")


def build_cfg(site: str, overrides: dict) -> dict:
    if site not in SITE_PRESETS:
        raise ValueError(f"Unknown site '{site}', must be one of {list(SITE_PRESETS)}")
    cfg = dict(SHARED, **SITE_PRESETS[site])
    for k, v in overrides.items():
        if v is not None:
            cfg[k] = v
    return cfg


def default_output_path(cfg: dict) -> Path:
    stem = cfg["output_stem"]
    kwp = int(cfg["peakpower_kw"] // 1000)
    return Path("Data/pv") / f"{stem}_PV_{kwp}MWp_hourly.csv"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--site", choices=list(SITE_PRESETS), default="palo-alto",
                        help="site preset (default: palo-alto for M2)")
    parser.add_argument("--output", type=Path, default=None,
                        help="override output path (default: auto from site)")
    parser.add_argument("--latitude", type=float, default=None)
    parser.add_argument("--longitude", type=float, default=None)
    parser.add_argument("--peakpower-kw", type=float, default=None)
    parser.add_argument("--target-year", type=int, default=None)
    parser.add_argument("--surface-tilt", type=float, default=None)
    args = parser.parse_args()

    cfg = build_cfg(args.site, dict(
        latitude=args.latitude,
        longitude=args.longitude,
        peakpower_kw=args.peakpower_kw,
        target_year=args.target_year,
        surface_tilt=args.surface_tilt,
    ))
    output = args.output if args.output is not None else default_output_path(cfg)

    print(f"Site: {args.site} "
          f"({cfg['latitude']}, {cfg['longitude']}), "
          f"{cfg['peakpower_kw']} kWp, tilt {cfg['surface_tilt']}°, "
          f"source year {cfg['source_year']} → target {cfg['target_year']}")
    raw = fetch_pvgis(cfg)
    print(f"  PVGIS returned {len(raw)} rows.")

    remapped = remap_to_target_year(raw, cfg)
    out = to_output_frame(remapped)

    print("Validating...")
    validate(out, cfg)

    output.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(output, index=False)
    print(f"Wrote {output}")


if __name__ == "__main__":
    main()
