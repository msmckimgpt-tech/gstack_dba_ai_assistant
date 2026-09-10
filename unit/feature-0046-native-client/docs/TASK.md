---
doc_type: TASK
feature_id: feature-0046-native-client
status: active
edit_policy: rewrite
feature_status: in-progress
feature_status_date: 2026-09-10
---

# Task

## TASK-20260910-inapp-update

요청: DQA 클라이언트 내부 동작으로 별도 설치파일 없이 버전을 갱신한다.
Minor: 기존 per-user 슬롯/신뢰 서버/CA/동의 경계 유지. 현재 요청이 구현·검증을 승인했으며 deploy_scope included다.

## 2.1 Implementation Plan

- `src/client/updater.py::{parse_manifest,download,run_flow}`: 채널의 update ZIP만 선택하고 다운로드·해시 검사 후 앱 내부 패키지 적용. 설치기 실행 fallback 제거. 기존 GUI worker thread에서 실행하여 UI·연결을 유지한다.
- `src/client/update_package.py::{apply_package,extract_payload,update_lock}`: Windows 설치기와 동일 mutex로 배타 적용. 유일한 신규 슬롯에 경로/링크/크기 검증 후 압축 해제, 실제 --verify-install 통과 후 active-slot 원자 교체. 오류 시 현재 포인터와 프로세스 보존.
- `src/scripts/build_client.py::build_update_package`, `src/scripts/publish_release.py::{publish,activate,check}`: 동일 완성 앱으로 Setup(최초 도입)과 Update ZIP 생성, 둘을 원자 게시. 버전별 내용 변경 거절.
- `unit/feature-0003-agent-web-ui/src/routers/client_release.py::{current_release,client_download}`: 기존 설치기 계약 유지, 검증된 update 필드와 현재 패키지만 서빙. 채널 철회 시 ZIP도 철회.
- `src/client/version.py`, installer fallback version, FUNCTION/REPORT/MODIFY/TEST/REVIEW 및 release notes 정합: 1.4.0.

## 수용 기준

- AC1: 1.4.0 앱 내 업데이트 → ZIP 다운로드·새 슬롯 준비, Setup/MSI/PowerShell 실행 0회; 현재 app/runner PID·작성 중 문구·페이지 유지.
- AC2: 기존 앱이 끝난 뒤 기존 런처 실행 → 새 버전·같은 홈/설정으로 복귀. 업데이트가 강제 종료하지 않으며 트레이 숨김은 새 실행이 아님. 크래시 후 다음 실행도 준비된 버전을 선택함.
- AC3: 손상/경로 이탈/폭탄/실행 검사 실패/쓰기 실패/중복 요청 → 현재 슬롯·연결 보존, 실패 표시. 같은/낮은 버전으로 되돌리지 않음.
- AC4: 빌드→게시→서버→다운로드→해시·실행 검증. 구버전 1.3.x 이하 최초 전환은 기존 앱 내 설치기 경로 1회가 필요함을 고지.

## Verification plan

- native 전체·패키지 실패 경계·동시 프로세스·서버/publisher 회귀.
- 실제 Windows 격리 설치본/WebView2에서 앱 내 ZIP 갱신과 다음 실행, 기존 사용자 앱 무접촉. 실제 제공자 질의·사용자 로그인은 fixture 수용과 구분.
- §18.8 independent backend/security/qa 및 ux/design 리뷰, 최대 3회, 마지막 P1 0.

## 9. Requested Scope

- [x] 구현·빌드·패키지 회귀
- [x] 실제 Windows 내부 갱신·실패·재실행 검증
- [x] 독립 리뷰·문서 정합
- [x] commit/push/PR 병합·채널 게시·서버 배포·다운로드 검증

## Context

- worktree: /root/download/docker/mysql_ai_delegated_dev/.worktrees/feature-0046-inapp-update
- branch: ai/codex/feature-0046-inapp-update; base 7420526a; 최신 main ebf5e365 통합(1.3.1 투명 아이콘 보존)
- policy: AGENTS.md SHA256 a28388df8ae641cb3e1a19fd3850543cdc197adbc56bc858807d74ae1694b4f2
- hot_paths: client updater/installation, scripts build/publish, web routers/client_release.py; 기존 상태는 task-history/20260910-before-inapp-update.md.
- 참고: Python zipfile 공식 문서의 경로 정화·압축 해제 자원 제한, Microsoft CreateMutexW 공식 문서의 이름 공간·동시 실행 계약.

## 앱 내부 갱신 완료 증거

제품 PR #1670, 병합·웹 배포 c684d12a, 공개 채널 1.4.0. 실제 Windows ZIP 갱신·구버전 최초 전환·운영 서버 다운로드/해시·제거 PASS. [출하 Run](test-runs.d/20260910-inapp-update-release.md). 전체 feature의 다른 잔여 작업과 이 요청 완료를 구분한다.

- [x] PR1671의 아이콘 출하 기록과 1.4.0 완료 기록 통합 — 양쪽 기록 보존 및 origin/main 대비 native/web 제품 bytes 동일 확인

## TASK-20260910-transparent-icon-release

사용자 요청: 전진한 버전을 반영하여 투명 아이콘을 배포까지 완료한다. 이전 SVG 승인과 마상 브랜드 방향을 유지한다.

- main/공개 채널 1.3.0을 통합하여 1.3.1을 배포했다. 슬롯 설치와 실행 중 연결 유지, 텍스트 선택·검색 등 최신 기능을 보존한다.
- 안정 실행기·ICO 경로를 창 재실행 속성/바로가기/프로토콜/제거 표시에 사용하고 기존 실행기의 PE 아이콘도 무중단 교체한다.
- 정책 SHA-256: a28388df8ae641cb3e1a19fd3850543cdc197adbc56bc858807d74ae1694b4f2. 위험도 Minor, 사용자 배포 명시 승인.
- 이전 아이콘 작업/잠금 화면으로 시각 검수 보류한 증적: [20260910-before-icon-release.md](task-history/20260910-before-icon-release.md). 1.1.3 후보는 게시하지 않는다.

- [x] 최신 main 충돌 해소·안정 실행기 및 투명 자산 경로 정합
- [x] 회귀·실제 Windows 신규/업그레이드 설치·작업 표시줄 검수·독립 리뷰
- [x] PR 병합·1.3.1 설치기 및 웹 배포·실제 다운로드/라이브 검증 (public/localhost 다운로드·실제 기본 DQA 화면 PASS)

- [x] 통합 merge b63ffb75의 양 부모 보존과 독립 최종 리뷰 확인, normal commit으로 완료 게이트 증적 정합

- [x] 배포 검수에서 발견한 Windows 공인주소80/443 리스너 누락 복구·공인주소 실제접속 확인 — UAC 승인 적용, Windows 실제 다운로드/기본 DQA 화면 PASS

- [x] 1.3.1 공개·웹 배포·공인 주소 복구와 실제 DQA 최종 증적 정합

- [x] 출하 후 main 1.4.0(c684d12a) 전진 통합 — 최신 제품 코드 보존, 아이콘 출하 기록만 병존

- [x] 최신 c684d12a 제품 및 1.4.0 출하 소유권 보존, 운영 배포본 SHA 동일 확인

- [x] 통합6bdcc7ba의 양 부모 보존·충돌 해소 독립 검토 및 최종 출하 기록 확인
