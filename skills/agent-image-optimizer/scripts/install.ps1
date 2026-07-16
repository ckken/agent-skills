$ErrorActionPreference = "Stop"

$Repository = if ($env:AGENT_IMAGE_OPT_REPOSITORY) {
    $env:AGENT_IMAGE_OPT_REPOSITORY
} else {
    "ckken/agent-skills"
}
$ReleaseBase = if ($env:AGENT_IMAGE_OPT_RELEASE_BASE_URL) {
    $env:AGENT_IMAGE_OPT_RELEASE_BASE_URL
} else {
    "https://github.com/$Repository/releases/latest/download"
}
$InstallDir = if ($env:AGENT_IMAGE_OPT_INSTALL_DIR) {
    $env:AGENT_IMAGE_OPT_INSTALL_DIR
} else {
    Join-Path $HOME ".local\bin"
}

if ([System.Runtime.InteropServices.RuntimeInformation]::OSArchitecture -ne "X64") {
    throw "agent-image-opt currently provides a Windows x86_64 binary only."
}

$Asset = "agent-image-opt-x86_64-pc-windows-msvc.zip"
$TempDir = Join-Path ([System.IO.Path]::GetTempPath()) ("agent-image-opt-" + [guid]::NewGuid())

try {
    New-Item -ItemType Directory -Force -Path $TempDir | Out-Null
    $Archive = Join-Path $TempDir $Asset
    $Checksums = Join-Path $TempDir "SHA256SUMS"

    Write-Host "Downloading $Asset from the latest agent-image-opt release..."
    Invoke-WebRequest "$ReleaseBase/$Asset" -OutFile $Archive
    Invoke-WebRequest "$ReleaseBase/SHA256SUMS" -OutFile $Checksums

    $ChecksumLine = Get-Content $Checksums | Where-Object { $_ -match "\s$([regex]::Escape($Asset))$" } | Select-Object -First 1
    if (-not $ChecksumLine) {
        throw "Checksum entry not found for $Asset."
    }

    $Expected = ($ChecksumLine -split "\s+")[0].ToLowerInvariant()
    $Actual = (Get-FileHash -Algorithm SHA256 $Archive).Hash.ToLowerInvariant()
    if ($Actual -ne $Expected) {
        throw "Checksum verification failed for $Asset."
    }

    $ExtractDir = Join-Path $TempDir "extracted"
    Expand-Archive -Path $Archive -DestinationPath $ExtractDir
    New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null
    $Destination = Join-Path $InstallDir "agent-image-opt.exe"
    Copy-Item (Join-Path $ExtractDir "agent-image-opt.exe") $Destination -Force

    Write-Host "Installed agent-image-opt to $Destination"
    & $Destination --json doctor
} finally {
    if (Test-Path $TempDir) {
        Remove-Item -Recurse -Force $TempDir
    }
}
