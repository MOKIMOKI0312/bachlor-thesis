$ErrorActionPreference = "Stop"
$RepoRoot = "C:\Users\18430\Desktop\毕业设计代码"
Set-Location $RepoRoot

$TS = Get-Date -Format "yyyyMMdd_HHmmss"
$ZipPath = "AI-Data-Center-Analysis_migration_bundle_20260311/analysis/m2f1_thesis_materials_$TS.zip"

# 内容清单（相对仓库根的路径）
$Files = @(
    # W2 数据
    "AI-Data-Center-Analysis_migration_bundle_20260311/analysis/m2f1_w2_scenario_compare_20260503_232820.csv",
    "AI-Data-Center-Analysis_migration_bundle_20260311/analysis/m2f1_w2_scenario_compare_20260503_232820.md",
    "AI-Data-Center-Analysis_migration_bundle_20260311/analysis/m2f1_w2b_scenario_compare_20260504_054338.csv",
    "AI-Data-Center-Analysis_migration_bundle_20260311/analysis/m2f1_w2b_scenario_compare_20260504_054338.md",
    "AI-Data-Center-Analysis_migration_bundle_20260311/analysis/m2f1_w2_pv_diagnostic_20260503_232820.json",
    "AI-Data-Center-Analysis_migration_bundle_20260311/analysis/m2f1_w2b_pv_diagnostic_20260504_054338.json",
    "AI-Data-Center-Analysis_migration_bundle_20260311/analysis/m2f1_w2_scenario_validation_20260503_232820.json",
    "AI-Data-Center-Analysis_migration_bundle_20260311/analysis/m2f1_w2b_scenario_validation_20260504_054338.json",
    "AI-Data-Center-Analysis_migration_bundle_20260311/analysis/m2f1_w2_negative_finding_summary.md",
    # W1-3 robustness
    "AI-Data-Center-Analysis_migration_bundle_20260311/analysis/m2f1_w1_3_robustness_curve_20260503_194137.csv",
    "AI-Data-Center-Analysis_migration_bundle_20260311/analysis/m2f1_w1_3_robustness_curve_20260503_194137.md",
    # W3 主表 + 4 PNG
    "AI-Data-Center-Analysis_migration_bundle_20260311/analysis/m2f1_thesis_main_table.md",
    "AI-Data-Center-Analysis_migration_bundle_20260311/analysis/m2f1_w2_figures_20260504_123702/fig1_w2_head_to_head.png",
    "AI-Data-Center-Analysis_migration_bundle_20260311/analysis/m2f1_w2_figures_20260504_123702/fig2_w1_robustness_curve.png",
    "AI-Data-Center-Analysis_migration_bundle_20260311/analysis/m2f1_w2_figures_20260504_123702/fig3_milp_soc_trajectory_week26.png",
    "AI-Data-Center-Analysis_migration_bundle_20260311/analysis/m2f1_w2_figures_20260504_123702/fig4_pv_load_diurnal_profile.png",
    # 关键工具源码
    "AI-Data-Center-Analysis_migration_bundle_20260311/tools/m2_tes_mpc_oracle.py",
    "AI-Data-Center-Analysis_migration_bundle_20260311/tools/evaluate_m2_rule_baseline.py",
    "AI-Data-Center-Analysis_migration_bundle_20260311/tools/build_w2_scenario_summary.py",
    "AI-Data-Center-Analysis_migration_bundle_20260311/tools/m2_mpc_plots.py",
    "AI-Data-Center-Analysis_migration_bundle_20260311/tools/m2_mpc_demo.ps1",
    "AI-Data-Center-Analysis_migration_bundle_20260311/tools/run_w2_scenario_batch.ps1",
    "AI-Data-Center-Analysis_migration_bundle_20260311/tools/run_w2b_scenario_batch.ps1",
    # 文档
    "README_handoff.md",
    "项目目标/技术路线.md",
    "项目目标/3周收尾路线-MILP-MPC-2026-05-03.md",
    "项目目标/W2-计划-TES节能-PV自消纳-2026-05-04.md"
)

# Verify all exist
$missing = @()
foreach ($f in $Files) {
    if (-not (Test-Path $f)) { $missing += $f }
}
if ($missing.Count -gt 0) {
    Write-Host "MISSING FILES:" -ForegroundColor Red
    $missing | ForEach-Object { Write-Host "  $_" }
    throw "thesis materials zip aborted: $($missing.Count) files missing"
}

# Compress
Compress-Archive -Path $Files -DestinationPath $ZipPath -CompressionLevel Optimal -Force
Write-Host "Wrote $ZipPath"

# Sanity print
$zipInfo = Get-Item $ZipPath
Write-Host "Size: $([math]::Round($zipInfo.Length / 1KB, 1)) KB"
Write-Host "File count: $($Files.Count)"
