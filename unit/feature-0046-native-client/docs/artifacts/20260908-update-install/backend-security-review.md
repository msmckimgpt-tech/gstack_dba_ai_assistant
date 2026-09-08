---
doc_type: REVIEW_ARTIFACT
feature_id: feature-0046-native-client
agent: backend-security
timestamp: 2026-09-08T05:05:34.771934+00:00
trigger: process lifecycle/설치 종료 및 session/사용자 경계
verdict: PASS
---

### 1. Blocking issues

(no findings)

### 2. Cross-domain concerns

(no findings)

### 3. Challenge to current spec

구버전 호환: 빌드와 동일한 Inno Setup6.7.3에서 /CLOSEAPPLICATIONS는 CloseApplications=force를 취소하지 않는다. Setup.Install.HelperFunc.pas:542-549의 Forced = InitForceCloseApplications OR (header.force AND NOT InitNoForceCloseApplications) 분기까지 확인했다.

CloseApplicationsFilter는 목적 파일 basename 매칭 후 실제 {app} 파일을 RM 등록하므로 전역 Python 이름 종료가 아니다. Windows RM은 사용자·세션 권한 경계를 존중한다. custom WMI/taskkill 확장은 필요 없다. RestartApplications=no와 /NORESTARTAPPLICATIONS는 exact /RELAUNCH를 단일 재실행 소유자로 유지한다. SetupLogging에는 설치 인자/경로가 들어가지만 현재 배포 인자에 자격증명은 없다.

강제 종료도 무응답 앱에는 최대30초 후 적용될 수 있다. 속도 단축을 사전 주장하지 않는다. 실제 메뉴에서 기존 고아 PID를 수동 제거하지 않은 채 설치 exit0, 동일경로/버전, 단일 재실행과 pending 해소를 확인해야 한다.

공식 근거: https://github.com/jrsoftware/issrc/blob/is-6_7_3/Projects/Src/Setup.Install.HelperFunc.pas#L542, https://jrsoftware.org/ishelp/topic_setup_closeapplicationsfilter.htm, https://learn.microsoft.com/en-us/windows/win32/api/restartmanager/nf-restartmanager-rmshutdown

### 4. Verdict

PASS

코드 검토 차단 결함0. 실제 설치 성공 판정은 후속 실측으로 별도 확인한다.
