; NREGA Bot Inno Setup Script
; Version defined by build script via /dAppVersion=
;
; IMPORTANT: Inno Setup resolves all relative paths in this file
; RELATIVE TO THIS FILE'S LOCATION (scripts/ directory).
; Therefore ALL file paths must be prefixed with ..\ to point
; to the project root where the actual files reside.

; The build script will override this version (via /dAppVersion=...).
; #ifndef ensures the command-line /d switch always takes precedence.
#ifndef AppVersion
#define AppVersion "3.0.0"
#endif
#define AppName "NREGA Bot"
#define AppPublisher "PoddarSolutions"
#define AppURL "https://nregabot.com"
#define AppExeName "NREGA Bot.exe"
#define OutputName "NREGABot-v" + AppVersion + "-Setup"

; Root directory (parent of scripts/ where this .iss file lives)
#define RootDir "..\"

[Setup]
; This ID must be the SAME for all versions to ensure proper updates.
AppId={{E6A5B0D1-2C3D-4E5F-8A9B-1C2D3E4F5A6B}}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}
DefaultDirName={autopf64}\{#AppName}
DefaultGroupName={#AppName}
AllowNoIcons=yes
OutputDir={#RootDir}dist\installer
OutputBaseFilename={#OutputName}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
UninstallDisplayIcon={app}\{#AppExeName}
SetupIconFile={#RootDir}assets\app_icon.ico
WizardImageFile={#RootDir}assets\wizard_image.bmp
WizardSmallImageFile={#RootDir}assets\wizard_small_image.bmp
LicenseFile={#RootDir}docs\license.txt
InfoBeforeFile={#RootDir}docs\infobefore.txt
DisableReadyPage=yes
CloseApplications=yes
CloseApplicationsFilter=NREGA Bot.exe

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}";

[Files]
; Main executable
Source: "{#RootDir}dist\NREGA Bot\{#AppExeName}"; DestDir: "{app}"; Flags: ignoreversion
; All supporting files from the onedir build (DLLs, assets, etc.)
Source: "{#RootDir}dist\NREGA Bot\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Run]

Filename: "{app}\{#AppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(AppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
