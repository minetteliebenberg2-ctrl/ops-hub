; Ops Hub one-click installer. Ships the exe only - no database.
; Ops Hub creates a fresh empty database beside the exe on first launch.
[Setup]
AppId={{B7E4C2A1-5D3F-4E8A-9C61-0F2A7D4B8E13}
AppName=Ops Hub
AppVersion=1.0
AppPublisher=Ops Hub
DefaultDirName={localappdata}\Ops Hub
DefaultGroupName=Ops Hub
PrivilegesRequired=lowest
DisableProgramGroupPage=yes
OutputDir=output
OutputBaseFilename=Ops Hub Setup
SetupIconFile=..\assets\ops_hub.ico
UninstallDisplayIcon={app}\Ops Hub.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; Flags: checkedonce

[Files]
Source: "..\Ops Hub.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\Ops Hub"; Filename: "{app}\Ops Hub.exe"
Name: "{autodesktop}\Ops Hub"; Filename: "{app}\Ops Hub.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\Ops Hub.exe"; Description: "Launch Ops Hub"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Data (database, backups, exports) is deliberately left behind on uninstall.
