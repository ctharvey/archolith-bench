<#
.SYNOPSIS
  Run the menhir recall benchmark against a PR's menhir code, locally.

.DESCRIPTION
  Fetches a PR into an isolated git worktree, starts the PR's menhir as a
  subprocess pointed at a budget-capped OpenAI proxy (so the PR code never
  sees the real API key), runs the stratified LongMemEval slice, compares
  to the pinned baseline, and writes a PR comment card.

  The bench harness and baseline come from main — the PR cannot modify what
  tests it. Budget caps are enforced in the proxy process, which the PR
  cannot modify.

.PARAMETER PR
  PR number to benchmark.

.PARAMETER MaxLLMCalls
  Hard cap on LLM calls. Default 200.

.PARAMETER MaxUSD
  Hard cap on USD spent. Default 5.0.

.PARAMETER MaxSeconds
  Hard cap on wall-clock seconds. Default 900 (15 min).

.PARAMETER QuestionsPerType
  Questions per LongMemEval type. Default 20 (120 total across 6 types).

.PARAMETER Confirm
  Required if the PR touches bench infrastructure (archolith-bench/,
  scripts/bench-pr.ps1, or the baseline file).

.PARAMETER DryRun
  Walk through the steps without spawning LLM calls or starting menhir.

.PARAMETER SkipMenhirStart
  Use this if menhir is already running on the configured port. Useful for
  iterative testing.

.EXAMPLE
  .\scripts\bench-pr.ps1 -PR 123

.EXAMPLE
  .\scripts\bench-pr.ps1 -PR 123 -DryRun

.EXAMPLE
  .\scripts\bench-pr.ps1 -PR 123 -SkipMenhirStart
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)]
    [int]$PR,

    [int]$MaxLLMCalls = 200,
    [double]$MaxUSD = 5.0,
    [int]$MaxSeconds = 900,
    [int]$QuestionsPerType = 20,
    [int]$MenhirPort = 8090,
    [int]$ProxyPort = 8765,
    [string]$Neo4jUri = "bolt://localhost:7687",
    [string]$Neo4jUser = "neo4j",
    [string]$Neo4jPassword = "password",
    [switch]$Confirm,
    [switch]$DryRun,
    [switch]$SkipMenhirStart
)

$ErrorActionPreference = 'Stop'
$RepoRoot = & git rev-parse --show-toplevel
Push-Location $RepoRoot

Write-Host "## Menhir Recall Benchmark — PR #$PR" -ForegroundColor Cyan

# ─── Pre-flight ────────────────────────────────────────────────
function Assert-PreFlight {
    Write-Host "## Pre-flight checks" -ForegroundColor Cyan

    $apiKey = $env:OPENAI_API_KEY
    if (-not $apiKey) {
        $envFile = Join-Path $RepoRoot ".env"
        if (Test-Path $envFile) {
            $line = Get-Content $envFile | Where-Object { $_ -match '^OPENAI_API_KEY=' } | Select -First 1
            if ($line) { $apiKey = ($line -split '=',2)[1].Trim() }
        }
    }
    if (-not $apiKey -and -not $DryRun) {
        throw "OPENAI_API_KEY not in env or .env — refusing to run (use -DryRun to skip)"
    }
    if ($apiKey) {
        Write-Host "  OPENAI_API_KEY: present (len=$($apiKey.Length))"
    }

    # Cooldown
    $cooldownFile = Join-Path $RepoRoot ".bench/cooldowns/$PR.txt"
    if (Test-Path $cooldownFile) {
        $lastRun = (Get-Item $cooldownFile).LastWriteTime
        $elapsed = (Get-Date) - $lastRun
        if ($elapsed.TotalMinutes -lt 10) {
            $wait = [math]::Ceiling(10 - $elapsed.TotalMinutes)
            throw "Cooldown active for PR $PR — wait ${wait}m"
        }
    }

    # Per-PR count
    $countFile = Join-Path $RepoRoot ".bench/runs/$PR/count.txt"
    if (Test-Path $countFile) {
        $count = [int](Get-Content $countFile)
        if ($count -ge 3) {
            throw "PR $PR already benched $count times (max 3)"
        }
        Write-Host "  prior runs for PR $PR: $count / 3"
    }

    # Sketchy-content check
    $prInfo = gh pr view $PR --json headRefOid,baseRefOid,author,files --jq '{sha:.headRefOid, author:.author.login, files:[.files[].path]}' 2>$null
    if (-not $prInfo) {
        throw "Could not fetch PR $PR via gh — are you authed?"
    }
    $prData = $prInfo | ConvertFrom-Json
    $sketchy = $prData.files | Where-Object {
        $_ -match '^(archolith-bench/|scripts/bench-pr)' -or
        $_ -match 'longmemeval-baseline\.json$'
    }
    if ($sketchy -and -not $Confirm) {
        Write-Warning "PR touches bench infrastructure:"
        $sketchy | ForEach-Object { Write-Warning "  $_" }
        throw "Re-run with -Confirm to proceed with a PR that modifies the bench itself"
    }

    Write-Host "  pre-flight: PASS" -ForegroundColor Green
    return $prData
}

# ─── Checkout PR into worktree ──────────────────────────────────
function New-PRWorktree {
    param([string]$HeadSha)
    Write-Host "## Step 1: fetch PR and create worktree" -ForegroundColor Cyan

    & git fetch origin "pull/$PR/head:pr-$PR-head" 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "git fetch failed for PR $PR" }

    $worktreePath = Join-Path $RepoRoot ".bench/worktrees/pr-$PR"
    if (Test-Path $worktreePath) {
        & git worktree remove --force $worktreePath 2>&1 | Out-Null
    }

    & git worktree add --detach $worktreePath $HeadSha 2>&1 | Out-Host
    if ($LASTEXITCODE -ne 0) { throw "git worktree add failed" }

    Write-Host "  worktree: $worktreePath"
    return $worktreePath
}

# ─── Overlay bench harness from main ────────────────────────────
function Overlay-BenchHarness {
    param([string]$WorktreePath)
    Write-Host "## Step 2: overlay bench harness from main" -ForegroundColor Cyan

    Push-Location $WorktreePath
    try {
        # Force-checkout bench harness + baseline from main
        & git checkout main -- archolith_bench/ci/ 2>&1 | Out-Host
        & git checkout main -- archolith_bench/harness/ 2>&1 | Out-Host
        & git checkout main -- archolith_bench/cli.py 2>&1 | Out-Host
        & git checkout main -- benchmarks/longmemeval-baseline.json 2>&1 | Out-Host
        & git checkout main -- scripts/bench-pr.ps1 2>&1 | Out-Host
        & git checkout main -- pyproject.toml 2>&1 | Out-Host
    } finally {
        Pop-Location
    }
    Write-Host "  bench harness: from main (PR's version ignored)"
}

# ─── Main ───────────────────────────────────────────────────────
try {
    $prData = Assert-PreFlight

    $worktreePath = New-PRWorktree -HeadSha $prData.sha
    Overlay-BenchHarness -WorktreePath $worktreePath

    # Bump per-PR count BEFORE running (so a crash still counts)
    $countFile = Join-Path $RepoRoot ".bench/runs/$PR/count.txt"
    $countDir = Split-Path $countFile -Parent
    if (-not (Test-Path $countDir)) { New-Item -ItemType Directory -Path $countDir -Force | Out-Null }
    $priorCount = if (Test-Path $countFile) { [int](Get-Content $countFile) } else { 0 }
    ($priorCount + 1) | Set-Content $countFile
    New-Item -ItemType File -Path (Join-Path $RepoRoot ".bench/cooldowns/$PR.txt") -Force | Out-Null

    # Build orchestrator config
    $env:BENCH_MENHIR_DIR = $worktreePath
    $pythonArgs = @(
        "-m", "archolith_bench.ci",
        "--pr", $PR,
        "--head-sha", $prData.sha,
        "--pr-author", $prData.author,
        "--repo-root", $RepoRoot,
        "--menhir-port", $MenhirPort,
        "--proxy-port", $ProxyPort,
        "--neo4j-uri", $Neo4jUri,
        "--neo4j-user", $Neo4jUser,
        "--neo4j-password", $Neo4jPassword,
        "--max-calls", $MaxLLMCalls,
        "--max-usd", $MaxUSD,
        "--max-seconds", $MaxSeconds,
        "--questions-per-type", $QuestionsPerType
    )
    if ($DryRun) { $pythonArgs += "--dry-run" }
    if ($SkipMenhirStart) { $pythonArgs += "--skip-menhir-start" }
    if ($Confirm) { $pythonArgs += "--confirm" }

    # Run orchestrator
    & python @pythonArgs
    $exitCode = $LASTEXITCODE

    # Show the card
    $cardPath = Join-Path $RepoRoot ".bench/runs/$PR/card.md"
    if (Test-Path $cardPath) {
        Write-Host "`n--- PR CARD ---" -ForegroundColor Yellow
        Get-Content $cardPath
        Write-Host "---" -ForegroundColor Yellow
        Write-Host "`nCard written to: $cardPath"
        Write-Host "Post to PR with:  gh pr comment $PR --body-file `"$cardPath`""
    }

    exit $exitCode
}
finally {
    # Clean up worktree (keep logs/results)
    $worktreePath = Join-Path $RepoRoot ".bench/worktrees/pr-$PR"
    if (Test-Path $worktreePath) {
        & git worktree remove --force $worktreePath 2>&1 | Out-Null
    }
    Pop-Location
}
