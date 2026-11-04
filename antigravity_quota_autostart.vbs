Set WshShell = CreateObject("WScript.Shell")
WshShell.Run "schtasks.exe /Run /TN AntigravityQuotaMonitor", 0, False
