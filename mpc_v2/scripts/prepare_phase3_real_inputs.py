"""Prepare real EPW/EnergyPlus/PVGIS inputs for Phase 3 sizing runs."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.request import urlopen

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[2]
EPLUS_ROOT = REPO_ROOT / "Nanjing-DataCenter-TES-EnergyPlus"
PVGIS_API = "https://re.jrc.ec.europa.eu/api/v5_3/seriescalc"


@dataclass(frozen=True)
class Phase3LocationInput:
    location_id: str
    label: str
    latitude: float
    longitude: float
    utc_offset_hours: int
    epw_path: Path
    baseline_timeseries: Path
    baseline_timestamp_col: str
    role: str
    pue_offset: float = 0.0


LOCATIONS = (
    Phase3LocationInput(
        location_id="nanjing",
        label="Nanjing",
        latitude=31.93160,
        longitude=118.8996,
        utc_offset_hours=8,
        epw_path=EPLUS_ROOT / "weather" / "CHN_JS_Nanjing.582380_TMYx.2009-2023.epw",
        baseline_timeseries=EPLUS_ROOT / "out" / "energyplus_nanjing" / "timeseries_15min.csv",
        baseline_timestamp_col="interval_start",
        role="baseline_east_china",
        pue_offset=0.0,
    ),
    Phase3LocationInput(
        location_id="guangzhou",
        label="Guangzhou",
        latitude=23.20990,
        longitude=113.4822,
        utc_offset_hours=8,
        epw_path=EPLUS_ROOT / "weather" / "CHN_GD_Guangzhou.592870_TMYx.2009-2023.epw",
        baseline_timeseries=REPO_ROOT
        / "results"
        / "multicity_tempfix_guangzhou_no_control_20260513"
        / "no_control"
        / "observation.csv",
        baseline_timestamp_col="timestamp",
        role="hot_humid_south_china",
        pue_offset=0.015,
    ),
    Phase3LocationInput(
        location_id="beijing",
        label="Beijing",
        latitude=40.08000,
        longitude=116.5850,
        utc_offset_hours=8,
        epw_path=EPLUS_ROOT / "weather" / "CHN_BJ_Beijing-Capital.Intl.AP.545110_TMYx.2009-2023.epw",
        baseline_timeseries=REPO_ROOT
        / "results"
        / "multicity_tempfix_beijing_no_control_20260513"
        / "no_control"
        / "observation.csv",
        baseline_timestamp_col="timestamp",
        role="north_china_policy_relevance",
        pue_offset=-0.005,
    ),
)


def prepare_phase3_real_inputs(
    output_locations_root: str | Path = REPO_ROOT / "data" / "locations",
    pvgis_root: str | Path = EPLUS_ROOT / "inputs" / "pvgis",
    target_year: int = 2025,
    pvgis_year: int = 2019,
    peak_power_kw: float = 20000.0,
    system_loss_pct: float = 14.0,
    force_download: bool = False,
) -> Path:
    """Create Phase 3 location CSVs and a data-source manifest."""

    output_locations_root = Path(output_locations_root)
    pvgis_root = Path(pvgis_root)
    raw_dir = pvgis_root / "raw"
    processed_dir = pvgis_root / "processed"
    raw_dir.mkdir(parents=True, exist_ok=True)
    processed_dir.mkdir(parents=True, exist_ok=True)
    output_locations_root.mkdir(parents=True, exist_ok=True)

    manifest_rows: list[dict[str, Any]] = []
    locations_yaml_rows: list[dict[str, Any]] = []
    for location in LOCATIONS:
        for required in (location.epw_path, location.baseline_timeseries):
            if not required.exists():
                raise FileNotFoundError(required)

        location_dir = output_locations_root / location.location_id
        location_dir.mkdir(parents=True, exist_ok=True)
        weather_path = location_dir / "weather_energyplus_2025.csv"
        load_path = location_dir / "load_energyplus_2025.csv"
        pv_path = processed_dir / f"CHN_{location.label}_PVGIS_20MWp_2025_local.csv"
        raw_json_path = raw_dir / f"CHN_{location.label}_PVGIS_20MWp_{pvgis_year}_raw.json"

        baseline = _load_energyplus_baseline(location)
        weather = _weather_from_baseline(baseline)
        load = _load_from_baseline(baseline)
        weather.to_csv(weather_path, index=False)
        load.to_csv(load_path, index=False)

        url = _pvgis_url(location, pvgis_year, peak_power_kw, system_loss_pct)
        if force_download or not raw_json_path.exists():
            _download(url, raw_json_path)
        pv_frame, pv_meta = _standardize_pvgis(
            raw_json_path,
            utc_offset_hours=location.utc_offset_hours,
            target_year=target_year,
        )
        pv_frame.to_csv(pv_path, index=False)

        locations_yaml_rows.append(
            {
                "id": location.location_id,
                "label": location.label,
                "role": location.role,
                "weather_profile": _rel(weather_path),
                "load_profile": _rel(load_path),
                "pv_profile_20mwp": _rel(pv_path),
                "price_profile": "Nanjing-DataCenter-TES-EnergyPlus/inputs/Jiangsu_TOU_2025_hourly.csv",
                "epw_path": _rel(location.epw_path),
                "energyplus_baseline_timeseries": _rel(location.baseline_timeseries),
                "pue_offset": float(location.pue_offset),
                "data_boundary": "EnergyPlus no-control annual boundary + PVGIS 20 MWp PV + Jiangsu TOU price",
            }
        )
        manifest_rows.append(
            {
                "location_id": location.location_id,
                "label": location.label,
                "latitude": location.latitude,
                "longitude": location.longitude,
                "utc_offset_hours": location.utc_offset_hours,
                "epw_path": _rel(location.epw_path),
                "energyplus_baseline_timeseries": _rel(location.baseline_timeseries),
                "weather_profile": _rel(weather_path),
                "load_profile": _rel(load_path),
                "pvgis_raw_json": _rel(raw_json_path),
                "pv_profile_20mwp": _rel(pv_path),
                "pvgis_url": url,
                "pvgis_radiation_db": pv_meta.get("radiation_db", ""),
                "pvgis_meteo_db": pv_meta.get("meteo_db", ""),
                "pvgis_peak_power_kw": peak_power_kw,
                "pvgis_system_loss_pct": system_loss_pct,
                "pvgis_slope_deg": pv_meta.get("slope", ""),
                "pvgis_azimuth_deg": pv_meta.get("azimuth", ""),
                "rows_15min_load_weather": len(load),
                "rows_hourly_pv": len(pv_frame),
            }
        )

    manifest = pd.DataFrame(manifest_rows)
    manifest_path = pvgis_root / "phase3_real_input_manifest.csv"
    manifest.to_csv(manifest_path, index=False)
    _write_locations_yaml(REPO_ROOT / "mpc_v2" / "config" / "phase3_locations.yaml", locations_yaml_rows)
    _write_source_note(pvgis_root / "phase3_real_input_sources.md", manifest, pvgis_year, target_year)
    return manifest_path


def _load_energyplus_baseline(location: Phase3LocationInput) -> pd.DataFrame:
    frame = pd.read_csv(location.baseline_timeseries)
    if location.baseline_timestamp_col not in frame.columns:
        raise ValueError(f"{location.baseline_timeseries} missing {location.baseline_timestamp_col}")
    frame = frame.copy()
    frame["timestamp"] = _rewrite_to_year(pd.to_datetime(frame[location.baseline_timestamp_col]), 2025)
    rename = {
        "zone_air_temp_c": "zone_temp_c",
        "ite_electricity_kw": "it_load_kw",
    }
    frame = frame.rename(columns=rename)
    return frame


def _weather_from_baseline(frame: pd.DataFrame) -> pd.DataFrame:
    required = ["timestamp", "outdoor_drybulb_c", "outdoor_wetbulb_c"]
    _require_columns(frame, required)
    out = pd.DataFrame(
        {
            "timestamp": frame["timestamp"],
            "outdoor_temp_c": pd.to_numeric(frame["outdoor_drybulb_c"], errors="raise"),
            "outdoor_wetbulb_c": pd.to_numeric(frame["outdoor_wetbulb_c"], errors="raise"),
        }
    )
    if "zone_temp_c" in frame:
        out["zone_temp_c"] = pd.to_numeric(frame["zone_temp_c"], errors="raise")
    return out


def _load_from_baseline(frame: pd.DataFrame) -> pd.DataFrame:
    _require_columns(frame, ["timestamp", "facility_electricity_kw", "chiller_electricity_kw", "chiller_cooling_kw"])
    facility = pd.to_numeric(frame["facility_electricity_kw"], errors="raise")
    chiller = pd.to_numeric(frame["chiller_electricity_kw"], errors="raise")
    if "it_load_kw" in frame:
        it_load = pd.to_numeric(frame["it_load_kw"], errors="coerce").fillna((facility - chiller).clip(lower=0.0))
    else:
        it_load = (facility - chiller).clip(lower=0.0)
    return pd.DataFrame(
        {
            "timestamp": frame["timestamp"],
            "it_load_kw": it_load.clip(lower=0.0),
            "base_facility_kw": facility.clip(lower=0.0),
            "chiller_cooling_kw": pd.to_numeric(frame["chiller_cooling_kw"], errors="raise").clip(lower=0.0),
            "chiller_electricity_kw": chiller.clip(lower=0.0),
        }
    )


def _standardize_pvgis(path: Path, utc_offset_hours: int, target_year: int) -> tuple[pd.DataFrame, dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    hourly = data["outputs"]["hourly"]
    timestamps = []
    power_kw = []
    for row in hourly:
        utc_center = pd.to_datetime(row["time"], format="%Y%m%d:%H%M")
        local_start = utc_center + timedelta(hours=utc_offset_hours) - timedelta(minutes=30)
        if local_start.month == 2 and local_start.day == 29:
            continue
        timestamps.append(local_start.replace(year=target_year))
        power_kw.append(max(0.0, float(row["P"]) / 1000.0))
    frame = pd.DataFrame({"timestamp": timestamps, "power_kw": power_kw})
    frame = frame.sort_values("timestamp").groupby("timestamp", as_index=False).mean()
    expected = pd.date_range(f"{target_year}-01-01 00:00:00", f"{target_year}-12-31 23:00:00", freq="h")
    frame = frame.set_index("timestamp").reindex(expected).sort_index()
    frame["power_kw"] = frame["power_kw"].fillna(0.0).clip(lower=0.0)
    frame.index.name = "timestamp"
    frame = frame.reset_index()
    meta = _pvgis_meta(data)
    return frame, meta


def _pvgis_meta(data: dict[str, Any]) -> dict[str, Any]:
    inputs = data.get("inputs", {})
    meteo = inputs.get("meteo_data", {})
    fixed = inputs.get("mounting_system", {}).get("fixed", {})
    slope = fixed.get("slope", {})
    azimuth = fixed.get("azimuth", {})
    return {
        "radiation_db": meteo.get("radiation_db", ""),
        "meteo_db": meteo.get("meteo_db", ""),
        "slope": slope.get("value", ""),
        "azimuth": azimuth.get("value", ""),
    }


def _pvgis_url(
    location: Phase3LocationInput,
    pvgis_year: int,
    peak_power_kw: float,
    system_loss_pct: float,
) -> str:
    params = {
        "lat": f"{location.latitude:.5f}",
        "lon": f"{location.longitude:.5f}",
        "startyear": int(pvgis_year),
        "endyear": int(pvgis_year),
        "pvcalculation": 1,
        "peakpower": f"{peak_power_kw:g}",
        "loss": f"{system_loss_pct:g}",
        "optimalangles": 1,
        "outputformat": "json",
    }
    return f"{PVGIS_API}?{urlencode(params)}"


def _download(url: str, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with urlopen(url, timeout=120) as response:
        payload = response.read()
    path.write_bytes(payload)


def _rewrite_to_year(timestamps: pd.Series | pd.DatetimeIndex, year: int) -> pd.Series:
    out = []
    for ts in pd.to_datetime(timestamps):
        if ts.month == 2 and ts.day == 29:
            continue
        out.append(pd.Timestamp(year=year, month=ts.month, day=ts.day, hour=ts.hour, minute=ts.minute, second=ts.second))
    return pd.Series(out)


def _write_locations_yaml(path: Path, rows: list[dict[str, Any]]) -> None:
    lines = ["locations:"]
    for row in rows:
        lines.append(f"  - id: {row['id']}")
        for key, value in row.items():
            if key == "id":
                continue
            if isinstance(value, float):
                lines.append(f"    {key}: {value:.6g}")
            else:
                lines.append(f"    {key}: {value}")
        lines.append("")
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _write_source_note(path: Path, manifest: pd.DataFrame, pvgis_year: int, target_year: int) -> None:
    lines = [
        "# Phase 3 Real Input Sources",
        "",
        f"Generated target year: {target_year}.",
        f"PVGIS source year: {pvgis_year}; timestamps are converted from UTC hourly centers to China local interval starts.",
        "",
        "PVGIS API endpoint: https://re.jrc.ec.europa.eu/api/v5_3/seriescalc",
        "",
        "| location | EPW | EnergyPlus baseline | PVGIS processed CSV | PVGIS radiation DB | slope | azimuth |",
        "|---|---|---|---|---|---:|---:|",
    ]
    for _, row in manifest.iterrows():
        lines.append(
            f"| {row['location_id']} | `{row['epw_path']}` | `{row['energyplus_baseline_timeseries']}` | "
            f"`{row['pv_profile_20mwp']}` | {row['pvgis_radiation_db']} | {row['pvgis_slope_deg']} | {row['pvgis_azimuth_deg']} |"
        )
    lines.extend(
        [
            "",
            "All Phase 3 matrix cases use the Jiangsu TOU 2025 hourly price curve:",
            "",
            "`Nanjing-DataCenter-TES-EnergyPlus/inputs/Jiangsu_TOU_2025_hourly.csv`",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def _require_columns(frame: pd.DataFrame, columns: list[str]) -> None:
    missing = [col for col in columns if col not in frame.columns]
    if missing:
        raise ValueError(f"missing columns: {missing}")


def _rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return str(path)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target-year", type=int, default=2025)
    parser.add_argument("--pvgis-year", type=int, default=2019)
    parser.add_argument("--force-download", action="store_true")
    args = parser.parse_args()
    print(
        prepare_phase3_real_inputs(
            target_year=args.target_year,
            pvgis_year=args.pvgis_year,
            force_download=args.force_download,
        )
    )


if __name__ == "__main__":
    main()
