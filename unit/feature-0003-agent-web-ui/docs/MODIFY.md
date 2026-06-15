---
doc_type: MODIFY
feature_id: feature-0003-agent-web-ui
status: active
edit_policy: append-only
source_of_truth: true
---

# Modify Log

## CHG-20260615-0259
- Date: 2026-06-15 (TASK-0259, **docs-only** — TASK-0257/0258 PB-0008 Windows-browser 시각검증 evidence 기록)
- Scope: agent-web-ui 문서만 — `docs/TEST.md` §4 Run 추가 + `docs/TASK.md` 0257/0258 항목의 "잔여 PB-0008" → "완료(PASS)" 갱신. src 코드 0.
- 변경: TEST.md §4 에 2026-06-15 (TASK-0257 점진적 세분화 + TASK-0258 [hidden] CSS 핫픽스) Run — Environment: Windows-browser(실 Chrome/148 relay) + CLI(make test 11 PASS·jsdom 30/30). 결과 PASS: ① 역할 신규=관리 콘솔 그룹만(계정/역할/감사/설정 vanish, computed display:none) ② 관리 콘솔 접근 체크→그룹 등장 ③ 계정 그룹 펼침=계정 조회만+나머지 6개 computed display:none(배포 CSS, TASK-0258 핫픽스 실측)+더 보기 ④ override 모드 그룹 비vanish+더 보기 도달. 사용자 두 예시 라이브 충족.
- 비변경: 코드·테스트·CSS 0(순수 evidence 기록).
- 검증: 라이브 배포(web `Up healthy`, 서빙 styles.css `[data-perm-code][hidden]{display:none!important}`, 캐시버스터 `?v=20260615-perm-disclosure-hidefix`) 후 win-browser.py 실 Chrome 으로 computed display 실측. 스크린샷 `artifacts/pb0008-task0257/`·`artifacts/pb0008-task0258/`.

## CHG-20260615-0258
- Date: 2026-06-15 (TASK-0258, **Minor §12.3** — TASK-0257 핫픽스: disclosure hidden row 가 실브라우저에서 안 숨겨지던 `[hidden]` CSS override 버그)
- Scope: agent-web-ui (프론트 전용) — within-group 행 게이팅이 실브라우저에서 무력(PB-0008 검출). `.permission-toggle-card{display:flex}` 가 UA `[hidden]{display:none}` 를 동일 specificity·후순위로 override → `el.hidden=true` 가 무력화(computed display:flex). jsdom 은 CSS 캐스케이드 없어 미검출.
- 변경:
  - `src/static/styles.css`: 신규 규칙 — `.permission-section[hidden], .permission-group[hidden], .permission-grid [data-perm-code][hidden] { display: none !important; }`. disclosure 의 section/group/row 모든 숨김 대상에 display:none 강제(기존 `.search-modal-overlay[hidden]{display:none}` 선례와 동형).
  - `src/static/admin.html`: 캐시버스터 `styles.css?v=20260615-perm-disclosure-hidefix` + `admin.js?v=...-hidefix`.
  - `tests/test_permission_dependency_map.py`: 신규 `test_c1_hidden_rows_force_display_none` — styles.css 에 `[data-perm-code][hidden]` display:none !important + group/section 규칙 존재 정적 검증(회귀 가드).
- 비변경: JS 로직·PERMISSION_DEPENDENCIES·저장 경로·RBAC·엔드포인트·스키마 0. 동작 방향 strictly safer(hidden 인 행을 *실제로* 숨김 — 권한을 드러내지 않음).
- 검증: `test_c1` 포함 **11 PASS** + make test 컨테이너 회귀 0(exit=0) + CSS brace(1125=1125) + 실브라우저 수정 CSS 주입 후 computed display 재확인(account.read=flex, 나머지 6개=none). **잔여**: 배포(web 만) + 최종 PB-0008.

## CHG-20260615-0257
- Date: 2026-06-15 (TASK-0257, **Major §12.3** 권한 편집 surface — 관리 콘솔 계정·역할 권한 편집기 점진적 세분화(progressive disclosure))
- Scope: agent-web-ui (프론트 전용) — `관리 콘솔 > 계정, 역할 > [각 항목]` 권한 grid 가 카테고리별 전 권한을 평면 노출해 핵심 게이트가 묻히던 것을, 종속성 기반 row 단위 disclosure 로 점진 세분화. 백엔드 RBAC enforce·권한 code·persistence·엔드포인트·스키마 **무변경**(편집기 표시 UX 전용).
- 변경:
  - `src/static/admin.js`:
    - 신규 `PERMISSION_DEPENDENCIES`(child→선행 parent, 31엔트리) — 관리 권한 마스터 게이트 `console.access`(account.read/role.read/audit.read.own/system_prompt.global.read 부모=console.access); 그룹 base 가 세부 게이트; 운영 권한 `.any`→`.own`.
    - 신규 `_applyPermissionDisclosure`/`_refreshGroupDisclosure`/`_setPermOrphanWarn`/`_permLabel` — 매 변경/초기에 row 가시성 재계산. `forceVisible`(명시 설정 권한+조상)로 비파괴(부여 권한 미숨김), `gateSatisfied`(checkbox=체크 / override=허용)로 자식 노출, "세부 권한 N개 더 보기" 강제 노출 토글 + orphan 경고칩(checkbox 모드).
    - `renderPermissionGrid`: 각 row wrapper 에 `data-perm-code` 부여 + change/bulk 핸들러에 `recompute()` 배선 + 말미 초기 `recompute()`. mode 분기(적대 리뷰 흡수): 그룹/섹션 통째 vanish 는 checkbox(역할) 모드만, override(계정) 모드는 그룹 비숨김+row 만 접음(§10.6 "전체 표시" 정합, "더 보기" 항상 도달).
  - `src/static/styles.css`: `.permission-group-more`(더 보기 토글) / `.permission-orphan-warn`(경고칩) / `.permission-toggle-card.permission-row-dependent`(종속 row 미세 좌측 accent). reveal 즉시 토글(애니메이션 없음 — 레이아웃 뒤틀림 방지).
  - `src/static/admin.html`: 캐시버스터 `styles.css?v=20260615-perm-disclosure` + `admin.js?v=20260615-perm-disclosure`.
  - `docs/CONVENTIONS.md` §10.6: progressive disclosure 표시 단계 계층 명문화(마스터 게이트·비파괴 BLOCKING·그룹 vanish=checkbox 한정).
- 비변경: 저장 경로(`querySelectorAll("input:checked")` / `select[data-override-code]`)는 hidden row 도 그대로 읽어 권한 누락 0; product 그룹 임베드 카드·dynamic product.access.* 처리·§10.6 section/group 정렬 무변경.
- 검증: 신규 `tests/test_permission_dependency_map.py` **10 PASS**(맵 정합 M1~M4 + 가시성 불변식 V1~V6) + make test 컨테이너 **전체 회귀 0**(make exit=0) + ruff clean + `node --check`(admin.js) + CSS brace(1113=1113) + **jsdom 실 DOM 30/30**. **잔여**: 배포(web 만 — `deploy_scope: included`) + PB-0008 Windows-browser 시각검증.

## CHG-20260615-0255b
- Date: 2026-06-15 (TASK-0255b PB-0008 Windows-browser 시각검증 evidence 후속 — 코드 변경 0, docs+scenario. CHG-20260615-0255 main `a410986` 머지·재배포 이후).
- 변경: `docs/TEST.md` §4 에 `Environment: Windows-browser` Run 기록(엔드포인트 insight_health + UI "인사이트 스캔 상태" 행 구분 실증) + `docs/TASK.md`(양 feature) PB-0008 체크박스 [x] + `docs/REVIEW.md` REV-20260615-0255c [SKIPPED] + `tests/win-browser-task0255-insight-health.scenario.json`(재현 시나리오).
- 검증 결과(PB-0008 실제 Windows Chrome/148, 배포 main `a410986`): `mysql-kr-an2-auth` insight_health=unstable/circuit_open(fail 11) → UI "⚠ 연결 불안정 (미커버)"; `mysql-gz-qa-kr` healthy/ok → "정상 (분석됨)". 운영자 구분 인지 충족. 콘솔 0. 자격증명 미노출.
- 비변경: src 코드 0(evidence·docs·scenario only). REV-20260615-0255c [SKIPPED:pb0008-evidence-docs-only].

## CHG-20260615-0255
- Date: 2026-06-15 (TASK-0255 cross-feature — 주 변경은 agent-core CHG-20260615-0255. 본 항목은 **web 표면화만**)
- Scope: agent-web-ui — `app.py`(신규 `_read_insight_datasource_health` + `admin_list_datasources` 에 `insight_health` 첨부, RO·graceful), `static/admin.js`(`datasourceInsightHealth` 맵 + 배지 enrich + `_dsInsightHealthLabel` + 상세 "인사이트 스캔 상태" 행), `static/admin.html`(admin.js ?v= 캐시버스터).
- 목적: insight-worker 가 PG 에 영속한 datasource 연결 health(agent-core R2)를 관리콘솔에 표면화 — 운영자가 **"연결 불안정 미커버"(circuit_open/unstable) vs "권한 실패"(perm_failed)** 를 구분. 권한 게이트 `console.access` 유지, 자격증명/민감정보 비노출.
- 검증: `make test` GREEN. PB-0008 Windows-browser 시각검증(배포 후) — CHECK#13.

## CHG-20260615-0254b
- Date: 2026-06-15 (TASK-0254 PB-0008 Windows-browser 시각검증 evidence 후속 — 코드 변경 0, docs-only. CHG-20260615-0254 main `f8845cc` 머지·web 재배포 이후).
- 변경: `docs/TEST.md` §4 에 `Environment: Windows-browser` Run 기록(자동 eval 계측 HOLD/FOLLOW 결과) + `docs/TASK.md` TASK-0254 에 PB-0008 PASS 체크박스 + `docs/REVIEW.md` REV-20260615-0254b [SKIPPED] + 스크린샷 `artifacts/pb0008-task0254/{01_prompt_pane_after,02_prompt_textarea_top}.png`.
- 검증 결과(PB-0008 실제 Windows Chrome/148, 배포 main `f8845cc`): 제품1(KR) 제품 프롬프트 '자동 작성' SSE 스트리밍 중 ① **HOLD**(위로 scrollTop=60) 후 토큰 8샘플 **전부 top=60 고정**(오버플로 748→852 증가) = 위로 스크롤 위치 유지, ② **FOLLOW**(하단 이동) 후 토큰 73샘플 **전부 dist=0** = 최하단 추종. 사용자 원요구("작성 현황 텍스트 상단 보기") 충족. 콘솔 에러 0.
- 비변경: src 코드 0(evidence·docs only). REV-20260615-0255 [SKIPPED:pb0008-evidence-docs-only].
- Files: unit/feature-0003-agent-web-ui/docs/{TEST,TASK,REVIEW,MODIFY}.md, artifacts/pb0008-task0254/*.png

## CHG-20260615-0254
- Date: 2026-06-15 (TASK-0254, **Minor §12.3** — 관리 콘솔 제품 프롬프트 '자동 작성' SSE 스트리밍 중 스크롤 stick-to-bottom 도입)
- Scope: agent-web-ui (프론트 전용) — `관리 콘솔 > 제품 > [항목] > 제품 프롬프트` 의 '자동 작성'(TASK-0237 SSE 토큰 스트리밍)이 매 토큰 갱신마다 무조건 textarea 를 최하단으로 강제 이동시켜, 사용자가 작성 중 상단 텍스트를 읽으려 위로 스크롤해도 다음 토큰에서 즉시 최하단으로 끌려가던 이슈.
- 변경:
  - `src/static/admin.js` (autoBtn 클릭 핸들러 `handleFrame`):
    - `ev === "token"` 분기: append **직전** `atBottom = scrollHeight - scrollTop - clientHeight <= 8` 판정 → 텍스트 append 후 `atBottom` 일 때만 `scrollTop = scrollHeight`. 무조건 `textarea.scrollTop = textarea.scrollHeight` 제거. 위로 스크롤한 상태면 위치 유지, 최하단에 있으면 갱신을 따라 내려감. (임계 8px = 분수 픽셀/브라우저 clamp 오차 흡수). 첫 토큰은 `textarea.value=""` 직후라 빈 상태 → atBottom=true → 정상적으로 따라감.
    - `ev === "done"` 분기: 최종 `textarea.value` 재할당이 스크롤을 상단으로 되돌리는 부수효과 보정 — 재할당 전 `atBottom`/`prevTop` 포착 후 재할당 직후 `scrollTop = atBottom ? scrollHeight : prevTop` 로 사용자 위치 보존.
  - `src/static/admin.html`: 캐시버스터 `admin.js?v=20260615-task0254-prompt-stream-scroll`.
- 비변경: SSE 백엔드 계약(`/api/admin/products/{id}/prompt/generate/stream`)·토큰 프레임 파싱·재진입 abort·RBAC·`done` 의 pending 저장(`setSystemPromptPending`)·meta 표시(`applyAutoGenMeta`)·styles.css 무변경. 순수 클라이언트 렌더 동작만 조정.
- 검증: `node --check admin.js` PASS + 서버 `.strip()` 사실 확인(app.py:16519) + make test 컨테이너 **회귀 0 PASS**(전 진행 100%·skip 2·fail/error 0, make exit=0) + ruff clean. **잔여**: 배포(web 만 — `deploy_scope: included`) + PB-0008 Windows-browser 시각검증(스트리밍 중 위로 스크롤 유지 / 최하단일 때만 따라감).

## CHG-20260612-0253
- Date: 2026-06-12 (TASK-0253, **Minor §12.3** — 관리 콘솔 head-of-line blocking 2건 제거: A datasource ↻ 새로고침 / B 제품 분석 완료율)
- Scope: agent-web-ui — TASK-0250 배포 후 PB-0008 중 사용자 발견. "느린 대상이 정상 대상을 뒤에서 대기시키는" head-of-line 2곳 제거(이벤트 루프 비블로킹 + 제품별 병렬·개별 즉시표시).
- 변경:
  - `src/app.py`:
    - (A) `admin_test_datasource`: `_db.probe_datasource({**ds, "host": _pin})` 직접 호출 → **`await asyncio.to_thread(_db.probe_datasource, {**ds, "host": _pin})`**. async 핸들러가 동기 블로킹 probe(도달불가 시 connection_timeout 8s 점유)로 이벤트 루프를 막아 동시 /test 가 직렬화되던 것을 스레드풀 이관으로 해소(`/api/ask` `asyncio.to_thread(run_agent)` 기존 패턴). SSRF pinned IP(`_pin`)·DNS rebinding 차단 경로 무변경(인자 그대로 전달).
    - (B) `admin_products_insight_coverage`: 단건(`?product_id=`) 요청 시 대상 제품 계산·캐시 put **이후 break** 추가 — 무관 제품 순회/계산 생략(프론트 제품별 병렬 단건 호출 패턴 정합). 응답 형태(`{coverage:{...}}`) 불변.
  - `src/static/admin.js`:
    - (A) datasource 추가 드롭다운 refresh 핸들러: 캐시 비운 뒤 `_rebuildDsAddList()` + 별도 `Promise.all(force:true)` **2벌 probe** → `_rebuildDsAddList(true)` 단일 경로(중복 제거, `_kickDsConn(dsk, status, forceProbe)` 로 force 전파). `_probeDatasourceConn` 의 in-flight dedup 을 force 무관 적용(↻ 연타 중복 방지, REV MINOR-2).
    - (B) `productCoverageLoading`(전역 bool) → `productCoverageLoadingIds`(제품별 Set) + `_isProductCoverageLoading(pid)` 헬퍼. `loadProductInsightCoverage` 를 전체 1회 fetch → **제품별 `?product_id=N` 단건 병렬**(동시성 cap `_COV_FETCH_MAX=4` via 신규 `_runWithConcurrency`) + 각 제품 settle 즉시 그 배지만 렌더. 4개 표시 함수(`buildCoverageBadge`/`buildProductCoverageDetail` summaryChip·refreshBtn.disabled·hint·`redrawChips` measuring)가 제품별 로딩 참조.
  - `src/static/admin.html`: 캐시버스터 `admin.js?v=20260612-task0253-headofline`.
- 비변경: RBAC(console.access)·datasource CRUD·`/test` 응답 계약(errno 만, 자격증명 비유출)·완료율 계산 함수(`_compute_product_insight_coverage`)·conn_health 모니터·styles.css 무변경.
- 검증: node --check(admin.js) + py_compile(app.py) + 신규 `test_datasource_test_nonblocking.py`(3)·`test_insight_coverage_endpoint.py`(5) **8 PASS** + make test 컨테이너 **전체 회귀 0** + ruff clean. outside-voice REV-20260612-0253 SHIP-WITH-FIXES→흡수. 잔여: 배포(web 만) + PB-0008.

## CHG-20260612-0249b
- Date: 2026-06-12
- Task: TASK-0249 PB-0008 Windows-browser 시각검증 evidence 후속 (코드 변경 0 — REV-20260612-0249 적대 리뷰 SHIP·main `12f5c5e` 머지 완료 이후).
- 변경: `docs/TEST.md` §4 Windows-browser Run 기록 + `tests/win-browser-task0249-coverage.scenario.json`(시각검증 시나리오) 추가 + `docs/FUNCTION.md` AC-0462 PB-0008 완료 표기 + `docs/TASK.md`/`docs/REVIEW.md` 검증 결과 기록.
- 검증 결과(PB-0008 Windows Chrome/148, 배포 main `12f5c5e`): 제품94 요약 100%(571/571), datasource accordion 별 dbgame(player) 99/99·dbcommon(common, 타 서버) 111/111·dbauth(auth, 타 서버) 10/10 각 마이크로바 100%·DB✓ 시각 실증 — 0/0 해소. 스크린샷 `/tmp/win-browser-shots/task0249/{10,11,12}*.png`.
- 비변경: src 코드 0(evidence·docs only). REV-20260612-0251 [SKIPPED:visual-verify-followup] PASS.
- Files: unit/feature-0003-agent-web-ui/docs/{TEST,FUNCTION,TASK,REVIEW}.md, unit/feature-0003-agent-web-ui/tests/win-browser-task0249-coverage.scenario.json

## CHG-20260612-0248
- Date: 2026-06-12 (TASK-0248, **Major §12.3** — 관리 콘솔 제품 삭제 시 참조 대화 차단(blocked) 전환; 스키마는 feature-0002 CHG-20260612-0248)
- Scope: agent-web-ui — 제품 삭제가 참조 대화를 거부(400)하던 가드 제거 → 삭제 허용 + 그 제품 pinned 대화를 **차단(blocked)** 으로 전환(이력 열람·공유는 가능, 새 메시지 진행 불가).
- 변경:
  - `src/app.py`:
    - 신규 상수 `_BLOCKED_PRODUCT_DELETED_REASON` + `_conversation_block_info(cid, *, conn=None)`(backend-aware 차단 상태 조회, 조회실패 fail-open — PG 모드는 `_pg_connect` 별도 open/close, 전달 conn 미close) + `_block_conversations_for_product(pid, reason, *, conn=None)`(`UPDATE agent_runtime.core_conversations SET blocked_at=now(), blocked_reason=%s WHERE product_id=%s AND blocked_at IS NULL` PG 정본 / MySQL 폴백, 재차단 방지, rowcount 반환).
    - `admin_delete_product`: `in_use>0` 거부(400) **제거** → 미차단 참조 COUNT(`... AND blocked_at IS NULL`) 산출 → 기존 WebProducts cascade 삭제 commit → **commit 후** `_block_conversations_for_product` 호출(cross-store) → 응답 `{ok, product_id, blocked_conversations}` + audit change_json `referencing_conversations`.
    - `ask`(기존대화 분기): 소유권 체크 직후 `_conversation_block_info` → blocked 면 403(slot 획득 前, conn.close 후 return).
    - `_list_conversations_pg`(SELECT + item) 및 MySQL `_list_conversations` parity 에 `blocked`/`blocked_at`/`blocked_reason` 필드 추가(동일 계약).
    - MySQL `_ensure_web_tables` 폴백: `AgentCoreConversations` 에 `blocked_at DATETIME`/`blocked_reason VARCHAR(256)` 멱등 ALTER(try/except).
  - `src/static/app.js`: `canAskInConversation`(blocked→false) + `sendPrompt` 차단 가드(토스트) + `renderComposer`(isBlocked → 입력창 disabled·전송버튼 aria-disabled·"차단된 대화" 안내, busy/권한 분기 우선순위 정렬) + `renderConversationHeader`(부제 맨앞 "🚫 차단됨") + `renderConversationList`(`.is-blocked` 행 + "차단" 배지).
  - `src/static/styles.css`: `.conv-item.is-blocked`(opacity .72 + 제목 line-through) + `.conv-item-blocked-badge`(danger 토큰 `--danger`/`--danger-soft`).
  - `src/static/admin.js`: 삭제 confirm 문구("참조 대화는 '차단' 상태로 전환·되돌릴 수 없음") + 결과 토스트(`삭제됨 (대화 N개 차단)`).
  - `src/static/index.html`·`admin.html`: 캐시버스터 `?v=20260612-task0248-blocked-conv`(styles.css·app.js·admin.js).
- 비변경: RBAC 권한 카탈로그(product.manage·conversation.ask 재사용)·신규 엔드포인트 0·share-create 제한 0·fork 동작 0(접근불가 제품 auto 강등 정합 보존).
- 검증: node --check(app.js·admin.js) + py_compile(app.py) + CSS brace 1108=1108 + make test 컨테이너 회귀 0(600 passed/2 skip) + 신규 7 PASS. outside-voice REV-20260612-0248 SHIP. 잔여: 배포(make migrate 先) + 라이브 + PB-0008.

## CHG-20260612-0250
- Date: 2026-06-12 (TASK-0250, **Major §12.3** — 연결 health 모니터; web/admin 측. 코어는 feature-0002 CHG-20260612-0250)
- Scope: agent-web-ui — 관리 콘솔 datasource 연결상태를 **백그라운드 모니터가 사전계산한 값으로 즉시 표시**(per-item lazy `/test` probe + 4-cap 세마포어 자동경로 폐기) + web 프로세스에 conn_health 모니터 기동.
- 변경:
  - `src/app.py`: `@app.on_event("startup")` `_start_conn_health_monitor`(`conn_health.start_monitor(datasources.health_probe_provider())`) + `@app.on_event("shutdown")` `_stop_conn_health_monitor`. `admin_list_datasources` 가 각 datasource 에 `conn_status`(=`conn_health.snapshot()` 조회, **좌표 비노출** status/elapsed_ms/checked_at 만) 첨부.
  - `src/static/admin.js`: datasources 목록 로드 시 `conn_status`→`datasourceConnStatus` 캐시 반영. `_kickDsConn` 가 캐시 hit(=모니터 populated) 즉시 표시, miss(unknown 콜드 edge)/force(↻)만 lazy `/test` 폴백 → 자동 토글 경로 세마포어 대기 폭주 제거. ↻ 새로고침은 명시 force probe.
  - `src/static/admin.html`: 캐시버스터 `?v=20260612-conn-health-status`.
- 비변경: RBAC(console.access)·datasource CRUD·스키마·`/test` 엔드포인트·기존 배지 painter 무변경(데이터 출처만 사전계산으로).
- 검증: node --check + make test 컨테이너 회귀 0. outside-voice REV-20260612-0250(코어 feature-0002). 잔여: 배포 후 PB-0008 admin 연결상태 시각검증.

## CHG-20260612-0249
- Date: 2026-06-12
- Task: TASK-0249 (제품 insight 완료율 멀티 datasource(1:N) + 대소문자 매칭 수정), **Minor §12.3** (web-ui app.py + agent-core db.py 교차 — db.py 변경은 CHG-20260612-0249 로 feature-0002 MODIFY.md 교차 기록). 동시세션 `task0248-product-delete-blocked-conv` 가 TASK-0248 선점 → §13.1 재번호 후 0249.
- 진단: 사용자 보고 — `관리 콘솔 > 제품 > 킹스레이드(KR_QA, id 94) > 데이터 소스 & 접근 가능 데이터베이스` 에서 DB객체 분석은 진행되는데 **테이블 분석 현황 0/0**. KR_QA 는 7개 접근 DB 가 각각 다른 datasource(다른 서버)에 바인딩된 진성 1:N 제품. **Bug A**: `_compute_product_insight_coverage` 가 제품 primary datasource 하나(auth)만 해석해 7 DB 전부를 단일 auth 서버에 질의 → 타 서버 DB 0 테이블. **Bug B**: Linux MySQL `lower_case_table_names=0` 라 등록명 `dbcommon`(소문자)↔실제 `dbCommon` 어긋나 `TABLE_SCHEMA IN (...)` 0행(db.py LOWER() 로 별도 해소). 두 결함 모두 있어야 정확히 0/0.
- 변경 (`unit/feature-0003-agent-web-ui/src/app.py`, `_compute_product_insight_coverage` 전면 리팩터):
  - 접근 DB rows 를 effective datasource_key(`row.datasource_key or product["datasource_key"]`) 별 **그룹핑**. 그룹마다 `_resolve_product_insight_scope(conn, {"id":pid, "datasource_key":dskey})` 로 scope/coords/engine/allow_null 해석 → SSRF 체크 → 그룹 좌표로 라이브 카탈로그 질의(MySQL=그룹 schemas 일괄, MSSQL=DB별 연결) → 그룹 scope 로 rag_objects 분자 조회.
  - PG 통찰 연결은 그룹 간 **1회 재사용**(내부 헬퍼 `_analyzed_sets_for_scope(scope, allow_null)` 가 scope 만 바꿔 조회), `finally` 에서 close.
  - 원래 노출 순서(`order`) 보존해 합산 → 프런트 per_db 1:1 매칭 유지. 응답 키 계약(per_db: db/connected/schema_analyzed/tables_total/tables_analyzed/note + top: pct/analyzed_objects/total_objects/measurable/reason/engine/default_db) **불변**.
  - `measurable = connected_count > 0`. 한 datasource 만 해석/연결 실패 → 그 DB 만 `connected:False`+note(부분 측정), 전부 실패 → `measurable:False`(reason: 미해석이면 "데이터소스를 해석할 수 없습니다", 도달실패면 "연결할 수 없습니다").
- 비변경: `_resolve_product_insight_scope`(reset/db-insights 공유 헬퍼) — 의도적 무변경. RBAC·스키마·암호화·엔드포인트 shape·insight-worker 런타임 0. db-insights/insight-reset 계산 경로 무영향.
- 검증: 신규 `tests/test_insight_coverage.py` 5 테스트(C1~C5) + make test 컨테이너 **전체 599 passed/2 skipped 회귀 0** + ruff clean + py_compile. 라이브 시뮬레이션 기대: 제품94 ≈ 42.6%(243/571), 제품1 = 100%(무회귀).
- Files: unit/feature-0003-agent-web-ui/src/app.py, unit/feature-0003-agent-web-ui/tests/test_insight_coverage.py, unit/feature-0002-agent-core/src/modules/db.py, unit/feature-0003-agent-web-ui/docs/{TASK,MODIFY,REVIEW}.md, docs/STATUS.md
- Rollback: `_compute_product_insight_coverage` 를 단일 datasource(primary 해석) 버전으로 환원 + db.py `LOWER(TABLE_SCHEMA)` → `TABLE_SCHEMA` 환원(단 0/0 버그 재발).

## CHG-20260612-0246b
- Date: 2026-06-12
- Task: TASK-0246 정련 (연결상태 배지 정렬 컨벤션 통일), **Minor §12.3** (CSS 1줄 + 캐시버스터)
- 진단: CHG-20260612-0246 배포 후 PB-0008 측정 — name/engine/coord 행별 left spread=0(정렬 완료), 단 연결배지가 `justify-self:end`(우측 정렬)라 배지 left spread=25px(폭 차이). 사용자 컬럼 정렬 선호([[feedback_row_list_column_alignment]] — "행별 left spread=0px") + sibling `.cov-db-row`(TASK-0245)가 status/reset 를 `justify-self:start` 로 통일한 것과 정합 위해 배지도 좌측 정렬로 맞춤.
- 변경 (`styles.css` 1줄): `.admin-ds-picker-item .admin-ds-conn` `justify-self: end` → **`justify-self: start`**(고정폭 104px 열에서 배지 자연폭 좌측 정렬 → 배지 left 도 행별 동일). `admin.html` 캐시버스터 `?v=20260612-ds-picker-colalign2`.
- 비변경: 그 외 grid 트랙·열 폭·probe·백엔드·RBAC 전부 CHG-0246 그대로.
- 검증: CSS brace 균형(1105/1105) + 배포 후 PB-0008 재측정(전 열 left spread=0). REV-20260612-0246 [SKIPPED:trivial-grid-align] 연장.
- Files: unit/feature-0003-agent-web-ui/src/static/{styles.css,admin.html}, unit/feature-0003-agent-web-ui/docs/{TASK,MODIFY,FUNCTION,REVIEW}.md
- Rollback: `justify-self: start` → `end` 환원.

## CHG-20260612-0246
- Date: 2026-06-12
- Task: TASK-0246 ("+ 데이터소스 추가" 드롭다운 항목 열 정렬 — 고정 열 폭 grid), **Minor §12.3** (CSS-only 단일 블록; admin.js·백엔드·RBAC·스키마 0). 동시세션 db-row-align cycle 이 TASK-0245·CHG/REV/REQ-0245·AC-0385 선점(PR #189/#191 main 14a296f) → §13.1 재번호 0245→0246, AC→0460.
- 진단: 사용자 — "목록 폭이 문자열 길이에 따라 일정하도록(현재 들쭉날쭉)". 라이브 DOM 측정(win-browser): 항목 폭(542px)·우측 끝(1174px)은 일정하나, `.admin-ds-picker-item` 이 `display:flex` + 이름 `flex:1 1 auto` 라 행마다 이름·좌표·배지 텍스트 길이에 따라 엔진 pill(x961/936/967)·좌표(x1011/986/1018)·연결배지(x1105/1080/1080) 의 시작 x 가 어긋나 열이 세로로 정렬되지 않음. (동일 종류의 정렬 결함을 별 요소 `.cov-db-row` 에서 고친 동시세션 TASK-0245 와 무겹침 — 셀렉터 격리.)
- 변경 (`unit/feature-0003-agent-web-ui/src/static/styles.css`, 단일 블록):
  - `.admin-db-picker-item.admin-ds-picker-item`(복합 셀렉터 — DB picker `.admin-db-picker-item` 단독 행은 미영향): `display:flex` → **`display:grid`** + `grid-template-columns: auto minmax(0,1fr) 56px 124px 104px` + `align-items:center; gap:8px`. 고정 트랙이라 모든 행이 동일 열 geometry 를 공유 → 이름(`1fr`)만 가변 흡수하고 엔진/좌표/상태 열은 정렬.
  - `.admin-ds-picker-engine`: flex 잔여 제거 → `justify-self:start` + `max-width:100%`+ellipsis. `.admin-ds-picker-coord`: `justify-self:start` + ellipsis(기존 `max-width:38%`·flex 제거). `.admin-ds-picker-item .admin-ds-conn`: `justify-self:end`(배지 우측 정렬 일치).
  - `unit/feature-0003-agent-web-ui/src/static/admin.html`: 캐시버스터 `?v=20260612-ds-picker-col-align`(styles.css·admin.js).
- 열 폭 근거(라이브 측정): 엔진 42~43px(→56), 좌표 최장 `10.31.21.71:11433` 87px(→124, FQDN 초과 시 ellipsis+title), 상태 최장 `연결됨 · 8.9ms` 94px(→104, justify-self:end). 이름 잔여 ≈186px(콘텐츠영역 518 − 고정 332). datasource 키 초과 시 ellipsis.
- 비변경: admin.js(probe/캐시/세마포어/구조 0), 백엔드 app.py, RBAC, 스키마, 엔드포인트, DB picker(`.admin-db-picker-item` 단독)·`.cov-db-row`(동시세션 0245)·accordion. CSS 한 블록.
- 검증: CSS brace 균형(1105/1105) + REV-20260612-0246 [SKIPPED:trivial-grid-align](단일 규칙 cosmetic, PB-0008 가 실질 게이트). 배포 후 PB-0008 Windows-browser 열 정렬 시각검증.
- Files: unit/feature-0003-agent-web-ui/src/static/{styles.css,admin.html}, unit/feature-0003-agent-web-ui/docs/{TASK,MODIFY,FUNCTION,REVIEW}.md
- Rollback: `.admin-ds-picker-item` 를 `display:flex` 로 환원 + engine/coord/conn 의 justify-self 제거(flex 속성 복원), 캐시버스터 환원.

## CHG-20260612-0244
- Date: 2026-06-12
- Task: TASK-0244 (관리 콘솔 제품 "+ 데이터소스 추가" 드롭다운 폰트 정합 + 연결 상태 표면화), **Major §12.3** (frontend-only 다중 파일 + 네트워크 probe 추가; RBAC·스키마·백엔드 엔드포인트 0)
- 진단 (사용자 요청 2건): 관리 콘솔 > 제품 > [항목] > 데이터소스 탭의 `+ 데이터소스 추가` 목록이 ① 각 항목 `${ds.key} — ${ds.engine} @ ${ds.host}:${ds.port}` 단일 raw `<span>`(무클래스)라 같은 화면 accordion 행(`.ds-acc-name` 굵은 이름 + `.ds-acc-engine` pill)·`+ 데이터베이스 추가` picker(`.admin-db-picker-name` 구조)와 폰트/정렬이 이질적, ② 연결 상태를 `⋯ > 연결 테스트`(일회성 토스트)로만 확인 가능하고 목록엔 표시가 없음.
- 변경 (frontend-only):
  - `unit/feature-0003-agent-web-ui/src/static/admin.js`:
    - `adminState.datasourceConnStatus`(Map, key(lower)→{state,elapsed_ms,error}) 신설.
    - `_paintDsConnBadge(el, entry)` — 주어진 `<span>` 에 연결 상태(확인 중/연결됨·ms/연결 실패) in-place 렌더(비동기 probe 완료 시 동일 노드 갱신).
    - `_probeDatasourceConn(key, {force})` — `/api/admin/datasources/{key}/test` POST. 캐시 우선 + in-flight dedup(`_dsConnInflight`). **동시 probe 4개 cap 세마포어**(`_dsConnAcquire`/`_dsConnRelease`) — 도달불가 datasource 다수 시 8s(db.py connection_timeout)×N web 스레드 동시 점유 방지(REV nit 선반영).
    - `_rebuildDsAddList` 재구성: 항목 = `[체크박스 · 이름(.admin-db-picker-name 재사용) · 엔진 pill(.admin-ds-picker-engine) · 좌표(.admin-ds-picker-coord) · 연결상태 배지(.admin-ds-conn)]`. 헤더(`.admin-ds-picker-head`)에 "데이터소스 · 연결 상태" 라벨 + `↻ 새로고침`(캐시 무효화 후 재probe, stopPropagation+preventDefault). 드롭다운 열림/재렌더 시 `_kickDsConn` 으로 캐시 hit→즉시 / miss→'확인 중' 후 probe. 토글 재렌더는 캐시 hit 라 재probe 폭주 없음.
  - `unit/feature-0003-agent-web-ui/src/static/styles.css`: `.admin-ds-picker-head`/`-head-label`/`-refresh`(sticky 헤더), `.admin-ds-picker-engine`(= `.ds-acc-engine` 토큰 1:1 복제로 accordion 과 정합), `.admin-ds-picker-coord`(muted ellipsis), `.admin-ds-conn`(.is-ok/.is-fail/.is-checking — `●` 점 + 한글 라벨 병행해 색-단독 비의존, is-checking 펄스 + prefers-reduced-motion 존중).
  - `unit/feature-0003-agent-web-ui/src/static/admin.html`: 캐시버스터 `?v=20260612-ds-picker-status`(styles.css·admin.js).
- 비변경: 백엔드(app.py 무수정 — 기존 `/datasources/{key}/test` 재사용), RBAC(console.access·canDs 게이트 보존), 스키마, 암호화, 엔드포인트 shape, datasource 바인딩 스테이징 흐름(stageAdd/Remove/SetPrimary·applyAllPending 무관), accordion ⋯ 메뉴.
- 검증: node --check admin.js PASS + CSS brace 균형(1103/1103) + outside-voice subagent 디자인/정합 적대적 리뷰 **SHIP**(BLOCKER 0; 시각정합 = `.admin-ds-picker-engine` ≡ `.ds-acc-engine` 토큰 동일·`.admin-db-picker-name` 재사용 확인, 동시성 nit 세마포어로 선반영, 색맹 대응 ●+라벨 확인) REV-20260612-0244. 배포 후 라이브 + PB-0008 Windows-browser 시각검증.
- Files: unit/feature-0003-agent-web-ui/src/static/{admin.js,styles.css,admin.html}, unit/feature-0003-agent-web-ui/docs/{TASK,MODIFY,REVIEW}.md
- Rollback: admin.js 의 datasourceConnStatus/_paintDsConnBadge/_probeDatasourceConn/세마포어 + `_rebuildDsAddList` 구조 재구성 되돌림(단일 span 복원), styles.css 의 `.admin-ds-picker-*`/`.admin-ds-conn` 블록 제거, 캐시버스터 환원.

## CHG-20260612-0243
- Date: 2026-06-12
- Task: TASK-0243 (TASK-0242 후속 — MSSQL db-insights catalog 귀속 수정), **Minor §12.3** (단일 read 함수 격리 수정; RBAC·스키마·암호화·엔드포인트 shape 0)
- 진단: TASK-0242 의 `_compute_product_db_insights` 가 by_db 를 `rag_objects.schema_name` 으로 묶었는데, **MSSQL 은 schema_name 이 SQL 스키마(`dbo`)** 라 등록 DB(catalog, 예: `GameLog_100`)와 차원이 다르다. 결과로 MSSQL 의 모든 통찰이 `dbo`/`dev50` 한두 바구니로 뭉쳐, 프런트가 `insByDb[등록DB명]` 로 조회할 때 전부 빗나가 **MSSQL 등록 DB 행이 모두 "역할 미파악"** 으로 떴다(라이브 제품91 by_db=['dbo','dev50'] vs 등록 DB=GameLog_100/dk_data_release/… 무교집합). MySQL 은 db==schema 라 우연히 정상 동작했음.
- 변경 (`unit/feature-0003-agent-web-ui/src/app.py`, 단일 함수):
  - 신규 `_db_catalog_from_object_key(object_key, engine, object_type)` — `rag_objects.object_key`(`{scope}:{path}`)에서 catalog 파싱. MySQL: path 첫 segment(=db). MSSQL: schema=`{catalog}.{sqlschema}`(2)·table=`{catalog}.{sqlschema}.{table}`(3) → 첫 segment, bare(default_db, segment 부족)→None.
  - `_compute_product_db_insights`: ① SELECT 에 `o.object_key` 추가, ② 로컬 `engine` 변수화, ③ 그룹핑 키를 schema_name → 파싱한 catalog 로 변경. MSSQL 의 catalog 미귀속(bare default_db) 행은 skip, MySQL 은 catalog==schema_name 이라 **결과 byte-identical**(폴백도 schema_name).
  - SELECT 외 다른 코드 무수정. `_compute_product_insight_coverage`(완료율)·`admin_product_insight_reset`(초기화)는 object_key 미사용(schema_name/table_name 컬럼만) — **무영향**(코드 주석 + 전체 회귀로 확인).
  - `unit/feature-0003-agent-web-ui/tests/test_db_insights.py`: 기존 행 6-tuple(object_key) 보강 + `_db_catalog_from_object_key` 파서 2 + MSSQL catalog 귀속 1 테스트 추가(14→17).
- 비변경: RBAC·스키마·암호화·엔드포인트 shape·coverage/insight-reset 계산·insight-worker write 경로(feature-0002) 0. MySQL by_db 키 집합 불변(라이브 대조).
- 검증: db_insights 17 PASS + make test 컨테이너 **전체 회귀 0**(coverage·reset 등 전 스위트 통과) + ruff clean + py_compile. **side-effect 격리 분석**: `_db_catalog_from_object_key`/`_compute_product_db_insights` 각 호출처 1곳, 다른 object_key 사용처는 MinIO 첨부·coverage(schema_name 전용)로 무관. 적대적 subagent 리뷰(REV-20260612-0243). 배포 후 라이브 MSSQL by_db=catalog 매칭 + PB-0008.
- Files: unit/feature-0003-agent-web-ui/src/app.py, unit/feature-0003-agent-web-ui/tests/test_db_insights.py, unit/feature-0003-agent-web-ui/docs/{TASK,MODIFY,REVIEW,FUNCTION,TEST}.md
- Rollback: `_db_catalog_from_object_key` 제거 + 그룹핑 키 schema_name 환원 + SELECT object_key 제거.

## CHG-20260612-0242
- Date: 2026-06-12
- Task: TASK-0242 (관리 콘솔 > 제품 > 데이터소스 & 접근 가능 데이터베이스 — DB별 insight-worker 파악 내용 표면화 + 추가 picker 분석상태), **Major §12.3** (신규 read 엔드포인트 + 다중 파일; RBAC·스키마·암호화 0)
- 배경: 각 DB 행은 완료율 마이크로바(TASK-0223/0229)만 보이고 insight-worker 가 파악한 *역할/도메인*(texts.text_content 의 "domain / summary / usage / key columns")은 UI 에 없었음. `+ 데이터베이스 추가` 드롭다운도 DB 이름만 나열. 사용자 요청: 각 DB 에서 파악된 내용을 같이 출력(역할 명시) + 완료율/분석상태를 목록에도 표시. 사용자 확정: 등록 DB 행은 **펼침 없이 한 줄 인라인**(DB명·설명·분석률·객체 N/N·동일), picker 는 **도메인 힌트 + 분석상태(미분석/분석중/분석됨)**.
- 변경:
  - `unit/feature-0003-agent-web-ui/src/app.py`:
    - 신규 `_clean_insight_segment(text)` — insight text_content 에서 "X domain:" 선두 라벨 + "key columns:" 꼬리 제거하고 summary/usage 만 ' · ' 결합(한 줄 설명용).
    - 신규 `_compose_db_insight_text(ent)` → (한 줄 description = 도메인 — 요약, 멀티라인 detail_text = schema 전문 + 테이블별 정제 본문[hover title용]). schema insight 없으면 table 도메인들로 합성.
    - 신규 `_insight_worker_liveness(conn)` — heartbeat KV(`insight_worker_last_cycle_at`/`_last_status`)로 {alive,age_sec,status}. alive=status∈{ok,skip_locked} AND age≤max(30,STALE_SEC)(insight._is_*_heartbeat_fresh 정합). picker '분석중' 판정.
    - 신규 `_compute_product_db_insights(conn, product, datasource_key=None)` — 편집 대상 datasource scope(coverage 와 동일 `_resolve_product_insight_scope`)로 `public.rag_objects ⋈ texts`(conversation_id='__global__', scope_key='common', object_type∈schema/table, datasource_key=scope[OR NULL if allow_null]) 조회 → DB(schema_name lower) 별 {db,domain,description,detail_text,analyzed_schema,analyzed_tables,analyzed_objects}.
    - 신규 엔드포인트 `GET /api/admin/products/{product_id}/db-insights` — console.access 게이트, `?datasource=<key>` 멀티 datasource scope 선택(요청 datasource 가 제품 바인딩이 아니면 400 — `_list_product_datasources` 검증), 미존재 product 404. read-only.
  - `unit/feature-0003-agent-web-ui/src/static/admin.js`:
    - state `productDbInsights`(Map `${pid}::${dsKey}`→payload) + `productDbInsightsLoading`(Set). 로더 `loadProductDbInsights({productId,datasourceKey,refresh,onDone})`(캐시+중복요청 차단) + `_dbInsightsKey`.
    - `buildDbRoleCell(insRow,{loading})` — 등록 DB 행의 한 줄 설명(역할 미파악/파악 중 fallback, 전문 hover title). `redrawChips` 가 이름 다음·진척 셀 앞에 삽입 + reset-spacer(그리드 7컬럼 일관).
    - `buildPickerInsightMeta(insRow,worker)` — picker 항목 도메인 힌트 + 분석상태 칩(분석됨=analyzed_objects>0 / 분석중=0+worker.alive / 미분석). `buildPicker` 가 각 항목에 부착.
    - `_ensureDbInsights` 지연로드 hook — `_refreshAccessibleDbs`(양 분기)·`_switchEditDs`(via refresh) 에서 호출, 완료 시 redraw. `loadProductInsightCoverage(refresh)` 시 insight 캐시 무효화.
  - `unit/feature-0003-agent-web-ui/src/static/styles.css`: `.cov-db-row` 그리드 6→7컬럼(설명 추가) + `.cov-db-role`/`-muted`/`.cov-db-reset-spacer` + `.admin-db-picker-name`/`-domain`/`-status`(is-done/is-running[pulse, prefers-reduced-motion 존중]/is-none). 기존 디자인 토큰만.
  - `unit/feature-0003-agent-web-ui/src/static/admin.html`: 캐시버스터 `?v=20260612-db-insight-surface`(admin.js + styles.css).
  - `unit/feature-0003-agent-web-ui/tests/test_db_insights.py`: 신규 14 테스트(세그먼트 정제 2 / 한 줄 합성 3 / worker liveness 3 / 집계 2 / 엔드포인트 4).
- 비변경: RBAC 권한 카탈로그(console.access 재사용), 스키마(웹·agent_runtime·PG), 암호화, 기존 엔드포인트 shape, insight-worker/agent-core 런타임. 완료율(coverage) 응답·계산 무변경(별도 read 경로).
- 검증: db_insights 14 PASS(올바른 PYTHONPATH) + make test 컨테이너 회귀 0(점매트릭스 100%) + ruff clean + node --check admin.js + CSS brace balance(1090/1090) + py_compile. REV-20260612-0242. 배포 후 PB-0008 Windows-browser 시각검증 예정.
- Files: unit/feature-0003-agent-web-ui/src/app.py, unit/feature-0003-agent-web-ui/src/static/{admin.js,styles.css,admin.html}, unit/feature-0003-agent-web-ui/tests/test_db_insights.py, unit/feature-0003-agent-web-ui/docs/{TASK,MODIFY,REVIEW,FUNCTION}.md
- Rollback: app.py 의 4 신규 함수 + 엔드포인트 제거, admin.js 의 state/로더/3 빌더/_ensureDbInsights/redrawChips·buildPicker 삽입 되돌림, styles.css 신규 클래스 + 그리드 복원, admin.html 캐시버스터 복원, test_db_insights.py 삭제.

## CHG-20260612-0240
- Date: 2026-06-12 (TASK-0240, **Minor §12.3** — datasource picker 클리핑 수정 + 데이터소스 추가 체크박스 토글 통일. frontend only)
- 사용자 보고(연속 2건): ① "`+ 데이터베이스 추가` 버튼으로 나타나는 리스트가 패널 내부로 잘리는 이슈", ② "`+ 데이터소스 추가` 버튼 또한 `+ 데이터베이스 추가` 리스트와 같이 체크박스 토글 형식으로 구성".
- 진단(① — Playwright clip 조상 재현):
  - `.admin-db-picker-list` 는 `position:absolute; top:calc(100%+4px); max-height:220px`. 펼치면 드롭다운(top=492, bottom=712)이 **3중 overflow 조상**에 잘림 — (a) `.ds-acc-body{overflow:hidden}`(내가 TASK-0239 펼침 애니메이션 때 도입, 가장 가까운 조상, bottom=504 → 220px 중 12px만 노출), (b) `.admin-detail-col{overflow-y:auto}`(제품 상세 패널 스크롤 컨테이너 — 긴 폼 스크롤에 필요해 제거 불가, bottom=820), (c) `.admin-workspace{overflow:hidden}`. `position:absolute` 인 한 (b) 스크롤 컨테이너가 패널 하단을 넘는 드롭다운을 계속 자름.
- 변경 (`src/static/styles.css`, `src/static/admin.js`, `src/static/admin.html` — frontend only):
  - **① 클리핑 원천 제거(css)**: `.admin-db-picker-list` 를 `position:absolute` 플로팅 → **inline 정상 흐름**(`margin-top:4px; width:100%; max-height:220px; overflow-y:auto`)으로 전환. 목록 자신만 스크롤하고 어떤 overflow 조상도 자르지 못함(클리핑 박스가 아니게 됨). `.ds-acc-body` 의 `overflow:hidden` 제거(재발 금지 주석 — 펼침 페이드는 opacity 위주라 overflow 불필요).
  - **② 데이터소스 추가 체크박스 토글(admin.js+css)**: accordion 하단 `<select class="ds-acc-add-select">`(단일 선택) → DB picker 와 동일한 inline 체크박스 토글 드롭다운(`.ds-acc-add-btn`(=`.admin-db-picker-btn` 재사용) + `.admin-db-picker-list`). `_rebuildDsAddList()` 가 등록 datasource 전체를 항목으로, **effective(desired) 바인딩이면 체크 상태**로 렌더. 체크 → `stageAddDatasource`+`_afterBindChange(key)`(새 datasource 펼침), 해제 → `stageRemoveDatasource`+`_afterBindChange`. 매 토글 후 `_rebuildDsAddList` 로 체크 상태 재동기화. 버튼 aria-haspopup/aria-expanded + 바깥 클릭 닫기. 즉시 API 아니라 desired 스테이징 유지(TASK-0239) → "모두 적용" 일괄. `.ds-acc-add-select` CSS → `.ds-acc-add-btn`(점선 버튼) + add-row `position:relative`.
  - 캐시버스터 `?v=20260612-ds-bulk-apply`→`?v=20260612-ds-picker-inline`.
- 비변경: RBAC·DB 스키마·암호화·**백엔드 0**(엔드포인트 그대로). 스테이징·diff-apply 로직(TASK-0239)도 그대로 — 데이터소스 추가의 진입 UI(select→체크박스)만 교체.
- 검증: **Playwright 실 헤드리스 브라우저**(라이브 admin, pid=92) — clip 조상 재현(ds-acc-body·admin-detail-col·admin-workspace 3중 확인) → 수정 후 4-test(DB picker 무클리핑·hitInside / ds picker 체크박스 3항목·바인딩된 것 체크·무클리핑 / 체크 토글 시 pending+1·행 2개·서버 1개 불변 / ⋯ 메뉴 hit-test 정상) + 토글 양방향(체크 +1 → 같은 항목 해제 시 desired==baseline 복귀 pending 0·행 1개) PASS, 콘솔/pageerror 0. make test 회귀 0. node --check PASS. CSS 1076/1076 balanced.
- Files: src/static/{admin.js,styles.css,admin.html}, docs/{TASK,MODIFY,REVIEW,FUNCTION}.md
- Rollback: frontend only — revert 시 TASK-0239 absolute picker + select UI 복귀(단 클리핑 재발). 데이터/스키마 영향 없음.

## CHG-20260612-0241
- Date: 2026-06-12 (TASK-0241, **Major §12.3** — 요청 취소 즉시 처리 + 취소 직후 재요청. cross-cutting feature-0002+0003)
- 사용자 보고: "assistant 요청 후 취소했을 때, 취소 메시지 후 곧바로 취소처리 + 채팅창 즉시 사용·재요청 가능하게(현재는 취소 후 응답 대기). 구조 변경 부작용도 모두 고려."
- 진단: 백엔드 취소(`/api/cancel` cancel 플래그 + agent 루프 폴링)는 정상. 진짜 결함 = 프런트 `sendPrompt` 가 `/api/ask`(worker mode 동기응답 long-poll attach)를 `await` 하고 `state.busyConversations.delete` 를 그 `finally` 에서만 → run 종료 시점까지 입력창 잠김. 또 즉시-재요청 허용 시 같은 conversation 의 old(취소)/new run 동시성 부작용 노출.
- 변경:
  - **app.js**: `cancelCurrentRun` optimistic — busy/입력창 즉시 해제 + pending 말풍선·진행폴링·경과타이머 정리 + in-flight `/api/ask` fetch abort(`state.askAbortControllers` Map) + 포커스 + `/api/cancel` 백그라운드 발사. `state.userCanceledKeys` Set 으로 sendPrompt catch 가 사용자취소를 식별해 에러 토스트/타임아웃 복구 다이얼로그 억제. lazy-create sentinel↔earlyCid 키 이중성은 `cancelKeys`(양쪽 키 취소) + `askKey`(effective 키 정렬) + 발사 직전 취소 재확인(`throw AbortError`)으로 처리.
  - **app.py**: `/api/cancel` 이 pending/running 무관 즉시 `set_run_status("canceled", only_if_current_run=True)` → orphan `/api/ask` attach 가 슬롯 즉시 반납. `_dispatch_ask_run_worker` attach 루프에 `request.is_disconnected()` + job-aware(`_get_ask_job_status(job_id)`) 종료 → 웹 슬롯 누수 차단(`request` 를 `_dispatch_ask_run`→worker 배선). **enqueue 선기록을 `set_run_status("processing", run_id="enqpre-<uuid>")`(sentinel)로** — KV `last_status_run_id` 가 직전(취소) run 으로 남아 orphan terminal write 가 가드를 우회·새 요청 processing 을 클로버하던 BLOCKER 차단.
  - **agent_core.py + memory.py**: `set_run_status(only_if_current_run=True)` supersede 가드(저장된 last_status_run_id 가 다른 run 이면 write skip). agent 루프 terminal write(canceled/done/error) 3곳 적용. claim/sentinel takeover 는 default(무조건) 유지.
- 정합: sentinel(enqueue) + only_if_current_run(terminal/cancel) + 무조건 takeover(claim, agent_core:2472) 3중. 나열 가능한 모든 인터리빙에서 새 run processing 보존·취소전용 canceled 오삭제 없음(2차 적대 리뷰 확인). orphan 은 현 LLM step(동기, 인터럽트 불가) 종료 후 답변 기록 없이 종료.
- 검증: 신규 `unit/feature-0002-agent-core/tests/test_set_run_status_supersede.py` 5건 PASS + 전체 pytest 회귀0(F/E 0, 2 skip) + ruff All checks passed + node --check + py_compile.
- follow-up(별 cycle, LOW): never-claimed pending job + sentinel KV 잔존(pending-job TTL reaper 부재 — 본 변경 이전 class, 악화 아님; 20분 후 stale_error·max_wait 슬롯반납 완화).

## CHG-20260612-0239
- Date: 2026-06-12 (TASK-0239, **Minor §12.3** — datasource accordion 후속 버그/UX 3건. frontend only)
- 사용자 보고(TASK-0238 재설계 직후 실사용): ① "⋯ 버튼이 작동하지 않아 검증 필요", ② "데이터소스 추가 후 일괄 적용 형식에 포함 안 됨(추가 시 즉시 반영되는 이슈)", ③ "각 데이터소스 클릭 시 깜빡임 → 부드러운 애니메이션 적용".
- 진단:
  - **①(기능 버그, Playwright hit-test 재현)**: `.ds-acc-menu-btn` 클릭 시 JS 는 `.ds-acc-menu` 의 `hidden` 을 정상 토글(`display:flex`)하나, TASK-0238 에서 행에 준 `.ds-acc-row{overflow:hidden}` 이 행 경계 밖(`top:100%`)으로 드롭되는 `position:absolute` 메뉴를 **클리핑** → 메뉴가 화면에 안 그려지고 `document.elementFromPoint(메뉴중앙)` 이 메뉴 항목이 아닌 뒤의 `.cov-db-editor` 를 맞힘(클릭 불가).
  - **②(일관성)**: 콘솔의 다른 모든 편집(productMeta/productDatabases/systemPrompts)은 `adminState.pending` 에 스테이징 후 footer "모두 적용" 으로 일괄 저장. datasource 바인딩만 즉시 API(`POST/PATCH/DELETE /datasources`) → 일괄 흐름 밖 anomaly.
  - **③(UX)**: 행 전환(`_switchEditDs`)·바인딩 변경이 전체 `renderProductDetail()` 재렌더 + 비동기 `_refreshAccessibleDbs`(칩 비웠다 다시 채움)를 유발 → 깜빡임.
- 변경 (`src/static/admin.js`, `src/static/styles.css`, `src/static/admin.html` — frontend only):
  - **① CSS**: `.ds-acc-row` 의 `overflow:hidden` 제거(재발 금지 주석) + `transition`(active 강조 부드럽게). 둥근 모서리는 `.ds-acc-head` 가 직접 — 좌측만, `:only-child`(메뉴 없는 행)는 양쪽, `.is-active`(펼친 행)는 하단 직각 분기.
  - **② 일괄 적용 스테이징(admin.js)**: 신규 `pending.productDatasources` Map(productId → {baseline:[{datasource_key,is_primary}], desired:[…]}). 헬퍼 `_ensureDatasourcePending`/`_settleDatasourcePending`/`effectiveProductDatasources`/`stageAddDatasource`/`stageRemoveDatasource`/`stageSetPrimaryDatasource` + 비교 `_dsBindNorm`/`_dsBindEqual`/`datasourceDirtyProductCount`. ⋯ 메뉴(기본지정/제거)·추가 select 가 즉시 API 대신 stage* 호출 + 로컬 `_afterBindChange`(accordion 만 재렌더). `pendingChangeCount`·`refreshPendingUI`(detail "데이터소스 바인딩 N")·`cancelAllPending`·삭제제품 GC 에 편입. `applyAllPending` 에 diff-apply 루프 추가 — baseline↔desired diff 로 제거(DELETE)→추가(0개면 PATCH, 이후 POST)→primary 재지정(POST is_primary) 순, **제품 DB PUT 보다 먼저** 수행(추가 바인딩에 DB PUT 가능) + 제거된 datasource 의 접근DB draft 는 PUT skip(서버가 바인딩과 함께 삭제 — 고아 방지).
  - **③ 깜빡임(admin.js+css)**: `_switchEditDs`·`_afterBindChange` 가 전체 렌더 대신 accordion 로컬 재렌더 + `redrawChips()` 동기 선호출(구 datasource DB 잔상 제거 후 비동기 정교화). `.ds-acc-body` 에 `@keyframes ds-acc-body-in`(opacity+translateY) 펼침 애니메이션, `@media (prefers-reduced-motion:reduce)` 로 비활성화.
  - 캐시버스터 `?v=20260612-ds-accordion`→`?v=20260612-ds-bulk-apply`.
- 비변경: RBAC·DB 스키마·암호화·**백엔드 0**(엔드포인트 add/remove/set/test/databases 그대로 재사용). desired-state 는 클라이언트 조립 후 기존 엔드포인트로 diff 호출.
- 검증: **Playwright 실 헤드리스 브라우저**(라이브 admin, pid=92) 4-test + 제거 일괄적용 — ⋯ 클릭 시 "연결 테스트" hit-test PASS, 추가 시 pending+1·행2개·**서버 1개 불변**, 전환 직후 동기 DB리스트 렌더(무 flash), "모두 적용" 후 서버 2개·pending 0, 제거 스테이징 시 서버 불변→적용 후 제거. 콘솔/pageerror 0. make test(컨테이너 pytest+ruff) 회귀 0. node --check PASS. CSS 1075/1075 balanced.
- Files: src/static/{admin.js,styles.css,admin.html}, docs/{TASK,MODIFY,REVIEW,FUNCTION}.md
- Rollback: frontend only — 직전 커밋으로 revert 시 TASK-0238 즉시-API accordion 복귀(단 ⋯ 메뉴 클릭불가 재발). 데이터/스키마 영향 없음.

## CHG-20260612-0238
- Date: 2026-06-12 (TASK-0238, **Minor §12.3** — datasource 패널 통합 accordion 재설계; 동시세션 cycle 이 TASK-0237 선점(자동작성 SSE)→본 cycle 은 0238)
- 사용자 요청: "기능은 모두 정상 동작 확인. 단 디자인적으로 중복되는 분류가 많고 통일감이 없다 → gstack 스킬을 적극 사용해 보충." 멀티 datasource(TASK-0228~0236)를 여러 동시세션이 증분 수정하며 누적된 시각 부채.
- 진단 (gstack `/design-review` + codex outside-voice 소스 감사):
  - **중복 분류**: datasource 정보가 3곳 — ① "데이터 소스" 섹션 칩, ② "편집 대상 데이터소스" `<select>`, ③ "접근 가능 데이터베이스" 헤더 배지(dbTitleDs). 같은 데이터를 3 표현으로 반복.
  - **통일감 부재**: 시각 패턴 3종 혼재 — 파란 pill(datasource 칩) / 점선 pill(시스템 DB 칩) / 둥근 사각 행(DB 항목). 칩 액션 아이콘 불일치(★기본/⟳테스트/×제거 가 칩마다). DB행은 텍스트버튼(초기화)+아이콘(×) 혼재. 헤더 배지는 제목에 공백 없이 붙고 대소문자 불일치. rgba 하드코딩(토큰 미사용).
- 변경 (표현 계층 교체, 편집 로직 보존):
  - `src/static/admin.js` (`renderProductDetail` datasource 영역 ~242줄 재작성):
    - **제거**: 별도 "데이터 소스" 섹션, 편집대상 `<select>`(_editDsSelect), 헤더 배지(dbTitleDs/`_updateDbSectionLabel`/`_renderDsChips`/dsChips), 독립 "연결 테스트" 버튼.
    - **신설**: 단일 섹션 "데이터 소스 & 접근 가능 데이터베이스" → `buildProductCoverageDetail` → datasource accordion(`.ds-acc`) → "＋ 데이터소스 추가" select. 각 datasource = `.ds-acc-row`(`▸/▾` caret + 이름 + 엔진 + "기본" 배지 + `⋯` 메뉴). 펼친(active) 행 아래로 `dbEditorWrap`(시스템칩 + DB리스트 + 추가 picker) 인라인 이동.
    - `_buildDsMenu(b)`: 행별 `⋯` 메뉴 — 연결 테스트 / 기본으로 지정(primary 아닐 때) / 바인딩 제거. 흩어진 ★/⟳/× + 공용 연결테스트 버튼을 한 곳으로 통일.
    - `_renderDsAccordion()`: 바인딩 배열로 행 재구축 + active 행 아래 dbEditorWrap 이동. `_switchEditDs(key)`: draft 보존 후 `_editDsKey` 전환 + `_renderDsAccordion` + `_refreshAccessibleDbs`. `_reloadProductDatasources()`: 바인딩 변경 후 adminState 정본 동기화 + `renderProductDetail()` 전체 재렌더(TASK-0236 교훈 유지).
    - **보존 클로저**(회귀 최소화): draft/`_swapDraftContents`/`_loadDraft`/`_draftKeyFor`/redrawChips/buildPicker/`_refreshAccessibleDbs`/`_serverDbsFor`. `let _editDsKey` 는 accordion 사용 전 선언(TASK-0236 TDZ 수정 유지).
  - `src/static/styles.css`: `.admin-db-ds-badge` 제거. `.ds-acc*`(`.ds-acc-row`/`.is-active`/`.ds-acc-head`/`.ds-acc-caret`/`.ds-acc-name`/`.ds-acc-engine`/`.ds-acc-primary`/`.ds-acc-body`/`.ds-acc-menu-wrap`/`.ds-acc-menu-btn`/`.ds-acc-menu`/`.ds-acc-menu-item`/`.ds-acc-add-row`/`.ds-acc-add-select`/`.cov-db-editor`) 신설 — 디자인 토큰(`--primary`/`--primary-soft`/`--border`/`--r-md`/`color-mix`)만 사용, 단일 시각 패턴(둥근 행).
  - `src/static/admin.html`: 캐시버스터 `?v=20260612-prompt-stream`→`?v=20260612-ds-accordion`(styles.css·admin.js).
- 비변경: RBAC 카탈로그·DB 스키마·암호화·엔드포인트 shape·백엔드 0(엔드포인트는 기존 datasources/datasource/test 재사용). 표현 계층만 교체.
- 검증: **Playwright 실 헤드리스 브라우저**(라이브 admin) — 단일(pid=92)·멀티(추가 후 2행)·MSSQL 캡처 + 펼침/접힘/전환(active 이동 + DB목록 datasource 반영)/추가 동작 PASS, 콘솔/pageerror 0. make test(컨테이너 pytest) 회귀 0. node --check admin.js PASS.
- Files: src/static/{admin.js,styles.css,admin.html}, docs/{TASK,MODIFY,REVIEW,FUNCTION}.md
- Rollback: 표현 계층만 교체이므로 직전 커밋(8be6487) 으로 revert 시 기존 칩+select+배지 UI 복귀(편집 로직 동일). 데이터/스키마 영향 없음.

## CHG-20260612-0237
- Date: 2026-06-12 (TASK-0237, **Major §12.3** — 자동작성 LLM 토큰 스트리밍 + OpenAI legacy 명명 정리; 동시세션 cycle 이 TASK-0231~0236 선점→§13.1 재번호 0233→0237)
- 사용자 요청: 제품 프롬프트 "자동 작성"이 최대 90초 LLM 호출 동안 "생성 중…" spinner 뿐이라 진행을 알 수 없음 → 토큰 스트리밍으로 실시간 표시.
- 변경 (feature-0003 측):
  - `src/app.py`: ① `_collect_product_prompt_context` 헬퍼 추출 — 기존 `admin_generate_product_prompt`(POST)의 MySQL 제품/스키마 조회 + PG 인사이트 수집 + knowledge_block + create_kwargs 조립을 비스트리밍/스트리밍 공유(중복 제거). 인증·권한·제품부재 실패 시 `(JSONResponse, None)` 반환. ② 신규 `GET /api/admin/products/{id}/prompt/generate/stream` — 인증·수집을 generator 진입 전 완료(export_audit_events_csv 패턴), 별 스레드 `produce()`가 `chat.completions.create(stream=True)` 동기 iterate → `loop.call_soon_threadsafe` 로 `asyncio.Queue` 브릿지(단일 uvicorn 이벤트 루프 블로킹 차단). SSE event `progress`→`token`(증분)→`done`(prompt+meta)|`error`. `truncated` = 마지막 chunk finish_reason=='length'. `StreamingResponse(media_type="text/event-stream", X-Accel-Buffering:no, Cache-Control:no-cache)`. ③ 기존 POST 핸들러는 헬퍼 사용으로 재작성(동작 동일, 비스트리밍 안전망). ④ `_sse_pack`(ensure_ascii=False). ⑤ `_get_openai_client`→`_get_llm_client` import(CHG agent-core 0237 정합). ⑥ `_resolve_session_default_model` env 소스 `LLM_MODEL or OPENAI_MODEL`.
  - `src/static/admin.js`: autoBtn 핸들러를 `apiFetch`(즉시 json) 우회 → `fetch + response.body.getReader() + TextDecoder + "\n\n" 프레임 파싱`. `token`→textarea append+글자수 카운터+자동 스크롤, `progress`→단계 라벨, `done`→최종 prompt 정합+`setSystemPromptPending`+`applyAutoGenMeta`(grounded/truncated 경고 — 기존 로직 헬퍼 추출), `error`→실패 메시지. `AbortController` 재진입 방어, `!resp.ok`(403/404/503 JSON) 분기.
  - `src/static/admin.html`: 캐시버스터 `?v=20260612-ds-detail-rerender`→`?v=20260612-prompt-stream`(styles.css·admin.js).
- 동반 변경 (feature-0002): `_get_openai_client`→`_get_llm_client` rename + alias, `OPENAI_API_BASE` 제거, env backward-compat. agent-core MODIFY.md CHG-20260612-0237 참조.
- 비변경: RBAC 카탈로그·DB 스키마·암호화·기존 엔드포인트 shape(신규 stream GET 추가 외). 비스트리밍 POST 응답 동일.
- 검증: 신규 `tests/test_prompt_generate_stream.py` 6(SSE 직렬화/파싱 라운드트립 + Queue 브릿지 누적/truncated/error) + 기존 truncation 3 PASS. node --check admin.js PASS. app.py AST 구문 OK. 시각 동작은 PB-0008(배포 후) 확인.
- Files: src/app.py, src/static/{admin.js,admin.html}, tests/test_prompt_generate_stream.py(신규), docs/{FUNCTION,TASK,REVIEW,MODIFY}.md
- Rollback: 신규 stream GET·헬퍼·프론트 SSE 제거 시 기존 POST 비스트리밍 경로로 복귀(안전). rename 은 alias 로 무중단.

## CHG-20260612-0236
- Date: 2026-06-12 (TASK-0236, **Minor §12.3** — datasource UI 바인딩 변경 후 미갱신 근본수정, frontend-only)
- Scope: TASK-0234 후속 사용자 보고 3건(연결테스트 무의미·DB 목록 datasource 단서 없음/미갱신·primary 미갱신). Playwright 실 헤드리스 브라우저로 재현 후 근본수정. 권한/스키마/엔드포인트/백엔드 0.
- Files:
  - unit/feature-0003-agent-web-ui/src/static/admin.js (① `_reloadProductDatasources`/첫-바인딩 PATCH 경로 → `renderProductDetail()` 전체 재렌더, ② `_editDsKey` 선언을 "편집 대상 select" 블록 앞으로 이동[TDZ 해소])
  - unit/feature-0003-agent-web-ui/src/static/admin.html (캐시버스터 `?v=20260612-ds-detail-rerender`)
- 근본 원인: (a) 제품 상세 datasource UI 가 단일 `renderProductDetail()` 시점 클로저 기반인데 바인딩 변경 후 칩만 부분 갱신 → 편집대상 select·배지·DB목록 stale. 바인딩 0↔1↔N 전환 시 select 생성/제거 불가. (b) `length>=2` 편집대상 select 블록이 `_editDsKey` 를 let 선언 전에 참조 → ≥2 바인딩 제품 렌더 시 ReferenceError(TDZ)로 패널 blank(잠복).
- 검증: Playwright 실브라우저 재현→수정→재검증(add/switch 모두 PASS, 콘솔에러 0) + make test 회귀 0.
- Rollback: 위 2파일 revert(frontend-only).
## CHG-20260612-0235v
- Date: 2026-06-12 (TASK-0235 후속 — PB-0008 Windows-browser 시각검증 PASS 기록 + 시나리오 자산 추가)
- Scope: TASK-0235(새 대화 첫 메시지 진행 단계 실시간 표시) 라이브 배포 후 실제 Windows 브라우저 검증 완료 기록. docs + test scenario only — 코드 0.
- 변경:
  - `docs/TEST.md`: §4 2026-06-12 TASK-0235 Run 의 Windows-browser Environment 를 "예정"→**PASS(23/23)** 로 갱신(증거 6 스크린샷 + 단계 실시간 전환·사이드바 동작 실측).
  - `tests/win-browser-task0235-newconv-progress.scenario.json`: 신규 — 새 대화 첫 요청 → pending bubble step 실시간 표시 → "단계 보기" → `#stepSidePanel` 사이드바 검증 시나리오(재현 가능).
- 비변경: app.js / index.html / 백엔드 / 스키마 0. TASK-0235 코드는 이미 PR #172 로 머지·배포됨.
- 검증: PB-0008 시나리오 PASS, healthz 200. CHECK#13 충족.
- Cross-ref: TASK-0235 / CHG-20260612-0234 / REV-20260612-0235v.

## CHG-20260612-0234
- Date: 2026-06-12 (TASK-0235, **Major §12.3** — 새 대화 첫 메시지 작업 단계 진행상황 실시간 표시; 동시세션 insight-reset·prompt-autogen·ds-a11y·ds-label cycle 이 TASK-0231/0232/0233/0234 선점→§13.1 재번호 0232→0235)
- Scope: 채팅 화면 새 대화(lazy_create) 첫 메시지의 진행 단계 폴링 시작 시점 수정. feature-0003(web-ui) **frontend-only** 단독.
- 배경: 사용자 보고 — 새 대화 첫 요청 시 작업 단계가 안 보이고 "시작 중" 만 표시. 진단 결과 step/사이드바 UI(TASK-0061)는 이미 존재하고, **데이터 공급 비대칭**이 근본원인. 기존 대화는 send 직전 `startProgressPolling()` 시작하지만(app.js:5476) 새 대화는 cid 가 `/api/ask` 응답 전까지 없어 폴링을 못 켜고, ask 블로킹 완료 후(run 종료 시점)에야 폴링 시작 → 처리 내내 "시작 중…".
- 변경:
  - `src/static/app.js`: lazy_create 의 early-cid 발급 분기를 **첨부 유무 무관 일반화**(기존 staged 첨부 있을 때만 `/api/new_conversation` 선호출하던 TASK-0106 분기). cid 확정 직후 `state.activeConversationId` 전환 + optimistic conversation entry 선등재 + `startProgressPolling({reset:true})` 즉시 시작. `earlyCidActivated` 플래그로 ask 실패 시 non-lazy 복구 경로(진행 중 run 추적) 분기. early-cid 발급 실패 시 기존 `lazy_create=true` 단일 호출 경로로 graceful fallback. 후처리 블록은 `pendingSentinel===busyKey` 가드로 중복 폴링 자연 차단.
  - `src/static/index.html`: 캐시버스터 `app.js?v=20260611-newconv-progress-steps`.
- 비변경: 백엔드 app.py·PG/웹 스키마·RBAC·엔드포인트·시크릿 0. step/progress 표시·"N단계 보기"→사이드바 UI(`renderPendingAssistantBubble`/`openStepSidePanel`/`#stepSidePanel`) 코드 무변경 — 데이터만 흐르면 자동 동작. `/api/new_conversation`·`/api/progress`·`/api/ask` API 계약 무변경. 병렬 worktree 가 app.py 점유 중이라 의도적으로 app.py 미수정.
- 검증: node --check app.js PASS + verify-completion PASS(9/9). 적대적 동시성 리뷰 REV-20260612-0235 CONCERN 2 흡수. **잔여**: web 재배포 + PB-0008 Windows-browser 시각검증.
- Files: src/static/app.js, src/static/index.html, docs/{FUNCTION,TASK,MODIFY,REVIEW,REPORT,TEST}.md, docs/reviews/20260612T000000Z-newconv-progress-concurrency.md, ../../docs/STATUS.md
- Rollback: 단일 함수(`sendPrompt`) 내 분기 일반화 + 캐시버스터. 되돌리면 staged 첨부 전용 early-cid 로 복귀(기존 동작). additive 한 state 전환만 추가됨.
- Cross-ref: TASK-0235 / REQ-20260611-0232 / REV-20260612-0235. (TASK-0061 실시간 step UI 후속 — 새 대화 경로 데이터 공급 보완.)
- Date: 2026-06-12 (TASK-0234, **Minor §12.3** — datasource UI 사용성 버그 2건, frontend-only)
- Scope: 멀티 datasource 1:N(TASK-0230) 배포 후 사용자 보고 2건. ① 연결 테스트 버튼이 바인딩 존재 시 무동작(드롭다운 add 모드 value=''), ② 선택 DB 가 어느 datasource 소속인지 불명. 권한/스키마/엔드포인트/백엔드 0.
- Files:
  - unit/feature-0003-agent-web-ui/src/static/admin.js (각 datasource 칩 per-chip ⟳ 연결테스트 + "접근 가능 데이터베이스" 헤더 datasource 배지 + 공용 버튼 안내 명확화 + reload 시 편집대상/배지 동기화)
  - unit/feature-0003-agent-web-ui/src/static/styles.css (`.admin-chip-action--ok/--fail`, `.admin-db-ds-badge`)
  - unit/feature-0003-agent-web-ui/src/static/admin.html (캐시버스터 `?v=20260612-ds-test-label`)
- 배경: ① 공용 "연결 테스트" 가 `dsSelect.value` 를 읽는데 TASK-0230 에서 바인딩 ≥1 이면 드롭다운이 "추가" 모드(value='')라 항상 빈 값 → 바인딩 datasource 테스트 불가. 백엔드 `/test` 엔드포인트는 정상(라이브 3/3 ok). ② 멀티 바인딩 시 DB 목록이 어느 datasource 것인지 라벨 없음.
- Rollback: 위 3파일 revert(frontend-only, 백엔드 영향 0).

## CHG-20260611-0233
- Date: 2026-06-11 (TASK-0233, **Minor §12.3** — datasource multi-bind UI 접근성 보강, frontend-only)
- Scope: TASK-0230 의 제품 상세 datasource multi-bind UI 를 gstack `/design-review` 소스 접근성 감사로 검토 후 HIGH 3 + MEDIUM 4 흡수. 권한/스키마/엔드포인트/백엔드 0.
- Files:
  - unit/feature-0003-agent-web-ui/src/static/admin.js (★/× 칩버튼 aria-label + disabled 중복요청 가드 + 두 select aria-label + 빈상태 CTA)
  - unit/feature-0003-agent-web-ui/src/static/styles.css (.admin-chip-action/.admin-chip-remove 24px 타깃 + :focus-visible + opacity)
  - unit/feature-0003-agent-web-ui/src/static/admin.html (캐시버스터 `?v=20260611-ds-multibind-a11y`)
- Rollback: 위 3파일 revert(frontend-only, 동작 영향 0 — 접근성 속성·CSS 만).
- Date: 2026-06-11 (TASK-0233, **Major §12.3** — 외부 LLM 비용 영향: 제품 프롬프트 "자동 작성" 결과 중간 잘림 해소; 동시세션 insight-reset cycle 이 TASK-0231/CHG-0231 선점→§13.1 재번호 0231→0232)
- 사용자 보고: `관리 콘솔 > 제품 > [각 제품] > 제품 프롬프트 > 자동작성` 텍스트가 글자 수 제한으로 중간 잘림.
- 근본 원인: `admin_generate_product_prompt` 가 출력 토큰 상한을 `max_tokens_for_model(llm_model, "summary")` 로 잡음 — `"summary"` 는 짧은 요약/토픽용 cap(Claude 7000 / 로컬 512). 웹 기본 모델 `claude-haiku-4` 기준 thinking budget(≤5000) 차감 후 실본문 ~2000 토큰 → 본문 잘림. `finish_reason` 미검사로 잘린 채 조용히 반환. 저장 컬럼(MEDIUMTEXT)·프론트 textarea(maxlength 없음)는 제약 아님.
- 변경 (feature-0003 측):
  - `src/app.py`: ① `admin_generate_product_prompt` 의 `max_tokens_for_model(..., "summary")` → `"prompt_gen"`, `timeout` 55→90s. ② LLM 응답 `choices[0].finish_reason == "length"` 검출 → `meta.truncated` 플래그 + `logging.warning`(model·max_tokens·product_id).
  - `src/static/admin.js`: 자동작성 핸들러가 `payload.meta.truncated` 시 metaEl 에 "출력 길이 제한 도달 — 잘렸을 수 있음, 재생성 권장" 경고 append + `.admin-meta-warn` 클래스.
  - `src/static/styles.css`: `.admin-meta.admin-meta-warn { color: var(--warning, #d97706); }` 신설(기존 디자인 토큰).
- 동반 변경 (feature-0002): `src/modules/model_catalog.py` 에 `"prompt_gen"` task cap 신설(Claude 20000 / 로컬 3072). agent-core MODIFY.md CHG-20260611-0233 참조.
- 비변경: RBAC 카탈로그·DB 스키마(`WebSystemPrompts.Content` MEDIUMTEXT 유지)·암호화·신규 엔드포인트·응답 shape(meta 에 `truncated` 키 추가 외) 무변경.
- 검증: agent-core 신규 5(prompt_gen cap 존재·summary 대비 단조성·thinking 차감 여유·로컬 4K 한도·tier 라우팅) + web-ui 신규 4(finish_reason 잘림 검출·meta.truncated 계약) = 9 PASS, model_catalog 기존 회귀 0, node --check admin.js PASS. 시각 동작은 PB-0008(배포 후) 확인.
- Files: src/app.py, src/static/admin.js, src/static/styles.css, tests/test_prompt_generate_truncation.py(신규), docs/{FUNCTION,REVIEW,TASK,MODIFY}.md
- Rollback: 위 3 src 파일 + model_catalog.py revert. cap 조정이라 데이터 마이그레이션 없음.

## CHG-20260611-0231
- Date: 2026-06-11 (TASK-0231, **Critical §12.3** — insight 분석 초기화 (접근 가능 DB 단위 삭제); 동시세션 SSRF·UI-통합·멀티datasource cycle 이 TASK-0228/0229/0230 선점→§13.1 재번호)
- Scope: 관리 콘솔 제품 상세 `접근 가능 데이터베이스 > insight 분석 완료율` per-DB 초기화 기능. 신규 RBAC 권한 + 엔드포인트 + 프런트. feature-0003(web-ui) 단독.
- 배경: 사용자 요청 — insight 분석이 잘못됐을 때 되돌릴 수단이 없었다. DB 단위로 PG insight(fact/rag/fingerprint)를 삭제하면 insight-worker 가 다음 cycle 에 자동 재분석한다.
- 변경:
  - `src/app.py`: ① RBAC `insight.reset`(group console, admin 한정 — `PERMISSION_DEFINITIONS` + `_ensure_seed_roles` admin catchup). ② `_resolve_product_insight_scope`(완료율 계산과 공유하는 datasource scope 해석 헬퍼 추출 + scope alias 집합 반환 — `_compute_product_insight_coverage` 도 이를 호출하도록 리팩터). ③ `_like_escape`/`_insight_reset_ds_heads`/`_insight_reset_fact_key_patterns`/`_insight_reset_kv_key_patterns`(저장 키 체계 정합 LIKE 패턴 — scope alias + live_schemas 기반, ESCAPE '\\'). ④ `POST /api/admin/products/{pid}/insight-reset`(라이브 카탈로그 (schema,table) 교집합으로 rag_objects 삭제 + audit start-event fail-safe + 단일 PG tx 4종 DELETE + complete-event + 완료율 캐시 무효화).
  - `src/static/admin.js`: `resetProductDbInsight`(dry-run 미리보기 → DB명 typed-confirm + 공유 제품 영향 경고 → 실삭제 → 완료율 새로고침) + TASK-0229 통합 DB 리스트(`redrawChips` 의 `cov-db-row`)에 per-DB "초기화" 버튼(`insight.reset` 권한자만).
  - `src/static/styles.css`: `.cov-db-reset` 위험색 버튼 + `cov-db-row` grid 6컬럼.
  - `src/static/admin.html`: 캐시버스터 `?v=20260611-db-coverage-insight-reset`.
- 비변경: PG/웹 스키마·시크릿·암호화·insight write 경로 무변경(read + targeted delete only). 기존 완료율 엔드포인트 동작 보존(_resolve 헬퍼 추출은 동치 리팩터).
- 검증: 신규 `tests/test_insight_reset.py` 14건 PASS + make test 505 passed/2 skipped(회귀 0) + ruff clean + py_compile + node --check + 라이브 PG 키패턴 매칭 실측. outside-voice 적대적 보안 리뷰 MAJOR 3(M1 MSSQL rag_objects 2-tier/M2 scope alias/M3 audit fail-safe) 흡수.
- Files: src/app.py, src/static/{admin.js,admin.html,styles.css}, tests/test_insight_reset.py, docs/{FUNCTION,TASK,REPORT,MODIFY,REVIEW}.md, ../../docs/STATUS.md
- Rollback: 신규 권한/엔드포인트/헬퍼는 additive. 프런트 버튼은 권한 게이트(미보유 시 미노출). 엔드포인트 미호출 시 기존 동작 무영향.
- Cross-ref: TASK-0231 / REQ-20260611-0228 / REV-20260611-0231. (TASK-0223 insight-coverage 후속, TASK-0229 UI-통합·TASK-0230 멀티datasource 위로 rebase.)

## CHG-20260611-0230
- Date: 2026-06-11 (TASK-0230, **Critical §12.3** — 멀티 datasource 1:N: 제품 ↔ 여러 datasource 참조)
- Scope: feature-0003 측 — 관리 평면(join 테이블·admin 엔드포인트·접근DB 차원화·제품 프롬프트 다중 datasource 인지) + UI(제품 상세 datasource 칩 multi-bind·편집 대상 선택기, 대화화면 다중 배지). 단일 바인딩·flag OFF 동작 0 변경.
- Files:
  - unit/feature-0003-agent-web-ui/src/app.py (`_ensure_web_product_datasources_schema` join 테이블+차원 마이그레이션 + `_list_product_datasources`/`_product_allowed_schemas_for_datasource` helper + admin GET/POST/DELETE `/products/{id}/datasources` + `_list_products`·`GET /api/admin/datasources`·`PUT databases` datasource 차원 + DELETE datasource 고아 정리 + `admin_generate_product_prompt` 다중 datasource ds-키·접근DB 그룹)
  - unit/feature-0003-agent-web-ui/src/static/admin.js (제품 상세 datasource 칩 multi-bind + 편집 대상 datasource 선택기 + 차원별 productDatabases pending 키)
  - unit/feature-0003-agent-web-ui/src/static/app.js (대화화면 다중 datasource 배지)
  - unit/feature-0003-agent-web-ui/src/static/styles.css (`.admin-chip--primary`/`.admin-chip-action`)
  - unit/feature-0003-agent-web-ui/src/static/{admin,index}.html (캐시버스터 `?v=20260611-product-multi-ds`)
  - unit/feature-0003-agent-web-ui/tests/test_product_multi_datasource_api.py (신규 7)
- 보안: admin 엔드포인트 console.access(+manage), 미등록 키 거부(400), audit. PUT databases 가 요청 datasource_key 바인딩 검증(임의 키 접근DB 주입 차단). 마이그레이션 loud(REV-0230 MAJOR-1). 런타임 격리는 agent-core `_DatasourceRouter`(CHG-20260611-0230 agent-core) 가 담당.
- Rollback: flag `AGENT_MULTI_DATASOURCE_ENABLED=0` 또는 제품 바인딩 1개 축소 시 기존 단일 경로 복귀. 코드 환원 시 위 파일 revert(join 테이블·차원 컬럼은 멱등 — 잔존해도 무해).
## CHG-20260611-0229
- Date: 2026-06-11 (TASK-0229, **Minor §12.3** — 관리 콘솔 제품 상세 "접근 가능 데이터베이스" UI 통합; 동시세션 SSRF cycle TASK-0228 선점→§13.1 재번호)
- Scope: frontend-only IA 재구성. 제품 상세의 (a) insight 분석 완료율 per-DB breakdown 리스트와 (b) 사용자 등록 DB chip 목록의 1:1 중복을 단일 통합 리스트로 융합 + (c) 시스템/메타데이터 고정 DB 다수 chip을 단일 묶음 칩(hover/focus 툴팁)으로 강등.
- 배경: 사용자 보고 — per-DB 완료율 행과 DB chip이 같은 DB를 두 번 표시(분리 의미 없음) + 시스템 DB 4종(MySQL)/3종(MSSQL)이 각각 chip이라 산만. gstack `/design-review` 메서드론(design subagent)으로 통합 스펙 도출. 데이터 정합 확인: 백엔드 `per_db` 집합 = 사용자 등록 DB(`_list_product_databases`)와 동일, 시스템 DB는 별도 출처(`metadata_schemas`)라 per_db 미포함 → 융합/분리가 데이터 모델과 정합.
- 변경:
  - `src/static/admin.js`: ① `buildProductCoverageDetail` → 요약 헤더+전체 진행 바로 축소(per-DB breakdown 제거). ② `buildDbCoverageCells(covRow, measuring)` 신설(통합 리스트 행의 마이크로바+통계+상태칩). ③ `buildSystemDbChip(lockedChips)` 신설(단일 묶음 칩 + title/aria-label/tabindex + hover·focus·focus-within 툴팁). ④ `redrawChips` 재작성(시스템 칩 + `per_db ↔ schema_name` 소문자 조인한 `cov-db-row` grid 리스트 + 빈 상태). ⑤ chipWrap 클래스 `admin-chip-wrap`→`cov-db-wrap`.
  - `src/static/styles.css`: `.cov-db-wrap`(flex column)/`.cov-db-list`/`.cov-db-row`(grid 5컬럼)/`.cov-microbar`+fill/`.cov-db-stat`/`.cov-db-status*`/`.cov-db-remove`(+spacer)/`.cov-db-list-empty`/`.sysdb-chip`+`-label`/`-tag`/`-tip`+`-title`/`-list` 신설·재구성. 기존 `.cov-db-list/.cov-db-row/.cov-db-name/.cov-db-stat` 정의 교체(단일 사용처). 디자인 토큰만 사용(신규 hex 0).
  - `src/static/admin.html`: 캐시버스터 styles.css·admin.js `?v=20260611-mssql-coverage-perdb`→`?v=20260611-db-coverage-unified`.
- 비변경: RBAC 카탈로그·DB 스키마·암호화·신규 엔드포인트·백엔드(app.py)·`/api/admin/products/insight-coverage` 응답 shape 무변경. 기존 per_db 데이터/draft chip 배열 그대로 사용.
- 검증: node --check admin.js PASS + CSS brace balance(1031/1031) + verify-completion PASS. 시각 동작은 PB-0008(배포 후) 확인.
- Files: src/static/admin.js, src/static/styles.css, src/static/admin.html, docs/{REPORT,REVIEW,TASK,MODIFY}.md
- Rollback: frontend 3파일 revert + 캐시버스터 환원. 백엔드 무관.

## CHG-20260611-0228
- Date: 2026-06-11 (TASK-0228, **Major §12.3** — datasource SSRF 사설망 경계 env 토글 + 의도적 비활성화)
- 사용자 보고: `관리 콘솔 > 데이터소스` 에서 새 데이터소스(host=`10.200.50.80`) 생성 시 "호스트 차단(SSRF): 사설/링크로컬 IP 차단(allowlist 필요): 10.200.50.80" 에러. **근본 원인**: `app._ssrf_check_host` 가 RFC1918 사설 IP 를 SSRF 방어로 차단(설계 의도, TASK-0205/0214). `10.200.50.80` 은 `10.0.0.0/8` 사설 대역이라 차단되며, 정당한 사내 host 는 `AGENT_DATASOURCE_HOST_ALLOWLIST` 에 등재해야 통과하는 구조. 코드 버그 아님 — 사내 운영 환경(대부분 사설망 IP)과 SSRF 방어 기본값의 불일치.
- 사용자 결정: SSRF 방어 구성을 **복원 가능한 형태로 보존(태그)** 하고 **현재는 사설 경계를 의도적으로 비활성화**. (사내 사설망 전면 운영 맥락 — 매 host allowlist 등재 부담 회피.)
- 변경:
  - `unit/feature-0003-agent-web-ui/src/app.py`:
    - `_ssrf_private_guard_enabled()` 신규 — `AGENT_DATASOURCE_SSRF_GUARD_ENABLED` env 파싱(기본 `1`=활성, secure-by-default; `0`/`false`/`no`/`off`=비활성).
    - `_ssrf_check_host()` — 사설/링크로컬/reserved/multicast 차단을 `private_guard` 분기 뒤로 이동. **메타데이터 IP 하드차단·DNS rebinding pin·빈 host 거부는 토글 무관 항상 유지**.
    - `GET /api/admin/datasources` 응답에 `ssrf_private_guard_enabled` 필드 추가(UI 안내 정합).
  - `static/admin.js`: `adminState.datasourcesSsrfPrivateGuard` + 안내 문구 분기(토글 OFF 시 "사설망 IP 허용, 메타데이터는 여전히 차단").
  - `static/admin.html`: admin.js 캐시버스터 `?v=20260611-ssrf-private-guard-toggle`.
  - `docs/DECISIONS.md` ADR-0030 (정본 + 복원 절차) / `docs/SECURITY.md` §11 (토글 정책 + 불변식) / `.env.secret.example` (토글 안내).
  - 신규 테스트 `unit/feature-0003-agent-web-ui/tests/test_ssrf_private_guard_toggle.py` (22 case: 토글 ON/OFF, 메타데이터 항상 차단, allowlist 공존, 파싱).
- 검증: py_compile + node --check PASS. 신규 22 PASS + datasource 회귀 29 PASS(회귀 0). 운영 `.env.secret` 에 `AGENT_DATASOURCE_SSRF_GUARD_ENABLED=0` 설정 + web 재배포는 배포 단계.
- Cross-ref: TASK-0228 / REQ-20260611-0228 / ADR-0030 / SECURITY §11. (TASK-0205/0214 SSRF 가드 후속.)

## CHG-20260611-0223
- Date: 2026-06-11 (TASK-0223, **Major §12.3** — 제품 프롬프트 자동작성 실데이터 정합 + MSSQL database-aware 3계층 인사이트 + ask-worker grounding 검증)
- Scope: 자동 생성 프롬프트가 실제 DB 인사이트에 근거하도록 매칭 로직 재작성(MySQL) + MSSQL database.schema.table 3계층 인사이트 파이프라인 신설(insight-worker 스캔 → fact_key → 엔드포인트/grounding 매칭). feature-0002(agent-core) + feature-0003(web-ui) 교차 변경.
- 배경: ① 자동작성 프롬프트가 없는 테이블(`play_log` 등)을 날조 — `source_type` 컬럼이 전부 `schema_insight`(신뢰불가, 실 종류는 fact_key 접두) + `scope_key`가 전부 `common`(ILIKE 매칭 0건)이라 인사이트 통째 누락. ② MSSQL 3계층 미지원 — insight-worker가 `dbo` 단일 DB만 스캔 + fact_key에 database 누락 → 제품 등록 DB와 매칭 불가.
- 변경:
  - `src/app.py` `admin_generate_product_prompt`: fact_key 접두로 종류 판별 + `regexp_replace`로 ds 접두 정규화 후 제품 접근 스키마/DB명 정확 매칭(boundary, substring 아님). MSSQL 3계층 segment 분기 렌더. datasource 교차노출 차단(제품 `DatasourceKey`→`_generate_datasource_key` scope_key 필터 + 무접두 레거시 허용). LLM 지시문 강화(실 인사이트만·날조 금지). 응답 `meta`(schema_insight_count/table_insight_count/topic_count/grounded). **+ `_log` F821 hotfix**(`_log.getLogger`→`logging.getLogger(__name__)` — TASK-0216 머지본 잠복 NameError).
  - `src/static/admin.js`: "자동 작성" 응답 meta 충실도 표시(grounded 시 스키마/테이블/주제 건수, 미수집 시 안내).
- 비변경: RBAC 카탈로그·시크릿·웹 스키마 무변경. 기존 `product.manage` 권한 재사용. PG 읽기 전용.
- 검증: pytest 444 passed/2 skipped(회귀 0) + py_compile + 라이브 end-to-end(MySQL 킹스레이드 138테이블·MSSQL 제품 60테이블 grounded·교차노출 0·ask-worker grounding 정상).
- Files: src/app.py, src/static/admin.js, (agent-core) modules/{config,insight,utils,schema}.py, agent_core.py, tests/test_mssql_three_tier_insight.py, 양 feature docs
- Rollback: 엔드포인트/헬퍼는 additive. ds_object_suffix가 active_database 미설정 시 2계층(MySQL 동치)이라 MSSQL 미사용 환경 무영향.

## CHG-20260611-0218
- Date: 2026-06-11 (TASK-0218, **Major §12.3** — 관리 콘솔 대시보드 CloudWatch 스타일 재구성)
- Scope: TASK-0210 위젯 그리드를 AWS CloudWatch 류 사람-친화 운영 대시보드로 재구성. gstack `/design-review` + cross-model(Codex+subagent) 디자인 감사(REV-20260611-0218) 반영.
- 변경:
  - `src/app.py` `_dash_widget_*`: ① 시간 위젯에 `days` 윈도우 전파(accounts/audits/conversations — 거짓 컨트롤 정직화). ② 주 metric `primary` 플래그. ③ 시계열 위젯(audits/conversations/usage)에 전기간 대비 `delta_pct`+`delta_sentiment`(neutral/bad) + 일별 `spark` 배열. ④ 위젯에 `tab`(drill-down 대상). 신규 helper `_dash_pct_delta`/`_dash_fill_daily`(UTC gap-fill, ≤60점). `_DASHBOARD_WIDGETS` 카탈로그 활동-우선 재편(conversations/usage/audits 상단). usage 주 metric=추정비용.
  - `src/static/admin.js`: toolbar(`dashboardRefreshBtn` 수동 새로고침 + `dashboardAutoRefresh` off/30/60s + `dashboardUpdated` 마지막 갱신) + `_setDashboardAutoRefresh`/`_updateDashboardMeta`. `buildDataWidgetBody` 주(크게+델타배지+sparkline)/보조(작게) 위계 + Top-N 비율막대(`--bar`). `_dashSparkline`(순수 SVG)·`_dashDeltaBadge`(의미별 색). fail-loud(`_buildDashboardErrorBanner` 전체 + 위젯 단위 재시도, `dashboardError` 상태). drill-down(`dashboard-widget-open`→`switchTab`). native HTML5 drag reorder(`reorderWidgetBefore`)+↑↓ 키보드 폴백. 접근성(card role/aria-label, move/vis/open aria-label, aria-pressed). adminState 필드 추가.
  - `src/static/admin.html`: toolbar 재구성(마지막갱신·기간·auto-refresh·새로고침·편집), `#dashboardWidgets` aria-live, 캐시버스터 `?v=20260611-dashboard-cloudwatch`.
  - `src/static/styles.css`: `.dashboard-primary*`/`.dashboard-secondary`/`.dashboard-delta`/`.dashboard-spark`/`.dashboard-list-row::after`(비율막대)/`.dashboard-error-banner`/`.dashboard-widget-error`/`.dashboard-widget-open`/drag 상태/`:focus-visible` 포커스 링. widget radius `--r-lg`→`--r-md`, 8px 그리드 정돈, 소형 라벨 `--text-muted`→`--text-2`(대비).
  - `tests/test_dashboard_overview.py`: +6(델타·gap-fill·카탈로그 활동-우선·window 전파) = 17.
- 비변경: RBAC 권한 카탈로그·시크릿·DB 스키마(웹·agent_runtime)·신규 엔드포인트 0. overview/preferences 응답 shape 확장(추가 필드)만. 추세/sparkline·window 는 비파괴 read(기존 컬럼/시계열).
- 검증: make test MAKE_EXIT=0(신규 6 포함 전체 PASS, 회귀 0) + node --check + py_compile + (내 코드) ruff 클린. **잔존(내 코드 아님)**: app.py:14133 `_log` F821(동시세션 TASK-0216 머지본 잠복 버그) — flag only.
- Files: unit/feature-0003-agent-web-ui/src/app.py, .../static/{admin.js,admin.html,styles.css}, .../tests/test_dashboard_overview.py, docs/{TASK,MODIFY,REVIEW,REPORT,FUNCTION,TEST}.md, ../../docs/STATUS.md
- Rollback: 추가 필드/helper/toolbar 는 additive. admin.js 대시보드 함수군·styles `.dashboard-*` 를 TASK-0210 버전으로 환원하면 위젯 그리드 v1 로 복귀(백엔드 추가 필드는 무시되어도 무해).

## CHG-20260611-0216
- Date: 2026-06-11 (TASK-0216, **Minor §12.3** — 제품 프롬프트 자동 작성 품질 강화)
- Scope: `POST /api/admin/products/{product_id}/prompt/generate` 엔드포인트 신규 추가 — DB 구조 인사이트(fact_entries 4종) + 사용자 대화 주제 패턴(topic 최신 50개) + 실제 사용 사례 요약(summary 최신 5개)를 LLM 컨텍스트로 구성해 시스템 프롬프트 자동 생성. 관리 콘솔 제품 상세 화면에 "자동 작성" 버튼 추가.
- 배경: 기존 자동 작성 엔드포인트 미존재 — 운영자가 제품 프롬프트를 수동 작성하던 구조. insight-worker가 축적한 팩트(schema_insight/table_insight/search_pref/insight)와 실제 사용자 대화 주제·요약을 활용하면 LLM이 더 정확하고 실무 적합한 프롬프트를 생성 가능.
- 변경:
  - `src/app.py`: `POST /api/admin/products/{product_id}/prompt/generate` 엔드포인트 추가. MySQL에서 제품/DB 스키마 조회, PG에서 fact_entries(4종) + core_conversations.topic(최신 50) + summary(최신 5) 조회 후 knowledge_block 구성 → LLM 호출(model/max_tokens/temperature 동적). 권한: `product.manage`.
  - `src/static/admin.js`: `buildSystemPromptEditor`에 `autoGenerateProductId` 파라미터 + "자동 작성" 버튼 추가(생성 중 disabled). `renderProductDetail`에서 `autoGenerateProductId: Number(product.id)` 전달. 불필요 hint 문자열("이 제품에만 적용됩니다.") 제거.
- 비변경: RBAC 카탈로그·스키마·시크릿 무변경. 기존 `product.manage` 권한 재사용. fact_entries/core_conversations/summary 읽기 전용(쓰기 없음).
- 검증: py_compile PASS + curl 실제 LLM 호출 성공(킹스레이드 product_id=1, 한국어 시스템 프롬프트 정상 생성).
- Files: unit/feature-0003-agent-web-ui/src/app.py, unit/feature-0003-agent-web-ui/src/static/admin.js, docs/{TASK,MODIFY,REVIEW}.md
- Rollback: 신규 엔드포인트는 additive — 미사용 시 무영향. admin.js의 버튼 제거 및 엔드포인트 삭제로 원복.

## CHG-20260611-0210
- Date: 2026-06-11 (TASK-0210, **Major §12.3** — 관리 콘솔 대시보드 보강)
- Scope: 빈약한 관리 콘솔 대시보드("운영 현황")를 카테고리별 위젯 그리드 + per-account 커스터마이즈(표시/순서) + 서버 영속으로 재구성. RBAC-스코프 집계 엔드포인트 + 본인 한정 prefs self-service.
- 배경: 기존 대시보드는 계정 metric 6개 + 권한 drift + pending 만 표시했고 전부 클라이언트 `adminState.accounts` 배열을 필터링해 계산(서버 집계 없음 → 계정/데이터 증가 시 비확장). 관리 콘솔 8개 카테고리 중 계정·역할만 일부 노출하고 제품/데이터소스/감사/사용량/대화는 통째 미노출.
- 변경:
  - `src/app.py` `_ensure_web_tables()`: `WebDashboardPreferences(AccountId BIGINT PK, Content MEDIUMTEXT, UpdatedAt, CreatedAt)` 멱등 CREATE 추가(MySQL, 웹테이블군 정합, alembic 무).
  - `src/app.py` `_runtime_tables_available()`: 두 probe 블록(postgres-backend + 기본) table 목록에 `WebDashboardPreferences` 추가 — TASK-0047 패턴. 기존 DB 배포 시 fast-path(`_schedule_memory_runtime_bootstrap`)가 신규 테이블 부재(errno 1146)를 감지해 우회하고 `_ensure_web_tables()` 의 멱등 CREATE 를 1회 실행하게 한다(누락 시 신규 테이블이 영원히 안 생기는 함정 — 라이브 배포 중 포착·수정).
  - `src/app.py` 신규 블록(`# TASK-0210` 배너): 위젯 카탈로그 `_DASHBOARD_WIDGETS`(key/title/permission/source) + `_dashboard_default_prefs`/`_sanitize_dashboard_prefs`/`_load_dashboard_pref_row`/`_save_dashboard_pref_row` + `_dash_widget_{accounts,roles,products,datasources,audits,conversations,usage}` 7종 + `GET /api/admin/overview`(RBAC-스코프, 위젯별 try/except 격리, PG 연결 permitted 시만 open, `days` clamp 후 interval) + `GET/PUT /api/admin/dashboard/preferences`(actor.id self-service, console.access 게이트).
  - `src/static/admin.js`: `renderDashboard` 재작성(overview+prefs fetch → 위젯 그리드) + `loadDashboardOverview`/`_dashboardRenderOrder`/`renderDashboardWidgets`/`buildWidgetCard`/`buildDataWidgetBody`/`buildPendingWidgetBody` + 편집(`setWidgetVisible`/`moveWidget`)·영속(`saveDashboardPrefs`/`resetDashboardPrefs`)·`wireDashboardControls`. adminState 에 overview/dashboardPrefs/dashboardEditMode/dashboardWindow 등 추가.
  - `src/static/admin.html`: 대시보드 pane 을 위젯 그리드(`#dashboardWidgets`) + 집계기간 select(`#dashboardWindow`) + 편집 toolbar/edit-bar 로 교체. 캐시버스터 `?v=20260611-dashboard-widgets`(styles.css·admin.js).
  - `src/static/styles.css`: `.dashboard-toolbar/.dashboard-edit-bar/.dashboard-widgets/.dashboard-widget*/.dashboard-metric*/.dashboard-list-*` 추가(기존 디자인 토큰 재사용).
  - `tests/test_dashboard_overview.py`: 신규 11 테스트(overview RBAC 스코프 operator/admin·403·client 위젯 catalog·sanitize·기본값·영속 round-trip).
- 비변경: 권한(RBAC) 카탈로그·시크릿·웹 외 스키마(agent_runtime 등)·기존 엔드포인트 무변경. 기존 권한(console.access/console.usage.read/audit.read.any) 재사용 + prefs 는 self-service.
- 검증: make test MAKE_EXIT=0 전체 PASS(신규 11, 회귀 0) + node --check admin.js + py_compile + ruff. outside-voice 적대적 보안리뷰 SHIP-ABLE BLOCKER/MAJOR 0(REV-20260611-0210), MINOR 1(PUT 예외 텍스트 노출) 흡수.
- Files: unit/feature-0003-agent-web-ui/src/app.py, unit/feature-0003-agent-web-ui/src/static/{admin.js,admin.html,styles.css}, unit/feature-0003-agent-web-ui/tests/test_dashboard_overview.py, docs/{TASK,MODIFY,REVIEW,REPORT}.md, ../../docs/STATUS.md
- Rollback: 신규 엔드포인트/테이블/위젯은 additive — 미사용 시 무영향. admin.js `renderDashboard` 및 admin.html 대시보드 pane 을 이전 metric-card 버전으로 환원하면 UI 원복(WebDashboardPreferences 테이블은 잔존해도 무해).

## CHG-20260610-0200
- Date: 2026-06-10 (TASK-0200, **Minor §12.3** — 읽기경로 정렬 교정)
- Scope: REV-20260610-0196 이 지적한 MINOR 잔존(수용 항목) 실행 — `_collect_matched_excerpts` 발췌 선택 정렬. (#1 convo_search LIKE escaping 은 feature-0002 CHG-20260610-0200.)
- 배경: conv 별 "가장 최근 매칭 1건" 을 `ROW_NUMBER() OVER (PARTITION BY cid ORDER BY msg_id DESC)` 로 골랐는데, UNION 양변 `agent_runtime.messages.id` / `core_messages.id` 가 독립 IDENTITY 시퀀스라 cross-table id 비교가 chronological 과 어긋날 수 있었다(어느 대화가 매칭되는지엔 무관, 어느 메시지 본문을 스니펫으로 보일지에만 영향).
- 변경 ([src/app.py](../src/app.py) `_collect_matched_excerpts`): UNION 내부 subquery 가 `msg_id` 대신 두 table 공통 `created_at`(PG timestamptz / MySQL CreatedAt·created_at) 을 선택하고 `ROW_NUMBER() OVER (… ORDER BY created_at DESC)` 로 정렬. PG 분기 + MySQL legacy 분기 + docstring 모두 갱신.
- 비변경: 매칭 집합·후처리(line-based 발췌 클리핑)·RBAC·스키마·응답 계약 무변경. ESCAPE/ILIKE 등 기존 로직 유지.
- 검증: `tests/test_cutover_routing_gaps.py` T1 에 `ORDER BY created_at DESC` 존재 + `msg_id` 정렬 부재 단언. make test exit=0. outside-voice [SKIPPED:minor-ordering-implements-REV-0196] (REV-20260610-0200).
- Files: unit/feature-0003-agent-web-ui/src/app.py, unit/feature-0003-agent-web-ui/tests/test_cutover_routing_gaps.py, docs/{TASK,MODIFY,REVIEW,FUNCTION}.md
- Rollback: 정렬 키를 `msg_id DESC` 로 환원(기능 무관, 스니펫 선택만 이전 동작).

## CHG-20260610-0197
- Date: 2026-06-10 (TASK-0197, **Minor §12.3** — 프런트 UI 소요시간 표시)
- Scope: assistant 말풍선 타임스탬프 옆 소요시간 표시. `message.meta.duration_ms`(agent_core `mirror_meta` 저장값)가 있는 assistant 메시지에 한해 기존 `formatElapsed()` 재사용, `.message-meta-duration` span 추가.
- 변경:
  - `src/static/app.js` (`renderMessages`): durationMs > 0 일 때 speaker·datetime 텍스트노드 + `<span class="message-meta-duration">N분 M초</span>` 구성. 0이거나 user 메시지면 기존 `textContent` 방식 유지.
  - `src/static/styles.css`: `.message-meta-duration { font-size: 10px; opacity: 0.7; }` 추가.
  - `src/static/index.html`: 캐시버스터 `?v=20260610-response-duration` 갱신(styles.css·app.js).
- 비변경: 백엔드(app.py)·API·DB 스키마·RBAC·시크릿 무변경.
- 검증: node --check app.js PASS. 시각 검증 = Windows-browser(PB-0008) 배포 후.
- Files: unit/feature-0003-agent-web-ui/src/static/{app.js,styles.css,index.html}, docs/{TASK,MODIFY,REVIEW}.md
- Rollback: 본 cycle 커밋 revert — assistant 말풍선에서 소요시간 표시 사라짐.

## CHG-20260610-0196
- Date: 2026-06-10 (TASK-0196, **Minor §12.3** — 백엔드 읽기/쓰기경로 라우팅)
- Scope: AR-M5 cutover 잔존 라우팅 누락 web 3건 복구(대화 제목 변경·관리자 제품 삭제·검색 발췌). TASK-0189 와 동일 결함 class(삭제된 MySQL 테이블을 PG 게이트 없이 조회) 전 서비스 스윕의 web 산물.
- 배경: cutover 로 `AgentCoreConversations`/`AgentMemoryMessages`/`AgentCoreMessages` 등 MySQL 테이블 DROP. 전 코드 스윕(SQL 컨텍스트에서 삭제 테이블을 조회하면서 `AGENT_RUNTIME_READ_BACKEND`/`_pg_connect`/`agent_runtime.` 지표가 함수 내 전무한 함수 추출) + 정적·라이브 검증으로 결함 4건 확정(false positive 제거: KB 게이트 dual-path·caller 라우팅·docstring·information_schema).
- 변경 ([src/app.py](../src/app.py)):
  - `rename_conversation_title`(`PATCH /api/conversations/{id}/title`): raw `UPDATE AgentCoreConversations`(삭제 테이블→**라이브 500**, 재현 확인) → 이미 PG 라우팅된 게이트 헬퍼 `_conv_update_topic(conn, cid, title)`(PG `agent_runtime.core_conversations`) 호출로 교체 + try/except→500.
  - `admin_delete_product`(`DELETE /api/admin/products/{id}`): 참조 가드 `SELECT COUNT(*) FROM AgentCoreConversations WHERE product_id`(→**라이브 500**, 재현 확인) 를 `_runtime_backend_is_pg()` 분기로 PG `agent_runtime.core_conversations` COUNT 라우팅(legacy MySQL else). cursor 는 분기별 자체 정리, 후속 Web* 삭제 autocommit 트랜잭션은 conn 그대로 사용(영향 0).
  - `_collect_matched_excerpts`(검색 발췌): `AgentMemoryMessages UNION AgentCoreMessages`(except→{} 로 스니펫 **항상 빈칸**) → `_runtime_backend_is_pg()` 분기로 PG `agent_runtime.messages` UNION ALL `core_messages`(`ROW_NUMBER() OVER (PARTITION BY cid ORDER BY msg_id DESC)`, `ILIKE … ESCAPE '!'` — MySQL utf8mb4_unicode_ci case-insensitive 패리티) 라우팅. 후처리(line-based 발췌 클리핑)는 DB 무관(rows(cid, content) 동일). legacy MySQL else 보존. params 튜플 양 분기 공유.
- 비변경: RBAC(엔드포인트 기존 게이트 `_account_can_access_conversation`/`_account_has_permission` 유지)·스키마·시크릿·프런트 무변경.
- 검증: 신규 `tests/test_cutover_routing_gaps.py`(T1 excerpts·T2 _conv_update_topic PG 라우팅 + 삭제 테이블 미접촉 가드). make test exit=0. outside-voice REV-20260610-0196.
- Files: unit/feature-0003-agent-web-ui/src/app.py, unit/feature-0003-agent-web-ui/tests/test_cutover_routing_gaps.py, docs/{TASK,MODIFY,REVIEW,FUNCTION}.md
- Rollback: 본 cycle 커밋 revert — 3 면이 다시 삭제된 MySQL 테이블 조회(rename·제품삭제 500, 발췌 빈칸).
- Cross-ref: convo_search(agent-core) 동일 cutover 복구는 feature-0002 CHG-20260610-0196.

## CHG-20260610-0189
- Date: 2026-06-10 (TASK-0189, **Minor §12.3** — 백엔드 읽기경로 라우팅)
- Scope: 날짜기준표 캘린더의 "대화 구간 이동"(날짜/시각 점프) 기능 복구. AR-M5 cutover 라우팅 누락 수정.
- 배경: 메시지 정본이 MySQL `AgentMemoryMessages` → PG `agent_runtime.messages` 로 cutover 되며 MySQL 테이블이 DROP(AR-M5). 메시지 목록(`_get_history`)·`_load_latest_assistant_message` 는 `AGENT_RUNTIME_READ_BACKEND` 게이트로 PG 라우팅 이전됐으나, 캘린더 backing 2개 엔드포인트(`/api/history_dates`·`/api/history_anchor`)는 이전에서 **누락**돼 삭제된 MySQL 테이블을 직접 조회 → `history_dates` 는 except 폴백으로 항상 `{"dates": {}}`(캘린더에 선택 가능한 날짜 없음 = 기능 누락), `history_anchor` 는 500. 프런트(app.js) 캘린더 로직(`openHistoryCalendarAt`/`renderHistoryCalendar`/`jumpToHistoryAnchor`)은 정상.
- 변경 ([src/app.py](../src/app.py)):
  - `history_anchor`: `AGENT_RUNTIME_READ_BACKEND == "postgres"` 일 때 PG `agent_runtime.messages` 에서 `id, created_at` 을 `to_char(created_at,'YYYY-MM-DD HH24:MI') <= left(%s,16)`(세션 tz wall-clock **분 단위** 문자열 비교) 기준 최신 1건 조회, 없으면 최초 1건 폴백. 반환 `message_id` 는 `_get_history` PG 분기가 DOM 에 부여한 PG id(`message-<id>`)와 동일 id-space → 점프 타겟 매칭. **분 단위 비교 이유**: 프런트 at 은 분 라벨에 `:00` 을 붙인 값(`YYYY-MM-DD HH:MM:00`)이고 실제 created_at 초는 0 이 아니라, 초 단위(`HH24:MI:SS <= ...:00`)면 클릭한 분의 메시지가 제외돼 직전 메시지로 점프하는 결함(원본 MySQL `CreatedAt <= when` 의 잠재 결함)이 생긴다 → 분 단위로 클릭한 분의 (마지막) 메시지에 정확 착지(라이브 검증). legacy MySQL 경로는 else 유지.
  - `history_dates`: 동일 게이트로 `to_char(created_at,'YYYY-MM-DD')` 그룹 + `string_agg(to_char(created_at,'HH24:MI') ORDER BY created_at)` 로 날짜별 시각 라벨 조립(원본 `DATE(CreatedAt)` + `GROUP_CONCAT(DATE_FORMAT(...,'%H:%i'))` 등가). legacy MySQL 경로 else 유지. history_anchor 와 동일 `to_char` 기준이라 라벨·점프 매칭 상호 일관.
  - 두 분기 모두 미사용 `_connect_memory()` conn 을 모든 return 경로(성공·무행·예외)에서 정확히 1회 close.
- 비변경: RBAC(엔드포인트는 기존 `_require_account` + `_resolve_conversation_for_account` 유지)·스키마·시크릿·프런트 무변경. 파괴적 연산 0(읽기 전용).
- 검증: 신규 `tests/test_history_calendar_pg_routing.py`(T1 PG 라우팅+삭제 테이블 미접촉 가드, T2 PG id 반환, T3 legacy back-compat). make test(컨테이너 pytest+ruff) exit=0. outside-voice 적대적 백엔드/QA 검토 REV-20260610-0189 — MAJOR 2건 제기됐으나 라이브 실측으로 무력화(① PG 세션 tz=Asia/Seoul=브라우저 KST → 날짜키 skew 없음, ② core-only 대화 0건 → core-fallback id-space gap 미발생).
- Files:
  - unit/feature-0003-agent-web-ui/src/app.py (`history_anchor`·`history_dates` PG 라우팅 분기)
  - unit/feature-0003-agent-web-ui/tests/test_history_calendar_pg_routing.py (신규 회귀 테스트)
  - unit/feature-0003-agent-web-ui/docs/TASK.md, MODIFY.md, REVIEW.md
- Rollback: 본 cycle 커밋 revert — 두 엔드포인트가 다시 MySQL `AgentMemoryMessages` 만 조회(= 캘린더 점프 재차 무력화).

## CHG-20260610-0189-SUGGESTIONS
- Date: 2026-06-10 (TASK-0189 근본원인 형제 인스턴스, **Minor §12.3** — 백엔드 읽기경로 라우팅)
- Scope: `/api/suggestions`(입력 추천: 최근 사용자 프롬프트 목록) — CHG-0189 와 동일 AR-M5 cutover 라우팅 누락으로 라이브 **HTTP 500**.
- 배경: TASK-0189 root-cause("cutover 시 미이전 엔드포인트") 자동 스윕(게이트 없이 `AgentMemoryMessages`/`AgentCoreMessages` 직접 조회 + PG 헬퍼 미사용 라우트 함수 탐지)에서 발견. `suggestions` 는 `SELECT Content FROM AgentMemoryMessages WHERE Role='user' …` 을 try/except 없이 실행 → 삭제된 테이블 조회로 예외 전파 → 500(입력 추천 기능 전면 사망). 라이브 재현 확인(MySQL `AgentMemoryMessages` 부재 + `/api/suggestions` 500).
- 변경 ([src/app.py](../src/app.py) `suggestions`): `AGENT_RUNTIME_READ_BACKEND == "postgres"` 일 때 PG `agent_runtime.messages` 에서 `SELECT content … WHERE role='user' AND conversation_id IN (…) ORDER BY created_at DESC LIMIT %s` 조회. legacy MySQL 경로는 else 보존. 추가로 조회 전체를 try/except 로 감싸 예외 시 빈 `rows`(=빈 items) fail-soft — 함수 기존 계약(`{"items": []}` 으로 degrade)과 정합.
- 비변경: RBAC(`conversation.ask` 게이트 유지)·응답 계약·스키마 무변경.
- 검증: 회귀 테스트 T4(`tests/test_history_calendar_pg_routing.py` — PG 라우팅 + 삭제 테이블 미접촉 가드). make test exit=0. 재배포 후 `/api/suggestions` 라이브 200.
- Files: unit/feature-0003-agent-web-ui/src/app.py (`suggestions` PG 라우팅 + fail-soft), tests/test_history_calendar_pg_routing.py (T4)
- Rollback: 본 변경 revert — `/api/suggestions` 가 다시 삭제된 MySQL 테이블 조회(500).

## CHG-20260610-0188
- Date: 2026-06-10 (TASK-0188, **Minor §12.3** — frontend-static-only)
- Scope: 공유 대화 페이지(`/share/{token}`)의 메시지 본문 markdown 미적용 수정 + 수신자 입장 가독성 디자인 보강.
- 배경: 사용자 보고 — 공유 링크로 전달받은 대화가 markdown 미적용 raw 텍스트(`**`, `|`, `#`, 코드펜스 그대로)로 보임. 근본 원인: 메인 채팅 UI(`app.js markdownToHtml`)는 `vendor/marked.umd.js` + `vendor/purify.min.js`(marked.parse → DOMPurify.sanitize)로 렌더하는데, 공유뷰는 ① `share.html` 이 두 라이브러리를 미로드하고 ② `share.js renderMessage` 가 `content.textContent = msg.content` 로 평문 렌더 → markdown 구문이 문자 그대로 노출.
- 변경:
  - [src/static/share.html](../src/static/share.html): `share.js` 앞에 `vendor/marked.umd.js` + `vendor/purify.min.js` 로드. css/js 링크 캐시버스터 `?v=20260610-share-md`. 헤더에 브랜드 라벨(`.share-brand`) + "링크 복사" 버튼(`#shareCopyLinkBtn`).
  - [src/static/share.js](../src/static/share.js): `renderMessage` 가 `renderMarkdownContent()` 호출 — 메인과 동일 marked+DOMPurify 파이프라인(라이브러리 부재 시 `.share-content-plain` 평문 폴백). ` ```sql ` 코드블록 "쿼리 보기" 토글 이식(`collapseSqlCodeBlocks`), 본문 외부 링크 `target=_blank rel="noopener noreferrer nofollow"`(`markExternalLinks`), 역할 배지(사용자/어시스턴트), `setupCopyLink`(clipboard API + textarea execCommand 폴백).
  - [src/static/share.css](../src/static/share.css): `.share-message-content` 에서 `white-space:pre-wrap` 제거(렌더 HTML) → 폴백 클래스에만 보존. 렌더 markdown 요소 스타일(제목 h1~h4, ul/ol/li, blockquote, 인라인/블록 code, **GFM 표**, hr, img, a, strong/em) + 역할 배지 + 메시지 좌측 accent border + 반응형(≤600px) + 인쇄/PDF 스타일시트(actions/footer 숨김, SQL 토글 펼침, pre 줄바꿈) + `.share-brand`/`.share-copy-link-btn`/`.share-sql-toggle-*`.
- 비변경: 백엔드(app.py)·공유 API(`/api/public/share/*`)·redaction·RBAC·DB 스키마·시크릿 무변경. 익명 페이지 XSS 표면은 메인 앱과 동일한 DOMPurify.sanitize 로 차단(데이터 노출 정책 무변경). node --check share.js PASS. 시각 검증 = Windows-browser(PB-0008) 배포 후.

## CHG-20260610-0186-MDTABLE
- Date: 2026-06-10 (TASK-0186 후속, **Minor §12.3** — frontend-only)
- Scope: CHG-20260610-0186 보강 — 표로 렌더되는 단계 결과 범위를 `execute_sql` 외 **전 도구**로 확장.
- 배경: 0186 은 `result_summary.preview_table`(구조화)이 있는 `execute_sql` 만 표로 렌더했는데, 라이브 `/api/progress` 확인 결과 `get_sample_rows`/`describe_table` 등은 `preview_table` 없이 markdown 표 **문자열**(`preview`)만 가짐 → 여전히 raw `<pre>` 노출(사용자 스크린샷이 바로 `get_sample_rows` raw md).
- 변경 ([src/static/app.js](../src/static/app.js)):
  - `parseMarkdownTablePreview(text)` 신규 — markdown 표 문자열(`| a | b |\n|---|---|\n| 1 | 2 |`)을 `{columns, rows}` 로 파싱(연속 `|` 라인 블록만, 2번째 줄 구분선 검증, 이후 "(N 행)"/"CSV 저장" 등 trailing 무시). 표 아니면 null.
  - `buildStepDetailEl` 결과 우선순위: ① `preview_table` → `buildResultTable` ② `preview` markdown 파싱 → `buildResultTable` ③ raw `<pre>` 폴백(비표형 list_schemas 등). 캐시버스터 `?v=20260610-step-md-table`.
- 비변경: 백엔드/RBAC/스키마/엔드포인트 무변경. XSS: 파싱값은 `buildResultTable` 의 `textContent`. node --check PASS. outside-voice [SKIPPED:frontend-only] (REV-20260610-0187).

## CHG-20260610-0186
- Date: 2026-06-10 (TASK-0186, **Minor §12.3** — frontend-only, web-ui 정적자산만)
- Scope: 실행 단계 사이드 패널(`단계 보기(N)`) ① 결과를 raw 마크다운 텍스트 → HTML 표 렌더링 ② 패널 너비 드래그 리사이즈.
- 배경: TASK-0173 이후 사이드 패널 결과가 `step.result_summary.preview`(markdown 문자열)를 `<pre>` 로 raw 출력 → 가독성 낮음. 단계 데이터엔 이미 구조화된 `preview_table`(columns/rows, `buildSqlStepPanel` 이 쓰는 것과 동일)이 포함돼 있어 백엔드 변경 없이 표로 렌더 가능.
- 변경:
  - [src/static/app.js](../src/static/app.js):
    - `buildStepDetailEl` 결과 블록: `result_summary.preview_table.columns` 가 있으면 기존 `buildResultTable(pt)`(행번호·헤더·hover, `.result-table-wrap` overflow:auto·max-height) 로 표 렌더, 없으면 `preview` 문자열 `<pre>` 폴백(describe 등 비표형 결과 호환).
    - 패널 리사이즈: `setupStepSidePanelResize()`(좌측 핸들 드래그 → 너비 = `innerWidth − clientX`, clamp [300, 92vw], localStorage `web.stepSidePanel.width` 영속, mouse+touch) + `_applyStepSidePanelWidth()` 를 `openStepSidePanel` 에서 호출(저장 너비 복원, 핸들 1회 배선 가드).
  - [src/static/index.html](../src/static/index.html): 패널 첫 자식에 `#stepSidePanelResizer`(role=separator) 추가. 캐시버스터 `?v=20260610-step-panel-table`.
  - [src/static/styles.css](../src/static/styles.css): `.step-side-panel` 에 min/max-width + `.is-resizing`(transition 제거·user-select 차단) + `.step-side-panel-resizer`(ew-resize 핸들, hover/드래그 시 primary 색 표시).
- 비변경: 백엔드(app.py/agent_core)·RBAC·스키마·엔드포인트·시크릿 무변경. `preview_table` 은 이미 `/api/progress` step 데이터에 포함. XSS: `buildResultTable` 은 `textContent` 사용.
- 게이트: node --check app.js PASS. outside-voice [SKIPPED:frontend-only] (REV-20260610-0186). 시각 검증=Windows-browser(PB-0008).

## CHG-20260610-0181
- Date: 2026-06-10
- TASK-Cycle: TASK-0181, **Minor §12.3** — 역할/계정 차트 모델별 stacked + 상세 표 요청(메시지) 수
- Summary: (A) 역할별·계정별 [토큰|비용] 막대를 모델별 누적(stacked)으로 분해(모델 색 일관). (B) 작업 화면 요청 수(distinct run_id) 컬럼 추가. 기존 컬럼 read 집계 확장, RBAC/스키마 무변경.
- Files:
  - `unit/feature-0003-agent-web-ui/src/app.py`: `admin_llm_usage` — totals/by_model 에 `count(distinct run_id)`=requests; by_account fold 에 `models:[{model,total_tokens,cost_usd}]` 보존 + 계정별 requests 별도 쿼리(`count(distinct run_id) WHERE run_id NOT NULL`); `_aggregate_usage_by_role` 가 역할별 `models[]`·`requests` 합산.
  - `unit/feature-0003-agent-web-ui/src/static/admin.js`: 전역 `modelColor`(등장 모델 전체로 1회 — 일별/도넛/stacked 색 일관) + `mcol()`; renderStacked/renderDonut 가 modelColor 사용; `renderStackedHBar`(역할/계정 토큰·비용 모델별 누적 막대) 신규 + 역할/계정 4 차트 교체; 요약 '요청' 카드; 상세 표(모델/역할/계정) '요청' 컬럼.
  - `unit/feature-0003-agent-web-ui/src/static/admin.html`: 캐시버스터 `?v=20260610-usage-stacked`.
- Note: 권한/엔드포인트/스키마/시크릿 신규 0 — read 집계 확장(distinct run_id, 모델 fold). 요청=사용자 메시지(run) 수, 호출=LLM 호출 수로 구분.
- Review: REV-20260610-0181 [SKIPPED:read-agg-no-rbac-no-schema]. Windows-browser(PB-0008) 검증 배포 후.

## CHG-20260610-0180
- Date: 2026-06-10
- TASK-Cycle: TASK-0180, **Minor §12.3** — 차트 카테고리별 행 레이아웃 + 일별 폭 채움 + 상세 표 여백
- Summary: TASK-0179 의 auto-fill grid(카테고리 무시 몰아넣기)를 명시적 행 구조(4:1 trend / 역할별 토큰|비용 / 계정별 토큰|비용)로 교체 + 일별 차트가 넓은 카드를 폭 채우게(viewBox=clientWidth) + 상세 표 카드화로 여백 해소. 순수 레이아웃.
- Files:
  - `unit/feature-0003-agent-web-ui/src/static/styles.css`: `.admin-usage-charts`/`.admin-usage-span2`(grid) 제거 → `.admin-usage-trend-row`(flex)+`.admin-usage-trend-main`(flex 4, min 420)+`.admin-usage-trend-side`(flex 1, min 240); `.admin-usage-row > card` min 300; `.admin-usage-table-card .admin-usage-table { max-width:none; width:100% }`.
  - `unit/feature-0003-agent-web-ui/src/static/admin.html`: 차트를 3행(trend 4:1 / 역할별 토큰·비용 / 계정별 토큰·비용)으로 재배치; details 상세 표를 카드(모델별 full + 역할별|계정별 2열)로. 캐시버스터 `?v=20260610-usage-rows`.
  - `unit/feature-0003-agent-web-ui/src/static/admin.js`: renderStacked 의 viewBox W 를 `el.clientWidth`(폴백 760)로, H 200 고정, 막대 cap 46→64, SVG max-width 제거(카드 폭 채움).
- Note: 권한/엔드포인트/스키마/백엔드 무변경 — 레이아웃/SVG 치수만. 데이터/툴팁/팔레트 동일. clientWidth 측정은 탭 활성 후 렌더 시점(폴백 760).
- Review: REV-20260610-0180 [SKIPPED:css-layout-no-logic]. Windows-browser(PB-0008) 검증 배포 후.

## CHG-20260610-0179
- Date: 2026-06-10
- TASK-Cycle: TASK-0179, **Minor §12.3** — LLM 사용량 차트 넓은 화면 가로 여백 해소 (CSS grid)
- Summary: 넓은 모니터에서 차트가 좌측만 차지하고 우측 가로 여백이 크던 것을, 차트 6개를 CSS grid 다열 배치로 채움. 순수 레이아웃(CSS/HTML), 동작/데이터 무변경.
- Files:
  - `unit/feature-0003-agent-web-ui/src/static/styles.css`: `.admin-usage-charts`(grid auto-fill minmax(400px,1fr)) + `.admin-usage-span2`(grid-column span 2) + 860px↓ 1열 미디어쿼리.
  - `unit/feature-0003-agent-web-ui/src/static/admin.html`: 차트 6개(일별/모델별/역할별/계정별/역할별비용/계정별비용)를 `.admin-usage-charts` grid 의 카드로 재배치, h3/h4 헤더를 각 카드 안으로. 일별 카드 `.admin-usage-span2`. 캐시버스터 `?v=20260610-usage-grid`.
  - `unit/feature-0003-agent-web-ui/src/static/admin.js`: 일별 차트 SVG max-width 780→1000(grid cell span2 폭 채움).
- Note: 권한/엔드포인트/스키마/백엔드 무변경 — 레이아웃만. 차트 데이터/툴팁/팔레트 동일.
- Review: REV-20260610-0179 [SKIPPED:css-layout-no-logic]. Windows-browser(PB-0008) 검증 배포 후.

## CHG-20260610-0178
- Date: 2026-06-10
- TASK-Cycle: TASK-0178, **Minor §12.3** — LLM 사용량 화면 여백 컴팩트화
- Summary: 사용자 보고(여백 과다). TASK-0177 디자인 카드·섹션·차트 패딩 누적분 축소. 순수 spacing(CSS/SVG), 동작/구조 무변경.
- Files:
  - `unit/feature-0003-agent-web-ui/src/static/styles.css`: `.admin-usage-card` padding 16/18→12/14; `.admin-usage-section` margin-top 20→12(first 14→8); `.admin-usage-h3/h4` margin 하향; `.admin-usage-metric` padding 11/14·strong 22→19·span margin-bottom 4; `.admin-usage-row` gap 16→12·min-width 280; usage `.summary-metrics` gap 10·margin-top 0.
  - `unit/feature-0003-agent-web-ui/src/static/admin.js`: renderStacked SVG H 252→196·pL 64→60·pT 16→10·pB 34→26; renderHBar 막대 div margin 8px→6px.
  - `unit/feature-0003-agent-web-ui/src/static/admin.html`: 캐시버스터 styles.css·admin.js `?v=20260610-usage-design`→`?v=20260610-usage-compact`.
- Note: 권한/엔드포인트/스키마/시크릿/백엔드 무변경 — 시각 spacing 만. 차트 데이터/구조 동일.
- Review: REV-20260610-0178 [SKIPPED:css-spacing-no-logic]. Windows-browser(PB-0008) 검증 배포 후.

## CHG-20260610-0177
- Date: 2026-06-10
- TASK-Cycle: TASK-0177, **Minor §12.3** — LLM 사용량 상세 표 추정 비용 컬럼 + gstack 디자인 관점 정렬
- Summary: (A) 역할별·계정별 상세 표에 추정 비용 컬럼 + 숫자 우측정렬. (B) gstack design-review 관점 subagent 리뷰 후 usage pane 디자인 토큰 정렬(요약 metric-card, 임의 hex→토큰, 차트 surface 카드, spacing/타이포 위계, 표/툴팁 클래스化). 백엔드 무변경.
- Files:
  - `unit/feature-0003-agent-web-ui/src/static/styles.css`: `.admin-usage-*` 클래스군 신규(.metric-card 정의 다음) — card/row/section/h3/h4/caption/metric/legend/table(+td.num)/details/empty/tooltip. 기존 :root 토큰(`--surface`/`--border`/`--border-subtle`/`--text*`/`--r-lg`/`--r-sm`/`--shadow-md`) 재사용.
  - `unit/feature-0003-agent-web-ui/src/static/admin.html`: usage pane 인라인 style 제거 + `.admin-usage-section/card/row/h3/h4/caption/details` 클래스 적용. 차트 각 블록을 surface 카드로 래핑(모델별|역할별, 역할별비용|계정별비용 2-col). 캐시버스터 styles.css·admin.js `?v=20260610-usage-design`.
  - `unit/feature-0003-agent-web-ui/src/static/admin.js`: `loadUsage` — 요약을 `.metric-card`/`.summary-metrics`(card 헬퍼)로, tbl 을 `.admin-usage-table` + `align:'right'`(td/th.num), 역할별·계정별 표 cost_usd 컬럼(costFmt) 추가, 툴팁 cssText→`className='admin-usage-tooltip'`, SVG fill 임의 hex→`var(--text*)`/`var(--border*)`(sed 치환), 빈 상태 `.admin-usage-empty`.
- Note: 권한/엔드포인트/스키마/시크릿/백엔드(app.py) 신규 0 — 순수 프론트(표 컬럼 + 디자인). cost_usd 데이터는 TASK-0176 백엔드 산물. 차트 막대 색 팔레트는 카테고리 구분용 의도라 유지.
- Review: REV-20260610-0177 [SKIPPED:frontend-design-no-rbac-no-schema] + general-purpose subagent 의 gstack design-review 관점 리뷰 반영(High 3·Med 4·Low). Windows-browser(PB-0008) 검증 배포 후.

## CHG-20260609-0176
- Date: 2026-06-09
- TASK-Cycle: TASK-0176, **Minor §12.3** — LLM 사용량 역할별·계정별 추정 비용 차트
- Summary: 사용자 요청. 역할별/계정별 토큰 막대 외에 추정 비용 막대 차트 추가. 비용은 모델별 단가라 계정×모델 분해로 집계.
- Files:
  - `unit/feature-0003-agent-web-ui/src/app.py`: `admin_llm_usage` by_account 쿼리를 `c.owner_account_id` 단일 GROUP BY → `owner_account_id, COALESCE(resolved_model,model)` 분해 + prompt/completion 추가, Python 계정별 fold(`_estimate_llm_cost_usd` 모델별 합 = `cost_usd`). `_aggregate_usage_by_role` 가 by_account 의 `cost_usd` 를 역할 버킷별 재합산(`by_role[].cost_usd`).
  - `unit/feature-0003-agent-web-ui/src/static/admin.js`: `renderHBar(el, rows, valueFmt)` 에 valueFmt 인자(기본 num, 비용은 usd) — strong·tip 포맷 적용. 역할별/계정별 추정 비용 차트 렌더 호출(`#usageRoleCostChart`/`#usageAccountCostChart`, cost_usd, 0 행 제외). element 선언 2개 추가.
  - `unit/feature-0003-agent-web-ui/src/static/admin.html`: 계정별 차트 다음에 "추정 비용" 섹션(역할별·계정별 2열 #usageRoleCostChart/#usageAccountCostChart) 추가. 캐시버스터 admin.js `?v=20260609-usage-charts2` → `?v=20260609-usage-cost`.
- Note: 권한/엔드포인트/스키마/시크릿 신규 0. 단가는 TASK-0166 의 `_LLM_PRICE_USD_PER_1M` 재사용(claude 근사 추정, 로컬=$0). by_account 가 모델 분해 fold 로 바뀌어도 응답 shape(account_id/calls/total_tokens + enrich username/role)는 동일 + cost_usd 추가.
- Review: REV-20260609-0176 [SKIPPED:frontend-viz-no-rbac-no-schema]. Windows-browser(PB-0008) 검증 배포 후.

## CHG-20260609-0173
- Date: 2026-06-09 (TASK-0173)
- Scope: 실행 단계(step) "근거(reason)" 사용자 노출 — frontend-only(web-ui 정적자산만).
- 문제: assistant 답변 시 실행 단계의 수행 근거가 화면에 나오지 않아, 사용자가 각 단계가 합리적으로 진행됐는지 확인 불가. 근본은 `reason` 데이터는 end-to-end 정상(LLM tool_notes → `agent_runtime.steps.reason_text` → `/api/progress` 응답)인데 프런트가 과거 "TMI 개선" 결정으로 step 사이드 패널에서 reason 을 `item.title`(hover 툴팁)에만 넣고 `.step-reason { display:none }` 으로 숨김.
- 변경:
  - [src/static/app.js](../src/static/app.js):
    - `buildStepDetailEl`: 숨김 주석 자리를 실제 `.step-reason`(라벨 "근거" pill + 텍스트) DOM 렌더링으로 교체 → step 사이드 패널의 모든 단계가 근거를 표시. compact/non-compact 공통.
    - `_renderStepSidePanelBody`: 인라인 렌더링으로 대체되었으므로 중복 `item.title = step.reason` 제거.
    - `buildSqlStepPanel`: 완료 메시지 상세의 execute_sql 단계 패널 상단에도 동일 `.step-reason` 추가(side panel 과 일관 — non-SQL 단계는 `buildStepBlocks` 가 이미 `work — reason` 표시 중이었음).
  - [src/static/styles.css](../src/static/styles.css): `.step-reason { display:none }` → 가시 secondary 라인(제목 아래 muted, "근거" pill) 스타일로 복원 + `.step-reason-label` / `.step-reason-text`.
  - [src/static/index.html](../src/static/index.html): styles.css·app.js 캐시버스터 `?v=20260609-query-toggle` → `?v=20260609-step-reason`.
- 비변경: 백엔드(app.py/agent_core)·RBAC·스키마·엔드포인트·시크릿 무변경. `reason` 텍스트는 LLM tool_notes 의 명시 user-facing 근거(provider chain-of-thought=`reasoning_content` 와 분리·폐기됨, agent_core.py:2054-2056) 이므로 노출 안전. XSS: `textContent` 사용.
- 게이트: node --check app.js PASS. outside-voice [SKIPPED:frontend-only] (REV-20260609-0173). 시각 검증=Windows-browser(PB-0008) 권장.

## CHG-20260609-0169
- Date: 2026-06-09 (TASK-0169)
- Scope: out-of-process ask-worker 실행모델 — web 측(feature-0003). 짝: feature-0002 CHG-20260609-0169.
- 변경 ([src/app.py](../src/app.py)):
  - `/api/ask`: `asyncio.to_thread(run_agent,…)` 를 `_dispatch_ask_run()` 으로 추상화. `AGENT_ASK_EXECUTION_MODE=inprocess`(기본) 는 현행 to_thread 그대로, `worker` 는 `ask_jobs` enqueue + 내부 `/api/ask_result` long-poll attach(동기 응답 계약 유지). 두 경로 동일 shape 의 agent_result 반환.
  - `_dispatch_ask_run_worker` / `_build_worker_agent_result`: readiness gate(worker heartbeat 신선도 → 부재 시 503), 단일문 slot enforce(`enqueue_ask_job`), run_timeout 까지 attach loop, `ask_jobs.result_json` 으로 응답 shape 패리티(answer/executed_sql/steps/result_csv_paths/rationale/error).
  - backstop ownership-aware(B1): `_reconcile_orphaned_runs_on_startup`(0159)·`_finalize_inflight_runs_on_shutdown`(0164)이 worker mode 에서 활성 `ask_jobs`(pending/running) conversation 을 skip — web 재배포가 worker run 을 오염하지 않음. `_active_ask_job_conversation_ids()` 신설.
  - `/api/cancel`: worker mode 에서 pending `ask_jobs` 도 canceled 로(2g — pending cancel 유실 방지). running 은 기존 KV 플래그 폴링 무변경.
  - 첨부 inline temp(M6): worker mode 는 `_inline_tmp_dir()` 가 `/shared/ask-inline`(web·worker 공통 볼륨) 반환, web 은 cleanup 안 함(worker terminal-only + reaper 소유).
  - BL-1(outside-voice): 403 product-access early-return 의 slot 이중 release 제거(finally 단일 release) — 기존 동시성 카운터 손상 수정.
- 게이트: make test 회귀 0(244 pass), py_compile OK, ruff clean. outside-voice 적대적 리뷰 2회(설계 전 + diff) — BLOCKER 3 + MAJOR 4 흡수.
- flag 기본 inprocess 라 본 배포 자체로는 동작 무변경(shadow). cutover 는 env 전환.
- **라이브 cutover 검증(2026-06-09, main 1320bca→후속 hotfix)**: 마이그레이션 0003 적용(live=0003, agent_kb_rw 권한 OK) → web+ask-worker 배포(healthz git_commit 일치) → `AGENT_ASK_EXECUTION_MODE=worker` 전환. 실측: ① ask enqueue→worker claim(atomic, lease=1)→run→result_json→/api/ask 동기 응답 shape 패리티 PASS, exactly-once(attempts=1). ② **web force-recreate 중 in-flight run 생존**(AC-0327): 동일 run_id·attempts=1·lease=1 로 done 도달, backstop 미오염(last_status=done/last_error 빈값, B1). ③ **hotfix**: `_ask_worker_ready` 가 `_parse_kv_timestamp`(naive UTC) 와 `datetime.now(timezone.utc)`(aware) 를 빼 TypeError→항상 False→readiness 영구 503 이던 tz 버그 라이브 포착·수정(naive 비교). project_task0159 KV tz stale 와 동형 함정.

## CHG-20260609-0167
- Date: 2026-06-09
- TASK-Cycle: TASK-0167, **Minor §12.3** — 관리 콘솔 작은 화면 세로 잘림 수정 (CSS)
- Summary: 사용자 보고(작은 브라우저 화면에서 화면 전체가 안 나오고 잘림). admin-shell/admin-workspace 가 height:100vh+overflow:hidden 인데 usage pane 만 자체 overflow-y 누락 → 차트·표로 길어진 usage pane 하단 잘림. usage pane 에 overflow-y:auto 추가(dashboard 와 동일 패턴).
- Files:
  - `unit/feature-0003-agent-web-ui/src/static/styles.css`: dashboard overflow 규칙(`[data-admin-pane="dashboard"].is-active`)에 `,[data-admin-pane="usage"].is-active` 셀렉터 추가 + 사유 주석.
  - `unit/feature-0003-agent-web-ui/src/static/admin.html`: styles.css 캐시버스터 `?v=20260605-ui-ux-polish` → `?v=20260609-usage-overflow`.
- Note: 권한/엔드포인트/스키마/시크릿/JS/HTML 구조 무변경 — CSS 셀렉터 1개 추가. 다른 pane(accounts/roles/products/audits)은 내부 admin-list 스크롤이라 제외(이중 스크롤 방지).
- Review: REV-20260609-0167 [SKIPPED:css-only-no-rbac-no-schema]. Windows-browser(PB-0008) 검증 배포 후.

## CHG-20260609-0166
- Date: 2026-06-09
- TASK-Cycle: TASK-0166, **Minor §12.3** — LLM 사용량 차트 고도화 (계정별 차트·hover 툴팁·막대 값·시간단위·추가지표)
- Summary: TASK-0165 후속(사용자 지적: 계정별 차트 부재·추가 지표·hover 상세·막대 정확한 값·시간 기준 선택). 상용 대시보드 수준으로 보강. 의존성 0 순수 SVG 유지.
- Files:
  - `unit/feature-0003-agent-web-ui/src/app.py`: `_LLM_PRICE_USD_PER_1M`(claude 근사 단가)+`_estimate_llm_cost_usd`+`_USAGE_GRAN`(date_trunc 화이트리스트+포맷+상한) 모듈 상수/헬퍼 추가. `admin_llm_usage` — `gran` 파라미터(화이트리스트 검증) + bucket_expr(`to_char(date_trunc('{gran}',...))`); by_model 에 prompt/completion + cost_usd; by_day/by_day_model 을 bucket 집계(by_day_model 은 서브쿼리로 by_day 와 동일 버킷); totals.cost_usd; 응답 `granularity` 추가.
  - `unit/feature-0003-agent-web-ui/src/static/admin.js`: `loadUsage` 재작성 — 커스텀 hover 툴팁(`tip`/`bindTip`, data-tip), renderStacked(막대 값 라벨 + data-tip + gran 라벨축약), renderDonut(data-tip 토큰/비중/호출/비용), renderHBar((el,rows[{label,value,tip}]) 일반화), 계정별 차트 렌더, 요약 추정비용 카드, 모델별 표 prompt/completion·비용 컬럼, gran/days URL 파라미터. usageGranSel change 바인딩 추가.
  - `unit/feature-0003-agent-web-ui/src/static/admin.html`: usage pane 에 `#usageGranSel`(시/일/주/월) + 기간 옵션(1일/1년) + `#usageAccountChart`(계정별 차트) + `#usageTrendTitle`(동적 단위 라벨). 캐시버스터 `?v=20260609-usage-charts` → `?v=20260609-usage-charts2`.
- Note: 권한 `console.usage.read`(admin)/엔드포인트/스키마/시크릿 신규 0. granularity 는 date_trunc 단위 화이트리스트로만 SQL 삽입(인젝션 차단). 비용은 공시가 근사 "추정"(로컬 LLM=$0).
- Review: REV-20260609-0166 [SKIPPED:frontend-viz-no-rbac-no-schema]. Windows-browser(PB-0008) 검증 배포 후.

## CHG-20260609-0165
- Date: 2026-06-09
- TASK-Cycle: TASK-0165, **Minor §12.3** — LLM 사용량 화면 차트화 (상용 AI 사용량 대시보드 구조 참조)
- Summary: TASK-0163 후속(사용자 요청). 관리 콘솔 > 감사 > LLM 사용량을 표 위주에서 Anthropic Console / OpenAI Usage 류 차트로 시각화. 일별 토큰 모델별 누적 막대 + 모델별 도넛 + 역할별 가로 막대. 의존성 0 순수 SVG(CDN 회피 — 정적자산 baked·WSL 내부). 동시 세션 TASK-0164(SIGTERM) 머지 충돌로 0164→0165 재부여.
- Files:
  - `unit/feature-0003-agent-web-ui/src/app.py`: `admin_llm_usage` 에 `by_day_model` 집계 추가 — `SELECT date(created_at)::text, COALESCE(resolved_model, model), sum(total_tokens) ... GROUP BY 1,2 ORDER BY 1` (기존 컬럼만, 비파괴 read). 응답에 `by_day_model` 추가.
  - `unit/feature-0003-agent-web-ui/src/static/admin.js`: `loadUsage` 에 SVG 차트 헬퍼 3종 추가 — `renderStacked`(일별 stacked 세로 막대 + 날짜축 + 범례), `renderDonut`(모델별 비중 도넛, 실제 서빙 모델 라벨 + % 범례), `renderHBar`(역할별 가로 막대). `colorMapFor`(모델/카테고리 안정 색상, 로컬/시스템=회색). data 수신 후 3 차트 렌더 호출.
  - `unit/feature-0003-agent-web-ui/src/static/admin.html`: usage pane 에 차트 컨테이너(#usageDayChart, #usageModelChart, #usageRoleChart) 추가 + 기존 모델별/역할별/계정별 표를 `<details>` "상세 표" 로 접이식 보존. 캐시버스터 `?v=20260609-usage-roles` → `?v=20260609-usage-charts`.
- Note: 권한 `console.usage.read`(admin)/엔드포인트/스키마/시크릿 신규 0. by_day_model 은 기존 llm_usage 컬럼만 사용(마이그레이션 불요).
- Review: REV-20260609-0165 [SKIPPED:frontend-viz-no-rbac-no-schema]. Windows-browser(PB-0008) 라이브 screenshot 검증 완료(배포 후).

## CHG-20260609-0164
- Date: 2026-06-09
- TASK-Cycle: TASK-0164, **Major §12.3** — 이월 처리: SIGTERM graceful finalizer(A1) + RBAC 고아 catalog prune(A2) + out-of-process 설계(B, 이월)
- Summary: in-process ask 실행의 orphan-on-redeploy 근본을 종료 시점 finalizer 로 저위험 차단 + RBAC catalog 정합 정리 + 구조적 재설계는 설계 문서로 이월. outside-voice PASS-WITH-NITS(BLOCKER 0).
- Files:
  - `unit/feature-0003-agent-web-ui/src/app.py`: `_SHUTDOWN_FINALIZE_MESSAGE` 상수 + `@app.on_event("shutdown") _finalize_inflight_runs_on_shutdown`(부팅 reconciliation 대칭 역, race 가드, 8s 소프트캡, 단일 connect) + `_prune_orphaned_permission_catalog(conn)`(고아 WebPermissions 행 가드 DELETE) + `_ensure_seed_roles` 에서 호출 연결.
  - `unit/feature-0003-agent-web-ui/tests/test_shutdown_finalizer.py`: 신규 단위테스트 3(역 boot-guard 선정 / 부팅이전 skip / race 가드).
  - `unit/feature-0003-agent-web-ui/docs/DESIGN-ask-worker.md`: 신규 — out-of-process ask-worker 아키텍처 설계(구현 안 함, B 이월).
  - (무변경 — A3) 빈 attachment 그룹 키는 forward-compatible 유지.

## CHG-20260609-0163
- Date: 2026-06-09
- TASK-Cycle: TASK-0163, **Major §12.3** — LLM 사용량 admin 계정별/역할별 집계 + 모델 해소 표시 (cross-feature, 주관 feature-0002)
- Summary: 관리 콘솔 > 감사 > LLM 사용량에 모델별(claude 포함 실제 모델)·계정별(이름/역할)·역할별 집계를 노출. 토큰 계측 복구·`resolved_model` 마이그레이션·in-process race 수정은 feature-0002 주관. 본 feature 는 엔드포인트 집계/표시 면.
- Files:
  - `unit/feature-0003-agent-web-ui/src/app.py`: `admin_llm_usage`(GET /api/admin/usage) — by_model `SELECT COALESCE(resolved_model, model) AS m, model, count(*), sum(total_tokens) ... GROUP BY COALESCE(resolved_model,model), model`(별칭+실제 모델 노출); by_account 를 이미 열린 MySQL `conn`(추가 개방 0)으로 `WebAccounts a LEFT JOIN WebRoles r ON r.Id=a.RoleId WHERE a.Id IN (%s,...)`(파라미터화) username·role enrich(실패 시 graceful null); 신규 모듈 헬퍼 `_aggregate_usage_by_role`(account None→`(시스템)`, role None→`(역할 없음)`, total_tokens desc) Python 폴딩; 응답에 `by_role` 추가. 권한 `console.usage.read`(admin) 게이트 무변경.
  - `unit/feature-0003-agent-web-ui/src/static/admin.html`: usage pane 에 역할별 표(`<h3>역할별</h3><div id="usageByRole">`) 추가; 정적자산 캐시버스터 `?v=20260605-tmi-cleanup` → `?v=20260609-usage-roles`.
  - `unit/feature-0003-agent-web-ui/src/static/admin.js`: `loadUsage` — `tbl(rows,cols)` 의 fmt 에 행 전체(r) 전달; 모델별에 `별칭 → 해소모델` 표시; 역할별 표(`#usageByRole`) 렌더; 계정별에 사용자명(`username (#id)`)·역할 컬럼 추가. `esc()` XSS 이스케이프 유지.
- Note: RBAC 카탈로그/엔드포인트/시크릿 신규 0. cross-DB(PG usage + MySQL 역할)는 SQL join 불가라 Python 으로 enrich/fold.
- Review: REV-20260609-0163 (정본 feature-0002) NEEDS-TWEAK→PASS, BLOCKER 1 흡수. **Windows-browser(PB-0008) 라이브 검증은 배포 후 수행.**

## CHG-20260608-0162
- Date: 2026-06-08
- TASK-Cycle: TASK-0162, **Minor §12.3** — 진행중("작업 중") 말풍선 생명주기 수정 (대화 전환 누출 + 새로고침 경과시간 초기화)
- Summary: 사용자 보고 2건 복구. (A) 요청 처리 중 다른 대화로 전환 시 직전 작업의 "작업 중" 말풍선이 전환한 대화에 누출 렌더되던 문제 — `selectConversation` 이 pendingBubble 스냅샷만 저장하고 `state.pendingBubble` 을 비우지 않아 잔존 말풍선이 새 대화에 렌더됨. (B) 새로고침 시 말풍선 경과시간이 0 으로 초기화되던 문제 — 말풍선이 `startedAt: Date.now()` 로 재생성되어 실제 run 시작 시각을 잃음. 서버가 보유한 run 시작 시각(KV `last_status_at`)을 `/api/history` 가 반환하고 프론트가 elapsed 기준점으로 쓰도록 수정.
- Files:
  - `unit/feature-0003-agent-web-ui/src/app.py`: `history()` 엔드포인트가 `last_status=='processing'` 일 때 `last_run_started_at`(=`load_memory_kv(conn, conv_id, "last_status_at")`)를 응답에 포함. 기존 `_account_can_access_conversation` 권한 게이트 안(`if conv_id:`)에서만 계산 — 신규 노출/IDOR 없음.
  - `unit/feature-0003-agent-web-ui/src/static/app.js`: (1) `selectConversation` — 스냅샷 저장 직후 `stopProgressPolling({reset:true})` 로 진행 상태(pendingBubble+polling+elapsed timer) 분리(`beginPendingConversation` 과 동일 패턴; 스냅샷은 reassign-null 이라 보존). (2) `loadHistory` processing 분기 — `startedAt` 을 `payload.last_run_started_at`(서버 run 시작) 파싱값으로, `Number.isFinite` 폴백 `Date.now()`. (3) `initializeWorkspace` resume 분기 — `startedAt` 을 `status.status_at`(ask_status snapshot) 파싱값으로 대칭 수정. (4) `loadHistory` 비-processing(else) 분기 — `_savedPendingBubbles[activeConversationId]` 폐기(stale 말풍선 부활 차단).
  - `unit/feature-0003-agent-web-ui/src/static/index.html`: 정적자산 캐시버스터 `?v=20260608-task-0156` → `?v=20260608-task-0162` (styles.css·app.js 양쪽).
- Note(tz): 클라 elapsed = `new Date(서버ISO).getTime()`(절대 epoch) − `Date.now()`(절대 epoch) → 브라우저 타임존 무관. `last_status_at` 은 `set_run_status` 가 'processing' 전이 시 1회만 기록(agent_core.py:1903)하고 terminal 시점까지 미갱신 → processing 상태에서 run 시작 시각으로 안정적. TASK-0159 의 PG timestamptz naive 변환 회귀와 무관(이 경로는 `_parse_kv_timestamp`/timestamptz 컬럼 미사용).
- Review: REV-20260608-0162 [SUBAGENT 적대적 diff 리뷰] APPROVE-WITH-NITS, BLOCKER 0.

## CHG-20260608-0161
- Date: 2026-06-08
- TASK-Cycle: TASK-0161, **Major §12.3** — RBAC 카탈로그 정리(거짓 컨트롤 권한 제거) + 죽은 코드 제거 (TASK-0158 Tier 3 종결)
- Summary: ① `attachment.execute_sql_on.own/.any` 제거(enforce 미배선 거짓 컨트롤 — 실제 게이트 allowlist+attachment_reader+sql_guard 무변경). ② 죽은 중복 제거(list_conversations HTTP 핸들러·#composerAttachments DOM·#tabCountAudits). ③ `upload.any` 유지+문서화. outside-voice 적대적 RBAC 리뷰 PASS-WITH-NITS(BLOCKER 0).
- Files:
  - `unit/feature-0003-agent-web-ui/src/app.py`: `PERMISSION_DEFINITIONS` 에서 `attachment.execute_sql_on.own/.any` 제거(실제 게이트 문서화 주석으로 대체) + operator/sales/admin 시드·catchup 제거 + `_cleanup_deprecated_role_permissions.removals` 2 코드 추가(전 롤 멱등 DELETE) + `upload.any` 의도적 UI 미노출 주석 + `POST /api/list_conversations` 핸들러 제거(내부 `_read_runtime_pg` 무관) + attachment 그룹 주석 갱신.
  - `unit/feature-0003-agent-web-ui/src/static/app.js`: execute_sql_on 라벨/설명 map 제거; 죽은 `#composerAttachments`/`Pills` 참조(렌더 hide·catch·pillsContainer 핸들러)·고아 `_toggleAttachmentPill` 제거(`state.composerAttachments`·`_removeAttachmentPill` 은 live 유지).
  - `unit/feature-0003-agent-web-ui/src/static/index.html`: 죽은 `#composerAttachments`/`#composerAttachmentsPills` DOM 제거.
  - `unit/feature-0003-agent-web-ui/src/static/admin.html`: `#tabCountAudits` stale 뱃지 제거.

## CHG-20260608-0158-V (PB-0008 Windows-browser 검증 기록)
- Date: 2026-06-08
- TASK-Cycle: TASK-0158 — 진입점 구성 Tier1·2 의 실제 Windows 브라우저 완료 게이트 검증 (코드 변경 없음, 테스트 증거만)
- Summary: `bin/win-browser.py`(무권한 relay)로 실제 Windows Chrome 에서 7개 진입점을 시나리오 검증(39/39 PASS). 결과·증거를 TEST.md §4 에 기록하고 재현용 시나리오를 tests 에 추가.
- Files:
  - `unit/feature-0003-agent-web-ui/docs/TEST.md`: §4 Test Run History 에 "Environment: Windows-browser" Run 추가(PASS 상세 + 스크린샷 10장 참조).
  - `unit/feature-0003-agent-web-ui/tests/win-browser-task0158.scenario.json`: 재현 가능 win-browser 시나리오 신규(비밀번호 없음 — authed-session 가정).
  - `unit/feature-0003-agent-web-ui/docs/TASK.md`: TASK-0158 완료 표시 + PB-0008 게이트 [x].

## CHG-20260608-0159
- Date: 2026-06-08
- TASK-Cycle: TASK-0159, **Major §12.3** — 고아 run 무한 폴링 수정 (런타임 run 생명주기/데이터 경로)
- Summary: 웹 DBA 챗 요청이 무한 "처리중"으로 멈추던 결함 복구. `/api/ask` 는 agent 를 `asyncio.to_thread` 로 web 프로세스 안에서 in-process 실행하므로, web 재배포/재시작이 in-flight run 을 죽이면 `set_run_status("done")` 미도달 → KV `last_status='processing'` 영구 고착 → 프런트엔드 무한 폴링 + 신규 질의 409 차단. 더해 20분 stale 자동복구가 `_last_step_at_for_run` 의 timestamptz(KST aware)→UTC 미변환 회귀(CHG-20260527-0001)로 elapsed 음수가 되어 영구히 안 터졌다. tz 변환 수정 + 부팅 시 고아 reconciliation 으로 재배포 즉시 자동복구를 보장.
- Files:
  - `unit/feature-0003-agent-web-ui/src/app.py`: (1) `_last_step_at_for_run` PG 분기 — aware timestamptz 를 `astimezone(timezone.utc).replace(tzinfo=None)` 으로 UTC naive 변환(이미 naive 면 통과). (2) 모듈 레벨 `_PROCESS_BOOT_UTC = datetime.utcnow().replace(microsecond=0)` (부팅 시각, 초 절삭 race 가드). (3) 신규 `@app.on_event("startup")` `_reconcile_orphaned_runs_on_startup` — daemon thread 에서 `last_status='processing'` 중 `last_status_at < _PROCESS_BOOT_UTC` 고아만 `set_run_status(..., "error", ...)` 정리. (4) `set_run_status` import.
  - `unit/feature-0003-agent-web-ui/tests/test_orphan_run_stale_recovery.py`: 신규 6 case (tz 변환·stale 판정·boot-guard).
- Note(즉시 해소, 코드 외): 라이브 PG `agent_runtime.kv` 의 고아 run `20260608053241-f47482aa` 를 `last_status=error` 로 수동 표시. 답변 미합성이라 재질의 필요.
- Note(병행 충돌): 본 cycle 중 다른 세션이 TASK-0158(진입점 Tier1·2, frontend)을 main 에 연속 병합 → 본 작업을 0159 로 재배정. app.py 무충돌(disjoint), docs 만 rebase 재삽입.

## CHG-20260608-0158-T2
- Date: 2026-06-08
- TASK-Cycle: TASK-0158, **Minor §12.3** — 진입점 구성 Tier 2 (관리자/자기서비스, frontend-only)
- Summary: Tier 2 진입점 4종 — audit.purge(파괴적, dry-run+typed-confirm)·내 활동기록 profile 탭·감사 필터 facet 드롭다운·첨부 권한 drift 진단 카드. 신규 RBAC 코드/스키마/시크릿/엔드포인트 무변경(기존 `audit.purge`·`audit.read.*`·`console.access` 권한과 엔드포인트에 UI 진입점만 추가).
- Files:
  - `unit/feature-0003-agent-web-ui/src/static/admin.html`: Audits pane 에 `#auditPurgeBtn`(.btn-danger) + resource/actor `<datalist>` + 대시보드 `#dashboardGrantHealth` 카드 컨테이너 신설.
  - `unit/feature-0003-agent-web-ui/src/static/admin.js`: `openAuditPurgeModal`(dry-run 미리보기 + typed-confirm)·`loadAuditFacets`(actors/resources)·`loadGrantHealth`(attachment-grants) 신규 + `renderAuditList` purge 가시성 게이트 + `attachAuditFilterHandlers` purge 바인딩 + `switchTab` audit init facet 로드 + setup grant 로드.
  - `unit/feature-0003-agent-web-ui/src/static/index.html`: 프로필 drawer 에 `data-profile-tab="audits"`("내 활동 기록") 탭 + pane(`#profileAuditList`/`#profileAuditMoreBtn`) 신설.
  - `unit/feature-0003-agent-web-ui/src/static/app.js`: `loadProfileAudits`(cursor 페이지네이션) 신규 + 프로필 탭 hook + `renderProfile` audit 권한 게이트 + more 버튼 바인딩.
  - `unit/feature-0003-agent-web-ui/src/static/styles.css`: `.btn-danger`·`.admin-modal-field/-preview/-actions`·`.admin-grant-health`/`.grant-health-*`·`.profile-audit-*` 신설 (기존 토큰만).

## CHG-20260608-0158
- Date: 2026-06-08
- TASK-Cycle: TASK-0158, **Minor §12.3** — "진입점 없는 기능" 전수조사 후 진입점 구성 (Tier 1, frontend-only)
- Summary: 백엔드·로직·RBAC 는 완성됐으나 사용자 진입점이 없던 기능에 UI 길을 추가 (Tier 1: 즉시답변·공유링크관리·scopeAll). 신규 RBAC 코드/스키마/시크릿/엔드포인트 무변경.
- Files:
  - `unit/feature-0003-agent-web-ui/src/static/index.html`: composer 에 `#composerFinalizeBtn`("즉시 답변") 신설 + 영구숨김 `#progressCard` 의 고아 `#cancelBtn`/`#finalizeBtn` 제거; attach 사이드패널에 `#composerAttachmentsScopeAll` 체크박스 행 신설.
  - `unit/feature-0003-agent-web-ui/src/static/app.js`: 구 cancelBtn/finalizeBtn const·toggle·listener 제거 + `composerFinalizeBtn` 신규 배선(renderComposer busy 분기 노출/권한 + click→finalizeCurrentRun); `openShareManager(cid)` 신규(공유 링크 목록/취소 모달, `GET /api/conversations/{cid}/shares`·`DELETE /api/share/{id}`) + ··· 메뉴 "공유 관리" 항목 + `requiredPermissionsFor` 에 `conversation.read` case 추가; `_loadConversationAttachmentList` 에 scopeAll 체크박스 상태 동기화/표시.
  - `unit/feature-0003-agent-web-ui/src/static/styles.css`: `.composer-finalize-btn`, `.share-mgr-*`(모달), `.attach-scope-all*` 스타일 신설 (기존 토큰만 사용).
  - `unit/feature-0003-agent-web-ui/docs/DESIGN-entry-points.md`: design.md 9섹션 형식 신규 작성.

## CHG-20260608-0157
- Date: 2026-06-08
- TASK-Cycle: TASK-0157, **Minor §12.3** — 요청 중단(interrupt) 진입점 복구 (frontend-only)
- Summary: 요청 처리 중 사용자가 실행을 멈출 수 있는 "중단" 버튼이 화면에 노출되지 않던 결함 복구. 근본 원인은 중단(`#cancelBtn`)·즉시 답변(`#finalizeBtn`) 버튼이 커밋 `4ba71f5` 에서 영구 숨김(`style="display:none"`)된 `#progressCard` 안에 고아로 남아 `renderProgress()` 의 `classList.remove("hidden")` 가 인라인 style 우선순위에 가려 무효였기 때문. 백엔드 `/api/cancel` + 에이전트 루프 폴링 + RBAC 는 정상. 사용자 선택(ChatGPT 패턴)에 따라 처리 중 전송 버튼을 "중단" 버튼으로 모핑.
- Files:
  - `unit/feature-0003-agent-web-ui/src/static/app.js`: `SEND_BTN_SEND_ICON`/`SEND_BTN_STOP_ICON` 상수 추가; `renderComposer()` 가 `isCurrentConvBusy()` 동안 `#sendBtn` 을 `.is-stop`(stop 아이콘 + `aria-label="중단"`, native disabled 해제) 로 모핑하고 종료 시 전송 버튼 환원 + 중단 권한 access-blocked 반영; `#sendBtn` click 핸들러 busy→`cancelCurrentRun()` / else `sendPrompt()` 분기; hover 전송모드 툴팁을 중단 모드에서 숨김.
  - `unit/feature-0003-agent-web-ui/src/static/styles.css`: `.send-btn.is-stop { background: var(--danger) }` + hover `#b91c1c` + `.is-stop.is-access-blocked` muted 규칙.
  - `index.html` 무변경 (영구 숨김 strip 미복원 — 기존 TMI 정리 UX 보존).

## CHG-20260605-0151
- Date: 2026-06-05
- TASK-Cycle: TASK-0151, **Major §12.3** — 첨부 text inline cap 정렬 버그 수정 (DB 조회 UX 개선의 web 면)
- Summary: text 첨부가 count cap(20)을 초과하는 대화에서 가장 오래된 20개만 inline 주입되고 방금 첨부한 최신 파일이 조용히 누락되던 정렬 버그를 수정. 최신 cap개를 보존하도록 DESC 선별 후 표시 순서는 시간순으로 복원.
- Files:
  - `unit/feature-0003-agent-web-ui/src/app.py`: `_prepare_text_inline_attachments` 의 `ORDER BY Id ASC LIMIT %s` → `ORDER BY Id DESC LIMIT %s`, 선별 후 `inline_entries.reverse()` 추가. AccountId IDOR 스코프(`AND AccountId = %s` + per-row 검증) 및 64KB size cap 무변경.

## CHG-20260528-0124
- Date: 2026-05-28
- Related Requirement: TASK-0124 (REQ-20260528-0124, **Minor** §12.3 — 관리 콘솔 RBAC 권한 정합 및 폐기 권한 정리)
- Summary: (1) `sales` 롤에 `conversation.delete.own` 추가 — 대화 생성·실행 권한과 삭제 권한 정합. (2) `conversation.suggestions.read` 폐기 — 항상 `conversation.ask` 종속, 단독 실효성 없는 zombie 권한; suggestions 엔드포인트 게이트를 `conversation.ask` 로 교체. (3) `pending` 롤에서 `conversation.file.read.own` 제거 — 승인 전 조회 전용 롤 의미와 파일 다운로드 혼재 제거. (4) `_cleanup_deprecated_role_permissions(conn)` 신설 — 기존 DB `WebRolePermissions` rows 에서 폐기 권한을 `DELETE` 로 멱등 제거.
- Files:
  - `unit/feature-0003-agent-web-ui/src/app.py`: `PERMISSION_DEFINITIONS` 에서 `conversation.suggestions.read` 제거; `SEED_ROLE_DEFINITIONS` sales 에 `conversation.delete.own` 추가, operator/sales 에서 `suggestions.read` 제거, pending 에서 `file.read.own` 제거; suggestions 엔드포인트 RBAC 게이트 `conversation.ask` 로 변경; `_legacy_permission_codes_from_row` 에서 `suggestions.read` 제거; `_ensure_seed_roles` catchup_codes 에 `conversation.delete.own` 추가; `_cleanup_deprecated_role_permissions` 신설 및 호출.
  - `docs/STATUS.md`: RBAC 권한 정합 변경 이력 2건 추가 (sales delete.own 추가 + suggestions.read 폐기 + file.read.own from pending 제거).

## CHG-20260528-0125
- Date: 2026-05-28
- Related Requirement: TASK-0125 (REQ-20260528-0125, **Minor** §12.3 — UX 2차 보완 7개 항목 구현; ux-compact-redesign 병합 시 재부여 — 브랜치 원번호 TASK-0123, main TASK-0123/0124 와 ID 충돌하여 다음 feature-0003 시퀀스로 정합)
- Summary: frontend-only UX 보완 7개 항목 일괄 구현. (1) `.composer-box` padding `9px→7px` (입력창 높이 프로필 버튼 48px 일치). (2) `_uploadComposerAttachment()` lazy 분기 재작성: 파일 선택 즉시 `/api/new_conversation` cid 발급 + 업로드 + `lazyConvCreating` 경쟁 방지 플래그. (3) 업로드 응답 `signed_url` bucket 보존 + `_sendAttachmentSnapshot` 포함 + `refreshWorkspace()` 후 lastUserMsg._attachments 재주입. (4) 첨부 chip `has-download` class + click 핸들러 (presigned GET). (5) `share.js` `downloadRowsAsCsv()` helper + SQL 결과표 하단 CSV 버튼. `share.css` `.share-csv-download-btn`. (6) `renderProgress()` `progressCardEl.open=true` + step details `detailsEl.open=true`. (7) lazy-create 성공 path `state.conversations` 최소 항목 추가 + `renderConversationList()`. node --check PASS. backend / RBAC / DB schema / endpoint contract 무변경.
- Files:
  - `unit/feature-0003-agent-web-ui/src/static/app.js`: lazy upload 재작성 + signed_url 보존 + lastUserMsg._attachments 재주입 + progressCardEl.open + detailsEl.open + state.conversations 최소 항목
  - `unit/feature-0003-agent-web-ui/src/static/styles.css`: `.composer-box` padding 축소 + `.attach-chip-dl` + `.message-bubble-attach-chip.has-download` hover 효과
  - `unit/feature-0003-agent-web-ui/src/static/share.js`: `downloadRowsAsCsv()` helper + CSV 버튼 삽입
  - `unit/feature-0003-agent-web-ui/src/static/share.css`: `.share-csv-download-btn` 스타일

## CHG-20260528-0123
- Date: 2026-05-28
- Related Requirement: REQ-20260527-0001 (**Major** §12.3 — KB 등록 UI/endpoint 제거)
- Summary: 관리 콘솔 "KB 등록" pane + backend endpoint 2개 + RBAC 권한 1코드 완전 제거. 제거 사유: (1) 대화 첨부(`WebConversationAttachments`) 의존 — 관리 영역이 사용자 대화에 기생하는 설계 결함, (2) Weight=90 manual fact 가 DB 스키마 변경 시 오래된 정보를 자동 수집(Weight=1)보다 우선 참조 → 스키마 오염 위험. `kb_ingest.py` 모듈 + 테스트는 재설계 시 재활용 가능하므로 보존.
- Files:
  - `unit/feature-0003-agent-web-ui/src/static/admin.html`: "KB 등록" tab 버튼 + `<section data-admin-pane="kb-ingest">` 전체 제거
  - `unit/feature-0003-agent-web-ui/src/static/admin.js`: `adminState.kbIngest` state + `mountKbIngestPane` + `loadKbIngestList` + `renderKbIngestList` + `renderKbIngestDetail` + `submitKbIngest` + `KB_INGEST_SCOPE_KEY_RE` + tab 분기 핸들러 (~221 LOC) 제거
  - `unit/feature-0003-agent-web-ui/src/app.py`: `attachment.kb.write.any` PERMISSION_DEFINITIONS 엔트리 + admin seed grant 항목 + `GET /api/admin/attachments` endpoint + `POST /api/admin/attachments/kb-ingest` endpoint + `_KB_INGEST_SCOPE_KEY_RE` (~264 LOC) 제거
  - `unit/feature-0003-agent-web-ui/docs/TASK.md`: TASK-0108 항목에 제거 사유 및 범위 기록

## CHG-20260528-0122
- Date: 2026-05-28
- Related Requirement: TASK-0122 (REQ-20260528-0122, **Minor** §12.3 — 외부 LLM 수신 동의 UI·권한·로직 전면 제거)
- Summary: 사용자 프로필 > 보안 및 계정 탭의 "외부 LLM 송신 동의" 섹션 제거. 서비스 사용 자체를 묵시 동의로 간주. `index.html` DOM 제거 / `app.js` consent 함수·변수·이벤트 바인딩 일체 제거 / `styles.css` consent CSS 블록 제거 / `app.py` `_ensure_web_account_consents_schema` + `_has_active_consent` 함수 제거, `_prepare_vision_inline_images` D11 consent gate + 409 응답 제거 (vision pre-fetch D13 보존, 4-tuple→3-tuple), `/api/account/consents` 3 엔드포인트 제거, `attachment.consent.grant|revoke` audit 핸들러 제거, `_model_to_consent_provider`→`_model_to_llm_provider` rename. py_compile + node --check PASS.
- Files:
  - `unit/feature-0003-agent-web-ui/src/static/index.html`: `profileConsentSection` div 제거
  - `unit/feature-0003-agent-web-ui/src/static/app.js`: consent 함수·변수 9개 제거 + RBAC description 갱신 + 이벤트 바인딩 제거
  - `unit/feature-0003-agent-web-ui/src/static/styles.css`: consent CSS 블록 (~43 LOC) 제거
  - `unit/feature-0003-agent-web-ui/src/app.py`: `_ensure_web_account_consents_schema` 제거 + `_has_active_consent` 제거 + consent gate 제거 + 3 엔드포인트 제거 + audit 핸들러 제거 + rename

## CHG-20260526-0108
- Date: 2026-05-26
- Related Requirement: TASK-0108 (REQ-20260526-0108, **Major** §12.3 — Sprint 3 (B: DDL/KB 보강) admin-only manual KB ingest)
- Summary: BRIEFING-attachment-multi-cycle.md §6.3 Sprint 3 Cycle 3 implementation. admin 콘솔 "스키마 정의서 KB 등록" pane 에서 text/markdown/.sql 첨부를 `AgentMemoryFactEntries` 의 manual fact 로 등록. SourceType='manual' 고정, Weight=90 고정 (BRIEFING D 의 0.9 scale ×100, 자동 수집 Weight=1 대비 90× 우선), ConversationId='__kb_manual__' reserved sentinel, FactKey=ScopeKey 자체. 동일 ScopeKey 재ingest 시 기존 active row 는 Weight=0 으로 logical supersede (Status 컬럼 추가 회피, `AgentMemoryFacts` VIEW 의 Weight DESC tie-break 가 자연 hide → 회귀 0). RBAC 1 코드 신설: `attachment.kb.write.any` (admin/dba role catchup). audit `attachment.kb.ingest` dispatch. AGENTS.md §11.3 신설 — manual ingest fact 정책 명문화. **outside-voice review (Codex `codex-cli 0.130.0`, `REV-20260526-0002`) Verdict BLOCK → PASS 전환 (Critical 5 + Nice-to-have 1 본 cycle 내 흡수)**: (B-1) 동시 ingest race → SELECT FOR UPDATE 명시 lock + reactivated 명시 계산 / (B-2) source_type/weight client spoofable → endpoint 가 서버 상수 고정 (request body 입력 무시) / (B-3) admin endpoint 가 `console.access` + `attachment.kb.write.any` 둘 다 require / (B-4) ingest 먼저 commit + audit fail-soft = canonical KB 변경만 + audit 누락 가능 → single transaction + audit 실패 시 rollback / (B-5) scope_key arbitrary string + audit 평문 → regex `^[A-Za-z0-9_.-]{1,96}$` validation + audit ChangeJson 에는 `scope_key_hash_prefix` (SHA256 prefix) 만 + masked_fields=["scope_key", ...]. Nice-to-have: `ON DUPLICATE KEY UPDATE Id = LAST_INSERT_ID(Id)` 로 fact_entry_id 명시 확보.
- Files:
  - `unit/feature-0003-agent-web-ui/src/app.py` (+~330 LOC): PERMISSION_DEFINITIONS 의 `attachment.kb.write.any` 1 코드 신설 (group="attachment") + SEED admin role grant + dba catchup. 신규 endpoint `GET /api/admin/attachments` (list, RBAC `console.access` AND `attachment.kb.write.any`). 신규 endpoint `POST /api/admin/attachments/kb-ingest` (RBAC + scope_key regex + 1 MB size cap + storage_minio body fetch + UTF-8 decode + kb_ingest.ingest_manual() + audit dispatch, single transaction). `_KB_INGEST_SCOPE_KEY_RE` module-level.
  - `unit/feature-0002-agent-core/src/modules/kb_ingest.py` (신규 ~205 LOC): `KB_MANUAL_CONVERSATION_ID="__kb_manual__"` + `DEFAULT_MANUAL_WEIGHT=90` + `DEFAULT_SOURCE_TYPE="manual"`. `ingest_manual(conn, *, scope_key, body, source_filename, source_sha256, source_type, weight) -> dict` — 4-step: INSERT IGNORE Texts → SELECT FOR UPDATE → UPDATE Id IN (active) → INSERT FactEntries ON DUPLICATE KEY UPDATE Id=LAST_INSERT_ID(Id). 응답 `{fact_entry_id, text_hash, fact_fingerprint, superseded_count, reactivated}`.
  - `unit/feature-0003-agent-web-ui/src/static/admin.html` (+~50 LOC): sidebar "시스템" 그룹에 신규 tab `kb-ingest` + workspace 의 신규 `<section data-admin-pane="kb-ingest">` (pane-head + list-detail layout — 좌 첨부 list, 우 form panel with ScopeKey input + 안내 + submit/cancel). cache-bust `v=20260526-task-0108-kb-ingest`.
  - `unit/feature-0003-agent-web-ui/src/static/admin.js` (+~230 LOC): `adminState.kbIngest` state + `switchTab("kb-ingest")` 분기 + `mountKbIngestPane()` + `loadKbIngestList()` (kind=text,markdown + .sql 별 호출 merge + CreatedAt DESC) + `renderKbIngestList()` + `renderKbIngestDetail()` + `submitKbIngest()` (client regex + source_type/weight 안 보냄). `KB_INGEST_SCOPE_KEY_RE` constant.
  - `unit/feature-0002-agent-core/tests/test_kb_ingest.py` (신규 ~190 LOC): 10 unit test (FakeConn 패턴 — happy path / supersede 3건 / reactivate 동일 본문 / mixed active+inactive 시나리오 / scope_key empty,long / body empty / fingerprint normalization / text_hash determinism / 상수). 10 PASS.
  - `unit/feature-0003-agent-web-ui/tests/test_kb_ingest_rbac.py` (신규 ~165 LOC): 8 e2e RBAC 시나리오 (admin ingest / 동일 ScopeKey reactivate / operator 403 / anonymous 401 / 비-허용 kind 400 / scope_key 누락 400 / 비존재 attachment 404). 운영 turn 에 `make web` 후 실행.
  - `AGENTS.md` (+31 LOC): §11.3 신설 — KB Fact 등록 정책 (Source/SourceType/Weight/ConversationId 4열 테이블 + manual fact supersede 정책 + 책임 분담).
  - `unit/feature-0003-agent-web-ui/docs/{FUNCTION,TASK,MODIFY,REVIEW,REPORT}.md`: docs append.
- 검증 (본 cycle):
  - `python3 -m pytest unit/feature-0002-agent-core/tests/test_kb_ingest.py -v` — 10 PASS.
  - `python3 -m py_compile` (변경 4 .py 파일) PASS.
  - `node --check unit/feature-0003-agent-web-ui/src/static/admin.js` PASS.
- Runtime 검증 deferral (사용자 운영 turn 책임):
  - PR 머지 + `docker compose -p repo build memory-init web` + `up -d --force-recreate web` 후 admin 콘솔 → "KB 등록" tab → text/markdown 첨부 1건 ingest → AgentMemoryFactEntries 에 ConversationId='__kb_manual__' Weight=90 row + WebAuditEvents 에 attachment.kb.ingest row 1개 (ChangeJson 의 scope_key_hash_prefix 확인, raw scope_key 미기록).
  - `test_kb_ingest_rbac.py` 8 시나리오 e2e PASS.
- Outside-voice rationale: 호출 ✓ — `REV-20260526-0002` (Codex). RBAC 신규 코드 + admin endpoint + DB mutation = 사용자 메모 `feedback_outside_voice_for_rbac.md` 정합. BLOCK → PASS 전환.

## CHG-20260522-0107
- Date: 2026-05-22
- Related Requirement: TASK-0107 (REQ-20260522-0107, **Major** §12.3 — 첨부 sandbox 활성화 + LLM context inject + drag&drop UX 확장)
- Summary: 사용자 직접 보고 2건 일괄 fix. (1) 파일 첨부 후 LLM 이 "실제 내용을 직접 볼 수 없습니다" 응답 — TASK-0094 sandbox ingest 파이프라인은 정의되어 있었으나 `app.py` upload endpoint 가 `sandbox_ingest.ingest_attachment` 를 호출하지 않아 MetaJson 에 sandbox_table_name 미기록 → ATTACHED FILES section 이 schema 명을 noindict → LLM 의 SQL tool 이 SELECT 시도 안 함. **수정 (3-phase)**: Phase A 활성화 — `app.py` upload endpoint audit dispatch 직후 `threading.Thread(target=_ingest_attachment_background, daemon=True)` spawn (kind=csv|xlsx). 신규 helper 가 storage_minio 로 bytes 받기 → `CREATE SCHEMA IF NOT EXISTS agent_attachment_<sha256(cid)[:32]>` (root user 단일-user MVP — 4-user 분리 grant 는 후속 cycle, .env 비밀번호 미설정) → `_open_memory_connection(database=schema)` → `sandbox_ingest.ingest_attachment` → MetaJson 에 sandbox_schema_name + sandbox_table_name (csv) 또는 sheets[] (xlsx) 기록 + UploadStatus='ingested'. 실패 → `_mark_ingest_failed` 가 'failed' + degraded_reason. `db.py` connect() 에 `agent_attachment_*` schema 패턴 → primary 라우팅 강제 (replica latency / 미배포 환경 안전). Phase B LLM 인지 — `agent_core.py` `_build_attachment_context_section` 강화: information_schema.columns SELECT (column명 + data_type) + `SELECT * FROM <schema>.<table> LIMIT 5` sample rows (markdown 표, 80자 truncate, pipe escape, table cap 20) + 명시 INSTRUCTION ("first try to answer from the sample rows above. If more data is needed, call execute_sql … Do NOT ask the user to paste the file contents"). UploadStatus='uploaded'/'failed' 분기 별 안내. (2) drag&drop 영역 협소 + 새 대화 시 첨부 차단 — composer-wrap 만 drop zone + pendingSentinel 미발급 시 `_uploadComposerAttachment` 가 "대화 컨텍스트 미정" toast 차단. **수정**: index.html 에 chat-pane 자식 `#chatDropOverlay` (점선 카드 + 아이콘) 추가, styles.css 에 `.chat-drop-overlay` (absolute inset 0 + backdrop-filter blur + fade-in 120ms) + `.chat-pane { position: relative }`. app.js `_bindComposerAttachmentEvents` 에 chat-pane scope 핸들러 + `_isFileDrag()` types Files guard + dragCounter 중첩 추적 + window dragend/drop reset (drop miss 방어) + chat-pane 밖 drop 시 브라우저 기본 동작 preventDefault. `_uploadComposerAttachment` 진입 시 컨텍스트 미정 검출 → `conversation.create` 권한 검증 → `pendingNewConversation=true` + `_newPendingSentinel()` + 모든 render 호출 → 기존 lazy-create path 재사용. py_compile + node --check PASS. backend RBAC / DB schema / endpoint contract / D11 consent / D13 server-side bytes 무변경.
- Files:
  - `unit/feature-0002-agent-core/src/modules/db.py`: `connect()` 에 `agent_attachment_*` schema 패턴 매칭 + sandbox 시 replica 라우팅 우회 (primary 강제) — replica latency / 미배포 환경에서도 즉시 SELECT 가능.
  - `unit/feature-0003-agent-web-ui/src/app.py`: upload endpoint (`POST /api/conversations/{cid}/attachments`) 의 audit dispatch 직후 `threading.Thread` 로 `_ingest_attachment_background` spawn (csv|xlsx 한정, fail-open). 신규 helper `_ingest_attachment_background(attachment_id, conversation_id, object_key, kind)`: storage_minio bytes → CREATE SCHEMA + sandbox conn → `sandbox_ingest.ingest_attachment` → MetaJson `sandbox_schema_name` + `sandbox_table_name` 또는 `sheets[]` + UploadStatus='ingested'. 신규 helper `_mark_ingest_failed(attachment_id, reason)`: UploadStatus='failed' + MetaJson `degraded_reason`.
  - `unit/feature-0002-agent-core/src/agent_core.py`: `_build_attachment_context_section` 전면 강화 — metadata + sandbox_table_specs 수집 + `information_schema.columns` SELECT + `SELECT * FROM <schema>.<table> LIMIT 5` sample rows (markdown 표 형식, 80자 cell truncate, pipe escape, table cap 20) + 명시 SQL INSTRUCTION 추가. UploadStatus='uploaded'/'failed' 분기별 안내. ingest 미완 시 fallback 메시지.
  - `unit/feature-0003-agent-web-ui/src/static/index.html`: chat-pane 자식으로 `#chatDropOverlay` div (점선 카드 + 아이콘 + "여기에 파일을 놓으세요" 텍스트). cache-bust query `v=20260522-task-0107-attachment` (styles.css + app.js 양쪽).
  - `unit/feature-0003-agent-web-ui/src/static/styles.css`: `.chat-drop-overlay` (absolute inset 0 + flex center + backdrop-filter blur 2px + fade-in animation 120ms) + `.chat-drop-overlay-card` (점선 border + box-shadow + 점선 색 primary) + `.chat-pane { position: relative }` + `@keyframes chat-drop-overlay-fade`.
  - `unit/feature-0003-agent-web-ui/src/static/app.js`: `_bindComposerAttachmentEvents()` 에 chat-pane scope drag/drop 핸들러 추가 — `_isFileDrag()` (types Files guard), dragCounter (자식 → 부모 bubble 중첩 추적), window dragend/drop reset (drop miss 방어), chat-pane 밖 drop 시 브라우저 기본 동작 preventDefault, multi-file 직렬 업로드. `_uploadComposerAttachment()` 진입 시 컨텍스트 미정 (activeConversationId 없음 + pendingSentinel 없음) 검출 → `conversation.create` 권한 검증 → 자동으로 pendingNewConversation=true + `_newPendingSentinel()` + 모든 render 호출 → 기존 lazy-create path 재사용.
  - `unit/feature-0003-agent-web-ui/docs/TASK.md`: TASK-0107 entry 추가 + Current Status 갱신.
  - `unit/feature-0003-agent-web-ui/docs/REPORT.md`: TASK-0107 Summary 추가.
  - `unit/feature-0003-agent-web-ui/docs/MODIFY.md`: 본 entry.
  - `unit/feature-0003-agent-web-ui/docs/REVIEW.md`: REV-20260522-0107 entry 추가.
  - `docs/STATUS.md`: TASK-0107 narrative entry + 표 row 갱신.

## CHG-20260522-0106
- Date: 2026-05-22
- Related Requirement: TASK-0106 (REQ-20260522-0106, **Major** §12.3 — 첨부 storage 모듈 import 경로 + lazy-create 첨부 staging)
- Summary: 사용자 직접 보고 2건 일괄 fix. (1) 웹 첨부 업로드 시 `Error: storage 모듈 import 실패: cannot import name 'storage_minio' from 'modules' (/app/modules/__init__.py)` toast — Dockerfile 이 feature-0002-agent-core 의 unified namespace 만 `/app/modules` 로 copy + feature-0003 의 `storage_minio.py`/`sandbox_schema.py` 는 `/app/web/modules/` 로 copy 하지만 `app.py` 의 `from modules import …` (4 callsite) 가 잘못된 경로. `from web.modules import …` 로 교체. attachment_reconciliation worker 는 docker (`/app/web/modules`) + host dev (sibling sys.path) 양쪽 dual-mode fallback. (2) "+ 새 대화" 클릭 후 첫 메시지 전 첨부 차단 (`isLazy` 조기 toast). lazy-create (TASK-0048) 는 backend cid 발급을 첫 send 까지 지연시키므로 cid 필수의 `/api/conversations/{cid}/attachments` 호출 불가. **Option A — client-side staging**: lazy 분기에서 즉시 차단 대신 pendingSentinel bucket 에 status=`staged` + `_localFile=File` 보관, `sendPrompt()` 의 lazy-create path 가 staged ≥1 감지 시 `/api/new_conversation` 으로 cid 즉시 발급 → `_flushStagedAttachmentsToCid()` 신규 helper 가 staged 일괄 업로드 → askBody 를 `lazy_create=true` → `conversation_id=earlyCid` 로 전환 + `attachment_ids` union. staged 0 인 lazy-create 는 기존 단일 호출 보존 (TASK-0048 정신). pill rendering 에 `data-staged` 속성 + "(첫 메시지와 함께 업로드)" tooltip + staged 토글 = remove. py_compile + node --check PASS. backend / RBAC / DB schema / endpoint contract 무변경.
- Files:
  - `unit/feature-0003-agent-web-ui/src/app.py`: `from modules import storage_minio` 3 callsite (L6044 vision inline, L7555 upload endpoint, L7771 metadata endpoint) → `from web.modules import storage_minio`. `from modules import sandbox_schema` (L11862 grant drift health) → `from web.modules import sandbox_schema`.
  - `unit/feature-0002-agent-core/src/modules/attachment_reconciliation.py`: `_delete_minio_object()` 의 storage_minio import 를 `try: from web.modules import storage_minio` 우선 시도 + ImportError 시 sys.path 삽입 fallback 의 dual-mode 보강 (docker container + host dev 양쪽 환경 호환).
  - `unit/feature-0003-agent-web-ui/src/static/app.js`: `_uploadComposerAttachment()` 의 `if (isLazy)` 차단 toast 제거 + pendingSentinel bucket 에 staged item 추가. `_renderAttachmentPills()` 에 `data-staged` 속성 + 조건부 tooltip. `_toggleAttachmentPill()` 에 staged 토글 = remove. `_flushStagedAttachmentsToCid()` 신규 helper. `sendPrompt()` 의 lazy-create attachment_ids 빌드 후 staged ≥1 감지 시 `/api/new_conversation` 발급 + flush + askBody 즉시-cid 모드 전환 + attachment_ids union.
  - `unit/feature-0003-agent-web-ui/docs/TASK.md`: TASK-0106 entry 추가 + Current Status 갱신
  - `unit/feature-0003-agent-web-ui/docs/MODIFY.md`: 본 entry
  - `unit/feature-0003-agent-web-ui/docs/REVIEW.md`: REV-20260522-0106 [SKIPPED:no-rbac-no-schema-no-secret-handling] 추가
  - `unit/feature-0003-agent-web-ui/docs/REPORT.md`: §1 Summary 상단에 TASK-0106 entry 추가
  - `docs/STATUS.md`: project-level entry 추가

## CHG-20260522-0008
- Date: 2026-05-22
- Related Requirement: TASK-0105 (REQ-20260522-0008, **Minor** §12.3 — Profile Drawer '내 감사 로그' 탭 일반 사용자 비노출)
- Summary: 사용자 직접 요청 — 일반 사용자에게 Profile Drawer 내 '내 감사 로그' 탭이 노출되어선 안 됨. TASK-0089 에서 추가한 `profileAuditTab` 버튼 + `data-profile-pane="audit"` 패널 + JS 함수 9개 (`_profileAuditEscapeHtml` / `_profileAuditFormatDt` / `_profileAuditHasReadPermission` / `updateProfileAuditTabVisibility` / `_profileAuditReadFilters` / `_profileAuditClearFilters` / `loadProfileAuditList` / `renderProfileAuditList` / `renderProfileAuditDetail` / `attachProfileAuditHandlers`) + `state.profileAudit` 초기값 + `profile-audit-*` CSS 블록 전체를 제거. backend `/api/profile/audits` 및 `/api/profile/audits/{event_id}` endpoint 무변경. admin 콘솔 '감사 로그' 탭 무변경. node --check + py_compile PASS. frontend-only.
- Files:
  - `unit/feature-0003-agent-web-ui/src/static/index.html`: `profileAuditTab` 버튼 제거, `data-profile-pane="audit"` 패널 전체 제거, 주석 갱신 (탭 수 4 → 3)
  - `unit/feature-0003-agent-web-ui/src/static/app.js`: `state.profileAudit` 초기값 제거, TASK-0089 `_profileAudit*` 함수 블록 전체 제거, `renderProfile()` 내 `updateProfileAuditTabVisibility()` 호출 제거, 탭 이벤트 핸들러의 audit 분기 제거, `attachProfileAuditHandlers()` 호출 제거
  - `unit/feature-0003-agent-web-ui/src/static/styles.css`: `.profile-audit-*` CSS 블록 전체 제거
  - `unit/feature-0003-agent-web-ui/docs/TASK.md`: TASK-0105 entry 추가 + Current Status 갱신
  - `unit/feature-0003-agent-web-ui/docs/MODIFY.md`: 본 entry
  - `unit/feature-0003-agent-web-ui/docs/REVIEW.md`: REV-20260522-0008 [SKIPPED:frontend-only] 추가
  - `unit/feature-0003-agent-web-ui/docs/REPORT.md`: §1 Summary 상단에 TASK-0105 entry 추가
  - `docs/STATUS.md`: project-level entry 추가

## CHG-20260522-0007
- Date: 2026-05-22
- Related Requirement: TASK-0104 (REQ-20260522-0007, **Major** §12.3 — 외부 노출 web 컨테이너 HTTPS 종단 활성화)
- Summary: 외부 사용자가 `https://112.185.196.20:18080/` 로 접속할 수 없던 이슈 수정. **근본 원인**: `repo/.env` 의 `ENABLE_WEB_TLS=1` + `WEB_TLS_CERT_FILE` / `WEB_TLS_KEY_FILE` 설정과 `docker-compose.yml` 의 TLS 분기 entrypoint 가 있었으나, dev 편의용 `docker-compose.override.yml` (gitignored) 가 entrypoint 자체를 평문 HTTP uvicorn 으로 강제 override. compose 자동 merge 로 base TLS 분기를 덮어써 외부 노출 시나리오에서도 평문만 listening. **수정**: `docker-compose.override.yml` 의 entrypoint 를 `--ssl-keyfile /certs/mysql-ai.company.local/privkey.pem --ssl-certfile /certs/mysql-ai.company.local/fullchain.pem` 포함한 HTTPS 종단으로 교체 (same-port 18080 HTTPS-only — 사용자 결정). `docker-compose.override.yml.example` 에 Variant A (local dev plain HTTP) / Variant B (외부-노출 HTTPS, default) 두 형태 주석 명시. 기존 인증서는 SAN 에 `IP Address:112.185.196.20` 이미 포함되어 재발급 불필요. 호스트 포트 매핑 `${WEB_PORT}:8000` (`18080:8000`) 그대로. backend / RBAC / endpoint contract / DB / Frontend 코드 무변경.
- Files:
  - `docker-compose.override.yml` (gitignored — 운영 인스턴스 직접 적용):
    - `services.web.entrypoint` 를 plain HTTP → HTTPS 종단 (`--ssl-keyfile` + `--ssl-certfile`) 으로 교체
    - 헤더 주석 갱신 — DEV ONLY 표기 → DEV / EXTERNAL-EXPOSED, TASK-0103 / TASK-0104 컨텍스트 명시
  - `docker-compose.override.yml.example` (committed template):
    - 헤더 주석에 사용 시나리오 (A) Local dev / (B) 외부 노출 single-instance / (C) Production with Caddy 3가지 명시
    - `services.web.entrypoint` 에 Variant A (commented out) / Variant B (default) 두 형태 제공
  - `unit/feature-0003-agent-web-ui/docs/TASK.md`: TASK-0104 entry 추가 + Current Status 갱신
  - `unit/feature-0003-agent-web-ui/docs/MODIFY.md`: 본 entry
  - `unit/feature-0003-agent-web-ui/docs/REVIEW.md`: REV-20260522-0007 [SKIPPED:non-policy-doc] 추가
  - `unit/feature-0003-agent-web-ui/docs/REPORT.md`: §1 Summary 상단에 TASK-0104 entry 추가
  - `unit/feature-0003-agent-web-ui/docs/FUNCTION.md`: AC-0271 (HTTPS 종단 활성화 acceptance) 추가
  - `docs/STATUS.md`: project-level entry 추가

## CHG-20260522-0006
- Date: 2026-05-22
- Related Requirement: TASK-0103 (REQ-20260522-0006, **Major** §12.3 — API Vault secure context 사전 차단 + UX 안내)
- Summary: 외부 사용자가 `http://112.185.196.20:18080/` 로 접속하여 OpenAI API Key 입력 시 모호한 toast 만 출력되며 저장 안 되던 이슈 수정. **근본 원인**: `encryptPlainApiKey()` 가 호출하는 `window.crypto.subtle` 은 secure context (HTTPS / localhost) 에서만 정의됨. 외부 IP 의 HTTP 접속에서는 `undefined` → `Cannot read properties of undefined (reading 'importKey')` 예외 → catch 블록 toast 가 사용자에게 원인을 명확히 전달 안 함. 서버는 `requires_secure_context: True` 를 내려줬으나 클라이언트가 활용 안 함. **수정**: `isVaultCryptoAvailable()` helper + `updateVaultReadiness()` `blocked` 신규 상태 (빨간 banner + 한국어 사유) + `syncVaultSteps()` 가 `cryptoOk = false` 시 모든 step disable + `encryptPlainApiKey()` 진입 시 사전 throw + styles.css `vault-banner[data-state="blocked"]` 빨간 톤. cache-bust `v=20260522-admin-topbar-rbac` → `v=20260522-vault-secure-context`. backend / RBAC / endpoint contract / DB / 암호화 알고리즘 (PBKDF2 + AES-GCM) 무변경.
- Files:
  - `unit/feature-0003-agent-web-ui/src/static/app.js`:
    - `isVaultCryptoAvailable()` — `window.isSecureContext && window.crypto?.subtle` 체크 helper 추가
    - `updateVaultReadiness()` — `cryptoOk = false` 시 readiness `blocked` 반환 + 한국어 사유 메시지 (`public_url` 이 https 면 보안 주소 표기)
    - `syncVaultSteps()` — `cryptoOk = false` 분기 추가, 모든 step `data-state="disabled"` + saveVaultBtn 차단
    - `encryptPlainApiKey()` — 진입 시점에 `isVaultCryptoAvailable()` 사전 검증, 명시적 한국어 안내 throw
  - `unit/feature-0003-agent-web-ui/src/static/styles.css`:
    - `.vault-banner[data-state="blocked"]` + `.vault-banner-dot` 빨간 색상 토큰 추가 (`#ef4444`)
  - `unit/feature-0003-agent-web-ui/src/static/index.html`:
    - cache-bust `v=20260522-admin-topbar-rbac` → `v=20260522-vault-secure-context`
  - `unit/feature-0003-agent-web-ui/docs/TASK.md`: TASK-0103 entry 추가 + Current Status 갱신
  - `unit/feature-0003-agent-web-ui/docs/MODIFY.md`: 본 entry
  - `unit/feature-0003-agent-web-ui/docs/REVIEW.md`: REV-20260522-0006 [SKIPPED:non-policy-doc] 추가
  - `unit/feature-0003-agent-web-ui/docs/REPORT.md`: §1 Summary 상단에 TASK-0103 entry 추가
  - `docs/STATUS.md`: project-level entry 추가

## CHG-20260522-0005
- Date: 2026-05-22
- Related Requirement: TASK-0102 (REQ-20260522-0005, Minor §12.3 — topbar 관리 콘솔 버튼 role fallback gate)
- Summary: 테스트에서 `sales` 역할 사용자에게 topbar 관리 콘솔 버튼이 노출되는 현상 확인. `canOpenAdminConsole()` 에 `role.key` 기반 fallback 추가 — `console_access` 플래그가 서버 응답에 포함된 경우 그것을 사용, 없으면 `role.key === "admin"` 으로 fallback. role 필드는 TASK-0098 이전부터 항상 직렬화되므로 서버 버전 무관하게 존재. backend / RBAC / DB / endpoint 무변경. cache-bust `v=20260522-admin-topbar-rbac`.
- Files:
  - `unit/feature-0003-agent-web-ui/src/static/app.js`:
    - `canOpenAdminConsole()` — `console_access !== undefined` 분기 추가, 없으면 `role.key === "admin"` fallback
  - `unit/feature-0003-agent-web-ui/src/static/index.html`:
    - cache-bust `v=20260522-console-access-gate` → `v=20260522-admin-topbar-rbac`
  - `unit/feature-0003-agent-web-ui/docs/TASK.md`: TASK-0102 entry 추가 + Current Status 갱신
  - `unit/feature-0003-agent-web-ui/docs/MODIFY.md`: 본 entry
  - `unit/feature-0003-agent-web-ui/docs/REVIEW.md`: REV-20260522-0005 [SKIPPED:non-policy-doc] 추가
  - `unit/feature-0003-agent-web-ui/docs/REPORT.md`: §1 Summary 상단에 TASK-0102 entry 추가
  - `unit/feature-0003-agent-web-ui/docs/FUNCTION.md`: AC-0269 추가
  - `docs/STATUS.md`: feature-0003 row 갱신

## CHG-20260522-0004
- Date: 2026-05-22
- Related Requirement: TASK-0100 (REQ-20260522-0004, Minor §12.3 — 관리 콘솔 버튼 RBAC gate 수정)
- Summary: TASK-0098 의 `can()` 단순화(`Boolean(state.user)`)로 인해 `canOpenAdminConsole()` 이 로그인한 모든 사용자에게 `true` 반환 → `관리 콘솔` 버튼이 admin 역할 이외의 사용자에게도 노출되던 이슈 수정. `_serialize_account()` 에 `console_access: bool` 최소 플래그 추가 + `canOpenAdminConsole()` 이 `state.user.console_access` 검사하도록 변경. TASK-0098 의 "permissions 전체 노출 차단" 설계 유지. backend RBAC catalog / DB schema / endpoint contract 무변경. cache-bust `v=20260522-console-access-gate`.
- Files:
  - `unit/feature-0003-agent-web-ui/src/app.py`:
    - `_serialize_account()` — `console_access: _account_has_permission(account, "console.access")` 플래그 추가 (payload 에 항상 포함)
  - `unit/feature-0003-agent-web-ui/src/static/app.js`:
    - `canOpenAdminConsole()` — `can("console.access")` → `Boolean(state.user?.console_access)` 로 변경
  - `unit/feature-0003-agent-web-ui/src/static/index.html`:
    - cache-bust `v=20260522-task-0098-perms` → `v=20260522-console-access-gate`
  - `unit/feature-0003-agent-web-ui/docs/TASK.md`: TASK-0100 entry 추가 + Current Status 갱신
  - `unit/feature-0003-agent-web-ui/docs/MODIFY.md`: 본 entry
  - `unit/feature-0003-agent-web-ui/docs/REVIEW.md`: REV-20260522-0004 [SKIPPED:non-policy-doc] 추가
  - `unit/feature-0003-agent-web-ui/docs/REPORT.md`: §1 Summary 상단에 TASK-0100 entry 추가
  - `docs/STATUS.md`: feature-0003 row tail 에 TASK-0100 완료 marker append
- Diff size: app.py +5 lines / app.js +5 lines / index.html 2 replace / docs 5 files
- Impact:
  - admin 역할(`console.access` 보유) 사용자만 `관리 콘솔` 버튼 표시 — 정상 동작 복원
  - 일반 사용자(operator/sales/pending) 는 버튼 미노출
  - `console.access` override grant 된 사용자는 버튼 노출 (RBAC 정합)
  - `_serialize_account()` 호출 모든 경로(로그인 / me / patch / bootstrap) 동일 적용
  - backend API 응답에 `console_access: true/false` 필드 추가 — 클라이언트 호환 변경 (기존 필드 제거 없음)
- Rollback Notes: `_serialize_account()` 의 `console_access` 필드 제거 + `canOpenAdminConsole()` 복원 (`return can("console.access")` 또는 `return Boolean(state.user)`) + index.html cache-bust 원복.

## CHG-20260522-0003
- Date: 2026-05-22
- Related Requirement: TASK-0099 (REQ-20260522-0003, Minor §12.3 — docs-only tracker hygiene)
- Summary: TASK-0073 audit subsystem followup backlog 8 entries (TASK-0086~0093) 8/8 완료 후 정리 cycle. TASK.md 의 stale `[ ]` 체크박스 2건 close: (1) line 152 TASK-0072 (main 통합 `f298f90` + post-deploy hotfix bundle TASK-0074/0075/0076/0077/0078/0079/0080 모두 deployed but 상태 `outside-voice-review` 미갱신), (2) line 2767 TASK-0073 `AGENT_AUDIT_ENABLED=0 + AGENT_MODE=prod` startup fail-closed acceptance (TASK-0092 V1-V3 fail-closed scenario 가 정확히 검증 → close). TASK.md 상단 Task Queue 에 TASK-0099 entry 추가. STATUS.md feature-0003 row tail 에 audit followup backlog 8/8 완료 marker append. docs-only — 코드 / RBAC / 스키마 / endpoint 변경 0.
- Files:
  - `unit/feature-0003-agent-web-ui/docs/TASK.md`:
    - line 152 TASK-0072 `[ ]` → `[x]` + 상태 텍스트 갱신 (deployed commits + hotfix bundle 명시)
    - line 2767 TASK-0073 startup fail-closed acceptance `[ ]` → `[x]` + TASK-0092 7 vector matrix V1-V3 cross-ref
    - 상단 Task Queue 에 TASK-0099 entry 추가 (본 closure cycle)
  - `unit/feature-0003-agent-web-ui/docs/MODIFY.md`: 본 entry
  - `unit/feature-0003-agent-web-ui/docs/REVIEW.md`: REV-20260522-0003 [SKIPPED:doc-only-tracker-hygiene]
  - `unit/feature-0003-agent-web-ui/docs/REPORT.md`: §1 Summary 상단에 TASK-0099 cycle entry 추가 + audit followup backlog 8/8 closure marker table
  - `docs/STATUS.md`: feature-0003 row tail 에 audit followup backlog 8/8 완료 marker append
- Diff size: docs-only. TASK.md 3 entry change (2 close + 1 new) + MODIFY/REVIEW/REPORT/STATUS 5 file 갱신. 코드 line change 0.
- Impact:
  - tracker hygiene — TASK.md 의 deployed task 가 정확히 `[x]` 로 close 되어 future cycle 의 audit followup backlog 검색 정확도 향상
  - TASK-0073 audit subsystem 의 7개 acceptance criteria 모두 close — Phase D 의 "deferred to followup cycle" 마지막 항목 (line 2767) 까지 정리 완료
  - 코드 / RBAC / 스키마 / endpoint 변경 없음 → 운영 영향 0
- Rollback Notes: docs-only. 5 file (TASK.md / MODIFY.md / REVIEW.md / REPORT.md / STATUS.md) 의 본 commit revert 로 즉시 복구 가능. 단 `[ ]` 로 돌릴 명분 없음 — 실제 deploy 상태 반영.

## CHG-20260522-0002
- Date: 2026-05-22
- Summary: TASK-0098 (REQ-20260522-0002, **Critical** §12.3 — Profile Drawer 탭 재구성 + 권한 정보 API 단위 차단) cycle ship. PR #49 multi-race rebase + ID reassign + squash commit. Codex outside voice 6 findings (1 blocker + 4 high + 1 medium) 흡수.
- Files:
  - `unit/feature-0003-agent-web-ui/src/static/index.html`: Profile Drawer 탭 5 → 4 (`[프롬프트, 보안 및 계정, API Vault, 내 감사 로그(gated)]`). 보안+계정 통합 pane (활동 정보 최상단 → 비밀번호 변경 → 세션/로그아웃). "권한 현황" DOM 제거. 첫 탭 `is-active` = "프롬프트". cache-bust `v=20260520-profile-audit` → `v=20260522-task-0098-perms`.
  - `unit/feature-0003-agent-web-ui/src/static/app.js`: `profilePermPillsEl` + `profileStateNoteEl` 변수 제거 + `renderProfile()` 의 호출 + `profileStateNote` 분기 제거. `openProfile(tab = "prompt")` 기본값 + `openProfileBtn` click handler 변경. `can(permission)` 함수를 `Boolean(state.user)` 분기로 단순화 (Codex F5). `apiFetch` 의 403 공통 처리 — toast `"요청을 수행할 수 없습니다."` + Promise reject. `_profileAuditHasReadPermission()` 도 `Boolean(state.user)` 분기. `buildPermissionPills()` 함수 자체는 dead code (호출 없음) 로 남김 — 별 cycle 의 cleanup 위임.
  - `unit/feature-0003-agent-web-ui/src/static/admin.js`: initialize() 가 `/api/auth/me` → `/api/admin/me` 전환 + `.catch(() => null)` 추가.
  - `unit/feature-0003-agent-web-ui/src/static/admin.html`: cache-bust `v=20260521-settings-listdetail` → `v=20260522-task-0098-perms`.
  - `unit/feature-0003-agent-web-ui/src/app.py`: `_serialize_account(account, *, include_permissions: bool = False)` 시그너처 + default `False`. 7 self callsite 자동 permissions 제거. admin callsite 3 곳 (`_list_accounts_for_admin`, admin account update, 신규 `/api/admin/me`) `include_permissions=True` 명시. 신규 `@app.get("/api/admin/me")` endpoint (console.access 보유자 200, 미보유 403, 비로그인 401). 일반 사용자 경로 403 메시지 5 패턴 9 callsite normalize — 모두 `"요청을 수행할 수 없습니다."` 통일. admin endpoint 의 403 메시지 보존.
  - `unit/feature-0003-agent-web-ui/tests/test_admin_me_rbac.py`: 신규 4 시나리오.
  - `unit/feature-0003-agent-web-ui/tests/test_auth_me_rbac.py`: 신규 5 시나리오.
  - `unit/feature-0003-agent-web-ui/docs/FUNCTION.md`: REQ-20260522-0002 + AC-0226~0234 9 항목 신규.
  - `unit/feature-0003-agent-web-ui/docs/TASK.md`: TASK-0098 queue entry + PLAN-APPROVED marker.
  - `unit/feature-0003-agent-web-ui/docs/REVIEW.md`: REV-20260522-0002 [AGENT-TEAM:codex-outside-voice].
  - `unit/feature-0003-agent-web-ui/docs/REPORT.md`: §1 Summary 갱신.
  - `docs/STATUS.md`: feature-0003 row prepend.
- 검증: py_compile + node --check + verify-completion --pre-commit PASS. 실 컨테이너 9 시나리오 smoke + UI dogfood 2 role 사용자 위임.
- Codex 6 findings 흡수 매핑: F1 (admin.js console.access blocker) → `/api/admin/me` 분리 / F2 (Option Y raw permission 비노출) → can() 단순화 + apiFetch 403 fallback + 메시지 normalize / F3 (403 메시지 권한명 노출) → 5 패턴 9 callsite normalize / F4 (누출 경로 다수) → default False 일괄 적용 / F5 (false 단순 전환 금지) → can() true 반환 + UI 표시 유지 / F6 (CSRF/race) → 현 backend SameSite + fresh permission 검사 안전.
- Multi-race rebase 영역: backup branch `backup/profile-tabs-restructure-pre-rebase` (677d48a tip) 에 원래 4 commit 보존. main HEAD `20f0344` 위에 squash commit. main 흡수 = PR #45 v3.10.0 + #47 TASK-0089 audit drawer + #48/#50 docs + #52 TASK-0094 첨부 multi-cycle Sprint 1 Phase 1 + #61 Phase 4 storage + DQA 브랜딩 (TASK-0097) + TASK-0095 GLOBAL prompt + TASK-0096 v2 (설정 list-detail). 의도 통합 = Profile Drawer 5 탭 → 4 탭 (audit 보존 + 3 탭 통합). ID reassign = TASK-0094→TASK-0098 / REQ-20260521-0001→REQ-20260522-0002 / AC-0199~0207→AC-0226~0234 / CHG·REV-20260521-0001~0004→CHG·REV-20260522-0002 / cache-bust `v=20260522-task-0098-perms`.

## CHG-20260521-0006
- Date: 2026-05-21
- Summary: TASK-0096 v2 (REQ-20260521-0004 follow-up). 사용자 직접 피드백 — "계정, 역할, 제품 탭과 일관된 디자인이 아닌것으로 확인되었습니다. 검색창을 포함하여, 해당 탭들과 일관된 디자인으로 구성해주세요." CHG-20260521-0005 의 sub-sidebar (`admin-settings-shell` + `admin-settings-nav`) 형태가 다른 탭의 5단 master-detail 패턴 (header → `admin-list-detail` (좌측 list-col + 우측 detail-col)) 과 시각 일관성 부족. v2 에서 sub-sidebar 전용 클래스 일괄 제거 + 계정/역할/제품 의 `admin-list-detail` / `admin-list-col` / `admin-detail-col` 그대로 차용 + `admin-list-row` 의 nav 변형 (`.admin-list-row--nav`, 체크박스 슬롯 hidden, full-width content) 추가. 검색창 = `admin-search` 재사용 (placeholder = "설정 항목 검색…"), 항목 카운트 = `admin-list-count` 재사용. 검색 필터는 row 의 `data-settings-tab` + `data-settings-group` + `data-settings-keywords` + textContent 를 합쳐 substring 매칭. UI restructure only — 데이터/API/권한 무영향.
- Files:
  - `unit/feature-0003-agent-web-ui/src/static/admin.html`:
    - `admin-settings-shell` + `admin-settings-nav` + `admin-settings-content` 구조 → 표준 `admin-list-detail` (`admin-list-col` (toolbar+search+`admin-list-head`+`admin-list`) + `admin-detail-col` (panel)) 로 교체. `admin-pane-hint` 단락 제거 (다른 탭과 일관 — pane-head 직접에 hint 없음).
    - 신규 hook id = `settingsSearch` (`admin-search`), `settingsListCount` (`admin-list-count`), `settingsList` (`admin-list`), `settingsDetail` (`admin-detail-col`). 기존 `globalPromptEditorMount` 보존.
    - 첫 항목은 `<button class="admin-list-row admin-list-row--nav is-active" role="option" aria-selected="true" data-settings-tab="global-prompt" data-settings-group="시스템 프롬프트" data-settings-keywords="...">`. row 본문은 `admin-list-row-cb` (visual hidden) + `admin-list-row-main` (`admin-list-row-title` + `admin-list-row-meta` 2줄).
    - section label = `admin-list-section-label` (UPPERCASE, head row 안). 차후 항목 추가 시 새 section label + row 묶음을 등재.
    - cache-buster `v=20260521-settings-subnav` → `v=20260521-settings-listdetail`.
  - `unit/feature-0003-agent-web-ui/src/static/styles.css`:
    - sub-sidebar 전용 셀렉터 (`.admin-settings-shell`, `.admin-settings-nav`, `.admin-settings-nav-group-label`, `.admin-settings-nav-item[.is-active]`, `.admin-settings-nav-label`, `.admin-settings-nav-hint`, `.admin-settings-content`) + 760px responsive 블록 일괄 제거. 함께 `.admin-pane-hint` 도 제거 (markup 에서도 미사용).
    - 신규: `.admin-list-section-label` (UPPERCASE 11px, head row 안). `.admin-list-row.admin-list-row--nav` 변형 (grid 1fr, button 전용 reset, cb 슬롯 hidden, meta 본문 영구 노출). `.admin-settings-panel`/-`head h3`/-`hint`/-`body` 본문 스타일은 유지하되 자체 border 제거 (`admin-detail-col` 의 surface 가 이미 border 책임).
  - `unit/feature-0003-agent-web-ui/src/static/admin.js`:
    - `mountSettingsSections()` 가 `bindSettingsList()` + `bindSettingsSearch()` + `updateSettingsListCount()` + `activateSettingsPanel(activeTab)` 호출. `bindSettingsNav()` 는 v1 의 `adminSettingsNav` 셀렉터 의존이라 제거.
    - `bindSettingsList()` — `#settingsList` 에 위임 click. row `[data-settings-tab]` 매칭.
    - `bindSettingsSearch()` — `#settingsSearch` 에 `input` 이벤트 → `applySettingsSearchFilter(value)`.
    - `applySettingsSearchFilter(query)` — 모든 row 에 대해 합친 haystack (`data-settings-tab` + `data-settings-group` + `data-settings-keywords` + textContent) lower-case substring 매칭, 비매칭 row 는 `display:none`.
    - `updateSettingsListCount()` — 가시 row 수 / 전체 row 수 형식 ("1건" 또는 "1 / 2건").
    - `activateSettingsPanel(tab)` — `#settingsList` + `#settingsDetail` 셀렉터로 갱신, `aria-selected` 동기화 추가. mount lazy 로직은 동일.
  - `unit/feature-0003-agent-web-ui/docs/FUNCTION.md`: AC-0210 갱신 — list-detail 패턴 + 검색 hook 표기.
  - `unit/feature-0003-agent-web-ui/docs/TASK.md`: TASK-0096 entry + Last Updated 갱신 (v2 흡수).
  - `unit/feature-0003-agent-web-ui/docs/MODIFY.md`: 본 entry.
  - `unit/feature-0003-agent-web-ui/docs/REVIEW.md`: REV-20260521-0006.
  - `unit/feature-0003-agent-web-ui/docs/REPORT.md`: §1 Summary follow-up note.
- Verification:
  - 정적 검사 N/A (frontend only).
  - 사후 검증: web 컨테이너 재배포 → `/browse` 로 설정 탭 진입 → header (Settings 라벨 + 제목) + 좌측 list-col (검색창 + section-label `시스템 프롬프트` + nav row `전역 시스템 프롬프트`) + 우측 detail-col (panel head + textarea body) 노출 확인 + 검색창에 "전역" 입력 시 row 1건 표시 / "missing" 입력 시 0 / 1 표시 + 콘솔 errors 없음.
- Risks:
  - row 의 hidden 처리는 `style.display = "none"` 인라인. screen reader 가 카운트 mismatch 가능 — 향후 `aria-hidden` 동기화 보강 후보 (현 build 는 카운트 라이브 영역으로 충분).
  - `admin-list-row--nav` 가 다른 탭의 row hover/active 스타일 (`admin-list-row.is-active` 의 primary-soft) 을 그대로 상속 — 시각 정합 OK 이며 권한 grid 처럼 추가 컬러 token 불필요.
- Trace: REQ-20260521-0004 → TASK-0096 → CHG-20260521-0006 → REV-20260521-0006 (CHG-20260521-0005 follow-up redesign).

## CHG-20260521-0005
- Date: 2026-05-21
- Summary: TASK-0096 (REQ-20260521-0004, **Minor** §12.3 — `설정` pane sub-sidebar + panel 확장 패턴). 사용자 직접 요청 — TASK-0095 검증 완료 후속, "`설정` 탭 내부 화면을 `계정`, `역할`, `제품` 과 같이 패널을 분리해줄 수 있을까요? 차후 `전역 시스템 프롬프트` 항목 외에도 설정 내 많은 항목이 추가될 예정인데 현재는 확장성이 너무 좁게 구현되어 있습니다." 단일 sub-section 누적 구조 → 좌측 sub-sidebar (항목 nav) + 우측 panel 의 2-column grid 확장 패턴으로 전환. 새 항목 추가 절차 = `<button data-settings-tab="X">` + `<article data-settings-panel="X">` + `SETTINGS_PANEL_MOUNTERS["X"] = mountFn` 3 단계. mount 함수는 panel 첫 활성화 시 1회 실행 (lazy mount, `adminState.settings.mountedPanels` Set). UI restructure only — 데이터/API/권한 무영향.
- Files:
  - `unit/feature-0003-agent-web-ui/src/static/admin.html`:
    - `admin-settings-list` / `admin-settings-section` (TASK-0095 단일 누적 구조) → `admin-settings-shell` (grid 240px + 1fr) + `admin-settings-nav` (sub-sidebar) + `admin-settings-content` (panel 컨테이너) 로 교체.
    - 첫 nav item = `data-settings-tab="global-prompt"` (is-active), 첫 panel = `data-settings-panel="global-prompt"` (is-active). nav 안에 그룹 라벨 (`시스템 프롬프트`) + label/hint 2-line 구조.
    - 신규 hook id = `adminSettingsNav`, `adminSettingsContent`. 기존 `globalPromptEditorMount` 는 panel body 안으로 이동 (변경 없음, 셀렉터 호환).
    - cache-buster `v=20260521-settings-tab` → `v=20260521-settings-subnav`.
  - `unit/feature-0003-agent-web-ui/src/static/styles.css`:
    - `.admin-settings-list` / `.admin-settings-section` (TASK-0095) 셀렉터 제거 (markup 에서 사용 안 됨).
    - `.admin-settings-shell` (grid 240px / 1fr), `.admin-settings-nav` (sticky, border-right), `.admin-settings-nav-group-label` (uppercase 11px), `.admin-settings-nav-item` (vertical flex + label/hint), `.admin-settings-nav-item.is-active` (소프트 surface 강조), `.admin-settings-content` (left padding 20), `.admin-settings-panel` (default `display:none`) + `.is-active` (`display:flex`), `.admin-settings-panel-head/-hint/-body` 스타일 추가.
    - `@media (max-width: 760px)` — sub-sidebar 가 가로 wrap 으로 collapse, content 가 그 아래로 stack.
  - `unit/feature-0003-agent-web-ui/src/static/admin.js`:
    - `adminState.settings` 에 `activeTab` (default `"global-prompt"`) + `mountedPanels` (Set) 추가.
    - `SETTINGS_PANEL_MOUNTERS` 객체 신설 — key=tab id, value=mount 함수. 차후 항목 추가 시 본 객체 한 줄 등록만으로 확장.
    - `mountSettingsSections()` 가 `bindSettingsNav()` + `activateSettingsPanel(activeTab)` 호출하는 형태로 재정의.
    - `bindSettingsNav()` — 1회 위임 click 핸들러 (`data-settings-tab` 매칭).
    - `activateSettingsPanel(tab)` — nav/panel `.is-active` toggle + 첫 활성화 시 mount 함수 1회 실행 + `mountedPanels` 기록.
    - `mountGlobalPromptPanel()` — TASK-0095 의 인라인 글로벌 프롬프트 마운트 로직을 단독 함수로 추출. 권한 게이트 + read-only disabled 처리 동일.
  - `unit/feature-0003-agent-web-ui/docs/FUNCTION.md`: AC-0210 신설 (sub-sidebar + panel 패턴 정의).
  - `unit/feature-0003-agent-web-ui/docs/TASK.md`: TASK-0096 entry + Last Updated 갱신.
  - `unit/feature-0003-agent-web-ui/docs/MODIFY.md`: 본 entry.
  - `unit/feature-0003-agent-web-ui/docs/REVIEW.md`: REV-20260521-0005.
  - `unit/feature-0003-agent-web-ui/docs/REPORT.md`: §1 Summary follow-up note.
- Verification:
  - py_compile / 정적 검사 N/A — 본 cycle 은 frontend 만 변경 (HTML/CSS/JS).
  - 사후 검증: web 컨테이너 재배포 → `/static/admin.html` 응답에 `admin-settings-shell` / `admin-settings-nav-item[data-settings-tab="global-prompt"]` markup 노출 확인 + `/browse` 로 좌측 sub-sidebar 노출 + 활성 panel 의 textarea 본문 노출 확인 + 권한 grid 회귀 없음 확인.
- Risks:
  - 차후 항목 추가 시 mount 함수가 panel 첫 활성화 후에만 작동하므로, 첫 진입 항목에서 다른 탭 데이터 의존 시 명시적 prefetch 필요. 본 cycle 의 `global-prompt` 단일 항목은 자기 충족.
  - `bindSettingsNav` 의 `dataset.bound = "1"` 가드로 중복 핸들러 부착 방지. 다른 admin tab 패턴과 동형.
- Trace: REQ-20260521-0004 → TASK-0096 → CHG-20260521-0005 → REV-20260521-0005.

## CHG-20260521-0004
- Date: 2026-05-21
- Summary: TASK-0095 follow-up hot-fix — fast-path catchup (`_ensure_seed_catchup`) 에 `_ensure_seed_global_system_prompt(conn)` 호출 누락을 보정. CHG-20260521-0003 이 slow path (`_ensure_web_tables`) 에만 helper 를 배치했지만, 기존 배포는 fast path 만 타기 때문에 GLOBAL scope row 가 자동 seed 되지 않았다. live deploy 후 DB 검증으로 발견 — `WebSystemPrompts WHERE Scope='global'` 0 row, 모든 응답이 코드 상수 fallback 만 작동. 관리 콘솔 `설정` 탭의 textarea 가 빈 채로 노출되어 운영자가 매번 직접 base prompt 를 입력해야 하는 UX 회귀 발생.
- Files:
  - `unit/feature-0003-agent-web-ui/src/app.py`:
    - `_ensure_seed_catchup(conn)` 안 `_ensure_seed_role_system_prompts(conn)` 직후에 `_ensure_seed_global_system_prompt(conn)` 추가. idempotent — 기존 row 가 있으면 no-op, agent_core import 실패 시 silent skip.
  - `unit/feature-0003-agent-web-ui/docs/MODIFY.md`: 본 entry.
  - `unit/feature-0003-agent-web-ui/docs/REVIEW.md`: REV-20260521-0004.
  - `unit/feature-0003-agent-web-ui/docs/REPORT.md`: §1 Summary follow-up note.
  - `unit/feature-0003-agent-web-ui/docs/TASK.md`: TASK-0095 entry sub-bullet.
- Verification:
  - py_compile PASS (app.py).
  - 사후 검증 절차: web 컨테이너 재배포 → `SELECT * FROM WebSystemPrompts WHERE Scope='global'` 1 row + Content 본문 = `agent_core.SYSTEM_PROMPT` (3179 chars) 일치 → `GET /api/admin/system-prompts?scope=global` 응답 `prompt.content` 비어있지 않음 확인.
- Risks:
  - 기존 row 가 빈 본문으로 이미 누군가 저장한 환경에서는 본 helper 가 no-op (existing row truthy → return). 의도한 동작이며, 운영자가 직접 갱신해야 한다.
- Trace: REQ-20260521-0003 → TASK-0095 → CHG-20260521-0004 → REV-20260521-0004 (CHG-20260521-0003 follow-up fix).

## CHG-20260520-0010
- Date: 2026-05-21
- Related Requirement: TASK-0087, REQ-20260520-0002
- Summary: 외부 LAN trust 강화 — TASK-0073 Eng review E3 의 deferred 항목 (`_get_client_ip(request)` X-Forwarded-For 무조건 trust = 사내 LAN + Caddy proxy 전제, 외부 LAN/공개 인터넷 노출 시 IP spoof 위험) 을 명시적 정책 + 코드로 lock-in. Plan v1 (RFC1918 trust + silent skip) → Codex outside voice review 6 findings (Major 5 + Minor 1) → Plan v2 (Caddy XFF 정규화 + mode-aware fail-loud + XFF IP 검증) 흡수. 사용자 명시 결정: RFC1918 default 유지 (사내 dev/staging 전제) + docker-compose port mapping 변경은 별 cycle. 본 변경은 feature-0003 + feature-0006 dual ownership — feature-0006 의 `CHG-20260520-0010` 와 동일 의의.
- Files:
  - `unit/feature-0003-agent-web-ui/src/app.py`:
    - imports 에 `ipaddress`, `sys` 추가 (알파벳 순 삽입)
    - `_parse_trusted_proxies(raw) -> tuple[_TrustedNetwork, ...]` helper 신설 — 콤마 분리 + `ipaddress.ip_network(token, strict=False)` 파싱. invalid 토큰은 `AGENT_MODE in {prod, staging}` 에서 `RuntimeError` startup, dev/test/"" 에서 stderr WARNING + 해당 토큰만 skip
    - module-level `WEB_TRUSTED_PROXIES = _parse_trusted_proxies(os.getenv("WEB_TRUSTED_PROXIES", ""))`
    - `ENABLE_WEB_TLS_PROXY=1` + `WEB_TRUSTED_PROXIES` empty 조합 startup gate — prod/staging `RuntimeError`, dev/test stderr WARNING (PIPA §29 audit `IpAddr` 품질 회귀 경고)
    - `_is_trusted_proxy(host) -> bool` helper — host 가 `WEB_TRUSTED_PROXIES` CIDR 화이트리스트 안인지 검증
    - `_get_client_ip(request) -> str` 재작성 — `direct_ip = request.client.host`, direct_ip 가 trusted proxy 이면 `X-Forwarded-For` 첫 토큰 사용 + `ipaddress.ip_address(first)` 파싱 검증 + 실패 시 direct_ip fallback. 그 외 모두 direct_ip 반환
  - `unit/feature-0003-agent-web-ui/docs/TASK.md`: TASK-0087 checkbox close + §2.9 Implementation Plan 신설 (사용자 in-cycle 결정 3 항목 + Phase A~E + 8 test 시나리오 + REV-20260520-0010 정본 + PLAN-APPROVED 마커)
  - `unit/feature-0003-agent-web-ui/docs/MODIFY.md`: 본 entry
  - `unit/feature-0003-agent-web-ui/docs/REVIEW.md`: REV-20260520-0010 [AGENT-TEAM:codex-outside-voice] (Verdict: NEEDS_REVISION, 6 findings Major 5 + Minor 1, 사용자 명시 결정으로 Major 1 거부 + 나머지 5 흡수)
  - `unit/feature-0003-agent-web-ui/docs/REPORT.md`: §1 Summary 상단 TASK-0087 cycle entry 추가
  - `unit/feature-0003-agent-web-ui/docs/TEST.md`: §4 Audit subsystem followup 에 TASK-0087 시나리오 8 건 추가
  - `unit/feature-0003-agent-web-ui/docs/FUNCTION.md`: AC-0205 / AC-0206 / AC-0207 신설
  - `unit/feature-0006-lan-proxy-access/src/caddy/Caddyfile`: `reverse_proxy web:8000` 블록에 `header_up X-Forwarded-For {client_ip}` 추가 (Caddy 가 받은 임의 XFF 를 본인이 본 TCP peer IP 로 덮어씀 → multi-hop / spoof 차단)
  - `unit/feature-0006-lan-proxy-access/docs/TASK.md`: TASK-0006 신규 entry + Task Queue
  - `unit/feature-0006-lan-proxy-access/docs/MODIFY.md`: CHG-20260520-0010 (dual ownership)
  - `unit/feature-0006-lan-proxy-access/docs/REVIEW.md`: REV-20260520-0010 (dual ownership)
  - `unit/feature-0006-lan-proxy-access/docs/REPORT.md`: §1 Summary cycle entry 추가
  - `unit/feature-0006-lan-proxy-access/docs/TEST.md`: TEST-0004 (caddy validate) 추가
  - `unit/feature-0006-lan-proxy-access/docs/FUNCTION.md`: AC-0004 (XFF 정규화) 신설
  - `docs/SECURITY.md` §9.7: 기존 "deferred to feature-0006" 마커를 8 bullet 정책 (Caddy XFF 정규화 / 조건부 trust / XFF token 검증 / RFC1918 사용자 명시 결정 trade-off / mode-aware fail-loud / proxy mode + empty / schema 호환 / share token 미래 결합) 으로 교체
- Diff size: app.py +51 lines (`_parse_trusted_proxies` + `WEB_TRUSTED_PROXIES` + proxy-mode gate + `_is_trusted_proxy` + `_get_client_ip` 재작성 — 기존 9 lines → 60 lines), Caddyfile +1 line, SECURITY.md §9.7 +9 lines (3 lines → 12 lines).
- Impact:
  - **audit `IpAddr` 품질**: 사내 LAN dev/staging 환경에서 audit IP 가 정확히 클라이언트 IP 로 기록 — 기존 동작 유지 (`WEB_TRUSTED_PROXIES` RFC1918 권장값 설정 시).
  - **외부 LAN spoof 차단**: Caddy 가 받는 임의 `X-Forwarded-For` 가 무시되고 Caddy 가 본 TCP peer IP 로 정규화. web 의 `_get_client_ip()` 가 direct connection IP 검증 후 XFF 사용 — 외부에서 임의 XFF 주입 attack 차단.
  - **malformed env 운영자 인지**: prod/staging 에서 invalid CIDR 또는 proxy mode + empty env 조합이 startup 실패 → 운영자가 즉시 인지.
  - **backward 호환 (default)**: `WEB_TRUSTED_PROXIES` 미설정 = `_get_client_ip()` 가 항상 direct_ip 반환. caddy compose 환경에서는 audit IP 가 caddy container IP 가 됨 — proxy mode + empty env warning/fatal 로 회귀 가시화.
  - **RBAC catalog 변경 없음**.
- Rollback Notes:
  - 코드 revert: `_get_client_ip()` 9 lines 원본 복원 + `_parse_trusted_proxies` / `WEB_TRUSTED_PROXIES` / proxy-mode gate / `_is_trusted_proxy` 삭제 + import `ipaddress` / `sys` 제거.
  - Caddyfile revert: `header_up X-Forwarded-For {client_ip}` 한 줄 제거.
  - SECURITY.md §9.7 revert: 8 bullet 정책 → 기존 3 bullet ("deferred to feature-0006") 복원.
  - schema 변경 없음 → DB rollback 불필요.

## CHG-20260521-0003
- Date: 2026-05-21
- Summary: TASK-0095 (REQ-20260521-0003, **Major** §12.3 — GLOBAL system prompt layer 신설). 시스템 프롬프트 누적 구조의 최상위 base 를 코드 상수 hard-code 에서 `WebSystemPrompts WHERE Scope='global'` row 로 이전. 모든 LLM 응답의 base prompt 가 운영자 관리 콘솔에서 관리 가능. RBAC 권한 2 종 신설 (`system_prompt.global.read` / `.write`, group=`settings`). 관리 콘솔 sidebar 에 `설정` 탭 + 확장 가능한 `admin-settings-section` sub-section 패턴 도입.
- Files:
  - `unit/feature-0002-agent-core/src/agent_core.py`:
    - `compose_system_prompt(conn, ...)` 함수 진입부 — `WebSystemPrompts WHERE Scope='global' AND ProductId IS NULL AND RoleId IS NULL AND AccountId IS NULL LIMIT 1` 조회 + 성공 시 base 로 사용, 실패 / row 없음 / 빈 본문 시 코드 상수 `SYSTEM_PROMPT` fallback. `parts: list[str] = [base_prompt]` 로 누적 시작.
  - `unit/feature-0003-agent-web-ui/src/app.py`:
    - `_ensure_seed_global_system_prompt(conn)` helper 신설 (after `_ensure_seed_role_system_prompts`): idempotent — 기존 row 있으면 no-op, 없으면 `agent_core.SYSTEM_PROMPT` 본문을 seed 로 INSERT. import / seed 본문 빈 경우 silent skip.
    - 부트스트랩 (`_ensure_seed_catchup` / `_ensure_web_tables` 후속) 에서 helper 호출.
    - `PERMISSION_DEFINITIONS` 에 `system_prompt.global.read` / `system_prompt.global.write` 2 권한 추가 (group=`settings`).
    - `_ensure_seed_roles` 의 admin 자동 grant catchup list 에 두 권한 코드 추가.
    - `GET /api/admin/system-prompts` scope allowlist 에 `global` 추가 + `system_prompt.global.read` 권한 가드 + `product_id` / `role_id` / `account_id` 인자 NULL 강제.
    - `PUT /api/admin/system-prompts` 동일 패턴 (`system_prompt.global.write` 권한 가드).
  - `unit/feature-0003-agent-web-ui/src/static/admin.html`:
    - sidebar 에 `시스템` 그룹 라벨 + `설정` 탭 (`data-admin-tab="settings"`) 추가.
    - `<section data-admin-pane="settings">` pane 신설 — `<article data-settings-section="global-prompt">` sub-section 컨테이너 + `<div id="globalPromptEditorMount">` mount point.
    - cache-bust 토큰 `v=20260519-audit-tab` → `v=20260521-settings-tab`.
  - `unit/feature-0003-agent-web-ui/src/static/admin.js`:
    - `PERMISSION_GROUP_ORDER` 에 `settings` 추가 (`product` 와 `misc` 사이).
    - `PERMISSION_GROUP_LABELS.settings = "시스템 설정"`.
    - `ADMIN_PERMISSION_SECTIONS.manage` 에 `settings` 그룹 포함.
    - `buildSystemPromptEditor({scope})` — `isGlobal` boolean + product select 조건 (`!isGlobal && scope !== "product" && !fixedProductId`) 으로 global scope 일 때 product 드롭다운 미렌더.
    - `switchTab("settings")` handler — `adminState.settings.initialized` 가드 + `mountSettingsSections()` 호출.
    - `mountSettingsSections()` — `system_prompt.global.read` 권한 검사 + `buildSystemPromptEditor({scope:'global', mountId:'globalPromptEditorMount'})` 마운트 + `system_prompt.global.write` 미보유 시 textarea read-only.
  - `unit/feature-0003-agent-web-ui/src/static/app.js`:
    - `PERMISSION_GROUP_ORDER` 에 `settings` 추가.
    - `PERMISSION_GROUP_LABELS.settings = "시스템 설정"`.
    - `WORK_SCREEN_PERMISSION_SECTIONS.manage` 에 `settings` 그룹 포함.
    - `permissionGroupOf(code)` — `system_prompt.global.` 접두사 우선 `settings` 그룹으로 매핑, 그 외 `system_prompt.` 는 기존대로 `product` fallback.
    - `PERMISSION_LABELS` / `PERMISSION_DESCRIPTIONS` 에 `system_prompt.global.read` / `.write` 2 entry 추가.
  - `unit/feature-0003-agent-web-ui/src/static/styles.css`:
    - `.admin-pane-hint` / `.admin-settings-list` / `.admin-settings-section` / `.admin-settings-section-head h3` / `.admin-settings-section-hint` / `.admin-settings-section-body` rules 추가 — sub-section 카드 패턴 (border + padding + flex-column gap), 차후 운영 항목 추가 시 동일 패턴 재사용.
  - `unit/feature-0003-agent-web-ui/docs/TASK.md`: TASK-0095 entry + Plan §2.7 PLAN-APPROVED marker (ms.mckim.gpt@gmail.com, 2026-05-21).
  - `unit/feature-0003-agent-web-ui/docs/FUNCTION.md`: REQ-20260521-0003 추가 + AC-0011 갱신 (5 layer 명시) + AC-0199 ~ AC-0204 신설.
  - `unit/feature-0003-agent-web-ui/docs/MODIFY.md`: 본 entry.
  - `unit/feature-0003-agent-web-ui/docs/REVIEW.md`: REV-20260521-0003.
  - `unit/feature-0003-agent-web-ui/docs/REPORT.md`: §1 Summary sticky note.
- Schema: 변경 없음 — `WebSystemPrompts.Scope VARCHAR(16)` 가 이미 'global' 을 수용. UNIQUE INDEX `UX_WebSystemPrompts_Scope` 가 `(Scope, ProductId, RoleId, AccountId)` 정합으로 working — global row 는 `(scope='global', product_id=NULL, role_id=NULL, account_id=NULL)` 단 1건.
- Audit: 기존 `admin.system_prompt.update` ActionCode + `_audit_admin_mutation` Same tx hook 재사용. ChangeJson 의 `scope` 필드가 `'global'` 인 row 가 새로 등장 — `_audit_admin_mutation` 의 redaction allowlist 에 system_prompt.content 본문이 이미 미포함 (SECURITY §9.2 정합). content_full 마스킹 정책은 GLOBAL scope 에도 그대로 적용.
- RBAC default grant 정책: admin role 만 자동 grant. operator/sales/dba/pending 은 명시 grant 가 없는 한 미보유 — 모든 LLM 응답에 영향가는 권한이라 운영자 한정 패턴 의도적으로 채택.
- Verification:
  - py_compile PASS (agent_core.py, app.py — 단 agent_core.py 76 line `'\``' SyntaxWarning 은 pre-existing, 본 cycle 무관).
  - node --check PASS (admin.js, app.js).
- Risks:
  - GLOBAL row 본문이 잘못 입력되면 모든 LLM 응답에 영향 — 운영자 한정 권한 + 빈 본문 시 코드 상수 fallback 으로 위험 완화.
  - 부트스트랩 시점 `from agent_core import SYSTEM_PROMPT` 가 실패할 수 있는 환경 (web 컨테이너 정상 환경에선 무관) — 본 helper 는 lazy try/except 으로 처리, seed 자체 skip 시에도 compose_system_prompt 는 자기 fallback 으로 정상 작동.
  - live runtime smoke (관리 콘솔 `설정` 탭 진입 + 본문 수정 + LLM 호출 시 적용 확인) 는 사용자 검증으로 위임.
- Trace: REQ-20260521-0003 → TASK-0095 → CHG-20260521-0003 → REV-20260521-0003.

## CHG-20260520-0009
- Date: 2026-05-20
- Summary: TASK-0089 (REQ-20260520-0004, **Minor** §12.3 — 작업 화면 audit drawer UX). profile drawer "내 감사 로그" 탭 신설 + 신규 backend endpoint 2 (`/api/profile/audits` + detail) + frontend (HTML + JS + CSS). Codex outside voice review 5 critical findings + 2 minimum-fix 흡수 v2 redesign.
- Files:
  - `unit/feature-0003-agent-web-ui/src/app.py`: 신규 endpoint 2 (`list_profile_audit_events` line ~9981, `get_profile_audit_event` line ~10043). 기존 helper 재사용 (`_audit_parse_filter_params`, `_audit_compose_where(scope="own")`, `_audit_row_to_dict`, `_audit_build_self_filter_sql`). `scope="own"` **강제** — `.any` 보유자도 본인만 (Codex C2).
  - `unit/feature-0003-agent-web-ui/src/static/index.html`: drawer-tab "내 감사 로그" (line 228, `data-profile-tab="audit"` + id `profileAuditTab` + hidden default) + drawer-pane (filter row mini 3 필드 + 1-column list + pagination + inline detail). cache-bust `v=20260520-profile-audit`.
  - `unit/feature-0003-agent-web-ui/src/static/app.js`: `state.profileAudit = {items, selectedId, filters, nextCursor, loading, forbidden}` + helper 6 (`_profileAuditEscapeHtml`, `_profileAuditFormatDt`, `_profileAuditHasReadPermission`, `updateProfileAuditTabVisibility`, `_profileAuditReadFilters`, `_profileAuditClearFilters`) + loader (`loadProfileAuditList`) + renderer (`renderProfileAuditList`, `renderProfileAuditDetail`) + handlers (`attachProfileAuditHandlers`). tab click handler audit branch + `renderProfile()` tab visibility wire.
  - `unit/feature-0003-agent-web-ui/src/static/styles.css`: `.profile-audit-*` ~15 클래스 — filter row + 1-column list + row hover/selected + pagination + inline detail dl + `<pre>` overflow:auto 수평 스크롤 (Codex C4).
  - `unit/feature-0003-agent-web-ui/docs/TASK.md`: §2.8 + TASK-0089 [x].
  - `unit/feature-0003-agent-web-ui/docs/REVIEW.md`: REV-20260520-0009.
  - `unit/feature-0003-agent-web-ui/docs/REPORT.md`: §1 Summary.
  - `unit/feature-0003-agent-web-ui/docs/TEST.md`: §4 본 cycle 결과.
  - `unit/feature-0003-agent-web-ui/docs/FUNCTION.md`: AC-0194.
- Codex outside voice 5 findings 흡수:
  - C1 URL 의미 mismatch → `/api/profile/audits` 신설
  - C2 `.any > .own` 우선 → backend `scope="own"` 강제
  - C3 CSV export drawer 위험 → 미노출 (admin 한정)
  - C4 drawer 폭 1-column + ChangeJson 수평 스크롤
  - C5 권한 race → tab visibility + 403 graceful
- Verification:
  - py_compile PASS
  - node --check app.js PASS
  - routing smoke: `/api/profile/audits` + `/api/profile/audits/{event_id}` 등록 확인
  - `list_profile_audit_events` + `get_profile_audit_event` 함수 존재 확인
- Risks: live browser smoke (drawer tab 클릭 → list 표시 → click → inline detail expand → filter 적용 / 403 시 "권한 없음") PR merge 후 사용자 위임. `audit.read.own` 권한 없는 사용자에게 tab 자체가 hidden — `updateProfileAuditTabVisibility()` 가 `renderProfile()` 마다 호출.
- Trace: REQ-20260520-0004 → TASK-0089 → CHG-20260520-0009 → REV-20260520-0009.

## CHG-20260520-0008
- Date: 2026-05-20
- Summary: TASK-0090 (REQ-20260520-0005, **Minor** §12.3 — CSV streaming export). `/api/admin/audits/export.csv` hard cap 50k row 제거 + StreamingResponse + keyset cursor pagination 전환. Codex outside voice review 5 critical findings + 2 minimum-fix 흡수 후 v2 redesign.
- Files:
  - `unit/feature-0003-agent-web-ui/src/app.py`:
    - `StreamingResponse` import 추가 (line 28).
    - 신규 helper `_audit_export_filter_hash(params)` (~line 9466): filter PII 회피용 sha256[:16] hash.
    - 신규 const `_AUDIT_EXPORT_CHUNK_SIZE = 500` + `_AUDIT_EXPORT_FLUSH_BYTES = 65536`.
    - `export_audit_events_csv` endpoint 전면 재작성: 2-phase (짧은 auth conn + max_id capture + start audit → sync generator with streaming-only conn + chunked SELECT + byte-threshold flush + try/finally + complete audit).
  - `docs/SECURITY.md §9.5`: `audit.export` 설명 갱신 (hard cap 50k 제거 + StreamingResponse + max_id high-water + self-audit + 동시 제한 별 cycle).
  - `unit/feature-0003-agent-web-ui/docs/TASK.md`: §2.7 + TASK-0090 [x].
  - `unit/feature-0003-agent-web-ui/docs/REVIEW.md`: REV-20260520-0008.
  - `unit/feature-0003-agent-web-ui/docs/REPORT.md`: §1 Summary.
  - `unit/feature-0003-agent-web-ui/docs/TEST.md`: §4 본 cycle 결과.
  - `unit/feature-0003-agent-web-ui/docs/FUNCTION.md`: AC-0193.
- Codex outside voice 5 findings 흡수:
  - C1 async generator + sync mysql → sync generator (def csv_iter) + streaming-only conn (generator 내부 finally)
  - C2 consistent snapshot → max_id high-water mark (long transaction 회피)
  - C3 query plan 미보장 → TEST.md EXPLAIN 기록 (future cycle, live mysql)
  - C4 cap 제거 = DoS/계약 변경 → SECURITY 갱신 + export self-audit + 동시 제한 별 cycle followup
  - C5 cleanup → generator 내부 try/finally (cursor + conn + complete audit)
- 추가: chunk_size 1000→500, 64KiB byte-threshold flush, CRLF 유지 (BOM 추가 안 함).
- Self-audit ActionCode 신설: `audit.export.start`, `audit.export.complete`, `audit.export.aborted` (purge 패턴 답습).
- Verification:
  - py_compile PASS
  - lightweight smoke: _AUDIT_EXPORT_CHUNK_SIZE=500 ✓, _AUDIT_EXPORT_FLUSH_BYTES=65536 ✓, helper 존재 ✓, StreamingResponse import ✓, filter_hash deterministic ✓
- Risks: live runtime smoke (PATCH 호출 + WebAuditEvents row 검증) PR merge 후 사용자 위임. 동시 export 제한 별 cycle (multi-worker semaphore 정합 검토). representative filters EXPLAIN 분석 별 cycle.
- Trace: REQ-20260520-0005 → TASK-0090 → CHG-20260520-0008 → REV-20260520-0008.

## CHG-20260520-0007
- Date: 2026-05-20
- Summary: TASK-0088 (REQ-20260520-0003, **Minor** §12.3 — `slow_query_log` 통합 ADR-0020 결정, docs only). ADR-0019 의 Codex C1 lock-in 의 최종 결론 — **Option C Decoupled 채택** (slow_query_log 와 WebAuditEvents 통합 안 함). Codex outside voice review 5 critical findings + 2 minimum-fix 흡수 후 v2 redesign 적용.
- Files:
  - `docs/DECISIONS.md`: ADR-0020 신설 (line 207~ ADR-0019 Consequences 다음). 4 section — Context (current state: not enabled, forward-looking) + Decision (Option C Decoupled, raw SQL PII 차단 1순위) + Options 검토 (A/B reject 구체 사유 + C 채택) + Recommended performance path (PS digest-first 1차, slow_query_log incident enable 2차) + Security policy + Consequences (외부 SaaS trigger 4 선행 조건). ADR-0019 Consequences 의 "별 cycle 분리" 라인에 ADR-0020 cross-reference 추가.
  - `docs/SECURITY.md §9.9`: ADR-0020 cross-reference + raw SQL = 민감 로그 + admin UI/ChangeJson 복제 금지 + PS digest-first 정책.
  - `unit/feature-0003-agent-web-ui/docs/TASK.md`: TASK-0088 [ ]→[x] + §2.6 본 plan PLAN-APPROVED.
  - `unit/feature-0003-agent-web-ui/docs/REVIEW.md`: REV-20260520-0007 entry.
  - `unit/feature-0003-agent-web-ui/docs/REPORT.md`: §1 Summary 갱신.
  - `unit/feature-0003-agent-web-ui/docs/TEST.md`: §4 본 cycle 결과 (docs only, ADR review trace).
- Decision 요지: slow_query_log 와 WebAuditEvents 의 통합 reject. 운영 성능 관측 = performance_schema/sys digest views (1차) + slow_query_log incident enable (2차). 외부 SaaS/multi-tenant trigger 시 `performance-log.read` permission + redaction/sampling + threat model ADR 선행 필수.
- Codex outside voice 5 findings 흡수:
  - **C1** current state framing 정정 (not enabled, forward-looking)
  - **C2** raw SQL PII 차단을 주 근거로 (1순위)
  - **C3** Option A reject 재작성 (semantic pollution + raw SQL PII + ChangeJson bloat + actor/target 의미 부재)
  - **C4** Option B reject 재작성 (raw SQL exfiltration + mount/race + DoS + 권한 의미 오염 + TABLE log destination 우회)
  - **C5** performance_schema digest-first 권유 추가
- Verification: docs only, code 변경 0. py_compile/runtime smoke 불필요. verify-completion PASS 만 확인.
- Risks: ADR 자체는 future trigger 조건만 명시 — 현재 운영 영향 0. 외부 SaaS/multi-tenant 진입 시점에 별 cycle (Major §12.3) 재진입 명시 (트리거 조건 4 선행).
- Trace: REQ-20260520-0003 → TASK-0088 → CHG-20260520-0007 → REV-20260520-0007.

## CHG-20260520-0006
- Date: 2026-05-20
- Summary: TASK-0091 (REQ-20260520-0006, ~~Minor~~→**Major** §12.3 — PATCH admin/products audit before-state full snapshot + audit integrity fix). Codex outside voice review 5 critical findings + 2 minimum-fix 흡수 — Minor 등급 추정이 audit integrity 결함 (autocommit=True default) 노출 → scope 확장.
- Files:
  - `unit/feature-0003-agent-web-ui/src/app.py`:
    - 신규 helper `_audit_product_snapshot(conn, product_id)` (~line 2127): single-row WebProducts snapshot + `SELECT ... FOR UPDATE` + `system_prompt_summary = {present, content_len, updated_at}` (SECURITY §9.2 정합 — content 본문 제외). `databases` 제외 (Codex C3 — 별 endpoint audit).
    - `admin_update_product()` 갱신 (line 8328~): `conn.autocommit=False` + before snapshot + UPDATE + `default_cleared_product_ids` 캡처 + after snapshot + audit + commit + `finally autocommit=True` (Codex C2 audit integrity fix).
    - `_AUDIT_BUILDER_PRODUCT_FIELDS` 확장 (line 8862): 7→8 field. `+is_default`, `+sort_order`, `+system_prompt_summary` / `-databases`, `-system_prompt` (Codex C1+C4).
    - builder branch `admin.product.update` (line 8966~): `default_cleared_product_ids` 키 명시 처리 (Codex C4 side effect).
  - `unit/feature-0003-agent-web-ui/docs/TASK.md` §2.5 본 plan + TASK-0091 [x]
  - `unit/feature-0003-agent-web-ui/docs/REVIEW.md` REV-20260520-0006
  - `unit/feature-0003-agent-web-ui/docs/REPORT.md` §1 Summary
  - `unit/feature-0003-agent-web-ui/docs/TEST.md` §4 sentinel + delta smoke 결과
  - `unit/feature-0003-agent-web-ui/docs/FUNCTION.md` AC-0192
- Codex outside voice 5 findings 흡수:
  - **C1**: `system_prompt.content` full drop → `system_prompt_summary` only (SECURITY §9.2)
  - **C2**: autocommit/transaction integrity fix (audit 실패 시 UPDATE rollback 가능)
  - **C3**: single-row `SELECT FOR UPDATE` + databases 제외
  - **C4**: allowlist 확장 (`is_default`, `sort_order`) + `default_cleared_product_ids` side effect
  - **C5**: C1 ACCEPT 로 자동 해소 (full content drop)
- Verification (Phase C sentinel smoke):
  - py_compile PASS
  - `'TASK-0091-SENTINEL' in body: False` ✓ (system_prompt full drop)
  - `'should_not_leak' in body: False` ✓ (databases drop)
  - sort_order 100→50 / is_default False→True / `default_cleared_product_ids: [5,9]` / `system_prompt_summary` 정합 ✓
- Risks: scope ~~Minor~~→Major (audit integrity fix 포함). 사용자 영향 0 (audit row 정확성). DB schema 변경 0. PATCH admin/products endpoint behavior: 외부 contract 동일, internal transaction semantics 만 변경.
- Trace: REQ-20260520-0006 → TASK-0091 → CHG-20260520-0006 → REV-20260520-0006.

## CHG-20260520-0005
- Date: 2026-05-20
- Summary: TASK-0086 (REQ-20260520-0001, **Major** §12.3 — `WebAccountActivity` legacy table DROP + dual write 종료). TASK-0073 Phase A2 의 dual source 일시 공존을 단일 source-of-truth (WebAuditEvents) 로 전환. Codex outside voice review 5 findings + 2 minimum-fix 흡수 후 v2 redesign 적용. backup + scratch restore rehearsal + 1:1 정합 (74=74) + 사용자 명시 ack 후 진행.
- Files:
  - `unit/feature-0003-agent-web-ui/src/app.py`:
    - `_log_search_activity()`: legacy `INSERT INTO WebAccountActivity` 블록 제거. dispatcher (`record_audit_event` → WebAuditEvents) 만 primary path. signature transparent 보존. docstring 갱신.
    - `_ensure_web_account_activity_schema()`: 함수 정의 + 호출 2 사이트 명시 제거 (Codex C1 — helper Option B 채택).
    - `_migrate_web_account_activity_to_audit()`: 함수 본체 + `SHOW TABLES LIKE` table-absent skip 보존. docstring 갱신 (TASK-0086 rollback 1~2 cycle window 명시).
  - `unit/feature-0003-agent-web-ui/tests/test_audit_migration.py`: 모듈 docstring 갱신 (3→2 시나리오) + `m3_log_search_activity_dual_write()` 제거 + main() M3 호출 제거 (Codex C2 minimum-fix).
  - `docs/SECURITY.md` §9.8: "별 cycle DROP" → "DROP 완료 (2026-05-20)" + 8 step 절차 + backup file + rollback 2 시나리오 cross-reference.
  - `unit/feature-0003-agent-web-ui/docs/TASK.md` §2.4 Implementation Plan (TASK-0086) 신설 + TASK-0086 [x] 마킹.
  - `unit/feature-0003-agent-web-ui/docs/REVIEW.md` REV-20260520-0005 entry 추가.
  - `unit/feature-0003-agent-web-ui/docs/REPORT.md` §1 Summary 갱신.
  - `unit/feature-0003-agent-web-ui/docs/TEST.md` §4 본 cycle 결과 prepend.
- DB: `DROP TABLE IF EXISTS WebAccountActivity` 실행. `SHOW TABLES` = 0 ✓. WebAuditEvents `conversation.search.body` row 74 변동 없음 ✓.
- Backup: `artifacts/mysql-backup/WebAccountActivity-20260520T074927Z.sql` (11,950 bytes, 74 row, digest `a09e7898d1ce88711f7a850ab5fbcc91`, file md5 `f4163df9dc1b7ac81ae4c463a0f35e98`). mysqldump 8 옵션 + scratch restore rehearsal PASS.
- v2 redesign (Codex 5 findings 흡수): C1 Option A 불가능 → helper Option B / C2 dispatcher-only 검증 → lightweight smoke + M3 제거 / C3 "single tx" → "single statement" / C4 backup 검증 강화 / C5 rollback 2 시나리오.
- Verification: Phase A~G 모두 PASS (backup integrity / 1:1 정합 / py_compile / import smoke / DROP 정합 / SHOW TABLES = 0 / mirror 보존).
- Risks: rollback window 1~2 cycle 동안 migration helper 보존. dispatcher-only 후 mirror failure = audit 누락 risk → lightweight smoke mitigated. function rename 별 cycle.
- Trace: REQ-20260520-0001 → TASK-0086 → CHG-20260520-0005 → REV-20260520-0005. TASK-0073 Phase A2 dual write 종료.

## CHG-20260520-0004
- Date: 2026-05-20
- Summary: TASK-0092 (REQ-20260520-0007, **Minor** §12.3 — `AGENT_AUDIT_ENABLED=0` + `AGENT_MODE=prod` startup fail-closed 7 vector matrix 검증). TASK-0073 Phase E 의 사용자 위임 항목 1 건 해소 (sandbox SSH 인증 차단 환경 해소 + docker/compose 가용 확인). Codex outside voice review 5 findings + 2 minimum-fix 흡수 후 v2 redesign 적용. Code 변경 0, docs append only.
- Files:
  - `unit/feature-0003-agent-web-ui/docs/TEST.md` — **§4** Test Run History 에 본 cycle 7 vector 결과 prepend (Codex C5 흡수 — §3 = Test Cases, §4 = Test Run History).
  - `unit/feature-0003-agent-web-ui/docs/TASK.md` — §2.3 Implementation Plan (TASK-0092) 신설 (PLAN-APPROVED by ms.mckim.gpt@gmail.com on 2026-05-20). TASK-0092 [ ]→[x] 마킹.
  - `unit/feature-0003-agent-web-ui/docs/REVIEW.md` — REV-20260520-0004 entry 추가 (head prepend, outside voice 5 findings + 2 minimum-fix 흡수 이력).
  - `unit/feature-0003-agent-web-ui/docs/REPORT.md` — §1 Summary 갱신 + 1.archived TASK-0093 Summary 보존.
- v2 redesign (Codex 5 findings 흡수):
  - **C1** 테스트 명령 오류: Dockerfile 이 web UI 를 `/app/web/` 에 복사 → `--entrypoint python` + `import web.app` 으로 정정. uvicorn entrypoint 우회 명확화.
  - **C2** compose 오염 위험: `docker run` 직접 호출 (compose 우회). `--no-deps` 동등 효과 — mysql 기동 + .env + shared volume + 다른 worktree compose project 모두 회피.
  - **C3** flag parsing 계약: V6 추가 (`AGENT_AUDIT_ENABLED=true` + prod → exit 1). strict-string-equality (`os.getenv(...).strip() == "1"`) 계약 명시화. 운영자가 `"true"` / `"yes"` / `"01"` 명시 시 fail-closed — SECURITY.md §8 계약 명시 별 cycle 후속 권고.
  - **C4** stderr 검증 강화: prefix-only 약함, full byte-equal strict 회피. 3 substring (`[FATAL] AUDIT REQUIRED IN PROD` + `set AGENT_AUDIT_ENABLED=1` + `TASK-0073 Phase A1`) 모두 포함 + `Traceback` / `ModuleNotFoundError` 부재 검증.
  - **C5** docs append 위치: TEST.md §3 → §4 (Test Run History) 정정.
- Verification (Phase A~B):
  - (Phase A0) `repo-web:latest` image 가용 확인 (435MB). `.env` 부재 — inline `-e` 만 사용.
  - (Phase A) 7 vector live spawn 실행 (`docker run --rm --entrypoint python repo-web:latest -c "import web.app"`).
  - (Phase B) **7 vector PASS (7/7)**:
    - V1 (audit=0 + mode=prod) → rc=1 + `[FATAL] ... AGENT_MODE=prod ...`
    - V2 (audit=0 + mode=unset) → rc=1 + `[FATAL] ... AGENT_MODE=(unset → prod) ...`
    - V3 (audit=0 + mode=staging) → rc=1 + `[FATAL] ... AGENT_MODE=staging ...`
    - V4 (audit=0 + mode=dev) → rc=0 + `IMPORTED OK`
    - V5 (audit=1 + mode=prod) → rc=0 + `IMPORTED OK`
    - V6 (audit=true + mode=prod) → rc=1 + `[FATAL] ... AGENT_MODE=prod ...` (Codex C3 strict-string-equality 계약)
    - V7 (모두 unset) → rc=0 + `IMPORTED OK`
- Risks: V6 가 운영자 trap (`AGENT_AUDIT_ENABLED="true"` 가 fail-closed) 노출 — SECURITY.md §8 의 strict-string-equality 계약 명시 필요 (별 cycle 후속). audit prod gate 자체는 정합 — 본 cycle scope 외.
- Trace: REQ-20260520-0007 → TASK-0092 → CHG-20260520-0004 → REV-20260520-0004.

## CHG-20260520-0003
- Date: 2026-05-20
- Summary: TASK-0093 (REQ-20260520-0008, **Minor** §12.3 — `bin/verify-completion.sh check_12` audit endpoint routing 정적 검사 신설). TASK-0073 Phase E hotfix (CHG-20260520-0001) 의 routing 회귀 fragility 보강. Codex outside voice review 5 findings + 2 minimum-fix 흡수 후 v2 redesign 적용.
- Files:
  - `bin/verify-completion.sh` — `check_12_audit_endpoint_routing()` 함수 신설 (line ~936-955) + `_check_audit_routing_order()` pure helper split (line ~957-1010). `main()` 의 line 1123 에 호출 추가. footer line 1126·1129 의 "9 checks" → "10 checks: 7 pilot + worktree binding + repo immutability + audit endpoint routing". META mode footer (line 1084·1091·1094) 는 그대로 — check_12 는 feature-specific 라 META mode 에서 의도적으로 skip.
  - `unit/feature-0003-agent-web-ui/docs/TASK.md` — §2.2 Implementation Plan (TASK-0093) 신설 (PLAN-APPROVED by ms.mckim.gpt@gmail.com on 2026-05-20). TASK-0093 [ ]→[x] 마킹.
  - `unit/feature-0003-agent-web-ui/docs/REVIEW.md` — REV-20260520-0003 entry 추가 (head prepend, outside voice 흡수 이력 + 5 findings 표).
  - `unit/feature-0003-agent-web-ui/docs/REPORT.md` — Phase A~F 변경 요약 + git 동기화 결과.
  - `unit/feature-0003-agent-web-ui/docs/TEST.md` — TEST 케이스 정의 (positive 1 + negative 5 fixture + SKIP 5 other-feature + 1 missing-app structural FAIL).
- check_12 spec (v2, Codex outside voice 5 findings 흡수):
  - feature_id != "feature-0003-agent-web-ui" 만 SKIP (silent return 0). 그 외 분기는 모두 FAIL — APIRouter 분리·prefix 변경·route 삭제가 silent pass 되는 v1 의 회귀 방지 게이트 의도 모순 (Codex C1) 차단.
  - 정적 GET sibling list 는 inline 4-path hardcoded 가 아니라 auto-discovery (`@app.get("/api/admin/audits/<non-{>")` 패턴 grep). new static GET 추가 시 자동 catch (Codex C4).
  - `/purge` (POST) 는 method-aware 라 GET `/{event_id}` 와 collision 위험 0. auto-discovery 패턴이 `@app.get(...)` 만 매치하여 자연 제외. hint 정확화 (Codex C3).
  - helper split (`_check_audit_routing_order(app_path)`) — Phase C fixture 테스트 진입점. production app.py 외에도 임의 fixture 파일로 호출 가능 (Codex C5).
  - `set -euo pipefail` 환경의 grep no-match (exit 1) 시 `|| true` fallback 처리 — log_check 호출 보장 (in-cycle fix during Phase C debug).
  - FAIL hint 4 종: (1) "audit routes not found in expected '@app.get("/api/admin/audits/...")' form" — structural refactor, (2) "static audit GET sibling(s) detected but '/{event_id}' detail endpoint missing" — route removal, (3) "'/{event_id}' detail endpoint detected but no static GET siblings" — layout 변화, (4) "'/api/admin/audits/{event_id}' (line N) precedes static GET sibling 'X' (line M). FastAPI/starlette linear match would route 'X' to '{event_id}' (422 int_parsing). Move '{event_id}' definition after all static GET siblings" — ordering 위반.
- Verification:
  - (Phase A) `bash -n bin/verify-completion.sh` PASS — syntax 정합.
  - (Phase B) production positive: `_check_audit_routing_order` wrapper 호출 → `CHECK#12 PASS audit endpoint routing order` (production app.py line 9522 max-static < line 9732 detail).
  - (Phase C) 5 fixture negative: valid.py PASS / wrong_order.py FAIL ordering / no_detail.py FAIL "detail endpoint missing" / no_siblings.py FAIL "no static GET siblings" / refactored.py FAIL "routes not found in expected form".
  - (Phase D) 5 other-feature SKIP: feature-0001 / 0002 / 0004 / 0005 / 0006 호출 → rc=0, no output.
  - (Phase D 추가) target feature + app.py 부재 → FAIL "expected app.py at <path> but file is missing".
- Risks: feature-0003 hardcode 는 의도적 — 일반화는 별 cycle. auto-discovery 패턴이 `@app.get(...)` 만 매치 — `@router.get(...)` / `app.include_router(prefix=...)` 등 APIRouter 패턴 채택 시 structural FAIL "routes not found in expected form" 으로 manual review 강제 (LOUD fail 의도). multi-line decorator / single quote / trailing slash 변형도 동일 — structural FAIL 로 잡힘. 본 cycle scope (Minor) 에서 AST 파서까지 도입 안 함.
- Trace: REQ-20260520-0008 → TASK-0093 → CHG-20260520-0003 → REV-20260520-0003.

## CHG-20260520-0002
- Date: 2026-05-20
- Summary: TASK-0073 후속 cycle backlog (TASK-0086~TASK-0093) list-up. `ai/claude/0086/audit-followup` worktree 의 단일 commit 으로 다음 세션 진입점 (`/_template:entry`) lock-in. 본 backlog 의 각 entry 는 별 cycle (별 PLAN-APPROVED + 별 CHG/REV) 로 분리.
- Files:
  - `unit/feature-0003-agent-web-ui/docs/TASK.md` — §2. Task Queue 의 머리에 "TASK-0073 Audit subsystem followup backlog (2026-05-20)" subsection 신설. 8 entries:
    - TASK-0086 Major §12.3 — WebAccountActivity legacy table DROP + dual write 종료 (data backup + 5 sub-step)
    - TASK-0087 Major §12.3 — 외부 LAN trust 강화 (Caddy trust_forwarded_for + `_get_client_ip` whitelist, feature-0006 위임)
    - TASK-0088 Minor §12.3 — slow_query_log 통합 ADR-0020 결정
    - TASK-0089 Minor §12.3 — 작업 화면 audit drawer UX (`audit.read.own` 본인 view)
    - TASK-0090 Minor §12.3 — CSV streaming export (`StreamingResponse` + generator)
    - TASK-0091 Minor §12.3 — PATCH admin/products audit before-state full snapshot
    - TASK-0092 Minor §12.3 — AGENT_AUDIT_ENABLED=0+prod startup fail-closed 검증 (Phase E 사용자 위임 항목)
    - TASK-0093 Minor §12.3 — verify-completion check_12 audit endpoint routing 정적 검사 (Phase E hotfix fragility 보강)
- Verification: 본 commit 은 docs only — code 변경 없음. 신규 worktree 의 base 는 a060c64 (TASK-0073 Phase E hotfix 머지 후 main HEAD). 다음 세션 진입 시 `cd /root/download/docker/mysql_ai_delegated_dev/.worktrees/0086-audit-followup && /_template:entry <선택한 task> 진행해주세요` 형태로 사용.
- Risks: backlog 8 entries 가 단일 worktree 에 묶임 — 다음 세션이 1 cycle 한정 1 task 만 진행. 다른 task 는 별 worktree (`ai/claude/0087/...` 등) 분기 필요. 또는 본 worktree 안에서 별 branch checkout (§13.2.2 F1 binding 위반 — 허용 안 됨). 다음 세션 작업자가 본 worktree 의 첫 task 선택 후 별 worktree 권장.
- Trace: TASK-0073 후속 → CHG-20260520-0002 → REV-20260520-0002. 본 backlog 는 신규 cycle 들의 staging area.

## CHG-20260520-0001
- Date: 2026-05-20
- Summary: TASK-0073 Phase E hotfix (REQ-20260519-0001, **Critical** §12.3) — `/api/admin/audits/{event_id}` routing 순서 회귀 fix + browser smoke 검증 PASS. main worktree 의 `make web` 재배포 후 audit subsystem 8 endpoint 실 검증 중 발견.
- Files:
  - `repo/unit/feature-0003-agent-web-ui/src/app.py` — `get_audit_event(event_id: int, ...)` endpoint 의 정의 위치를 `export_audit_events_csv` / `list_audit_actors` / `list_audit_resources` / `purge_audit_events` 4 정적 sibling endpoint 뒤로 이동. NOTE comment 추가 — FastAPI/starlette 의 linear match order 가 `/{event_id}` path parameter 로 `export.csv` / `actors` / `resources` 를 잡아 422 int_parsing error. 본 fix 로 detail endpoint 가 정적 path 다음에 매칭.
- Verification: `python3 -m py_compile` PASS. `make web` 재배포 후 browser smoke 검증 PASS:
  - GET /api/admin/audits/{int} → 200 + detail (item.id=128, action=admin.role.create)
  - GET /api/admin/audits/export.csv → 200 + Content-Type=text/csv + Content-Disposition=attachment
  - GET /api/admin/audits/actors → items=[{actor_account_id: 1, username: 'bootstrap_admin'}]
  - GET /api/admin/audits/resources → items=[{resource_type: 'conversation'}, {resource_type: 'role'}]
  - POST /api/admin/audits/purge dry_run → {purged: 0, to_purge: 0, cutoff: '2026-05-01T...', chunk_size: 1000}
  - admin.role.create 호출 → audit row 68→69 (delta=1) + ChangeJson 화이트리스트 정합
  - anonymous share view (cookie 없음) → ActorType='anonymous' + ActorAccountId NULL + token_prefix 8 char (`Wp45TbFK`) + view_count_after=2 + masked_fields=['share.token_full']
  - WebAccountActivity → WebAuditEvents migration 68 row 모두 RequestId=`account-activity:%` marker 정합
- Risks: routing 순서 정합성은 endpoint 추가/삭제 시 fragile — 향후 audit endpoint 확장 시 정적 path 가 `/{event_id}` 보다 위에 위치 보장 필요. NOTE comment 가 가이드.
- Trace: REQ-20260519-0001 → TASK-0073 Phase E hotfix → CHG-20260520-0001 → REV-20260520-0001.

## CHG-20260519-0026
- Date: 2026-05-19
- Summary: TASK-0073 Phase E (REQ-20260519-0001, **Critical** §12.3) — Completion Checklist 마킹 + TASK-0073 [~] → [x] + Phase E checkbox [x] + 외부 영향 (make web + browser smoke + AGENT_AUDIT_ENABLED prod fail-closed manual + WebAccountActivity migration SQL count) 사용자 위임 명시. sandbox SSH 인증 차단으로 본 session 내 컨테이너 재배포 불가.
- Files:
  - `unit/feature-0003-agent-web-ui/docs/TASK.md` — TASK-0073 Task Queue entry `[~]` → `[x]` + Phase E sub-checkbox `[x]` + Completion Checklist §7 의 TASK-0073 sub-entries 추가 (20+ AC, 16 [x] + 3 [ ] 사용자 위임 외부 영향). 8 commit hash 목록 본문 포함.
- Verification: 본 phase 는 docs only — code 변경 없음. `bash bin/verify-completion.sh --pre-commit feature-0003-agent-web-ui` PASS. TASK-0073 의 모든 Phase 가 [x] 마킹 완료, 외부 영향 (사용자 위임) 3 항목은 [ ] 로 명시.
- Risks: 본 cycle 종료 후 사용자가 외부 영향 검증 안 하면 컨테이너 가동 + audit row 실 검증 미수행 — 별 cycle Phase E 의 결과 보고 (`docs/TEST.md §3 Test Run History` append) 권유.
- Trace: REQ-20260519-0001 → TASK-0073 Phase E → CHG-20260519-0026 → REV-20260519-0022.

## CHG-20260519-0025
- Date: 2026-05-19
- Summary: TASK-0073 Phase D (REQ-20260519-0001, **Critical** §12.3) — 프로젝트 수준 docs 일괄 갱신. SECURITY §9 (Audit subsystem 정책 + Sensitive field catalog source-of-truth) + DECISIONS.md ADR-0019 + ARCHITECTURE.md §4·§6 + CONVENTIONS.md §10.6 audit group + STATUS.md feature-0003 row + feature 의 REPORT.md §1 (Phase 별 변경 요약 + git 동기화 결과) + TEST.md §2.1 audit subsystem scope.
- Files:
  - `repo/docs/SECURITY.md` — §9 (Audit subsystem 정책) 신설. §8 가 TASK-0072 cross-account search 점유라 §9 로 분리. 정합성 보존. 하위 §9.1~9.9: 권한 모델 (`audit.*` 4건 + group=audit), Sensitive field catalog (`_AUDIT_BUILDER_*_FIELDS` + `_AUDIT_MASKED_FIELDS_*` source-of-truth), Tx 정책 split (admin Same tx fail-safe / user fail-open), Anonymous ActorType (E4), purge self-audit + idempotency (E8), `AGENT_AUDIT_ENABLED` prod fail-closed (Codex C5), RemoteAddr spoof risk (E3), WebAccountActivity 흡수 (Codex C2), 보관 정책 + 외부 배포 TODO.
  - `repo/docs/DECISIONS.md` — ADR-0019 신설. Context (TASK-0072 의 WebAccountActivity 한정 + CEO review 9 + Codex 14 + Eng review 9 합의) + Decision (Approach B + WebAuditEvents 단일 + dispatcher + builder allowlist + 2 helper + RBAC 4 + AGENT_AUDIT_ENABLED prod gate + chunked purge + 흡수 migration) + Consequences 11 항목.
  - `repo/docs/ARCHITECTURE.md` — §4 (현재 기능 맵) 의 feature-0003 row 에 audit subsystem 명시 + feature-0006 의 `_get_client_ip` X-Forwarded-For trust 정책 참조. §6 (의존성 맵) 에 feature-0003 → feature-0006 의존 (TASK-0073) 추가.
  - `repo/docs/CONVENTIONS.md` — §10.6 화면별 권한 섹션 정렬 정책에 audit group 추가. group 키 list 갱신 (console/account/role/conversation/product/`audit`/misc). 화면별 2단 section 표의 manage 묶음에 audit 합류. label map 의 `audit`="감사" 추가. 두 화면 모두 "관리 권한" 묶음에 audit 등재.
  - `repo/docs/STATUS.md` — feature-0003-agent-web-ui row 갱신 (TASK-0073 신규 entry prepend). 2026-05-19 audit subsystem 도입 일지 entry prepend.
  - `unit/feature-0003-agent-web-ui/docs/REPORT.md` — §1 Summary rewrite. Phase 별 변경 요약 + git 동기화 결과 (§16.5 Step 6) + 남은 위험 / 후속.
  - `unit/feature-0003-agent-web-ui/docs/TEST.md` — §2.1 신설 (Audit subsystem 검증 case 5 분야 — dispatcher unit / RBAC enforcement / migration smoke / AGENT_AUDIT_ENABLED prod fail-closed / admin UI smoke).
- Verification: 본 phase 는 docs only — py_compile / node --check 대상 변경 없음. `bash bin/verify-completion.sh --pre-commit feature-0003-agent-web-ui` PASS. SECURITY.md / DECISIONS.md / CONVENTIONS.md / ARCHITECTURE.md 의 정합성 확인.
- Risks: SECURITY.md §8 (TASK-0072) 와 §9 (TASK-0073) 의 1년/365일 retention 정책이 유사 — 별 cycle 통합 검토. CONVENTIONS.md §10.6 갱신 후 작업 화면의 audit placeholder UX 가 실제 entry point 부재 (admin 콘솔 redirect) — UX 보강 별 cycle.
- Trace: REQ-20260519-0001 → TASK-0073 Phase D → CHG-20260519-0025 → REV-20260519-0021.

## CHG-20260519-0024
- Date: 2026-05-19
- Summary: TASK-0073 Phase C (REQ-20260519-0001, **Critical** §12.3) — Frontend admin 콘솔 "감사 로그" tab 신설 + filter / list / detail / CSV export gated + `PERMISSION_GROUP_ORDER` 'audit' group 추가. CONVENTIONS.md §10.6 정합 — admin section 의 관리 권한 묶음에 audit 그룹 합류. 작업 화면 placeholder.
- Files:
  - `repo/unit/feature-0003-agent-web-ui/src/static/admin.html` — 새 sidebar tab `data-admin-tab="audits"` (#adminTabAudits) + filter row (action / resource_type / actor_account_id / actor_type select / from_at + to_at datetime-local / q + 적용 / 초기화) + list-detail pane (admin-audit-row + admin-audit-detail + admin-audit-detail-fields dl + admin-audit-detail-change pre) + CSV export `<a id="auditExportCsvBtn">` (hide 기본). cache-bust `v=20260518-shell-grid-rows` → `v=20260519-audit-tab` (styles + admin.js).
  - `repo/unit/feature-0003-agent-web-ui/src/static/admin.js` — `PERMISSION_GROUP_ORDER` 에 audit 추가, `PERMISSION_GROUP_LABELS.audit="감사"`. `ADMIN_PERMISSION_SECTIONS.manage.groups` 에 audit 추가. switchTab("audits") 첫 진입 시 loadAuditList() 트리거. adminState.audit state (items / selectedId / nextCursor / scope / loading / initialized / filters). `_auditEscapeHtml` / `_auditFormatDt` / `_readAuditFilters` / `_clearAuditFilters` / `loadAuditList(append)` / `renderAuditList()` / `renderAuditDetail(id)` / `attachAuditFilterHandlers()` 함수 신설. CSV button gate = `audit.export` permission. tab 자체 hide gate = `audit.read.own || audit.read.any`. cursor pagination via "더 불러오기" button + Enter 키 apply.
  - `repo/unit/feature-0003-agent-web-ui/src/static/styles.css` — audit pane styles 10+ class 추가 (`.admin-audit-filter`, `.admin-audit-row` + 변형, `.admin-audit-detail-*`, `.admin-list-scope`, `.admin-audit-pagination`).
  - `repo/unit/feature-0003-agent-web-ui/src/static/app.js` — `PERMISSION_GROUP_ORDER` 에 audit 추가, `PERMISSION_GROUP_LABELS.audit="감사"`. `WORK_SCREEN_PERMISSION_SECTIONS.manage.groups` 에 audit 추가 (작업 화면 placeholder).
  - `repo/unit/feature-0003-agent-web-ui/src/static/index.html` — cache-bust `styles.css?v=20260519-chat-pane-flex` → `v=20260519-audit-tab` + `app.js?v=20260519-pending-entries` → `v=20260519-audit-tab`.
- Verification: `node --check admin.js && node --check app.js` PASS. backend 의 `/api/admin/audits*` 5 endpoint (Phase A4) 호출. ChangeJson 의 `<pre>` 영역은 `_auditEscapeHtml` 로 XSS 차단 (TASK-0058 share.html `<pre>` 패턴 답습). CSV gate / tab visibility gate 가 `adminState.me.permissions[<code>]` truthy 검사.
- Risks: 작업 화면의 audit 그룹 placeholder 가 본인 `audit.read.own` 권한이라도 작업 화면에서 실 audit 진입점 부재 (admin 콘솔로 안내) — Phase E 별도 UX cycle 에서 작업 화면 audit drawer 검토 가능. 시간 정렬 `_auditFormatDt` 가 toLocaleString (browser timezone) — server OccurredAt UTC 와 mismatch 가능, 의도된 UX (사용자 local TZ).
- Trace: REQ-20260519-0001 → TASK-0073 Phase C → CHG-20260519-0024 → REV-20260519-0020. CONVENTIONS.md §10.6 audit group section 배치 lock-in.

## CHG-20260519-0023
- Date: 2026-05-19
- Summary: TASK-0073 Phase B (REQ-20260519-0001, **Critical** §12.3) — 3 test 파일 신설. dispatcher / RBAC / migration 의 핵심 행위 HTTP smoke 검증. 실 실행은 컨테이너 가동 + admin/operator/sales 자격 필요 — Phase E 사용자 위임 (본 cycle 의 plan 본문 명시: "환경 미비 시 test 작성만 + 실행은 Phase E 에 위임").
- Files:
  - `repo/unit/feature-0003-agent-web-ui/tests/test_audit_dispatcher.py` — 신설. 7 시나리오 (D1~D7). HTTP smoke 4 (D1~D4) + static / code review 3 (D5~D7). D7 은 `bin/verify-completion.sh check_11` 의 정적 symbol check 와 동일 grep — 컨테이너 무관 실행 가능.
  - `repo/unit/feature-0003-agent-web-ui/tests/test_audit_rbac.py` — 신설. 10 시나리오 (S1~S10). E1 B 의 핵심 (S3a admin password-reset target user 본인 audit 가시성) + E4 (S9 anonymous share view + S10 actor_type=anonymous filter) + 404 byte-equal metadata leak 차단 (S4) + CSV export (S6) + purge dry_run (S7) + prod fail-closed (S8, manual).
  - `repo/unit/feature-0003-agent-web-ui/tests/test_audit_migration.py` — 신설. 3 시나리오 (M1 legacy → new migration visible / M2 idempotent / M3 dual write coverage). mysql client 직접 사용 — DB_HOST / DB_PORT / DB_USER / DB_PASSWORD / MEMORY_DB env 필수.
- Verification: 3 file 모두 `python3 -m py_compile` PASS. test_search_rbac.py (TASK-0072 Phase B) 와 동일 urllib + login + Set-Cookie 패턴 답습. 컨테이너 가동 후 사용자가 `python3 tests/test_audit_*.py --base-url http://localhost:18080 --admin-user admin --admin-pass <pw>` 로 실행 가능.
- Risks: HTTP smoke 가 컨테이너 환경 의존 — admin/operator/sales 비밀번호 미보유 시 partial PASS. dispatcher 단위 검증이 실제 dispatcher import 직접 호출 X (PYTHONPATH 의존 회피) — `record_audit_event` symbol 부재 시 D7 static check 가 cover. M1 의 legacy INSERT 가 직접 SQL — `make ask` 우회 시 docker exec mysql 또는 host mysql client 필요.
- Trace: REQ-20260519-0001 → TASK-0073 Phase B → CHG-20260519-0023 → REV-20260519-0019.

## CHG-20260519-0022
- Date: 2026-05-19
- Summary: TASK-0073 Phase A6 (REQ-20260519-0001, **Critical** §12.3) — user 5 endpoint fail-open best-effort audit hook + anonymous share view (ActorType='anonymous'). `_audit_user_action` helper 신설 (TASK-0072 `_log_search_activity` 패턴 답습). Eng review E4 — ActorType column 활용 anonymous filter.
- Files:
  - `repo/unit/feature-0003-agent-web-ui/src/app.py`
    - 신규 helper `_audit_user_action(conn, request, account, *, action, resource_type, resource_id, request_ctx, target_account_id, actor_type='account')` — user endpoint fail-open audit. try/except wrap → 실패 시 conn.rollback() + stderr log + main flow 계속. `/api/ask` long-running LLM + share view anonymous flow 전용.
    - POST /api/ask — `conversation.ask` hook (conv_id 결정 직후, LLM 호출 전, ChangeJson `{conversation_id, model, lazy_create, prompt_length}`).
    - POST /api/conversations/{cid}/share — `conversation.share.create` hook (token 발급 직후, token full X — `token_prefix[:8]` 만, scope_mode + anchor_message_id + share_id).
    - DELETE /api/share/{share_id} — `conversation.share.revoke` hook (UPDATE rowcount 직후, already_revoked flag + conversation_id + share_id).
    - GET /api/public/share/{token} — `share.public.view` hook (anonymous! viewer None 이면 ActorType='anonymous' + ActorAccountId NULL, viewer 있으면 'account'). ChangeJson `{share_id, token_prefix[:8], view_count_after, remote_addr}`. Eng review E4 정합.
    - POST /api/public/share/{token}/fork — `share.fork` hook (fork 결과 직후, source_share_id + source_token_prefix + new_conversation_id).
- Verification: `python3 -m py_compile unit/feature-0003-agent-web-ui/src/app.py` PASS. _audit_user_action helper 가 5 endpoint 모두에서 호출. _log_search_activity (Phase A2 mirror) 까지 합쳐 user audit path 전부 wire-up 완료. dispatcher 의 best-effort 실패 시 stderr `[TASK-0073 Phase A6] <action> audit failed: <exc>` log. plan 의 "user 4 endpoint" 는 실제로는 5 endpoint — `/api/conversations` search snippet 가 TASK-0072 `_log_search_activity` 의 자연 wrap (Phase A2 dual write), 본 phase 의 명시 5 endpoint = ask + share create + share revoke + share view (anonymous) + share fork.
- Risks: `share.public.view` 의 `viewer = _optional_account(request, conn)` 는 cookie 없으면 None 반환. ActorType='anonymous' 분기 정합. dispatcher 의 actor_type 화이트리스트 (`account` / `anonymous` / `system`) 검증 — 잘못된 값 → `account` 로 normalize. token_prefix 가 8 char 만 — full token 64 char 의 1/8 노출, PII 침해 면적 최소.
- Trace: REQ-20260519-0001 → TASK-0073 Phase A6 → CHG-20260519-0022 → REV-20260519-0018. Eng review E4 (anonymous ActorType) lock-in + Codex C11 (TASK-0058 share anonymous path 누락) lock-in.

## CHG-20260519-0021
- Date: 2026-05-19
- Summary: TASK-0073 Phase A5 (REQ-20260519-0001, **Critical** §12.3) — admin 11 mutation endpoint Same tx audit hook + ActionCode-specific `build_audit_change_json()` builder dispatch + `_audit_admin_mutation()` helper. Codex outside voice C6 minimum-fix (raw 검증 X, builder allowlist). Eng review E5 (product delete cascade lock 순서) + E6 (explicit dispatcher, decorator 거부).
- Files:
  - `repo/unit/feature-0003-agent-web-ui/src/app.py`
    - 신규 helper `_audit_pick_fields(source, fields)` — 화이트리스트 field 만 extract.
    - 신규 helper `_audit_redact_sensitive(d)` — password_hash / token / api_key 등 sensitive field 값을 `<redacted>` 로 shallow 치환.
    - 신규 `build_audit_change_json(*, action, before, after, request_ctx)` dispatcher — 16 ActionCode (admin 11 + user 5) 의 ChangeJson 화이트리스트 빌더. unknown action 은 ValueError raise (Codex C6 explicit allowlist).
    - 신규 `_audit_admin_mutation(conn, request, actor, *, action, resource_type, resource_id, before, after, request_ctx, target_account_id)` helper — builder dispatch + record_audit_event 호출. caller 가 commit 직전 1 line 으로 호출.
    - 11 admin mutation endpoint 의 Same tx audit hook 적용:
      1. PATCH /api/admin/accounts/{id} — admin.account.update (before=target, after=updated, target_account_id=account_id)
      2. POST /api/admin/accounts/{id}/password-reset — admin.account.password-reset (PasswordHash 명시 redact)
      3. DELETE /api/admin/accounts/{id} — admin.account.delete
      4. POST /api/admin/roles — admin.role.create
      5. PATCH /api/admin/roles/{id} — admin.role.update
      6. DELETE /api/admin/roles/{id} — admin.role.delete
      7. POST /api/admin/products — admin.product.create (autocommit tx 뒤에 별 tx hook)
      8. PATCH /api/admin/products/{id} — admin.product.update
      9. DELETE /api/admin/products/{id} — admin.product.delete (E5 cascade lock 순서 — system_prompts → product_databases → role_permissions → account_permission_overrides → permissions → products → audit)
      10. PUT /api/admin/products/{id}/databases — admin.product.databases.update (before-state schemas 캡처 후 hook)
      11. PUT /api/admin/system-prompts — admin.system_prompt.update (before/after content_len + content_preview_after 120 char, full content 미포함)
- Verification: `python3 -m py_compile unit/feature-0003-agent-web-ui/src/app.py` PASS. record_audit_event 호출 19 회 (= 11 admin endpoint hook + 2 purge self-audit + 1 _log_search_activity mirror + helper 정의 5 etc.). 각 hook 의 try/except 가 audit 실패 시 conn.rollback() 후 500 응답 (Same tx fail-safe). plan 의 "13" 은 elastic 표현 — 11 endpoint 가 admin mutation 전부 (TASK-0073 plan E5 의 cascade lock 순서가 admin.product.delete 1 개 endpoint).
- Risks: PATCH /api/admin/accounts/{id} 의 conn close() 위치가 audit hook 뒤로 이동 — 기존 flow 가 _set_account_overrides + revoke 세션 후 close. audit hook 도 같은 conn 사용. POST /api/admin/products 의 autocommit=False/True toggle 가 audit hook 안 영향 — finally 의 `conn.autocommit = True` 다음에 audit hook 이 추가 INSERT (auto-commit 모드 안전). PUT /api/admin/products/{id}/databases 의 before-state 캡처가 DELETE 직전에 — 추가 SELECT row.
- Trace: REQ-20260519-0001 → TASK-0073 Phase A5 → CHG-20260519-0021 → REV-20260519-0017. Codex C6 (builder allowlist) + Eng review E5 (cascade lock 순서) + E6 (explicit dispatcher) lock-in.

## CHG-20260519-0020
- Date: 2026-05-19
- Summary: TASK-0073 Phase A4 (REQ-20260519-0001, **Critical** §12.3) — 5 audit read endpoint + 1 chunked PK purge endpoint. `.own` SQL filter = `ActorAccountId OR TargetAccountId` (Eng review E1) + 404 byte-equal metadata leak 차단 + CSV 50k hard cap + chunked purge w/ idempotency_key + start/complete self-audit + 30s deadline.
- Files:
  - `repo/unit/feature-0003-agent-web-ui/src/app.py`
    - helper functions 신설 — `_audit_row_to_dict(row)`, `_audit_build_self_filter_sql(account_id)`, `_audit_resolve_read_scope(actor)`, `_audit_parse_filter_params(request)`, `_audit_compose_where(*, scope, account_id, params, cursor_id)`, `_audit_parse_cursor(cursor)`, `_audit_clamped_limit(raw)`. defaults: `_AUDIT_LIST_DEFAULT_LIMIT=100`, `_AUDIT_LIST_MAX_LIMIT=500`, `_AUDIT_PURGE_CHUNK_SIZE=1000`, `_AUDIT_PURGE_MAX_RUNTIME_SEC=30`.
    - `GET /api/admin/audits` — list w/ filter (action_code / resource_type / actor_account_id / actor_type / from_at / to_at / q / cursor / limit). `.own` filter E1 (Actor OR Target). LIMIT N+1 → next_cursor 판정. Response `{items, next_cursor, scope}`.
    - `GET /api/admin/audits/{event_id}` — detail. `.own` 보유자는 본인 actor/target 일 때만, 권한 부족 무조건 404 (byte-equal).
    - `GET /api/admin/audits/export.csv` — `audit.export` gate. hard cap 50k row. `csv` 모듈 + `io.StringIO` + `PlainTextResponse` w/ Content-Disposition.
    - `GET /api/admin/audits/actors` — distinct actor facet. `.own` = 본인 1건만 (enumeration 차단). `.any` = WebAccounts JOIN.
    - `GET /api/admin/audits/resources` — distinct resource_type facet. `.own` 분기 SQL.
    - `POST /api/admin/audits/purge` — chunked PK purge. `audit.purge` gate. dry_run=true → COUNT(*) 만 반환. 실 삭제 — chunk 1000 row 별 tx (LRT 회피). start/complete self-audit 2건. idempotency_key = sha256(cutoff + started_at_minute)[:32]. max runtime 30s (deadline 초과 시 partial — 다음 호출 cursor 재시작).
- Verification: `python3 -m py_compile unit/feature-0003-agent-web-ui/src/app.py` PASS. endpoint 6개 신설 (5 GET + 1 POST). 사용한 helper 모두 file 내 정의. `_build_actor_from_request` (Phase A1) 재사용. `record_audit_event` (Phase A1) purge start/complete 호출.
- Risks: `.own` SQL filter 가 `ActorAccountId IS NULL` row 도 OR 분기로 `TargetAccountId=:self` 매칭 가능 — anonymous share view 시 본인 share 의 viewer 가 본인 audit 에 보이는 경우 (E4 정합, 의도). CSV 50k cap 가 large fleet 에서 모자랄 수 있음 — 본 cycle 의 hard cap, 별 cycle 에서 streaming export 검토. purge max runtime 30s 가 LLM 으로 인한 connection stall 회피 — partial purge 시 다음 호출 cursor 자연 재시작 (cutoff 이전 row 가 남아 있음).
- Trace: REQ-20260519-0001 → TASK-0073 Phase A4 → CHG-20260519-0020 → REV-20260519-0016. Eng review E1 (Actor OR Target self filter) + E8 (chunked purge Python 의사코드).

## CHG-20260519-0019
- Date: 2026-05-19
- Summary: TASK-0073 Phase A3 (REQ-20260519-0001, **Critical** §12.3) — RBAC catalog audit 4건 + permission group `audit` 신규 + admin/operator/sales/dba/pending 5 role 자동 grant catchup. Codex outside voice C8/C9/C10 lock-in (`.own/.any` 정합 + dba seed/catchup 보강 + permission group misc fallback 차단). Eng review E9 — dba 누락 보강.
- Files:
  - `repo/unit/feature-0003-agent-web-ui/src/app.py`
    - `PERMISSION_DEFINITIONS` 끝부분 (system_prompt.manage.role.any 다음) 에 4 entry 추가 — `audit.read.own` (모든 role), `audit.read.any` (admin/dba), `audit.export` (admin/dba), `audit.purge` (admin only). 모두 `group="audit"` (신규 permission group). 기존 ~40 → 44 codes.
    - `SEED_ROLE_DEFINITIONS` pending/operator/sales role `permissions` set 에 `audit.read.own` 명시 추가. admin 은 `set(PERMISSION_CODES)` 라 자동 모두 포함.
    - `_ensure_seed_roles` admin catchup (line ~1486) 의 명시 code list 에 `audit.read.own/.any/.export/.purge` 4 code 추가.
    - operator/sales catchup (line ~1511) 의 `catchup_codes` tuple 에 `audit.read.own` 추가.
    - 신규 dba role catchup loop — `SELECT Id FROM WebRoles WHERE RoleKey='dba' LIMIT 1` 검색 + 존재 시 `audit.read.own/.any/.export` 3 code INSERT IGNORE (.purge 는 admin only). Eng review E9 lock-in.
    - 신규 pending role catchup loop — `audit.read.own` INSERT IGNORE (SEED_ROLE_DEFINITIONS 와 dual safety).
- Verification: `python3 -m py_compile unit/feature-0003-agent-web-ui/src/app.py` PASS. `_ensure_permission_catalog` 가 `_ensure_seed_roles` 앞에서 hydrate 되므로 (TASK-0063 회귀 fix 답습) 신규 4 permission id 가 catchup INSERT 시 valid 보장. frontend admin.js / app.js 의 `PERMISSION_GROUP_ORDER` 갱신은 Phase C scope (본 commit 의 backend 만 RBAC enforce 가능).
- Risks: dba role 이 DB 에 없는 환경은 catchup loop graceful skip. 이미 audit 권한 보유한 admin (e.g. 수동 grant) 은 INSERT IGNORE 라 duplicate 회피. `set(PERMISSION_CODES)` 가 SEED admin 권한을 매 catchup 마다 재계산 → 정적 (module load 시 fixed) 이라 안전.
- Trace: REQ-20260519-0001 → TASK-0073 Phase A3 → CHG-20260519-0019 → REV-20260519-0015. Codex C8/C9/C10 + Eng review E9 lock-in.

## CHG-20260519-0018
- Date: 2026-05-19
- Summary: TASK-0073 Phase A2 (REQ-20260519-0001, **Critical** §12.3) — `WebAccountActivity` (TASK-0072) 기존 row 흡수 + migration helper + `_log_search_activity` dual write wrap. Codex outside voice C2 minimum-fix (legacy table 발견 + transparent wrap). 기존 table 자체는 본 cycle DROP 안 함 (별 cycle backup 후 DROP).
- Files:
  - `repo/unit/feature-0003-agent-web-ui/src/app.py`
    - `_log_search_activity()` 본문 변경 — signature 무변경 (6 keyword args 보존, caller 변경 0). 본문은 dual write: (1) 기존 `WebAccountActivity` INSERT + commit, (2) 새 `record_audit_event(conn, actor={account_id, actor_type:'account'}, action, resource_type='conversation', resource_id=target_owner_id, change_json={query_hash, matched_count, _legacy_source:'WebAccountActivity'}, target_account_id=target_owner_id)` mirror best-effort. 두 source 모두 실패해도 main flow 차단 X.
    - 신규 `_migrate_web_account_activity_to_audit(conn)` helper — 기존 row → WebAuditEvents transform. SQL: `INSERT INTO WebAuditEvents (...) SELECT waa.AccountId, NULL, 'account', waa.TargetOwnerId, NULL, waa.Action, 'conversation', CAST(waa.TargetOwnerId AS CHAR), JSON_OBJECT(...), NULL, NULL, NULL, CONCAT('account-activity:', waa.Id), waa.CreatedAt FROM WebAccountActivity waa WHERE NOT EXISTS (SELECT 1 FROM WebAuditEvents wae WHERE wae.RequestId = CONCAT('account-activity:', waa.Id))`. RequestId marker 로 idempotent. legacy table 부재 시 SHOW TABLES check 후 graceful skip. 성공 시 stderr `migrated N WebAccountActivity row(s) → WebAuditEvents` log.
    - `_ensure_seed_catchup()` 에 `_migrate_web_account_activity_to_audit(conn)` 호출 추가 (Phase A0 `_ensure_web_audit_events_schema` 직후). fast path.
    - `_ensure_web_tables()` slow path 에도 동일 migration 호출 추가 — `WebRoles CREATE TABLE` 직전.
- Verification: `python3 -m py_compile unit/feature-0003-agent-web-ui/src/app.py` PASS. dispatcher (Phase A1) 의 `record_audit_event` 호출이 `_log_search_activity` mirror 에서 첫 실 사용 — INSERT path 의 정상 동작 확인 본 cycle 의 `make web` 재배포 + browser smoke (Phase E) 에서 검증.
- Risks: dual write 시 동일 audit event 가 두 row (legacy + new) — search 통계 / billing 의 double count 위험. 본 cycle 에서 admin UI 는 WebAuditEvents 만 조회 (Phase C) 라 frontend 영향 0. 별 cycle DROP table 시 분리. migration helper 의 `JSON_OBJECT` 가 MySQL 8.0 한정 — repo 의 docker-compose.yml MySQL 8.0 가정 (§15.4) 정합.
- Trace: REQ-20260519-0001 → TASK-0073 Phase A2 → CHG-20260519-0018 → REV-20260519-0014. Codex C2 (WebAccountActivity 발견) 최소 fix.

## CHG-20260519-0017
- Date: 2026-05-19
- Summary: TASK-0073 Phase A1 (REQ-20260519-0001, **Critical** §12.3) — audit dispatcher `record_audit_event()` + `AGENT_AUDIT_ENABLED` prod startup fail-closed gate + verify-completion check_11_audit_dispatcher SPOF guard. CEO review · Codex outside voice C5 minimum-fix · Eng review E6 (explicit dispatcher) / E7 (SPOF mitigation) 흡수.
- Files:
  - `repo/unit/feature-0003-agent-web-ui/src/app.py`
    - 신규 env constants (line 67 직후) — `AGENT_AUDIT_ENABLED` (bool, default 1), `AGENT_MODE` (str, lower-cased), `_AUDIT_IS_PROD_MODE` (bool — AGENT_MODE not in dev/test).
    - 신규 `_enforce_audit_prod_gate()` 함수 + module-load 시점 즉시 호출 — prod (AGENT_MODE != dev/test) 에서 AGENT_AUDIT_ENABLED=1 가 아니면 `sys.exit(1)` + stderr `[FATAL] AUDIT REQUIRED IN PROD — set AGENT_AUDIT_ENABLED=1 (AGENT_MODE=...; TASK-0073 Phase A1)`. Codex C5 — flag bypass surface 차단.
    - 신규 `record_audit_event(conn, *, actor, action, resource_type, resource_id, change_json, masked_fields=None, target_account_id=None)` dispatcher (Phase A0 `_ensure_web_audit_events_schema` 뒤). AGENT_AUDIT_ENABLED=0 (dev/test only) 일 때 silent no-op. actor=None / actor_type='system' 시 ActorAccountId/ActorRoleId NULL 보정 (E4). admin caller = same conn / tx 호출 → 실패 bubble up (caller rollback). user caller = best-effort try/except wrapper → 실패 stderr only. dispatcher 자체는 commit/rollback 안 함 (E6 explicit).
    - 신규 helper `_build_actor_from_request(request, account, *, actor_type='account')` — caller 가 actor dict 조립 시 사용 (remote_addr / user_agent / session_id 자동 캡처).
  - `repo/bin/verify-completion.sh`
    - 신규 `check_11_audit_dispatcher(fdir)` 함수 — feature-0003-agent-web-ui scope 일 때 src/app.py 안 `record_audit_event(`, `AGENT_AUDIT_ENABLED`, `_enforce_audit_prod_gate` 3 symbol 존재 강제. 다른 feature scope 는 silent PASS. Eng review E7 SPOF mitigation.
    - main() 호출 추가 — check_2~9 다음 line 에 `check_11_audit_dispatcher "$fdir"` 호출 + failed counter 반영. PASS / FAIL 메시지 "8 checks" → "9 checks (7 pilot + worktree binding + audit dispatcher)" 로 갱신.
- Verification: `python3 -m py_compile unit/feature-0003-agent-web-ui/src/app.py` PASS. `bash -n bin/verify-completion.sh` PASS. Phase A0 schema 변경 0 — dispatcher 가 기존 `WebAuditEvents` INSERT 패턴 사용. RBAC / endpoint / 데이터 변경 0 (dispatcher 는 caller wire-up 전이라 INSERT row 실측 0). 본 commit 은 인프라 layer 만.
- Risks: module-load time `sys.exit` 가 tests 의 import 차단 가능 → Phase B tests 에서 `AGENT_MODE=test` 환경변수 강제 (test runner 가 환경 set). dispatcher 가 commit/rollback 안 한다는 caller contract 가 강함 — admin endpoint 의 same-tx fail-safe 정합성에 의존, 추후 Phase A5 wire-up 시 transaction boundary 명확 표기.
- Trace: REQ-20260519-0001 → TASK-0073 Phase A1 → CHG-20260519-0017 → REV-20260519-0013. CEO review 9 decision + Codex 14 findings + Eng review E6/E7 lock-in.

## CHG-20260519-0016
- Date: 2026-05-19
- Summary: TASK-0085 (REQ-20260519-0014, Minor §12.3) — lazy-create 사이드바 optimistic pending entry 도입. "+ 새 대화 송신 직후 다른 대화 전환 시 새 대화 entry 가 사이드바에서 잠시 사라지는" UX 회귀 fix + 사용자 의도 "작업 step 현황의 출력 위해" pending entry 클릭으로 컨텍스트 swap 지원.
- Files:
  - `repo/unit/feature-0003-agent-web-ui/src/static/app.js`
    - state 정의 (line 120~127) — `pendingConversationEntries: new Map()` field 추가. Map<sentinel, { sentinel, message, started_at, status }>. status: "in_flight" | "failed". multi-pending 지원 (TASK-0082 unique sentinel 정합).
    - `sendPrompt()` lazy-create 진입 (line 3596~3605) — `state.pendingConversationEntries.set(busyKey, {...})` + `renderConversationList()` 호출 → 사이드바 즉시 표시.
    - `sendPrompt()` success path (line 3685~3687) — closure 일치 여부와 무관하게 본 send 의 sentinel entry 만 `pendingConversationEntries.delete(busyKey)` (실 cid entry 는 `refreshWorkspace` 가 backend list refresh 로 등재 — optimistic 자연 swap).
    - `sendPrompt()` catch path (line 3705~3715) — 본 send 의 entry status="failed" set + `renderConversationList()` + 3 s 후 자동 delete. toast 안내와 함께 양방향 신호.
    - `renderConversationList()` 변경 (line 1209~1450) — `hasPending` 을 `hasDraftPending` (작성 중 placeholder) + `hasInFlightPending` (응답 대기 entries) 둘로 split. empty-state guard 도 둘 다 검사. 신규 `appendInFlightPendingItems()` 가 entries 를 started_at desc 정렬 후 each 표시 (라벨 = prompt 첫 60 자, meta = "응답 대기 중…" / "전송 실패", `is-pending-inflight` / `is-pending-failed` class, 활성 sentinel = `is-active`). failed entry 는 click 비활성, in_flight 는 `_switchToPendingConversationContext(entry)` 클릭 handler. `combinedPrepend` 가 own 그룹의 prepend 로 (1) in-flight entries (상단) + (2) 작성 중 placeholder (하단) 같이 표시.
    - `_switchToPendingConversationContext(entry)` helper 신설 (line 3100~3137) — pending entry 클릭 시 sentinel 컨텍스트로 swap. `stopProgressPolling({reset:false, abort:true})` + `state.activeConversationId=""` + `state.pendingNewConversation=true` + `state.pendingSentinel=entry.sentinel` + `messages=[]` + `pendingBubble` 도 entry metadata 기반 복원 (startedAt 이어짐 → elapsed timer 자연 진행). renderComposer / renderMessages / renderProgress / startElapsedTimer 호출. 응답 도착 시 sendPrompt 의 success path closure 일치 (`state.pendingSentinel === busyKey`) → 자동 `activeConversationId=newCid` + `startProgressPolling`.
  - `repo/unit/feature-0003-agent-web-ui/src/static/index.html` — `app.js?v=20260519-unique-sentinel` → `app.js?v=20260519-pending-entries` cache-bust 토큰 갱신.
- Verification: `node --check app.js` PASS. backend / RBAC / endpoint / audit / DB 무변경. smoke 5 종 (송신 후 전환 / 응답 도착 / catch / click swap / multi-pending).
- Risks: pendingBubble swap 시 step 정보 손실 (cid 전 polling 불가) / closure mismatch 시 cid binding skip / 3 s failed timer / grapheme-safe slice 미적용 / legacy appendPendingItem 보존.
- Trace: REQ-20260519-0014 → TASK-0085 → CHG-20260519-0016 → REV-20260519-0012. TASK-0048 lazy-create + TASK-0082 unique sentinel 의 자연 연속.

## CHG-20260519-0015
- Date: 2026-05-19
- Summary: TASK-0084 (REQ-20260519-0013, Minor §12.3) — D2Coding 우선 monospace stack 으로 전역 통일 재시도. 사용자 후속 요청 "D2Coding 폰트를 우선해줄 수 있을까요?" + AskUserQuestion 으로 적용 범위 확인 (본문 + 코드 모두). CHG-0014 의 한글 친화 sans-serif stack 을 폐기하고, CHG-0013 의 monospace 통일 의도를 D2Coding (한글 monospace 가독성 검증된 NAVER 폰트) 우선으로 부활. `--font` 와 `--mono` 두 토큰을 다시 동일 D2Coding 우선 monospace stack 으로 통합. 사용자가 D2Coding 미설치 환경에서 fallback chain 의 Cascadia Code / SFMono-Regular / Consolas / Noto Sans Mono CJK KR / system monospace 로 자동 fallback.
- Files:
  - `repo/unit/feature-0003-agent-web-ui/src/static/styles.css`
    - line 33~35 (`:root` Typography 토큰) — CHG-0014 의 sans-serif stack 폐기. 새 stack: `--mono: "D2Coding", "D2Coding ligature", "Cascadia Code", "SFMono-Regular", Consolas, "Noto Sans Mono CJK KR", ui-monospace, Menlo, monospace` + `--font: var(--mono)` 로 통합. body cascade (`font-family: var(--font)` line 65 + `font: inherit` line 72~73) 가 그대로 작동해 작업·관리 화면 전역에 D2Coding 우선 monospace 적용. var(--mono) 명시 사용처 (코드/로그 영역) 도 동일하므로 영향 없음.
  - `repo/unit/feature-0003-agent-web-ui/src/static/admin.html` — line 7 `styles.css?v=20260519-cjk-readable` → `styles.css?v=20260519-d2coding-mono` cache-bust 토큰 갱신.
- Verification:
  - CSS syntax 단순 토큰 교체. JS / Python 변경 없음.
  - cascade 검증: body / button / input / textarea / select 의 기존 font cascade 그대로 작동.
  - smoke (사용자 직접 확인 권장): ①작업 화면 (`/`) 진입 → D2Coding 설치 시 한글·영문 모두 D2Coding 등폭으로 렌더, 미설치 시 Cascadia Code (영문 등폭) + system monospace (한글 fallback). ②관리 화면 (`/admin`) 동일. ③한글 메시지·이름·테이블명에서 글자 폭 정합. ④`var(--mono)` 명시 영역도 동일 stack — 변경 영향 없음.
  - index.html cache-bust 미갱신 (CHG-0014 와 동일 — 사용자 main wt revert 의도 존중). 사용자가 작업 화면 진입 시 Ctrl+Shift+R 권장.
- Risks:
  - **D2Coding 미설치 환경**: 사용자가 D2Coding 폰트를 시스템에 설치하지 않은 경우 첫 fallback `Cascadia Code` (영문) + system monospace (한글) 로 렌더. 영문은 등폭 OK 이나 한글은 system monospace 가 깔려 있어야 등폭. 사용자가 D2Coding 설치 (NAVER 공식 https://github.com/naver/d2codingfont) 후 재확인 권장.
  - **D2Coding 가독성 보고 가능성**: CHG-0014 에서 사용자가 monospace 가독성 호소했었음. D2Coding 은 한글 monospace 중 가독성 가장 좋은 평가지만 일반 본문 sans-serif 보다는 가독성 trade-off 있음. 사용자가 본 stack 검증 후 추가 조정 요청 시 별 cycle (예: 본문은 sans-serif + var(--mono) 사용처만 D2Coding 으로 분리).
  - **D2Coding ligature 변형**: stack 두 번째 entry `D2Coding ligature` 는 D2Coding 의 ligature 지원 변형 — `==`, `=>`, `->` 같은 합자 표시. 시스템에 설치 시 자동 적용. 미설치 시 무영향.
  - **CHG-0013 + CHG-0014 + CHG-0015 trace**: append-only 정책 (§5.2). 3 차례의 monospace ↔ sans-serif ↔ monospace 진동이 정직하게 기록. CHG-0013 (monospace 시도) → CHG-0014 (sans-serif 환원, 가독성) → CHG-0015 (D2Coding 우선 monospace 부활, 가독성 + 정렬 양립).
  - **share.css 무변경**: 공유 페이지 별도 stylesheet — 영향 없음.
- Trace: REQ-20260519-0013 → TASK-0084 → CHG-0015 → REV-0011. AC-0184 (전역 monospace) + AC-0185 (--mono 사용처 monospace) 모두 본 cycle 에서 단일 stack 통합으로 의미 합쳐짐. AC-0186 (admin.html cache-bust) 갱신. 새 AC-0187 등록 (D2Coding 우선).

## CHG-20260519-0014
- Date: 2026-05-19
- Summary: TASK-0083 followup (REQ-20260519-0012, Minor §12.3) — CHG-0013 의 monospace 통합 방향 폐기 + 한글 가독성 우선 system-ui sans-serif stack 으로 재설정. 사용자 추가 보고: "한글 기준으로 눈이 아픕니다… 한글 기준으로 가장 범용성있는 폰트로 다시 설정해주세요". CHG-0013 의 `--font: var(--mono)` 통합을 해제하고 `--font` 를 OS native 한글 폰트 자동 fallback stack 으로 갱신. `--mono` 는 원래 stack 복원 (코드/로그 영역만 적용). worktree `ai/claude/task-0083` 에서 진행 — 다른 AI 작업자의 a7b7ded commit 의 docs 변경 (CHG-0013/REV-0009 흡수) 과 격리된 src commit.
- Files:
  - `repo/unit/feature-0003-agent-web-ui/src/static/styles.css`
    - line 33~35 (`:root` Typography 토큰) — CHG-0013 의 `--mono` stack (한글 monospace fallback 포함) + `--font: var(--mono)` 통합 해제. 새 stack: `--font: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", "Apple SD Gothic Neo", "Noto Sans KR", "Malgun Gothic", "맑은 고딕", "Helvetica Neue", Arial, sans-serif`. macOS 는 `-apple-system → Apple SD Gothic Neo`, Windows 는 `Segoe UI → 맑은 고딕`, Linux/ChromeOS 는 `system-ui` 또는 Noto Sans CJK 자동 fallback. `--mono` 는 CHG-0013 이전 stack 복원: `"Cascadia Code", "SFMono-Regular", Consolas, monospace`.
    - 다른 `font-family` 출현 위치 무변경 — `var(--mono)` 명시 사용처 (line 1069, 1082, 1186, 1379, 2542) 는 monospace 유지, hardcoded `ui-monospace, ...` (line 2216) 와 `monospace` (line 3846) 도 그대로. `var(--font)` 사용처 (body line 65 등) 만 sans-serif 로 환원.
  - `repo/unit/feature-0003-agent-web-ui/src/static/admin.html` — line 7 `styles.css?v=20260518-shell-grid-rows` → `styles.css?v=20260519-cjk-readable` cache-bust 토큰 갱신.
- Verification:
  - CSS syntax 단순 토큰 교체. JS / Python 변경 없음.
  - cascade 검증: `body { font-family: var(--font); }` (line 65) + `button/input/textarea/select { font: inherit; }` (line 72~73) 가 sans-serif 적용. `var(--mono)` 사용처 (코드/로그 영역) 는 monospace 유지.
  - smoke (사용자 직접 확인 권장): ①작업 화면 (`/`) 메시지 본문 / sidebar / topbar / composer / popover 텍스트가 sans-serif 로 자연스러운 한글 표시. ②관리 화면 (`/admin`) list / detail / form 텍스트가 sans-serif. ③`var(--mono)` 명시 영역 (예: result table, log view, code snippet) 은 여전히 monospace.
  - index.html cache-bust 미갱신 (사용자가 main wt 에서 직접 revert 한 의도 존중) — 사용자가 작업 화면 진입 시 styles.css 가 캐시되어 새 stack 이 즉시 안 보일 수 있음. Ctrl+Shift+R (hard refresh) 권장.
- Risks:
  - **index.html cache-bust 미갱신**: 사용자의 main wt revert 흔적 (system reminder 명시) 을 존중하기 위해 본 cycle 에서 skip. 사용자가 hard refresh 또는 캐시 무시 모드로 접근해야 새 stack 적용 인지. 사용자가 index.html cache-bust 도 갱신 요청 시 별 cycle 1 line.
  - **system-ui 의미 ambiguity**: 일부 구형 브라우저 (특히 모바일 Safari 12 이하) 가 `system-ui` 를 인식 못 함. fallback `-apple-system` / `BlinkMacSystemFont` 로 안전. 본 stack 의 광범위 fallback 으로 실용적 risk 0.
  - **Pretendard 등 별도 한글 모던 폰트 미포함**: 시스템 native 폰트 우선 — Pretendard 같은 비표준 폰트는 stack 에 포함 안 함. 사용자가 Pretendard 우선 요청 시 첫 위치에 추가 또는 WebFont 도입 (별 cycle).
  - **CHG-0013 design intent 회수**: CHG-0013 의 "전역 등폭" intent 가 본 cycle 로 사실상 폐기 — 사용자 feedback 의 가독성 우선. CHG-0013 entry 는 append-only 이므로 그대로 유지하되, 본 entry 가 후속 정정임을 명시.
  - **share.css 무변경**: share.html (공유 페이지) 은 별도 stylesheet 사용 — typography 변경 영향 없음. 별도 cycle 필요 시 추가 작업.
- Trace: REQ-20260519-0012 → TASK-0083 followup → CHG-0013 (monospace, a7b7ded 의 docs / 본 cycle 의 worktree src) → CHG-0014 (sans-serif 환원). AC-0184 (전역 monospace 통일) 의 design intent 는 CHG-0014 로 부분 해제 — "var(--font) 영역은 sans-serif, var(--mono) 영역은 monospace 유지" 로 재정의. 새 AC-0185 등록.

## CHG-20260519-0013
- Date: 2026-05-19
- Summary: TASK-0083 (REQ-20260519-0011, Minor §12.3) — web UI 전역 폰트를 monospace 로 통일. `:root` 의 `--font` 토큰을 `--mono` 와 같은 stack 으로 묶어 작업 화면 / 관리 화면의 모든 text 를 등폭 글꼴로 렌더. 영문은 Cascadia Code / SFMono-Regular / Consolas, 한글은 D2Coding / Noto Sans Mono CJK KR fallback. 사용자 요청 — "문자열 길이와 실제 표현되는 위치가 정합" 을 위한 등폭 정렬 보장.
- Files:
  - `repo/unit/feature-0003-agent-web-ui/src/static/styles.css`
    - line 33~36 (`:root` Typography 토큰 정의) — `--font: "Segoe UI", "Noto Sans KR", -apple-system, BlinkMacSystemFont, sans-serif` 제거 → `--mono` stack 을 한글 monospace fallback 포함으로 확장 (`"Cascadia Code", "SFMono-Regular", Consolas, "D2Coding", "Noto Sans Mono CJK KR", ui-monospace, Menlo, monospace`) + `--font: var(--mono)` 로 참조 통합. 기존 `body { font-family: var(--font); }` (line 65) + `button/input/textarea/select { font: inherit; }` (line 72~73) cascade 가 그대로 작동해 전역 적용.
    - 다른 `font-family` 출현 위치 (line 1069 `var(--mono)`, line 1082 `var(--mono)`, line 1186 `var(--mono)`, line 1379 `var(--mono)`, line 1904 `var(--font-mono, ui-monospace, monospace)` 별도 변수, line 2216 hardcoded `ui-monospace, SFMono-Regular, Menlo, monospace`, line 2542 `var(--mono)`, line 3846 `monospace`, line 4026/4170/4190/4217/4233 `inherit`) 무변경 — 기존이 이미 monospace 또는 inherit 이라 영향 없음.
  - `repo/unit/feature-0003-agent-web-ui/src/static/index.html` — line 7 `styles.css?v=20260519-chat-pane-flex` → `styles.css?v=20260519-mono-font-stack` cache-bust 토큰 갱신.
  - `repo/unit/feature-0003-agent-web-ui/src/static/admin.html` — line 7 `styles.css?v=20260518-shell-grid-rows` → `styles.css?v=20260519-mono-font-stack` cache-bust 토큰 갱신.
- Verification:
  - CSS syntax 단순 토큰 교체. JS / Python AST 변경 없음.
  - `var(--font)` / `var(--mono)` 참조 자리 의미 무손상 — 두 토큰이 동일한 값으로 통합되어 cascade 결과 동일 (등폭) 보장.
  - smoke (사용자 직접 확인 권장): ①작업 화면 (`/`) 진입 → sidebar / topbar / composer / message bubble / popover 의 모든 텍스트가 monospace 로 표시. ②관리 화면 (`/admin`) 진입 → list / detail / bulk toolbar / form 의 모든 텍스트가 monospace 로 표시. ③한글 메시지·이름·테이블명에서 글자 폭 정합 (system 에 D2Coding / Noto Sans Mono CJK KR 가 깔려 있을 때). ④`share.html` (별도 `share.css`) 은 본 변경 영향 없음 — 의도.
- Risks:
  - **한글 monospace 시스템 의존**: 시스템에 D2Coding / Noto Sans Mono CJK KR 가 설치되지 않은 환경 (예: 기본 Windows / macOS 사용자) 은 fallback chain 의 `ui-monospace` 또는 `monospace` 가 system default monospace 를 사용하는데, 일반적으로 한글은 system default proportional font (예: 맑은 고딕 / Apple SD Gothic Neo) 로 표시되어 한글만 등폭이 깨질 수 있음. CSS 단독으로 강제 불가 — system 폰트 설치 안내 또는 WebFont 도입은 별 cycle.
  - **읽기 가독성 trade-off**: monospace 는 한글·영문 혼합 본문에서 가독성이 일반 sans-serif 보다 낮을 수 있음. 사용자가 명시 요청한 "문자열 길이 / 위치 정합" 우선이라 trade-off 수용. 사용자가 추후 일부 영역 (예: navigation, button label) 만 sans-serif 로 환원 요청 시 별 cycle.
  - **`--font` 토큰의 의미 분리 소실**: 기존에 proportional / monospace 두 토큰이 분리되어 있던 design intent 가 사라짐. `var(--font)` 참조 자리에서 향후 다시 proportional 로 돌리려면 단일 line 변경 (line 35 `--font: var(--mono)` → 별도 stack) 으로 회복 가능 — 미래 cycle 옵션 보존.
  - **share.css (share.html 전용) 미변경**: 공유 페이지의 폰트는 본 cycle 범위 외. 사용자가 명시한 "프로젝트로 실행되는 웹브라우저" 가 작업·관리 화면을 가리킨다고 해석. share.html 도 monospace 통일 요청 시 별 cycle 1 line 추가.
- Trace: REQ-20260519-0011 → TASK-0083 → CHG-20260519-0013 → REV-20260519-0009. AC-0184 (전역 monospace 통일) 신규 등록. 기존 AC 회귀 없음 (cascade 동일).

## CHG-20260519-0012
- Date: 2026-05-19
- Summary: TASK-0082 (REQ-20260519-0010, Minor §12.3) — lazy-create unique sentinel design 도입. TASK-0081 followup. 글로벌 단일 sentinel 의 컨텍스트 충돌로 첫 in-flight 중 + 새 대화 클릭 시 input 활성화 안 되던 회귀 근본 fix.
- Files:
  - `repo/unit/feature-0003-agent-web-ui/src/static/app.js`
    - state 정의 (line 115 부근) — `pendingSentinel: null` field 추가. 각 lazy-create 진입의 unique sentinel 보관.
    - 상수 정의 (line 156 부근) — `PENDING_CONV_SENTINEL` 글로벌 별칭 유지 (legacy 호환) + `PENDING_CONV_SENTINEL_PREFIX` 신설 + `_newPendingSentinel()` helper 추가. helper 는 `${prefix}_${Date.now()}_${random 6 char}` 패턴으로 unique id 발급.
    - `isCurrentConvBusy()` (line 333~339) — sentinel 점유 검사를 글로벌 단일 토큰 → `state.pendingSentinel` 점유 여부로 변경. `state.pendingNewConversation && state.pendingSentinel && busyConversations.has(state.pendingSentinel)` AND 조건.
    - `beginPendingConversation()` (line 2993~3015) — TASK-0081 의 stale guard 분기 제거 + 항상 reset 흐름 진입 + `state.pendingSentinel = _newPendingSentinel()` 명시 부여. 첫 in-flight 여부와 무관하게 새 컨텍스트는 별개 sentinel 으로 분리. 기존 stopProgressPolling / activeConversationId reset / renderComposer 호출 chain 무변경.
    - `sendPrompt()` busyKey 결정 (line 3458~3475) — lazy-create 시 `state.pendingSentinel` 을 busyKey 로 capture. pendingSentinel 미할당 (직접 send 진입) fallback 으로 새 sentinel 생성 후 state 에 기록. 직접 send 는 `busyKey = targetConvId` 그대로.
    - `sendPrompt()` success path (line 3522~3539) — `if (state.pendingSentinel === busyKey)` closure check 후에만 `pendingNewConversation = false; activeConversationId = newCid; pendingSentinel = null` cleanup + polling 시작. closure mismatch (사용자가 send 도중 + 새 대화 이동) 시 두 번째 컨텍스트 state 보존 + refreshWorkspace 만 호출 (사이드바 list refresh).
    - `sendPrompt()` catch path (line 3537~3551) — TASK-0081 의 cleanup 도 closure check 추가. `if (state.pendingSentinel === busyKey)` 일 때만 cleanup. pending bubble error 표시 / toast 안내는 closure 무관하게 본 send 발생 사실을 알림.
  - `repo/unit/feature-0003-agent-web-ui/src/static/index.html` — `app.js?v=20260519-pending-recovery` → `app.js?v=20260519-unique-sentinel` cache-bust 토큰 갱신.
- Verification:
  - `node --check repo/unit/feature-0003-agent-web-ui/src/static/app.js` PASS.
  - backend / RBAC / endpoint / audit / DB 무변경 (Python AST 검증 대상 없음).
  - smoke (사용자 직접 확인 권장): 회귀 시나리오 4 종 — ①첫 송신 in-flight 중 "+ 새 대화" 클릭 → 입력칸 활성화 + 두 번째 prompt 작성 + send → 두 응답 모두 정상 (각자 sentinel 분리, sidebar 양 conv 표시). ②catch 분기 종료 후 "+ 새 대화" → 정상 진입 (closure check 로 cleanup OK). ③응답 후 "+ 새 대화" → 정상. ④pending bubble error 표시 → closure check 와 무관하게 표시 (cleanup 은 closure 일치 시에만, bubble UI 는 별도).
- Risks:
  - **closure mismatch 시 첫 대화의 activeConversationId 갱신 skip**: 첫 send 의 success path 가 newCid 를 받아도 closure mismatch (두 번째 컨텍스트 이동) 면 `state.activeConversationId` 를 newCid 로 set 하지 않음. 사용자가 사이드바 conversation list 에서 첫 대화 (이미 발급된 newCid) 를 직접 클릭해서 진입해야 함. `refreshWorkspace(newCid)` 가 list 를 refresh 하므로 첫 대화는 list 에 표시. 의도된 동작이지만 사용자 인지 필요.
  - **closure mismatch 시 polling 시작 skip**: 첫 send 의 응답 도착 시 closure mismatch 면 `startProgressPolling` 호출 안 함. 첫 대화의 backend status="processing" 인 비동기 흐름은 사용자가 첫 대화로 진입 후 `loadHistory` → `startProgressPolling` (line 2895~2899 의 last_status=processing 경로) 가 다시 시작. 일관성 OK.
  - **pendingSentinel race**: 동일 ms 안에 두 진입 시 random suffix (`Math.random().toString(36).slice(2, 8)`) 로 16^6 = ~16M 가지 분리. 실용적 충돌 위험 0.
  - **legacy PENDING_CONV_SENTINEL reference**: 본 fix 후 글로벌 단일 토큰 검사는 모두 `state.pendingSentinel` 검사로 변경됨. `PENDING_CONV_SENTINEL` 상수는 외부 reference 없으나 호환 차원에서 유지 (별 cycle 에서 cleanup 가능).
- Trace: REQ-20260519-0010 → TASK-0082 → CHG-20260519-0012 → REV-20260519-0008. TASK-0081 의 stale 가드 + catch cleanup 정책 본 design 으로 자연 흡수. AC-0072 / AC-0075~0077 / AC-0176~0178 (TASK-0081) 회귀 보호.

## CHG-20260519-0011
- Date: 2026-05-19
- Summary: TASK-0081 (REQ-20260519-0009, Minor §12.3) — `beginPendingConversation()` stale flag 회복 가드 + `sendPrompt()` catch 분기 `pendingNewConversation` cleanup. 두 번째 새 대화 send (요청 버튼 / Ctrl+Enter) 가 무동작이던 회귀 fix.
- Files:
  - `repo/unit/feature-0003-agent-web-ui/src/static/app.js`
    - line 2993~2997 (`beginPendingConversation()` 의 early-return guard) — `state.pendingNewConversation` 단독 검사 → `state.pendingNewConversation && state.busyConversations.has(PENDING_CONV_SENTINEL)` 로 좁힘. 첫 lazy-create send 가 실제 in-flight (sentinel 점유) 일 때만 진입 보류. stale state (catch 분기 후 cleanup 누락 등) 는 통과해 정상 reset 흐름으로 진입.
    - line 3536~3537 (`sendPrompt()` 의 lazy-create catch 분기 진입 직후) — `state.pendingNewConversation = false` 명시 cleanup 1 줄 추가. pending bubble 의 error 표시 / toast 안내 로직은 무변경. busyConversations sentinel cleanup 은 기존 finally 블록의 `state.busyConversations.delete(busyKey)` 가 담당 (변경 없음).
  - `repo/unit/feature-0003-agent-web-ui/src/static/index.html` — `app.js?v=20260519-chat-pane-flex` → `app.js?v=20260519-pending-recovery` cache-bust 토큰 갱신.
- Verification:
  - `node --check repo/unit/feature-0003-agent-web-ui/src/static/app.js` PASS.
  - backend / RBAC / endpoint / audit / DB 무변경 (Python AST 검증 대상 변경 없음).
  - smoke (사용자 직접 확인 권장): ①새 대화 만들기 + 메시지 송신 + 정상 응답 후 다시 "+ 새 대화" 클릭 + 두 번째 메시지 send → 정상 진행. ②새 대화 만들기 + 메시지 송신 + (네트워크 차단 시뮬레이션 또는 backend timeout) catch 진입 후 "+ 새 대화" 클릭 + 두 번째 메시지 send → 정상 진행. ③첫 송신 in-flight 상태 (응답 도착 전) 에서 "+ 새 대화" 클릭 → 입력란 포커스만 유지 (의도적 — sentinel race 방지).
- Risks:
  - **lazy-create in-flight 중 "+ 새 대화" 클릭 보류 유지**: 사용자가 첫 송신 응답을 기다리는 중에 두 번째 대화로 전환을 시도하면 여전히 포커스만 잡고 진입 보류. 이는 sentinel 중복 race 방지를 위한 의도된 동작. UX 측면에서 사용자 안내 toast 추가 여부는 별 cycle 검토 가능.
  - **catch 분기 cleanup 이 pending bubble error 표시와 독립**: `state.pendingNewConversation = false` 직후에도 `state.pendingBubble` 의 error 영역은 그대로 표시되어 사용자가 직전 실패 컨텍스트를 확인 가능. 다만 사용자가 즉시 "+ 새 대화" 로 이동하면 pending bubble 도 새 흐름에 의해 정리될 수 있음 — AC-0077 의 빨간 오류 표시 안내 의도와 약간 trade-off.
  - **다른 entry point**: `beginPendingConversation()` 외에 `state.pendingNewConversation` 을 set 하는 코드 경로 미발견. line 3001 (본 함수 내부) + line 3524 의 success cleanup + line 3537 신규 catch cleanup 3 군데로 명확.
- Trace: REQ-20260519-0009 → TASK-0081 → CHG-20260519-0011 → REV-20260519-0007 (lazy-create state machine, AC-0072/0075/0076/0077 의 회귀 차단)

## CHG-20260519-0010
- Date: 2026-05-19
- Summary: TASK-0080 (REQ-20260519-0008, Minor §12.3) — `_collect_matched_excerpts` 의 SELECT 를 `AgentMemoryMessages` + `AgentCoreMessages` UNION ALL 로 확장. TASK-0077 followup. core-only conv 의 snippet 부재 회귀 차단.
- Files:
  - `repo/unit/feature-0003-agent-web-ui/src/app.py` — `_collect_matched_excerpts` 의 inner SELECT 가 두 table UNION ALL. 두 sub-SELECT 모두 동일 `conv_ids` IN + LIKE pattern + `COLLATE utf8mb4_unicode_ci` 통일. outer `ROW_NUMBER OVER (PARTITION BY cid ORDER BY msg_id DESC)` 으로 conv 별 더 최근 매칭 1건 선택. 파라미터 binding 은 `(conv_ids, pattern, conv_ids, pattern)` 4 그룹. line-based clip 로직 (LINE_MAX 220 + HALF_WINDOW 60) 무변경.
- Verification:
  - `python3 -m py_compile unit/feature-0003-agent-web-ui/src/app.py` PASS.
  - make web 재배포 OK — repo-web-1 29 초 후 healthy.
  - smoke (사용자 브라우저 직접 확인 권장): core-only conv 에 매칭되는 검색어로 검색 → snippet 영역에 본문 excerpt 노출 확인.
- Risks:
  - **msg_id 의 두 table namespace 차이**: AgentMemoryMessages.Id 와 AgentCoreMessages.id 가 다른 schema. 본 fix 는 더 큰 id = 더 최근 가정 (monotonic 시간 증가) — 본 프로젝트 schema 정합. 동일 시점에 양 table 모두 INSERT 가 일어나는 race 에서는 어느 row 가 "더 최근" 인지 모호하나 sub-second race 라 사용자 시각 영향 0.
  - **collation 통일 cost**: `COLLATE utf8mb4_unicode_ci` 명시로 index 우회 가능 — query 비용 ↑ 가능. 단 본 query 는 `WHERE conv_ids IN (...)` 으로 row scope 가 conv 단위 (검색 결과 LIMIT 50) 라 cost overhead 미미.
  - **AgentCoreMessages content 컬럼이 NULL 인 row**: LIKE 의 NULL 매칭은 false 라 자동 제외 — 안전. 단 NULL content 의 conv 가 list 에 포함되면 excerpt 부재 (frontend snippet skip) — 그대로.
  - **search EXISTS 와 excerpt 의 동기화**: TASK-0072 의 `_list_conversations` search EXISTS subquery 가 두 table 모두 검사하므로 본 fix 와 일치. 향후 EXISTS / excerpt 중 하나만 변경 시 동기화 깨질 위험.
- Trace: REQ-20260519-0008 → TASK-0080 → CHG-20260519-0010 → REV-20260519-0006 (followup of TASK-0077)

## CHG-20260519-0009
- Date: 2026-05-19
- Summary: TASK-0079 (REQ-20260519-0007, Minor §12.3) — `.chat-pane` 의 flex 누락으로 짧은 대화 + 큰 viewport 조합 시 composer 아래 회색 빈 영역 노출되던 layout 결함 차단. TASK-0066 ChatGPT 패턴 layout 재구조화 시점 cascade 잔여 결함 — TASK-0068~0071 chain 이 admin 영역만 다뤘고 작업 화면 chat-pane 은 미적용.
- Files:
  - `repo/unit/feature-0003-agent-web-ui/src/static/styles.css` — `.chat-pane` 에 `flex: 1 1 auto` + `min-height: 0` 추가 (2 line). 다른 속성 (display: flex, flex-direction: column, overflow: hidden, background: var(--bg)) 무변경.
  - `repo/unit/feature-0003-agent-web-ui/src/static/index.html` — cache-bust styles.css + app.js `v=20260519-snippet-line` → `v=20260519-chat-pane-flex` (양쪽 동일).
- Verification:
  - browser smoke 는 사용자 hard refresh 후 직접 확인 권장 (cache-bust `v=20260519-chat-pane-flex`).
  - make web 재배포 OK — repo-web-1 29 초 후 healthy.
  - DOM cascade 정합: `.app-shell { grid-template-rows: minmax(0, 1fr) }` (TASK-0071) → `.chat-column { flex column }` → `.chat-pane { flex: 1 1 auto; min-height: 0 }` (본 cycle) → `.messages-wrap { flex: 1; min-height: 0 }` → `.messages { flex: 1; min-height: 0 }`.
- Risks:
  - **다른 viewport 조합 검증**: 본 환경 (사용자 브라우저) 에서 정상 확인 필요. 작은 viewport (height < 600) 에서는 `.messages` 의 `overflow-y: auto` 가 scroll 흡수.
  - **mobile 반응형**: `.app-shell` 의 mobile 분기 (`max-width: 680px`) 는 grid → single column. `.chat-pane` 의 flex chain 은 mobile 에서도 정상 (single column 안에서 grow).
  - **TASK-0073 (다른 session) 과 file overlap 없음**: 본 cycle 의 styles.css `.chat-pane` 변경은 TASK-0073 의 admin / audit / endpoint 영역과 영역 분리.
- Trace: REQ-20260519-0007 → TASK-0079 → CHG-20260519-0009 → REV-20260519-0005 (TASK-0066 cascade 잔여 결함 hotfix)

## CHG-20260519-0008
- Date: 2026-05-19
- Summary: TASK-0078 (REQ-20260519-0006, Minor §12.3) — search modal 3 항목 추가 hotfix of TASK-0077. (1) mouseup race 보강 (mouseup target 추적 추가), (2) preset 텍스트 "부터" 제거, (3) snippet 본문 발췌 line-based clip.
- Files:
  - `repo/unit/feature-0003-agent-web-ui/src/app.py` — `_collect_matched_excerpts` 의 excerpt 추출 로직을 line-based 로 재작성. 매칭 위치의 line 경계 (`text.rfind("\n", 0, idx)` + `text.find("\n", idx)`) 를 찾아 line 전체를 반환. line 이 LINE_MAX (220 char) 초과 시 매칭 위치 ±HALF_WINDOW (60 char) clip + "…" prefix/suffix. 매칭 위치 검색 실패 (escape edge) 시 first line 사용.
  - `repo/unit/feature-0003-agent-web-ui/src/static/index.html` — `#searchDatePresets` 의 5 preset button 텍스트 "...부터" → "..." (5 개 모두). data-preset-hours 데이터 속성 무변경 (1/24/168/720/8760). cache-bust `v=20260519-search-presets` → `v=20260519-snippet-line` (styles.css + app.js 양쪽).
  - `repo/unit/feature-0003-agent-web-ui/src/static/styles.css` — `.search-snippet` 의 `-webkit-line-clamp: 2` → `3` + `line-height: 1.45` + `max-height: 4.6em` 추가. line-based excerpt 의 시각 잘림 완화.
  - `repo/unit/feature-0003-agent-web-ui/src/static/app.js`
    - `state.searchModal` 에 `mouseupOnOverlay: false` 추가.
    - `openSearchModal` reset 에 `mouseupOnOverlay = false` 추가.
    - `_bindSearchModalListeners` 의 overlay handler 패턴 갱신 — `overlay.mousedown` (mousedownOnOverlay 기록) + `overlay.mouseup` (mouseupOnOverlay 기록, **신규**) + `overlay.click` 시 둘 다 true + target === overlay 일 때만 close.
- Verification:
  - `python3 -m py_compile unit/feature-0003-agent-web-ui/src/app.py` PASS.
  - `node --check unit/feature-0003-agent-web-ui/src/static/app.js` PASS.
  - `make web` 재배포 OK — `repo-web-1` 24 초 후 healthy.
- Risks:
  - **line-based excerpt 가 가독 line 보다 짧을 가능성**: 매칭 line 이 1 char 일 수도 있음 (예: 빈 line 직후 매칭 char 만 있는 line). 본 cycle 은 그대로 노출 — 사용자가 더 긴 context 가 필요하면 별 cycle 에서 neighboring line 추가 옵션 도입 권고.
  - **mouseup race 보강**: 양 끝점 모두 overlay 인 의도적 backdrop click 만 close. 사용자 의도 모호 케이스 (예: backdrop 위 mousedown → 곧바로 backdrop 위 mouseup) 는 정상 close — 의도적 backdrop click 으로 인식.
  - **preset 텍스트 변경**: 단순 텍스트 변경. 다른 영향 0.
  - **line-clamp 3 의 시각 영역 ↑**: 결과 row 의 height 가 1 줄 분량 (~21 px) 증가 가능. result list 의 max-height (TASK-0072 의 modal 본체 max-height 72vh) 내에서 노출 — viewport 안 result row 수가 ~1 개 감소할 수 있음. 보통 결과 list 가 길지 않아 영향 미미.
- Trace: REQ-20260519-0006 → TASK-0078 → CHG-20260519-0008 → REV-20260519-0004 (hotfix of TASK-0077)

## CHG-20260519-0007
- Date: 2026-05-19
- Summary: TASK-0077 (REQ-20260519-0005, Minor §12.3) — search modal 5 항목 hotfix bundle of TASK-0072/0076. 사용자 직접 테스트 보고 5 항목 모두 반영 — min char 3→2, 소유자 facet 제거, 기간 preset 5종, mouseup race fix, snippet 본문 excerpt.
- Files:
  - `repo/unit/feature-0003-agent-web-ui/src/app.py` — `_normalize_search_query` raw-len gate 3→2. `_collect_matched_excerpts(conn, conv_ids, q)` helper 신설 (MySQL 8.0 `ROW_NUMBER() OVER (PARTITION BY ConversationId ORDER BY Id DESC)` window function, content 매칭 위치 ±40 char clip + "…" prefix/suffix, AgentMemoryMessages 한정). `/api/conversations` endpoint 응답에 `matched_excerpts: {conv_id: "..."}` 첨부 (body-search 활성 시만, 실패 안전 — snippet 은 best-effort UX).
  - `repo/unit/feature-0003-agent-web-ui/src/static/index.html` — 소유자 facet button + `#searchOwnerPopover` + `#searchOwnerList` DOM 제거. 기간 popover 에 `#searchDatePresets` row 신설 (5 preset button). input placeholder "제목 · 계정명 · 본문 (3자 이상)" → "제목 · 본문 (2자 이상)". cache-bust `v=20260519-search-facets` → `v=20260519-search-presets`.
  - `repo/unit/feature-0003-agent-web-ui/src/static/styles.css` — `.search-modal-popover-presets` + `.search-modal-popover-preset` 토큰 신설 (flex-wrap row, chip 모양).
  - `repo/unit/feature-0003-agent-web-ui/src/static/app.js`
    - `state.searchModal`: `owner_id` / `owner_username` / `product_id` / `ownerAccountsCache` 제거, `matched_excerpts: {}` + `mousedownOnOverlay: false` 추가.
    - 제거: `_loadOwnerAccountsForSearch`, `_openOwnerPopover`. `_closeSearchPopovers` / `_updateSearchFacetChipLabels` 의 owner 분기 제거.
    - `openSearchModal` reset 갱신 (owner 흔적 제거, matched_excerpts + mousedownOnOverlay 초기화).
    - `runSearchQuery`: min 2 char gate, owner_id 쿼리 파라미터 보내지 않음, matched_excerpts state 캐시 (append 모드 merge), 실패 시 reset.
    - `renderSearchModalResults`: empty state 문구 2자 기준, snippet 영역이 topic 대신 `sm.matched_excerpts[item.id]` excerpt + highlight. excerpt 부재 시 snippet skip (제목 매칭만).
    - `_searchHighlight`: min length 3 → 2.
    - `_bindSearchModalListeners`:
      - overlay click + mousedown race fix — `mousedownOnOverlay` flag 추적, click 시 둘 다 overlay 일 때만 close.
      - owner chip handler 제거.
      - facetClear: owner 흔적 reset 제거 + matched_excerpts reset 추가.
      - 기간 preset row click handler 신설 (5 preset 공통 — `data-preset-hours` 읽어 now - hours ~ now 자동 채움 + popover input sync + 적용 + runSearchQuery).
      - popover close mousedown 의 owner 분기 제거 (date 만 검사).
- Verification:
  - `python3 -m py_compile unit/feature-0003-agent-web-ui/src/app.py` PASS.
  - `node --check unit/feature-0003-agent-web-ui/src/static/app.js` PASS.
  - `make web` 재배포 OK — `repo-web-1` 8 초 후 healthy.
  - browser smoke 는 사용자 hard refresh 후 직접 확인 권장 (cache-bust `v=20260519-search-presets`).
- Risks:
  - **min 2 char gate 약화**: 검색 결과 수 증가 가능 + rate limit 빈번 진입 가능 — per-account 10 req/min 정책은 그대로라 DoS 표면 추가 0. raw 2 char 가 한글 grapheme 1 자도 통과 (예: "데") 는 일반적 검색어 패턴.
  - **`_collect_matched_excerpts` MySQL 8.0 dependency**: window function 의존. MySQL 5.7 환경에서는 query 실패 — try/except 로 silent skip + snippet 부재 fallback. STATUS.md 의 MySQL 8.0 명시와 정합.
  - **snippet excerpt PII 표면**: TASK-0072 의 audit/RBAC 정책 그대로. `.any` 한정 + opt-in chip + `WebAccountActivity` audit (현재 `conversation.search.body` action 만 기록 — excerpt 자체는 별 audit action 안 만듦, snippet chip 활성 시점에 이미 query 단위 audit 기록). 새 PII 표면 아님.
  - **소유자 facet 폐기 회귀**: backend `owner_id` 파라미터 호환 유지 — 향후 frontend 재도입 또는 다른 caller 영향 0.
  - **mouseup race fix**: mouseup 이 overlay 안에서 일어나지 않는 경우 click 이벤트도 발생 안 함 (브라우저 표준). 본 fix 는 click 발생 시 mousedown 도 overlay 였는지 검사 — drag-out 후 다시 modal 안으로 돌아와 mouseup 발생하는 edge case 도 안전 (target 이 modal element 라 close 안 됨).
- Trace: REQ-20260519-0005 → TASK-0077 → CHG-20260519-0007 → REV-20260519-0003 (hotfix bundle of TASK-0072/0076)

## CHG-20260519-0006
- Date: 2026-05-19
- Summary: TASK-0076 (REQ-20260519-0004, Minor §12.3) — search modal UX 3 결함 hotfix bundle of TASK-0072. 사용자 직접 테스트 보고: (1) facet click 무동작, (2) 키보드 ↑↓ scroll 미동작, (3) 매칭 message bubble jump 미동작. frontend only — backend / RBAC / audit / endpoint 무변경.
- Files:
  - `repo/unit/feature-0003-agent-web-ui/src/static/index.html` — 제품 facet button DOM 제거 (사용자 결정: 대화 중 product 변경 가능 → 필터 부적합). `#searchOwnerPopover` + `#searchDatePopover` 2 popover element 신설 (overlay 안 fixed 위치). cache-bust styles.css + app.js `v=20260519-modal-contrast` → `v=20260519-search-facets`.
  - `repo/unit/feature-0003-agent-web-ui/src/static/styles.css` — `.search-modal-popover*` 토큰 ~110 줄 신설 (popover 자체 + header + body + popover-item + popover-field date input + footer + apply/clear buttons). `.message.is-search-matched` + `@keyframes search-matched-pulse` (1.6 s box-shadow pulse for matched message bubble jump highlight).
  - `repo/unit/feature-0003-agent-web-ui/src/static/app.js`
    - `state.searchModal` 에 `owner_username`, `ownerAccountsCache`, `pendingJumpQuery`, `pendingJumpConvId` 4 필드 추가.
    - `openSearchModal` 의 reset 보강 (owner_id / date_from / date_to / chip label / popover close).
    - 신규 helpers: `_positionPopoverBelow` / `_closeSearchPopovers` / `_updateSearchFacetChipLabels` / `_loadOwnerAccountsForSearch` (1 회 캐시) / `_openOwnerPopover` (admin accounts list + "전체" + role label) / `_openDatePopover` (`<input type="date">` from/to 동기화) / `_jumpToSearchMatchedMessage` (messageLogEl `.message` textContent lowercase compare → 첫 매칭 row scrollIntoView + `is-search-matched` class 1.8 s).
    - input keydown handler 갱신: ArrowDown / ArrowUp 시 active row 의 `scrollIntoView({block:'nearest'})` 추가. Enter 도 click 과 동일 pending jump 저장.
    - result item click 시 `state.searchModal.pendingJumpQuery = q` + `pendingJumpConvId` 저장 → closeSearchModal → selectConversation.
    - `_bindSearchModalListeners` 끝부분에 owner / date facet click handler + date apply / clear button handler 추가. overlay mousedown 시 popover 외 click 이면 popover 자동 close.
    - `selectConversation` 끝 (loadHistory + renderMessages + product hydration 직후) 에 `_jumpToSearchMatchedMessage()` 호출 추가.
- Verification:
  - `node --check unit/feature-0003-agent-web-ui/src/static/app.js` PASS.
  - `make web` 재배포 OK — `repo-web-1` recreated 26 초 후 healthy.
  - browser smoke 는 사용자 hard refresh 후 직접 확인 권장 (cache-bust `v=20260519-search-facets`).
- Risks:
  - facet popover positioning 은 `position: fixed` + chip getBoundingClientRect 기반 — modal scroll / viewport resize 시 popover anchor drift 가능 (단발 click 후 즉시 적용이므로 보통 무문제. 단 popover 가 viewport 밖이면 right-edge clamp 만 적용 — bottom clamp 추가는 follow-up).
  - matched message jump 의 client-side textContent compare 는 user / assistant 메시지 모두 검사 — content snippet 매칭이 너무 광범위 (예: q="대화" 가 "대화 시작" 안내문에도 매칭) 시 정확도 낮음. backend matched_message_id 응답 도입은 별 cycle 권고.
  - owner_id facet 의 admin accounts cache 가 modal close 후 유지 — admin/operator 의 계정 추가/삭제 가 한 session 안에서 발생하면 stale 가능. 후속 cycle 에서 SSE / invalidate hook 권고.
- Trace: REQ-20260519-0004 → TASK-0076 → CHG-20260519-0006 → REV-20260519-0002 (hotfix bundle of TASK-0072)

## CHG-20260519-0005
- Date: 2026-05-19
- Summary: TASK-0072 + TASK-0074 HTTP smoke test 실행 결과를 `unit/feature-0003-agent-web-ui/docs/TEST.md §4 Test Run History` 에 append. bootstrap_admin 1 토큰만 ad-hoc curl (operator pw 미보유). 6/8 PASS — S2 (any cross-account), S4 (cursor disjoint), S5 (q invalid 400), S6 (rate limit 429), S7 (DDL idempotent), S8 (audit SHA-256). S1/S3 (operator 의존) skip — `_list_conversations` 의 has_any 분기 + endpoint 의 effective_owner_id 강제 overwrite 코드 review 로 검증.
- Files:
  - `repo/unit/feature-0003-agent-web-ui/docs/TEST.md` — §4 Test Run History 에 2026-05-19 entry 추가 (8 sub-result + skip 사유 + UI 가독성 사용자 직접 확인 권장 note).
- Verification: 6/8 시나리오 PASS (S1/S3 operator 의존 skip). 코드 변경 0 — 단순 test 결과 기록.
- Risks: 0 (append-only 문서 갱신).
- Trace: TASK-0072 + TASK-0074 → CHG-20260519-0005 (test execution record only, no spec change)

## CHG-20260519-0004
- Date: 2026-05-19
- Summary: TASK-0074 (REQ-20260519-0002, Minor §12.3) — search modal 색상 가독성 hotfix of TASK-0072. site theme = light (`--bg #f4f4f5` / `--surface #ffffff` / `--text #18181b`) 환경에서 modal 의 미정의 var fallback (dark hardcode `#1f2429`) + site 의 text inherit 검은색 = 어두운 배경 위 검은 텍스트 = 가독성 0 (사용자 screenshot 보고). modal CSS 전체를 site 의 기존 토큰으로 일관 적용.
- Files:
  - `repo/unit/feature-0003-agent-web-ui/src/static/styles.css` — `--search-modal-bg: var(--surface)`, `--search-modal-border: var(--border)`, `--search-highlight-bg: #fde68a`. modal block 의 모든 `var(--text-primary)` → `var(--text)`, `rgba(255,255,255,.04|.03|.05)` → `var(--primary-soft)` / `var(--bg)`, chip aria-pressed bg → `--primary-soft`, owner badge "내" = triple (bg + border + color), snippet bg = `--bg`, snippet-hl color = `--text` + `font-weight: 600`, result-item button reset (background transparent + border 0 + width 100% + text-align left + font-family inherit), backdrop `rgba(15,23,42,0.48)` (modal pop 강조 유지).
  - `repo/unit/feature-0003-agent-web-ui/src/static/index.html` — cache-bust styles.css + app.js `v=20260518-conv-search` → `v=20260519-modal-contrast`.
  - `repo/unit/feature-0003-agent-web-ui/docs/{FUNCTION,TASK,MODIFY,REVIEW,REPORT}.md` + `repo/docs/STATUS.md` — REQ-20260519-0002 / TASK-0074 / CHG-20260519-0004 / REV-20260519-0001 entries.
- Verification:
  - `make web` 재배포 OK — repo-web-1 recreated 12 초만에 healthy.
  - backend / RBAC / endpoint / audit / TASK-0073 의 WebAuditEvents 영역 무변경.
  - python3 / node --check 대상 변경 없음 (CSS + cache-bust only).
- Risks: 매우 낮음 — CSS 토큰 변경만. modal 외 영역 영향 0. TASK-0073 Phase A0 (WebAuditEvents) 와 file overlap 없음 (styles.css + index.html cache-bust vs app.py DDL + docs).
- Trace: REQ-20260519-0002 → TASK-0074 → CHG-20260519-0004 → REV-20260519-0001 (hotfix of TASK-0072)

## CHG-20260519-0003
- Date: 2026-05-19
- Summary: TASK-0073 (REQ-20260519-0001, **Critical** §12.3) — Phase A0: WebAuditEvents DDL + bootstrap helper. plan §2.1 (TASK-0073) 의 Eng review lock-in (E2 schema hybrid + E4 ActorType + E1 TargetAccountId) 의 schema 정의를 코드로 정착. 본 CHG 는 schema 만 — dispatcher (Phase A1), migration (A2), RBAC (A3), endpoints (A4), admin hook (A5), user hook (A6), tests (B), frontend (C), project docs (D) 는 별 phase.
- Files:
  - `repo/unit/feature-0003-agent-web-ui/src/app.py`
    - **신설** `_ensure_web_audit_events_schema(conn)` (line ~2501 직전, `_log_search_activity` 직후, `_ensure_must_change_password_schema` 직전). DDL: `WebAuditEvents` 14 columns (Id BIGINT PK, ActorAccountId/ActorRoleId/TargetAccountId BIGINT NULL, ActorType VARCHAR(16) DEFAULT 'account', SessionId VARCHAR(64), ActionCode VARCHAR(64), ResourceType VARCHAR(32), ResourceId VARCHAR(64), ChangeJson/MaskedFields JSON, RemoteAddr VARCHAR(64), UserAgent VARCHAR(255), RequestId VARCHAR(64), OccurredAt TIMESTAMP(3) DEFAULT CURRENT_TIMESTAMP(3)) + 5 secondary indexes (IX_WAE_Actor / Target / Action / Resource / ActorType). Docstring 에 Eng review E1-E5 결정 근거 명시 (Approach B + Same tx admin / fail-open user + ActorType enum + TargetAccountId self filter).
    - **fast-path hydrate** (`_ensure_seed_catchup` line ~2541): `_ensure_web_audit_events_schema(conn)` 호출 추가 (`_ensure_web_account_activity_schema` 직후). 기존 배포 재기동 시 audit table backfill.
    - **slow-path bootstrap** (`_ensure_web_tables` line ~2748): 동일 helper 호출 추가 (`_ensure_web_account_activity_schema` 직후, `WebRoles` CREATE 직전). 신규 배포 첫 기동 시 audit table 생성.
    - 3 위치 모두 TASK-0072 의 `_ensure_web_account_activity_schema` 패턴 답습.
- Verification:
  - `python3 -m py_compile unit/feature-0003-agent-web-ui/src/app.py` → **PASS** (helper 신설 + 2 hook 추가 syntax 검증).
  - `bash bin/verify-completion.sh --pre-commit feature-0003-agent-web-ui` (commit 직전 gate).
  - 컨테이너 재기동 시 fast-path / slow-path 모두 `WebAuditEvents` DDL 적용 확인은 Phase E (make web 재배포) 에서.
- Risks:
  - **DDL idempotent**: `CREATE TABLE IF NOT EXISTS` — 기존 배포 재기동 시 noop. TASK-0072 패턴 검증됨.
  - **Schema migration 정합**: ActorType `DEFAULT 'account'` 기본값으로 기존 row 가 있어도 NOT NULL 충족 (단 본 phase 는 신규 table, 기존 row 0). Phase A2 의 WebAccountActivity migration 시 ActorType="account" 명시 INSERT.
  - **Index cardinality**: 5 secondary indexes — write 부하 5x. 단 admin 빈도 낮음 + user (대화·SQL·share·anonymous) 도 본질 write 빈도. 365일 retention 후 partitioning 검토 (Phase 2).
  - **schema drift**: 본 cycle 의 다른 Phase 가 schema 변경 시 본 helper 의 DDL 도 update 필요. 단 schema 는 Eng review 에서 fix 됨 — drift 없음.
- Trace: REQ-20260519-0001 → TASK-0073 → §2.1 (TASK-0073) 의 Eng review lock-in E2 + E1 + E4 → Phase A0 → CHG-20260519-0003 → REV-20260519-0001 (CEO + Eng + Phase A0 통합, Phase D)

## CHG-20260519-0002
- Date: 2026-05-19
- Summary: TASK-0073 (REQ-20260519-0001, **Critical** §12.3) — `/plan-eng-review` Eng review lock-in (E1-E9 + 30 test paths + 5 deadlock scenarios). Codex outside voice 의 Additional risk 9 (C7-C14) + 5 deadlock scenarios + 추가 eng items 를 architecture-level 로 lock-in. 사용자 결정 2 항목 (E1 self 정의 = Actor OR Target / E4 anonymous share audit 포함 + ActorType column) + 나머지 7 항목 prose lock-in. 본 CHG 는 plan 본문 update 만, 코드 변경 0. Phase A0 진입 ready 상태.
- Files:
  - `repo/unit/feature-0003-agent-web-ui/docs/TASK.md`
    - §2.1 (TASK-0073) 의 마지막 subsection 으로 "Eng review lock-in (E1-E9)" 추가 — 9 finding 의 architecture-level decision + Phase B 시나리오 확장 8 → 10 + Test infra 보강 + Acceptance criteria + Eng review 결과 요약 명시.
    - 본 추가로 `WebAuditEvents` DDL 14 columns (ActorType + TargetAccountId 추가) + 5 secondary indexes 확정. E8 chunked PK purge Python 의사코드 정착. E1 self filter SQL (`WHERE ActorAccountId = :self OR TargetAccountId = :self`) 확정.
- Verification:
  - 본 CHG 는 plan 본문 update 만이라 py_compile / node --check 적용 대상 없음.
  - `bash bin/verify-completion.sh --pre-commit feature-0003-agent-web-ui` (Phase A0 진입 전 lock-in commit).
- Risks:
  - **E1 B 결정의 부수효과**: admin actor 의 mutation 이 target user audit 에 보임 → admin "감시당함" 인지 가능. 단 정당한 보안 추적, SECURITY.md §8 에 명시.
  - **E4 B 결정의 부수효과**: anonymous share view 도 audit row → write 부하 추가 (대화 share 빈도에 비례). 단 ActorType="anonymous" filter 로 분리 조회 가능.
  - **E8 chunked purge idempotency**: 1 분 내 중복 purge 차단 (`idempotency_key = hash(cutoff, started_at_minute)`). 단 1 분 이후 동일 cutoff 재호출은 허용 — 이미 deleted 된 데이터라 noop 이지만 audit.purge.start row 만 추가 생성. 운영 정책상 acceptable.
  - **E2 Schema 변경 가능성**: ActorType column 추가는 본 CHG 가 plan 본문만 update — 실제 DDL 은 Phase A0. DDL 변경 시 본 lock-in 의 schema 명세 update 필요.
  - **테스트 부하**: 30 test paths 중 Phase B 10 HTTP smoke 가 가장 무거움 (admin/operator/sales/dba 다중 role + cross-account). 실행 시간 ~3분 추정.
- Trace: REQ-20260519-0001 → TASK-0073 → §2.1 Implementation Plan (TASK-0073) + Codex outside voice 14 findings + Eng review 9 lock-in → CHG-20260519-0001 (CEO) → CHG-20260519-0002 (Eng) → REV-20260519-0001 (CEO + Eng 통합, Phase D)

## CHG-20260519-0001
- Date: 2026-05-19
- Summary: TASK-0073 (REQ-20260519-0001, **Critical** §12.3) — 모든 계정 행위 audit 기능 + 관리 콘솔 조회 plan 본문 작성 (plan-approved 단계, 코드 변경 0). CEO review 9 decision (Mode=HOLD SCOPE, Scope=Approach B Balanced, Storage=DB-only, Hook=Web-ui 단일, MySQL log=통합, RBAC=4건 .self/.any, Tx=Same tx, Masking=Hybrid, Flag=AGENT_AUDIT_ENABLED=1) → Codex outside voice 14 findings + 6 minimum-fix dispatch (read-only sandbox, model_reasoning_effort=high) → 9 decision 중 5 reset (Storage·MySQL log·Hook·Tx·Masking 의 5 domain) → Major redesign 사용자 확정. WebAccountActivity (TASK-0072) 흡수 결정 (직전 검토 보고가 놓친 결손, codex finding C2). 본 CHG 는 plan 본문 작성만, Phase A0 부터 별 cycle 시작.
- Files:
  - `repo/unit/feature-0003-agent-web-ui/docs/TASK.md`
    - Task Queue 에 TASK-0073 entry 추가 (in-cycle 결정 9 항목 + 상태 `approved-after-outside-voice` + 사용자 메모리 `feedback_outside_voice_for_rbac` 적용).
    - `<!-- PLAN-APPROVED by ms.mckim.gpt@gmail.com on 2026-05-19 (TASK-0073 Phase A0~F 일괄, Critical 등급 audit 표면 신설 + WebAccountActivity 흡수 + RBAC 4건 .own/.any + Tx split + Allowlist builder + AGENT_AUDIT_ENABLED prod fail-closed) -->` marker.
    - §2.1 Implementation Plan (TASK-0073) section 신설 (§2.1 (TASK-0072) 위에 시간 역순 배치). 본 plan 의 구성: CEO 9 decision 표 + outside voice 종합 결정 표 (Codex 14 findings) + Must-fix 5 + Additional risk 9 (eng review lock-in) + 영향 파일 13 + Phase A0~F 순서 + 위험도 평가 표 10 + 검증 계획 + outside voice 결과 요약.
- Verification:
  - `bash bin/verify-completion.sh --pre-commit feature-0003-agent-web-ui` (Phase A0 진입 전, plan-approved commit).
  - 본 CHG 는 plan 본문 작성만이라 py_compile / node --check / HTTP smoke 적용 대상 없음.
  - 외부 검증: Codex outside voice (`codex exec -s read-only -c 'model_reasoning_effort="high"'`) 14 findings + 6 minimum-fix 도출 → 본 plan 의 redesign 에 모두 흡수.
- Risks:
  - **PII leak (ChangeJson masking)**: Action-specific allowlist builder + SECURITY.md §8 sensitive field catalog (Phase D 작성) + admin UI HTML escape.
  - **RBAC bypass (.own ↔ .any)**: TASK-0058 share read-gate 패턴 + Phase B smoke 8 시나리오 + 404/403 byte-equal.
  - **Tx atomicity (admin Same tx)**: dispatcher SPOF = verify-completion.sh check + 100% test coverage + builder explicit raise on unknown action.
  - **`/api/ask` deadlock**: user endpoint fail-open + TASK-0072 `_log_search_activity` 패턴 답습 + Same tx 제외.
  - **Feature flag bypass**: `AGENT_AUDIT_ENABLED` prod (`AGENT_MODE!=dev/test`) startup fail-closed + dev/test only toggle.
  - **WebAccountActivity 흡수**: migration data 보존 (기존 table drop 별 cycle backup 후) + dual source 일시 공존 → 단일 source 전환.
  - **RBAC hydrate 순서**: TASK-0063 회귀 fix 패턴 답습 (`_ensure_permission_catalog` 가 `_ensure_seed_roles` 앞).
  - **365일 chunked purge**: `ORDER BY Id LIMIT N` cursor 재시작 가능 + idempotency key + `audit.purge` self-audit row.
- Trace: REQ-20260519-0001 → TASK-0073 → §2.1 Implementation Plan (TASK-0073) + Codex outside voice 14 findings + 6 minimum-fix → CHG-20260519-0001 → REV-20260519-0001 (Phase D)

## CHG-20260518-0010
- Date: 2026-05-18
- Summary: TASK-0072 (REQ-20260518-0010, **Critical** §12.3) — 타 계정 대화 검색·필터 + WebAccountActivity audit log 신설. Phase A0~E. outside voice 3 review (security FIX-FIRST, adversarial Blocker + 3 sub-spec, ux NEEDS-TWEAK) 의 4 must-fix + 3 sub-spec + 6 risk 모두 흡수. UI 위치 = Spotlight modal (Cmd/Ctrl+K) + 사용자 변형 ("+ 새 대화" 우측 같은 높이 돋보기 icon). 사용자 in-cycle 결정 5 항목 채택.
- Files:
  - `repo/unit/feature-0003-agent-web-ui/src/app.py`
    - Phase A0: `_ensure_web_account_activity_schema(conn)` + `_log_search_activity(conn, account_id, action, target_owner_id, query, matched_count)` 신설. `WebAccountActivity` 테이블 (`Id, AccountId, Action, TargetOwnerId, QueryHash CHAR(64), MatchedCount, CreatedAt`, 2 index). slow path (`_ensure_web_tables`) + fast path (`_ensure_seed_catchup`) 양쪽에서 idempotent 보장.
    - Phase A1 helpers: `_RATE_LIMIT_BUCKETS` / `_RATE_LIMIT_LOCK` / `_COLLATION_AUDIT_DONE` module global + `_escape_like_for_search(s)` (`!`/`%`/`_` 3 char escape) + `_normalize_search_query(q)` (strip + len 3-200 gate, post-escape 0 literal char 차단) + `_search_rate_limit_check(account_id, max_per_min=10)` (in-process token bucket, 60 s window) + `_audit_message_table_collations(conn)` (process 당 1 회 information_schema 점검) + `_parse_search_cursor(cursor)` (`updated_at|conversation_id` 파싱).
    - Phase A1: `_list_conversations()` 시그니처 확장 (`q`, `owner_id`, `product_id`, `date_from`, `date_to`, `cursor`). 3 sub-spec 적용 — (a) SQL composition order: owner_id WHERE 가 q/owner_id/product_id 보다 항상 먼저 AND, `.own` 사용자 owner_id 는 self 로 SQL 단계에서 강제 overwrite; (b) `hidden_ids` SQL push: Python post-filter 폐기 후 `c.conversation_id NOT IN (...)` 로 이전; (c) Python re-sort 삭제: SQL `ORDER BY c.updated_at DESC, c.conversation_id DESC LIMIT N` 단일화. 본문 search 는 `c.topic` / `topic_kv.Value` / `owner.Username` (.any 한정) / `AgentMemoryMessages.Content` EXISTS subquery / `AgentCoreMessages.content` EXISTS subquery + `LIKE %s ESCAPE '!'`. `WebAccounts.DeletedAt IS NULL` 필터 추가 (cross-account leak 추가 차단 layer). cursor pagination keyset on `(updated_at, conversation_id)` DESC.
    - Phase A2: `/api/conversations` 가 `q`/`owner_id`/`product_id`/`date_from`/`date_to`/`cursor`/`limit` query param 수신. search mode 분기 (search params 가 하나라도 있을 때 활성). body-search 시 `_search_rate_limit_check` 10 req/min 진입 (429), `SET SESSION max_execution_time = 3000` 적용, `_log_search_activity` audit INSERT. 응답: `{items, current=null, next_cursor, matched_count, search_mode=true, has_any}`. q < 3 char 또는 escape-0 → 400. `.own` 사용자 owner_id 는 endpoint 에서도 effective overwrite 로 byte-equal response 보장.
  - `repo/unit/feature-0003-agent-web-ui/src/static/index.html`
    - `.sidebar-head` 의 "+ 새 대화" 버튼 우측에 같은 높이 `#openSearchBtn` (돋보기 SVG icon + aria-label="대화 검색 (Ctrl+K)") 추가. `+ 새 대화` 는 `flex: 1`, 검색 버튼은 `flex: 0 0 auto` (30×30).
    - body 끝 직전에 `#searchModalOverlay` (role="dialog" aria-modal="true") + `#searchModal` (header + input row + facets row + result list + footer). facets: `#searchFacetOwner` (.any 한정 hidden 토글) / `#searchFacetProduct` / `#searchFacetDate` / `#searchFacetSnippet` (.any 한정 hidden, aria-pressed) / `#searchFacetClear`.
    - cache-bust `v=20260518-shell-grid-rows` → `v=20260518-conv-search`.
  - `repo/unit/feature-0003-agent-web-ui/src/static/styles.css`
    - `.sidebar-head` flex-direction column → row (gap 6 px, align-items: center). `.btn-new-conv { flex: 1 1 auto }` + `.btn-search-conv { flex: 0 0 auto; width/height: 30px }` + hover/focus-visible 상태.
    - 신규 search modal 토큰 ~200 줄: `--search-highlight-bg` / `--search-modal-bg` / `--search-modal-border` root var, `.search-modal-overlay` (fixed, backdrop blur, z-index 1200), `.search-modal` (max-width 640px, max-height 72vh), header / input row / facets / result list / footer / snippet (`-webkit-line-clamp: 2`) / `.search-snippet-hl` (highlight bg). a11y: `focus-visible` outline ring, mobile (`max-width: 600px`) 분기.
  - `repo/unit/feature-0003-agent-web-ui/src/static/app.js`
    - `state.searchModal: { open, q, owner_id, product_id, date_from, date_to, snippet_opt_in, cursor, results, has_any, debounceTimer, activeResultIdx, lastFocusedBeforeOpen }` 신설.
    - `openSearchModal()` / `closeSearchModal()` / `runSearchQuery({append})` / `renderSearchModalResults()` / `_searchHighlight(text, q)` (case-insensitive 매칭 highlight) / `_bindSearchModalListeners()` 추가.
    - Cmd/Ctrl+K (toggle) + Esc (close 시 only) 글로벌 keydown. ArrowDown/ArrowUp 으로 결과 이동, Enter 로 선택. backdrop click 도 close. 300 ms 디바운스. snippet opt-in chip 토글. cursor pagination 더 보기 버튼.
    - file 끝의 `initialize()` 호출 직전에 `_bindSearchModalListeners()` 호출.
  - `repo/unit/feature-0003-agent-web-ui/tests/test_search_rbac.py` 신설 — 6 시나리오 standalone Python smoke (urllib).
  - `repo/unit/feature-0003-agent-web-ui/docs/{FUNCTION,TASK,MODIFY,REVIEW,REPORT,TEST}.md` + `repo/docs/SECURITY.md §8` + `repo/docs/STATUS.md` — REQ-20260518-0010 / TASK-0072 / CHG-20260518-0010 / REV-20260518-0010 entries.
- Verification:
  - `python3 -m py_compile unit/feature-0003-agent-web-ui/src/app.py` PASS (Phase A0/A1/A2 + helper 5 + endpoint 모두).
  - `python3 -m py_compile unit/feature-0003-agent-web-ui/tests/test_search_rbac.py` PASS.
  - `node --check unit/feature-0003-agent-web-ui/src/static/app.js` PASS (Phase C 의 modal handler 포함).
  - HTTP smoke 6 시나리오 (`tests/test_search_rbac.py`) 는 Phase E 에서 컨테이너 가동 후 실행 (admin/operator 비밀번호 필요).
  - `make web` 재배포 + browser smoke (Cmd+K open / q="test" 입력 / Esc close / snippet chip toggle / cursor 더 보기) 도 Phase E 에서.
- Risks:
  - **WebAccountActivity DDL idempotent**: `CREATE TABLE IF NOT EXISTS`. slow + fast path 양쪽 보장.
  - **3 sub-spec 회귀**: `.own` 사용자 owner_id 가 endpoint 와 _list_conversations 양쪽에서 self 로 강제. byte-equal response 보장. Phase B 6 시나리오 smoke 에서 검증.
  - **PII leak**: snippet opt-in 기본 OFF + `.any` 한정 + audit log + SHA-256 hash. cross-account body 검색 전 사용자가 명시적으로 chip 켜야 본문 미리보기 노출.
  - **성능 회귀**: min 3 char + LIMIT 50 + per-account rate 10/min + `max_execution_time=3000ms` + collation audit. 한계 도달 시 후속 cycle 에서 ngram FULLTEXT 도입 (REVIEW.md REV-20260518-0010 의 미해결 followup).
  - **share-link 회귀**: `share.js` 신규 import 없음. modal element 는 `index.html` 에만 mount.
- Trace: REQ-20260518-0010 → TASK-0072 → §2.1 Implementation Plan (TASK-0072) + outside voice 3 verdict → CHG-20260518-0010 → REV-20260518-0010

## CHG-20260518-0008
- Date: 2026-05-18
- Summary: TASK-0071 (REQ-20260518-0009, Minor §12.3 — shell grid row hotfix, RBAC / endpoint / 데이터 / JS 무변경) TASK-0070 의 list-detail row fix 이후에도 사용자 3 차 screenshot 보고 — dashboard pane 처럼 list-detail 을 사용하지 않는 화면에서 큰 viewport (height 800+) + 짧은 content 조합 시 sidebar / commit-bar 가 viewport 의 약 70% 위치까지만 차지하고 그 아래 회색 빈 영역이 viewport bottom 까지 노출.
- 원인: `.app-shell` / `.admin-shell` 둘 다 `display: grid; height: 100vh` 만 정의하고 `grid-template-rows` 미정의 → default `grid-auto-rows: auto` → single row track 의 height 가 자식 max-content 결정. 자식 (sidebar / column) 의 max-content 가 짧으면 grid track 도 짧음. grid container 자체는 100vh 차지하지만 track 이 100vh 보다 작으면 track 아래 빈 영역. 이전 cycle 의 fix (list-detail / workspace 의 flex grow) 는 column 안의 stretch chain 만 해결 — column 의 height 자체가 grid track 에 의해 결정되는 layer 는 미처리. cascade 의 root.
- 관찰: 동일 viewport (900) 에서 본 환경 (chrome headless) 은 grid track 이 100vh 차지 (다른 grid track sizing 동작), 사용자 환경에서는 max-content 차지 — 환경별 grid algorithm 동작 차이가 회귀 노출 timing 결정.
- Files:
  - `repo/unit/feature-0003-agent-web-ui/src/static/styles.css`
    - `.app-shell` 에 `grid-template-rows: minmax(0, 1fr)` 추가. single row 가 grid container 의 전체 height 차지하도록 명시.
    - `.admin-shell` 에 동일 rule 추가. 두 shell 동일 패턴 유지.
    - 다른 속성 (grid-template-columns / height: 100vh / overflow: hidden) 무변경.
  - `repo/unit/feature-0003-agent-web-ui/src/static/admin.html` — cache-bust `v=20260518-admin-list-rows` → `v=20260518-shell-grid-rows`.
  - `repo/unit/feature-0003-agent-web-ui/src/static/index.html` — cache-bust `v=20260518-product-composer` → `v=20260518-shell-grid-rows` (양쪽 페이지 동일 cache-bust 로 정렬).
  - `repo/unit/feature-0003-agent-web-ui/docs/{FUNCTION,TASK,MODIFY,REVIEW,REPORT}.md` + `repo/docs/STATUS.md` — REQ-20260518-0009 / TASK-0071 / CHG-20260518-0008 / REV-20260518-0008 entries.
- Verification:
  - `SKIP_INIT=1 make web` 재배포 OK.
  - DOM (browser headless `/admin` dashboard pane, viewport `1320x900`):
    `admin-shell h = 900` (viewport 와 일치), `admin-column h = 900`, `commit-bar bottom = 900` (viewport bottom 정확히 sticky), `gridTemplateRows = "900px"` (minmax(0, 1fr) 의 computed 값).
  - Screenshot `/tmp/admin-dashboard-fixed.png` — sidebar (brand → 탭 → ... → pending footer) 가 viewport 전체 height 차지 + admin-column (topbar → dashboard content + 자연 빈 영역 → commit-bar 가 viewport bottom). sidebar / commit-bar 아래 회색 빈 영역 사라짐.
  - 작업 화면 (`/`) 도 동일 fix 자연 적용 — `.app-shell` 의 동일 rule.
  - 양쪽 shell 의 일관성 보장 (`.app-shell` 과 `.admin-shell` 둘 다 `grid-template-rows: minmax(0, 1fr)`).
- Trace: REQ-20260518-0009 → TASK-0071 → CHG-20260518-0008 → REV-20260518-0008 (hotfix of TASK-0068 / 0069 / 0070 layout chain — cascade root fix)

## CHG-20260518-0007
- Date: 2026-05-18
- Summary: TASK-0070 (REQ-20260518-0008, Minor §12.3 — admin list-detail grid row hotfix, RBAC / endpoint / 데이터 / JS 무변경) TASK-0069 follow-up. 사용자 screenshot 2 차 보고 — `역할` / `제품` 등 항목이 적은 pane 에서 화면 height 가 큰 viewport 의 경우 list-col / detail-col box 가 viewport 의 일부만 차지하고 그 아래로 admin-workspace 의 padding 영역이 회색으로 노출. 항목이 많은 pane (`계정` 26 row) 이나 화면이 좁을 때는 content 가 row 를 자연 채워 노출 없었기에 1 차 검증 (720 viewport) 에서는 놓침.
- 원인: `.admin-list-detail { display: grid; grid-template-columns: minmax(280px, 360px) minmax(0, 1fr) }` 의 `grid-template-rows` 미정의 → default `grid-auto-rows: auto` → row 의 height 가 content 결정. `align-items: stretch` 는 row 안에서 column 분배만 담당 (row 자체의 height 결정 X). 결과: list-col / detail-col content 가 짧으면 row 도 짧고 list-detail 의 flex grow 가 의미를 잃음.
- Files:
  - `repo/unit/feature-0003-agent-web-ui/src/static/styles.css`
    - `.admin-list-detail` 에 `grid-template-rows: minmax(0, 1fr)` 추가. 단일 row 의 height 를 명시. minmax(0, ...) 으로 자식의 min-content 무시 — 큰 viewport 에서도 row 가 list-detail 의 flex grow 받은 height 전부 차지.
    - 다른 속성 (grid-template-columns / gap / align-items / min-* 0 / flex 1 1 auto) 무변경.
  - `repo/unit/feature-0003-agent-web-ui/src/static/admin.html` — cache-bust `v=20260518-admin-workspace-flex` → `v=20260518-admin-list-rows`.
  - `repo/unit/feature-0003-agent-web-ui/docs/{FUNCTION,TASK,MODIFY,REVIEW,REPORT}.md` + `repo/docs/STATUS.md` — REQ-20260518-0008 / TASK-0070 / CHG-20260518-0007 / REV-20260518-0007 entries.
- Verification:
  - `SKIP_INIT=1 make web` 재배포 OK.
  - DOM (browser headless `/admin` → 제품 tab, viewport `1320x900`):
    `viewport = 900`, `listDetail h = 682` (이전엔 자기 content 약 200 만큼만), `listCol h = 682`, `detailCol h = 682`, `cbar y = 839 / bottom = 900` (viewport bottom 에 정확히 sticky).
  - Screenshot `/tmp/admin-products-fixed.png` — list-col / detail-col box 가 viewport 의 거의 전체 height 까지 stretch + 3 items 만 있어도 box 자체는 commit-bar 까지 stretch + 회색 빈 영역 사라짐. 사용자 screenshot 회귀 완전 해결.
  - 다른 pane (계정 / 역할) 도 동일 fix 자연 적용 — `.admin-list-detail` 단일 rule 변경.
- Trace: REQ-20260518-0008 → TASK-0070 → CHG-20260518-0007 → REV-20260518-0007 (hotfix of TASK-0068 / 0069 layout chain)

## CHG-20260518-0006
- Date: 2026-05-18
- Summary: TASK-0069 (REQ-20260518-0007, Minor §12.3 — admin layout hotfix, RBAC / endpoint / 데이터 / JS 무변경) TASK-0068 follow-up. 사용자 screenshot 으로 보고된 layout 회귀 — admin `역할 관리` (및 다른 list-detail pane) 에서 commit-bar 가 workspace content 바로 아래에 좁게 위치하고 그 아래로 큰 회색 빈 영역이 admin-column 의 bottom 까지 노출. 원인: TASK-0068 에서 commit-bar 를 admin-shell grid (3rd row) → admin-column 의 flex column item 으로 이전한 후 `.admin-workspace` 에 `flex: 1` 명시 누락. flex column 안에서 workspace 가 자기 content 만큼만 차지 → flex column 의 남은 공간이 빈 채로 보이고 commit-bar 가 workspace 끝 바로 아래에 위치 (sticky bottom 효과 상실). 각 `.admin-pane.is-active` 의 `flex: 1 1 auto` 가 의미를 가지려면 부모 `.admin-workspace` 자체가 stretch 되어야 함.
- Files:
  - `repo/unit/feature-0003-agent-web-ui/src/static/styles.css`
    - `.admin-workspace` 에 `flex: 1 1 auto` 추가. 다른 속성 (overflow / padding / display flex column / min-* 0) 무변경.
  - `repo/unit/feature-0003-agent-web-ui/src/static/admin.html`
    - cache-bust `v=20260518-admin-layout` → `v=20260518-admin-workspace-flex` (admin.html / admin.js 양쪽 stylesheet ref).
  - `repo/unit/feature-0003-agent-web-ui/docs/{FUNCTION,TASK,MODIFY,REVIEW,REPORT}.md` + `repo/docs/STATUS.md` — REQ-20260518-0007 / TASK-0069 / CHG-20260518-0006 / REV-20260518-0006 entries.
- Verification:
  - `SKIP_INIT=1 make web` 재배포 OK.
  - DOM (browser headless `/admin` → 역할 tab):
    `wsHeight = 607, wsBottom = 659, cbarTop = 659, cbarBottom = 720, colHeight = 720, colBottom = 720`
    → `workspaceTouchesCommitBar = true` (둘 사이 빈 공간 없음), `commitBarAtBottom = true` (commit-bar 가 column 의 bottom 에 정확히 위치).
  - Screenshot `/tmp/admin-roles-fixed.png` — 역할 list-detail 이 admin-workspace 의 남은 height 전부 차지 + commit-bar 가 viewport bottom 에 sticky. 회색 빈 영역 사라짐. screenshot 으로 보고된 회귀 fix 확인.
  - 다른 pane (계정 / 제품 / 대시보드) 도 동일 fix 자연 적용 — `.admin-workspace` 의 단일 rule 변경이 전체 admin pane 에 일관 적용.
- Trace: REQ-20260518-0007 → TASK-0069 → CHG-20260518-0006 → REV-20260518-0006 (hotfix of TASK-0068)

## CHG-20260518-0005
- Date: 2026-05-18
- Summary: TASK-0068 (REQ-20260518-0006, Minor §12.3 — admin layout 정합 + 미사용 버튼 정리. backend / endpoint / RBAC / 데이터 영역 무변경.) 사용자 follow-up — 관리 콘솔의 사이드바 구성을 작업 화면 (TASK-0066 의 ChatGPT 패턴) 과 동일하게 정렬 + 헤더의 `새로고침` / `로그아웃` 버튼 제거 (사용자 직접 테스트에서 거의 사용 안 되는 것 확인).
- Files:
  - `repo/unit/feature-0003-agent-web-ui/src/static/admin.html`
    - `<header class="topbar">` 의 `.topbar-brand` 를 `.admin-sidebar` 의 첫 child `.sidebar-brand` (brand-icon + "MySQL AI" — 작업 화면과 동일 brand) 로 이전. 기존 admin brand 가 "관리 콘솔" 이었지만 ChatGPT 패턴은 brand 가 product 정체성 (MySQL AI), 페이지 컨텍스트 (관리 콘솔) 는 topbar 안에 표시.
    - 기존 topbar 의 `#refreshAdminBtn` (새로고침) 과 `#adminLogoutBtn` (로그아웃) 2 element 제거. `#backToAppBtn` (작업 화면 전환) 만 `.topbar-end` 에 유지.
    - `.admin-body` wrapper 제거.
    - 신규 `.admin-column` (sidebar 옆 영역 wrapper, flex column) 안에 `<header class="topbar">` (`.topbar-info` 안에 `<h2 class="chat-title">관리 콘솔</h2>` + `<span class="chat-subtitle">계정 · 역할 · 제품 · 시스템 프롬프트 운영</span>`) → `<main class="admin-workspace">` → `<footer class="admin-commit-bar">` 순서로 배치. commit bar 가 sidebar 와 분리되어 admin-column 의 하단에만 표시.
    - cache-bust `v=20260515-task-0062` → `v=20260518-admin-layout` (admin.html 은 이전 cycle 들의 cache-bust 흐름에서 누락되어 별 cycle 마다 갱신 안 됐던 점도 정렬).
  - `repo/unit/feature-0003-agent-web-ui/src/static/admin.js`
    - `#refreshAdminBtn` click handler 제거 (적용된 pending clear + loadAdminData 호출 로직 제거 — element 부재로 dead reference).
    - `#adminLogoutBtn` click handler 제거 — `POST /api/auth/logout` 호출 흐름 제거. 로그아웃은 작업 화면 (`/`) 의 프로필 drawer 에서 가능하므로 기능 손실 없음.
    - `#backToAppBtn` click handler 유지 (pending change 보호 confirm + `window.location.href = "/"`).
  - `repo/unit/feature-0003-agent-web-ui/src/static/styles.css`
    - `.admin-shell` 의 `grid-template-rows: var(--topbar-h) minmax(0, 1fr) auto` → `grid-template-columns: 220px minmax(0, 1fr)` (작업 화면의 `.app-shell` 과 동일 패턴 — 단일 row 2-column).
    - `.admin-body` rule 폐기 (HTML wrapper 도 제거됨).
    - 신규 `.admin-column` — `display: flex; flex-direction: column; min-width: 0; overflow: hidden`.
    - `.admin-sidebar` 의 `padding: 10px 8px` 제거 — brand 가 sidebar 의 첫 영역으로 들어가면서 padding 을 각 child (`.sidebar-brand`, `.admin-tabs`, `.admin-sidebar-foot`) 가 갖도록 함. 신규 `.admin-sidebar .admin-tabs { padding: 10px 8px 0 }` + `.admin-sidebar .admin-sidebar-foot { padding-left: 8px; padding-right: 8px }`.
    - 반응형 `@media (max-width: 680px)` 에서 `.admin-body { grid-template-columns: 1fr }` → `.admin-shell { grid-template-columns: 1fr }` 로 정렬.
    - `.sidebar-brand` rule (TASK-0066 신설, index.html 의 `.sidebar` 에서만 사용) 은 그대로 재사용 — admin.html 의 sidebar 안에서도 동일 스타일 (52px height, border-bottom).
  - `repo/unit/feature-0003-agent-web-ui/docs/{FUNCTION,TASK,MODIFY,REVIEW,REPORT}.md` + `repo/docs/STATUS.md` — REQ-20260518-0006 / TASK-0068 / CHG-20260518-0005 / REV-20260518-0005 entries.
- Verification:
  - `node --check unit/feature-0003-agent-web-ui/src/static/admin.js` PASS
  - `SKIP_INIT=1 make web` 재배포 OK
  - DOM 검증 (browser headless `/admin`): `refreshBtnPresent = false`, `logoutBtnPresent = false`, `backBtnPresent = true`, `brandInSidebar = true` (sidebar-brand 가 admin-sidebar 안에 mount), `adminColumnPresent = true`, `oldAdminBodyPresent = false`, `topbarHeight = 52` (var(--topbar-h)), `topbarInfoText = "관리 콘솔 ... 시스템 프롬프트 운영"`, `gridCols = "220px 1060px"` (sidebar 220 + 나머지).
  - Screenshot `/tmp/admin-merged.png`: 좌측 admin-sidebar (brand "MA MySQL AI" + 대시보드 (active) + 계정 카테고리 (계정 26 / 역할 5) + 제품 카테고리 (제품 3) + pending 변경 0건 footer) / 우측 admin-column (topbar "관리 콘솔" 좌측 정렬 제목 + 부제 + 우측 끝 "작업 화면" 버튼만 / Overview 운영 현황 metric cards / 변경사항 0건 commit bar) — 작업 화면과 100% 일관된 ChatGPT 패턴.
- Trace: REQ-20260518-0006 → TASK-0068 → CHG-20260518-0005 → REV-20260518-0005 (follow-up of TASK-0066 / 0067)

## CHG-20260518-0004
- Date: 2026-05-18
- Summary: TASK-0067 (REQ-20260518-0005, Minor §12.3 — UI 위치 이전 + native select → custom dropdown 전환. backend / endpoint / RBAC / 데이터 영역 무변경.) 사용자 직접 테스트 follow-up — TASK-0066 의 layout 통합 후 사이드바도 채팅 영역처럼 확장하기 위해 `제품 칩` 을 사이드바에서 composer 의 우측 (textarea 와 send 버튼 사이) 으로 이전. ChatGPT 의 모델 선택 UI 패턴 — chip 클릭 시 drop-up dropdown 으로 옵션 표시 + 선택 시 즉시 적용 + chip label/dot 갱신.
- Files:
  - `repo/unit/feature-0003-agent-web-ui/src/static/index.html`
    - `.sidebar-head` 의 `.product-chip-wrap` (caption + label.product-chip + select 형태) 제거. `.sidebar-head` 에는 `#newConversationBtn` 만 남음 → 사이드바 vertical 공간 확장.
    - `.composer-box` 안 textarea 와 `#sendBtn` 사이에 `.composer-product-chip-wrap` 신설 — `button#productChip` (dot + label + arrow) + `div#productDropupMenu.product-dropup-menu`.
    - chip 의 기존 ID 보존 (`productChip`, `productChipDot`) + 신규 ID (`productChipLabel`, `productDropupMenu`).
    - cache-bust `v=20260518-topbar-merge` → `v=20260518-product-composer`.
  - `repo/unit/feature-0003-agent-web-ui/src/static/app.js`
    - `renderProductChip()` 재작성 — 기존 native `<select id="productSelect">` 의존 (renderProductOptions 호출) 제거. 새 chip 의 dataset.mode / label / aria-label / busy 시 disabled 갱신. menu 가 열려 있으면 `renderProductDropupMenu()` 도 즉시 갱신해 옵션 list 동기화.
    - chip label 정책: pinned 시 `compactLabel = product_key` (chip width 보존), aria-label 은 `fullLabel = "{name} ({key})"` (a11y 보존).
    - 신규 `renderProductDropupMenu()` — section head ("이 대화의 제품") + auto item + products 의 pinned items 렌더. `state.products` 변경 시 menu open 중에도 즉시 반영.
    - 신규 `buildProductDropupItem({mode, pid, label, selected})` — `role="menuitem"`, dot + label + check svg, click handler 가 closeProductDropup + setActiveProduct 호출.
    - 신규 `openProductDropup()` / `closeProductDropup()` — menu visibility + chip `aria-expanded` 동기화 + outside-click (mousedown capture, setTimeout 0 으로 trigger click 충돌 방지) + ESC 닫기.
    - DOM ready 의 기존 `productSelect` change handler 제거. 신규 `#productChip` click handler 가 dropdown toggle.
    - `setActiveProduct` 본체 무변경 — backend `PATCH /api/conversations/{cid}/product` 호출, optimistic state 갱신, toast 메시지 모두 그대로.
  - `repo/unit/feature-0003-agent-web-ui/src/static/styles.css`
    - 신규 `.composer-product-chip-wrap` (relative + flex 끝 정렬), `.composer-product-chip` (pill: 30px height, padding 0 9px, border 1px, hover/expanded 시 primary 색 강조, busy 시 opacity .5), `.composer-product-chip-dot` (7px 원, mode=auto 회색 / mode=pinned 파랑), `.composer-product-chip-label` (max-width 130px ellipsis).
    - 신규 `.product-dropup-menu` (`position: absolute; right: 0; bottom: calc(100% + 6px); z-index: 50; min-width: 220px; max-width: 280px; max-height: 320px; overflow-y: auto`) — chip 위로 펼침 (drop-up).
    - 신규 `.product-dropup-item` + `.is-selected` + `.product-dropup-item-dot` + `.product-dropup-item-label` + `.product-dropup-item-check` (svg checkmark, selected 시만 opacity 1) + `.product-dropup-section-head` (소형 caps).
    - `.composer-box` 의 `gap: 8px` → `gap: 6px` 로 조정 (chip + send 간 간격 자연스럽게).
    - 기존 `.product-chip-wrap` / `.product-chip` / `.product-chip-caption` / `.product-chip-select` rule 은 stylesheet 에 남아 있으나 사용처가 사라져 dead code (제거는 별 cycle).
  - `repo/unit/feature-0003-agent-web-ui/docs/{FUNCTION,TASK,MODIFY,REVIEW,REPORT}.md` + `repo/docs/STATUS.md` — REQ-20260518-0005 / TASK-0067 / CHG-20260518-0004 / REV-20260518-0004 entries.
- Verification:
  - `node --check unit/feature-0003-agent-web-ui/src/static/app.js` PASS
  - `SKIP_INIT=1 make web` 재배포 OK
  - DOM 검증 (browser console): `chipInComposer = true` (chip 이 composer-box 안), `oldSelectPresent = false` (기존 native select 부재), `oldWrapPresent = false` (sidebar product-chip-wrap 부재), `sidebarHeadChildren = ["BUTTON.btn-new-conv"]` (sidebar-head 가 새 대화 버튼만), `chipLabel = "auto"`, `chipMode = "auto"` (hydrate 정상).
  - 동작 검증: chip click → menu 표시 (4 items: auto + KR + MV + GZ_KR, auto selected), `dropUp = true` (menuY=459 < chipY=644 — drop-up 보장), KR item click → menu close + chip 갱신 (`chipMode=pinned, chipLabel="KR", chipAriaLabel="이 대화의 제품 선택, 현재 킹스레이드 (KR)"`) + toast "제품을 킹스레이드로 바꿨어요. 다음 답변부터 적용됩니다.". backend endpoint `PATCH /api/conversations/{cid}/product` 정상 호출.
- Trace: REQ-20260518-0005 → TASK-0067 → CHG-20260518-0004 → REV-20260518-0004 (follow-up of TASK-0066)

## CHG-20260518-0003
- Date: 2026-05-18
- Summary: TASK-0066 (REQ-20260518-0004, Minor §12.3 — UI layout 재구조화, RBAC / endpoint / 데이터 영역 무변경) TASK-0065 follow-up. 사용자 직접 테스트 피드백: 헤더 4 버튼 제거 후 `.chat-header` 가 거의 비어 있어 `.topbar` (관리 콘솔) 와 영역 통합 필요. ChatGPT 패턴으로 layout 재구조화 — sidebar 가 전체 height, brand (`[MA] MySQL AI`) 를 sidebar 의 첫 영역으로 이전, topbar (대화 제목 + 관리 콘솔) 을 chat-column 의 첫 영역으로 이전, chat-header 폐기로 채팅 영역 확장. 대화 제목은 좌측 정렬 (사용자 명시 — 중앙 정렬 금지).
- Files:
  - `repo/unit/feature-0003-agent-web-ui/src/static/index.html`
    - `.app-shell` 내 grid 구조 재정의:
      - 기존: `.topbar` (전체 너비) + `.app-body` (sidebar + chat-pane)
      - 신규: `.sidebar` (column 1, 전체 height) + `.chat-column` (column 2, 전체 height) — `.app-body` wrapper 폐기.
    - `.topbar-brand` 를 `.sidebar` 의 첫 child `.sidebar-brand` 로 이전 (brand icon + name).
    - 신규 `.chat-column` 안에 `.topbar` (대화 제목 + tools + 관리 콘솔) → `.chat-pane` 순서.
    - `.chat-pane > .chat-header` 폐기 — `.chat-title` / `.chat-subtitle` / `#loadMoreBtn` 은 `.topbar > .topbar-info` / `.topbar-tools` 로 이전. `#openAdminBtn` 은 `.topbar-end` 위치 유지.
    - cache-bust `v=20260518-header-cleanup` → `v=20260518-topbar-merge`.
  - `repo/unit/feature-0003-agent-web-ui/src/static/styles.css`
    - `.app-shell` 의 `grid-template-rows: var(--topbar-h) minmax(0, 1fr)` → `grid-template-columns: var(--sidebar-w) minmax(0, 1fr)` (단일 row, 2 column).
    - `.app-body` rule 폐기 (HTML 에서 wrapper 제거됨).
    - `.chat-column` 신설 — `display: flex; flex-direction: column; min-width: 0; overflow: hidden`.
    - `.sidebar-brand` 신설 — `padding: 0 14px; height: var(--topbar-h); border-bottom: 1px solid var(--border-subtle)`. topbar 와 baseline (y=52px) 정렬.
    - `.topbar` rule 갱신 — `padding: 0 20px; height: var(--topbar-h); flex-shrink: 0`. 기존 topbar-brand min-width 제거 (brand 가 sidebar 로 이전됨).
    - `.topbar-info` 신설 — `display: flex; flex-direction: column; min-width: 0; flex: 1 1 auto` (좌측 정렬, justify-content 미설정).
    - `.topbar-tools` 신설 — `display: flex; align-items: center; gap: 6px; flex-shrink: 0` (loadMoreBtn 등).
    - `.topbar-end` 기존 유지 (관리 콘솔, `margin-left: auto`).
    - `.chat-header` / `.chat-header-info` / `.chat-header-tools` rule 폐기. `.chat-title` / `.chat-subtitle` typography rule 만 유지 (topbar-info 안에서 사용).
    - 반응형 `@media (max-width: 680px) { .app-body { ... } }` → `.app-shell { grid-template-columns: 1fr }` 로 변경.
  - `repo/unit/feature-0003-agent-web-ui/docs/{FUNCTION,TASK,MODIFY,REVIEW,REPORT}.md` + `repo/docs/STATUS.md` — REQ-20260518-0004 / TASK-0066 / CHG-20260518-0003 / REV-20260518-0003 entries.
- Verification:
  - DOM 검증: `.app-shell` gridTemplateColumns = `"252px 1028px"` (sidebar-w + 나머지), `.sidebar-brand` 정상 mount + 텍스트 "MA MySQL AI", `.topbar` mount + height 52px, `.topbar-info` mount, 기존 `.chat-header` DOM 부재.
  - Browser smoke (`gstack /browse` headless + screenshot `/tmp/layout-merged.png`): sidebar 좌측 (brand + 제품 칩 + 새 대화 + conv list + 프로필) / chat-column 우측 (topbar 제목 좌측 정렬 + `최근 갱신 ... 메시지 22 · 소유자 admin` 부제 + 우측 끝 `관리 콘솔` 버튼) — ChatGPT 패턴 정확 구현. brand 와 topbar 의 baseline (y=52px) 정렬. sticky 날짜 분기선 ("2026년 4월 16일") + per-conversation "···" trigger 등 직전 cycle 변경사항 무회귀.
  - JS 변경 없음 — 모든 element ID 보존 (conversationTitle / conversationSubtitle / loadMoreBtn / openAdminBtn 모두 getElementById 동작).
- Trace: REQ-20260518-0004 → TASK-0066 → CHG-20260518-0003 → REV-20260518-0003 (follow-up of TASK-0065)

## CHG-20260518-0002
- Date: 2026-05-18
- Summary: TASK-0065 (REQ-20260518-0003, Minor §12.3 — UI 정리 + sticky 분기선) TASK-0063 직접 테스트 follow-up. (1) 헤더의 대화 복사 / 공유 / 제목 변경 / 삭제 4 버튼 제거 (per-item "···" menu 로 일원화). (2) menu trigger 우측 상단 → 우측 하단 이동 (badge "내/sales" 우측 상단 영역과 시각 충돌 해결). (3) 채팅 로그 날짜 분기선에 `position: sticky; top: 0` 적용 — Slack 패턴. 사용자가 분기선까지 scroll 할 필요 없이 현재 시야의 날짜 그룹 헤더가 messageLog 상단에 stick 되고 click 시 캘린더 popover anchored 진입.
- Files:
  - `repo/unit/feature-0003-agent-web-ui/src/static/index.html`
    - `chat-header-tools` 의 `forkConversationBtn` / `shareConversationBtn` / `renameConversationBtn` / `deleteConversationBtn` 4 element 제거. `loadMoreBtn` 만 유지 (이전 기록 — 별 기능).
    - cache-bust `v=20260518-conv-menu` → `v=20260518-header-cleanup`.
  - `repo/unit/feature-0003-agent-web-ui/src/static/app.js`
    - 4 element 의 `getElementById` 변수 선언 (line 56/59/60/61) 제거.
    - `toggleConversationActionButtons` 류 가시성 로직 (line 2492 ~ 2530) 의 4 element 관련 분기 (35 lines) 삭제. cancel/finalize 만 남음.
    - DOM ready 의 4 element click handler (line 3837 ~ 3860) 삭제. backend helper (`deleteConversation` / `renameCurrentConversation` / `forkConversation` / `createConversationShare`) 는 conv-item "···" menu 의 makeItem handler 가 cid 인자로 직접 호출하므로 유지.
  - `repo/unit/feature-0003-agent-web-ui/src/static/styles.css`
    - `.conv-item` 에 `padding-right: 32px` 추가 (trigger 22px + margin 10px 확보).
    - `.conv-item-menu-trigger` 의 `top: 6px` → `bottom: 6px` (위치 우측 하단으로 이동).
    - `.message-date-divider` 에 `position: sticky; top: 0; z-index: 5` + `padding: 4px 0` (sticky 안정성). label 의 배경 `var(--surface-2)` → `var(--surface-1, #ffffff)` 로 조정 (sticky 시 message bubble 위에 자연스럽게 떠 보이도록 불투명도 강화) + `box-shadow: 0 1px 2px rgba(0,0,0,.04)` 추가. hover 시 `box-shadow: 0 2px 6px rgba(37,99,235,.18)` 로 elevation 강화.
  - `repo/unit/feature-0003-agent-web-ui/docs/{FUNCTION,TASK,MODIFY,REVIEW,REPORT}.md` + `repo/docs/STATUS.md` — REQ-20260518-0003 / TASK-0065 / CHG-20260518-0002 / REV-20260518-0002 entries.
- Verification:
  - `node --check unit/feature-0003-agent-web-ui/src/static/app.js` PASS
  - `SKIP_INIT=1 make web` 재배포 OK
  - Browser smoke (`gstack /browse` headless): (1) 헤더 4 버튼 부재 확인 (snapshot 의 `chat-header-tools` 영역에 `loadMoreBtn` + product selector 외 추가 버튼 없음), (2) active conv-item 의 "···" trigger 가 bottom=6px / right=6px / opacity=1 로 우측 하단 정상 위치 (DOM `getComputedStyle` 확인), (3) 2 분기선 conversation 에서 `messageLog.scrollTop = 600` 깊이 스크롤 시 첫 분기선 "2026년 4월 15일" 이 messageLog 상단에 stick (screenshot `/tmp/sticky-scrolled.png` 첨부) — Slack 패턴 정확 구현.
- Trace: REQ-20260518-0003 → TASK-0065 → CHG-20260518-0002 (follow-up of TASK-0063 / CHG-20260518-0001)

## CHG-20260518-0001
- Date: 2026-05-18
- Summary: TASK-0063 (REQ-20260518-0001, **Major** §12.3 — RBAC catalog 확장 2건 + 신규 endpoint 1건 + 파괴적 액션 menu 통합) 작업 화면 대화 항목별 "···" menu (복사 / 공유 / 제목 변경 / 삭제) + 캘린더 시간 이동을 채팅 로그 날짜 분기선 click trigger 로 이전. ChatGPT / Slack UX 패턴 정렬.
- Decisions (사용자):
  - 복사 = full self-fork (`_fork_conversation_impl` 재활용, 메시지+첨부+SQL 결과 + 활성 대화 자동 전환).
  - 신규 권한 `conversation.duplicate.own` / `conversation.duplicate.any` 분리 추가 (rename/delete 일관성).
  - 헤더 `shareConversationBtn` 유지 (active 대화의 quick share path) — per-item menu 와 dual entry.
  - 헤더 `historyCalendarBtn` 제거 — 캘린더 trigger 는 채팅 로그의 날짜 분기선이 단일 진입점. 먼 과거 jump 는 popover header 의 ‹ › (월) + « » (년, 데이터가 1년 이상일 때만) 로 해결.
- Outside voice review: Codex (general-purpose subagent, 10 blindspot 보강 — risk 1 admin/operator/sales catchup loop 일반화, risk 2 IsDynamic NULL legacy schema 는 별도 cycle followup, risk 3 fast-path hydration call site 정합, risk 5 share-token bypass 차단 (read-gate 명시 호출), risk 6 403 vs 404 metadata leak 차단 (rename/delete 와 동일 wording), risk 7 `.any` superset semantics backend mirror, risk 8 frontend hide-vs-disable — rename/delete pattern (visible + is-access-blocked + toast) 채택, risk 9 PERMISSION_LABELS / PERMISSION_DESCRIPTIONS / requiredPermissionsFor 3 곳 갱신, risk 10 사본 제목 grapheme-safe truncation).
- Catchup 순서 fix: `_ensure_seed_catchup` 의 `_ensure_permission_catalog` 호출을 `_ensure_seed_roles` 앞으로 옮김. 기존 호출 순서로는 `_ensure_seed_roles` 의 admin/operator/sales catchup loop 이 `_permission_id_map(conn)` 으로 신규 권한 id 를 lookup 할 때 catalog 에 아직 INSERT 안 되어 0 을 받아 skip 하던 회귀 (Codex risk 3 변형).
- Files:
  - `repo/unit/feature-0003-agent-web-ui/src/app.py`
    - `PERMISSION_DEFINITIONS` 에 `conversation.duplicate.own` / `conversation.duplicate.any` 2건 추가 (catalog 34 → 36, group=conversation).
    - `SEED_ROLE_DEFINITIONS` operator/sales 에 `conversation.duplicate.own` grant. admin 은 `set(PERMISSION_CODES)` 으로 자동 포함.
    - `_ensure_seed_roles` 의 admin catchup tuple 에 `conversation.duplicate.own/.any` 추가. operator/sales catchup loop 을 `(share.create, duplicate.own)` 리스트 기반으로 일반화 (Codex risk 1).
    - `_ensure_seed_catchup` 의 `_ensure_permission_catalog` 호출을 `_ensure_seed_roles` 앞으로 이동 (Codex risk 3 변형 fix).
    - 신규 endpoint `POST /api/conversations/{cid}/duplicate` — read-gate 먼저 (404 단일 wording, Codex risk 5/6), `.any` superset semantics (Codex risk 7), `_fork_conversation_impl` 재활용, 제목은 grapheme-safe `사본: <base[:256-len('사본: ')]>` (Codex risk 10).
  - `repo/unit/feature-0003-agent-web-ui/src/static/app.js`
    - `PERMISSION_LABELS` / `PERMISSION_DESCRIPTIONS` 양쪽에 duplicate 2건 추가 (Codex risk 9).
    - `requiredPermissionsFor` switch 에 `conversation.duplicate` / `conversation.share` case 추가.
    - `renameCurrentConversation(cid)` / `deleteConversation(cid)` / `createConversationShare({conversationId})` 시그니처를 cid 인자 수용 가능하도록 확장 (backward compat).
    - 신규: `duplicateConversationFromMenu(cid)` (RBAC + create 권한 사전 gate + apiFetch POST).
    - 신규: `openConversationItemMenu(cid, triggerEl)` / `closeConversationItemMenu()` — fixed-position dropdown (z=200) + a11y (role=menu/menuitem, aria-haspopup, aria-expanded) + outside-click (setTimeout 0 으로 trigger click 충돌 방지) + ESC + scroll/resize close + viewport edge clamping.
    - `renderConversationList()` 의 conv-item 마다 `.conv-item-menu-trigger` 추가 (hover 시 fade-in, active 시 상시 표시) + click handler toggle + keyboard (Enter/Space).
    - `renderMessages()` 에 `.message-date-divider` 삽입 (createdAt 비교, 첫 등장만) + click → `openHistoryCalendarAt(dateKey, divider)`.
    - `openHistoryCalendar` → `openHistoryCalendarAt(dateKey?, anchorEl?)` 로 리팩토링. anchorEl 가 주어지면 popover 를 fixed-position 으로 분기선 하단에 mount + viewport clamping.
    - `calendarDateBounds()` 신설 — `(oldest, newest)` 키 추출. 년 jump 버튼 (« ») 노출 조건 = `(newestYear - oldestYear) >= 1`.
    - `renderHistoryCalendar()` 의 popover header 에 동적 nav 슬롯 (`#calendarNav`) 렌더 — `‹ › [Y년 M월] (« »)` + cursor 가 oldest/newest 범위를 넘으면 disabled.
    - 헤더 historyCalendarBtn 의 가시성 토글 + click handler + outside-click pair 제거. outside-click 은 popover 외부 + `.message-date-divider` 외부 click 일 때만 닫음.
  - `repo/unit/feature-0003-agent-web-ui/src/static/index.html` — `historyCalendarBtn` 삭제, popover header 를 `#calendarNav` slot + hidden `#calendarTitle` (backward compat) 로 교체. cache-bust `v=20260518-conv-menu`.
  - `repo/unit/feature-0003-agent-web-ui/src/static/styles.css` — `.conv-item-menu-trigger` (absolute 위치, hover/active fade), `.conv-item-menu` (fixed, z=200, shadow), `.conv-menu-item` + `.is-danger` + `.is-access-blocked`, `.message-date-divider` + label (Slack pill 패턴, before/after horizontal line), `.history-calendar-nav` + `.calendar-nav-btn` + `.calendar-nav-title` (월/년 nav).
- Verification:
  - `python3 -m py_compile unit/feature-0003-agent-web-ui/src/app.py` PASS
  - `node --check unit/feature-0003-agent-web-ui/src/static/app.js` PASS
  - `node --check unit/feature-0003-agent-web-ui/src/static/admin.js` PASS
  - `SKIP_INIT=1 make web` 재배포 OK (buildx provenance race 우회는 기존 dc-build 가드 동작).
  - DB 직접 확인: `agent_memory.WebPermissions` 의 `conversation.duplicate.own/.any` row hydrate 확인. 신규 role grant — admin (duplicate.any + duplicate.own), operator (duplicate.own), sales (duplicate.own).
  - Browser smoke (gstack `/browse` headless): 좌측 conv-item 마다 "···" trigger 표시, click → 4 menu 항목 (복사 / 공유 / 제목 변경 / 삭제 — danger 색) 정상 mount + outside-click + ESC close 동작. 채팅 로그에 "YYYY년 M월 D일" 분기선 표시 (메시지 2 일 이상), click → popover anchored 오픈, 월 nav (‹ ›) 정상 (현재 데이터 1년 미만이라 « » 조건 충족 안 됨 = 정상). 헤더 historyCalendarBtn 부재 확인.
- Trace: REQ-20260518-0001 → TASK-0063 → CHG-20260518-0001

## CHG-20260515-0005
- Date: 2026-05-15
- Summary: TASK-0062 (REQ-20260515-0011 / REQ-20260515-0012, Minor §12.3) — 사용자 GOAL 2026-05-15 후속 2 항목.
  - **다중선택 UX 개선**: `.conv-item-checkbox` 제거 → Ctrl/Meta toggle + Shift range 만으로 다중 선택. 일반 click 은 단일 선택 + `state.conversationSelected.clear()` + `state.conversationLastClickIdx = -1`. `renderConversationBulkBar()` 의 노출 임계값 `count >= 1` → `count >= 2`. 즉 2 개 이상 선택 시에만 bar 가시.
  - **Point rail 위치 비례 분포**: `.message-point-rail` 을 `flex column` → `position: relative` 로 변경. 각 `.message-point-dot` 가 `position: absolute; left: 50%; top: <pct>%; transform: translate(-50%, -50%)`. `pct = (msg.offsetTopInLog + msg.height/2) / messageLog.scrollHeight * 100`. 신규 helper `layoutMessagePointRail()` 가 `renderMessagePointRail` 끝 + resize listener 에서 재계산. `.is-active` 의 transform 도 `translate(-50%, -50%) scale(1.8)` 로 보정 (좌측 튐 방지).
- Files:
  - `repo/unit/feature-0003-agent-web-ui/src/static/app.js` — `renderConversationList` 의 checkbox block 제거 + 일반 click 의 `conversationSelected.clear()` 추가 + `renderConversationBulkBar` 임계값. `renderMessagePointRail` 끝에 `layoutMessagePointRail()` 호출 + helper 신설 + resize handler 가 layout + highlight 둘 다 호출.
  - `repo/unit/feature-0003-agent-web-ui/src/static/styles.css` — `.message-point-rail` (flex/gap/padding/overflow 제거 + relative 추가), `.message-point-dot` (position absolute + transform translate), `.message-point-dot.is-active` (translate + scale 합성), `.conv-item-checkbox` rule 제거, `.conv-item.is-multi-selected` outline-offset -1px 보강.
  - `repo/unit/feature-0003-agent-web-ui/src/static/index.html` + `admin.html` — cache-bust `v=20260515-task-0062`.
  - `repo/unit/feature-0003-agent-web-ui/docs/FUNCTION.md` — REQ-20260515-0011 / REQ-20260515-0012 + AC-0108 ~ AC-0113 추가.
  - `repo/unit/feature-0003-agent-web-ui/docs/TASK.md` — Task Queue entry 추가.
- Verification:
  - `node --check unit/feature-0003-agent-web-ui/src/static/app.js` PASS
  - `node --check unit/feature-0003-agent-web-ui/src/static/admin.js` PASS
  - (browser smoke 는 후속 단계에서 make web 재배포 후 진행)
- Trace: REQ-20260515-0011 / REQ-20260515-0012 → TASK-0062 → CHG-20260515-0005

## CHG-20260515-0004
- Date: 2026-05-15
- Summary: TASK-0061 round 2 — /qa 심층 검증 결과 docs 보강. Phase 4/5 의 사용자 상호작용 흐름 (dot click smooth scroll, 캘린더 월 이동 + day click) 을 browser 자동화 (`make browser-*`, session `483add52718b4a93`) 로 실측 확인. Phase 3/6/8 의 destructive endpoint 는 1차 cycle 의 contract 확정 (응답 형식 / 권한 / DOM 노출) 으로 충분, 운영 환경 실 호출은 사용자 명시 시점에 별도 진행 권고. round 2 신규 발견 이슈 0 건.
- Files:
  - `repo/unit/feature-0003-agent-web-ui/docs/REPORT.md` — round 2 검증 결과 summary 라인 prepend.
  - `repo/unit/feature-0003-agent-web-ui/docs/TEST.md` — round 2 test run history entry prepend (Phase 4/5 deep + Phase 3/6/8 contract 정합 메모).
- Verification:
  - browser session `483add52718b4a93`, screenshot `/shared/out/browser/shot_20260515_091222.png`.
  - 대화 `20260515080029-a5353434` (2 메시지), Point rail dot click → `messageLog.scrollTop=245 → smooth scroll`, active dot id `291` 갱신.
  - 캘린더 popover title 2026년 5월 ↔ 4월 prev/next 이동, day "15" click → 시각 list 1개 표시.
- Trace: TASK-0061 → CHG-20260515-0003 → CHG-20260515-0004 (post-ship QA round 2).

## CHG-20260515-0003
- Date: 2026-05-15
- Summary: TASK-0061 (REQ-20260515-0003 ~ REQ-20260515-0010, **Major** §12.3 — UI 상태 / 인증(비밀번호 초기화) / 파괴적 데이터(bulk delete) 일괄 변경) GOAL.md 8 항목 합본 cycle.
- Phases:
  - Phase 1+2: 답변 버블 내부 실시간 step 진행상황 + 신규 대화 첫 요청 즉시 polling 연결 (state.pendingBubble + renderPendingAssistantBubble + 1초 elapsed timer + applyProgressPayload 동기화 + sendPrompt lazy-create 분기에서 cid 발급 즉시 polling start).
  - Phase 3: 끊긴 processing 대화 만료 감지 + 붉은 badge — backend `_compute_display_status(conn, conversation_id, last_status, last_status_at, last_status_run_id)` + `_last_step_at_for_run` + `_parse_kv_timestamp` helper. env `WEB_PROGRESS_STALE_TIMEOUT_SECONDS=1200` (20분). `_list_conversations` payload 에 `display_status` / `raw_status` / `is_stale` 추가. `/api/progress` / `_build_ask_status_snapshot` / `/api/ask_status` / `/api/ask_result` long-poll 일관 stale 처리. frontend `.conv-dot.is-stale-error` + tooltip + bubble error 영역 + 1회 toast 안내.
  - Phase 4: 우측 Point rail (`#messagePointRail` + `renderMessagePointRail()` + scroll observer → `highlightActivePoint()` + click → `scrollIntoView smooth`). 좁은 화면(`max-width:720px`) hidden.
  - Phase 5: 캘린더/시각 이동 — backend `/api/history_dates` 가 `AgentMemoryMessages` 정본 기준 (이전 `AgentCoreMessages` 에서 변경). frontend `historyCalendarBtn` + `#historyCalendarPopover` (월간 grid + 시각 목록) + `/api/history_anchor?at=...` jump + `.is-anchor-highlight` 1.5s 강조.
  - Phase 6 (Critical 분면): 관리자 주관 비밀번호 초기화. `WebAccounts.MustChangePassword TINYINT(1) NOT NULL DEFAULT 0` 컬럼 idempotent ALTER (`_ensure_web_tables` slow path + `_ensure_must_change_password_schema` + `_ensure_seed_catchup` fast path). 신규 endpoint `POST /api/admin/accounts/{id}/password-reset` — `secrets.token_urlsafe(12)` 임시비번 + `_hash_password` 저장 + `MustChangePassword=1` + 대상 계정 `WebAuthSessions IsRevoked=1`. self-reset 거부. `_serialize_account` 에 `must_change_password` 필드 + `_fetch_account_rows` 가 `COALESCE(a.MustChangePassword, 0)` SELECT. `/api/auth/me` PATCH 가 비밀번호 변경 성공 시 `MustChangePassword = 0`. frontend `adminPasswordResetBtn` (Account detail) + 1회 표시 modal + 강제 변경 modal (login + initializeWorkspace 직후 must_change_password=true 시 노출).
  - Phase 7: 관리자 select-all 현재 페이지 fix — `currentPageAccounts()` helper 신설. `accountSelectAll` change handler 와 `updateAccountSelectAllCheckbox()` 가 동일 helper 사용해 현재 페이지 row 만 토글. 다른 페이지 선택은 보존.
  - Phase 8: 내 대화 Ctrl/Shift 다중 선택 + bulk delete — `state.conversationSelected: Set<string>` + `state.conversationLastClickIdx`. `renderConversationList()` 의 own 그룹에만 `.conv-item-checkbox` 추가 + Ctrl/Meta toggle + Shift range. `.conv-bulk-bar` (label / 삭제 / 선택 해제). backend `_delete_conversation_impl(conn, account, conversation_id, force, confirm_text)` helper 추출 (단건/일괄 공용) + 신규 `POST /api/delete_conversations` partial success endpoint (`{deleted, deleted_pending, failed:[{conversation_id, reason}], current}`). ≥10 typed-confirm + processing 대화 강제 삭제 confirm.
- Files:
  - backend: `repo/unit/feature-0003-agent-web-ui/src/app.py` — env + helper 추가, `_list_conversations` / `/api/progress` / `_build_ask_status_snapshot` / `/api/ask_result` / `/api/history_dates` / `_delete_conversation_impl` / `/api/delete_conversations` / `/api/admin/accounts/{id}/password-reset` / `_serialize_account` / `_fetch_account_rows` 수정.
  - frontend: `repo/unit/feature-0003-agent-web-ui/src/static/app.js` — state 확장 + renderMessages + renderPendingAssistantBubble + elapsed timer + applyProgressPayload 동기화 + renderConversationList Ctrl/Shift + renderConversationBulkBar + bulkDeleteConversations + renderMessagePointRail + highlightActivePoint + calendarState + openHistoryCalendar / renderHistoryCalendar / jumpToHistoryAnchor + showForceChangePasswordModal + must_change_password hook in handleLogin/initializeWorkspace + listener wiring.
  - frontend: `repo/unit/feature-0003-agent-web-ui/src/static/admin.js` — currentPageAccounts + select-all change handler + updateAccountSelectAllCheckbox + renderAccountDetail 의 adminPasswordResetBtn + triggerPasswordResetFlow + showTemporaryPasswordModal.
  - frontend: `repo/unit/feature-0003-agent-web-ui/src/static/index.html` — `.messages-wrap` / `#messagePointRail` / `#historyCalendarBtn` / `#historyCalendarPopover` / `#conversationBulkBar` 추가 + cache-bust `v=20260515-task-0061`.
  - frontend: `repo/unit/feature-0003-agent-web-ui/src/static/admin.html` — cache-bust 만 갱신 (button 은 renderAccountDetail 에서 동적 mount).
  - frontend: `repo/unit/feature-0003-agent-web-ui/src/static/styles.css` — Phase 1~8 신규 클래스 토큰 (pending bubble + stale dot + point rail + history calendar + conv-item-checkbox + conv-bulk-bar + admin-modal + temp-password-display + field-input).
  - env: `repo/.env.example` — `WEB_PROGRESS_STALE_TIMEOUT_SECONDS=` placeholder + 설명.
  - docs: `repo/unit/feature-0003-agent-web-ui/docs/{FUNCTION,TASK,MODIFY,REVIEW,REPORT,TEST}.md`.
- Verification:
  - `python3 -m py_compile unit/feature-0003-agent-web-ui/src/app.py` PASS
  - `node --check unit/feature-0003-agent-web-ui/src/static/app.js` PASS
  - `node --check unit/feature-0003-agent-web-ui/src/static/admin.js` PASS
  - `make web` 재배포 PASS — `repo-web-1 Recreated/Started`
  - browser 검증 (http://web:8000): cache-bust `v=20260515-task-0061` 적용 확인 / `.messages-wrap` / `#messagePointRail` / `#historyCalendarBtn` / `#historyCalendarPopover` / `#conversationBulkBar` 모두 존재 / login 후 conv list 45개 + own checkbox 34개 / bulk bar 1개 선택 시 "1개 선택됨" 라벨 / 캘린더 popover 2026년 4월 + has-messages 1일 (4/22) / `/api/progress` 응답에 display_status·raw_status·is_stale 포함 / `/api/history_dates` 응답 first/last 2026-04-22 / `/api/delete_conversations` 빈 body → 400 validation / pending bubble 강제 렌더 시 spinner + elapsed + bubble DOM 정상 / admin page accountList 15 + currentPageAccounts() 15 + filteredAccounts() 26 (다른 페이지 보존 가능) / 비-bootstrap_admin 계정 detail panel 에 `adminPasswordResetBtn` "비밀번호 초기화" 노출.
- Trace: REQ-20260515-0003 ~ REQ-20260515-0010 → TASK-0061 → CHG-20260515-0003

## CHG-20260515-0002
- Date: 2026-05-15
- Summary: TASK-0060 (REQ-20260515-0002) 실제 접근 가능 DB 분석 기반 Product 시스템 프롬프트 작성 + Role `전 Product 공통` 프롬프트 작성 + runtime 누적 적용 fix.
- Files / Data:
  - `agent_memory.WebSystemPrompts`:
    - Product prompt upsert: `KR / 킹스레이드` (`dbgame,dblog,dbauth`), `MV / 마이크로볼츠` (`account_db,dev_1_1_1_20,have_00,log_v2,global_db`).
    - Role common prompt upsert: `pending`, `operator`, `admin`, `sales`, `dba` 각각 `Scope='role' AND ProductId IS NULL`.
  - `repo/unit/feature-0002-agent-core/src/agent_core.py`: Role `ProductId IS NULL` prompt 를 fallback 이 아니라 공통 누적 지침으로 조립하도록 변경.
  - `repo/unit/feature-0002-agent-core/tests/test_compose_system_prompt.py`: pinned/auto 모드 누적 적용 테스트 추가.
  - `repo/unit/feature-0003-agent-web-ui/docs/{FUNCTION,TASK,REVIEW,REPORT,TEST}.md` 및 feature-0002 문서 갱신.
- DB Analysis:
  - `KR`: `dbgame` 98 tables / 약 147만 rows, `dblog` 279 tables / 약 3929만 rows, `dbauth` 9 tables / 약 7977 rows. 주요 확인 범위: `dbgame.player` 2187 rows (`CreatedTime` 2026-04-07~2026-04-23), `dblog.battleend` 813,280 rows, `dblog.item` 12,656,848 rows, `dbauth.accountbasicinfo` 2187 rows.
  - `MV`: `account_db` 6 tables / 약 21.8만 rows, `dev_1_1_1_20` 62 tables / 약 12.6만 rows, `have_00` 50 tables / 약 2520만 rows, `global_db` 28 tables / 약 599 rows, `log_v2` DB 존재 + tables 0. 주요 확인 범위: `account_db.account` 242,973 rows, `have_00.player` 232,922 rows, `have_00.matchhistory` 8,006,486 rows (`rv_created_at` 2023-09-09~2026-05-11).
- Verification:
  - `python3 -m py_compile unit/feature-0002-agent-core/src/agent_core.py unit/feature-0003-agent-web-ui/src/app.py`
  - `python3 -m unittest unit/feature-0002-agent-core/tests/test_compose_system_prompt.py`
  - SQL readback: Product prompt 2건, Role common prompt 5건 content length 확인.
  - web 컨테이너 내부 `compose_system_prompt(product_id=1, role_id=16, product_mode="pinned")` 직접 조회로 Product context + Role common guidance 포함 확인.

## CHG-20260515-0001
- Date: 2026-05-15
- Summary: TASK-0059 (REQ-20260515-0001, **Major** §12.3 — 사용자 대화 routing 데이터 영역). "새 대화" 버튼 누른 후 첫 메시지가 신규 대화가 아닌 직전 active 대화로 routing 되던 lazy-create 결함 수정. frontend 의 신규 의도가 backend 로 전달되지 않아 빈 `conversation_id` 가 "session 초기화 후 직전 대화 이어받기" 와 구분 불가했던 갭을 명시적 `lazy_create` hint + `force_new` 분기로 닫는다. 인증/인가 모델 무변경.
- Files:
  - `repo/unit/feature-0003-agent-web-ui/src/static/app.js`:
    - `sendPrompt()` 의 askBody 에 `isLazyCreate=true` 일 때만 `lazy_create: true` hint 를 추가. 기존 대화 ask 경로는 hint 미포함 (의미 변경 0).
    - `loadConversations()` 의 `state.activeConversationId` 덮어쓰기를 `!state.pendingNewConversation` 가드 안으로 이동. pending 모드 race 시 사이드바 리스트만 갱신하고 active 보존 → 직전 대화로 복귀하던 회귀 차단.
  - `repo/unit/feature-0003-agent-web-ui/src/app.py`:
    - `_resolve_conversation_for_account` 시그니처에 `force_new: bool = False` kwarg 추가. requested_id 가 truthy 이면 force_new 무시 (의도 상호배타), 빈 문자열이면 `_repair_current_conversation(..., force_new=force_new)` 로 위임. 기존 `_repair_current_conversation` 의 force_new 동작 (line 1167 의 visible fallback 차단 + line 1172 의 신규 cid 생성 + `_assign_conversation_owner(force=True)`) 그대로 활용 — body 변경 없음.
    - `/api/ask` 의 빈 `request_conversation_id` 경로에서 `lazy_create_requested = bool(data.get("lazy_create"))` 추출 후 `_resolve_conversation_for_account(..., create_if_missing=True, force_new=lazy_create_requested)` 호출. hint 없는 legacy client (예: 첫 로그인 후 직전 대화 자동 이어받기 흐름) 는 force_new=False 로 기존 동작 유지.
- Trace: REQ-20260515-0001 → TASK-0059 → CHG-20260515-0001
- Verify: `python3 -m py_compile unit/feature-0003-agent-web-ui/src/app.py` / `node --check unit/feature-0003-agent-web-ui/src/static/app.js` / `bash bin/verify-completion.sh --pre-commit feature-0003-agent-web-ui`

## CHG-20260514-0001
- Date: 2026-05-14
- Summary: TASK-0058 (REQ-20260514-0001, **Critical** §12.3) 대화 공유 링크 기능 도입. anonymous accessible read-only view + 로그인 viewer 의 fork. 사용자 결정 6 항목 + codex outside voice review 의 blindspot 10 개 (B1-B2 blocking + R1-R10 recommended) 모두 plan 에 반영.
- Files:
  - `repo/unit/feature-0003-agent-web-ui/src/app.py`:
    - `PERMISSION_DEFINITIONS` 에 `conversation.share.create` (group="conversation") 추가 → catalog 33 → 34.
    - `SEED_ROLE_DEFINITIONS` 의 operator/sales permissions set 에 `conversation.share.create` 추가. admin 은 `set(PERMISSION_CODES)` 자동 포함.
    - `_ensure_seed_roles` admin 보정 list 에 `conversation.share.create` 추가 + operator/sales catchup INSERT IGNORE.
    - `_ensure_web_conversation_shares_schema(conn)` helper 신설 → `_ensure_web_tables` (slow path) + `_ensure_seed_catchup` (fast path) 양쪽에서 호출. fast path 에 `_ensure_permission_catalog(conn)` 추가로 신규 권한 hydrate.
    - `_optional_account(request, conn)` 헬퍼 신설 — anonymous endpoint 용 (쿠키 없으면 None).
    - `_fork_conversation_impl(conn, account, source_id, from_id)` 로 fork 본체 추출. 기존 `/api/fork_conversation` 은 helper 호출. share-token 경로는 read-gate 우회.
    - `/share/{token}` FileResponse route (admin 옆).
    - 신규 5 endpoint: POST `/api/conversations/{cid}/share`, GET `/api/conversations/{cid}/shares`, DELETE `/api/share/{share_id}`, GET `/api/public/share/{token}`, POST `/api/public/share/{token}/fork`. Token `secrets.token_urlsafe(32)` + UNIQUE 충돌 5 회 retry. revoke + view counter = 단일 race-free UPDATE.
  - `repo/unit/feature-0003-agent-web-ui/src/static/index.html`: chat 헤더 fork 버튼 옆에 `shareConversationBtn` 추가.
  - `repo/unit/feature-0003-agent-web-ui/src/static/app.js`:
    - `shareConversationBtn` DOM reference + `PERMISSION_LABELS` / `PERMISSION_DESCRIPTIONS` 매핑 추가.
    - 메시지 hover "여기까지 공유" 액션 + 헤더 share 버튼 visibility toggle + click handler.
    - `createConversationShare({anchorMessageId})` async — `/api/conversations/{cid}/share` 호출 + clipboard.writeText + toast.
  - `repo/unit/feature-0003-agent-web-ui/src/static/share.html` (신규): anonymous read-only view, `meta robots noindex,nofollow`, `share.css` 만 import (메인 styles.css 격리).
  - `repo/unit/feature-0003-agent-web-ui/src/static/share.css` (신규): minimal styling. `.share-sql` (dark `<pre>`), `.share-result-table`, fixed footer 사내 협업 고지.
  - `repo/unit/feature-0003-agent-web-ui/src/static/share.js` (신규): vanilla JS — token 추출 → fetch → 메시지 + meta.final_sql + meta.result_rows 렌더 → can_fork 시 fork 버튼.
  - `repo/unit/feature-0003-agent-web-ui/docs/FUNCTION.md`: §2 Goal REQ-20260514-0001 + §11 AC-0053~AC-0060.
  - `repo/unit/feature-0003-agent-web-ui/docs/TASK.md`: TASK-0058 + §2.1 Implementation Plan + PLAN-APPROVED 마커.
  - `repo/docs/SECURITY.md`: anonymous endpoint 2 곳 명시 + 외부 배포 시 IP 제한/비밀번호 보호 후속 cycle 권장.
  - `repo/docs/STATUS.md`: feature-0003 row 갱신.
- Verification:
  - `python3 -c "import ast; ast.parse(...)"` app.py OK.
  - `node --check` app.js / share.js OK.
  - 부트스트랩 idempotency 는 helper 패턴 (try/except pass + INSERT IGNORE + ON DUPLICATE KEY UPDATE).
  - Runtime 검증 (sales/admin 로그인 → 헤더 "공유" 버튼 → dialog 발급 → anonymous URL 접근 → revoke → 410) 은 후속 단계.

## CHG-20260512-0002
- Date: 2026-05-12
- Summary: TASK-0056 (REQ-20260512-0002, **Major** §12.3 — 작업 화면·관리 콘솔 권한 정렬 분리, AI 자율 commit/push 대상은 사용자 결정) 작업 화면 (`index.html` 권한 현황) 과 관리 콘솔 (`admin.html` 권한 grid) 의 권한 group 순서가 동일 `console→account→role→conversation→[product]→misc` 으로 묶여 있어, 화면 맥락(자기시점 / 관리자시점) 이 정반대인데도 두 곳 모두 admin 메타권한이 위로 노출되던 문제 fix. 화면별 2단 section (관리/운영/기타) 으로 분리, 작업 화면은 운영 권한이 위로 + 관리 권한은 보유 시만 묶음 형태로 뒤로. CONVENTIONS.md §10.6 정책 신설.
- Files:
  - `repo/docs/CONVENTIONS.md` §10.6 (화면별 권한 섹션·정렬 정책) 신설 — 화면별 section 순서 표, 정합 규칙 6 줄, 동적 권한 (`product.access.<key>`, `system_prompt.*`) 처리, 검증 한 줄.
  - `repo/unit/feature-0003-agent-web-ui/src/static/admin.js`:
    - 새 상수 `ADMIN_PERMISSION_SECTIONS` (관리/운영/기타 3 section 정의) 추가.
    - 새 함수 `sectionedGroupedPermissions(opts)` — `groupedPermissions()` 결과를 section 으로 묶고 빈 group/section 제외 + 미매핑 group 은 "기타" fallback.
    - `renderPermissionGrid` 가 outer section header (`.permission-section` + `.permission-section-head` + `.permission-section-title` + `.permission-section-description` + `.permission-section-groups`) 로 감싸고 inner `<details data-perm-group>` 들을 `sectionGroupsEl` 에 append 하도록 수정.
    - 기존 line 50 의 "backend `PERMISSION_GROUP_ORDER` (app.py) 와 순서 동기 필수" 주석은 실제로는 backend `PERMISSION_DEFINITIONS[*].group` 키 정합에 가까워 표현 정정.
  - `repo/unit/feature-0003-agent-web-ui/src/static/app.js`:
    - `PERMISSION_GROUP_ORDER` 에 `product` 그룹 추가 + `PERMISSION_GROUP_LABELS.product = "제품"` 추가 (작업 화면 측 누락 fix).
    - 새 상수 `WORK_SCREEN_PERMISSION_SECTIONS` (운영/관리/기타 3 section) 추가 — 관리자측과 정반대 순서.
    - `permissionGroupOf()` 가 `system_prompt.` 접두사를 `product` 그룹으로 명시 매핑 (app.py `system_prompt.manage.role.any` 의 `group: "product"` 와 정합).
    - `PERMISSION_LABELS` / `PERMISSION_DESCRIPTIONS` 에 `product.manage` / `system_prompt.manage.role.any` 항목 추가.
    - `buildPermissionPills(containerEl)` 가 WORK_SCREEN_PERMISSION_SECTIONS 의 2단 묶음 (`.perm-section-meta` + `.perm-section-meta-head` + `.perm-section-meta-title` + `.perm-section-meta-description` + `.perm-section-meta-groups`) 으로 렌더. section 안의 어느 group 권한도 보유하지 않으면 section 자체 미렌더 (관리 권한 묶음 자동 hide). 미매핑 group orphan 처리도 추가.
  - `repo/unit/feature-0003-agent-web-ui/src/static/styles.css`:
    - 작업 화면측: `.perm-section-meta`, `.perm-section-meta-head`, `.perm-section-meta-title`, `.perm-section-meta-description`, `.perm-section-meta-groups`. 관리 권한 묶음만 살짝 opacity/muted 처리.
    - 관리 콘솔측: `.permission-section`, `.permission-section-head`, `.permission-section-title`, `.permission-section-description`, `.permission-section-groups`. `data-perm-section="manage"` 는 살짝 파란 background, `"operate"` 는 살짝 녹색 background.
    - `.permission-grid/.override-grid { gap: 18px }` 로 increase (외부 section 들 간격), `.permission-section-groups > .permission-group + .permission-group { margin-top: 0 }` 로 gap 중첩 제거.
  - `repo/unit/feature-0003-agent-web-ui/src/static/admin.html`: styles.css / admin.js cache-bust slug `v=20260512-perm-sections`.
  - `repo/unit/feature-0003-agent-web-ui/src/static/index.html`: styles.css / app.js cache-bust slug `v=20260512-perm-sections`.
- Verification:
  - `node --check admin.js` 통과.
  - `node --check app.js` 통과.
  - DB schema / backend RBAC catalog / endpoint guard / system prompt assembly 변경 **0**. 본 cycle 은 frontend 렌더링과 project-level 컨벤션 문서만 수정 — 인가 모델 무영향.
  - 두 화면 모두 정렬은 frontend 상수 (`WORK_SCREEN_PERMISSION_SECTIONS` / `ADMIN_PERMISSION_SECTIONS`) 가 단일 정의처. 미매핑 group 은 "기타" section 으로 자동 fallback.
- Risks:
  - 백엔드에 새 group key 가 추가되는 경우 (예: 향후 `audit`, `integration` 등) 두 상수에 명시 매핑하지 않으면 "기타" 로 떨어진다. CONVENTIONS.md §10.6 의 정합 규칙으로 명시.
  - 작업 화면의 "관리 권한" section 자동 hide 는 사용자가 실제로 admin perm 을 한 개도 보유하지 않을 때만 적용 — admin 계정은 항상 표시됨. 일반 사용자는 관리 권한 section 자체가 없어지므로 시각적 단순화.
  - 시각 검증 (`make web` 기동 후 두 화면 비교 + 일반 사용자 / admin 계정 양 시점) 은 사용자 환경에서 진행 권고.

## CHG-20260508-0001
- Date: 2026-05-08
- Summary: TASK-0054 (REQ-20260508-0001) PR 흐름으로 main 동기화 — feat/adopt-external-anchor-v3.2.0-rc + issue/1-github-bootstrap 의 누적 작업을 두 개의 PR 로 main 에 머지. AI 자율 commit/push (§16.5).
- Files:
  - PR #2 (`feat/adopt-external-anchor-v3.2.0-rc` → `main`):
    - merge commit `eafe4c2` (admin merge, 72 commits / 137 files / +28320 / -9018)
    - 충돌 해결 commit `ae53965` — main 의 v3.0.0 마이그레이션과 본 브랜치의 v3.6.0 진화 conflict (10 files: AGENTS.md / CONTRIBUTING.md / unit/_template/docs/TASK.md / docs/{CODEBASE_MAP,LEARNINGS}.md / playbooks/{PB-0001~0004,README}.md) 을 §3.2 + §16.6 자율 해결 원칙에 따라 본 브랜치 본문 우선으로 통합.
  - PR #3 (`issue/1-github-bootstrap` → `main`):
    - merge commit `3fd4272` (admin merge, 단일 commit `38702cd`)
    - 변경: `.github/workflows/{ai-execute,ai-review,ai-triage}.yml` 의 `runs-on` 을 `[self-hosted, linux]` 로 + `anthropics/claude-code-action@v1` 제거 + 로컬 `claude -p ...` CLI 직접 호출.
  - 본 cycle 의 `unit/feature-0003-agent-web-ui/docs/REPORT.md` §3 에 Git 동기화 결과 양식 (§16.5 Step 6) 으로 PR #2 + PR #3 의 머지 commit hash, 충돌 해결 사유, CI fail 인프라 이슈 요약을 누적 기록.
- Verification:
  - `gh pr view 2 --json state,mergedAt,mergeCommit` → `MERGED`, mergeCommit `eafe4c25af3eda75e2f74cd9350dfc3c9531fad9`.
  - `gh pr view 3 --json state,mergedAt,mergeCommit` → `MERGED`, mergeCommit `3fd4272fdc2aaa902df50c8cb03431a7a99c3855`.
  - `git show origin/main:.github/workflows/ai-execute.yml | grep runs-on` → `runs-on: [self-hosted, linux]` (운영 정합성 회복).
  - 직전 `bin/verify-completion.sh --post-commit feature-0003-agent-web-ui` PASS (6/6).
- Risks:
  - feat 브랜치는 PR #2/PR #3 의 merge commits + ae53965 만큼 main 보다 behind 3 — feat 에서 추가 작업 시 catch-up 필요 (사용자 결정).
  - main 의 self-hosted runner 환경에서 `repo-agent` 이미지 누락 (selfhosted-runtime-smoke fail) 은 별도 인프라 후속 작업으로 분리. PR #2 / PR #3 자체의 정책 위반은 아님.
  - CI 의 `policy-contract` (브랜치 이름 `feat/*` 가 `issue/<번호>-<short-slug>` 자동화 계약 외) + `ai-review` (heredoc EOF delimiter 워크플로 버그) 는 본 PR 본문과 무관한 인프라 이슈로 admin merge 정당화. 정책 자동화 자체는 향후 cycle 에서 보강 필요.

## CHG-20260507-0001
- Date: 2026-05-07
- Summary: TASK-0053 사용자 follow-up 2 항목 수정 — (1) Account/Role 의 pending 상태 row UI 뒤틀림 버그 fix, (2) 제품별 접근 카드 list 를 권한 grid 의 'product' 그룹 details 안으로 이전. AI 자율 commit/push.
- Files:
  - [unit/feature-0003-agent-web-ui/src/static/styles.css](../src/static/styles.css)
    - Issue 1 fix: `.admin-list-row.has-pending::before { content: ""; }` 의 placeholder rule 이 CSS Grid container 의 `::before` 가 4번째 grid item 으로 참여해 cb 를 column 2 로 밀고 chips 를 row 2 col 1 로 wrap 시키던 버그 fix. pseudo-element 자체를 제거하고, `.has-pending` 에 `border-color: rgba(37,99,235,.35)` 만 적용해 시각적 표시 유지 (`pendingDot` "•" 이 이미 title 안에서 indicator 역할).
    - 신규 `.admin-product-card-list-embedded` 스타일 (margin-top + padding-top + dashed border-top) — 권한 grid 'product' 그룹 details 안에 inline 배치될 때 정적 권한과의 시각적 구분.
  - [unit/feature-0003-agent-web-ui/src/static/admin.js](../src/static/admin.js)
    - Issue 2: `buildRoleProductCardList(role, disabled, opts={})` / `buildAccountProductOverrideList(account, disabled, opts={})` 시그니처에 `opts.embed` 추가. embed=true 면 별도 section title 생략 (부모 details summary 의 "제품" 라벨과 중복 회피), hint 메시지 단축.
    - `renderRoleDetail`: 기존 `paneEl.appendChild(productCards)` 를 `permWrap.querySelector('details[data-perm-group="product"]')` 가 있으면 그 안에 append, 없으면 fallback 으로 paneEl 에 append 하는 분기로 변경. embed 옵션 전달.
    - `renderAccountDetail`: 동일 패턴으로 `overrideWrap` 안의 product 그룹 details 에 productOverrides append.
  - [unit/feature-0003-agent-web-ui/src/static/admin.html](../src/static/admin.html)
    - cache-bust `v=20260507-row-fix-embed`.
- Verification:
  - (a) `node --check admin.js` PASS / `make web` 재배포.
  - (b) **Issue 1 DOM 분석 (수정 전 → 수정 후)**: sales role 에 pending 적용 후 `getBoundingClientRect`. 수정 전 — `cb x=70 y=30` (column 2 — 잘못), `main x=175 y=9` (column 3 — 잘못), `chips x=11 y=73` (row 2 col 1 — wrap). 수정 후 — `cb x=11 y=30` (column 1 ✓), `main x=34 y=9` (column 2 ✓), `chips x=270 y=26` (column 3 ✓), 모두 row 1 에 정상 배치. row height 102 → 72 (정상 높이).
  - (c) **Issue 2 DOM 검증**: `details[data-perm-group="product"]` 안에 `.admin-product-card-list-embedded` 1 개 + `.admin-product-card` 3 개 (KR / TT / 전 Product 공통) 정상 배치 확인. 사용자가 "제품" 그룹 collapse 시 정적 권한과 product 카드가 함께 접힘.
  - (d) **시각 확인** (스크린샷): pending 상태 sales row 가 다른 role row 와 동일한 패턴 (cb / 아바타 / name+meta / active 칩) 으로 표시. "제품" 그룹 펼치면 정적 권한 + 안내 hint + product 카드 (체크박스 + product key) inline 노출.
- Risks:
  - **CSS pseudo-element grid item 회귀 위험**: 향후 다른 `::before`/`::after` 에 `content: "..."` 가 추가될 때 같은 버그 재발 가능. 방어책: grid container 의 pseudo-element 는 `position: absolute` 로 grid flow 에서 제외하거나 `display: none`. 본 수정은 placeholder rule 자체를 제거.
  - **embed=true 모드의 hint 텍스트 차이**: 부모 details 안에 들어가면 footer 정보가 중복되지 않도록 hint 를 단축. UX 일관성 손실 우려는 적음 — footer "모두 적용" 메시지가 이미 다른 곳에서 노출됨.
  - **Account detail 의 product card 도 동일 처리**: override grid 의 product 그룹 details 안에 inline 배치. 사용자가 "제품" collapse 시 product 별 override select 도 함께 접힘.
- Range: styles.css +6 lines (rule 제거 + 신규 embedded 변형 + has-pending border), admin.js +~25 lines (renderRoleDetail/renderAccountDetail 의 분기 + buildRoleProductCardList/buildAccountProductOverrideList 의 embed opts), admin.html cache-bust 2 lines. 신규 파일 0.
- Notes: 본 fix 는 TASK-0053 의 후속 보완 — 사용자 직접 보고 + 시각 의도 ("제품 접기에 따라 출력") 반영. 정책 주체 (Product) 결정은 변경 없음. CSS Grid 의 ::before pseudo-element 가 grid item 으로 참여한다는 사실은 흔한 함정 — LEARNINGS.md 등재 권고.

## CHG-20260506-0027
- Date: 2026-05-06
- Summary: TASK-0053 (REQ-20260506-0006, Major §12.3) 신규 제품 default 정책 토글 + 권한 grid 의 product sub-catalog + Role/Account detail 의 product-카드 통합. TASK-0052 완료 직후 사용자 follow-up. **사용자 in-cycle 설계 전환 (2026-05-06)**: 정책 주체를 Role 이 아닌 **Product** 로 변경 — 운영자가 product 생성 시점에 토글로 결정하는 것이 더 자연스럽다는 의도. AI 자율 commit/push.
- Files:
  - [unit/feature-0003-agent-web-ui/src/app.py](../src/app.py)
    - **Phase A — `WebProducts.DefaultRoleAccess` 정책 토글 (product 주체)**:
      - `_ensure_dynamic_permissions_schema(conn)` 에 `ALTER TABLE WebProducts ADD COLUMN DefaultRoleAccess TINYINT(1) NOT NULL DEFAULT 1` 추가 (idempotent ALTER, 기존 운영 데이터 호환).
      - `_ensure_product_access_permissions(conn)` (catchup backfill) 의 role grant SQL 이 product 의 `DefaultRoleAccess` 값에 따라 분기 — true 면 모든 role grant, false 면 grant 안 함.
      - `POST /api/admin/products` 의 body 에 `default_role_access` 수용, INSERT 시 컬럼 set + transaction 안 backfill 분기에 동일 적용.
      - `PATCH /api/admin/products/{id}` 에 `default_role_access` 수용 (기존 product 정책 변경 가능).
      - `_list_products` SELECT 와 응답 dict 에 `default_role_access` 필드 추가.
      - `WebRoles.DefaultProductAccess` 관련 코드 모두 제거 — `_load_role_by_id` / `_list_roles` SELECT/GROUP BY/dict 에서 컬럼 삭제, `admin_update_role` 의 body 수용 + UPDATE 컬럼 제거. 컬럼 자체는 destructive DROP 회피 차원에서 잔존 (다음 cleanup cycle 에서 DROP COLUMN).
  - [unit/feature-0003-agent-web-ui/src/static/admin.js](../src/static/admin.js)
    - **Phase A frontend**: Product detail 에 토글 1 row 추가 ("신규 역할 자동 접근"). Product detail 의 `merged` 객체에 `default_role_access` 추가, `setProductMetaPending` 핸들러 + `applyAllPending` 의 productMeta PATCH body 에 포함, `describePatchKeys` 라벨 추가. **Role detail 의 토글은 제거** (이전 설계의 잔재 — Role-side 의 default_product_access 흐름 전부 삭제: mergedRole/setRolePending/applyAllPending/startNewRole/describePatchKeys 모두 정정).
    - **Phase B — 권한 grid 의 dynamic 권한 분리**: `groupedPermissions(opts={excludeDynamic})` 옵션 추가, `dynamicProductPermissions()` 헬퍼 신설. `renderPermissionGrid(..., opts={excludeDynamic})` 옵션 전달. Role detail 과 Account detail 의 grid 호출이 `excludeDynamic: true` 로 dynamic `product.access.<key>` 권한들을 별도 product subcatalog 로 분리.
    - **Phase B/C — product subcatalog cards**: `buildRoleProductCardList(role, disabled)` 신설 — product 별 collapsible card (헤더에 access 토글, 본문에 role-scope system prompt textarea fixedProductId=Number(product.id)). "전 Product 공통" generic card 도 마지막에 추가 (fixedProductId=0). `buildAccountProductOverrideList(account, disabled)` 신설 — product 별 flat card 에 override select (allow/deny/inherit) 만 표시 (account scope prompt 는 profile drawer 영역).
    - **Role/Account detail 재구성**: `renderRoleDetail` 의 기존 단일 `buildSystemPromptEditor` (역할 시스템 프롬프트 Role Scope) 호출이 `buildRoleProductCardList` 로 교체. `renderAccountDetail` 에서 권한 override grid 다음에 `buildAccountProductOverrideList` 추가. permission 변경 onChange 핸들러는 dynamic 권한들의 기존 상태 (subcatalog 에서 변경된 값) 를 union 으로 보존하도록 수정.
  - [unit/feature-0003-agent-web-ui/src/static/styles.css](../src/static/styles.css)
    - `.admin-product-card-list` / `.admin-product-card[open]` / `.admin-product-card-head` / `.admin-product-card-toggle` / `.admin-product-card-info` / `.admin-product-card-body` / `.admin-product-card-flat` / `.admin-product-card-generic` 스타일 추가. 토큰 (`--border-subtle` / `--text-muted`) 사용.
  - [unit/feature-0003-agent-web-ui/src/static/admin.html](../src/static/admin.html)
    - cache-bust `v=20260506-c5-product-cards`.
- Verification:
  - (a) `python3 -m py_compile` PASS / `node --check admin.js` PASS / `make web` 재배포.
  - (b) Schema: `DESC WebProducts` 에 `DefaultRoleAccess tinyint(1) NOT NULL DEFAULT 1` 컬럼 추가 확인. 기존 product (KR/TT) 모두 1 유지 (기존 운영 호환). `WebRoles.DefaultProductAccess` (이전 시도) 컬럼은 잔존하나 어떤 SQL 도 참조하지 않음 — 다음 cleanup cycle 에서 DROP COLUMN.
  - (c) `/api/admin/roles` 응답에서 `default_product_access` 필드 제거 확인 (admin role keys 에서 미존재). `/api/admin/products` 응답에 `default_role_access` 필드 노출.
  - (d) **Phase A E2E smoke (product-driven)**: 신규 product `DE` 를 `default_role_access=false` 로 생성 → DB 직접 확인: 6 role 모두 `has_de_grant=NO` ✓. admin effective `product.access.de=False` ✓. 비교 신규 product `JP` 를 `default_role_access=true` 로 생성 → 6 role 모두 `has_jp_grant=YES` ✓. **정책 주체가 product 라는 의도 정확히 반영**.
  - (e) **Phase B/C DOM smoke** (browse): Role detail 진입 시 토글 2 개만 ("활성 / 기본 가입 역할") 노출 — 신규 제품 자동 접근 토글은 Role detail 에서 제거됨, 대신 Product detail 로 이동. 권한 grid `details[data-perm-group="product"]` 안에 `product.manage` / `system_prompt.manage.role.any` 만 (dynamic 코드 제외) ✓. `.admin-product-card-list` 1 개 + `.admin-product-card` 3 개 (KR + TT + 전 Product 공통) 정상.
- Risks:
  - **호환성 영향 0**: `DefaultRoleAccess DEFAULT 1` + 기존 product 들 모두 1 으로 backfill 되어 기존 운영 동작 유지. 운영자가 product 생성 시 토글을 명시적으로 끌 때만 신규 product 의 자동 grant 차단 발효.
  - **이전 시도의 잔재**: `WebRoles.DefaultProductAccess` 컬럼이 DB 에 잔존 — destructive DROP COLUMN 회피. 어떤 SQL 도 참조하지 않으므로 동작 영향 0. 다음 cleanup cycle 에서 정리 (또는 운영자가 직접 `ALTER TABLE WebRoles DROP COLUMN DefaultProductAccess` 가능).
  - **권한 grid 의 dynamic 분리로 인한 caller-update 의존성**: Role/Account detail 의 onChange 핸들러가 `existingDynamic` union 보존 안 하면 product subcatalog 의 토글 변경이 grid 의 onChange 호출 시점에 무효화됨. union 처리 코드 추가. 검증: subcatalog 토글 변경 후 grid 의 정적 권한 토글 변경 → footer 카운트 양쪽 다 반영.
  - **buildRoleProductCardList 가 buildSystemPromptEditor 의 fixedProductId 인자에 의존**: 기존 함수 signature 보존 (TASK-0051 cycle 부터). `fixedProductId=0` 는 generic "Product 무관" 케이스 — backend `_load_system_prompt` 의 `ProductId IS NULL` 매칭과 일치.
  - **계정 detail 의 product card 는 prompt textarea 미포함**: account scope prompt 는 profile drawer 영역 (AC-0014). admin 콘솔에서는 access override 만 product 별 카드로.
- Range: app.py +~60 lines (WebProducts schema ALTER + product API/admin_update_product 의 default_role_access + 정책-driven backfill 분기 + role API 의 default_product_access 제거), admin.js +~250 lines (Phase B groupedPermissions/dynamicProductPermissions + Phase C buildRoleProductCard*/buildAccountProductOverride* + Role/Account detail 재구성 + Product detail 토글), styles.css +~70 lines, admin.html cache-bust.
- Notes: 본 cycle 은 사용자 in-cycle 설계 전환의 결과 — 처음 작성한 Role-side 정책을 Product-side 로 정정. 운영 시나리오: 운영자가 product 를 만들 때 토글로 "이 제품은 모든 role 에 기본 grant" / "명시 grant 만" 결정. 한 번 결정되면 그 product 의 권한 분배 정책으로 고정 (PATCH 로 변경은 가능하나 신규 product 의 backfill 시점에만 적용). TASK-0052 의 8 endpoint guard 는 변경 없음 (보안 표면 동일).

## CHG-20260506-0026
- Date: 2026-05-06
- Summary: TASK-0052 Phase 1B/1C/1D + Phase 2 검증 — 계정·역할 → 제품 권한 상속/override 모델 본체 도입. Codex outside voice 의 9 개 finding 모두 통합 + admin_update_account RoleId 손실 pre-existing 버그 fix. AI 자율 commit/push 모드.
- Files:
  - [unit/feature-0003-agent-web-ui/src/app.py](../src/app.py)
    - **Phase 1B (DB schema + catalog source 전환 + caller-update + 트랜잭션)**:
      - `_resolve_permission_catalog(conn=None)` body 를 DB-driven 으로 교체 — conn 이 주어지면 정적 PERMISSION_DEFINITIONS + `WebPermissions WHERE IsDynamic=1` union 반환. graceful fallback (column missing / DB error → static).
      - `_product_permission_code(product_key)` 헬퍼 신설 — `product.access.<key.lower()>` namespace 변환.
      - `_ensure_dynamic_permissions_schema(conn)` 헬퍼 신설 — `WebPermissions ADD COLUMN IsDynamic / ProductId + INDEX` idempotent ALTER. slow path (`_ensure_web_tables`) + fast path (`_ensure_seed_catchup`) 양쪽에서 호출.
      - `_ensure_product_access_permissions(conn)` 헬퍼 신설 — 모든 WebProducts 에 대해 `INSERT IGNORE INTO WebPermissions (Code, Label, ..., IsDynamic=1, ProductId)` + 모든 WebRoles 에 grant `INSERT IGNORE INTO WebRolePermissions (RoleId, PermissionId)`. D2-A 호환성 backfill, idempotent. backfill 결과를 stderr 에 1 회 기록 (운영 transparency, Codex Claim 5).
      - bootstrap 흐름 (`_ensure_web_tables` + `_ensure_seed_catchup`) 에 `_ensure_dynamic_permissions_schema` + `_ensure_product_access_permissions` 호출 추가.
      - `_decorate_account_rows` / `_ensure_management_survivor_for_role_change` / `admin_update_account` (override + permissions 빌드) / `_list_roles` / `_load_role_by_id` / `admin_create_role` / `admin_update_role` 의 7 callsite 가 `_resolve_permission_catalog(conn)` 결과 (`catalog_codes` / `catalog_map`) 를 명시적으로 전달하도록 caller-update.
      - `_account_permissions(account)` 가 cached map 을 그대로 dict 변환해 dynamic codes (e.g. `product.access.kr`) 가 silently drop 되지 않도록 수정 (기존: `for code in PERMISSION_CODES` iteration → 정적 코드만).
    - **Phase 1B (product CRUD 트랜잭션 — Codex Claim 2)**:
      - `POST /api/admin/products` 가 `conn.autocommit=False` + 명시적 commit/rollback 안에서 product row + WebPermissions row + WebRolePermissions backfill (모든 role grant) 한 트랜잭션 처리.
      - `DELETE /api/admin/products/{id}` 가 in_use guard 통과 후 명시적 트랜잭션 안에서 WebSystemPrompts → WebProductDatabases → WebRolePermissions(IsDynamic=1 ProductId 참조) → WebAccountPermissionOverrides(동일) → WebPermissions → WebProducts cascade 정리.
    - **Phase 1B/1C (`_account_has_product_access` 헬퍼)**:
      - 신설. int / ProductKey 문자열 / int-string 모두 수용. int 입력 시 conn 으로 ProductKey 조회 후 `product.access.<key.lower()>` permission lookup.
    - **Phase 1C (G1-G8 8 endpoint guards — Codex Claim 3 + 4)**:
      - G1 `PATCH /api/conversations/{cid}/product` pinned 모드 — 권한 없으면 403.
      - G2 `POST /api/new_conversation` body `product_id` — 권한 없으면 403 (명시 입력) 또는 auto 강등 (default 채움 분기).
      - G3 `POST /api/ask` body `product_id` hint — 동일 패턴.
      - G4 `POST /api/ask` 기존 conversation 의 `product_id_for_run` 시점 — Codex Claim 3 의 직접 해소. 권한 회수 후 pinned 대화 재실행 시 403 + `이 대화의 제품 접근 권한이 회수되었습니다...` 안내.
      - G5 `POST /api/fork_conversation` source product 상속 + `product_mode` 'auto' 보존 fix (Codex Claim 4 fork 버그). source 'auto' 가 fork 후 'pinned' 으로 변질되던 회귀 차단. fork 대상 계정이 source product 접근 권한 없으면 auto 강등.
      - G6 `_save_account_product_pref` defense-in-depth (signature 에 `account` 추가) — caller-level 가드 누락 시 fallback 보호망.
      - G7 `GET /api/auth/me/system-prompt?product_id=<X>` — 권한 없으면 403.
      - G8 `PUT /api/auth/me/system-prompt` body `product_id` — 동일 패턴.
    - **pre-existing 버그 fix (Phase 1C 작업 중 발견)**:
      - `admin_update_account` (`PATCH /api/admin/accounts/{account_id}`) 가 body 에 `role_id` 미명시 시 `target.get("role")` (항상 None) 으로 fallback 해 next_role_id=0 으로 떨어져 PATCH 마다 RoleId 를 0 으로 덮어쓰던 회귀. `target.get("role_id")` 직접 조회로 fix. 본 fix 가 없으면 admin 의 permission_overrides 변경만으로도 admin role 손실 → 권한 lockout.
  - [unit/feature-0003-agent-web-ui/src/static/admin.js](../src/static/admin.js)
    - **Phase 1D**: `PERMISSION_GROUP_ORDER += "product"` (`["console","account","role","conversation","product","misc"]`), `PERMISSION_GROUP_LABELS["product"] = "제품"`. backend `app.py` 와 동기 필수. 기존 `renderPermissionGrid` 가 자동으로 product group 에 정적 + 동적 코드들 (`product.manage`, `system_prompt.manage.role.any`, `product.access.<key>`) 모두 노출.
  - [unit/feature-0003-agent-web-ui/src/static/admin.html](../src/static/admin.html)
    - cache-bust 갱신 (`v=20260506-c5-product-perms`).
- Verification:
  - (a) `python3 -m py_compile unit/feature-0003-agent-web-ui/src/app.py` 통과.
  - (b) `node --check unit/feature-0003-agent-web-ui/src/static/admin.js` 통과.
  - (c) `make web` 재배포 + `repo-web-1 Recreated/Started`.
  - (d) bootstrap 후 stderr `[TASK-0052 Phase 1B catchup] product access backfill: 7 permission/role-permission rows added` 메시지 확인 (1 perm row + 6 role grants).
  - (e) `/api/admin/permissions` count 33 → 34 (`product.access.kr` 추가) → POST FR 후 35 → DELETE FR 후 34 복귀. cascade 정합성 확인.
  - (f) bootstrap_admin 의 effective permissions 에 `product.access.kr=true`, FR 생성 후 `product.access.fr=true`, FR 삭제 후 사라짐. D2-A 호환성 backfill 동작.
  - (g) Phase 2 P0 negative HTTP smoke (deny override 적용 후): T01 PATCH conv→KR (G1) 403, T02 new_conversation KR (G2) 403, T07 GET sysprompt?product_id=1 (G7) 403, T08 PUT sysprompt body product_id=1 (G8) 403. cleanup 후 admin permissions 34/34 회복 확인.
  - (h) admin_update_account RoleId 보존 fix 검증: PATCH `{"permission_overrides":{"product.access.kr":"deny"}}` → role 'admin' 보존, 33/34 true (KR 만 deny).
  - (i) G3/G4 직접 HTTP smoke 는 model validation (`gpt-5-mini` not allowed) 단계에서 차단되어 정적 코드 검증으로 대체 — 코드 경로가 G1/G2 와 동일 패턴 (`_account_has_product_access` 직접 호출).
- Risks:
  - **D2-A 호환성 backfill 의 보안 의미**: pending/sales/operator 등 모든 role 이 KR 에 default grant. 운영자가 권한 회수가 필요한 (role × product) 조합에 admin 콘솔 deny override 를 추가해야 secure-by-default 효과 (Codex Claim 5 명시).
  - **product_key immutability**: ProductKey 변경 시 권한 코드 namespace drift. ProductKey 는 사실상 immutable 로 정책 — 변경은 delete + recreate 경유. 같은 key 의 과거 override 는 cascade 로 사라짐 (briefing §F5).
  - **Phase 2 P2 부분 (DOM/UX)**: `/api/sessions/me` filter (effective products 만 반환), 사이드바 chip option filter (FE permission map 기반) 는 본 turn 에 미포함 — frontend 렌더링은 이미 Phase 1B 의 effective permission map 으로 자동 갱신되므로 별 cycle 에서 보강. 보안 경계는 G1-G8 가드가 server-side 에서 보장.
  - **`/api/sessions/me` 정보 노출 (Codex Claim 6 D4 변경)**: end-user `/api/session` 응답에서 effective products 만 반환하도록 split 은 본 turn 에 미적용 — 별도 작은 cycle 로 후속. 보안 임팩트는 mutation 가드가 이미 보장하므로 P0 아님 (briefing §6 NOT in scope 와 일치).
- Range: app.py +~480 lines (helper 5 신설 + 7 caller-update + 8 가드 + 트랜잭션 wrapper + bug fix), admin.js +2 lines (group order + label), admin.html +0 (cache-bust 만), 신규 파일 0.
- Notes: 본 turn 의 변경은 **Critical 등급 인증/인가 구조 변경** (AGENTS.md §12.3) 이지만 사용자가 AI 자율 commit/push 권한을 명시 부여 (2026-05-06) 함에 따라 진행. Phase 1A (commit 4dd1d0a) 와 본 cycle (Phase 1B/1C/1D + Phase 2) 가 함께 C5 본체를 완성. **Phase 2 의 P2 항목 (sessions/me filter, end-user FE chip filter) 은 정보 노출 강화 차원의 follow-up 으로 별 cycle**.

## CHG-20260506-0025
- Date: 2026-05-06
- Summary: TASK-0052 (REQ-20260506-0005, Critical §12.3 인증/인가 구조 변경) Phase 1A — RBAC engine catalog 인자화 refactor. Codex Claim 1 (정적 PERMISSION_CODES 가정에 5 hot path hardwired) 의 1 단계 해소. 동작 변경 0, plumbing 만 추가. Phase 1B (DB-driven catalog + product 권한 backfill) 진입을 위한 surface 준비.
- Files:
  - [unit/feature-0003-agent-web-ui/src/app.py](../src/app.py)
    - L18~19: `from collections.abc import Iterable` import 추가
    - L290~ 신규 `_resolve_permission_catalog(conn=None) -> tuple[list, set, dict]` 헬퍼 — Phase 1A 시점은 정적 `(PERMISSION_DEFINITIONS, PERMISSION_CODES, PERMISSION_DEFINITION_MAP)` 그대로 반환. Phase 1B 에서 conn 인자 사용해 WebPermissions IsDynamic=1 row union 으로 교체 예정.
    - `_empty_permission_map(catalog_codes=None)` 시그니처 확장 — None 이면 정적 PERMISSION_CODES 사용 (기존 동작).
    - `_apply_permission_overrides(base_codes, overrides=None, *, catalog_codes=None)` 시그니처 확장 — catalog_codes 가 주어지면 그 catalog 기반으로 map build.
    - `_validate_permission_codes(codes, *, catalog_codes=None)` 시그니처 확장.
    - `_normalize_override_payload(payload, *, catalog_codes=None, catalog_map=None)` 시그니처 확장.
    - `_permission_catalog_payload(*, catalog=None)` 시그니처 확장 — caller 가 명시적 catalog 전달 가능.
    - `/api/admin/permissions` 엔드포인트 (L5761) — 단일 위치를 신규 plumbing 경로 (`_resolve_permission_catalog(conn) → _permission_catalog_payload(catalog=...)`) 로 전환. Phase 1A 검증용. 다른 callsite 는 Phase 1B 에서 caller-update.
- Verification:
  - (a) `python3 -m py_compile unit/feature-0003-agent-web-ui/src/app.py` 통과.
  - (b) `make web` EXIT=0 (provenance metadata file race 우회 정상) + `repo-web-1 Recreated/Started`.
  - (c) `docker exec repo-web-1 grep -c "_resolve_permission_catalog\|catalog_codes" /app/web/app.py` → 17 hits, 신규 코드 deploy 확인.
  - (d) bootstrap_admin login → `/api/admin/permissions` HTTP 200, count=33 codes (이전과 동일). 첫 3: `console.access`/`console.manage`/`account.read`. 마지막 3: `conversation.finalize.any`/`product.manage`/`system_prompt.manage.role.any` — 정확히 이전 catalog 와 일치.
- Risks:
  - **Backward-compat default 검증된 callsite**: `_apply_permission_overrides` (3 callsites at L854/3681/5403), `_validate_permission_codes` (2 callsites at L5545/5624), `_normalize_override_payload` (1 callsite at L5395) 모두 catalog_codes/catalog_map kwarg 미전달 — 기본값 None → 정적 PERMISSION_CODES 사용 → 기존 동작 유지. 회귀 0.
  - **L3518/3570 `for code in PERMISSION_CODES`** (role payload `permissions` map) 는 Phase 1A 에서 변경 없음. Phase 1B 에서 dynamic 코드 추가 시 caller 가 catalog 를 전달하도록 update.
  - **Container deploy 검증**: `/api/admin/permissions` 만 신규 plumbing 사용. 정적 결과와 동일함 HTTP smoke 로 확인.
- Range: app.py +~30 lines (helper + 5 시그니처 확장 + 1 callsite 전환). 신규 파일 0 개.
- Notes: Phase 1A 는 briefing §12 권고 ("Phase 1A 단독 deploy 가능") 따라 분리 commit 권장. Phase 1B 가 conn-driven catalog 도입 + product 권한 backfill 을 담당. 본 turn 은 Phase 1B 진입을 위한 plumbing 만.

## CHG-20260506-0024
- Date: 2026-05-06
- Summary: TASK-0048 후속 fix — backend `_repair_current_conversation` 호출처 5 곳의 `create_if_missing=_account_has_permission(...)` 자동 생성 분기를 모두 비활성화. 사용자 보고 회귀 ("대화 삭제 시 새 대화가 그대로 남는 이슈") 의 근본 원인은 `/api/delete_conversation` 응답 `current` 필드가 backend 의 자동 생성 분기로 또 다른 빈 cid 를 발급해서 frontend 가 그것을 active 로 채택해 사이드바에 다시 등장하던 것. lazy 정책의 일관성을 backend 전 경로에 적용한다.
- Files:
  - [unit/feature-0003-agent-web-ui/src/app.py](../src/app.py)
    - `_build_conversations_payload` (L3412 부근): `create_if_missing=can_create` 분기 제거, `create_if_missing=False` 고정. 후속 재호출 단계도 단일화.
    - `/api/session` 응답 조립 (L3737 부근): `create_if_missing=False`.
    - `/api/history` 의 conv resolver (L4470 부근): `create_if_missing=False`.
    - `/api/delete_conversation` pending 케이스 (L4651 부근): `create_if_missing=False` + 회귀 사유 주석.
    - `/api/delete_conversation` 일반 케이스 (L4662 부근): `create_if_missing=False`.
    - `/api/ask` 의 lazy creation (L3851): `create_if_missing=True` 그대로 보존 — 사용자가 명시적으로 메시지를 보낼 때만 row 가 만들어지는 경로 유지.
- Verification:
  - `python3 -m py_compile unit/feature-0003-agent-web-ui/src/app.py` 통과.
  - `make web` EXIT=0 + `repo-web-1 Recreated/Started` 후 새 코드 deploy.
  - 시나리오 검증 (HTTP API):
    1. `/api/conversations` 호출 → row delta=0 (이전엔 빈 대화 자동 생성). items=46 정상 listing.
    2. `/api/session` 호출 → row delta=0.
    3. `/api/new_conversation` 으로 빈 대화 1건 생성 (delta=+1, backward-compat 경로) → 그 cid 를 `/api/delete_conversation` 으로 삭제 → 응답 `{"deleted":"...","current":""}`, row delta=-1. **이전엔 응답의 current 가 새 자동 생성된 cid 였고 frontend 가 그것을 active 로 채택해 사이드바에 또 빈 대화가 등장**. fix 후엔 current="" 라 frontend 가 "대화를 선택하세요" 상태로 떨어진다.
- Risks:
  - 마지막 대화를 삭제한 사용자는 backend 가 자동으로 새 대화를 만들어주지 않는다 — frontend 가 "대화를 선택하세요" 헤더 + 사이드바 empty-state 를 표시하고 사용자가 명시적으로 "새 대화" 버튼을 눌러야 한다. 이는 TASK-0048 lazy 정책의 의도된 결과이며 사용자 보고 회귀의 직접 해결책.
  - 다른 호출처(`/api/use_conversation`, `/api/cancel`, `/api/finalize` 등) 에서 `_resolve_conversation_for_account` 의 default 가 이미 `False` 라 영향 없음.

## CHG-20260506-0023
- Date: 2026-05-06
- Summary: TASK-0051 (REQ-20260506-0004) 관리 콘솔 일괄 저장 정책 회복 + 메타데이터 4 스키마 항상 노출 + DB 목록 라이브 enum — 인라인 save 버튼 3 종(`프롬프트 저장` / `제품 정보 저장` / `DB 목록 저장`) 제거 후 footer `모두 적용` 단일 commit 흐름으로 통합. 메타데이터 4 종(`information_schema`/`mysql`/`sys`/`performance_schema`) 을 회색 disabled chip 으로 강제 노출(REV-20260422-0006 정책 시각화). 자유 텍스트 chip 입력을 `GET /api/admin/databases/available` 라이브 enum 기반 picker 로 교체. C5(계정·역할 → 제품 권한 상속/override) 는 다음 cycle 분리(plan-eng-review 후 진행 권고).
- Files:
  - [unit/feature-0003-agent-web-ui/src/app.py](../src/app.py)
    - L5897~ 신규 `GET /api/admin/databases/available` 엔드포인트 추가. `_account_has_permission(account, "console.access")` 게이트 후 `_open_memory_connection(database=None)` 으로 `SHOW DATABASES` 실행. 결과를 `metadata_schemas`(고정 4 종 + `present` flag) / `user_schemas`(메타·`agent_memory`·`MEMORY_DB`·정규식 위반 제외 + 정렬) 로 분리해 반환. 모듈 상수 `_DATABASES_AVAILABLE_METADATA` / `_DATABASES_AVAILABLE_INTERNAL` / `_DATABASES_AVAILABLE_NAME_RE` 추가.
  - [unit/feature-0003-agent-web-ui/src/static/admin.js](../src/static/admin.js)
    - `adminState` 에 `availableDatabases` 와 `pending.{productMeta, productDatabases, systemPrompts}` 3 buckets 추가. `METADATA_SCHEMAS`/`INTERNAL_SCHEMAS` 상수 + `systemPromptPendingKey()` 헬퍼 추가.
    - `pendingChangeCount()` 에 신규 buckets 합산. `setProductMetaPending` / `setProductDatabasesPending` / `setSystemPromptPending` / `getSystemPromptPending` 헬퍼 신규.
    - `refreshPendingUI()` 의 `commitBarDetail` 에 신규 카테고리 (제품 정보 / 제품 DB / 프롬프트) 표시.
    - `cancelAllPending()` 이 신규 buckets + `productDbDraft` 까지 clear.
    - `loadAdminData()` 가 `Promise.all` 에 `/api/admin/databases/available` 추가 + 제품/역할/계정 삭제 시 stale pending entry GC.
    - `renderProductDetail()`: `saveMetaBtn` / `saveDbBtn` 두 버튼 제거. name/desc/active/default/sort 입력 변경 → `setProductMetaPending`. chip wrap 상단에 메타 4 종 locked chip 강제 prepend(× 없음, `is-locked` 클래스 + `항상 접근` 라벨). 자유 텍스트 input 을 `<select>` picker 로 교체 — 옵션은 user_schemas 에서 메타·내부·이미 등록된 schema 제외. chip × 클릭 / picker 추가 시 `setProductDatabasesPending`. dbHint 끝에 메타 4 종 정책 안내 한 줄 추가.
    - `buildSystemPromptEditor()`: `saveBtn` / `clearBtn` 제거. textarea 위에 안내 메시지 ("변경사항은 하단 '모두 적용' 버튼으로 일괄 저장됩니다") 추가. textarea `input` 이벤트 → `setSystemPromptPending`. `refresh()` 가 pending entry 우선 사용해 사용자 입력 보존.
    - `applyAllPending()` 6 단계로 확장 — 기존 accounts/roles/newRoles 뒤로 productMeta(PATCH `/api/admin/products/{id}`) → productDatabases(PUT `/api/admin/products/{id}/databases`) → systemPrompts(PUT `/api/admin/system-prompts`) 순서. 실패는 기존 `failures` 배열에 합류.
    - `renderDashboard()` `dashboardPendingList` 에 productMeta / productDatabases / systemPrompts 3 카테고리 row 추가. `describePatchKeys` 에 `is_default`/`sort_order` 라벨 추가.
  - [unit/feature-0003-agent-web-ui/src/static/styles.css](../src/static/styles.css)
    - `.admin-chip.is-locked` (회색 + `cursor: not-allowed` + opacity 0.85), `.admin-chip-locked-hint` (소형 라벨), `.admin-db-picker-row`, `.admin-db-picker` (select + disabled 상태) 추가. 기존 `--text-muted` / `--border-subtle` 토큰 사용.
  - [unit/feature-0003-agent-web-ui/src/static/admin.html](../src/static/admin.html)
    - cache-bust query 를 `v=20260506-batch-commit` 로 갱신 (styles.css / admin.js 양쪽).
- Verification:
  - (a) `python3 -m py_compile unit/feature-0003-agent-web-ui/src/app.py` 통과.
  - (b) `node --check unit/feature-0003-agent-web-ui/src/static/admin.js` 통과.
  - (c) `grep -n "프롬프트 저장\|제품 정보 저장\|DB 목록 저장\|saveMetaBtn\|saveDbBtn\|clearBtn"` admin.js 에서 0 hit (3 개 인라인 save 버튼 + 그 핸들러 변수 모두 제거 확인).
  - (d) `grep -c "/api/admin/databases/available" admin.js app.py` → 양쪽 1 hit (FE / BE 한 쌍).
  - (e) 컨테이너 재빌드(`make web`) + UX smoke 는 사용자 환경에서 진행 예정 (재빌드 후 cache-bust 가 반영돼야 신규 admin.js 가 브라우저에 로드됨).
- Range: backend 1 파일 +60 lines, FE admin.js ~+200 lines (인라인 save 핸들러 제거 + pending 통합 + locked chip + picker), styles.css +44 lines, admin.html cache-bust 2 lines.
- Notes: REV-20260422-0006 의 메타 4 종 bypass 정책은 시각화만 변경했고 backend tool-level (`tools.py` `_METADATA_SCHEMAS`) 은 손대지 않았다 — agent 실행 동작에는 영향 없음. C5(계정·역할 → 제품 권한 상속/override) 는 신규 테이블(`WebRoleProductAccess`/`WebAccountProductAccessOverrides`) 마이그레이션 + RBAC override 모델(TASK-0024) 충돌 검토 + `compose_system_prompt` product 조회 경로 영향 분석이 필요해 별 cycle 로 분리. 진입 전 `/plan-eng-review` 권고. 권한 게이트 약함(`console.access` 만으로 DB 목록 enum 가능)에 대한 위협 모델: enum 결과는 schema 이름 / 존재 여부에 한정되며 row 데이터 노출은 없고, 실제 등록은 `product.manage` 권한 게이트의 PUT `/api/admin/products/{id}/databases` 가 그대로 유지된다 (`agent_memory` / `mysql.user` 등 민감 schema 자체는 user_schemas 에서 제외).

## CHG-20260506-0022
- Date: 2026-05-06
- Summary: TASK-0050 (REQ-20260506-0003) `make web` 의 docker compose v5.1.1 + buildx v0.31.1 provenance metadata file race 회피 — Makefile 에 `dc-build SERVICE=...` reusable 가드 타깃 추가, `web` 타깃을 build/up 분리.
- Files:
  - `Makefile`
    - `.PHONY` 목록에 `dc-build` 추가
    - `dc-build` 타깃 신설 — `$(DC_QUIET) build $(SERVICE)` 호출 + 임시 로그 캡처. EXIT≠0 + 로그에 `compose-build-metadataFile` 문자열 포함 시에만 EXIT=0 으로 정규화 (다른 빌드 오류는 그대로 전파). `SERVICE` 인자 검증 포함.
    - `web` 타깃을 `up -d --build web` 단일 호출에서 `$(MAKE) -s dc-build SERVICE=web` + `$(DC_QUIET) up -d --no-build web` 의 2 단계로 분리. image 를 미리 만들어 두고 컨테이너 교체만 별도 단계로 수행.
- Verification:
  - `make web` EXIT=0, 로그에 `[make] note: docker compose v5.1.1+buildx v0.31.1 의 provenance metadata file race 우회 — web image 빌드 OK, compose EXIT=1 무시` 출력. `Container repo-web-1 Recreate/Recreated/Started` 후 `Web UI (HTTPS): https://localhost:18080` 노출.
  - `docker exec repo-web-1 grep -n PENDING_CONV_SENTINEL /app/web/static/app.js` 으로 TASK-0048 의 새 코드가 컨테이너에 반영됨을 확인.

## CHG-20260506-0021
- Date: 2026-05-06
- Summary: TASK-0049 (REQ-20260506-0002) 누적된 빈 대화 일괄 정리 — `bin/cleanup-empty-conversations.sh` 추가 + 운영 데이터 1회 적용.
- Files:
  - `bin/cleanup-empty-conversations.sh` (신규, executable)
    - dry-run 기본 + `--execute` 명시 시 DELETE
    - `--owner-account-id <N>` 으로 계정 한정 가능 (정수 정규식 검증)
    - `--keep-recent-min <분>` 으로 최근 N분 이내 대화 보호 (default 5)
    - `AgentMemoryKv.last_status='processing'` 인 대화 보호 (실행 중 ask race)
    - SQL 주입 방지: 모든 인터폴레이션 변수 정수 정규식 검증, AgentCoreConversations / AgentMemoryMessages collation 차이는 `COLLATE utf8mb4_unicode_ci` 명시 변환
    - DB password 는 `.env` 의 `DB_PASSWORD` 에서 읽어 git 추적 대상이 아닌 값으로 처리
- Verification:
  - dry-run: `would_delete=42, oldest=2026-04-15, newest=2026-04-30 10:41:10` (5분 이내 row 1건 보호 확인).
  - execute: `88 conversations / 42 empty / 46 non-empty → 46 conversations / 0 empty / 46 non-empty` (방금 만든 backward-compat 검증 row 도 5분 보호 cutoff 통과해 정리됨).
  - 보호 검증: `processing` last_status 를 갖는 대화는 dry-run sample 에 포함되지 않음 (별도 query 로 0 건 확인).

## CHG-20260506-0020
- Date: 2026-05-06
- Summary: TASK-0048 (REQ-20260506-0001) "새 대화" 생성 시점을 lazy 화 — 버튼 클릭 시 client-side pending state 만 표시하고, 첫 메시지 전송 시 `/api/ask` 의 lazy creation path 가 실제 row 를 만들도록 전환. 기존에 사용자가 새 대화 버튼만 누르고 메시지를 보내지 않으면 `AgentCoreConversations` 에 빈 row 가 누적되던 문제를 신규 row 측에서 차단.
- Files:
  - `unit/feature-0003-agent-web-ui/src/static/app.js`
    - `state` 에 `pendingNewConversation: false` + 모듈 상수 `PENDING_CONV_SENTINEL = "__pending__"` 추가
    - `isCurrentConvBusy()` 가 pending 모드에서 sentinel 도 검사
    - `renderConversationList()` 가 pending 모드면 빈 `state.conversations` 에서도 그룹을 그리고 "내 대화" 그룹 상단에 placeholder (`conv-item is-own is-active is-pending`) prepend. 기존 `renderGroup` 시그니처에 `prependFn` optional 인자 추가
    - `renderConversationHeader()` 가 pending 일 때 "새 대화" + "첫 메시지를 입력하면 대화가 만들어집니다." 표시
    - `beginPendingConversation()` 신설 — backend 호출 없이 `state.pendingNewConversation=true`, `activeConversationId=""`, `messages=[]` + 사이드바/헤더/composer 리렌더 + 입력란 포커스
    - `selectConversation()` 시작에 pending 자동 종료 분기
    - `sendPrompt()` 에 lazy create 분기:
      - `isLazyCreate = isPending || !state.activeConversationId` 판정
      - busy sentinel `PENDING_CONV_SENTINEL` 사용 + lazy create 시 progress polling 시작 보류
      - `/api/ask` body 에 `product_mode` / `product_id` hint 첨부 (사용자 직전 의도 보존)
      - 응답에 `conversation_id` 가 있으면 `state.pendingNewConversation=false` + `state.activeConversationId=newCid` 채택
      - lazy create 단계의 ask 실패는 attach/resume 다이얼로그 대신 재시도 안내 토스트 (cid 발급 여부가 client 에 불확실)
    - `newConversationBtn.click` 핸들러를 `createConversation()` → `beginPendingConversation()` 로 교체. 기존 `createConversation()` 함수는 다른 호출처 호환을 위해 보존
  - `unit/feature-0003-agent-web-ui/src/app.py`
    - `/api/ask` — `request_conversation_id` 가 비어 lazy 생성된 경로에서 body 의 `product_mode` / `product_id` hint 를 normalize 후 `AgentCoreConversations.product_id/product_mode` 셋업 + `_save_account_product_pref` 호출. `request_conversation_id` 명시 경로에는 무시 (TASK-0047 의 PATCH race 가드 단독 진실 보존). hint 적용 실패는 ask 자체를 막지 않고 default fallback.
  - `unit/feature-0003-agent-web-ui/src/static/index.html` — cache-bust `v=20260429-product-selector` → `v=20260506-pending-conv` (styles.css, app.js 양쪽).
  - `unit/feature-0003-agent-web-ui/src/static/styles.css` — `.conv-item.is-pending` 1 selector 그룹 추가 (border-dashed + faded text + cursor:default). 토큰만 사용(`--text-2`, `--text-muted`, `--border`).
- Verification:
  - `python3 -m py_compile unit/feature-0003-agent-web-ui/src/app.py` 통과 예정 (재빌드 단계).
  - `node --check unit/feature-0003-agent-web-ui/src/static/app.js` 통과 예정.
  - frontend 흐름 inspection: 새 대화 버튼 → backend round trip 0회, placeholder 표시. 첫 메시지 → `/api/ask` 1회 (lazy create + product hint 적용). 응답 `conversation_id` 채택 후 `refreshWorkspace`.

## CHG-20260430-0019
- Date: 2026-04-30
- Summary: TASK-0047 후속 — Playwright QA 실행 중 발견된 마이그레이션 누락 회귀(R-09 closed) + race-guard 검증 자동화.
- Files:
  - `unit/feature-0003-agent-web-ui/src/app.py` `_runtime_tables_available` — 신규 컬럼(`product_mode`, `ProductPrefMode`, `ProductPrefPinnedId`) 존재 여부도 probe 에 포함. errno 1054 (Unknown column) 도 1146 과 함께 False 반환 분기로 처리해 `_ensure_web_tables` idempotent ALTER 들이 자동 트리거되도록 함. **버그**: 기존 배포에서 새 컬럼 마이그레이션이 fast-path 로 우회되던 회귀를 제거.
  - `repo/.gstack/qa-reports/qa-product-selector.cjs` (신규) — Playwright 28-check QA spec. 검증 항목: AUTH/SESSION/BUST/MARKUP/CHIP/LABEL/PATCH/NEWCONV/UI/HYDRATE/RACE/CONSOLE. SQL 주입은 stdin 파이프로 nested-quote 회피.
  - `repo/.gstack/qa-reports/qa-product-selector-result.json` (생성) — 28/28 PASS, healthScore=100, console.error=0.
  - `repo/.gstack/qa-reports/screenshots/product-01..04.png` (생성) — 진단 스크린샷.
- Verification:
  - `docker compose build --no-cache web` (이전 `--build` 가 stale layer cache 로 신규 코드를 누락했음 — `--no-cache` 가 필수임을 학습).
  - 컬럼 검증: `SHOW COLUMNS FROM AgentCoreConversations LIKE 'product_mode'` → `product_mode varchar(8) NO '' pinned ''`. `SHOW COLUMNS FROM WebAccounts LIKE 'ProductPref%'` → 2 row.
  - QA spec 28/28 PASS:
    - 마크업/cache-bust/select 옵션/data-mode 동기화/localStorage 미러
    - PATCH 4 케이스(pinned 정상 / auto 정상 / pinned w/o product_id → 400 / 비존재 product_id → 400)
    - new_conversation 2 케이스(auto / pinned)
    - UI 인터랙션 2 케이스(select pinned ↔ auto)
    - 신규 auto 대화 hydrate
    - **PATCH race guard**: `AgentMemoryKv.last_status='processing'` 상태에서 PATCH → 409, 정리 후 → 200.
    - console.error 0.

## CHG-20260429-0018
- Date: 2026-04-29
- Summary: TASK-0047 — Product Selector 칩(사이드바) + Auto 모드 진입 UX. `product_mode` 컬럼/`WebAccounts.ProductPref*`/PATCH endpoint/agent_core auto 분기 추가, 한글 "상품" → "제품" 일괄 치환.
- Files:
  - `unit/feature-0002-agent-core/src/agent_core.py` — `compose_system_prompt(... , product_mode='pinned'|'auto')` 분기 추가, `run_agent`/`_run_agent_core` 시그니처에 `product_mode` 전달.
  - `unit/feature-0003-agent-web-ui/src/app.py` — DDL 2 컬럼 추가(AgentCoreConversations.product_mode, WebAccounts.ProductPrefMode/PinnedId), 헬퍼 4종(`_normalize_product_mode`, `_load_account_product_pref`, `_save_account_product_pref`, `_load_conversation_product`, `_conversation_is_processing`), `/api/session` 응답 확장(`product_pref`, `conversation_product`), `/api/new_conversation` body 확장(`mode`, pref upsert), `/api/ask` 분기(mode='auto' → product_id None + allowed_schemas=[]), 신규 `PATCH /api/conversations/{cid}/product` (race 가드 포함).
  - `unit/feature-0003-agent-web-ui/src/static/index.html` — 사이드바 헤더에 `<div class="product-chip-wrap">` + caption + `<select id="productSelect">` 신설. cache-bust `?v=20260429-product-selector`.
  - `unit/feature-0003-agent-web-ui/src/static/styles.css` — `.product-chip-wrap`/`.product-chip-caption`/`.product-chip[data-mode]`/`.product-chip-dot`/`.product-chip-select` 신설, mobile ≤720px 분기.
  - `unit/feature-0003-agent-web-ui/src/static/app.js` — state 3-필드 분리 (productMode/pinnedProductId/activeProductId), `renderProductOptions`/`renderProductChip`/`readProductPrefFromLocal`/`writeProductPrefToLocal`/`applyProductHydration`/`setActiveProduct` 신규, `initializeWorkspace`/`refreshWorkspace`/`selectConversation`/`createConversation`/`renderComposer`/`initialize` 흐름에 hydrate + lockout + select change 바인딩 추가, `PRODUCT_PREF_LS_KEY` 상수.
  - `unit/feature-0003-agent-web-ui/src/static/admin.html`, `unit/feature-0003-agent-web-ui/src/static/admin.js` — "상품" → "제품" 일괄 치환.
  - `unit/feature-0003-agent-web-ui/docs/TASK.md` — TASK-0047 entry.
  - `unit/feature-0003-agent-web-ui/docs/BRIEFING-product-selector-v1.md` (신규) — 차후 검증 항목(R-01..R-16) + 사람 확인 결정사항(D-01..D-05).
- Notes:
  - **사용자 검토 없이 agent team 4 인(UX/Frontend Architect/Backend Engineer/QA-Flow Validator) 합의 + Codex CLI 교차검증** 으로 진행됨. 운영 반영 전 D-01..D-05 결정과 R-01..R-16 검증 필요.
  - 마이그레이션은 idempotent(`try/except`) — 기존 행은 default `'pinned'` 로 backfill, NULL product_id 는 ask 진입 시 기존 default 채움 경로 보존.
  - "상품" → "제품" 치환은 사용자 가시 텍스트만. 코드 식별자(`Product`/`product_id`/`WebProducts`/`ProductKey`) 보존.

## CHG-20260326-0001
- Date: 2026-03-26
- Summary: Web UI 앱과 정적 자산을 기능 단위 구조로 이관
- Files: src/app.py, src/static/*
- Notes: 코어 로직은 별도 feature에 유지

## CHG-20260414-0002
- Date: 2026-04-14
- Summary: 메인 워크스페이스를 작업 중심 콘솔 레이아웃으로 재개편하고 로그인/드로어/빠른 액션 UX를 재정의
- Files: src/static/index.html, src/static/styles.css, docs/TASK.md, docs/REPORT.md, docs/TEST.md
- Notes: 기존 기능 ID와 JS 결합은 유지하고, 시각 체계와 정보 배치를 전면 수정

## CHG-20260415-0003
- Date: 2026-04-15
- Summary: 계정/권한 체계를 실제 인증 모델로 교체하고, 대화 소유권과 관리자 화면 기준으로 Web UI를 전면 재구성
- Files: src/app.py, src/static/index.html, src/static/styles.css, src/static/app.js, src/static/admin.html, src/static/admin.js, docs/TASK.md, docs/REPORT.md, docs/TEST.md, ../.env
- Notes: `WebUsers`/`WebKeywords` 런타임 경로를 제거하고 `WebAccounts`/`WebAuthSessions`/`AgentCoreConversations.owner_account_id`를 기준으로 동작하도록 변경. 로컬 LLM 게이트웨이 미가용 시 false positive를 막기 위해 연결 가능 여부를 세션 응답에 반영

## CHG-20260415-0004
- Date: 2026-04-15
- Summary: App-Shell 기준 메인 레이아웃, 프로필 드로어, 병렬 대화 UX, 관리자 콘솔 사용성을 강화
- Files: src/app.py, src/static/index.html, src/static/styles.css, src/static/app.js, src/static/admin.html, src/static/admin.js, docs/TASK.md
- Notes: 사이드바 하단 프로필 트리거와 드로어 구조를 추가했고, `state.busyConversations`로 대화별 요청 상태를 분리했다. `/api/auth/me` 비밀번호 변경 엔드포인트, Admin 검색/필터/페이지네이션이 함께 추가되었다.

## CHG-20260415-0005
- Date: 2026-04-15
- Summary: 프로필 드로어를 3탭 구조로 재편하고 API Vault를 통합했으며, UI 정책/학습 문서를 최신화
- Files: src/static/index.html, src/static/styles.css, src/static/app.js, docs/AGENTS.md, docs/TASK.md, ../../../docs/LEARNINGS.md
- Notes: 계정별 설정을 탑바에서 제거하고 프로필 드로어의 `계정 / 보안 / API Vault` 탭으로 이동했다. 로그아웃 시 드로어 및 인증 폼 상태 초기화 규칙을 코드와 문서에 동시에 반영했다.

## CHG-20260415-0006
- Date: 2026-04-15
- Summary: 내장 Local LLM 소유 구성을 제거하고 외부 provider 소비 계약으로 전환
- Files: src/app.py, src/static/index.html, src/static/app.js, docs/TASK.md, docs/REPORT.md, docs/TEST.md, ../.env, ../../../../docker-compose.yml, ../../../../Makefile
- Notes: 현재 repo는 더 이상 Ollama/local-llm-gateway를 직접 기동하지 않는다. `LOCAL_LLM_API_BASE` 연결 가능 여부만 세션과 오류 메시지에 반영한다.

## CHG-20260416-0007
- Date: 2026-04-16
- Summary: Web UI 권한 모델을 RBAC + account override로 cutover하고 관리자 콘솔을 Accounts/Roles 2영역으로 재구성
- Files: src/app.py, src/static/index.html, src/static/app.js, src/static/admin.html, src/static/admin.js, src/static/styles.css, docs/TASK.md, docs/REPORT.md, docs/TEST.md, ../../../docs/STATUS.md
- Notes: role명 휴리스틱을 제거하고 `permission code + ownership`만으로 권한을 판정한다. `WebPermissions`/`WebRoles`/`WebRolePermissions`/`WebAccountPermissionOverrides`가 단일 정본이며, legacy `Role`/`Can*` 컬럼은 마이그레이션 원본으로만 남긴다. `/api/clear_memory`는 410으로 유지하고, 계정 삭제는 soft delete + 세션 폐기로 고정했다.

## CHG-20260421-0008
- Date: 2026-04-21
- Summary: 대화 사이드바의 내 계정/타 계정 대화 구분 하이라이트·정렬과 대화/말풍선 단위 fork(복제) 기능 도입
- Files: src/app.py, src/static/index.html, src/static/app.js, src/static/styles.css, docs/TASK.md, docs/FUNCTION.md, docs/REPORT.md, docs/REVIEW.md
- Notes: 사이드바는 `내 대화` / `타 계정 대화` 2 그룹으로 분할 렌더되고 내 대화는 primary 좌측 바 + 틴트, 타 계정 대화는 owner 뱃지를 강조한다. 말풍선 user 메시지에 `is-own-message` / `is-other-message` 톤 분리와 `나 (<username>)` / `<owner_username>` 라벨을 적용했다. 신규 `POST /api/fork_conversation` 은 `conversation.create` 권한과 원본 대화의 read 권한을 동시에 요구하며, 원본 `topic`(앞에 `[Fork] ` 접두사)과 메시지(internal 제외)를 `AgentMemoryMessages` 에 `CreatedAt` 보존 + `MetaJson.forked_from_*` 추가로 복제한다. 프론트엔드는 헤더 `대화 복사`(전체 복제), 말풍선 hover 액션 `여기서 분기`(부분 복제) 버튼을 제공한다.

## CHG-20260421-0009
- Date: 2026-04-21
- Summary: System Prompt Depth 3 계층(Product→Role→Account) + Product 단위 DB 접근 화이트리스트 도입
- Files: ../feature-0002-agent-core/src/agent_core.py, ../feature-0002-agent-core/src/modules/tools.py, src/app.py, src/static/admin.html, src/static/admin.js, src/static/index.html, src/static/app.js, src/static/styles.css, docs/TASK.md, docs/FUNCTION.md, docs/REPORT.md, docs/REVIEW.md
- Notes: 신규 테이블 `WebProducts` / `WebProductDatabases` / `WebSystemPrompts` + `AgentCoreConversations.product_id` 컬럼 추가. `_runtime_tables_available` probe list 에 신규 3 테이블 포함해 기존 배포 재진입 시 자동 마이그레이션. 신규 permission `product.manage` / `system_prompt.manage.role.any` 를 `admin` 역할에 기본 부여, seed 로 ProductKey=`KR` + DB(`dbgame`/`dblog`/`dbauth`) 생성. `agent_core.compose_system_prompt` 가 base prompt 뒤로 `## PRODUCT CONTEXT` → `## ROLE GUIDANCE` → `## ACCOUNT PREFERENCES` 블록을 순차 append. `modules/tools.py` 에 모듈 전역 `_ACTIVE_SCHEMA_ALLOWLIST` + `set_/clear_active_schema_allowlist()` + `_whitelist_violation()` 을 두고, 모든 DB 도구 핸들러가 호출 직전 스키마 참조를 검사(`execute_sql` 은 `schema.table` 정규식 추출). `run_agent` 는 `allowed_schemas` kwarg 을 받아 try/finally 로 whitelist 를 세팅/복원하는 얇은 래퍼 + 본문 `_run_agent_core` 로 분리. 보안 수정: `_whitelist_violation` 에서 `_SYSTEM_SCHEMAS` 우회를 제거해 `mysql`/`performance_schema`/`sys`/`agent_memory` 직접 참조가 whitelist 로 차단되도록 했다. 관리 콘솔은 `계정 카테고리` / `상품 카테고리` 그룹 구분선 + `상품 (Products)` 탭(Product CRUD + 접근 DB chip 편집 + Product scope prompt 편집기) 을 추가, Roles detail 에 Role scope prompt 편집기(Product 드롭다운 포함), 프로필 드로우에 `프롬프트` 탭(Account scope) 을 추가. 신규 API: `GET/POST/PATCH/DELETE /api/admin/products`, `PUT /api/admin/products/{id}/databases`, `GET/PUT /api/admin/system-prompts`, `GET/PUT /api/auth/me/system-prompt`. 세션 응답에 `products` / `default_product_id` 포함. `/api/new_conversation` / `/api/fork_conversation` / `/api/ask` 가 대화 `product_id` 를 해석해 `run_agent` 에 `product_id`/`role_id`/`account_id`/`allowed_schemas` 를 전달.

## CHG-20260422-0011
- Date: 2026-04-22
- Summary: agent_core `OpenAI()` 초기화에 per-call `timeout` + `max_retries` 를 적용하고 TASK-0034 러너 `ASK_TIMEOUT_SEC` 을 서버 `run_timeout_sec` 이상으로 정렬
- Files: ../feature-0002-agent-core/src/agent_core.py, tests/task0034_runner.py, docs/TASK.md, docs/REPORT.md, docs/MODIFY.md
- Notes: TASK-0034 Q4/Q5 실패 원인 분석에서 확인된 근본 원인 1(agent_core 의 `OpenAI(**client_kwargs)` 가 timeout 파라미터 없이 초기화돼 LLM 호출이 무한 대기) 과 근본 원인 2(러너 600s < 서버 900s 로 클라이언트가 먼저 포기해 좀비 스레드 발생) 를 동시 대응. 1) `agent_core.py:26~32` import 에 `AGENT_OPENAI_MAX_RETRIES` 추가, `agent_core.py:1134~1139` `client = OpenAI(**client_kwargs)` 를 `OpenAI(**client_kwargs, timeout=max(5,int(AGENT_TIMEOUT_SEC)), max_retries=max(0,int(AGENT_OPENAI_MAX_RETRIES)))` 로 확장. 현재 `.env` 값 기준 `timeout=300s`, `max_retries=0`. 2) `tests/task0034_runner.py:52~56` `ASK_TIMEOUT_SEC=600.0` 을 `ASK_TIMEOUT_SEC=960.0` 으로 인상하고 산정 근거 주석(`max(AGENT_TIMEOUT_SEC*3, AGENT_EARLY_FINALIZE_MS/1000)=900`) 추가. 검증: (a) `python3 -m py_compile` 통과, (b) `docker compose up -d --force-recreate web` 후 신규 컨테이너(StartedAt=2026-04-22T01:02:40Z) 기동, `docker exec grep` 으로 `timeout=max(5` 와 `AGENT_OPENAI_MAX_RETRIES` 반영 확인, `modules.config` import 시 `AGENT_TIMEOUT_SEC=300`/`AGENT_OPENAI_MAX_RETRIES=0` 확정, (c) bootstrap_admin 로그인 후 신규 대화로 `gpt-5.4-mini` 모델 `/api/ask` 한 턴 실행 — HTTP 200, wall=5s, steps_count=1, `list_schemas` + `SELECT FROM information_schema.schemata` 정상 실행.

## CHG-20260422-0010
- Date: 2026-04-22
- Summary: (문서화 전용) `/api/progress` 폴링 루프의 `setInterval` → 순번 기반 `setTimeout` + AbortController + 적응형 주기 리팩터 사후 리뷰 · 학습 기록
- Files: docs/TASK.md, ../../docs/LEARNINGS.md, docs/MODIFY.md
- Notes: 코드 변경 없음. TASK-0036 커밋(27127b9) 에 번들됐지만 commit message 에 언급되지 않은 폴링 리팩터를 TASK-0037 로 분리해 설계·검증·학습 내용을 사후 문서화한다. 검증: (a) `grep -c "setInterval" src/static/app.js` = 0, (b) 5 개 적응형 상수(`PROGRESS_FETCH_TIMEOUT_MS=4000`, `PROGRESS_POLL_ACTIVE_MS=1200`, `PROGRESS_POLL_IDLE_MS=3000`, `PROGRESS_POLL_HIDDEN_MS=10000`, `PROGRESS_POLL_ERROR_MS=8000`) 모두 `scheduleProgressPolling`/`pollProgress` 본문에서 실제 참조, (c) 서버 `/api/progress` (app.py:4381~4426) 가 `client_run_id` 파라미터를 수용하고 서버 run_id 와 불일치 시 `next_after_step=0` 으로 리셋 (line 4405-4406), (d) `curl -sk -b cookie https://127.0.0.1:18080/api/progress?conversation_id=&client_run_id=STALE` 가 HTTP 200 + `{steps, status, status_at, step_count, run_id, conversation_id}` 스키마를 반환. `docs/LEARNINGS.md` 에 `LRN-20260422-0011 장시간 작업 폴링 5원칙(순번 기반 setTimeout 체인 + AbortController + 요청당 timeout + document.hidden 감지 + 서버측 delta with client_run_id)` 을 추가.

## CHG-20260422-0014
- Date: 2026-04-22
- Summary: 클라이언트 타임아웃 시 대화 지속 복구 경로 도입 — 서버 read-only 상태/결과 엔드포인트 2종 + 브라우저 복구 다이얼로그 + test runner attach 분기 (TASK-0041)
- Files: src/app.py, src/static/app.js, tests/task0034_runner.py, docs/TASK.md, docs/MODIFY.md, docs/REPORT.md, docs/FUNCTION.md, docs/REVIEW.md, ../../docs/LEARNINGS.md
- Notes: 사용자 요청(2026-04-22) — "클라이언트 타임아웃이 나타날 경우 해당 대화를 사용자 판단하에 지속적으로 처리할 수 있는 방법" 에 대응. 에이전트 작업자 스레드는 `asyncio.to_thread` 로 HTTP 연결과 독립적으로 실행되므로, 클라이언트(httpx/브라우저/proxy)가 ReadTimeout 으로 끊겨도 백엔드에서 계속 완료까지 진행한다. 이 자원을 회수할 read-only 경로가 없어 기존엔 결과가 유실됐다. `src/app.py` 에 `_ASK_TERMINAL_STATUSES={done,error,canceled}` / `_ASK_SUCCESS_STATUSES={done,canceled}` 상수와 `_load_run_meta_kv(conn, conversation_id)` 단일 쿼리 KV loader, `_build_ask_status_snapshot(conn, conversation_id)` 스냅샷 빌더, `GET /api/ask_status` (1-shot, `conversation.read.own/any` 권한) 과 `GET /api/ask_result` (long-poll `wait<=60s`, deadline/0.5s interval, terminal 시 assistant/steps 전문, 타임아웃 시 `{timeout:true}`) 2 엔드포인트를 추가. `/api/ask` 슬롯풀(WEB_PARALLEL_LIMIT=6) 과 분리되어 attach 가 새로운 실행을 시작시키지 않는다. `src/static/app.js` 에 `ASK_ATTACH_POLL_WAIT_SEC=45` / `ASK_ATTACH_MAX_TOTAL_SEC=1800` 상수, `fetchAskStatus`/`showTimeoutRecoveryDialog`(3 버튼 모달: 요청 취소/즉시 답변/계속 기다리기, Escape 로 dismiss) / `attachAndWaitForResult` (long-poll 루프, run_id 고정, terminal 시 `refreshWorkspace`) 를 추가했고, `sendPrompt()` 의 `apiFetch("/api/ask",...)` 를 try/catch 로 감싸 실패 + `is_processing=true` 이면 다이얼로그 → 사용자 선택에 따라 `/api/cancel`/`/api/finalize`/attach 로 분기한다. `initializeWorkspace()` 끝에 boot-time auto-attach: 페이지 로드 시 현재 대화가 서버에서 처리 중이면 자동으로 busy 상태 + progress polling + attach 를 재개한다. `tests/task0034_runner.py` 에 `ATTACH_TIMEOUT_SEC=960.0` / `ATTACH_POLL_WAIT_SEC=45` 상수, `_steps_from_attach(meta)` 헬퍼, `_attach_run(client, cid, msg, t0)` 함수(ask_status → ask_result long-poll 반복)를 추가했고, 기존 `httpx.ReadTimeout` 분기가 `{"error": "client-read-timeout"}` 을 반환하는 대신 `_attach_run` 으로 이어받아 `attached_after_timeout=True, attach_verdict="succeeded-via-attach"|"attach-status-<status>"` 메타와 함께 turn 기록을 정상 작성한다. 검증: (a) `python3 -m py_compile` 3 파일 통과, (b) `node --check static/app.js` JS 문법 OK, (c) `make web` 재빌드/재기동 → 새 sha256 이미지 반영 + `/api/ask_status` / `/api/ask_result` 401 응답으로 라우팅 확인, (d) terminal 상태 대화에 대한 `/api/ask_status` + `/api/ask_result` 가 38ms 이내 snapshot/assistant 반환 확인, (e) `python3 tests/task0034_runner.py --target api --only Q4,Q5` 재수행. 보안: `/api/ask_status`/`/api/ask_result` 는 read-only 이며 기존 `conversation.read.own/any` 권한 모델 재사용 — 새로운 공격 표면 추가 없음. 범위: 서버 1 파일 약 190 줄, 프론트 1 파일 약 230 줄, 테스트 1 파일 약 95 줄.

## CHG-20260422-0013
- Date: 2026-04-22
- Summary: SQL schema whitelist 정규식을 context-aware 2 단계 스캐너로 재작성 — `alias.column` 오탐으로 합법 SQL 이 차단되던 TASK-0036 회귀 제거 (TASK-0040)
- Files: ../feature-0002-agent-core/src/modules/tools.py, docs/TASK.md, docs/MODIFY.md, docs/REPORT.md, docs/REVIEW.md, ../../docs/LEARNINGS.md
- Notes: 기존 `_SCHEMA_TABLE_REF_RE = r"\`?([A-Za-z_]\w*)\`?\s*\.\s*\`?([A-Za-z_]\w*)\`?"` 는 SQL 문맥 구분 없이 모든 `x.y` 패턴을 `schema.table` 로 간주했다. `SELECT bb.BattleType, be.Star FROM dblog.t bb JOIN dblog.u be ON be.a = bb.a` 같은 alias.column 토큰이 전부 schema 후보로 수집되어 `_whitelist_violation` 이 Product whitelist=`{dbauth,dbgame,dblog}` 에서 `be`/`bb` 불허로 판정 → TASK-0034 Q4 재수행의 모든 턴이 `BLOCKED_SCHEMAS=bb,be` 로 실패했다. 수정: `_SCHEMA_TABLE_REF_RE` 를 제거하고 `_TABLE_LIST_RE`(`FROM`/`JOIN` 키워드 뒤 ~ 다음 절 키워드 `ON|WHERE|GROUP BY|ORDER BY|HAVING|LIMIT|UNION|JOIN|FROM|;|)|$` 전까지 lookahead) + `_INNER_REF_RE`(그 구간 내부에서 `schema.table` 만 추출) 2 단계 스캐너로 재작성. SELECT 절/WHERE 절/ON 절의 alias.column 은 FROM/JOIN 슬라이스 바깥이어서 더 이상 매칭되지 않는다. 검증: in-process 15 테스트 케이스 (단일 FROM / FROM+WHERE alias / FROM+JOIN+alias.col ON / 혼합 스키마 / 백틱 / subquery / 비허용 schema 차단 / SELECT 절 alias.col 무시 / semicolon terminator / UNION 경계 / whitespace DOTALL / 중복 refs dedup) 전부 expected refs 일치, `_whitelist_violation` 이 Q4-like SQL 에서 `{dblog}` 만 검출하고 `dbstat.foo` 는 여전히 차단. 범위: `modules/tools.py` 약 25 줄 (`_SCHEMA_TABLE_REF_RE` 제거 + 2 단계 스캐너 추가). TASK-0034 Q4/Q5 재수행을 가능하게 하는 선행 블로커 해제.

## CHG-20260422-0012
- Date: 2026-04-22
- Summary: 메타데이터 4 스키마(`information_schema`/`sys`/`mysql`/`performance_schema`) 를 Product whitelist 와 무관하게 항상 agent tool 에서 접근 가능하도록 bypass 정책 확장 (REV-20260421-0005 일부 완화)
- Files: ../feature-0002-agent-core/src/modules/tools.py, docs/TASK.md, docs/MODIFY.md, docs/REVIEW.md, docs/FUNCTION.md, docs/REPORT.md
- Notes: 사용자 지시(2026-04-22, "assistant 가 스키마 구조를 찾지 못하는 이슈를 방지") 에 따라 Product 단위 DB whitelist 의 bypass 집합을 확장. `tools.py` 의 `_SYSTEM_SCHEMAS` 단일 frozenset 을 `_METADATA_SCHEMAS`(information_schema/sys/mysql/performance_schema, whitelist bypass) + `_INTERNAL_SCHEMAS`(agent_memory, whitelist 차단 유지) 두 frozenset 으로 분리했고, `_SYSTEM_SCHEMAS` 는 이들의 union 으로 남겨 기존 `_is_user_schema` / `search_tables` UX 필터 동작을 보존했다. `_whitelist_violation` 의 `allowed` 집합을 `{information_schema}` 에서 `_METADATA_SCHEMAS` 전체로 교체. 차단 시 에러 메시지 끝에 "메타데이터 스키마(information_schema/sys/mysql/performance_schema) 는 항상 접근 가능" 한 줄을 덧붙여 LLM 이 잘못 참조한 user schema 를 information_schema 경로로 리디렉션할 수 있도록 힌트를 남긴다. `agent_memory` 는 계속 차단(타 계정 대화/세션/권한 override 보호). 검증: (a) `python3 -m py_compile modules/tools.py` 통과, (b) `docker compose up -d --build web` + `--force-recreate` 후 컨테이너 in-process 호출 8 케이스(whitelist=None/메타데이터 4종 bypass/허용 user schema/혼합 통과/agent_memory 차단/비허용 user schema 차단/`_is_user_schema` UX 필터 보존) 모두 통과, (c) `execute_tool` 경로로 `execute_sql("SELECT ... FROM information_schema.TABLES")` / `describe_schema("sys")` / `execute_sql("... performance_schema.tables")` 정상 응답, `execute_sql("... mysql.user")` 는 tool-level whitelist 통과 후 DB 에서 실제 행 반환(MySQL GRANT 가 열려있음 — REV-20260422-0006 에 2 차 방어 필요성 기록), `execute_sql("... agent_memory.AgentMemoryMessages")` 와 임의 비허용 `dbstat.*` 은 여전히 차단. 범위: 코드 변경 `tools.py` 1 파일 약 14 줄. `list_schemas` 결과에 메타데이터를 노출할지는 UX 결정 영역으로 현 상태(숨김) 유지.

## CHG-20260423-0015
- Date: 2026-04-23
- Summary: Approach A wedge (사업팀 자가서비스) pilot infra — sales role seed + role-scope system prompt seed + 복제 DB 접속 envelope + pilot onboarding runbook (TASK-0044)
- Files: src/app.py, ../feature-0002-agent-core/src/modules/config.py, ../feature-0002-agent-core/src/modules/db.py, ../../.env.example, docs/TASK.md, docs/MODIFY.md, docs/FUNCTION.md, ../../docs/STATUS.md
- Notes: office-hours 2026-04-23 세션에서 승인된 Approach A (사업팀 통계/단순 데이터 자가서비스 wedge) 의 infra 구현. (1) `SEED_ROLE_DEFINITIONS` 에 RoleKey=`sales` / Name=`사업팀` entry 를 추가 — operator 권한에서 `conversation.delete.own` 만 제거한 9 개 권한(conversation.create/ask/suggestions.read/list.own/read.own/file.read.own/rename.own/cancel.own/finalize.own) 으로 사업팀 pilot 이 자기 대화 흐름은 조작하되 과거 요청 기록 삭제는 막는 subset. (2) 신규 `SEED_ROLE_SYSTEM_PROMPTS` + `_ensure_seed_role_system_prompts(conn)` 부트스트랩 단계 — `_load_system_prompt` 로 존재 여부 먼저 확인해 idempotent(관리 콘솔 수정 존중), 없을 때만 `_upsert_system_prompt(scope='role', role_id=<sales>, product_id=None)` 로 4 지침(단순 조회 → 문장 / 집계 → 결과셋 표 / ad-hoc 분석 → DBA 팀 이관 안내 후 종료 / DB 쓰기 쿼리 거부) prompt 를 insert. `_ensure_seed_products` 바로 뒤에 호출해 sales role + WebSystemPrompts 스키마 준비 모두 보장된 상태에서 실행. `agent_core.compose_system_prompt` 가 기존 로직(TASK-0036) 그대로 `## ROLE GUIDANCE (sales)` 블록으로 주입한다. (3) `modules/config.py` 에 `REPLICA_DB_HOST` / `REPLICA_DB_PORT` / `REPLICA_DB_USER` / `REPLICA_DB_PASSWORD` env 4 개 + 파생 `REPLICA_DB_ENABLED=bool(REPLICA_DB_HOST)` 추가, `__all__` 에 5 개 export. `modules/db.py::connect()` 에 라우팅 로직 — `REPLICA_DB_ENABLED` 가 True 이고 요청된 `database` 가 `MEMORY_DB`(=agent_memory) 가 아니면 복제 인스턴스(host/port/user/password) 로 접속, 그 외(미설정/메모리 연결/database=None) 는 기존 primary 파라미터. memory DB 는 항상 primary 이므로 대화·세션·권한 정본이 보존된다. (4) `.env.example` 에 `REPLICA_DB_HOST=` / `REPLICA_DB_PORT=` / `REPLICA_DB_USER=` / `REPLICA_DB_PASSWORD=` 4 placeholder + 사업팀 pilot 이름 치환용 `WEB_PILOT_SALES_USERNAMES=` 주석 추가. 실제 접속 정보/계정 이름은 `.env` 또는 docker-compose secret 으로만 주입(commit 금지). (5) pilot 계정 자동 생성은 하지 않음 — admin 이 관리 콘솔에서 수동 발급하도록 docs/TASK.md §TASK-0044 pilot onboarding runbook 에 3 단계 절차(계정 발급 / Product whitelist 2 가지 옵션 / 복제 DB 접속 등록) 기록. (6) Product 단위 접근 DB 화이트리스트 조정은 런타임 코드 변경 없이 runbook 으로 해결 — 옵션 A(KR Product 에서 dbauth 제거) 또는 옵션 B(KR-Sales Product 신규 생성) 중 조직 정책에 맞게 선택. 현재 seed 는 호환성을 위해 변경하지 않음. 검증: (a) `python3 -m py_compile unit/feature-0003-agent-web-ui/src/app.py unit/feature-0002-agent-core/src/modules/config.py unit/feature-0002-agent-core/src/modules/db.py` 통과, (b) `docker compose up -d --build web` 후 `/api/session` HTTP 200 OK + bootstrap_admin 로그인 성공, (c) MySQL 에 `SELECT r.RoleKey,r.Name,COUNT(rp.PermissionId) FROM WebRoles r LEFT JOIN WebRolePermissions rp ON r.Id=rp.RoleId WHERE r.RoleKey='sales' GROUP BY r.Id` 결과 1 row `sales / 사업팀 / 9`, (d) `SELECT LEFT(Content,60) FROM WebSystemPrompts WHERE Scope='role' AND RoleId=(SELECT Id FROM WebRoles WHERE RoleKey='sales') AND ProductId IS NULL` 1 row 에 "당신은 게임 사업팀을 지원하는 DBA 어시스턴트다" 로 시작. 범위: 코드 3 파일 약 70 줄(app.py +54, config.py +12, db.py +11), `.env.example` +6 줄, 문서 4 파일. 사업팀 pilot 의 단순/집계/ad-hoc 실제 응답 acceptance 3 개는 pilot 계정 발급 이후 admin 이 수동 확인(TASK.md AC 체크리스트의 미체크 3 항목) 하도록 남겨둔다 — 현재 환경에 사업팀 pilot 계정 발급이 선행되지 않아 코드 단독으로는 검증 불가.


## CHG-20260424-0016
- Date: 2026-04-24
- Related Requirement: TASK-0045 (template v3.2.0-rc.1 external anchor 도입)
- Summary: ANCHOR.md §1-§3 작성 — Web UI feature가 "UI + 서버 측 로직 전체" 범위임을 명시, System Prompt 3계층 조립의 Web feature 귀속 근거, layering 위반 방지, whitelist 관리 onboarding 시나리오.
- Files: unit/feature-0003-agent-web-ui/docs/ANCHOR.md, unit/feature-0003-agent-web-ui/docs/TASK.md
- Impact: feature 방향성 stable reference 확립. System Prompt 조립을 core로 옮기려는 향후 요청은 §1 / §2 Alt-A와 충돌 감지 (Conflict Protocol 발화). whitelist 정책 변경 시 §3 시나리오가 onboarding 진입점 역할.
- Rollback Notes: ANCHOR.md 내용 revert 시 verify-completion check #6이 24h grace 만료 후 FAIL. 사용자 직접 §1-§3 재작성 필요.

## CHG-20260425-0017
- Date: 2026-04-25
- Related Requirement: TASK-0046, REQ-20260425-0001
- Summary: 프로필 드로어의 API Vault 탭을 Linear Wizard 3-step 구조로 재설계 + 단일 진입점 destructive 정책. 사용자 raw feedback "프로필쪽 키 입력하는곳 왜이래? 알아먹기 힘드네" 대응.
- Files: unit/feature-0003-agent-web-ui/src/static/index.html, unit/feature-0003-agent-web-ui/src/static/styles.css, unit/feature-0003-agent-web-ui/src/static/app.js, unit/feature-0003-agent-web-ui/docs/TASK.md, unit/feature-0003-agent-web-ui/docs/MODIFY.md, unit/feature-0003-agent-web-ui/docs/REPORT.md, docs/REQUEST.md, docs/REQUEST_ARCHIVE.md
- Notes: 4 단계 반복(initial Linear Wizard → fix1 saved card 분리 → fix2 replacingVault flag → final 단일 진입점) 으로 사용자 검증을 거쳐 완성. 핵심 변경 (1) `index.html` L246-L334 의 vault 패널 markup 을 `vault-banner` (readiness tri-state) + `ol.vault-stepper > li.vault-step × 3` (Step 1 사용할 API 키 / Step 2 passphrase / Step 3 암호화 후 저장) + `vault-saved` (information only — 저장 시 노출, 버튼 0 개) + `vault-danger-zone` (저장된 키 삭제 1 개) + `details.vault-advanced` (cipher 직접 붙여넣기, 기본 접힘) 로 재구성. (2) `styles.css` L1420-L1582 에 `.vault-banner` / `.vault-banner-dot[data-state]` / `.vault-stepper` / `.vault-step[data-state="active|done|disabled"]` / `.vault-step-num` / `.vault-step-head/title/body/hint` / `.vault-saved` / `.vault-danger-zone` / `.btn-danger-link` / `.vault-advanced[-body]` 신규(약 170 줄). (3) `app.js` 의 vault state helper 군 재작성 — `updateVaultStatus` → `updateVaultReadiness` rename + `computeVaultReadiness` 의 진실 출처를 input value 에서 storage(localStorage cipher + sessionStorage|input passphrase) 로 통일, `syncVaultSteps` 가 `cipherSaved` 만으로 saved-default ↔ wizard 입력 모드 전환, `renderVaultSavedCard` 가 saved card + danger zone 동시 hidden 토글, `encryptPlainApiKey` + `writeVaultState` 를 단일 saveVault 흐름으로 합쳐 "암호화 후 저장" 한 버튼이 평문→cipher 변환→영속 모두 처리, `clearVaultBtn` 핸들러 앞에 `confirm("저장된 암호화 키를 삭제할까요? ...")` 가드 추가, 신규 `vaultImportCipherBtn` 핸들러로 `v1:` prefix 검증 후 ciphertext 직접 import. 키 갈아끼움 진입점은 "저장된 키 삭제" → confirm → wizard 재진입 → 새 평문 입력 → 저장 1 경로로 단일화 — `vaultReplaceBtn` / `replacingVault` flag / `enterReplaceMode` / `cancelReplaceMode` 모두 제거. cache-bust `v=20260425-vault-final`. (4) 검증: `repo/.gstack/qa-reports/qa-vault.cjs` (Playwright Node script, browse 데몬 우회) 28/28 PASS, healthScore 100, console.error 0 건. AUTH/SESSION/BUST/DRAWER/TAB/UI(10)/FLOW(3)/REG(8)/CONSOLE 전 카테고리 통과. 사용자 직접 브라우저 검증 4 시나리오(저장 완료 / 새로고침 / 삭제 후 새 키 입력 / confirm 취소) 모두 만족. (5) 사용자 raw feedback ("프로필쪽 키 입력하는곳 왜이래? 알아먹기 힘드네") 의 구조적 원인(시작점이 `<details>` 에 숨음 / 라벨 한 글자 차이 / 종속관계 표현 실패 / "저장" 동사 모호성 / 결과 동일 진입점 중복) 모두 해소됨.

## CHG-20260512-0001
- Date: 2026-05-12
- Related Requirement: TASK-0055, REQ-20260512-0001
- Summary: 관리 콘솔 카테고리별 다중선택 (multi-select) UI 정합 컨벤션 v0.2 도입 — Accounts / Roles / Products 의 bulk toolbar / select-all / row checkbox / cross-page banner / keyboard 단축키 / a11y / typed-confirm / RBAC partial-fail UI 를 단일 패턴으로 통일. drift 재발 차단을 위한 runtime contract assertion 추가.
- Files: docs/CONVENTIONS.md (project-level §10 신설), unit/feature-0003-agent-web-ui/docs/DESIGN.md (신규), unit/feature-0003-agent-web-ui/src/static/admin.html (Accounts bulk anchor 이전, Products multi-select HTML 신설, 모든 카테고리에 role/aria-live/cross-page banner), unit/feature-0003-agent-web-ui/src/static/styles.css (--z-bulk-bar/--z-bulk-banner/--bulk-bar-bottom/--bulk-bar-elev 토큰, .admin-bulk-actions sticky, .admin-bulk-cross-page, .kbd-hint, .toast-skipped), unit/feature-0003-agent-web-ui/src/static/admin.js (BULK_ENTITY_UNIT/BULK_ACTION_LABEL/CONFIRM_TYPED_THRESHOLD 상수, confirmBulkAction/runBulkActionWithPartialFail/assertBulkBarContract/renderCrossPageBanner/applyShiftRangeSelect 헬퍼, Accounts/Roles/Products 의 render*List/render*BulkBar/bulk*SetActive/bulk*Delete 전면 통일, productSelected: Set<number> 신설, accountLastClickIdx/roleLastClickIdx/productLastClickIdx 신설, Esc 글로벌 핸들러, productSelectAll listener, initialize 끝에 assertBulkBarContract 호출), unit/feature-0003-agent-web-ui/docs/FUNCTION.md (REQ-20260512-0001 + AC-0031~0040), unit/feature-0003-agent-web-ui/docs/TASK.md (TASK-0055 entry), unit/feature-0003-agent-web-ui/docs/MODIFY.md (본 entry), unit/feature-0003-agent-web-ui/docs/REVIEW.md (REV-20260512-0001), unit/feature-0003-agent-web-ui/docs/REPORT.md (본 cycle Summary prepend), docs/STATUS.md (feature-0003 갱신 2026-05-12).
- Diff size: admin.js 2645 → 3080 lines (+435), admin.html 219 → 250 lines (+31), styles.css 2976 → 3052 lines (+76). cache-bust v=20260512-bulk-contract-v02.
- Impact: 차후 admin 카테고리 추가 시 컨벤션 미준수가 runtime assertion (console.warn) 으로 감지된다. 사용자가 보고한 계정 우상단 / 역할 좌하단 / 제품 다중선택 부재 의 카테고리 간 일관성 결여 root cause 두 가지 (DOM anchor 표준 부재 + .admin-pane-head-right 슬롯 semantic 충돌) 가 정책 + 코드 두 층에서 모두 해소.
- Rollback Notes: 본 변경은 backend 데이터 모델 변경 없음. UI/JS/CSS 만 변경. admin.js / admin.html / styles.css 의 git revert 로 즉시 복구 가능. RBAC catalog 변경 없음 (기존 권한 product.manage / account.activate 등의 row-level check 만 활용).

## CHG-20260521-0001
- Date: 2026-05-21
- Related Requirement: TASK-0094, REQ-20260521-0001
- Summary: 첨부 기능 multi-cycle (A CSV ingest + B DDL/KB + C Vision + D PDF RAG) 의 BRIEFING 정본 (Revision 2) 작성 + TASK.md 신규 entry 등재 + PLAN-APPROVED 마커 부여. Codex outside-voice review 2 회 (REV-20260520-0001 1차 + REV-20260521-0002 2차 follow-up) 흡수. 코드 변경 0, 계획 문서만 갱신.
- Files: unit/feature-0003-agent-web-ui/docs/BRIEFING-attachment-multi-cycle.md (신규, 923 lines), unit/feature-0003-agent-web-ui/docs/TASK.md (TASK-0094 entry + Current Status + PLAN-APPROVED 마커), .gitignore (`.context/` 추가).
- Notes: 본 cycle 은 코드/스키마/RBAC catalog 변경 없이 multi-cycle plan 의 정본을 lock-in 한다. 핵심 결정 21 건 (D1~D21):
  - D1 S3-compat MinIO (compose +1 service `minio`). 사내망 다운로드용 signed URL 만 발급, 외부 LLM provider 에는 절대 송신 금지 (D13).
  - D2 sandbox DB = 동일 cluster + 별 schema `agent_attachment_<sha256(conv_id)[:32]>`. `WebConversationAttachmentsSandboxSchemas` mapping table 유지.
  - D3 vector store = PGVector (Postgres 도입 — compose +1 service `postgres`). 단계적 (D10): dev 1차는 agent_memory 와 동일 컨테이너 + DB 분리, prod 는 별 instance 옵션 PLAN gate 재검토.
  - D4 4 시나리오 (A CSV + B DDL/KB + C Vision + D PDF RAG) 전부 진행. 4 sprint 분리. D18 단일 통합 PLAN gate.
  - D5 Codex outside-voice review 2 회 완료 — 1차 17 Valid finding 흡수, 2차 Critical 3 + Major 11 + Minor 2 흡수 (F8 만 사용자 명시 거부).
  - D6 lifecycle 4 종 (user delete / conv soft / admin purge / legal erasure) + tombstone + nullable FK (R-Claim6) + UX 4 state 표면화 (R-F1) + pseudonymous irreversible event id (R-F12).
  - D7 MIME allowlist + archive 거부. D8 size cap (per-file 25MB / per-conv 100MB / per-account 1GB).
  - D9 share derived redact + 기존 token 자동 redact (R-F7 Critical) + `WebShareLinks.PolicyVersion` column.
  - D10 PGVector dev/prod 단계적.
  - D11 consent provider×data_class×purpose + revoke + 재동의 + grouped batch modal (R-F2) + provider Files API lifecycle (R-F13).
  - D12 audit HMAC + extension/size bucket + AST normalized SQL + denied reason + pseudonym cross-ref.
  - D13 외부 LLM bytes = server-side read + base64 inline 또는 Files API. `WebConversationAttachmentProviderFiles` 신규 + post-inference delete (R-F13).
  - **D14 sandbox SQL guard = AST shape allowlist (R-F3 Critical)** — single SELECT/CTE only, FOR UPDATE / LOCK / EXPLAIN ANALYZE / optimizer hint / SLEEP / BENCHMARK / user variable / INTO OUTFILE / LOAD_FILE / information_schema / mysql.* / performance_schema / sys.* 전부 거부. denylist 는 보조 secondary check.
  - D15 wildcard grant 금지 + writer 최소권한 (CREATE/ALTER/INSERT/SELECT) (R-Claim4) + grant drift health endpoint `/api/admin/health/attachment-grants` + 주기 reconciliation (R-F4).
  - D16 attachment_ids selected-only + lazy-create attachment snapshot (R-F5) — busyKey/pending sentinel 에 snapshot 저장.
  - D17 UploadStatus 7 값 + retrieval-time policy (R-F6) — partial_indexed 문서 answer meta degraded_sources / UI banner / LLM system note / OCR follow-up.
  - **D18 단일 통합 PLAN gate** — Codex F8 의 1A/1B/1C 분할 권고 사용자 명시 거부. 위험 격리는 D14 + R-Claim4 + R-F4 + D20 조합으로 충족.
  - **D19 `WebAttachmentDerivedMessages(AttachmentId, MessageId, DerivationType, CreatedAt)` join table** (R-F11) — many-to-many 정규화, share redact/audit/fork 의 source-of-truth.
  - **D20 MinIO dual-key rotation runbook** (R-F9) — old/new 24h dual window + canary write/read/delete + 컨테이너 순차 재기동 + rollback + audit `attachment.storage.key_rotation`.
  - **D21 pending role attachment metadata-only** (R-F14) — bytes download 는 승인 후, audit `attachment.bytes_download.denied_pending` 기록.
- Impact: Sprint 1 (Cycle 0 Foundation + Cycle 1 CSV ingest) implementation 진입 가능. D14 SQL allowlist guard 통과가 Sprint 1 ship 조건. 코드 변경은 별 worktree `ai/claude/0087/sprint-1-foundation-csv` (또는 `0094/sprint-1-...`) 에서 진행. 본 cycle 자체의 코드/스키마/RBAC catalog 영향 0.
- Rollback Notes: 본 변경은 문서 only. revert 시 BRIEFING 신규 파일 삭제 + TASK.md 의 TASK-0094 entry + PLAN-APPROVED 마커 + Current Status 갱신 revert + .gitignore 의 `.context/` 한 줄 revert. revert 후 Sprint 1 진입은 BRIEFING/계획 재작성 필요.

## CHG-20260521-0002
- Date: 2026-05-21
- Related Requirement: TASK-0094 cleanup follow-up (AGENTS.md §16.5 Step 6 사후 동기화 결과 기록)
- Summary: TASK-0094 PLAN-APPROVED cycle (CHG-20260521-0001, PR #40 merged 2026-05-21T02:15:30Z) 의 §16.5 Step 6 결과 기록 보강. CHG-20260521-0001 본 PR 에서 누락된 REPORT.md §1 Summary 의 cycle entry + Git 동기화 결과 표 append. 추가 코드 변경 0.
- Files: unit/feature-0003-agent-web-ui/docs/REPORT.md (§1 Summary 상단에 TASK-0094 entry + Git 동기화 결과 표), unit/feature-0003-agent-web-ui/docs/MODIFY.md (본 entry), unit/feature-0003-agent-web-ui/docs/REVIEW.md (REV-20260521-0002 [SKIPPED:report-sync-only]).
- Notes: 단순 운영 기록 follow-up. AGENTS.md §16.5 Step 6 의 결과 기록을 본 cycle 의 첫 PR 에 포함하지 못한 누락 보강. outside-voice review 추가 호출 없음 (REPORT.md 의 단순 사실 append 는 SUBAGENT review 대상 아님 — SKIPPED).
- Impact: docs only. backend / RBAC / 스키마 영향 0.
- Rollback Notes: REPORT.md TASK-0094 entry 한 블록 revert 로 즉시 복구 가능. MODIFY/REVIEW 의 본 entry 도 함께 revert.

## CHG-20260521-0003
- Date: 2026-05-21
- Related Requirement: TASK-0094 (REQ-20260521-0001, Critical §12.3) Sprint 1 Phase 1 — Pre-flight (ADR + compose + env + bootstrap script + platform-runtime ANCHOR)
- Summary: 첨부 기능 multi-cycle Sprint 1 Cycle 0 진입 인프라 사전 작업. ADR-0022 (MinIO 도입) + ADR-0023 (sandbox schema + D15 maintenance path 분리) + ADR-0025 (PGVector for attachment Sprint 4 prerequisite) 등재. docker-compose.yml 에 `minio` + `minio-init` service 추가. `.env.example` 16 변수 추가 (MinIO 7 + 호스트 port 2 + browser redirect 1 + ATTACHMENT_MAX_BYTES_* 3 + ATTACHMENT_AUDIT_HMAC_KEY 1 + SANDBOX_SQL_* 2). `unit/feature-0003-agent-web-ui/src/scripts/minio-init.sh` 신설 (idempotent bucket + bucket-scoped policy + app key bootstrap). feature-0001-platform-runtime ANCHOR §1 갱신.
- Files:
  - `docs/DECISIONS.md` — ADR-0022/0023/0025 신설 (3 ADR, 약 56 lines)
  - `docker-compose.yml` — `minio` + `minio-init` 2 service 추가 (약 50 lines)
  - `.env.example` — MinIO + attachment + sandbox 섹션 추가 (41 lines, 16 vars)
  - `unit/feature-0003-agent-web-ui/src/scripts/minio-init.sh` — 부트스트랩 신규 (130 lines, mc-based)
  - `unit/feature-0001-platform-runtime/docs/ANCHOR.md` — §1 비-MySQL service platform 책임 명시 항목 추가
  - `unit/feature-0003-agent-web-ui/docs/TASK.md` — Sprint 1 Phase 1~12 breakdown + Phase 1 [x] 표시 + Current Status 갱신
  - `unit/feature-0003-agent-web-ui/docs/MODIFY.md` — 본 entry
  - `unit/feature-0003-agent-web-ui/docs/REVIEW.md` — REV-20260521-0003 entry
- Notes: Phase 1 은 코드 직접 변경 (Python / JS) 없이 인프라 / 정책 / 부트스트랩만. Phase 2~12 가 schema / RBAC / storage wrapper / API / UI / share / lifecycle / sandbox / ingest / SQL guard 본격 작업. **D14 SQL allowlist guard 통과** 가 Sprint 1 ship 조건 (Phase 12).
- Impact:
  - 본 Phase 1 ship 후 dev 환경에서 `make up` 또는 `docker compose up -d` 시 minio + minio-init 함께 가동. minio-init 부트스트랩 1 회 완료 후 minio API endpoint (`minio:9000`) 에서 app key 인증 가능. `agent-attachments` bucket 생성 확인 가능.
  - 본 Phase 1 자체는 backend / RBAC catalog / 스키마 영향 0. Phase 2 진입 시 `_ensure_web_conversation_attachments_schema(conn)` 등 helper 와 schema column 신설.
  - 실제 attachment upload / ingest / SQL 실행 path 는 Phase 5/11/12 ship 까지 unavailable (사용자에게는 영향 없음).
- Rollback Notes:
  - ADR-0022/0023/0025 의 status 를 `superseded` 또는 `rejected` 로 갱신.
  - docker-compose.yml 의 `minio` + `minio-init` service block 제거.
  - `.env.example` 의 MinIO/attachment/sandbox 섹션 제거.
  - `unit/feature-0003-agent-web-ui/src/scripts/minio-init.sh` 파일 삭제.
  - `unit/feature-0001-platform-runtime/docs/ANCHOR.md` 의 비-MySQL service 항목 revert.
  - 실제 데이터 영향 0 (Phase 1 은 인프라 / 정책만). minio container volume `../artifacts/minio-data` 도 비어 있어 별도 cleanup 불필요.

## CHG-20260521-0004
- Date: 2026-05-21
- Related Requirement: TASK-0094 (REQ-20260521-0001, Critical §12.3) Sprint 1 Phase 2 — Cycle 0 schema (5 신규 table + 1 column ALTER)
- Summary: BRIEFING §5.1 정본의 첨부 metadata + sandbox mapping + consent + derived join + provider files lifecycle 5 신규 테이블 + 기존 `WebConversationShares` 에 `PolicyVersion` column (R-F7) idempotent ALTER. 6 helper 신설 + fast/slow path 양쪽 호출 등록. py_compile PASS.
- Files:
  - `unit/feature-0003-agent-web-ui/src/app.py` — 6 helper 신설 (line 2638~2853, 약 215 lines) + 호출 등록 2 곳 (`_ensure_seed_catchup` line 3037~3047, `_ensure_web_tables` line 3414~3424)
  - `unit/feature-0003-agent-web-ui/docs/FUNCTION.md` — AC-0210~0215 추가 (6 AC)
  - `unit/feature-0003-agent-web-ui/docs/TASK.md` — Phase 2 [x] 표시 + Current Status 갱신
  - `unit/feature-0003-agent-web-ui/docs/MODIFY.md` — 본 entry
  - `unit/feature-0003-agent-web-ui/docs/REVIEW.md` — REV-20260521-0004 [SKIPPED:schema-only] append
- Notes: Phase 2 는 schema only — backend endpoint / RBAC catalog / UI 변경 0. 실제 INSERT / SELECT path 는 Phase 5 (upload API), Phase 8 (share redact), Phase 11 (ingest), Phase 12 (SQL guard) 에서 ship. 5 신규 table 은 모두 빈 상태로 시작 — 본 schema add 자체가 사용자에게는 영향 없음.
- Impact: 부트스트랩 (`_ensure_seed_catchup` fast path + `_ensure_web_tables` slow path) 양쪽에서 신규 helper 가 idempotent 실행. 기존 배포에도 자동 적용. `WebConversationShares.PolicyVersion` column 은 기존 row 에 DEFAULT 1 backfill. backend / RBAC catalog 영향 0.
- Rollback Notes:
  - `unit/feature-0003-agent-web-ui/src/app.py` 의 6 helper 정의 + 호출 등록 revert.
  - 5 신규 table 은 `DROP TABLE IF EXISTS WebConversationAttachments, WebConversationAttachmentsSandboxSchemas, WebAccountConsents, WebAttachmentDerivedMessages, WebConversationAttachmentProviderFiles;` 로 제거 (rollback DDL 단순).
  - `WebConversationShares.PolicyVersion` column 은 `ALTER TABLE WebConversationShares DROP COLUMN PolicyVersion;` 으로 제거 (column 자체는 NOT NULL DEFAULT 1 이라 기존 row 영향 0).
  - 본 Phase 2 가 ship 된 commit 후에 사용자 데이터가 누적되지 않은 시점이라 rollback risk 최소.

## CHG-20260521-0005
- Date: 2026-05-21
- Related Requirement: TASK-0094 (REQ-20260521-0001, Critical §12.3) Sprint 1 Phase 3 — Cycle 0 RBAC (4 권한 + 6 checklist + D21 pending)
- Summary: BRIEFING §5.2 1~4 row 정합. 첨부 기능 4 권한 코드 (`conversation.attachment.{upload,read}.{own,any}`) catalog 추가 + admin/operator/sales/dba/pending 5 role 모두 catchup + D21 (R-F14) pending metadata-only + app.js label/description map. attachment group 신설은 Phase 12 (Cycle 1 attachment.execute_sql_on.*) 까지 보류.
- Files:
  - `unit/feature-0003-agent-web-ui/src/app.py` — PERMISSION_DEFINITIONS 4 코드 추가 (line 314~341, 약 28 lines), SEED_ROLE_DEFINITIONS pending/operator/sales 의 permissions set 에 attachment 권한 추가, _ensure_seed_roles 의 admin/operator-sales/dba/pending 4 곳 catchup tuple 갱신.
  - `unit/feature-0003-agent-web-ui/src/static/app.js` — PERMISSION_LABELS (line ~267) + PERMISSION_DESCRIPTIONS (line ~310) 에 4 코드 추가 (각 8 lines).
  - `unit/feature-0003-agent-web-ui/docs/FUNCTION.md` — AC-0216~0218 (3 AC).
  - `unit/feature-0003-agent-web-ui/docs/TASK.md` — Phase 3 [x] 표시 + Current Status 갱신.
  - `unit/feature-0003-agent-web-ui/docs/MODIFY.md` — 본 entry.
  - `unit/feature-0003-agent-web-ui/docs/REVIEW.md` — REV-20260521-0005 [SKIPPED:rbac-catalog-only] append.
- Notes: 사용자 메모리 정책 "RBAC plan 은 outside voice 필수" 대응 — 본 Phase 3 의 RBAC 변경은 TASK-0094 BRIEFING Revision 2 (Codex outside-voice review 2 회 흡수 lock-in) 의 D6/D11/D12/D14/D15/D16/D21 결정 정합. catalog blindspot 대응은 BRIEFING REV-20260520-0001 Claim #1 (6 checklist) + Claim #3 (정적 catalog source) + REV-20260521-0002 R-F14 (pending metadata-only) 흡수로 이미 정본 review 완료. 사용자 명시 진입 결정에 따라 본 Phase 진행. 후속 plan-eng-review / codex review 는 Phase 12 (D14 SQL guard, Ship 조건) 진입 시점에 권장.
- Impact: 새 catalog 4 코드 + 5 role catchup. 기존 배포에 `_ensure_seed_catchup` fast path 진입 시 자동 INSERT IGNORE. application-level endpoint 는 Phase 5 (upload API) 에서 ship — 본 Phase 3 ship 직후 시점은 권한만 부여, 실제 upload/download 경로 unavailable.
- Rollback Notes: PERMISSION_DEFINITIONS 의 4 코드 entry / SEED_ROLE_DEFINITIONS pending/operator/sales 추가 권한 / _ensure_seed_roles 의 5 catchup 추가 / app.js label/description map 의 4 entry revert. 기존 배포의 WebRolePermissions 에 INSERT 된 row 는 `DELETE FROM WebRolePermissions WHERE PermissionId IN (SELECT Id FROM WebPermissions WHERE Code LIKE 'conversation.attachment.%')` 또는 보존 (catalog 무관 row 는 영향 0).

## CHG-20260522-0001
- Date: 2026-05-22
- Related Requirement: TASK-0097 (REQ-20260522-0001, Minor §12.3) DQA 브랜딩 적용
- Summary: 웹 UI 전체 브랜딩을 'MySQL AI' → DQA (Database Query Assistant) 로 변경. SVG 로고 신설.
- Files:
  - `unit/feature-0003-agent-web-ui/src/static/index.html` — title / auth-title / auth-logo / sidebar brand-icon·name 변경.
  - `unit/feature-0003-agent-web-ui/src/static/admin.html` — title / sidebar brand-icon·name 변경.
  - `unit/feature-0003-agent-web-ui/src/static/styles.css` — 상단 주석 갱신, .auth-logo / .brand-icon background → transparent.
  - `unit/feature-0003-agent-web-ui/src/static/logo-dqa.svg` — 신규 SVG 로고 (48×48, primary #2563eb, DB 실린더+돋보기).
  - `unit/feature-0003-agent-web-ui/docs/FUNCTION.md` — REQ-20260522-0001 + AC-0219~0222 등재.
  - `unit/feature-0003-agent-web-ui/docs/TASK.md` — TASK-0097 [x] + Current Status 갱신.
  - `unit/feature-0003-agent-web-ui/docs/MODIFY.md` — 본 entry.
  - `unit/feature-0003-agent-web-ui/docs/REVIEW.md` — REV-20260522-0001 [SKIPPED:static-asset-only] append.
- Notes: 정적 자산 변경만. backend / RBAC / endpoint / DB / audit 무변경. docker cp 로 런닝 컨테이너에 즉시 반영 확인 (browse 스크린샷 3장).
- Impact: 브라우저 출력 브랜딩만 변경. 기능 영향 0.
- Rollback Notes: `index.html` / `admin.html` / `styles.css` 의 DQA → MySQL AI 텍스트 revert + `logo-dqa.svg` 제거.

## CHG-20260521-0006
- Date: 2026-05-22
- Related Requirement: TASK-0094 (REQ-20260521-0001, Critical §12.3) Sprint 1 Phase 4 — Cycle 0 storage wrapper + D20 rotation runbook
- Summary: BRIEFING D1/D13/D20 + R-F9 정합. MinIO S3-compat 첨부 storage wrapper `storage_minio.py` (boto3 기반, idempotent client cache, safe filename + object key, put/get/delete/signed URL/bucket_exists/smoke_test/reset_cache/CLI entry) 신설. D20 dual-key rotation runbook 별 doc. boto3>=1.34.0 / botocore>=1.34.0 requirements 추가.
- Files:
  - `unit/feature-0002-agent-core/src/requirements.txt` — boto3 + botocore 4 줄 추가 (agent 이미지 + web 이미지 공통 dep).
  - `unit/feature-0003-agent-web-ui/src/modules/__init__.py` — modules 패키지 신설 (마커 파일, 약 5 lines).
  - `unit/feature-0003-agent-web-ui/src/modules/storage_minio.py` — 약 350 lines (config + client cache + safe_filename + make_object_key + put/get/delete/signed URL + bucket_exists + run_smoke_test + reset_client_cache + CLI smoke).
  - `unit/feature-0003-agent-web-ui/docs/RUNBOOK-minio-key-rotation.md` — 약 150 lines (6 섹션: 전제/정상 path/rollback/체크리스트/자동화/cross-ref).
  - `unit/feature-0003-agent-web-ui/docs/FUNCTION.md` — AC-0223~0225 (3 AC, TASK-0097 의 AC-0219~0222 와 충돌하여 본 cycle AC 0223 부터 재번호).
  - `unit/feature-0003-agent-web-ui/docs/TASK.md` — Phase 4 [x] + Current Status 갱신.
  - `unit/feature-0003-agent-web-ui/docs/MODIFY.md` — 본 entry.
  - `unit/feature-0003-agent-web-ui/docs/REVIEW.md` — REV-20260521-0006 [SKIPPED:storage-wrapper-only] append.
- Notes: storage_minio.py 는 thin wrapper — RBAC / consent / audit / size cap / MIME 검증 모두 caller (Phase 5 upload endpoint) 책임. 본 Phase 의 module 은 SDK abstraction 만 제공. 외부 boto3 호출 실패는 모두 StorageOperationError 로 wrap 되어 caller fail-fast. boto3 미설치 환경 (dev/test) 에서는 BOTO3_AVAILABLE=False 로 import 성공 후 `get_s3_client()` 호출 시점에 StorageConfigError 발생 — graceful degradation 정합.
- Impact: 본 Phase 의 module 만 ship — 실제 upload/download endpoint 는 Phase 5 ship 후 가용. requirements.txt 변경으로 docker 이미지 rebuild 필요 (다음 compose up 시 자동). D20 runbook 은 운영자 reference — 실제 rotation 진행은 별 사용자 trigger.
- Rollback Notes: requirements.txt 의 boto3 + botocore 2 entry revert. modules/storage_minio.py + modules/__init__.py + RUNBOOK 파일 삭제 + FUNCTION/TASK/MODIFY/REVIEW 의 본 cycle entry revert. import 한 caller 가 없으므로 (Phase 5 미시작) 즉시 revert 가능.

## CHG-20260521-0007
- Date: 2026-05-22
- Related Requirement: TASK-0094 (REQ-20260521-0001, Critical §12.3) Sprint 1 Phase 5 — Cycle 0 upload API + audit + HMAC + size cap + D21 deny
- Summary: BRIEFING §5.4 6 endpoint + D7/D8/D11/D12/D13/D21 정합. FastAPI multipart upload (UploadFile/File/Form) + RBAC 검증 + size cap + HMAC categorical 메타 + MinIO put/get + audit dispatch + D21 pending bytes deny. 약 900 lines.
- Files:
  - `unit/feature-0003-agent-web-ui/src/app.py`:
    - FastAPI import 에 UploadFile/File/Form 추가
    - `build_audit_change_json` 에 4 신규 ActionCode case (attachment.upload / .delete / .consent.grant / .consent.revoke) — D12 raw filename / bytes 절대 미노출
    - attachment helper 묶음 신설 (`_attachment_size_caps`, `_hmac_filename`, `_extension_bucket`, `_size_bucket`, `_kind_from_mime`, `_account_role_key`, `_account_is_pending`, `_account_can_access_attachment`, `_check_attachment_size_caps`, `_load_attachment_row`, `_serialize_attachment_for_audit`, `_serialize_attachment_for_api`, `_ATTACHMENT_ALLOWED_MIME_TO_KIND` 상수)
    - 6 endpoint 신설:
      * `POST /api/conversations/{cid}/attachments` (multipart upload + MinIO put + INSERT + audit)
      * `GET /api/conversations/{cid}/attachments` (list active)
      * `GET /api/attachments/{id}` (metadata + signed URL re-issue, D21 pending deny)
      * `DELETE /api/attachments/{id}` (soft-delete user reason, audit)
      * `POST /api/account/consents` (D11 grant, UNIQUE upsert, audit)
      * `DELETE /api/account/consents/{id}` (D11 revoke, RevokedAt UPDATE, audit)
  - `unit/feature-0003-agent-web-ui/docs/FUNCTION.md` — AC-0226~0233 (8 AC)
  - `unit/feature-0003-agent-web-ui/docs/TASK.md` — Phase 5 [x] + Current Status 갱신
  - `unit/feature-0003-agent-web-ui/docs/MODIFY.md` — 본 entry
  - `unit/feature-0003-agent-web-ui/docs/REVIEW.md` — REV-20260521-0007 [SUBAGENT:codex-deferred] (codex review 권장 시점인데 Phase 통합 ship 후 별 cycle 로 분리)
- Notes: 본 Phase 의 endpoint 가 BRIEFING D7/D8/D11/D12/D13/D21 결정의 application-level enforcement — Phase 4 의 storage 모듈 (SDK abstraction) 위에서 보안 결정 적용. 사용자 메모리 정책 "RBAC plan 은 outside voice 필수" 정합 — RBAC 변경은 Phase 3 에서 catalog 작업 완료, 본 Phase 는 catalog enforcement 이라 별 review 우선순위 낮음. 다만 D21 pending bytes deny 의 application-level 분기 (`_account_is_pending`) 는 향후 codex review 권장 항목으로 명시.
- Impact: 본 Phase ship 직후 dev 환경에서 첨부 upload/list/get/delete + consent grant/revoke 가능. MinIO + WebConversationAttachments + WebAccountConsents 모두 활성 — Phase 6 (composer UI) 진입 시 frontend 가 본 endpoint 호출. raw bytes 는 사내망 다운로드만 (signed URL) + 외부 LLM 송신은 Phase 5 unblock 안 됨 (Cycle 2 vision / Cycle 3 KB / Cycle 4 RAG 시점 ship).
- Rollback Notes: 6 endpoint definition + helper 묶음 + audit case 4 모두 revert. 기존 row 는 DB 에 보존 — `DELETE FROM WebConversationAttachments`/`WebAccountConsents` 또는 보존. MinIO bucket 의 객체는 운영자가 별도 `mc rm` 또는 보존.

## CHG-20260521-0008
- Date: 2026-05-22
- Related Requirement: TASK-0094 (REQ-20260521-0001, Critical §12.3) Sprint 1 Phase 6 — Cycle 0 composer UI (paperclip + drag-drop + pills + D16 snapshot + R-F5 lazy-create)
- Summary: BRIEFING §5.6 + D16 + R-F5 정합. composer 영역에 첨부 UI (paperclip 버튼 + hidden file input + drag-drop overlay + attachment pills + scope-all checkbox) 추가. state.composerAttachments 신규 + helper 7개 + event binding + selectConversation 진입 시 list load.
- Files:
  - `unit/feature-0003-agent-web-ui/src/static/index.html` — composer-wrap 안에 composer-attachments + composer-drop-overlay + attach-btn + file input 추가 (약 25 lines).
  - `unit/feature-0003-agent-web-ui/src/static/styles.css` — `.composer-wrap` position relative + `.composer-attachments` + `.composer-attachment-pill` (selected/uploading/error data-attr 별 스타일) + `.composer-drop-overlay` + `.attach-btn` (약 130 lines).
  - `unit/feature-0003-agent-web-ui/src/static/app.js`:
    - state.composerAttachments 추가 (byConv / uploadingCount / nextLocalId)
    - sendPrompt 의 askBody 에 attachment_ids + attachment_scope_all 명시 (snapshot 호출)
    - helper 7 신설: `_composerAttachmentKey`, `_ensureComposerBucket`, `_composerAttachmentSnapshot`, `_renderAttachmentPills`, `_uploadComposerAttachment`, `_guessKindFromFile`, `_toggleAttachmentPill`, `_loadConversationAttachments`, `_bindComposerAttachmentEvents` (실제 9 helper)
    - initialize 끝에 `_bindComposerAttachmentEvents()` 호출 (paperclip click / file input change / scope-all change / pills toggle / drag-drop)
    - selectConversation 끝에 `_loadConversationAttachments(cid)` 호출 (대화 진입 시 backend ground truth 동기화)
  - `unit/feature-0003-agent-web-ui/docs/FUNCTION.md` — AC-0234~0240 (7 AC)
  - `unit/feature-0003-agent-web-ui/docs/TASK.md` — Phase 6 [x] + Current Status 갱신
  - `unit/feature-0003-agent-web-ui/docs/MODIFY.md` — 본 entry
  - `unit/feature-0003-agent-web-ui/docs/REVIEW.md` — REV-20260521-0008 [SKIPPED:frontend-only] append
- Notes: lazy-create 상태에서는 paperclip 클릭 시 사용자에게 "첨부는 대화 생성 후 가능" 안내 후 거부 — backend endpoint 가 cid 를 요구하기 때문. 첫 메시지 send 후 (대화 생성 후) 다시 paperclip 클릭 가능. Phase 11 (ingest pipeline) 진입 후 사용자가 실제 LLM 응답에서 CSV/XLSX 의 content 가 활용되는 것을 확인 가능 — 본 Phase 만으로는 attachment_ids 전송만 가능하고 backend `/api/ask` 가 아직 attachment 를 prompt context 에 주입하지 않음 (Phase 11 ship 후 활성).
- Impact: 사용자 view 의 첫 표면화 — 본 Phase ship 후 사용자가 composer 의 paperclip + drag-drop 으로 파일 업로드 가능, pill 로 선택 토글 가능. 실제 LLM context 주입은 Phase 11 ship 후.
- Rollback Notes: index.html 의 신규 마크업 4개 (composer-attachments / composer-drop-overlay / attach-btn / file input) 제거. styles.css 의 신규 130 lines block 제거. app.js 의 state.composerAttachments + 9 helper + binding + load call + sendPrompt askBody 갱신 모두 revert. backend / DB / 권한 영향 0 (Phase 5 endpoint 는 그대로 유지 — Phase 6 revert 만으로 backend 호출 안 됨).

## CHG-20260521-0009
- Date: 2026-05-22
- Related Requirement: TASK-0094 Sprint 1 Phase 7 — D11 consent grouped batch modal (R-F2)
- Summary: Profile Drawer 의 "보안 및 계정" 탭에 consent UI 추가. provider × 3 group grouped batch toggle. GET /api/account/consents endpoint 신규 (POST/DELETE 는 Phase 5 ship).
- Files: app.py (GET /api/account/consents 추가), index.html (#profileConsentSection), app.js (_renderConsentSection + _handleConsentToggle + binding), styles.css (consent UI), FUNCTION/TASK/MODIFY/REVIEW.
- Notes: DB 는 세분 row, UX 는 3 group. R-F2 modal 폭격 위험 해소 정합.
- Rollback: 본 cycle entry revert + #profileConsentSection 마크업/CSS/JS 제거.

## CHG-20260521-0010
- Date: 2026-05-22
- Related Requirement: TASK-0094 Sprint 1 Phase 8 — D9 share redact + R-F7 PolicyVersion 활성
- Summary: WebConversationShares.PolicyVersion column 활성 (INSERT 명시 + SELECT 추출 + redact 로직 분기). attachment_derived 메시지 본문 자동 redact + share.policy.redact_applied audit. 기존 token (Phase 2 ship 시 DEFAULT 1 backfill) 도 배포 즉시 새 정책 적용.
- Files: app.py (_share_redact_message_content / _share_load_messages 갱신 / public_share_view redact dispatch / INSERT PolicyVersion / build_audit_change_json case), FUNCTION/TASK/MODIFY/REVIEW.
- Notes: attachment_derived flag 의 실제 설정은 Phase 11 (ingest) / Cycle 2/3/4 ship 시점. 본 phase 는 mechanism 만 ship.
- Rollback: SHARE_POLICY_VERSION_CURRENT=1 로 reset 또는 redact_active 분기 비활성.

## CHG-20260521-0011
- Date: 2026-05-22
- Related Requirement: TASK-0094 Sprint 1 Phase 9 — F1 delete UX + D6 reconciliation + R-Claim6 tombstone + F12 pseudonym
- Summary: attachment lifecycle reconciliation worker (feature-0002-agent-core) + 4 state 표면화 (_serialize_attachment_for_api) + R-Claim6 tombstone 정합.
- Files: feature-0002-agent-core/src/modules/attachment_reconciliation.py (신규), app.py (_serialize_attachment_for_api 갱신), FUNCTION/TASK/MODIFY/REVIEW.
- Notes: worker scheduling (cron / thread) 은 Phase 10 후속 cycle. 본 phase 는 mechanism + run_once 만.
- Rollback: 모듈 + serialize 변경 revert.

## CHG-20260521-0012
- Date: 2026-05-22
- Related Requirement: TASK-0094 Sprint 1 Phase 10 — 4 MySQL user + R-Claim4 minimal grants + R-F4 drift health
- Summary: .env.example 4 user credentials + modules/sandbox_schema.py (4 helper) + admin health endpoint.
- Files: .env.example, modules/sandbox_schema.py (신규), app.py (GET /api/admin/health/attachment-grants), FUNCTION/TASK/MODIFY/REVIEW.
- Notes: 실제 4 MySQL user 생성 + maintainer 의 wildcard grant 는 운영자가 root 로 사전 진행 (Sprint 1 ship 시 runbook 별도). 본 phase 는 application helper + drift endpoint.
- Rollback: 4 helper module / endpoint / env entry revert.

## CHG-20260521-0013
- Date: 2026-05-22
- Related Requirement: TASK-0094 Sprint 1 Phase 11 — CSV/XLSX ingest pipeline + LLM prompt integration
- Summary: sandbox_ingest.py (ingest_csv + ingest_xlsx + ingest_attachment) + agent_core._build_attachment_context_section + /api/ask attachment_ids env passing.
- Files: feature-0002-agent-core/src/modules/sandbox_ingest.py (신규), agent_core.py (compose_system_prompt 갱신), app.py (/api/ask attachment_ids env), requirements.txt (chardet/openpyxl), FUNCTION/TASK/MODIFY/REVIEW.
- Notes: 실제 ingest 호출은 별 background worker 가 필요 (Phase 5 upload endpoint 가 RowInsert 만 ship, ingest 는 별도 trigger). 본 phase 는 helper + LLM prompt mechanism. Phase 12 의 SQL guard 와 결합 시 사용자 view 의 첨부 기반 SQL 응답 가능.
- Rollback: 모듈/helper/env passing revert.

## CHG-20260521-0014
- Date: 2026-05-22
- Related Requirement: TASK-0094 Sprint 1 Phase 12 — D14 + R-F3 Critical SQL allowlist guard + Sprint 1 Ship
- Summary: sql_guard.py (sqlglot AST allowlist) + attachment.execute_sql_on.{own,any} RBAC + attachment group 신설 + audit ActionCode 3 + FE 상수 갱신. Sprint 1 Critical Ship 조건 충족.
- Files: feature-0002-agent-core/src/modules/sql_guard.py (신규), requirements.txt (sqlglot), app.py (PERMISSION_DEFINITIONS 2 + SEED operator/sales + 3 catchup + build_audit_change_json case 3), app.js + admin.js (PERMISSION_GROUP_ORDER 9 group + label + sections), docs/CONVENTIONS.md §10.6, FUNCTION/TASK/MODIFY/REVIEW.
- Notes: 본 Phase 가 Sprint 1 Critical Ship 조건 충족. validate_sql_for_sandbox 의 실제 호출 (LLM tool 실행 시점) 은 별 cycle 또는 후속 patch — 본 phase 는 guard module + RBAC + audit dispatch 메커니즘 + group 정합.
- Rollback: sql_guard.py + 2 RBAC + group + 3 audit case + FE 상수 + CONVENTIONS revert.

## CHG-20260522-0007 (feature-0008: composer model selector)
- Date: 2026-05-22
- Related Requirement: 사용자 요청 (2026-05-22) — profile drawer 의 API Vault
  잔존 영역 + 모델 선택 UI 를 composer textarea 좌측 `+` dropdown 으로 이전
  (ChatGPT 패턴).
- Files:
  - `unit/feature-0003-agent-web-ui/src/static/index.html`: composer-box 의
    `#attachBtn` (paperclip) 제거 → `#composerActionsBtn` (`+` icon) 신규 +
    `#composerActionsMenu` (primary drop-up popup) + `#composerModelMenu`
    (secondary popup) 추가.
  - `unit/feature-0003-agent-web-ui/src/static/app.js`:
    - `state.modelCatalog` + `state.selectedModel` 신규 (선택 모델 보존).
    - dead vault code (주석화된 readVaultState 등 함수 정의 161 줄) 일괄 삭제.
    - `_bindComposerAttachmentEvents()` 의 attachBtn 직접 binding → fileInput
      change 핸들러만 유지. `+` 버튼 → primary popup 의 "파일 첨부" 항목으로
      통합.
    - 신규 helpers: `_composerCurrentModel()`, `_updateComposerModelLabel()`,
      `_closeComposerActionsMenus()`, `_openComposerActionsMenu()`,
      `_renderComposerModelMenu()`, `_openComposerModelMenu()`,
      `_bindComposerActionsEvents()`.
    - `sendPrompt()` 의 askBody.model fallback chain: `state.selectedModel` →
      `state.session.default_model` → `state.modelCatalog.default_model` →
      `state.apiVaultOptions.default_model` → literal "claude-sonnet-4".
    - `loadVaultOptions()` 가 `state.modelCatalog` 도 채우고 composer model
      label 즉시 갱신.
  - `unit/feature-0003-agent-web-ui/src/static/styles.css`: `.attach-btn`
    rename → `.composer-actions-btn` + 신규 `.composer-actions-menu` +
    `.composer-actions-item` + `.composer-model-menu` + `.composer-model-item*`.
    `.composer-box` 에 `position: relative` (popup anchor).
    반응형 fallback (max-width 720px) — secondary popup 위치 조정.
  - `unit/feature-0003-agent-web-ui/src/static/index.html` + `admin.html`:
    cache-bust `v=20260522-bedrock-cutover` → `v=20260522-composer-model-selector`.
- Impact:
  - UX: ChatGPT-스타일 multi-action `+` dropdown — 첨부 + 모델 선택을 한 곳에
    통합. textarea 좌측 영역 정리.
  - 사용자가 turn 별 모델 (Sonnet 4.6 / Haiku 4.5) 명시 선택 가능 — backend
    default 보다 우선 적용.
  - product chip (composer 우측) 은 별 영역 유지 — product 선택 의도와 모델
    선택 의도가 분리되어 명확.
- Rollback: 본 cycle 의 변경은 frontend-only — revert 시 attach-btn paperclip
  복원 + 모델 selector 제거 + cache-bust 회귀. backend 영향 0.
- Verification:
  - `node --check app.js` PASS.
  - DOM 구조: 12 service docker-compose 무영향. backend `/api/api-vault/options`
    응답 contract 무변경.

## CHG-20260522-0007
- Date: 2026-05-22
- Related Requirement: TASK-0094 Sprint 2 — Cycle 2 Vision Ship (Major §12.3, BRIEFING §6.2)
- Summary: 첨부 image (kind=image) 의 vision 가능 모델 (Claude Sonnet 4 / Haiku 4) inline 송신 + D11 consent gate + D13 base64 inline + D9 share redact + D19 derived join. feature-0007 (bedrock) 머지 위에서 LiteLLM proxy auto-normalize 활용.
- Files:
  - feature-0002-agent-core/src/modules/model_catalog.py (S2.1 — supports_vision flag + model_supports_vision helper + __all__)
  - feature-0002-agent-core/src/modules/llm.py (S2.2 — messages_for_provider helper + __all__ + import)
  - feature-0002-agent-core/src/agent_core.py (S2.3 + S2.6 — _load_attachment_inline_images + _call_llm self-contained injection + mirror_meta attachment_derived flag + imports)
  - feature-0003-agent-web-ui/src/app.py (S2.4 + S2.5 + S2.6 — _prepare_vision_inline_images + _model_to_consent_provider + _has_active_consent + _cleanup_vision_inline + build_audit_change_json case attachment.vision.invoke + ask 안 vision pre-fetch/cleanup/audit dispatch + WebAttachmentDerivedMessages INSERT + model_supports_vision import)
  - feature-0003-agent-web-ui/docs/FUNCTION.md (AC-0280~0285)
  - feature-0003-agent-web-ui/docs/TASK.md (Sprint 2 [x] mark)
  - feature-0003-agent-web-ui/docs/MODIFY.md (본 entry)
  - feature-0003-agent-web-ui/docs/REVIEW.md (REV-20260522-0014/0015)
  - feature-0003-agent-web-ui/docs/TODO-SPRINT-2-PLUS.md (Sprint 2 step 들 [x] mark + Sprint 3/4 인계 정본 보존)
- Notes:
  - **Cross-feature import 회피 (option A)**: storage_minio (feature-0003) 를 agent_core (feature-0002) 가 직접 import 안 함. caller (app.py /api/ask) 가 image bytes pre-fetch + base64 + 임시 file 작성, env `ATTACHMENT_IMAGE_INLINE_PATH` 로 path 만 전달. agent_core 는 path read only.
  - **DB string contract 불변**: messages_for_provider 는 provider 직전 transient 변환 — `AgentMemoryMessages.Content` 는 string 유지. share builder / fork / audit 영향 0.
  - **D11 consent gate**: image 첨부 + vision 가능 모델 시 `(account_id, provider=anthropic, data_class=file_image, purpose=inference)` 의 active row 확인. 미동의 시 409 + `{error_code: "consent_required", consent_required: [...]}` body 응답 (frontend modal trigger).
  - **D12 audit masking**: vision audit ChangeJson 는 `{attachment_id, mime_type, size_bucket}` 만. raw filename / bytes / object_key 절대 미노출.
  - **D13 정합**: server-side bytes read + base64 inline only. signed URL 외부 송신 0.
  - **D9 share redact**: agent_core 가 vision invoke 결과 메시지 mirror 시 MetaJson 에 `attachment_derived=true` + `derivation_type="vision_analysis"` 추가 → Sprint 1 Phase 8 의 `_meta_has_attachment_derived` 가 자동 redact 적용.
  - **D19 join**: app.py 가 audit dispatch 직후 (vision 성공 시) `_load_latest_assistant_message` 로 message_id 확보 + `WebAttachmentDerivedMessages` INSERT (각 inline attachment 별 1 row).
  - **size/count cap**: 단일 image ≤ 5MB (pre-base64), turn 당 ≤ 5. 비용 폭주 + context overflow 방지.
  - **R-F13 provider Files API lifecycle SKIPPED**: 본 cycle 은 base64 inline only → provider 측 잔존 0 → Files API 미사용 → R-F13 진입 불요. WebConversationAttachmentProviderFiles schema 는 Sprint 1 Phase 2 에서 already ship (D13 schema), 본 cycle 의 lifecycle row INSERT/DELETE 가 없음.
  - **bedrock 정합**: catalog 변경 0 (option A 사용자 결정), flag 만 추가. LiteLLM proxy (feature-0007) 가 OpenAI Chat Completions `image_url` content-array → Anthropic Vision spec (`{type:image, source:{type:base64, ...}}`) auto-normalize. `drop_params: true` 로 미지원 OpenAI param silent drop.
  - **테스트**: 14 unit test pass — messages_for_provider 8 (empty / vision_off / conversion / empty base64 skip / multi-turn idempotency / 다중 image inline / DB string 불변 / integration with claude-sonnet-4) + _load_attachment_inline_images 6 (env 부재 / file 부재 / 정상 JSON / 빈 base64 skip / 잘못된 schema / invalid JSON). _prepare_vision_inline_images 통합 test 는 container smoke 시점.
  - **codex outside-voice review SKIPPED** (사용자 결정 2026-05-22) — REV-20260522-0014 에 사유 명시.
  - Sprint 2 의 commit 분리 (rebase 후 hash): S2.1+S2.2+S2.3 backend / S2.4+S2.5+S2.6 source / S2.8 docs ship.
- Rollback: 본 4 source 파일 + 5 docs revert. Sprint 1 산출물 (storage_minio, sandbox_*, sql_guard, attachment_reconciliation, RBAC 6, audit 10, endpoint 7) 은 보존.

## CHG-20260527-0001
- Date: 2026-05-27
- Related Requirement: AR-M5-impl web hotfix — PG cutover MySQL 잔존 쿼리 차단 (TASK-AR-M5)
- Summary: `_last_step_at_for_run()` 에 `AGENT_RUNTIME_READ_BACKEND=postgres` 가드 추가. PG 모드에서 MySQL `AgentMemorySteps` 직접 조회 제거 → `agent_runtime.steps` 쿼리로 대체. web 컨테이너 재빌드 시 `ensure_memory_schema()` 가 `pass` 로만 동작하여 MySQL `agent*` 테이블 재생성 차단.
- Files:
  - feature-0003-agent-web-ui/src/app.py (_last_step_at_for_run PG 가드 추가)
- Notes:
  - PG 경로: `_pg_connect()` 로 연결 → `SELECT MAX(created_at) FROM agent_runtime.steps WHERE conversation_id=%s AND run_id=%s`. tzinfo=None 정규화 (datetime.utcnow() 비교 기준 일치).
  - MySQL fallback 유지: `AGENT_RUNTIME_READ_BACKEND != postgres` 시 기존 `AgentMemorySteps` 쿼리 동작.
  - web 이미지 재빌드 필요: `docker compose build web && docker compose up -d web` (feature-0002 의 pass-only `ensure_memory_schema()` 가 빌드에 포함).
- Rollback: app.py 의 본 PG 가드 블록 제거 + web 컨테이너 재빌드.

## CHG-20260527-ASK-STATUS-FIX
- Date: 2026-05-27
- Related Requirement: TASK-0121 (**Critical §12.3** — AR-M5 PG cutover 후 `ask_status` 500 fix)
- Summary: `_load_latest_assistant_message` 가 MySQL `AgentMemoryMessages`(AR-M5 에서 DROP됨)를 직접 쿼리하던 경로를 PG routing으로 전환. `agent_runtime.messages WHERE role='assistant' ORDER BY id DESC LIMIT 50` 쿼리 추가. psycopg2 JSONB는 dict이므로 json.dumps로 직렬화 후 기존 루프에 투입. MySQL 쿼리는 PG 예외 발생 시 fallback으로 유지.
- Files: unit/feature-0003-agent-web-ui/src/app.py
- Rollback: PG routing 블록 제거 + MySQL 직접 쿼리 복원.

## CHG-20260527-ASK-STATUS-PG
- Date: 2026-05-27
- Related Requirement: TASK-0121 (ask_status 500 오류 수정)
- Summary: `_load_latest_assistant_message` 에 PG routing 추가. AR-M5에서 MySQL `AgentMemoryMessages` 테이블 DROP 후 `ask_status` 500 오류. PG `agent_runtime.messages` WHERE role='assistant' ORDER BY id DESC LIMIT 50 쿼리로 대체. JSONB meta_json은 `json.dumps()` 직렬화 후 기존 `json.loads()` 루프에 전달 (호환 유지). PG 실패 시 MySQL fallback (try/except).
- Files:
  - feature-0003-agent-web-ui/src/app.py (_load_latest_assistant_message PG 경로 추가)
- Notes:
  - psycopg2 JSONB → dict 반환 → `json.dumps()` → 기존 `json.loads()` 흐름 유지.
  - MySQL fallback 경로 유지 (PG 연결 실패 시).
  - `from modules.db import _pg_connect` 기존 app.py PG 패턴 일치.
- Rollback: PG routing 블록 제거, MySQL 직접 쿼리 복원.

## CHG-20260527-PERM-TOGGLE-VALUE
- Date: 2026-05-27
- Related Requirement: TASK-0121 (**Critical §12.3** — 역할 권한 저장 시 "unknown permissions: on" 오류)
- Summary: `buildRoleProductCard()` 의 product access 토글 checkbox 에 `value` 속성 미설정으로 인해 브라우저 기본값 `"on"` 이 `permission_codes` 배열에 포함되어 서버 검증 실패. `toggleInput.value = perm.code` 추가. admin.js 캐시 버스팅 `v=20260527-task-0121-perm-toggle-value`.
- Files: unit/feature-0003-agent-web-ui/src/static/admin.js, unit/feature-0003-agent-web-ui/src/static/admin.html
- Rollback: admin.js 의 `toggleInput.value = perm.code` 라인 제거 + admin.html 캐시 버스트 이전 버전으로 복원.

## CHG-20260609-FORK-SHARE-PG-CUTOVER
- Date: 2026-06-09
- Related Requirement: TASK-0167 (**Major §12.3** — 대화 분기/공유 cutover 회귀 HTTP 500 수정)
- Summary: 2026-05-27 MySQL→PG cutover 로 `AgentCoreConversations`/`AgentMemoryMessages`/`AgentMemoryKv` 가 DROP 됐는데 fork/share/duplicate/public-share-view 가 raw MySQL 경로를 유지해 `Table 'agent_memory.agentmemorymessages' doesn't exist` / `agentcoreconversations` 500 을 던졌다 (CHG-20260527-ASK-STATUS-PG 의 형제 회귀 — 당시 `_load_latest_assistant_message` 만 고치고 fork/share 면은 누락). `AGENT_RUNTIME_READ_BACKEND=postgres` 분기 + `_pg_connect()` 로 PG `agent_runtime.{core_conversations,messages,kv}` 라우팅하는 backend-aware helper 10종 신설(`_runtime_backend_is_pg`/`_meta_json_to_dict`/`_conv_load_topic`/`_conv_load_product`/`_conv_load_messages_raw`/`_conv_message_exists`/`_conv_update_topic_product`/`_conv_update_topic`/`_conv_copy_messages`/`_conv_load_share_meta`). `public_share_view` 는 core_conversations(PG) + WebProducts/WebAccounts(MySQL) cross-DB 이므로 단일 JOIN 을 PG read + MySQL enrichment + Python merge(`_conv_load_share_meta`)로 분리. jsonb meta_json 은 read 시 dict 정규화 / insert 시 `%s::jsonb` 캐스트. MySQL else 분기는 비-postgres 배포용 legacy fallback 보존(`_ensure_conversation_row`/`_assign_conversation_owner` 관례 답습).
- Files:
  - unit/feature-0003-agent-web-ui/src/app.py (backend-aware helper 블록 + 5개 함수 라우팅)
  - unit/feature-0003-agent-web-ui/tests/test_fork_share_cutover.py (회귀 e2e T1~T5)
- Notes:
  - jsonb meta_json: PG psycopg 는 jsonb→dict 반환 → `_meta_json_to_dict` 로 정규화 후 `_is_internal_message`(str|None 시그니처)에는 `json.dumps` 직렬화 전달. insert 는 `%(...)s::jsonb` 와 동등한 `%s::jsonb` 캐스트(runtime_backend._PG_INSERT_MEMORY_MESSAGE 패턴 일치).
  - `_pg_connect()` 는 autocommit=True (mysql.connector 기본 동작 일치) → 명시 commit 불요.
  - fork 메시지 복제 시 FK(fk_messages_conv) 충족: create_new_conversation + _assign_conversation_owner 가 새 conv row 를 선커밋 → 이후 messages INSERT.
- Rollback: backend-aware helper 블록 제거 + 각 함수의 raw MySQL 쿼리 복원. 단 MySQL 런타임 테이블은 DROP 상태이므로 rollback 시 500 재발 — PG 경로가 정본.

## CHG-20260609-SHARE-ERRCONTRACT
- Date: 2026-06-09
- Related Requirement: TASK-0168 (**Minor §12.3** — TASK-0167 outside-voice REV-20260609-0001 권고 F1·F2 처리)
- Summary: **F1** `public_share_view` 의 대화 메타/메시지 로드(`_conv_load_share_meta`/`_share_load_messages`, PG read)를 `try/except` 로 감싸 PG 일시 장애 시 bare 500(FastAPI 기본) 대신 graceful JSON 500(`"공유 대화를 불러오지 못했습니다."`)을 반환 — fork(`_fork_conversation_impl`)의 명시 500 래핑과 에러 계약 대칭. 상단 `ViewCount++`(revoke race 가드 겸용 UPDATE)는 그대로 두며, 로드 실패 시 1 과대카운트는 허용 가능한 soft-metric 오차(race 정합 우선)로 주석화. **F2** 신규 `tests/test_share_redaction_invariant.py` — `modules.db._pg_connect` 를 mock + `AGENT_RUNTIME_READ_BACKEND=postgres` set 으로 cutover 후 PG dict-meta(jsonb→dict) 경로를 결정적 재현하고, 익명 공유뷰 보안 불변식(attachment_derived redact / internal 메시지 필터 / 정상 본문 보존 / 정책 version gate)을 단언. 성공경로 동작·RBAC·스키마·엔드포인트 계약 무변경.
- Files:
  - unit/feature-0003-agent-web-ui/src/app.py (public_share_view F1 try/except)
  - unit/feature-0003-agent-web-ui/tests/test_share_redaction_invariant.py (F2 신규)
- Notes:
  - F2 는 web 컨테이너 in-process 실행(`docker exec -w /app repo-web-1 python <test>`) 또는 make test(pytest 수집)로 검증. 라이브 DB 불요(mock).
  - 컨테이너 in-process 3/3 PASS 확인(2e89ac3 위, TASK-0167 _share_load_messages PG 경로 대상).
  - redaction/internal-filter 코드(`_share_redact_message_content`/`_is_internal_message`)는 TASK-0167·0168 모두 무변경 — F2 는 cutover refactor 후에도 불변식이 살아있음을 가드.
- Rollback: F1 try/except 제거(원래 bare 호출 복원) + 테스트 파일 삭제. 동작 회귀 없음(F1 은 실패경로만, F2 는 테스트).

## CHG-20260609-FORK-CORE-CONTEXT
- Date: 2026-06-09
- Related Requirement: TASK-0170 (**Major §12.3** — fork 문맥 상실 수정, 하이브리드 Phase 1, ADR-WEB-0005)
- Summary: fork/duplicate/공유-fork 본에서 어시스턴트가 이전 대화 문맥을 인지 못 하던 버그 수정. 원인: LLM 문맥은 `agent_runtime.core_messages`(agent_core `_load_conversation_messages` → `_PG_LOAD_CORE_MESSAGES`)에서 읽는데, fork(`_fork_conversation_impl`)는 표시 메시지(`agent_runtime.messages`)만 복사하고 core_messages 를 복사 안 해 복사본 core_messages 가 비어 문맥 0. 신규 헬퍼 `_conv_load_core_messages_raw`/`_conv_copy_core_messages`(PG 전용)로 fork 시 core_messages 를 deep-copy(role/content/tool_calls/tool_call_id/name/created_at, tool_calls jsonb 직렬화 후 `::jsonb` 재삽입). anchored fork 는 앵커 메시지 created_at 까지(`src_rows[-1][3]`), full fork/duplicate 는 전체. 교차계정 공유 fork 도 이 복사로 snapshot(상시 cross-tenant 흐름 없음). core 복사 실패 시 fork 통째 cleanup(`delete_conversation_records`, PG CASCADE)+500(반쪽 fork 금지). 응답 dict 에 `core_copied` 추가.
- 설계 경위: 사용자가 git식 reference 아키텍처 희망 → `DESIGN-fork-reference.md` 설계 → outside-voice 적대적 검토(REV-20260609-0003)가 순수 reference 의 BLOCKER 2(cross-table 시각 cut 불가, 로더 오기술)+보안 안티패턴 3(`.any` 영구 tap, 교차계정 live read, sandbox 공유) 발견 → **하이브리드 확정(ADR-WEB-0005)**: Phase 1=core_messages 복사(본 변경), Phase 2=첨부(후속 cycle).
- Files:
  - unit/feature-0003-agent-web-ui/src/app.py (_conv_load_core_messages_raw/_conv_copy_core_messages + _fork_conversation_impl 배선 + core_copied)
  - unit/feature-0003-agent-web-ui/tests/test_fork_share_cutover.py (T1b 문맥 복사 단언)
  - unit/feature-0003-agent-web-ui/docs/DESIGN-fork-reference.md (설계 정본)
  - unit/feature-0003-agent-web-ui/docs/DECISIONS.md (ADR-WEB-0005)
- Notes:
  - cross-table 시각 cut 의 한계(DESIGN §14 F1): anchored fork 경계 ±1턴. copy 라 straddling turn 은 로드 시 `_normalize_history_rows` 가 자가 치유(reference 와 달리 corruption 아님).
  - 스키마 변경·코어 로더 변경 0 — 순수 복사라 마이그레이션 0, 회귀 표면 최소(무-fork·기존 대화 무영향).
  - PG 전용: 비-postgres 배포는 core 복사 skip([]), fork 는 표시 메시지로 진행.
- Rollback: 두 헬퍼 + _fork_conversation_impl 의 core 복사 블록 + core_copied 제거. fork 는 TASK-0167 동작(표시만 복사)으로 회귀(문맥 상실 재발).

## CHG-20260609-FORK-ATTACHMENTS
- Date: 2026-06-09
- Related Requirement: TASK-0171 (**Major §12.3** — fork 첨부 복사, 하이브리드 Phase 2, ADR-WEB-0005)
- Summary: fork/duplicate/공유-fork 본에서 사용자가 원본 첨부 파일을 열람·다운로드하고 어시스턴트가 첨부 맥락을 이어가도록, fork 시 첨부를 복사한다. 신규 `_copy_conversation_attachments(conn, source_cid, new_cid, fork_account_id)` 가 `WebConversationAttachments` 활성 행(`DeletedAt IS NULL`)을 새 ConversationId + fork 소유 AccountId 로 복사하고, blob 은 **독립 복사**(`storage_minio.get_object_bytes`→`put_object_bytes`, 새 ObjectKey)한다. ObjectKey 공유는 reconciliation 이 공유 blob 을 hard-delete 해 fork 가 404 되는 refcount 위험이 있고 server-side copy 가 없어 get+put 으로 독립 복사한다(ADR 의 "blob 재업로드 0" 에서 안전상 이탈). CSV/XLSX 는 `_ingest_attachment_background` background 재적재로 **fork 전용 sandbox 스키마**(`sha256(new_cid)`)를 만든다(조상 스키마 공유 금지 — DESIGN §14 F5). `_fork_conversation_impl` 에 배선(core_messages 복사 직후), 응답에 `attachments_copied` 추가. 첨부는 보조물이라 per-attachment fail-open(단일 실패가 fork 를 막지 않음). IDOR 게이트(`_account_can_access_attachment`, conversation 소유 기반) 무변경 — fork 가 자기 행 소유라 그대로 통과.
- outside-voice(REV-20260609-0004, FIX-FIRST) 반영:
  - #2 (MAJOR) orphan blob: put→INSERT + fail-open 이 행 없는 blob 을 남겨 reconciliation 이 GC 못 함 → **INSERT 먼저 → put → put 실패 시 행 보상삭제**(업로드 endpoint 검증 순서). 양방향 고아(행 없는 blob / blob 없는 행) 차단.
  - #6 (MAJOR) quota 우회: 복사가 cap 검사 미수행 → 반복 fork 로 storage 무한 증식 → 복사 전 `_check_attachment_size_caps`(per-file/conv/account 누적) 검사, 초과분 skip(log).
  - #5 (MINOR) audit: 교차계정 fork 가 타 계정 첨부를 forker 로 이동하는 보안민감 이벤트 → `public_share_fork` 의 `share.fork` audit ctx 에 `attachments_copied`/`core_messages_copied` 건수 기록(파일명·바이트 비노출, D12).
  - #7 (MINOR) test flap: ingest 타이밍/cap-skip 대비 테스트를 ⊆+count 일관성으로 완화.
- Files:
  - unit/feature-0003-agent-web-ui/src/app.py (_copy_conversation_attachments + fork 배선 + share.fork audit ctx)
  - unit/feature-0003-agent-web-ui/tests/test_fork_attachments.py (A1~A4 신규)
- Notes:
  - 현 배포엔 활성 sandbox 0개(첨부는 text kind) — CSV 재적재 경로는 미사용/미라이브검증, 코드는 방어적 포함.
  - WebConversationAttachments 는 MySQL web 테이블(conn autocommit=True → 즉시 커밋). soft-deleted(DeletedAt) 첨부는 SELECT 에서 제외(tombstone 미복사).
- Rollback: `_copy_conversation_attachments` + fork 배선 + audit ctx 2키 + 테스트 제거. fork 는 TASK-0170 동작(첨부 미복사)으로 회귀.

## CHG-20260609-PREVIEW-CSV-GUARD
- Date: 2026-06-09
- Related Requirement: TASK-0174 ("전체 N행 미리보기" 인라인 로더 방어막 — #118 인라인 경로)
- Summary: 본문 "📎 전체 N행 미리보기" 링크가 타는 `loadCsvAsInlineTable` 에 값 기반 방어 가드 추가. 기존엔 #118 가드가 SQL-nav 경로(`loadFullCsvIntoTable`)에만 있고 본문 인라인 경로엔 없어, 잘못된 CSV 링크를 그대로 인라인 렌더했다. 로드한 CSV 의 식별 값 토큰이 인접 미리보기 표(td)와 전혀 겹치지 않으면 렌더 거부(헤더명이 아닌 값 비교 — LLM 헤더 리네이밍 오탐 방지). previewTokens≥2 일 때만 거부해 단일 토큰 우연 불일치 오탐 차단.
- Files:
  - unit/feature-0003-agent-web-ui/src/static/app.js (distinctiveValueTokens 헬퍼 신규 + loadCsvAsInlineTable 가드)
- Notes:
  - 1차 방어는 backend(agent_core _collapse_large_tables 값매칭, CHG-20260609-PREVIEW-CSV-MATCH). 본 가드는 방어심층(defense-in-depth) 최종선.
  - §18.8 패널(REV-20260609-0173) JS 오탐 지적 반영(≥2 임계).
- Rollback: distinctiveValueTokens + loadCsvAsInlineTable 가드 블록 제거.

## CHG-20260609-TASK0174-CLOSE
- Date: 2026-06-09
- Related Requirement: TASK-0174 (cycle closure — 라이브 검증 기록)
- Summary: TASK-0174 인라인 가드(CHG-20260609-PREVIEW-CSV-GUARD) cycle 마감 — TASK.md 체크박스 [x] 갱신 + TEST.md §4 에 PB-0008 Windows-browser 무회귀 검증 Run 기록(2026-06-09 TASK-0174 항목, CHECK#13 충족). 코드 변경 없음(문서 한정).
- Files:
  - unit/feature-0003-agent-web-ui/docs/TASK.md (TASK-0174 체크박스 완료)
  - unit/feature-0003-agent-web-ui/docs/TEST.md (§4 Test Run History PB-0008 Run 추가)
- Rollback: 체크박스 환원 + TEST.md §4 항목 제거.

## CHG-20260610-0184
- Date: 2026-06-10
- Related Requirement: TASK-0184 (REQ-20260610-0184)
- Summary: 관리 콘솔 LLM 사용량 3건. (A) 계정별 독립 차트를 **역할 drill-down**(역할 막대 클릭→그 역할 계정만 검색·Top-N 페이징, 기본 접힘)으로 대체 — 계정 수 증가 시 차트 과다 길이/탐색난 해소. (B) 프로필 **'사용 내역' 탭** 신설 — 신규 `GET /api/profile/usage`(본인 owner_account_id 한정, `_require_account` 로그인만, 추정 비용·역할 enrich 제외) + 미니 SVG 차트(모델별 stacked·donut). (C) 의도치 않게 노출된 프로필 **'내 활동 기록' 탭/패널/JS 제거**(`/api/profile/audits` 는 호출처 없이 잔존). RBAC 카탈로그·스키마·시크릿 무변경.
- Files:
  - unit/feature-0003-agent-web-ui/src/app.py (`profile_llm_usage` 신규 엔드포인트)
  - unit/feature-0003-agent-web-ui/src/static/admin.html (계정별 독립 차트 → drill 패널 + 캐시버스터)
  - unit/feature-0003-agent-web-ui/src/static/admin.js (`renderStackedHBar` onRowClick + `toggleAccountDrill`/`renderAccountDrill` + drill 컨트롤 바인딩 + 계정 독립 차트/`acctLabel` 제거)
  - unit/feature-0003-agent-web-ui/src/static/index.html (audits 탭/패널 제거 + usage 탭/패널 + 캐시버스터)
  - unit/feature-0003-agent-web-ui/src/static/app.js (`loadProfileAudits`/audit 게이트/핸들러 제거 + `loadProfileUsage`/미니차트 + usage 탭 핸들러)
  - unit/feature-0003-agent-web-ui/src/static/styles.css (`admin-usage-drill`·`admin-usage-hbar-row` + `profile-usage` 클래스)
  - unit/feature-0003-agent-web-ui/docs/TASK.md, FUNCTION.md, REVIEW.md, STATUS.md
- Rollback: 본 cycle 커밋 revert — drill 패널→계정별 독립 차트 복원, 프로필 usage 탭/엔드포인트 제거, audits 탭/JS 복원.

## CHG-20260610-0184-COSTCHART
- Date: 2026-06-10
- Related Requirement: TASK-0184 (A drill-down 누락 보강 — 사용자 지적 "계정별 비용 차트 누락")
- Summary: A drill-down 전환 시 계정별 독립 차트(토큰+비용) 2종을 모두 제거하고 drill 패널에 **토큰만** 넣어 계정별 비용이 사라졌다(역할별은 토큰|비용 둘 다 유지). drill 패널 body 를 **[토큰 | 비용] 2열**(`usageDrillChart`/`usageDrillCostChart`, `.admin-usage-drill-charts` flex, 좁으면 wrap)로 재구성하고 `renderAccountDrill` 이 토큰(`total_tokens`/num)·비용(`cost_usd`/usd) 막대를 함께 렌더(빈 검색·접힘 시 둘 다 클리어). by_account 응답엔 이미 `cost_usd` 포함 — 백엔드 무변경. 캐시버스터 `?v=20260610-usage-drill2`(admin).
- Files:
  - unit/feature-0003-agent-web-ui/src/static/admin.html (drill body → 토큰|비용 2열 + 캐시버스터)
  - unit/feature-0003-agent-web-ui/src/static/admin.js (`renderAccountDrill` 비용 차트 렌더 + 접힘/빈검색 클리어)
  - unit/feature-0003-agent-web-ui/src/static/styles.css (`.admin-usage-drill-charts`/`-col`)
- Rollback: drill body 를 단일 `usageDrillChart`(토큰만)로 환원.

## CHG-20260610-0198
- Date: 2026-06-10
- Related Requirement: TASK-0198 (사용자 요청 — LLM 사용량 모델별 분리/선택 차트 + 좌우 스크롤 제거)
- Summary: `관리 콘솔 > 감사 > LLM 사용량` 상단 대시보드가 종합만 보이고 모델별 분리/선택 불가 + 좌우 스크롤 불편 해소. **(A) 모델 필터·분리**: 상단 모델 칩 바(`#usageModelFilter`)로 전체/모델 다중 토글, 선택 모델 기준으로 요약·일별·도넛·역할·계정 차트/표를 클라이언트 재계산(`buildView`)으로 좁힘. `loadUsage` 가 응답을 days|gran 키로 캐시(`_lastRaw`)하고 칩 토글은 재조회 없이 재렌더(`refetch:false`). 모델 키=`COALESCE(resolved_model,model)`. 부분 선택 시 역할·계정 표의 요청·호출은 모델 횡단이라 `—`(토큰·비용은 기여분 재합산으로 정확). **(B) 모델별 요약 카드**: 합계 카드(스코프 라벨) + 모델별 분리 카드(토큰/요청/호출/비용, 클릭 시 단독 선택). **(C) 좌우 스크롤 제거**: usage pane `overflow-x:hidden`, flex `min-width:min(Npx,100%)`, 넓은 표는 카드 내부 `overflow-x:auto`. `color-mix`/`--accent` 미사용 → `--primary`/`--primary-soft` 토큰. 백엔드/API/스키마/RBAC/시크릿 무변경(읽기 전용 집계 표시만). 캐시버스터 `?v=20260610-usage-model-filter2`. PB-0008 Windows-browser 검증 시 전체 모델 상태에서 세로 스크롤바(15px) 등장으로 인한 잔여 6px 측정값을 추가 차단 — usage pane summary-metrics `minmax(min(160px,100%),1fr)` + pane 직접 자식 `min-width:0;max-width:100%`. `userCanScrollHorizontally:false` 확정(TEST.md §3).
- Files:
  - unit/feature-0003-agent-web-ui/src/static/admin.js (`loadUsage` 모델 필터 상태·`buildView`·`renderModelFilter`·모델별 요약 카드·view 기준 렌더·부분선택 `—` 처리)
  - unit/feature-0003-agent-web-ui/src/static/admin.html (`#usageModelFilter` 컨테이너 + admin.js/styles.css 캐시버스터 `usage-model-filter2`)
  - unit/feature-0003-agent-web-ui/src/static/styles.css (가로 스크롤 차단[overflow-x:hidden + min-width:min(Npx,100%) + pane 자식 min-width:0/max-width:100% + summary minmax min()] + `.admin-usage-filter`/`-chip`/`-mcard*` 스타일)
  - unit/feature-0003-agent-web-ui/tests/win-browser-task0198-usage.scenario.json (PB-0008 검증 시나리오 신규)
  - unit/feature-0003-agent-web-ui/docs/{TASK,FUNCTION,REVIEW,TEST}.md (명세·이력·검증 기록)
- Rollback: 캐시버스터 환원 + `loadUsage` 를 직접 `data` 렌더로 되돌리고(`buildView`/필터 칩 제거), `#usageModelFilter` div 와 `.admin-usage-filter`/`-chip`/`-mcard*` CSS·`overflow-x`·`min-width` 변경 제거.

## CHG-20260610-0202
- Date: 2026-06-10
- Related Requirement: TASK-0202 (사용자 요청 — LLM 사용량 "모델별" 모델 전환 애니메이션 + 비선택 dim/이탈 시 사라짐)
- Summary: `관리 콘솔 > 감사 > LLM 사용량` "모델별" 카드(`.admin-usage-mcards`)에서 모델 카드 클릭(solo 선택) 시 비선택 카드가 즉시 사라져 불편하던 것을 개선. (1) 카드를 필터된 `view.by_model` 대신 **전체 `data.by_model`** 로 항상 렌더(카드 수치는 각 모델 고유값이라 선택 무관) — 비선택 카드가 DOM 에서 제거되지 않음. 선택=`is-active`·비선택=`is-dimmed`, 컨테이너에 `is-filtering`(부분 선택 시만). (2) CSS: `.admin-usage-mcard` 에 opacity/transform 트랜지션, `.is-filtering .is-dimmed`=흐림(opacity .4, hover 시), `.is-filtering:not(:hover) .is-dimmed`=fade-out(opacity 0+scale .92+pointer-events none), `prefers-reduced-motion` 가드. (3) JS hover 생명주기: 영역 이탈 fade-out 종료(`transitionend opacity`)시 `display:none` 회수(active 카드 제외), 재진입 시 reflow 기반 0→.4 fade-in 복구, 칩 바 필터링 등 마우스 영역 밖 재렌더는 초기 transition 미발동이라 동기 `display:none` 회수(유령 카드 방지). 백엔드/API/스키마/RBAC/시크릿/`buildView`/차트·표(전부 `view.*` 유지) 무변경 — 카드 렌더 소스와 표현만 변경. 캐시버스터 `?v=20260610-usage-model-anim`.
- Files:
  - unit/feature-0003-agent-web-ui/src/static/admin.js (`loadUsage` 모델별 카드 렌더를 `data.by_model` 전체+active/dimmed, `is-filtering` 컨테이너, transitionend/mouseenter 생명주기 + 동기 회수)
  - unit/feature-0003-agent-web-ui/src/static/styles.css (`.admin-usage-mcard` 트랜지션 + `.is-filtering`/`.is-dimmed` dim/접힘 규칙 + reduced-motion)
  - unit/feature-0003-agent-web-ui/src/static/admin.html (캐시버스터 `usage-model-filter2` → `usage-model-anim`)
  - unit/feature-0003-agent-web-ui/docs/{TASK,MODIFY,REVIEW}.md (명세·이력·검증 기록)
- Rollback: 캐시버스터 환원 + 카드 렌더를 `view.by_model` 직접 렌더(soloActive 단일 강조)로 되돌리고 `is-filtering`/`is-dimmed`/transitionend·mouseenter 핸들러 제거, styles.css 의 `.is-filtering`/`.is-dimmed` 규칙·opacity/transform 트랜지션·reduced-motion 블록 제거.

## CHG-20260611-0204
- Date: 2026-06-11
- Related Requirement: TASK-0204 (사용자 피드백 — TASK-0202 모델 카드 hover 동작 불편/의도치 않음 → '모델별' 카드 제거 + 칩 토큰수 제거)
- Summary: `관리 콘솔 > 감사 > LLM 사용량` 요약 영역의 '모델별' 분리 카드 그리드(`.admin-usage-mcards`, TASK-0198 도입·TASK-0202 애니메이션)를 **제거**한다. 사용자 라이브 사용에서 모델 카드 클릭 시 비선택 카드가 즉시 사라지고(빈 공간) hover 결합 dim/접힘이 re-render·마우스 이동과 충돌해 잭을 유발 → 상단 '모델' 칩 바 + '전체' 가 모델별 분리/선택을 이미 담당하므로 중복 섹션을 폐기. (1) admin.js `loadUsage`: mcards 빌드 + 카드 클릭/transitionend/mouseenter/동기회수 핸들러 제거 → `summaryEl.innerHTML = totalsHtml`(합계 카드만). (2) admin.js `renderModelFilter`: 칩 버튼 내 토큰수(`admin-usage-chip-tok`) 및 '전체' 토큰수 제거(모델명만), 미사용 `tokByKey`/`t` 파라미터 정리. (3) styles.css: `.admin-usage-mcards*` + `.admin-usage-chip-tok` 규칙 제거(dead). 모델 토큰량은 '모델별 비중' 도넛·일별 차트·상세 표에 유지. `buildView`/차트/표 무변경(회귀 0), 백엔드/API/스키마/RBAC 무변경. 캐시버스터 `?v=20260611-usage-no-mcards`.
- Files:
  - unit/feature-0003-agent-web-ui/src/static/admin.js (mcards 섹션·핸들러 제거, 칩 토큰수 제거, 미사용 정리)
  - unit/feature-0003-agent-web-ui/src/static/styles.css (`.admin-usage-mcards*`·`.admin-usage-chip-tok` 제거)
  - unit/feature-0003-agent-web-ui/src/static/admin.html (캐시버스터 → usage-no-mcards)
  - unit/feature-0003-agent-web-ui/docs/{TASK,MODIFY,FUNCTION,REVIEW}.md
- Rollback: TASK-0202 시점 admin.js/styles.css 환원(mcards 그리드+카드 클릭/hover 핸들러+`.admin-usage-mcard*`/`.admin-usage-chip-tok` CSS 복원) + 캐시버스터 환원.

## CHG-20260611-0205
- Date: 2026-06-11
- Related Requirement: TASK-0205 (사용자 요청 — 텍스트박스 Shift+Enter 줄바꿈 지원)
- Summary: composer 입력 텍스트박스(`promptInputEl`)의 `keydown` 핸들러에서 `event.shiftKey` 가 true 이면 즉시 `return` 하여 브라우저 기본 줄바꿈 동작을 허용한다. `sendMode` 설정("Enter 전송"/"Ctrl+Enter 전송")과 무관하게 Shift+Enter 는 항상 줄바꿈. 기존 Enter/Ctrl+Enter 전송 경로 무변경. 백엔드·API·스키마·RBAC 0.
- Files:
  - unit/feature-0003-agent-web-ui/src/static/app.js (promptInputEl keydown — Shift+Enter early return 1줄)
  - unit/feature-0003-agent-web-ui/docs/{TASK,MODIFY,REVIEW}.md
- Rollback: `if (event.shiftKey) return;` 1줄 제거.

## CHG-20260611-0206
- Date: 2026-06-11
- Related Requirement: TASK-0206 (사용자 피드백 — 쿼리 문자열 항상 표시, 실행결과셋 기본 숨김 토글)
- Summary: 답변 내 SQL 쿼리 문자열은 항상 표시하고, 실행결과셋(테이블/미리보기 데이터)을 `결과 보기` 버튼으로 기본 숨김·클릭 시 토글한다. ① `collapseSqlCodeBlocksInContent()` — ` ```sql ``` ` 코드블록 숨김 로직 제거(항상 표시). ② `buildSqlStepPanel()` — SQL `<pre>` 항상 표시, 결과 테이블+CSV 액션을 `sql-result-toggle-wrap`+`resultBody(hidden=true)`로 감싸고 `결과 보기/닫기` 토글. ③ `renderMessageDetails()` 구형 fallback — SQL 토글 제거(항상 표시). ④ `buildStepDetailEl()` 사이드 패널 — 결과셋(표/preview)을 `sql-result-toggle-wrap`+`resultBody(hidden=true)`로 감싸고 `결과 보기/닫기` 토글. ⑤ styles.css — `.sql-result-toggle-wrap`, `.sql-result-body` 규칙 추가. 백엔드·API·스키마·RBAC 0.
- Files:
  - unit/feature-0003-agent-web-ui/src/static/app.js (4개 함수 수정)
  - unit/feature-0003-agent-web-ui/src/static/styles.css (토글 래퍼 CSS 추가)
  - unit/feature-0003-agent-web-ui/docs/{TASK,MODIFY,REVIEW}.md
- Rollback: `collapseSqlCodeBlocksInContent` 원상복구 + `buildSqlStepPanel`·`buildStepDetailEl` 결과셋 토글 래퍼 제거 + styles.css `.sql-result-toggle-wrap`·`.sql-result-body` 제거.

## CHG-20260611-0207
- Date: 2026-06-11 (TASK-0207, **Minor §12.3** — 관리 콘솔 데이터소스 pane UI 표준화 + 수정/삭제 노출)
- Scope: `관리 콘솔 > 데이터소스` pane 을 계정/역할/제품/설정 과 동일한 list-detail 5단 구조(DESIGN.md §2)로 재구성하고 수정/삭제 액션을 상세 패널에 명시 노출. 프런트 전용 — 백엔드/API/스키마/RBAC/시크릿 무변경.
- 배경: 데이터소스 pane 만 표준 구조 미적용(`h3` + 평면 `admin-ds-list` + 미스타일 클래스 `admin-badge`/`admin-field`/`admin-row-actions`)이라 시각적으로 이질적. 수정(PATCH)/삭제(DELETE+force) 핸들러는 TASK-0205 에서 이미 구현됐으나 평면 행 우측 버튼에 묻혀 잘 안 보였음.
- 변경:
  - `src/static/admin.html`: 데이터소스 `<section data-admin-pane="datasources">` 를 `drawer-label`+`h2`+`admin-pane-head-right`(`#newDatasourceBtn`) 헤더 + `admin-list-detail`(좌 `admin-list-col`: `#datasourceSearch`/`#datasourceListCount`/`#datasourceList`, 우 `admin-detail-col` `#datasourceDetail`) 로 교체. 정적자산 캐시버스터 `?v=20260611-usage-no-mcards` → `?v=20260611-ds-admin-ui`.
  - `src/static/admin.js`: `renderDatasourcesPane` 전면 재작성(`#datasourcesPane`/`admin-ds-list`/`dsFormHost`/`_dsShowForm` 폐기 → `_dsRenderList`/`_dsSyncListActive`/`_dsRenderDetail`/`_dsRenderDetailEmpty`/`_dsRenderForm`/`_dsKvRow`). 목록 클릭→상세, 검색 필터(`adminState._dsSearch`, dataset.bound idempotent), 선택 상태(`adminState._dsSelectedKey`), 생성 후 canonical(소문자) key 자동 선택. `refreshPendingUI` 에 `#tabCountDatasources` 카운트 배지 추가. RBAC 게이트(console.manage·ds.editable·encryption-ready) 전부 보존.
  - `src/static/styles.css`: 미스타일 클래스 `admin-badge`(+`--muted`/`--warn`)·`admin-kv`(dl/dt/dd)·`admin-detail-title`·`admin-field`(+label·readonly)·`admin-row-actions` 표준 토큰 스타일 추가. (`admin-detail-head` 중복정의 제거 — 패널 리뷰 BLOCKER 수정, 기존 canonical 재사용.)
- 비변경: `/api/admin/datasources` CRUD/test/databases 엔드포인트·envelope 암호화·SSRF allowlist·RBAC·제품별 datasource 바인딩 UI(buildProductDetail) 무변경.
- 검증: node --check admin.js PASS. 패널([SUBAGENT:design-correctness]) SHIP-WITH-FIXES 5건 전부 수용. 빌드/배포 + Windows-browser(PB-0008) 시각검증은 배포 단계.
- Files: unit/feature-0003-agent-web-ui/src/static/{admin.html,admin.js,styles.css}, unit/feature-0003-agent-web-ui/docs/{TASK,MODIFY,REVIEW}.md
- Rollback: admin.html 데이터소스 section + admin.js `renderDatasourcesPane` 군 + styles.css 추가 블록을 TASK-0205 상태로 환원(기능 무관, 레이아웃만 평면 복귀).

## CHG-20260611-0208
- Date: 2026-06-11 (TASK-0208, **Minor §12.3** — 프로필 drawer 너비 조절 + 사용 내역 집계 단위)
- Scope: 사용자 요청 2건 — ① 프로필 사이드바(`#profileDrawer`)를 `단계 보기` 패널처럼 너비 드래그 조절 + 영속. ② `사용 내역` 탭 집계 단위(시간별/일별/월별) 셀렉터. 프런트 전용 — 백엔드/API/스키마/RBAC/시크릿 무변경.
- 배경: drawer 는 고정 폭 390px(모바일 380px) 이었고, 사용 내역 탭은 `gran=day` 하드코딩이라 시간/월 단위 조회 불가(백엔드 `/api/profile/usage` 는 TASK-0166 이후 `gran` hour/day/week/month 를 이미 지원했으나 프런트 컨트롤 부재).
- 변경:
  - `src/static/app.js`: (Task1) `PROFILE_DRAWER_WIDTH_KEY`/`PROFILE_DRAWER_MIN_W`/`_profileDrawerMaxW`/`_applyProfileDrawerWidth`/`setupProfileDrawerResize` 추가(단계 패널 `setupStepSidePanelResize` 미러). `openProfile` 가 setup+apply 호출. `_applyProfileDrawerWidth` 는 ≤680px 에서 inline 너비 미적용(미디어쿼리 소유). (Task2) `loadProfileUsage` 가 `#profileUsageGran` 값을 `GRAN_LABEL`(hour/day/month) 검증 후 `&gran=` 전달 + `#profileUsageTrendTitle` 동기화, `#profileUsageGran` change 리스너 추가.
  - `src/static/index.html`: `#profileDrawer` 첫 자식으로 `#profileDrawerResizer` + 내부 스크롤 래퍼 `.drawer-scroll`(헤더/탭/패널 래핑). 사용 내역 헤더에 `.profile-usage-controls` + `#profileUsageGran` 셀렉터(시간별/일별/월별). 캐시버스터 `?v=20260610-response-duration` → `?v=20260611-profile-resize-gran`.
  - `src/static/styles.css`: `.drawer` 에서 padding/gap/overflow-y 제거 + `overflow:hidden`(비스크롤 shell), 신규 `.drawer-scroll`(flex:1·min-height:0·overflow-y:auto·padding·gap) 으로 스크롤 이동. `.drawer.is-resizing`·`.drawer-resizer`(+`::before`·hover) 추가(단계 패널 리사이저 패턴). `.profile-usage-controls`(flex row).
- 비변경: `/api/profile/usage` 엔드포인트·RBAC·집계 SQL·단계 보기 패널 코드·기타 drawer 탭 로직 무변경.
- 검증: node --check app.js PASS, styles.css 중괄호 911/911, drawer aside div 30/30. 패널([SUBAGENT:design-correctness], REV-20260611-0208) SHIP-WITH-FIXES — MAJOR(스크롤 분리)+MINOR(모바일 가드) 수정 후. 빌드/배포 + Windows-browser(PB-0008) 시각검증은 배포 단계.
- Files: unit/feature-0003-agent-web-ui/src/static/{app.js,index.html,styles.css}, unit/feature-0003-agent-web-ui/docs/{TASK,MODIFY,REVIEW}.md
- Rollback: app.js 추가 함수군 + index.html 리사이저/`.drawer-scroll`/gran 셀렉터 + styles.css 추가/변경 블록 환원(기능 무관, drawer 고정폭·사용내역 일별 고정 복귀).

## CHG-20260611-0209
- Date: 2026-06-11 (TASK-0209, **Minor §12.3** — 관리 콘솔 LLM 사용량 드롭다운 순서 정렬)
- Scope: `관리 콘솔 > LLM 사용량` 헤더의 집계범위/집계기준 드롭다운 순서를 프로필 `사용 내역`(TASK-0208)과 동일하게(집계기준 먼저) 정렬. 프런트 전용 — 백엔드/API/스키마/RBAC/시크릿/JS/CSS 무변경.
- 배경: 프로필 사용 내역 탭은 집계기준(gran)→집계범위(days) 순인데, 관리 콘솔은 반대(days→gran)라 두 화면 일관성 결여. 사용자가 관리 콘솔을 프로필 순서에 맞춰달라 요청.
- 변경 (`src/static/admin.html`): `.admin-pane-actions` 내 `#usageGranSel`(시/일/주/월) 을 `#usageDaysSel`(최근 N일) 앞으로 이동(형제 순서 교체). 캐시버스터 `?v=20260611-ds-admin-ui` → `?v=20260611-usage-dropdown-order`.
- 비변경: `admin.js` 의 두 select id 참조·change 핸들러·`/api/admin/usage` 호출·집계 로직 무변경(순서 무관). RBAC/엔드포인트/스키마 무변경.
- 검증: admin.html select 태그 균형(4/4). 빌드/배포 + Windows-browser(PB-0008) 시각검증은 배포 단계. outside-voice [SKIPPED:frontend-trivial-reorder] (REV-20260611-0209).
- Files: unit/feature-0003-agent-web-ui/src/static/admin.html, unit/feature-0003-agent-web-ui/docs/{TASK,MODIFY,REVIEW,FUNCTION}.md
- Rollback: 두 select 의 순서를 원위치(days→gran)로 환원.

## CHG-20260611-0213
- Date: 2026-06-11 (TASK-0213, **Minor §12.3** — 접근 가능 DB 선택 드롭다운+체크박스)
- Scope: `관리 콘솔 > 제품 > 접근 가능 데이터베이스` picker UI 를 드롭다운+체크박스 연속 토글 방식으로 교체. RBAC·API 계약·스키마 신규 0.
- 배경: 기존 `<select>` + `+ 추가` 버튼 패턴은 DB 여러 개를 등록할 때 드롭다운 선택 → 버튼 클릭을 반복해야 해 불편. 체크박스 드롭다운으로 연속 토글 가능하게 개선.
- 변경:
  - `unit/feature-0003-agent-web-ui/src/static/admin.js`: `buildPicker()` 체크박스 드롭다운 패널 방식으로 재작성, `pickerSelect`/`pickerAddBtn`/`pickerRow` → `pickerDropBtn`/`pickerDropList`/`pickerWrap`. 항목 체크 시 즉시 draft push+setProductDatabasesPending+redrawChips, 언체크 시 즉시 draft splice. 패널 외부 클릭 닫기. `_refreshAccessibleDbs` 내 `buildPicker()` 호출 유지.
  - `unit/feature-0003-agent-web-ui/src/static/styles.css`: `.admin-db-picker-wrap/.admin-db-picker-btn/.admin-db-picker-list/.admin-db-picker-item/.admin-db-picker-empty` 신규.
  - `unit/feature-0003-agent-web-ui/src/static/admin.html`: 캐시버스터 `?v=20260611-db-picker-checkbox`.
  - `unit/feature-0002-agent-core/src/modules/db.py`: `_connect_mssql` 의 `db_name` 폴백 `""` → `"tempdb"` (중립 DB, 무자격 참조 누출 차단).
  - `unit/feature-0002-agent-core/src/app.py`: `admin_create_datasource`/`admin_update_datasource` 에서 `default_db` 필드 갱신 제거(NULL 고정).
  - `unit/feature-0002-agent-core/tests/test_multi_datasource.py`: `test_connect_engine_dispatch_mssql_uses_pymssql` 기대값 `"" → "tempdb"` 수정.
- 비변경: RBAC·API 계약·WebDatasources 스키마·`_refreshAccessibleDbs`·고정칩 렌더링 무변경.
- 검증: node --check admin.js PASS. verify-completion PASS. 빌드/배포 + PB-0008 시각검증은 배포 단계.
- Files: unit/feature-0003-agent-web-ui/src/static/{admin.html,admin.js,styles.css}, unit/feature-0002-agent-core/src/modules/db.py, unit/feature-0002-agent-core/src/app.py, unit/feature-0002-agent-core/tests/test_multi_datasource.py, docs/{TASK,MODIFY,REVIEW}.md
- Rollback: admin.js picker 교체 전 상태(select+추가버튼) + styles.css picker-wrap 블록 제거 + db.py `""` 복원 + app.py default_db 복원.

## CHG-20260611-0213-docs
- Date: 2026-06-11 (TASK-0213 docs cycle — verify-completion PASS 확인 후 docs 보완)
- Scope: TASK-0213 문서 보완 (REVIEW.md REV 엔트리 추가, MODIFY.md 검증 상태 갱신).
- Files: unit/feature-0003-agent-web-ui/docs/{TASK,MODIFY,REVIEW}.md

## CHG-20260611-0216
- Date: 2026-06-11 (TASK-0216, **Minor §12.3** — 데이터소스 키 자동 생성: 엔진+호스트+포트 해시)
- Scope: `관리 콘솔 > 데이터소스` 항목의 키를 식별자 문자열에서 `엔진+호스트+포트` SHA-256 해시(앞 12자 + 엔진 태그)로 변경. 기존 `main_mysql` 레거시 키 자동 마이그레이션 포함.
- 배경: 식별자 문자열 키(`main_mysql` 등)는 엔드포인트 용도가 바뀔 때 기존 키가 그대로 남아 대응이 어려웠음. 해시 키는 동일 엔드포인트=항상 동일 키(멱등), 엔드포인트 변경 시 자동으로 다른 키가 발급되어 명확히 구분된다.
- 변경:
  - `unit/feature-0003-agent-web-ui/src/app.py`:
    - `_generate_datasource_key(engine, host, port)` 신규 함수: `{engine}:{host}:{port}` SHA-256 해시 앞 12자 + 엔진 태그 → `{engine}-{hash12}` 형식. `_ds_valid_key` 제약(소문자 영숫자·_·-, `ds` 시작 금지) 통과.
    - `admin_create_datasource`: body `key` 수신 제거 → `_generate_datasource_key` 자동 생성. 409 에러 메시지 상세화("동일 엔드포인트가 이미 등록되어 있습니다"). 응답 `default_db` 미정의 버그 → `None` 명시.
    - `_seed_main_mysql_datasource`: `key = "main_mysql"` → `key = _generate_datasource_key("mysql", DB_HOST, int(DB_PORT))`. 레거시 `main_mysql` 키 존재 시 해시 키로 rename + `WebProducts.DatasourceKey` 참조 일괄 UPDATE(운영 연속성 보장, 멱등).
  - `unit/feature-0003-agent-web-ui/src/static/admin.js`:
    - `_dsRenderForm`: 신규 생성 시 key 입력 필드 제거, 자동 생성 안내 힌트 추가. 수정 시는 key readonly 표시 유지. body 전송 시 `key` 필드 제외(`k !== "key"` 가드). 생성 완료 토스트 "(키 자동 생성)" 메시지 추가.
- 비변경: `_migrate_env_datasources_to_db`(`.env` 레거시 경로 — 의도적 유지), RBAC(console.manage), API 계약(수신 필드에서 `key` 제거만), WebDatasources 스키마, DEK/KEK 암호화 경로.
- 검증: py_compile app.py PASS, node --check admin.js PASS.
- Files: unit/feature-0003-agent-web-ui/src/app.py, unit/feature-0003-agent-web-ui/src/static/admin.js, unit/feature-0003-agent-web-ui/docs/{TASK,MODIFY,FUNCTION,REVIEW}.md
- Rollback: `_generate_datasource_key` 제거 + `admin_create_datasource` body key 수신 복원 + `_seed_main_mysql_datasource` `"main_mysql"` 복원 + `_dsRenderForm` key 입력 필드 복원.

## CHG-20260611-0217
- Date: 2026-06-11 (TASK-0217, **Minor §12.3** — 데이터소스 해시 키 버그 수정 2건)
- Scope: TASK-0216 후속 버그 2건 — ① `main_mysql` 마이그레이션 시 패스워드 AAD 재암호화 누락, ② PATCH 수정 시 키 재생성 미처리.
- 배경: AESGCM 암호화에서 AAD=DatasourceKey를 사용하기 때문에, 키 이름이 바뀌면 동일 DEK로도 복호가 실패(InvalidTag)한다. TASK-0216에서 `main_mysql` → 해시 키로 rename할 때 PasswordEnc를 재암호화하지 않아 부팅 시마다 `datasource_decrypt_failed` 오류로 데이터소스가 전부 skip됐다.
- 변경:
  - `unit/feature-0003-agent-web-ui/src/app.py`:
    - `_seed_main_mysql_datasource`: rename 전 `PasswordEnc, EncryptionVersion` 조회 → DEK 로드 → 복호 → 새 키 AAD로 재암호화 → `UPDATE ... DatasourceKey=%s, PasswordEnc=%s, EncryptionVersion=%s` 원자적 처리. 복호 실패 시 기존 암호문 유지(silent pass).
    - `admin_update_datasource`: 기존 `SELECT Id` → `SELECT Engine, Host, Port, PasswordEnc, EncryptionVersion`. 변경 후 새 해시 키 계산(`_generate_datasource_key`), 키 변경 시: ① 패스워드 입력 있으면 새 키 AAD로 암호화, ② 패스워드 입력 없으면 기존 패스워드를 복호 후 새 키 AAD로 재암호화(실패 시 500 + 직접 입력 안내). `DatasourceKey` 업데이트 + `WebProducts.DatasourceKey` 참조 업데이트. 응답에 `key_changed: bool` 추가.
  - `unit/feature-0003-agent-web-ui/src/static/admin.js`:
    - `_dsRenderForm` save 핸들러: `await apiFetch(PATCH)` 응답의 `key`(`updated.key || ds.key`)로 `_dsSelectedKey` 동기화 → 키 변경 후에도 목록 선택 유지.
- 비변경: RBAC(console.manage), 신규 엔드포인트, WebDatasources 스키마, DEK/KEK 키 구조. 암호화 알고리즘(AESGCM) 동일.
- 검증: py_compile app.py PASS, node --check admin.js PASS.
- Files: unit/feature-0003-agent-web-ui/src/app.py, unit/feature-0003-agent-web-ui/src/static/admin.js, unit/feature-0003-agent-web-ui/docs/{TASK,MODIFY,FUNCTION,REVIEW}.md
- Rollback: app.py 두 함수 변경 전 상태 복원 + admin.js save 핸들러 `ds.key` 직접 참조 복원.

## CHG-20260611-0218
- Date: 2026-06-11
- Task: TASK-0218 (데이터소스 키 명시적 rename 지원 + AAD 자가수복), **Minor §12.3**
- 변경:
  - `unit/feature-0003-agent-web-ui/src/app.py`:
    - `_seed_main_mysql_datasource`: `main_mysql` 행이 DB에 없을 때(이미 rename됨)의 `else` 브랜치 추가. 해시 키 행의 `PasswordEnc` 를 현재 키 AAD로 복호 시도 → 실패 시 구 AAD(`main_mysql`)로 복호 → 성공 시 현재 키 AAD로 재암호화하는 자가수복 로직. 복호 완전 실패 시 silent pass(수동 재입력 필요).
    - `admin_update_datasource`: PATCH body `key` 필드 수신 추가 — `_ds_valid_key`로 검증 후 `explicit_new_key` 로 처리. `new_k` 결정 순서: ① 명시 키(`body.key`, 현재 키와 다를 때) ② 엔진+호스트+포트 해시 재계산. 기존 패스워드 재암호화·`DatasourceKey` 업데이트·`WebProducts.DatasourceKey` 참조 업데이트 경로 동일. 409 에러 메시지 간결화.
  - `unit/feature-0003-agent-web-ui/src/static/admin.js`:
    - `_dsRenderForm`: 수정(`isEdit`) 시 key 필드 `readonly` → `false`(편집 가능), `is-readonly` CSS 클래스 제거. 라벨 "키" → "키 (변경 시 수정)".
    - `_dsRenderForm` save 핸들러: `k === "key"` 분기 추가 — 수정 시 값이 원래 키와 다를 때만 `body.key = v` 로 전송, 신규 생성 시 미전송 유지.
- 비변경: RBAC(console.manage), 신규 엔드포인트, WebDatasources 스키마, DEK/KEK 키 구조, 암호화 알고리즘(AESGCM).
- 검증: py_compile app.py PASS, node --check admin.js PASS.
- Files: unit/feature-0003-agent-web-ui/src/app.py, unit/feature-0003-agent-web-ui/src/static/admin.js, unit/feature-0003-agent-web-ui/docs/{TASK,MODIFY,FUNCTION,REVIEW}.md
- Rollback: app.py `else` 브랜치 제거 + `admin_update_datasource` `explicit_new_key` 로직 제거. admin.js key 필드 `readonly=true` 복원.

## CHG-20260611-0223
- Date: 2026-06-11
- Task: TASK-0223 (제품별 insight-worker 분석 완료율 UI), **Major §12.3** (read-only 통계, RBAC·스키마·암호화·외부계약 변경 0)
- 변경:
  - `unit/feature-0002-agent-core/src/modules/db.py`:
    - 신규 `list_information_schema_tables(datasource, *, schemas, database, timeout, cap)`: datasource 의 `information_schema.TABLES` 에서 `(schema, table)` 객체 목록을 **flag-무관 직결**로 열거(`list_server_databases_classified` 패턴 — `connect()` 의 flag-gated datasource 경로 우회). MySQL=`TABLE_SCHEMA IN (schemas)`(VIEW 포함, insight 정합), MSSQL=`database` 1개 컨텍스트 + `_MSSQL_SYSTEM_SCHEMAS` 제외. 신규 상수 `_MSSQL_SYSTEM_SCHEMAS`.
  - `unit/feature-0003-agent-web-ui/src/app.py`:
    - 신규 헬퍼 `_compute_product_insight_coverage(conn, product)`: 제품 accessible DB 기준 분석 완료율 산출. 분자=PG `rag_objects`(conv=`__insight_worker__`, scope=`common`, object_type∈{schema,table}) 의 통찰 보유 객체, **catalog-driven 매칭**(라이브 (schema,table) ∩ rag (schema,table), set dedup). datasource 스코핑=`_dsr.scope_key`(엔드포인트 해시); 기본 엔드포인트면 `datasource_key IS NULL`(ds=None 스캔)도 허용. 분모 연결은 resolve 된 datasource RO 좌표(SSRF 가드+pinned IP, timeout 5s, per-datasource 실패 격리). MSSQL 비-default_db 접근DB=미스캔(analyzed 0+flag).
    - 신규 엔드포인트 `GET /api/admin/products/insight-coverage` (`admin_products_insight_coverage`): `console.access`. `?product_id=` 단건, `?refresh=1` 캐시 무시. 인메모리 TTL 캐시(90s) `_INSIGHT_COVERAGE_CACHE` + 헬퍼.
  - `unit/feature-0003-agent-web-ui/src/static/admin.js`:
    - `adminState.productCoverage`(Map)+`productCoverageLoading`. `loadProductInsightCoverage()` (loadAdminData 후 fire-and-forget). `buildCoverageBadge`(목록 row 배지)+`buildProductCoverageDetail`(상세 전체%+per-DB breakdown+새로고침)+`_coverageTone`. `renderProductList` row 에 배지, `renderProductDetail` 접근 가능 DB 섹션에 breakdown 삽입.
  - `unit/feature-0003-agent-web-ui/src/static/styles.css`: `.cov-badge`/`.cov-bar`/`.cov-db-row` 등 완료율 시각 스타일(등급별 색: ok≥80/warn≥40/low/muted).
  - `unit/feature-0003-agent-web-ui/src/static/admin.html`: 캐시버스터 `?v=20260611-insight-coverage`.
- 비변경: RBAC 카탈로그, WebProducts/WebProductDatabases/rag_objects 스키마, 암호화 경로, insight-worker write 경로. 기존 엔드포인트 계약.
- 검증: py_compile app.py+db.py PASS, node --check admin.js PASS, verify-completion(코드 게이트) + 라이브 실측 + PB-0008 Windows-browser.
- Files: unit/feature-0002-agent-core/src/modules/db.py, unit/feature-0003-agent-web-ui/src/app.py, unit/feature-0003-agent-web-ui/src/static/{admin.js,admin.html,styles.css}, unit/feature-0003-agent-web-ui/docs/{TASK,MODIFY,REVIEW}.md
- Rollback: app.py 신규 헬퍼·엔드포인트·캐시 제거 + db.py `list_information_schema_tables`/`_MSSQL_SYSTEM_SCHEMAS` 제거 + admin.js/styles.css/admin.html coverage 추가분 복원.

## CHG-20260611-0225
- Date: 2026-06-11
- Task: TASK-0225 (textarea 우측 하단 핸들 더블클릭 시 내용 높이로 자동 확장), **Minor §12.3** (비파괴 프런트 추가, 백엔드·RBAC·스키마·암호화·외부계약 변경 0)
- 변경:
  - 신규 `unit/feature-0003-agent-web-ui/src/static/textarea-autogrow.js`: document 레벨 `dblclick` capture 위임 핸들러. `resize: vertical|both` 인 textarea 에 한정, 더블클릭 좌표가 우측 하단 native resize 핸들 영역(`GRAB_PX=18`) 안일 때만 발동(본문 더블클릭=단어선택은 통과). `fitToContent`: `style.height="auto"` → `scrollHeight` 측정 → border-box 보정 후 적용, 상한 `MAX_PX=600`. capture phase 로 본문 선택 동작보다 먼저 핸들 영역 가로챔.
  - `unit/feature-0003-agent-web-ui/src/static/index.html`: `textarea-autogrow.js?v=20260611-dblclick-autogrow` script 태그 추가(app.js 다음).
  - `unit/feature-0003-agent-web-ui/src/static/admin.html`: 동 script 태그 추가(admin.js 다음). 동적 생성 `.admin-prompt-textarea` 도 capture 위임으로 자동 커버.
  - `unit/feature-0003-agent-web-ui/src/static/share.html`: 동 script 태그 추가(share.js 다음).
- 비변경: 백엔드(app.py 무수정), RBAC, 스키마, 암호화, 신규 엔드포인트, 기존 JS 의 promptInput auto-grow(input 이벤트) 로직. share.js 의 클립보드용 숨김 textarea 는 대상 아님(resize 핸들 없음).
- 검증: node --check textarea-autogrow.js PASS, verify-completion(코드 게이트), 배포 후 PB-0008 Windows-browser 시각검증 예정.
- Files: unit/feature-0003-agent-web-ui/src/static/textarea-autogrow.js, unit/feature-0003-agent-web-ui/src/static/{index,admin,share}.html, unit/feature-0003-agent-web-ui/docs/{TASK,MODIFY,REVIEW}.md
- Rollback: textarea-autogrow.js 삭제 + 3개 html 의 script 태그 1줄씩 제거.

## CHG-20260611-0226
- Date: 2026-06-11
- Task: TASK-0226 (MSSQL 제품 분석 완료율 미표시(연결) 수정 — per-DB 연결 격리; 동시세션 TASK-0225 충돌로 재번호 §13.1), **Minor §12.3** (TASK-0223 후속 버그수정, RBAC·스키마·엔드포인트 0)
- 진단: MSSQL 제품(`mssql_local`)이 "측정 불가" — RO 로그인 `agent_ro` 가 `dk_data_release` 만 GRANT(123 테이블, rag 123/123=100%), 나머지 4 DB 권한없음(18456). bug1=accessible DB 전체 단일 try/except → 한 DB 실패가 전체 오염. bug2=`scannable=default_db` 게이트(None)가 분석된 DB 마저 미스캔 처리.
- 변경:
  - `unit/feature-0003-agent-web-ui/src/app.py` `_compute_product_insight_coverage`: MSSQL 분기 **per-DB try/except 격리** — DB별 연결 실패는 `connected=False`+note, 나머지 정상 집계. `scannable`(default_db) → `connected` 대체. 비연결 DB 는 분모 제외. 전부 실패 시 reason. MySQL 경로는 단일 try 유지(회귀 0). `base["default_db"]` 추가(unused 제거).
  - `unit/feature-0003-agent-web-ui/src/static/admin.js`: per-DB 렌더 `d.scannable`→`d.connected`, 비연결="연결 불가"(cov-low). 배지/요약 "연결 불가" vs "대상 없음" 구분(per_db.connected===false 검사). total=0 도 per-DB 목록 노출. MSSQL 안내 "RO GRANT 없는 DB=연결 불가, 집계 제외".
  - `unit/feature-0003-agent-web-ui/src/static/admin.html`: 캐시버스터 `?v=20260611-mssql-coverage-perdb`.
- 비변경: RBAC, 스키마, 엔드포인트(`/api/admin/products/insight-coverage` 응답 shape 만 `scannable`→`connected`+`note` 확장), insight write, 매칭 의미론(catalog-driven 동일).
- 검증: py_compile app.py PASS, node --check admin.js PASS, make test + 라이브 실측 + PB-0008.
- Files: unit/feature-0003-agent-web-ui/src/app.py, unit/feature-0003-agent-web-ui/src/static/{admin.js,admin.html}, unit/feature-0003-agent-web-ui/docs/{TASK,MODIFY,REVIEW,FUNCTION,TEST}.md
- Rollback: app.py MSSQL 분기를 단일 try + scannable 게이트로 복원, admin.js connected→scannable 복원.

## CHG-20260611-0227
- Date: 2026-06-11
- Task: TASK-0227 (실행 단계 사이드 패널 갱신 시 "결과 보기" 펼침 상태 유지), **Minor §12.3** (frontend-only, RBAC·스키마·엔드포인트·백엔드 0)
- 진단: 실행 단계 사이드 패널(`#stepSidePanel`)에서 한 단계의 "결과 보기"를 펼쳐 결과셋을 보던 중, 폴링으로 새 단계가 추가되면 패널이 통째로 재렌더되며 펼쳐둔 결과셋이 닫힘. 근본 원인 = `_renderStepSidePanelBody`가 `body.innerHTML=""`로 전체를 비우고 재생성하는데, 펼침 여부가 DOM 로컬 변수(`resultBody.hidden`)로만 존재해 재렌더 시 기본값(닫힘)으로 리셋. (스크롤 위치는 이미 스냅샷/복원하던 비대칭.)
- 변경:
  - `unit/feature-0003-agent-web-ui/src/static/app.js`:
    - `state.stepResultExpanded`(Set) 신설 — 펼친 단계의 안정 키 영속화.
    - `_stepResultKey(step, idx)` 헬퍼 — `progressSteps` dedup과 동일한 `step_index:created_at` 키(둘 다 없으면 `idx:` fallback).
    - `buildStepDetailEl` 결과 토글: 초기 `hidden`/버튼 라벨/`aria-expanded`를 Set에서 복원, 토글 클릭 시 add/delete.
    - `resetProgressTracking` + `applyProgressPayload`의 runId 변경 분기에서 `state.stepResultExpanded.clear()` — run 전환 시 다른 run의 동일 step 키 혼동 방지.
  - `unit/feature-0003-agent-web-ui/src/static/index.html`: 캐시버스터 `?v=20260611-step-result-persist`.
- 비변경: 백엔드(app.py 무수정), RBAC, 스키마, 암호화, 엔드포인트, `buildSqlStepPanel`(완료된 채팅 메시지용 — run 완료 후 폴링 정지로 재렌더 안 됨, 본 버그 무관), progress strip 레거시 카드(`renderProgress`는 `buildStepDetailEl` 공용 → 동일 혜택).
- 검증: node --check app.js PASS, verify-completion(코드 게이트), 배포 후 PB-0008 Windows-browser 시각검증 예정.
- Files: unit/feature-0003-agent-web-ui/src/static/app.js, unit/feature-0003-agent-web-ui/src/static/index.html, unit/feature-0003-agent-web-ui/docs/{TASK,MODIFY,REVIEW}.md
- Rollback: app.js의 `state.stepResultExpanded`·`_stepResultKey`·토글 복원/저장·clear 4개 변경 되돌림, index.html 캐시버스터 복원.

## CHG-20260612-0245
- Date: 2026-06-12 (TASK-0245, **Minor §12.3** — 제품 상세 접근가능 DB 리스트 행 컬럼 정합)
- Scope: 관리 콘솔 제품 상세 `접근 가능 데이터베이스` 통합 리스트(`.cov-db-row`)의 컬럼 폭이 문자열 길이에 따라 들쭉날쭉하던 것을 고정폭 트랙으로 정렬. CSS 전용 — 백엔드/API/스키마/RBAC/시크릿 무변경.
- 배경: `.cov-db-row` 가 행 단위 `display:grid` 인데 `grid-template-columns` 의 통계·상태칩·초기화 컬럼이 `auto` 라 행마다 콘텐츠 폭(`37/37`↔`123/123`, `DB✓`↔`연결 불가`)이 달라짐 → 남는 폭을 분배받는 name/role `fr` 컬럼이 행마다 어긋나 역할설명·진척바 시작 x 불일치(green-line 보고).
- 변경 ([src/static/styles.css](../src/static/styles.css)):
  - `.cov-db-row` `grid-template-columns`: `minmax(56px,0.8fr) minmax(0,1.6fr) 96px auto auto auto 24px` → `minmax(96px,0.9fr) minmax(0,1.7fr) 96px 54px 76px 60px 24px` (통계 54·상태 76·초기화 60 고정).
  - `.cov-db-status` + `.cov-db-reset`: `justify-self: start` 추가 — 고정폭 컬럼에서 grid item stretch 로 pill/button 이 늘어나지 않고 자연폭 유지(좌측 정렬).
  - admin.html 캐시버스터 `?v=20260612-ds-picker-status` → `?v=20260612-db-row-align`.
- 비변경: `.cov-db-stat` 우측 정렬·마이크로바·셀 빌더(buildDbCoverageCells/buildDbRoleCell) JS·권한 게이트·데이터 무변경. 행 콘텐츠/구조 동일, 트랙 폭만 고정.
- 검증: CSS brace 균형 OK. 배포 후 PB-0008 Windows-browser 시각검증(행 간 정렬 일치).
- Files: unit/feature-0003-agent-web-ui/src/static/styles.css, unit/feature-0003-agent-web-ui/src/static/admin.html, unit/feature-0003-agent-web-ui/docs/{TASK,MODIFY,REVIEW,FUNCTION}.md
- Rollback: `grid-template-columns` 를 이전 값으로 환원 + `justify-self` 2줄 제거(정렬만 이전 들쭉날쭉으로 복귀, 기능 무관).

## CHG-20260612-0251
- Date: 2026-06-12 (TASK-0251, **Major §12.3 — 익명 공유뷰 데이터 노출 경계**) — 공유 페이지 SQL "쿼리 열고닫기" 토글을 의도된 "실행 쿼리 전환" navigator 로 교정 + 누락된 백엔드 steps 공급 + 익명 sanitize.
- Scope: `/share/{token}` 익명 공유 페이지의 SQL/결과 표시. ① share.js 가 본문 ```sql``` 블록을 "쿼리 보기/닫기" 열고닫기 토글로 감싸던 것(사용자가 본 그 버튼) 제거 → 본문 SQL 항상 펼침. ② 답변의 execute_sql 단계를 메인 UI 와 동일한 ◀▶ navigator(결과셋별 쿼리 전환)로 렌더. ③ 그 navigator 데이터(meta.steps)를 share API 가 공급하지 않던 것을 동적 조립로 보강. ④ 익명 노출이므로 step sanitize.
- 배경/진단(라이브):
  - share.js 의 `collapseSqlCodeBlocks` 가 markdown ```sql``` 블록을 토글로 감쌌다. 사용자 토큰(conv 20260612055236, msg id=554)은 meta=`{run_id,duration_ms}`뿐 + 본문에 ```sql``` 블록 → 정확히 이 토글이 노출됨.
  - 메인 UI(app.js)는 `meta.steps`(execute_sql 단계)를 `buildSqlNavigator` 로 전환하나, **share API(`_share_load_messages`→`_conv_load_messages_raw`)는 저장 `meta_json` 만 읽어 steps 가 없다**(라이브 PG: 저장 message meta 에 steps/result_summary 0건 — steps 는 일반 로드 경로가 `agent_runtime.steps` 에서 동적 조립). 즉 navigator 데이터 공급원이 share 경로에 부재.
- 변경:
  - [src/static/share.js](../src/static/share.js): `collapseSqlCodeBlocks` 제거(본문 SQL 항상 펼침). `renderAssistantDetails` 가 meta.steps 의 execute_sql 단계 렌더(1개=`buildSqlStepPanel`, 2+=`buildSqlNavigator` ◀▶ 전환 + "쿼리 N/M" + "대상: schema.table" + ←→Home End 키보드). 메인 UI helper 이식: `buildSqlStepPanel`/`buildSqlNavigator`/`buildPreviewTable`/`formatSqlForDisplay`(`` sentinel 포함)/`extractFirstTableRef` + `SQL_FORMAT_KEYWORDS` 상수. steps 없는 구형 메시지는 기존 `final_sql`/`result_rows` 폴백 유지.
  - [src/static/share.css](../src/static/share.css): `.share-sql-toggle-*` 제거, `.share-sql-navigator`/`.share-sql-group`/`.share-step-reason`/`.share-result-table-wrap` 신규(@media print 는 비활성 패널 모두 펼침).
  - [src/static/share.html](../src/static/share.html): 캐시버스터 `?v=20260610-share-md` → `?v=20260612-share-sql-nav`(share.js·share.css).
  - [src/app.py](../src/app.py): **(핵심)** `_share_attach_sanitized_steps` 신설 — `_share_load_messages` 가 assistant 메시지(redact 안 된)에 `_load_steps_for_message`(agent_runtime.steps)로 steps 동적 조립 → navigator 라이브 동작. **(보안)** `_share_sanitize_step` — 익명 노출용 화이트리스트 `{tool,sql,reason,intent,work,result_summary.preview_table}` 로 재구성(csv_paths[서버 `/shared/` 경로]·preview[결과 전문]·args·error 제거). `_SHARE_REDACTED_META_KEYS` 에 `steps` 추가(attachment_derived 메시지 redact + steps 재조립 skip 이중 차단).
- 보안(REV-20260612-0251, outside-voice 적대): BLOCKER(steps 경유 csv_paths/preview/args/error 익명 누출)→`_share_sanitize_step` 흡수(라이브 검증: step 직렬화에 csv_paths 0·preview 0·`/shared/out` 0). MINOR(sentinel 누락 주장)→오탐 기각(`cat -A` + 라이브 `LIMIT 10` 정상). XSS=textContent 일관 PASS. version gate=steps 재조립이 redact 안 된 assistant 메시지만 + attachment 항상 steps 제거로 정합.
- 비변경: RBAC 권한·DB 스키마·암호화·신규 엔드포인트 0(읽기 경로 steps 조립+sanitize). 메인 UI(app.js) 무변경.
- 검증: 신규/보강 4 테스트(steps redact·정상 steps 보존·sanitize 가 csv_paths/preview/args/error 제거·malformed 안전) + make test 컨테이너 **599 PASS(회귀 0, skip 2)** + ruff clean + node --check share.js + CSS brace 균형 + py_compile. Playwright 실 헤드리스 chromium 2종(mock + 라이브 sanitized 대화 20260527044221 id=128 8 execute_sql) ALL PASS.
- Files: unit/feature-0003-agent-web-ui/src/app.py, unit/feature-0003-agent-web-ui/src/static/{share.js,share.css,share.html}, unit/feature-0003-agent-web-ui/tests/test_share_redaction_invariant.py, unit/feature-0003-agent-web-ui/docs/{TASK,MODIFY,REVIEW}.md, unit/feature-0003-agent-web-ui/docs/reviews/20260612T010000Z-share-anonymous-exposure.md, docs/STATUS.md
- Rollback: share.js 의 `renderAssistantDetails` 를 final_sql/result_rows 단일 표시 + `collapseSqlCodeBlocks` 토글로 환원, app.py 의 `_share_attach_sanitized_steps` 호출/`_share_sanitize_step`/`steps` redact 키 제거(공유 페이지가 다시 본문 토글 + 단일 SQL 로 복귀).

## CHG-20260612-0252
- Date: 2026-06-12 (TASK-0252, **doc-only** — TASK-0251 PB-0008 Windows-browser 완료 게이트 기록)
- Scope: 문서 전용 — 코드/정적자산/스키마/RBAC 0. TASK-0251(공유 페이지 SQL navigator) 의 라이브 배포 후 PB-0008 Windows-browser 시각검증 PASS 결과를 TEST.md §4 에 기록하고 STATUS.md/TASK.md 의 잔여 항목을 완료로 갱신.
- 변경: TEST.md §4(TASK-0251 Windows-browser Run — 사용자 토큰 토글 0·본문 SQL 펼침 / steps 토큰 navigator "쿼리 1/8"↔"8/8" ▶◀ click hit-test 전환 / 익명 API csv_paths·preview 누출 0), STATUS.md(TASK-0251 잔여→완료), TASK.md(AC5 체크).
- 검증: doc-only — 코드 변경 없음(make test 무관). PB-0008 실측은 TASK-0251 배포본(main 9cee54a) 대상.
- Files: docs/STATUS.md, unit/feature-0003-agent-web-ui/docs/{TASK,TEST,MODIFY,REVIEW}.md
- Rollback: 문서 기록 제거(실제 시스템 영향 0).

## CHG-20260615-0256
- Date: 2026-06-15 (TASK-0256)
- Scope: 웹 UI 정적자산 — markdown ```diff 블록 렌더 + CSS. 백엔드/API/스키마/RBAC 0.
- 변경: app.js enhanceDiffBlocks(marked.parse→enhance→DOMPurify.sanitize) 신설 — <pre><code class="language-diff"> 를 라인별 <span class="diff-line ..."> 로 재구성(textContent 양방향, 새 HTML 주입 없음). share.js 동일 parity. styles.css/share.css diff 팔레트(다크 코드배경 #1a1b26/#1e293b 정합). index.html/share.html 캐시버스터 bump.
- 검증: node --check app.js/share.js PASS. 렌더 동작은 PB-0008(배포 후).
- Files: src/static/{app.js,share.js,styles.css,share.css,index.html,share.html}, docs/{TASK,MODIFY,FUNCTION,REVIEW}.md
- Rollback: enhanceDiffBlocks 호출 제거(원래 marked.parse 직접 sanitize) + CSS/캐시버스터 환원.
- Deploy: web 재빌드(정적자산 베이킹).

## CHG-20260615-0260
- Date: 2026-06-15 (TASK-0260)
- Scope: 웹 UI 정적자산 — 답변 SQL navigator(◀▶ 결과셋 전환) 확장 높이 보존. 백엔드/API/스키마/RBAC/CSS 0.
- 변경: `buildSqlNavigator`(app.js + share.js parity)에 navigator 인스턴스별 `maxPanelHeight` 추적 + `preserveHeight()`(panels.scrollHeight 가 더 크면 `panels.style.minHeight` floor 갱신) 추가. `update()` 가 전환 전(나가는 패널)·후(들어오는 패널) 2회 측정 → 본 적 있는 최대 높이를 바닥으로 박아 작은 결과셋으로 전환해도 panels 컨테이너 축소 안 됨(아래 콘텐츠/스크롤 점프 제거). 축소만 방지·확장 허용. min-height 는 JS inline 동적 설정(CSS 파일 무변경). index.html/share.html 캐시버스터 bump.
- 검증: node --check app.js/share.js PASS + Playwright headless chromium 격리 검증(큰 1000px→작은 2행 전환 panels.h 불변·점프 0px; 수정 전 대조 960px 점프 재현). 실 동작은 PB-0008(배포 후).
- Files: src/static/{app.js,share.js,index.html,share.html}, docs/{TASK,MODIFY,REPORT}.md, docs/STATUS.md(repo)
- Rollback: `preserveHeight()`/`maxPanelHeight` 제거 + `update()` 의 preserveHeight 2호출 제거 + 캐시버스터 환원(navigator 가 다시 활성 패널 높이로 컨테이너 재조정 = 점프 복귀).
- Deploy: web 재빌드(정적자산 베이킹).

## CHG-20260615-0261
- Date: 2026-06-15 (TASK-0261)
- Scope: 대화 화면 제품 드롭업 datasource 네트워크 상태 배지. app.py(read-only enrich) + 정적자산. RBAC/스키마/엔드포인트 shape 0.
- 변경: 신규 `_attach_product_conn_status(conn, products)`(app.py) — conn_health `snapshot()`(TASK-0250 모니터, 추가 probe 없음)을 `datasources.resolve(key)→scope_key` 로 매핑(admin all_datasources→scope_key 와 동일 키)해 각 product 의 datasources[] 에 `conn_status`{status,elapsed_ms,checked_at} + product 레벨 `conn_status_overall`(최악: unstable>unknown>healthy) 첨부. 좌표/비번 비노출, graceful(unknown), 바인딩없음 None. `get_session`(/api/session)·`auth_me`(/api/auth/me) 두 호출 직후 enrich(admin 경로 _list_products 무영향). frontend `buildProductDropupItem`(app.js) 가 `connStatusOverall`→dot `.product-dropup-item-dot--conn`+`.is-ok/.is-fail/.is-unknown`+title/aria-label, `connStatusMeta` 헬퍼, datasource 배지 tooltip 에 상태 라벨 병기. styles.css conn dot 색(specificity 0,3,0 override). index.html 캐시버스터 bump(styles.css·app.js).
- 검증: 신규 test_product_conn_status.py 8 PASS + make test 컨테이너 전체 회귀 0(PYTEST_EXIT=0) + ruff clean + node --check app.js + CSS brace(1128=1128) + py_compile + Playwright 격리(healthy=초록/unstable=빨강/unknown=중립/바인딩없음=파랑) + 라이브 conn_health 실측. 실 동작은 PB-0008(배포 후).
- Files: src/app.py, src/static/{app.js,styles.css,index.html}, tests/test_product_conn_status.py, docs/{TASK,MODIFY,REPORT,REVIEW,FUNCTION}.md, docs/STATUS.md(repo)
- Rollback: `_attach_product_conn_status` 호출 2곳 + 함수 제거(products 응답에서 conn_status/conn_status_overall 사라짐) + app.js connStatusMeta/dot conn 클래스 + styles.css conn dot 규칙 + 캐시버스터 환원(dot 가 모드색으로 복귀).
- Deploy: web 재빌드(app.py + 정적자산 베이킹). ask/insight-worker 무변경.
