param(
    [string]$EnergyPlusExe,

    [string]$OutputDir = "out/energyplus_nanjing"
)

$ErrorActionPreference = "Stop"

function Assert-File {
    param([string]$Path, [string]$Label)
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "$Label not found: $Path"
    }
}

function Assert-CsvHeader {
    param([string]$Path, [string]$ExpectedHeader, [string]$Label)
    $header = Get-Content -LiteralPath $Path -TotalCount 1 -Encoding UTF8
    if ($header -ne $ExpectedHeader) {
        throw "$Label header mismatch. Expected '$ExpectedHeader', got '$header'"
    }
}

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Model = Join-Path $Root "model/Nanjing_DataCenter_TES.epJSON"
$Weather = Join-Path $Root "weather/CHN_JS_Nanjing.582380_TMYx.2009-2023.epw"
$Price = Join-Path $Root "inputs/Jiangsu_TOU_2025_hourly.csv"
$Pv = Join-Path $Root "inputs/CHN_Nanjing_PV_6MWp_hourly.csv"
$Out = Join-Path $Root $OutputDir

if ([string]::IsNullOrWhiteSpace($EnergyPlusExe)) {
    throw "Missing required -EnergyPlusExe path. Example: .\run_energyplus_nanjing.ps1 -EnergyPlusExe 'C:\EnergyPlusV23-1-0\energyplus.exe'"
}

Assert-File -Path $EnergyPlusExe -Label "EnergyPlus executable"
Assert-File -Path $Model -Label "EnergyPlus model"
Assert-File -Path $Weather -Label "Nanjing weather"
Assert-File -Path $Price -Label "TOU price input"
Assert-File -Path $Pv -Label "PV forecast input"
Assert-CsvHeader -Path $Price -ExpectedHeader "timestamp,price_usd_per_mwh" -Label "TOU price input"
Assert-CsvHeader -Path $Pv -ExpectedHeader "timestamp,power_kw" -Label "PV forecast input"

New-Item -ItemType Directory -Force -Path $Out | Out-Null

Write-Host "EnergyPlus: $EnergyPlusExe"
Write-Host "Model:      $Model"
Write-Host "Weather:    $Weather"
Write-Host "Price CSV:  $Price"
Write-Host "PV CSV:     $Pv"
Write-Host "Output:     $Out"

& $EnergyPlusExe -w $Weather -d $Out $Model
$exit = $LASTEXITCODE
if ($exit -ne 0) {
    throw "EnergyPlus failed with exit code $exit"
}

Write-Host "EnergyPlus run completed."
