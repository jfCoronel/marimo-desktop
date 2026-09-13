; Inno Setup script for marimo desktop.
;   iscc /DAppVersion=0.3.0 packaging\windows\installer.iss
; Produces dist\marimo-desktop-<version>-windows-x64-setup.exe
;
; Per-user install (PrivilegesRequired=lowest): no admin prompt, which also
; means no attempt to write to Program Files. The installer is unsigned, so
; SmartScreen will warn on first run — "More info" -> "Run anyway".

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

#define AppName "marimo desktop"
#define AppPublisher "jfCoronel"
#define AppURL "https://github.com/jfCoronel/marimo-desktop"
#define AppExe "marimo-desktop.exe"

[Setup]
AppId={{8F3C2D41-9A6E-4C5B-8E17-2B9D4A6F1C30}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}/issues
AppUpdatesURL={#AppURL}/releases
DefaultDirName={autopf}\marimo desktop
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64
OutputDir=..\..\dist
OutputBaseFilename=marimo-desktop-{#AppVersion}-windows-x64-setup
SetupIconFile=..\..\assets\icon.ico
UninstallDisplayIcon={app}\{#AppExe}
UninstallDisplayName={#AppName}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
LicenseFile=..\..\LICENSE

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional shortcuts:"

[Files]
Source: "..\..\dist\{#AppExe}"; DestDir: "{app}"; Flags: ignoreversion
; The bundled exe carries ux's generic icon; the shortcuts below point at ours.
Source: "..\..\assets\icon.ico"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"; IconFilename: "{app}\icon.ico"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; IconFilename: "{app}\icon.ico"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "Launch {#AppName}"; Flags: nowait postinstall skipifsilent

[Messages]
; First launch pulls an interpreter and marimo down; say so before they wonder.
FinishedLabel=Setup has installed {#AppName}.%n%nThe first launch downloads a Python interpreter and marimo (about 200 MB) and may take a few minutes. Later launches are instant.
