# clean.ps1 — очистка артефактов сборки и временных файлов
$ErrorActionPreference = 'SilentlyContinue'

# 1. Папки сборки
$targets = @('build', 'dist', 'installer_output')
foreach ($t in $targets) {
    if (Test-Path $t) {
        Remove-Item -Recurse -Force $t
        Write-Host "Removed: $t" -ForegroundColor Yellow
    }
}

# 2. Кеши Python (__pycache__ и скомпилированные файлы)
Get-ChildItem -Path . -Directory -Filter '__pycache__' -Recurse |
    ForEach-Object {
        Remove-Item -Recurse -Force $_.FullName
        Write-Host "Removed: $($_.FullName)" -ForegroundColor DarkGray
    }

Get-ChildItem -Path . -File -Include '*.pyc', '*.pyo' -Recurse |
    Remove-Item -Force

# 3. Временные файлы базы данных (замки и бэкапы, если программа вылетала)
$db_temps = @('tabel_data.json.tmp*', 'tabel_data.json.lock', '*.log', '*.bak')
foreach ($pattern in $db_temps) {
    Get-ChildItem -Path . -File -Filter $pattern |
        ForEach-Object {
            Remove-Item -Force $_.FullName
            Write-Host "Removed: $($_.Name)" -ForegroundColor DarkYellow
        }
}

# 4. Очистка временных папок PyInstaller (_MEI*) в системе
Get-ChildItem -Path $env:TEMP -Directory -Filter '_MEI*' |
    Remove-Item -Recurse -Force

Write-Host "`nCleanup complete." -ForegroundColor Green