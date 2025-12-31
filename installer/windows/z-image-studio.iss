; Z-Image Studio Windows Installer Script
; Inno Setup 6+
;
; Build command: iscc z-image-studio.iss
;
; For CI/CD, you can use:
;   choco install innosetup
;   iscc /DVERSION=0.2.0 z-image-studio.iss

; Version can be passed via command line: /DVERSION=x.x.x
; Defaults to 0.1.0 if not provided
#ifndef VERSION
#define VERSION "0.1.0"
#endif

[Setup]
AppId=z-image-studio
AppName=Z-Image Studio
AppVersion={#VERSION}
AppVerName=Z-Image Studio {#VERSION}
AppPublisher=Z-Image Studio
AppPublisherURL=https://github.com/iconben/z-image-studio
AppSupportURL=https://github.com/iconben/z-image-studio/issues
AppUpdatesURL=https://github.com/iconben/z-image-studio/releases
DefaultDirName={autopf}\Z-Image Studio
DefaultGroupName=Z-Image Studio
AllowNoIcons=yes
LicenseFile=..\..\LICENSE
; Modern wizard style
WizardStyle=Modern
; Compression
Compression=lzma2/fast
SolidCompression=yes
; Output settings
OutputBaseFilename=Z-Image-Studio-Setup
; App mutex for single instance
AppMutex=Global\Z-Image-Studio-Mutex

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional icons:"
Name: "startmenuicon"; Description: "Create Start Menu shortcuts"; GroupDescription: "Additional icons:"

[Files]
; Main application files (from PyInstaller build)
Source: "..\..\dist\zimg.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\..\dist\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

; Copy the webui launcher script
Source: "..\..\scripts\windows-webui-launcher.bat"; DestDir: "{app}"; Flags: ignoreversion

; License file
Source: "..\..\LICENSE"; DestDir: "{app}"; Flags: ignoreversion

; App icon for shortcuts
Source: "..\..\src\zimage\static\logo-180.png"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
; Web UI shortcut (main entry point - shown first in Start Menu)
Name: "{groupname}\Z-Image Studio (Web UI)"; Filename: "{app}\windows-webui-launcher.bat"; WorkingDir: "{app}"; IconFilename: "{app}\logo-180.png"; Tasks: startmenuicon
Name: "{groupname}\Z-Image Studio (Web UI)"; Filename: "{app}\windows-webui-launcher.bat"; WorkingDir: "{app}"; IconFilename: "{app}\logo-180.png"; Tasks: desktopicon

; CLI shortcut (for advanced users)
Name: "{groupname}\Z-Image Studio CLI"; Filename: "{app}\zimg.exe"; WorkingDir: "{app}"; IconFilename: "{app}\logo-180.png"; Tasks: startmenuicon

; Documentation shortcut
Name: "{groupname}\View License"; Filename: "{app}\LICENSE"; Tasks: startmenuicon

; Uninstall shortcut
Name: "{groupname}\Uninstall Z-Image Studio"; Filename: "{uninstallexe}"; Tasks: startmenuicon

[Run]
; Optionally open the web UI after installation (commented out by default)
; Filename: "{app}\windows-webui-launcher.bat"; Description: "Launch Z-Image Studio Web UI"; Flags: postinstall shellexec

[UninstallRun]
; Clean up user data on uninstall (optional - user data is in AppData)
; Uncomment if you want to remove user data on uninstall
; Filename: "{app}\windows-webui-launcher.bat"; Parameters: "cleanup"; Flags: runhidden

[Messages]
BeveledLabel=Z-Image Studio Installer

[Dirs]
; Create AppData directory for user data (created at runtime via platformdirs)
; No need to create here - the app handles this
