# Border Sentinel AI — Complete Unified Full-Stack Runner
param(
    [switch]$RunPipeline,
    [string]$BeforeVideo = "Yash Raj 1.mp4",
    [string]$AfterVideo = "Yash Raj 2.mp4",
    [switch]$NoPreview
)

Write-Host "=================================================================" -ForegroundColor Cyan
Write-Host "   BORDER SENTINEL AI // DEFENSE C2 PLATFORM (SIH26187)          " -ForegroundColor Yellow
Write-Host "=================================================================" -ForegroundColor Cyan

$root = $PSScriptRoot
$env:PYTHONPATH = $root

# Dynamically resolve Python executable
$pythonExe = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $pythonExe -and (Test-Path "$root\backend\.venv\Scripts\python.exe")) {
    $pythonExe = "$root\backend\.venv\Scripts\python.exe"
}
if (-not $pythonExe -and (Test-Path "$root\.venv\Scripts\python.exe")) {
    $pythonExe = "$root\.venv\Scripts\python.exe"
}
if (-not $pythonExe) {
    $pythonExe = "python"
}

Write-Host "Using Python: $pythonExe" -ForegroundColor DarkGray

# Resolve NPM executable
$npmCmd = (Get-Command npm.cmd -ErrorAction SilentlyContinue).Source
if (-not $npmCmd) {
    $npmCmd = (Get-Command npm -ErrorAction SilentlyContinue).Source
}
if (-not $npmCmd) {
    $npmCmd = "npm"
}

Write-Host "[1/2] Starting FastAPI Backend on http://localhost:8000 ..." -ForegroundColor Green
$backendJob = Start-Process -FilePath $pythonExe -ArgumentList "-m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload" -WorkingDirectory $root -PassThru

Start-Sleep -Seconds 2

Write-Host "[2/2] Starting React C2 Dashboard on http://localhost:5173 ..." -ForegroundColor Green
$frontendJob = Start-Process -FilePath $npmCmd -ArgumentList "run dev" -WorkingDirectory "$root\dashboard" -PassThru

$pipelineJob = $null
if ($RunPipeline) {
    Start-Sleep -Seconds 2
    Write-Host "[3/3] Launching Stage 4 Computer Vision Surveillance Pipeline..." -ForegroundColor Cyan
    $previewFlag = if ($NoPreview) { "--no-preview" } else { "" }
    $pipelineArgs = "step4_classifier_alerts.py `"$BeforeVideo`" `"$AfterVideo`" $previewFlag"
    $pipelineJob = Start-Process -FilePath $pythonExe -ArgumentList $pipelineArgs -WorkingDirectory $root -PassThru
}

Write-Host ""
Write-Host "=================================================================" -ForegroundColor Cyan
Write-Host " SYSTEM ONLINE & OPERATIONAL                                     " -ForegroundColor Green
Write-Host "   Dashboard URL:  http://localhost:5173                         " -ForegroundColor White
Write-Host "   API Swagger:    http://localhost:8000/docs                    " -ForegroundColor White
Write-Host "   Live Video:     http://localhost:8000/api/stream              " -ForegroundColor White
if ($RunPipeline) {
    Write-Host "   CV Pipeline:    Active (streaming to C2 Dashboard)            " -ForegroundColor Yellow
}
Write-Host "=================================================================" -ForegroundColor Cyan
Write-Host "Press Ctrl+C or close this terminal to stop running servers."

try {
    if ($pipelineJob) {
        Wait-Process -Id $backendJob.Id, $frontendJob.Id, $pipelineJob.Id
    } else {
        Wait-Process -Id $backendJob.Id, $frontendJob.Id
    }
} finally {
    Stop-Process -Id $backendJob.Id -ErrorAction SilentlyContinue
    Stop-Process -Id $frontendJob.Id -ErrorAction SilentlyContinue
    if ($pipelineJob) {
        Stop-Process -Id $pipelineJob.Id -ErrorAction SilentlyContinue
    }
}