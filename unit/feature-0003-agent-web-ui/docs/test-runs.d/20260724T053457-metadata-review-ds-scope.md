### Run (2026-07-24) — metadata-review-ds-scope: 메타데이터 거버넌스 검토 큐 datasource 필터 + 자동승급 목록 정합 + 등록 시각 표시 — **Environment: Windows-browser**

- 대상 변경: `static/admin.js`(frontend — `_metaReviewScopeParam` 신규·3개 큐 로더 scope_key 전송·`_metaListRow`/`renderFeedbackQueue`/`_metaRenderReviewDetail`/`_metaBuildEnumBundle` 등록 시각·`_metaPrimeReviewBadge` scope·sample 날짜 통일) + §18.8 Finding 1 반영 additive 백엔드(`kb_glossary.count_glossary_feedback`/`count_enum_feedback` scope_key 파라미터·`admin_metadata` 엔드포인트 scope_filter 전달) + 테스트 monkeypatch 2건. RBAC·스키마·엔드포인트 shape·마이그 0.
- PRE-COMMIT 검증(자동, 라이브 비의존):
  - `node --check`(ESM, scratchpad `.mjs` 복사 parse-only) PASS · `py_compile`(kb_glossary/admin_metadata) PASS.
  - `verify_metadata_list_detail.mjs` — clean main baseline 대조 **신규 회귀 0**(worktree 26 PASS / 3 FAIL == baseline 26 PASS / 3 FAIL, FAIL 집합 identical). `[D]` jsdom 섹션 `_metaSyncViews is not defined` crash 및 `[B4]` 3 FAIL 은 테스트 하니스의 함수-추출 eval 방식 노후화(clean main 동일) — 본 변경과 무관한 pre-existing.
  - pytest(agent 이미지 격리 컨테이너) **116 PASS / 0 FAIL** — feature-0003 metadata(glossary-autoreg/enum-feedback/sample-curation) 44 + feature-0002 glossary/enum 72(count scope 파라미터 additive·회귀 0).
  - 리스트는 3개 큐 엔드포인트(glossary-feedback/enum-feedback/sample-feedback)의 기존 optional `scope_key` + `created_at` 반환 계약 재사용, 배지는 count 함수 scope 파라미터 신설로 정합.
  - jsdom/headless 한계: 실 데이터소스 셀렉터 조작→큐 재필터·자동승급 항목 목록 정합·등록 시각 실렌더는 실 대화 데이터 + 실 admin 세션 + layout 이 필요해 headless 실측 부적합 → 아래 POST-DEPLOY PB-0008 로 정본 확인(카고컬트 방지 — headless 통과 위장 안 함). 정적 자산(ES module)은 web 이미지에 baked + cache-buster `?v=dev` 빌드 자동주입(inject_asset_stamp content-hash) → 서빙본 반영은 merge + `deploy-web` 재배포 선행.
- §18.8 적대 리뷰: frontend/correctness/security 렌즈(SUBAGENT) — REVIEW.md REV-20260724T053457-metadata-review-ds-scope.
- POST-DEPLOY PB-0008 라이브 계획(정본, Windows-browser): 배포(web-only, deploy_scope: included) 후 실 Windows Chrome(`bin/win-browser.py` CDP relay)로 https://localhost/admin 로그인 → `지식베이스 > 메타데이터` →
  1. **검토 큐 datasource 필터**: 상단 데이터소스 셀렉터에서 특정 datasource 선택 시 용어/ENUM/샘플 검토 큐가 그 datasource 후보로 필터, '공용' 선택 시 전체 표시(pending 배지 수와 정합).
  2. **자동승급 목록 정합**: 자동승급(auto_promoted) 후보가 있는 datasource 선택 → 검토 큐에서 확인 → '목록' 보기로 전환 시 동일 항목이 목록에 조회됨.
  3. **등록 시각**: 용어/ENUM/샘플 목록 행 + 검토 큐 행·상세 + ENUM 묶음 행에 `등록 <시각>` 표시.
  - pageerror 0 확인. 결과를 본 fragment 하단·REPORT/REVIEW 에 append.

### POST-DEPLOY 결과 (2026-07-24, 배포 2b22b5ff → main) — **Environment: Windows-browser** — PASS
- 방법: PB-0008 — `bin/win-browser.py` CDP relay 실 Windows Chrome, https://localhost/admin(bootstrap_admin 세션). eval "1+1"=2 relay 게이트 통과. `/livez` git_commit=2b22b5ff · 서빙 `/static/admin.js?v=e8a2d7019ebb` 에 `_metaReviewScopeParam` 4건 curl 확증.
- **Fix 1 (검토 큐 datasource 필터) PASS**: `지식베이스 > 메타데이터 > 용어사전 > 용어 검토 큐`, scope=**공용**일 때 96건(여러 datasource: mysql-kr-an1-auth·mysql-mv-dev… 혼재=전체 triage), 데이터소스 셀렉터를 **mysql-kr-an1-auth**(scope_key mysql-ce4d6fb514bc)로 변경 시 **16건**으로 필터되고 16행 전부 `scope: mysql-kr-an1-auth`(타 datasource 후보 미표시).
- **MAJOR 배지 정합(§18.8 Finding 1) PASS**: 용어 검토 큐 배지가 공용=**96**(=리스트 96건), mysql-kr-an1-auth=**16**(=리스트 16건) — 배지↔리스트 카운트 datasource 선택에 정합(수정 전이면 배지 96 고정 표시).
- **Fix 2 (자동승급 항목 목록 가시성) PASS**: mysql-kr-an1-auth 에서 '용어 목록' 보기 전환 → **84건**, 그중 **82건 "자동등록" 배지**(자동수집/자동승급 kb_glossary 항목이 해당 datasource 목록에서 조회). 스크린샷에 dbGame·전용보물·ItemIndex 등 자동등록 용어 확인.
- **Fix 3 (등록 시각) PASS**: 검토 큐 96행·목록 84행 전부 `등록 2026. 07. 24. 오후/오전 …` 표기(`_metaFmtDt`). 스크린샷 각 행 하단 "등록 …" 육안 확인.
- pageerror 0(window.__errs). 스크린샷: scratchpad `metadata-ds-list-registered.png`(mysql-kr-an1-auth 용어 목록 84건·자동등록 배지·등록 시각·검토 큐 배지 16). 원 마찰 3건(datasource 미필터·자동승급 목록 미조회·등록 시점 미표시) 전부 해소 확인.
