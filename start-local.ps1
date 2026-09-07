$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = Join-Path $root ".venv\Scripts\python.exe"
$web = Join-Path $root "apps\web"
$mongo = $null
$mongoExe = "C:\Program Files\MongoDB\Server\8.0\bin\mongod.exe"

if (-not (Test-Path $python)) {
    Write-Host "Creating Python environment..."
    python -m venv (Join-Path $root ".venv")
    & $python -m pip install -e "$root[dev]"
}

& $python -c "import agentprobe" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Installing backend dependencies..."
    & $python -m pip install -e "$root[dev]"
}

if (-not (Test-Path (Join-Path $web "node_modules"))) {
    Write-Host "Installing dashboard dependencies..."
    & npm.cmd install --prefix $web
}

$env:AGENTPROBE_STORAGE_BACKEND = "memory"
$env:AGENTPROBE_TEMPLATE_BACKEND = "mongodb"
$env:NEXT_PUBLIC_API_URL = "http://localhost:8000/api/v1"

$mongoListening = Get-NetTCPConnection -State Listen -LocalPort 27017 -ErrorAction SilentlyContinue
if (-not $mongoListening) {
    if (-not (Test-Path $mongoExe)) {
        throw "MongoDB is not installed at $mongoExe"
    }
    $mongoData = Join-Path $root "data\mongodb"
    if (-not (Test-Path $mongoData)) {
        New-Item -ItemType Directory -Path $mongoData | Out-Null
    }
    Write-Host "Starting local MongoDB..."
    $mongo = Start-Process -FilePath $mongoExe -ArgumentList @(
        "--dbpath", $mongoData, "--bind_ip", "127.0.0.1", "--port", "27017", "--quiet"
    ) -WorkingDirectory $root -NoNewWindow -PassThru
    Start-Sleep -Seconds 2
}

Write-Host "Starting AgentProbe without Docker..."
$api = Start-Process -FilePath $python -ArgumentList @(
    "-m", "uvicorn", "agentprobe.main:app",
    "--app-dir", (Join-Path $root "apps\api"),
    "--host", "127.0.0.1", "--port", "8000"
) -WorkingDirectory $root -NoNewWindow -PassThru

$dashboard = Start-Process -FilePath "npm.cmd" -ArgumentList @(
    "run", "dev"
) -WorkingDirectory $web -NoNewWindow -PassThru

Write-Host ""
Write-Host "Dashboard:       http://localhost:3000"
Write-Host "Test chatbot:    http://localhost:8000/demo"
Write-Host "API docs:        http://localhost:8000/docs"
Write-Host "Storage:         in memory (resets when stopped)"
Write-Host "Press Ctrl+C to stop both services."

try {
    while (-not $api.HasExited -and -not $dashboard.HasExited) {
        Start-Sleep -Seconds 1
    }
}
finally {
    if (-not $api.HasExited) { Stop-Process -Id $api.Id -Force }
    if (-not $dashboard.HasExited) { Stop-Process -Id $dashboard.Id -Force }
    if ($mongo -and -not $mongo.HasExited) { Stop-Process -Id $mongo.Id -Force }
}
