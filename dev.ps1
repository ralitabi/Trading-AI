# ============================================================
#  Trading AI - dev runner
#  Starts BOTH servers with auto-reload:
#    backend  : uvicorn --reload  -> restarts on any .py change
#    frontend : vite (HMR)        -> updates browser instantly on save
#  Usage: double-click dev.bat, or run  .\dev.ps1  in PowerShell
# ============================================================
$root = $PSScriptRoot

# Clean slate first. Two failure modes have bitten us before:
#  1. a leftover listener blocks the port (silent "nothing works")
#  2. killing a uvicorn parent leaves its worker child alive, serving STALE
#     code on the port — so sweep by command line, not just by port
Get-CimInstance Win32_Process -Filter "Name='python.exe' or Name='node.exe'" |
    Where-Object { $_.CommandLine -match 'uvicorn|vite' } |
    ForEach-Object {
        try { Stop-Process -Id $_.ProcessId -Force -ErrorAction Stop; Write-Host "  killed stale server pid $($_.ProcessId)" } catch {}
    }
foreach ($port in 8742, 8000, 5173) {
    $owners = Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue |
        Select-Object -ExpandProperty OwningProcess -Unique
    foreach ($owningPid in $owners) {
        try { Stop-Process -Id $owningPid -Force -ErrorAction Stop; Write-Host "  freed port $port (killed pid $owningPid)" } catch {}
    }
}

Write-Host ""
Write-Host "  Trading AI - starting dev environment" -ForegroundColor Cyan
Write-Host "  Backend  -> http://127.0.0.1:8742  (auto-reloads on backend changes)"
Write-Host "  Frontend -> http://localhost:5173  (hot-updates on frontend changes)"
Write-Host ""

# Backend: uvicorn watches backend/ and restarts itself on every file change.
# WATCHFILES_FORCE_POLLING: OneDrive folders swallow file-change notifications,
# so without polling the auto-reload silently never fires.
$backendCmd = "`$host.UI.RawUI.WindowTitle = 'Trading AI - BACKEND :8742'; Set-Location '$root\backend'; `$env:WATCHFILES_FORCE_POLLING='true'; python -m uvicorn main:app --reload --port 8742"
Start-Process powershell -ArgumentList '-NoExit', '-Command', $backendCmd

# Frontend: Vite HMR pushes changes to the browser without even refreshing
$frontendCmd = "`$host.UI.RawUI.WindowTitle = 'Trading AI - FRONTEND :5173'; Set-Location '$root\frontend'; npm run dev"
Start-Process powershell -ArgumentList '-NoExit', '-Command', $frontendCmd

# Open the dashboard once the frontend is up
Start-Sleep -Seconds 6
Start-Process "http://localhost:5173"
