# Builds the AINGEL Desktop installer: publishes the app, zips it, embeds the zip and its SHA-256 in AingelSetup,
# publishes AingelSetup as one file and writes a release manifest with the installer's own SHA-256.
# Output: desktop\dist-installer\AINGEL-Desktop-Setup-<version>.exe and manifest.json; with -Web, both are also copied
# to web\public\downloads so the website's download button points to a real, verified file.
# Needs the .NET 8 SDK (or newer); downloads no NuGet packages. The computer that installs it needs the .NET 8 Desktop
# Runtime (Microsoft), which Windows offers to install if it is missing.
param([switch]$Web, [switch]$SkipTests)
$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
[xml]$project = Get-Content (Join-Path $root "AingelDesktop\AingelDesktop.csproj")
$version = $project.Project.PropertyGroup.Version | Where-Object { $_ } | Select-Object -First 1

& (Join-Path $root "Build-Desktop.ps1") -SkipTests:$SkipTests
$work = Join-Path $root "obj-installer"
if (Test-Path $work) { Remove-Item $work -Recurse -Force }
New-Item -ItemType Directory $work | Out-Null
$zip = Join-Path $work "payload.zip"
# The published app without debug symbols.
$files = Get-ChildItem (Join-Path $root "dist") -File | Where-Object { $_.Extension -ne ".pdb" }
Compress-Archive -Path $files.FullName -DestinationPath $zip
$payloadHash = (Get-FileHash $zip -Algorithm SHA256).Hash.ToLowerInvariant()
Set-Content -Path (Join-Path $work "payload.sha256") -Value $payloadHash -NoNewline -Encoding ascii

$out = Join-Path $root "dist-installer"
if (Test-Path $out) { Remove-Item $out -Recurse -Force }
$hashFile = Join-Path $work "payload.sha256"
$setupOut = Join-Path $work "setup"
dotnet publish (Join-Path $root "AingelSetup\AingelSetup.csproj") -c Release -r win-x64 --no-self-contained `
  -p:PublishSingleFile=true -p:IncludeNativeLibrariesForSelfExtract=true -p:DebugType=none "-p:Version=$version" `
  "-p:PayloadZip=$zip" "-p:PayloadHash=$hashFile" -o $setupOut
if ($LASTEXITCODE -ne 0) { throw "installer build failed" }
New-Item -ItemType Directory $out | Out-Null
$name = "AINGEL-Desktop-Setup-$version.exe"
Copy-Item (Join-Path $work "setup\AingelSetup.exe") (Join-Path $out $name)
$installer = Get-Item (Join-Path $out $name)
$manifest = [ordered]@{
  product = "AINGEL Desktop"
  version = $version
  date = (Get-Date -Format "yyyy-MM-dd")
  file = $name
  size_bytes = $installer.Length
  sha256 = (Get-FileHash $installer.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
  payload_sha256 = $payloadHash
  signed = $false
  platform = "Windows 10 2004+ / Windows 11, x64"
  requires = ".NET 8 Desktop Runtime (Microsoft)"
}
# UTF-8 without a byte-order mark: strict JSON readers reject one.
[IO.File]::WriteAllText((Join-Path $out "manifest.json"), ($manifest | ConvertTo-Json), (New-Object Text.UTF8Encoding $false))
if ($Web) {
  $downloads = Join-Path $root "..\web\public\downloads"
  New-Item -ItemType Directory $downloads -Force | Out-Null
  Copy-Item (Join-Path $out "*") $downloads -Force
}
Get-Content (Join-Path $out "manifest.json")
