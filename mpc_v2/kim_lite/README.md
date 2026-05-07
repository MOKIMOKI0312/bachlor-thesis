# Kim-lite Paper-like MPC

This package is a separate Kim-style paper-like MPC path for thesis experiments.
It is intentionally independent from the rebuilt minimal `mpc_v2/core` controller.

## Scope

- Cold-plant + TES scheduling structure inspired by Kim et al. 2022.
- Structural reproduction only; this package does not claim numeric reproduction of Kim et al. 2022.
- First version uses a signed net TES proxy:

```text
Q_tes_net = Q_chiller - Q_load
soc[k+1] = (1 - loss_per_h * dt_h) * soc[k] + Q_tes_net[k] * dt_h / E_tes_kwh_th
```

Positive `Q_tes_net` charges TES. Negative `Q_tes_net` discharges TES.

## Deferred Or Explicitly Scoped Features

- Full split charge/discharge efficiency model is deferred.
- Complex DR baseline is deferred; Phase D implements peak-cap first.
- PPT files are not modified unless `PPT_PATH` is explicitly provided and backed up.
