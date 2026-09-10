
## META-0071-inbox-autonomy — template v3.54.0

- [x] Apply canonical migration in isolated worktree.
- [x] Verify full policy contracts, persona source, version and idempotency.
- [x] Base migration QA/backend/security reviewed.
- Integration: PR merge and main synchronization are tracked in template META-CYCLE-071 delivery manifest.

## TASK-20260908T020000-delegation-friction — 개발 위탁 병목 정합

- 상태: done — PR #1616 병합·web 배포·실제 자산 확인 완료; 전달 중 발견한 정리 도구 보완도 구현·독립 검증 완료
- 요청: Claude·Codex 개발 대화와 구현 결과를 대조하고 불필요·부족·과도한 정책을 수정해 반복 병목을 해소한다(현재 사용자의 직접 지시).
- 작업: `ai/codex/meta-delegation-friction-20260908`; base `76a76ddd`; 별도 worktree. 기존 main의 미추적 파일 보존.
- 승인 근거: 현재 요청이 정책 개선 및 그에 필요한 검증 도구 수정을 직접 위임했다. 추가 설계 승인이나 기존 대화의 승인 마커를 만들지 않는다.
- 위험: Major(후속 작업자 행동·검증에 영향); 인증/인가·데이터 변경 없음. 새로 연결한 테스트가 실제 연결 실패 안내의 삭제된 UI 참조를 검출해 `connect-modal.js`의 안내를 수정했다. 최신 main의 트레이 안내를 보존한 최종 제품 차이는 자동 연결 실패 안내 한 문구다(동작·권한 변경 없음).

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
- hot_paths: `AGENTS.md`, `bin/cycle-finalize.sh`, `pyproject.toml`, `docs/STATUS.md`, `unit/feature-0003-agent-web-ui/src/static/app/connect-modal.js`; 각 파일 소유권을 worker별 분리. 기존 활성 런타임 작업을 보존하며, 최종 제품 차이는 실패 안내 한 문구다.
- 범위 보완: Makefile/CI/pytest 경로 정본화, 실제 검증 누락이 드러낸 native-client 테스트 경계 수정. 검증·인계 정본은 `docs/improvements/delegation-friction-20260908/REPORT.md`에 기록한다.

- 추가 사용자 지시(2026-09-08): 일반 Windows 웹브라우저가 아닌 별도 DQA 클라이언트로 서비스 사용. §15.4.1·§16.6, PROJECT, PB-0009, check #13을 해당 기준으로 정합화한다. 기존 사용자 앱을 검증 편의로 종료하지 않는다.

- [x] 원본 16개 목적 표집·구현 대조와 승인/읽기/재개 정책 정합 완료.
- [x] 현재 색인 압축·원본/상태/링크 보존, DQA 주 경로 정합 완료.
- [x] 최신 main ec913f94 합류, 전체 8,059 PASS/16 skip/실패0·Bats69·도구24 및 독립 리뷰 완료.

- [x] 최신 main 8f49f1fc 추가 합류: feature0043 1671 PASS/1 skip, workflow Bats69 PASS, board Bats134 PASS/4 skip, Python 도구34 PASS.
- [x] PR #1616 merge a92c9256, 정본 web-only 배포 exit0·양 replica healthy·90초 soak·CA 검증된 healthz200·실제 서빙 자산 확인. GitHub Actions 비활성, 설치 DQA 흐름/대화 스모크 NOT-RUN은 REPORT에 별도 기록.
- [x] 전달 중 재현한 보존 옵션/삭제 후 본인 board 완료/허위 완료 출력 수정: lifecycle33 PASS·독립6 PASS·deploy quiesce34 PASS·독립 출력6조합. 마지막 보완은 host 도구와 문서이며 배포 앱 소스 변경 없음.

- [x] PR #1618 merge d81325ff, 본 작업 worktree·로컬/원격 브랜치·REGISTRY 정리 완료. 관측된 이미-done 경고와 직접-init의 강제 새 세션 안내를 후속 출력 정합 대상으로 수정; 실제 auth/board core 전이 정책은 유지. 검증은 추가 리뷰와 REPORT 참조.

## META-0074-skill-descriptions — 2026-09-08

- Request: 프로젝트 스킬 설명을 사용 상황과 결과 중심으로 정리.
- Scope: description-only command/skill/plugin metadata, personas pointer, template v3.54.3 and global wrapper generator.
- Risk: Minor. User request authorizes implementation and verification; PR creation/merge pending final confirmation.
- [x] Canonical template-upgrade.sh --apply in isolated worktree; main preserved.
- [x] Source-description consistency, command bodies/metadata and reinstall verified.
- [x] Backend/QA reviewed shared implementation; findings fixed, final PASS.
- [ ] PR creation and merge after user confirmation.
- Acceptance: descriptions explain when/what; command bodies, permissions and custom wrappers preserved.

## META-0076-dqa-field-audit — DQA 실무 검증 개선 요구서 설계·오케스트레이션 (2026-09-10)

- 요청(현재 사용자 직접 지시): 첨부 요구서 2건(`01_DQA_실무검증_개선요구서.md`·`02_DQA_개발AI_전달프롬프트.md`)의 DQA-01~09 개선 과제를 **설계**하고, 설계 완료 후 실제 구현은 **opus 서브에이전트에 위임**하며 본 세션은 오케스트레이션만 수행한다.
- 상태: in-progress — 설계(EVIDENCE·DESIGN) 작성 중. 구현은 항목별 별도 feature cycle(ITEM-xx → `feature_id` 별 worktree)로 진행하며 본 META cycle 은 설계 산출물 + 오케스트레이션 원장만 소유한다.
- 작업: worktree `.worktrees/META-0076-dqa-field-audit`, branch `ai/claude-corp/META-0076-dqa-field-audit`, base `36c5940f`.
- 정책: `AGENTS.md` SHA-256 `21286d42d52a987af6bed233fb5c050b429ddfa77d33b4979fea3acb4a17fdef` (진입 시점, worktree 동일).
- 위험: 본 META cycle 자체는 **Minor**(docs/improvements 설계 문서 + meta 원장, 코드 무변경). 설계가 정의하는 구현 ITEM 중 ITEM-01(인수 계정 경계)·ITEM-03(Product 초기 권한)은 인가 코드 변경이라 **Critical** — 각 ITEM cycle 착수 전 §7.1·§12.3 명시 승인을 AskUserQuestion 으로 받는다(요구서의 항목별 완료 기준은 설계 입력이며 §12 승인을 대체하지 않는다). 나머지 ITEM 은 Major/Minor 로 설계 문서에 항목별 명시.
- 근거 접근: 요구서 §7 근거 루트(`/mnt/e/.../dqa-work`)는 읽기 전용으로 필요한 파일만 확인했고, 원문 로그·SQL·계정 식별자 값은 산출물에 복제하지 않았다(EVIDENCE.md 인용 규칙).

### 2.1 Implementation Plan (설계 cycle)

1. `docs/improvements/dqa-field-audit-20260910/EVIDENCE.md` — 요구서 관측 항목별 근거 등급(`[기록]/[관찰]/[코드]/[사용자]`) 고정. 현 코드 file:line 확정 결함과 재현 필요 관찰을 구분.
2. `docs/improvements/dqa-field-audit-20260910/DESIGN.md` — `_TEMPLATE-ROADMAP.md` 스키마(ITEM 단위: feature_id·risk·depends_on·entry_points·acceptance·guards) + 병렬 wave 계획(핫스팟 WIP ≤2, §13.2.5-A) + 검증 매핑(요구서 §6 필수 검증 → 테스트/실측). 다른 세션(opus 서브에이전트)이 0 맥락으로 읽고 착수 가능해야 한다.
3. `meta/REVIEW.md` 엔트리(META mode check #9) → `verify-completion --pre-commit META-0076-dqa-field-audit` → commit → push → PR → merge(§16.5.1). 설계 문서가 main 에 랜딩된 뒤 각 ITEM 을 서브에이전트에 dispatch.
4. 오케스트레이션 원장: 각 ITEM 의 worktree/branch/PR/검증 결과를 `DESIGN.md §5 진행 현황` 에 갱신(improve_cycle 상태 모델과 동일 — pending→in-progress→done/blocked).

### 수용 기준

- AC-META-0076-1: DESIGN.md 의 모든 ITEM 이 요구서 DQA-id·UX-id 를 인용하고 EVIDENCE 근거 ID 로 뒷받침된다(근거 없는 결함 단정 0).
- AC-META-0076-2: 각 ITEM 이 `feature_id`(verify 정규식 충족)·entry_points(file:line)·acceptance(요구서 완료 기준 매핑)·guards 를 갖고, 종속 그래프가 DAG 다.
- AC-META-0076-3: wave 계획이 같은 핫스팟 파일(`ai_tools.py`·`tools.py`·`_conv_store.py`·`handler.py`·`messages.js`)의 동시 편집을 2 이하로 제한한다.
- AC-META-0076-4: Critical ITEM 은 사용자 승인 전 착수하지 않으며, 미승인 시 `blocked: needs-human-plan-approval` 로 표기된다.
