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

#define MyAppName "DQA Connect"
#define MyAppExe "DQAConnect.exe"
#define MyAppVersion "1.0.0"
#define MyPublisher "Masangsoft"

[Setup]
AppId={{7C4B1F2E-9A3D-4E58-B1C6-DQA0CONNECT01}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
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

[Files]
; 앱 폴더 전체 — `runtime\python.exe` 포함. 하나라도 빠지면 설치는 되고 연결만 실패한다.
Source: "{#AppDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExe}"
Name: "{group}\{#MyAppName} 제거"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExe}"; Tasks: desktopicon
Name: "{userstartup}\{#MyAppName}"; Filename: "{app}\{#MyAppExe}"; Tasks: startup

[Run]
Filename: "{app}\{#MyAppExe}"; Description: "지금 실행"; Flags: nowait postinstall skipifsilent
