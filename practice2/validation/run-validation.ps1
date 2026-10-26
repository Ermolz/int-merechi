param([string]$JavaHome = $env:JAVA_HOME)
$ErrorActionPreference = 'Stop'
$validationDirectory = $PSScriptRoot
$workspaceDirectory = Split-Path -Parent $validationDirectory
$libraryDirectory = Join-Path $validationDirectory 'lib'
$buildDirectory = Join-Path $validationDirectory 'build'

if (-not $JavaHome) {
    $javaCommand = Get-Command javac.exe -ErrorAction SilentlyContinue
    if ($javaCommand) { $JavaHome = Split-Path -Parent (Split-Path -Parent $javaCommand.Source) }
}
if (-not $JavaHome) {
    $candidate = Get-ChildItem -LiteralPath 'C:\Program Files\Eclipse Adoptium' -Directory -ErrorAction SilentlyContinue |
        Where-Object { Test-Path -LiteralPath (Join-Path $_.FullName 'bin\javac.exe') } |
        Sort-Object Name | Select-Object -First 1
    if ($candidate) { $JavaHome = $candidate.FullName }
}
if (-not $JavaHome) { throw 'JDK 11+ is required. Pass -JavaHome or set JAVA_HOME.' }
$java = Join-Path $JavaHome 'bin\java.exe'
$javac = Join-Path $JavaHome 'bin\javac.exe'
if (-not (Test-Path -LiteralPath $javac)) { throw "JDK compiler not found: $javac" }
if (-not (Test-Path -LiteralPath (Join-Path $libraryDirectory 'org.semanticweb.hermit-1.4.3.456.jar'))) { throw 'Bundled HermiT libraries are missing.' }

New-Item -ItemType Directory -Path $buildDirectory -Force | Out-Null
$javaClassPath = "$libraryDirectory\*;$buildDirectory"
$sources = @((Join-Path $validationDirectory 'VerifyOntology.java'), (Join-Path $validationDirectory 'VerifyPractice3.java'))
& $javac -proc:none -encoding UTF-8 -cp $javaClassPath -d $buildDirectory @sources
if ($LASTEXITCODE -ne 0) { throw "Compilation failed: $LASTEXITCODE" }
$ontologyPath = Join-Path $workspaceDirectory 'PC_Builder.owl'
$hashBefore = (Get-FileHash -LiteralPath $ontologyPath -Algorithm SHA256).Hash
$logConfiguration = Join-Path $validationDirectory 'logback.xml'
& $java "-Dlogback.configurationFile=$logConfiguration" -cp $javaClassPath VerifyOntology $ontologyPath 2>&1 |
    Tee-Object -FilePath (Join-Path $validationDirectory 'reasoner-output.txt')
if ($LASTEXITCODE -ne 0) { throw "Validation failed: $LASTEXITCODE" }
$hashAfter = (Get-FileHash -LiteralPath $ontologyPath -Algorithm SHA256).Hash
if ($hashBefore -ne $hashAfter) { throw 'Validation unexpectedly changed the ontology.' }
"$hashAfter  PC_Builder.owl" | Set-Content -LiteralPath (Join-Path $validationDirectory 'owl-sha256.txt') -Encoding utf8
