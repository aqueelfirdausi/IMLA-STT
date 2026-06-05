' Start Dictate.vbs
' Double-click to launch IMLA Dictate with:
'   - pythonw.exe  => NO console / black terminal window
'   - verb "runas" => UAC elevation so the keyboard hook works system-wide

Dim fso, scriptDir
Set fso = CreateObject("Scripting.FileSystemObject")
scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)

' Full path to pythonw.exe (same venv that has all dependencies installed).
Dim pythonw
pythonw = "C:\Users\Administrator\AppData\Local\hermes\hermes-agent\venv\Scripts\pythonw.exe"

' Check it exists before trying to launch.
If Not fso.FileExists(pythonw) Then
    MsgBox "pythonw.exe not found at:" & vbCrLf & pythonw & vbCrLf & vbCrLf & _
           "Update the pythonw path in 'Start Dictate.vbs'.", 16, "IMLA Dictate"
    WScript.Quit
End If

Dim scriptArg
scriptArg = Chr(34) & scriptDir & "\dictate.py" & Chr(34)

' ShellExecute with "runas" triggers UAC elevation.
Set oShell = CreateObject("Shell.Application")
oShell.ShellExecute pythonw, scriptArg, scriptDir, "runas", 1
