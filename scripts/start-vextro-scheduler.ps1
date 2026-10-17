param(
    [switch]$SkipStartupDelay
)

$ErrorActionPreference = "Stop"

if (-not $SkipStartupDelay) {
    Start-Sleep -Seconds 60
}

$repositoryRoot = Split-Path -Parent $PSScriptRoot
$pythonPath = Join-Path $repositoryRoot "backend\.venv\Scripts\python.exe"
$backendDirectory = Join-Path $repositoryRoot "backend"
$scraperDirectory = Join-Path $repositoryRoot "vextro_scraper"
$scraperScheduler = Join-Path $scraperDirectory "vextro_scraper\scheduler.py"
$runtimeDirectory = Join-Path $repositoryRoot ".runtime"
$schedulerLockPath = Join-Path $runtimeDirectory "scheduler.pid"

New-Item -ItemType Directory -Path $runtimeDirectory -Force | Out-Null

if (-not (Test-Path -LiteralPath $pythonPath)) {
    throw "VEXTRO Python environment is missing: $pythonPath"
}

if (-not (Test-Path -LiteralPath $scraperScheduler)) {
    throw "VEXTRO scraper scheduler is missing: $scraperScheduler"
}

if (Test-Path -LiteralPath $schedulerLockPath) {
    $existingProcessId = Get-Content -LiteralPath $schedulerLockPath -ErrorAction SilentlyContinue

    if (
        $existingProcessId -and
        (Get-Process -Id $existingProcessId -ErrorAction SilentlyContinue)
    ) {
        exit 0
    }
}

$PID | Set-Content -LiteralPath $schedulerLockPath

try {
    $backendHealthy = $false

    try {
        $healthResponse = Invoke-WebRequest `
            -UseBasicParsing `
            -Uri "http://127.0.0.1:8000/health" `
            -TimeoutSec 5
        $backendHealthy = $healthResponse.StatusCode -eq 200
    }
    catch {
        $backendHealthy = $false
    }

    if (-not $backendHealthy) {
        Start-Process `
            -FilePath $pythonPath `
            -ArgumentList @(
                "-m",
                "uvicorn",
                "app.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                "8000"
            ) `
            -WorkingDirectory $backendDirectory `
            -WindowStyle Hidden `
            -RedirectStandardOutput (Join-Path $runtimeDirectory "backend-output.log") `
            -RedirectStandardError (Join-Path $runtimeDirectory "backend-error.log")

        for ($attempt = 0; $attempt -lt 30; $attempt++) {
            Start-Sleep -Seconds 2

            try {
                $healthResponse = Invoke-WebRequest `
                    -UseBasicParsing `
                    -Uri "http://127.0.0.1:8000/health" `
                    -TimeoutSec 5

                if ($healthResponse.StatusCode -eq 200) {
                    $backendHealthy = $true
                    break
                }
            }
            catch {
                $backendHealthy = $false
            }
        }
    }

    if (-not $backendHealthy) {
        throw "VEXTRO backend did not become healthy within 60 seconds."
    }

    # Read the same environment-backed key as FastAPI without printing it.
    # An explicitly supplied scraper key remains authoritative.
    if (-not $env:INGESTION_API_KEY) {
        Push-Location $backendDirectory
        try {
            $env:INGESTION_API_KEY = & $pythonPath -c `
                "from app.core.config import settings; print(settings.ingestion_api_key or '')"
        }
        finally {
            Pop-Location
        }
    }

    if (-not $env:INGESTION_API_KEY) {
        throw "INGESTION_API_KEY is required for secure scraper delivery."
    }

    if (-not $env:VEXTRO_API_URL) {
        $env:VEXTRO_API_URL = "http://127.0.0.1:8000"
    }

    $env:VEXTRO_SCRAPE_TRIGGER = "scheduler"

    # Run the scheduler as a package module from the Scrapy project root.
    # Running scheduler.py directly makes Python search from the inner package
    # directory and can fail to resolve imports such as vextro_scraper.*.
    Push-Location $scraperDirectory
    try {
        & $pythonPath -u -m vextro_scraper.scheduler `
            *>> (Join-Path $runtimeDirectory "scheduler.log")

        if ($LASTEXITCODE -ne 0) {
            throw "VEXTRO scraper scheduler exited with code $LASTEXITCODE. See .runtime\scheduler.log."
        }
    }
    finally {
        Pop-Location
    }
}
finally {
    Remove-Item -LiteralPath $schedulerLockPath -Force -ErrorAction SilentlyContinue
}
