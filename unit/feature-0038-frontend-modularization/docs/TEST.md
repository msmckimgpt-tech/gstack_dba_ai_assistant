---
doc_type: TEST
feature_id: feature-0038-frontend-modularization
status: active
edit_policy: mixed
source_of_truth: true
---

# Test

<!-- §1, §2, §4는 rewrite (케이스 정의). §3은 append-only (실행 결과 이력). -->

## 1. Test Scope
- behavior-neutral 검증: 각 추출 cycle 이 렌더·인터랙션·서버 계약을 바꾸지 않았는지
- 제외: 기능 신규 동작 (본 initiative 는 동작 변경 0 이 계약)

> **검증 환경 분류 (AGENTS.md §15.4)** — §3 Run 의 `Environment` 는 아래 중 하나로 명시한다.
> 웹/UI(화면·상호작용) 검증은 **`Windows-browser` 만 인정**한다.
>
> | Environment | 의미 | UI 검증 인정 |
> |---|---|---|
> | `CLI` | curl / pytest / API 계약 | ✗ (서버 계약만) |
> | `WSL-headless` | WSL 내부 headless chromium | ✗ (화면 검증 불가) |
> | `Windows-browser` | 실제 Windows Chrome/Edge CDP 자동 구동 (`bin/win-browser.py`) | ✓ |

## 2. Test Cases

### TEST-20260803T170000-css-split-1 (byte-parity)
- Purpose: styles.css → css/ 7분할이 캐스케이드 관점에서 무손실임을 기계 증명
- Preconditions: 분할 완료 상태
- Steps: `cat css/{base,shell,chat,drawers,admin,profile,search-audit}.css | cmp static/styles.css(구) -`
- Expected Result: byte-identical (cmp exit 0)

### TEST-20260803T170000-css-split-2 (per-file 파싱 건전성)
- Purpose: 분할 경계가 주석/규칙 블록을 파일 간에 쪼개지 않았는지
- Steps: 파일별 `/* */` 균형 + 주석 제거 후 `{}` 균형 스캔
- Expected Result: 전 파일 균형 (원본 기존 결함 제외 — §3 Run 참조)

### TEST-20260803T170000-css-split-3 (실렌더)
- Purpose: 작업화면·관리콘솔이 분할 CSS 7장으로 동일 렌더
- Steps: PB-0008 — web-a/b 에 docker cp 주입(CSS-safe) → 실 Windows Chrome 로 / 및 /admin 진입, styleSheets 로드 수·landmark computed style·전체 스크린샷
- Expected Result: 7 sheets 로드·layout 정상·시각 회귀 0

### TEST-20260803T190000-usage-aiops-split-1 (역재구성 byte-parity)
- Purpose: admin.js → admin/usage.js·admin/aiops.js 이동이 배선 외 무수정임을 기계 증명
- Steps: 새 admin.js 에서 import 2줄 제거 + 포인터 주석 2줄을 모듈 본문으로 치환 + export 접두 4개 제거 → HEAD admin.js 와 cmp
- Expected Result: byte-identical

### TEST-20260803T190000-usage-aiops-split-2 (ESM 파싱·순환 안전)
- Purpose: 3파일 ESM 파싱 + 순환 import TDZ 안전(모듈 top-level 이 admin.js 바인딩을 평가 시점에 안 읽음)
- Expected Result: SourceTextModule 파싱 OK · 상태 초기화(adminState.usage/aiOps)는 admin.js 잔류

## 3. Test Run History
<!-- append-only: 새 실행 결과를 아래에 추가한다. 기존 결과를 수정하거나 삭제하지 않는다. -->

### Run 2026-08-03-001 (Cycle 1 기준선)
- Date: 2026-08-03
- Environment: CLI
- Runner: AI (claude-corp)
- Result Summary: 분할 전 실측 — styles.css 9,328줄 sha256=349ce797a2caf3…3190, admin.js 14,007줄, app.js 13,165줄. url()/@import 참조 0건 (분할 경로 안전 전제 확인).
- Pass/Fail: PASS (기준선 기록)

### Run 2026-08-03-002 (byte-parity + 파싱 건전성)
- Date: 2026-08-03
- Environment: CLI
- Runner: AI (claude-corp)
- Result Summary: 7파일 순차 concat `cmp` → **byte-identical**. 파일별 주석·중괄호 균형 스캔 → 전 파일 OK. admin.css 의 `/* … --text*/ … */` 주석 조기종료 1건은 **원본 L5577 에 기존재하는 pre-existing 결함**으로, 조기종료·잔여 토큰이 같은 파일 안에 온전히 보존되어 분할로 인한 동작 변화 없음 (REVIEW REV-20260803T174500-css-split 기록).
- Pass/Fail: PASS

### Run 2026-08-03-003 (headless — CSS 소비 스위트)
- Date: 2026-08-03
- Environment: WSL-headless
- Runner: AI (claude-corp)
- Result Summary: 분할 CSS concat 을 실 chromium 에 태우는 `verify_product_dropup_keynav.py` **27 passed / 0 failed** · `verify_product_dropup_scroll.py` **11 passed / 0 failed** (양 스크립트는 이번 cycle 에서 concat 로더로 갱신).
- Pass/Fail: PASS

### Run 2026-08-03-004 (make test 전 스위트)
- Date: 2026-08-03
- Environment: CLI
- Runner: AI (claude-corp)
- Result Summary: worktree 에서 `sudo make test` (격리 compose 프로젝트 `repo-unittest`) — **EXIT 0** (pytest feature-0002/0003/0023 전 스위트 PASS, ruff "All checks passed!"). 갱신된 CSS 참조 테스트 5파일(test_share_edit_usable·test_share_joinable_confirm_persist·test_permission_dependency_map + headless 2종) 포함.
- Pass/Fail: PASS

### Run 2026-08-03-005 (PB-0008 사전 시각검증 — 미머지 static QA)
- Date: 2026-08-03
- Environment: Windows-browser
- Runner: AI (claude-corp)
- Bridge: relay @ http://172.26.144.1:9223 — `win-browser.py doctor` ok:true, Chrome/150.0.7871.128, eval 프로브 `1+1`→2
- Evidence: `test-runs.d/evidence/20260803-css-split-workscreen.png` · `test-runs.d/evidence/20260803-css-split-admin.png`
- Result Summary: web-a/b 양 replica 에 css/ 7파일 + 신규 index/admin.html docker cp 주입(CSS-safe 사전 QA, 원본 백업 후) → LB 왕복 4회 신규 html 서빙 확인 → 실 Windows Chrome 진입. 작업화면: 7 sheets 전부 로드(cssRules>0)·`.app-shell` grid·`.sidebar` 252px·전체 스크린샷 정상. 관리콘솔: 7+graph.css 8 sheets·`.admin-pane` flex·`.admin-sidebar` 220px·대시보드 카드/차트/지표 전부 정상 렌더(스크린샷). 시각 회귀 0. QA 후 컨테이너 원상 복구(백업 html 재주입 + css/ 제거) 확인.
- Pass/Fail: PASS
- Notes: 주입 도중 병렬 세션의 PR #1120 배포로 컨테이너가 재생성되어 1회 재주입함 — QA 결과에는 영향 없음. POST-DEPLOY 재검증은 배포 후 Run 으로 별도 기록.

### Run 2026-08-03-006 (롤백 리허설)
- Date: 2026-08-03
- Environment: CLI
- Runner: AI (claude-corp)
- Result Summary: Cycle 1 커밋(44308fae)에 `git revert --no-edit HEAD` 실적용 →
  base(c0c6800f) 대비 `git diff` **0줄**(완전 원상: styles.css sha256 원본 일치
  349ce797…·css/ 소멸·html 단일 link 복원) → revert 제거 후 재적용·최신 main rebase.
  단일-PR 단일-revert 롤백 가능성 실증 — 이후 cycle 은 동일 절차 준용(§2.1 게이트 6).
  라이브 롤백은 deploy-web.sh last-good 병용.
- Pass/Fail: PASS

### Run 2026-08-03-007 (Cycle 1 POST-DEPLOY — 라이브 검증)
- Date: 2026-08-03
- Environment: Windows-browser
- Runner: AI (claude-corp)
- Bridge: relay @ http://172.26.144.1:9223, Chrome/150.0.7871.128
- Evidence: `test-runs.d/evidence/20260803-css-split-postdeploy-admin.png`
- Result Summary: PR #1124 머지 → deploy-web 스파인 배포(1da17988, soak 90s 통과·워커 롤아웃 포함, RC=0).
  라이브 검증 — 서빙 html 의 css 7-link 전부 스탬프 주입(`?v=c7ca8cf30ead`), 캐시 계약 실측
  (스탬프 일치 → `immutable`, 불일치 → `no-store`), 실 Windows Chrome: 작업화면 7 sheets
  로드·`.app-shell` grid / 관리콘솔 8 sheets·`.admin-pane` flex·스크린샷 정상. 시각 회귀 0.
- Pass/Fail: PASS

### Run 2026-08-03-008 (Cycle 2 — usage/aiops 추출 기계 검증)
- Date: 2026-08-03
- Environment: CLI
- Runner: AI (claude-corp)
- Result Summary: admin.js 14,007→13,050줄(-957). admin/usage.js 693줄·admin/aiops.js 289줄 신설.
  **역재구성 byte-parity IDENTICAL** (import 2줄·포인터 주석 2줄·export 접두 4개만이 델타임을 기계 증명).
  3파일 ESM 파싱 OK(SourceTextModule). import/export 표면 기계 산출 — usage←{adminState,apiFetch,
  _metaPopulateScopeSelect,activateAiConsoleSubtab,switchTab}·aiops←{adminState,apiFetch,
  mountGuidanceRegistryPanel}·역방향 export 는 loadUsage/loadAiOps 2개뿐(교차 0).
- Pass/Fail: PASS

### Run 2026-08-03-009 (Cycle 2 — make test 전 스위트)
- Date: 2026-08-03
- Environment: CLI
- Runner: AI (claude-corp)
- Result Summary: C2 worktree `sudo make test` (격리 compose `repo-unittest`) — **RC=0**
  (pytest feature-0002/0003/0023 전 스위트 PASS · ruff "All checks passed!"). 합본 로더로
  전환한 test_llm_budget_pane.py 3건 포함 — 이동 문자열 단언이 admin/aiops.js 를 통해 충족됨.
- Pass/Fail: PASS

### Run 2026-08-03-010 (Cycle 2 — 패널 BLOCKING 흡수 후 재검증)
- Date: 2026-08-03
- Environment: CLI
- Runner: AI (claude-corp)
- Result Summary: §18.8 패널 BLOCK(aiops.js 자유 식별자 `$` — 운영 현황 pane 크래시) 흡수:
  admin.js `export const $` + aiops.js import. 경계 재절단(usage=구 L1560–2238·aiops=구
  L2352–2626 — 주석-코드 정합 3곳 복구) 후 HEAD 재생성. 재검 — **역재구성 byte-parity
  IDENTICAL** · ESM 파싱 3파일 OK · **acorn-globals 자유 식별자 usage/aiops = 0/0** ·
  stale 포인터 주석 2건(app.js·admin.html) 갱신. admin.js 최종 13,058줄(-949).
- Pass/Fail: PASS

### Run 2026-08-03-011 (Cycle 2 POST-DEPLOY — 라이브 검증)
- Date: 2026-08-03
- Environment: Windows-browser
- Runner: AI (claude-corp)
- Bridge: relay @ http://172.26.144.1:9223, Chrome/150.0.7871.128
- Evidence: `test-runs.d/evidence/20260803-c2-postdeploy-usage.png`
- Result Summary: PR #1125 머지 → deploy-web 배포(3748c4fd, soak 통과, RC=0). 신규 모듈
  서빙 200 + 스탬프 전파(`?v=b01e2ae58857`) 확인. 실 Windows Chrome — error/unhandledrejection
  후크 설치 후: **'운영 현황' 서브탭(패널 BLOCK 축) 클릭 → 85,283자 렌더·KPI 표시·에러 0**,
  새로고침·'더 보기' 실행, 'LLM 사용량' 서브탭 → KPI/일별차트/모델도넛/역할막대/모델칩 13개
  렌더, 기간 변경 재조회·모델 칩 토글 실행 — **전 구간 pageerror 0**. 스크린샷 evidence.
- Pass/Fail: PASS

### Run 2026-08-03-012 (Cycle 3 — settings/audit 추출 기계 검증)
- Date: 2026-08-03
- Environment: CLI
- Runner: AI (claude-corp)
- Result Summary: admin.js 13,058→11,827줄(-1,231). admin/settings.js 881줄·admin/audit.js
  388줄 신설. **역재구성 byte-parity IDENTICAL** · ESM 파싱 5모듈 OK · **acorn-globals
  자유 식별자 settings/audit = 0/0**. 상태 초기화(adminState.settings/audit)는 admin.js
  잔류(TDZ 축 — Cycle 2 학습 선반영). mountGuidanceRegistryPanel 은 settings.js export +
  admin.js re-export 로 aiops.js 계약 보존. 참조 테스트 1건(test_audit_tamper_evidence F1)
  합본 전환. 검증기 자체 결함(푸터 제거 창 오류)으로 1차 MISMATCH → 규칙 정확화 후 IDENTICAL.
- Pass/Fail: PASS

### Run 2026-08-03-013 (Cycle 3 — make test 전 스위트)
- Date: 2026-08-03
- Environment: CLI
- Runner: AI (claude-corp)
- Result Summary: C3 worktree `sudo make test` — **RC=0** (pytest 전 스위트 PASS · ruff clean).
  합본 전환한 test_audit_tamper_evidence F1 포함.
- Pass/Fail: PASS

### Run 2026-08-04-014 (Cycle 3 POST-DEPLOY — 라이브 검증)
- Date: 2026-08-04
- Environment: Windows-browser
- Runner: AI (claude-corp)
- Bridge: relay @ http://172.26.144.1:9223, Chrome/150.0.7871.128
- Evidence: `test-runs.d/evidence/20260804-c3-postdeploy-settings.png`
- Result Summary: PR #1128 머지 → 배포(86c0d7c3, RC=0) → 신규 모듈 서빙 200·스탬프 전파
  (`?v=a71a85edb03b`). 실 Windows Chrome (error/unhandledrejection 후크): 시스템 > 설정
  목록 5행 렌더 → **5패널 순회 활성화 전건 실렌더**(prompts 2,481 · runtime-timeouts 25,100 ·
  model-thinking-budgets 9,719 · redteam-review 16,036 · performance-parallelism 26,212자) →
  감사 > 감사 로그 목록 **100행**·무결성 검증 버튼 존재 → re-export 경유 축(프롬프트 > 지침
  서브탭) 5,879자 렌더. **전 구간 에러 0**.
- Pass/Fail: PASS

### Run 2026-08-04-015 (Cycle 4 — accounts/roles 추출 기계 검증)
- Date: 2026-08-04
- Environment: CLI
- Runner: AI (claude-corp)
- Result Summary: admin.js 11,827→10,466줄(-1,361, 누적 -3,541). admin/accounts.js(792줄)·
  admin/roles.js(618줄) 신설. **역재구성 byte-parity IDENTICAL** · ESM 파싱 OK ·
  **acorn-globals 자유 식별자 6모듈 전부 0**. 신규 패턴: roles.js 가 accounts.js 의
  filteredAccounts 를 모듈 간 직접 import. 권한 grid 인프라(renderPermissionGrid·
  PERMISSION_DEPENDENCIES·groupedPermissions)는 두 pane 공유 코어라 admin.js 잔류
  (§2.1 "착수 시 심볼 재실측" 조항 — 표의 '권한 grid 포함' 문언을 경계 재실측으로 보정).
  참조 테스트 2건(two_factor·login_attempt_limit) 합본 전환.
- Pass/Fail: PASS

### Run 2026-08-04-016 (Cycle 4 — 패널 BLOCKING/MAJOR 흡수 후 재검증)
- Date: 2026-08-04
- Environment: CLI
- Runner: AI (claude-corp)
- Result Summary: 패널 BLOCK(test_llm_usage_quota f1/f2 — quota call-site 이동으로 make test
  RC=2) 흡수: `_read_admin_bundle()` 합본 전환. MAJOR(verify_profile_icon_admin_surfaces.mjs
  5단언 회귀) 합본 전환 → **17 PASS / 0 FAIL** 실측. MINOR(dead import filteredAccounts)
  제거. 재검 — 역재구성 byte-parity **IDENTICAL** · ESM OK. make test 재실행 별도 Run.
- Pass/Fail: PASS

### Run 2026-08-04-017 (Cycle 4 — make test 최종)
- Date: 2026-08-04
- Environment: CLI
- Runner: AI (claude-corp)
- Result Summary: 패널 흡수 후 최종 상태 `sudo make test` — **RC=0** (전 스위트 PASS · ruff
  clean; 수정 전 RC=2 였던 test_llm_usage_quota f1/f2 포함).
- Pass/Fail: PASS

### Run 2026-08-04-018 (Cycle 4 POST-DEPLOY — 라이브 검증)
- Date: 2026-08-04
- Environment: Windows-browser
- Runner: AI (claude-corp)
- Bridge: relay @ http://172.26.144.1:9223, Chrome/150.0.7871.128
- Evidence: `test-runs.d/evidence/20260804-c4-postdeploy-roles.png`
- Result Summary: PR #1129 머지 → 배포(475bde1b, RC=0) → accounts/roles 모듈 서빙 200.
  실 Windows Chrome (error 후크): 계정 pane 목록 **15행**·상세 권한 grid **94행 렌더 /
  65행 disclosure 게이트 접힘**(보안 표면 게이팅 정상) · 역할 pane 목록 **8행**·상세 권한
  grid **188행**(역할 편집기 전 권한 표시 정합)·제품 카드 139·pending bar 존재 — **전 구간
  에러 0**. (중간에 브라우저 탭이 작업화면으로 이탈해 재진입 1회 — 결과 무영향)
- Pass/Fail: PASS

### Run 2026-08-04-019 (Cycle 5 — products/datasources 추출 기계 검증)
- Date: 2026-08-04
- Environment: CLI
- Runner: AI (claude-corp)
- Result Summary: admin.js 10,466→**7,647줄**(-2,819 — 최대 감폭, 초기 대비 **-45.4%**).
  admin/datasources.js(795줄)·admin/products.js(2,090줄) 신설. **역재구성 byte-parity
  IDENTICAL** · ESM OK · **acorn-globals 8모듈 free-vars 전부 0**. Product subcatalog 는
  accounts/roles 공유 코어라 admin.js 잔류. 테스트: 리터럴-대조 스캔(12 플래그) →
  실행 판별 — verify_product_icon_chip_list.mjs 만 실회귀(기준선 18/1 → 13/6) → 합본
  전환으로 18/1 복구. 나머지 mjs 하네스 다수는 main 기준선에서도 동일 크래시/FAIL =
  **pre-existing**(REPORT §8 추적 누적). pytest 측 플래그는 백엔드 docstring 노이즈.
- Pass/Fail: PASS

### Run 2026-08-04-020 (Cycle 5 — make test 전 스위트)
- Date: 2026-08-04
- Environment: CLI
- Runner: AI (claude-corp)
- Result Summary: C5 worktree `sudo make test` — **RC=0** (pytest 전 스위트 PASS · ruff clean).
- Pass/Fail: PASS

### Run 2026-08-04-021 (Cycle 5 — 패널 BLOCKING 흡수 후 재검증)
- Date: 2026-08-04
- Environment: CLI
- Runner: AI (claude-corp)
- Result Summary: 패널 BLOCK(profile_icon_consistency 22P/1F→21P/2F 신규 회귀) 흡수 —
  합본 전환 후 **22/1 기준선 복구**. dead import 5건·dead export 3건 정리(표면 산출의
  주석-텍스트 집계 결함 교정 — 이후 cycle 주석-제거 후 스캔). 재검: 역재구성 byte-parity
  **IDENTICAL**(export 19 규칙) · free-vars 0/0 · 아이콘 하네스 3종 기준선 동치
  (22/1·18/1·17/0). make test 최종 재실행 별도 Run.
- Pass/Fail: PASS

### Run 2026-08-04-022 (Cycle 5 — make test 최종)
- Date: 2026-08-04
- Environment: CLI
- Runner: AI (claude-corp)
- Result Summary: 패널 흡수 후 최종 상태 `sudo make test` — **RC=0**.
- Pass/Fail: PASS

### Run 2026-08-04-023 (Cycle 5 POST-DEPLOY — 라이브 검증)
- Date: 2026-08-04
- Environment: Windows-browser
- Runner: AI (claude-corp)
- Bridge: relay @ http://172.26.144.1:9223, Chrome/150.0.7871.128
- Evidence: `test-runs.d/evidence/20260804-c5-postdeploy-products.png`
- Result Summary: PR #1130 머지 → 배포(03665d28, RC=0) → products/datasources 모듈 서빙 200.
  실 Windows Chrome (에러 후크): 제품 pane 목록 **19행**·상세 5,283자·**접근 DB allowlist
  섹션+picker 렌더**(보안 경계 UI)·pending bar 존재 · 데이터소스 pane **27행·엔진 아이콘
  27**·상세 렌더 · 역할 상세 제품카드 **39**(subcatalog 잔류↔이동 경계 온전) — 전 구간 에러 0.
- Pass/Fail: PASS

### Run 2026-08-04-024 (Cycle 6 — metadata 추출 기계 검증 + 하네스 부채 상환)
- Date: 2026-08-04
- Environment: CLI
- Runner: AI (claude-corp)
- Result Summary: admin.js 7,647→**4,805줄**(-2,842, 초기 대비 **-65.7%**). admin/metadata.js
  (2,869줄 — 최대 단일 모듈) 신설. **역재구성 byte-parity IDENTICAL** · ESM OK ·
  free-vars 는 mermaid-render 전역 브릿지 2건(HEAD 동일 pre-existing, typeof 가드) 외 0.
  _metaPopulateScopeSelect 는 re-export 로 usage.js 계약 보존.
  **동반 부채 상환**: styles.css 직독 mjs **20건**(STATIC/staticDir 변수명 무관 리터럴 전수)
  css/ concat 수선 + 도메인 합본 + 구계약 cache-buster 단언 6건 신계약 전환 + pre-C1
  기준선(fd61bb48) worktree 대조로 귀책 판별 — 초래 회귀 전부 수선(green 화:
  engine_dropdown 36/0·ds_list_engine_icon 17/0·bs_paging 32/0·bs_prefill 44/0·
  share_participants 17/0 등), **가동 하네스 전건 기준선 동치 이상**. 잔여 red/크래시는
  기준선 동일 pre-existing — inline_desc/list_detail 은 양 트리 동일
  `ReferenceError: _metaScopeIsProduct`(07-29 metadata-product-scope 이래, REPORT §8).
  pytest 1건(test_metadata_perm_split) 합본 전환.
- Pass/Fail: PASS

### Run 2026-08-04-025 (Cycle 6 — make test 전 스위트)
- Date: 2026-08-04
- Environment: CLI
- Runner: AI (claude-corp)
- Result Summary: `sudo make test` — **RC=0** (합본 전환한 test_metadata_perm_split 포함).
- Pass/Fail: PASS

### Run 2026-08-04-026 (Cycle 6 — 패널 흡수 후 최종)
- Date: 2026-08-04
- Environment: CLI
- Runner: AI (claude-corp)
- Result Summary: 패널 BLOCKING 3건(하네스 3건 변수명 누락·구계약 단언 3건·문서 오기) +
  MINOR(mermaid dead 배선 제거·admin.html 귀속 주석 2·assert 메시지) 전건 흡수. 패널 기준선
  오측 1건은 fd61bb48 재측정으로 반증(inline_desc/list_detail = 양 트리 동일 pre-existing
  ReferenceError). 수선 후 실측: share_participants 17/0·bs_prefill 44/0·member 계열 기준선
  동치. 최종 `sudo make test` — **RC=0**.
- Pass/Fail: PASS

### Run 2026-08-04-027 (Cycle 6 POST-DEPLOY — 라이브 검증)
- Date: 2026-08-04
- Environment: Windows-browser
- Runner: AI (claude-corp)
- Bridge: relay @ http://172.26.144.1:9223, Chrome/150.0.7871.128
- Evidence: `test-runs.d/evidence/20260804-c6-postdeploy-metadata.png`
- Result Summary: PR #1132 머지 → 배포(6f74d8cf, RC=0 — 병렬 세션 feature-0039 ops-scheduler
  동반 반영·rebase 충돌은 gen-status 재생성으로 해소) → metadata 모듈 서빙 200. 실 Windows
  Chrome (에러 후크): 지식베이스 > 메타데이터 **5서브뷰 순회 전건 렌더**(용어사전 7행·ENUM
  4행·테이블/컬럼/샘플 각 1행) · 검토·검수 큐 토글 · 부트스트랩 '스키마 골격 가져오기' 버튼
  표시 — 전 구간 에러 0.
- Pass/Fail: PASS

### Run 2026-08-04-028 (Cycle 7 — app.js type=module 전환 기계 검증)
- Date: 2026-08-04
- Environment: CLI
- Runner: AI (claude-corp)
- Result Summary: index.html script 태그 전환(app.js 자체 무변경 — 유일한 비-기계적 지점,
  단독 격리). 기계 실측: **ESM(strict) 파싱 OK** · **암묵 전역 쓰기 0**(AssignmentExpression
  좌변 free identifier 전수) · 비표준 free 읽기 = mermaid-render 전역 브릿지 2건뿐(typeof
  가드) · 동반 classic 5스크립트의 app.js 전역 참조 **0**(share.js 자체 선언·mermaid-render
  'initialize' 는 프로퍼티) · inline 핸들러 0. fallback(classic 순차 분할)은 §2.1 명시 유지.
- Pass/Fail: PASS

### Run 2026-08-04-029 (Cycle 7 — make test + 패널)
- Date: 2026-08-04
- Environment: CLI
- Runner: AI (claude-corp)
- Result Summary: §18.8 패널 **SHIP**(B0/M0 — index.html 소비 테스트 7종 HEAD↔변경 A/B 실행
  델타 0 · chromium 양팔 headless 스모크 module 팔 pageerror 0 · strict/전역 축 AST 전수 청정,
  MINOR 3건 기록 — 콜백 this 3건 → Cycle 8 계획 명기). `sudo make test` 1·2차는 **네트워크
  장애로 pip 이 PyPI 도달 불가**(RC=2 — pytest 미설치, 테스트 미도달·코드 무관). 회복 후
  재실행 결과는 다음 Run.
- Pass/Fail: PARTIAL (패널 PASS · make test 는 네트워크 회복 후 재실행)

### Run 2026-08-04-030 (Cycle 7 — make test 재실행, 네트워크 회복 후)
- Date: 2026-08-04
- Environment: CLI
- Runner: AI (claude-corp)
- Result Summary: PyPI 도달 회복 후 `sudo make test` — **RC=0, FAILED 0** (Run-029 의 RC=2
  는 pip 네트워크 장애로 확정 — 코드 무관).
- Pass/Fail: PASS

### Run 2026-08-04-031 (Cycle 7 POST-DEPLOY — 풀 스모크 라이브 검증)
- Date: 2026-08-04
- Environment: Windows-browser
- Runner: AI (claude-corp)
- Bridge: relay @ http://172.26.144.1:9223, Chrome/150.0.7871.128
- Evidence: `test-runs.d/evidence/20260804-c7-postdeploy-{workscreen,answer}.png`
- Result Summary: PR #1133 머지 → 배포(c4e613a2, RC=0) → 라이브 `type="module"` 스탬프 서빙.
  풀 스모크 — 부트(module 태그·사이드바·컴포저·auth hidden) · 대화 전환/히스토리 로드 ·
  새 대화 → 전송 → **POST /api/ask 200** → enqueue → worker claim → 진행 표시(폴러) →
  **답변 완주 렌더**("2", 36초: 대기 0.4·준비 2.6·추론 33) · 프로필 drawer · 관리 링크 —
  **전 구간 JS 에러(error/unhandledrejection) 0**.
  검증 중 특이사항 2건 (전부 리팩터 무관 입증): ① 실사용자가 동일 Windows Chrome 사용 중
  → 탭 전환 간섭 수 회(서버 로그·DB 교차로 갈라냄) ② 호스트 광역 네트워크 장애 창(전
  datasource probe down·PyPI/GitHub DNS 실패)에서 ask 2건이 회로차단 오류 종결(ask_jobs
  555/556 — **프론트는 오류를 정확히 표면화**, 회복 후 재시도 완주). 오류 경로·완주 경로
  양쪽 검증 완료.
- Pass/Fail: PASS

### Run 2026-08-04-032 (Cycle 8 — app/auth·profile 추출 기계 검증)
- Date: 2026-08-04
- Environment: CLI
- Runner: AI (claude-corp)
- Result Summary: app.js 13,216→**12,431줄**(-785). app/auth.js(253)·app/profile.js(571)
  신설 — **비연속 다중 세그먼트**(auth 2·profile 3, 구분자 주석 연결) 방식 최초 적용.
  **역재구성 byte-parity IDENTICAL** · ESM OK · free-vars 0/0. 사전 검사로 **ESM
  import-binding write 함정 적발·회피**: handleLogout 이 전역 타이머 let 을 재할당 →
  의도적 잔류(경계 재실측 조항). C7 패널 MINOR-1(콜백 this 함수식 유지) 준수.
  테스트 1건(test_two_factor_auth) 합본 전환.
- Pass/Fail: PASS

### Run 2026-08-04-033 (Cycle 8 — make test)
- Date: 2026-08-04
- Environment: CLI
- Runner: AI (claude-corp)
- Result Summary: `sudo make test` — **RC=0** (합본 전환 test_two_factor_auth 포함).
- Pass/Fail: PASS

### Run 2026-08-05-034 (Cycle 8 — 패널 SHIP + MINOR 흡수 재검)
- Date: 2026-08-05
- Environment: CLI
- Runner: AI (claude-corp)
- Result Summary: §18.8 패널 **SHIP**(B0/M0 — 역재구성 sha256 동일·binding-write 0·
  컨테이너 pytest 111 passed·headless A/B 로그인 풀 경로 동작). MINOR 3건 흡수(dead
  import 제거·conv-date-tree 주석 경계 재절단·헤더 레인지 정정) 후 재검 — parity
  **IDENTICAL** · free-vars 0/0.
- Pass/Fail: PASS

### Run 2026-08-05-035 (Cycle 8 POST-DEPLOY — 라이브 검증)
- Date: 2026-08-05
- Environment: Windows-browser
- Runner: AI (claude-corp)
- Bridge: relay @ http://172.26.144.1:9223, Chrome/150.0.7871.128
- Evidence: `test-runs.d/evidence/20260805-c8-postdeploy-profile.png`
- Result Summary: PR #1141 머지 → 배포(3d08b1e5, RC=0) → app/{auth,profile}.js 서빙 200.
  실 Windows Chrome (에러 후크): 프로필 drawer **열기·탭 3종·전환·리사이즈 핸들·닫기**
  전 상호작용 PASS — 에러 0. **로그아웃→로그인 왕복은 라이브 미수행 (사유)**: 실사용자
  활성 세션(같은 Windows Chrome 공유)을 강제 종료하는 조작이라 보류 — 패널의 headless
  A/B 가 로그인 폼 submit→handleLogin(모듈)→apiFetch→오류 렌더 **풀 경로를 이미 실증**
  (REV-20260805T093000), C7 풀 스모크가 로그인-후 부트 경로를 라이브 검증. 다음 로그인
  왕복 기회(사용자 비활성 창)에 보강 가능.
- Pass/Fail: PASS (사유 명시 — §15.4.1)

### Run 2026-08-05-036 (Cycle 9 — 폴더 관리 추출 기계 검증)
- Date: 2026-08-05
- Environment: CLI
- Runner: AI (claude-corp)
- Result Summary: app.js 12,430→**12,069줄**(-361). app/sidebar.js(381줄 — 폴더 로드·트리·
  생성/이름변경/설정/삭제·undo·이동 다이얼로그·메뉴) 신설, 비연속 2세그먼트.
  **역재구성 byte-parity IDENTICAL** · ESM OK · free-vars 0. **양방향 binding-write
  사전 검사**가 공유 DnD `let _dqaDrag` 의 이동 불가 결합(잔류 renderConversationList +
  중첩 핸들러가 직접 쓰기)을 적발 → 주석+let 잔류, renderConversationList 분리는
  _dqaDrag 의 state 편입(비-중립 mini-change) 승인 후 후속으로 기록. 리터럴-대조 결합 0.
- Pass/Fail: PASS

### Run 2026-08-05-037 (Cycle 9 — make test)
- Date: 2026-08-05
- Environment: CLI
- Runner: AI (claude-corp)
- Result Summary: `sudo make test` — **RC=0**.
- Pass/Fail: PASS

### Run 2026-08-05-038 (Cycle 9 — 패널 SHIP)
- Date: 2026-08-05
- Environment: CLI
- Runner: AI (claude-corp)
- Result Summary: §18.8 패널 **SHIP**(B0/M0 — headless A/B 사이드바 DOM 992B 동일·새 폴더
  생성→rename→커밋 플로우 동등·컨테이너 pytest 161+33 passed). MINOR 3(표기류) 흡수/기록.
- Pass/Fail: PASS

### Run 2026-08-05-039 (Cycle 9 POST-DEPLOY — 라이브 검증)
- Date: 2026-08-05
- Environment: Windows-browser
- Runner: AI (claude-corp)
- Bridge: relay @ http://172.26.144.1:9223, Chrome/150.0.7871.128
- Evidence: `test-runs.d/evidence/20260805-c9-postdeploy-sidebar.png`
- Result Summary: PR #1142 머지 → 배포(7e229e35, RC=0) → app/sidebar.js 서빙 200.
  실 Windows Chrome (에러 후크): 새 폴더 버튼 → **POST /api/folders 200 → '새 폴더' 렌더**
  (createFolderFlow 이동분 라이브 동작) → 테스트 폴더 API 삭제 정리(id 21) · 대화 행
  **dragstart 시각 표식 동작**(잔류 _dqaDrag 경로 회귀 없음) — 전 구간 에러 0.
- Pass/Fail: PASS

### Run 2026-08-05-040 (Cycle 10 — messages 렌더 추출 기계 검증)
- Date: 2026-08-05
- Environment: CLI
- Runner: AI (claude-corp)
- Result Summary: app.js 12,068→**11,119줄**(-949). app/messages.js(960줄 — markdown/SQL/
  CSV/스텝 패널/상세/첨부 칩/아바타) 신설, 단일 연속 세그먼트(구 L3118–4068).
  **역재구성 byte-parity IDENTICAL** · ESM OK · free-vars 0(표준 전역 외) ·
  양방향 binding-write 0 · top-level 실행문 0. 테스트 5건(py 1 + mjs 4) 합본 전환.
- Pass/Fail: PASS

### Run 2026-08-05-041 (Cycle 10 — make test)
- Date: 2026-08-05
- Environment: CLI
- Runner: AI (claude-corp)
- Result Summary: `sudo make test` — **RC=0** (합본 전환 test_msg_speaker_attribution_web 포함).
- Pass/Fail: PASS

### Run 2026-08-05-042 (Cycle 10 — 패널 SHIP)
- Date: 2026-08-05
- Environment: CLI
- Runner: AI (claude-corp)
- Result Summary: §18.8 패널 **SHIP**(B0/M0 — headless A/B 렌더 8,253자 byte-동일·마커
  7종 실증·mjs 19종 A/B FAIL-set 동일=회귀 0). MINOR 3(표기류) 흡수/기록.
- Pass/Fail: PASS

### Run 2026-08-04-043 (Cycle 10 POST-DEPLOY — 라이브 검증)
- Date: 2026-08-04
- Environment: Windows-browser
- Runner: AI (claude-corp)
- Bridge: relay @ http://172.26.144.1:9223, Chrome/150.0.7871.128
- Evidence: `test-runs.d/evidence/20260805-c10-postdeploy-messages.png`
- Result Summary: PR #1143 머지 → 배포(e7d2bf93, RC=0) → app/messages.js 서빙 200.
  실 Windows Chrome (에러 후크): 기존 대화 렌더 — **markdown 39노드·SQL 패널 5·details 3·
  아바타 7** 전부 정상 표출, 에러 0.
- Pass/Fail: PASS

## 4. Untested Areas
- (Cycle 2) JS 변경은 미머지 docker cp 사전 QA 불가(ES module 스탬프 미주입 시 이중 인스턴스·모듈 캐시
  함정 — 확립된 제약). 사전 검증은 make test + ESM 파싱 + byte-parity 로 갈음하고, **실브라우저
  검증은 배포 직후 POST-DEPLOY PB-0008**(LLM 사용량·AI 운영 현황 pane 렌더+인터랙션)로 수행한다.
- 공유 뷰(share.html)는 본 initiative 영향 없음

## 20260805T1055-phaseA-state-intake — 공유 let 2건 state 편입 (Phase A mini-change)

### Run — 20260805T1055 정적·소스-추출 검증 (Environment: CLI/node) — PASS
- 치환 실측: `_dqaDrag` 14건 · `_sidebarCatchupTimer` 8건 → bare 잔존 **0** (전 static 트리
  grep + 주석 제외 스캔) · ESM 문법 검사 PASS.
- 계약 가드 신설 `tests/verify_state_intake.mjs` **15/15 PASS** — [A] let 소멸+state 프로퍼티+
  잔존0 [B] DnD 세터/가드·catchup 이 state 경유 배선 [C] _scheduleSidebarCatchup 동적 왕복
  (타이머 저장→디바운스 clear→만료 해제).
- 전 mjs 하네스 회귀: **40/40 rc=0** (소스-추출 하네스들이 신 코드 형상으로 green — 특히
  verify_new_conv_dedup 의 renderConversationList eval 경로 정상).

### Run — PB-0008 시각검증 (Environment: Windows-browser — POST-DEPLOY 예정, 사전 미수행 사유 명시)
- **사전 미수행 사유**: JS(ES module) 변경 — 본편 Cycle 2~10 과 동일한 확립 제약(docker cp
  사전검증은 모듈 캐시 이중 인스턴스 함정). 사전 검증은 기계 증명(잔존 0·계약 가드·전수
  하네스 green)으로 갈음.
- **POST-DEPLOY 계획**: 실 Windows Chrome — ① 사이드바 대화 행 드래그 → 폴더 드롭(이동) ②
  폴더 헤더 드래그 → 순서 변경 ③ '새 폴더' 버튼 root 드롭존(폴더에서 빼기) ④ 새 메시지 도착
  시 사이드바 unread catch-up 갱신(디바운스) ⑤ 로그아웃 시 타이머 정리(콘솔 에러 0) + 스크린샷.
