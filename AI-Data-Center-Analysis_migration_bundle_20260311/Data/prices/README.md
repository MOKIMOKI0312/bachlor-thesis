# Electricity Price Data

## 主用：`CAISO_NP15_2023_hourly.csv`（M2 主实验）

CAISO（California Independent System Operator）NP15 Gen Trading Hub 的 2023 年全年 day-ahead hourly LMP（Locational Marginal Price）。

| 字段 | 说明 |
|---|---|
| 节点 | `TH_NP15_GEN-APND`（NP15 Gen Hub, zonal, 覆盖 Northern California 含硅谷）|
| 市场 | Day-Ahead Hourly（DAM）|
| 时区 | America/Los_Angeles（与 Palo Alto PV 和 SFO EPW 一致）|
| 行数 | 8760（DST 切换日 forward-fill，保证固定网格）|
| 列 | `timestamp, price_usd_per_mwh` |
| 数据源 | CAISO OASIS 公开 API，通过 `gridstatus` Python 包（>=0.35）获取 |

**获取方式**：

```bash
pip install gridstatus
D:/Anaconda/python.exe tools/download_caiso_lmp.py
```

脚本按月分批查询 OASIS（单次查询 ≤ 31 天），自动去重、时区转换、DST 填补。见 `tools/download_caiso_lmp.py`。

**审稿友好性**：NP15 DAM 是 CAISO 最流动的 zonal 价格，SustainDC (NeurIPS 2024) 和 Ju & Crozier (Applied Energy 2024) 的 RL 调度论文都用它。鸭子曲线（duck curve）带来的中午负电价 + 傍晚峰值的日内梯度是 reward shaping 研究观察 policy 分化的理想信号。

## 备用：`SGP_USEP_2023_hourly.csv`（Singapore 合成，M3 或附录用）

保留原 `download_usep.py` 产物作为 M3 中国章节的对照或论文附录材料。

`SGP_USEP_2023_hourly.csv` 是**合成数据**：

1. EMA 公开 2023 月均 USEP 表（`Average-Monthly-USEP.pdf`）
2. 典型 Singapore 批发电价日内曲线（夜谷 02-06，晚峰 19-22）
3. Log-normal 小时噪声（sigma=0.22），月均保持不变

EMC 的真实半小时 USEP 需 SAML SSO 账号（SEW+ 门户），非市场参与者无法获取，详见 `项目目标/决策-站点切换-CAISO-2026-04-19.md`。此文件不在 M2 主实验中使用。

产出脚本：`tools/download_usep.py`。
