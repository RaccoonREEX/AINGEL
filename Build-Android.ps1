param([switch]$Install, [switch]$DeviceTests)
$ErrorActionPreference = 'Stop'
$project = Join-Path $PSScriptRoot 'android'
$previousJava = $env:JAVA_HOME
$previousOptions = $env:JAVA_TOOL_OPTIONS
try {
    $studioJava = Join-Path $env:ProgramFiles 'Android\Android Studio\jbr'
    if (Test-Path -LiteralPath (Join-Path $studioJava 'bin\java.exe')) { $env:JAVA_HOME = $studioJava }
    $sdk = if ($env:ANDROID_HOME) { $env:ANDROID_HOME } else { Join-Path $env:LOCALAPPDATA 'Android\Sdk' }
    if (!(Test-Path -LiteralPath (Join-Path $sdk 'platform-tools\adb.exe'))) { throw 'Install Android SDK and platform-tools first.' }
    $sdkProperty = $sdk.Replace('\', '/').Replace(':', '\:')
    [IO.File]::WriteAllText((Join-Path $project 'local.properties'), "sdk.dir=$sdkProperty`n", [Text.UTF8Encoding]::new($false))
    # On this Windows host the JDK Unix-domain NIO pipe fails. A nonexistent
    # directory selects the JDK's normal authenticated loopback TCP fallback.
    # This option is scoped to this build; no Java/Windows settings are changed.
    $missingSocketDirectory = 'C:/aingel-java-socket-fallback-' + [Guid]::NewGuid().ToString('N')
    $env:JAVA_TOOL_OPTIONS = "$previousOptions -Djdk.net.unixdomain.tmpdir=$missingSocketDirectory".Trim()
    $adb = Join-Path $sdk 'platform-tools\adb.exe'
    if ($DeviceTests -or $Install) {
        $devices = @(& $adb devices | Select-String '^\S+\s+device$')
        if ($devices.Count -ne 1) { throw 'Connect exactly one authorized USB debugging device.' }
        & $adb reverse tcp:8010 tcp:8010
        if ($LASTEXITCODE -ne 0) { throw 'USB reverse failed.' }
    }
    $gradleArguments = @('assembleDebug', 'testDebugUnitTest', 'lintDebug', '--no-daemon', '--console=plain')
    if ($DeviceTests) { $gradleArguments += 'connectedDebugAndroidTest' }
    Push-Location $project
    try {
        & .\gradlew.bat @gradleArguments
        if ($LASTEXITCODE -ne 0) { throw 'Android build or validation failed.' }
    } finally { Pop-Location }
    $apk = Join-Path $project 'app\build\outputs\apk\debug\app-debug.apk'
    Write-Output "Validated debug APK: $apk"
    if ($Install) {
        & $adb install -r $apk
        if ($LASTEXITCODE -ne 0) { throw 'APK installation failed.' }
        & $adb shell am start -n ec.aingel.mobile/.MainActivity
        if ($LASTEXITCODE -ne 0) { throw 'Could not open AINGEL.' }
    }
} finally {
    $env:JAVA_HOME = $previousJava
    $env:JAVA_TOOL_OPTIONS = $previousOptions
}
