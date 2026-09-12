; ============================================================================
; QuickPhrase — Inno Setup 6.x 安装 / 更新 / 重装 / 版本回退稳定版
;
; 以后只修改 quickphrase.py 中：
;
;     APP_VERSION = "1.8.3"
;
; PyInstaller 固定命令见 pyinstaller_build.txt
;
; 编译目录：
;
; quickphrase.py
; QP.ico
; QuickPhrase.iss
; pyinstaller_build.txt
; dist\QuickPhrase.exe
;
; 安装后：
;
; %LOCALAPPDATA%\Programs\QuickPhrase\
; ├─ QuickPhrase.exe
; └─ ico\
;    └─ QP.ico
;
; QuickPhrase 用户数据位于 %APPDATA%\QuickPhrase\phrases.json，
; 偏好设置使用 QSettings 保存。安装、更新、同版本重装、回退均不删除用户数据。
; ============================================================================

#define AppName "QuickPhrase"
#define AppFullName "QuickPhrase"
#define AppPublisher "LinyeXie"
#define AppURL "https://github.com/LinyeXie"

#define AppExeName "QuickPhrase.exe"
#define AppExeSource "dist\QuickPhrase.exe"

#define AppIconName "QP.ico"
#define AppIconSource "QP.ico"

#define InstallerOutputDir "installer_output"


; ============================================================================
; 自动读取 quickphrase.py 中的 APP_VERSION
; ============================================================================

#if !FileExists(AddBackslash(SourcePath) + "quickphrase.py")
  #error "未找到 quickphrase.py。请将 quickphrase.py 与 QuickPhrase.iss 放在同一目录。"
#endif

#define AppVersionLine Trim(ExecAndGetFirstLine(GetEnv("ComSpec"), '/C findstr /B /C:"APP_VERSION =" "' + AddBackslash(SourcePath) + 'quickphrase.py"', SourcePath))

#if AppVersionLine == ""
  #error "无法在 quickphrase.py 中找到 APP_VERSION。请保持格式：APP_VERSION = ""1.8.3"""
#endif

#define FirstQuote Pos('"', AppVersionLine)

#if FirstQuote <= 0
  #error "APP_VERSION 未使用双引号。请保持格式：APP_VERSION = ""1.8.3"""
#endif

#define VersionTail Copy(AppVersionLine, FirstQuote + 1)
#define SecondQuote Pos('"', VersionTail)

#if SecondQuote <= 0
  #error "APP_VERSION 缺少结束双引号。"
#endif

#define AppVersion Copy(VersionTail, 1, SecondQuote - 1)

#if AppVersion == ""
  #error "APP_VERSION 不能为空。"
#endif

#define InstallerBaseName "QuickPhrase_Setup_v" + AppVersion


; ============================================================================
; 编译前检查
; ============================================================================

#if !FileExists(AddBackslash(SourcePath) + AppExeSource)
  #error "未找到 dist\QuickPhrase.exe。请先执行 pyinstaller_build.txt 中的一行命令。"
#endif

#if !FileExists(AddBackslash(SourcePath) + AppIconSource)
  #error "未找到 QP.ico。请将原始 QP.ico 与 QuickPhrase.iss 放在同一目录。"
#endif


; ============================================================================
; Setup
; ============================================================================

[Setup]

; AppId 永久固定。以后任何版本都不要修改，否则 Windows 会认为是另一款软件。
AppId={{A3A68085-DAE7-4CF3-8A9C-86B57A793D69}}

AppName={#AppName}
AppVerName={#AppName} v{#AppVersion}
AppVersion={#AppVersion}

AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}
AppUpdatesURL={#AppURL}

DefaultDirName={localappdata}\Programs\QuickPhrase
DefaultGroupName={#AppName}

PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog

WizardStyle=modern
SetupIconFile={#AppIconSource}
UninstallDisplayIcon={app}\ico\{#AppIconName}

ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0

OutputDir={#InstallerOutputDir}
OutputBaseFilename={#InstallerBaseName}

UseSetupLdr=yes
Compression=lzma2/max
SolidCompression=yes

Uninstallable=yes
CreateUninstallRegKey=yes

UsePreviousAppDir=yes
UsePreviousGroup=yes
UsePreviousLanguage=yes
UsePreviousTasks=yes

CloseApplications=yes
RestartApplications=no
RestartIfNeededByRun=no

SetupLogging=yes
ChangesAssociations=no

DisableWelcomePage=no
DisableDirPage=auto
DisableProgramGroupPage=yes
AllowNoIcons=yes

VersionInfoCompany={#AppPublisher}
VersionInfoDescription={#AppFullName} Setup
VersionInfoProductName={#AppFullName}
VersionInfoProductVersion={#AppVersion}
VersionInfoCopyright=Copyright © 2026 {#AppPublisher}


; ============================================================================
; Languages
; ============================================================================

[Languages]

Name: "english"; MessagesFile: "compiler:Default.isl"


; ============================================================================
; Tasks
; ============================================================================

[Tasks]

; 首次安装默认全部勾选。没有 unchecked 标志即为默认选中。
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "安装选项："
Name: "startup"; Description: "开机自启动（登录 Windows 后启动到系统托盘）"; GroupDescription: "安装选项："


; ============================================================================
; Dirs
; ============================================================================

[Dirs]

Name: "{app}\ico"


; ============================================================================
; Files
; ============================================================================

[Files]

; ignoreversion 必须保留，才能同时支持升级、同版本重装与回退。
Source: "{#AppExeSource}"; DestDir: "{app}"; DestName: "{#AppExeName}"; Flags: ignoreversion

; QP.ico 同时用于卸载项、桌面快捷方式和开始菜单快捷方式。
Source: "{#AppIconSource}"; DestDir: "{app}\ico"; DestName: "{#AppIconName}"; Flags: ignoreversion


; ============================================================================
; InstallDelete
; ============================================================================

[InstallDelete]

; 清理早期版本可能遗留在安装根目录中的 QP.ico。
; 安装 / 更新 / 重装 / 回退不会删除用户数据。
Type: files; Name: "{app}\QP.ico"


; ============================================================================
; UninstallDelete — 真正卸载必须删除全部 QuickPhrase 数据
; ============================================================================

[UninstallDelete]

; 软件密码无法找回。真正卸载时永久删除全部常用语与数据。
Type: filesandordirs; Name: "{userappdata}\QuickPhrase"


; ============================================================================
; Icons
; ============================================================================

[Icons]

Name: "{autoprograms}\QuickPhrase"; Filename: "{app}\{#AppExeName}"; WorkingDir: "{app}"; IconFilename: "{app}\ico\{#AppIconName}"; Comment: "{#AppFullName}"

Name: "{autodesktop}\QuickPhrase"; Filename: "{app}\{#AppExeName}"; WorkingDir: "{app}"; IconFilename: "{app}\ico\{#AppIconName}"; Comment: "{#AppFullName}"; Tasks: desktopicon


; ============================================================================
; Registry — 开机自启动
; ============================================================================

[Registry]

; 与 QuickPhrase“软件设置 -> 开机自启动”使用同一个 HKCU Run 项。
; --startup 表示登录后仅驻留托盘，不弹主窗口。
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "QuickPhrase"; ValueData: """{app}\{#AppExeName}"" --startup"; Flags: uninsdeletevalue; Tasks: startup


; ============================================================================
; Run
; ============================================================================

[Run]

Filename: "{app}\{#AppExeName}"; Description: "运行 QuickPhrase"; WorkingDir: "{app}"; Flags: nowait postinstall skipifsilent shellexec


; ============================================================================
; Code — 安装 / 更新 / 同版本重装 / 降级检测
; ============================================================================

[Code]

const
  QuickPhraseUninstallBaseKey =
    'Software\Microsoft\Windows\CurrentVersion\Uninstall';

  QuickPhraseUninstallKey =
    'Software\Microsoft\Windows\CurrentVersion\Uninstall\{A3A68085-DAE7-4CF3-8A9C-86B57A793D69}_is1';

  QuickPhraseRunKey =
    'Software\Microsoft\Windows\CurrentVersion\Run';

  QuickPhraseSettingsKey =
    'Software\LinyeXie\QuickPhrase';


// 兼容 Inno Setup 6.x：Pascal Script 自定义函数使用 Integer 作为注册表根键类型。
// HKCU32/HKCU64/HKLM32/HKLM64 常量仍可直接作为 Integer 参数传入。
function TryReadVersionFromKey(
  const RootKey: Integer;
  const KeyName: String;
  var Version: String
): Boolean;
begin
  Version := '';

  Result :=
    RegQueryStringValue(
      RootKey,
      KeyName,
      'DisplayVersion',
      Version
    );

  if Result then
  begin
    Version := Trim(Version);
    Result := Version <> '';
  end;
end;


function TryFindVersionByDisplayName(
  const RootKey: Integer;
  var Version: String
): Boolean;
var
  SubKeys: TArrayOfString;
  I: Integer;
  KeyName: String;
  DisplayName: String;
  CandidateVersion: String;
begin
  Result := False;
  Version := '';

  if not RegGetSubkeyNames(
    RootKey,
    QuickPhraseUninstallBaseKey,
    SubKeys
  ) then
    Exit;

  if GetArrayLength(SubKeys) = 0 then
    Exit;

  for I := 0 to GetArrayLength(SubKeys) - 1 do
  begin
    KeyName :=
      QuickPhraseUninstallBaseKey + '\' + SubKeys[I];

    DisplayName := '';

    if RegQueryStringValue(
      RootKey,
      KeyName,
      'DisplayName',
      DisplayName
    ) then
    begin
      DisplayName := Trim(DisplayName);

      // Inno Setup normally stores AppVerName here, e.g.
      // "QuickPhrase v1.8.2", so match by prefix rather than exact equality.
      if Pos('QuickPhrase', DisplayName) = 1 then
      begin
        if TryReadVersionFromKey(
          RootKey,
          KeyName,
          CandidateVersion
        ) then
        begin
          Version := CandidateVersion;
          Result := True;
          Exit;
        end;
      end;
    end;
  end;
end;


function TryGetInstalledVersion(var Version: String): Boolean;
begin
  Version := '';
  Result := False;

  // First try the permanent AppId uninstall key in every possible registry
  // root/view. Old builds may have been installed in a different privilege
  // mode or registry view than the setup currently running.
  if TryReadVersionFromKey(
    HKCU32,
    QuickPhraseUninstallKey,
    Version
  ) then
  begin
    Log(
      'Detected QuickPhrase via HKCU32 AppId key, version ' + Version
    );
    Result := True;
    Exit;
  end;

  if IsWin64 then
  begin
    if TryReadVersionFromKey(
      HKCU64,
      QuickPhraseUninstallKey,
      Version
    ) then
    begin
      Log(
        'Detected QuickPhrase via HKCU64 AppId key, version ' + Version
      );
      Result := True;
      Exit;
    end;
  end;

  if TryReadVersionFromKey(
    HKLM32,
    QuickPhraseUninstallKey,
    Version
  ) then
  begin
    Log(
      'Detected QuickPhrase via HKLM32 AppId key, version ' + Version
    );
    Result := True;
    Exit;
  end;

  if IsWin64 then
  begin
    if TryReadVersionFromKey(
      HKLM64,
      QuickPhraseUninstallKey,
      Version
    ) then
    begin
      Log(
        'Detected QuickPhrase via HKLM64 AppId key, version ' + Version
      );
      Result := True;
      Exit;
    end;
  end;

  // Compatibility fallback:
  // search uninstall entries by DisplayName. This also detects historical
  // QuickPhrase installers if their uninstall subkey name differed.
  if TryFindVersionByDisplayName(
    HKCU32,
    Version
  ) then
  begin
    Log(
      'Detected QuickPhrase via HKCU32 DisplayName scan, version ' + Version
    );
    Result := True;
    Exit;
  end;

  if IsWin64 then
  begin
    if TryFindVersionByDisplayName(
      HKCU64,
      Version
    ) then
    begin
      Log(
        'Detected QuickPhrase via HKCU64 DisplayName scan, version ' + Version
      );
      Result := True;
      Exit;
    end;
  end;

  if TryFindVersionByDisplayName(
    HKLM32,
    Version
  ) then
  begin
    Log(
      'Detected QuickPhrase via HKLM32 DisplayName scan, version ' + Version
    );
    Result := True;
    Exit;
  end;

  if IsWin64 then
  begin
    if TryFindVersionByDisplayName(
      HKLM64,
      Version
    ) then
    begin
      Log(
        'Detected QuickPhrase via HKLM64 DisplayName scan, version ' + Version
      );
      Result := True;
      Exit;
    end;
  end;

  Version := '';
  Log(
    'QuickPhrase uninstall information was not found in HKCU/HKLM, ' +
    '32-bit or 64-bit registry views.'
  );
end;


function NormalizeVersion(const Version: String): String;
var
  I: Integer;
  DotCount: Integer;
begin
  Result := Trim(Version);
  DotCount := 0;

  for I := 1 to Length(Result) do
  begin
    if Result[I] = '.' then
      DotCount := DotCount + 1;
  end;

  while DotCount < 3 do
  begin
    Result := Result + '.0';
    DotCount := DotCount + 1;
  end;
end;


function CompareVersionStrings(
  const InstalledVersion: String;
  const SetupVersion: String
): Integer;
var
  InstalledPacked: Int64;
  SetupPacked: Int64;
  Cmp: Integer;
begin
  if
    StrToVersion(NormalizeVersion(InstalledVersion), InstalledPacked) and
    StrToVersion(NormalizeVersion(SetupVersion), SetupPacked)
  then
  begin
    Cmp := ComparePackedVersion(InstalledPacked, SetupPacked);

    if Cmp < 0 then
      Result := -1
    else if Cmp > 0 then
      Result := 1
    else
      Result := 0;
  end
  else
    Result := 99;
end;


function InitializeSetup(): Boolean;
var
  InstalledVersion: String;
  SetupVersion: String;
  CompareResult: Integer;
  MessageText: String;
  NL: String;
begin
  Result := False;

  NL := Chr(13) + Chr(10);
  SetupVersion := '{#AppVersion}';

  if not TryGetInstalledVersion(InstalledVersion) then
  begin
    MessageText :=
      'QuickPhrase 尚未安装。' + NL + NL +
      '当前安装版本：未安装' + NL +
      '预安装版本：v' + SetupVersion + NL + NL +
      '安装器已检查当前用户/所有用户以及 32/64 位卸载注册表。' + NL +
      '是否安装 QuickPhrase v' + SetupVersion + '？';

    Result :=
      MsgBox(
        MessageText,
        mbConfirmation,
        MB_YESNO or MB_DEFBUTTON1
      ) = IDYES;

    Exit;
  end;

  CompareResult :=
    CompareVersionStrings(InstalledVersion, SetupVersion);

  if CompareResult = -1 then
  begin
    MessageText :=
      '检测到 QuickPhrase 已安装。' + NL + NL +
      '当前安装版本：v' + InstalledVersion + NL +
      '预安装版本：v' + SetupVersion + NL + NL +
      '安装类型：版本更新' + NL + NL +
      '继续后将更新 QuickPhrase 程序文件。' + NL +
      '常用语、窗口位置、偏好设置和其他用户数据将保留。' + NL + NL +
      '是否继续更新？';

    Result :=
      MsgBox(
        MessageText,
        mbConfirmation,
        MB_YESNO or MB_DEFBUTTON1
      ) = IDYES;

    Exit;
  end;

  if CompareResult = 0 then
  begin
    MessageText :=
      '当前已经安装相同版本的 QuickPhrase。' + NL + NL +
      '当前安装版本：v' + InstalledVersion + NL +
      '预安装版本：v' + SetupVersion + NL + NL +
      '安装类型：重新安装' + NL + NL +
      '继续后将重新安装当前版本。' + NL +
      '常用语、窗口位置、偏好设置和其他用户数据将保留。' + NL + NL +
      '是否继续重新安装？';

    Result :=
      MsgBox(
        MessageText,
        mbConfirmation,
        MB_YESNO or MB_DEFBUTTON1
      ) = IDYES;

    Exit;
  end;

  if CompareResult = 1 then
  begin
    MessageText :=
      '检测到当前 QuickPhrase 版本高于此安装包版本。' + NL + NL +
      '当前安装版本：v' + InstalledVersion + NL +
      '预安装版本：v' + SetupVersion + NL + NL +
      '安装类型：版本回退' + NL + NL +
      '继续后将使用较旧版本替换当前 QuickPhrase 程序文件。' + NL +
      '常用语、窗口位置、偏好设置和其他用户数据不会删除。' + NL + NL +
      '注意：较新版本创建的数据或设置，可能无法被旧版本完全识别。' + NL + NL +
      '是否确认回退？';

    Result :=
      MsgBox(
        MessageText,
        mbConfirmation,
        MB_YESNO or MB_DEFBUTTON2
      ) = IDYES;

    Exit;
  end;

  MessageText :=
    '检测到 QuickPhrase 已安装，但无法可靠比较两个版本号。' + NL + NL +
    '当前安装版本：v' + InstalledVersion + NL +
    '预安装版本：v' + SetupVersion + NL + NL +
    '继续后将覆盖 QuickPhrase 程序文件。' + NL +
    '常用语、窗口位置、偏好设置和其他用户数据不会删除。' + NL + NL +
    '是否继续安装？';

  Result :=
    MsgBox(
      MessageText,
      mbConfirmation,
      MB_YESNO or MB_DEFBUTTON2
    ) = IDYES;
end;


function InitializeUninstall(): Boolean;
var
  MessageText: String;
  NL: String;
begin
  NL := Chr(13) + Chr(10);

  MessageText :=
    '警告：卸载 QuickPhrase 会永久删除全部软件数据。' + NL + NL +
    '将删除：' + NL +
    '• 全部常用语与隐藏内容' + NL +
    '• 软件密码验证数据' + NL +
    '• 快捷键、窗口位置与全部偏好设置' + NL + NL +
    '软件密码无法找回或重置。' + NL +
    '卸载后的数据无法恢复。' + NL + NL +
    '是否确认继续卸载？';

  Result :=
    MsgBox(
      MessageText,
      mbConfirmation,
      MB_YESNO or MB_DEFBUTTON2
    ) = IDYES;
end;


procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usUninstall then
  begin
    // 无论开机自启动是安装器创建，还是之后在软件设置中打开，
    // 卸载 QuickPhrase 时都删除同一个 Run 项。
    RegDeleteValue(
      HKEY_CURRENT_USER,
      QuickPhraseRunKey,
      'QuickPhrase'
    );

    // QSettings 在 Windows 上位于 HKCU\Software\LinyeXie\QuickPhrase。
    RegDeleteKeyIncludingSubkeys(
      HKEY_CURRENT_USER,
      QuickPhraseSettingsKey
    );

    // 双保险：同时显式删除漫游 AppData 中的 phrases.json 等数据。
    DelTree(
      ExpandConstant('{userappdata}\QuickPhrase'),
      True,
      True,
      True
    );
  end;
end;


procedure InitializeWizard();
begin
  WizardForm.Caption :=
    'QuickPhrase v{#AppVersion}';
end;