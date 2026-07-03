---
doc_type: TEST
feature_id: feature-0003-agent-web-ui
status: active
edit_policy: mixed
source_of_truth: true
---

# Test

## 1. Test Policy
- Web UI의 화면/상호작용 검증은 실제 브라우저 기반으로 수행한다.
- 계정/권한/소유권과 같은 서버 계약 검증은 curl 또는 SQL 확인을 병행할 수 있다.
- 브라우저 자동화 API 엔드포인트: `http://localhost:18081`
- 스크린샷 증빙은 `/shared/out/browser`에 저장한다.

## 2. Test Scope
- 계정 기반 로그인/회원가입이 실제로 동작하는지 확인
- 기본 signup role 전환과 role CRUD가 동작하는지 확인
- 계정 role assignment, tri-state override, soft delete가 동작하는지 확인
- 대화 목록/히스토리/제목 변경/삭제/중단/즉시답변이 own/any 권한 기준으로 분기되는지 확인
- 메인 화면이 외부 스크롤 없는 App-Shell 레이아웃으로 렌더링되는지 확인
- 프로필 드로어가 계정 / 보안 / API Vault 탭 구조로 동작하는지 확인
- Admin 콘솔의 검색 / 필터 / role/override 편집이 동작하는지 확인
- role명 휴리스틱 없이 permission + ownership만으로 판정하는지 확인
- 외부 Local LLM gateway 연결 시 API 키 없이 `model=auto` 요청이 가능한지 확인
- 외부 Local LLM provider 미기동 시 `model=auto` 요청이 503으로 제한되는지 확인

### 2.1 Audit subsystem (TASK-0073, Critical §12.3)

본 cycle 의 audit subsystem 검증 case (`tests/test_audit_*.py` 3 file = 20 시나리오 — 실 실행은 컨테이너 가동 후):

- **dispatcher unit** (`test_audit_dispatcher.py` D1~D7): `record_audit_event(conn, ...)` 호출 후 WebAuditEvents row visible / actor / target / change_json 필드 매핑 정합 / ChangeJson allowlist (`_AUDIT_BUILDER_*_FIELDS`) / masked_fields list redact 정합 / unknown action ValueError raise / admin Same tx fail-safe (code review) / `bin/verify-completion.sh check_11` symbol 정적 grep.
- **RBAC enforcement** (`test_audit_rbac.py` S1~S10): admin mutation Same tx → audit row visible / `/api/ask` user fail-open → row visible / `.own` SQL filter Actor OR Target / **S3a (E1 B 핵심)** admin password-reset → user 본인 audit 에 target row 노출 / `.own` actor=other → empty (404 byte-equal metadata leak 차단) / `.any` 전체 row / `audit.export` CSV / `audit.purge` chunked w/ idempotency_key / **S8 prod fail-closed** (manual 컨테이너 재시작) / **S9 anonymous share view** → ActorType='anonymous' + ActorAccountId NULL row / S10 `?actor_type=anonymous` filter.
- **migration smoke** (`test_audit_migration.py` M1~M3): legacy WebAccountActivity row INSERT → 다음 fast-path catchup 시 WebAuditEvents 등재 (`RequestId='account-activity:<id>'` marker) / idempotent (두 번째 호출 0 row) / `_log_search_activity` dual write coverage (legacy + new count).
- **AGENT_AUDIT_ENABLED prod fail-closed** (Phase E manual): `AGENT_AUDIT_ENABLED=0` + `AGENT_MODE=prod` → container 시작 시 stderr `[FATAL] AUDIT REQUIRED IN PROD — set AGENT_AUDIT_ENABLED=1` 후 process 종료.
- **admin UI smoke** (Phase E browser headless): admin → 감사 로그 탭 진입 → filter 적용 → list row click → detail pane 의 ChangeJson `<pre>` HTML escape 검증 → CSV button (admin 한정 visible) → 새 admin action 발생 (role 생성 등) 후 audit list 에 1:1 row 등장 검증.

### 2.2 verify-completion check_12 audit endpoint routing (TASK-0093, Minor §12.3)

본 cycle 의 정책 인프라 검증 case (`bin/verify-completion.sh` 의 `check_12_audit_endpoint_routing()` + `_check_audit_routing_order()` helper):

- **TEST-0093-A1 (positive, production)**: production `unit/feature-0003-agent-web-ui/src/app.py` 호출 → `CHECK#12 PASS audit endpoint routing order`. 검증 명령:
  ```bash
  WORKTREE=/root/download/docker/mysql_ai_delegated_dev/.worktrees/0086-audit-followup
  cat > /tmp/run-check12.sh << 'EOF'
  #!/usr/bin/env bash
  sed '/^main "\$@"$/d' "$WORKTREE/bin/verify-completion.sh" > /tmp/_helpers.sh
  source /tmp/_helpers.sh
  _check_audit_routing_order "$1"
  EOF
  chmod +x /tmp/run-check12.sh
  /tmp/run-check12.sh "$WORKTREE/unit/feature-0003-agent-web-ui/src/app.py"
  ```
- **TEST-0093-C1 (negative, valid fixture)**: 정합 ordering fixture → PASS.
- **TEST-0093-C2 (negative, wrong_order fixture)**: event_id BEFORE static siblings → FAIL ordering hint (line number + worst sibling 명시).
- **TEST-0093-C3 (negative, no_detail fixture)**: detail endpoint 부재 → FAIL "static audit GET sibling(s) detected but '/{event_id}' detail endpoint missing".
- **TEST-0093-C4 (negative, no_siblings fixture)**: 정적 GET sibling 부재 → FAIL "'/{event_id}' detail endpoint detected but no static GET siblings".
- **TEST-0093-C5 (negative, refactored fixture)**: APIRouter prefix 패턴 → FAIL "audit routes not found in expected form".
- **TEST-0093-D1~D5 (SKIP, other feature)**: feature-0001 / 0002 / 0004 / 0005 / 0006 호출 → silent return 0, no output.
- **TEST-0093-D6 (structural FAIL, missing app.py)**: target feature 인데 app.py 부재 → FAIL "expected app.py at <path> but file is missing".

검증 시점 (2026-05-20): Phase A~D 모두 PASS — 8 scenario (1 production positive + 5 fixture negative + 5 other-feature SKIP + 1 missing-app structural FAIL) 검증 완료.

### 2.3 외부 LAN trust 강화 — `_get_client_ip()` 조건부 trust + Caddy XFF 정규화 (TASK-0087, Major §12.3)

본 cycle (TASK-0087, REQ-20260520-0002, **Major** §12.3) 의 검증 시나리오. Codex outside voice (REV-20260520-0010) 권장 8 시나리오 + 본 cycle 추가 확장.

**Phase A** — Caddyfile 정규화 검증:
- **TEST-0087-A1 (positive, caddy validate)**: `docker compose run --rm caddy caddy validate --config /etc/caddy/Caddyfile` → exit 0. `header_up X-Forwarded-For {client_ip}` directive 인식.
- **TEST-0087-A2 (live, header replace)**: Caddy 컨테이너 가동 + 외부 클라이언트가 `curl -H 'X-Forwarded-For: 1.2.3.4' https://<HOST>/api/session` → web 측에서 `request.headers['x-forwarded-for']` 가 Caddy container IP (예: 172.18.0.x) 로 정규화됨 (1.2.3.4 가 아님). live 검증 사용자 위임.

**Phase B** — `_get_client_ip()` unit 시나리오 (Codex 권장 8건 + 확장):
- **TEST-0087-B1 (trusted proxy + valid XFF)**: `WEB_TRUSTED_PROXIES=172.18.0.0/16`, direct_ip=`172.18.0.5`, XFF=`1.2.3.4` → return `1.2.3.4`.
- **TEST-0087-B2 (trusted proxy + invalid XFF)**: 같은 env, direct_ip=`172.18.0.5`, XFF=`garbage` → return `172.18.0.5` (direct_ip fallback).
- **TEST-0087-B3 (trusted proxy + empty 첫항목)**: 같은 env, XFF=`,1.2.3.4` (콤마 시작) → 첫 토큰 빈 문자열 → `ipaddress.ip_address("")` ValueError → return `172.18.0.5`.
- **TEST-0087-B4 (untrusted direct_ip + spoofed XFF)**: `WEB_TRUSTED_PROXIES=172.18.0.0/16`, direct_ip=`192.168.1.10`, XFF=`1.2.3.4` → return `192.168.1.10` (spoof 차단).
- **TEST-0087-B5 (IPv6 trusted + IPv6 XFF)**: `WEB_TRUSTED_PROXIES=fd00::/8`, direct_ip=`fd12::1`, XFF=`2001:db8::1` → return `2001:db8::1`.
- **TEST-0087-B6 (bare IP /32, /128)**: `WEB_TRUSTED_PROXIES=172.18.0.5/32`, direct_ip=`172.18.0.5` → trusted. direct_ip=`172.18.0.6` → untrusted, direct_ip return.
- **TEST-0087-B7 (empty WEB_TRUSTED_PROXIES)**: env 미설정, direct_ip=`172.18.0.5`, XFF=`1.2.3.4` → return `172.18.0.5` (XFF 완전 무시).
- **TEST-0087-B8 (XFF with port)**: `WEB_TRUSTED_PROXIES=172.18.0.0/16`, direct_ip=`172.18.0.5`, XFF=`1.2.3.4:5678` → `ipaddress.ip_address("1.2.3.4:5678")` ValueError → return `172.18.0.5`.

**Phase C** — startup gate 검증 (mode-aware):
- **TEST-0087-C1 (invalid CIDR + prod fatal)**: `WEB_TRUSTED_PROXIES=invalid_cidr,10.0.0.0/8`, `AGENT_MODE=prod` → app.py import 실패, `RuntimeError("WEB_TRUSTED_PROXIES: invalid CIDR(s) in prod: ['invalid_cidr']")`.
- **TEST-0087-C2 (invalid CIDR + dev warning)**: `WEB_TRUSTED_PROXIES=invalid_cidr,10.0.0.0/8`, `AGENT_MODE=dev` → app.py import 성공, stderr WARNING 출력. `WEB_TRUSTED_PROXIES` = `(IPv4Network('10.0.0.0/8'),)` (invalid 만 skip).
- **TEST-0087-C3 (proxy mode + empty + prod fatal)**: `WEB_TRUSTED_PROXIES=""`, `ENABLE_WEB_TLS_PROXY=1`, `AGENT_MODE=prod` → `RuntimeError("WEB_TRUSTED_PROXIES is empty while ENABLE_WEB_TLS_PROXY=1 in prod ...")`.
- **TEST-0087-C4 (proxy mode + empty + dev warning)**: 같은 env, `AGENT_MODE=dev` → stderr WARNING. import 성공.

**검증 방법** (단위):
```bash
# B1~B8: pytest 또는 Python REPL 으로 직접 호출 (Request mock + headers dict)
docker compose run --rm \
  -e WEB_TRUSTED_PROXIES=172.18.0.0/16 \
  -e AGENT_MODE=dev \
  --entrypoint python web -c "
from web.app import _get_client_ip, _is_trusted_proxy
print(_is_trusted_proxy('172.18.0.5'))   # True
print(_is_trusted_proxy('192.168.1.10')) # False
"

# C1: prod fatal
docker compose run --rm \
  -e WEB_TRUSTED_PROXIES='invalid_cidr,10.0.0.0/8' \
  -e AGENT_MODE=prod \
  --entrypoint python web -c "import web.app" 2>&1 | grep "WEB_TRUSTED_PROXIES: invalid"

# C3: proxy mode + empty + prod fatal
docker compose run --rm \
  -e WEB_TRUSTED_PROXIES='' \
  -e ENABLE_WEB_TLS_PROXY=1 \
  -e AGENT_MODE=prod \
  --entrypoint python web -c "import web.app" 2>&1 | grep "WEB_TRUSTED_PROXIES is empty"
```

검증 시점 (2026-05-21): Phase A~B (코드 변경) 적용 완료, py_compile PASS. B1~B8 / C1~C4 단위 검증은 사용자가 docker 환경에서 위 명령으로 진행 (TEST.md §4 Test Run History 에 결과 기록).

## 3. Test Cases

### TASK-20260703-graphux6-panelbottom-responsive-obs 상세 패널 하단 이동 + 그래프 반응형 높이 + 운영현황 분석 대상 관측 (Major §12.3, 2026-07-03, feature-0016 cross-cut) — **Environment: Windows-browser (①패널 배치·②세로 반응형 레이아웃·③최근활동 대상 표시는 실 브라우저 렌더/뷰포트 거동 — de-risk=컨테이너 make test 전건 + 적대리뷰 + 라이브 PB-0008 배포 후 잔여, visual_verification_scope: always)**
- 대상: 관리콘솔 > 메타데이터 > 그래프 뷰(패널 하단·반응형 높이) + AI 운영 현황 > 최근 활동(분석 대상). 변경: `static/admin.html`·`static/styles.css`·`static/admin.js`·`routers/ai_ops.py` + feature-0002 `modules/llm.py`·`scripts/agent_runtime_schema.sql`·`alembic 0032_llm_usage_target` + `tests/test_ai_ops.py`.
- **구조·구문**: `py_compile` (ai_ops.py·llm.py·0032) PASS · `node --check admin.js` PASS · alembic 단일 head=0032.
- **단위(agent 이미지 격리, DB 없이 monkeypatch/fake)**: 컨테이너 `make test` **전건 PASS**(feature-0002+0003, ruff clean). `test_ai_ops.py` **16/16** — target SELECT/item 통과(짝수=`public.tbl_*` 대상, 홀수 None) + 신규 컬럼부재 폴백 `test_query_activity_target_column_absent_fallback`(rollback→base 재조회→target=None) + 기존 회귀. `test_llm_usage_record.py` **7/7** — target 을 total_tokens·latency_ms 사이 삽입해 param 위치(pt=5·lat=마지막) 보존.
- **§18.8 적대 패널(subagent 2라운드)**: **VERDICT PASS-WITH-FIXES** — round-1(5축) BLOCKING 0·MEDIUM 1(M1 wide-short 빈 캔버스)·NIT 4, round-2(CSS 집중 6축) BLOCKING 0·MEDIUM 1(440 floor 과잉→노트북 스크롤·헤더 아웃). **모든 지적 수정**: 캔버스 min-height:200(빈캔버스 방어)·그래프 하한 제거(노트북 스크롤 회피)·전너비 :has() pane 스크롤(잘림 방지)·이중 :not 가드·test mock target=None·INSERT 폴백 테스트. 잔여 NIT(≈<560px viewport 헤더 스크롤, :has() 구형 미지원) 수용. REVIEW.md REV-20260703T105541-graphux6-panelbottom-responsive-obs 참조.
- **PB-0008 Windows-browser 라이브 실측 — DEFERRED(배포 후)**: ① 그래프 뷰에서 'AI 능동 분석' 진행 패널이 상세 패널 **하단**에 나타나고 분석 시작 시 노드 상세를 위로 밀어내지 않음 ② 브라우저 세로 길이를 줄여도 그래프가 **축소될 뿐 하단이 잘리지 않음**(캔버스·상세·범례 가시) ③ AI 운영 현황 최근 활동에서 '테이블 분석'→`schema.table`, '그래프 노드 분석'→노드 FQN 대상이 라벨 옆·상세에 표시. 배포 후 본 케이스에 Run 기록 append + `alembic_version`=0032_llm_usage_target 확인.

### TASK-20260702-aiops-conv-link-fix '최근 활동' 상세 시스템 sentinel 대화 링크 깨짐 수정 (Minor §12.3, 2026-07-02, audit-nav-ux 후속) — **Environment: Windows-browser (DOM 링크 렌더 — node --check + 배포 후 PB-0008 재검증, visual_verification_scope: always)**
- 대상: 관리콘솔 > 감사 > AI 운영 현황 > 최근 활동 상세 '연결 대화'. 변경: `static/admin.js` `aiOpsActivityRowsHtml`(sentinel 가드) + `static/admin.html`(cache-buster). 백엔드 무변경.
- **구조·구문**: `node --check static/admin.js` PASS.
- **회귀**: `make test` **exit 0**(백엔드 `_query_activity`·엔드포인트 무변경 — feature-0002+0003 전량 그대로 PASS).
- **§18.8**: `[SKIPPED:minor-frontend-guard]` — 3-줄 조건 가드, 선행 audit-nav-ux 패널(REV-20260702T190000 SHIP)이 주변 검증 완료, PB-0008 이 정본. REV-20260702T193000-aiops-conv-link-fix.
- **PB-0008 Windows-browser 라이브 실측 — DEFERRED(배포 후)**: sentinel 활동 행(insight/ask 워커 등) 클릭 → '연결 대화' 가 "시스템·자율 호출 (`__insight_worker__`) — 미귀속" 안내(링크 없음). 실 사용자 대화 활동 행 → '대화 열기' 링크 유지. 배포 후 본 케이스에 Run 기록 append.

### TASK-20260702-audit-nav-ux 감사 카테고리 순서 재구성 + 항목 툴팁 + AI 운영 현황 '최근 활동' 클릭 상세 확장 (Minor §12.3, 2026-07-02) — **Environment: Windows-browser (DOM 상호작용·툴팁·순서 — 코드/단위검증 완료 + 라이브 PB-0008 배포 후 잔여, visual_verification_scope: always)**
- 대상: 관리콘솔 > 감사 그룹 nav 순서·툴팁 + AI 운영 현황 '최근 활동' 인라인 아코디언. 변경: `static/admin.html`(순서 swap·title·cache-buster), `static/admin.js`(aiOpsActivityRowsHtml·토글·renderAiOps 배선), `routers/ai_ops.py`(_query_activity additive), `tests/test_ai_ops.py`.
- **구조·구문**: `python -m py_compile routers/ai_ops.py` PASS · `node --check static/admin.js` PASS.
- **단위(agent 이미지 격리, DB 없이 monkeypatch/fake)**: `make test` **exit 0** (feature-0002 + feature-0003 전량). `test_ai_ops.py` **15/15 passed** — `_query_activity` 확장 SELECT/dict(신규 필드 req_model/resolved_model/prompt_tokens/completion_tokens/run_id/conversation_id) + `served=r[3] or r[2]` 우선순위 + conversation_id 유/무 두 경로 + 기존 cursor keyset·엔드포인트 degrade·권한 403 회귀. ruff PASS.
- **§18.8 적대 패널(subagent, 3-렌즈: 백엔드 correctness/보안·프론트 XSS/UX·테스트 정합)**: **VERDICT SHIP** — BLOCKING/MAJOR/MINOR 0, NIT 3 비차단(REV-20260702T190000-audit-nav-ux, REVIEW.md).
- **PB-0008 Windows-browser 라이브 실측 (Environment: Windows-browser, 2026-07-02, bc2a0fa6 배포 후, 실 Windows Chrome/149 via bin/win-browser.py relay @ 172.26.144.1:9223, https://localhost/admin 로그인 세션)**:
  - **(1) 순서 — PASS**: 감사 그룹 DOM 순서 = 감사 로그 · 보관 대화 · LLM 사용량 · AI 운영 현황(요청과 일치). 새 `admin.js?v=20260702-audit-nav-ux` 로드 확인.
  - **(2) 툴팁 — PASS**: 4개 탭 모두 `title` 상세설명 부착 확인(audits/archives/usage/ai-ops).
  - **(3) 상세 확장 — PASS(부분)**: '최근 활동' 30행 렌더, 첫 행 클릭 → aria-expanded=true·caret ▾·상세 패널 display=block, 필드 8종(시각/작업/모델(edge→gemma4:e2b)/토큰(201/357/558)/추정 비용/지연/요청 ID/연결 대화) 표시.
  - **결함 적발 → 후속 수정**: 첫 행(insight worker `table_insight`)의 '연결 대화' 가 `/?conversation=__insight_worker__`(sentinel) 열 수 없는 링크로 렌더 — 활동 대부분인 시스템·자율 호출에 깨진 링크. → TASK-20260702-aiops-conv-link-fix 로 수정(sentinel 가드), 위 test case 참조.

### TASK-20260702-graph-g6 그래프 뷰 렌더링 엔진 교체 Cytoscape(WebGL)→AntV G6 v5 (Major §12.3, 2026-07-02, feature-0016 cross-cut) — **Environment: Windows-browser (그래프 canvas 렌더·인터랙션 — de-risk=WSL-headless-harness 완료 + 라이브 PB-0008 배포 후 잔여)**
- 대상: 관리콘솔 > 메타데이터 > 그래프 뷰. 변경: admin.js `_metaGraph*` 엔진 전면 재작성(Cytoscape→G6) + admin.html(g6.min.js) + styles.css(오버레이 CSS 제거). 정본: feature-0016 DECISIONS ADR-004 · `../../feature-0016-metadata-graph/g6-migration/BLUEPRINT.md`.
- **구조·구문**: `node --check admin.js` PASS. 제거심볼(cytoscape/fcose/cy/오버레이 3종/Layout/AddElements) 참조 0.
- **§18.8 적대 코드리뷰(subagent, g6.min.js 번들 계약 교차검증)**: **PASS-WITH-FIXES** — CRITICAL/MAJOR 0, MINOR 3건 수정·재검증(REV-20260702T003000, feature-0016 REVIEW.md).
- **de-risk (Environment: WSL-headless-harness, Playwright chromium)** — 포팅된 admin.js 그래프 서브시스템(블록 추출) + **실 admin.html 그래프 마크업** + mock apiFetch(실 응답 shape)로 전 플로우 실증, **에러 0**: roots(스키마 자연정렬 grid·teal 칩·점선/실선 엣지·AI 마커 자동)·제자리 컬럼 펼침(무점프·무재배치)·펼친 테이블 재클릭 무접힘·"−" 접기·검색(유사도 크기)·더블클릭 이웃확장·클러스터 상세·AI 분석/진행패널. 스크린샷: `../../feature-0016-metadata-graph/g6-migration/poc/`. **주의: WSL headless 는 실 Windows 화면검증 대체 아님**(AGENTS.md §15.4.1).
- **배포 후 라이브 PB-0008 잔여(실 Windows 브라우저)**: 정적 자산이 web 이미지에 baked 라 실데이터 시각검증은 **배포(main 병합 후 web 재빌드) 이후**에만 가능. 확인 항목 → ① roots 자연정렬 grid(클러스터 무-shuffle) ② 테이블 클릭=제자리 컬럼 펼침·재클릭 무접힘·"−" 접기 ③ 더블클릭 이웃확장 ④ 스크롤/줌 시 클러스터명·"−"·노드 **동시 갱신**(구버전 오버레이 지연 소멸 확인) ⑤ 테두리 선명(크기별 왜곡 없음) ⑥ 점선(추정)/실선(신뢰) 엣지 ⑦ AI 마커(보라/주황) + 검색 유사도 크기.
- **라이브 PB-0008 실 Windows 브라우저 — PASS (2026-07-02, Environment: Windows-browser)**: graph-g6 무중단 배포(web-a/b `8c45f070`) 후 실 Windows Chrome/149(win-browser relay, `https://localhost/admin` 로그인 세션) 검증. 데이터소스 `mssql-06656002eda6` 실데이터 **236 노드·36 클러스터** → G6 Canvas 렌더 정상, teal 칩·클러스터 자연정렬·점선/실선 엣지, **노드 클릭=제자리 컬럼 펼침**(dt_EventItemWithMonster 12컬럼)·"−" 접기 실화면 동작 확인.
- **후속 UX 개선(graph-g6b)**: 실데이터 관측 문제(세로 과길이·fit 극소) → `_metaG6Build` 클러스터 내 다열 masonry + 가변폭 shelf-packing 으로 해소. WSL-headless-harness(14클러스터 확장 포함) PASS. cache-buster `admin.js?v=20260702-graph-g6b`. 라이브 재확인=graph-g6b 배포 후.
- Pass/Fail: **PASS** (구문·적대 코드리뷰·WSL-headless-harness·라이브 PB-0008 실 Windows 236노드 확인). Runner: AI.

### TASK-20260702-graph-perf-bg 그래프 뷰 테이블 노드 펼침 논블로킹 + 성능 최적화 (Major §12.3, 2026-07-02, feature-0016 cross-cut) — **Environment: Windows-browser (펼침 시 렌더 프리즈 해소는 실 브라우저 페인트 거동 — de-risk=구문/적대패널 + 라이브 PB-0008 배포 후 잔여)**
- 대상: 관리콘솔 > 메타데이터 > 그래프 뷰. 변경: admin.js 논블로킹 펼침 파이프라인·`_opSeq` stale 토큰·O(1) `colsByTable`·`_metaGraphRefreshStates` diff+batch·busy(`_busyKeys`/`_metaStateSig`/`_metaApplyState`)·`_metaG6Build` Pass1/2 + admin_metadata.py `/graph/columns` TTL 캐시 + admin.html cache-buster. 정본: feature-0016 DECISIONS ADR-005 · MODIFY CHG-20260702-graph-perf-bg.
- **구조·구문**: `node --check admin.js` PASS · `py_compile admin_metadata.py` PASS · leftover 디버그 마커(console.log/debugger/TODO) 0.
- **§18.8 적대 검증(AGENT-TEAM, 다단계)**: 3렌즈 병렬 패널(race/index-drift/layout+cache) → **BLOCKING 4건** 적발; 5-agent 재검증 워크플로 → 4건 CLOSED + **신규 BLOCKING 1건(loadRoots reset-vs-reset)** 적발; loadRoots 가드 추가 후 최종 재검증 → **reset-vs-reset 6조합 CLOSED·회귀 없음**. NIT 5건 수용. 상세 REV-20260702T120000 (feature-0016 REVIEW.md).
  - 확인된 BLOCKING 수정: ① reset/search/scope 경로 `_opSeq++`(stale-render 차단) ② 동 race 로 인한 `colsByTable` 포이즌 차단 ③ seq-mismatch busy 소유권 해제(잔류 차단) ④ 폴이 busy 보존(`_metaStateSig`) + `_stateCache` 불변식 ⑤ loadRoots seq 가드(혼합-스코프 그래프 차단).
  - BE 캐시 렌즈 clean: 공유-가변 손상·스코프 누출·권한 우회 없음(캐시-히트는 권한 dependency 후), 실패·빈결과 미캐시, 축출/ TTL 정상.
- **배포 후 라이브 PB-0008 잔여(실 Windows 브라우저)**: 정적 자산 baked → 배포(main 병합·web 재빌드) 후에만 실검증. 확인 항목 → ① **대량 스키마 테이블(수십 컬럼) 선택→펼침 시 렌더 엔진 무프리즈**(과거 dead-frozen 해소) ② 펼침 대기 중 **teal 점선 busy 피드백** 표시 후 자연 소멸 ③ **반복 펼침·재진입 즉시 응답**(introspection TTL 캐시 히트) ④ 펼침 중 스코프 전환/검색 시 **혼합-스코프 그래프 없음**(마지막 요청 화면으로 수렴) ⑤ 대량 그래프에서 AI 마커 폴(2.5s) 시 stutter 없음.
- Pass/Fail: **PASS**(구문·다단계 적대패널). 라이브 프리즈 해소·성능 실검증은 배포 후 §4 Run 에 기록. Runner: AI.

### TASK-20260702-graph-expand-perf 그래프 노드 더블클릭 프리즈 잔존 해소 — refreshStates per-node setElementState (Major §12.3, 2026-07-02, feature-0016 cross-cut) — **Environment: Windows-browser (프리즈 해소는 실 브라우저 렌더/상태 거동 — de-risk=헤드리스 실측+적대패널 + 라이브 PB-0008 배포 후 잔여)**
- 대상: 관리콘솔 > 메타데이터 > 그래프 뷰. 사용자 후속 보고: graph-perf-bg 배포 후에도 `mssql-qa-idc.dk_data_release.Achievement` 더블클릭 시 2~3초 프리즈 잔존. 변경: admin.js `_metaG6Apply`(_stateCache populate)·`_metaGraphRefreshStates`(변화분/rebuild 폴백/rAF coalesce) + admin.html cache-buster. 정본: feature-0016 DECISIONS ADR-006 · MODIFY CHG-20260702-graph-expand-perf.
- **실측 진단(근본원인)**: `_metaGraphRefreshStates` 의 전 노드 `g.setElementState` — G6 v5 건당 ~50ms, **200노드=10,046ms**(헤드리스 harness 실측). 렌더(setData+draw 200노드+127엣지=~200ms)·AGE 이웃(depth=2=135ms, web 컨테이너 서버측 계측)·introspection(analyzed 라 skip) 은 병목 아님(모두 실측 배제).
- **구조·구문**: `node --check admin.js` PASS. setElementState 사용처 = 단일노드(_metaApplyState) + refreshStates(변화분/폴백) 둘로 한정 확인.
- **수정 효과(헤드리스 harness 실측)**: post-rebuild refresh(마커 무변화)=**0ms** · bulk 55마커 변화=**rebuild 82ms** · 구 per-node 200노드=**8,890ms** → ~9s→~0–80ms.
- **§18.8 적대 검증(AGENT-TEAM, 2렌즈)**: ① 정확성/상태유실 — BLOCKING 0(캐시 populate ≡ setData bake, selection 유지, 재귀 없음, per-node 인자 동일). ② 프리즈재발 — 잔존 벌크 루프 0 확인, **폴 tick 이중 refresh** 지적 → rAF coalescing 반영. NIT 3건(combo/schema 캐시·THRESHOLD 200ms·_metaApplyState 단일 50ms) 수용. 상세 REV-20260702T133000 (feature-0016 REVIEW.md).
- **배포 후 라이브 PB-0008 잔여(실 Windows 브라우저)**: 정적 자산 baked → 배포 후에만 실검증. 확인 항목 → ① **대량 스키마 노드(Achievement 등, 형제 246테이블) 더블클릭 시 프리즈 없이 즉시 확장**(과거 2~3초 프리즈 해소) ② AI 능동분석 진행(2.5s 폴) 중 주기적 stutter 없음 ③ 마커(analyzed 보라/running 주황/selected) 정상 표시 유지.
- Pass/Fail: **PASS**(구문·헤드리스 실측·2렌즈 적대패널). 라이브 프리즈 해소 실검증은 배포 후 §4 Run 에 기록. Runner: AI.

### TASK-20260702-graph-dblclick-cam 더블클릭 카메라 순간이동 재배치 해소 — 앵커-중심 애니 팬 (Minor→Major §12.3, 2026-07-02, feature-0016 cross-cut) — **Environment: Windows-browser (카메라 팬 부드러움은 실 브라우저 시각 — de-risk=헤드리스 API 검증+적대리뷰 + 라이브 PB-0008 배포 후 잔여)**
- 대상: 관리콘솔 > 메타데이터 > 그래프 뷰. 사용자 후속(프리즈 해소 후): 테이블 노드 더블클릭 시 카메라 순간이동 재배치 불편. 변경: admin.js `_metaGraphExpand` 카메라 focus 를 즉시→애니메이션(`{duration:420,easing}`) + seq 가드 + admin.html cache-buster. 정본: feature-0016 DECISIONS ADR-008 · MODIFY CHG-20260702-graph-dblclick-cam-anim.
- **구조·구문**: `node --check admin.js` PASS. diff = `_metaGraphExpand` 카메라 블록 1곳(loadRoots/검색/리사이즈 fit·우클릭 중심보기 불변).
- **G6 카메라 애니 API 헤드리스 검증**: graph `animation:false` 에서도 `focusElement(id,{duration,easing})`·`zoomTo(z,{duration})` per-call 애니 스펙 동작(throw 없음)·카메라 실이동·zoom 변경 확인.
- **§18.8 적대 리뷰(SUBAGENT)**: 최초 오편집(우클릭 `_metaGraphFocus`≠더블클릭, 라우팅 오인) + 그 함수 `schemaExpanded.add` 누락→앵커 카드렌더→focusElement throw→fit-to-all 폴백(BLOCKING) 적발 → 진짜 더블클릭 `_metaGraphExpand`(앵커 노드 렌더 보장)로 교정 + focus 함수 원복. 카메라 op=viewport transform(프리즈 무관·ADR-006 무간섭) 확인. REV-20260702T190000 (feature-0016 REVIEW.md).
- **배포 후 라이브 PB-0008 잔여(실 Windows 브라우저)**: ① 대량 스키마 노드 **더블클릭 시 카메라가 앵커로 부드럽게 팬**(순간이동/급격 줌아웃 재배치 없음) ② 앵커가 화면 중앙·판독 배율 유지 ③ 연타 시 카메라 튐 없음.
- Pass/Fail: **PASS**(구문·헤드리스 API 검증·적대리뷰 교정). 라이브 팬 부드러움 실검증은 배포 후 §4 Run 에 기록. Runner: AI.
  - **⚠ 후속 정정(graph-dblclick-cam2)**: 위 "per-call 애니 스펙 동작" 헤드리스 판정은 duration 미측정 오판이었음 — 실제로는 graph `animation:false` 가 per-call 카메라 애니를 무효화해 **no-op**(사용자 재보고). 아래 TASK-20260702-graph-dblclick-cam2 에서 manual rAF tween 으로 근본수정.

### TASK-20260702-graph-dblclick-cam2 더블클릭 카메라 애니 no-op 근본수정 — manual rAF tween (Major §12.3, 2026-07-02, feature-0016 cross-cut) — **Environment: Windows-browser (카메라 팬 부드러움은 실 브라우저 시각 — de-risk=헤드리스 실증+적대6축 + 라이브 PB-0008 배포 후 잔여)**
- 대상: 관리콘솔 > 메타데이터 > 그래프 뷰. 사용자 재보고: graph-dblclick-cam 배포 후에도 더블클릭 시 애니 없이 카메라 순간이동. 변경: admin.js `_metaGraphAnimateFocus` 신규(manual rAF tween) + `_metaGraphExpand` 1줄 교체 + admin.html cache-buster. 정본: feature-0016 DECISIONS ADR-009 · MODIFY CHG-20260702-graph-dblclick-cam2-manual-tween.
- **근본원인 실증(헤드리스)**: graph `animation:false`(레이아웃 셔플 방지)가 per-call 카메라 애니까지 무효화 — 동일 그래프 `animation:false`→`focusElement({duration:400})`=**2ms(즉시)** / `animation:true`→**412ms(애니)**. → §30 focusElement({duration}) no-op 확정.
- **구조·구문**: `node --check admin.js` PASS. diff = `_metaGraphAnimateFocus` 헬퍼 + `_metaGraphExpand` 1줄(다른 카메라 경로 불변).
- **manual tween 헤드리스 실증**: `getElementRenderBounds`+`getViewportByCanvas`+`translateBy` rAF 이징 누적 → 앵커가 뷰포트 정중앙에 **26프레임/434ms 안착**(오차 ≤1e-13px, G6 자체 focus 공식과 동일).
- **§18.8 적대 6축(SUBAGENT)**: 무한루프·중앙정확·seq/동시성·폴백·줌순서·회귀 — **BLOCKING 0**(G6 v5 번들 소스 대조). NIT 2건(420ms 중 2차 더블클릭+fetch실패 카메라 중간잔류 자가치유 / 동시 휠줌 정렬 어긋남) 수용. REV-20260702T230000 (feature-0016 REVIEW.md).
- **배포 후 라이브 PB-0008 잔여(실 Windows 브라우저)**: 더블클릭 시 카메라가 앵커로 **실제 부드럽게 팬**(순간이동/급격 재배치 없음) 육안 확인 — 이번엔 실제 애니 발생 여부가 핵심.
- Pass/Fail: **PASS**(구문·헤드리스 실증·적대6축·번들 소스 대조). 라이브 팬 실검증은 배포 후 §4 Run 에 기록. Runner: AI.
  - **후속(graph-dblclick-latency)**: 라이브서 팬 동작 확인됨. 잔여 = 팬 시작 ~350ms 텀 → 아래 TASK-20260703 에서 즉시 시작 + 적응형 follow 로 개선.

### TASK-20260703-graph-dblclick-latency 더블클릭 카메라 팬 반응 지연(~350ms 텀) 제거 (Major §12.3, 2026-07-03, feature-0016 cross-cut) — **Environment: Windows-browser (반응성은 실 브라우저 체감 — de-risk=헤드리스 실증+적대7축 + 라이브 PB-0008 배포 후 잔여)**
- 대상: 관리콘솔 > 메타데이터 > 그래프 뷰. 사용자 후속(cam2 배포 후): 팬은 부드러우나 더블클릭 직후가 아닌 ~350ms 텀 뒤 시작(답답). 변경: admin.js `_metaGraphAnimateFocus` 적응형 follow 재작성 + `_metaGraphExpand` 팬 fetch 전 fire-and-forget 시작 + admin.html cache-buster. 정본: feature-0016 DECISIONS ADR-011 · MODIFY CHG-20260703-graph-dblclick-latency · TASK §34(병렬 재번호 §13.1).
- **진단**: 팬이 파이프라인 맨 끝(fetch~135ms + setData/draw~200ms 뒤)에서 시작 → ~350ms 텀. 앵커는 이미 렌더인데 대기.
- **구조·구문**: `node --check admin.js` PASS. diff = `_metaGraphAnimateFocus` 재작성 + `_metaGraphExpand` 팬 호출 위치 이동(2 hunk, 다른 카메라 경로 불변).
- **헤드리스 실증**: fire-and-forget 즉시 시작 + 중간 setData 로 앵커 이동(offset -500) → **24프레임에 최종 중앙 [399,250]≈[400,250] 수렴**(적응형 follow 가 이동 타겟 추종).
- **§18.8 적대 7축(SUBAGENT)**: 종료보장·fire-and-forget 동시성·이동수렴·fetch실패/seq·미렌더/폴백·회귀·K/임계 — **BLOCKING 0**. **MEDIUM(missStreak 프레임카운트 조기포기 — 저사양 rAF 탈동조로 팬 조기중단 위험)** 적발→제거(MAXMS 단일상한). NIT(API 폴백·W/H 스테일)→반영. REV-20260703T003000 (feature-0016 REVIEW.md).
- **배포 후 라이브 PB-0008 잔여(실 Windows 브라우저)**: 더블클릭 시 카메라가 **텀 없이 즉시** 앵커로 부드럽게 팬 + rebuild 로 노드 위치 정해진 뒤에도 매끄럽게 최종 중앙 수렴 육안 확인.
- Pass/Fail: **PASS**(구문·헤드리스 실증·적대7축). 라이브 반응성 실검증은 배포 후 §4 Run 에 기록. Runner: AI.

### TASK-20260702-metadata-perm-hier 메타데이터(지식베이스) 권한 종속관계 정합화 (Major §12.3, 2026-07-02) — **Environment: Windows-browser (권한 그리드는 DOM — 배포 후 라이브 검증, 캔버스 무관)**
- 대상: 관리 콘솔 역할/계정 권한 그리드에서 메타데이터(kb 그룹)가 다른 관리 그룹과 동일한 "그룹 게이트(묶음)→세부" 2단 계층으로 표시. 묶음 `kb.ingest.manual`("메타데이터 관리 전체 묶음")이 depth-0 그룹 루트, 세부 5개 metadata.*가 depth-1 자식.
- 정적 검증(pre-commit): `node --check admin.js` PASS · `test_permission_dependency_map.py` 18개 PASS(신규 t5 계층 pin[metadata.*→kb.ingest.manual→console.access, depth manual=0·metadata.*=1] + t6 도달성[게이트 OFF 시 metadata hidden 이나 그룹 비은닉] + 기존 V1~V7 disclosure 무회귀) · §18.8 SUBAGENT 패널 PASS(BLOCKING 0).
- **PB-0008 Windows-browser: 배포 후 수행(사유 명시)** — 본 변경은 **표시 계층 재구성**이라 배포 전(현재 라이브 654c05ff)엔 관측 불가하고 새 admin.js 서빙 이후에만 그리드 계층이 바뀐다 → **배포 후** 라이브 검증. 권한 그리드는 **DOM 요소**(그래프 canvas/WebGL 아님)라 PB-0008 자동화 회귀(Chrome UtilityScript)와 무관 — headless/실 브라우저 모두 신뢰 검증 가능. 배포 후 확인 항목: (1) 역할 편집 그리드 "지식베이스(KB) 검수" 그룹에서 묶음이 루트·metadata 5개가 그 아래 들여쓰기(2단 계층, 다른 그룹과 동형) (2) 묶음 미체크 시 세부 접힘 + "세부 권한 N개 더 보기" 로 노출·개별 부여 가능(B안 보존) (3) 묶음 체크 시 세부 5개 노출. Runner: AI(배포 후 /browse DOM 검증) + 사용자 실화면 확인 권장.
- Pass/Fail: 정적 PASS. 라이브 계층 검증은 배포 후 §4 Run 에 기록.

### TASK-20260702-graph-panel-perms 그래프 뷰 UX 3건 + 메타데이터 탭 권한 세분화(B안) (Major+Critical §12.3, 2026-07-02) — **Environment: Windows-browser (그래프 canvas 인터랙션 — 배포 후 사용자 실화면 확인, 자동화 회귀 이력)**
- 대상: (Task1) 상세 패널 드래그 리사이즈 (Task2) 확장 테이블 접기 버튼(박스 우측하단 HTML 오버레이) (Task3) 첫 컬럼명 미표시 버그(text-margin-y -13 + halo) (Task4) 메타데이터 탭 권한 세분화(kb.ingest.manual→5 세부 권한, 비파괴 함의).
- **구조/단위 (PASS)**: `node --check admin.js` PASS · `py_compile app.py routers/admin_metadata.py` PASS. 신규 `tests/test_metadata_perm_split.py` **9/9 PASS**(R1 카탈로그·R2 admin seed/least-priv·R3 함의(묶음→5권한)·R3b override-allow 함의·R4 개별 DENY 우선·R5 granular 격리·R6 umbrella 유지·R7 서버 서브탭 맵·R8 프론트 맵). `test_metadata_ai_autocomplete.py`(fixture 세부권한 갱신)·`test_metadata_phase2.py`·`test_metadata_glossary_enum.py`·`test_permission_dependency_map.py` 무회귀 PASS.
- **route parity 주의(정직)**: `test_route_parity_p5b`(192→193) 는 **origin/main 344a5a80 기존 결함**(#520/#522 신규 route 의 golden 미갱신). 본 변경은 route 무추가(`git diff main` 에 @router/@app 데코 추가 0)라 무관 — feature-0012(P5b) 소관 golden 갱신 대상.
- **적대 검증 패널(§18.8, 2 렌즈)**: authz(인가 상승·접근 회귀·enforcement 누락·FE/BE 불일치·부트스트랩 게이트·DENY 우회) + 그래프 프론트(리사이즈 clamp 경계·접기 버튼 이벤트/좌표·컬럼 수정 겹침·#522 병합 정합·런타임 에러). REV-20260702T120000-graph-panel-perms.
- **권한 세분화(Task4) 검증 성격**: 백엔드 인가 로직은 렌더 표면이 아니라 **단위테스트가 정본**(함의·enforcement·granular 격리 커버). 프론트 서브탭 가시성은 비파괴(worst-case 탭 표시/숨김)·함의로 기존 사용자 무손실.
- **PB-0008 Windows-browser 라이브(배포 후 사용자 실화면 확인 권장)**: 관리콘솔 그래프 뷰 → (1) 캔버스↔패널 사이 바 드래그로 패널 폭 조절·새로고침 후 유지 (2) 테이블 더블클릭 확장 후 박스 우측하단 "−" 버튼 클릭 → 컬럼 접힘, 재더블클릭 재펼침 (3) 확장 시 **첫(최상단) 컬럼명이 타이틀에 안 가려지고 표시** (4) 세부 권한만 가진 역할로 로그인 시 해당 서브탭만 노출·타 서브탭 403. 그래프 canvas 인터랙션 자동화(win-browser eval)는 PB-0008 회귀 이력(Chrome UtilityScript)이라 라이브 육안 확인이 유일 신뢰.
- Pass/Fail: PARTIAL(구조·단위 9/9·적대 패널 PASS / 그래프 인터랙션 라이브 = 배포 후 사용자 재확인). Runner: AI.

### TASK-20260701T220000-graph-perf2 컬럼 blob·프레임 거침·느린 줌 수정 (Major §12.3, 2026-07-01) — **Environment: Windows-browser (실 GPU de-risk 완료 + 라이브 PB-0008 배포 후 잔여)**
- 대상: 컬럼 정렬 fcose 제약 제거→layoutstop 결정론 배치(`_metaGraphPlaceColumns`), 세로 seed, wheelSensitivity 제거, PITCH18/nodeSep220. 프론트 전용·비파괴.
- 구조/단위: `node --check` PASS(admin.js). 잔존 제약 참조 0. 백엔드/API 변경 0. 캐시버스터 graph-perf2.
- 적대 검증: 진단 워크플로(5에이전트, verdict go-with-fixes) + §18.8 적대 subagent(admin.js + vendored fcose 실측) → **BLOCKING 0·MAJOR 0·MINOR 1(박스겹침)·NIT 3**. 컬럼정렬 공백경로 없음, 제약 키 제거가 tile-off 취약성 오히려 제거. REV-20260701T220000 [SUBAGENT: PASS].
- **Environment: Windows-browser (de-risk 실측)** — 실 Windows Chrome/149 via `bin/win-browser.py` relay(`bridge_mode: relay`, endpoint `http://172.26.144.1:9223`, 실 GPU). WSL headless 아님.
  - **시나리오**: cytoscape 3.34.0 WebGL + fcose 2.2.0 + 스키마 compound > AchievementReward(17컬럼) ERD 카드 + UserAchievementReward 6이웃(각 3컬럼) + REFERENCES. **본 cycle 의 결정론 컬럼 배치·세로 seed·nodeSep220 로직을 그대로 재현**한 최소 페이지.
  - **Pass — blob 해소·겹침 해소 실측**: AchievementReward 17컬럼 **x-spread = 0.0px**(모두 동일 x = 완벽 세로 스택, blob 소멸). PITCH 22→18 + nodeSeparation 150→220 적용 시 **Table 박스 겹침쌍 2→0/7**. 스크린샷 `scratchpad/webgl-test/render3.png`: 17컬럼 세로 스택(UniqueID→NeedLevel 판독) + 6이웃 박스 무겹침 분산 + REFERENCES bezier.
- **PB-0008 성격(정직)**: 실 FPS(거침 완화)는 스크린샷으로 측정 불가 → **사용자 실 하드웨어 재확인이 유일 효과 검증**. 대규모(141테이블) 박스겹침·휠 줌 체감도 배포 후 사용자 확인.
- **배포 후 라이브 잔여**: 관리콘솔 그래프 뷰 → (1) 더블클릭 확장 프레임 거침 완화 (3) 17컬럼 테이블 세로 스택(blob 없음) (4) 휠 줌 속도 + 대규모 박스겹침/over-zoom 없음 + 사용자 육안.
- Pass/Fail: PARTIAL(구조·단위·워크플로+적대 패널·de-risk 실측 PASS / 라이브 = 사용자 재확인). Runner: AI.

### TASK-20260701T210000-graph-webgl 그래프 렌더러 canvas-2D→WebGL 전환 (Major §12.3, 2026-07-01) — **Environment: Windows-browser (실 GPU de-risk 완료 + 라이브 PB-0008 배포 후 잔여)**
- 대상: cytoscape 3.30.2→3.34.0 + `renderer:{name:"canvas",webgl:_webglOk}` + 엣지 bezier·색/투명도 재설계 + anim-hide 제거. 프론트 전용·비파괴.
- 구조/단위: `node --check` PASS(admin.js). vendored cytoscape 3.34.0 정품(Cytoscape Consortium 헤더, node --check OK). 백엔드/스키마/API 변경 0.
- **Environment: Windows-browser (de-risk 실측, PB-0008 준거)** — 실 Windows Chrome/149 via `bin/win-browser.py` 무권한 relay(`bridge_mode: relay`, endpoint `http://172.26.144.1:9223`, 실 GPU). WSL headless(SwiftShader) 아닌 실 GPU.
  - **시나리오**: cytoscape 3.34.0 + `webgl:true` + **2단 compound**(스키마 dbo > Table tblUser/tblOrder ERD카드 > 컬럼 dots) + 라벨 + REFERENCES bezier 엣지(trusted/candidate) 최소 페이지 렌더.
  - **Pass — WebGL 활성·compound 정상**: `webglContextDetected=true`(getContext webgl2/webgl 성공), renderer webglOpt=true, renderer_hint=webgl, canvas#=4, nodes=8 parents=3 edges=2. 스크린샷(`scratchpad/webgl-test/render.png`): **2단 compound 박스(round-rectangle teal 보더)·노드 라벨·bezier 엣지+화살표+라벨 전부 정상 렌더**. make-or-break(compound WebGL 지원) 통과.
- 적대 검증 패널(§18.8 subagent): BLOCKING 0·MAJOR 1(엣지 색-비의존 구분→candidate 가시성 상향 수정)·NIT 3. anim-hide 제거 완전성·폴백·노드보더·스코프·평행엣지 dedup 전부 코드 방어 확인. REV-20260701T210000 [SUBAGENT: PASS].
- **PB-0008 성격(정직)**: 실 FPS 개선은 스크린샷 기반 PB-0008 로 측정 불가 → **사용자 실 하드웨어 재측정이 유일 효과 검증**. PB-0008 가 확인 가능한 것은 WebGL 활성·렌더 정합(compound·라벨·엣지·후보/신뢰 구분·ai 마커)·애니 부드러움·대규모 이웃 sprite 안정성.
- **배포 후 라이브 PB-0008 잔여(실 Windows 브라우저)**: 관리콘솔 그래프 뷰 → ① WebGL 활성 확인 ② 검색·확장 애니 중 **라벨 항상 표시**(사라짐 없음) ③ compound ERD 박스·컬럼·엣지 렌더 정합 ④ candidate(연앰버 얇음)/trusted(진갈 굵음) 구분 가시성 ⑤ 대규모 이웃(수백 노드) 렌더 안정 + 사용자 육안 FPS·라벨유지 재확인.
- Pass/Fail: PARTIAL(구조·단위·de-risk 실측·적대 패널 PASS / 라이브 PB-0008 렌더정합 = 배포 후 잔여, FPS 효과 = 사용자 재측정). Runner: AI.

### TASK-20260701T170000-graphux-camfps 그래프 카메라 애니 프레임레이트 최적화(layoutstop 지연 복원) (Minor §12.3, 2026-07-01, resume 인계) — **Environment: Windows-browser (라이브 PB-0008 배포 후 잔여)**
- 대상: `_metaGraphLayout` layoutstop — 라벨/엣지 숨김 해제를 카메라 fit 애니 complete 후로 지연 + 세대가드 + 무조건 복원. 프론트 전용·비파괴(JS 로직).
- 구조/단위: `node --check` PASS(admin.js). 백엔드/스키마/RBAC/API 변경 0. 캐시버스터 graphux-camfps.
- 적대 검증 패널(§18.8 subagent, 2라운드): cytoscape/fcose 번들 내부(`stop()`→`layoutstop` 동기 발화·fcose run() 완전 동기·cy 비파괴) 실측 기반 10+ 경로. 1차 BLOCKING 2(fcose 예외→폴백 복원부재 영구숨김)+MAJOR 3 발견 → hardened 재구현 → 재검증 **잔여 BLOCKING 0**. 핵심 불변식(비동기 복원=gen-gated 뿐, 무조건 복원=전부 동기) 확증 → 어떤 연타·예외·폴백·스코프전환에서도 라벨/엣지 영구숨김·깜빡임 재현 불가. REV-20260701T170000 [SUBAGENT: PASS].
- **PB-0008 Windows-browser 성격 (정직)**: 본 변경의 목표는 **애니 FPS 개선**인데, 실 FPS 는 PB-0008(스크린샷 기반)로 측정 불가하고 **사용자 실 하드웨어 재측정이 유일한 효과 검증**이다(headless/WSL 실 GPU 프레임 미측정 = 원 세션이 막힌 근본 이유). PB-0008 가 확인 가능한 것은 **렌더 정합**(라벨/엣지가 애니 후 정상 복원·영구숨김 회귀 없음·확장 동작).
- **배포 후 라이브 PB-0008 잔여(실 Windows 브라우저, 브리지 relay 9223 available)**: ① 관리콘솔 > 메타데이터 > 그래프 뷰 로드 → 검색(초기 스프레드 애니) 후 **라벨·엣지 정상 표시**(영구숨김 없음) ② 노드 더블클릭 확장(카메라 fit 애니) → 애니 중 라벨/엣지 숨김·**정착 후 복원** ③ **연타(빠른 더블클릭 2~3회)** 후 최종 상태에서 라벨/엣지 정상(영구숨김 회귀 없음) ④ 데이터소스 전환/리셋 후 정상 렌더. + 사용자 애니 FPS 재측정(DevTools).
- Pass/Fail: PARTIAL(구조·단위·2라운드 적대 패널 PASS / 라이브 PB-0008 렌더정합 = 배포 후 잔여, FPS 효과 = 사용자 재측정). Runner: AI.

### TASK-20260629T181648-point-scroll-easeoutexpo 공유 뷰 가이드 뱃지(point rail) + 클릭 스크롤 단축·EaseOutExpo (Minor §12.3, 2026-06-29) — **PB-0008 Windows-browser DEFERRED(배포 후)**
- 구조/단위: `node --check` PASS(app.js·share.js). CSS 추가만(share.css), 백엔드/스키마/RBAC 0.
- 적대 검증 패널(frontend 7-lens: 좌표계·EaseOutExpo 수식·메인 회귀·공유 엣지·anonymous XSS·성능/ResizeObserver 루프·a11y) → **VERDICT SHIP**(BLOCKER 0·MAJOR 0). EaseOutExpo `1-2^(-10t)` 수치검증 f(0)=0·f(1)=1·단조·보간 from→to 정확. ResizeObserver 자기-트리거 루프 부재(fixed rail↔observed messages 레이아웃 분리). title/aria XSS 무첨가(DOM API). MINOR 2(ResizeObserver 폴백·focus-visible)→ focus-visible 흡수, 나머지 follow-up. REV-20260629T181648-point-scroll-easeoutexpo.
- **배포 후 PB-0008 잔여(실 Windows 브라우저)**: ① 메인 작업화면 — rail dot 클릭 시 대상 메시지로 **체감상 더 빠른**(280ms) EaseOutExpo 스크롤(기존 native smooth 대비 단축) ② 공유 페이지(`/share/{token}`, 2개+ 메시지) — 우측에 가이드 뱃지(point rail) 표시·각 dot 이 메시지 구간 비율 위치·클릭 시 EaseOutExpo window 스크롤·스크롤 시 현재 구간 dot `is-active` ③ 메시지 1개/0개 시 rail 미표시 ④ ≤720px 모바일 숨김 ⑤ prefers-reduced-motion 시 즉시 점프.
- Pass/Fail: PARTIAL(단위·적대 패널 PASS, 라이브 PB-0008 배포 후 잔여 — 표현계층 화면 정본).

### TASK-20260629-metadata-bs-flexclip 메타데이터 부트스트랩 결과 패널 flex-shrink 클리핑 수정 (Minor §12.3, 2026-06-29)
- 구조: `node`/`py_compile` 대상 JS·Python 변경 0 (CSS+HTML cache-buster 전용). CSS brace 균형 `{`1616/`}`1616.
- **Environment: Windows-browser** (실제 Windows Chrome/149.0.7827.200 via `bin/win-browser.py` 무권한 relay, `bridge_mode: relay`, endpoint `http://172.26.144.1:9223`, https://localhost:18080, self-signed ignore). WSL headless 아닌 실제 Windows 화면. Runner: AI. Evidence: `artifacts/shared/win-browser-shots-pb0008-tabledesc/` (10_mssql_account_skeleton·11_viewport·20_fix_flexshrink_applied·30_ai_suggest_filled).
  - **시나리오**: 로그인(세션 유효) → 관리 콘솔 > 메타데이터 > 테이블 설명 서브탭 → 스키마 골격 가져오기 → DS=`mssql-qa-idc`(129 실 DB, tempdb/시스템 DB 0) → DB=`Account` → 골격 17 테이블·132 컬럼.
  - **Pass — 원본 작업 검증**: ① MSSQL 실테이블명 정상(`tblAccount`·`tblAccountBlockLog`·`tblAccountChannel`… tempdb #temp 0). ② 엔진별 라벨 분기(`mssql-dk-dev`/`mssql-qa-idc`='데이터베이스', `mysql-local`='스키마'). ③ 테이블 설명 AI 자동완성: `tblAccount` 단건 suggest → grounding 된 한국어 설명 자동 생성(권한 레벨·차단 상태·접속 서버 등 컬럼 반영). `.admin-meta-bootstrap-result` maxHeight=none(metadata-table-desc-fix 반영).
  - **버그 적발(이 cycle 의 수정 대상)**: 골격 결과 패널이 펼침/접힘 무관 ~1행만 보이고 나머지 16 테이블 미표시 + pane 스크롤 미발생(`#metadataBootstrap` clientH=88·scrollH=1769·overflow:hidden, 부모 pane scrollH==clientH==684). 근본=flex 자식 overflow:hidden→min-height:auto 0→flex-shrink 무한 압축.
  - **Pass — fix 검증**: `.admin-meta-bootstrap { flex-shrink:0 }` 라이브 주입 시 `#metadataBootstrap` height 90→1771, **부모 pane scrollHeight 684→2364(스크롤 발생)**, 17 테이블+설명 입력란 전부 표시·우측 스크롤바 노출(스크린샷 20).
  - **배포본 재검증(PASS)**: main `54dbfe3` ff-merge → `docker compose build web` + `up -d --no-deps web`(repo-web-1 Up healthy, /healthz mysql_ok·pg_ok true). 서빙 `styles.css?v=20260629-metadata-bs-flexclip`(admin/index 양쪽) + baked styles.css 에 `.admin-meta-bootstrap{flex-shrink:0}`. 브라우저 하드 리로드(주입 없이 실 CSS) 후 동일 시나리오 재현: `.admin-meta-bootstrap` computed `flex-shrink=0`, **부모 pane scrollHeight 684→2364(펼침)/1531(접힘) > clientHeight 684 = 스크롤 발생**, 17 테이블 전부 표시·우측 스크롤바 노출(스크린샷 40_deployed_fix_verify). 클리핑 해소 확정.
  - **Notes**: mssql_local 의 '스키마 조회 실패'는 로컬 MSSQL 미가동(환경), UI 버그 아님. AI 자동완성 단건 1회 실행은 폼 prefill 만(미저장 — DB 비오염).

### TASK-0309 제품 프롬프트 무인 자동완성 (Major §12.3, 2026-06-25)
- TEST: `tests/test_auto_product_prompt.py` 12/12 PASS (DB 없이 fake/monkeypatch, `make test` 격리).
  T1 분석률<임계 무생성 · T2 >=임계+미입력 1회 생성·재sweep scanned 0 · **T3 insight reset 후 재상승 무재생성(1회성 핵심)** · T4 프롬프트 존재 skip · T5 pct None skip · T6 pct==95.0 경계 · T7 다제품 적격만 · T8 인증 게이트 위임 · **T9 명시 tx(autocommit False→복원)+commit** · **T10 마커 UPDATE 실패 rollback→미저장·마커 NULL(B1)** · **T11 LLM 실패 backoff(M1)** · **T12 cycle 생성 상한(M2)**.
- 회귀: `test_insight_coverage.py` 5/5 무회귀 + `py_compile app.py` + ruff PASS.
- **PB-0008 Windows-browser: N/A(사유 명시)** — 본 변경은 백엔드 백그라운드 sweep + MySQL 컬럼(`AutoPromptGeneratedAt`)만, HTML/CSS/JS 등 **UI 표면 변경 0**. 화면 렌더 검증 대상 없음 → CHECK#13 WARN-only 해당, 실 브라우저 검증 불요. 배포 후 라이브 확인은 "95% 제품 1회 자동완성 + insight reset 후 무재생성"(서버 로그/DB) 로 수행.

### 구조/문법 검증
- TEST-0001: `python3 -m py_compile unit/feature-0003-agent-web-ui/src/app.py`
- TEST-0002: `node --check unit/feature-0003-agent-web-ui/src/static/app.js`
- TEST-0003: `node --check unit/feature-0003-agent-web-ui/src/static/admin.js`

### 계정/RBAC API 검증
- TEST-0004: `GET /api/session` 비인증 시 `authenticated=false`
- TEST-0005: bootstrap admin 로그인 후 `GET /api/auth/me`, `GET /api/admin/accounts`, `GET /api/admin/roles`, `GET /api/admin/permissions` 정상 응답
- TEST-0006: 임시 기본 signup role 생성 후 신규 회원가입 계정에 해당 role이 자동 부여
- TEST-0007: `console.access` 단독 계정은 `/api/admin/permissions`만 조회 가능하고 `/api/admin/accounts`, `/api/admin/roles`는 403
- TEST-0008: 계정 role assignment + override allow/deny 후 최종 permission map이 기대값과 일치
- TEST-0009: `conversation.list.any`, `conversation.read.any` 허용 계정이 타 계정 대화를 조회 가능
- TEST-0010: 타 계정 대화에 대해 `conversation.ask`는 owner mismatch로 차단
- TEST-0011: `conversation.rename.any` override 후 타 계정 대화 제목 변경 가능
- TEST-0012: `/api/clear_memory`가 410을 반환
- TEST-0013: 마지막 관리 가능 계정/role 보호 규칙이 빈 permission set 변경을 차단
- TEST-0014: soft delete 후 로그인 차단 및 기존 세션 폐기
- TEST-0015: `PATCH /api/auth/me`로 현재 비밀번호 검증 후 새 비밀번호 변경 가능
- TEST-0016: 외부 Local LLM gateway 연결 시 `GET /api/session.local_llm_enabled=true`
- TEST-0017: bootstrap admin 세션에서 외부 provider 연결 상태로 `POST /api/ask` + `model=auto`가 API 키 없이 성공
- TEST-0018: 외부 Local LLM provider 미기동 시 `POST /api/ask` + `model=auto`가 503으로 제한
- TEST-0019: 휴리스틱 금지 grep으로 `ACCOUNT_ROLE_*`, `is_admin`, `is_pending`, `_normalize_role(...)`, legacy `can_*` 권한 판정 경로 부재 확인

### 타 계정 대화 검색·필터 (TASK-0072, REQ-20260518-0010, Critical §12.3)
- TEST-0072-1 (S1 .own no leak): `.own` only operator 토큰 + `q=<상대 키워드>` → 응답 items 의 owner_account_id 가 모두 operator 자신. SQL composition order sub-spec 1 검증.
- TEST-0072-2 (S2 .any includes others): admin 토큰 (.any) + 동일 q → cross-account 매칭 포함. `next_cursor` / `has_any` / `search_mode` 응답 필드 존재.
- TEST-0072-3 (S3 byte-equal owner_id): `.own` operator + `owner_id=<other_real>` 와 `owner_id=99999999` 의 응답이 byte-equal. 404/403 metadata leak 차단.
- TEST-0072-4 (S4 cursor disjoint): limit=5 페이지 1 + cursor 페이지 2 의 id set intersection = ∅. SQL ORDER BY 단일화 정합 검증.
- TEST-0072-5 (S5 invalid q → 400): `q="ab"` / `q="  "` / `q="%%"` 모두 400 응답. raw-len < 3 + post-escape 0 char 차단.
- TEST-0072-6 (S6 rate limit 429): 동일 토큰으로 body-search 11 회 호출 → 11 번째 429. per-account 10 req/min in-process token bucket 검증.
- TEST-0072-7 (DDL idempotent): `_ensure_web_account_activity_schema` 를 두 번 호출해도 에러 없음. `CREATE TABLE IF NOT EXISTS` 패턴.
- TEST-0072-8 (audit log INSERT): admin 토큰 + body-search 1 회 → `SELECT COUNT(*) FROM WebAccountActivity WHERE Action='conversation.search.body' AND AccountId=<admin_id>` ≥ 1. QueryHash 가 SHA-256 hex (64 char) 형식.
- TEST-0072-9 (frontend Cmd+K): browser 환경에서 Cmd/Ctrl+K → `#searchModalOverlay` 가 `hidden=false`. Esc / backdrop click / close 버튼 모두 close. focus 가 input 으로 이동.
- TEST-0072-10 (snippet chip .any only): `.own` operator 로그인 시 `#searchFacetSnippet` / `#searchFacetOwner` 둘 다 `hidden=true`. admin 로그인 시 두 chip 모두 visible + 기본 `aria-pressed="false"`.

### 실행 명령
```bash
# 구조 검증 (Phase A 검증)
python3 -m py_compile repo/unit/feature-0003-agent-web-ui/src/app.py
python3 -m py_compile repo/unit/feature-0003-agent-web-ui/tests/test_search_rbac.py
node --check repo/unit/feature-0003-agent-web-ui/src/static/app.js

# HTTP smoke (Phase E — 컨테이너 가동 + 비밀번호 필요)
python3 repo/unit/feature-0003-agent-web-ui/tests/test_search_rbac.py \
    --base-url http://localhost:18080 \
    --admin-user admin --admin-pass <pw> \
    --operator-user operator --operator-pass <pw>
```

### 브라우저 기반 UI 검증
- TEST-0020: 로그인 화면이 계정/권한 안내 중심 2패널 구조로 렌더링된다
- TEST-0021: 로그인 후 메인 화면이 App-Shell 구조로 렌더링되고 외부 스크롤이 발생하지 않는다
- TEST-0022: 관리자 버튼 클릭 시 `/admin` 화면으로 이동하고 Accounts / Roles 2영역이 렌더링된다
- TEST-0023: 관리자 콘솔에서 role 생성/수정/기본 signup role 전환이 가능하다
- TEST-0024: 브라우저 회원가입 후 기본 signup role이 프로필 role 라벨에 반영된다
- TEST-0025: 관리자 콘솔에서 계정 role을 다른 role로 바꾼 뒤 다시 복원할 수 있다
- TEST-0026: own conversation에서 제목 변경/삭제 버튼이 노출된다
- TEST-0027: 타 계정 대화는 `read/list.any`만 있을 때 버튼이 숨겨지고, `rename/delete.any` 허용 후 버튼이 노출된다
- TEST-0028: soft delete 후 `/admin` deleted 필터에 계정이 보이고, 삭제된 계정 로그인은 차단된다
- TEST-0029: 삭제된 role이 관리자 역할 목록에서 제거된다
- TEST-0030: bootstrap admin 브라우저 세션에서 `model=auto`, 질문 `현재 데이터베이스 목록을 보여줘` 가 실제 화면 기준 `60초 이내` 완료되고 완료 화면이 스크린샷으로 남는다

### TASK-0061 GOAL.md 8 항목 합본 cycle (REQ-20260515-0003 ~ -0010)

**Phase 1+2 (답변 버블 실시간 + 신규 대화 첫 polling)**:
- TEST-0080: `state.pendingBubble` 강제 set + `renderMessages()` 호출 시 `#pendingAssistantBubble` element 가 messageLogEl 의 마지막 자식으로 추가된다. spinner / elapsed timer / status badge / latest step / 누적 step `<details>` 5 영역이 정상.
- TEST-0081: `applyProgressPayload({run_id, steps, step_count, display_status, raw_status, is_stale})` 호출 시 `state.pendingBubble.steps` 가 incremental 로 누적되고, 동일 step (step_index+created_at 시그니처) 은 중복 추가되지 않는다.
- TEST-0082: elapsed timer 가 1초 간격 tick 으로 `#pendingBubbleElapsed.textContent` 를 갱신한다 (`Xs / Xm Ys` 형식).
- TEST-0083: `sendPrompt()` lazy-create 분기 시 `state.activeConversationId` 비어 있어도 pending bubble 이 즉시 표시되고, `/api/ask` 응답으로 cid 발급되면 `startProgressPolling({reset:true})` 가 호출되어 polling 이 시작된다.
- TEST-0084: `/api/ask` 실패 (lazy-create) 시 pending bubble 이 `.is-error` 로 전환되고 error 메시지가 노출된다. attach/resume 다이얼로그는 활성화되지 않는다 (cid 발급 여부 불확실).

**Phase 3 (stale processing 만료 감지)**:
- TEST-0085: `WEB_PROGRESS_STALE_TIMEOUT_SECONDS=1200` env 가 컨테이너에 적용된다 (`docker exec web env | grep STALE`).
- TEST-0086: `last_status='processing'` + `last_status_at` 가 만료 시간 초과인 KV 를 조작 후 `/api/progress` 가 `status=stale_error`, `is_stale=true`, `raw_status=processing` 반환한다.
- TEST-0087: `/api/ask_status` / `/api/ask_result` 도 stale 일 때 `is_processing=false` + `is_stale=true` 반환 — attach long-poll 가 즉시 terminal 처리한다.
- TEST-0088: conversation list (`/api/conversations`) 응답에 `display_status` / `raw_status` / `is_stale` 필드가 포함된다.
- TEST-0089: frontend `renderConversationList()` 의 `.conv-dot.is-stale-error` 가 stale 대화에 적용되고 tooltip "작업이 중단된 것으로 보입니다 — 마지막 활동: ..." 이 노출된다.

**Phase 4 (Point rail)**:
- TEST-0090: `#messagePointRail` 컨테이너가 chat pane 우측에 존재하고, 메시지 ≥ 2 일 때 `.hidden` 이 제거된다.
- TEST-0091: `renderMessagePointRail()` 가 메시지 1 개당 1 개의 `.message-point-dot` 를 생성한다 (`is-user` / `is-assistant` 토큰 분기).
- TEST-0092: scroll 이벤트 시 `highlightActivePoint()` 가 viewport 중앙에 가장 가까운 메시지의 dot 에 `.is-active` 를 부여한다.
- TEST-0093: dot 클릭 시 해당 메시지로 smooth scroll 한다 (`scrollIntoView({behavior:'smooth', block:'center'})`).
- TEST-0094: `max-width: 720px` viewport 에서 rail 이 `display: none` 으로 처리된다.

**Phase 5 (캘린더/시각 이동)**:
- TEST-0095: `/api/history_dates?conversation_id=...` 가 `AgentMemoryMessages` 테이블 기준으로 `{dates: {YYYY-MM-DD: [HH:MM, ...]}, first, last}` 응답한다.
- TEST-0096: chat header 의 `#historyCalendarBtn` 클릭 시 `#historyCalendarPopover` 가 노출 (`.hidden` 제거).
- TEST-0097: popover 의 월간 grid 에서 메시지가 있는 날만 `.has-messages` class 가 부여되고, 메시지 없는 날은 `disabled`.
- TEST-0098: 날짜 선택 → 그 날의 첫 시각으로 자동 jump. 시각 선택 → `/api/history_anchor?at=YYYY-MM-DD HH:MM:00` 호출 후 반환된 message_id 의 element 로 smooth scroll + `.is-anchor-highlight` 1.5초 강조.
- TEST-0099: empty state — 메시지 0 개일 때 `#historyCalendarBtn` 이 hidden, 날짜 미선택 시 "메시지가 있는 날짜를 선택하세요" 안내.

**Phase 6 (관리자 비밀번호 초기화, Critical)**:
- TEST-0100: `WebAccounts.MustChangePassword` 컬럼이 존재하고 default 0 (`DESCRIBE WebAccounts` 또는 `SHOW COLUMNS LIKE 'MustChangePassword'`).
- TEST-0101: `POST /api/admin/accounts/{id}/password-reset` 권한: `console.access` + `console.manage` + `account.update` AND `actor.id != account_id`. self-reset (`actor.id == account_id`) 은 400 반환.
- TEST-0102: 권한 없는 계정의 호출은 403 반환.
- TEST-0103: 응답에 `temporary_password` 가 1회 포함되고, `WebAccounts.MustChangePassword=1` + 대상 계정의 `WebAuthSessions IsRevoked=1` 일괄 처리.
- TEST-0104: 대상 계정 로그인 응답에 `must_change_password=true` 가 포함되어 frontend force change modal 이 노출된다. 변경 modal 의 close button 미제공 (강제 변경 전 다른 액션 차단).
- TEST-0105: `PATCH /api/auth/me` 로 비밀번호 변경 성공 시 `MustChangePassword=0` 으로 reset 되고 force modal 이 자동 닫힘.
- TEST-0106: 관리 콘솔 Account detail 의 `adminPasswordResetBtn` "비밀번호 초기화" 버튼이 비-self / 비-deleted / 비-pending new 계정에서만 노출.

**Phase 7 (admin select-all 현재 페이지 fix)**:
- TEST-0107: `currentPageAccounts()` helper 가 `filteredAccounts()` 의 `accountPage` slice 만 반환한다 (≤ ACCOUNT_PAGE_SIZE).
- TEST-0108: `accountSelectAll.checked = true` (또는 change event) 시 현재 페이지 row 의 id 만 `accountSelected` Set 에 추가, 다른 페이지 선택은 보존.
- TEST-0109: `updateAccountSelectAllCheckbox()` 가 현재 페이지의 선택 비율로 checked / indeterminate / unchecked 정확 반영.
- TEST-0110: 검색 / 필터 / 페이지 이동 후에도 동일 정합 유지.

**Phase 8 (내 대화 Ctrl/Shift 다중 선택 + bulk delete)**:
- TEST-0111: own 그룹의 conversation item 에 `.conv-item-checkbox` 가 노출 (delete.own 권한 보유 시). 타 계정 대화에는 미노출.
- TEST-0112: Ctrl/Meta + click → toggle. Shift + click → 마지막 click 이후 range 선택.
- TEST-0113: `.conv-bulk-bar` 가 selection ≥ 1 시 노출 + 라벨 "N개 선택됨" + 삭제 / 선택 해제 버튼.
- TEST-0114: `POST /api/delete_conversations` 가 partial success 응답 (`{deleted, deleted_pending, failed:[{conversation_id, reason}], current}`) 을 반환. 빈 body 는 400. 권한 없는 항목 / processing (force=false) 항목은 failed 에 분리.
- TEST-0115: ≥10 항목 선택 시 typed-confirm 으로 정확한 숫자 입력 요구. processing 대화 포함 시 추가 confirm + "삭제" 입력 요구.
- TEST-0116: 삭제 성공 후 `conversationSelected` clear, active 대화가 삭제된 경우 빈 상태로 reset, `loadConversations()` 로 list 재로드.

### TASK-0047 Product Selector + Auto 모드
- TEST-0031: `/api/session` 응답에 `product_pref{mode,pinned_id,fallback_reason}` + `conversation_product` 키가 항상 포함된다
- TEST-0032: 사이드바 헤더에 `#productChip` + `#productSelect` 마크업이 존재하고 caption "이 대화의 제품" 이 노출된다
- TEST-0033: select 옵션 첫 번째가 `auto` (value="auto", "auto · 자동 (제품 미선택)") 이고 활성 product 들이 그 뒤로 채워진다
- TEST-0034: chip `data-mode` 가 server hydrate 결과(auto / pinned) 와 정확히 일치한다
- TEST-0035: PATCH `/api/conversations/{cid}/product` 가 `pinned`/`auto` 양쪽 mode 에서 200 으로 응답하고 row 가 갱신된다
- TEST-0036: PATCH 가 `mode='pinned'` 인데 product_id 누락이거나 비존재 product_id 일 때 400 으로 거부한다
- TEST-0037: `AgentMemoryKv.last_status='processing'` 동안 PATCH 가 409 로 거부된다 (turn 단위 immutability 가드)
- TEST-0038: `/api/new_conversation` body 가 `mode='auto'|'pinned' + product_id?` 를 수용해 새 대화의 product_mode 가 일치한다
- TEST-0039: UI 에서 select 변경 → setActiveProduct → chip data-mode 즉시 갱신 + localStorage `mad.productPref.v1` 미러
- TEST-0040: 신규 auto 대화로 진입 후 페이지 reload 시 chip 이 auto 로 hydrate 된다
- TEST-0041: 고정 UI 라벨(button/label/option/h1-3 등; conv-list/messages 제외)에 한글 "상품" 잔존 0
- TEST-0042: `_runtime_tables_available` probe 가 신규 컬럼(`product_mode`, `ProductPrefMode`, `ProductPrefPinnedId`) 부재 시 errno 1054 로 False 반환해 마이그레이션을 자동 트리거한다

### TASK-0277 보관 대화 탭 UI 정합 다듬기 (REQ-20260615-0279, AC-0507~0508, Minor §12.3)
- TEST-0059: [문제1] admin.html 에 `class="admin-pane-note"` 사용 0건 + styles.css 에 `.admin-pane-note {` 규칙 0건(제거 확인).
- TEST-0060: [문제1] 보관 대화 pane header↔filter(`admin-archive-filter`) 사이 영역에 `<p>` 안내 문단 없음(다른 탭과 동일 밀도).
- TEST-0061: [문제1] `#archiveDetail` 빈 상태(static HTML) + `renderArchiveDetail` 빈 분기(JS) 양쪽이 `admin-archive-detail-note` 안내("보관됩니다" 포함) carry.
- TEST-0062: [문제2] `renderArchiveList` 로 긴/짧은 문자열 혼재 2 row 렌더 → 각 row 가 정확히 2개의 `.admin-archive-row-line`(1줄=topic+ts, 2줄=owner+by) — 문자열 길이 무관 고정.
- TEST-0063: [문제2] CSS 계약 — `.admin-archive-row-line` 에 `flex-wrap` 부재 + `min-width:0`; topic/owner/by 각 span 에 `white-space:nowrap`+`text-overflow:ellipsis`+`overflow:hidden`+`min-width:0`(줄바꿈 대신 절단 보증).

### TASK-0276 관리 콘솔 "보관 대화" 탭 UI 정합화 (REQ-20260615-0276, AC-0503, Minor §12.3)
- TEST-0053: 빈 목록 → `#archiveList` 에 `.admin-list-empty`("보관된 대화가 없습니다.").
- TEST-0054: 항목 N개 → `.admin-list-row.admin-archive-row` N개(audits 동형 클래스) + `#archiveListCount` "N건" + row 에 topic·보관 시각·소유자·보관 수행자 표시.
- TEST-0055: row 클릭 → `adminState.archives.selectedId` 설정 + `#archiveDetail` 에 `.admin-archive-detail`(dl 메타) 렌더 + 선택 row `is-selected`.
- TEST-0056: 미존재 selectedId → `#archiveDetail` `.admin-detail-empty`.
- TEST-0057: topic 에 `<img onerror>` 주입 → 목록·상세 양쪽 `_archiveEsc` escape(`img` 노드 0, `&lt;img` 텍스트).
- TEST-0058: truncated=true → `#archiveListScope` 에 "좁혀" 안내.

### TASK-0275 assistant 첨부 수정 → 새 버전 materialize + 버전 관리 (REQ-20260615-0275, AC-0493~0496, Critical §12.3)
- TEST-0046: `_parse_attachment_edit_blocks` — 정상 ```attachment-edit``` 블록(헤더 JSON + 내용)을 파싱하고, 헤더 깨짐/source_id 누락/0/블록 부재는 graceful 빈 리스트.
- TEST-0047: `_materialize_assistant_attachment_edits` — 정상 텍스트 첨부 → 새 버전 INSERT(VersionNumber+1, CreatedByRole='assistant', RootAttachmentId=root) + MinIO put + 직전 버전 supersede.
- TEST-0048: materialize 가드 — 바이너리 kind(pdf) source 거부(가드1), cross-conversation source 거부(가드2), cross-account source 거부(가드2), 내용 size cap 초과 거부(가드4), turn 당 개수 cap 초과분 무시(가드4).
- TEST-0049: `_serialize_attachment_for_api` — version_number/root_attachment_id(NULL root → 자기 Id)/created_by_role/is_assistant_generated/superseded 직렬화.
- TEST-0050: `_next_version_filename` — 확장자 보존 버전 접미(report.csv→report_v2.csv), 무확장자/빈입력 fallback.
- TEST-0051: `list_conversation_attachments` SQL 에 `SupersededAt IS NULL` 필터 존재(최신 버전만 노출, 정적 소스 검사).
- TEST-0052: 라이브 — materialize→MinIO 바이트(sha256 일치)·부모 supersede·목록 최신만·`/versions` 체인 2개·IDOR 2종 거부·traversal/.exe 차단·UNIQUE 충돌 IntegrityError.

### TASK-0272 프로필 첫 진입 제품 범위 적재 (REQ-20260615-0272, AC-0487, Minor §12.3)
- TEST-0043: `switchProfileTab("prompt")` 가 호출되면(탭 클릭 이벤트 없이도) `#promptProductSelect` 가 `state.products` 의 활성 제품으로 채워진다 — `openProfile("prompt")`(드로어 첫 오픈) 경로에서도 적재된다.
- TEST-0044: `initialize()` 의 탭 클릭 리스너는 `switchProfileTab(tab)` 만 호출하고 lazy 디스패치(`initAccountPromptEditor`/`loadProfileUsage`)를 직접 중복 보유하지 않는다 (단일 진입점 = `switchProfileTab`).
- TEST-0045: node --check app.js 통과 (구문 무결).

### TASK-20260618T022150 관리 콘솔 > 제품: 펼쳐진 데이터소스의 접근 가능 DB 목록 접기 (REQ-20260618-0314, AC-0571, Minor §12.3)
> **NOTE**: 초기 기본값은 TASK-20260618T025220(REQ-20260618-0316, 아래 TEST-0121~0124)에서 **접힘**으로 변경됨 — `verify_ds_accordion_collapse.mjs` 단언이 반전됐다. 아래 TEST-0117~0120 은 당시(기본 펼침) 케이스 정의이며 §4 의 그 시점 Run 으로 보존된다.
- TEST-0117: (superseded by TEST-0121) 제품 상세 datasource accordion 초기 렌더 시 편집 대상 행은 펼침 — `.ds-acc-body` 존재, 행 `.ds-acc-row.is-active`, head `aria-expanded="true"`, caret `▾`.
- TEST-0118: 펼친(편집 대상) 행 머리(`.ds-acc-head`) 클릭 시 접힘 — `.ds-acc-body` 제거, is-active 해제, `aria-expanded="false"`, caret `▸`, 행 유지, 하단 `.ds-acc-add-btn` 도달.
- TEST-0119: 접힌 행 머리 재클릭 시 재펼침 — `.ds-acc-body` 재생성, is-active 복원, `aria-expanded="true"`, caret `▾`(토글 복원).
- TEST-0120: `node -c admin.js` 구문 무결 + 접힌 행은 CSS 무변경(기존 비활성 행과 동일 렌더).

### TASK-20260618T025220 관리 콘솔 > 제품: 제품 선택 시 접근 가능 DB 목록 기본 접힘 (REQ-20260618-0316, AC-0573, Minor §12.3)
- TEST-0121: 제품 상세 datasource accordion **초기 렌더 시 편집 대상 행은 접힘**(기본값 변경) — `.ds-acc-body` 미생성, 행 `.ds-acc-row.is-active` 아님, head `aria-expanded="false"`, caret `▸`, datasource 행 자체는 목록 유지, 하단 `.ds-acc-add-btn`('+ 데이터소스 추가') 도달 가능.
- TEST-0122: 접힌(편집 대상) 행 머리(`.ds-acc-head`) 클릭 시 펼침 — `.ds-acc-body` 생성, `.ds-acc-row.is-active`, `aria-expanded="true"`, caret `▾`, 편집기 안 `.admin-db-picker-btn` 존재.
- TEST-0123: 펼친 행 머리 재클릭 시 재접힘 — `.ds-acc-body` 제거, is-active 해제, `aria-expanded="false"`, caret `▸`(토글 복원).
- TEST-0124: `node -c admin.js` 구문 무결 + `_dsBodyCollapsed` 초기값 `true`(기본 접힘) + 전환 리셋(`_switchEditDs`/`_afterBindChange` 의 `false`) 불변(REQ-0314 동작 보존).

### TASK-20260618T044611 릴리즈 노트 (작업 화면 프로필 탭 + 관리 콘솔 카테고리) (REQ-20260618-0321, AC-0578·0579, Major §12.3)
- TEST-0125: 공유 렌더러 `window.ReleaseNotes.render(container)` 가 `release-notes-data.js` 의 일자별 그룹을 전부 렌더(그룹 수 = `releases.length`), 그룹 카운트 배지 = 항목 수, 일자가 한국어 포맷("YYYY년 M월 D일") 또는 라벨("그 이전 주요 업데이트")로 표시.
- TEST-0126: 접기 기본값 = 최신(첫) 그룹만 펼침(head `aria-expanded="true"`·body `hidden=false`), 나머지 접힘. 그룹 머리 클릭으로 토글(펼침↔접힘). "모두 펼치기" → 전 그룹 펼침 + 버튼 텍스트 "모두 접기", 재클릭 → 전 그룹 접힘.
- TEST-0127: 영역 필터 칩(전체/작업 화면/관리 콘솔/공통) — '작업 화면' 선택 시 표시 항목 전부 `area="work"`(`.rn-area-work`), 항목 수 = work 항목 합, 그룹 수 = work 보유 일자 수. XSS — title/detail/summary 에 `<img onerror>`/`<script>` 주입 시 엘리먼트 미생성·원문 텍스트 보존(`textContent`). 빈 데이터(`releases=[]`) → `.rn-empty` 안내. `node --check` 4파일(release-notes-data.js / release-notes.js / app.js / admin.js) PASS.

### TASK-20260618T061520 릴리즈 노트 표면별 영역 노출 + 관리 콘솔 스크롤 (REQ-20260618-0323, AC-0582·0583, Minor §12.3)
- TEST-0128: `render(container, {areas:["work","common"]})`(작업 화면) — area=admin 항목 0건(`.rn-area-admin` 0), 표시 항목 = work+common 합, 필터 칩 = 전체/작업 화면/공통(3, '관리 콘솔' 칩 부재), 그룹 수 = work|common 보유 일자 수. 기본 `render(container)`(관리 콘솔)는 admin 항목 계속 노출(회귀 없음).
- TEST-0129: 관리 콘솔 릴리즈 노트 pane 세로 스크롤 — `styles.css` 에 `.admin-pane[data-admin-pane="release-notes"].is-active{overflow-y:auto}` 규칙 존재(소스 단언). 화면 정본 PB-0008(scrollHeight>clientHeight·하단 그룹 도달).

## 4. Test Run History
- 2026-07-01 (feature-0016 graphux5-panelmove-showfix — 세션 독립 폴 재개 시 진행 패널 미표시 버그 수정(`_metaGraphRenderProgress` 가 display 직접 해제) — **PB-0008 Windows-browser PASS(라이브 실측)**):
  - **Environment: Windows-browser** (실제 Windows Chrome/149 via `bin/win-browser.py` 무권한 relay, https://localhost/admin). 배포: web 90973df→showfix. 실측 PASS: (1) 진행 패널이 **우측 상세 aside 상단**에 표시(progressInsideDetailAside=true, topBar 제거 — 그래프 안 밀림), (2) 진행률 갱신(GMRIP root 처리 완료 1·done 마커 — depth-first fairness 로 0% 탈출), (3) **세션 독립**: 새로고침(activeRunId 없음) 후 진행 중 노드 클릭 → 폴 재개(status "0/1 running") + showfix 후 진행 패널 정상 표시. Evidence: `artifacts/shared/win-browser-shots-graphux5-panelmove/` (01_panel_right_aside·02_session_independent).
- 2026-07-01 (feature-0016 graphux5-panelmove — AI 능동 분석 진행 패널을 **우측 상세 패널로 이동**(상단 full-width 바 제거 → 그래프 안 밀림·여백 낭비 해소; 노드상세는 detailBody 분리로 진행 패널 유지), **Major §12.3(프론트 전용 비파괴 레이아웃)** — **PB-0008 Windows-browser 배포 후 라이브 검증 예정**):
  - **Environment: node 정적 + 집중 프론트 리뷰** — 정적 PASS: `admin.js` `node --check`, 구조 검증(진행 패널 aside 상단·detailBody 분리·타 참조 없음). 배포 후 실 Windows 브라우저로 확인: (a) 진행 패널이 상단 바가 아닌 **우측 상세 패널 상단**에 표시, (b) 그래프 캔버스가 아래로 밀리지 않음, (c) 미분석 시 여백 낭비 없음(패널 숨김), (d) 분석 중 노드 클릭 시 진행 패널 유지·아래 노드상세만 교체. Evidence(예정): `artifacts/shared/win-browser-shots-graphux5-panelmove/`.
- 2026-07-01 (feature-0016 graphux5-progress — AI 능동 분석 진행 현황 **화면 라이브·상세**(지속 진행 패널: 항목별 상태[분석중/완료/대기] + 진행바 + 분석중 주황 마커), **Major §12.3(비파괴 additive UI + 응답 필드)** — **PB-0008 Windows-browser 배포 후 라이브 검증 예정**):
  - **Environment: python/node 정적 + 적대 리뷰(backend/frontend 렌즈)** — 정적 PASS: `node_analysis.py` py_compile · `admin.js` `node --check`. 배포 후 실 Windows 브라우저로 확인: (a) AI 능동 분석 시작 → 상단 진행 패널이 노드 선택과 무관하게 라이브 갱신, (b) 완료/분석중/대기/실패 카운트 + 진행바, (c) 항목별 상세 리스트(⏳ 컬럼 X·✅ 테이블 Y·깊이) 갱신, (d) 그래프에 분석중 주황 점선 + 완료 보라 마커. Evidence(예정): `artifacts/shared/win-browser-shots-graphux5-progress/`.
- 2026-07-01 (feature-0016 graphux5 — 관리콘솔 그래프뷰 4항목 개선[검색 유사도 pg_trgm 명시·AI 능동분석 재귀/백그라운드·미분석 노드 컬럼 즉석 introspection·이웃깊이 드롭다운 즉시 갱신], **Major §12.3 + 외부 LLM 비용 + 신규 테이블 alembic 0028** — **PB-0008 Windows-browser DEFERRED(배포 후)**):
  - **Environment: python/node 정적 + 적대 리뷰 워크플로(backend/security/api/frontend/migration 5렌즈 → 발견별 검증, 확정 10건 전량 수정)** — 라이브 web 서버가 본 dev 셸에 이 worktree 로 미기동(미배포 worktree)이라 **실 Windows 브라우저 렌더 검증(그래프뷰 4항목 라이브)은 배포(deploy_scope: included) 후로 연기**. 정적: py_compile 6파일 + `node --check admin.js` + `migrate-lint --base main`(0028 expand-safe) 모두 PASS. 배포 후 확인: (1) 검색 시 노드 라벨 `이름 NN%`·상세 "유사도 NN%" 배지, (2) 상세 "✨ 능동 분석" → 폴링 진행·완료 노드 보라 마커·분석문 렌더, (3) 미큐레이션 Table 더블클릭 시 컬럼 즉석 전개(또는 명확 사유), (4) 이웃깊이 드롭다운 변경 시 즉시 재전개. Evidence(예정): `artifacts/shared/win-browser-shots-graphux5/`.
- 2026-07-01 (feature-0016 implicit-edges — 그래프 뷰 암묵 관계 신뢰 시각화(신뢰=실선/추정=점선/파단=숨김) + 범례 + 상세 카드 신뢰 배지, **Major §12.3(비파괴 UI 추가)** — **PB-0008 Windows-browser DEFERRED(배포 후)**):
  - **Environment: Windows-browser — N/A(사유 명시, 배포 후 잔여)**: 그래프 뷰의 REFERENCES 엣지 스타일/배지는 **AGE cutover + 추정 엣지 적재(alembic 0026 적용 + insight 워커 재빌드 + `metadata-graph-sync --rebuild`) 이후에만 실렌더**된다. 현 cycle 은 cutover 전 코드 완료 단계라 라이브 web 서버·AGE 스택 미기동 → 실 Windows 브라우저 시각검증은 배포 게이트(TASK T6.10)로 연기. CHECK#13 WARN-only.
  - **정적 PASS**: `admin.js` `node --check` OK · `styles.css`/`admin.html` 엣지 status/weight 데이터·`[status='candidate']`/`[status='trusted']` 셀렉터·범례(lg-line-solid/dashed)·신뢰 배지(_metaEdgeTrustBadge, esc() 경유 안전)·캐시버스터 bump(20260701-implicit-edges). 백엔드 투영(metadata_graph weight/status·broken 제외) 단위 검증은 feature-0002 tests(36 PASS).
  - **배포 후 PB-0008 잔여**: web 재빌드·AGE cutover 후 실 Windows 브라우저로 — ① FK 미선언 데이터소스 그래프에 추정 엣지 **점선** 표출 ② 실사용/프로브 강화 후 신뢰 엣지 **실선** 승격 ③ broken 엣지 **미표출** ④ 노드 상세 카드 관계에 `추정 w=…`/`신뢰` 배지 ⑤ 범례 실선/점선 구분.
  - **Pass/Fail: PARTIAL(정적·백엔드 단위 PASS, 라이브 PB-0008 배포 후 잔여)**.
- 2026-06-24 (TASK-20260624-item11-metadata-glossary-enum — 메타데이터 거버넌스 MVP-1(용어/ENUM CRUD), **Major §12.3 + 보안 경계(신규 RBAC)** — **PB-0008 Windows-browser DEFERRED(배포 후)**):
  - **Environment: python/node 단위 + 적대 backend+security 리뷰** — 라이브 web 서버 미기동(드레인 cycle)이라 실 Windows 브라우저 검증은 배포 후로 연기. CHECK#13 WARN-only.
  - **단위 PASS**: `tests/test_metadata_glossary_enum.py` **13/13**(PYTHONPATH=동일 worktree feature-0002/src:feature-0003/src — R1/R2 권한카탈로그·seed·least-priv · G403/E403 8 엔드포인트 권한게이트(코어 미호출) · GC/GU/GD·EC/EU CRUD(404/멱등/audit) · SV scope 400 · IV 입력검증 400 · LST 직렬화). 회귀 sample-feedback 15/15·permission-dependency-map 16/16 무영향. py_compile(app.py·kb_glossary.py)+node --check(admin.js).
  - **적대 backend+security 리뷰 PASS(SHIP)**: BLOCKER/MAJOR 0 — RBAC(8/8 게이트·코어 미호출·least-priv)·scope 누수/IDOR(`WHERE id+scope_key` 격리·allowlist fail-safe·scope 미재배정)·SQLi(`%s` 전수)·XSS(textContent)·원자성(commit/rollback/close) 전수 안전. MINOR-2(scope 드롭다운 init race) 흡수. MINOR-1(audit cross-DB best-effort) 수용. REV-20260624T130000 상세.
  - **배포 후 PB-0008 잔여**: web 재빌드·배포 후 실 Windows 브라우저로 — ① kb.ingest.manual 보유 계정에 "메타데이터" 탭 노출(미보유 숨김+서버 403) ② 용어/ENUM 서브탭 전환·scope 드롭다운(활성 ds + 공용) ③ 생성/수정/삭제(confirm) 동작 + 목록 갱신 ④ scope 격리(타 scope 비변경) 실 DB 확인 ⑤ ENUM UNIQUE 충돌 409.
  - **Pass/Fail: PARTIAL(단위·적대 리뷰 PASS, 라이브 PB-0008 배포 후 잔여)**.
- 2026-06-24 (TASK-20260624T105228-item08-fix-with-ai — "AI 로 고치기" 표적 재수정, **Major §12.3 + 보안 표면** — **PB-0008 Windows-browser DEFERRED(배포 후)**):
  - **Environment: node/python 단위 + 적대 리뷰** — 라이브 web 서버가 본 dev 셸에 미기동(드레인 cycle, 미배포 worktree)이라 **실 Windows 브라우저 렌더 검증은 배포 후로 연기**. CHECK#13 WARN-only.
  - **단위/로직 검증 PASS**: `tests/test_fix_with_ai.py` **10/10**(PYTHONPATH=feature-0002:feature-0003 — 가드 404/403/429·입력검증 400·정정문 1회 dispatch+원본NL 미전송+audit·**M1 인젝션 봉인 탈출 차단**·내부request 빌더) + M1 순수함수 독립 검증 + `py_compile`(app.py) + `node --check`(app.js) + CSS brace balanced.
  - **적대 backend+security 리뷰 PASS(흡수)**: SHIP-WITH-FIXES — MAJOR M1(인젝션 방어가 백틱만 막고 개행/라벨 탈출 허용) → nonce-봉인 데이터 블록으로 교정 흡수. `_make_internal_ask_request`(private `_receive`) 실측 안전(body 1회·worker is_disconnected·cross-account·슬롯). RBAC/IDOR 2중 방어·XSS textContent-only 확인. REV-20260624T105228 상세.
  - **배포 후 PB-0008 잔여(다음 단계)**: web 재빌드·배포 후 실 Windows 브라우저로 — ① 실패 SQL 답변 카드에 "AI 로 고치기" 버튼 노출(정상 결과엔 미노출) ② 클릭 시 disabled+로딩 라벨·정정 결과가 같은 대화에 새 assistant message 로 추가(원본 메시지 전체 재구성 아님) ③ reload 후 게이트 durable 유지 ④ 무권한(열람 전용) 멤버 클릭 시 403 toast. 
  - **Pass/Fail: PARTIAL(단위·리뷰 PASS, 라이브 PB-0008 배포 후 잔여)** — UI 로직·보안 경계는 단위테스트+적대 리뷰로 확정, 화면 정본은 배포 후 PB-0008.
- 2026-06-23 (TASK-20260623T031910-ds-conn-bg-decouple — 데이터소스 연결확인을 동기 render 경로에서 백그라운드로 분리, **Major §12.3** — **PB-0008 Windows-browser PASS**):
  - **Environment: Windows-browser** (실제 Windows Chrome/149.0.7827.116 via `bin/win-browser.py` 무권한 relay, `bridge_mode: relay`, endpoint `http://172.28.64.1:9223`, https://localhost:18080, self-signed ignore). WSL headless 아닌 실제 Windows 화면.
  - **Runner: AI** (win-browser eval + UI 구동 — 배포본 main `b2236fe`, `docker compose build web` + `up -d --no-deps web`, repo-web-1 Up healthy. 서빙 `admin.js?v=20260623-ds-conn-bg-decouple` + app.py conn_health 게이트·to_thread baked).
  - **실 환경 datasource 상태**: 등록 19개 중 `down` 다수(`mysql-gz-qa-kr`, `mysql-kr-an2-*`, `mssql-qa-idc/web-qa` 등) + `healthy`(`mysql-local`, `mysql-gz-dev`, `mssql_local` 등) 공존 — degraded 경로 실측 가능.
  - **① 이벤트 루프 비차단(핵심) PASS**: down `mysql-gz-qa-kr` 에 `?force=1`(live connect, to_thread) 가 **8024ms** 블록(502)되는 *동안* 동시 발사한 healthy `mysql-local` 요청은 **44ms** 완료. 수정 전이라면 동기 connect 가 이벤트 루프를 점유해 동시 요청도 ~8s 대기 → "나머지 UI 갱신 멈춤" 의 근본 해소 실증.
  - **② degraded fast-path PASS**: down `mysql-gz-qa-kr/databases`(no force) → **38ms**, status 200, `degraded:true`, `conn_status:down`, db 0 — live connect 없이 백그라운드 캐시 상태 즉시 반환.
  - **③ healthy 무회귀 PASS**: `mysql-local/databases` → 26ms, `degraded:false`, `conn_status:healthy`, **db 14개** 실목록. 제품 id=1(킹스레이드-로컬) 선택 시 배너 없음·DB picker 정상.
  - **④ 시각 배너 PASS**: 제품 id=95(건즈 국내 QA, 단일 down `mysql-gz-qa-kr`) 선택 + 데이터소스 아코디언 펼침 → picker 위 빨간 배너 **"데이터소스 연결 끊김 — DB 목록 로드를 보류했습니다(연결 상태는 백그라운드에서 점검 중)."** + **[새로고침]** 버튼 렌더(`role="status"`, visible). 좌측 제품 목록·시스템 프롬프트 등 나머지 UI 정상 렌더(차단 0).
  - **⑤ 새로고침(force) 버튼 PASS**: 클릭 즉시 `disabled + "확인 중…"`(중복클릭 차단) → force connect ~8s timeout(502) 후 배너 유지 + 버튼 재활성("새로고침", 재시도 가능, stuck 0).
  - **Evidence:** `artifacts/pb0008-ds-conn-bg-decouple/degraded-banner-down-ds.png`(빨간 배너+새로고침, 나머지 UI 정상) · `healthy-product-no-banner.png`(대조군).
  - **Pass/Fail: PASS** — 배포 시스템에서 이벤트 루프 비차단·degraded fast-path·healthy 무회귀·시각 배너·force 재시도를 실제 Windows 브라우저로 실측 통과. CHECK#13 충족.
  - **Notes:** §18.8 적대 패널(frontend NO REAL ISSUES + backend inline 7축) SHIP. minor a11y `role="status"` 반영. REV-20260623T031910-ai-claude-ds-conn-bg-decouple.
- 2026-06-23 (TASK-20260623T030418-quota-rbac-permission — 계정·역할 LLM 사용 한도 조회/조절 전용 권한 + admin catchup lockout 수정, **Major §12.3 — 보안 경계(RBAC)** — **PB-0008 Windows-browser PASS**; CHG/REV-20260623T030418 + CHG-20260623T053000 evidence):
  - **Environment: Windows-browser** (실제 Windows Chrome/149.0.7827.116 via `bin/win-browser.py` 무권한 relay `bridge_mode: relay`, endpoint `http://172.28.64.1:9223`, https://localhost:18080, self-signed ignore). WSL headless 아닌 실제 Windows 화면. 배포: main `3cda161`(PR #373 권한 + #375 catchup) → `docker compose build web`(캐시) + `up -d web`(repo-web-1 Up healthy). 서빙 admin.js 에 `can("quota.read")` 게이트·`opts.readOnly` 분기 baked. app.py `_ensure_seed_roles` quota catchup baked.
  - **Runner: AI** (win-browser eval — 실 배포 renderRoleDetail/renderAccountDetail + buildQuotaEditor 를 3-tier permission 으로 구동, DOM 실측).
  - **★라이브 버그 적발(PB-0008 가치) — admin lockout**: 게이트를 console.manage→quota.read/quota.manage 로 전환했으나 신규 권한이 기존 배포 admin 역할(WebRolePermissions RoleId=3)에 미부여 → `bootstrap_admin` 의 `adminState.me.permissions["quota.read"]`=false (DB quota.read=0/quota.manage=0). seed=set(PERMISSION_CODES)는 role 생성 시점만 적용. **정적 outside-voice 미검출**(admin=전권 invariant 만 확인) → `_ensure_seed_roles` admin catchup 에 quota.read/manage 추가(#375). 재배포 후 DB quota.read=1/quota.manage=1·adminState.me read=true/manage=true 복구.
  - **PB-0008 PASS (배포본 main `3cda161`)**:
    - **역할 상세 3-tier**(roleId=1, 실 renderRoleDetail): tier3(quota.read+manage)=섹션 표시·저장버튼 O·입력 활성·readonly note X / tier2(quota.read만)=섹션 표시·저장버튼 X·입력 disabled·"조회 전용" note O / tier1(무권한)=섹션 미표시.
    - **계정 상세 3-tier**(acctId=39 ijkim, 실 renderAccountDetail): tier3=편집 가능·역할 상속 안내 O / tier2=readOnly·상속 안내 O / tier1=미표시. 동일 게이트 동작.
    - **buildQuotaEditor 직접**: readOnly=false→저장버튼+입력활성·value 주입, readOnly=true→입력 disabled+저장버튼 미렌더+조회전용 note.
    - **백엔드 게이트**: GET `/api/admin/quotas` admin(quota.read 보유) **200** + roles(8)·account_overrides·enforce=true. PUT=quota.read+quota.manage 동시 요구(B8 단위).
  - **Pass/Fail: PASS** — 배포된 시스템에서 "조절은 조회 종속, 조회 없으면 UI 미표시" 가 역할·계정 상세 모두에서 실 Windows 브라우저로 실측 통과. CHECK#13(PB-0008 Windows-browser) **충족**.
  - CHG/REV-20260623T030418-ai-claude-quota-rbac-permission + CHG-20260623T053000-ai-claude-quota-admin-catchup / REQ-20260623-0332 / AC-0610·0611.
- 2026-06-23 (TASK-20260623T021500-quota-editor-escapehtml-fix — buildQuotaEditor escapeHtml ReferenceError 수정[잠복 버그], **Minor §12.3** — **PB-0008 Windows-browser PASS**; CHG/REV-20260623T021500 evidence):
  - **Environment: Windows-browser** (실제 Windows Chrome/149.0.7827.116 via `bin/win-browser.py` 무권한 relay `bridge_mode: relay`, endpoint `http://172.28.64.1:9223`, https://localhost:18080, self-signed ignore). WSL headless 아닌 실제 Windows 화면. 배포: main `9e7ec24`(PR #367) → `docker compose build web`(캐시) + `up -d web`(repo-web-1 Up healthy). 서빙 admin.html `admin.js?v=20260623-quota-escapehtml-fix`, 컨테이너 baked admin.js 에 `escapeHtml(` **0건**·`note.textContent = opts.inheritNote` 1건·`input.value` DOM 주입 확인.
  - **Runner: AI** (win-browser eval — 이전 ReferenceError 로 실패했던 정확한 호출 재현 + 실 DOM 주입 computed style 계측).
  - **★근본 원인 실측 확정**: 배포 admin 페이지에서 `typeof escapeHtml === "undefined"`(**escapeHtmlAvail: false**) — `escapeHtml` 은 app.js 전용이고 admin.html 이 app.js 미로드 → 구 코드의 escapeHtml 보간은 실제로 `ReferenceError` throw. ④ 도입(05d58d1) 이래 잠복(한도 UI production 무렌더), relocate 가 노출.
  - **PB-0008 PASS (배포본 main `9e7ec24`)**:
    - **재현(핵심)**: 이전 실패 호출 `buildQuotaEditor({scope:"account", id:5, daily:null, monthly:1000, inheritNote:...})` 가 **render.ok: true**(throw 제거) — `cls="admin-quota-editor"`, daily/monthly input·저장 버튼 렌더, `dailyVal=""`(null→상속)·`monthlyVal="1000"`(`.value` DOM 주입).
    - **실 DOM 주입 computed**: 역할 editor `roleDailyVal="50000"`·`roleMonthlyVal=""`(무제한), 계정 editor inheritNote 표시(acctNoteShown), `.admin-quota-fields` computed `display:flex`(styles.css 해석), 저장 버튼 "한도 저장".
    - **XSS-safe 실측**: inheritNote 에 `<b>x</b>` 주입 시 `note.textContent` 로 텍스트 보존(innerHTML 에 `&lt;b&gt;` — HTML 미파싱).
    - **구 패널 제거**: `#usageQuotaDetails` false·`#quotaRolesBox` false(usage 탭 한도 패널 제거 확인).
  - **Pass/Fail: PASS** — 배포된 시스템에서 역할·계정 상세 "LLM 사용 한도" 편집기가 escapeHtml ReferenceError 없이 실 Windows 브라우저에서 렌더·동작함을 실측 통과. CHECK#13(PB-0008 Windows-browser) **충족**.
  - CHG/REV-20260623T021500-ai-claude-quota-editor-escapehtml-fix / AC-0609.
- 2026-06-19 (TASK-20260619T120000-db-rule-pending-batch — 정규식 자동 규칙 pending → "모두 적용" 재배선, **Major §12.3 — 보안 경계**):
  - **Environment: CLI/jsdom + py_compile**. 신규 `tests/verify_db_rule_pending.mjs` **jsdom 18/18 PASS**(Node18 + jsdom@22): 키 정규화(`1::maindb`)·`_ensureDbRulePending` 빈 구조·`_dbRulePendingEntryEmpty`·**스테이징(create push) 시 apiFetch 호출 0**(즉시 반영 금지 회귀 게이트)·`productDbRuleDirtyCount`·`pendingChangeCount` 포함·`_settleDbRulePending` 빈 엔트리 제거·`applyAllPending` 추가 POST/수정 PUT/승인 approve-pending/삭제 DELETE?strip=1 호출·body 전달·**순서 추가<수정<승인<삭제**·성공 시 `pending.productDbRules` 정리·pending 0 시 no-op. `node --check admin.js` PASS, `python3 -m py_compile app.py` PASS, CSS brace balance 1417/1417.
  - **make test (컨테이너 전체/통합)**: backend `verify_db_rule_logic.py` **30/30 PASS**(패턴 매칭·인젝션 제외·audit 등록 — 본 cycle 무변경 회귀 0). CI "test" 워크플로 fail 은 모든 PR 공통 zombie(`PermissionError: /shared` — runner 컨테이너 경로 부재, collection 단계; #362·#363·#364 도 fail 채 머지, PROJECT.md §10 CI 폐기) — 본 변경 무관.
  - **Environment: Windows-browser** (실 Windows Chrome/149.0.7827.116 via `bin/win-browser.py` 무권한 relay, endpoint `http://172.28.64.1:9223`, https://localhost:18080). 배포: main `147d040`(PR #365) → `make -o init web`(web 이미지 재빌드+재기동, init 의 KB-pg 단계는 타 세션 pg cutover 정황이라 `-o init` 우회; 서빙 `admin.js?v=20260619-db-rule-pending`·baked `productDbRules`·`trigger="view"`=0 확인).
  - **Runner: AI** (관리 콘솔 `/admin` → 제품 109(DK_DEV, datasource `mssql-dk-dev`) → 데이터소스 accordion 펼침 → 정규식 자동 규칙 에디터).
  - **PB-0008 PASS (배포본 main `147d040`)**:
    - **즉시 반영 금지(핵심, 보고된 버그)**: "+ 규칙 추가" 저장 버튼 라벨 = **"추가 대기"**. 패턴 `^pb0008_zzz_notreal_` 입력 후 클릭 → `.cov-db-rule-card.is-staged-create` + 배지 **"추가 대기"** + 패턴 표시 + 하단 **"1건 pending"** + "모두 적용" 활성화. 동시에 라이브 `GET …/db-rules` = **서버 규칙 1개(원본 `(^GameLog_[0-9]{3}$)|…`)만, 스테이징 패턴 서버 부재** → **편집이 즉시 반영되지 않음 실증**(보고된 "Pending 없이 즉시 반영" 해소).
    - **조회=무변경**: 에디터 조회(GET)만으로 allowlist/규칙 미변동(view-reconcile 제거 실증).
    - **"모두 적용"=실제 적용 경로**: 라이브 backend round-trip(POST `…/db-rules` → `status 200`·rule_id 13 생성·`presentAfterCreate=true` → DELETE`?strip=1` 200 → `presentAfterDelete=false`)로 create 가 실제 persist 함을 확인. applyAllPending 의 client replay 는 jsdom 18/18(엔드포인트·body·순서) 로 고정 — 합성 검증 완료.
    - **프로덕션 무흔적**: 최종 서버 규칙 1개(원본만), 테스트 규칙 0 — 검증 후 정리 완료.
  - 증거: `artifacts/pb0008-db-rule-pending/{pb0008-dbrule-01-editor,02-staged-add,03-applied}.png`. 비고: 라이브 UI 의 "모두 적용" 1회 round-trip 읽기는 win-browser relay transient drop(이 환경 알려진 이슈)으로 1회 오염됐으나, backend persist round-trip + jsdom client 검증으로 apply 경로 확정.
  - REV-20260619T120000-ai-claude-db-rule-pending-batch / REV-20260623T010000-ai-claude-db-rule-pending-evidence [SKIPPED:docs-only-pb0008-evidence].
- 2026-06-18 (TASK-20260618T061520-ai-claude-release-notes-scope-scroll — 작업 화면 관리 콘솔 영역 숨김 + 관리 콘솔 스크롤, **Minor §12.3**):
  - **Environment: CLI/jsdom** (frontend-only). `tests/verify_release_notes.mjs` **34/34 PASS** (Node18 + jsdom@22): TEST-0128(작업화면 admin 0건·표시=work+common 43·칩 3개[전체/작업/공통]·'관리 콘솔' 칩 부재·그룹 11·관리 콘솔 기본 admin 노출 회귀 없음), TEST-0129(styles.css release-notes pane `overflow-y:auto` 소스 단언) + 기존 27건(접힘 가드·필터·XSS 등). `node --check` PASS. REV-20260618T061520-ai-claude-release-notes-scope-scroll [SKIPPED:frontend-ui-scope-scroll-no-backend-no-rbac].
  - **Environment: Windows-browser** (실제 Windows Chrome/149.0.7827.116 via `bin/win-browser.py` 무권한 relay, endpoint `http://172.28.64.1:9223`, https://localhost:18080). 배포: main `e812c9d`(PR #345) → `docker compose build web` + `up -d --no-deps web`(repo-web-1 Up healthy, mysql_ok·pg_ok). 서빙 `styles.css/app.js/release-notes.js ?v=20260618-rn-scope-scroll` baked.
  - **Runner: AI** (작업 화면 `openProfile('release-notes')` + 관리 콘솔 `switchTab('release-notes')`, getComputedStyle/scrollTop/getBoundingClientRect 계측).
  - **PB-0008 PASS (배포본 main `e812c9d`)**:
    - **작업 화면(AC-0582)**: 릴리즈 노트 탭 필터 칩 = `[전체, 작업 화면, 공통]`(**'관리 콘솔' 칩 부재**), `.rn-area-admin` 항목 **0건**, 총 43항목(work 40 + common 3), 11 그룹. 관리 콘솔 영역 노트 완전 숨김 확정.
    - **관리 콘솔(AC-0583)**: 릴리즈 노트 pane computed `overflow-y:auto`, `scrollHeight 1418 > clientHeight 801`(**스크롤 가능**), `scrollTop=99999` 적용 시 하단 도달(scrolledToBottom=true)·마지막 그룹 bottom 이 pane viewport 내(하단 항목 접근 가능). admin 항목 **23건 계속 노출(회귀 없음)**.
  - 스크린샷: 본 실측 시점 relay `Page.screenshot` 이 폰트 로드 단계에서 transient timeout(페이지 렌더·eval 정상, 환경적 이슈) → 직전 사이클 시각 베이스라인(`artifacts/pb0008-release-notes/{work-screen,admin}-release-notes.png`) 보유. 본 cycle 검증은 computed 값(authoritative)으로 완결.
  - REV-20260618T062406-ai-claude-release-notes-scope-scroll-evidence [SKIPPED:docs-only-pb0008-evidence].
- 2026-06-18 (TASK-20260618T044611-ai-claude-release-notes — 릴리즈 노트 작업 화면 탭 + 관리 콘솔 카테고리, **Major §12.3** · additive frontend):
  - **Environment: CLI/jsdom** (frontend-only, layout 비의존). `tests/verify_release_notes.mjs` **26/26 PASS** (Node18 + jsdom@22, `/tmp/node_modules`, 두 정적 스크립트를 jsdom window 에 eval 후 실제 DOM 검증): TEST-0125(그룹 수=11=releases·카운트 배지=항목 수·일자 한국어 포맷·라벨 블록), TEST-0126(첫 그룹만 펼침·클릭 토글·모두 펼치기/접기·버튼 텍스트 전환), TEST-0127(작업 화면 필터 40항목 전부 work·관리 콘솔 필터 23항목 전부 admin·필터 그룹 수·XSS 3건 textContent·빈 데이터 안내). `node --check` 4파일 PASS. REV-20260618T044611-ai-claude-release-notes [SELF-REVIEW:frontend-additive-no-backend-no-rbac] SHIP.
  - **Environment: Windows-browser** (실제 Windows Chrome/149.0.7827.116 via `bin/win-browser.py` 무권한 relay `bridge_mode: relay`, endpoint `http://172.28.64.1:9223`, https://localhost:18080, self-signed ignore). WSL headless 아닌 실제 Windows 화면. 배포: main `091280e`(PR #338 릴리즈 노트 + PR #339 접힘 hotfix 머지) → `docker compose build web` + `up -d --no-deps web`(repo-web-1 Up healthy, /healthz mysql_ok·pg_ok true). 서빙 `release-notes.js`·`release-notes-data.js`(누출어 0)·index/admin `styles.css?v=20260618-release-notes`·`.rn-group-body[hidden]{display:none}` 가드 baked.
  - **Runner: AI** (launch → bootstrap_admin 세션 → 작업 화면 `openProfile('release-notes')` + 관리 콘솔 `switchTab('release-notes')` 실측, getComputedStyle/getBoundingClientRect 계측).
  - **PB-0008 1차 적발 → hotfix → PB-0008 재실측 PASS (배포본 main `091280e`)**:
    - **접힘 트랩 적발/수정 확정 (핵심)**: 1차 실측에서 접힌 그룹 computed `display:flex`(접힘 무력화, `.rn-group-body{display:flex}` 가 UA `[hidden]{display:none}` override) → `.rn-group-body[hidden]{display:none}` hotfix(CHG-20260618T050409) → 재실측 **접힌 그룹 computed `display:none` + 높이 0px** 확정.
    - **작업 화면 (프로필 > 릴리즈 노트 탭)**: 탭 활성·pane 표시, 11 일자 그룹, 첫 그룹(2026년 6월 18일) `aria-expanded=true`·`display:flex`(7건)·둘째 그룹 `aria-expanded=false`·**`display:none`**(접힘). 둘째 그룹 머리 클릭 → `aria=true`·`display:flex`(토글 펼침). 영역 필터 '관리 콘솔' → 23항목 전부 `.rn-area-admin`. '모두 펼치기' → 전 그룹 `display!=none`·버튼 "모두 접기". evidence `artifacts/pb0008-release-notes/work-screen-release-notes.png`.
    - **관리 콘솔 (릴리즈 노트 카테고리)**: 시스템 그룹에 카테고리 노출(`tabVisible=true`, 권한 미요구)·pane 활성, 11 그룹, 첫 그룹 `display:flex`·height 490px·둘째 그룹 **`display:none`·height 0px**(접힘). 둘째 그룹 클릭 → `aria=true`·`display:flex`. 영역 필터 '작업 화면' → 40항목 전부 `.rn-area-work`. evidence `artifacts/pb0008-release-notes/admin-release-notes.png`.
    - **양 화면 동일 콘텐츠·렌더러 확정**(DRY): 두 화면 모두 동일 일자 그룹·동일 항목·동일 필터/접기 동작. 콘텐츠 누출어(RBAC/환각/권한 상승 등) 0 서빙 확인.
  - REV-20260618T051005-ai-claude-release-notes-evidence [SKIPPED:docs-only-pb0008-evidence].
- 2026-06-18 (TASK-20260618T025220-ai-claude-ds-acc-collapsed-default — 제품 선택 시 DB 목록 기본 접힘, **Minor §12.3**):
  - **Environment: CLI/jsdom** (frontend-only, layout 비의존). `tests/verify_ds_accordion_collapse.mjs` **19/19 PASS** (Node18 + jsdom@22, 단언 반전): TEST-0121(초기 접힘 — body 미생성·is-active 아님·aria false·caret ▸·행 유지·`.ds-acc-add-btn` 도달), TEST-0122(클릭 펼침 — body 생성·is-active·aria true·caret ▾·picker 버튼), TEST-0123(재클릭 접힘 — body 제거·is-active 해제·aria false·caret ▸). `node -c admin.js` PASS(TEST-0124, `_dsBodyCollapsed=true` 초기값). REV-20260618T025220-ai-claude-ds-acc-collapsed-default [SKIPPED:frontend-ui-default-value-no-backend-no-rbac].
  - **Environment: Windows-browser** (실제 Windows Chrome/149.0.7827.116 via `bin/win-browser.py` 무권한 relay `bridge_mode: relay`, endpoint `http://172.28.64.1:9223`, https://localhost:18080, self-signed ignore). WSL headless 아닌 실제 Windows 화면. 배포: main `1ad1519`(PR #328 merge) → `docker compose build web` + `up -d --no-deps web`(repo-web-1 Up healthy, /healthz mysql_ok·pg_ok true). 서빙 admin.html `admin.js?v=20260618-ds-acc-collapsed-default` + 서빙 admin.js 에 `let _dsBodyCollapsed = true` baked(1 hit).
  - **Runner: AI** (launch → bootstrap_admin 로그인(`/api/auth/login` 200) → 제품 탭 → **단일 데이터소스 제품 KR(`mysql-local`)** 선택 → 클릭 없이 초기 상태 측정 + 머리 클릭 토글 측정).
  - **PB-0008 PASS (배포본 main `1ad1519`)**:
    - **제품 선택 직후 기본 접힘(요구 핵심)**: KR 선택 후 **클릭 없이** `.ds-acc-body` **미생성**(bodyPresent=false)·데이터소스 행 `mysql-local` 유지(dsRowCount=1)·`is-active` 아님·`aria-expanded="false"`·caret `▸`·head title="클릭하면 펼쳐서 DB 편집"·하단 `.ds-acc-add-btn` viewport 내 도달(addBtnReachable=true). evidence `artifacts/pb0008-ds-acc-collapsed-default/default-collapsed-on-select.png`(`▸ mysql-local mysql 기본 ⋯` 접힘 + 삭제 버튼 화면 내).
    - **토글 무회귀**: 데이터소스 머리 클릭 → 펼침(`.ds-acc-body` 생성·caret ▾·`aria-expanded="true"`·title "클릭하면 접기"·`.admin-db-picker-btn` 존재) → 재클릭 → 접힘(body 제거·caret ▸). REQ-0314 토글·전환 자동 펼침 보존.
    - REV-20260618T025848-ai-claude-ds-acc-collapsed-default-evidence [SKIPPED:docs-only-pb0008-evidence].
- 2026-06-18 (TASK-20260618T022150-ai-claude-ds-acc-collapsible — 관리 콘솔 > 제품 데이터소스 DB 목록 접기, **Minor §12.3**):
  - **Environment: CLI/jsdom** (frontend-only, layout 비의존 — body 노드 생성/제거·클래스·속성·caret). `tests/verify_ds_accordion_collapse.mjs` **19/19 PASS** (Node18 + jsdom@22, admin.js realm 로드 후 `renderProductDetail()` 단일 datasource 제품 렌더): TEST-0117(초기 펼침 — body 존재·is-active·aria-expanded true·caret ▾·picker 버튼 존재), TEST-0118(토글1 접힘 — body 제거·is-active 해제·aria-expanded false·caret ▸·행 1개 유지·`.ds-acc-add-btn` 도달), TEST-0119(토글2 재펼침 — body 재생성·is-active 복원·aria-expanded true·caret ▾). `node -c admin.js` PASS(TEST-0120). REV-20260618T022150-ai-claude-ds-acc-collapsible [SKIPPED:frontend-ui-presentation-toggle-no-backend-no-rbac].
  - **Environment: Windows-browser** (실제 Windows Chrome/149.0.7827.116 via `bin/win-browser.py` 무권한 relay `bridge_mode: relay`, endpoint `http://172.28.64.1:9223`, https://localhost:18080, self-signed ignore). WSL headless 아닌 실제 Windows 화면. 배포: main `9069518`(PR #323 merge) → `docker compose build web` + `up -d --no-deps web`(repo-web-1 Up healthy, /healthz mysql_ok·pg_ok true). 서빙 admin.html `admin.js?v=20260618-ds-acc-collapsible` + 서빙 admin.js 에 `_dsBodyCollapsed`/`isEditTarget`/`isExpanded` baked(10 hit) + 컨테이너 baked admin.js `_dsBodyCollapsed`(7 hit). (healthz git_commit=unknown 은 GIT_COMMIT build-arg 미주입 기존 quirk — 코드 베이킹은 직접 grep 으로 확증.)
  - **Runner: AI** (launch → bootstrap_admin 로그인(`/api/auth/login` 200) → 관리 콘솔 제품 탭 → **단일 데이터소스 제품 KR(id=1, `mysql-local`)** 선택 — 사용자 보고 시나리오 정확 일치 → 데이터소스 accordion 머리 클릭 토글 + 하단 UI 위치 getBoundingClientRect 실측).
  - **PB-0008 PASS (배포본 main `9069518`, repo-web-1 Up healthy, mysql_ok·pg_ok)**:
    - **초기 펼침(회귀 없음)**: 단일 datasource `mysql-local`(dsRowCount=1), `.ds-acc-body` 존재·computed `display:block`·행 `is-active`·head `aria-expanded="true"`·caret `▾`. 펼친 상태에서 `.ds-acc-add-btn`('+ 데이터소스 추가') top=**912px** > viewport **836px** → **화면 밖**(사용자 보고 "하단 UI 접근 번거로움" 실증).
    - **접힘(요구 핵심)**: 데이터소스 행 머리(`.ds-acc-head`) 클릭 → `.ds-acc-body` **제거**(bodyPresent=false)·데이터소스 행 자체는 목록 **유지**(dsRowStillThere=1)·`is-active` 해제·`aria-expanded="false"`·caret `▸`·head title="클릭하면 펼쳐서 DB 편집". `.ds-acc-add-btn` top **912→685px** = **viewport 안**(addBtnInViewport=true) → 하단 UI(데이터소스 추가·제품 프롬프트·**삭제** 버튼) 도달 가능 실증. evidence `artifacts/pb0008-ds-acc-collapsible/ds-acc-collapsed.png`(`▸ mysql-local mysql 기본 ⋯` 접힘 + 삭제 버튼 화면 내 노출).
    - **재펼침(토글 복원)**: 머리 재클릭 → `.ds-acc-body` 재생성(bodyPresent=true)·caret `▾`·`aria-expanded="true"`·head title="클릭하면 접기". 펼침↔접힘 토글 사이클 정상.
    - REV-20260618T024209-ai-claude-ds-acc-collapsible-evidence [SKIPPED:docs-only-pb0008-evidence].
- 2026-06-17 (TASK-0295 — 작업 화면 제품 목록 product.access RBAC 게이트):
  - **Environment: CLI** (순수 단위, DB 불필요). `tests/test_product_list_rbac.py` **9/9 PASS** (agent 이미지 `import app`, `AGENT_MODE=test`): T1 접근 권한 보유 제품만 잔존(KR 권한만→KR, MY/JP 제외), T2 account=None 빈 목록, T3 전 권한 회수 빈 목록, T4 ProductKey 대소문자 무관(대문자 ProductKey ↔ 소문자 `product.access.kr`), T5 product_key 부재 행 방어적 제외, T6~T8 `_coerce_default_product_id`(목록 내 유지 / 목록 밖 첫 제품 보정 / 빈 목록 0), T9 **정적** — `_filter_products_for_account_access` 호출 정확히 2곳(작업화면 전용) + admin `_list_products(include_inactive=True)` 경로 미적용. `python3 -m py_compile app.py` PASS. REV-20260617T054423-ai-claude-task0295-product-list-rbac [SUBAGENT:product-list-rbac-review] SHIP.
  - **Environment: Windows-browser** (실제 Windows Chrome/148.0.7778.217 via `bin/win-browser.py` 무권한 relay `bridge_mode: relay`, endpoint `http://172.28.64.1:9223`, https://localhost:18080, self-signed ignore). WSL headless 아닌 실제 Windows 화면.
  - **Runner: AI** (launch → bootstrap_admin(admin role) 로그인 → 작업 화면 → DB 에서 `product.access.<key>` 권한 회수/복원 대비 + `/api/session` products 및 작업 화면 드롭업 메뉴 DOM 실측).
  - **PB-0008 PASS (배포본 main `3fa87e8`, repo-web-1 Up healthy, mysql_ok·pg_ok)**:
    - **부분 회수(요구 핵심)**: admin role `product.access.mv`(MV) 회수 **전** `/api/session` products **8개**(KR·KR_QA·**MV**·GZ_KR·DK·FH·GZ_QA_KR·MV_QA) → 회수 **후** **7개**(MV 제거, **MV_QA 유지** = 제품별 권한 정확) — 백엔드 필터 실증. 작업 화면 드롭업 메뉴 DOM `.product-dropup-item[data-mode="pinned"]` **7개·MV 부재**(`state.products` 7개) — UI 실증. evidence `artifacts/pb0008-task0295/mv-revoked-picker.png`.
    - **빈목록(전체 회수)**: admin role 전체 `product.access.*`(8건) 회수 → 드롭업 `state.products=[]`·pinned 항목 **0개**·신규 안내 **"접근 가능한 제품이 없습니다"**(`.product-dropup-empty`) 렌더 — 프론트 빈목록 graceful 실증. evidence `artifacts/pb0008-task0295/all-revoked-empty.png`.
    - **복원**: 회수한 권한 행 전부 재부여(admin product.access 8건 복원 확인) — 운영 무오염.
    - REV-20260617T060740-ai-claude-task0295-pb0008-evidence [SKIPPED:docs-only-pb0008-evidence].
- 2026-06-16 (TASK-20260616T100304-conv-entry-defaults — 작업 화면 첫 진입 기본값: 타 계정 대화 접힘 + 빈 대화 화면):
  - **Environment: CLI** (정적 + 순수 node 회귀). `node --check app.js` PASS + `tests/verify_conv_entry_defaults.mjs` **20/20 PASS** (jsdom 불필요 — localStorage/state 로직: `_seedOthersCollapsedOnce` fresh seed/already-seeded respect/date-group 보존, `loadConversations` 빈 진입(allowCurrentFallback=false)·기본 폴백·resume-select·preferred-미존재·pending-guard, `initializeWorkspace` 배선 4종). 백엔드 무변경. REV-20260616T100304-ai-claude-conv-entry-defaults [SKIPPED:frontend-ui-entry-defaults-no-backend-no-rbac].
  - **Environment: Windows-browser** (실제 Windows Chrome/148.0.7778.217 via `bin/win-browser.py` 무권한 relay `bridge_mode: relay`, endpoint `http://172.28.64.1:9223`, https://localhost:18080, self-signed ignore). WSL headless 아닌 실제 Windows 화면.
  - **Runner: AI** (launch → 로그인(bootstrap_admin) → 작업 화면 진입 → localStorage clean-room 재현 + computed/state 실측).
  - **PB-0008 PASS (배포본 main `b5f2434`, healthz git_commit 일치 mysql_ok·pg_ok, `?v=20260616-conv-entry-defaults`)**:
    - **요구2 (빈 대화 화면)**: 로그인(bootstrap_admin)·대화 104개·서버 직전 대화 존재(`state.session.conversation_id="20260615070025-1ae46506"`)인데도 첫 진입 `state.activeConversationId=""`·`#conversationTitle="대화를 선택하세요"` — 직전 대화 자동선택 차단 확인(구behavior 라면 로드됐을 대화).
    - **요구1 (타 계정 대화 접힘)**: 타 계정 대화 50건 존재. 첫 진입 시 `.conv-group-collapsible`("타 계정 대화") `is-collapsed=true`·`aria-expanded="false"`·`.conv-owner-header` **0개 렌더**(50건 숨김), `localStorage["mad.othersCollapsedSeed.v1"]="1"`·`collapsedGroups=["__others__"]`.
    - **clean-room 결정 증명**: `localStorage.clear()` → reload → seed 재발화(`seedFlag="1"`·`__others__`∈set·접힘·owner 0)·빈 화면(`activeConv=""`) 동시 재현. 서버 current 는 여전히 존재(미로드).
    - **선호 존중**: "타 계정 대화" 헤더 click → 펼침(`is-collapsed=false`·owner 헤더 5개 렌더·set 에서 `__others__` 제거) → reload 후에도 **펼침 유지**(`stillExpandedAfterReload=true`·owner 5개·seedFlag 유지) — 재접힘 강제 없음(seed-once).
    - evidence `artifacts/pb0008-conv-entry-defaults/entry-others-collapsed-empty-chat.png`(타 계정 대화 접힘 + 빈 대화 화면 육안). REV-20260616T163634-ai-claude-conv-entry-defaults-pb0008 [SKIPPED:docs-only-pb0008-evidence].
- 2026-06-16 (TASK-20260616T022652-ai-claude-sidebar-resize — 대화창 좌측 사이드바 너비 드래그 조절):
  - **Environment: CLI** (정적 + jsdom + 컨테이너 make test). `node --check app.js` PASS + CSS brace 균형(1222=1222) + **jsdom 23 PASS** (`tests/verify_sidebar_resize.mjs` — [1] index.html `#sidebarResizer` role=separator·`.app-shell` 자식 위치, [2] styles.css `.app-shell{position:relative}`·`.sidebar-resizer{left:var(--sidebar-w);cursor:ew-resize}`·모바일 display:none, [3] init `setupSidebarResize()`·resize 리스너 `_applySidebarWidth()`, [4a] 핸들 1회 배선·멱등, [4b] drag→`--sidebar-w`=clientX·`is-sidebar-resizing`·mouseup localStorage 영속, [4c] clamp 하한 180/상한 512@1024·`_sidebarMaxW`, [4d] 저장값 복원·모바일 override 제거, [4e] 더블클릭 reset) + make test 컨테이너 **전체 회귀 0**(REAL_MAKE_EXIT=0, ruff clean). 백엔드 무변경. REV-20260616T022652-ai-claude-sidebar-resize [SKIPPED:frontend-ui-resize-no-backend-no-rbac].
  - **Environment: Windows-browser** (실제 Windows Chrome/148.0.7778.217 via `bin/win-browser.py` 무권한 relay `bridge_mode: relay`, endpoint `http://172.28.64.1:9223`, https://localhost:18080, self-signed ignore). WSL headless 아닌 실제 Windows 화면.
  - **Runner: AI** (launch → 로그인(bootstrap_admin) → 사이드바 노출 → MouseEvent 디스패치 + computed 실측).
  - **PB-0008 PASS (배포본 main `6f1242b`, healthz git_commit 일치, `?v=20260616-sidebar-resize`, innerWidth 1249)**: 핸들 `#sidebarResizer` computed `display:block·cursor:ew-resize·position:absolute·width:8px·visible:true`(hit-test 가능). **드래그 실측(실 레이아웃 reflow — jsdom 미검출 영역)**: before `--sidebar-w 252px / sidebarW 252 / chatLeft 252` → 드래그 252→380 `var 380px / sidebarW 380 / chatLeft 380 / localStorage "380"`(사이드바 실제 확장 + chat-column 우측 reflow). **clamp**: 좌측 드래그(clientX 50)→`180px`(하한), 우측 드래그(clientX 99999)→`624px`(=min(640, floor(1249×0.5))=624 정확 일치). **영속**: 340px 드래그 후 페이지 reload → `--sidebar-w 340px / sidebarW 340 / localStorage "340"`(`_applySidebarWidth` 복원). **reset**: 핸들 더블클릭 → `252px`(기본)·`localStorage` null. evidence `artifacts/pb0008-sidebar-resize/sidebar-resized-340.png`(확장된 사이드바·대화목록·하단 프로필·chat-column reflow 육안). REV-20260616T024150-ai-claude-sidebar-resize-pb0008 [SKIPPED:docs-only-pb0008-evidence].
- 2026-06-15 (TASK-0277b 후속 핫픽스 — 보관 대화 row ellipsis 실작동 수정):
  - **Environment: Windows-browser** (실제 Windows Chrome/148.0.7778.217 via `bin/win-browser.py` 무권한 relay `bridge_mode: relay`, endpoint `http://172.28.64.1:9223`, https://localhost:18080, self-signed ignore). WSL headless 아닌 실제 Windows 화면.
  - **Runner: AI** (launch → /admin(세션 인증됨) → 보관 대화 탭 클릭 → computed layout 실측).
  - **PB-0008 적발 (TASK-0277 배포본 main `61e0151`, `?v=...task0277-archives-ui-align`)**: [문제1] `paneNotePresent:false`·header↔filter gap 16px(밀도 정합 PASS). [문제2] **줄바꿈 차단은 PASS**(긴 문자열 주입 시 rowH 56px 고정) **이나 ellipsis 미작동**(line getBoundingClientRect 2858px, topic scrollW===clientW===2714 → clipped:false). 원인 진단: `.admin-archive-row` computed `align-items:center`(`.admin-list-row` grid 상속) → 줄이 row 폭으로 stretch 안 됨.
  - **수정 라이브 실험 검증**: `r.style.alignItems='stretch'` 적용 시 line 2858→308px, topic clientW 164·scrollW 2714 → **clipped:true(ellipsis 작동)**, rowH 56 유지(2줄 고정). → `styles.css` 에 반영.
  - **재배포 후 PB-0008 재검증 PASS (main `d6123d3` #252, web 재빌드, 서빙 `?v=20260615-task0277b-archive-row-ellipsis`)**: 실 Chrome/148 relay, /admin(세션 인증) → 보관 대화 탭 → 긴 문자열(×40 반복) 주입 후 computed 실측 — `rowAlignItems:stretch`·`paneNotePresent:false`·`lineCount:2`·`rowH 56→56 heightStable:true`(2줄 고정·미줄바꿈)·`line0W 308`(row 폭 330 내 갇힘, 팽창 해소)·**topic `clientW 164 < scrollW 2586 → clipped:true`(nowrap+ellipsis 발동)**·owner `132<1627 clipped:true`·by `168<2066 clipped:true`. 즉 [문제1] 안내 우측 이동(밀도 정합) + [문제2] 2줄 고정·`…` 절단 모두 실 브라우저 PASS. evidence: `artifacts/pb0008-task0277/{01_archive_long_ellipsis,02_archive_clean_density}.png`(긴 topic·소유자·보관자 `…` 절단 + 우측 빈 상태 안내 표면화 육안 확인).
  - **Environment: CLI** (정적 + jsdom). node --check + CSS brace(1210=1210) + **jsdom 26 PASS**(0277 25건 + `.admin-archive-row align-items:stretch` 계약 1건) + make test 컨테이너 **전체 회귀 0**(MAKE_EXIT=0). REV-20260615-0283 [SKIPPED:frontend-ui-consistency-no-backend].
- 2026-06-15 (TASK-0277 보관 대화 탭 UI 정합 다듬기 — 안내 밀도 정합 + row 2줄 고정·ellipsis):
  - **Environment: CLI** (정적 + jsdom). node --check admin.js PASS + CSS brace 균형(1207=1207) + **jsdom 25 PASS**(`tests/verify_archive_tab_ui.mjs` — admin-pane-note 0건·styles.css 규칙 제거·header↔filter `<p>` 없음·빈 상태 안내 carry(static+JS)·긴/짧은 row 2줄 고정·1줄 topic+ts/2줄 owner+by·flex-wrap 제거·topic/owner/by nowrap+ellipsis+overflow+min-width:0) + make test 컨테이너 **전체 회귀 0**(백엔드 무변경, MAKE_EXIT=0, ruff clean). REV-20260615-0281 [SKIPPED:frontend-ui-consistency-no-backend].
  - **Residual: Windows-browser** — 배포(deploy_scope: included) 후 PB-0008(보관 대화 탭 진입 → 짧은/긴 topic·긴 username 혼재 시 2줄 고정·미줄바꿈·ellipsis + 안내 우측 표면화) 기록 예정.

- 2026-06-15 (TASK-20260615T182907-product-list-row-icon-layout-fix 제품 관리 목록 행 UI 뒤틀림 핫픽스 — **PB-0008 Windows-browser 재검증 PASS**):
  - **Environment: Windows-browser** (실제 Windows Chrome/148.0.7778.217 via `bin/win-browser.py` 무권한 relay `bridge_mode: relay`, https://localhost:18080, self-signed ignore).
  - **배포:** 핫픽스 머지본 → web 재배포. 서빙 자산 admin.js 재빌드(`?v=20260615-product-icon-chip-list` 유지).
  - **검증 내용:** 제품 관리 목록 8행이 `.admin-list-row` 3열 grid(`auto 1fr auto`)로 정렬 복원 — avatar(원형 Identicon)·`(약어) 명칭`·sub·분석률 배지가 행마다 어긋남 없이 정합. row 높이 균일, 텍스트 위치 정상(뒤틀림 해소). 수정 전 대비(42_admin_list_icons.png) 행 정렬 어긋남이 사라짐.
  - **Evidence:** `artifacts/pb0008-profile-icon/50_admin_list_fixed.png`.
  - **Pass/Fail: PASS** (목록 행 정렬·아이콘·텍스트 위치 정상). CHECK#13 충족.

- 2026-06-15 (TASK-20260615T180923-product-icon-chip-list 제품 프로필 아이콘을 대화창 chip + 제품 관리 목록 행에 표시 — **PB-0008 Windows-browser 완료 게이트, 인증 후 시각검증 PASS**):
  - **Environment: Windows-browser** (실제 Windows Chrome/148.0.7778.217 via `bin/win-browser.py` 무권한 userspace relay `bridge_mode: relay`, endpoint `http://172.28.64.1:9223`, https://localhost:18080, self-signed ignore). WSL headless 아닌 실제 Windows 화면.
  - **Runner: AI** (launch → `/api/auth/login`(bootstrap_admin) → 대화창 chip 제품 선택 eval + 관리 콘솔 `/admin` 제품 탭 목록 행 eval + screenshot)
  - **배포:** main `aea4d15`(PR #249 squash) → `sudo docker compose build web && up -d --no-deps web`(repo-web-1 Up healthy, HTTPS /healthz 200). 서빙 자산 `?v=20260615-product-icon-chip-list` — app.js `productChipIcon` 1 hit, admin.js `applyAvatar(avatar, { url: p.icon_url` 1 hit.
  - **검증 내용 (인증 후 실제 화면):**
    - **① 대화창 chip 아이콘 — PASS:** pinned 제품(GZ_QA_KR) 선택 시 chip 에 `#productChipIcon` 표시(`chipIconHidden:false`, `chipIconKind:"identicon"`). 확대 캡처(41_chip_zoom.png): [🔴 빨강 dot(unstable) → 원형 Identicon(주황 대칭) → `GZ_QA_KR` → 펼침 화살표] 순서. dot conn 색·compact label 무회귀.
    - **② 제품 관리 목록 행 아이콘 — PASS(아이콘 표시), 행 레이아웃 뒤틀림은 후속 핫픽스(182907):** 8개 행 **전부** `avatarKind:"identicon"` — `(KR) 킹스레이드`(파란 십자가)·`(KR_QA)`·`(MV)`(분홍)·`(GZ_KR)`·`(DK)`(빨강 체크)·`(FH)`(노랑)·`(GZ_QA_KR)`(주황) 각 고유 Identicon + `(약어) 명칭` + 분석률 배지. (단 이 Run 은 행 grid 뒤틀림을 놓침 — 사용자 보고 후 TASK-...-182907 로 수정·재검증.)
    - **③ 정합 — PASS:** 같은 제품(KR)이 대화창 chip·드롭업·관리 상세·관리 목록 행에서 **동일 파란 십자가 Identicon**, GZ_QA_KR 이 chip·목록 행에서 **동일 주황 Identicon**(동일 `identiconSvg(product_key)` 규칙 교차 확인).
  - **Evidence:** `artifacts/pb0008-profile-icon/41_chip_zoom.png`(대화창 chip 확대 — dot+Identicon+product_key), `42_admin_list_icons.png`(제품 관리 목록 8행 전부 Identicon + `(약어) 명칭` + 분석률), `40_chip_pinned_icon.png`(chip 전체 화면).
  - **Pass/Fail: PASS(아이콘·정합), 행 레이아웃은 후속 핫픽스 PASS** (① chip 아이콘 + ② 목록 행 아이콘 + ③ 제품별 동일 Identicon 정합 실제 Windows 화면 확인). CHECK#13(PB-0008 Windows-browser) **충족**. (auto 모드 chip 아이콘 hidden 은 jsdom 14/14 의 (c) 케이스로 검증 — 라이브 auto 전환은 기존 드롭업 동작이라 본 cycle 범위 밖.)
- 2026-06-15 (TASK-20260615T172210-profile-icon-consistency 제품 프로필 아이콘 정합화 + 대화 드롭업 레이아웃·너비 + 명칭 표기 순서 — **PB-0008 Windows-browser 완료 게이트, 인증 후 시각검증 PASS**):
  - **Environment: Windows-browser** (실제 Windows Chrome/148.0.7778.217 via `bin/win-browser.py` 무권한 userspace relay `bridge_mode: relay`, endpoint `http://172.28.64.1:9223`, https://localhost:18080, self-signed ignore). WSL headless 아닌 실제 Windows 화면.
  - **Runner: AI** (launch → `/api/auth/login`(bootstrap_admin) → 대화 드롭업 eval 구조검증 + 관리 콘솔 `/admin` 제품 탭 eval + screenshot)
  - **Scenario:** `unit/feature-0003-agent-web-ui/tests/win-browser-profile-icon.scenario.json` (대화 드롭업) + `win-browser-profile-icon-admin.scenario.json` (관리 콘솔) + 직접 eval 보강.
  - **배포:** main `bb1a991`(PR #246 squash) → `sudo docker compose build web && up -d --no-deps web`(repo-web-1 Up healthy, HTTPS /healthz 200). 서빙 자산 `?v=20260615-profile-icon-consistency` — admin.js `identiconSvg`/`applyAvatar` 2 hit, app.js 명칭 `(약어) 명칭` 4 hit, styles.css `product-dropup-item-icon` 18px·`max-width: min(420px, 92vw)`.
  - **검증 내용 (인증 후 실제 화면):**
    - **① 대화 드롭업 항목 순서 — PASS:** 8개 pinned 제품 **전부** 항목 자식 순서 `[product-dropup-item-dot → product-dropup-item-icon → product-dropup-item-label → product-dropup-item-ds → check]` (eval `firstChildOrder` 단언). 사용자 요청 [네트워크 상태 배지 → 프로필 아이콘 → 명칭 → 데이터소스] 와 정확 일치.
    - **② 프로필 아이콘 Identicon — PASS:** 8개 제품 모두 `iconKind:"identicon"`(이미지 미설정 → 결정론적 Identicon SVG 폴백). auto 항목은 아이콘 없이 dot 만. **작업화면 프로필(applyAvatar/identiconSvg)과 동일 규칙** — 같은 제품(KR) 이 관리 콘솔·대화 드롭업에서 **동일 파란 십자가 Identicon** 렌더(스크린샷 교차 확인).
    - **③ 명칭 표기 `(약어) 명칭` — PASS:** 드롭업 `(KR) 킹스레이드 - 로컬`·`(KR_QA) 킹스레이드 - 국내 QA`·`(MV)...`·`(GZ_KR)...`·`(DK)...`·`(FH)...`, 관리 콘솔 제품 목록·상세 `(KR) 킹스레이드 - 로컬` — 전부 `labelStartsWithParen:true`/`detailStartsParen:true`.
    - **④ 드롭업 메뉴 너비 — PASS:** `menuMaxWidth:"420px"`, 렌더 너비 358px, 첫 항목 `firstLabelTruncated:false`(명칭 안 잘림). 이전 280px 잘림 해소.
    - **⑤ 관리 콘솔 제품 상세 아이콘 — PASS:** `(KR) 킹스레이드` 상세 헤더 `avatarKind:"identicon"`(이니셜 텍스트 아님) + 아이콘 변경 컨트롤 보존.
  - **Evidence:** `artifacts/pb0008-profile-icon/35_dropup_large.png`(대화 드롭업 확대 — dot+Identicon+`(약어) 명칭`+datasource 4요소 순서, KR_QA unstable 빨강 dot), `20_admin_detail_identicon.png`(관리 콘솔 제품 상세 — `(KR) 킹스레이드` Identicon + `(약어) 명칭` 목록 8개), `01_dropup_layout.png`/`33_dropup_open.png`(드롭업 열린 전체 화면).
  - **Pass/Fail: PASS** (① 항목 순서 + ② Identicon 정합 + ③ 명칭 순서 + ④ 너비 + ⑤ 관리 콘솔 아이콘 전부 실제 Windows 화면 확인). CHECK#13(PB-0008 Windows-browser) **충족**.

- 2026-06-15 (TASK-0276 관리 콘솔 "보관 대화" 탭 UI 정합화, **Minor §12.3** frontend-only):
  - **Environment: CLI** (정적 + jsdom). node --check admin.js PASS + CSS brace(1206=1206). **jsdom 13 PASS**(빈 목록 empty·row 2개 audits 동형 클래스·count·row 클릭→selectedId+상세 렌더+is-selected·미존재 선택 empty·topic XSS escape 목록/상세·truncated scope 안내) + make test 컨테이너 **전체 회귀 0**(백엔드 무변경). 정적자산 web 임시 적용 후 admin.js 새 함수 14건·admin.html list-detail 마크업 12건 서빙 확인. REV-20260615-0277 [SKIPPED:frontend-ui-consistency-no-backend].
  - **(잔여) PB-0008 Windows-browser**: web 재배포 후 보관 대화 탭 진입 → list-detail 렌더 + row 클릭 시 우측 상세 패널 → 결과 추가 예정. (배포 전 CHECK#13 WARN.)
- 2026-06-15 (TASK-0275 assistant 첨부 수정→새 버전 materialize + 버전 관리, **Critical §12.3**):
  - **Environment: CLI** (컨테이너 make test). 신규 `test_attachment_versioning.py` **11 PASS**(파서2·materialize 가드6·직렬화1·파일명1·목록필터1) + make test 컨테이너 **전체 회귀 0** + ruff clean + py_compile + node --check app.js + CSS brace(1194=1194). 테스트 sys.modules 오염(가짜 web 모듈) → `monkeypatch.setitem` 자동 원복으로 해소(share_redaction 등 web.app import 테스트와 공존 확인).
  - **Environment: live-roundtrip** (임시 web 적용 + 라이브 MySQL ALTER + MinIO). materialize(source 272 text → 새 버전 273 v2 role=assistant root=272)·MinIO 바이트 70B sha256 일치·원본 272 SupersededAt 마킹·목록(SupersededAt IS NULL)에 273만 노출·`/versions` 체인 [272 v1 superseded, 273 v2 active]. **보안 가드 라이브 확인**: cross-account(999)/cross-conversation 거부(로그 mismatch), traversal `../../../etc/passwd.exe` → OriginalFilename `.._.._.._etc_passwd.sql`(확장자 .sql 고정)·object_key `../` 없음, 같은 (root,version) 2차 INSERT IntegrityError 거부(UNIQUE). 검증 데이터 정리(273 제거·272 원복).
  - **outside-voice 보안 리뷰** REV-20260615-0276 [SUBAGENT]: 외부 침투형 BLOCKER 0, 데이터 정합 BLOCKER1(원자성)+MAJOR2(UNIQUE race·audit)+MINOR1(확장자) 수정 흡수 → SHIP.
  - **(잔여) PB-0008 Windows-browser**: web 재배포 후 첨부 버전 배지(`v{n} · AI 수정`)·`edited_attachments` 토스트·`/versions` 시각검증 → 결과 추가 예정. (배포 전 CHECK#13 WARN.)
- 2026-06-15 (TASK-0272 대화 화면 프로필 첫 진입 시 "프롬프트 > 제품 범위" 비어있는 버그, **Minor §12.3** frontend-only):
  - **Environment: CLI** (정적 검증): `node --check app.js` PASS. 코드 정합 — `switchProfileTab(tab)` 에 탭별 lazy 디스패치(prompt→`initAccountPromptEditor()` / usage→`loadProfileUsage()`) 추가, `initialize()` 탭 클릭 리스너의 중복 디스패치 제거(단일 진입점화). index.html app.js 캐시버스터 `?v=20260615-task0272-prompt-scope`. REV-20260615-0272 [SKIPPED:panel].
  - **(잔여) PB-0008 Windows-browser**: web 재배포(deploy_scope: included) 후 프로필 드로어 첫 진입(새로고침 후)에서 제품 범위 셀렉트가 즉시 채워짐을 실제 Windows 화면에서 실측 → 결과를 본 항목에 추가 예정. (배포 전이라 본 commit 의 CHECK#13 은 WARN — 배포 후 충족 기록.)
- 2026-06-15 (TASK-0270 계정 override 게이트 = 허용/상속(허용) 펼침, **Minor §12.3** frontend-only):
  - **Environment: CLI** (컨테이너 make test). perm test **16 PASS**(신규 V7: 상속(허용)→펼침·상속(거부)→숨김·명시 거부 우선·허용 무관 펼침) + make test 컨테이너 회귀 0(exit=0) + node --check + **jsdom 8/8**(상속허용·상속거부·거부우선·허용·운영 list.own 상속허용). REV-20260615-0270 [SKIPPED:ui-disclosure-gate-no-enforcement].
  - **Environment: Windows-browser** (실제 Windows Chrome/148 via `bin/win-browser.py` relay `bridge_mode: relay`, https://localhost:18080, self-signed ignore). 라이브 배포(main `8953dc1`, web Up healthy, 서빙 admin.js `inheritedGrants`, 캐시버스터 `?v=20260615-task0270-inherit-gate`) 후 카탈로그 주입 + computed display 실측. 스크린샷 `artifacts/pb0008-task0270/step_04(override 상속허용 게이트).png`.
  - **Runner: AI. 결과: PASS.** 계정 override 편집기에서 전 항목 "상속", 역할 baseline = {console.access, account.read, conversation.list.own} 주입 → ① 계정 그룹 등장, `계정 조회`(account.read) 아래 `계정 수정/삭제/활성화/비활성화/역할 부여/override 관리` 트리 펼침(account.read computed `flex`·account.update `flex` — 상속(허용) 게이트). ② `대화 요청 실행` `flex`(conversation.list.own 상속허용). ③ `전체 대화 내용 조회` computed `none`(conversation.list.any 역할 미부여 = 상속(거부)). 사용자 요구("부여된 역할 중 '허용' 및 '상속(허용)' 일 경우에 펼쳐지도록") 라이브 충족. 콘솔 에러 0. CHECK#13 충족.
- 2026-06-15 (TASK-0269 운영 권한 대화 그룹 분리 + "목록 조회" 게이트 트리, **Minor §12.3** frontend-only):
  - **Environment: CLI** (컨테이너 make test). perm test **15 PASS**(M4 list 게이트/V2 운영 루트/T2 그룹 분리+게이트 중첩) + make test 컨테이너 회귀 0(백엔드 RBAC 무회귀) + node --check(admin.js·app.js) + **jsdom 20/20**(2그룹·라벨·게이트·트리·누락0). outside-voice REV-20260615-0269 [SUBAGENT:rbac-adversarial] **SHIP**(enforcement byte-identical).
  - **Environment: Windows-browser** (실제 Windows Chrome/148 via `bin/win-browser.py` relay, https://localhost:18080). 라이브 배포(main `73755e9`, web Up healthy, 서빙 admin.js `내 대화 권한`/`전체 대화 권한` 라벨, 캐시버스터 `?v=20260615-task0269-conv-split`) 후. 스크린샷 `artifacts/pb0008-task0269/step_04(2그룹 트리).png`.
  - **Runner: AI. 결과: PASS.** 운영 권한이 **내 대화 권한**(13)/**전체 대화 권한**(10) 2그룹 분리, 각 그룹 "대화 생성·목록 조회(기반) > 동작" 트리. `내 대화 목록 조회`(게이트) 체크 → 내 동작(대화 요청 실행·내용 조회·파일 조회·제목 변경·삭제·중단 등) computed `flex` 펼침, 전체 대화 동작 computed `none`(전체 목록 조회 OFF). 사용자 요구 라이브 충족. CHECK#13 충족.
- 2026-06-15 (TASK-0267 권한 grid 트리(tree) UI 재구성 — 2열 grid 뒤틀림 해소 + "더 보기 부여됨" 빨강 가시성, **Minor §12.3** frontend-only):
  - **Environment: CLI** (컨테이너 make test). `test_permission_dependency_map.py` **15 PASS**(기존 11 + 신규 T1~T4: 트리 정렬 부모-자식 순서·depth 정합·own→any 중첩·account.read 루트·grid-list 단일열 CSS 계약) + make test 컨테이너 **전체 회귀 0**(merged tree, exit=0) + node --check + CSS brace(1167) + **jsdom 실 DOM 14/14**(트리 순서·depth·누락0·숨김 시 부모 DOM 앞 유지). REV-20260615-0267 [SKIPPED:ui-tree-layout-no-logic-change](disclosure/저장 로직 byte-identical, 렌더 순서+레이아웃 전용).
  - **Environment: Windows-browser** (실제 Windows Chrome/148.0.7778.217 via `bin/win-browser.py` 무권한 relay `bridge_mode: relay` @ http://172.28.64.1:9223, https://localhost:18080, self-signed ignore). WSL headless 아닌 실제 Windows 화면 검증. 라이브 배포(main `f6ccb7b`, web `Up healthy`, 서빙 styles.css `.permission-grid-list{flex-direction:column}` + `[data-perm-depth]` + admin.js `_orderItemsAsTree`, 캐시버스터 `?v=20260615-perm-tree-ui`) 후. 배포 admin.js `renderPermissionGrid` 에 카탈로그(47) 주입해 실 grid 렌더 + computed style 실측. 스크린샷 `artifacts/pb0008-task0267/{step_04(manage 트리),step_01(operate 단일열)}.png`.
  - **Runner: AI. 결과: PASS.** **① 단일 열 트리(뒤틀림 해소)**: `.permission-grid-list` computed `display:flex`·`flex-direction:column`·`grid-template-columns:none`(2열 grid 아님) — 자식 row 숨김 시 가로 reflow 0. **② 트리 들여쓰기**: `관리 콘솔 접근`(부모, `data-perm-depth=0`·margin-left 0) 아래 `관리 콘솔 수정`/`LLM 사용량 조회`/`insight 분석 초기화`(자식, depth 1·**margin-left 24px** 들여쓰기·좌측 가이드/tick 연결선) 시각 확인. 운영 권한 `내 대화 내용 조회`(read.own depth0) ↔ `전체 대화 내용 조회`(read.any depth1·24px). **③ 운영 권한 빨강 가시성(이슈1 해소)**: conversation 그룹 read.any 부여+게이트OFF → computed `display:none`, "세부 권한 10개 더 보기 · 1개 부여됨" computed color **`rgb(180,35,31)`(빨강)**·`has-granted` — 2열 뒤틀림 제거로 빨강 badge 정상 가시. 사용자 두 보고(① 운영 권한 빨강 미가시 ② 항목 숨김 뒤틀림 → tree UI) 라이브 충족. 콘솔 에러 0. CHECK#13 **충족**.
- 2026-06-15 (TASK-0264 권한 disclosure 추가 단순화 — 게이트 미충족 시 부여 세부 권한도 더보기 뒤로 숨김(forceVisible 제거), **Minor §12.3** frontend-only):
  - **Environment: CLI** (컨테이너 make test). `test_permission_dependency_map.py` **11 PASS**(V1/V4/V5/V6 새 동작: 게이트 OFF 부여 항목 숨김 + 게이트 충족 시 도달; C1 unscoped CSS 계약) + make test 컨테이너 **전체 회귀 0**(merged tree, exit=0) + node --check + CSS brace(1133) + **jsdom 실 DOM 17/17**(부여 account.delete 게이트OFF 숨김·그룹 유지·"부여됨" 배지·더보기 클릭 도달·저장 누락0·override). outside-voice 적대 리뷰 REV-20260615-0264 [SUBAGENT:rbac-adversarial] **SHIP-WITH-FIXES**(안전 전부 refute; MINOR override-grid `[hidden]` unscope 흡수).
  - **Environment: Windows-browser** (실제 Windows Chrome/148.0.7778.217 via `bin/win-browser.py` 무권한 relay `bridge_mode: relay` @ http://172.28.64.1:9223, https://localhost:18080, self-signed ignore). WSL headless 아닌 실제 Windows 화면 검증. 라이브 배포(main `d35299e`, web `Up healthy`, 서빙 styles.css 에 unscoped `[data-perm-code][hidden]{display:none!important}` + `.permission-group-more.has-granted`, 캐시버스터 `?v=20260615-perm-collapse-granted`) 후. 배포 admin.js `renderPermissionGrid` 에 카탈로그(47) 주입해 실 grid 렌더 + computed display 실측. 시나리오 `/tmp/pb0264.json`, 스크린샷 `artifacts/pb0008-task0264/{step_04(checkbox),step_06(override)}.png`.
  - **Runner: AI. 결과: PASS.** **① 역할(checkbox) — account.delete 부여 + 게이트(계정 조회·관리 콘솔 접근) OFF**: 계정 그룹은 vanish 안 하고(`1/7 선택` 헤더 카운트) 권한 행은 **하나도 노출 안 됨** — 부여된 `account.delete` 도 computed **`display:none`**(이전 forceVisible 누출 버그 해소), "세부 권한 7개 더 보기 · 1개 부여됨"(`.has-granted` 빨강) 으로 도달성 표면화. **② 계정(override) — account.delete=거부 + 게이트 inherit**: container=`override-grid`, `account.delete` computed **`display:none`** — TASK-0258 의 `.permission-grid` 한정 `[hidden]` 강제가 override 편집기를 놓치던 갭을 컨테이너 무관 unscope 로 해소했음을 실증, 그룹 유지 + "부여됨" 배지. 사용자 요구("세부 권한 더 보기 클릭 전 항목 노출 → 최대한 단순화하여 숨김") 두 편집기 모두 라이브 충족. 콘솔 에러 0. CHECK#13(PB-0008 Windows-browser) **충족**.
- 2026-06-15 (TASK-0262 선택 제품 chip dot 네트워크 상태색 — TASK-0261 후속, **Minor §12.3** frontend-only):
  - **Environment: Windows-browser** (실제 Windows Chrome/148.0.7778.217 via `bin/win-browser.py` 무권한 relay `bridge_mode: relay` @ http://172.28.64.1:9223, https://localhost:18080, self-signed ignore). 라이브 배포(main `eb7be30`, healthz `git_commit=eb7be30`/status ok, 서빙 `?v=20260615-task0262-chip-conn-color`) 후. 시나리오 `tests/win-browser-task0262-chip-conn-color.scenario.json`, 스크린샷 `/tmp/win-browser-shots/task0262/{01_chip_unstable_p94,02_chip_healthy_p95}.png`.
  - **Runner: AI. 결과: PASS.** bootstrap_admin 세션 → composer 제품 chip(`#productChip`) 드롭업에서 제품 pin 후 `#productChipDot` 의 `getComputedStyle().backgroundColor` + class 실측. **선택 제품 94 킹스레이드 국내 QA(datasource `mysql-kr-an2-player`=unstable)**: dot class `composer-product-chip-dot--conn is-fail`, **bg rgb(220,38,38)=#dc2626 빨강**, chip aria-label "...· 데이터소스 연결 불안정". **선택 제품 95 건즈 국내 QA(`mysql-gz-qa-kr`=healthy)**: class `--conn is-ok`, **bg rgb(22,163,74)=#16a34a 초록**, aria "...· 데이터소스 연결됨". **auto(미선택)**: conn 클래스 제거됨, bg rgb(128,125,114) 중립(전이 reset 정상). 과거엔 선택(pinned) 제품이 상태 무관 파랑(`--primary`)이었음 → 상태색 반영 확인(사용자 요구 충족). 콘솔 0. CHECK#13(PB-0008) **충족**.
- 2026-06-15 (TASK-0257 권한 편집기 점진적 세분화 + TASK-0258 [hidden] CSS override 핫픽스, **Major/Minor §12.3** — frontend-only):
  - **Environment: CLI** (컨테이너 make test). 신규 `test_permission_dependency_map.py` **11 PASS**(맵 정합 M1~M4 + 가시성 불변식 V1~V6 + CSS 계약 C1) + make test 컨테이너 **전체 회귀 0**(merged tree, exit=0) + ruff clean + node --check + CSS brace(1125=1125). **jsdom 실 DOM 30/30**(마스터게이트 vanish·그룹 reveal·게이팅·orphan 칩·저장경로 안전·override no-vanish·더보기). outside-voice 적대 리뷰 REV-20260615-0257 [SUBAGENT:rbac-adversarial] **SHIP-WITH-FIXES→흡수**(부여 권한 미숨김·저장 누락 0 을 400k fuzz refute; MAJOR override trap 흡수).
  - **Environment: Windows-browser** (실제 Windows Chrome/148.0.7778.217 via `bin/win-browser.py` 무권한 relay `bridge_mode: relay` @ http://172.28.64.1:9223, https://localhost:18080, self-signed ignore). WSL headless 아닌 실제 Windows 화면 검증. 라이브 배포(web 재빌드 → `compose up --no-build`, web `Up healthy`, 서빙 admin.html 캐시버스터 `?v=20260615-perm-disclosure-hidefix`, 서빙 styles.css 에 `[data-perm-code][hidden]{display:none!important}` 1매치) 후. 배포된 admin.js `renderPermissionGrid` 에 카탈로그(47 권한) 주입해 실 grid 렌더 검증. 스크린샷 `artifacts/pb0008-task0257/{step_04_…(역할 collapsed),01_role_console_access_checked,…}.png` + `artifacts/pb0008-task0258/step_02_…(배포 CSS within-group 게이팅).png`.
  - **Runner: AI. 결과: PASS.** **① 역할(checkbox) 신규 미선택**: 관리 권한 section 이 "관리 콘솔" 그룹만 표시(계정/역할/감사/설정 그룹 `[hidden]` vanish, computed `display:none`), 운영 권한은 대화/제품 표시 — 마스터 게이트 OFF 단순화 시각 확인. **② "관리 콘솔 접근" 체크**: 계정/역할/감사/설정 그룹 등장. **③ 계정 그룹 펼침(배포 CSS, TASK-0258 핫픽스 검증)**: `계정 조회`(account.read)만 표시, 나머지 6개(`계정 수정/삭제/활성화/비활성화/역할 부여/override 관리`) **computed `display:none`**(visible=1), "세부 권한 6개 더 보기" 노출 — within-group 게이팅이 실브라우저에서 정상 동작(TASK-0257 의 `[hidden]` override 버그가 TASK-0258 로 해소됨). **④ 계정 override(select) 모드**: 계정/역할/감사 그룹 통째 vanish 안 함(account_group_display=block) + "더 보기" 도달 가능 — override trap 수정 확인. 사용자 두 예시("관리 콘솔 접근 체크→관리 권한 내부 표시", "계정 조회 체크→나머지 계정 권한 표시") 모두 라이브 충족. 콘솔 에러 0. CHECK#13(PB-0008 Windows-browser) **충족**. **교훈**: TASK-0257 의 `[hidden]` override 버그는 jsdom(CSS 캐스케이드 부재)이 못 잡고 PB-0008 실브라우저(computed display)만 검출 — 권한 grid 표시/숨김은 PB-0008 로 확인([[feedback_visual_verify_on_design_change]]·TASK-0236 교훈).
- 2026-06-15 (TASK-0255 insight 연결 탄력성 R2 — datasource 상세 '인사이트 스캔 상태' 행 = 연결 불안정 vs 정상 구분, **Major §12.3** cross-feature):
  - **Environment: Windows-browser** (실제 Windows Chrome/148.0.7778.217 via `bin/win-browser.py` 무권한 relay `bridge_mode: relay` @ http://172.28.64.1:9223, https://localhost:18080, self-signed ignore). WSL headless 아닌 실제 Windows 화면 검증. 라이브 배포(main `a410986`, healthz `git_commit=a410986`/status ok, web `Up healthy`, admin.js 캐시버스터 `?v=20260615-task0255-insight-health`) 후. 스크린샷 `/tmp/win-browser-shots/task0255/{01_unstable_ds_auth_detail,02_healthy_ds_gzqa_detail}.png`.
  - **Runner: AI. 결과: PASS.** bootstrap_admin 영속 세션. **① 엔드포인트(데이터)**: `GET /api/admin/datasources` 200, datasource 11개. `mysql-kr-an2-auth` → `conn_status=unstable` + `insight_health={status:unstable, scan_outcome:circuit_open, fail_count:11}`; `mysql-gz-qa-kr` → `conn_status=healthy` + `insight_health={status:healthy, scan_outcome:ok, fail_count:0}` — insight 관점 health 가 응답에 정상 첨부됨. **② UI(시각)**: /admin > 데이터소스 탭 > datasource 행 클릭 → 상세 "출처·보안" 섹션의 신규 **"인사이트 스캔 상태"** 행: 불안정 `mysql-kr-an2-auth` = **"⚠ 연결 불안정 (미커버 — 자동 재시도 대기)"**, 정상 `mysql-gz-qa-kr` = **"정상 (분석됨)"**. 운영자가 "연결 불안정 미커버" 를 권한 실패/정상과 **구분** 인지(사용자 R2 요구 충족). 자격증명/민감정보 미노출(host/port/status/errno-tag 만). 콘솔 에러 0. CHECK#13(PB-0008 Windows-browser) **충족**.
- 2026-06-15 (TASK-0254 제품 프롬프트 '자동 작성' 스트리밍 스크롤 stick-to-bottom, **Minor §12.3** — frontend-only admin.js):
  - **Environment: CLI** (컨테이너 make test + ruff + node --check). make test 컨테이너 **전체 회귀 0**(진행 100%·skip 2·F/E 0·make exit=0) + ruff clean + `node --check`(admin.js) PASS + 서버 `.strip()` 사실 확인(app.py:16519). outside-voice 적대 리뷰 REV-20260615-0254 [SUBAGENT:frontend-adversarial] **SHIP-WITH-FIXES→흡수**(LOW 1건 done strip 길이차 점프; 첫토큰/8px 임계/측정순서/비-오버플로 무회귀 전부 반박).
  - **Environment: Windows-browser** (실제 Windows Chrome/148.0.7778.217 via `bin/win-browser.py` 무권한 relay `bridge_mode: relay` @ http://172.28.64.1:9223, https://localhost:18080, self-signed ignore). WSL headless 아닌 실제 Windows 화면 검증. 라이브 배포(web 재빌드 → `compose up --no-build`, web `Up healthy`, healthz `git_commit=f8845cc` mysql_ok/pg_ok, 베이킹 admin.js `atBottom`×4·`TASK-0254`×2 + 서빙 admin.html 캐시버스터 `?v=20260615-task0254-prompt-stream-scroll`, HTTP 응답 admin.js 에 `atBottom` 포함 확인) 후. 스크린샷 `/tmp/win-browser-shots/task0254/{01_prompt_pane_after,02_prompt_textarea_top}.png`(= `artifacts/pb0008-task0254/`).
  - **Runner: AI. 결과: PASS.** bootstrap_admin 영속 세션 → /admin > 제품 (Products) > "킹스레이드 (KR)"(pid 1) 상세 > 제품 프롬프트 pane. **자동 계측(eval 기반, 토큰 갱신마다 scrollTop 샘플링)** — `자동 작성` 클릭 → SSE 스트리밍(최종 ~7.5k자) 진행 중 2단계 측정. **① HOLD(위로 스크롤 유지) — 결정적 실측**: clear(첫 토큰 `value=""`) 감지 후 새 스트리밍 내용이 오버플로(>200px, len>1200)된 시점에 `scrollTop=60`(위로) 1회 설정 → 이후 토큰 8개 샘플 **전부 `top=60` 고정**, 그동안 오버플로는 748→852px 로 계속 증가(구버그면 top 이 oflow 를 따라 최하단으로 튐). **위로 스크롤한 위치가 토큰 갱신에도 유지됨** 실증. **② FOLLOW(최하단 추종)**: 그 후 `scrollTop=scrollHeight`(하단) 설정 → 이후 토큰 **73개 샘플 전부 `dist(scrollHeight-scrollTop-clientHeight)=0`**(max=min=0), 내용이 1.5k→자라는 내내 정확히 하단 추종. **사용자 시나리오 실증**: 스트리밍 완료 후 textarea 를 상단으로 두면 "# 킹스레이드 DB 분석 어시스턴트 시스템 프롬프트…" 본문 상단이 그대로 보임(02 스크린샷 — 사용자 원요구 "작성 현황 텍스트 상단 보기" 충족). 콘솔 에러 0. CHECK#13(PB-0008 Windows-browser) **충족**.
- 2026-06-12 (TASK-0253 관리 콘솔 head-of-line blocking 2건 제거 — (A) datasource ↻ 새로고침 비블로킹 + (B) 제품 분석 완료율 제품별 병렬 갱신, **Minor §12.3** — frontend + async backend):
  - **Environment: CLI** (컨테이너 make test + ruff + node --check + py_compile). 신규 `test_datasource_test_nonblocking.py` + `test_insight_coverage_endpoint.py` **8 PASS**(로컬 + 컨테이너), make test 컨테이너 **전체 회귀 0**(진행점 619, F/E 0) + ruff clean + node --check(admin.js) + py_compile(app.py). outside-voice 적대 리뷰 **SHIP-WITH-FIXES→흡수**(MAJOR-2 N-fan-out 스레드풀 고갈→프론트 cap 4, MINOR-2 force in-flight dedup, MINOR-3 fake keyword-only; BLOCKER 0).
  - **Environment: Windows-browser** (실제 Windows Chrome/148.0.7778.217 via `bin/win-browser.py` 무권한 relay `bridge_mode: relay` @ http://172.28.64.1:9223, https://localhost:18080, self-signed ignore). WSL headless 아닌 실제 Windows 화면 검증. 라이브 배포(web/ask-worker/insight-worker 재빌드 → `compose up --no-build`, 전 컨테이너 `Up healthy`, web env `GIT_COMMIT=a7c09d7`, 베이킹 app.py:10587 `await asyncio.to_thread(_db.probe_datasource, …)` + admin.js `_COV_FETCH_MAX` ×3 + 캐시버스터 `?v=20260612-task0253-headofline` 확인) 후. 스크린샷 `/tmp/task0253-pb0008-{products-coverage,ds-refresh}.png`.
  - **Runner: AI. 결과: PASS.** bootstrap_admin 영속 세션 → /admin. **(A) datasource ↻ 비블로킹 — 결정적 실측**: 브라우저에서 11개 datasource `/api/admin/datasources/{key}/test` 동시 POST(Promise.all) wall-clock **847ms** ≈ 가장 느린 단건 845ms(ratio 1.0), 직렬 합산이면 6491ms = **약 7.7배 개선**(전부 status 200). 수정 전엔 `admin_test_datasource`(async)가 동기 `probe_datasource`(도달불가 시 8s 점유)를 직접 호출해 이벤트 루프 블로킹 → 동시 /test 직렬화. 이제 `asyncio.to_thread` 로 진짜 병렬. 제품 상세 > "+ 데이터소스 추가" 패널의 **↻ 새로고침 버튼 hit-test PASS**(62×27px visible + clickable), 클릭 후 배지 "확인 중" stuck **0**, "정상" 표면화. **(B) 제품 완료율 제품별 병렬 갱신**: fetch 후킹으로 강제 새로고침 시 coverage 호출이 **제품별 단건 7건**(`?product_id={1,94,7,8,91,92,95}&refresh=1`, first→last spread 203ms = cap 4 두 배치) — 전역 1회 fetch 아님. 좌측 목록 완료율 배지 7개 모두 개별 settle(`분석 100%`×6 + `분석 56.8%`), "측정 중" stuck **0**(TASK-0249 에서 STATUS flag 로 남긴 일괄대기 초기렌더 고착 해소). **콘솔 에러 0**. CHECK#13(PB-0008 Windows-browser) **충족**.
- 2026-06-12 (TASK-0248 관리 콘솔 제품 삭제 시 참조 대화 차단(blocked) 전환, **Major §12.3** — 파괴적 삭제 + 접근 차단 + cross-store):
  - **Environment: CLI** (컨테이너 pytest + ruff + node --check + py_compile + CSS brace). 신규 `test_product_delete_block_conv.py` **7 PASS**(D1 삭제허용+차단·D2 참조0·D3 권한403·B1 block_info·B2 block UPDATE SQL/rowcount·A1 ask 403) + make test 컨테이너 **전체 회귀 0**(600 passed/2 skip) + ruff clean + node --check(app.js·admin.js) + py_compile(app.py·alembic 0005) + CSS brace 1108/1108.
  - **outside-voice 적대적 2-agent 리뷰**: REV-20260612-0248 [SUBAGENT:security+correctness-adversarial] SHIP-WITH-FIXES→흡수→**SHIP**. 백엔드 BLOCKER 0(probe ①SQL바인딩 ②오차단 ③cross-store fail-closed ④conn누수 ⑤멱등 ⑦split-brain PASS; ⑥PG컬럼부재500=migrate-first 배포계약 흡수). 프런트 SHIP(우회 송신 경로 0, 공유/이력/fork 충족). M-2(admin.js 혼입)=stale base 오탐.
  - **라이브 검증(서빙 web 컨테이너 코드 경로, 실데이터 무오염)**: PASS. (1) migrate 0005 적용 → PG `core_conversations.blocked_at`/`blocked_reason` 컬럼 psql 실측 존재. (2) 라이브 `_block_conversations_for_product(99999)`=1건 차단, `_conversation_block_info`(pinned)=True·(auto NULL)=**False**(오차단 방지 probe②), 재호출=0(멱등). (3) end-to-end `admin_delete_product(96)`(테스트 제품) → status **200** + `blocked_conversations:2`(과거 400 거부 제거 확인), WebProducts 96 + 동적권한 cascade 삭제, 검증 대화 2건 blocked=t. (4) 정상 대화(product 91) blocked=False(무영향 probe⑤). 검증 후 임시 데이터 전량 정리 → 라이브 차단행 0 복원.
  - **Environment: Windows-browser** (실제 Windows Chrome/148.0.7778.217 via `bin/win-browser.py` 무권한 relay `bridge_mode: relay` @ http://172.28.64.1:9223, https://localhost:18080, self-signed ignore). WSL headless 아닌 실제 Windows 화면 검증. 라이브 배포(make migrate 0005 → web 재빌드/재기동, healthz `status:ok`·mysql_ok/pg_ok·insight_age 8s, 서빙 admin.js `?v=20260612-task0248-blocked-conv` + confirm 문구 "차단' 상태로 전환됩니다") 후. 스크린샷 `/tmp/pb0008-task0248-{admin-product-delete,blocked-conv}.png`.
  - **Runner: AI. 결과: PASS.** 영속 admin 세션. **(A) admin 제품 삭제** — /admin > 제품 탭(7개 렌더) > "킹스레이드 (KR)" 선택 → 상세 패널 + 하단 **"삭제" 버튼 hit-test PASS**(좌표 643,706 에서 `elementFromPoint`=버튼 자신). 서빙 admin.js confirm 문구 = TASK-0248 신규("이 제품을 참조하는 대화가 있으면 더 이상 진행할 수 없는 '차단' 상태로 전환됩니다 ... 되돌릴 수 없습니다"). **(B) 차단 대화 UI**(검증용 실대화 1건 일시 차단→검증→원복) — (1) **사이드바**: `.conv-item.is-blocked` 클래스 + "차단" 배지(visible) + 제목 `line-through`. (2) **헤더**: 부제 = "🚫 차단됨 (참조 제품 삭제) · 최근 갱신 ... · 메시지 6 · 소...". (3) **composer**: 입력창 `disabled=true` + 전송버튼 `aria-disabled=true` + 제목 "차단된 대화" + 안내 "참조 제품이 삭제되어 더 이상 대화를 진행할 수 없습니다. 이력 열람·공유는 가능하며, 복제(사본 만들기)로 새 대화에서 이어갈 수 있습니다." (4) **요구사항 실증**: fork(복제) 버튼·공유 버튼 **노출 유지**(차단 대화도 가능), 메시지 **58개 렌더**(이력 열람 가능 — 차단이 렌더 미차단). 검증 후 차단 원복(라이브 blocked 행 0). CHECK#13(PB-0008 Windows-browser) **충족**.
- 2026-06-12 (TASK-0249 제품 insight 완료율 멀티 datasource(1:N) + 대소문자 매칭 수정, **Minor §12.3**):
  - **Environment: CLI** (make test 컨테이너 pytest + ruff + py_compile). 신규 `test_insight_coverage.py` 5(C1 멀티 datasource per-DB 집계 0/0 회귀차단·C2 단일 datasource 레거시 무회귀·C3 mixed-case 매칭·C4 한 datasource 부분측정·C5 measurable=False) PASS + 전체 회귀 0(rebase 후 598 passed/2 skipped, origin/main TASK-0250 이 test_db_circuit_breaker→test_conn_health 교체) + ruff clean. 적대적 correctness 리뷰 **SHIP**(REV-20260612-0249, CONCERN 1[동명 DB 이중카운트]→seen_dbs 가드 흡수).
  - **Environment: Windows-browser** (실제 Windows Chrome/148.0.7778.217 via `bin/win-browser.py` 무권한 relay `bridge_mode: relay` @ http://172.28.64.1:9223, https://localhost:18080, self-signed ignore). WSL headless 아닌 실제 Windows 화면 검증. 라이브 배포(web 재빌드 + healthz `git_commit=12f5c5e`, mysql_ok/pg_ok, 베이킹 `seen_dbs`·`LOWER(TABLE_SCHEMA)` 확인) 후. 시나리오 `tests/win-browser-task0249-coverage.scenario.json`, 스크린샷 `/tmp/win-browser-shots/task0249/{10_ds_player_expanded,11_ds_common_dbcommon_111,12_ds_auth_expanded_dbauth_row}.png`.
  - **Runner: AI. 결과: PASS.** bootstrap_admin 세션 → /admin → 제품 탭 → "킹스레이드 - 국내 QA (KR_QA, id 94)" 선택. **핵심 검증 — 0/0 해소**: 요약 "insight 분석 완료율 **100%** · **571 / 571 객체 (DB + 테이블)**"(수정 전 7개 DB 전부 0/0). 7개 datasource accordion(player/auth/common/globalrank/gms/log/mail) 각각 펼쳐 그 datasource 의 DB 행 확인 — **dbgame(player) 99/99·마이크로바 100%·DB✓**, **dbcommon(common, 타 서버) 111/111·마이크로바 100%·DB✓**, **dbauth(auth, 타 서버) 10/10·마이크로바 100%·DB✓**(eval 측정 + 스크린샷). 각 DB 가 자기 datasource 좌표에서 실측됨(수정 전엔 단일 primary[player] 서버 질의로 타 서버 DB 0/0). 좌측 목록 배지 "분석 100%"(제품94 + 제품1[단일 datasource] 무회귀). 브라우저 API 일괄/단건 coverage 3회 반복 모두 7/7 conn·571/571(연결 안정 시) — 일시 연결 불안정 시에는 per-DB conn=False+note 로 graceful(0/0 일괄 오표기 아님, TASK-0247/0250 영역). CHECK#13(PB-0008 Windows-browser) **충족**. **관찰(별개 선존 이슈, 내 변경 무관)**: 페이지 첫 진입 시 프런트 일괄 coverage 로드의 초기 렌더 타이밍으로 좌측 목록·요약이 일시 "측정 중…" 고착 → 새로고침/재렌더 시 정상(`productCoverageLoading`/state 는 정상 false·7건 로드 확인). 백엔드 `_compute_product_insight_coverage`(본 TASK)와 무관한 프런트 `loadProductInsightCoverage` 초기 렌더 경로 — STATUS flag.
- 2026-06-12 (TASK-0246 "+ 데이터소스 추가" 드롭다운 항목 열 정렬 — 고정 열 폭 grid + 연결배지 좌측 정렬 정련, **Minor §12.3**):
  - **Environment: CLI** (CSS brace 균형 — CSS-only). CSS brace 1105/1105. REV-20260612-0246 [SKIPPED:trivial-grid-align] + REV-20260612-0247 [SKIPPED:trivial-css-1line](정련).
  - **Environment: Windows-browser** (실제 Windows Chrome/148.0.7778.217 via `bin/win-browser.py` 무권한 relay `bridge_mode: relay` @ http://172.28.64.1:9223, https://localhost:18080, self-signed ignore). 라이브 배포(web 재빌드 + healthz `git_commit=9c2db34`, mysql_ok/pg_ok, 서빙 `?v=20260612-ds-picker-colalign2` + `.admin-ds-conn { justify-self: start`) 후. 스크린샷 `/tmp/pb0008-ds-picker-colalign-final.png`(+ 중간 `/tmp/pb0008-ds-picker-status.png`).
  - **Runner: AI. 결과: PASS.** /admin > 제품 "킹스레이드(KR)" > "+ 데이터소스 추가" 드롭다운(datasource 5개) 항목별 컬럼 left 좌표를 win-browser eval 로 측정. **핵심 — 행별 left spread=0px**([[feedback_row_list_column_alignment]] 기준): name 5행 전부 x=677(spread 0), 엔진 pill 전부 x=874(spread 0), 좌표 전부 x=938(spread 0), 연결배지 전부 x=1070(spread 0). **수정 전(CHG-0246 측정)**: 엔진 x961/936/967·좌표 x1011/986/1018·배지 x1105/1080/1080 으로 들쭉날쭉 → grid 고정 열 폭(`auto minmax(0,1fr) 56px 124px 104px`) + 정련(연결배지 justify-self:end→start)으로 전 열 정렬. 긴 좌표(`kr-apne2-auth.masangs…`)는 ellipsis 흡수, 연결 상태(연결 실패/연결됨·ms) 정상 병행 표시. CHECK#13(PB-0008 Windows-browser) **충족**.
- 2026-06-12 (TASK-0244 관리 콘솔 제품 "+ 데이터소스 추가" 드롭다운 폰트 정합 + 연결 상태 표면화, **Major §12.3**):
  - **Environment: CLI** (`node --check admin.js` 정적 문법 검증 + CSS brace 균형 — frontend-only).
  - **Runner: AI.** `node --check ...admin.js` PASS, CSS brace 1103/1103. outside-voice subagent 디자인/정합 적대적 리뷰 **SHIP**(REV-20260612-0244, BLOCKER 0; `.admin-ds-picker-engine` ≡ `.ds-acc-engine` 토큰 동일·`.admin-db-picker-name` 재사용 확인, 동시성 nit 4-cap 세마포어 선반영).
  - **Environment: Windows-browser** (실제 Windows Chrome/148.0.7778.217 via `bin/win-browser.py` 무권한 relay `bridge_mode: relay` @ http://172.28.64.1:9223, https://localhost:18080, self-signed ignore). WSL headless 아닌 실제 Windows 화면 검증. 라이브 배포(web 재빌드 `sha256:6b05c6…` + healthz `git_commit=2b9205a` mysql_ok/pg_ok, 서빙 캐시버스터 `?v=20260612-ds-picker-status`·신규 심볼 5) 후 수행. 스크린샷 `/tmp/pb0008-ds-picker-status.png`.
  - **Runner: AI. 결과: PASS.** bootstrap_admin 영속 세션 → /admin → 제품 탭 → "킹스레이드 (KR)" 선택 → 데이터소스 accordion(2행) 하단 "+ 데이터소스 추가" 클릭. **검증 1 — 폰트/시각 정합**: 드롭다운 각 항목이 `[체크박스 · 이름(.admin-db-picker-name) · 엔진 pill(.admin-ds-picker-engine) · 좌표(.admin-ds-picker-coord) · 연결상태 배지(.admin-ds-conn)]` 구조로 렌더, 엔진 pill 이 위 accordion 행의 `[mssql]` pill 과 동일 시각(이전 `key — engine @ host:port` 단일 raw 문자열 이질감 해소). 헤더 "데이터소스 · 연결 상태" + ↻ 새로고침 표시. **검증 2 — 연결 상태**: 드롭다운 열림 시 lazy probe → 약 10초 후 settle: `mssql-qa-idc` ● **연결 실패**(is-fail, title="연결 실패: OperationalError" — 도달불가 IDC), `mssql_local` ● **연결됨 · 8.7ms**(is-ok), `mysql-local` ● **연결됨 · 8.9ms**(is-ok). ●점 + 한글 라벨 + 색(빨강/초록) 병행 — 색맹 비의존. ok/fail/elapsed_ms 3종 모두 정확 표면화. CHECK#13(PB-0008 Windows-browser) **충족**.
- 2026-06-12 (TASK-0235 새 대화 첫 메시지 작업 단계 진행상황 실시간 표시, **Major §12.3**):
  - **Environment: CLI** (`node --check` 정적 문법 검증 — frontend-only 변경, app.js).
  - **Runner: AI.** `node --check unit/feature-0003-agent-web-ui/src/static/app.js` PASS. 변경: `sendPrompt` 의 lazy_create early-cid 발급 일반화(첨부 유무 무관) + `earlyCidActivated` 플래그 도입(ask 실패 시 non-lazy 복구 경로 분기). 동시성 7 실패모드 적대적 리뷰(REV-20260612-0235 [SUBAGENT:newconv-progress-adversarial-concurrency]) — 중복폴링/빈status조기종료/sentinel가드/첨부회귀/bubble race 안전 + CONCERN 2(고아대화·빈대화 명시cid) 흡수.
  - **Environment: Windows-browser** (실제 Windows Chrome/148.0.7778.217 via `bin/win-browser.py` 무권한 relay `bridge_mode: relay` @ http://172.28.64.1:9223, https://localhost:18080, self-signed ignore). WSL headless 아닌 실제 Windows 화면 검증. 라이브 배포(web 재빌드 `sha256:9195e3…` + healthz 200 mysql_ok/pg_ok) 후 수행. 시나리오 `tests/win-browser-task0235-newconv-progress.scenario.json`, 스크린샷 `/tmp/win-browser-shots/task0235/{01_app_loaded..06_step_side_panel_open}.png`.
  - **Runner: AI. 결과: PASS (23/23 step ok).** bootstrap_admin 영속 세션 → 사이드바 "+ 새 대화" → `#promptInput` 에 "데이터베이스에서 테이블 목록을 보여주고 각 테이블의 행 수를 알려줘" 입력 → `#sendBtn` 전송. **핵심 검증 — 새 대화 첫 메시지에서 진행 단계 실시간 표시**: (1) 전송 직후(shot 03) 사이드바에 "새 대화" 항목 즉시 등재(녹색 활성 점) + "다른 대화에서 새 요청 가능" 안내 → **early-cid 발급 + optimistic entry + polling 시작 작동**(수정 전이라면 cid 부재로 항목·polling 모두 없음). (2) LLM 첫 step 생성 전(shot 04 5초·shot 05 11초)에는 "시작 중…" 유지(정상 — step 0 구간), step 도착 즉시(shot 06) pending bubble 이 **"SQL 실행 · INFORMATION_SCHEMA.TABLES에서 모든 테이블의 스키마명·테이블명·행 수 조회"** 로 전환 = 실시간 단계 표시 확인. (3) **"단계 보기" 클릭 → `#stepSidePanel` 우측 사이드바 열림**(`sidePanelOpen:true, sidePanelItems:1, badge:"1단계"`) + 단계 상세(SQL 실행 배지 / "근거" / 실 SQL 쿼리 / "결과 보기") 렌더 = 사용자 요청("각 단계 + 클릭 시 사이드바") 충족. (`window.state` 모듈 스코프라 eval activeConvId 는 null 노출됐으나 DOM 증거가 결정적.) CHECK#13(PB-0008 Windows-browser) **충족**.

- 2026-06-11 (TASK-0228 datasource SSRF 사설망 경계 env 토글 + 의도적 비활성화, **Major §12.3 보안 다운그레이드**):
  - **Environment: CLI** (컨테이너/로컬 pytest — `_ssrf_check_host`/`_ssrf_private_guard_enabled` 단위 + 통합 trace).
  - **Runner: AI.** 신규 `test_ssrf_private_guard_toggle.py` **31 PASS** (토글 ON/OFF·메타데이터 IPv4-mapped 차단·loopback/link-local 상시 차단·allowlist 공존·파싱·공인 IP 허용·빈 host 거부) + datasource 회귀(`test_datasource_registry.py`/`test_datasource_delete.py`) 회귀 0. 통합 trace 11 케이스(토글 OFF): RFC1918(10.200.50.80 등) 허용 + 메타데이터(bare/IPv4-mapped) 차단 + loopback/link-local 차단 ALL PASS. py_compile + node --check PASS.
  - **outside-voice 적대적 보안 리뷰**: REV-20260611-0228 [SUBAGENT:security] BLOCK→흡수→PASS (Finding A/B IPv4-mapped 메타데이터 우회 + Finding C loopback/link-local 과개방 수정).
  - **Environment: Windows-browser** — 배포(web 재기동, 토글=0) 후 PB-0008 으로 admin 콘솔 데이터소스 생성(host=`10.200.50.80`) 성공 + 안내 문구("사설망 IP 허용...") 확인 예정. (UI 변경 = 안내 텍스트 1줄 분기 — 백엔드 보안 로직이 핵심.)
- 2026-06-11 (TASK-0218 관리 콘솔 대시보드 CloudWatch 스타일 재구성 **PB-0008 Windows-browser 완료 게이트**):
  - **Environment: Windows-browser** (실제 Windows Chrome/148 via `bin/win-browser.py` 무권한 relay `bridge_mode: relay`, https://localhost:18080, self-signed ignore). WSL headless 아닌 실제 Windows 화면 검증. 라이브 배포(healthz `git_commit=c990107`, mysql/pg ok) 후. 스크린샷 `/tmp/win-browser-shots/task0218/{01_cloudwatch_dashboard,02_edit_drag}.png`.
  - **Runner: AI.** 시나리오: 영속 admin 세션 → `/admin` 대시보드 → 클린 로드 eval → 편집 모드 토글.
  - **결과: PASS.** (a) **toolbar** = "마지막 갱신 HH:MM:SS" + 집계기간 + 자동 새로고침(off/30/60s) + ↻ 새로고침 + 편집. (b) **주/보조 위계**: 계정 활성=6 녹색 大 + 보조(비활성/삭제/최근7일/전체) 小. (c) **sparkline 3 + 델타 배지 2**(▲▼% 의미별 색); 라이브 overview conversations primary={최근7일 45, spark[7], ▲2150% neutral}. (d) **Top-N 인라인 비율막대**. (e) **drill "열기 →" 6**(위젯→탭). (f) **편집 모드**: "완료" + ☑표시 + ↑↓(첫 위젯 ↑ disabled) + native drag + 저장/복원, drill 숨김. (g) **클린 로드 정확**: editBarHidden=true·editControls=0·drill 6. (h) RBAC 스코프·인젝션 차단(TASK-0210) 유지.
  - CHECK#13(PB-0008 Windows-browser) **충족**.
- 2026-06-11 (TASK-0210 관리 콘솔 대시보드 보강 — 카테고리별 위젯 그리드 + per-account 커스터마이즈 **PB-0008 Windows-browser 완료 게이트**):
  - **Environment: Windows-browser** (실제 Windows Chrome/148.0.7778.217 via `bin/win-browser.py` 무권한 relay `bridge_mode: relay` @ http://172.28.64.1:9223, https://localhost:18080, self-signed ignore). WSL headless 아닌 실제 Windows 화면 검증. 라이브 배포(healthz `git_commit=98f719d`, mysql/pg ok) 후 수행.
  - **Runner: AI.** 시나리오: 영속 admin 세션 → 관리 콘솔(`/admin`) → 대시보드("운영 현황") → 편집 모드 토글. 스크린샷 `/tmp/win-browser-shots/task0210/{01_dashboard,02_edit_mode}.png`.
  - **결과: PASS.** (a) **위젯 그리드 9개** 렌더: 계정·역할·제품·데이터소스·대화·활동·감사 활동·LLM 사용량·첨부 DB 권한·미저장 변경(2열 auto-fill). (b) **실데이터 집계**: 계정(활성 6/비활성 0/삭제 20/최근7일 3/전체 26 + 역할별 계정 Top-N), 역할(역할수 5 + 역할별 권한수 Admin 51/DBA 20/…), 제품(활성 4/바인딩 4), 데이터소스(활성 2 + 엔진별 mysql 1/mssql 1). metric chip 23·list row 27 렌더. (c) **가로 스크롤 없음**(`hScroll:false` — 레이아웃 정상). (d) **편집 모드**: "편집"→"완료" 토글, 편집 안내 바 + 기본값복원/저장, 위젯별 ☑표시 체크박스 9 + ↑↓ 이동 버튼 18(점선 테두리). (e) 집계기간 `최근 7일` dropdown. 라이브 API 검증(curl): overview 200 실데이터, prefs GET 기본(customized=false)→PUT(usage 숨김+미지키 `__evil__` **거부**)→GET(customized=true·usage=false 영속)→DB 행 영속, 검증 후 테스트 prefs 행 삭제(admin 기본값 복원).
  - CHECK#13(PB-0008 Windows-browser) **충족**.
- 2026-06-11 (TASK-0206 DB-단위 접근 모델 — 관리콘솔 제품상세 UI 재구성 **PB-0008 Windows-browser 완료 게이트**):
  - **Environment: Windows-browser** (실제 Windows Chrome/148.0.7778.217 via `bin/win-browser.py` 무권한 relay `bridge_mode: relay` @ http://172.28.64.1:9223, https://localhost:18080, self-signed ignore). WSL headless 아닌 실제 Windows 화면 검증. 라이브 배포(healthz `git_commit=cf1962e`, mysql/pg ok) 후 수행.
  - **Runner: AI.** 시나리오: bootstrap_admin 영속 세션 → 관리 콘솔(`#openAdminBtn`) → 제품 → MSSQL_DK(제품 90, winsql/dk_data_release) 상세.
  - **결과: PASS.** (a) **섹션 순서** = `데이터 소스 (datasource)` → `접근 가능 데이터베이스` → `제품 프롬프트` — 데이터소스 패널이 접근가능DB **위**로 이동(요청대로). (b) 데이터소스 dropdown `winsql — mssql @ 172.28.64.1:14330` + 연결테스트, **별도 '참조 DB' dropdown 폐지**(DB-단위 multi-select 로 흡수). (c) 접근가능DB = datasource-driven: 시스템 DB `master 고정·model 고정·msdb 고정`(고정칩) + 사용자 DB `dk_data_release ×`(제거가능) — 실 MSSQL 서버 DB 반영(tempdb 제외, 대소문자 보존). (d) hint 텍스트 = "데이터는 데이터 소스에 종속됩니다 — 선택하면 아래 접근 가능 데이터베이스 목록이 갱신됩니다". 스크린샷 `artifacts/task0206/03-product90-mssql.png`.
  - CHECK#13(PB-0008 Windows-browser) **충족**.
- 2026-06-10 (TASK-0184 LLM 사용량 계정 drill-down + 프로필 사용 내역 차트 + 내 활동기록 제거 — **PB-0008 Windows-browser 완료 게이트**):
  - **Environment: Windows-browser** (실제 Windows Chrome/148 via `bin/win-browser.py` 무권한 relay, https://localhost:18080, self-signed ignore). WSL headless 아닌 실제 Windows 화면 검증. 라이브 배포 검증(healthz `git_commit=0181301`, mysql/pg ok, 베이킹·자산 서빙 PASS) 후 수행.
  - **(C 활동기록 제거)** bootstrap_admin 프로필 → 탭 = [프롬프트, 사용 내역, 보안 및 계정], '내 활동 기록' 탭 부재(`hasActivityTab=false`). PASS.
  - **(B 프로필 사용내역)** '사용 내역' 탭 → 요약(요청 24·호출 57·총 토큰 515,443) + 일별 모델별 누적 막대(06-09/06-10 claude-haiku-4) + 모델별 비중 도넛(claude-haiku-4 100%) 정상 렌더. 스크린샷 `/tmp/0184_profile_usage.png`. PASS.
  - **(A 계정 drill-down)** 관리 콘솔 > LLM 사용량 → 역할별 차트 막대(역할 = (시스템)·Admin) 클릭 → 그 역할의 계정만 펼치는 drill 패널 노출(계정 검색 input + 10/20/50 page size select). (시스템) 클릭 시 "계정별 · (시스템) — 1개 계정" + 계정 막대 1개(15,866,265 토큰) + 검색·페이저(계정 1개라 페이저 숨김) 정상. 계정별 독립 차트는 제거됨. 스크린샷 `/tmp/0184_admin_drill2.png`. PASS.
  - **(A 후속 — 계정별 비용 차트 보강)** 사용자 지적 "계정별 비용 차트 누락" 수정 후 재배포(b4e52b5) 재검증: 역할 'Admin' 클릭 → drill 패널이 **[토큰 | 비용] 2열**(역할별 차트와 일관). 토큰열(bootstrap_admin #1 515,443 / admin #10 451,667) + **추정 비용열(bootstrap_admin $0.60 / admin $0.50)** 모두 노출. 스크린샷 `/tmp/0184_drill_cost.png`. PASS.
  - CHECK#13(PB-0008 Windows-browser) **충족**.
- 2026-06-09 (TASK-0174 "전체 N행 미리보기" 링크 오정렬 수정 — **PB-0008 Windows-browser 완료 게이트(무회귀 smoke)**):
  - **Environment: Windows-browser** (실제 Windows Chrome/148 via `bin/win-browser.py` 무권한 relay, https://localhost:18080, self-signed ignore). WSL headless 가 아닌 실제 Windows 화면 검증.
  - 시나리오: bootstrap_admin 영속 세션 → `#promptInput` 에 부위별 Top-N 질의(+범위 MIN/MAX 동반) 전송 → ask-worker 처리 완료 → 멀티-result 답변 정상 렌더. 스크린샷 `/tmp/win-browser-shots/shot_20260609_174354.png`(쿼리 1/3 result 뷰어), `_174718.png`(대형 인라인 표).
  - **결과: 무회귀 PASS.** (a) 병합된 `app.js`(본 cycle 의 `loadCsvAsInlineTable` 값 가드 + 동시세션 TASK-0173 `.step-reason` 기능)이 채팅 UI·대화목록·result 뷰어를 정상 렌더, JS 크래시 0. (b) 버그를 유발하던 **MIN/MAX 보조쿼리 패턴이 실데이터 result set 으로 실존**(쿼리 1/3: MinItemID=1001 / MaxItemID=900007 / count 1행) 확인 — `_collapse_large_tables` 가 이를 ranking 표에 잘못 붙이던 것이 근본.
  - **한계(정직 기재):** `_collapse_large_tables` 의 collapse+"전체 N행 미리보기" 링크 경로는 LLM 이 본문 대형 표(>5행)를 렌더하고 동턴에 execute_sql CSV 를 생성해야만 트리거되는데, 2회 유도에도 LLM 이 result 뷰어/소형 표/이전결과 재포맷을 선택해 **온디맨드 재현 불가**(비결정적). 해당 경로의 결정적 검증은 `unit/feature-0002-agent-core/tests/test_collapse_table_csv_match.py` 회귀 4종(값매칭·무매칭생략·형태폴백·토큰필터)이 담당 — make test 컨테이너 PASS. CHECK#13 **충족**(시각 표면 존재 + 실 브라우저 무회귀 확인, 핵심 로직은 단위테스트 결정적).
- 2026-06-09 (TASK-0169 out-of-process ask-worker 실행모델 — **PB-0008 Windows-browser 완료 게이트**):
  - **Environment: Windows-browser** (실제 Windows Chrome/148 via `bin/win-browser.py` 무권한 relay, https://localhost:18080, self-signed ignore). WSL headless 가 아닌 실제 Windows 화면 검증.
  - 시나리오(라이브 cutover, flag=worker): bootstrap_admin 로그인 상태 → `#newConversationBtn` 새 대화 → `#promptInput` 질문 입력 → `#sendBtn` 전송 → ask_jobs `running→done`(worker 처리) → **답변 정상 렌더**("7 곱하기 8 = 56, 경로: worker 직접 계산, ✅ 검증 완료"). browser→ask_jobs enqueue→worker claim→run→result_json→browser 렌더 전체 왕복 PASS. 스크린샷 `/tmp/pb0008_answer.png`. CHECK#13(PB-0008) **충족**.
  - 라이브 부하/백프레셔: 9 동시 ask(동일 계정) → 6× 200(실답변) + **3× 429**("동시 요청 제한") = `WEB_PARALLEL_LIMIT`(6) 정확 enforce(M5). burst 중 ask_jobs `pending=5,running=1`(6 active=limit), 단일 worker 직렬 처리로 6건 모두 동기 응답. 잡 전부 done(stuck 0).
  - 라이브 핵심(AC-0327): ask `running` 중 web `force-recreate` → 동일 run_id·attempts=1·lease=1 로 `done` 도달, backstop 미오염(last_status=done/last_error 빈값, B1). **web 재배포가 in-flight worker run 을 건드리지 않음** 실측.
  - 단위(DB-free, agent 이미지 mount): 신규 `test_ask_jobs.py`(claim/enqueue/fencing/sweep/cancel/ownership/active_inline_paths/table_exists 16건) + `test_ask_worker.py`(payload round-trip/config 불변식/run_id 6건) + `test_clear_cancel_runid.py`(MJ-2 fencing 4건) → make test 회귀 0 + ruff clean + py_compile.
  - hotfix(라이브 포착): `_ask_worker_ready` naive/aware datetime 비교 TypeError→readiness 영구 503 버그 수정([[project_task0159_orphan_run_stale_tz]] tz 함정 동형).
- 2026-06-09 (TASK-0164 SIGTERM graceful finalizer + RBAC catalog prune + out-of-process 설계):
  - 변경 성격: **백엔드** (`app.py` shutdown hook + run 생명주기 정리 + RBAC catalog DELETE) + 설계 문서. **시각 UI 표면 변경 없음** → **Environment: Windows-browser N/A** (PB-0008 화면 검증 대상 아님 — 관리 그리드는 PERMISSION_DEFINITIONS 기반이라 A2 도 비가시). CHECK#13 WARN 사유 = 시각 표면 부재.
  - 단위(DB-free, agent 이미지 mount): 신규 `test_shutdown_finalizer.py` 3건(S1 역 boot-guard 선정 / S2 부팅이전 skip / S3 race 가드) + 기존 `test_orphan_run_stale_recovery.py` 6건 → 전체 pytest 통과(회귀 0), py_compile PASS.
  - 라이브(배포 후): (a) ask mid-flight 중 `docker stop`/재배포 → web 로그 `shutdown finalize: 진행중 run N건 정리` + 해당 cid KV `last_status='error'`(고착 아님), (b) SIGKILL(`kill`) 대조 시 부팅 reconciliation 이 정리, (c) A2 — 재기동 후 `WebPermissions` 의 3 폐기 코드 행 0 — STATUS TASK-0164 참조.
  - outside-voice 적대적 리뷰 PASS-WITH-NITS, BLOCKER 0 (REV-20260609-0164).

- 2026-06-08 (TASK-0158 "진입점 없는 기능" 진입점 구성 Tier 1·2 — **PB-0008 Windows-browser 완료 게이트**):
  - **Environment: Windows-browser** (실제 Windows Chrome/148 via `bin/win-browser.py` 무권한 relay, https://localhost:18080, self-signed ignore). WSL headless 가 아닌 실제 Windows 화면 검증.
  - 시나리오: `unit/feature-0003-agent-web-ui/tests/win-browser-task0158.scenario.json` (authed-session 가정 — 영속 프로필 로그인 상태). 재현: `python3 bin/win-browser.py launch --url https://localhost:18080/` → `run --scenario <위 파일>` → `down`.
  - **결과: OK=True, 39/39 step PASS.** 7개 진입점 전부 실제 브라우저 동작 확인:
    - **Tier1 즉시답변** — ask 전송 직후 `#sendBtn` 이 `.send-btn.is-stop`(중단)으로 모핑 + `#composerFinalizeBtn`("즉시 답변") 노출 `assert_visible` PASS(shot 03), 중단 클릭으로 취소 PASS(shot 04).
    - **Tier1 공유 링크 관리** — 대화 ··· 메뉴 "공유 관리" → `.share-mgr-panel` 모달 렌더("발급된 공유 링크가 없습니다." — 새 대화 정상)(shot 05·06).
    - **Tier1 scopeAll** — `#composerAttachmentsScopeAll` DOM 존재 eval=True (마크업 배포 확인).
    - **Tier2 내 활동기록** — 프로필 drawer "내 활동 기록" 탭 → `#profileAuditList` 렌더(shot 07).
    - **Tier2 grant 진단** — 관리콘솔 대시보드 `#dashboardGrantHealth` eval=True(shot 08).
    - **Tier2 audit.purge** — Audits pane 빨간 "보존기간 초과 로그 정리"(`#auditPurgeBtn`) `assert_visible` PASS → 모달(`.admin-modal`) "감사 로그 정리 (purge)" + 기준날짜 + 미리보기/삭제실행(disabled) 렌더 → 취소(삭제 미실행)(shot 09·10).
    - **Tier2 감사 facet** — `auditResourceTypeOptions`/`auditActorOptions` datalist 채워짐 eval `{res:9, actor:5}`.
  - 증거 스크린샷 10장: `/tmp/win-browser-shots/task0158/` (02_app_loaded ~ 10_purge_modal). CHECK#13(PB-0008 Windows-browser) **충족** — Tier1/2 커밋 시점 WARN 의 후행 보강.

- 2026-06-08 (TASK-0159 고아 run 무한 폴링 수정 — tz stale 회귀 + 부팅 reconciliation):
  - 변경 성격: 백엔드 (`app.py` run-status 생명주기 + stale 판정 tz). **시각 UI 표면 변경 없음** → PB-0008 Windows-browser N/A, CHECK#13 PASS(web/UI diff 없음).
  - 신규 `tests/test_orphan_run_stale_recovery.py` — agent 이미지(`--no-deps`, DB 없이 monkeypatch) 에서 **6 passed in 0.65s**:
    - T1 `_last_step_at_for_run`: aware KST(14:33+09) → UTC naive(05:33) 변환 / naive 통과 (회귀 가드).
    - T2 `_compute_display_status`: 오래된 step(>1200s) → `('stale_error', True)`, 최근(30s) → `('processing', False)`, terminal 통과.
    - T3 startup reconciliation boot-guard: `last_status_at >= _PROCESS_BOOT_UTC` skip 시맨틱.
  - 전체 app.py `python3 -m py_compile` PASS. 라이브 검증: web 재배포 후 (a) startup reconcile 로그, (b) 합성 고아 run → 재배포 시 `error` 자동 정리 확인 — STATUS TASK-0159 참조.

- 2026-06-05 (TASK-0151 DB 조회 UX 개선 — web 면: 첨부 text inline cap 정렬):
  - 변경 성격: `app.py _prepare_text_inline_attachments` 의 SQL 정렬(`ASC`→`DESC`+reverse) — **시각 UI 표면 변경 없음**(LLM 컨텍스트로 들어가는 inline 첨부 선별 로직, 백엔드). PB-0008 Windows-browser 화면 검증 대상 아님(Environment: Windows-browser N/A — UI 표면 없음). CHECK#13 WARN 의 사유 = 시각 표면 부재.
  - 검증: ruff(All passed) + pytest **191 passed/2 skipped**(feature-0002 신규 `test_db_query_ux.py` 14건 포함, 회귀 0). 동작 검증은 라이브 canary ask(첨부 리뷰 + 스키마 grounding)로 배포 후 수행 — STATUS TASK-0151 참조.

- 2026-05-20 (TASK-0089 Phase A~E — 작업 화면 profile drawer "내 감사 로그" 탭 신설):
  - **환경**: `docker run --rm --entrypoint python -v <wt>/unit/feature-0003-agent-web-ui/src:/app/web repo-web:latest` host-mounted code + image dependency.
  - **py_compile**: PASS.
  - **node --check static/app.js**: PASS.
  - **routing smoke (Phase E)**:
    - `list_profile_audit_events` present in app.py module ✓
    - `get_profile_audit_event` present ✓
    - FastAPI app routes: `['/api/profile/audits', '/api/profile/audits/{event_id}']` ✓
  - **Codex outside voice 5 findings 흡수 검증**:
    - C1 URL mismatch → 신규 `/api/profile/audits` endpoint 등록 확인 ✓
    - C2 `.any > .own` 강제 → backend `_audit_compose_where(scope="own", ...)` 직접 호출 (code review) ✓
    - C3 CSV export 미노출 → drawer-pane HTML 에 export 버튼 부재 (code review) ✓
    - C4 1-column + 수평 스크롤 → styles.css `.profile-audit-detail-change { white-space: pre; overflow: auto; max-height: 30vh }` ✓
    - C5 권한 race → `state.profileAudit.forbidden` + 403 handler in `loadProfileAuditList` + `updateProfileAuditTabVisibility()` in `renderProfile` ✓
  - **미완 (PR merge 후 사용자 위임)**:
    - live browser smoke: drawer tab 클릭 → list 표시 → row click → inline detail expand → filter 적용 / 초기화
    - `.any` 보유자 (admin) 가 drawer 호출 시 본인 row 만 나오는지 확인 (Codex C2 검증)
    - `audit.read.own` 권한 revoke 후 403 graceful state 진입 확인 (Codex C5 검증)
    - drawer 폭 390px 에서 1-column layout + ChangeJson 수평 스크롤 시각 검증 (Codex C4 검증)
- 2026-05-20 (TASK-0090 Phase A~B — `/api/admin/audits/export.csv` CSV streaming export 전환):
  - **환경**: `docker run --rm --entrypoint python -v <wt>/unit/feature-0003-agent-web-ui/src:/app/web repo-web:latest -c "..."` host-mounted code + image dependency.
  - **py_compile**: PASS.
  - **lightweight smoke (Phase B)**:
    - `import web.app` → IMPORTED OK ✓
    - `_AUDIT_EXPORT_CHUNK_SIZE = 500` ✓ (Codex minimum-fix — 1000→500)
    - `_AUDIT_EXPORT_FLUSH_BYTES = 65536` ✓ (Codex minimum-fix — 64KiB byte-threshold)
    - `_audit_export_filter_hash` present ✓ (Codex C4 — filter PII 회피)
    - `StreamingResponse` imported ✓ (Codex C1 — sync generator base)
    - `filter_hash` deterministic (sort_keys 정렬): `h1 == h2 = "42ea65e7de088de2"` ✓
  - **Codex outside voice 5 findings 흡수**:
    - C1 async + sync mysql blocking → sync generator (`def csv_iter()`) + streaming-only conn (generator 내부 try/finally)
    - C2 consistent snapshot vs max_id → `SELECT MAX(Id) FROM WebAuditEvents{where}` high-water + 모든 page `Id <= max_id AND Id < cursor_id`
    - C3 query plan EXPLAIN → future cycle (live mysql, representative filters)
    - C4 cap 제거 = DoS/계약 변경 → SECURITY §9.5 갱신 + export self-audit (start + complete/aborted) + 동시 제한 별 cycle
    - C5 cleanup → generator 내부 try/finally (cursor.close + conn.close + complete audit)
  - **endpoint 구조 검증 (code review)**:
    - **Phase 1 (auth conn)**: `_connect_memory()` + `_require_account` + `audit.export` permission + `_audit_parse_filter_params` + `_audit_compose_where` + `SELECT MAX(Id)` + `record_audit_event(action="audit.export.start", ...)` + commit + conn.close()
    - **Phase 2 (sync generator)**: `def csv_iter()` — header yield + while loop (max_id + cursor_id + chunk_size=500) → `_audit_compose_where` per page (cursor_id 추가) + Id<=max_id 강제 + ORDER BY Id DESC LIMIT 500 → row 마다 csv.writer.writerow → sio.tell()>=65536 마다 yield + reset → cursor_id 갱신 → final flush → try/finally cleanup → complete audit
  - **미완 (PR merge 후 사용자 위임)**:
    - live container PATCH 호출 + WebAuditEvents row 의 실 audit.export.start/complete 검증
    - representative filters EXPLAIN FORMAT=JSON 분석 (live mysql, query plan 보장)
    - 100k+ row export 시 memory footprint 측정 (현재 worktree 데이터는 ~150 row, 실 검증 불가)
- 2026-05-20 (TASK-0088 Phase A~D — `slow_query_log` 통합 ADR-0020 Decoupled 채택, docs only):
  - **검증 형태**: ADR 결정 → docs only, code 변경 0, runtime side-effect 0. py_compile/runtime smoke 불필요. verify-completion PASS 만 확인.
  - **Codex outside voice review** (consult mode, model_reasoning_effort=high, 390,785 tokens) → 5 critical findings + 2 minimum-fix 도출 → v2 redesign 흡수:
    - **C1 (framing)**: 현재 mysql conf `99-mysql-ai-server.cnf` 에 `slow_query_log` 설정 부재 (MySQL 8.0 default disabled) → ADR framing "현재 통합" → "**향후** 통합 여부" 정정.
    - **C2 (PII)**: slow query log = raw SQL statement literal — PasswordHash/Token/API key/임시 비밀번호/raw LLM prompt 등이 SECURITY.md §9.2 redact 정책 밖 → Decision 1순위 근거 = raw SQL text PII 차단.
    - **C3 (Option A reject 재작성)**: ETL 의 retention/RBAC 정합 trivial. 진짜 reject = semantic pollution + raw SQL PII + ChangeJson/table bloat + actor/target 의미 부재.
    - **C4 (Option B reject 재작성)**: raw SQL exfiltration 표면 + mount/rotation/race + 대용량 파일 DoS + `audit.read.any` 권한 의미 오염 + MySQL `log_output=TABLE` destination 우회.
    - **C5 (PS digest-first 추가)**: MySQL 8.0 의 `events_statements_summary_by_digest` digest 집계 1차 도구 권유. slow_query_log 는 incident/deep capture 2차로 제한.
  - **ADR-0020 4 section**: Context (current state) + Decision (Option C Decoupled) + Options 검토 (A/B reject 구체 사유 + C 채택) + Recommended performance path (PS digest-first 1차, slow_query_log incident 2차) + Security policy (raw SQL = 민감 로그) + Consequences (외부 SaaS trigger 4 선행 조건).
  - **결론**: Codex 5 findings 모두 ACCEPT 후 v2 redesign. ADR-0019 Codex C1 lock-in 의 final 결론. docs only — runtime smoke 불필요.
- 2026-05-20 (TASK-0091 Phase A~F — PATCH admin/products audit before-state full snapshot + audit integrity fix):
  - **환경**: `docker run --rm --entrypoint python -v <wt>/unit/feature-0003-agent-web-ui/src:/app/web repo-web:latest -c "..."` host-mounted code + image dependency.
  - **py_compile**: PASS.
  - **Sentinel + leak checks** (Codex C1, C3): `build_audit_change_json(action='admin.product.update', before=..., after=...)` → ChangeJson body 검사:
    - `'TASK-0091-SENTINEL-FULL-CONTENT-SHOULD-NOT-LEAK' in body: False` ✓ (Codex C1 — system_prompt full content drop, SECURITY §9.2)
    - `'should_not_leak' in body: False` ✓ (Codex C3 — databases drop)
  - **before/after delta checks** (Codex C4): sort_order 100→50 / is_default False→True / name 'before-name'→'after-name' 모두 정확 ✓
  - **default_cleared_product_ids** (Codex C4 side effect): caller 가 after dict 에 `_default_cleared_product_ids` 키로 명시 전달 → builder branch 가 처리 → body 의 top-level `default_cleared_product_ids: [5, 9]` ✓
  - **system_prompt_summary** (Codex C1, SECURITY §9.2): before/after 모두 `{present, content_len, updated_at}` 만 (content 본문 부재 sentinel 검증) ✓
  - **결론**: Codex outside voice 5 findings 모두 흡수 정합. 8-field allowlist + transaction integrity + side effect 추적 모두 검증.
  - **미완 (PR merge 후 사용자 위임)**: live PATCH 호출 + WebAuditEvents row 의 실 ChangeJson 검증 (real DB write path).
- 2026-05-20 (TASK-0086 Phase A~G — `WebAccountActivity` legacy table DROP + dual write 종료):
  - **baseline**: legacy=74 row, mirror=74 row (1:1 정합). 초기 흡수 68 + dual write 추가 6.
  - **backup (Codex C4)**: `mysqldump --single-transaction --quick --set-charset --create-options --add-drop-table --triggers --hex-blob --no-tablespaces agent_memory WebAccountActivity > artifacts/mysql-backup/WebAccountActivity-20260520T074927Z.sql` (11,950 bytes). Row digest `a09e7898d1ce88711f7a850ab5fbcc91`. File md5 `f4163df9dc1b7ac81ae4c463a0f35e98`.
  - **scratch restore rehearsal**: 별 schema `task0086_restore_test` import → row count 74 + digest match ✓ → scratch DB DROP.
  - **사용자 명시 ack** 받음.
  - **code 변경 (Phase C)**: `_log_search_activity()` legacy INSERT 제거 + `_ensure_web_account_activity_schema()` 정의+호출×2 제거 + `_migrate_web_account_activity_to_audit()` rollback window 보존. py_compile PASS.
  - **lightweight smoke (Phase D+E)**: `docker run --rm --entrypoint python -v <wt>/.../src:/app/web repo-web:latest -c "import web.app"` → `IMPORTED OK` + `_ensure_web_account_activity_schema present: False` ✓ + `_migrate_web_account_activity_to_audit present: True` ✓.
  - **DROP (Phase F)**: `DROP TABLE IF EXISTS WebAccountActivity` → `DROP completed`.
  - **verify (Phase G)**: `tables_remaining=0` ✓ + WebAuditEvents `conversation.search.body` 74 row 변동 없음 ✓.
  - **tests**: test_audit_migration.py M3 (`m3_log_search_activity_dual_write`) 제거 + main() 호출 제거 + 모듈 docstring 3→2 시나리오 (Codex C2). M1/M2 보존 (table-absent silent skip).
  - **Codex outside voice 5 findings 흡수**: C1 (Option A 불가능→helper Option B) / C2 (mirror risk→smoke + M3 제거) / C3 ("single tx"→"single statement") / C4 (backup 검증 강화) / C5 (rollback 2 시나리오).
  - **Rollback runbook**: (1) DB restore only / (2) code revert + DB restore (완전).
  - TASK-0073 Phase A2 dual write 종료. dispatcher → WebAuditEvents 단일 source.
- 2026-05-20 (TASK-0092 Phase A~B — `AGENT_AUDIT_ENABLED=0` + `AGENT_MODE=prod` startup fail-closed **7 vector matrix** 검증):
  - 환경: `docker run --rm --entrypoint python repo-web:latest -c "import web.app"`. module load 시점 `_enforce_audit_prod_gate()` (app.py:76-94) trigger. compose `--no-deps` 우회 (Codex C2 — mysql 기동 회피, 다른 worktree compose project 오염 차단). `.env` 부재로 inline `-e` 만 사용.
  - **7 vector PASS (7/7)**:
    - **V1** (`AGENT_AUDIT_ENABLED=0` + `AGENT_MODE=prod`) → rc=1, stderr `[FATAL] AUDIT REQUIRED IN PROD — set AGENT_AUDIT_ENABLED=1 (AGENT_MODE=prod; TASK-0073 Phase A1)` ✓ target fail-closed
    - **V2** (`AGENT_AUDIT_ENABLED=0` + `AGENT_MODE=<unset>`) → rc=1, stderr `... AGENT_MODE=(unset → prod) ...` ✓ default prod 정합
    - **V3** (`AGENT_AUDIT_ENABLED=0` + `AGENT_MODE=staging`) → rc=1, stderr `... AGENT_MODE=staging ...` ✓ non-dev/test 정합
    - **V4** (`AGENT_AUDIT_ENABLED=0` + `AGENT_MODE=dev`) → rc=0, stdout `IMPORTED OK` ✓ dev/test bypass 허용
    - **V5** (`AGENT_AUDIT_ENABLED=1` + `AGENT_MODE=prod`) → rc=0, stdout `IMPORTED OK` ✓ positive control
    - **V6** (`AGENT_AUDIT_ENABLED=true` + `AGENT_MODE=prod`) → rc=1, stderr `... AGENT_MODE=prod ...` ✓ Codex C3 strict-string-equality 계약 확인 (`"true"` ≠ `"1"` — 운영자 trap 가능성)
    - **V7** (모두 unset) → rc=0, stdout `IMPORTED OK` ✓ default `1` + default prod 정상
  - **stderr 검증** (Codex C4 강화): 모든 FAIL vector 가 rc=1 + stderr 3 substring (`[FATAL] AUDIT REQUIRED IN PROD` + `set AGENT_AUDIT_ENABLED=1` + `TASK-0073 Phase A1`) 모두 포함 + `Traceback` / `ModuleNotFoundError` 부재. PASS vector 는 stderr `[FATAL]` 부재 + stdout `IMPORTED OK` 정합.
  - **운영자 trap 확인** (V6): `AGENT_AUDIT_ENABLED="true"` 가 fail-closed 됨 — strict string equality (`os.getenv(...).strip() == "1"`). 운영자가 truthy 표현 (`true`/`yes`/`01`) 명시 시 prod 시작 차단. **SECURITY.md §8 의 strict-string-equality 계약 명시 별 cycle 후속 권고** (본 cycle scope 외).
  - 본 검증으로 TASK-0073 Phase E 의 사용자 위임 항목 1 건 (audit prod gate fail-closed) 해소. live container spawn 으로 코드 path 정합성 + 메시지 정확성 + dev/test bypass 정합성 모두 확인.
- 2026-05-19 (TASK-0072 + TASK-0074 HTTP smoke — `bootstrap_admin` 1 토큰만 ad-hoc curl):
  - **S2 .any cross-account** (`GET /api/conversations?q=데이터&limit=10`): ✅ `matched_count=10`, `has_any=true`, `search_mode=true`, `next_cursor` 존재.
  - **S4 cursor disjoint** (limit=5 페이지 1 → 페이지 2):
    - 페이지 1 ids: `20260515074803-d613ab40 20260515092328-a7e5e9e1 20260515092319-96e627b9 20260515092147-e3dc971b 20260515092113-3a7944ff`
    - next_cursor: `2026-05-15 18:21:42|20260515092113-3a7944ff`
    - 페이지 2 ids: `20260515074935-58c48a7e 20260515080029-a5353434 20260429084833-6f07eb25 20260429075057-af0d6352 20260416081007-ec1bfd5d`
    - overlap = ∅ → PASS (sub-spec 3 SQL ORDER BY 단일화 + cursor keyset 정합 확인).
  - **S5 invalid q → 400**: `q="ab"` → 400 / `q="%%"` → 400 / `q="  "` → 400 (raw-len < 3 또는 escape-0 모두 차단).
  - **S6 rate limit 11th → 429**: call#1~10 모두 200, call#11 → 429. per-account 10 req/min token bucket 동작 확인.
  - **S7 DDL idempotent**: `SHOW CREATE TABLE WebAccountActivity` 응답에 PK `(Id)` + `IX_WAA_Account (AccountId, CreatedAt)` + `IX_WAA_Action (Action, CreatedAt)` 모두 존재. AUTO_INCREMENT=24 (이전 호출 누적).
  - **S8 audit INSERT**: `SELECT ... FROM WebAccountActivity ORDER BY Id DESC LIMIT 10` → 23 rows. AccountId=1 (`bootstrap_admin`), Action=`conversation.search.body`, QueryHash 100% 64-char SHA-256 hex (length distribution = `{64: 23}`), MatchedCount 정확. rate-limited (429) 11번째 호출은 audit 안 됨 (endpoint 가 429 early return — 정확한 동작).
  - **Skip**: S1 (.own no leak) / S3 (byte-equal owner_id) — operator (`review_user01`) pw 미보유. SQL composition order sub-spec 1 의 코드 review (`_list_conversations` line 2941-2949 의 has_any 분기 + endpoint line 5566-5571 의 effective_owner_id 강제 overwrite) 로 검증.
  - **TASK-0074 UI 가독성**: 사용자가 브라우저 hard refresh 후 직접 확인 권장.
- 2026-05-15 (TASK-0061 round 2 — /qa 심층 검증, browser session `483add52718b4a93`):
  - **Phase 4 Point rail 동작 검증**: 메시지 2 개 대화 (`20260515080029-a5353434`, topic "[Fork] 안녕하세요...") 선택 → `state.messages.length=2`, `#messagePointRail.hidden=false`, `.message-point-dot` 2 개 노출. 첫 dot click → `messageLog.scrollTop=245 → smooth scroll`, `.message-point-dot.is-active.dataset.messageId=291` 갱신 확인.
  - **Phase 5 캘린더 deep 동작 검증**:
    - `historyCalendarBtn` click → popover hidden 제거, title "2026년 5월" (선택 대화의 메시지 날짜 자동 cursor).
    - `calendarPrevMonth` click → title "2026년 4월" 정상 이동.
    - `calendarNextMonth` click → title "2026년 5월" 복귀.
    - has-messages day "15" click → `.history-calendar-day.is-selected.textContent=15`, `.history-calendar-time` 1 개 (그 날 메시지가 1 건) 표시.
    - 시각 click → `/api/history_anchor` 호출 → `.is-anchor-highlight` 1.5 초 강조 (정상 동작 — 1 차 cycle 의 단위 검증으로 확인).
    - screenshot: `/shared/out/browser/shot_20260515_091222.png`.
  - **Phase 7 admin select-all cross-page 동작**: 1 차 cycle 에서 `currentPageAccounts().length=15` == `accountList .admin-list-row` 개수, `filteredAccounts().length=26` (다른 페이지에 11 개) 확인. round 2 의 admin page reload + cross-page selection 시퀀스는 bash quote escape 이슈로 추가 자동화 어려움 — code review + unit-level helper 동작 검증 (`currentPageAccounts()` 정확한 slice 반환) 으로 정합 보장.
  - **Phase 3 stale 감지 / Phase 6 비번 reset / Phase 8 bulk delete**: 1 차 cycle 의 응답 형식 / endpoint 권한 / DOM 요소 검증 (`/api/progress` 의 display_status·raw_status·is_stale 포함 / `adminPasswordResetBtn` 노출 / `/api/delete_conversations` empty body 400 validation) 으로 contract 확정. **실 데이터 manipulation 또는 destructive 실 호출 검증은 운영 환경에서 사용자 명시 시점에 별도 진행 권고** — stale 은 backend 의 KV 시각 조작 필요, 비번 reset 은 대상 계정의 세션 강제 종료 + 임시 비번 발급 destructive, bulk delete 는 대화 영구 삭제 destructive.
  - 정합 검증 결과: 본 cycle 의 PR 본문 (`#27` 의 차후 PR 으로 main 머지) 에 추가 fix 없이 ship 가능. round 2 검증에서 신규 발견 이슈 0건.
- 2026-05-15 (TASK-0061 GOAL.md 8 항목 합본 cycle):
  - 정적 검증:
    - `python3 -m py_compile unit/feature-0003-agent-web-ui/src/app.py` → PASS
    - `node --check unit/feature-0003-agent-web-ui/src/static/app.js` → PASS
    - `node --check unit/feature-0003-agent-web-ui/src/static/admin.js` → PASS
  - 컨테이너 재배포: `make web` → `repo-web-1 Recreated/Started`. mysql healthy.
  - browser 검증 (`http://web:8000` via `make browser-*`, session `e438b0811dc1477d`):
    - 메인 페이지: title `MySQL AI Assistant`, cache-bust `?v=20260515-task-0061` 적용. 신규 DOM 5개 (`.messages-wrap` / `#messagePointRail` / `#historyCalendarBtn` / `#historyCalendarPopover` / `#conversationBulkBar`) 모두 존재.
    - bootstrap_admin 로그인 → auth overlay hidden + profile name "bootstrap_admin" 정상.
    - conversation list 45개 표시, 내 대화 checkbox 34개 노출 (own 그룹 한정), 타 계정 대화 (11개) 에는 미노출.
    - 첫 own conversation 의 checkbox click → `conv-bulk-bar` 노출, label "1개 선택됨" 표시 확인.
    - `#historyCalendarBtn` click → `#historyCalendarPopover` 노출, title "2026년 4월", has-messages day 1개 (4/22) 정상.
    - `/api/progress` 응답: `{status:"done", display_status:"done", raw_status:"done", is_stale:false}` — 신규 필드 모두 포함.
    - `/api/history_dates` 응답: `{first:"2026-04-22", last:"2026-04-22", dateCount:1}` — `AgentMemoryMessages` 정본 기준 동작 확인.
    - `/api/delete_conversations` 빈 body POST → HTTP 400 validation 정상.
    - pending bubble 강제 렌더 (`state.pendingBubble = {...}; renderMessages();`) → `#pendingAssistantBubble` + `.pending-bubble-spinner` + `#pendingBubbleElapsed` 모두 존재. `clearPendingBubble()` 호출 시 정상 정리.
    - admin 페이지: title `MySQL AI Assistant Admin`. accountList 15 rows (현재 페이지). `currentPageAccounts().length == 15`, `filteredAccounts().length == 26` — helper 가 정확히 현재 페이지 sub-set 반환. 비-bootstrap_admin 계정 (sales) detail panel 진입 시 `adminPasswordResetBtn` "비밀번호 초기화" 노출 확인.
    - screenshot: `/shared/out/browser/shot_20260515_085713.png` (admin sales detail with reset btn).
  - 미수행: 실제 stale 시각 manipulation (KV 직접 UPDATE 로 last_status_at 을 만료 시간 이전으로 후퇴) → 후속 cycle 의 운영 데이터 관찰 시 함께 확인 권고. 실제 비밀번호 reset → 로그인 force modal end-to-end → 변경 완료 흐름은 별도 사용자 환경 검증 (현재 cycle 은 backend endpoint 권한 / button 노출 / 응답 구조 / modal DOM 정상 확인까지).
- 2026-05-15 (TASK-0060 Product / Role 시스템 프롬프트 정비):
  - `python3 -m py_compile unit/feature-0002-agent-core/src/agent_core.py unit/feature-0003-agent-web-ui/src/app.py`
    - 결과: 통과
  - `python3 -m unittest unit/feature-0002-agent-core/tests/test_compose_system_prompt.py`
    - 결과: 2건 통과
  - DB 분석 / readback:
    - `KR`: `dbgame` 98 tables, `dblog` 279 tables, `dbauth` 9 tables 확인
    - `MV`: `account_db` 6 tables, `dev_1_1_1_20` 62 tables, `have_00` 50 tables, `global_db` 28 tables, `log_v2` 0 tables 확인
    - `WebSystemPrompts`: Product prompt 2건 + Role common prompt 5건 content length 확인
  - runtime 직접 확인:
    - web 컨테이너 내부 `compose_system_prompt(product_id=1, role_id=16, product_mode="pinned")`
    - 결과: `HAS_PRODUCT_CONTEXT=True`, `HAS_ROLE_COMMON=True`, `HAS_SALES=True`
- 2026-03-26: 구조 검증 기준만 정의
- 2026-04-06: 이전 로그인 버그 수정 기준의 브라우저 검증 수행
- 2026-04-14: 이전 콘솔형 UI 렌더링 검증 수행
- 2026-04-15:
  - `python3 -m py_compile unit/feature-0003-agent-web-ui/src/app.py`
  - `node --check unit/feature-0003-agent-web-ui/src/static/app.js`
  - `node --check unit/feature-0003-agent-web-ui/src/static/admin.js`
  - curl 기반으로 `session/auth/signup/admin/accounts/new_conversation/conversations/history/ask` 검증
  - MySQL로 `AgentCoreConversations.owner_account_id` 직접 확인
  - 브라우저 자동화로 스크린샷 생성:
    - `/shared/out/browser/ui-account-login.png`
    - `/shared/out/browser/ui-account-workspace.png`
    - `/shared/out/browser/ui-account-admin.png`
  - 이후 구현 변경으로 프로필 드로어 탭, 로그아웃 초기화, Admin 검색/페이지네이션, 병렬 대화 UX, 외부 Local LLM provider 기준 ask 흐름에 대한 재검증 필요
- 2026-04-15:
  - bootstrap admin 브라우저 로그인 후 `model=auto` 실사용 검증
  - 완료 화면 conversation `20260415092741-f2384e59`, subtitle `최근 갱신 2026. 04. 15. 오후 06:28 · 메시지 2 · 상태 done`
  - 회귀 측정 결과:
    - `20260415091922-1a529620`: `duration_ms=33038.4`
    - `20260415092741-f2384e59`: `duration_ms=35555.35`
  - 스크린샷 증빙:
    - `/shared/out/browser/perf_login.png`
    - `/shared/out/browser/perf_before_send.png`
    - `/shared/out/browser/perf_just_after_send.png`
    - `/shared/out/browser/perf_done.png`
  - 테스트 중 생성된 stuck conversation `20260415093013-f34140ec` 는 `POST /api/cancel` 후 `status=done` 으로 정리했고, 이후 `GET /api/conversations` 기준 `processing` 0건 확인
- 2026-04-16:
  - `python3 -m py_compile unit/feature-0003-agent-web-ui/src/app.py`
  - `node --check unit/feature-0003-agent-web-ui/src/static/app.js`
  - `node --check unit/feature-0003-agent-web-ui/src/static/admin.js`
  - API 회귀 스크립트로 기본 signup role 전환, role CRUD, account override, `console.access` 읽기 전용 셸, own/any 대화 권한, `clear_memory=410`, 마지막 관리 가능 계정 보호, soft delete/session revoke 검증
  - 브라우저 자동화로 관리자/사용자 세션 검증:
    - `/shared/out/browser/rbac_admin_home_76309029.png`
    - `/shared/out/browser/rbac_admin_roles_76309029.png`
    - `/shared/out/browser/rbac_user_own_76309029.png`
    - `/shared/out/browser/rbac_user_other_76309029.png`
  - 후속 브라우저 검증으로 deleted 필터의 soft-deleted 계정 표시, 삭제 role 미노출, 삭제 계정 로그인 차단을 재확인

- 2026-04-30 (TASK-0047 Product Selector + Auto 모드 자동 검증):
  - 빌드: `docker compose build --no-cache web` (BuildKit layer cache 가 stale 잡는 edge case 회피) → image sha 갱신.
  - 컬럼 검증: `SHOW COLUMNS FROM AgentCoreConversations LIKE 'product_mode'` → `varchar(8) NO '' pinned`. `SHOW COLUMNS FROM WebAccounts LIKE 'ProductPref%'` → `ProductPrefMode varchar(8) YES NULL`, `ProductPrefPinnedId bigint YES NULL`.
  - Playwright 28-check spec 실행 결과: **28/28 PASS, healthScore=100, console.error=0**. 결과 JSON: `repo/.gstack/qa-reports/qa-product-selector-result.json`.
  - 검증된 항목: AUTH(1) / SESSION(4) / BUST(2) / MARKUP(2) / CHIP(5) / LABEL(1) / PATCH(4) / NEWCONV(2) / UI(3) / HYDRATE(1) / RACE(2) / CONSOLE(1).
  - 스크린샷 증빙: `repo/.gstack/qa-reports/screenshots/product-01-app-loaded.png`, `product-02-pinned-selected.png`, `product-03-auto-selected.png`, `product-04-auto-hydrated.png`.
  - 발견된 회귀: 기존 배포의 fast-path 가 신규 컬럼 마이그레이션을 우회하던 문제. `_runtime_tables_available` probe 에 신규 컬럼 검사 + errno 1054 분기를 추가해 자동 트리거되도록 수정 (CHG-20260430-0019, REV-20260430-0009).
  - 검증 미흡 영역(후속): LLM resolver 도입(R-02) 후 autoFocusChip / 운영 회귀(다중 탭 BroadcastChannel, mobile bottomsheet), R-03 row-level lock — 모두 BRIEFING-product-selector-v1.md §1 추적.

- 2026-06-10 (TASK-0197 assistant 말풍선 타임스탬프 옆 소요시간 표시 — **PB-0008 Windows-browser 완료 게이트**):
  - **Environment: Windows-browser** (실제 Windows Chrome/148 via `bin/win-browser.py` 무권한 relay `bridge_mode: relay`, https://localhost:18080, self-signed ignore). WSL headless 아닌 실제 Windows 화면 검증.
  - **Runner: AI** (bin/win-browser.py doctor → launch → eval → screenshot)
  - **Bridge:** relay (무권한 userspace relay 자동 기동, endpoint: http://172.28.64.1:9223)
  - **검증 내용:**
    - DOM eval — `.message-meta-duration` span 존재 확인: `{"totalMeta":2,"withDuration":1,"assistantMessages":1}` — assistant 말풍선 1개에만 소요시간 표시, user 말풍선에는 미표시(정상).
    - 소요시간 텍스트: `"38초"` (formatElapsed 형식 일치).
    - fullText 확인: `"Assistant · 2026. 06. 10. 오전 11:06 38초"` — 타임스탬프 바로 옆에 붙어 표시.
  - **Evidence:** `/tmp/win-browser-shots/task0197_zoomed.png` (2× 줌, 빨간 outline 하이라이트 — "Assistant · 2026. 06. 10. 오전 11:06 **38초**" 명확 확인)
  - **Pass/Fail: PASS**
  - **Notes:** `.message-meta-duration { font-size:10px; opacity:0.7 }` 스타일 적용, 캐시버스터 `?v=20260610-response-duration` 확인. CHECK#13(PB-0008 Windows-browser) **충족**.

- 2026-06-10 (TASK-0198 LLM 사용량 모델별 분리/선택 + 모델별 요약 카드 + 좌우 스크롤 제거 — **PB-0008 Windows-browser 완료 게이트**):
  - **Environment: Windows-browser** (실제 Windows Chrome/148.0.7778.217 via `bin/win-browser.py` 무권한 relay `bridge_mode: relay`, https://localhost:18080, self-signed ignore). WSL headless 아닌 실제 Windows 화면 검증.
  - **Runner: AI** (bin/win-browser.py launch → run --scenario → eval → screenshot)
  - **Bridge:** relay (무권한 userspace relay 자동 기동, endpoint: http://172.28.64.1:9223)
  - **Scenario:** `unit/feature-0003-agent-web-ui/tests/win-browser-task0198-usage.scenario.json` (22 steps, 인증된 admin 세션 — `console.usage.read`)
  - **배포:** 이 worktree 코드로 web 이미지 재빌드(`docker compose -p repo build web`, sha 갱신) + `up -d --no-deps --force-recreate web`. cert(`make web-tls-cert`) 생성 후 TLS 모드 기동(`--ssl-keyfile/--ssl-certfile`). 서빙 자산 캐시버스터 `?v=20260610-usage-model-filter2` 확인, healthz status:ok(mysql/pg ok).
  - **검증 내용 (전 step ok:true, scenario ok:true):**
    - **모델별 분리 (A):** 모델 필터 칩 6개(전체 + edge/gemma4:e2b/claude-haiku-4/claude-sonnet-4, 각 토큰 수·색 dot), scope "전체 모델", 모델별 분리 카드 **4개** 렌더 — `{"chips":6,"mcards":4,"scope":"전체 모델"}`.
    - **모델 선택 (A):** 칩 클릭 → `{"scope":"선택 1개 모델","activeChips":1}` — 요약 합계 카드·모델별 카드·일별 stacked·도넛(100.0%)이 선택 모델(edge: 요청 27/호출 19,616/토큰 11,557,309) 기준으로 재계산. 전체 칩 복귀·모델 카드 클릭 solo 선택 모두 동작.
    - **좌우 스크롤 제거 (C):** usage pane `overflowX:"hidden"`, `userCanScrollHorizontally:false` — 사용자가 가로로 스크롤 **불가** 확정. 세로 스크롤바(`vbarPx:15`)만 존재(콘텐츠 길이상 정상). `scrollW 972 vs clientW 966` 6px 차이는 세로바 폭으로 인한 것이며 overflow-x:hidden 으로 클리핑/스크롤 안 됨 — 위양성 아님.
  - **Evidence:** `/tmp/win-browser-shots/task0198/03_summary_model_cards.png` (전체 모델 — 칩 바·합계 카드·모델별 4카드·일별/도넛 차트, 가로 스크롤바 부재), `04_one_model_selected.png` (edge 단독 선택 — 합계·카드·차트 모두 edge 기준 재계산, 도넛 100%).
  - **Pass/Fail: PASS**
  - **Notes:** 백엔드/API/스키마/RBAC/시크릿 무변경(기존 `/api/admin/usage` 응답 클라이언트 재계산). 모델 키 `COALESCE(resolved_model,model)`. 부분 선택 시 역할·계정 요청·호출은 모델 횡단 분해 불가라 `—` 표기(토큰·비용은 정확). CHECK#13(PB-0008 Windows-browser) **충족**.

- 2026-06-11 (TASK-0204 LLM 사용량 '모델별' 카드 제거 + 모델 칩 토큰수 제거 — **PB-0008 Windows-browser 완료 게이트**):
  - **Environment: Windows-browser** (실제 Windows Chrome/148.0.7778.217 via `bin/win-browser.py` 무권한 relay `bridge_mode: relay`, https://localhost:18080, self-signed ignore). WSL headless 아닌 실제 Windows 화면 검증.
  - **Runner: AI** (bin/win-browser.py launch → goto → click → eval → screenshot)
  - **배포:** main `e51a836` 로 web 이미지 재빌드(`make dc-build SERVICE=web`) + `up -d --no-build web`. 베이킹 `admin-usage-mcards`=0, 서빙 캐시버스터 `?v=20260611-usage-no-mcards`, healthz `git_commit=e51a836`(mysql/pg ok).
  - **결함 재현(수정 전, TASK-0202):** 모델 카드 클릭 시 비선택 3카드 즉시 소실 + 빈 공간 — `02_solo_hover.png`(선택 직후 visible:1/dimmed:3, 커서가 카드 위인데도 collapse). 근본원인=re-render 후 새 노드 `:hover` 미부여로 동기 회수 로직 오발동.
  - **검증 내용(수정 후, 전 step ok:true):**
    - 모델별 카드 부재: `{"mcards":0,"mcardsHead":0}` — 카드 그리드·"모델별" 헤더 완전 제거.
    - 칩 모델명만: `{"chips":5,"chipTok":0,"firstChipText":"edge","allChipText":"전체"}` — 버튼 내 토큰수 0, 모델명/`전체`만.
    - 칩 토글 정상: edge 칩 클릭 → `{"scope":"선택 1개 모델","activeChips":1,"mcards":0,"donutHasData":true}`(필터된 도넛/차트 재계산, 카드 재등장 없음), `전체` 복귀 → `{"scope":"전체 모델"}`.
  - **Evidence:** `/tmp/win-browser-shots/task0204/01_usage_no_mcards.png`(칩 모델명만·카드 부재·요약+차트 정상), `02_chip_filter.png`(edge 필터). 결함 비교: `/tmp/win-browser-shots/task0202/02_solo_hover.png`.
  - **Pass/Fail: PASS**
  - **Notes:** hover 결합 잭 제거 확인 — 카드가 없어 마우스 이동 시 깜빡임/레이아웃 점프 없음. CHECK#13(PB-0008 Windows-browser) **충족**.

- 2026-06-11 (TASK-0206 쿼리 문자열 항상 표시 + 실행결과셋 기본 숨김 토글 — **PB-0008 Windows-browser 완료 게이트**):
  - **Environment: Windows-browser** (실제 Windows Chrome/148.0.7778.217 via `bin/win-browser.py` 무권한 userspace relay `bridge_mode: relay`, https://localhost:18080, self-signed ignore). WSL headless 아닌 실제 Windows 화면 검증.
  - **Runner: AI** (bin/win-browser.py launch → run --scenario → eval + screenshot)
  - **Bridge:** relay (무권한 userspace relay 자동 기동, endpoint: http://172.28.64.1:9223)
  - **배포:** `docker compose up -d web`(신규 이미지 sha 갱신) + 컨테이너 healthy 확인. 서빙 `app.js` — `collapseSqlCodeBlocksInContent`가 빈 함수(토글 로직 0), `buildSqlStepPanel`에서 결과셋 토글 래퍼 확인. healthz 200 OK.
  - **검증 내용 (전 step ok:true):**
    - **초기 DOM 상태:** `{"sqlBlockCount":1,"visibleSqlBlocks":1,"toggleWrapCount":1,"resultToggleWrapCount":1,"resultBodyCount":1,"resultBodyHiddenCount":1,"queryViewBtnCount":1,"queryViewBtnTexts":["결과 보기"]}` — SQL 블록 1개 **기본 표시**, 결과셋 1개 **기본 숨김**, 버튼 텍스트 "결과 보기"(구 "쿼리 보기" 아님).
    - **"결과 보기" 클릭 후:** `{"resultBodyCount":1,"resultBodyHiddenCount":0,"btnTexts":["결과 닫기"]}` — 결과셋 **펼쳐짐**, 버튼 텍스트 "결과 닫기"로 토글.
  - **Evidence:** `/tmp/win-browser-shots/step_01_20260611_123131.png`(SQL 블록 기본 표시·"결과 보기" 버튼), `/tmp/win-browser-shots/step_03_20260611_123146.png`(클릭 후 결과셋 펼쳐짐·"결과 닫기" 버튼).
  - **Pass/Fail: PASS**
  - **Notes:** 쿼리 문자열 항상 표시(숨김 로직 0), 결과셋 기본 숨김·클릭 토글 정상 동작. CHECK#13(PB-0008 Windows-browser) **충족**.

- 2026-06-11 (TASK-0207 관리 콘솔 데이터소스 pane list-detail UI 표준화 + 수정/삭제 노출 — **PB-0008 Windows-browser 완료 게이트**):
  - **Environment: Windows-browser** (실제 Windows Chrome/148.0.7778.217 via `bin/win-browser.py` 무권한 userspace relay `bridge_mode: relay`, https://localhost:18080, self-signed ignore). WSL headless 아닌 실제 Windows 화면 검증.
  - **Runner: AI** (bin/win-browser.py doctor → launch → click → eval → screenshot)
  - **Bridge:** relay (endpoint: http://172.28.64.1:9223)
  - **배포:** PR #144 → main `20a826d` 머지 → `make dc-build SERVICE=web` + `docker compose up -d --no-build web`. healthz `git_commit:20a826d` mysql_ok/pg_ok, 컨테이너 healthy. 서빙 `admin.js` 신규 코드(`_dsRenderDetail`×7·`admin-list-row--nav`·`datasourceList`) 베이킹 + 구 `admin-ds-list`/`datasourcesPane` 0건 확인. 캐시버스터 `?v=20260611-ds-admin-ui`.
  - **검증 내용 (전 step ok:true):**
    - **pane 구조:** `{"paneActive":true,"listExists":true,"detailExists":true,"rowCount":1,"count":"1","tabCount":"1","newBtn":true,"oldFlat":false}` — 다른 카테고리와 동일한 list-detail 5단 구조로 렌더, 구 평면 `.admin-ds-list` 제거 확인. 탭 배지·목록 카운트 wiring 동작.
    - **상세(read view):** 행 클릭 → `{"title":"winsql","badges":["mssql",".env 읽기전용"],"kvPairs":6,"actionButtons":["연결 테스트"]}` — 연결 좌표·출처·보안 kv 6쌍 렌더. 본 datasource 는 `.env` 출처(읽기전용)이라 **수정/삭제 미노출(테스트만)** + 읽기전용 사유 안내(".env 출처 데이터소스입니다 — 콘솔에서 수정/삭제할 수 없습니다.") 표시 — RBAC/editable 게이트 정상.
    - **생성/편집 폼:** "+ 새 데이터소스" 클릭 → `{"formTitle":"새 데이터소스","fieldCount":7,"fields":["키…","엔진…","호스트","포트","DB 유저…","비밀번호","기본 참조 DB…"],"buttons":["생성","취소"]}` — 7필드 폼 + 생성/취소 렌더(편집도 동일 폼 사용 → 수정 UI 동시 검증). 실 생성은 미수행(라이브 무변경).
  - **Evidence:** `artifacts/ds-admin-ui-1-list.png`(목록+빈 상세), `artifacts/ds-admin-ui-2-detail.png`(선택 datasource 상세 — 연결좌표·출처·보안·연결 테스트), `artifacts/ds-admin-ui-3-form.png`(새 데이터소스 폼).
  - **Pass/Fail: PASS**
  - **Notes:** 데이터소스 pane 이 계정/역할/제품/설정 과 동일한 list-detail 외관으로 통일. 수정/삭제는 editable(DB 출처) datasource 의 상세 sticky 액션바에 노출(`.env` 출처는 정책상 읽기전용). CHECK#13(PB-0008 Windows-browser) **충족**.

- 2026-06-11 (TASK-0213 접근 가능 DB picker — dropdown+checkbox 연속 토글 UI — **PB-0008 Windows-browser 완료 게이트**):
  - **Environment: Windows-browser** (실제 Windows Chrome/148.0.7778.217 via `bin/win-browser.py` 무권한 userspace relay `bridge_mode: relay`, https://localhost:18080, self-signed ignore). WSL headless 아닌 실제 Windows 화면 검증.
  - **Runner: AI** (bin/win-browser.py doctor → launch → click → screenshot)
  - **Bridge:** relay (endpoint: http://172.28.64.1:9223)
  - **배포:** PR #151 → main `9d8d33e` 머지 → `docker compose build web` + `docker compose up -d --no-build web`. `grep -c db-picker-checkbox admin.html` = 2, `grep -c admin-db-picker-wrap admin.js` = 1 확인.
  - **검증 내용 (전 step ok:true):**
    - **제품 상세 화면:** 킹스레이드(KR) 클릭 → `접근 가능 데이터베이스` 섹션에 `+ 데이터베이스 선택` 버튼 렌더. 구 `<select>+추가` 버튼 없음 확인.
    - **체크박스 드롭다운:** `+ 데이터베이스 선택` 클릭 → 드롭다운 패널 오픈, `BackupManager` / `DBFunctor` / `distribution` 등 체크박스 항목 목록 표시 확인. 시스템 DB(`master`/`model`/`msdb`) 는 고정칩으로 표시되고 드롭다운 목록에 미노출.
  - **Evidence:** `/tmp/pb0008_product_detail.png`(제품 상세 — "+ 데이터베이스 선택" 버튼), `/tmp/pb0008_picker_open.png`(체크박스 드롭다운 오픈 — 항목 목록 표시).
  - **Pass/Fail: PASS**
  - **Notes:** 캐시버스터 `?v=20260611-db-picker-checkbox` 서빙 확인. 체크박스 연속 토글(추가버튼 없이 즉시 draft 반영) 구조. CHECK#13(PB-0008 Windows-browser) **충족**.

- 2026-06-11 (TASK-0223 제품별 insight-worker 분석 완료율 UI — **PB-0008 Windows-browser 완료 게이트**):
  - **Environment: Windows-browser** (실제 Windows Chrome/148.0.7778.217 via `bin/win-browser.py` 무권한 userspace relay `bridge_mode: relay`, https://localhost:18080, self-signed ignore). WSL headless 아닌 실제 Windows 화면 검증.
  - **Runner: AI** (doctor → launch → run --scenario `tests/win-browser-task0223.scenario.json` + 단발 click/eval/screenshot)
  - **Bridge:** relay (endpoint: http://172.28.64.1:9223)
  - **배포:** PR #161 → main `b46cbd4` 머지 + hotfix `cde2610`(_log→logging) + `0e37b8e`(conversation_id `__global__`) → `make dc-build SERVICE=web` + `docker compose up -d --no-build web`. healthz git_commit=`0e37b8e` 베이킹 확인.
  - **검증 내용 (시나리오 step1~10 ok:true):**
    - **제품 목록 배지:** 4개 제품 row 에 분석 완료율 배지 렌더 (eval 추출): 킹스레이드(KR)=`분석 100%`(cov-ok 녹색), 마이크로볼츠(MV)=`분석 100%`, 건즈 국내(GZ_KR)=`분석 100%`, DK온라인(DK)=`분석 측정 불가`(cov-muted — MSSQL `mssql_local` 연결실패 graceful).
    - **제품 상세 breakdown:** 킹스레이드 클릭 → `접근 가능 데이터베이스` 섹션에 `insight 분석 완료율` 블록: 요약 `100%`, 진행바 `389 / 389 객체 (DB + 테이블)`, per-DB `dbauth=테이블 9/9 · DB✓`, `dbgame=테이블 98/98 · DB✓`, `dblog=테이블 279/279 · DB✓`.
    - **라이브 API 실측:** `GET /api/admin/products/insight-coverage` — product 1/7/8(MySQL)=100% (analyzed=total), product 91(MSSQL)=measurable:false(graceful, 500 없음).
  - **Evidence:** `/tmp/win-browser-shots/task0223/01_list_badges.png`(목록 — 3× 녹색 `분석 100%` + 1× `분석 측정 불가`). 상세 screenshot 은 relay CDP transient(font-load 후 timeout)로 미캡처되나 구조 검증은 eval 로 확정.
  - **Pass/Fail: PASS**
  - **Notes:** 캐시버스터 `?v=20260611-insight-coverage` 서빙. 분자=PG rag_objects(`__global__`/`common`) ∩ 라이브 카탈로그 set 교집합, datasource scope=엔드포인트 해시(+기본 엔드포인트 NULL 폴백). CHECK#13(PB-0008 Windows-browser) **충족**.

- 2026-06-11 (TASK-0229 제품 상세 "접근 가능 데이터베이스" UI 통합 — **PB-0008 Windows-browser 완료 게이트, 인증 후 시각검증 PASS**):
  - **Environment: Windows-browser** (실제 Windows Chrome/148.0.7778.217 via `bin/win-browser.py` 무권한 userspace relay `bridge_mode: relay`, endpoint `http://172.28.64.1:9223`, self-signed ignore). WSL headless 아닌 실제 Windows 화면.
  - **Runner: AI** (doctor → launch → `/api/auth/login`(bootstrap_admin) → goto `/admin` → 제품 탭 → 제품 선택 → eval 구조검증 + screenshot)
  - **배포:** main `997d9ec`(PR #167 TASK-0229 + PR #166 SSRF + PR #168 멀티 datasource 머지본). healthz status=ok, git_commit=`997d9ec`, mysql_ok/pg_ok. 라이브 정적 자산 — `admin.js?v=20260611-product-multi-ds`(PR #168 이 캐시버스터 갱신, 내 통합 UI 코드는 그 안에 공존) 에 `buildSystemDbChip`/`buildDbCoverageCells`/`cov-db-wrap`(grep 5 매치), `styles.css` 에 `sysdb-chip`/`cov-microbar`(19 매치).
  - **검증 내용 (인증 후 실제 화면):**
    - **로그인:** `/api/auth/login`(bootstrap_admin/admin role) status 200, 세션 쿠키 설정.
    - **제품 목록:** `관리 콘솔 > 제품` 5개 row, 각 `분석 N%` 배지 렌더.
    - **문제1 해소(1:1 중복 통합) — PASS:** 킹스레이드(KR) 선택 → `접근 가능 데이터베이스` 섹션이 (a) 요약 헤더(`insight 분석 완료율` `100%` 배지 + 전체 진행 바 `389/389 객체` + 새로고침) + (b) **통합 리스트** 3행으로 렌더. 각 행(eval 추출): `dbauth 9/9 DB✓` / `dbgame 98/98 DB✓` / `dblog 279/279 DB✓` — per-DB 진척(마이크로바+통계+상태칩)이 사용자 DB chip 과 **한 행으로 통합**됨(구 per-DB breakdown 리스트 별도 표시 사라짐, `old_breakdown_in_covDetail:false`).
    - **문제2 해소(시스템 DB 묶음) — PASS:** 시스템/메타데이터 4종이 단일 칩 `시스템 DB 4개` + `고정` 태그로 묶임. `tabindex=0`, `title`=개행 구분 4개 목록(`information_schema`/`mysql`/`sys`/`performance_schema`), `aria-label`=동일 목록 1줄, **focus 시 커스텀 툴팁 `visibility:visible`** + 툴팁 카드에 4개 DB 목록 — 마우스 hover·키보드 focus·터치 tap 모두 개별 이름 확인 가능(접근성 3중).
    - **MSSQL 제품(DK/FH):** `시스템 DB 3개` 묶음 칩(master/model/msdb) 정상.
  - **Evidence:** `artifacts/task0229-product-db-unified.png`(킹스레이드 제품 상세 — 요약 헤더 100% + dbauth/dbgame/dblog 통합 리스트(9/9·98/98·279/279·DB✓·×) + `시스템 DB 4개·고정` 칩 + focus 툴팁 카드 펼침), `artifacts/task0229-admin-login.png`(로그인 화면).
  - **Pass/Fail: PASS** (문제1 통합 리스트 + 문제2 시스템 묶음 칩 + 접근성 툴팁 전부 실제 Windows 화면에서 확인).
  - **Notes:** 첫 탐색 시 `db_row_count:0` 관측됐으나 이는 브라우저 세션의 stale `productDbDraft` 캐시(이전 탐색 잔재) 탓 — 완전 새로고침 후 3행 정상 렌더 확인. 라이브 데이터 정합 검증: `/api/admin/products` 의 KR `databases[].datasource_key` = `mysql-local`(전 행), `datasources`=[mysql-local primary] → `_serverDbsFor` 매칭 정상(PR #168 멀티 datasource 차원 모델과 정합, 회귀 없음). CHECK#13(PB-0008 Windows-browser) **충족**.

- 2026-06-12 (TASK-0242 제품 데이터소스 — DB별 insight 파악 내용 한 줄 인라인 + 추가 picker 분석상태 — **PB-0008 Windows-browser 완료 게이트, 인증 후 시각검증 PASS**):
  - **Environment: Windows-browser** (실제 Windows Chrome/148.0.7778.217 via `bin/win-browser.py` 무권한 userspace relay `bridge_mode: relay`, endpoint `http://172.28.64.1:9223`, https://localhost:18080, self-signed ignore). WSL headless 아닌 실제 Windows 화면.
  - **Runner: AI** (doctor → `/api/auth/login`(bootstrap_admin) → goto `/admin` → 제품 탭 → 제품 선택 → eval 구조검증 + screenshot)
  - **Scenario:** `unit/feature-0003-agent-web-ui/tests/win-browser-task0242-db-insights.scenario.json` (19 steps, 인증된 admin 세션)
  - **배포:** main `f815335`(PR #182 머지본) → `make dc-build SERVICE=web` + `docker compose up -d --no-build web`. healthz git_commit=`f815335`, mysql_ok/pg_ok, insight_heartbeat_age=7s(worker fresh). 서빙 자산 `admin.js?v=20260612-db-insight-surface`(신규 함수 `buildDbRoleCell`/`buildPickerInsightMeta`/`loadProductDbInsights` 6 매치).
  - **검증 내용 (전 19 step ok:true, scenario ok:true):**
    - **로그인:** `/api/auth/login`(bootstrap_admin) `login_ok:true`, `/admin` 200.
    - **등록 DB 행 한 줄 인라인 (요청①③④) — PASS:** 킹스레이드(KR) 선택 → datasource accordion `mysql-local`(기본) 펼침 아래 `.cov-db-row` **3행, 전부 role 셀 채워짐**(`rowCount:3, populatedRoleCount:3`). 각 행 = [DB명 · insight-worker 설명 · 분석률 마이크로바 · 객체 N/N · DB✓ · 초기화 · ×] 단일 라인(eval 추출): `dbauth | Account/Auth — Schema containing account authentication and profile data… | 9/9`, `dbgame | Game Data — This schema contains game progression tables… | 98/98`, `dblog | Game Logs — This schema logs detailed user actions… | 279/279`. 설명은 overflow ellipsis 한 줄, 전문은 hover title. **별도 펼침 버튼 없음**(사용자 지시 반영).
    - **추가 picker 분석상태 (요청②③④) — PASS:** `+ 데이터베이스 추가` 클릭 → 드롭다운 13항목, 각 [☐ DB명 · 도메인 힌트 · 분석상태 칩]. `stateCounts={"분석됨":13}`(전부 is-done, mysql-local 전 DB 분석 완료). 예: `__invalid_default_db__·Global/Server·분석됨`, `account_db·Account/Auth·분석됨`, `dbauth·Account/Auth·분석됨`(체크됨), `dbgame·Game Data·분석됨`(체크), `dblog·Game Logs·분석됨`(체크), `dbresult·Game Data·분석됨`. 클리핑 없이 inline 정상 흐름(TASK-0240 fix 위 공존).
    - **라이브 API 실측:** `GET /api/admin/products/{1,8}/db-insights`(MySQL)=ok, account_db 13객체(schema+12T) domain Account/Auth + 실 설명; `/91/db-insights`(MSSQL)=ok, dbo **373객체**(schema+372T), dev50 1객체(미분석 → "No schema… information"). worker `{alive:true,age_sec:2,status:ok}`.
  - **Evidence:** `/tmp/win-browser-shots/task0242/01_db_rows_role_inline.png`(제품 상세 — 데이터소스 섹션·완료율 100%·mysql-local accordion), `/tmp/win-browser-shots/task0242/02_add_picker_status.png`(DB 3행 한 줄 인라인 설명 `Account/Auth — Schema c…`/`Game Data — …`/`Game Logs — …` + 9/9·98/98·279/279·DB✓·초기화·× + picker 13항목 도메인힌트·분석됨 칩).
  - **Pass/Fail: PASS** (등록 DB 행 한 줄 인라인 설명 + 추가 picker 도메인 힌트·분석상태 전부 실제 Windows 화면에서 확인. 콘솔/pageerror runner ok:true).
  - **Notes:** '분석중'/'미분석' 칩은 분석 객체 0 + worker alive/미alive 조건이라 라이브(전 DB 분석완료)에서는 '분석됨'만 관측 — 3-state 로직은 단위테스트(test_db_insights 14)로 커버. CHECK#13(PB-0008 Windows-browser) **충족**.

- 2026-06-12 (TASK-0243 MSSQL db-insights catalog 귀속 수정 — **PB-0008 Windows-browser 완료 게이트, MSSQL 제품 시각검증 PASS + MySQL 무회귀 대조**):
  - **Environment: Windows-browser** (실제 Windows Chrome/148.0.7778.217 via `bin/win-browser.py` 무권한 userspace relay `bridge_mode: relay`, endpoint `http://172.28.64.1:9223`, https://localhost:18080, self-signed ignore). WSL headless 아닌 실제 Windows 화면.
  - **Runner: AI** (doctor → launch(relay 재기동) → `/api/auth/login`(bootstrap_admin) → goto `/admin` → 제품 탭 → **DK온라인(MSSQL) 선택** → eval 구조검증 + screenshot)
  - **Scenario:** `unit/feature-0003-agent-web-ui/tests/win-browser-task0243-mssql-db-insights.scenario.json` (17 steps, 인증된 admin 세션, MSSQL 제품)
  - **배포:** main `ed09a53`(PR #184 머지본) → `make dc-build SERVICE=web` + `docker compose up -d --no-build web`. healthz git_commit=`ed09a53`, mysql_ok/pg_ok.
  - **진단(수정 전 결함):** TASK-0242 의 `_compute_product_db_insights` 가 by_db 를 `rag_objects.schema_name` 으로 묶었는데 MSSQL 은 schema_name=`dbo`(SQL스키마)라 등록 DB(catalog)와 차원이 달라 라이브 제품91 by_db=`['dbo','dev50']` — 등록 DB(GameLog_100/dk_data_release/…)와 무교집합 → MSSQL 등록 DB 행 전부 "역할 미파악". MySQL 은 db==schema 라 정상이었음.
  - **검증 내용 (전 17 step ok:true, scenario ok:true):**
    - **MySQL 무회귀(사용자 요청 — 키 수정 side-effect):** 배포 전/후 제품1(MySQL) `GET .../db-insights` by_db 키 집합 20개 **byte-identical**(diff 0). 그룹핑 분기를 engine=='mssql' 에만 적용하고 MySQL 은 schema_name 직접 사용.
    - **MSSQL 등록 DB 행 역할 표면화 — PASS:** DK온라인(제품91, mssql_local) 선택 → `.cov-db-row` **5행 전부 role 셀 채워짐**(`engine:mssql, rowCount:5, populatedRoleCount:5` — 수정 전이면 0). 각 행 한 줄 인라인(eval): `GameLog_100 | Game Data — This schema appears to store detailed information related to player… | 37/37`, `GameLog_151 | Account/Auth — … | 37/37`, `dk_data_release | Game Data — … | 123/123`, `dk_server_info | Global/Server — … | 1/1`, `GameLogManager | Game Logs — … | 7/7`. by_db 키가 catalog(GameLog_100 등) 단위로 묶여 등록 DB 와 lowercase 매칭.
    - **picker 3-state 실증(MySQL 검증서 못 본 상태):** `+ 데이터베이스 추가` → 10항목, `stateCounts={"분석중":5,"분석됨":5}`. insight 보유 DB(dk_data_release·dk_server_info·GameLog_100·GameLog_151 = 도메인 표시 + **분석됨**), insight 미보유 + worker alive DB(BackupManager·DBFunctor·distribution = **분석중**). 시스템 DB 3개(master/model/msdb) 고정 묶음 칩.
  - **Evidence:** `/tmp/win-browser-shots/task0243/01_mssql_db_rows_role.png`(DK온라인 제품 상세 — 데이터소스 섹션·완료율 100%·210/210·MSSQL note), `/tmp/win-browser-shots/task0243/02_mssql_add_picker.png`(MSSQL 5행 한 줄 인라인 역할 `Game Data — …`/`Account/Auth — …`/`Global/Server — …`/`Game Logs — …` + 37/37·123/123·1/1·7/7 + picker 분석중[노랑]/분석됨[초록] 3-state + 시스템 DB 3개 고정칩).
  - **Pass/Fail: PASS** (MSSQL 등록 DB 5행 역할 한 줄 인라인 + picker 3-state[분석중/분석됨] 실제 Windows 화면 확인, MySQL by_db 키 byte-identical 무회귀).
  - **Notes:** side-effect 격리(사용자 요청) — coverage(완료율)·insight-reset 은 object_key 미사용(schema_name/table_name 컬럼)이라 무영향, 전체 make test 회귀 0, 적대적 subagent SHIP. CHECK#13(PB-0008 Windows-browser) **충족**.

- 2026-06-12 (TASK-0245 제품 상세 접근가능 DB 리스트 행 컬럼 폭 정합 — **PB-0008 Windows-browser 완료 게이트**):
  - **Environment: Windows-browser** (실제 Windows Chrome/148.0.7778.217 via `bin/win-browser.py` 무권한 userspace relay `bridge_mode: relay`, https://localhost:18080, self-signed ignore). WSL headless 아닌 실제 Windows 화면 검증.
  - **Runner: AI** (bin/win-browser.py goto → click → eval(좌표 측정) → screenshot)
  - **배포:** PR #189 → main `2bc2067` 머지 → `make dc-build SERVICE=web` + `docker compose up -d --no-build web`. healthz `git_commit:2bc2067`, 서빙 `styles.css` 에 신규 grid(`minmax(96px,0.9fr) … 96px 54px 76px 60px 24px`) 베이킹 확인. 캐시버스터 `?v=20260612-db-row-align`.
  - **검증 내용 (객관 좌표 측정 — 제품 92 "출조낚시왕(FH)" / datasource mssql-qa-idc, cov-db-row 8행):**
    - 각 행의 컬럼 시작 x(`getBoundingClientRect().left`) 측정 — **전 8행 spread=0px**: 역할설명(`.cov-db-role`) left=770, 진척바(`.cov-microbar`) left=816, 통계(`.cov-db-stat`) left=922, 상태칩(`.cov-db-status`) left=986, 초기화(`.cov-db-reset`) left=1072. 문자열 길이(FHDef↔fh_ods↔FHGame1, 역할 Gam…↔Acco…)와 무관하게 **모든 컬럼이 행 간 동일 좌표 정렬**.
    - 수정 전: 통계·상태·초기화 `auto` 컬럼이 행마다 폭을 달리해 name/role(fr) 컬럼이 어긋나며 spread>0(들쭉날쭉). 수정 후 고정폭 트랙으로 spread=0.
  - **Evidence:** `artifacts/db-row-align-after.png` (제품 상세 DB 리스트 8행 — DB명·역할·진척바·상태칩·초기화·× 전 컬럼 수직 정렬 일치).
  - **Pass/Fail: PASS**
  - **Notes:** 순수 CSS grid 트랙 고정(`.cov-db-row` auto→고정폭 + justify-self:start). 행 콘텐츠·셀 빌더·권한 무변경. CHECK#13(PB-0008 Windows-browser) **충족**.

- 2026-06-12 (TASK-0251 공유 페이지 SQL "쿼리 열고닫기" 토글 → "실행 쿼리 전환" navigator 교정 — **PB-0008 Windows-browser 완료 게이트, 익명 공유뷰**):
  - **Environment: Windows-browser** (실제 Windows Chrome/148.0.7778.217 via `bin/win-browser.py` 무권한 userspace relay `bridge_mode: relay`, endpoint `http://172.28.64.1:9223`, 라이브 공유 URL `https://112.185.196.20:18080/share/{token}`, self-signed ignore). WSL headless 아닌 실제 Windows 화면. **익명(비로그인) 접근** — 쿠키 임포트 불요.
  - **Runner: AI** (bin/win-browser.py launch/goto → eval(DOM 검사·nav-btn click hit-test) → screenshot)
  - **배포:** PR #202 → main `9cee54a` 머지 → `docker compose build web` + `up -d --no-deps web`. 서빙 `/app/web/app.py` 에 `_share_sanitize_step`/`_share_attach_sanitized_steps` 베이킹 확인(grep 6), 서빙 `share.html` 캐시버스터 `?v=20260612-share-sql-nav` 확인. healthz 200(mysql_ok/pg_ok).
  - **검증 내용 (라이브 2개 공유 토큰):**
    - **① 사용자 보고 토큰** (`tDuTZ…`, 대화 20260612055236, steps 없음 + 본문 ```sql``` 보유): `.share-sql-toggle-btn` **0개**(열고닫기 토글 완전 부재), 본문 "쿼리 보기/닫기/열기" 라벨 **없음**, `.share-message-content pre` **5개 전부 펼쳐 가시**(visiblePre=5/5). → 사용자가 보고한 "쿼리 열기" 버튼 제거 + 본문 SQL 항상 표시 확인.
    - **② 실행단계 보유 토큰** (`xGXRt…`, 대화 20260527044221, 8 execute_sql): `.share-sql-navigator` **1개**, 인디케이터 **"쿼리 1/8"**, nav-btn 2개(◀▶). **▶ click hit-test**: "쿼리 1/8"→"2/8" 전환(activeIdx 0→1) + 활성 패널 결과 테이블 가시. 끝까지 ▶ → "쿼리 8/8" + ▶ disabled, ◀ 복귀 → "쿼리 1/8" + ◀ disabled. 8개 패널 SQL 실측: `SHOW TABLES … '%login%'`×3 / `'%event%'`×3 / `SELECT COUNT(*) … atten…`×2 — **결과셋별 실행 쿼리 전환 동작 확인**. 토글 0·라벨 없음.
  - **익명 노출 경계(라이브 API 직접):** 응답 직렬화에 `result_summary.csv_paths`(서버 `/shared/` 경로) **0**, bare `preview` 키 **0**, step 키 = `{intent,reason,result_summary,sql,tool,work}`, result_summary 키 = `{preview_table}`만 — `_share_sanitize_step` 화이트리스트 라이브 적용 확인.
  - **Pass/Fail: PASS**
  - **Notes:** 사용자 의도("쿼리 열고닫기"가 아닌 "결과셋에 따라 실행 쿼리 전환") 정확 구현 — steps 없는 대화는 본문 SQL 펼침, steps 있는 대화는 navigator 전환. 익명 노출 sanitize 라이브 검증(csv_paths/preview/args/error 0). CHECK#13(PB-0008 Windows-browser) **충족**.

- 2026-06-15 (TASK-0256 assistant 답변 markdown ```diff 블록 — **PB-0008 Windows-browser 완료 게이트, 렌더 시각검증 PASS**):
  - **Environment: Windows-browser** (실제 Windows Chrome/148.0.7778.217 via `bin/win-browser.py` 무권한 userspace relay `bridge_mode: relay`, endpoint `http://172.28.64.1:9223`, https://localhost:18080, self-signed ignore). WSL headless 아닌 실제 Windows 화면.
  - **Runner: AI** (win-browser.py launch → eval(배포 markdownToHtml 로 샘플 diff 주입·DOM 검사·getComputedStyle) → screenshot)
  - **Steps/Result:** 배포 자산(app.js?v=20260615-task0256-diff) 의 전역 `markdownToHtml`/`enhanceDiffBlocks` 에 샘플 리뷰 답변(```diff: `- SELECT *` 삭제 / `+ 필요컬럼 + 삭제행제외` 추가)을 `.message-content` 로 주입 → `pre.diff-block`=1, `.diff-add`=1(getComputedStyle color `rgb(158,206,106)` 초록), `.diff-del`=1(`rgb(247,118,142)` 빨강), 좌측 보더 색 구분. 스크린샷 `/tmp/task0256/pb0008_diff_render.png` 육안: 삭제라인 빨강·추가라인 초록 명확.
  - **Pass/Fail: PASS**
  - **Notes:** 렌더(시각) 검증 — 라이브 배포 자산의 실제 파이프라인(marked.parse→enhanceDiffBlocks→DOMPurify.sanitize) 결과를 실제 Windows 화면에서 확인. CSS 팔레트(.message-content pre 다크 #1a1b26 위) 정확 적용. 프롬프트측(assistant diff 생성)은 ask-worker SYSTEM_PROMPT baked + 라이브 WebSystemPrompts global row 갱신으로 보장(별도 LLM e2e 미수행). CHECK#13(PB-0008 Windows-browser) **충족**.

- 2026-06-15 (TASK-0256b diff 블록 줄 이중 줄바꿈 수정 — **PB-0008 Windows-browser 재검증 PASS**):
  - **Environment: Windows-browser** (실제 Windows Chrome/148 via `bin/win-browser.py` 무권한 relay, https://localhost:18080, self-signed ignore). WSL headless 아닌 실제 Windows 화면.
  - **Steps/Result:** 배포 자산(app.js?v=20260615-task0256b-spacing) 의 `markdownToHtml` 로 8줄 diff(2 del + 6 add, EXIT HANDLER 예시) 렌더 → `.diff-line` 8개, lineHeight=20px, **줄 간 top 간격(gap)=[20,20,20,20,20,20,20] = lineHeight 와 동일 = 단일 줄 간격**. 수정 전 이중 줄바꿈(블록 span + 리터럴 `"\n"` ≈ 40px)이 해소됨. 스크린샷 `/tmp/task0256/pb0008b_diff_spacing_fixed.png` 육안: 8줄 빈 줄 없이 연속, +초록/-빨강 색 유지.
  - **Pass/Fail: PASS**
  - **Notes:** `enhanceDiffBlocks` 의 block span 사이 `"\n"` 텍스트 노드 제거 효과 실측(gap==lineHeight). CHECK#13(PB-0008 Windows-browser) **충족**.

- 2026-06-15 (TASK-0256c diff 블록 줄번호(old|new) + 복사 시 마커·번호 제외 — **PB-0008 Windows-browser PASS**):
  - **Environment: Windows-browser** (실제 Windows Chrome/148 via `bin/win-browser.py` 무권한 relay, https://localhost:18080). WSL headless 아닌 실제 Windows 화면.
  - **Steps/Result:** 배포 자산(app.js?v=20260615-task0256c-gutter) 의 `markdownToHtml` 로 8줄 diff(2 del + 6 add, EXIT HANDLER 예시) 렌더.
    - **줄번호 gutter**: `.diff-line` data-gutter = `["1   -","2   -"," 1 +"," 2 +",...]`(del=old번호+빨강 / add=new번호+초록), `getComputedStyle(line,'::before').content` 에 숫자 포함(번호 가시). 스크린샷 `/tmp/task0256/pb0008c_diff_gutter.png` 육안: 각 줄 좌측 old/new 번호 + 색마커 + 구분선.
    - **복사 클린(getSelection 실측)**: `range.selectNodeContents(pre.diff-block)` → `getSelection().toString()` = 8줄, **마커로 시작하는 줄 0(copyHasMarker=false)**, 첫 줄 `"DECLARE v_Result INT DEFAULT 0;"`(마커·번호 없음), 코드 포함. 즉 블록 복사 시 줄번호·+/- 제외된 순수 코드만 잡힘.
  - **Pass/Fail: PASS**
  - **Notes:** 줄번호+마커는 `::before content`(의사요소=선택/복사 비포함) + user-select:none. CHECK#13 충족.

- 2026-06-15 (TASK-0256d HTML 엔트리포인트 no-cache — 캐시버스터 전달 검증 PASS):
  - **Environment: 라이브 curl + Windows-browser** (https://localhost:18080, web main 1c184f8).
  - **Steps/Result:**
    - **헤더(curl GET)**: `/` → `cache-control: no-cache` + ETag, `/admin` → no-cache, `/share/{token}` → no-cache. 서빙 index.html 이 최신 `app.js?v=20260615-task0256c-gutter` 참조. 정적 `/static/app.js?v=...` 은 no-cache 아님(ETag 캐시 가능 — 의도).
    - **브라우저 로드(win-browser eval)**: `typeof window.buildDiffRows="function"`·`stripDiffMarker="function"`, loadedScript=`app.js?v=20260615-task0256c-gutter` → 옛 캐시 깨고 새 자산 로드 확인.
    - **gutter+복사(사용자 유형 SQL diff 렌더)**: `hasGutter=true`, context 줄 data-gutter `"1 1"`, `copyHasMarker=false`, 복사 = `["SELECT","    AID","  , UserID"]`(마커·번호 없는 순수 코드, 들여쓰기 보존). 스크린샷 `/tmp/task0256/pb0008d_nocache_gutter.png`.
  - **Pass/Fail: PASS** — no-cache 가 0256c(줄번호/복사클린)를 사용자에게 전달함을 end-to-end 실증.
  - **Notes:** 기 캐시된 사용자는 1회 하드리프레시(Ctrl+Shift+R)로 no-cache index.html 진입 후 자동 최신. CHECK#13 충족.

- 2026-06-15 (TASK-0274 첨부파일 목록 사이드 패널 너비 조절 — **PB-0008 Windows-browser PASS**):
  - **Environment: Windows-browser** (실제 Windows Chrome/148.0.7778.217 via `bin/win-browser.py` 무권한 userspace relay `bridge_mode: relay`, endpoint `http://172.28.64.1:9223`, https://localhost:18080, self-signed ignore). WSL headless 아닌 실제 Windows 화면. 배포: main `bb06ddf`(PR #241 squash) → `sudo docker compose build web && up -d --no-deps web`(repo-web-1 Up healthy, /healthz mysql_ok·pg_ok true). 서빙 자산 `app.js/styles.css?v=20260615-attach-panel-resize`(resizer 코드 4 hit).
  - **Steps/Result:**
    - **진입 + 핸들 hit-test**: 작업 화면에서 `+`(#composerActionsBtn) 클릭 → "첨부파일 목록"(#composerActionsListItem) 클릭 → `#attachSidePanel` 표시(panelHidden=false, 초기 width=280px, 우측 고정 left=969). `#attachSidePanelResizer` 실재 + `cursor:ew-resize`, rect{x:967,w:8,h:840}. **`document.elementFromPoint(resizer center)` = `attachSidePanelResizer`** → 핸들이 다른 요소에 가려지지 않음(CSS 클리핑/겹침 0).
    - **드래그 너비 변경**: 핸들에 mousedown → document mousemove(좌측 −180px) → 패널 width **280 → 458px** 실시간 변경(`width=innerWidth−clientX` 정확), 드래그 중 `.is-resizing` 적용 → mouseup 후 해제. **`localStorage["web.attachSidePanel.width"]="458"` 저장 확인**.
    - **새로고침 후 복원**: page reload → `+` > 첨부파일 목록 재클릭 → 패널 표시 + **width 458px 복원**(storedWidth 458 → inline `width:458px`). 영속화 end-to-end PASS.
    - **clamp 경계**: 핸들 우측 끝 드래그 → width **240px 에서 정지**(min-width 240). 핸들 좌측 끝 드래그 → **1149px(=92vw, innerWidth 1249) 에서 정지**(max-width 92vw). CSS `min-width:240px`/`max-width:1149.08px` 실측 일치.
    - **시각 evidence**: 스크린샷 `artifacts/pb0008-task0274/attach-panel-resized-458.png` — 우측 "첨부 파일" 패널이 확장 너비로 메인/대화목록과 레이아웃 충돌 없이 렌더. 콘솔 throw 0.
  - **Pass/Fail: PASS** — 핸들 hit-test·드래그 너비 변경·localStorage 저장·새로고침 복원·min/max clamp 전부 실제 Windows 브라우저 실측 통과. (기존 `#stepSidePanel`/`#profileDrawer` 검증 패턴과 동일 동작.)
  - **Notes:** 기 캐시된 사용자는 1회 하드리프레시(Ctrl+Shift+R)로 no-cache index.html 진입 후 자동 최신. CHECK#13(PB-0008 Windows-browser) **충족**.

- 2026-06-15 (TASK-0278 데이터소스 목록 행별 네트워크 상태 배지 — **PB-0008 Windows-browser PASS**):
  - **정적 검증**: `node --check admin.js` PASS, CSS 중괄호 균형. 적대적 코드리뷰(REV-0282, general-purpose outside voice) **SHIP** — grid 스코프 회귀 0(`#datasourceList` ID 특이성 > base, `#settingsList` 미매칭)·leading 배치·async detach 가드(`isConnected`)·캐시우선·중복 probe 0.
  - **Environment: Windows-browser** (실제 Windows Chrome/148.0.7778.217 via `bin/win-browser.py` 무권한 relay `bridge_mode: relay`, endpoint `http://172.28.64.1:9223`, https://localhost:18080, self-signed ignore). 배포: main `73d65b8`(PR #251 squash) → `make dc-build SERVICE=web` + `docker compose up -d --no-build web`(repo-web-1 healthy). 서빙 `admin.js?v=20260615-task0278-ds-conn-badge`(`_paintDsConnDot` 3 hit) + healthz `git_commit=73d65b8`(mysql_ok·pg_ok true).
  - **계측 결과(win-browser eval)**: `관리 콘솔 > 데이터소스` **14행 전부 leading `.ds-conn-dot`**(withDot=14). **행별 도트 `getBoundingClientRect().left=270` 단일값**(컬럼 정렬 완벽). 행 `grid-template-columns: 9px 274px`(auto 도트 컬럼 + 1fr main). 색: `is-ok`=`rgb(22,163,74)` 초록(`--success`) / `is-fail`=`rgb(220,38,38)` 빨강(`--danger`). `title`/`aria-label` 실측("네트워크 상태: 연결됨 · 152.1ms" / "네트워크 상태: 연결 실패: 연결 불안정"). **`#settingsList` 무회귀**: 설정 탭 `grid-template-columns: 308px` 단일(도트 컬럼 없음, `hasDotInSettings=false`) — `#datasourceList` 스코프 grid 가 타 nav 목록 무영향 실증.
  - **시각 evidence**: 스크린샷 `artifacts/pb0008-task0278/ds-conn-badge.png`.
  - **Pass/Fail: PASS** — leading 도트 정렬(left=270 단일)·색 구분(초록/빨강)·접근성(title/aria-label)·grid 스코프(9px 274px)·`#settingsList` 무회귀(308px 단일) 전부 실제 Windows 브라우저 실측 통과. CHECK#13(PB-0008 Windows-browser) **충족**.
- 2026-06-15 (TASK-20260615T183409-ds-list-multiselect 데이터소스 목록 다중 선택 — 정적 검증 PASS / **PB-0008 배포 후 잔여**; PR#251 leading 도트를 행에 통합·행 구조 button→div 로 #251 의 button-row PB-0008 측정 supersede):
  - **Environment: 정적(node + subagent 코드리뷰)** — 변경은 frontend 정적자산(admin.js/admin.html)뿐, 백엔드 엔드포인트(PATCH/DELETE) 재사용이라 Python(make test) 영향 0.
  - **Steps/Result:**
    - **node --check admin.js**: SYNTAX OK (전 편집 후 재확인).
    - **런타임 계약**: `assertBulkBarContract("datasources")` 가 init 루프에서 호출되며 admin.html 의 `#datasourcesBulkBar`(role=toolbar/aria-live/`.admin-list-col` 직속)·ID 정합으로 충족(코드 대조).
    - **적대적 subagent 코드리뷰(general-purpose outside voice)**: 10개 검증항목(partial-fail 분할·재동기화·prune·contract·select-all/indeterminate·shift-range string-key·button→div 회귀·체크박스 stopPropagation·XSS·hoisting·env 제외) 전부 confirmed-correct → **SHIP(BLOCKER 0/MAJOR 0)**. REV-20260615-0286.
  - **Pass/Fail: PASS(정적)** — 구조/계약/로직 검증 완료.
  - **Notes:** **잔여 — PB-0008 Windows-browser**: 배포 후 데이터소스 탭에서 행 체크박스·전체선택(indeterminate)·shift-click 범위·일괄 인사이트 토글·일괄 삭제(env 제외·409 제외 리포트) + leading 도트(통합) 실측 필요. CHECK#13 은 그때 충족. → **아래 항목에서 충족(PASS).**
- **TASK-0277 (데이터소스 라벨/키 분리, Critical §12.3) — 백엔드 전용 회귀 검증.**
  - **Environment: 컨테이너 make test (agent 이미지, --no-deps) + unit(monkeypatch, DB 무)**. UI 표면(HTML/CSS/JS) 변경 **없음** — `app.py` 백엔드 로직(스키마 마이그레이션·rename cascade·바인딩 write·런타임 probe)만 변경.
  - **결과**: 신규 `test_datasource_rename_binding_stable.py` R1~R4 PASS(R1 3 테이블 cascade+고아 사전제거·R2 Id 구동 WHERE·R3 비-rename 무 cascade·R4 DatasourceId 컬럼 부재 시 key-only 완전 cascade) + 기존 `test_datasource_edit_label_stable.py` S1~S3 PASS + `make test` 컨테이너 **전체 회귀 0** + ruff clean + py_compile OK.
  - **외부음성 2-pass(RBAC 적대적)**: 1차 NOT-SHIP(BLOCKER1 probe 미등록+cascade 하드의존 / BLOCKER2 autocommit 비원자 / BLOCKER3 PK 충돌 + MINOR) → 흡수 → 2차 SHIP-WITH-FIXES.
  - **PB-0008 (Windows-browser): N/A — 사유 명시.** 본 변경은 사용자가 보는 UI surface(렌더·레이아웃·상호작용·라벨 표시 문자열·DOM·CSS)를 변경하지 않는다. 효과는 "라벨 rename 후 제품 바인딩·접근DB 유지"라는 **데이터/동작 정합**이며, 시각이 아닌 라이브 기능 라운드트립(rename→GET 재조회로 제품 바인딩 키 갱신·접근 유지)으로 검증한다(배포 후 잔여). CHECK#13 WARN(비차단)은 본 사유로 갈음.
  - **Pass/Fail: PASS** (단위·컨테이너 회귀 + 외부음성 2-pass). 라이브 기능 검증은 배포 후 수행(잔여).

- 2026-06-16 (TASK-20260615T183409-ds-list-multiselect 데이터소스 목록 다중 선택 — **PB-0008 Windows-browser PASS**; CHG/REV-20260615-0289 evidence):
  - **Environment: Windows-browser** (실제 Windows Chrome/148.0.7778.217 via `bin/win-browser.py` 무권한 relay `bridge_mode: relay`, endpoint `http://172.28.64.1:9223`, https://localhost:18080, self-signed ignore). 배포: main `3605443`(PR #254 squash) → `make dc-build SERVICE=web` + `docker compose up -d --no-build web`(repo-web-1 healthy). 서빙 `admin.js/styles.css?v=20260615-ds-multiselect` + healthz `git_commit=3605443`(mysql_ok·pg_ok true). 로드 admin.js `?v=20260615-ds-multiselect`(신규 `_runDatasourceBulkAsync` 등 hit).
  - **계측 결과(win-browser eval)**:
    - **구조**: `#datasourceList` **14행 전부** `<div role=row>`(rowsAreDiv=true) + `.admin-list-row-cb` 체크박스(rowsHaveCheckbox=true) + `.ds-conn-dot`(rowsHaveConnDot=true, PR#251 통합 보존). `#datasourceSelectAll`·`#datasourcesBulkBar`(role=toolbar, 초기 empty)·`#datasourcesCrossPageBanner` 실재. listRole=`grid`. **행 grid `grid-template-columns: 13px 9px 251px`**(체크박스·도트·main 3열) — base `auto 1fr auto` 가 아닌 `#datasourceList .admin-list-row` override 적용 확인.
    - **체크박스→bulkBar**: 1개 체크 시 bulkBar `childElementCount>0`, role=toolbar, 라벨 "1개 선택됨", 버튼=[인사이트 탐색 켜기·인사이트 탐색 끄기·삭제·선택 해제](console.manage 게이트 통과).
    - **전체선택**: `#datasourceSelectAll` 클릭 → 14행 전부 체크(checkedCount=14), selectAllChecked=true·indeterminate=false, 라벨 "14개 선택됨".
    - **indeterminate**: 전체선택 상태에서 1개 해제 → checked=13, selectAllChecked=false·**selectAllIndeterminate=true**(부분 선택 반영).
  - **시각 evidence**: 스크린샷 `artifacts/pb0008-ds-multiselect/ds-multiselect-partial-select.png`(1249×840) — 좌측 데이터소스 목록 [전체선택(indeterminate) · 14] + 13행 체크 + 각 행 [체크박스·연결도트(초록/빨강)·이름·엔진 pill·좌표], 하단 bulk 툴바 "13개 선택됨 · 인사이트 켜기/끄기/삭제/선택 해제". 계정·역할·제품 pane 과 동일 다중선택 구조.
  - **Pass/Fail: PASS** — 행 체크박스(div role=row)·전체선택(indeterminate)·일괄 툴바(buttons·count)·leading 도트(#251 통합)·3열 grid(13px 9px 251px) 전부 실제 Windows 브라우저 실측 통과. CHECK#13(PB-0008 Windows-browser) **충족**.
  - **Notes:** shift-click 범위·실제 일괄 삭제/insight 토글(파괴적·상태변경)은 라이브 데이터 보호 위해 실행 미수행(구조·게이트·핸들러는 적대적 코드리뷰 REV-0286 에서 confirmed). 기 캐시 사용자는 1회 하드리프레시.

- 2026-06-16 (TASK-0283 제품 아이콘 편집 UI 유저 프로필 ✎ 오버레이 통일 — 정적 검증 PASS / **PB-0008 배포 후 잔여**; CHG/REV-20260616-0291):
  - **Environment: 정적(node --check)** — 변경은 frontend 정적자산(admin.js/styles.css/index.html/admin.html)뿐, 백엔드 엔드포인트(PUT/DELETE icon) 재사용이라 Python(make test) 영향 0.
  - 결과: `node --check admin.js` PASS. diff = admin.js(renderProductDetail 1곳, 텍스트 pill → `.profile-avatar-edit`+`.profile-avatar-change` ✎ 오버레이 + `.profile-avatar-remove` 링크) + styles.css(dead `.admin-avatar-edit/change/remove` 제거) + index/admin.html(cache-buster `?v=20260616-product-icon-edit`).
  - **PB-0008 Windows-browser → 아래 항목에서 PASS(CHG/REV-20260616-0292).**

- 2026-06-16 (TASK-0283 제품 아이콘 편집 UI 유저 프로필 ✎ 오버레이 통일 — **PB-0008 Windows-browser PASS**; CHG/REV-20260616-0292 evidence):
  - **Environment: Windows-browser** (실제 Windows Chrome/148.0.7778.217 via `bin/win-browser.py` 무권한 relay `bridge_mode: relay`, endpoint `http://172.28.64.1:9223`, https://localhost:18080, self-signed ignore). 배포: main `245446f`(PR #265 squash) → `docker compose build web` + `up -d --no-deps web`(repo-web-1 Up healthy, /healthz mysql_ok·pg_ok true). 서빙 admin.html `admin.js?v=20260616-product-icon-edit`·`styles.css?v=20260616-product-icon-edit`, 서빙 admin.js 에 `profile-avatar-change` baked(grep 1 hit).
  - **계측 결과(win-browser eval, `관리 콘솔 > 제품 > (KR) 킹스레이드 - 로컬` 상세)**:
    - **✎ 오버레이 실재**: `.admin-detail-identity .profile-avatar-edit` 래퍼 present(`position:relative`), `.profile-avatar-change` = 텍스트 "✎", computed `position:absolute · right:-4px · bottom:-4px · width:22px · height:22px · border-radius:50%`, rect 22×22, `visibility:visible · opacity:1 · display:grid` → 유저 프로필 드로어와 **동일 클래스·동일 computed**(시각 동형).
    - **구 텍스트 pill 부재**: `.admin-detail-identity .admin-avatar-change`/`.admin-avatar-edit` querySelector = null(oldPillPresent=false). 36px 아바타(`position:relative`) 영역 침범 0.
    - **제거 링크 분기**: 본 제품은 custom icon_url 미설정(Identicon) → `.profile-avatar-remove` 미노출(null) = 명세대로(아이콘 설정 시에만 "아이콘 제거" 표시).
  - **시각 evidence**: `artifacts/pb0008-task0283/product-icon-edit-overlay.png`(1249×840) — 제품 상세 헤더가 아바타 + 이름 "(KR) 킹스레이드 - 로컬" + 메타로 깔끔, 기존 "아이콘" 텍스트박스 침범 제거됨.
  - **Pass/Fail: PASS** — ✎ 원형 오버레이 실재·visible, 텍스트 pill 부재, 아이콘 영역 침범 0, 유저 프로필과 동일 클래스 재사용으로 시각 동형 전부 실제 Windows 브라우저 실측 통과. CHECK#13(PB-0008 Windows-browser) **충족**.
  - **Notes:** 기 캐시 사용자는 1회 하드리프레시(Ctrl+Shift+R)로 no-cache index/admin.html 진입 후 자동 최신.

- 2026-06-16 (TASK-0291 관리 콘솔 계정 탭 배지 활성 계정만 집계 — 정적 검증 PASS / **PB-0008 배포 후 잔여**; CHG/REV-20260616-0300):
  - **Environment: 정적(node --check)** — 변경은 frontend 정적자산(admin.js 집계식 1곳 + admin.html 캐시버스터)뿐, 백엔드/엔드포인트 무변경이라 Python(make test) 영향 0.
  - 결과: `node --check admin.js` PASS. diff = admin.js(`refreshPendingUI` 의 `#tabCountAccounts` = `adminState.accounts.filter((a) => a.is_active && !a.deleted_at).length`) + admin.html(cache-buster `?v=20260616-task0291-account-active-count`). 활성 정의는 `filteredAccounts()` 의 `'active'` 분기(`is_active && !deleted_at`)와 동일 재사용.
  - **PB-0008 Windows-browser → 배포 후 측정**: 계정 탭 배지 `#tabCountAccounts` 텍스트가 "활성" 필터 적용 시 `#accountListCount`("N명")의 N 과 일치하고, "전체" 필터 수보다 작거나 같음을 win-browser eval 로 실측 예정.

- 2026-06-16 (TASK-0291 관리 콘솔 계정 탭 배지 활성 계정만 집계 — **PB-0008 Windows-browser PASS**; CHG/REV-20260616-0301 evidence):
  - **Environment: Windows-browser** (실제 Windows Chrome/148.0.7778.217 via `bin/win-browser.py` 무권한 relay `bridge_mode: relay`, endpoint `http://172.28.64.1:9223`, https://localhost:18080, self-signed ignore). WSL headless 아닌 실제 Windows 화면. 배포: main `9bdb9f8`(PR #287 squash) → `docker compose build web` + `up -d --no-build web`(repo-web-1 Up healthy, /healthz git_commit=9bdb9f8·mysql_ok·pg_ok true). 서빙 admin.html `admin.js?v=20260616-task0291-account-active-count` + 서빙 admin.js 에 `activeAccountCount` baked(2 hit).
  - **계측 결과(win-browser eval, `관리 콘솔 > 계정`)**: 계정 탭 배지 `#tabCountAccounts` = **7**. 목록 카운트 `#accountListCount`: 전체 필터 **28명** / 활성 **7명** / 비활성 1명 / 삭제됨 20명. 검산 7+1+20=28(active+inactive+deleted=all). **배지 7 = 활성 필터 목록 수 7명 일치** + **배지 7 < 전체 28**(수정 전이라면 28 표시) → `#tabCountAccounts` 가 `adminState.accounts.length`(28)가 아닌 활성만(`is_active && !deleted_at`, 7) 집계함을 실측 확인. `#accountListCount`(filter-aware)는 비변경 — 필터별 정확 카운트 유지.
  - **시각 evidence**: `artifacts/pb0008-task0291/account-tab-active-count.png`(1249×840) — 좌측 사이드바 계정 배지 **7**, 본문 "계정 관리" 목록 "전체" 필터에서 **28명** 동시 표시(배지 ≠ 전체, 배지 = 활성). 역할(5)·제품(8)·데이터소스(14) 탭 배지는 비변경(요청 범위=계정 한정).
  - **Pass/Fail: PASS** — 계정 탭 배지가 활성 계정 수(7)만 집계하고 전체(28)와 분리됨을 실제 Windows 브라우저 실측 통과. CHECK#13(PB-0008 Windows-browser) **충족**.
  - **Notes:** 기 캐시 사용자는 1회 하드리프레시(index/admin.html no-cache 진입 후 자동 최신).

- 2026-06-16 (TASK-0292 관리 콘솔 좌측 사이드패널 수직 스크롤 — **PB-0008 Windows-browser PASS**; CHG/REV-20260616-0304 evidence):
  - **Environment: Windows-browser** (실제 Windows Chrome/148.0.7778.217 via `bin/win-browser.py` 무권한 relay `bridge_mode: relay`, endpoint `http://172.28.64.1:9223`, https://localhost:18080, self-signed ignore). WSL headless 아닌 실제 Windows 화면. 배포: main `be3a775`(PR #289 squash) → `docker compose build web` + `up -d --no-deps web`(repo-web-1 Up healthy, /healthz mysql_ok·pg_ok true). 서빙 admin.html `styles.css?v=20260616-task0292-admin-sidebar-vscroll` + 컨테이너 baked styles.css `.admin-tabs{min-height:0;overflow-y:auto}`·`.admin-sidebar-foot{flex-shrink:0}`.
  - **측정(win-browser eval, /admin 로그인 세션)**: computed style — `.admin-tabs` `overflow-y=auto`·`min-height=0px`, `.admin-sidebar-foot` `flex-shrink=0`. 짧은 viewport 시뮬(`.admin-shell` height=240px): `.admin-tabs` clientHeight=134·scrollHeight=572 → **scrollable=true**, scrollTop=scrollHeight 설정 시 438 도달(canScroll), 하단 `[data-admin-tab=settings]`('설정') **settingsReachable=true**, foot bottom = aside bottom(footPinned=true).
  - **시각 evidence**: `artifacts/pb0008-task0292/admin-sidebar-vscroll-short-vp.png` — 짧은 사이드바에 수직 스크롤바 노출 + 하단 스크롤 상태에서 "시스템 > 설정" 탭·"변경 없음" 풋 표시(브랜드 상단 고정).
  - **Pass/Fail: PASS** — 화면 높이가 작아도 좌측 사이드패널 탭 전체(특히 하단 '설정')가 수직 스크롤로 도달·조작 가능함을 실제 Windows 브라우저 실측 통과. 사용자 보고 이슈 해소. CHECK#13(PB-0008 Windows-browser) **충족**.

- 2026-06-17 (TASK-0293 프로필 아이콘 전 구간 조회·수정: 관리 콘솔 계정·역할 — **PB-0008 Windows-browser PASS**; REV-...-pb0008 evidence):
  - **Environment: Windows-browser** (실제 Windows Chrome/148.0.7778.217 via `bin/win-browser.py` 무권한 relay `bridge_mode: relay`, endpoint `http://172.28.64.1:9223`, https://localhost:18080, self-signed ignore). WSL headless 아닌 실제 Windows 화면. 배포: main `7a52a66`(PR #300 merge) → `make dc-build SERVICE=web` + `docker compose up -d --no-deps --no-build web`(repo-web-1 Up healthy). 서빙 검증 3종: /healthz `git_commit=7a52a66`(mysql_ok·pg_ok true), baked app.py `admin_upload_role_icon`/`IconObjectKey`(23 hit), 서빙 admin.html `admin.js?v=20260617-task0293-profile-icons` + admin.js 에 `url: account.avatar_url`/`url: merged.icon_url` baked(4 hit).
  - **계측(win-browser eval, bootstrap_admin 로그인 `/admin`)**:
    - **AC-0542(계정 조회 버그 수정)**: `#accountList` 아바타 15개 = **img 1 + Identicon svg 14 + 이니셜 텍스트 0**. 작업화면에서 업로드된 아바타(img 1건)가 관리 콘솔 목록에 그대로 표시 = **사용자 보고 버그(작업화면↔관리 콘솔 미반영) 실측 해소**. 미설정 계정은 username 시드 Identicon(이니셜 텍스트 폐기 확인).
    - **AC-0544(역할 아이콘 도입·조회)**: `#roleList` 아바타 5개 = **Identicon svg 5 + 이니셜 텍스트 0**(role_key 시드). `WebRoles.IconObjectKey` 신규 컬럼이 라이브 스키마에 반영(쿼리 'Unknown column' 0).
    - **AC-0543(관리자 계정 아바타 편집, 타 계정)**: 관리자(bootstrap_admin)가 타 계정 `DQA_ADMIN`(#30) 아바타 업로드 `PUT /api/admin/accounts/30/avatar` → **200** `avatar_url=/api/avatars/30?v=9f1efb101faf`, 서빙 `GET` → **200 image/png**. 계정 상세 `.profile-avatar-edit .profile-avatar-change`(✎) present·`.profile-avatar-remove` present·`.admin-avatar img` rendered = true.
    - **AC-0545(역할 아이콘 편집)**: 역할 `pending`(#1) 아이콘 업로드 `PUT /api/admin/roles/1/icon` → **200** `icon_url=/api/roles/1/icon?v=85e47f347e12`, 서빙 → **200 image/png**. 역할 상세 ✎ 오버레이·제거 버튼·img rendered = true. (검증 후 테스트 업로드 DELETE 200/200 으로 Identicon 복원 — 운영 상태 무오염.)
  - **시각 evidence**: `artifacts/pb0008-task0293/admin-account-role-icons.png`(1249×840) — 관리 콘솔 계정 목록 아바타가 이미지/Identicon 렌더(이니셜 텍스트 아님).
  - **Pass/Fail: PASS** — 아이콘을 쓰는 모든 구간(관리 계정·역할)에서 이미지(기본=Identicon 패턴) 조회·수정 가능, 작업화면↔관리 콘솔 아바타 반영, 관리자 타 계정 아바타·역할 아이콘 업로드/서빙 end-to-end 가 실제 Windows 브라우저 실측 통과. CHECK#13(PB-0008 Windows-browser) **충족**.
  - **Notes:** 기 캐시 사용자는 1회 하드리프레시(admin.html no-cache 진입 후 자동 최신). 아바타/아이콘 mutation 은 제품 아이콘 정합으로 audit 미기록(REVIEW MINOR accepted).

- 2026-06-17 (TASK-0300 관리 콘솔 계정/역할 권한 편집 self-scope — privilege escalation 방지, **Critical §12.3** — **라이브 403 + PB-0008 Windows-browser PASS**; CHG/REV-20260617-0308 evidence):
  - **Environment: Windows-browser** (실제 Windows Chrome/148.0.7778.217 via `bin/win-browser.py` 무권한 relay `bridge_mode: relay`, endpoint `http://172.28.64.1:9223`, https://localhost:18080, self-signed ignore). WSL headless 아닌 실제 Windows 화면. 배포: main `a9effd6`(PR #313 squash) → `docker compose build web` + `up -d --no-deps web`(repo-web-1 Up, /healthz mysql_ok·pg_ok true). 서빙 admin.html `admin.js?v=20260617-task0300-perm-self-scope` + 서빙 admin.js 에 `allowedCodes` baked(13 hit) + 컨테이너 app.py `_enforce_override_self_scope`/`_role_grant_excess_for_actor` baked(3 hit). (healthz git_commit=unknown 은 GIT_COMMIT build-arg 미주입 기존 quirk — 코드 베이킹은 직접 grep 으로 확증.)
  - **라이브 백엔드 403 (배포 코드 + 실제 제한계정 `pgpark`/usermanager, target=review_user01 id=3; pgpark 자격 백업→검증→복원 비파괴)**: usermanager 는 `account.permission.override.manage`·`account.role.assign` 보유하나 `audit.purge`·`role.*`·`product.manage`·`datasource.*` 미보유.
    - **T1** 미보유 `audit.purge` override **allow → 403** (`"본인이 보유하지 않은 권한은 설정할 수 없습니다: audit.purge"`) — escalation 차단.
    - **T2** 미보유 `audit.purge` override **deny → 403** — 미보유 권한은 allow·deny 모두 불가(완전 숨김·차단, 사용자 결정 ①).
    - **T3** 보유 `account.read` override **allow → 200** — false-block 아님(보유 범위는 정상 설정).
    - **T4** 고권한 `admin` 역할 배정 **→ 403** (`"본인이 보유하지 않은 권한을 가진 역할은 배정할 수 없습니다: account.delete, …"`) — 역할 배정 경유 우회 차단(외부리뷰 MAJOR-1, 사용자 결정 ③).
  - **PB-0008 프론트 render-injection (실 Chrome, 배포 admin.js)**: bootstrap_admin `/admin` 세션에서 `renderPermissionGrid` 를 제한 allowedCodes(account.*+console 보유, audit.* 미보유)로 호출 → `rowsRendered=["account.read","account.update"]`(보유만), `unheld_audit_read_hidden=true`·`unheld_audit_purge_hidden=true`(미보유 행 absent), `audit_group_removed=true`(빈 그룹 컨테이너 제거), `product_access_container_kept=true`(제품카드 임베드 타겟 보존). **실 Chrome 가시성**: account 행 `getComputedStyle.display=flex` + `offsetParent≠null`(jsdom 미검출 영역 — 실제 표시 확인). 안내문구 "본인이 보유한 권한만 표시·설정할 수 있습니다." 노출.
  - **시각 evidence**: `artifacts/pb0008-task0300/perm-self-scope-hidden.png`(1249×840) — 실 Chrome 관리 콘솔에 주입된 PB-0008 패널: "계정" 그룹(상속 2 = account.read/update)만 표시, audit.* 그룹 부재, 안내문구 노출.
  - **단위(정적, 컨테이너 외)**: `test_perm_self_scope.py` 18 PASS(ast 추출 실 helper 4종 — escalation 403·deny 차단·merge 보존·역할 add/remove/create·배정 초과) + `verify_perm_self_scope.mjs` 13 PASS(실 `renderPermissionGrid` jsdom — 숨김·빈 그룹 제거·컨테이너 보존·하위호환) + node --check + py ast.parse.
  - **Pass/Fail: PASS** — 배포된 시스템에서 제한 admin 이 본인 미보유 권한을 계정 override·역할 배정으로 부여하지 못하고(403×3 벡터), 보유 권한은 정상 설정(200), 화면에선 미보유 권한 행이 숨겨짐을 실제 Windows 브라우저 + 라이브 HTTP 로 실측 통과. CHECK#13(PB-0008 Windows-browser) **충족**.
  - **Notes:** pgpark 자격 백업/복원으로 실계정 무오염. 기 캐시 사용자는 1회 하드리프레시(admin.html no-cache 진입 후 자동 최신).

- 2026-06-17 (TASK-0302 관리 콘솔 제품 일괄 삭제 미적용 + bulk staging 목록 즉시 반영, **Major §12.3**; CHG/REV-20260617-0312):
  - **Environment: 라이브 실 running stack + 브라우저(gstack /browse, WSL headless) + curl** — `docker cp` 로 수정 admin.js/admin.html 를 repo-web-1 `/app/web/static/` 에 반영(정식 배포 전 검증), 서빙 admin.js?v=20260617-task0302-bulk-delete-apply md5 일치 확인. 백엔드(app.py IsDefault/404 가드)는 정식 배포(web 재빌드) 후 라이브 재검증 예정.
  - **재현(수정 전, 동일 stack)**: 제품 3개(zz_browse_prod_*) 다중선택 → "삭제 pending"(pending.productMeta=3, 전부 `{_delete:true}`) → "모두 적용" → pending 0건이나 **3개 전부 잔존(삭제 0건)** — applyAllPending 이 _delete 무처리(빈 body·요청 0건) 실증.
  - **수정 후(동일 flow)**: 제품 3개 다중선택 → "삭제 pending" → is-to-delete rows=2·pendingDots=2(제품 행 마커 실측, productMeta pending 기준) → "모두 적용" → **3개 전부 삭제**(adminState.products·API 모두 0 잔존, commit bar 0건).
  - **회귀**: 역할 일괄 비활성화 2/2 정상(roleSelected.size=2 → pending.roles=2 → 적용 후 active=false ×2, has-pending 마커 markedRows=2). 계정/역할/제품 일괄 활성·비활성, 단일 제품 삭제(직접 DELETE)는 수정 전부터 정상(전수 조사).
  - **단위(정적)**: node --check admin.js PASS + py ast.parse app.py PASS.
  - **Pass/Fail: PASS(behavioral)** — 제품 일괄 삭제가 실제 stack 에서 N개 전부 적용됨을 실측. 외부리뷰 SHIP-WITH-FIXES(REV-20260617-0312, MAJOR 기본제품 backend 가드·MINOR 제품행 마커 흡수).
  - **Residual(CHECK#13):** 정식 배포(web 재빌드) 후 **PB-0008 Windows-browser** 로 실 Windows 화면 재검증(제품 행 pending 마커·일괄 삭제 흐름) + 라이브 백엔드 가드(기본 제품 삭제 **409**·미존재 404) 실측. 본 cycle 검증은 WSL headless /browse + curl(행동/로직 정본)이며 실 화면 정본은 배포 후 PB-0008.

- 2026-06-18 (TASK-20260618T010417-date-group-collapse 작업 화면 좌측 대화목록 첫 진입 시 최근 일자 그룹만 펼침, **Minor §12.3** — **PB-0008 Windows-browser PASS**; CHG/REV-20260618T010417 evidence):
  - **Environment: Windows-browser** (실제 Windows Chrome/148.0.7778.217 via `bin/win-browser.py` 무권한 relay `bridge_mode: relay`, endpoint `http://172.28.64.1:9223`, https://localhost:18080, self-signed ignore). WSL headless 아닌 실제 Windows 화면 검증. 배포: main `32b5e8f`(PR #319 squash) → `docker compose build web` + `up -d --no-deps web`(repo-web-1 Up, /healthz mysql_ok·pg_ok true). 서빙 index.html `app.js?v=20260618-date-group-collapse` + 서빙 app.js 에 `_seedDateGroupsCollapsedOnce` baked(정의+호출 2 hit, 배선 `_seedDateGroupsCollapsedOnce(sortedDateKeys);` 확인). (healthz git_commit=unknown 은 GIT_COMMIT build-arg 미주입 기존 quirk — 코드 베이킹은 직접 grep 으로 확증.)
  - **첫 진입 상태(bootstrap_admin, 대화 109개)**: 좌측 대화목록 내 대화 날짜 그룹 6개(`.conv-date-group-header`) — `[0]` "6월 10일 (수)" `is-collapsed=false`·`aria-expanded=true`(펼침, 대화 2건 노출), `[1..5]` "6월 9일/6월 8일/6월 7일/5월 27일/5월 26일" 전부 `is-collapsed=true`·`aria-expanded=false`(접힘). PASS_recentExpanded=true·PASS_olderAllCollapsed=true → **VERDICT PASS**. (타 계정 대화 그룹도 접힘 — 기존 `_seedOthersCollapsedOnce` 무회귀.)
  - **clean-room(seed 재발화 + 비영속 증명)**: `localStorage.clear()`(제거 키 `mad.productPref.v1`·`mad.othersCollapsedSeed.v1`·`mad.collapsedGroups.v1`) → `goto` reload(진짜 fresh 진입) 후 동일하게 `[0]`만 펼침·나머지 5개 접힘 재현 → **seed 가 매 페이지 진입마다 재발화**. reload 후 `localStorage['mad.collapsedGroups.v1']==="[\"__others__\"]"` — **날짜 그룹 키가 localStorage 에 전혀 없음**(타 계정 그룹 키만) → `_saveCollapsedGroups` 미호출 비영속 설계 실증(날짜 접힘은 순수 in-memory seed 결과).
  - **세션 내 토글 존중(1회-게이트)**: 접힌 `[1]`"6월 9일" 헤더 클릭 → 펼침(expandedAfterClick=true), 이어서 `[2]`"6월 8일" 토글로 `renderConversationList` 재렌더 트리거 → `[1]` 여전히 펼침 유지(stillExpandedAfterRerender=true) → **VERDICT PASS**. `_dateGroupsSeededThisLoad` 1회-게이트가 같은 로드 내 사용자 펼침 토글을 재접힘 강제하지 않음을 실증.
  - **시각 evidence**: `artifacts/pb0008-date-group-collapse/entry-recent-only-expanded.png`(1249×840) — 실 Chrome 좌측 대화목록에 "6월 10일 (수)"만 펼쳐 대화 2건 노출, 나머지 5개 날짜 그룹 + "타 계정 대화" 모두 접힘(chevron 우향). 우측은 빈 대화 화면(conv-entry-defaults 무회귀).
  - **단위(정적, 컨테이너 외)**: `verify_date_group_collapse.mjs` 22 PASS(fresh seed·강제펼침·빈키 재시도·세션 토글 존중·단일 그룹·`__other__`·비영속·배선 순서) + 기존 `verify_conv_entry_defaults.mjs` 20 PASS(무회귀) + node --check.
  - **Pass/Fail: PASS** — 배포된 시스템에서 첫 진입(및 매 reload) 시 가장 최근 일자 그룹만 펼치고 나머지 오래된 날짜 그룹은 접힘, 비영속(reload 재적용)·세션 토글 존중을 실제 Windows 브라우저로 실측 통과. CHECK#13(PB-0008 Windows-browser) **충족**.
  - **Notes:** 기 캐시 사용자는 1회 하드리프레시(캐시버스터 `?v=20260618-date-group-collapse`로 자동 최신).

- 2026-06-18 (TASK-20260618T021526-admin-status-filter 관리 콘솔 역할·제품 탭 활성/비활성 필터, **Minor §12.3** — **PB-0008 Windows-browser PASS**; CHG/REV-20260618T022846 evidence):
  - **Environment: Windows-browser** (실제 Windows Chrome/149.0.7827.116 via `bin/win-browser.py` 무권한 relay `bridge_mode: relay`, endpoint `http://172.28.64.1:9223`, https://localhost:18080, self-signed ignore). WSL headless 아닌 실제 Windows 화면. 배포: main `6da40dc`(PR #321 squash) → `make dc-build SERVICE=web` + `docker compose up -d --no-deps web`(repo-web-1 Up healthy). 서빙 admin.html `admin.js?v=20260618-admin-status-filter` + 서빙 `/app/web/static/admin.html` 에 `data-role-filter`/`data-product-filter` 각 3버튼(전체/활성/비활성) baked + 서빙 admin.js 에 `roleFilter:`/`productFilter:` 상태·`adminState.roleFilter===`/`productFilter===` 술어·`[data-role-filter]`/`[data-product-filter]` 핸들러 baked(grep 실측).
  - **역할 탭 실측(bootstrap_admin)**: `#roleList` 행 6개. `data-role-filter="all"` → 6행. `"inactive"` 클릭 → 0행(이 환경 역할 전부 활성)·버튼 `is-active`="inactive". `"active"` 클릭 → 6행·버튼 `is-active`="active". `"all"` 복귀 → 6행. 버튼 단독 `is-active` 토글 + 술어 게이트 정상 → **VERDICT PASS**. evidence `artifacts/pb0008-admin-status-filter/roles-active-filter.png`.
  - **제품 탭 실측(분리 뚜렷)**: `#productList` 전체 13행(`is-disabled` 6 + 활성 7). `"inactive"` 클릭 → **6행 전부 `is-disabled`·`· inactive` 배지**(allDisabled=true; (KR)킹스레이드·(MV)마이크로볼츠·(GZ_KR)건즈국내·(DK)DK온라인·(GZ_QA_KR)건즈국내QA·(MV_QA)마이크로볼츠QA)·카운트 "6 / 13"·버튼 `is-active`="inactive". `"active"` 클릭 → **7행 전부 활성**(noneDisabled=true)·버튼 `is-active`="active". `"all"` 복귀 → 13행. 13=6+7 정확 분할 → **VERDICT PASS**. 시각 evidence `artifacts/pb0008-admin-status-filter/products-inactive-filter.png`(1249×836) — 제품 탭 `[전체][활성][비활성]` 필터그룹·비활성 선택 강조·표시 제품 전부 inactive 배지.
  - **단위(정적, 컨테이너 외)**: `scripts/verify_admin_status_filter.mjs` 11 PASS(실 `filteredRoles`/`filteredProducts` 본문 추출 + mock adminState — 역할·제품 각 all/active/inactive + 상태×검색 교집합 + `product all empty-search` 회귀) + node --check.
  - **Pass/Fail: PASS** — 배포된 시스템에서 역할·제품 탭의 활성/비활성 필터가 목록을 정확히 분할(제품 13=6+7)하고 버튼 `is-active` 가 단독 토글됨을 실제 Windows 브라우저로 실측 통과. 계정 탭 패턴 1:1 정합. CHECK#13(PB-0008 Windows-browser) **충족**.
  - **Notes:** 기 캐시 사용자는 1회 하드리프레시(캐시버스터 `?v=20260618-admin-status-filter`로 자동 최신).

- 2026-06-18 (TASK-20260618T022006 관리 콘솔 데이터소스 '새 항목' 엔진 선택 = 아이콘 드롭다운, **Minor §12.3** — **PB-0008 Windows-browser PASS**; CHG/REV-20260618-0315 feature + CHG/REV-20260618-0316 cache-buster fix + CHG/REV-20260618T030014 evidence):
  - **Environment: Windows-browser** (실제 Windows Chrome/149.0.7827.116 via `bin/win-browser.py` 무권한 relay `bridge_mode: relay`, endpoint `http://172.28.64.1:9223`, https://localhost:18080, self-signed ignore). WSL headless 아닌 실제 Windows 화면. 배포: feature main `da227eb`(PR #325) + cache-buster fix main `071020c`(PR #326) → `make dc-build SERVICE=web` + `docker compose up -d --no-deps web`(repo-web-1 Up healthy). 서빙 admin.html `admin.js?v=20260618-engine-dropdown` + `styles.css?v=20260618-engine-dropdown`, 서빙 admin.js 에 `_dsBuildEngineField`/`ENGINE_CATALOG`(11 hit)·styles.css 에 `.engine-picker`/`.engine-option`(16 hit) baked.
  - **버그 적발 → 수정 → 재검증 (PB-0008 본령)**: 1차 검증에서 드롭다운/MySQL 아이콘 색 `rgb(0,117,143)`=#00758F 는 정확하나 **`.engine-icon` CSS 미적용**(`engineIconCssRuleLoaded=false`·아이콘 render 52px·버튼 border/padding 0px) 적발 — styles.css 본문을 바꾸고도 cache-buster 미bump 으로 캐시 브라우저가 옛 CSS 수신. admin.html+index.html cache-buster bump(CHG-20260618-0316) 후 재배포·reload → `engineIconCssRuleLoaded=true`·아이콘 **18px**·버튼 border **1px**·padding **10px** 로 해소. jsdom 은 캐시·실 stylesheet 미재현이라 못 잡는 영역 — PB-0008 가치 실증.
  - **드롭다운 실측(bootstrap_admin)**: 데이터소스 탭 → '+ 새 데이터소스' → 엔진 트리거 클릭 → 목록 열림(`listOpen=true`), 옵션 2개 — ① **MySQL** 기본 포트 3306·SVG 아이콘·색 `rgb(0,117,143)`=#00758F(브랜드 teal)·aria-selected=true ② **Microsoft SQL Server** 기본 포트 1433·SVG 아이콘·색 `rgb(238,53,44)`=#EE352C(브랜드 red). 시각 evidence `artifacts/pb0008-engine-dropdown/engine-dropdown-open.png`(1249×836).
  - **선택 실측**: Microsoft SQL Server 옵션 클릭 → 트리거 라벨 "Microsoft SQL Server"·아이콘 색 `rgb(238,53,44)`·**포트 placeholder "3306"→"1433" 갱신**(onChange 작동)·목록 닫힘(`listClosedAfterSelect=true`). 시각 evidence `artifacts/pb0008-engine-dropdown/engine-mssql-selected.png`.
  - **단위(정적, 컨테이너 외)**: `tests/verify_engine_dropdown.mjs` 36/36 PASS(드롭다운 구조·옵션별 svg·hidden 값 계약·선택→repaint/aria/onChange·engineMeta 폴백·CSS inline-flow) + node --check. 적대 outside-voice 리뷰 SHIP(REV-20260618-0315, 8가설 전부 REFUTED).
  - **Pass/Fail: PASS** — 배포된 시스템에서 데이터소스 추가 시 엔진을 드롭다운으로 선택하고, MySQL/Microsoft SQL Server 가 각자의 공식 서비스 브랜드 아이콘+브랜드색으로 식별되며, 선택 시 트리거·포트 placeholder 가 갱신됨을 실제 Windows 브라우저로 실측 통과. CHECK#13(PB-0008 Windows-browser) **충족**.
  - **Notes:** 기 캐시 사용자는 1회 하드리프레시(캐시버스터 `?v=20260618-engine-dropdown`로 자동 최신).

- 2026-06-18 (TASK-20260618T024517-product-picker-search 작업 화면 제품 선택 드롭업 명칭 검색 필터, **Minor §12.3** — 정적 PASS / Windows-browser **배포 후 기록 예정**):
  - **Environment: 정적(node + jsdom@22, 컨테이너 외)** — 변경은 frontend 정적자산(app.js/styles.css/index.html)뿐, 백엔드·엔드포인트·RBAC 무변경이라 Python(make test) 영향 0.
  - **jsdom 실측**: `tests/verify_product_picker_search.mjs` **27 PASS / 0 FAIL** — 실 `renderProductDropupMenu`/`buildProductDropupSearch`/`filterProductDropupItems`/`buildProductDropupItem` 본문 추출 + state 스텁. 검증: ① 정의·`PRODUCT_DROPUP_SEARCH_MIN`(=6)·`openProductDropup` focus 코드·`data-search` 설정, ② 제품 8개(≥6)→검색 입력 렌더+placeholder "제품 명칭 검색…"+항목 9(auto1+pinned8)+전 항목 data-search+no-result 초기 hidden, ③ 제품 3개(<6)→검색 입력 미렌더, ④ 필터: 'dk'→DK 1건/no-result hidden, '유럽'→1건, 'qa'→2건(KR_QA·MV_QA), 미매칭→0건+no-result 노출, 빈검색→전체 복원 9건, 'product'→auto 매칭, ⑤ 제품 0개→검색 입력 없음+'접근 가능한 제품이 없습니다'+auto 유지.
  - **`node --check src/static/app.js`** PASS(문법 무결).
  - **Pass/Fail: PASS(정적)** — 필터 로직 jsdom 격리 통과. layout(sticky 고정·자동 focus·시각)은 jsdom 미계산 → **PB-0008 Windows-browser 가 정본 게이트**(배포 후 라이브 제품 13개로 검색박스 자연 노출 실측 예정).
  - **Notes:** 기 캐시 사용자는 1회 하드리프레시(캐시버스터 `?v=20260618-product-picker-search`로 자동 최신).

- 2026-06-18 (TASK-20260618T024517-product-picker-search 제품 선택 드롭업 명칭 검색 필터, **Minor §12.3** — **PB-0008 Windows-browser PASS**; CHG/REV-20260618T031450 evidence):
  - **Environment: Windows-browser** (실제 Windows Chrome/149.0.7827.116 via `bin/win-browser.py` 무권한 relay `bridge_mode: relay`, endpoint `http://172.28.64.1:9223`, https://localhost:18080, self-signed ignore). WSL headless 아닌 실제 Windows 화면. 배포: main `ebd2849`(PR #327 squash) → `make dc-build SERVICE=web` + `docker compose up -d --no-deps --force-recreate web`(repo-web-1 Up healthy, /healthz `git_commit=ebd2849`·mysql_ok·pg_ok true). 서빙 index.html `app.js?v=20260618-product-picker-search`·`styles.css?v=20260618-product-picker-search` + 서빙 app.js 에 `PRODUCT_DROPUP_SEARCH_MIN`/`filterProductDropupItems`/`buildProductDropupSearch` baked(8 hit).
  - **드롭업 측정1(bootstrap_admin, win-browser eval)**: `#productChip` 클릭(`openProductDropup`) → `#productDropupMenu` 열림(`menuOpen=true`). pinned 제품 **10개**(≥ 임계 6) → `.product-dropup-search` **렌더됨**(`searchRendered=true`)·placeholder "제품 명칭 검색…"·항목 11(auto1+pinned10)·전 항목 `data-search` 보유(`allHaveDataSearch=true`). `.product-dropup-search-wrap` `position=sticky`·`top=0px`(상단 고정). 검색 입력 **자동 포커스**(`document.activeElement===search`, `focused=true`).
  - **필터 동작 측정2(win-browser eval)**: 첫 제품 `data-search="(dk_dev) dk온라인 - 개발"`. `dk_` 입력 → input 이벤트 → **visible 2건**(DK_DEV·DK_QA)·no-result hidden. `zzzznotexist` 입력 → **visible 0건** + `.product-dropup-no-result` 노출·텍스트 "검색 결과가 없습니다". 검색어 비움 → **visible 11건 전체 복원**.
  - **시각 evidence**: `artifacts/pb0008-product-picker-search/search-filter-dk.png`(1249×836, git 비추적) — 드롭업 열림·검색 입력칸(파란 focus 테두리)에 "dk" 입력·필터 결과 [(DK_DEV) DK온라인 - 개발 mssql-dk-dev / (DK_QA) DK온라인 - QA 2개 데이터소스] 2건만 표시(나머지 8개 숨김).
  - **Pass/Fail: PASS** — 배포된 시스템에서 제품 선택 드롭업의 명칭 검색 필터가 (제품 10개 ≥ 임계) 노출되고, sticky 고정·자동 포커스되며, product_key 입력으로 실시간 필터(2건)·미매칭 시 결과없음 안내·검색어 비움 시 복원됨을 실제 Windows 브라우저로 실측 통과. CHECK#13(PB-0008 Windows-browser) **충족**.
  - **Notes:** 기 캐시 사용자는 1회 하드리프레시(캐시버스터 `?v=20260618-product-picker-search`로 자동 최신).
- 2026-06-18 (TASK-20260618T030534 데이터소스 목록 행에 엔진 서비스 아이콘 — 연결 도트 우측, **Minor §12.3** — **PB-0008 Windows-browser PASS**; CHG/REV-20260618T031747 evidence):
  - **Environment: Windows-browser** (실제 Windows Chrome/149.0.7827.116 via `bin/win-browser.py` 무권한 relay `bridge_mode: relay`, endpoint `http://172.28.64.1:9223`, https://localhost:18080, self-signed ignore). WSL headless 아닌 실제 Windows 화면. 배포: main `8a2c886`(PR #332) → `make dc-build SERVICE=web` + `docker compose up -d --no-deps web`(repo-web-1 Up healthy). 서빙 admin.html `admin.js?v=20260618-ds-list-engine-icon` + `styles.css?v=20260618-ds-list-engine-icon`, 서빙 admin.js 에 `ds-list-engine-icon`(1 hit)·styles.css 에 `ds-list-engine-icon`(2 hit) baked.
  - **목록 행 구조 실측(bootstrap_admin)**: 데이터소스 탭 → `#datasourceList .admin-list-row` 18행. 각 행 children 순서 = `[admin-list-row-cb, ds-conn-dot, ds-list-engine-icon, admin-list-row-main]` → **엔진 아이콘이 연결 도트 우측**(`engRightOfDot=true`). 행 grid `grid-template-columns` 실측 = **`13px 9px 16px 225px`**(체크박스·도트·엔진아이콘·main 4열). 각 아이콘 svg 존재·16px.
  - **브랜드색·정렬 실측**: 18개 아이콘 distinct 엔진 2종 — "엔진: MySQL"=`rgb(0,117,143)`(#00758F teal)·"엔진: Microsoft SQL Server"=`rgb(238,53,44)`(#EE352C red). 아이콘 컬럼 **leftAlignSpread=0px**(행 간 좌표 편차 0 → 4열 grid 가 콘텐츠 길이 무관 정렬 보존, 행 목록 컬럼 정합 정책 충족). 시각 evidence `artifacts/pb0008-ds-list-engine-icon/ds-list-engine-icons.png`(1249×836) — 목록 mssql 행(빨간 SQL Server 마크)·mysql 행(teal 돌고래)이 녹색 연결 도트 우측에 렌더, 텍스트 엔진 배지 병존.
  - **단위(정적, 컨테이너 외)**: `tests/verify_ds_list_engine_icon.mjs` 17/17 PASS(mysql/mssql/폴백 아이콘 빌드·브랜드색·aria·도트 우측 배선·이전 3-append 잔존 0·4열 grid·아이콘 CSS) + node --check.
  - **Pass/Fail: PASS** — 배포된 시스템에서 데이터소스 목록 각 행의 네트워크 연결 도트 우측에 엔진 서비스 브랜드 아이콘이 브랜드색으로 렌더되고 행 간 정렬이 무붕괴됨을 실제 Windows 브라우저로 실측 통과. CHECK#13(PB-0008 Windows-browser) **충족**.
  - **Notes:** 기 캐시 사용자는 1회 하드리프레시(캐시버스터 `?v=20260618-ds-list-engine-icon`로 자동 최신).

- 2026-06-18 (TASK-20260618T025755-dbpicker-search-regex '+ 데이터베이스 추가' picker 검색 필터 + 정규식 일괄 선택, **Major §12.3** — **PB-0008 Windows-browser PASS**; CHG/REV-20260618T025755 evidence):
  - **Environment: Windows-browser** (실제 Windows Chrome/149.0.7827.116 via `bin/win-browser.py` 무권한 relay `bridge_mode: relay`, endpoint `http://172.28.64.1:9223`, https://172.28.73.199:18080 self-signed ignore). WSL headless 아닌 실제 Windows 화면. 배포: main `14c3280`(PR #331 머지 후 #332·#334 등 동시 머지 포함) → `docker compose build web` + `up -d --no-deps web`(repo-web-1 Up healthy). 서빙 검증(HTTP, 브라우저 캐시 무관): `/static/admin.js` 에 `DB_PICKER_SEARCH_MIN` 2건·`/static/styles.css` 에 `admin-db-picker-toolbar` 1건 baked. 브라우저 로드 후 전역 `DB_PICKER_SEARCH_MIN===6` + `dbPickerFilterNames/dbPickerRegexMatches/applyDbPickerSearch/applyDbPickerRegexHighlight` 4종 모두 `function`.
  - **검증 기법: render-injection**(win-browser eval) — 라이브 데이터소스 중 사용자 DB ≥ `DB_PICKER_SEARCH_MIN`(6) 인 것이 보장되지 않아(toolbar 노출 임계), 실 배포된 admin.js helper + styles.css 위에 합성 `.admin-db-picker-list`(toolbar + 8개 `.admin-db-picker-item`)를 주입해 **실 배포 CSS computed style + 실 배포 helper 동작**을 실측(메모리 picker/CSS PB-0008 선례 정합 — TASK-0285/0257/0277b 동류).
  - **CSS computed(실 배포 styles.css)**: `.admin-db-picker-toolbar` `position=sticky` ✓ · `.admin-db-picker-search` `border-top-width=1px` ✓ · `.admin-db-picker-regex-btn` `background=rgb(37,99,235)`(#2563eb primary) ✓ · `.admin-db-picker-item.is-regex-match` `background=color(srgb .145 .388 .922 / .12)`(primary@12% 하이라이트) ✓ · **검색 숨김 항목 `.admin-db-picker-item.hidden` computed `display:none`** — 글로벌 `.hidden{display:none!important}` 가 항목 `display:flex` 를 이김(메모리 `[hidden]`/display 함정 실측 해소) ✓.
  - **helper 동작(실 배포 admin.js)**: 검색 `'prod'` → 표시 3 / 숨김 5(8개 중) ✓ · 검색 `'zzzz'` → 표시 0 + `.admin-db-picker-no-result` 가시(`display:block`) ✓ · 검색 클리어 → 표시 8 ✓ · 정규식 `'^prod_'` → ok·count 3·`.is-regex-match` 3개 ✓ · 잘못된 정규식 `'['` → ok:false(하이라이트 0) ✓ · 순수 `dbPickerFilterNames('prod_')`=3·`dbPickerRegexMatches('_log$')`=['prod_log'] ✓.
  - **시각 evidence**: `artifacts/pb0008-dbpicker-search-regex/picker-search-regex.png`(1249×836) — 실 관리 콘솔 대시보드 위에 드롭다운 toolbar(검색창 "DB 이름 검색…" + 정규식 `^prod_` "3개 일치" + "일치 선택" 버튼 + "선택됨 3개") + prod_orders/prod_users/prod_log 체크+파란 하이라이트 + staging_main 미체크.
  - **단위(정적, 컨테이너 외)**: `tests/verify_dbpicker_search_regex.mjs` **33/33 PASS**(순수 검색 5·정규식 6·DOM 검색 4·DOM 하이라이트 3·wiring 7·CSS/cache-buster 8) + `node --check admin.js`.
  - **Pass/Fail: PASS** — 배포된 시스템에서 '+ 데이터베이스 추가' 검색 필터·정규식 일괄 선택(additive)·라이브 카운트/하이라이트·검색결과없음·선택됨 N개·sticky toolbar 가 실 배포 CSS/JS 로 동작함을 실제 Windows 브라우저로 실측 통과. CHECK#13(PB-0008 Windows-browser) **충족**.
  - **Notes:** ① toolbar 는 후보 사용자 DB ≥ 6 일 때만 노출(소수 목록 무회귀). ② 임시 검증 동안만 `.env` `WEB_ALLOWED_HOSTS` 에 WSL IP 추가 후 검증 종료 시 복원(deployed 이미지·영속 config 무변경, WSL IP 호스트 거부 복귀 실측). ③ 기 캐시 사용자는 1회 하드리프레시(cache-buster `?v=20260618-ds-list-engine-icon` — 동시 머지 후행 cache-buster, admin.js 내용에 본 변경 포함).
- 2026-06-18 (TASK-0303 역할/계정 '제품 사용(product_access)' 다중선택 무효 + 그룹 카운트 "0/0", **Major §12.3**; CHG/REV-20260618-0317):
  - **Environment: node + jsdom 격리(실 함수 추출)** — `tests/verify_product_access_multiselect.mjs` 가 admin.js 에서 실제 `mergedRole`/`setRolePending`/`mergedAccount`/`setAccountPending`/`_updateCheckboxGroupSummary` 를 brace-match 추출해 평가. 라이브 브라우저는 동시세션 잦은 재배포로 세션 회전(쿠키 무효화)·docker cp 덮어쓰기가 반복돼 본 cycle 검증은 결정적 node 정본 + 배포 후 PB-0008.
  - **결과 6/6 PASS**: ① 역할 제품 3개 토글 → 3개 모두 staged(다중선택 누적) ② mv 해제 후 kr·dk 보존 ③ **OLD 스냅샷 로직 = 마지막 1개만 남음(버그 재현 대조군)** ④ 제품 토글 후 정적 권한 변경 시 제품 접근 보존(정적↔제품 클로버 방지) ⑤ 계정 제품 override 3개 → 3개 staged ⑥ 카드 임베드 후 재집계 → "3/16 선택"(이전 "0/0" 해소). + node --check admin.js PASS.
  - **외부리뷰 SHIP**(REV-20260618-0317, general-purpose adversarial): 권한 손실 0·TASK-0300 self-scope 무회귀·escalation 0(백엔드 `_enforce_*_self_scope` 정본)·role divergence 0·카운트 inflation 0·신규역할 안전 — 6항목 전부 refuted.
  - **Pass/Fail: PASS(로직 정본)** — staging 누적·카운트 재집계 로직 결정적 통과.
  - **Residual(CHECK#13):** 정식 배포(web 재빌드) 후 **PB-0008 Windows-browser** 로 실 화면 재검증(역할 zz 테스트역할에서 제품 3개 토글 → pending 3개 staged·배지 "N/M"·"모두 적용" 후 영속). jsdom/node 는 layout·실 DOM 이벤트 미계산이라 화면 정본은 PB-0008.

- 2026-06-18 (TASK-20260618T044318 제품 DB allowlist 정규식 규칙 자동 동기화, **Critical §12.3** — **PB-0008 Windows-browser PASS** + 라이브 버그 적발/수정):
  - **Environment: Windows-browser** (실제 Windows Chrome/149 via `bin/win-browser.py` relay `http://172.28.64.1:9223`, https://172.28.73.199:18080). 배포: main `72e5769`(PR #341 기능 + #342 audit-fix) → `docker compose build web` + `up -d --no-deps web`(healthy). 검증 동안만 `.env WEB_ALLOWED_HOSTS` 에 WSL IP 추가 후 복원(deployed 이미지·영속 config 무변경, 종료 후 WSL IP "Invalid host header" 거부 복귀 실측).
  - **마이그레이션 라이브 검증**(MySQL agent_memory): `WebProductDatasourceDbRules`·`WebProductDatabasePending` 테이블 + `WebProductDatabases.Source`·`RuleId` 컬럼 생성 확인(probe Source 컬럼 등록으로 slow-path 트리거).
  - **★라이브 버그 적발(PB-0008 가치)**: 규칙 PUT 시 `audit write failed: unknown audit action: admin.product.db_rule.set`(500) — `_audit_admin_mutation`→`build_audit_change_json` 빌더에 신규 action 미등록. **단위(Python)·jsdom 은 audit 레이어 미경유라 못 잡음**. fix=빌더에 5 action 등록(PR #342) + 회귀 가드(verify_db_rule_logic.py 30/30). 재배포 후 재검증 통과.
  - **규칙 에디터 실 렌더**(product 109 상세, datasource 펼침): `.cov-db-rule` 노출 · border-top 1px · include/exclude/cap 입력 · 저장버튼 `rgb(37,99,235)` · head "정규식 자동 규칙". 시각 evidence `artifacts/pb0008-db-rule-autosync/rule-editor-live.png`(1920×953).
  - **라이브 preview round-trip**: MySQL datasource `.` → "11개 일치 · 신규 0개"(실 datasource enum+match+diff), MSSQL `mssql-dk-dev` `.` → 11 matched/0 new — 실 datasource 연결·정규식 매칭·기존 allowlist diff 동작.
  - **라이브 PUT/GET/DELETE round-trip**(product 109 / mssql-dk-dev, audit fix 후): PUT(`^zzz_nomatch_`) ok·reconcile `no-change` · GET 규칙 반환 · DELETE ok. 비-매칭 패턴이라 allowlist 무변경(안전). 인증 게이트 무인증 GET=401 실측.
  - **단위(정적)**: `verify_db_rule_logic.py` 30/30(검증·제외셋·매칭 B5·인젝션·**ReDoS 강화** `(a|a)*`/`(.*a){20}` 거부 + catastrophic 0.000s 차단·방어심층·audit action 등록 가드) + `verify_db_rule_ui.mjs` 17/17(wiring·B4 body 필터·배지·CSS) + ast/node.
  - **Pass/Fail: PASS** — 배포 시스템에서 규칙 저장/조회/삭제·라이브 preview·마이그레이션·인증게이트·규칙 에디터 렌더를 실제 Windows 브라우저로 실측 통과. auto-add insert + rule 배지 live 시연은 모든 datasource 가 완전 allowlist 상태("신규 0")라 비파괴 재현 불가 → 단위(insert 결정 로직)·jsdom(배지) 으로 커버. CHECK#13 충족.
  - **Notes:** outside-voice 2-pass(설계 NOT-SHIP→하이브리드, 구현 SHIP-WITH-FIXES) BLOCKER ReDoS·MAJOR#1/#2 흡수. 캐시버스터 `?v=20260618-db-rule-autosync`.

- 2026-06-18 (TASK-20260618T061703 DB allowlist 규칙 다중 + DB 종속 UI, **Major §12.3** — **PB-0008 Windows-browser PASS**; CHG/REV evidence):
  - **Environment: Windows-browser** (실제 Windows Chrome/149 via `bin/win-browser.py` relay `http://172.28.64.1:9223`, https://172.28.73.199:18080). 배포: main `ae9226f`(PR #347) → `docker compose build web` + `up -d`(healthy). 검증 동안만 `.env WEB_ALLOWED_HOSTS` 에 WSL IP 추가 후 복원(종료 후 "Invalid host header" 거부 복귀 실측).
  - **마이그레이션 라이브 검증**(MySQL agent_memory): `WebProductDatasourceDbRules` 의 `UQ_WebProductDsDbRule` UNIQUE **제거됨**(uniq:0) + `SortOrder` 컬럼 추가(sortcol:1) — fast-path catchup 등록(MAJOR#2)으로 재기동 반영.
  - **다중 규칙 라이브 확인**: product 109 / datasource `mssql-dk-dev` 에 규칙 2개 추가 POST 연속 성공(rule_id 9·10) — UNIQUE 제거로 (product,ds) 당 복수 규칙 공존(총 3개, 2번째 POST duplicate-key 없음). GET db-rules ruleCount=3.
  - **종속(중첩) UI 실 렌더**(eval DOM 스냅샷 — 스크린샷은 폰트-로드 타임아웃 환경 이슈로 대체): `.cov-db-rule-card` 3개, 각 카드 = [규칙 N · 패턴(code) · 한도 pill · 수정/삭제] + **"이 규칙으로 추가된 DB N개"(`.cov-db-rule-dblist`) 중첩 섹션** + "+ 규칙 추가" 버튼. 실측 카드: ①`(^GameLog_[0-9]{3}$)|(^dk_game_release_[0-9]{3}$)` 한도3(실 운영 규칙) ②`^zzz_pb_a_` 한도3 ③`^zzz_pb_b_ (제외:_tmp$)` 한도5. 각 카드 hasEdit/hasDel=true.
  - **종속 N>0 비재현 사유**: mssql-dk-dev 의 사용자 DB 11개가 전부 기존 manual allowlist → 규칙 dedup 으로 rule-owned 0개("이 규칙으로 추가된 DB 0개"). 비파괴로는 rule-owned 행 재현 불가 → 중첩 *구조*(섹션·필터 rule_id===rule.id)는 실 렌더로, 중첩 *엔트리*는 단위/jsdom 으로 커버.
  - **삭제 격리 라이브**: 테스트 규칙 9·10 을 `DELETE /db-rules/{id}?strip=1` 로 정리 → 실 GameLog 규칙 1개 보존(remaining=[`(^GameLog_[0-9]{3}$)`]). RuleId 스코프 strip 으로 타 규칙 불변 확인.
  - **단위(정적)**: `verify_db_rule_logic.py` 30/30(순수 helper·ReDoS·audit 가드) + `verify_db_rule_ui.mjs` 18/18(복수형 엔드포인트·카드/폼·rule_id 필터·중첩·manual 분리·CSS) + ast/node.
  - **Pass/Fail: PASS** — 배포 시스템에서 다중 규칙 생성/공존·규칙 카드·DB 종속 중첩 섹션·삭제 격리·UNIQUE 제거 마이그레이션을 실제 Windows 브라우저로 실측 통과. CHECK#13 충족.
  - **Notes:** outside-voice(다중규칙 격리) SHIP-WITH-FIXES — A~G 확인, BLOCKER 0, MAJOR#1(INSERT IGNORE 중복방지)·#2(fast-path catchup) 흡수. 캐시버스터 `?v=20260618-db-rule-multi`.

### TASK-20260619T034522-oauth-google-foundation — Google 계정(OAuth) 로그인 토대 (REQ-20260619-0327, AC-0596~0601, Critical §12.3)
- **단위 테스트**: `tests/test_oauth_google_foundation.py` **36/36 PASS** (agent 이미지 격리 컨테이너, `PYTHONPATH=feature-0002-agent-core/src:feature-0003-agent-web-ui/src`, `import app`).
  - AC-0596 비활성 기본: `_oauth_google_configured()` flag/credential 조합 3 + `/start`·`/callback` flag-OFF 404 + `/config` enabled/disabled bool.
  - AC-0597 PKCE: challenge == base64url(sha256(verifier)) + verifier 엔트로피.
  - AC-0598 서명 state: roundtrip + tampered-sig 거부 + tampered-body 거부 + expired(TTL) 거부 + garbage 거부.
  - AC-0599 claim 검증: valid + issuer/audience/expired/nonce/email-unverified/domain 거부 + email_verified "true" 문자열 수용 + 도메인 화이트리스트 allow/block.
  - AC-0600 계정 매핑(FakeConn): subject 매칭 / email link(**UPDATE 에 PasswordHash 미포함=기존 비번 보존 단언**) / 신규 pending 자동 생성(role=3 + sentinel + ApprovedAt NULL).
  - AC-0601 sentinel: `_verify_password(*, OAUTH_NO_PASSWORD_SENTINEL)` 항상 False (3 케이스).
- **회귀**: feature-0002 + feature-0003 전체 pytest — 신규 회귀 **0**. 유일 실패 = 사전존재 `test_product_delete_block_conv` 2건이며 **base(main d639219)에서도 동일 실패**(product-delete RBAC, 본 변경과 무관) 대조 확인(`PYTEST_RC=1` 양쪽 동일). collection/import 오류 0.
- **정적**: `python3 -m py_compile app.py` OK.
- **Pass/Fail: PASS** (토대 단계). 배포·라이브 e2e(Google Cloud Console OAuth Client 등록 필요)·PB-0008(버튼 노출/로그인 화면)·ID token 서명검증은 활성화 cycle TODO(SECURITY.md §14.3).
- **Notes:** 기본 비활성(flag OFF)이라 라이브 OAuth round-trip 은 credential 주입 후에만 가능 — 토대 검증은 단위(순수 helper + FakeConn + flag-gating)로 완결. ID token 서명 미검증은 의도적 trade-off(§14.3 정직 기록).

- 2026-06-24 (TASK-0308 제품 탭 데이터소스 인사이트 탐색 상태 표시, **Minor §12.3** — **PB-0008 Windows-browser PASS**; CHG/REV-20260624T020000 evidence):
  - **Environment: Windows-browser** (실제 Windows 브라우저 — **사용자 직접 시각 검증**, 2026-06-24). win-browser.py relay/eval 가 아닌 운영자 본인의 실 화면 확인이며, 본 AI 세션은 배포·서빙·정적검증까지 수행. WSL headless 아님.
  - **배포**: main `6606b8e`(PR #396 머지) → `docker compose build web` + `up -d web`(repo-web-1 Up healthy). 서빙 검증(HTTP, 브라우저 캐시 무관, AI 수행): web 컨테이너 baked `/app/web/static/admin.js` 에 `ds-acc-insight` 1건 + 엔진 primary 색 분기(`ds-acc-engine" + (b.is_primary`) 1건 + `ds-acc-primary`(구 '기본' 텍스트 배지) **0건**(제거 확인), `/app/web/static/styles.css` 에 `ds-acc-insight` 4건, `admin.html` cache-buster `v=20260624-product-insight-badge`.
  - **검증 기법: 운영자 실 화면 육안 검증** — 제품 상세 '데이터 소스 & 접근 가능 데이터베이스' accordion 각 datasource 행 헤더에 인사이트 탐색 상태 아이콘(켜짐=눈 은은 / 꺼짐=빗금눈 amber 칩)이 표시되고, 기본(primary) 데이터소스가 엔진 배지 색(파랑)으로 구분되며, '기본' 텍스트 배지 제거로 아이콘 위치가 행마다 일정함을 확인. 사전 Artifact 목업(실 CSS·아이콘 렌더)으로 디자인 승인 → 배포 후 실 화면 일치 확인.
  - **Pass/Fail: PASS** — 배포된 시스템에서 인사이트 탐색 상태 표시 + primary 엔진색이 실제 Windows 화면으로 정상 동작함을 운영자 직접 확인. CHECK#13(PB-0008 Windows-browser) **충족**.
  - **Notes:** frontend only(admin.js·styles.css·admin.html cache-buster), 백엔드/마이그 0(insight_enabled 는 datasources API 기존 필드). OFF(amber) 표시는 insight 탐색이 꺼진 datasource 가 있을 때 노출(현재 mssql-qa-idc 는 TASK-0307 에서 활성화되어 ON 표시).

- 2026-06-24 (feature-0009 cycle `gc-settings-archive-leave` — 대화 ··· 메뉴 '보관' → 설정 팝업 이동 + 그룹 참여자 '나가기', **Minor §12.3**; CHG/REV-20260624T031337 evidence):
  - **Environment: CLI** (정적 소스 단언 + 적대적 리뷰; frontend-only, layout 비의존). 실렌더/클릭 동작의 최종 확인은 PB-0008(Windows-browser, 배포 후) — 본 변경은 worktree(WSL)에서 작성되어 PB-0008 미실행(메인 세션/배포 후 권장).
  - **정적**: `node --check static/app.js` PASS + CSS brace 균형 1489=1489.
  - **신규 jsdom-less 정적 테스트** `tests/verify_settings_archive_leave.mjs` **22/22 PASS**(함수 본문 중괄호 추출 + 문자열 단언):
    - openConversationItemMenu: '보관' 항목 제거 / '공유'·'설정' 유지.
    - openConversationSettings: '대화 관리' 섹션 + `canDeleteConversation`/`isGroupConversation` 판정 + `if (canArchive)` 분기 + 보관→`deleteConversation(cid)` / 나가기→`leaveConversation(cid)` + `(canArchive || isGroup)` 가드 + `.conv-settings-sec-danger`.
    - leaveConversation: `/members/` 엔드포인트 + `method:"DELETE"` + 본인 `state.user.id` + `window.confirm` + `refreshWorkspace`.
    - styles.css `.conv-settings-sec-danger` 규칙 존재.
  - **적대적 3-렌즈 리뷰(security/authz·correctness·UX)**: 실질 결함 0건(REVIEW.md REV-20260624T031337). client gate cosmetic(backend authoritative)·IDOR 없음(self id only)·버튼-권한 매핑 정합 확인. 1건 LOW 는 기존 환경의존(`is_group` PG-only, 본 변경 비도입).
  - **Pass/Fail: PASS**(정적 게이트). 백엔드/스키마/RBAC 무변경 — backend leave/archive 엔드포인트는 기존, 본 변경은 프론트 진입점·UI 재배치만. [SKIPPED:frontend-ui-archive-leave-relocation-no-backend-no-rbac for backend regression; CHECK#13 PB-0008 배포 후 권장].

- 2026-06-25 (TASK-20260625T021924-rule-db-coverage — 정규식 자동 규칙 추가 DB 의 insight 분석 여부·완료율 UI 표시, **Minor §12.3** — frontend-only; CHG/REV-20260625T021924 evidence):
  - **Environment: CLI** (jsdom 격리 + 정적 소스 단언 + 적대적 frontend 리뷰; frontend-only, layout 비의존). 실렌더/시각 정본은 PB-0008(Windows-browser, 배포 후) — 본 변경은 worktree(WSL)에서 작성돼 PB-0008 미실행(배포 후 사용자 확인 권장).
  - **정적**: `node --check static/admin.js` PASS.
  - **신규 테스트** `tests/verify_rule_db_coverage.mjs` **20/20 PASS**(`node verify_rule_db_coverage.mjs`, jsdom@22 설치 시 DOM 검증 포함):
    - DOM(jsdom) — `buildDbCoverageCells`: 분석 완료(4/5, schema_analyzed) → 마이크로바 80% fill·통계 '4/5'·분석 여부 'DB✓'·톤 ok / covRow null → '측정 대기'·측정 로딩 → '측정 중' / connected=false → '연결 불가'.
    - wiring(소스) — 규칙 카드 종속 DB 루프가 `productCoverage.per_db` 로 covByDb 구성 + `buildDbCoverageCells(covRow, …)` 호출 + db명 소문자 매칭 + `_isProductCoverageLoading` 측정상태 + 연결불가 `is-offline`.
    - wiring(M1) — 메인 목록 rule 행 skip 이 `if (_isRuleRow && canManage) return;` 조건부(read-only 뷰어 노출 보존, 무조건 skip 회귀 방지).
    - CSS — `.cov-db-rule-dbitem .cov-microbar` 폭·`margin-left:auto`·`.cov-db-stat` 폭.
    - cache-buster — admin.html styles.css/admin.js `?v=20260625-rule-db-coverage`.
  - **적대적 frontend 리뷰(6 렌즈: scope·데이터정합·orphan·null안전·CSS·staleness)**: BLOCKER 0 / **MAJOR 1 흡수**(M1 read-only 뷰어 orphan — 메인 목록 skip canManage 조건부화) / MINOR 2 수용(다중 ds 동명 DB 이름키·규칙 DB 초기화 버튼 미노출). REVIEW.md REV-20260625T021924-rule-db-coverage [SUBAGENT:adversarial-frontend-PASS] SHIP.
  - **Pass/Fail: PASS**(정적+jsdom 게이트). 백엔드/스키마/RBAC 무변경 — 백엔드 `_compute_product_insight_coverage` 는 이미 Source 무관 전체 DB coverage 를 `per_db[]` 로 제공, 본 변경은 표현계층 매칭만. CHECK#13 PB-0008(규칙 카드 분석 진척 표시) 배포 후 사용자 시각 검증 권장.

- 2026-06-25 (feature-0009 cycle `gc-other-msg-left` — 그룹대화 상대방 메시지 좌측 정렬, **Minor §12.3** — frontend CSS-only; CHG/REV-20260625T065430 evidence):
  - **Environment: Headless-render-mock** (실제 styles.css + `renderMessages()` DOM 구조 재현, Chromium headless; frontend CSS-only). 실 그룹대화 다수 참여자 메시지의 라이브 최종 확인은 PB-0008(Windows-browser, 배포 후) — 본 변경은 worktree(WSL)에서 작성돼 PB-0008 미실행(배포 후 사용자 시각 확인 권장).
  - **정적**: `node --check static/app.js` PASS(무변경 확인 — JS 미수정) + CSS brace 균형.
  - **충실한 mock 렌더 측정**: `scratchpad/bubble-align-mock.html`(실 styles.css 링크 + 5개 메시지 row: own·other·assistant·own·other+mention) 를 Chromium headless 로 렌더 후 각 버블의 좌/우 여백(px) 측정:
    - `is-user is-own-message` (내 메시지): leftGap 447/558, **rightGap 25 → 우측** (요청대로 유지).
    - `is-user is-other-message` (상대방): **leftGap 25 → 좌측**, rightGap 304.
    - `is-assistant`: **leftGap 25 → 좌측**, rightGap 73. (상대방과 동일 좌측 기준선 25px 확인.)
    - `is-user is-other-message is-mention-me` (멘션 하이라이트 상대방): **leftGap 25 → 좌측** + 주황 강조선 정상.
  - 증거: `artifacts/pb0008-gc-other-msg-left/bubble-align-result.png`(내 파란 버블 우측·상대방 회색 버블/assistant 흰 버블 좌측·멘션 주황 강조선 좌측, 육안 확인).
  - **Pass/Fail: PASS**(headless mock 게이트). 내 메시지=우측, 상대방·assistant=좌측 동일 기준선으로 사용자 요청 충족. JS/백엔드/스키마/RBAC 무변경. [SKIPPED:frontend-css-presentation-no-logic for backend/panel; CHECK#13 PB-0008 배포 후 실 그룹대화 권장].

- 2026-06-29 (TASK-20260629T114221-metadata-bootstrap-mssql-db — 메타데이터 부트스트랩 MSSQL database 차원 + 패널 잘림, **Major §12.3** — cross-engine 골격 introspection; CHG/REV-20260629T114221 evidence):
  - **Environment: WSL-headless-Playwright(repo-browser-1) + 실 HTTPS API(curl, admin 세션)**. 실 Windows 화면 최종 확인은 PB-0008 — worktree(WSL)에서 작성돼 미실행(배포 후 사용자 시각 확인 권장, 선례 동일).
  - **정적**: `python3 -m py_compile app.py` PASS · `node --check static/admin.js` PASS · CSS 1줄 교체(브레이스 영향 없음).
  - **백엔드 introspection 직호출(app 내부 함수)**: MSSQL `mssql-qa-idc`/`GunzGame` → `_bootstrap_collect_skeleton_mssql` 88 실테이블(`_CurrencyType`·`Account`·`AccountItem`…)·전부 schema_name=GunzGame·임시(`#`)테이블 0 / `Account` DB 17테이블·`GameLog` 36 / MySQL `mysql-local` 센티넬·시스템스키마 제외 확인.
  - **실 HTTPS 엔드포인트(curl, `mysql_ai_session` admin)**:
    - `GET …/bootstrap/schemas?datasource=mssql-qa-idc` → engine=mssql·unit_kind=database·129개(tempdb/master/model/msdb 없음).
    - `GET …/bootstrap/schemas?datasource=mysql-local` → engine=mysql·unit_kind=schema·13개(`__invalid_default_db__` 센티넬 제거).
    - `POST …/bootstrap {mssql-qa-idc, GunzGame}` → 88테이블·전부 schema_name=GunzGame·temp 0·컬럼 포함.
    - `POST …/tables/suggest {mssql-qa-idc, GunzGame, Account}` → target=description·grounded=true(29컬럼 introspect)·정확 한국어 설명(claude-haiku-4).
  - **Playwright 브라우저 서비스(eval, admin 로그인)**: 메타데이터 탭 노출(권한)·tables 서브뷰 전환·부트스트랩 패널 `display=block`·`offsetParent!=null`(visibleOnPage)·`.admin-meta-bootstrap-result` computed `maxHeight='none'`(패널 잘림 해소)·DS=mssql-qa-idc 선택 시 라벨 '데이터베이스 *'·status '129개 데이터베이스'·GunzGame 88 table-name 렌더(`GunzGame.Account`…). 증거: `artifacts/shared/out/browser/claude_verify_dbdropdown.png`.
  - **§18.8 적대 verification panel (general-purpose 2-lens, cross-feature 0002 포함)**: lens1 보안 VERDICT SAFE(SQLi·allowlist·의존함수 실재·시스템객체·RBAC·dialect 컨텍스트·자원누수). lens2 정합성: 1차 **MAJOR**(Path A — describe_table 컬럼 오버레이 read 축이 schema_name=DB 규약과 불일치) → tools.py overlay 키=pin DB명 수정 → 2차 재검증 **BLOCKING**(pin DB명 소문자 정규화 vs 저장값 원본 케이스, PG `=` case-sensitive 0행 — 라이브 검증 DB 가 전부 대문자 포함이라 우연 통과한 회귀) → kb_metadata.py `LOWER` case-insensitive 수정 → 3차 재검증 **VERDICT SAFE**(NIT 2 선재·비회귀 수용).
  - **Path A 검증(코드/런타임)**: `_tool_describe_table` 가 MSSQL 일 때 `get_active_default_db()`(소문자 'gunzgame') 로 오버레이 조회 → `load_column_descriptions_for_table` 가 `LOWER(schema_name)=LOWER(%s)` 로 저장값 'GunzGame' 과 매치(panel 런타임 `LOWER('GunzGame')='gunzgame'` TRUE 확인). 함수 호출처 `tools.py:789` 단일(Path A 격리). `py_compile` tools.py·kb_metadata.py PASS. (라이브 노출 단언은 column_descriptions DB 0행이라 미수행 — 코드/축 정합 + panel 3-pass 로 검증; PB-0008 배포 후 실 컬럼 설명 저장 시 사용자 확인 권장.)
  - **Pass/Fail: PASS**. 사용자 보고 3건 전부 해소: (1) 테이블 설명 AI 자동완성 정상(이미 구현+grounding 복구), (2) 테이블명 오류=tempdb 임시테이블 → 실 DB 실테이블, (3) 패널 내부 잘림 해소(maxHeight none). + describe_table 컬럼 오버레이 MSSQL read 축 정합(Path A, panel 적발·수정). RBAC/스키마/마이그 무변경. [PB-0008 Windows-browser 배포 후 사용자 시각 확인 권장].

### TEST-20260629T080500-new-conv-dedup — 새 대화 첫 전송 시 사이드바 대화 중복 제거 (frontend-only, CLI/jsdom)
- **Environment: CLI/jsdom** (frontend-only — backend/스키마/RBAC 무경유). `node --check src/static/app.js` PASS.
- **신규 회귀 가드 `tests/verify_new_conv_dedup.mjs` 18/18 PASS** (Node v18.19.1 + jsdom@22, `/tmp/node_modules`):
  - **[A] 정적 불변식**: lazy-create optimistic 등재 정확히 2곳(early-cid + fallback) · 각 등재 *직전* 윈도에 `pendingConversationEntries.delete(busyKey)` · 등재 *직후* `renderConversationList()` · 등재 키 `topic: message.slice` 2곳/`title: message.slice` 잔존 0 · 첨부 경로 `topic: "(파일 첨부 중)"`(title 잔존 0) · index.html app.js cache-buster `20260629d-new-conv-dedup`.
  - **[B] 실 `renderConversationList` jsdom 추출·실행**: (B1) 수정 후 상태(placeholder 제거 + conversations 에 topic 항목 1개) → in-flight placeholder 0 · draft 0 · 실 대화 항목 정확히 1개 · 제목=메시지(폴백 '새 대화' 아님). (B2) 회귀 재현 상태(placeholder 존재 + title 키 항목) → placeholder 1 + 실 항목 1 = 사이드바 2개 동시 표시 · title 키 항목은 폴백 '새 대화' 로 표시(중복의 '새 대화' 출처 문서화).
- **무회귀**: 기존 `tests/verify_conv_entry_defaults.mjs` **20/20 PASS** · `tests/verify_date_group_collapse.mjs` **22/22 PASS**(대화 목록 로직 동일 영역).
- **Pass/Fail: PASS**. 사용자 보고("새 대화에서 요청 보내면 현재 대화 + 별도 '새 대화' 중복 생성") 해소: optimistic 항목과 placeholder 의 동시 렌더 창 제거 + optimistic 항목 메시지 제목 표시.
- **미수행(배포 후 사용자 확인 권장)**: PB-0008 Windows-browser 실 화면 검증(새 대화 첫 전송→사이드바 항목 1개·중복 0·진행 중 placeholder 비중복) — WSL worktree 라 미실행(frontend-only render, 선례 동일). REV-20260629T080500-new-conv-dedup [SKIPPED:frontend-ui-render-state-no-backend-no-rbac] 적용 예정.

### TEST-20260630T005923-share-joinable-confirm-persist — 공유 '링크 생성' 참여 허용 확인 모달 + '참여 허용' 체크박스 대화별 영속 (Critical 인접 §12.3 인가/프라이버시 UX, frontend-only)
- **Environment: agent 이미지 pytest (DB 없이 — static read + inspect.getsource)** + CLI `node --check`. backend/스키마/RBAC 무경유(app.py diff 0).
- **기존 owner-guard 회귀 가드 `tests/test_share_joinable_owner_guard.py`** — 리팩터 후에도 인가 불변식 보존되도록 3 assertion 갱신(f1 `intended`+최종 joinable 강제 false, f2 cid 파라미터, f3 cid 전달). B1~B3(백엔드 403 게이트·INSERT 선행·admin 우회 없음) 무변경 PASS.
- **신규 회귀 가드 `tests/test_share_joinable_confirm_persist.py` 7/7 PASS**:
  - **[P 영속]** P1 헬퍼 존재+기본 ON(`!== false`)·정규화, P2 openShareDialog 초기값 복원(`joinableInit ? ' checked' : ''`)+change 영속, P3 promptShareExpiry cid 복원+change/확정 영속.
  - **[C 확인 게이트]** C1 `confirmShareJoinable` 존재, C2 '링크 생성' 이 confirm→취소중단→발급 순서(인덱스 단언), C3 비소유자 canAllow=false 분기에서만 '허용' 버튼 렌더(비소유자 강제 false), C4 확인 모달 CSS 존재.
- **통합 회귀**: 공유 테스트 13/13 + **feature-0003 전체 pytest 548 PASS(회귀 0)**. `node --check src/static/app.js` PASS.
- **§18.8 적대 패널 2렌즈**: 보안/authz VERDICT SAFE(5가설 REFUTED·BLOCKING 0), UX/regression VERDICT SOUND(5가설 REFUTED·BLOCKING 0). 상세 REV-20260630T005923-share-joinable-confirm-persist.
- **Pass/Fail: PASS**. 요청1(생성 직후 참여 허용 확인 모달)·요청2(체크박스 상태 대화별 유지=회귀 해소) 코드/테스트 검증 완료.
- **미수행(배포 후 사용자 확인 권장)**: PB-0008 Windows-browser 실 화면(링크 생성→'참여 허용 확인' 모달·취소 시 발급 중단·체크박스 토글 후 재진입 상태 유지) — WSL worktree 미실행(frontend render, 선례 동일).

### TASK-0016 graphux-expand-relax — 더블클릭 확장 시 신규노드 겹침 해소(주변 노드 부드럽게 밀어냄) (frontend-only, feature-0016 연계)
- **Environment: Windows-browser** (실제 Windows Chrome/149 via `bin/win-browser.py` relay `http://172.26.144.1:9223`, https://localhost/admin — 인증 세션). 관리콘솔 메타데이터 > 🕸 그래프 뷰, 데이터소스 mssql-qa-idc.
  방법론: 배포 전 **런타임 인젝션 검증** — 실 그래프·실 데이터에 대해 신규 relax 설정(numIter 250·nodeRepulsion
  16000·반경 R 밖 고정)을 그대로 실행해 실측·스크린샷 캡처(코드와 동일 config). **정식 배포 후 배포 번들로 최종 재확인.**
- **정량 실측**:
  - depth-2 덴스 확장(Achievement*, 128노드·신규 120): seed 겹침쌍 **502 → relax 후 17**(96.6%↓), fcose **153ms**.
  - depth-1 확장(Achievement, 4컬럼): 겹침쌍 **4**, fcose **49ms**, 컬럼 ordinal 세로스택 보존(1@dy75·2@105·3@135·4@165).
  - locality: 반경 밖 far 노드 이동 최소(depth-2 far 4중 0 이동) — 원거리 문맥 보존.
- **시각(스크린샷 아티팩트)**: `scratchpad/pb0008-04..06` — 신규 노드가 주변 테이블을 밀어내 겹침 해소, 컬럼 세로스택+round-taxi 유지.
- **Pass/Fail: PASS**(인젝션 검증) — 사용자 보고 2건 해소: (1) 더블클릭 시 컬럼 세로스택 가시화(겹침 제거로 판독), (2) 신규 노드가 주변 노드를 부드럽게 밀어냄(겹침 502→17). 잔여 minor 겹침(극단 depth-2 17쌍)은 numIter 250(perf) 유지 trade-off.
- **배포 후 최종 확인 (배포 번들, 2026-07-01) PASS**: web 재배포(git_commit=e2efac2, soak 통과) 후 배포된 `admin.js?v=graphux-expand-relax` 로 동일 시나리오 재확인 — 검색 achievement→Achievement 더블클릭 확장(신규 120, 총 300노드) 결과 **겹침쌍 0**, Achievement 컬럼 ordinal 세로스택 유지(1@dy75·2@105·3@135·4@165). 스크린샷 `scratchpad/pb0008-07-DEPLOYED-final.png`.

### TASK-0016 ERD 카드 — 컬럼을 테이블 compound 박스 안에(겹침 원천 차단) (frontend-only, feature-0016 연계)
- **Environment: Windows-browser** (실 Windows Chrome/149 via `bin/win-browser.py` relay, https://localhost/admin 인증 세션). 메타데이터 > 🕸 그래프 뷰, mssql-qa-idc.
  방법론: 배포 전 **런타임 인젝션 검증**(코드와 동일 로직: 컬럼을 테이블 compound 자식으로 재부모 + fcose alignment/relativePlacement 제약). **정식 배포 후 배포 번들 재확인.**
- **정량 실측**: 3 테이블 박스·컬럼 25 — 컬럼 순서 top→bottom **보존(true)**, 최상위 박스 겹침 **1쌍**(이전 satellite 11쌍), fcose 131ms. node --check OK.
- **Pass/Fail: PASS**(인젝션) — 사용자 보고(더블클릭 시 컬럼 스택이 이웃 테이블과 겹침, 3회) 해소: 컬럼이 테이블 박스 안 ordinal 세로 목록으로 들어가고 fcose 가 박스 bounds 로 이웃 공간을 확보해 겹침 원천 차단.
- **배포 후 최종 확인**: web 재배포(배포 번들) 후 다컬럼 테이블 더블클릭 PB-0008 재확인 예정.

### TASK-20260701T163000-graphview-render — 그래프 뷰 3건(마커 렌더-타임·클러스터 선택 상세·클러스터명 좌정렬/무잘림) (feature-0003 프론트 + feature-0002 백엔드 cross-cut, Major §12.3 — **PB-0008 Windows-browser PASS**)
- **Environment: Windows-browser** (실 Windows Chrome/149.0.7827.200 via `bin/win-browser.py` 무권한 relay `bridge_mode: relay`, endpoint `http://172.26.144.1:9223`, https://localhost/admin 인증 세션). WSL headless 아닌 실제 Windows 화면.
  - 방법론: 백엔드 baked(정적자산은 이미지 내장, 신규 엔드포인트는 재빌드 필요)라 **프리뷰 인젝션 검증** — 변경 `admin.js`/`admin.html`/`styles.css` 를 실행 중 web-a·web-b `/app/web/static/` 에 주입(디스크 서빙, cache-buster `?v=20260701-graphview-render` 로 신규 번들 강제). 데이터소스 `mssql-06656002eda6`(mssql-qa-idc), 250 노드·스키마 클러스터 50.
- **정량 실측**:
  - **②클러스터 선택 상세 — PASS**: `accountdb` 클러스터(compound parent) 클릭 → 우측 상세 패널이 배지 '스키마 클러스터' + 이름 `accountdb` + 섹션 '테이블 (58)'(C_CouponSupplyType 등 목록)로 갱신. 클릭 클러스터 선택 강조(gold border) 확인. 이전(클릭 무시) 대비 정상 갱신.
  - **③클러스터명 좌정렬·좌여백·무잘림 — PASS**: 오버레이 라벨 div 50개 생성(클러스터 1:1). `accountdb` 박스 좌상단 (64,122) 기준 라벨 (74,126) = **좌여백 +10px·상단 +4px 정확**(marginOkX/Y true). `whiteSpace:nowrap`·`textAlign:left`·`scrollWidth==clientWidth`(**무잘림**). native 스키마 라벨 `label:""`(숨김, 이중표시 없음). 줌 1.7배 시 라벨 재배치(90,93)·폰트 16px 클램프 — `cy.on('render')` 동기화 정상.
  - **①마커 렌더-타임 — 백엔드 로직 실DB 정합 + 프론트 배선**: 신규 집계 쿼리를 실 KB PG(`node_analysis_jobs`)에 직접 실행 → 로드한 scope `mssql-06656002eda6` 에 done 335·active 183·distinct 826, `accountdb`(done=t)·`accountdb.GMRIP`(done=t) 정확 반환. 프론트 `_metaGraphSyncAnalysisMarkers` 가 로드/검색/확장 직후 `GET .../graph/analyze/status` 호출·마커 적용하도록 배선(현재 프리뷰는 백엔드 미배포라 404 → **graceful skip**: 그래프 250노드 정상 렌더, JS 예외 0 실측). 마커 렌더 최종 확인은 **실배포(web 재빌드) 후**.
- **Pass/Fail: PASS**(②③ 라이브 실측 + ①백엔드 실DB 정합·프론트 배선·graceful). CHECK#13(PB-0008 Windows-browser) **충족**(웹 자산 변경에 이번 cycle Windows-browser Run 기록).
- **배포 후 최종 확인**: web 재빌드·재배포(deploy_scope: included — 백엔드 포함) 후, mssql-qa-idc 그래프 진입 시 분석완료 노드(≈335)에 보라 마커·진행중(≈183)에 주황 마커가 **클릭 없이** 렌더되는지 PB-0008 재확인.

### TASK-0016 ERD 박스 벌림 + 박스 클릭/더블클릭 정합 (frontend-only, feature-0016 연계)
- **Environment: Windows-browser** (실 Windows Chrome/149 via `bin/win-browser.py` relay, https://localhost/admin 인증 세션). 메타데이터 > 🕸 그래프 뷰, mssql-qa-idc.
  방법론: 배포 전 **런타임 인젝션 검증**(코드와 동일 로직: 증분 경로 신규-박스 감지 시 전체-스프레드 config). **정식 배포 후 배포 번들 재확인.**
- **정량 실측(인젝션)**: 141테이블 compound 전체-스프레드(`randomize:false`·`packComponents:true`·`numIter:1000`·`nodeRepulsion 18000`·고정없음) → 테이블 박스겹침 **886 → 0**, fcose **109ms**. node --check OK. 캐시버스터 `admin.js?v=20260701-erd-spread`.
- **Pass/Fail: PASS**(인젝션) — 사용자 보고 2건 대응: (4) 밀집 뷰 박스겹침(886→0 벌림), (5) 박스 클릭/더블클릭 정합(tap 핸들러 Table 예외로 단일=상세·더블=확장, 일반 노드와 동일). 적대리뷰 MAJOR(hasCompound 과발동) 수정 — full-spread 는 신규 노드가 박스를 들여올 때만 발동.
- **배포(2026-07-01)**: web 무중단 롤링 `git_commit=a6bf0eb`(PR #511 머지), soak 90s 통과, edge /healthz 200. 배포 자산 서빙 검증: `GET /static/admin.js?v=20260701-erd-spread` 에 `newAddsBox` 마커 3건 baked(HTTP 정본). 그래프 뷰 UI 로드 sanity(실 Windows Chrome relay screenshot): 관리콘솔>메타데이터>🕸 그래프 뷰 진입·렌더 정상(범례·검색·이웃깊이·상세 패널), 배포 회귀 0. 스크린샷 `scratchpad/pb0008-graphview-empty.png`.
- **라이브 인터랙션 검증 — 사용자 실화면 확인 요망(자동 tool 차단)**: (a) 밀집 박스겹침 해소 + term 국소 push, (b) Table 박스 단일=상세·더블=확장 정합 은 **canvas(cytoscape) 노드 클릭/더블클릭이 필요**한데, 이번 세션 win-browser 자동화가 막힘 — Chrome 149.0.7827.200 자동업데이트로 Playwright eval(주입 검증) UtilityScript 파손 + tool 이 canvas 좌표 클릭·더블클릭(350ms)·native `<select>` datasource 전환 미지원(메모리 project-pb0008-eval-regression-chrome200). 배포 전 **인젝션 실측(886→0, 109ms)** + **적대 리뷰(tap 로직 확인·MAJOR 수정)** 로 코드 정합은 확증. 최종 화면 동작은 이슈 신고자(사용자)의 실 브라우저 확인이 정본 — 선례(FPS·인터랙션 효과 PB-0008 사용자 확인) 동일.

### TASK-20260701T220000-graphview-webgl-labels — 클러스터명 오버레이 WebGL 렌더러 호환 수정 (frontend-only, Minor §12.3 — **PB-0008 Windows-browser PASS**)
- **Environment: Windows-browser** (실 Windows Chrome/149.0.7827.200 via `bin/win-browser.py` 무권한 relay `bridge_mode: relay`, endpoint `http://172.26.144.1:9223`, https://localhost/admin 인증 세션). WSL headless 아닌 실 Windows 화면.
  - 방법론: graphview-render(§18) + graph-webgl(§17) **병합 번들**을 실행 중 web-a·web-b `/app/web/static/` 에 프리뷰 인젝션(admin.js/html/styles.css + **vendor/cytoscape.min.js 3.34.0**). cache-buster `20260701-graphview-webgl-labels`. 데이터소스 mssql-06656002eda6(mssql-qa-idc).
- **정량 실측(WebGL 렌더러 하)**:
  - **회귀 적발(수정 전)**: cytoscape 3.34.0 `renderer.webgl=true` 확인. 초기 로드 후 오버레이 `labelDivs=0`(미표시). 진단: `cy.on('render')` 가 WebGL 렌더러에서 emit 0(pan 후 renderFires=0) — 반면 `_metaGraphSyncClusterLabels()` 수동 호출은 35 divs 정상 생성·`renderedBoundingBox` 정상. → 이벤트 바인딩이 근본원인.
  - **수정 후 PASS**: 이벤트를 `render viewport resize layoutstop add remove` + node `position drag free` 로 교체 → 로드 시 **labelDivs=35** 자동 생성(webgl=true), `cy.panBy({120,60})` 후 라벨 transform `(308,435)→(428,495)` = **+120/+60 정확 추종**(tracked=true). 클러스터 tap → 상세 '스키마 클러스터 / 테이블 (130)' 렌더. 좌상단 좌정렬·무잘림 유지(스크린샷 `scratchpad/graphview-webgl-final.png`).
- **Pass/Fail: PASS** — WebGL 렌더러 하에서 클러스터명 오버레이(생성·pan/zoom 추종)·클러스터 상세가 정상 동작함을 실 Windows 브라우저로 실측. CHECK#13(PB-0008 Windows-browser) **충족**.
- **배포 후 최종 확인**: web 재빌드·재배포(graph-webgl WebGL + graphview-render 동시 첫 배포) 후 라이브에서 클러스터명·상세·①마커(백엔드 배포분) 재확인.

### TASK-20260701T100738-convswitch-opacity-guard — 좌측 대화 선택 시 대화창 미표시 방어 하드닝 (frontend-only, Minor §12.3 — **PB-0008 Windows-browser PASS**)
- **Environment: Windows-browser** (실 Windows Chrome/149.0.7827.200 via `bin/win-browser.py` 무권한 relay `bridge_mode: relay`, endpoint `http://172.26.144.1:9223`, https://localhost/ 인증 세션 bootstrap_admin). WSL headless 아닌 실 Windows 화면.
  - 방법론: 정적자산 baked 라 배포 전 **프리뷰 인젝션** — 변경 `app.js`·`index.html` 을 실행 중 web-a·web-b `/app/web/static/` 에 주입(cache-buster `?v=20260701-convswitch-opacity-guard` 로 신규 finally-guard 번들 강제 서빙 확인). 데이터 bootstrap_admin 54 대화.
- **정량 실측(Windows Chrome)**:
  - 앱 로드 → served `app.js?v=20260701-convswitch-opacity-guard`(finally-guard 번들) 확인, 로그인 세션 유지(authHidden=true).
  - 대화 A(`…1c170112`) 선택 → messageLog `computedOpacity` 0.70(fade-in 중간 샘플) → **정착 1**(inline=""), `msgs=4`, `visibility:visible`, 제목 "dbgame 스키마의 item 테이블 구조를 알려줘" 갱신, ghost 0. 스크린샷 `scratchpad/pb0008_convselect.png`(테이블 구조·인덱스 구성·특징·메시지 전부 가시).
  - 대화 A→B(`…1669c81d`) 전환(크로스페이드 begin→finally commit 경로) → `msgs=2` 렌더, 제목 "dbgame 스키마에 어떤 테이블들이…" 갱신, opacity fade-in 후 1 수렴.
- **Pass/Fail: PASS** — 하드닝 후 대화 선택/전환이 실 Windows 브라우저에서 정상 렌더(opacity 1 정착)·회귀 0. CHECK#13(PB-0008 Windows-browser) **충족**(웹 자산 변경에 이번 cycle Windows-browser Run 기록). 보강: headless browse 5대화 전부 op1·렌더, `node --check` PASS, §18.8 적대 리뷰 VERDICT PASS.
- **배포 후 최종 확인**: web 재빌드·재배포(deploy_scope: included) 후 라이브에서 대화 선택 렌더 + 새 cache-buster(`20260701-convswitch-opacity-guard`) 서빙 재확인.

### TASK-20260702-graphview-webgl-polish — 그래프 뷰 WebGL 외곽선 선명화 + 테이블 단일클릭 컬럼 인라인 토글 (frontend-only, Minor §12.3, /_template:resume 재개)
- **Environment: Windows-browser** (PB-0008, `bin/win-browser.py` relay `http://172.26.144.1:9223`, https://localhost/admin — 관리콘솔 메타데이터 > 🕸 그래프 뷰). **이번 재개 cycle 라이브 인터랙션 실측은 미수행 — 사유(정직 기록)**:
  - (1) 원본 세션(cfbede21)이 **두 기능(WebGL 외곽선 선명화·단일클릭 컬럼 토글)을 이미 실 Windows-browser 로 라이브 검증**했다(세션 기록: "두 개선 동시 검증 — 박스 외곽선·컬럼 점·텍스트 선명 + `DT_RestartLocation` 컬럼 6개 ERD 카드 인라인 펼침" + "FPS 59fps 유지"). 그 세션이 계정 session-limit 로 중단돼 리뷰/버그수정/랜딩만 미완이었고, 본 재개가 그 후속을 완수.
  - (2) 재개가 **추가/변경한 델타**(접힘 시 `introspected.delete` 버그 수정 · #519 결정론 컬럼 seed 재정합 · canvas-2D 폴백 pixelRatio 회귀 수정)는 (a) 코드가 아직 미배포(pre-commit 시 라이브는 구 graph-perf2 서빙) (b) 그래프 canvas 노드 클릭 자동화가 PB-0008 회귀 이력(Chrome UtilityScript eval) — 공유 Windows 인프라라 quiet-time 별도 승인 필요 → 라이브 클릭 인터랙션 자동 재현 불가. **정적 검증으로 대체**: `node --check` PASS + §18.8 적대 패널 REV-20260702T000000-graphview-webgl-polish VERDICT PASS(축1~6 안전 + vendored Cytoscape 3.34 pixelRatio/webglTexSize 소스 검증).
- **배포 후 최종 확인(필수)**: web 재빌드·재배포(deploy_scope: included) 후 (a) baked 자산 검증 — `GET /static/admin.js?v=20260702-graphview-webgl-polish` 에 `webglTexSize`·`_metaGraphToggleColumns`·`introspected.delete` 마커 HTTP 정본 확인 + (b) **사용자 실화면 인터랙션 확인 요망**: 테이블 노드 단일클릭 → 컬럼 세로 스택 펼침 / 재클릭 접힘 / **접었다 재펼침 시 컬럼 재출현**(introspect 테이블) / 줌인 외곽선·텍스트 선명 / 더블클릭 이웃확장 무회귀.
- **Pass/Fail: 정적 PASS(코드정합·리뷰) + 원본 세션 라이브 PASS(2기능) · 재개 델타 라이브 = 배포 후 사용자 실화면 확인 대기**. CHECK#13(PB-0008 Windows-browser) 충족(웹 자산 변경에 이번 cycle Windows-browser Run·미수행 사유 기록).

### TASK-20260701T230501-doc-sync-rn-0701 — 릴리즈노트 07-01 블록 신규(+7) + 캐시버스터 bump (doc_sync, 비-정책 콘텐츠 doc-only)
- **Environment: Windows-browser (PB-0008)** — **미수행(사유 명시, 카고컬트 방지)**: 본 변경은 사용자 노출 릴리즈노트 **콘텐츠 데이터**(`static/release-notes-data.js`) + `index/admin.html` 캐시버스터 토큰 bump 뿐으로, 릴리즈노트 **렌더 로직(`release-notes.js`) 무변경** — 새로 시각검증할 UI 동작/상호작용 델타가 없다(데이터 콘텐츠 변경). 또한 (a) 본 실행은 무인 cron doc_sync 라 인터랙티브 Windows-browser 브리지(`bin/win-browser.py` relay) 미가동, (b) 배포는 cron wrapper 소관(post-merge)이라 pre-commit 시점엔 신 콘텐츠 미서빙.
- **원천 UI 변경 07-01 PB-0008 PASS(provenance)**: 본 블록이 announce 하는 실제 화면 변화는 각 feature cycle 이 이미 실 Windows-browser 로 검증 — TASK-20260701T163000-graphview-render **PASS**, TASK-20260701T220000-graphview-webgl-labels **PASS**, TASK-20260701T100738-convswitch-opacity-guard **PASS**(위 §3 Run 기록). 잔여 graphview-webgl-polish·graph-panel-perms canvas 인터랙션은 배포 후 사용자 실화면 확인 대기(자동화 회귀 이력).
- **Pass/Fail: PASS(콘텐츠 doc-only 정적 검증)** — `node --check release-notes-data.js` PASS + vm 로드 generated=2026-07-01·07-01 블록 7항목 스키마 정합. CHECK#13(PB-0008 Windows-browser) 충족(웹 자산 변경에 이번 cycle Windows-browser Run·미수행 사유 기록).

### Run (2026-07-02) — TASK-20260702-aiops-panel: AI 운영 관제 패널 + LLM 계측 확장 (Major §12.3, cross-unit feature-0002/shared/0003)
- **단위 PASS**: `tests/test_ai_ops.py` **10/10**(PYTHONPATH=feature-0002/src:feature-0003/src:worktree-root, `import app`) — T1 taxonomy self-surface(등록 매핑 + 미등록/None/공백→ai.other.unmapped) · T2 ask-worker age 밴드(10/90/300/None→ok/degraded/down/down) + inprocess na · T3 datasource worst-of(ok/unstable→저하/circuit_open→중단/빈→unknown) · T4 PG 미가용 부분 degrade(pg_available=False, 200, banner=축 기반, ask na, Attention 표면화) · T5 PG 가용 빈 결과(banner ok, categories 빈, workers_total=2) · A1 권한 403(console.access-only, TestClient require_permission) · R1 `_record_llm_usage` latency_ms(미전달=NULL byte-동치, 명시값 123 전달) · R2 usage 없음→INSERT 스킵.
- **회귀 PASS**: `test_permission_dependency_map.py` 16/16(v2 리스트 console.aiops.read 포함) · `test_dashboard_overview.py` 20/20 · `test_usage_conversations.py`+`test_llm_usage_quota.py` 28/28. 전체 `tests/` collection 무오류(app import 무결성).
- **마이그**: `bin/migrate-lint.sh` (적대 리뷰어 실행) `✓ PASS expand-safe`(0030 ADD COLUMN 비-DROP, down_revision 0029 체인).
- **정적**: `py_compile`(app.py·llm.py·model_catalog.py·routers/ai_ops.py·admin_console.py·마이그·test) PASS · `node --check`(admin.js·verify_admin_tab_gating.mjs) PASS.
- **탭 게이팅 회귀**: `tests/verify_admin_tab_gating.mjs`(jsdom@22 로컬 설치 실행) — 신규 ai-ops 케이스 2건 **PASS**([admin] console.aiops.read→표시 · [빈권한] console.access-only→숨김 fail-open 방지). 기존 '시스템 그룹라벨' 2 FAIL 은 로컬 jsdom 버전 artifact(main 동일 선재 32p/2f, 본 feature 무관; agent 이미지 CI jsdom 에선 정상).
- **§18.8 적대 패널**: 3-렌즈 AGENT-TEAM BLOCKING 0 (REV-20260702T140000-aiops-panel). NIT 3 반영(stream_options 회귀방지·CSS cache-buster 되돌림·mjs 게이팅 케이스)·2 수용기록.
- **Environment: Windows-browser (PB-0008)** — **배포 후 라이브 예정**: 본 변경은 신규 백엔드 라우터(`/api/admin/ai-ops`) + 마이그(0030) + 프론트 패널을 포함해, 프리뷰 static 인젝션만으론 검증 불가(백엔드/스키마 재적재 필요). 정합 순서 = cycle-finalize(main 병합) → web-a/web-b 재배포(마이그 자동적용) → **실 Windows-browser(win-browser.py relay @ 172.26.144.1:9223, Chrome 149, doctor OK)로 패널 렌더·상태 배너·KPI·카테고리 드릴다운·타일 deep-link(대시보드→ai-ops)·탭 권한 게이팅(admin 노출/operator 미노출) 실측** → 스크린샷 첨부. (win-browser 브리지 가동 확인 완료 — 배포 후 즉시 수행.)
- **Pass/Fail: PASS(단위·회귀·정적·마이그·게이팅·적대패널)**. CHECK#13(PB-0008)는 deploy-backed 완료 기준상 배포 후 라이브 실측으로 충족 예정(위 순서, 미수행 사유·수행 계획 명시).
- **[POST-DEPLOY 갱신 2026-07-02] PB-0008 Windows-browser 라이브 실측 PASS**: PR #526 main 병합(c5e259db) → web-a/web-b 재배포(healthz/readyz/livez=200, git_commit=c5e259db) → `/api/admin/ai-ops` 미인증 401(등록·게이트 확인). **실 Windows 브라우저(win-browser relay, Chrome 149) 실측**: admin 세션에서 `data-admin-tab="ai-ops"` 탭 display:flex·visible(권한 게이팅 라이브 동작), 클릭 시 패널 렌더 완료 — 배너(종합 상태 중단, worst-of)·상태 축 4종·KPI(워커 1/2·24h 566회·지연 계측이후)·Attention·**카테고리 드릴다운 13행**(에이전트 추론 $11.22·인사이트 분석 등 실집계)·계측 커버리지 전부 표시(loading 해제). **대시보드 'AI 상태' 타일 deep-link 클릭 → activePane="ai-ops"(aiOpsActive=true) 실측**. 스크린샷 2매(pb0008_ai_ops_panel·pb0008_dashboard_tile). → CHECK#13 실충족.
- **[POST-DEPLOY 갱신] 마이그 0030 적용 hotfix**: 배포 자동 마이그레이션이 stale agent 이미지(head=0029)로 0030 을 **미적용**(deploy exit 0)한 것을 포착 → postgres superuser 로 `ALTER TABLE agent_runtime.llm_usage ADD COLUMN IF NOT EXISTS latency_ms INTEGER` + alembic_version stamp 직접 적용·검증(`latency_ms integer YES`, `alembic_version=0030`). 근본 수정은 별도 cycle(deploy-web.sh reorder+MIGRATE_ALEMBIC_IMAGE, PR #530, REV-20260702T160000-migrate-fresh-image). insight/ask-worker 도 계측 코드로 재빌드·recreate(15e0befc). — 상세 REPORT.md.

### Run (2026-07-02) — TASK-20260702-aiops-scroll: AI 운영 현황 pane 세로 스크롤 (Minor §12.3 — feature-0003 프론트 CSS 단독)
- **정적 검증 PASS**: `styles.css` brace balanced(1701/1701). pane 세로 스크롤 셀렉터에 `.admin-pane[data-admin-pane="ai-ops"].is-active` 추가(dashboard/usage 와 동일 `overflow-y:auto; overflow-x:hidden` 상속). cache-buster `styles.css?v=20260702-aiops-scroll`.
- **§18.8**: [SKIPPED:minor-css-scroll] — 2줄 CSS 셀렉터 편입, 신규 로직 0. REV-20260702T170000-aiops-scroll.
- **Environment: Windows-browser (PB-0008)** — 배포 후 라이브 실측 예정: web 재배포(cache-buster styles.css bump 로 신 CSS 강제 로드) → 실 Windows 브라우저에서 AI 운영 현황 탭 진입 → **pane 세로 스크롤 동작 + 하단 커버리지 섹션 도달** 실측 + 스크롤 스크린샷. (CSS-only 변경이나 실 렌더 스크롤은 PB-0008 이 정본.)
- **Pass/Fail: PASS(정적·CSS·적대 skip 근거)**. CHECK#13(PB-0008)는 배포 후 스크롤 실측으로 충족 예정.
- **[POST-DEPLOY 갱신 2026-07-02] PB-0008 세로 스크롤 라이브 PASS**: PR #531 병합(b915e121) → web 재배포(soak 통과, git_commit=b915e121, 신 CSS `styles.css?v=20260702-aiops-scroll` 서빙 확인) → 실 Windows 브라우저(win-browser relay, Chrome 149) 실측: AI 운영 현황 pane `overflow-y:auto`·`overflow-x:hidden`, scrollHeight 1340 > clientHeight 684 (**canScroll=true**), 하단까지 스크롤(scrollTop=656=maxScroll) → **이전에 잘려 도달 불가하던 '계측 커버리지' 섹션 완전 노출**(스크린샷 pb0008_scroll_bottom). → CHECK#13 실충족.

### TASK-20260702T021700-attach-count-scope — "+" 메뉴 첨부 개수 배지 대화 전환 후 stale 수정 (frontend-only, Minor §12.3 — /_template:entry arg-given)
- **정적 검증(pre-commit 정본)**: `node --check app.js` **PASS**. 근본원인·수정 정합 §18.8 적대 패널 REV-20260702T021700-attach-count-scope — 초기 FAIL(MAJOR 1: delete/leave 계열 갭) → loadHistory 두 exit 배지 재렌더 추가로 수정 반영 후 정합(BLOCKING 0). 코드 trace: 배지 setter = `_renderAttachmentPills` 유일 / 재렌더 훅 4지점(beginPendingConversation·_switchToPendingConversationContext·loadHistory×2)이 switchConversation 외 모든 컨텍스트 진입·전환·삭제 랜딩 경로 커버.
- **Environment: Windows-browser (PB-0008)** — **미수행(사유 명시, 카고컬트 방지)**: 본 변경은 client-side JS(`app.js`)로 web 이미지에 baked 되어 **재배포 전에는 라이브에 미서빙**(현 서빙 `app.js?v=20260701-convswitch-opacity-guard` = 수정 전 — 버그가 라이브에 존재함은 확인). 또한 relay 모드 실 브라우저 검증(`bin/win-browser.py` @ 172.26.144.1:9223, Chrome 149.0.7827.200 — 브리지 doctor OK 확인)은 **사용자의 실제 Windows Chrome 을 점유**(공유 인프라·사용자 화면 필요)해 무인 dispatch 시점에 자동 인터랙션(로그인→첨부→대화 전환→배지 확인) 수행이 사용자 세션 침해. **배포 후 라이브 확인으로 이행**.
- **배포 후 최종 확인(필수)**: web 재빌드·재배포(deploy_scope: included) 후 (a) baked 자산 검증 — `GET /static/app.js?v=20260702-attach-count-scope` 서빙 + 4개 `_renderAttachmentPills()` 훅 마커 확인, (b) **사용자 실화면 인터랙션 확인 요망**: ① 대화 A 에 파일 첨부 → "+" 열어 배지 개수 확인 → "새 대화" 클릭 → "+" 배지 **비워짐** / ② 대화 A 첨부 후 다른 기존 대화 B(첨부 없음) 전환 → 배지 비워짐, 첨부 있는 B 면 B 개수 / ③ 첨부 있는 활성 대화 **보관/나가기** 후 다른 대화 랜딩 → 배지가 삭제 대화 개수 잔류 안 함.
- **Pass/Fail: 정적 PASS(코드정합·적대검증) · 라이브 = 배포 후 사용자 실화면 확인 대기**. CHECK#13(PB-0008 Windows-browser) 충족(웹 자산 변경에 이번 cycle Windows-browser Run·미수행 사유·배포 후 수행 계획 기록).

### Run (2026-07-02) — graph-ctxmenu: 메타데이터 그래프 뷰 노드 우클릭 상세 상호작용 (Major §12.3 — frontend-only, 코드 거주 feature-0003 / 문서 정본 feature-0016-metadata-graph TASK §24)
- **정적·dev-loop 검증 PASS**: `node --check admin.js` PASS + WSL-headless-harness(그래프 블록 + 실 admin.html 마크업 + mock apiFetch) **28/28 PASS** — 네이티브 우클릭 이벤트 경로(canvas capture preventDefault + G6 node/combo/edge/canvas:contextmenu)·kind 별 메뉴·관계 상세 패널(방향·신뢰/추정 w·근거·로컬 조인 컬럼·행 클릭 이동)·중심 보기 지속 칩·1회성 hop 확장·기존 클릭/더블클릭/접기 회귀·콘솔 에러 0. 상세: `unit/feature-0016-metadata-graph/docs/TEST.md` graph-ctxmenu 절.
- **§18.8**: ux/design/qa 3인 적대 패널 — MAJOR 3 전건 수정(엣지 우클릭 메뉴·로컬 조인 컬럼 표기·중심 보기 지속 칩). REV-20260702T121500-ai-claude-feature-0016-graph-ctxmenu (feature-0016 REVIEW.md).
- **Environment: Windows-browser (PB-0008)** — **배포 후 라이브 실측 예정(커밋 시점 미수행 사유 명시, 카고컬트 방지)**: 본 변경은 web 이미지에 baked 되는 정적 자산(admin.js/styles.css/admin.html)이고 배포 스파인 `bin/deploy-web.sh` 는 origin/main HEAD 만 배포하므로 **머지 전 라이브 반영 불가**. cycle-finalize(main 병합) → web-a/web-b 재배포(cache-buster admin.js `?v=20260702-graph-ctxmenu2`·styles.css `?v=20260702-graph-ctxmenu` 신자산 강제 로드) → 실 Windows 브라우저(win-browser relay)로 그래프 뷰 우클릭 메뉴(노드/컬럼/용어/클러스터/엣지/빈캔버스)·관계 상세 패널·중심 보기 칩·기본 메뉴 차단·기존 상호작용 회귀를 실측하고 본 Run 에 POST-DEPLOY 갱신을 기록한다. (canvas 노드 우클릭의 무인 자동화가 Chrome eval 제약으로 막히면 스크린샷+가능 범위 실측 후 사용자 실화면 확인 요망 항목을 명시.)
- **Pass/Fail: 정적·dev-loop·적대패널 PASS · 라이브 = 배포 후 PB-0008 실측 대기**. CHECK#13 충족(웹 자산 변경에 이번 cycle Windows-browser Run·미수행 사유·배포 후 수행 계획 기록).
- **[POST-DEPLOY 갱신 2026-07-02] PB-0008 Windows-browser 라이브 실측 PASS**: PR #538 main 병합(16fc1598) → deploy-web.sh 무중단 롤링(web-a/web-b git_commit=16fc1598, soak 90s 통과) → 자산 서빙 검증(`admin.js?v=20260702-graph-ctxmenu2` 신규 심볼 10건·`styles.css?v=20260702-graph-ctxmenu` 신규 클래스 20건·admin.html 버스터 정합). **실 Windows 브라우저(win-browser relay, Chrome 149 — Playwright eval 회귀 해소 확인) 라이브 실측**: 로그인 세션에서 메타데이터 > 그래프 뷰 → 데이터소스 `mssql-06656002eda6`(실데이터 239~258노드) 전환 후 ① **테이블 노드 우클릭(pointer 시퀀스) → 컨텍스트 메뉴 전 항목 표시**(dt_MonsterDrop — 배지·상세 보기 포커스 링·관계 상세·관계 확장 1/2/3-hop chips·중심 보기·컬럼 펼치기·AI 능동 분석·FQN 복사) ② **관계 상세 패널 렌더**(해당 노드 관계 0 → 빈 상태 안내 정상; 관계 행·신뢰 배지·근거·행 클릭 이동은 dev-loop harness 28/28 정본) ③ **중심 보기(메뉴 경유) → 지속 칩 "🎯 중심 보기: dbo ✕ 전체 보기" + 258노드 부분 그래프 → ✕ 클릭 → roots 복귀·칩 제거** ④ **스키마 클러스터 우클릭 메뉴**(클러스터 상세·스키마명 복사) ⑤ **Escape dismiss**. 브라우저 기본 메뉴 차단 확인(캔버스 영역 preventDefault). 스크린샷 4매: `artifacts/feature-0016-metadata-graph/20260702-graph-ctxmenu-pb0008/pb-{1..4}-*.png`. → CHECK#13 실충족.
- **비고(라이브 데이터 상태)**: 현재 roots 투영은 REFERENCES 엣지 희소(게임 DB FK 미선언 — 알려진 상태). 관계 행이 채워진 패널·엣지 우클릭 메뉴는 harness(실 응답 shape mock) 28/28 로 검증 — 추정 관계 축적 후 라이브 재확인 권장.

### Run (2026-07-02) — TASK-20260702-aiops-activity-paging: 활동 페이징 + main agent latency (Major §12.3 — feature-0003 web/UI·API + cross-unit feature-0002 core)
- **단위 PASS**: `tests/test_ai_ops.py` **15/15**(신규 5) — `_query_activity` cursor 미지정(has_more→next_cursor=마지막 id, WHERE 없음, ORDER BY id DESC) / cursor 지정(WHERE id<%s, params=(cursor, limit+1), no-more→next_cursor null) / activity 엔드포인트 데이터(items limit + next_cursor) / PG degrade(200, items 빈, next_cursor null) / 권한 403(console.access-only, TestClient). agent latency 는 기존 `test_record_llm_usage_latency_column`(passthrough) 커버.
- **회귀 PASS**: `test_route_parity_p5b`(골든 **195**, 신규 `/api/admin/ai-ops/activity` 반영) · permission 16 · dashboard 20 · usage 12 — 합 66 PASS. 전체 collection 무오류(agent_core 변경 import 포함).
- **정적**: `node --check` admin.js PASS. `py_compile` agent_core.py·ai_ops.py PASS.
- **§18.8**: 2-렌즈 적대 패널(agent_core hot-path + 페이징 backend / 프론트 XSS·더보기) — REV-20260702T180000-aiops-activity-paging.
- **Environment: Windows-browser (PB-0008)** — 배포 후 라이브 실측 예정(cache-buster admin.js bump): AI 운영 현황 → '최근 활동' **'더 보기' 클릭 → 과거 활동 append**(중복/누락 없이) + next_cursor 소진 시 '과거 기록 끝' + main agent 신규 호출의 latency 기록 확인 + 스크린샷.
- **Pass/Fail: PASS(단위·회귀·정적·적대패널)**. CHECK#13(PB-0008)는 배포 후 '더 보기' 실측으로 충족 예정.

### Run (2026-07-03) — graph-reltrace: 접힌 상태 관계 표시 + 관계 클릭 추적 + AI 능동 분석 연동 (Major §12.3 — frontend feature-0003 admin.js/styles/html + cross-unit feature-0002 metadata_graph 투영 / 문서 정본 feature-0016-metadata-graph TASK §32)
- **정적·격리 검증 PASS**: `node --check admin.js` PASS + `py_compile metadata_graph.py` PASS + 신규 함수 참조 심볼 전수 정의 확인. **엣지 집계 로직 격리 Node 11/11 PASS**(접힘=테이블-레벨 승격·펼침=컬럼-레벨·혼합·미렌더 graceful·다수 컬럼쌍 dedupe/trusted 승급·intra-table 제외) + `_metaGraphRelTraceRowsHTML` 추적 행 산출(data-trace 대상 정확·방향화살표·힌트). **백엔드 라이브 AGE**: dblog 스키마 신규 REFERENCES Cypher 실행 → `account.AccountId→arenabegin.AccountId`(conversation·candidate) 반환(FK null-status 포함·broken 제외·34-47ms 실측).
- **§18.8**: frontend + backend+qa 2렌즈 적대 패널 — frontend PASS-WITH-FIXES(MAJOR data-trace 따옴표 이스케이프 + MINOR 용어행 오라우팅·looksColumn 취약 전건 수정) / backend PASS(라이브 AGE 실측 확정). REV-20260703T152607-ai-root-feature-0016-graph-reltrace (feature-0016 REVIEW.md).
- **Environment: Windows-browser (PB-0008)** — **배포 후 라이브 실측 예정(커밋 시점 미수행 사유 명시, 카고컬트 방지)**: 본 변경은 web 이미지에 baked 되는 정적 자산(admin.js/styles.css/admin.html) + 백엔드 metadata_graph 투영이고, 배포 스파인 `bin/deploy-web.sh` 는 origin/main HEAD 만 배포하므로 **머지 전 라이브 반영 불가**. cycle-finalize(main 병합) → web-a/web-b + insight/ask-worker 재배포(cache-buster admin.js/styles.css `?v=20260703-graph-reltrace` 신자산 강제 로드 + 백엔드 schema_tables REFERENCES 활성) → 실 Windows 브라우저(win-browser relay, Chrome 149)로 **① 접힌 상태 테이블 간 관계 엣지 표시**(더블클릭 전) **② 상세 패널 "관계(N)" 행 클릭 → 대상 테이블·컬럼 추적**(대상 강조·카메라 이동) **③ AI 능동 분석 결과의 추적 가능 관계 행** 실측하고 본 Run 에 POST-DEPLOY 갱신을 기록한다. (canvas 노드 클릭의 무인 자동화가 막히면 CDP 실좌표 클릭 + 스크린샷으로 실측.)
- **Pass/Fail: 정적·격리(11/11)·라이브 Cypher·적대패널 PASS · 라이브 = 배포 후 PB-0008 실측 대기**. CHECK#13 충족(웹 자산 변경에 이번 cycle Windows-browser Run·미수행 사유·배포 후 수행 계획 기록).
- **비고(사전 결함 정리)**: 본 파일(feature-0003 TEST.md)에 origin/main 부터 미해결 병합 충돌 마커(`<<<<<<< / ======= / >>>>>>>`, graph-ctxmenu ↔ aiops-activity-paging Run)가 잔존해 있어, 두 Run 을 모두 보존하는 방향으로 함께 해소함(본 cycle 산출 아님·정리).
- **[POST-DEPLOY 갱신 2026-07-03] PB-0008 Windows-browser 라이브 실측**: PR #554 main 병합(7dcf2e8c) → deploy-web.sh 무중단 롤링(web-a/web-b git_commit=7dcf2e8c, soak 통과) + insight/ask-worker 재빌드 → 신자산 서빙 확인(`admin.js?v=20260703-graph-reltrace` 신규 심볼 6·`styles.css` amgr-tracehint). 실 Windows 브라우저(win-browser relay, Chrome 149)로 mysql-local 스코프 dblog 스키마 펼침 실측: **① 접힌 상태 테이블 간 관계 엣지 표시 PASS** — dblog 12테이블 전부 접힌 상태에서 `account ─ ─▶ arenabegin` 점선(추정) 엣지 렌더(더블클릭 전, 스크린샷 `artifacts/feature-0016-metadata-graph/20260703-reltrace-pb0008/01-collapsed-relations.png`). **② 부분 갭 발견**: 테이블 노드 단일클릭 상세 패널에 "관계(N)" 섹션 미표시(depth=1 fetch 는 테이블 기준 2-hop REFERENCES 미포함; 컬럼 단일클릭 depth=1 엔 정상) → **후속 reltrace-tabledetail(TASK §33)로 모델 병합 수정**. **③ AI 능동 분석 추적 행**은 모델 기반(`_metaGraphRelTraceRowsHTML`)이라 정상 — 최종 확인은 §33 재배포 후 통합.

### Run (2026-07-03) — reldetail-colexpand: 상세 패널 관계 컬럼 아코디언 + 방향 구분·개수 + 의미 툴팁 (Major §12.3 — frontend feature-0003 admin.js/styles/html / 문서 정본 feature-0016-metadata-graph TASK §35)
- **정적·격리 검증 PASS**: `node --check admin.js` PASS + **격리 로직 Node 8/8 PASS**(방향별 개수·컬럼 그룹화·참조함/받음 대상·관계없는 컬럼 plain·컬럼 self 분류·의미 툴팁 방향문장+근거+신뢰도·FK 툴팁) + **intra-table self-FK 2케이스 PASS**(리뷰 MAJOR 반영: manager_id 참조함 + id 참조받음 양방향, sc===tc 자기참조는 out 만).
- **§18.8**: frontend 집중 적대 리뷰 [SUBAGENT: PASS-WITH-FIXES] — MAJOR(intra-table self-FK 참조받음 누락)+MINOR(미정의 CSS 변수) 수정, XSS·아코디언·dedup·reltrace 회귀 CLEAN. REV-20260703T165147-ai-root-feature-0016-reldetail-colexpand (feature-0016 REVIEW.md).
- **Environment: Windows-browser (PB-0008)** — **배포 후 라이브 실측 예정(커밋 시점 미수행 사유 명시)**: 정적 자산(admin.js/styles.css/admin.html)이 web 이미지 baked + deploy-web 은 origin/main HEAD 만 배포 → 머지 전 라이브 반영 불가. cycle-finalize(main 병합) → web-a/web-b 재배포(cache-buster `?v=20260703-reldetail-colexpand`) → 실 Windows 브라우저(win-browser relay, Chrome 149)로 **① 컬럼 클릭 시 관계 아코디언 펼침 ② 참조함(→)/참조받음(←) 구분 ③ 방향별 개수 배지(→N ←M·전체 요약) ④ 관계 hover 시 의미 분석 툴팁(방향·근거·신뢰도)** 실측 후 본 Run 에 POST-DEPLOY 갱신을 기록한다.
- **Pass/Fail: 정적·격리(8/8+2)·적대패널 PASS · 라이브 = 배포 후 PB-0008 실측 대기**. CHECK#13 충족(웹 자산 변경에 이번 cycle Windows-browser Run·미수행 사유·배포 후 수행 계획 기록).
- **[POST-DEPLOY 갱신 2026-07-03] PB-0008 Windows-browser 라이브 실측 PASS (4항목)**: PR #561 main 병합(ecf84e24) → deploy-web.sh 무중단 롤링(web-a/web-b git_commit=ecf84e24, soak 통과) → 신자산 서빙(`admin.js?v=20260703-reldetail-colexpand` `_metaRelSemanticTip` 2건). 실 Windows 브라우저(win-browser relay, Chrome 149) mysql-local 스코프 dblog `account` 테이블 단일클릭 상세 실측(배포 중 PG 19s 재시작 transient "db connection failed" 1회 → 복구 후 정상): **① 컬럼 클릭 관계 펼침 PASS** — AccountId 컬럼 아코디언(🔗) 클릭 → aria-expanded=true, 관계 그룹 펼침. **② 참조함/참조받음 구분 PASS** — `→ 참조함 (1)` 방향 그룹 헤더 표시. **③ 방향별 개수 PASS** — 컬럼 배지 `→1 ←0` + 전체 요약 `관계 1 · 참조함 1 · 참조받음 0`. **④ hover 의미 툴팁 PASS** — 관계 행 title=`관계 의미 분석\ndblog.account.AccountId 이(가) dblog.arenabegin.AccountId 을(를) 참조합니다.\n근거: 대화 JOIN 학습 · 추정 관계 (신뢰도 49% — 실사용·프로브로 강화·감쇠)\n...`. 스크린샷: `artifacts/feature-0016-metadata-graph/20260703-colexpand-pb0008/04-accordion-expanded.png`. → 사용자 요청 4건 전건 라이브 충족. CHECK#13 실충족.

### Run (2026-07-03) — reltrace-tabledetail: 테이블 단일클릭 상세에 관계 표시(모델 병합) (Minor §12.3 — frontend-only, 코드 거주 feature-0003 / 문서 정본 feature-0016-metadata-graph TASK §33)
- **정적·격리 검증 PASS**: `node --check admin.js` PASS + **모델 병합 로직 격리 Node 5/5 PASS**(테이블 self 모델 병합 1건·대상 정확·컬럼 self dedup·broken 제외·self무관 제외).
- **§18.8**: frontend 집중 적대 리뷰(isSelf 정확성·dedup 방향·관계 상세 모델 병합·성능·회귀·nm 폴백). REV-20260703T160000-ai-root-feature-0016-reltrace-tabledetail (feature-0016 REVIEW.md).
- **Environment: Windows-browser (PB-0008)** — **배포 후 라이브 실측 예정(커밋 시점 미수행 사유 명시)**: 정적 자산(admin.js/admin.html)이 web 이미지 baked + deploy-web 은 origin/main HEAD 만 배포 → 머지 전 라이브 반영 불가. cycle-finalize(main 병합) → web-a/web-b 재배포(cache-buster admin.js `?v=20260703-reltrace-tabledetail`) → 실 Windows 브라우저로 **테이블 노드 단일클릭 → 상세 패널 "관계(N)" 행 표시 → 행 클릭 시 대상 테이블·컬럼 추적** + graph-reltrace 3항목(① 접힌 관계 ② 관계 클릭 추적 ③ AI 분석 추적) 통합 실측 후 본 Run 에 POST-DEPLOY 갱신을 기록한다.
- **Pass/Fail: 정적·격리(5/5)·적대패널 PASS · 라이브 = 배포 후 PB-0008 실측 대기**. CHECK#13 충족(웹 자산 변경에 이번 cycle Windows-browser Run·미수행 사유·배포 후 수행 계획 기록).
- **[POST-DEPLOY 갱신 2026-07-03] PB-0008 Windows-browser 라이브 실측 PASS (graph-reltrace 3항목 통합)**: PR #556 main 병합(b14eb117) → deploy-web.sh 무중단 롤링(web-a/web-b git_commit=b14eb117, soak 통과; 1차 시도 transient soak 실패→2차 성공) → 신자산 서빙(`admin.js?v=20260703-reltrace-tabledetail` `_metaKeyDisplayNode` 3건). 실 Windows 브라우저(win-browser relay, Chrome 149) mysql-local 스코프 dblog 실측: **① 접힌 상태 관계 표시 PASS** — dblog 12테이블 접힌 상태에서 `account ─ ─▶ arenabegin` 점선 엣지(01-collapsed-relations.png). **② 테이블 단일클릭 상세 관계 클릭 추적 PASS** — account 노드 단일클릭 → 상세 "관계(1)" 섹션 + 추적 행 `→ dblog.arenabegin.AccountId (conversation) 추정 w=0.49 🔎 추적`(읽기 쉬운 fqn, raw key 아님) 표시(02) → 행 클릭 → account·arenabegin 컬럼 펼침 + **대상 컬럼 강조 + 카메라 이동** + 상세 arenabegin 전환(03/04, 상태 "관계 추적 → AccountId (대상 테이블·컬럼 강조)"). **③ AI 능동 분석 추적 PASS** — arenabegin 능동 분석 완료(로그·이력 역할 분류) → 결과 박스 "연결 관계 추적 (1)" + 추적 행 `← dblog.account.AccountId 추정 w=0.49 🔎 추적`(05). 스크린샷 5매: `artifacts/feature-0016-metadata-graph/20260703-reltrace-pb0008/0{1..5}-*.png`. → graph-reltrace(§32)+reltrace-tabledetail(§33) 사용자 요청 3건 전건 라이브 충족. CHECK#13 실충족.

### Run (2026-07-02) — schema-card-ctxmenu: 스키마 카드 우클릭 + 카드 라벨 압축 (Minor §12.3 — frontend-only, 코드 거주 feature-0003 / 문서 정본 feature-0016-metadata-graph TASK §26)
- **정적·dev-loop 검증 PASS**: `node --check admin.js` PASS + WSL-headless-harness **ctxmenu 10/10 PASS**(카드 라벨=스키마명 전용+개수 우상단 badge·접힌 카드 우클릭 메뉴 펼치기/클러스터 상세/스키마명 복사·펼친 스키마 접기 항목·빈 스키마 badge=0·에러 0) + **graph-initview 회귀 31/31 PASS**. 큰 수(8122) badge 넘침·크래시 없음 확인. 상세: `unit/feature-0016-metadata-graph/docs/TEST.md` schema-card-ctxmenu 절.
- **§18.8**: general-purpose 적대 리뷰(G6 badge API·우클릭 라우팅·상태 정합·회귀). REV-20260702T172500 (feature-0016 REVIEW.md).
- **Environment: Windows-browser (PB-0008)** — **배포 후 라이브 실측 예정(커밋 시점 미수행 사유 명시, 카고컬트 방지)**: 본 변경은 web 이미지에 baked 되는 정적 자산(admin.js/admin.html)이고 배포 스파인 `bin/deploy-web.sh` 는 origin/main HEAD 만 배포하므로 **머지 전 라이브 반영 불가**. cycle-finalize(main 병합) → web-a/web-b 재배포(cache-buster admin.js `?v=20260702-schema-card-ctxmenu` 신자산 강제 로드) → 실 Windows 브라우저(win-browser relay, Chrome 149)로 스키마 카드 라벨(이름+개수 badge, "테이블" 문자열 없음)·**접힌 카드 우클릭 메뉴**(펼치기/클러스터 상세/스키마명 복사)·펼친 스키마 우클릭 접기·기존 우클릭/좌클릭 회귀를 실측하고 본 Run 에 POST-DEPLOY 갱신을 기록한다.
- **Pass/Fail: 정적·dev-loop·적대리뷰 PASS · 라이브 = 배포 후 PB-0008 실측 대기**. CHECK#13 충족(웹 자산 변경에 이번 cycle Windows-browser Run·미수행 사유·배포 후 수행 계획 기록).
- **[POST-DEPLOY 갱신 2026-07-02] PB-0008 Windows-browser 라이브 실측 PASS**: PR #544 병합(8fcda59c) → deploy-web.sh 무중단 롤링(soak 통과, 자산 `admin.js?v=20260702-search-badge` 서빙 확인) → 실 Windows Chrome 149(relay): `mssql-06656002eda6` 검색 `user` → **스키마 카드 12장 유지 + badge 매칭/전체(teal, accountdb 1+/58·atum2_db_1 11+/136), cap 도달 `+` 표기**, 검색 클리어 → 전체 개수(58) 원복. 종전 검색 시 badge 소실 결함 해소. 스크린샷 `artifacts/feature-0016-metadata-graph/20260702-search-badge-pb0008/`. → CHECK#13 실충족.
- **[POST-DEPLOY 갱신 2026-07-02] PB-0008 Windows-browser 라이브 실측 PASS**: PR #542 main 병합(100535f8) → deploy-web.sh 무중단 롤링(web-a/web-b git_commit=100535f8, soak 통과) → 자산 서빙 검증(`styles.css?v=20260702-schema-card-ctxmenu`·`admin.js?v=20260702-schema-card-ctxmenu` 라이브 확인). **실 Windows 브라우저(win-browser relay, Chrome 149 — eval 프로브 1+1=2 OK) 라이브 실측**: 메타데이터 > 그래프 뷰 → `mssql-06656002eda6`(62 스키마) 전환 → ① **62 카드 전부 라벨=스키마명 전용 + 개수 우상단 badge**(accountdb→58·AccountDB→33·atum2_db_1→136), 라벨에 "테이블" 문자열 0건(`anyTableWord=false`) — 카드 폭 과점유 해소 확인 ② **접힌 카드(accountdb) 우클릭(pointer 시퀀스: pointerdown/up button:2 + contextmenu) → 메뉴 표시**(헤더 "스키마 accountdb · 테이블 58" + 펼치기(58개)/클러스터 상세(펼치지 않음)/스키마명 복사) — **종전 무반응 결함 라이브 해소** ③ **"펼치기" 메뉴 클릭 → accountdb 58 테이블 라이브 펼침**(status "58개 펼침") ④ **펼친 스키마 "−" ctl(XS:) 우클릭 → "접기 (카드로)" 항목 노출**. 스크린샷 2매: `artifacts/feature-0016-metadata-graph/20260702-schema-card-ctxmenu-pb0008/pb-{cards-badge,card-ctxmenu}-live.png`. → CHECK#13 실충족.

### TASK-20260702T230501-doc-sync-rn-0702 — 릴리즈노트 07-02 블록 신규(+8) + 캐시버스터 bump (doc_sync, 비-정책 콘텐츠 doc-only)
- **Environment: Windows-browser (PB-0008)** — **미수행(사유 명시, 카고컬트 방지)**: 본 변경은 사용자 노출 릴리즈노트 **콘텐츠 데이터**(`static/release-notes-data.js`) + `index/admin.html` 캐시버스터 토큰 bump 뿐으로, 릴리즈노트 **렌더 로직(`release-notes.js`) 무변경** — 새로 시각검증할 UI 동작/상호작용 델타가 없다(데이터 콘텐츠 변경). 또한 (a) 본 실행은 무인 cron doc_sync 라 인터랙티브 Windows-browser 브리지(`bin/win-browser.py` relay) 미가동, (b) 배포는 cron wrapper 소관(post-merge)이라 pre-commit 시점엔 신 콘텐츠 미서빙.
- **jsdom DOM 렌더 검증(대체)**: `node verify_release_notes.mjs` — passed 33(전체 그룹 20·07-02 그룹 head 펼침·07-01 접힘·카운트 배지=항목수·관리 62/작업 85·work+common 96·XSS 제목/summary esc·빈 releases 가드) / failed 1(pre-existing admin release-notes pane `overflow-y:auto` CSS 규칙 — data-only 변경 무관, baseline 동일). `node --check release-notes-data.js` PASS.
- **원천 UI 변경 07-02 PB-0008(provenance)**: 본 블록이 announce 하는 화면 변화 중 graph-ctxmenu(PR#538)·graph-initview·search-badge(PR#544)는 각 feature cycle 이 실 Windows-browser 로 검증 PASS(위 §3 Run 기록). G6 v5 렌더러 전면 교체·rel-selfheal·더블클릭 카메라 팬은 배포 후 사용자 실화면 확인 대기.
- **Pass/Fail: PASS(콘텐츠 doc-only 정적+jsdom 검증)**. CHECK#13(PB-0008 Windows-browser) 충족(웹 자산 변경에 이번 cycle Windows-browser Run·미수행 사유·배포 후 계획 기록).

### Run (2026-07-03) — node-role-viz: AI 능동 분석 완료 테이블 역할 시각 표식 (Major §12.3 — 코드 거주 feature-0002/0003 / 문서 정본 feature-0016-metadata-graph TASK §33, ADR-010)
- **정적·단위·harness 검증 PASS**: `node --check admin.js` PASS · 신규 단위 test_node_analysis_role.py 10건 + relevance 28건 회귀 0 (합 38 PASS) · 전체 pytest(0002+0003) exit 0 · WSL-headless-harness(실 admin.html/admin.js/g6.min.js + mock API) 4 시나리오 ALL PASS·pageerror 0(미분석 teal 원형 / 폴 경로 role bake 칩색·아이콘·라벨색·캐시서명 / sync 경로 / 무효 role 방어) + 시각 스크린샷(역할 8종 칩+범례). 상세: `unit/feature-0016-metadata-graph/docs/TEST.md` node-role-viz 절.
- **§18.8**: 적대 패널 4렌즈(backend/frontend/ux·design/qa) — 결과는 feature-0016 REVIEW.md REV 항목.
- **Environment: Windows-browser (PB-0008)** — **배포 후 라이브 실측 예정(커밋 시점 미수행 사유 명시, 카고컬트 방지)**: 본 변경은 web 이미지 baked 정적 자산 + insight-worker 코드 + alembic 0031 이며 deploy-web.sh 는 origin/main HEAD 만 배포 — **머지 전 라이브 반영 불가**. cycle-finalize(main 병합) → alembic 0031 + web·insight-worker 재배포(cache-buster `admin.js?v=20260703-node-role-viz`) → 백필 role 데이터 생성 후 실 Windows 브라우저로 역할 칩 색/아이콘/범례/상세 패널 역할 칩을 실측하고 본 Run 에 POST-DEPLOY 갱신을 기록한다.
- **Pass/Fail: 정적·단위·harness PASS · 라이브 = 배포 후 PB-0008 실측 대기**. CHECK#13 충족(웹 자산 변경에 이번 cycle Windows-browser Run·미수행 사유·배포 후 수행 계획 기록).

### Run (2026-07-03) — role-legend-panel: 역할 범례를 우측 상세 패널 상단 세로·접힘으로 이전 (Minor §12.3 — frontend-only 표현 전용, 코드 거주 feature-0003 / 문서 정본 feature-0016-metadata-graph TASK §36)
- **정적·구조 검증 PASS**: 표현 전용(admin.html/styles.css, JS·데이터·API 무변경 — `node --check` 대상 없음). `.admin-meta-graph-legend-roles` 잔여 참조 0(html/css/js grep). 회귀 최대 리스크(범례 wipe) 구조적 방지 확인 — 상세 렌더 4곳(admin.js:4862/4885/5035/5368)은 `metadataGraphDetailBody`(실존) `.innerHTML` 만 교체, aside 는 `d.clientWidth`(admin.js:4245) 폭 조회로만 참조 → 새 `<details>` 범례(body/progress 의 형제)는 안 지워짐.
- **§18.8**: 적대 패널 [SUBAGENT] 7축(회귀·잔여참조·CSS변수·접힘UX·패널접기부작용·레이아웃·시인성) — BLOCKING 0, NIT 2(수용). 결과 정본 feature-0016 REVIEW.md REV-20260703T020000-…-role-legend-panel [SUBAGENT: PASS].
- **Environment: Windows-browser (PB-0008)** — **배포 후 라이브 실측 예정(커밋 시점 미수행 사유 명시, 카고컬트 방지)**: 본 변경은 web 이미지 baked 정적 자산(admin.html/styles.css)이고 `deploy-web.sh` 는 origin/main HEAD 만 배포 — **머지 전 라이브 반영 불가**(현 서빙 `styles.css?v=20260703-reltrace-tabledetail` = 수정 전). cycle-finalize(main 병합) → web-a/web-b 재배포(cache-buster `styles.css?v=20260703-reldetail-colexpand-role-legend-panel` 신 CSS 강제 로드) → 실 Windows 브라우저(win-browser relay)로 그래프 뷰 진입 → **① 역할 범례가 우측 상세 패널 상단에 세로로 표시**(칩 8종 색+아이콘) **② summary 클릭 → 접힘/펼침 토글**(카펫 rotate) **③ 노드 클릭 후에도 범례 유지(wipe 없음)** **④ 툴바 전폭에서 역할 범례 행 제거 확인** 실측하고 본 Run 에 POST-DEPLOY 갱신을 기록한다.
- **Pass/Fail: 정적·구조·§18.8 PASS · 라이브 = 배포 후 PB-0008 실측 대기**. CHECK#13 충족(웹 자산 변경에 이번 cycle Windows-browser Run·미수행 사유·배포 후 수행 계획 기록).
