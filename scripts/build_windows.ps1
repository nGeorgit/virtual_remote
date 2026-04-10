$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $repoRoot

$pythonVersion = "3.11"
$pyInstallerVersion = "6.19.0"
$distPath = Join-Path $repoRoot "dist\mobile-typer.exe"
$versionFile = Join-Path $repoRoot "packaging\windows_version_info.txt"
$installScriptPath = Join-Path $repoRoot "scripts\install_mobile_typer.ps1"
$installBatchPath = Join-Path $repoRoot "scripts\install_mobile_typer.bat"
$localUvDir = Join-Path $repoRoot ".build-tools\uv"
$localUvExe = Join-Path $localUvDir "uv.exe"
$uvInstallScript = "https://astral.sh/uv/install.ps1"

function Write-Step {
    param([string]$Message)
    Write-Host ""
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Resolve-UvCommand {
    $command = Get-Command uv -ErrorAction SilentlyContinue
    if ($command) {
        return $command.Source
    }

    if (Test-Path $localUvExe) {
        $env:Path = "$(Split-Path $localUvExe);$env:Path"
        return $localUvExe
    }

    return $null
}

function Install-Uv {
    $existing = Resolve-UvCommand
    if ($existing) {
        Write-Step "Found uv at $existing"
        return $existing
    }

    Write-Step "uv was not found. Installing a local copy from Astral."
    New-Item -ItemType Directory -Force -Path $localUvDir | Out-Null
    $env:UV_INSTALL_DIR = $localUvDir
    $env:UV_NO_MODIFY_PATH = "1"
    Invoke-RestMethod $uvInstallScript | Invoke-Expression

    $installed = Resolve-UvCommand
    if (-not $installed) {
        throw "uv installation finished, but uv.exe was still not found."
    }

    return $installed
}

function Ensure-Python {
    param([string]$UvExe, [string]$Version)

    Write-Step "Ensuring Python $Version is available through uv"
    & $UvExe python install $Version
    if ($LASTEXITCODE -ne 0) {
        throw "uv could not install Python $Version."
    }
}

function Build-Executable {
    param([string]$UvExe, [string]$Version, [string]$PyInstallerVersion)

    Write-Step "Building mobile-typer.exe"
    & $UvExe run --python $Version --with "pyinstaller==$PyInstallerVersion" pyinstaller `
        --noconfirm `
        --clean `
        --onefile `
        --windowed `
        --add-data "icons;icons" `
        --version-file $versionFile `
        --hidden-import qrcode `
        --hidden-import tkinter `
        --hidden-import tkinter.messagebox `
        --name mobile-typer `
        run_mobile_typer.py

    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller build failed."
    }
}

function Resolve-SignTool {
    $command = Get-Command signtool.exe -ErrorAction SilentlyContinue
    if ($command) {
        return $command.Source
    }

    $kitsRoot = "${env:ProgramFiles(x86)}\Windows Kits\10\bin"
    if (-not (Test-Path $kitsRoot)) {
        return $null
    }

    $tool = Get-ChildItem -Path $kitsRoot -Filter signtool.exe -Recurse -ErrorAction SilentlyContinue |
        Sort-Object FullName -Descending |
        Select-Object -First 1

    if ($tool) {
        return $tool.FullName
    }

    return $null
}

function Try-SignExecutable {
    param([string]$ExecutablePath)

    $certificatePath = $env:MOBILE_TYPER_SIGN_PFX
    $certificatePassword = $env:MOBILE_TYPER_SIGN_PFX_PASSWORD
    if (-not $certificatePath -or -not $certificatePassword) {
        return
    }

    $signTool = Resolve-SignTool
    if (-not $signTool) {
        throw "Signing was requested, but signtool.exe could not be found."
    }

    Write-Step "Signing mobile-typer.exe"
    $arguments = @(
        "sign",
        "/f", $certificatePath,
        "/p", $certificatePassword,
        "/fd", "SHA256",
        "/td", "SHA256"
    )

    if ($env:MOBILE_TYPER_SIGN_TIMESTAMP_URL) {
        $arguments += @("/tr", $env:MOBILE_TYPER_SIGN_TIMESTAMP_URL)
    }

    $arguments += $ExecutablePath
    & $signTool @arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Code signing failed."
    }
}

function Stage-Installers {
    Write-Step "Staging client install scripts"
    Copy-Item -Path $installScriptPath -Destination (Join-Path $repoRoot "dist\install_mobile_typer.ps1") -Force
    Copy-Item -Path $installBatchPath -Destination (Join-Path $repoRoot "dist\install_mobile_typer.bat") -Force
}

$uvExe = Install-Uv
Ensure-Python -UvExe $uvExe -Version $pythonVersion
Build-Executable -UvExe $uvExe -Version $pythonVersion -PyInstallerVersion $pyInstallerVersion
Try-SignExecutable -ExecutablePath $distPath
Stage-Installers

if (-not (Test-Path $distPath)) {
    throw "Build completed without producing $distPath"
}

Write-Step "Build complete"
Write-Host $distPath -ForegroundColor Green
