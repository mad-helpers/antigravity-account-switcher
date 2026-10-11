Set WshShell = CreateObject("WScript.Shell")
strPath = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)
WshShell.CurrentDirectory = strPath
WshShell.Run "pythonw -c ""import chatgpt_account_manager as m; m.launch_chatgpt(instance_num=1)""", 0, True
WScript.Sleep 1500
WshShell.Run "pythonw chatgpt_cdp_daemon.py", 0, False

