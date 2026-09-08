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

; 버전 정본은 `src/client/version.py` 의 `CLIENT_VERSION` 이고, `build_client.py` 가
; `/DAppVersion=` 으로 주입한다. 아래 폴백은 **손으로 ISCC 를 부를 때만** 쓰이며 정본과
; 같은 값이어야 한다 — `tests/test_updater.py::test_iss_version_matches_the_canon` 이 대조한다.
;
; ⚠ 갈리면 **설치기 파일명과 프로그램이 말하는 버전이 서로 다른** 상태가 되고, 그 상태에서
;   업데이트 판정은 «항상 새것»(무한 재설치) 또는 «영원히 최신»(아무도 못 받음) 중 하나로
;   고장난다. 어느 쪽이든 사용자에게는 원인이 보이지 않는다.
#ifndef AppVersion
  #define AppVersion "1.1.1"
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
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayName={#MyAppName}
UninstallDisplayIcon={app}\{#MyAppExe}

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
; 앱 폴더 전체 — `runtime\python.exe` 포함. 하나라도 빠지면 설치는 되고 연결만 실패한다.
Source: "{#AppDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
; 아이콘은 **보이는 이름**을 쓴다 — 사용자가 누르는 것이 곧 DQA 다.
Name: "{group}\{#MyDisplayName}"; Filename: "{app}\{#MyAppExe}"
Name: "{group}\{#MyDisplayName} 제거"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyDisplayName}"; Filename: "{app}\{#MyAppExe}"; Tasks: desktopicon
Name: "{userstartup}\{#MyDisplayName}"; Filename: "{app}\{#MyAppExe}"; Tasks: startup

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
Root: HKCU; Subkey: "Software\Classes\dqa-connect\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\{#MyAppExe},0"
Root: HKCU; Subkey: "Software\Classes\dqa-connect\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExe}"" ""%1"""

[Run]
Filename: "{app}\{#MyAppExe}"; Description: "{#MyDisplayName} 실행"; Flags: nowait postinstall skipifsilent
; feature-0046 client-update-channel: **업데이트로 무음 설치된 경우** 앱을 다시 띄운다.
;
; ⚠ 위 줄은 `skipifsilent` 라 무음 설치에서는 돌지 않는다. 그것이 없으면 사용자는
;   [업데이트] 를 눌렀다가 **프로그램이 사라지는 것**을 본다 — 업데이트를 적용하려면 실행 중인
;   exe 를 비켜 줘야 하므로 우리가 스스로 끝내기 때문이다(`client/updater.apply`).
;
; ⚠ 무음이면 **무조건** 다시 띄우지는 않는다. MDM·스크립트로 무음 배포하는 경로에서 남의
;   세션에 창이 뜨면 안 된다. 우리 업데이터만 `/RELAUNCH` 를 준다(`updater.SILENT_ARGS`).
Filename: "{app}\{#MyAppExe}"; Flags: nowait runasoriginaluser; Check: RelaunchAfterSilentUpdate

[Code]
function RelaunchAfterSilentUpdate: Boolean;
var
  I: Integer;
begin
  Result := False;
  if not WizardSilent then
    Exit;
  { ⚠ 인자 **하나씩** 대조한다. `Pos('/RELAUNCH', GetCmdTail)` 로 보면 다른 인자의 값
    안에 그 문자열이 들어 있어도 참이 된다 — 실행 여부를 정하는 판정에 부분 문자열을 쓰지
    않는다. }
  for I := 1 to ParamCount do
    if CompareText(ParamStr(I), '/RELAUNCH') = 0 then
    begin
      Result := True;
      Exit;
    end;
end;
