Set WshShell = CreateObject("WScript.Shell")
Set FSO = CreateObject("Scripting.FileSystemObject")
strPath = FSO.GetParentFolderName(WScript.ScriptFullName)
batPath = strPath & "\run_bot.bat"
WshShell.CurrentDirectory = strPath
WshShell.Run "cmd.exe /c """ & batPath & """", 0, False
