# Singapore USEP hourly series

`SGP_USEP_2023_hourly.csv` is **synthesised** from:

1. EMA published monthly USEP averages for 2023 (see `Average-Monthly-USEP.pdf`).
2. Typical Singapore wholesale diurnal profile (night valley 02-06, evening peak 19-22).
3. Log-normal hourly noise (sigma=0.22), monthly-mean preserved.

EMC's real half-hourly USEP requires SAML SSO authentication and is not accessible via automated download. If genuine EMC half-hourly CSVs are later obtained, replace this file with a simple aggregation to hourly means.

Produced by `tools/download_usep.py`.
