$ErrorActionPreference = "Stop"

Set-Location $PSScriptRoot

function Stop-SteamDesktop {
    $procs = Get-Process SteamToolsDesktop -ErrorAction SilentlyContinue
    foreach ($p in $procs) {
        try {
            Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue
        } catch {
            # Ignorar procesos que cierren entre consultas.
        }
    }
}

$exePath = Join-Path $PSScriptRoot "dist\SteamToolsDesktop.exe"
if (-not (Test-Path $exePath)) {
    Write-Output "SMOKE_FAIL: Ejecutable no encontrado en dist\\SteamToolsDesktop.exe"
    exit 1
}

Stop-SteamDesktop

$proc = Start-Process -FilePath $exePath -PassThru
$ok = $false
$deadline = (Get-Date).AddSeconds(20)

while ((Get-Date) -lt $deadline) {
    try {
        $resp = Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:8080/api/config" -TimeoutSec 1
        if ($resp.StatusCode -eq 200) {
            $ok = $true
            break
        }
    } catch {
        # Retry until timeout.
    }
}

if (-not $ok) {
    Stop-SteamDesktop
    Write-Output "SMOKE_FAIL: API local no respondio en /api/config"
    exit 1
}

try {
    Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
} catch {
    # Ignorar si ya terminó.
}

for ($i = 0; $i -lt 8; $i++) {
    Stop-SteamDesktop
    $remaining = @(Get-Process SteamToolsDesktop -ErrorAction SilentlyContinue).Count
    if ($remaining -eq 0) {
        break
    }
    Start-Sleep -Milliseconds 400
}

$remaining = @(Get-Process SteamToolsDesktop -ErrorAction SilentlyContinue).Count
if ($remaining -ne 0) {
    Write-Output "SMOKE_FAIL: Quedaron procesos SteamToolsDesktop activos ($remaining)"
    exit 1
}

Write-Output "SMOKE_OK: Ejecutable inicia, responde API local y cierra limpio"
exit 0