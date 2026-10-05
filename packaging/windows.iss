[Setup]
AppId={{FB2EC19F-CB40-4A39-A2B3-FAEF96B21D19}
AppName=말씀카드
AppVersion=0.1.0
DefaultDirName={localappdata}\Programs\WordCard
DefaultGroupName=말씀카드
PrivilegesRequired=lowest
OutputDir=..\dist\installer
OutputBaseFilename=WordCard-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\WordCard.exe

[Files]
Source: "..\dist\WordCard\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\말씀카드"; Filename: "{app}\WordCard.exe"
Name: "{autodesktop}\말씀카드"; Filename: "{app}\WordCard.exe"

[Run]
Filename: "{app}\WordCard.exe"; Description: "말씀카드 실행"; Flags: nowait postinstall skipifsilent
