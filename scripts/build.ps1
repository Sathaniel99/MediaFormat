#Requires -Version 5.1
<#
.SYNOPSIS
    Compila MediaFormat con PyInstaller.

.DESCRIPTION
    Politica del proyecto: TODO fix o feature termina con una compilacion.
    El agente NO decide la version: el usuario elige entre rebuild de la version
    actual o subir version con scripts/bump_version.py y volver a compilar.

.PARAMETER Version
    Version esperada. Si no coincide con app/version.py el script falla a
    proposito, para que el numero del ejecutable nunca mienta.

.PARAMETER Windowed
    Compila sin consola. Usar cuando la UI Qt este lista (Fase 2).

.PARAMETER SkipTests
    Omite los tests. Solo para una emergencia explicita del usuario.

.PARAMETER Clean
    Borra build/ y dist/ antes de compilar.

.PARAMETER Onedir
    Compila en carpeta (--onedir) en vez de un solo .exe (--onefile). Sirve para
    comparar tamano y arranque; el modo por defecto sigue siendo onefile.
#>
[CmdletBinding()]
param(
    [string]$Version,
    [switch]$Windowed,
    [switch]$SkipTests,
    [switch]$Clean,
    [switch]$Onedir
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Push-Location $root
try {
    $python = Join-Path $root ".venv\Scripts\python.exe"
    if (-not (Test-Path $python)) {
        throw "No se encontro .venv. Ejecuta la preparacion del entorno antes de compilar."
    }

    $sourceVersion = (& $python -c "from app.version import __version__; print(__version__)").Trim()
    if (-not $sourceVersion) {
        throw "No se pudo leer app/version.py"
    }
    if ($Version -and $Version -ne $sourceVersion) {
        throw "La version pedida ($Version) no coincide con app/version.py ($sourceVersion). Usa scripts/bump_version.py <patch|minor|major> y vuelve a compilar."
    }
    if ($Version -and $Version -notmatch '^\d+\.\d+\.\d+$') {
        throw "Version invalida: $Version (se espera x.y.z)"
    }
    $buildVersion = $sourceVersion

    Write-Host "MediaFormat $buildVersion" -ForegroundColor Cyan
    Write-Host "Raiz: $root" -ForegroundColor DarkGray

    if ($Clean) {
        Write-Host "[clean] borrando build/ y dist/" -ForegroundColor Yellow
        Remove-Item (Join-Path $root "build"), (Join-Path $root "dist") -Recurse -Force -ErrorAction SilentlyContinue
    }

    if (-not $SkipTests) {
        Write-Host "[1/3] Tests" -ForegroundColor Cyan
        & $python -m unittest discover -s tests -t .
        if ($LASTEXITCODE -ne 0) {
            throw "Los tests fallaron. No se compila."
        }
    }
    else {
        Write-Host "[1/3] Tests omitidos (-SkipTests)" -ForegroundColor Yellow
    }

    Write-Host "[2/3] PyInstaller" -ForegroundColor Cyan
    $mode = if ($Onedir) { "onedir" } else { "onefile" }
    $exeName = "MediaFormat-$buildVersion"
    $versionFile = Join-Path $root "build\version_info.txt"
    & $python (Join-Path $root "scripts\make_version_info.py") $versionFile
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path $versionFile)) {
        throw "No se pudo generar build\version_info.txt"
    }
    $pyInstallerArgs = @(
        "-m", "PyInstaller",
        "--noconfirm",
        "--name", $exeName,
        "--distpath", (Join-Path $root "dist"),
        "--workpath", (Join-Path $root "build"),
        "--specpath", (Join-Path $root "build"),
        "--version-file", $versionFile,
        "--paths", $root,
        "--optimize", "1"
    )
    if ($Onedir) {
        $pyInstallerArgs += "--onedir"
    }
    else {
        $pyInstallerArgs += "--onefile"
    }
    if ($Windowed) {
        $pyInstallerArgs += "--windowed"
    }
    else {
        $pyInstallerArgs += "--console"
    }

    # Modulos que la app no usa. Recortan el bundle sin tocar QtCore/Gui/Widgets.
    $excludes = @(
        "tkinter",
        "pydoc",
        "doctest",
        "PySide6.QtNetwork",
        "PySide6.QtQml",
        "PySide6.QtQuick",
        "PySide6.QtQuickWidgets",
        "PySide6.QtQuickControls2",
        "PySide6.QtSql",
        "PySide6.QtTest",
        "PySide6.QtDBus",
        "PySide6.QtPrintSupport",
        "PySide6.QtOpenGL",
        "PySide6.QtOpenGLWidgets",
        "PySide6.QtSvg",
        "PySide6.QtSvgWidgets",
        "PySide6.QtXml",
        "PySide6.QtConcurrent",
        "PySide6.QtHelp",
        "PySide6.QtUiTools",
        "PySide6.QtDesigner",
        "PySide6.QtPdf",
        "PySide6.QtPdfWidgets",
        "PySide6.QtWebEngineCore",
        "PySide6.QtWebEngineWidgets",
        "PySide6.QtWebChannel",
        "PySide6.QtWebSockets",
        "PySide6.QtMultimedia",
        "PySide6.QtMultimediaWidgets",
        "PySide6.QtPositioning",
        "PySide6.QtSerialPort",
        "PySide6.QtBluetooth",
        "PySide6.QtNfc",
        "PySide6.QtCharts",
        "PySide6.QtDataVisualization",
        "PySide6.QtStateMachine",
        "PySide6.QtScxml",
        "PySide6.QtSensors",
        "PySide6.QtTextToSpeech",
        "PySide6.QtHttpServer",
        "PySide6.QtGraphs",
        "PySide6.QtLocation",
        "PySide6.QtRemoteObjects",
        "PySide6.QtVirtualKeyboard"
    )
    foreach ($module in $excludes) {
        $pyInstallerArgs += @("--exclude-module", $module)
    }

    $icon = Join-Path $root "resources\icon.ico"
    if (Test-Path $icon) {
        $pyInstallerArgs += @("--icon", $icon)
        # El icono viaja dentro del .exe para que la ventana lo use en runtime.
        $pyInstallerArgs += @("--add-data", "$icon;resources")
    }
    $pyInstallerArgs += (Join-Path $root "main.py")

    & $python @pyInstallerArgs
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller fallo."
    }

    if ($Onedir) {
        $bundleDir = Join-Path $root "dist\$exeName"
        $exePath = Join-Path $bundleDir "$exeName.exe"
    }
    else {
        $exePath = Join-Path $root "dist\$exeName.exe"
    }
    if (-not (Test-Path $exePath)) {
        throw "No se genero el ejecutable esperado: $exePath"
    }

    Write-Host "[3/3] Metadatos del build" -ForegroundColor Cyan
    $commit = "n/a"
    try {
        $commit = (& git rev-parse --short HEAD 2>$null)
        if ($LASTEXITCODE -ne 0 -or -not $commit) {
            $commit = "n/a"
        }
    }
    catch {
        $commit = "n/a"
    }

    $exeSize = (Get-Item $exePath).Length
    if ($Onedir) {
        $bundleSize = (Get-ChildItem -Recurse -File $bundleDir | Measure-Object -Property Length -Sum).Sum
        $exeRelative = "dist/$exeName/$exeName.exe"
    }
    else {
        $bundleSize = $exeSize
        $exeRelative = "dist/$exeName.exe"
    }

    $info = [ordered]@{
        app         = "MediaFormat"
        version     = [string]$buildVersion
        built_at    = (Get-Date).ToString("yyyy-MM-ddTHH:mm:ssK")
        python      = (& $python -c "import sys; print(sys.version.split()[0])").Trim()
        commit      = [string]$commit
        windowed    = [bool]$Windowed
        mode        = [string]$mode
        exe         = $exeRelative
        size_mb     = [math]::Round($exeSize / 1MB, 1)
        bundle_mb   = [math]::Round($bundleSize / 1MB, 1)
        sha256      = (Get-FileHash -Algorithm SHA256 -Path $exePath).Hash
    }
    $info | ConvertTo-Json | Set-Content -Path (Join-Path $root "dist\build_info.json") -Encoding UTF8

    $sizeMb = [math]::Round($exeSize / 1MB, 1)
    $bundleMb = [math]::Round($bundleSize / 1MB, 1)
    Write-Host ""
    Write-Host "OK: $exePath ($sizeMb MB, bundle $bundleMb MB, $mode)" -ForegroundColor Green
    Write-Host "Registra el cambio en CHANGELOG.md." -ForegroundColor DarkGray
    Write-Host "Recuerda: la version solo cambia si el usuario lo decide." -ForegroundColor DarkGray
    exit 0
}
catch {
    Write-Host "BUILD FALLIDO: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
finally {
    Pop-Location
}
