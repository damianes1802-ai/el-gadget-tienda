Set WshShell = CreateObject("WScript.Shell")
strDir = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)

' Activar venv si existe
Dim venvPython
venvPython = strDir & "\venv\Scripts\pythonw.exe"

If CreateObject("Scripting.FileSystemObject").FileExists(venvPython) Then
    WshShell.Run """" & venvPython & """ """ & strDir & "\scripts\marketing_desktop.py""", 0, False
Else
    WshShell.Run "pythonw """ & strDir & "\scripts\marketing_desktop.py""", 0, False
End If
