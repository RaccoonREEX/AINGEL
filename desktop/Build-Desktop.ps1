# Builds AINGEL Desktop, runs its checks and publishes a framework-dependent build to desktop\dist.
# Needs the .NET 8 SDK (or newer) on the build machine and the .NET 8 Desktop Runtime on the computer that runs it.
# No NuGet packages are downloaded: the app uses only libraries included with .NET.
param([switch]$SkipTests)
$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
dotnet build (Join-Path $root "AingelDesktop.slnx") -c Release
if ($LASTEXITCODE -ne 0) { throw "build failed" }
if (-not $SkipTests) {
    dotnet (Join-Path $root "AingelDesktop.Tests\bin\Release\net8.0-windows\AingelDesktop.Tests.dll")
    if ($LASTEXITCODE -ne 0) { throw "checks failed" }
}
$dist = Join-Path $root "dist"
if (Test-Path $dist) { Remove-Item $dist -Recurse -Force }
dotnet publish (Join-Path $root "AingelDesktop\AingelDesktop.csproj") -c Release -o $dist --no-self-contained
if ($LASTEXITCODE -ne 0) { throw "publish failed" }
Get-FileHash (Join-Path $dist "AingelDesktop.exe") -Algorithm SHA256 | Format-List
"Published to $dist"
