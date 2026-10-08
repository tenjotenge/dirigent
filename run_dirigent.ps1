<#
.SYNOPSIS
    Starts Dirigent's backend and desktop frontend from one command.

.DESCRIPTION
    This Windows-first launcher is deliberately self-contained: it resolves the
    repository from its own location, reuses a healthy backend when possible,
    and only starts the frontend after the backend health endpoint responds.
    A macOS/Linux launcher can use the same four-stage contract later.
#>

param(
    [switch]$SkipFrontend,
    [switch]$BackendOnly
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSCommandPath
$VenvPath = Join-Path $ProjectRoot ".venv"
$PythonExe = Join-Path $VenvPath "Scripts\python.exe"
$BackendScript = Join-Path $ProjectRoot "run_backend.py"
$FrontendScript = Join-Path $ProjectRoot "run_frontend.bat"
$LogDir = Join-Path $ProjectRoot "logs"
$BackendLog = Join-Path $LogDir "backend.log"
$HealthUrl = "http://127.0.0.1:8000/health"
$HealthTimeoutSeconds = 30
$HealthPollMilliseconds = 500

function Write-Step([int]$Step, [string]$Message) {
    Write-Host "[$Step/4] $Message" -ForegroundColor Cyan
}

function Write-Info([string]$Message) {
    Write-Host $Message -ForegroundColor Gray
}

function Write-Success([string]$Message) {
    Write-Host $Message -ForegroundColor Green
}

function Write-LauncherError([string]$Message) {
    Write-Host "ERROR: $Message" -ForegroundColor Red
}

function Test-BackendHealth {
    try {
        $response = Invoke-RestMethod -Uri $HealthUrl -Method Get -TimeoutSec 2 -ErrorAction Stop
        return $response.status -eq "ok"
    } catch {
        return $false
    }
}

function Show-BackendLog {
    if (Test-Path $BackendLog) {
        Write-Host "Recent backend log output:" -ForegroundColor Yellow
        Get-Content -Path $BackendLog -Tail 30 | ForEach-Object {
            Write-Host "  $_" -ForegroundColor DarkGray
        }
    }
}

function Stop-ManagedBackend([System.Diagnostics.Process]$Process) {
    if ($null -ne $Process -and -not $Process.HasExited) {
        Write-Info "Stopping backend process..."
        # The launcher starts cmd.exe to merge stdout/stderr into one log. End
        # its process tree so the Python child cannot be left behind.
        & taskkill.exe /pid $Process.Id /t /f | Out-Null
        $Process.WaitForExit(5000) | Out-Null
    }
}

function Wait-ForBackendHealth([System.Diagnostics.Process]$Process) {
    $deadline = (Get-Date).AddSeconds($HealthTimeoutSeconds)
    $attempt = 0
    Write-Info "Polling $HealthUrl (timeout: $HealthTimeoutSeconds seconds)"

    while ((Get-Date) -lt $deadline) {
        $attempt++
        if (Test-BackendHealth) {
            Write-Success "Backend is healthy (attempt $attempt)"
            return $true
        }

        if ($Process.HasExited) {
            Write-LauncherError "Backend exited before becoming healthy (exit code $($Process.ExitCode))."
            return $false
        }

        Start-Sleep -Milliseconds $HealthPollMilliseconds
    }

    Write-LauncherError "Backend did not become healthy within $HealthTimeoutSeconds seconds."
    return $false
}

try {
    Set-Location $ProjectRoot

    Write-Step 1 "Activating virtual environment"
    if (-not (Test-Path $VenvPath)) {
        throw "Virtual environment not found at '$VenvPath'. Create it with: python -m venv .venv"
    }
    if (-not (Test-Path $PythonExe)) {
        throw "Python executable not found at '$PythonExe'. Recreate the .venv virtual environment."
    }
    $env:VIRTUAL_ENV = $VenvPath
    $env:Path = "$(Join-Path $VenvPath 'Scripts');$env:Path"
    Write-Success "Virtual environment found."

    Write-Step 2 "Starting backend"
    $backendAlreadyRunning = Test-BackendHealth
    $backendProcess = $null

    if ($backendAlreadyRunning) {
        Write-Success "Backend is already running and healthy; reusing it."
    } else {
        New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
        Clear-Content -Path $BackendLog -ErrorAction SilentlyContinue
        New-Item -ItemType File -Path $BackendLog -Force | Out-Null

        # cmd.exe supplies a single combined stdout/stderr stream in backend.log.
        $backendCommand = 'set "API_PORT=8000" && "{0}" "{1}" --no-reload >> "{2}" 2>&1' -f $PythonExe, $BackendScript, $BackendLog
        $backendProcess = Start-Process -FilePath "cmd.exe" -ArgumentList "/d", "/c", $backendCommand -WorkingDirectory $ProjectRoot -WindowStyle Hidden -PassThru
        Write-Success "Backend process started (PID: $($backendProcess.Id)); logging to $BackendLog"
    }

    Write-Step 3 "Waiting for backend health"
    if ($backendAlreadyRunning) {
        Write-Success "Backend is already healthy."
    } elseif (-not (Wait-ForBackendHealth $backendProcess)) {
        Stop-ManagedBackend $backendProcess
        Show-BackendLog
        exit 1
    }

    if ($SkipFrontend -or $BackendOnly) {
        Write-Step 4 "Frontend skipped"
        Write-Success "Dirigent backend is ready at $HealthUrl"
        if (-not $backendAlreadyRunning) {
            Write-Info "Press Ctrl+C to stop the backend."
            try {
                $backendProcess.WaitForExit()
            } finally {
                Stop-ManagedBackend $backendProcess
            }
        }
        exit 0
    }

    Write-Step 4 "Launching frontend"
    if (-not (Test-Path $FrontendScript)) {
        throw "Frontend launcher not found at '$FrontendScript'."
    }

    Write-Success "Dirigent is ready."
    # Wait for the frontend command so this launcher retains ownership of the
    # backend it started, while leaving externally managed backends untouched.
    $frontendCommand = 'call "{0}"' -f $FrontendScript
    $frontendProcess = Start-Process -FilePath "cmd.exe" -ArgumentList "/d", "/c", $frontendCommand -WorkingDirectory $ProjectRoot -PassThru
    try {
        $frontendProcess.WaitForExit()
        if ($frontendProcess.ExitCode -ne 0) {
            Write-LauncherError "Frontend exited with code $($frontendProcess.ExitCode)."
            exit $frontendProcess.ExitCode
        }
    } finally {
        if (-not $backendAlreadyRunning) {
            Stop-ManagedBackend $backendProcess
        }
    }
} catch {
    Write-LauncherError $_.Exception.Message
    exit 1
}
