# ==============================================================================
# Antigravity Account Switcher & Migration Suite - Windows Installer
# Organization: mad-helpers (https://github.com/mad-helpers/antigravity-account-switcher)
# ==============================================================================

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$VbsLauncher = Join-Path $ScriptDir "AntigravitySwitcher.vbs"
$PsScript = Join-Path $ScriptDir "switcher_windows.ps1"
$Desktop = [System.Environment]::GetFolderPath('Desktop')
$StartMenu = [System.Environment]::GetFolderPath('Programs')

Write-Host "`n🚀 Installing Antigravity Account Switcher & Migration Suite..." -ForegroundColor Cyan
Write-Host "👨‍💻 Developed by: mad-helpers (Madgod-xyz & Bombhub-apk)" -ForegroundColor Yellow
Write-Host "🌐 GitHub: https://github.com/mad-helpers/antigravity-account-switcher`n" -ForegroundColor Gray

# 1. Locate Antigravity Icon
$iconPath = "$env:LOCALAPPDATA\Programs\Antigravity\Antigravity.exe"
if (!(Test-Path $iconPath)) {
    $iconPath = "$env:ProgramFiles\Antigravity\Antigravity.exe"
}
if (!(Test-Path $iconPath)) {
    $iconPath = "shell32.dll,44"
}

# 2. Create Desktop Shortcut (.lnk)
$wsh = New-Object -ComObject WScript.Shell
$desktopShortcutPath = Join-Path $Desktop "Antigravity Switcher.lnk"
$shortcut = $wsh.CreateShortcut($desktopShortcutPath)
$shortcut.TargetPath = "wscript.exe"
$shortcut.Arguments = "`"$VbsLauncher`""
$shortcut.WorkingDirectory = $ScriptDir
$shortcut.Description = "Google Antigravity Account Switcher & Project Migration Suite (iOS Liquid Glass)"
$shortcut.IconLocation = "$iconPath,0"
$shortcut.Save()

Write-Host "✓ Desktop shortcut created: $desktopShortcutPath" -ForegroundColor Green

# 3. Create Start Menu Shortcut
$startShortcutPath = Join-Path $StartMenu "Antigravity Switcher.lnk"
$startShortcut = $wsh.CreateShortcut($startShortcutPath)
$startShortcut.TargetPath = "wscript.exe"
$startShortcut.Arguments = "`"$VbsLauncher`""
$startShortcut.WorkingDirectory = $ScriptDir
$startShortcut.Description = "Google Antigravity Account Switcher & Project Migration Suite"
$startShortcut.IconLocation = "$iconPath,0"
$startShortcut.Save()

Write-Host "✓ Start Menu shortcut registered." -ForegroundColor Green

# 4. Register CLI command 'agy-switch'
$binDir = Join-Path $HOME ".gemini\bin"
if (!(Test-Path $binDir)) {
    New-Item -ItemType Directory -Path $binDir -Force | Out-Null
}
$cmdPath = Join-Path $binDir "agy-switch.cmd"
$cmdContent = @"
@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$PsScript" %*
"@
$cmdContent | Set-Content $cmdPath -Encoding ASCII

# Add to user PATH if not present
$userPath = [System.Environment]::GetEnvironmentVariable("Path", "User")
if ($userPath -notlike "*$binDir*") {
    [System.Environment]::SetEnvironmentVariable("Path", "$userPath;$binDir", "User")
    Write-Host "✓ Added $binDir to User PATH." -ForegroundColor Green
}

Write-Host "`n🎉 Installation Complete!" -ForegroundColor Cyan
Write-Host "• Double-click 'Antigravity Switcher' on your Desktop to open the iOS Liquid Glass GUI." -ForegroundColor White
Write-Host "• Or use CLI anywhere: 'agy-switch --usage' or 'agy-switch --list'." -ForegroundColor White
Write-Host ""
