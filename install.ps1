# ==============================================================================
# Antigravity Account Switcher, Quota & Smart RTL Suite v3.0 - Windows Installer
# Organization: mad-helpers (https://github.com/mad-helpers/antigravity-account-switcher)
# Authors: mad-helpers (Madgod-xyz & Bombhub-apk)
# ==============================================================================

function Install-AntigravitySuite {
    $ErrorActionPreference = "Stop"

    $NoRestartDaemon = $false
    if ($args -contains "-NoRestartDaemon" -or $args -contains "--no-restart-daemon" -or $env:AGY_NO_RESTART_DAEMON -eq "1") {
        $NoRestartDaemon = $true
    }

    Write-Host ""
    Write-Host "[*] Installing Antigravity Account Switcher, Quota & Smart RTL Suite v3.0..." -ForegroundColor Cyan
    Write-Host "[*] Organization: mad-helpers (Madgod-xyz & Bombhub-apk)" -ForegroundColor Yellow
    Write-Host "[*] Repository:   https://github.com/mad-helpers/antigravity-account-switcher" -ForegroundColor Gray
    Write-Host ""

    $CandidateRoot = $PSScriptRoot
    if (-not $CandidateRoot -and $MyInvocation.MyCommand.Path) {
        $CandidateRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
    }

    $IsLocalRepo = $false
    if ($CandidateRoot -and (Test-Path (Join-Path $CandidateRoot "ag_suite\__init__.py"))) {
        $IsLocalRepo = $true
    }

    $GeminiRoot = Join-Path $HOME ".gemini"
    if (-not (Test-Path $GeminiRoot)) {
        New-Item -ItemType Directory -Path $GeminiRoot -Force | Out-Null
    }

    $TmpDir = $null
    try {
        if ($IsLocalRepo) {
            $ScriptDir = $CandidateRoot
            Write-Host "[*] Using local repository checkout: $ScriptDir" -ForegroundColor Gray
        } else {
            $InstallDir = Join-Path $GeminiRoot "antigravity-account-switcher"
            Write-Host "[*] Bootstrapping repository from GitHub (main branch) to $InstallDir..." -ForegroundColor Cyan
            [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

            $bootstrapped = $false
            $gitCmd = Get-Command git -ErrorAction SilentlyContinue
            if ($gitCmd) {
                try {
                    if (Test-Path (Join-Path $InstallDir ".git")) {
                        & git -C $InstallDir fetch origin main --depth 1 2>$null
                        & git -C $InstallDir reset --hard origin/main 2>$null
                    } else {
                        if (Test-Path $InstallDir) {
                            Remove-Item -Path $InstallDir -Recurse -Force -ErrorAction SilentlyContinue
                        }
                        & git clone --branch main --depth 1 "https://github.com/mad-helpers/antigravity-account-switcher.git" $InstallDir 2>$null
                    }
                    if (Test-Path (Join-Path $InstallDir "ag_suite\__init__.py")) {
                        $bootstrapped = $true
                        Write-Host "[OK] Synchronized repository via git (branch: main)." -ForegroundColor Green
                    }
                } catch {
                    $bootstrapped = $false
                }
            }

            if (-not $bootstrapped) {
                $TmpDir = Join-Path ([System.IO.Path]::GetTempPath()) ("agy-suite-install-" + [guid]::NewGuid().ToString("N"))
                New-Item -ItemType Directory -Path $TmpDir -Force | Out-Null
                $TmpZip = Join-Path $TmpDir "main.zip"
                $TmpExtract = Join-Path $TmpDir "extract"
                $ZipUrl = "https://github.com/mad-helpers/antigravity-account-switcher/archive/refs/heads/main.zip"

                Write-Host "[*] Downloading archive $ZipUrl..." -ForegroundColor Cyan
                Invoke-WebRequest -UseBasicParsing -Uri $ZipUrl -OutFile $TmpZip
                Expand-Archive -Path $TmpZip -DestinationPath $TmpExtract -Force

                $NestedRoot = Join-Path $TmpExtract "antigravity-account-switcher-main"
                if (-not (Test-Path $NestedRoot)) {
                    $firstChild = Get-ChildItem -Path $TmpExtract -Directory | Select-Object -First 1
                    if ($firstChild) {
                        $NestedRoot = $firstChild.FullName
                    }
                }

                if (-not (Test-Path (Join-Path $NestedRoot "ag_suite\__init__.py"))) {
                    throw "Downloaded archive from main.zip did not contain ag_suite\__init__.py."
                }

                if (-not (Test-Path $InstallDir)) {
                    New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null
                }
                Copy-Item -Path (Join-Path $NestedRoot "*") -Destination $InstallDir -Recurse -Force
                Write-Host "[OK] Extracted main.zip into $InstallDir" -ForegroundColor Green
            }

            $ScriptDir = $InstallDir
        }

        $TargetApp = Join-Path $GeminiRoot "antigravity"
        $TargetBin = Join-Path $TargetApp "bin"
        $TargetAgSuite = Join-Path $TargetBin "ag_suite"
        $TargetLegacyChatgpt = Join-Path $TargetBin "legacy\chatgpt"
        $TargetAppUi = Join-Path $TargetBin "app"
        $TargetFonts = Join-Path $TargetBin "assets\fonts"
        $CliBinDir = Join-Path $GeminiRoot "bin"
        $PluginDest = Join-Path $GeminiRoot "config\plugins\antigravity-account-suite"
        $SkillDest = Join-Path $GeminiRoot "config\skills\antigravity-account-suite"

        $Desktop = [System.Environment]::GetFolderPath("Desktop")
        $StartMenu = [System.Environment]::GetFolderPath("Programs")
        $StartupFolder = [System.Environment]::GetFolderPath("Startup")

        # ----------------------------------------------------------------------
        # 1. Create Target Directories & Deploy Runtime Packages/Files
        # ----------------------------------------------------------------------
        foreach ($dir in @($TargetApp, $TargetBin, $TargetAgSuite, $TargetLegacyChatgpt, $TargetAppUi, $TargetFonts, $CliBinDir, $PluginDest, $SkillDest)) {
            if (-not (Test-Path $dir)) {
                New-Item -ItemType Directory -Path $dir -Force | Out-Null
            }
        }

        $srcAgSuite = Join-Path $ScriptDir "ag_suite"
        if (Test-Path $srcAgSuite) {
            Get-ChildItem -Path $srcAgSuite -Filter "*.py" -File | ForEach-Object {
                Copy-Item $_.FullName -Destination (Join-Path $TargetAgSuite $_.Name) -Force
            }
        }

        $srcLegacyChatgpt = Join-Path $ScriptDir "legacy\chatgpt"
        if (Test-Path $srcLegacyChatgpt) {
            Get-ChildItem -Path $srcLegacyChatgpt -File | ForEach-Object {
                Copy-Item $_.FullName -Destination (Join-Path $TargetLegacyChatgpt $_.Name) -Force
            }
        }

        Get-ChildItem -Path $ScriptDir -Filter "*.py" -File | Where-Object {
            $_.Name -notmatch "^(test_|_verify_|inspect_|check_|compare_|deep_audit|diff_servers|dry_run|build_injector|setup_ide_theme)"
        } | ForEach-Object {
            Copy-Item $_.FullName -Destination (Join-Path $TargetBin $_.Name) -Force
        }

        foreach ($runtimeFile in @(
            "antigravity_quota_injector.js",
            "switcher_windows.ps1",
            "AntigravitySwitcher.vbs",
            "AntigravitySwitcher.bat",
            "antigravity_quota_autostart.vbs"
        )) {
            $src = Join-Path $ScriptDir $runtimeFile
            if (Test-Path $src) {
                Copy-Item $src -Destination (Join-Path $TargetBin $runtimeFile) -Force
            }
        }

        $injectorSrc = Join-Path $ScriptDir "antigravity_quota_injector.js"
        if (Test-Path $injectorSrc) {
            Copy-Item $injectorSrc -Destination (Join-Path $TargetApp "antigravity_quota_injector.js") -Force
        }

        $srcAppDir = Join-Path $ScriptDir "app"
        if (Test-Path $srcAppDir) {
            Copy-Item (Join-Path $srcAppDir "*") -Destination $TargetAppUi -Recurse -Force
            $staleRuntimeHtml = Join-Path $TargetAppUi "runtime_window.html"
            if (Test-Path $staleRuntimeHtml) {
                Remove-Item $staleRuntimeHtml -Force -ErrorAction SilentlyContinue
            }
        }

        $srcFontsDir = Join-Path $ScriptDir "assets\fonts"
        if (Test-Path $srcFontsDir) {
            Copy-Item (Join-Path $srcFontsDir "*") -Destination $TargetFonts -Recurse -Force
        }

        Write-Host "[OK] Deployed ag_suite, runtime modules, UI assets, and local fonts to $TargetBin" -ForegroundColor Green

        # ----------------------------------------------------------------------
        # 2. Register Global CLI Binaries (agy-switch.cmd & agy-quota.cmd)
        # ----------------------------------------------------------------------
        $agySwitchCmd = Join-Path $CliBinDir "agy-switch.cmd"
        $agyQuotaCmd = Join-Path $CliBinDir "agy-quota.cmd"

        $switchCmdContent = @"
@echo off
setlocal
set "TARGET_CLI=%USERPROFILE%\.gemini\antigravity\bin\cli.py"
if "%~1"=="" (
    python "%TARGET_CLI%" --gui
) else (
    python "%TARGET_CLI%" %*
)
endlocal
"@
        Set-Content -Path $agySwitchCmd -Value $switchCmdContent -Encoding ASCII

        $quotaCmdContent = @"
@echo off
setlocal
set "TARGET_CLI=%USERPROFILE%\.gemini\antigravity\bin\cli.py"
if "%~1"=="" (
    python "%TARGET_CLI%" --usage
) else (
    python "%TARGET_CLI%" %*
)
endlocal
"@
        Set-Content -Path $agyQuotaCmd -Value $quotaCmdContent -Encoding ASCII

        $userPath = [System.Environment]::GetEnvironmentVariable("Path", "User")
        if (-not $userPath) { $userPath = "" }
        if ($userPath -notlike "*$CliBinDir*") {
            $newPath = if ($userPath) { "$userPath;$CliBinDir" } else { $CliBinDir }
            [System.Environment]::SetEnvironmentVariable("Path", $newPath, "User")
            Write-Host "[OK] Added $CliBinDir to User PATH." -ForegroundColor Green
        }
        if ($env:PATH -notlike "*$CliBinDir*") {
            $env:PATH = "$CliBinDir;$env:PATH"
        }
        Write-Host "[OK] Registered CLI commands: agy-switch & agy-quota" -ForegroundColor Green

        # ----------------------------------------------------------------------
        # 3. Deploy Native Antigravity 2.33+ Plugin & Skill
        # ----------------------------------------------------------------------
        $srcPluginDir = Join-Path $ScriptDir "plugin"
        if (Test-Path $srcPluginDir) {
            Copy-Item (Join-Path $srcPluginDir "*") -Destination $PluginDest -Recurse -Force
            if (Test-Path $srcFontsDir) {
                foreach ($fontDest in @(
                    (Join-Path $PluginDest "assets\fonts"),
                    (Join-Path $PluginDest "sidecars\account-suite\fonts")
                )) {
                    if (-not (Test-Path $fontDest)) {
                        New-Item -ItemType Directory -Path $fontDest -Force | Out-Null
                    }
                    Copy-Item (Join-Path $srcFontsDir "*") -Destination $fontDest -Recurse -Force
                }
            }

            $mcpServerPath = (Join-Path $TargetBin "mcp_server.py") -replace "\\", "\\"
            $mcpJsonLines = @(
                "{",
                "  `"mcpServers`": {",
                "    `"antigravity-account-suite`": {",
                "      `"command`": `"python`",",
                "      `"args`": [",
                "        `"$mcpServerPath`"",
                "      ],",
                "      `"env`": {",
                "        `"PYTHONIOENCODING`": `"utf-8`"",
                "      }",
                "    }",
                "  }",
                "}"
            )
            $mcpConfigPath = Join-Path $PluginDest "mcp_config.json"
            [System.IO.File]::WriteAllLines($mcpConfigPath, $mcpJsonLines, (New-Object System.Text.UTF8Encoding($false)))
            Write-Host "[OK] Deployed native Antigravity plugin to $PluginDest" -ForegroundColor Green
        }

        $srcSkillFile = Join-Path $ScriptDir "skills\antigravity-account-suite\SKILL.md"
        if (Test-Path $srcSkillFile) {
            Copy-Item $srcSkillFile -Destination (Join-Path $SkillDest "SKILL.md") -Force
            Write-Host "[OK] Installed SKILL.md to $SkillDest" -ForegroundColor Green
        }

        # ----------------------------------------------------------------------
        # 4. Write Launch-Antigravity.vbs & Shortcuts (--remote-debugging-port=0)
        # ----------------------------------------------------------------------
        $launchVbsPath = Join-Path $TargetBin "Launch-Antigravity.vbs"
        $launchVbsContent = @"
Option Explicit
Dim shell, fso, env, exe, args, i, arg
Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
Set env = shell.Environment("PROCESS")
env("GOMEMLIMIT") = "3GiB"
env("GOGC") = "50"

exe = shell.ExpandEnvironmentStrings("%LOCALAPPDATA%\Programs\Antigravity\Antigravity.exe")
If Not fso.FileExists(exe) Then
    exe = shell.ExpandEnvironmentStrings("%ProgramFiles%\Antigravity\Antigravity.exe")
End If
If Not fso.FileExists(exe) Then
    exe = shell.ExpandEnvironmentStrings("%ProgramFiles(x86)%\Antigravity\Antigravity.exe")
End If

args = " --remote-debugging-port=0"
For i = 0 To WScript.Arguments.Count - 1
    arg = WScript.Arguments(i)
    If LCase(arg) <> "--remote-debugging-port=0" Then
        args = args & " " & Chr(34) & arg & Chr(34)
    End If
Next

If fso.FileExists(exe) Then
    shell.Run Chr(34) & exe & Chr(34) & args, 1, False
End If
"@
        Set-Content -Path $launchVbsPath -Value $launchVbsContent -Encoding ASCII

        $antigravityCandidates = @(
            "$env:LOCALAPPDATA\Programs\Antigravity\Antigravity.exe",
            "$env:ProgramFiles\Antigravity\Antigravity.exe",
            "${env:ProgramFiles(x86)}\Antigravity\Antigravity.exe"
        )
        $antigravityExe = $antigravityCandidates | Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1
        $iconPath = if ($antigravityExe) { "$antigravityExe,0" } else { "shell32.dll,44" }

        $wsh = New-Object -ComObject WScript.Shell
        $deployedSwitcherVbs = Join-Path $TargetBin "AntigravitySwitcher.vbs"

        foreach ($lnkPath in @(
            (Join-Path $Desktop "Antigravity Switcher.lnk"),
            (Join-Path $StartMenu "Antigravity Switcher.lnk")
        )) {
            try {
                $sc = $wsh.CreateShortcut($lnkPath)
                $sc.TargetPath = "wscript.exe"
                $sc.Arguments = "`"$deployedSwitcherVbs`""
                $sc.WorkingDirectory = $TargetBin
                $sc.Description = "Google Antigravity Account Switcher & Quota Suite v3.0 (Liquid Glass)"
                $sc.IconLocation = $iconPath
                $sc.Save()
            } catch {}
        }
        Write-Host "[OK] Updated Desktop & Start Menu shortcuts for Antigravity Switcher." -ForegroundColor Green

        if ($antigravityExe) {
            $agyWorkingDir = Split-Path -Parent $antigravityExe
            foreach ($agyLnkPath in @(
                (Join-Path $Desktop "Antigravity.lnk"),
                (Join-Path $StartMenu "Antigravity.lnk")
            )) {
                try {
                    $sc = $wsh.CreateShortcut($agyLnkPath)
                    $sc.TargetPath = "wscript.exe"
                    $sc.Arguments = "`"$launchVbsPath`" --remote-debugging-port=0"
                    $sc.WorkingDirectory = $agyWorkingDir
                    $sc.Description = "Google Antigravity IDE (CDP HUD & Smart RTL v3 Enabled)"
                    $sc.IconLocation = "$antigravityExe,0"
                    $sc.Save()
                } catch {}
            }
            Write-Host "[OK] Updated Antigravity shortcuts with Launch-Antigravity.vbs (--remote-debugging-port=0)." -ForegroundColor Green
        }

        # ----------------------------------------------------------------------
        # 5. Startup Cleanup, Scheduled Task (AntigravityQuotaMonitor) & Daemon
        # ----------------------------------------------------------------------
        $dupStartupLnk = Join-Path $StartupFolder "AntigravityQuotaMonitor.lnk"
        if (Test-Path $dupStartupLnk) {
            Remove-Item $dupStartupLnk -Force -ErrorAction SilentlyContinue
        }

        $autostartVbsPath = Join-Path $StartupFolder "antigravity_quota_autostart.vbs"
        $autostartVbsContent = @"
Set WshShell = CreateObject("WScript.Shell")
WshShell.Run "schtasks.exe /Run /TN AntigravityQuotaMonitor", 0, False
"@
        try {
            Set-Content -Path $autostartVbsPath -Value $autostartVbsContent -Encoding ASCII
        } catch {}

        $pythonwCmd = Get-Command pythonw.exe -ErrorAction SilentlyContinue
        $pythonwPath = if ($pythonwCmd) { $pythonwCmd.Source } else { "pythonw.exe" }
        $daemonPyPath = Join-Path $TargetBin "sync_daemon.py"

        $taskRegistered = $false
        try {
            $trArg = "`"$pythonwPath`" `"$daemonPyPath`""
            & schtasks.exe /Create /TN "AntigravityQuotaMonitor" /TR $trArg /SC ONLOGON /F 2>$null | Out-Null
            if ($LASTEXITCODE -eq 0) {
                $taskRegistered = $true
                Write-Host "[OK] Registered Scheduled Task 'AntigravityQuotaMonitor'." -ForegroundColor Green
            }
        } catch {}

        if (-not $taskRegistered) {
            try {
                $action = New-ScheduledTaskAction -Execute $pythonwPath -Argument "`"$daemonPyPath`"" -WorkingDirectory $TargetBin
                $trigger = New-ScheduledTaskTrigger -AtLogOn
                $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit ([TimeSpan]::Zero)
                Register-ScheduledTask -TaskName "AntigravityQuotaMonitor" -Action $action -Trigger $trigger -Settings $settings -Force -ErrorAction Stop | Out-Null
                $taskRegistered = $true
                Write-Host "[OK] Registered Scheduled Task 'AntigravityQuotaMonitor' via ScheduledTasks module." -ForegroundColor Green
            } catch {
                $fallbackAutostart = @"
Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = "$TargetBin"
WshShell.Run Chr(34) & "$pythonwPath" & Chr(34) & " " & Chr(34) & "$daemonPyPath" & Chr(34), 0, False
"@
                try {
                    Set-Content -Path $autostartVbsPath -Value $fallbackAutostart -Encoding ASCII
                } catch {}
                Write-Host "[!] Non-admin fallback: configured direct daemon launch in Startup folder." -ForegroundColor Yellow
            }
        }

        if (-not $NoRestartDaemon) {
            # Restart ONLY sync_daemon.py; NEVER touch Antigravity.exe or language_server.exe
            try {
                $existingDaemons = Get-CimInstance Win32_Process -Filter "Name = 'pythonw.exe' OR Name = 'python.exe'" -ErrorAction SilentlyContinue |
                    Where-Object { $_.CommandLine -like "*sync_daemon.py*" }
                foreach ($proc in $existingDaemons) {
                    Stop-Process -Id $proc.ProcessId -Force -ErrorAction SilentlyContinue
                }
            } catch {}

            Start-Sleep -Milliseconds 300
            $started = $false
            if ($taskRegistered) {
                try {
                    & schtasks.exe /Run /TN "AntigravityQuotaMonitor" 2>$null | Out-Null
                    if ($LASTEXITCODE -eq 0) { $started = $true }
                } catch {}
            }
            if (-not $started) {
                try {
                    $wsh.CurrentDirectory = $TargetBin
                    $wsh.Run("`"$pythonwPath`" `"$daemonPyPath`"", 0, $false) | Out-Null
                } catch {}
            }

            $healthy = $false
            $deadline = (Get-Date).AddSeconds(8)
            while ((Get-Date) -lt $deadline) {
                try {
                    $resp = Invoke-WebRequest -Uri "http://127.0.0.1:39281/health" -UseBasicParsing -TimeoutSec 2 -ErrorAction Stop
                    if ($resp.StatusCode -eq 200) {
                        $healthy = $true
                        break
                    }
                } catch {}
                Start-Sleep -Milliseconds 400
            }

            if ($healthy) {
                Write-Host "[OK] Quota & CDP Sync Daemon is online at http://127.0.0.1:39281/health" -ForegroundColor Green
            } else {
                Write-Host "[!] Daemon started in background; health endpoint warming up." -ForegroundColor Yellow
            }
        } else {
            Write-Host "[*] Skipped daemon restart (-NoRestartDaemon)." -ForegroundColor Gray
        }

        Write-Host ""
        Write-Host "[OK] Installation Complete (v3.0.0)!" -ForegroundColor Cyan
        Write-Host "  - CLI: 'agy-quota', 'agy-switch --doctor', 'agy-switch --status-json', 'agy-switch --gui'" -ForegroundColor White
        Write-Host "  - Sidecar Aux Pane: sidecar://antigravity-account-suite/account-suite/" -ForegroundColor White
        Write-Host ""
    } finally {
        if ($TmpDir -and (Test-Path $TmpDir)) {
            Remove-Item -Path $TmpDir -Recurse -Force -ErrorAction SilentlyContinue
        }
    }
}

Install-AntigravitySuite @args
