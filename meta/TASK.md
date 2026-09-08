
## META-0071-inbox-autonomy — template v3.54.0

- [x] Apply canonical migration in isolated worktree.
- [x] Verify full policy contracts, persona source, version and idempotency.
- [x] Base migration QA/backend/security reviewed.
- Integration: PR merge and main synchronization are tracked in template META-CYCLE-071 delivery manifest.

## TASK-20260908T020000-delegation-friction — 개발 위탁 병목 정합

- 상태: in-progress
- 요청: Claude·Codex 개발 대화와 구현 결과를 대조하고 불필요·부족·과도한 정책을 수정해 반복 병목을 해소한다(현재 사용자의 직접 지시).
- 작업: `ai/codex/meta-delegation-friction-20260908`; base `76a76ddd`; 별도 worktree. 기존 main의 미추적 파일 보존.
- 승인 근거: 현재 요청이 정책 개선 및 그에 필요한 검증 도구 수정을 직접 위임했다. 추가 설계 승인이나 기존 대화의 승인 마커를 만들지 않는다.
- 위험: Major(후속 작업자 행동·검증에 영향); 인증/인가·데이터 변경 없음. 새로 연결한 테스트가 실제 연결 실패 안내의 삭제된 UI 참조를 검출해 `connect-modal.js`의 안내 두 문구도 수정한다(동작·권한 변경 없음).

### 2.1 Implementation Plan

1. 원본 개발 세션을 도구/계정/날짜별로 표집하고 중복 import·probe를 구분한다. `docs/improvements/delegation-friction-20260908/EVIDENCE.md`에 세션·원본 행·현재 코드/커밋·잔존 여부를 기록한다. 비밀/대화 원문은 복제하지 않는다.
2. `AGENTS.md` §7·10·13·16·18, `CLAUDE.md`, `CONTRIBUTING.md`, 외부 submodule `.claude/commands/_template/entry.md`의 소비자 override(`CLAUDE.md`), `.codex/{CONTEXT.md,commands/_template/entry.md}`의 읽기 범위·기존 승인·작업 지속·검증 라우팅을 현행 정본으로 일치시킨다. 도메인 보호와 실제 검증은 유지한다.
3. `docs/{STATUS,ARCHITECTURE}.md`를 현황/구조 색인으로 압축하고 원본 상세는 archive에 보존한다. 완료 상태를 추정하지 않고 기존 링크·상태·차단 사항을 유지한다.
4. 실제 재현되는 workflow 결함만 `bin/`에서 수정하고 해당 회귀검증을 실행한다. 이미 해결된 결함은 재구현하지 않는다.
5. 관련 기계 검증·독립 리뷰·verify-completion을 통과하고 commit→push→PR 병합→공유 main 반영을 확인한다. 초기에는 정책/도구만 예상했으나 새 테스트가 화면 오류를 검출했다. 추가 사용자 결정으로 주 사용 경로를 DQA 클라이언트로 정정한다. PB-0009와 check #13을 맞추고 실제 접근 가능 범위·대체 검증을 구분한다. 호환 분기의 안내 변경 자산도 배포·확인한다.

### 수용 기준

- AC-20260908T020000-delegation-friction-1: 양 도구의 원본 대화 근거와 실제 개발 결과를 연결한 검수 원장, 표집 범위·한계를 제공한다.
- AC-20260908T020000-delegation-friction-2: 예: 이미 위임된 정책 수정 요청 + main 체크아웃 → 격리 후 같은 세션에서 실행; 새 세션/재승인 요구가 남지 않는다.
- AC-20260908T020000-delegation-friction-3: 양 도구 entry가 목차→필수 공통 규칙→해당 절을 읽고, 1MB 이상의 정책 본문 전체를 강제 적재하지 않는다.
- AC-20260908T020000-delegation-friction-4: STATUS/ARCHITECTURE 상세 원본 보존·링크 해석·상태 보존과 분량 감소를 검증한다.
- AC-20260908T020000-delegation-friction-5: 수정 workflow의 실제 실패→회귀 통과 및 독립 리뷰/완료 게이트 결과를 기록한다.

### 검증·인계

- 정책 경로: worktree `AGENTS.md` 및 공유 main `AGENTS.md`(진입 시 같은 `76a76ddd`). 내용 SHA-256은 EVIDENCE/REPORT에 실제 실행값 기록.
- hot_paths: `AGENTS.md`, `bin/cycle-finalize.sh`, `pyproject.toml`, `docs/STATUS.md`, `unit/feature-0003-agent-web-ui/src/static/app/connect-modal.js`; 각 파일 소유권을 worker별 분리. 기존 활성 런타임 작업은 건드리지 않고 실패 안내 두 문구만 변경한다.
- 범위 보완: Makefile/CI/pytest 경로 정본화, 실제 검증 누락이 드러낸 native-client 테스트 경계 수정. 검증·인계 정본은 `docs/improvements/delegation-friction-20260908/REPORT.md`에 기록한다.

- 추가 사용자 지시(2026-09-08): 일반 Windows 웹브라우저가 아닌 별도 DQA 클라이언트로 서비스 사용. §15.4.1·§16.6, PROJECT, PB-0009, check #13을 해당 기준으로 정합화한다. 기존 사용자 앱을 검증 편의로 종료하지 않는다.
