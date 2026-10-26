param(
 [string]$ProtegeDirectory = $env:PROTEGE_HOME,
 [string]$JavaHome = $env:JAVA_HOME
)
$ErrorActionPreference = 'Stop'
if (-not $ProtegeDirectory) { throw 'Pass -ProtegeDirectory or set PROTEGE_HOME.' }
if (-not $JavaHome) { throw 'Pass -JavaHome or set JAVA_HOME.' }
$practiceDirectory = Split-Path -Parent $PSScriptRoot
$workspaceDirectory = Split-Path -Parent $practiceDirectory
$sourceOntology = Join-Path $workspaceDirectory 'practice4\PC_Builder_Practice4.owl'
$libraryDirectory = Join-Path $workspaceDirectory 'validation\lib'
$runtimeDirectory = Join-Path $env:TEMP ('pc-builder-practice5-run-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $runtimeDirectory -Force | Out-Null
$snapPlugin = Join-Path $ProtegeDirectory 'plugins\snap-sparql-query-plugin.jar'
$rdfPlugin = Join-Path $ProtegeDirectory 'plugins\rdf-library-3.0.1.jar'
$standardPlugin = Join-Path $ProtegeDirectory 'plugins\sparql-query-plugin-3.0.0.jar'
foreach ($requiredFile in @($snapPlugin,$rdfPlugin,$standardPlugin,$sourceOntology,(Join-Path $JavaHome 'bin\javac.exe'))) {
 if (-not (Test-Path -LiteralPath $requiredFile)) { throw "Required file missing: $requiredFile" }
}
Add-Type -AssemblyName System.IO.Compression.FileSystem
foreach ($pluginPath in @($snapPlugin,$rdfPlugin)) {
 $archive = [IO.Compression.ZipFile]::OpenRead($pluginPath)
 try {
  foreach ($entry in $archive.Entries) {
   if ($entry.Name.EndsWith('.jar')) {
    $dependencyTarget = Join-Path $runtimeDirectory $entry.Name
    [IO.Compression.ZipFileExtensions]::ExtractToFile($entry,$dependencyTarget,$true)
   }
  }
 } finally { $archive.Dispose() }
}
$classPath = "$libraryDirectory\*;$rdfPlugin;$standardPlugin;$runtimeDirectory\*;$runtimeDirectory"
$javacPath = Join-Path $JavaHome 'bin\javac.exe'
$javaPath = Join-Path $JavaHome 'bin\java.exe'
$hashBefore = (Get-FileHash -LiteralPath $sourceOntology -Algorithm SHA256).Hash
& $javacPath -proc:none -encoding UTF-8 -cp $classPath -d $runtimeDirectory (Join-Path $PSScriptRoot 'Practice5.java')
if ($LASTEXITCODE -ne 0) { throw 'Compilation failed' }
$logConfiguration = Join-Path $workspaceDirectory 'validation\logback.xml'
& $javaPath "-Dlogback.configurationFile=$logConfiguration" -cp $classPath Practice5 $sourceOntology $practiceDirectory 2>&1 |
 Tee-Object -FilePath (Join-Path $PSScriptRoot 'run-output.txt')
if ($LASTEXITCODE -ne 0) { throw 'SPARQL validation failed' }
if ((Get-FileHash -LiteralPath $sourceOntology -Algorithm SHA256).Hash -ne $hashBefore) { throw 'The practice4 source unexpectedly changed' }
$hashTargets = @($sourceOntology,(Join-Path $practiceDirectory 'PC_Builder_Asserted.owl'),(Join-Path $practiceDirectory 'PC_Builder_Inferred.owl'))
$hashLines = $hashTargets | ForEach-Object { $hash = Get-FileHash -LiteralPath $_ -Algorithm SHA256; "$($hash.Hash.ToLowerInvariant())  $([IO.Path]::GetFileName($_))" }
$hashLines | Set-Content -LiteralPath (Join-Path $PSScriptRoot 'sha256.txt') -Encoding utf8
