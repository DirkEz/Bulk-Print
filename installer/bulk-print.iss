#define MyAppName "Bulk Print"
#define MyAppVersion GetEnv("APP_VERSION")
#define MyAppPublisher "Deyvo"
#define MyAppExeName "BulkPrint.exe"

[Setup]
AppId={{BE3FA6EC-D649-4023-A150-B2D4320EDB91}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=..\dist
OutputBaseFilename=BulkPrint-Setup-v{#MyAppVersion}
SetupIconFile=..\assets\deyvo-logo.ico
Compression=lzma
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
ArchitecturesInstallIn64BitMode=x64
UninstallDisplayIcon={app}\{#MyAppExeName}
CloseApplications=yes
RestartApplications=no
AlwaysRestart=no

[Languages]
Name: "dutch"; MessagesFile: "compiler:Languages\Dutch.isl"

[Tasks]
Name: "desktopicon"; Description: "Maak een snelkoppeling op het bureaublad"; GroupDescription: "Extra opties:"; Flags: unchecked

[InstallDelete]
Type: files; Name: "{app}\BulkPrint.exe"
Type: filesandordirs; Name: "{app}\_internal"

[Files]
Source: "..\dist\BulkPrint\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Description: "Start {#MyAppName}"; Flags: nowait postinstall skipifsilent
