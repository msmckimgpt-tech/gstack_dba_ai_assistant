---
doc_type: TEST
feature_id: feature-0044-qa-staging-pipeline
status: active
edit_policy: mixed
source_of_truth: true
---

# Test

<!-- §1, §2, §4는 rewrite (케이스 정의). §3은 append-only (실행 결과 이력). -->

## 1. Test Scope

**본 cycle(Phase 0 설계 제안) 의 검증 범위**: 없음. 산출물이 문서이며 실행 코드·설정 변경이
0 이다. 웹/UI 변경도 없어 PB-0008 시각검증 대상이 아니다.

아래 §2 는 **구현 cycle(Phase 1~7) 에서 실행할 케이스 정의**다. 설계 단계에서 미리 적어 두는
이유는, 각 Phase 의 "무엇을 확인하면 그 단계가 끝난 것인가"를 구현 전에 고정하기 위해서다.

제외 범위: VPN·사내 CA·GitLab 자체의 동작 검증(인프라 담당 영역), Kubernetes 등 미채택 대안.

> **검증 환경 분류 (AGENTS.md §15.4)** — §3 Run 의 `Environment` 는 아래 중 하나로 명시한다.
> 웹/UI(화면·상호작용) 검증은 **`Windows-browser` 만 인정**한다.
>
> | Environment | 의미 | UI 검증 인정 |
> |---|---|---|
> | `CLI` | curl / pytest / API 계약 | ✗ (서버 계약만) |
> | `WSL-headless` | WSL 내부 headless chromium | ✗ (화면 검증 불가) |
> | `Windows-browser` | 실제 Windows Chrome/Edge CDP 자동 구동 (`bin/win-browser.py`) | ✓ |

## 2. Test Cases

### TEST-20260826T140000-offline-build-1
- Purpose: 폐쇄망 빌드 재현성 — 사내 미러만 도달 가능한 상태에서 전체 이미지 빌드가 성공하는가
- Preconditions: Phase 1 완료 (베이스 이미지·pip 파라미터화 + 버전/해시 고정)
- Steps: 외부 인터넷을 차단한 네트워크 네임스페이스(또는 방화벽 규칙)에서 전체 compose 빌드 실행
- Expected Result: 전 서비스 이미지 빌드 성공. 외부 도메인 접속 시도 0건. 실패 시 QA 에서도 실패한다.

### TEST-20260826T140000-digest-identity-2
- Purpose: dev·QA·live 가 동일 바이트를 쓰는가 — 이미지 다이제스트 등가성
- Preconditions: Phase 2·3 완료 (매니페스트 발행 + registry push)
- Steps: 매니페스트의 다이제스트와 QA·라이브에서 실제 실행 중인 컨테이너의 이미지 다이제스트를 대조
- Expected Result: 3자 모두 동일. 하나라도 다르면 build-once 계약이 깨진 것이다.

### TEST-20260826T140000-preflight-fail-closed-3
- Purpose: env 키 누락 시 배포가 시작되지 않는가 (fail-closed)
- Preconditions: Phase 2 완료 (preflight 확장)
- Steps: 매니페스트 `env_keys_required` 중 1개를 QA 의 `.env*` 에서 제거한 뒤 배포 러너 실행
- Expected Result: preflight 단계에서 중단. 컨테이너 재생성 0건. **부분 기동으로 진행하지 않는다.**

### TEST-20260826T140000-mcp-reachability-4
- Purpose: MCP 도달성 — 배포 완료 판정이 사용자 진입 경로를 실제로 확인하는가
- Preconditions: Phase 5 완료 (자동 스모크)
- Steps: QA 배포 직후 스모크 실행 — `/livez`·`/readyz` · OAuth discovery 2종 · `/api/ai/mcp` ·
  대화 경로 · 브리지 `list_open_requests`
- Expected Result: 6/6 통과. discovery 가 404 인 상태를 "정상 배포"로 판정하지 않는다.

### TEST-20260826T140000-user-roundtrip-5
- Purpose: VPN 밖 사용자 머신에서 실제로 쓸 수 있는가 (자동화로 대체 불가)
- Preconditions: Phase 4·6 완료 (TLS·VPN DNS·온보딩)
- Steps: 사용자 머신 Claude Code 에 QA MCP 등록 → 브라우저 OAuth 완주 → 도구 1회 호출 →
  웹 화면에서 task 기록 렌더 확인
- Expected Result: 4단계 전부 성공. 웹/UI 변경 포함 릴리즈면 PB-0008 시각검증 추가.
- Environment: `Windows-browser` (4번 단계)

### TEST-20260826T140000-rollback-6
- Purpose: 실패 시 이전 다이제스트로 재빌드 없이 복귀하는가
- Preconditions: Phase 5 완료
- Steps: 의도적으로 스모크를 실패시키는 릴리즈를 QA 에 배포 → 자동 롤백 관찰
- Expected Result: last-good 다이제스트로 복귀. 승격 태그 미생성. 라이브 무영향.

### TEST-20260826T140000-promote-gate-7
- Purpose: QA 를 우회한 승격이 차단되는가
- Preconditions: Phase 7 완료
- Steps: QA 스모크 결과가 없는 매니페스트에 `promote/*` 태그를 붙이고 라이브 러너 실행
- Expected Result: 라이브 러너가 거부. 배포 시작 안 함.

## 3. Test Run History

### Run 2026-08-26 — Phase 0 (설계 제안)
- Environment: 해당 없음
- Result: N/A — 실행 코드·설정 변경 0 인 문서 산출물이라 실행 검증 대상이 없다.
- Note: §2 의 7개 케이스는 각 Phase 구현 시 실행한다. 설계의 실현 가능성은
  TEST-20260826T140000-offline-build-1 에서 처음 실증된다.

## 4. 미작성 테스트와 커버 계획

본 cycle 은 자동 테스트를 작성하지 않았다. 사유: 산출물이 설계 문서이며 실행 가능한 단위가
없다. 커버 계획은 §2 의 케이스 정의로 갈음하며, 각 Phase PR 에서 해당 케이스를 실행하고
그 결과를 §3 에 append 한다.
