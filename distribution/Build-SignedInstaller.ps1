# Requires a publicly trusted Code Signing certificate accessible through the Windows store.
# No private key export, password arguments, trust-store changes or SmartScreen settings.
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][ValidatePattern('^[A-Fa-f0-9]{40}$')][string]$CertificateThumbprint,
    [Parameter(Mandatory=$true)][string]$SignToolPath,
    [Parameter(Mandatory=$true)][string]$InnoSetupPath,
    [Parameter(Mandatory=$true)][string]$PythonPath,
    [Parameter(Mandatory=$true)]
    [ValidatePattern('^https?://[A-Za-z0-9.-]+(?::[0-9]+)?(/[A-Za-z0-9/_.-]*)?$')][string]$TimestampServer,
    [ValidateSet('CurrentUser','LocalMachine')][string]$CertificateStore='CurrentUser',
    [switch]$CheckOnly
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$radarRoot=Split-Path $PSScriptRoot -Parent
$thumb=$CertificateThumbprint.ToUpperInvariant()

function Resolve-Executable([string]$Path) {
    $resolved=(Resolve-Path -LiteralPath $Path -ErrorAction Stop).Path
    if (-not (Test-Path -LiteralPath $resolved -PathType Leaf)) { throw 'Executable not found.' }
    return $resolved
}
function Assert-Signed([string]$Path) {
    $signature=Get-AuthenticodeSignature -LiteralPath $Path
    if ($signature.Status -ne 'Valid' -or -not $signature.SignerCertificate -or
        $signature.SignerCertificate.Thumbprint -ne $thumb -or -not $signature.TimeStamperCertificate) {
        throw ('Signature, publisher or timestamp verification failed: '+$Path)
    }
    & $script:signTool verify /pa /all /tw $Path
    if ($LASTEXITCODE -ne 0) { throw ('SignTool verification failed: '+$Path) }
}
function Inno-Quote([string]$Value) {
    if ($Value.Contains('"') -or $Value.Contains("`r") -or $Value.Contains("`n")) { throw 'Invalid command argument.' }
    return '$q'+$Value.Replace('$','$$')+'$q'
}

# Check the identity and its trust chain before preparing or changing build artifacts.
$certPath='Cert:\'+$CertificateStore+'\My\'+$thumb
if (-not (Test-Path -LiteralPath $certPath)) { throw 'Code Signing certificate not found in the selected Windows store.' }
$cert=Get-Item -LiteralPath $certPath
if (-not $cert.HasPrivateKey) { throw 'Certificate has no accessible private key. Configure the token or signing provider.' }
if ($cert.NotAfter -le (Get-Date) -or $cert.NotBefore -gt (Get-Date)) { throw 'Certificate is outside its validity period.' }
$eku=@($cert.Extensions | Where-Object { $_.Oid.Value -eq '2.5.29.37' } | ForEach-Object { $_.EnhancedKeyUsages } | ForEach-Object { $_.Value })
if ($eku -notcontains '1.3.6.1.5.5.7.3.3') { throw 'This certificate is not intended for Code Signing.' }
$chain=New-Object System.Security.Cryptography.X509Certificates.X509Chain
try {
    $chain.ChainPolicy.RevocationMode=[System.Security.Cryptography.X509Certificates.X509RevocationMode]::Online
    $chain.ChainPolicy.UrlRetrievalTimeout=[TimeSpan]::FromSeconds(30)
    $null=$chain.ChainPolicy.ApplicationPolicy.Add((New-Object System.Security.Cryptography.Oid '1.3.6.1.5.5.7.3.3'))
    if (-not $chain.Build($cert)) { throw 'Windows could not validate the certificate chain or revocation status.' }
} finally { $chain.Dispose() }
$publisher=$cert.GetNameInfo([System.Security.Cryptography.X509Certificates.X509NameType]::SimpleName,$false)
if ([string]::IsNullOrWhiteSpace($publisher) -or $publisher.Contains("`n") -or $publisher.Contains("`r")) { throw 'Invalid publisher name.' }
$script:signTool=Resolve-Executable $SignToolPath
$inno=Resolve-Executable $InnoSetupPath
$python=Resolve-Executable $PythonPath
Write-Output ('Publisher: '+$publisher)
Write-Output ('Certificate valid until: '+$cert.NotAfter.ToString('yyyy-MM-dd'))
if ($CheckOnly) { Write-Output 'Preflight passed. No files signed or built.'; return }

# Each signed build gets its own output directory; published installers are not replaced.
$buildId=(Get-Date -Format 'yyyyMMdd-HHmmss')+'-'+[Guid]::NewGuid().ToString('N').Substring(0,8)
$output=Join-Path $radarRoot ('dist/signed/'+$buildId)
$payload=Join-Path $radarRoot 'work/installer-build/payload'
Push-Location $radarRoot
try {
    & $python (Join-Path $PSScriptRoot 'build_installer.py')
    if ($LASTEXITCODE -ne 0) { throw 'Payload build failed.' }
    $signArgs=@('sign','/fd','SHA256','/tr',$TimestampServer,'/td','SHA256','/sha1',$thumb,'/s','My','/d','Radar de Leiloes')
    if ($CertificateStore -eq 'LocalMachine') { $signArgs+='/sm' }
    foreach ($name in @('Radar.exe','RadarTray.exe','RadarUpdate.exe')) {
        $file=Join-Path $payload $name
        & $script:signTool @signArgs $file
        if ($LASTEXITCODE -ne 0) { throw ('Signing failed: '+$name) }
        Assert-Signed $file
    }
    # Signing changes bytes; regenerate the payload manifest only after verification.
    $manifest=[ordered]@{}
    Get-ChildItem -LiteralPath $payload -File -Recurse | Sort-Object FullName | ForEach-Object {
        $relative=$_.FullName.Substring($payload.Length+1)
        $manifest[$relative]=(Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
    }
    $manifest | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $radarRoot 'work/installer-build/payload-manifest.json') -Encoding UTF8
    $null=New-Item -ItemType Directory -Path $output
    $command=(Inno-Quote $script:signTool)+' sign /fd SHA256 /tr '+(Inno-Quote $TimestampServer)+' /td SHA256 /sha1 '+$thumb+' /s My /d '+(Inno-Quote 'Radar de Leiloes')
    if ($CertificateStore -eq 'LocalMachine') { $command+=' /sm' }
    $command+=' $f'
    $innoArgs=@('/Q','/DSignedBuild',('/DPublisherName='+$publisher),('/Sradar='+$command),
        ('/DPayload='+$payload),('/DOutput='+$output),('/DIcon='+(Join-Path $payload 'radar.ico')),
        ('/DBootstrapper='+(Join-Path $radarRoot 'work/installer-downloads/MicrosoftEdgeWebview2Setup.exe')),
        (Join-Path $PSScriptRoot 'radar.iss'))
    & $inno @innoArgs
    if ($LASTEXITCODE -ne 0) { throw 'Signed installer build failed. Do not publish the output.' }
    $installers=@(Get-ChildItem -LiteralPath $output -Filter 'Instalar-Radar-de-Leiloes-*-Windows.exe' -File)
    if ($installers.Count -ne 1) { throw 'Expected exactly one installer.' }
    $installer=$installers[0].FullName
    Assert-Signed $installer
    $hash=(Get-FileHash -LiteralPath $installer -Algorithm SHA256).Hash.ToLowerInvariant()
    ($hash+'  '+$installers[0].Name) | Set-Content -LiteralPath ($installer+'.sha256') -Encoding ASCII
    [ordered]@{file=$installers[0].Name;sha256=$hash;publisher=$publisher;certificate=$thumb;status='Valid';timestampVerified=$true;
        createdAt=(Get-Date).ToUniversalTime().ToString('o');smartScreenReputation='Not verified; signature does not guarantee absence of warnings'} |
        ConvertTo-Json | Set-Content -LiteralPath (Join-Path $output 'signature-report.json') -Encoding UTF8
    Write-Output ('Signed and verified: '+$installer)
    Write-Output 'A new signed file may still trigger SmartScreen until reputation accumulates.'
} finally { Pop-Location }
