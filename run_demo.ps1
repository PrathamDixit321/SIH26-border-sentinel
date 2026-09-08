# Border Sentinel AI — Complete Full-Stack Runner
Write-Host "=================================================================" -ForegroundColor Cyan
Write-Host "   BORDER SENTINEL AI // DEFENSE C2 PLATFORM (SIH26187)          " -ForegroundColor Yellow
Write-Host "=================================================================" -ForegroundColor Cyan

$root = $PSScriptRoot
$env:PYTHONPATH = $root
$env:Path = [System.Environment]::GetEnvironmentVariable("Path","User") + ";" + [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";C:\Users\Komal\.local\bin"

Write-Host "[1/2] Starting FastAPI Backend on http://localhost:8000 ..." -ForegroundColor Green
$backendJob = Start-Process -FilePath "$root\backend\.venv\Scripts\python.exe" -ArgumentList "-m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload" -WorkingDirectory $root -PassThru

Start-Sleep -Seconds 2

Write-Host "[2/2] Starting React C2 Dashboard on http://localhost:5173 ..." -ForegroundColor Green
$frontendJob = Start-Process -FilePath "npm.cmd" -ArgumentList "run dev" -WorkingDirectory "$root\dashboard" -PassThru

Write-Host ""
Write-Host "=================================================================" -ForegroundColor Cyan
Write-Host " SYSTEM ONLINE & OPERATIONAL                                     " -ForegroundColor Green
Write-Host "   Dashboard URL:  http://localhost:5173                         " -ForegroundColor White
Write-Host "   API Swagger:    http://localhost:8000/docs                    " -ForegroundColor White
Write-Host "   Live Video:     http://localhost:8000/api/stream              " -ForegroundColor White
Write-Host "=================================================================" -ForegroundColor Cyan
Write-Host "Press Ctrl+C or close this terminal to stop both servers."

try {
    Wait-Process -Id $backendJob.Id, $frontendJob.Id
} finally {
    Stop-Process -Id $backendJob.Id -ErrorAction SilentlyContinue
    Stop-Process -Id $frontendJob.Id -ErrorAction SilentlyContinue
}