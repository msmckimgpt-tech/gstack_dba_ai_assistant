---
doc_type: REPORT
feature_id: feature-0046-native-client
status: active
edit_policy: rewrite
source_of_truth: true
---

# Report

## TASK-20260910-inapp-update

DQA 1.4.0부터 클라이언트가 업데이트 ZIP을 직접 받아 검증하고 새 버전을 준비한다. 별도 설치 프로그램을 실행하지 않으며 현재 앱과 AI 연결을 유지한다. 사용자가 알림 영역 DQA 아이콘을 오른쪽 클릭해 [종료]한 뒤 다시 실행하면 새 버전이 적용된다. 트레이 숨김은 종료가 아니다.

실행 중인 파일 대신 새 버전 폴더에 압축을 풀고 실제 새 실행 파일의 자가검사를 통과한 뒤에만 실행 대상을 원자적으로 전환한다. 설치기와 같은 mutex로 경쟁을 막으며 다운로드 손상·경로 이탈·확장 크기 초과·파일 잠금·검사 실패 시 기존 활성 버전과 작업을 보존한다. 게시기 역시 잠금·동일 버전 불변·게시 직전 해시 대조로 채널과 파일의 불일치를 차단한다.

최초 설치용 Setup은 유지한다. 기존 1.3.x 이하에는 ZIP 갱신 기능이 없어 1.4.0으로 처음 전환할 때만 기존 앱 내 설치기를 한 번 실행한다. 사용자가 별도로 설치파일을 찾을 필요는 없다. 1.2.x에서의 최초 전환은 기존 코드 때문에 재시작되므로 작업을 마친 뒤 진행해야 한다.

## 검증

- 최신 main ebf5e365의 1.3.1 투명 아이콘·설치기 수정을 통합했다. native 650 PASS / 1 skip 후 빠진 DOM 검사를 의존성 경로를 지정해 PASS: 총 651개 검증. 릴리스노트 34 PASS, ruff·codenav PASS.
- 독립 backend/security/QA 3회, UX/design 2회 검토 후 P1/P2 0. 동시 게시 경합·게시 검증 불일치·prune 순서 오류를 수정하고 재현 검사로 해소를 확인했다.
- 실제 Windows 격리 설치본에서 1.4.0→시험용 1.4.1 ZIP 갱신, 앱/러너 PID·draft 유지, 정상 종료 후 같은 프로필로 새 버전 실행을 확인했다. mutex·손상·포인터 잠금 실패도 기존 버전을 보존했다.
- 실제 WebView2에서 안내 문구를 확인했다. 제어된 페이지·러너 검사이며 사용자 원본 계정의 실제 AI 대화 검증은 아니다.
- 상세 근거와 한계: [최종 검증 Run](test-runs.d/20260910-inapp-update.md).

## 출하 상태

- worktree: `.worktrees/feature-0046-inapp-update`; branch: `ai/codex/feature-0046-inapp-update`.
- 제품 commit `223f08ae`, [PR #1670](https://github.com/msmckimgpt-tech/gstack_dba_ai_assistant/pull/1670), 병합·배포 `c684d12a`. 1.4.0 Setup·Update ZIP 공개를 완료했다. 웹 두 replica ready·90초 soak PASS, 실제 서빙 릴리스노트 일치.
- Windows에서 실제 운영 서버의 1.4.0 ZIP 발견·다운로드·CA·크기·SHA-256 일치 PASS. 격리 설치본 내부 갱신 검증과 별도로 기록한다. GitHub check run은 없으므로 원격 CI PASS로 주장하지 않는다.
- 추가로 실제 1.3.1 동결 앱에서 기존 업데이트 메뉴→1.4.0 최초 전환을 검증했다. 현재 앱/러너/draft 유지, 재실행 시 새 버전·동일 프로필 복귀 PASS.
- 배포 시 compose metadata-file 경합 경고가 있었으나 canonical 배포기가 생성 이미지의 GIT_COMMIT 정합을 확인하고 두 replica·soak 검사를 완료했다. web-only 배포이며 실제 제공자 대화 스모크는 미수행이다.
- [출하 실측 원장](test-runs.d/20260910-inapp-update-release.md)에 채널 지문·배포·Windows 실서버 다운로드·검증용 설치 제거 결과를 기록했다.
- deploy_scope: included. 착수 정책 SHA-256 `a28388df8ae641cb3e1a19fd3850543cdc197adbc56bc858807d74ae1694b4f2`; 병합 시 template_version 메타데이터만 v3.54.3으로 전진한 것을 diff로 확인했다. 배포·완료 정책 SHA-256 `21286d42d52a987af6bed233fb5c050b429ddfa77d33b4979fea3acb4a17fdef`.
- 이전 동작·출하 이력: [1.3.0 기록](report-history/20260910-before-inapp-update.md), [통합 main 1.3.1 기록](report-history/20260910-main-icon-before-inapp.md).

## 남는 특성

미서명 자동 적용 기본 off와 기존 신뢰 서버/CA를 유지한다. 실행 중일 수 있는 이전 슬롯은 자동 삭제하지 않으므로 반복 갱신 시 디스크 사용량이 증가한다. 앱 제거 시 versions 전체를 정리한다. 준비 완료 뒤 프로세스가 비정상 종료되더라도 다음 실행은 새 버전을 선택한다.

## TASK-20260910-transparent-icon-release

사용자 요청: 전진한 버전을 반영하여 투명 아이콘을 배포까지 완료한다. 이전 SVG 승인과 마상 브랜드 방향을 유지한다.

- main/공개 채널 1.3.0을 통합하여 1.3.1을 배포했다. 슬롯 설치와 실행 중 연결 유지, 텍스트 선택·검색 등 최신 기능을 보존한다.
- 안정 실행기·ICO 경로를 창 재실행 속성/바로가기/프로토콜/제거 표시에 사용하고 기존 실행기의 PE 아이콘도 무중단 교체한다.
- 정책 SHA-256: a28388df8ae641cb3e1a19fd3850543cdc197adbc56bc858807d74ae1694b4f2. 위험도 Minor, 사용자 배포 명시 승인.
- 이전 아이콘 작업/잠금 화면으로 시각 검수 보류한 증적: [20260910-before-icon-release.md](report-history/20260910-before-icon-release.md). 1.1.3 후보는 게시하지 않는다.

## 2026-09-10 — 투명 아이콘 1.3.1 검증

Environment: DQA-client
Result: PASS
Scenario: 실제 Windows동결본/격리설치본의 아이콘·업데이트·실패보존·바로가기·제거. native624/웹30/노트34도PASS. 실제사용자계정/유료AI는검증대상이아니다. [정본](test-runs.d/20260910-transparent-icon-release.md). PR1617 병합 및 채널/웹 배포 결과는 아래 최종 출하 기록을 참조한다.

## 2026-09-10 — 1.3.1 최종 출하

PR1617 병합 main ebf5e365를 웹2replica에 배포하고 ready·90초 soak를 통과했다. Windows 설치기1.3.1을 공개했으며 public/localhost 양쪽 실제 다운로드의 TLS/bytes/SHA가 검증빌드와 일치한다. 기본 주소 실제 DQA 로그인 화면의 투명 심볼과 작업 표시줄을 확인하고 검증용 앱을 정상 종료했다. 사용자 원본 설치/앱은 변경하지 않았다.

배포 검수에서 발견한 Windows public80/443 리스너 누락은 feature-0006에서 수정했다. 사용자 UAC 승인 후 정본 운영 스크립트와 해당 리스너를 복구했으며 다른 포트·방화벽·서비스 재시작은 변경하지 않았다. [최종 원장](test-runs.d/20260910-transparent-icon-release.md). 웹/클라이언트 제품은 ebf5e365이고 이후 커밋은 운영 스크립트·검증·증적 정합이다. GitHub Actions와 유료 AI 대화는 별도 PASS를 주장하지 않는다.

### 1.4.0 병행 출하와 통합 경계

마감 시 main은 c684d12a(앱 내부 ZIP 갱신1.4.0)로 전진했다. 해당 제품 코드를 그대로 통합했고 1.3.1 아이콘 출하 증적을 병존시켰다. 1.4.0 빌드·공개는 feature-0046-inapp-update 세션이 소유한다. 이 아이콘 세션의 실제 설치 검증은1.3.1이며, 앞 ebf5e365는 아이콘 배포 시점의 commit이다. 이후 cf6c0998 웹에서도 public health를 재확인했고 최신 버전을1.3.1로 되돌려 게시하지 않는다.
