' Marketing El Gadget - lanzador silencioso (sin ventana de consola)
Set fso = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")

baseDir = fso.GetParentFolderName(WScript.ScriptFullName)
shell.CurrentDirectory = baseDir

cmdLine = "cmd /c "
If fso.FileExists(baseDir & "\venv\Scripts\activate.bat") Then
    cmdLine = cmdLine & "call venv\Scripts\activate.bat && "
End If
cmdLine = cmdLine & "pythonw scripts\marketing_desktop.py"

' 0 = ventana oculta, False = no esperar a que termine
shell.Run cmdLine, 0, False
