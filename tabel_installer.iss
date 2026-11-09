; Скрипт установщика для программы "Табель учёта рабочего времени"
; Создан для сборки, выполненной через PyInstaller (файл Work schedule.exe в папке dist)

#define MyAppName "Табель учёта рабочего времени"
#define MyAppVersion "1.3.1"
#define MyAppPublisher "ОАО ""Компания МогНат"""
#define MyAppExeName "Work schedule.exe"
#define MyAppURL "https://github.com/Londimain/Work-schedule"

[Setup]
; AppId — уникальный идентификатор. НЕ МЕНЯЙТЕ его при обновлениях, иначе установщик будет считаться новым приложением.
AppId={{A1B2C3D4-E5F6-7890-1234-56789ABCDEF0}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
; Позволяет установщику закрыть программу, если она запущена
CloseApplications=yes
RestartApplications=yes

; Папка установки по умолчанию (Program Files)
DefaultDirName={autopf}\{#MyAppName}
; Папка в меню "Пуск"
DefaultGroupName={#MyAppName}
AllowNoIcons=yes

; Папка, куда Inno Setup положит готовый установщик
OutputDir=installer_output
; Имя файла установщика
OutputBaseFilename=Tabel_Setup_v{#MyAppVersion}
; Иконка для самого установщика
SetupIconFile=ico\tabel.ico
; Сжатие
Compression=lzma2/ultra64
SolidCompression=yes
; Стиль мастера установки
WizardStyle=modern

; Запрос прав администратора (т.к. установка в Program Files)
PrivilegesRequired=admin

[Languages]
; Русский язык для мастера установки
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"

[Tasks]
; Опциональный пункт: создать ярлык на рабочем столе
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; Главный файл программы из папки dist (результат сборки PyInstaller)
Source: "dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion

; Если у вас есть дополнительные файлы (например, папка ico или файлы данных), добавьте их сюда:
; Source: "ico\*"; DestDir: "{app}\ico"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
; Ярлык в меню "Пуск"
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
; Ярлык для удаления программы
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
; Ярлык на рабочем столе (создается, только если выбрана соответствующая задача)
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
; Опция "Запустить программу" в конце установки
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent