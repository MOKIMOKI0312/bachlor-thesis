# Demo: short walkthrough of MPC TES control on M2-F1 trainlike env.
# Runs heuristic + MILP for 96 steps each, plus a single SOC/sign-rate PNG.
# Designed for live presentation.

$ErrorActionPreference = "Stop"
$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $RepoRoot
$Conda = "D:/Anaconda/Scripts/conda.exe"
$PythonArgs = @("run", "-n", "aidc-py310", "python")
$PlotPython = "D:/Anaconda/python.exe"
$DemoDir = "runs/m2_tes_mpc_oracle"
$TS = Get-Date -Format "yyyyMMdd_HHmmss"

$EnergyPlusRoot = $null
if ($env:ENERGYPLUS_PATH -and (Test-Path (Join-Path $env:ENERGYPLUS_PATH "pyenergyplus"))) {
    $EnergyPlusRoot = $env:ENERGYPLUS_PATH
} else {
    $KnownEnergyPlusRoot = "C:/Users/18430/EnergyPlus-23.1.0/EnergyPlus-23.1.0-87ed9199d4-Windows-x86_64"
    if (Test-Path (Join-Path $KnownEnergyPlusRoot "pyenergyplus")) {
        $EnergyPlusRoot = $KnownEnergyPlusRoot
    }
}
if (-not $EnergyPlusRoot) {
    $EnergyPlusRoot = Get-ChildItem $HOME -Directory -Filter "EnergyPlus-*" -ErrorAction SilentlyContinue |
        ForEach-Object { Get-ChildItem $_.FullName -Directory -ErrorAction SilentlyContinue } |
        Where-Object { Test-Path (Join-Path $_.FullName "pyenergyplus") } |
        Sort-Object FullName |
        Select-Object -First 1 -ExpandProperty FullName
}
if ($EnergyPlusRoot) {
    $env:ENERGYPLUS_PATH = $EnergyPlusRoot
    $env:EPLUS_PATH = $EnergyPlusRoot
    $env:PYTHONPATH = if ($env:PYTHONPATH) { "$EnergyPlusRoot;$env:PYTHONPATH" } else { $EnergyPlusRoot }
    $env:PATH = "$EnergyPlusRoot;$env:PATH"
    Write-Host "ENERGYPLUS_PATH=$EnergyPlusRoot"
}

function Assert-DemoArtifacts {
    param([string]$Tag)
    $runDir = Join-Path $DemoDir $Tag
    $monitor = Join-Path $runDir "monitor.csv"
    $result = Join-Path $runDir "result.json"
    if ((Test-Path $monitor) -and (Test-Path $result)) {
        return
    }
    throw "missing demo artifacts for $Tag"
}

$startTime = Get-Date

Write-Host "==> [1/3] MPC-Heuristic 96 step demo"
& $Conda @PythonArgs tools/m2_tes_mpc_oracle.py `
    --tag demo_heuristic_$TS --eval-design trainlike --max-steps 96 `
    --out-dir $DemoDir --solver heuristic --forecast-noise-mode perfect
if ($LASTEXITCODE -ne 0) { throw "demo heuristic failed (exit $LASTEXITCODE)" }
Assert-DemoArtifacts "demo_heuristic_$TS"

Write-Host "==> [2/3] MPC-MILP 96 step demo"
& $Conda @PythonArgs tools/m2_tes_mpc_oracle.py `
    --tag demo_milp_$TS --eval-design trainlike --max-steps 96 `
    --out-dir $DemoDir --solver milp --forecast-noise-mode perfect
if ($LASTEXITCODE -ne 0) { throw "demo milp failed (exit $LASTEXITCODE)" }
Assert-DemoArtifacts "demo_milp_$TS"

Write-Host "==> [3/3] Generating demo SOC + valve sign-rate PNG"
$DemoOutDir = "analysis/m2f1_demo_$TS"
New-Item -ItemType Directory -Force -Path $DemoOutDir | Out-Null

$pyScript = @"
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

heur = pd.read_csv(r'$DemoDir/demo_heuristic_$TS/monitor.csv')
milp = pd.read_csv(r'$DemoDir/demo_milp_$TS/monitor.csv')

def valve_series(df):
    for col in ['tes_valve_target', 'TES_valve_wrapper_position', 'TES_DRL']:
        if col in df.columns:
            return pd.to_numeric(df[col], errors='coerce').fillna(0.0).to_numpy(), col
    raise RuntimeError('No TES valve column found in monitor.csv')

def sign_rates(values):
    eps = 1e-6
    return [
        float((values < -eps).mean() * 100.0),
        float((abs(values) <= eps).mean() * 100.0),
        float((values > eps).mean() * 100.0),
    ]

heur_valve, heur_col = valve_series(heur)
milp_valve, milp_col = valve_series(milp)
rates = [sign_rates(heur_valve), sign_rates(milp_valve)]

fig, (ax_soc, ax_bar) = plt.subplots(
    2, 1, figsize=(10, 6.4), dpi=140,
    gridspec_kw={'height_ratios': [2.2, 1.0]}
)
ax_soc.plot(heur['TES_SOC'].values, color='#ff7f0e', label='Heuristic', linewidth=1.6)
ax_soc.plot(milp['TES_SOC'].values, color='#d62728', label='MILP', linewidth=1.6)
ax_soc.set_xlabel('Step (15-min)')
ax_soc.set_ylabel('TES_SOC')
ax_soc.set_title('M2-F1 demo: TES SOC trajectory (96 step / 24 h)')
ax_soc.grid(alpha=0.3)
ax_soc.legend(loc='best')

labels = ['Charge valve < 0', 'Hold valve = 0', 'Discharge valve > 0']
colors = ['#1f77b4', '#8c8c8c', '#d62728']
left = [0.0, 0.0]
ypos = [0, 1]
for idx, (label, color) in enumerate(zip(labels, colors)):
    vals = [rates[0][idx], rates[1][idx]]
    ax_bar.barh(ypos, vals, left=left, color=color, label=label)
    for y, lft, val in zip(ypos, left, vals):
        if val >= 5.0:
            ax_bar.text(lft + val / 2.0, y, f'{val:.0f}%', va='center', ha='center',
                        color='white', fontsize=8)
    left = [lft + val for lft, val in zip(left, vals)]
ax_bar.set_yticks(ypos, ['Heuristic', 'MILP'])
ax_bar.set_xlim(0, 100)
ax_bar.set_xlabel('Valve sign-rate over 96 steps (%)')
ax_bar.grid(axis='x', alpha=0.25)
ax_bar.legend(loc='lower center', bbox_to_anchor=(0.5, -0.58), ncol=3, frameon=False)
ax_bar.text(100, -0.42, f'valve cols: {heur_col} / {milp_col}',
            ha='right', va='center', fontsize=8, color='#555555')
fig.tight_layout()
fig.savefig(r'$DemoOutDir/demo_soc_trajectory.png')
print('Wrote', r'$DemoOutDir/demo_soc_trajectory.png')
"@
$pyScript | & $PlotPython -
if ($LASTEXITCODE -ne 0) { throw "demo plot failed" }
$DemoPng = Join-Path $DemoOutDir "demo_soc_trajectory.png"
if (-not (Test-Path $DemoPng)) { throw "demo plot missing: $DemoPng" }

$duration = (Get-Date) - $startTime
Write-Host ""
Write-Host "Demo complete. Outputs:"
Write-Host "  $DemoDir/demo_heuristic_$TS/"
Write-Host "  $DemoDir/demo_milp_$TS/"
Write-Host "  $DemoOutDir/demo_soc_trajectory.png"
Write-Host ""
Write-Host "Total wall-clock: $($duration.TotalMinutes.ToString('F2')) minutes"
