; Скрипт установщика для программы "Табель учёта рабочего времени"
; Создан для сборки, выполненной через PyInstaller (файл Work schedule.exe в папке dist)

#define MyAppName "Табель учёта рабочего времени"
#define MyAppVersion "1.3.6"
#define MyAppPublisher "ОАО ""Компания МогНат"""
#define MyAppExeName "Work schedule.exe"
#define MyAppURL "https://github.com/Londimain/Work-schedule"

[Setup]
AppId={{A1B2C3D4-E5F6-7890-1234-56789ABCDEF0}
AppName={#MyAppName}
VersionInfoVersion={#MyAppVersion}.0
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
CloseApplications=force
RestartApplications=yes

DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
AllowNoIcons=yes

OutputDir=installer_output
OutputBaseFilename=Tabel_Setup_v{#MyAppVersion}
SetupIconFile=ico\tabel.ico
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern

PrivilegesRequired=admin

[Languages]
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion

; --- ВЫДАЕМ ПРАВА НА ЗАПИСЬ В ПАПКУ ПРОГРАММЫ ---
[Dirs]
; Разрешаем обычным пользователям писать в папку программы и её подпапку "Табель"
Name: "{app}"; Permissions: users-modify
Name: "{app}\Табель"; Permissions: users-modify

[Icons]
; Ярлык в меню "Пуск"
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"

; --- ИЗМЕНЕНО: Ярлык "Отчёты табеля" теперь ведет в папку программы ---
Name: "{group}\Отчёты табеля"; Filename: "{app}\Табель"; IconFilename: "{app}\{#MyAppExeName}"; IconIndex: 0

; Ярлык на рабочем столе (создается, только если выбрана соответствующая задача)
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

; --- ИЗМЕНЕНО: Ярлык "Отчёты табеля" на рабочем столе ведет в папку программы ---
Name: "{autodesktop}\Отчёты табеля"; Filename: "{app}\Табель"; IconFilename: "{app}\{#MyAppExeName}"; IconIndex: 0; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent