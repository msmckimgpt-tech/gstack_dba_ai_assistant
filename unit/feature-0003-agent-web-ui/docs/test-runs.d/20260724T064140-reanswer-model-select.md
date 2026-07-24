---
run_at: 2026-07-24T15:47:00+09:00
session: ai/claude/feature-0019-reanswer-model
scope: [message-editing, reanswer, model-selector, reasoning-effort]
verdict: PRE-COMMIT PASS (단위 6 + JS 구문 + §18.8 적대 리뷰 SHIP) · POST-DEPLOY PB-0008 배포 후 실측 예정
---

### Run (2026-07-24) — reanswer-model-select: 요청사항 수정 재답변이 선택한 model·추론강도로 재요청 — **Environment: Windows-browser (PB-0008 배포 후 실측 예정)**

cross-feature: 코드 거주 feature-0003(`static/app.js`·`routers/conversations.py`), 정본 cycle 문서
feature-0019-message-editing(`docs/{TASK,MODIFY,REPORT}.md`, CHG-20260724T064140-reanswer-model-select).

- **변경**:
  - `static/app.js` `_submitMessageEdit`: mode==="reanswer" 일 때 body 에 `model=_composerCurrentModel()`
    + `reasoning_level=_composerCurrentReasoningLevel()` 추가(정상 `/api/ask` askBody 와 동일 helper·
    동일 fallback chain). simple 수정은 재답변 없어 미포함 유지.
  - `routers/conversations.py` `post_edit_message`: reanswer `ask_body` 에 편집 body 의 model(비어있지
    않을 때)·reasoning_level(None/"" 아닐 때) forward. 부재 시 미포함 → `ask()` 가 기존대로
    `API_DEFAULT_MODEL`(claude-haiku-4) / config 기본 추론 폴백(구 클라이언트 하위호환). 형식·allowlist·
    reasoning 정규화는 `ask()` 가 재검증.
- **PRE-COMMIT 정적·단위 (PASS, 라이브 비의존)**:
  - 신규 `tests/test_message_editing_reanswer_model.py` **6 PASS**(격리 컨테이너 -v 확증): F1 model+reasoning
    forward · F2 부재 시 ask_body 미포함(기본 폴백 보존) · F3 명시 'normal' forward · F4 non-2xx(400/429)→
    편집 직전 브랜치 상태 복원 · F5 2xx→미복원 · S1 simple 미dispatch.
  - §18.8 적대적 리뷰(security+correctness 서브에이전트) = **SHIP**(신규 결함 0), MINOR 1건(non-2xx 보상
    복원 미비 — model forward 가 400 도달 경로 신설) in-cycle 하드닝. 정본 REVIEW REV-20260724T064140.
  - `make test`(agent 이미지 격리) 실행 — 신규 6 PASS 포함. 실패는 전부 pre-existing local-env 순서/환경
    flake, 본 변경 무관: (a) 기존 4건(test_routine_dbanalysis·test_runtime_settings×2·test_item11_batch8 —
    feature-0019 REPORT 문서화·CI 통과 실증), (b) `test_shutdown_finalizer.py::S1` — **격리 실행 시 3/3 PASS**
    (`pytest test_shutdown_finalizer.py`), full-suite 에서만 실패하는 **순서/자원경합 flake**. 근본: finalizer
    (app.py `_finalize_inflight_runs_on_shutdown`)가 호출하는 `_active_ask_job_conversation_ids()` 가
    worker-mode 시 실 PG I/O 를 하는데 S1 이 이를 stub 하지 않는 **테스트 격리 gap**(형제 테스트가 남긴
    worker-mode + 병렬 세션 고부하 시 I/O 가 raise→바깥 except 삼킴→`calls` 빔). 내 diff 는 finalizer/
    worker-mode 경로와 **code-disjoint**(post_edit_message reanswer + app.js + monkeypatch-only 테스트).
    CI(정본 게이트)·격리 실행 모두 GREEN. `ruff check` PASS.
- **Environment: Windows-browser (PB-0008) — PRE-COMMIT 라이브 미수행 사유**: 본 변경은 **동작 수정**이라
  실 시각검증이 (1) 배포된 프론트(app.js 는 web 이미지에 baked → merge+deploy 후에만 서빙) 와 (2) 배포된
  백엔드 + **AI 운영 계측(resolved model·추론예산 관측)** 을 요구한다. 미배포 코드에서는 사이트가 구
  동작(model/reasoning 미전송)을 서빙하므로 pre-commit 라이브 검증은 의미가 없다(카고컬트 방지 — headless
  로 통과 위장하지 않음). 따라서 정본 시각검증은 POST-DEPLOY.
- **POST-DEPLOY PB-0008 라이브 계획(정본, Windows-browser)**: 배포(web-only, deploy_scope: included) 후
  실 Windows Chrome(`bin/win-browser.py` CDP relay)로 `https://localhost/` 로그인 → 1:1 대화에서
  (a) 컴포저에서 model=**claude-sonnet** + 추론 강도=**매우높음** 선택, (b) 본인 user 메시지 hover→'수정'
  →요청사항 수정(재답변), (c) 재답변 생성 후 **관리 콘솔 'AI 운영' 활동/사용 내역**에서 해당 재답변의
  resolved model=sonnet · 추론예산 상향(≠haiku·≠일반) 확인, (d) `< n/m >` 버전 페이징·simple 수정 무회귀.
  pageerror 0. → 결과를 본 fragment 하단·REPORT/REVIEW 에 append.
