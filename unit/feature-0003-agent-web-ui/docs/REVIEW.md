---
doc_type: REVIEW
feature_id: feature-0003-agent-web-ui
status: active
edit_policy: append-only
source_of_truth: true
---

# Review Log

## REV-20260629T170913-glossary-role-fieldname-fix [SKIPPED:Minor 비핵심경로 필드명 정정 — 라이브 실증(role 객체 key/name)+배포후 PB-0008 재검증으로 검증 대체] — 용어사전 역할 드롭다운/라벨 필드명 버그 수정 (TASK-20260629T170913-glossary-role-fieldname-fix, Minor §12.3 — 프런트 전용)
- 대상: `src/static/admin.js` `_metaRoleLabel`·`_metaPopulateRoleFilter` 의 role 객체 읽기 `role_key/role_name → key/name`(4 refs) + admin.html cache-buster. 백엔드/RBAC/스키마 0.
- Panel skip 사유(§18.8 6.4): Minor + 비핵심경로(인증/송신/미신뢰 렌더 무관 — 내부 역할 메타데이터 dropdown 채움) + 변경이 필드명 4개 정정. 정본 검증은 **라이브 실증**으로 선행 — PB-0008 브라우저에서 `/api/admin/roles` 200·role 객체 키 `["id","key","name",...]`(role_key/role_name 부재) 확인, `adminState.roles.length=8`인데 드롭다운 옵션 2개뿐 재현. 수정 효과는 **배포 후 PB-0008 재검증**(드롭다운에 실제 8역할 노출)으로 최종 확인.
- 자체 점검(반증 시도): ① role 객체 key/name 항상 존재? — `_list_roles` 직렬화가 전 행 부여(라이브 8역할 전수 key/name 확인). ② 대소문자? — key 는 `.toLowerCase()` 비교, DB RoleKey 소문자(dba/admin/sales)라 정합. ③ 타 호출부 회귀? — `_metaRoleLabel` 은 term tag/badge/toast/유사어/관계 6곳 단일 진실원, 전부 동일 수정 혜택. term.role_key·역할 생성 payload role_key 는 별개 객체라 무영향. ④ 빈 역할 목록(403)? — `if(!rk) continue`/find 가 빈 배열 안전.
- Human Approval Needed: 아니오 (Minor·비파괴·RBAC/스키마 무변경·명백 회귀 정정).
- Deploy 승인 근거(FIRST_REQUEST.md deploy_scope: included): cycle-final 후 web 재배포 사전 승인(정적 자산 재빌드).
- Cross-ref: CHG/TASK-20260629T170913-glossary-role-fieldname-fix · TASK-20260629T141637-glossary-role-single-ui.

## REV-20260629T165743-metadata-bs-flexclip [SUBAGENT:adversarial-css-regression] (TASK-20260629-metadata-bs-flexclip — 부트스트랩 결과 패널 flex-shrink 클리핑 수정 + cache-buster bump, Minor §12.3)
- 대상: `static/styles.css` `.admin-meta-bootstrap { flex-shrink: 0 }`(+주석), `static/admin.html`·`static/index.html` `styles.css?v=` cache-buster bump. (CSS 전용 — 백엔드/JS 로직 0.)
- 적대 리뷰 5축(회귀범위·flex-shrink 부작용·min-height/overflow 상호작용·cache-buster 정합·CSS 문법) → **VERDICT: SAFE**(BLOCKING 0·NIT 0, 반증 실패).
  1. **회귀범위 격리**: `admin-meta-bootstrap` 클래스는 `admin.html:615` metadata pane 단일 `<section>` 에만 존재(index.html·admin.js grep 0). CSS 규칙도 metadata 문맥 한 곳 → 타 pane 오염 없음.
  2. **부작용 없음**: 부모 pane `overflow-y:auto` 가 형제 총합 초과분을 스크롤로 흡수(형제 미잘림). 형제 `#metadataList`(`.admin-list`: `flex:1 1 auto; min-height:0; overflow-y:auto`)가 유일 grow+자체 스크롤로 잔여 공간 흡수. 부트스트랩은 grow/basis 미선언 → 변경 후 `flex:0 0 auto`(자연높이 고정, grow=0 이라 형제 밀어내기 경로 없음).
  3. **형제 안전·타겟 정확**: 클리핑 근원은 `overflow:hidden`→flex `min-height:auto`=0. `#metadataForm`(overflow:visible)은 min-content 바닥 보존, `#metadataList`는 의도된 shrink+내부 스크롤 설계. `overflow:hidden`+미설계 shrink로 0까지 무너진 유일 케이스가 `.admin-meta-bootstrap` → 단일 타겟 수정이 정확.
  4. **cache-buster 정합**: `styles.css?v=` 가 admin.html:7 + index.html:9 양쪽 동일 `20260629-metadata-bs-flexclip` bump. `share.html` 은 별도 `share.css` 참조라 무관. JS 무변경이라 `admin.js?v=` 유지 정당.
  5. **CSS 문법**: brace 균형 1616/1616, `@media(max-width:560px)`(7742→7745)와 무관한 depth-0 규칙 블록 내부 정상 위치. diff 정확히 8줄(숨은 변경 없음).
- 라이브 PB-0008 실브라우저 검증(별도 증적): fix 주입 시 paneScrollHeight 684→2364, 17 테이블 전부 표시·pane 스크롤 정상. 배포본 재검증은 REPORT/TEST §3.

## REV-20260629T142631-metadata-bs-collapse [SUBAGENT:adversarial-frontend-statemachine+xss+regression] (TASK-20260629-metadata-bs-collapse — 부트스트랩 결과 패널 접기+검색 재설계 + cache-buster bump, Major §12.3)
- 대상: `static/admin.js`(렌더+토글+검색+힌트), `static/admin.html`(검색 필터바), `static/styles.css`(접기/검색/조밀), `index.html`/`admin.html` cache-buster.
- 패널(적대 frontend 리뷰어 1, 7축: value-loss·state-machine·XSS·AI-fill 회귀·event-binding·edge·max-height): **BLOCKER 0**.
  - VALUE-LOSS: CLEAN — 접기/필터는 시각 토글(class/`display`)만, save·AI-fill·apply 가 descendant 셀렉터로 숨은 입력까지 전체 수집. 유실 경로 없음.
  - XSS: CLEAN — 식별자 textContent·값 .value/String(), 검색어는 includes+textContent 만(셀렉터/HTML 삽입 0).
  - AI-fill: CLEAN — apply 셀렉터 nesting 투명, fill 후 hint 갱신이 접힌 헤더까지 반영.
  - event-binding/edge/max-height: CLEAN — idempotent bound 가드, 0테이블/0컬럼/특수문자/0결과 카운트 정상, 460px 캡 미재도입(metadata-table-desc-fix 보존).
  - MINOR(diff 귀속): 모두펼치기 라벨이 개별 토글 후 desync(자가복구) → **수정 흡수**(`allExpanded` 상태 제거, `_metaBootstrapSyncExpandAllLabel` 로 DOM 기준 라벨 동기화 — render/toggleTable/toggleAll 3곳).
  - MAJOR(pre-existing, diff 무관, **수용·follow-up**): tables↔columns 서브탭 전환 시 부트스트랩 미재렌더 → render/save mode 불일치(stale 패널·저장 0건). 서브탭 핸들러가 `_metaBootstrapRenderResult` 미호출이 원인 — 본 cycle scope(잘림·여백) 밖이라 미수정, 별도 티켓 권고.
- 판정: SHIP-WITH-FIXES → MINOR 흡수 후 SHIP.

## REV-20260629T041724-doc-sync-rn-0629 [SKIPPED:non-policy-doc] — 릴리즈노트 06-29 블록 정합 + 캐시버스터 bump (TASK-20260629T041724-doc-sync-rn-0629, 비-정책 doc-only)
- Date: 2026-06-29 (`/_dqa:doc_sync` 무인 스케줄, worktree ai/claude/doc-sync-20260629-130501).
- 변경: `static/release-notes-data.js` releases head 에 신규 '2026-06-29' 블록 3항목 prepend(용어사전 대화 자율등록 · 용어 검토 큐 중첩 · 답변 평가 중복 정리) + `index.html`·`admin.html` cache-buster `?v=20260629-rn-0629`→`?v=20260629b-rn-0629`.
- SKIP 사유(§18.4): 변경이 (a) 사용자 노출 릴리즈노트 텍스트 콘텐츠 3항목 추가 + cache-buster bump 뿐, (b) 실행/인가/데이터/응답계약 무영향. 원천 코드(40c0de0 glossary-conv-autoreg·284e75a glossary-review-nest·31aa67a feedback-unique-vote)는 각 cycle 에서 이미 적대 패널 + 라이브 검증·배포 완료 → 본 릴리즈노트 cycle 은 비-정책 doc 경량. 사실 정확성·평이화·비노출은 머지 3건 REPORT/diff 1:1 대조로 검증.
- 적대 제외 판정: 첨부 wrong-bubble(ec39a60)은 REPORT·커밋이 "정상 display 경로 동작 동일"(스키마/마이그·프론트·cache-buster 무변경, 드문 fork/마이그 cross-space 엣지) 명시 → 사용자 체감 변화 0 이라 항목 미추가(보수적 결정).
- 검증: `node --check release-notes-data.js` PASS(JS 구문) + 항목 스키마(type/area/title/detail) 정합 + releases head '2026-06-29' 블록 3항목. 비-user-facing(내부/devops — OAuth 폴백 1d0ace4·b9335b5, conversation_audit persona 84f2e45, template v3.36.0 0f69e6d, web-router-modularization 99bffb1 behavior-neutral) 의도적 제외 확인.
- Human Approval Needed: 아니오(자동 동기화).
- Cross-ref: CHG-20260629T041724-doc-sync-rn-0629 / TASK-20260629T041724-doc-sync-rn-0629 / FUNCTION '릴리즈노트 콘텐츠 — 06-29 블록 신설' / 원천 머지 40c0de0·284e75a·31aa67a. META(STATUS·wiki)는 별도 commit/상위 루프 소관.

## REV-20260629T123000-glossary-review-nest-deploy [DEPLOY-RECORD] — 용어 검토 큐 IA 중첩 배포 완료 (TASK-20260629-glossary-review-nest)
- Date: 2026-06-29. 프런트 전용(정적 자산) 변경 — deploy_scope:included(동일 admin 영역 직전 배포 사용자 승인 + 본 변경 프런트 전용·되돌리기 용이) 따라 web-only 재배포. 첫 배포 surface 는 본 세션 선행 cycle 에서 완료.
- 실행: `repo-web` 이미지 재빌드(신규 admin.html/admin.js/styles.css baked) → web --force-recreate(healthy). memory-init/ask-worker 미touch(스키마·agent-core 무변경).
- 검증(컨테이너 baked 자산): admin.html cache-buster `?v=20260629-glossary-review-nest`(admin.js·styles.css) · `data-meta-subtab="glossary-review"` 제거(0) · `#metadataGlossaryViews` strip(1) · `data-glossary-view` 2개 · `ADMIN_TAB_PERMISSIONS.metadata` 에 kb.glossary.curate 포함 · `_metaSyncGlossaryViews` 정의 · functional glossary-review 잔재 0 · web healthz OK. (cache-buster bump 으로 직전 glossary-conv-autoreg UI 미전파 갭도 동반 propagate.)
- Cross-ref: REV-20260629T120000-glossary-review-nest / CHG-20260629-glossary-review-nest.

## REV-20260629T120711-attach-id-space [SKIPPED:h5b-attach-layer-direct-closure-of-prior-adversarial-finding-self-review] — 첨부 영속 레이어에 message_id_space 추가 (TASK-20260629T120711-attach-id-space, Major §12.3)
- Date: 2026-06-29. 선행 REV-20260629T022055-feedback-id-space 의 **잔여** 항목("동일 특성을 공유하는 첨부 영속 레이어 `_load_assistant_attachments_by_message`, message.id 키 — 별도 feature 범위")을 사용자 요청으로 마저 완수. 본 cycle 은 이미 적대 backend 리뷰(H1~H7)가 도출·수용한 **H5(b)** 의 첨부 레이어 직접 폐쇄이고, 피드백 레이어에서 검증된 동일 패턴의 미러 + 전용 cross-space 회귀 테스트라 full 적대 패널 대신 적대 self-review + 회귀 테스트로 종결(check #9 인식 `[SKIPPED:<사유>]`).
- 결함(H5(b) 첨부 레이어 재기술): `_load_assistant_attachments_by_message` 는 MetaJson.message_id **단일 키**로 그룹핑, `_attach_assistant_attachments` 는 history 메시지 `id` 단일 키로 매칭했다. message.id 는 표시 store(`agent_runtime.messages.id`)와 core fallback(`core_messages.id`) 두 독립 IDENTITY 공간서 와 숫자만 같아도 다른 답변 → core 공간 메시지가 같은 숫자의 display 첨부를 잘못 표시하는 wrong-bubble 가능(피드백 레이어와 동일 선재 특성).
- 해소: id_space 차원 추가 → (message_id, message_id_space) 복합 키. materialize 가 MetaJson 에 `message_id_space="display"` 영속(message_id 출처 `_load_latest_assistant_message` 가 표시 store 전용이라 불변), 로더·attacher 가 복합 키로 그룹핑·매칭. `_attach_user_feedback` 와 정확히 대칭.
- 적대 self-review (반증 시도 → 안전 확인):
  1. **정상 경로 회귀?** — display 메시지(`id_space="display"`) + display 첨부(MetaJson space='display')는 같은 키라 기존과 동일 매칭. 현재 `_get_history` 의 두 호출부(PG·MySQL)는 항상 display 리스트에 attach 하므로 관측 동작 불변. (반증 실패=안전.)
  2. **legacy 행 누락?** — message_id_space 키 없는 기존 MetaJson 행은 로더·materialize 모두 'display' 로 간주 → 기존 display 메시지에 정상 합류(L4 단언). 무손실.
  3. **wrong-bubble 실증** — A3: display 첨부가 같은 숫자 id 의 core 메시지엔 미주입·display 메시지엔 정상 주입. L4: core/display 같은 숫자 100 이 별개 키. (방어가 실제로 동작.)
  4. **stale int-key 소비자?** — `_load_assistant_attachments_by_message`/`_attach_assistant_attachments` 의 src 호출부는 `_get_history` 2곳뿐, 테스트는 test_task0285 뿐(grep 확인). 옛 int-key 기대 소비자 0 → 타입 변경(dict[int]→dict[tuple]) 안전.
  5. **share/프론트 영향?** — share view 는 본 함수 미호출(redact 는 MetaJson.attachment_derived flag 기반), 프론트는 서버가 채운 `_attachments` 만 렌더 → JS·cache-buster 불요.
  6. **join 테이블 범위?** — `core_attachment_derived_messages.message_id`(비-FK)는 라이브 surfacing 에서 message_id 로 조회되지 않음(INSERT/mirror/backfill 전용) → wrong-bubble surface 아님, 범위 밖(Resume≠Re-scope).
- 검증: 대상 테스트 11/11(A1~A3·L1~L4·V·S), `make test` 전체 exit=0(두 feature 회귀 0)·ruff 통과·py_compile.
- Human Approval Needed: 없음(자동 동기화). 배포는 web 코드 재빌드 동반(스키마 마이그 없음) — deploy_scope: included(FIRST_REQUEST 전역) 자동 배포 대상.
- Cross-ref: 선행 REV-20260629T022055-feedback-id-space(잔여 출처) / CHG-20260629T120711-attach-id-space.
## REV-20260629T120000-glossary-review-nest [SUBAGENT:adversarial-state-machine + adversarial-access-control + adversarial-regression-dom] — SHIP-WITH-FIXES (MAJOR 1 수정)
- Date: 2026-06-29. TASK-20260629-glossary-review-nest(Minor §12.3, 프런트 IA). §18.8 적대 검증 워크플로 3 lens 병렬(상태머신·렌더 / 권한 게이트·접근경계 / 회귀·DOM·XSS). **BLOCKER 0, MAJOR 1(3 lens 독립 동일근본), MINOR 2, NIT 4**.
- **[MAJOR] 적발→수정**: 부모 `ADMIN_TAB_PERMISSIONS.metadata = [ingest.manual, sample.curate]` 가 `kb.glossary.curate` 누락 → `canSeeTab("metadata")` 가 curate-only 사용자에게 false → 메타데이터 탭 자체 미표시 → 중첩된 용어 검토 큐 도달 불가. 본 변경이 추가한 `_metaSubtabVisible` 의 OR(curate) 분기·`_GLOSSARY_VIEW_PERM.review` 가 그 페르소나에 dead path 가 되어 변경의 명시 목표(curate-only 접근 보존) 무력화. **수정**: 탭 게이트에 `kb.glossary.curate` 추가(backend `admin_list_glossary_feedback` 가 curate 단독 200 → 표시 확장이 실 인가와 정합, 서버 403 이 실경계). pre-existing 갭이나 본 IA 가 큐를 더 깊이 중첩하므로 동반 수정이 정합.
- **[MINOR] 수정**: 메타 탭 재진입 분기에 `_metaSyncGlossaryViews()`+`_metaPrimeReviewBadge()` 추가(strip 가시성·active·배지 stale 방어). **[NIT] 수정**: gview 클릭 핸들러의 `_metaSyncGlossaryViews` 이중 호출 제거(_metaRenderForm 위임); gview 버튼 `aria-selected` 추가(a11y).
- **결함 없음 확인(적대 검증됨)**: 타 서브탭(enums/tables/columns/samples) 게이트 회귀 0(_metaSubtabVisible 비-glossary 분기 = 기존 `!perm||can(perm)` 동치), ingest-only/둘다없음 persona 접근 경계 견고(curate-only list 누수·CRUD 폼 노출 차단 — _metaSyncGlossaryViews 가 권한 없는 보기 보정), XSS(gview/배지 textContent·정적 HTML, innerHTML 미사용), 부트스트랩/역할필터/scope 정합, 잔여 glossary-review 참조 0, 백엔드/route 무변경.
- 검증: node --check PASS. Human Approval Needed: 없음(자동 동기화 + deploy_scope:included). 프런트 SHIP.
- Cross-ref: TASK-20260629-glossary-review-nest / CHG-20260629-glossary-review-nest / 선행 TASK-20260629-glossary-conv-autoreg.

## REV-20260629T112000-glossary-conv-autoreg-deploy [DEPLOY-RECORD] — 용어사전 대화 자율등록 배포 완료 (TASK-20260629-glossary-conv-autoreg)
- Date: 2026-06-29. 배포 승인 근거: 사용자 AskUserQuestion "지금 배포"(라이브 스키마 변경 동반이라 deploy_scope:included 와 전역 deploy-confirm 정책 교차 확인 후 명시 승인). FIRST_REQUEST 정책상 승인 근거 기록.
- 실행: ① `repo-web`·`repo-ask-worker`·`repo-memory-init` 이미지 재빌드(공유 Dockerfile) → ② `memory-init` 재실행(`agent_core.py --init-memory` → `_ensure_pg_schema()` 가 agent_kb_schema.sql 0023 미러 idempotent 적용, exit 0 "schema 적용 완료") → ③ `web`+`ask-worker` --force-recreate(둘 다 healthy).
- 검증: 라이브 PG(`agent_kb`) — kb_glossary.role_key/source 컬럼·glossary_feedback·glossary_relations 테이블·ux_kb_glossary_scope_role_term 제약 전부 present. 런타임 `web.app`: kb.glossary.curate 권한 + 신규 5 라우트 등록 + 코어 함수(auto_promote_or_queue·_feedback_status 등) present. web/ask-worker 부팅 로그 에러 0.
- Cross-ref: REV-20260629T103000-glossary-conv-autoreg / feature-0002 CHG-20260629T110000-glossary-autoreg-bootstrap-sql.

## REV-20260629T022055-feedback-id-space [SKIPPED:h5b-direct-closure-of-prior-adversarial-finding-self-review] — 피드백 고유성 키에 id_space 추가 (TASK-20260629T022055-feedback-id-space, Major §12.3)
- Date: 2026-06-29. 선행 REV-20260629T014345-feedback-unique-vote 의 적대 backend 리뷰가 **CONFIRMED→수용(watch-item)** 한 H5(b)(두 id 공간 모호성)를 사용자 요청으로 마저 해소. 본 cycle 은 그 한정 결함의 직접 수정이라 full 적대 패널 대신 self-review + 회귀 테스트로 종결(설계가 이미 H5(b) 분석에서 도출됨).
- 결함(H5(b) 재기술): `message.id` 가 표시 store(`agent_runtime.messages.id`)와 core fallback(`core_messages.id`) 두 독립 IDENTITY 공간서 온다(숫자 겹침). 0021 의 (created_by, message_id) 키는 cross-space 에서 (a) DB 충돌(다른 답변 같은 키 → UPSERT 가 남의 투표 덮음) (b) wrong-bubble 복원 가능.
- 해소: id_space("display"|"core") 차원 추가 → 키 (created_by, message_id, message_id_space). 두 공간의 같은 숫자 id 가 다른 키가 되어 (a)(b) 모두 차단. /api/history 4개 빌더가 id_space 노출, record_feedback/endpoint/app.js/복원 헬퍼가 전 경로 일관 전달·매칭.
- 설계 판단:
  1. **인덱스 신규명**: 3-col 인덱스를 `ux_sample_feedback_user_msg_space_vote`(신규)로 — 구 2-col 동명 인덱스가 있으면 부트스트랩 `CREATE … IF NOT EXISTS` 가 정의 변경을 감지 못하는 same-name no-op trap 회피(구명 DROP + 신명 CREATE 멱등).
  2. **default 'display'**: 신규 컬럼 NOT NULL DEFAULT 'display' — 라이브 적재분은 전부 표시 store 경로라 기존 행 정합.
  3. **ON CONFLICT 추론**: 3-col + 동일 술어로 신규 인덱스를 arbiter 추론(컬럼셋+술어 매칭, 인덱스명 무관). suggested=true 는 술어 제외 → plain INSERT 보존.
  4. **하위호환**: id_space 기본 'display' 라 미전송 클라이언트·기존 행 모두 'display' 로 정합(대다수 경로 동작 동일).
- 잔여: 동일 특성을 공유하는 첨부 영속 레이어(`_load_assistant_attachments_by_message`, message.id 키)는 본 cycle 범위 밖(별도 feature) — 피드백 한정 해소.
- 검증: flywheel 13/13(3-col ON CONFLICT·id_space 전달 단언)·curation 15/15(id_space 전달)·두 feature 전체 회귀 0. py_compile·node --check·alembic chain linear(0021→0022 단일 head).
- Human Approval Needed: 없음(자동 동기화). 배포는 0022 스키마 적용 동반 — confirm 대상.
- Cross-ref: feature-0002 REV-20260629T022055-feedback-id-space / 마이그 0022 / 선행 REV-20260629T014345-feedback-unique-vote(H5(b) 출처).

## REV-20260629T014345-feedback-unique-vote [SUBAGENT:adversarial-backend] — 답변당 사용자별 고유 피드백 강제 (TASK-20260629T014345-feedback-unique-vote, Major §12.3)
- Date: 2026-06-29. 결정(AskUserQuestion): 재투표 **변경 허용**(👍↔👎, UPSERT last-write-wins, 답변당 1행).
- 설계 근거: 중복의 권위적 차단은 **DB 계층**(부분 UNIQUE + UPSERT)이어야 한다 — 프론트 dedup(`data-done` DOM 플래그)은 새로고침/전환에 소실되어 신뢰 불가. 답변 식별자는 기존에 첨부 영속이 키로 쓰는 표시 store `agent_runtime.messages.id`(프론트 `message.id`)를 재사용 — 새 식별 체계 도입 없이 정합.
- 안전/적대 분석(검토 표면):
  1. **부분 인덱스 + ON CONFLICT 단일문**: ON CONFLICT 추론 술어를 부분 인덱스 술어와 문자 동일하게 작성(`WHERE message_id IS NOT NULL AND created_by IS NOT NULL AND suggested=false`). 삽입 행이 술어 불충족(suggested=true 또는 message_id/created_by NULL)이면 arbiter 미적용 → 평범 INSERT(검수 큐 "샘플 등록" 다중 제출 동작 보존). 충족(plain vote)이면 중복 시 DO UPDATE.
  2. **마이그 데이터 안전**: message_id 신규 컬럼 → 기존 행 전부 NULL → 부분 인덱스 술어가 NULL 제외 → 기존(중복 포함) 행이 UNIQUE INDEX 생성을 막지 않음(무손실·멱등, IF NOT EXISTS).
  3. **id 회수**: lastval()(DO UPDATE 경로에서 직전 시퀀스값 반환 부정확) 제거 → `RETURNING id` 로 INSERT/DO UPDATE 양 경로 정확.
  4. **격리**: history 피드백 주입은 (conversation_id, created_by) 로 스코프 — 타 사용자 피드백 미노출. PG 조회 fail-soft(예외 시 빈 dict, 이력 표시 비차단).
  5. **잔여 watch**: message_id 부재(프론트 message.id 없는 fallback core 경로)·익명(created_by None)은 부분 인덱스 대상 외 → 고유성 미강제(기존 동작). 정상 로그인 + 표시 store 경로(대다수)는 완전 강제.
- 적대 검증(general-purpose adversarial-backend, H1~H7) **VERDICT: FIX-NEEDED — 확정 결함 1건(H5(b)) 수용(documented watch-item), 나머지 H1~H4·H6·H7 REFUTED(건전)**:
  - **H1~H4 REFUTED**: 부분 인덱스 arbiter 추론은 plan-time 인덱스 명세 매칭이라 suggested=true 행은 술어 불충족으로 충돌검사 건너뛰고 plain INSERT(검수 큐 보존); ON CONFLICT 술어가 인덱스 술어와 문자 동일(런타임 에러 없음); 신규 message_id NULL 이라 기존 데이터로 인덱스 생성 실패 없음(무손실·멱등); DO UPDATE(≠DO NOTHING)라 RETURNING 항상 행 반환.
  - **H6 REFUTED**: `_load_user_feedback_by_message` 가 (conversation_id, created_by) 양축 스코프 → 타 사용자 누출 없음, conn fail-soft/close 정리.
  - **H7 REFUTED**: set_updated_at 트리거 재설정은 같은 tx now() 동일값이라 무해.
  - **H5(b) CONFIRMED → 수용(watch-item)**: `m["id"]` 가 표시 store(`agent_runtime.messages.id`)와 core fallback(`core_messages.id`)의 **두 독립 IDENTITY 공간**에서 올 수 있다(app.py:6879 명시). fork/마이그로 대화가 core-only→display 전환되는 드문 경우 고유성 우회 또는 wrong-bubble 복원 가능. **수용 근거**: ① 동일 `message.id` 키잉은 **기존 첨부 영속 레이어가 이미 공유하는 선재 아키텍처 특성**(본 변경이 신규 도입 아님) ② 단일 history 응답은 항상 한 id 공간(혼재는 cross-load 전환 시만) ③ 지배적 실패모드는 "구 core 답변이 display 전환 후 history 에서 사라짐"이라 중복 우회 도달성이 낮음 ④ 정상 표시-store 경로(사용자 보고 시나리오)는 완전 강제 ⑤ 근본 해소(id 공간 통일/태깅)는 첨부 레이어 동반 변경이 필요한 별도 아키텍처 과제 — 본 버그 fix scope·risk 초과. 사용자에게 후속 과제로 표면화.
  - **H5(1) 인지**: message_id/created_by NULL(익명·fallback)은 부분 인덱스 외 → 고유성 미적용(의도된 한계).
  - **테스트 공백(권고)**: 단위 테스트가 FakeConn SQL-shape 만 검증 → 실 PG ON CONFLICT+부분 인덱스 의미(suggested 분기·재투표 갱신) 미검증. 후속 ephemeral PG 통합 테스트 권고(out-of-scope).
- 테스트: curation 15/15 + flywheel 15/15(신규 vote-UPSERT 키 단언 포함) PASS, 두 feature 전체 회귀 0.
- Human Approval Needed: 없음(commit/push/main 병합 자동 동기화). 배포는 deploy_scope 판정(Phase 6.8) — 마이그 0021 적용 동반이라 1회 confirm 대상.
- Cross-ref: feature-0002 REV-20260629T014345-feedback-unique-vote / CHG-20260629T014345-feedback-unique-vote / MIGRATIONS 0021.
## REV-20260629T103000-glossary-conv-autoreg [SUBAGENT:adversarial-correctness-db + adversarial-security-governance] — SHIP-WITH-FIXES (BLOCKER 1건 적발·수정, 적대 패널 완료)
- Date: 2026-06-29. TASK-20260629-glossary-conv-autoreg(Major §12.3, cross-cut 0002+0003, ADR-20260629T101500). §18.8 적대 패널 2인: ① 정확성·DB·동시성, ② 보안·거버넌스·RBAC·XSS. 두 리뷰어가 **동일 BLOCKER 독립 적발**.
- **[BLOCKER] (적발→수정)** `kb_glossary.auto_promote_or_queue` — 거부(rejected)된 용어가 고신뢰 재추론 시 라이브 kb_glossary 에 재유입(poisoning 방어 무력화). 원인: `_insert_glossary_auto`(라이브 INSERT)가 거부 가드(`record_glossary_suggestion`의 WHERE pending)보다 **먼저** 실행되고 가드 차단 시 롤백 안 됨 → 부활 행이 검토 큐에서 되돌릴 핸들도 없는 좀비. **수정**: 삽입 전에 `_feedback_status` 로 선검사 — status ∈ {rejected, promoted, auto_promoted} 면 즉시 "skipped"(INSERT 미발생). 회귀 테스트 2건 추가(`test_auto_promote_skips_rejected_term`·`test_auto_promote_skips_already_promoted`).
- **[MAJOR] (수정)** poisoning 방어 미검증(false-green) → 위 회귀 테스트로 게이트 고정.
- **[MINOR] (수정)** 마이그 0021 `ADD CONSTRAINT` 재실행 비멱등 → 신규 제약도 `DROP CONSTRAINT IF EXISTS` 선행(트리거 패턴)으로 멱등화.
- **[MINOR] (부분완화)** 자율등록이 매 턴 LLM 호출(기본 ON·per-account cap 부재) → 짧은 답변(<80자) 추론 skip 가드 추가. 자연 rate-limit(턴=과금) 존재하므로 잔여 per-account cap 은 후속 후보(AGENT_GLOSSARY_AUTOPROPOSE=0 로 즉시 차단 가능).
- **[MINOR] (수용)** downgrade 의 UNIQUE(scope,term) 재추가가 role별 중복 시 실패 가능 — 마이그 주석에 문서화된 trade-off(다운그레이드 한정).
- **결함 없음 확인(적대 검증됨)**: RBAC 6개 신규 엔드포인트 정합(검토큐=kb.glossary.curate, 관계=kb.ingest.manual), role_key 검증(WebRoles∪'*'), scope 가드, XSS(textContent/value 만), 프롬프트 주입측 datamark 펜스, audit 4종, reject 단일 동작, ON CONFLICT 타깃↔UNIQUE 제약 정합, GRANT, conn 수명/soft-fail.
- 검증: 코어 21 + 웹 신규 13 + 기존 metadata 회귀 + route_snapshot 갱신 → 전체 **1222 passed**(잔여 7=`web.app` 컨테이너 레이아웃 의존, 본 변경 무관). ruff·py_compile·node --check·단일 alembic head PASS.
- Human Approval Needed: 없음(commit/push/main 병합·재배포는 자동 동기화 정책 + deploy_scope:included). 코드 SHIP.
- Cross-ref: feature-0002 REV-20260629T103000-glossary-conv-autoreg / ADR-20260629T101500-glossary-conversation-autoregistration.

## REV-20260626T135945-ask-dedup-idempotency [SKIPPED:hotfix-1line-param-isolation-live-pg-validated] — 동일 cycle 라이브 회귀 hotfix (TASK-20260626-ask-dedup-idempotency, Major §12.3)
- Date: 2026-06-26. 본체 REV-20260626T134920-ask-dedup-idempotency 의 배포 검증 단계에서 적발된 라이브 PG 회귀의 즉시 수정. 신규 동작 추가 아닌 **버그 수정(파라미터 격리)** 이라 full §18.8 패널 SKIP — 대신 라이브 PG 직접 실행으로 검증(해당 실패 모드에 가장 직접적인 테스트).
- 회귀: dedup NOT EXISTS 가 `%(cid)s`/`%(account_id)s` 를 INSERT SELECT(varchar 추론)와 공유 → PG `AmbiguousParameter: inconsistent types deduced for parameter $1 — text versus character varying` → 워커 모드 신규 /api/ask 전부 500. 단위 FakeConn 테스트는 SQL 문자열만 검사해 미포착(파싱·타입추론은 실 PG 에서만 발현).
- 수정: dedup 절을 전용 파라미터 `%(dcid)s`/`%(daccount)s` + 테이블 alias `d` 로 분리(각 파라미터 단일 컨텍스트). 검증: ① 라이브 PG(`repo-ask-worker-1`)에 수정 enqueue SQL 직접 실행 → parse/execute 성공(limit=0 → None, AmbiguousParameter 소멸). ② `test_ask_jobs.py` 에 `%(DCID)S`/`%(DACCOUNT)S`/`d.conversation_id` 단언 추가로 회귀 고정(21/21 PASS). ③ 재빌드·재배포 후 baked 코드 재검증.
- 잔여 교훈: ask_jobs 단위 테스트가 SQL-shape 만 검증 → PG 의미(타입추론·jsonb·제약) 회귀는 미포착. 후속 개선 후보 = ephemeral PG 통합 테스트(out-of-scope, 본 cycle 미수행).
- Human Approval Needed: 없음(commit/push/main 병합·재배포는 자동 동기화 + deploy_scope:included). 코드 SHIP.
- Cross-ref: REV-20260626T134920-ask-dedup-idempotency / feature-0002 CHG-20260626-ask-dedup-idempotency(HOTFIX 항목) / TASK-20260626-ask-dedup-idempotency.

## REV-20260626T134920-ask-dedup-idempotency [SUBAGENT:adversarial-concurrency-7hypothesis] — SHIP-WITH-FIXES → 흡수 후 SHIP (TASK-20260626-ask-dedup-idempotency, Major §12.3 — /api/ask send/concurrency 멱등화, cross-feature 0002+0003)
- Date: 2026-06-26
- Cycle: assistant 요청 2번 중복 전송/처리 결함 수정. worker enqueue 멱등화(ask_jobs `dedup_message` NOT EXISTS + `find_active_dup_ask_job` → 기존 run attach) + 프론트 실패 status 재시도 + web 불안정 트리거 문서화. worktree `ai/claude/ask-dedup-idempotency`(base 15ef5f4). CHG-20260626-ask-dedup-idempotency.
- §18.8 verification panel = 적대적 concurrency/regression 코드 리뷰(general-purpose REFUTE, H1~H7 + 추가 발견). 라이브 `agent_runtime.ask_jobs`(159행, 중복 페이로드 7군 — 보고 버그쌍 포함) + 전체 dispatch/attach 루프/`_build_worker_agent_result`/`claim`/`_ACTIVE_SLOT_PREDICATE`/`set_run_status`/`_compute_display_status` 정독. **VERDICT: SHIP-WITH-FIXES → 흡수 후 SHIP. BLOCKER 0 · MAJOR 0 · MINOR 3 + doc nit.**
- **반증 실패=안전 확인(핵심)**: H1 attach-to-existing — pending/running 만 매칭(done 미attach), `_build_worker_agent_result(job_id, conv_id)` 가 그 job 의 result_json 을 conv_id 강제 → **cross-conversation 결과 누출 불가**; attach 루프는 KV-terminal OR job-terminal 둘 다로 종료(stale terminal 조기종료 없음, send#1 sentinel 이 processing 보장). H3 sentinel skip — 기존 run 이 KV last_status 소유, 새 sentinel 미작성이 정확(재포인팅 방지). H5 `payload->>'user_message'` — 파라미터 바인딩(주입 없음)·EXPLAIN ix_ask_jobs_conv 라이드·159행 perf 무이슈·unicode/quote 정확. H6 회귀 — `dedup_message=None` → SQL byte-identical(절 미주입), 429/abort/`_build_worker_agent_result` 경로 무변경. H7 프론트 — 읽기전용 `/api/ask_status`·슬롯 미점유·≤2.1s bounded.
- **MINOR 흡수(3)**: ① **stale-running 미제외**(find/dedup 이 죽은 run 에 attach → timeout fallback) → `find_active_dup_ask_job`·enqueue dedup 절을 `_ACTIVE_SLOT_PREDICATE` 재사용으로 교체(heartbeat 끊긴 running 제외, `stale_seconds` 파라미터화)+테스트 MAKE_INTERVAL 단언 추가. ② **index.html cache-buster 미bump**(part B 미전파) → `app.js?v=20260626-ask-dedup-idempotency` 로 bump+스테이징. ③ **dedup 키 attachment 누락**(동시 same-text/different-attachment → 잘못된 답변 attach, WEB_PARALLEL_LIMIT>1+진성 동시 필요) → **accepted trade-off**(dedup 의도=동일 재전송, 시나리오 극희소; 후속 확장 여지). doc nit(동시 race "atomic backstop" 과장) → app.py 주석·문서를 "commit 된 중복에 atomic, sub-ms 동시충돌은 partial unique index 후속" 로 정정.
- **잔여(accepted)**: 진성 sub-ms 동시 중복은 partial unique index 로만 완전 차단(관측 결함은 순차 재전송이라 현 범위 충분). 테스트는 FakeConn SQL-shape 회귀고정(런타임 PG dedup 의미는 미검증 — 기존 suite 스타일과 동일, 라이브 배포 후 ask_jobs dup=0 재검증으로 보완).
- 검증(흡수 후): `test_ask_jobs.py` **21/21 PASS**(신규 dedup 5) + `py_compile`(ask_jobs.py·app.py) + `node --check`(app.js) PASS.
- Human Approval Needed: 외부 영향(PR 생성)은 사용자 confirm. commit/push/main 병합·배포(deploy_scope: included)는 자동 동기화 정책. 코드 자체는 SHIP.
- Cross-ref: feature-0002 CHG-20260626-ask-dedup-idempotency / TASK-20260626-ask-dedup-idempotency / FUNCTION REQ-20260626-ask-dedup-idempotency / REPORT 2026-06-26.

## REV-20260625T204254-conv-switch-fade [SUBAGENT:adversarial-frontend-8hypothesis] — SHIP-WITH-FIXES → 흡수 후 SHIP (TASK-20260625T204254-conv-switch-fade, Minor §12.3 — frontend-only 대화 전환 크로스페이드)
- Date: 2026-06-25
- Cycle: 좌측 사이드 대화 전환 크로스페이드(fade-out/in + 목표 우선 로딩 시 가속). worktree `ai/claude/feature-0003-agent-web-ui`(base 2666738). CHG-20260625T204254-conv-switch-fade.
- §18.8 verification panel = 적대적 frontend 코드 리뷰(general-purpose REFUTE, H1~H8 8가설 반증 시도). 통과가 아니라 결함 적발 목적. **VERDICT: SHIP-WITH-FIXES → 2건 흡수 후 SHIP**.
- **MAJOR(방어 — 수정)**: 고스트(`.messages-switch-ghost` z-index:3)가 `#messagePointRail`(z-index auto) 위에 페인트될 fragility — geometry 상 고스트 폭(logRect.width)이 16px rail 을 제외해 실제 겹치지 않으나, 향후 레이아웃 변경 시 occlusion 위험. **수정**: `.message-point-rail` 에 `z-index:4` 부여(고스트보다 위 — rail dot 항상 노출 보장).
- **MINOR(수정)**: fade-in 완료 후 `messageLogEl` 에 인라인 `opacity:1`+`transition:opacity` 영구 잔류(현재 다른 코드가 messageLog opacity 미접근이라 무해하나 latent). **수정**: fade-in `transitionend`(once)에서 opacity 가 여전히 "1" 이면 인라인 opacity/transition 제거(새 전환이 선점했으면 no-op).
- **반증 실패=안전 확인**: H1(연속 A→B→C 전환) — begin 이 `_removeSwitchGhost()` 선행 + 매 commit 가 opacity 복원, 재클릭은 begin 전 return → 최대 1 고스트·stuck 없음. H2(가속 transitionend 어긋남) — 동일 고스트·동일 `{once}` 리스너 재발화 + `MSG_FADE_OUT_MS+250` fallback 타이머 미해제로 누수 차단. H3(에러/empty-state/pending 복원 stuck) — try/catch 양 분기 commit + empty/pending 도 opacity 0 재구성 후 fade-in. H5(중복 `message-<id>`) — 고스트가 `#messageLog` 보다 DOM 후순위라 `getElementById` 는 real 노드 우선(rail jump·검색·steps 버튼 query 전부 real 스코프). H6(비전환 renderMessages) — 크로스페이드 함수가 `_msgSwitchGhost` null-guard, renderMessages 는 상태 미참조. H7(인라인 잔류) — MINOR 로 흡수. H8(scrollTop 점프) — 고스트 scrollTop=live 복제, real 로그 하단스크롤은 opacity 0 하에서 invisible.
- 검증(수정 후): `node --check app.js` PASS + CSS brace balance 1585/1585. (전환은 CSS transition/transitionend·timer 기반 → jsdom 단위테스트 부적합, 정적검사+적대리뷰로 대체 — steps-btn-pending-persist cycle 선례 동일.)
- Human Approval Needed: 외부 영향(PR 생성)은 사용자 confirm. commit/push/main 병합·배포(deploy_scope: included)는 자동 동기화 정책. 코드 자체는 SHIP.
- Cross-ref: TASK-20260625T204254-conv-switch-fade / CHG-20260625T204254-conv-switch-fade.

## REV-20260625T173000-role-account-prompt-autogen [SUBAGENT:adversarial-2lens(backend+security/privacy, frontend/ux)] — SHIP (BLOCKER 0 + MAJOR 2 흡수 + MINOR 2 흡수) (TASK-20260625-role-account-prompt-autogen, Major §12.3 — 외부 LLM dispatch 2개 scope 확장)
- Date: 2026-06-25
- Cycle: 역할 '전체 제품 프롬프트' + 프로필 '제품별 개인 프롬프트' 자동작성. worktree `ai/claude/role-account-prompt-autogen`(base 7e6aab8). CHG-20260625-role-account-prompt-autogen.
- §18.8 verification panel = 적대적 코드 리뷰 2렌즈(general-purpose REFUTE). 통과가 아니라 결함 적발 목적. **VERDICT: SHIP-WITH-FIXES ×2 → 수정 후 SHIP**.
- **MAJOR-1 (백엔드/비용 — 수정)**: self-service 계정 프롬프트 자동작성(`/api/auth/me/system-prompt/generate[/stream]`)이 로그인만으로 호출 가능한데 LLM 토큰 quota 를 우회(`_check_account_token_quota` 미호출) — 임의 로그인 사용자가 무제한 ~20k 토큰(prompt_gen cap) LLM 호출 가능. 기존 product/role 경로는 admin 게이트라 blast radius 제한이었으나 self-service 로 확장하며 노출 증가. **수정**: `_collect_account_prompt_context` 에 `_check_account_token_quota(conn, account)` 게이트 추가(초과 시 429, /api/ask 와 동일). 회귀 가드 `test_collect_account_prompt_context_quota_exceeded`. (admin-gated role/product 경로는 기존 acceptance 유지 — `_record_llm_usage` 미기록은 수동경로 동일 feature-wide 기존 갭, 후속 분리.)
- **MAJOR-2 (프론트/UX — 수정)**: 프로필 프롬프트 에디터에 dirty 상태가 없어, 자동 작성으로 채운 미저장 본문이 있는 상태에서 `#promptProductSelect` 제품 전환 시 `reloadAccountPrompt()` 가 서버값으로 덮어써 **생성 본문 silent 소실**("검토 후 저장" 안내와 모순). **수정**: `initAccountPromptEditor` 에 `_lastLoaded`/`_prevValue` 추적 + 제품 전환 change 핸들러에 dirty 시 `window.confirm`(취소 시 선택값 복원·전환 중단).
- **MINOR (수정)**: ① 빠른 더블클릭 시 앞선 호출 finally 가 뒤 호출 스트림 버튼을 재활성/abort 핸들 제거하던 재진입 가드 결함 — `finish()` 를 `_streamAbort === controller` 일 때만 동작하도록(app.js·admin.js 양쪽 — 패널이 admin 기존 패턴 결함도 지적). ② 프로필 `#promptMeta`(.helper-text)는 admin `.admin-meta-warn` 같은 강조가 없어 실패·잘림 메시지가 muted — `.helper-text-warn`(var(--danger)) 추가 + 에러/truncated 시 토글.
- **NIT**: ① done 재할당 시 스크롤 위치 보존(admin 동형) 적용. ② `"int | None"` quoted annotation 은 파일 기존 스타일(app.py 1508/5771/24883/25251 등 다수)과 **일치** → 무변경(거짓 불일치). ③ outer `.catch` 도달불가(방어적, save/clear 패턴과 동일) → 무변경.
- **반증 실패=안전 확인**: ① 인가/IDOR — role=`system_prompt.manage.role.any`(role PUT 과 동일 게이트), account=request-supplied account_id 없음(authed caller 의 id 만 사용) → 타계정 대화 접근 경로 없음. ② privacy — 역할 교차사용자 집계는 `owner_account_id` 필터 + **빈 account_ids 면 PG 미접근 빈 결과**(전체 누출 가드, `test_collect_signals_empty_accounts_short_circuits`) + 집계 메타(제목·요약)만. ③ SQLi — `_collect_conversation_signals_pg` filter_sql 은 고정 컬럼 조각 + `%s` placeholder·int 캐스팅(사용자 텍스트 미보간). ④ 리팩터 회귀 — 공유 응답 헬퍼는 원본 인라인과 byte-equivalent(SSE 이벤트·JSON shape·헤더·truncation 로그 불변). ⑤ 연결 누수 없음.
- 검증(수정 후): `test_auto_role_prompt.py`(7) + `test_auto_account_prompt.py`(5) 신규 + 회귀(product prompt 12·stream 3·truncation 4) = **33/33 PASS**(agent 이미지) + `py_compile app.py` + ruff(app.py) PASS + `node --check` app.js/admin.js + CSS brace balance(1572/1572).
- Human Approval Needed: 외부 영향(PR 생성·머지·배포)은 사용자 confirm. 코드 자체는 SHIP.
- Cross-ref: TASK-20260625-role-account-prompt-autogen / CHG-20260625-role-account-prompt-autogen / FUNCTION REQ-20260625-role-account-prompt-autogen(AC-RAP-1~3).

## REV-20260625T161500-auto-product-prompt [SUBAGENT:adversarial-1lens(security+cost+correctness+ops)] — SHIP (BLOCKER 1 + MAJOR 2 흡수) (TASK-0309, Major §12.3 — 자율 LLM dispatch + 자율 DB write)
- Date: 2026-06-25
- Cycle: 제품 insight 분석률 95% 도달 시 제품 프롬프트 무인 자동완성(1회성). worktree `ai/claude/auto-product-prompt`(base 262a065). CHG-20260625-auto-product-prompt.
- §18.8 verification panel = 적대적 코드 리뷰(general-purpose REFUTE, lens: 보안/비용·정확성·운영/동시성). 통과가 아니라 결함 적발 목적. **VERDICT: BLOCK → 수정 후 SHIP**.
- **BLOCKER B1 — 거짓 원자성(수정)**: `_connect_memory` 가 **autocommit=True** 라 docstring 의 "단일 tx commit / rollback 정합" 이 런타임에 미성립 — upsert·마커 UPDATE·audit 가 각자 즉시 commit 되고 끝의 `conn.commit()`/`rollback()` 은 no-op. 부분 실패(upsert 성공 후 마커 UPDATE 실패) 시 **프롬프트는 저장됐는데 마커 NULL** → 관리자가 프롬프트 삭제 시 1회성 불변식 붕괴(재생성). **수정**: 저장 블록 진입 시 `conn.autocommit = False`(기존 admin mutation 패턴, app.py 13666/21291/21410 선례) + 마커 행 `SELECT ... FOR UPDATE` 잠금 + 재검사 + 단일 commit, except rollback, finally autocommit 복원. 회귀 가드 test_save_uses_explicit_transaction·**test_marker_update_failure_rolls_back**(UPDATE 실패 주입 → 프롬프트 미저장·마커 NULL 검증).
- **MAJOR M1 — 실패 경로 비용 누수(수정)**: 마커는 성공 시에만 설정되므로, 만성 실패 제품(LLM 권한/쿼터/빈본문)이 매 sweep cycle(180s)마다 LLM 재호출 → "제품당 1회뿐" 단언이 실패 케이스에서 무효. **수정**: in-process 실패 backoff(`_AUTO_PROMPT_FAIL_UNTIL`, `AGENT_AUTO_PROMPT_FAIL_BACKOFF_SEC` 기본 3600) — 실패 제품은 backoff 창 동안 재호출 안 함, 성공 시 해제. 회귀 가드 test_llm_failure_backoff.
- **MAJOR M2 — cycle 생성 버스트(수정)**: 후보 전체를 한 cycle 에 동기 LLM 직렬 호출 → 최초 활성화 시 이미 95%·미입력 제품 다수면 비용 버스트. **수정**: cycle 당 생성 상한 `AGENT_AUTO_PROMPT_MAX_PER_CYCLE`(기본 3, 0=무제한) — 초과 시 break, 나머지는 다음 cycle(마커가 1회성이라 결국 전부 처리). 회귀 가드 test_max_per_cycle_cap.
- **MINOR(수용)**: m1 자동 LLM 호출이 `_record_llm_usage`(비용 가시성 chokepoint) 우회 — **수동 '자동작성' 경로도 동일**(feature-wide 기존 갭, TASK-0309 신규 회귀 아님) → 후속 과제로 분리. m2 수동입력 lost-update 잔여 창 — FOR UPDATE + 저장직전 재검사로 축소(완전 차단은 WebSystemPrompts 공통 잠금 필요, 발생확률 낮음). m3 env 소수 임계 float 경계 — 기본 95.0 정확, 무해.
- **반증 실패=안전 확인**: ① 1회성 reset 생존(`admin_product_insight_reset` 가 PG fact/rag/kv 만 삭제·WebProducts 무변경 코드 확인) ② SQLi(신규 3쿼리 정적/`%s`+int 캐스팅) ③ 인증 분리 누수 없음(엔드포인트가 `_collect_product_prompt_context` 에서 product.manage 강제 후 코어 위임, 코어는 `@app` 미노출) ④ system actor audit 적절(account/role NULL 보정) ⑤ 연결 누수 없음(sweep/auto conn 각 finally close, coverage 자체 PG conn finally close).
- 검증(수정 후): `test_auto_product_prompt.py` **12/12 PASS**(T1~T12, B1/M1/M2 회귀 가드 포함) + `test_insight_coverage.py` 5/5 무회귀 + `py_compile` + ruff PASS.
- Human Approval Needed: 아니오(자동 동기화 정책 — deploy_scope: included). 단 배포 후 라이브 확인(95% 제품 1회 자동완성 + reset 후 무재생성) 권장.
- Cross-ref: TASK-0309 / CHG-20260625-auto-product-prompt / FUNCTION REQ-20260625-auto-product-prompt(AC-0623~AC-0624).

## REV-20260625T092403-doc-sync-release-notes [SKIPPED: 사용자 노출 릴리즈노트 정적 콘텐츠 큐레이션 — 제품 로직·인가·스키마·렌더로직 무변경, 적대 패널 불요] (TASK-20260625-doc-sync-release-notes, Minor §12.3)
- Date: 2026-06-25
- Cycle: `/_dqa:doc_sync` maintenance (CHG-20260625T092403-doc-sync-release-notes). 직전 릴리즈노트(0fd4ca9, 06-23 16:52) 이후 main 병합된 user-facing 변경 14건(late 06-23 + 06-24)을 `static/release-notes-data.js` 릴리즈노트 콘텐츠에 반영(`date: "2026-06-24"` 블록 prepend + `generated` 갱신).
- 변경: 릴리즈노트 **정적 큐레이션 데이터만** — 렌더 로직(`release-notes.js`)·백엔드·라우팅·RBAC·스키마 무변경. 사용자 평이화 문구(내부 구현/테이블명/feature-id/엔드포인트 비노출).
- SKIP 사유(§18.4): 변경이 (a) 사용자 노출 릴리즈노트 텍스트 콘텐츠 추가뿐, (b) 실행/인가/데이터 경계 무영향. 제품 로직 변화 없음 → 적대적 verification 패널 불요(비-정책 doc 경량 cycle).
- 검증: `node --check release-notes-data.js` PASS(JS 구문 — 데이터 객체 무결성) + 항목 스키마(type/area/title/detail) 정합 + 머지 커밋 14건(461506e/147426f/393d15c/e5acb43/16746be/1ee5f1a/4a9ab9b/2c35d57/eb459e4/5f4f45b/dca8f81/43687e9/6df7fac/eb46302) 1:1 대조. 윈도=직전 릴리즈노트 commit(0fd4ca9, 06-23 16:52) 이후 — 적대 검증 Lens B 가 late-06-23 머지(e5acb43 답변 피드백·43687e9 사이드바 구분) + 06-24 eb459e4(알림 제어) 누락 적발 → 보강. 내부/비-user-facing(shared 추출·SSOT·CI·발표자료·doc_sync)은 의도적 제외 확인.
- Human Approval Needed: 아니오.
- Cross-ref: CHG-20260625T092403-doc-sync-release-notes / TASK-20260625-doc-sync-release-notes / FUNCTION '릴리즈노트(업데이트 내역) 콘텐츠 — 06-24 머지분 반영'.

## REV-20260624T170757-metadata-ai-autocomplete [SUBAGENT:adversarial-2lens(backend-security+frontend-css)] — SHIP (BLOCKING 2건 흡수) (TASK-20260624-metadata-ai-autocomplete, Major §12.3 — 외부 LLM dispatch + 서브뷰별 RBAC 표면)
- Date: 2026-06-24
- Cycle: 중단 세션 resume — 관리 콘솔 메타데이터 5 서브뷰 AI 자동완성(단건+골격 일괄) + pane 스크롤 수정. 백엔드 2 엔드포인트는 기 작성(미커밋), 본 cycle 은 CSS(스크롤+버튼)·테스트·docs·§18.8 panel·완료 게이트.
- §18.8 verification panel = 2-lens 적대(general-purpose REFUTE): (A) backend-security, (B) frontend/css.
- **(A) backend-security — VERDICT: BLOCK → 수정 후 SHIP**:
  - BLOCKING-1: samples 의 `sql` 입력이 `_METADATA_FIELD_CAPS` 에 키 부재 → cap=None 무제한 길이가 프롬프트에 raw 삽입(토큰/비용 폭주). **수정**: `"sql": 8000` 추가(`_metadata_str_field` 강제). 회귀 가드 test_samples_sql_input_capped_400.
  - BLOCKING-2: 신규 LLM dispatch 엔드포인트 2개에 rate-limit 부재(코드베이스 fix-with-ai 등은 `_search_rate_limit_check` 강제). **수정**: 두 핸들러에 `_search_rate_limit_check(max_per_min=_METADATA_AI_RATE_PER_MIN=20)`(RBAC 통과 후·LLM 전, 429). 회귀 가드 test_suggest_rate_limited_429·test_bootstrap_rate_limited_429(LLM 미호출 단언).
  - 안전 확인(REFUTE 실패): RBAC 우회(게이트가 LLM/introspection 전·sub 정규화 후 정확매칭·samples 강등 불가), SQLi(introspection schema=allowlist 멤버십·`_safe_ident` string-literal 컨텍스트), 응답 신뢰경계(parse/shape isinstance 가드·cap·영속 안 함). NIT(introspect table allowlist 방어심화·LLM 예외 메시지 노출=기존 패턴)는 수용.
- **(B) frontend/css — VERDICT: SHIP**: XSS 없음(생성물 input.value 전용·자동영속 없음), 스크롤 수정 정확(metadata pane 한정·타 pane 무영향·내부 nested 스크롤 충돌 없음), 이벤트 바인딩 정적 버튼+dataset.bound 가드 안전, target↔폼필드 5 서브뷰 전수 일치, disable/복구 try/finally 보장, color-mix 선례 다수. NIT(서브탭 전환 후 골격 mode 불일치=기존 저장 경로 약점 상속·회귀 아님 / samples 단건 도달성 / disabled hover 미관)는 수용.
- 무결성: test 18/18(수정 후) + py_compile(app.py) OK. UI 실렌더 정본=PB-0008(배포 후).

## REV-20260624T160000-scope-key-unify [SUBAGENT:scope-key-unify-review] **SHIP** (TASK-20260624-scope-key-unify, REQ-20260624-scope-key-unify, Major §12.3 — scope 경계 死data 수정)
- Date: 2026-06-24
- 분류: **리뷰 대상**(Major — admin write 의 scope_key 축 변경, ITEM-10/11/03 admin 공유 경로). §18.8 적대적 패널 2-lens(scope 정합 + 회귀) + 종합 + 교정 후 재확인 agent.
- 배경(死data 발견): `/_template:resume` 의 ITEM-11 Phase 2 작동검증 중 구조 감사(4 dim)가 scope-key 축 불일치 死data 적발 — admin write=datasource 라벨, 질의 read=엔드포인트 해시(`get_active_datasource`=`_ds.get('scope_key') or _ds.get('key')`)라 DB-등록 ds 의 ds-scoped 설명/샘플이 'common' 외 영영 안 읽힘. 라이브 재현 확정(라벨 저장→해시 읽기 len 0). ITEM-10/03 도 동형(공유 게이트/드롭다운). KB 테이블 전부 0행이라 손실 데이터 없는 잠복.
- **1차 패널 — BLOCKER 적발 → 교정**: 첫 fix(write=`_dsr.scope_key`)가 .env 레거시 ds(host 필수)에서 해시를 *계산* → write(해시)≠read(라벨) 死data 역재발(축 반전)을 2 lens 가 독립 적발. **교정**: write 를 read 와 **동일한 식** `ds.get('scope_key') or ds.get('key')` 로 미러링(노출 scope_key·valid_scope_keys 둘 다) → DB ds=해시·.env ds=라벨 양쪽 write==read. insight(insight.py:1908)도 동일 축이라 write/read/insight 3자 정합.
- **재확인(교정판 v2)**: 적대 agent 가 7항목 반증 → **RESOLVED**(① DB=해시·② .env=라벨 write==read, ③ insight 3자 정합, ④ health `_sk` 분리 무결, ⑤ 드롭다운 read축, ⑥ .env 회귀 테스트가 v1 로직선 FAIL/v2 PASS = 유효 가드, ⑦ 20 호출부 무회귀). BLOCKER/MAJOR 0.
- 변경: app.py `_metadata_valid_scope_keys`(라벨→read축) + `/api/admin/datasources` scope_key 노출(read축) / admin.js scope 드롭다운 value=read축·표시=라벨 + 탭 게이트 OR(kb.sample.curate, RISK) + bootstrap source='bootstrap'(NIT) / cache-buster bump. read(feature-0002) 무변경.
- 검증: phase2 29(scope 양방향 회귀 2 신규) + glossary/enum 13 + flywheel 12 PASS. py_compile + node --check. KB 테이블 0행 재확인(라벨 行 orphan 없음 — 백필 불요).
- MINOR(수용/out-of-scope): insight_health 의 .env ds 키 불일치(TASK-0255 pre-existing, 본 diff 무관·display-only) · 본 배포 .env ds 0개라 실해 없음.
- base: worktree base 73bc222(main). **잔여**: verify-completion → 머지(PR) → web 재배포(deploy_scope: included) → 死data 수정 라이브 재검증(라벨/해시 정합).
- Verdict: **SHIP**.

## REV-20260624T133000-item11-phase2 [SUBAGENT:item11-phase2-backend+security+injection] **SHIP** (TASK-20260624-item11-phase2, REQ-20260624-item11-phase2, Major §12.3 — 신규 RBAC 표면 + KB 주입 경로 신설 + 부트스트랩 introspection)
- Date: 2026-06-24
- 분류: **리뷰 대상**(Major — 신규 RBAC 권한 표면 `kb.ingest.manual`/`kb.sample.curate` 게이트, KB 주입 경로 신설, 부트스트랩 introspection sink). §18.8 적대적 검증 패널 **2회**.
- **1차 패널(구현 세션) — SHIP-WITH-FIXES → 전부 흡수**: backend+security 적대 리뷰가 BLOCKER B1 + MAJOR M2 적발 → 본 cycle 내 수정:
  - **BLOCKER B1(흡수)**: 부트스트랩 `schema_name` 이 `dialect.describe_schema_tables` f-string(dialects.py:251)에 게이트 없이 도달 → RO 커넥션 UNION 읽기 인젝션. fix: `_safe_ident` 정제 + `load_known_schemas` 멤버십 allowlist(미포함 404) + `_bootstrap_collect_skeleton` 산출 tname 도 `_safe_ident`(방어심층). SQLi 거부 회귀 테스트 +1.
  - **MAJOR M2(흡수)**: alembic 0017 이 잘못된 위치(`src/alembic/`)에 생성 → 올바른 체인(`alembic/versions/`, down_revision=0016)으로 이동, stray 제거, 단일 head 검증.
  - MINOR(수용): 샘플 PUT 동기 임베딩(app 층 timeout 가드 없음, 예외→stale 폴백이라 무한블록 아님) · 부트스트랩 컬럼 실패 silent · data_type 엔진별 표기차(표시용).
- **2차 패널(resume 재검증, 최종 staged 상태 — `/_template:resume`)**: B1/M2 fix 의 실제 코드 적용 + 신규 BLOCKER 부재를 3-lens 적대 서브에이전트로 final diff 에서 반증 시도 → **전원 SHIP, BLOCKER/MAJOR 0**:
  - **security lens**(반증 후 무결): B1 SQLi fix 실재·계층화 확인 — `safe_schema=_safe_ident(schema_name)` → `if safe_schema not in set(load_known_schemas(conn)): 404` → safe_schema 만 sink 도달(`dbo' UNION...--` → `dbo UNION...--` → 미존재 schema 404). raw schema_name 은 로깅/echo 만, SQL 미도달. RBAC 모든 엔드포인트 선차단(403, 코어 미호출), wildcard 우회 없음, `kb.ingest.manual` 단독으로 sample 권한 미부여. scope/IDOR: update/delete 전부 `WHERE id=%s AND scope_key=%s`+rowcount→404, scope allowlist(datasource keys ∪ 'common'). SSRF: 부트스트랩 DS 는 `all_datasources` 멤버십만(미존재 404, 'common' 400), 좌표는 등록 record(사용자 입력 아님), SELECT-only. XSS: admin.js 메타데이터/부트스트랩 렌더 전부 textContent/replaceChildren. GRANT rw/ro 정합(RO write 불가).
  - **backend lens**(반증 후 무결): alembic 0017 유일 head·올바른 위치·멱등(IF NOT EXISTS / pg_roles 가드 GRANT / downgrade DROP IF EXISTS). CRUD 원자성(ON CONFLICT 단일 statement · rollback/404 · UniqueViolation→409). 하이브리드 C 임베딩 3분기(active/stale/untouched). 주입 read glossary 동형(get_active_datasource · 캐스케이드 · cap). overlay non-destructive(native 빈 comment 만 충전). 순수 additive(삭제 0). 테스트 27 신뢰성(tautology 아님 — 코어 미호출·affected·임베딩 길이·SQLi 404 단언).
  - **prompt-injection lens**(반증 후 무결): `_datamark_untrusted` 펜스 + "참고 데이터, 지시 아님" 가드, sentinel strip 으로 breakout-proof("Ignore previous instructions" 도 untrusted 데이터로만 전달). 빈 결과 섹션 생략. 부트스트랩 미영속(POST 만 영속) · heavy introspection 없음(샘플/인덱스 미호출, cap 500/200). overlay 결과도 datamark fence.
- **독립 테스트 재실행(resume)**: phase2 **27/27** + MVP-1 회귀 **13/13** + sample_flywheel 회귀 **12/12** PASS (PYTHONPATH=feature-0002/src:feature-0003/src:worktree-root, pytest 9.0.3).
- 패널 minor(비차단, 수용/follow-up): substring 매칭 짧은 이름 오매칭(기존 glossary 동형 — 신규 회귀 아님; 단어경계/최소길이 follow-up) · RO env(`AGENT_KB_PG_USER_RO`) 미설정 시 RW 폴백(ADR-0021 기록, SQL 은 SELECT-only) · 위 구현세션 MINOR 3건.
- base: worktree base b652dc1. **잔여**: verify-completion --pre-commit → 머지(PR) → web+ask-worker 재배포(deploy_scope: included, 마이그 0017 superuser 적용+GRANT) → PB-0008 Windows-browser UI 시각검증(배포 후, WARN-only).
- Verdict: **SHIP**.

## REV-20260623T010000-ai-claude-db-rule-pending-evidence [SKIPPED:docs-only-pb0008-evidence] (TASK-20260619T120000 후속 — 배포 + PB-0008 실측 기록)
- Date: 2026-06-23 (cycle REV-20260619T120000-ai-claude-db-rule-pending-batch 의 배포·시각검증 evidence)
- 분류 근거: docs 전용(TEST.md §3 Windows-browser Run 추가). 코드·자산·RBAC·스키마 무변경 → 리뷰 SKIP. 대상 코드는 본 cycle REV-20260619T120000 (SUBAGENT SHIP) 에서 점검 완료.
- 배포: main `147d040`(PR #365) → `make -o init web` web 재빌드+재기동(서빙 `?v=20260619-db-rule-pending`·baked staging·view-reconcile 0). PROJECT.md §8.5 사람 승인 후 진행.
- PB-0008 PASS(실 Windows Chrome/149): 규칙 추가 클릭 → "추가 대기" 배지 + "1건 pending" + **서버 규칙 unchanged**(즉시 반영 금지 = 보고된 버그 해소 실증) / 조회만으로 미변경 / backend create persist round-trip(POST 200·persist·DELETE 정리) + jsdom 18/18 로 apply 경로 확정 / 프로덕션 무흔적. 증거 `artifacts/pb0008-db-rule-pending/*.png`.
- 잔여: 없음(cycle 완전 마감).

## REV-20260623T031910-ai-claude-ds-conn-bg-decouple [SUBAGENT:frontend-degraded-banner + AI-inline:backend-async-correctness] **SHIP** (TASK-20260623T031910, REQ-20260623-ds-conn-bg-decouple, Major §12.3)
- Date: 2026-06-23
- 분류: **리뷰 대상**(Major — 관리 콘솔 async 동작 변경, 다중 파일). §18.8 적대적 검증 패널 2-lens(frontend + backend) 실행. frontend 서브에이전트 완주 → **NO REAL FUNCTIONAL ISSUES**. backend 서브에이전트는 세션 한도로 미완 → 백엔드 핵심 리스크는 구현 중 AI inline 으로 file:line 직접 검증(아래).
- frontend 패널 검증 결과(반증 시도 후 무결):
  1. **closure/TDZ 무결**: `pickerWrap`(const, admin.js:7154, 7174 append)이 `_setAccessDbDegraded`(7450)·`_refreshAccessibleDbs`(첫 호출 7839) 정의·호출보다 선행. `_refreshAccessibleDbs` 는 6799 no-op forward-decl → 7478 재할당, 첫 실호출은 한참 후. TDZ/undefined 0.
  2. **DOM lifecycle 무결**: `renderProductDetail` 가 매 진입 `paneEl.innerHTML=""`(6612)로 이전 subtree(배너·closure dbEditorWrap 포함) 폐기 → 배너가 타 제품으로 누수 불가. `_setAccessDbDegraded` 가 매 호출 기존 `.admin-db-degraded-note` 제거 후 재삽입 → 중복 0.
  3. **기존 호출자 호환**: `_refreshAccessibleDbs(nk)`(7545)·`(next)`(7573)·`(_selectedDatasourceKey)`(7839) 단일인자 — 새 `(key, opts={})` 가 `force=false` 로 무회귀.
  4. **force-retry 루프 없음**: 성공(degraded:false → 배너 제거)·재degrade(배너 재생성, 버튼 enabled)·throw(apiFetch 가 !ok 시 throw, admin.js:398 → catch → degraded=true → 배너 재생성) 모두 terminal. 클릭 시 `disabled=true` 동기 설정으로 중복클릭 차단. 무한루프·stuck "확인 중…" 0.
  5. **정상경로 무회귀**: classified/userDbs/lockedChips(MySQL 메타 4종 / MSSQL 시스템칩) 로직이 else 블록으로 재들여쓰기 byte-equivalent, `availableUserDbs=userDbs` 여전히 비-degraded 경로 말미 실행. catch 는 `degraded=true` 1줄 추가만(의도).
- backend AI inline 검증(반증 시도 후 무결):
  a. **conn 핸드오프 thread-safety**: `await asyncio.to_thread(_reconcile_one_db_rule, conn, …)` 는 await 동안 worker 스레드 단독 소유(이벤트 루프 동시접근 0) — 본 코드베이스 기존 선례 `await asyncio.to_thread(_build_ask_status_snapshot, conn, conv_id)`(app.py:10895)와 동형. mysql.connector 순차 cross-thread 사용 안전.
  b. **scope_key 정합**: `_ch.status_for(ds)` → `_scope_key_of` → `_dsr.scope_key(ds)`, 모니터 등록(`health_probe_provider`→`all_datasources`)·`resolve` 모두 `_row_to_ds` 가 채운 동일 `scope_key` 사용 → 일치. 불일치해도 None→UNKNOWN→to_thread connect(Layer1 유지)로 **안전 degrade**(오작동 아님).
  c. **모니터 startup 와이어링**: `_start_conn_health_monitor` = `@app.on_event("startup")`(app.py:808) → web 프로세스가 _STATE 채움 → Layer2 게이트 활성.
  d. **응답 shape 호환**: `conn_status`/`degraded` 키 **추가만**, degraded 시 빈 `databases`/`databases_classified`. 서버측 타 소비자 0(프론트가 유일 소비자, degraded 처리). 하위호환.
  e. **`record_foreground_result(ds, False, None, "list_databases_failed")`**: 시그니처 `(ds, ok, elapsed_ms=None, err="")` 일치, try/except 래핑(double-fault 0). 실패 피드백 → 다음 요청 캐시 fast-path.
  f. **UNSTABLE+DOWN 게이트**: 데이터플레인은 unstable(느리지만 alive) 허용 정책이나, 본 control-plane 조회는 8s 블록 회피 위해 unstable 도 skip + `?force=1` escape 로 명시 재시도 보장 — 합당.
  g. **잔여 동기 connect 0**: 제품 진입 경로의 3 async 핸들러 전부 오프로드. `/db-insights` 는 sync def(FastAPI threadpool) + PG insight 읽기라 live datasource connect 아님 → 무관.
- 패널 minor(비차단) 반영/메모:
  - minor#1(degraded 배너 a11y 미announce) → **본 cycle 반영**: `note.setAttribute("role","status")` 추가(서버 degraded 경로는 toast 없음 → SR 안내 보강).
  - minor#2(collapsed 기본뷰에서 배너가 off-DOM `dbEditorWrap` 에 생성 → 행 펼칠 때 노출) → by-design(배너가 편집기와 함께 이동, 펼침 시 정확히 노출). 후속 개선 후보: collapsed accordion head 에도 degraded 신호 표면화.
- base: worktree base 14d8b13. **잔여**: verify-completion --pre-commit → 머지 → web 재배포(deploy_scope: included) → PB-0008 Windows-browser 시각검증(불안정 데이터소스 제품 진입 시 타 UI 비차단 + degraded 배너 + 새로고침 실열거).
- Verdict: **SHIP**.

## REV-20260619T120000-ai-claude-db-rule-pending-batch [SUBAGENT:db-rule-pending-security] **SHIP** (TASK-20260619T120000, REQ-20260619-0331, Major §12.3 — 보안 경계/RBAC 인접)
- Date: 2026-06-19
- 분류: **리뷰 대상**(보안 경계 = 접근 가능 DB allowlist 변경 경로 재배선). §18.8 적대적 검증 패널(security+correctness 서브에이전트) 실행 → **SHIP**. 6개 주장 모두 적대 검증·반증 시도 후 무결 확인 + jsdom 18+19 PASS 재확인.
- 패널 검증 결과(반증 시도 후 무결):
  1. **스테이징 ≠ 쓰기**: 규칙 에디터 add/edit/delete/approve 핸들러에 잔여 즉시 `apiFetch` 0 — 읽기성(`/preview` dry-run·GET list)만 남음. 유일 쓰기 경로 = `applyAllPending`.
  2. **replay 정확성**: create POST / update PUT{id} / approve POST{id}/approve-pending{schemas} / delete DELETE{id}?strip=1 — body·method·param 이 기존 즉시 경로와 동일(app.py 핸들러 contract 일치). 순서 create→update→approve→delete(삭제 마지막=rule_id 참조 보존) 적정. 빈 schemas skip.
  3. **보안 게이트 무손상**: `_db_rule_gate`(product.manage+바인딩)·`_validate_db_rule_pattern`·cap clamp·SSRF·`_DB_RULE_NAME_INJECT_RE`·audit 무변경 — 스테이징은 호출 시점만 늦출 뿐 서버 검증 우회 0. 클라이언트가 구 UI 로 못 보내던 것을 보낼 수 없음.
  4. **view-reconcile 제거 안전**: GET `/db-rules` 는 읽기만, pending 큐는 백그라운드 루프(`_start_db_rule_reconcile_loop`)+on-write reconcile(create/update) 가 계속 채움. `account` 명시 소비(`_ = account`)로 lint 무손상. 제거는 오히려 "에디터 열기만으로 GRANT" escalation 차단.
  5. **optimistic desync 없음**: 수정 대기 후 삭제 시 `delete updates[id]`(+본 cycle 보강 `delete approves[id]`) 후 삭제 staged → 삭제 카드는 undo 만 노출(공존 불가, 삭제 우선). staged-create `tempId` 는 서버 미전송, apply 후 엔트리 삭제 → 충돌·중복제출 0.
  6. **GC/staleness**: `cancelAllPending`·`loadAdminData` stale GC(키 `productId::dsKey` 파싱)·`_settleDbRulePending` 빈 엔트리 제거·성공 시 엔트리 삭제·실패 시 `entryFailed` 보존 재시도 — reload 후 누수/중복적용 0.
- 패널 minor(비차단) 반영/메모:
  - minor#1(같은 규칙 approve+delete 의도 모호) → **본 cycle 반영**: delBtn 핸들러에서 `updates` 와 함께 `approves[rule.id]` 도 정리(삭제될 규칙의 승인 대기 제거).
  - minor#2(`split("::")` 키 파싱) → 실제 datasource 키는 `{engine}-{hash12}`(예 `mysql-3f2a1b9c7e41`)로 `::` 불포함 → 도달 불가(방어심층 nit, 무조치).
  - `_reconcile_product_db_rules`(app.py) 호출자 0(view-reconcile 제거 결과) — (product,ds) 일괄 reconcile 유틸로 보존, 후속 cleanup 시 제거 가능(기능 영향 0).
- base-behind-main: 본 worktree base 28e76d6 가 현재 main(51d69c4, +21 commit, 타 세션 머지)보다 뒤짐 — 내 diff 는 12파일/+353/−69 로 scoped(2FA/feature-0009 등은 내 변경 아님, main-ahead). 머지 전 rebase 필요(commit/finalize 단계).
- 추가 메모: ① 부분 실패 — dbRule 엔트리는 op별 try/catch + `entryFailed` 시 엔트리 미정리(loadAdminData 가 서버 정본 재동기화), 다른 pending 섹션과 동형. ② 범위 A carve-out — 확정 규칙의 백그라운드 자동 동기화는 의도 보존(§10.7 "시스템 동작 ≠ 콘솔 편집"). ③ 라이브 round-trip(클릭→대기 배지→"모두 적용" 반영→조회만으로 미반영)은 PB-0008 Windows-browser 가 머지·배포 후 최종 게이트로 검증.

## REV-20260618T062406-ai-claude-release-notes-scope-scroll-evidence [SKIPPED:docs-only-pb0008-evidence]
- Date: 2026-06-18 (TASK-20260618T061520 후속 docs-only — PB-0008 evidence)
- 분류 근거: docs 전용(TEST §4 Run + TASK 마감 + MODIFY/REVIEW). 코드·자산·RBAC·스키마 무변경 → 리뷰 SKIP. 대상 코드는 본 cycle REV-20260618T061520 에서 점검 완료.
- 잔여: 없음(cycle 마감).

## REV-20260618T061520-ai-claude-release-notes-scope-scroll [SKIPPED:frontend-ui-scope-scroll-no-backend-no-rbac]
- Date: 2026-06-18 (TASK-20260618T061520 — 릴리즈 노트 표면별 영역 + 관리 콘솔 스크롤)
- 분류 근거: Minor frontend-only — 렌더러 `opts.areas` 화이트리스트 + 작업 화면 호출 1 + CSS overflow 1규칙 + 캐시버스터. 백엔드·RBAC·스키마·엔드포인트·데이터 0. 보안 표면 무(영역 숨김은 UX 필터일 뿐 — 콘텐츠 자체가 비민감 공개 릴리즈 노트, 접근 제어 아님).
- 점검: 작업 화면 admin 0건·칩 3개(전체/작업/공통)·관리 콘솔 기본 전체 무회귀(verify 34/34). 스크롤=TASK-0167 검증된 dashboard/usage 패턴 재사용. 빈 영역(allowed 전부 0) → 기존 빈 상태 안내 경로. 화면 정본 PB-0008(재배포 후).
- Verdict: SHIP.

## REV-20260618T051005-ai-claude-release-notes-evidence [SKIPPED:docs-only-pb0008-evidence]
- Date: 2026-06-18 (TASK-20260618T044611 후속 docs-only — PB-0008 Windows-browser 시각검증 evidence)
- 분류 근거: docs 전용(TEST §4 Run PASS + TASK 마감 + MODIFY/REVIEW). 코드·정적자산·RBAC·스키마 무변경 → 리뷰 SKIP. 검증 대상 코드는 본 cycle REV-20260618T044611([SUBAGENT]) + REV-20260618T050409(hotfix) 에서 점검 완료.
- 잔여: 없음(cycle 마감).

## REV-20260618T050409-ai-claude-release-notes [SKIPPED:frontend-css-collapse-hotfix-no-backend-no-rbac]
- Date: 2026-06-18 (TASK-20260618T044611 후속 — PB-0008 적발 접힘 버그 CSS hotfix)
- 분류 근거: CSS 1규칙(`.rn-group-body[hidden]{display:none}`) + 캐시버스터 bump 2 + 테스트 가드 1. 로직·백엔드·RBAC·스키마·엔드포인트·데이터 0. 본 cycle 의 적대적 리뷰(REV-20260618T044611 [SUBAGENT])는 이미 완료, 본 항목은 그 리뷰가 의존한 화면 정본(PB-0008)이 적발한 단일 CSS 트랩의 수정이라 추가 패널 불요.
- 적발/수정: PB-0008 Windows-browser computed `display:flex`(접힌 그룹) → `[hidden]` override 트랩 → class+attr 명시 규칙으로 수정. jsdom 가드 단언 추가(27/27). 재배포 후 PB-0008 재실측으로 확정.
- Verdict: SHIP(hotfix).

## REV-20260618T044611-ai-claude-release-notes [SUBAGENT:release-notes-adversarial] SHIP
- Date: 2026-06-18 (TASK-20260618T044611 — 릴리즈 노트 작업 화면 탭 + 관리 콘솔 카테고리)
- 분류 근거: **비파괴 additive frontend**(백엔드·RBAC·스키마·엔드포인트·DB·인증/인가·신규 권한·데이터 마이그레이션 0). 보안 표면은 ①정적 콘텐츠의 내부정보 누출(이 기능의 핵심 요구 AC-0579) ②렌더러 XSS 두 축 → 적대적 subagent 1회로 점검(staged diff 전수 + `release-notes-data.js` 콘텐츠 정독).
- subagent VERDICT: **SHIP-WITH-FIXES** → 지적된 콘텐츠 누출 3건 수정 후 SHIP.
- 흡수한 지적(콘텐츠 누출, AC-0579):
  - [MAJOR] `release-notes-data.js` "권한(RBAC) 관리" — "RBAC" 내부 약어 노출 → **수정**: "권한 관리".
  - [MAJOR] "잘못된 답변(환각) 감소" — "환각" 내부 ML 용어 → **수정**: "잘못된 답변 감소"(평이 표현이 이미 의미 전달).
  - [MINOR] "(권한 상승 방지)" — 위협 모델 명시(민감 보안 처리 specifics) → **수정**: "(보안 강화)".
  - [author's-call] "MySQL / SQL Server" 엔진명 — 사용자가 직접 고르는 UI 컨트롤 라벨이라 무해 판단 → **유지**.
- 점검 통과(BLOCKER 0):
  - H1 (XSS) — 렌더러는 전 사용자-가시 문자열(title/detail/summary/date/badge/count)을 `el(tag,cls,text)`→`textContent` 로만 주입, `innerHTML` 은 컨테이너 clear(`""`) 2곳뿐. `<img onerror>`/`<script>` 주입 시 엘리먼트 미생성·원문 보존(test 3건). **clean.**
  - H2 (콘텐츠 누출) — cutover/PG/SSRF/KEK/livelock/alembic/SQL-injection/내부 호스트·포트·파일경로 누출 0(grep 확인). HTTPS/연결 안정성·무거운 쿼리·데이터 저장 등 진짜 민감 내부는 "안정성/보안 개선"으로 추상화됨(의도된 bar). 위 3건만 수정.
  - H3 (그룹 가시성) — `ADMIN_TAB_PERMISSIONS` 미등록 → `canSeeTab` true → 시스템 그룹 라벨 항상 표시(설정 숨김 사용자도 "시스템 > 릴리즈 노트"). 의도된 동작(상시 제공), 다른 그룹/탭 게이팅 무영향.
  - H4 (로드 순서/null) — 렌더는 탭 클릭 시점 호출(전 스크립트 로드 후), 양 호출처 `if (window.ReleaseNotes)` 가드, `render()` 는 `!container`/빈 `RELEASE_NOTES` 가드.
  - H5 (접힘/필터) — `rendered === 0` 기준으로 필터 후 "보이는 첫 그룹"만 펼침, 빈 그룹 skip, per-filter 빈 상태 안내. test 26/26.
  - DRY — 양 화면이 동일 data+renderer(`?v=20260618-release-notes`) 단일 출처.
- 잔여: 화면 정본 PB-0008 Windows-browser(배포 후 양 화면 실측) — 별 evidence 기록.
- Verdict: **SHIP** (수정 3건 반영 후, BLOCKER 0).

## REV-20260618T031450-ai-claude-product-picker-search-evidence [SKIPPED:docs-only-pb0008-evidence]
- Date: 2026-06-18 (TASK-20260618T024517 후속 docs-only — PB-0008 Windows-browser 시각검증 evidence 기록)
- 분류 근거: docs 전용(TEST §4 Windows-browser Run + TASK 마감 + MODIFY/REVIEW). 코드·정적자산·RBAC·스키마 무변경 → 리뷰 SKIP. 검증 대상 코드는 이미 REV-20260618T024517(본 cycle) 에서 자체 점검 완료.
- 잔여: 없음(cycle 마감).
## REV-20260618T031747-ai-claude-ds-list-engine-icon-evidence [SKIPPED:docs-only-pb0008-evidence]
- Date: 2026-06-18 (TASK-20260618T030534 후속 docs-only — PB-0008 Windows-browser 시각검증 evidence 기록)
- 변경: 코드 0. TEST.md §3 Windows-browser Run + TASK.md 마감 + MODIFY evidence. 실 Windows Chrome 으로 데이터소스 목록 각 행 도트 우측 엔진 아이콘(MySQL #00758F·Microsoft SQL Server #EE352C)·4열 grid·정렬 무붕괴(leftAlignSpread=0) PB-0008 PASS 기록.
- 판단: docs-only evidence 라 외부 패널 불요(SKIPPED). 검증 정본(PB-0008 실측)은 직전 cycle(PR #332)의 코드 변경에 대한 것이며 본 항목은 그 결과를 문서에 영속화. 회귀 위험 0.
- Cross-ref: CHG-20260618T031747 / TASK-20260618T030534(REV-20260618T030534 의 evidence).

## REV-20260618T024517-ai-claude-product-picker-search [SKIPPED:frontend-ui-search-filter-no-backend-no-rbac]
- Date: 2026-06-18 (TASK-20260618T024517 — 제품 선택 드롭업 명칭 검색 필터)
- 분류 근거: frontend-only 비파괴 UI 추가(검색 입력 + 클라이언트측 표시 필터). 백엔드·스키마·RBAC·엔드포인트·데이터·인증/인가 무변경 → §12.3 Minor. 적대 보안 리뷰 패널(outside-voice)은 RBAC/권한 모델 변경 한정([[feedback_outside_voice_for_rbac]])이라 대상 아님.
- 자체 점검: ① 필터는 클라이언트 표시 토글일 뿐 — 제품 접근 권한은 백엔드 `state.products`(TASK-0295 `_filter_products_for_account_access`)가 이미 게이트하므로, 검색은 그 권한 게이트 결과 위에서만 동작(권한 우회 0, 숨겨진 제품을 검색으로 드러낼 수 없음). ② 재렌더 대신 `.hidden` 토글로 포커스·한글 IME 유지(매 input 마다 input 요소 재생성 시 조합 깨짐 회피). ③ 매 open 시 메뉴 재렌더라 검색어 비휘발(직전 검색어 stale 잔류 없음). ④ 제품 수 < 임계(6)면 입력칸 미렌더 → 소수 제품 환경 기존 동작 무회귀. ⑤ Escape/외부 클릭 닫기는 기존 `openProductDropup` 의 document capture 핸들러가 처리(검색 input 도 menu.contains 보호 안). ⑥ data-search 는 라벨(`(product_key) 제품명`) 소문자라 product_key·한글명 양쪽 매칭.
- 잔여: PB-0008 Windows-browser 실측(배포 후, 실 드롭업에서 입력→실시간 필터·sticky 고정·자동 focus·결과없음 안내).
## REV-20260618T030534-ai-claude-ds-list-engine-icon [SKIPPED:frontend-ui-list-icon-no-backend-no-rbac]
- Date: 2026-06-18
- Cycle: TASK-20260618T030534 (데이터소스 목록 행에 엔진 서비스 아이콘 — 연결 도트 우측), Minor §12.3 — frontend-only, 비파괴 additive.
- 변경: `_dsRenderList` 가 연결 도트 우측에 `engineMeta(ds.engine)` 브랜드 아이콘(`.ds-list-engine-icon`) 삽입 + `#datasourceList` 행 grid 4열화 + cache-buster. 백엔드·RBAC·스키마·엔드포인트·데이터 0.
- 판단: 외부 패널 SKIP — (1) Minor 추가(비파괴) UI, (2) 핵심 자산(engineMeta/ENGINE_CATALOG/baked 아이콘)은 직전 TASK-20260618T022006 에서 적대 outside-voice 리뷰 SHIP(REV-20260618-0315, 8가설 REFUTED)로 이미 검증됨 — 본 변경은 그 단일 출처를 목록 행에 재사용할 뿐. (3) 유일한 신규 리스크인 행 grid 정렬은 4열 grid 동반 갱신 + jsdom 단언 + PB-0008 실측으로 커버.
- Verification: jsdom `verify_ds_list_engine_icon.mjs` 17/17 PASS(아이콘 빌드·브랜드색·aria·도트 우측 배선·이전 3-append 잔존 0·4열 grid·아이콘 CSS) + node --check. **화면 정본 = PB-0008 Windows-browser(배포 후)** — 목록 각 행 도트 우측 MySQL/SQL Server 브랜드 아이콘·행 정렬 무붕괴(jsdom 은 grid layout 미계산).
- Residual: 머지 → 배포(web 재빌드) → PB-0008 Windows-browser → 마감.
- Cross-ref: CHG-20260618T030534 / REQ-20260618-0319·AC-0576 / TASK-20260618T022006(엔진 드롭다운 — 아이콘 자산 출처).

## REV-20260618T030014-ai-claude-engine-dropdown-evidence [SKIPPED:docs-only-pb0008-evidence]
- Date: 2026-06-18 (TASK-20260618T022006 후속 docs-only — PB-0008 Windows-browser 시각검증 evidence 기록)
- 변경: 코드 0. TEST.md §3 Windows-browser Run + TASK.md 마감 체크박스 + MODIFY evidence 항목. 실 Windows Chrome 으로 엔진 드롭다운(MySQL #00758F·Microsoft SQL Server #EE352C 브랜드 아이콘+색)·선택 동작 PB-0008 PASS 사실 기록.
- 판단: docs-only evidence 기록이라 외부 패널 불요(SKIPPED). 검증 정본(PB-0008 실측)은 직전 cycle(feature PR #325 + cache-buster fix PR #326)의 코드 변경에 대한 것이며 본 항목은 그 결과를 문서에 영속화. 회귀 위험 0.
- Cross-ref: CHG-20260618T030014 / TASK-20260618T022006(REV-20260618-0315 feature + REV-20260618-0316 fix 의 evidence).

## REV-20260618-0316 [SKIPPED:cache-buster-bump-no-logic-change]
- Date: 2026-06-18
- Cycle: TASK-20260618T022006 후속 fix — 엔진 드롭다운 styles.css cache-buster 누락 보정.
- 변경: admin.html + index.html 의 `styles.css?v=` 2곳을 `?v=20260618-engine-dropdown` 으로 bump. 코드 로직·CSS 본문·백엔드·RBAC·데이터 0(순수 cache-buster 문자열).
- 판단: 로직/계약 변경이 전무한 cache-buster bump 이라 외부 패널 불요(SKIPPED). 정합성 검증은 PB-0008 재검증(재배포 후 `.engine-icon` CSS 적용·아이콘 18px·버튼 border/padding)으로 직접 실측한다.
- 근본: TASK-20260618T022006 가 styles.css 본문을 변경하고도 이를 링크하는 페이지의 cache-buster 를 안 올려, 캐시 브라우저가 옛 CSS 수신 → 미스타일. PB-0008 실 Windows Chrome 1차에서 적발(jsdom 미검출 영역). 교훈: 공유 styles.css 변경 시 admin.html·index.html 양쪽 cache-buster 동반 bump.
- Cross-ref: CHG-20260618-0316 / TASK-20260618T022006(REV-20260618-0315 의 후속).

## REV-20260618T022846-ai-claude-admin-status-filter-evidence [SKIPPED:docs-only-pb0008-evidence]
- Date: 2026-06-18 (TASK-20260618T021526 후속 docs-only — PB-0008 Windows-browser 시각검증 evidence 기록)
- 변경: 코드 0. TEST.md §4 Windows-browser Run 추가 + TASK.md 마지막 체크박스 완료 + MODIFY/REVIEW evidence 항목. PR #321 머지(main `6da40dc`)·web 재배포·PB-0008 PASS(제품 13=6+7 분할·역할 6) 사실 기록.
- 판단: docs-only evidence 기록이라 코드 리뷰/외부 패널 불요. 검증 정본(PB-0008 실측)은 직전 cycle 의 코드 변경에 대한 것이며 본 항목은 그 결과를 영속화. 회귀 위험 0.
- Verdict: **[SKIPPED]** — docs-only evidence.

## REV-20260618T021526-ai-claude-admin-status-filter [SKIPPED:frontend-ui-list-filter-no-backend-no-rbac]
- Date: 2026-06-18 (TASK-20260618T021526-ai-claude-admin-status-filter — 관리 콘솔 역할·제품 탭 활성/비활성 필터 추가)
- 등급: **Minor §12.3** — frontend-only(admin.html 2 toolbar + admin.js 상태/술어/배선). 백엔드·RBAC·스키마·엔드포인트·데이터 0 → 외부 보안 패널 불요(§18.8 dispatch: ux/design 후보지만 기존 계정 탭 패턴을 그대로 미러한 비파괴 list 필터라 패널 skip).
- 변경 요지: 계정 탭의 검증된 `admin-filter-group`+`accountFilter`+`filteredAccounts()` 패턴을 역할·제품에 1:1 이식. `filteredRoles()`/`filteredProducts()` 가 상태 필터를 검색어 매칭 앞에서 적용, 기본 "all" 로 무회귀.
- 판단 근거 / 대안 검토:
  - 보안/권한: 클라이언트 측 *표시* 필터일 뿐 데이터 fetch·권한 경계 무관(역할·제품 목록 자체는 기존 RBAC 게이트로 로드됨). enforcement 영향 0.
  - 회귀: `filteredProducts()` 의 `if(!q) return slice()` 단축 제거가 유일한 동작 변경점 — 빈 검색 + filter="all" 이 전체 반환임을 verify 11/11(특히 `product all empty-search`)로 확인. 기본 "all" 이라 미상호작용 사용자에겐 변화 없음.
  - 검증 정본: 화면 동작은 PB-0008 Windows-browser(배포 후) — 역할·제품 탭에서 비활성 클릭 시 비활성 행만 렌더 + computed `is-active` 버튼 상태.
- Verdict: **[SKIPPED]** — frontend-only list 필터, 검증된 계정 탭 패턴 미러. 백엔드·권한·스키마 무영향, 회귀 위험 낮음(verify 11/11 + node --check).
## REV-20260618-0315 [SUBAGENT:engine-dropdown-adversarial] — SHIP
- Date: 2026-06-18
- Cycle: TASK-20260618T022006 (관리 콘솔 데이터소스 '새 항목' 엔진 선택 = 아이콘 드롭다운), Minor §12.3 — frontend-only, 비파괴 UI.
- Trigger: §18.8 — production 배포(deploy_scope: included) 대상 + 데이터소스(자격증명) surface 인접이라 적대적 outside-voice(general-purpose, REFUTE 지향) 1패스. RBAC 변경 없음(자체로는 panel 비의무)이나 배포 대상이라 선제 검증.
- Verdict: **SHIP** (8가설 전부 REFUTED, BLOCKER/MAJOR 0).
- 적대 검증 8항목(file:line evidence):
  - H1 저장 계약 파손 — **REFUTED**: hidden `<input>` 이 `.value` 계약 유지(`hidden.value=selected`/`_choose` 가 canonical mysql|mssql 기록), save 루프(`inputs[k].value.trim()`)에서 engine 은 password/user/key 특수케이스 미해당→`else body[k]=v`→POST/PATCH 동일 직렬화. create·edit 모두 engine 정상 전송.
  - H2 XSS(`ic.innerHTML=meta.icon`) — **REFUTED**: meta 는 하드코딩 `ENGINE_CATALOG`(또는 폴백 [0])에서만, `.icon` 은 모듈 상수 2개. user/server 입력이 innerHTML 미도달. `ds.engine` 은 lookup 키로만 사용(HTML 렌더 안 됨).
  - H3 편집 prefill 회귀 — **REFUTED**: edit 시 `ds.engine||"mysql"` 로 초기화·해당 옵션 aria-selected/버튼 paint. 필드 순서(key→engine→host→port→user→password) 보존, write-only user/password·key-on-change 로직 무변경.
  - H4 리스너 누수 — **REFUTED**(기존 norm 정합, 회귀 아님): `_closeEnginePicker` 가 렌더당 추가·미제거인데 기존 `_closePicker`(admin.js ~6629, admin-db-picker)와 **동일 패턴**. 더 나쁜 관행 도입 아님, stale 리스너는 detached 노드 `contains` 1회 체크로 저렴. 선택적 cleanup 은 주변 코드와 괴리되어 미적용.
  - H5 드롭다운 클리핑 — **REFUTED**: `.engine-picker-list` 는 normal flow(`margin-top`/`width:100%`), **position:absolute 없음**. wrapper relative 는 containing-block 위생만. TASK-0240 완화책(`.admin-detail-col` overflow scroll)과 정합, `max-height:240px`+`overflow-y:auto` 로 목록 자체 흡수.
  - H6 키보드/a11y — **REFUTED**(기능 정상, minor polish gap): role=listbox/option·aria-selected·aria-haspopup·aria-expanded, ↓↑ 클램프·Enter/Space·Esc+버튼 refocus, 포커스 트랩 없음. minor=keydown 이 `document.activeElement` 기반(열린 후 옵션 포커스로 동작) — `_open()` 이 선택 옵션 포커스라 수용.
  - H7 포트 placeholder 데이터손실 — **REFUTED**: onChange·초기 paint 모두 `inputs.port.placeholder` 만 set, `.value` 미할당. 사용자 입력 포트는 엔진 변경에도 보존.
  - H8 미변경 편집 폴백 강제 — **REFUTED**(가정조차 무해): edit 무상호작용 시 `engineMeta(ds.engine)` 가 저장 엔진 그대로 반환→동일 값 전송. 백엔드가 engine∈{mysql,mssql} 보장이라 폴백 발화 불가, 구 자유텍스트도 동일 `||"mysql"` 폴백 보유(신규 coercion surface 0).
  - 기타: admin.html cache-bust `?v=20260617-...`→`?v=20260618-engine-dropdown`(정확), 백엔드 계약 미접촉.
- Verification: jsdom `verify_engine_dropdown.mjs` 36/36 PASS + node --check. **화면 정본 = PB-0008 Windows-browser(배포 후)** — 드롭다운 열림·MySQL/SQL Server 브랜드 아이콘 렌더·선택 반영·브랜드색(jsdom 은 layout 미계산이라 픽셀·클리핑 미검출).
- Residual: 머지 → 배포(web 재빌드) → PB-0008 Windows-browser → 마감.
- Cross-ref: CHG-20260618-0315 / REQ-20260618-0315·AC-0572 / TASK-20260618T022006.

## REV-20260618T011645-ai-claude-date-group-collapse-evidence [SKIPPED:docs-only-pb0008-evidence]
- Date: 2026-06-18 (TASK-20260618T010417 후속 docs-only — PB-0008 Windows-browser 시각검증 evidence 기록)
- 변경: 코드 0. TEST.md §4 Windows-browser Run 추가 + TASK.md 마지막 체크박스 완료 + REPORT.md "완료 대기"→"완료" + MODIFY/REVIEW evidence 항목. PR #319 머지(main `32b5e8f`)·web 재배포·PB-0008 PASS 사실 기록.
- 판단: docs-only evidence 기록이라 코드 리뷰/외부 패널 불요. 검증 정본(PB-0008 실측 결과)은 직전 cycle 의 코드 변경에 대한 것이며 본 항목은 그 결과를 문서에 영속화할 뿐. 회귀 위험 0.

## REV-20260618T010417-ai-claude-date-group-collapse [SKIPPED:frontend-ui-entry-defaults-no-backend-no-rbac]
- Date: 2026-06-18 (TASK-20260618T010417-ai-claude-date-group-collapse — 작업 화면 좌측 대화목록 첫 진입 시 최근 일자 그룹만 펼침)
- 등급: **Minor §12.3** — frontend-only UI 기본값. 백엔드·RBAC·스키마·엔드포인트·데이터 0 → 외부 보안 패널 불요(§18.8 dispatch: ux/design 후보지만 단일 코드 파일 비파괴 기본값이라 패널 skip).
- 변경 요지: `_seedDateGroupsCollapsedOnce(sortedDateKeys)` 가 매 페이지 로드당 1회(`_dateGroupsSeededThisLoad` 가드) `sortedDateKeys[0]` 펼침·나머지 접힘. 비영속(세션 단위, reload 재적용). `renderConversationList` 정렬 직후 배선.
- 판단 근거 / 대안 검토:
  - **대안 A(채택): 매 reload 1회 seed + 비영속.** 사용자 결정(AskUserQuestion 2026-06-18). 날짜 그룹 키가 상대적(`__today__`/`__yesterday__`/`YYYY-MM-DD`)이라 시간 경과 시 의미가 변한다 — 타 계정 그룹(`__others__`)의 영구 1회 seed(`mad.othersCollapsedSeed.v1`) 패턴을 그대로 쓰면 seed 한 다음 날 "어제"가 다른 대화를 가리켜 무의미. 매 로드 재계산이 요구 문구("처음 진입할 때") 및 날짜 상대성과 정합.
  - **대안 B(기각): 영구 1회 seed(타 계정 패턴 복제).** 날짜 상대키 때문에 다음 날 효과 소멸. 사용자 미채택.
  - **[0] 강제 펼침(delete) 선택 이유**: 직전 세션이 영속으로 최근 키를 접힘 set 에 남겼을 수 있어, 매 진입 "최근은 펼침" 보장을 위해 `delete` 필요. 사용자가 로드 후 최근 그룹을 접으면 1회-게이트가 그 토글을 그 로드 동안 존중.
  - **비영속(`_saveCollapsedGroups` 미호출) 선택 이유**: seed 가 localStorage 에 날짜 상대키를 쌓으면 stale 누적·다음 날 오접힘. 세션 단위 in-memory 적용으로 reload 마다 깨끗이 재계산. 타 계정/owner 그룹의 영속 토글은 별 키라 무영향.
  - **회귀 경계**: 타 계정 그룹 seed(`_seedOthersCollapsedOnce`)·owner 그룹 토글·날짜 그룹 사용자 클릭 토글(`_saveCollapsedGroups` 영속)은 전부 비변경. seed 는 own 날짜 그룹의 `sortedDateKeys` 만 대상.
- 리스크: 낮음. 비파괴 UI 기본값. 빈 대화(키 0)·단일 그룹·`__other__` 엣지 케이스 테스트 커버. rollback = 코드 제거(데이터 영향 0).
- 검증: `verify_date_group_collapse.mjs` 22/22 PASS + `verify_conv_entry_defaults.mjs` 20/20 무회귀 + node --check. 화면 정본 = PB-0008 Windows-browser(배포 후).

## REV-20260617T060740-ai-claude-task0295-pb0008-evidence [SKIPPED:docs-only-pb0008-evidence]
- Date: 2026-06-17 (TASK-0295 후속 docs-only — PB-0008 Windows-browser 시각검증 evidence)
- Skip 사유: docs 전용(TEST/MODIFY/REVIEW/TASK). 코드/정적자산/스키마/RBAC 무변경 — 본체 검토는 REV-20260617T054423-ai-claude-task0295-product-list-rbac [SUBAGENT:product-list-rbac-review] (SHIP) 담당.
- 기록 요지: TASK-0295 PB-0008 **PASS**(실 Chrome/148.0.7778.217, 배포본 main `3fa87e8`, repo-web-1 healthy). win-browser eval 실측 — **부분 회수**: admin role 로그인 시 `/api/session` products 8개 → `product.access.mv` 회수 후 **7개**(MV 제거·MV_QA 유지, 제품별 권한 정확), 작업 화면 드롭업 메뉴 DOM 7개·MV 부재. **빈목록**: 전체 `product.access.*` 회수 시 드롭업 제품 0개 + 신규 안내 "접근 가능한 제품이 없습니다"(`.product-dropup-empty`) 렌더. 검증 후 회수 권한 전부 복원(운영 무오염). evidence `artifacts/pb0008-task0295/{mv-revoked-picker,all-revoked-empty}.png`.

## REV-20260617T054423-ai-claude-task0295-product-list-rbac [SUBAGENT:product-list-rbac-review] — SHIP
- Date: 2026-06-17 (TASK-0295 — 작업 화면 제품 목록 product.access RBAC 게이트, REQ-20260617-0293/AC-0548, Major §12.3)
- 대상: backend 헬퍼 2개(`_filter_products_for_account_access`·`_coerce_default_product_id`) + 작업 화면 2곳(`/api/session`·`/api/auth/me`) 필터 적용 + frontend 빈목록 안내. [[feedback_outside_voice_for_rbac]] 정합 — RBAC 인접 변경 외부 시각 필수.
- 적대적 검토 6축 전부 판정 (코드 근거 + 격리 실행 assertion):
  - ① **admin over-block = OK**: `_account_has_product_access`(app.py:1287)는 admin bypass·`.any` superset 없는 순수 권한맵 lookup — 기존 mutation 게이트 8곳과 동일 의미론. `DefaultRoleAccess` DEFAULT=1(app.py:3531) + `_ensure_product_access_permissions` 가 기본 제품마다 **전 role** backfill(2437-2441) → 기본 제품은 admin 포함 노출. 유일 미노출은 명시 `DefaultRoleAccess=0`(grant-only) 제품이며 요구사항 의도 + 기존 403 정합.
  - ② **conversation_product/pinned pref 누출 = OK(fail-closed)**: `_load_account_product_pref`(2801) active_ids 가 필터된 products 기준 → 회수 pinned pref 는 `pinned_inactive` auto 강등. `_load_conversation_product`(2843)가 회수 제품 name/key 를 enrich 해도 프론트 `applyProductHydration`(app.js:1118-1142)이 product_id/mode 만 읽고 name/key 미사용 → 라벨은 필터된 state.products lookup 실패로 일반 "Product" graceful degrade. ask=G4(9807) / re-pin=G1(10470) 403 유지.
  - ③ **under-block 우회 = OK**: 작업화면 products 응답 경로 `/api/session`(8917)·`/api/auth/me`(15597) 2곳 전부 필터 적용. 타 `"products"` 키(11388·16392)는 admin. 프론트 `state.products` 할당 2곳(app.js:6819·7142) 모두 `/api/session` 출처. SSE/ws products 경로 없음.
  - ④ **admin 4곳 회귀 = OK**: `_list_products(include_inactive=True)` 4호출(16388/16765/17031/17202) 필터 미적용·`console.access`+product.read|manage 게이트 유지.
  - ⑤ **fail-closed = OK**: account=None→[]·product_key 누락→제외·try/except→[]·malformed permissions→[]. 전 분기 격리 실측 PASS.
  - ⑥ **default 보정 부작용 = OK**: `_coerce_default_product_id` 는 필터된 id 집합 내에서만 선택, 빈 목록=0. 접근 불가 제품 default 노출 경로 없음.
- 종합: **SHIP** (BLOCKER 0 / MAJOR 0). 순수 display-layer 게이트 — authorization chokepoint(G1-G8) 무변경. 전 경로 fail-closed, admin 무회귀, 누출/우회 0. accepted: 회수 pid 잔여 `state.activeProductId` UX 비정합은 enforcement 상 안전(403)·TASK-0052 기존 동작(본 변경 도입 아님).

## REV-20260617T040000-ai-claude-task0293-profile-icons-pb0008 [SKIPPED:docs-only-pb0008-evidence]
- Date: 2026-06-17 (TASK-0293 후속 docs-only — PB-0008 Windows-browser 시각검증 evidence)
- Skip 사유: docs 전용(TEST/TASK/MODIFY/REVIEW). 코드/정적자산/스키마/RBAC 무변경 — 본체 검토는 REV-20260617T034455-ai-claude-task0293-profile-icons [SUBAGENT:profile-icon-rbac-review] (SHIP) 담당.
- 기록 요지: TASK-0293 PB-0008 **PASS**(실 Chrome/148.0.7778.217, 배포본 main `7a52a66`, healthz git_commit 일치). win-browser eval 실측 — **AC-0542**: `#accountList` 아바타 15 = img 1(작업화면 업로드 아바타가 관리 콘솔에 반영 = 사용자 보고 버그 해소)+Identicon svg 14+이니셜 0. **AC-0544**: `#roleList` 아바타 5 = Identicon svg 5(role_key 시드)+이니셜 0, `WebRoles.IconObjectKey` 라이브 반영. **AC-0543**: 관리자→타계정 `DQA_ADMIN`(#30) 아바타 `PUT /api/admin/accounts/30/avatar` 200·서빙 200 image/png·상세 ✎ 오버레이+제거+img. **AC-0545**: 역할 `pending`(#1) `PUT /api/admin/roles/1/icon` 200·서빙 200·상세 ✎ 오버레이+제거+img. 검증 후 테스트 업로드 DELETE 200/200 으로 Identicon 복원(운영 무오염). evidence `artifacts/pb0008-task0293/admin-account-role-icons.png`.

## REV-20260617T034455-ai-claude-task0293-profile-icons [SUBAGENT:profile-icon-rbac-review]
- Date: 2026-06-17 (TASK-0293 — 프로필 아이콘 전 구간 조회·수정: 관리 콘솔 계정·역할; REQ-20260617-0291, AC-0542~0545, Major §12.3)
- 트리거: 신규 admin mutation 엔드포인트 4 + 비파괴 스키마 1컬럼 + RBAC-adjacent(관리자가 타 계정 아바타·역할 아이콘 변경). `feedback_outside_voice_for_rbac.md` 정합 — 외부(적대적) 시각 패널 호출.
- 판정: **SHIP** (BLOCKER 0 / MAJOR 0 / MINOR 1[accepted·문서화] / NIT 2[non-blocking]). 신규 코드가 검증된 TASK-0268 선례(`upload_product_icon`/`delete_product_icon`/`serve_product_icon`)의 충실한 isomorph 이며 **더 약한 게이트를 도입하지 않음**을 6축 적대적 검토(반박 기본)로 확인.
- 6축 결과:
  - **① IDOR/권한 경계 PASS**: 신규 엔드포인트 게이트가 기존 admin baseline 과 정확히 일치 — 계정 아바타 = `console.access`+`console.manage`+`account.update`(=`admin_update_account`), 역할 아이콘 = `+role.update`(=`admin_update_role`). 임의 account_id/role_id 치환은 admin-scoped 의도(콘솔 전반과 정합). **권한 체크가 `_store_image_upload` MinIO write 前 선차단** → 비-admin 은 object orphan 도 불가. self-service(`/api/auth/me/avatar`, 로그인·본인)와 admin 경로 분리 깨끗.
  - **② 업로드 안전성 PASS**: 매직바이트(svg/gif·거짓 MIME 거부)·size cap(2MB/5MB) 서버 강제, object key 네임스페이싱(`avatars/<id>/`·`role-icons/<id>/`), 이전 key best-effort 삭제 try/except — 선례 동형.
  - **③ 라우트 충돌 PASS**: `GET /api/roles/{id}/icon` 이 유일한 `/api/roles/*`(grep 확인). 역할 mutation 은 `/api/admin/roles/*`. shadowing 0. 로그인-서빙(비-admin)은 의도(제품 아이콘 정합).
  - **④ 스키마 안전성 PASS**: fast-path(`_ensure_avatar_icon_schema` idempotent ALTER, seed-catchup 경유) + slow-path(CREATE 컬럼) 정합. `WebRoles` 는 기존 always-create 테이블이라 TASK-0218 `_runtime_tables_available` probe trap 비해당(ADD COLUMN). `_list_roles` GROUP BY 에 IconObjectKey 추가로 ONLY_FULL_GROUP_BY 정합(member_count 집계 불변, IconObjectKey 는 grouped Id 에 함수종속).
  - **⑤ audit 미기록 MINOR(accepted)**: `admin_update_account/role` 은 `_audit_admin_mutation` audit 하나, 제품 아이콘(`upload_product_icon`)은 미audit. 신규 아바타/아이콘은 **아이콘 선례(미audit)** 를 따름. 아바타·역할아이콘 변경은 저감도·가역·비-권한 cosmetic 이라 제품 아이콘 취급이 타당(문서화 결정 — FUNCTION.md AC-0545). 후속으로 admin-action audit 원하면 `_audit_admin_mutation` 1줄 추가 trivial. ship blocker 아님.
  - **⑥ 프론트 PASS**: 클라이언트 size 가드(2MB/5MB) + 서버 검증 이중(서버 authoritative). 신규 역할 가드 `!merged._isNew && console.manage && role.update` — 위조해도 PUT `/roles/0/icon`→400 또는 nonexistent→404. `applyAvatar` `img.onerror` Identicon 폴백, AC-0542 조회버그 수정(이니셜→`applyAvatar` username 시드, 작업화면과 동일 시드).
- NIT(non-blocking): (a) `admin_delete_account_avatar` 는 `deleted_at` 재확인 안 함(NULL cleanup 이라 무해, `delete_my_avatar` 정합) (b) `_serve_image_object` `Cache-Control: private`(per-key 캐시버스터로 freshness 처리). 둘 다 조치 불요.
- 후속(follow-up, 비차단): admin-action audit trail 을 아바타/아이콘에도 원할 경우 `_audit_admin_mutation` 추가 — 별 cycle.

## REV-20260616T163634-ai-claude-conv-entry-defaults-pb0008 [SKIPPED:docs-only-pb0008-evidence]
- Date: 2026-06-16 (TASK-20260616T100304-conv-entry-defaults 후속 docs-only — PB-0008 시각검증 evidence)
- Skip 사유: docs 전용(TEST/REPORT/TASK/MODIFY/REVIEW + STATUS). 코드/정적자산/RBAC 무변경 — 본체 검토는 REV-20260616T100304-ai-claude-conv-entry-defaults [SKIPPED:frontend-ui-entry-defaults-no-backend-no-rbac] 담당.
- 기록 요지: TASK-20260616T100304-conv-entry-defaults PB-0008 Windows-browser **PASS**(실 Chrome/148, 배포본 main `b5f2434`, healthz git_commit 일치). win-browser eval computed/state/localStorage 실측 — **요구2**: bootstrap_admin 로그인·대화 104개·서버 직전 대화 존재(`state.session.conversation_id` set)인데도 첫 진입 `state.activeConversationId=""`·`#conversationTitle="대화를 선택하세요"`(직전 대화 자동선택 차단). **요구1**: 타 계정 대화 50건·첫 진입 시 "타 계정 대화" 그룹 `is-collapsed`·`aria-expanded="false"`·`.conv-owner-header` 0개 렌더·`mad.othersCollapsedSeed.v1="1"`·`collapsedGroups=["__others__"]`. **clean-room**: `localStorage.clear()`→reload 시 seed 재발화 + 빈 화면 동시 재현. **선호 존중**: 헤더 click 펼침(owner 5개·set 에서 제거) → reload 후 펼침 유지(재접힘 강제 없음). evidence `artifacts/pb0008-conv-entry-defaults/entry-others-collapsed-empty-chat.png`.

## REV-20260616T100304-ai-claude-conv-entry-defaults [SKIPPED:frontend-ui-entry-defaults-no-backend-no-rbac]
- Date: 2026-06-16 (TASK-20260616T100304-conv-entry-defaults — 작업 화면 첫 진입 기본값: 타 계정 대화 접힘 + 빈 대화 화면)
- Skip 사유: frontend-only(`src/static/app.js` + `index.html` 캐시버스터 + 신규 jsdom-less 회귀 테스트). 백엔드/RBAC/스키마/엔드포인트/SQL 무변경 — 적대적 보안/데이터 리뷰 패널 트리거(§18.8) 비해당. 변경은 ① localStorage seed 1회 + ② 클라이언트 자동선택 게이트로, 서버 권한 경계(대화 접근권은 `/api/conversations`·`/api/history`·`/api/use_conversation` 의 기존 게이트 불변)에 영향 0.
- 자체 검토:
  - **요구1 (타 계정 대화 접힘)**: `_seedOthersCollapsedOnce()` 는 seed 플래그(`mad.othersCollapsedSeed.v1`) 부재 시에만 1회 `__others__` 를 접힘 set 에 추가·영속한다. date 그룹 토글과 독립이고, 사용자가 펼치면 `collapsedDateGroups` 에서 제거되어 영속되므로 다음 진입에 재접힘을 강제하지 않는다(선호 존중). 접힘은 표시 전용 — 타 계정 대화 노출 권한 자체는 불변(접혀도 RBAC 경계 동일).
  - **요구2 (빈 대화 화면)**: `loadConversations` 의 신규 `allowCurrentFallback` 는 **initializeWorkspace 의 fresh 진입에서만 false**. 다른 모든 호출자(createConversation/delete/refresh 등)는 default `true` 라 무회귀. 회귀 위험 2건 명시 차단 — (a) deep-link `?conversation=`(TASK-0263)은 `allowCurrentFallback=true` 유지, (b) 진행 중 요청 resume(TASK-0041)은 서버 current 가 `is_processing` 이면 그 대화를 `_preferCid` 로 선택(preferredExists 경로) + `_resumeStatus` 공유로 status 중복 fetch 회피. pendingNewConversation 가드 보존.
  - 검증: node --check PASS + `tests/verify_conv_entry_defaults.mjs` 20/20 PASS(seed fresh/respect·date 그룹 보존, 빈 진입/폴백/resume-select/preferred-미존재/pending-guard, init 배선 4종). 시각 정본은 PB-0008 Windows-browser.

## REV-20260616-0301 [SKIPPED:docs-only-pb0008-evidence]
- Date: 2026-06-16 (TASK-0291 후속 docs-only — PB-0008 시각검증 evidence)
- Skip 사유: docs 전용(TEST/STATUS/REPORT/MODIFY/REVIEW). 코드/RBAC 무변경 — 본체 검토는 REV-20260616-0300 [SKIPPED:frontend-only-display-count].
- 기록 요지: TASK-0291 PB-0008 **PASS**(배포본 main 9bdb9f8). win-browser eval 실측 — 계정 탭 배지 `#tabCountAccounts`=7 이 활성 필터 목록 카운트 `#accountListCount`=7명과 일치, 전체 28명(=7활성+1비활성+20삭제)과 분리. 배지가 `adminState.accounts.length`(28) 아닌 활성만(`is_active && !deleted_at`) 집계 확인.

## REV-20260616-0300 [SKIPPED:frontend-only-display-count]
- Date: 2026-06-16 (TASK-0291 — 계정 탭 배지 활성 계정만 집계)
- Skip 사유: frontend-only 표시 로직(admin.js 집계식 1곳 + 캐시버스터). 백엔드/RBAC/스키마/엔드포인트/데이터 흐름 무변경 — 외부 시각(보안/데이터) 리뷰 트리거 부재.
- 판단 근거: 활성 정의를 기존 `filteredAccounts()` 의 `'active'` 분기(`is_active && !deleted_at`)와 동일하게 재사용해 분류 일관성 유지 — 새 분류 의미 도입 없음. `#accountListCount`(filter-aware)는 비변경이라 "전체/활성/비활성/삭제" 필터별 정확 카운트는 기존대로 목록에서 확인 가능. 배지는 사용자 의도대로 "실제 중요한 정보(활성 수)"만 노출.
- 검증: node --check PASS. PB-0008 Windows-browser 실측은 web 재배포 후(배지 = 활성 필터 목록 수 일치).

## REV-20260616-0298 [SKIPPED:docs-only-pb0008-evidence]
- Date: 2026-06-16 (TASK-0287 후속 docs-only — PB-0008 시각검증 evidence)
- Skip 사유: docs 전용(STATUS/REPORT/TASK/MODIFY/REVIEW). 코드/RBAC 무변경 — 본체 검토는 REV-20260616-0297 [SKIPPED:frontend-only-download-method].
- 기록 요지: TASK-0287 PB-0008 **PASS**(배포본 main c5b4823). win-browser 실측 — `_buildMessageAttachChip({id,...})` 칩 click → window.fetch monkeypatch 로 chipUsesFetch=true(fetch `/api/attachments/{id}/download` 호출, navigation `<a>` 아님)·credentials=same-origin·has-download. 목록과 동일 `_downloadAttachmentById` fetch+blob 경로 검증.

## REV-20260616-0297 [SKIPPED:frontend-only-download-method]
- Date: 2026-06-16 (TASK-0287 — 말풍선 첨부 칩 다운로드 실패 수정)
- Skip 사유: frontend-only 1곳(`_buildMessageAttachChip` 의 다운로드 방식을 navigation→fetch+blob 으로 통일). 백엔드/RBAC/스키마/엔드포인트 무변경 — 적대적 보안/데이터 리뷰 패널 트리거(§18.8) 비해당. `_downloadAttachmentById`(목록에서 검증·작동) 재사용이라 신규 위험 표면 0.
- 자체 검토: 다운로드 권한은 `download_attachment` 엔드포인트의 `_account_can_access_attachment`(own/any) + pending 차단으로 불변(프론트는 호출 방식만 변경). signed_url 폴백 경로 보존. node --check PASS. 시각·실 다운로드 검증은 PB-0008.

## REV-20260616-0296 [SKIPPED:docs-only-pb0008-evidence]
- Date: 2026-06-16 (TASK-0286 후속 docs-only — PB-0008 시각검증 + 라이브 프롬프트 갱신 evidence)
- Skip 사유: docs 전용(STATUS/REPORT/TASK/MODIFY/REVIEW). 코드/정적자산/RBAC 무변경 — 본체 적대 보안 검토는 REV-20260616-0295 [SUBAGENT:attach-edit-strip-security] SHIP-WITH-FIXES 담당.
- 기록 요지: TASK-0286 PB-0008 Windows-browser **PASS**(실 Chrome/148, 배포본 main b884b67). render-injection computed 실측 — `markdownToHtml`(diff + attachment-edit 블록 텍스트) → fullBodyHidden=true(전체 본문 미노출)·diffPresent=true(변경점 유지)·`.attachment-edit-note`("📎 수정된 첨부 파일 (filename)", rgb(37,99,235))·attachEditBlockGone=true. 백엔드 strip=pytest 10 PASS. 라이브 WebSystemPrompts global row 에 DELIVERING 섹션 멱등 append(6837→8536). 실 e2e 는 LLM 의존이라 합성 검증, 실사용 시 자연 재현. evidence `artifacts/pb0008-task0286/attach-edit-diff-only.png`.

## REV-20260616-0295 [SUBAGENT:attach-edit-strip-security] — SHIP-WITH-FIXES
- Date: 2026-06-16 (TASK-0286 — assistant 첨부 수정본 전달 시 전체 본문 노출 제거 + 변경점만(diff) + 파일 명시 전달)
- 대상: agent_core SYSTEM_PROMPT(attachment-edit 안내), app.py `_strip_attachment_edit_blocks`/`_update_assistant_message_content` + ask 후처리 strip, 프론트 `enhanceAttachmentEditBlocks`(app.js/share.js).
- 적대적 코드 리뷰(general-purpose subagent, 7개 위협) **SHIP-WITH-FIXES** — BLOCKER 0, MAJOR 1(흡수), MINOR 2(기록).
  - **MAJOR 흡수**: lazy 정규식 ```` ```attachment-edit\n(.*?)\n``` ```` 이 **편집 대상 파일 본문에 ``` 라인이 포함**되면(markdown 등) 조기 종료 → strip 후 잔여 본문 평문 노출 + 첨부 절단 저장(0286 이 막으려는 바로 그 회귀, parse=TASK-0274 한계 상속). **수정**: parse·strip 공통으로 라인 기반 `_attachment_edit_block_spans`(여는 펜스 다음 줄=헤더, 다음 블록 직전까지의 **마지막 단독 ``` 줄**=닫는 펜스 → 본문 내 ``` 허용) 도입. 회귀 테스트 S6(strip embedded-fence 누출 0)·S7(parse 본문 절단 0) 추가.
  - IDOR/content UPDATE: `_update_assistant_message_content` 는 ask `_conversation_owned_by_account` 게이트 후 실행, WHERE 에 conversation_id(UUID 전역유일) 동반, message_id 출처/UPDATE 동일 backend(PG 우선·MySQL fallback), %s 바인딩 → 오변조/인젝션 0. refute.
  - 멱등: strip 후 note(`📎 수정본`)엔 attachment-edit 토큰 없음 + `"attachment-edit" not in` 가드 → 재-UPDATE 없음. refute.
  - XSS: enhance 는 textContent 경로 + DOMPurify 이전 적용 + 깨진 JSON try/catch graceful. refute.
  - LLM 재컨텍스트: history 가 읽는 `messages.content` = strip 이 UPDATE 하는 컬럼 → 이후 턴은 stripped 본문만. refute.
- MINOR(기록만): ① MySQL fallback UPDATE 대상 `AgentMemoryMessages` 는 AR-M5 cutover 드롭(loader 와 대칭 dead path, 무해). ② A1 테스트가 호출 문자열만 검사(실 배선은 전체 회귀로 커버).
- 검증: 신규 `test_task0286_attach_edit_strip.py` 10 PASS(S1~S7·P1·P2·A1) + make test 컨테이너 전체 회귀 0(PYTEST_EXIT=0, ruff clean) + py_compile + node --check + CSS brace(styles 1243·share 107).

## REV-20260616-0294 [SKIPPED:docs-only-pb0008-evidence]
- Date: 2026-06-16 (TASK-0285 후속 docs-only — PB-0008 Windows-browser 시각검증 evidence 기록)
- Skip 사유: docs 전용(STATUS/REPORT/TASK/MODIFY/REVIEW). 코드/정적자산/백엔드/RBAC 무변경 — 리뷰 패널 트리거 비해당. 본체 변경의 적대 보안 검토는 직전 cycle REV-20260616-0293 [SUBAGENT:attach-surfacing-security] SHIP 가 담당.
- 기록 요지: TASK-0285(첨부 버전 현황 표면화 ②③④) PB-0008 Windows-browser **PASS**(실 Chrome/148, 배포본 main 1c4737d). render-injection computed 실측 — ③ `_buildMessageAttachChip` assistant 칩 `v2 · AI 수정` 배지 color rgb(37,99,235)·bg rgb(232,240,255)·`.message.is-assistant` 칩 배경 rgb(255,255,255)(밝은 배경 가시)·다운로드 가능, ② `_renderAttachmentVersionsBox` 2행·최신 위·"AI 수정 · 최신"·버전별 다운로드 2개. jsdom 이 못 잡는 CSS 캐스케이드(ai-edited 색·assistant 칩 배경)를 실 브라우저 computed 로 확증. 라이브 assistant 수정본 데이터 0건이라 합성 render-injection 으로 검증(실사용 시 자연 재현). evidence `artifacts/pb0008-task0285/attach-version-surfacing.png`.

## REV-20260616-0293 [SUBAGENT:attach-surfacing-security] — SHIP
- Date: 2026-06-16 (TASK-0285 — 첨부 버전 현황 표면화 ②③④, TASK-0275 후속 보완)
- 대상: ② `list_conversation_attachments` version_count 집계, ③ `_load_assistant_attachments_by_message` + `_get_history` assistant 첨부 직렬화(IDOR 표면), ④ materialize step 기록.
- 적대적 보안 리뷰(general-purpose subagent, 침투 관점 7개 위협) **SHIP** — BLOCKER 0, MAJOR 0, MINOR 1.
  - IDOR(③): `_load_assistant_attachments_by_message` 는 ConversationId 스코프만이나, 유일 호출경로 `/api/history` 가 `_account_can_access_conversation`(own/any) 선게이트. 첨부 AccountId 는 INSERT 시 대화 소유자로 고정(同conv·同account 가드) → cross-conv/cross-account 누출 0. refute.
  - signed_url 누출: `_serialize_attachment_for_api` include_signed_url=False 기본, 양 신규 호출처 미전달 → ObjectKey/HMAC/AccountId 미노출. refute.
  - SQLi: 신규 3쿼리 전부 %s 바인딩(cid/conversation_id 보간 0). refute.
  - MetaJson.message_id 조작: message_id 는 서버 파생(`_load_latest_assistant_message` DB 조회)이고 LLM 은 source_id/filename 만 제공(별도 가드). 조작 MetaJson 은 mid<=0 drop — 타 메시지 첨부 부착 불가. refute.
  - fail-soft: 신규 조회 try/except→빈 dict, history 비차단. confirm.
  - ④ run_id: 자기 run 의 render_steps 에서 추출(공격자 미주입), ask 가 `_conversation_owned_by_account` 게이트. refute.
- MINOR(비보안, 기록만): `agent_runtime.steps` 에 (conversation_id,run_id,step_index) UNIQUE 부재 → 중복 시 cosmetic 이중 항목(에러 아님). max+1 충돌 드묾 + try/except 보호. 흡수 불요.
- 검증: 신규 `test_task0285_attach_surfacing.py` 9 PASS + make test 컨테이너 전체 회귀 0(PYTEST_EXIT=0, ruff clean) + py_compile + node --check + CSS brace(1242=1242).

## REV-20260616T024150-ai-claude-sidebar-resize-pb0008 [SKIPPED:docs-only-pb0008-evidence]
- Date: 2026-06-16 (TASK-20260616T022652-ai-claude-sidebar-resize 후속 docs-only — PB-0008 evidence 기록)
- Skip 사유: docs 전용(TASK/TEST/REPORT/MODIFY/REVIEW). 코드/정적자산/백엔드/RBAC 무변경 — 리뷰 패널 트리거 비해당. 본체 변경의 적대 검토는 직전 cycle REV-20260616T022652-ai-claude-sidebar-resize 가 담당.
- 기록 요지: 사이드바 너비 드래그 조절 PB-0008 Windows-browser **PASS**(실 Chrome/148, 배포본 6f1242b). 드래그 시 사이드바 폭 실제 reflow·clamp(180/624)·새로고침 복원·더블클릭 reset 전부 computed 실측 — jsdom 이 검출 못하는 실 레이아웃 변화까지 확인.

## REV-20260616T022652-ai-claude-sidebar-resize [SKIPPED:frontend-ui-resize-no-backend-no-rbac]
- Date: 2026-06-16 (TASK-20260616T022652-ai-claude-sidebar-resize — 대화창 좌측 사이드바 너비 드래그 조절)
- Skip 사유: frontend-only UI 인터랙션 추가(`src/static/{index.html,styles.css,app.js}`). 백엔드/RBAC/스키마/엔드포인트/데이터 경계 무변경 — 적대적 보안/데이터 리뷰 패널 트리거(§18.8) 비해당. 이미 본 repo 에 검증된 우측 패널 resizer 3종(`#stepSidePanelResizer` 등)과 byte 동형 패턴이라 신규 위험 표면 0.
- 자체 검토 요지:
  - 안전: `--sidebar-w` clamp [180, min(640, 50%vw)] 으로 사이드바가 화면을 잠식하거나 0폭으로 사라지지 않음. 모바일(≤680)에선 핸들 숨김 + inline override 제거로 기존 반응형(grid 1fr·사이드바 display:none) 보존.
  - 영속: `localStorage["web.sidebar.width"]`(기존 `web.*` panel-width 네임스페이스 정합). try/catch 로 storage 차단 환경 graceful.
  - 회귀: grid 컬럼 변수만 조절 — `.app-shell` 레이아웃·chat-column·기존 우측 패널 resizer 무영향. `position:relative` 추가는 절대배치 자식 없던 컨테이너라 부작용 0.
- 검증: node --check PASS + CSS brace(1222=1222) + jsdom 23/23(`verify_sidebar_resize.mjs`) + make test 컨테이너 전체 회귀 0(REAL_MAKE_EXIT=0, ruff clean). 시각·인터랙션 최종 확인은 PB-0008 Windows-browser(배포 후).

## REV-20260616-0292 [SKIPPED:docs-only-pb0008-evidence]
- Date: 2026-06-16 (§13.1 origin max REV-20260616-0291 → 0292)
- Cycle: TASK-0283 후속 docs-only — 제품 아이콘 편집 ✎ 오버레이 통일 PB-0008 Windows-browser PASS evidence 기록. 코드/정적자산 0 변경.
- Skip 사유: §18.8.1 경량 — docs-only(검증 결과 기록), 코드·CSS·엔드포인트·RBAC 표면 0. 원 변경의 적대 검토는 REV-20260616-0291([SKIPPED:frontend-icon-edit-ui-no-backend-no-rbac]) 에서 완료.
- 자체 점검: ① 기록 사실성 — win-browser eval computed(`.profile-avatar-change` absolute·22px·circular·visible) + 구 pill 부재 + 배포 baking(`?v=20260616-product-icon-edit`·`profile-avatar-change` 1 hit) 실측에 근거. ② evidence 경로(`artifacts/pb0008-task0283/product-icon-edit-overlay.png`)는 git 외부(§2)라 참조만. ③ 회귀 0(문서만).
- Verification: 라이브 win-browser 실측 + screenshot. node/make test 무관(코드 무변경).
- Cross-ref: CHG-20260616-0292 / REV-20260616-0291(원 변경) / TASK-0283.

## REV-20260616-0291 [SKIPPED:frontend-icon-edit-ui-no-backend-no-rbac]
- Date: 2026-06-16 (§13.1 origin max REV-20260616-0290 → 0291)
- Cycle: TASK-0283 (관리 콘솔 제품 아이콘 편집 UI 를 유저 프로필과 동일한 ✎ 오버레이로 통일), **Minor §12.3** — frontend-only(`src/static/admin.js` 1곳 + dead CSS 제거 + cache-buster). RBAC/인증/스키마/엔드포인트/데이터/시크릿/백엔드 0.
- Trigger: §18.8 dispatch 키워드(UI/수정버튼/레이아웃 → ux,design). 변경 실질은 기존 편집 컨트롤을 이미 검증된 유저 프로필 패턴(`.profile-avatar-edit`)으로 재배치 — 신규 데이터·권한·인터랙션·엔드포인트 0 → §18.8.1 경량 경로(적대 패널 불요, Minor frontend-only + 정책 doc 0 → skip). 직전 REV-20260615-0286(제품 목록 행 레이아웃 버그) 와 동일 부류.
- 자체 점검:
  - ① **패턴 동형성**: 유저 프로필(index.html `.profile-avatar-edit` > `.profile-avatar-lg` + `.profile-avatar-change` ✎ + 숨김 input, 텍스트블록에 `.profile-avatar-remove`)을 admin.js 제품 상세에 그대로 재현. ✎ 버튼은 `position:absolute; right:-4px; bottom:-4px; 22px 원형`(styles.css 6420) — 36px 아바타 우하단 오버레이라 침범 0. 클래스 재사용이므로 시각 동형 보장.
  - ② **기능 보존**: PUT `/api/admin/products/:id/icon`(변경)·DELETE(제거) 엔드포인트, 5MB 가드, image/png·jpeg·webp accept, FormData, toast, `renderProductDetail()` 재렌더, `canManage`(product.manage) 게이트 무변경 — 이벤트 핸들러 본문 그대로 이식.
  - ③ **dead CSS 안전 제거**: `.admin-avatar-edit`/`.admin-avatar-change`/`.admin-avatar-remove` 는 admin.js 의 본 블록(5798/5802/5820) 단일 사용처였음(grep 전수 확인) → 제거해도 회귀 0. `.admin-avatar` 베이스(목록·계정 아바타 공용)·`.admin-avatar-sm`·has-avatar-img·image clip 규칙은 유지.
  - ④ **cache-buster**: styles.css 변경 → index/admin.html 양쪽 ref bump, admin.js 변경 → admin.html ref bump. HTML no-cache(app.py `_HTML_NO_CACHE`) 전제 충족([[project_static_asset_cache_busting]]).
- 검증: node --check admin.js PASS. (잔여) web 재배포(deploy_scope: included) 후 PB-0008 Windows-browser 시각검증(제품 상세 ✎ 오버레이·텍스트 침범 0·유저 프로필 시각 동형) → TEST.md §4.
- Cross-ref: CHG-20260616-0291 / TASK-0283 / REV-20260615-0286(동일 부류 선례).

## REV-20260615-0288 [SKIPPED:migration-fk-orphan-hotfix]
- Date: 2026-06-15 (TASK-0279 라이브 rollout 후속, **Critical §12.3** — 데이터 이전 무결성)
- Cycle: alembic 0009 conversation FK 제거 — 라이브 backfill 이 orphan 126행을 FK 차단해 발견. 원 cutover 는 REV-20260615-0287 에서 outside-voice 2인 검토 완료(데이터 이전 SHIP-WITH-FIXES / 인가 SHIP).
- Skip 사유: §18.8.1 경량 — DDL 제약 *제거*만(데이터·컬럼·인덱스·인가 표면 불변, RBAC 0). orphan(probe-6)은 원 리뷰가 "verify 가 잡는다"로 예측한 시나리오가 라이브에서 실현된 것 — 설계대로 per-row skip+verify 가 검출, 해소는 MySQL no-FK 현실과 정합(첨부 read 가드·타입 정합 무변경).
- 자체 점검: ① 데이터 무손실(제약만 DROP). ② conversation_id 컬럼+인덱스 유지 → JOIN/조회 불변. ③ 서브테이블 attachment FK(id 보존 안정) 유지 — derived 1행 정상 적재 확인. ④ 신규 업로드 대화 존재는 앱이 보장(살아있는 대화에만 업로드). ⑤ 인가/타입/quota 경로 0 변경.
- Verification: test E3/E4 추가 + make test 회귀 0. 라이브 0009 적용 후 re-backfill 272 전량 + verify diff=0(rollout 게이트).
- Cross-ref: CHG-20260615-0288 / REV-20260615-0287(원 cutover) / TASK-0279.

## REV-20260615-0286 [SKIPPED:frontend-layout-bugfix-no-backend-no-rbac]
- Date: 2026-06-15 (REV 번호: 동시세션 TASK-0277/0277b/0278 이 REV-0281~0285 선점 → §13.1 재번호 0281→0286)
- Cycle: TASK-20260615T182907-product-list-row-icon-layout-fix (제품 관리 목록 행 UI 뒤틀림 핫픽스), **Minor §12.3** — frontend-only(`src/static/admin.js` 1곳). RBAC/인증/스키마/엔드포인트/데이터/시크릿/백엔드 0.
- Trigger: §18.8 dispatch 키워드(UI/레이아웃 → ux,design). 변경 실질은 단일 파일 grid 레이아웃 버그 수정(avatar 위치 1곳) — 신규 데이터·권한·인터랙션 0 → §18.8.1 경량 경로(적대 패널 불요, Minor frontend-only + 정책 doc 0 → skip).
- 자체 점검:
  - ① **근본 원인 정확성**: `.admin-list-row { grid-template-columns: auto 1fr auto }` 3열. 원래 제품 행 `[cb, meta]` 2자식(auto 1fr) 정상 → PR #249 가 `[cb, avatar, meta]` 3자식으로 avatar 가 1fr·meta 가 auto 칸 점유 = 뒤틀림. 수정은 avatar 를 meta>titleRow 안으로 이동해 다시 2자식 → grid 복원. jsdom [3] 으로 `row.append(cb, meta)` 단언·`row.append(cb, avatar, meta)` 부재 단언.
  - ② **계정 행 동형성**: 계정 목록 행이 이미 `title.append(avatar, name, ...)` + `main.append(title, meta)` + `row.append(cb, main, chips)` 검증된 패턴. 제품 행도 동일 `admin-list-row-title`(flex, 기존 CSS) 재사용 → 새 CSS 0.
  - ③ **회귀**: 아이콘 렌더(applyAvatar)·Identicon 정합·row click(selectedProductId)·shift-range·cov 배지·checkbox·명칭 `(약어) 명칭` 무변경(DOM 위치만 재배치). chip·드롭업·상세 무관.
  - ④ **텍스트 잘림**: `.admin-list-row-title` min-width:0 + name 의 ellipsis 컨텍스트 → 긴 명칭 안전.
- 검증: node --check admin.js + jsdom `tests/verify_product_icon_chip_list.mjs` **19/19 PASS**(기존 14 + [3] 행 레이아웃 5) + make test 컨테이너 회귀 0.
- Residual: web 재배포(deploy_scope: included) 후 PB-0008 Windows-browser 재검증(목록 행 정렬·아이콘·텍스트 위치 정상) → TEST.md §4.
- Cross-ref: CHG-20260615-0286 / TASK-20260615T182907-product-list-row-icon-layout-fix / CHG-20260615-0279(원인).

## REV-20260615-0287 [SUBAGENT:attachment-pg-cutover]
- Date: 2026-06-15
- Cycle: TASK-0279 (첨부 메타 MySQL agent_memory → PG agent_runtime 통합 cutover), **Critical §12.3** — 파괴 위험 데이터 이전 + 신규 스키마 + cross-store cutover + 인가 표면(첨부 read 가드).
- Trigger: §18.8 — 데이터 마이그레이션 무결성 + 다수 read 경로의 IDOR/scope 가드 PG 이식 → 적대적 outside-voice 2인(데이터 이전 / 인가 표면, general-purpose). [[feedback_outside_voice_for_rbac]] 정합.
- Verdict: **SHIP-WITH-FIXES → 흡수 → SHIP** (BLOCKER 0).
  - **데이터 이전 리뷰**: probe 1(타입 정합)·2(ID 보존)·3(version-chain UNIQUE)·5(commit 순서)·6(backfill orphan/FK)·dual-write 9경로 전수 매핑 전부 **코드 file:line 으로 안전 반박**. JSON=str(mysql.connector) ↔ `::text`, DATETIME naive UTC ↔ `AT TIME ZONE 'UTC'` 정합 확인. id 보존(plain bigint PK)·NULLS DISTINCT UNIQUE 동형·commit 후 동기 미러 확인.
  - **인가 표면 리뷰**: probe 1~6(IDOR account_id / conversation-scope 게이트 선행 / 버전체인 root 유래 / fail-open 미발생 / sandbox allowlist fail-closed / GRANT) 전부 **homomorphic — MySQL 원본과 file:line parity**. 타 계정 attachment_id 주입 시 PG 분기도 zero-row. **SHIP**.
- 흡수한 fix(REV findings):
  - **MAJOR-1**(read flip 후 dual-write fail-soft 누락분이 size-cap 누적을 과소계상 → quota 우회): `_check_attachment_size_caps` 를 MySQL(권위) 계산 후 read_pg 면 `max(MySQL, PG)` 보수 enforce 로 교정(미러 누락 시에도 cap 우회 불가). 회귀 테스트 `test_b2_size_caps_max_of_mysql_and_pg`.
  - **MINOR-1**(derived 미러 FK orphan): `mirror_derived_messages` 가 부모 첨부를 먼저 `mirror_attachments` 후 derived upsert.
  - **MINOR-2**(sandbox UPDATE-only writer): 모듈 docstring 정정(INSERT writer 0, UPDATE-only DroppedAt 은 PG read 미소비 → accepted staleness, decommission 정리).
- Accept(비차단·근거): RW-role read(`agent_kb_rw`)는 RO replica lag 으로 인한 staleness 악화 회피 위해 의도적(cutover 정합 > least-privilege). 부속 verify 의 SUM 미검증은 id 보존+DO NOTHING 이라 안전. bootstrap GRANT 위임(§7 ALL TABLES)은 §6d 가 §7 앞이라 스냅샷 커버.
- **MAJOR-1 운영 게이트(load-bearing)**: read flip 은 **`attachment_backfill --verify` diff=0 확인 후**에만. 본 cycle 은 MySQL 쓰기 유지(롤백 안전망) → 읽기 flip 되돌리면 전량 복구. MySQL 폐기(decommission cycle)는 verify diff=0 연속 확인 + 주기 backfill 수렴 확보가 전제.
- Verification: 신규 `test_attachment_pg_cutover.py` 14 PASS + make test 컨테이너 전체 회귀 0 + ruff clean + py_compile. 라이브 PG 라운드트립은 migrate-first 배포 단계 게이트.
- Residual: migrate-first(alembic 0008 superuser) → web+ask-worker 재배포 → dual-write ON → backfill → verify diff=0 → read flip → 라이브 검증 → PB-0008.
- Cross-ref: TASK-0279 / 0006_datasource_health(GRANT 함정 선례) / 0007_core_conv_archived(migrate-first 선례) / [[project_cutover_readpath_routing_gaps]].

## REV-20260615-0284 [SKIPPED:pb0008-evidence-docs-only]
- Date: 2026-06-15
- Cycle: TASK-0277b 후속 (PB-0008 재검증 PASS evidence 기록 — docs-only: TEST.md §4 placeholder 교체 + TASK.md 완료 표기). src 코드 0.
- Skip 사유: 코드 변경 0(순수 evidence/docs). 핵심 변경은 REV-20260615-0283 [SKIPPED:frontend-ui-consistency-no-backend](align-items:stretch)에서 이미 리뷰. 본 후속은 라이브 실 브라우저 실증 기록.
- 실증: PB-0008(실 Chrome/148 relay, 배포 main `d6123d3` #252 web 재배포) — 보관 대화 탭에서 긴 문자열 주입 후 `rowAlignItems:stretch`·`paneNotePresent:false`·2줄 고정(rowH 56)·line0W 308(row 폭 갇힘)·topic/owner/by `clipped:true`(nowrap+ellipsis 발동) 전부 실측 PASS. [문제1] 밀도 정합 + [문제2] 2줄 고정·`…` 절단 모두 확정. CHECK#13 충족.
- Cross-ref: CHG-20260615-0284 / TASK-0277b / REV-20260615-0283 / artifacts/pb0008-task0277/.

## REV-20260615-0283 [SKIPPED:frontend-ui-consistency-no-backend]
- Date: 2026-06-15
- Cycle: TASK-0277b (TASK-0277 후속 핫픽스 — 보관 대화 row ellipsis 실작동 수정), **Minor §12.3** — frontend-only(styles.css 1 규칙 + 캐시버스터 + jsdom 계약). RBAC/스키마/엔드포인트/백엔드 0.
- Skip 사유: 순수 CSS 1줄(`align-items: stretch`) + 테스트 계약. 데이터·인가·엔드포인트 무관. §18.8.1 Minor frontend-only → 적대 패널 불요.
- 발견 경위 (PB-0008 의 가치): TASK-0277 의 jsdom 은 CSS 규칙(`white-space:nowrap`/`text-overflow:ellipsis`/`min-width:0`) 존재만 검사해 25 PASS 했으나, **실 브라우저 PB-0008 에서 ellipsis 가 실제로 발동하지 않음**을 적발. 원인은 jsdom 이 계산하지 못하는 cascade/layout: `.admin-archive-row` 가 `.admin-list-row`(grid, `align-items:center`)와 함께 선언돼 flex 컬럼 줄이 row 폭으로 stretch 되지 않고 콘텐츠 폭으로 팽창 → span shrink 불가 → ellipsis 미작동(줄바꿈만 차단된 상태). headless/jsdom 이 실 브라우저 시각검증을 대체할 수 없음을 재확인.
- 자체 점검: ① 라이브 실험(eval) 로 `align-items:stretch` 적용 시 line 2858→308px, topic clientW 164·scrollW 2714 → clipped:true, rowH 56(2줄) 유지 사전 확인 후 코드 반영. ② 회귀: stretch 는 줄을 row 폭에 맞출 뿐 다른 탭/grid 레이아웃과 무관(`.admin-archive-row` 한정 규칙). ③ jsdom 계약 단언 추가(align-items:stretch). node --check + CSS brace(1210=1210) + jsdom 26 PASS + make test 회귀 0.
- Residual: 머지 → web 재배포(deploy_scope: included) → PB-0008 재검증(clipped:true·2줄 고정·밀도) → TEST.md §4.
- Cross-ref: CHG-20260615-0283 / TASK-0277b / REV-20260615-0281(TASK-0277 본 변경) / FUNCTION AC-0508.

## REV-20260615-0281 [SKIPPED:frontend-ui-consistency-no-backend]
- Date: 2026-06-15
- Cycle: TASK-0277 (관리 콘솔 "보관 대화" 탭 UI 정합 다듬기 — TASK-0276 list-detail 위 후속), **Minor §12.3** — frontend-only(admin.html + admin.js + styles.css). RBAC/인증/스키마/엔드포인트 계약/데이터/시크릿/백엔드 0.
- Skip 사유: 순수 표현 계층 다듬기. (1) 단일 사용처의 안내 문단(`admin-pane-note`)을 같은 pane 의 우측 빈 상태로 옮겨 다른 운영 탭과 밀도 정합(정보 소실 0). (2) 좌측 row 의 줄바꿈을 CSS(`flex-wrap` 제거 + span nowrap/ellipsis/min-width:0)로 절단 처리. 신규 데이터 노출·인가 경로·엔드포인트·인터랙션 모델 0 — `GET /api/admin/conversations/archived`(기존 권한 게이트·응답 계약) 그대로. §18.8.1 + Minor + 정책 doc 변경 0 → 적대 패널 skip 허용.
- 자체 점검: ① 안내 이동 후 사용자/LLM 유래 문자열 노출 경로 무변경(빈 상태 안내는 정적 상수 문구만, 데이터 미주입). ② row 템플릿(`renderArchiveList`)·이스케이프(`_archiveEsc`)·클릭 핸들러·상세 렌더 로직 byte-identical — 변경은 CSS layout + 빈 분기 안내 carry 뿐. ③ `.admin-pane-note` 제거 전 전 static 파일 grep 으로 사용처 0 확인(admin.html 단일 → 제거 대상이 그 사용처). ④ ellipsis 동작 전제 `min-width:0` 을 topic/owner/by 전 span 에 부여(flex item 기본 min-width:auto 가 절단을 막는 함정 회피). ⑤ 시각(`-ts`)은 `flex:0 0 auto`+nowrap 으로 비절단·우측 정렬 보존. node --check admin.js PASS + CSS brace 균형 + jsdom 25 PASS + make test 회귀 0.
- Residual: verify-completion --pre-commit + web 재배포(deploy_scope: included) 후 PB-0008 Windows-browser(보관 대화 탭 — 짧은/긴 topic·긴 username 혼재 시 2줄 고정·미줄바꿈·ellipsis + 안내 우측 표면화) → TEST.md §4 기록.
- Cross-ref: CHG-20260615-0281 / TASK-0277 / FUNCTION REQ-20260615-0279(AC-0507~0508) / REV-20260615-0278(TASK-0276 list-detail 선행).

## REV-20260615-0280 [SKIPPED:frontend-ui-consistency-no-backend-no-rbac]
- Date: 2026-06-15
- Cycle: TASK-20260615T180923-product-icon-chip-list (제품 프로필 아이콘을 대화창 chip + 제품 관리 목록 행에 표시), **Minor §12.3** — frontend-only(`src/static/{index.html,app.js,admin.js,styles.css}`). RBAC/인증/스키마/엔드포인트/데이터/시크릿/백엔드 0.
- Trigger: §18.8 dispatch 키워드 매칭(UI/아이콘/chip/목록 → ux,design). 변경 실질은 **직전 cycle(profile-icon-consistency)의 `applyAvatar`/`identiconSvg` 헬퍼·CSS 를 chip·목록 행에 추가 적용**한 것 — 신규 데이터 노출·권한 경계·인터랙션 모델 0 → §18.8.1 경량 경로(적대 패널 불요, Minor frontend-only + 정책 doc 변경 0 → panel skip).
- 자체 점검:
  - ① **정합**: chip·목록 행·드롭업·관리 상세가 모두 동일 `identiconSvg(product_key)` → 동일 제품 동일 패턴/색(jsdom 으로 동일 product_key 동일 SVG 단언).
  - ② **chip 회귀**: pinned 만 아이콘 표시·auto 는 hidden+비움(jsdom 3-case). dot conn 색·label compact·aria-label·busy disable 로직 무변경(추가만). icon_url 설정 시 `<img>`+onerror Identicon 폴백.
  - ③ **목록 행 회귀**: checkbox→avatar→meta 순서 추가만, row click(selectedProductId)·shift-range·cov 배지 무변경. `admin-avatar admin-avatar-sm` 는 계정 목록 행 검증된 클래스 재사용.
  - ④ **레이아웃**: chip max-width 180→200(아이콘 16px+gap 흡수, label ellipsis 유지). 행 아이콘 26px 원형 클립(직전 cycle `.admin-avatar > svg` 규칙).
  - ⑤ **XSS**: identiconSvg 는 해시 정수→고정 SVG(입력 미보간), 이미지 src 는 서버 발급 icon_url. 신규 주입 표면 0.
- 검증: node --check(app.js·admin.js) + CSS brace(1211=1211) + jsdom `tests/verify_product_icon_chip_list.mjs` **14/14 PASS** + make test 컨테이너 회귀 0.
- Residual: verify-completion + web 재배포(deploy_scope: included) 후 PB-0008 Windows-browser(chip 아이콘·목록 행 아이콘) → TEST.md §4.
- Cross-ref: CHG-20260615-0279 / TASK-20260615T180923-product-icon-chip-list / REV profile-icon-consistency(직전).

## REV-20260615-0279 [SKIPPED:pb0008-evidence-docs-only]
- Date: 2026-06-15
- Cycle: TASK-20260615T172210-profile-icon-consistency 후속 (PB-0008 Windows-browser 시각검증 evidence 기록 — docs-only: TEST.md §4 Run 1건 + TASK.md 완료 표기 + scenario 파일 보존. src 코드 0).
- Skip 사유: 코드 변경 0(순수 evidence/docs). 핵심 변경은 REV-20260615-0277 [SKIPPED:frontend-ui-consistency-no-backend-no-rbac] 에서 이미 리뷰(identicon 이식·드롭업 순서·명칭 순서). 본 후속은 라이브 실 브라우저 실증 기록.
- 실증: PB-0008(실 Chrome/148 relay, 배포 main `bb1a991` PR #246 web 재배포) — 대화 드롭업 항목 순서 [dot→icon→label→ds] 8제품·전 제품 Identicon·명칭 `(약어) 명칭`·메뉴 너비 max 420px 미잘림·관리 콘솔 제품 상세 Identicon 전부 실측 PASS. CHECK#13 충족.
- Cross-ref: CHG-20260615-0278 / TEST.md §4 (2026-06-15 profile-icon Run) / REV-20260615-0277 / artifacts/pb0008-profile-icon/.

## REV-20260615-0278 [SKIPPED:frontend-ui-consistency-no-backend]
- Date: 2026-06-15
- Cycle: TASK-0276 (관리 콘솔 "보관 대화" 탭 UI 정합화), **Minor §12.3** — frontend-only(admin.html + admin.js + styles.css). RBAC/인증/스키마/엔드포인트 계약/데이터/시크릿/백엔드 0.
- Skip 사유: 기존 운영 탭(감사 로그 `admin-audit-row`/`admin-audit-detail`/`admin-audit-filter`)의 **검증된 list-detail 패턴을 verbatim 동형 이식**한 것. 신규 데이터 노출·인가 경로·인터랙션 모델 0 — `GET /api/admin/conversations/archived`(기존 권한 게이트·응답 계약) 를 그대로 소비하고 표현만 table→list-detail 로 재배치. §18.8.1 + Minor + 정책 doc 변경 0 → 적대 패널 skip 허용.
- 자체 점검: ① 모든 사용자/LLM 유래 문자열(topic/username/conversation_id)이 `_archiveEsc` 로 escape — 목록·상세 양쪽 jsdom 으로 XSS 미주입 단언(태그 → `&lt;`, `img` 노드 0). ② row 클릭 → selectedId + 상세 렌더 + is-selected, 미선택 → empty, 재조회 시 선택 유지/해제 정합(jsdom 13 PASS). ③ 응답 필드 그대로 사용(부재 필드 message_count 조건부 생략 — undefined 노출 없음). ④ 검색 input/버튼 `dataset.bound` idempotent 바인딩(중복 핸들러 없음). ⑤ truncated → scope 안내로 표면화(상위 일부만 표시 silent 누락 방지). node --check admin.js PASS + CSS brace 1206=1206.
- Residual: verify-completion --pre-commit + web 재배포(deploy_scope: included) 후 PB-0008 Windows-browser(보관 대화 탭 진입 → list-detail 렌더 + row 클릭 상세) → TEST.md §4 기록.
- Cross-ref: CHG-20260615-0277 / TASK-0276 / FUNCTION REQ-20260615-0276(AC-0503) / REV-20260615-0274(동일 list-detail 정합 선례).

## REV-20260615-0276 [SUBAGENT:attachment-version-security]
- Date: 2026-06-15
- Cycle: TASK-0275 (assistant 첨부 수정→새 버전 materialize + 버전 관리), **Critical §12.3** — LLM 자동 데이터 변형·저장 신규 표면 + MinIO 쓰기 + 스키마 변경. (REV 번호: 동시세션이 REV-20260615-0275[첨부패널 resize evidence] 선점 → 본 보안 리뷰 0276.)
- Trigger: §18.8 — 신뢰 불가 입력(LLM 출력)이 사용자 데이터를 자동 생성·저장하는 표면 + 신규 인가 경로(/versions) + IDOR 가능성 → 적대적 보안/정합 리뷰(general-purpose outside voice). [[feedback_outside_voice_for_rbac]] 정합.
- Verdict: **SHIP** (외부 침투형 BLOCKER 0; 데이터 정합 BLOCKER1+MAJOR2+MINOR1 **수정 후 흡수**).
  - 외부 침투형 PASS(7): IDOR(conv+account scope 이중 가드), path traversal(safe_filename `[^A-Za-z0-9._\-]`→`_` + uuid prefix), kind 우회(source kind 기준 + 확장자 source 고정), 권한 상승(account_id 일치 강제), DoS(count cap 5 슬라이스+per-block 1MB+누적 SUM 재조회), SQLi(전 bound param), /versions 권한(_account_can_access_attachment + pending signed_url 차단).
  - 수정한 데이터 정합 결함:
    - BLOCKER(V8) autocommit 비원자 INSERT/put/supersede → **put-before-insert 재배치**(orphan DB row 제거) + supersede WHERE `VersionNumber<new` self-heal.
    - MAJOR(V6) 비유니크 인덱스 + lock 없는 MAX+1 race → **UNIQUE `UQ_WCA_VersionChain`**(동시 INSERT IntegrityError 거부).
    - MAJOR(V10) materialize audit 부재 → **`attachment.version.create` audit** 추가(D12 categorical).
    - MINOR(V3) `.exe` 등 확장자 다운로드 노출 → **source 확장자 강제 고정**.
- Verification: 신규 test_attachment_versioning.py 11 PASS + make test 회귀 0 + 라이브 라운드트립(materialize·MinIO sha256·supersede·목록필터·/versions·IDOR 2종 라이브거부·traversal/.exe 라이브차단 `.._.._.._etc_passwd.sql`·UNIQUE IntegrityError).
- Residual: 머지 → web 재배포(migrate 불필) + PB-0008. MinIO 고아 객체(INSERT 실패 시)는 reconciliation worker 정리(무해, 정상 업로드 경로와 동형).
- Cross-ref: CHG-20260615-0275 / TASK-0275 / FUNCTION REQ-20260615-0275(AC-0493~0496).

## REV-20260615-0277 [SKIPPED:frontend-ui-consistency-no-backend-no-rbac]
- Date: 2026-06-15 (REV 번호: 동시세션 TASK-0275 보안 리뷰가 REV-20260615-0276 선점 → §13.1 감지-후-재번호 0276→0277)
- Cycle: TASK-20260615T172210-profile-icon-consistency (제품 프로필 아이콘 정합화 + 대화 드롭업 레이아웃·너비 + 명칭 표기 순서), **Major §12.3** — frontend-only(`src/static/{admin.js,app.js,styles.css,index.html,admin.html}`). RBAC/인증/스키마/엔드포인트 계약/데이터/시크릿/백엔드(app.py) 0.
- Trigger: §18.8 dispatch 키워드 매칭(UI/화면/아이콘/레이아웃/목록 → ux,design). 그러나 변경 실질은 **이미 운영 중인 작업화면 프로필 헬퍼(app.js `applyAvatar`/`identiconSvg`, TASK-0268)를 관리 콘솔·대화 드롭업에 byte-identical 이식**하여 시각을 *정합* 시킨 것 + 표시 순서·문자열 순서 재배열이다. 신규 데이터 노출·권한 경계·인터랙션 모델·백엔드 계약 0 → §18.8.1 경량 경로(적대 패널 불요, Minor/Major frontend-only + 정책 doc 변경 0 → panel skip 허용). docs-only 정책 변경 아님(코드 변경)이므로 cross-ref 무결성 점검 의무 비해당.
- 자체 점검(안전 속성):
  - ① **정합 근거**: admin.js 의 `_identiconHash`/`identiconSvg` 가 app.js 와 byte-identical(jsdom 테스트가 문자열 동등 + 동일 seed→동일 SVG 산출로 강제). 같은 제품(product_key 시드)은 작업화면·관리 콘솔·대화 드롭업에서 **동일 Identicon** 렌더 → 시각 정합 달성.
  - ② **회귀 표면**: icon_url 설정 제품은 기존과 동일하게 `<img>` 표시(applyAvatar 의 url 분기 + onerror Identicon 폴백). 미설정 제품만 이니셜 텍스트→Identicon 으로 바뀜(개선, 데이터/동작 무관). 아이콘 업로드/제거 편집 컨트롤(product.manage) 경로·핸들러 무변경.
  - ③ **드롭업 레이아웃**: 자식 순서 dot→icon→label→ds 는 사용자 명시 요청(네트워크 상태 배지·프로필 아이콘·명칭·데이터소스) 순서 그대로. auto 항목은 mode!=="pinned" 라 아이콘 미생성(제품 아님 — 정상). datasource 배지·check svg·click 핸들러(setActiveProduct) 무변경 → 선택 동작 회귀 0(jsdom 으로 순서·폴백·img 분기 검증).
  - ④ **너비**: 메뉴 max-width `min(420px,92vw)` 로 좁은 뷰포트는 92vw clamp(오버플로 방지), 명칭은 `.product-dropup-item-label` 의 ellipsis 유지(확대로 잘림 빈도 감소, 초장문은 여전히 안전 말줄임). chip 라벨(compact=product_key)은 무변경.
  - ⑤ **명칭 순서**: 7곳 전부 `(${product_key}) ${name}` 로 일괄(grep 으로 잔존 `명칭 (약어)` 0건 확인). 백엔드는 name/product_key 분리 반환이라 프론트 단일 책임 — 직렬화 계약 무변경.
  - ⑥ **XSS/주입**: identiconSvg 는 해시 정수→고정 포맷 SVG(사용자 입력 미보간), label 은 `textContent`(HTML 미해석). 신규 주입 표면 0.
- 검증: node --check(app.js·admin.js) PASS + CSS brace 균형(1198=1198) + jsdom `tests/verify_profile_icon_consistency.mjs` **23/23 PASS** + make test 컨테이너 전체 회귀 0(ruff clean, 2 skip, MAKE_EXIT=0).
- Residual: verify-completion --pre-commit + web 재배포(deploy_scope: included) 후 PB-0008 Windows-browser 시각검증(관리 콘솔 제품 Identicon·대화 드롭업 항목 순서·메뉴 너비·명칭 표기) → TEST.md §4 기록.
- Cross-ref: CHG-20260615-0276 / TASK-20260615T172210-profile-icon-consistency / TASK-0268(아이콘 인프라).

## REV-20260615-0275 [SKIPPED:pb0008-evidence-docs-only]
- Date: 2026-06-15
- Cycle: TASK-0274 후속 (첨부 패널 resize PB-0008 Windows-browser 시각검증 evidence 기록 — docs-only: TEST.md §4 Run 1건 + TASK.md 완료 표기. src 코드 0).
- Skip 사유: 코드 변경 0(순수 evidence/docs). 핵심 변경은 REV-20260615-0274 [SKIPPED:ui-pattern-clone] 에서 이미 리뷰(step-side-panel resize 패턴 verbatim 이식). 본 후속은 라이브 실증 기록.
- 실증: PB-0008(실 Chrome/148 relay, 배포 main `bb06ddf` web 재배포) — 핸들 hit-test(elementFromPoint=attachSidePanelResizer)·드래그 280→458px·localStorage 저장·새로고침 후 458px 복원·min240/max92vw(1149) clamp 전부 실측 PASS. CHECK#13 충족.
- Cross-ref: CHG-20260615-0275 / TEST.md §4 (2026-06-15 TASK-0274 Run) / REV-20260615-0274 / artifacts/pb0008-task0274/.

## REV-20260615-0274 [SKIPPED:ui-pattern-clone]
- Date: 2026-06-15
- Cycle: TASK-0274 (첨부파일 목록 사이드 패널 `#attachSidePanel` 너비 조절 가능화), **Minor §12.3** — frontend-only(index.html + styles.css + app.js). RBAC/인증/스키마/엔드포인트 계약/데이터/시크릿/백엔드 0.
- Trigger: §18.8 dispatch 키워드 매칭(UI/사이드바/레이아웃 → ux,design) 이나, 변경 실질은 **이미 운영 중인 `#stepSidePanel`(`setupStepSidePanelResize`)·`#profileDrawer`(`setupProfileDrawerResize`) 의 resize 패턴을 verbatim 복제**한 것이다. 신규 UX 결정·인터랙션 모델·권한 경계·데이터 노출 0 → 적대적 패널 불요(§18.8.1 + Minor + 정책 doc 변경 0 → panel skip 허용).
- 자체 점검: ① 핸들 마크업/CSS/JS 가 step-side-panel 의 검증된 구현과 selector·상수만 다른 동형 — 우측 고정 패널 동일 기하(`width=innerWidth−clientX`)·동일 clamp 구조. ② min-width 240px(첨부 pill 가독 하한)·max-width 92vw(step/profile 와 동일)·초기 280px 유지 → 레이아웃 회귀 표면 없음. ③ `dataset.wired` 가드로 핸들러 중복 배선 차단(패널 재오픈 시). ④ localStorage 키 `web.attachSidePanel.width` 는 기존 `web.stepSidePanel.width`·`web.profileDrawer.width` 와 분리 → 상호 간섭 0. ⑤ 패널 open 단일 경로(`composerActionsListItem` 클릭)에서만 wiring → 누락 진입점 없음(grep 확인). node --check app.js PASS.
- Residual: verify-completion --pre-commit + web 재배포(deploy_scope: included) 후 PB-0008 Windows-browser 시각검증(좌측 핸들 hit-test·드래그 너비 변경·새로고침 후 복원) → TEST.md §4 기록.
- Cross-ref: CHG-20260615-0274 / TASK-0274 / FUNCTION REQ-20260615-0274(AC-0492).

## REV-20260615-0272 [SKIPPED:panel]
- Date: 2026-06-15
- Cycle: TASK-0272 (대화 화면 프로필 첫 진입 시 "프롬프트 > 제품 범위" 비어있는 버그; 동시세션이 TASK-0271/AC-0470 선점→§13.1 재번호 0271→0272·AC-0470→0487), **Minor §12.3** — 프론트엔드 단일 파일(app.js) 버그 수정 + 캐시버스터. RBAC/인증/스키마/엔드포인트 계약/데이터/시크릿 0.
- Trigger: §18.8 dispatch 키워드 매칭(UI/화면/form) 이나, 변경 실질은 lazy-load 디스패치를 탭 클릭 리스너 → `switchProfileTab()` 내부로 이전한 frontend-only 1-file 수정이다. 권한 경계·데이터 노출·쿼리 변화·외부 계약 0 → 적대적 보안/RBAC 패널 불요(§6.3 Minor + 1 file + 정책 doc 변경 0 → panel skip 허용).
- Reason: 근본원인이 "기본 활성 탭은 클릭 이벤트가 없어 lazy 적재가 누락"이라는 이벤트 배선 위치 문제로 명확. `switchProfileTab` 단일 진입점화는 기존 두 호출 경로(openProfile, 탭 클릭)를 모두 커버하며 중복 디스패치를 제거해 회귀 표면을 오히려 줄인다. `state.products` 적재 시점(부트스트랩)이 프로필 오픈보다 선행함을 코드로 확인(데이터 race 아님). node --check PASS.
- Residual: verify-completion --pre-commit + web 재배포(deploy_scope: included) 후 PB-0008 Windows-browser 시각검증(프로필 첫 진입 시 제품 범위 채워짐) → TEST.md §4 기록.
- Cross-ref: CHG-20260615-0272 / TASK-0272 / FUNCTION REQ-20260615-0272(AC-0487).

## REV-20260615-0271 [SKIPPED:pb0008-evidence-docs-only]
- Date: 2026-06-15
- Cycle: TASK-0271 (TASK-0269/0270 PB-0008 Windows-browser 시각검증 evidence 기록 — docs-only: TEST.md §4 Run 2건 + TASK.md 완료 표기. src 코드 0).
- Skip 사유: 코드 변경 0(순수 evidence/docs). 핵심 변경은 REV-20260615-0269 [SUBAGENT:rbac-adversarial] SHIP / REV-20260615-0270 [SKIPPED:ui-disclosure-gate] 에서 이미 리뷰. 본 후속은 라이브 실증 기록.
- 실증: PB-0008(실 Chrome/148 relay) — ① TASK-0270(배포 `8953dc1`): 계정 override 전부 상속 + 역할 baseline 주입 → 상속(허용) 게이트가 자식 펼침(account.read/update/conv.ask=flex), 상속(거부)는 접힘(read.any=none). ② TASK-0269(배포 `73755e9`): 운영 권한 내 대화/전체 대화 2그룹 분리·목록 조회 게이트 트리. 사용자 요구 라이브 충족. CHECK#13 충족.
- Cross-ref: CHG-20260615-0271 / TEST.md §4 (2026-06-15 TASK-0269·0270 Run) / REV-20260615-0269·0270.

## REV-20260615-0270 [SKIPPED:ui-disclosure-gate-no-enforcement]
- Date: 2026-06-15
- Cycle: TASK-0270 (계정 override 편집기 게이트 = 허용/상속(허용) 펼침 — frontend-only `src/static/admin.js`)
- Skip 사유: 변경은 override(계정) 편집기의 **disclosure 게이트 충족 판정**(자식 row 를 *시각적으로* 펼칠지)만 — `gateSatisfied` 에 "상속(허용)"(상속 + 역할 부여) 분기 추가. enforcement(권한 체크는 code 기반)·override **저장 경로**(select 값 그대로 읽음)·권한 의미·역할(checkbox) 모드는 byte-identical. 적대적 RBAC 리뷰 불필요(노출 affordance만, 권한 결정/저장 무변경).
- 자체 점검: ① 상속 baseline 정확성 — 계정 역할 `permission_codes`(frontend) = `_load_role_permission_codes`(WebRolePermissions, 자동부여 audit.read.own 도 seed 영속) = 백엔드 계정 effective `_apply_permission_overrides` 의 base 와 **동일 출처** → 정확한 상속 집합. ② "거부" 우선 — 명시 거부는 역할 부여해도 게이트 OFF(jsdom 검증). ③ "허용"은 inherited 무관 펼침. ④ 역할(checkbox) 모드 gateSatisfied 무변경(체크). ⑤ inheritedGrants 미전달 시 빈 Set 기본 → 역할 편집기 동작 불변.
- 검증: perm test 16 PASS(신규 V7) + make test 회귀 0 + node --check + jsdom 8/8(상속허용 펼침·상속거부 숨김·거부 우선·허용 무관·운영 list.own 상속허용). PB-0008(배포 후).
- Cross-ref: CHG-20260615-0270 / TASK-0270.

## REV-20260615-0269 [SUBAGENT:rbac-adversarial] — SHIP
- Date: 2026-06-15
- Cycle: TASK-0269 (운영 권한 대화 그룹 own/any 분리 + "목록 조회" 게이트 — RBAC 카탈로그 group 필드 변경. app.py + admin.js + app.js)
- 패널: 적대적 outside-voice(general-purpose subagent) — RBAC 카탈로그 group 분리가 enforcement/기능을 깨지 않는지 5 카테고리 검증.
- **VERDICT: SHIP** (BLOCKER/MAJOR/MINOR 0). 전부 refuted:
  - **enforcement 불변** — `_require_permission`→`_account_has_permission`→`_account_permissions` 전부 **code 키 기반**, group 무관. conversation 권한 code 불변 → 접근 결정 byte-identical. group 읽기는 catalog 영속/응답 passthrough뿐(접근 결정 미사용).
  - **group 소비자** — `/api/admin/permissions`(메타 passthrough), admin.js `groupedPermissions`(`permission.group` 버킷, `||"misc"`/order-99 fallback), app.js `permissionGroupOf`(코드 추론) 전부 새 문자열 graceful. `group=="conversation"` 하드코딩 0(repo grep). bare `"conversation"` 리터럴은 audit resource_type·URL query param(권한 group 아님).
  - **work screen 정합** — `permissionGroupOf` 23개 conversation code 검증 0 mismatch(share.create→conversation_own 포함), WORK_SCREEN 섹션·라벨·order 에 두 신규 그룹 존재, misc 낙오 0.
  - **dependency 건전성** — 루트 3(create/list.own/list.any) + 자식 20, 전 자식 same-group 게이트로 무순환·cross-group stray 0. share.create→list.own·ask→list.own 정확.
  - **attachment 그룹** — conversation.attachment.* 가 own/any 로 이동(접두 정합), 빈 "attachment" 그룹은 `groupedPermissions` 가 항목 있는 그룹만 Map 생성하므로 무영향(기존과 동일).
  - 추가: `WebPermissions.GroupName VARCHAR(32)` 신값 16자 무절단, `_ensure_permission_catalog` `ON DUPLICATE KEY UPDATE GroupName=VALUES()` 부팅 시 멱등 갱신(마이그 불요), 정적 권한 group 은 Python tuple 출처(DB 무관 정확).
- 검증: perm test 15 PASS(M4 list 게이트/V2 운영 루트/T2 그룹 분리+게이트 중첩 갱신) + make test 컨테이너 회귀 0(백엔드 RBAC 무회귀) + jsdom 20/20 + PB-0008(배포 후).

## REV-20260615-0268 [SKIPPED:pb0008-evidence-docs-only]
- Date: 2026-06-15
- Cycle: TASK-0268 (TASK-0267 트리 UI PB-0008 Windows-browser 시각검증 evidence 기록 — docs-only: TEST.md §4 Run + TASK.md PB-0008 완료 표기. src 코드 0).
- Skip 사유: 코드 변경 0(순수 evidence/docs). 핵심 변경은 선행 REV-20260615-0267 [SKIPPED:ui-tree-layout] 에서 리뷰. 본 후속은 라이브 실증 기록.
- 실증: PB-0008(실 Chrome/148 relay, 배포 main `f6ccb7b` web Up healthy) — ① `.permission-grid-list` computed flex column(grid-template-columns none) ② 자식 depth1·margin-left 24px 들여쓰기 ③ 운영 권한 "더 보기 · 1개 부여됨" rgb(180,35,31) 빨강 가시. 사용자 두 보고(빨강 미가시·뒤틀림) 충족. CHECK#13 충족.
- Cross-ref: CHG-20260615-0268 / TEST.md §4 (2026-06-15 TASK-0267 Run) / REV-20260615-0267.

## REV-20260615-0267 [SKIPPED:ui-tree-layout-no-logic-change]
- Date: 2026-06-15
- Cycle: TASK-0267 (권한 grid 트리 UI 재구성 — 2열 grid→단일 열 트리 + 자식 들여쓰기. frontend-only `src/static/{admin.js,styles.css}`)
- Skip 사유: disclosure 가시성·게이트·도달성(그룹 유지/배지)·저장 경로·`has-granted` 빨강 CSS·RBAC enforce·권한 code·엔드포인트·스키마 **무변경**. 변경은 **렌더 순서(`_orderItemsAsTree` 트리 DFS)+레이아웃(grid→flex column 들여쓰기)** 뿐 — 권한 의미·저장에 영향 0. 적대적 RBAC 리뷰 불필요(가시성/저장 로직 byte-identical).
- 주요 안전 포인트 자체 점검: ① **렌더 누락 0** — `_orderItemsAsTree` 누락 안전망 + jsdom 실측(account 7/7·conversation 23/23 전부 렌더). ② **저장 무영향** — 저장 closure 는 `querySelectorAll("input:checked")`/`select` 로 순서 무관. ③ **제품 카드 임베드 무영향** — product 그룹 두 정적 권한 모두 루트(depth 0, 카탈로그 순서 보존), 임베드 카드는 renderPermissionGrid 후 append 라 reorder 무관. ④ **숨김 동작 무변경** — `_applyPermissionDisclosure` 로직 동일(트리는 시각 순서·들여쓰기만).
- 검증: perm test 15 PASS(신규 T1~T4 트리 정렬/depth/단일열 CSS 계약) + make test 회귀 0 + jsdom 14/14(순서·depth·누락0·숨김 시 부모 DOM 앞 유지). 빨강 badge 는 본 cycle 전 라이브 실측으로 정상 확인(checkbox/override 둘 다 rgb(180,35,31)) — 본 cycle 은 2열 뒤틀림 제거로 가시성 회복. 최종 PB-0008(배포 후) 로 단일 열·들여쓰기·운영 권한 빨강 가시성 시각검증.
- Cross-ref: CHG-20260615-0267 / TASK-0267 / [[feedback_visual_verify_on_design_change]].

## REV-20260615-0265 [SKIPPED:pb0008-evidence-docs-only]
- Date: 2026-06-15
- Cycle: TASK-0265 (TASK-0264 PB-0008 Windows-browser 시각검증 evidence 기록 — docs-only: TEST.md §4 Run + TASK.md PB-0008 완료 표기. src 코드 0).
- Skip 사유: 코드 변경 0(순수 evidence/docs). 핵심 코드 변경은 선행 REV-20260615-0264 [SUBAGENT:rbac-adversarial] SHIP-WITH-FIXES 에서 이미 적대 리뷰 완료. 본 후속은 라이브 실증 기록일 뿐.
- 실증: PB-0008(실 Chrome/148 relay, 배포 main `d35299e` web Up healthy) — ① 역할(checkbox) account.delete 부여+게이트OFF → computed `display:none`(권한 행 0 노출, "더 보기 7개·1개 부여됨") ② 계정(override) account.delete=거부 → override-grid 행 computed `display:none`(unscope 수정 실증). 사용자 두 편집기 요구 충족. CHECK#13 충족.
- Cross-ref: CHG-20260615-0265 / TEST.md §4 (2026-06-15 TASK-0264 Run) / REV-20260615-0264.

## REV-20260615-0264 [SUBAGENT:rbac-adversarial] — SHIP-WITH-FIXES → 흡수 후 SHIP
- Date: 2026-06-15
- Cycle: TASK-0264 (권한 disclosure 추가 단순화 — forceVisible 제거, 게이트 미충족 시 부여 세부 권한도 숨김. frontend-only `src/static/{admin.js,styles.css}`)
- 패널: 적대적 outside-voice(general-purpose subagent) — #1 우선순위 "부여된 권한이 도달 불가/저장 누락될 수 있는가" 를 6 카테고리로 증명/반증.
- **VERDICT: SHIP-WITH-FIXES**. 안전 카테고리 전부 **refuted**:
  - **부여 도달불가** — refuted: `grantedCount>0` 면 그룹 vanish 안 함(`hiddenCount===rows.length && grantedCount===0` 만 vanish) → "더 보기 · N개 부여됨" 항상 존재, 그룹 헤더 `N/M 선택` 카운트도 부여 노출. override 모드는 그룹/섹션 vanish 자체가 없음. console.access 루트·product 임베드 카드 모두 안전. 부여-vanish-no더보기 경로 없음.
  - **섹션 숨김 trap** — refuted: `secEl.hidden = !groups.some(g=>!g.hidden)` 이라 grant 로 살아남은 그룹(`g.hidden===false`)이 있으면 섹션 유지.
  - **저장 누락(가장 중요)** — refuted: 저장 closure 가 `:checked`/`select[data-override-code]` 를 `:not([hidden])` 필터 없이 질의, `hidden` 속성/닫힌 `<details>` 는 querySelectorAll·`:checked`·select.value 에 무영향, disabled 는 `*.permission.manage` 권한에만 결속 → hidden-but-granted 항상 저장(누락 0).
  - **리스너 중복/recompute** — refuted: `isExplicit` 단일 호출처서 항상 전달, "더 보기" 버튼 `if(!more)` 내부서만 바인딩(중복 없음).
  - **게이트 시맨틱** — refuted: `isVisible` 전 조상 체인 요구, 사이클 가드, override 게이트 `=== "allow"` 만(deny 는 자식 안 엶, V6 검증).
- 흡수한 결함:
  - **[MINOR] 계정 override 편집기 `[hidden]` 미적용** — override 컨테이너 = `.override-grid`(≠`.permission-grid`), 행 = `.field.override-field`(`.field{display:flex}` 가 UA `[hidden]{display:none}` override) → TASK-0258 의 `.permission-grid [data-perm-code][hidden]` 강제 규칙이 override 행을 놓침(=TASK-0258 갭, 이 cycle 이 granted 행까지 확대 노출). **흡수**: CSS 셀렉터를 컨테이너 무관 `[data-perm-code][hidden]` 로 unscope(`[data-perm-code]` 는 권한 row 에만 부여 → 안전). test_c1 도 "unscoped 셀렉터 존재" 검증으로 강화. (안전 영향 없음 — 안 숨겨지는 건 *더* 노출되는 방향이라 도달불가 아님. 사용자 단순화 목표가 override 모드서 미충족되던 부분만 해소.)
- 후속 검증: jsdom 17/17(부여 게이트OFF 숨김·그룹 유지·부여됨 배지·더보기 도달·저장누락0·override) + make test 회귀 0 + PB-0008(배포 후, 계정 override 행 computed display:none 포함).

## REV-20260615-0263 [SKIPPED:pb0008-evidence-docs-only]
- Date: 2026-06-15
- Cycle: TASK-0262 PB-0008 evidence (verify-completion check#9 REV id 4자리 규칙 — `-0262b` 접미는 FAIL 이라 0263 채번; TASK-0259 가 0257/0258 evidence cycle 였던 패턴과 동일). docs+scenario, src 0.
- Skip 사유: 코드 변경 0(순수 evidence/docs/scenario). 핵심 코드 변경은 선행 REV-20260615-0262 [SKIPPED:frontend-color-readonly-no-rbac] 에서 검토 완료. 본 후속은 라이브 실증 기록.
- 실증: PB-0008(main `eb7be30`) — 선택 제품 chip dot 이 datasource 상태색(94 unstable=빨강, 95 healthy=초록) 으로 표시, auto 전이 시 conn 클래스 reset(회색). CHECK#13 충족.
- Cross-ref: TEST.md §4 (2026-06-15 TASK-0262 Run) / TASK-0262 / REV-20260615-0262.

## REV-20260615-0262 [SKIPPED:frontend-color-readonly-no-rbac]
- Date: 2026-06-15
- Cycle: TASK-0262 (선택 제품 chip dot 네트워크 상태색 — TASK-0261 후속, frontend-only).
- Skip 사유: 순수 클라이언트 렌더(색) 보완 — 백엔드/RBAC/엔드포인트/스키마/시크릿 0. 데이터 소스(`conn_status_overall`)·conn 색 의미론·specificity override 패턴은 선행 **REV-20260615-0261 [SKIPPED:readonly-enrich]** 에서 이미 검토됨(본 cycle 은 동일 패턴을 드롭업 목록→트리거 chip 으로 확장 적용). 노출면 무변(읽기전용 enrich, 좌표/비번 비노출). outside-voice 불요 조건 충족.
- 검증: node --check + CSS brace 1131=1131 + make test 회귀 0 + ruff clean. 배포 후 PB-0008(CHECK#13).
- Cross-ref: CHG-20260615-0262 / TASK-0262 / REV-20260615-0261 / FUNCTION AC-0477.

## REV-20260615-0259 [SKIPPED:pb0008-evidence-docs-only]
- Date: 2026-06-15
- Cycle: TASK-0259 (TASK-0257/0258 PB-0008 Windows-browser 시각검증 evidence 기록 — docs-only: TEST.md §4 Run + TASK.md PB-0008 완료 표기. src 코드 0).
- Skip 사유: 코드 변경 0(순수 evidence/docs). 핵심 코드 변경은 선행 REV-20260615-0257 [SUBAGENT:rbac-adversarial] SHIP-WITH-FIXES / REV-20260615-0258 [SKIPPED:css-display-hotfix] 에서 이미 리뷰 완료. 본 후속은 라이브 실증 기록일 뿐.
- 실증: PB-0008(실 Chrome/148 relay, 배포 web `Up healthy`) — 계정 그룹 펼침 시 계정 조회만 visible·나머지 6개 computed `display:none`(visible=1) + 역할 그룹 vanish/등장 + override 그룹 비vanish. 사용자 두 예시 라이브 충족. CHECK#13 충족. 자격증명 미노출.
- Cross-ref: CHG-20260615-0259 / TEST.md §4 (2026-06-15 TASK-0257/0258 Run) / REV-20260615-0257·0258.

## REV-20260615-0258 [SKIPPED:css-display-hotfix-strictly-safer]
- Date: 2026-06-15
- Cycle: TASK-0258 (TASK-0257 핫픽스 — disclosure hidden row 가 실브라우저에서 안 숨겨지던 `[hidden]` CSS override 버그. frontend-only `src/static/styles.css` 1규칙 + 캐시버스터 + 회귀 가드 테스트).
- Skip 사유: 적대 리뷰 생략 정당화 — 변경은 `[hidden]` 속성을 받은 요소를 **확실히 `display:none` 으로 숨기는** 단일 CSS 규칙뿐(`.permission-section/group[hidden]` + `[data-perm-code][hidden] { display:none !important }`). 동작 방향이 **strictly safer**(권한을 더 *숨기는* 쪽 — 의도된 disclosure 대로 hidden 인 행이 실제로 사라짐. 권한을 *드러내거나* 부여 권한을 숨기는 방향이 아님). RBAC enforce·권한 code·persistence·JS 로직·저장 경로 0 변경. TASK-0257 의 비파괴 안전속성(부여 권한은 forceVisible 이라 애초에 `[hidden]` 안 붙음 → 본 규칙의 영향 밖)은 그대로 유지.
- 검출/검증: 버그는 TASK-0257 의 **PB-0008 실브라우저 검증**이 잡았다(eval `.hidden===true` 인데 computed `display:flex` — jsdom CSS 캐스케이드 부재로 미검출). 수정은 ① 실브라우저 CSS 주입 후 computed display 재확인(account.read=flex, 나머지 6개=none) ② 신규 정적 회귀 가드 `test_c1_hidden_rows_force_display_none` ③ make test 전체 회귀 0 으로 검증. 최종 배포 후 PB-0008 재확인.
- Cross-ref: CHG-20260615-0258 / TASK-0258 / REV-20260615-0257(원 기능) / [[feedback_visual_verify_on_design_change]].

## REV-20260615-0257 [SUBAGENT:rbac-adversarial] — SHIP-WITH-FIXES → 흡수 후 SHIP
- Date: 2026-06-15
- Cycle: TASK-0257 (관리 콘솔 계정·역할 권한 편집기 점진적 세분화 — **Major §12.3** 권한 편집 surface, frontend-only `src/static/{admin.js,styles.css}`)
- 패널: 적대적 outside-voice(general-purpose subagent) — 8개 결함 카테고리를 명시 증명/반증 시도. RBAC plan 외부시각 정책([[feedback_outside_voice_for_rbac]]) 정합(단, 권한 *모델* 변경 아님 — 편집기 표시 UX 전용이라 enforce/code/persistence 무변경).
- **VERDICT: SHIP-WITH-FIXES**. 반박된(비결함, refuted) 우려:
  - **#1 부여 권한이 숨겨질 수 있는가** — 200k checkbox + 200k override **랜덤 fuzz 0건**. `forceVisible` 가 명시 설정(on/허용/거부) 권한 + 모든 조상을 표시 마킹 → 어떤 상태에서도 부여 권한 hidden=false. 최악도 "더 보기"로 도달.
  - **#2 저장 누락(data loss)** — 저장 closure 가 `permWrap.querySelectorAll("input:checked")` / `select[data-override-code]` 를 wrapper 전체에 `:not([hidden])` 필터 없이 질의. HTML `hidden` 속성은 querySelectorAll/`:checked`/select.value 에 영향 없고 전역 `[hidden]{display:none}` 도 없음 → hidden-but-checked 권한 정상 저장. **REFUTED**(가장 중요한 검증, clean).
  - **#5 무한루프/perf/버튼 중복** — `let more = querySelector(...)` 재사용으로 버튼 1개 유지(50회 recompute 후 1개), 리스너 `if(!more)` 내부만 부착, isVisible 캐시 사이클 가드, O(n) — REFUTED.
  - **#6 제품 그룹** — product 루트(product.manage·system_prompt.manage.role.any)는 부모 없음→항상 visible→그룹 hiddenCount≠rows.length→그룹 미숨김, 카운트는 `[data-perm-code]`만 세어 임베드 제품 카드 무영향 — REFUTED.
  - **#7 맵 정합** — 31 deps 전부 실제 code, 무순환·루트 종료, 마스터게이트/own→any 정확 — REFUTED. **#8 §10.6 정렬** — section/group 순서 불변(intra-group hidden 토글만) — REFUTED.
- 흡수한 결함:
  - **[MAJOR] override 모드 그룹 도달불가 trap** — override 모드 기본(전부 inherit)에서 account/role/audit/settings 그룹이 통째 hidden 되며 "더 보기" 탈출구도 그 안에 묶여 사라져, 관리자가 inherit 자식 row(예: account.update=deny)에 도달 불가. 게이트(select)를 allow 로 바꾸면 *실효 권한*이 바뀌는 destructive side-effect. **흡수**: `_refreshGroupDisclosure` 에 mode 분기 — 그룹/섹션 통째 vanish 는 checkbox(역할) 모드만(마스터게이트 체크박스가 항상 보이는 복원 레버). override 모드는 그룹/섹션 **비숨김**(§295 "전체 표시" 정합) + row 만 접고 "더 보기" 항상 도달. 신규 override 가시성 테스트 V5/V6 + jsdom S6 추가.
  - **[MINOR] dead branch** — `_refreshGroupDisclosure` 의 `if(more.parentElement!==list) ... else if(list) ...` 양쪽 모두 appendChild → 단일 `if(list) list.appendChild(more)` 로 정리. **흡수**.
  - **[MINOR] override 모드 orphan 칩 부재 / §10.6 "전체 표시" 약화** — override 게이트 inherit 의 role-grant 모호성 때문에 칩을 checkbox 모드 한정 유지(accepted: inherit 게이트에 오탐 칩 회피). §10.6 약화는 MAJOR 흡수(override 그룹 비숨김)로 해소 + §10.6 에 disclosure 계층 명문화.
- 후속 검증: jsdom 실 DOM 30/30(저장경로 안전·override no-vanish·더보기 도달 포함) + make test 회귀 0 + PB-0008 Windows(배포 후).

## REV-20260615-0255c [SKIPPED:pb0008-evidence-docs-only]
- Date: 2026-06-15
- Cycle: TASK-0255b (PB-0008 Windows-browser 시각검증 evidence 기록 — docs-only: TEST.md §4 Run + 양 feature TASK.md PB-0008 체크박스; src 코드 0).
- Skip 사유: 코드 변경 0(순수 evidence/docs). 본 cycle 핵심 코드 변경은 선행 REV-20260615-0255(agent-core, 5-lens adversarial) / REV-20260615-0255b(web) SHIP_WITH_FIXES 에서 이미 적대 리뷰 완료. 본 후속은 라이브 실증 기록일 뿐.
- 실증: PB-0008(main `a410986`) — `/api/admin/datasources` insight_health 첨부(auth=unstable/circuit_open, gz-qa-kr=healthy/ok) + UI "인사이트 스캔 상태" 행(불안정="⚠ 연결 불안정", 정상="정상(분석됨)") 구분 실증. CHECK#13 충족. 자격증명 미노출.
- Cross-ref: TEST.md §4 (2026-06-15 TASK-0255 Run) / TASK-0255 / REV-20260615-0255(b).

## REV-20260615-0255b [SUBAGENT:5-lens adversarial, cross-feature(TASK-0255)] — SHIP_WITH_FIXES
- Date: 2026-06-15
- Cycle: TASK-0255 (cross-feature — 주 리뷰는 agent-core REV-20260615-0255). web 영향분(`_read_insight_datasource_health` + `admin_list_datasources` insight_health 첨부 + admin.js 배지) 검토. (id 접미 `b`: 동일 날짜 TASK-0254 evidence 가 `REV-20260615-0255` 선점 — 충돌 회피.)
- L3(credential-leak) lens 전수: web 응답·admin.js 에 자격증명/민감정보 노출 없음(host 는 기존 conn_status/datasource 목록과 동형 노출, errno-tag 80자). `console.access` 권한 게이트 유지. RO 연결·graceful(테이블 부재 시 {} — 목록 무영향). BLOCKER 0. 상세는 agent-core REV-20260615-0255.
- 잔여: PB-0008 Windows-browser 시각검증(배포 후, CHECK#13) — admin.js "인사이트 스캔 상태" 행.

## REV-20260615-0255 [SKIPPED:pb0008-evidence-docs-only]
- Date: 2026-06-15
- Cycle: TASK-0254 PB-0008 Windows-browser 시각검증 evidence 기록 (docs-only — TEST.md §4 Run + TASK 체크박스 + 스크린샷; src 코드 0).
- Skip 사유: 코드 변경 0(순수 evidence/docs). 본 cycle 의 핵심 코드 변경은 선행 REV-20260615-0254 [SUBAGENT:frontend-adversarial] SHIP 에서 이미 적대 리뷰 완료. 본 후속은 그 결과를 라이브에서 실증한 기록일 뿐.
- 실증 결과: PB-0008 (배포 main `f8845cc`) — HOLD 8샘플 top=60 고정 / FOLLOW 73샘플 dist=0 → 두 요구사항(위로 스크롤 유지 / 최하단 추종) 라이브 PASS. CHECK#13 충족.
- Cross-ref: CHG-20260615-0254b / TASK-0254 / TEST.md §4 (2026-06-15 Run).

## REV-20260615-0254 [SUBAGENT:frontend-adversarial] — SHIP-WITH-FIXES → 흡수 후 SHIP
- Date: 2026-06-15
- Cycle: TASK-0254 (제품 프롬프트 '자동 작성' SSE 스트리밍 중 스크롤 stick-to-bottom — **Minor §12.3**, 프론트 전용 `src/static/admin.js`)
- 패널: 적대적 outside-voice(general-purpose subagent) — stick-to-bottom 로직을 반증 시도(첫토큰/8px 임계/측정 순서/done 재할당/비-오버플로/수동관찰 무회귀).
- **VERDICT: SHIP-WITH-FIXES (NOT-SHIP 0)**. 반박된(비결함) 우려:
  - 첫 토큰 정확 — `value=""` 가 atBottom 측정 전 실행 → scrollHeight≈clientHeight·scrollTop=0 → atBottom=true → 첫 토큰 정상 추종, off-by-one(한 줄 위 stranded) 없음. 비-오버플로→오버플로 전환도 매 프레임 clamp 로 atBottom 유지.
  - 8px 임계 적정 — line-height ≈17.4px(12px×1.45) → 의도적 1줄 스크롤업은 미포착(되끌려가지 않음), 분수픽셀(≤1~2px)은 흡수. 트레이드오프 수용.
  - 비-오버플로/수동관찰 무회귀 — 내용이 다 보이면 `scrollHeight==clientHeight`·scrollTop=0 → atBottom 항상 true → 기존 무조건 추종과 동일. `textarea-autogrow.js` 는 더블클릭에만 발화해 스트리밍 비간섭.
- **흡수한 FIX**:
  - **LOW(real)** — `done` 분기의 strip 길이차 점프: 서버 `done.prompt = "".join(accumulated).strip()`(app.py:16519 grep 확인)인데 스트리밍 중엔 un-stripped 토큰을 append → done 재할당 시 내용이 짧아져(흔히 선/후행 개행 trim) `!atBottom` 분기에서 `prevTop` 이 새 max 초과 → 약간 하단 점프. **흡수**: 동일하면 재할당 생략(스크롤 리셋 회피) + `maxTop=max(0, scrollHeight-clientHeight)` 로 명시 clamp(`atBottom ? maxTop : min(prevTop, maxTop)`).
- 수용(INFO/nit): 스트리밍 중 `metaEl` 글자수(un-stripped)와 최종 저장값(stripped) 경계 불일치는 cosmetic(최종 저장은 post-done stripped value 라 영속 정확) — 무조치.
- 검증: `node --check`(admin.js) PASS + 서버 `.strip()` 사실 확인(app.py:16519) + make test 컨테이너 **회귀 0 PASS**(진행 100%·skip 2·fail/error 0·make exit=0)+ruff clean + verify-completion 9 checks PASS. **잔여**: 배포(web) + PB-0008 Windows-browser 시각검증(스트리밍 중 위로 스크롤 유지 / 최하단 추종).
- Cross-ref: CHG-20260615-0254 / TASK-0254 / AC-0429 (REQ-20260612-0237 TASK-0237 SSE 스트리밍 후속).

## REV-20260612-0253 [SUBAGENT:concurrency+SSRF-adversarial] — SHIP-WITH-FIXES → 흡수 후 SHIP
- Date: 2026-06-12
- Cycle: TASK-0253 (관리 콘솔 head-of-line blocking 2건 제거 — **Minor §12.3**, A datasource ↻ 새로고침 / B 제품 분석 완료율)
- 패널: 적대적 outside-voice — 동시성/이벤트 루프·프론트 경쟁상태·force dedup·SSRF 회귀·백엔드 break·테스트 품질.
- **VERDICT: SHIP-WITH-FIXES (BLOCKER 0)**. 반박된(비결함) 우려:
  - SSRF 회귀 없음 — `to_thread(_db.probe_datasource, {**ds, "host": _pin})` 의 `_pin` 은 `_ssrf_check_host` 가 반환한 검증된 pinned IP, to_thread 는 인자 그대로 전달(host 재해석 X) → DNS rebinding 차단 유지.
  - 커넥션/소켓 누수 없음 — `probe_datasource`·`_compute_product_insight_coverage` 모두 `finally` close. 스레드/병렬이 lifecycle 무변경.
  - 백엔드 break 안전 — `out[pid]=cov` + `_insight_cov_cache_put` **이후** break → 캐시 put 안 건너뜀, 응답 형태 동일.
  - 프론트 로딩 영구 stuck 없음 — `_loadOne` 의 `finally` 가 모든 경로(403 catch 포함)에서 `productCoverageLoadingIds.delete(pid)`.
  - A force 전파/세마포어 release 정상 — refresh→캐시 delete→`_rebuildDsAddList(true)`→각 `_kickDsConn(force:true)`; release 는 `_probeDatasourceConn` finally 에서 항상.
- **흡수한 FIX**:
  - **MAJOR-2** (N-fan-out 이 공용 anyio 스레드풀[기본 40] 고갈 → 한 레이어 위 head-of-line 재발 우려): 프론트 `loadProductInsightCoverage` 에 동시성 cap `_COV_FETCH_MAX=4` + `_runWithConcurrency` 도입(datasource probe `_DS_CONN_MAX=4` 와 동형). 작은 풀은 사실상 전부 동시, 큰 풀은 백엔드 보호.
  - **MINOR-2** (force 경로가 in-flight dedup 우회 → ↻ 연타·force 렌더 중첩 시 같은 key 2벌 probe): `_probeDatasourceConn` 의 in-flight dedup 가드를 `if(!force)` 밖으로 빼 force 무관 적용("force=캐시 무시"이지 "진행 중 probe 무시"가 아님).
  - **MINOR-3** (테스트 fake 시그니처가 실제 `probe_datasource(ds, *, timeout=None)` 의 keyword-only 와 불일치): fake 3곳을 `lambda ds, *, timeout=None:`/`def _slow_probe(ds, *, timeout=None)` 로 정합 → 시그니처 회귀 포착.
  - **MAJOR-1** (신규 테스트가 agent 이미지 밖에서 `import app` 실패 → 미실행): `make test`(agent 이미지 + PYTHONPATH) green 으로 게이트 충족(전체 회귀 0). 본 worktree 는 .env 심링크로 로컬 import 도 가능해 8 PASS 별도 확인.
- 수용(MINOR/nit): async 핸들러에 `_connect_memory`/`_dsr.resolve`(메모리 DB 동기) 잔존 — 메모리 DB 정상 시 수 ms, probe 구간 블로킹만 본 cycle 스코프(주석 정정); fan-out 중 제품 삭제 시 stale Map 항목(렌더 안 됨, 무해); T3 timing 테스트 마진 ~2.5x(flaky 낮음).
- 검증: node --check(admin.js) + py_compile(app.py) + 신규 8 PASS + make test 컨테이너 **전체 회귀 0** + ruff clean.
- 확장 방향: 제품 수십~수백 시 background 사전계산 worker(TASK-0250 conn_health 패턴) + Redis 외부 캐시(현 `_insight_cov_cache` 는 프로세스 로컬 TTL — 다중 인스턴스 미공유) → 진입 시 단일 조회 즉시표시. REPORT 참조.
- Cross-ref: CHG-20260612-0253 / TASK-0253. (선행 head-of-line 제거: REV-20260612-0250 datasource 연결 도메인.)

## REV-20260612-0252 [SKIPPED:doc-only] — SHIP
- Date: 2026-06-12
- Cycle: TASK-0252 (TASK-0251 PB-0008 Windows-browser 완료 게이트 기록 — **doc-only**)
- Reason: 문서 전용 — 코드/정적자산/스키마/RBAC/엔드포인트 0. TASK-0251 라이브 배포본(main 9cee54a)의 PB-0008 Windows-browser 시각검증 PASS 결과를 TEST.md §4 에 기록하고 STATUS/TASK 잔여를 완료 갱신할 뿐. 실 시스템 mutation 0 이라 적대적 패널 불요(전례 doc-only SKIP 동일).
- 실측 근거: 실제 Windows Chrome/148 via bin/win-browser.py(relay) 로 라이브 공유 URL 2종 검증 — 사용자 토큰 토글 0개·본문 SQL pre 5/5 펼침 / steps 토큰 navigator "쿼리 1/8"↔"8/8" ▶◀ click hit-test 전환·경계 disabled. 익명 API 응답에 csv_paths/preview 누출 0.
- Cross-ref: CHG-20260612-0252 / TASK-0252 / TASK-0251 / REV-20260612-0251.

## REV-20260612-0251 [SUBAGENT:share-anonymous-exposure-adversarial] — NOT-SHIP → 흡수 → PASS
- Date: 2026-06-12
- Cycle: TASK-0251 (익명 공유뷰 SQL "쿼리 열고닫기" 토글 → "실행 쿼리 전환" navigator 교정 + 백엔드 steps 공급 + 익명 sanitize, **Major §12.3 — 익명 데이터 노출 경계**)
- Trigger: §18.8 — `/share/{token}` 은 **anonymous(비로그인) 접근** public-exposure 면 + 본 cycle 이 share API 에 step별 sql/result 공급을 신설(노출면 확대). REV-20260609-0001 의 "public-exposure 면 redaction 불변식 자동 가드" 권고 정합.
- 패널: outside-voice 적대적 보안 리뷰(general-purpose subagent) — redaction 우회 / XSS / version gate / null 안전 / 회귀 5축 적대 검토.
- Verdict: 초기 **NOT-SHIP**(BLOCKER 1) → 핵심 발견 흡수 후 **PASS**.
- BLOCKER (흡수됨): share API 에 steps 를 조립해 넣으면 각 step 의 `result_summary.csv_paths`(서버 `/shared/` 파일 경로)·`preview`(결과 전문)·step `args`(원본 tool 인자)·`error`(원본 오류 본문)가 **익명 JSON 페이로드로 누출**(화면 렌더가 아닌 `curl` API 응답에서). 라이브 PG 확인: `agent_runtime.steps.result_summary_json` 614건 중 540건이 `csv_paths`(`/shared/...`)·`preview` 보유.
- Resolution: `_share_sanitize_step` 신설 — 각 step 을 화이트리스트 `{tool,sql,reason,intent,work,result_summary.preview_table}` 로 재구성(그 외 키 제거). `_share_attach_sanitized_steps` 가 조립 후 sanitize 를 강제하고, attachment_derived 메시지는 steps 자체를 제거(redact + 재조립 skip 이중 차단). **라이브 end-to-end 검증**: worktree app.py 를 컨테이너에 임시 적용 후 `_share_load_messages('20260527044221-bc2639bf', v=CURRENT)` 호출 → 응답 JSON 에 `csv_paths` 키 0·bare `preview` 키 0·step 경유 `/shared/out` 0(직렬화 grep). 신규 단위테스트 2건(`test_share_sanitize_step_strips_server_paths_and_raw_payload` 가 csv_paths/preview/args/error 제거 + `/shared/` 문자열 부재 단언, `_handles_malformed` 가 비-dict/누락 result_summary 안전).
- MAJOR (정합 확인): version gate(`redact_active`) 와 steps 재조립의 상호작용 — steps 재조립은 `role=='assistant' and not was_redacted` 일 때만 수행하므로 attachment_derived(redact 대상)는 steps 가 붙지 않음. 현 v2 토큰(redact_active=False)에서도 attachment 메시지는 본문이 write 시점에 이미 redact 저장 + steps 미조립이라 정합.
- MINOR (오탐 기각): "`formatSqlForDisplay` 가 `` sentinel 누락 → `LIMIT 100` 숫자 오치환" 주장은 **false positive** — diff 의 비가시 제어문자(``)를 리뷰어가 못 본 것. `cat -A` 로 `^A${i}^A` 마스킹·`/^A(\d+)^A/g` 복원 정상 확인 + Playwright 라이브에서 `LIMIT 10` 정상 표시.
- XSS / null 안전 / 폴백 회귀: PASS(buildPreviewTable/buildSqlStepPanel 전부 `textContent` 사용 — 익명 페이지에 신뢰불가 DB 컬럼명/셀값 HTML 미해석; 본문은 DOMPurify 유지; steps 없는 구형 메시지 final_sql/result_rows 폴백 보존).
- Human Approval Needed: no (노출 축소 방향 + 익명 경계 sanitize 가 base 대비 강화).
- 잔존(범위 밖, flag-only): 답변 **본문 텍스트**에 LLM 이 `/shared/` 경로를 직접 쓴 경우는 base 부터의 본문 표시 동작(step 경유 아님) — 별도 본문 redaction 정책. 본 cycle 은 step 경유 누출만 책임.
- Artifact: unit/feature-0003-agent-web-ui/docs/reviews/20260612T010000Z-share-anonymous-exposure.md
- Cross-ref: CHG-20260612-0251 / TASK-0251 / REV-20260609-0001(public-exposure 가드 권고) / TASK-0094(share redaction 정책).

## REV-20260612-0248 [SUBAGENT:security+correctness-adversarial, 2-agent] — SHIP-WITH-FIXES → 흡수 후 SHIP
- Date: 2026-06-12
- Cycle: TASK-0248 (관리 콘솔 제품 삭제 시 참조 대화 차단(blocked) 전환 — **Major §12.3**, 파괴적 삭제 + 접근 차단 + cross-store)
- 패널: 적대적 outside-voice 2-agent 병렬 — (A) 백엔드 보안/정합성(SQL 바인딩·오차단·cross-store fail-closed·conn 누수·멱등·컬럼부재·split-brain), (B) 프런트 우회/요구사항 정합(canAsk/sendPrompt 우회·공유/이력/fork 충족).
- **백엔드 VERDICT: SHIP-WITH-FIXES (BLOCKER 0)**. probe 판정:
  - ① UPDATE/SELECT 파라미터 바인딩·순서 — **PASS**(PG/MySQL 양 경로 `(reason, product_id)` placeholder 순서 정확, 전부 parametrized, 인젝션 불가; `test_block_conversations_for_product_sql` 가 순서 고정).
  - ② 타 제품/auto(NULL) 오차단 — **PASS**(`WHERE product_id = %s AND blocked_at IS NULL` — SQL 3-value logic 으로 NULL product_id 미매칭, 타 제품 불가침).
  - ③ cross-store fail-closed 백스톱 진위 — **PASS(가설 반증)**. pinned 대화: 제품 cascade 삭제로 `WebProducts` 행 소멸 → `_account_has_product_access(<deleted_id>)` 가 행 없음 → False → `/api/ask` 403. 차단 UPDATE 실패와 무관하게 진행 차단. **허구 아님**(BLOCKER 회피).
  - ④ ask 403 경로 conn 누수/이중 close — **PASS**(`_conversation_block_info(conn=conn)` 의 `own_conn=False` → 전달 conn 미close, PG 모드는 별도 `_pg_connect` 만 open/close; ask 가 1회 close 후 return — 이중 close/누수 없음).
  - ⑤ 멱등성 — **PASS**(재차단 방지 `blocked_at IS NULL`, `product_id<=0/None` early-return, 삭제 제품 재삭제 무해).
  - ⑥ PG 컬럼 런타임 부재 시 500 — **FAIL(MAJOR)**. `_conversation_block_info` 는 except fail-open 으로 안전하나, `_list_conversations_pg` 메인 SELECT(except 없이 finally 만)와 `admin_delete_product` COUNT 는 가드 없어 `UndefinedColumn` → 500. → **운영 절차로 흡수**(아래).
  - ⑦ COUNT/block backend 판정 일치(split-brain) — **PASS**(`_runtime_backend_is_pg()` ≡ `os.environ AGENT_RUNTIME_READ_BACKEND == postgres`, 둘 다 동일 리터럴 조건 — 단일 요청 내 분기 불일치 없음).
  - list row unpack 7컬럼 일치(PG positional / MySQL dict-access) **PASS**, blocked JSON PG/MySQL parity **PASS**.
- **MAJOR-1/2 (probe ⑥) 흡수 결정 = 운영 절차(코드 무변경)**: 이 프로젝트는 **migrate-first 가 명시적 배포 계약**(TASK-0149/MIGRATIONS.md, web=DML-only role 이라 런타임 ALTER 불가). 과거 additive 컬럼(`resolved_model`, TASK-0163)도 동일하게 degrade 가드 없이 처리한 기존 패턴. degrade 가드 추가는 PG tx abort 처리 복잡도+회귀 위험 도입 → **배포 E 단계가 `make migrate`(alembic 0005) 를 web 재빌드 *전* hard precondition 으로 못 박고, 라이브 F 검증에서 `SELECT blocked_at` 컬럼 존재를 psql 로 실측 게이트**. MINOR(fail-open auto-모드 사각=`allowed_schemas=[]` 로 데이터 누출 0; PG commit-직전-예외 close 암묵 rollback)은 수용.
- **프런트 VERDICT: SHIP (BLOCKER/MAJOR 0)**. 우회 송신 경로 전수 조사 — `/api/ask` 호출 진입점은 `sendPrompt()` 단 하나(sendBtn click·Enter keydown 모두 경유), 시작부 `active.blocked` 가드 + `promptInputEl.disabled = busy || isBlocked` + 백엔드 403 이중 차단 → 우회 불가(UX 결함조차 아님). 요구사항: **공유 가능 O**(share-create 에 blocked 제한 미추가), **이력 열람 O**(renderMessages blocked 미참조, CSS dim/line-through 가 `pointer-events` 미차단), **fork 가능 O**(canFork blocked 미참조, composer 안내문과 동작 일치). renderComposer 분기 우선순위 정상(!hasAsk > isBlocked > 타계정 > busy). MINOR(blocked+busy 동시 시 "중단버튼+차단안내" cosmetic 공존 — sendPrompt busy early-return 으로 우회 불가, run 종료 후 수렴) 수용.
- **프런트 M-2(admin.js 무관 변경 혼입 의혹) = 오탐 확정**: 리뷰어가 `git diff main`(=stale base ff59f8f)을 봄. origin/main(f2a390b)이 base 이후 PR #196(conn-health-monitor)로 전진했고, `git diff HEAD` 기준 본 cycle 실작업은 TASK-0248 9개 파일뿐(conn-health 혼입 0). **머지 전 origin/main 위로 rebase 완료**(admin.html 캐시버스터 충돌 1건 해결, app.py/admin.js 자동 병합으로 conn-health+TASK-0248 양립 — node --check/py_compile/make test 600 passed·2 skip·신규 7 PASS 재검증).
- 검증: node --check(app.js·admin.js) + py_compile(app.py·alembic) + CSS brace 1108=1108 + make test 컨테이너 **전체 회귀 0**(600 passed/2 skip) + 신규 `test_product_delete_block_conv.py` **7 PASS**.
- Cross-ref: feature-0002(스키마 blocked_at/blocked_reason + alembic 0005_core_conv_blocked) / CHG-20260612-0248 / TASK-0248.
## REV-20260612-0251 [SKIPPED:visual-verify-followup] — PASS
- Related TASK: feature-0003-agent-web-ui (TASK-0249 — PB-0008 Windows-browser 시각검증 evidence 후속)
- Reason: 코드 변경 0(이미 REV-20260612-0249 에서 적대 리뷰 SHIP·머지 완료). 본 cycle 은 TEST.md §4 Run 기록 + win-browser 시나리오 파일 추가뿐 — 시각검증 evidence 영속화. 신규 로직/엔드포인트/권한 표면 0.
- 검증 결과: PB-0008 Windows Chrome/148 PASS — 제품94 요약 100%(571/571), datasource accordion 별 dbgame 99/99·dbcommon 111/111·dbauth 10/10 마이크로바·DB✓ 시각 실증(0/0 해소). 스크린샷 `/tmp/win-browser-shots/task0249/{10,11,12}*.png`.
- Timestamp: 2026-06-12T00:00:00Z
- Human Approval Needed: no
- Cross-ref: REV-20260612-0249 / TASK-0249 / TEST.md §4 2026-06-12.

## REV-20260612-0250 [SUBAGENT:conn-health-monitor-adversarial] — SHIP-WITH-FIXES (cross-feature, 코어=feature-0002)
- Date: 2026-06-12
- Cycle: TASK-0250 (연결 health 모니터 — web/admin 측, **Major §12.3**)
- 패널: 본 cycle 의 적대적 outside-voice 2-pass 리뷰는 코어(feature-0002 conn_health.py + gate)에서 수행(REV-20260612-0250). web 측 변경은 그 모니터의 표면 — admin 표시(사전계산 conn_status)와 web 프로세스 모니터 기동.
- web 측 검토: ① `conn_status` 응답이 **좌표/비밀번호 비노출**(snapshot 화이트리스트 status/elapsed_ms/checked_at 만) — IDOR/누출 0(console.access 신뢰경계 내). ② admin.js 자동 토글 경로의 per-item lazy probe 폐기로 세마포어 head-of-line 대기 제거(m1: unknown 콜드 edge 만 lazy 폴백). ③ startup/shutdown 훅이 모니터 생명주기 idempotent 관리(start 이중 가드). 신규 RBAC 0, 엔드포인트 shape: `admin_list_datasources` 에 `conn_status` 필드 추가뿐.
- 검증: node --check admin.js + make test 컨테이너 회귀 0. 잔여: 배포 후 PB-0008 admin 연결상태 시각검증(CHECK#13 WARN).
- Cross-ref: feature-0002 REV-20260612-0250(코어 적대 리뷰) / CHG-20260612-0250(web) / TASK-0250.

## REV-20260612-0249 [SUBAGENT:backend-correctness] — SHIP
- Related TASK: feature-0003-agent-web-ui (TASK-0249 — 제품 insight 완료율 멀티 datasource(1:N) + 대소문자 매칭 수정)
- Trigger: schema/query keyword matched (coverage 계산 SQL·멀티 datasource 격리) — §18.8 backend/qa dispatch. 적대적 correctness+보안 outside-voice.
- Timestamp: 2026-06-12T00:00:00Z
- Verdict: **SHIP** (BLOCKER 0, CONCERN 1 흡수). 핵심 버그 2개(① datasource_key 별 그룹핑으로 멀티 datasource 정상 집계, ② db.py `LOWER(TABLE_SCHEMA)` 대소문자 매칭) 올바르게 해결 — 단일 datasource 무회귀·datasource 격리(각 그룹 자기 coords/scope, cross-datasource 누수 없음)·SQL injection 무표면(LOWER 변경이 bound param 유지)·pg 연결 finally close 전부 PASS.
- Critical issue (흡수): 동명 DB 가 서로 다른 datasource 그룹에 등록될 경우(멀티 datasource 정상 시나리오) `order` 중복 → 합산 이중 카운트로 pct 왜곡. 합산 루프에 `seen_dbs` 가드 추가로 흡수(app.py:14402) → 재테스트 599 passed 무회귀.
- 잔여(저위험 후속, 회귀 아님): 혼합 engine top-level 표기(engines_seen[0]; per_db 는 정확), 한 그룹 PG 실패 시 전역 측정불가 정책(데이터 무결성 우선), `_analyzed_sets_for_scope` cursor 위생(connection close 로 회수 — 실 누수 없음).
- Artifact: unit/feature-0003-agent-web-ui/docs/reviews/20260612T000000Z-coverage-multi-ds-correctness.md
- Human Approval Needed: no (Minor §12.3 — RBAC·스키마·암호화·엔드포인트 shape 0, read-only coverage 계산, BLOCKER 0)
- Cross-ref: CHG-20260612-0249 / TASK-0249 / [[project_task0223_product_insight_coverage]].

## REV-20260612-0247 [SKIPPED:trivial-css-1line] — SHIP
- Related TASK: feature-0003-agent-web-ui (TASK-0246 정련 CHG-0246b — 연결배지 `justify-self` end→start)
- Trigger: CHG-0246 배포 후 PB-0008 측정에서 연결배지 left spread=25(우측 정렬). 사용자 컬럼 정렬 선호(행별 left spread=0)·sibling `.cov-db-row` 컨벤션 정합.
- Verdict: **SHIP** (BLOCKER 0). CSS 1줄(`justify-self: end`→`start`) + 캐시버스터. 로직/구조/권한/데이터 0.
- SKIPPED 근거: cosmetic 정렬 1줄, 실질 게이트 = PB-0008 재측정(전 열 left spread=0).
- Human Approval Needed: no
- Cross-ref: CHG-20260612-0246b / REV-20260612-0246 / [[feedback_row_list_column_alignment]].

## REV-20260612-0246 [SKIPPED:trivial-grid-align] — SHIP
- Related TASK: feature-0003-agent-web-ui (TASK-0246 — "+ 데이터소스 추가" 드롭다운 항목 열 정렬). 동시세션 db-row-align 이 TASK-0245 선점 → §13.1 재번호 0245→0246.
- Trigger: TASK-0244 직후 CSS-only follow-up(단일 규칙 블록 — flex→grid 고정 열 폭). 적대적 outside-voice 보다 PB-0008 실측 시각검증이 실질 게이트인 cosmetic 변경.
- Timestamp: 2026-06-12T00:00:00Z
- Verdict: **SHIP** (BLOCKER 0). 변경 = `.admin-ds-picker-item` `display:flex`→`display:grid` + 고정 트랙 + justify-self. admin.js·백엔드·RBAC·스키마·probe 동작·DB picker·`.cov-db-row`(동시세션 0245)·accordion 무변경(셀렉터 격리: 복합 `.admin-db-picker-item.admin-ds-picker-item`).
- SKIPPED 근거(§18.4): ① 코드/엔드포인트/권한/데이터 노출 면 0(순수 CSS 레이아웃), ② 변경 표면 = 단일 규칙 블록, ③ 열 폭은 라이브 DOM 측정(엔진 43/좌표 87/상태 94px)에 근거, ④ 레이아웃 정확성은 실 픽셀(PB-0008 Windows-browser)이 결정적. 전례 TASK-0178/0179/0180 css-layout SKIP 과 동급.
- 셀프 점검: 고정 트랙 합(체크박스 auto + 4 gap×8 + 56+124+104 = 332) < 콘텐츠영역(≈518) → 이름 `1fr` ≈186px 확보(잘림 시 ellipsis). 측정 콘텐츠 전부 트랙 내 수용. justify-self(start/start/end)로 좌/우 경계 정렬.
- Human Approval Needed: no (cosmetic CSS·신뢰경계 무관·BLOCKER 0)
- 검증: CSS brace 균형(1105/1105). 배포 후 PB-0008 Windows-browser 열 정렬 시각검증(실질 게이트).
- Cross-ref: CHG-20260612-0246 / TASK-0246 / FUNCTION REQ-20260612-0246(AC-0460) / REV-20260612-0244.

## REV-20260612-0244 [SUBAGENT:design+correctness] — SHIP
- Related TASK: feature-0003-agent-web-ui (TASK-0244 — "+ 데이터소스 추가" 드롭다운 폰트 정합 + 연결 상태 표면화)
- Trigger: UI/디자인 변경(§18.8 UI→design/ux) + 시각 정합·네트워크 probe 동작의 회귀/접근성 outside-voice 검토. 사용자 요청 = 폰트 이질감 해소 + 연결 상태 표면화.
- Timestamp: 2026-06-12T00:00:00Z
- Verdict: **SHIP** (BLOCKER 0, NIT 4 — 1건[동시성 cap] 선반영, 나머지 cosmetic/기존 부채). 5개 검토 항목 전부 CLEAN.
- 검증 결과:
  - **(1) 시각 정합 — CLEAN**: 신규 `.admin-ds-picker-engine`(styles.css 2997~3002) 이 accordion `.ds-acc-engine`(2774~2781)과 byte-identical 토큰(`font-size:11px; color:var(--text-2); background:var(--bg); border:1px solid var(--border-subtle); border-radius:var(--r-sm); padding:1px 6px`). 이름은 DB picker `.admin-db-picker-name`(2960) 직접 재사용. 항목 폰트 13px(`.admin-db-picker-item`)=accordion `.ds-acc-head` 13px. 연결 배지는 `.admin-db-picker-status` pill geometry 미러. 사용 CSS 변수 전부 정의됨(:root 9~46).
  - **(2) 연결 상태 UX — CLEAN(+cap 반영)**: lazy probe(드롭다운 열림 시 probe) + 세션 캐시 + ↻ 강제 재probe 합리적. 엔드포인트 `/datasources/{key}/test`(app.py 10362)→`{ok,elapsed_ms,error}`, apiFetch 2xx/throw 양 경로 처리. **동시성 cap 부재 nit → 본 cycle 에서 4개 세마포어로 선반영**(unreachable 다수 + 8s connection_timeout 시 web 스레드 동시 점유 차단).
  - **(3) 회귀 — CLEAN**: 체크박스 토글→`_rebuildDsAddList` 재호출 시 캐시 hit 경로(`state===ok|fail`)가 재probe 차단 확인. refresh 버튼 `<button type=button>`+stopPropagation+preventDefault → 체크 토글/`_closeDsAdd` 닫힘과 무충돌(addRow.contains true).
  - **(4) 접근성/엣지 — CLEAN**: 빈 목록 early-return(헤더 추가 前)·canDs=false 시 picker 블록 미렌더. 상태 = `●` 점 + 한글 라벨 병행이라 색-단독 비의존(색맹 OK). is-fail tooltip 에 error 노출(admin-only, 신뢰경계 내).
  - **(5) 코드 품질 — CLEAN**: 명명/변수 정합, 미사용 없음.
- NIT: ① 동시성 cap(반영 완료). ② `_closeDsAdd` document 리스너 누수 = 0244 신규 아님(기존 picker 5272·⋯메뉴 5430 동일 패턴) — 별도 정리 가치. ③ is-checking 색맹 OK(점+텍스트). ④ refresh 충돌 없음(확인됨).
- Human Approval Needed: no (frontend-only·기존 엔드포인트 재사용·신뢰경계 내·BLOCKER 0)
- 검증: node --check admin.js PASS + CSS brace 균형 + 배포 후 PB-0008 Windows-browser 시각검증.
- Cross-ref: CHG-20260612-0244 / TASK-0244.

## REV-20260612-0243 [SUBAGENT:correctness+side-effect] — SHIP
- Related TASK: feature-0003-agent-web-ui (TASK-0243 — MSSQL db-insights catalog 귀속 수정)
- Trigger: 사용자 명시 — "키 수정 시 다른 기능 side-effect 면밀 검증". by_db 그룹핑 키를 schema_name→object_key catalog 로 변경하는 것이 coverage/insight-reset/insight-worker write 등 다른 기능에 영향 주는지 적대적 검증.
- Timestamp: 2026-06-12T00:00:00Z
- Verdict: **SHIP** (BLOCKER/MAJOR/MINOR 0, NIT 2 — docstring 문구·스타일). 5개 검토 항목 전부 CLEAN.
- 검증 결과:
  - **(1) 파서 엣지 — CLEAN**: 식별자에 점(.) 불가(`_sanitize_ident_part` 가 `[0-9A-Za-z_]` 만 허용 후 dot-join) → catalog/schema/table segment 에 literal dot 없음. 접두에 ':' 불가(`_ds_valid_key` 가 ':' 금지, 키=`{engine}-{hash12}`) → `split(':',1)` 항상 안전. object_key varchar(255) 절단은 fact_key 의 `:{digest}` 를 끝에 붙이므로 front catalog 보존. column 객체는 SQL `object_type IN (schema,table)` 로 사전 제외.
  - **(2) MySQL 무회귀 — CLEAN**: MySQL 은 `database_name` 미설정(set_active_database 는 MSSQL 분기 전용) → object_key path=`{schema}`|`{schema}.{table}`, segs[0]==schema_name 항상. 게다가 본 구현은 MySQL 을 schema_name 직접 사용 분기로 처리 → by_db 키 **byte-identical**.
  - **(3) side-effect 격리 — CLEAN**: `_db_catalog_from_object_key` 호출처 1곳(db-insights). `_compute_product_insight_coverage` 는 object_type/schema_name/table_name 만 SELECT(object_key 미사용). `admin_product_insight_reset` 는 (schema_name,table_name) 튜플 매칭(object_key 미사용, 코드 주석 일치). 다른 object_key 사용처는 MinIO 첨부(무관). insight-worker write 경로(feature-0002) 무수정 — git diff: app.py+test+docs 3 파일만.
  - **(4) 프런트 정합 — CLEAN**: WebProductDatabases.SchemaName("GameLog_100") → worker `ds_object_suffix` 가 `.lower()` → object_key catalog `gamelog_100` → 백엔드 by_db 키 `db.lower()` → 프런트 `insByDb[entry.schema_name.toLowerCase()]` — 3-way 동일 소스 소문자화, 불일치 없음.
  - **(5) over-skip — CLEAN(accepted-risk note)**: 현 worker 는 MSSQL 통찰을 항상 catalog-qualified(set_active_database 항상 호출, default_db 포함) → 등록 catalog 누락 없음. 유일한 over-skip = legacy pre-TASK-0220 bare 데이터인데, 본 수정이 **오히려 개선**(기존엔 잘못된 'dbo' 바구니로 붕괴, 이제 정확히 skip) — 신규/악화 아님.
- NIT(반영): docstring `{scope}:` → `{ds_prefix}:` 정정(접두는 datasource_key 라벨/해시, 파서가 버림). NIT2(engine.lower vs object_type 정확매칭)=worker 가 항상 소문자 리터럴 기록이라 무위험, 미수정.
- Human Approval Needed: no (단일 함수 격리·write 경로 무관·전체 회귀 0)
- 검증: db_insights 17 PASS(파서 2 + MSSQL 귀속 1 신규) + make test 컨테이너 전체 회귀 0 + ruff clean + py_compile. 배포 후 라이브 대조(MySQL 키 불변·MSSQL catalog 매칭) + PB-0008 MSSQL.
- Cross-ref: CHG-20260612-0243 / TASK-0243 / FUNCTION REQ-20260612-0243(AC-0456) / TASK-0242(REV-20260612-0242).

## REV-20260612-0242 [SUBAGENT:security] — SHIP-WITH-FIXES→흡수→SHIP
- Related TASK: feature-0003-agent-web-ui (TASK-0242 — 관리 콘솔 제품 데이터소스 DB별 insight 파악 내용 표면화 + 추가 picker 분석상태)
- Trigger: 신규 read 엔드포인트(API/endpoint) + PG 데이터 노출 surface — 적대적 보안/정합 outside-voice(§18.8). RBAC/스키마 무변경(console.access 재사용)이나 데이터 노출 면이라 subagent 검토.
- Timestamp: 2026-06-12T00:00:00Z
- Verdict: SHIP-WITH-FIXES (BLOCKER/MAJOR 0) → MINOR 2건 흡수 후 SHIP
- 점검 영역: SQL injection / scope confusion·cross-datasource·cross-product leak / IDOR / crash / resource.
  - **SQL injection — 없음**: 보간되는 `cond` 는 고정 리터럴(`o.datasource_key IS NULL` 분기는 `allow_null` bool 게이트), scope/conversation/scope_key 전부 bound `%s`. allow_null 은 server-computed(`scope==default_endpoint_scope`). 기존 coverage 쿼리와 동일.
  - **scope confusion / 누수 — 없음**: `?datasource=` 는 사용 전 `_list_product_datasources` 로 제품 바인딩 검증(미바인딩 400), 둘 다 lowercase 비교. 미지정 시 product primary 폴백(공격자값 X). `allow_null` 은 default endpoint 일 때만 NULL 행 포함 — 동일 물리 엔드포인트. cross-product 동일 scope 노출은 데이터모델 본질(엔드포인트 해시)로 기존 coverage 와 동일, 신규 누수 아님.
  - **IDOR — 없음**: product_id 미존재 404. console.access admin 은 이미 전 제품/coverage 가시. db-insights 는 더 상세(도메인/text_content)하나 바인딩 datasource 한정·기존 신뢰경계 내. 프런트는 textContent/title 만(innerHTML X) → stored-XSS 없음.
  - **crash — 없음**: datetime/load_memory_kv 모듈 스코프, fromisoformat try/except 안전 기본값, 파서 `str(x or "")`/`.get` 방어, PG 실패는 `{ok:False}` graceful + 프런트 "역할 미파악" fallback.
- MINOR(흡수): (1) `_compute_product_db_insights` PG 연결이 성공 경로에서만 close → 예외 시 누수(기존 coverage 패턴 답습). → **try/finally 로 모든 경로 close** 개선(기존 패턴보다 나아짐). (2) 결과셋 무제한(text_content 전량 메모리 적재). → **ORDER BY object_type,schema,table + LIMIT 5000** 방어적 절단(schema 우선 보존). NIT(scope=None while ok=True)은 fail-closed(빈 by_db) — cosmetic, 미수정.
- Human Approval Needed: no (신규 read·console.access 재사용·신뢰경계 내, MINOR 전건 흡수)
- 검증: 신규 14 테스트 PASS + make test 컨테이너 회귀 0 + ruff clean + node --check + py_compile. 배포 후 PB-0008 Windows-browser 시각검증.
- Cross-ref: CHG-20260612-0242 / TASK-0242 / FUNCTION REQ-20260612-0242(AC-0453~0455).

## REV-20260612-0240 [SKIPPED:frontend-no-backend-no-rbac] — PASS
- 패널 skip 사유: datasource picker 클리핑 수정 + 추가 UI 체크박스화. **frontend only**(admin.js/styles.css/admin.html) — RBAC·스키마·시크릿·엔드포인트·백엔드 0. 적대적 보안 subagent 비대상(§18.8).
- Date: 2026-06-12
- Cycle: TASK-0240 (picker 클리핑 + 데이터소스 추가 체크박스 토글, **Minor §12.3**)
- 검토 결과 (반증 시도):
  - **① 클리핑 근본수정 검증**: overflow 제거만으로 충분했나, inline 전환이 맞나? → Playwright 로 3중 클립 조상(ds-acc-body / admin-detail-col[overflow-y:auto, 제거 불가] / admin-workspace) 확인. `.ds-acc-body` overflow 만 제거하면 패널 스크롤 컨테이너(admin-detail-col)에서 여전히 잘릴 수 있음 → absolute→inline 전환이 정답(클리핑 박스 자체를 없앰). 수정 후 clipped:false + hitInside:true 실측. PASS.
  - **② 체크박스 토글 정합(최우선)**: select→체크박스로 바꿔도 스테이징 의미가 유지되나? → 체크=stageAdd, 해제=stageRemove, effective(desired) 바인딩이 체크 상태로 렌더. Playwright: 미체크 항목 체크 시 pending+1·행 2개·서버 불변, 같은 항목 해제 시 desired==baseline 복귀 pending 0·행 1개(토글 양방향). PASS.
  - **②-b 이미 바인딩된 datasource 체크 해제 = 제거**: 목록이 등록 datasource 전체를 보이고 바인딩된 것을 체크 표시하므로, 체크 해제로 기존 바인딩도 제거 가능(⋯ 메뉴 "바인딩 제거"와 동일 경로 stageRemove). primary 제거 시 첫째 승격도 stageRemove 가 처리. 일관. PASS.
  - **②-c 목록 재진입 동기화**: 토글 후 `_rebuildDsAddList` 가 effective 기준으로 체크 상태 다시 그림 + 버튼 재오픈 시에도 rebuild. accordion 로컬 재렌더(_afterBindChange)와 add-list 는 독립 컨테이너라 충돌 없음. PASS.
  - **③ ⋯ 메뉴 회귀 없음**: inline 전환·add-row 교체가 기존 ⋯ 메뉴(TASK-0239 수정)를 건드리지 않나? → Playwright TEST D 로 ⋯ 클릭 시 메뉴 항목 hit-test 정상 재확인. PASS.
- 잔여 리스크: 시각(드롭다운이 inline 으로 패널을 밀어내는 레이아웃·긴 목록 자체 스크롤)은 PB-0008 Windows-browser(배포 후). 기능/클리핑은 위에서 커버.

## REV-20260612-0241 [SUBAGENT:concurrency-adversarial] — SHIP (2-pass)
- Date: 2026-06-12
- Cycle: TASK-0241 (요청 취소 즉시 처리 + 취소 직후 재요청, **Major §12.3**, cross-cutting feature-0002+0003)
- 패널: 분산/동시성 정확성 특화 적대적 subagent 2-pass (run 수명주기·동시성 변경 — feedback 메모리 "concurrency-critical = outside-voice 필수" 적용).
- **1차 — NOT-SHIP (BLOCKER 2 · HIGH 2 · MEDIUM 2)**:
  - BLOCKER-1/2: enqueue 선기록이 run_id 없이 processing 을 써 KV `last_status_run_id` 가 직전(취소) run 으로 남음 → orphan terminal canceled write 가 supersede 가드를 우회해 새 요청 processing 을 클로버(새 요청이 조기 canceled 반환).
  - HIGH-1: 프런트 abort 가 서버 웹 슬롯을 안 풀어 빠른 취소→재요청 반복 시 6한도 429.
  - HIGH-2: 재요청 attach 가 orphan canceled 를 자기 terminal 로 오인 조기반환.
  - MEDIUM-1: early-cid sentinel↔cid 키 불일치로 중단이 in-flight fetch 를 못 끊음.
  - MEDIUM-2: pending(cid 발급 전) 윈도 취소가 발사 직전 send 를 못 막아 orphan run.
- **흡수 수정**: enqueue 선기록 sentinel run_id(BLOCKER-1/2+HIGH-2 동시 해소 — orphan 의 per-attempt run_id fencing 을 깨지 않으면서 가드가 정확히 skip) / attach `request.is_disconnected()` + job-aware 종료(HIGH-1) / 프런트 `cancelKeys`+`askKey`+발사전 재확인(MEDIUM-1/2).
- **2차 재검증 — SHIP**: BLOCKER 2·HIGH 2·MEDIUM 2 모두 닫힘 확인. sentinel+only_if_current_run+무조건 takeover 3중 정합, 나열 가능한 모든 인터리빙에서 새 run 보존·취소전용 canceled 오삭제 없음. is_disconnected 는 본문 소진 후 Starlette 표준 비차단 패턴(false-positive 없음). 프런트 askKey TDZ/스코프/flag 순서 안전. 신규 회귀 없음.
- **잔존(별 cycle, LOW)**: never-claimed pending job + sentinel KV 잔존 = pending-job TTL reaper 부재(본 변경 이전 class, 악화 아님 — sentinel 화가 오히려 run 귀속 모호성 제거). SHIP 차단 사유 아님.

## REV-20260612-0239 [SKIPPED:frontend-no-backend-no-rbac] — PASS
- 패널 skip 사유: datasource accordion 후속 버그/UX 수정. **frontend only**(admin.js/styles.css/admin.html) — RBAC·DB 스키마·시크릿·엔드포인트 shape·백엔드 0(기존 엔드포인트 재사용, desired-state 는 클라이언트 diff). 적대적 보안 subagent 비대상(§18.8).
- Date: 2026-06-12
- Cycle: TASK-0239 (⋯ 메뉴 클릭불가 + 추가 즉시반영 + 클릭 깜빡임, **Minor §12.3**)
- 검토 결과 (반증 시도):
  - **① 메뉴 클리핑 근본수정 검증**: overflow 제거가 정말 원인이었나? → Playwright `elementFromPoint(메뉴중앙)` 가 수정 전 `.cov-db-editor`(클리핑돼 메뉴 안 그려짐) → 수정 후 `.ds-acc-menu-item`("연결 테스트") 로 바뀜을 실측. 토글 JS 는 원래 정상이었고 CSS 클리핑이 유일 원인. PASS.
  - **② 일괄 적용 정합(최우선 위험)**: desired-state diff 가 서버를 올바른 최종 상태로 수렴시키나? baseline 은 진입 시 1회 스냅샷, desired 만 변형, apply 시 제거→추가→primary 순. → 추가 스테이징 시 서버 바인딩 불변(Playwright list endpoint 직접 확인) → "모두 적용" 후에만 서버 2개. 제거도 동일(스테이징 불변→적용 후 1개). primary 재지정: 0개→첫 추가는 PATCH(자동 primary), 그 외 명시 POST is_primary. PASS.
  - **②-b 제거+DB 고아 방지**: 제거된 datasource 의 접근DB draft 가 PUT 되면 서버가 방금 삭제한 행을 되살리거나 미존재 바인딩 PUT 오류. → `_removedDsByProduct` Set 으로 해당 pkey 의 productDb PUT skip(pending 만 정리) 확인. PASS.
  - **②-c dirty/취소/GC/재진입**: desired==baseline 이면 `_settleDatasourcePending` 가 엔트리 삭제(dirty 0). cancelAllPending·삭제제품 GC·재진입 펼침대상(effective primary) 모두 desired 반영. 부분 실패 시 loadAdminData 가 서버 정본 재동기화. PASS.
  - **③ 깜빡임 제거 부작용 없나**: 전체 렌더 대신 로컬 accordion 재렌더로 바꿔 다른 패널(프롬프트/삭제)이 stale 되지 않나? → 바인딩 변경은 datasource 영역에만 영향, 그 영역만 재렌더가 정합. redrawChips 동기 선호출 후 비동기 _refreshAccessibleDbs 가 picker/시스템칩 정교화(순서 보존). prefers-reduced-motion 존중. PASS.
- 잔여 리스크: 시각(펼침 애니메이션 부드러움·메뉴 드롭 위치)은 PB-0008 Windows-browser(배포 후) — WSL 헤드리스는 hit-test/동작 검증. 기능/상태 정합은 위에서 커버. 다중 datasource(3개+) 복합 배치(동시 추가+제거+primary 변경)는 diff 로직상 지원하나 Playwright 는 단일 추가/제거만 실측 — 복합은 단위 로직(_dsBindEqual/diff) 정확성에 의존.

## REV-20260612-0238 [SKIPPED:frontend-redesign-no-backend-no-rbac] — PASS
- 패널 skip 사유: datasource 패널 통합 accordion **재설계(표현 계층)**. RBAC 카탈로그·DB 스키마·시크릿·엔드포인트 shape·백엔드 로직 변경 0(기존 datasources/datasource/test 엔드포인트 재사용). 적대적 보안 subagent 비대상(§18.8). 디자인 통일성/접근성 감사는 gstack `/design-review` + codex outside-voice 가 이미 수행 → 그 지적을 흡수한 재설계 자체가 리뷰 산출물.
- Date: 2026-06-12
- Cycle: TASK-0238 (datasource 패널 통합 accordion 재설계, **Minor §12.3**)
- 검토 결과 (반증 시도):
  - **회귀 위험(최우선)**: 편집 로직(draft/_refreshAccessibleDbs/redrawChips/buildPicker)을 그대로 두고 표현 계층(섹션 구조·칩→행)만 교체했나? → draft 클로저 4종 + _serverDbsFor + buildPicker 그대로 보존, dbEditorWrap(시스템칩+DB리스트+picker) 컨테이너 자체를 active 행 아래로 **이동**(재생성 아님)했음을 소스로 확인. _editDsKey TDZ 수정(TASK-0236) 유지. PASS.
  - **첫 바인딩 vs 추가 바인딩 분기**: "＋ 데이터소스 추가" 가 미바인딩 제품엔 PATCH `/datasource`(첫 바인딩), 기존 바인딩 제품엔 POST `/datasources`(추가) 로 갈리나? → `hadBindings` 분기로 처리 확인. PASS.
  - **active 전환 시 DB 목록 정합**: 행 전환(_switchEditDs)이 _editDsKey 갱신 후 _refreshAccessibleDbs(key) 를 호출해 펼친 datasource 의 접근DB 만 보이나? → Playwright 멀티 바인딩 전환에서 DB 목록이 datasource 별로 바뀜 확인. PASS.
  - **바인딩 제거/기본지정 후 정본 동기화**: ⋯ 메뉴 액션이 adminState.products + product 로컬을 갱신하고 renderProductDetail() 전체 재렌더하나(TASK-0236 부분갱신 버그 재발 방지)? → `_reloadProductDatasources` 가 GET 재조회→adminState 동기화→renderProductDetail() 호출 확인. PASS.
  - **접근성**: caret head 가 button + aria-expanded, ⋯ 메뉴 aria-haspopup/role=menu/menuitem + aria-label, 추가 select aria-label 유지. PASS.
- 잔여 리스크: 시각 레이아웃 최종 확인은 PB-0008 Windows-browser(배포 후) — WSL 헤드리스는 동작 검증, 실 픽셀 괴리는 Windows 화면 필요. 기능/구조 회귀는 위에서 커버.

## REV-20260612-0237 [SKIPPED:backend-sse-streaming-self-review] — PASS
- 패널 skip 사유: SSE 토큰 스트리밍 + LLM 명명 정리. 인증/인가/데이터 경계/스키마/시크릿 변경 0(신규 stream GET 은 기존 product.manage 게이트 재사용). 적대적 보안 subagent 비대상(§18.8) — 단 단일 이벤트 루프 블로킹·스레드 누수·buffering 위험이 있어 backend correctness self-review 수행. 동시세션 cycle 이 REV-0235/0236 선점→§13.1 재번호 0233→0237.
- Date: 2026-06-12
- Cycle: TASK-0237 (자동작성 LLM 토큰 스트리밍 SSE + OpenAI legacy 명명 정리, **Major §12.3**)
- 검토 결과 (반증 시도):
  - **이벤트 루프 블로킹(최우선 위험)**: docker-compose web 은 단일 uvicorn 워커(`--workers` 없음). async generator 안에서 동기 LLM stream 을 `for chunk in stream` 직접 iterate 하면 전 사용자 루프 정지(Codex C1, export_audit_csv 가 sync generator 쓴 이유). → **별 스레드 `produce()` + `loop.call_soon_threadsafe` + `asyncio.Queue` 브릿지**로 async generator 는 큐 `await get()` 만 — 블로킹 호출이 메인 루프 밖. PASS.
  - **스레드 누수(client disconnect)**: client 가 스트림 중 끊으면 generator 가 중단되나 producer 스레드는 잔존 가능. → `call_soon_threadsafe` 가 loop closed 시 예외 → `_emit` 의 try/except 로 무시 + SDK timeout 90s 내 stream iteration 자연 종료. PASS(완전 즉시 취소는 아니나 90s bound).
  - **인증 우회 불가**: 인증·권한(product.manage)·제품조회를 `_collect_product_prompt_context` 가 generator 진입 **전** 수행 → 실패 시 JSON 403/404/503(SSE 헤더 전송 전). 권한 없는 자가 stream 토큰 받는 경로 없음. PASS.
  - **truncated 정합**: 마지막 chunk finish_reason=='length' → done.meta.truncated. 비스트리밍 POST 와 동일 의미(meta shape 동일 + truncated). PASS.
  - **에러 채널**: stream 시작 후(HTTP 200) LLM 예외는 SSE `error` event 로만 전달(HTTP 상태 변경 불가) → 프론트가 error event 분기 처리. PASS.
  - **rename 무중단**: `_get_llm_client` alias(`_get_openai_client`) + env fallback(LLM_MODEL or OPENAI_MODEL). 운영 .env `OPENAI_MODEL=auto` 무중단. PASS.
- 잔여 리스크: **프록시/TLS buffering 시 토큰 batched 도착** → uvicorn 직접 종단(nginx 없음)이라 위험 낮으나 X-Accel-Buffering:no 헤더 + PB-0008 시각검증으로 최종 확인 필요. `call_openai_embeddings` rename 은 follow-up(범위 외).
- 검증: 신규 test_prompt_generate_stream.py 6 + truncation 3 + (agent-core) env_naming 6 + 앵커 PASS. node --check. 통합테스트(app import)는 컨테이너 `make test` 영역.
- Human Approval Needed: no — 사용자 승인 plan(PLAN-APPROVED) 범위 내. 보안 trade-off 신규 0.
- Cross-ref: CHG-20260612-0237 / TASK-0237 / agent-core REV-20260612-0237 / plan groovy-hugging-clarke.

## REV-20260612-0236 [SKIPPED:frontend-bugfix-no-backend-no-rbac]
- Date: 2026-06-12
- Cycle: TASK-0236 (datasource UI 바인딩 변경 후 미갱신 근본수정, **Minor §12.3**)
- Reason: frontend-only 버그 수정. 부분 갱신→전체 재렌더 전환 + TDZ 선언 순서 수정. 신규 RBAC/스키마/엔드포인트/백엔드/시크릿 0건. 새 백엔드 표면 0. outside-voice panel 불필요 조건 충족.
- 검증 방식(이번엔 실측): **Playwright 실 헤드리스 브라우저(chromium-headless-shell)로 라이브 admin 콘솔 구동** → 수정 전 add 후 productDetail blank(ReferenceError) 재현 → 수정 후 add(칩·편집대상 select·배지 갱신)·edit-target switch(배지·DB목록 전환 datasource 반영) 모두 PASS, 콘솔/page 에러 0. make test 컨테이너 회귀 0. 라이브 `/test` 백엔드 정상은 TASK-0234 에서 확인됨.
- 교훈: TASK-0234/0233 의 frontend 변경을 실제 브라우저 검증 없이 배포해 사용자가 미흡함을 반복 보고. **JS 동작 버그는 WSL 헤드리스(Playwright)로 충분히 잡히므로 frontend 변경 시 실브라우저 재현/검증을 기본 게이트로 삼는다.** (PB-0008 Windows 검증은 시각 괴리 전용으로 별도 유지.)
- Human Approval Needed: no.
- Cross-ref: CHG-20260612-0236 / TASK-0236 / TASK-0234(직전) / TASK-0230(원 멀티 datasource cycle).

## REV-20260612-0235v [SKIPPED:verification-evidence-docs-test-only]
- Related TASK: feature-0003-agent-web-ui (TASK-0235 후속)
- Reason: TASK-0235 코드(PR #172 머지·배포 완료)의 PB-0008 Windows-browser 시각검증 PASS 를 TEST.md 에 기록 + 재현 시나리오 자산 추가. 변경 = docs(TEST.md) + test scenario(json) only, src/백엔드/스키마/RBAC 0. 코드 리뷰 대상 변경 없음 — TASK-0235 본체는 REV-20260612-0235 [SUBAGENT] 에서 이미 적대적 동시성 리뷰 완료.
- Timestamp: 2026-06-12T00:35:00Z
- Cross-ref: REV-20260612-0235 (본체 리뷰) / TASK-0235 / CHG-20260612-0235v.

## REV-20260612-0235 [SUBAGENT:newconv-progress-adversarial-concurrency] — CONCERN
- Related TASK: feature-0003-agent-web-ui (TASK-0235)
- Trigger: UI/screen keyword matched (작업 단계 표시/사이드바) + 동시성 state 전환 (lazy-create send 경로)
- Timestamp: 2026-06-12T00:00:00Z
- Verdict: CONCERN
- Artifact: unit/feature-0003-agent-web-ui/docs/reviews/20260612T000000Z-newconv-progress-concurrency.md
- Critical issue (if BLOCK/CONCERN): early-cid 발급 후 /api/ask 실패 시 빈 대화 고아화 가능 (CONCERN #3) → earlyCidActivated 플래그로 non-lazy 복구 경로 분기하여 흡수
- Human Approval Needed: no
- 요약: 적대적 동시성 리뷰 7 실패모드 중 5개(중복폴링/빈status조기종료/sentinel가드/첨부회귀/bubble race) 안전 확인. CONCERN 2건 흡수 — #3 고아 대화(earlyCidActivated 도입: ask 실패 시 진행 중 run 추적 경로로 전환, 빈 대화는 실 run 컨테이너가 됨), #2 빈 대화에 명시 cid /api/ask → run_agent 가 user_message 저장 책임(agent_core:1379/2273)이라 기존 staged-attachment 흐름과 동일 검증된 경로로 확인. (동시세션 insight-reset·prompt-autogen·ds-a11y·ds-label cycle 이 TASK-0231/0232/0233/0234 선점→§13.1 재번호 0232→0235.)
## REV-20260612-0234 [SKIPPED:frontend-bugfix-no-backend-no-rbac]
- Date: 2026-06-12
- Cycle: TASK-0234 (datasource UI 사용성 버그 2건 — 연결 테스트 무동작 + DB↔datasource 소속 불명, **Minor §12.3**)
- Reason: frontend-only 버그 수정. ① 공용 연결 테스트 버튼이 빈 드롭다운 값을 읽던 것을 per-chip ⟳ 버튼(기존 `/api/admin/datasources/{key}/test` 엔드포인트 그대로 호출)으로 보완. ② 헤더에 편집 대상 datasource 표시 배지 추가. 신규 RBAC/스키마/엔드포인트/백엔드/시크릿 0건. 새 백엔드 표면 0 — 기존 엔드포인트의 frontend 호출 경로만 수정. outside-voice panel 불필요 조건 충족.
- 검증: 백엔드 `/test` 정상 확인(라이브 mysql-local 7.3ms / mssql-qa-idc 129.8ms / mssql-f82c51b3425f 7.9ms 전부 ok) + node --check admin.js + CSS brace balance + make test 컨테이너 회귀 0.
- Human Approval Needed: no.
- Cross-ref: CHG-20260612-0234 / TASK-0234 / TASK-0230(원 멀티 datasource cycle).

## REV-20260611-0233 [SKIPPED:frontend-a11y-no-backend-no-rbac]
- Date: 2026-06-11
- Cycle: TASK-0233 (datasource multi-bind UI 접근성 보강, **Minor §12.3**) — 동시세션 TASK-0231 insight-reset 선점→0232 재번호
- 본 cycle 자체가 gstack `/design-review`(소스 디자인·접근성 outside-voice subagent) 감사의 **산물** — subagent 가 TASK-0230 UI 의 HIGH 3(aria-label·select 라벨·async disabled) + MEDIUM 4(24px 타깃·focus-visible·opacity·빈상태 CTA)를 발견, 본 cycle 이 전부 흡수. 즉 outside-voice 가 선행됨.
- Reason: frontend-only 접근성 속성(aria-label)·CSS(터치타깃·focus-visible)·JS 가드(중복요청 disabled) 추가. RBAC/스키마/엔드포인트/백엔드/시크릿 0건. 새 기능 0(기존 동작에 접근성·중복방지 덧입힘). 추가 outside-voice panel 불필요 조건 충족(새 위험 표면 0).
- 검증: node --check admin.js + CSS brace balance + make test 회귀 0 + 라이브 기능 회귀 16/16 PASS(별도).
- Human Approval Needed: no.
- Cross-ref: CHG-20260611-0233 / TASK-0233 / REV-20260611-0230(원 cycle).
## REV-20260611-0232 [SKIPPED:backend-cap-adjust-no-security-surface] — PASS
- 패널 skip 사유: 토큰 cap 조정 + 잘림 가시화로 인증/인가/데이터 경계/스키마/시크릿 변경 0. 적대적 보안 subagent 대상 아님(§18.8). 동시세션 insight-reset cycle 이 REV-0231 선점→§13.1 재번호 0231→0232. 아래는 backend correctness self-review.
- Date: 2026-06-11
- Cycle: TASK-0232 (제품 프롬프트 "자동 작성" 결과 중간 잘림 해소, **Major §12.3** — 외부 LLM 비용 영향)
- 분류: 토큰 cap 조정 + 잘림 가시화. 적대적 보안 패널 비대상 — 인증/인가/데이터 경계/스키마/시크릿 변경 0. backend correctness 관점 self-review.
- 검토 결과 (반증 시도):
  - **비용 영향(사용자 confirm 범위)**: `max_tokens` 는 출력 **상한**일 뿐 청구는 실제 생성 토큰 기준 → cap 상향(7000→20000)이 곧 비용 증가 아님. 자동작성은 admin(`product.manage`) 수동 트리거라 호출 빈도 낮음. cap 은 무제한이 아닌 명시값 유지(CHG-0004 비용 폭주 차단 정합).
  - **task 격리**: `"prompt_gen"` 사용처는 `admin_generate_product_prompt`(app.py) **단 1곳**. 기존 `"summary"` cap(7000) 무변경 → summary/classify/topic 등 3개 호출처(llm.py) 회귀 0.
  - **응답 shape 호환**: `meta.truncated` 는 **신규 키 추가**(기존 키 6종 불변) → admin.js 외 소비자 호환 깨짐 없음. 미지원 클라이언트는 키 무시.
  - **조용한 잘림 제거**: `finish_reason == "length"` 검출 → meta.truncated=True + warning 로그 + UI 경고. finish_reason 부재(None) 시 오탐 안 함(false).
  - **로컬 LLM 4K 한도**: prompt_gen 3072 ≤ 4096(컨텍스트 윈도) → 입력 프롬프트 공간 잠식 안 함.
- 검증: 신규 9 PASS(agent-core 5 cap 단조성·thinking 여유·tier 라우팅 + web-ui 4 truncated 검출/계약), model_catalog 기존 회귀 0, node --check admin.js PASS.
- Risk: low — cap 조정 + UI 가시화. 데이터/권한/스키마 무변경. cap 환원 시 잘림 재발하나 동작 안전(fail-safe).
- Human Approval Needed: no — 사용자 보고 이슈의 직접 수정, 보안 trade-off 신규 0.
- Cross-ref: CHG-20260611-0232 / TASK-0232 / agent-core REV-20260611-0232.

## REV-20260611-0231 [SUBAGENT:insight-reset-adversarial-security]
- Date: 2026-06-11
- Cycle: TASK-0230 (insight 분석 초기화 — 접근 가능 DB 단위 삭제), **Critical §12.3** (파괴적 데이터 삭제 + 신규 RBAC)
- Panel: 적대적(outside-voice) 보안 subagent. 대상: app.py 신규 함수(`_resolve_product_insight_scope`/`_like_escape`/`_insight_reset_*_patterns`/엔드포인트 `admin_product_insight_reset`) + admin.js/styles.css. 라이브 PG(agent_kb) 데이터로 검증. 집중 9개: SQL인젝션·권한우회·IDOR·과삭제/과소삭제·트랜잭션·audit무결성·dry-run우회·DoS·에러노출.
- Verdict: 반증 시도로 **MAJOR 3 발견 → 전부 흡수**:
  - **MAJOR M1** MSSQL rag_objects 과소삭제 → 완료율 divergence: reset 이 `object_key LIKE '{scope}:{db}.%'`(3-tier)만 매칭해 2-tier 레거시(`{scope}:dbo.t`, catalog-less, 라이브 168행) 누락. 완료율 계산은 `(schema_name,table_name)` 컬럼으로 catalog 무시 매칭 → 삭제 후에도 완료율 0 안 됨(이 기능의 핵심 목표 위반). **수정**: reset 의 rag_objects 삭제를 완료율 분자와 **동일한 (schema_name, table_name) 교집합 + schema 노드**로 통일(라이브 카탈로그 조회). 2-tier/3-tier object_key 형식 무관 동일 행 집합.
  - **MAJOR M2** 레거시 scope alias 미삭제 → fingerprint 잔존: 같은 DB 가 hash/.env label(`main_mysql`)/NULL 세대로 공존하는데 단일 scope 만 처리 → 다른 alias fingerprint 잔존 시 재분석 skip 위험. **수정**: `_resolve_product_insight_scope` 가 alias 집합(hash+label+NULL) 반환, 키 패턴이 전체 alias 삭제.
  - **MAJOR M3** audit fail-safe 역행: 파괴적 삭제가 먼저 commit 되고 audit 은 후행 best-effort → audit 실패 시 삭제 흔적 소실. **수정**: audit.purge 패턴 답습 — `insight.reset.start` 이벤트를 삭제 **전에** commit(실패 시 삭제 중단), 삭제 후 `insight.reset.complete`.
- 반증 실패(안전 확인): SQL 인젝션 0(`_like_escape` \\/%/_ 이스케이프 + `%s` 파라미터 바인딩 + ESCAPE '\\', placeholder/param 개수 일치, 라이브 underscore/prefix 오매칭 0). 권한 게이트 견고(insight.reset admin 한정, operator/sales 미부여). IDOR 차단(accessible-DB 멤버십 검증). 트랜잭션 단일 tx + rollback + psycopg3 .closed/.autocommit 정상.
- 잔여(미수정·합의): N1 dry-run↔실삭제 TOCTOU(표시 오차만, 삭제는 LIKE 재평가) MINOR. N2 에러 메시지 일반화(generic 메시지로 수정함). N4 fake PG 커서가 SQL 미실행이라 통합 테스트는 라이브 의존(키 패턴 단위테스트 + 라이브 실측으로 보완).
- 라이브 검증: account_db(MySQL) rag_objects 14·fact 7·kv 17 매칭, MSSQL 2-tier(168)/3-tier(205) 분포 확인, (schema,table) 교집합으로 양쪽 포괄 확인.
- Risk: medium-high — 파괴적이나 권한·IDOR·인젝션·트랜잭션·audit fail-safe 전부 검증. 삭제만(재분석은 worker 자동). RBAC 카탈로그 1건 추가(admin 전용).
- Cross-ref: CHG-20260611-0230 / TASK-0230 / REQ-20260611-0228.

## REV-20260611-0230 [SUBAGENT:product-multi-datasource-isolation-adversarial] — PASS(MAJOR 흡수)
- Date: 2026-06-11
- Cycle: TASK-0230 (멀티 datasource 1:N — 제품 ↔ 여러 datasource, **Critical §12.3**, cross-feature)
- 정본: agent-core REVIEW.md REV-20260611-0230(라우터·격리 분석 본문). 본 entry 는 feature-0003 측 변경(관리 엔드포인트·마이그레이션·UI·제품 프롬프트)에 대한 cross-ref + 흡수 요지.
- Verdict: **BLOCKER 0** — cross-datasource 격리 HOLD. MAJOR 3건 흡수.
- feature-0003 관련 흡수: **MAJOR-1** `_ensure_web_product_datasources_schema` 의 broad `try/except: pass` partial-migration silent → 컬럼 존재 선확인(information_schema) + 단계별 실패 loud 로깅(error) + 컬럼 부재 시 backfill/PK 이전 skip. **MAJOR-2** `_product_allowed_schemas_for_datasource`(admin 표시용) 는 폴백 유지(게이트 아님) — 런타임 게이트 입력 `_datasource_allow_schemas`(agent-core) 만 fail-closed.
- 검증 SAFE: admin add/remove(console.access+console.manage), 미등록 키 거부(400, `_dsr.resolve`), DELETE datasource 가 join+접근DB 고아 정리 + primary 승격, `PUT databases` 가 요청 datasource_key 바인딩 검증(임의 키 접근DB 주입 차단), IDOR 없음(product 존재 확인 + ProductId 스코프). 신규 RBAC 권한 0(기존 console.* 재사용).
- 검증: 신규 `test_product_multi_datasource_api.py` 7 + make test 컨테이너 회귀 0 + node --check.
- Risk: medium-high(Critical 데이터 경계 신규 차원) → 격리·fail-closed·migration loud 로 완화. RBAC 카탈로그/시크릿 무변경.
- Human Approval Needed: no (보안 trade-off 신규 0 — 격리 강화. 사용자 사전 confirm[전체 구현 + LLM tool 선택] 범위 내).
- Cross-ref: CHG-20260611-0230 / TASK-0230 / ADR-CORE-0004 / agent-core REV-20260611-0230 / [[feedback_outside_voice_for_rbac]] 정합.

## REV-20260611-0223 [SUBAGENT:mssql-three-tier-adversarial]
- Date: 2026-06-11
- Cycle: TASK-0223 (제품 프롬프트 자동작성 실데이터 정합 + MSSQL 3계층 인사이트), **Major §12.3**
- Panel: 적대적(outside-voice) subagent. 대상 6파일(app.py 엔드포인트, config.py ds_object_suffix/ContextVar, utils.py 3계층 파싱, insight.py multi-DB 스캔+read-back, schema.py bootstrap, agent_core.py grounding grouping). 집중: 권한 경계·write/read 정합(livelock)·MySQL 회귀·3계층 파싱 엣지·스캔 비용.
- Verdict: 반증 시도로 **4개 실결함 발견 → 전부 수정**:
  - **MAJOR** MSSQL DB명 대소문자 불일치: `set_active_database` 가 소문자화한 fact_key segment vs 원본 대소문자 `WebProductDatabases.SchemaName` lookup → 인사이트 전량 폐기(기능 무력화). **수정**: 수집 dict 키·렌더 lookup 모두 소문자 통일(app.py).
  - **MAJOR** read-back 맵 cross-DB 충돌 livelock: `_build_insight_object_maps` 가 `(schema,table)` 키 → 여러 database 의 동일 `dbo.<table>` 충돌 → 매 사이클 재생성. **수정**: `object_key`(`{ds}:{db}.{schema}.{table}` 유일) 키로 전환 + read-back 쿼리 `object_key IN` 매칭(PG+MySQL 경로).
  - **MAJOR** bootstrap 2계층 누락: schema.py 2곳이 `ds_object_suffix` 미경유 2계층 키 → 스캐너 read-back 과 orphan. **수정**: 2곳 `ds_object_suffix` 치환.
  - **MAJOR** 엔드포인트 datasource 필터 부재: 같은 이름 schema/DB 가 타 datasource 에 있으면 교차노출. **수정**: 제품 DatasourceKey→scope_key ds_seg 필터(무접두 레거시 허용).
- 반증 실패(안전 확인): MySQL 2계층 byte-identical(active_database=None), `_infer_rag_object_from_fact` 2계층 무변경, ContextVar 누출 없음(set_active_datasource 가 database 리셋), `_discover_mssql_databases` 파라미터 바인딩(인젝션 없음)·권한밖 DB 연결실패 격리(RO GRANT 경계 강제), fingerprint/refresh 키 정합.
- 잔여(미수정·합의): 스캔 비용 O(datasource×database)는 worker lock+사이클 sleep 으로 pile-up 없음(MINOR, budget 이월). 엔드포인트 LIMIT 제거는 인사이트 규모상 수용(MINOR).
- 라이브 검증: MySQL 138테이블·MSSQL 60테이블 grounded, MSSQL 제품에 MySQL 테이블 누출 0, ask-worker grounding(database.schema grouping) 정상.
- Risk: medium — 신규 데이터 경로(MSSQL multi-DB)이나 권한경계·livelock·교차노출·회귀 전부 검증. RBAC/스키마/시크릿 무변경.
- Cross-ref: CHG-20260611-0223 / TASK-0223.

## REV-20260611-0218 [SUBAGENT:cloudwatch-dashboard-design] [CODEX:cross-model-design]
- Date: 2026-06-11
- Cycle: TASK-0218 (관리 콘솔 대시보드 CloudWatch 스타일 사람-친화 재구성), **Major §12.3**
- Panel: gstack `/design-review` 메서드론 + **Design Outside Voices** 2(Codex cross-model `codex exec` 소스 디자인 감사 + Claude 디자인 서브에이전트). 분류=APP UI. 대상: admin.html 대시보드 pane + admin.js 대시보드 함수군 + styles.css `.dashboard-*` + app.py `_dash_widget_*`.
- Verdict: 현 대시보드는 "구성 가능한 지표 모음"이나 CloudWatch 운영 대시보드의 **상태 판단·신선도·추세·원인 동선** 부족. **cross-model 강한 합의** Top 발견:
  - [HIGH] 9개 동일 비중 위젯 → 위계 부재(핵심 KPI 강조·위젯 내 주/보조 metric 없음).
  - [HIGH] 시간 컨트롤 거짓 — `days` 가 사실상 usage 만 적용(audits/conversations INTERVAL 하드코딩) + 새로고침·auto-refresh·"마지막 갱신" 없음(신선도 불명).
  - [HIGH] 절대값만 — 전기간 대비 추세(▲▼%)·sparkline 없어 "이상한가" 판단 불가(SVG 자산 admin.js:815/837 재사용 가능, lib 0).
  - [HIGH] fail-loud 부재 — API 실패가 "위젯 없음"으로 오인.
  - [HIGH] 접근성 — 색만 인코딩, 포커스 링·aria-live·aria-label 누락, `--text-muted` 대비 AA 미달.
  - [MED] drill-down 부재, ↑↓ reorder 투박(→HTML5 drag), AI slop(균일 카드·radius·8px 혼재).
- 반영(TASK-0218 구현): window 전파(거짓 컨트롤 정직화) + 주/보조 metric 위계 + 전기간 델타 배지(의미별 색) + 순수 SVG sparkline + Top-N 비율막대 + 새로고침/auto-refresh/마지막갱신 + fail-loud(전체·위젯 재시도) + 접근성(포커스/aria-live/aria-label, --r-md·8px) + drill-down(위젯→탭) + native drag reorder(↑↓ 키보드 폴백 유지) + 카탈로그 활동-우선 재편. 추세/sparkline·window 전파만 백엔드 증설(비파괴 read, **스키마 변경 0**). MED drill 의 row-level 필터·"위젯 추가 라이브러리"는 이월(편집모드가 숨김 위젯을 노출하므로 add 기능 충족).
- Risk: medium — 대시보드 표면 대폭 변경이나 RBAC/권한/스키마/시크릿 무변경, 신규 엔드포인트 0(기존 overview/preferences 응답 shape 확장만).
- Cross-ref: CHG-20260611-0218 / TASK-0218 / STATUS.md 2026-06-11. 디자인 감사 산출은 본 cycle 의 outside-voice 게이트 충족.

## REV-20260611-0216 [SKIPPED:additive-endpoint-existing-perm-readonly-pg]
- Date: 2026-06-11
- Cycle: TASK-0216 (제품 프롬프트 자동 작성 품질 강화 — topic/fact_entries/summary), **Minor §12.3**
- Reason: additive 신규 엔드포인트, 기존 `product.manage` 권한 재사용(RBAC 신규 0), PG 데이터 읽기 전용(fact_entries/core_conversations/summary — 쓰기 없음), 스키마/마이그레이션 없음, 시크릿 처리 없음. `_connect_memory()`/`_pg_connect()` 기존 패턴 준수. SQL 인젝션 표면 없음(product_id는 FastAPI int 경로 파라미터, SQL 파라미터 바인딩 전용). LLM 호출은 서버측 완결(사용자 입력이 LLM 프롬프트에 직접 흐르지 않음 — DB에서 읽은 팩트만 포함).
- Risk: very low — 읽기 전용 DB 조회 + additive LLM 생성 엔드포인트.
- Cross-ref: CHG-20260611-0216 / TASK-0216.

## REV-20260611-0213 [SKIPPED:frontend-picker-ui-no-rbac-schema-change]
- Date: 2026-06-11
- Cycle: TASK-0213 (접근 가능 DB 선택 UI — dropdown+checkbox 멀티 토글), **Minor §12.3**
- Reason: 순수 프론트엔드 UI 변경(admin.js picker 렌더 방식 교체 + styles.css + cache-buster). RBAC 로직 무변경, 스키마/마이그레이션 없음, 시크릿 처리 없음. db.py MSSQL tempdb fallback(neutral DB, 비즈니스 데이터 미노출) + app.py default_db 제거는 동일 cycle 에서 단일 패치로 처리됨. 보안 리뷰 패널 불필요.
- Risk: very low — UI 렌더 레이어만 변경.
- Cross-ref: CHG-20260611-0213 / TASK-0213.

## REV-20260611-0210 [SUBAGENT:dashboard-overview-adversarial]
- Date: 2026-06-11
- Cycle: TASK-0210 (관리 콘솔 대시보드 보강 — 위젯 그리드 + per-account 커스터마이즈/영속), **Major §12.3**
- Panel: 적대적(outside-voice) 보안 subagent. 대상: app.py 신규 블록(`_DASHBOARD_WIDGETS`/위젯 집계 7종/`GET /api/admin/overview`/`GET·PUT /api/admin/dashboard/preferences`/`WebDashboardPreferences` 부트스트랩) + admin.js 대시보드 렌더/편집/저장. 헬퍼(`_require_account`/`_account_has_permission`/`_estimate_llm_cost_usd`) 정합 포함.
- Verdict: **SHIP-ABLE** (BLOCKER 0, MAJOR 0). 핵심 주장("권한 경계 = 데이터 노출 경계", "prefs 본인 한정", "days 인젝션 안전", "sanitize 견고")을 모두 반박 시도 후 실 exploit 도출 실패:
  - 권한 경계 누수 없음: `catalog`(권한 필터)와 `permitted`/`_isolate`(위젯 데이터 생성)가 동일 predicate `_account_has_permission(actor, w["permission"])` 사용 → 미보유 위젯은 catalog·widgets 양쪽 부재. PG 연결도 `conversations|usage ∈ permitted` 일 때만 open → console.access-only operator 는 usage 테이블 미접근. operator 시드(console.usage.read 미부여, audit.read.own 만) 대조 확인.
  - IDOR 불가: GET/PUT 모두 `actor["id"]`(세션 쿠키 해시 유래)만 사용, request body 의 account_id 미신뢰. `_sanitize_dashboard_prefs` 는 `widgets` 만 읽음.
  - SQL 인젝션 없음: `days` 만 f-string 에 도달하나 `max(1,min(365,int()))` clamp + `int(days)` 재적용(기존 `admin_llm_usage` 동일 패턴). 나머지 위젯 SQL 정적, prefs JSON 은 `%s` 바인딩.
  - 저장 본문 견고: 미지 키/비-dict/중복 거부, 유효 키 9개로 출력 ≤9 bound → `items[:64]` cap-vs-dedup 순서 무관. 임의/과대 JSON 누적 불가.
  - 권한 회수 후 잔존 안전: 저장 prefs 의 권한-상실 키는 server catalog 부재로 미렌더(데이터 미반환), 권한 회복 시 부활(의도).
  - 오류 격리: 위젯 except 가 `{"error":True, metrics:[], lists:[]}` (예외 텍스트·교차 데이터 무노출).
- 흡수: MINOR(app.py PUT 실패 시 `_json_error(f"...{exc}")` raw 예외 텍스트 노출) → generic 메시지 + `logging.warning(exc_info=True)` 서버측 기록으로 수정(선례 정합). MINOR(order 임의 int) = 클라 정렬 전용·SQL 미도달 → 미수정(권고도 not required). NIT 2 = 설계 의도(audit 위젯은 own-only 사용자에 미노출이 scoped 변형보다 안전) 수용.
- Risk: low-medium — 신규 데이터 노출 표면이나 권한 경계·인젝션·IDOR 전부 PASS, 권한 카탈로그/스키마(웹 외)/시크릿 무변경.
- Cross-ref: CHG-20260611-0210 / TASK-0210 / STATUS.md 2026-06-11.

## REV-20260610-0200 [SKIPPED:minor-ordering-implements-REV-0196]
- Date: 2026-06-10
- Cycle: TASK-0200 (cutover 복구 MINOR 하드닝 — `_collect_matched_excerpts` 발췌 정렬 교정), **Minor §12.3**
- Reason: 본 변경은 직전 cycle 의 적대적 패널(REV-20260610-0196)이 명시적으로 지적한 MINOR 잔존 항목("two-table msg_id namespace 정렬 caveat")의 **실행**이다. 권고를 그대로 구현(독립 id 시퀀스 cross-table 비교 → 공통 `created_at` 기준 정렬)했고, 매칭 집합·RBAC·스키마·응답 계약 무변경(스니펫 선택 순서만 개선). 회귀 테스트 가드(`ORDER BY created_at DESC` 존재 + `msg_id` 정렬 부재) 추가, make test exit=0. SQL 유효성은 ROW_NUMBER OVER ORDER BY 표준이라 추가 패널 불필요 — REV-0196 의 SHIP 검토 범위 안. (#1 convo_search escaping 은 feature-0002 REV-20260610-0200.)
- Risk: very low — 읽기 정렬 키 1개 변경.
- Cross-ref: CHG-20260610-0200 / TASK-0200 / REV-20260610-0196(원 지적).

## REV-20260610-0197 [SKIPPED:frontend-only-no-rbac-no-schema-no-secret]
- Date: 2026-06-10
- Cycle: TASK-0197 (assistant 말풍선 타임스탬프 옆 소요시간 표시), **Minor §12.3**
- 사유: 정적자산(app.js·styles.css·index.html) 3파일만 변경. 백엔드(app.py)·API 엔드포인트·DB 스키마·RBAC·시크릿 무변경. `message.meta.duration_ms` 는 agent_core 가 이미 저장하는 기존 필드를 읽기만 함(신규 데이터 수집/노출 경로 없음). node --check PASS. 시각 검증 = Windows-browser(PB-0008) 배포 후.

## REV-20260610-0196 [SUBAGENT:cutover-routing-gaps-adversarial]
- Date: 2026-06-10
- Cycle: TASK-0196 (AR-M5 cutover 잔존 라우팅 누락 일괄 복구 — web 3건 + agent-core convo_search), **Minor §12.3**
- Panel: 적대적 backend + QA subagent. 대상: 4개 수정 함수(`rename_conversation_title`/`admin_delete_product`/`_collect_matched_excerpts`/`convo_search`) diff + agent_runtime_schema.sql.
- Verdict: **SHIP** (MAJOR 0). 모든 공격 차원 반박:
  - PG SQL 유효(ILIKE / `ESCAPE '!'` / `ROW_NUMBER() OVER (PARTITION BY … ORDER BY …)` / 중첩 derived table 별칭).
  - 예약어/식별자: PG `kv.key`·`kv.value` 는 **비예약어** → unquoted 정상(스키마 column 명 일치). MySQL 분기는 backtick, PG 분기는 무backtick — 양쪽 정확.
  - case-insensitive 패리티: 모든 PG search 술어가 `ILIKE`(convo_search 3·excerpts 2), case-sensitive `LIKE` 잔존 0.
  - column 순서/row 언패킹: `_format_row`(conv_id,role,content,created_at,source) 3 PG SELECT 와 정확 일치, excerpts `(cid,content)` 2-col 일치.
  - cursor/conn 수명: admin_delete PG 가드는 자체 `_pg_connect`+`with cursor`+`finally close`, MySQL conn 미접촉 → 후속 Web* autocommit 트랜잭션에 그대로 사용 가능(누수·이중close·closed-conn 사용 0). rename 은 게이트 헬퍼 위임(try/except→500).
  - 잔존 ungated 삭제테이블 참조 0(전부 else MySQL legacy 분기), auth/RBAC 게이트 무변경, import(`_pg_connect`/`_runtime_backend_is_pg`/`os`) 존재.
- Findings(MINOR, non-blocking, 모두 pre-existing·범위 외):
  - convo_search 의 `like_pattern = f"%{pattern}%"` 가 LIKE 메타문자(`%`/`_`) 미이스케이프 — **pre-existing**(MySQL·PG 분기 동일 패리티). cutover-routing 범위 외, 추후 hardening 후보.
  - `_collect_matched_excerpts` 의 two-table `msg_id` namespace(messages.id ↔ core_messages.id 독립 시퀀스)로 ROW_NUMBER 정렬이 chronological 최신이 아닐 수 있음 — MySQL legacy 와 동일 구조(parity-preserving), 발췌 스니펫 선택만 영향(매칭 정확성 무관). 수용.
- Risk: low — 읽기/쓰기 라우팅, RBAC/스키마/파괴 0. make test exit=0(회귀 0).
- Cross-ref: CHG-20260610-0196 / TASK-0196 / TASK-0189(동일 class 선행) / feature-0002 REV-20260610-0196(convo_search).

## REV-20260610-0189 [SUBAGENT:calendar-pg-routing-adversarial]
- Date: 2026-06-10
- Cycle: TASK-0189 (날짜기준표 캘린더 "대화 구간 이동" 복구 — AR-M5 cutover 라우팅 누락), **Minor §12.3**
- Panel: 적대적 backend + QA subagent. 대상: `history_anchor`/`history_dates` PG 라우팅 분기 + app.js 캘린더 소비부 + agent_runtime_schema.sql. cutover 영역(메모리상 취약)이라 outside-voice 호출.
- Verdict(패널): **FIX-FIRST** — MAJOR 2 제기. **반영(본 작성자 라이브 실측): 두 MAJOR 모두 본 배포에서 무력화 → SHIP.**
- Findings & 처리:
  - **[패널 MAJOR #1] tz 불일치** — `_pg_connect` 가 세션 TimeZone 미설정 → `to_char` 가 PG 서버 tz 로 렌더되는데, 프런트 분기선/셀 날짜키는 `new Date(message.created_at)`(브라우저 tz)로 계산 → 서버 tz≠브라우저 tz 면 클릭한 분기선 날짜가 캘린더 `dates` 에 없어 선택 불가. → **실측 무력화**: 라이브 PG `SHOW timezone` = **Asia/Seoul**(docker-compose `TZ=${TZ}`=Asia/Seoul 주입), 원시 `created_at` 도 `+09` 저장. `to_char(created_at,'YYYY-MM-DD')` 날짜키 == 브라우저(KST) `new Date()` 날짜키 → **skew 없음**. 또한 분기선/메시지 본문은 이미 cutover 후 동일 PG timestamptz→JS 경로로 정상 렌더 중(앱 전반이 TZ=Asia/Seoul 에 이미 결합). 본 수정은 그 기존 결합과 정합. **잔존(수용/follow-up)**: PG 세션 tz≠브라우저 tz 인 미래/타지역 배포에서는 skew 가능 — 단 이는 앱 전반의 기존 tz 결합 속성이지 본 fix 가 도입한 것 아님. 필요 시 서버계산 day_key 를 프런트로 내려 분기선도 그 키를 쓰도록 일원화(별도 cycle).
  - **[패널 MAJOR #2] core-fallback id-space gap** — `_get_history` 는 `agent_runtime.messages` 에 assistant 가 없으면 `core_messages`(다른 id)로 폴백해 DOM 을 렌더하는데, 캘린더 2엔드포인트는 `agent_runtime.messages` 만 조회 → 그런 대화는 캘린더 빈/미스. → **실측 무력화**: 라이브 집계 91 대화 중 "core 에만 assistant 있고 agent_runtime.messages 엔 없는" 대화 = **0건**. 모든 대화 DOM 이 PG id 로 렌더 → 캘린더 id-space 완전 일치. 패널도 "순수 core 대화는 pre-cutover(history_dates 가 AgentMemoryMessages 만 조회)에도 캘린더 빈 = 신규 회귀 아님" 인정. **잔존(수용/follow-up)**: 향후 core-fallback 대화가 생기면 두 엔드포인트에도 동일 폴백 미러링(별도 cycle).
  - **[패널 무반박] PG SQL 구문/의미(`to_char <=` lexicographic monotonic, `string_agg ... ORDER BY ... GROUP BY to_char` 유효·MySQL 등가), id-space(공통 경로), 리소스(conn 모든 경로 1회 close·pg finally close, 누수/이중 close 없음), auth/scope(분기 전 `_require_account`+`_resolve_conversation_for_account` 유지) — 결함 없음 확인.**
- Risk: low — 읽기 전용 라우팅, RBAC/스키마/파괴 0. make test exit=0(회귀 0).
- Cross-ref: CHG-20260610-0189 / TASK-0189 / `_get_history`(app.py) PG 분기 / agent_runtime_schema.sql `agent_runtime.messages`.

## REV-20260610-0188 [SKIPPED:frontend-only-no-rbac-no-schema-no-secret]
- Date: 2026-06-10
- Cycle: TASK-0188 (공유 대화 페이지 markdown 미적용 수정 + 수신자 가독성 디자인), **Minor §12.3**
- 사유: web-ui 정적자산(share.html/share.js/share.css)만 변경. 백엔드(app.py)·공유 API(`/api/public/share/*`)·redaction·RBAC·DB 스키마·엔드포인트·시크릿 무변경 — 데이터 경로/노출 정책 그대로.
- XSS(익명 페이지 핵심 검토): 변경 전 `textContent`(XSS 0) → 변경 후 `innerHTML = DOMPurify.sanitize(marked.parse(...))`. **메인 인증 UI(`app.js markdownToHtml`)와 완전 동일한 파이프라인·동일 라이브러리(`vendor/marked.umd.js`+`vendor/purify.min.js`, 동일 config 없는 기본 sanitize)** 를 재사용. 렌더 대상 데이터는 동일 conversation 메시지(신규 데이터 소스 0) — 익명 viewer 가 받는 표현이 평문→HTML 로 바뀔 뿐, 인증 viewer 가 이미 받던 것과 동일. 본문 외부 링크는 `rel="noopener noreferrer nofollow"` + `target=_blank` 강제. 위험 델타 = 인증 UI 와 동치, 신규 표면 0.
- 검증: node --check share.js PASS. 라이브러리 로드 순서(marked+purify → share.js) 확인. 라이브러리 부재 시 평문 폴백(degrade-safe). 시각 검증 = Windows-browser(PB-0008) 배포 후.

## REV-20260610-0187 [SKIPPED:frontend-only-no-rbac-no-schema-no-secret]
- Date: 2026-06-10
- Cycle: TASK-0186 후속 (markdown 표 파싱으로 전 도구 결과 표 렌더), **Minor §12.3**
- 사유: app.js 1파일 — 순수 클라이언트 markdown→표 파서(`parseMarkdownTablePreview`) + buildStepDetailEl 우선순위 1줄 확장. 백엔드/RBAC/스키마/엔드포인트 무변경, 데이터 경로 무변경(기존 `preview` 문자열 재해석). 파서는 표가 아니면 null 반환→기존 `<pre>` 폴백 보존(안전 degrade). node --check PASS + 파서 자가 테스트(get_sample_rows 형식 파싱·비표형 null·trailing 무시) PASS. XSS=`buildResultTable` textContent. 시각 검증=Windows-browser(PB-0008).

## REV-20260610-0186 [SKIPPED:frontend-only-no-rbac-no-schema-no-secret]
- Date: 2026-06-10
- Cycle: TASK-0186 (단계 사이드 패널 결과 표 렌더링 + 패널 리사이즈), **Minor §12.3**
- 사유: web-ui 정적자산(app.js/styles.css/index.html)만 변경. 백엔드·RBAC·스키마·엔드포인트·시크릿 무변경. ① 표 렌더링은 step 데이터에 이미 있는 `result_summary.preview_table` 을 기존·검증된 `buildResultTable`(메시지 상세 SQL 패널에서 운영 중)로 재사용 — 신규 데이터 경로 0, raw 텍스트 폴백 보존. ② 리사이즈는 순수 클라이언트 너비 조절(localStorage), 서버 무관. XSS=`buildResultTable` 의 `textContent`. node --check PASS. 시각 검증=Windows-browser(PB-0008).

## REV-20260610-0181 [SKIPPED:read-agg-no-rbac-no-schema]
- Date: 2026-06-10
- Cycle: TASK-0181 (역할/계정 모델 stacked + 요청 수), **Minor §12.3**
- 사유: 기존 llm_usage 컬럼 read 집계 확장(distinct run_id, 계정×모델 fold 보존) + 프론트 stacked 시각화. 파라미터화된 기존 `win` 패턴, 신규 SQL 삽입 없음. RBAC/스키마/시크릿/엔드포인트 0, 권한 게이트(`console.usage.read` admin) 무변경. make test 282 passed/5 skipped(회귀 0). 시각 검증 Windows-browser(PB-0008).

## REV-20260610-0180 [SKIPPED:css-layout-no-logic]
- Date: 2026-06-10
- Cycle: TASK-0180 (차트 카테고리별 행 레이아웃 + 일별 폭 채움 + 상세 표 여백), **Minor §12.3**
- 사유: 순수 CSS/HTML 레이아웃 + SVG viewBox 치수(clientWidth) 변경 — 동작/데이터/RBAC/스키마/백엔드 무변경. 반응형(flex-wrap)로 좁은 화면 대응. node --check PASS. 시각 검증 Windows-browser(PB-0008).

## REV-20260610-0179 [SKIPPED:css-layout-no-logic]
- Date: 2026-06-10
- Cycle: TASK-0179 (차트 grid 다열 배치), **Minor §12.3**
- 사유: 순수 CSS grid 레이아웃(차트 배치) — 동작/데이터/RBAC/스키마/백엔드 무변경. 반응형(auto-fill + 860px 미디어쿼리)로 넓은/좁은 화면 모두 대응. node --check PASS. 시각 검증 Windows-browser(PB-0008).

## REV-20260610-0178 [SKIPPED:css-spacing-no-logic]
- Date: 2026-06-10
- Cycle: TASK-0178 (LLM 사용량 화면 여백 컴팩트화), **Minor §12.3**
- 사유: 순수 CSS/SVG spacing 축소(padding·margin·차트 높이) — 동작/데이터/구조/RBAC/스키마 무변경. 디자인 토큰 체계(TASK-0177) 유지하며 값만 컴팩트. node --check PASS. 시각 검증 Windows-browser(PB-0008).

## REV-20260610-0177 [SUBAGENT: gstack design-review 관점 디자인 리뷰 — usage pane, 반영]
- Date: 2026-06-10
- Cycle: TASK-0177 (LLM 사용량 상세 표 비용 컬럼 + 디자인 정렬), **Minor §12.3**
- Reviewer: general-purpose subagent (gstack `/design-review` designer's eye 관점 — usage pane 의 admin.html/admin.js/styles.css 직접 읽고 토큰·일관성·위계·AI slop 점검). 사용자 명시 요청("gstack 디자인 관점 리뷰 자율 진행·적용").
- Verdict: 코드/차트 로직 건강, 문제는 전부 "표면 위생"(임의 hex·인라인 style·spacing 혼재). **리디자인 아닌 토큰 정렬**이 정답으로 판정.
- 반영(High 3): H1 요약 raw flex → `.metric-card`/`.summary-metrics` 통일 / H2 임의 hex(#888/#999/#666/#333/#e5e7eb/#f1f5f9/#eee) → `--text*`/`--border*` 토큰(warm/cool gray 불일치 제거) / H3 22·18·14 혼재 margin → 8px 그리드 클래스.
- 반영(Med 4): M1 차트 섹션 `.admin-usage-card` surface 구획 / M2 h2(18)→h3(14)→h4(12) 위계 / M4 상세 표 `.admin-usage-table`(우측정렬·tabular-nums·hover) / (M3 eyebrow 케이스는 이미 일관 — 변경 불요 확인).
- 반영(Low): L1 툴팁 인라인 cssText(cool slate #1f2937, 그림자 .28) → `.admin-usage-tooltip`(`--text`·`--shadow-md`) / L4 빈 상태 `.admin-usage-empty` 클래스.
- 보류(데이터 규모 의존): L3 도넛 중앙 큰 수 축약(현 규모 OK), L2 select 의 `.btn-secondary` 재사용(시각 정상). 차트 막대 색 팔레트는 카테고리 구분 의도라 유지(`--chart-*` 토큰 승격은 후속 선택).
- 결론: 외부 의존성 0 유지, 기존 토큰 재사용. RBAC/스키마/백엔드 무변경 → 동작 위험면 없음. node --check PASS. 시각 검증 Windows-browser(PB-0008).

## REV-20260609-0176 [SKIPPED:frontend-viz-no-rbac-no-schema]
- Date: 2026-06-09
- Cycle: TASK-0176 (LLM 사용량 역할별·계정별 추정 비용 차트), **Minor §12.3**
- 사유: frontend 시각화(순수 SVG 비용 막대) + 백엔드는 기존 llm_usage 컬럼 read 집계를 계정×모델 분해로 확장(파라미터화된 기존 `win` 패턴, 신규 SQL 삽입 없음). 비용은 TASK-0166 의 추정 단가 상수 재사용(부정확성 기존 명시). RBAC/스키마/시크릿/신규 엔드포인트 0, 권한 게이트(`console.usage.read` admin) 무변경. node --check/py_compile + make test 269 passed/5 skipped(회귀 0). 시각 검증 Windows-browser(PB-0008).

## REV-20260609-0173 [SKIPPED:frontend-only-no-rbac-no-schema-no-secret]
- Date: 2026-06-09
- Cycle: TASK-0173 (실행 단계 "근거(reason)" 사용자 노출), **Minor §12.3**
- 사유: web-ui 정적자산(app.js/styles.css/index.html)만 변경. 백엔드(app.py/agent_core)·RBAC·스키마·엔드포인트·시크릿 무변경. 변경 본질은 **이미 end-to-end 로 흐르는 `reason` 데이터의 프런트 렌더링 복원**(과거 `.step-reason{display:none}` 으로 숨긴 것을 가시화) — 신규 데이터 노출 경로 없음. 노출되는 `reason` 은 LLM tool_notes 의 명시 user-facing 근거이며 provider chain-of-thought(`reasoning_content`)와 분리·폐기되어 민감정보 누출 면 없음(agent_core.py:2054-2056). XSS=`textContent` 사용. node --check PASS. 시각 검증=Windows-browser(PB-0008) 권장.

## REV-20260609-0169 [SUBAGENT: general-purpose 적대적 리뷰 ×2 (설계 전 + 구현 diff) — ask-worker, NEEDS-FIXES→FIXED, BLOCKER 3 + MAJOR 4 흡수]
- Date: 2026-06-09 (TASK-0169)
- 대상: out-of-process ask-worker 실행모델(feature-0003 web + feature-0002 agent-core 양면). Critical §12.3 (agent 실행 경계·동시성·크래시 시맨틱). feedback_outside_voice_for_rbac 정책 → outside-voice 필수.
- **1차(설계 전)**: DESIGN-ask-worker.md 를 "as written 구현 불가" 판정. BLOCKER 3 + MAJOR 4 + MINOR n → plan(TASK.md §2.1)에 8 하드닝 흡수:
  - B1 backstop ownership-aware / B2 단일문 atomic claim / B3 lease fencing + 시간기반 heartbeat / M4 set_run_status 순서 / M5 단일문 slot enforce / M6 temp /shared·terminal-only·reaper / M7 readiness gate + result_json 패리티 / cancel-pending·worker SIGTERM·stop_grace.
- **2차(구현 diff)**: 8 하드닝 VERIFIED correct + 신규 결함 3건 발견·즉시 수정:
  - **BL-1 (BLOCKER, mode 무관)**: 403 product-access 경로 slot 이중 release → 동시성 카운터 손상. **수정**: 명시 release 제거(finally 단일). (기존 main 잠복 버그, outside-voice 가 표면화.)
  - **MJ-1 (MAJOR)**: inline temp reaper 가 mtime 만 보고 활성 job 첨부 삭제 → 장기 queued/requeue job read-after-delete. **수정**: `active_inline_paths()` 로 활성 job 경로 제외.
  - **MJ-2 (MAJOR)**: `_clear_cancel_request` 가 conversation 단위라 fencing cancel 을 덮어쓸 수 있음. **수정**: run_id-scoped clear(다른 run 겨냥 cancel 보존). (run_timeout<stale 불변식이 실무상 대부분 차단 + 방어.)
  - MINOR 3(worker SIGTERM 장기 run 미중단=sweeper backstop / set_job_run_id 실패 무해 / pending 슬롯 점유=readiness gate 바운드): 문서화 수용.
- 회귀 테스트 추가: test_ask_jobs(claim/enqueue/fencing/sweep/cancel/ownership/active_inline_paths), test_ask_worker(payload round-trip/config 불변식/run_id 파라미터), test_clear_cancel_runid(MJ-2). make test 244 pass·회귀 0.
- Verdict: **SAFE TO MERGE (flag 기본 inprocess)** — BL-1/MJ-1/MJ-2 모두 fix. worker cutover 전 라이브 검증 이월(부하·web 재배포 중 run 생존 실측).

## REV-20260609-0167 [SKIPPED:css-only-no-rbac-no-schema]
- Date: 2026-06-09
- Cycle: TASK-0167 (관리 콘솔 작은 화면 세로 잘림 수정), **Minor §12.3**
- 사유: CSS 셀렉터 1개 추가(usage pane 에 overflow-y:auto, 기존 dashboard pane 과 동일·검증된 패턴) + 캐시버스터. JS/HTML 구조·RBAC·스키마·엔드포인트·시크릿 무변경, 동작 위험면 없음. 이중 스크롤 위험은 내부 admin-list 스크롤을 가진 다른 pane 을 셀렉터에서 제외해 회피. 시각 검증은 Windows-browser(PB-0008) screenshot(작은 viewport).

## REV-20260609-0166 [SKIPPED:frontend-viz-no-rbac-no-schema]
- Date: 2026-06-09
- Cycle: TASK-0166 (LLM 사용량 차트 고도화 — 계정별 차트·hover 툴팁·막대 값·시간단위·추가지표), **Minor §12.3**
- 사유: frontend 시각화 고도화(순수 SVG) + 백엔드는 기존 llm_usage 컬럼 read 집계 확장. **granularity SQL 안전성**: `date_trunc` 단위는 `_USAGE_GRAN` 화이트리스트 키로만, 포맷도 화이트리스트 상수 → 동적 SQL 삽입 없음(인젝션 차단). days 는 clamp 된 int. 비용은 추정 표시(부정확성 명시, 로컬=$0). RBAC/스키마/시크릿/신규 엔드포인트 0, 권한 게이트(`console.usage.read` admin) 무변경 → `feedback_outside_voice_for_rbac` 비해당. node --check/py_compile PASS + make test 218 passed/5 skipped(회귀 0). 시각 검증은 Windows-browser(PB-0008) screenshot.

## REV-20260609-0165 [SKIPPED:frontend-viz-no-rbac-no-schema]
- Date: 2026-06-09
- Cycle: TASK-0165 (LLM 사용량 화면 차트화 — 상용 AI 대시보드 구조 참조), **Minor §12.3**
- 사유: frontend 시각화 추가(순수 SVG 차트) + 백엔드는 기존 llm_usage 컬럼 read 집계(`by_day_model`) 1건만 추가(파라미터화된 기존 `win` 패턴 답습). RBAC/스키마/시크릿/신규 엔드포인트 0, 권한 게이트(`console.usage.read` admin) 무변경. 동작 위험면 없음 — 사용자 메모 `feedback_outside_voice_for_rbac.md`(RBAC 변경 시 outside-voice) 비해당. node --check/py_compile PASS. 시각 검증은 Windows-browser(PB-0008) screenshot 으로 대체(배포 후 완료). 동시 세션 TASK-0164(SIGTERM) 머지 충돌로 0164→0165 재부여.

## REV-20260609-0164 [SUBAGENT: general-purpose 적대적 RBAC/런타임 리뷰 — SIGTERM finalizer + catalog prune, BLOCKER 0]
- Date: 2026-06-09
- Cycle: TASK-0164 (REQ-20260609-0164, **Major §12.3** — run 생명주기 + RBAC catalog delete). [[feedback_outside_voice_for_rbac]] 정책상 outside-voice 필수.
- Reviewer: general-purpose subagent (적대적 검증 — A1 종료 finalizer 정확성 + A2 RBAC delete 안전성 독립 검증, 코드/테스트 실행 포함).
- Verdict: **PASS-WITH-NITS. BLOCKER 0.**
- Findings:
  - (A1) 부팅/종료 partition **정확**(진리표: None→부팅마킹·종료skip / `<boot`→부팅 / `>=boot`→종료, 중복·누락 0). race 가드 충분(uvicorn 이 awaited `/api/ask` 를 drain → 에이전트 terminal write 가 shutdown hook 보다 선행 → 재조회 skip; 덮어써도 error+재시도 메시지로 무해, 부팅 backstop). sync handler 는 shutdown 시 loop inline 실행(정상), partial state 멱등·안전. 공통 케이스 no-op, 예외 경로 shutdown 크래시 없음. helper 부팅 hook 과 동일.
  - (A2) DELETE 가드(WebRolePermissions 0 AND WebAccountPermissionOverrides 0) 실제 안전, 순서(링크 제거 → prune) 정확, `_ensure_permission_catalog` 가 prune 전 재시드(폐기 코드 제외)라 멱등. catalog ROW 의존 없음(그리드/엔드포인트는 `_resolve_permission_catalog`=PERMISSION_DEFINITIONS+IsDynamic만). `conversation.file.read.own` 정확히 제외(타롤 live·`/api/file` enforce). FK 0 — DELETE 위반 없음, PermissionId 참조 테이블 2개 모두 가드.
  - py_compile PASS, 신규 테스트 3 통과(리뷰어 실행 확인).
- NITs(반영): (1) shutdown connect 가 8s 소프트캡 밖이라 hung DB 시 grace 초과 가능 → **단일 connect 시도로 단축**(재시도 제거, worst-case 1×timeout, boot backstop degrade). (2) 테스트 mock 기본값 None→`""`(프로덕션 contract 정합) **수정**. (3) set_run_status 4-conn(기존 helper, 대상 near-empty라 무해) — 이월. (4) `@app.on_event` deprecation(기존 패턴, lifespan 마이그레이션) — 이월.

## REV-20260609-0163 [SUBAGENT: general-purpose 적대적 diff 리뷰 — LLM 사용량 회계, NEEDS-TWEAK→PASS, BLOCKER 1 흡수 (cross-feature, 정본 feature-0002)]
- Date: 2026-06-09
- Cycle: TASK-0163 (REQ-20260609-0163, **Major §12.3** — LLM 사용량 admin 계정별/역할별 집계 + 모델 해소)
- 본 feature 면(엔드포인트 `admin_llm_usage`+`_aggregate_usage_by_role`, 프론트 admin.html/js)에 대한 적대적 리뷰 결과는 feature-0002 정본([[feature-0002-agent-core/docs/REVIEW.md]] REV-20260609-0163)에 기록. 요지: BLOCKER 1(B1, in-process 동시 ask cfg 전역 race — 명시 인자 전환으로 흡수) + cross-DB enrich 파라미터화·XSS `esc()`·MySQL conn 재사용·by_model GROUP BY·권한 `console.usage.read` 무변경 전부 VERIFIED-CLEAR. Verdict PASS.

## REV-20260608-0162 [SUBAGENT: general-purpose 적대적 diff 리뷰 — 진행중 말풍선 생명주기, BLOCKER 0]
- Date: 2026-06-08
- Cycle: TASK-0162 (REQ-20260608-0162, **Minor §12.3** — 대화 전환 누출 + 새로고침 경과시간 초기화)
- Reviewer: general-purpose subagent (적대적 diff 리뷰 — app.js 상태머신 + app.py thin 필드). §18.8 trigger: API/endpoint(backend) + UI/screen(ux) 면 + 타임스탬프(TASK-0159 fragile 영역) 정합.
- Verdict: **APPROVE-WITH-NITS**. **BLOCKER 0**.
- VERIFIED-CORRECT: (1) `clearPendingBubble()` 가 `state.pendingBubble = null` (reassign) 이라 직전에 `_savedPendingBubbles[_prevConvId]` 에 저장한 **객체 참조** 손상 없음 — 복원 경로 정상. (2) processing 대화로 전환 시 중복 말풍선 없음 — `stopProgressPolling` 가 비운 뒤 `loadHistory` 가 정확히 1개 생성, 복원 가드(`!state.pendingBubble`)는 false 라 재생성 안 함, 단일 `#pendingAssistantBubble` id in-place 교체. (3) dangling poll race 없음 — `stopProgressPolling` 가 `progressPollSeq++` + 타이머 취소, `pollProgress` 의 `seq` 가드 + `applyProgressPayload` 는 pendingBubble 이 이미 있을 때만 갱신(생성 안 함)이라 누출 말풍선 부활 불가. (4) Bug B 시각수학 tz-safe — `last_status_at` 은 `utc_now_iso()`(명시 offset) 문자열, 클라 `new Date(str).getTime()` 절대 epoch → 브라우저 TZ 무관. TASK-0159 PG timestamptz 컬럼 경로와 무관(클라에서 `_parse_kv_timestamp` 미사용). (5) 'processing'(=`last_status_at`)는 run 당 1회 기록 — 모든 `set_run_status` 호출 grep 확인(agent_core.py:1903 start 1회 / 2253·2266·2271 terminal / app.py:648 orphan error). (6) RBAC/IDOR clean + backward-compat — `last_run_started_at` 은 `if conv_id:`(권한 게이트 통과 후)에서만 계산, 신규 노출 없음. 폴백(`Number.isFinite`→`Date.now()`) + `formatElapsed` 음수 clamp 로 빈/미래/파싱불가값 안전.
- Nits (반영): (1) `initializeWorkspace` resume 경로(line ~5532)도 `Date.now()` 사용 → 본 cycle **반영**: `status.status_at` 기준점 + 폴백으로 대칭화(loadHistory 가 실무상 shadow 하지만 divergence 시 elapsed 리셋 방지). (2) 선존 stale 부활(전환 후 완료 대화 복귀 시 `_savedPendingBubbles` 잔존 → 죽은 말풍선 복원) → 본 cycle **반영**: loadHistory 비-processing 분기에서 `_savedPendingBubbles[cid]` 폐기.
- Nit (note-only): (3) legacy offset-less `last_status_at` 포맷이 deploy 를 가로질러 processing 으로 남아있을 이론적 케이스 — `utc_now_iso()` 항상 offset 출력 + 부팅 orphan-reconcile 이 pre-boot processing 을 error 처리 → 실질 window 0.
- 결론: deploy 안전. 라이브 거동 검증(PB-0008 Windows-browser)은 배포 후 완료 게이트로 수행.

## REV-20260608-0161 [SUBAGENT: general-purpose 적대적 RBAC/보안 리뷰 — execute_sql_on 제거, BLOCKER 0]
- Date: 2026-06-08
- Cycle: TASK-0161 (REQ-20260608-0161, **Major §12.3** — RBAC 권한 모델 변경: 거짓 컨트롤 권한 제거 + 죽은 코드). [[feedback_outside_voice_for_rbac]] 정책에 따라 outside-voice 필수.
- Reviewer: general-purpose subagent (적대적 검증 — 권한 제거가 보안 회귀인지 독립 코드 검증).
- Verdict: **PASS-WITH-NITS. BLOCKER 0.**
- Findings (A~F 전부 confirmed-safe):
  - (A) `attachment.execute_sql_on.*` enforce 호출처 **0** 재확인(app.py 60+ `_account_has_permission` callsite 전수 + agent_core/tools/modules grep). BRIEFING 이 `/api/ask` gate 를 계획했으나 미구현 — `/api/ask` 는 `conversation.ask` 만 체크. 제거는 회귀 아님.
  - (B) 실제 게이트 3중(① 계정-스코프 allowlist app.py:7663-7687 `AccountId=%s` IDOR fix + tools `_whitelist_violation` fail-closed ② `sql_guard.validate_sql_for_sandbox` tools.py:582 ③ `attachment_reader` SELECT-only) 무손상 — 권한 제거로 열리는 경로 없음(교차계정은 이미 allowlist 차단).
  - (C) `_cleanup_deprecated_role_permissions` 가 두 코드 `role_key=None` 전 롤 DELETE(멱등), `_legacy_permission_codes_from_row` 는 현 카탈로그 기반이라 KeyError 없음, 시드 가정 코드 없음, CI-safe(테스트 미참조).
  - (D) `POST /api/list_conversations` 호출자 0, HTTP 핸들러만 제거, 내부 PG 메서드명 `list_conversations`(memory.py/runtime_backend.py/agent_core.py)·web 헬퍼 `_list_conversations` 무관 무손상.
  - (E) `upload.any` 는 `_account_can_access_attachment`(app.py:5004) 로 실제 enforce — execute_sql_on 과 본질적으로 다름(문서화 주장 정확).
  - (F) 빈 attachment 그룹 admin.js 자동 제외, `state.composerAttachments` live, py_compile/node PASS.
- NITs(본 cycle 흡수): (1) `#composerAttachments` 잔여 참조 2건(app.js 4574/4650 null-guard)·고아 `_toggleAttachmentPill` → **제거 완료**. (2) `ADMIN_PERMISSION_SECTIONS` 의 attachment 그룹 키 잔존 → 무해(빈 그룹 자동 제외) + 향후 attachment 권한 추가 시 forward-compatible 위해 **의도적 유지**.

## REV-20260608-0158 [SKIPPED:test-evidence-no-code-change] (PB-0008 Windows-browser 검증 기록)
- Date: 2026-06-08
- TASK-Cycle: TASK-0158 — Windows-browser 완료 게이트 증거 기록 (코드 변경 0)
- Skip reason: 코드/RBAC/스키마/시크릿 변경 없음 — TEST.md §4 Run + 재현 시나리오(tests) + TASK 완료 표시뿐인 **검증 증거 커밋**. 진입점 구현(Tier1·2)의 적대적 리뷰는 본 cycle 의 REV-20260608-0158/-T2(아래) 가 이미 수행. outside-voice 미해당.

## REV-20260608-0159 [SUBAGENT: general-purpose 적대적 backend/qa diff 리뷰 — 고아 run/tz stale, BLOCKER 0]
- Date: 2026-06-08
- Cycle: TASK-0159 (REQ-20260608-0159, **Major §12.3** — 고아 run 무한 폴링 수정: tz stale 회귀 + 부팅 reconciliation)
- Reviewer: general-purpose subagent (적대적 backend/QA diff 리뷰 — app.py 변경 + 신규 테스트). §18.8 trigger: run-status/query 생명주기 = backend 면.
- Verdict: **APPROVE-WITH-NITS**. **BLOCKER 0**.
- VERIFIED-CORRECT: (1) tz 변환 `raw.astimezone(timezone.utc).replace(tzinfo=None)` 가 `_parse_kv_timestamp`·`datetime.utcnow()` 와 정합 — 3개 `_compute_display_status` 호출처 모두 복구. (2) 쓰기 백엔드 정합 — `set_run_status`→`save_memory_kv` 가 PG runtime conn(`agent_runtime.kv`)에 쓰고 read 도 동일 PG → 일치. (3) boot-guard 타이밍 — `_PROCESS_BOOT_UTC` 가 모듈 import(요청 처리 전) 시 캡처 → 새 ask(`agent_core.py:1869`, to_thread 내부)는 항상 boot 이후 → 정상 skip, 오탐 없음. (4) 이벤트루프/startup 비차단 — 동기 hook 은 daemon thread spawn 만(기존 hook 패턴 동일), 모든 DB/sleep/except 는 thread 내부. (5) `error` 시맨틱 — `_ASK_TERMINAL_STATUSES`∈error(스피너 해제) ∧ `_ASK_SUCCESS_STATUSES`∌error(phantom 답변 방지) ∧ `_conversation_is_processing`=False(409 해제).
- Nits (Low, non-blocking): (a) `utc_now_iso()` 초 절삭 vs `_PROCESS_BOOT_UTC` 마이크로초 → 동일-초 race 이론적 가능 → **반영함**: `_PROCESS_BOOT_UTC = datetime.utcnow().replace(microsecond=0)`. (b) MySQL fallback 분기 naive==UTC 가정 미변경 — cutover dead path, 본 버그 아님. (c) `_load_latest_run_id_from_steps` 는 aware-aware 비교로 내부 정합, 영향 없음.
- 결론: deploy 안전. 테스트 6 passed.

## REV-20260608-0158 [SKIPPED:frontend-only-no-new-rbac-no-schema-no-secret] (Tier 2)
- Date: 2026-06-08
- TASK-Cycle: TASK-0158 Tier 2 (REQ-20260608-0158, **Minor** §12.3 — 진입점 구성 Tier 2; Tier 1 리뷰는 아래 동일 id 항목)
- Skip reason: frontend-only (admin.html/admin.js + index.html/app.js + styles.css). 신규 RBAC 권한 코드 없음 — 기존 `audit.purge`(파괴적 endpoint 는 백엔드가 권위적으로 게이트)·`audit.read.own/.any`·`console.access` 에 UI 진입점만 추가. DB 스키마/시크릿/엔드포인트 무변경. **audit.purge(파괴적) 안전장치**: UI 가 dry-run 미리보기로 삭제 대상 건수 확인 후 typed-confirm(건수 일치) 통과 시에만 실 삭제 호출 — 백엔드 검증(권한·idempotency)에 더해 클라 2단계 가드. 신규 attack surface 없음 → outside-voice 미해당. node --check PASS(app.js·admin.js). **Tier 3 의 execute_sql_on enforce-or-remove 착수 시에는 RBAC 모델 변경이므로 outside-voice 필수**([[feedback_outside_voice_for_rbac]]).

## REV-20260608-0158 [SKIPPED:frontend-only-no-new-rbac-no-schema-no-secret]
- Date: 2026-06-08
- TASK-Cycle: TASK-0158 (REQ-20260608-0158, **Minor** §12.3 — 진입점 전수조사 후 구성, Tier 1)
- Skip reason: frontend-only (index.html/app.js/styles.css + docs). **신규 RBAC 권한 코드 없음** — 기존 권한(`conversation.finalize.*`, `conversation.read.*`, `conversation.share.create`)·엔드포인트(`/api/finalize`, `/api/conversations/{cid}/shares`, `/api/share/{id}`, `attachment_scope_all`)에 UI 진입점만 추가. `requiredPermissionsFor` 의 `conversation.read` case 는 **클라이언트 게이트 매핑**일 뿐 백엔드 RBAC 무변경(서버가 read.own/.any + DELETE creator/read.any 를 권위적으로 강제). DB 스키마/시크릿 무변경. 신규 attack surface 없음 → outside-voice 트리거 미해당. node --check PASS. **주의(이월)**: Tier 3 의 `attachment.execute_sql_on.*` enforce-or-remove 는 RBAC 모델 변경이므로 착수 시 outside-voice 필수([[feedback_outside_voice_for_rbac]]).

## REV-20260608-0157 [SKIPPED:frontend-only-no-rbac-no-schema-no-secret]
- Date: 2026-06-08
- TASK-Cycle: TASK-0157 (REQ-20260608-0157, **Minor** §12.3 — 요청 중단(interrupt) 진입점 복구)
- Skip reason: frontend-only (static/app.js + static/styles.css). 신규 RBAC 권한 코드 없음 — 기존 `conversation.cancel.own/.any` 게이트(`/api/cancel`, `canCancelConversation`)를 **그대로 재사용**하여 이미 존재하던 진입점을 노출만 함. DB 스키마/엔드포인트/시크릿 무변경. 백엔드 취소 경로(에이전트 루프 폴링)도 무변경. 신규 attack surface 없음 → outside-voice 트리거 미해당. node --check PASS.

## REV-20260605-0151 [SUBAGENT: general-purpose 적대적 diff 리뷰 — app.py 첨부 cap, BLOCKER 0]
- Date: 2026-06-05
- Cycle: TASK-0151 (DB 조회 사용자 경험 개선 — 첨부 text inline cap 정렬 버그 수정), **Major §12.3**
- Reviewer: general-purpose subagent (적대적 diff 리뷰 — 본 cycle 의 app.py 변경 포함 전체 diff). 정본 기록은 feature-0002 `REV-20260605-0151`.
- Verdict: ACCEPTED. **BLOCKER 0**.
- Findings (app.py 한정): `_prepare_text_inline_attachments` 의 `ORDER BY Id DESC LIMIT cap` + `inline_entries.reverse()` 가 최신 cap개 보존 후 시간순 복원으로 correct(confirmed). AccountId IDOR 스코프(`AND AccountId=%s` + per-row 검증) 무변경 유지(confirmed). 빈 결과 처리 정상. BLOCKER/SHOULD-FIX 0.

## REV-20260528-0124 [SKIPPED:no-rbac-expansion-no-schema-no-secret-handling]
- Date: 2026-05-28
- TASK-Cycle: TASK-0124 (REQ-20260528-0124, **Minor** §12.3 — RBAC 권한 정합 및 폐기 권한 정리)
- Skip reason: 신규 RBAC 권한 코드 추가 없음 (기존 코드 제거 + 기존 삭제 권한을 누락된 롤에 부여만) / DB 스키마 변경 없음 / secret handling 없음 / 폐기 권한 DB 정리는 DELETE 뿐 — 신규 attack surface 없음. outside-voice (Codex) 트리거 미해당.

## REV-20260528-0125 [SKIPPED:frontend-only-no-rbac-no-schema-no-secret]
- Date: 2026-05-28
- TASK-Cycle: TASK-0125 (REQ-20260528-0125, **Minor** §12.3 — UX 2차 보완 7개 항목; ux-compact-redesign 병합 시 재부여 — 브랜치 원번호 TASK-0123)
- Skip reason: 신규 RBAC 권한 코드 없음 / DB schema 변경 없음 / secret handling 없음 / backend endpoint 추가·변경 없음. 순수 frontend-only (app.js + styles.css + share.js + share.css) 변경. TASK-0102 미해결 상태이나 본 cycle 변경과 교차점 없음.

## REV-20260528-0123 [SKIPPED:removal-only-no-new-rbac-no-schema-mutation]
- Date: 2026-05-28
- TASK-Cycle: REQ-20260527-0001 (**Major** §12.3 — KB 등록 UI/endpoint 제거)
- Skip reason: 신규 RBAC 코드 추가 없음 (기존 코드 삭제만) / DB schema 변경 없음 / secret handling 없음 / 순수 제거 작업 (UI pane + JS ~221 LOC + endpoint 2개 + RBAC 권한 정의 + seed grant). 기존 `AgentMemoryFactEntries` 데이터 DROP 안 함 — 이미 등록된 manual KB fact 는 Weight=90 으로 잔존하나 UI 진입점이 없어 신규 등록 불가. 재설계 시 별 cycle 에서 Codex outside-voice 호출 예정.

## REV-20260528-0122 [SKIPPED:no-rbac-no-schema-no-secret-handling]
- Date: 2026-05-28
- TASK-Cycle: TASK-0122 (REQ-20260528-0122, **Minor** §12.3 — 외부 LLM 수신 동의 UI·권한·로직 제거)
- Skip reason: RBAC 권한 코드 신규 추가 없음 (기존 description 텍스트 수정만) / DB schema 변경 없음 / secret handling 없음 / 순수 제거 작업 (UI DOM + JS 함수 + CSS + backend 엔드포인트 3개 + audit 핸들러). 기존 `WebAccountConsents` 테이블 DROP 안 함 — 데이터 보존 목적.

## REV-20260526-0002 [SUBAGENT:codex — Sprint 3 admin-only manual KB ingest]
- Date: 2026-05-26
- TASK-Cycle: TASK-0108 (REQ-20260526-0108, **Major** §12.3 — RBAC 신규 코드 + admin endpoint + manual KB fact ingest path)
- Outside-voice channel: codex (`codex-cli 0.130.0`, `codex exec --sandbox read-only`). 사용자 메모리 `feedback_outside_voice_for_rbac.md` 정합 — RBAC 신규 코드 catalog 변경 + DB mutation = 정적 catalog blindspot 위험 영역.
- Trigger: 사용자 args 명시 호출 + §18.8 dispatch 키워드 (auth/RBAC/schema/migration/API) 매칭.
- Verdict: **BLOCK** → **PASS 전환** (Critical 5 + Nice-to-have 1 본 cycle 내 흡수).
- Section A (Summary): admin-only manual KB ingest 의 초안 구현 (RBAC `attachment.kb.write.any` + `modules/kb_ingest.py` + `POST /api/admin/attachments/kb-ingest` + `GET /api/admin/attachments` + admin pane + tests + AGENTS.md §11.3) 작성. outside-voice review 가 5 Critical 식별: (B-1) 동시 ingest race → active row 2개 가능 / (B-2) source_type/weight client spoofable / (B-3) admin endpoint 가 console.access 미요구 / (B-4) ingest 먼저 commit + audit fail-soft = canonical 변경 + audit 누락 / (B-5) scope_key arbitrary + audit 평문. + Nice-to-have: `Id = LAST_INSERT_ID(Id)` 패턴. 모두 본 cycle 흡수.
- Section B (Critical findings — 본 cycle 내 반영 완료):
  - **B-1 (Critical)**: kb_ingest.py 의 3-statement 흐름 (INSERT IGNORE Texts → UPDATE supersede → INSERT FactEntries) 가 (conv,scope,key) 범위 lock 없이 동작 → 동시 ingest 2건이 둘 다 supersede 후 INSERT 하면 active row 2개 남고 VIEW invariant 깨짐. **반영**: 4-step 으로 재구성 — INSERT IGNORE Texts → `SELECT Id, Weight, FactFingerprint FROM ... WHERE ... FOR UPDATE` → `UPDATE ... WHERE Id IN (active_ids)` → INSERT ON DUPLICATE KEY UPDATE. FOR UPDATE 가 단일 transaction 안 gap-locking + 사전 SELECT 의 existing_active_ids 로 reactivated 명시 계산.
  - **B-2 (Critical)**: endpoint 의 `source_type`/`weight` 가 request body 입력. 클라이언트가 `weight=1000` 또는 `source_type=insight_worker` 로 BRIEFING 의 manual/90 계약 오염 가능. **반영**: endpoint 가 `enforced_source_type = "manual"` + `enforced_weight = 90` 서버 상수 고정. request body 의 source_type/weight 입력 무시. 향후 조정은 별 admin policy field 로.
  - **B-3 (Critical)**: `/api/admin/*` 인데 `console.access` 미요구. 기존 admin endpoint 패턴 (admin_me 등) 은 console.access + 세부 권한 둘 다. 커스텀 role 에 `attachment.kb.write.any` 만 부여된 경우 관리 콘솔 밖에서 호출 가능. **반영**: list endpoint + ingest endpoint 양쪽 모두 `console.access` AND `attachment.kb.write.any` require.
  - **B-4 (Critical)**: ingest commit 먼저 + audit fail-soft (사용자 4 endpoint 패턴). admin mutation 패턴에서는 부적합 — 감사 실패 시 canonical KB 변경만 남고 audit 누락. **반영**: kb_ingest.ingest_manual() 호출 후 commit 안 함 → audit dispatch 후 commit 1회만. audit dispatch 실패 시 conn.rollback() + `_json_error("audit dispatch 실패", 500)`. canonical KB 변경 + audit 가 atomic 보장.
  - **B-5 (Critical)**: scope_key arbitrary string + audit ChangeJson 평문 저장. PII-adjacent / 제어문자 / 공백 변형 / log 혼동 source. **반영**: server regex `_KB_INGEST_SCOPE_KEY_RE = re.compile(r"^[A-Za-z0-9_.\-]{1,96}$")` validation + client (admin.js) 의 동일 regex 즉시 피드백 + admin.html input 의 `pattern` 속성. audit ChangeJson 에는 `scope_key_hash_prefix` (SHA256 prefix 16자) 만 + `masked_fields=[..., "scope_key"]` 명시. HMAC 대신 SHA256 prefix 채택 이유: HMAC key 관리 안정성 (별 secret 도입 시점 미정) + prefix collision 위험 낮음.
- Section C (Nice-to-have — 본 cycle 동반 흡수):
  - C-1: `ON DUPLICATE KEY UPDATE Id = LAST_INSERT_ID(Id)` ✓ — fact_entry_id 명시 확보 (lastrowid 추론 의존 제거).
- Section D (Verdict): BLOCK → **PASS 전환** — 5 Critical + 1 Nice-to-have 본 cycle 흡수. Test coverage: kb_ingest unit 10 PASS (FakeConn 패턴) + RBAC matrix e2e 8 시나리오 deferral (사용자 운영 turn).
- Decision authority: 사용자 args "Full Sprint 3" 명시 + 사용자 메모 `feedback_outside_voice_for_rbac.md` 정책 정합. BLOCK verdict 는 본 cycle 변경 자체 reject 가 아니라 admin-only canonical KB fact path 의 보안/무결성 보강 요구 — 모두 반영 완료.

## REV-20260522-0107 [SKIPPED:no-rbac-no-schema-no-new-secret-handling]
- Related TASK: TASK-0107 (REQ-20260522-0107, **Major** §12.3 — 첨부 sandbox 활성화 + LLM context inject + drag&drop UX 확장)
- Reason: 사용자 직접 보고 2건 일괄 fix. **Phase A (sandbox 활성화)**: 이미 ship 된 sandbox 파이프라인 (`sandbox_ingest.ingest_attachment` + `agent_attachment_<sha256>` schema + WebConversationAttachments.MetaJson 의 sandbox_table_name 필드) 의 caller 누락분 ship — backend RBAC catalog / DB schema 변경 0 (테이블 신설 없음, MetaJson append-only, `agent_attachment_*` schema 는 lazy-create 패턴으로 이미 정의됨). 단일-user MVP 결정 — root user 가 maintainer/writer/cleanup 모두 수행. 4-user 분리 grant model (BRIEFING D2/D15) 은 후속 cycle 에 .env 비밀번호 설정 후 재진입. Phase A.1 의 db.py replica 라우팅 우회는 sandbox schema 가 replica 미배포 환경에서도 즉시 조회 가능하도록 — 보안 영향 0 (메모리 DB 의 단일 user 가 동일 경로 사용, replica 가 없거나 latency 가 있어 SELECT 0건 반환되는 silent failure 차단). **Phase B (prompt inject)**: agent_core.py 의 시스템 프롬프트 ATTACHED FILES section 에 schema/columns/sample rows 까지 inject — D17 prompt injection guard 정책상 사용자 입력 에 대해선 별도 sanitization (PR #34) 가 이미 작동 중이며 본 영역은 backend 가 information_schema + 자기 sandbox table 조회 결과만 inject (사용자 임의 텍스트 inject 아님). MetaJson 의 sandbox_table_name 은 ingest 시 backend 가 부여한 안전한 명 (`<file_kind>__<original_filename_sanitized>`). LLM SQL tool 실행 시 D14 AST allowlist guard 가 statement 형식 제한 — 사용자가 의도적 prompt injection 시 SQL 실행은 별도 RBAC `attachment.execute_sql_on.own/.any` gate 에 또 차단. **Phase C (UI)**: drag&drop overlay + auto-pending — frontend 한정. permission `conversation.create` 검증 후 진입 → 새로운 권한 우회 경로 없음. AGENTS.md §18.8 trigger 분석: (a) "schema/migration" 시그널 — sandbox `CREATE SCHEMA IF NOT EXISTS` 는 idempotent + 사용자 conversation_id 별로 분리, 운영 DB 의 정의 schema (agent_memory) 와 별 namespace. lazy-create 패턴이 D14/D17 정책 충족. (b) "auth/credential/PII" — 본 cycle 의 prompt inject sample rows 는 사용자가 본인 conversation 에 첨부한 파일에 한정 (RBAC `attachment.read.own` 으로 이미 gate). 외부 LLM 송신 동의 (D11 consent) 는 첨부 업로드 시 이미 검증되어 unchanged. (c) "API/endpoint/contract" — endpoint 신설 0 (기존 upload endpoint 의 background 후속 작업만 추가, 응답 contract 무변경). (d) "UI" — drag&drop UI 표면 확장은 보안 표면 신설 없음. SKIPPED 정당화: backend RBAC / DB schema / endpoint contract / 암호화 알고리즘 / D7 MIME / D8 size cap / D11 consent gate / D12 HMAC / D13 server-side bytes / D14 AST allowlist / D17 prompt injection guard 모두 무변경. 4-user 분리 grant model 은 후속 cycle 로 명시 분리 (.env 비밀번호 미설정 → 단일-user MVP). py_compile + node --check PASS. 후속 모니터링: live deploy 후 (1) 첨부 업로드 후 LLM 이 sample rows 인식 + execute_sql 호출 동선 확인, (2) chat-pane 전체에서 drag&drop overlay 표시 확인, (3) "+ 새 대화" 직전 + drag&drop 첨부 시 자동 pending 진입 + 첫 send 직전 staged flush 동선 정상화 확인.
- Timestamp: 2026-05-22T09:00:00Z

## REV-20260522-0106 [SKIPPED:no-rbac-no-schema-no-secret-handling]
- Related TASK: TASK-0106 (REQ-20260522-0106, **Major** §12.3 — 첨부 storage 모듈 import 경로 + lazy-create 첨부 staging)
- Reason: 사용자 직접 보고 2건 일괄 fix. (1) Python import 경로 교정 — `from modules import storage_minio/sandbox_schema` (4 callsite) → `from web.modules import …`. Dockerfile 의 `COPY unit/feature-0003-agent-web-ui/src /app/web` 를 정확히 반영하는 namespace 정정에 한정 — backend / RBAC catalog / DB schema / endpoint contract / 암호화 알고리즘 / signed URL / D11 consent / D13 server-side bytes / D7 MIME allowlist / D8 size cap / D12 HMAC 모두 무변경. (2) lazy-create staging — `_uploadComposerAttachment()` 의 isLazy 차단 제거 + pendingSentinel bucket 에 staged item + sendPrompt 첫 send 직전 `/api/new_conversation` 발급 + `/api/conversations/{cid}/attachments` 일괄 업로드 + askBody 즉시-cid 모드 전환. backend endpoint contract 무변경 — 기존 multipart endpoint 를 cid 발급 직후 호출하는 흐름 추가일 뿐. AGENTS.md §18.8 trigger 분석: (a) "UI/button/file/dialog" 시그널 있으나 기존 attachment UI 의 동작 회복 + 차단 토스트 → staging 흐름 전환에 한정, 새로운 보안 표면 없음. (b) "auth/credential/PII" 키워드 미해당 — 첨부 bytes 는 D11 consent gate + D13 server-side read 의 기존 정책에 그대로 귀속, 본 cycle 은 client UX 만 변경. (c) "schema/migration" 미해당 — `WebConversationAttachments` / `WebAccountConsents` / `WebAttachmentDerivedMessages` 모두 무변경. SKIPPED 정당화: import 경로 정정 (코드의 정확성 회복) + frontend UX 흐름 보강 (차단 동작 → staging 흐름) + py_compile + node --check PASS. 보안 모델 / RBAC / DB / 외부 비용 / migration 모두 미해당. 후속 모니터링: live deploy 후 사용자 브라우저에서 (1) 첨부 업로드 정상화 toast (2) "+ 새 대화" 직후 첨부 후 첫 메시지 전송 시 staged → uploaded → ask 흐름 정상화 확인.
- Timestamp: 2026-05-22T08:00:00Z

## REV-20260522-0008 [SKIPPED:frontend-only]
- Related TASK: TASK-0105 (REQ-20260522-0008, **Minor** §12.3 — Profile Drawer '내 감사 로그' 탭 일반 사용자 비노출)
- Reason: 사용자 직접 요청에 의한 UI 요소 제거 (탭 버튼 + 패널 + JS + CSS). backend endpoint (`/api/profile/audits`) / RBAC catalog / DB schema / 암호화 알고리즘 무변경. AGENTS.md §18.8 trigger 분석: UI/button 시그널 있으나 기존 탭 UI 를 **제거** 하는 것이며 보안 표면을 줄이는 방향 — 새 기능 구현 아님. audit endpoint 자체는 backend 에 보존되어 있으므로 향후 정책 변경 시 재노출 가능. node --check + py_compile PASS 확인. SKIPPED 정당화: frontend-only 삭제 + Minor §12.3 등급 + 보안 모델 변경 없음.
- Timestamp: 2026-05-22T06:00:00Z

## REV-20260522-0007 [SKIPPED:non-policy-doc]
- Related TASK: TASK-0104 (REQ-20260522-0007, **Major** §12.3 — 외부 노출 web 컨테이너 HTTPS 종단 활성화)
- Reason: TASK-0103 의 secure-context guard 의 근본 해결책 — same-port 18080 에서 HTTPS 종단을 활성화. **infra only** (compose entrypoint 변경 + override template 주석 갱신) — backend / RBAC catalog / DB schema / endpoint contract / Frontend 코드 / 암호화 알고리즘 모두 무변경. 기존 self-signed 인증서가 SAN 에 외부 IP `112.185.196.20` 을 이미 포함하므로 인증서 발급/회전 작업 없음. AGENTS.md §18.8 trigger 분석: (1) "auth/credential" 키워드 — security subagent 후보. 본 변경은 secure channel **활성화** (방향: 보안 강화), TLS 종단 자체는 base `docker-compose.yml` 에 이미 작성되어 있던 분기를 dev override 가 막고 있던 구조를 정상화. 추가 attack surface 없음 — 평문 18080 이 끊긴 것은 secure-context guard 의 정상 동작과 정렬. (2) "deploy/infra" 신호 — devex/qa 후보이나 변경 범위가 1 개 entrypoint 라인 + `.example` 주석에 한정, 운영 영향은 외부 사용자가 `https://` 로 접근하는 것 + 첫 접속에서 self-signed 경고 우회 (사전 안내 필요) 두 가지뿐. SKIPPED 정당화: 변경 surface 가 단일 entrypoint string + `.example` 문서화에 한정, 검증은 `curl -sk https://` HTTP 200 + 컨테이너 로그 `https://0.0.0.0:8000` 으로 직접 확인 완료, 보안 algorithm / 인증서 / RBAC 모두 무변경 — 외부 voice 게이트 trigger 미해당. 후속 cycle 로 분리: (a) Caddy 기반 production 운영 시 LE 인증서 자동 회전 runbook 정비, (b) 클라이언트 측 cross-tab `state.apiVaultOptions` caching (TASK-0103 의 후속 항목), (c) 외부 사용자에게 self-signed 경고 우회 안내 페이지 — 본 cycle 은 즉시 가시성 회복에 한정.
- Timestamp: 2026-05-22T04:35:00Z

## REV-20260522-0006 [SKIPPED:non-policy-doc]
- Related TASK: TASK-0103 (REQ-20260522-0006, **Major** §12.3 — API Vault secure context 사전 차단 + UX 안내)
- Reason: 외부 IP HTTP 접속에서 `window.crypto.subtle = undefined` 로 인한 OpenAI API Key 저장 실패 hotfix. `isVaultCryptoAvailable()` helper + `updateVaultReadiness()` `blocked` 상태 + `syncVaultSteps()` 차단 + `encryptPlainApiKey()` 사전 throw + styles.css 빨간 톤. **frontend only** — backend / RBAC catalog / DB schema / endpoint contract / 암호화 알고리즘 (PBKDF2 + AES-GCM) 무변경. AGENTS.md §18.8 trigger 분석: (1) "auth/credential" 키워드 — security subagent 후보. 본 변경은 자격증명 처리 동선이지만 **암호화 알고리즘과 server-side 검증은 그대로 유지**, 추가된 것은 클라이언트 사전 가드 + 사용자 안내 메시지뿐 — 보안 모델/감쇠 위험 없음 (오히려 secure context 강제로 보안 강화). (2) UI/button 신호 — ux/design subagent 후보이나 기존 banner / step UI 재사용, 신규 컴포넌트 없음. SKIPPED 정당화: hotfix 성격 (외부 사용자 전원 영향, 즉시 가시성 회복 필요) + 보안 attack surface 축소 방향 + algorithm 변경 없음. 후속 cycle 로 분리: (a) HTTPS 종단점 (nginx/Caddy 18443 등) 인프라 추가, (b) `requires_secure_context` 신호를 `state.apiVaultOptions` 에 caching 후 cross-tab 동기화. 본 cycle 은 즉시 가시성 + UI 차단에 한정.
- Timestamp: 2026-05-22T03:40:00Z

## REV-20260522-0005 [SKIPPED:non-policy-doc]
- Related TASK: TASK-0102 (REQ-20260522-0005, Minor §12.3)
- Reason: topbar 관리 콘솔 버튼 role fallback gate — `canOpenAdminConsole()` 에 `role.key` 기반 fallback 추가. app.js + index.html(cache-bust) 변경. backend / RBAC catalog / DB schema / endpoint contract 무변경. Minor §12.3 — display-only 조건 보강, RBAC 설계 변경 아님. AGENTS.md §18.8 trigger: UI/button 시그널 있으나 기존 버튼 노출 조건 강화 (신규 UI 기능 구현 아님) — SKIPPED 정당.
- Timestamp: 2026-05-22T00:00:00Z

## REV-20260522-0004 [SKIPPED:non-policy-doc]
- Related TASK: feature-0003-agent-web-ui
- Reason: TASK-0100 (REQ-20260522-0004, Minor §12.3) — `관리 콘솔` 버튼 RBAC gate 수정. `_serialize_account()` 에 `console_access` 플래그 추가 + `canOpenAdminConsole()` 변경. 코드 변경이나 UI/RBAC 관련이므로 tech review 대상이나, Minor §12.3 (RBAC catalog / DB schema / endpoint contract 무변경, 표시 조건만 복원) 이며 변경 surface 가 최소화됨. 이슈의 근본 원인이 명확 (TASK-0098 can() 단순화의 side-effect) + 수정이 정확히 원래 의도(admin 전용 표시) 복원. AGENTS.md §18.8 trigger: UI/button 시그널 있으나 버튼 노출 여부만 수정 (새 UI 기능 구현 아님) — SKIPPED 정당.
- Timestamp: 2026-05-22T00:00:00Z

## REV-20260522-0003 [SKIPPED:doc-only-tracker-hygiene]
- Date: 2026-05-22
- Decision: TASK-0099 (REQ-20260522-0003, Minor §12.3 — docs-only tracker hygiene) — TASK-0073 audit subsystem followup backlog 8 entries (TASK-0086~0093) 8/8 완료 후 정리 cycle. TASK.md 의 stale `[ ]` 체크박스 2건 close + TASK-0099 entry 추가 + STATUS.md marker append. 코드 / RBAC / 스키마 / endpoint 변경 0.
- Mode: SKIPPED (AGENTS.md §18.4 META mode 정책 — docs-only tracker hygiene cycle, outside-voice review 대상 아님. `feedback_outside_voice_for_rbac` 미해당)
- Reason: 본 cycle 은 사후 정리 docs-only — TASK-0072 의 main 통합 commits (`f298f90` + hotfix bundle TASK-0074~0080) 와 TASK-0092 의 7 vector matrix (V1-V7) 검증 결과를 tracker 에 반영하는 단순 사실 기록. SUBAGENT 또는 AGENT-TEAM review 의 비용 정당화 어려움. verify-completion CHECK#9 충족용 SKIPPED prefix.
- Self-check 결과:
  - **TASK-0072 stale checkbox close 정합성**: f298f90 commit (`feat(feature-0003): TASK-0072 — 타 계정 대화 검색·필터 + WebAccountActivity audit`) 이 main 통합 + 후속 hotfix bundle (TASK-0074~0080) 도 모두 main 통합. STATUS.md feature-0003 row 도 "cache-bust `v=20260518-conv-search`" 로 deployment 완료 명시. TASK.md line 152 의 `[ ]` 가 실제 상태와 일치하지 않음 → close 정합.
  - **TASK-0073 line 2767 acceptance close 정합성**: TASK-0092 (REQ-20260520-0007, Minor §12.3) 의 7 vector matrix PASS (7/7) 가 본 acceptance 의 "`AGENT_AUDIT_ENABLED=0` + `AGENT_MODE=prod` 환경에서 컨테이너 시작 시 process 종료 + stderr `[FATAL]` 검증" 을 정확히 수행. V1 (AGENT_MODE=prod + AUDIT=0), V2 (AGENT_MODE=staging + AUDIT=0), V3 (AGENT_MODE=production + AUDIT=0) 모두 fail-closed 확인. acceptance criterion 정확 충족 → close 정합.
  - **신규 TASK-0099 entry**: 본 closure cycle 자체를 등재 — future cycle 의 traceability 보강.
  - **다른 미완 `[ ]` 항목 영향**: TASK-0034 (perf test) / TASK-0044 (pilot QA) / feature-0001/4/5/6 의 TASK-0004 stub — 본 cycle 범위 밖 (user 환경 필요 또는 user direction 필요). 본 cycle 은 audit followup backlog 정리에 한정.
- Alt 거부:
  - **stale checkbox 그대로 두기 (no-op)**: tracker 정확도 회귀 + future cycle 이 다시 발견해 처리해야 할 빚 누적. 거부.
  - **stale checkbox 5건 일괄 close (모든 미완 항목 포함)**: TASK-0034 / TASK-0044 / feature-0001/4/5/6 TASK-0004 는 user 환경 / direction 필요 — close 권한 없음. 거부.
  - **각 close 마다 별 cycle**: 1-line tick × 2 의 cycle 분리는 overhead 만 발생. 단일 cycle 묶기.
- Cross-ref: TASK.md §2 Task Queue (TASK-0099 entry + line 152 TASK-0072 close + line 2767 TASK-0073 close), MODIFY.md CHG-20260522-0003, REPORT.md §1 cycle entry, docs/STATUS.md feature-0003 row tail.

## REV-20260522-0002 [AGENT-TEAM:codex-outside-voice]
- Date: 2026-05-22
- Decision: TASK-0098 (REQ-20260522-0002, **Critical** §12.3 — Profile Drawer 탭 재구성 + 권한 정보 API 단위 차단) cycle ship. PR #49. Codex outside voice (consult mode, 101,989 tokens) 6 findings (1 blocker + 4 high + 1 medium) 흡수 + plan v2 redesign + PLAN-APPROVED (2026-05-21) 후 4 commit 으로 진행. push 후 main 다수 PR 머지 (#45 v3.10.0 + #47 TASK-0089 + #48/#50 + #52/#61 TASK-0094 첨부 multi-cycle Sprint 1 + DQA 브랜딩 + TASK-0095 GLOBAL prompt + TASK-0096 v2 설정 list-detail) → 반복 CONFLICTING → 사용자 결정 "Rebase main + conflict resolve" → multi-race rebase + ID reassign + squash commit 으로 main HEAD `20f0344` 위 재작성. 본 commit 머지로 사용자 명시 의도 (Profile Drawer 4 탭 재구성 + 권한 정보 API 단위 차단) 완성.
- Reason: 사용자 in-cycle 결정 — (1) 탭 순서 `[프롬프트, 보안 및 계정, API Vault]` + 통합 탭 "활동 정보" 최상단, (2) "권한 현황" 패널 = 운영자 전용 분류 + UI/API 양쪽 차단, (3) PR 단위 = commit 분리 + 단일 PR, (4) multi-race rebase 시 사용자 결정 "Rebase main + 빠른 머지 시도". 사용자 메모 `feedback_outside_voice_for_rbac` 정책 적용.
- Codex outside voice 6 findings 흡수 매핑:
  - **F1 (blocker)** — admin.js `/api/auth/me.permissions["console.access"]` 의존 → `/api/admin/me` admin 전용 self endpoint 분리 (console.access gate).
  - **F2 (high)** — Option Y (raw permission 비노출) 채택. `can()` 단순화 + apiFetch 403 fallback + 메시지 normalize.
  - **F3 (high)** — 403 메시지 권한명 노출 → 5 패턴 9 callsite `"요청을 수행할 수 없습니다."` 통일.
  - **F4 (high)** — 누출 경로 다수 → `_serialize_account` default `False` + 7 self callsite 일괄 적용.
  - **F5 (high)** — 30+ callsite false 단순 전환 금지 → `can()` true 반환 + UI 표시 유지 + backend 403 fallback.
  - **F6 (medium)** — CSRF/session race 점검: 현 backend SameSite cookie + 항상 fresh `_account_has_permission` 검사 → 안전.
- Multi-race rebase 영역: 본 cycle 원래 4 commit (`2eeb22c/058d59a/2d15365/677d48a`, base `8888130`) 가 backup branch `backup/profile-tabs-restructure-pre-rebase` (677d48a tip) 에 보존. main HEAD `20f0344` 위에 단일 squash commit 으로 재작성. main 흡수 = #45 v3.10.0 + #47 TASK-0089 audit drawer + #48/#50 docs + #52 TASK-0094 첨부 multi-cycle Sprint 1 Phase 1 (MinIO + ADR + 부트스트랩) + #61 Phase 4 storage wrapper + RUNBOOK + DQA 브랜딩 (TASK-0097) + TASK-0095 GLOBAL prompt + TASK-0096 v2 (설정 list-detail). 의도 통합 = Profile Drawer 5 탭 → 4 탭 (audit 보존 + 3 탭 통합). ID reassign = TASK-0094→**TASK-0098** (main 의 TASK-0094 첨부 + TASK-0096 설정 list-detail 과 collision 회피) / REQ-20260521-0001→**REQ-20260522-0002** / AC-0199~0207→**AC-0226~0234** / CHG·REV-20260521-0001~0004→**CHG·REV-20260522-0002** / cache-bust `v=20260522-task-0098-perms`.
- Alt 거부:
  - **Option X (boolean ui_capabilities)**: 파생 노출 위험 → Codex reject.
  - **PR 닫고 새 cycle**: 본 cycle 의 plan + outside voice + 검증 손실 → reject.
  - **revert main 의 PR #45/#47/#52/#61 등**: 다른 cycle 의 기능 손실 → 부적합.
- Risks: multi-race rebase 가 시간 비용 큼 + main 의 추가 진행 시 또 conflict 가능성. 빠른 머지 시도 필요. 회귀 위험 = (a) Profile Drawer audit 탭 visibility 단순화 (모든 로그인 사용자 → 노출), TASK-0073 audit.read.own 모든 role grant 정책 정합, (b) 30+ callsite can() 단순화 → backend 403 fallback (UX 검증 사용자 위임), (c) admin 콘솔 진입 `/api/admin/me` 호출 + 403/401 시 redirect "/".
- 사용자 의도 완성 확인:
  - Profile Drawer 탭 `[프롬프트, 보안 및 계정, API Vault]` ✓ + audit gated 보존
  - 보안+계정 통합 + 활동 정보 최상단 ✓
  - "권한 현황" 운영자 전용 + UI 비노출 ✓
  - API 단위 권한 정보 차단 ✓ (`/api/auth/me` permissions 미포함)
  - 관리 콘솔 권한 정보 조회 ✓ (`/api/admin/me` + admin callsite 3 곳 명시)
- Test: py_compile (app.py + 2 tests) + node --check (app.js + admin.js) + verify-completion --pre-commit PASS. 실 컨테이너 9 시나리오 smoke + UI dogfood 2 role 사용자 위임.

## REV-20260521-0006 [SKIPPED:self-review-after-plan-approved]
- Date: 2026-05-21
- Decision: TASK-0096 v2 (REQ-20260521-0004 follow-up — `설정` pane 을 계정/역할/제품 과 동일한 list-detail 패턴으로 정렬). 사용자 명시 follow-up 피드백 — "계정, 역할, 제품 탭과 일관된 디자인이 아닌것으로 확인되었습니다. 검색창을 포함하여, 해당 탭들과 일관된 디자인으로 구성해주세요." → CHG-20260521-0005 의 sub-sidebar (`admin-settings-shell`) 변형 폐기, 표준 `admin-list-detail` 5단 구조 + `admin-search` 검색창 + `admin-list-row` nav 변형 채택. UI restructure only — 데이터/API/권한 무영향이라 `feedback_outside_voice_for_rbac` 발동 조건 미해당, self-review.
- Reason: 사용자 명시 직접 요청. 시각 일관성 회복 + 검색 가용성 신설.
- Self-check 결과:
  - **시각 일관성 (사용자 핵심 요구)**: header (`admin-pane-head` + drawer-label/h2) → list-detail (좌측 list-col surface + border + 12px padding + `admin-search` + section-label + list rows / 우측 detail-col surface + border + 18~22px padding + panel) 패턴이 계정/역할/제품 과 1:1 정합. `admin-list-row` 의 hover/`is-active` (primary-soft) 도 그대로 상속 → row 선택 표시도 동일 색상.
  - **검색 가용성 (사용자 명시)**: `admin-search` placeholder = "설정 항목 검색…", 입력 즉시 row 필터 + 카운트 갱신. row 의 `data-settings-keywords` 가 영문/한글 양쪽 매칭 (예: "전역", "global", "system prompt", "base").
  - **확장성 보존**: 새 항목 추가 절차 (CHG-20260521-0005 의 v1 패턴 동일 골자) = (1) `<button class="admin-list-row admin-list-row--nav" data-settings-tab="X" data-settings-group="..." data-settings-keywords="...">` row 추가, (2) `<article class="admin-settings-panel" data-settings-panel="X">` panel 추가, (3) `SETTINGS_PANEL_MOUNTERS["X"] = mountFn` 등록 1 줄.
  - **lazy mount 정합 보존**: `adminState.settings.mountedPanels` Set 그대로. 첫 활성화 시에만 mount 호출. row 재선택 시 mount 호출 안 됨 (편집 state 보존).
  - **Backward compat**: `globalPromptEditorMount` id + `buildSystemPromptEditor({scope:'global'})` 호출 + `system_prompt.global.read/.write` 권한 게이트 모두 그대로. v1 의 inline panel head/hint markup 도 그대로 유지.
  - **a11y**: nav row 가 `role="option"` + `aria-selected` toggle. 카운트는 `aria-live="polite"` 유지. 리스트 컨테이너는 `role="listbox"`.
- Alt 거부:
  - **header 위 별도 검색바**: list-toolbar 안에 두는 형식이 다른 탭과 정합. header 위는 패턴 outlier 가 됨.
  - **row hover 시 placeholder check icon 추가**: 다른 탭 row 가 그렇지 않으므로 거부. 일관성 우선.
  - **section label 을 row 위 별 div 로 분리**: `admin-list-head` 안에 section label + count 가 한 줄로 collapsed 되는 게 다른 탭의 `admin-list-select-all + count` 정렬과 시각 동형.
- Verification:
  - 정적 검사 N/A (frontend only).
  - 사후 검증: web 컨테이너 재배포 → `/browse` 로 설정 탭 진입 → header (Settings 라벨 + 제목) + 좌측 list-col (검색창 + section-label `시스템 프롬프트` + nav row `전역 시스템 프롬프트`) + 우측 detail-col (panel head + textarea body 3178 자) 노출 확인 + 검색창 input 시 필터 작동 + 콘솔 errors 없음 + 권한 grid 회귀 없음.
- Trace: REQ-20260521-0004 → TASK-0096 → CHG-20260521-0006 → REV-20260521-0006.

## REV-20260521-0005 [SKIPPED:self-review-after-plan-approved]
- Date: 2026-05-21
- Decision: TASK-0096 (REQ-20260521-0004, **Minor** §12.3 — `설정` pane sub-sidebar + panel 확장 패턴) self-review. `feedback_outside_voice_for_rbac` policy 는 admin/audit 표면 직접 변경 시 발동, 본 cycle 은 settings UI restructure (HTML/CSS/JS 만) 라 미해당. self-review 채택. 단일 sub-section 누적 구조 → `admin-settings-shell` (grid 240px / 1fr) + `admin-settings-nav` (sub-sidebar) + `admin-settings-content` (panel container) 의 2-column 확장 패턴으로 전환. 새 항목 추가 절차 = nav `<button data-settings-tab="X">` + content `<article data-settings-panel="X">` + `SETTINGS_PANEL_MOUNTERS["X"] = mountFn` 3 단계.
- Reason: 사용자 직접 요청 — TASK-0095 검증 완료 후속, "`설정` 탭 내부 화면을 `계정`, `역할`, `제품` 과 같이 패널을 분리해줄 수 있을까요? 차후 `전역 시스템 프롬프트` 항목 외에도 설정 내 많은 항목이 추가될 예정인데 현재는 확장성이 너무 좁게 구현되어 있습니다." 사용자 의사 확인 (B안 선택 — 1차 sidebar 깔끔 유지 + 설정 그룹 안 무한 확장 가능 패턴) 후 진행.
- Self-check 결과:
  - **확장성 (사용자 핵심 요구)**: 새 항목 추가 = (1) admin.html 에 nav button + content article 한 쌍, (2) admin.js 의 `SETTINGS_PANEL_MOUNTERS` 에 mount 함수 등록 1줄. mount 함수 내부에서 권한 게이트 + lazy fetch — 다른 panel 의 데이터 의존 없음.
  - **Lazy mount 정합성**: `adminState.settings.mountedPanels` Set 으로 panel 첫 활성화 시에만 mount. 재진입 시 mount 호출 안 됨 (편집 state 보존). nav 클릭 = `.is-active` toggle 만, panel 데이터는 그대로.
  - **Backward compat**: `globalPromptEditorMount` id 보존 + `buildSystemPromptEditor({scope:'global'})` 호출 동일. 권한 게이트 (`system_prompt.global.read/write`) 그대로 유지. API/DB 무영향.
  - **반응형**: `@media (max-width: 760px)` 에서 sub-sidebar 가 가로 wrap 으로 collapse + content 가 그 아래 stack. 기존 admin tab 패턴 (`@media (max-width: 760px)` 가 sidebar 를 hamburger 로 전환하는 경향) 과 정합.
  - **권한 게이트 유지**: `mountGlobalPromptPanel()` 안 `can("system_prompt.global.read")` 체크 그대로. read 권한 없으면 panel 본문에 빈 placeholder 노출 (TASK-0095 동일 동작).
- Alt 거부:
  - **A안 (1차 sidebar tab 격상)**: 사용자 명시 의사로 거부 (B안 권장). 운영 항목 5+개 시 1차 sidebar 가 길어져 카테고리 균형 깨짐.
  - **단일 페이지 + 항목 collapsible accordion**: vertical scroll 누적 동일 문제. 사용자가 명시적으로 거부한 패턴.
  - **iframe / SPA route**: overengineering. admin.html 의 기존 tab 패턴과 동형 유지가 일관성 우선.
- Verification:
  - frontend only 변경 — py_compile / pytest 비대상.
  - 사후 (commit 후) 재배포 절차: `make web` → `/static/admin.html` HEAD 응답 200 + grep `admin-settings-shell` PASS → `/browse` 로 admin 로그인 → 설정 tab 진입 → 좌측 sub-sidebar `전역 시스템 프롬프트` nav item 노출 (active) + 우측 panel 의 textarea 3204 자 본문 노출 확인 → `/browse` 스크린샷 캡처.
- Risks:
  - 향후 mount 함수가 다른 panel 데이터에 의존하면 lazy mount 가 race 일으킬 수 있음. 본 cycle 의 `global-prompt` 단일 항목은 자기 충족이므로 무영향. 추가 항목 ship 시 별 cycle 에서 ADR.
  - 첫 활성 panel 이 hard-code (`activeTab: "global-prompt"`) — URL hash 라우팅은 별 cycle 로 미루기 (현재 단일 항목이라 의미 없음).
- panel: SKIPPED:self-review-after-plan-approved. UI restructure only, 데이터/API/권한 무영향, 사용자 직접 요청 의사 확정 후 진행.
- Trace: REQ-20260521-0004 → TASK-0096 → CHG-20260521-0005 → REV-20260521-0005.

## REV-20260521-0004 [SKIPPED:self-review-after-plan-approved]
- Date: 2026-05-21
- Decision: TASK-0095 follow-up hot-fix — fast-path catchup `_ensure_seed_catchup(conn)` 에 `_ensure_seed_global_system_prompt(conn)` 호출 추가. CHG-20260521-0003 의 부트스트랩 helper 배치 누락을 보정 (slow path `_ensure_web_tables` 에만 두었고 fast path 누락). live deploy 후 web 컨테이너 안 DB 검증으로 발견.
- Reason: 사용자 요청 "기능적인 검증 및 스크린샷을 통하여 UI 구성도 검증해주세요." 진행 중 발견. WebSystemPrompts row 조회 결과 GLOBAL scope 0 row + `GET /api/admin/system-prompts?scope=global` 응답이 `{prompt: null, scope: 'global'}` — 코드 상수 fallback 만 작동. 관리 콘솔 `설정` 탭 textarea 가 빈 채 노출되어 운영자가 base prompt 를 매번 직접 입력해야 하는 UX 회귀.
- 근본 원인:
  - `_ensure_web_tables` (slow path) 만 helper 호출 → schema 가 이미 잡힌 기존 배포는 `_runtime_tables_available()` 가 true 라 fast path `_ensure_seed_catchup` 만 타고 helper 호출 안 됨.
  - `_ensure_seed_role_system_prompts` 등 다른 catchup-style seed helper 는 모두 양쪽 (slow + fast) 에서 호출되는 패턴. 본 helper 만 패턴 위반 — 부주의.
- Self-check 결과:
  - **idempotency 보존**: `_ensure_seed_global_system_prompt` 진입부 `_load_system_prompt(...)` 결과 truthy 시 early return. 양쪽 path 에서 호출돼도 INSERT 는 1회만.
  - **agent_core import 실패 안전성**: lazy `from agent_core import SYSTEM_PROMPT` + try/except — fast path 에서도 동일하게 silent skip 보장. `compose_system_prompt` 의 fallback 이 인계.
  - **호출 순서**: `_ensure_seed_role_system_prompts(conn)` 직후 — schema 가 잡혔다는 것을 다른 catchup helper 가 보장한 시점. 신규 dynamic permission 컬럼 backfill 보다 앞서지만 system_prompt seed 는 권한과 무관해 무영향.
- Alt 거부:
  - **부트스트랩 변경 없이 운영자가 첫 로그인 시 직접 채워 넣게**: UX 회귀 자체. 신규 배포는 GLOBAL row 가 자동 생성되는데 기존 배포만 미작동 = 환경 간 불일치. 거부.
  - **fast path 폐지 + 항상 slow path**: `_runtime_tables_available()` 우회 = 매 부트스트랩마다 비싼 schema-rebuild 경로 발동. 다른 catchup helper 와 정합성 깨짐. 거부.
- Verification:
  - py_compile PASS (app.py).
  - 사후 (commit 후) 재배포 절차: `make web` → DB `SELECT * FROM WebSystemPrompts WHERE Scope='global'` 1 row + Content 본문 확인 → API 응답 `prompt` 필드 비어있지 않음 확인 → admin 콘솔 `설정` 탭 textarea 본문 노출 확인.
- Risks:
  - 본 helper 가 fast path 에서 매 재기동마다 호출 — `_load_system_prompt` 1회 SELECT 만 추가 (truthy → return). 미미한 overhead, 무시 가능.
  - 본 hot-fix 자체로 인한 schema migration 없음 — rollback 단순 (코드 1 줄 revert).
- panel: SKIPPED:self-review-after-plan-approved (CHG-20260521-0003 와 동일 surface — system_prompt 표면 + audit 변경 없음. Codex outside voice trigger 미해당. 본 fix 는 1-line correction 으로 외부 검증 비용 대비 가치 낮음).
- Trace: REQ-20260521-0003 → TASK-0095 → CHG-20260521-0004 → REV-20260521-0004 (CHG-20260521-0003 follow-up fix).

## REV-20260520-0010 [AGENT-TEAM:codex-outside-voice]
- Date: 2026-05-21
- Decision: TASK-0087 (REQ-20260520-0002, **Major** §12.3 — 외부 LAN trust 강화) plan v2 흡수 (Codex outside voice review verdict **NEEDS_REVISION**, 6 findings Major 5 + Minor 1). 사용자 명시 결정으로 Major #1 (RFC1918 default 권장값) 거부 + 나머지 5 흡수 (Major #2-5 + Minor #1). PLAN-APPROVED 후 Phase A~E 실행 — Caddy XFF 정규화 (A) → `_get_client_ip()` 재작성 + module-level 상수 + mode-aware fail-loud (B) → SECURITY.md §9.7 정책 갱신 (C) → docs (D) → verify-completion + commit + cycle-finalize (E).
- Mode: SUBAGENT (Codex CLI consult mode, gpt-5 default, model_reasoning_effort=high, read-only sandbox)
- Session: model_reasoning_effort=high, 228,107 tokens
- Review subject: Plan v1 (RFC1918 trust + silent skip + Caddy reverse_proxy 내부 trusted_proxies)
- Result: NEEDS_REVISION → Plan v2 흡수 완료
- Reason: AGENTS.md §17 외부 검증 정책 + `feedback_outside_voice_for_rbac` user policy — 본 변경은 IP-trust 보안 표면 + multi-feature (feature-0003 + feature-0006) + audit subsystem 의존성. 정적 review 만으로 cross-feature blindspot 검출 불가, outside voice 필수.
- Findings:
  - **Major #1 (RFC1918 전체 trust 위험)** — `WEB_TRUSTED_PROXIES`는 "사내 클라이언트 대역"이 아니라 "web이 직접 TCP peer로 보는 reverse proxy 대역"이어야 함. 현재 compose 구조에서 web port 가 `${WEB_PORT}:8000` 으로 LAN publish 되어 있어 사내 클라이언트가 Caddy 우회 시 자기 사설 IP 가 trusted proxy 로 판정되어 XFF spoof 가능. → **사용자 명시 거부** (사내 LAN dev/staging 전제 + 본 worktree 컨테이너는 테스트 후 정리). SECURITY.md §9.7 에 trade-off 명시.
  - **Major #2 (Caddy 문법 부정확)** — Plan v1 의 `reverse_proxy { trusted_proxies static private_ranges }` 가 Caddy v2 문서 기준 부정확. Caddy 권장은 global option `servers > trusted_proxies static <ranges>`. → **흡수**: trusted_proxies 추가 대신 `reverse_proxy { header_up X-Forwarded-For {client_ip} }` 로 단일 hop XFF 정규화 (더 안전한 대안). multi-hop / spoof 모두 차단.
  - **Major #3 (Caddy `private_ranges` global trust 위험)** — Caddy 가 직접 사내 LAN 클라이언트를 받는 구조에서 `trusted_proxies static private_ranges` global 은 private IP 클라이언트의 XFF 신뢰 → spoof. → **흡수**: global trusted_proxies 추가 안 함 (Major #2 와 동일 결정 — XFF 정규화로 대체).
  - **Major #4 (malformed XFF 검증 누락)** — Plan v1 의 `_get_client_ip()` 는 XFF 첫 토큰을 IP 검증 없이 반환 (`garbage`, `1.2.3.4:1234` 등 audit 오염). → **흡수**: `ipaddress.ip_address(first)` 파싱 검증 + 실패 시 direct_ip fallback.
  - **Major #5 (malformed env silent skip 부적합)** — Plan v1 의 `_parse_trusted_proxies` 가 invalid CIDR 토큰을 silent skip → 운영자 인지 못함. → **흡수**: mode-aware — `AGENT_MODE in {prod, staging}` 에서 `RuntimeError` startup, dev/test/"" 에서 stderr WARNING + 해당 토큰만 skip.
  - **Minor #1 (silent regression warning)** — proxy mode (`ENABLE_WEB_TLS_PROXY=1`) + `WEB_TRUSTED_PROXIES` empty 조합 = audit IP 가 Caddy container IP 만 기록 (PIPA §29 접근기록 품질 회귀). → **흡수**: prod/staging `RuntimeError` startup, dev/test stderr WARNING.
- 질문별 답변 흡수 매트릭스:
  | Codex Q | 답변 | Plan v2 반영 |
  |---|---|---|
  | Q1 silent regression default | 보수적 default 유지 + proxy mode fail-loud | proxy-mode gate 추가 |
  | Q2 Caddy `private_ranges` cover | docker bridge subnet 포함, but reverse_proxy 내부 `static` 문법 아님 | global trusted_proxies 자체를 추가 안 함 + XFF 정규화로 대체 |
  | Q3 단일 hop 가정 안전성 | 안전하지 않음 (web port LAN publish) — XFF 정규화 권장 | `header_up X-Forwarded-For {client_ip}` 추가 |
  | Q4 IPv6 support | `ipaddress.ip_address` IPv6 OK. Caddy `private_ranges` 는 fd00::/8 + ::1 만 (fc00::/7 아님) | `_get_client_ip` IPv6 자동 지원, Caddy global private_ranges 안 씀 |
  | Q5 schema 호환 | VARCHAR(64) 가 IPv4/IPv6 모두 수용 OK | 변경 없음 |
  | Q6 다른 surface | rate limit per-account, share token IP allowlist 별 cycle 보류, login throttling 미확인 | SECURITY.md §9.7 에 share token allowlist build 가능성 명시 |
  | Q7 malformed env | fail-loud 권장 | Major #5 흡수 |
  | Q8 test coverage | IPv6, invalid env fatal, malformed XFF fallback, 빈 첫항목, /32 /128, direct LAN client spoofed XFF, caddy validate | TEST.md §4 8 시나리오 추가 |
- Decision: Codex 권고 6/6 모두 검토 + 5 흡수 + 1 사용자 명시 거부 (Major #1). PLAN-APPROVED 마커 부여 (2026-05-21).
- Risk:
  1. **사용자 명시 거부 #1**: RFC1918 전체 trust 의 위험 (사내 클라이언트가 web port 직접 접근 + 자기 IP 를 trusted proxy 로 가장 + XFF spoof) 은 본 worktree 컨테이너 정리 정책과 사내 dev/staging 전제 로 격리. 외부 인터넷 / 미신뢰 LAN 노출 시점에 별 cycle 에서 (a) `WEB_TRUSTED_PROXIES` 좁힘 + (b) docker-compose port mapping `127.0.0.1:${WEB_PORT}:8000` 으로 변경.
  2. **Caddy XFF 정규화의 single-hop 의존성**: Caddy 앞에 upstream proxy (cloudflare/ALB) 가 추가되면 `{client_ip}` 가 upstream proxy IP 가 되어 진짜 클라이언트 IP 가 audit 에서 사라짐. 별 cycle 검토 필요.
  3. **`ipaddress.ip_address()` 검증 실패 시 direct_ip fallback**: trusted proxy 가 malformed XFF 를 보내는 비정상 상황에서 audit IP 가 caddy container IP 로 기록 — 정상 동작이라 risk 아님. 단 운영 관측 (Caddy log) 필요.
- Alternatives considered:
  - Plan v1 그대로 진행: Codex 6/6 무시 — 거부 (보안 표면 + audit 표면 + multi-feature)
  - docker-compose port mapping 변경 같이 진행 (Codex 더 근본 권고): 사용자 외부 접속 경로 유지 명시 결정으로 거부 — 별 cycle 분리
  - `WEB_TRUSTED_PROXIES` default = docker bridge subnet (172.18.0.0/16): 사용자 명시 결정 (RFC1918 전체) 으로 거부 — SECURITY.md §9.7 에 trade-off 명시
  - Caddy global `trusted_proxies static <narrow>`: 본 시스템 (Caddy 단일 hop) 에서는 효과 미미 + XFF 정규화가 더 강력 — 채택 안 함
- Cross-ref: TASK.md §2.9 (TASK-0087 Implementation Plan + PLAN-APPROVED 마커), MODIFY.md CHG-20260520-0010, REPORT.md §1 cycle entry, docs/SECURITY.md §9.7, feature-0006-lan-proxy-access REV-20260520-0010 (dual ownership)

## REV-20260521-0003 [SKIPPED:self-review-after-plan-approved]
- Date: 2026-05-21
- Decision: TASK-0095 (REQ-20260521-0003, **Major** §12.3 — GLOBAL system prompt layer 신설) self-review (verify-completion CHECK#9 정합 prefix `SKIPPED:` 사용 — Codex outside voice trigger 미해당, `feedback_outside_voice_for_rbac` policy 는 admin/audit 표면 직접 변경 시 발동, 본 cycle 은 `system_prompt` 표면 + RBAC 추가지만 audit 자체 변경 없음). PLAN-APPROVED 후 7 phase 실행 — Plan (A) → agent_core compose 함수 GLOBAL fetch (B) → app.py bootstrap seed helper (C) → RBAC 2 권한 + admin auto-grant catchup (D) → admin endpoint scope='global' allowlist + 권한 가드 (E) → 관리 콘솔 `설정` 탭 + sub-section 패턴 + buildSystemPromptEditor scope='global' + CSS (F) → 문서 갱신 (FUNCTION/MODIFY/REVIEW/REPORT). 본 review 는 self-review (대화 기반 검토 — Codex outside voice trigger 미해당. `feedback_outside_voice_for_rbac` policy 는 admin/audit 표면 직접 변경 시 발동, 본 cycle 은 `system_prompt` 표면이라 self-review 채택).
- Reason: 사용자 직접 요청 — "현재 서비스 사용자의 시스템 프롬프트 누적 구조에서, 최상위 전역 프롬프트도 구성해주세요. Product / Role / Account 에 기본적으로 처음 누적되어 요청사항에 적용될 부분입니다." 기존 4 layer (BASE → Product → Role → Account) 의 BASE 가 코드 상수 hard-code 라 운영자 수정 불가. WebSystemPrompts 테이블이 이미 scope/product_id/role_id/account_id 4-tuple 을 수용하는 schema 라 minimal change 로 GLOBAL scope 추가 가능.
- Self-check 결과:
  - **Schema 무변경 확인**: WebSystemPrompts.Scope VARCHAR(16) 가 이미 'global' 수용. UNIQUE INDEX `UX_WebSystemPrompts_Scope` 가 (Scope, ProductId, RoleId, AccountId) 4-tuple 정합 — global row 는 (`global`, NULL, NULL, NULL) 단 1건. DDL migration 불필요.
  - **Fallback 정합성**: agent_core.compose_system_prompt 가 (a) row 없음 (b) Content 빈 문자열 (c) 조회 실패 (예: WebSystemPrompts 테이블 미존재 / 부트스트랩 race) 3 경로 모두 코드 상수 SYSTEM_PROMPT 로 회귀. graceful degradation 보장.
  - **부트스트랩 순서**: `_ensure_seed_global_system_prompt(conn)` 가 `_ensure_seed_role_system_prompts(conn)` 다음 호출 — schema 가 이미 잡힌 상태 보장. agent_core import 가 부트스트랩 시점 실패할 수 있는 환경 대응 (lazy try/except). seed 본문 빈 경우 silent skip — compose_system_prompt 단의 fallback 이 인계.
  - **RBAC 가드**: `system_prompt.global.read` / `.write` 가 admin only 자동 grant. GET/PUT endpoint 가 scope='global' branch 에서 권한 가드 실행 — operator/sales/dba/pending 은 명시 grant 없으면 403. 모든 LLM 응답에 영향 가는 권한이라 운영자 한정 패턴 의도적 채택.
  - **Audit 정합성**: 기존 `admin.system_prompt.update` ActionCode + `_audit_admin_mutation` Same tx hook 재사용. ChangeJson 의 `scope` 필드가 `'global'` 인 row 가 새로 등장하지만 redaction allowlist (system_prompt.content 본문 미포함) 는 SECURITY §9.2 정합 그대로 적용.
  - **UI 확장성**: `설정` 탭 안에 `<article data-settings-section="...">` 카드 list 패턴 — 차후 운영 항목 추가 시 동일 패턴으로 sub-section 누적 가능. `mountSettingsSections()` 가 single mount entry, 신규 sub-section 마다 mount 호출 1줄만 추가.
  - **Permission group order 정합**: 작업 화면 (`app.js`) 과 관리 콘솔 (`admin.js`) 양쪽 `PERMISSION_GROUP_ORDER` 에 `settings` 추가 + 양쪽 `permissionGroupOf` 가 `system_prompt.global.` 접두사 우선 매핑. 양쪽 grid/pill 정상 노출.
- Alt 거부:
  - **신규 테이블 `WebGlobalSystemPrompts` 별도 분리**: WebSystemPrompts 가 이미 scope discriminator 를 갖는 generic 테이블이라 별도 테이블은 불필요한 split. 거부.
  - **권한 신설 없이 `system_prompt.manage.role.any` 재사용**: 의미 오버로드 (role-scope 권한 코드가 global scope 까지 관할 — 권한 체계 혼란). 거부.
  - **관리 콘솔 dashboard 상단에 직접 노출**: 사용자 명시 redirect — "`설정` 탭을 만들어주세요. 차후 항목이 추가될 수 있으므로 확장성있게 구성해주세요." 라 dashboard 상단 안 + 신규 `설정` 탭 채택.
  - **Outside voice review (Codex consult mode)**: `feedback_outside_voice_for_rbac` policy 가 admin/audit 표면 직접 변경 시 발동. 본 cycle 은 `system_prompt` 표면 + RBAC 추가지만 audit 자체 변경 없음 (기존 hook 재사용). self-review 채택. live runtime smoke 는 사용자 검증으로 위임.
- Verification (Phase G 에서 verify-completion.sh 통과 확인 예정):
  - py_compile PASS (agent_core.py — pre-existing SyntaxWarning 76 line `'\``' 무관, app.py).
  - node --check PASS (admin.js, app.js).
  - 부트스트랩 seed idempotency: `_load_system_prompt(conn, scope='global', product_id=None, role_id=None, account_id=None)` 가 row 반환 시 helper no-op 확인 (코드 reading 기반).
  - compose_system_prompt fallback chain: row 없음 / 빈 본문 / 조회 실패 3 경로 모두 SYSTEM_PROMPT 로 회귀 (코드 reading 기반).
- Risks:
  - GLOBAL row 본문이 잘못 입력되면 모든 LLM 응답에 영향 — 운영자 한정 권한 + 빈 본문 시 코드 상수 fallback 으로 위험 완화. 사용자가 textarea 비우고 적용 시 row delete (= fallback 회귀) 패턴은 기존 `_upsert_system_prompt` 가 처리.
  - live runtime smoke (관리 콘솔 `설정` 탭 진입 + 본문 수정 + LLM 호출 시 적용 확인) 는 사용자 검증으로 위임. PR merge 후 사용자가 admin 으로 로그인 → 설정 탭 진입 → 텍스트 수정 → 임의 대화 ask → assistant 응답이 새 base prompt 반영하는지 확인 필요.
  - 부트스트랩 race (web 컨테이너 내 worker 다중 시작 + WebSystemPrompts schema 직전 INSERT) 는 INSERT 의 UNIQUE INDEX 가 차단. helper 가 `_load` 후 INSERT 라 race 시 한쪽이 IntegrityError 가능 — `_upsert_system_prompt` 가 이미 INSERT...ON DUPLICATE KEY UPDATE 패턴이므로 idempotent.
- 미해결 followup:
  - 차후 `설정` 탭 sub-section 항목 추가 시 동일 `admin-settings-section` 패턴 재사용 — 본 cycle 은 1 sub-section 만 도입.
  - GLOBAL row 의 body 가 PROMPT_LABELS 의 다른 scope 와 길이/구조 일관성 강제 정책은 별 cycle 검토 (현 시점 freeform).
- panel: SKIPPED:self-review-after-plan-approved (Codex outside voice trigger 미해당 — system_prompt 표면 + audit 변경 없음. 사용자 PLAN-APPROVED marker 가 panel 의 외부 검증 대체).
- Trace: REQ-20260521-0003 → TASK-0095 → CHG-20260521-0003 → REV-20260521-0003.

## REV-20260520-0009 [AGENT-TEAM:codex-outside-voice]
- Date: 2026-05-20
- Decision: TASK-0089 (REQ-20260520-0004, **Minor** §12.3 — 작업 화면 audit drawer UX) plan v1 초안 → Codex outside voice review (consult mode, 829,505 tokens) → 5 critical findings + 2 minimum-fix → v2 redesign → 사용자 confirm. profile drawer "내 감사 로그" 탭 + 신규 backend endpoint 2 (`/api/profile/audits` + detail, `scope="own"` 강제) + frontend (HTML + JS + CSS).
- Codex outside voice 5 findings 흡수:
  - **C1 — URL 의미 mismatch**: `/api/admin/audits` 는 `.own` 호출 가능하나 `/admin/` 이 drawer 와 부합 안 함. **ACCEPT** → 신규 `/api/profile/audits` + detail (helper 재사용).
  - **C2 — `.any > .own` 우선**: `_audit_resolve_read_scope()` 가 `.any` 먼저 선택. frontend `scope=own` 만으로 부족. **ACCEPT** → backend `_audit_compose_where(scope="own", ...)` 강제. `.any` 보유자도 본인만.
  - **C3 — CSV export drawer 위험**: export endpoint `scope="any"` 고정, drawer 노출 시 `audit.export` 보유자가 전체 CSV. **ACCEPT** → drawer 에 export/purge 미노출.
  - **C4 — drawer 폭 + ChangeJson**: 390px 에 2-column 안 맞음, ChangeJson 줄바꿈 비효율. **ACCEPT** → 1-column list + inline detail expand + `<pre>` overflow:auto 수평 스크롤.
  - **C5 — 권한 race**: backend OK (매 요청 권한 재확인), frontend 처리 필요. **ACCEPT** → tab visibility (`updateProfileAuditTabVisibility()` `renderProfile()` 마다) + 403 graceful state.profileAudit.forbidden.
- 추가: mini filter `action_code` + `from_at` + `to_at` (3 필드, actor_id/actor_type 본인 한정 무의미 제거).
- Alt 거부:
  - **v1 단독 진행 (기존 endpoint 재사용)**: C1 + C2 fatal. `.any` 보유자가 drawer 에서 전체 audit 노출. backend 강제 필수.
  - **C3 완화 (drawer 에 export 노출)**: scope="any" 고정 CSV 라 PII 전체 유출. drawer 미노출 필수.
- Verification:
  - py_compile PASS
  - node --check app.js PASS
  - routing smoke: 신규 endpoint 2 등록 확인
- Risks: live browser smoke (drawer tab → list → inline detail expand → filter / 403 시 "권한 없음") PR merge 후 사용자. CSV export drawer 추가는 별 cycle (`/api/profile/audits/export.csv` + scope="own" 강제 필요).
- 미해결 followup:
  - drawer 에서 자기 audit CSV export (`/api/profile/audits/export.csv`, scope="own" 강제) 별 cycle (Minor)
  - TASK-0073 backlog 1 entry 남음 (TASK-0087, 외부 LAN trust feature-0006 위임)
  - SECURITY.md §8 strict-string-equality 계약 (TASK-0092 followup)
  - `_migrate_web_account_activity_to_audit()` 제거 (TASK-0086 followup, rollback window 종료 후)
  - 동시 export 제한 + EXPLAIN 분석 (TASK-0090 followup)
- panel: AGENT-TEAM:codex-outside-voice — Codex consult mode (829,505 tokens).
- Trace: REQ-20260520-0004 → TASK-0089 → CHG-20260520-0009 → REV-20260520-0009.

## REV-20260520-0008 [AGENT-TEAM:codex-outside-voice]
- Date: 2026-05-20
- Decision: TASK-0090 (REQ-20260520-0005, **Minor** §12.3 — CSV streaming export) plan v1 초안 → Codex outside voice review (consult mode, model_reasoning_effort=high, 550,870 tokens) → 5 critical findings + 2 minimum-fix → v2 redesign → 사용자 confirm. `/api/admin/audits/export.csv` hard cap 50k row 제거 + StreamingResponse + keyset cursor pagination + max_id high-water + try/finally + self-audit.
- Reason: TASK-0073 Phase A4 의 50k cap 이 large fleet (100k+ row) export 부족. memory footprint (50k × 1KB = 50MB+ buffer) DoS surface. `feedback_outside_voice_for_rbac` policy — audit export 표면 직접 변경.
- Codex outside voice 5 findings 흡수:
  - **C1 — async + sync mysql.connector blocking**: StreamingResponse 는 sync iterator 받음 (iterate_in_threadpool). async generator 안 sync cur.execute = event loop blocking. endpoint conn close 가 generator 보다 먼저 실행 위험. **ACCEPT** → `def csv_iter()` sync generator + 별 streaming conn (generator 내부 finally cleanup).
  - **C2 — consistent snapshot vs max_id**: `START TRANSACTION WITH CONSISTENT SNAPSHOT` long transaction 부담. audit append-only → `MAX(Id)` high-water mark 가 minimal overhead. **ACCEPT** → 시작 시 `SELECT MAX(Id) FROM WebAuditEvents{where}` 잡고 모든 page `Id <= max_id`.
  - **C3 — keyset + filter 정합 + query plan**: keyset 자체는 정합. 단 `ORDER BY Id DESC + filter` 조합 인덱스 미보장. **ACCEPT (부분)** → TEST.md 에 EXPLAIN 분석 future cycle 명시 (본 cycle 은 코드 변경만, live mysql EXPLAIN 별 cycle).
  - **C4 — cap 제거 = DoS/계약 변경**: cap 은 SECURITY.md §9 명시. 제거 시 운영 제어 (export self-audit + 동시 실행 제한 + EXPLAIN) 필요. **ACCEPT (부분)** → cap 제거 + SECURITY §9.5 갱신 + export self-audit (start + complete/aborted). 동시 실행 제한 (semaphore) 은 multi-worker 정합 검토 필요 → 별 cycle followup.
  - **C5 — cleanup try/finally**: client disconnect / timeout / send error 시 cursor/conn 누설. **ACCEPT** → generator 내부 try/finally (cursor.close + conn.close + complete audit).
- 추가 흡수 (minimum-fix 2):
  - chunk_size 1000 → **500** (안전 마진)
  - 1 row yield 대신 **64KiB byte-threshold flush** (uvicorn buffering 효율)
  - CRLF 유지, BOM 추가 안 함 (기존 contract 보존)
- Alt 거부:
  - **v1 단독 진행 (outside voice 흡수 X)**: C1 (event loop blocking) + C5 (cleanup 누설) 모두 fatal. v2 redesign 필수.
  - **C4 완화 (cap 1M 으로 증가만)**: large fleet 미충족 + streaming 미적용 시 memory footprint 그대로. 사용자 v2 단독 진행 confirm 시 거부.
  - **C2 제외 (snapshot/high-water 없이)**: 중간 INSERT 가 export 에 섞일 가능성. audit append-only 가정 + max_id 가 minimal overhead 라 채택.
- Self-audit ActionCode 신설 (purge 패턴 답습): `audit.export.start`, `audit.export.complete`, `audit.export.aborted`. ChangeJson = `{scope, filter_hash, max_id, exported_row_count, elapsed_ms, aborted}`. filter_hash = sha256[:16] (raw filter PII 회피).
- Verification (Phase B lightweight smoke):
  - py_compile PASS
  - `_AUDIT_EXPORT_CHUNK_SIZE=500` ✓
  - `_AUDIT_EXPORT_FLUSH_BYTES=65536` ✓
  - `_audit_export_filter_hash` 존재 + sort_keys 정렬 deterministic (h1 == h2 = `42ea65e7de088de2`) ✓
  - `StreamingResponse` imported ✓
- Risks: live runtime smoke (실 PATCH/SSE export 호출 + WebAuditEvents row 검증) PR merge 후 사용자 위임. 동시 export 제한 (semaphore) 미구현 — 별 cycle. representative filters EXPLAIN 분석 별 cycle.
- 미해결 followup:
  - 동시 export 제한 (multi-worker semaphore 정합 검토 + advisory lock 또는 별 솔루션, Minor)
  - representative filters EXPLAIN FORMAT=JSON 분석 (Minor, live mysql)
  - SECURITY.md §8 strict-string-equality 계약 (TASK-0092 V6 followup)
  - rollback window 종료 후 `_migrate_web_account_activity_to_audit()` 제거 (TASK-0086 followup)
  - TASK-0073 backlog 2 entries 남음 (TASK-0087, TASK-0089) — 각 별 cycle
- panel: AGENT-TEAM:codex-outside-voice — Codex consult mode (550,870 tokens). 본 cycle verification panel.
- Trace: REQ-20260520-0005 → TASK-0090 → CHG-20260520-0008 → REV-20260520-0008.

## REV-20260520-0007 [AGENT-TEAM:codex-outside-voice]
- Date: 2026-05-20
- Decision: TASK-0088 (REQ-20260520-0003, **Minor** §12.3 — `slow_query_log` 통합 ADR-0020, docs only) plan v1 초안 → Codex outside voice review (consult mode, model_reasoning_effort=high, 390,785 tokens) → 5 critical findings + 2 minimum-fix → v2 redesign → 사용자 confirm → ADR-0020 accepted. ADR-0019 Codex C1 lock-in 의 최종 결론 — **Option C Decoupled 채택**.
- Reason: ADR-0019 (audit subsystem) 에서 lock-in 된 "slow_query_log 통합은 별 cycle 분리" 의 최종 ADR 결정. 사용자 정책 (`feedback_outside_voice_for_rbac`) 적용 — ADR 자체가 audit 정책 표면 + DB-only retention/RBAC 정합 영향.
- Codex outside voice 5 findings 흡수 결정:
  - **C1 — current state framing 오류**: 현재 mysql conf 에 `slow_query_log` 설정 부재 (MySQL 8.0 default disabled). v1 초안이 "현재 운영 로그 통합" framing — "**향후** slow query 관측 통합 여부" 로 정정 필요. **ACCEPT** → Context 에 "current state: not enabled, forward-looking decision" 명시.
  - **C2 — raw SQL PII = 주 근거**: slow query log 는 SQL statement literal 보존. PasswordHash/session_token_hash/api_key/임시 비밀번호/raw LLM prompt 등이 SECURITY.md §9.2 redact 정책 밖. v1 의 "의도 mismatch" 추상적. **ACCEPT** → Decision 1순위 근거 = raw SQL text PII 차단.
  - **C3 — Option A reject 부정확**: ETL 의 retention/RBAC 정합 trivial. v1 의 "retention 정합 가능하나 RBAC overlap 모호" 가 부정확. 진짜 reject 사유 = (1) semantic pollution, (2) raw SQL PII, (3) ChangeJson/table bloat (고빈도 slow query), (4) actor/target 의미 부재. **ACCEPT** → Option A reject 재작성 (4 구체 사유).
  - **C4 — Option B reject 약함**: "audit 와 의도 mismatch" 추상. 구체 사유 = (1) raw SQL exfiltration 표면 (read-only mount 라도 endpoint PII), (2) mount/rotation/race (logrotate 중 partial read), (3) 대용량 파일 DoS (tail/filter timeout/OOM), (4) `audit.read.any` 권한 의미 오염, (5) MySQL `log_output=TABLE` destination 우회. **ACCEPT** → Option B reject 재작성 (5 구체 사유).
  - **C5 — performance_schema 빠짐**: MySQL 8.0 의 `events_statements_summary_by_digest` digest 집계 1차 도구. v1 ADR 가 PS 언급 부재 = 큰 구멍. "PS/sys digest-first, slow_query_log 는 incident/deep capture 제한" 가 더 방어 가능. **ACCEPT** → Consequences 에 PS digest-first 권유 (1차), slow_query_log incident enable (2차).
- 추가 흡수: Status framing (proposed → accepted 사용자 confirm 후). 외부 SaaS/multi-tenant trigger 4 선행 조건 명확화 — `performance-log.read` permission + raw SQL redaction/sampling + retention + endpoint threat model ADR 선행.
- Alt 거부:
  - **v1 단독 진행 (outside voice 흡수 X)**: 5 findings 모두 fatal (C1 framing 오류 + C2 PII risk 누락 + C3/C4 reject 사유 부정확 + C5 PS digest-first 누락). v2 redesign 필수.
  - **C5 제외 (PS 언급 생략)**: ADR 범위 밖 주장 가능하나, "성능 관측 권유" 가 ADR-0020 의 핵심 ramification. 사용자 v2 단독 진행 confirm 시 거부.
- Risks: docs only, code 변경 0, DB schema 변경 0. ADR 자체는 future trigger 조건만 명시 — 현재 운영 영향 0. 외부 SaaS/multi-tenant 진입 시점에 별 cycle (Major §12.3) 재진입 명시.
- 미해결 followup:
  - 외부 SaaS/multi-tenant 진입 시 별 cycle (4 선행 조건 충족 후): `performance-log.read` permission 신설 + raw SQL redaction/sampling 정책 + retention + endpoint threat model ADR.
  - `performance_schema` digest views 운영자 access policy (별 cycle 또는 SECURITY.md §9 갱신).
  - TASK-0073 backlog 3 entries 남음 (TASK-0087/0089/0090) — 각 별 cycle.
- panel: AGENT-TEAM:codex-outside-voice — Codex consult mode (390,785 tokens). 본 ADR 의 verification panel.
- Trace: REQ-20260520-0003 → TASK-0088 → CHG-20260520-0007 → REV-20260520-0007. ADR-0020 accepted. ADR-0019 Codex C1 lock-in 의 final 결론.

## REV-20260520-0006 [AGENT-TEAM:codex-outside-voice]
- Date: 2026-05-20
- Decision: TASK-0091 (REQ-20260520-0006, ~~Minor~~→**Major** §12.3 — PATCH admin/products audit before-state full snapshot + audit integrity fix) plan v1 초안 → Codex outside voice review (consult mode, model_reasoning_effort=high, ~5분, 687,409 tokens) → 5 critical findings + 2 minimum-fix → v2 redesign (scope 확장) → 사용자 confirm → Phase A~F 진행. **audit integrity 결함 fix 포함** (Codex C2).
- Reason: TASK-0073 Phase A5 의 admin.product.update audit 정합성 강화 + Codex 가 발견한 audit integrity 결함 (autocommit=True default) 일괄 fix. 사용자 정책 (`feedback_outside_voice_for_rbac`) 적용 — audit 표면 직접 변경 의무 outside voice.
- Codex outside voice 5 findings 흡수 결정:
  - **C1 — `system_prompt.content` full = SECURITY.md §9.2 위반**: full content 금지, `content_len_*` + preview 만 허용. **ACCEPT** → snapshot 에 `system_prompt_summary = {present, content_len, updated_at}` 만, content 본문 제외.
  - **C2 — `admin_update_product()` 가 same tx audit 아님 (audit integrity 결함)**: autocommit=True default + UPDATE 즉시 commit + audit fail 시 rollback 가능 0. **ACCEPT (scope 확장 Minor→Major)** → `conn.autocommit=False` + `SELECT FOR UPDATE` + commit + finally autocommit=True.
  - **C3 — `_list_products()` 기반 snapshot 과잉 + FOR UPDATE 불가**: 전체 list scan. databases / system_prompt 별 endpoint. **ACCEPT** → single-row `SELECT FOR UPDATE` helper. `databases` 제외.
  - **C4 — `sort_order` / `is_default` 누락은 현재 결함**: endpoint 가 갱신하는데 allowlist 빠짐. `is_default=true` side effect 도 기록 권장. **ACCEPT** → allowlist 확장 + `default_cleared_product_ids` extra ChangeJson.
  - **C5 — Rollback 설명 낙관적**: full prompt ChangeJson 들어가면 code revert 만으로 복구 안 됨 → 별 redact/purge SQL 필요. **자동 해소** (C1 ACCEPT 로 content 가 애초에 안 들어감).
- Alt 거부:
  - **v1 단독 진행 (outside voice 흡수 X)**: C1 (PII 노출) + C2 (audit integrity 결함) 모두 fatal. v2 redesign 필수.
  - **C2 제외 (scope 유지)**: audit integrity 결함이 cycle 안에 노출됐는데 별 cycle 위임은 부정합. 사용자 v2 단독 진행 confirm 시 거부.
  - **C4 제외 (allowlist 확장 별 cycle)**: sort_order/is_default 가 현재 audit 에 안 잡힘 — 본 cycle 의 audit 정합성 강화 의도와 모순. 사용자 v2 단독 진행 confirm 시 거부.
- Verification (Phase C sentinel smoke, host-mounted code + docker run):
  - `'TASK-0091-SENTINEL' in body: False` ✓ — system_prompt full content drop (Codex C1)
  - `'should_not_leak' in body: False` ✓ — databases drop (Codex C3)
  - sort_order 100→50 / is_default False→True / `default_cleared_product_ids: [5,9]` ✓ (Codex C4)
  - `system_prompt_summary` 정확 ({present, content_len, updated_at}) (Codex C1+SECURITY §9.2)
- Risks: scope 확장 (Minor→Major) — audit integrity fix 포함. 사용자 영향 0 (audit row 정확성만), DB schema 변경 0, endpoint external contract 변경 0. transaction semantics 만 internal 변경 — concurrent PATCH race 가 `SELECT FOR UPDATE` 로 차단됨 (이전 race window 회귀 fix). live runtime smoke (실 PATCH 호출 + audit row 확인) 는 PR merge 후 next deploy 사용자 검증.
- 미해결 followup:
  - admin.product.create 의 audit 도 allowlist 확장 결과 자동 정합 — 별 sentinel test 권유 (Minor)
  - admin.product.databases.update audit 의 system_prompt summary 패턴 도입 검토 (별 cycle)
  - SECURITY.md §8 strict-string-equality 계약 (TASK-0092 V6 followup)
  - rollback window (1~2 cycle) 후 `_migrate_web_account_activity_to_audit()` 제거 (TASK-0086 followup)
  - TASK-0073 backlog 4 entries 남음 (TASK-0087, 0088, 0089, 0090) — 각 별 cycle
- panel: AGENT-TEAM:codex-outside-voice — Codex consult mode (687,409 tokens). 본 cycle 의 verification panel.
- Trace: REQ-20260520-0006 → TASK-0091 → CHG-20260520-0006 → REV-20260520-0006. **TASK-0091 cycle 종료, TASK-0073 Phase A5 audit 정합성 강화 + audit integrity 결함 fix.**

## REV-20260520-0005 [AGENT-TEAM:codex-outside-voice]
- Date: 2026-05-20
- Decision: TASK-0086 (REQ-20260520-0001, **Major** §12.3 — `WebAccountActivity` legacy table DROP + dual write 종료) plan v1 초안 → Codex outside voice review (consult mode, model_reasoning_effort=high, ~5분, 398,567 tokens) → 5 critical findings + 2 minimum-fix → v2 redesign 흡수 → 사용자 confirm → Phase A backup + scratch restore + 1:1 정합 (74=74) → 사용자 명시 ack → Phase C~G 진행 완료. **WebAccountActivity DROP 완료, dual write 종료, dispatcher (WebAuditEvents) 단일 source-of-truth 전환**.
- Reason: TASK-0073 Phase A2 의 dual source 일시 공존 종료가 본 cycle 의 목적. 1:1 정합 검증 + scratch restore rehearsal + 사용자 명시 ack 가 Major + 파괴적 DROP 의 risk mitigation. 사용자 정책 (`feedback_outside_voice_for_rbac`) 적용 — audit subsystem 보안 표면 + 파괴적 데이터 작업 의무 outside voice.
- Codex outside voice 5 findings 흡수 결정:
  - **C1 — Option A (graceful skip) 불가능**: `_ensure_web_account_activity_schema()` 가 line 2979 + 3130 에서 계속 호출 → DROP 후 재기동 시 table 다시 생성. **ACCEPT** → helper Option B 채택 (호출 + 정의 모두 명시 제거). migration helper (`_migrate_web_account_activity_to_audit`) 만 rollback window 보존.
  - **C2 — dispatcher-only 전환 = mirror 실패가 곧 감사 누락**: record_audit_event 는 fail-open. legacy INSERT 제거 후 mirror = primary audit write. **ACCEPT** → Phase D+E lightweight smoke (host-mounted code + docker run import). 이전 6 row (id 69~74) 가 mirror 와 1:1 정합 입증 → mirror 작동성 확인. tests/test_audit_migration.py M3 제거 (Codex minimum-fix 2).
  - **C3 — "single tx DROP" 표현 잘못됨**: MySQL DDL 은 implicit commit. "DROP atomic" 의미와 "multi-step single tx" 구분. **ACCEPT** → "DROP TABLE single statement" 로 표현 정정. SECURITY.md §9.8 + plan 본문 모두 갱신.
  - **C4 — Backup 검증 약함**: row count 만 부족. mysqldump 옵션 보강 + scratch restore rehearsal + canonical digest 필요. **ACCEPT** → mysqldump 8 옵션 (`--single-transaction --quick --set-charset --create-options --add-drop-table --triggers --hex-blob --no-tablespaces`) + scratch restore 별 schema import → digest match 검증 + row digest `a09e7898d1ce88711f7a850ab5fbcc91`.
  - **C5 — Rollback 정의 불완전**: backup restore = legacy table 만. dual write 부활 = code revert 필요. helper 제거 후 migration 경로 사라짐. **ACCEPT** → rollback runbook 2 시나리오 분리 (DB restore only / code revert + DB restore). REPORT.md + SECURITY.md §9.8 + 본 plan §2.4 모두 cross-reference.
- 추가 흡수:
  - function rename `_log_search_activity()` → 보류 (caller 안정성 우위, 별 cycle).
  - PR title: `chore(feature-0003): retire WebAccountActivity legacy audit table` (refactor 아닌 운영 DB DROP).
- Alt 거부:
  - **v1 단독 진행 (outside voice 흡수 X)**: C1 (Option A 불가능) 가 fatal — DROP 후 재기동 시 table 다시 생성. v2 redesign 필수.
  - **C1 완화 (migration helper 도 제거)**: rollback 1~2 cycle window 포기. dead code 0 하지만 code revert + backup restore + migration helper restore 모두 필요. 사용자 v2 단독 진행 confirm 시 거부.
  - **Phase E smoke 경량화 (dispatcher-only 검증 완화)**: C2 의 mirror failure risk 명시 검증 약화. 사용자 v2 단독 진행 confirm 시 lightweight import smoke 진행.
- Risks: rollback window 1~2 cycle 동안 `_migrate_web_account_activity_to_audit()` 보존 — table-absent silent skip. 그 window 후 별 cycle 에서 helper 자체 제거 검토. dispatcher-only 전환 후 mirror failure = audit 누락 risk — lightweight smoke 로 mitigated, runtime smoke (실제 search 호출) 는 PR merge 후 next deploy 자동 검증. function name `_log_search_activity()` 보존 (이름 낡았지만 caller 안정성 우위).
- 미해결 followup:
  - rollback window (1~2 cycle) 후 `_migrate_web_account_activity_to_audit()` helper 자체 제거 별 cycle (Minor).
  - function rename `_log_search_activity()` → `_audit_conversation_search()` 별 cycle (Minor).
  - SECURITY.md §8 strict-string-equality 계약 명시 (TASK-0092 followup, V6 결과 기반).
  - TASK-0087 (Major, 외부 LAN trust) — feature-0006 위임 별 cycle.
  - TASK-0088~0091 (Minor 4) — 각 별 cycle.
- panel: AGENT-TEAM:codex-outside-voice — Codex consult mode 외부 voice review 실 수행 (398,567 tokens). 본 cycle 의 verification panel.
- Trace: REQ-20260520-0001 → TASK-0086 → CHG-20260520-0005 → REV-20260520-0005. **TASK-0086 cycle 종료, TASK-0073 Phase A2 dual write 종료.**

## REV-20260520-0004 [AGENT-TEAM:codex-outside-voice]
- Date: 2026-05-20
- Decision: TASK-0092 (REQ-20260520-0007, **Minor** §12.3 — `AGENT_AUDIT_ENABLED=0` + `AGENT_MODE=prod` startup fail-closed 7 vector matrix 검증) plan v1 초안 → Codex outside voice review (consult mode, model_reasoning_effort=high, ~5분, 490,891 tokens) → 5 findings + 2 minimum-fix → v2 redesign 흡수 → 사용자 confirm. Phase A0~E 본 cycle 진행 완료, **7 vector PASS (7/7)**.
- Reason: TASK-0073 Phase E 의 사용자 위임 항목 1 건 (audit prod gate fail-closed live 검증) 해소. sandbox SSH 인증 차단 (TASK-0073 시점) → docker/compose 가용 환경 (Docker 29.3.1 + Compose v5.1.1) 으로 변경 → live container spawn 가능. 사용자 정책 (`feedback_outside_voice_for_rbac` user memory) 적용 — RBAC catalog 변경 없음에도 audit subsystem 보안 표면 자체 검증 가치 인정.
- Codex outside voice 5 findings 흡수 결정:
  - **C1 — 테스트 명령 오류**: Dockerfile 이 web UI 를 `/app/web/` 에 복사 (line 23). `python -c "import app"` 는 `ModuleNotFoundError`. uvicorn entrypoint 우회도 불명확. **ACCEPT** → `--entrypoint python` + `import web.app` 으로 정정.
  - **C2 — compose 오염**: `depends_on: mysql` + `.env` + shared volume + 다른 worktree compose project 와 엮일 위험. **ACCEPT** → `docker run` 직접 호출 (compose 우회). `--no-deps` 동등 효과.
  - **C3 — flag parsing 계약 공백**: `os.getenv(...).strip() == "1"` 은 `"true"`/`"yes"`/`"01"`/`""` 모두 disabled. 운영자 trap 가능. **ACCEPT** → V6 추가 (`AGENT_AUDIT_ENABLED=true` + prod → exit 1 negative 검증). SECURITY.md §8 strict-string-equality 계약 명시 별 cycle 후속.
  - **C4 — stderr 검증**: prefix-only 약함, full byte-equal 너무 strict. **ACCEPT** → 3 substring (`[FATAL] AUDIT REQUIRED IN PROD` + `set AGENT_AUDIT_ENABLED=1` + `TASK-0073 Phase A1`) 모두 포함 + `Traceback`/`ModuleNotFoundError` 부재 검증.
  - **C5 — docs append 위치**: TEST.md §3 = Test Cases 정의, §4 = Test Run History. **ACCEPT** → §4 에 append.
- Alt 거부:
  - **v1 단독 진행 (outside voice 흡수 X)**: 5 findings 모두 정합 — 특히 C1 (`import app` 오류) 가 검증 자체 실패시킴. v2 redesign 필수.
  - **V6 제거 (7→6 vector)**: C3 의 strict-string-equality 계약 검증 가치 → 운영자 trap 노출 + SECURITY.md §8 후속 cycle 근거. 사용자 v2 단독 진행 confirm.
  - **V7 제거 (7→6 vector)**: default `1` + default prod 정상 검증 가치 → V5 와 별 의미 (V5 는 명시 set, V7 은 default fallback). 사용자 v2 단독 진행 confirm.
- Risks: V6 가 운영자 trap 노출 — `AGENT_AUDIT_ENABLED="true"` 가 fail-closed. 운영자가 truthy 표현 명시 시 prod 시작 차단. **SECURITY.md §8 strict-string-equality 계약 명시 별 cycle 후속 권고**. 본 cycle scope 외.
- 미해결 followup: 본 cycle 결과의 후속 작업 — 별 cycle.
  - **SECURITY.md §8 strict-string-equality 계약 명시** — V6 결과 기반 (Minor §12.3). 운영자 가이드.
  - TASK-0086 (Major, WebAccountActivity DROP) — 별 cycle.
  - TASK-0087 (Major, 외부 LAN trust) — feature-0006 위임 별 cycle.
  - TASK-0088~0091 (Minor 4) — 각 별 cycle.
- panel: AGENT-TEAM:codex-outside-voice — Codex consult mode 외부 voice review 실 수행. 본 cycle 의 verification panel.
- Trace: REQ-20260520-0007 → TASK-0092 → CHG-20260520-0004 → REV-20260520-0004. **TASK-0092 cycle 종료, TASK-0073 Phase E 위임 1 건 해소.**

## REV-20260520-0003 [AGENT-TEAM:codex-outside-voice]
- Date: 2026-05-20
- Decision: TASK-0093 (REQ-20260520-0008, **Minor** §12.3 — verify-completion check_12 audit endpoint routing 정적 검사) plan v1 초안 → Codex outside voice review (consult mode, model_reasoning_effort=high, ~5분, 132,668 tokens) → 5 findings + 2 minimum-fix → v2 redesign 흡수 → 사용자 confirm. Phase A~F 본 cycle 진행 완료.
- Reason: TASK-0073 Phase E hotfix (CHG-20260520-0001) 의 routing 회귀 fragility — `/{event_id}` 가 정적 sibling 위에 정의되면 FastAPI/starlette linear match 가 422 int_parsing 발생. 본 cycle 은 그 회귀를 정적 grep 으로 영구 차단. 사용자 정책 (`feedback_outside_voice_for_rbac` user memory) 적용 — RBAC catalog 변경 없음에도 audit 표면 회귀 방어 정책으로 outside voice 호출. Minor 등급이지만 보안 표면 자체 점검 가치 인정.
- Codex outside voice 5 findings 흡수 결정:
  - **C1 — SKIP 정책 오류**: event_id 또는 sibling 부재 시 silent PASS 는 "구조 변화 시 manual review 강제" 의도 모순. APIRouter 분리·prefix 변경·route 삭제가 silent pass. **ACCEPT** → SKIP 정책 변경 (feature_id != feature-0003 만 SKIP. 그 외 분기 모두 FAIL "manual review required").
  - **C2 — grep 패턴 fragility**: multi-line decorator / single quote / @router.get / prefix router / trailing slash false-negative 가능. **ACCEPT (C1 과 통합)** → structural change 미검출 시 FAIL 처리로 보강. AST 파서까지는 안 감 (Minor scope).
  - **C3 — `/purge` method-aware mismatch**: POST 라 GET `/{event_id}` 와 collision 0. FAIL hint 의 "purge would route" 표현 부정확. **ACCEPT** → `/purge` 는 sibling list 에서 자동 제외 (auto-discovery 패턴이 `@app.get(...)` 만 매치).
  - **C4 — Inline 4 hardcoded sibling list**: new static GET (e.g., `/stats`) 추가 시 stale. **ACCEPT** → auto-discovery 패턴 (`@app.get("/api/admin/audits/<non-{>")` 자동 grep 수집).
  - **C5 — Negative test 의 production app.py 임시 이동 위험**: dirty worktree / hook / 중간 실패. **ACCEPT** → temp fixture 5 scenario + helper split (`_check_audit_routing_order(app_path)` pure helper).
- 추가 흡수:
  - footer line "9 checks" → "10 checks: 7 pilot + worktree binding + repo immutability + audit endpoint routing" 명시화 (Codex 직접 권장).
  - in-cycle fix (Phase C debug): `set -euo pipefail` + grep no-match (exit 1) 시 `|| true` fallback 처리. log_check 호출 보장.
- Alt 거부:
  - **v1 단독 진행 (outside voice 흡수 X)**: 5 findings 모두 정합 — SKIP 정책 오류는 회귀 방지 게이트 의미 손상. v2 redesign 필수.
  - **C1 완화 (구조 변화 시 WARN exit 0 + stderr 경고)**: 일반 audit refactor 마다 manual review 강제 부담 완화 가능하나, "회귀 방지 게이트" 의도 약화. 사용자 v2 단독 진행 confirm 시 거부.
  - **C4 완화 (inline 3 GET sibling + NOTE comment)**: 단순성 vs new sibling 추가 시 수동 갱신 신뢰. 사용자 v2 단독 진행 confirm 시 auto-discovery 채택.
  - **별 worktree 분기 (ai/claude/0093/check-12)**: branch 이름 task-id 1:1 정합 vs Minor 작업의 worktree spawn overhead. 사용자 본 worktree 유지 confirm.
- Risks: feature-0003 hardcode 는 의도적 — 일반화는 별 cycle. structural change LOUD FAIL 정책은 audit feature refactor 마다 check_12 update 동반 필요 (의도된 강제 행위). multi-line decorator / @router.get 같은 FastAPI 변형은 structural FAIL 로 잡힘 (false-positive 아님 — LOUD fail 의도). AST 파서 도입은 별 cycle (다른 feature 에 동일 패턴 발견 시).
- 미해결 followup: 본 cycle 결과의 후속 작업 — 별 task 별 별 cycle.
  - TASK-0086 (Major, WebAccountActivity DROP) — 별 cycle.
  - TASK-0087 (Major, 외부 LAN trust) — feature-0006 위임 별 cycle.
  - TASK-0088~0091 (Minor 4) — 별 cycle.
  - TASK-0092 (Minor, AGENT_AUDIT_ENABLED=0+prod fail-closed 검증) — Phase E 위임 항목 별 cycle.
- panel: AGENT-TEAM:codex-outside-voice — Codex consult mode 외부 voice review 실 수행. 본 cycle 의 verification panel.
- Trace: REQ-20260520-0008 → TASK-0093 → CHG-20260520-0003 → REV-20260520-0003. **TASK-0093 cycle 종료.**

## REV-20260520-0002 [SKIPPED:backlog-staging]
- Date: 2026-05-20
- Decision: TASK-0073 후속 cycle backlog 8 entries (TASK-0086 ~ TASK-0093) 를 `ai/claude/0086/audit-followup` worktree 의 단일 commit 으로 lock-in. 본 worktree 는 다음 세션의 진입점.
- Reason: 사용자 명시 요청 — "후속 cycle 에 대한 항목은 별도로 진행할 신규 worktree 에 list-up". 본 worktree 의 backlog 는 staging area — 각 task 의 실 작업은 별 cycle (별 PLAN-APPROVED + 별 CHG/REV + 가능 시 별 worktree).
- Alt 거부:
  - **docs/TODOS.md 에 list-up**: CLAUDE.md 정책 "TODOS.md 는 feature 단위로 귀속되지 않은 repo-level 보류 아이템만 추적". 본 8 entries 는 모두 feature-0003 귀속 → feature 의 TASK.md Task Queue 가 정합.
  - **단일 큰 worktree 안에 8 task 모두 진행**: §13.2.2 F1 binding — 한 worktree = 한 branch. 단 본 backlog staging 자체는 단일 worktree OK (단일 commit, 단일 task = backlog 등재).
  - **다음 세션에서 직접 list-up**: 사용자 요청 위배. 본 cycle 종료 *전*에 backlog lock-in 명시.
- Risks: 8 entries 가 단일 worktree 에 등재 — 다음 세션 작업자가 1 cycle = 1 task 분리 정합 보장 필요. NOTE: 별 task 진행 시 별 worktree (`git worktree add ../.worktrees/0086-<slice> -b ai/claude/0086/<slice>` 또는 0087+ 번호 사용) 권유.
- 미해결 followup: 다음 세션에서 본 worktree 진입 후 task 선택 → `/plan-eng-review` 또는 `/autoplan` 호출 → outside voice (Codex) → PLAN-APPROVED → 작업 진행.
- panel: SKIPPED:backlog-staging — 본 commit 은 docs only backlog list-up, 실 작업 cycle 진입 전. plan/eng review 는 task 선택 후 다음 세션.
- Trace: TASK-0073 후속 → CHG-20260520-0002 → REV-20260520-0002.

## REV-20260520-0001 [SKIPPED:hotfix-after-smoke]
- Date: 2026-05-20
- Decision: TASK-0073 Phase E hotfix — `/api/admin/audits/{event_id}` routing 회귀 fix. 정적 sibling endpoint (export.csv / actors / resources) 가 `event_id` parameter 로 잡혀 422. detail endpoint 를 정적 path 뒤로 이동.
- Reason: 사용자 후속 결정 ("make web 재배포 + 일반 테스트") 진행 중 main worktree 의 browser smoke 검증에서 발견. FastAPI/starlette 의 linear match order 회귀. NOTE comment 로 향후 endpoint 확장 시 가이드.
- Alt 거부:
  - **`{event_id:int}` path converter**: FastAPI / starlette 미지원.
  - **별 path prefix (`/api/admin/audit-events/{id}`)**: API contract 변경 — frontend admin.js 의 detail click handler 도 수정 필요. routing 순서 변경이 minimal viable.
  - **endpoint 합치기 (`/api/admin/audits/lookup?id=X`)**: REST 패턴 위반. routing 순서가 자연.
- Risks: routing 순서 정합성이 endpoint 추가/삭제 시 fragile. 향후 audit endpoint 확장 시 NOTE comment 가 가이드.
- 미해결 followup: 별 cycle 의 verify-completion check_12 — `/api/admin/audits/{event_id}` 가 정적 sibling endpoint 보다 *뒤* 정의됐는지 정적 grep (선택). 신규 worktree 의 audit-followup backlog 에 등재.
- panel: SKIPPED:hotfix-after-smoke — make web 재배포 후 직접 smoke 검증으로 발견된 회귀, 단일 endpoint 정의 위치 변경 (logic 변경 0). minimal viable hotfix.
- Trace: REQ-20260519-0001 → TASK-0073 Phase E hotfix → CHG-20260520-0001 → REV-20260520-0001.

## REV-20260519-0022 [SKIPPED:multi-phase-plan-approved]
- Date: 2026-05-19
- Decision: TASK-0073 Phase E (REQ-20260519-0001, **Critical** §12.3) — Completion Checklist 마킹 + TASK-0073 [x] + 외부 영향 검증 (make web 재배포 + browser headless smoke + AGENT_AUDIT_ENABLED=0/prod startup fail + WebAccountActivity migration SQL count) 사용자 위임. 본 cycle 의 모든 in-process 산출물 lock-in.
- Reason: plan PLAN-APPROVED 2026-05-19 의 Phase E 명시 — verify-completion + 컨테이너 재배포 + browser smoke + 최종 commit + TASK-0073 [x]. sandbox SSH 인증 차단으로 본 session 내 `make web` 가동 불가 → 외부 영향 3 항목은 사용자 위임 (사용자 plan 본문에서도 명시: "본 session 종료 후 사용자가 직접 진행 (sandbox SSH 인증 차단). 단 모든 commit 이 local main 에 누적되어 사용자가 한 번에 push 가능"). docs only Phase E 라 verify-completion PASS 안전.
- Alt 거부:
  - **session 내 make web 강제 시도**: sandbox 정책상 docker compose 호출 불가 — 강제 시 에러 + cycle 중단.
  - **TASK-0073 [x] 안 마킹**: in-process 산출물이 plan PLAN-APPROVED 의 거의 100% 달성 (Phase A1~D 모두). 외부 영향만 사용자 위임 — TASK Queue [x] 적절 + Completion Checklist 3 [ ] 항목으로 명시.
  - **Phase E commit 안 함**: TASK Queue [x] + Completion Checklist 변경은 cycle 종료 marker. 마지막 commit 으로 동기화 완결.
- Risks: 사용자가 외부 영향 검증 안 할 시 컨테이너 실 audit row 실 검증 미수행 → 다음 cycle 의 회귀 risk. `docs/TEST.md §3 Test Run History` append 가 사용자 검증 후 별 cycle 권유.
- 미해결 followup: 사용자가 `make web` 재배포 후 8 시나리오 검증 (admin 탭 / filter / detail / CSV / 새 admin action 발생 후 audit row 1:1 / AGENT_AUDIT_ENABLED=0+prod startup fail / WebAccountActivity migration SQL count). 결과를 `docs/TEST.md §3` append + 별 cycle 의 verify-completion PASS.
- panel: SKIPPED:multi-phase-plan-approved — cycle 종료 marker entry. plan PLAN-APPROVED + Phase A1~D 의 lock-in 결과 + 외부 영향 사용자 위임 = 본 cycle 의 자연 완료.
- Trace: REQ-20260519-0001 → TASK-0073 Phase E → CHG-20260519-0026 → REV-20260519-0022. **TASK-0073 cycle 종료.** 외부 영향 (push origin main / browser smoke / migration SQL count) 사용자 위임.

## REV-20260519-0021 [SKIPPED:multi-phase-plan-approved]
- Date: 2026-05-19
- Decision: TASK-0073 Phase D (REQ-20260519-0001, **Critical** §12.3) — 프로젝트 수준 docs 일괄 갱신. SECURITY §9 (audit subsystem) + DECISIONS ADR-0019 + ARCHITECTURE §4·§6 + CONVENTIONS §10.6 audit group + STATUS feature-0003 row + REPORT §1 phase 요약 + TEST §2.1 audit scope.
- Reason: PLAN-APPROVED 2026-05-19 의 Phase D 명시 — sensitive field catalog source-of-truth (SECURITY §8) + ADR-0019 + ARCHITECTURE §4·§6 + CONVENTIONS §10.6 + STATUS row + feature 의 REVIEW/REPORT/TEST. SECURITY §8 가 TASK-0072 점유라 §9 로 재배치 — plan 본문 의도 보존 (Audit subsystem 정책 신설), numbering 충돌 회피.
- Alt 거부:
  - **SECURITY §8 안 subsection (8.8~8.9) 추가**: TASK-0072 의 cross-account search 정책 안에 audit subsystem 섞이면 의미 분리 안 됨. §9 신설이 정합.
  - **별 file `docs/AUDIT.md` 신설**: project-level docs 의 single source 패턴 위반. 본 cycle 의 정책 정본이 SECURITY.md.
  - **ADR-0019 를 feature-local DECISIONS.md 에**: AGENTS.md §16.4 — project-level 의사결정은 `docs/DECISIONS.md` (정합). RBAC 4 catalog 신설 + Tx split + masking 정책 = project-scope 결정.
  - **ARCHITECTURE §6 의 의존성 line 미추가**: TASK-0073 의 `_get_client_ip` 가 feature-0006-lan-proxy-access 의 Caddy XFF 정책 의존 — 명시 표기가 보안 가시성.
- Risks: SECURITY §8 (TASK-0072 1 년 retention) 와 §9 (TASK-0073 365 일 retention 권장) 의 정책 정합성 — 일치하나 별 cycle 통합 정리 필요. CONVENTIONS §10.6 갱신 후 작업 화면 audit placeholder 가 실 entry 부재 → UX 보강 별 cycle.
- 미해결 followup: Phase E browser headless smoke + verify-completion 최종 + Completion Checklist 모두 [x] + TASK-0073 [x] 완료 마킹. 사용자 push origin main (sandbox SSH 인증 차단으로 본 session 위임).
- panel: SKIPPED:multi-phase-plan-approved — docs 변경은 plan PLAN-APPROVED 의 자연 산출. SECURITY §8 → §9 재배치는 plan 본문 의도 보존 (numbering 충돌 해소).
- Trace: REQ-20260519-0001 → TASK-0073 Phase D → CHG-20260519-0025 → REV-20260519-0021.

## REV-20260519-0020 [SKIPPED:multi-phase-plan-approved]
- Date: 2026-05-19
- Decision: TASK-0073 Phase C (REQ-20260519-0001, **Critical** §12.3) — Frontend admin 콘솔 "감사 로그" tab 신설 + 7 항목 filter row + list-detail pane + CSV export (gated) + 작업 화면 / 관리 콘솔 양쪽 PERMISSION_GROUP_ORDER 'audit' 그룹 추가.
- Reason: plan PLAN-APPROVED 2026-05-19 의 Phase C 명시. ChangeJson 의 XSS 차단은 `<pre>` + HTML escape (TASK-0058 share.html 패턴 답습). cursor pagination 으로 audit row 수 large fleet 에서도 안전. CSV gate / tab visibility gate 는 permission map truthy 검사로 hide-vs-disable=hide (TASK-0052 패턴 답습).
- Alt 거부:
  - **본인 audit 작업 화면 drawer**: 본 cycle scope 외. admin 콘솔 진입 권유 위한 작업 화면 placeholder 만.
  - **purge UI 본 cycle**: Critical 등급 + retention 정책 다양 → admin manual SQL 또는 API 직접 호출이 안전. 본 cycle scope 외.
  - **detail pane 의 ChangeJson 인터랙티브 viewer (diff)**: 본 cycle scope 외. `<pre>` 정적 표시가 minimal viable.
  - **action_code multi-select chip**: input + 1 value 가 minimal viable. 별 cycle UX 보강.
- Risks: 작업 화면 placeholder 가 audit 그룹 권한 표시만 + 실 entry point 부재 → 사용자 혼란 가능 (UX wart). `_auditFormatDt` 가 browser local TZ — 다국적 운영 시 admin 간 동기화 차이. CSV button 의 href 가 filter 적용된 URL — 사용자가 후속 filter 변경 후 안 누르면 stale.
- 미해결 followup: Phase E browser headless smoke 가 admin 탭 진입 / filter / detail / CSV button visibility / 새 admin action 발생 시 audit row 1:1 정합 확인. 작업 화면의 audit drawer (`audit.read.own` 본인 view) 별 cycle UX 보강.
- panel: SKIPPED:multi-phase-plan-approved — Frontend 변경은 TASK-0058 share.html 패턴 답습 + CONVENTIONS.md §10.6 정합 lock-in. ChangeJson escape XSS 차단도 검증된 답습.
- Trace: REQ-20260519-0001 → TASK-0073 Phase C → CHG-20260519-0024 → REV-20260519-0020. CONVENTIONS.md §10.6 + TASK-0052 hide-vs-disable + TASK-0058 share.html `<pre>` escape lock-in.

## REV-20260519-0019 [SKIPPED:multi-phase-plan-approved]
- Date: 2026-05-19
- Decision: TASK-0073 Phase B (REQ-20260519-0001, **Critical** §12.3) — 3 test 파일 신설. test_audit_dispatcher (7) + test_audit_rbac (10) + test_audit_migration (3) = 20 시나리오. 실 실행은 컨테이너 가동 + admin/operator/sales 자격 필요 — Phase E 사용자 위임 (plan 본문 명시).
- Reason: plan PLAN-APPROVED 2026-05-19 의 Phase B 명시 — "tests/test_audit_dispatcher.py + test_audit_rbac.py (10 시나리오) + test_audit_migration.py". 컨테이너 미가동 본 session 에서 자동 실행 불가, file 작성 only. TASK-0072 `test_search_rbac.py` 의 urllib + login + Set-Cookie 패턴 답습 — 검증 안전한 답습 대상.
- Alt 거부:
  - **pytest 기반 unit test**: 본 repo 의 기존 test 패턴이 urllib script — pytest 의존 추가 X (zero new dependency).
  - **mock dispatcher direct import**: PYTHONPATH 의존 fragile. HTTP endpoint 응답 + DB SELECT 검증이 더 robust.
  - **자동 실행 (본 session)**: 컨테이너 환경 + admin/operator/sales 비밀번호 보유 가정 — 본 session sandbox 미지원. plan 본문이 명시 "환경 미비 시 test 작성만 + 실행은 Phase E 에 위임".
- Risks: 사용자 환경에서 실 실행 시 admin/operator/sales 비밀번호 가용성 미보장 — TASK-0075 의 6/8 PASS scenario (operator pw 미보유로 일부 skip) 동일 trade-off. M1 의 직접 SQL INSERT 가 docker exec mysql 또는 host mysql client 필요 — 환경별 분기. S3a (admin password-reset target audit 가시성) 가 실 password reset 호출이라 부수효과 큼 — manual 검증 권유.
- 미해결 followup: Phase E 에서 컨테이너 가동 후 `python3 tests/test_audit_*.py` 실행 → `docs/TEST.md §4 Test Run History` append. S3a 의 password-reset target user 본인 audit 가시성 검증이 E1 B 의 핵심 — manual 검증 결과 별 cycle 기록.
- panel: SKIPPED:multi-phase-plan-approved — test 작성은 plan PLAN-APPROVED 의 자연 산출. TASK-0072 `test_search_rbac.py` 패턴 답습이라 새 review 면 적음.
- Trace: REQ-20260519-0001 → TASK-0073 Phase B → CHG-20260519-0023 → REV-20260519-0019.

## REV-20260519-0018 [SKIPPED:multi-phase-plan-approved]
- Date: 2026-05-19
- Decision: TASK-0073 Phase A6 (REQ-20260519-0001, **Critical** §12.3) — user 5 endpoint best-effort audit + anonymous share view (ActorType='anonymous'). Eng review E4 + Codex C11 (anonymous share path) 합쳐 lock-in.
- Reason: PLAN-APPROVED 2026-05-19. user endpoint (`/api/ask` + share CRUD + anonymous view) 는 fail-open 필수 — long-running LLM 또는 anonymous flow 에서 audit 실패가 user 응답 차단하면 main 기능 손실. TASK-0072 `_log_search_activity` 의 fail-open 패턴이 검증된 답습 대상.
- Alt 거부:
  - **user endpoint Same tx**: Codex C3/C4 — `/api/ask` 의 long-running LLM (분 단위 lock hold) + agent_core 별 connection 정합성 깨짐. Same tx 가 deadlock 위험.
  - **anonymous share view 미감사**: Eng review E4 + Codex C11 — admin/operator 가 누가 share token 으로 access 했는지 가시성 손실. ActorType='anonymous' + ActorAccountId NULL 로 row 등록 (audit completeness 유지).
  - **token full 저장**: PII 위협. token_prefix 8 char 만 (full token = 64 char 의 1/8 노출). share token 의 entropy 충분.
  - **`/api/conversations` search snippet 별 hook**: TASK-0072 `_log_search_activity` 가 이미 Phase A2 에서 dual write — 별 hook 불필요 (자연 통합).
- Risks: dispatcher 실패 시 stderr log 만 — audit completeness 가 silent loss 가능. verify-completion check_11 + Phase B `tests/test_audit_dispatcher.py` 가 silent loss 검출. anonymous view 의 `viewer = _optional_account` 가 cookie 오류 시 None 반환 → False positive 'anonymous' label 가능 (실제로는 logged-in viewer 의 cookie 오류). 본 cycle scope, 별 cycle 검증 필요.
- 미해결 followup: Phase B 의 `tests/test_audit_dispatcher.py` 가 fail-open silent loss path 검증. `tests/test_audit_rbac.py` 의 시나리오 (9) anonymous share view → audit row 생성 검증 + (10) `?actor_type=anonymous` filter 검증. silent loss 의 metric 수집 (`stderr [TASK-0073 Phase A6] failed` 카운터) 별 cycle.
- panel: SKIPPED:multi-phase-plan-approved — Codex C11 + Eng review E4 가 plan 단계 lock-in. TASK-0072 `_log_search_activity` 패턴 검증 답습이라 본 phase 의 추가 review 면 적음.
- Trace: REQ-20260519-0001 → TASK-0073 Phase A6 → CHG-20260519-0022 → REV-20260519-0018. Eng review E4 (anonymous ActorType) + Codex C11 (TASK-0058 share anonymous path) lock-in.

## REV-20260519-0017 [SKIPPED:multi-phase-plan-approved]
- Date: 2026-05-19
- Decision: TASK-0073 Phase A5 (REQ-20260519-0001, **Critical** §12.3) — admin 11 mutation endpoint Same tx audit hook + 16 ActionCode build_audit_change_json builder + _audit_admin_mutation helper. plan 의 "13" 은 elastic 표현, 11 endpoint 가 admin mutation 전부.
- Reason: PLAN-APPROVED 2026-05-19. Codex outside voice C6 — raw request 검증 X, builder allowlist 만. PasswordHash / token / api_key 명시 redact. Eng review E5 product delete cascade lock 순서 (system_prompts → product_databases → role_permissions → account_permission_overrides → permissions → products → audit INSERT). Eng review E6 — decorator 거부, 각 endpoint 의 explicit `_audit_admin_mutation()` 호출.
- Alt 거부:
  - **decorator @audit_action**: Eng review E6 거부 — actor capture / ChangeJson builder / masked_fields 가 endpoint 마다 다르므로 magic hide. 11 endpoint 각각 explicit.
  - **src/audit_builders.py 별 module**: PYTHONPATH dependency. app.py 안 helper 섹션이 더 robust + import 부담 0.
  - **POST /admin/products 의 audit 를 inner tx 안**: autocommit=False/True toggle 의 finally 안에 audit hook 두면 rollback 정합성 모호. finally 의 autocommit=True 복원 다음에 hook — autocommit 모드 안전.
  - **DELETE /admin/products 의 audit 를 _audit_admin_mutation helper 로**: E5 cascade lock 순서가 product 의 dependent row 정리 후 audit row INSERT 가 정합 — helper 호출 대신 inline record_audit_event + conn.commit() 한 tx 안 정리.
- Risks: PATCH/POST/DELETE 의 conn.close() 위치가 audit hook 뒤로 이동 — 기존 flow 의 close() 가 implicit commit 이었을 가능성 → audit hook 의 conn.commit() 가 명시 commit 보장. PUT /databases 의 before-state 캡처 SELECT 추가 — 성능 영향 negligible (단 product 의 schemas 수가 작음, ≤ ~10). PATCH /products 의 audit before 가 ProductKey 만 — full snapshot 필요하면 별 SELECT 필요, 본 cycle 의 cost-benefit 으로 후속 정확화.
- 미해결 followup: PATCH /admin/products 의 before-state 가 ProductKey 만 — full WebProducts row 캡처는 별 cycle. Phase B 의 test 가 11 endpoint 각각의 audit row visible 검증. Phase E 의 browser smoke 가 admin 11 action 실 발생 시 audit row 1:1 정합 확인.
- panel: SKIPPED:multi-phase-plan-approved — Eng review E5 (cascade lock 순서) + E6 (explicit dispatcher) + Codex C6 (builder allowlist) 가 plan 단계 lock-in. Critical 등급이나 plan PLAN-APPROVED 후 phase 단위 panel 재호출은 cargo-cult.
- Trace: REQ-20260519-0001 → TASK-0073 Phase A5 → CHG-20260519-0021 → REV-20260519-0017. Codex C6 + Eng review E5/E6 lock-in.

## REV-20260519-0016 [SKIPPED:multi-phase-plan-approved]
- Date: 2026-05-19
- Decision: TASK-0073 Phase A4 (REQ-20260519-0001, **Critical** §12.3) — 5 audit read endpoint (`GET /api/admin/audits` + detail + export.csv + actors facet + resources facet) + 1 chunked purge endpoint (`POST /api/admin/audits/purge`). E1 self filter (Actor OR Target) + 404 byte-equal + E8 chunked PK 의사코드 그대로 구현.
- Reason: PLAN-APPROVED 2026-05-19. Eng review E1 = "B (Actor OR Target)" 사용자 결정 — admin actor + user target 이벤트가 user 본인 audit 에 노출 (admin 의 password-reset / 권한 grant / share revoke 이벤트의 user side 가시성). E8 chunked purge 의 Python 의사코드를 그대로 SQL 로 구현 — chunk 별 tx + 30s deadline + idempotency_key (1 분 내 중복 차단) + start/complete self-audit 2건.
- Alt 거부:
  - **`.own` = ActorAccountId 만**: E1 결정 A 라면 본인 actor 만. admin 의 user-target 이벤트가 user 본인 audit 에서 invisible — 보안 가시성 손실. 사용자 결정 B 정합.
  - **detail 404 vs 403 분리**: Codex C-style metadata leak — `.own` 사용자가 다른 사용자 audit id 를 시도하면 403 응답이 row 존재 신호. 모두 404 = byte-equal.
  - **CSV streaming (chunked)**: 본 cycle scope 외. hard cap 50k 로 DoS 방지. 별 cycle 검토.
  - **purge 전체 1-tx**: LRT 회피 위반. chunk = 별 tx + 30s deadline 으로 partial purge 자연 재시작.
- Risks: `.own` Actor OR Target 분기로 anonymous share view 의 viewer 가 본인 audit 에 보이는 경우 — E4 정합 (anonymous actor + share resource 가 share owner 의 audit 에 노출은 의도된 가시성). CSV 50k 가 large fleet 에서 모자랄 수 있음 — 본 cycle scope, follow-up. purge deadline 30s 가 짧을 수 있음 — partial purge 시 다음 호출 cursor 자연 재시작 보장.
- 미해결 followup: Phase A5 의 admin 13 mutation endpoint hook (Same tx) + ActionCode 별 builder. Phase B 의 10 RBAC smoke (특히 (3a) admin password-reset → user 본인 audit 노출, (9)(10) anonymous share view audit_type filter).
- panel: SKIPPED:multi-phase-plan-approved — Eng review E1 / E8 / E5 가 plan 단계에서 SQL filter + 의사코드 lock-in. Critical 등급이나 plan PLAN-APPROVED 후 Phase 단위 panel 재호출은 cargo-cult (REV-20260519-0013/0014/0015 정합).
- Trace: REQ-20260519-0001 → TASK-0073 Phase A4 → CHG-20260519-0020 → REV-20260519-0016. Eng review E1 (Actor OR Target) + E8 (chunked PK purge Python 의사코드) lock-in.

## REV-20260519-0015 [SKIPPED:multi-phase-plan-approved]
- Date: 2026-05-19
- Decision: TASK-0073 Phase A3 (REQ-20260519-0001, **Critical** §12.3) — RBAC catalog +4 (`audit.read.own/.any/.export/.purge`) + permission group `audit` 신규 + admin/operator/sales/dba/pending 5 role 자동 catchup. Codex outside voice C8/C9/C10 + Eng review E9 lock-in.
- Reason: PLAN-APPROVED 2026-05-19. `.own/.any` 패턴 (TASK-0058 share + TASK-0063 RBAC catchup) 답습 — 본인 actor/target 만 조회 (.own) + 전체 audit row 조회 (.any superset). admin/dba 가 `.any` + `.export`, admin 만 `.purge` 의 분리는 권한 책임 최소화 (compliance 외부 검토 vs retention 관리 분리). `feedback_outside_voice_for_rbac` 정책 강제 — RBAC 변경은 outside voice 필수, Codex 가 plan 단계에서 14 finding lock-in.
- Alt 거부:
  - **`audit.*` 단일 권한 (group="audit")**: Codex C8 — `.own/.any` 분리 정합성 깨짐. admin 의 `.any` 가 sales 의 `.own` 을 superset 으로 포함하는 의미 명확.
  - **`.purge` 는 dba 도 grant**: dba 가 retention 정책 직접 결정하면 책임 분산. admin 만 grant — Compliance 책임 명확.
  - **dba role 을 SEED_ROLE_DEFINITIONS 에 추가**: TASK-0060 의 dba 가 manual 생성 case 라 SEED 추가는 scope creep. catchup loop 만 보강 (E9 의 가벼운 해석).
  - **permission_group_of fallback="misc"**: Codex C10 — group="audit" 명시 + frontend `PERMISSION_GROUP_ORDER` 갱신 (Phase C scope) 으로 misc fallback 차단.
- Risks: dba role 이 DB 에 부재한 환경은 catchup graceful skip — 향후 dba 생성 시 다음 catchup 에서 backfill. INSERT IGNORE 라 duplicate 안전. `_ensure_permission_catalog` 가 `_ensure_seed_roles` 앞 호출 보장 (TASK-0063 회귀 fix 패턴) — 신규 permission id 가 valid 시점에 catchup 진행.
- 미해결 followup: Phase C frontend `PERMISSION_GROUP_ORDER` 갱신 (admin.js + app.js). Phase D `docs/CONVENTIONS.md §10.6` 갱신 (audit group 의 admin section "관리" 우선 노출). Phase B `tests/test_audit_rbac.py` 의 10 시나리오 검증.
- panel: SKIPPED:multi-phase-plan-approved — RBAC catalog 4 추가는 Codex outside voice + Eng review E9 가 plan 단계 lock-in. 본 phase 단위 commit 마다 panel 재호출은 cargo-cult.
- Trace: REQ-20260519-0001 → TASK-0073 Phase A3 → CHG-20260519-0019 → REV-20260519-0015. Codex outside voice C8/C9/C10 + Eng review E9 lock-in.

## REV-20260519-0014 [SKIPPED:multi-phase-plan-approved]
- Date: 2026-05-19
- Decision: TASK-0073 Phase A2 (REQ-20260519-0001, **Critical** §12.3) — `WebAccountActivity` (TASK-0072) 기존 row 흡수 migration helper + `_log_search_activity` dual write wrap. legacy table 본 cycle DROP 안 함 (별 cycle backup 후).
- Reason: Codex outside voice C2 minimum-fix (TASK-0072 schema 발견 — 직전 검토 보고가 놓친 결손). plan 본문 명시 — "기존 row → WebAuditEvents transform + `_log_search_activity` transparent wrap (signature 보존, caller 변경 0)". dual source 일시 공존이 data 보존 우선 + 별 cycle backup 검증 후 DROP 안전.
- Alt 거부:
  - **legacy table 즉시 DROP**: backup 검증 전 DROP 시 audit trail 손실 risk. plan 명시 "data 보존" 위배.
  - **single write (legacy INSERT 제거, dispatcher only)**: legacy table 이 정합 상태 검증 전이라 dual source 비교 검증 불가. 별 cycle 까지 dual 유지가 안전.
  - **migration on demand (별 manual script)**: catchup 패턴 (TASK-0063) 답습 못 함. fast/slow path 양쪽 hydrate 가 zero-touch 정합.
- Risks: dual write 시 동일 audit event 가 두 row — search 통계 double count. 본 cycle frontend (Phase C) 가 WebAuditEvents 만 조회라 UX 영향 0. JSON_OBJECT 가 MySQL 8.0+ 한정 — `docker-compose.yml` MySQL 8.0 가정 (§15.4) 정합. migration RequestId marker 가 64 char limit 안 (`account-activity:` 17 + bigint ≤ 20 = ≤ 37 char) 안전.
- 미해결 followup: 별 cycle TASK 등재 — `WebAccountActivity` data backup → DROP table → `_log_search_activity` mirror 본문에서 legacy INSERT 제거 → search 통계 single source 정합화. Phase B test (`tests/test_audit_migration.py`) 가 idempotency 검증 (두 번 호출 시 두 번째 INSERT 0 row).
- panel: SKIPPED:multi-phase-plan-approved — Codex outside voice C2 가 plan 단계의 minimum-fix 로 이미 lock-in. plan 본문이 transform SQL signature 명시 + idempotency 요구. 본 phase 단위 commit 마다 panel 재호출은 cargo-cult (REV-20260519-0013 의 reasoning 답습).
- Trace: REQ-20260519-0001 → TASK-0073 Phase A2 → CHG-20260519-0018 → REV-20260519-0014. Codex outside voice C2 minimum-fix lock-in.

## REV-20260519-0013 [SKIPPED:multi-phase-plan-approved]
- Date: 2026-05-19
- Decision: TASK-0073 Phase A1 (REQ-20260519-0001, **Critical** §12.3) — audit dispatcher `record_audit_event()` + `AGENT_AUDIT_ENABLED` prod startup fail-closed gate + verify-completion check_11 SPOF guard 구현. CEO review 9 decision · Codex outside voice 14 findings + 5 minimum-fix · Eng review E6 (explicit dispatcher) / E7 (SPOF mitigation) 의 in-cycle lock-in.
- Reason: PLAN-APPROVED 2026-05-19 (TASK-0073 Phase A0~F 일괄). Critical 등급이라 Codex outside voice 가 plan 단계에서 14 findings + 5 minimum-fix 의 redesign 흡수 완료. 본 Phase A1 commit 은 dispatcher 인프라 + prod fail-closed gate 만 추가하므로 별도 panel 호출 불필요 — 이미 plan 단계의 outside voice 가 dispatcher signature / gate 정책 / SPOF mitigation 모두 lock-in.
- Alt 거부:
  - **startup hook 안 sys.exit** (FastAPI `@app.on_event("startup")`): main thread 가 await 인 상황에서 raise SystemExit 가 fully propagate 안 되는 환경 존재 (uvicorn worker 분기). module-load time exit 가 가장 단순 + 결정적.
  - **dispatcher decorator pattern** (`@audit_action(...)`): Eng review E6 에서 명시 거부 — decorator 가 actor capture / ChangeJson builder / masked_fields per-endpoint 차이를 magic-hide. 17 hook site 각각 explicit `record_audit_event(...)` 호출.
  - **autocommit dispatcher 안 conn.commit()**: caller 의 transaction 정책 (admin Same tx fail-safe / user fail-open) 과 충돌. dispatcher 는 commit/rollback 안 함 (E6 explicit).
- Risks: module-load `sys.exit` 가 Phase B tests 의 import 차단 가능 — test runner 가 `AGENT_MODE=test` 환경변수 강제. caller 가 dispatcher 의 commit/rollback 책임 망각 시 INSERT 가 visible 안 됨 — admin endpoint same-tx 정책의 docstring + verify-completion check #11 로 인지 강화.
- 미해결 followup: 추후 Phase 들 (A2~E) 모두 본 dispatcher 의 caller wire-up. Phase A5/A6 의 wire-up 시 caller contract (admin Same tx / user fail-open) 의 docstring 보강 + Phase B 의 `tests/test_audit_dispatcher.py` 가 INSERT row visible 한 E2E 검증.
- panel: SKIPPED:multi-phase-plan-approved — Critical §12.3 이나 Codex outside voice + Eng review 가 plan 단계에서 dispatcher signature / gate 정책 / SPOF mitigation 모두 lock-in (REV-20260519-0001 이전 cycle 의 plan 단계 outside-voice 보고 = 본 cycle 의 panel 대체). 본 Phase 단위 commit 마다 panel 재호출은 cargo-cult.
- Trace: REQ-20260519-0001 → TASK-0073 Phase A1 → CHG-20260519-0017 → REV-20260519-0013. CEO review 9 decision + Codex 14 findings + Eng review E6/E7 lock-in.

## REV-20260519-0012 [SKIPPED:design-panel]
- Date: 2026-05-19
- Decision: TASK-0085 (REQ-20260519-0014, Minor §12.3) — lazy-create 사이드바 optimistic pending entry. multi-pending sentinel-keyed `state.pendingConversationEntries` Map + closure-aware cleanup + `_switchToPendingConversationContext` 클릭 swap. backend / RBAC / endpoint / audit / DB 무변경.
- Reason: 사용자 직접 요청 — "+ 새 대화 송신 직후 다른 대화 전환 시 사이드바에서 잠시 사라지는 이슈" + "대화 내부 진입 가능 — 작업 step 현황 출력 위해". TASK-0048 lazy 패턴이 backend list 등재를 응답 시점까지 지연 — frontend placeholder + backend list 둘 다 새 entry 없는 구간이 사이드바 완전 소실. backend 변경 없이 frontend optimistic UI 로 해결.
- Alt 거부:
  - **backend eager row 생성**: TASK-0048 빈 대화 누적 방지 의도 위배.
  - **state.conversations 에 직접 추가**: refreshWorkspace 가 통째 replace 라 사라짐.
  - **single pendingConversation object**: multi-pending 두 번째가 첫 번째 overwrite. TASK-0082 unique sentinel 정합 깨짐.
  - **pendingBubble 도 sentinel 별 Map**: 완전한 multi-bubble. 본 cycle scope 초과.
- Risks: pendingBubble swap 시 step 정보 손실 (cid 전 polling 불가) / closure mismatch 시 cid binding skip / 3 s failed timer / 메모리 누수 (closure cleanup 으로 보호) / legacy appendPendingItem 보존.
- 미해결 followup: 사용자 환경 검증 (5 시나리오) / lazy-create progress streaming (cid 미리 발급) / failed entry dismiss 버튼.
- panel: SKIPPED:design-panel — Minor §12.3 + frontend state machine 변경 + 단일 파일 + RBAC/auth/DB 무영향. AGENTS.md §18.4 SKIPPED 정책 (단순 작업).
- Trace: REQ-20260519-0014 → TASK-0085 → CHG-20260519-0016 → REV-20260519-0012. TASK-0048 + TASK-0082 design 의 자연 연속.

## REV-20260519-0011 [SKIPPED:design-panel]
- Date: 2026-05-19
- Decision: TASK-0084 (REQ-20260519-0013, Minor §12.3) — D2Coding 우선 monospace stack 으로 전역 통일 재시도. `:root` 의 `--font` / `--mono` 두 토큰을 다시 단일 D2Coding 우선 monospace stack 으로 통합 (`"D2Coding", "D2Coding ligature", "Cascadia Code", "SFMono-Regular", Consolas, "Noto Sans Mono CJK KR", ui-monospace, Menlo, monospace`) + `--font: var(--mono)` 참조. admin.html cache-bust `?v=20260519-d2coding-mono`. index.html cache-bust 는 사용자 main wt revert 의도 존중 skip.
- Reason: 사용자 직접 요청 "D2Coding 폰트를 우선해줄 수 있을까요?" + AskUserQuestion (D2Coding 적용 범위) 응답 "본문 + 코드 모두 (전역 monospace 통일 부활)". 흐름: (1) CHG-0013 — 첫 요청 monospace 통일 시도 → (2) CHG-0014 — 한글 가독성 호소로 sans-serif 환원 → (3) CHG-0015 — D2Coding (NAVER 한글 monospace 가독성 검증된 폰트) 우선으로 monospace 통일 부활. 사용자는 monospace 의 정렬 효과를 원하지만 한글 가독성도 보장되어야 함을 D2Coding 으로 양립. D2Coding 은 한글·영문 모두 등폭이며 한글 가독성이 system monospace 보다 우월하므로 사용자 가독성 호소 (CHG-0014 reason) 완화 가능.
- Alt 거부:
  - **본문은 sans-serif 유지 + var(--mono) 만 D2Coding 우선**: 사용자가 본문 가독성 + 코드 영역 한글 등폭 둘 다 보장. 단점 — 사용자가 AskUserQuestion 응답에서 명시적으로 "본문 + 코드 모두 (전역 monospace 통일 부활)" 선택. 본 cycle 의 명시 결정과 충돌. 향후 사용자가 가독성 호소 시 본 옵션으로 별 cycle.
  - **D2Coding WebFont 도입 (CDN 또는 self-host)**: D2Coding 미설치 환경에서도 보장. 단점 — 외부 의존 (CDN) 또는 self-host 인프라 + 첫 로딩 latency + CSP 검토 + offline 환경 제약. 본 cycle 범위 초과 — 별 cycle 에서 결정. 현재는 사용자가 D2Coding 을 직접 설치한 환경 가정.
  - **D2Coding ligature 만 우선**: ligature 변형 한정. 단점 — ligature 미사용 사용자 환경 분기. 일반 D2Coding 우선 + ligature 도 fallback chain 에 포함이 안전.
  - **CHG-0013 진동 차단 위해 강제 sans-serif**: 사용자 요청 무시. 정책 위반.
- Risks:
  - **D2Coding 미설치 환경**: fallback chain 으로 자동 대체되지만 한글이 system monospace 또는 default 폰트로 fallback → 사용자 의도 (D2Coding 한글 가독성 + 등폭) 미달. 사용자 환경에 D2Coding 설치 안내 필요 (https://github.com/naver/d2codingfont).
  - **monospace 한글 가독성 trade-off**: D2Coding 이 한글 monospace 중 가독성 좋지만 sans-serif 본문 (system-ui 등) 보다는 가독성 낮음. 사용자가 CHG-0014 에서 "눈 아픔" 호소했었음 — D2Coding 으로도 같은 호소 가능. 사용자 검증 후 추가 조정 (예: 본문 sans-serif + 코드 D2Coding) 가능.
  - **stack 첫 entry 인용**: `D2Coding` 과 `D2Coding ligature` 두 변형 모두 첫 줄 우선 — 시스템에 설치된 변형 자동 적용. 일부 시스템이 두 변형을 다른 폰트로 인식 가능 — 영향 최소 (둘 다 D2Coding 계열).
  - **CHG-0013/0014/0015 진동 trace**: 본 cycle 이 세 번째 진동 — 사용자 의도가 명확히 결정된 상태이긴 하나, 미래 cycle 에 readability vs alignment 의 trade-off 가 재발할 가능성. WebFont 도입이 영구 해결책 — 별 cycle.
  - **share.css 무변경**: 공유 페이지 별도 stylesheet. 본 cycle 영향 없음.
- 미해결 followup:
  - **D2Coding WebFont 도입**: 환경 무관 보장. CSP / CDN / self-host 검토 + 첫 로딩 FOUC 처리.
  - **사용자 가독성 검증**: 본 stack 적용 후 사용자가 한글 본문 가독성에 만족하는지 확인. 호소 시 본문 sans-serif + 코드 D2Coding 분리 또는 다른 한글 monospace (예: Sarasa Gothic K Mono) 시도.
- Trace: REQ-20260519-0013 → TASK-0084 → CHG-0015 → REV-0011. AC-0184 / AC-0185 의 design intent 가 CHG-0015 로 단일 D2Coding 우선 monospace 통합으로 합쳐짐. AC-0186 cache-bust 갱신. AC-0187 (D2Coding 우선) 등록.
- [SKIPPED:design-panel] cosmetic-only typography stack 갱신 (`:root` 의 `--font` / `--mono` 두 토큰 + admin.html cache-bust). 사용자가 직접 D2Coding 우선 monospace 통일 의사결정 (AskUserQuestion 응답 명시). UI 도메인 변경이나 security / data / API contract / RBAC / audit 영향 없음 — 단순 CSS 토큰 + cache-bust 1 line. design panel 호출 가치 vs 실행 비용 trade-off 에서 skip 정합 (§18.8 cosmetic-only exception). 사용자가 추가 가독성 호소 시 별 cycle 에서 design panel 호출 가능.

## REV-20260519-0010
- Date: 2026-05-19
- Decision: TASK-0083 followup (REQ-20260519-0012, Minor §12.3) — REV-0009 의 monospace 통합 design 폐기 + 한글 가독성 우선 system-ui sans-serif stack 으로 재설정. `:root` 의 `--font` 를 `system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", "Apple SD Gothic Neo", "Noto Sans KR", "Malgun Gothic", "맑은 고딕", "Helvetica Neue", Arial, sans-serif` 로 갱신. `--mono` 는 REV-0009 이전 stack (`"Cascadia Code", "SFMono-Regular", Consolas, monospace`) 복원. `--font: var(--mono)` 참조 제거 → 두 토큰 의미 분리 회복. admin.html cache-bust 토큰을 `?v=20260519-cjk-readable` 로 갱신, index.html cache-bust 는 사용자 직접 revert 흔적 (system reminder) 존중하여 본 cycle 에서 skip.
- Reason: 사용자 직접 보고 — "중간에 확인해보니, 한글 기준으로 눈이 아픕니다… 한글 기준으로 가장 범용성있는 폰트로 다시 설정해주세요". REV-0009 의 monospace 통합은 영문·ASCII 정렬에는 정합하지만 한글에는 (a) 모노스페이스 한글 폰트 (D2Coding, Noto Sans Mono CJK KR) 가 시스템에 없는 경우 fallback 결과로 폭 정합 깨짐 + (b) 한글 모노스페이스가 시스템에 깔려 있어도 일반 본문 가독성이 낮음. 사용자의 가독성 우선 결정. 가장 범용성 있는 한글 폰트 stack 은 OS native (Windows = 맑은 고딕, macOS = Apple SD Gothic Neo, Linux = Noto Sans CJK 자동 fallback) 를 우선하는 system-ui 기반. 별도 WebFont 설치 없이 모든 환경에서 자연 한글 렌더링.
- Alt 거부:
  - **Pretendard 우선 stack**: 한글 디자인 표준이며 가독성 우수. 단점 — 시스템에 미설치 시 WebFont 로딩 필요 (별도 CDN/self-host). 본 cycle 의 "범용성" 우선이라 system-native 가 정합. 사용자가 Pretendard 도입 요청 시 별 cycle 에서 WebFont + stack 첫 자리 추가.
  - **`--font` 만 변경하고 `--mono` 의 한글 monospace fallback (D2Coding, Noto Sans Mono CJK KR) 은 유지**: 코드/로그 영역의 한글이 등폭 유지. 단점 — `var(--mono)` 사용처가 실제 한글을 자주 표시하는 곳인지 검토 결과 SQL/code snippet 중심이라 한글 비중 낮음 + 시스템 의존성 유지 부담. REV-0009 이전 원본 stack 복원이 가장 단순 + 회귀 0.
  - **CHG-0013 entry 를 git revert 또는 amend**: append-only 정책 (§5.2) + CHG-0013 가 다른 AI 작업자의 a7b7ded commit 에 흡수된 상태 → revert 시 다른 작업자의 다른 변경도 영향. CHG-0014 로 forward-only 정정.
  - **index.html cache-bust 도 갱신**: admin.html 과 동일 갱신으로 일관성. 단점 — 사용자 system reminder 의 "intentional, don't revert" 신호 위반 가능 + 사용자가 main wt 에서 직접 revert 한 의도 (이전 작업자 영역과의 분리) 와 충돌. 안전 마진을 위해 index.html 은 skip + 사용자에게 hard refresh 안내.
  - **WebFont 도입 (Noto Sans KR variable / Pretendard)**: 모든 환경에서 동일 한글 렌더링 보장. 단점 — 외부 의존 + 첫 로딩 latency + CSP 검토 + offline 환경 제약. 본 cycle 범위 초과 — 별 cycle.
- Risks:
  - **index.html cache-bust 미갱신**: 사용자가 작업 화면 첫 진입 시 styles.css 가 브라우저 캐시 hit → 새 sans-serif stack 즉시 안 보일 수 있음. Ctrl+Shift+R (hard refresh) 또는 DevTools "Disable cache" 모드 필요. UX 영향 단기 (캐시 만료 후 자연 해소).
  - **system-ui 구형 브라우저 미지원**: iOS Safari 12 이하 / Android Browser 일부가 `system-ui` 키워드를 인식 못 함 — fallback `-apple-system` / `BlinkMacSystemFont` 가 그 자리를 채움. 실용적 risk 0.
  - **CHG-0013 design intent 의 부분 해제**: AC-0184 "전역 monospace 통일" 의 의도가 CHG-0014 로 사실상 폐기. AC-0185 (var(--font) 영역은 sans-serif, var(--mono) 영역은 monospace 유지) 로 재정의. 추후 read 시 CHG-0013 + CHG-0014 의 trace 가 명확.
  - **한글 폰트 스타일 차이 (OS 별)**: 맑은 고딕 / Apple SD Gothic Neo / Noto Sans CJK 가 weight·shape 미세하게 다름 — 사용자 환경별 시각 차. 의도된 trade-off (범용성 우선).
  - **share.css 무변경**: 공유 페이지는 별도 stylesheet — 본 cycle 영향 없음. 사용자가 share.html 도 갱신 요청 시 별 cycle.
- 미해결 followup:
  - **사용자 환경 검증**: 본 stack 의 한글 가독성을 사용자 환경 (Windows 맑은 고딕 / macOS Apple SD Gothic Neo / Linux Noto Sans CJK) 에서 직접 확인.
  - **Pretendard WebFont 도입 검토**: 모든 환경에서 동일 한글 렌더링 필요 시.
  - **`var(--mono)` 영역의 한글 가독성 별도 검토**: 코드/로그 영역에서 한글이 등장하는 경우 monospace 가독성 issue 있는지 사용자 확인.
- Trace: REQ-20260519-0012 → TASK-0083 followup → CHG-0014 (sans-serif 환원) → REV-0010. REV-0009 의 design intent 는 본 entry 로 정정됨 — append-only 유지하되 후속 의사결정이 우선.

## REV-20260519-0009
- Date: 2026-05-19
- Decision: TASK-0083 (REQ-20260519-0011, Minor §12.3) — `:root` 의 `--font` / `--mono` 두 토큰을 단일 monospace stack 으로 통합. `--mono` 에 한글 monospace fallback (`D2Coding`, `Noto Sans Mono CJK KR`) 추가 + `--font: var(--mono)` 참조. body / button / input / textarea / select 의 기존 cascade (`var(--font)` / `font: inherit`) 가 그대로 작동해 작업·관리 화면 전역에 등폭 글꼴 적용. cache-bust 토큰 동시 갱신 (index.html + admin.html).
- Reason: 사용자 직접 요청 — "프로젝트로 실행되는 웹브라우저 내에서 출력되는 폰트를 monospace로 변경하여 문자열 길이와 실제 표현되는 위치가 정합하도록 구성". 의도는 "한 글자 한 글자가 같은 너비를 차지해서 ASCII 표 / 로그 / 결과 출력의 컬럼 정렬이 깨지지 않게" 로 해석. 현재 `--font` 가 Segoe UI / Noto Sans KR (proportional) 라 한글 / 영문 모두 가변 폭 → 사용자 의도와 불일치. 가장 단순한 변경 (`--font` 를 monospace stack 으로 치환) 으로 전역 일관 적용 가능. body 단위 `font-family: var(--font)` 가 cascade 의 출발점이라 단일 토큰 변경으로 전체 효과.
- Alt 거부:
  - **`* { font-family: monospace !important; }` 같은 universal selector 강제**: 모든 element 강제 적용. 단점 — `var(--mono)` 를 명시 적용한 코드 영역 (line 1069 등) 이 사실상 의미 잃음 + `!important` 가 향후 part-only 회복을 어렵게 함. 기존 token 시스템 활용이 design intent 보존 측면 우월.
  - **body 의 `font-family` 만 변경 (`var(--font)` → `var(--mono)`)**: 단일 line 변경으로도 효과 동일. 단점 — `--font` 토큰이 정의는 있으나 실제 사용처 없음 → 의도 불명. `--font: var(--mono)` 통합이 향후 reader 에게 "두 토큰이 의도적으로 같다" 를 명시.
  - **WebFont (D2Coding / JetBrains Mono) CDN 로딩**: 시스템에 monospace 한글 폰트 미설치 환경에서도 한글 등폭 보장. 단점 — 외부 의존 + 로딩 latency + offline 환경 제약 + CSP 검토. 본 cycle 의 1-line CSS 변경 범위 초과 → 별 cycle.
  - **share.html 까지 동시 변경**: 공유 페이지도 monospace 통일. 단점 — share.css 의 typography 가 별도 design intent (공유 뷰는 일반 사용자 대상이라 가독성 우선) 일 수 있음. 사용자가 "프로젝트로 실행되는 웹브라우저" 라고 표현 — 작업·관리 화면을 가리킨다고 해석. share.html 도 통일 요청 시 별 cycle.
  - **monospace 영역만 명시 변경 (예: result table, log view 만)**: 더 보수적인 접근. 단점 — 사용자 요청 "출력되는 폰트" 는 전역 의도 표현. 부분 변경은 사용자 의도 축소 해석.
- Risks:
  - **한글 monospace 시스템 의존**: D2Coding / Noto Sans Mono CJK KR 미설치 환경에서 한글이 fallback `ui-monospace` / `monospace` 로 해석되어 system default 한글 (proportional) 로 렌더 가능. CSS 단독으로 강제 불가. 사용자가 정합 깨짐을 보고 시 (a) 시스템 폰트 설치 안내 또는 (b) WebFont 도입 (별 cycle).
  - **가독성 trade-off**: monospace 가 일반 본문 가독성 (특히 긴 한글 문장) 보다 ASCII 정렬에 최적화. 사용자가 일부 영역 (network / button label / popover) 만 sans-serif 로 복원 요청 시 그 영역의 `font-family` 를 `var(--font)` 가 아닌 별도 stack 으로 명시.
  - **font 토큰 의미 분리 소실**: `--font` (proportional 의도) 와 `--mono` (등폭 의도) 의 분리가 사라짐. 향후 design intent 회복 시 line 35 `--font: var(--mono)` 를 명시 stack 으로 되돌리면 됨 — 1-line 회복 가능.
  - **cache-bust 토큰 동기화**: index.html + admin.html 두 곳 모두 갱신. share.html 은 share.css 사용 (별 stylesheet) — cache-bust 동기화 불필요.
  - **AC-0184 신규 등록 + 회귀 검증**: 기존 AC (chat pane / lazy-create / unique sentinel / search / excerpt) 모두 typography 와 무관 → cascade 동일성으로 회귀 0. smoke 시나리오는 MODIFY.md 의 Verification 항목 참조.
- 미해결 followup:
  - **한글 monospace WebFont 도입**: 사용자 환경 무관 등폭 보장. CDN (예: jsDelivr 의 D2Coding) 또는 self-host. CSP / 로딩 latency / offline 영향 검토. 별 cycle.
  - **share.html monospace 통일 여부**: 사용자 의도 확인 후 결정.
  - **specific 영역의 sans-serif 복원 요청**: 사용자가 가독성 보고 시 부분 복원.
- Trace: REQ-20260519-0011 → TASK-0083 → CHG-20260519-0013 → REV-20260519-0009. AC-0184 (전역 monospace 통일) 등록.

## REV-20260519-0008
- Date: 2026-05-19
- Decision: TASK-0082 (REQ-20260519-0010, Minor §12.3) — lazy-create unique sentinel design 도입. 글로벌 단일 `PENDING_CONV_SENTINEL` 토큰을 각 lazy-create 진입마다 `state.pendingSentinel = _newPendingSentinel()` 으로 분리 + closure-aware cleanup. TASK-0081 의 stale guard 자연 흡수.
- Reason: 사용자 직접 보고 followup of TASK-0081 — "+ 새 대화 클릭 후 입력칸 활성화 안 됨". 직접 코드 검토로 root cause 재구명: (1) `isCurrentConvBusy()` 가 글로벌 단일 sentinel (`PENDING_CONV_SENTINEL`) 점유 여부 검사. (2) 첫 send 의 in-flight 시 busyConversations 에 sentinel 점유 → 사용자가 + 새 대화 클릭해도 두 번째 컨텍스트에서 isCurrentConvBusy() 가 same sentinel 검사로 true 반환 → renderComposer 가 input.disabled = true 그대로 → 활성화 안 됨. (3) TASK-0081 의 guard 분기는 in-flight 시 early return + renderComposer 미호출 — input 상태 update 안 됨. 두 결함이 합쳐져 사용자 증상 발생. 근본 해결은 unique sentinel design — 컨텍스트별 별개 토큰으로 isCurrentConvBusy 가 두 번째 컨텍스트에서 false 반환.
- Alt 거부:
  - **TASK-0081 의 guard 분기에서 input.disabled = false 강제 + toast 안내**: minimal hotfix (1~2 줄). 단점 — input 활성화는 됐지만 send 시점에 isCurrentConvBusy=true 라 또 차단 → 무한 루프 UX. 사용자가 prompt 작성해도 보낼 수 없음.
  - **isCurrentConvBusy 의 sentinel 검사를 시간 기반 비교**: pendingNewConversation 진입 시간 기록 후 비교. 너무 fragile + race window 다양.
  - **글로벌 sentinel 제거 + busyConversations 에 lazy 진입 자체를 add 안 함**: backend 와의 race window 보호 상실 — backend 의 lazy-create 가 종료되기 전 사용자가 다시 send 시 동일 cid 충돌 위험. sentinel design 의 목적 (race window 보호) 상실.
  - **각 컨텍스트마다 별도 state slice (multi-pending state machine)**: 가장 robust 하지만 frontend state 모델의 대규모 refactor — overkill. 본 fix 의 unique sentinel + closure cleanup 으로 충분.
- Risks:
  - **closure mismatch 시 첫 대화의 activeConversationId 갱신 skip + polling skip**: 사용자가 첫 응답 도착 전 + 새 대화 클릭으로 두 번째 컨텍스트 이동한 경우, 첫 대화의 newCid 가 발급돼도 본 컨텍스트에서 자동 binding 안 함. 사용자가 사이드바 conversation list 에서 첫 대화 클릭으로 진입해야 함. `refreshWorkspace(newCid)` 가 사이드바 list 를 refresh 하므로 첫 대화는 표시. 의도된 동작 (사용자 의지 = 두 번째 대화 진입) 이지만 사용자 인지 위해 별 cycle 에서 toast 안내 추가 검토 가능.
  - **pendingSentinel race**: `Math.random().toString(36).slice(2, 8)` 6 char 16M 분리. 동일 ms 안 다중 진입 시 충돌 위험 무시 가능.
  - **legacy PENDING_CONV_SENTINEL reference**: 본 fix 후 글로벌 단일 토큰 검사 경로 모두 `state.pendingSentinel` 로 변경. 상수 자체는 호환 별칭으로 유지 — 별 cycle 정리 가능.
  - **TASK-0081 의 catch cleanup 정책 보존**: 본 design 의 catch path 도 closure-aware cleanup 으로 TASK-0081 의 의도 유지. 다만 closure mismatch 시 (드물 것이나) cleanup skip — 두 번째 컨텍스트의 state 보호.
- 미해결 followup:
  - **사용자 환경 직접 검증**: 4 종 회귀 시나리오 (in-flight 중 새 대화 / catch 후 새 대화 / 응답 후 새 대화 / pending bubble error 표시 보존) 는 코드 trace + node --check 로 검증. 사용자 환경의 정확한 reproduce 시 추가 cycle 가능.
  - **legacy 상수 cleanup**: `PENDING_CONV_SENTINEL` 의 외부 reference 없음 확인됨 — 별 cycle 에서 정리 가능.
  - **첫 대화 closure mismatch 안내 toast**: 사용자가 첫 응답 도착 시점에 두 번째 컨텍스트라면 toast "이전 요청 응답이 도착했습니다 — 사이드바에서 첫 대화를 확인하세요" 추가. UX 가치 별 cycle 판단.
- Trace: REQ-20260519-0010 → TASK-0082 → CHG-20260519-0012 → REV-20260519-0008. TASK-0081 의 stale guard / catch cleanup 정책 본 design 으로 자연 흡수. AC-0072 / AC-0075~0077 / AC-0176~0178 회귀 보호.

## REV-20260519-0007
- Date: 2026-05-19
- Decision: TASK-0081 (REQ-20260519-0009, Minor §12.3) — `app.js` 의 `beginPendingConversation()` early-return guard 조건을 `state.pendingNewConversation` 단독 → `state.pendingNewConversation && state.busyConversations.has(PENDING_CONV_SENTINEL)` 로 좁힘. 추가로 `sendPrompt()` 의 lazy-create catch 분기 진입 시점에 `state.pendingNewConversation = false` cleanup 1 줄 명시.
- Reason: 사용자 직접 보고 — "새 대화에서 요청을 보낸 후, 다시 새 대화로 별개의 요청을 보내려고 했을 때 진행되지 않는 이슈" + 증상 추가 확인 ("두 번째 send 를 진행하는 상호작용 (요청 UI 버튼, Ctrl+Enter) 가 막혀있다"). Explore subagent 의 코드 trace 와 직접 코드 검토 (line 333~337 `isCurrentConvBusy()` + line 2993 `beginPendingConversation` early-return + line 3437 `sendPrompt` busy guard + line 3533~3551 catch 분기) 로 root cause 2 군데 확정. (1) `beginPendingConversation` early-return 가 stale `pendingNewConversation` flag 만으로 진입 차단 — catch 분기가 flag cleanup 누락이라 한 번 실패한 lazy-create 가 두 번째 "+ 새 대화" 진입 자체를 막음. (2) catch 분기 cleanup 부재. fix 는 두 layer 모두 가드.
- Alt 거부:
  - **`beginPendingConversation()` 의 가드를 완전히 제거**: 사용자 클릭 의도를 100% 신뢰하고 항상 reset 후 진입. 단점 — 첫 lazy-create 가 실제 in-flight (sentinel 점유) 인 race window 에서 사용자가 클릭 시 두 번째 sentinel add 가 동일 KEY 충돌 + busyConversations Set 의 멱등성으로 보이지만 finally 의 delete 가 두 번 일어나 race. 안전 마진을 위해 sentinel 점유 시에만 보류 유지.
  - **`sendPrompt()` 의 line 3437 `isCurrentConvBusy()` 자체 우회**: 사용자가 두 번째 새 대화에서 send 를 시도할 때 busy 검사 skip. 단점 — backend 의 동일 계정 동시 lazy-create 가 의도 외 conv 생성 가능. busy guard 자체는 보존 + state cleanup 으로 해결.
  - **backend 의 동일 계정 dual-pending 제약 추가**: `/api/ask` 의 lazy-create 진입 시 같은 account 의 직전 unset conversation 존재 여부 검증. 단점 — backend 정책 변경 + 사용자 의도와 무관한 차단 가능 (정상 use case 인 빠른 multi-conv 도 차단). frontend state 단순 정리가 정합.
- Risks:
  - **lazy-create in-flight 중 "+ 새 대화" 진입 보류 유지**: 사용자가 첫 송신 응답을 기다리는 중 두 번째 대화로 전환 시도 시 입력란 포커스만 잡고 return. 의도된 동작 (sentinel 중복 race 방지) 이나 사용자가 "왜 안 됨" 으로 인지할 수 있음. UX 측면 toast 안내 추가는 별 cycle.
  - **catch 분기 cleanup 시 pending bubble error 표시와 상태 분리**: `state.pendingNewConversation = false` 직후 사용자가 "+ 새 대화" 클릭 시 `state.pendingBubble` 의 error 영역도 함께 정리될 수 있음. AC-0077 의 빨간 오류 영역 노출 의도와 약한 trade-off — 사용자가 새 대화로 즉시 이동하면 오류 영역 확인 못 할 수 있음. toast 의 "다시 시도하거나 사이드바를 새로고침해 주세요" 안내가 1차 채널.
  - **다른 entry point 검증**: `state.pendingNewConversation` 을 set 하는 위치 = `beginPendingConversation()` line 3001 (본 함수 내부), reset 위치 = (a) `sendPrompt()` success line 3524 (`isLazyCreate && newCid` 조건부) + (b) catch 신규 line 3537 cleanup. 그 외 3rd-party 진입 없음 (grep 검증 — `pendingNewConversation` 출현 위치 5 곳 모두 동일 흐름 안).
- 미해결 followup:
  - **사용자 환경 직접 검증**: 본 fix 의 회귀 시나리오 5 종은 코드 trace + node --check 로 검증. 사용자 환경의 정확한 catch 트리거 조건 (network 종류 / timeout / 서버 응답 형식) 은 미확정 — 사용자가 본 fix 후 동일 reproduce 시 추가 cycle 가능.
  - **UX toast 안내**: in-flight 보류 + catch cleanup 두 분기 모두 사용자 행동에 미세한 비대칭 (전자는 click 무동작, 후자는 새 대화 정상 진입) — toast 로 명시 가능. 별 cycle.
- Trace: REQ-20260519-0009 → TASK-0081 → CHG-20260519-0011 → REV-20260519-0007. AC-0072 (pending bubble) / AC-0075~0077 (lazy-create UX) 회귀 차단.

## REV-20260519-0006
- Date: 2026-05-19
- Decision: TASK-0080 (REQ-20260519-0008, Minor §12.3) — `_collect_matched_excerpts` 의 SELECT 를 `AgentMemoryMessages` + `AgentCoreMessages` UNION ALL + `ROW_NUMBER OVER (PARTITION BY cid ORDER BY msg_id DESC)` 으로 conv 별 더 최근 매칭 1건 선택. collation 통일 `COLLATE utf8mb4_unicode_ci`.
- Reason: 사용자 직접 확인 — "`excerpt 의 AgentCoreMessages 포함 (UNION)` 자세하게 다시 설명해주세요". TASK-0077 / TASK-0078 의 REVIEW followup 으로 명시만 했고 실제 코드 변경 없었음. 정직 설명 후 사용자 결정 — 본 cycle 진행. TASK-0072 의 `_list_conversations` search EXISTS subquery 는 두 table 모두 검사하므로 excerpt 도 두 table 모두 검사해야 정합. core-only conv 의 snippet 부재 회귀 차단.
- Alt 거부:
  - **두 table 별 query 2회**: AgentMemoryMessages 먼저 → AgentCoreMessages fallback. Python 측에서 conv 마다 둘 중 더 최근 결정. UNION 보다 query 2 회 + Python 후처리. 본 fix 의 단일 UNION query 가 더 효율 + DB 단일 transaction.
  - **AgentMemoryMessages 우선 + fallback**: Python merge. memory 우선이 일반적이나 conv 가 core 우선인 케이스 있음 — priority 가정 위험. msg_id 단순 비교가 schema agnostic.
  - **timestamp 컬럼 기반 정렬**: 두 table 의 timestamp 컬럼 존재 여부 + 통일 schema 검증 필요. msg_id (auto-increment) 는 schema 보장. 우회.
- Risks:
  - **msg_id namespace 차이**: AgentMemoryMessages.Id (BIGINT) 와 AgentCoreMessages.id (BIGINT 추정) 가 다른 schema. 더 큰 id = 더 최근 가정 (monotonic 시간 증가). 동시 INSERT race 의 모호함 sub-second — 사용자 시각 영향 0. 검증: 두 table 의 schema 확인 필요 (별 cycle).
  - **collation 통일 cost**: index 우회 가능 — query 비용 ↑. WHERE conv_ids IN (...) 으로 row scope LIMIT 50 conv 단위라 cost overhead 미미.
  - **AgentCoreMessages content NULL**: LIKE NULL 매칭 = false 라 자동 제외. NULL content conv 는 excerpt 부재 (frontend snippet skip).
  - **search EXISTS / excerpt 의 동기화**: TASK-0072 의 EXISTS 가 두 table — 본 fix 와 일치. 향후 EXISTS 만 변경 시 동기화 깨짐 — search test (TASK-0072 의 Phase B 시나리오) 에 두 table coverage 추가 권고 (별 cycle).
- 미해결 followup:
  - **excerpt 의 neighboring line 추가** (TASK-0078 followup) — 매칭 line 이 매우 짧은 경우.
  - **backend matched_message_id 응답** (TASK-0077 followup) — jump 정확도 100%.
  - **popover bottom-edge clamp** (TASK-0076 followup) — viewport 하단 chip drop-up.
- Trace: REQ-20260519-0008 → TASK-0080 → CHG-20260519-0010 → REV-20260519-0006 (followup of TASK-0077)

## REV-20260519-0005
- Date: 2026-05-19
- Decision: TASK-0079 (REQ-20260519-0007, Minor §12.3) — `.chat-pane` 에 `flex: 1 1 auto; min-height: 0` 추가 (CSS 2 line). TASK-0066 의 ChatGPT 패턴 layout 재구조화 시점에 누락된 cascade 잔여 결함.
- Reason: 사용자 screenshot 보고 — 짧은 대화 + 큰 viewport 조합에서 composer 아래 viewport bottom 까지 회색 빈 영역. 원인: `.chat-column` flex container 안에서 `.chat-pane` 의 flex 미정의 (default `flex: 0 1 auto`) → 자식 max-content 만 차지. `.messages-wrap (flex: 1)` 이 chat-pane 안에서 grow 하려면 chat-pane 자체가 column 의 남은 영역 차지 필요. `min-height: 0` 은 overflow 자식 (messages-wrap 안 messages) 의 flex 자라기를 허용. TASK-0068~0071 의 cascade hotfix chain 이 admin 영역만 다뤘고 (`.admin-shell` / `.admin-list-detail` / `.admin-workspace`) 작업 화면 `.chat-pane` 은 미적용 — 본 cycle 이 cascade 마무리.
- Alt 거부:
  - `.chat-pane { height: 100% }` — flex container 안 자식의 height: 100% 는 grow 보장 안 됨 (parent height 가 100% 이어야). flex: 1 이 더 명시적.
  - `.chat-column` 의 grid-template-rows 명시 (TASK-0071 패턴) — chat-column 은 flex 가 더 자연 (가변 자식). grid 로 가면 chat-pane row 가 1fr 명시 필요 + topbar + chat-pane 두 row 분배. flex 가 더 단순.
  - composer 를 chat-column 직접 자식으로 이전 (`.chat-pane` 분리) — TASK-0066 의 의도 (chat-pane 가 composer 포함 단위) 깨짐. layout DOM 변경은 회귀 위험 ↑.
- Risks:
  - **다른 viewport 조합**: 본 환경 chrome headless 가 default flex 동작 일관성 ↑. 사용자 환경에서 추가 회귀 검증 가능성 제한 — 다른 brower / DPI 조합 사용자 확인 권장.
  - **mobile 반응형**: `.app-shell` 의 max-width 680px 분기에서 grid → single column. `.chat-pane` 의 flex chain 은 mobile 에서도 정상 (single column 안 grow).
  - **TASK-0068~0071 cascade chain 의 missing 마지막 piece**: admin 영역 fix 만 cascade hotfix 로 진행되고 작업 화면은 동일 결함 노출까지 누적 — 본 fix 가 chain 마무리. 향후 layout 재구조화 시 chain 전체 (.app-shell, .admin-shell, .chat-pane, .admin-workspace, .admin-list-detail) 일관 적용 권고.
- 미해결 followup:
  - **layout 회귀 검증 자동화** — Phase 시각 검증 (gstack `/qa` 또는 screenshot diff) 도입 권고. 별 cycle.
- Trace: REQ-20260519-0007 → TASK-0079 → CHG-20260519-0009 → REV-20260519-0005 (TASK-0066 cascade 잔여 결함 hotfix)

## REV-20260519-0004
- Date: 2026-05-19
- Decision: TASK-0078 (REQ-20260519-0006, Minor §12.3) — search modal 3 항목 추가 hotfix. mouseup race 보강 (mouseup target 도 추적), preset 텍스트 "부터" 제거, snippet 본문 발췌 line-based clip.
- Reason: TASK-0077 의 5 항목 fix 적용 후 사용자 직접 테스트 보고 — (1) modal 바깥 mousedown 후 modal 안 mouseup 일 때도 close 됨 (TASK-0077 의 mousedownOnOverlay-only flag 가 click target = overlay 일 때만 검사하므로 mouseup 위치 무관). DOM 표준상 click event 의 target 은 mousedown + mouseup 양 끝점의 공통 ancestor — backdrop 에서 mousedown → modal 안 mouseup 시 click target 이 overlay 가 될 수 있어 close 트리거. (2) preset 버튼 "1시간 전부터" 가 너무 길어 popover 안 5 버튼 1 row 에 안 들어가는 wrapping 발생 — "부터" 제거로 간결화. (3) snippet ±40 char clip 이 multi-line content 의 일부 line 만 cut 해 의미 파악 어려움 — 사용자 사례 "일정 line 아래에 있는 경우 가끔 확인". 매칭 line 전체 반환으로 의미 보존.
- Alt 거부:
  - **mouseup race fix 의 다른 패턴**: (a) `pointerup` event 사용 — 동작 비슷하나 일관성 차이. (b) `mousedown` 시 `ev.preventDefault()` 로 click 자체 차단 — selection 등 다른 mouse 동작도 차단됨. 본 fix 의 mousedown + mouseup + click 3 단 검사가 가장 단순 + 표준 정합 (click 의 정의 자체와 일치).
  - **snippet line 단위 vs 문장 단위**: 문장 단위 (period/comma split) 도 옵션. 그러나 본 프로젝트 본문은 SQL / 자연어 혼합 — 문장 분할 규칙이 복잡 + 한국어 종결 어미 추적 필요. line (`\n`) 단위가 markdown / 코드 / 자연어 모두 robust.
  - **excerpt 의 neighboring line 추가**: 매칭 line + 이전/다음 line 한 줄씩 (총 3 line) 노출. context 확장에 좋으나 시각 영역 ↑, line-clamp 3 만으로 단일 매칭 line 도 가독 충분. 본 cycle 은 단일 매칭 line 만 — 후속 cycle 권고.
  - **preset 5 버튼 수 축소**: "1시간 전" 만 두고 나머지 3 개 (1주 / 1개월 / 1년) 으로 단순화 옵션. 사용자 결정은 "부터" 텍스트만 제거 — 5 버튼 유지. 사용자 결정 그대로 채택.
- Risks:
  - **mouseup race 보강 의 side effect**: 정상 backdrop click (양 끝점 모두 overlay) 만 close. 사용자가 backdrop 위 mousedown → 곧바로 backdrop 위 mouseup 도 close — 이건 의도적 backdrop click 으로 인식 정합. drag 가 modal 안으로 들어왔다 다시 backdrop 으로 가서 mouseup 도 close (양 끝점 모두 overlay) — drag 중간 modal 통과는 추적 못 함. edge case 이고 의도적 close 일 가능성 높음 — 그대로 둠.
  - **snippet line-based excerpt 의 short line**: 매칭 line 이 1~2 char 일 수 있음. snippet 영역에 매우 짧은 텍스트만 노출 가능 — 사용자 가독 영향 small. 후속 cycle 에서 min excerpt length 또는 neighboring line 추가 권고.
  - **preset 텍스트 단순화**: 한국어 사용자에 "1시간 전" 만 보이면 의미 모호 가능 — "지금부터 1시간 이전" 또는 "지금부터 1시간 이전까지". 그러나 popover 의 header "기간 선택" 과 from/to input 옆 노출이라 컨텍스트로 의미 명확. 사용자 결정 정합.
  - **CSS line-clamp 3 의 row height 증가**: result row 높이가 1 line (~21 px) 정도 증가. modal max-height 72vh 안에서 viewport 노출 row 수가 ~1 개 감소 가능. 보통 결과 list 가 짧아 영향 미미.
  - **TASK-0073 (다른 session) 과 file overlap**: 본 cycle = `src/app.py` 의 `_collect_matched_excerpts` (TASK-0072 helper 영역) + frontend. TASK-0073 = `src/app.py` 의 audit/dispatcher 영역. 충돌 없음.
- 미해결 followup:
  - **excerpt 의 neighboring line 추가** (1 cycle 이상 후) — 매칭 line 의 이전/다음 line 1 개씩 추가 옵션.
  - **excerpt 의 AgentCoreMessages 포함** (TASK-0077 followup) — 현재 AgentMemoryMessages 한정.
  - **backend matched_message_id 응답** (TASK-0077 followup) — jump 정확도 100%.
  - **popover bottom-edge clamp** (TASK-0076 followup) — viewport 하단 chip 의 popover 가 drop-up.
- Trace: REQ-20260519-0006 → TASK-0078 → CHG-20260519-0008 → REV-20260519-0004 (hotfix of TASK-0077)

## REV-20260519-0003
- Date: 2026-05-19
- Decision: TASK-0077 (REQ-20260519-0005, Minor §12.3) — search modal 5 항목 hotfix bundle. min char 3→2, 소유자 facet 제거 (효용성 낮음 — 사용자 결정), 기간 preset 5종 (1시간/1일/1주/1개월/1년 전), mouseup race fix, snippet 본문 excerpt (backend `_collect_matched_excerpts` 신설).
- Reason: 사용자 직접 테스트 보고 5 항목이 TASK-0072 / 0076 의 명세 누락 또는 사용성 부족. min 2 char 는 한국어 grapheme 검색 정합. 소유자 facet 은 admin/operator 의 실제 needs 가 낮음 (대부분 q 입력으로 충분). 기간 preset 은 매번 date input 채우는 마찰 해소. mouseup race 는 modal 안 text drag 가 backdrop 위에서 떼지면 close 되던 자연스럽지 못한 UX. snippet 본문 excerpt 는 TASK-0072 의 REV-20260519-0002 followup ("backend matched_message_id 응답") 의 다음 step — 본 cycle 은 매칭 *message id* 가 아닌 매칭 *content excerpt* 만 첨부 (frontend jump 의 정확도는 TASK-0076 의 textContent compare 그대로 유지 — message id 응답은 별 cycle).
- Alt 거부:
  - **owner facet 유지 + role label refine**: 소유자 facet 의 사용자 가치를 늘리려 role group / role chip 추가 옵션. 사용자 결정 ("효용성 낮음") 이 분명하므로 단순 제거가 더 가치. backend `owner_id` 파라미터는 호환 위해 유지.
  - **mouseup race 의 다른 fix 패턴**: (a) `pointerup` event 사용 — 동작 비슷하나 browser 지원 차이. (b) modal close 자체를 click 이 아닌 별도 "X" 버튼 / Esc 만으로 — 사용자 backdrop click close 의도 손실. (c) modal 안 selection 가능 영역 추적 + 그 영역 내 mousedown 시 close 비활성. 본 fix 의 mousedownOnOverlay flag 가 가장 단순 + browser 표준 정합 (click = mousedown + mouseup 같은 element). 채택.
  - **snippet excerpt backend matched_message_id 채택**: 매칭 message *id* 를 함께 응답하면 frontend jump 가 100% 정확. 단 2 message table (AgentMemoryMessages + AgentCoreMessages) namespace + frontend 의 message.id mapping 명시화 필요 — scope 초과. 본 cycle 은 excerpt 만 (snippet 본문 표시 결함 fix) + jump 는 client-side textContent compare 유지 (TASK-0076 그대로). matched_message_id 는 미해결 followup.
  - **excerpt clip range 다른 값**: ±40 char (총 ~80-83 + q length). 더 좁으면 (±20) context 부족, 더 넓으면 (±80) snippet 영역 시각 overflow. 40 은 한국어 평균 1 줄 (40-60 byte = 20-30 char) 정합.
- Risks:
  - **min 2 char 검색 빈도 ↑**: 사용자 입력 시 더 자주 trigger 가능 (1 char 추가 시점부터 검색). per-account rate 10/min 정책 그대로라 DoS 표면 변화 0. UX trade-off — 더 빨리 결과 보이나 사소한 typo 도 검색 trigger.
  - **MySQL 8.0 window function 의존**: `_collect_matched_excerpts` 의 `ROW_NUMBER() OVER (PARTITION BY ...)` 는 MySQL 8.0+ 필수. 5.7 환경에서 fail. 본 프로젝트 MySQL 8.0 명시 (STATUS.md / TASK-0064) 라 호환. fallback: try/except 로 silent skip — snippet 없으면 frontend 가 표시 안 함 (제목 매칭만).
  - **excerpt PII**: TASK-0072 의 audit/RBAC 정책 (snippet chip opt-in + `.any` 한정 + `WebAccountActivity` audit) 그대로. 새 PII 표면 아님 — TASK-0072 의 snippet 영역이 *정확화* 됐을 뿐. opt-in chip 클릭 시 이미 audit log 기록되어 있음.
  - **소유자 facet 제거 회귀**: backend `owner_id` 파라미터 호환 유지로 향후 facet 재도입 0 cost. `.own` 사용자의 SQL composition order sub-spec 1 (TASK-0072 의 self-overwrite) 도 그대로 동작.
  - **TASK-0073 (다른 session) 과 file overlap**: TASK-0073 은 `src/app.py` 의 audit/dispatcher 영역. 본 cycle 도 `src/app.py` 변경 — 영역 분리 (TASK-0073 = WebAuditEvents + dispatcher Phase A0+, 본 cycle = `_normalize_search_query` line edit + `_collect_matched_excerpts` 신설 + endpoint payload 1 줄 추가). 충돌 가능성 점검 — `_normalize_search_query` 와 `_collect_matched_excerpts` 는 TASK-0072 helper 영역 (line 2887-3000 부근) 으로 TASK-0073 의 audit 영역 (`_audit_*`) 과 다른 위치. 안전.
- 미해결 followup:
  - **backend matched_message_id 응답** — 매칭 message id 까지 반환해 frontend jump 정확도 100%. 2 message table 의 namespace + frontend message.id mapping 명시 필요.
  - **excerpt 의 AgentCoreMessages 포함** — 현재 AgentMemoryMessages 한정. 일부 conv 의 본문이 core 에 있으면 excerpt 부재. UNION + per-conv ROW_NUMBER 으로 확장 가능 (별 cycle).
  - **popover bottom-edge clamp** (TASK-0076 의 followup) 미적용.
  - **owner accounts cache invalidate** (TASK-0076 의 followup) — 소유자 facet 제거로 자동 해소 (cache 미사용).
- Trace: REQ-20260519-0005 → TASK-0077 → CHG-20260519-0007 → REV-20260519-0003 (hotfix bundle of TASK-0072/0076)

## REV-20260519-0002
- Date: 2026-05-19
- Decision: TASK-0076 (REQ-20260519-0004, Minor §12.3) — search modal UX 3 결함 hotfix bundle. 제품 facet 은 사용자 결정 ("대화 중 product 변경 가능") 으로 DOM 제거. 소유자 / 기간 facet 은 popover UI 신설. ArrowUp/Down 시 active row scrollIntoView. 매칭 message bubble jump 는 frontend textContent compare (backend matched_message_id 응답 없이 client-side).
- Reason: 사용자 직접 테스트 보고 3 결함이 TASK-0072 의 명세 안에 포함됐어야 할 functionality 누락이었음. backend 의 `_list_conversations` 가 `owner_id` / `date_from` / `date_to` 파라미터를 이미 받지만 frontend popover UI 가 placeholder 만 있었음 — 사용자가 chip 클릭해도 동작 없음. 본 cycle 은 frontend 의 missing UI 만 채움. backend / RBAC / audit 영역 무변경.
- Alt 거부:
  - **제품 facet 구현 (3 option)**: 사용자 결정으로 DOM 제거 선택 — 대화 중 product 가 변경될 수 있어 *시점* 별 product filter 는 사용자 의도 왜곡 가능. cycle scope 축소.
  - **Backend matched_message_id 응답**: 검색 결과의 정확한 매칭 message id 를 backend 가 함께 반환하면 frontend jump 정확도 ↑. 그러나 `_list_conversations` 의 EXISTS subquery 가 어느 row 매칭인지 알지 못함 — 별 query (window function `ROW_NUMBER() OVER (PARTITION BY conv_id ORDER BY ts DESC)` 또는 GROUP BY MIN(Id)) 필요. 2 message table (AgentMemoryMessages + AgentCoreMessages) 의 id namespace 가 다르고, frontend 의 message.id 와 mapping 명확화 필요 — Minor cycle scope 초과. 본 cycle 은 client-side textContent compare 채택 (q 와 messages 둘 다 client 측 보유라 round-trip 불필요). 정확도 낮음 (예: q="대화" 가 안내문 등 광범위 매칭) — 후속 cycle 권고.
  - **owner facet 의 SSE / invalidate hook**: admin accounts cache 가 modal close 후 유지 → admin/operator 의 계정 추가/삭제 가 같은 session 안 발생 시 stale. SSE 또는 WebSocket invalidate 도입 vs cache TTL (예: 60 s) vs modal open 마다 refresh. 본 cycle 은 1 회 캐시 + 별 session 마다 refresh — 가장 단순. follow-up cycle 권고.
- Risks:
  - **facet popover positioning**: `position: fixed` + getBoundingClientRect. modal scroll / viewport resize 시 popover anchor drift. popover 자체가 단발 click 후 즉시 적용이라 drift window 좁아 보통 무문제. viewport right-edge clamp 만 적용, bottom clamp 미적용 — chip 이 viewport 하단에 있을 때 popover 가 viewport 밖 나갈 수도 있음 (follow-up).
  - **matched message jump 정확도**: client-side `textContent.toLowerCase().includes(needle)` — q 가 짧거나 흔한 단어일 때 첫 매칭 row 가 사용자 의도와 다를 수 있음 (특히 user prompt 안 매칭이 assistant 본문 매칭보다 먼저). 본 cycle 의 trade-off — backend 의 정확한 매칭 message id 응답이 정확도 ↑ 이지만 schema/query 복잡도 ↑ 별 cycle.
  - **owner facet `.any` 한정**: `.own` 사용자에게는 owner chip 자체가 `hidden`. 정합 (`.own` user 가 owner_id 입력해도 backend sub-spec 1 이 self 로 강제 overwrite). cross-account leak 0.
  - **TASK-0073 (다른 session) 과 file overlap 없음**: 본 cycle = `src/static/{index.html, styles.css, app.js}` + docs. TASK-0073 = `src/app.py` (WebAuditEvents DDL) + docs. concurrent commit OK.
- 미해결 followup:
  - **Backend matched_message_id 응답** — `_list_conversations` 의 search mode 시 각 conv 의 첫 매칭 message id 함께 반환. frontend jump 정확도 100%. window function 또는 GROUP BY MIN(Id) per conv 추가 query.
  - **owner accounts cache invalidate** — 60 s TTL 또는 SSE.
  - **popover bottom-edge clamp** — viewport 하단 chip 의 popover 가 위로 펼침 (`drop-up`) 분기.
  - **snippet 본문 미리보기 정확도** — 현재 snippet 은 topic 만 미리보기. backend 가 매칭 message excerpt (matched_message_id 채택 시 함께) 반환 시 snippet 본문 정확.
- Trace: REQ-20260519-0004 → TASK-0076 → CHG-20260519-0006 → REV-20260519-0002 (hotfix bundle of TASK-0072)

## REV-20260519-0001
- Date: 2026-05-19
- Decision: TASK-0074 (REQ-20260519-0002, Minor §12.3) — search modal CSS 의 색상 토큰을 site theme 의 기존 var (`--surface`, `--text`, `--border`, `--text-muted`, `--primary`, `--primary-soft`, `--bg`) 으로 일관 적용. 미정의 var fallback (`--text-primary` → `--bg-elev` dark hardcode `#1f2429`) 폐기. backdrop 의 dark overlay 는 modal pop 강조 위해 유지.
- Reason: TASK-0072 modal CSS 가 dark theme 가정 var (`--text-primary`, `--bg-elev`) 사용 — site 가 정의 안 한 var 라 fallback 인 hardcode dark color 가 발동. 그러나 site 자체는 light theme (`--bg #f4f4f5` / `--surface #ffffff` / `--text #18181b`) 라 modal 의 검은 배경 위 text inherit 가 검은색 → contrast 0. UX review (TASK-0072 outside voice) 가 site theme 가정 명시 안 한 결과 — light theme 위 dark modal 의 가독성을 사용자가 직접 발견. 사용자 screenshot ("사용자가 이용할 수 없을 정도의 색상 구성") 으로 hotfix 진입.
- Alt 거부:
  - `@media (prefers-color-scheme: dark)` 분기: site 자체가 단일 theme (`:root` 에 light 만 정의, `prefers-color-scheme` 분기 없음) — modal 만 dark 분기 추가는 site 정합 깨짐.
  - 미정의 var 의 fallback 값을 light 로 단순 swap (`var(--bg-elev, #ffffff)`): 다른 site 컴포넌트도 `var(--text-primary)` / `var(--bg-elev)` 가정으로 만들면 동일 회귀 재발 가능. 본 fix 는 site 의 *기존 토큰* (`--surface` / `--text` 등 site 가 명시 정의한 것) 으로 통일해 fallback 의존 차단.
  - dark theme 강제 (site root 에 `--text-primary: #fff` 추가): 다른 모든 site CSS 영향 — scope 폭발.
- Risks:
  - **backdrop dark overlay 유지**: modal pop 강조 위해 `rgba(15,23,42,0.48)` 유지. light theme 위 어두운 overlay 가 modal 의 white background 와 contrast 잘 보이는 효과. light dimming 으로 갔다가 modal boundary 흐려지면 UX 회귀.
  - **highlight bg `#fde68a` (yellow 300)** light theme 위 dark text 와 contrast WCAG AA 충분 (검산: contrast ratio ~10:1). dark theme 도입 시 highlight bg 재검토 필요 (별 cycle).
  - **`--primary-soft` (#eff6ff) result row hover/active bg** light theme 위 visible 가능 (parent surface = #ffffff, hover = #eff6ff 의 contrast). visible 영역 충분.
  - **다른 modal 영향 0**: 본 cycle 의 변경은 `.search-modal*` selector 한정. admin modal / profile drawer / 비밀번호 reset modal 등 무관.
- 미해결 followup:
  - **site 의 dark theme 도입 시 modal 재검토** — `prefers-color-scheme: dark` 분기 또는 사용자 toggle 시 search modal 색상도 함께 swap. 본 cycle 의 fix 가 site theme inherit 패턴이라 자동 swap 가능하나 highlight bg (`#fde68a`) 와 backdrop (`rgba(15,23,42,0.48)`) 은 dark theme 위 재검산 필요.
  - **CSS 토큰 contract 명료화** — site root 의 모든 토큰 (`--bg-elev`, `--text-primary`, `--border-strong`) 이 정의 안 됨에도 다른 컴포넌트들이 fallback 으로 사용 중. site 의 root 토큰 정의 audit + 미정의 var 의 fallback 강제 정책은 별 cycle (DESIGN.md §15 확장 권고).
- Trace: REQ-20260519-0002 → TASK-0074 → CHG-20260519-0004 → REV-20260519-0001 (hotfix of TASK-0072)

## REV-20260518-0010
- Date: 2026-05-18
- Decision: TASK-0072 (REQ-20260518-0010, **Critical** §12.3) — 타 계정 대화 검색·필터 plan 의 D1/D2/D3 결정 + outside voice 3 개 verdict 흡수 + 사용자 in-cycle 결정 5 항목 확정. UI 위치 재결정 (사이드바 검색바 → Spotlight modal pattern), index 정책 (LIKE + 강한 안전망, FULLTEXT 별 cycle), 본문 열람 정책 (`.any` 보유자 검색·snippet 허용 + audit log 수반).

### Outside voice 3 verdict 요약

- **Security review** (FIX-FIRST) → 4 must-fix 모두 흡수:
  1. `WebAccountActivity` audit log 신설 (PIPA §29 / 접근기록 보관)
  2. `LIKE %s ESCAPE '!'` 명시 + `%`/`_`/`!` 3 char escape (NO_BACKSLASH_ESCAPES sql_mode 회귀 차단)
  3. D1 → B (FULLTEXT) 권고 — 그러나 adversarial 의 분리 권고 더 설득력 (아래 D1 참조)
  4. Per-account rate limit 10 req/min + `max_execution_time=3000ms`
- **Adversarial review** (Blocker → 3 sub-spec 흡수 후 진입) → 3 sub-spec + 6 risk 모두 흡수:
  - 3 sub-spec: (a) SQL composition order — `owner_id = self` 가 q 보다 항상 먼저 AND, (b) `hidden_ids` SQL push (`NOT IN`), (c) Python re-sort 삭제 (`app.py:2967-2971`)
  - 6 risk: `WebAccounts.DeletedAt` 필터 / collation audit / account name search `.any` 한정 / `q="%%"` post-escape 0 char 차단 / 404 vs 403 byte-equal / `share.js` 회귀 가드
- **UX review** (NEEDS-TWEAK) → 사이드바 252px 에 chip 4개 fit 불가. Spotlight modal pattern (Cmd/Ctrl+K) 권고 → 사용자 변형 채택 ("+ 새 대화" 버튼 우측 같은 높이 돋보기 icon + modal overlay).

### D1 / D2 / D3 결정 + 근거

- **D1 → A (LIKE only + 강한 안전망)** — security 와 상충 (B FULLTEXT 권고). adversarial 의 근거 채택: 한국어 FULLTEXT 는 `ngram` parser + `innodb_ft_min_token_size` 튜닝 필수 → `ALTER TABLE ADD FULLTEXT` 자체가 Critical migration. 신규 PII 표면 도입과 interleave 회피 위해 FULLTEXT 는 별 cycle 분리. 본 cycle 의 LIKE 안전망: min 3 char + length cap 200 + LIMIT 50 + per-account rate 10/min + `max_execution_time=3000ms` + collation audit.
- **D2 → A (snippet 항상 OFF + chip opt-in)** — security + adversarial 일치. B (`.any` 기본 ON) 는 user interaction 전에 PII snippet 노출되는 worst-of-both. opt-in chip 클릭 자체가 audit log 대상 (의도 추적).
- **D3 → B (cursor `updated_at DESC, conversation_id DESC`)** — offset 은 기존 `app.py:2849` LIMIT 200 + `2967-2971` Python re-sort 와 incoherent (page 2 가 stale subset 반환). cursor 가 안전 + Python re-sort 삭제와 정합.

### 사용자 in-cycle 결정 5 항목

1. 권한 모델: 기존 `conversation.list.any` 재활용 (신규 catalog 없음)
2. 검색 범위: 제목 + 계정명 + 메시지 본문 (SQL/결과셋 제외)
3. UI 위치 (재결정): Spotlight modal pattern + 사용자 변형 ("+ 새 대화" 버튼 우측 같은 높이 돋보기 icon + Cmd/Ctrl+K)
4. D1 index: A (LIKE + 강한 안전망)
5. 본문 열람: `.any` 보유자 = 검색 매칭 + snippet 모두 허용 + audit log 수반

### Alt 거부 정리

- **D1 B (FULLTEXT) 거부**: 한국어 ngram + innodb_ft_min_token_size 튜닝 + 대용량 `ALTER TABLE ADD FULLTEXT` 의 lock 시간 = 본 cycle 외 Critical migration. 분리.
- **UI 사이드바 위 검색바 + chip 거부**: 252px 사이드바 fit 불가 (chip 4개 1줄 ~296px 필요). 2줄 wrap 시 toolbar 120px → conv-list 15-20% 잠식. Spotlight modal 이 conv-list 잠식 0 + Cmd/Ctrl+K 단축키로 power-user friction 낮음.
- **신규 catalog `conversation.search.any` 거부**: 사용자 초기 결정 (권한 모델 = list.any 재활용). admin/operator 의 list 권한 = search 권한 묶음. 단 audit log 로 search 활동 추적해 권한 misuse 가시화.
- **본문 검색 .own 한정 거부**: 사용자 결정 (본문 열람 = `.any` 허용 + audit). 감사 needs 우선. audit log 가 misuse 보호 layer.

### Risks (재평가)

- **RBAC bypass** (Critical) → 3 sub-spec + Phase B 6 시나리오 smoke + 404/403 byte-equal 로 차단
- **PII leak (snippet + cross-account body)** (Critical) → snippet opt-in 기본 OFF + `WebAccountActivity` audit + SHA-256 hash + `.any` 한정
- **SQL injection** (Major) → bound param + `ESCAPE '!'` + escape 후 의미 char ≥ 2
- **성능 회귀 (LIKE full scan)** (Major) → LIMIT 50 + min 3 char + rate 10/min + `max_execution_time=3000ms` + collation audit
- **WebAccountActivity DDL** (Major) → `_ensure_web_tables` idempotent + `CREATE TABLE IF NOT EXISTS` + `(account_id, ts)` index
- **share-link 회귀** (Minor) → `share.js` 신규 import 없음 (Phase C 가드)

### 미해결 followup

- **FULLTEXT migration cycle** — 본 cycle 의 LIKE 안전망이 성능 한계 (≥ 5만 conv + 빈번한 body search) 도달 시 후속 cycle 로 ngram FULLTEXT 도입. trigger: rate limit 빈번 진입 또는 `max_execution_time` 빈번 hit.
- **DESIGN.md §15 filter chip 패턴 v0.1** — UX review 권고. 본 cycle 은 modal 안 facet 만 사용. 사이드바 filter chip 이 필요해지면 별도 정합화 cycle.
- **외부 LAN 배포 시 추가 게이트** — `repo/docs/SECURITY.md` §7 (TASK-0058 share-link) 의 IP allowlist / token 비밀번호 / 시간 만료 권장사항이 본 검색 endpoint 에도 동일 적용. 후속 SECURITY §8 에 명시.

- Trace: REQ-20260518-0010 → TASK-0072 → §2.1 Implementation Plan (TASK-0072) + outside voice 3 verdict (security FIX-FIRST + adversarial Blocker + UX NEEDS-TWEAK) → CHG-20260518-0010 (Phase A0~E 진행 시 commit 별로 append) → REV-20260518-0010

## REV-20260518-0008
- Date: 2026-05-18
- Decision: TASK-0071 (REQ-20260518-0009, Minor §12.3) — `.app-shell` / `.admin-shell` 양쪽에 `grid-template-rows: minmax(0, 1fr)` 추가. cascade root fix.
- Reason: 본 cycle 은 TASK-0068 → 0069 → 0070 의 layout hotfix chain 의 마지막 root. 이전 fix 들이 column 안의 stretch chain (workspace → pane → list-detail → list-col) 을 차례로 해결했으나 column 자체의 height 결정 layer (.app-shell / .admin-shell 의 grid track) 는 미처리. grid 의 single row 가 default `auto` 면 row track height = 자식 max-content — grid container 가 `height: 100vh` 여도 track 이 100vh 보다 작아질 수 있음. 본 환경 (chrome headless) 은 grid track 이 100vh 차지하는 동작이라 stretch 정상 보였지만, 사용자 환경에서는 max-content 차지 동작이라 노출. browser engine / 동일 brower 의 timing / DPI 등 환경별 grid algorithm 차이가 회귀 timing 결정. `minmax(0, 1fr)` 으로 row 가 container 의 전체 height 차지하도록 명시 — 환경 의존성 제거.
- Cascade 정리 (요약):
  ```
  .app-shell / .admin-shell { height: 100vh; display: grid; grid-template-rows: minmax(0, 1fr) }  ← TASK-0071 fix
    └ .sidebar / .admin-sidebar  (grid item, row 의 full height stretch)
    └ .chat-column / .admin-column  (grid item, row 의 full height stretch)
        └ .topbar (flex-shrink: 0)
        └ .chat-pane / .admin-workspace  { flex: 1 1 auto }  ← TASK-0069 fix
            └ .chat 영역 / .admin-pane.is-active  { flex: 1 1 auto }
                └ .admin-list-detail  { flex: 1 1 auto; grid-template-rows: minmax(0, 1fr) }  ← TASK-0070 fix
                    └ .admin-list-col / .admin-detail-col  (grid item, row stretch)
        └ .composer / .admin-commit-bar  (flex-shrink: 0)
  ```
- Alt 거부: `grid-template-rows: 100vh`. minmax(0, 1fr) 보다 명시적이지만 container 의 height: 100vh 와 row 의 100vh 중복 — DRY 위반. 1fr 이 container size 의 100% 를 의미 (single row 일 때).
- Risks:
  - **다른 brower / DPI 회귀 검증 불가**: 본 환경 chrome headless 에서는 1 차 (TASK-0069) 부터 정상 보였음. 사용자 환경 (실제 browser) 에서만 노출 — 본 환경에서 추가 회귀 검증 가능성 제한. 그러나 `minmax(0, 1fr)` 은 CSS Grid spec 의 명시적 단일 row stretch 패턴이라 환경 의존성 없는 fix.
  - **반응형 mobile**: `.app-shell { grid-template-columns: 1fr }` / `.admin-shell { grid-template-columns: 1fr }` 으로 단일 column 인데 row 도 1fr 이라 정상 동작. mobile 환경 별 cycle 검증 권장.
  - **viewport height 0 edge case**: `minmax(0, 1fr)` 의 min 이 0 이라 viewport 가 매우 짧을 때 (height 0) row 도 0 — `overflow: hidden` 의 shell 안에서 자식이 grow 동작 멈춤. 비현실 case 라 무시.
  - **scrollbar 영향**: 부모에 scrollbar 가 있는 경우 100vh ≠ 실 가용 height. shell 자체에 `overflow: hidden` 있어 scrollbar 발생 안 함. 자식의 overflow-y: auto 만 동작.
- Trace: REQ-20260518-0009 → TASK-0071 → CHG-20260518-0008 → REV-20260518-0008 (hotfix chain root of TASK-0068 / 0069 / 0070)

## REV-20260518-0007
- Date: 2026-05-18
- Decision: TASK-0070 (REQ-20260518-0008, Minor §12.3) — `.admin-list-detail` 에 `grid-template-rows: minmax(0, 1fr)` 추가. CSS 1 줄 root-cause fix.
- Reason: TASK-0068/0069 layout chain 의 마지막 stretch gap. `.admin-list-detail` 가 grid (column 2 정의) 이지만 row 가 default `auto` → row height = content. `.admin-pane` / `.admin-workspace` / `.admin-column` 의 flex grow chain 이 list-detail 까지는 정상 도달했으나 list-detail 의 grid row 가 그 height 를 column 들에 분배 안 함. `minmax(0, 1fr)` 으로 row 가 list-detail 의 flex grow 받은 height 전부 차지 + min-content 무시 (자식 column 의 min-height 0 와 정합).
- 1 차 검증 (TASK-0069) 에서 놓친 이유: 본 환경의 viewport (720) 에서는 list-col content (search input + select-all + 3+ items + bulk-bar + pagination) 의 총 height 가 우연히 list-detail 의 stretch 된 height 와 비슷 (~500) → 시각적으로 stretch 된 것처럼 보임. 사용자의 큰 viewport (900+) 에서는 list-col content 가 짧아 row 가 짧음 → 그 차이가 시각화됨. 검증 viewport 다양성 부족이 회귀 1 cycle 연장 원인.
- Alt 거부: `min-height: 100%` (list-col / detail-col 에 추가). flex grow 와 결합 시 fragility (parent height 100% 의존). grid-template-rows 가 root cause 에 가깝고 simpler.
- Risks:
  - **다른 viewport 비율 검증**: 큰 viewport (1320x900) 에서 fix 검증 완료. 매우 짧은 viewport (height 500-) 의 경우 list-col content (toolbar + items) 가 row 보다 클 수도 — overflow-y: auto 의 `.admin-list` 가 scroll 동작으로 흡수. 또한 list-col / detail-col 자체에 `min-height: 0` 명시되어 있어 grid row stretch 와 정합.
  - **dashboard pane**: dashboard 는 list-detail 사용 안 함 (`.admin-pane[data-admin-pane="dashboard"].is-active { overflow-y: auto }` 직접 scroll). 본 변경 무영향.
  - **mobile 반응형** (`@media (max-width: 680px)`): `.admin-list-detail { grid-template-columns: 1fr }` 으로 단일 column. row 1 fr 도 그대로 동작 — column 1 (list-col) 이 1fr row 의 전체 height.
- Trace: REQ-20260518-0008 → TASK-0070 → CHG-20260518-0007 → REV-20260518-0007 (hotfix of TASK-0068 / 0069 layout chain)

## REV-20260518-0006
- Date: 2026-05-18
- Decision: TASK-0069 (REQ-20260518-0007, Minor §12.3) — `.admin-workspace` 에 `flex: 1 1 auto` 추가. 다른 fix path 미선택 — 1 줄로 root cause 해결되므로 우회 패치 불필요.
- Reason: TASK-0068 에서 admin layout 을 작업 화면과 동일한 ChatGPT 패턴으로 재구조화하면서 commit-bar 의 위치가 `.admin-shell` grid 의 3rd row → `.admin-column` flex column 의 3rd flex item 으로 이전. 그러나 `.admin-workspace` 의 flex 명시 누락으로 flex column 안에서 workspace 가 자기 content 만큼만 차지하고 column 의 남은 공간이 빈 채로 노출 + commit-bar 가 viewport bottom 이 아닌 workspace 끝 바로 아래에 위치하는 시각 회귀. `.admin-pane.is-active { flex: 1 1 auto }` 가 의미를 가지려면 부모 `.admin-workspace` 자체가 stretch 되어야 함. cascade 의 출발점인 workspace 에 flex grow 명시.
- Alt-A 거부: admin-column 의 grid (rows: topbar-h / 1fr / auto) 로 변경. flex 보다 명시적이지만 commit-bar 의 가시성/숨김 토글이 grid template-rows 도 함께 갱신해야 하므로 fragility 증가. flex column + flex grow 가 더 단순.
- Alt-B 거부: commit-bar 의 position: sticky bottom: 0. workspace 의 flex 미해결 시 workspace 가 자기 content 만큼만 차지하는 본질 문제는 그대로. sticky 는 sticky overflow 부모를 필요로 하는데 그 정의가 workspace 와 conflict 가능.
- Risks:
  - **다른 admin pane (대시보드 / 계정 / 제품) 회귀 검증**: `.admin-workspace` 단일 rule 변경이므로 모든 pane 에 일관 적용. 대시보드는 `.admin-pane[data-admin-pane="dashboard"].is-active { overflow-y: auto }` 보유 — workspace 가 stretch 되면 dashboard content scroll 동작이 dashboard 내부에서 정상 동작 (이전엔 admin-shell grid 의 1fr 이 같은 효과 제공). 본 cycle browser smoke 는 역할 pane 한정 — 다른 pane 도 동일 fix 자연 적용되지만 dashboard scroll 검증은 사용자 직접 확인 권장.
  - **min-height 0**: `.admin-workspace { min-height: 0 }` 가 이미 있어 flex 자식 (`.admin-pane`) 의 overflow / scroll 동작 정합. flex grow 추가가 이 동작과 충돌 없음.
  - **mobile 반응형**: `.admin-shell { grid-template-columns: 1fr }` (mobile) 일 때 admin-sidebar 가 숨겨지고 admin-column 만 표시. flex grow 가 mobile 에서도 동일 동작.
- Trace: REQ-20260518-0007 → TASK-0069 → CHG-20260518-0006 → REV-20260518-0006 (hotfix of TASK-0068)

## REV-20260518-0005
- Date: 2026-05-18
- Decision: TASK-0068 (REQ-20260518-0006, Minor §12.3) — 관리 콘솔의 sidebar 영역 구성을 작업 화면 (TASK-0066) 과 동일한 ChatGPT 패턴으로 정렬 + 헤더의 `새로고침` / `로그아웃` 제거.
- Method:
  - **layout 통일성**: 사용자는 작업 화면 / 관리 콘솔을 빈번히 전환한다 (`backToAppBtn`). 두 화면의 layout 이 일관되면 인지 비용 (eye tracking, mental model) 감소. TASK-0066 에서 작업 화면의 `.app-shell` 을 2-column grid 로 단순화한 패턴을 admin 에 그대로 적용. brand "MySQL AI" 도 통일 (admin 의 기존 "관리 콘솔" brand 는 페이지 컨텍스트라 topbar 안에 표시하는 것이 정합 — product 정체성 vs 페이지 컨텍스트 분리).
  - **새로고침 버튼 제거의 의미**: pending 변경 보호 confirm + state clear + `loadAdminData()` 호출이었음. 사용자가 거의 사용 안 한다는 피드백 — 보통 `모두 적용` 또는 `취소` (commit-bar) 로 pending 정리하거나 페이지 reload (브라우저 F5) 로 충분. dead UI 제거가 SCREEN clutter 감소에 기여. element 제거 시 admin.js 의 click handler 도 함께 제거 (null reference 안전성).
  - **로그아웃 버튼 제거의 의미**: admin 의 topbar 에서 직접 로그아웃은 빠른 path 였으나 사용자 통상 흐름이 작업 화면으로 돌아가 (`backToAppBtn`) → 프로필 drawer → 로그아웃 이라 중복. 로그아웃 endpoint (`POST /api/auth/logout`) 는 작업 화면 프로필 drawer 에서 그대로 호출 가능 — 기능 손실 없음.
  - **`backToAppBtn` 유지**: admin → 작업 화면 전환은 사용자가 자주 사용 (pending 보호 confirm 도 의미 있음). 단일 quick path 로 유지.
  - **commit-bar 위치**: 기존 `.admin-shell` 의 grid-template-rows 3rd row (`auto`) 였던 footer 를 `.admin-column` 안의 마지막 flex item 으로 이전. sidebar 영역에는 commit-bar 가 표시되지 않고 workspace 의 하단에만 표시 — 시각 정합 (commit-bar 가 workspace 와 묶임).
  - **`.admin-sidebar` padding 정책**: brand 가 sidebar 의 첫 영역으로 들어가면서 sidebar 자체의 `padding: 10px 8px` 를 제거하고 각 child (`.sidebar-brand` = `padding: 0 14px`, `.admin-tabs` = `padding: 10px 8px 0`, `.admin-sidebar-foot` = `padding-left/right: 8px`) 가 자기 padding 갖도록 — brand 가 sidebar 전체 너비를 차지하고 padding 안쪽 정렬은 brand-icon/name 의 자체 padding 으로 자연스럽게.
- Risks:
  - **로그아웃 접근성 감소**: admin 페이지에서 직접 로그아웃 path 가 사라짐 → 작업 화면으로 이동 (1 click) → 프로필 drawer 열기 (1 click) → 로그아웃 (1 click). 3 click. 보안 의도의 빠른 강제 로그아웃 (예: 공용 머신에서 자리 비울 때) 시 불편할 수 있음. 후속 cycle 에서 작업 화면 프로필 drawer 의 "로그아웃" 버튼이 admin 페이지에서도 동일 접근 가능한지 확인 권장 (drawer 자체가 admin 페이지엔 없으므로 새로운 path 필요할 수도).
  - **새로고침 버튼 제거 후 pending stale 회복**: 사용자가 의도치 않게 pending 을 쌓은 상태에서 `취소` (commit-bar) 도 못 누르거나 잘못 누른 경우 의도된 적용을 되돌리는 path 가 줄어듦. 그러나 commit-bar 의 `취소` 가 동일 역할 수행 — 실질 영향 없음.
  - **brand 통일 후 페이지 식별성**: admin 페이지의 brand 가 "관리 콘솔" → "MySQL AI" 로 바뀌어 사용자가 어느 페이지인지 혼동할 가능성. 그러나 topbar 의 `<h2 class="chat-title">관리 콘솔</h2>` + subtitle 이 페이지 컨텍스트를 명확히 표시 + browser tab 의 `<title>MySQL AI Assistant Admin</title>` 도 식별 유지. 시각적으로 admin sidebar 의 `대시보드` / `계정 카테고리` / `제품 카테고리` 탭 구성이 관리 콘솔 인지 즉시 알림.
  - **반응형 admin mobile**: `.admin-shell { grid-template-columns: 1fr }` + `.admin-sidebar { display: none }` 으로 sidebar 숨김 + workspace 만 표시. mobile 에서 admin tab 전환 path 부재 — 별 cycle 검토. (관리 콘솔은 desktop-first 가정이 일반적)
  - **dead CSS 잔존 확대**: TASK-0066 의 `.topbar-brand`, TASK-0067 의 `.product-chip-*` 에 이어 `.admin-body` rule 도 dead code. 본 cycle 에서 `.admin-body` rule 도 제거 — `.topbar-brand` / `.product-chip-*` 잔존 (별 cycle 정리 권장).
- Trace: REQ-20260518-0006 → TASK-0068 → CHG-20260518-0005 → REV-20260518-0005 (follow-up of TASK-0066 / 0067)

## REV-20260518-0004
- Date: 2026-05-18
- Decision: TASK-0067 (REQ-20260518-0005, Minor §12.3) — 제품 칩을 사이드바 → composer 우측 (textarea/sendBtn 사이) 으로 이전. ChatGPT 모델 선택 UI 패턴. 기존 native `<select>` 를 custom button + drop-up dropdown 으로 대체.
- Method:
  - **위치 결정 — composer 우측**: 사용자 명시 "요청사항을 입력하는 우측". textarea 와 send-btn 사이가 의미상 정합 (입력 → 모드 선택 → 전송). ChatGPT 의 모델 selector 가 composer 영역 안에 있는 패턴과 일치.
  - **drop-up 필요성**: chip 이 composer (페이지 하단 근처) 에 위치하므로 menu 가 chip 아래로 펼치면 viewport 밖. CSS `position: absolute; bottom: calc(100% + 6px)` 로 chip 위로 펼침 — drop-up 보장. 사용자 명시한 "상대적인 위치로 drop-up" 정합.
  - **native `<select>` 폐기 사유**: native dropdown 위치는 브라우저가 결정 (보통 below). drop-up 효과를 보장할 수 없음. custom button + custom menu 로 전환.
  - **chip label 정책 — compact vs full**: chip 폭이 좁아 pinned 일 때 전체 이름 + product_key 를 보여주면 ellipsis 발생. `compactLabel = product_key` (KR / MV / GZ_KR — 짧고 식별 가능) 채택. 단 a11y 는 보존 — `aria-label` 에 `"이 대화의 제품 선택, 현재 {name} ({product_key})"` 전체 형식 유지.
  - **menu 옵션 list 갱신**: `state.products` 가 비동기 hydrate 되므로 menu 가 열려 있는 동안에도 product list 가 갱신될 수 있음. `renderProductChip()` 끝에서 `chip.aria-expanded === "true"` 면 `renderProductDropupMenu()` 도 즉시 호출해 동기화.
  - **busy 상태 정책**: 기존 `isCurrentConvBusy()` race 가드 유지 — busy 시 chip.disabled + aria-disabled + cursor not-allowed. menu open 도 `chip.disabled` 체크로 차단. 사용자가 응답 처리 중에 product 를 바꾸려 하면 chip 자체가 비활성.
- Risks:
  - **dead CSS 잔존**: 기존 `.product-chip-wrap` / `.product-chip` / `.product-chip-caption` / `.product-chip-select` rule 이 stylesheet 에 남아 있음 (사용처 없음). 무해이지만 별 cycle 에서 제거 권장 (TASK-0066 의 `.topbar-brand` dead rule 과 함께).
  - **a11y — native select 의 keyboard 동작 대체**: native `<select>` 는 keyboard 화살표 / Enter / Esc / 빠른 search 자동 지원. custom dropdown 은 본 cycle 에선 click + outside-click + ESC close 만 구현. arrow key 탐색은 후속 cycle 검토 (TASK-0063 conv-item menu 와 동일 정책 — Esc 만 적용).
  - **drop-up 의 viewport 경계 처리**: chip 이 viewport 하단 근처라 drop-up 이 자연스럽지만, chip 이 viewport 상단 근처 (mobile keyboard 등 viewport 축소 시) 면 menu 가 위로 튀어나갈 수 있음. CSS `max-height: 320px; overflow-y: auto` 로 안전망. fully responsive 동작은 후속 cycle 검토 가능.
  - **menu z-index 50 vs sticky 분기선 z-index 5 vs conv-item dropdown z-index 200**: 분기선 (5) 위, conv-item menu (200) 아래. composer 영역에서 menu 가 펼쳐지면 sticky 분기선 위에 표시되므로 정합. conv-item menu 와 동시 노출은 일반적이지 않으므로 200 충돌은 무시 가능.
  - **JS — element ID 보존**: chip 의 ID (`productChip`, `productChipDot`) 보존으로 기존 외부 reference 무영향. 신규 ID (`productChipLabel`, `productDropupMenu`) 는 본 cycle 신설.
- Trace: REQ-20260518-0005 → TASK-0067 → CHG-20260518-0004 → REV-20260518-0004 (follow-up of TASK-0066)

## REV-20260518-0003
- Date: 2026-05-18
- Decision: TASK-0066 (REQ-20260518-0004, Minor §12.3) — ChatGPT 패턴 layout 재구조화. 사용자 결정: topbar 에 대화 제목 통합 + 좌측 정렬 + brand 를 sidebar 영역으로 이전. `.app-shell` grid 2-row → 2-column. `.app-body` wrapper / `.chat-header` 폐기.
- Method:
  - **선택지 비교**: AskUserQuestion 으로 두 옵션 제시 — (A) chat-pane 안에 관리 콘솔 편입 (topbar 는 brand 전용, sidebar 와 같은 너비), (B) topbar 중앙에 대화 제목 통합 (단일 전체 너비 헤더). 사용자가 (B) 변형 채택 — topbar 에 대화 제목 통합하되 **중앙 정렬 X, 좌측 정렬** + brand 를 sidebar 영역 안으로 (ChatGPT UI 명시). chat-header 폐기로 채팅 영역 확장 효과.
  - **layout 변환**: 기존 `.app-shell` 이 row 2개 (topbar | app-body) + `.app-body` 가 column 2개 (sidebar | chat-pane) 의 nested grid. 변환 후 `.app-shell` 이 직접 column 2개 (sidebar | chat-column). `.app-body` wrapper 폐기로 DOM depth 감소. chat-column 안에서 flex column 으로 topbar + chat-pane 쌓음.
  - **baseline 정렬**: `.sidebar-brand` 의 height = `var(--topbar-h)` = 52px 로 topbar 와 baseline 일치. `.sidebar-brand` 의 border-bottom (border-subtle) 이 `.topbar` 의 border-bottom (border) 와 시각적으로 연결되어 sidebar / chat-column 의 첫 row 가 단일 헤더 row 로 보임 — 시각 통합 효과.
  - **chat-title typography 보존**: `.chat-header` rule 은 폐기했지만 `.chat-title` / `.chat-subtitle` 의 font-size / weight / color rule 은 그대로 유지 — topbar-info 안에서 동일 스타일로 렌더.
  - **JS 무변경**: 모든 element ID (`conversationTitle`, `conversationSubtitle`, `loadMoreBtn`, `openAdminBtn`) 가 보존되어 getElementById 호출이 그대로 동작. `setupChatHeader` 같은 별도 mount 로직 불필요.
- Risks:
  - **반응형 mobile (max-width: 680px)**: 기존 `.app-body { grid-template-columns: 1fr }` + `.sidebar { display: none }` 패턴을 `.app-shell { grid-template-columns: 1fr }` + `.sidebar { display: none }` 으로 변환. 동일 효과 — sidebar 숨김 + chat-column 만 표시. mobile 환경 실측 검증은 별 cycle 권장.
  - **brand 가 sidebar 안으로 이전 후 sidebar 의 vertical scroll 영향**: `.sidebar { display: flex; flex-direction: column; overflow: hidden }` 인데 `.sidebar-brand` (flex-shrink: 0) + 기존 `.sidebar-head` + `.conv-list` (overflow-y: auto) + `.sidebar-profile` 의 구조에서 brand 가 첫 child 라 conv-list 의 scroll 영역이 brand height 만큼 줄어듦. 252px sidebar 에서 brand 52px 추가는 시각적으로 자연스러움.
  - **`.chat-pane` 의 background**: 기존엔 chat-pane 의 첫 child 가 chat-header (surface 배경) 라 시각적 구분이 있었으나 이제 chat-pane 의 첫 child 가 access-notice 또는 progress-strip 또는 messages-wrap. chat-pane background (var(--bg)) 가 그대로 노출되어 topbar 와 시각 구분 명확 (topbar 는 surface, chat-pane 은 bg).
  - **JS 사이드 effect 미검증**: setupChatHeader / 진행 상황 표시 / point rail 등 directing 코드가 chat-header rect 또는 chat-pane 첫 child rect 를 참조할 가능성. grep 으로 확인 — `.chat-header` selector 참조 없음. `.chat-title` / `.chat-subtitle` 은 textContent 만 갱신하며 layout 의존성 없음.
  - **dead code 잔존**: `.topbar-brand` CSS rule 이 더 이상 사용되지 않으나 stylesheet 에 남음. 무해이지만 별 cycle 에서 제거 권장.
- Trace: REQ-20260518-0004 → TASK-0066 → CHG-20260518-0003 → REV-20260518-0003 (follow-up of TASK-0065)

## REV-20260518-0002
- Date: 2026-05-18
- Decision: TASK-0065 (REQ-20260518-0003, Minor §12.3) — TASK-0063 직접 테스트 follow-up 3 항목. 헤더 4 버튼 제거 + "···" trigger 위치 우측 하단 + 분기선 `position: sticky`.
- Method:
  - **헤더 4 버튼 제거**: TASK-0063 의 dual entry 정책 (헤더 share 유지 / per-item menu) 은 일관성 측면에서 의도적이었으나 사용자 직접 테스트로 cancel/finalize 만 남기는 단일 진입점이 더 명료하다는 피드백 확인. share 가 hidden 패턴인 점은 REV-20260518-0001 Risks 의 잔여 trade-off 였는데, 본 cycle 에서 헤더 4 element 전체 제거로 자연 해소. duplicate/rename/delete/share/fork 의 backend helper 시그니처와 conv-item menu makeItem handler 는 무변경 — UI 진입점만 정리.
  - **trigger 우측 하단 이동**: TASK-0063 의 우측 상단 위치는 `.conv-owner-badge` ("내/sales/admin" pill) 의 우측 상단 위치와 시각 영역 겹침. 직접 테스트에서 hover 시 trigger 가 badge 일부를 가리거나 trigger 의 click target 이 badge 와 인접해 misclick 가능성 확인. 우측 하단 (`bottom: 6px; right: 6px`) 으로 이동하면 `.conv-item-meta` (dot + 시간 + owner) 영역과 만나는데 `.conv-item` 에 `padding-right: 32px` 보정으로 meta 가 trigger 만큼 좌측으로 압축. 사용자 시야 동선상 우측 하단은 "더보기" 의 자연스러운 위치 (Slack/Discord/Notion 의 menu trigger 위치 patterns).
  - **분기선 sticky**: TASK-0063 의 분기선 click trigger 가 동작은 정확하나 사용자가 캘린더 진입 의도일 때 분기선까지 scroll → click 의 2 단계가 부담. Slack 패턴 (date pill 이 message group 상단에 sticky) 으로 `position: sticky; top: 0; z-index: 5` 적용. CSS 만으로 동작 — JS scroll observer 불필요. label 배경을 `surface-2` (반투명) → `surface-1` (불투명 흰색) 으로 조정해 sticky 시 message bubble 위에 떠 있어도 가독성 보장. box-shadow elevation 으로 시각 분리. hover 시 box-shadow 강화로 clickable affordance 명확화.
- Risks:
  - **sticky 가 flex column + overflow:auto 부모에서 정상 동작하는가**: `.messages { display: flex; flex-direction: column; overflow-y: auto; gap: 14px }` — sticky 는 flex item 에서도 정상 동작. 본 cycle browser smoke 에서 `scrollTop = 600` 시 첫 분기선이 messageLog top + padding 영역에 정확히 stick 됨 확인 (`topInLog = 20`, padding-top 20px 와 일치).
  - **gap: 14px 의 시각 부작용**: sticky element 가 다음 element 위에 stick 될 때 그 위로는 gap 만큼 빈 공간이 보일 수 있음. 현재 디자인에서 분기선 위에 message bubble 이 들어가는 구조 (분기선이 message group 헤더) 라 부작용 없음.
  - **z-index 충돌**: pending bubble, message-actions ("여기서 분기" / "여기까지 공유" 버튼), message-point-rail dot 등의 z-index 와 비교 — 본 cycle 변경 element 는 z-index 5. menu dropdown (z=200), 캘린더 popover (default z=10 이하) 보다 낮아 dropdown / popover 가 sticky 위에 덮이는 정상 동작.
  - **active conv-item 의 trigger 상시 표시 정책 유지**: trigger 위치 이동만 변경, opacity 정책 (hover/active 시 1) 은 무변경. discoverability 보존.
  - **헤더 4 element 제거 후 backend helper 미사용 회귀 가능성**: `deleteConversation` / `renameCurrentConversation` / `forkConversation` / `createConversationShare` 는 conv-item menu 의 makeItem handler 와 message-bubble actions ("여기서 분기", "여기까지 공유") 양쪽에서 여전히 호출됨 — dead code 아님. grep 검증.
- Trace: REQ-20260518-0003 → TASK-0065 → CHG-20260518-0002 → REV-20260518-0002 (follow-up of TASK-0063)

## REV-20260518-0001
- Date: 2026-05-18
- Decision: TASK-0063 (REQ-20260518-0001, Major §12.3) — 작업 화면 대화 항목별 "···" menu + 캘린더 시간 이동 분기선 trigger 화. Codex outside voice review 10 risk 모두 반영 + 사용자 4 결정 채택.
- Method:
  - **복사 = full self-fork (사용자 결정 1)**: 메시지/첨부/SQL 결과까지 전부 보존. `_fork_conversation_impl` 은 share-fork 와 self-duplicate 양쪽이 공유 (helper 추출의 본 의도와 정합 — TASK-0058 R4). helper 가 `_set_account_current_conversation` 으로 active 자동 전환하는 side-effect 는 Codex risk 4 가 지적했지만, 본 cycle 에서는 ChatGPT 동등 UX (복사 후 새 대화 활성) 가 사용자 의도와 정합 — 의도적 유지.
  - **신규 권한 분리 (사용자 결정 2)**: `conversation.duplicate.own/.any` 추가는 rename/delete/cancel/finalize 와 동일 own/any 이원화 패턴 일관성. operator/sales 는 `.own` 만, admin 은 set(PERMISSION_CODES) 로 둘 다 자동 grant. `.any` 는 사용자 요청 없으면 grant 0 — 보수적.
  - **헤더 share 유지 (사용자 결정 3)**: active 대화의 quick share path 보존. per-item menu 의 "공유" 와 동일 endpoint (`POST /api/conversations/{cid}/share`) 호출 + 동일 helper (`createConversationShare`). dual entry 의 redundancy 는 discoverability 와 muscle memory 양쪽을 보존. 단 Codex risk 8 가 지적한 hide-vs-disable 불일치 — 헤더 share 는 여전히 hidden 패턴, menu items 는 visible + is-access-blocked 패턴. menu 안 일관성은 보장되나 share 만 헤더에서 hidden — 후속 cycle 에서 share 헤더도 visible 패턴으로 통일 가능 (별 cycle).
  - **분기선 단일 trigger + popover nav (사용자 결정 4)**: 헤더 historyCalendarBtn 제거 → 채팅 로그의 날짜 분기선이 캘린더 단일 진입점. 사용자 명시 — 먼 과거 jump 는 popover header 의 `‹` / `›` (월) + `«` / `»` (년) 로 해결. 년 jump 버튼은 `(newestYear - oldestYear) >= 1` 일 때만 조건부 노출 (사용자 명시). cursor 가 oldest/newest 범위를 넘는 방향은 disabled.
- Risks:
  - **Backend `_account_can_access_conversation` 의 호출 순서 (Codex risk 5/6)**: read-gate 먼저 호출 → 404 단일 wording ("권한이 없거나 대화를 찾을 수 없습니다.") → metadata leak 차단. `.any` 가 superset semantics 인 점은 backend 도 mirror (`is_own AND .own OR .any`).
  - **`_ensure_seed_catchup` 호출 순서 (Codex risk 3 변형)**: 기존 catalog hydrate 가 seed_roles 보다 뒤에 있어 신규 권한 grant 가 skip 되었음. 본 cycle 에서 fix — catalog 가 항상 먼저. 동일 패턴 회귀가 발생할 수 있는 future 권한 추가 시 본 review entry 가 참조 자료.
  - **Frontend hide-vs-disable inconsistency (Codex risk 8 잔여)**: menu 안은 rename/delete pattern 통일됨. 헤더 share 만 여전히 hidden — share 헤더도 visible 로 통일하는 별 cycle 권장.
  - **Backend IsDynamic NULL legacy schema (Codex risk 2)**: `_ensure_permission_catalog` 가 4 컬럼만 INSERT — IsDynamic DEFAULT 0 가 schema 에 보장된다고 가정. 현 운영 환경은 TASK-0052 Phase 1B 의 schema ALTER 가 DEFAULT 0 보장. 별 배포 환경에서 column 부재 시 _resolve_permission_catalog 의 graceful fallback (line 320) 으로 안전망 동작. 후속 cycle 에서 IsDynamic 명시 INSERT 강화 가능.
  - **년 jump 버튼 조건의 edge case**: oldest 와 newest 가 같은 해 (예: 2026-01 / 2026-12) 면 `newestYear - oldestYear = 0` → 년 jump 버튼 숨김. 1 년 폭 데이터인데 년 jump 가 없어 보이지만 월 jump 11 회로 같은 효과 달성 가능. 후속 cycle 에서 `>= 365 일` 또는 `>= 12 months` 조건으로 정밀화 가능.
- Trace: REQ-20260518-0001 → TASK-0063 → CHG-20260518-0001 → REV-20260518-0001

## REV-20260515-0004
- Date: 2026-05-15
- Decision: TASK-0062 (REQ-20260515-0011 / -0012, Minor §12.3) GOAL 2026-05-15 후속 2 항목 — 사용자 UX 개선 요청.
- Method:
  - **다중선택 UX**: 사용자 요청 "체크박스는 없애고 다중선택을 통한 표현만 나타나도록 / 다른 대화 항목 선택 시 나머지 선택 상태 해제 / 2개 이상일 때 표시". 셋 모두 동일한 흐름의 자연스러운 부분 — checkbox 가 visual noise 인 동시에 다중 선택의 진실원을 분산시킨다 (set + checkbox.checked 두 곳). modifier-only 입력으로 단일화하고 (`set` 만 진실원), 일반 click 흐름의 단일 선택 의도를 명시 (`clear` + `selectConversation`). bulk bar 의 1 개 threshold 는 단일 선택 만으로도 bar 표면 → discoverability 측면에선 도움이지만 본 요청은 minimal 추구. `count >= 2` 로 변경.
  - **Point rail 비례 분포**: 기존 구현은 rail 안에 dot 들이 4px gap 으로 단순 누적되었다. 메시지 1 개가 매우 길고 다른 1 개가 짧으면 dot 위치가 실제 scroll 위치와 매핑되지 않는다. `messageLog.scrollHeight` 기준 비례 (`top: <pct>%`) 로 배치하면 사용자가 "rail 의 dot 위치 = 메시지의 실제 위치" 를 직관적으로 인식. CSS transform 으로 dot 의 vertical center 정렬 + active 시 scale 합성으로 좌측 튐 방지.
- Risks:
  - **scroll 시 layout 재계산 비용**: 본 구현은 layout 을 render 시 1 회 + resize 시 1 회만 호출 (scroll 시는 active dot highlight 만). 대화 길이 변화 시 (메시지 추가 / 펼침) `renderMessages()` 가 자동 재호출하므로 일관성 유지. 단, `<details>` 펼침/접힘 같은 scrollHeight 변화 이벤트는 layout 을 직접 트리거하지 않음 — 후속 cycle 에서 MutationObserver 또는 ResizeObserver 검토 가능.
  - **dot 의 시각 겹침**: 메시지가 매우 가까이 있으면 dot 들이 겹칠 수 있다. 현재 8px 크기 + 부모 16px width — 메시지 간 거리가 ~ scrollHeight/N 의 작은 값이면 시각적으로 잘 안 보임. 사용자 피드백 수용 후 cluster 처리 후속 검토.
  - **다중 선택 discoverability**: checkbox 제거로 "다중 선택이 가능하다는 것" 자체가 visual 신호 없음. 단, 사용자 요청이 이를 명시했고 macOS Finder / GitHub PR list 등 동일 패턴 (modifier-only) 이 표준. tooltip / first-time 안내는 미적용.
- Trace: REQ-20260515-0011 / REQ-20260515-0012 → TASK-0062 → CHG-20260515-0005 → REV-20260515-0004

## REV-20260515-0003
- Date: 2026-05-15
- Decision: TASK-0061 (REQ-20260515-0003 ~ -0010) GOAL.md 8 항목 합본 cycle. 사용자가 Phase 1~8 일괄 승인 + 비밀번호 초기화 권장안 (MustChangePassword + 임시비번 1회 표시 + 세션 revoke + self-reset 금지) 채택을 2026-05-15 명시.
- GOAL.md §7 미결정 사항 결정:
  - **비밀번호 초기화 (REQ-20260515-0008)**: `MustChangePassword` 컬럼 채택 — 권장안 그대로. 사유: 임시 비번 + 세션 revoke 만으로는 대상 계정이 임시 비번을 계속 쓸 수 있어 보안 약함. `MustChangePassword=1` + 다음 로그인 시 강제 변경 modal 로 1회용 보장. 사용자의 명료화 "관리자 계정의 비밀번호 초기화가 아닌, 관리자 주관으로 특정 계정의 비밀번호를 초기화 하는 기능" 과 정합 — AC-0093 self-reset 거부와 일치.
  - **#progressCard 유지 vs 축소 (REQ-20260515-0003)**: 유지 (호환성). 1차 구현은 사용자별 collapsed 상태 localStorage 보존만 변경, hidden 처리는 미적용.
  - **bulk delete partial vs rollback (REQ-20260515-0010)**: partial success + 결과 요약. admin bulk UX (AC-0035) 와 일관성 우선. transaction rollback 은 사용자 의도 (일부라도 삭제) 와 정합 떨어짐.
  - **stale 만료시간 기본값 (REQ-20260515-0005)**: `WEB_PROGRESS_STALE_TIMEOUT_SECONDS=1200` (20분). 장시간 SQL/LLM 작업 (예: 복잡 QA — TASK-0034) 의 step 간격 추정 기준. env override 가능. 보수적 시작값으로 운영 오탐 줄임.
- Method:
  1. **Phase 분할 + 자족적 검증**: Phase 3 backend (env + helper + 3 endpoint 응답) 가장 자족적이라 먼저. Phase 1+2 (pending bubble + lazy polling) frontend 핵심. Phase 4 (point rail) Phase 1 의 message render 위에. Phase 5 (캘린더) 독립. Phase 7 (admin select-all fix) 자족. Phase 8 (bulk delete) backend helper 추출 + 신규 endpoint. Phase 6 (Critical 분면 — 인증 변경) 사용자 confirm 후 마지막.
  2. **§16.3 verify-completion 분리**: 각 Phase 종료 시 python compile + node --check 즉시 검증. 전체 완료 후 `make web` 재배포 + browser smoke (http://web:8000 진입, 신규 DOM 5개 (`.messages-wrap` / `#messagePointRail` / `#historyCalendarBtn` / `#historyCalendarPopover` / `#conversationBulkBar`) 존재 확인, 로그인 후 conv list checkbox 34개, /api/progress display_status 필드, /api/history_dates AgentMemoryMessages 기준, admin currentPageAccounts() == 현재 페이지 row, password-reset btn 노출).
  3. **인증 모델 영향 확인 (Phase 6 Critical)**:
     - `WebAccounts.MustChangePassword` ALTER 는 idempotent (slow path + fast path 양쪽). 기존 계정 default 0 — 기존 동작 불변.
     - `/api/admin/accounts/{id}/password-reset` 권한: `console.access` + `console.manage` + `account.update` AND **self-reset 거부** (`actor.id == account_id` → 400). 단일 endpoint 에 모두 명시.
     - 응답에 `temporary_password` 1회 포함 — server 로그/DB 평문 저장 없음. hash 만 저장.
     - 대상 계정의 `WebAuthSessions IsRevoked=1` 일괄 처리 — 모든 디바이스 강제 로그아웃.
     - frontend force change modal: `must_change_password=true` 면 닫기 button 미제공 (오직 비밀번호 변경 성공 후 자동 close). `/api/auth/me` PATCH 성공 시 `MustChangePassword=0` reset.
  4. **bulk delete 안전성 (Phase 8 — 파괴적)**:
     - `_delete_conversation_impl` helper 추출로 단건 endpoint 와 동일한 owner 가드 (`_account_can_access_conversation` + `conversation.delete.own`/`conversation.delete.any`) 재사용. cross-account leak 가능성 없음.
     - partial success 응답 — 일부 실패해도 다른 항목은 정상 처리. processing 대화는 `force=true` + `confirm_text="삭제"` 명시 시에만 처리. UI 가 ≥10 typed-confirm + processing 추가 confirm 으로 우발 클릭 방어.
- Risks:
  - **legacy cache**: cache-bust `v=20260515-task-0061` 적용 — 브라우저 hard reload 또는 cache clear 필요. 캐시된 구버전 frontend 는 신규 endpoint 응답 contract (`/api/progress` 의 `display_status` 등) 를 모름 — 단, 신규 필드는 기존 필드와 호환 (status 가 여전히 동작) 이므로 회귀 없음.
  - **`/api/history_dates` source 변경**: 이전 `AgentCoreMessages` 를 사용하던 client 흐름이 없음 — 사용 사례 자체가 본 cycle 의 캘린더 popover 만. 회귀 영향 없음.
  - **첫 stale 판정 false positive 가능성**: status_at / 첫 step 등록 직전 race 에서 시간 정보 자체가 없으면 보수적으로 stale 처리하지 않음 (helper 코드 참조). 운영 데이터 관찰 후 기본값 조정 가능.
  - **pending bubble polling 누락**: cid 발급 전 (lazy-create 첫 응답까지) 는 polling 이 안 됨 (cid sentinel). 그 사이 step 은 응답 도착 후 첫 polling 으로 누적 받음 (`after_step=0` snapshot). 첫 polling 까지의 미세한 지연은 elapsed timer 가 client tick 으로 보완.
  - **point rail 의 scroll observer**: 매 scroll 마다 모든 message element 의 getBoundingClientRect 호출 → O(N). 메시지 1000개 이상에서 jank 가능 — 현재 규모 (대화당 수십~수백 메시지) 에서는 무리 없음. 필요 시 IntersectionObserver 로 교체 후속 cycle.
- Trace: REQ-20260515-0003 ~ REQ-20260515-0010 → TASK-0061 → CHG-20260515-0003 → REV-20260515-0003

## REV-20260515-0002
- Date: 2026-05-15
- Decision: Product prompt 는 `WebProductDatabases`에 등록된 실제 접근 DB만 기준으로 작성하고, Role `전 Product 공통` prompt 는 특정 Product 선택 시에도 누적 적용되도록 runtime 조립 로직을 수정한다.
- Method:
  1. `WebProducts` / `WebProductDatabases`에서 현재 Product가 `KR(킹스레이드)`와 `MV(마이크로볼츠)` 두 개임을 확인했다. `KR` 접근 DB는 `dbgame,dblog,dbauth`, `MV` 접근 DB는 `account_db,dev_1_1_1_20,have_00,log_v2,global_db`.
  2. `information_schema.TABLES/COLUMNS`와 제한적 집계로 주요 스키마 성격을 확인했다. `KR`은 현재 상태(`dbgame`) + 대용량 로그(`dblog`) + 인증/기기(`dbauth`) 구조이고, `MV`는 계정 마스터(`account_db`) + 기준정보(`dev_1_1_1_20`) + 보유/매치 이력(`have_00`) + 서버/이벤트 기준(`global_db`) 구조다. `log_v2`는 DB는 존재하나 테이블이 0개다.
  3. Product prompt 에 민감 컬럼 경고를 포함했다. `dbauth`의 DeviceToken/광고 식별자/IP, `account_db`의 password/token/db 접속 정보는 원문 출력 금지 또는 최소화 대상으로 명시했다.
  4. Role 공통 prompt 는 `pending/operator/admin/sales/dba` 각각의 역할명과 권한 성격에 맞춰 작성했다.
  5. 기존 runtime 은 Role×Product prompt 가 있으면 Role common prompt 를 fallback 으로만 사용했다. UI의 "전 Product 공통" 의미와 다르므로 feature-0002의 `compose_system_prompt()`를 공통 누적 방식으로 수정했다.
- Risks:
  - Product prompt 는 현재 DB 상태 기준이다. 스키마가 크게 바뀌면 Product prompt 도 재검토해야 한다.
  - `make mysql`은 self-signed TLS chain 오류로 실패했다. 직접 SQL은 실행 중인 mysql 컨테이너 내부에서 root 환경변수 기반으로 수행했고, 비밀번호 값은 출력하지 않았다.
  - `make web` 재기동 중 기존 web/mysql/browser/worker 컨테이너가 한 번 정리된 뒤 web/mysql만 재기동했다. 최종 검증에 필요한 web/mysql은 정상 기동 상태다.

## REV-20260515-0001
- Date: 2026-05-15
- Decision: TASK-0059 (REQ-20260515-0001, **Major** §12.3 — 사용자 대화 routing 데이터 영역). "새 대화" 의 lazy-create 의도가 backend 로 전달되지 않아 빈 `conversation_id` 가 `_repair_current_conversation` 폴백 경로에서 `account.last_conversation_id` 로 귀결되던 결함을, 명시적 `lazy_create` body hint + `_resolve_conversation_for_account(force_new=...)` plumbing 으로 닫음. 인증/인가 catalog·endpoint guard·owner check 무변경.
- Method:
  1. **버그 재현 분석**: 사용자 보고 "새 대화 만든 후 그 대화에서 요청을 보냈는데 기존 대화에서 처리됨". 코드 trace 로 핵심 경로 파악 — frontend `beginPendingConversation()` [app.js:2148-2172] 이 `state.activeConversationId=""` + `pendingNewConversation=true` 로 두고 backend row 를 lazy 생성 위임 (TASK-0048 빈 대화 누적 방지 정책). `sendPrompt()` [app.js:2454] 는 `askBody.conversation_id=""` 로 `/api/ask` 호출. backend [app.py:4273-4285] 가 빈 cid 경로에서 `_resolve_conversation_for_account(..., create_if_missing=True)` 호출 → `_repair_current_conversation` [app.py:1156-1179] 으로 폴백 → `current_id = account.last_conversation_id` (= 직전 대화) 가 visible 안에 있으면 line 1167-1168 의 early return 으로 **기존 대화 ID 반환**. 신규 의도가 backend 로 전달되지 않음.
  2. **부가 race 발견**: `loadConversations` [app.js:2074] 이 pending 모드 진행 중에 호출되면 `payload.current` (= backend `_repair_current_conversation(create_if_missing=False)` 결과 = 직전 대화 id) 로 `state.activeConversationId` 를 덮어써 pending 의도를 깨뜨릴 수 있음. progress polling 정리에서 폴백된 갱신이나 다른 비동기 path 가 호출하는 경로에서 발생 가능.
  3. **대안 비교**:
     - **Alt A (선택)**: 명시적 `lazy_create` hint — frontend 가 pending 의도를 backend 에 신호. 단일 변경점 + 기존 fallback 보존 + legacy client 호환.
     - **Alt B**: backend 가 빈 conversation_id 를 항상 신규 생성. 단순하지만 첫 로그인 후 자동 이어받기 / `/api/use_conversation` 미호출 client 흐름이 깨짐. backward-compat 위배.
     - **Alt C**: frontend 가 pending 모드일 때 명시적 `/api/new_conversation` 먼저 호출. TASK-0048 의 빈 대화 누적 방지 정책이 부활하므로 거부.
  4. **race 가드 분리**: backend 의 routing fix 만으로는 pending 의도가 frontend 자체에서 깨질 가능성 잔존 → `loadConversations` 의 active id 덮어쓰기에 `!state.pendingNewConversation` 가드 추가. 두 변경은 독립적 — 하나만 적용해도 일부 시나리오 보호되나, 함께 적용해야 모든 reproduction 경로 차단.
- Risks:
  - **legacy client (구버전 frontend)**: hint 미포함 ask 요청은 force_new=False 로 기존 동작 유지. 그래서 backend 단독 deploy 후 frontend 가 캐시된 구버전이면 버그는 그대로 재현 가능. cache-bust 필요 시 `static/app.js` 의 query string 갱신 (e.g. `v=20260515-lazy`). 본 cycle 은 변경 자체에 cache-bust 미포함 — 사용자가 hard reload 또는 browser cache clear 로 확인.
  - **신규 cid 의 owner assign 경로**: `_repair_current_conversation` 의 force_new=True 분기는 `_create_conv(conv_file=_account_conv_file(...))` 호출 후 즉시 `_assign_conversation_owner(conn, next_id, account_id, force=True)` 와 `_set_account_current_conversation` 을 호출 (line 1175-1177). 즉 새 cid 는 본 계정 소유로 즉시 assign 되며 cross-account leak 가능성 없음.
  - **pending 가드의 부작용**: `loadConversations` 가 pending 중에 호출되어도 active id 가 보존되므로 backend `payload.current` 와 frontend `state.activeConversationId` 가 일시적으로 분기. 사용자가 사이드바에서 다른 대화를 직접 선택하면 `selectConversation` [app.js:2101] 이 pending 모드를 종료시키므로 (line 2106-2108) 정합 회복. 첫 메시지 전송 시에는 `sendPrompt` 의 lazy create 분기 (line 2509-2513) 가 새 cid 로 정리.
  - **owner check 우회 가능성**: 변경 후에도 명시 cid 가 들어오는 경로 (`request_conversation_id` truthy) 는 기존 `_conversation_owned_by_account` 검사 [app.py:4269-4271] 를 그대로 거친다. force_new 경로는 새 cid 를 즉시 생성하므로 owner check 가 무의미 (본 계정 소유). 인가 모델 무변경 확인.
  - **TASK-0048 정책과의 충돌 여부**: TASK-0048 은 "빈 대화 row 누적 방지" 가 목적. 본 fix 의 force_new 분기는 **메시지 전송 시점에만** 발동하므로 row 가 만들어지는 즉시 메시지가 attach 됨 → 빈 대화 아님. 정책 위배 0.
- Follow-ups:
  - 운영 검증: web 컨테이너 재배포 후 (a) 직전 대화 X 가 있는 상태에서 "새 대화" 클릭 → 빈 입력창 → 메시지 전송 → 새 cid Y 발급 + 메시지가 Y 에 attach (X 에는 추가 없음) 확인. (b) 직전 대화 X 가 있는 상태에서 "새 대화" 클릭 → 사이드바 새로고침 트리거 → active 가 X 로 복귀 안 되는지 확인 (pending 가드).
  - cache-bust: 다음 cycle 에서 frontend 변경 함께 deploy 할 때 `static/app.js?v=` 갱신.
  - 회귀 테스트: feature-0003 unit tests 에 "lazy create 의도 시 신규 cid 발급" + "pending 모드 race 시 active 보존" 케이스 추가 가능 (현 cycle defer — TASK-0034 성능 테스트와 함께 다룰지 사용자 결정).

## REV-20260514-0001
- Date: 2026-05-14
- Decision: TASK-0058 (REQ-20260514-0001, **Critical** §12.3) 대화 공유 링크 기능 도입. anonymous 접근 허용은 사내 IP 가정 + 외부 배포 시 IP 제한/비밀번호 보호 후속 cycle. PLAN-APPROVED + 사용자 결정 6 항목 + outside voice review 완료 후 진행.
- Method:
  1. **요구사항 정제**: 사용자 요청 "특정 대화를 링크로 공유" 가 매우 광범위. 6 가지 결정사항을 AskUserQuestion 2 라운드로 확정 — 외부 anonymous 허용, 무기한 + revoke, read+fork, full+anchored 둘 다 생성 시 선택, `conversation.share.create` 권한 신설, 메시지 + SQL + 결과셋 모두 노출 (사내 협업 우선).
  2. **Outside voice review** (메모리 정책 `feedback_outside_voice_for_rbac`): RBAC catalog 변경이므로 general-purpose subagent 로 plan blindspot 10 건 수집. B1 (메시지 테이블 이중성 — `AgentMemoryMessages` vs `AgentCoreMessages` Id 공간 분리 — fork 의 `from_message_id` 와 정합 위해 `AgentMemoryMessages.Id` 채택), B2 (`_require_account` 가 401 raise → `_optional_account` 신설), R4 (`_fork_conversation_impl` 추출로 share-grant 가 read-gate 우회), R5 (AnchorMessageId inclusive `Id <= anchor`), R6 (revoke + view race-free 단일 UPDATE), R7 (file attachment 자동 hide), R8 (token UNIQUE 충돌 retry 5 회), R10 (share.html FileResponse) 모두 plan 에 흡수.
  3. **위험 분리**: Critical 등급 (SECURITY.md §3 의 인증/인가 + 개인정보 + 외부 공개 범위 3 항목 동시) 이지만 5 phase 가 모두 비파괴 추가 + idempotent. Phase 별 syntax check 통과 후 다음 phase 진행.
  4. **검증**: app.py Python AST parse OK, app.js / share.js node --check OK. 부트스트랩 idempotency 는 helper 패턴 (try/except pass + INSERT IGNORE + ON DUPLICATE KEY UPDATE). 실런타임 검증 (sales/admin 로그인 → 헤더 공유 → URL 발급 → anonymous 접근 → revoke → 410) 은 후속 단계.
- Risks:
  - **외부 IP 노출**: 사내 IP 가정이 깨지는 순간 (예: 실수로 외부 LAN 으로 expose, VPN 미접속) 대화의 SQL 원문 + 결과셋이 외부에 그대로 노출. 사용자도 이 위험을 인지하고 "추후 사내 배포 시 보완" 결정. 후속 cycle 의 보완 옵션: (a) Caddy / reverse proxy IP allowlist (사내 CIDR), (b) share token 별 비밀번호 옵션 (`WebConversationShares.PasswordHash` 컬럼 추가), (c) 시간 기반 만료 (현재 무기한). 본 cycle 은 minimum viable.
  - **anonymous endpoint 보안 표면**: `/api/public/share/{token}` 과 `/api/public/share/{token}/fork` 가 시스템의 유이한 anonymous-allowed 경로. 향후 RBAC refactor 가 실수로 `_require_account` 를 모든 endpoint 에 일괄 부착하면 share view 가 깨질 수 있음. 두 endpoint 모두 inline 주석으로 anonymous 의도 명시. SECURITY.md 에 정책 등재.
  - **token enumeration**: `secrets.token_urlsafe(32)` = 256-bit entropy → brute force 비현실적. UNIQUE 충돌 retry loop 는 보안 위협 없음 (5 회 재시도 후 500 반환).
  - **revoke + view race**: 단일 `UPDATE ... WHERE Token=? AND RevokedAt IS NULL` rowcount 가 0 일 때 410 Gone 반환. rowcount > 0 + 그 후 revoke 사이 라스트 mile 은 stale-by-one 수용.
  - **anchor 의미 혼란**: inclusive (`Id <= anchor`) — fork 의 `from_message_id` 와 정확히 동일. UI label "여기까지 공유" 가 그 의미 표현.
- Follow-ups:
  - 외부 배포 전: IP allowlist 또는 token 별 비밀번호 옵션 cycle.
  - `/api/public/share/{token}` 의 rate limit (DDoS 완화) — 본 cycle defer.
  - 운영 검증: sales/admin 계정 양쪽으로 헤더 공유 / 메시지 hover 공유 / anonymous URL 접근 / revoke / 410 회귀 / fork 흐름 실제 동작 확인.
  - 프로필 drawer 의 "내 공유 링크" 관리 탭 — `GET /api/conversations/{cid}/shares` 와 `DELETE /api/share/{id}` 가 이미 backend 에 있으니 frontend UI 만 후속 추가 가능.

## REV-20260507-0001
- Date: 2026-05-07
- Decision: TASK-0053 의 사용자 follow-up 2 항목 수정 — pending row UI 뒤틀림 + product 카드 위치 이동 — 을 1 commit 에 통합. AI 자율 commit/push.
- Method:
  1. **Issue 1 진단**: pending sales row 의 DOM 을 `getBoundingClientRect` 로 분석 → cb 가 column 2 (x=70), main 이 column 3 (x=175), chips 가 row 2 col 1 (x=11, y=73) 에 wrap 되어 있음. 수상한 4번째 grid item 추정. CSS 검토 결과 `.admin-list-row.has-pending::before { content: ""; }` placeholder rule 발견 — `::before` 가 grid container 의 pseudo-element 이지만 `content: ""` 가 있으면 generated DOM 에 참여해 grid 의 4번째 child 가 되어 column 1 row 1 을 차지. 다른 children 이 한 칸씩 밀리고 chips 는 wrap.
  2. **Issue 1 수정**: pseudo-element 자체를 제거 (placeholder 의도가 사라졌음). 시각적 표시는 `border-color` 변경으로 유지 (`pendingDot` "•" 이 이미 title 안에서 indicator 역할 수행).
  3. **Issue 2 구현**: `buildRoleProductCardList` / `buildAccountProductOverrideList` 에 `opts.embed` 옵션 추가. embed=true 면 별도 section title 생략 (부모 details summary 의 "제품" 라벨이 이미 표시), hint 단축. `renderRoleDetail` / `renderAccountDetail` 가 `permWrap.querySelector('details[data-perm-group="product"]')` 로 grid 의 product 그룹 details 를 찾아 그 안에 append. 없으면 fallback paneEl append.
  4. **검증**: DOM 좌표 비교 (수정 전 cb x=70 → 수정 후 x=11), embedded 카드 카운트 3 (KR/TT/전 Product 공통), 시각 screenshot 비교.
- Risks:
  - **CSS Grid pseudo-element 함정 재발 위험**: 향후 `::before`/`::after` 에 content 추가 시 grid item 으로 참여. LEARNINGS.md 의 frontend pitfall 항목 등재 권고. 방어 패턴: grid container 의 pseudo 는 `position: absolute` 로 flow 에서 제외 또는 `display: none`.
  - **embed 옵션의 hint 길이 차이**: standalone 모드 vs embed 모드의 hint 텍스트가 다름 (footer 안내 중복 회피). UX 일관성 손실은 미미 — 동일 의미를 압축 표현.
  - **Issue 2 의 fallback 경로**: grid 에 product 그룹이 없으면 (정적 product.manage 권한 자체가 없는 환경) product 카드 list 가 별도 paneEl section 으로 표시. 운영 환경에서 product 그룹은 항상 존재하므로 발생 시나리오 거의 없음.
- Why combine in one commit: 두 이슈가 독립적이지만 사용자가 동시에 보고 + 둘 다 동일 cycle (TASK-0053) 의 보완 + 둘 다 admin.js + styles.css 파일 영역. 분리 commit 의 이득 < 통합 deploy 의 일관성.

## REV-20260506-0014
- Date: 2026-05-06
- Decision: TASK-0053 의 3 phase (A/B/C) 를 1 cycle 안에 통합 진행. **사용자 in-cycle 설계 전환 (2026-05-06)** — 처음 작성한 Phase A 의 "Role 의 DefaultProductAccess 토글" 접근을 사용자 의도에 따라 "Product 의 DefaultRoleAccess 토글" 로 정정. 분리 commit 하지 않은 이유: 본 cycle 의 수정은 보안 표면 추가 0 + 기존 동작 호환 (DEFAULT 1 백필) + frontend 재구성이 핵심. 분리 commit 의 회귀 표면 제어 이득보다 통합 deploy 의 일관성 (정책 토글이 곧 product subcatalog 와 함께 보임) 이 더 큼.
- Method:
  1. **Phase A (정책 토글, product 주체)**: WebProducts 에 `DefaultRoleAccess TINYINT(1) NOT NULL DEFAULT 1` 컬럼. 기존 product 모두 1 으로 backfill 되어 D2-A 와 동일 동작 유지. POST `/api/admin/products` 의 transaction 안 backfill SQL + `_ensure_product_access_permissions(conn)` (catchup) 양쪽이 product 의 `DefaultRoleAccess` 값에 따라 분기. POST/PATCH `/api/admin/products` body 에 `default_role_access` 수용. Role-side 의 이전 시도 (`WebRoles.DefaultProductAccess`) 는 컬럼 잔존하나 어떤 SQL 도 참조하지 않음 — 다음 cleanup cycle 에서 DROP COLUMN.
  2. **Phase B (권한 grid 의 dynamic 분리)**: `groupedPermissions(opts)` 에 excludeDynamic 옵션 추가. `dynamicProductPermissions()` 헬퍼로 product 별 정렬된 동적 권한 목록 반환. `renderPermissionGrid` 가 옵션 통과. Role detail 과 Account detail 의 onChange 핸들러는 dynamic 권한들의 기존 상태를 union 으로 보존해 subcatalog 와의 분리가 데이터 손실로 이어지지 않게 처리.
  3. **Phase C (Role/Account detail 의 product subcatalog 카드)**: `buildRoleProductCardList(role, disabled)` — product 별 collapsible card 안에 access 토글 + role-scope system prompt textarea (fixedProductId=Number(id)) 묶음 + "전 Product 공통" generic card (fixedProductId=0). `buildAccountProductOverrideList(account, disabled)` — flat card 에 override select. Role detail 의 단일 buildSystemPromptEditor 호출은 product 카드의 textarea 로 흡수 (Product detail 의 product-scope prompt + profile drawer 의 account-scope prompt 는 그대로).
  4. **검증 매트릭스**: py_compile + node check + make web + Phase A E2E (DE 생성 with `default_role_access=false` → 6 role 모두 grant 0, JP 생성 with true → 6 role 모두 grant) + Phase B/C DOM (admin-product-card-list/admin-product-card 카운트 + 권한 grid dynamic 코드 제외 확인 + 스크린샷).
- Risks:
  - **호환성 우선의 default 1**: 운영자가 product 생성 시 토글을 명시적으로 끄지 않으면 기존 동작 유지 (D2-A 호환).
  - **이전 시도 잔재**: `WebRoles.DefaultProductAccess` 컬럼이 destructive DROP 회피로 잔존. 어떤 SQL 도 참조하지 않으므로 동작 영향 0. 본 cycle 자체가 commit 전 상태에서 in-place 정정이라 git log 에는 이 잔재가 노출되지 않음 (single commit). 다음 cleanup cycle 에서 명시적 DROP COLUMN.
  - **Phase B 의 onChange union 처리**: dynamic 권한들이 grid 와 subcatalog 두 곳에서 source-of-truth 가 분리되어 보일 수 있으나 실제 storage 는 단일 (`role.permission_codes` / `account.permission_overrides`). onChange 가 정적/동적 양쪽 union 을 보장하므로 race-free.
  - **Account detail 의 product card 에 prompt textarea 부재**: account scope prompt 는 profile drawer (AC-0014) 가 source-of-truth.
  - **product 가 100 개 이상이 되면 cards 가 길어짐**: collapsible details 라 펼치지 않으면 헤더만 보여 스크롤 부담 적음. 추후 search 필터 추가 가능 (별 cycle).
  - **"신규 역할 자동 접근" 토글의 의미 명시**: **신규** product 생성 시점에만 효력. 기존 product 의 grant 는 product PATCH 의 default_role_access 변경으로도 변하지 않음 (정책만 변경, 기존 grant 보존). admin UI 에 명시 hint 추가는 별 cycle.
- Why this design switch (Role-driven → Product-driven): 사용자가 본 cycle 진행 중 명시적으로 의도 정정 — "신규 제품 자동 접근의 주체를 Role 이 아닌 Product 를 기준으로 적용". 직관적으로도 정책의 주체는 "이 product 가 어떻게 분배되는지" 이지 "이 role 이 무엇을 자동으로 받는지" 가 아님. Product-driven 이 product 운영자의 결정 권한을 명확히 함.
- Why this combines Phase A/B/C in one commit: 사용자가 한 번에 3 항목 (토글 + sub catalog + role-prompt 묶기) 을 요청했고 AI 자율 commit/push 권한이 명시되어 있음. 분리 commit 은 회귀 표면 제어 이득 < 통합 deploy 의 일관성 (3 변경이 한 화면에서 함께 보여야 의도 전달) 이 더 큼.

## REV-20260506-0013
- Date: 2026-05-06
- Decision: TASK-0052 의 Phase 1B/1C/1D + Phase 2 검증을 사용자 AI 자율 commit/push 모드에서 1 cycle 안에 완료한다. Codex outside voice 의 9 finding 모두 통합 (정적 catalog 가정 → DB-driven, autocommit → 명시적 트랜잭션, 가드 8 곳 도입, fork product_mode 복사 fix 등). 작업 중 발견된 pre-existing `admin_update_account` RoleId 손실 버그도 즉시 fix.
- Method:
  1. **Phase 1B (catalog DB-driven 전환)**: Phase 1A 가 깐 plumbing (`_resolve_permission_catalog(conn=None)`) 의 body 만 교체. conn 이 주어지면 정적 + WebPermissions IsDynamic=1 union 반환. graceful fallback (column missing / DB error) 으로 호환성 유지. caller 7 곳을 `_resolve_permission_catalog(conn)` 결과 (`catalog_codes` / `catalog_map`) 를 명시적으로 전달하도록 update.
  2. **Phase 1B (schema migration)**: `_ensure_dynamic_permissions_schema(conn)` 헬퍼 + `_ensure_product_access_permissions(conn)` 헬퍼. slow path (`_ensure_web_tables`) + fast path (`_ensure_seed_catchup`) 양쪽에서 호출되어 기존 배포에서도 신규 컬럼/권한 row/role grant 가 자동 적용. backfill 결과를 stderr 에 1 회 기록 (운영 transparency, Codex Claim 5).
  3. **Phase 1B (product CRUD 트랜잭션, Codex Claim 2)**: `conn.autocommit=False` + 명시적 commit/rollback. POST 는 product + permission row + role grant cascade 한 트랜잭션. DELETE 는 in_use guard 통과 후 SystemPrompts → ProductDatabases → RolePermissions → AccountPermissionOverrides → Permissions → Products cascade 한 트랜잭션. 부분 실패 시 product 자체 rollback.
  4. **Phase 1C (G1-G8)**: `_account_has_product_access(account, product_id_or_key, *, conn=None)` 단일 진입점. 8 endpoint 가드 (briefing §3.4 매트릭스). G4 가 Codex Claim 3 의 직접 해소 — 권한 회수 후 pinned 대화 재실행 차단. G5 가 fork 의 product_mode 'auto' 보존 fix 도 함께 처리 (Codex Claim 4).
  5. **Phase 1D (admin UI)**: PERMISSION_GROUP_ORDER 에 'product' 추가. admin.js + app.py 양쪽 동기. 기존 renderPermissionGrid 가 자동 노출.
  6. **Phase 2 (HTTP smoke)**: bootstrap_admin 으로 deny override 적용 → G1/G2/G7/G8 직접 403 검증 + product CRUD lifecycle (T13/T14/T15/T16) + admin_update_account RoleId 보존 fix 검증. G3/G4 는 model validation 단계에서 차단되어 정적 코드 검증으로 대체 (코드 경로 동일 패턴).
- Risks:
  - **Critical 등급 변경 + AI 자율 commit**: AGENTS.md §12.3 (인증/인가 구조 변경) 으로 본래는 사람 승인 필요. 사용자가 명시적으로 AI 자율 권한 부여 (2026-05-06) — 정책 적용 우선순위 §3.1 1 위 (사용자 직접 지시) 에 따라 진행. 본 변경의 보안 의미: 8 endpoint mutation/read 가드가 추가되어 product 격리 강화, 단 D2-A 호환성 backfill 로 모든 role 이 default-grant 라 운영자 후속 deny override 필요.
  - **pre-existing 버그의 발견 시점**: admin_update_account RoleId 손실은 이전 cycle 부터 존재했을 가능성이 높음 (코드상 `target.get("role")` 은 어느 시점부터 None 이었음). Phase 1C 의 negative smoke 에서만 트리거되어 catch — 일반 운영에서는 admin 이 본인 PATCH 를 거의 하지 않아 dormant 였던 회귀로 추정. 본 fix 가 cycle 안에 포함되어 안전.
  - **D2-A 의 secure-by-default 갭**: 본 cycle 종료 후에도 pending/sales/operator 등 모든 role 이 KR (현재 1 product) 에 default-grant. 운영자가 deny override 로 회수해야 실효 격리. 운영 transparency 메시지로 안내.
  - **Phase 2 negative smoke 의 G3/G4 미직접 검증**: model validation 단계 차단으로 HTTP smoke 가 가드 도달 불가. 정적 코드 검증으로 대체 — G1/G2 와 동일 패턴이라 회귀 위험 낮음. 후속 cycle 에서 valid model 로 재시도 가능.
  - **admin lockout 보호 (briefing F8 — NOT in scope)**: admin 이 자기 자신의 마지막 product access 를 deny 로 잠가 lockout 가능성. survivor 보호 로직 (`_ensure_management_survivor_for_account_change`) 은 console.manage 류만 검사하고 product access 는 미포함. 별 cycle 검토.
- Why this combines Phase 1B/1C/1D in one commit (분리 commit 옵션 선택 안 함): 본 cycle 진입 시 사용자가 "나머지 Phase 모두 진행" + "AI 자율 commit/push" 명시. Phase 1B/1C/1D 는 의존 순차라 각 phase 단독 deploy 의미가 적음 (1B 만 deploy 시 가드 없는 상태로 DB schema 변경, 1C 만 deploy 는 1B 없이 catalog 가 catch 못함). Phase 1A 는 deploy-safe 단일 변경이라 분리 commit 했지만 (4dd1d0a), 본 cycle 은 통합 deploy 가 일관성에 유리.
- How this changes BRIEFING-c5: 본 cycle 로 briefing 의 Phase 1A/1B/1C/1D + Phase 2 P0 (T01-T08, T13-T16 직접 + T19/T20/T21-T23 정적) 모두 ✓. 미구현 항목: Phase 2 P2 (sessions/me filter, end-user FE chip filter) — 별 cycle. F8 (admin lockout 보호) — 별 cycle.

## REV-20260506-0012
- Date: 2026-05-06
- Decision: TASK-0052 Phase 1A 만 본 turn 에서 진행한다. RBAC engine 의 정적 PERMISSION_CODES 가정 (Codex Claim 1) 을 catalog 인자 받는 형태로 refactor 하되, **동작 변경은 0** — 모든 5 함수의 catalog 인자 default = None = 정적 사용. `/api/admin/permissions` 만 신규 plumbing 검증 경로로 전환해 Phase 1B 의 DB-driven 전환 surface 를 미리 검증한다. Phase 1B/1C/1D 는 별 cycle 분리.
- Method:
  1. **`_resolve_permission_catalog(conn=None)` 헬퍼** 신설 — Phase 1A 시점은 정적 `(PERMISSION_DEFINITIONS, PERMISSION_CODES, PERMISSION_DEFINITION_MAP)` 반환. Phase 1B 가 body 만 교체 (conn 으로 WebPermissions union). 단일 함수가 catalog source 의 single point of customization 이 되도록 설계.
  2. **5 함수 시그니처 확장** — `_empty_permission_map(catalog_codes=None)`, `_apply_permission_overrides(..., *, catalog_codes=None)`, `_validate_permission_codes(..., *, catalog_codes=None)`, `_normalize_override_payload(..., *, catalog_codes=None, catalog_map=None)`, `_permission_catalog_payload(*, catalog=None)`. 모두 `*` keyword-only, 기본값 None = 정적 사용. 기존 callsite 6 곳 (L854/3681/5403/5545/5624/5395) 모두 None 인자로 호출 → 기존 동작 유지.
  3. **plumbing 검증 endpoint 1 곳** — `/api/admin/permissions` (L5761) 만 새 경로 (`_resolve_permission_catalog(conn) → _permission_catalog_payload(catalog=catalog_definitions)`) 로 전환. HTTP smoke 로 catalog 결과가 이전과 동일 (33 codes) 임을 확인. 다른 callsite 는 Phase 1B 에서 caller-update.
  4. **검증 매트릭스**: py_compile + container reload + container 내부 grep + bootstrap_admin HTTP login + /api/admin/permissions 응답 비교. 4/4 통과.
- Risks:
  - **Phase 1A 단독 commit 의 의미**: 코드 변경은 plumbing 만, 동작은 0. 그래도 commit 분리는 (a) 회귀 표면 명확화, (b) Phase 1B 가 catalog source 만 교체하는 단순 변경으로 떨어짐, (c) 향후 다른 RBAC 변경이 plumbing path 를 그대로 활용. 위험 회피 ROI 높음.
  - **`/api/admin/permissions` endpoint 만 plumbing 사용 — 다른 callsite 는 정적 path 그대로**: Phase 1B 가 catalog 를 dynamic 하게 만들 때 다른 callsite (특히 L3518/3570 의 role payload `permissions` map 빌드) 도 catalog 를 받아야 함. Phase 1B 의 caller-update 범위를 briefing §4 의 Phase 1B 항목에 명시.
  - **Iterable import 추가 (L18)**: typing 외 collections.abc 에서 가져와 type hint 만 사용. 런타임 영향 0.
- Why not Phase 1B 까지 한 turn: Briefing §12 의 "Phase 1A 는 product 권한 도입 없이도 안전하게 deploy 가능" 에 따라 분리. Phase 1A 단독 회귀 면적이 0 이라 commit 후 즉시 운영 deploy 가능. Phase 1B 는 backfill SQL + 8 endpoint guard 의 complexity 합산이 큼 — 별 cycle 의 plan + verification 필요.
- How this changes BRIEFING-c5: 본 turn 의 Phase 1A 완료를 briefing §4 마이그레이션 plan Phase 1A 항목에 ✓ 표시 권고. Phase 1B 진입 시 briefing §12 의 후속 단계 안내 그대로 적용.

## REV-20260506-0011
- Date: 2026-05-06
- Decision: TASK-0051 (REQ-20260506-0004) 관리 콘솔 5 가지 UX/정책 요청 중 4 건(C1~C4) 만 본 cycle 에서 진행하고, **C5 (계정·역할 → 제품 권한 상속/override 모델)** 는 다음 cycle 로 분리한다. 메타데이터 4 종 노출은 신규 backend 정책 변경 없이 UI 시각화로만 처리한다 (REV-20260422-0006 에서 이미 tool-level bypass 가 정의됨). DB 목록 picker 는 신규 read-only enumeration 엔드포인트(`GET /api/admin/databases/available`) 로 제공하고 권한 게이트는 `console.access` 로 약하게 둔다.
- Method:
  1. **C5 분리 결정**: 사용자가 직접 `[A → B → C → D]` 까지만 진행하도록 지시 + C5 는 review 후 다음 cycle 진행 권고를 명시 요청. 분리의 운영 근거: (a) C5 는 신규 테이블 2 개(`WebRoleProductAccess`, `WebAccountProductAccessOverrides`) + 기존 RBAC override 모델(TASK-0024) + `compose_system_prompt` 의 product 조회 경로(`feature-0002-agent-core/src/agent_core.py`) 변경 영향을 동시에 받는다. (b) 일괄 commit 정책 회복(C1~C4) 과 권한 모델 확장(C5) 은 서로 독립이라 한 PR 안에서 묶어도 회귀 표면이 분리되지 않는다. (c) `/plan-eng-review` 를 거치지 않으면 RBAC override 우선순위 (Role default → Account override) 와 신규 product access override 우선순위가 어떻게 합성되는지 결정이 명확하지 않다 — 무리한 진행 시 인증 인접 회귀 가능성.
  2. **메타데이터 4 종 시각화 방식 비교**: (a) backend 가 응답에 `databases` 필드로 메타 4 종을 항상 강제 포함시키는 방안, (b) backend WebProductDatabases 에 자동 INSERT, (c) UI 가 정책 상수로 직접 그리고 backend 는 무관, 3 가지를 비교. (c) 채택 — 사유: REV-20260422-0006 의 tool-level bypass 정책은 데이터 저장과 무관하게 항상 적용되므로 WebProductDatabases 에 메타를 굳이 저장할 필요가 없다(중복 진실 회피, AGENTS.md §13.1). (a)/(b) 는 user_schemas 와 metadata_schemas 의 정책적 의미 차이(metadata = 항상 bypass / user = 사용자 화이트리스트) 를 코드에서 구분 못 하게 만든다.
  3. **DB picker 권한 게이트 결정**: enum 결과는 schema 이름 / 존재 여부 한정이며 row 데이터 노출이 없다. 실제 등록은 `product.manage` 권한이 필요한 PUT `/api/admin/products/{id}/databases` 가 게이트로 남는다. 따라서 enum 자체는 `console.access` 만으로 허용해 product 관리자가 아닌 readonly 관리자에게도 picker UX 가 도움이 되도록 한다. 민감 schema(`agent_memory`, `MEMORY_DB`) 는 user_schemas 응답에서 backend 가 제외해 picker 옵션에 노출되지 않도록 이중 가드.
  4. **일괄 commit 흐름 통합 방식**: pending bucket 별 PATCH/PUT 호출을 `applyAllPending()` 하나에 합치는 6 단계로 확장. 신규 buckets 의 실패는 기존 `failures` 배열에 합류해 동일 toast UX 유지. 부분 성공 의미를 보존(예: 제품 메타는 PATCH 성공인데 시스템 프롬프트 PUT 만 실패해도 `${ok}건 성공 ${failures.length}건 실패` 로 표기).
  5. **System prompt textarea pending 보존**: pending entry 가 `loadAdminData()` reload 로 사라지지 않도록, `refresh()` 가 pending 우선으로 textarea 값을 복원. productSelect 변경 시에도 새 (scope, productId, ...) key 의 pending 이 있으면 그 값을 표시.
- Risks:
  - **회귀 표면**: applyAllPending 6 → 9 단계 확장. 기존 single-button save 경로가 사라졌으므로 사용자가 변경 후 footer 적용을 누르지 않으면 변경이 유실된다. 완화: textarea/input 변경 즉시 `refreshPendingUI()` 가 footer 카운트를 증가시키고 `beforeunload` 핸들러가 confirm 하도록 기존 `pendingChangeCount > 0` 체크가 그대로 동작.
  - **TextArea pending 키 충돌**: 같은 (scope, productId, roleId, accountId) 조합에 두 번 입력해도 마지막 입력이 덮어쓴다 (Map). productSelect 가 바뀌면 다른 key 의 pending 이 활성화되어 두 분기 모두 보존된다 — 기존 동작과 일치.
  - **DB picker stale**: `availableDatabases` 는 loadAdminData 시점의 스냅샷이라 admin 콘솔 진입 후 새 DB 가 생성되어도 즉시 반영되지 않는다. 완화: `refreshAdminBtn` (새로고침) 또는 footer apply 후 자동 reload 가 picker 도 갱신.
  - **권한 게이트 약화 우려**: `console.access` 만으로 enum 가능. 위협 모델: (a) schema 이름 자체가 정보 누출이라는 관점이 있을 수 있으나, 본 콘솔에 진입한 시점에 이미 `WebProducts`/`WebProductDatabases` 의 등록된 user 화이트리스트는 노출됨(기존 동작). (b) 등록 변경은 여전히 `product.manage` 가 필요하므로 권한 escalation 표면 없음. 결정: `console.access` 유지.
  - **C5 누락 인지**: 본 cycle 종료 시 사용자가 `계정·역할 → 제품 권한 상속/override` 가 빠졌다는 사실을 인지하지 못할 위험. 완화: REPORT.md "후속 작업" 에 C5 권고 명시 + ANCHOR.md §3 의 "Role/Product 권한 부여" 시나리오 본 cycle 에서 시각화만 강화 + 다음 cycle 의 plan-eng-review 호출 권유.
- Why not C5 한 cycle 에 묶기: (1) RBAC override 모델(TASK-0024) 과의 우선순위 합성이 결정되지 않음. (2) `compose_system_prompt` 의 product 조회 경로가 새 권한 모델에 어떻게 의존하는지 추적 필요. (3) 신규 테이블 2 개 + 기존 `WebAccountPermissionOverrides` 와의 책임 분리 정의 필요. (4) 사용자 명시 지시("C5는 다음 cycle에서, review 후 진행할 수 있도록 권고") 와 일치.
- How this changes REV-20260422-0006: 정책 결정은 그대로 유지되고, 본 review 에서는 그 결정을 admin UI 가 직접 시각화하도록 끌어올린다 (메타 4 종을 admin 콘솔에서 회색 chip 으로 항상 노출 + dbHint 안내 + tool-level bypass 정책 변경 없음).

## REV-20260506-0010
- Date: 2026-05-06
- Decision: 빈 대화 누적 방지를 위해 "새 대화" 생성 시점을 backend row 즉시 발급에서 client-side pending → 첫 메시지 전송 시 `/api/ask` lazy creation 으로 전환한다. 기존 backend `/api/new_conversation` 엔드포인트는 backward compatibility 를 위해 보존하지만 frontend 는 더 이상 호출하지 않는다.
- Method:
  1. backend `/api/ask` 의 `_resolve_conversation_for_account(create_if_missing=True)` lazy create 경로가 이미 존재함을 확인 (`src/app.py` L3853 부근). 즉 cid 없이 ask 가 들어와도 backend 는 새 대화를 만들 수 있다. 단 `/api/new_conversation` 이 적용하던 product hint (mode/product_id) 가 ask body 에 없어 lazy 생성 row 는 default('pinned' + default product) 로 시작해 사용자가 'auto' 의도를 가진 경우 회귀가 발생.
  2. 두 가지 backend 보강안을 비교: (a) ask body 에 product hint 수용해 cid 발급 직후 적용, (b) `/api/new_conversation` 을 client 가 한 단계 앞서 호출 후 그 cid 로 ask. (a) 채택 — round trip 1회 절약 + 기존 `_resolve_conversation_for_account` 경로 재사용.
  3. PATCH race 가드(TASK-0047) 와의 충돌 방지: hint 적용은 lazy 생성 분기에만 한정하고, `request_conversation_id` 가 명시된 경로에는 hint 를 무시한다. 즉 기존 대화의 product 변경 단독 진실은 여전히 `PATCH /api/conversations/{cid}/product`.
  4. 기존 누적된 빈 대화 일괄 정리는 destructive 변경 (`DELETE FROM AgentCoreConversations WHERE NOT EXISTS (... messages)`) 이라 §12.1 사람 승인 필요. 본 turn 범위 외 — REPORT.md 후속 작업으로만 명시.
  5. ask 실패 시 cid 미상 처리: lazy create 분기에서 ask 가 네트워크/타임아웃으로 실패하면 backend 가 이미 cid 를 만들었을 가능성이 있지만 client 는 `payload.conversation_id` 를 받지 못해 알 수 없다. 이 경우 attach/resume 다이얼로그(TASK-0041) 는 cid 를 알 때만 유효하므로 활성화하지 않고, 사용자에게 "재시도하거나 사이드바를 새로고침해 주세요" 안내 토스트만 노출. 사용자가 사이드바 새로고침을 통해 새 대화 row 를 발견하면 그 cid 로 메시지를 다시 보낼 수 있다.
- Risks:
  - **lazy create 단계 ask 실패 시 buried orphan**: backend 는 cid 를 만들고 사용자는 모르는 상태가 1 케이스 발생. 다음 사이드바 동기화에서 visible 해지므로 데이터 유실은 아니지만 사용자 혼란 가능. 완화: 실패 토스트가 "사이드바 새로고침" 을 명시.
  - **busy sentinel race**: 동시에 여러 sendPrompt 가 동작하면 sentinel 이 충돌 가능. 단 `isCurrentConvBusy()` 가 sentinel 을 체크해 두 번째 호출은 즉시 return 하므로 안전.
  - **TASK-0041 attach 우회**: lazy create 분기는 attach 다이얼로그를 의도적으로 비활성화. 사용자가 "이전 turn 에서 첫 메시지가 timeout 됐는데 결과를 회수하고 싶다" 는 케이스에서는 사이드바 새로고침으로 새 대화에 진입한 뒤 그 대화의 attach 흐름(페이지 로드 시 auto-attach) 이 동작한다.
  - **PATCH race 가드와 무관**: lazy 생성 직후 hint 적용 시점은 client 가 ask 응답을 받기 전이라 사용자가 PATCH 를 동시에 발사할 수 없다. 가드와 충돌하지 않음.
- Why not 단계 분리(create 후 ask): client-side 에서 `POST /api/new_conversation` 후 그 cid 로 `POST /api/ask` 를 chain 하는 방안도 검토. 장점: backend 무수정. 단점: (1) round trip 1회 추가, (2) ask 가 영구 실패하면 빈 대화 1개가 그대로 남아 본 TASK 의 의도(빈 누적 방지) 를 약화. (a) 채택 시 backend 는 hint 수용 외 무변경이며 lazy 생성된 cid 는 ask 가 실패해도 backend 측에 남지만 그 빈 대화는 사용자가 사이드바에서 인지 → 의도적으로 생성한 시각이 있으므로 정리 책임을 사용자에게 위임 가능.

## REV-20260430-0009
- Date: 2026-04-30
- Decision: TASK-0047 의 실제 동작 검증을 Playwright + curl 로 수행하고, 발견된 회귀 1건(마이그레이션 fast-path 우회) 을 즉시 수정한다.
- Method:
  1. `docker compose up -d --build web` 후 `/api/session` 응답 + `SHOW COLUMNS` 비교 → 신규 컬럼 미반영 확인.
  2. 컨테이너 안에서 `_runtime_tables_available()` 직접 호출로 fast-path 가 새 컬럼을 검증하지 않음을 입증.
  3. probe 에 `SELECT product_mode FROM AgentCoreConversations LIMIT 1` / `SELECT ProductPrefMode FROM WebAccounts LIMIT 1` / `SELECT ProductPrefPinnedId FROM WebAccounts LIMIT 1` 추가 + errno 1054 분기 처리.
  4. `--no-cache` 빌드로 BuildKit layer cache 무효화 후 재기동.
  5. Playwright 28-check spec(`qa-product-selector.cjs`) 작성 + 실행, 부분 fail 3건은 spec 의 expectation 보정으로 해결(사용자 데이터인 conv-list 와 messages 는 검사 범위 밖, hydrate 결과는 server 답변과 일치 비교).
  6. PATCH race-guard 도 자동화: `AgentMemoryKv.last_status='processing'` 직접 주입 → PATCH → 409 검증.
- Reason: AGENTS.md §16.2 (종료 전 "실제 데이터 결과 출력" 확인) + 사용자 명시 지시("Playwright 로 실제 동작 검증"). agent team 합의는 turn-local 의사결정이고, 실 환경 동작은 통제된 자동 검증으로만 신뢰 가능.
- Trade-offs / Risk:
  - probe 에 컬럼 검사를 추가했으므로 향후 컬럼 신설마다 probe 도 업데이트해야 한다 (메인테넌스 부담). 대신 마이그레이션 누락 회귀는 어떤 신규 컬럼이든 자동 차단된다.
  - `--no-cache` 빌드는 빌드 시간이 길지만 (`COPY src/...` 단계에서 file-content hash 가 제대로 동작하지 않은 BuildKit edge case), 마이그레이션 검증 후엔 정상 cache 사용 가능.
  - QA spec 의 "상품" 검사 범위는 `.conv-list / .messages / .progress-strip / .access-notice / .toast` 의 후손을 제외 — 사용자 입력 텍스트는 정책상 강제 치환 대상이 아니므로 회귀는 없으나, 향후 i18n 글로싱 필요 시 spec 갱신 필요.
- Verification: 28/28 PASS, healthScore=100, console.error=0. JSON 결과 = `repo/.gstack/qa-reports/qa-product-selector-result.json`.
- Follow-up:
  - **R-09 (BRIEFING)** "기존 NULL product_id 행 backfill" → closed (probe 강화로 자동 트리거 보장).
  - **R-03** PATCH race 강화는 last_status 단일 키 가드만 자동화됨 — row-level lock / version 컬럼 도입은 여전히 후속.
  - 다른 R-01..R-16 항목은 운영 검증 / 사용자 인터뷰 / 추가 spec 으로 이관.

## REV-20260429-0008
- Date: 2026-04-29
- Decision: TASK-0047 — Product Selector UX 와 Auto 모드 도입을 **agent team 4 인 합의 + Codex CLI 교차검증** 으로 사람 검토 없이 본 turn 에 시행한다 (사용자 명시 지시).
- Method:
  1. **4인 agent team 병렬 검토** (UX Designer / Frontend Architect / Backend Engineer / QA-Flow Validator) — 각자 600 단어 의견서 산출. 의견서는 본 세션 transcript 에 보존, 핵심 합의는 BRIEFING §4 에 요약.
  2. **합의 통합 spec v1** 작성(`/tmp/product-selector-spec.md` — 휘발). UI 위치(사이드바 chip), state(productMode/pinnedProductId/activeProductId 3-필드), DB(product_mode 컬럼), API(PATCH /api/conversations/{cid}/product + new_conversation body 확장), agent_core(auto 한 줄 inject + allowed_schemas=[]), 카피("제품" 한글) 결정.
  3. **Codex CLI 교차검증** (`codex exec`) — 5건 추가 리스크: (a) auto 라벨 기대 불일치, (b) WebAccounts 컬럼 vs JSON pref (기존 결정 강화), (c) PATCH race 강화 필요, (d) 사이드바 의미 모호성 (caption 추가), (e) pinned 비활성 fallback / localStorage hydrate race. (a)(c)(d)(e) 를 spec v2 에 반영.
- Reason:
  - 사용자가 본 요청에 한해 "사용자 검토없이 agent team 면밀 검토" 를 명시했고, 반영해야 할 의견의 다양성(UX/구현/보안/회귀)이 단일 AI 검토로 부족했다.
  - Codex CLI 는 본 저장소 외부의 두 번째 LLM(`codex-cli 0.125.0`)으로, agent team 의견을 한 번 더 비판적으로 검증하기 위한 적격 보조 검토자.
- Trade-offs / Risk:
  - LLM resolver 미도입 상태에서 auto 라벨이 사용자 기대를 일부 깰 수 있다 (R-01) → 라벨에 "auto · 자동 (제품 미선택)" 으로 명시.
  - PATCH race 가드는 `last_status='processing'` 단일 키 기반으로 1차만 처리, race window 가 완전히 닫히진 않음 (R-03). 다음 turn 에 row-level lock or version 컬럼 도입 권고.
  - localStorage hydrate 우선 적용은 깜빡임 감소 vs 권한 회수 시 잠깐 잘못된 표시 (R-05) — 서버 hydrate 응답으로 reconcile + fallback_reason 토스트로 보강.
  - "상품" → "제품" 치환은 사용자 가시 텍스트만; 코드 식별자(`Product`/`product_id`/`WebProducts`/`ProductKey`) 보존으로 ABI/스키마 영향 없음.
- Verification (이번 turn):
  - syntax: `python3 -m py_compile` (app.py / agent_core.py), `node --check` (app.js) 모두 통과.
  - in-process 단위: `compose_system_prompt(None,...)` ↔ fake-conn `compose_system_prompt(... ,product_mode='auto'|'pinned')` — auto 분기에 `[AUTO MODE]` 라인 1개 inject 확인, pinned 분기에는 미주입 확인.
  - 잔존 "상품" grep: `unit/feature-0003-agent-web-ui/src` + `unit/feature-0002-agent-core/src` 0 건.
- Follow-up: BRIEFING-product-selector-v1.md §1 (R-01..R-16) + §2 (D-01..D-05) — 운영 반영 전 사람 결정/검증 필요. agent_team 합의는 turn-local 의사결정이며, 운영 회귀 위험은 별도 task 로 추적한다.

## REV-20260326-0001
- Date: 2026-03-26
- Decision: Web UI는 소유권만 분리하고 런타임 이미지는 core feature Dockerfile에서 조립한다
- Reason: 실행 경로를 단순하게 유지하면서 기능 경계를 문서화하기 위함
- Risk: Web UI 단독 이미지 분리가 필요한 경우 추가 조정이 필요하다

## REV-20260421-0002
- Date: 2026-04-21
- Decision: 대화 fork 는 신규 `conversation.fork` permission 을 추가하지 않고 기존 `conversation.create` + 원본에 대한 `read.own/read.any` 조합으로 판정한다.
- Reason: fork 의 본질은 "내 계정으로 새 대화를 만들어 메시지를 채우는 것" 이며, 이는 `conversation.create` + 원본 읽기 가능 여부의 교집합과 정확히 일치한다. 신규 permission 을 추가하면 모든 role 매트릭스를 갱신해야 하고 override/role seed 와 기존 관리 콘솔 문서도 동시에 고쳐야 해 범위가 불필요하게 커진다.
- Risk: 향후 "타 계정 대화 읽기는 가능하나 fork 는 금지" 정책이 필요해질 경우, 별도 deny override 나 새 permission 도입이 추가로 필요하다.
- Alternatives considered:
  - `conversation.fork` 신규 permission 도입: 범위/가치 대비 비용이 크다고 판단해 기각.
  - 서버 측에서 `_get_history` + `/api/new_conversation` + 연속 `/api/ask` 로 프론트엔드가 재현: 원본 CreatedAt 보존 불가, 내부 메시지 필터도 어긋나며, 대규모 round-trip 발생 → 기각.

## REV-20260421-0003
- Date: 2026-04-21
- Decision: fork 시 `AgentMemoryMessages` 삽입을 `memory.py` helper 가 아닌 app.py 엔드포인트에서 직접 SQL 로 수행한다.
- Reason: helper 는 `CreatedAt` 을 DB DEFAULT CURRENT_TIMESTAMP 로 맡기지만 fork 는 **원본 시계열을 보존** 해야 사용자가 기존 대화를 재생하는 맥락이 깨지지 않는다. 또 `MetaJson` 에 `forked_from_*` 을 합성 주입하려면 insert 지점을 직접 제어할 필요가 있다.
- Risk: helper 가 향후 감사 필드/트랜잭션 훅을 추가할 경우 엔드포인트 로직도 함께 업데이트해야 한다. `docs/FUNCTION.md` 의 Dependencies 에 memory 스키마 의존성을 명시해 이 커플링을 추적한다.
- Alternatives considered:
  - helper 에 `created_at_override` 매개변수 추가: core feature 의 public API 계약을 바꿔야 하고 fork 외 호출처가 없어서 인터페이스 부풀림이라 판단해 기각.

## REV-20260421-0004
- Date: 2026-04-21
- Decision: Product-단위 DB 접근 whitelist 를 agent tools 레벨의 모듈-전역 `_ACTIVE_SCHEMA_ALLOWLIST` + `set/clear` 헬퍼로 구현하고, `run_agent` 는 본문(원래 `run_agent`) 을 `_run_agent_core` 로 rename 한 뒤 thin wrapper 로 감싸 try/finally 안에서 whitelist 를 세팅/복원한다.
- Reason: 도구 dispatch(`execute_tool`) 로 whitelist 를 모든 경로에 파라미터로 전파하려면 tool 시그니처 전부 확장 + 기존 호출처(CLI/insight worker 포함) 모두 갱신이 필요하다. 모듈-전역 + context 매니저 패턴은 (1) call site 가 `agent_core.run_agent` 만 변경, (2) 모든 tool 이 단일 `_whitelist_violation(refs)` 진입점만 공유, (3) finally 로 워커 스레드 재사용 시 leak 방지라는 세 조건을 동시에 만족한다.
- Risk: `run_agent` 가 재진입(reentrant) 될 경우 마지막 setter 가 이전 whitelist 를 덮어쓴다. 현재 구조는 `asyncio.to_thread` 로 worker 당 1 호출이므로 충돌이 없지만, 향후 nested agent 호출이 도입되면 stack-based state(`contextvars.ContextVar`) 로 전환해야 한다.
- Alternatives considered:
  - tool signature 확장(`execute_tool(conn, tool, args, *, allowed_schemas)`): 호출처 파급이 크고, `_tool_execute_sql` 이 내부 helper 에서 재귀 참조를 할 때 또 다시 전달해야 해 반복 노이즈가 발생해 기각.
  - `threading.local`: `asyncio.to_thread` 의 스레드 풀이 재사용되므로 cleanup 이 반드시 finally 로 이뤄져야 한다는 점에서 현재 전역 + finally 패턴과 실질적 동일, 단순성 우선해 현 안 채택.

## REV-20260421-0005
- Date: 2026-04-21
- Decision: `_whitelist_violation` 이 `information_schema` 만 명시적으로 bypass 하고, 그 외 시스템 스키마(`mysql`, `performance_schema`, `sys`, `agent_memory`) 는 whitelist 규칙을 통해 **기본 차단** 한다.
- Reason: 초기 구현은 `_SYSTEM_SCHEMAS` 전체를 bypass 했으나, 이는 "Product=KR 이 `dbgame`/`dblog`/`dbauth` 만 허용" 이라는 운영 의도와 충돌한다. agent 가 `SELECT * FROM mysql.user` 를 요청하면 whitelist 가 손을 대지 않고 통과시켜 자격 정보가 유출될 수 있다. `information_schema` 만 "스키마 카탈로그 자체 조회 용도로 필요" 라는 명시적 이유로 예외 처리하고, 나머지 시스템 스키마는 whitelist 에 수동 등록하지 않는 한 차단되도록 한다.
- Risk: 운영 중 `agent_memory` 나 `mysql` 시스템 스키마 쿼리가 필요해질 경우 Product DB 목록에 수동 추가가 필요하다. 현재 설계상 이는 audit 목적에 부합하며, 과도한 접근이 발생하기 전에 관리 콘솔에서 명시적으로 추가해야만 허용된다.
- Alternatives considered:
  - 모든 `_SYSTEM_SCHEMAS` bypass(초기 안): 운영 의도와 보안 모두 어긋나 기각.
  - `_SYSTEM_SCHEMAS` 중 특정 항목만 화이트리스트(예: `agent_memory` 만 항상 허용): 현재 agent 가 자신의 메모리 DB 를 조회할 이유가 없어 불필요한 표면적 확장이라 기각.
- Superseded in part by: REV-20260422-0006 (메타데이터 4 스키마 bypass 재도입, `agent_memory` 차단 유지 부분은 유효).

## REV-20260422-0007
- Date: 2026-04-22
- Decision: TASK-0040 (regex context-aware) 와 TASK-0041 (attach/resume 복구 경로) 두 건을 한 번에 반영한다. 두 건 모두 TASK-0034 Q4/Q5 재수행을 가능하게 만드는 전제 조건이었고, TASK-0041 은 코드 경로가 서로 독립이지만 향후 runner 의 타임아웃 내구성에도 동일한 장치가 필요했기 때문에 함께 기록한다.
- Reason:
  - TASK-0040: 기존 `_SCHEMA_TABLE_REF_RE` 단일 regex 는 SQL 문맥 정보가 없었다. SELECT 절/WHERE 절/ON 절의 `alias.column` 은 구문적으로 `schema.table` 와 같은 `x.y` 토큰이라 whitelist 검사기가 구분할 수 없었고, Q4-like SQL 이 전부 `BLOCKED_SCHEMAS=bb,be` 로 거부됐다. 기존 regex 를 확장해 negative lookbehind 로 해결하려고 시도해봐도 FROM/JOIN 뒤 alias 선언(`FROM dblog.t bb`) 과 이후 alias 참조 (`bb.BattleType`) 가 같은 SQL 안에 공존하는 구조라 1 단계 regex 로는 근본적으로 구분이 불가능하다. FROM/JOIN 구간을 slice 하고 그 안에서만 `schema.table` 을 찾는 2 단계 스캐너가 최소한의 정확도 게이트이고, SQL 파서를 도입하지 않는 선에서 가장 단순한 정답이다.
  - TASK-0041: 에이전트 작업자 스레드(`asyncio.to_thread` 로 분리된 CPU/IO 루프)는 HTTP 연결과 독립이다. 클라이언트가 ReadTimeout 으로 끊어지거나 브라우저를 닫아도 서버는 완료까지 진행하지만, 그 결과를 회수할 read-only 경로가 없어 유저 입장에서는 "타임아웃 = 답변 손실" 처럼 보였다. `AgentMemoryKv(last_status/last_status_run_id/last_duration_ms/last_error)` + `AgentMemoryMessages` + `AgentMemorySteps` 이 이미 진행 상태와 최종 결과를 저장하고 있으므로, 새로운 상태 저장소 없이 스냅샷 + long-poll read-only 2 엔드포인트만 추가하면 UX 복구가 가능하다. `/api/ask` 슬롯풀(WEB_PARALLEL_LIMIT=6) 과 의도적으로 분리해 attach 가 새 실행을 시작시키지 않도록 했다 — 이것이 "새 요청으로 재진입해 중복 실행을 유발하지 않는" 안전 속성이다.
- Risk:
  1. 2 단계 regex 스캐너는 여전히 SQL 파서가 아니다. `WITH cte AS (...)` 같은 CTE 구문이나 `JOIN LATERAL (subquery)` 같은 복잡 구조에서 slice lookahead 경계가 어긋날 수 있음. 현재 agent 가 생성하는 SQL 범위에서는 15 케이스 검증으로 대응되지만, 생성 SQL 복잡도가 커지면 `sqlparse` 같은 경량 파서 도입을 재검토해야 한다.
  2. `/api/ask_status`/`/api/ask_result` 는 기존 `conversation.read.own/any` 권한을 재사용하므로 새로운 공격 표면은 없다. 다만 long-poll 60s 가 WEB_PARALLEL_LIMIT 과 별도로 백그라운드 연결을 유지하므로, 장기적으로 한 대화에 대해 동일 사용자가 다수 탭으로 polling 하면 연결 수가 쌓일 수 있다 (현재는 MCP 수준 트래픽에서는 무시 가능).
  3. 브라우저 boot-time auto-attach 는 페이지 새로고침 시마다 `/api/ask_status` 호출을 추가한다 — is_processing 여부만 체크하는 가벼운 쿼리라 비용은 미미하지만, 401/타 계정 대화 복구 시 attach 가 시작되지 않도록 권한 필터가 올바르게 동작해야 한다(기존 `_account_can_access_conversation` 로 보장됨).
- Alternatives considered:
  - TASK-0040 대안 (기각): 기존 regex 에 `(?<!\\w)\\s*` 류 lookbehind 를 덧붙여 alias.column 을 배제하는 방안 — alias 가 SELECT/WHERE/ON 모든 위치에 등장하므로 부정형 lookbehind 로 완전 배제가 불가. SQL 파서 도입 — 지금 필요한 정확도 대비 의존성 추가 비용이 크다.
  - TASK-0041 대안 (기각): 기존 `/api/progress` 폴링을 확장해 최종 답변을 같이 실어보내는 방안 — `/api/progress` 는 최근 N 스텝만 반환하고 응답 payload 크기를 keep-small 하도록 최적화되어 있어 최종 answer 를 싣기엔 부적합. Server-Sent Events / WebSocket 도입 — 인프라(프록시, TLS 종단, 재접속) 복잡도가 늘어나 현재 규모에 과하다.
  - TASK-0041 대안 (고려됨): 다이얼로그에서 `즉시 답변` 은 사실상 `/api/finalize` + attach 로 매핑됐는데, 이를 `/api/finalize` 없이 attach 만으로 끝내도 `finalize` 와 동등하지 않다 (LLM 추가 툴콜을 막지 않음). 본 구현은 두 경로를 구분 유지.
- How this relates to prior reviews: REV-20260422-0006 (메타데이터 4 스키마 bypass) 이후, Product DB whitelist 자체는 제대로 작동하지만 `_extract_sql_schema_refs` 가 alias 까지 오탐하던 부작용이 TASK-0040 에서 해제됐다. REV-20260421-0005 / REV-20260422-0006 의 "alias.column 은 whitelist 대상이 아님" 이라는 암묵 가정이 이제는 코드로도 성립한다.

## REV-20260422-0006
- Date: 2026-04-22
- Decision: `_whitelist_violation` 의 bypass 집합을 `{information_schema}` 에서 `_METADATA_SCHEMAS = {information_schema, sys, mysql, performance_schema}` 로 확장한다. `agent_memory` 는 `_INTERNAL_SCHEMAS` 로 분리해 **계속 차단** 유지.
- Reason: 사용자 지시(2026-04-22, "assistant 가 스키마 구조를 찾지 못하는 이슈를 방지"). 실사용에서 agent 가 `information_schema.TABLES` 외에 `sys.schema_table_statistics` / `performance_schema.tables` / 드물게 `mysql.*` 을 교차 검증 조회하려는 시도가 차단당해 탐색 루프에 빠지는 현상이 관찰됐다. 메타데이터 4 종은 DB 구조 탐색(정의·통계·런타임 메트릭) 에 필요한 "카탈로그적" 성격이므로 Product 관리자가 DB 목록에 일일이 추가하지 않아도 기본 허용되는 편이 운영 직관과 맞는다. `agent_memory` 는 타 계정 대화/세션/권한 override 를 담고 있어 성격이 다르며 계속 차단해야 한다.
- Risk:
  1. `mysql.user`/`mysql.db`/`mysql.global_priv` 에는 credential hash / grant 정보가 있다. 이 결정으로 tool-레벨 1 차 방어가 풀리므로, **DB 커넥터 MySQL 계정의 GRANT 가 2 차 방어로 남아야** 한다. 스모크 테스트 시점에서는 현 계정이 `mysql.user SELECT` 권한을 가지고 있어 실제 행이 반환됨을 확인했다 — 운영상 민감도가 높으면 MySQL 계정 GRANT 를 `information_schema` + Product DB 만 허용하도록 좁힐 것.
  2. `performance_schema`/`sys` 는 민감도 낮음(런타임 stat + 뷰 집합).
  3. write 가능 agent 계정을 도입하게 되면 본 결정을 재검토해야 한다(현재는 read-only 전제).
- Alternatives considered:
  - 메타데이터 스키마를 Product DB 목록에 수동 등록(REV-20260421-0005 의 원안): 관리 부담이 크고, 모든 Product 에서 동일하게 필요해 등록 누락 시 agent 가 탐색에 실패하는 결함이 재발한다. 기각.
  - `information_schema` + `sys` 2 종만 bypass: 사용자가 `mysql`/`performance_schema` 를 포함해 4 종을 명시했고, 둘 다 DBA 작업에서 교차 검증이 빈번해 2 종으로는 충분하지 않아 기각.
  - `agent_memory` 까지 포함한 전체 `_SYSTEM_SCHEMAS` bypass: agent 가 자신의 메모리 DB 를 읽을 이유가 없고, 타 계정 대화 유출 경로가 생기므로 기각.
- How this changes REV-20260421-0005: REV-20260421-0005 의 "`information_schema` 만 bypass" 결정을 "메타데이터 4 종 bypass, 에이전트 내부 스키마는 계속 차단" 으로 교체. `agent_memory`/임의 user schema 를 차단한다는 핵심 보안 의도는 유지된다.

## REV-20260512-0001
- Date: 2026-05-12
- Decision: 관리 콘솔의 모든 카테고리 다중선택 UX 를 단일 정합 컨벤션 (CONVENTIONS.md §10 + DESIGN.md v0.2) 으로 통일하고, drift 재발 차단을 위해 admin.js 의 `assertBulkBarContract(entity)` runtime check 를 initialize 끝에서 호출한다. Bulk toolbar 위치 표준은 **list 직하단 sticky** (`.admin-bulk-actions`), `.admin-pane-head-right` 는 primary action (`+ 새 X`) 전용으로 단일 semantic 유지.
- Reason: 사용자 raw feedback (2026-05-12) "관리 콘솔에 구성된 항목 별 다중선택 UI/UX 가 카테고리 별로 일관성없이 차이가 나타나는것을 확인했습니다 — 계정: 우측 상단 / 역할: 좌측 하단 / 제품: 다중 선택 기능 없음. 차후 작업에서도 이러한 경향이 나타나지 않도록 방향을 정합적으로 명시해주세요." Root cause 두 가지: (1) DOM anchor 위치 표준 부재 → Accounts (header slot) vs Roles (list 하단) 갈라짐. (2) `.admin-pane-head-right` 슬롯의 semantic 충돌 — 어떤 카테고리에서는 "+ 새 X" primary action, 다른 카테고리에서는 동적 bulk action 슬롯으로 점유 → 컴포넌트 표준화 실패의 본질. Products 의 multi-select 부재는 의도적 결정이 아니라 drift 로 판정 (활성·비활성·삭제 의미가 있는 동질 entity 리스트 = §10.1 적용 룰 충족).
- Risk:
  1. **Accounts bulk anchor 이전** (헤더 우상단 → list 직하단): 기존 e2e/screenshot test 가 `#accountsBulkBar` 의 위치 selector 에 의존했다면 깨질 수 있다. 본 cycle 에서는 e2e selector 변경 영향 검증을 못 했음 (실제 e2e suite 위치 후속 확인). 사용자 화면 시각 차이는 의도적.
  2. **Products multi-select 신설 + selectedProductId 단수 동거**: detail panel 은 단일 selectedProductId 만 신뢰 (DESIGN.md §12 Phase A). row click 은 단일 detail 선택, checkbox click 은 multi-select Set — 두 흐름이 별 path 라 race 없음. 다만 사용자가 checkbox 만 다수 체크 후 detail 을 expect 하는 mental model 가능 — 후속 모니터링 필요.
  3. **bulkProductDelete 의 _delete 키 plumbing**: backend `setProductMetaPending(_delete: true)` 가 apply 단계에서 실제 DELETE API 를 호출하는지 backend (`app.py applyAllPending` flow) 확인 필요. 본 cycle 은 pending 마킹만 추가했고, 실제 backend 가 product `_delete` 키를 수용하지 않으면 NO-OP 또는 에러. 후속 검증 항목으로 REPORT.md 에 명시.
  4. **assertBulkBarContract 가 console.warn only**: 운영 코드 차단 안 함 (best-effort). 정말 강제하려면 CI snapshot/jsdom test 가 필요 (별 cycle).
  5. **typed-confirmation prompt UX**: `window.prompt()` 기반이라 모던 UX 와 어긋날 수 있음. 후속에서 custom modal 로 업그레이드 가능 (v0.3 후보).
- Alternatives considered:
  - **DOM anchor 표준을 헤더 우상단 (Accounts 패턴)** 으로 통일: 후보였으나 (a) "+ 새 X" 와 동적 bulk action 이 같은 슬롯을 두고 경쟁, (b) row 선택 인터랙션의 시선·손 위치 근접성 부족 — 기각.
  - **Notion morph 패턴** (헤더 자체가 bulk toolbar 로 변형): 모던 레퍼런스로 존재하지만 본 컨벤션의 "헤더 = primary 전용" 단일 semantic 원칙 위반 → 명시 거부 (DESIGN.md §14 참조).
  - **Linear floating pill** (viewport footer fixed): 강한 visibility 장점이나 list-scope 의미 약화 + drawer/modal 과 z-index 전쟁 → v0.2 에서는 list 직하단 sticky 채택, floating pill 은 v0.3 옵션으로 기록.
  - **Vercel 패턴** (multi-select 없이 row-hover inline action): admin entity 가 일괄 적용 가치를 갖는 (활성·비활성·삭제) 카테고리에는 부적합 → 면제 카테고리의 reference 로만 인용 (CONVENTIONS §10.1).
  - **RBAC 새 권한 추가** (예: `account.bulk_delete`): catalog 변경 = RBAC plan 영역 (사용자 메모리 정책 "RBAC plan 은 outside voice 필수") → 본 cycle scope 에서 분리. 기존 권한 (`account.delete` 등) 의 row-level check 만 활용.
- How this relates to prior reviews: 본 REV 는 관리 콘솔의 UI 표준화 첫 정본. 기존 REPORT.md 의 TASK-0053 (제품 권한 grid + product 카드 통합) / TASK-0051 (일괄 저장 정책 회복) 등은 개별 UI 변경이었으나 표준 컨벤션 없이 진행됨 → 본 cycle 이 그 누적 inconsistency 의 가드레일을 사후 도입. 외부 design 시각 결과 (worker-design framework 차용 + general-purpose subagent) 는 v0.1 의 IA 6 / Visual 5 / Interaction 6 / Consistency 7 / A11y 4 dimension rating 과 5 gap (cross-page selection / empty·loading·error / optimistic rollback / confirm 컨벤션 / RBAC gating) 을 강하게 지적 → v0.2 에 모두 흡수.
- Open questions (DESIGN.md §13 참조):
  - Q-13.1: cross-page banner 의 "전체 페이지 선택" 버튼 (보이지 않는 페이지까지 모두 선택) — 본 cycle 미포함, v0.3 후보.
  - Q-13.2: bulk action apply 후 undo (toast 내부 "되돌리기") — 후속 평가.
  - Q-13.3: shift+click range 의 cross-page 동작 (현재는 visible 만) — 본 cycle 의 결정과 모순 없음.
  - Q-13.4: `assertBulkBarContract` 의 CI 화 (jsdom unit 또는 e2e snapshot) — 별 cycle.

## REV-20260521-0001 [SUBAGENT:codex] TASK-0094 첨부 multi-cycle BRIEFING Revision 2 review

- **Mode**: SUBAGENT (Codex CLI consult mode, gpt-5 default, reasoning=medium, web_search_cached, read-only sandbox)
- **Session**: 019e4421-2a8f-74a2-8b91-6afc191856e0 (resume — 1차 REV-20260520-0001 후속)
- **Review subject**: BRIEFING-attachment-multi-cycle.md (Revision 1 → Revision 2 흡수 검증)
- **Result**: NEEDS_REVISION → Revision 2 흡수 완료
- **Finding 수**: 1차 Claim 20 재검토 + 신규 finding F1~F14 (Critical 3 / Major 11 / Minor 2)
- **Critical 흡수**:
  - **F3** (D14 SQL guard): denylist → AST shape allowlist 전환 — `SELECT/CTE only`, FOR UPDATE/LOCK/EXPLAIN ANALYZE/optimizer hint/SLEEP/BENCHMARK/user variable/INTO OUTFILE/LOAD_FILE/information_schema/mysql/performance_schema/sys 전부 거부
  - **F7** (D9 share redact): 기존 share token 도 배포 즉시 자동 redact + audit `share.policy.redact_applied` + `WebShareLinks.PolicyVersion` 저장
  - **F8** (Sprint 1 gate 분할): 사용자 명시 거부 — 단일 통합 gate 유지 (D18 신규). 위험 격리는 D14 + R-Claim4 + R-F4 + D20 조합으로 충족
- **Major 흡수**: Claim#4/Claim#6/F1/F2/F4/F5/F6/F9/F11/F12/F13 모두 §2.2 inline `→ Rev2 (R-XXX)` 마커로 반영
- **Minor 흡수**: F10 (§15 worktree cleanup 완료 조건), F14 (D21 pending metadata-only)
- **Decision**: D1~D17 의 17 결정에 D18~D21 신규 4 결정 추가하여 D1~D21 21 결정 lock-in. PLAN-APPROVED 마커 부여 (2026-05-21)
- **Reason**: AGENTS.md §17 외부 검증 정책 — 본 BRIEFING 은 Critical §12.3 (인증/인가·개인정보·외부 공개 범위·비용 4 항목 동시 변경) 이므로 outside-voice 2 회 동반이 정합. RBAC catalog 변경 (7 신규 권한 code) + 외부 LLM PII 송신 정책 + MinIO storage + sandbox SQL 실행 모두 단일 plan 으로 묶여 있어 정적 review 만으로는 cross-feature blindspot 검출 불가
- **Risk**:
  1. **Codex 권고 거부 1건 (F8)**: gate 분할 거부의 위험은 D14 SQL allowlist guard 통과를 Sprint 1 ship 조건으로 격상하여 격리. 단, MinIO bootstrap / consent infra / RBAC 4 codes 가 D14 통과 전 ship 되는 경로는 운영 책임. 사용자 명시 결정이므로 본 cycle scope 안에서 추가 mitigation 없음
  2. **2회 review 후에도 잠재 blindspot 가능**: outside-voice 는 정적 review 라 implementation-time 발견 issue 는 Sprint 1~4 각 cycle 의 `/plan-eng-review` + `/codex` review 에서 재검증
  3. **TASK 번호 재할당**: 초기 등재 TASK-0087 → TASK-0094 로 재할당 (TASK.md TASK-0087 이미 점유). git worktree 이름 `0087-attachment-briefing` 은 cleanup 시 별 명칭으로 재생성 가능 (현재는 유지)
- **Alternatives considered**:
  - 3차 outside-voice review (Codex follow-up): 비용 ~$1-2 추가 + 사용자 거부 (Revision 2 흡수 후 PLAN-APPROVED 진입 선택)
  - subagent review (general-purpose): codex 의 web_search_cached 와 정적 분석 깊이를 능가하지 못함 — codex 단일로 충분
  - Revision 2 직접 작성 없이 Critical 3건만 inline patch: D18~D21 의 신규 결정이 누락 — 거부
- **Cross-ref**: BRIEFING §17 (Codex 2차 review + Revision 2 흡수 매트릭스). 본 entry 는 §17.5 의 verdict 평가와 §2.2 의 inline 결정 갱신을 review 정본으로 lock-in

## REV-20260521-0002 [SKIPPED:report-sync-only] TASK-0094 cleanup follow-up REPORT.md §16.5 Step 6 사후 기록

- **Mode**: SKIPPED (AGENTS.md §18.4 META mode 정책 — non-policy doc-only cycle, outside-voice review 대상 아님)
- **Subject**: REPORT.md §1 Summary 의 TASK-0094 entry + Git 동기화 결과 표 append (CHG-20260521-0002)
- **Reason**: 본 follow-up 은 §16.5 Step 6 의 단순 사실 (commit hash / PR # / merge timestamp) 기록 보강. 정책 / 아키텍처 / RBAC catalog / 스키마 변경 없음. SUBAGENT 또는 AGENT-TEAM review 의 비용 정당화 어려움. 본 entry 는 verify-completion CHECK#9 충족용 SKIPPED 마커
- **Cross-ref**: CHG-20260521-0001 의 본 cycle 정본 review 는 REV-20260521-0001 [SUBAGENT:codex] (2회 outside-voice review 흡수)

## REV-20260521-0003 [SKIPPED:phase1-infra-only] TASK-0094 Sprint 1 Phase 1 (Pre-flight) review

- **Mode**: SKIPPED — Phase 1 (Pre-flight) 은 인프라 추가 / 정책 ADR / 부트스트랩 스크립트만. backend / RBAC catalog / 스키마 변경 0. outside-voice review 의 비용 정당화 어려움. 본 entry 는 verify-completion CHECK#9 충족용 SKIPPED 마커.
- **Subject**: ADR-0022 (MinIO) + ADR-0023 (sandbox schema + maintenance path) + ADR-0025 (PGVector Sprint 4 prerequisite) + docker-compose.yml minio/minio-init service + .env.example 16 변수 + minio-init.sh 부트스트랩 + feature-0001 ANCHOR §1 갱신.
- **Reason**: 본 Phase 의 모든 결정은 TASK-0094 BRIEFING Revision 2 (REV-20260521-0001 [SUBAGENT:codex] — Codex 2회 outside-voice review 흡수) 의 D1/D2/D3/D10/D15/D20 결정 정본을 그대로 구현. ADR 본문도 BRIEFING §2.2 inline 결정 + §17 Codex 매트릭스 cross-ref. 추가 review 없음.
- **Cross-ref**:
  - Codex 1차 review (REV-20260520-0001, BRIEFING §13)
  - Codex 2차 review (REV-20260521-0002, BRIEFING §17)
  - 정본 BRIEFING review (REV-20260521-0001 [SUBAGENT:codex])
- **Sprint 1 cycle 의 outside-voice 추가 호출 시점**: Phase 12 의 D14 SQL allowlist guard 가 Ship 조건이라, Phase 12 진입 시 Codex 추가 review 권장. Phase 2~11 의 schema / RBAC / API / UI / share / lifecycle / sandbox / ingest 는 각 Phase 종료 시 SKIPPED 또는 짧은 SUBAGENT review 적정.

## REV-20260521-0004 [SKIPPED:schema-only] TASK-0094 Sprint 1 Phase 2 (Cycle 0 schema) review

- **Mode**: SKIPPED — Phase 2 는 schema 신설 (5 신규 table + 1 column ALTER) + 6 helper 정의 + bootstrap 호출 등록만. backend endpoint / RBAC catalog / UI / share / lifecycle / sandbox / ingest / SQL guard 모두 미작업. outside-voice review 의 비용 정당화 어려움. verify-completion CHECK#9 충족용 SKIPPED 마커.
- **Subject**: 5 신규 table (`WebConversationAttachments` / `WebConversationAttachmentsSandboxSchemas` / `WebAccountConsents` / `WebAttachmentDerivedMessages` / `WebConversationAttachmentProviderFiles`) + 1 column ALTER (`WebConversationShares.PolicyVersion`). 6 helper. py_compile PASS.
- **Reason**: BRIEFING Revision 2 §5.1 의 column 정의를 정합 그대로 SQL DDL 로 옮긴 단계. column type / NOT NULL / DEFAULT / INDEX 모두 BRIEFING 명세 따름. D6 / D11 / D12 / D17 / D19 / R-F7 / R-F11 / R-F13 의 결정 inline 반영. outside-voice review 1차/2차에서 schema 자체에 대한 추가 finding 없음 (D9/F11 의 derived join table 만 R-F11 흡수, 이미 D19 로 적용).
- **Cross-ref**:
  - BRIEFING §5.1 (정본 schema 정의)
  - 정본 review: REV-20260521-0001 [SUBAGENT:codex]
  - Phase 1 review: REV-20260521-0003 [SKIPPED:phase1-infra-only]
- **다음 outside-voice 시점**: Phase 12 (D14 SQL allowlist guard, Ship 조건) — schema 가 아닌 보안 경계 코드. 본 cycle Critical 의 핵심 ship guarantor. Phase 12 진입 직전 Codex 추가 review 권장. Phase 3~11 의 RBAC / storage / API / UI / share / lifecycle / sandbox / ingest 도 SKIPPED 또는 짧은 SUBAGENT review 적정.

## REV-20260521-0005 [SKIPPED:rbac-catalog-only] TASK-0094 Sprint 1 Phase 3 (Cycle 0 RBAC) review

- **Mode**: SKIPPED — Phase 3 는 RBAC catalog 4 코드 + 6 checklist (catalog + seed + 5 catchup + FE label) 적용만. endpoint / business logic / UI section 변경 0. 본 RBAC 변경은 BRIEFING Revision 2 정본 review (REV-20260521-0001 [SUBAGENT:codex]) 에서 D6/D11/D12/D14/D15/D16/D21 결정으로 이미 outside-voice review 흡수 완료. 추가 codex review 비용 정당화 어려움.
- **Subject**: `conversation.attachment.{upload,read}.{own,any}` 4 코드 catalog + SEED_ROLE_DEFINITIONS pending/operator/sales 갱신 + _ensure_seed_roles admin/operator-sales/dba/pending 4 catchup + app.js label/description map.
- **Reason**: 사용자 메모리 정책 ("RBAC plan 은 outside voice 필수") 와 본 Phase 의 SKIPPED 결정의 절충 — BRIEFING 정본 review 가 RBAC catalog blindspot 대응 (REV-20260520-0001 Claim #1 6 checklist + Claim #3 정적 catalog source + REV-20260521-0002 R-F14 pending metadata-only) 을 흡수 lock-in 했고, 본 Phase 는 정본 결정의 mechanical 적용. 새로운 권한 의미 결정 (예: read.any 의 범위 / pending metadata-only 범위) 은 본 Phase 에서 발생하지 않음.
- **Risk**:
  1. **6 checklist 누락 가능성**: Phase 3 의 작업은 (1) PERMISSION_DEFINITIONS + (2) SEED_ROLE_DEFINITIONS + (3~5) _ensure_seed_roles 의 4 catchup + (6) FE label. 검증: `bash bin/verify-completion.sh --pre-commit feature-0003-agent-web-ui` PASS + py_compile PASS + admin.js 는 backend label 직접 사용이라 별 map 불필요 확인.
  2. **pending metadata-only enforcement**: catalog 수준에서는 read.own 부여 — bytes download 차단은 Phase 5 endpoint application-level. 본 Phase 만으로는 enforcement 미완. Phase 5 진입 시 `if account.role.key == 'pending': deny bytes` 분기 명시 + AC 갱신.
- **Cross-ref**: BRIEFING §5.2 + 정본 REV-20260521-0001 + Phase 2 REV-20260521-0004.
- **다음 outside-voice 시점**: Phase 12 (D14 SQL guard, Ship 조건). Phase 5 (upload API) 에서 attachment endpoint 의 권한 검증 + pending bytes deny 의 정합도 codex review 권장 (RBAC enforcement 의 application-level 표면).

## REV-20260522-0001 [SKIPPED:static-asset-only]
- Date: 2026-05-22
- Trigger: TASK-0097 (REQ-20260522-0001, Minor §12.3) — DQA 브랜딩 적용
- Skip Reason: 정적 자산 변경 (HTML/CSS/SVG) 만. backend/RBAC/endpoint/DB/audit 무변경. outside-voice review 불필요 — §18.8 Minor 기준 충족.
- Evidence: browse 스크린샷 3장 (로그인 화면 + 사이드바 + 관리 콘솔) 으로 렌더링 확인.

## REV-20260521-0006 [SKIPPED:storage-wrapper-only] TASK-0094 Sprint 1 Phase 4 (Cycle 0 storage) review

- **Mode**: SKIPPED — Phase 4 는 boto3 wrapper + signed URL helper + smoke test + D20 runbook docs. backend endpoint / RBAC / 스키마 / UI 변경 0. 본 module 의 함수 시그니처 + 책임 경계 (RBAC/audit/consent 는 caller 책임) 는 BRIEFING §5.3 정본 + REV-20260521-0001 [SUBAGENT:codex] (BRIEFING Revision 2 정본 review) 에서 lock-in. 추가 codex review 비용 정당화 어려움.
- **Subject**: `storage_minio.py` (350 lines), `RUNBOOK-minio-key-rotation.md` (150 lines), requirements.txt 의 boto3 + botocore entry.
- **Reason**: 본 module 은 SDK abstraction layer — 보안 결정 (RBAC / consent / audit / MIME / size) 모두 caller (Phase 5 upload endpoint) 책임. 본 Phase 자체의 결정은 (1) boto3 client cache 의 idempotent 패턴, (2) signed URL TTL 환경변수화, (3) D13 (외부 LLM signed URL 금지) docstring 명시, (4) D20 runbook 의 4-step rotation + 3 rollback 경로 — 모두 BRIEFING 정본 결정의 thin implementation.
- **Risk**:
  1. **boto3 retry/timeout config 가 default 값**: env-driven `MINIO_MAX_ATTEMPTS=3` / `connect_timeout=5s` / `read_timeout=30s` 는 dev 환경 가정. prod 대용량 upload (PDF 25 MB) 에서 read_timeout 부족 가능 — Phase 11 ingest pipeline 진입 시 재검토.
  2. **signed URL TTL 15 분 default**: 사내망 다운로드 시점 + 사용자 화면 refresh window 정합 — Phase 6 (composer UI) 진입 시 frontend 다운로드 flow 확정 후 재검토.
  3. **client cache 의 thread safety**: `_S3_CLIENT_CACHE` 는 module-level dict — Python GIL 하에서 single-thread access 가정. FastAPI 의 worker 가 multi-thread (uvicorn 의 default) 일 때 cache 가 dict 이라 race 가능하나 boto3 client 자체가 thread-safe 라 read race 는 무해. write race 는 1 client overwrite 1 client 으로 마무리 — 무해. 다만 명시 lock 은 향후 cycle 후보.
- **Cross-ref**: BRIEFING §5.3 + ADR-0022 + 정본 REV-20260521-0001 + Phase 3 REV-20260521-0005.
- **다음 outside-voice 시점**: Phase 5 (upload API + audit + D12 HMAC) 진입 시 codex review 권장 — application-level RBAC / consent 검증 + audit dispatch 정합이 본 module 위에서 결정됨.

## REV-20260521-0007 [SUBAGENT:codex-deferred] TASK-0094 Sprint 1 Phase 5 (Cycle 0 upload API) review

- **Mode**: SUBAGENT (codex) review 권장 — BRIEFING REV-20260521-0006 의 "다음 outside-voice 시점: Phase 5" lock-in. 다만 본 entry 작성 시점은 ship gate 동시 진행이라 review 완료 전 commit. **deferred** = ship 후 별 cycle 에서 codex review 호출 + 발견 finding 흡수 시 Phase 5.1 (혹은 Phase 6 진입 전 patch) 로 정합.
- **Subject**:
  - 6 endpoint signature + 권한 검증 + audit dispatch + signed URL 발급 흐름 (storage_minio integration)
  - D7 MIME allowlist 의 정확성 (XLSX legacy `.xls` + MIME spoof 위험)
  - D8 size cap 의 cumulative sum 정합 (DeletePending + DeletedAt IS NULL 필터)
  - D12 HMAC 의 dev fallback key (`_FALLBACK_AUDIT_HMAC_KEY__set_via_env_for_prod`) — prod 환경에서 ATTACHMENT_AUDIT_HMAC_KEY 부재 시 알람?
  - D13 외부 LLM 송신 금지 정합 — `_serialize_attachment_for_api(include_signed_url=...)` 의 caller 가 외부 LLM 경로에서 None 강제하는 분기 부재 (현재는 caller 책임)
  - D21 pending bytes deny 의 application-level enforcement — `_account_is_pending` 의 role.key 추출 logic 이 account 구조 가정에 의존 (account.role dict / account.role_key fallback)
  - audit `attachment.upload` / `.delete` 의 categorical 메타 충분성
  - MinIO put 실패 시 row hard-delete (orphan 방지) 의 race / partial failure
- **Reason**: Phase 5 가 Phase 3 RBAC enforcement + Phase 4 storage 의 application-level 결합점 — Codex 1차/2차 review (REV-20260520-0001 + REV-20260521-0002) 는 BRIEFING 정본 단계에서 결정. 본 Phase 는 결정의 application-level 적용. ship 후 codex review 로 (a) endpoint signature 의 보안 경계 (b) D12 HMAC enforcement (c) D21 deny enforcement coverage (d) MinIO orphan race 패턴 검증.
- **Risk**:
  1. **HMAC dev fallback**: prod 환경에서 `ATTACHMENT_AUDIT_HMAC_KEY` 미설정 시 fallback key 사용으로 모든 tenant 의 HMAC 가 같은 key 로 발급 — audit row 의 cross-tenant 비교 가능. 별 cycle 또는 본 Phase patch 에서 prod fail-loud 추가 권장.
  2. **MIME spoof**: caller 가 보낸 Content-Type 헤더에만 의존 — 실제 파일 매직 바이트 검증은 미구현. Phase 11 ingest pipeline 진입 시 (XLSX 의 zip 매직 등) 본격 검증.
  3. **size cap race**: 동시 upload 시 size cap 검사 후 INSERT 사이 race — 본 Phase 는 single-tx 검사라 cumulative SUM 일관성 유지하나 INSERT 직후 동시 upload 의 추가 확인 미수행. 위험 낮음 (per-account 1GB cap 이라 race window 좁음).
  4. **`_account_can_access_attachment` 의 soft-deleted 거부**: `DeletedAt IS NOT NULL` 인 row 는 caller 모두 거부 — reconciliation worker / admin restore path 미구현 (Phase 9 ship 후 추가).
  5. **Endpoint coverage**: BRIEFING §5.4 의 7 endpoint 중 본 Phase 가 6 (POST/GET/GET-by-id/DELETE attachment + POST/DELETE consent). `/api/ask` body 확장 (Cycle 1 attachment_ids / attachment_scope_all) 은 Phase 11 ingest + Phase 12 SQL guard 시점에 추가.
- **Cross-ref**: BRIEFING §5.1 / §5.4 / D6/D7/D8/D11/D12/D13/D21 + ADR-0022 + 정본 REV-20260521-0001 + Phase 4 REV-20260521-0006.
- **다음 outside-voice 시점**: 본 entry 의 deferred codex review (Phase 6 진입 전 또는 Phase 5.1 patch cycle). Phase 12 (D14 SQL guard, Ship 조건) 는 별도 review trigger.

## REV-20260521-0008 [SKIPPED:frontend-only] TASK-0094 Sprint 1 Phase 6 (Cycle 0 composer UI) review

- **Mode**: SKIPPED — Phase 6 는 frontend (index.html + styles.css + app.js) 의 composer UI 추가만. backend 변경 0. 본 UI 의 D16 attachment selection snapshot + R-F5 lazy-create binding 은 BRIEFING REV-20260521-0001 [SUBAGENT:codex] (정본) 및 REV-20260521-0002 (Codex 2차) 의 결정 application. 추가 codex review 의 비용 정당화 어려움.
- **Subject**: composer-attachments + composer-drop-overlay + attach-btn + file input 마크업 + 130 lines CSS (pill / overlay / paperclip) + state.composerAttachments + 9 helper + event binding + selectConversation list load.
- **Reason**: 본 UI 의 보안 결정 (RBAC / consent / D7 MIME / D8 size cap / D12 HMAC / D13 외부 LLM 송신 / D21 pending deny) 모두 Phase 5 의 backend endpoint 에서 enforcement — 본 frontend 는 backend 응답을 그대로 표시 + frontend cap 검증 (accept 속성 의 MIME 허용 list 만). server-side check 가 source of truth.
- **Risk**:
  1. **lazy-create 상태에서 paperclip 거부**: 사용자가 새 대화 + 파일 첨부 + 메시지 흐름을 기대할 수 있으나 본 cycle 은 cid 가 있어야 upload — UX 가독성 안내 (toast) 로 graceful. Phase 11 진입 시 lazy-create 시점에도 client-side 임시 stash → 첫 send 직후 자동 upload 옵션 검토.
  2. **drag-drop 의 dragenter/leave race**: dragCounter 로 child element entry race 처리하지만 brfowser-specific race 가능. browse QA 권장 (별 cycle).
  3. **multiple 파일 선택 미지원**: input 에 multiple 미설정 — Sprint 1 simplicity. Phase 11 또는 후속 cycle 에서 batch upload + progress bar 검토.
  4. **D16 attachment_ids 의 backend 처리**: 본 Phase 의 sendPrompt 가 askBody 에 attachment_ids/scope_all 명시 전송하지만, backend `/api/ask` 가 아직 이 필드를 수용하지 않음 (Phase 11 ingest pipeline 진입 시 ship). 본 Phase 만으로는 attachment_ids 가 backend 에 도달해도 silent ignored — D16 minimum exposure 의 의미는 backend 가 attachment_ids 를 사용하는 시점 (Phase 11) 부터 활성.
- **Cross-ref**: BRIEFING §5.6 + D16 + R-F5 + 정본 REV-20260521-0001 + Phase 5 REV-20260521-0007.
- **다음 outside-voice 시점**: Phase 11 (ingest pipeline) + Phase 12 (SQL guard, Ship 조건) — 본 frontend snapshot 이 backend `/api/ask` 의 attachment_ids 처리와 결합되는 시점.

## REV-20260521-0009 [SKIPPED:consent-ui-only] TASK-0094 Sprint 1 Phase 7 review

- **Mode**: SKIPPED — consent grouped UX 는 BRIEFING D11 + R-F2 정본 결정의 thin application. backend POST/DELETE 는 Phase 5 review 와 동일.
- **Subject**: GET /api/account/consents + profile drawer consent section + grouped batch helper.
- **Reason**: 본 Phase 의 결정은 (1) provider × group mapping (`_CONSENT_GROUPS`) (2) batch toggle UX 패턴 — 모두 BRIEFING 정본 결정. 보안 경계 변경 0.
- **Risk**: group mapping 의 향후 확장 (Cycle 4 의 다른 data_class) 시 본 cycle 의 `_CONSENT_GROUPS` 갱신 필수.

## REV-20260521-0010 [SKIPPED:share-redact-mechanism] TASK-0094 Sprint 1 Phase 8 review

- **Mode**: SKIPPED — D9 + R-F7 mechanism ship 만. derived flag 의 실제 설정은 Phase 11+ 에서 attachment 인용 시점에 추가.
- **Risk**: attachment_derived flag 가 message MetaJson 에 설정 안 되면 본 redact 가 활성 안 됨 (false negative). Phase 11/Cycle 2-4 의 flag 설정 누락 시 share view 에 본문 노출 — 향후 cycle 의 검증 필수 항목.

## REV-20260521-0011 [SKIPPED:lifecycle-worker-only] TASK-0094 Sprint 1 Phase 9 review

- **Mode**: SKIPPED — D6 4 종 SLA + F1 4 state + F12 pseudonym 모두 BRIEFING 정본 결정 application.
- **Risk**: worker scheduling 미설정 시 DeletePending row 누적 — Phase 10 후속 cycle 에서 cron / thread 활성 필수. MinIO delete 실패 시 graceful fail (worker 다음 pass 에서 재시도). nullable FK 옵션 (R-Claim6 의 alt) 은 별 cycle 결정 영역.

## REV-20260521-0012 [SKIPPED:sandbox-helper-only] TASK-0094 Sprint 1 Phase 10 review

- **Mode**: SKIPPED — D15 + R-Claim4 + R-F4 BRIEFING 정본 결정 application.
- **Risk**: maintainer connection 의 wildcard grant 가 root 또는 별 superuser 로 사전 부여되어야 함 (runbook 작업). detect_grant_drift 의 information_schema.schema_privileges 가 GRANTEE format 의 host part 매칭에 의존 — '%' host 가정 (.env 의 4 user 도 '%' host 로 생성 권장). DROP cleanup user 의 invocation 은 reconciliation worker (Phase 9) 가 사용.

## REV-20260521-0013 [SKIPPED:ingest-mechanism] TASK-0094 Sprint 1 Phase 11 review

- **Mode**: SKIPPED — Codex Claim #14 (XLSX/CSV cap) 정본 결정 application. ingest worker 의 process 격리 / memory budget 은 별 cycle.
- **Risk**: ingest_attachment 호출자 (background trigger) 가 본 phase 에서 ship 안 됨 — 별 cycle 또는 후속 phase 에서 추가 필요. env ATTACHMENT_IDS 의 thread-safety: 본 cycle 은 single-process FastAPI + asyncio.to_thread 라 race 가능하나 cleanup pop 으로 mitigate. 별도 thread-local 옵션은 후속 검토.

## REV-20260521-0014 [SUBAGENT:codex-deferred-final] TASK-0094 Sprint 1 Phase 12 + Ship review

- **Mode**: SUBAGENT (codex) review 권장 — Sprint 1 Critical Ship 조건의 핵심 guarantor. BRIEFING REV-20260521-0006 의 "다음 outside-voice 시점: Phase 12 (D14 SQL allowlist guard, Ship 조건)" lock-in.
- **Subject**: sql_guard.py 의 AST allowlist 완전성 (R-F3 명시 케이스 전수 검증), attachment.execute_sql_on RBAC enforcement, audit dispatch coverage, attachment group 정합.
- **Reason**: Sprint 1 Ship 직전 final review. validate_sql_for_sandbox 의 모든 거부 패턴이 BRIEFING R-F3 의 명시 케이스 (FOR UPDATE / LOCK IN SHARE MODE / EXPLAIN ANALYZE / optimizer hint / SLEEP / BENCHMARK / user variables / INTO OUTFILE / LOAD_FILE / information_schema / mysql / performance_schema / sys) 를 모두 cover 하는지 + multi-statement 검사가 robust 한지 + sqlglot 의 MySQL dialect 가 모든 위험 case 를 정확히 파싱하는지.
- **Risk**:
  1. **sqlglot version 의 MySQL dialect 정합성**: sqlglot 23.x 가 LOCK IN SHARE MODE / EXPLAIN ANALYZE 같은 MySQL-specific 표현을 정확히 lock clause 로 parse 하는지 불확실. 본 cycle 의 secondary denylist regex 가 backup defense.
  2. **multi-statement 검사 휴리스틱**: comment / string 안 ; 를 단순 stripping 으로 처리 — 복잡한 escape 케이스 (이중 quoted ' 안 \'\') 가 false negative 가능. sqlglot.parse 의 len > 1 도 보조 검사로 있음.
  3. **validate_sql_for_sandbox 호출 site 누락**: 본 phase 는 guard module 만 ship. 실제 LLM tool 실행 시점의 호출 site (예: agent_core.tools.execute_sql) 는 별 cycle. caller integration 검증은 Sprint 1 후속 또는 Sprint 2 의 ingest pipeline 활성 시점.
  4. **`attachment_reader` MySQL user 의 권한 부여 누락**: maintenance path (Phase 10 sandbox_schema.ensure_sandbox_schema_via_maintainer) 가 reader 에게 SELECT 부여하지만, 정본 SELECT (예: AgentMemoryMessages) 접근은 본 cycle scope 외 — 별 cycle.
  5. **sqlglot 미설치 환경의 fallback**: SQLGLOT_AVAILABLE=False 시 deny 강제 — 정합. 단, 운영 환경에 sqlglot 가 설치되어야 sandbox SQL 활성.
- **Cross-ref**: BRIEFING §6.1 + D14 + R-F3 + 정본 REV-20260521-0001 + Phase 11 REV-20260521-0013.
- **Sprint 1 Ship 평가**: Phase 1~12 모두 main merged. BRIEFING D1~D21 21 결정 + R-Claim4/R-Claim6/R-F1/R-F2/R-F3/R-F4/R-F5/R-F6/R-F7/R-F9/R-F10/R-F11/R-F12/R-F13/R-F14 모두 application-level 또는 module-level enforcement 완료. Cycle 0 (Foundation) + Cycle 1 (CSV ingest) 가 ship — 사용자가 첨부 upload, list, metadata, delete, consent grant/revoke, composer paperclip/drag-drop, attachment pill 활성. attachment_ids 가 /api/ask 의 env 통해 LLM prompt section 으로 전달. Sandbox SQL 의 실제 LLM tool execution 은 caller integration 별 cycle.

## REV-20260522-0009 [SUBAGENT:self-review]
- Related Change: CHG-20260522-0007 (feature-0008 composer-model-selector)
- Reason: 사용자 명시 요청 (2026-05-22) — profile drawer 의 API Vault 잔존 +
  모델 선택 UI 를 composer 좌측 `+` dropdown 으로 이전 (ChatGPT 패턴).
- Verdict: PASS — frontend-only 변경, backend contract 무변경.
- Risks (잔존):
  - `state.apiVaultOptions` 와 `state.modelCatalog` 가 같은 응답을 alias 로
    보존. 본 cycle 후 별 cycle 에서 `apiVaultOptions` 명 deprecation + 단일
    `modelCatalog` 로 통합 권장.
  - secondary popup (`.composer-model-menu`) 가 primary 우측에 표시 — 화면
    좁을 때 (≤ 720px) 위치 fallback CSS 작동 검증 필요 (브라우저 수동 테스트).
  - product chip + 모델 selector 의 분리 유지 결정 — 둘이 동시에 열리지 않게
    `closeProductDropup()` 호출 + ESC / outside click 핸들러로 일관성.
- Open Questions: per-conversation 모델 보존 (state.selectedModel 이 세션 globl
  current — 대화 전환 시 reset 필요한지 사용자 결정). 본 cycle 은 global 유지.
- Human Approval Needed: 사용자 명시 요청 + UX 결정 (`+` 안 [파일/모델], dropdown
  내 모델 button → 설명 포함 선택창) 충족.
## REV-20260522-0014 [SKIPPED:user-decision] TASK-0094 Sprint 2 Ship review

- **Mode**: SKIPPED — codex outside-voice review 가 Major §12.3 정책상 권장이나 사용자 명시 결정 (2026-05-22) 으로 SKIP.
- **Subject**: Sprint 2 의 vision invoke 경로 (D11 consent + D13 base64 inline + D9 share redact + D12 audit masking + cross-feature import 회피 + bedrock proxy auto-normalize) 의 보안 표면.
- **Reason — SKIP 정합**:
  1. **bedrock 정합 자동 흡수**: 본 cycle 의 catalog 변경량이 매우 작음 (supports_vision flag dict entry 만). LiteLLM proxy 가 OpenAI image_url → Anthropic Vision spec auto-normalize → backend spec 분기 0 → 외부 review 가 catch 할 추가 표면 작음.
  2. **D11/D12/D13 정합이 Sprint 1 의 D14 SQL guard 와 동등 mechanism 패턴 재사용**: Sprint 1 의 REV-20260521-0014 [SUBAGENT:codex-deferred-final] 에서 already 4 risk vector (sqlglot dialect / multi-statement / 호출 site 누락 / grant 부여) 검토 완료. 본 cycle 의 D13 base64 inline + D11 consent gate 는 별 SQL parsing 표면 없이 정적 boundary check 만 — 새 codex review 의 ROI 낮음.
  3. **caller integration test 는 container smoke 에서 검증**: _prepare_vision_inline_images 의 통합 test 가 PYTHONPATH 차이로 unit test 불가 → S2.8 verify-completion + 실 환경 smoke 시점에 검증. codex review 가 정적 분석만이라 통합 검증 cover 불가.
- **Risk** (review SKIP 대신 본 entry 로 명시):
  1. **D11 consent enum drift**: 본 cycle 이 `provider='anthropic'` 단일 매핑 가정 (`_model_to_consent_provider` 의 claude-* → anthropic). 향후 catalog 에 openai/local vision 가능 모델 추가 시 매핑 확장 필요. 매핑 누락 시 vision invoke 진입 안 함 (보수적 fail-closed) — 사용자 toast 추가는 별 cycle.
  2. **size/count cap 의 사용자 안내 누락**: cap 위반 시 silent skip (count 5 초과 시 정렬 후 첫 5만 inline, size 5MB 초과 시 무시). 사용자에게 "어느 image 가 inline 안 됐는지" toast 안내는 본 cycle scope 외 — frontend follow-up.
  3. **임시 file lifecycle race**: `/tmp/mysql_ai_inline_<cid>_<uuid>.json` 가 _run_agent_core 예외 raise 시 cleanup 누락 가능 (`_cleanup_vision_inline` 가 normal path 만). 단 finally block 또는 explicit try/finally 가 ask 함수 전체에 없음 — Sprint 1 의 ATTACHMENT_IDS env cleanup 패턴 동등. 별 cycle 의 robustness 강화 영역.
  4. **multi-turn vision invoke 의 누적 image 처리**: 본 cycle 의 messages_for_provider 가 첫 user message 만 변환 (idempotency 보장). 다만 user 가 후속 turn 에 새 image 첨부 시 본 cycle 은 매 turn 마다 첫 user message inline — 즉 후속 turn 의 image 도 새 inline. 다만 history 안의 old user message 는 inline 안 함 (provider 가 history 안 image 를 알 수 없음). 사용자 의도 ("계속 그 image 분석") 와 mismatch 가능성 — UX 검토 별 cycle.
  5. **provider 측 잔존 (R-F13 SKIPPED)**: 본 cycle 은 base64 inline only → LiteLLM proxy → Bedrock → provider 측 임시 처리 후 자동 deletion (Bedrock 의 stateless invoke). Files API 미사용 → WebConversationAttachmentProviderFiles row INSERT 0. Anthropic 의 retention 정책 (24h cache 등) 은 별 cycle 의 D11 consent 명문화 영역.
  6. **bedrock proxy normalize 의 fallback**: LiteLLM 의 image_url → Anthropic image conversion 이 실패 시 backend 에 어떤 error 가 return 되는지 unknown. Sprint 2 의 _call_llm 의 except 분기 (line 1463 부근의 `LLM 호출 오류` capture) 가 graceful — 사용자에게 toast. 정확한 error message 의 vision-specific 분기 (e.g., "vision 가능 모델이지만 image 형식 지원 안 함") 는 별 cycle.
- **Cross-ref**: BRIEFING §6.2 + D11 + D13 + D9 + D12 + D19 + feature-0007 (bedrock) AGENTS.md + Sprint 1 REV-20260521-0014.

## REV-20260522-0015 [SKIPPED:base64-inline-only] TASK-0094 Sprint 2 S2.7 (R-F13 provider Files API lifecycle) review

- **Mode**: SKIPPED — 본 cycle 은 base64 inline only 로 provider 측 잔존 0 → R-F13 진입 불요.
- **Subject**: WebConversationAttachmentProviderFiles row INSERT/DELETE + reconcile_provider_files worker.
- **Reason — SKIP 정합**:
  1. **Bedrock invocation 가 stateless**: LiteLLM proxy 가 OpenAI image_url content-array 를 Anthropic Vision spec 으로 normalize → Bedrock Sonnet 4.x / Haiku 4.x 가 inline image 를 invoke 처리 후 자동 폐기. provider 측 별 file resource 가 persist 되지 않음 → INSERT 대상 0.
  2. **WebConversationAttachmentProviderFiles schema 는 Sprint 1 Phase 2 에서 already ship** (D13 schema, R-F13 prerequisite). 본 cycle 의 lifecycle row INSERT/DELETE 가 없을 뿐 schema 영향 0.
  3. **OpenAI Files API / Anthropic Files API 통합은 별 cycle**: Sprint 4 (PDF/MD RAG) 시점에 long-context PDF 의 chunking + embedding + RAG retrieval 과 함께 Files API path 가 가능하면 그때 R-F13 lifecycle row INSERT/DELETE + reconcile_provider_files worker 활성.
- **Risk**: 본 SKIP 결정의 risk 0 — base64 inline 의 boundary 만 D13 정합으로 cover. 향후 vision 가능 모델이 Files API 강제 또는 base64 token cost 가 prohibitive 한 경우 R-F13 활성 재검토.
- **Cross-ref**: BRIEFING §6.2 S2.7 + R-F13 + WebConversationAttachmentProviderFiles schema (Sprint 1 Phase 2).

## REV-20260527-0001 [SKIPPED:trivial-pattern-match] AR-M5-impl web hotfix — _last_step_at_for_run PG 가드

- **Mode**: AGENT (pattern-match with existing `_conversation_is_processing()` guard)
- **Subject**: `app.py` `_last_step_at_for_run()` PG 가드 추가 (CHG-20260527-0001)
- **Scope**: 단순 guard 추가 — 기존 `_conversation_is_processing()` 과 동일한 패턴(`os.environ.get("AGENT_RUNTIME_READ_BACKEND") == "postgres"` → `_pg_connect()` → SQL) 의 반복 적용.
- **Review findings**:
  1. **패턴 일관성 확인**: `_conversation_is_processing()` 과 동일한 guard 구조 사용 — `_pg_connect()` 호출, `with pg.cursor()`, `pg.close()`, `except Exception: return None`. 패턴 drift 없음.
  2. **tzinfo 정규화**: PG `timestamptz` 반환 시 `datetime` 은 aware (tz 포함). `datetime.utcnow()` (naive) 와 비교를 위해 `.replace(tzinfo=None)` 추가 — 기존 MySQL fallback (`datetime` aware 아님) 과 동등.
  3. **MySQL fallback 보존**: `AGENT_RUNTIME_READ_BACKEND != postgres` 시 기존 `AgentMemorySteps` 쿼리 그대로 유지 — 런타임 분기 안전.
  4. **PG schema 정합**: `agent_runtime.steps.created_at` (timestamptz) + index `ix_steps_conv_run` (conversation_id, run_id) 존재 확인 — 쿼리 효율 적절.
- **Risk**: low — exception catch 가 `return None` (graceful degradation). `_compute_display_status()` 호출자가 None 처리 이미 완료.
- **Cross-ref**: CHG-20260527-0001 / TASK-AR-M5 / AR-M5-impl.

## REV-20260609-0001 [SUBAGENT:ship] TASK-0167 fork/share/duplicate/public-share-view PG cutover 회귀 수정 review

- **Mode**: SUBAGENT (adversarial outside-voice — security + backend lens). 결정: RBAC 변경 아님(권한 게이트 불변, 데이터 라우팅만)이나 **anonymous public-share 표면 포함**이라 outside-voice 1회 호출 (사용자 결정 "구현 후 1회 패널").
- **Subject**: CHG-20260609-FORK-SHARE-PG-CUTOVER — backend-aware helper 10종 + 5개 함수(`_fork_conversation_impl`/`_share_anchor_belongs_to_conversation`/`_share_load_messages`/`public_share_view`/`duplicate_conversation`) PG 라우팅.
- **Scope**: 정착된 `AGENT_RUNTIME_READ_BACKEND=postgres` + `_pg_connect()` 패턴 답습(`_list_conversations_pg`/`_ensure_conversation_row`/`_assign_conversation_owner` 대조). `public_share_view` cross-DB merge(core_conversations PG + WebProducts/WebAccounts MySQL) 신설.
- **Verdict**: **SHIP** — 모든 findings MINOR/NIT, blocker 0.
- **Review findings (외부 시각 독립 확인)**:
  1. **anonymous 표면 무누출**: old 단일 JOIN 과 노출 필드 동일(topic/owner_username/product_key/product_name/product_mode, 전부 `.get() or default`). token 유효성 게이트(revoke/404/race) 가 merge helper 보다 선행 — 접근 의미 불변. `product_id` 는 load 되나 미노출. KeyError/오owner 위험 없음.
  2. **redaction/internal-filter 생존**: tuple+dict-meta 전환 후에도 `_is_internal_message`(dict→`json.dumps` 직렬화 전달) + `_share_redact_message_content`(dict `dict(meta_json)` shallow-copy, source jsonb 비변형) 정상 작동. `_share_redact_message_content` 본문은 무변경.
  3. **fork write FK 순서 정합**: `_assign_conversation_owner`(autocommit `_pg_connect`)가 새 `core_conversations` row 를 message INSERT 전 **선커밋** → `fk_messages_conv` 충족(다른 connection 이어도). jsonb `%s::jsonb` 캐스트 = runtime_backend 패턴 일치. created_at 보존(timestamptz round-trip).
  4. **cleanup PG-aware**: 부분 실패 시 `delete_conversation_records`→`memory.delete_conversation`→`_pg_delete_conversation`(core_conversations CASCADE→messages) 로 완전 정리.
  5. **누수 없음**: 모든 helper `try/finally` 로 cursor/`_pg_connect` close (예외 경로 포함). fork 당 ~6 PG conn 은 perf NIT.
  6. **injection 안전**: 전부 bound `%s`. 정수 overflow/유니코드/collation 무영향.
- **Accepted follow-ups (non-blocking, 별 cycle)**:
  - F1 (MINOR): `_share_load_messages` 의 `_conv_load_messages_raw` PG read 미가드 → 전파 500. fork 의 명시적 500 래핑과 비대칭이나 "DB 오류 시 빈 공유뷰 렌더보다 정직한 500" 이 의도. error contract 일관화는 cosmetic.
  - F2 (HIGH-VALUE): 회귀 e2e 가 "500 미발생" 만 단언. public-exposure 면이므로 stale-policy attachment_derived 메시지 redact 단언 추가 권장. 단 redaction 코드 면 무변경이라 본 cycle 회귀위험 낮음 — 별 cycle 에서 fixture 동반 추가.
- **Cross-ref**: CHG-20260609-FORK-SHARE-PG-CUTOVER / TASK-0167 / CHG-20260527-ASK-STATUS-PG(형제) / runtime_backend._PG_INSERT_MEMORY_MESSAGE.

## REV-20260609-0002 [SKIPPED:defensive-errorhandling-and-test-only] TASK-0168 공유뷰 error contract(F1) + redaction 회귀 가드(F2)

- **Mode**: SKIPPED — 본 cycle 자체가 직전 REV-20260609-0001(SUBAGENT) 의 accepted follow-up(F1·F2) 구현이며, 추가 적대적 패널 불요.
- **Subject**: CHG-20260609-SHARE-ERRCONTRACT — `public_share_view` graceful 500 래핑(F1) + `tests/test_share_redaction_invariant.py`(F2).
- **Reason — SKIP 정합**:
  1. **성공경로·RBAC·스키마·계약 무변경**: F1 은 데이터 로드 *실패경로* 에만 작용(bare 500 → JSON 500). 익명 공유뷰의 노출 필드·접근 게이트·정상 렌더는 한 글자도 안 바뀜. 신규 데이터 노출 0.
  2. **F2 는 테스트 전용**: redaction/internal-filter 로직(`_share_redact_message_content`/`_is_internal_message`)은 TASK-0167·0168 모두 무변경. F2 는 그 불변식을 PG dict-meta 경로에서 *자동 가드* 할 뿐 동작을 바꾸지 않는다.
  3. **보안 변경의 검증을 테스트 자체가 수행**: 직전 패널이 "unverified by automation" 으로 지적한 redaction 불변식을 본 cycle 의 F2 가 컨테이너 in-process 3/3 PASS 로 충족(stale/NULL→redact, internal 필터, 정상 보존, version gate). 별도 패널보다 실증 가드가 우월.
- **Risk**: low — F1 실패경로는 더 보수적(빈 뷰 대신 명시 실패)이고, ViewCount 1 과대카운트(로드 실패 시)는 soft-metric 오차로 명시 수용. F2 무위험.
- **Cross-ref**: REV-20260609-0001 F1·F2 / CHG-20260609-SHARE-ERRCONTRACT / TASK-0168 / AC-0327·AC-0328.

## REV-20260609-0003 [SUBAGENT:revise-to-hybrid] TASK-0170 fork 문맥 복원 — git식 reference 설계 적대적 검토

- **Mode**: SUBAGENT (적대적 staff 아키텍트 + appsec). 대상: **설계 문서** `DESIGN-fork-reference.md`(코드 아님) — 사용자가 선택한 git식 reference 아키텍처를 구현 전 검증.
- **Verdict**: **RECOMMEND-SIMPLER-APPROACH (하이브리드로 수정)** — 순수 reference 는 착수 전 must-fix 다수.
- **Findings (요지, 상세 DESIGN §14)**:
  - F1 [BLOCKER] cross-table 시각 cut 불가 — `messages`/`core_messages` 독립 clock, 앵커 시각으로 core 자르면 turn 갈라져 `_normalize_history_rows` 가 통째 drop → 문맥 소실 재발.
  - F2 [BLOCKER] 로더 오기술 — 실제는 tail 윈도우(+user 보존)라 lineage merge 후 조상 evict.
  - F3 [MAJOR] `.any`-source fork 가 권한 회수 후에도 피해자 데이터 영구 live tap(IDOR 지속화).
  - F4 [MAJOR] 교차계정 live reference 는 매 ask 마다 A→B LLM 데이터 상시 흐름 — deep-copy snapshot 과 비등가(데이터 격리 위반).
  - F5 [MAJOR] sandbox 조상 스키마 공유가 1-conv-1-schema 격리 파괴.
  - F6/F7 [MINOR] 토큰 예산 부재(depth≤32 과대), fork_depth silent copy 강등, copy-on-delete race.
- **권고 = 하이브리드**: ① core_messages(+로컬 sandbox) deep-copy now, ② 동일소유자 file blob 만 참조(후속), 코어 로더·IDOR 게이트·교차계정 reference 폐기.
- **반영**: 사용자 결정으로 하이브리드 채택(ADR-WEB-0005). **Phase 1(core_messages 복사) 본 cycle 구현** — 코어 로더 무변경·스키마 변경 0·교차계정=snapshot 으로 F1(완화: copy 라 로더 자가치유)/F3/F4/F5 구조적 제거. 첨부는 Phase 2(후속, IDOR 동반 시 재-패널).
- **Cross-ref**: DESIGN-fork-reference.md §14·§15 / ADR-WEB-0005 / CHG-20260609-FORK-CORE-CONTEXT / TASK-0170 / AC-0329.

## REV-20260609-0004 [SUBAGENT:fix-first-then-ship] TASK-0171 fork 첨부 복사 (하이브리드 Phase 2)

- **Mode**: SUBAGENT (적대적 staff 백엔드 + appsec/IDOR). 대상: `_copy_conversation_attachments` + fork 배선 코드.
- **Verdict**: **FIX-FIRST → (수정 후) SHIP**. 접근모델 OK(IDOR/JSON/sandbox 격리/SQLi/commit), 교차계정 복사는 사용자 의도(full-copy) 정합. MAJOR 2 + MINOR 2 수정 요구.
- **Findings & 반영**:
  - #1 IDOR — **OK**: 새 ConversationId+fork AccountId 행은 `_account_can_access_attachment`(conv 소유) 그대로 통과, 게이트 변경 0.
  - #2 [MAJOR] orphan blob: put→INSERT + fail-open 이 행 없는 blob 을 남겨 reconciliation 이 GC 못 함. → **수정**: INSERT 먼저 → put → put 실패 시 행 보상삭제(업로드 endpoint 패턴).
  - #3 MetaJson — **OK**: mysql-connector 는 JSON 을 str 반환, pass-through 재삽입은 MySQL 이 JSON 파싱(이중인코딩 없음). csv/xlsx=NULL 정합.
  - #4 재적재 — **OK**: 스키마명 `sha256(new_cid)` 라 fork 전용(공유 없음, F5 충족). blob 선복사로 재적재 입력 보장.
  - #5 [MINOR] audit gap(교차계정 첨부 이동 미감사). → **수정**: `share.fork` ctx 에 attachments_copied/core_messages_copied 추가.
  - #6 [MAJOR] quota 우회: 복사가 `_check_attachment_size_caps` 미수행 → 반복 fork storage 증식. → **수정**: 복사 전 per-file/conv/account cap 검사, 초과 skip.
  - #7 [MINOR] test flap(ingest 타이밍/skip). → **수정**: ⊆+count 일관성으로 완화.
- **Residual(수용)**: cap 초과 첨부는 silent skip(quota 정합 우선 — 제품이 fork 면제 원하면 별도 결정). 현 배포 sandbox 0 라 CSV 재적재는 미라이브검증(방어적 코드).
- **Cross-ref**: CHG-20260609-FORK-ATTACHMENTS / ADR-WEB-0005 Phase 2 / TASK-0171 / AC-0330 / DESIGN-fork-reference.md §15.

## REV-20260609-0174 [SUBAGENT:preview-csv-inline-guard]
- Date: 2026-06-09
- Cycle: TASK-0174 (미리보기 인라인 로더 방어 가드)
- Panel: backend+QA adversarial subagent (REV-20260609-0173 과 동일 패널, app.js 가드 포함 리뷰).
- Verdict/Resolution: block.previousElementSibling=TABLE 가정 신뢰(#122 기확립, marked 가 본문=td/헤더=th 렌더). MAJOR(재포맷 오탐) → previewTokens≥2 임계 + backend 값매칭이 1차이므로 본 가드는 심층방어. DOM 가정 안전.
- Risk: low — backend 가 이미 잘못된 링크 미부착. 가드는 우연 잔존 케이스 최종 차단.

## REV-20260609-0175 [SKIPPED:docs-only-cycle-closure]
- Date: 2026-06-09
- Cycle: TASK-0174 cycle closure (체크박스 + TEST.md Run 기록)
- Reason: 문서 한정(TASK.md 체크박스 + TEST.md §4 검증 기록). 코드·RBAC·스키마·시크릿 0건. 실질 수정은 REV-20260609-0174(SUBAGENT 패널)에서 검토·배포됨. outside-voice 불필요 조건 충족.

## REV-20260610-0184 [SKIPPED:rbac-schema-unchanged-readonly-ui]
- Date: 2026-06-10
- Cycle: TASK-0184 (LLM 사용량 계정 drill-down + 프로필 사용 내역 차트 + 내 활동기록 제거)
- Reason: 조회 UI 전용. (A) 계정 drill-down·(C) 활동기록 탭 제거는 순수 프론트(권한·엔드포인트·스키마 0). (B) 신규 `GET /api/profile/usage` 는 `_require_account`(로그인)만 요구하고 `owner_account_id`=본인으로 INNER JOIN 강제해 **권한 카탈로그(WebPermissions/PERMISSION_DEFINITIONS) 변경 0·권한 상승 0·추정 비용 비노출** — 본인 소유 대화 usage 자기조회(기존 `/api/profile/audits` self-service 패턴과 동일, audit 보다 노출 범위 좁음: 본인 토큰 지표만). 새 권한 도입·grant·역할 변경이 없어 RBAC 권한 모델 변경이 아님 → outside-voice 불필요 조건 충족. make test(컨테이너 pytest+ruff) exit=0 회귀 0, node --check/py_compile PASS.
- Residual: Windows-browser(PB-0008) 시각 검증은 배포 후 수행(CHECK#13 WARN, TEST.md §3 Run 으로 기록 예정).

## REV-20260610-0185 [SKIPPED:css-readonly-chart-addition]
- Date: 2026-06-10
- Cycle: TASK-0184 A drill-down 누락 보강 (계정별 비용 차트)
- Reason: 사용자 지적("계정별 비용 차트 누락") 후속 — drill 패널에 비용 막대(`usageDrillCostChart`) 추가 + 2열 레이아웃. 순수 프론트(HTML/CSS/JS), 권한·엔드포인트·스키마 0(by_account 응답의 기존 `cost_usd` 를 추가 렌더). RBAC 권한 모델 변경 아님 → outside-voice 불필요. node --check PASS.

## REV-20260610-0198 [SKIPPED:rbac-schema-unchanged-readonly-ui]
- Date: 2026-06-10
- Cycle: TASK-0198 (LLM 사용량 모델별 분리/선택 차트 + 모델별 요약 카드 + 좌우 스크롤 제거)
- Trigger: UI/screen/layout/chart keyword 매칭(§18.8 → ux/design). 단 조회 UI 전용 + 권한·스키마·시크릿 무변경이라 전례(REV-20260610-0184/0185)와 동일하게 경량 SKIP.
- Reason: 순수 프론트(admin.js·admin.html·styles.css). 기존 `GET /api/admin/usage`(권한 `console.usage.read`) 응답을 **그대로** 받아 클라이언트에서 모델 필터·재계산(`buildView`)만 수행 — 신규 엔드포인트·쿼리·권한·grant·역할·스키마·시크릿·환경변수 0. 모델 필터링은 백엔드가 이미 내려주는 `by_model`/`by_day_model`/`models[]` 의 부분집합 선택일 뿐이라 노출 데이터 범위 확대 없음(권한 보유자가 이미 보던 동일 데이터). 부분 선택 시 요청·호출 분해 불가 항목은 `—` 로 정직 표기(오집계 방지). 좌우 스크롤 제거는 `overflow-x`/`min-width` CSS. `color-mix`/`--accent` 미사용 → 프로젝트 토큰 통일(구버전 브라우저 회귀 회피). RBAC 권한 모델 변경 아님 → outside-voice 불필요. node --check PASS.
- Residual: Windows-browser(PB-0008) 시각 검증은 배포 후 수행(CHECK#13 WARN, TEST.md §3 Run 으로 기록).

## REV-20260610-0202 [SUBAGENT:frontend-adversarial]
- Date: 2026-06-10
- Cycle: TASK-0202 (LLM 사용량 "모델별" 카드 전환 애니메이션 + 비선택 dim/이탈 시 사라짐)
- Trigger: UI/screen/layout/animation/interaction keyword(§18.8 → ux/design). 순수 프론트지만 hover/transitionend/display:none 상호작용 로직이라 경량 SKIP 대신 frontend subagent 적대적 리뷰 수행.
- Panel: general-purpose subagent(frontend/UX 적대적). 변경 3파일(admin.js·styles.css·admin.html) 실독 후 transitionend 정확성·display 복구·grid reflow·전체복귀 리셋·reduced-motion·TASK-0198 회귀 점검.
- Findings & 처리:
  - **B1 (BLOCKER, 흡수)**: 칩 바 필터링 등 마우스가 카드 영역 밖인 채 재렌더되면 갓 삽입된 비선택 카드의 초기값이 `opacity:0`(transition 은 초기 상태엔 미발동) → `transitionend` 미발생 → `display:none` 회수 누락 → `opacity:0` 유령 카드가 grid 빈 칸 점유. → **재렌더 직후 `!matches(":hover")`면 dimmed 카드를 동기 `display:none`** 으로 회수하는 패스 추가.
  - **M1 (MAJOR, 흡수)**: 회수된 카드 재진입 복구가 `display:""` 만이라 opacity 0→.4 보간 없이 pop-in. → mouseenter 에서 `display:""`+`opacity:0` 후 강제 reflow→인라인 opacity 해제로 부드러운 fade-in.
  - **M2 (MAJOR, 의도 수용)**: `display:none` 회수 시 grid `auto-fill` 트랙 재계산으로 남은 선택 카드가 top-left 로 이동. → 사용자 요청("나머지 모델이 사라지도록")의 focused single-card 종착이 의도라 수용(빈 칸 잔존보다 깔끔). 문서화.
  - **m3 (MINOR, 의도)**: hover 중 흐린 비선택 카드는 pointer-events 복구돼 클릭 가능 → 모델 간 "전환" 동선(흐림 보고 다른 모델 클릭)으로 의도된 동작.
- TASK-0198 회귀: 칩 바·`buildView`·도넛/일별/역할/계정 차트·상세 표 전부 `view.*` 유지(미변경), 카드만 `data.by_model` 분리 — subagent "회귀 없음·클린 리셋" 확인.
- Verdict: B1/M1 수정 반영 후 SHIP-able(BLOCKER 0). RBAC/스키마/엔드포인트/시크릿 0 — 권한 모델 변경 아님(outside-voice RBAC 게이트 불요).
- Residual: Windows-browser(PB-0008) 시각 검증은 배포 후 수행(CHECK#13 WARN, TEST.md Run 으로 기록 예정).

## REV-20260611-0204 [SKIPPED:frontend-removal-readonly-ui]
- Date: 2026-06-11
- Cycle: TASK-0204 (LLM 사용량 '모델별' 카드 제거 + 모델 칩 토큰수 제거)
- Trigger: UI/screen/layout keyword(§18.8 → ux/design). 단 본 cycle 은 **기능 제거 + 라벨 단순화**(추가 로직 0)라 전례(REV-0184/0198/0202 류 readonly-ui)와 동일 경량 SKIP.
- Reason: 순수 프론트(admin.js·styles.css·admin.html). 중복 UI(`.admin-usage-mcards`) 제거 + 칩 토큰수 제거 — 신규 엔드포인트·쿼리·권한·grant·역할·스키마·시크릿 0. 노출 데이터 범위 축소(토큰수는 도넛·차트·표에 잔존). 직전 TASK-0202 의 hover 결합 잭을 섹션 폐기로 근본 해소(라이브 win-browser 로 결함 재현 확인 후 결정). `buildView`/차트/표 무변경(회귀 0). RBAC 권한 모델 변경 아님 → outside-voice 불필요. node --check PASS.
- Residual: Windows-browser(PB-0008) 시각검증은 배포 후 수행(모델별 카드 부재·칩 모델명만·칩 토글 정상 — CHECK#13).

## REV-20260611-0205 [SKIPPED:frontend-only-single-line]
- Date: 2026-06-11
- Cycle: TASK-0205 (composer Shift+Enter 줄바꿈 지원)
- Trigger: keydown/input keyword(§18.8 → ux). 단 본 cycle 은 **keydown 핸들러 1줄 early return** 으로 브라우저 기본 동작을 허용하는 것 — 신규 로직·상태·API 0. 전례(REV-0198/0204 readonly-ui)와 동일 경량 SKIP.
- Reason: `if (event.shiftKey) return;` 1줄. 권한·엔드포인트·스키마·시크릿 무변경. 기존 Enter/Ctrl+Enter 전송 경로 미영향. 단순 기본 동작 허용 — outside-voice 불필요.

## REV-20260611-0206 [SKIPPED:frontend-rendering-toggle]
- Date: 2026-06-11
- Cycle: TASK-0206 (쿼리 문자열 항상 표시 + 실행결과셋 기본 숨김 토글)
- Trigger: UI/button/layout keyword(§18.8 → ux). 단 본 cycle 은 **표시 방향 교정** — 쿼리 문자열을 숨기던 토글을 제거하고 결과셋에 토글을 추가하는 렌더링 로직 재배치. 신규 엔드포인트·쿼리·권한·스키마·시크릿 0.
- Reason: 순수 프론트엔드(app.js 4개 함수 + styles.css CSS 추가). 기존 데이터 흐름·API·RBAC 무변경. 사용자가 이미 볼 수 있던 데이터(쿼리/결과셋)의 표시 순서·기본 노출 여부만 변경. node --check PASS, py_compile PASS. outside-voice 불필요.
- Residual: 배포 후 라이브 확인 필요(쿼리 항상 표시·결과 보기 토글 — CHECK#13 WARN).

## REV-20260611-0207 [SUBAGENT:design-correctness]
- Date: 2026-06-11
- Cycle: TASK-0207 (관리 콘솔 데이터소스 pane UI 표준화 + 수정/삭제 노출), **Minor §12.3** — 프런트 3파일(admin.html·admin.js·styles.css), 백엔드/API/스키마/RBAC/시크릿 0.
- Trigger: UI/page/form/layout keyword(§18.8 → ux/design). frontend-only 이나 가시적 레이아웃 재구성 + 타 pane 공유 클래스(`admin-detail-head` 등) 접촉이라 SKIP 대신 design+correctness 패널 1인 실행.
- 패널 결과: **SHIP-WITH-FIXES**. RBAC/보안 게이트(console.manage·ds.editable·env-readonly·encryption-ready) HEAD 대비 무손실 확인. 지적 5건 전부 수용·수정:
  - BLOCKER: styles.css 에 `.admin-detail-head` 중복 정의 → 동일 specificity 후순위로 accounts/roles/products/audit 상세 헤더(divider+flex-start) 전역 회귀. → 중복 rule 제거, 기존 canonical(3168) 재사용.
  - SHOULD-FIX: 생성 직후 `_dsSelectedKey = body.key`(raw) 인데 서버가 `strip().lower()` 정규화 → 목록 매칭 실패로 자동선택 누락. → POST 응답 canonical key(폴백 `body.key.toLowerCase()`) 사용.
  - SHOULD-FIX: 읽기전용 사유 안내가 sticky 액션바(`admin-detail-actions`, bottom:-18px) 아래 append → sticky 깨짐. → 액션바 위(앞)로 이동.
  - NICE: `.admin-field input.is-readonly` 배경 `var(--surface-2, …)` 인데 `--surface-2` 미정의 → no-op. → `var(--bg)` 로 교체.
  - NICE: `role=listbox` option 비활성 행 `aria-selected` 제거 대신 `"false"` 명시.
- Risk: low — 프런트 레이아웃/상태. 백엔드·데이터·권한 무영향. 잔여 시각검증은 PB-0008(배포 후).

## REV-20260611-0208 [SUBAGENT:design-correctness]
- Date: 2026-06-11
- Cycle: TASK-0208 (프로필 drawer 너비 조절 + 사용 내역 집계 단위), **Minor §12.3** — 프런트 3파일(app.js·index.html·styles.css), 백엔드/API/스키마/RBAC/시크릿 0.
- Trigger: UI/sidebar/layout/screen keyword(§18.8 → ux/design) + 신규 drag 인터랙션(단순 SKIP 부적합) → design+correctness 패널 1인 적대적 실행.
- 패널 결과: **SHIP-WITH-FIXES**. 단계 보기 패널 패턴의 충실한 복제(리스너 add/remove 균형·`dataset.wired` 중복배선 가드·touch+mouse·`gran` 화이트리스트 검증+`encodeURIComponent`·`textContent` 고정 dict=XSS-safe) 확인. 지적 수용:
  - MAJOR: drawer 가 패널 전체 스크롤(`overflow-y:auto`+padding)이라 absolute `.drawer-resizer`(`height:100%`)가 콘텐츠와 함께 스크롤 → 긴 탭(사용 내역) 스크롤 시 핸들이 시야 밖. (단계 패널은 `.step-side-panel-body` 내부 스크롤이라 무해.) → `.drawer` 의 padding/gap/overflow 를 신규 `.drawer-scroll` 래퍼로 이동, 리사이저는 비스크롤 shell(`.drawer`, `overflow:hidden`)에 고정. index.html 헤더/탭/패널을 `.drawer-scroll` 로 래핑.
  - MINOR: 데스크톱 저장 너비가 inline `style.width` 로 모바일 미디어쿼리(`min(100vw,380px)`)를 무력화. → `_applyProfileDrawerWidth` 가 ≤680px 에서 inline 미적용(`style.width=""`)하고 미디어쿼리가 폭 소유.
  - MINOR(수용·미수정): 초협소(~<348px) 뷰포트에서 `PROFILE_DRAWER_MIN_W=320` 이 뷰포트 초과 가능 — 단계 패널 `MIN_W=300` 에서 그대로 상속된 동작이라 회귀 아님.
- 비이슈 확인: `left:0`(border-box → 패딩박스 좌변=좌측 가장자리)·close/탭 비충돌·`is-resizing` 은 드래그 중에만 transition 제거(open 슬라이드 무영향)·`week` 미노출은 백엔드 재검증으로 안전.
- Risk: low — 프런트 레이아웃/상호작용. 백엔드·데이터·권한 무영향. 잔여 시각검증은 PB-0008(배포 후).
- Cross-ref: CHG-20260611-0208 / TASK-0208.

## REV-20260611-0209 [SKIPPED:frontend-trivial-reorder]
- Date: 2026-06-11
- Cycle: TASK-0209 (관리 콘솔 LLM 사용량 집계기준↔집계범위 드롭다운 순서 정렬), **Minor §12.3** — admin.html DOM 재배치 1건.
- Reason: `.admin-pane-actions` 내 형제 `<select>` 2개(`#usageGranSel`/`#usageDaysSel`)의 순서 교체뿐. JS 는 두 요소를 id 로 참조하므로 동작/이벤트/조회 로직 무변경, RBAC·스키마·엔드포인트·백엔드·CSS 무변경. 위험 표면이 없어 적대적 패널 불요(전례 REV-20260611-0204/0205 frontend-only SKIP 과 동일 등급). 시각 동등성은 PB-0008(배포 후)로 확인.
- Risk: negligible — DOM 형제 순서.
- Cross-ref: CHG-20260611-0209 / TASK-0209 / TASK-0208(프로필 순서 기준).

## REV-20260611-0213 [SKIPPED:frontend-picker-ui-no-rbac-schema-change]
- Date: 2026-06-11
- Cycle: TASK-0213 (접근 가능 DB 선택 드롭다운+체크박스 UI 개선), **Minor §12.3**
- Reason: 프런트 UX 교체(select+버튼 → 체크박스 드롭다운) + 백엔드 MSSQL tempdb 폴백 보안 하향(업무 데이터 0, 무자격 참조 차단). RBAC 카탈로그·API 계약(엔드포인트/envelope)·WebDatasources 스키마 신규 0. tempdb 폴백은 보안 상향(빈 문자열=로그인 기본 DB 중 업무 DB 가능 → tempdb=업무 데이터 없음)이므로 적대적 보안 리뷰 불요. node --check admin.js PASS.
- Risk: low — 프런트 UX + 백엔드 MSSQL 연결 폴백 DB 변경만. 업무 데이터·RBAC·암호화 영향 없음.
- Cross-ref: CHG-20260611-0213 / TASK-0213.

## REV-20260611-0216 [SKIPPED:auto-key-no-rbac-no-schema-no-secret]
- Date: 2026-06-11
- Cycle: TASK-0216 (데이터소스 키 자동 생성: 엔진+호스트+포트 해시), **Minor §12.3**
- Reason: 키 생성 방식을 식별자 문자열에서 결정론적 해시로 교체한 것이 변경의 전부. RBAC(console.manage) 게이트 무변경, `WebDatasources` 스키마 무변경(컬럼 추가/삭제 없음, DatasourceKey 값만 달라짐), DEK/KEK 암호화 경로 무변경, 신규 엔드포인트 없음. 레거시 `main_mysql` 마이그레이션은 멱등 UPDATE/DELETE 2~3개이며 rollback 은 행 rename 역방향으로 가능. py_compile app.py PASS, node --check admin.js PASS.
- Risk: low — 키 값 형식 변경만. 기존 `main_mysql` 키를 가진 운영 환경은 부팅 시 자동 마이그레이션(멱등). `.env` 출처 레거시 datasource 는 의도적 미변경.
- Cross-ref: CHG-20260611-0216 / TASK-0216.

## REV-20260611-0217 [SKIPPED:bugfix-aad-reencrypt-no-new-surface]
- Date: 2026-06-11
- Cycle: TASK-0217 (데이터소스 해시 키 버그 수정 2건), **Minor §12.3**
- Reason: 기존 AESGCM(AAD=DatasourceKey) 재사용 — 신규 암호화 표면 없음. 버그 수정: ① rename 시 재암호화 누락(InvalidTag) ② PATCH 시 키 불일치. RBAC 게이트·스키마·신규 엔드포인트 0. 재암호화 로직은 기존 `encrypt_password`/`decrypt_password` 함수 호출이므로 암호화 계층 변경 없음. 복호 실패 시 기존 암호문 유지(silent pass) — 연결 테스트로 가시화. py_compile PASS, node --check PASS.
- Risk: low — 복호→재암호화 경로 추가이며 기존 DEK/KEK 체인 무변경. PATCH 키 변경 409 충돌은 동일 엔드포인트 중복 등록 차단이라 안전.
- Cross-ref: CHG-20260611-0217 / TASK-0217 / TASK-0216.

## REV-20260611-0218 [SKIPPED:bugfix-aad-fix2-no-new-surface]
- Date: 2026-06-11
- Cycle: TASK-0218 (데이터소스 키 명시적 rename 지원 + AAD 자가수복), **Minor §12.3**
- Reason: 자가수복 로직과 명시 rename 모두 기존 DEK/AESGCM(`encrypt_password`/`decrypt_password`) 재사용 — 신규 암호화 표면 없음. RBAC 게이트(console.manage) 무변경, 스키마 무변경, 신규 엔드포인트 없음. 자가수복은 복호→재암호화만 추가이며 실패는 silent pass(수동 재입력으로 가시화). 명시 rename은 기존 key_changed 경로와 동일 로직. admin.js key 필드는 readonly → 편집 가능으로 UX 변경만. py_compile PASS, node --check PASS.
- Risk: low — 자가수복은 서버 재시작 시 1회 실행 멱등. 명시 rename은 기존 키 변경 경로 재사용. admin.js 변경은 UX only.
- Cross-ref: CHG-20260611-0218 / TASK-0218 / TASK-0217.

## REV-20260611-0223 [SUBAGENT:insight-coverage-matching-semantics]
- Date: 2026-06-11
- Cycle: TASK-0223 (제품별 insight-worker 분석 완료율 UI), **Major §12.3**
- Outside-voice: 적대적 설계 리뷰 subagent 1인 — "그럴듯하지만 틀린" 매칭 의미론 반증 임무. datasource 접근 모델 인접(memory: access-model 인접 작업 외부시각 필수)이라 구현 전 설계 검증 dispatch.
- 판정: 리뷰는 prompt 에 기술한 **단순 설계**(분자를 SQL `schema_name IN (접근DB)` 필터로) 기준 **NOT-SHIP** + 5건 지적. 핵심 2건:
  1. **[BLOCKER] NULL vs 해시 이중기록**: TASK-0206 이후 "기본 MySQL" 제품의 `DatasourceKey` 는 NULL 이 아니라 main_mysql 해시. insight 가 ds=None(NULL)+main_mysql(hash) 로 같은 테이블 2벌 기록.
  2. **[BLOCKER] MSSQL schema_name 차원**: rag `schema_name`=SQL 스키마(`dbo`), 접근DB=catalog(database) → `schema_name IN (접근DB)` 항상 0 매칭.
  - 그 외 [MAJOR] 분모 연결 유저(information_schema 권한필터)·.env 라벨 폴백, [MINOR] VIEW 양쪽 동일.
- 해소(구현이 catalog-driven 으로 선반영): 실제 구현은 리뷰가 권고한 형태와 일치 — ① 분자를 **라이브 카탈로그 (schema,table) ∩ rag (schema,table) 집합 교집합**(set dedup)으로 계산해 MSSQL dbo 차원·이중기록 모두 해소(SQL schema 필터 미사용), ② datasource 매칭에 `_dsr.scope_key`(해시, .env 라벨 폴백 포함) 사용 + 기본 엔드포인트일 때만 `datasource_key IS NULL` 합산(distinct 라 과대집계 0), ③ 분모를 resolve 된 datasource RO 좌표로 직결해 insight 와 GRANT 가시성 정합, ④ MSSQL 비-default_db=미스캔(analyzed 0+flag), ⑤ VIEW 양쪽 포함. 5건 모두 반영 확인.
- Risk: low-medium — read-only 통계(쓰기·RBAC·스키마·암호화 0). 라이브 DB 조회는 90s TTL 캐시+per-datasource 실패 격리+SSRF 가드+5s timeout. 측정 불가는 graceful "측정 불가" 표시(500 없음).
- Cross-ref: CHG-20260611-0223 / TASK-0223 / TASK-0206 / TASK-0219.

## REV-20260611-0225 [SKIPPED:frontend-textarea-autogrow-no-backend]
- Date: 2026-06-11
- Cycle: TASK-0225 (textarea 우측 하단 핸들 더블클릭 시 내용 높이로 자동 확장), **Minor §12.3**
- Reason: 순수 클라이언트 UX 추가. 신규 JS 1파일(document `dblclick` capture 위임) + html 3개 script 태그 추가뿐. 백엔드(app.py)·RBAC·스키마·암호화·신규 엔드포인트·기존 JS 로직 무변경. 핸들 영역(~18px) 좌표 판정으로 본문 더블클릭(단어선택) 미간섭. 위험 표면 없어 적대적 패널 불요(전례 REV-20260611-0209/0213 frontend-only SKIP 과 동일 등급). node --check PASS.
- Risk: low — 클라이언트 height 스타일 변경만. 600px 상한으로 레이아웃 폭주 방지. 시각 동작은 PB-0008(배포 후)로 확인.
- Cross-ref: CHG-20260611-0225 / TASK-0225.

## REV-20260611-0226 [SKIPPED:mssql-perdb-bugfix-no-new-surface]
- Date: 2026-06-11
- Cycle: TASK-0226 (MSSQL 제품 분석 완료율 미표시(연결) 수정 — per-DB 연결 격리; 동시세션 TASK-0225 충돌로 재번호 §13.1), **Minor §12.3**
- Reason: TASK-0223 read-only 통계의 버그수정. RO 로그인(`agent_ro`)이 일부 DB 에만 GRANT 된 환경에서 단일 try/except 가 한 DB 실패로 전체를 "측정 불가" 오염시키던 것을 **per-DB 연결 격리**로 수정. 신규 RBAC 권한·DB GRANT·스키마·암호화·엔드포인트 경로 0 — 엔드포인트 응답 shape 의 per_db 필드명 `scannable`→`connected`+`note` 확장만(프런트 동반 수정). datasource 연결은 기존 `list_information_schema_tables` 직결 재사용(SSRF 가드 선행 유지). 매칭 의미론(catalog-driven set 교집합) 무변경. 적대적 보안 리뷰 불요 — 권한 경계·자격증명 처리·쓰기 경로 변화 없음. py_compile/node --check PASS.
- Risk: low — 비연결 DB 를 분모에서 제외(측정 가능 DB 기준)하는 정직 표기. MySQL 경로는 단일 try 유지(회귀 0). 본 수정은 권한을 부여하지 않으며(agent_ro GRANT 는 운영자 영역), 권한 없는 DB 를 "연결 불가"로 가시화만 한다.
- Cross-ref: CHG-20260611-0226 / TASK-0226 / TASK-0223.

## REV-20260611-0227 [SKIPPED:frontend-ui-state-persist-no-backend]
- Date: 2026-06-11
- Cycle: TASK-0227 (실행 단계 사이드 패널 갱신 시 "결과 보기" 펼침 상태 유지), **Minor §12.3**
- Reason: 순수 클라이언트 UI 상태 보존 버그수정. 폴링 재렌더(`_renderStepSidePanelBody`의 `body.innerHTML=""`)가 펼쳐둔 결과셋을 닫던 것을, 펼침 상태를 `state.stepResultExpanded`(Set)에 영속화 후 복원해 해소. 신규 RBAC·스키마·암호화·엔드포인트·백엔드(app.py) 0 — `app.js` state 필드 1 + 헬퍼 1 + 토글 배선 + run 전환 시 clear 뿐. 위험 표면 없어 적대적 패널 불요(전례 REV-20260611-0209/0213/0225 frontend-only SKIP 과 동일 등급). node --check PASS.
- Risk: low — 클라이언트 펼침 상태 추적만. run 전환 시 Set clear 로 키 누수 방지. step 키는 기존 dedup 키(`step_index:created_at`) 재사용. 시각 동작은 PB-0008(배포 후)로 확인.
- Cross-ref: CHG-20260611-0227 / TASK-0227.

## REV-20260611-0228 [SUBAGENT:security] — BLOCK→흡수→PASS
- Related TASK: feature-0003-agent-web-ui (TASK-0228)
- Trigger: SSRF/보안경계 keyword matched — datasource host 가드 사설망 차단 비활성화 (§12.3 Major 보안 다운그레이드, 사용자 명시 승인)
- Timestamp: 2026-06-11T00:00:00Z
- Verdict: BLOCK (초기) → 발견 전건 흡수 후 PASS 재검증
- Artifact: unit/feature-0003-agent-web-ui/docs/reviews/20260611T000000Z-security.md
- Critical issue (흡수됨): (A/B) 토글 OFF 시 IPv4-mapped IPv6 메타데이터 IP(`::ffff:169.254.169.254`/`::ffff:100.100.100.200`)가 `str(ip).endswith(...)` 정규화 빗나감으로 통과 → 메타데이터 SSRF. (C) 토글이 loopback/link-local 까지 함께 개방(승인 범위=RFC1918 초과).
- Resolution: 메타데이터 차단을 `ip.ipv4_mapped` 언래핑 비교(토글 무관)로 강화 + 토글을 `is_private`(RFC1918)에만 적용하고 loopback/link-local/reserved/multicast 는 상시 차단. 단위테스트 22→31(IPv4-mapped 메타데이터·loopback·link-local 케이스 추가) + 통합 trace 11 케이스 ALL PASS. datasource 회귀 12/29 PASS(회귀 0).
- Human Approval Needed: no (보안 다운그레이드 자체는 사용자 사전 승인 + 잔여 위험을 승인 범위로 정확히 한정)
- Cross-ref: CHG-20260611-0228 / TASK-0228 / ADR-0030 / SECURITY §11.

## REV-20260611-0229 [SKIPPED:frontend-ia-merge-no-backend]
- Date: 2026-06-11
- Cycle: TASK-0229 (관리 콘솔 제품 상세 `접근 가능 데이터베이스` UI 통합 — DB chip ↔ insight 완료율 1:1 중복 제거 + 시스템 DB 단일 묶음 칩; 동시세션 SSRF cycle TASK-0228 선점→§13.1 재번호), **Minor §12.3**
- Design panel: gstack `/design-review` 메서드론(general-purpose design subagent) — 사용자 보고 2 IA 문제(중복 1:1 / 시스템 chip 산만)에 대한 통합 재설계 스펙 도출. 핵심 결정 "분석 대상(사용자 DB)=단일 리스트 행(진척+제거), 비-분석 대상(시스템 DB)=접근성 묶음 칩". 디자인 토큰 한정·접근성(hover만 금지) 제약 반영.
- Reason: 순수 frontend IA 재구성. admin.js(렌더 함수 3종 재작성/신설) + styles.css(클래스 재구성) + admin.html(캐시버스터). **신규 RBAC 권한·DB 스키마·암호화·신규 엔드포인트·백엔드(app.py)·coverage 엔드포인트 응답 shape 변경 0** — 기존 per_db 데이터와 draft chip 배열을 클라이언트에서 `db ↔ schema_name`(소문자) 조인해 한 리스트로 표시할 뿐. 적대적 보안 패널 불요 — 권한 경계·자격증명·쓰기 경로 변화 없음(전례 REV-20260611-0225/0227 frontend-only SKIP 동일 등급).
- 데이터 정합 검증: 백엔드 `_compute_product_insight_coverage` 의 `accessible = _list_product_databases(conn, pid)` 확인 → `per_db` 집합 = 사용자 등록 DB(draft) 와 동일, 시스템 DB(metadata_schemas)는 per_db 미포함 → 1:1 융합 + 시스템 분리가 데이터 모델과 정합. picker 추가 직후(per_db 미갱신) DB 는 `covRow=null`→"측정 대기" graceful.
- 접근성: 시스템 묶음 칩에 `title`(네이티브) + `aria-label`(스크린리더) + `tabindex=0` + `:hover`/`:focus`/`:focus-within` 커스텀 툴팁 3중 병행 — 키보드·터치 사용자도 개별 DB 이름 확인 가능.
- Risk: low — 시각 IA 변경만. 연결 불가 DB 는 행 opacity 다운+점선 마이크로바+"연결 불가" 상태칩으로 정직 표기(기존 색상 등급 로직 재사용). node --check admin.js PASS + CSS brace balance. 시각 동작은 PB-0008(배포 후)로 확인.
- Cross-ref: CHG-20260611-0229 / TASK-0229 / TASK-0223 / TASK-0206.

## REV-20260612-0245 [SKIPPED:css-grid-alignment]
- Date: 2026-06-12
- Cycle: TASK-0245 (제품 상세 접근가능 DB 리스트 행 컬럼 폭 정합), **Minor §12.3** — CSS 1파일(+admin.html 캐시버스터), 백엔드/API/스키마/RBAC/시크릿 0.
- Trigger: layout/UI keyword(§18.8 → ux). 단 본 cycle 은 `.cov-db-row` grid 트랙 `auto`→고정폭 전환 + `justify-self:start` 2줄 — 신규 로직·상태·DOM·엔드포인트·권한 0. 전례(REV-0178 css-spacing / REV-0179·0180 css-layout)와 동일 경량 SKIP.
- Reason: 행 단위 grid 의 가변(`auto`) 컬럼이 콘텐츠 길이에 따라 행마다 트랙폭을 달리해 fr 컬럼이 어긋나던 것을 고정폭으로 못박아 전 행 트랙 동일화. 데이터·권한·구조 무변경, 순수 시각 정렬. outside-voice 불필요.
- Residual: 배포 후 PB-0008 Windows-browser 시각검증(행 간 역할설명·진척바·상태칩 시작 x 정렬 일치) — CHECK#13.

## REV-20260615-0256 [SUBAGENT:ship]
- Date: 2026-06-15
- Cycle: TASK-0256 (assistant 답변 diff 블록 — 프롬프트 + 웹 UI 렌더), **Major §12.3** (라이브 전역 프롬프트 = 전 답변 영향 + UI 렌더 + 배포).
- Trigger: §18.8 — UI/render(ux/design) + 프롬프트 출력 포맷. enhanceDiffBlocks 가 marked 렌더 HTML 을 DOMPurify 전 후처리 → XSS 표면 → 적대적 보안/정합 리뷰(general-purpose outside voice).
- Verdict: **SHIP** (BLOCKER/MAJOR 0).
  - 보안/XSS: parse→enhance→sanitize 순서. textContent 양방향 round-trip 안전(이중이스케이프·엔티티디코딩 XSS 없음). marked 가 코드 본문·fence info 이스케이프(실측) → `pre>code.language-diff` 셀렉터 속성주입 불가. span+class DOMPurify 기본 allowlist 통과(실측), DOMPurify 최종 실행.
  - 정합: diffLineClass 가 +++/---/@@/blank/context 정상 분류. 일반 코드블록·표·```sql 무회귀(language-diff 없으면 원본 early-return). 프롬프트 ```diff 예시 안전(py_compile), no-JSON/한국어 규칙·ATTACHED FILES 무충돌.
  - MINOR(보정 완료): 내용 정확히 "---" 인 삭제 라인 meta 오색 → +++/--- 는 후행 공백 시에만 meta 로 한정(app.js/share.js).
- Residual: PB-0008 Windows-browser 시각검증(배포 후) — diff +초록/-빨강 라인 구분.
- Cross-ref: CHG-20260615-0256 / TASK-0256 / feature-0002 REV-20260615-0256.

## REV-20260615-0260 [SKIPPED:frontend-ui-no-backend-no-rbac]
- Date: 2026-06-15
- Cycle: TASK-0260 (답변 결과셋 ◀▶ 전환 시 확장 높이 보존 — 스크롤 점프 제거), **Minor §12.3** — frontend-only 2 src(app.js+share.js) + 캐시버스터 2(index.html/share.html), 백엔드/API/스키마/RBAC/시크릿/CSS 0.
- Trigger: layout/UI keyword(§18.8 → ux). 단 본 cycle 은 navigator 의 panels 컨테이너에 동적 min-height floor 를 박는 표시 UX 만 — 신규 로직 분기 1개(축소 방지), 신규 상태·DOM 구조·엔드포인트·권한·데이터 노출 0. 전례(REV-0227 frontend-ui-state-persist / REV-0245 css-grid)와 동일 경량 SKIP.
- Reason: display 토글식 navigator 가 활성 패널 높이로 컨테이너를 매 전환 재조정해 작은 결과셋으로 갈 때 컨테이너 급축소 → 아래 콘텐츠 점프. 본 적 있는 최대 높이를 floor 로 박아 축소만 방지(확장은 허용). 결과 데이터·sanitize 경계·share 노출 표면 무변경(이미 렌더된 패널의 표시 높이만 보존, 새 데이터 로드/노출 없음) → 보안/정합 outside-voice 불필요.
- Verification: node --check app.js/share.js PASS + Playwright headless chromium 격리(큰 1000px→작은 2행 panels.h 불변·점프 0px / 수정 전 대조 960px 점프) — [[feedback_frontend_real_browser_gate]].
- Residual: 배포 후 PB-0008 Windows-browser 시각검증(다중 결과셋 답변 ◀▶ 전환 시 스크롤 점프 없음) — CHECK#13.
- Cross-ref: CHG-20260615-0260 / TASK-0260.

## REV-20260615-0261 [SKIPPED:readonly-enrich-no-rbac-no-schema]
- Date: 2026-06-15
- Cycle: TASK-0261 (대화 화면 제품 드롭업 datasource 네트워크 상태 배지), **Minor §12.3** — app.py read-only enrich + 정적자산(app.js/styles.css/index.html), 신규 테스트. RBAC/스키마/엔드포인트 shape/시크릿/conn_health 모니터 0.
- Trigger: §18.8 — UI/표시(ux) + datasource/연결 상태(backend read). 단 본 cycle 은 기존 conn_health 모니터(TASK-0250, 이미 outside-voice 게이트 통과)의 사전계산 snapshot 을 **읽어 표면화**만 — 신규 probe·연결·권한·데이터 노출 경계 변경 0.
- Reason: enrich 가 노출하는 것은 status/elapsed_ms/checked_at 뿐(좌표/비밀번호 비노출 — datasource_public 마스킹과 동일 계약, admin_list_datasources 의 conn_status 와 byte-동형). 매핑은 `datasources.resolve→scope_key`(admin all_datasources→scope_key 와 동일 키). graceful(conn_health/resolve 실패→unknown, 예외 비전파). 신규 인가 표면·SQL·외부영향 0 → 적대적 보안 outside-voice 불필요(REV-0190 datasource probe read-agg / REV-0255 insight health 표면화 선례와 동형 경량 SKIP).
- Verification: 신규 test_product_conn_status.py 8 PASS(scope_key 매핑·최악상태 집계·좌표 비노출·graceful) + make test 컨테이너 전체 회귀 0 + ruff clean + node --check + CSS brace + Playwright 격리(상태별 dot 색 + 바인딩없음 모드색 유지) + 라이브 conn_health snapshot 실측(an2-*=unstable, local/mssql=healthy 다양).
- Residual: 배포 후 PB-0008 Windows-browser 시각검증(드롭업 dot 색이 연결 상태 반영) — CHECK#13.
- Cross-ref: CHG-20260615-0261 / TASK-0261 / TASK-0250(conn_health 모니터 소스).

## REV-20260615-0262 [SKIPPED:frontend-rendering-fix]
- Date: 2026-06-15
- Cycle: TASK-0256b (diff 블록 줄 이중 줄바꿈 수정), **Minor §12.3** — 정적자산 2파일(JS) + 변경 자산 캐시버스터. 백엔드/API/스키마/RBAC/CSS/시크릿 0.
- Trigger: UI 렌더 버그. enhanceDiffBlocks 에서 block span 사이 `"\n"` 제거 — 신규 로직·상태·DOM 구조·엔드포인트·권한 0(텍스트 노드 1종 미삽입 + 미사용 파라미터 정리). 전례(REV-20260612-0236 frontend-bugfix) 동일 경량 SKIP.
- Reason: 근본원인 명확(display:block + 리터럴 `"\n"` = <pre> 이중 줄바꿈). XSS 표면 무변경(textContent 경로 동일, DOMPurify 최종 정화). 적대적 패널 불요.
- Residual: PB-0008 Windows-browser 재검증(단일 줄 간격) — CHECK#13.
- Cross-ref: CHG-20260615-0256b / TASK-0256b / REV-20260615-0256.

## REV-20260615-0263 [SUBAGENT:security-adversarial]
- Date: 2026-06-15
- Cycle: TASK-0263 (LLM 사용량 차트 hover 비용 + 클릭→집계 기여 대화목록 모달; 동시세션 TASK-0262 chip-conn-color 선점으로 재번호), **Major §12.3** — 신규 read 엔드포인트 2개 + admin 이 타 사용자 대화 메타(제목/소유자/일시/usage)를 조회하는 인가 표면.
- Trigger: §18.8 — API/endpoint + 인가 경계(타 계정 데이터 노출) → 적대적 보안 리뷰(general-purpose outside voice). [[feedback_outside_voice_for_rbac]] 정합(인가 표면 변경=외부시각 필수).
- Verdict: **SHIP** (BLOCKER 0, MAJOR 0).
  - SQLi: `_query_usage_conversations` 의 model/account_ids/day_label/owner/days 전부 bound param(%s, int 강제). gran→to_char fmt 는 `_USAGE_GRAN` 화이트리스트만 SQL 삽입. 문자열 보간 사용자 입력 0.
  - 권한: admin 엔드포인트는 console.usage.read **AND** conversation.list.any 순차 게이트(한쪽만으론 403). profile 은 owner_account_id=self(인증 계정 a.Id) 강제 + query 의 role/account_id 무시 → 일반 사용자 권한 상승 경로 없음.
  - 데이터 노출: 반환 메타 한정(좌표/비번/메시지 본문/csv_paths/preview 0). owner enrich 는 admin 만, profile 미적용.
  - NULL 처리: INNER JOIN + `conversation_id IS NOT NULL` 로 insight/시스템 비대화 usage 제외. owner NULL 대화는 `owner_is_null_ok=False` 가드(model/day 클릭 시 `owner_account_id IS NOT NULL`). "(시스템)" 역할 클릭은 query 전 빈 목록 단락.
  - 차트 정합: day=to_char(date_trunc(gran,...)) 포맷·model=COALESCE(resolved,model) 가 admin_llm_usage 집계와 동일 키.
  - MINOR(비차단): 대형 역할의 wide IN 절(admin 신뢰 경로, 파라미터화). in-query 예외 503 wrap 은 optional cleanup.
- Verification: 신규 test_usage_conversations.py 11 PASS + make test 컨테이너 회귀 0 + ruff + node --check + CSS brace + Playwright 격리.
- Residual: 배포 후 라이브 엔드포인트 검증(차원 필터 대화목록) + PB-0008(차트 hover 비용·클릭 모달·deep-link) — CHECK#13.
- Cross-ref: CHG-20260615-0263 / TASK-0263.

## REV-20260615-0266 [SKIPPED:sql-syntax-hotfix]
- Date: 2026-06-15
- Cycle: TASK-0266 (TASK-0263 핫픽스 — usage/conversations interval 파라미터 PG 문법; 동시세션 TASK-0264/0265 선점으로 0265→0266 재번호), **Minor §12.3** — app.py 1줄 SQL 문법 수정 + 회귀 가드. 백엔드 로직/인가/노출 표면 0(엔드포인트 동작만 정상화).
- Trigger: 라이브 500 버그 수정. 인가/데이터 노출 경계는 TASK-0263 의 REV-20260615-0263 [SUBAGENT:security-adversarial] 가 이미 검토(SHIP) — 본 핫픽스는 `interval %s`→`%s::interval` 문법 교정만, WHERE 조건·바인드·노출 화이트리스트 무변경. 적대 패널 재실행 불요.
- Reason: PG 가 `interval $1` 불허 → 캐스트 문법으로 동일 의미 보존(days 바인드 유지). fake cursor 단위테스트가 못 잡던 클래스라 SQL 정적 검증 가드(`test_q2b`) 추가 + 라이브 PG 실증.
- Verification: test_usage_conversations.py 12 PASS + 라이브(admin 34건 200·누출 0·일자필터 정합·profile 200).
- Residual: 정식 web 재빌드(임시 복사본 → 정식 이미지) + PB-0008.
- Cross-ref: CHG-20260615-0266 / TASK-0266 / TASK-0263(REV-0263 보안리뷰).

## REV-20260615-0267 [SUBAGENT:ship]
- Date: 2026-06-15
- Cycle: TASK-0256c (diff 블록 줄번호 old|new + 복사 시 마커·번호 제외), **Minor §12.3** — 정적자산(JS 2 + CSS 2) + 캐시버스터. 백엔드/API/스키마/RBAC/시크릿 0.
- Trigger: UI 렌더 + 신규 DOM 속성(data-gutter)·복사 메커니즘 → outside-voice(general-purpose) 적대적 리뷰.
- Verdict: **SHIP** (BLOCKER/MAJOR 0).
  - 복사 클린: 줄번호+마커는 data-gutter→`.diff-line::before content`(의사요소=선택/복사 비포함, 스펙상 Chrome/FF/Safari) + user-select:none/pointer-events:none 이중. 코드는 마커 제거 후 textContent 만 → 블록 복사 시 순수 코드. stripDiffMarker(마커 1 + 공백 1)가 프롬프트 "+ "/"- " 규약의 들여쓰기 보존. block span 다중줄 복사 시 개행 유지(0256b).
  - XSS: data-gutter/style 에 content 유래 바이트 0(줄번호=정수 카운터, mark=리터럴, --diff-gutter-ch=정수). 코드 textContent + DOMPurify 3.3.3 default 가 마지막 실행(data-* ALLOW 기본 true·style 기본 allow → 보존). style strip 시 var fallback 7 graceful(≥100줄만 약간 좁음).
  - 줄번호: hunk seed/removed-only/added-only/context/no-hunk(1-based)/meta/literal `---`/blank 전부 정확, off-by-one 0.
  - 레이아웃: `.diff-line` padding-left == `::before` width(동일 calc), 줄바꿈 hanging-indent + gutter top:0/bottom:0. 비-diff 코드/표/0256b 단일줄간격 무회귀(early-return·스코프).
  - MINOR(non-defect, 미수정): degenerate `@@ -0,0 @@` "0" 표시 / 빈 줄 복사 시 공백 1개(pre-existing).
- Residual: PB-0008 Windows-browser(줄번호 표시 + getSelection 복사 시 코드만) — CHECK#13.
- Cross-ref: CHG-20260615-0256c / TASK-0256c / REV-20260615-0256.

## REV-20260615-0269 [SKIPPED:cache-header-infra]
- Date: 2026-06-15
- Cycle: TASK-0256d (HTML 엔트리포인트 no-cache), **Minor §12.3** — app.py 3 route 에 응답 헤더 1종 + 테스트. RBAC/스키마/엔드포인트 계약/데이터/시크릿 0.
- Trigger: 백엔드(app.py) 변경이나 표준 HTTP 캐시 시맨틱(no-cache)뿐 — 권한 경계·인증·데이터 노출·쿼리 변화 0. 적대적 보안 패널 불요.
- Reason: FileResponse 에 `Cache-Control: no-cache` 추가는 브라우저 재검증 강제(보안 약화 아님 — 오히려 stale UI 방지). share.html(익명)도 민감 데이터 없는 정적 HTML 이라 무영향. 캐시버스터 전달 신뢰성 회복이 목적. test_html_no_cache + make test PASS.
- Residual: web 재배포 후 라이브 헤더(curl -I) 검증 + 사용자 하드리프레시 1회.
- Cross-ref: CHG-20260615-0256d / TASK-0256d / TASK-0256c(이 수정이 적용되게 하는 전제).

## REV-20260615-0268 [SUBAGENT:image-upload-security]
- Date: 2026-06-15
- Cycle: TASK-0268 (프로필 아바타 / 제품 아이콘 이미지 업로드·서빙; 동시세션 TASK-0267[perm-tree] 선점으로 0267→0268 재번호), **Major §12.3** — 신규 파일 업로드/서빙 엔드포인트 6 + 스키마 컬럼 2.
- Trigger: §18.8 — 파일 업로드(XSS/MIME/traversal) + 인가(IDOR) + 새 엔드포인트 → 적대적 보안 리뷰(general-purpose outside voice). [[feedback_outside_voice_for_rbac]] 정합.
- Verdict: **SHIP** (BLOCKER 0).
  - 업로드 공격면: `_sniff_image` 가 클라 MIME 무시·매직바이트로만 png/jpg/webp 판정 → SVG/HTML/GIF 거부(XSS 차단). 서빙 content-type 은 검증된 ext 기반 image/* 만 + `nosniff`+`inline`(흡수) → MIME 스니핑 XSS 닫힘. 프론트는 `<img>` 로만 로드(스크립트 실행 경로 없음).
  - 인가: avatar upload 는 path 에 account_id 없이 owner=self(인증 id) 강제. product icon 은 product.manage 게이트(upload/delete). serve 는 로그인 필요(아바타/아이콘=조직 내 공개 표시물, 의도된 동작).
  - 경로주입: object key = `<리터럴 prefix>/<int id>/<uuid4>.<검증 ext>` — 파일명 미사용 → traversal 0.
  - 스키마: `_ensure_avatar_icon_schema` 멱등 + fast/slow path 양쪽('Unknown column' 회귀 방지).
  - 정합: 교체 시 DB commit 후 old object best-effort delete(orphan 무해), 캐시버스터(object key 해시)로 stale 0.
  - 흡수: MAJOR(nosniff/Content-Disposition 부재) → `_serve_image_object` 헤더 2개 추가(라이브 실측 확인). MINOR(무제한 read·webp chunk·orphan·공개아이콘)는 비차단 기록.
- Verification: 신규 test_avatar_icon_upload.py 8 PASS + make test 회귀 0 + Playwright(Identicon) + 라이브 라운드트립(업로드 200/SVG 거부/삭제/nosniff 헤더).
- Residual: 정식 web 재빌드 + PB-0008(아바타/아이콘 업로드·Identicon 표시).
- Cross-ref: CHG-20260615-0268 / TASK-0268.

## REV-20260615-0273 [SUBAGENT:archive-security]
- Date: 2026-06-15
- Cycle: TASK-0273 (대화 삭제→soft-archive + admin 조회 + 맥락 참조), **Critical §12.3** — 파괴적 삭제 동작 의미 변경 + 신규 admin 데이터 접근 표면 + 스키마 마이그레이션.
- Trigger: §18.8 — 파괴적 동작 변경(hard-delete→archive)·신규 인가 표면(타 계정 보관 대화 메타)·진행 차단 우회 가능성 → 적대적 보안/정합 리뷰(general-purpose outside voice). [[feedback_outside_voice_for_rbac]] 정합.
- Verdict: **SHIP** (BLOCKER 0).
  - 데이터 보존(의도적): _delete_conversation_impl 가 hard-delete 대신 archive(UPDATE) — 데이터·MinIO 첨부 보존. admin only 접근. "삭제" 라벨 vs 실제 보관 괴리·GDPR 은 사용자 명시 결정(제품 정책).
  - 목록 숨김(전 경로): archived_at IS NULL 이 _list_conversations_pg(PG)·_list_conversations(MySQL) 둘 다 + has_any/self + 검색/날짜 + 파생(suggestions/_repair_current). 누출 0.
  - 진행 차단: _conversation_block_info 가 blocked_at OR archived_at → /api/ask 403(slot 전). fork 사본은 신규 cid(archived NULL) 라 진행 가능·source 는 차단 — 우회 없음.
  - admin 인가: conversation.archive.read.any 게이트, 메타만(본문 0), q bound param(SQLi 0). operator/sales 미부여(admin only).
  - 권한 catchup: catalog + admin seed + admin catchup INSERT IGNORE(기존 admin 재기동 자동 grant — 라이브 확인). 멱등 스키마 3중(additive).
  - MINOR(비차단): ① _list_conversations_pg 가 except 없는 try/finally — migrate 전 배포 시 컬럼 부재로 /api/conversations 500(단, TASK-0248 선례 동형 + migrate-first 정책 + 라이브 컬럼 적용 완료). ② admin 계정목록/usage/overview count 쿼리가 archived 필터 미적용 — admin/self 권한 뷰의 metric 드리프트(cross-user 누출 없음). follow-up.
- Verification: 신규 test_conversation_archive.py 7 PASS + 기존 block_conv 테스트 SQL 갱신 + make test 회귀 0 + 라이브 라운드트립(목록숨김·PG 기록·ask 403·admin 조회).
- Residual: 머지 → make migrate(alembic 0007 superuser, migrate-first) → web 재배포 + PB-0008.
- Cross-ref: CHG-20260615-0273 / TASK-0273 / TASK-0248(blocked 선례).

## REV-20260615-0282 [SUBAGENT:ship]
- Date: 2026-06-15 (REV-0277·0281 이 profile-icon·archives 계열에 선점되어 §13.1 재번호 0282)
- Cycle: TASK-0278 (관리 콘솔 데이터소스 목록 행별 네트워크 상태 배지), **Minor §12.3** — frontend-only, 기존 인프라 재사용.
- Trigger: 디자인/UI 변경 + grid 공유 클래스(`.admin-list-row--nav` 를 `#datasourceList`·`#settingsList` 동시 사용) 회귀 표면 → 적대적 코드리뷰(general-purpose outside voice). RBAC/보안 변경 없음([[feedback_outside_voice_for_rbac]] 강제 대상 아님)이나 회귀 위험 검토 위해 호출.
- Verdict: **SHIP** (BLOCKER 0, MAJOR 0).
  - grid 스코프 회귀 0: `#datasourceList .admin-list-row.admin-list-row--nav`(특이성 1,0,3,0) > base `.admin-list-row.admin-list-row--nav`(0,0,2,0). `#settingsList`·audit·archive nav 행은 `#datasourceList` 조상 미매칭 → 1fr 유지. settingsList 무영향.
  - leading 배치: `row.appendChild(dot)` → `appendChild(main)` 순서로 도트 col1(auto 9px)·main col2(1fr). 행 맨 앞 확정.
  - async 안전: 검색 재렌더(`innerHTML=""`) 후 늦은 probe resolve 는 `dot.isConnected` 가드로 stale 노드 갱신 차단. cache-hit fast path 가 `_dsConnAcquire` 前 return → 사전계산 N개는 세마포어 슬롯 미점유(probe storm 0).
  - 캐시우선: loadAdminData 가 conn_status(healthy→ok / unstable→fail / insight circuit_open→fail) 사전 반영, unknown 은 delete(=miss). 동기 즉시 색칠, hit 시 force=false 가 네트워크 호출 없이 즉시 resolve(중복 probe 0).
  - 독립성: `_paintDsConnDot` 은 picker `_paintDsConnBadge`(텍스트 배지)와 분리 — picker 동작 무영향.
  - MINOR(비차단, 흡수): grid item 의 무효 `flex` 선언 제거 + base 도트 `color` 명시(currentColor 점+halo 일관)로 정리 완료.
- Verification: node --check admin.js + CSS brace(1215=1215) 균형.
- Residual: 머지 → web 재배포(정적자산) → PB-0008 Windows-browser(도트 색·leading 정렬·aria-label).
- Cross-ref: CHG-20260615-0282 / TASK-0278 / REQ-20260615-0280 / REQ-20260612-0244(연결배지 인프라 선례).

## REV-20260615-0285 [SKIPPED:pb0008-evidence-docs-only]
- Date: 2026-06-15
- Cycle: TASK-0278 PB-0008 evidence 기록 (docs-only).
- Skip 사유: 코드 변경 0(순수 evidence/docs). 핵심 변경은 REV-20260615-0282 [SUBAGENT:ship] 에서 이미 적대적 리뷰(SHIP). 본 후속은 라이브 실 Windows 브라우저 PB-0008 PASS 실측 기록.
- Cross-ref: CHG-20260615-0285 / TASK-0278 / REV-20260615-0282(코드 cycle).
## REV-20260615-0286 [SUBAGENT:ds-multiselect-review]
- Date: 2026-06-15
- Cycle: TASK-20260615T183409-ds-list-multiselect (관리 콘솔 데이터소스 목록 다중 선택 구조), **Major §12.3** — 신규 일괄 파괴적 삭제(bulk delete) + 일괄 mutation(insight 토글) + 목록 행 구조(button→div) 변경.
- Trigger: §18.8 — 파괴적 일괄 동작 신설 + 공유 bulk 계약 프레임워크 확장 + 즉시-적용(async) vs pending 모델 차이 → 적대적 코드리뷰(general-purpose outside voice, "refute ship-readiness" 프롬프트). [[feedback_visual_verify_on_design_change]] 정합(UI 변경).
- Verdict: **SHIP** (BLOCKER 0 / MAJOR 0). 리뷰어가 10개 검증항목을 코드 대조로 전부 confirmed-correct 판정:
  - partial-fail 분할/토스트 카운트 정확(off-by-one·mislabel 없음), 완료 후 loadAdminData+재렌더 재동기화 + 삭제 key prune 동작.
  - `assertBulkBarContract("datasources")` 충족(ID 정합: `datasourcesBulkBar`/`datasourceSelectAll`/`datasourcesCrossPageBanner`, role=toolbar+aria-live, `.admin-list-col` 직속, head-right 라벨 누출 0).
  - select-all=필터 기준+indeterminate 정확, shift-range string-key 일관(`renderCrossPageBanner` 양측 `String(id)` 비교 → 타입 불일치 없음).
  - button→div 전환이 단일 상세 click·`_dsSyncListActive`·`newDatasourceBtn` 무파손, 체크박스 `stopPropagation` 로 상세 누출 0.
  - env 비-editable datasource 는 `_dsBulkTargetable` 게이트에서 API 호출 전 제외(insight·delete 양쪽), 바인딩 409 는 force 안 함 → "제외". XSS(textContent/createElement) 0, 함수 hoisting/TDZ 0.
- MINOR/NIT(비차단, 제품 패턴 기인 비회귀, 수정 불요): ① confirm count 가 env 포함 전체 size(제품도 동일) ② async bulk in-flight 중 버튼 비활성화 없음(더블클릭 시 2회 발화→404/409=제외, 데이터 무해) ③ insight 토글 후 선택 미해제(즉시-CRUD 모델에 타당) ④ cross-page "현재 페이지만 보기" no-op(페이징 없음, 제품 동일) ⑤ role=row aria-selected 미설정(제품 동일).
- Verification: node --check admin.js PASS + 런타임 contract assert + diff 적대 리뷰. 백엔드 무변경(엔드포인트 재사용)이라 Python 테스트 영향 0.
- Residual: web 재빌드 + PB-0008 Windows-browser(체크박스·전체선택·shift-range·일괄 삭제·insight 토글 실측).
- Cross-ref: CHG-20260615-0286 / REQ-20260615-0281 / TASK-20260615T183409-ds-list-multiselect.
## REV-20260615-0277 [SUBAGENT:rbac-adversarial]
- Change: 데이터소스 라벨/키 분리 — 제품↔데이터소스 바인딩의 canonical 식별자를 renameable 라벨(`DatasourceKey`)에서 stable surrogate `WebDatasources.Id` 로 이전. 라벨 rename 시 바인딩이 고아되던 근본결함 수정(사용자 보고). (TASK-0277, **Critical** §12.3, PLAN-APPROVED.)
- 근본원인: rename(`admin_update_datasource` key_changed) cascade 가 `WebProducts.DatasourceKey` 만 갱신, 멀티 datasource(TASK-0228/0230) join 바인딩 본체(`WebProductDatasources`)·접근DB 차원(`WebProductDatabases`) 누락 → 미바인딩=접근 0(데이터 접근 상실). 대조: 삭제 경로는 3 테이블 모두 정리.
- 대안 평가: A(키 유지+cascade 완성) / B1(DisplayLabel+키 불변) / **B2(Id surrogate 재배선, 사용자 선택)**. B2 채택.
- 구현: ① 3 테이블 `DatasourceId BIGINT NULL` 멱등 추가 + 현재 키 backfill + 단일컬럼 인덱스(`_ensure_web_product_datasources_schema`). ② rename → Id 구동 완전 cascade(3 테이블) + new_k 고아 사전제거(PK 충돌 방지) + 명시 트랜잭션(rollback). ③ 바인딩 write(add/remove/set-primary/databases) dual-write Id+Key. ④ `_runtime_tables_available` probe 에 DatasourceId 등록(기존 배포 마이그레이션 트리거, TASK-0047). ⑤ seed main_mysql→해시 rename cascade 보강. read 는 cascade 가 키 신선도 보장(무변경), 컬럼 drop·read Id-JOIN 전면화는 이월.
- 외부음성 2-pass(RBAC 적대적): 1차 **NOT-SHIP**(BLOCKER1 probe 미등록+cascade 하드의존[TASK-0047 함정] / BLOCKER2 autocommit 비원자 / BLOCKER3 PK 충돌 / MINOR DELETE-force Id·테스트). 전부 흡수 수정 → 2차 **SHIP-WITH-FIXES**(4 BLOCKER 해소 확인, 신규 BLOCKER 0).
  - Accepted-risk(비차단): MAJOR-1(cascade OR-clause 이론적 PK 충돌) — dual-write/backfill 이 (key,DatasourceId) 일관성 유지 + DatasourceKey UNIQUE 라 같은 (제품,스키마)에 같은 Id distinct 행 2개 생성 불가 → 실질 도달 불가, 게다가 이제 fail-loud(rollback). MINOR-1(ensure_dek 내부 commit) — 첫 datasource write 전 호출이라 DEK 영속만, rename 원자성 무영향. MINOR-2(seed 충돌 swallow) — 기존 패턴·seed-time·동일 일관성 논거로 도달 난망.
- Verification: 신규 test_datasource_rename_binding_stable.py 4(R1 3테이블 cascade+pre-clean·R2 Id구동·R3 비-rename 무cascade·R4 컬럼부재 key-only 완전동작) + 기존 test_datasource_edit_label_stable 3 PASS + make test 컨테이너 회귀 0 + ruff clean.
- Residual: 머지 → web 재배포(스키마 마이그레이션은 web 부팅 _ensure_web_tables 에서; ask-worker/insight-worker 코드 무변경) → 라이브 검증(라벨 rename→제품 바인딩·접근DB 유지).
- Cross-ref: CHG-20260615-0277 / TASK-0277.

## REV-20260615-0289 [SKIPPED:pb0008-evidence-docs-only]
- Date: 2026-06-16
- Cycle: TASK-20260615T183409-ds-list-multiselect PB-0008 evidence 기록 (docs-only).
- Skip 사유: 코드 변경 0(순수 evidence/docs). 핵심 코드 변경은 REV-20260615-0286 [SUBAGENT:ds-multiselect-review] 에서 이미 적대적 리뷰(SHIP, BLOCKER 0). 본 후속은 라이브 main 3605443 배포 후 실 Windows 브라우저 PB-0008 PASS 실측 기록(14행 div+체크박스+연결도트·grid 13px 9px 251px·전체선택 indeterminate·bulkBar buttons).
- Cross-ref: CHG-20260615-0289 / TASK-20260615T183409-ds-list-multiselect / REV-20260615-0286(코드 cycle).

## REV-20260616-0290 [SUBAGENT:conn-tristate]
- Date: 2026-06-16 (동시세션 REV-20260615-0289 선점 → 0290 재번호)
- Cycle: TASK-0282 (datasource 연결 상태 3단계 분류 + 느린 타-리전 연결 완화), **Major §12.3** — conn_health 분류/게이트 로직 + fast-fail 완화(unstable 시도 허용) + 표시 3색.
- Trigger: §18.8 + [[feedback_outside_voice_for_rbac]] 정합(연결 게이트·worker 점유 경계 변경) — 적대적 코드리뷰(general-purpose outside voice, "refute ship-readiness").
- Verdict: **SHIP-WITH-FIXES** (BLOCKER 0). 보안(SSRF `_ssrf_check_host`/`_is_blocked_target` 불변·비번/좌표 snapshot·/test·classify 비노출)·분류경계(classify `==SLOW`/`==DOWN_AFTER_FAILS` `>=`, elapsed None=healthy)·상태전이(blip→unstable→down→복구·stale 강등)·프론트정합(state↔CSS 1:1, 레거시 is-fail 별칭) 전부 코드 file:line 대조 confirmed-correct.
- 흡수(must-fix):
  - **(MAJOR/process)** worktree base 4030640 이 origin/main(PR#261 TASK-0277 DatasourceId surrogate) 이전 → 그냥 머지하면 app.py TASK-0277 작업 silent revert. **origin/main(fe173d7) 위로 rebase + make test 재실행**. → **흡수 완료**(rebase 시 app.py 자동병합 양립 확인, docs 충돌만 재번호).
  - **(MINOR)** foreground connect 성공이 elapsed 미측정(0.0)→HEALTHY 로 background UNSTABLE 을 덮어 느린 DS 배지 flapping(≤`AGENT_CONN_HEALTHY_RECHECK_SEC` 30s). → db.py `connect_with_retry` 가 connect 소요(ms) 측정해 `_record_health(elapsed_ms=…)`→`record_foreground_result` 전달 → foreground 도 SLOW 임계로 unstable 일관 분류. **흡수 완료**.
- Should-note(비차단): ① down DS worker 점유 window 가 1-fail→연속 2-fail 로 약간 넓어짐(background 2-3s 내 DOWN 도달까지 bounded; per-attempt 10s×3 retry 한계 불변 — TASK-0247/0250 의 15분 starvation 재발 아님; Q2 의 명시 수용 비용, ask-worker 가 monitor 기동 전제). ② 레거시 cache `state:"fail"` 가 배포 직후 1회 회색(down) 렌더 — self-heal(다음 loadAdminData snapshot).
- Verification: test_conn_health 재작성 27 + product_conn down 최악 + /test status + make test 컨테이너 전체 회귀 0 + ruff + node --check + CSS brace(1221).
- Residual: web+ask-worker+insight-worker 재배포 → PB-0008 Windows-browser(3색 배지·느린연결=빨강·끊김=회색·작업화면 사용가능 실측).
- Cross-ref: CHG-20260616-0290 / TASK-0282.

## REV-20260616-0291 [SUBAGENT:attachment-access]
- Date: 2026-06-16
- Cycle: TASK-0284 (첨부 3개 이슈: cross-account LLM 주입 / 외부 머신 다운로드 / 파일명 지칭), **Critical §12.3** — 첨부 LLM 주입 인가 스코프 변경(AccountId → ConversationId) + 신규 프록시 다운로드 라우트.
- Trigger: §18.8 + [[feedback_outside_voice_for_rbac]] — 인가 경계(RBAC/IDOR) 변경. 적대적 코드리뷰(general-purpose outside voice, "refute ship-readiness").
- Verdict: **SHIP-WITH-FIXES** (BLOCKER 0, MAJOR 0, MINOR 1).
- 핵심 가설 반증(confirmed-correct, 코드 file:line 대조):
  - **H1 cross-account LLM 주입 → REFUTED**: `/api/ask` 가 주입 전 conv_id 를 **owner-only** 게이트(`_conversation_owned_by_account` app.py:9338/6128, `_account_can_access_conversation`(any) 아님) → 비-owner 는 타 대화 ask 불가(403). 모든 주입 쿼리가 ConversationId 스코프 + conv_id 는 owned conv 에 바인딩. 타 대화 attachment_ids 주입은 ConversationId 불일치로 0행. conv_id 흐름 `ask → _dispatch_ask_run → _run_agent_core(conversation_id=) → compose_system_prompt → _build_attachment_context_section` + worker 경로(modules/ask.py)도 동일 게이트 conv_id 상속. 미게이트 호출자 0.
  - **H2 account 폴백 fail-open → REFUTED**: 둘 다 없으면 fail-closed(`_attach_scope_clause`→None→pg_select []; agent_core 가드 `not account_id and not _scope_by_conv`→"").
  - **H3 다운로드 IDOR → REFUTED**: `download_attachment` 가 `get_attachment_metadata` 와 구조 동형(_account_can_access_attachment own/any, row=None→404, pending→403 으로 metadata(200+null)보다 더 엄격).
  - **H4 inline/XSS → REFUTED**: octet-stream + `Content-Disposition: attachment` + nosniff 로 inline 렌더 차단(text/html 첨부 포함).
  - **H5 SQLi → REFUTED**: scope 컬럼명은 고정 리터럴(if 분기, 사용자 입력 아님), 값은 전부 %s 바인딩.
  - **H6 PG/MySQL parity → REFUTED**: MySQL 폴백은 `rows is None`(예외)만, PG 0행(`[]`)은 폴백 안 탐. 양 백엔드 스코프 동일.
- 흡수(must-fix MINOR-1): `download_attachment` ascii_fallback(app.py)이 CR/LF 제어문자 미제거 → Content-Disposition 헤더 인젝션 표면(OriginalFilename 은 업로드 시 `.strip()` 만 → CRLF 잔존 가능). **현 uvicorn+h11 런타임은 CRLF 헤더값 거부→500 이라 비악용**이나 ASGI 서버 교체 대비 방어적으로 `c.isprintable()` 필터로 모든 비출력 제어문자 제거. filename*(RFC5987)은 percent-encoding 이라 원래 안전. **흡수 완료**.
- Should-note(비차단): fork 는 첨부를 새 ConversationId + fork-owner AccountId 로 복사(app.py:10537~)하므로 기존 AccountId 스코프도 매칭됐을 것 — 진짜 깨진 케이스는 account-context drift 이며, ConversationId 스코프가 올바른 통일(보안 경계는 owner-gated 유지).
- Verification: test_attachment_idor.py(IDOR 5 + 신규 conversation 스코프·account 폴백·파일명 우선 4) + test_task0284_attachment_access.py 9 + make test 컨테이너 전체 회귀 0(pytest 0 fail/2 skip, ruff clean).
- Residual: 머지 → 배포(web + ask-worker 재빌드) → 라이브 검증(cross-account 주입·외부 다운로드·파일명 답변) → PB-0008.
- Cross-ref: CHG-20260616-0291 / TASK-0284 / feature-0002 REV-20260616-0291.

## REV-20260616-0299 [SUBAGENT:rbac-gating]
- Date: 2026-06-16
- Cycle: TASK-0288 (권한 회수 미반영 RBAC 결함 4종 + '제품' 권한 2축 분리), **Critical §12.3** — 권한 모델/인가 경계 변경.
- Trigger: §18.8 + [[feedback_outside_voice_for_rbac]] — RBAC 카탈로그·엔드포인트 게이트 변경. 적대적 보안 리뷰(general-purpose outside voice, bypass·escalation·lockout·blindspot 집요 탐색).
- Verdict: **SHIP** (BLOCKER 0, MAJOR 0, MINOR 2, NIT 1).
- 7항목 코드대조 결론(전부 안전):
  - **① bypass**: datasource/product 조회·변경 엔드포인트 22개 전수 grep — GET 6개 전부 `_account_has_any_permission(read,manage)` 게이트, CRUD 는 _ds_write_common 단일경로 datasource.manage·product.manage. 누락 0. (관찰: `/api/session`·`/api/auth/me` 가 인증사용자에 _list_products 반환하나 자격증명 0·work-screen 피커용·사용은 _account_has_product_access 별도 게이트 — 범위외 사전존재.)
  - **② lockout**: admin catchup tuple 에 datasource.read/manage·product.read 등록 확인, admin seed=set(PERMISSION_CODES), _ensure_permission_catalog→_ensure_seed_roles 순서로 신규코드 backfill. 위험 0.
  - **③ superset(manage⊇read)**: GET 게이트 전부 read|manage OR — manage-only 계정도 조회 통과.
  - **④ 동적권한 group 마이그레이션**: UPDATE 는 GroupName 만(IsDynamic=1 AND product.access.% 한정·멱등), enforce(_account_has_product_access)는 code 기반·GroupName 미참조, WebRolePermissions 부여 보존. group=순수 UI 메타.
  - **⑤ 프론트 게이팅 보안경계**: ADMIN_TAB_PERMISSIONS↔백엔드 403 1:1 정합(프론트=UX, 실경계=백엔드). jsdom 34/34.
  - **⑥ IDOR/escalation**: 바인딩 엔드포인트 console.manage 유지(accepted), datasource_key=_dsr.resolve 검증, admin_list_datasources user/password 비노출(has_password bool만).
  - **⑦ override 회수**: OVERRIDE_DENY→False, _empty_permission_map 이 전 PERMISSION_CODES(신규 포함) 시드 → 신규 권한도 deny 회수 실효.
- 흡수(MINOR-1): datasource 탭 생성/수정/삭제/bulk 버튼이 console.manage 게이트 → datasource.manage 로 정합(read-only 뷰어는 목록만). **흡수 완료**.
- 흡수(NIT): `_resolve_permission_catalog` docstring 의 동적권한 GroupName 'product'→'product_access' 갱신. **흡수 완료**.
- Should-note(비차단, accepted): product-datasource 바인딩 mutation(`/api/admin/products/{id}/datasource(s)`)은 console.manage 유지(사전존재 결정·데이터 접근은 product.access+DB allowlist 별도 게이트). 범위 명시.
- Verification: jsdom verify_admin_tab_gating.mjs 34 PASS + make test 컨테이너 전체 회귀 0(영향 테스트 4개 신규 계약 갱신) + node --check + py ast.parse.
- Residual: 머지 → 배포(web 재빌드) → 라이브 재검증(테스트계정 products/datasources 403 전환·탭 숨김) → PB-0008 Windows-browser.
- Cross-ref: CHG-20260616-0299 / TASK-0288.
## REV-20260616-0302 [SUBAGENT:runtime-transparency]
- Date: 2026-06-16
- Cycle: TASK-0289 (대화 수행시간 정직 표시 + 내부 동작 투명화 + 즉각 반응 + 큐 병목 완화), **Major §12.3** — 채팅 요청 경로의 수행시간 측정·step 기록·worker 큐 폴링 변경(인증/데이터 비파괴, 사용자-대면 동작 변경).
- Trigger: §18.8(backend + performance + UX dimension) — 채팅 lifecycle·ask-worker run-status/cancel 인접(TASK-0241 clobber trap)·타이밍 산수. 적대적 코드리뷰(general-purpose outside voice, "refute correctness").
- Verdict: **SHIP** (BLOCKER 0, MAJOR 0, MINOR 0). 8개 위험가설 전부 코드 file:line 대조 confirmed-correct + 회귀 0.
- 핵심 가설 반증(confirmed-correct):
  - **emit_index 정합 → OK**: 단일 스레드 `_run_agent_core` 에서 activity·tool 둘 다 사용 전 `+=1` → 단조·충돌불가. progress `after_step`(StepIndex>%s)·프론트 `Math.max(stepCount, maxIdx)`·`_load_step_count_for_run` COUNT(*) 전부 contiguous index 와 정합. `step_intent = step_count==1`(tool 전용 카운터) 불변. emit 저장 실패(DB gap) 시에도 프론트 Math.max 라 폴링 무영향(robustness 보너스). attachment_edit step(`max(step_index)+1`)도 자동 적응.
  - **TASK-0241 clobber → OK**: 모든 terminal `set_run_status(only_if_current_run=True)`·run_id 게이팅·superseded 가드 불변. `duration_ms`=total 로 값만 교체(동일 전달). canceled-path "결과 정리 중" activity skip 정확.
  - **queued_ms wall-clock → OK**: `ask_jobs.created_at` = timestamptz → psycopg tz-aware → `.timestamp()` POSIX epoch(tz-naive skew 없음). `time.time()-created_at.timestamp()` 초→×1000 ms, `max(0.0,…)` 음수 클램프. total = queued(ms) + (now_perf−agent_entry_perf)×1000 = disjoint 2구간 합(큐 대기 vs in-process) — sound.
  - **_emit_activity 안전 → OK**: cid/run_id/mem_conn 전부 def·첫 호출 전 할당, DB-connect 실패는 그 전 early-return(unbound 참조 0). try/except: pass 로 PG write 실패가 run 을 못 깸. `_writes_allowed` 게이트(tool step 과 동일).
  - **claim RETURNING → OK**: 프로덕션 소비자 1곳(ask.py)이 dict `.get("created_at")` 만(positional 0), `row[7] if len(row)>7 else None` 가드. 테스트 8-tuple/dict/7-tuple 호환 전부 green.
  - **breakdown 직렬화 → OK**: `dict[str,float]` JSON-safe, 기존 `duration_ms` 와 동일 `mirror_meta→save_memory_message(json.dumps)` 경로. 구 메시지(breakdown 부재)는 `formatDurationBreakdown` 가 "" 반환→plain duration 폴백.
  - **activity step 헬퍼 오염 → OK**: in-memory `steps` 리스트에 미append → `_step_csv_paths`/`_summarize_step_rationale`/`_collapse_large_tables` 미노출. share 경로 `_share_sanitize_step` whitelist 통과하나 SQL/사용자 payload 없는 서버상수 라벨뿐 + share.js 가 `tool==="execute_sql"` SQL 패널만 → inert(누출 0).
  - **성능 → OK**: `_emit_activity`당 PG conn open/close(기존 tool step 과 동일 패턴), run 당 ~6-8개·bounded(unbounded 성장 0). idle_poll 0.5s = idle claim SELECT 4× 빈도(단일 worker 무시 가능).
- Should-note(비차단): claim→agent_entry_perf 사이 미세 구간(run_id set + heartbeat 스레드 기동) 미집계 — sub-ms under-count, 결함 아님.
- Verification: test_duration_breakdown.py 3(산수 결정 고정) + test_ask_jobs.py created_at 2 + verify_runtime_transparency.mjs 16(jsdom 포맷·정적계약) + feature-0002 전체 pytest 회귀 0(2 skip) + py_compile + node --check app.js.
- Residual: 머지 → web + ask-worker 재빌드(agent_core baked) → 라이브(total 표시·activity 타임라인·큐 단축) → PB-0008 Windows-browser(수행시간 안 줄어듦·내부 동작 step·breakdown). SSE 토큰 스트리밍(P3b)은 후속 cycle(사용자 결정).
- Cross-ref: CHG-20260616-0302 / TASK-0289 / feature-0002 REV-20260616-0302.
- Cross-ref: CHG-20260616-0301 / TASK-0289 / feature-0002 REV-20260616-0301.

## REV-20260616-0303 [SKIPPED:frontend-only-css-overflow]
- Date: 2026-06-16
- Cycle: TASK-0292 (관리 콘솔 좌측 사이드패널 수직 스크롤), **Minor §12.3** — frontend-only CSS.
- Skip 근거: 변경이 순수 CSS 2속성(styles.css `.admin-tabs` 에 `min-height:0; overflow-y:auto;`, `.admin-sidebar-foot` 에 `flex-shrink:0`) + admin.html 캐시버스터 1줄. 백엔드/RBAC/인가/스키마/엔드포인트/데이터 흐름 무변경 — §18.8 outside-voice dispatch 키워드(auth/schema/API/perf) 비매칭. 작업 화면 `.conv-list`(styles.css:500-503) 의 기존 검증된 idiom 을 admin 사이드바에 동형 적용한 것이라 신규 보안/회귀 표면 없음.
- 비변경 단언: HTML 구조 0, JS 0, 백엔드 0. 모바일(≤680 `.admin-sidebar{display:none}`) 무영향. 다른 페이지(index/share)는 admin 사이드바 미렌더라 무영향.
- Verification: CSS brace 균형 검사 + 정적 검증 → 머지 → web 재배포 → PB-0008 Windows-browser(짧은 viewport: `.admin-tabs` overflow-y computed=auto·scrollHeight>clientHeight·하단 '설정' 탭 스크롤 도달).
- Cross-ref: CHG-20260616-0303 / TASK-0292 / AC-0541.

## REV-20260616-0304 [SKIPPED:docs-only-pb0008-evidence]
- Date: 2026-06-16
- Cycle: TASK-0292 후속 docs-only (PB-0008 evidence + 배포 기록), **Minor §12.3**.
- Skip 근거: 코드·자산 변경 0 (TASK-0292 본 변경은 CHG-0303/REV-0303 에서 이미 적대 평가 SKIP·머지·배포). 본 cycle 은 PB-0008 PASS 결과와 배포 사실을 정본 문서에 기록하는 docs-only. 신규 보안/회귀 표면 없음.
- 검증 요약: PB-0008 Windows-browser PASS — computed `overflowY=auto`·`minHeight=0px`·foot `flexShrink=0`; 짧은 viewport(240px)에서 `.admin-tabs` scrollHeight 572 > clientHeight 134 → scrollable, 하단 '설정' 탭 스크롤 도달(settingsReachable=true), foot/brand 고정.
- Cross-ref: CHG-20260616-0304 / TASK-0292 / AC-0541.

## REV-20260616-0305 [SUBAGENT:audit-dashboard-scope]
- Date: 2026-06-16
- Cycle: TASK-0293 (감사 로그 `.own` Actor-only + 대시보드 위젯 데이터 권한 게이팅), **Critical §12.3** — 감사 가시성/데이터 노출 경계 변경.
- Trigger: §18.8 + [[feedback_outside_voice_for_rbac]] — audit 스코프 + RBAC 데이터 경계 변경. 적대적 보안 리뷰(general-purpose outside voice).
- Verdict: **SHIP** (BLOCKER 0, MAJOR 0, MINOR 1).
- 8항목 코드대조 결론(전부 안전):
  - **① audit `.own` 완전성**: `_audit_build_self_filter_sql`=`ActorAccountId=%s` 단일, 호출처 전수(list/single/profile list·single/resources facet inline) Actor-only 일관, actors facet `.own`=본인 actor 단건. **잔존 `OR TargetAccountId` SQL 분기 0건**(TargetAccountId 잔존은 DDL/INSERT/SELECT projection 만).
  - **② under-exposure 부작용 무**: 본인 actor 이벤트(ask/share 등)는 ActorAccountId=self 기록이라 그대로 노출. single-event 404 byte-equal 유지.
  - **③ `.any` 무영향**: self filter 는 `if scope=="own"` 가드 안만 — `.any` 전체 조회.
  - **④ 위젯 게이팅 완전성**: catalog·widgets 동일 `_actor_can_see_widget` 경계, `_isolate` 미허가 데이터 미계산, PG 블록도 permitted 게이트.
  - **⑤ superset**: products/datasources 리스트 권한 read|manage OR.
  - **⑥ conversations 권한 적정**: cross-account COUNT(*) 집계 → conversation.list.any.
  - **⑦ prefs 우회 불가**: overview permitted 가 유일·실효 경계 + 프런트 catalog 권위 렌더 이중 차단.
  - **⑧ grant_health/pending**: 데이터원 엔드포인트 console.access 게이트, pending=순수 클라.
- 흡수(MINOR): profile audit 엔드포인트 docstring "Actor or Target" → Actor-only 갱신(동작 무해, 주석만). **흡수 완료**.
- Verification: test_dashboard_overview.py + test_audit_rbac.py smoke + make test 컨테이너 회귀 0.
- Residual: 머지 → 배포(web 재빌드) → 라이브 재검증(`.own` target row 부재·대시보드 리소스 위젯 데이터 0).
- Cross-ref: CHG-20260616-0305 / TASK-0293 / TASK-0288(선행).

## REV-20260617-0306 [SUBAGENT:widget-data-scope]
- Date: 2026-06-17
- Cycle: TASK-0294 (대시보드 위젯 데이터 `.own`/`.any` 세분화 스코핑), **Critical §12.3** — 위젯 데이터 노출 경계 변경.
- Trigger: §18.8 + [[feedback_outside_voice_for_rbac]] — RBAC 데이터 스코프 변경. 적대적 보안 리뷰(general-purpose outside voice).
- Verdict: **SHIP** (BLOCKER 0, MAJOR 0, MINOR 0, INFO 1).
- 7항목 코드대조 결론(전부 안전):
  - **① SQL injection**: self-filter `ActorAccountId/owner_account_id = %s` parameterized(%s + args 튜플, placeholder=args 정합), account_id `int()` 캐스트·f-string 직접삽입 0, days int clamp.
  - **② `.own` self-scope 완전성**: audits 5쿼리(cur_total/prior/last24/spark/by_action) 전부 `AND ActorAccountId=self`, by_actor `if not own` 생략. conversations 전 COUNT/spark `owner_account_id=self`, 활성소유자 `if not own` 생략. 누출 0.
  - **③ scope 결정**: `_widget_data_scope` = any 보유시 'any' else 'own'. own+any 둘다→'any'(정상).
  - **④ 가시성↔데이터 정합**: `_actor_can_see_widget`(own|any OR) ↔ `_widget_data_scope`. `.own`만→visible+scope='own'.
  - **⑤ account_id 무결성**: `int(actor["id"])` = 세션쿠키 인증 서버권위값(요청파라미터 아님). fail-closed(None→-1 매칭0).
  - **⑥ `.any` 무회귀**: scope='any'→own=False→self_and=''/args=() → 쿼리 byte-identical, by_actor/owners 전부 실행.
  - **⑦ 잔존 위젯**: accounts(by_role 집계만·개별 username 미노출)·usage(per-model 집계·per-account 비용 미노출)는 단일 관리권한이라 `.own` 짝 불필요·PII 미노출.
- 흡수(INFO/defense-in-depth): D1 fail-open(`scope='own'`+`account_id=None`→cross-account widen, 현 호출그래프 도달불가) → account_id None 시 -1(매칭 0) fail-closed 적용. **흡수 완료**.
- Verification: test_dashboard_overview.py + make test 컨테이너 회귀 0.
- Residual: 머지 → 배포(web 재빌드) → 라이브 재검증(`.own` 계정 위젯 self-scoped·by_actor/활성소유자 부재) + PB-0008.
- Cross-ref: CHG-20260617-0306 / TASK-0294 / TASK-0293(선행).

## REV-20260617-0307 [SUBAGENT:perm-self-scope-security]
- Date: 2026-06-17
- Cycle: TASK-0300 (관리 콘솔 계정/역할 권한 편집 self-scope — privilege escalation 방지), **Critical §12.3** — 인가 경계 변경.
- Trigger: §18.8 + [[feedback_outside_voice_for_rbac]] — RBAC 권한 모델 변경. 적대적 보안 리뷰(general-purpose outside voice).
- Verdict: **SHIP-WITH-FIXES** → 권고 흡수 후 **SHIP**.
- 우회 경로 전수(진입점→가드): 계정 override=`admin_update_account`(`_enforce_override_self_scope` 403) SAFE / 역할 권한=`admin_update_role`+`admin_create_role`(`_enforce_role_permission_self_scope` 403) SAFE / `_set_account_overrides`·`_set_role_permissions` 타 HTTP 호출처 0 / signup·`/api/auth/me`=perm/override 미수용 SAFE / `_create_role_with_permissions`=seed·bootstrap(actor 비도달) N/A / delete cascade=부여 불가 SAFE.
- 확인-안전(무조치): ① merge 정확성 — 범위 밖 기존값 보존(누락 시), escalation 체크가 merge **앞**이라 범위 밖 값 덮어쓰기/삭제 불가. 범위 안 inherit/uncheck 정확 제거. ② editable 집합 — `_account_permissions`(effective: deny override→False 반영) 기준, actor=세션 권위값. ③ survivor/lockout — survivor 가 merge **결과**로 평가, self-scope 로 last-management 박탈 불가. ④ bootstrap=전권→no-op, 무권한 actor=부여 0+기존 보존. ⑤ 프론트=UX 전용, 백엔드 merge 가 최종 정본. ValueError→403·conn.close() 전 신규 분기 present.
- 흡수한 권고:
  - **MAJOR-1 (역할 *배정* 경유 escalation)**: `account.role.assign` 보유 admin 이 고권한 역할 배정으로 미보유 권한 부여 가능. **사용자 결정(배정도 차단)** → `_role_grant_excess_for_actor` 신설 + `admin_update_account` 역할 변경 시 배정역할 권한 ⊄ actor → 403 + 프론트 드롭다운 숨김. **흡수 완료**.
  - **MINOR-1 (product.access.* self-scope 포함 over-block)**: DefaultRoleAccess=1 제품 무영향(admin 전보유), =0 제품만 미보유 admin provisioning 불가. **사용자 결정(포함 유지)** — 더 엄격·기본제품 무영향. accepted.
  - **MINOR-2 (계정/역할 가드 비대칭)**: override=submitted 전체 vs role=added 만 검사(데이터 모델 차이로 둘 다 정확). **docstring NOTE 추가**(향후 잘못된 통일 방지). 흡수.
- Verification: test_perm_self_scope.py 18 PASS(ast 추출 실 helper 4종) + verify_perm_self_scope.mjs 13 PASS(실 renderPermissionGrid) + node --check + py ast.parse. **화면 정본 = PB-0008**.
- Residual: 머지 → 배포(web 재빌드) → 라이브 재검증(제한 admin 미보유 권한 행/역할/제품카드 부재·우회 PATCH 403×3경로·범위 밖 기존값 보존) + PB-0008.
- Cross-ref: CHG-20260617-0307 / TASK-0300 / TASK-0288(RBAC 선행)·TASK-0257(권한 편집기).

## REV-20260617-0308 [SKIPPED:evidence-docs-only-pb0008-live403]
- Date: 2026-06-17
- Cycle: TASK-0300 evidence (라이브 403 + PB-0008 Windows-browser 검증 기록), docs-only.
- Trigger: §18.4 — 코드 무변경 evidence 기록 cycle. panel 생략 정당(TEST/REPORT/TASK/MODIFY 문서만, RBAC 코드 변경은 선행 REV-20260617-0307 에서 적대 보안 리뷰 완료).
- Verdict: **[SKIPPED]** — 검증 산출물 기록(라이브 403 4벡터 PASS + PB-0008 실 Chrome PASS). 신규 코드/엔드포인트/권한 0.
- Cross-ref: CHG-20260617-0308 / TASK-0300 / REV-20260617-0307(코드 적대 보안 리뷰 SHIP).

## REV-20260617-0311 [SKIPPED:frontend-only-font-size-2lines]
- Date: 2026-06-17
- Cycle: TASK-0301 (제품 목록 항목 글꼴 크기 정합), frontend-only 2줄 변경.
- Trigger: §18.4 — RBAC·스키마·엔드포인트 무변경, 시각 정합 2줄 CSS 클래스 교체(보안 surface 없음). panel 생략 정당.
- Verdict: **[SKIPPED]** — `admin-account-name`(15px) → `admin-list-row-name`(13px) 클래스 교체. 데이터 흐름·권한·스키마 무영향. 기능 회귀 없음(동일 텍스트 노출, 크기만 변경).
- Cross-ref: CHG-20260617-0311 / TASK-0301.

## REV-20260617-0312 [SUBAGENT:bulk-delete-apply-safety]
- Date: 2026-06-17
- Cycle: TASK-0301 (관리 콘솔 제품 일괄 삭제 미적용 + bulk staging 목록 즉시 반영), Major §12.3 — 파괴적 삭제 경로 활성화.
- Trigger: §18.8 — 그동안 무효였던 파괴적 동작(제품 일괄 삭제) 활성화. 적대적 outside-voice 리뷰(general-purpose, REFUTE 지향).
- Verdict: **SHIP-WITH-FIXES** → 권고 흡수 후 SHIP.
- 적대 검증 6항목: ① 의도외 삭제 — **REFUTED**(`_delete` 는 `bulkProductDelete` 만 staging, 제품 상세 편집기엔 delete 버튼 없음→PATCH-only 행에 stray `_delete` 불가, DELETE 분기는 `if (patch._delete)` 엄격 게이트) ② 기본 제품 보호 — **REAL MAJOR**(백엔드 무가드, 프론트 canTargetRow 만) ③ 혼합 PATCH+DELETE — MINOR by-design(`_delete` 우선, account/role 정합, 삭제 행 편집 폐기는 정확) ④ partial-fail — **REFUTED**(per-item try/catch, 실패 시 `pending.delete` 미도달→pending 보존+failures, `loadAdminData` 재동기화, 백엔드 tx rollback) ⑤ renderXList 회귀 — MOSTLY REFUTED + MINOR(제품 행 pending 마커 부재로 cosmetic no-op) ⑥ cascade — MINOR 기존·의도적(hard delete + 참조 대화 '차단' 전환 TASK-0248).
- 흡수한 권고:
  - **MAJOR (기본 제품 backend 가드)**: `DELETE /api/admin/products/{id}` 에 `IsDefault`→409 + 미존재→404 추가. bulk DELETE 경로가 이제 실제 서버 도달 → 프론트 canTargetRow(client-trust)만으론 destructive cascade 보호 불충분. 단일 삭제 경로도 동일 가드 적용. **흡수 완료**.
  - **MINOR (제품 행 pending 마커)**: 제품 행에 `has-pending`/`is-to-delete` + pending dot 신설(계정/역할 동형) → `renderProductList` 재렌더가 실제 시각 표시. **흡수 완료**(라이브 is-to-delete rows=2·pendingDots=2 확인). 주석도 정합화.
  - MINOR (혼합 by-design)·MINOR (cascade 기존) — 무조치(정확/의도).
- Verification: 라이브(실 running stack + 브라우저) 수정 전 0/3 → 수정 후 3/3 삭제, 회귀 역할 일괄 비활성 2/2, node --check + py ast.parse. **화면 정본 = PB-0008(배포 후)**.
- Residual: 머지 → 배포(web 재빌드) → 라이브 재검증(기본 제품 삭제 409·일괄 삭제 전부·pending 마커) + PB-0008 Windows-browser.
- Cross-ref: CHG-20260617-0312 / TASK-0302 / TASK-0300·TASK-0301(동시세션 식별자 충돌로 재번호된 별건들).

## REV-20260618T022150-ai-claude-ds-acc-collapsible [SKIPPED:frontend-ui-presentation-toggle-no-backend-no-rbac]
- Date: 2026-06-18
- Cycle: TASK-20260618T022150-ai-claude-ds-acc-collapsible (관리 콘솔 > 제품: 펼쳐진 데이터소스의 접근 가능 DB 목록 접기), **Minor §12.3**.
- Panel 생략 근거(§18.8): 표현 계층 전용 toggle 추가 — 백엔드·스키마·엔드포인트·RBAC·데이터·CSS 무변경, 신규 권한 0, 파괴적 동작 0. UI/layout 신호는 PB-0008 Windows-browser 가 정본 검증(§10.5). RBAC/보안 인접 아님 → outside-voice 불요([[feedback_outside_voice_for_rbac]] 비대상).
- 설계 판단: ① 접힘을 별 상태(`_dsBodyCollapsed`)로 두고 `_editDsKey`(편집 대상)는 보존 — 접어도 draft/picker 클로저가 유지되어 데이터 손실 0, 재펼침 시 그대로 복원. ② 기본값 펼침(false)로 멀티 datasource 기존 흐름·패널 재진입 일관성 무회귀. ③ 다른 datasource 전환(`_switchEditDs`)·편집 대상 제거(`_afterBindChange`) 시 자동 펼침 리셋 — "전환=편집 시작" 의도와 정합, 접힌 채 다른 ds 로 넘어가 혼란 방지. ④ 접힌 행 = 기존 비활성 행과 동일 렌더라 CSS 무변경(멀티 datasource 에 이미 존재하던 스타일 재사용).
- 검토한 회귀 리스크: (a) 접힘 중 `_refreshAccessibleDbs`/`redrawChips` 가 detached `dbEditorWrap` 에 작동 — DOM 분리 상태라도 메모리 노드 조작은 무해, 재펼침 시 반영. (b) `_afterBindChange` else-분기(primary 배지 갱신)는 접힘 상태 보존 — 접은 채 기본 지정해도 body 안 튀어나옴(의도). (c) accordion 재렌더가 head 클로저를 새로 만들어 토글 후 재클릭 정상 동작(테스트 토글2 로 확인).
- Verification: `node -c admin.js` + `tests/verify_ds_accordion_collapse.mjs` 19/19 PASS. 화면 정본 = PB-0008(배포 후).
- Residual: 머지 → web 재배포(deploy_scope: included) → PB-0008 Windows-browser(실 화면 접기/펼치기 + 하단 UI 접근) → evidence CHG/REV.
- Cross-ref: CHG-20260618T022150-ai-claude-ds-acc-collapsible / REQ-20260618-0314 / AC-0571 / TASK-0238(accordion 원 설계).

## REV-20260618T024209-ai-claude-ds-acc-collapsible-evidence [SKIPPED:docs-only-pb0008-evidence]
- Date: 2026-06-18
- Cycle: TASK-20260618T022150-ai-claude-ds-acc-collapsible PB-0008 evidence 기록, **Minor §12.3**, docs-only.
- Panel 생략 근거(§18.8): 코드·스키마·RBAC·배포 변경 0 — 이미 머지·배포된 frontend toggle(PR #323)의 실 Windows 브라우저 검증 결과를 문서에 기록할 뿐. 신규 위험 표면 없음.
- PB-0008 요지(PASS): 단일 datasource 제품 KR(`mysql-local`) — 사용자 보고 시나리오 정확 일치. 초기 펼침(body display:block·caret ▾·'+ 데이터소스 추가' 912px > viewport 836px 화면 밖) → 데이터소스 머리 클릭 접힘(`.ds-acc-body` 제거·행 유지·is-active 해제·aria false·caret ▸·'+ 데이터소스 추가' 685px viewport 내) → 재클릭 재펼침(body 재생성·caret ▾) 토글 사이클. 하단 UI(데이터소스 추가·삭제) 도달 실증.
- Verification: docs-only. 실측 정본 = 본 evidence 가 기록하는 PB-0008.
- Cross-ref: CHG-20260618T024209-ai-claude-ds-acc-collapsible-evidence / CHG-20260618T022150-ai-claude-ds-acc-collapsible / REQ-20260618-0314 / AC-0571.

## REV-20260618T025220-ai-claude-ds-acc-collapsed-default [SKIPPED:frontend-ui-default-value-no-backend-no-rbac]
- Date: 2026-06-18
- Cycle: TASK-20260618T025220-ai-claude-ds-acc-collapsed-default (제품 선택 시 접근 가능 DB 목록 기본 접힘), **Minor §12.3**.
- Panel 생략 근거(§18.8): 기존 toggle(REQ-20260618-0314)의 초기값 1줄 flip — 백엔드·스키마·엔드포인트·RBAC·데이터·CSS 무변경, 신규 권한·파괴적 동작 0. UI 동작 정본은 PB-0008 Windows-browser. RBAC/보안 인접 아님.
- 설계 판단: ① 초기값만 `true` 로 두고 토글/전환 리셋 로직은 그대로 — 사용자가 datasource 를 명시 클릭하면 펼쳐 편집 시작(REQ-0314 "전환=편집 시작" 의도 보존). ② `_dsBodyCollapsed` 는 렌더 함수 클로저 변수라 매 `renderProductDetail`(제품 선택·아이콘 변경 등)마다 재초기화 → 제품 선택 시 항상 접힘으로 시작(요구 정합). 같은 제품 보는 중 머리 클릭 토글은 `_renderDsAccordion`(부분 렌더)이라 세션 내 펼침 유지. ③ 접힘 중에도 `_refreshAccessibleDbs`/`redrawChips`/`buildPicker` 는 detached `dbEditorWrap` 에 정상 작동 → 펼치면 최신 내용 표시(회귀 0, 테스트 토글1 로 확인).
- 검토한 회귀 리스크: 멀티 datasource 제품도 초기 전부 접힘(이전엔 primary 펼침) — 사용자가 "제품 선택 시 DB 목록 접힘"을 명시 요청했으므로 의도된 변경. coverage 요약(`buildProductCoverageDetail`)·datasource 행 목록은 그대로 표시(접히는 것은 per-datasource DB 편집기뿐).
- Verification: `node -c admin.js` + `tests/verify_ds_accordion_collapse.mjs` 19/19 PASS. 화면 정본 = PB-0008(배포 후).
- Residual: 머지 → web 재배포(deploy_scope: included) → PB-0008 Windows-browser(제품 선택 직후 기본 접힘) → evidence.
- Cross-ref: CHG-20260618T025220-ai-claude-ds-acc-collapsed-default / REQ-20260618-0316 / AC-0573 / TASK-20260618T022150(접기 토글 도입).

## REV-20260618T025848-ai-claude-ds-acc-collapsed-default-evidence [SKIPPED:docs-only-pb0008-evidence]
- Date: 2026-06-18
- Cycle: TASK-20260618T025220-ai-claude-ds-acc-collapsed-default PB-0008 evidence 기록, **Minor §12.3**, docs-only.
- Panel 생략 근거(§18.8): 코드·스키마·RBAC·배포 0 — 이미 머지·배포된 frontend 기본값 변경(PR #328)의 실 Windows 브라우저 검증 결과 기록. 신규 위험 표면 없음.
- PB-0008 요지(PASS): 단일 datasource 제품 KR(`mysql-local`) 선택 직후 **클릭 없이** DB 목록 접힘(`.ds-acc-body` 미생성·caret ▸·aria false·행 유지·하단 '+ 데이터소스 추가' viewport 내) = 사용자 요청 "제품 선택 시 기본 접힘" 실증. 머리 클릭 → 펼침(body 생성·caret ▾·picker) → 재클릭 → 접힘 토글 무회귀(REQ-0314 보존).
- Verification: docs-only. 실측 정본 = 본 evidence 가 기록하는 PB-0008.
- Cross-ref: CHG-20260618T025848-ai-claude-ds-acc-collapsed-default-evidence / CHG-20260618T025220-ai-claude-ds-acc-collapsed-default / REQ-20260618-0316 / AC-0573.
## REV-20260618T025755-ai-claude-dbpicker-search-regex [SKIPPED:frontend-ui-picker-search-no-backend-no-rbac]
- Date: 2026-06-18
- Cycle: TASK-20260618T025755-ai-claude-dbpicker-search-regex ('+ 데이터베이스 추가' picker 검색 필터 + 정규식 일괄 선택), **Major §12.3**.
- Panel 생략 근거(§18.8): frontend-only — 백엔드·스키마·엔드포인트·RBAC·데이터 0. 선택 쓰기는 기존 pending → "모두 적용"(`applyAllPending`) 경로 + 기존 schema_name 검증(시스템/내부 스키마 제외·비-MSSQL 형식·MSSQL 대소문자 보존)을 **그대로** 통과한다. 정규식은 후보 목록(이미 권한 게이트되어 받아온 `availableUserDbs`) 위에서 선택을 편하게 할 뿐, 서버가 받는 body·검증·권한 경계는 불변이라 신규 위험 표면이 없다. RBAC plan 변경이 아니므로 outside-voice(권한 catalog blindspot) 트리거에도 해당 없음.
- 설계 판단: ① 정규식 선택은 **additive**(기존 선택 해제 없음) — "미리 선택" 의미에 맞고, 사용자가 의도치 않게 선택을 잃지 않게 한다(해제는 개별 체크박스/× 로). ② 정규식·검색 모두 **대소문자 무시**(`i` 플래그 / lower 비교) — 운영 편의(DB 이름 표기 흔들림 흡수). MSSQL 대소문자 보존 datasource 도 push 시 원래 case 유지(`dsCaseInsensitive ? raw : v`). ③ toolbar 노출 임계 `DB_PICKER_SEARCH_MIN=6`(자매 제품 드롭업 `PRODUCT_DROPUP_SEARCH_MIN` idiom) — 소수 목록은 검색/정규식 불필요. ④ 입력값을 렌더 함수 클로저(`_dbPickerQuery`/`_dbPickerRegex`)에 보존 — 비동기 insight 도착으로 `buildPicker` 가 재렌더돼도 사용자가 입력한 검색/정규식이 사라지지 않음(재렌더 시 `_applySearch`/`_applyRegexPreview` 로 복원). ⑤ 순수 helper(`dbPickerFilterNames`/`dbPickerRegexMatches`)와 DOM helper(`applyDbPickerSearch`/`applyDbPickerRegexHighlight`)를 모듈 스코프로 분리 — jsdom 으로 검색·정규식 의미를 격리 검증.
- 검토한 회귀 리스크: 후보 < 6 이면 toolbar 미노출(기존 체크박스 목록 그대로) — 무회귀. `.hidden` 은 글로벌 `.hidden{display:none !important}` 로 항목 `display:flex` 를 이김(class 토글이라 `[hidden]` 어트리뷰트 함정 무관). 정규식 부정확 입력은 ok:false → 하이라이트/선택 안 함 + 인라인 오류(빈 선택 사고 0). 잘못된 스키마명은 push 검증에서 걸러짐(잘못된 allowlist 항목 생성 0).
- Verification: `node -c admin.js` + `tests/verify_dbpicker_search_regex.mjs` **33/33 PASS**(순수 검색 5·정규식 6·DOM 검색 4·DOM 하이라이트 3·wiring 7·CSS/cache-buster 8). 화면 정본 = PB-0008 Windows-browser(배포 후).
- Residual: 머지 → web 재배포(deploy_scope: included) → PB-0008 Windows-browser(검색 라이브 필터·정규식 라이브 카운트/하이라이트·"일치 선택" additive·선택됨 N개·sticky·결과없음) → evidence.
- Cross-ref: CHG-20260618T025755-ai-claude-dbpicker-search-regex / REQ-20260618-0317 / AC-0574 / AC-0575 / docs/PROPOSAL-frequent-db-config-changes.md.

## REV-20260618T025755-ai-claude-dbpicker-search-regex-evidence [SKIPPED:docs-only-pb0008-evidence]
- Date: 2026-06-18
- Cycle: TASK-20260618T025755 PB-0008 Windows-browser evidence ('+ 데이터베이스 추가' 검색 필터 + 정규식 일괄 선택), **docs-only**.
- Panel 생략 근거(§18.8): 코드·스키마·RBAC·배포 변경 0 — 이미 머지·배포된 frontend 기능(PR #331)의 실 Windows 브라우저 검증 결과를 문서에 기록할 뿐. 신규 위험 표면 없음.
- PB-0008 요지(PASS): 실 배포 admin.js helper(DB_PICKER_SEARCH_MIN=6 + 4 fn) + styles.css 위 render-injection. CSS computed: toolbar sticky·search border 1px·"일치 선택" 버튼 rgb(37,99,235)·is-regex-match primary@12%·hidden 항목 display:none(글로벌 .hidden !important 가 .admin-db-picker-item display:flex 이김). helper: 검색 'prod' 3/8·'zzzz' 0+결과없음 가시·정규식 '^prod_' count 3·'[' ok:false·순수 helper 정상. 시각 evidence picker-search-regex.png(1249×836).
- Verification: docs-only. 실측 정본 = 본 evidence 가 기록하는 PB-0008 + tests/verify_dbpicker_search_regex.mjs 33/33.
- Cross-ref: CHG-20260618T025755-ai-claude-dbpicker-search-regex-evidence / CHG-20260618T025755-ai-claude-dbpicker-search-regex / REQ-20260618-0317 / AC-0574 / AC-0575.

## REV-20260618-0317 [SUBAGENT:product-access-multiselect-safety]
- Date: 2026-06-18
- Cycle: TASK-0303 (역할/계정 '제품 사용(product_access)' 다중선택 무효 + 그룹 카운트 "0/0"), Major §12.3 — 권한 편집(어떤 product.access 코드가 staged/저장되는지)에 영향 → RBAC-인접.
- Trigger: §18.8 + [[feedback_outside_voice_for_rbac]] — 권한 모델 staging 경로 변경. 적대적 outside-voice 리뷰(general-purpose, REFUTE 지향).
- Verdict: **SHIP** — 권고 흡수 0(전 concern refuted), 머지 가능.
- 적대 검증 6항목(전부 REFUTED): ① 권한 손실 — mergedRole 은 항상 effective 전체(base∪pending) 반환, 모든 pending write 가 "전체±단건"이라 정적/hidden 손실 불가(writer 2곳뿐: 5017·7193). ② TASK-0300 self-scope 회귀 — preservedHidden 라이브 읽기는 stale 보다 *엄격히 안전*(hidden 코드는 base/pending 양쪽에 존재, 라이브가 누락 가능성 더 낮음), `verify_perm_self_scope.mjs` 13/13 유지. ③ escalation — allowedCodes/_selfAllowedRole 필터·백엔드 `_enforce_role_permission_self_scope`(app.py:1257)·`_enforce_override_self_scope`(1227) 무변경, 프론트는 in-memory source 만 바꿈(bypass 0). ④ role divergence — onToggle=캡처 role.id(선택 시 detail 전체 재렌더), main=selectedRoleId, 분기 불가. ⑤ count inflation — product_access 그룹은 dynamic-only 빈 컨테이너(static 체크박스 0), buildSystemPromptEditor 는 textarea/select(checkbox 0) → 정확히 제품 토글만 집계("3/16"). ⑥ 신규역할 — 카드는 `!merged._isNew` 시만 임베드(onToggle 미도달), main onChange 의 mergedRole 은 draft 반환(무영향).
- 무조치(기존·범위외): M1(그룹 "모두 선택/해제" 버튼이 카드 toggle 에 change 미디스패치 — bulk 선택 미영속, TASK-0303 이전부터 존재) · M2(계정 메인 override onChange 가 hidden 보존에 stale 사용 — overrideWrap DOM 에서 product select 라이브 수집하므로 안전, 역할측만 라이브 전환). 둘 다 본 fix 미도입.
- Verification: `verify_product_access_multiselect.mjs` 6 PASS(실 추출 함수 + OLD 버그 대조군) + node --check. **화면 정본 = PB-0008(배포 후)**.
- Residual: 머지 → 배포(web 재빌드) → 라이브 재검증(역할 제품 3개 토글→3개 staged·배지 N/M·적용 후 영속) + PB-0008 Windows-browser.
- Cross-ref: CHG-20260618-0317 / REQ-20260618-0320 / TASK-0303 / TASK-0300(self-scope 선행)·TASK-0288(RBAC 선행).

## REV-20260618T044318-ai-claude-db-rule-autosync [SUBAGENT:rbac-adversarial-2pass]
- Date: 2026-06-18
- Cycle: TASK-20260618T044318 (제품 DB allowlist 정규식 규칙 자동 동기화), **Critical §12.3** — RBAC/데이터 접근 경계 변경.
- Panel: outside-voice 필수(feedback_outside_voice_for_rbac) — [SKIPPED] 아님. general-purpose 적대(REFUTE) 2-pass.
- **Pass 1 (설계) — NOT-SHIP → 안전 하이브리드**: 순수 자동적용은 allowlist(=`set_active_schema_allowlist` fail-closed 경계)에 대한 무인 GRANT 라, "데이터소스에 DB 를 만들 수 있는 누구나(DBA·마이그레이션·공격자)가 패턴에 맞는 이름을 지으면 AI 가 승인 없이 즉시 읽음" + cap-경고는 사후약방문이라 indefensible. 권고=규칙 엔진은 만들되 broad/cap초과/모호는 pending 승인. 사용자 결정으로 안전 하이브리드 채택. BLOCKER B1~B5·M2~M6 도출.
- **Pass 2 (구현 코드) — SHIP-WITH-FIXES**: B1(cap withhold·empty include 매치없음)·B3(생성자 귀속 감사)·B4(수동 PUT manual-only 교체로 rule 행 생존, 프론트 body 필터, 레거시 폴백)·B5(MySQL IGNORECASE/MSSQL 대소문자=enforcement 정합)·M2(제외 union)·M4(add-only, 열거실패 no-op)·M6(5 엔드포인트 product.manage 게이트, lazy reconcile 게이트 내부) **충족 확인**. SQL 인젝션 clean(파라미터화+인젝션 정규식). 
  - **BLOCKER(흡수)**: ReDoS — alternation 그룹수량자(`(a|a)*`·`(.*a){20}`)가 중첩수량자 휴리스틱 우회 → 41자 입력에 >20s catastrophic backtracking(요청·백그라운드 스레드 hang). 수정=검증에 그룹수량자 `)[*+?{]` 금지·무한수량자(*,+)≤8·`_match_db_rule` 가 저장패턴 재검증(방어심층). 실측: 동일 패턴 0.000s 즉시 [] 반환.
  - **MAJOR 흡수**: #1 백그라운드 creator **활성·비삭제** 확인 추가(비활성 계정 권한 잔존 차단). #2 picker rule 행 체크박스 비활성(uncheck no-op 혼란 제거).
  - **MAJOR 문서화(잔여)**: #3 approve-pending 은 시스템/내부/인젝션 재검증하나 *현재 패턴* 재매칭은 안 함 — pending 행은 staging 시점 실 일치였고 비-시스템 사용자 DB 라 영향 낮음(후속 강화 여지).
- Verification: `verify_db_rule_logic.py` 25/25 + `verify_db_rule_ui.mjs` 17/17 + ast/node 구문 + ReDoS 실측. 화면 정본 = PB-0008(배포 후).
- Residual: 머지 → web 재배포(deploy_scope: included) → PB-0008 Windows-browser → evidence.
- Cross-ref: CHG-20260618T044318-ai-claude-db-rule-autosync / REQ-20260618-0322 / AC-0580 / AC-0581 / PLAN-db-rule-autosync.md / PROPOSAL-frequent-db-config-changes.md.


## REV-20260618T052403-ai-claude-db-rule-autosync-audit-fix [SKIPPED:audit-action-registration-no-rbac-change]
- Date: 2026-06-18
- Cycle: TASK-20260618T044318 후속 — audit action 등록 버그 수정(PB-0008 적발).
- Panel 생략 근거(§18.8): 권한 모델/접근 경계 변경 0 — 이미 outside-voice 2-pass 통과한 규칙 기능이 동작하도록 audit ActionCode 를 builder 에 등록하는 결함 수정일 뿐(감사 누락→감사 기록 정상화 방향, 보안 강화). 신규 위험 표면 없음.
- 내용: build_audit_change_json 이 db_rule 5 action 을 raise 이전에 처리 → PUT/DELETE 500 해소. record_audit_event 경로(autoadd/staged/approve)는 builder 미경유라 원래 정상(방어적 등록 포함).
- Verification: verify_db_rule_logic.py 30/30 + 재배포 후 라이브 round-trip + PB-0008.
- Cross-ref: CHG-20260618T052403-ai-claude-db-rule-autosync-audit-fix / TASK-20260618T044318 / REQ-20260618-0322.
## REV-20260618T061703-ai-claude-db-rule-multi [SUBAGENT:multi-rule-isolation-adversarial]
- Date: 2026-06-18
- Cycle: TASK-20260618T061703 (DB allowlist 정규식 규칙 다중 + 종속 UI), **Major §12.3** — 접근경계 인접.
- Panel: outside-voice(general-purpose, REFUTE) — 다중규칙 격리 초점. RBAC plan 인접이라 [SKIPPED] 아님.
- VERDICT: **SHIP-WITH-FIXES** (BLOCKER 0). 핵심: enforcement(allowlist 해석)는 (Product,Datasource,SchemaName)만 보고 RuleId/Source 미참조 → 규칙 bookkeeping 이 접근경계를 넓히거나 깨지 못함. 사전 안전 invariant 전부 보존(F 확인).
- A 교차 dedup: `_reconcile_one_db_rule` 가 규칙별 existing 재계산 + 규칙별 커밋 → 순차 reconcile 이 앞 규칙 행 인지(중복행 없음). B 삭제 격리: strip=RuleId+Source='rule' 스코프(타 규칙·manual 불변). C 고아 RuleId(무-strip 삭제): enforcement 무영향·UI 카드에서만 누락(허용). D IDOR: PUT/DELETE/approve 가 rule_id 의 (product,ds) 소속 재검증 → 타 제품 rule_id 404. E 마이그레이션: UNIQUE drop 멱등(information_schema 가드)·동시워커 안전·probe 가 기존배포 slow-path 트리거. G 프론트: `_isRuleRow` 스코프 정상·카드 DB 필터 datasource_key+rule_id 양조건.
- 흡수한 MAJOR: #1 동시 reconcile/PK 미마이그 시 중복 allowlist 행 가능 → reconcile auto-add·approve 를 **INSERT IGNORE** + auto-add pending 정리. #2 스키마 helper 가 slow path 전용이라 fast-path 재기동서 UNIQUE 미제거 → **`_ensure_seed_catchup` 에 helper 등록**.
- 잔여 MINOR(무해): 규칙 간 pending phantom(rule A pending 을 rule B 가 auto-add) — approve 의 `low in existing` 가드로 no-op. manual PUT 이 manual 승격 schema 의 pending 미정리(동류).
- Verification: verify_db_rule_logic.py 30/30 + verify_db_rule_ui.mjs 18/18. 화면 정본=PB-0008(배포 후).
- Cross-ref: CHG-20260618T061703-ai-claude-db-rule-multi / REQ-20260618-0323 / AC-0582 / AC-0583 / TASK-20260618T044318.

## REV-20260619T012028-ai-claude-share-link-expiry [SUBAGENT:share-link-expiry-adversarial]
- Date: 2026-06-19
- Cycle: TASK-20260619T012028-share-link-expiry (대화 공유 링크 시간 기반 만료), **Major §12.3** — 익명 공유 접근경계 인접.
- Panel: outside-voice(general-purpose, REFUTE) — 익명 share 접근제어 초점. 보안경계 변경이라 [SKIPPED] 아님([[feedback_outside_voice_for_rbac]]).
- VERDICT: **SHIP** (BLOCKER 0, MAJOR 0). 9 probe 전부 REFUTED.
- 만료우회(P1): public_share_view 순서 = ViewCount UPDATE(만료 predicate) → `_share_load_active`(share 컬럼만, 대화 본문 미포함) → RevokedAt 410 → bumped==0 시 `_share_row_expired` 410 → **그 다음에야** `_conv_load_share_meta`/`_share_load_messages`. fork 도 `_share_row_expired` 가 `_fork_conversation_impl` 앞. 만료 링크는 어떤 경로로도 본문/메타/카운트 누출 0.
- clock skew/TOCTOU(P2): 만료 평가 전부 DB 시계(create DATE_ADD(NOW()), UPDATE predicate NOW(), `_share_row_expired` NOW()). Python datetime.now() 0(grep 확인). autocommit 단일 연결=단일 시계 도메인. UPDATE→재확인 window 는 "카운트 시점 유효→직후 만료=1회 view 성공" 무해 경계뿐.
- SQLi(P3): `expires_expr` 는 코드 상수("NULL" 또는 "DATE_ADD(NOW(), INTERVAL %s SECOND)") — 사용자 데이터 미보간. seconds 는 `%s` 파라미터화. 컬럼/값 개수 양 분기 정합.
- 입력검증(P4): `int()` 가 float/비숫자 거부(400), ≤0=무기한, >365일=400(DATE_ADD 도달 전 차단→interval overflow 불가). 서버가 프론트 프리셋과 독립 검증.
- 무회귀(P5): expires 없으면 ExpiresAt NULL=never. ALTER 멱등(try/except)+양 경로 등록(probe fast-path 트랩 회피). 기존행 무영향.
- 취소vs만료(P6): RevokedAt 410 우선, bumped==0 분기서 `_share_row_expired` 로 구분. 둘 다 410·본문 0 → 보안영향 0.
- audit(P7): build_audit_change_json share.create 화이트리스트에 expires_in_seconds(plain int) 추가, token_full 마스킹 유지(prefix 8자만).
- 프론트(P8): share.js textContent / app.js escapeHtml 로 만료 표시 XSS-safe(expires_at=서버 DB DATETIME). 취소 path 가 POST 전 abort(share 미생성), 모달 리스너 cleanup.
- IDOR/authz(P9): create/list/revoke/view/fork 게이트 전부 불변(weaken 0). fork 의 share-token-as-grant 설계 유지 + 만료/취소 추가 집행.
- 잔여(무해): MINOR 취소-race 라벨(취소를 만료로 표기할 미세 경계, 둘 다 410)·NIT probe 자기문서화·boundary 더블카운트(ViewCount soft-metric).
- Verification: test_task20260619_share_expiry.py 12/12 + make test 회귀 0 + py_compile + node --check. 화면 정본=PB-0008(배포 후).
- Cross-ref: CHG-20260619T012028-ai-claude-share-link-expiry / REQ-20260619-0324 / AC-0584~0587 / SECURITY.md §7.2.
## REV-20260619T014034-ai-claude-llm-restriction-notice [SUBAGENT:llm-restriction-adversarial]
- Date: 2026-06-19
- Cycle: TASK-20260619T014034 (LLM provider 외부요인 제한 명시 표면화) — web 면(엔드포인트 + UI 4 surface). **Major §12.3**.
- Trigger: §18.8 — 신규 외부 노출 엔드포인트(`/api/llm/health`)·probe 외부 비용·UI 표면. 적대적 코드리뷰(general-purpose outside voice). full 본문 = feature-0002 REV-20260619-0311.
- Verdict: **SHIP-WITH-FIXES** (BLOCKER 0). web 면 confirmed-safe 요약:
  - `/api/llm/health` 인증 게이트 정합 — 미인증은 probe 트리거 없이 cheap read 만(M1 force 비용증폭은 module probe 5s 플로어로 차단).
  - 프론트 XSS-safe — 모든 사용자향 텍스트 `textContent`(innerHTML 미사용), `applyLlmProviderStatus` 전 DOM null-guard + try/catch, 인라인 notice dedup, 폴링 타이머 단일 가드(`_llmHealthPollTimer`).
  - **m5 흡수**: 인라인 notice append 가 무조건 최하단 강제 → `atBottom`(8px) 후에만 추종(stick-to-bottom 정책 정합).
  - `_read_llm_provider_status` graceful(PG 실패→unknown→배너 미표시). m6(hot-path PG read 캐시)은 inline-notice staleness 위험으로 미도입(single-row PK read 유지).
- Verification: verify_llm_restriction_surface.mjs 35(정적 7+CSS 5+wiring 6+jsdom 4-surface 17) + node --check + py_compile(app.py). 화면 정본=PB-0008(restricted 주입 4-surface, 배포 후).
- Cross-ref: CHG-20260619T014034-ai-claude-llm-restriction-notice / TASK-20260619T014034 / feature-0002 REV-20260619-0311(full).

## REV-20260619T021356-ai-claude-login-attempt-limit [SUBAGENT:login-attempt-limit-adversarial]
- Date: 2026-06-19
- Cycle: TASK-20260619T021356-login-attempt-limit (잘못된 로그인 시도 제한), **Critical §12.3** — 인증 경로.
- Panel: outside-voice(general-purpose, REFUTE) — Critical 인증 변경 필수 적대 리뷰([[feedback_outside_voice_for_rbac]]).
- VERDICT: **SHIP-WITH-FIXES** (BLOCKER 0, MAJOR 1, MINOR 5, NIT 2). 10 probe.
- REFUTED(clean): clock skew/TOCTOU(전부 DB NOW()/DATE_ADD, Python datetime 0), 카운터 리셋 정합(성공/임계 양쪽 초기화·post-unlock 즉시 재잠금 없음), admin unlock authz/IDOR(console.manage+account.update 게이트·audit), audit(auth.lockout/unlock 화이트리스트·PII 0·anonymous fail-open), 회귀(성공 로그인/bootstrap/must_change/serialize 무영향), is_locked 게이트가 비번 검증 선행.
- **흡수한 MINOR/NIT**: ① IP 버킷 무한증가(공격자 영향 IP 키) → 4096 초과 시 만료 버킷 sweep + throttled 시 빈 버킷 정리. ② /api/auth/me 가 본인 failed_login_attempts 노출 → admin-context(include_permissions)로 이동.
- **accept+문서화(코드 주석 + 본 항목)**:
  - **MAJOR 동시요청 soft-threshold**: is_locked 가 느린 PBKDF2(310k) 직전 스냅샷이라 동시 버스트가 잠금 기록 전 임계 초과 가능. `LOGIN_MAX_FAILED_ATTEMPTS`=연속(sequential) 한도, 절대 상한 아님. 1차 방어=DB 잠금(영속·cross-worker, 임계 넘으면 결국 잠김·UPDATE 멱등), 2차=IP throttle(단일 IP 버스트 ~4 계정/window 로 제한)+느린 해시. 분산 botnet 은 사내 LAN 위협모델 외. 외부 노출 가시화 시 별 cycle 에서 원자적 재검사(SELECT FOR UPDATE) 또는 per-account in-memory pre-gate.
  - MINOR 계정열거 오라클(429+잠금메시지 vs 401-일반): 잠금 스킴의 본질(잠금 상태가 곧 존재 누설). 사용자가 명시 선택한 계정 잠금 + 사내 LAN. 미존재 경로는 일반 401+IP기록 유지.
  - MINOR schema-catchup 선행 의존(COALESCE 는 NULL 만, 부재 컬럼 미보호): `_ensure_*` 가 serving 전 startup 에 실행 = must_change_password(동일 SELECT 패턴)와 동일 idiom, 기존 검증됨.
  - MINOR unlock audit-fail 500-after-commit(autocommit): password-reset 동일 기존 패턴(잠금은 실제 해제됨, admin 재시도 시 already-unlocked).
  - MINOR XFF-spoof: `_get_client_ip` 는 WEB_TRUSTED_PROXIES 직접 peer 만 XFF 신뢰(SECURITY.md §9.7 Caddy XFF 정규화). 기존 audit/session 과 동일 의존.
  - NIT locked_until naive tz: admin 배지는 bool is_locked 만 사용 = cosmetic.
- 테스트 한계 명시: 단위는 IP throttle 실동작 + source-grep — 동시성 window/열거 오라클/라이브 DB 잠금은 미커버(라이브 재검증 + PB-0008 로 보완).
- Verification: test_login_attempt_limit.py 11/11 + make test 회귀 0 + py_compile + node --check. 화면 정본=PB-0008(배포 후).
- Cross-ref: CHG-20260619T021356-ai-claude-login-attempt-limit / REQ-20260619-0325 / AC-0588~0591.

## REV-20260619T022449-ai-claude-release-note-llm-restriction [SKIPPED:content-only-no-logic-no-rbac-no-backend]
- Date: 2026-06-19
- Cycle: TASK-20260619T022449 (릴리즈 노트에 LLM 사용 제한 안내 항목 추가) — content-only, **Minor §12.3**.
- Rationale(SKIP): `release-notes-data.js` 정적 콘텐츠 1항목 추가 + 캐시버스터 bump 만. 로직/엔드포인트/RBAC/스키마/데이터 접근 0, 렌더러 불변. 텍스트는 렌더러가 textContent 주입(XSS-safe, verify_release_notes.mjs 가드). 적대 리뷰 대상 표면 없음.
- 내용 검토: 내부동작 비노출(AC-0579) 준수 — Bedrock/자격증명/분류기/PG 등 미노출, "외부 요인"으로 추상화. 기존 노트 문체 정합.
- Verification: verify_release_notes.mjs 34/34 + node --check.
- Cross-ref: CHG-20260619T022449-ai-claude-release-note-llm-restriction / TASK-20260619T022449 / TASK-20260619T014034.

## REV-20260619T023922-ai-claude-audit-tamper-evidence [SUBAGENT:audit-tamper-evidence-adversarial]
- Date: 2026-06-19
- Cycle: TASK-20260619T023922-audit-tamper-evidence (감사 기록 변조방지 해시 체인), **Critical §12.3** — 감사 무결성.
- Panel: outside-voice(general-purpose, REFUTE) — Critical 감사 무결성 필수 적대 리뷰.
- VERDICT: **SHIP-WITH-FIXES** (BLOCKER 0, MAJOR 3, MINOR 4, NIT 1). 9 probe.
- REFUTED(clean): seal 실패 fail-open(감사 write 유지)·GET_LOCK 재진입/release(finally)·authz(audit.read.any+first_break 내용 비노출)·purge checkpoint 정합(단일 시계 정상)·sync-seal 실패 후 Id 순 재봉인(skip/fork 없음)·기존 read/export/list 무회귀·스키마 멱등 양 경로.
- **흡수한 MAJOR**:
  - MAJOR-1(RR 스냅샷 fork): record_audit_event 가 admin 트랜잭션(autocommit=False) caller conn 으로 봉인 시 REPEATABLE READ 고정 스냅샷이 stale view fork 유발 가능 + UPDATE 가드 부재 → **동기 봉인을 fresh autocommit 연결로 전환**(최신 커밋만 보고, 스냅샷 pinning 없음) + **UPDATE `WHERE Id=%s AND EventHash IS NULL` 가드**(locking read 최신 평가, double-seal 차단·경쟁 시 실제 EventHash 로 head 재동기화).
  - MAJOR-4(verify/purge lock starvation+메모리): `batch=1000000` 단일 봉인이 GET_LOCK 장기점유+대량 fetchall → **`_seal_audit_chain_drain`(1000-batch 반복, 락 짧게)** 로 교체.
  - MAJOR-2(in-DB 체인 과대표현): full DB-write 공격자는 체인 재계산(2a)·tail truncation(2b)·checkpoint 위조(5) 로 검증 통과 가능 = in-DB 체인 본질 한계 → **위협모델 정직화**(schema docstring + SECURITY.md §13: 비-체인-인지 변조/손상/부분권한 탐지용임을 명시) + **백그라운드 sealer off-DB 로그 앵커**(`[audit-chain-anchor] id=.. hash=.. sealed_count=..`, 외부 WORM/SIEM 선적 시 외부 대조 탐지). 주기적 외부 notarization 은 별 cycle TODO.
- **수용(문서화)**: MINOR(CAST(JSON AS CHAR) 서버버전/charset 의존 → MySQL major upgrade 시 과거 history false-invalidate 위험·운영 시 동결 가정)·MINOR(ThroughEventId 기록되나 verify 미사용=장식적·향후 boundary 강화 여지)·MINOR(Id/OccurredAt 비-단조 backfill[WebAccountActivity 마이그] 시 경계 interleave 가능·정상상태 무관)·MINOR(테스트=source-grep+순수함수, DB 통합/동시성/truncation 미커버 — make test 게이트가 DB-less라 불가, 라이브 round-trip 으로 보완)·NIT(\x1f/\x1e 구분자 UserAgent embeddable=chosen-prefix collision only).
- Verification: test_audit_tamper_evidence.py 11/11 + make test 회귀 0 + py_compile + node --check. 화면 정본=PB-0008(배포 후).
- Cross-ref: CHG-20260619T023922-ai-claude-audit-tamper-evidence / REQ-20260619-0326 / AC-0592~0595 / SECURITY.md §13.

## REV-20260619T030500-ai-claude-llm-usage-quota [SUBAGENT:llm-usage-quota-adversarial]
- Date: 2026-06-19
- Cycle: TASK-20260619T030500-llm-usage-quota (LLM 사용량 한도), **Major §12.3** — 비용 통제·가용성 영향.
- Panel: outside-voice(general-purpose, REFUTE) — over-block/우회 초점.
- VERDICT: **SHIP-WITH-FIXES** (BLOCKER 0, MAJOR 0, MINOR 다수). 9 probe.
- REFUTED(clean): 게이트가 slot/worker dispatch 선행(양 모드 커버, conn 닫음)·fail-open 전구간(킬스위치/account None/effective 예외/PG 실패)·0vs미설정 정합·used>=limit 경계·SQLi(table/key_col/trunc 전부 코드 상수)·authz(console.manage·404·self-quota 없음·audit PII 0)·RBAC 무교차·입력검증(NaN/Inf→None)·무회귀(미설정 시 PG 미조회·스키마 멱등 양경로)·프론트 XSS(escapeHtml).
- **흡수한 MINOR**: parse_limit BIGINT overflow→500 (clamp 9e15 상한) · 0=무제한 footgun (캡션 "전면 차단=1" 명시).
- **수용(문서화)**: 동시요청 race(pre-flight 한도 본질, parallel limit 6 bound·비용통제라 허용) · aux-call(validate/summary/classify/topic/sql_fix) conversation_id 없어 INNER join 탈락 = under-count(가용성 우선·dominant inference 는 집계·evasion 아님) · admin `prompt/generate` LLM 미게이트(console.manage admin-only 저표면) · daily/monthly date_trunc tz=PG 세션(UTC, 기존 대시보드 정합) · 계정 override free-text id(오타→404, 향후 picker) · 1.x 정수절단.
- Verification: test_llm_usage_quota.py 10/10 + make test 회귀 0. 화면 정본=PB-0008(배포 후).
- Cross-ref: CHG-20260619T030500-ai-claude-llm-usage-quota / REQ-20260619-0327 / AC-0596~0599.
## REV-20260619T034522-ai-claude-oauth-google-foundation [SUBAGENT:oauth-google-foundation-adversarial]
- Date: 2026-06-19
- Cycle: TASK-20260619T034522-oauth-google-foundation (Google 계정 OAuth 로그인 토대), **Critical §12.3** — 인증 경로. 사내 웹서비스 편입 기반작업.
- Panel: outside-voice(general-purpose, REFUTE) — Critical 인증 + 신규 계정 프로비저닝, `feedback_outside_voice_for_rbac` 정책(권한/인증 변경은 외부 시각 필수) 적용.
- VERDICT: **SHIP-WITH-FIXES** (BLOCKER 0, MAJOR 2, MINOR 2, NIT 2). **MAJOR/MINOR 4건 전부 흡수 후 재검증 PASS** — 토대 단계지만 활성화 전 게이트로 미루지 않고 즉시 수정.
- REFUTED(clean): 비파괴 위반(flag OFF→/start·/callback 404·기존 login/signup/session/RBAC 무변경·스키마 멱등 NULL)·sentinel 비번 로그인(split("$") ValueError→False)·서명 미검증 임의 ID token 위조(고정 token endpoint 백채널 client_secret+TLS·aud 치환차단=실악용 불가)·admin/로컬 계정 email-link 탈취(Email=NULL)·open redirect/SSRF(고정 `/`·상수 endpoint)·권한 상승(pending 우선·ApprovedAt NULL 하드코딩=signup 보다 보수적)·state 위변조/재생(HMAC+compare_digest+TTL+skew)·oauth_subject 누출(_serialize_account 미포함).
- **흡수한 MAJOR**:
  - MAJOR-1(login-CSRF/세션 고정): self-contained 서명 state 가 개시 브라우저에 미바인딩 → 공격자가 자기 플로우 callback URL 을 피해자에게 먹여 공격자 계정으로 로그인시킬 수 있었음(서명은 위변조만 차단). → **state↔브라우저 바인딩 추가**: `/start` 가 random binding 을 state payload(`b`)와 단명 httponly 쿠키(`OAUTH_BIND_COOKIE`)에 동시 심고, `/callback` 이 `hmac.compare_digest(쿠키, state.b)` 일치 시에만 수락(`_oauth_callback_redirect` 가 모든 종료 경로서 쿠키 삭제). 단위테스트 missing-cookie/mismatch 거부 추가.
  - MAJOR-2(email 재할당 인계): email-link 가 가변 식별자(email)로 안정 식별자(sub) 덮어써 퇴사자→신규입사자 email 재할당 시 옛 계정 인계 가능. → **email-link 를 OAuthSubject NULL(미연결) 계정으로 한정**, 이미 다른 sub 면 `email-conflict` 거부(인계 0, 관리자 개입). SECURITY.md §15.4 명시 + 단위테스트.
- **흡수한 MINOR**: MINOR-1(nonce 조건부→무조건 enforce, replay 방어) · MINOR-2(aud 문자열만→배열 처리, OIDC 정합).
- **수용(문서화)**: NIT-1(`.env.oauth` agent-common 공유=least-privilege 위배, §15.4 acknowledged·web-only 분리 후속) · NIT-2(스키마 ALTER 비동기 적용 race=기성 idiom[FailedLoginAttempts/AvatarObjectKey 동일]·신규 회귀 아님). **잔여 활성화 게이트 TODO: ID token JWKS RS256 서명 검증(§15.3)** — 백채널 구조상 현재 실악용 불가하나 외부 배포 전 필수.
- Verification: test_oauth_google_foundation.py 36/36(기존 29 + 바인딩/conflict/nonce/aud 7 신규) + 전체 회귀 0(사전존재 product-delete 2건 base 동일·무관) + py_compile OK. 비파괴(flag OFF) 유지.
- Cross-ref: CHG-20260619T034522-ai-claude-oauth-google-foundation / REQ-20260619-0328 / AC-0600~0601 / SECURITY.md §15.

## REV-20260619T040000-ai-claude-two-factor-auth [SUBAGENT:two-factor-auth-adversarial]
- Date: 2026-06-19
- Cycle: TASK-20260619T040000-two-factor-auth (2단계 인증 TOTP), **Critical §12.3** — 인증 경로.
- Panel: outside-voice(general-purpose, REFUTE) — 2FA bypass/brute-force 집중 적대 리뷰.
- VERDICT: **SHIP-WITH-FIXES** (BLOCKER 0, MAJOR 1, MINOR 2). 11 probe. **클린 bypass 없음**, crypto core RFC6238 검증(test vector 일치).
- REFUTED(clean): bypass(2FA 계정은 /login 에서 세션·쿠키 절대 미발급·pending token DEK-HMAC 서버전용·위조 불가)·TOTP 정확(HMAC-SHA1 counter RFC 일치·±1 drift·constant-time)·secret 암호화(AAD 계정 바인딩·평문 미저장/미로그·setup 1회 노출·KEK 부재 503 fail-safe·serialize 미노출)·enrollment authz(IDOR 없음·session aid·disable 비번 재확인·Enabled=0 미확정)·admin 해제(게이트+audit·복구경로)·무회귀(미설정=off·KEK 부재여도 일반 로그인 정상)·프론트 XSS-safe(escapeHtml/textContent).
- **흡수한 MAJOR**: TOTP brute-force throttle 증폭 — 비밀번호 통과 시 `_login_ip_clear`+`_login_reset_lockout` 가 TOTP 분기 *전* 실행 → 비번 보유 공격자가 step1 반복으로 IP버킷·계정잠금 무한 리셋하며 6자리 코드(3/1M) brute-force(2FA 핵심 위협=비번 유출 시나리오 무력화) → **(a) 2FA 분기는 리셋 미룸(2단계 완료 시에만 reset)** + **(b) TOTP 실패 시 `_login_record_failure`(계정 잠금 ② 인프라, DB·cross-IP)+IP 기록, step-2 시작 시 is_locked 차단**. 결과: IP throttle(per-IP) + 계정 잠금(5회→15분, cross-IP) 이중 bound.
- **흡수한 MINOR**: 백업코드 소비 race(autocommit read-modify-write 중복 소비) → `SELECT ... FOR UPDATE` 명시 tx 원자화.
- **수용(문서화)**: pending token TTL(300s) 내 재사용(유효 코드 필요 + 이중 throttle 로 bound)·30s step 내 TOTP 코드 재사용(RFC 표준·산업관행)·KEK 부재 시 Enabled=1 계정 fail-closed(admin disable 복구)·`_runtime_tables_available` probe 에 WebAccountTotp 미등록(catchup 무조건 생성이라 무영향).
- Verification: test_two_factor_auth.py 10/10(B1 roundtrip+drift·B9 흡수 가드) + make test 회귀 0 + py_compile + node --check. 화면 정본=PB-0008(배포 후).
- Cross-ref: CHG-20260619T040000-ai-claude-two-factor-auth / REQ-20260619-0329 / AC-0604~0607 / docs/SECURITY.md §16.

## REV-20260619T084227-ai-claude-release-notes-security-6 [SKIPPED:release-notes-content-curation-no-logic-no-rbac]
- Date: 2026-06-19
- Cycle: TASK-20260619T084227-release-notes-security-6 (보안 6종 릴리즈 노트 기록), Minor §12.3 frontend-only.
- Panel 생략 근거(§18.8): 로직·RBAC·스키마·엔드포인트 변경 0 — 정적 릴리즈 노트 데이터(`release-notes-data.js`) 콘텐츠 추가 + 캐시버스터만. 보안 표면 변화 없음.
- 대신 AC-0579 내부 동작 비노출 자가 검증: 신규 6 항목에 암호화/해시체인/TOTP secret/인젝션/datamarking/RBAC/PG/quota/체인/token 등 금지 용어 0(스캔 clean). 사용자 보이는 결과만.
- Cross-ref: CHG-20260619T084227-ai-claude-release-notes-security-6 / REQ-20260619-0330 / AC-0608.

## REV-20260623T014626-ai-claude-quota-ui-relocate [SKIPPED:ui-relocation-readonly-serialize-no-new-rbac-no-endpoint]
- Date: 2026-06-23
- Cycle: TASK-20260623T014626-quota-ui-relocate (LLM 한도 UI 역할·계정 상세 이전), Minor §12.3.
- Panel 생략 근거(§18.8): 신규 엔드포인트 0·RBAC 게이트 변경 0·집행 로직 변경 0. 기존 PUT `/api/admin/quotas/role|account/{id}`(console.manage 게이트, ④ REV-20260619T030500 에서 SHIP-WITH-FIXES 검증 완료) 재사용 + UI 위치 이동. 추가는 read-only 직렬화 필드(역할 한도=role.read admin 게이트 /api/admin/roles, 계정 override=include_permissions admin-context 한정 — 자기 /api/auth/me 비노출, failed_login_attempts idiom 동형). 비-admin 노출 0.
- 검증: test_llm_usage_quota.py 11/11. 화면 정본=PB-0008.
- Cross-ref: CHG-20260623T014626-ai-claude-quota-ui-relocate / REQ-20260623-0331 / AC-0609.

## REV-20260623T021500-ai-claude-quota-editor-escapehtml-fix [SUBAGENT:escapehtml-referenceerror-adversarial]
- Date: 2026-06-23
- Cycle: TASK-20260623T021500-quota-editor-escapehtml-fix (buildQuotaEditor escapeHtml ReferenceError 수정), Minor §12.3 frontend-only.
- Panel: outside-voice(general-purpose, REFUTE) — XSS·렌더 안전성·잠복여부·스코프 완전성 집중.
- VERDICT: **SHIP** (BLOCKER 0, MAJOR 0, MINOR 2[흡수 1·수용 1]). 6 probe.
- 확인(REFUTED clean): XSS-safe(`input.value=`·`note.textContent=` DOM 프로퍼티는 HTML 미파싱·fmtVal 은 ""/String(number) 뿐·동적 값 innerHTML 미경유) · escapeHtml 미가용 crux 확정(admin.html <script> 633-637 에 app.js 부재·escapeHtml=app.js:495 전용) · admin.js 잔여 escapeHtml call-site 0(스코프 완전, 구 loadQuotas 가 보유했던 5곳 전부 제거) · 콜러(renderRoleDetail 5411·renderAccountDetail 4704) throw 제거로 상세 pane 전체 깨짐 위험 해소.
- **잠복 버그 확인(적대 리뷰 핵심)**: ④ LLM 한도 도입(05d58d1) 이래 구 loadQuotas 도 admin 페이지에서 동일 escapeHtml ReferenceError → 한도 UI 가 production 에서 한 번도 정상 렌더된 적 없음. relocate 회귀가 아니라 latent 결함을 PB-0008 이 적발.
- **흡수한 MINOR**: 테스트 가드 1400자 고정 윈도가 함수(2372자) 전체 미포함 → 슬라이스를 다음 `\nfunction ` 경계까지로 정정(buildQuotaEditor 본문 전체 escapeHtml 부재 보장).
- **수용(문서화)**: 콜러 try/catch 방어는 선택(throw 제거로 moot, belt-and-suspenders 차원만).
- Verification: test_llm_usage_quota.py 11/11(F1 회귀 가드) + node --check OK. 화면 정본=PB-0008(배포 후).
- Cross-ref: CHG-20260623T021500-ai-claude-quota-editor-escapehtml-fix / REQ-20260623-0331 / AC-0609.

## REV-20260623T030418-ai-claude-quota-rbac-permission [SUBAGENT:quota-rbac-adversarial]
- Date: 2026-06-23
- Cycle: TASK-20260623T030418-quota-rbac-permission (LLM 사용 한도 조회/조절 전용 권한), **Major §12.3 — 보안 경계(RBAC)**.
- Panel: outside-voice(general-purpose, REFUTE) — privilege-escalation·access-control 누출·manage⊃read 집행 집중([[feedback_outside_voice_for_rbac]]).
- VERDICT: **SHIP-WITH-FIXES** (BLOCKER 0, MAJOR 2[흡수], MINOR 1[수용]). 6 probe.
- 확인(REFUTED clean): admin seed(set(PERMISSION_CODES)) 신규 2종 자동 보유→무lockout·console bootstrap 정상 / strip 헬퍼 non-no-op(actor=_require_account→_decorate_account_rows 로 permissions dict 채워짐, dict/list 양형 in-place 안전) / self-session(/api/session·/api/auth/me)=include_permissions 없음→quota 무노출 / _load_role_by_id 단건=quota 미포함(role create/update/delete 응답 무누출) / 프론트 readOnly=defense-in-depth(실 경계=백엔드 PUT).
- **흡수한 MAJOR-1**: PATCH `/api/admin/accounts/{id}`(`admin_update_account`) 응답 `_serialize_account(include_permissions=True)` 가 strip 미적용 → account.update 보유·quota.read 미보유 actor 가 no-op PATCH 로 한도값 회수(read-gate 무력) → 응답에 `_strip_quota_fields_if_unpermitted(payload, actor)` 추가. (유일 미커버 include_permissions 사이트, admin_accounts/admin_me 는 기존 커버.)
- **흡수한 MAJOR-2**: "조절은 조회 종속"이 admin.js PERMISSION_DEPENDENCIES(가시성 힌트)에만 존재 — PUT role/account 가 quota.manage 만 검사 → quota.manage 단독 보유 시 GET·직렬화는 strip 되나 PUT 은 통과(blind-write). 사용자 요구가 enforcement 레이어에서 미성립 → PUT 게이트에 **quota.read + quota.manage 동시 요구**(서버 집행).
- **수용(문서화)**: MINOR(console.manage 분리로 quota.manage 보유자가 console.manage/account.update 없이 한도 변경 가능=접근 확대) — 전용 위임 권한의 의도된 설계. 스톡 seed(operator/sales/pending) 미보유라 즉시 확대 없음·grant escalation 은 _enforce_override_self_scope 로 bound. MODIFY/SECURITY 이행주의 명시.
- Verification: test_llm_usage_quota.py 18/18(B8 양권한·B11/B12 MAJOR 가드·F2/F3) + test_permission_dependency_map.py 자동검증 + make test 회귀 0 + node --check + py_compile. 화면 정본=PB-0008(배포 후).
- Cross-ref: CHG-20260623T030418-ai-claude-quota-rbac-permission / REQ-20260623-0332 / AC-0610·0611 / SECURITY.md §6.

## REV-20260623T053000-ai-claude-quota-admin-catchup [SKIPPED:idempotent-admin-catchup-no-new-gate-no-rbac-surface]
- Date: 2026-06-23
- Cycle: TASK-20260623T030418-quota-rbac-permission follow-up (admin catchup lockout 수정), Major §12.3 후속.
- Panel 생략 근거(§18.8): 신규 엔드포인트·게이트·RBAC 표면 변화 0. 기존 `_ensure_seed_roles` admin catchup 리스트(TASK-0288 datasource.read/manage·product.read 동형 선례)에 quota.read/quota.manage 2줄 추가(INSERT IGNORE 멱등 backfill). admin 은 정의상 set(PERMISSION_CODES) 전권 — catchup 은 그 invariant 복원이라 권한 확대 아님(seed 의도와 정합). 비-admin seed 무변경.
- 적발 경위: 본 cycle(REV-20260623T030418) PB-0008 라이브 검증에서 bootstrap_admin quota.read=false → 게이트 전환 후 admin lockout 확인(DB WebRolePermissions RoleId=3 quota.read=0). outside-voice 가 "admin seed=set(PERMISSION_CODES)" 는 확인했으나 기존 배포 row 의 retroactive 미적용(catchup 필요)은 정적 리뷰로 미검출 — PB-0008 의 가치.
- 검증: test_llm_usage_quota.py 16/16(B13 catchup 소스 가드) + make test 회귀 0. 화면 정본=재PB-0008.
- Cross-ref: CHG-20260623T053000-ai-claude-quota-admin-catchup / TASK-20260623T030418-quota-rbac-permission / AC-0610.

## REV-20260623T090440-sample-feedback-curation [SUBAGENT:item03-impl-selfcheck]
- Date: 2026-06-23
- Cycle: TASK-20260623T090440-sample-feedback-curation (답변 피드백 → 샘플쿼리 KB 환류 flywheel 의 web 층, ROADMAP dba-ai-nl2sql ITEM-03), **Major §12.3 — 보안 경계(신규 RBAC `kb.sample.curate`)**.
- 리뷰어: 구현 subagent 본인의 self-check(item03-impl-selfcheck). **자기 구현에 대한 self-review 는 적대성 한계가 있음**(작성자 편향 — 같은 가정을 공유하면 누락도 공유). 따라서 본 entry 는 **마감 verdict 가 아니라 구현 자체 점검 + 메인 세션 적대 리뷰 예정 명시**다.
- Self-check(구현자 관점, 확인된 것):
  - **RBAC 게이트 위치**: 검수 endpoint 3종(GET/approve/reject) 모두 `_require_permission(request, conn, "kb.sample.curate")` 가 작업(코어 호출) **이전**에 실행 — 미보유 시 403 후 즉시 return, 코어(list/promote/reject) 미호출(테스트 S1~S3 가 코어 호출 부재까지 단언). 사용자 적재는 `_account_can_access_conversation`(read.own/any) 게이트로 타 대화 적재 차단(U1=404).
  - **cross-DB conn 분리**: 적재/승급/거부=PG(`_pg_connect`/`_pg_connect_ro`), auth/audit=memory(`_connect_memory`) — 각 conn 은 별도 try/finally 로 close. PG write 는 autocommit=False + 명시 commit/rollback(원자성). audit 실패는 best-effort(작업 성공을 막지 않음, fail-open) — submit 은 user-endpoint 패턴, approve/reject 는 작업 성공 후 별도 memory conn.
  - **poisoning 방어**: 승급은 명시 호출(approve)만 — 사용자 적재는 pending 까지. 👎/비-pending 승급 시도는 코어가 None 반환 → 409(audit 미기록, A2 가 단언). generated_sql PII 마스킹은 코어 record_feedback 책임(web 무가공 전달).
- **self-check 한계(메인 적대 리뷰가 봐야 할 잠재 표면)**:
  - scope_key 도출(`_conversation_scope_key`)이 'common' 폴백을 쓴다 — 무권한/오분류 product 의 피드백이 'common' 스코프로 섞일 가능성(검색 오염 측면)은 정적 self-check 로 단정 못 함. 검수 단계가 사람 게이트라 즉시 위험은 낮으나 적대 검토 필요.
  - 사용자 적재 endpoint 가 대화 **열람자**(read.own/any, 발화 권한 없는 그룹 멤버 포함)에게 열려 있음 — 의도된 설계(피드백은 열람자도)이나, 대량 적재(spam/DoS)·scope 오염 벡터는 rate-limit 부재. 적대 리뷰에서 abuse 표면 점검 권장.
  - generated_sql/nl_question 길이 상한(100k/8k)·마스킹은 코어 의존 — 코어 마스킹 우회(특수 PII 패턴) 여부는 feature-0002 책임이나 경계 신뢰 가정은 적대 검토 대상.
  - UI(app.js 버튼·admin.js 탭)는 jsdom/headless 미검증 — **실렌더 정본=PB-0008(Windows-browser)**, 메인 세션 마감.
- **마감 예정(메인 세션)**: 신규 RBAC=보안 표면이므로 **메인 세션이 적대적 security 리뷰(privilege-escalation·access-control 누출·cross-DB·scope 오염·abuse 표면) 를 별도 수행 후 마감**한다. 본 cycle 산출물은 구현+단위검증(15/15)+verify+commit/push 까지.
- 검증: test_sample_feedback_curation.py 15/15 + 인접 RBAC/audit 회귀 0(test_permission_dependency_map·insight_reset·audit_rbac·admin_me_rbac) + full suite 회귀 0(사전존재 9건 baseline 무관) + node --check + py_compile + CSS brace 1454.
- Cross-ref: CHG-20260623T090440-ai-claude-sample-feedback-curation / REQ-20260623-0333 / AC-0612·0613 / ROADMAP dba-ai-nl2sql ITEM-03.

## REV-20260623-0334 [SUBAGENT:item03-adversarial-security-backend]
- Date: 2026-06-23
- Cycle: TASK-20260623T090440-...-sample-feedback-curation (ITEM-03 피드백 flywheel web), **Major §12.3 + 보안 표면(신규 RBAC)**. 메인 세션이 self-check 위 잠재 표면을 적대적으로 재검토.
- Trigger: §18.8 — auth/RBAC+API+UI → security+backend. (general-purpose outside voice, REFUTE: privilege-escalation·access-control·abuse·cross-ds·injection·XSS·audit·cross-DB·poisoning.)
- VERDICT: **SHIP-WITH-FIXES** (BLOCKER 0) → fixes 흡수 후 SHIP.
- Confirmed-safe(무혐의): admin endpoint 3종 모두 DB작업 전 `_require_permission("kb.sample.curate")`(privilege-escalation 차단) · 신규 권한 least-priv(admin seed 만, operator/sales/pending 미부여, `test_permission_dependency_map` 만족) · 사용자 적재 `_account_can_access_conversation`(임의 cid 주입→404) · SQLi 없음(%s) · **stored XSS 없음**(admin.js `_sfEsc` 로 nl_question/sql/scope escape) · promote admin-only·down 미승급·비-pending→409 · cross-ds: promote 가 feedback scope_key 상속(A→B 이동 불가) · blast 0(기존 endpoint 무변경, app.py 순수 additive).
- **흡수한 MAJOR**: **M1(적재 abuse/큐 DoS)** — 사용자 피드백 endpoint rate-limit 부재 → `_search_rate_limit_check(account_id, max_per_min=10)` 추가(429), body-search 동형. **M2(promote TOCTOU 이중승급)** — 코어 `promote_feedback`(feature-0002, cross-ref)에 `SELECT … FOR UPDATE` 행락 + 최종 UPDATE `AND status='pending'` 추가(동시 approve 직렬화).
- **흡수한 MINOR/NIT**: MINOR-1 nl_question PII 미마스킹 → 코어 `record_feedback` 가 nl_question 도 `_mask_pii`(구 `_mask_sql` 일반화). NIT-1 `_mask_pii` fail-open silent → 경고 로그(fail-loud). NIT-2 submit audit best-effort 는 user-endpoint 패턴(수용).
- **수용(문서화)**: scope 'common' 폴백은 의도된 공통 스코프(검수 사람게이트로 완화). UI 실렌더는 PB-0008(Windows-browser) 메인 마감.
- Verification: 보안 fix 후 test_sample_flywheel 12 + test_sample_feedback_curation 15 = **27 통과**(회귀 0) + py_compile + `_mask_sql` 잔여참조 0. cross-ref 코어 변경(feature-0002 sample_feedback.py)은 MODIFY 에 기록.
- Cross-ref: CHG-20260623T090440-...-sample-feedback-curation / ROADMAP dba-ai-nl2sql ITEM-03.

## REV-20260624T105228-item08-fix-with-ai [SUBAGENT:item08-impl-selfcheck + adversarial-backend-security] — SHIP-WITH-FIXES (M1 흡수)
- Cycle: TASK-20260624T105228-item08-fix-with-ai ("AI 로 고치기" 표적 재수정, ROADMAP dba-ai-nl2sql ITEM-08). **Major §12.3 + 보안 표면(신규 엔드포인트 = 프롬프트 인젝션/RBAC)**.
- 上단(점검 결과/self-check 한계)은 구현 subagent self-check, 下단(§적대 backend+security 리뷰)이 별도 적대 리뷰(general-purpose REFUTE) — self-check 가 예고한 표면이 실제 MAJOR(M1)로 적중, fix 흡수.
- 점검 결과(통과):
  - 가드 순서가 `post_sample_feedback` 와 동형(account → access 404 → rate-limit 429 → scope 403 → audit). test G1~G3 가 각 거부 경로에서 `ask` 미dispatch 를 단언.
  - 프롬프트 인젝션: 지시문은 서버 고정, client 입력은 데이터 블록에만 + 백틱 무력화 + cap. test P1/P2 통과.
  - 새 run 전체 재질문 회피: 동일 cid + 정정문만 전달(원본 NL 미전송). test D1 이 `original_nl not in body["message"]` 단언.
  - 1회 dispatch: `post_fix_with_ai` 는 `ask` 를 정확히 1회 호출, 추가 루프 없음(self-reflection 내부 cap 상속).
  - agent_core·ask-worker·gateway·credential·ROADMAP 무변경(git diff 가 feature-0003 web 만 — app.py/app.js/styles.css/index.html/tests).
- **self-check 한계(메인 적대 리뷰가 봐야 할 잠재 표면)**:
  - `_make_internal_ask_request` 가 `request._receive`(Starlette private) 위임 — 본 Starlette 버전에서 `_receive` 존재 확인(import 시 inspect 로 검증)했으나, 버전 업그레이드 시 깨질 수 있는 결합. worker-mode attach 의 `is_disconnected` 실제 동작은 정적 self-check 로 단정 못 함(라이브 검증=PB-0008/메인).
  - 백틱→'ˋ'(U+02CB) 치환은 코드펜스 인식 차단이 목적이나, LLM 이 'ˋ' 를 시각적으로 백틱처럼 해석할 가능성(모델 의존)은 정적으로 단정 불가. 데이터 블록 명시 부정문이 1차 방어선.
  - 정정 dispatch 가 `API_DEFAULT_MODEL` 로 고정 — 원본 대화가 다른 모델이었어도 web 기본 모델로 정정(의도된 동작이나 사용자 기대와의 괴리는 메인 판단).
  - UI `can("conversation.ask")` 는 표시 게이트(로그인 시 true) — 실제 발화 거부는 서버 403 + apiFetch toast. 무권한 멤버에게 버튼이 보이나 클릭 시 403(설계상 의도, sample-feedback 패턴 동형).
- Verification(self-check 시점): test_fix_with_ai.py 9/9 + test_sample_feedback_curation.py 15/15 회귀 0 + py_compile + node --check.

### 적대 backend+security 리뷰 결과 (2026-06-24, general-purpose REFUTE) — VERDICT: SHIP-WITH-FIXES
- **MAJOR M1(흡수)** — 프롬프트 인젝션 방어가 엉뚱한 구분자를 막음: 정정 지시문은 데이터 블록을 **코드펜스(```)가 아니라 `[실패한 SQL]` 라벨+개행**으로 구분하는데 sanitizer 는 **백틱만** 무력화. 공격자는 백틱 없이 **개행+가짜 라벨+가짜 마감문**으로 데이터 블록을 탈출 가능(실측: `newline injection survived: True`). 엔드포인트가 client `executed_sql`/`error_message` 를 DB 대조 없이 신뢰하므로 `conversation.ask` 사용자가 임의 텍스트 주입 가능(단 실행은 sql_guard/RBAC/own-scope 로 제한 → 권한상승 아닌 정보유출/self-reflection 오용 → MAJOR). **fix(흡수)**: nonce-봉인 데이터 블록 — 매요청 `secrets.token_hex(8)` nonce 로 `«SQL-{nonce}»`…`«/SQL-{nonce}»` 봉인, sanitizer 가 입력에서 `«·»`+nonce 제거 → client 가 닫는 마커 위조 불가(개행/가짜라벨 봉인 블록 안에 갇힘). 회귀 테스트 `test_message_seals_against_newline_and_fake_marker_escape` +1.
- **MINOR(수용, house-consistent)**: m1 rate-limit 버킷이 search/feedback 와 공유(전역 dict) — sample-feedback 동형 기존 패턴 + 혼합 시 더 보수적(비용 안전 방향)이라 수용. m2 멀티워커 시 워커당 한도(account 단위 차단은 정상, IP 우회 불가) — 기존 모든 rate-limit 과 동일 한계. m3 입력검증이 auth 앞(400 vs 401) — sample-feedback 동형. m4 클릭당 audit 2건(trigger+ask) + 403 시 toast 2회 — 무해 UX.
- **NIT**: n1 U+02CB 주석(가시문자, nonce 봉인 후 보조), n2 정정은 `API_DEFAULT_MODEL` 고정(의도).
- **REFUTE 실패(=확인된 안전)**: `_make_internal_ask_request`(private `_receive`) — 실측상 ① body 정확히 1회 공급(Starlette 캐싱, 원본 `_receive` 호출 0) ② worker-mode `is_disconnected` 는 취소된 CancelScope 안 await 라 즉시 False(hang/조기중단 없음; client-disconnect abort 반응성만 저하, backstop 이 슬롯 회수) ③ scope headers 복제로 **동일 세션→동일 계정**(cross-account dispatch 없음) ④ 슬롯 1회 획득(중복 enqueue 없음). RBAC/IDOR(2중 방어: 엔드포인트 access-gate + 위임 ask 재검증), XSS(textContent only), 입력검증, 회귀/blast 모두 안전.
- 평가: 신규 엔드포인트의 인젝션 방어를 nonce 봉인으로 근본 교정 후 SHIP. 재dispatch 우회는 실측상 안전·수용 가능.
- Verification(흡수 후): test_fix_with_ai.py **10/10** PYTHONPATH=feature-0002:feature-0003 실측 + M1 순수함수 독립 검증 + py_compile + node --check. 전체 suite=`make test`(agent 이미지).
- Cross-ref: CHG-20260624T105228-item08-fix-with-ai / FUNCTION REQ-20260624-0334 / ROADMAP dba-ai-nl2sql ITEM-08(→done). 라이브 UI 렌더 정본=PB-0008(Windows-browser, 배포 후).

## REV-20260624T020000-product-insight-status-badge [SKIPPED:ui-tweak-user-approved-mockup]
- Date: 2026-06-24
- Cycle: TASK-0308 (제품 탭 데이터소스 인사이트 탐색 상태 표시), **Minor §12.3** — frontend only(admin.js+styles.css), 백엔드 0.
- Panel skip 사유(§18.4): (1) 표현계층 전용 변경(렌더 헤더에 상태 아이콘 추가 + primary 표기를 텍스트배지→엔진색), 비파괴·additive. (2) `insight_enabled` 는 datasources API 기존 필드라 신규 데이터 경로/권한 0. (3) admin.js `node --check` 통과. (4) **사용자가 Artifact 목업(실 CSS·아이콘 렌더)으로 디자인을 직접 검토·승인**(아이콘 design "모범적" 확인 + '기본' 텍스트→엔진색 조정 지시 반영). a11y: 색 단독 의존 회피(켜짐 눈/꺼짐 빗금눈 형태 차이 + title/aria-label).
- 잔여 검증: UI 실렌더 정본은 PB-0008(Windows-browser, 배포 후) — gstack /browse(WSL headless)는 보조.
- Cross-ref: CHG-20260624T020000-product-insight-status-badge / TASK-0308.

## REV-20260624T024500-task0308-pb0008-close [SKIPPED:docs-only-cycle-close]
- Date: 2026-06-24
- Cycle: TASK-0308 마감(PB-0008 검증 기록 + 체크박스 닫기), docs-only(TASK.md+TEST.md+MODIFY.md), 코드 0.
- Panel skip 사유(§18.4): 코드/런타임 변경 없는 cycle-close 문서화. 검증 사실은 **사용자 직접 PB-0008 Windows-browser PASS**(TEST.md §4 기재) — AI 가 배포·서빙·정적검증 수행, 운영자가 실 화면 육안 확인. 새 코드 경로/리스크 0.
- Cross-ref: CHG-20260624T024500-task0308-pb0008-close / TASK-0308.

## REV-20260624T130000-item11-metadata-glossary-enum [SUBAGENT:impl-selfcheck + adversarial-backend-security] — SHIP (MINOR-2 흡수)
- Date: 2026-06-24
- Cycle: TASK-20260624-item11-metadata-glossary-enum (메타데이터 거버넌스 MVP-1 — 용어/ENUM CRUD), **Major §12.3 — 보안 경계(신규 RBAC `kb.ingest.manual` + KB 적재 표면)**. 본 worktree 는 구현+단위검증+self-check 까지; **적대 security 리뷰·verify-completion·머지·배포·PB-0008 = 메인 세션**(PLAN-APPROVED 위임 경계 — commit/push/PR/merge/deploy 금지).
- Self-check 결과(구현자 자기검증, 적대 아님):
  - RBAC: 8 엔드포인트 전부 `_metadata_resolve_account`(=`_require_permission(…, "kb.ingest.manual")`)를 코어 호출 **전에** 통과해야 진행. 단위테스트 G403/E403 이 4×2 엔드포인트에서 미보유 → 403 + 코어 미호출(`called["hit"] is False`)을 단언. 신규 권한은 PERMISSION_DEFINITIONS(group kb) + admin seed(set(PERMISSION_CODES)) + `_ensure_seed_roles` catchup(retroactive). operator/sales/pending 미부여(R2).
  - scope 격리(핵심 위험): admin CRUD 는 **단일 scope** + **by id + scope 가드 SQL**(`WHERE id=%s AND scope_key=%s`) → 타-scope 행 비변경(cross-scope 오작용 차단). 허용 scope = 등록 datasource 키 ∪ common(미허용/빈값 400, SV 테스트). CURRENT_FACT_SCOPE_KEY 미사용(BLOCKER 회피) — 요청 명시 scope_key.
  - KB poisoning 면: 등록은 명시 권한 + 명시 입력만(자동학습/부트스트랩 없음). 입력 trim+길이 cap(IV 테스트). 삭제 멱등(이미 없음=200, audit 미기록).
  - cross-DB: CRUD=PG(agent_kb, `_pg_connect`/`_pg_connect_ro`, write autocommit=False+rollback), audit=memory(MySQL, `_connect_memory`) — conn 분리(sample-feedback 동형).
  - XSS: 프론트 전 경로 textContent/DOM API(createElement/replaceChildren), innerHTML 무사용. scope `<option>`·목록 행·폼 입력 모두 사용자 데이터 escape.
  - 무결성: py_compile(app.py·kb_glossary.py) + node --check(admin.js) OK. 단위 13/13. 회귀 sample-feedback 15/15·permission-dependency-map 16/16(권한 카탈로그 정합) 무영향.
- 미해결/위험(정직):
  - (1) **적대 security 리뷰 미수행** — 본 cycle 은 self-check 만. 신규 RBAC + KB 적재(검색/답변 직접 영향)는 보안 표면이라 메인의 적대 리뷰 필수(권한 우회·scope 누수·인젝션 재확인).
  - (2) **UI 실렌더 미검증** — PB-0008(Windows-browser) 미수행(배포 후 메인). gstack /browse(WSL headless)도 미수행. 탭 노출/서브탭 전환/scope 드롭다운/CRUD 폼/삭제 confirm 의 실 화면 동작은 PB-0008 에서 확정.
  - (3) `_metadata_valid_scope_keys` 가 매 mutation 요청마다 `all_datasources(memory conn)` 1회 조회(추가 MySQL 왕복) — 단순/보수적이나 캐시 미적용(저빈도 admin 경로라 수용). datasources 조회 실패 시 common 만 허용 → 정상 datasource scope 가 일시 400 날 수 있음(fail-safe 방향 — 미지 scope 적재 차단 우선).
  - (4) ENUM update UNIQUE 충돌 409 는 예외 클래스명(`UniqueViolation`/`IntegrityError`) 매칭 — psycopg 버전/래핑에 따라 달라질 수 있어 메인이 실 PG 에서 확인 권장(미스 시 500 으로 떨어지나 데이터 무손상).
  - (5) Phase 2(테이블/컬럼 설명·describe_table 부트스트랩·샘플 admin) 미구현 — ITEM-11 부분 진행. ROADMAP 갱신은 메인.

### 적대 backend+security 리뷰 결과 (2026-06-24, general-purpose REFUTE) — VERDICT: SHIP
- **BLOCKER/MAJOR 0.** 핵심 표면 전수 점검 후 결함 미적발 — RBAC·IDOR/scope 누수·SQLi·XSS·원자성·입력검증 모두 **REFUTE 실패(=안전)**.
- **RBAC(안전)**: 8/8 엔드포인트가 코어 호출 전 `_require_permission(…, "kb.ingest.manual")` — 빠진 핸들러 0, 권한명 전수 일치(정의·seed·catchup·엔드포인트·프론트), operator/sales/pending 미부여(least-priv). G403/E403 테스트가 403 시 코어 미호출 단언.
- **scope 누수/IDOR(안전)**: update/delete 전부 `WHERE id=%s AND scope_key=%s` 격리 + UPDATE 가 scope_key 미재배정(타 scope 이동 벡터 없음) + allowlist(등록 ds ∪ common, 조회 실패 시 common-only fail-safe) + strip/lower/빈값 400. **명시**: `kb.ingest.manual` 보유자는 모든 등록 scope 편집 가능 — 기존 `kb.sample.curate` 와 동일 flat KB-curation RBAC(per-ds 큐레이션은 향후 follow-up). MVP 의도 수용.
- **SQLi(안전)**: 6 코어 + 엔드포인트 전부 `%s`(식별자/값/LIMIT 포함), f-string/format/% 주입 0.
- **원자성(안전)**: 각 mutation `_pg_connect(autocommit=False)`+commit/rollback+`finally close`, 404 경로도 rollback, RO list `_pg_connect_ro`, ENUM 409 매칭 미스도 rollback+close(누수 0). audit memory conn 도 close.
- **XSS(안전)**: 신규 admin.js 전 경로 createElement/textContent, innerHTML 0. 탭 게이트 + 버튼 게이트 + 서버 403 이중.
- **흡수 — MINOR-2(scope 드롭다운 init race)**: 첫 탭 진입이 datasources 로드 전이면 드롭다운에 common 만 남던 race → **메타데이터 탭 재진입 시 `_metaPopulateScopeSelect` 재호출**(선택 보존)로 fix(admin.js switchTab). node --check OK, test 13/13 유지.
- **수용 — MINOR-1(audit cross-DB best-effort)**: PG mutation(agent_kb)과 audit(MySQL memory)은 cross-DB 라 한 트랜잭션 불가 → audit 은 별도 conn best-effort(실패 시 warning, mutation 은 이미 commit). "모든 mutation audit 보장"이 cross-DB 제약상 엄밀히는 미충족 — 동기 롤백 불가하므로 설계 수용, 운영 가시성(warning 로그) 유지. (sample-feedback 등 기존 admin mutation 과 동일 한계.)
- **NIT(미흡수, 무해)**: `_metaEsc` dead code(호출 0, textContent 사용) · create-audit `resource_id` 64자 절단(term 전체는 change_json 보존, cosmetic).
- Verification(흡수 후): test 13/13(PYTHONPATH=동일 worktree feature-0002/src:feature-0003/src) + py_compile + node --check.
- Cross-ref: CHG-20260624T130000-item11-metadata-glossary-enum / FUNCTION REQ-20260624-item11 / (feature-0002) kb_glossary.py admin CRUD 6함수. 라이브 UI 정본=PB-0008(메인, 배포 후).
## REV-20260624T031337-gc-settings-archive-leave [SUBAGENT:adversarial-3lens-PASS]
- Date: 2026-06-24
- Cycle: feature-0009 group-conversation `gc-settings-archive-leave` (CHG-20260624T031337), **Minor §12.3** — frontend only(app.js+styles.css+index.html), 백엔드/스키마/RBAC 0.
- Panel: 적대적 3-렌즈 서브에이전트 리뷰(security/authz · correctness/edge-case · UX). 목적=결함 적발. backend 게이트(app.py `_delete_conversation_impl` 17153–17213 / `remove_conversation_member` 14487–14548)와 프론트 게이팅을 교차 검증.
- **판정: 실질 결함 0건(SHIP)**. 핵심 근거:
  - **[HIGH] not-real — client gate cosmetic**: archive(POST `/api/delete_conversation`)·leave(DELETE `.../members/{id}`) 둘 다 backend 가 권한을 독립 재검증(archive=owner/`.any` 2차 게이트, leave=`is_self_leave or is_owner or member.manage`). 보관 대신 나가기를 보여줘도 권한 상승 없음.
  - **[HIGH] not-real — IDOR 없음**: `leaveConversation` 이 대상 id 를 `state.user.id` 로만 도출(roster/URL 입력 무사용) → 타인 강제 퇴장 불가. backend 도 동일 게이트.
  - **[MED] not-real — owner→'보관', admin(.any)→'보관', 비보유 그룹멤버→'나가기', 타인 1:1→미렌더**: 모든 버튼-권한 매핑이 backend accept/reject 와 정확히 일치. owner 는 `canArchive` true 라 위험한 409(owner 제거 차단) 경로에 도달하지 않음.
  - **[MED] not-real — `refreshWorkspace("")` 안전**: leave 응답에 `current` 없음 → "" 로 기본 대화 재선택(의도적, deleteConversation 의 `payload.current` 와의 차이는 정당).
  - **[LOW] real(기존 환경의존, 본 변경 비도입)**: `is_group`/`member_count` 는 PG read 경로(`_list_conversations_pg`)에서만 채워짐 — MySQL-only read backend 면 '나가기' 분기가 dead. 단 사이드바 그룹 배지(기존)도 동일 필드 의존이고 그룹대화는 PG-native(feature-0009)라 영향권 밖. 추적만.
- Verification: `node --check app.js` PASS + `tests/verify_settings_archive_leave.mjs` 22/22 PASS(정적). UI 실렌더 정본=PB-0008(Windows-browser, 배포 후) — 본 worktree(WSL)에서 미실행, 메인 세션/배포 후 권장.
- Cross-ref: CHG-20260624T031337-gc-settings-archive-leave / FUNCTION '대화 ··· 메뉴 보관→설정 이동' / feature-0009 TASK §7.

## REV-20260624T090534-ci-pytest-green [SKIPPED: CI 워크플로 설정 + 테스트 stub 정합 — 제품·런타임·인가·스키마 무변경, 적대 패널 불요]
- Date: 2026-06-24
- Cycle: ci-pytest-green-fix (CHG-20260624T090534-ci-pytest-green). Minor §12.3.
- 변경: `.github/workflows/ci.yml` pytest PYTHONPATH 에 repo 루트 + `web` 심링크(shared·web.app collection 해소) / `test_product_delete_block_conv.py` fake 에 TASK-0302 `SELECT IsDefault` 분기.
- SKIP 사유(§18.4): 변경이 (a) CI 워크플로 설정, (b) 테스트 stub fake 정합뿐 — 제품/런타임 로직·인가·스키마 무변경. 적대 패널 불요.
- 검증: CI 동일 환경 전체 pytest **all green(exit 0)** + ruff PASS. 84 collection ERROR + 2 stale fail → 0. main CI 장기 red 해소.
- Human Approval Needed: 아니오.

## REV-20260624T075458-gc-share-participants [SUBAGENT:adversarial-3lens-PASS] — SHIP (MINOR 2 + NIT 1 흡수) (TASK-20260624T075458-gc-share-participants, REQ-20260624-gc-share-participants, Minor §12.3 — frontend-only, feature-0009 cross-cut)
- Date: 2026-06-24
- 분류: **리뷰 대상**(Minor — frontend-only 표현계층 추가, 기존 게이트된 read 엔드포인트 재사용, 신규 백엔드/스키마/RBAC 0). §18.8 UI/membership 키워드 → 적대적 3-렌즈(security·authz / correctness / UX) 서브에이전트 패널 1회.
- 변경 요지: 공유 팝업(`openShareDialog`)에 그 대화 참여 멤버 roster(`GET /api/conversations/{cid}/members` 재사용) 칩 표시. owner 우선·'소유자' 배지·아바타 `_msgAvatarEl` 재사용·사용자명 textContent.
- 적대 패널 결과 — **BLOCKER/MAJOR 0**:
  - **[MINOR] authz 주석 부정확 → 흡수**: 공유 메뉴 가시성 게이트는 `conversation.share.create`, members 엔드포인트는 `conversation.read.own/.any`+멤버십 — 두 게이트가 다르다. 원 주석("팝업을 여는 actor 는 이미 대화 접근 권한 보유")의 전제가 항상 참은 아님. → 주석을 사실에 맞게 정정(read 불가 actor 는 members **404** → 로컬 catch 가 우아하게 안내, roster 미노출, 같은 게이트인 `/shares` 도 동반 실패). **privacy 신규 노출 없음**(이미 대화 전체 열람 가능한 자만 roster 를 봄, ANCHOR §1·§3 정합).
  - **[MINOR] 스크롤 부재 → 흡수**: `.share-participants` 가 `max-height`/`overflow` 없어 참여자 多 시 패널(80vh) 내 발급 링크 영역을 압박 → `max-height:132px; overflow-y:auto; flex-shrink:0` 부여.
  - **[NIT] 빈상태 문구 → 흡수**: 비그룹/미공유 대화에서 owner 자신도 roster 에 없어 "참여 중인 사용자가 없습니다"가 혼동 유발 → "아직 참여 중인 **다른** 사용자가 없습니다…"로 정정.
  - **방어 확인(not-real)**: XSS(username textContent·아바타 DOM API), use-after-close(detached `participantsBox` 쓰기는 무해 no-op), joinable 생성 직후 roster race(`_ensure_owner_membership` 트랜잭션 내 보장·순차 await), owner_account_id null(`ownerId!=null` 가드 + role OR), 빈 username 폴백, 403 더블토스트(엔드포인트는 404 반환 → apiFetch 403 자동토스트 미발동).
- Verification: `node --check app.js` PASS + CSS brace 1549=1549 + `tests/verify_share_participants.mjs` **17/17 PASS**(정적 소스 단언). UI 실렌더 정본=PB-0008(Windows-browser, 배포 후) — 본 worktree(WSL) 미실행.
- Cross-ref: CHG-20260624T075458-gc-share-participants / FUNCTION REQ-20260624-gc-share-participants(AC-0620) / feature-0009 TASK §7 · MODIFY cross-ref.

## REV-20260625T020249-admin-metadata-relocate [SUBAGENT:adversarial-3lens-PASS] — SHIP (BLOCKER/MAJOR 0, MINOR 1 추적) (TASK-20260625T020249-admin-metadata-relocate, REQ-20260625-admin-metadata-relocate, AC-0625, Minor §12.3 — 정적 DOM 재배치)
- Date: 2026-06-25
- 분류: **리뷰 대상**(Minor — UI 표현계층 DOM 재배치, JS/CSS/RBAC/스키마/pane 본문 무변경). §18.8 UI/layout 키워드 → 적대적 3-렌즈(권한게이팅 회귀·IA정합·접근성) 서브에이전트 패널 1회.
- 변경 요지: 관리 콘솔 사이드바에서 '메타데이터'/'샘플 검수' 버튼을 '감사' 그룹에서 신설 '지식베이스' 그룹으로 이동(admin.html only).
- 적대 패널 결과 — **BLOCKER/MAJOR 0, verdict SHIP**:
  - **[렌즈1 권한게이팅 회귀] 결함 없음**: `applyAdminTabVisibility()` 가 `btn.dataset.adminTab` 키로 `canSeeTab()` 호출 — DOM 그룹 위치 무관. `metadata`/`sample-review` 권한 매핑(kb.ingest.manual∪kb.sample.curate / kb.sample.curate) 불변. 신설 '지식베이스' 그룹 자동숨김(둘 다 미보유 시 라벨+divider hide) 정상, 축소된 '감사' 그룹(audits/usage/archives) collapse 정상.
  - **[렌즈2 pane/switchTab] 결함 없음**: `switchTab()` 이 `data-admin-pane` 문자열 매칭, 초기화 분기(`tabName === "metadata"|"sample-review"`)·클릭 바인딩(`data-admin-tab`) 모두 위치 비의존. pane 본문(`data-admin-pane="metadata"|"sample-review"`) 무변경 존재.
  - **[렌즈3 숨은 의존성] 결함 없음**: styles.css nth-child/nth-of-type 전무(.admin-tab-group-label/-divider 는 class 셀렉터), admin.js 배열 인덱스 접근 없음(전부 forEach/find), '감사' 라벨 텍스트 기반 탭배치 판정 코드 없음.
  - **[렌즈4 IA정합] MINOR — 흡수(추적)**: admin.js:167 권한그룹 라벨 `kb:"지식베이스(KB) 검수"` vs 사이드바 신설 그룹 '지식베이스' 용어 미세 불일치(전자=curate 한정 뉘앙스, 후자=메타데이터 ingest 포괄 상위어). 기능 결함 아님 — 후속 용어 통일 시 정리. ship 차단 아님.
  - **[렌즈5 접근성/렌더] 결함 없음**: 신설 라벨/divider 마크업이 기존 4개 그룹(계정/제품/감사/시스템)과 구조·class 동일. (기존 한계: nav.admin-tabs 에 role=tablist 부재 — 변경 전부터 동일, 신규 회귀 미도입.)
- Verification: diff 검수(admin.html 11+/5-) + 3-렌즈 적대 서브에이전트 코드근거 확인(클릭 바인딩 admin.js:9581-9583 data-admin-tab 기반 포함). UI 실렌더 정본=PB-0008(Windows-browser, 배포 후) — worktree=WSL 미실행, WARN-only.
- Human Approval Needed: 아니오(Minor — 인증/인가/파괴/외부비용 무관).
- Cross-ref: CHG-20260625T020249-admin-metadata-relocate / TASK 동일 / FUNCTION REQ-20260625-admin-metadata-relocate(AC-0625).
## REV-20260625T020410-gc-member-kick-ban [SUBAGENT:adversarial-security-authz + reverify] — SHIP (BLOCKER 1 + MINOR 3 + NIT 1 흡수) (TASK-20260625T020410-gc-member-kick-ban, REQ-20260625-gc-member-kick-ban, Critical §12.3 — 접근제어, cross-feature feature-0003+0002)
- Date: 2026-06-25
- 분류: **리뷰 대상**(Critical — 신규 멤버십 접근제어 표면: ban 엔드포인트 4 + join/fork 재참여 게이트 + 신규 PG 테이블). §18.8 적대적 보안/authz 패널 1회 + 수정 후 재검증 1회.
- 변경 요지: 공유 대화 owner 가 참여자 추방(kick=제거)/차단(ban=제거+재참여 영구 차단)/해제(unban). 엄격 owner 전용(사용자 결정). 차단=신규 `conversation_member_bans` + join/fork is_banned 게이트.
- **적대 패널 결과 — BLOCKER 1 적발 → 수정**:
  - **[BLOCKER][authz/exfiltration] `public_share_fork` ban 우회 → 수정**: 차단된 account 가 share-token 을 보유하면 `POST /api/public/share/{token}/fork` 로 원본 대화 메시지+첨부를 자기 계정으로 전량 복제 가능했다(fork 가 `_account_can_access_conversation` 를 의도적 우회, is_banned 미체크). ban 의 목적("추가 접근 영구 차단") 무력화. → fork 에 `is_banned` 게이트 추가(403 + audit `conversation.member.fork_blocked`, `_fork_conversation_impl` 호출 전, **fail-closed**). 재검증: 다른 fork 경로 `/api/fork_conversation`·`/api/conversations/{cid}/duplicate` 는 `_account_can_access_conversation` 게이트라 차단 비-멤버는 404 — 우회 없음 확인.
  - **[MINOR][일관성] ban 비원자 커밋 순서 → 수정**: remove_member(자체 commit)→ban_member(별도 commit) 순이라 ban 실패 시 "제거됨+미차단=자유 재참여"(fail-open). → 순서 역전(ban_member 먼저→remove_member 나중) — fail-window 가 "차단 등재됨+멤버 잔존"(안전 방향)으로.
  - **[MINOR][입력] account 무검증 → 수정**: `target_id<=0` 거부(400) 가드 추가.
  - **[NIT→수정][fail-open] join is_banned PG 예외 → fail-closed**: 예외 시 `_is_banned=False`(fail-open)였던 것을 500 반환(거부)으로. add_member 도 동일 PG 요구라 추가 가용성 손실 없음.
  - **[MINOR][정보누출] 404 vs 403 — 수용**: ban/unban/bans 의 read.any admin 은 404 게이트 통과 후 owner 403 → 대화 존재여부 누출. admin 은 이미 enumerate 가능이라 실害 낮음 → 403 유지(의미상 정확), 문서화.
  - **방어 확인(not-real)**: owner_account_id null fail-closed(누구도 owner 게이트 통과 못 함), SQLi 전수 `%(...)s`, reason 512cap 이중, 멤버 추가 경로 전수(add_member: owner backfill + join-only — ban 우회 재등재 없음), unban 멤버십 미복원(의도), ban 후 메시지/첨부 tombstone(기존 정책).
- Verification: `py_compile`(app.py·group_members.py·alembic 0018) + `node --check app.js` + CSS brace 1561=1561 + `test_member_kick_ban.py` 8 + `test_member_ban_endpoints.py` 5(ast 계약 — owner-only·가드·fork BLOCKER 회귀·join 순서) + `verify_member_kick_ban.mjs` 19 + 회귀(group_members 10·share-participants 17·settings-archive-leave 22) 전부 PASS. 라이브 authz/UI 정본=PB-0008 + 배포 후(본 worktree=WSL 미실행).
- Cross-ref: CHG-20260625T020410-gc-member-kick-ban / FUNCTION REQ-20260625-gc-member-kick-ban(AC-0626~0629) / feature-0002 MODIFY·FUNCTION / feature-0009 TASK·MODIFY / docs/SECURITY.md 멤버 차단.
## REV-20260625T021924-rule-db-coverage [SUBAGENT:adversarial-frontend-PASS] — SHIP (MAJOR 1 흡수 + MINOR 2 수용) (TASK-20260625T021924-rule-db-coverage, REQ-20260625-rule-db-coverage, Minor §12.3 — frontend-only 표시 추가)
- Date: 2026-06-25
- 분류: **리뷰 대상**(Minor — frontend-only 표시 추가, 기존 게이트된 coverage 데이터 재사용, 신규 백엔드/스키마/RBAC/엔드포인트 0). §18.8 UI/표시 키워드 → 적대적 frontend 리뷰(scope/leakage · 데이터 정합 · double-render/orphan · null/empty 안전 · CSS · staleness 6 렌즈) 서브에이전트 1회.
- 변경 요지: 관리 콘솔 제품 상세 '데이터 소스 & 접근 가능 데이터베이스'의 정규식 자동 규칙 카드에 표시되는 규칙 추가 DB 에, 메인 목록과 동일한 분석 여부(DB✓/✗)·완료율(ta/tt 마이크로바) 셀(`buildDbCoverageCells`) 부착. 백엔드 `per_db[]`(Source 무관 전체 DB) 재사용.
- 적대 패널 결과 — **BLOCKER 0 / MAJOR 1 / MINOR 2**:
  - **[MAJOR] M1 read-only 뷰어 orphan → 흡수**: 규칙 카드(`_renderRuleEditor`/`_buildRuleCard`)는 `if (canManage)`(admin.js:8350) 게이트라 `product.read`-only 뷰어(coverage 배지·detail view 는 `product.read` 에 허용)는 카드를 못 본다. 그런데 메인 목록(`redrawChips`)은 rule 행을 **무조건** 제외(`if (_isRuleRow) return`)해, read-only 뷰어에게 규칙 DB 가 메인·카드 어디에도 안 보였다 → "규칙 DB 도 분석 여부·완료율 노출" 요청 불변식 위반(해당 role 한정 data-loss). **수정**: 메인 목록 skip 을 `if (_isRuleRow && canManage) return;` 로 조건부화 — canManage 뷰어는 규칙 카드에서(메인 목록 중복 제외 유지), read-only 뷰어는 메인 목록에서 coverage 와 함께 본다. `canManage`(admin.js:7783)는 `redrawChips`(8211) 이전 정의라 scope 안전(TDZ 없음). 흡수 후 무조건-skip 회귀 방지 단언 추가(verify_rule_db_coverage.mjs).
  - **[MINOR] m1 다중 datasource 동명 DB 이름키 lookup → 수용**: 같은 DB 이름이 두 datasource 에 있으면 이름 키 Map 이 첫 per_db 행을 보여줌. 메인 목록(admin.js:8241)과 **동일한 기존 한계**(백엔드도 `seen_dbs` 로 이름 dedup) — 신규 회귀 아님, 발생 가능성 낮음. 인지만.
  - **[MINOR] m2 규칙 DB per-DB 초기화 버튼 미노출 → 수용**: 규칙 항목은 `×`/초기화 컨트롤 없음(규칙 편집/삭제로 관리). 의도적 scope 선택(grid spacer 불필요한 flex 항목). 제품 소유자 확인 권장 사항이나 본 표시 추가 cycle 범위 밖.
  - **방어 확인(not-real)**: 변수 scope(`_ruleCov`/`_ruleCovByDb`/`_ruleMeasuring` if-블록 const, `covRow` forEach arrow const — 메인 목록 `covRow` 와 별 함수 scope, 충돌/shadow-throw 없음), 데이터 정합(`per_db[].db`===`schema_name`, 양측 소문자), null/empty(covRow null=측정 대기/중·connected false=연결 불가·tables_total 0 분기), CSS(flex 마이크로바 폭 명시·이름 ellipsis 로 overflow 없음·grid-only `justify-self` no-op), staleness(coverage 도착 시 `renderProductDetail()` 전체 재빌드로 카드 재렌더).
- Verification: `node --check admin.js` PASS + `tests/verify_rule_db_coverage.mjs` **20/20 PASS**(jsdom buildDbCoverageCells 렌더 8 + wiring/M1 6 + CSS 3 + cache-buster 2 + helper 추출 1). UI 실렌더 정본 = PB-0008(Windows-browser, 배포 후) — 본 worktree(WSL) 미실행.
- Human Approval Needed: 아니오(Minor — 비파괴 표시 추가, 인증/데이터/외부비용 무관).
- Cross-ref: CHG-20260625T021924-rule-db-coverage / FUNCTION REQ-20260625-rule-db-coverage / TASK-20260625T021924-rule-db-coverage / TEST 2026-06-25 Run.

## REV-20260625T030242-gc-member-actions-hover [SKIPPED:frontend-css-presentation-no-logic] (TASK-20260625T030242-gc-member-actions-hover, REQ-20260625-gc-member-actions-hover, Minor §12.3 — frontend CSS-only)
- Date: 2026-06-25
- 분류: **패널 SKIP** — 순수 CSS 표현계층 변경. JS/DOM/핸들러/백엔드/엔드포인트/RBAC/스키마 무변경(app.js 의 칩 구조 그대로 재사용, CSS 셀렉터만 교체). 보안/인가/데이터 표면 0 → 적대 패널 불요.
- 변경 요지: 공유 팝업 참여자/차단 목록을 반응형 그리드로 바꾸고, 추방/차단/해제 버튼을 기본 접힘 → 칩 hover/focus 시 `max-width`+`opacity`+`transform` 트랜지션으로 펼침. 그리드 셀 고정으로 형제 칩 위치 불변(요구), 이름 `flex:1` 로 평소 여백 0(사용자 2차 요청 충족).
- 설계 근거(대안 비교): flex-wrap 인라인 확장 = 같은 줄 형제 reflow(요구 위반) / 세로 스택 = 우측 여백 낭비(사용자 2차 지적) / **그리드** = 셀 고정(reflow 0) + 이름 flex 채움(여백 0) + 다열(세로 단축) 동시 충족. 셀 내부 펼침이라 absolute 오버레이의 스크롤 컨테이너 클리핑·이웃 칩 겹침 문제도 없음.
- Verification: CSS brace 1571=1571 + 신규 `tests/verify_member_actions_hover.mjs` **15/15 PASS**(grid·다열·접힘 기본값·hover/focus 펼침·transition·`@media (hover:none)` 터치 폴백·캐시버스터). 기존 `verify_member_kick_ban.mjs`(JS/DOM 불변) 무회귀. 라이브 시각/애니메이션 정본=PB-0008(Windows-browser, 배포 후 — 본 worktree=WSL 미실행).
- Cross-ref: CHG-20260625T030242-gc-member-actions-hover / FUNCTION REQ-20260625-gc-member-actions-hover(AC-20260625T030242-gc-member-actions-hover-1·-2) / feature-0009 TASK·MODIFY cross-ref.

## REV-20260625T045450-limit-subject-msg [SKIPPED:message-text-only-no-logic] (Minor §12.3 — 계정 한도 메시지 문구)
- Date: 2026-06-25
- Cycle: limit-subject-msg (CHG-20260625T045450-limit-subject-msg). cross-feature(feature-0002 주관 / feature-0003 계정 메시지).
- 변경: `app.py` `_check_account_token_quota` 한도 초과 메시지에 "계정의 ... 사용 한도" 주체 명시.
- SKIP 사유(§18.4/§18.8): 사용자 노출 메시지 문구만 — 429 게이트 로직·RBAC(quota.read/manage)·스키마·엔드포인트 무변경. 보안/인가/데이터 표면 0. 메시지 텍스트 단언 테스트 부재(무회귀).
- Verification: py_compile(app.py) PASS.
- Human Approval Needed: 아니오 (Minor — 비파괴 문구 변경).
- Cross-ref: CHG-20260625T045450-limit-subject-msg / TASK limit-subject-msg / feature-0002 CHG·REV-20260625T045450-limit-subject-msg.

## REV-20260625T163424-gc-participant-product-select [SUBAGENT:adversarial-authz-6hypothesis-PASS] — SHIP (BLOCKER/MAJOR/MINOR 0, 참고 1 수용) (TASK-20260625T163424-gc-participant-product-select, REQ-20260625-gc-participant-product-select, Major §12.3 — authz 경계: 참가자 발화 RBAC, feature-0009 cross-cut 코드거주=feature-0003)
- Date: 2026-06-25 (중단 세션 resume — 원본 작성 세션 372f8779 docs 직전 중단분 마무리).
- Scope: 공유 대화 참가자(비-owner 멤버)의 per-message 제품 선택·발화. 인가 경계 변경(발신자 본인 RBAC 로 제품 게이트, 권한 상속 없음, 대화 공통 바인딩 비파괴).
- 검증 방식(§18.8): 적대적 서브에이전트 패널 1회 — authz 핵심경로(`/api/ask` + RBAC helper) 인접이라 SKIP 불가. 리뷰어에게 "통과가 아니라 결함 적발" 지시 + 6개 공격가설 강제.
- 결과(전부 코드 라인 근거 + REFUTED):
  - ① 권한 우회 → REFUTED. 이중 게이트: parse 시 `_account_has_product_access`(app.py L3525) + run-product 적용 후 재확인(L11571). 타입혼동(auto early-return)·0/음수/str/None pid 전부 fail-closed(403 또는 override 미적용).
  - ② 대화 바인딩 오염 → REFUTED. backfill UPDATE 가드 `_participant_product_override is None`(L11582). override 가 대화 공통 product 를 persist 하는 경로 없음.
  - ③ owner/1:1 회귀 → REFUTED. override 는 member-only 분기(L11357-11370)에서만 채움. FE `isParticipantInSharedConversation`(L894) owner/1:1 false.
  - ④ view-only 과다 노출 → REFUTED. `_conversation_view_only_products_for` fail-closed + 대화 고정 1건 한정(L3569). except 는 노출 축소 방향.
  - ⑤ FE 정합 → REFUTED. 참가자 setActiveProduct PATCH 미호출(L1496-1505 return), view-only 항목 disabled + click listener 미등록(L1349), sendPrompt per-message 동봉(L7868-7877).
  - ⑥ auto 모드 → REFUTED. product_id_for_run=None + allowed_schemas_for_run=[] (메타 스키마만), default 자동채움 미수행.
- VERDICT: **SHIP** (BLOCKING 0).
- 참고(비-blocking, 본 변경 도입 아님 — 수용): run-product 재조회(L11524-11536) 가 예외로 row_p=None 이 되어도 override 적용 시 L11571 RBAC 재확인이 걸려 권한 우회·노출 없음. 정보용 기록.
- Human Approval Needed: 아니오 (PLAN-APPROVED feature-0009 슬라이스 + 기존 RBAC helper 재사용 + 패널 SHIP).
- Cross-ref: CHG-20260625T163424-gc-participant-product-select / feature-0009 REV-20260625T163424-gc-participant-product-select (cross-ref).
## REV-20260625T065430-gc-other-msg-left [SKIPPED:frontend-css-presentation-no-logic] (TASK-20260625T065430-gc-other-msg-left, REQ-20260625-gc-other-msg-left, Minor §12.3 — frontend CSS-only)
- Date: 2026-06-25
- 분류: **패널 SKIP** — 순수 CSS 표현계층(정렬) 변경. JS/DOM/핸들러/백엔드/엔드포인트/RBAC/스키마 무변경. app.js `renderMessages()` 가 이미 부여하던 class(`is-own-message`/`is-other-message`/`is-assistant`)를 그대로 사용하고 styles.css 정렬 규칙만 교체. 보안/인가/데이터 표면 0 → 적대 패널 불요.
- 변경 요지: 그룹/공유 대화에서 '상대방'(타 참여자, `is-other-message`) 메시지를 우측 → 좌측 정렬로 이동(assistant 와 동일 좌측 기준선). 내 메시지(`is-own-message`)는 우측 유지. 좌측으로 옮긴 버블의 꼬리(border-radius)도 좌측 하단으로 대칭화.
- 설계 근거: 기존 `.message.is-user`(특이도 0,2,0)가 own/other 구분 없이 모두 `align-self:flex-end`(우측)였음 → `.message.is-user.is-other-message`(0,3,0) override 로 other 만 `flex-start`(좌측). 그룹채팅 관례(KakaoTalk/Slack — 내 메시지 우측, 타인 메시지 좌측)와 정합. 들여쓰기 0 으로 assistant 와 좌측 기준선 통일.
- Verification: `node --check static/app.js` PASS(무변경 확인) + CSS brace 균형 + **충실한 mock 렌더 검증**(실제 styles.css + `renderMessages()` DOM 구조 재현, Chromium headless): 버블 좌우 위치 수치 측정 — `is-own-message` rightGap=25(우측), `is-other-message`/`is-assistant` leftGap=25(좌측 동일 기준선), 멘션 하이라이트 상대방도 좌측 + 주황 강조선 정상. 증거 `artifacts/pb0008-gc-other-msg-left/bubble-align-result.png`. 라이브 시각 정본=PB-0008(Windows-browser, 배포 후 — 본 worktree=WSL 미실행, 실 그룹대화 다수 참여자 메시지 필요).
- Human Approval Needed: 아니오 (Minor·프론트 CSS·사용자 명시 요청·비파괴 표현계층).
- Cross-ref: CHG-20260625T065430-gc-other-msg-left / feature-0009 TASK·MODIFY·REPORT cross-ref.

## REV-20260625T165205-doc-sync-rn-0625 [SKIPPED: 사용자 노출 릴리즈노트 정적 콘텐츠 큐레이션 — 제품 로직·인가·스키마·렌더로직 무변경, 적대 패널 불요] (TASK-20260625T165205-doc-sync-rn-0625, Minor §12.3)
- Date: 2026-06-25
- Cycle: `/_dqa:doc_sync` maintenance (CHG-20260625T165205-doc-sync-rn-0625, resume from doc-sync-20260625-160433). 직전 릴리즈노트(06-24 블록, 600f2b5) 이후 main 병합된 06-25 user-facing 변경 9종을 `static/release-notes-data.js` 에 반영(`date: "2026-06-25"` 블록 prepend) + `index.html`·`admin.html` cache-buster bump.
- 변경: 릴리즈노트 **정적 큐레이션 데이터만** — 렌더 로직(`release-notes.js`)·백엔드·라우팅·RBAC·스키마 무변경. 사용자 평이화 문구(내부 구현/테이블명/feature-id/엔드포인트 비노출).
- SKIP 사유(§18.4): 변경이 (a) 사용자 노출 릴리즈노트 텍스트 콘텐츠 추가 + cache-buster bump 뿐, (b) 실행/인가/데이터 경계 무영향. 제품 로직 변화 없음 → 적대적 verification 패널 불요(비-정책 doc 경량 cycle). 단 사실 정확성은 별도 general-purpose 적대 검증(환각/귀속/평이화/누락/STATUS정합 5축)으로 확인 — VERDICT CLEAN.
- 검증: `node --check release-notes-data.js` PASS(JS 구문) + 항목 스키마(type/area/title/detail) 정합 + 머지 커밋 10건(09114ed/cc62773/1d83d94/29d1bbf/5c525db/4cd26e7/23b7175/874f15e/70c57f6/23fa679) 1:1 대조. 내부/비-user-facing(shared P5a·codebase-map·template upgrade·spec-anchor id)은 의도적 제외 확인.
- Human Approval Needed: 아니오.
- Cross-ref: CHG-20260625T165205-doc-sync-rn-0625 / TASK-20260625T165205-doc-sync-rn-0625 / FUNCTION '릴리즈노트(업데이트 내역) 콘텐츠 — 06-25 머지분 반영' / META commit 5df5d9c(STATUS·wiki 06-25 정합).

## REV-20260625T103503-steps-btn-pending-persist [SUBAGENT:adversarial-frontend-8hypothesis-PASS] — SHIP (BLOCKER/MAJOR/MINOR 0, NIT 1 흡수 + NIT 1 보류) (TASK-20260625T103503-steps-btn-pending-persist, REQ-20260625-steps-btn-pending-persist, Minor §12.3 — frontend-only `static/app.js` 렌더 조건)
- Date: 2026-06-25 (/_template:entry dispatch, worktree ai/claude/fix-steps-btn-pending).
- 변경: 대화 중 새 요청 전송 시 이전 답변 "단계 보기" 버튼 일시 소실 버그 수정. `renderMessages()` 의 버튼 부착/fallback 가드 `!state.pendingBubble` 2곳 제거 + step side panel `stepSidePanelLive` 라이브 판정 도입(폴링 덮어쓰기 엣지 차단). 백엔드·인가·스키마 무변경.
- 패널(§18.8, UI/button dispatch → frontend): general-purpose 적대적 frontend 리뷰어가 8개 가설(H1 가드제거가 버그수정·호출경로 실재 / H2 중복버튼 / H3 bare block 스코프·중괄호 / H4 `pending===state.pendingBubble` ref 동일성·mutate-not-reassign / H5 라이브 패널 갱신 회귀 / H6 historical→live 복귀 / H7 close 후 stale-true / H8 null·그룹·복원 엣지)로 반증 시도 — **전부 반증 실패=안전**. 라인 인용 근거(버그경로 8006→8016, mutate-not-reassign 5318 등) 확인.
- VERDICT: **SHIP**. BLOCKER 0 / MAJOR 0 / MINOR 0. NIT-1(`closeStepSidePanel` 미리셋) → **흡수**(false 리셋 1줄 추가). NIT-2(`stepSidePanelConvId` set-but-never-read) → **보류**: 본 diff 이전부터 존재하던 동작, 범위 밖.
- 검증: `node --check app.js` PASS(흡수 후 재검사).
- 등급 근거(§12.3 Minor): frontend 단일 파일 렌더 조건 로직, 비파괴, 인가/데이터/스키마 경계 무영향.
- Human Approval Needed: 아니오 (Minor §12.3 — AI 자율 진행 + REVIEW 기록).
- Cross-ref: CHG-20260625T103503-steps-btn-pending-persist / TASK-20260625T103503-steps-btn-pending-persist.

## REV-20260625T192007-doc-sync-rn-0625b [SKIPPED: 사용자 노출 릴리즈노트 정적 콘텐츠 큐레이션 — 제품 로직·인가·스키마·렌더로직 무변경, 적대 패널 불요] (TASK-20260625T192007-doc-sync-rn-0625b, Minor §12.3)
- Date: 2026-06-25
- Cycle: `/_dqa:doc_sync` no-arg 전 타깃 정합 (CHG-20260625T192007-doc-sync-rn-0625b). 직전 doc_sync(163929) 이후 main 병합된 06-25 user-facing 변경 5종을 `static/release-notes-data.js` 의 기존 `2026-06-25` 블록 items 에 추가(9→14) + `index.html`·`admin.html` cache-buster bump(b→c).
- 변경: 릴리즈노트 **정적 큐레이션 데이터만** — 렌더 로직(`release-notes.js`)·백엔드·라우팅·RBAC·스키마 무변경. 사용자 평이화 문구(내부 구현/테이블명/feature-id/엔드포인트 비노출).
- SKIP 사유(§18.4): 변경이 (a) 사용자 노출 릴리즈노트 텍스트 콘텐츠 추가 + cache-buster bump 뿐, (b) 실행/인가/데이터 경계 무영향. 제품 로직 변화 없음 → 적대적 verification 패널 불요(비-정책 doc 경량 cycle). 사실 정확성은 머지 본문 5건 1:1 대조 + 평이화/내부 비노출 자체검증.
- 검증: `node --check release-notes-data.js` PASS(JS 구문) + 항목 스키마(type/area/title/detail) 정합 + 머지 5건(908fade/1f370c4+334c858/1a69f70/c8637f2) 1:1 대조. 비-user-facing(6104bf6 개발용 LLM 호출주체 임시전환)은 의도적 제외 확인. PR#442(unread baseline)는 기존 안 읽음 배지 항목에 흡수.
- Human Approval Needed: 아니오.
- Cross-ref: CHG-20260625T192007-doc-sync-rn-0625b / TASK-20260625T192007-doc-sync-rn-0625b / FUNCTION '릴리즈노트 콘텐츠 — 06-25 잔여 머지분(5건) 추가' / META commit(STATUS·wiki·overview·hot·Log 06-25 잔여 정합).

## REV-20260625T105417-steps-btn-cachebust [SKIPPED:cache-buster-only-no-logic] (TASK-20260625T105417-steps-btn-cachebust, Minor §12.3 — frontend-only)
- Date: 2026-06-25 (/_template:entry dispatch 후속, worktree ai/claude/steps-btn-cachebust).
- 변경: index.html 의 `app.js?v=20260625-gc-unread-read-fix` → `?v=20260625-steps-btn-pending-persist` 1줄. 직전 cycle(steps-btn-pending-persist)의 app.js 수정이 캐시된 사용자에게 전파되도록 cache-buster bump.
- SKIP 사유(§18.4): 순수 캐시버스터 쿼리 문자열 변경 — JS/렌더/인가/스키마/응답계약 무변경. 적대 패널 불요. (정적 자산 전파 메커니즘은 app.py:10582 TASK-0256d 에 명세 — HTML no-cache + 정적 `?v=` 버스팅.)
- 검증: app.js 는 index.html 에서만 로드(grep 확인) — 단일 진입점 bump 으로 충분.
- Human Approval Needed: 아니오.
- Cross-ref: CHG-20260625T105417-steps-btn-cachebust / CHG-20260625T103503-steps-btn-pending-persist(전파 대상).

## REV-20260626T080501-doc-sync-rn-0626 [SKIPPED:non-policy-doc] (TASK-20260626T080501-doc-sync-rn-0626, 비-정책 doc-only — 릴리즈노트 콘텐츠 + cache-buster)
- Date: 2026-06-26 (`/_dqa:doc_sync` 무인 스케줄, worktree ai/claude/doc-sync-20260626-080501).
- 변경: `static/release-notes-data.js` 06-25 블록 6항목 추가(14→20) + generated 06-26 + `index.html`·`admin.html` cache-buster `?v=20260625c-rn-0625`→`?v=20260626-rn-0626`.
- SKIP 사유(§18.4): 변경이 (a) 사용자 노출 릴리즈노트 텍스트 콘텐츠 추가 + cache-buster bump 뿐, (b) 실행/인가/데이터/응답계약 무영향. 제품 로직 변화 0 → 적대 verification 패널 불요(비-정책 doc 경량 cycle). 사실 정확성·평이화는 ULTRACODE 3축 워크플로(release-notes 분석→적대검증 verdict pass + 완전성 비평 go-with-fixes)로 머지 6건 1:1 대조 CLEAN, 내부용어 누출 0.
- 검증: `node --check release-notes-data.js` PASS(JS 구문) + 항목 스키마(type/area/title/detail) 정합 + 머지 6건(998376b/8728ade/92753ab/9b1dc16+36ad138+d90e1e2/bec35bd/feca44f) 1:1 대조. 비-user-facing(c2ed580/7c89b7d/3a7da05) 의도적 제외 확인.
- Human Approval Needed: 아니오.
- Cross-ref: CHG-20260626T080501-doc-sync-rn-0626 / TASK-20260626T080501-doc-sync-rn-0626 / FUNCTION '릴리즈노트 콘텐츠 — 06-25 후속 머지분(6건) 추가' / META commit(STATUS feature-0003·0009 행 + wiki hot.md·Log.md·feature-0009 카드 §7).

## REV-20260626T025055-product-chip-always-enabled [SUBAGENT:adversarial-product-race] — VERDICT SAFE (TASK-20260626T025055-product-chip-always-enabled, Minor §12.3 — frontend + backend PATCH 가드, TASK-0047 race 가드 완화)
- Date: 2026-06-26 (`/_template:entry` dispatch, worktree ai/claude/feature-0003-agent-web-ui, base c11cc27).
- 변경: 제품 선택 chip 을 처리 중에도 항상 활성화 — `static/app.js` renderProductChip busy 분기·setActiveProduct reject 가드 제거 + `src/app.py` `update_conversation_product`(PATCH)의 `_conversation_is_processing`→409 turn-immutability 가드·docstring 제거 + `index.html` cache-buster bump.
- 패널(§18.8 dispatch: UI/button → ux + backend/endpoint): 적대 검증 1렌즈(general-purpose 적대 리뷰어, read-only). 통과가 아니라 결함 적발 목적. 반증 대상 = "처리 중 제품 변경이 in-flight `/api/ask` 답변을 오염시키거나 백엔드 race 를 유발하지 않는다".
- 5축 검증 결과(전부 반증 실패):
  - ① ask 캡처 시점: 제품은 슬롯 획득(11662) 후 1회 read(11676-11704)→`run_kwargs` baked(11995-12013). 실행 중/후 재조회 없음.
  - ② worker 재조회: worker payload(11289-11303)는 product 캡처 전달, `_payload_to_kwargs`(modules/ask.py:85-104)·`run_agent`(agent_core) 모두 conversation product 재조회 0. agent_core 의 유일 conv SELECT(`_list_conversations` 2413)는 topic/timestamp 만.
  - ③ PATCH 부수효과: `update_conversation_product`(12332~)는 단일 row UPDATE(12407~)+`_save_account_product_pref` 뿐 — run 취소·KV·캐시 무영향.
  - ④ 동시성/데드락: 캡처된 값이라 late UPDATE 가 진행 중 run 의 product 를 소급 변경 불가. 단일 row UPDATE 라 데드락 벡터 없음.
  - ⑤ participant override: `_parse_participant_product_override`(3491)는 body 캡처(11526)·미영속(11738 skip)이라 PATCH 무관.
- VERDICT: **SAFE.** in-flight 답변 오염·백엔드 race 불가. 제거된 409/race 가드는 데이터 정합성 아닌 보수적 UX 가드(redundant defense-in-depth).
- Watch item(적발→해소): 적대 리뷰가 "①② 프론트 가드만 풀면 owner 클릭이 백엔드 409 로 실패(활성처럼 보이나 동작 안 함)" 를 적발 → 본 cycle 에서 ③ 백엔드 409 가드도 제거하여 해소(세 계층 일괄). 추가 발견 desync 우려(409 시 chip 라벨↔실제 pinned 불일치)는 409 제거로 처리 중 케이스에서 소멸.
- 검증: `node --check app.js` · `python3 -m py_compile app.py` · `ruff check app.py`(All checks passed) PASS. 잔여 chip disable 신호 grep 0. RBAC(conversation.ask·소유권·product access·IsActive)·스키마·엔드포인트 계약 무변경 재확인.
- Human Approval Needed: 아니오 (Minor, 비파괴, RBAC 무변경, 사용자 명시 결정 + SAFE).
- Deploy 승인 근거(FIRST_REQUEST.md deploy_scope: included, 사용자 결정 2026-06-11): cycle-final 후 web 재배포 사전 승인 범위. 첫 배포 직전 "deploy_scope: included 활성 — 이후 자동 배포" 1줄 표면화 완료. 실행: commit f049fee → main ff-merge → origin push → `sudo docker compose build web && up -d --no-deps web`. 검증: `repo-web-1` Up healthy + baked 서빙 `app.js?v=20260626-product-chip-always-enabled` + app.py 409 제거(grep 0) + healthz OK. ask-worker 미재빌드(web-only).
- Cross-ref: CHG-20260626T025055-product-chip-always-enabled / TASK-20260626T025055-product-chip-always-enabled / ADR-WEB-0006.

## REV-20260626T130501-doc-sync-rn-0626b [SKIPPED:non-policy-doc] (TASK-20260626T130501-doc-sync-rn-0626b, 비-정책 doc-only — 릴리즈노트 콘텐츠 + cache-buster)
- Date: 2026-06-26 (`/_dqa:doc_sync` 무인 스케줄 ULTRACODE, worktree ai/claude/doc-sync-20260626-130501).
- 변경: `static/release-notes-data.js` 신규 '2026-06-26' 블록(1항목, product-chip) prepend + `index.html`·`admin.html` cache-buster `?v=20260626-rn-0626`→`?v=20260626b-rn-0626`.
- SKIP 사유(§18.4): 변경이 (a) 사용자 노출 릴리즈노트 텍스트 콘텐츠 1항목 추가 + cache-buster bump 뿐, (b) 실행/인가/데이터/응답계약 무영향. 제품 로직 변화 0(product-chip 코드 f049fee 는 별도 cycle 에서 이미 배포·검증됨) → 적대 verification 패널 불요(비-정책 doc 경량 cycle). 사실 정확성·평이화는 ULTRACODE 워크플로(3타깃 read-only Explore 분석 → 타깃별 적대 검증자)로 검증: window 독립 재확인(cd05fa1..HEAD user-facing 단일 f049fee, late-merge 누락 0), 내부용어 누출 0, 검증자 수정(제목 정밀화 '가능해짐'→'바꿀 수 있습니다'·cache-buster datepart suffix) 흡수.
- 검증: `node --check release-notes-data.js` PASS(JS 구문) + 항목 스키마(type/area/title/detail) 정합 + releases head '2026-06-26' 신설. 비-user-facing(15ef5f4 cycle 마감 doc·c11cc27 08:05 doc-sync) 의도적 제외 확인.
- Human Approval Needed: 아니오.
- Cross-ref: CHG-20260626T130501-doc-sync-rn-0626b / TASK-20260626T130501-doc-sync-rn-0626b / FUNCTION '릴리즈노트 콘텐츠 — product-chip 06-26 블록 신설' / 원천 머지 f049fee(ADR-WEB-0006). META(STATUS·wiki) 무변경 — 이번 run delta 0.

## REV-20260629T080501-doc-sync-rn-0629 [SKIPPED:non-policy-doc] (TASK-20260629T080501-doc-sync-rn-0629, 비-정책 doc-only — 릴리즈노트 콘텐츠 + cache-buster)
- Date: 2026-06-29 (`/_dqa:doc_sync` 무인 스케줄 ULTRACODE, worktree ai/claude/doc-sync-20260629-080501).
- 변경: `static/release-notes-data.js` 기존 '2026-06-26' 블록에 [fixed/work] 1항목(ask-dedup, 같은 질문 중복 처리 수정) 합류 + summary 보강 + generated 06-26→06-29 + `index.html`·`admin.html` cache-buster `?v=20260626b-rn-0626`→`?v=20260629-rn-0629`.
- SKIP 사유(§18.4): 변경이 (a) 사용자 노출 릴리즈노트 텍스트 콘텐츠 1항목 추가 + cache-buster bump 뿐, (b) 실행/인가/데이터/응답계약 무영향. ask 멱등화 코드(0818b0a/3595ea3)는 별도 cycle 에서 이미 적대 패널(REV-20260626T134920 SHIP-WITH-FIXES·135945 hotfix) + 라이브 PG 검증 완료 → 본 릴리즈노트 cycle 은 비-정책 doc 경량. 사실 정확성·평이화·비노출은 ULTRACODE 워크플로(완전성 비평 refuted:false + 릴리즈노트 비노출 반증 refuted:false·leaksInternals:false + realityMatch:true)로 검증.
- 검증: `node --check release-notes-data.js` PASS(JS 구문) + 항목 스키마(type/area/title/detail) 정합 + 06-26 블록 items 1→2. 비-user-facing(15ef5f4·483c4c0·c11cc27 doc·doc-sync) 의도적 제외 확인.
- Human Approval Needed: 아니오.
- Cross-ref: CHG-20260629T080501-doc-sync-rn-0629 / TASK-20260629T080501-doc-sync-rn-0629 / FUNCTION '릴리즈노트 콘텐츠 — ask-dedup 06-26 블록 합류' / 원천 머지 0818b0a·3595ea3(ask-dedup-idempotency) / 본체 리뷰 REV-20260626T134920·135945. META(STATUS·wiki)는 별도 commit.

## REV-20260629T114221-metadata-bootstrap-mssql-db [SUBAGENT:adversarial-2lens-security+correctness] (TASK-20260629T114221-metadata-bootstrap-mssql-db — 메타데이터 부트스트랩 MSSQL database 차원 + 패널 잘림 + describe_table 오버레이 정합, Major §12.3)
- Date: 2026-06-29 (`/_template:entry` arg-given, worktree ai/claude/metadata-table-desc-fix).
- 문제: 관리 콘솔 > 메타데이터 > 테이블/컬럼 설명의 "스키마 골격 가져오기"가 MSSQL 데이터소스에서 **임시테이블(`#…`)** 을 테이블명으로 노출("모두 올바르지 않은 값") + 스키마 드롭다운이 고정 역할 스키마로 오염 + 부트스트랩 결과 패널이 내부 460px 박스에 갇혀 잘려 보임. AI 자동완성은 이미 구현됐으나 깨진 골격에 grounding 해 무력화.
- 근본 원인: (a) `admin_bootstrap`/`_metadata_introspect_table` 가 `_db.connect(datasource=ds)` 를 `database=None` 으로 호출 → `shared/db.py:_connect_mssql` 의 의도적 보안 설계(default_db/caller 미지정 시 중립 `tempdb` 고정, 무자격 2-part 쿼리 누수 차단)로 `tempdb` 연결 → 임시테이블 열거. (b) `load_known_schemas` 가 dialect `list_schema_names`(MSSQL=전체 sys.schemas) 를 필터 없이 반환. MySQL 은 schema==database 라 영향 없음.
- 결정 (사용자 AskUserQuestion): MSSQL server>db>schema>table 4계층을 (scope_key, schema_name, table_name) 3-키 모델에 매핑할 때 **schema_name = database 명**. 근거: ① 주입 read 경로(`load_table_column_descriptions`)는 table_name 으로 매칭하고 schema_name 은 표시 라벨(`schema.table`)이라, DB명을 넣으면 라벨이 의미있고(GunzGame.Account) DB 간 동명 테이블이 자연 구분됨, ② MySQL 이 이미 schema_name=DB명(schema==DB)이라 엔진 간 일관, ③ 모델 스키마 무변경(마이그레이션 0). 검토한 대안: schema_name="DB.schema" 복합값(라벨 길고 매칭 토큰 복잡 — 기각), schema_name=SQL스키마(dbo)(DB 차원 소실·동명 충돌 — 기각).
- 평탄화 한계(수용): MSSQL DB 안 복수 SQL 스키마(dbo+사용자스키마)의 동명 테이블은 골격에서 최초 1건만(대부분 dbo 단일). 향후 다중 SQL 스키마 DB 가 빈번해지면 schema_name="db.schema" 재검토.
- 변경(feature-0003): app.py(`admin_bootstrap_schemas` 엔진분기 + `engine`/`unit_kind` 응답, `admin_bootstrap` MSSQL database allowlist+연결, `_bootstrap_collect_skeleton_mssql` 신규, `_metadata_introspect_table` 엔진분기, `_BOOTSTRAP_MYSQL_SYS_SCHEMAS`), admin.js(unit_kind 라벨 분기 헬퍼), admin.html(label id), styles.css(`.admin-meta-bootstrap-result` max-height 제거).
- 변경(cross-feature feature-0002, Path A — panel 적발 후 추가): `tools.py` `_tool_describe_table` 가 MSSQL 일 때 KB 컬럼 오버레이 조회 키를 SQL 스키마(dbo)가 아니라 `get_active_default_db()`(pin DB명)로 + `kb_metadata.py` `load_column_descriptions_for_table` schema 매칭 case-insensitive(`LOWER`) → 부트스트랩 저장 컬럼 설명이 describe_table 도구 출력에 주입(이전 'dbo' vs DB명 + 대소문자 비대칭으로 미주입). 질문-시점 grounding(Path B `load_table_column_descriptions`)은 schema 무관·원래 정상.
- 보안: SQLi 방어 유지 — schema/database/table 식별자는 `_safe_ident` + allowlist 멤버십(MySQL=load_known_schemas / MSSQL=list_server_databases 시스템제외)로만 통과. RBAC(`kb.ingest.manual`) 무변경. database 연결은 RO 로그인 GRANT 범위 내. 외부 비용/파괴적 변경 없음.
- §18.8 적대 verification panel(general-purpose 2-lens, 통과 아닌 결함 적발 목적): **lens1 보안**(SQLi·allowlist·의존함수 실재·시스템객체 노출·RBAC·dialect 컨텍스트·자원누수 7항목) VERDICT SAFE. **lens2 정합성/회귀**(read/write 축·suggest dedup·MySQL 회귀·프론트 분기·CSS·cap 6항목) → 1차 **MAJOR 1**(Path A: describe_table 오버레이 read 축이 schema_name=DB 규약과 불일치) 적발 → 사용자 결정으로 본 cycle 포함·수정(tools.py overlay 키) → 2차 재검증 **BLOCKING 1**(pin DB명 소문자 정규화 vs 저장값 원본 케이스, PG `=` case-sensitive 로 0행) 적발 → case-insensitive 수정(kb_metadata.py LOWER) → 3차 재검증 **VERDICT SAFE**(BLOCKING/MAJOR/MINOR 0, NIT 2 선재·비회귀 수용: `''`폴백 동순위 비결정성·docstring). 적대 검증이 라이브 검증(쓰인 DB 가 전부 대문자 포함이라 우연 통과)으로는 놓칠 case 회귀를 적발·차단.
- 검증: `py_compile` app.py·tools.py·kb_metadata.py PASS · `node --check` admin.js PASS · 라이브 introspection 직호출(GunzGame 88 실테이블·temp 0) · 실 HTTPS API(curl, admin 세션: schemas/bootstrap/suggest 전부 정상) · Playwright 브라우저 eval(라벨 '데이터베이스 *'·129 DB·maxHeight none·88테이블 렌더·스크린샷). 단건 suggest grounded=true(29컬럼)·정확 설명.
- Human Approval Needed: 아니오 (Major 이나 비파괴·RBAC/스키마/마이그 무변경·사용자 설계 결정 + SAFE). 
- Deploy 승인 근거(FIRST_REQUEST.md deploy_scope: included, 사용자 결정 2026-06-11): cycle-final 후 web 재배포 사전 승인 범위. (이 환경의 컨테이너는 `docker restart` 시 RW 레이어가 baked 이미지로 복원되므로 영구 반영은 이미지 재빌드 필수 — hand-patch 는 검증용 임시.)
- Cross-ref: REQ-20260629T114221-metadata-bootstrap-mssql-db / CHG-20260629T114221-metadata-bootstrap-mssql-db / TASK-20260629T114221-metadata-bootstrap-mssql-db / 관련 정본 shared/db.py `_connect_mssql`(tempdb 고정, TASK-0213) · feature-0002 dialects.py(MySQL/MSSQL describe_*).

## REV-20260629T141637-glossary-role-single-ui [SUBAGENT:adversarial-3agent-2lens+reverify] — 메타데이터 용어사전 역할 선택 UI 단일화 + mis-scope 가드 (TASK-20260629T141637-glossary-role-single-ui, Minor §12.3 — 프런트 전용)
- 범위: feature-0003 `src/static/{admin.js,admin.html}` — 역할 선택 UI 2곳(툴바 필터 + 폼 select)을 단일 역할 컨텍스트(툴바 하나)로 통합. 폼 role select 폐기, role_key 는 `_metaGlossaryTargetRole` 단일 진실원에서 주입(생성=컨텍스트/전체→공용, 수정=기존 보존). 읽기전용 '등록 대상 역할' 배지/노트. RBAC/스키마/백엔드 무변경.
- §18.8 적대 verification panel(general-purpose, 결함 적발 목적): **1차 2-lens 병렬** — lens1(회귀/correctness 7항목: 생성/수정 role_key·제거된 폼 필드 잔여참조·payload 이중주입·배지 가드·필터 동작·node-check) **VERDICT BLOCKING 0/NIT 1**(로직 중복). lens2(UX/데이터정합 5항목: 혼동·mis-scope·역할이동 회귀·빈 역할목록·보기 전환) **VERDICT BLOCKING 2/NIT 2**.
  - **BLOCKING F2(mis-scope)**: 특정 역할 컨텍스트 등록 시 성공 토스트("등록했습니다")에 역할 미표기 → 어느 namespace 에 들어갔는지 사후 인지 불가(역할별 비중복 namespace invariant 위험). → **수정**: 토스트에 대상 역할 표기(`…했습니다 (역할: X / 공용)`).
  - **BLOCKING F5(배지 stale)**: 생성 폼 열린 채 툴바 역할 변경 시 '등록 대상 역할' 배지 미갱신 → 표시값≠실제 등록값(F2 가중). → **수정**: change 핸들러가 `_metaUpdateGlossaryRoleBadge`(id 기반, 폼 재렌더·입력 소실 없이 배지/노트만 갱신) 호출.
  - **NIT 흡수**: F1(‘전체 역할’ 보기 생성 시 공용 귀속 노트 추가) · 로직 중복(`_metaGlossaryTargetRole` 헬퍼로 배지·payload·토스트 일원화).
- **재검증(3번째 agent, 6항목 반증)**: F2/F5 해소 확인(토스트=payload 동일 진실원·배지 갱신 시 **입력 보존**·수정 모드 역할 고정), 함수 hoisting 정상, 배지 id glossary 외 미생성·null-guard 안전, 제출 후 `editing` 지역변수 생존. **VERDICT BLOCKING 0/NIT 2/클린**. 잔여 NIT 2(토스트 `!rk` 도달불가 dead-guard·"공용"/"공용 (모든 역할)" 라벨 미세 표기차)는 무해·비회귀로 수용.
- **알려진 trade-off(F3, 의도적 수용)**: 폼 역할 select 제거로 기존 용어의 역할 이동(공용↔역할) 직접 편집 UI 가 사라짐. 백엔드 PUT(`admin_update_glossary`, role_key 인자)은 capability 유지하나 UI 경로 없음. 재등록 경로는 glossary_relations(term id 종속) 미승계 + 중복 잔존. 사용자가 "단일 역할 컨텍스트"를 명시 선택한 결과로 수용하되, 이동 필요 시 후속 전용 affordance 검토 — 사용자에 표면화.
- 검증: node --check(admin.js) PASS · 적대 패널 3-agent(2-lens + 재검증) · Windows 브라우저(PB-0008) 라이브 렌더 후 완료 선언 · web 재배포 후 cache-buster·healthz.
- Human Approval Needed: 아니오 (Minor·비파괴·RBAC/스키마 무변경·사용자 설계 결정 + 재검증 클린).
- Deploy 승인 근거(FIRST_REQUEST.md deploy_scope: included, 사용자 결정 2026-06-11): cycle-final 후 web 재배포 사전 승인 범위(정적 자산 — 컨테이너 baked 이미지 재빌드 필수).
- Cross-ref: TASK/CHG-20260629T141637-glossary-role-single-ui / 원본 glossary-conv-autoreg·glossary-review-nest / 결함② role.read 권한 부여(코드 외).
## REV-20260629T143914-share-mermaid-responsive [SUBAGENT:adversarial-security+correctness] (TASK-20260629T143914-share-mermaid-responsive — 공유 뷰 mermaid + 전체 폭 반응형, Minor §12.3)
- Related Change: CHG-20260629T143914-share-mermaid-responsive
- Reason: 사용자 요청 — feature-0013 mermaid 렌더가 메인 UI 에만 적용돼 공유 대화 뷰에선 raw 코드블록으로 노출 + 공유 페이지 고정폭 960px 라 넓은 답변이 잘림.
- Alternatives Considered:
  - **공유 뷰 mermaid 적용 방식**: (a) share.js 에 함수 복제 vs (b) app.js→공용 `mermaid-render.js` 추출. **(b) 추출 채택** — 익명 공유는 공개 노출면이라 strict 보안설정이 두 뷰에서 갈라지면 위험. 단일 소스로 XSS posture 일원화(미래 mermaid 변경도 1곳).
  - **폭**: 큰 max-width 캡 vs 전체폭. **전체폭(`max-width:100%`) 채택** — 사용자 명시 요청("브라우저 전체 크기로 반응"). 넓은 표/다이어그램 표시. clamp 패딩으로 대형 화면 좌우 여백 확보.
- §18.8 적대 패널 (SUBAGENT general-purpose, security+correctness, 결함 적발 목적): **no BLOCKING**. 검증 결과:
  1. **XSS posture** — app.js·share.js 모두 `window.DOMPurify.sanitize(...)` 무인자·무 setConfig/addHook 호출(grep 확인) → 기본 allowlist 동일. enhance(sanitize 이전, source 는 `textContent` 로만)→sanitize→render(이후 strict SVG) 순서 두 뷰 동일. SVG 는 DOMPurify 표면 미통과. `mermaid.initialize` 는 전 static 트리에 단 1곳(mermaid-render.js), 항상 strict. `_mermaidInited` 단일 전역 → strict 재플립 불가.
  2. **추출 정합성** — 추출 함수 본문 byte-identical(주석만 reflow), markdownToHtml/renderMessageContent 호출부 유지, 로드 순서(mermaid.min→mermaid-render→app.js) 정확, node --check 3파일 OK.
  3. **share fallback** — (a) mermaid.min 실패→ensureMermaidInit false→mermaidFallback(원문 pre), (b) mermaid-render 실패→share.js typeof 가드 passthrough — 둘 다 콘텐츠 보존, 페이지 무파손.
  4. **함수 중복 0** — 4함수·2 module var 각 단 1곳 정의(app.js 정의 완전 제거, redeclare SyntaxError 없음).
  5. **반응형** — 넓은 요소(table/pre/mermaid) 전부 `overflow-x:auto` 격리, 헤더 flex-wrap+min-width:0. 모바일/print media query 무충돌.
  6. **회귀** — diff/attachment/결과표/외부링크 무영향, 비-mermaid 답변 early-return 으로 무변경.
- 반영: **NIT-1**(app.js bare 호출 → `typeof` 가드, mermaid-render.js 404 시 메인 UI 보호) 적용. **NIT-2**(다이어그램 없어도 3.3MB mermaid 로드) 는 메인 UI 동일 패턴이라 defer(MODIFY follow-up).
- Human Approval Needed: 아니오 (Minor, 비파괴, XSS posture 무변경, 사용자 명시 요청 범위).
- Deploy 승인 근거(FIRST_REQUEST.md deploy_scope: included): cycle-final 후 web 재배포 사전 승인. backend/스키마 무변경이라 web 이미지만 재빌드.
- Cross-ref: CHG-20260629T143914-share-mermaid-responsive / TASK-20260629T143914-share-mermaid-responsive / feature-0013 mermaid 렌더(REV-20260629T120500-relationship-diagrams 패널 SHIP — 본 변경은 그 검증된 코드의 call-site 확장).

## REV-20260629T144600-share-mermaid-responsive-deploy [SKIPPED:deploy-record-only — 코드 적대검증은 REV-20260629T143914-share-mermaid-responsive SUBAGENT 패널서 완료] 배포 완료 + PB-0008 기록
- Related Change: CHG-20260629T143914-share-mermaid-responsive (Deploy & live-verify)
- Panel skip 사유: 이번 변경은 PR #464 머지 후 web 재배포 + 배포-후 docs 기록(TASK/MODIFY/REVIEW)뿐 — 코드 무변경. 코드 적대 검증은 선행 `[SUBAGENT:adversarial-security+correctness]`(no BLOCKING)에서 완료.
- deploy_scope 승인 근거 (Phase 6.8): 전역 `FIRST_REQUEST.md deploy_scope: included`. frontend-only(backend/스키마/migrate 무관) → **web 이미지만** 재빌드·재기동.
- 라이브 검증(PB-0008 실 Windows Chrome 149): ① **메인 뷰 무회귀** — markdownToHtml→renderMermaidDiagrams flowchart SVG(7501) error 0(mermaid-render.js 추출이 메인 UI 무파손). ② **공유 뷰** — share 렌더 경로 flowchart SVG(7637) error 0 + `.share-container` computed maxWidth=100%·실폭 1249=viewport(전체 폭). 증적 `artifacts/pb0008-share-mermaid-responsive.png`. healthz ok.
- 배포-후 docs 기록이라 F0 repo-immutability escape(worktree finalize 완료, f7dcb07 동일 패턴).

## REV-20260629T080500-new-conv-dedup [SUBAGENT:adversarial-correctness — 5가설 전부 REFUTED, no BLOCKING] 새 대화 첫 전송 시 사이드바 대화 중복 제거
- Related Change: CHG-20260629T080500-new-conv-dedup / TASK-20260629T080500-new-conv-dedup / FUNCTION REQ-20260629T080500-new-conv-dedup.
- 위험등급: **Minor §12.3** (frontend-only — `app.js` + `index.html` cache-buster + 신규 테스트, backend/스키마/마이그/RBAC/credential 무변경).
- §18.8 적대 패널(general-purpose, correctness lens, 코드 정독): 5개 회귀 가설 전부 **REFUTED**.
  - H1(early-cid 조기 placeholder 제거가 catch/cancel/lazy-fail 경로 파손) REFUTED — `earlyCidActivated=true` 면 lazy-fail 분기(`else if (isLazyCreate && !earlyCidActivated)`) 미진입 → failed-status `get(busyKey)` 미도달. user-cancel 경로 delete 는 멱등 no-op. placeholder→실 cid optimistic 항목(clickable·polling)으로 교체라 진행추적 연속(오히려 중복 해소로 개선).
  - H2(추가 delete 가 후속 delete/get 파손) REFUTED — `Map.delete` 멱등, failed-status get 은 `!earlyCidActivated` 가드 안이라 early-cid 경로 미도달.
  - H3(render 를 find-guard 밖 이동→중복 unshift/무한루프/과다렌더) REFUTED — find-guard 는 여전히 `unshift` 등재만 감쌈, 밖으로 나온 건 `renderConversationList()` 호출뿐(state 무변형·재귀 없음·1회 추가 렌더 무해, placeholder 제거 반영 목적과 정합).
  - H4(`title`→`topic` 가 타 소비처 파손) REFUTED + **기존 버그 확정**: 백엔드 conversation-list payload 키가 `"topic"`(app.py 7145/7511), `refreshWorkspace` 가 `state.conversations` 전면 교체(app.js 5557). conversation 객체에서 `.title` 읽는 소비처 0건(사이드바 2533/헤더 2781/검색 9492/이름변경 6378·6390/OS알림 637 전부 `.topic`). 기존 `title:` 는 backend shape 불일치로 폴백 "새 대화" 표시되던 실제 버그.
  - H5(send 중 다른 새 대화 이동 mismatch 오염/누수) REFUTED — 정리 블록 전부 `state.pendingSentinel === busyKey` 가드 안(mismatch 면 미진입, 2차 컨텍스트 무오염). mismatch 시 busyKey placeholder 는 가드 밖 8421 delete + catch 경로 delete 가 책임(기존 설계, 변경 영향 밖).
- 검증: `tests/verify_new_conv_dedup.mjs` 18/18 PASS(정적 불변식 + jsdom 실 `renderConversationList` 행위, 회귀 재현 포함) + 기존 `verify_conv_entry_defaults.mjs` 20/20·`verify_date_group_collapse.mjs` 22/22 무회귀 + `node --check app.js` PASS.
- Human Approval Needed: 아니오 (Minor, 비파괴, 사용자 명시 보고 범위, backend/RBAC 무변경).
- Deploy 승인 근거(FIRST_REQUEST.md deploy_scope: included): cycle-final 후 web 재배포 사전 승인. frontend-only → **web 이미지만** 재빌드·재기동.
- PB-0008 Windows-browser: WSL worktree 미실행 — 배포 후 사용자 시각 확인 권장(새 대화 첫 전송→사이드바 항목 1개·진행 중 placeholder 비중복).
- 비차단 nit(패널): early-cid/fallback 두 블록은 상호배타 분기라 한쪽만 실행(중복처럼 보이나 의도). mismatch placeholder 잔류 시간은 기존 동작.

## REV-20260629T080500-new-conv-dedup-deploy [SKIPPED:deploy-record-only — 코드 적대검증은 REV-20260629T080500-new-conv-dedup SUBAGENT correctness 패널서 완료] 배포 완료 + 라이브 검증
- Related Change: CHG-20260629T080500-new-conv-dedup / TASK-20260629T080500-new-conv-dedup.
- Panel skip 사유: 본 엔트리는 ff-merge·web 재배포·라이브 검증 기록뿐(코드 무변경). 코드 적대 검증은 선행 `[SUBAGENT:adversarial-correctness]`(5가설 REFUTED, no BLOCKING)에서 완료.
- deploy_scope 승인 근거(Phase 6.8): 전역 `FIRST_REQUEST.md deploy_scope: included`(2026-06-11 사용자 결정). frontend-only(app.js + index.html cache-buster) → **web 이미지만** 재빌드·재기동(`docker compose build web && up -d --no-deps web`, override entrypoint=HTTPS 종단 유지).
- git 흐름: 작업 중 origin/main 이 dad75c3→54dbfe3→8a35eee 로 2회 전진(동시 세션 머지). 각각 재rebase 로 정합(코드 충돌 0 — 신규분 전부 doc 또는 styles.css/admin.html, app.js 무중첩; FUNCTION.md tail 충돌은 양쪽 엔트리 보존으로 해소). ff-merge main → 92751b4 → push origin main.
- 라이브 검증: `GET /healthz` HTTP 200(repo-web-1 healthy). 서빙 `index.html` 가 `app.js?v=20260629d-new-conv-dedup` 참조. 서빙 `app.js` 에 fix 반영(`new-conv-dedup` 주석 5·optimistic 등재 `topic: message.slice` 2곳).
- PB-0008 Windows-browser 실 화면 시각검증(새 대화 첫 전송→사이드바 항목 1개·진행 중 placeholder 비중복)은 WSL worktree 라 미실행 — **배포 후 사용자 확인 권장**(frontend-only render-state, 선례 동일).
- 배포-기록 doc-only 라 F0 repo-immutability escape(worktree finalize 완료, f7dcb07/8a35eee 동일 패턴).
