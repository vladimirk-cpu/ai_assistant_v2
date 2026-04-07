[Setup]
AppName=AI Assistant
AppVersion=1.0
DefaultDirName={pf}\AI Assistant
DefaultGroupName=AI Assistant
UninstallDisplayIcon={app}\ai-assistant.exe
OutputDir=..\installer
OutputBaseFilename=AI_Assistant_Setup
Compression=lzma2
SolidCompression=yes
PrivilegesRequired=lowest

[Files]
Source: "..\dist\ai-assistant.exe"; DestDir: "{app}"
Source: "..\config\policies.yaml"; DestDir: "{app}\config"; Flags: recursesubdirs

[Icons]
Name: "{group}\AI Assistant"; Filename: "{app}\ai-assistant.exe"
Name: "{group}\Uninstall AI Assistant"; Filename: "{uninstallexe}"
Name: "{userdesktop}\AI Assistant"; Filename: "{app}\ai-assistant.exe"

[Run]
Filename: "{app}\ai-assistant.exe"; Description: "Запустить AI Assistant"; Flags: postinstall nowait skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}\config"
Type: dirifempty; Name: "{app}"
