<#
.SYNOPSIS
    Antigravity Account Switcher & Migration Suite for Windows 10 & 11
    Author: Ethan Carter (https://github.com/Bombhub-apk) & Madgod-xyz
    Description:
        Seamless 1-click Google account switcher & project migration suite for Google Antigravity.
        Features iOS Liquid Glass UI, multi-language support (EN, FA, ZH, ES), and live model quotas.
#>

param (
    [switch]$Usage,
    [switch]$List,
    [string]$Switch,
    [string[]]$SetProjectQuota,
    [string]$LaunchInstance,
    [switch]$StatusJson,
    [switch]$NoRestart,
    [switch]$Save,
    [switch]$Logout,
    [string]$Migrate,
    [switch]$About,
    [switch]$GitHub,
    [switch]$CLI,
    [switch]$IdeTheme,
    [switch]$Help
)

$GitHubRepoUrl = "https://github.com/Bombhub-apk/antigravity-account-switcher"
$AuthorName = "Ethan Carter (https://github.com/Bombhub-apk) & Madgod-xyz"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$AppDir = Join-Path $ScriptDir "app"
$AccountsDir = Join-Path $HOME ".gemini\accounts"
$ManifestPath = Join-Path $AccountsDir "manifest.json"

# -------------------------------------------------------------
# C# Native Windows Credential Manager Interop (advapi32.dll)
# -------------------------------------------------------------
if (-not ([System.Management.Automation.PSTypeName]'WinCred').Type) {
    $csharpCode = @"
    using System;
    using System.Text;
    using System.Runtime.InteropServices;

    public class WinCred {
        [DllImport("advapi32.dll", SetLastError = true, CharSet = CharSet.Unicode)]
        public static extern bool CredRead(string target, int type, int reservedFlag, out IntPtr credentialPtr);

        [DllImport("advapi32.dll", SetLastError = true, CharSet = CharSet.Unicode)]
        public static extern bool CredWrite([In] ref CREDENTIAL userCredential, int flags);

        [DllImport("advapi32.dll", SetLastError = true, CharSet = CharSet.Unicode)]
        public static extern bool CredDelete(string target, int type, int flags);

        [DllImport("advapi32.dll", SetLastError = true)]
        public static extern void CredFree([In] IntPtr cred);

        [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
        public struct CREDENTIAL {
            public int Flags;
            public int Type;
            public string TargetName;
            public string Comment;
            public System.Runtime.InteropServices.ComTypes.FILETIME LastWritten;
            public int CredentialBlobSize;
            public IntPtr CredentialBlob;
            public int Persist;
            public int AttributeCount;
            public IntPtr Attributes;
            public string TargetAlias;
            public string UserName;
        }

        public static string Read(string target) {
            IntPtr credPtr;
            if (!CredRead(target, 1, 0, out credPtr)) return null;
            try {
                CREDENTIAL cred = (CREDENTIAL)Marshal.PtrToStructure(credPtr, typeof(CREDENTIAL));
                byte[] bytes = new byte[cred.CredentialBlobSize];
                Marshal.Copy(cred.CredentialBlob, bytes, 0, cred.CredentialBlobSize);
                string utf8 = Encoding.UTF8.GetString(bytes);
                if (utf8.StartsWith("go-keyring-base64:") || utf8.StartsWith("{")) return utf8;
                return Encoding.Unicode.GetString(bytes);
            } finally {
                CredFree(credPtr);
            }
        }

        public static bool Write(string target, string username, string secret) {
            byte[] bytes = Encoding.UTF8.GetBytes(secret);
            IntPtr secretPtr = Marshal.AllocHGlobal(bytes.Length);
            try {
                Marshal.Copy(bytes, 0, secretPtr, bytes.Length);
                CREDENTIAL cred = new CREDENTIAL();
                cred.Type = 1;
                cred.TargetName = target;
                cred.UserName = username;
                cred.CredentialBlob = secretPtr;
                cred.CredentialBlobSize = bytes.Length;
                cred.Persist = 2;
                return CredWrite(ref cred, 0);
            } finally {
                Marshal.FreeHGlobal(secretPtr);
            }
        }

        public static bool Delete(string target) {
            return CredDelete(target, 1, 0);
        }
    }
"@
    Add-Type -TypeDefinition $csharpCode -Language CSharp
}

if (!(Test-Path $AccountsDir)) {
    New-Item -ItemType Directory -Path $AccountsDir -Force | Out-Null
}

function Get-Manifest {
    if (Test-Path $ManifestPath) {
        try {
            return Get-Content $ManifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
        } catch {
            return @{}
        }
    }
    return @{}
}

function Save-Manifest($manifest) {
    $manifest | ConvertTo-Json -Depth 4 | Set-Content $ManifestPath -Encoding UTF8
}

function Get-CurrentToken {
    $targets = @("gemini:antigravity", "gemini", "antigravity")
    foreach ($t in $targets) {
        $val = [WinCred]::Read($t)
        if ($val) { return $val }
    }
    return $null
}

function Restart-Antigravity {
    Write-Host "🔄 Restarting Google Antigravity..." -ForegroundColor Cyan
    Get-Process -Name "Antigravity" -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 1
    
    $paths = @(
        "$env:LOCALAPPDATA\Programs\Antigravity\Antigravity.exe",
        "$env:ProgramFiles\Antigravity\Antigravity.exe",
        "$env:ProgramFiles(x86)\Antigravity\Antigravity.exe"
    )
    $exe = $paths | Where-Object { Test-Path $_ } | Select-Object -First 1
    if ($exe) {
        Start-Process $exe
    } else {
        Start-Process "Antigravity" -ErrorAction SilentlyContinue
    }
}

function Switch-Account($accountKey) {
    $manifest = Get-Manifest
    $prop = $manifest.PSObject.Properties[$accountKey]
    if (!$prop) {
        Write-Host "❌ Account '$accountKey' not found in manifest." -ForegroundColor Red
        return $false
    }
    $tokenFile = $prop.Value.token_file
    if (!(Test-Path $tokenFile)) {
        Write-Host "❌ Token file missing for '$accountKey'." -ForegroundColor Red
        return $false
    }
    $token = (Get-Content $tokenFile -Raw -Encoding UTF8).Trim()
    
    # Write to both targets for maximum compatibility
    $ok1 = [WinCred]::Write("gemini:antigravity", "antigravity", $token)
    $ok2 = [WinCred]::Write("gemini", "antigravity", $token)
    
    if ($ok1 -or $ok2) {
        Restart-Antigravity
        Write-Host "✓ Successfully switched to $accountKey!" -ForegroundColor Green
        return $true
    } else {
        Write-Host "❌ Failed to write credential to Windows Credential Manager." -ForegroundColor Red
        return $false
    }
}

function Save-CurrentAccount {
    $token = Get-CurrentToken
    if (!$token) {
        Write-Host "❌ No active Antigravity account found. Please sign in to Antigravity first." -ForegroundColor Yellow
        return $false
    }

    # Fetch info using quota engine
    $pyScript = Join-Path $ScriptDir "quota_engine.py"
    $quotaData = $null
    try {
        $rawLines = python $pyScript
        $jsonStr = $rawLines -join "`n"
        $quotaData = $jsonStr | ConvertFrom-Json
    } catch {}

    $email = if ($quotaData -and $quotaData.email) { $quotaData.email } else { "user@antigravity.ai" }
    $tier = if ($quotaData -and $quotaData.tier) { $quotaData.tier } else { "Free" }
    $tierCode = if ($quotaData -and $quotaData.tier_code) { $quotaData.tier_code } else { "free" }
    $remPct = if ($quotaData -and $quotaData.session) { $quotaData.session.remaining_pct } else { 100 }

    $tokenFile = Join-Path $AccountsDir "$($email -replace '[\\/:*?""<>|]', '_').token"
    $token | Set-Content $tokenFile -Encoding UTF8
    
    $manifest = Get-Manifest
    $newEntry = [PSCustomObject]@{
        label = $email
        email = $email
        tier = $tier
        tier_code = $tierCode
        remaining_pct = $remPct
        token_file = $tokenFile
        saved_at = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")
    }
    $manifest | Add-Member -MemberType NoteProperty -Name $email -Value $newEntry -Force
    Save-Manifest $manifest
    Write-Host "✓ Account '$email' saved successfully!" -ForegroundColor Green
    return $true
}

function Logout-And-Add {
    [WinCred]::Delete("gemini:antigravity") | Out-Null
    [WinCred]::Delete("gemini") | Out-Null
    Restart-Antigravity
    Write-Host "✓ Logged out from Antigravity. Please sign in with your other Google account!" -ForegroundColor Green
}

function Show-UsageCLI {
    $pyScript = Join-Path $ScriptDir "quota_engine.py"
    try {
        $rawLines = python $pyScript
        $jsonStr = $rawLines -join "`n"
        $data = $jsonStr | ConvertFrom-Json
        if (!$data -or $data.error) {
            Write-Host "❌ Could not retrieve Antigravity usage. Please check internet connection or sign in." -ForegroundColor Red
            return
        }

        $email = $data.email
        $tier = $data.tier
        $sess = $data.session
        $used = $sess.used_pct
        $rem = $sess.remaining_pct
        $countdown = $sess.resets_in

        function Make-Bar($pct, $width=20) {
            $fill = [math]::Min($width, [math]::Max(0, [math]::Round(($pct / 100.0) * $width)))
            $empty = $width - $fill
            return ("█" * $fill) + ("░" * $empty)
        }

        $bar = Make-Bar $used 22

        Write-Host "`n┌─────────────────────────────────────────────────────────────┐" -ForegroundColor Cyan
        Write-Host "│             ANTIGRAVITY ACCOUNT SUITE • MADGOD-XYZ          │" -ForegroundColor Cyan
        Write-Host "│   Plan: $tier  •  Account: $email" -ForegroundColor Green
        Write-Host "├─────────────────────────────────────────────────────────────┤" -ForegroundColor Cyan
        Write-Host "│  Active Session Quota                                       │" -ForegroundColor White
        Write-Host "│  $used% used ($rem% remaining) • Resets: $countdown" -ForegroundColor Yellow
        Write-Host "│  [$bar] $used%                                 │" -ForegroundColor Cyan
        Write-Host "├─────────────────────────────────────────────────────────────┤" -ForegroundColor Cyan
        Write-Host "│  Model Breakdown                                            │" -ForegroundColor White
        foreach ($p in $data.pools) {
            $pBar = Make-Bar $p.used_pct 16
            Write-Host "│  • $($p.name): $($p.used_pct)% used [$pBar] (Resets: $($p.resets_in))" -ForegroundColor White
        }
        Write-Host "└─────────────────────────────────────────────────────────────┘`n" -ForegroundColor Cyan
    } catch {
        Write-Host "❌ Error running quota engine: $_" -ForegroundColor Red
    }
}

function Open-LiquidGlassUI {
    # Prepare live state payload
    $pyQuota = Join-Path $ScriptDir "quota_engine.py"
    $pyMigrate = Join-Path $ScriptDir "migration_engine.py"
    
    $quotaJson = "{}"
    $convsJson = "[]"
    try {
        $quotaLines = python $pyQuota
        $quotaJson = $quotaLines -join "`n"
    } catch {}
    try {
        $convsLines = python $pyMigrate --list
        $convsJson = $convsLines -join "`n"
    } catch {}

    $manifest = Get-Manifest
    $manifestJson = $manifest | ConvertTo-Json -Depth 4

    # Generate standalone runner html with baked-in data for instant offline launch
    $templateHtml = Get-Content (Join-Path $AppDir "index.html") -Raw -Encoding UTF8
    $injectedScript = '<script>' + "`nwindow.INITIAL_PAYLOAD = { activeAccount: " + $quotaJson + ", savedAccounts: " + $manifestJson + " };`nwindow.INITIAL_CONVERSATIONS = " + $convsJson + ";`n" + '</script>'
    $runtimeHtml = $templateHtml.Replace('<!-- Scripts -->', "$injectedScript`n  <!-- Scripts -->")
    $runtimePath = Join-Path $AppDir "runtime_window.html"
    $runtimeHtml | Set-Content $runtimePath -Encoding UTF8

    # Launch in standalone App mode via Edge or Chrome
    $edgePaths = @(
        "$env:ProgramFiles(x86)\Microsoft\Edge\Application\msedge.exe",
        "$env:ProgramFiles\Microsoft\Edge\Application\msedge.exe"
    )
    $chromePaths = @(
        "$env:LOCALAPPDATA\Google\Chrome\Application\chrome.exe",
        "$env:ProgramFiles\Google\Chrome\Application\chrome.exe",
        "$env:ProgramFiles(x86)\Google\Chrome\Application\chrome.exe"
    )

    $browserExe = ($edgePaths + $chromePaths) | Where-Object { Test-Path $_ } | Select-Object -First 1

    if ($browserExe) {
        $fileUrl = "file:///$($runtimePath -replace '\\', '/')"
        $argsList = "--app=$fileUrl --window-size=620,860 --disable-features=Translate"
        Start-Process $browserExe -ArgumentList $argsList
    } else {
        Start-Process $runtimePath
    }
}

# -------------------------------------------------------------
# CLI Dispatcher
# -------------------------------------------------------------
$cliPy = Join-Path $ScriptDir "cli.py"

if ($Help) {
    if (Test-Path $cliPy) {
        & python $cliPy --help
    } else {
        Write-Host "`nAntigravity Account Switcher CLI" -ForegroundColor Cyan
        Write-Host 'Commands: -Usage, -List, -Switch <email>, -SetProjectQuota <proj> <email>, -LaunchInstance <slot>, -StatusJson, -Save, -Logout' -ForegroundColor White
    }
    exit
}

if ($StatusJson) {
    if (Test-Path $cliPy) {
        & python $cliPy --status-json
    } else {
        $manifest = Get-Manifest
        $manifest | ConvertTo-Json -Depth 5
    }
    exit
}

if ($SetProjectQuota) {
    if (Test-Path $cliPy) {
        & python $cliPy --set-project-quota $SetProjectQuota
    } else {
        Write-Host "❌ cli.py required for setting project quota." -ForegroundColor Red
    }
    exit
}

if ($Usage) {
    if (Test-Path $cliPy) {
        & python $cliPy --usage
    } else {
        Show-UsageCLI
    }
    exit
}

if ($About) {
    Write-Host "`n🚀 Antigravity Account Switcher & Migration Suite" -ForegroundColor Cyan
    Write-Host "👨‍💻 Developed by: $AuthorName" -ForegroundColor Yellow
    Write-Host "⭐ GitHub Repository: $GitHubRepoUrl`n" -ForegroundColor White
    exit
}

if ($GitHub) {
    Start-Process $GitHubRepoUrl
    exit
}

if ($List) {
    if (Test-Path $cliPy) {
        & python $cliPy --list
    } else {
        $manifest = Get-Manifest
        $curr = Get-CurrentToken
        Write-Host "`n🚀 Saved Antigravity Accounts [Windows]" -ForegroundColor Cyan
        Write-Host "👨‍💻 Author: $AuthorName ($GitHubRepoUrl)`n" -ForegroundColor Gray
        foreach ($prop in $manifest.PSObject.Properties) {
            $active = ""
            $tf = $prop.Value.token_file
            if ($curr -and (Test-Path $tf) -and ((Get-Content $tf -Raw -Encoding UTF8).Trim() -eq $curr.Trim())) {
                $active = " [ACTIVE ●]"
            }
            $tier = if ($prop.Value.tier) { "[$($prop.Value.tier)]" } else { "[Free]" }
            Write-Host " • $($prop.Name) $tier$active (Saved: $($prop.Value.saved_at))" -ForegroundColor White
        }
        Write-Host ""
    }
    exit
}

if ($Switch) {
    if (Test-Path $cliPy) {
        $extra = if ($NoRestart) { @("--no-restart") } else { @() }
        & python $cliPy --switch $Switch @extra
    } else {
        Switch-Account $Switch
    }
    exit
}

if ($LaunchInstance) {
    if (Test-Path $cliPy) {
        & python $cliPy --launch-instance $LaunchInstance
    } else {
        & python "$ScriptDir\server.py" --launch-instance $LaunchInstance
    }
    exit
}

if ($Save) {
    if (Test-Path $cliPy) {
        & python $cliPy --save
    } else {
        Save-CurrentAccount
    }
    exit
}

if ($Logout) {
    if (Test-Path $cliPy) {
        & python $cliPy --logout
    } else {
        Logout-And-Add
    }
    exit
}

if ($IdeTheme) {
    if (Test-Path "$ScriptDir\setup_ide_theme.py") {
        & python "$ScriptDir\setup_ide_theme.py"
    } else {
        & python "$HOME\.gemini\antigravity\bin\setup_ide_theme.py"
    }
    exit
}

# Default: Open the new iOS Liquid Glass GUI
Open-LiquidGlassUI

