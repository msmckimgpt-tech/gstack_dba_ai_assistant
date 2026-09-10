; DQA Connect — Windows 설치 마법사 (Inno Setup 6)
;
; ## 왜 설치기인가 (사용자 결정 2026-09-03)
;
; 초판은 포터블 단일 exe 였다. 그 형식은 설치·제거·시작메뉴·자동시작이 전부 없고, 매 실행마다
; 임시폴더에 전체를 풀어 느리며 백신이 의심한다. 중소 데스크톱 앱의 사실상 표준은 설치기다.
;
; ## 이 스크립트가 지키는 것
;
; - **per-user 설치**: `PrivilegesRequired=lowest` — 관리자 권한을 묻지 않는다. 사내 PC 에서
;   관리자 권한이 없는 사용자가 대부분이고, 권한 요청 자체가 이탈 지점이다.
; - **앱 폴더를 통째로** 담는다. `runtime\python.exe`(동봉 인터프리터)가 반드시 포함돼야
;   러너가 돈다 — 그것이 이 형식으로 옮긴 이유다.
; - **자동 시작은 기본 끔**. 사용자가 요청하지 않은 상주는 놀라움이다(그리고 이 프로그램은
;   사용자의 AI 계정 사용량을 쓴다). 체크박스로 명시적으로 켠다.
;
; ⚠ 서명하지 않는다(사용자 결정). 설치기 실행에서 SmartScreen 이 한 번 뜨고, 설치 후 앱
;   실행에는 뜨지 않는다.
;
; 빌드: ISCC.exe /DAppDir=<앱폴더> /O<출력폴더> DQAConnect.iss

#ifndef AppDir
  #error AppDir 을 지정하세요: ISCC /DAppDir=...\dist\DQAConnect
#endif

; ⚠ 두 이름을 **가른다** (사용자 결정 2026-09-04).
;   `MyAppName`  — 설치 폴더·제거 항목 등 **패키징 층**. 바꾸면 기존 설치본의 업그레이드
;                  경로가 갈리므로 그대로 둔다.
;   `MyDisplayName` — **사용자가 보는 이름**. 이 프로그램은 「연결 도우미」가 아니라 DQA
;                  자체다(앱 창을 직접 그린다). 시작 메뉴·바탕화면 아이콘이 이것을 쓴다.
;                  정본은 `shared/dqa_identity.DISPLAY_NAME`.
#define MyAppName "DQA Connect"
#define MyDisplayName "DQA"
#define MyAppExe "DQAConnect.exe"
#define MyPublisher "Masangsoft"
#define MyAppUserModelID "Masangsoft.DQA.Connect"

; 버전 정본은 `src/client/version.py` 의 `CLIENT_VERSION` 이고, `build_client.py` 가
; `/DAppVersion=` 으로 주입한다. 아래 폴백은 **손으로 ISCC 를 부를 때만** 쓰이며 정본과
; 같은 값이어야 한다 — `tests/test_updater.py::test_iss_version_matches_the_canon` 이 대조한다.
;
; ⚠ 갈리면 **설치기 파일명과 프로그램이 말하는 버전이 서로 다른** 상태가 되고, 그 상태에서
;   업데이트 판정은 «항상 새것»(무한 재설치) 또는 «영원히 최신»(아무도 못 받음) 중 하나로
;   고장난다. 어느 쪽이든 사용자에게는 원인이 보이지 않는다.
#ifndef AppVersion
  #define AppVersion "1.5.0"
#endif
#define MyAppVersion AppVersion

[Setup]
AppId={{7C4B1F2E-9A3D-4E58-B1C6-DQA0CONNECT01}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyDisplayName}
DisableProgramGroupPage=yes
; ⚠ **저장된 옛 그룹 이름을 재사용하지 않는다** (실측 2026-09-04).
;   Inno 는 업그레이드에서 레지스트리에 적어 둔 지난 그룹 이름을 그대로 쓴다. 그래서
;   `DefaultGroupName` 을 «DQA» 로 바꿔도 덮어 설치한 머신은 여전히 «DQA Connect» 폴더
;   **안에** «DQA» 바로 가기를 두게 된다 — 이름을 바꾼 의미가 절반만 도달한다.
;   위 `[InstallDelete]` 가 옛 폴더를 지우므로 남는 것도 없다.
UsePreviousGroup=no
; 관리자 권한을 묻지 않는다 — 사내 PC 의 일반 사용자가 그대로 설치할 수 있어야 한다.
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputBaseFilename=DQAConnect-Setup-{#MyAppVersion}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
SetupIconFile=..\client\assets\dqa.ico
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayName={#MyAppName}
UninstallDisplayIcon={app}\dqa.ico
CloseApplications=no
RestartApplications=no
SetupMutex=Global\DQAConnectSetup
SetupLogging=yes
ChangesAssociations=yes

[Languages]
Name: "korean"; MessagesFile: "compiler:Languages\Korean.isl"

[Tasks]
Name: "desktopicon"; Description: "바탕 화면에 바로 가기 만들기"; GroupDescription: "추가 작업:"
; 기본 해제 — 요청하지 않은 상주는 놀라움이고, 이 프로그램은 사용자의 AI 사용량을 쓴다.
Name: "startup"; Description: "Windows 시작 시 자동으로 실행 (내 AI 를 항상 연결해 둡니다)"; GroupDescription: "추가 작업:"; Flags: unchecked

[InstallDelete]
; ⚠ **옛 이름의 바로 가기를 지운다** (실측 2026-09-04).
;
; 보이는 이름을 «DQA Connect» → «DQA» 로 바꾸면서, 덮어 설치한 머신에 **두 벌이 남았다**:
;   Start Menu\Programs\DQA Connect\{DQA Connect.lnk, DQA Connect 제거.lnk, DQA.lnk, DQA 제거.lnk}
; Inno 는 자기가 더 이상 만들지 않는 바로 가기를 알아서 치우지 않는다 — 제거 프로그램이 돌 때만
; 지운다. 그래서 업그레이드 경로에서만 나타나고, **새로 설치해 보는 검증으로는 안 보인다.**
;
; 그룹 폴더 이름도 바뀌므로 옛 폴더를 통째로 지운다. 그 안에 있는 것은 전부 우리 것이다.
Type: filesandordirs; Name: "{autoprograms}\{#MyAppName}"
Type: files; Name: "{autodesktop}\{#MyAppName}.lnk"
Type: files; Name: "{userstartup}\{#MyAppName}.lnk"

[Files]
Source: "..\client\assets\dqa.ico"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#AppDir}\*"; DestDir: "{code:GetSlotDir}"; Excludes: "install-complete.txt"; Flags: ignoreversion recursesubdirs createallsubdirs
; Verify the complete payload before shortcuts or activation can change.
Source: "{#AppDir}\install-complete.txt"; DestDir: "{code:GetSlotDir}"; Flags: ignoreversion; AfterInstall: VerifySlot
Source: "{#Launcher}"; DestDir: "{app}"; DestName: "DQALauncher.pending.exe"; Flags: ignoreversion; AfterInstall: UpdateLauncher
Source: "{#Launcher}"; DestDir: "{app}"; DestName: "DQAConnect.exe"; Flags: ignoreversion; Check: NeedsCompatibilityEntry; BeforeInstall: PreserveLegacyEntry

[Icons]
; 아이콘은 **보이는 이름**을 쓴다 — 사용자가 누르는 것이 곧 DQA 다.
Name: "{group}\{#MyDisplayName}"; Filename: "{app}\DQALauncher.exe"; IconFilename: "{app}\dqa.ico"; AppUserModelID: "{#MyAppUserModelID}"
Name: "{group}\{#MyDisplayName} 제거"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyDisplayName}"; Filename: "{app}\DQALauncher.exe"; Tasks: desktopicon; IconFilename: "{app}\dqa.ico"; AppUserModelID: "{#MyAppUserModelID}"
Name: "{userstartup}\{#MyDisplayName}"; Filename: "{app}\DQALauncher.exe"; Tasks: startup; IconFilename: "{app}\dqa.ico"; AppUserModelID: "{#MyAppUserModelID}"

[Registry]
; `dqa-connect://` 스킴 핸들러 — 웹의 [내 AI 실행] 이 이 프로그램을 **연결 정보와 함께** 띄운다.
;
; ⚠ 이것이 없으면 실제로 일어난 일(실측 2026-09-03): 사용자가 [내 AI 실행] 을 눌러도 스킴을
;   받는 프로그램이 없어 아무 일도 없거나, 사용자가 시작 메뉴에서 직접 켜서 「연결 정보가
;   없습니다」만 본다. 브라우저는 **스킴 핸들러 부재를 감지하지 못하므로** 버튼은 조용히 죽는다.
;
; per-user 설치이므로 HKCU 에 쓴다(관리자 권한 불필요).
Root: HKCU; Subkey: "Software\Classes\dqa-connect"; ValueType: string; ValueName: ""; ValueData: "URL:{#MyDisplayName}"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\dqa-connect"; ValueType: string; ValueName: "URL Protocol"; ValueData: ""
Root: HKCU; Subkey: "Software\Classes\dqa-connect\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\dqa.ico,0"
Root: HKCU; Subkey: "Software\Classes\dqa-connect\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\DQALauncher.exe"" ""%1"""

[UninstallDelete]
Type: files; Name: "{app}\DQALauncher.exe"
Type: files; Name: "{app}\DQALauncher.pending.exe"
Type: filesandordirs; Name: "{app}\versions"
Type: files; Name: "{app}\active-slot.txt"
Type: files; Name: "{app}\DQAConnect.legacy*.exe"

[Run]
Filename: "{app}\DQALauncher.exe"; Description: "{#MyDisplayName} 실행"; Flags: nowait postinstall skipifsilent; Check: ActivationSucceeded
; Legacy updaters request a relaunch. New updaters leave the running app alone.
Filename: "{app}\DQALauncher.exe"; Flags: nowait runasoriginaluser; Check: RelaunchAfterSilentUpdate

[Code]
var
  SlotName: String;
  Activated: Boolean;
  SlotVerified: Boolean;
  LauncherReady: Boolean;
  HadInstallation: Boolean;
  LegacyBackup: String;

function MoveFileEx(ExistingFile, NewFile: String; Flags: Cardinal): Boolean;
  external 'MoveFileExW@kernel32.dll stdcall';

function GetSlotDir(Param: String): String;
var
  N: Integer;
begin
  if SlotName = '' then
  begin
    if not ForceDirectories(ExpandConstant('{app}\versions')) then
      RaiseException('설치 폴더를 만들지 못했습니다.');
    N := 1;
    repeat
      SlotName := '{#MyAppVersion}-' + IntToStr(N);
      if CreateDir(ExpandConstant('{app}\versions\') + SlotName) then Break;
      if not DirExists(ExpandConstant('{app}\versions\') + SlotName) then
        RaiseException('새 설치 폴더를 확보하지 못했습니다.');
      N := N + 1;
      if N > 10000 then RaiseException('설치 폴더 수가 너무 많습니다.');
    until False;
  end;
  Result := ExpandConstant('{app}\versions\') + SlotName;
end;

procedure UpdateLauncher;
var
  Attempt: Integer;
  ErrorCode: Cardinal;
begin
  if not SlotVerified then Exit;
  { The launcher protocol is unchanged; only its icon changes in this release. }
  for Attempt := 1 to 50 do
  begin
    if MoveFileEx(ExpandConstant('{app}\DQALauncher.pending.exe'),
                  ExpandConstant('{app}\DQALauncher.exe'), 9) then
    begin
      LauncherReady := True;
      Exit;
    end;
    ErrorCode := DLLGetLastError;
    Log('DQA launcher replacement retry: Windows error ' + IntToStr(ErrorCode));
    if (ErrorCode <> 5) and (ErrorCode <> 32) and (ErrorCode <> 33) then Break;
    Sleep(100);
  end;
  RaiseException('실행기를 갱신하지 못했습니다. 현재 앱과 기존 실행 대상을 유지합니다.');
end;

function NeedsCompatibilityEntry: Boolean;
begin
  Result := False;
  if not SlotVerified or not LauncherReady then Exit;
  Result := True;
  if FileExists(ExpandConstant('{app}\DQAConnect.exe')) and
     FileExists(ExpandConstant('{app}\DQALauncher.exe')) then
    Result := GetSHA256OfFile(ExpandConstant('{app}\DQAConnect.exe')) <>
              GetSHA256OfFile(ExpandConstant('{app}\DQALauncher.exe'));
end;

procedure PreserveLegacyEntry;
var
  N: Integer;
begin
  if not FileExists(ExpandConstant('{app}\DQAConnect.exe')) then Exit;
  LegacyBackup := ExpandConstant('{app}\DQAConnect.legacy.exe');
  N := 1;
  while FileExists(LegacyBackup) do
  begin
    LegacyBackup := ExpandConstant('{app}\DQAConnect.legacy-') + IntToStr(N) + '.exe';
    N := N + 1;
  end;
  { Renaming preserves the running image and its original runtime directory. }
  if not RenameFile(ExpandConstant('{app}\DQAConnect.exe'), LegacyBackup) then
    RaiseException('기존 실행 경로를 보존하지 못했습니다. 현재 앱은 계속 실행됩니다.');
end;

procedure DeinitializeSetup;
begin
  DeleteFile(ExpandConstant('{app}\DQALauncher.pending.exe'));
  if not Activated and (LegacyBackup <> '') and FileExists(LegacyBackup) then
  begin
    if FileExists(ExpandConstant('{app}\DQAConnect.exe')) and
       not DeleteFile(ExpandConstant('{app}\DQAConnect.exe')) then
    begin
      Log('DQA compatibility entry retained; legacy backup remains reachable.');
      Exit;
    end;
    if not RenameFile(LegacyBackup, ExpandConstant('{app}\DQAConnect.exe')) then
      Log('DQA legacy backup retained; launcher fallback remains reachable.');
  end;
end;

procedure VerifySlot;
var
  Code: Integer;
begin
  if not Exec(GetSlotDir('') + '\{#MyAppExe}', '--verify-install',
              GetSlotDir(''), SW_HIDE, ewWaitUntilTerminated, Code) then
    RaiseException('새 버전을 검사하지 못했습니다. 기존 버전을 유지합니다.');
  if Code <> 0 then
    RaiseException('새 버전의 실행 검사에 실패했습니다. 기존 버전을 유지합니다.');
  SlotVerified := True;
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  TempPointer, PointerFile: String;
  Attempt: Integer;
  ErrorCode: Cardinal;
begin
  if CurStep = ssInstall then
    HadInstallation := FileExists(ExpandConstant('{app}\DQAConnect.exe')) or
                       FileExists(ExpandConstant('{app}\active-slot.txt'));
  if CurStep = ssPostInstall then
  begin
    { Inno may suppress an AfterInstall exception and continue copying files. }
    if not SlotVerified or not LauncherReady then
      RaiseException('설치를 완료하지 못했습니다. 기존 실행 대상을 유지합니다.');
    PointerFile := ExpandConstant('{app}\active-slot.txt');
    TempPointer := ExpandConstant('{app}\active-slot.pending');
    if not SaveStringToFile(TempPointer, SlotName, False) then
      RaiseException('새 버전의 실행 정보를 기록하지 못했습니다.');
    { Replace only the pointer after the entire installation commits. }
    for Attempt := 1 to 50 do
    begin
      Activated := MoveFileEx(TempPointer, PointerFile, 9);
      if Activated then Break;
      ErrorCode := DLLGetLastError;
      Log('DQA activation retry: Windows error ' + IntToStr(ErrorCode));
      { NTFS replacement of an open destination can also return ACCESS_DENIED. }
      if (ErrorCode <> 5) and (ErrorCode <> 32) and (ErrorCode <> 33) then Break;
      Sleep(100);
    end;
    if not Activated then
    begin
      DeleteFile(TempPointer);
      RaiseException('새 버전 적용에 실패했습니다. 기존 실행 대상을 유지합니다.');
    end;
    Log('DQA activated slot ' + SlotName);
  end;
end;

function ActivationSucceeded: Boolean;
begin
  Result := Activated and not HadInstallation;
end;

function GetCustomSetupExitCode: Integer;
begin
  Result := 0;
  if not Activated then Result := 10;
end;

function RelaunchAfterSilentUpdate: Boolean;
var
  I: Integer;
begin
  Result := False;
  if not WizardSilent or not Activated then Exit;
  for I := 1 to ParamCount do
    if CompareText(ParamStr(I), '/RELAUNCH') = 0 then
    begin
      Result := True;
      Exit;
    end;
end;

procedure CurPageChanged(CurPageID: Integer);
begin
  if (CurPageID = wpFinished) and not Activated then
  begin
    WizardForm.FinishedHeadingLabel.Caption := '설치를 완료하지 못했습니다';
    WizardForm.FinishedLabel.Caption := '현재 앱과 연결은 계속 사용할 수 있습니다. 기존 실행 대상을 유지했습니다. 설치 오류를 확인한 뒤 다시 시도해 주세요.';
  end;
end;
