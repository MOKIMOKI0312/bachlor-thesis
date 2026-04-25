"""Download CAISO NP15 Gen Hub day-ahead hourly LMP for 2023.

DATA PROVENANCE
---------------
CAISO（California Independent System Operator）通过 OASIS（Open Access
Same-time Information System）公开发布 2009 年至今全部 LMP 数据，无需
账号 / API key。本脚本用 gridstatus Python 包（MIT 许可，封装 OASIS
API）下载 2023 全年 NP15 Gen Trading Hub（节点代码 TH_NP15_GEN-APND）
的 day-ahead hourly 结算价格。

NP15（North of Path 15）是 CAISO 三个 zonal hub 之一，覆盖 Northern
California 含硅谷（Palo Alto / Mountain View / Sunnyvale）的数据中心
集群。Day-ahead hourly 市场是 RL 环境 timestep 对齐的自然选择。

OUTPUT SCHEMA
-------------
Data/prices/CAISO_NP15_2023_hourly.csv
    timestamp: America/Los_Angeles 本地时间, "YYYY-MM-DD HH:MM:SS"
    price_usd_per_mwh: LMP, rounded to 2 decimals

与 Data/prices/SGP_USEP_2023_hourly.csv 保持平行 schema（timestamp +
price_XXX_per_mwh），下游 PriceSignalWrapper 只需读一个新的列名即可
切换数据源。

REFERENCES
----------
- gridstatus: https://github.com/gridstatus/gridstatus
- CAISO OASIS: http://oasis.caiso.com
- 决策文档: 项目目标/决策-站点切换-CAISO-2026-04-19.md
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

import gridstatus

# ---- Config -----------------------------------------------------------------
NODE = "TH_NP15_GEN-APND"
TARGET_YEAR = 2023
TZ = "America/Los_Angeles"
DEFAULT_OUTPUT = Path("Data/prices/CAISO_NP15_2023_hourly.csv")

# Expected sanity ranges for 2023 NP15 DAM LMP
EXPECT_ANNUAL_MEAN_MIN = 20.0     # USD/MWh floor (2023 NP15 annual mean ~50-70)
EXPECT_ANNUAL_MEAN_MAX = 120.0    # ceiling
EXPECT_MIN_FLOOR = -150.0         # negative prices allowed (midday PV glut) but not below
EXPECT_MAX_CAP = 2500.0           # CAISO scarcity cap


def fetch_year_chunked(year: int, node: str) -> pd.DataFrame:
    """Fetch DAM hourly LMP month-by-month to avoid OASIS single-query limits.

    CAISO OASIS rejects queries spanning > 31 days for LMP data. We batch by
    calendar month, then concatenate.
    """
    iso = gridstatus.CAISO()
    frames = []
    for month in range(1, 13):
        start = pd.Timestamp(year=year, month=month, day=1, tz=TZ)
        if month == 12:
            end = pd.Timestamp(year=year + 1, month=1, day=1, tz=TZ)
        else:
            end = pd.Timestamp(year=year, month=month + 1, day=1, tz=TZ)

        print(f"  fetching {start.date()} → {end.date()} ...", flush=True)
        df_m = iso.get_lmp(
            start=start,
            end=end,
            market="DAY_AHEAD_HOURLY",
            locations=[node],
        )
        frames.append(df_m)

    df = pd.concat(frames, ignore_index=True)
    return df


def normalize(df: pd.DataFrame, node: str) -> pd.DataFrame:
    """Select the node, convert to local TZ, dedupe, sort by time."""
    # gridstatus column schema (as of 0.29.x): Time (UTC), Market, Location, LMP,
    # Energy, Congestion, Loss. We only need Time + LMP.
    loc_col = "Location" if "Location" in df.columns else "location"
    time_col = "Time" if "Time" in df.columns else "time"
    lmp_col = "LMP" if "LMP" in df.columns else "lmp"

    df = df[df[loc_col] == node].copy()
    df[time_col] = pd.to_datetime(df[time_col], utc=True).dt.tz_convert(TZ)
    df = df.sort_values(time_col).drop_duplicates(subset=[time_col])
    df = df.reset_index(drop=True)
    # Rename canonical
    return df.rename(columns={time_col: "Time", lmp_col: "LMP"})[["Time", "LMP"]]


def fill_dst_gaps(df: pd.DataFrame, year: int) -> pd.DataFrame:
    """CAISO DAM reports 23h on spring-forward day and 25h on fall-back day.
    Reindex to a uniform 8760-hour America/Los_Angeles grid and forward-fill
    any DST gap."""
    idx = pd.date_range(
        start=f"{year}-01-01 00:00",
        end=f"{year}-12-31 23:00",
        freq="h",
        tz=TZ,
    )
    assert len(idx) == 8760, f"{year} grid should be 8760 hours, got {len(idx)}"

    df = df.set_index("Time")
    df = df[~df.index.duplicated(keep="first")]
    df = df.reindex(idx)
    if df["LMP"].isna().any():
        n_gap = df["LMP"].isna().sum()
        print(f"  DST / missing rows: {n_gap} (forward-filling)")
        df["LMP"] = df["LMP"].ffill().bfill()
    df.index.name = "Time"
    return df.reset_index()


def validate(df: pd.DataFrame) -> None:
    assert len(df) == 8760, f"Expected 8760 rows, got {len(df)}"
    lmp = df["LMP"]
    mean = lmp.mean()
    assert EXPECT_ANNUAL_MEAN_MIN < mean < EXPECT_ANNUAL_MEAN_MAX, (
        f"Annual mean {mean:.2f} outside expected "
        f"[{EXPECT_ANNUAL_MEAN_MIN}, {EXPECT_ANNUAL_MEAN_MAX}] USD/MWh for NP15 2023"
    )
    assert lmp.min() >= EXPECT_MIN_FLOOR, (
        f"Minimum LMP {lmp.min():.2f} below floor {EXPECT_MIN_FLOOR}"
    )
    assert lmp.max() <= EXPECT_MAX_CAP, (
        f"Maximum LMP {lmp.max():.2f} above cap {EXPECT_MAX_CAP}"
    )
    print(
        f"  rows {len(df)}, mean {mean:.2f}, "
        f"min {lmp.min():.2f}, max {lmp.max():.2f} USD/MWh"
    )


def to_output_frame(df: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame({
        "timestamp": df["Time"].dt.strftime("%Y-%m-%d %H:%M:%S"),
        "price_usd_per_mwh": df["LMP"].round(2).values,
    })


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--year", type=int, default=TARGET_YEAR)
    parser.add_argument("--node", type=str, default=NODE)
    args = parser.parse_args()

    print(f"Downloading CAISO {args.node} DAM hourly LMP for {args.year} ...")
    raw = fetch_year_chunked(args.year, args.node)
    print(f"  raw rows returned: {len(raw)}")

    df = normalize(raw, args.node)
    print(f"  after node/tz normalize: {len(df)} rows")

    df = fill_dst_gaps(df, args.year)

    print("Validating ...")
    validate(df)

    out = to_output_frame(df)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(args.output, index=False)
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
