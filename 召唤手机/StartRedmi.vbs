'===========  StartRedmi.vbs  ===========
Option Explicit
Dim ws, fso, batPath
Set ws  = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

'取 vbs 自身所在目录（支持中文/空格）
batPath = fso.BuildPath(fso.GetParentFolderName(WScript.ScriptFullName), "StartRedmi.bat")

'静默运行（0=隐藏窗口）
ws.Run "cmd /c chcp 65001 > nul & """ & batPath & """", 0, False
'========================================