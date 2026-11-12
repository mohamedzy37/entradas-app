# Genera el fichero .env del despliegue con secretos aleatorios criptograficos.
# Uso (desde la raiz del repo):
#   powershell -ExecutionPolicy Bypass -File scripts\generar-env.ps1
# No sobrescribe un .env existente salvo con -Force.

param([switch]$Force)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$envFile = Join-Path $root '.env'

if ((Test-Path $envFile) -and -not $Force) {
    Write-Host ".env ya existe. Usa -Force para regenerarlo (cambia los secretos)." -ForegroundColor Yellow
    Write-Host "OJO: con -Force cambia POSTGRES_PASSWORD y la BD existente dejara de aceptar" -ForegroundColor Yellow
    Write-Host "la conexion; habria que borrar sus datos con: docker compose down -v" -ForegroundColor Yellow
    exit 0
}

function New-Secret([int]$bytes = 32) {
    $buffer = New-Object byte[] $bytes
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    $rng.GetBytes($buffer)
    $rng.Dispose()
    return ($buffer | ForEach-Object { $_.ToString('x2') }) -join ''
}

$content = @"
# Generado por scripts/generar-env.ps1 el $(Get-Date -Format 'yyyy-MM-dd HH:mm').
# NO subir al repositorio (esta en .gitignore).
POSTGRES_PASSWORD=$(New-Secret 24)
JWT_SECRET=$(New-Secret 32)
JWT_REFRESH_SECRET=$(New-Secret 32)

PUBLIC_ORIGIN=https://localhost
HTTP_PORT=80
HTTPS_PORT=443
TLS_CN=localhost

# Login con Google (opcional, ver README). Vacio = desactivado.
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=

SEED_DEMO_DATA=true
"@

# UTF-8 sin BOM: docker compose no entiende el BOM.
[IO.File]::WriteAllText($envFile, $content.Replace("`r`n", "`n"), (New-Object System.Text.UTF8Encoding($false)))
Write-Host "Creado $envFile con secretos nuevos." -ForegroundColor Green
