# Installs the bundled EB Garamond fonts for the current user (no admin rights needed),
# so LibreOffice and Word render the CV with the right typeface. Safe to run more than once.
$src = Join-Path $PSScriptRoot "..\assets\fonts"
$dest = Join-Path $env:LOCALAPPDATA "Microsoft\Windows\Fonts"
$reg = "HKCU:\Software\Microsoft\Windows NT\CurrentVersion\Fonts"
New-Item -ItemType Directory -Force $dest | Out-Null
if (-not (Test-Path $reg)) { New-Item -Force $reg | Out-Null }

$names = @{
    "EBGaramond-Regular.ttf"    = "EB Garamond Regular (TrueType)"
    "EBGaramond-Bold.ttf"       = "EB Garamond Bold (TrueType)"
    "EBGaramond-Italic.ttf"     = "EB Garamond Italic (TrueType)"
    "EBGaramond-BoldItalic.ttf" = "EB Garamond Bold Italic (TrueType)"
}
foreach ($file in $names.Keys) {
    $target = Join-Path $dest $file
    if (-not (Test-Path $target)) { Copy-Item (Join-Path $src $file) $target }
    Set-ItemProperty -Path $reg -Name $names[$file] -Value $target
}
Write-Output "EB Garamond installed for the current user in $dest"
