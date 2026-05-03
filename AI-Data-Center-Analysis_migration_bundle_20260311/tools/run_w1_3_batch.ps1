$ErrorActionPreference = "Stop"
$Python = "D:/Anaconda/python.exe"
$OutDir = "runs/m2_tes_mpc_oracle"
$TS = Get-Date -Format "yyyyMMdd_HHmmss"
$FailedCells = @()

function Run-Cell {
    param(
        [string]$Tag,
        [string[]]$ExtraArgs
    )
    Write-Host "==> $Tag"
    & $Python tools/m2_tes_mpc_oracle.py `
        --tag $Tag `
        --eval-design trainlike `
        --max-steps 672 `
        --out-dir $OutDir `
        --solver milp `
        @ExtraArgs
    if ($LASTEXITCODE -ne 0) {
        $script:FailedCells += $Tag
        Write-Host "FAILED: $Tag (exit $LASTEXITCODE)" -ForegroundColor Red
        throw "cell $Tag failed; halting batch (set:Stop)"
    }
}

Run-Cell "w1_3_perfect_$TS" @("--forecast-noise-mode", "perfect")

foreach ($pair in @(@(0.05, "05"), @(0.10, "10"), @(0.20, "20"))) {
    $sigma = $pair[0]
    $slabel = $pair[1]
    foreach ($seed in 1, 2, 3) {
        Run-Cell "w1_3_gauss_s${slabel}_seed${seed}_$TS" @(
            "--forecast-noise-mode", "gaussian",
            "--forecast-noise-sigma", "$sigma",
            "--forecast-noise-seed", "$seed"
        )
    }
}

foreach ($h in 1, 4, 12) {
    Run-Cell "w1_3_persist_h${h}_$TS" @(
        "--forecast-noise-mode", "persistence_h",
        "--forecast-noise-persist-h", "$h"
    )
}

Write-Host "TS=$TS"
Write-Host "Batch OK, 13 cells, no failures."
