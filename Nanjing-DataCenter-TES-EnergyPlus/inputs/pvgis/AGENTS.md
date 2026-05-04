# PVGIS Input Rules

本目录预留给 PVGIS 原始导出文件、参数记录和由 PVGIS 数据派生出的 PV 时序输入。

## 规则

- 不把未知来源的 PV 曲线放入本目录后写成 PVGIS 结果。
- 每个 PVGIS 导出或派生文件都应配套记录地点、经纬度、weather database、装机容量、system loss、slope、azimuth、时间分辨率和生成日期。
- 原始下载文件和处理后的标准 CSV 应能区分；不要覆盖原始 PVGIS 文件。
- 如派生标准输入 CSV，应满足上级目录要求的 `timestamp,power_kw` schema。
- 修改或新增 PVGIS 文件后，检查是否需要同步更新 `../../docs/`、论文 LaTeX 或输入数据说明。
