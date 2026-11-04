Set WshShell = CreateObject("WScript.Shell")
UserProfile = WshShell.ExpandEnvironmentStrings("%USERPROFILE%")
WshShell.Run "powershell.exe -NoProfile -WindowStyle Hidden -File " & Chr(34) & UserProfile & "\.gemini\antigravity\bin\Start-Codex-With-Theme.ps1" & Chr(34), 0, False
