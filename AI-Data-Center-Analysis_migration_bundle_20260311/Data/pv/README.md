# PV Output Data

## 主用：`CAISO_PaloAlto_PV_6MWp_hourly.csv`（M2 主实验）

Palo Alto, California 6 MWp 光伏电站的 2023 年逐时出力时间序列。

| 字段 | 值 |
|---|---|
| 坐标 | 37.44°N, -122.14°W（Palo Alto 中心，Stanford 附近）|
| 装机容量 | 6 MWp（crystalline-Si）|
| 固定倾角 | 30°（NorCal 最优，约 latitude-5）|
| 方位 | 180°（正南）|
| 系统损耗 | 14%（PVGIS 默认）|
| 时区 | America/Los_Angeles（wall-clock 本地时，tz-naive）|
| 行数 | 8760 |
| 列 | `timestamp, power_kw` |
| 数据源 | PVGIS-SARAH2 via `pvlib.iotools.get_pvgis_hourly()` |
| 源年 → 目标年 | 2020（PVGIS 最新 SARAH2 覆盖年）→ 2023（对齐 TMY EPW + LMP）|

**典型年产量**：10.44 GWh / 年，比产率 1740 kWh/kWp（NorCal 典型范围 1500-1900）。

**日内形态**：正午 12-13 点达峰 ~3968 kW（年均），夏季单日峰值可达 5500+ kW；夜间 20:00-05:00 归零。月产量 5-7 月 1.0 GWh，12 月 0.67 GWh，反映 NorCal 季节性辐照差异。

**获取方式**：

```bash
D:/Anaconda/python.exe tools/generate_pvgis.py --site palo-alto
```

`tools/generate_pvgis.py` 已改造为多站点预设架构（`SITE_PRESETS` 字典），支持 `palo-alto`（默认）和 `singapore` 两套配置。

**DST 处理**：Palo Alto 有夏令时。为了与 `SGP_PV_6MWp_hourly.csv`（Singapore 无 DST）的 tz-naive schema 保持一致，本脚本将源数据 tz_convert 到 Pacific 后丢弃 tz 信息，用 naive 本地 wall-clock 时间 floor + dedupe + reindex 到完整 8760 小时网格。春季跳表（3 月 12 日 02:00→03:00）的 1 小时空洞由邻近小时 forward-fill，秋季回表（11 月 5 日 01:00→02:00）的重复小时保留首次出现。此简化对 RL 环境（按 ordinal hour 索引）无影响，最多引入 ±1 小时的 solar-time-vs-clock-time 偏差（每年 2 天）。

## 备用：`SGP_PV_6MWp_hourly.csv`（Singapore，M3 或敏感性分析用）

保留原 Singapore Changi 站点产物作为对照或 M3 中国章节的气候外推参考。

| 字段 | 值 |
|---|---|
| 坐标 | 1.35°N, 103.82°E（Singapore Changi）|
| 装机 / 倾角 / 方位 / 损耗 | 6 MWp / 10° / 180° / 14% |
| 时区 | Asia/Singapore（无 DST）|

获取：`D:/Anaconda/python.exe tools/generate_pvgis.py --site singapore`

决策背景详见 `项目目标/archive/决策-站点切换-CAISO-2026-04-19.md`。
