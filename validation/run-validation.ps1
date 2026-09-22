param([string]$ProtegeDirectory = 'C:\Users\Ermolz\Desktop\Protege-5.6.9')
$ErrorActionPreference = 'Stop'
$validationDirectory = $PSScriptRoot
$workspaceDirectory = Split-Path -Parent $validationDirectory
$libraryDirectory = Join-Path $validationDirectory 'lib'
New-Item -ItemType Directory -Path $libraryDirectory -Force | Out-Null
Add-Type -AssemblyName System.IO.Compression.FileSystem
$bundleNames = @('owlapi-osgidistribution.jar','guava.jar','org.apache.servicemix.bundles.javax-inject.jar','slf4j-api.jar','logback-classic.jar','logback-core.jar')
foreach ($bundleName in $bundleNames) {
    Copy-Item -LiteralPath (Join-Path $ProtegeDirectory "bundles\$bundleName") -Destination (Join-Path $libraryDirectory $bundleName) -Force
}
$hermitName = 'org.semanticweb.hermit-1.4.3.456.jar'
Copy-Item -LiteralPath (Join-Path $ProtegeDirectory "plugins\$hermitName") -Destination (Join-Path $libraryDirectory $hermitName) -Force
foreach ($containerName in @('owlapi-osgidistribution.jar',$hermitName)) {
    $archive = [IO.Compression.ZipFile]::OpenRead((Join-Path $libraryDirectory $containerName))
    try {
        foreach ($entry in $archive.Entries) {
            if ($entry.FullName.EndsWith('.jar')) {
                $destinationPath = Join-Path $libraryDirectory ([IO.Path]::GetFileName($entry.FullName))
                [IO.Compression.ZipFileExtensions]::ExtractToFile($entry,$destinationPath,$true)
            }
        }
    } finally { $archive.Dispose() }
}
$javaClassPath = "$libraryDirectory\*;$validationDirectory"
& javac -proc:none -encoding UTF-8 -cp $javaClassPath -d $validationDirectory (Join-Path $validationDirectory 'VerifyOntology.java')
if ($LASTEXITCODE -ne 0) { throw "Compilation failed: $LASTEXITCODE" }
$logConfiguration = Join-Path $validationDirectory 'logback.xml'
$resultPath = Join-Path $validationDirectory 'reasoner-output.txt'
& java "-Dlogback.configurationFile=$logConfiguration" -cp $javaClassPath VerifyOntology (Join-Path $workspaceDirectory 'PC_Builder.owl') 2>&1 | Tee-Object -FilePath $resultPath
if ($LASTEXITCODE -ne 0) { throw "Validation failed: $LASTEXITCODE" }
Get-FileHash -LiteralPath (Join-Path $workspaceDirectory 'PC_Builder.owl') -Algorithm SHA256 | Format-List | Out-File -LiteralPath (Join-Path $validationDirectory 'owl-sha256.txt')
