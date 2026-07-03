# Install Sotto: copy the packaged app out of the (OneDrive-synced) project into
# %LOCALAPPDATA%\Programs\Sotto and create Start-menu shortcuts.
$ErrorActionPreference = "Stop"

$src = Join-Path $PSScriptRoot "dist\Sotto"
$dst = Join-Path $env:LOCALAPPDATA "Programs\Sotto"
if (-not (Test-Path "$src\Sotto.exe")) { throw "dist\Sotto\Sotto.exe not found - build first" }

# stop a running instance so files aren't locked
Get-Process Sotto -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Milliseconds 500

if (Test-Path $dst) { Remove-Item -Recurse -Force $dst }
New-Item -ItemType Directory -Force (Split-Path $dst) | Out-Null
Copy-Item -Recurse $src $dst
Write-Output "installed -> $dst"

$programs = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs"
$ws = New-Object -ComObject WScript.Shell

$lnk = $ws.CreateShortcut((Join-Path $programs "Sotto.lnk"))
$lnk.TargetPath = "$dst\Sotto.exe"
$lnk.WorkingDirectory = $dst
$lnk.Description = "Sotto - local dictation"
$lnk.Save()
Write-Output "shortcut -> Start menu \ Sotto"

$adminLnkPath = Join-Path $programs "Sotto (administrator).lnk"
$lnk2 = $ws.CreateShortcut($adminLnkPath)
$lnk2.TargetPath = "$dst\Sotto.exe"
$lnk2.WorkingDirectory = $dst
$lnk2.Description = "Sotto - local dictation (can type into elevated apps)"
$lnk2.Save()
# set the RunAsAdministrator flag byte in the .lnk
$bytes = [IO.File]::ReadAllBytes($adminLnkPath)
$bytes[0x15] = $bytes[0x15] -bor 0x20
[IO.File]::WriteAllBytes($adminLnkPath, $bytes)
Write-Output "shortcut -> Start menu \ Sotto (administrator)"
