<#
.SYNOPSIS
    Antigravity Account Switcher, 6-Pool Quota & Smart RTL Suite v3.0 for Windows 10 & 11
    Organization: mad-helpers (https://github.com/mad-helpers/antigravity-account-switcher)
    Authors: mad-helpers (Madgod-xyz & Bombhub-apk)
    Description:
        Seamless 1-click Google account switcher, 6-pool real-time model quotas, and project migration suite for Google Antigravity.
#>

param (
    [switch]$Usage,
    [switch]$List,
    [switch]$Doctor,
    [string]$Switch,
    [string[]]$SetProjectQuota,
    [string]$LaunchInstance,
    [switch]$StatusJson,
    [switch]$NoRestart,
    [switch]$NoSwitch,
    [switch]$Save,
    [switch]$Logout,
    [string]$Migrate,
    [switch]$About,
    [switch]$GitHub,
    [switch]$CLI,
    [switch]$Help
)

$GitHubRepoUrl = "https://github.com/mad-helpers/antigravity-account-switcher"
$AuthorName = "mad-helpers (Madgod-xyz & Bombhub-apk)"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
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
    Write-Host "🔄 Restarting Google Antigravity (--remote-debugging-port=0)..." -ForegroundColor Cyan
    Get-Process -Name "Antigravity" -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 1

    $paths = @(
        "$env:LOCALAPPDATA\Programs\Antigravity\Antigravity.exe",
        "$env:ProgramFiles\Antigravity\Antigravity.exe",
        "${env:ProgramFiles(x86)}\Antigravity\Antigravity.exe"
    )
    $exe = $paths | Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1
    if ($exe) {
        Start-Process $exe -ArgumentList "--remote-debugging-port=0"
    } else {
        Start-Process "Antigravity" -ArgumentList "--remote-debugging-port=0" -ErrorAction SilentlyContinue
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

    $ok1 = [WinCred]::Write("gemini:antigravity", "antigravity", $token)
    $ok2 = [WinCred]::Write("gemini", "antigravity", $token)
    $ok3 = [WinCred]::Write("antigravity", "antigravity", $token)

    if ($ok1 -or $ok2 -or $ok3) {
        if (-not $NoRestart) {
            Restart-Antigravity
        }
        Write-Host "✓ Successfully switched to $accountKey!" -ForegroundColor Green
        return $true
    } else {
        Write-Host "❌ Failed to write credential to Windows Credential Manager." -ForegroundColor Red
        return $false
    }
}

function Open-LiquidGlassUI {
    $cliPy = Join-Path $ScriptDir "cli.py"
    if (Test-Path $cliPy) {
        & python $cliPy --gui
        return
    }

    $serverPy = Join-Path $ScriptDir "server.py"
    $controlUrl = "http://127.0.0.1:39285/index.html"
    $stateUrl = "http://127.0.0.1:39285/api/state"

    $ready = $false
    try {
        $resp = Invoke-WebRequest -Uri $stateUrl -UseBasicParsing -TimeoutSec 1 -ErrorAction Stop
        if ($resp.StatusCode -eq 200) { $ready = $true }
    } catch {}

    if (-not $ready -and (Test-Path $serverPy)) {
        $pyw = Get-Command pythonw.exe -ErrorAction SilentlyContinue
        $pyExe = if ($pyw) { $pyw.Source } else { "python.exe" }
        Start-Process $pyExe -ArgumentList "`"$serverPy`" --server-only" -WorkingDirectory $ScriptDir -WindowStyle Hidden
        for ($i = 0; $i -lt 12; $i++) {
            Start-Sleep -Milliseconds 250
            try {
                $resp = Invoke-WebRequest -Uri $stateUrl -UseBasicParsing -TimeoutSec 1 -ErrorAction Stop
                if ($resp.StatusCode -eq 200) { break }
            } catch {}
        }
    }

    $edgePaths = @(
        "${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe",
        "$env:ProgramFiles\Microsoft\Edge\Application\msedge.exe"
    )
    $chromePaths = @(
        "$env:LOCALAPPDATA\Google\Chrome\Application\chrome.exe",
        "$env:ProgramFiles\Google\Chrome\Application\chrome.exe",
        "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe"
    )
    $browserExe = ($edgePaths + $chromePaths) | Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1
    if ($browserExe) {
        Start-Process $browserExe -ArgumentList "--app=$controlUrl --window-size=620,860 --disable-features=Translate"
    } else {
        Start-Process $controlUrl
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
        Write-Host "`nAntigravity Account Switcher & Quota Monitor CLI v3.0 ($AuthorName)" -ForegroundColor Cyan
        Write-Host "Commands: -Usage, -List, -Doctor, -Switch <email>, -SetProjectQuota <proj> <email>, -LaunchInstance <slot>, -StatusJson, -Save, -Logout" -ForegroundColor White
    }
    exit
}

if ($Doctor) {
    if (Test-Path $cliPy) {
        & python $cliPy --doctor
    } else {
        & python (Join-Path $ScriptDir "quota_engine.py") --doctor
    }
    exit
}

if ($StatusJson) {
    if (Test-Path $cliPy) {
        & python $cliPy --status-json
    }
    exit
}

if ($SetProjectQuota) {
    if (Test-Path $cliPy) {
        $extra = if ($NoSwitch) { @("--no-switch") } else { @() }
        & python $cliPy --set-project-quota $SetProjectQuota @extra
    }
    exit
}

if ($Usage) {
    if (Test-Path $cliPy) {
        & python $cliPy --usage
    }
    exit
}

if ($About) {
    Write-Host "`n🚀 Antigravity Account Switcher, Quota & Smart RTL Suite v3.0" -ForegroundColor Cyan
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
    }
    exit
}

if ($Switch) {
    if (Test-Path $cliPy) {
        $extra = if ($NoRestart) { @("--no-restart") } else { @("--restart") }
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
    }
    exit
}

if ($Logout) {
    if (Test-Path $cliPy) {
        & python $cliPy --logout
    } else {
        [WinCred]::Delete("gemini:antigravity") | Out-Null
        [WinCred]::Delete("gemini") | Out-Null
        [WinCred]::Delete("antigravity") | Out-Null
        Restart-Antigravity
    }
    exit
}

Open-LiquidGlassUI
