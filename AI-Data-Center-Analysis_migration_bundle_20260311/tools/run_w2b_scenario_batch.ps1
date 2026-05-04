$ErrorActionPreference = "Stop"
$Python = "D:/Anaconda/python.exe"
$OutDir = "runs/m2_tes_mpc_oracle"
$TS = Get-Date -Format "yyyyMMdd_HHmmss"
$LogDir = "logs/w2b_scenario_batch_$TS"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

if (-not $env:ENERGYPLUS_PATH) {
    $EnergyPlusRoot = Get-ChildItem $HOME -Directory -Filter "EnergyPlus-*" -ErrorAction SilentlyContinue |
        ForEach-Object { Get-ChildItem $_.FullName -Directory -ErrorAction SilentlyContinue } |
        Where-Object { Test-Path (Join-Path $_.FullName "pyenergyplus") } |
        Sort-Object FullName |
        Select-Object -First 1 -ExpandProperty FullName
    if ($EnergyPlusRoot) {
        $env:ENERGYPLUS_PATH = $EnergyPlusRoot
        $env:EPLUS_PATH = $EnergyPlusRoot
        $env:PYTHONPATH = if ($env:PYTHONPATH) { "$EnergyPlusRoot;$env:PYTHONPATH" } else { $EnergyPlusRoot }
        $env:PATH = "$EnergyPlusRoot;$env:PATH"
        Write-Host "ENERGYPLUS_PATH=$EnergyPlusRoot"
    }
}

function Run-Cmd {
    param([string]$Tag, [string[]]$CellArgs, [int]$TimeoutMinutes)
    Write-Host "==> $Tag"
    $startTime = Get-Date
    $stdout = Join-Path $LogDir "$Tag.stdout.log"
    $stderr = Join-Path $LogDir "$Tag.stderr.log"
    $proc = Start-Process -FilePath $Python -ArgumentList $CellArgs -NoNewWindow -PassThru `
        -RedirectStandardOutput $stdout -RedirectStandardError $stderr
    $lastSize = -1
    while (-not $proc.HasExited) {
        Start-Sleep -Seconds 30
        $duration = (Get-Date) - $startTime
        if ($duration.TotalMinutes -gt $TimeoutMinutes) {
            Stop-Process -Id $proc.Id -Force
            throw "cell $Tag timed out after $TimeoutMinutes min; stdout=$stdout stderr=$stderr"
        }
        if (Test-Path $stdout) {
            $size = (Get-Item $stdout).Length
            if ($size -ne $lastSize) {
                Write-Host "    elapsed=$($duration.TotalMinutes.ToString('F1')) min stdout_bytes=$size"
                Get-Content -Path $stdout -Tail 5 -ErrorAction SilentlyContinue
                $lastSize = $size
            } else {
                Write-Host "    elapsed=$($duration.TotalMinutes.ToString('F1')) min no new stdout"
            }
        } else {
            Write-Host "    elapsed=$($duration.TotalMinutes.ToString('F1')) min waiting for stdout"
        }
        if (Test-Path $stderr) {
            $errSize = (Get-Item $stderr).Length
            if ($errSize -gt 0) {
                Write-Host "    stderr tail:"
                Get-Content -Path $stderr -Tail 5 -ErrorAction SilentlyContinue
            }
        }
    }
    $proc.WaitForExit()
    $exit = $proc.ExitCode
    if ($null -eq $exit) {
        $stdoutText = if (Test-Path $stdout) { Get-Content -Raw -Path $stdout -ErrorAction SilentlyContinue } else { "" }
        if ($stdoutText -match "Wrote .+result\\.json" -and $stdoutText -match "Wrote .+monitor\\.csv") {
            $exit = 0
        } else {
            $exit = 1
        }
    }
    $duration = (Get-Date) - $startTime
    Write-Host "    exit=$exit duration=$($duration.TotalMinutes.ToString('F1')) min"
    Write-Host "    stdout=$stdout"
    Write-Host "    stderr=$stderr"
    if (Test-Path $stdout) { Get-Content -Path $stdout -Tail 20 -ErrorAction SilentlyContinue }
    if ((Test-Path $stderr) -and ((Get-Item $stderr).Length -gt 0)) {
        Write-Host "    stderr final tail:"
        Get-Content -Path $stderr -Tail 20 -ErrorAction SilentlyContinue
    }
    if ($exit -ne 0) { throw "cell $Tag failed (exit $exit)" }
}

Run-Cmd -Tag "w2b_mpc_milp_year_$TS" -CellArgs @(
    "tools/m2_tes_mpc_oracle.py",
    "--tag", "w2b_mpc_milp_year_$TS",
    "--eval-design", "official_ood",
    "--out-dir", $OutDir,
    "--solver", "milp",
    "--forecast-noise-mode", "perfect"
) -TimeoutMinutes 240

Run-Cmd -Tag "w2b_mpc_heuristic_year_$TS" -CellArgs @(
    "tools/m2_tes_mpc_oracle.py",
    "--tag", "w2b_mpc_heuristic_year_$TS",
    "--eval-design", "official_ood",
    "--out-dir", $OutDir,
    "--solver", "heuristic",
    "--forecast-noise-mode", "perfect"
) -TimeoutMinutes 60

Run-Cmd -Tag "w2b_baseline_neutral_year_$TS" -CellArgs @(
    "tools/evaluate_m2_rule_baseline.py",
    "--tag", "w2b_baseline_neutral_year_$TS",
    "--eval-design", "official_ood",
    "--policy", "neutral"
) -TimeoutMinutes 60

Write-Host "TS=$TS"
Write-Host "Batch OK, 3 W2-B full-year cells, no failures."
Write-Host "Logs: $LogDir"
$TS | Out-File -Encoding utf8 tools/_w2b_batch_ts.txt
