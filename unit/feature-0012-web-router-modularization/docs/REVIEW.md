---
doc_type: REVIEW
feature_id: feature-0012-web-router-modularization
status: active
edit_policy: append-only
source_of_truth: true
---

# Review Records

> 이전 기록(31건): [REVIEW-archive-20260711T120729.md](./_archive/REVIEW-archive-20260711T120729.md)

## REV-20260701-0007 [SKIPPED:mechanical byte-neutral extraction — make test route-parity + static prefix-완전성 게이트; §18.8 byte-동치는 DI 전환(REV-0006)에서 수행]
- Related Change: CHG-20260701-0007 (admin/metadata 34 핸들러 → routers/admin_metadata.py 추출)
- 검증 성격: 추출은 라우트 경로·메서드·응답 불변 mechanical move(핸들러 코드 자체 무변경, `app.X` 참조 접두만). auth byte-동치(auth-sensitive)는 선행 DI 전환 REV-0006 §18.8 패널에서 검증 완료. 본 추출은 **route-parity(경로+메서드+순서) + make test 전체 + static prefix-완전성 검사**가 결함 게이트.
- 결정적 검증: (1) route-parity 골든 docker `_build_table` 재생성 = **set-neutral(added/removed 0), total 192 불변, 순서만 갱신**(34 metadata 라우트 include 순서상 끝 이동). (2) make test **1313 passed·0 fail·route drift 0**. (3) **make test 안전망이 추출 결함 1건 실적 적발**: `_SAMPLE_WEIGHT_MIN/_MAX`(튜플-대입 모듈상수) whitelist 누락 → NameError → 완전 mod_syms static 재검사(튜플/AnnAssign/import 타깃 포함)로 전수 0 확인 후 보정. (4) py_compile app.py+router OK. (5) 커플링 4유형 사전 grep: type1(직접호출)=재참조 완료, type2/3/4(monkeypatch·getsource·소스텍스트 contract)=metadata 핸들러 해당 0 확인. (6) 헬퍼 monkeypatch 보존: `_metadata_*`/`_connect_memory`/`record_audit_event` app.py 잔류 → router `app.X` 동적참조로 테스트 monkeypatch 계약 유지.
- app.py 28,224→26,734(~1,490↓, 단일 도메인 최대). routers 12개 / metadata 34 라우트 추출.
- 학습: whitelist mod_syms 는 튜플-대입 타깃까지 수집 필수(누락 시 router NameError, make test 적발). 추출 후 완전 mod_syms static 재검사를 골든 재생성 전 수행 = 조기 적발.
- 후속 배포: 컨테이너 로드(uvicorn web.app:app)에서 router import 는 기존 11 router 와 동일 `routers.<d>` 경로(신규 top-level 모듈 아님)라 web_context류 위험 없음 — 배포 blue-green healthz 게이트가 최종 안전망.
- **배포·라이브 검증 완료(main 0b91b1b, PR #506)**: blue-green soak 통과·healthz git_commit=0b91b1b·추출 admin_metadata 라우트 미인증 401 verbatim(`{"error":"로그인이 필요합니다."}`) — DI seam byte-동치 + 컨테이너 로드 import 프로덕션 확인. deploy_scope: included(전역 standing) 근거 자동 배포.

## REV-20260701-0008 [SKIPPED:deploy-record — 라이브 smoke 검증이 게이트; §18.8 byte-동치는 CHG-0006 REV-0006 에서 수행]
- Related Change: CHG-20260701-0008 (admin/metadata 마일스톤 배포·라이브 검증)
- 검증 성격: 코드 무변경 배포 기록. byte-동치 §18.8 은 DI 전환(REV-0006)에서, 추출 route-parity 는 REV-0007 에서 완료. 본 항목은 **프로덕션 라이브 smoke** 가 게이트.
- 결정적 검증: (1) CI test PASS(36s). (2) blue-green 배포 soak 90s 통과·롤백 없음. (3) 라이브 edge healthz git_commit=0b91b1b·status=ok(배포 커밋 일치). (4) 추출 admin_metadata 라우트 미인증 **401 verbatim** = DI seam(require_permission→get_current_account→_AuthError 401) 프로덕션 byte-동치 + 컨테이너 로드 router import 정상(web_context류 ModuleNotFoundError 없음 — healthz 게이트 통과가 입증). (5) insight/ask-worker GIT_COMMIT WARN = 별건(웹 배포 무관).
- 결론: admin/metadata 도메인 deploy-backed 완료.

## REV-20260701-0009 [SKIPPED:mechanical byte-neutral 전체추출 — make test route-parity + 커플링 6유형 grep + static missing-prefix 게이트]
- Related Change: CHG-20260701-0009 (6 도메인 35 핸들러 전체추출)
- 검증 성격: 추출은 라우트 경로/메서드/응답 불변 mechanical move(핸들러 코드 무변경, DEFER 는 인라인 auth 그대로, `app.X` 참조 접두만). auth 로직 변경 0(§18.8 byte-동치 불요). 게이트 = route-parity(경로+메서드+순서) + make test 전체 + static prefix-완전성 + 커플링 6유형 전수.
- 결정적 검증: (1) route-parity 골든 docker `_build_table` 재생성 = **set-neutral(added/removed 0), total 192 불변**. (2) make test **1313 passed·0 fail·route drift 0**. (3) **make test 안전망이 미포착 커플링 4건 실적 적발·수정**: `hasattr(app,"handler")` 3(→모듈), `app.app.routes` flat 순회 1(→재귀 walk). (4) 6 신규 router 가 docker(uvicorn web.app 컨테이너 로드)에서 정상 import(골든 재생성이 app 로드 성공으로 입증). (5) 추출기 self-healing missing-prefix static 재검사 clean, py_compile app.py+6 router OK.
- 커플링 6유형 확립(추출 전 grep): (1)`app.<h>(` 직접호출 (2)`monkeypatch.setattr(app,...)` (3)`getsource(app.<h>)` (4)소스텍스트 `read_text/ast.parse`+핸들러명 (5)`hasattr/getattr(app,"<h>")` 문자열-인자 (6)`app.app.routes` flat 순회. profile·integrations 는 커플링 0(TestClient+snapshot), 나머지 4 도메인은 getsource/hasattr/route-check 재참조.
- app.py 26,734→24,648(~2,086↓). 12→18 router. DEFER 핸들러(preauth) 인라인 auth 보존 = byte-identical.
- 학습: 핸들러 추출은 DI 전환 불요(monkeypatch 는 `app.X` 동적참조로 보존). DEFER byte-동치 DI-rework 는 향후 정제(현 목표=모듈화, 전체추출이 최단).

## REV-20260701-0010 [SKIPPED:mechanical byte-neutral 전체추출 — make test route-parity + 커플링 7유형 게이트]
- Related Change: CHG-20260701-0010 (datasources 6 + auth 18 전체추출)
- 검증 성격: mechanical route-preserving move(auth 로직 무변경, PUBLIC/DEFER 인라인 그대로). 게이트 = route-parity + make test + 커플링 전수.
- 결정적 검증: (1) 골든 재생성 set-neutral 192. (2) make test **1313 passed·0 fail·route drift 0**(2회 반복 — 1차 hasattr 루프 2 + source-text 호출식 count 1 적발, 2차 GREEN). (3) datasources CLEAN-DI 3(`_ds_write_common`)·auth PUBLIC 7(signup/login/oauth)·DEFER 5 전부 인라인 auth 보존 = byte-identical. (4) 2 신규 router docker 컨테이너 로드 정상(골든 재생성 app 로드 성공). (5) py_compile+static missing-prefix clean.
- 커플링 7유형 확립: 기존 6 + **(7) source-text 호출식 count**(helper 호출식을 app.py 소스에서 count — 추출 이동 시 변동, app.py+routers 합산 수정). auth_me 필터 호출이 auth.py 로 이동해 count 2→1 적발.
- app.py 24,648→23,536(~1,112↓). 18→20 router.
- 학습: 커플링 스캔은 핸들러명 grep 만으론 부족 — helper 호출식 count 형 source-text 검사(핸들러명 무참조)는 make test 가 최종 안전망. reref import guard 정확 매칭 필수.

## REV-20260701-0011 [SKIPPED:mechanical byte-neutral 전체추출 — make test route-parity + 커플링 8유형 게이트]
- Related Change: CHG-20260701-0011 (conversations 17 append + products 22 전체추출)
- 검증 성격: mechanical route-preserving move(auth 로직 무변경, DEFER/txn/streaming 인라인 그대로). conversations 는 기존 router append.
- 결정적 검증: (1) 골든 재생성 set-neutral 192. (2) make test **1313 passed·0 fail·route drift 0**(2회 — 1차 source-text contract 6 적발[test_group_conversation_s2 APP→APP_ALL·test_share_joinable_owner_guard getsource substring], 2차 GREEN). (3) products txn(admin_create/update/delete_product)·streaming(prompt/generate/stream)·pre-auth 전부 인라인 보존 byte-identical. (4) --append: 기존 conversations.py(10) + 신규 17 = 27 핸들러, NEW 블록 missing-prefix clean, 골든 재생성 app 로드 성공(컨테이너 import 정상). (5) py_compile OK.
- 커플링 8유형 확립: 기존 7 + **(8) getsource 컨텍스트-substring**(helper 앞 단어 포함 substring 이 `app.` 접두로 깨짐 — 단일 심볼명은 생존). test_share_joinable_owner_guard 의 `not _conversation_owned_by_account` 적발.
- app.py 23,536→20,542(~2,994↓, 단일 배치 최대). 20→21 router. **잔여 app.py 라우트 16(session 시작 148 대비 −132, 89% 추출)**.
- 학습: --append 모드로 도메인 재통합(conversations sub-resource 를 lifecycle router 로). source-text getsource 는 helper-접두에 취약 — make test 가 안전망.

## REV-20260701-0012 [SKIPPED:mechanical byte-neutral 전체추출 완주 — make test route-parity + 커플링 9유형 게이트]
- Related Change: CHG-20260701-0012 (잔여 16 라우트 append — 라우트 핸들러 전량 추출 완료)
- 검증 성격: mechanical route-preserving move. DEFER(long-poll/fail-soft/opt) 인라인 그대로. cross-call `ask` 는 내부 caller/monkeypatch 대상 모듈 전환.
- 결정적 검증: (1) 골든 set-neutral 192. (2) make test **1313 passed·0 fail·route drift 0**. (3) **잔여 @app 라우트 0**(148 전량 추출) — python AST 확인. (4) cross-call `ask`: 내부 caller(conversations.py post_fix_with_ai) `app.ask`→bare `ask`(동일 모듈), monkeypatch/hasattr/getsource `app.ask`→`conversations.ask`, post_fix_with_ai 가 bare `ask` 호출 → `conversations.ask` module global → monkeypatch 정합(make test 입증). (5) 4 router append(conversations/share/admin_console/system) 컨테이너 로드 정상(골든 재생성 app 로드 성공).
- 커플링 9유형: 기존 8 + **(9) cross-call 핸들러**(route 이자 내부 함수). `ask`(POST /api/ask, fix-with-ai 가 내부 호출) 유일.
- app.py 20,542→18,917(~1,625↓). **148 route 핸들러 전량 21 router 추출 — app.py = 헬퍼 라이브러리 + DI seam + include_router.**
- 잔여 아키텍처: app.py ~18.9k = **헬퍼**(web_context 미이동 — 원래 monkeypatch 블로커, 별도 workstream). route-handler 모듈화는 완주. 완전 thin-app 은 web_context 헬퍼 추출 필요(DI seam 선행).

## REV-20260702-0013 [SUBAGENT:batch4 bare-name namequal 회귀 — F821 완전성·객체동일성·부작용 4축 적대검증]
- Related Change: CHG-20260702-0013 (batch4 추출의 bare app-global/import 참조 `app.` 한정 — 라이브 500 3종 수정)
- 검증 성격: mechanical name-qualification(bare `X` → `app.X`, 6심볼/10개소). route-preserving, 동작 무변경 주장.
- §18.8 SUBAGENT 패널(general-purpose, 적대적 refute 지시) — **VERDICT: PASS**(BLOCKING 0, NIT 0). 4축 refute 전부 실패:
  - (1) **정확성**: 6심볼 전부 `app` 모듈 attribute — `MEMORY_DB`(app.py:99)·`LLM_QUOTA_ENFORCE`(app.py:758) 모듈레벨 정의, `load_memory_kv`·`mark_cancel_requested`·`set_run_status`·`mark_finalize_requested`(app.py:48–59 `from modules.memory import`). 세 라우터 모두 상단 `import app`. → NameError 해소.
  - (2) **완전성**: `ruff --select F821 routers/` → **All checks passed**(22 라우터 전체). ruff 검출력을 probe 주입으로 검증. 동적패턴(globals/getattr/star-import) 없음(유일 getattr 은 로컬 config 대상). 잔여 bare 3건은 주석/docstring(비실행). → 이 클래스 잔여 회귀 0.
  - (3) **회귀**: `app.X` == 원본 bare `X` 동일 객체 — app.py 에서 6심볼 재대입/shadow/재정의 없음(순수 re-export). cancel/finalize/history 의미 무변경.
  - (4) **부작용**: `git diff --check` whitespace 0, word-diff 제거10↔추가10 전부 `app.` 접두만, 문자열/들여쓰기 훼손 없음, HEAD 대비 신규 lint(F841/F401/F811) 0, py_compile PASS.
- 사전 검증: 관련 45 테스트 PASS(quota/history/finalize/product-conn-status/usage, CI PYTHONPATH 로 실행, exit 0 100%).
- deploy-backed: 배포 후 라이브 `GET /api/admin/databases/available`·`/api/history` 상태·`/api/cancel`·`/api/finalize` 500→200 재검증(§16.3).
- 학습: batch1~4 의 "byte-neutral" route-parity 게이트는 **테스트 미커버 핸들러의 NameError 를 놓쳤다** — 추출 게이트에 `ruff --select F821` 추가가 이 클래스 방어선.

## REV-20260702-0014 [SKIPPED:mechanical 골든 재생성 — diff 정확히 +1 legit route(#514 analyze/status), route_parity 테스트 PASS, runtime 무변경]
- Related Change: CHG-20260702-0014 (route-parity 골든 192→193 재생성 — CI red 해소)
- 검증 성격: test fixture(golden snapshot) 전용 재생성. 런타임 코드 무변경(web 이미지 미반영).
- 결정적 검증(패널 불요 사유 = auditable diff 가 검증 그 자체):
  - (1) drift 원인 정밀 식별: `_build_table()` ordered 를 (path,methods) 키로 골든과 diff → **정확히 +1**(`GET /api/admin/metadata/graph/analyze/status`), 제거 0·중복 0·재정렬 0.
  - (2) 추가 route 정당성: `admin_metadata.py:1013` 실핸들러 + `admin.js:3974` 프론트 실사용(그래프 AI 분석 상태 폴링). `git log -S` → feature-0016 `24445e94`(#514) 추가, 골든 미동반. → stale 확정(골든이 193 이어야 함).
  - (3) 재생성 결과 auditable: `git diff route_snapshot_p5b.json` = total_routes/api_routes 2줄 + analyze/status 블록만(9 ins/2 del). 다른 192 route 불변 → masking 없음.
  - (4) `test_route_parity_p5b` PASS(193/192).
- 범위 규율: 추가 route 는 feature-0016(#514) 소산이나 골든은 feature-0012 route-parity 안전망 소관 → feature-0012 유지보수 cycle 로 처리(route 출처 명기).

## REV-20260710T235820-item05-router-autoreg [SKIPPED:roadmap-spec-transcription] — 라우터 자동 등록 (parallel-work-structure ITEM-05)
- Related Change: CHG-20260710T235820-item05-router-autoreg. cycle: ai/claude-corp/feature-0012-item05-router-autoreg — `/_dqa:improve_cycle` 드레인 4번째 항목(ITEM-05, Minor). 승인: ROADMAP §6.1.
- SKIPPED 사유: what/acceptance/guards 는 ROADMAP ITEM-05 완전 명세(improve-fit-reviewer 2-round 기검증)의 전사. 인증·권한 로직 무접촉(등록 배선만) — auth 는 각 라우터 내부 Depends 불변, 등록 순서는 INCLUDE_ORDER 스냅샷으로 고정(shadow 역전 없음을 byte-동치 스냅샷이 기계 증명). §18.8 dispatch 비해당(API 표면 무변경 — 205 route in-order byte-동치).
- 검증(acceptance 전건): (a) 라우트 테이블 byte-동치 205 (b) ruff F821 clean (c) A/B pytest rc=0(route-parity 골든 포함) (d) 더미 라우터 app.py 무편집 등록 실증. batch4 교훈(F821 게이트) 선제 적용.
- 잔여 위험·완화: pkgutil 동적 import 는 모듈 import 부작용 순서를 파일명 순으로 바꿀 수 있으나, 全 라우터 모듈은 import 시점에 `from app import ...`/`import app` + APIRouter 선언만 수행(부작용 없음 — 기존에도 전량 import 됐음). INCLUDE_ORDER 누락 신규 모듈은 맨 뒤(기존 등록에 shadow 영향 없는 위치) 파일명 순.
- Human Approval Needed: 아니오 — Minor·byte-동치 기계 증명·§6.1. 배포는 §6.1 자동(web 재빌드+healthz/스모크, 실패 시 롤백+blocked).

## REV-20260711T100116-item10-webctx-batch1 [SKIPPED:roadmap-spec-transcription] — web_context 추출 batch1 (parallel-work-structure ITEM-10)
- Related Change: CHG-20260711T100116-item10-webctx-batch1. cycle: ai/claude-corp/feature-0012-item10-web-context — 드레인 10번째 항목(ITEM-10, Major) batch1. 승인: ROADMAP §6.1(코드 항목 10 명시 사전 승인).
- SKIPPED 사유: TASK-0012-8 이 명시한 "안전 영역(테스트 0변경)" inc3/inc4 의 전사 — 이동 대상·순서가 이전 세션의 ultracode 적대검증(Strategy B leaf-first, REV-0015/0016)으로 이미 확정된 경로. 인증·인가 semantics 무변경(순수 데이터/빌더 이동, 호출부 rebind — 403/401 메시지·권한 판정 로직 byte-동치). 기계 게이트 4종이 동치를 직접 증명: 스냅샷 byte-동치·F821·py_compile·전 스위트 pytest. 실측 1건(소스-계약 테스트 위치)은 계약 내용 무변경 위치 갱신(선례 batch4 ROUTERS 포함).
- 잔여 위험·완화: monkeypatch 되는 심볼 없음(사전 grep — 호출/상수 읽기만) · inspect.getsource 는 함수 객체 기준이라 이동 무관(web_context 소스 반환) · _legacy_permission_codes_from_row 등 잔류 심볼은 rebind 된 PERMISSION_CODES 를 그대로 참조.
- Human Approval Needed: 아니오 — §6.1. behavior-neutral 이동, 배포는 item 완료 시(§6.1 자동).

## REV-20260711T103000-item10-webctx-batch2 [SKIPPED:roadmap-spec-transcription] — web_context 추출 batch2 (parallel-work-structure ITEM-10)
- Related Change: CHG-20260711T103000-item10-webctx-batch2. cycle: ai/claude-corp/feature-0012-item10-webctx-b2. 승인: ROADMAP §6.1.
- SKIPPED 사유: batch1 과 동일 계보(leaf-first byte-동치 이동 + rebind) — 인증·인가 semantics 무변경(상수·seed 데이터·조회 함수만). 기계 게이트 4종(스냅샷 byte-동치·F821·py_compile·전 스위트 pytest rc=0)이 동치 직접 증명. 이동 전 monkeypatch 소비 grep 0 확인.
- Human Approval Needed: 아니오 — §6.1.

## REV-20260711T110000-item10-webctx-batch3 [SUBAGENT:improve-fit-reviewer(§18.8 auth dispatch)] — web_context 추출 batch3: 세션쿠키·패스워드·TOTP (parallel-work-structure ITEM-10)
- Related Change: CHG-20260711T110000-item10-webctx-batch3. cycle: ai/claude-corp/feature-0012-item10-webctx-b3. 승인: ROADMAP §6.1.
- **§18.8 적대 패널 VERDICT: SHIP** (BLOCKING/MAJOR/MINOR 0 · NIT 1) — 인증 코어 인접(auth dispatch)이라 SKIPPED 아닌 패널 실검증:
  - byte-동치: 제거 vs 추가 라인 기계 대조 SequenceMatcher ratio 1.0(비공백 270/270), 함수 본문 공백 변형 0, 양 파일 ast.parse 통과.
  - name-resolution: AST 미해석 이름 0 + **라이브 import 실행** — 30개 심볼 전존, RFC 6238 공식 벡터(T=59→287082)·pbkdf2 왕복·drift ±1 허용/±2 거부 스팟체크 전건 통과.
  - monkeypatch/테스트 계약: setattr 311건→유니크 65 attr 과 이동 30심볼 교집합 0(내부 의존 위험군 포함), getsource 소비는 함수객체 기준이라 생존, routers app.X 동적참조 rebind 전원 포함·섀도잉 0.
  - 인증 semantics: TOTP 상수·pbkdf2 포맷·쿠키 httponly/samesite/secure 분기 보존. 함수-지역 절대 import 는 sys.path 전역 해석이라 파일 위치 무관(web.app/bare-app 양 경로 batch1/2 가동 실적으로 기검증).
  - INVARIANT: `from app import` 0 · 신규 top-level import 는 stdlib 4종(base64/hmac/json/secrets)뿐 — 무순환.
  - NIT(이동 부산물 stale 자기지시 주석) → 본 커밋에서 정리.
- 게이트: 스냅샷 byte-동치 · F821 clean(중간 14건 적발 → import 보강+_b64decode 동반 이동 — 게이트 실효 사례) · py_compile · 전 스위트 pytest rc=0.
- Human Approval Needed: 아니오 — §6.1. behavior-neutral(패널 기계 증명), 배포는 item 완료 시.

## REV-20260711T111000-item10-webctx-batch4 [SKIPPED:roadmap-spec-transcription] — web_context 추출 batch4 (parallel-work-structure ITEM-10)
- Related Change: CHG-20260711T111000-item10-webctx-batch4. cycle: ai/claude-corp/feature-0012-item10-webctx-b4. 승인: ROADMAP §6.1.
- SKIPPED 사유: batch1/2 와 동일 계보의 비인증 순수 leaf(출력 정규화·경로/URL 빌더·상수) — auth dispatch 비해당(b3 와 달리 인증 semantics 무접촉). 기계 게이트 4종 전건 GREEN + monkeypatch census 0. 내부 호출쌍(_normalize_output→_strip_ansi, _is_internal_message→_should_mark_internal_message)은 동반 이동으로 패치-관통 이슈 원천 배제(어느 쪽도 테스트 패치 대상 아님을 census 로 확인).
- Human Approval Needed: 아니오 — §6.1.

## REV-20260711T112500-item10-webctx-batch5 [SKIPPED:roadmap-spec-transcription] — web_context 추출 batch5 (parallel-work-structure ITEM-10)
- Related Change: CHG-20260711T112500-item10-webctx-batch5. cycle: ai/claude-corp/feature-0012-item10-webctx-b5. 승인: ROADMAP §6.1.
- SKIPPED 사유: leaf 계보 계속 — 이동 전 AST 폐포 스캔(미해석 이름 0 인 13 + 의존 보강 2)과 패치 census(전 후보 0 — 관통 위험 쌍은 제외)로 경계를 기계 확정. RBAC seed 는 부트스트랩-시점 함수(요청 경로 아님)라 auth dispatch 의 라이브 인가 판정 표면 비해당. 기계 게이트 4종 GREEN. 1차 시도 절단 사고는 게이트가 설계대로 차단(정직 기록: MODIFY 참조) — 출하물은 AST 재작업본.
- Human Approval Needed: 아니오 — §6.1.

## REV-20260711T124000-item10-webctx-batch6 [SUBAGENT:improve-fit-reviewer(적대 이동성 분석)] — web_context 추출 batch6 A+B+C (parallel-work-structure ITEM-10)
- Related Change: CHG-20260711T124000-item10-webctx-batch6. cycle: ai/claude-corp/feature-0012-item10-webctx-b6. 승인: ROADMAP §6.1.
- **적대 분석(사전, AST 호출그래프 + 테스트/라우터 전수 grep — auth 인접이라 SKIPPED 아닌 실검증)**:
  - 핵심 규칙 실측 확립: X 단독 이동은 항상 패치-안전(인터셉트 지점=호출자 측) — 파손은 "패치되는 X 의 호출자 Y 를 co-move" 할 때만. 파손 실례 3건(파일:라인) 문서화(_ds_write_common·_collect_role_prompt_context·_delete_conversation_impl co-move 시나리오 — 전부 본 batch 범위 밖).
  - 판정표: SAFE-MOVE 13(본 batch) / MOVE-WITH-RETARGET 1(_account_has_permission — 현행 재타깃 필요 0건 확인 후 이동) / **KEEP-IN-APP 3**(_connect_memory: 부트스트랩 기계+app 설정 전역 결합·shared/db 부적합 사유 포함, _require_account: 5줄에 12+건 패치 우회 트랩, _account_can_access_conversation: DB-접촉 폐포+폐포원 개별 패치).
  - 숨은 계약 적발: test_perm_self_scope 가 app.py AST 에서 4개 self-scope 가드 소스를 추출 — 이동 금지 확인(본 batch 비포함).
  - retarget 필요 테스트: **0건**(패치사이트 ~162건 전수 — dual-patch 세금 회피, retarget 전략 기각).
- 검증: 4중 게이트 GREEN(스냅샷 byte-동치·F821·py_compile·전 스위트 pytest rc=0) — 판정표 예측(0 파손) 실증. 이동 영구 금지 목록 9종 web_context 헤더 등재(미래 batch 의 가드레일).
- Human Approval Needed: 아니오 — §6.1. (별건: deploy-web.sh flake 하드닝은 명세 밖 — 사용자 보고)

## REV-20260711T120729-docs-archive [SKIPPED:mechanical-archiving] — §5.5 아카이빙
- Related Change: CHG-20260711T120729-docs-archive. 재구성 md5==원본(assert)·verbatim·런타임 코드 0. 승인: 사용자 지시+§5.5.

## REV-20260711T121500-item10-routers-p1 [SKIPPED:pattern-pilot-mechanical] — routers/ 이동 파일럿
- Related Change: CHG-20260711T121500-item10-routers-p1. 승인: ROADMAP §6.1(ITEM-10) + 판정표 §4 권장 경로. 26줄 단건·기계 게이트 4종 GREEN·직접호출 테스트가 패치-단일점 보존을 실증(적대 판정표가 이 경로를 사전 검증). 대형 클러스터 적용 시(다음 배치)는 규모에 따라 §18.8 패널 재소집.

## REV-20260711T151943-item10-routers-p2 [SKIPPED:pattern-transcription] — _metadata_* routers 이동
- Related Change: CHG-20260711T151943-item10-routers-p2. 승인: ROADMAP §6.1. 파일럿(REV-20260711T121500, 판정표 §4 사전 적대검증 경로)의 확립 패턴 전사 — 신규 판단은 census 기반 선별 예외 1건(_metadata_llm_complete 호출부 app.X 유지)뿐이며 그 목적 자체가 패치-단일점 보존. 기계 게이트 4종 + 해당 패치 테스트 통과가 관통 보존을 직접 증명.

## REV-20260711T152337-item10-routers-p3 [SKIPPED:pattern-transcription] — 프롬프트 컨텍스트 조립 이동
- Related Change: CHG-20260711T152337-item10-routers-p3. 승인: ROADMAP §6.1. p1/p2 확립 패턴 + census 선행(패치 4종·직접참조 6종·app 내부 호출자 1) — 판정표가 파손 실례로 경고한 클러스터를 그 판정표의 권장 경로(app.X)로 이동, 해당 패치 테스트(test_auto_role_prompt/auto_account_prompt 등) 통과가 관통 보존 직접 증명. 기계 게이트 4종 GREEN.

## REV-20260711T153043-item10-routers-p4 [SKIPPED:pattern-transcription] — _conv_* 이동
- Related Change: CHG-20260711T153043-item10-routers-p4. 승인: ROADMAP §6.1. 확립 패턴 전사(패치 0 — 관통 표면 없음). 기계 게이트 4종 GREEN.

## REV-20260711T153747-item10-routers-p5 [SKIPPED:pattern-transcription] — 대화 조회 이동
- Related Change: CHG-20260711T153747-item10-routers-p5. 승인: ROADMAP §6.1. 확립 패턴 전사(패치 0). 기계 게이트 4종 GREEN.

## REV-20260711T160724-item10-routers-p6 [SKIPPED:pattern-transcription] — fork·steps·첨부편집 이동
- Related Change: CHG-20260711T160724-item10-routers-p6. 승인: ROADMAP §6.1. 패턴 전사(패치 0). 게이트 4종 GREEN.

## REV-20260711T161858-item10-routers-p7 [SKIPPED:pattern-transcription] — 감사 인프라 이동
- Related Change: CHG-20260711T161858-item10-routers-p7. 승인: ROADMAP §6.1. 패턴 전사 + record_audit_event KEEP(판정표 KEEP 3종과 동일 논거 — 12× 패치-단일점). 게이트 4종 GREEN.

## REV-20260711T195338-item10-routers-p8 [SKIPPED:pattern-transcription] — 부트스트랩 스키마 이동
- Related Change: CHG-20260711T195338-item10-routers-p8. 승인: ROADMAP §6.1. 패턴 전사 + global-쓰기 등가 변환(ast.Global 스캔으로 기계 검출). F0 접촉 사고는 원복 완료·정직 기록(TASK). 게이트 4종 GREEN.

## REV-20260711T195739-item10-routers-p9 [SKIPPED:pattern-transcription] — 제품 인사이트·첨부 이동
- Related Change: CHG-20260711T195739-item10-routers-p9. 승인: ROADMAP §6.1. census(패치 1 — 내부 호출 0 확인)+패턴 전사. 게이트 4종 GREEN.

## REV-20260711T202222-item10-routers-p10 [SKIPPED:pattern-transcription] — 스키마/시드 일괄 이동
- Related Change: CHG-20260711T202222-item10-routers-p10. 승인: ROADMAP §6.1. 패턴 전사(setattr 0·getsource 는 rebind 생존 실증 계보·global-쓰기 등가 변환 자동 적용). 게이트 4종 GREEN.
