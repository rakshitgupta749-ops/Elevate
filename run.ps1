<#
.SYNOPSIS
    Runs both Backend (FastAPI/uvicorn) and Frontend (Vite/React) for Elevate on Windows.

.DESCRIPTION
    Activates the Python virtual environment (if present), starts the backend server,
    starts the frontend dev server, displays their local URLs, and handles clean
    termination of both processes when Ctrl+C is pressed.

.PARAMETER SeparateWindows
    Optional switch. If specified, opens backend and frontend in separate console windows.
    Defaults to running both in the current terminal (matching run.sh behavior).

.EXAMPLE
    .\run.ps1
    Runs both servers in the current terminal window.

.EXAMPLE
    .\run.ps1 -SeparateWindows
    Runs backend and frontend in separate dedicated console windows.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File .\run.ps1
    Runs the script bypassing any local execution policy restrictions.
#>

[CmdletBinding()]
param(
    [switch]$SeparateWindows
)

# Set working directory to the project root where this script resides
Set-Location -Path $PSScriptRoot

Write-Host "=== Elevate Project Launcher (Windows) ===" -ForegroundColor Cyan

# 1. Activate Python virtual environment if found
$venvActivatePaths = @(
    (Join-Path $PSScriptRoot "venv\Scripts\Activate.ps1"),
    (Join-Path $PSScriptRoot ".venv\Scripts\Activate.ps1"),
    (Join-Path $PSScriptRoot "backend\venv\Scripts\Activate.ps1")
)

$venvFound = $false
foreach ($activateScript in $venvActivatePaths) {
    if (Test-Path $activateScript) {
        Write-Host "Activating virtual environment: $activateScript" -ForegroundColor DarkCyan
        try {
            . $activateScript
            $venvFound = $true
            break
        } catch {
            Write-Warning "Could not activate $activateScript : $_"
        }
    }
}

# 2. Resolve Python executable
# Prioritize virtual environment python, fall back to system python
$pythonExe = "python"
$pythonCandidates = @(
    (Join-Path $PSScriptRoot "venv\Scripts\python.exe"),
    (Join-Path $PSScriptRoot ".venv\Scripts\python.exe"),
    (Join-Path $PSScriptRoot "backend\venv\Scripts\python.exe")
)
foreach ($candidate in $pythonCandidates) {
    if (Test-Path $candidate) {
        $pythonExe = $candidate
        break
    }
}

# 3. Resolve npm executable on Windows (npm.cmd)
$npmCommand = Get-Command "npm.cmd" -ErrorAction SilentlyContinue
if (-not $npmCommand) {
    $npmCommand = Get-Command "npm" -ErrorAction SilentlyContinue
}
$npmExe = if ($npmCommand) { $npmCommand.Source } else { "npm.cmd" }

# Helper to terminate a process and its child processes cleanly (e.g. node.exe, reloader)
function Stop-ProcessTree([int]$procId) {
    if ($procId -gt 0) {
        try {
            # Use taskkill with /T (tree) and /F (force) to ensure child workers and node are terminated
            Start-Process taskkill.exe -ArgumentList "/PID $procId /T /F" -WindowStyle Hidden -Wait -ErrorAction SilentlyContinue
        } catch {
            try {
                Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
            } catch {}
        }
    }
}

$backendDir = Join-Path $PSScriptRoot "backend"
$frontendDir = Join-Path $PSScriptRoot "frontend"

Write-Host "Starting Backend server (FastAPI)..." -ForegroundColor Cyan
$backendArgs = @{
    FilePath         = $pythonExe
    ArgumentList     = "-m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"
    WorkingDirectory = $backendDir
    PassThru         = $true
}
if (-not $SeparateWindows) {
    $backendArgs["NoNewWindow"] = $true
}
$backendProcess = Start-Process @backendArgs

Write-Host "Starting Frontend server (Vite)..." -ForegroundColor Cyan
$frontendArgs = @{
    FilePath         = $npmExe
    ArgumentList     = "run dev"
    WorkingDirectory = $frontendDir
    PassThru         = $true
}
if (-not $SeparateWindows) {
    $frontendArgs["NoNewWindow"] = $true
}
$frontendProcess = Start-Process @frontendArgs

Write-Host ""
Write-Host "==========================================" -ForegroundColor Green
Write-Host " Elevate - Both servers are running!" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Green
Write-Host " Backend API: http://127.0.0.1:8000" -ForegroundColor White
Write-Host " Frontend:    http://localhost:5173" -ForegroundColor White
Write-Host " Press Ctrl+C to stop both servers." -ForegroundColor Yellow
Write-Host "==========================================" -ForegroundColor Green
Write-Host ""

# 4. Monitor processes and wait for exit or Ctrl+C
try {
    while ($true) {
        if ($backendProcess.HasExited) {
            Write-Host "Backend server stopped (Exit code: $($backendProcess.ExitCode))." -ForegroundColor Yellow
            break
        }
        if ($frontendProcess.HasExited) {
            Write-Host "Frontend server stopped (Exit code: $($frontendProcess.ExitCode))." -ForegroundColor Yellow
            break
        }
        Start-Sleep -Milliseconds 500
    }
}
finally {
    Write-Host "`nShutting down servers..." -ForegroundColor Yellow
    if ($backendProcess -and -not $backendProcess.HasExited) {
        Stop-ProcessTree $backendProcess.Id
    }
    if ($frontendProcess -and -not $frontendProcess.HasExited) {
        Stop-ProcessTree $frontendProcess.Id
    }
    Write-Host "All servers stopped." -ForegroundColor Green
}
