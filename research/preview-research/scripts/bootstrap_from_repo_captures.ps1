param(
    [string]$Python = (Join-Path $PSScriptRoot "..\.venv\Scripts\python.exe")
)

$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$repositoryRoot = (Resolve-Path (Join-Path $projectRoot "..\..")).Path
$pairCache = Join-Path $repositoryRoot "research\pair-fit-v2\cache"

if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) {
    throw "Python executable not found: $Python. Run project setup or pass -Python explicitly."
}
if (-not (Test-Path -LiteralPath $pairCache -PathType Container)) {
    throw "Pair Fit cache not found: $pairCache. Use live acquisition or manual imports instead."
}

Set-Location $projectRoot
$env:PYTHONPATH = Join-Path $projectRoot "src"

function Invoke-Preview {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Arguments)
    & $Python -m preview_research.cli @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "preview_research command failed: $($Arguments -join ' ')"
    }
}

$playerCaptures = @(
    @{ Season = "2021-22"; Dataset = "player_base_totals"; Phase = "Phase 2C"; Body = "phase2c\raw\phase2c-raw-asset_832db055e9f3ebfac420b968.json"; Meta = "phase2c\raw\phase2c-raw-asset_832db055e9f3ebfac420b968.metadata.json" },
    @{ Season = "2021-22"; Dataset = "player_per100"; Phase = "Phase 2C"; Body = "phase2c\raw\phase2c-raw-asset_743bf37f13833e2d00f00da1.json"; Meta = "phase2c\raw\phase2c-raw-asset_743bf37f13833e2d00f00da1.metadata.json" },
    @{ Season = "2022-23"; Dataset = "player_base_totals"; Phase = "Phase 2A"; Body = "phase2a\raw\phase2a-raw-asset_d5f038caee22019a748eed5c.json"; Meta = "phase2a\raw\phase2a-raw-asset_d5f038caee22019a748eed5c.metadata.json" },
    @{ Season = "2022-23"; Dataset = "player_per100"; Phase = "Phase 2A"; Body = "phase2a\raw\phase2a-raw-asset_ab061d6a5bba1d84a946134c.json"; Meta = "phase2a\raw\phase2a-raw-asset_ab061d6a5bba1d84a946134c.metadata.json" },
    @{ Season = "2023-24"; Dataset = "player_base_totals"; Phase = "Phase 3A1"; Body = "phase3a1\raw\league_dash_player_stats_2023-24_base_totals.attempt-1.json"; Meta = $null },
    @{ Season = "2023-24"; Dataset = "player_per100"; Phase = "direct audit"; Body = "live_responses\league_dash_player_stats_2023-24_base_per100possessions.json"; Meta = "live_responses\league_dash_player_stats_2023-24_base_per100possessions_metadata.json" },
    @{ Season = "2024-25"; Dataset = "player_base_totals"; Phase = "R2A"; Body = "phase3f-r2a\non-protected-prior-profiles\02-totals\verified-response.json"; Meta = "phase3f-r2a\non-protected-prior-profiles\02-totals\verification.json" },
    @{ Season = "2024-25"; Dataset = "player_per100"; Phase = "R2A"; Body = "phase3f-r2a\non-protected-prior-profiles\01-per100possessions\verified-response.json"; Meta = "phase3f-r2a\non-protected-prior-profiles\01-per100possessions\verification.json" },
    @{ Season = "2025-26"; Dataset = "player_base_totals"; Phase = "Phase 4A"; Body = "phase4a\2025-26-player-profiles\external\02-totals\verified-response.json"; Meta = "phase4a\2025-26-player-profiles\external\02-totals\verification.json" },
    @{ Season = "2025-26"; Dataset = "player_per100"; Phase = "Phase 4A"; Body = "phase4a\2025-26-player-profiles\external\01-per100possessions\verified-response.json"; Meta = "phase4a\2025-26-player-profiles\external\01-per100possessions\verification.json" }
)

foreach ($capture in $playerCaptures) {
    $arguments = @(
        "import-nba-json", (Join-Path $pairCache $capture.Body),
        "--dataset", $capture.Dataset,
        "--season", $capture.Season,
        "--source", "Audited Pair Fit v2 $($capture.Phase) stats.nba.com capture"
    )
    if ($null -ne $capture.Meta) {
        $arguments += @("--source-metadata", (Join-Path $pairCache $capture.Meta))
    }
    Invoke-Preview @arguments
}

foreach ($season in @("2021-22", "2022-23", "2023-24")) {
    $body = Join-Path $pairCache "phase3a1\raw\league_dash_player_shot_locations_${season}_base_totals_by_zone.attempt-1.json"
    Invoke-Preview import-nba-json $body `
        --dataset player_shot_zones --season $season `
        --source "Audited Pair Fit v2 Phase 3A1 stats.nba.com shot-zone capture" `
        --source-metadata (Join-Path $pairCache "phase3a1\manifest.json")
}

foreach ($season in @("2021-22", "2022-23", "2023-24", "2024-25", "2025-26")) {
    Invoke-Preview build-shooting --entity player --season $season
}

$benchmarkUrl = "https://www.kaggle.com/datasets/eoinamoore/historical-nba-data-and-player-box-scores"
Invoke-Preview benchmark --dataset player_base_totals --season 2025-26 `
    --column FG_PCT --entity-column PLAYER_ID --entity 1628983 `
    --expected 0.553 --tolerance 0.0005 `
    --source "Kaggle eoinamoore version 515 packaged snapshot: SGA raw FG%=55.3" `
    --source-url $benchmarkUrl
Invoke-Preview benchmark --dataset player_shooting --provider derived --season 2025-26 `
    --column CALC_FG3_PCT --entity-column PLAYER_ID --entity 1628983 `
    --expected 0.386 --tolerance 0.0005 `
    --source "Kaggle eoinamoore version 515 packaged snapshot: SGA raw FG3%=38.6" `
    --source-url $benchmarkUrl

Invoke-Preview coverage
