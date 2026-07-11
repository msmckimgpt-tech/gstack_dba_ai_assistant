---
doc_type: MODIFY
feature_id: feature-0012-web-router-modularization
status: active
edit_policy: append-only
source_of_truth: true
---

# Modify Log

> 이전 기록(30건): [MODIFY-archive-20260711T120729.md](./_archive/MODIFY-archive-20260711T120729.md)

## CHG-20260701-0007
- Date: 2026-07-01
- Related Requirement: P5b router 추출 #10 — **admin/metadata 도메인 34 핸들러 → routers/admin_metadata.py**. inline-heavy 도메인 첫 추출(DI 전환 CHG-0006 선행).
- Summary:
  admin/metadata 34 핸들러(DI 전환 33 + 이연 1 `admin_metadata_suggest` inline 유지)를 AST 경계로 `src/routers/admin_metadata.py`(신규, 1447줄) 추출. **tokenize 기반 결정적 변환기**(`metadata_extract.py`): whitelist app-symbol(32) → `app.X` 접두(문자열/속성/정의 안전), `@app.<m>`→`@router.<m>`. 핸들러가 `_metadata_*` 헬퍼와 교차 배치돼 있어 핸들러 함수만 개별 추출(헬퍼는 app.py 잔류, `app.X` 참조로 monkeypatch 보존). app.py 맨 끝 `from routers.admin_metadata import router; include_router`(순환 안전).
  - 동반 테스트 재참조(4파일): `app.<handler>(` → `admin_metadata.<handler>(` 65개(happy 49 + suggest/bootstrap_describe 16) + `from routers import admin_metadata` import. 403-gate 9는 TestClient(route 사용)라 무변경.
  - **make test 안전망 적발·교정**: `_SAMPLE_WEIGHT_MIN`/`_MAX`(app.py `= 1, 1000` **튜플 대입** 모듈 상수)를 whitelist 도출(mod_syms=`ast.Name` 타깃만)이 놓침 → NameError → **완전 mod_syms(튜플/AnnAssign/import 타깃 포함) static 재검사**로 전수 확인 후 `app.` 접두 보정.
- Files: src/routers/admin_metadata.py(신규 1447줄), src/app.py(34 제거 + include_router), tests/test_metadata_{glossary_enum,phase2,glossary_autoreg,ai_autocomplete}.py(재참조), tests/route_snapshot_p5b.json(골든 순서 재생성·set-neutral 192) + docs.
- Impact: **app.py 28,224→26,734 줄(~1,490↓ — 단일 도메인 최대 감소).** make test 전체 통과·**1313 passed·0 fail**·route drift 0, route-parity 192(set 불변·순서만 갱신, docker `_build_table` 재생성), py_compile OK. byte-neutral(라우트 경로·메서드·응답 불변).
- 학습: **whitelist 도출 시 mod_syms 는 튜플-대입(`A, B = ...`)·AnnAssign·import 타깃까지 수집 필수** — `ast.Name` 타깃만 하면 튜플-상수 누락 → 추출 router NameError(make test 안전망 적발). 추출 후 **완전 mod_syms 로 router bare-ref static 재검사**를 골든 재생성 전에 수행하면 조기 적발.
- Rollback: revert(admin_metadata.py 삭제 + app.py 34 복원 + 4 테스트 재참조 원복 + 골든 복원).

## CHG-20260701-0008
- Date: 2026-07-01
- Related Requirement: P5b admin/metadata 마일스톤(CHG-0006 DI 전환 + CHG-0007 추출) **프로덕션 배포·라이브 검증**(deploy-backed 완료 기준).
- Summary:
  PR #506(CHG-0006/0007 2 커밋 + origin/main 재머지) CI test PASS → main 머지(0b91b1b) → `sudo -E bin/deploy-web.sh` blue-green 무중단 롤링(web-a·web-b 순차 recreate, healthz-gated commit-match, soak 90s 통과). deploy_scope: included(FIRST_REQUEST.md 전역 standing) 근거 자동 배포.
  - 라이브 검증(edge 112.185.196.20): healthz git_commit=0b91b1b·status=ok / 추출 admin_metadata 라우트 `/api/admin/metadata/glossary`·`/samples` 미인증 **401 `{"error":"로그인이 필요합니다."}` verbatim** — DI seam byte-동치 + 컨테이너 로드(uvicorn web.app:app) router import 프로덕션 확인(web_context류 ModuleNotFoundError 없음).
- Files: docs(MODIFY/REVIEW/REPORT/TASK) — 배포 기록(코드 무변경).
- Impact: admin/metadata 도메인 deploy-backed 완료. insight/ask-worker GIT_COMMIT WARN 은 별건(웹 무관).
- Rollback: `sudo -E bin/deploy-web.sh --rollback`(이전 색 유지, 이미 안정).

## CHG-20260701-0009
- Date: 2026-07-01
- Related Requirement: P5b router 추출 batch — **6 도메인 35 핸들러 전체추출**(profile·integrations·attachments·admin_audits·admin_accounts·admin_roles). inline-heavy 도메인 대량 추출.
- **전략 전환(핵심 발견)**: **핸들러 router 추출은 DI 전환을 요구하지 않는다.** 원래 블로커(테스트 monkeypatch 커플링)는 *helper* 를 web_context 로 옮길 때만 발생(cross-call 네임스페이스 이탈); *핸들러* 추출은 `import app`+`app.X` 동적참조라 `app._require_account` 등 monkeypatch 계약이 그대로 보존됨(admin_metadata_suggest 선례). → **DEFER 핸들러(pre-auth gate 등)도 인라인 auth 유지로 byte-identical 추출 가능**("이연=구조 재편 후 추출"의 구조 재편 = router 이동 자체). 잔여 10 도메인 분류 workflow(11 agents): CLEAN-DI 5·ALREADY-DI 36·PUBLIC 7·DEFER 50(preauth 42·longpoll 4·txn 3·failsoft 1). 전체추출로 도메인 라우트 split(var-vs-concrete 순서 위험) 회피.
- Summary:
  6 도메인 전 핸들러(ALREADY-DI + PUBLIC + DEFER-inline)를 **범용 tokenize 추출기**(`extract_router.py`)로 router 이동. 개선: (1) 완전 mod_syms(튜플/AnnAssign/import 타깃), (2) **import 심볼 제외 + app.py import_map 으로 router 로컬 import 동적 생성**(fastapi/stdlib/typing), (3) self-healing missing-prefix static 재검사. profile(4)·integrations(4, RedirectResponse/OAuth)·attachments(4)·admin_audits(7)·admin_accounts(8)·admin_roles(8).
  - 동반 테스트 재참조(범용 `reref_tests.py`, `app.<handler>`→`<module>.<handler>` call·getsource·attribute 전부 + module-level import): test_audit_tamper_evidence·test_login_attempt_limit·test_llm_usage_quota·test_avatar_icon_upload·test_two_factor_auth. **추가 커플링 2유형 make test 적발·수정**: (a) `hasattr(app,"handler")` 문자열-인자 3건 → `hasattr(<module>,...)`, (b) `app.app.routes` flat 순회(중첩 include_router 라우트 미포착) → 재귀 walk(test_task0284 route-registered), (c) source-text regex `def download_attachment...@app\.`(app.py) → routers/attachments.py + `@router\.`.
- Files: src/routers/{profile,integrations,attachments,admin_audits,admin_accounts,admin_roles}.py(신규 6), src/app.py(35 제거 + include_router 6), tests/(6 파일 reref+import+coupling fix), tests/route_snapshot_p5b.json(골든 순서 재생성·set-neutral 192) + docs.
- Impact: **app.py 26,734→24,648 줄(~2,086↓).** 12→18 router. make test 전체 통과·1313 passed·0 fail·route drift 0, route-parity 192(set 불변), py_compile OK. byte-neutral(라우트 경로/메서드/응답 불변, DEFER 핸들러 인라인 auth 그대로).
- 학습: 추출 커플링 유형 확장 → (1)직접호출 (2)monkeypatch (3)getsource attribute (4)소스텍스트 read_text/ast.parse (5)**`hasattr/getattr(app,"handler")` 문자열-인자** (6)**`app.app.routes` flat 순회(중첩 라우트)**. 추출 전 grep: `app\.<h>`·`hasattr\(app,"<h>"`·`app.app.routes`. **DI 전환은 추출의 전제가 아님** — 모듈화(app.py 축소)가 목표면 전체추출(인라인 유지)이 최단.
- Rollback: revert(6 router 삭제 + app.py 35 복원 + 테스트 원복 + 골든 복원).

## CHG-20260701-0010
- Date: 2026-07-01
- Related Requirement: P5b 전체추출 batch2 — admin/datasources(6) + api/auth(18) 24 핸들러.
- Summary:
  admin/datasources 6(CLEAN-DI 3 `_ds_write_common` 인라인 유지 + ALREADY-DI 3) → routers/admin_datasources.py. api/auth 18(PUBLIC 7 signup/login/oauth + ALREADY-DI 6 avatar/totp + DEFER 5) → routers/auth.py. 전체추출(인라인 auth 보존, byte-identical).
  - 동반 테스트 reref: datasources 4파일(admin_update/delete/test_datasource 직접호출) + auth 3파일(test_oauth_google_foundation 8 직접호출, test_two_factor_auth·test_login_attempt_limit getsource). **커플링 추가 적발·수정**: hasattr 루프 2(`for fn in (...): hasattr(app,fn)`→auth), **source-text 호출식 count**(test_product_list_rbac 가 `_filter_products_for_account_access(account, products)` 를 app.py 소스에서 2회 count — auth_me 가 auth.py 로 이동해 1로 감소 → app.py+routers 합산 검색으로 수정; 핸들러명 아닌 호출식이라 커플링 스캔 미포착).
  - reref 도구 guard 정밀화: `f" {module}"` generic substring 오탐(module="auth") → `^from routers import ...\b{module}\b` 정확 매칭.
- Files: src/routers/{admin_datasources,auth}.py(신규), src/app.py(24 제거 + include_router 2), tests/(8 파일 reref+coupling fix), tests/route_snapshot_p5b.json(골든 set-neutral 192) + docs.
- Impact: **app.py 24,648→23,536 줄(~1,112↓).** 18→20 router. make test 1313·0 fail·route drift 0, route-parity 192, byte-neutral(PUBLIC/DEFER 인라인 그대로).
- 학습: 커플링 7유형 = 기존 6 + **(7) source-text 호출식 count**(핸들러명 아닌 helper 호출식을 app.py 소스에서 count → 추출로 이동 시 count 변동, app.py+routers 합산으로 수정). reref import guard 는 정확 매칭 필수(generic substring 금지).
- Rollback: revert(2 router 삭제 + app.py 24 복원 + 테스트 원복 + 골든 복원).

## CHG-20260701-0011
- Date: 2026-07-01
- Related Requirement: P5b 전체추출 batch3 — api/conversations 17(→기존 conversations.py **append**) + admin/products 22(신규) = 39 핸들러. **잔여 도메인 대부분 추출 완료**.
- Summary:
  api/conversations 17 sub-resource 핸들러(members/share/attachments/messages/product/sample-feedback/fix-with-ai 등, ALREADY-DI 10 + DEFER 7 인라인) → **기존 routers/conversations.py 에 append**(추출기 --append 모드 신규: 기존 import 에 부족분 병합·핸들러 뒤 추가·include_router 기존 유지·NEW 블록만 missing-prefix 검사). admin/products 22(CLEAN-DI 1 + ALREADY-DI 5 + DEFER 16 txn/streaming/pre-auth 인라인) → routers/admin_products.py(신규).
  - 동반 테스트 reref: conversations 7파일(direct-call post_sample_feedback/post_fix_with_ai + getsource create_conversation_share/list_conversation_shares/list_conversation_attachments/mark_conversation_read) + products 5파일(direct-call). **source-text contract 2 make test 적발·수정**: (a) test_group_conversation_s2 `@app.get(".../members")` in APP(app.py만) → member 핸들러 이동으로 APP_ALL(app.py+routers)+`@router` 허용, (b) **test_share_joinable_owner_guard getsource substring `joinable and not _conversation_owned_by_account`** → 추출로 helper 가 `app._conversation_owned_by_account` 접두되어 substring(앞 단어 `not ` 포함) 불일치 → `not app._conversation_owned_by_account` 로 갱신.
  - 추출기 개선: missing-prefix 에서 IMPORTED 심볼 제외(로컬 import 로 커버), --append 시 NEW 블록만 검사(기존 router F821 은 별건).
- Files: src/routers/conversations.py(+17 append), src/routers/admin_products.py(신규), src/app.py(39 제거 + include_router 1[products; conversations 기존]), tests/(13 파일 reref+source-text fix), tests/route_snapshot_p5b.json(골든 set-neutral 192) + docs.
- Impact: **app.py 23,536→20,542 줄(~2,994↓).** 20→21 router(conversations append). make test 1313·0 fail·route drift 0, route-parity 192, byte-neutral. **잔여 app.py 라우트 16(session 시작 148 대비)**.
- 학습: getsource substring 검사는 **helper 앞 컨텍스트(`not X`, `= X`) 포함 시 app. 접두로 깨짐**(단일 심볼명은 부분문자열로 생존) → 추출 시 그런 substring 은 `app.` 접두형으로 갱신. --append 는 기존 router import 병합 + include_router 미추가. 커플링 8유형(신규 8=getsource 컨텍스트-substring).
- Rollback: revert(conversations 17 append 제거 + admin_products 삭제 + app.py 39 복원 + 테스트 원복 + 골든).

## CHG-20260701-0012
- Date: 2026-07-01
- Related Requirement: P5b 전체추출 batch4 — 잔여 16 라우트(misc/deferred/cross-call). **app.py 라우트 핸들러 전량(148) 추출 완료.**
- Summary:
  잔여 16 핸들러를 기존 router 에 그룹 append: conversations(ask·fork_conversation·clear_memory·progress·ask_result·suggestions 6) + share(public_share_view·public_share_fork 2) + admin_console(admin_get/put_system_prompt·admin_get/put_dashboard_prefs 4) + system(livez·readyz·get_session·get_api_vault_options 4). DEFER(ask_result long-poll·progress/suggestions fail-soft·public_share_view opt) 인라인 유지 byte-identical.
  - **cross-call 핸들러 `ask` 처리(9번째 커플링 유형)**: `ask` 는 route 이자 내부 함수(conversations.py:1397 post_fix_with_ai 가 `app.ask(internal_req)` 호출 + test monkeypatch). conversations.py 로 append → 내부 caller `app.ask`→`ask`(동일 모듈 bare), 테스트 `monkeypatch.setattr(app,"ask")`→`conversations` + `hasattr(app,"ask")`→`conversations` + getsource/직접호출 reref.
  - 동반 테스트 reref: suggestions/ask(conversations) + public_share_*(share) 등 6파일.
- Files: src/routers/{conversations,share,admin_console,system}.py(append), src/app.py(16 제거), tests/(6 reref+cross-call fix), tests/route_snapshot_p5b.json(골든 set-neutral 192) + docs.
- Impact: **app.py 20,542→18,917 줄(~1,625↓).** **잔여 @app 라우트 0 — 148 route 핸들러 전량 21 router 로 추출 완료.** app.py = 헬퍼 라이브러리 + DI seam + 미들웨어 + include_router(조립부). make test 1313·0 fail·route drift 0, route-parity 192, byte-neutral.
- 학습: 커플링 9유형 = 기존 8 + **(9) cross-call 핸들러**(route 이자 내부 함수 — 추출 시 내부 caller 참조 `app.X`→동일모듈 bare + monkeypatch/hasattr 대상 모듈 전환). app.py 잔여(~18.9k)=헬퍼(web_context 미이동, 원래 블로커 — 별도 workstream).
- Rollback: revert(4 router append 제거 + app.py 16 복원 + ask cross-call 원복 + 테스트·골든).

## CHG-20260702-0013
- Date: 2026-07-02
- Related Requirement: batch4 전체추출(CHG-20260701-0012)의 **bare-name 회귀 수정** — 라우터 모듈이 app-모듈 전역/import 심볼을 `app.` 로 한정하지 않아 런타임 `NameError` → 라이브 500 3종.
- Summary:
  P5b batch4 가 app.py 핸들러를 router 모듈로 추출하며, 원래 app.py 네임스페이스에서 해소되던 bare 참조(`MEMORY_DB`, `load_memory_kv` 등)를 `app.` 으로 한정하지 않았다. router 모듈은 `import app` 만 하므로 해당 bare name 이 미해소 → 핸들러 실행 시 `NameError` → 500. CHG-0012 의 "byte-neutral" 주장은 name-resolution 관점에서 부정확(모듈 경계 이동 시 bare app-global 은 비-byte-neutral). 6심볼/10개소를 `app.<name>` 으로 한정.
  - `admin_console.py:78` `MEMORY_DB` → `app.MEMORY_DB` (`GET /api/admin/databases/available` — 제품 DB 화이트리스트 피커).
  - `admin_quotas.py:52` `LLM_QUOTA_ENFORCE` → `app.LLM_QUOTA_ENFORCE` (`GET /api/admin/quotas`).
  - `conversations.py` `load_memory_kv`×5(186·188·194·478·534) + `mark_cancel_requested`(480) + `set_run_status`(503) + `mark_finalize_requested`(535) → 전부 `app.` 한정 (`/api/history` 상태 bubble · `/api/cancel` · `/api/finalize`).
  - 발견 경위: graph-panel-perms(91541447) 배포 후 라이브 브라우저 검증 중 admin 콘솔 500 관측 → `ruff check --select F821 routers/` 전수 감사로 6심볼 확정(브라우저로는 2심볼만 관측, 감사로 LLM_QUOTA_ENFORCE·mark_cancel_requested·set_run_status·mark_finalize_requested 추가 색출).
- Files: src/routers/{admin_console,admin_quotas,conversations}.py (10개소 `app.` 접두만).
- Impact: 라이브 admin console 500 3종 해소(제품 DB 피커·대화 상태 폴링·취소/즉시답변). 순수 name-qualification — `app.X` 는 app.py 가 정의(MEMORY_DB L99·LLM_QUOTA_ENFORCE L758)/import(L48–59 from modules.memory)한 **동일 객체**라 동작 무변경. route 무추가(route-parity 불변).
- 검증: ruff F821 clean(22 router 전체), py_compile PASS, 관련 45 테스트 PASS(quota/history/finalize/conn-status/usage), §18.8 SUBAGENT 패널 VERDICT PASS(정확성·완전성·회귀·부작용 4축 refute 실패), 배포 후 라이브 3엔드포인트 500→200.
- 학습: **라우터 전체추출은 name-resolution 상 byte-neutral 이 아니다** — 추출된 핸들러의 bare app-global/import 참조는 `app.` 한정 필수. batch1~4 의 "byte-neutral" 게이트(make test route-parity)는 *hit 되지 않은* 핸들러의 NameError 를 놓쳤다(테스트 미커버 경로). 향후 추출 시 `ruff --select F821` 를 추출 게이트에 추가 권장. (route-parity 골든 192 vs 실 193 stale 도 같은 batch4 미완 — 별도.)
- Rollback: revert 3파일 `app.` 접두 제거(bare 복원).

## CHG-20260702-0014
- Date: 2026-07-02
- Related Requirement: route-parity 골든 stale 해소(CI red `test_route_parity_p5b` 192→193). batch4(CHG-0012)가 골든을 192 로 set-neutral 했으나, 이후 feature-0016 `24445e94`(#514, "관리콘솔 메타데이터 그래프 뷰 출력 3건 수정")가 `GET /api/admin/metadata/graph/analyze/status` route 를 **추가하면서 골든을 갱신하지 않아** 실 193 vs 골든 192 drift → CI 상시 red.
- Summary:
  route-parity 안전망(`test_route_parity_p5b`)의 골든 스냅샷을 `_build_table()` 출력으로 재생성(테스트 docstring 의 sanctioned 갱신 방법). 정밀 diff 로 drift 원인을 **정확히 1개 route 추가**로 확정(제거·중복·재정렬 0): `GET /api/admin/metadata/graph/analyze/status`(`admin_metadata.py:1013` 정의, `admin.js:3974` 그래프 뷰 AI 분석 상태 폴링에 실사용 — 정당한 엔드포인트). 골든 `total_routes 192→193`, `api_routes 191→192`, analyze/status 블록 in-order 삽입.
- Files: src/../tests/route_snapshot_p5b.json (골든만).
- Impact: CI `test_route_parity_p5b` green 회복(→ 이후 PR 이 route-parity red 위로 머지하지 않음). **runtime 무변경** — 골든은 test fixture 이고 web 이미지(Dockerfile 은 src 만 COPY, tests/ 미포함)에 미반영 → web 재배포는 runtime no-op.
- 검증: 재생성 후 `test_route_parity_p5b` PASS(총 193/api 192). git diff 가 count 2줄 + analyze/status 블록만 변경(9 ins/2 del) 임을 확인 — 다른 route 미변경(오갱신·masking 없음).
- 학습: 의도적 route 추가 시 골든 갱신은 **route 추가 feature 의 책임**(여기선 #514 누락). route-parity 게이트가 이를 잡았으나, 추출-batch 들이 골든을 set-neutral 로 유지하는 사이 타 feature 의 route 추가와 겹쳐 blame 이 흐려졌다. 향후 route 추가 PR 은 골든 동반 갱신 필수(CI 가 강제).
- Rollback: revert route_snapshot_p5b.json(192 복원 — CI red 재발).

## CHG-20260710T235820-item05-router-autoreg (라우터 자동 등록 — app.py 꼬리 배선 경합 제거, parallel-work-structure ITEM-05)
- Date: 2026-07-10
- Related Requirement: ROADMAP parallel-work-structure ITEM-05 (F-008 — include_router 23개가 app.py 꼬리 19,641–19,717 에 밀집, 라우터 신설마다 같은 블록 편집 → 병렬 배선 경합).
- Summary: `routers/__init__.py` 에 `register_all(app)` 구현(pkgutil.iter_modules 순회 → 각 모듈 `router` 심볼 수집 → (INCLUDE_ORDER, 모듈명) 정렬 일괄 include). 23개 라우터 모듈 전부에 `INCLUDE_ORDER = 10..230`(현행 include 순서 스냅샷 고정, 10 간격). app.py 꼬리 블록(import 23+include 23+개별 주석, 3,846 bytes)을 `_register_all_routers(app)` 1줄 호출로 대체 — app.py 19,717→19,650줄. 이후 라우터 신설은 `routers/` 파일 추가만으로 등록(app.py diff 0).
- Files: `unit/feature-0003-agent-web-ui/src/routers/__init__.py`(register_all) · 23개 라우터 모듈(INCLUDE_ORDER 1줄씩) · `unit/feature-0003-agent-web-ui/src/app.py`(꼬리 치환). cross-feature: 코드 거주 feature-0003, 정본 docs 는 본 feature-0012(§0 primary 규약).
- Impact: 라우팅 표면 무변경(byte-동치 검증 아래). 배포 scope: web 이미지 재빌드(코드 baked) — §6.1 자동 배포.
- 검증: (a) 라우트 테이블 in-order 스냅샷 205 route **byte-동치**(전=후, mysql-ai-web:current, `_walk_routes` 식 재귀 열거) (b) `ruff --select F821` routers/ 22모듈+app.py clean (c) A/B pytest(main vs worktree, feature-0003 전 스위트) 양쪽 rc=0 — route-parity 골든 포함 회귀 0 (d) 더미 라우터(`zz_dummy_probe.py`, INCLUDE_ORDER=990) 추가만으로 라우트 노출 확인 후 제거.
- Rollback: app.py 꼬리를 명시 import/include 23쌍으로 복원 + INCLUDE_ORDER 제거(단일 커밋 revert).

## CHG-20260711T100116-item10-webctx-batch1 (web_context 추출 batch1 — inc3 권한 카탈로그 + inc4 계정 행 빌더, parallel-work-structure ITEM-10)
- Date: 2026-07-11
- Related Requirement: ROADMAP parallel-work-structure ITEM-10 (F-007-2 — app.py ~19.6k 헬퍼·전역이 전 웹 작업의 공유 착지점).
- Summary: leaf-first 증분(inc1/inc2 계보) 계속 — inc3(SESSION_COOKIE + PERMISSION_DEFINITIONS/CODES/DEFINITION_MAP + _METADATA_MANUAL_IMPLIES + _resolve_permission_catalog, 562줄) · inc4(OVERRIDE_* 상수 + _empty_permission_map + _normalize_override_value + _apply_permission_overrides + _fetch_account_rows + _load_role_permission_codes + _load_account_override_values + _decorate_account_rows, 167줄)를 web_context.py 로 byte-동치 이동. 호출 폐포가 web_context 안에서 닫힘(app 의존 0 — INVARIANT `from app import` 금지 유지). app.py 상단 re-import rebind 로 app 내 호출부·routers `app.X` 동적참조·테스트 monkeypatch/getsource 전부 보존. app.py 19,650→18,931줄.
- Files: `unit/feature-0003-agent-web-ui/src/app.py`(블록 제거+rebind import) · `src/web_context.py`(+768줄) · `tests/test_group_conversation_s2.py`(APP_ALL 에 web_context.py 포함 — 소스-계약 위치 무관 고정).
- 검증: 라우트 스냅샷 205 in-order byte-동치(main 대비, _walk_routes 재귀) · ruff F821 clean(src 전체) · py_compile · feature-0003 전 스위트 pytest rc=0(소스-계약 1건 위치 갱신 후 전건 GREEN). 배포 scope: web 재빌드(item 완료 시 §6.1 — 중간 batch 도 머지-가능 유지).
- Rollback: 단일 커밋 revert(이동+rebind 원자).

## CHG-20260711T103000-item10-webctx-batch2 (web_context 추출 batch2 — 검증 정규식·인증 파라미터·seed 롤, parallel-work-structure ITEM-10)
- Date: 2026-07-11
- Summary: batch1(CHG-20260711T100116) 계속 — 검증 정규식 5종(ANSI/CONTROL/MODEL/USERNAME/ROLE_KEY_RE) + SEED_ROLE_DEFINITIONS/_seed_role_definition/_seed_role_codes(RBAC seed) + PASSWORD_HASH_ITERATIONS/AUTH_SESSION_DAYS(인증 파라미터)를 web_context.py 로 byte-동치 이동(상단 rebind). 전부 순수 leaf(monkeypatch 소비 0 — 사전 grep). app.py 18,931→18,854줄.
- Files: src/app.py · src/web_context.py.
- 검증: 라우트 스냅샷 byte-동치 · ruff F821 clean · py_compile · feature-0003 전 스위트 rc=0(테스트 무변경 — app.SEED_ROLE_DEFINITIONS 등 읽기 소비는 rebind 보존).
- Rollback: 단일 커밋 revert.

## CHG-20260711T110000-item10-webctx-batch3 (web_context 추출 batch3 — 세션쿠키·패스워드·TOTP, parallel-work-structure ITEM-10)
- Date: 2026-07-11
- Summary: 인증 leaf 클러스터를 web_context.py 로 byte-동치 이동 — 세션쿠키 4(_get_session_id/_request_is_https/_set/_clear_session_cookie) · 패스워드 6(_sanitize/_is_valid_username·_is_valid_password·_hash/_verify_password·_b64decode) · TOTP 상수 6+함수 14(_totp_dek 계열의 `modules.cred_crypto`/`shared.datasources` 는 함수-지역 lazy import 동반 이동 — top-level app-free INVARIANT 유지, 역방향 참조 없어 순환 불가). web_context 상단 import 보강(base64/hmac/json/secrets). app.py 18,854→18,569줄(누적 19,650→18,569, -1,081).
- Files: src/app.py · src/web_context.py.
- 검증: 스냅샷 byte-동치 · ruff F821 clean(중간 스캔이 14건 적발 → import 보강+_b64decode 동반 이동으로 해소 — F821 게이트가 name-resolution 회귀를 실제 차단한 사례) · py_compile · 전 스위트 pytest rc=0(test_two_factor_auth 포함) · monkeypatch 소비 0(사전 census: 상위는 _connect_memory 68·_require_account 52 등 — 본 batch 비대상).
- Rollback: 단일 커밋 revert.

## CHG-20260711T111000-item10-webctx-batch4 (web_context 추출 batch4 — 세션 경로·출력 정규화·미디어 URL, parallel-work-structure ITEM-10)
- Date: 2026-07-11
- Summary: 순수 leaf 3군 이동 — ① SESSION_DIR(+mkdir)·INTERNAL_MEMORY_PREFIXES·PLACEHOLDER_TOPICS ② 출력 정규화/내부메시지 판정 5함수(_strip_ansi/_normalize_output/_should_mark_internal_message/_is_internal_message/_unwrap_followup_user_request — 내부 호출쌍 동반 이동) ③ 미디어 URL·대화파일 경로 5함수(_avatar/_product_icon/_role_icon_url_for·_account_conv_file·_conv_file). web_context 에 pathlib.Path 추가. app.py 18,569→18,475줄(누적 -1,175).
- 검증: 스냅샷 byte-동치 · F821 clean · py_compile · 전 스위트 pytest rc=0 · monkeypatch 0(사전 census — SESSION_DIR 테스트 참조 0, routers _conv_file 소비 4 는 app.X 동적).
- Rollback: 단일 커밋 revert.

## CHG-20260711T112500-item10-webctx-batch5 (web_context 추출 batch5 — 계정 로더·id 맵·RBAC seed, parallel-work-structure ITEM-10)
- Date: 2026-07-11
- Summary: 16블록 513줄 이동 — 대화 id IO 2·권한/역할 id 맵 2·계정 로더 2·_issue_auth_session·_is_safe_model_name + RBAC seed 부트스트랩 7함수+SEED_PRODUCT_DEFINITIONS. 패치-관통 위험 쌍(_product_permission_code/_ensure_product_access_permissions)·shared 래퍼 2종·프롬프트-seed 쌍은 의도 제외(AST 폐포 스캔+패치 census 로 경계 확정). app.py 18,475→18,009줄(누적 -1,641). web_context 에 logging·datetime 계열 import 보강.
- 사고·교훈: 1차 시도의 라인-휴리스틱 경계가 flush-left SQL heredoc(seed 함수 다수)에서 함수를 절단 — py_compile/F821(5,733)이 즉발 차단, git checkout 후 **AST end_lineno 추출기로 재작업**(이동 텍스트·잔여 app.py·신규 wc 3중 ast.parse 게이트 내장). 이동 경계는 이후 batch 부터 AST 가 정본.
- 검증: 스냅샷 byte-동치 · F821 clean · py_compile · 전 스위트 pytest rc=0.
- Rollback: 단일 커밋 revert.

## CHG-20260711T124000-item10-webctx-batch6 (web_context 추출 batch6 A+B+C — retarget 영역 판정표 기반, parallel-work-structure ITEM-10)
- Date: 2026-07-11
- Summary: 적대 분석 판정표(아래 REV)의 SAFE-MOVE 13함수 311줄 3단 이동(A: 계정/권한 read-model 7 · B: 제품 접근 4 · C: 인증 read/감사 actor 2). KEEP 3종(_connect_memory·_require_account·_account_can_access_conversation)은 패치-단일점 보존을 위해 app 영구 잔류 — 이동 영구 금지 목록 9종을 web_context 헤더에 명문화. app.py 18,009→17,724줄(누적 -1,926).
- 검증: 스냅샷 byte-동치 · F821 clean · py_compile · 전 스위트 pytest rc=0(판정표의 "현행 테스트 0건 파손" 예측 실증).
- 배포 인시던트(별건 기록): batch4/5 배포가 preflight `docker compose config` 간헐 실패(6회 중 3회) + 롤백-직후 edge 재검 조기 판정으로 3회 실패 — 5a42b6e1 이미지 자체는 단독 서빙 정상 실증, 라이브는 last-good(14b7d876) healthy. deploy-web.sh 하드닝(stderr 포획·config 재시도·롤백 후 edge backoff)은 feature-0014 소유 명세 밖 → 사용자 승인 대기.
- Rollback: 단일 커밋 revert.

## CHG-20260711T120729-docs-archive (MODIFY/REVIEW §5.5 아카이빙)
- Date: 2026-07-11. MODIFY 45건(30 이관)·REVIEW 46건(31 이관) — verbatim·무손실 md5·가역.

## CHG-20260711T121500-item10-routers-p1 (routers/ 이동 파일럿 — _ds_write_common)
- Date: 2026-07-11. 판정표 §4("대형 호출자는 web_context 아닌 routers/ — 패치-단일점 자동 보존") 경로의 첫 실적용. 패턴: 이동 함수의 app-전역 참조를 app.X 동적으로 전환 + 도메인 내 호출 로컬화 + 외부(테스트) 참조는 app 꼬리 rebind. app.py 17,724→17,704줄.
- 검증: 4중 게이트 GREEN — 특히 test_datasource_delete(#S1: app._connect_memory/_require_account 패치 + app._ds_write_common 직접 호출)가 이동 후에도 패치 관통 없이 통과 = 패턴의 핵심 주장 실증.

## CHG-20260711T151943-item10-routers-p2 (_metadata_* 20종 routers 이동)
- Date: 2026-07-11. 판정표 §4 routers-경로 2차 — 파일럿 패턴 그대로: app.X 동적(패치-단일점)·로컬화·선별 예외(_metadata_llm_complete 는 호출부 app.X 유지)·꼬리 rebind. admin_metadata.py 2,483줄(도메인 소유 정상화). app.py 17,704→17,294.
- 검증: census(테스트 직접참조 4·setattr 1·routers 소비 단일파일·app 내부 1) 선행 → 4중 게이트.

## CHG-20260711T152337-item10-routers-p3 (프롬프트 컨텍스트 조립 8종 이동)
- Date: 2026-07-11. p1/p2 패턴 + 신규 판단 1: 소비가 4개 라우터(admin_roles/admin_products/auth/conversations)에 분산된 공용 계층 → 도메인 파일 대신 register_all-제외 공용 모듈 routers/_prompt_context.py 신설(모듈명 `_` 접두 규약 활용). 판정표 실례 #2(_collect_role_prompt_context co-move 파손 시나리오)가 지목한 바로 그 클러스터 — app.X 동적화로 안전 이동. app.py 17,294→16,449.
