param(
    [string]$JarPath = ".\tools\tika\tika-server-standard-3.2.3.jar",
    [int]$Port = 9998,
    [string]$JavaPath = ""
)

$Utf8NoBom = [System.Text.UTF8Encoding]::new($false)
[Console]::InputEncoding = $Utf8NoBom
[Console]::OutputEncoding = $Utf8NoBom
$OutputEncoding = $Utf8NoBom

if (-not (Test-Path -LiteralPath $JarPath)) {
    Write-Error "Tika server jar not found: $JarPath"
    exit 1
}

if (-not $JavaPath) {
    if ($env:JAVA_HOME -and (Test-Path -LiteralPath (Join-Path $env:JAVA_HOME "bin\java.exe"))) {
        $JavaPath = Join-Path $env:JAVA_HOME "bin\java.exe"
    } else {
        $javaCommand = Get-Command java -ErrorAction SilentlyContinue
        if ($null -eq $javaCommand) {
            Write-Error "Java executable not found. Set JAVA_HOME or pass -JavaPath explicitly."
            exit 1
        }
        $JavaPath = $javaCommand.Source
    }
}

Write-Host "Starting Apache Tika Server on port $Port"
Write-Host "Using Java: $JavaPath"
& $JavaPath -version
& $JavaPath -jar $JarPath --port $Port
