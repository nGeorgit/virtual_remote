param(
    [string]$SourcePath = (Join-Path $PSScriptRoot "mobile-typer"),
    [string]$SourceExe = (Join-Path $PSScriptRoot "mobile-typer.exe"),
    [switch]$AutoStart,
    [switch]$SkipDesktopShortcut,
    [switch]$SkipFirewallRule,
    [switch]$LaunchAfterInstall
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

$installDir = Join-Path $env:LOCALAPPDATA "MobileTyper"
$installExe = Join-Path $installDir "mobile-typer.exe"
$startMenuDir = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs"
$startMenuShortcut = Join-Path $startMenuDir "Mobile Remote.lnk"
$runKeyPath = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run"
$firewallRuleName = "Mobile Remote"

$comShell = New-Object -ComObject WScript.Shell
$safeDesktopPath = $comShell.SpecialFolders.Item("Desktop")
$desktopShortcut = Join-Path $safeDesktopPath "Mobile Remote.lnk"

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

function Resolve-SourcePayload {
    if (Test-Path $SourcePath -PathType Container) {
        return @{
            Mode = "Directory"
            Path = (Resolve-Path $SourcePath).Path
        }
    }

    if (Test-Path $SourceExe -PathType Leaf) {
        return @{
            Mode = "SingleFile"
            Path = (Resolve-Path $SourceExe).Path
        }
    }

    throw "Could not find a Mobile Typer payload. Expected either $SourcePath or $SourceExe."
}

function Reset-InstallDirectory {
    if (-not (Test-Path $installDir)) {
        New-Item -ItemType Directory -Force -Path $installDir | Out-Null
        return
    }

    Get-ChildItem -Path $installDir -Force | Remove-Item -Recurse -Force
}

function Install-Payload {
    param([hashtable]$Payload)

    Reset-InstallDirectory

    if ($Payload.Mode -eq "Directory") {
        Write-Step "Installing canonical onedir payload"
        Copy-Item -Path (Join-Path $Payload.Path "*") -Destination $installDir -Recurse -Force
    }
    else {
        Write-Step "Installing single-file fallback payload"
        Copy-Item -Path $Payload.Path -Destination $installExe -Force
    }

    if (-not (Test-Path $installExe -PathType Leaf)) {
        throw "The install payload did not produce $installExe."
    }
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
        New-ItemProperty -Path $runKeyPath -Name "MobileTyper" -Value ('"{0}"' -f $ExecutablePath) -PropertyType String -Force | Out-Null
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

    $getFirewallRuleCommand = Get-Command -Name Get-NetFirewallRule -ErrorAction SilentlyContinue
    $newFirewallRuleCommand = Get-Command -Name New-NetFirewallRule -ErrorAction SilentlyContinue
    $removeFirewallRuleCommand = Get-Command -Name Remove-NetFirewallRule -ErrorAction SilentlyContinue

    if ($getFirewallRuleCommand -and $newFirewallRuleCommand -and $removeFirewallRuleCommand) {
        Get-NetFirewallRule -DisplayName $firewallRuleName -ErrorAction SilentlyContinue | Remove-NetFirewallRule | Out-Null
        New-NetFirewallRule -DisplayName $firewallRuleName -Direction Inbound -Action Allow -Program $ExecutablePath -Profile Private | Out-Null
        return
    }

    Write-Host "  [INFO] NetSecurity cmdlets are unavailable. Falling back to netsh advfirewall." -ForegroundColor Cyan
    & netsh advfirewall firewall delete rule "name=$firewallRuleName" "program=$ExecutablePath" | Out-Null
    & netsh advfirewall firewall add rule "name=$firewallRuleName" dir=in action=allow "program=$ExecutablePath" profile=private enable=yes | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "netsh could not create the Windows Firewall rule."
    }
}

function Create-Shortcuts {
    Write-Step "Creating shortcuts"
    New-Item -ItemType Directory -Force -Path $startMenuDir | Out-Null

    try {
        New-Shortcut -ShortcutPath $startMenuShortcut -TargetPath $installExe -WorkingDirectory $installDir -Description "Mobile Remote"
        Write-Host "  [OK] Start Menu shortcut created." -ForegroundColor Green
    }
    catch {
        Write-Host "  [WARN] Failed to create Start Menu shortcut." -ForegroundColor Yellow
    }

    if ($SkipDesktopShortcut) {
        return
    }

    try {
        New-Shortcut -ShortcutPath $desktopShortcut -TargetPath $installExe -WorkingDirectory $installDir -Description "Mobile Remote"
        Write-Host "  [OK] Desktop shortcut created." -ForegroundColor Green
    }
    catch {
        Write-Host "  [WARN] Windows blocked the Desktop shortcut due to localized or redirected folders." -ForegroundColor Yellow
        Write-Host "  [INFO] The app is still installed successfully. Use the Start Menu shortcut instead." -ForegroundColor Cyan
    }
}

$payload = Resolve-SourcePayload
Install-Payload -Payload $payload
Create-Shortcuts
Set-AutoStart -ExecutablePath $installExe -Enabled ([bool]$AutoStart)
Set-FirewallRule -ExecutablePath $installExe

Write-Step "Install complete"
Write-Host "Executable is located at: $installExe" -ForegroundColor Green

if ($LaunchAfterInstall) {
    Write-Step "Launching Mobile Remote"
    Start-Process -FilePath $installExe -WorkingDirectory $installDir
}
