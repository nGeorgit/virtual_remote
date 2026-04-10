$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

param(
    [string]$SourceExe = (Join-Path $PSScriptRoot "mobile-typer.exe"),
    [switch]$AutoStart,
    [switch]$SkipDesktopShortcut,
    [switch]$SkipFirewallRule,
    [switch]$LaunchAfterInstall
)

$installDir = Join-Path $env:LOCALAPPDATA "MobileTyper"
$installExe = Join-Path $installDir "mobile-typer.exe"
$startMenuDir = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs"
$startMenuShortcut = Join-Path $startMenuDir "Mobile Typer.lnk"
$desktopShortcut = Join-Path ([Environment]::GetFolderPath("Desktop")) "Mobile Typer.lnk"
$runKeyPath = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run"
$firewallRuleName = "Mobile Typer"

function Write-Step {
    param([string]$Message)
    Write-Host ""
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Test-IsAdmin {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function New-Shortcut {
    param(
        [string]$ShortcutPath,
        [string]$TargetPath,
        [string]$WorkingDirectory,
        [string]$Description
    )

    $shell = New-Object -ComObject WScript.Shell
    $shortcut = $shell.CreateShortcut($ShortcutPath)
    $shortcut.TargetPath = $TargetPath
    $shortcut.WorkingDirectory = $WorkingDirectory
    $shortcut.Description = $Description
    $shortcut.IconLocation = $TargetPath
    $shortcut.Save()
}

function Set-AutoStart {
    param([string]$ExecutablePath, [bool]$Enabled)

    if ($Enabled) {
        New-Item -Path $runKeyPath -Force | Out-Null
        New-ItemProperty `
            -Path $runKeyPath `
            -Name "MobileTyper" `
            -Value ('"{0}"' -f $ExecutablePath) `
            -PropertyType String `
            -Force | Out-Null
        return
    }

    Remove-ItemProperty -Path $runKeyPath -Name "MobileTyper" -ErrorAction SilentlyContinue
}

function Set-FirewallRule {
    param([string]$ExecutablePath)

    if ($SkipFirewallRule) {
        return
    }

    if (-not (Test-IsAdmin)) {
        Write-Warning "Skipping firewall rule because this installer is not running as Administrator."
        return
    }

    Write-Step "Adding or updating the Windows Firewall rule"
    Get-NetFirewallRule -DisplayName $firewallRuleName -ErrorAction SilentlyContinue | Remove-NetFirewallRule | Out-Null
    New-NetFirewallRule `
        -DisplayName $firewallRuleName `
        -Direction Inbound `
        -Action Allow `
        -Program $ExecutablePath `
        -Profile Private | Out-Null
}

if (-not (Test-Path $SourceExe)) {
    throw "Could not find mobile-typer.exe at $SourceExe"
}

Write-Step "Installing Mobile Typer"
New-Item -ItemType Directory -Force -Path $installDir | Out-Null
Copy-Item -Path $SourceExe -Destination $installExe -Force

Write-Step "Creating shortcuts"
New-Shortcut `
    -ShortcutPath $startMenuShortcut `
    -TargetPath $installExe `
    -WorkingDirectory $installDir `
    -Description "Mobile Typer"

if (-not $SkipDesktopShortcut) {
    New-Shortcut `
        -ShortcutPath $desktopShortcut `
        -TargetPath $installExe `
        -WorkingDirectory $installDir `
        -Description "Mobile Typer"
}

Set-AutoStart -ExecutablePath $installExe -Enabled $AutoStart.IsPresent
Set-FirewallRule -ExecutablePath $installExe

Write-Step "Install complete"
Write-Host $installExe -ForegroundColor Green

if ($LaunchAfterInstall) {
    Write-Step "Launching Mobile Typer"
    Start-Process -FilePath $installExe -WorkingDirectory $installDir
}
