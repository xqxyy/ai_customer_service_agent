param(
    [int]$Port = 8001,
    [switch]$StopDocker
)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $ProjectRoot

function Invoke-NativeCommand($FilePath, [string[]]$Arguments) {
    $oldErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        & $FilePath @Arguments
        $script:LastNativeExitCode = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $oldErrorActionPreference
    }
}

Write-Host "Stopping AI Customer Service Agent" -ForegroundColor Yellow

$connections = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if ($connections) {
    $pids = $connections | Select-Object -ExpandProperty OwningProcess -Unique
    foreach ($pidValue in $pids) {
        try {
            Stop-Process -Id $pidValue -Force
            Write-Host "[OK] Stopped backend process on port $Port`: $pidValue" -ForegroundColor Green
        } catch {
            Write-Host "[WARN] Could not stop process $pidValue`: $($_.Exception.Message)" -ForegroundColor Yellow
        }
    }
} else {
    Write-Host "[OK] No backend process is listening on port $Port" -ForegroundColor Green
}

if ($StopDocker) {
    Invoke-NativeCommand "docker" @("compose", "stop")
    if ($script:LastNativeExitCode -ne 0) {
        throw "docker compose stop failed."
    }
    Write-Host "[OK] Docker Compose dependencies stopped. Volumes are preserved." -ForegroundColor Green
} else {
    Write-Host "[INFO] Docker containers are still running. To stop them too, run: stop_project.bat -StopDocker"
}
