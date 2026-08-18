param(
    [int]$Port = 8001,
    [string]$PythonPath = "",
    [switch]$RebuildRag,
    [switch]$RunRagEval,
    [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$DefaultPython = "C:\Users\11932\.conda\envs\langchain1.2\python.exe"

function Write-Step($Message) {
    Write-Host ""
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Write-Ok($Message) {
    Write-Host "[OK] $Message" -ForegroundColor Green
}

function Write-Warn($Message) {
    Write-Host "[WARN] $Message" -ForegroundColor Yellow
}

function Resolve-Python {
    if ($PythonPath -and (Test-Path -LiteralPath $PythonPath)) {
        return (Resolve-Path -LiteralPath $PythonPath).Path
    }

    if (Test-Path -LiteralPath $DefaultPython) {
        return $DefaultPython
    }

    $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
    if ($pythonCommand) {
        return $pythonCommand.Source
    }

    throw "Python was not found. Activate the conda env first, or pass -PythonPath."
}

function Invoke-ProjectPython($Python, [string[]]$Arguments) {
    Invoke-NativeCommand $Python $Arguments
    if ($script:LastNativeExitCode -ne 0) {
        throw "Command failed: $Python $($Arguments -join ' ')"
    }
}

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

function Test-DockerReady {
    try {
        docker info --format "{{.ServerVersion}}" *> $null
        return $true
    } catch {
        return $false
    }
}

function Start-DockerDesktop {
    if (Test-DockerReady) {
        Write-Ok "Docker Engine is running"
        return
    }

    $dockerDesktop = "C:\Program Files\Docker\Docker\Docker Desktop.exe"
    if (-not (Test-Path -LiteralPath $dockerDesktop)) {
        throw "Docker Engine is not running, and Docker Desktop was not found. Open Docker Desktop manually and retry."
    }

    Write-Warn "Docker Engine is not running. Starting Docker Desktop..."
    Start-Process -FilePath $dockerDesktop -WindowStyle Hidden | Out-Null

    for ($i = 1; $i -le 36; $i++) {
        Start-Sleep -Seconds 5
        if (Test-DockerReady) {
            Write-Ok "Docker Engine is ready"
            return
        }
        Write-Host "Waiting for Docker Engine... ($i/36)"
    }

    throw "Docker Engine startup timed out. Wait until Docker Desktop shows Engine running, then retry."
}

function Start-ComposeDependencies {
    Invoke-NativeCommand "docker" @("compose", "up", "-d")
    if ($script:LastNativeExitCode -eq 0) {
        return
    }

    $knownContainers = @(
        "ai-customer-service-postgres",
        "ai-customer-service-milvus-etcd",
        "ai-customer-service-milvus-minio",
        "ai-customer-service-milvus"
    )

    $existing = @()
    foreach ($name in $knownContainers) {
        $containerId = docker ps -a --filter "name=^/$name$" --format "{{.ID}}"
        if ($containerId) {
            $existing += $name
        }
    }

    if ($existing.Count -eq $knownContainers.Count) {
        Write-Warn "docker compose up failed, but existing project containers were found. Starting them directly..."
        Invoke-NativeCommand "docker" (@("start") + $knownContainers)
        if ($script:LastNativeExitCode -eq 0) {
            return
        }
    }

    throw "docker compose up -d failed. Check Docker Desktop and container name conflicts."
}

function Wait-Port($HostName, [int]$TargetPort, [int]$TimeoutSeconds = 90) {
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)

    while ((Get-Date) -lt $deadline) {
        try {
            $client = [System.Net.Sockets.TcpClient]::new()
            $async = $client.BeginConnect($HostName, $TargetPort, $null, $null)
            $connected = $async.AsyncWaitHandle.WaitOne(1000, $false)
            if ($connected) {
                $client.EndConnect($async)
                $client.Close()
                return $true
            }
            $client.Close()
        } catch {
        }

        Start-Sleep -Seconds 2
    }

    return $false
}

function Test-PortInUse([int]$TargetPort) {
    $connection = Get-NetTCPConnection -LocalPort $TargetPort -State Listen -ErrorAction SilentlyContinue
    return $null -ne $connection
}

function Test-WorkbenchReady([int]$TargetPort) {
    try {
        $state = Invoke-RestMethod "http://127.0.0.1:$TargetPort/workbench/state" -TimeoutSec 5
        return $state.PSObject.Properties.Name -contains "prompt_templates"
    } catch {
        return $false
    }
}

Set-Location $ProjectRoot
New-Item -ItemType Directory -Force -Path (Join-Path $ProjectRoot "tmp") | Out-Null
if (-not $env:COMPOSE_PROJECT_NAME) {
    $env:COMPOSE_PROJECT_NAME = "aiagent"
}

Write-Host "AI Customer Service Agent startup" -ForegroundColor Green
Write-Host "Project root: $ProjectRoot"
Write-Host "Compose project: $env:COMPOSE_PROJECT_NAME"

Write-Step "Checking Python"
$Python = Resolve-Python
Write-Ok "Python: $Python"
Invoke-ProjectPython $Python @("-c", "import sys; print('Python executable:', sys.executable)")

Write-Step "Starting Docker dependencies"
Start-DockerDesktop
Start-ComposeDependencies

Write-Step "Waiting for PostgreSQL and Milvus"
if (-not (Wait-Port "127.0.0.1" 56433 120)) {
    throw "PostgreSQL port 56433 is not ready. Run docker compose ps for details."
}
Write-Ok "PostgreSQL: localhost:56433"

if (-not (Wait-Port "127.0.0.1" 19531 120)) {
    throw "Milvus port 19531 is not ready. Run docker compose ps for details."
}
Write-Ok "Milvus: localhost:19531"

Write-Step "Running database migrations"
Invoke-ProjectPython $Python @("-m", "alembic", "upgrade", "head")
Write-Ok "Alembic upgraded to head"

if ($RebuildRag) {
    Write-Step "Rebuilding RAG knowledge base"
    Invoke-ProjectPython $Python @("-m", "scripts.build_authoritative_knowledge")
    Invoke-ProjectPython $Python @("-m", "scripts.prepare_documents")
    Invoke-ProjectPython $Python @("-m", "scripts.build_chunks")
    Invoke-ProjectPython $Python @("-m", "scripts.ingest_knowledge_base")
    Write-Ok "RAG data was rebuilt and ingested into Milvus"
    $RunRagEval = $true
}

if ($RunRagEval) {
    Write-Step "Running RAG evaluation"
    Invoke-ProjectPython $Python @("-m", "scripts.run_rag_eval")
}

Write-Step "Starting FastAPI"
if (Test-WorkbenchReady $Port) {
    Write-Ok "Backend is already running: http://127.0.0.1:$Port/"
} elseif (Test-PortInUse $Port) {
    throw "Port $Port is already in use by another service. Stop it, or run start_project.bat -Port 8010."
} else {
    $outLog = Join-Path $ProjectRoot "tmp\uvicorn-$Port.out.log"
    $errLog = Join-Path $ProjectRoot "tmp\uvicorn-$Port.err.log"
    $arguments = @("-m", "uvicorn", "backend.app.main:app", "--port", "$Port")

    Start-Process `
        -FilePath $Python `
        -ArgumentList $arguments `
        -WorkingDirectory $ProjectRoot `
        -WindowStyle Hidden `
        -RedirectStandardOutput $outLog `
        -RedirectStandardError $errLog | Out-Null

    $ready = $false
    for ($i = 1; $i -le 40; $i++) {
        Start-Sleep -Seconds 2
        if (Test-WorkbenchReady $Port) {
            $ready = $true
            break
        }
    }

    if (-not $ready) {
        Write-Host "FastAPI stderr log:" -ForegroundColor Yellow
        if (Test-Path -LiteralPath $errLog) {
            Get-Content -LiteralPath $errLog -Tail 80
        }
        throw "FastAPI startup failed or timed out."
    }

    Write-Ok "Backend started: http://127.0.0.1:$Port/"
    Write-Host "stdout log: $outLog"
    Write-Host "stderr log: $errLog"
}

Write-Step "Health check"
$health = Invoke-RestMethod "http://127.0.0.1:$Port/health" -TimeoutSec 20
Write-Host ("health.status = " + $health.status)
Write-Host ("database.ok   = " + $health.database.ok)
Write-Host ("milvus.ok     = " + $health.milvus.ok)

if (-not $NoBrowser) {
    Start-Process "http://127.0.0.1:$Port/"
}

Write-Host ""
Write-Host "Startup complete" -ForegroundColor Green
Write-Host "Workbench: http://127.0.0.1:$Port/"
Write-Host "Swagger:   http://127.0.0.1:$Port/docs"
Write-Host "Health:    http://127.0.0.1:$Port/health"
Write-Host ""
Write-Host "Useful commands:"
Write-Host "  start_project.bat -RebuildRag  # rebuild RAG after changing knowledge files"
Write-Host "  start_project.bat -RunRagEval  # run RAG evaluation during startup"
Write-Host "  start_project.bat -Port 8010   # use another backend port"
