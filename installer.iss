; CompressTool Installer
#define MyAppName "CompressTool"
#define MyAppVersion "1.1.0"
#define MyAppExeName "压缩解压工具.exe"

[Setup]
AppId={{8F3A2B1C-4D5E-6F7A-8B9C-0D1E2F3A4B5C}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
DefaultDirName={autopf}\本地压缩解压工具
DefaultGroupName=压缩解压工具
DisableProgramGroupPage=yes
OutputDir=installer_output
OutputBaseFilename=压缩解压工具_安装包
Compression=lzma
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
SetupIconFile=app_icon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}

[Tasks]
Name: "desktopicon"; Description: "Create desktop shortcut"; GroupDescription: "Additional icons:"; Flags: unchecked
Name: "rightmenu"; Description: "Register right-click menu"; GroupDescription: "Integration:"; Flags: checkedonce

[Files]
Source: "dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\压缩解压工具"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Uninstall"; Filename: "{uninstallexe}"
Name: "{autodesktop}\压缩解压工具"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Registry]
; 文件夹右键 - 同时注册Directory和Folder确保显示
Root: HKCR; Subkey: "Directory\shell\CompressTool"; ValueType: string; ValueName: ""; ValueData: "压缩到..."; Flags: uninsdeletekey; Tasks: rightmenu
Root: HKCR; Subkey: "Directory\shell\CompressTool"; ValueType: string; ValueName: "Icon"; ValueData: "{app}\{#MyAppExeName}"; Tasks: rightmenu
Root: HKCR; Subkey: "Directory\shell\CompressTool\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" --compress ""%1"""; Tasks: rightmenu
Root: HKCR; Subkey: "Folder\shell\CompressTool"; ValueType: string; ValueName: ""; ValueData: "压缩到..."; Flags: uninsdeletekey; Tasks: rightmenu
Root: HKCR; Subkey: "Folder\shell\CompressTool\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" --compress ""%1"""; Tasks: rightmenu

; 压缩包右键 - 注册到所有文件，确保一定显示
Root: HKCR; Subkey: "*\shell\CompressToolExtract"; ValueType: string; ValueName: ""; ValueData: "解压到..."; Flags: uninsdeletekey; Tasks: rightmenu
Root: HKCR; Subkey: "*\shell\CompressToolExtract"; ValueType: string; ValueName: "Icon"; ValueData: "{app}\{#MyAppExeName}"; Tasks: rightmenu
Root: HKCR; Subkey: "*\shell\CompressToolExtract\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" --extract ""%1"""; Tasks: rightmenu

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch now"; Flags: nowait postinstall skipifsilent
