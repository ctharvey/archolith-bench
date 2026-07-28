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
  Retained for command-line compatibility. Menhir PRs cannot alter the trusted
  benchmark harness in this repository.

.PARAMETER MenhirRepo
  Local Menhir checkout used to resolve and fetch the target PR. Defaults to
  the sibling `../menhir` repository.

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
    [string]$Neo4jUri = "bolt://localhost:7689",
    [string]$Neo4jUser = "neo4j",
    [string]$Neo4jPassword = "lmedata123",
    [string]$MenhirRepo = "",
    [switch]$Confirm,
    [switch]$DryRun,
    [switch]$SkipMenhirStart
)

$ErrorActionPreference = 'Stop'
$RepoRoot = & git rev-parse --show-toplevel
$MenhirRepo = if ($MenhirRepo) { $MenhirRepo } else { Join-Path (Split-Path $RepoRoot -Parent) "menhir" }
if (-not (Test-Path (Join-Path $MenhirRepo ".git"))) {
    throw "Menhir repository not found at '$MenhirRepo'. Pass -MenhirRepo <path>."
}
$MenhirPython = Join-Path $MenhirRepo ".venv/Scripts/python.exe"
if (-not $DryRun -and -not $SkipMenhirStart -and -not (Test-Path $MenhirPython)) {
    throw "Menhir virtualenv Python not found at '$MenhirPython'."
}
$BenchPython = Join-Path $RepoRoot ".venv/Scripts/python.exe"
if (-not (Test-Path $BenchPython)) { $BenchPython = "python" }
$apiKey = $null
Push-Location $RepoRoot

Write-Host "## Menhir Recall Benchmark — PR #$PR" -ForegroundColor Cyan

# ─── Pre-flight ────────────────────────────────────────────────
function Assert-PreFlight {
    Write-Host "## Pre-flight checks" -ForegroundColor Cyan

    $script:apiKey = $env:OPENAI_API_KEY
    if (-not $script:apiKey) {
        $envFile = Join-Path $RepoRoot ".env"
        if (Test-Path $envFile) {
            $line = Get-Content $envFile | Where-Object { $_ -match '^OPENAI_API_KEY=' } | Select -First 1
            if ($line) { $script:apiKey = ($line -split '=',2)[1].Trim() }
        }
    }
    if (-not $script:apiKey -and -not $DryRun) {
        throw "OPENAI_API_KEY not in env or .env — refusing to run (use -DryRun to skip)"
    }
    if ($script:apiKey) {
        Write-Host "  OPENAI_API_KEY: present (len=$($script:apiKey.Length))"
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
        Write-Host "  prior runs for PR ${PR}: $count / 3"
    }

    # Resolve the PR in the Menhir repository, not the benchmark repository.
    Push-Location $MenhirRepo
    try {
        $prInfo = gh pr view $PR --json headRefOid,baseRefOid,author --jq '{sha:.headRefOid, author:.author.login}' 2>$null
    } finally {
        Pop-Location
    }
    if (-not $prInfo) {
        throw "Could not fetch PR $PR via gh — are you authed?"
    }
    $prData = $prInfo | ConvertFrom-Json
    Write-Host "  pre-flight: PASS" -ForegroundColor Green
    return $prData
}

# ─── Checkout PR into worktree ──────────────────────────────────
function New-PRWorktree {
    param([string]$HeadSha)
    Write-Host "## Step 1: fetch PR and create worktree" -ForegroundColor Cyan

    & git -C $MenhirRepo fetch origin "pull/$PR/head:menhir-pr-$PR-head" 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "git fetch failed for PR $PR" }

    $worktreePath = Join-Path $RepoRoot ".bench/worktrees/menhir-pr-$PR"
    if (Test-Path $worktreePath) {
        & git -C $MenhirRepo worktree remove --force $worktreePath 2>&1 | Out-Null
    }

    & git -C $MenhirRepo worktree add --detach $worktreePath $HeadSha 2>&1 | Out-Host
    if ($LASTEXITCODE -ne 0) { throw "git worktree add failed" }

    Write-Host "  worktree: $worktreePath"
    return $worktreePath
}

# ─── Main ───────────────────────────────────────────────────────
try {
    $prData = Assert-PreFlight

    $worktreePath = New-PRWorktree -HeadSha $prData.sha

    if (-not $DryRun) {
        # Bump per-PR count BEFORE running (so a crash still counts)
        $countFile = Join-Path $RepoRoot ".bench/runs/$PR/count.txt"
        $countDir = Split-Path $countFile -Parent
        if (-not (Test-Path $countDir)) { New-Item -ItemType Directory -Path $countDir -Force | Out-Null }
        $priorCount = if (Test-Path $countFile) { [int](Get-Content $countFile) } else { 0 }
        ($priorCount + 1) | Set-Content $countFile
        New-Item -ItemType File -Path (Join-Path $RepoRoot ".bench/cooldowns/$PR.txt") -Force | Out-Null
        $env:OPENAI_API_KEY = $apiKey
    }

    # Build orchestrator config
    $pythonArgs = @(
        "-m", "archolith_bench.ci",
        "--pr", $PR,
        "--head-sha", $prData.sha,
        "--pr-author", $prData.author,
        "--repo-root", $RepoRoot,
        "--menhir-dir", $worktreePath,
        "--menhir-python", $MenhirPython,
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
    & $BenchPython @pythonArgs
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
    $worktreePath = Join-Path $RepoRoot ".bench/worktrees/menhir-pr-$PR"
    if (Test-Path $worktreePath) {
        & git -C $MenhirRepo worktree remove --force $worktreePath 2>&1 | Out-Null
    }
    Pop-Location
}
