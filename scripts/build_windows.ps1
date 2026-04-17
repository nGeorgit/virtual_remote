param(
    [switch]$SkipInstaller,
    [switch]$SkipSigning
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

# PowerShell 2.0 does not populate $PSScriptRoot, so fall back to the invoked script path.
$scriptRoot = $null
$psScriptRootVariable = Get-Variable -Name PSScriptRoot -ErrorAction SilentlyContinue
if ($psScriptRootVariable -and $psScriptRootVariable.Value) {
    $scriptRoot = $psScriptRootVariable.Value
}
elseif ($MyInvocation.MyCommand.Path) {
    $scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
}
else {
    throw "Unable to determine the build script directory."
}

$repoRoot = (Resolve-Path (Join-Path $scriptRoot "..")).Path
Set-Location $repoRoot

$vendorRoot = Join-Path $repoRoot "vendor\windows"
$manifestPath = Join-Path $vendorRoot "manifest.json"
$requirementsPath = Join-Path $repoRoot "packaging\windows-build-requirements.txt"
$specPath = Join-Path $repoRoot "packaging\mobile_typer.spec"
$versionFile = Join-Path $repoRoot "packaging\windows_version_info.txt"
$nsisScriptPath = Join-Path $repoRoot "packaging\mobile_typer_win7.nsi"
$installScriptPath = Join-Path $repoRoot "scripts\install_mobile_typer.ps1"
$installBatchPath = Join-Path $repoRoot "scripts\install_mobile_typer.bat"

$buildRoot = Join-Path $repoRoot ".build\windows"
$venvDir = Join-Path $buildRoot "venv"
$venvPython = Join-Path $venvDir "Scripts\python.exe"
$distRoot = Join-Path $repoRoot "dist\windows"
$appDir = Join-Path $distRoot "mobile-typer"
$appExe = Join-Path $appDir "mobile-typer.exe"
$hashOutputPath = Join-Path $distRoot "SHA256SUMS.txt"
$bundleManifestOutputPath = Join-Path $distRoot "build-manifest.json"
$installerOutputPath = Join-Path $distRoot "mobile-typer-win7-setup.exe"
$pyInstallerWorkPath = Join-Path $buildRoot "pyinstaller"

$env:PYTHONHASHSEED = "0"
if (-not $env:SOURCE_DATE_EPOCH) {
    $env:SOURCE_DATE_EPOCH = "1704067200"
}

function Write-Step {
    param([string]$Message)

    Write-Host ""
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Resolve-RepoPath {
    param([string]$RelativePath)

    return Join-Path $repoRoot ($RelativePath -replace "/", "\")
}

function Get-RepoRelativePath {
    param([string]$FullPath)

    $full = [System.IO.Path]::GetFullPath($FullPath)
    $root = [System.IO.Path]::GetFullPath($repoRoot)
    if ($full.StartsWith($root, [System.StringComparison]::OrdinalIgnoreCase)) {
        $relative = $full.Substring($root.Length).TrimStart('\')
        return $relative.Replace('\', '/')
    }

    return $full
}

function Test-PlaceholderHash {
    param([string]$Hash)

    if (-not $Hash) {
        return $true
    }

    return $Hash -match "^(TO_BE_FILLED|PLACEHOLDER|REPLACE_ME)"
}

function Get-ManifestValue {
    param(
        [Parameter(Mandatory = $true)]$InputObject,
        [Parameter(Mandatory = $true)][string]$Name
    )

    if ($null -eq $InputObject) {
        return $null
    }

    if ($InputObject -is [System.Collections.IDictionary]) {
        return $InputObject[$Name]
    }

    $property = $InputObject.PSObject.Properties[$Name]
    if ($property) {
        return $property.Value
    }

    return $null
}

function Get-FileSha256 {
    param([string]$Path)

    $stream = [System.IO.File]::OpenRead($Path)
    try {
        $sha256 = New-Object System.Security.Cryptography.SHA256Managed
        try {
            $hashBytes = $sha256.ComputeHash($stream)
        }
        finally {
            $sha256.Dispose()
        }
    }
    finally {
        $stream.Dispose()
    }

    return ([System.BitConverter]::ToString($hashBytes)).Replace("-", "").ToLowerInvariant()
}

function ConvertTo-JsonCompat {
    param($InputObject)

    $convertCmd = Get-Command ConvertTo-Json -ErrorAction SilentlyContinue
    if ($convertCmd) {
        return $InputObject | ConvertTo-Json -Depth 5
    }

    Add-Type -AssemblyName System.Web.Extensions
    $serializer = New-Object System.Web.Script.Serialization.JavaScriptSerializer
    $serializer.MaxJsonLength = [int]::MaxValue
    return $serializer.Serialize($InputObject)
}

function Read-VendorManifest {
    if (-not (Test-Path $manifestPath -PathType Leaf)) {
        throw "Missing vendor manifest at $manifestPath"
    }

    $json = [System.IO.File]::ReadAllText($manifestPath)

    # PowerShell 3+ provides ConvertFrom-Json. PowerShell 2.0 does not.
    $convertCmd = Get-Command ConvertFrom-Json -ErrorAction SilentlyContinue
    if ($convertCmd) {
        return $json | ConvertFrom-Json
    }

    # Fallback for PowerShell 2.0 using .NET JavaScriptSerializer
    Add-Type -AssemblyName System.Web.Extensions
    $serializer = New-Object System.Web.Script.Serialization.JavaScriptSerializer
    return $serializer.DeserializeObject($json)
}

function Assert-VendorArtifact {
    param(
        [Parameter(Mandatory = $true)]$Artifact,
        [switch]$Optional
    )

    $relativePath = [string](Get-ManifestValue -InputObject $Artifact -Name "relative_path")
    if (-not $relativePath) {
        throw "Vendor manifest entry is missing relative_path."
    }

    $artifactPath = Resolve-RepoPath $relativePath
    if (-not (Test-Path $artifactPath)) {
        if ($Optional) {
            return $null
        }

        throw "Missing vendored artifact: $relativePath. See vendor/windows/README.md for the required layout."
    }

    $expectedArtifactHash = [string](Get-ManifestValue -InputObject $Artifact -Name "sha256")
    if (-not (Test-PlaceholderHash $expectedArtifactHash)) {
        $actualHash = Get-FileSha256 -Path $artifactPath
        $expectedHash = $expectedArtifactHash.ToLowerInvariant()
        if ($actualHash -ne $expectedHash) {
            throw "SHA256 mismatch for $relativePath. Expected $expectedHash but found $actualHash."
        }
    }

    return $artifactPath
}

function Get-PythonExecutable {
    param($Manifest)

    $python = Get-ManifestValue -InputObject $Manifest -Name "python"
    if (-not $python) {
        throw "vendor/windows/manifest.json does not define the vendored Python runtime."
    }

    return Assert-VendorArtifact -Artifact $python
}

function Get-NSISExecutable {
    param($Manifest)

    $installerTools = Get-ManifestValue -InputObject $Manifest -Name "installer_tools"
    if (-not $installerTools) {
        return $null
    }

    foreach ($artifact in $installerTools) {
        $artifactPath = Assert-VendorArtifact -Artifact $artifact -Optional
        if ($artifactPath) {
            return $artifactPath
        }
    }

    return $null
}

function Assert-Wheelhouse {
    param($Manifest)

    $wheelhouse = Get-ManifestValue -InputObject $Manifest -Name "wheelhouse"
    if (-not $wheelhouse) {
        throw "vendor/windows/manifest.json does not define the offline wheelhouse."
    }

    foreach ($artifact in $wheelhouse) {
        [void](Assert-VendorArtifact -Artifact $artifact)
    }
}

function Ensure-BuildDirectories {
    New-Item -ItemType Directory -Force -Path $buildRoot | Out-Null
    New-Item -ItemType Directory -Force -Path $distRoot | Out-Null
}

function Ensure-BuildVirtualEnv {
    param([string]$PythonExe)

    if (Test-Path $venvPython -PathType Leaf) {
        return
    }

    Write-Step "Creating offline build virtual environment"
    & $PythonExe -m venv $venvDir
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to create the build virtual environment."
    }
}

function Assert-PythonVersion {
    param([string]$PythonExe)

    & $PythonExe -c "import sys; raise SystemExit(0 if sys.version_info[:2] == (3, 8) else 1)"
    if ($LASTEXITCODE -ne 0) {
        throw "The authoritative Windows build requires a vendored Python 3.8 runtime."
    }
}

function Install-BuildRequirements {
    param([string]$PythonExe)

    Write-Step "Installing pinned build requirements from the repo-local wheelhouse"
    & $PythonExe -m pip install --no-index --find-links (Join-Path $repoRoot "vendor\windows\wheels") --requirement $requirementsPath
    if ($LASTEXITCODE -ne 0) {
        throw "Offline dependency installation failed. Ensure the committed vendor/windows/wheels payload matches vendor/windows/manifest.json."
    }
}

function Invoke-PyInstallerBuild {
    param([string]$PythonExe)

    Write-Step "Building the canonical Windows 7 onedir artifact"

    if (Test-Path $appDir) {
        Remove-Item -Path $appDir -Recurse -Force
    }
    if (Test-Path $pyInstallerWorkPath) {
        Remove-Item -Path $pyInstallerWorkPath -Recurse -Force
    }

    & $PythonExe -m PyInstaller --noconfirm --clean --distpath $distRoot --workpath $pyInstallerWorkPath $specPath
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller build failed."
    }

    if (-not (Test-Path $appExe -PathType Leaf)) {
        throw "Build completed without producing $appExe"
    }
}

function Resolve-SignTool {
    $command = Get-Command signtool.exe -ErrorAction SilentlyContinue
    if ($command) {
        if ($command.Source) {
            return $command.Source
        }

        return $command.Definition
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

function Try-SignFile {
    param([string]$FilePath)

    if ($SkipSigning) {
        return
    }

    $certificatePath = $env:MOBILE_TYPER_SIGN_PFX
    $certificatePassword = $env:MOBILE_TYPER_SIGN_PFX_PASSWORD
    if (-not $certificatePath -or -not $certificatePassword) {
        return
    }

    $signTool = Resolve-SignTool
    if (-not $signTool) {
        throw "Signing was requested, but signtool.exe could not be found."
    }

    Write-Step "Signing $(Split-Path $FilePath -Leaf)"
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

    $arguments += $FilePath
    & $signTool @arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Code signing failed for $FilePath."
    }
}

function Stage-InstallArtifacts {
    Write-Step "Staging repo-local installer and manifest files"

    Copy-Item -Path $installScriptPath -Destination (Join-Path $distRoot "install_mobile_typer.ps1") -Force
    Copy-Item -Path $installBatchPath -Destination (Join-Path $distRoot "install_mobile_typer.bat") -Force
    Copy-Item -Path $nsisScriptPath -Destination (Join-Path $distRoot "mobile_typer_win7.nsi") -Force
    Copy-Item -Path $manifestPath -Destination (Join-Path $distRoot "vendor-manifest.json") -Force
    Copy-Item -Path (Join-Path $vendorRoot "SHA256SUMS.txt") -Destination (Join-Path $distRoot "vendor-SHA256SUMS.txt") -Force
}

function Build-NSISInstaller {
    param([string]$NsisExe)

    if ($SkipInstaller) {
        return
    }

    if (-not $NsisExe) {
        Write-Warning "NSIS is not vendored yet. Skipping setup.exe generation and leaving mobile_typer_win7.nsi in dist/windows/."
        return
    }

    Write-Step "Building the optional NSIS installer"
    & $NsisExe /DAPP_SOURCE_DIR=$appDir /DOUT_FILE=$installerOutputPath $nsisScriptPath
    if ($LASTEXITCODE -ne 0) {
        throw "NSIS failed to build the Windows 7 installer."
    }
}

function Write-OutputManifest {
    $files = Get-ChildItem -Path $distRoot -Recurse |
        Where-Object { -not $_.PSIsContainer -and $_.FullName -ne $hashOutputPath } |
        Sort-Object FullName

    $hashLines = @()
    $manifestEntries = @()
    foreach ($file in $files) {
        $hash = Get-FileSha256 -Path $file.FullName
        $relativePath = Get-RepoRelativePath $file.FullName
        $hashLines += "$hash *$relativePath"
        $manifestEntries += @{
            path = $relativePath
            sha256 = $hash
            bytes = $file.Length
        }
    }

    Set-Content -Path $hashOutputPath -Value $hashLines

    $buildManifest = @{
        schema_version = 1
        canonical_artifact = "dist/windows/mobile-typer/"
        python_hash_seed = $env:PYTHONHASHSEED
        source_date_epoch = $env:SOURCE_DATE_EPOCH
        generated_files = $manifestEntries
    }
    Set-Content -Path $bundleManifestOutputPath -Value (ConvertTo-JsonCompat -InputObject $buildManifest)
}

$manifest = Read-VendorManifest
$pythonExe = Get-PythonExecutable -Manifest $manifest
$nsisExe = Get-NSISExecutable -Manifest $manifest
Assert-Wheelhouse -Manifest $manifest
Ensure-BuildDirectories
Assert-PythonVersion -PythonExe $pythonExe
Ensure-BuildVirtualEnv -PythonExe $pythonExe
Install-BuildRequirements -PythonExe $venvPython
Invoke-PyInstallerBuild -PythonExe $venvPython
Try-SignFile -FilePath $appExe
Stage-InstallArtifacts
Build-NSISInstaller -NsisExe $nsisExe
if (Test-Path $installerOutputPath -PathType Leaf) {
    Try-SignFile -FilePath $installerOutputPath
}
Write-OutputManifest

Write-Step "Build complete"
Write-Host "Canonical Win7 artifact directory: $appDir" -ForegroundColor Green
if (Test-Path $installerOutputPath -PathType Leaf) {
    Write-Host "Optional installer: $installerOutputPath" -ForegroundColor Green
}
Write-Host "Bundle manifest: $bundleManifestOutputPath" -ForegroundColor Green
