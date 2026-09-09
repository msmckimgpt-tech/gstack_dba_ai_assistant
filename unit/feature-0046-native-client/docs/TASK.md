---
doc_type: TASK
feature_id: feature-0046-native-client
status: active
edit_policy: rewrite
feature_status: in-progress
feature_status_date: 2026-09-09
---

# Task

## TASK-20260909-nondisruptive-update

요청: DQA 클라이언트 설치·업데이트 중 현재 작업과 연결을 유지한다.
위험도 Minor (§12.3): 실행 파일 배치·업데이트 생명주기 변경. 인증/인가·데이터 형식·비용 변경 없음.
현재 요청이 구현·검증을 위임했고 deploy_scope included(§16.5.1)이다.

## 2.1 Implementation Plan

- `src/installer/DQAConnect.iss::{GetSlotDir,CurStepChanged}`: 매 설치마다 새로운 versions 하위 폴더에 완전한 앱·Python을 설치. 실행 중인 파일은 쓰거나 지우지 않는다. CloseApplications/RestartApplications를 끄고 SetupMutex로 설치기 동시 쓰기를 막는다.
- `src/installer/Launcher.cs::Main`, `src/scripts/build_client.py::build_launcher`: 고정 DQALauncher.exe가 원자 교체되는 active-slot.txt를 읽어 완성된 슬롯을 실행. 시작 메뉴·바탕화면·자동시작·스킴이 같은 진입점을 사용한다. 런처는 기존 Windows .NET Framework 컴파일러로 빌드하며 기존 버전이 있으면 덮어쓰지 않는다.
- `src/client/updater.py::{apply,run_flow,check_detail,settle_pending_install}`: 다운로드/재검증 후 설치기를 실행하고 종료코드와 실제 활성 슬롯을 확인. 앱 종료 콜백 제거, 연결 중에도 설치 가능, 설치 중 중복 차단, 현재 버전과 다음 실행 버전 구분.
- `src/client/{bridge,gui}.py`: 업데이트 후 종료 배선 제거, 설치 진행·완료·실패를 GUI 상태에 노출. 미서명 자동 적용 기본 off는 유지.
- `src/client/version.py`: 1.3.0. FUNCTION/REPORT/TEST/REVIEW/MODIFY와 릴리스 설명을 같은 결과로 정합.

## 수용 기준

- AC1: DQA에서 응답 중 새 버전 설치 → 기존 앱 PID·러너 PID·로컬 연결·대화가 계속 살아 있고 강제 종료 0회.
- AC2: 새 슬롯 검증·설치 성공 후에만 실행 대상 전환. 실패/취소/같은 버전 재설치가 현재 슬롯을 덮어쓰지 않는다.
- AC3: 현재 앱을 사용자가 정상 종료한 뒤 실행 → 새 버전·같은 사용자 홈·로그인·연결 선택으로 복귀. 창 닫기(트레이 숨김)는 적용 시점이 아니다.
- AC4: 설치기는 한 번만 실행되고, 준비된 같은 버전을 반복 권유하지 않는다. 다운로드/설치 실패는 기존 앱을 유지하며 실패를 표시한다.
- AC5: Windows 설치기 직접 실행으로 legacy→새 구조, 새 구조→새 슬롯을 검증. 구버전 자체 업데이터의 종료 코드는 소급 수정할 수 없으므로 메뉴를 통한 최초 전환 한계를 별도 기록.

## Verification plan

- 의미 있는 회귀: 연결 중 업데이트, 설치 실패/중복, 활성 경로 검증, 설치 완료와 단순 spawn 구별, 확인 거절, 해시 실패.
- Windows: 격리 설치 루트/홈의 실제 설치본과 장시간 자식 작업을 실행하고 설치 전후 PID·로그·연결을 측정. 기존 사용자 앱은 종료하지 않는다.
- 독립 panel: backend/security/qa + ux/design(상태·확인 문구), 최대 3회, P1 0 확인.

## 9. Requested Scope

- [x] 구현 및 focused/native 회귀 — 산출물: src 및 회귀617 PASS/1 SKIP
- [x] Windows 설치·업데이트·실패 경계 실측 — 산출물: 실제 설치본8시나리오 PASS, 실제제공자/핀/다중세션 미검증 명시
- [x] 독립 리뷰·문서 정합 — 산출물: 독립 리뷰2인 및 docs
- [ ] commit/push/PR 병합·출하·채널 바이트 검증

## Context

- worktree: /root/download/docker/mysql_ai_delegated_dev/.worktrees/feature-0046-nondisruptive-update
- branch: ai/codex/feature-0046-nondisruptive-update; base bb962bb1
- policy: AGENTS.md SHA-256 a28388df8ae641cb3e1a19fd3850543cdc197adbc56bc858807d74ae1694b4f2
- 이전 상태: [task-history](task-history/20260909-before-nondisruptive-update.md)
- 현재 앱 계속 사용·다음 실행 적용을 합리적 기본값으로 고지. 사용자의 추가 선택이 도착하면 반영.
- 외부 근거: https://jrsoftware.org/ishelp/topic_setup_closeapplications.htm (force는 미저장 작업을 잃게 할 수 있음), https://jrsoftware.org/ishelp/topic_installorder.htm (files→icons→registry→uninstall log→run), https://jrsoftware.org/ishelp/topic_setup_setupmutex.htm (설치 동시 실행 배제).
