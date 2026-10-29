[CmdletBinding()]
param(
    [ValidateRange(1, 65535)]
    [int]$Port = 8000,
    [switch]$NoBrowser,
    [switch]$SkipInstall,
    [switch]$Check
)

$ErrorActionPreference = 'Stop'
$projectRoot = $PSScriptRoot
$server = $null
$launchExitCode = 0

function Invoke-Checked {
    param([string]$Program, [string[]]$Arguments)
    & $Program @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$Program failed (exit code $LASTEXITCODE)."
    }
}

Push-Location -LiteralPath $projectRoot
try {
    $python = Join-Path $projectRoot '.venv\Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $python)) {
        if ($SkipInstall) {
            throw 'No virtual environment found. Run again without -SkipInstall.'
        }
        $created = $false
        foreach ($candidate in @('py', 'python', 'python3')) {
            $command = Get-Command $candidate -ErrorAction SilentlyContinue
            if (-not $command) { continue }
            $prefix = @()
            if ($candidate -eq 'py') { $prefix = @('-3') }
            try {
                & $command.Source @prefix -c 'import sys, venv; sys.exit(0 if sys.version_info >= (3, 11) else 1)' 2>$null
                if ($LASTEXITCODE -ne 0) { continue }
            }
            catch { continue }
            Write-Host 'Creating the project virtual environment...'
            Invoke-Checked -Program $command.Source -Arguments ($prefix + @('-m', 'venv', '.venv'))
            $created = $true
            break
        }
        if (-not $created) {
            throw 'Install Python 3.11+ with venv support, or create .venv with your Python executable first.'
        }
    }

    $npm = Get-Command npm.cmd -ErrorAction SilentlyContinue
    if (-not $npm) { throw 'Node.js and npm are required. Install Node.js 20.19+ or 22+, then reopen your terminal.' }

    # Do not stop or reuse a process belonging to another launch.
    $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, $Port)
    $listener.ExclusiveAddressUse = $true
    try { $listener.Start() }
    catch { throw "Port $Port is already in use. Stop the existing server or use .\launch.cmd -Port 8001." }
    finally { $listener.Stop() }

    $requirements = Join-Path $projectRoot 'requirements.lock'
    $pythonStamp = Join-Path $projectRoot '.venv\.dam-requirements.sha256'
    $pythonHash = (Get-FileHash -LiteralPath $requirements -Algorithm SHA256).Hash
    $pythonChanged = -not (Test-Path -LiteralPath $pythonStamp)
    if (-not $pythonChanged) { $pythonChanged = (Get-Content -LiteralPath $pythonStamp -Raw).Trim() -ne $pythonHash }
    if (-not $SkipInstall -and $pythonChanged) {
        Write-Host 'Installing backend dependencies...'
        Invoke-Checked -Program $python -Arguments @('-m', 'pip', 'install', '-r', 'requirements.lock')
        Set-Content -LiteralPath $pythonStamp -Value $pythonHash -Encoding ascii
    }
    Invoke-Checked -Program $python -Arguments @('-c', 'import fastapi, uvicorn, sqlalchemy, httpx, dotenv, itsdangerous')

    Push-Location -LiteralPath (Join-Path $projectRoot 'frontend')
    try {
        $nodeStamp = Join-Path (Get-Location).Path 'node_modules\.dam-package-lock.sha256'
        $nodeHash = (Get-FileHash -LiteralPath 'package-lock.json' -Algorithm SHA256).Hash
        $nodeChanged = -not (Test-Path -LiteralPath $nodeStamp)
        if (-not $nodeChanged) { $nodeChanged = (Get-Content -LiteralPath $nodeStamp -Raw).Trim() -ne $nodeHash }
        if (-not $SkipInstall -and $nodeChanged) {
            Write-Host 'Installing dashboard dependencies...'
            Invoke-Checked -Program $npm.Source -Arguments @('ci')
            Set-Content -LiteralPath $nodeStamp -Value $nodeHash -Encoding ascii
        }
        Write-Host 'Building the dashboard...'
        Invoke-Checked -Program $npm.Source -Arguments @('run', 'build')
    }
    finally { Pop-Location }

    if (-not (Test-Path -LiteralPath (Join-Path $projectRoot '.env'))) {
        Invoke-Checked -Program $python -Arguments @('manage.py', 'init')
    }

    $stdoutLog = Join-Path $projectRoot '.venv\dam-server.log'
    $stderrLog = Join-Path $projectRoot '.venv\dam-server.err.log'
    $url = "http://127.0.0.1:$Port"
    Write-Host 'Starting DAM...'
    $server = Start-Process -FilePath $python -ArgumentList @(
        '-m', 'uvicorn', 'backend.dam.main:create_app', '--factory',
        '--host', '127.0.0.1', '--port', "$Port"
    ) -WorkingDirectory $projectRoot -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput $stdoutLog -RedirectStandardError $stderrLog

    $ready = $false
    $deadline = [DateTime]::UtcNow.AddSeconds(30)
    while ([DateTime]::UtcNow -lt $deadline) {
        if ($server.HasExited) {
            throw "Server exited during startup. See $stderrLog"
        }
        try {
            $health = Invoke-RestMethod -Uri "$url/health" -TimeoutSec 1
            if ($health.status -eq 'ok') { $ready = $true; break }
        }
        catch { }
        Start-Sleep -Milliseconds 300
    }
    if (-not $ready) { throw "Server did not become ready within 30 seconds. See $stderrLog" }

    Write-Host "Dashboard: $url" -ForegroundColor Green
    Write-Host "API docs:  $url/docs"
    Write-Host 'Sign in as admin or reviewer using the passwords in .env.'
    Write-Host "Server logs: $stdoutLog and $stderrLog"
    if ($Check) {
        $dashboard = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 5
        if ($dashboard.StatusCode -ne 200 -or $dashboard.Content -notmatch 'id="root"') {
            throw 'The dashboard did not serve the built frontend.'
        }
        Write-Host 'Launch check passed; stopping the test server.' -ForegroundColor Green
    }
    else {
        if (-not $NoBrowser) {
            try { Start-Process -FilePath $url }
            catch { Write-Warning "Could not open a browser automatically. Open $url manually." }
        }
        Write-Host 'Keep this terminal open. Press Ctrl+C to stop DAM.'
        while (-not $server.HasExited) { Start-Sleep -Milliseconds 500 }
        $server.WaitForExit()
        if ($server.ExitCode -ne 0) { throw "Server stopped unexpectedly. See $stderrLog" }
    }
}
catch {
    Write-Host "Launch failed: $($_.Exception.Message)" -ForegroundColor Red
    $launchExitCode = 1
}
finally {
    if ($null -ne $server -and -not $server.HasExited) {
        Stop-Process -Id $server.Id -ErrorAction SilentlyContinue
        $server.WaitForExit()
    }
    Pop-Location
}
exit $launchExitCode
