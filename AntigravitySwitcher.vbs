' Antigravity Switcher Silent Windows Launcher (v3.0)
' Organization: mad-helpers (https://github.com/mad-helpers/antigravity-account-switcher)
Set WshShell = CreateObject("WScript.Shell")
Set FSO = CreateObject("Scripting.FileSystemObject")
ScriptDir = FSO.GetParentFolderName(WScript.ScriptFullName)
ServerScript = Chr(34) & ScriptDir & "\server.py" & Chr(34)
WshShell.Run "pythonw " & ServerScript, 0, False
