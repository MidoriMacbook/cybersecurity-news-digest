param([int]$Port = 8000, [switch]$Rebuild)

$ErrorActionPreference = 'Stop'
$projectDirectory = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectDirectory
$pythonExecutable = Join-Path $projectDirectory '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonExecutable)) {
    python -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Не удалось создать Python-окружение.' }
    & $pythonExecutable -m pip install -r apps/api/requirements.txt
    if ($LASTEXITCODE -ne 0) { throw 'Не удалось установить backend-зависимости.' }
}
$webDirectory = Join-Path $projectDirectory 'apps\web'
$staticDirectory = Join-Path $webDirectory 'out'
if ($Rebuild -or -not (Test-Path -LiteralPath $staticDirectory)) {
    Push-Location -LiteralPath $webDirectory
    try {
        pnpm install --frozen-lockfile
        if ($LASTEXITCODE -ne 0) { throw 'Не удалось установить frontend-зависимости.' }
        # Pass an actual empty value even in Windows PowerShell 5, where assigning
        # an empty environment variable otherwise removes it. This prevents a
        # developer .env.local from baking a separate API origin into the bundle.
        node (Join-Path $PSScriptRoot 'build-web.cjs')
        if ($LASTEXITCODE -ne 0) { throw 'Не удалось собрать интерфейс.' }
    } finally {
        Pop-Location
    }
}
$env:STATIC_DIR = $staticDirectory
Write-Host "Кибердайджест: http://127.0.0.1:$Port"
Write-Host 'Остановка: Ctrl+C. Учётные данные модели задаются переменными окружения.'
& $pythonExecutable -m uvicorn app.main:app --app-dir apps/api --host 127.0.0.1 --port $Port
exit $LASTEXITCODE
