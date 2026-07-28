; NREGA Bot Lite Inno Setup Script
; Version defined by build script via /dAppVersion=

#ifndef AppVersion
#define AppVersion "3.0.7"
#endif
#define AppName "NREGA Bot Lite"
#define AppPublisher "PoddarSolutions"
#define AppURL "https://nregabot.com"
#define AppExeName "NREGA Bot Lite.exe"
#define OutputName "NREGABot-Lite-v" + AppVersion + "-Setup"

; Since this .iss file is in scripts/, paths are relative to scripts/.
; Use RootDir to point to the project root directory.
#define RootDir "..\"

[Setup]
; Unique AppId for Lite version (different from main app)
AppId={{A7B8C9D0-1E2F-3A4B-5C6D-7E8F9A0B1C2D}}
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
CloseApplicationsFilter={#AppExeName}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}";

[Files]
; Main executable
Source: "{#RootDir}dist\NREGA Bot Lite\{#AppExeName}"; DestDir: "{app}"; Flags: ignoreversion
; All supporting files from the onedir build (DLLs, assets, etc.)
Source: "{#RootDir}dist\NREGA Bot Lite\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(AppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
