---
doc_type: GOAL
scope: feature-0003-agent-web-ui
status: active
updated_at: 2026-05-15
source_of_truth: true
---

# GOAL: Web UI 실시간 진행 표시, 대화 이동, 계정 관리, 대화 일괄 삭제

이 문서는 신규 세션에서 `/goal` 로 바로 구현에 들어갈 수 있도록 현재 확인된 누락 기능과 구현 순서를 정리한 작업 진입점이다.

## 1. 목표

`unit/feature-0003-agent-web-ui`의 작업 화면과 관리 콘솔에서 다음 기능을 실제 브라우저에서 확인 가능한 수준으로 구현한다.

1. 답변 버블 내부 실시간 step 진행상황 표시
   - 스피너
   - 경과 타이머
   - 최신 작업명
   - 작업 근거 `reason`
   - 누적 step 목록
2. polling 결과가 대화 중 진행상황에 실시간 반영되도록 연결
3. 우측 스크롤 대화 Point rail
4. 대화를 진행했던 시각으로 이동하는 캘린더
5. 관리자 계정 구성의 비밀번호 초기화
6. 관리자 계정 일괄 적용 기능의 현재 페이지 선택 버그 수정
7. `내 대화` 여러 항목 Ctrl 토글 선택 / Shift 순차 선택 후 일괄 삭제
8. 실제 진행이 끊긴 `processing` 대화의 만료 감지와 붉은색 오류 badge 표시

## 2. 현재 검증 결과

2026-05-15 브라우저와 코드 기준으로 확인한 상태다.

| 항목 | 상태 | 근거 |
| --- | --- | --- |
| 상단 실시간 progress strip | 구현됨 | `src/static/index.html`의 `#progressCard`, `src/static/app.js::renderProgress()` |
| 답변 버블 내부 실시간 progress | 미구현 | assistant bubble은 완료 후 `renderMessageDetails()`만 append |
| `/api/progress` polling | 부분 구현 | `src/app.py::progress()`, `src/static/app.js::pollProgress()` |
| 신규 대화 첫 요청 중 polling | 미흡 | lazy-create 시 `conversation_id`가 없어 요청 직후 polling 시작 불가 |
| 우측 대화 point rail | 미구현 | 브라우저 DOM selector 없음 |
| 캘린더 이동 UI | 미구현 | `/api/history_anchor`, `/api/history_dates`만 존재 |
| `history_dates` backend | 점검 필요 | `AgentCoreMessages` 조회. 현재 메시지 경로와 불일치 가능성 |
| 관리자 계정 비밀번호 초기화 | 미구현 | 본인 비밀번호 변경 API만 존재 |
| 관리자 계정 다중 선택/일괄 pending | 구현됨 | `adminState.accountSelected`, `renderAccountBulkBar()` |
| 관리자 계정 현재 페이지 전체 선택 | 버그 있음 | select-all이 현재 페이지가 아니라 전체 filtered account 대상 |
| `내 대화` 다중 선택/일괄 삭제 | 미구현 | 대화 목록은 단일 button 선택, delete API도 단건 |
| 끊긴 processing 대화 오류 표시 | 미구현 | 대화 목록은 `item.status === "processing"`이면 주황색 `.conv-dot.is-processing`으로만 표시 |

브라우저 확인 요약:

```text
메인 화면:
- #progressCard 존재
- 답변 버블 내부 progress 없음
- 우측 rail/calendar 없음
- 대화 checkbox 0개
- bulk delete 없음

로그인 후 메인 화면:
- 대화 항목 45개 확인
- 대화 checkbox 0개

관리자 화면:
- 계정 row 15개
- 계정 checkbox 15개
- #accountSelectAll 존재
- 비밀번호 reset control 없음
```

## 3. 대상 파일

주 대상:

- `unit/feature-0003-agent-web-ui/src/static/index.html`
- `unit/feature-0003-agent-web-ui/src/static/app.js`
- `unit/feature-0003-agent-web-ui/src/static/admin.html`
- `unit/feature-0003-agent-web-ui/src/static/admin.js`
- `unit/feature-0003-agent-web-ui/src/static/styles.css`
- `unit/feature-0003-agent-web-ui/src/app.py`

문서 대상:

- `unit/feature-0003-agent-web-ui/docs/FUNCTION.md`
- `unit/feature-0003-agent-web-ui/docs/TASK.md`
- `unit/feature-0003-agent-web-ui/docs/REPORT.md`
- `unit/feature-0003-agent-web-ui/docs/TEST.md`
- 필요 시 `unit/feature-0003-agent-web-ui/docs/REVIEW.md`

참고 코드 위치:

- progress strip markup: `index.html` `#progressCard`
- final assistant details: `app.js::renderMessageDetails()`
- message render: `app.js::renderMessages()`
- progress render/polling: `app.js::renderProgress()`, `pollProgress()`, `applyProgressPayload()`
- ask submit: `app.js::sendPrompt()`
- progress API: `app.py::progress()`
- conversation status source: `app.py`의 conversation list status map, `_conversation_is_processing()`, `_build_ask_status_snapshot()`
- history anchor APIs: `app.py::history_anchor()`, `history_dates()`
- single delete conversation API: `app.py::delete_conversation()`
- self password change: `app.py::auth_me_patch()`
- admin account update: `app.py::admin_update_account()`
- admin account list/select: `admin.js::renderAccountList()`
- admin account select-all bug: `admin.js` accountSelectAll change handler
- admin apply pending: `admin.js::applyAllPending()`

## 4. 구현 순서

### Phase 0. 문서와 계획 정렬

- `feature-0003-agent-web-ui/docs/FUNCTION.md`에 REQ/AC 추가.
- `TASK.md`에 Implementation Plan 작성.
- 위험도는 Major로 분류한다.
  - UI 상태 관리, auth/account 관리, 삭제 API가 함께 변경된다.
  - `TASK.md`에 `plan-review` 상태와 승인 필요 여부를 기록한다.

### Phase 1. 답변 버블 내부 live progress

구현:

- `app.js`에 pending assistant bubble state를 추가한다.
- `sendPrompt()` 시작 시 사용자 메시지와 pending assistant bubble을 즉시 렌더한다.
- `applyProgressPayload()`가 전역 `#progressCard`뿐 아니라 pending bubble에도 step snapshot을 반영하도록 한다.
- pending bubble 내부에 다음 요소를 렌더한다.
  - spinner
  - elapsed timer
  - status badge
  - 최신 step title
  - 최신 step reason/result summary
  - 접을 수 있는 누적 step 목록
- 최종 응답 수신 또는 `/api/ask_result` attach 완료 시 pending bubble을 실제 assistant message로 교체한다.

수용 기준:

- 기존 대화에서 질문 전송 즉시 assistant pending bubble이 생긴다.
- polling으로 step이 추가될 때 bubble 안의 step 수와 최신 근거가 갱신된다.
- 완료 후 bubble에는 최종 답변과 기존 `실행 단계 및 쿼리 결과 보기` details가 유지된다.
- 오류, 취소, 즉시 답변 상태가 bubble에 표시된다.

주의:

- 현재 `#progressCard`는 유지하거나 보조 상태로 축소할 수 있다. 제거 시 기존 사용자 흐름 회귀 여부를 검토한다.
- timer는 클라이언트 기준 `startedAt`으로 표시하고, 서버 `status_at`은 보조 기준으로만 사용한다.

### Phase 2. 신규 대화 첫 요청 polling 연결

구현 후보:

1. `/api/ask_start`를 추가해 `conversation_id`와 `run_id`를 먼저 반환하고, 실제 실행은 background task로 돌린다.
2. 기존 `/api/ask`를 유지하되 lazy-create 직후 상태를 저장하고 client가 attach할 수 있는 최소 응답을 먼저 받는 구조로 분리한다.

기본 방향:

- 신규 API 분리를 우선 검토한다.
- 기존 `/api/ask`, `/api/ask_status`, `/api/ask_result`, `/api/progress` backward compatibility를 유지한다.

수용 기준:

- 새 대화 첫 메시지에서도 pending bubble과 progress polling이 즉시 표시된다.
- `/api/ask` timeout 회복 흐름과 충돌하지 않는다.

### Phase 3. 끊긴 processing 대화 만료 감지와 오류 badge

문제:

- 대화 목록에서 `last_status=processing`이면 주황색 badge로 표시된다.
- 외부 이슈, 컨테이너 재시작, 프로세스 종료, 네트워크 장애 등으로 실제 작업이 더 이상 진행되지 않아도 KV 상태가 `processing`으로 남으면 사용자는 작업이 계속 진행 중이라고 오해한다.
- step이 충분한 시간 동안 증가하지 않고 run heartbeat도 없는 대화는 `processing`이 아니라 `stale/error` 계열 상태로 보여야 한다.

구현:

- backend에서 run의 실제 진행 여부를 판정하는 helper를 추가한다.
  - 입력: `conversation_id`, `last_status`, `last_status_at`, `last_status_run_id`, 마지막 step 생성 시각 또는 step count
  - 기준: `last_status=processing`이고, 마지막 status/step 갱신 시각이 만료시간을 초과하면 stale 처리
- 만료시간은 환경변수로 설정 가능하게 한다.
  - 예: `WEB_PROGRESS_STALE_TIMEOUT_SECONDS`
  - 기본값은 운영 오탐을 줄이기 위해 10~30분 범위에서 시작한다.
- conversation list payload에 표시용 상태를 별도로 포함한다.
  - 예: `status="stale_error"` 또는 `display_status="stale_error"`
  - 원본 `last_status`는 필요하면 `raw_status`로 유지한다.
- `/api/progress`, `/api/ask_status`, `/api/ask_result`도 stale 상태를 일관되게 반환하도록 정리한다.
- stale로 판정된 대화는 프론트에서 붉은색 badge로 표시한다.
  - `.conv-dot.is-stale-error` 또는 `.conv-dot.is-error`
  - tooltip/상태 문구: "작업이 중단된 것으로 보입니다" 계열
- 사용자가 해당 대화를 열었을 때 상단/버블 진행 상태에도 "작업 중단 감지"를 표시하고, 재시도/취소/삭제 같은 다음 행동을 선택할 수 있게 한다.

수용 기준:

- 실제 진행이 멈춘 지 만료시간이 지난 `processing` 대화는 대화 목록에서 주황색이 아니라 붉은색 badge로 표시된다.
- 정상적으로 step이 계속 추가되는 장시간 작업은 stale로 오탐하지 않는다.
- stale 상태는 새로고침 후에도 동일하게 표시된다.
- stale 상태의 대화는 사용자가 "계속 처리 중"으로 오해하지 않도록 명확한 문구를 제공한다.
- `/api/ask_status`의 `is_processing`은 stale 상태에서 false로 반환되거나, 별도 `is_stale=true`를 반환해 attach/resume 로직이 무한 대기하지 않는다.

주의:

- 단순히 프론트에서 시간만 보고 빨간색으로 바꾸면 탭 비활성/클라이언트 시간 오차의 영향을 받는다. source of truth는 backend 판정이어야 한다.
- stale 판정은 실제 run을 취소/삭제하지 않는다. 상태 표시와 사용자 안내가 1차 목적이다.
- stale로 판정된 후 새 요청을 허용할지, 먼저 취소/정리 액션을 요구할지는 구현 시 현재 busy guard와 함께 결정한다.

### Phase 4. 우측 대화 Point rail

구현:

- `index.html` chat 영역 우측에 point rail 컨테이너를 추가한다.
- `renderMessages()`가 메시지별 stable anchor id를 부여한다.
- 메시지마다 point를 만들고 시간/role/title tooltip을 제공한다.
- scroll 이벤트에서 현재 viewport에 가장 가까운 메시지를 highlight한다.
- point 클릭 시 해당 메시지로 scroll한다.

수용 기준:

- 메시지가 많은 대화에서 우측 rail이 표시된다.
- point 클릭으로 해당 메시지 위치로 이동한다.
- 모바일/좁은 화면에서는 rail을 숨기거나 상단 compact control로 대체한다.

### Phase 5. 캘린더/시각 이동

구현:

- `history_dates()`가 실제 메시지 저장 테이블을 기준으로 날짜/시각을 반환하도록 수정한다.
- 작업 화면에 날짜 선택 UI와 해당 날짜의 시각 목록을 추가한다.
- 날짜/시각 선택 시 `/api/history_anchor?conversation_id=...&at=...`를 호출하고, 반환된 message id anchor로 scroll한다.

수용 기준:

- 현재 대화의 메시지가 있는 날짜만 선택 가능하거나 표시상 구분된다.
- 특정 시각 선택 시 가장 가까운 과거 메시지로 이동한다.
- 메시지가 없으면 사용자에게 명확한 empty state를 보여준다.

### Phase 6. 관리자 계정 비밀번호 초기화

권장 보안 정책:

- 관리자가 임시 비밀번호를 생성해 대상 계정에 1회 표시한다.
- 대상 계정의 기존 세션은 revoke한다.
- 임시 비밀번호는 서버 로그와 DB에 평문 저장하지 않는다.
- 가능하면 `MustChangePassword` 성격의 컬럼을 추가하고 로그인 후 비밀번호 변경을 강제한다.

구현:

- backend에 관리자 reset endpoint 추가.
  - 예: `POST /api/admin/accounts/{account_id}/password-reset`
- 권한은 `console.manage` + `account.update`를 최소 요구로 시작하고, 별도 권한이 필요하면 permission catalog에 추가한다.
- `admin.js` 계정 상세에 `비밀번호 초기화` 액션을 추가한다.
- reset 결과의 임시 비밀번호는 modal에서 한 번만 표시한다.

수용 기준:

- 관리자가 타 계정 비밀번호를 초기화할 수 있다.
- 자기 계정 reset은 별도 확인을 요구하거나 제한한다.
- reset 후 대상 계정 기존 세션이 만료된다.
- 브라우저에서 reset control이 확인된다.

### Phase 7. 관리자 계정 일괄 적용 현재 페이지 버그 수정

구현:

- `renderAccountList()`의 현재 페이지 계산을 helper로 분리한다.
- `updateAccountSelectAllCheckbox()`와 `accountSelectAll` change handler가 같은 helper를 사용한다.
- cross-page banner 동작과 충돌하지 않게 한다.

수용 기준:

- 현재 페이지 전체 선택은 현재 페이지 row만 선택한다.
- 다른 페이지 선택 상태는 banner와 bulk bar에서 보존/표시된다.
- 검색/필터/페이지 이동 후 select-all checked/indeterminate 상태가 정확하다.

### Phase 8. `내 대화` 다중 선택 후 일괄 삭제

구현:

- `app.js` state에 conversation selection set과 last selected index를 추가한다.
- `renderConversationList()`에서 `내 대화` 항목에 checkbox 또는 selection affordance를 추가한다.
- Ctrl/Meta click은 토글 선택, Shift click은 현재 표시 순서 기준 range 선택으로 처리한다.
- 일괄 삭제 bar를 추가한다.
- backend에 bulk delete API를 추가한다.
  - 예: `POST /api/delete_conversations`
  - payload: `{ conversation_ids: string[], force?: boolean, confirm_text?: string }`
- 단건 `/api/delete_conversation` 로직을 내부 helper로 분리해 중복을 줄인다.
- 처리 중 대화가 포함되면 partial failure 또는 강제 삭제 확인을 제공한다.

수용 기준:

- `내 대화`에서 Ctrl/Meta 토글 선택이 가능하다.
- Shift range 선택이 가능하다.
- 선택된 여러 대화를 한 번에 삭제할 수 있다.
- 타 계정 대화는 권한이 없는 경우 선택/삭제 대상이 되지 않는다.
- 처리 중 대화가 섞인 경우 사용자가 어떤 항목이 실패/대기 상태인지 알 수 있다.

## 5. 검증 명령

정적 검증:

```bash
python3 -m py_compile unit/feature-0003-agent-web-ui/src/app.py
node --check unit/feature-0003-agent-web-ui/src/static/app.js
node --check unit/feature-0003-agent-web-ui/src/static/admin.js
```

서비스 재기동:

```bash
make web
```

브라우저 검증:

```bash
make browser-session
make browser-goto url="http://web:8000/"
make browser-eval script="document.title"
make browser-goto url="http://web:8000/admin"
make browser-eval script="document.title"
```

필수 브라우저 확인:

- 새 대화 첫 질문 중 pending assistant bubble이 보이는지
- 기존 대화 질문 중 step이 bubble 내부에서 갱신되는지
- 완료 후 최종 답변과 실행 details가 유지되는지
- 실제 진행이 끊긴 processing 대화가 만료 후 붉은색 오류 badge로 표시되는지
- 우측 point rail 클릭 이동이 되는지
- 캘린더/시각 선택 이동이 되는지
- 관리자 계정 상세에 비밀번호 초기화가 보이는지
- 관리자 계정 현재 페이지 select-all이 현재 페이지에만 적용되는지
- `내 대화` Ctrl/Shift 선택 후 bulk delete가 되는지

## 6. 신규 세션 호출 프롬프트

다음 프롬프트를 새 세션에서 그대로 사용한다.

```text
/goal repo/GOAL.md를 기준으로 feature-0003-agent-web-ui의 미구현 Web UI 기능을 실제 구현까지 진행해주세요.

반드시 먼저 다음을 확인해주세요.
1. repo/AGENTS.md
2. repo/GOAL.md
3. repo/unit/feature-0003-agent-web-ui/docs/AGENTS.md
4. repo/unit/feature-0003-agent-web-ui/docs/FUNCTION.md
5. repo/unit/feature-0003-agent-web-ui/docs/TASK.md
6. repo/unit/feature-0003-agent-web-ui/docs/REPORT.md
7. repo/unit/feature-0003-agent-web-ui/docs/ANCHOR.md

작업 범위:
- 답변 버블 내부 실시간 step 진행상황 표시
- 신규 대화 첫 요청 포함 polling 실시간 반영
- 우측 대화 Point rail
- 끊긴 processing 대화 만료 감지와 붉은색 오류 badge 표시
- 캘린더/시각 기반 대화 이동
- 관리자 계정 비밀번호 초기화
- 관리자 계정 일괄 적용 현재 페이지 선택 버그 수정
- 내 대화 Ctrl/Shift 다중 선택 후 일괄 삭제

진행 규칙:
- 먼저 FUNCTION.md에 REQ/AC를 추가하고 TASK.md §2.1 Implementation Plan을 작성해주세요.
- 위험도는 Major로 보고 plan-review 상태를 명시해주세요.
- 사용자 승인이 필요하면 구현을 멈추고 승인 요청 지점을 명확히 알려주세요.
- 승인 없이 진행 가능한 문서 정리, 코드 조사, 테스트 설계는 계속 진행해주세요.
- 구현 시 코드와 문서를 같은 작업 단위로 갱신해주세요.
- 완료 전 python compile, node --check, make web, browser 검증을 수행해주세요.
- 브라우저에서 실제 selector/DOM/상호작용으로 확인한 결과를 REPORT.md와 TEST.md에 남겨주세요.
```

## 7. 미결정 사항

- 비밀번호 초기화에서 `MustChangePassword` DB 컬럼을 추가할지, 임시 비밀번호 + 세션 revoke만으로 1차 구현할지 결정이 필요하다. 보안상 권장은 `MustChangePassword` 추가다.
- progress 전역 `#progressCard`를 유지할지, 답변 버블 중심으로 축소할지 결정이 필요하다. 호환성상 1차 구현에서는 유지하는 편이 안전하다.
- bulk conversation delete에서 일부 실패 시 전체 rollback할지, partial success를 허용할지 결정이 필요하다. 현재 admin bulk UX와 일관성을 맞추려면 partial success + 결과 요약이 적합하다.
- stale processing 판정 만료시간의 기본값 결정이 필요하다. 장시간 SQL/LLM 작업을 고려하면 1차 기본값은 20분 안팎이 적합하지만, 실제 작업별 heartbeat/step 갱신 주기를 확인한 뒤 조정해야 한다.
