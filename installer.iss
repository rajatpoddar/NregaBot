; NREGA Bot Inno Setup Script
; Version 2.9.0

; The build script will override this version. This is a fallback.
#define AppVersion "2.9.0"
#define AppName "NREGA Bot"
#define AppPublisher "PoddarSolutions"
#define AppURL "https://nregabot.com"
#define AppExeName "NREGA Bot.exe"
#define OutputName "NREGABot-v" + AppVersion + "-Setup"

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
OutputDir=dist\installer
OutputBaseFilename={#OutputName}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
UninstallDisplayIcon={app}\{#AppExeName}
SetupIconFile=assets\app_icon.ico
WizardImageFile=wizard_image.bmp
WizardSmallImageFile=wizard_small_image.bmp
LicenseFile=license.txt
InfoBeforeFile=infobefore.txt
DisableReadyPage=yes
CloseApplications=yes
CloseApplicationsFilter=NREGA Bot.exe

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}";

[Files]
Source: "dist\{#AppExeName}"; DestDir: "{app}"; Flags: ignoreversion
; NOTE: All other data, including the platform-specific 'bin' folder,
; is bundled into the single .exe by PyInstaller and does not need to be listed here.

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Run]

Filename: "{app}\{#AppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(AppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
