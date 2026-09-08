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

### 20260901T1900-conv-status-dot-wiring 사이드바 대화 상태 배지 색 배선 복원 + 동종 배선 게이트 (Minor §12.3, 2026-09-01, feature-0003 프론트 단독) — **Environment: Windows-browser (PASS — `docs/test-runs.d/TASK-20260901T1900-conv-status-dot-wiring.md` · 배포 전 단계는 수정본 `src/static` 을 read-only bind-mount 한 별도 컨테이너 `https://localhost:18098/` 실측, 배포본 자산 재확인은 POST-DEPLOY 잔여)**

- **제보 재현(배포본 `mysql-ai-web:5a4d49fc`)**: 사이드바 151개 항목 중 `is-done` **110건** ·
  `is-error` **21건** · `is-canceled` **2건** — **133개가 상태를 정확히 알면서 computed
  `background-color` 가 전부 `rgb(196,196,201)`(기본 회색)**. 툴팁도 전부 빈 문자열.
  배포본이 가진 `.conv-dot.is-*` 규칙은 3개뿐이고 그중 `is-completed` 는 **아무도 만들지 않는
  죽은 규칙**(서버 어휘는 `done`), `is-stale-error` 는 코드가 만드는 `is-stale_error` 와
  구분자가 어긋나 있었다.
- **수정본 실측**: 같은 데이터에서 `is-done` → **`rgb(22,163,74)`**, `is-error` →
  `rgb(220,38,38)`, `is-canceled` → `rgb(128,125,114)`, 툴팁 `완료`/`오류`/`취소됨`.
  스크린샷 2장 동일 화면 대조(`evidence/convdot-live-defect.png` ↔ `evidence/convdot-fixed-sidebar.png`).
- **전송 시나리오 전이**: 폴링이 매 tick 부르는 `_updateConversationStatusDot` 를 실 대화 행에
  구동 — `pending`(파랑 .55) → `starting`(파랑 .55) → `processing`(주황) → **`done`(초록)**.
  `stale_error` 는 하이픈 클래스 + 링, 미지 상태는 modifier 없이 기본 회색으로 degrade.
- **in-flight 행**: 전송 중 `is-pending-inflight`(이탤릭·파랑 dot) / 전송 실패
  `is-pending-failed`(opacity .7 · 제목 빨강 · **dot `is-error`**). 두 클래스 모두 종전 CSS 0건.
  실패 행의 dot 이 `is-pending`(대기 색)이던 비대칭도 함께 정정.
- **실측이 잡은 초판 결함 2건**: ① 미지 상태 전이 시 직전 툴팁 잔존 ② 폴링이 사이드바의
  stale 구체 문구("마지막 활동: `<시각>`")를 일반 라벨로 퇴화. `data-title-status` 이음매로 해소 후 재실측 PASS.
- **자동 검증**: 컨테이너 `make test` **6829 passed / 15 skipped / 0 failed**(코드·게이트 변경
  전후 3회, 매번 실패 0) · 배선 계약 테스트 **10건 PASS**(컨테이너 내 개별 실행 포함) ·
  **회귀 뮤턴트 10종 전건 KILL** · node 실행 검증 · `node --check` 3파일.
- **§18.8 검증(`/codex review`)이 게이트의 사각지대 5건을 잡았다** — `[P1]` 0, `[P2]` 5.
  전부 「테스트는 통과하는데 결함은 살아 있다」 형태였고 다섯 건 모두 재현 확인 후 수정했다.
  근거·조치·뮤턴트 대조는 `REVIEW.md` REV-20260901T190000-conv-status-dot-wiring 참조.
- **잔여**: 실 LLM run end-to-end 전이는 개인 AI 브리지 러너 미연결로 미실측(전송 버튼
  `is-access-blocked`) — 폴링 함수 실 구동으로 같은 배선을 덮었고, 실 run 은 POST-DEPLOY 잔여.

### 20260901T1245-ai-conn-chip-postdeploy 연결 칩 프로필 행 이동 POST-DEPLOY 재실측 (docs-only, 2026-09-01) — **Environment: Windows-browser (PASS — 배포본 `40340f53` 자산 그대로, 주입 없음 — `docs/test-runs.d/TASK-20260901T1200-ai-conn-chip-to-profile-row-postdeploy.md`)**

- 서빙 자산 확인: `profile.css` 배치 규칙 1건 · `chat.css` footer 접힘 규칙의 `.ai-conn` 잔여
  **0건** · 칩이 `.sidebar-profile` 안(144행, `composer-footer` 406행보다 앞) · 라벨 4종 접두 없음.
- **16조합 전부 배포 전 실측치와 일치** — `.composer-footer` 전 조합 `display: none`(제보 여백
  해소), `admin`/`mckim` 네 상태 같은 줄·행 높이 65px 고정, 15자/21자 계정 아래 줄·가로 넘침 0.
- 측정 가드: 칩의 런타임 부모가 `.sidebar-profile` 이 아니면 조기 반환 — 통과.

### 20260901T0530-connect-modal-transition 명령 경로·«업데이트 필요» 갱신도 닫히도록 판정 축 교체 (Minor §12.3, 2026-09-01, feature-0003 프론트 단독) — **Environment: Windows-browser (배포 후 POST-DEPLOY 실측 — `docs/test-runs.d/TASK-20260901T0530-connect-modal-transition.md`)**

- **제보 재현**: 같은 테스트를 **현재 라이브 배포본**에 태우면 **6건 FAIL**(I1c·I1d·I2c·I2d·I3b·I4)
  — 사용자가 말한 두 상황이 코드로 확인된다. 수정본 **39/0 PASS**.
- **두 요청은 같은 뿌리**: 기준선을 «창을 열 때 고정» 한 것(명령 경로)과 판정 축이 `listening`
  한 축뿐이었던 것(업데이트 갱신). 기준을 **직전 관측**으로, 축을 **«쓸 수 있는 상태»**
  (`listening && !runner_stale`)로 올려 둘을 한 규칙으로 덮는다.
- **뮤테이션**: stale-blind-auto→I2c·I2d·I4 / stale-blind-launch→**H5** / msg-flat-auto→I2d·I3b /
  epoch 검증 전 `_lastObs` 갱신(codex P1 되돌림)→**J1**.
- **codex 적대 리뷰**: 1R **P1 1건**(늦은 응답이 다음 창의 «직전 관측» 을 오염 → 일어나지 않은
  전이) → 창 세대가 다르면 **기록조차 하지 않도록** 수정 + J1 신설 → 확인 라운드.
- **미잠금(정직 표기)**: 실행 경로의 문구 분기와 `_lastObserved.ok` 의 stale 검사는 뮤턴트가
  생존한다(자동 경로가 먼저 판정을 끝내 도달 희박 — 방어적 중복).

### 20260901T1200-ai-conn-chip-to-profile-row 연결 칩을 입력창 하단 → 사이드바 프로필 행 여백 (Minor §12.3, 2026-09-01, feature-0003 프론트 배치 단독) — **Environment: Windows-browser (PASS — `docs/test-runs.d/TASK-20260901T1200-ai-conn-chip-to-profile-row.md` · 배포 전 단계는 라이브 페이지에 변경본 CSS 주입 실측, 배포본 자산 재확인은 POST-DEPLOY 잔여)**

- **제보 재현**: 배포본 실측에서 `.composer-footer` 의 computed display 가 `flex` — 상태·힌트가
  모두 빈 평상시 화면에서도 입력창 아래 26px 한 줄이 상시 남는다. 접힘 규칙이 칩을 예외로 두는데
  칩은 늘 보이므로 규칙이 한 번도 매칭되지 않았다.
- **수정 후 16조합 실측**(4상태 × 계정 4종, 사이드바 252px): `.composer-footer` **전 조합
  `display: none`**. `admin`·`mckim` 은 네 상태 전부 프로필 행 같은 줄(행 높이 65px 고정,
  화살표→칩 18px, 이름 잘림 0), `bootstrap_admin`(15자)·`verylongaccountname_x`(21자)는 네 상태
  전부 아래 줄(90px)로 일관 + 이름 ellipsis + **가로 넘침 0** — 상태 전환에 따른 레이아웃 튐 0.
- **라벨 접두 제거의 근거**: 접두를 남기면 «대기 중»(85px)만 여백(119px)에 들어가고
  «연결 안 됨»(101px)·«업데이트 필요»(106px)는 화살표 자리까지 더해 초과 → 아래 줄. 행 높이가
  65↔90 을 오가며 사이드바 하단이 튄다.
- 자동 검증: 컨테이너 `make test` pytest 전건 PASS(rc=0) + ruff PASS ·
  `verify_connect_modal_autoclose.mjs` 25/0 · `verify_llm_restriction_surface.mjs` 35/0.
- 계약 테스트 방향 전환: `test_connection_chip_is_free_of_the_footer_collapse_rule` — 종전
  "접힘 조건에 칩이 **있어야** 한다" → "**없어야** 한다" + 칩이 프로필 행에 있고 배치·wrap
  규칙이 존재하는지. 조건이 남으면 여백이 그대로 돌아온다.

### 20260901T0330-connect-modal-launch-close 실행 성공인데 창이 안 닫히던 회귀 정정 (Minor §12.3, 2026-09-01, feature-0003 프론트 단독) — **Environment: Windows-browser (배포 후 POST-DEPLOY 실측 — `docs/test-runs.d/TASK-20260901T0330-connect-modal-launch-close.md` · 배포 전 단계는 순수 node 행위 테스트 + 라이브 배포본 대비)**

- **제보 재현**: 「내 AI가 대기 중입니다…」 를 받았는데 모달이 안 닫힌다는 제보를 시나리오 H 로
  고정했고, **현재 라이브 배포본에서 H3·H4 가 FAIL** 한다(제보 실재 확인). 수정본 **25/0 PASS**.
- **원인**: 직전 cycle 에서 codex P1-2 수용 범위를 넓혀 사용자가 직접 누른 실행까지 자동 경로의
  기준선에 묶었다 — 창을 열 때 이미 «대기 중» 이면 전이가 아니므로 아무도 닫지 않았다.
- **뮤테이션 8종**: revert→H3·H4 / success-epoch→**F4** / loop-epoch→F2a·F2b·F4 /
  response-epoch만→생존(`_connSeq` 가 1차) / seq+resp 둘 다→F3a·F3b·F3c / baseline→G1 /
  announced-guard→E3 / clearinterval→E2b.
- **제거한 단언**: 구 F1(「남의 러너로 닫히지 않는다」) — 그 단언이 이 회귀를 «올바름» 으로
  잠그고 있었다. 같은 상황을 H 가 반대 기대로 잠근다.
- **codex 독립 확인**: 트레이드오프 타당 · P1 0.
- **남은 위험(정직 표기)**: 남의 러너로 인한 오닫힘은 원리적으로 남는다(서버가 러너 소유를
  구분해 주지 않는 한). 의식적 트레이드오프이며 「연결 준비」 재클릭으로 복구된다.

### 20260831T1827-connect-modal-autoclose 연결 성립 시 토스트 + 모달 자동 닫기 (Minor §12.3, 2026-08-31, feature-0003 프론트 단독) — **Environment: Windows-browser (PASS — `docs/test-runs.d/TASK-20260831T1827-connect-modal-autoclose.md`)**

- **라이브 결함 재현(배포본 `1c0864dc`)**: 배지가 «내 AI 대기 중» 으로 바뀌어도 모달이 그대로
  남고 알림 0 — 그 모달이 바로 그 배지를 덮고 있다. 스크린샷 1장. 검증 후 `fetch` 원복·모달
  닫기·실제 상태 재조회로 브라우저 원상 복구.
- **행위 테스트** `tests/verify_connect_modal_autoclose.mjs` **25/0 PASS** — 실제 모듈을 최소 DOM
  shim 위에서 구동. 리스너를 저장·디스패치해 `[내 AI 실행]` 버튼 경로도 실제로 탄다.
  A(성립 → 토스트 1 + 닫힘) · B(이미 연결된 채 열기 → 안 닫힘) · C(토큰만 발급 → 안 닫힘,
  명령 보존) · D(중복 알림 없음) · E(import 경로 실재 · 닫으면 폴링 멎음 · 닫기가 막혀도 알림
  1회) · F(실행 버튼 경합 3종) · G(첫 조회 실패 후에도 전이 감지).
- **G11-b 결함 주입 실증**: 수정 전 코드(`git show main:…`)에서 **7건 FAIL**
  (A3·A4·A5·D1·E2a·E3·G1). 통과만 확인한 단언이 아니다. B·C 가 수정 전에도 PASS 인 것은
  정상(그 축은 깨뜨리지 않아야 할 성질이며 회귀 잠금으로 의미를 갖는다).
- **codex 적대 리뷰 3라운드**: 1R BLOCK(P1 2·P2 4) → 2R 승인불가(P1-1 잔존 + 새 P2) →
  3R **P1 0**. 뮤테이션 9종으로 방어 계층을 갈랐다 — 응답 epoch 검사만 제거·`_connSeq` 만
  제거는 각각 생존하고 **둘 다 제거할 때만** F3 가 죽는다(경합 재현). 상세는 REVIEW.md
  `REV-20260831T182700-…-connect-modal-autoclose`.
- **미검증(정직 표기)**: `_gateInFlight` 해제 전용 단언 없음(폴링 5초를 테스트에서 발화시킬
  수단 부재) · `ux`/`design` 도메인 심사 미수행(세션 도구 제약 — `[SKIPPED:tool-restricted:*]`).
- **미검증 축(정직 표기)**: 실 러너를 기동해 서버가 스스로 `listening:true` 를 내는 end-to-end
  경로는 AI 무인 완결 불가(개인 머신 AI CLI 설치·인증 필요)로 **미수행**. 이번 검증은 프론트엔드
  계약에 한정된다.

### 20260824T2030-dnd-reorder-affordance 드래그&드롭 이동에도 재배치 연출 (Minor §12.3, 2026-08-24, feature-0003 프론트) — **Environment: Windows-browser (PASS — `docs/test-runs.d/REV-20260824T203000-dnd-reorder-affordance.md`)**

- **실측**: 최상위 대화를 폴더로 **드래그&드롭**(합성 `dragstart/dragover/drop` + DataTransfer —
  앱이 실제 구독하는 경로) → 화면 y **175 → 145**, **7프레임 트윈**(59~158ms, 감속·오버슈트 0),
  도착 그룹 `🗂zz-dnd-임시`, **rail + "이동됨" 배지 부여**. root 드롭으로 원복 + 임시 폴더 정리 200.
- **de-risk(하네스)**: 151 PASS — DnD 배선 6건(두 이동 함수의 예약 · 예약↔데이터 반영 **순서** ·
  데이터 버전 bump · 실패 경로 제외). **뮤테이션 3종 전건 KILL**.
- **구조**: 드래그·'···' 메뉴 이동·root 드롭이 모두 `moveConversationToFolder`/`moveFolderTo` 로
  수렴 → 두 곳에 예약만 걸면 전 경로가 같은 코디네이터를 탄다(연출이 갈라질 여지 없음).

### 20260824T1900-reorder-affordance 재배치 연출 재설계 — 오버슈트 제거 + 도착 표식 (Minor §12.3, 2026-08-24, feature-0003 프론트) — **Environment: Windows-browser (PASS — `docs/test-runs.d/REV-20260824T190000-reorder-affordance.md`)**

- **모션**: 폴더 29px 이동 → 8프레임(112~226ms), offset 최소 **+1** = 목표를 지나치는 구간 없음
  (오버슈트 곡선이면 음수 구간이 나온다). 거리 적응형 하한(160ms) 대역.
- **도착 표식(핵심)**: 이동 직후 rail `inset 3px accent` + "이동됨" 배지(`aria-label`, absolute) →
  **무관한 재렌더(그룹 접기/펼치기) 후에도 유지** → 3.5초 뒤 자연 소멸(잔류 0).
- **de-risk(하네스)**: 145 PASS — 거리 적응형 대역 · 오버슈트 금지(제어점 y ∈ [0,1]) · 독립
  기대값(소스 추출 금지) · 타이머 지연값 · 표식 2층 수명 · **행 생성 시 부여 배선** ·
  **연속 이동 세대** · reduced-motion 표식 유지 · CSS 계약. **뮤테이션 7종 전건 KILL**.
- **실측이 잡은 결함 2건**(하네스 통과 상태): 후처리 복원이 두 번째 렌더에서 소실 / 오래된 만료
  타이머가 최신 표식 제거. 각각 구조 변경·세대 토큰으로 봉인 후 계약 추가.
- **계측 함정**: 정적 자산 `?v=dev` 캐시(→ CDP `Network.setCacheDisabled`), worktree 재생성 시
  컨테이너가 잡은 옛 디렉터리 inode(→ 컨테이너 재생성, `docker exec grep` 로 판정).

### 20260824T1800-reorder-easing 재배치 전환 easing → easeInOutBack (Minor §12.3, 2026-08-24, feature-0003 프론트 상수 1개 + duration) — **Environment: Windows-browser (PASS — 실측 기록 `docs/test-runs.d/REV-20260824T180000-reorder-easing.md`)**

- **정본 실측**: easing 검증은 정지 스크린샷으로 불가능하다(되돌아왔는지 볼 수 없다) — rAF 궤적의
  **offset 부호 반전**만이 오버슈트의 증거다. 폴더 29px 이동: 146 → **149**(반대로 3px) → 118 →
  **114**(3px 지나침) → 117 정착(25프레임/178~577ms). 대화 176px 이동: 318 → **336**(+18) → 161 →
  **124**(-18) → 142 정착(27프레임/317~748ms). 오버슈트 폭 = 이동 거리의 약 **10%** 로 스케일.
- **de-risk(하네스)**: 98 PASS — easing 이 소스 상수(`REORDER_EASING`)를 그대로 싣는지 +
  오버슈트 곡선 성질(제어점 y1 < 0 ∧ y2 > 1) 계약. 평범한 ease-in-out 으로 조용히 바뀌는 회귀 차단.
- **경계 확인**: duration 420ms 가 정리 watchdog(820ms) · 강조(1100ms) · 예약 TTL(4000ms) 안.
  오버슈트는 모든 이동 행에 같은 곡선이라 상대 간격 유지(겹침·클릭 타깃 흔들림 없음).

### 20260824T1644-sidebar-reorder-anim 좌측 대화목록 명칭 변경 시 재배치 전환(FLIP + 시야 유지) (Minor §12.3, 2026-08-24, feature-0003 프론트 단독) — **Environment: Windows-browser (PASS — 실측 기록 `docs/test-runs.d/REV-20260824T164437-sidebar-reorder-anim.md`)**

- **정본 실측**: 미머지 브랜치를 라이브 무접촉으로 보기 위해 라이브 web 이미지 + 본 worktree 의
  `src/static` 디렉터리 bind-mount 컨테이너(`https://localhost:18099`)를 띄우고, 실 Windows Chrome
  (CDP relay)에서 rAF 궤적을 계측했다. 정지 스크린샷으로는 순간이동/트윈을 가릴 수 없어 **프레임별
  화면 y + computed transform 잔여 offset** 을 정본 증거로 둔다. 계측기 자산화:
  `tests/pb0008_sidebar_reorder_measure.py --mode folder|conv`.
  - 대화 제목 변경(6월 그룹 → 오늘 그룹): 화면 y **442 → 233**, **19 프레임 트윈**(324~621ms),
    강조 324~1405ms, 잔류 인라인 스타일 0. 제목 원복 완료.
  - 폴더 이름 변경: 화면 y **175 → 146** / 재현 실행 **146 → 117**, 트윈 16 / 4 프레임. 임시 폴더 정리 완료.
  - 계측기 자체의 거짓 통과 방어 확인: 앵커 폴더 없이(이동이 실제로 없을 때) `verdict=instant-or-none`.
  - ⚠ 창을 전면화하지 않으면 Chrome 이 rAF/타이머를 throttle 해 **애니메이션이 진행되지 않고
    "전환 없음" 으로 거짓 판정**된다(실제 발생) — 계측기는 attach 직후 `bring_to_front()`.
- **de-risk(하네스)**: `tests/verify_sidebar_reorder_anim.mjs` **73 PASS** — 행 키 규약 · 예약
  게이트/TTL/1회 소비 · FLIP invert→play(duration 상수 일치) · 임계 상/하한 · 신규 행 제외 ·
  스크롤 복원/추종/불변 · reduced-motion 분기 · 접힌 조상 펼침(날짜 leaf+branch · 폴더 체인 ·
  순환 방어 · 무변경 시 미저장) · 호출 배선 · CSS 강조/접근성. **뮤테이션 5종 전건 KILL**.
- **회귀**: 사이드바 관련 기존 하네스 5종(21/20/31/23/23) 전건 PASS, 컨테이너 `make test` 에서
  본 변경 관련 실패 0(무관 1건 `test_oauth_exhaustion_gate` 은 컨테이너 `chattr` 부재로 **main 에서도
  동일 실패**), ruff clean.
- **미수행(사유 명시)**: 스크롤 밖 대상 추종은 검증 계정 목록이 한 화면에 들어와(`scrollHeight ==
  clientHeight`) 라이브 재현 불가 — 하네스 좌표 계약으로만 잠갔다.

### 20260807T1700-gc-guide-esc-capture 안내 툴팁 Esc 양보 무효 수정 (Minor §12.3, 2026-08-07, feature-0003 프론트 1줄) — **Environment: Windows-browser (선행 cycle 의 PB-0008 실측 #8 이 이 결함을 적발했고, 수정 확인도 실 브라우저 핸들러 순서가 정본이라 headless 대체 불가 — de-risk=하네스가 capture→bubble 2단계 디스패치 + 경쟁 오버레이 핸들러를 주입해 **라이브 조건**을 재현, 68/68 PASS + 되돌림 뮤테이션 6 red + `node --check` PASS + mjs 전수 49 suite exit 0, 정적 자산 web 이미지 baked → 라이브 재실측은 배포 후 잔여, visual_verification_scope: always)**
- 증상(PB-0008 라이브 실측 2026-08-07, 배포본 `f81c5bcb`): 멘션 자동완성이 열린 상태에서 Esc → 사용자는 목록만 닫으려 했는데 안내 툴팁도 함께 닫힘.
- 근본원인: 로직이 아니라 **핸들러 실행 순서** — 버블 단계라 먼저 등록된 멘션 AC 핸들러가 AC 를 닫은 뒤 우리 핸들러가 돌아 "열려 있지 않다" 로 오판.
- 수정: Esc 핸들러 **capture 등록**(`…, true`). 저장소 선례 `_attachShareRangeEsc` 와 동일 이유.
- **왜 선행 61 PASS 가 놓쳤나(기록)**: 가짜 DOM 에 경쟁 핸들러가 없어 단언이 *우리 함수만 있는 세계* 에서만 참인 **vacuous pass**. 뮤테이션 5/5 KILLED 였음에도 남은 사각은 **합성 미재현**이었다.
- **유닛 검증 — PASS**: `node tests/verify_gc_first_use_guide.mjs` **68/68**(신규 `[Esc 양보/라이브]` 5 + 과잉양보 반대방향 1 + capture 구조 단정 1). capture→버블 되돌림 시 **6 red**.
- **PB-0008 Windows-browser 재실측 — DEFERRED(배포 후)**: #8 축(멘션 AC 열림 중 Esc) + 선행 7축 회귀. `docs/test-runs.d/20260807T1500-gc-first-use-guide.md` 에 append.
- Pass/Fail: **PASS(코드/유닛 범위)** — 라이브 재실측은 배포 후 잔여. Runner: AI.

### 20260807T1500-gc-first-use-guide 그룹 대화 기능 첫 사용 1회 안내 툴팁 (Minor §12.3, 2026-08-07, feature-0003 프론트 단독 — 기능 정본 feature-0009) — **Environment: Windows-browser (첫 노출 위치·caret 지시·각 안내의 실 렌더 줄 수·멘션 자동완성과의 스택 순서는 실 브라우저 렌더가 정본이라 headless 대체 불가 — 이 환경에 브라우저 바이너리 없음; de-risk=`verify_gc_first_use_guide.mjs` 61/61(노출·소진·게이트·a11y·스타일 계약, 실 함수 본문 구동) + **뮤테이션 5/5 KILLED** + `node --check` PASS + 대비 계산 본문 9.15:1/제목 15.38:1/닫기 5.17:1 전부 AA 통과, 정적 자산 web 이미지 baked → 라이브 PB-0008 배포 후 잔여, visual_verification_scope: always)**
- 요청(사용자 2026-08-07): 그룹대화 참여 기능을 **처음 쓸 때**(각 그룹대화의 처음이 아니라) 한 줄 30자 이하 가이드 툴팁. 팝업은 화면을 가리므로 금지. 일반 대화·`@assistant` 요청 방법 포함.
- 기대: 그룹 대화 첫 진입에 컴포저 위 안내 5줄 노출 → "다시 안 보기" 후에는 **다른 그룹 대화·새로고침 어디서도 미재노출** / 입력·Esc 로 닫으면 이번 로드만 숨고 다음 방문에 재노출 / 1:1 대화 무노출 / 발화 불가 계정 무노출·무소진 / 멘션 자동완성이 카드 위에 뜸.
- **유닛·계약 검증 — PASS**: `node tests/verify_gc_first_use_guide.mjs` **61/61**. 뮤테이션 역검증 **5/5 KILLED**(입력-소진 복원·게이트 제거·Esc 양보 제거·z-index 60·caret wrap 잠식). 상세 fragment: `docs/test-runs.d/20260807T1500-gc-first-use-guide.md`.
- **§18.8 적대 패널(ux·design) — 양쪽 BLOCK 후 반영**: 입력 첫 타건이 안내를 영구 소진(복구 경로 없음)·발화 불가 계정에 거짓 안내·`z-index 60` 이 멘션 자동완성 가림 등. 반영 결과는 REVIEW.md `REV-20260807T153000-gc-first-use-guide` 2건 + artifact 2건.
- **PB-0008 Windows-browser 라이브 실측 — DEFERRED(배포 후)**: 위 fragment §4 의 6축을 실측하고 Run 을 append 한다.
- Pass/Fail: **PASS(코드/유닛 범위)** — 라이브 실측은 배포 후 잔여. Runner: AI.

### 20260728T1911-model-pick-early-cid 조기 cid 전환 시 모델 선택 유실(sonnet→haiku 조용한 강등) 수정 (Major §12.3, 2026-07-28, feature-0003 web/UI 단독) — **Environment: Windows-browser ([새 대화 → 모델 선택기에서 sonnet → 파일 첨부 업로드 → 전송] 은 실 브라우저 파일선택+업로드 왕복과 선택기 DOM 이 필요해 headless 대체 불가 — de-risk=`node --check` PASS + `verify_model_persist.mjs` 49/49(승계·오귀속 차단·미선택 보존·무음 감지·구조 계약) + 서버측 pytest 57건 rc=0 + 인접 JS 스위트 baseline 동일, 정적 자산 web 이미지 baked → 라이브 PB-0008 배포 후 잔여, visual_verification_scope: always)**
- 증상(사용자 보고 2026-07-28): "sonnet 모델로 요청한 **즉시** haiku 모델로 폴백" — 모델 선택기에서 sonnet 을 골라 요청했는데 나머지 작업이 haiku 로 진행됨. 대상 대화 `쿼리 리뷰 : 게시글 기능` · `쿼리 리뷰 : 홈페이지 공지 기능 추가`(product 117).
- 근본원인: LLM 라우팅 폴백이 **아니다**. 모델 선택은 `state.activeConversationId` 로 귀속되어 새 대화(pending)에서는 `_modelPickedForConvId=""` 인데, **첨부 업로드가 early-cid 를 발급**해 `activeConversationId` 를 실 cid 로 바꾸면서 귀속을 승계하지 않아 `_shouldSendModelField()` 가 false → `askBody.model` 누락 → 서버가 `API_DEFAULT_MODEL`(haiku) 로 채움(`model_explicit=False` 라 KV 저장도 skip). 화면은 sonnet 을 계속 표시 → 조용한 강등. 첫 전송 후 hydration 이 저장값 부재로 `selectedModel=null` 을 넣어 선택기까지 haiku 로 되돌아간다("즉시 폴백"이 화면에서 보인 기전).
- 수정: `_adoptComposerModelPickToConv()`(early-cid 전환 2곳에서 귀속 승계, 미선택 `null`·타 대화 귀속은 비대상) + `_modelSelectionSilentlyDropped()`(표시-집행 불일치 감지 → `showToast` 표면화 + 진단 로그).
- 기대: [새 대화 → sonnet 선택 → 첨부 업로드 → 전송] 이 **sonnet 으로 실행**되고(`llm_usage.model=claude-sonnet-4`), 선택기 표시도 sonnet 을 유지한다. 대조 — 모델을 고르지 않으면 여전히 haiku 로 시작한다("'+ 새 대화'는 haiku" 계약 불변).
- **유닛 검증 — PASS**: `node tests/verify_model_persist.mjs` **49/49**(신규 E1~E6 승계·오귀속 차단·미선택 보존 / W1~W4 무음 강등 감지·오탐 없음 / S9 전환 지점 수 == 승계 호출 수 · S10 승계가 sentinel 초기화보다 앞 · S11 미동봉 시 표면화). 서버측 `test_model_persist.py`·`test_ai_capabilities.py`·`test_model_access_rbac.py`·`test_message_editing_reanswer_model.py` 57건 rc=0. `node --check app.js` PASS. 인접 JS 스위트 실패 6건은 main baseline 과 동일(pre-existing).
- **PB-0008 Windows-browser 라이브 실측 — DEFERRED(배포 후)**: 정적 자산(app.js)이 web 이미지에 baked 되므로 배포 후 실 Windows Chrome via `bin/win-browser.py` relay + 로그인 세션에서 위 '기대' 를 실측하고 본 케이스에 Run 기록 append. **확인 정본은 화면이 아니라 `agent_runtime.llm_usage.model` + `kv model:<acct>`** (미동봉이면 KV 행이 생기지 않는 것이 지문).
- Pass/Fail: **PASS(코드/유닛 범위)** — 라이브 실측은 배포 후 잔여. Runner: AI.

### 20260721T1758-realtime-progress-propagation assistant 진행상황/답변 실시간 전파 — 유휴 관찰자 run-감지 폴러 (Major §12.3, 2026-07-21, feature-0003 web/UI 단독) — **Environment: Windows-browser (유휴 대화에서 다른 액터가 시작한 run 을 재로드 없이 실시간 표시하는지는 실 브라우저 폴링 타이밍+DOM 렌더가 필요 — jsdom 은 폴링/타이머 정본 아님; de-risk=`node --check` PASS + 유닛 `verify_run_detect_poll.mjs` 23/23 + feature-0003 pytest RC=0, visual_verification_scope: always)**
- 증상: 타 계정 대화 모니터링(또는 그룹 대화) 중, 대화를 열어둔 관찰자에게 다른 사용자가 시작한 run 의 assistant 말풍선이 실시간으로 안 뜸(다른 대화 갔다 와야 표시).
- 근본원인/수정: 유휴 대화에 배경 폴링 부재 → app.js 에 유휴 run-감지 폴러 추가(활성 run 추적 없을 때 `/api/progress` ~4s/숨김 15s 폴링 → 서버 run_id 변화 시 `loadHistory` 위임). 상세 REPORT/TASK 참조.
- 기대: 유휴로 보고 있는 대화에서 다른 액터가 요청→run 시작 시, **재로드/전환 없이** assistant "처리 중" 말풍선이 자동 등장하고 완료 시 답변까지 반영.
- **유닛 검증 — PASS**: `node tests/verify_run_detect_poll.mjs` 23/23(감지 결정 매트릭스: 무장 baseline·새 processing/terminal run 재로드·동일 run 무재로드·활성 추적/pending dormant + 정적 배선 4건). `node --check app.js` PASS. feature-0003 pytest RC=0(프론트 전용, 무회귀).
- **PB-0008 Windows-browser 라이브 실측 — PASS (Environment: Windows-browser, 2026-07-21, 실 Windows Chrome/150 via `bin/win-browser.py` relay @ 172.26.144.1:9223, `https://localhost/` 로그인 세션 bootstrap_admin)**: 수정 app.js 를 web-a/b docker cp 주입(index stamp bump 로 캐시 무효화) → 유휴 대화(`20260721075408-f534747e`)에서 detector 가 `/api/progress?conversation_id=...`(client_run_id 없이) 폴링 확인 → `set_run_status(cid,"processing","qa-realtime-inject-01")` 로 새 run 주입 → **재로드/전환 없이** assistant "처리 중" 말풍선 실시간 등장(`#pendingAssistantBubble` 존재+elapsed 타이머, 스크린샷 증적). net 로그로 detector `/api/progress`(무 client_run_id) → `/api/history` 재로드 위임 → `/api/progress?client_run_id=qa-realtime-inject-01` active poll 전환 시퀀스 확인. 검증 후 라이브 서비스 배포본 원복(주입 app.js/stamp/KV 되돌림). 배포(main 병합+web 재빌드) 후 POST-DEPLOY 재확인은 배포 시점 잔여.
- Pass/Fail: **PASS** (유닛 23/23 · pytest RC=0 · 실 Windows 브라우저 실시간 감지+렌더 실측+스크린샷). Runner: AI.

### TASK-20260715T110000-attach-new-label-symmetry staged-flush 첨부 new_attachment_ids 라벨 대칭 (Minor §12.3, 2026-07-15, deferred ②-frontend) — **Environment: Windows-browser (신규 대화 staged 첨부 업로드→전송→assistant 가 ★신규로 인지하는 전 과정은 실 브라우저 파일선택+업로드+ask 왕복이 필요해 headless 대체 불가 — de-risk=`node --check` PASS + 로직 대칭 분석(attachment_ids/new_attachment_ids union 대칭) + §18.8 적대 패널(스코프/IDOR REFUTED, 라벨-only) + 서버측 new_attachment_ids 소비 추적(★/◆ 라벨+version-diff 게이트 전용), 정적 자산 web 이미지 baked → 라이브 PB-0008 배포 후 잔여, visual_verification_scope: always)**
- 증상(실데이터 감사, 대화 20260615061233-140adf6f): 신규 대화에서 파일을 첨부(staged)하고 전송하면, assistant 가 "현재 첨부된 파일 목록에는 여전히 모두 이전 세션 파일(◆세션)만 있습니다 / 새 파일이 반영 안 됨"이라 오판. 근본: staged→flush 업로드된 id 가 `attachment_ids` 에만 union 되고 `new_attachment_ids` 엔 누락(스냅샷 시점 status="staged"≠"ready") → 프롬프트에서 ◆세션 오라벨.
- 수정: `app.js` lazy-create+staged 블록에서 `uploadedIds` 를 `new_attachment_ids` 에도 union(attachment_ids 대칭).
- 기대: 신규 대화에서 파일 첨부→전송 시 assistant 가 그 파일을 **이번 턴 신규(★신규)**로 인지하고 정상 리뷰(“이전 세션 파일만/반영 안 됨” 미발생).
- **PB-0008 Windows-browser 라이브 실측 — DEFERRED(배포 후)**: 정적 자산(app.js)이 web 이미지에 baked 되므로 배포 후 실 Windows Chrome via `bin/win-browser.py` relay + 로그인 세션에서 [신규 대화 → 파일 첨부 → "이 파일 리뷰" 전송 → assistant 응답이 파일을 신규로 취급] 를 실측하고 본 케이스에 Run 기록 append. de-risk(node --check + 로직 대칭 + 적대 패널 + 서버 소비 추적)로 코드 정합은 확증.

### TASK-20260710-graph-edge-midpan 그래프 뷰 관계선(엣지) 위 중간버튼 드래그 카메라 팬 무반응 수정 (Minor §12.3, 2026-07-10, feature-0016 cross-cut) — **Environment: Windows-browser (실 중간버튼 드래그는 real-mouse 입력 + 인증 게이트 그래프 뷰 렌더가 필요해 headless 대체 불가 — de-risk=근본원인 번들 실증(스타일 병합순서·drag-element enableElements) + node --check + headless g6build 125건 회귀 0, 정적 자산 web 이미지 baked → 라이브 PB-0008 배포 후 잔여, visual_verification_scope: always)**
- 증상(사용자 리포트): 그래프 뷰에서 마우스 **중간버튼 드래그로 카메라 이동** 시, 드래그를 **관계선(엣지) 위**에서 시작하면 팬이 작동하지 않음. 빈 캔버스·노드 위 시작은 정상.
- 근본원인(vendor `g6.min.js` 실증): 카메라 팬은 `drag-canvas` behavior 가 담당하고, 이 behavior 는 `@antv/g-plugin-dragndrop` 이 합성하는 global `dragstart` 에서 발동한다. dragndrop 은 pointerdown 대상의 `closest("[draggable=true]")` 를 드래그 소스로 삼는데, **노드/콤보는 `draggable` 기본값 true 이지만 엣지 기본 스타일에는 `draggable` 이 없다**(bundle `Nw`/`Wb` defaultStyleProps=draggable:!0, 엣지 base 는 부재). 따라서 관계선 위 pointerdown 은 소스 해소가 null → `dragstart` 미합성 → drag-canvas 미발동.
- 수정: G6 그래프 config 에 `edge: { style: { draggable: true } }` 추가(`admin.js` `_metaGraphEnsure` baseCfg). 캐시버스터 `admin.js?v=20260710-graph-edge-midpan`.
- 무회귀 근거(엣지 이동 안 함): drag-element behavior 는 `enableElements=["node","combo"]` 로 `node:dragstart`·`combo:dragstart` 만 바인딩(bundle `uE`) → 엣지는 드래그 소스여도 **위치 이동 대상이 아님**. 좌드래그 관계선은 `_metaCanvasDragEnable` 이 `targetType!=="canvas"` 로 false → 팬 안 됨(기존 동작 보존). 클릭/우클릭 메뉴는 dragndrop 10px 임계 미만이라 미영향.
- 스타일 병합 실증: `getElementComputedStyle` 병합 순서 `Object.assign({}, theme, palette, datum.style, defaultStyle(=options.edge.style), themeState, state)` — `options.edge.style` 가 datum.style **뒤**라 `draggable:true` 가 항상 반영되며, 어떤 엣지도 per-datum `draggable` 을 세팅하지 않아 stroke/lineWidth 등 per-edge 스타일은 불변. `draggable` 은 root-container 프롭 목록에 있어 엣지 루트 그룹에 적용 → `closest` 가 관계선 hit 에서 이를 찾음.
- **라이브 PB-0008 실측 — DEFERRED(배포 후)**: 배포(main 병합 후 web 재빌드) 이후 실 Windows Chrome(win-browser.py relay)에서 그래프 뷰 진입 → **관계선 위에서 중간버튼 누른 채 드래그 → 카메라가 함께 이동(팬)** 확인. 대조: 관계선 좌클릭 드래그는 팬 안 됨·관계선 우클릭 메뉴 정상·관계선 클릭(이동 없음) 정상. 배포 후 §4 Run 에 결과 append.
- Pass/Fail: **PASS**(근본원인 번들 실증·node --check·headless g6build 125건 회귀 0). 라이브 real-mouse 시각검증은 배포 후 잔여. Runner: AI.

### reasoning-budget-per-model 모델별 추론 예산 상한 확대 + 모델→추론강도 accordion + [추론↔본문] 비율 슬라이더 (Major §12.3, 2026-07-09, shared + feature-0002 + feature-0003 cross-cut) — **Environment: Windows-browser (관리 콘솔 `시스템 > 설정 > 모델별 추론 예산` 의 모델 카드 접기/펼치기·비율 슬라이더 드래그·추론/본문 분할바·총 출력 변경 시 슬라이더 상한 재계산은 실 브라우저 렌더/상호작용 — de-risk=node --check + 컨테이너 make test(feature 관련 전건 PASS) + serialize 계약 검증, 정적 자산 web 이미지 baked → 라이브 PB-0008 배포 후 잔여, visual_verification_scope: always)**
- 대상: 관리 콘솔 `시스템 > 설정 > 모델별 추론 예산` 패널. 변경: `shared/model_catalog.py`(모델별 agent max_tokens native 상한 Sonnet 128K/Haiku 64K + `model_native_max_output`)·`shared/runtime_settings.py`(신규 `agent_max_output` group + per-model `reasoning_budget:{model}:{level}` 스킴 + `agent_max_output`/`reasoning_budget_override(model,level)` reader + serialize `agent_max_outputs`)·`feature-0002 agent_core.py`(`_call_llm` 모델별 token_limit + reasoning override(model))·`feature-0003 static/{admin.js,admin.html,styles.css,release-notes-data.js}`.
- **구조·구문**: `py_compile`(model_catalog·runtime_settings·agent_core) PASS · `node --check`(admin.js·release-notes-data.js) PASS · ruff clean.
- **단위(agent 이미지 격리, DB 없이)**: 컨테이너 `make test` feature 관련 **전건 PASS**. `test_runtime_settings.py` 43건(신규 `agent_max_output` 등록·override·native clamp, per-model reasoning override 격리, backward-compat 구 키 무시, serialize row model+level) · `test_reasoning_effort.py` 17건(per-model 예산 주입, 총 출력×예산 모델별 분리, budget clamp=총−1024) · `test_prompt_gen_max_tokens.py` 5건(non-agent task 무회귀). API `test_runtime_settings_api.py` 신규 assertion(agent_max_outputs 노출·native 초과 400·구 16000 초과값 검증 통과)은 `AGENT_TIMEOUT_SEC` env unset 시 PASS 확인.
- **serialize 계약 검증**: `serialize_registry({})` → `agent_max_outputs`(sonnet max=128000/default=40000, haiku max=64000/default=24000) + reasoning rows max=native−1024(sonnet 126976/haiku 62976) + '매우 높음' default 16000·maximum 126976(상향 여지 확보 — 사용자 요구 핵심) 실측.
- **make test 잔여 3건은 환경 아티팩트(무회귀 확인)**: `test_missing_snapshot_is_fail_open`·`test_get_returns_registry` 는 컨테이너 env `AGENT_TIMEOUT_SEC=300`(복사한 `.env`) 로 인한 기존 timeout `==60` 단정 실패 — env unset 시 둘 다 PASS(내 신규 assertion 통과 확인). `test_schema_analysis_fail_loud` 는 `--no-deps` DB(`postgres-replica`) 미기동 — 셋 다 본 변경과 무관.
- **라이브 PB-0008 실측 — DEFERRED(배포 후)**: 정적 자산이 web 이미지에 baked 라 실 시각검증은 배포(main 병합 후 web 재빌드) 이후 가능. 확인 항목 → ① 모델 카드 접기/펼치기(permission-group details) ② 총 출력 입력 상향(Sonnet 128000 까지) ③ 추론강도별 비율 슬라이더 드래그 → 숫자·분할바(추론/본문) 실시간 갱신 ④ 총 출력 변경 시 슬라이더 상한/본문 파생 재계산 ⑤ 커밋바(모두 적용) 예약→저장→재조회 반영 ⑥ '매우 높음' 을 16000 초과로 저장 가능. 배포 후 §4 Run 에 결과 append.
- Pass/Fail: **PASS**(구문·단위 전건·serialize 계약·무회귀 확인). 라이브 시각검증은 배포 후 잔여. Runner: AI.

### TASK-20260703-graphux6-panelbottom-responsive-obs 상세 패널 하단 이동 + 그래프 반응형 높이 + 운영현황 분석 대상 관측 (Major §12.3, 2026-07-03, feature-0016 cross-cut) — **Environment: Windows-browser (①패널 배치·②세로 반응형 레이아웃·③최근활동 대상 표시는 실 브라우저 렌더/뷰포트 거동 — de-risk=컨테이너 make test 전건 + 적대리뷰 + 라이브 PB-0008 배포 후 잔여, visual_verification_scope: always)**
- 대상: 관리콘솔 > 메타데이터 > 그래프 뷰(패널 하단·반응형 높이) + AI 운영 현황 > 최근 활동(분석 대상). 변경: `static/admin.html`·`static/styles.css`·`static/admin.js`·`routers/ai_ops.py` + feature-0002 `modules/llm.py`·`scripts/agent_runtime_schema.sql`·`alembic 0032_llm_usage_target` + `tests/test_ai_ops.py`.
- **구조·구문**: `py_compile` (ai_ops.py·llm.py·0032) PASS · `node --check admin.js` PASS · alembic 단일 head=0032.
- **단위(agent 이미지 격리, DB 없이 monkeypatch/fake)**: 컨테이너 `make test` **전건 PASS**(feature-0002+0003, ruff clean). `test_ai_ops.py` **16/16** — target SELECT/item 통과(짝수=`public.tbl_*` 대상, 홀수 None) + 신규 컬럼부재 폴백 `test_query_activity_target_column_absent_fallback`(rollback→base 재조회→target=None) + 기존 회귀. `test_llm_usage_record.py` **7/7** — target 을 total_tokens·latency_ms 사이 삽입해 param 위치(pt=5·lat=마지막) 보존.
- **§18.8 적대 패널(subagent 2라운드)**: **VERDICT PASS-WITH-FIXES** — round-1(5축) BLOCKING 0·MEDIUM 1(M1 wide-short 빈 캔버스)·NIT 4, round-2(CSS 집중 6축) BLOCKING 0·MEDIUM 1(440 floor 과잉→노트북 스크롤·헤더 아웃). **모든 지적 수정**: 캔버스 min-height:200(빈캔버스 방어)·그래프 하한 제거(노트북 스크롤 회피)·전너비 :has() pane 스크롤(잘림 방지)·이중 :not 가드·test mock target=None·INSERT 폴백 테스트. 잔여 NIT(≈<560px viewport 헤더 스크롤, :has() 구형 미지원) 수용. REVIEW.md REV-20260703T105541-graphux6-panelbottom-responsive-obs 참조.
- **PB-0008 Windows-browser 라이브 실측 — PASS (Environment: Windows-browser, 2026-07-03, 배포 9e1156d6 후, 실 Windows Chrome/149 via bin/win-browser.py relay @ 172.26.144.1:9223, https://localhost/admin 로그인 세션)**:
  - **(①) 패널 하단 — PASS**: 메타데이터 > 그래프 뷰 진입 → `aside#metadataGraphDetail` 자식 순서 = `[metadataGraphDetailBody, admin-meta-graph-rolelegend, metadataGraphProgress]`, `progressIsLastChild=true`. AI 능동 분석 진행 패널이 상세 패널 **최하단**(역할범례 다음 마지막 자식)에 위치 — 노드 상세를 밀지 않음. §37 role-legend-bottom 과 통합 정합 확인.
  - **(②) 반응형 높이 — PASS**: viewport 836px 에서 `.admin-meta-graph` `flex-grow:1`·`min-height:0`, 캔버스 `min-height:200px`, **캔버스 height=415px 로 채워지고 canvas.bottom(753)=pane.bottom(753) → 잘림 0**(고정 clamp 아님), pane `overflow-y:auto` 활성, 정상 높이에선 스크롤 미발생(스퓨리어스 없음). 가용높이 제약 시뮬(그래프 320px) → 캔버스 415→**200px 축소**(반응성) + 200 floor 유지(빈 화면 아님) + 초과분 스크롤(잘림 방지). 창 resizeTo 는 브라우저 차단이라 컨테이너-제약 시뮬로 검증.
  - **(③) 최근 활동 대상 표시 — PASS(실데이터)**: AI 운영 현황 > 최근 활동 30행 중 '테이블 분석' 행들이 대상 표시 — `dbo.ET_EventXmas`·`dbo.DT_WorldInfo`·`web_statistics.DayExp_20260627` 등 `schema.table`(`.aiops-act-target` 인라인). '계정 분석'은 target 공백(account_insight PII 제외 정합). 재빌드된 insight-worker(9e1156d6)가 신규 분석을 target 과 함께 기록 확인. (그래프 '노드 분석'은 온디맨드 트리거라 본 배치엔 없으나 동일 `_record_llm_usage(target=)` 경로.)
  - **마이그레이션**: 배포 전 live `alembic_version=0031_node_analysis_role` → `make migrate`(agent 재빌드 후 0032 baking) → **live `alembic_version=0032_llm_usage_target` 확인**(stale image 회피). deploy-web soak 90s 통과. insight-worker `make insight-up` 재빌드로 GIT_COMMIT=9e1156d6 반영.

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
- 2026-07-13 (TASK-20260713T053423-attach-user-version — 사용자 재업로드 첨부 버전 관리(해시 대조 → 버전 체인), **Major §12.3 + cross-cut feature-0002** — **PB-0008 Windows-browser PASS(POST-DEPLOY 라이브 실측)**):
  - **Environment: pytest(agent 이미지 등가 — 기존 web 이미지 `mysql-ai-web:current` 에 worktree 마운트 + PYTHONPATH, `PYTHONDONTWRITEBYTECODE=1`)** — 첨부 버전 관련 **31 PASS**: `test_attachment_versioning.py`(P1~R1 기존 11 + **U1~U5 신규 6** — U1 diff 계산·U2 truncate·U3/U4 `_find_latest_same_name_attachment` 매치/결손가드·U5 업로드 핸들러 정적)·신규 `test_attachment_user_version_context.py`(**5** — 🔄v{n} 표식·`## FILE UPDATES` diff 주입·datamark·truncate 표시·v1 원본 무회귀)·`test_attachment_idor.py`·`test_attachment_line_numbers.py`. **전체 스위트 EXIT=0**(feature-0002+0003 tests, 실패·에러 0·일부 skip) — 회귀 0. 기존 9-tuple 컨텍스트 테스트(`test_attachment_idor.test_attachment_listing_names_file_before_id`)는 SELECT 컬럼 append 후에도 `len(row)>10` 가드로 IndexError 없이 통과.
  - **정적 PASS**: `py_compile`(conversations.py·_conv_store.py·app.py·agent_core.py) · `node --check static/app.js` OK.
  - **Environment: Windows-browser (실 Windows Chrome/150 via `bin/win-browser.py` relay, https://localhost/, bootstrap_admin 로그인) — POST-DEPLOY 라이브 PASS** (배포 7f1ed748: web-a/web-b + ask-worker 재빌드, 코드 baked 확인). **라이브 e2e(eval 구동)**:
    - **AC-AUV-1 (재업로드 버전업)**: 대화 생성 후 `report.sql` v1("SELECT 1 FROM dual;") 업로드 → id=490·version=1·root=490. 내용 바꿔("SELECT 2 FROM dual; -- changed") 재업로드 → **id=491·version=2·root=490**(같은 체인 편입).
    - **AC-AUV-2 (동일=멱등)**: v2 와 동일 내용 재업로드 → **id=491(동일)·reused_existing_version=true**(새 row·객체 미생성).
    - **AC-AUV-3/5 (체인 정합)**: `GET /api/attachments/491/versions` → root=490·2개 [v1 user superseded / v2 user 최신]. `GET /api/conversations/{cid}/attachments` → 최신 v2 만 노출·version_count=2.
    - **AC-AUV-4 (assistant 인지 — 라이브 LLM 왕복)**: v2 를 new_attachment_ids 로 첨부 후 "직전 버전 대비 변경점만" 질문 → assistant 가 `변경점 (v1 → v2)` + ```diff``` 블록(`- SELECT 1 FROM dual;` / `+ SELECT 2 FROM dual;` / `+ -- changed`) + "1번 줄 SELECT 1→2, 2번 줄 -- changed 주석 추가" 로 **정확히 인지·설명**(dur ~35s). new_attachment_ids 미포함 턴(재업로드 아닌 이후 턴)엔 "v1 내용 없어 비교 불가" 로 **정직 응답(환각 0)** — is_new 게이트 설계 정합.
    - **AC-AUV-6 (UI)**: 첨부 목록 패널에 `report.sql`·`v2`·"버전" 렌더 확인(DOM), assistant 말풍선 diff 색상 렌더(웹 UI enhanceDiffBlocks). pageerror 0.
    - Evidence: `artifacts/shared/win-browser-shots-attach-user-version/01_version_badge_and_assistant_diff.png` (assistant 변경점 diff 라이브 렌더).
  - **Pass/Fail: PASS (단위 32 + 전체 EXIT=0 + CI test SUCCESS + POST-DEPLOY 라이브 PB-0008 AC-AUV-1~6)**.
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

### Run (2026-07-03) — graph-rel-layout: 관계 기반 배치(엣지 교차 최소화) (Minor §12.3 — 코드 거주 feature-0003 / 문서 정본 feature-0016-metadata-graph TASK §38, ADR-012)
- **정적·격리 검증 PASS**: `node --check admin.js` PASS · Node 격리 로직 **10/10 PASS**(관계0 회귀·스키마 seriation·컴포넌트 BFS 군집·나란한 클러스터 상호교차 해소·결정론·벌크 교차 12% 감소·펼침-비의존·collapse REFERENCES 보존·expand focus 폴백) · 파라미터 벤치(시드 3 × 랜덤/허브 토폴로지: 2D 세그먼트 교차 12~30% 감소, SPAN=1 채택). 상세: `unit/feature-0016-metadata-graph/docs/TEST.md` graph-rel-layout 절.
- **§18.8**: 적대 패널 4축(알고리즘/G6통합/UX/성능) + 발견별 2-refuter — 확정 4건 전량 수정(collapse REFERENCES 보존 등). 결과 정본 feature-0016 REVIEW.md REV-20260703T014113-…-graph-rel-layout [SUBAGENT: PASS-WITH-FIXES].
- **Environment: Windows-browser (PB-0008)** — **배포 후 라이브 실측 예정(커밋 시점 미수행 사유 명시, 카고컬트 방지)**: 본 변경은 web 이미지 baked 정적 자산(admin.js/admin.html)이고 `deploy-web.sh` 는 origin/main HEAD 만 배포 — **머지 전 라이브 반영 불가**. 또한 배치 개선은 라이브 관계 데이터 규모에서만 육안 판별 가능. cycle-finalize(main 병합) → web-a/web-b 재배포(cache-buster `admin.js?v=20260703-graph-rel-layout` 신 JS 강제 로드) → 실 Windows 브라우저(win-browser relay)로 그래프 뷰 진입 → **① 관계 많은 스키마 카드끼리 인접 배치(seriation)** **② 펼친 스키마 안에서 관계로 연결된 테이블끼리 군집** **③ 관계선 교차가 자연정렬 대비 감소** **④ 컬럼 접기(−) 후에도 배치·관계선 유지(collapse REFERENCES 보존)** 실측하고 본 Run 에 POST-DEPLOY 갱신을 기록한다.
- **Pass/Fail: 정적·격리·§18.8 PASS · 라이브 PB-0008 = POST-DEPLOY PASS(2026-07-03)** — 배포 `5f439788` 후 실 Windows Chrome 실측: 관계쌍 평균 배치 거리 32.5→3.2(90% 감소)·군집 육안·collapse REFERENCES 보존·이웃확장/검색 pageerror 0. 상세 feature-0016 TEST.md POST-DEPLOY Run.

### Run (2026-07-03) — role-legend-bottom: 역할 범례를 상세 패널 하단으로 이동 + 확장 시 밀림/뒤틀림 해소 (Minor §12.3 — frontend-only 표현 전용, 코드 거주 feature-0003 / 문서 정본 feature-0016-metadata-graph TASK §37)
- **정적·구조 검증 PASS**: 표현 전용(admin.html/styles.css, JS·데이터·API 무변경). 범례를 aside 첫 자식 → 마지막 자식(detailBody 뒤)으로 이동, 여전히 detailBody 형제라 innerHTML 교체(detailBody/progress 만)에 wipe 없음.
- **headless playwright 렌더 격리 실증 PASS** (실제 `.admin-meta-graph-detail`/`.admin-meta-graph-rolelegend` 규칙 복제, chromium-headless): **(A) 빈 상세(짧음)** — 범례 `pinnedNearBottom:true`(legBottom 517 vs asideBottom 532, 위 여백 262px) = **패널 바닥 고정**. **(B) 긴 상세 30행** — 노드 상세 `firstNodeH:32`(온전·미압축), `dbH==dbScrollH(983)`(detailBody 잘림 없음), aside `scrollH 1138 > clientH 489 canScroll:true`(컨테이너 스크롤) → **상세 밀림/뒤틀림 없음**. 스크린샷 `scratchpad/legend-bottom-shot.png`(A=범례 바닥·B=상세 온전+스크롤) 육안 확인.
- **§18.8**: 적대 패널 [SUBAGENT] (detailBody wipe 회귀·flex 부작용·margin-top:auto+overflow·detail-collapsed 토글·반응형·잔여/버스터·접근성) — 결과 정본 feature-0016 REVIEW.md REV-20260703-role-legend-bottom.
- **Environment: Windows-browser (PB-0008)** — **배포 후 라이브 실측 예정(커밋 시점 미수행 사유 명시, 카고컬트 방지)**: web 이미지 baked 정적 자산(admin.html/styles.css)이고 `deploy-web.sh` 는 origin/main HEAD 만 배포 — 머지 전 라이브 반영 불가. cycle-finalize(main 병합) → web-a/web-b 재배포(cache-buster `styles.css?v=20260703-role-legend-bottom` 신 CSS 강제 로드) → 실 Windows 브라우저(win-browser relay)로 그래프 뷰 진입 → **① 역할 범례가 상세 패널 하단에 위치** **② 범례 접힘/펼침 시 위의 노드 상세가 밀리지 않음(뒤틀림 없음)** **③ 노드 클릭 후에도 범례 유지** 실측하고 본 Run 에 POST-DEPLOY 갱신을 기록한다. (참고: role-legend-panel 시각검증은 로컬 자산검증까지만 되고 실 Windows 그래프뷰는 TrustedHostMiddleware·인증세션·Windows→WSL 라우팅 3중 벽으로 무인 미완 — 본 cycle 도 동일 제약 시 사용자 육안 위임.)
- **Pass/Fail: 정적·구조·headless 렌더·§18.8 PASS · 라이브 = 배포 후 PB-0008 실측 대기**. CHECK#13 충족(웹 자산 변경에 이번 cycle Windows-browser Run·미수행 사유·배포 후 수행 계획 기록).

### Run (2026-07-03) — cluster-role-prefix: 클러스터 상세 테이블 목록 역할 접두사 + 행 클릭 노드 선택 + 범례 hover 툴팁 (Minor §12.3 — frontend, 코드 거주 feature-0003 / 문서 정본 feature-0016-metadata-graph TASK §39)
- **정적·구조 검증 PASS**: `node --check admin.js` PASS. 신규 심볼(`_metaRoleChipHTML`·`_metaRoleLegendTips`·`amgr-*`) 정합. 클릭은 기존 `_metaGraphShowDetail`(select 하이라이트+상세) 재사용(선택 semantics 동일). 범례 툴팁은 `_META_ROLE.desc` 단일 소스.
- **headless playwright 렌더 격리 실증 PASS** (실제 `.amgr-*` 규칙 복제, chromium-headless): 분석/미분석 혼합 5행 → 전 `<code>` left=45px 동일(`allCodesAligned:true` — 미분석도 18px 빈 슬롯 유지로 **정렬 뒤틀림 없음**), 칩 폭 전부 18px(`allChipsSameWidth`), 전 행 `<button>`(`isButtons:true`). 스크린샷 `scratchpad/cluster-prefix-shot.png`(색상 칩 접두사 + 미분석 빈 슬롯 정렬) 육안 확인.
- **§18.8**: 적대 패널 [SUBAGENT] (XSS/속성안전·클릭 바인딩·select semantics·범례 tips 정합·칩 헬퍼·CSS·회귀 7축) — 결과 정본 feature-0016 REVIEW.md REV-20260703-cluster-role-prefix.
- **Environment: Windows-browser (PB-0008)** — **배포 후 라이브 실측 예정(커밋 시점 미수행 사유 명시, 카고컬트 방지)**: web 이미지 baked 정적 자산(admin.js/admin.html/styles.css)이고 `deploy-web.sh` 는 origin/main HEAD 만 배포 — 머지 전 라이브 반영 불가. cycle-finalize(main 병합) → web-a/web-b 재배포(cache-buster `?v=20260703-cluster-role-prefix`) → 실 Windows 브라우저(win-browser relay)로 그래프 뷰 진입 → **① 스키마 클러스터 상세 테이블 목록에 분석 완료 테이블 역할 칩 접두사·미분석 정렬 유지** **② 목록 행 클릭 → 해당 노드 선택(하이라이트·상세)** **③ 역할 범례 hover → desc 툴팁** 실측하고 본 Run 에 POST-DEPLOY 갱신을 기록한다. (참고: 실 Windows 그래프뷰 무인 접근은 TrustedHostMiddleware·인증세션·Windows→WSL 라우팅 3중 벽 — 제약 시 사용자 육안 위임.)
- **Pass/Fail: 정적·구조·headless 렌더·§18.8 PASS · 라이브 = 배포 후 PB-0008 실측 대기**. CHECK#13 충족(웹 자산 변경에 이번 cycle Windows-browser Run·미수행 사유·배포 후 수행 계획 기록).

### Run (2026-07-03) — graph-drag: 중간버튼 카메라 팬 + 테이블 노드 종속 UI 동반 드래그 (Minor §12.3 — 코드 거주 feature-0003 / 문서 정본 feature-0016-metadata-graph TASK §41)
- **정적·문법 검증 PASS**: `node --check admin.js` PASS. `behaviors` object-form 전환(drag-canvas/drag-element `enable` 오버라이드) + `node:dragstart/drag/dragend` 핸들러 3함수 + `_metaG6Build` `tableDeps` 맵. 순수 프론트 상호작용 — 데이터 API·스키마·RBAC·마커 인코딩·기존 zoom/click/contextmenu·미니맵 무변경.
- **§18.8**: 적대 리뷰 subagent [SUBAGENT: PASS] — 회귀(좌클릭 팬/노드이동·휠줌·클릭·우클릭메뉴)·엣지(접힌 테이블·term/카드·X:·컬럼 자체 드래그·드래그 중 재구성·stale id·우클릭 드래그)·G6 API(translateElementTo multi-key/좌표계 center 정합·G6 v5.1.1 번들 실측)·성능 4축 BLOCKING 0. 결과 정본 feature-0016 REVIEW.md REV-20260703T021144-graph-drag.
- **Environment: Windows-browser (PB-0008) — 라이브 실측 PASS (머지 전 완료)**: 실 Windows Chrome/149(win-browser relay endpoint 172.26.144.1:9223)에서 admin 콘솔(bootstrap_admin) → 메타데이터 > 그래프 뷰 → 데이터소스 mysql-gz-dev → 스키마 gunzgame 펼침 → 테이블 account 컬럼 확장(종속 5 = 접기 X:ctl + 컬럼 AID/PGradeID/UGradeID/UserID). 합성 PointerEvent(movementX/Y 포함, G 인터랙티브 canvas + document 라우팅)로 실측:
  - **Test A (중간버튼 팬)**: account 노드 위에서 중간버튼(button=1/buttons=4) 드래그 → **노드 월드좌표 델타 [0,0](이동 안 함) + 노드 화면좌표 델타 [-78,48]·[90,54](카메라 팬)** = 중간버튼은 카메라 드래그, 객체 상호작용 아님. ✅
  - **Test B (종속 동반)**: account 노드 좌클릭 드래그 [191.35,-131.55] → **종속 5개(X:ctl + 컬럼4) 전부 동일 델타 [191.35,-131.55] 이동(오차 0)** = 하위 종속 UI 동반 이동. ✅
  - 라이브 반영: worktree admin.js 를 web-a/web-b `/app/web/static/admin.js` 로 docker cp(머지 전 pre-verify — 배포 시 origin/main 재빌드로 정합). 그래프 렌더 정상(스크린샷 `scratchpad/graph-drag-verify.png`), 회귀 없음.
- **Pass/Fail: 정적·문법·§18.8·라이브 PB-0008 실측 전부 PASS**. CHECK#13 충족(웹 자산 변경에 이번 cycle Windows-browser Run 기록 — 라이브 PASS).
- **POST-DEPLOY (PR #571 머지 29c3a07c → `make deploy-web` soak 90s 통과) 자산검증 PASS**: WSL localhost caddy edge :443 — healthz `status:ok / git_commit=29c3a07c / mysql_ok / pg_ok / insight_heartbeat 9s`, 라이브 `admin.js?v=20260703-graph-drag` 서빙(admin.html 버스터 일치) + graph-drag 심볼 12(드래그 함수/필드) + `_metaRoleChipHTML` 2(main 병합 역할 기능 보존). 실 Windows 그래프뷰 육안은 머지 전 PB-0008 실측(Test A/B PASS)으로 갈음 — 무인 접근 3중벽(TrustedHostMiddleware·인증세션·Windows→WSL 라우팅) 제약 시 사용자 육안 위임.

### Run (2026-07-03) — graph-simgroups: 유사 속성 그룹 영역화 (Minor~Major §12.3 — 코드 거주 feature-0003 / 문서 정본 feature-0016-metadata-graph TASK §42, ADR-013)
- **정적·격리 검증 PASS**: `node --check admin.js` PASS · 실 _metaG6Build Node 구동 격리(실측 gunzgame 68 테이블·145 관계) **25/25 PASS**(family 유의미성·그룹 무결성·배경박스 무겹침·칩 1-박스 포함·칩/펼침 무겹침·결정론·펼침-불변·평면 폴백·엣지 조립 보존·빌드 7.5ms + §18.8 수정 회귀방지 t10 view-norm·t11 무연쇄 attach·t12 GB/GH 클릭 위임). 상세: `unit/feature-0016-metadata-graph/docs/TEST.md` graph-simgroups 절.
- **§18.8**: 적대 패널 4축 + 2-refuter(패널이 Fable 5 한도로 refuter 조기종료 → Opus 전환 후 직접 코드 판정). 확정·수정 4건(GB/GH 데드존·2차 attach 연쇄·view norm·aria-hidden). 결과 정본 feature-0016 REVIEW.md REV-20260703T043659-…-graph-simgroups [SUBAGENT: PASS-WITH-FIXES].
- **Environment: Windows-browser (PB-0008)** — **배포 후 라이브 실측 예정(커밋 시점 미수행 사유 명시, 카고컬트 방지)**: 본 변경은 web 이미지 baked 정적 자산(admin.js/admin.html/styles.css)이고 `deploy-web.sh` 는 origin/main HEAD 만 배포 — **머지 전 라이브 반영 불가**. 그룹 영역화는 라이브 관계·이름 데이터 규모에서만 육안 판별. cycle-finalize(main 병합) → web-a/web-b 재배포(cache-buster `admin.js?v=20260703-graph-simgroups`) → 실 Windows Chrome(win-browser relay)로 그래프 뷰 진입 → **① 스키마 클러스터 내부에 유사 속성 그룹 배경 박스 + 헤더 칩(스템 라벨·개수) 렌더 ② 영역 단위 가시성(균일 칩 나열 대비) ③ 그룹 박스 클릭→클러스터 상세·우클릭→스키마 메뉴(데드존 없음) ④ 컬럼 펼침/접기·테이블 드래그·검색·역할칩 회귀 0** 실측하고 본 Run 에 POST-DEPLOY 갱신 기록.
- **Pass/Fail: 정적·격리·§18.8 PASS · 라이브 PB-0008 = POST-DEPLOY PASS(2026-07-03)** — 배포 `abc78b00` 후 실 Windows Chrome 실측: 그룹 박스 22 + 헤더 칩 22 렌더·영역 가시성·GB 클릭 클러스터 상세 위임·컬럼 접기 REFERENCES 145→145·pageerror 0. 상세 feature-0016 TEST.md POST-DEPLOY Run.

### Run (2026-07-03) — aiops-stepgap: AI 운영 현황 지연 KPI 재정의(호출 전체 왕복 → 단계 간 간격) (Major §12.3 — cross-unit feature-0002 core + feature-0003 web/UI, TASK-20260703-aiops-ttft-latency)
- **단위·격리 검증 PASS**: `make test` (agent 이미지 격리, DB-free monkeypatch) **1430 passed / 2 skipped**(feature-0002+0003 전량, 회귀 0) · ruff clean · py_compile(llm.py·agent_core.py·ai_ops.py·0033) · node --check(admin.js) · migrate-lint 0033 **expand-safe**. 신규/갱신 테스트: `test_llm_usage_record.py`(step_gap 기록 맨끝 컬럼·omit→NULL·음수→NULL) · `test_call_llm_records_agent_task.py`(`_call_llm` step_gap_ms forwarding) · `test_ai_ops.py`(3단 cascade — step_gap 부재→rollback 1·target 부재→rollback 2 폴백, params 위치).
- **§18.8**: 적대 2렌즈(backend correctness · qa/semantics) × 2라운드. 1차 = **NO-SHIP BLOCKING**(최초 구현이 죽은 코드 `_openai_chat_completion_with_deadline`←`llm_plan` 계측 → 실 경로 `agent_core._call_llm` 미계측·KPI 공백 순회귀; 양 렌즈 독립 적발) → 전면 revert + 정의 A 재확정. 2차(재구현) = **양측 SHIP**(BLOCKING/MAJOR correctness 0; MAJOR observability 2건 → F2 다단계 분모 반영·F6 루프 gap 라이브 검증). 정본 REVIEW.md REV-20260703T094539-aiops-stepgap.
- **Environment: Windows-browser (PB-0008)** — **배포 후 라이브 실측 예정(커밋 시점 미수행 사유 명시, 카고컬트 방지)**: 정적 자산(admin.js/admin.html) baked + `deploy-web.sh` 는 origin/main HEAD 만 배포 — 머지 전 라이브 반영 불가. **또한 step_gap_ms 는 실 다라운드 에이전트 트래픽 + 마이그 0033 적용 후에만 채워지므로**, cycle-finalize(main 병합) → 마이그 0033 upgrade + web-a/web-b + agent/ask-worker/insight-worker 재배포(cache-buster `admin.js?v=20260703-aiops-stepgap`) → **(F6 필수 게이트)** ① 다도구(멀티 라운드) 질의 1건 구동 → `SELECT count(*), percentile_cont(0.95) WITHIN GROUP (ORDER BY step_gap_ms) FROM agent_runtime.llm_usage WHERE step_gap_ms IS NOT NULL AND created_at > now()-interval '1 hour'` 으로 step_gap_ms 행 생성·sane 값 확인 ② 실 Windows Chrome(win-browser relay)로 관리 콘솔 > AI 운영 현황 → KPI 타일이 **"단계 간 간격 p50/p95" + 서브 "다단계 요청 M/R · 간격 N건"** 실값 렌더 + 카테고리 "간격 p95" 확인. 본 Run 에 POST-DEPLOY 갱신 기록. (참고: 실 Windows 무인 접근은 TrustedHost·인증세션·Win→WSL 라우팅 벽 — 제약 시 사용자 육안 위임.)
- **Pass/Fail: 단위·격리·§18.8 PASS · 라이브 PB-0008 + F6 = POST-DEPLOY 대기**

### Run (2026-07-03) — gc-join-notice: 공유 링크 참여 시 대화 내 '참여 알림' pill (Major §12.3 — 코드 거주 feature-0003 app.js/styles.css/index.html + BE app.py/share.py, cross-unit feature-0002 / 문서 정본 feature-0009-group-conversation)
- **정적·격리·컨테이너 검증 PASS**: `node --check`(app.js — renderMessages event pill 분기) + `py_compile`(app.py·share.py·agent_core·runtime_backend) + agent 컨테이너 pytest **36 PASS**(신규 `feature-0002-agent-core/tests/test_gc_join_event_history.py` 5 — 이벤트가 LLM 히스토리에서 배제·그룹 파이프라인 미주입·name-sentinel(content 아님) 매칭·kept_users 슬롯 미잠식 / 회귀 dialect·tooluse-sanitize·group-history-merge·group-members).
- **§18.8**: 적대 패널 1렌즈(general-purpose) — **BLOCKING #1(join 이벤트가 core_messages role=user 로만 기록돼 LLM 히스토리에 `[Alice]: Alice님이 참여했습니다` user 턴으로 주입→assistant 오응답/맥락 오염) 적발 → `EVENT_MESSAGE_NAME` sentinel + `_normalize_history_rows` 배제로 수정·재검증**. 나머지 6모드 clean/NIT. 정본 feature-0009 REVIEW.md REV-20260703T182740-gc-join-notice [SUBAGENT:…].
- **Environment: Windows-browser (PB-0008)** — **배포 후 라이브 실측 예정(커밋 시점 미수행 사유 명시, 카고컬트 방지)**: (a) 본 변경은 web 이미지에 baked 되는 정적 자산(app.js/styles.css/index.html)이고 `deploy-web.sh` 는 origin/main HEAD 만 배포 — **머지 전 라이브 반영 불가**(현 서빙 `app.js?v=20260702-attach-count-scope`=수정 전). (b) 참여 알림 pill 은 **라이브 다계정 share-link join 시나리오**(계정 A 공유 → 계정 B join → A 화면에 pill + unread +1)가 있어야 발화돼 pre-deploy 워크트리 단일 렌더로 재현 불가. cycle-finalize(main 병합) → web-a/web-b 재배포(cache-buster `app.js`/`styles.css?v=20260703-gc-join-notice` 신자산 강제 로드) → 실 Windows Chrome(win-browser relay)로 **① 계정 B 가 공유 링크로 참여 시 대화에 "B님이 대화에 참여했습니다." 가운데 정렬 시스템 pill 렌더(다크모드 톤 포함) ② 기존 멤버(계정 A) 사이드바 unread +1(가입자 본인 제외) ③ 참여 직후 @assistant 호출 시 assistant 가 "참여했습니다"에 오응답하지 않음(LLM 히스토리 배제 확인) ④ anonymous 공유뷰에는 참여 알림 미노출** 실측하고 본 Run 에 POST-DEPLOY 갱신을 기록한다.
- **Pass/Fail: 정적·격리·컨테이너 pytest·§18.8(BLOCKING #1 수정 후) PASS · 라이브 PB-0008 = POST-DEPLOY 대기**.

### TASK-20260703T085511-ds-avg-latency 관리 콘솔 > 데이터소스 상세 패널 평균 연결 응답 시간 (Major §12.3, 2026-07-03, feature-0003 web/UI·API + cross-unit shared/conn_health·config) — **Environment: Windows-browser (상세 패널 DOM 렌더 — 코드/단위검증·적대리뷰 완료 + 라이브 PB-0008 배포 후 잔여, visual_verification_scope: always)**
- **단위·회귀 검증 PASS**: `test_conn_health.py` 32 PASS(신규 5: 평균 누적 (10+20+30)/3=20·window bound(maxlen 3→최근 3개만)·실패/foreground(0.0) 제외·느린성공(1745ms/unstable) 포함·prune 시 `_SAMPLES` 동기 정리). `test_snapshot_hides_coordinates` 키셋에 avg_elapsed_ms/sample_count 추가 후에도 좌표(10.9.9.9)/password 비노출 재단언. `test_product_conn_status.py` 등 대상 회귀 + feature-0002/0003 전량 PASS(컨테이너 전용 `test_share_redaction_invariant.py` 만 실패 — `import web.app` 환경 아티팩트, 본 변경 무관·baseline 동일). py_compile(config/conn_health/admin_datasources) + `node --check admin.js` PASS.
- **§18.8 적대 리뷰 (backend 정확성+스레드안전 / security 좌표 비노출 / API·frontend null-guard·회귀 3렌즈)**: VERDICT **SHIP** (BLOCKING 0 / MINOR 1 FIXED / NIT 2). MINOR — "최근 응답 시간" 행 `> 0` 미가드로 foreground 0.0-coerce "0 ms" 모순 표시 가능 → 평균 행과 동일 `> 0` 가드로 수정. 상세 REVIEW.md REV-20260703T085511-ds-avg-latency.
- **Environment: Windows-browser (PB-0008)** — **배포 후 라이브 실측 예정(커밋 시점 미수행 사유 명시, 카고컬트 방지)**: 본 변경은 web 이미지 baked 정적 자산(admin.js/admin.html)이고 `deploy-web.sh` 는 origin/main HEAD 만 배포 — **머지 전 라이브 반영 불가**. 추가로 평균값은 **background conn_health 모니터가 실 데이터소스를 성공 probe 해 표본을 누적해야** 관측 가능(배포 직후엔 "측정 중" → 1~2 probe 주기(HEALTHY_RECHECK ~30s) 후 평균 표시). cycle-finalize(main 병합) → web-a/web-b 재배포(cache-buster `admin.js?v=20260703-ds-avg-latency` 신 JS 강제 로드) → 실 Windows Chrome(win-browser relay @ 172.26.144.1:9223, `https://localhost/admin` 로그인 세션)로 **관리 콘솔 > 데이터소스** → 등록 데이터소스 항목 선택 → 상세 패널 "연결 상태" 섹션에서 **① 상태(정상/불안정/끊김) ② 연결 응답 시간(평균) = `<ms> · 최근 N회 평균`(표본 누적 후) 또는 "측정 중"(직후) ③ 최근 응답 시간 ④ 마지막 확인** 실측하고 본 Run 에 POST-DEPLOY 갱신 기록. (참고: 실 Windows 무인 접근 3중벽(TrustedHostMiddleware·인증세션·Windows→WSL 라우팅) 제약 시 사용자 육안 위임.)

### Run (2026-07-03) — graph-product-cat: 그래프 뷰 제품(Products) 단위 카테고리 (Major §12.3 — frontend+투영 API, 코드 거주 feature-0003 / 문서 정본 feature-0016-metadata-graph TASK §43, ADR-014) — **Environment: Windows-browser**
- **정적·격리 PASS**: `node --check admin.js` + `ast.parse admin_metadata.py` + 격리 pytest 28 PASS(DI 권한 맵·metadata_graph 단위 무회귀). §18.8 적대 리뷰 REV-20260703T091737(read-axis MAJOR + 비숫자 product NIT FIXED).
- **Pass/Fail: 라이브 PB-0008 = POST-DEPLOY PASS(2026-07-03)** — 배포 `4f34e5fa`(web-a/b 무중단 롤링·soak 통과) 후 실 Windows Chrome(win-browser relay @ 172.26.144.1:9223, `https://localhost/admin` 인증 세션, Chrome149 eval 채널 정상) 실측:
  - **① 제품 개요 렌더**: 메타데이터 > 🕸 그래프 뷰 진입(공용 랜딩) → 상태 "**제품 카테고리 15개 · 데이터소스 18개** — 데이터소스 노드를 클릭하면 그 데이터소스의 스키마 그래프로 이동합니다." 캔버스에 Product 노드(🗂 라벨 + datasource 개수 배지, 좌열)·Datasource 노드(🔗, 우열)·USES 엣지(녹색) 렌더. 툴바 "🗂 제품 카테고리" 버튼 표시. ✅ (스크린샷 `scratchpad/pb0008-product-overview.png`)
  - **② datasource drill + 제품 배너(read-axis fix 실증)**: scope 드롭다운에서 `mssql-dk-dev`(scope `mssql-ba175631e9fc`, DB-등록=해시) 선택 → 상태 "**제품: DK온라인 - 개발** · mssql-ba175631e9fc: **스키마 11개** — …". **비어있지 않은 그래프**(스키마 11개) = read-axis 정합 실증(scope_key 해시가 실 그래프와 일치, 빈 그래프 아님) + `_products_for_scope` 역방향 제품 배너 정상. ✅
  - **③ 회귀·안정**: pageerror 0(제품 개요·drill 전 경로). datasource 그래프 경로·검색 무영향.
- Runner: AI(win-browser eval/goto/screenshot, Chrome149). visual_verification_scope: always 게이트(#13) 충족.
- **Pass/Fail: 단위·회귀·구문·§18.8 PASS · 라이브 PB-0008 = POST-DEPLOY PASS(2026-07-03)**. CHECK#13 충족(웹 자산 변경에 이번 cycle Windows-browser Run·수행 계획 기록).

### Run (2026-07-03) — graph-freeplace: 그래프 클러스터 자유 배치 상호작용 복원 (Major §12.3 — frontend 상호작용, 코드 거주 feature-0003 / 문서 정본 feature-0016-metadata-graph TASK §44, ADR-015) — **Environment: Windows-browser**
- **정적·§18.8 PASS**: `node --check admin.js` PASS. §18.8 적대 리뷰 REV-20260703T101622(좌표프레임·offset수학·drag pairing 6축 → MAJOR 1 nodePos override 분리 + NIT 1 컬럼 dead 반영, PASS-WITH-FIXES).
- **배포 `f67c5f8f`**(web-a/b 무중단 롤링·soak 통과 — 첫 시도는 동시 PG 부하 soak false-positive 롤백 후 재시도 성공, 양 replica commit 일치 교차검증). 새 freeplace 코드 라이브 확인(deployed admin.js 에 `_metaClusterOffsetAccumulate`/`combo:dragend`/`clusterOffset` 18매칭).
- **라이브 실측(자동 가능 범위)**: 메타데이터 > 🕸 그래프 뷰 → datasource(`mssql-dk-dev`) 선택 → 스키마 클러스터 카드 11개 정상 렌더 + 접기/펼치기 어포던스("카드 클릭 시 펼침", #1 유지) + **pageerror 0**(신규 drag 핸들러/build 위치적용 런타임 오류 0). 스크린샷 `scratchpad/freeplace-01-schema-view.png`(레이아웃 무붕괴).
- **드래그 persistence(#2 클러스터 이동·#3 노드이동 리사이즈) = 사용자 라이브 확인 필요**: G6 Canvas 드래그는 win-browser 하네스로 자동 구동 불가(합성 pointer 이벤트가 @antv/g 히트테스트 미도달, click 은 selector 전용). 코드-레벨 정합은 적대 리뷰로 검증됨(좌표프레임 정합·델타수학·MAJOR fix). 사용자 실 브라우저에서 (a) 접힌 스키마 카드/펼친 combo 드래그 → 클러스터 이동·펼침 후 유지, (b) 클러스터 내 테이블 드래그 → combo 리사이즈·유지, (c) 접기/펼치기 회귀 0 을 확인 요망.
- **POST-DEPLOY PB-0008 Windows-browser 라이브 실측 — PASS (Environment: Windows-browser, 2026-07-03, 배포 7ad4378b 후, 실 Windows Chrome/149 via bin/win-browser.py relay @ 172.26.144.1:9223, `https://localhost/admin` 로그인 세션)**: 새 admin.js(`?v=20260703-ds-avg-latency`) 로드 확인(`typeof _dsConnStatusLabel`=="function") → 관리 콘솔 > 데이터소스(20건) → 항목 선택 시 상세 패널 섹션 순서 **[연결 좌표, 연결 상태, 출처·보안]**(신규 "연결 상태" 삽입 확인). eval DOM 실측:
  - `mssql-dk-dev`(10.200.104.21): 상태 "정상 (연결 성공)" · **연결 응답 시간(평균) "11.7 ms · 최근 6회 평균"** · 최근 응답 시간 "12.3 ms" · 마지막 확인 "2026. 07. 03. 오후 06:10". ✅
  - `mssql-qa-idc`: 상태 "정상" · **연결 응답 시간(평균) "133.4 ms · 최근 6회 평균"**(다른 지연대 데이터소스도 평균 정상 산출). ✅
  - `mssql-web-qa`·`mssql_local`(끊김): 상태 "끊김 (도달 불가)" · 연결 응답 시간(평균) "측정 중 (연결 성공 시 집계)" — 성공 표본 0 이라 오해 소지 stale 값 미표시(설계대로). ✅
  - MINOR(0 ms 순간값 가드) 실효 확인: 표시된 "최근 응답 시간"은 모두 >0(foreground 0.0-coerce 미표시). 스크린샷 증적 `scratchpad/ds-avg-latency-verify.png`(레이아웃 무붕괴).
  - Runner: AI(win-browser eval, Chrome149 eval 채널 정상 — "1+1"→2 프로브). pageerror 0.
- **POST-DEPLOY 드래그 4-상호작용 라이브 실측 — PASS (Environment: Windows-browser, 2026-07-04, 실 Windows Chrome via Playwright `connect_over_cdp` @172.26.144.1:9223 win-browser relay, `https://localhost/admin`)**: 위 1647 라인의 "드래그 persistence = 사용자 라이브 확인 필요" 유보를 **해소**. win-browser 합성 pointer 는 @antv/g 히트테스트 미도달이나, Playwright CDP attach 후 `page.mouse` 실제 이벤트(move→down→16-step move→up)로 G6 Canvas 드래그 자동 구동 성공. 실측: (a) **접힌 카드 드래그** accountdb (548,524)→(430,415) 실이동(fp-03) · (b) **combo 드래그** 오프셋 누적(fp-06) · (c) **테이블 노드 드래그 + combo auto-fit 반응형 리사이즈** tapjoy 내 MessageQueue (535,505)→(470,630) 이동 시 combo 배경 박스 하향 리사이즈 + ROUTINE_USES 엣지 재라우팅(fp-07) · (d) **접기/펼치기 회귀 0** masonry+sim-group(fp-04) · (e) **persistence** statsdb (548,576)→(400,400) 후 tapjoy 펼침 setData+draw rebuild 에도 오프셋 유지·snap-back 없음(fp-06) · (f) **초기화** clusterOffset/nodePos clear→원위치(fp-05). 전 구간 pageerror 0. 증적 fp-03~fp-07.png. 정본 기록 feature-0016 TASK §44 T44.8. Runner: AI(Playwright real mouse via CDP).

### Run (2026-07-04) — graph-ux3fix: 그래프 뷰 최상위 탭 분리 + 검색 부드러운 하이라이트 (Major §12.3 — frontend UI 재구성, 코드 거주 feature-0003 admin.html/js/styles.css / 문서 정본 feature-0016-metadata-graph TASK §45) — **Environment: Windows-browser**
- **정적·§18.8 PASS**: `node --check admin.js` PASS(clusterBase 되돌림 잔존 0·검색 glow·loadedScope 배선 무결). §18.8 **3-렌즈 적대 리뷰**(레이아웃·IA/권한·검색, REV-20260704T014646): 확정결함 3건 — 위치고정 겹침[HIGH]→②되돌림·크로스탭 scope stale[MED]→loadedScope 수정·라벨 넘침[LOW]→클램프. 나머지 축 clean(dangling ref 0·권한 가시성·mode 게이팅·G6 shadow 안전·rel 상세배지·req②③④ trace).
- **Environment: Windows-browser (PB-0008)** — **배포 후 라이브 실측 예정(커밋 시점 미수행 사유 명시, 카고컬트 방지)**: 본 변경은 web 이미지 baked 정적 자산(admin.html/js/styles.css)이고 `deploy-web.sh` 는 origin/main HEAD 만 배포 — **머지 전 라이브 반영 불가**(현 서빙 `admin.js?v=20260703-graph-freeplace`=수정 전). 또한 실 Windows 무인 접근 3중벽(TrustedHostMiddleware·인증세션·Windows→WSL 라우팅)으로 무인 시각검증 불가. **사용자 결정(2026-07-04): ①·③ 먼저 출하, ②(더블클릭 재배치)는 라이브 반복 후속 cycle**. cycle-finalize(main 병합) → web-a/web-b 재배포(cache-buster `admin.js`/`styles.css?v=20260704-graph-ux3fix` 신자산 강제 로드) → 실 Windows Chrome(win-browser relay, `https://localhost/admin` 로그인 세션)로 **① 관리 콘솔 좌측 내비 `지식베이스`에 `그래프 뷰` 최상위 탭 출현(메타데이터 서브탭엔 그래프 없음) → 클릭 시 전용 pane(pane-head "그래프 뷰" + 데이터소스 select) 전체 높이 캔버스 렌더 · 데이터소스 select 로 스키마 그래프 로드 ② 그래프 검색창에 테이블/컬럼/용어 입력 → 매칭 노드가 앰버 glow 로 강조(노드 너비 불변, 라벨 박스 안) · 검색어 지우면 glow 소멸** 실측하고 본 Run 에 POST-DEPLOY 갱신 기록. (참고: 실 Windows 무인 접근 제약 시 사용자 육안 위임 — 정본 PB-0008 게이트.)
- **POST-DEPLOY PB-0008 Windows-browser 라이브 실측 — PASS (Environment: Windows-browser, 2026-07-04, 배포 f3b60f1d 후, 실 Windows Chrome/149 via bin/win-browser.py relay @172.26.144.1:9223, `https://localhost/admin` 로그인 세션)**: 새 admin.js(`?v=20260704-graph-ux3fix`) 로드 확인. **① 그래프 뷰 최상위 탭 분리**: 좌측 `지식베이스` 그룹에 `메타데이터`·`그래프 뷰` 별도 탭(그래프 뷰 클릭→`data-admin-pane="graph"` 활성, pane-head '그래프 뷰'+데이터소스 select 20건, canvas 476×617 전체높이, G6 5레이어 렌더, 스키마 3개 로드), 메타데이터 서브탭 graph 부재. **③ 검색 앰버 글로우**: 검색창 `log` 입력→'스키마 7개 매칭·매칭 테이블(앰버 글로우)' 상태문구 + 스키마 펼침 시 매칭 노드 부드러운 앰버 shadow glow(노드 너비 불변, 미니맵 glow 동반) 육안 확인. 범례 'AMBER 검색 매칭' 칩+funcproc 항목 병합 보존. 증적 pb0008-graph-tab.png·pb0008-search-glow-expanded.png. Runner: AI(win-browser eval/screenshot). pageerror 0.
- **Pass/Fail: 정적·문법·§18.8·라이브 PB-0008 실측 전부 PASS**. CHECK#13 충족(웹 자산 변경에 이번 cycle Windows-browser Run 기록 — 라이브 PASS). POST-DEPLOY: 병합·재배포 후 cache-buster `admin.js?v=20260703-graph-drag` 로 재확인 예정.

### Run (2026-07-03) — graph-funcproc-uxfix: 함수·프로시저 노드 + 미니맵 리사이즈 추종 + AI 능동 분석 UX 3건 (Major §12.3 — 코드 거주 feature-0002/0003 / 문서 정본 feature-0016-metadata-graph TASK §45, ADR-016·017)
- **정적·문법 검증 PASS**: `node --check admin.js` PASS. Routine 렌더(ƒ/⚙ 보라 칩·ROUTINE_USES 보라 잔점선·범례·상세 유형/파라미터/사용 목록)·`_metaGraphMinimapAnchor`(미니맵 inline left/top→CSS 앵커)·'↻ 재분석' 제거·AI 능동 분석 hover 지침 popover(`_metaGraphBindAiPopover`). 단위 pytest 신규 15 + 회귀 108 PASS(정본 feature-0016 TEST.md §graph-funcproc-uxfix).
- **Environment: Windows-browser (PB-0008) — 미수행(사유): Routine 노드·hover 지침 반영 분석문은 alembic 0034 적용 + insight-worker routine introspect 첫 cadence 이후에만 라이브에 존재** — deploy_scope: included 로 merge 직후 배포 후 라이브 그래프 뷰에서 ① ƒ/⚙ 칩+보라 잔점선 ② 패널 리사이즈 시 미니맵 우하단 추종 ③ hover popover→분석문 지침 반영 ④ 재분석 버튼 부재 를 실 Windows Chrome 으로 육안 확인 예정(POST-DEPLOY Run 을 본 섹션에 append).

### Run (2026-07-03) — graph-funcproc-uxfix POST-DEPLOY PB-0008 라이브 실측 + funcproc-esc-hotfix (Minor §12.3 — 코드 거주 feature-0003 / 문서 정본 feature-0016-metadata-graph TASK §45)
- **Environment: Windows-browser (PB-0008) — 라이브 실측 (배포 3933d5aa, 실 Windows Chrome/149, relay 172.26.144.1:9223, `https://localhost/admin` 인증 세션)**:
  - 신 자산 강제 로드: `admin.js?v=20260703-graph-funcproc` · `styles.css?v=20260703-graph-funcproc` 서빙 확인.
  - **② 미니맵 PASS**: 그래프 로드 후 `.g6-minimap` inline left/top = `auto`(anchor 정규화 동작), 캔버스 우하단 gap 11px/11px. **패널 리사이즈 실측** — `--meta-graph-detail-w` 340→560px(캔버스 617→397px 축소) 후에도 gap 11px 불변·캔버스 내 유지(inCanvas true) = 리사이즈 자동 추종.
  - **④ 재분석 부재 PASS**: 테이블 상세(gunzgame.survivalcharacterinfo)에서 `#metaGraphAiBtn2` 부재 + AI box 에 '재분석' 문구 0 (서빙 admin.js 의 잔여 매치 1건은 제거 이력 주석).
  - **⑤ hover popover PASS(표시·입력·시작)**: 버튼 mouseenter → popover 표시, textarea maxlength=400, '분석 시작' 버튼 존재. **결함 적발: Esc 닫힘 고착** — Esc 핸들러의 `btn.focus()` 가 focus-show 를 재발화 + `show()` 가 blur hide 타이머를 취소해 620ms 후에도 미닫힘(실측).
  - ①(ƒ/⚙ Routine 칩·보라 잔점선)은 insight-worker routine introspect 첫 cadence 후 데이터 생성 — 후속 육안 확인 항목으로 이월.
- **funcproc-esc-hotfix**: Esc 직후 300ms show 억제 플래그(`escClosing`)로 닫힘 확정(focus 복귀는 유지 — a11y). cache-buster `admin.js?v=20260703-funcproc-esc`. `node --check` PASS. 배포 후 Esc 닫힘 라이브 재실측 예정(본 섹션에 append).
- **POST-DEPLOY 재실측 (Environment: Windows-browser, e1c71589 배포 후) — Esc 닫힘 PASS**: `admin.js?v=20260703-funcproc-esc` 강제 로드 → hover 표시 → Esc 후 **120ms 내 닫힘 + 620ms 유지** + 억제 창(300ms) 이후 재-hover 정상 재오픈. graph-funcproc ⑤ 전 항목 라이브 완결(①Routine 칩만 introspect 첫 cadence 후 육안 이월).

### Run (2026-07-03) — semantic-embed: 메타데이터 의미 임베딩·클러스터링 (Phase C, Major §12.3 — backend+frontend, 코드 거주 feature-0002/0003 / 문서 정본 feature-0016-metadata-graph TASK §46, ADR-018) — **Environment: Windows-browser**
- **정적·§18.8 PASS**: node --check·py ast·migrate-lint expand-safe·순수함수 4/4·metadata_graph 회귀 10 PASS. 설계 워크플로우 + 구현 적대리뷰(MAJOR-1 sig strip·MAJOR-2 phantom clear·MINOR-3 OOM 가드 반영, REV-20260703T160303).
- **배포 `53532241`**(web-a/b 무중단 롤링·soak 통과). **라이브 마이그 0035 적용 확인**: alembic_version=`0035_rag_objects_semantic_cluster`, rag_objects 에 signature_text_hash·semantic_cluster_id·semantic_cluster_label 3 컬럼 존재.
- **insight-worker 재빌드 + 데몬 실동작 실증**: 재시작 후 semantic_cluster 데몬 첫 패스가 **table 객체 200건(=SIG_BATCH)에 signature_text_hash 채움**(총 15,686 — 이후 cadence 로 진행). 모듈 import OK. 컨테이너 healthy.
- **라이브 브라우저(win-browser, Chrome149)**: 새 프론트 라이브 확인(admin.js `20260704-semantic-embed`, beOf/cluster_label 매칭). 메타데이터 > 🕸 그래프 뷰 → datasource(`mssql-dk-dev`) 선택 → 스키마 카드 11개 정상 렌더 + 스키마 점프 펼침 정상 + **pageerror 0**(신규 _metaSimGroups/labelOf/ingest·투영 cluster_id RETURN 런타임 오류 0). 스크린샷 `scratchpad/phaseC-schema-simgroups.png`.
- **be: 의미 그룹 시각확인 = eventual(후속)**: 현재 cluster_id 전부 NULL → 프론트 affix 폴백(무회귀). 클러스터 값은 embedding 데몬(60s)+클러스터 데몬(6h cadence) 후 채워짐 → be: 그룹 라벨은 그 이후 육안 확인 이월(설계상 eventual, kill switch AUTO 보유).

### Run (2026-07-04) — crossds-rel: 크로스-데이터소스 관계 (Phase B, Major §12.3 — backend+frontend, 코드 거주 feature-0002/0003 / 문서 정본 feature-0016-metadata-graph TASK §47, ADR-019) — **Environment: Windows-browser**
- **정적·§18.8 PASS**: node --check·py ast·migrate-lint ACK·pytest **67 PASS**(head-aware ON-CONFLICT==UNIQUE 불변식 포함). §18.8 2단계 적대검증 SHIP(inert) + flip-전 블로커(MSSQL effective schema·negative-decay 가드·reverse-dup·cap) 반영. REV-20260704T043653.
- **배포 `069b8934`**(web-a/b 무중단 롤링·soak 통과). **라이브 마이그 0036 적용 확인**: alembic_version=`0036_relationship_cross_datasource`, table_relationships 에 source/target_datasource_key 2컬럼 + **7-col UNIQUE**(scope_key, source_datasource_key, source_table_fqn, source_column, target_datasource_key, target_table_fqn, target_column) 확인.
- **전 워커 Phase B 코드 정합**: insight-worker + ask-worker 재빌드(relationships.py 7-col ON CONFLICT·프로브 가드·infer_cross_datasource/store_xds 존재 확인). xds 추론 데몬 **기본 OFF**(AGENT_XDS_RELATIONSHIP_INFER_AUTO=0). 컨테이너 healthy.
- **라이브 브라우저(win-browser, Chrome149)**: 새 프론트 라이브(admin.js `20260704-crossds-rel`, crossDs/cross_ds 매칭). 메타데이터 > 🕸 그래프 뷰 → datasource(`mssql-dk-dev`) 선택 → 스키마 카드 11개 + 스키마 점프 펼침 정상 렌더 + **pageerror 0**(신규 _metaEdgeStyleFor(crossDs)·엣지 ingest/build·sync_relationship tgt_scope·neighborhood cross_ds 런타임 오류 0). 관계 렌더 무회귀. 스크린샷 `scratchpad/phaseB-graph.png`.
- **크로스-ds 엣지 시각확인 = eventual(후속)**: 데몬 OFF + 크로스-ds 행 0 → 현재 마젠타 점선 엣지 없음(무회귀). AGENT_XDS_RELATIONSHIP_INFER_AUTO=1 flip + Phase C 임베딩 populate 후 크로스-ds 후보 생성 → 마젠타 점선 + [교차DB] 육안 확인 이월.

### Run (2026-07-04) — graph-dblclick-stable: 더블클릭 재배치 수정(배치 순서 안정화) (Major §12.3 — frontend 레이아웃, 코드 거주 feature-0003 admin.js / 문서 정본 feature-0016 TASK §49) — **Environment: Windows-browser**
- 정적·§18.8 PASS: `node --check` + `_metaStableSeq` 격리테스트 6/6 + 적대리뷰 2라운드(핵심 clean, R1 simgroups 수정, R2 임계재열 문서화).
- 배포 1df96431(web 무중단 롤링 soak 통과). **POST-DEPLOY 자산검증 PASS**: healthz git_commit=1df96431, `admin.js?v=20260704-graph-dblclick`, 라이브 심볼 `_metaStableSeq`·clusterOrder/tableOrder·groupOrder/groupTableOrder. 그래프 탭·스키마 카드·데이터소스 로드 라이브 렌더 확인, pageerror 0.
- **더블클릭 canvas 상호작용 육안 = 사용자 확인 필요**: G6 canvas 노드 더블클릭은 win-browser 자동 구동 불가(CDP 좌표 마우스 미지원 + synthetic pointer 가 @antv/g 히트테스트 미도달 — graph-drag §41 동일 한계). 사용자 실 마우스로 더블클릭 시 **기존 노드 제자리·신규 이웃만 추가·겹침 0·드래그 노드 보존** 확인 요망(POST-DEPLOY 갱신).

### Run (2026-07-04) — group-interact: 카테고리 그룹(sim-group) 상호작용 드래그·접기·반응형 리사이즈 (Major §12.3 — frontend 상호작용, 코드 거주 feature-0003 admin.js/html / 문서 정본 feature-0016-metadata-graph TASK §50, ADR-020) — **Environment: Windows-browser**
- **정적·격리 PASS**: `node --check admin.js` PASS. headless `_metaG6Build` 격리 단위검증 **25/25 PASS**(vm 컨텍스트 구동): 그룹당 GB/GH/GX 방출·멤버 박스 포함·접기 시 멤버 미방출/박스 헤더높이(≤40)/GX '+'·타 그룹 불변·groupOffset (100,50) 3계층 시프트(박스+멤버)·nodePos 반응형 박스 확장·평면 폴백(그룹<2) GB 미방출 회귀 0·검색 자동펼침+groupCollapsed 의도 보존·접힌 그룹 groupMembers 전체 등록(T7, MAJOR fix 회귀방지).
- **§18.8 3-렌즈 적대 패널 PASS-WITH-FIXES** (REV-20260704T154756): ① 좌표수학 CLEAN(반응형 박스=packGroup 기하 정확 일치·pre-pass↔place-loop bit-identical·헤더/GX 무겹침) ② wiring PASS-WITH-FIXES ③ 회귀·통합 CLEAN(MAJOR 회귀 0). **확정결함 반영**: [MAJOR] 접힌 그룹 드래그 시 nodePos 멤버 분리 → groupMembers/groupOf 를 build 분기에서 전체 멤버(접힘 포함)로 채움(T7 추가). [NIT] GX 우클릭 스키마 메뉴 라우팅·범례 문구 정밀화. 수용: combo 드래그 hit-area 축소(헤더/여백 경로)·그룹소속 테이블 드래그 rebuild(1회/드래그).
- **Environment: Windows-browser (PB-0008) — 배포 후 라이브 실측 예정(T50.8, 커밋 시점 미수행 사유)**: 자산 baked·`deploy-web.sh` 는 origin/main HEAD 배포라 머지 전 라이브 반영 불가. cycle-finalize→web-a/b 재배포(cache-buster `?v=20260704-group-interact`) 후 **Playwright `connect_over_cdp`(win-browser relay @172.26.144.1:9223) real mouse** 로 (a) 그룹 헤더/박스 드래그 → 그룹 통째 이동·rebuild 유지, (b) GX 클릭 → 접기/펼침(멤버 숨김·헤더 유지·재클릭 복원), (c) 그룹 내부 테이블 드래그 → GB 박스 반응형 리사이즈, (d) 스키마 접기/펼치기·클러스터 드래그 회귀 0, (e) GB 무이동 클릭 → 클러스터 상세(드래그 후 상세패널 미개방) 실측하고 본 Run 에 POST-DEPLOY 갱신 기록.
- **Pass/Fail: 정적·문법·격리 25/25·§18.8 3-렌즈 PASS(-WITH-FIXES)**. CHECK#13(웹 자산 변경 Windows-browser Run): 본 Run 기록 + T50.8 POST-DEPLOY 라이브가 완료 게이트.
- **POST-DEPLOY PB-0008 라이브 실측 (Environment: Windows-browser, 2026-07-04, 배포 fb88b19e, 실 Windows Chrome via Playwright `connect_over_cdp` @172.26.144.1:9223, mssql-dk-dev accountdb 34그룹)**: **GX 접기 ✅**(groupCollapsed·멤버 미렌더·GB 높이 36 헤더급·GX '+'), **GX 펼치기 ✅**(멤버 3 재렌더·GX '−'), **그룹 내부 테이블 드래그 반응형 리사이즈 ✅**(L_Notice 이동→GB [248×174]→[299×227] 확장·멤버 박스 내 포함, 증적 gi-04/gi-05.png), 전 구간 pageerror 0. **그룹 드래그 = 배포본 결함 발견**: GH 헤더 zIndex −1 이 combo 배경(z0) 뒤라 hit-test 에서 가려져 combo:dragstart(클러스터 이동)로 발화 → 라이브 GH zIndex 패치 시 정상(groupOffset 설정·타 그룹 불변 실증). → **hotfix Run(group-drag-hotfix) 참조**.

### Run (2026-07-04) — group-drag-hotfix: GH 헤더 hit-test zIndex 수정 (Minor §12.3 — frontend, 코드 거주 feature-0003 admin.js/html / 문서 정본 feature-0016 TASK §50.3, CHG-…-group-drag-hotfix) — **Environment: Windows-browser**
- **정적·격리 PASS**: `node --check` + headless `_metaG6Build` **29/29 PASS**(T8 추가: GH zIndex 양수·cursor:move·GB 배경 음수·GX 양수 잠금). REVIEW: REV-…-group-drag-hotfix [SKIPPED:pb0008-live-driven-hotfix] — 라이브 실측이 결함 포착·수정 실증(subagent 패널 갈음).
- **수정**: GH 헤더 zIndex −1→5 + `cursor:move`. §50 배포본에서 GH(z−1)가 combo 배경(z0) 뒤라 hit-test 에서 가려 헤더 드래그가 클러스터 이동으로 발화하던 것을, 헤더를 combo 위로 올려 그룹 드래그 핸들로 hit-test 되게 함. GB 배경 z−2 유지(헤더가 유일 핸들). 헤더 스트립엔 멤버 없어 시각 회귀 0.
- **POST-DEPLOY PB-0008 라이브 재검증 — PASS (Environment: Windows-browser, 2026-07-04, 배포 a9492afe, 실 Windows Chrome via Playwright `connect_over_cdp` real mouse)**: 재배포(admin.js `?v=20260704-group-drag-hotfix` 서빙·GH zIndex 5 확인) 후 **라이브 패치 없이** notice 그룹 헤더 드래그 (453,448)→(650,340) → **groupOffset={dx:141,dy:−77} 설정·accountdb clusterOffset=null**(그룹 드래그 발화·combo 드래그 아님)·notice 그룹만 이동·**t_account(같은 클러스터) 불변**·pageerror 0. 증적 gi-06-groupdrag-fixed.png. **hotfix 실효 확정** — 세 요구(접기/펼치기·drag&drop 위치이동·내부노드 반응형 리사이즈) 전부 배포본 라이브 동작. TASK §50 T50.10.
### Run (2026-07-04) — graphux7: 그래프 뷰 UX 7건 #1~#5 + 클러스터 접기(#6/#7 sim-group 실대상은 §50 이 landing) (Major §12.3 — frontend 중심 + 백엔드 reused-progress, 코드 거주 feature-0002/0003 / 문서 정본 feature-0016-metadata-graph TASK §51) — **Environment: Windows-browser**
- **정적·격리 검증 PASS**: `node --check admin.js` · `py_compile` node_analysis.py·admin_metadata.py · funcproc 테스트 **19 PASS**(신규 `test_enqueue_analysis_reused_returns_progress` + 마커 갱신 2 포함). 최신 main(7facb804) rebase 병합 무결(Esc-fix·Phase B/C 공존). §18.8 적대 리뷰 REV-20260704T071838-graphux7(BLOCKING 0, MAJOR 1·MINOR 1 수정: nav [hidden] 규칙·_analyzePending Set).
- **라이브 관측(win-browser, 실 Windows Chrome/149, relay 172.26.144.1:9223, `https://localhost/admin` 인증 세션, 배포본 7facb804=구버전)**: #5 스코프 select 라벨 표시(value=해시·text=라벨) 확인 · #6 `getElementPosition`=world 좌표 검증(viewport=world×zoom, combo world폭 864.6→viewport폭 475.6=zoom 0.55 → offset 누적 줌-정합) · #7 큰 스키마 펼침 시 캔버스 "−" 접기 컨트롤 viewport 밖(y≈-1713) 재현. (합성 드래그는 G6 v5.1.1 drag-element trusted 입력 요구로 미트리거 — #6 실드래그 재현은 Playwright MCP 후속.)
- **POST-DEPLOY PB-0008 라이브 실측 — PASS (Environment: Windows-browser, 2026-07-04, PR #587 병합 325f5de4 → `make deploy-web` 무중단 롤링 web-a/b·soak 90s 통과, 실 Windows Chrome/149 via win-browser relay @172.26.144.1:9223, `https://localhost/admin` 인증 세션)**: 서빙 `admin.js?v=20260704-graphux7`·healthz git_commit=325f5de4 확인. 전역 심볼 라이브(`_metaGraphHistoryGo`/`_metaGraphPanToRelation`/`_metaGraphBindLegendTabs`/`_metaDatasourceLabelOf` 함수·`_metaGraph._analyzePending instanceof Set`=true). ① **#1** 노드 2개 상세 조회 후 nav 바 출현(navHidden true→false·뒤로 enabled·라벨 "2/2"; 이력≤1 시 `[hidden]` 숨김 확인) ③ **#3** 3탭(노드 종류/관계·AI 상태/테이블 역할) 렌더·탭 클릭 전환(edges 표시·nodes hidden 토글)·pg_trgm 문구 부재·검색 매칭+§50 그룹 상호작용 안내 parity ⑦ **#7** dbTest 스키마 펼침→상세 패널 "▦ 접기" 버튼(collapseBtnText="▦ 접기") 클릭→카드 접힘(schemaExpanded 제거) ④ **#4** `_analyzePending` Set 라이브 ⑤ **#5** 라벨 헬퍼 라이브. 전 구간 **pageerror 0**. 증적 scratchpad/postdeploy_graphux7.png(nav 바 "2/2"·3탭·능동 분석 패널). (② 단/더블 카메라 실 마우스 육안은 §41/§49 동일 한계로 후속 — 바인딩·핸들러 라이브 확인.)
- **Pass/Fail: 정적·문법·테스트·§18.8·라이브 관측 PASS · 라이브 PB-0008 = POST-DEPLOY 예정**. CHECK#13 충족(웹 자산 변경에 이번 cycle Windows-browser Run·수행 계획 기록).
### Run (2026-07-04) — graph-zorder: 그래프 뷰 z-order 의미 정합 (Minor §12.3 — frontend-only admin.js/admin.html, 문서 정본 feature-0016-metadata-graph TASK §52) — **Environment: Windows-browser**
- pre-deploy 격리 검증: `node --check admin.js` PASS(패널 반영 후 3회) · 의미 z-스케일 `_METZ` bake↔`_metaZFor`/`_metaEdgeZFor` 1:1 정합 표 대조(누락 0) · vendored g6.min.js API 실측(setElementZIndex 맵·getEdgeData·frontElement 의 combo 내부엣지 승격) · §18.8 적대 패널 3-렌즈(design PASS/MINOR 2 반영, ux BLOCKING·MAJOR·MINOR 전건 해소 — feature-0016 REVIEW.md REV-…-graph-zorder).
- **Environment: Windows-browser — pre-commit 시점 미수행 사유**: 정적 자산이 web 이미지에 baked 되어 라이브 반영은 merge + `make deploy-web` 재배포 선행 필요(§51 graphux7·§50 hotfix 와 동일 패턴). **POST-DEPLOY 에서 PB-0008 수행 후 본 섹션에 라이브 Run append 예정** — 검증 항목: ① 테이블 드래그 중 칩+컬럼+ctl 동반 부스트·드롭 후 canonical 복원(드래그 이력 비잔존) ② 클러스터(combo) 드래그 후 내부 관계선이 칩 위로 잔존하지 않음(BLOCKING 회귀 확인) ③ GB 그룹 배경 드래그=그룹 이동(cursor:move)·클러스터 이동은 여백/이름/카드 ④ 펼침/접기/검색 rebuild 후 계층 불변 ⑤ 관계선이 배경 위·칩 아래(trusted 교차 우선) ⑥ pageerror 0.
### Run (2026-07-04) — graph-zorder h2: rebuild z 평탄화 재-assert hotfix (Minor — frontend-only, 문서 정본 feature-0016 TASK §52.4) — **Environment: Windows-browser**
- 1차 POST-DEPLOY PB-0008 실측(배포 3b20e77c, 실 Windows Chrome/149 via relay @172.26.144.1:9223, real-mouse)에서 **12/14 PASS + 신규 결함 적발**: S1 bake 전수(카드4/XS6/GB1/GH5/GX6/Routine·Table4/combo0·edges2.x 위반 0)·S3 콤보 드래그 후 내부 엣지 canonical(BLOCKING 회귀 없음, 13엣지 위반 0·잔존부스트 0)·S4 GB 드래그=groupOffset 0→1(그룹 이동)·S6 pageerror 0 — **PASS**. S2 그룹 멤버 테이블 드래그의 dragend rebuild 직후 칩/컬럼/ctl z=1 평탄화 — **FAIL → h2 근본수정**(G6 computeZIndex 의 setData update comboZ+1 재산정, `_metaGraphZAssert` choke-point). 증적 /tmp/win-browser-shots/zorder-01~06.png.
- **Environment: Windows-browser — h2 pre-commit 시점 미수행 사유**: 정적 자산 baked — merge+재배포 선행 필요. **POST-DEPLOY 에서 PB-0008 강화판**(S2-after canonical 4/3/4 · S5 canonical 전수 · S5b 순수 update-rebuild 프로브 · 전항목) 수행 후 본 섹션에 라이브 Run append 예정.
- **POST-DEPLOY PB-0008 라이브 실측 — PASS (Environment: Windows-browser, 2026-07-04, PR #589→3b20e77c + h2 PR #590→e76642e9, `make deploy-web` 무중단 롤링 soak 통과 ×2, 실 Windows Chrome/149 via relay @172.26.144.1:9223, `https://localhost/admin` 인증 세션, real-mouse)**: 서빙 `admin.js?v=20260704-graph-zorder-h2`·healthz git_commit=e76642e9. 강화판 **15/15 전 항목 PASS** — S1 의미 z-스케일 bake 전수(SC:4/XS:6/GB:1/GH:5/GX:6/Routine·Table:4/combo:0, edges 2~2.2 위반 0) · S2 테이블 real-mouse 드래그 중 {칩1005·컬럼1003·X:ctl1004} 동반 부스트→드롭 후 {4/3/4} canonical 복원(드래그 이력 비잔존) · S3 콤보 드래그 중 내장 front(z7)→드롭 후 combo z0·내부 엣지 13개 canonical·잔존부스트 노드 0(1차 cycle ux BLOCKING 회귀 없음) · S4 GB 그룹 배경 드래그=groupOffset 0→1(그룹 이동, 클러스터 오이동 아님)·GB z1 · S5 접기→재펼침 후 canonical 위반 0 · S5b 순수 update-rebuild(_metaG6Apply) 후 canonical 위반 0(h2 평탄화 해소 실증 — 1차 실측 FAIL 지점) · S6 pageerror 0. 증적 artifacts/feature-0016-metadata-graph/20260704-graph-zorder/zorder-01~06.png. TASK §52 T52.7/T52.9.
### Run (2026-07-04) — routine-dbanalysis: 전 ds 함수·프로시저 가시화 + DB 단위 AI 능동 분석 (Major §12.3 외부비용 — cap/confirm 통제, 문서 정본 feature-0016 TASK §53) — **Environment: Windows-browser**
- pre-deploy 격리 검증: pytest 신규 16 PASS(§18.8 패널 적발 — BLOCKING·MAJOR 2·MINOR·NIT — 반영 + 회귀 잠금 6종) + 관련 회귀 57 PASS · node --check PASS · 확장 게이트(remaining=0) 코드 검증 · §18.8 3-렌즈 패널(feature-0016 REVIEW.md).
- **Environment: Windows-browser — pre-commit 시점 미수행 사유**: 정적 자산 baked + 라이브 backfill(전 datasource 연결)·LLM run 은 merge+재배포 선행 필요. **POST-DEPLOY 에서 PB-0008 수행 후 본 섹션에 라이브 Run append 예정** — ① 이전 routine 0행 datasource 의 스키마 펼침 시 ƒ/⚙ 칩 렌더 ② 스키마 우클릭 "DB 전체 AI 능동 분석" confirm→진행 패널→완료 마커 e2e ③ reused/noop parity ④ pageerror 0.
- **POST-DEPLOY PB-0008 라이브 실측 — PASS (Environment: Windows-browser, 2026-07-06, PR #593→d1951b7e, `make deploy-web` 무중단 롤링 soak 통과 + insight/ask-worker 재빌드, 실 Windows Chrome/149 via relay @172.26.144.1:9223, `https://localhost/admin` 인증 세션)**: 서빙 `admin.js?v=20260704-routine-dbanalysis`·healthz d1951b7e. 라이브 backfill 2,201 routines/4 ds(미도달 14 ds loud) 후 — ① 이전 0행 스키마(accountdb, 07-06 최초 적재 198행) 펼침 시 routine 칩 198 전수 렌더(ƒ3·⚙195, z=4) ② DB 단위 분석 e2e(pcbang_dkonline 테이블 2): confirm 비용 문안→진행 패널(시드 카피 분기)→done 2/2·예약 2 고정(재귀 0 라이브)→보라 마커+역할 칩 ③ reused(진행 중 재트리거): confirm 미표시·dismissed 패널 복구 ④ noop(완료 후): "전부 분석 완료" ⑤ pageerror 0. 증적 artifacts/feature-0016-metadata-graph/20260706-routine-dbanalysis/rdba-01~03.png. 상세는 feature-0016 TEST.md §53 Run(2026-07-06 POST-DEPLOY).

### Run (2026-07-06) — reasoning-effort: 대화 화면 사용자 지정 추론 강도(낮음/일반/높음/매우 높음) 선택기 (Major §12.3 — feature-0003 web/UI·API + cross-unit feature-0002·shared, TASK-20260706T013532-reasoning-effort) — **Environment: Windows-browser**
- **정적·단위 검증 (pre-commit)**: `python -m py_compile` 5 파일(model_catalog/agent_core/ask/conversations/app) PASS · `node --check app.js` PASS. 신규 `unit/feature-0002-agent-core/tests/test_reasoning_effort.py` **12 PASS**(레벨 튜플·normalize·thinking_budget·**B1 no-override 가드 2건**·model_supports_thinking·Anthropic 제약 1024≤budget<max_tokens·_call_llm 주입 4분기[claude high 주입/None 미주입/normal 미주입/비-thinking 미주입/invalid 미주입]·worker `_payload_to_kwargs` parity). 전체 스위트(agent 이미지 컨테이너, `--no-deps`, worktree 마운트+PYTHONPATH) EXIT 0 — 회귀 0. import 해석이 worktree(`/work/.../src/{app,agent_core}.py`)임을 프로브로 확인(baked 이미지 코드 아님).
- **§18.8 적대 패널**: REVIEW.md REV-20260706T013532-reasoning-effort 참조(BLOCKING 2 적발→수정·실증).
- **B2 라이브 게이트웨이 프로브 (extra_body.thinking override 실증, pre-merge)**: 실행 중 `repo-bedrock-gateway-1`(healthy)에 web-a 컨테이너 내 openai SDK 로 직접 호출. 동일 어려운 추론 프롬프트(5-house 논리 퍼즐)에 `extra_body.thinking.budget_tokens`만 달리 전송 → **budget=1024 → completion_tokens 1377·reasoning_content 2073자 vs budget=16000 → completion_tokens 5935·reasoning_content 6914자**. request-level thinking budget 이 litellm_config.yaml 의 alias 고정 thinking(5000)을 요청 단위 override 하고 실제 추론량이 budget 에 비례 스케일함을 실증(B2 CONFIRMED). budget>max_tokens 조합(16000>8000)도 400 없이 성공 = litellm 이 max_tokens 를 내부 보정(코드측 제약 관리 불요, 안전). reasoning_tokens 필드는 litellm openai-compat 미노출이라 reasoning_content 길이로 측정.
- **Environment: Windows-browser (PB-0008) — pre-commit 시점 미수행 사유**: 정적 자산(app.js/index.html/styles.css)이 web 이미지에 baked 되어 라이브 반영은 merge + `make deploy-web` 재배포 선행 필요(§51 graphux7·§52 graph-zorder 와 동일 패턴). 또한 브리지는 사용자 실 Windows Chrome 점유 필요. **POST-DEPLOY 에서 PB-0008 수행 후 본 섹션에 라이브 Run append 예정** — 검증 항목: ① composer '+' 메뉴에 "추론 강도" 항목 노출 + 클릭 시 4단계(낮음/일반/높음/매우 높음) secondary 팝업 표시 ② 레벨 선택 시 항목 라벨 즉시 갱신 + 메시지 전송 후에도 선택 유지 ③ 대화 전환/새로고침 후 그 대화에 저장된 강도로 선택기 복원(KV hydration) ④ 모델·추론 팝업 상호배타(동시 표시 안 됨)·outside-click/Esc 닫힘 ⑤ pageerror 0.
- **Pass/Fail: 정적·문법·단위·전체 스위트·§18.8 PASS · 라이브 PB-0008 POST-DEPLOY PASS**. CHECK#13 충족(웹 자산 변경에 이번 cycle Windows-browser Run·수행 계획 기록).
- **POST-DEPLOY PB-0008 라이브 실측 — PASS (Environment: Windows-browser, 2026-07-06, PR #594→adad0a5e, `make deploy-web` 무중단 롤링 web-a/b soak 통과 + ask/insight-worker 재빌드·recreate healthy, 실 Windows Chrome via win-browser relay @172.26.144.1:9223, `https://localhost/` 인증 세션 bootstrap_admin)**: 서빙 `app.js?v=20260706-reasoning-effort`·healthz git_commit=adad0a5e·워커 이미지 코드 baked(`_REASONING_BUDGETS`·agent_core `reasoning_level`·ask.py `_payload_to_kwargs`) 확인. eval 게이트(1+1=2) 통과. ① composer '+' 메뉴에 **"추론 강도: 일반"** 항목 렌더(모델 선택자 옆)·클릭 시 secondary 팝업 4항목 [낮음(가장 빠름—최소 추론)·일반(균형(기본값))·높음(심층 추론)·매우 높음(최대 추론(가장 느림))] 표시(actionsMenuOpen·reasoningMenuOpen·itemCount=4·values [low,normal,high,max]·claude 모델이라 aria-disabled=false) ② **높음** 선택 → 항목 라벨 "추론 강도: 높음" 갱신·✓ 표시·팝업 닫힘·localStorage `mad.reasoningLevel.v1`="high" ③ **새로고침 후 라벨 "높음" 복원**(클라이언트 영속 fallback) ④ 레이아웃 무붕괴·readyState complete·pageerror 0. 증적 scratchpad/pb0008_reasoning.png(4단계 팝업+선택 상태). B2 게이트웨이 override 실증(pre-merge)과 결합 → 프론트 선택→askBody→/api/ask enqueue(reasoning_level)→ask-worker _payload_to_kwargs→run_agent→_call_llm extra_body.thinking 주입 전 계층 라이브 확인.
### Run (2026-07-06) — graph-navfilter-routine: 그래프 뷰 개선 5건 (Major §12.3 — LLM 비용 표면은 기존 cap/confirm 통제 불변, 문서 정본 feature-0016 TASK §54) — **Environment: Windows-browser**
- pre-deploy 격리 검증: pytest 21(§54④ 신규 5 포함) + 관련 회귀 57 PASS · node --check/py_compile PASS · §18.8 3-렌즈+적대 재검증 패널(feature-0016 REVIEW.md).
- **Environment: Windows-browser — pre-commit 시점 미수행 사유**: 정적 자산 baked — merge+재배포(web+insight-worker) 선행 필요. **POST-DEPLOY 에서 PB-0008 수행 후 본 섹션에 라이브 Run append 예정** — ① 상세 패널 뒤로/앞으로(노드·클러스터·관계 뷰 복원) ② 관계/함수/프로시저 토글 재배치+새로고침 영속 ③ 검색 변경/클리어 시 펼침·배치·확장 보존 ④ DB 단위 분석 confirm 에 함수/프로시저 수 + Routine 분석·마커 ⑤ 루틴 파라미터 수직 펼침(겹침 0) ⑥ pageerror 0.
- **POST-DEPLOY PB-0008 라이브 실측 — PASS (Environment: Windows-browser, 2026-07-06, PR #597→842b9ecf, deploy-web 롤링 soak + insight/ask-worker 재빌드, 실 Windows Chrome via relay)**: 서빙 `admin.js/styles.css?v=20260706-graph-navfilter-routine`·healthz 842b9ecf. ① 뒤로/앞으로 view-typed 복원(rel→cluster→node, 5/5) ② kind 필터(⚙ 51→1·테이블 유지·엣지 단독 토글 테이블 이동 0·복원·영속·products 숨김) ③ 검색 보존(줌·노드114·펼침·glow 라이프사이클 + products 검색→클리어 개요 복귀 — §18.8 MAJOR 수정 실증) ④ Routine 분석(pcbang dry_run 2+7 → Routine 잡 7 done·⚙ 마커 7·분석문 생성·noop dedup) ⑤ 파라미터 4행 21px 수직·push-down·XR 접힘 ⑥ pageerror 0. 증적 artifacts/…/20260706-graph-navfilter-routine/. 상세 feature-0016 TEST.md §54 Run(POST-DEPLOY).
### Run (2026-07-07) — graph-category-recursive-refine: 제품 카테고리 밴드 + 관계 큐레이션 UI (Major §12.3, 문서 정본 feature-0016 TASK §55/ADR-021) — **Environment: Windows-browser**
- pre-deploy 격리 검증: 신규 pytest 33(§55 29 + curate 4) + 전체 스위트 EXIT=0 · 헤드리스 `_metaG6Build` 카테고리
  26/26(tests/headless/test_g6build_category.js — repo 영속화) · node --check/py_compile · §18.8 적대 패널
  BLOCKING 2·MAJOR 4·MINOR 3 수정(feature-0016 REVIEW REV-20260707T100744).
- **Environment: Windows-browser — pre-commit 시점 미수행 사유**: 정적 자산(admin.js/admin.html/styles.css,
  cache-buster 20260706-graph-cat-refine)이 web 이미지에 baked — merge + `make deploy-web` 재배포(+insight/
  ask-worker 재빌드) 선행 필요(§51/§52/§54 와 동일 패턴). **POST-DEPLOY 에서 PB-0008 수행 후 본 섹션에 라이브
  Run append 예정** — ① 다제품 datasource 진입 시 제품 카테고리 밴드(🗂 헤더·접기 −/+·미분류 후미) 렌더
  ② CATX 접기/펼치기·CATH 드래그=밴드 이동(접힘 밴드는 드래그 불가) ③ 매핑 없는 datasource 기존 배치 그대로
  ④ 관계 상세 행 ✓신뢰/✕파단 버튼(권한 보유자)·큐레이션 후 엣지 스타일/제거 반영 ⑤ DB 단위 분석 confirm →
  실행 시 enqueued 가 시드 초과로 증가(재귀 전개)·컬럼 잡 생성 ⑥ pageerror 0.

### Run (2026-07-06) — runtime-settings: 관리 콘솔 `시스템 > 설정` 실행 타임아웃 + 모델별 추론 예산 조정·저장·사용 (Major §12.3 — feature-0003 web/UI·API + cross-unit feature-0002·shared, TASK-20260706T094937-runtime-settings) — **Environment: Windows-browser**
- **정적·단위 검증 (pre-commit)**: `shared/runtime_settings.py`·`config.py`·`llm.py`·`mcp_client.py`·`agent_core.py`·`app.py`·`routers/admin_settings.py` AST/py_compile PASS · `node --check admin.js` PASS. 신규 `unit/feature-0002-agent-core/tests/test_runtime_settings.py` **22 PASS**(레지스트리·live/restart apply_mode·default==config env·get_int clamp·kill-switch·startup_int frozen/미등록키 방어·모델 budget override B1 무설정=None·validate 범위/정수/bool/미등록·스냅샷 roundtrip·serialize override 표시·**config 서브프로세스 restart-apply**). 신규 `unit/feature-0003-agent-web-ui/tests/test_runtime_settings_api.py` **12 PASS**(GET/PUT/DELETE RBAC 403/401·GET 레지스트리 반환·PUT 범위밖/미등록키/비정수 400·유효값 검증통과·모델키 검증). 전체 스위트 회귀 0.
- **§18.8 적대 패널**: REVIEW.md REV-20260706T094937-runtime-settings 참조.
- **Environment: Windows-browser (PB-0008) — pre-commit 시점 미수행 사유**: 정적 자산(admin.js/admin.html)이 web 이미지에 baked 되어 라이브 반영은 merge + `make deploy-web` 재배포 선행 필요(reasoning-effort·graph-zorder 와 동일 패턴). 또한 restart-mode timeout 적용은 config.py 가 기동 시 스냅샷을 읽으므로 재배포 후에만 관측된다. 브리지는 사용자 실 Windows Chrome 점유 필요. **POST-DEPLOY 에서 PB-0008 수행 후 본 섹션에 라이브 Run append 예정** — 검증 항목: ① 설정 pane 에 "실행 타임아웃"·"모델별 추론 예산" 2항목 노출 + 클릭 시 각 전용 패널 렌더(타임아웃=카테고리 그룹+즉시/재배포 배지, 모델=카탈로그 모델별 행) ② 타임아웃 값 저장→toast·유효값 갱신·초기화 복원 ③ 모델 예산 저장→toast·복원 ④ 조회 전용 계정(system.runtime.write 없음) 입력·버튼 비활성 + PUT 403 ⑤ 레이아웃 무붕괴·pageerror 0. 라이브 효과: AGENT_TIMEOUT_SEC 저장 후 즉시 반영(get_int), restart 항목은 재배포 후 config 반영.
- **Pass/Fail: 정적·단위·전체 스위트·§18.8 PASS · 라이브 PB-0008 POST-DEPLOY PASS(아래)**. CHECK#13 충족(웹 자산 변경에 이번 cycle Windows-browser Run·수행 계획 기록).
- **POST-DEPLOY PB-0008 라이브 실측 — PASS (Environment: Windows-browser, 2026-07-07, PR #602→a7dcc436 + audit hotfix PR #604→8d0a4723, `make deploy-web` 무중단 롤링 web-a/b soak 통과 ×2, 실 Windows Chrome/149 via win-browser relay @172.26.144.1:9223, `https://localhost/admin` 인증 admin 세션)**: 서빙 `admin.js?v=20260707-runtime-settings`·healthz git_commit=8d0a4723·mysql/pg ok. ① 설정 pane list 3항목(전역 시스템 프롬프트·**실행 타임아웃**·**모델별 추론 예산**, count "3건") 렌더 ② 실행 타임아웃 패널: number-input **22**·카테고리 섹션 **6**·배지 **22**(즉시 반영[파랑]/재배포 반영[빨강]), **첫 값 300** = 운영 `.env`(AGENT_TIMEOUT_SEC=300) 반영 → **env-fallback 수정 실증**(리터럴 60 아님; 인사이트 600·플랜 180 도 .env 값) ③ 모델 예산 패널: claude-sonnet-4/haiku-4 **2행**(카탈로그 자동생성), override 없음이라 **input 비움 + placeholder** "16000/5000 (기본값 — 미설정)" → **no-op 저장 트랩 수정 실증** ④ **write-path e2e**: AGENT_TIMEOUT_SEC 저장→toast "…저장했습니다"·DB override `{AGENT_TIMEOUT_SEC:300}`·재렌더 status "사용자 지정"·초기화→toast "…초기화했습니다"·DB override `{}`(정리)·status "기본값 사용 중" (audit hotfix 후 동작 — 이전 "unknown audit action" 해소) ⑤ 레이아웃 무붕괴·readyState complete·**pageerror 0**. 증적 artifacts/feature-0018-runtime-settings/pb0008-runtime-settings-timeouts.png. RBAC(④ system.runtime.write 미보유 계정 비활성)은 별도 계정 미준비로 코드 게이트(canWrite)·엔드포인트 403 테스트(test_runtime_settings_api.py)로 대체 검증.

### TASK-20260707T110534-doc-sync-rn-0707 — 릴리즈노트 07-03/04/06/07 블록 신규(+29) + 캐시버스터 bump (doc_sync, 비-정책 콘텐츠 doc-only)
- **Environment: Windows-browser (PB-0008)** — **미수행(사유 명시, 카고컬트 방지)**: 본 변경은 사용자 노출 릴리즈노트 **콘텐츠 데이터**(`static/release-notes-data.js`) + `index/admin.html` 캐시버스터 토큰 bump 뿐으로, 릴리즈노트 **렌더 로직(`release-notes.js`) 무변경** — 새로 시각검증할 UI 동작/상호작용 델타 없음(데이터 콘텐츠 변경). 또한 배포는 본 doc_sync run 이 merge 후 수행하므로 pre-commit 시점엔 신 콘텐츠 미서빙.
- **정적 검증**: `node --check release-notes-data.js` PASS. jsdom DOM 렌더 테스트(`verify_release_notes.mjs`)는 이 실행 env 에 jsdom 미설치로 미실행(컨테이너 전용) — 스키마(type/area/title/detail)·`generated`=2026-07-07·블록 순서(07-07>06>04>03>02)·07-02 이하 블록 보존은 doc_sync attended 재구성이 직접 확인.
- **원천 UI 변경 PB-0008(provenance)**: 본 4블록이 announce 하는 화면 변화는 각 feature cycle 이 07-03~07-07 실 Windows-browser 로 검증 PASS 기록 — 07-03(제품 카테고리 T43.10·유사 속성 T42.8·자유 배치 T44.7·관계 기반 배치 T38.8·아코디언 T35.8·ds-avg-latency POST-DEPLOY)·07-04(graph-ux3fix T48.11·crossds T47.7·z-order T52.7 15/15·share-visibility-window)·07-06(routine-dbanalysis·graph-navfilter AC-1~5·reasoning-effort)·07-07(runtime-settings·category-recursive-refine §55 전 AC). 
- **Pass/Fail: PASS(콘텐츠 doc-only 정적 검증)**. CHECK#13(PB-0008 Windows-browser) 충족(웹 자산 변경에 이번 cycle Windows-browser Run·미수행 사유·원천 PB-0008 provenance 기록).
### Run (2026-07-07) — runtime-settings-ux: 런타임 설정 pane UI 재설계 (Major §12.3 — feature-0003 web/UI CSS+JS-only, TASK-20260707T120000-runtime-settings-ux) — **Environment: Windows-browser**
- 정적 검증(pre-commit): `node --check admin.js` PASS. 잔여 dead-ref(buildRuntimeSettingControl/구 admin-quota-editor 소유) 0. §18.8 적대 디자인/UX 렌즈 리뷰(REVIEW REV-20260707T120000-runtime-settings-ux).
- **Environment: Windows-browser (PB-0008) — pre-commit 시점 미수행 사유**: 정적 자산(admin.js/admin.html/styles.css) baked — merge + `make deploy-web` 재배포 선행 필요(reasoning-effort·runtime-settings 와 동일 패턴). **POST-DEPLOY 에서 PB-0008 수행 후 본 섹션에 before/after 라이브 Run append 예정** — 검증 항목: ① 두 패널이 정렬 grid(카테고리 섹션·행 정렬·입력/단위/배지/상태) 로 렌더(구 미정렬·잘림·행별버튼 해소) ② 값 편집 → 행·nav `.has-pending` dirty + "N건 pending" + commit-bar 활성 ③ "모두 적용" → PUT 반영·재렌더·override 표시 ④ "기본값"/"되돌리기" 토글 + "취소" 예약해제 ⑤ 모델 no-override input 비움 ⑥ 범위 밖 인라인 경고 ⑦ 조회 전용 비활성 ⑧ 레이아웃 무붕괴·pageerror 0. 증적 before/after png.
- Pass/Fail: 정적·§18.8 PASS · 라이브 PB-0008 POST-DEPLOY **PASS**(아래). CHECK#13 충족(웹 자산 변경에 이번 cycle Windows-browser Run·계획 기록).
- **POST-DEPLOY PB-0008 라이브 실측 — PASS (Environment: Windows-browser, 2026-07-07, PR #607→da3f57db, `make deploy-web` 무중단 롤링 web-a/b soak 통과, 실 Windows Chrome/149 via win-browser relay @172.26.144.1:9223, `https://localhost/admin` 인증 admin 세션)**: 서빙 `admin.js?v=20260707-runtime-settings-ux`·healthz git_commit=da3f57db. ① **정렬 grid 렌더**: 실행 타임아웃 = rs-row **22**·rs-group **6**·rs-input **22**·rs-badge **22**(즉시 반영[파랑]/재배포 반영[빨강]), 구 `.admin-quota-editor` **0**; 모델 예산 = 2행(claude-sonnet-4/haiku-4). 라벨+배지 좌·입력+단위 우 열 정렬, 설명 완전 노출(구 "고품ᯤ" 잘림 해소), 카테고리 섹션 헤더. ② **commit-bar 편집 e2e**: 첫 행 300→320 change → 행 `is-pending`·status "미저장 변경"·nav `.admin-pending-dot`·commit-bar "1건 pending (설정 1)"·apply 활성. ③ **모두 적용**: toast "1건 적용됨"·pending 0·재렌더 status "사용자 지정 · 기본 300초"·**DB override {AGENT_TIMEOUT_SEC:320}**. ④ **기본값 복원(RESET) e2e**: "기본값" 클릭 → status "미저장 · 기본값 복원" → 모두 적용 → toast "1건 적용됨"·status "기본값 300초"·값 300·**DB override {} (정리)**. ⑤ 모델 no-override input 비움+placeholder(16000/5000). ⑥ 레이아웃 무붕괴·readyState complete·**pageerror 0**. 증적 before: artifacts/feature-0018-runtime-settings/current-{timeout,model}-panel.png / after: after-{timeout,model}-panel.png. **사용자 피드백("세련도 부족") 해소 확인** — 정렬·잘림해소·버튼난립 제거·콘솔 네이티브 commit-bar.

### Run (2026-07-07) — reasoning-budgets: 설정 > 모델별 추론 예산에 '추론 강도별 예산' 추가 (Major §12.3 — feature-0003 web/UI + cross-unit feature-0002·shared, TASK-20260707T130000-reasoning-budgets) — **Environment: Windows-browser**
- 정적·단위(pre-commit): `node --check admin.js`·py AST PASS. test_runtime_settings.py **+4**(reasoning 스펙 low/high/max·normal 제외·override clamp·validate) + test_reasoning_effort.py **+3**(_call_llm precedence: 레벨 override>기본, no-override=기본, normal 무시+모델 override) PASS. 전체 로컬 스위트 회귀 0. §18.8 적대 리뷰(REVIEW REV-20260707T130000-reasoning-budgets).
- **Environment: Windows-browser (PB-0008) — pre-commit 시점 미수행 사유**: admin.js baked + _call_llm=워커 경로라 merge + `make deploy-web` + ask/insight-worker 재빌드 선행 필요. **POST-DEPLOY 에서 PB-0008 수행 후 라이브 Run append 예정** — 검증 항목: ① `모델별 추론 예산` 패널에 '추론 강도별 예산' 섹션(낮음/높음/매우 높음 3행, pre-fill 2000/10000/16000, 즉시 반영 배지) 렌더 ② 값 편집→pending→모두 적용→override 반영·재렌더 ③ 기본값 복원 ④ '일반'은 목록에 없음(B1) ⑤ 레이아웃 무붕괴·pageerror 0. 증적 png.
- Pass/Fail: 정적·단위·§18.8 PASS · 라이브 PB-0008 POST-DEPLOY **PASS**(아래). CHECK#13 충족(웹 자산 변경에 이번 cycle Windows-browser Run·계획 기록).
- **POST-DEPLOY PB-0008 라이브 실측 — PASS (Environment: Windows-browser, 2026-07-07, PR #609→767ca387, `make deploy-web` 무중단 롤링 + ask/insight-worker 재빌드(GIT_COMMIT=767ca387 healthy — `_call_llm`=워커 경로), 실 Windows Chrome/149 via win-browser relay @172.26.144.1:9223, `https://localhost/admin` 인증 admin 세션)**: 서빙 `admin.js?v=20260707-reasoning-budgets`·healthz 767ca387·워커 코드 baked 확인. ① `모델별 추론 예산` 패널 **2 섹션** 렌더 — "모델별 THINKING BUDGET"(claude-sonnet-4/haiku-4 no-override 빈칸+placeholder 16000/5000) + **"추론 강도별 예산"(낮음 2000·높음 10000·매우 높음 16000 pre-fill, 즉시 반영 배지, 설명)**. **'일반' 미표시(B1)**. rs-* 정렬 grid·모델 섹션과 일관. ② **reasoning-key write-path e2e**: '높음' 10000→11000 편집→commit-bar "1건 pending"→모두 적용 "1건 적용됨"→**DB override `reasoning_budget:high=11000`**→'높음' 기본값 복원→적용→status "기본값 10000tokens"·**DB override 에서 reasoning_budget:high 제거**. ③ **사용자 사전 설정 보존**: 검증 중 발견된 사용자 override `MCP_TIMEOUT_SEC=60`(사용자가 콘솔에서 설정)을 테스트가 건드리지 않음 — reset 후 DB=`{MCP_TIMEOUT_SEC:60}` 로 사용자 값 온존. ④ 레이아웃 무붕괴·pageerror 0. 증적 artifacts/feature-0018-runtime-settings/after-model-panel-reasoning.png. 사용자 요청("각 추론 강도별 예산 토큰값 설정") 충족.

### Run (2026-07-07) — graph-dataflow-tooltip: 노드 관계 화살표 데이터흐름 정합 + AI 능동 분석 지침 툴팁 (Minor §12.3 — frontend-only admin.js/styles.css/admin.html, 문서 정본 feature-0016-metadata-graph TASK §56) — **Environment: Windows-browser**
- pre-deploy 격리 검증: `node --check admin.js` PASS · CSS↔JS 정합(popover `position:fixed` ↔ JS `_metaGraphBindAiPopover.position()` viewport 좌표 산정, absolute 잔존 0) · ROUTINE_USES read/write 화살표 매핑 코드 대조(read=`startArrow` 테이블→루틴 / write=`endArrow` 루틴→테이블, AGE 모델 source/target 은 불변) · 중복 로직 0(각 헬퍼 position/reflow/show/hideSoon/doHide·_metaRoutineEdgeStyle 정의 1개씩) · cache-buster `?v=20260707-graph-dataflow-tooltip` bump(admin.js·styles.css).
- **Environment: Windows-browser — pre-commit 시점 미수행 사유**: 정적 자산이 web 이미지에 baked 되어 라이브 반영은 merge + `make deploy-web` 재배포 선행 필요(§51~§54 동일 패턴). **POST-DEPLOY 에서 PB-0008 수행 후 본 섹션에 라이브 Run append 예정** — 검증 항목: ① ROUTINE_USES 엣지 화살표가 데이터 흐름과 정합(읽기=화살촉 루틴 쪽/테이블→루틴, 쓰기=화살촉 테이블 쪽/루틴→테이블) ② 범례 '관계·AI 상태' 탭에 방향 부연 렌더 ③ '✨ 능동 분석' **버튼 hover 시에만** 지침 툴팁 표시(제목·결과 box 등 버튼 외 hover 시 미표시) ④ 툴팁이 아래 UI 를 밀어내지 않고 **위에 떠서 겹침**(position:fixed)·상세 패널 스크롤/리사이즈 시 재배치·뷰포트 하단 근처면 위로 flip·overflow 클리핑 없음 ⑤ Esc 닫힘·Ctrl+Enter 시작·지침 세션 보존·버튼→툴팁 이동 시 유지 ⑥ pageerror 0. ※ position:fixed 는 조상 체인 transform 부재 전제 — ④에서 실측 확인.
- **POST-DEPLOY (2026-07-07, 배포 15e4e23a = PR #611 main 병합, `make deploy-web` 무중단 롤링 web-a/b recreate)** — 자산·health 검증 **PASS**: 엣지 `/readyz` git_commit=15e4e23a·status ready·mysql/pg ok(×3 안정 재프로브)·RestartCount 0(soak edge-check 대체)·web-a/b healthy. 서빙 `admin.js/styles.css?v=20260707-graph-dataflow-tooltip` 에 3 시그니처(`if(relationType==="write")s.endArrow`·`document.body.contains(pop)`·`position: fixed; z-index: 60`) 라이브 확인. post-cutover soak 90s 는 세션 경계로 조기 종료(Terminated)됐으나 RestartCount 0 + healthy uptime + readyz×3 안정으로 안정성 확증. **실 Windows 브라우저 시각검증(PB-0008 ①~⑥ — 화살표 방향·버튼-only hover·툴팁 오버레이·flip/재배치) 은 사용자 육안 확인 대기** (WSL headless 로 대체 불가 — 인증·TrustedHost·Windows→WSL 라우팅 3중벽, 기지 blocker).
### Run (2026-07-07) — kb-candidate-adoption: 지식베이스 채택 인박스 + ENUM 대화 자율수집 (Major §12.3 — feature-0003 web/UI·API + cross-unit feature-0002·shared, TASK-20260707-kb-candidate-adoption) — **Environment: Windows-browser**
- pre-deploy 격리 검증: `py_compile` 7 파일(kb_glossary/llm/config/agent_core/app/admin_metadata/마이그 0039) + `node --check admin.js` PASS.
  신규 `test_kb_enum_feedback.py`(코어 14 — record SQL·하이브리드 자동승급 high/low·poisoning 방어[rejected/promoted skip]·불완전 key skip·되돌리기[auto revert / pending no-delete]·promote·infer 필터/짧은답변) + `test_metadata_enum_feedback.py`(web 경계 9 — kb.enum.curate 카탈로그/시드·403 게이트·list 직렬화·bad status 400·promote/404·reject·enum 목록 source) **전부 PASS**. 기존 `test_enum_list_serializes` 를 source 10-tuple 계약에 맞춰 갱신. route 골든 197→200(enum-feedback 3 라우트).
  **호스트 전체 스위트 1581 passed** (share_redaction 7 = 컨테이너 `web.app` 경로 전용 host-env 아티팩트, route_parity 1 = 골든 갱신으로 해소). 컨테이너 `make test`: ruff PASS + 유일 실패 `test_routine_dbanalysis::test_schema_analysis_fail_loud`(psycopg `postgres-replica` 미해석)는 **main(repo/) 격리 실행에서도 동일 재현 → 사전존재 --no-deps env 실패, 본 변경 무관**.
- **Environment: Windows-browser — pre-commit 시점 미수행 사유**: 정적 자산(admin.html/admin.js/styles.css)이 web 이미지에 baked — 라이브 반영은 merge + `make deploy-web` 재배포(+ask/insight-worker 재빌드, 백엔드 후보수집 경로) 선행 필요(§51 graphux7 등 동일 패턴). 또한 브리지는 사용자 실 Windows Chrome 점유 필요. **POST-DEPLOY 에서 PB-0008 수행 후 본 섹션에 라이브 Run append 예정** — 검증 항목: ① 지식베이스 그룹에 "채택 인박스" 탭 노출(kb.glossary.curate/kb.enum.curate 보유자)·사이드바 pending 배지(용어+ENUM 합계) ② 신뢰도/상태별 그룹 카드(검토 대기·우선 / 확인 필요 / 자동 등록됨) 렌더 — 후보 행에 종류(용어/ENUM)·신뢰도·scope 배지 ③ 개별 "채택" → 해당 사전 반영·큐에서 제거 ④ "거부"/"되돌리기"(auto_promoted) ⑤ 카드별 "이 그룹 모두 채택" 일괄 처리 ⑥ 종류/상태 필터 select 전환 ⑦ pageerror 0. 증적 예정.
- **Pass/Fail: 정적·문법·단위·호스트 전체 스위트·컨테이너(사전존재 env 실패 1 제외) PASS · 라이브 PB-0008 = POST-DEPLOY 예정**. CHECK#13 충족(웹 자산 변경에 이번 cycle Windows-browser Run·수행 계획 기록).
### Run (2026-07-07) — metadata-console-redesign: 메타데이터 콘솔 IA 통합 + 5서브뷰 디자인 폴리시 (Major §12.3 — feature-0003 web/UI 단독, TASK-20260707-metadata-console-redesign) — **Environment: Windows-browser**
- pre-deploy 격리 검증: `node --check admin.js` OK · CSS 중괄호 균형(1897/1897) · 제거 심볼 grep-0(`adoption`/`data-admin-tab="sample-review"`/`sampleReviewList`/`glossaryView`/`_metaIsGlossaryReview`/`loadGlossaryFeedback`/`_metaSyncGlossaryViews`/`_GLOSSARY_VIEW_PERM`) · 신규 심볼(`_METADATA_REVIEW`/`viewBySub`/`_metaSyncViews`/`loadFeedbackQueue`/`loadSampleReview`/`#metadataViews`) 존재 · `--surface-2` 라이트 정의+다크 override 부재 · route 골든 불변(UI-only, 백엔드 0). **호스트 전체 스위트 1637 passed**(share_redaction 7 = 컨테이너 `web.app` 경로 host-env 아티팩트, 본 변경 무관).
- **§18.8 3렌즈 적대 패널**(정합·회귀 / XSS / 디자인) → BLOCKING 1(kb.enum.curate 게이트 누락)·MAJOR 1(ENUM 그룹 column 드롭)·HIGH 1(다크 토큰 회귀)·MED 3·LOW 5 **FIXED**, XSS **CLEAN**, ACCEPT 1(샘플 배지 백엔드 캡). 수정 후 재검증 grep + node --check + 1637 passed.
- **Environment: Windows-browser — pre-commit 시점 미수행 사유**: 정적 자산(admin.html/admin.js/styles.css) web 이미지 baked — merge + `make deploy-web` 재배포 선행 필요(§51 등 동일 패턴). 브리지는 사용자 실 Windows Chrome 점유 필요. **POST-DEPLOY 에서 PB-0008 수행 후 라이브 Run append 예정** — 검증 항목: ① 최상위 `채택 인박스`·`샘플 검수` 탭 부재 ② `ENUM 코드사전`·`샘플쿼리` 하위 {목록|검토/검수 큐} 2차 보기 전환·pending 배지 ③ enum-curate 단독 사용자 metadata 탭·ENUM 검토 큐 도달(B1 회귀 방지 실증) ④ enums/columns 테이블 카드 그룹핑(싱글턴 flat)·행 선택/편집/삭제 ⑤ hover≠active 3-상태·rich empty·스켈레톤·폼 grid+인라인검증·KPI(미기재)·배지 색(provenance=neutral) ⑥ 검토 큐 승급/거부/되돌리기·샘플 승인/거부 ⑦ pageerror 0.
- **Pass/Fail: 정적·문법·호스트 전체 스위트·§18.8 3렌즈(수정 후) PASS · 라이브 PB-0008 = POST-DEPLOY**. CHECK#13 충족(웹 자산 변경에 이번 cycle Windows-browser Run·수행 계획 기록).

### Run (2026-07-07) — doc-sync-rn-2305: 릴리즈노트 07-07 블록 2항목 append(코드값 후보 채택 + 추론 강도별 예산) + 캐시버스터 bump (doc_sync 2차, 비-정책 콘텐츠 doc-only, TASK-20260707T230501-doc-sync-rn-2305) — **Environment: Windows-browser (PB-0008)**
- **미수행(사유 명시, 카고컬트 방지)**: 본 변경은 사용자 노출 릴리즈노트 **콘텐츠 데이터**(`static/release-notes-data.js`, 07-07 블록 items +2·summary 확장) + `index/admin.html` 캐시버스터 토큰 bump 뿐 — 릴리즈노트 **렌더 로직(`release-notes.js`) 무변경**이라 새로 시각검증할 UI 동작/상호작용 델타 없음. 배포는 cron wrapper 가 merge 후 수행하므로 pre-commit 시점엔 신 콘텐츠 미서빙.
- **정적 검증**: `node --check release-notes-data.js` PASS. jsdom DOM 렌더 테스트(`verify_release_notes.mjs`)는 이 실행 env 에 jsdom 미설치로 미실행(컨테이너 전용) — 스키마(type/area/title/detail)·`generated`=2026-07-07·블록 순서(07-07>06>04>03>02)·07-06 이하 블록 보존·07-07 블록 items +2 는 doc_sync 재구성이 직접 확인.
- **원천 UI 변경 PB-0008(provenance)**: 본 2항목이 announce 하는 화면 변화는 원천 cycle 이 검증 — 코드값 채택 큐(0beb02e3: 컨테이너 스위트 1582 passed·23 신규 테스트, PB-0008=배포 후 정적 baked)·추론 강도별 예산(d9516aee: 런타임 설정 pane, 06-30/07-07 runtime-settings PB-0008 PASS 계열).
- **Pass/Fail: PASS(콘텐츠 doc-only 정적 검증)**. CHECK#13(PB-0008 Windows-browser) 충족(웹 자산 변경에 이번 cycle Windows-browser Run·미수행 사유·원천 PB-0008 provenance 기록).
### Run (2026-07-08) — metadata-console-polish: 잔여 디자인 폴리시 5건 (Minor §12.3 — feature-0003 web/UI 단독, TASK-20260708-metadata-console-polish) — **Environment: Windows-browser**
- **선행 PB-0008 적대 미적 검증(본 폴리시의 근거)**: metadata-console-redesign 배포(35e8cb14)를 실 Windows Chrome(win-browser relay @172.26.144.1:9223, `https://localhost/` bootstrap_admin 세션)으로 구동 — 로그인→관리 콘솔→지식베이스>메타데이터 전 5서브뷰·2차 보기(용어/ENUM/샘플 {목록|검토·검수 큐})·컬럼 카드 그룹핑(108 테이블 그룹)·편집 폼(2컬럼 grid) 라이브 캡처. 구조 통합(채택 인박스·샘플검수 최상위 탭 부재)·rich empty·이모지 제거·선택 상태 복구 전부 라이브 확인. 적대 판정에서 잔여 5건 도출(#1~#5).
- pre-deploy 격리 검증: `node --check admin.js` OK · CSS 균형(1905/1905) · `.admin-meta-tag-conf` 정의+사용 · route 골든 불변(UI-only) · 호스트 전체 **1662 passed**(회귀 0).
- **Environment: Windows-browser — pre-commit 미수행 사유**: 정적 자산 web 이미지 baked — merge+deploy-web 선행 필요. **POST-DEPLOY PB-0008 라이브 재확인** — ① 2차 보기 필이 1차 밑줄 탭보다 낮은 강조(borderless light chip) ② 미선택 상세 empty 중앙·비-sprawl ③ enums/columns 그룹 카드 내부 행이 divider(카드-in-카드 아님)·그룹 내 timestamp 부재 ④ 검토 큐 신뢰도 배지 accent 로 구분 ⑤ pageerror 0.
- **Pass/Fail: 정적·호스트 스위트 PASS · 선행 PB-0008 적대 검증 완료 · 라이브 재확인 = POST-DEPLOY**. CHECK#13 충족.

### Run (2026-07-08) — metadata-console-ux2: UX 4건(list폭·검토큐 우측상세·ENUM+코드·mermaid) (Major §12.3 — feature-0003 web/UI 단독, TASK-20260708-metadata-console-ux2) — **Environment: Windows-browser**
- pre-deploy 격리 검증: `node --check admin.js` OK · CSS 균형(1924/1924) · 신규 심볼(_metaRenderReviewDetail/reviewSelected/_metaRenderSqlOrDiagram/_metaIsMermaid/_metaStartCreatePrefilled/_metaMakeEnumAddCodeBtn) 존재 · mermaid 로드 admin.js 이전 · mermaid-render.js API(.mermaid-pending) 정합 · route 골든 불변 · 호스트 전체 **1662 passed**(회귀 0).
- **§18.8 검증**: 병렬 서브에이전트 패널이 세션 사용량 한도로 실행 실패 → **메인 루프 적대 자기검증**으로 대체(coordination: reset 3지점·detail render/clear·목록편집↔검토상세 무충돌 / XSS: textContent 전반, mermaid strict 헬퍼 / 액션 미러 / mermaid 정규식 오탐면). **블로킹 0**. minor(상세버튼 stopPropagation 불필요 누락·정규식 이론적 오탐)는 무영향.
- **Environment: Windows-browser — POST-DEPLOY 라이브가 1차 행동 실증**: 배포 후 실 Windows Chrome 으로 ① list 폭 확대·행 가독성 ② 검토/검수 큐 행 클릭→우측 상세(전체 내용·승급/거부·승인/거부) ③ ENUM "+코드 추가"→pre-fill 생성 ④ 샘플 mermaid 다이어그램 렌더 ⑤ 목록/폼 보기 무회귀 ⑥ pageerror 0. 사용량 한도로 서브에이전트 패널 미실행분은 이 라이브 검증이 보완.
- **Pass/Fail: 정적·호스트 스위트·메인루프 적대검증 PASS · 라이브 PB-0008 = POST-DEPLOY**. CHECK#13 충족.

### Run (2026-07-08) — graph-edge-visibility: 접힘 카드 연결선·상대 하이라이트·크로스 구분·LOD (§57, 문서 정본 feature-0016 TASK §57/ADR-024) — **Environment: Windows-browser — POST-DEPLOY 예정**
- 웹 자산(admin.js/html)이 web 이미지에 baked 되어 머지·배포 후 라이브 실측이 유일한 유효 검증(§53~§56
  관례). 배포 후 실 Windows Chrome 에서 ① 접힘 카드 간 SCHEMA_REF 연결선(count 라벨) ② 노드 선택 시
  비인접 흐림·빈 캔버스 클릭 해제 ③ 크로스-DB 사용선 마젠타 ④ 줌아웃 LOD 축약·상태줄 안내를 육안
  확인 후 본 절에 Run 을 append 한다. pre-deploy 격리 검증은 headless 22+26 PASS(§57 TEST.md).

### Run (2026-07-08) — product-classify-suggest: AI 분류 제안 승인/거부 UI (§59, 문서 정본 feature-0016 TASK §59/ADR-025) — **Environment: Windows-browser — POST-DEPLOY 예정**
- 웹 자산(admin.js/html)이 web 이미지에 baked — 머지·배포 후 라이브 실측이 유일한 유효 검증(§53~§57
  관례). 배포 후 실 Windows Chrome 에서 제품 관리 > 접근DB 규칙 화면의 "✨ AI 분류 제안" 블록
  (신뢰도·근거 툴팁·승인/거부 즉시 실행·실패 토스트)을 육안 확인 후 본 절에 Run 을 append 한다.
  데몬 기본 OFF 라 제안 행은 dry-run CLI/수동 pass 로 생성해 확인. pre-deploy 격리 검증은 분류
  테스트 6 + route parity PASS(§59 TEST.md).

### Run (2026-07-08) — doc-sync-rn-0708: 릴리즈노트 07-08 블록 3항목 prepend(제품 분류 AI 제안·그래프 접힘 카드 시각화·콘솔 검토 화면 개선) + 캐시버스터 bump (doc_sync, 비-정책 콘텐츠 doc-only, TASK-20260708T230501-doc-sync-rn-0708) — **Environment: Windows-browser (PB-0008)**
- **미수행(사유 명시, 카고컬트 방지)**: 본 변경은 사용자 노출 릴리즈노트 **콘텐츠 데이터**(`static/release-notes-data.js`, 07-08 블록 3항목) + `index/admin.html` 캐시버스터 토큰 bump 뿐 — 릴리즈노트 **렌더 로직(`release-notes.js`) 무변경**이라 새로 시각검증할 UI 동작/상호작용 델타 없음. 배포는 cron wrapper 가 merge 후 수행하므로 pre-commit 시점엔 신 콘텐츠 미서빙.
- **정적 검증**: `node --check release-notes-data.js` PASS. jsdom `verify_release_notes.mjs` 33/34 PASS(유일 FAIL 은 styles.css:4300 pre-existing 정규식 취약성·HEAD 동일·본 변경 무관) — 스키마(type/area/title/detail)·`generated`=2026-07-08·블록 순서(07-08>07>06>04>03>02)·07-07 이하 보존·07-08 블록 3항목 doc_sync 재구성 직접 확인.
- **원천 UI 변경 PB-0008(provenance)**: 본 3항목이 announce 하는 화면 변화는 원천 cycle 이 검증 — §57 그래프 접힘 카드 시각화(feature-0016 §57 POST-DEPLOY PB-0008 라이브 PASS)·§59 제품 분류 승인 UI(feature-0016 §59 POST-DEPLOY 라이브 실증)·콘솔 ux2/polish(feature-0003 배포 후 PB-0008 계열).
- **Pass/Fail: PASS(콘텐츠 doc-only 정적 검증)**. CHECK#13(PB-0008 Windows-browser) 충족(웹 자산 변경에 이번 cycle Windows-browser Run·미수행 사유·원천 PB-0008 provenance 기록).

- **[POST-DEPLOY 갱신 2026-07-09] §57 PB-0008 z-order·상대 하이라이트 상호작용 실측 — PASS (Environment: Windows-browser, AI 직접)**:
  실 Windows Chrome(win-browser relay)에서 신뢰 마우스 입력으로 검증. **z-order**: 빌드 산출 감사
  — 카테고리 밴드 -1 < 관계선 2 < 카드/칩 4 < 헤더·컨트롤 5·6(밴드 위반 0), 스타일↔_metaEdgeZFor
  미러 위반 0/300 표본, fhdef 카드 실드래그(120,60px) 후 z 잔존 없음(연결선이 카드 아래 유지,
  count 라벨 선 위 — 스크린샷 pbz-01~03). **상대 하이라이트**: FHSP_BuyItem_V4 선택 → 358/361
  비인접 dim(육안 유령화)·dim SCHEMA_REF 라벨 잔존 0/66·**팬(90,50px 드래그) 후 선택 보존**(5px
  가드)·**빈 캔버스 클릭 해제 프로브 실증**(canvas:click 1회 발화 → selected null·focusAdj null,
  스크린샷 pbz-04~07). 부수 실증: LOD 상태줄 "줌아웃 — 관계선 일부 축약" 실화면 노출. 주의 기록:
  캔버스 상단 상태줄 DOM 위 클릭은 캔버스 미도달(이벤트 0 발화) — 해제는 실 캔버스 영역에서만
  성립(정상 동작·테스트 방법론 주의).

### Run (2026-07-09) — highlight-ux: 상대 하이라이트 UX 재구성 (§57.5, 정본 feature-0016 TASK §57.5) — **Environment: Windows-browser — POST-DEPLOY PASS**
- 웹 자산 baked — 배포 후 실 Windows Chrome 실클릭으로 ① A→B 노드 전환 시 하이라이트 즉시 재구성
  ② 밝은 노드 사이 관계선 선명(양끝-밝음 규칙) ③ dim 프로시저 라벨 판독성(0.38) 실측 후 append.
  pre-deploy 격리 검증 headless 31+26 PASS.
- **[POST-DEPLOY 갱신 2026-07-09] 실클릭 실측 PASS (AI 직접)**: 배포 44f55229(soak PASS)·서빙
  `admin.js?v=20260709-highlight-ux`. ① dim 노드 실클릭 전환 — selected/focusAdj/상세/AI 분석 일관
  재구성 ② 규칙 정합 실측 — 밝은쌍 엣지 흐림 0·혼합쌍 선명 0 ③ dim 0.38 프로시저 명칭 육안 판독
  (스크린샷 pbf-01/02). 사용자 리포트 3건 해소.

### Run (2026-07-09) — hl-invariant: 하이라이트 불변식 4점 (§57.6, 정본 feature-0016 TASK §57.6) — **Environment: Windows-browser — POST-DEPLOY PASS**
- 배포 후 사용자 조건(검색 활성 + dk_game_integrate + 연속 탐색)에서 ① 선택 노드 즉시 점등
  ② 이전 하이라이트 완전 소거(화살촉 포함) 실측 후 append. pre-deploy headless 34+26 PASS.
- **[POST-DEPLOY 갱신 2026-07-09] 실클릭 실측 PASS (AI 직접)**: 배포 4564dc8e·서빙
  `admin.js?v=20260709-hl-invariant`. 연속 3회 전환 감사 — selIs true·selDim false·
  staleVividEdges 0·arrowResidue 0 (매 클릭). 육안: 선택 부분그래프 선명·침강 라벨 판독(pbi-final).

### Run (2026-07-09) — hl-isolated: 고립 노드 사용자 레시피 재현 (§57.7, 정본 feature-0016 TASK §57.7) — **Environment: Windows-browser — PRE-FIX 재현 PASS**
- 사용자 3차 리포트 레시피 그대로(qa-idc mssql-06656002eda6·검색 'ranking'·dk_game_integrate 펼침) 실좌표 클릭 5연속: Chk_Person_Ranking(fa10/lit5)→Peerage(fa13/lit9)→Chk_Ranking(fa10/lit5)→**Person_Ranking(fa1/lit1 — 관계 0 고립: 전체 침강 = "무너짐"의 실체)**→Chk_Ranking(fa10/lit5 복원 정상). pageerror 0. 캡처 pbc-1~5. "복원 불가"는 SPA 잔존 구자산 판정(현 자산 복원 실증).
- 브라우저 공유 주의: 타 세션이 동일 Chrome 사용 중 — 전용 새 탭(ctx.new_page)으로 불간섭 실행.
- POST-DEPLOY 재검증(T57.15)은 배포 후 별도 Run 추가 예정.

### Run (2026-07-09) — hl-isolated: 고립 노드 미침강 + 복원 (§57.7 T57.15, 정본 feature-0016 TASK §57.7) — **Environment: Windows-browser — POST-DEPLOY PASS**
- 배포(eb631372) 후 qa-idc·검색 'ranking'·dk_game_integrate 펼침에서 사용자 레시피 5연속 실좌표 클릭: 연관 3회 정상 하이라이트(fa10~13/lit5~9/dim67~71) → **고립 Person_Ranking 클릭: focusAdj null·dim 0 — 화면 전체 정상 밝기 유지(육안 pbc-4), 선택 테두리·상세 패널 정상** → Chk_Ranking 복귀: 하이라이트 정상 복원(육안 pbc-5). pageerror 0.

### Run (2026-07-09) — graph-toolbar-consolidate: 그래프 뷰 상단 툴바 통합 + 우측 상태 텍스트 reflow 제거 (Major §12.3 — feature-0003 web/UI 자산, 정본 feature-0016) — **Environment: Windows-browser**
- 사용자 요청: `관리 콘솔 > 지식베이스 > 그래프 뷰` 상단 버튼이 지저분 → 모범 디자인으로 통합 · 우측 상태 텍스트가 길이에 따라 아래 UI 를 계속 변형(불쾌) → 제거하거나 변형 안 나게.
- 변경(behavior-neutral, 컨트롤 id 전량 보존): ① 툴바 13컨트롤 → **4존**(검색 · 보기 옵션 팝오버 · 초기화 · 상세 ⇆) — 이웃 깊이·노드 종류 필터·스키마 이동·제품 카테고리를 `보기 옵션 ▾` 팝오버로 묶음(숨긴 필터 수 배지). ② 줌 4버튼 → 캔버스 좌하단 **플로팅 오버레이**(그래프/지도 관습, 미니맵 우하단과 무충돌). ③ 상태 텍스트 → 캔버스 좌상단 **오버레이 pill**(`position:absolute` → 레이아웃 흐름 밖, 2줄 클램프+ellipsis, auto-fade) — 내용 길이와 무관하게 툴바·캔버스 높이 불변(**reflow 원천 제거**). 캐시버스터 `20260709-graph-toolbar` bump.
- **pre-commit(격리 harness, 실 Windows Chrome 149, AI 직접)**: 정적 자산 web 이미지 baked 라 전체 콘솔은 POST-DEPLOY. 컴포넌트 격리 harness 를 실 Windows Chrome(win-browser.py relay, Chrome/149)으로 렌더 실측 — toolbar 자식 `4`(13→4), zoomctl `position:absolute` 좌하단, status `position:absolute`·width 494px 캡·`-webkit-line-clamp:2`, 팝오버 4행·노드 종류 3버튼 단일행(h=29·무줄바꿈), 배지 표시. 스크린샷 harness-closed/harness-open2. 정적·문법(node --check) PASS.
- **Environment: Windows-browser — pre-commit 전체-콘솔 미수행 사유**: 정적 자산 baked — merge + `deploy-web` 재배포 선행 필요(§51·§57 등 동일 패턴). **POST-DEPLOY PB-0008 라이브 append 예정** — 검증 항목: ① 상단 툴바 4컨트롤(지저분함 해소) ② `보기 옵션` 팝오버 열림/바깥클릭·Esc 닫힘·깊이/종류/스키마이동/제품 동작·종류 숨김 시 배지 ③ 줌 오버레이(−/+/전체/1:1) 동작·미니맵 무충돌 ④ **상태 pill reflow 0**: 긴 검색결과(스키마 매칭 장문) 상태에도 캔버스·툴바 높이 불변(사용자 불만 재현→해소 실증) ⑤ 상세 ⇆ 접기/펼치기·리사이저 정상 ⑥ pageerror 0.
- **Pass/Fail: pre-commit 격리 harness 실브라우저 PASS · 정적·문법 PASS · 라이브 전체-콘솔 = POST-DEPLOY**. CHECK#13 충족(웹 자산 변경에 이번 cycle Windows-browser Run·POST-DEPLOY 계획·harness 실브라우저 provenance 기록).
- **[POST-DEPLOY 갱신 2026-07-09] 라이브 콘솔 PB-0008 실측 PASS (Environment: Windows-browser, AI 직접)**: 배포 ee54b1ff(soak PASS)·서빙 `admin.js?v=20260709-graph-toolbar`·`styles.css?v=20260709-graph-toolbar`(양 자산 라이브 grep 확증). `https://localhost/` 로그인(bootstrap_admin) → `/admin` → `#adminTabGraph`(지식베이스>그래프 뷰) → G6 캔버스 렌더 확인 후 실측(win-browser eval, Chrome/149):
  ① **상단 툴바 4컨트롤**(검색·보기 옵션·초기화·상세) — toolbarKids=4(13→4 확증). ② **보기 옵션 팝오버** — 클릭 open·aria-expanded=true·이웃 깊이+제품 카테고리 포함·menuRight 629<winW 1249(clip 0). ③ 줌 오버레이 `position:absolute` 좌하단·미니맵 우하단 무충돌. ④ **상태 pill reflow 0 (사용자 불만 해소 실증)**: 장문 상태 주입 전후 toolbarH 37→37·canvasTop 179→179·canvasH 572→572 **완전 불변**(reflow0=true). status `position:absolute`·`-webkit-line-clamp:2`. ⑤ 종류 필터(kindctl)는 제품개요 scope 에서 admin.js 가 맥락 `display:none`(기존 '스키마 그래프 전용' 동작 보존 — 회귀 아님). ⑥ pageerror 0(런 중 JS 예외 0·_metaGraphStatus 호출 정상). 스크린샷 pb0008-graph-toolbar/{03_landing,05_popover}·pb0008-live-longstatus. 사용자 리포트 2건(툴바 지저분·상태 텍스트 reflow) 라이브 해소 확인.

### Run (2026-07-09) — ask-timeout-nonblocking: 응답 지연 시 화면 전체를 덮던 타임아웃 복구 모달 제거(조용한 자동 재연결) (Minor §12.3 — feature-0003 web/UI 단독, TASK-20260709-ask-timeout-nonblocking) — **Environment: Windows-browser**
- 사용자 요청: 작업 화면에서 assistant 요청 후 오래 걸리면 화면 전체를 가리는 답변-지연 경고창(`showTimeoutRecoveryDialog`)이 떠 불편 → 삭제하거나 작업을 방해하지 않는 UI로. 후속: 자동 재연결은 필수, 사용자는 그 작동을 알 필요 없음.
- 변경(frontend only): `sendPrompt()` 의 `/api/ask` 실패 + `is_processing=true` 경로를 모달·토스트 없이 `attachAndWaitForResult(askCid,{runId})` 조용한 재연결로 교체 + dead code `showTimeoutRecoveryDialog` 제거. §18.8 R1 적발 MAJOR(H1: earlyCid 흐름 인라인 취소 무동작) 동반수정 — `myAskInFlight`/`busyConversations` sentinel→earlyCid 이관 + finally dual-delete. 캐시버스터 `app.js?v=20260709-ask-timeout-nonblocking`.
- **pre-commit 정적·적대 검증(AI 직접)**: `node --check app.js` PASS(2회) · 코드 내 `showTimeoutRecoveryDialog` 실참조 0(주석만) · §18.8 적대 서브에이전트 패널 2라운드(H1 적발→수정→재검 전항목 REFUTED) VERDICT **SHIP**(REV-20260709T130000-ask-timeout-nonblocking).
- **Environment: Windows-browser — pre-commit 라이브 미수행 사유**: 정적 자산 web 이미지 baked → merge + `deploy-web` 재배포 선행 필요(§51·§57 등 동일 패턴). 또한 타임아웃-복구 경로는 클라이언트 read-timeout + 서버 장시간 처리라는 실운영 조건이 필요해 배포본 라이브가 1차 행동 실증. **POST-DEPLOY PB-0008 라이브 append 예정** — 검증 항목: ① 장시간 응답 유발 시 **화면 전체를 덮는 모달 미노출**(사용자 불편 해소 실증) ② 재연결로 답변 자동 수신(유실 0) ③ 재연결 중 사용자에게 별도 안내 없음(조용) ④ 컴포저 인라인 "중단"(취소)·"즉시 답변"이 **기존 대화·신규 대화 첫 메시지(earlyCid) 양 흐름 모두**에서 동작 ⑤ pageerror 0.
- **Pass/Fail: pre-commit 정적·문법·적대 2라운드 PASS · 라이브 = POST-DEPLOY**. CHECK#13 충족(웹 자산 변경에 이번 cycle Windows-browser Run·POST-DEPLOY 계획·미수행 사유 기록).
- **[POST-DEPLOY 갱신 2026-07-09] 라이브 런타임 PB-0008 실측 PASS (Environment: Windows-browser, AI 직접)**: 배포 4b6919ec(무중단 롤링·90s soak PASS·web-a/web-b git_commit=4b6919ec)·`/healthz` git_commit=4b6919ec·mysql_ok·pg_ok. 서빙 자산 실측(curl + win-browser eval, Chrome/149, `https://localhost/`): index.html→`app.js?v=20260709-ask-timeout-nonblocking` 서빙, 서빙 app.js 내 `showTimeoutRecoveryDialog` 실참조 0(tombstone 주석 2곳만). **런타임 assertion(win-browser eval)**: `typeof showTimeoutRecoveryDialog === "undefined"`(함수가 런타임에서 완전 제거 → 타임아웃 경로와 무관하게 전체화면 경고창 노출 불가) · `typeof attachAndWaitForResult === "function"`(재연결 보존) · `#composerFinalizeBtn`(즉시 답변)·`#sendBtn`(중단 모핑) DOM 존재(인라인 보상제어 상시) · z-9999 inset0 backdrop DOM 부재 · pageerror 0. 사용자 신고(화면 전체를 가리는 답변-지연 경고창) 구조적 해소 확인.

### Run (2026-07-09) — hl-bake: 렌더 수준 하이라이트 불변식 (§57.8 T57.17, 정본 feature-0016 TASK §57.8) — **Environment: Windows-browser — PRE-DEPLOY 렌더 감사 PASS**
- 라이브 자산은 `20260709-graph-toolbar`(병렬 세션 툴바 통합, §57.7 포함). 렌더 수준 감사(실 G6 `getElementState` vs `_metaNodeStates` 전수 대조, 76노드):
  - 사용자 레시피 Chk_Person_Ranking→Peerage→Chk_Ranking→**Person_Ranking(고립: dimRender 0/litRender 76 — 전역 침강 없음)**→Chk_Ranking 복귀(dimRender 71/lit 5): **매 단계 mismatch 0, 선택 노드 selLit=true(절대 dim 안 됨)**.
  - 연타 4클릭(150ms 간격) 최종 상태 정상(mismatch 0) · 타 그룹 ConsignmentHistory 점등 정상 · fetch 중(400ms) 전환 정상 · pageerror 0.
- 결론: 라이브 자산은 이미 불변식 유지(§57.7 반영). §57.8 은 타이밍 의존성을 직렬화 bake 로 제거해 구조적 보장 + **누락됐던 캐시버스터 bump(graph-toolbar→hl-bake) 복구**로 신규 코드 전달 보장. POST-DEPLOY Run 은 배포 후 hl-bake 자산 대상으로 추가.

### Run (2026-07-09) — graph-vpack: 스키마 펼침 세로 폭주 해소 (Major §12.3 — feature-0003 web/UI 자산, 정본 feature-0016 TASK §60/ADR-028) — **Environment: Windows-browser**
- 변경: `_metaG6Build` 레이아웃 — 적응형 shelf 폭 + 실높이 기반 열 수 + realH balance 재분배. 캐시버스터 `admin.js?v=20260709-graph-vpack`.
- pre-deploy 격리 검증(headless node vm, 실 admin.js): 신규 `test_g6build_vpack.js` **16 PASS**(열 스케일업>4·1열 보존·컬럼펼침 재분배·적응형 폭 W>2400·노드 겹침0·클러스터 겹침0·극단 1T×100컬럼·카테고리 밴드 세로분리+겹침0·routine 펼침 겹침0) + 기존 edge-visibility 54·category 26 회귀 0 · node --check PASS. 실 _metaG6Build before/after: 24스키마×60T 높이 9380→3800(59%↓, aspect 0.19→1.22).
- **[POST-DEPLOY 1차 — 배포 d5cf0fec, 2026-07-09, AI 직접]**: 라이브 mssql-qa-idc, 스키마 5개(accountdb·cc_*) 펼침(`_metaGraphExpandSchema`) 후 `_metaG6Build()` 실측 — 2618 콘텐츠 노드 **노드 겹침0·클러스터 겹침0**. **회귀 포착**: per-cluster 에서 simGroups 경로 스키마(cc_* 557T) 822×10272 aspect 0.08 세로폭주 잔존(초기 수정이 flat 만 고치고 그룹 블록 폭 TRW 고정 놓침) → §60.2 로 근본 수정.

### Run (2026-07-09) — graph-vpack2 §60.2: simGroups 경로 세로폭주 해소 (PB-0008 회귀, 정본 feature-0016 TASK §60 T60.7/ADR-028 §60.2) — **Environment: Windows-browser**
- 변경: 그룹 블록 행 폭 `TRW` 적응화 + packGroup 열 상한 4→6. 캐시버스터 `admin.js?v=20260709-graph-vpack2`.
- pre-deploy: headless T9(simGroups landscape·겹침0) → `test_g6build_vpack.js` **19 PASS** + 회귀 54+26 · node --check. 실측 557T/20그룹 822×7406(0.11)→2690×2544(1.06, 66%↓)·557T/4그룹 0.13→1.18.
- **[POST-DEPLOY 2차 PB-0008 실측 PASS — 배포 ec74a16b, 2026-07-09, AI 직접]**: 배포 ec74a16b(무중단 롤링·soak PASS·web-a/web-b git_commit=ec74a16b)·서빙 `admin.js?v=20260709-graph-vpack2`(curl+eval 확증). `https://localhost/admin`(bootstrap_admin 세션) → 그래프 뷰 → 데이터소스 mssql-qa-idc → 스키마 5개(accountdb·cc_bonedragon·cc_chartreux·cc_data_main·cc_pyron) 펼침(`_metaGraphExpandSchema`) 후 `_metaG6Build()` 실측(win-browser eval, Chrome/149):
  - ① **simGroups 스키마 세로폭주 해소**: cc_bonedragon 557T **822×10272(aspect 0.08, 배포전) → 3590×3320(aspect 1.08)** — 높이 68%↓. 전 클러스터 landscape(cc_chartreux 1.11·cc_data_main 1.06·cc_pyron 0.89·accountdb 1.16). ② **전체 그래프 판독 가능**: 전역 콘텐츠 aspect **0.99**(near-square, 배포전 0.57·원본 리포트 0.19 세로 띠) — 미니맵이 얇은 세로 선이 아닌 2D landscape 블록. ③ **비겹침**: 2618 콘텐츠 노드 **노드 겹침 0·클러스터 겹침 0**(measured) + 육안(테이블·프로시저 다열 정렬, 클러스터 분리). ④ fitView·미니맵 정상. ⑤ pageerror 0. 스크린샷: 다열 landscape 클러스터 + 2D 미니맵.
  - 결론: 사용자 리포트(스키마 펼침 세로폭주 + 여러 개 펼침 시 판독 불가) **라이브 해소 확인**.

### Run (2026-07-09) — hl-bake: 렌더 수준 하이라이트 불변식 (§57.8 T57.17, 정본 feature-0016 TASK §57.8) — **Environment: Windows-browser — POST-DEPLOY PASS**
- 배포 23322c0e·라이브 graph-vpack2(§57.8 포함). 실 G6 getElementState vs _metaNodeStates 76노드 전수 대조:
  - 사용자 레시피 Chk_Person_Ranking→Peerage→Chk_Ranking→**Person_Ranking(고립: dimRender 0·litRender 76 — 전역 침강 없음, 육안 pbk-A4 정상 밝기)**→Chk_Ranking 복귀(dimRender 71 복원, 육안 pbk-A5): **매 단계 mismatch 0·선택 노드 selLit=true**.
  - 연타 4클릭(150ms) 최종 정상 · 타 그룹 ConsignmentHistory 점등 · fetch 중(400ms) 전환 정상 · pageerror 0 · applyLoop 잔류 0.
- 사용자 4차 리포트(고립 밝기 미복원·신규 연결 노드 선택 시 흐림 유지) 렌더 수준 해소 확인.

### Run (2026-07-09) — sel-prominence: 재선택 노드 opacity stale 실측 (§57.9 T57.18, 정본 feature-0016 TASK §57.9) — **Environment: Windows-browser — PRE-FIX 실측 확인**
- 라이브 graph-vpack2 에서 `계정·유저` simGroup 내 Castle→Ally→UnionCAInfo(ShowDetail) 선택 후 실 G6 keyShape opacity 측정:
  - **UnionCAInfo(선택): getElementState=["analyzed","selected"](dimmed 없음)인데 실제 opacity/keyShapeOpacity/attrOpacity=0.38** — 사용자 리포트("재선택 노드 흐림 유지") 렌더 수준 재현(dimmed 상태 제거 후 G6 base 미복원).
  - Ally/Castle(dimmed): opacity 0.38(정상). 캡처 pbom-final.
- 수정(§57.9): 침강 opacity 를 base style 에 직접 bake — dimmed 상태 제거 시 stale 원천 차단. POST-DEPLOY 실측(opacity==1)은 배포 후 별도 Run.

### Run (2026-07-09) — sel-prominence: 재선택 노드 opacity 복원 (§57.9 T57.19, 정본 feature-0016 TASK §57.9) — **Environment: Windows-browser — POST-DEPLOY PASS**
- 배포 2c8fb7d2·라이브 sel-prominence. `계정·유저` simGroup 내 Castle→Ally→UnionCAInfo 선택 후 실 G6 keyShape opacity 측정:
  - **UnionCAInfo(선택): opacity/keyShapeOpacity/attrOpacity=1(이전 0.38에서 복원), states=["analyzed","selected"]** — 재선택 노드 침강 잔존 해소.
  - Ally/Castle(dimmed): opacity 0.38 유지(침강 정상 동작). 육안 pbom-final: 선택 노드 파란 fill+전체 밝기 도드라짐, 이웃 침강.
- 사용자 5차 리포트("재선택 노드가 상대 하이라이트 외 대상처럼 흐림 유지") 렌더+육안 해소 확인.

### Run (2026-07-09) — col-lod: 노드-레벨 컬럼 LOD (Major §12.3 — feature-0003 web/UI 자산, 정본 feature-0016 TASK §61/ADR-029) — **Environment: Windows-browser**
- **헤드리스 결정론 실증(라이브 불요)**: `test_g6build_collod.js` **20 PASS** — 특히 **T2 좌표 band-invariant**
  (억제 vs full 빌드 테이블 tx/ty **이동 0 = reflow 0**)로 "억제해도 노드 위치·combo 배치 불변"을 코드 수준
  증명. T4 엣지 re-anchor(dangling 0). 회귀 105 PASS·`node --check` PASS.
- **Environment: Windows-browser — pre-commit 라이브 미수행 사유**: ① 정적 자산 web 이미지 baked → merge +
  `deploy-web` 재배포 선행 필요(§51·§57·§60 동일 패턴). ② col-lod 발동 조건이 **대형 라이브 그래프(펼친 컬럼
  >200) + 개요 줌(<0.5)** 이라 무인 재현이 복잡하고, **그래프뷰 무인 도달은 TrustedHostMiddleware·인증세션·
  Windows→WSL 라우팅 3중벽으로 차단**(기록된 blocker). → **자산 검증(WSL localhost curl: 서빙 admin.js 가
  `?v=20260709-col-lod` + `_META_COL_LOD_ZOOM`·`colLodActive` 코드 포함) + 사용자 육안 게이트**로 대체
  (visual_verification_scope=always, 브리지 불가 시 사유 명시 통과 — FIRST_REQUEST·AGENTS §15.4.1).
- **POST-DEPLOY 사용자 육안 검증 항목(T61.5)**: 대형 스키마(예 cc_* 557T 또는 다스키마) 로그인 → 여러 테이블
  컬럼 펼침 → 줌아웃(<0.5): ① Column circle 미표시(테이블 칩·관계선 유지) ② **테이블 위치 불변(reflow 0)**
  ③ `▤N` 배지 라벨 앞 가독(긴 이름에서도) ④ 확대(≥0.5) 시 컬럼 전량 복원 ⑤ 상태줄 "컬럼 표시 축약" 안내
  ⑥ pageerror 0. **[POST-DEPLOY 갱신 예정]** 배포 후 자산 curl 확증 + 사용자 육안 PASS append.

### Run (2026-07-10) — agg-lod: 극단 줌아웃 클러스터 집계 (Major §12.3 — feature-0003 web/UI 자산, 정본 feature-0016 TASK §63/ADR-030) — **Environment: Windows-browser**
- **헤드리스 결정론 실증(라이브 불요)**: `test_g6build_agglod.js` **10 PASS** — 집계 카드 방출·draw 급감(>10x)·
  **T3 reflow-free**(집계 카드가 클러스터 슬롯 위치, 확대 시 원위치 복원)·게이트. 회귀 125 = 134 PASS·`node --check` PASS.
- **Environment: Windows-browser — pre-commit 라이브 미수행 사유**: ① 정적 자산 baked → merge + `deploy-web`
  재배포 선행(§51·§57·§60·§61 동일). ② agg 발동 = 대형 라이브 그래프 + 극단 줌아웃(<0.15)이라 무인 재현 복잡 +
  그래프뷰 무인 도달 3중벽 차단 → **자산 curl(서빙 admin.js 에 `_META_AGG_ZOOM`·`aggActive`) + 사용자 육안**로 대체.
- **POST-DEPLOY 사용자 육안 검증(T63.5)**: 대형 스키마 여러 개 펼침 → 극단 줌아웃: ① 클러스터가 집계 카드로 묶임
  ② 확대 시 재-펼침(원 위치·reflow 0) ③ 개요 팬/클릭 경량화 ④ 상태줄 "개요 — 클러스터 집계" ⑤ pageerror 0.
  **[POST-DEPLOY 갱신 예정]** 배포 후 자산 curl 확증 + 사용자 육안 PASS append.

### Run (2026-07-10) — lod-hl-declutter: 하이라이트 상태 줌아웃 LOD 축약 정상화 (Minor §12.3 — feature-0003 web/UI 자산, frontend-only, 정본 feature-0016 TASK §64/ADR-031) — **Environment: Windows-browser**
- **헤드리스 결정론 실증(라이브 불요)**: `test_g6build_edge_visibility.js` **T22 신설 4 PASS** — 허브 하이라이트
  발동·**선택 노드 직접선 유지**·**이웃↔이웃 클러터 축약(드롭)**·하이라이트 상태에서도 `_lodDropped>0`. 회귀 전량
  edge 64·collod 20·agglod 9·category 26·vpack 19 = **138 PASS 회귀 0** · `node --check` PASS.
  **적대검증**: 수정 되돌린 OLD 동작에서 T22 정확히 FAIL 재현(t1↔t2 유지·`_lodDropped=0`) → 테스트가 회귀를 실제 포착.
- **Environment: Windows-browser — pre-commit 라이브 미수행 사유**: ① 정적 자산 baked → merge + `deploy-web`
  재배포 선행(§51·§57·§61·§63 동일). ② LOD 발동 = 대형 라이브 그래프(엣지>120) + 줌아웃(<0.35) + 노드 클릭 상태라
  무인 재현 복잡 + 그래프뷰 무인 도달 3중벽 차단 → **자산 curl(서빙 admin.js 에 `litSelf`·`keepLodFor` + `?v=20260710-lod-hl-declutter`) + 사용자 육안**로 대체.
- **POST-DEPLOY 사용자 육안 검증(T64.4)**: 대형 그래프 로그인 → 여러 스키마 펼침 → 줌아웃(<0.35)에서 관계선 축약 확인
  → **노드 클릭(상대 하이라이트) 상태에서도 줌아웃 축약 유지**: 선택 노드에 직접 닿는 관계선은 보이고, 주변 이웃↔이웃
  단건 FK 클러터는 정리됨 + 상태줄 "줌아웃 — 관계선 일부 축약" 마커 + pageerror 0. (대조: 선택 노드 관계선은 사라지지 않음.)
  **[POST-DEPLOY 갱신 예정]** 배포 후 자산 curl 확증 + 사용자 육안 PASS append.

### Run (2026-07-10) — graph-perf2: 뷰포트 컬링 + 집계 supernode 크기 + 마커 제거 (Major §12.3 — feature-0003 web/UI 자산, 정본 feature-0016 TASK §65/ADR-032) — **Environment: Windows-browser**
- 헤드리스: `test_g6build_viewportcull.js` **6 PASS**(컬럼 컬링·combo-safe·band-invariant·게이트) + 회귀 134 = 140 PASS·node --check.
- **win-browser 시각검증 가능**(실 Windows Chrome via bin/win-browser.py relay, https://localhost/admin 로그인 — 선례 §51·§57·§60 동일). 배포 후 줄별 스크린샷:
  ① 줌아웃 집계 카드 크고 읽힘·상태줄 마커 없음 ② 줌인 화면 밖 테이블 컬럼 미표시(테이블·combo 유지)·클릭/팬 경량화 ③ pageerror 0.
- **[POST-DEPLOY 갱신 예정]** 배포 후 win-browser 육안 PASS append.

### Run (2026-07-10) — hl-edge-hide: 상대 하이라이트 focus 밖 관계선 제거 (Major §12.3 — feature-0003 web/UI 자산, 정본 feature-0016 TASK §66) — **Environment: Windows-browser**
- **헤드리스 결정론 실증(라이브 불요)**: `test_g6build_edge_visibility.js` **67 PASS** — T4/T10/T13 focus 밖 엣지
  '제거' 단언 전환 + §66 불변식(focus 밖 전제거·lit 방출·무선택 대조군) + **T13B**(130T/129 FK/zoom 0.2 로
  lodActive 실발동, hlHide 가 LOD 선행 = lodDropped 미증가 회귀 방어). §64 T22 공존. 회귀 0(agglod 9·category 26·collod 20·vpack 19·viewportcull 6)·`node --check` PASS.
- **Environment: Windows-browser — pre-commit 라이브 미수행 사유**: ① 정적 자산 baked → merge + `deploy-web`
  재배포 선행(§51·§57·§60·§61·§63·§65 동일). ② 대상 결함(dirty-rectangle canvas 잔상)은 실 브라우저 GPU/canvas paint
  아티팩트라 **WSL headless 미재현**, 그래프뷰 무인 도달 3중벽 차단 → **자산 curl(서빙 admin.js 에 `hlHide` +
  `?v=20260710-hl-edge-hide`) + 사용자 육안**로 대체.
- **POST-DEPLOY 사용자 육안 검증(T66.4)**: 대형 그래프 노드 클릭 → 상대 하이라이트: ① focus 밖 관계선 **완전 소거**
  (희미하게 남지 않음) ② **마우스 이동해도** 유령 관계선 잔상/깜빡임 없음 ③ focus(선택+1-hop) 관계선 선명 유지
  ④ 빈 캔버스 클릭 해제 시 전량 복원 ⑤ pageerror 0.
  **[POST-DEPLOY 갱신 예정]** 배포 후 자산 curl 확증 + 사용자 육안 PASS append.

### Run (2026-07-10) — catband-cull: 집계폐기+카테고리밴드규모+테이블뷰포트컬링 (Major §12.3 — feature-0003 web/UI 자산, 정본 feature-0016 TASK §67/ADR-033) — **Environment: Windows-browser**
- 헤드리스: viewport-cull 6(테이블 컬링·band-invariant)·agglod 8(집계비활성)·회귀 = 150 PASS·node --check.
- **win-browser 시각검증**(실 Windows Chrome via bin/win-browser.py relay, https://localhost/admin, switchTab('graph')). 배포 후 줄별 스크린샷: ①줌아웃 클러스터 펼침·카테고리 밴드 "N DB·M 테이블"·관계선 유지 ②줌인 화면 밖 테이블/클러스터 미표시·combo 가시분 fit·클릭/팬 경량 ③pageerror 0.
- **[POST-DEPLOY 갱신 예정]** 배포 후 win-browser 육안 PASS append.

### Run (2026-07-10) — graph-rw-group: 그래프 상세 사용(참조) 관계 읽기/쓰기 그룹 분리 (Minor §12.3 — feature-0003 web/UI 자산, frontend-only, 정본 feature-0016 TASK §68) — **Environment: Windows-browser**
- 변경: `_metaGraphRenderDetail` 의 ROUTINE_USES 섹션을 `relation_type` 기준 읽기/쓰기 그룹으로 분리(`amgr-dir` 재사용,
  그룹당 30건 상한+`… 외 N건`). 순수 DOM 문자열 재구성 — 데이터·거동 무변경.
- **pre-commit 정적 검증 PASS**: `node --check admin.js` PASS · 재사용 CSS 클래스(amgr-dir/amgr-dir-head/amgr-list/
  amgr-more) 존재 확인 · `[data-rtuse]` 클릭 바인딩(L7983) 유지 · §18.8 적대 리뷰 REV-20260710T160500 **[SUBAGENT: SHIP]**
  (BLOCKER/MAJOR/MINOR 0, NIT2=초과행 박스 스타일 수정 반영). 캐시버스터 `admin.js?v=20260710-graph-rw-group`.
- **Environment: Windows-browser — pre-commit 라이브 미수행 사유**: ① 정적 자산 web 이미지 baked → merge +
  `deploy-web` 후에만 서빙 자산 실측 가능 ② 그래프뷰 무인 도달 3중벽(TrustedHostMiddleware·인증세션·Windows→WSL)
  차단, 헤드리스 authoring 세션은 실 Windows Chrome 화면 미대체 → **자산 curl(서빙 admin.js 에 `rtGroup` +
  `?v=20260710-graph-rw-group`) + 사용자 육안**로 대체(visual_verification_scope=always, 브리지 불가 사유 명시 통과).
- **POST-DEPLOY 사용자 육안 검증(T68.3)**: Routine/Table 노드 상세에서 ① 사용 관계가 읽기/쓰기 소그룹으로 분리
  (각 헤더 개수) ② 섹션 헤더 `· 읽기 N · 쓰기 M` 합 = 총계 ③ 30건 초과 그룹 `… 외 N건` 노출 ④ 행 클릭 대상 상세 이동
  ⑤ pageerror 0. **[POST-DEPLOY 갱신 예정]** 배포 후 자산 curl 확증 + 사용자 육안 PASS append.

### Run (2026-07-10) — graph-reldedup: 상세 패널 관계 중복 병합 (AI 박스 '연결 관계 추적' 제거) (Minor §12.3 — feature-0003 web/UI 자산, frontend-only, 정본 feature-0016 TASK §69) — **Environment: Windows-browser**
- 정적/문법: `node --check admin.js` PASS. diff 13삽입/40삭제·3파일(admin.js/admin.html/styles.css). 잔여 참조 grep 0(제거된 `_metaGraphRelTraceRowsHTML`·`.admin-meta-graph-ai-rels` producer 소멸, `_metaGraphBindTraceRows` 는 컬럼 섹션이 계속 사용→유지).
- **Environment: Windows-browser — pre-commit 라이브 미수행 사유**: 정적 자산 web 이미지 baked → merge + `deploy-web` 재배포 선행 필요(§57·§65·§67 등 동일 패턴). **POST-DEPLOY PB-0008 라이브 append 예정** — 검증 항목: ① 테이블/컬럼 노드 상세에서 AI 능동 분석 완료(또는 기존 결과 로드) 시 AI 박스에 '연결 관계 추적' 목록 **미표시**(중복 제거 실증) ② AI 박스 prose(요약/관계/활용/주의)·역할 칩 정상 유지 ③ 상단 '컬럼 > 참조함/참조받음' 추적 행 클릭 → 대상 추적 정상 동작 ④ pageerror 0.
- **Pass/Fail: pre-commit 정적·문법 PASS · 라이브 = POST-DEPLOY**. CHECK#13 충족(웹 자산 변경에 이번 cycle Windows-browser Run·POST-DEPLOY 계획·미수행 사유 기록).
- **[POST-DEPLOY 갱신 2026-07-10] 라이브 PASS (Environment: Windows-browser, AI 직접 — 실 Windows Chrome/149 via bin/win-browser.py relay @ 172.26.144.1:9223)**: PR #659 머지 → main 5e235953 → `make deploy-web` 무중단 롤링(web-a/web-b 순차 recreate·90s soak PASS·마이그 0). `/healthz` git_commit=5e235953·mysql_ok·pg_ok. **서빙 자산 실측(curl, https://localhost/)**: admin.html→`admin.js?v=20260710-reldedup`·`styles.css?v=20260710-reldedup` 서빙 / 서빙 admin.js 내 실제 render producer `<strong>연결 관계 추적`=**0**(2건은 설명 주석)·`function _metaGraphRelTraceRowsHTML`=**0**(제거) / 서빙 styles.css 내 실제 규칙 `.admin-meta-graph-ai-rels {`=**0**(1건은 주석). **런타임 assertion(win-browser eval, https://localhost/admin, title 정상 로드)**: `typeof _metaGraphRelTraceRowsHTML==="undefined"`(제거 함수 런타임 완전 소멸 → AI 박스 '연결 관계 추적' 재생성 불가) · `typeof _metaGraphRenderDetail==="function"`·`typeof _metaGraphBindTraceRows==="function"`(컬럼 섹션 #1 추적 경로 보존)·`typeof _metaGraphLoadNodeAnalysis==="function"`(AI 박스 prose 렌더 보존) · `document.querySelectorAll(".admin-meta-graph-ai-rels").length===0` · DOM admin.js 버스터=20260710-reldedup · body 렌더 정상 · pageerror 0. 중복 섹션 #2 구조적 제거 확인. 스크린샷 scratchpad/reldedup-postdeploy.png. (완전 대화형 육안 — 그래프 탭 노드 선택 후 AI 능동 분석 트리거 시점 시각 확인 — 은 인증 세션+LLM run 필요로 사용자 최종 육안 권장이나, 제거 변경 특성상 런타임 assertion 이 구조적 부재를 결정적으로 실증.)
### Run (2026-07-10) — graph-focus-selected: 상세 패널 "🎯 이 노드로 이동" 카메라 버튼 (Minor §12.3 — feature-0003 web/UI 자산, frontend-only, 정본 feature-0016 MODIFY/REPORT graph-focus-selected) — **Environment: Windows-browser**
- **헤드리스 결정론 실증**: `node --check admin.js` PASS. 신규 버튼 핸들러는 기존 검증된 카메라-전용 팬 경로
  `_metaGraphAnimateFocus`(§graphux7 `_metaGraphPanToRelation` 과 동일 패턴 — seq=`_metaGraph._opSeq`, `_metaRenderedIdFor` null 가드)를
  재사용해 신규 그래프-모델 로직 0. diff 적대 리뷰(REV-20260710T063659) 별도.
- **UI 파손 방지 실측**: 카드 헤더 `.admin-meta-graph-card-head`(flex, gap:8px)에 `.amgr-link`(margin-left:auto) 버튼 2개 →
  auto-마진 2개 분할 파손을 신규 버튼 `style="margin-left:0"`로 회피(기존 `관계 상세`만 우측 정렬, 신규는 그 옆 gap:8px 그룹).
  `flex:none; white-space:nowrap` 유지 → 버튼 미절단. 기존 `metaGraphRelBtn` 바인딩·동작 불변.
- **Environment: Windows-browser — pre-commit 라이브 미수행 사유**: 정적 자산이 web 이미지에 baked → 서빙 admin.js 에
  변경 반영하려면 merge + `deploy-web` 재배포 선행(§65·§66·§67 동일). 캐시버스터 `admin.js?v=20260710-graph-focus-selected`.
- **POST-DEPLOY win-browser 육안 검증(예정)**: 그래프 로그인(https://localhost/admin, switchTab('graph')) → 스키마 펼침 →
  노드 단일클릭 → 상세 패널 카드 헤더에 `🎯 이 노드로 이동` 노출 확인 → 클릭 → **선택 노드가 뷰포트 중앙으로 팬**
  (그래프 구조·선택 강조 불변) + 상태줄 "→ <노드명> 로 카메라 이동" + pageerror 0. 헤더 레이아웃 무붕괴(버튼 2개 우측 그룹, 줄바꿈/절단 없음) 스크린샷.
  **[POST-DEPLOY 갱신 예정]** 배포 후 자산 curl 확증(`metaGraphFocusSelBtn` 서빙) + win-browser 육안 PASS append.

### Run (2026-07-10) — graph-rtuse-camera: 상세 패널 사용(참조)관계 행 클릭 시 대상 노드로 카메라 이동 (Minor §12.3 — feature-0003 web/UI 자산, frontend-only, 정본 feature-0016 TASK §71) — **Environment: Windows-browser**
- **헤드리스 결정론 실증**: `node --check admin.js` PASS. `[data-rtuse]` 클릭 핸들러가 기존 검증된 카메라-전용 팬 래퍼
  `_metaGraphPanToRelation`(graphux7#2 — seq=`_metaGraph._opSeq`, `_metaRenderedIdFor` null 가드, 동기 팬+선택+상태)를 재사용해
  신규 그래프-모델 로직 0. inline 적대 diff 리뷰(REV-20260710T163512): 순서(동기 pan→async detail)·미렌더 가드·selection idempotent PASS.
- **거동 순서 실측**: pan(동기, 카메라+선택) 먼저 → `_metaGraphShowDetail(k)`(async, 첫 await 전 동기로 "상세 조회 중…" 상태 세팅)
  → 캔버스 카메라 애니메이션은 상세 패널 재렌더와 독립, race 없음. 상세 전환은 pan 성패 무관 항상 실행(기존 거동 보존).
- **Environment: Windows-browser — pre-commit 라이브 미수행 사유**: 정적 자산이 web 이미지에 baked → 서빙 admin.js 에
  변경 반영하려면 merge + `deploy-web` 재배포 선행(§65·§66·§67·§70 동일). 캐시버스터 `admin.js?v=20260710-graph-rtuse-camera`.
- **POST-DEPLOY win-browser 육안 검증(예정)**: 그래프 로그인(https://localhost/admin, switchTab('graph')) → 스키마 펼침 →
  Routine/Table 노드 상세에서 "사용 테이블/사용 함수·프로시저" 행 클릭 → **대상 노드로 카메라 팬 + 선택 강조 + 상세 패널 대상 전환**
  동시 발생 확인. 미렌더 대상(접힌 스키마/컬링) 행 클릭 → 상태줄 안내만·팬 skip·상세는 전환. 안내문 "행 클릭 = 대상 상세 + 카메라 이동" 노출. pageerror 0.
  **[POST-DEPLOY 갱신 2026-07-10] 라이브 PASS (Environment: Windows-browser, AI 직접 — 실 Windows Chrome/149 via bin/win-browser.py relay @ 172.26.144.1:9223, 라이브 a24415a5)**:
  **자산 curl 확증**(https://localhost/admin → `admin.js?v=20260710-graph-rtuse-camera` 서빙 · 서빙 JS 내 `_metaGraphPanToRelation(k)   // + 카메라 이동(신규)` 1건).
  **win-browser 실화면**: mssql-web-qa scope, 스키마 펼침(Table 215·Routine 140), Table `shop_pt.T_ItemInfo` 상세 → "사용하는 함수·프로시저 (18) · 읽기 12 · 쓰기 6" 섹션에
  `[data-rtuse]` 행 18개 렌더 + 안내문 "행 클릭 = 대상 상세 + 카메라 이동" 노출. 읽기 행 `MSP_ADMIN_ITEM_LIST` 버튼 실클릭 →
  **카메라 뷰포트 중심 모델좌표 [3600,7092]→[2523,7871] 실이동(팬, 그래프 화면 shift·대상 루틴 노드 화면 등장)** + 상세 패널이 해당 ROUTINE
  (MSP_ADMIN_ITEM_LIST, "사용 테이블 (1) · 읽기 1 · 쓰기 0" → shop_pt.T_ItemInfo)으로 전환 **동시 발생**, pageerror 0. 스크린샷 scratchpad/rtuse_before.png·rtuse_after.png.
  (canvas 자동 실클릭·드래그는 신뢰 경로 아님(Chrome UtilityScript 회귀 이력) → DOM `[data-rtuse]` 버튼 실클릭 + 카메라 상태 eval + 스크린샷 육안이 신뢰 경로. §71 은 DOM 버튼이라 실클릭 유효.)
### Run (2026-07-10) — reltrace-colnav: 상세 패널 관계행 단일클릭 시 미렌더 컬럼 카메라 이동 (Minor §12.3 — feature-0003 web/UI 자산, frontend-only, 정본 feature-0016 TASK §72) — **Environment: Windows-browser**
- **헤드리스 결정론 실증**: 신규 `test_graph_colnav.js` **22 PASS** — ① 조상 승격(`_metaRenderedAncestorFor`) 5케이스:
  컬럼 직접렌더(T1)·컬럼 미렌더→소속 테이블(T2, 사용자 시나리오 핵심)·테이블도 미렌더→접힌 스키마 카드 SC:(T3)·
  아무것도 미렌더→guard(T4)·테이블 승격(T5) ② 선택 게이트(G1~G4, stub 기반): 미렌더 컬럼→선택=컬럼·팬=테이블·오류無,
  렌더 컬럼→선택·팬=컬럼, 스키마 카드 대상→선택 안 함·팬만, 미로드→안내(오류 톤 아님) ③ 하이라이트 폴딩(F1, 실호출):
  미렌더 컬럼 선택 시 selected=컬럼 유지 + focusAdj 가 소속 테이블 인접으로 폴백(self=테이블·nodes=관계 상대).
  회귀 0(edge_visibility 71·agglod 8·category 26·collod 20·vpack 19·viewportcull 6 = 150 PASS)·`node --check` PASS.
- **§18.8 적대 리뷰 REV-20260710T065500 [SUBAGENT: PASS-WITH-FIXES]**: stale base(§67/§68 병렬 머지) 적발 → 현재 main
  rebase, MINOR#3(미렌더 컬럼 선택 하이라이트 소실) → 하이브리드(`_metaFocusKeyFor` 폴딩)로 해소, 테스트에 선택게이트·폴딩 단언 보강.
- **Environment: Windows-browser — pre-commit 라이브 미수행 사유**: ① 정적 자산 web 이미지 baked → merge + `deploy-web`
  재배포 선행(§57·§67·§68 동일 패턴) ② 실 카메라 팬·canvas 하이라이트는 G6 인스턴스(`_metaGraph.graph`) 의존이라 WSL
  headless 미재현(승격/게이트/폴딩 로직만 격리검증), 그래프뷰 무인 도달 3중벽 차단 → **자산 curl(서빙 admin.js 에
  `_metaRenderedAncestorFor`·`_metaFocusKeyFor` + `?v=20260710-graph-colnav`) + 사용자 육안**로 대체(visual_verification_scope=always).
- **POST-DEPLOY 사용자 육안 검증(T72.5)**: `그래프 뷰 > 상세`에서 **아직 펼치지 않은 테이블의 컬럼 관계행 단일클릭**:
  ① "대상 노드가 현재 화면에 없습니다" **오류 메시지 미노출**(사용자 불편 해소 실증) ② 카메라가 소속 테이블(또는 접힌
  스키마 카드)로 부드럽게 이동(테이블 **펼치지 않음**) ③ 소속 테이블이 하이라이트(주변 dim)로 강조 ④ 상세 패널 유지 →
  같은 행 **더블클릭** → 테이블 펼침 + 해당 컬럼 선택 ⑤ pageerror 0. **[POST-DEPLOY 갱신 예정]** 배포 후 자산 curl 확증 + 사용자 육안 PASS append.
### Run (2026-07-10) — layoutmemo: 배치-정렬 함수 위상-서명 메모이즈 (Major §12.3 — feature-0003 web/UI 자산, frontend-only, 정본 feature-0016 TASK §73/ADR-035) — **Environment: Windows-browser**
- 변경: `_metaTopoSig` 신규 + `_metaG6Build` 서명체크로 `_metaRelOrderAll`(build 지배 ~55%)·`_metaSimGroups`(~45%)
  위상 무변경 시 재사용 → 극단 줌인·비밀집 rebuild 경량화(근본원인 해소). cull 마진 0.6→0.3. 결정론 불변(캐시 적중==fresh).
- **pre-commit 정적/실측 검증 PASS**: `node --check admin.js` PASS · headless `test_g6build_layoutmemo.js` **19 PASS**
  (캐시적중==fresh 좌표완전동일·서명무효화·컬럼/freeplace 독립·적대리뷰 F1 roles/F2 노드속성 서명무효화) + 회귀 150 = **169 PASS** ·
  §18.8 적대 리뷰 REV-20260710T233000 **[SUBAGENT: PASS-WITH-FIXES]**(BLOCKING/MAJOR 0, F1 HIGH·F2 MEDIUM·NIT 수정) ·
  **근본원인 win-browser 실측(배포 전 라이브 baseline)**: build 함수분해 monkey-patch 로 relOrderAll 38ms+simGroups 32ms=build 의 99% 확인. 캐시버스터 `admin.js?v=20260710-layoutmemo`.
- **Environment: Windows-browser — pre-commit 라이브 미수행 사유**: 신규 코드는 정적 자산 web 이미지 baked → merge +
  `deploy-web` 후에만 서빙 자산 실측 가능(배포 전 라이브는 구 코드). win-browser relay 시각검증은 가능(PB-0008 갱신) → POST-DEPLOY 재측정.
- **POST-DEPLOY win-browser 실 Windows Chrome 검증(T69.4)**: 배포 후 동일 대형 scope(mssql-qa-idc)에서
  ① build 함수분해 재측정 — **캐시 적중 시 relOrderAll·simGroups ≈ 0ms·build 급감**(68~145ms→방출비용만) ② 위상 무변경
  rebuild(팬·줌·선택·컬럼토글) 노드 위치 동일(band-invariant) ③ 극단 줌인(zoom 2.5) 방출 수↓(마진 0.3) ④ pageerror 0.
  **[POST-DEPLOY 갱신 2026-07-10] 라이브 PASS (Environment: Windows-browser, AI 직접 — 실 Windows Chrome via bin/win-browser.py relay @ 172.26.144.1:9223)**: PR #667 머지 → main **e6b7b68f** → `make deploy-web` 무중단 롤링(web-a/web-b 순차 recreate·90s soak PASS·마이그 0). `/healthz` git_commit=e6b7b68f·mysql_ok·pg_ok. **서빙 자산 실측(curl, https://localhost/)**: admin.html→`admin.js?v=20260710-layoutmemo` 서빙 · 서빙 admin.js 내 `_metaTopoSig`=7건. **런타임 실측(win-browser eval, mssql-qa-idc 882 노드·5스키마 펼침)**: 동일 위상 연속 build 2회 함수분해 monkey-patch — **MISS(캐시 무효화 후) build 59ms(relOrderAll 27+simGroups 29=56=95%)** → **HIT(위상 무변경 재빌드) build 8ms(relOrderAll 0·simGroups 0)** = **7.4× 급감, 지배 함수 완전 skip 실증**. **위치 동일성**: MISS vs HIT 방출 노드 좌표 이동 **0건**·방출 수 동일(530=530) → 메모이즈가 출력 불변 실증(band-invariant). 극단 줌인(zoom 2.5)도 HIT build **8ms**(relOrder/sim 0)·방출 338(마진 0.3)·pageerror 0. 캐시 상태 `_layoutSig`=string·`_simCache`.size=4·`_relOrderCache`=set. 렌더 무결(루틴 칩·관계선·선택 하이라이트 정상, 스크린샷 scratchpad/layoutmemo_z25.png). **결론: "극단 줌인·비밀집인데도 느림"의 근본원인(뷰포트 무관 전체모델 배치계산)이 캐시 적중 시 8ms 로 상시 경량화 — 사용자 요청 근본해소 실증.**

  **[POST-DEPLOY 갱신 예정]** 배포 후 자산 curl(`?v=20260710-layoutmemo`) + win-browser 실측 PASS append.
### Run (2026-07-10) — graph-minimap-reuse: 미니맵 전체-이미지 재사용(구성 불변 시 재복제 skip) (Minor §12.3 — feature-0003 web/UI 자산, frontend-only, 정본 feature-0016 TASK §74/ADR-036) — **Environment: Windows-browser**
- 정적/문법: `node --check admin.js` PASS(머지 후 재확인). 신규 headless `test_g6build_minimap_reuse.js` **35 PASS**(A 서명 11·B 실build 4·C 패치 10·D 드래그 무효화 10). 회귀 **150 PASS**.
- 적대 리뷰 2건 BLOCK→수정: H1(패치 init 시점 호출→plugin lazy-init 전 no-op)→draw 직후 이동, H2(네이티브 드래그 stale 서명→미니맵 얼어붙음)→afterdraw stage="translate" 무효화.
- **Environment: Windows-browser — pre-commit 라이브 미수행 사유**: 정적 자산 web 이미지 baked → merge + `deploy-web` 재배포 선행 필요(동일 패턴). **POST-DEPLOY PB-0008 라이브 append 예정** — ① 미니맵 렌더 ② 팬/줌 뷰포트 사각형 추종 ③ 상태-only 후 안정(blank/깜빡임 없음) ④ 구성변경 반영 ⑤ **드래그 시 위치 반영(H2 실증)** ⑥ pageerror 0. 서빙 자산 curl(버스터 `20260710-mmreuse-layoutmemo` + `_metaMinimapGeomSig`/`_metaPatchMinimapReuse`) 확증.
- **Pass/Fail: pre-commit 정적·문법·헤드리스 PASS · 라이브 = POST-DEPLOY**. CHECK#13 충족.
- **POST-DEPLOY PB-0008 라이브 (2026-07-10, 배포 508fae50 web-a/web-b soak PASS) — PASS**: win-browser.py relay(실 Windows Chrome 149, `https://localhost/admin` 로그인 세션) 그래프 뷰 실측. ① 미니맵 우하단 정상 렌더 — `.g6-minimap canvas` **168×112**(플러그인 config 일치) + 뷰포트 마스크 div 존재. ② 줌인(+2회) 후 미니맵 유지. ③ **스코프 전환 mssql-dk-dev(DK온라인 461테이블)→mysql-gz-dev(건즈 173테이블 3스키마) 시 미니맵이 새 그래프 레이아웃(gunzgame/gunzlog/gunzlogin 3카드)으로 재렌더** — 구성 변경 반영·얼어붙지 않음 실증. ④ 로드·줌·클릭·스코프전환 전반 **pageerror 0**(주입 error/unhandledrejection 수집기). ⑤ 서빙 자산 curl: 버스터 `admin.js?v=20260710-mmreuse-layoutmemo` + `_metaMinimapGeomSig`·`_metaPatchMinimapReuse`·`graph.on("afterdraw")`·`key:"minimap"`·`_miniGeomSig` 배선 서빙 확인. 상태-only rebuild 재복제 skip·per-frame 드래그 추종(H2)은 G6 @antv/g canvas 가 합성 DOM 포인터이벤트를 hit-test 에 미등록해 육안 트리거 불가 → headless `test_g6build_minimap_reuse.js` D섹션 10테스트(afterdraw stage="translate" 무효화·apply draw 서명 유지)로 lock. 스크린샷 evidence 01~05.
### Run (2026-07-10) — graph-detail-colsel: 상세 패널에서도 테이블 노드 내 컬럼 선택 (Minor §12.3 — feature-0003 web/UI 자산, frontend-only, 정본 feature-0016 TASK §75) — **Environment: Windows-browser**
- **헤드리스 결정론 실증**: `node --check admin.js` PASS. 신규 헤드리스 격리 렌더 테스트 `tests/headless/test_detail_colsel.js`
  (collod 하네스 패턴 — vm 로 admin.js 로드 + `_metaGraph` 참조 주입 + `_metaGraphRenderDetail` 실 데이터 렌더 캡처) **8/8 PASS**:
  ① plain 컬럼 `.amgr-col-select[data-col]` ② 관계 컬럼 `.amgr-col-head`(캐럿 `.amgr-col-caret[data-coltoggle]` + 선택버튼)
  ③ relcount(→N)·아코디언 body 보존 ④ 구 `.amgr-col-toggle`/`data-colrel` 완전 제거 ⑤ 안내 문구 갱신. 기존 g6build headless 6종
  (agglod/category/collod/edge_visibility/viewportcull/vpack) 무회귀.
- **선택 경로 재사용 실증**: 상세 패널 컬럼 클릭 핸들러는 캔버스 컬럼 노드 클릭·`[data-rtuse]` 행과 **동일한** `_metaGraphShowDetail(colKey)`
  경로 호출 → 새 그래프-모델/선택 상태 로직 0(`_metaGraph.selected` 공유). 캐럿(아코디언)과 선택 버튼은 형제·`stopPropagation` 양쪽 → 이중발화 0.
  diff 적대 리뷰(REV-20260710T230000) **[SUBAGENT: PASS]** — Critical/Major/Minor 0 + a11y nit 2건(캐럿 `aria-controls`+상태중립 label, 선택 버튼 간결 label) 반영.
- **Environment: Windows-browser — pre-commit 라이브 미수행 사유**: 정적 자산이 web 이미지에 baked → 서빙 admin.js/styles.css 에
  변경 반영하려면 merge + `deploy-web` 재배포 선행(§65·§66·§67·graph-focus-selected 동일). 캐시버스터 admin.js/styles.css `?v=20260710-graph-detail-colsel`.
- **POST-DEPLOY win-browser 육안 검증(예정, T75.4)**: 그래프 로그인(https://localhost/admin, switchTab('graph')) → 스키마·테이블 펼침 →
  테이블 노드 클릭 → 상세 패널 컬럼 목록에서 컬럼(plain/관계 모두) 클릭 → **상세가 그 컬럼 뷰로 전환** + 그래프에서 해당 컬럼 강조(렌더된 경우)
  + 관계 컬럼 캐럿(▸)은 여전히 인플레이스 아코디언 펼침(선택과 독립) + 레이아웃 무붕괴 + pageerror 0.
  **[POST-DEPLOY 갱신 예정]** 배포 후 자산 curl 확증(서빙 admin.js 에 `.amgr-col-select`·버스터 `20260710-graph-detail-colsel`) + win-browser 육안 PASS append.

### Run (2026-07-10) — cull-refkeep: 뷰포트 컬링 참조·상호작용 보존 (Major §12.3 — feature-0003 web/UI 자산, frontend-only, 정본 feature-0016 TASK §76/ADR-037) — **Environment: Windows-browser**
- 변경: `_faKeep`/`_clusterHasFocus` 헬퍼 + 3 컬 지점(클러스터·루틴·테이블) 예외 가드. 선택 노드의 관계 상대(focusAdj)를 화면 밖이어도 방출 → 관계선 렌더 + 상세 네비 팬 복원. 무선택 시 예외 0(컬링 무손실).
- **pre-commit 정적/실측 검증 PASS**: `node --check admin.js` PASS · headless `test_g6build_cullrefkeep.js` **10 PASS**(뷰포트 내 노드 엣지 컬링무효 — 무선택 in-view 연결 상대 방출·무연결 컬링 + focusAdj 중복커버 + nodePosAll) + 회귀 169 = **179 PASS** · §18.8 적대 리뷰(REVIEW.md). 캐시버스터 `admin.js?v=20260710-cullrefkeep`.
- **Environment: Windows-browser — pre-commit 라이브 미수행 사유**: 정적 자산 web 이미지 baked → merge + `deploy-web` 후에만 서빙 자산 실측 가능. win-browser relay 시각검증 가능(PB-0008) → POST-DEPLOY.
- **POST-DEPLOY win-browser 실 Windows Chrome 검증(T76.3)**: 대형 그래프 줌인 → 노드 선택 → ① 화면 밖 관계 노드로 **관계선 유지**(참조) ② 상세 패널 관계행 클릭 → **화면 밖 대상으로 카메라 팬**(상호작용) ③ 무선택 시 컬링·성능 유지 ④ pageerror 0.
  **[POST-DEPLOY 갱신 예정]** 배포 후 자산 curl(`?v=20260710-cullrefkeep` + `_faKeep`/`_clusterHasFocus`) + win-browser 실측 PASS append.
windows-browser: ITEM-09 graph browser QA (PB-0008) — 로드/클릭/우클릭/드래그/줌/검색/패널, 사용자 환경 게이트

- **CHECK#13 · Environment: Windows-browser — 미수행 사유 (doc-sync-rn-0713, 2026-07-13) 릴리즈노트 콘텐츠·PB-0008 신규 렌더 델타 없음**: 변경은 `release-notes-data.js` 콘텐츠 데이터뿐(렌더 로직 `release-notes.js` 불변·cache-buster 빌드 자동주입) → 새로 Windows-browser 로 시각검증할 UI 렌더 델타 없음(브리지 불가 아님 — 검증 대상 자체가 콘텐츠 데이터라 부적용). 검증: `node --check` PASS + vm 구조검증(블록순서·스키마·누출0). 원천 UI(그래프 §57.4~76·타임아웃 모달 제거·§69 caveats)는 각 원천 cycle POST-DEPLOY PB-0008 이 검증(다수 PASS). 릴리즈노트 실서빙은 본 run 의 make deploy-web(web 재빌드) 후 end-state 검증(라이브 `?v=` 해시 갱신·generated 07-10)으로 확인.

- **CHECK#13 · Environment: Windows-browser — 미수행 사유 (doc-sync-rn-0714, 2026-07-14) 릴리즈노트 콘텐츠·PB-0008 신규 렌더 델타 없음**: 변경은 `release-notes-data.js` 콘텐츠 데이터뿐(렌더 로직 `release-notes.js` 불변·cache-buster 빌드 자동주입) → 새로 Windows-browser 로 시각검증할 UI 렌더 델타 없음(브리지 불가 아님 — 검증 대상 자체가 콘텐츠 데이터라 부적용). 검증: `node --check` PASS + vm 구조검증(28 releases·07-13 블록 8항목·스키마·누출0). 원천 UI(그래프 §77~81·첨부 버전·ds-conn-test)는 각 원천 cycle POST-DEPLOY PB-0008 이 검증(PASS). 릴리즈노트 실서빙은 **cron wrapper 의 web 재빌드**(inject_asset_stamp content-hash 주입) 후 서빙 확인(스킬은 로컬 commit 만 — end-state 검증은 배포 소유자 몫).

### Run (2026-07-14) — anim-effect-pref: 작업 화면 애니메이션 복원 + 인앱 "애니메이션 효과" 설정 (Major §12.3 — feature-0003 web/UI 자산, frontend-only) — **Environment: Windows-browser**
- 변경: `_prefersReducedMotion()` pref-aware 개편(getMotionPref/setMotionPref/applyMotionPref/_osPrefersReducedMotion, localStorage `mad.motionEffect.v1`) + 캘린더/검색 점프 네이티브 smooth `scrollIntoView` → pref-aware `scrollMessagePointIntoCenter` 라우팅 + 프로필 계정 탭 '화면 효과 > 애니메이션 효과' select + `<html data-motion>` init 배선 + `.profile-select-row` 스타일.
- **pre-commit 정적/문법 검증 PASS**: `node --check app.js` PASS · 심볼 배선 확인(getMotionPref/setMotionPref/applyMotionPref/renderMotionPref/motionEffectSelect) · 잔여 네이티브 smooth-into-center `scrollIntoView({behavior:"smooth"})` **0건**(3 타깃 경로 전부 pref-aware 로 수렴) · `os` 기본값 하위호환(미설정 사용자 기존과 동일).
- **Environment: Windows-browser — pre-commit 라이브 미수행 사유**: 정적 자산이 web 이미지에 baked → merge + `deploy-web` 재배포 후에만 서빙 자산 실측 가능(기존 web/UI 자산 cycle 과 동일 패턴). win-browser relay 시각검증 가능(PB-0008) → **POST-DEPLOY 라이브 append 예정**.
- **POST-DEPLOY win-browser 실 Windows Chrome 검증(계획)**: OS "애니메이션 효과" off(or 배터리 절약) 재현 상태에서 — 프로필>계정>화면 효과>애니메이션 효과 **'항상 켬'** 설정 후 ① 좌측 대화 전환 시 **크로스페이드** 복원 ② 우측 가이드 뱃지(point rail) 클릭 시 **부드러운 스크롤 이동** 복원 ③ 날짜 분기선>캘린더>시각 버튼 클릭 시 **부드러운 스크롤 이동** 복원 / **'항상 끔'** 시 즉시 이동 / **'시스템 설정 따름'**(기본) 시 OS 신호 존중 / localStorage 영속(새로고침 유지) · pageerror 0. 서빙 자산 curl(app.js 내 `MOTION_PREF_KEY`/`motionEffectSelect`) 확증.
- **[POST-DEPLOY 갱신 2026-07-14] 라이브 PASS (Environment: Windows-browser, AI 직접 — 실 Windows Chrome via bin/win-browser.py, https://localhost/ bootstrap_admin 세션, 라이브 f00519dd)**: PR #786 머지 → main f00519dd → `deploy-web --web-only` 무중단 롤링(web-a/web-b recreate·90s soak PASS·caddy no-op). `/healthz` git_commit=f00519dd·mysql_ok·pg_ok. **서빙 자산 실측(curl)**: index.html→`app.js?v=b162038f7a10`·`styles.css?v=b162038f7a10`(stamp 갱신) · 서빙 app.js 모션 심볼(MOTION_PREF_KEY/getMotionPref/applyMotionPref/motionEffectSelect) 16 hit · 서빙 styles.css `html:not([data-motion="on"]) .messages-switch-ghost` 1 hit. **런타임 assertion(win-browser eval, 로그인 작업 화면)**: `matchMedia(reduce)=false`(이 머신 reduce off) / `setMotionPref('off')→_prefersReducedMotion()=true`·data-motion=off / `'on'→false`(OS 무관 복원)·data-motion=on / `'os'→OS(matchMedia)와 일치`·data-motion=os / `#motionEffectSelect` 존재·옵션 3종(os:시스템 설정 따름·on:항상 켬·off:항상 끔)·value hydration · `jumpToHistoryAnchor`/`_jumpToSearchMatchedMessage` 소스에 `scrollMessagePointIntoCenter` 라우팅 확인 · 설정 원복 검증. **시각**: 프로필>계정>화면 효과>애니메이션 효과 select 정합 렌더(스크린샷 scratchpad/anim-pref-account-tab.png). pageerror 0.
- **검증 한계(정직 기록)**: 본 검증 Windows 머신은 OS reduce-motion off(matchMedia=false) 상태라 "reduce-motion 하에서 '항상 켬'이 실제 부드러운 모션을 복원"하는 육안 시연은 불가. 단 `'on'→_prefersReducedMotion()=false`(OS 신호 무관)가 크로스페이드 가드·point-rail 애니메이터·캘린더/검색 라우팅 3경로 전부를 구동하는 단일 게이트이므로 복원 로직은 결정적으로 실증됨. 사용자(reduce-motion 활성 환경)의 '항상 켬' 육안 최종 확인 권장.
- **Pass/Fail: PASS** (CHECK#13 충족 — 웹 자산 변경에 이번 cycle Windows-browser Run·POST-DEPLOY 라이브 실측 완료).

### Run (2026-07-14) — account-subtabs: 프로필 '계정' 탭 하위 세분화(계정/알림/UI/사용 내역) (Minor §12.3 — feature-0003 web/UI 자산, frontend-only) — **Environment: Windows-browser**
- 변경: 계정 pane 을 `.profile-subtabs`(4버튼) + 4× `.profile-subpane` 재구성(7섹션→4그룹, id 전부 보존) + `switchAccountSubtab()`(is-active/hidden 토글·하위탭별 lazy 렌더) + `switchProfileTab` 디스패치 변경 + 버튼 리스너 + `.profile-subtabs`/`.profile-subtab` CSS.
- **pre-commit 정적/문법 검증 PASS**: `node --check app.js` PASS · 하위탭 버튼 4·subpane 4·섹션 id(profileNotifySection/profileMotionSection/profileTotpSection/logoutBtn/passwordChangeForm/profileUsage*) 전부 보존 · security-and-account pane div 균형 32/32 · switchAccountSubtab 배선(def+switchProfileTab call+listener).
- **Environment: Windows-browser — pre-commit 라이브 미수행 사유**: 정적 자산이 web 이미지에 baked → merge + `deploy-web` 재배포 후에만 서빙 자산 실측 가능(동일 패턴). PB-0008 → **POST-DEPLOY 라이브 append 예정**.
- **POST-DEPLOY win-browser 실 Windows Chrome 검증(계획)**: 프로필>계정 탭 진입 시 4 하위 탭(계정·알림·UI·사용 내역) 노출 + 기본 '계정' 활성(활동/비번/2FA/로그아웃만 표시) / '알림' 클릭→멘션·데스크톱 토글만 / 'UI' 클릭→애니메이션 효과 select만 / '사용 내역' 클릭→차트 로드(loadProfileUsage 발화) / 하위 탭 전환 상태(state.accountSubtab) 유지 / pageerror 0. 서빙 자산 curl(app.js `switchAccountSubtab`·index.html `data-account-subtab`) 확증.
- **[POST-DEPLOY 갱신 2026-07-14] 라이브 PASS (Environment: Windows-browser, AI 직접 — 실 Windows Chrome via bin/win-browser.py, https://localhost/ bootstrap_admin, 라이브 53e55bfe)**: PR #788 머지 → main 53e55bfe → `deploy-web --web-only`. **1차 soak false-positive 롤백**(edge /healthz 순간 비정상+mysql/pg 정상 — cold-start+insight-worker 동시부하 transient; 정적자산 변경이라 백엔드 /healthz 영향 불가) → **재배포 soak PASS**(web-a/web-b 53e55bfe·caddy no-op). `/healthz` git_commit=53e55bfe·mysql_ok·pg_ok. **서빙 자산 실측(curl)**: app.js `switchAccountSubtab` 5 hit·index.html `data-account-subtab` 4. **런타임 assertion(win-browser eval, 로그인)**: 하위탭 4개[account,notifications,ui,usage]·기본 account 활성·`default_only_account`=true / notifications 클릭→onlyNotif+notifyMentionsChk 존재 / ui 클릭→onlyUI+motionEffectSelect 존재 / usage 클릭→onlyUsage+profileUsageDayChart 존재 / account 복귀→onlyAccount+profileTotpSection·logoutBtn 존재. 각 전환 정확히 1 subpane visible. **시각**: 세그먼트 하위탭 바(계정/알림/UI/사용 내역) 정합 렌더·UI 탭에 '화면 효과>애니메이션 효과' 격리(스크린샷 scratchpad/subtabs-account.png·subtabs-ui.png). pageerror 0.
- **Pass/Fail: PASS** (CHECK#13 충족 — 웹 자산 변경에 이번 cycle Windows-browser Run·POST-DEPLOY 라이브 실측 완료).

- **CHECK#13 · Environment: Windows-browser — 미수행 사유 (doc-sync-rn-0715, 2026-07-15) 릴리즈노트 콘텐츠·PB-0008 신규 렌더 델타 없음**: 변경은 `release-notes-data.js` 콘텐츠 데이터뿐(렌더 로직 `release-notes.js` 불변·cache-buster 빌드 자동주입) → 새로 Windows-browser 로 시각검증할 UI 렌더 델타 없음(브리지 불가 아님 — 검증 대상 자체가 콘텐츠 데이터라 부적용). 검증: `node --check` PASS + vm 구조검증(29 releases·07-14 블록 10항목·스키마·누출0). 원천 UI(메시지 편집·그래프 도움말/카테고리밴드/AI분석·애니메이션/계정탭·결과보기 스크롤)는 각 원천 cycle POST-DEPLOY PB-0008 이 검증(PASS). 릴리즈노트 실서빙은 **cron wrapper 의 web 재빌드**(inject_asset_stamp content-hash 주입) 후 서빙 확인(스킬은 로컬 commit 만 — end-state 검증은 배포 소유자 몫).

- **CHECK#13 · Environment: Windows-browser — 미수행 사유 (doc-sync-rn-0716, 2026-07-16) 릴리즈노트 콘텐츠·PB-0008 신규 렌더 델타 없음**: 변경은 `release-notes-data.js` 콘텐츠 데이터뿐(렌더 로직 `release-notes.js` 불변·cache-buster 빌드 자동주입) → 새로 Windows-browser 로 시각검증할 UI 렌더 델타 없음(검증 대상 자체가 콘텐츠 데이터라 부적용). 검증: `node --check` PASS + vm 구조검증(30 releases·07-15 블록 7항목[admin 6·common 1]·07-14 보존 10·스키마·누출0). **`verify_release_notes.mjs` 33/34 PASS·1 FAIL(스크롤 정규식)** = `styles.css`(본 cycle 미변경) 대상 pre-existing false-negative(규칙 line 4386 `overflow-y:auto` 실재·선택자~속성 사이 설명 주석 길이가 테스트 160자 정규식 창 초과, pristine HEAD 동일 재현) — 본 cycle 무관·feature-0003 소관. 원천 UI(관계도 우클릭/상세/드래그·ENUM 큐·권한·'AI 추론' 콘솔)는 각 원천 cycle POST-DEPLOY PB-0008 이 검증(PASS). 릴리즈노트 실서빙은 **cron wrapper 의 web 재빌드**(inject_asset_stamp content-hash 주입) 후 서빙 확인(스킬은 로컬 commit 만 — end-state 검증은 배포 소유자 몫).

- **CHECK#13 · Environment: Windows-browser — 미수행 사유 (doc-sync-rn-0716b, 2026-07-16) 릴리즈노트 콘텐츠·PB-0008 신규 렌더 델타 없음**: 변경은 `release-notes-data.js` 콘텐츠 데이터뿐(렌더 로직 `release-notes.js` 불변·cache-buster 빌드 자동주입) → 새로 Windows-browser 로 시각검증할 UI 렌더 델타 없음(검증 대상 자체가 콘텐츠 데이터라 부적용). 검증: `node --check` PASS + vm 구조검증(31 releases·07-16 블록 4항목[admin 4]·07-15 보존 7·스키마·누출0). 원천 UI(그래프 검색 확대/결과 목록·상세 [뒤로/앞으로] 탐색·헤딩 hover-pan·콘솔 서브탭 통합)는 각 원천 cycle POST-DEPLOY PB-0008 이 검증(PASS). 릴리즈노트 실서빙은 attended run 의 `make deploy-web`(inject_asset_stamp content-hash 주입) 후 본 run 이 직접 end-state 서빙 검증.
- **CHECK#13 · Environment: Windows-browser — 미수행 사유 (doc-sync-rn-0717, 2026-07-17) 릴리즈노트 콘텐츠·PB-0008 신규 렌더 델타 없음**: 변경은 `release-notes-data.js` 콘텐츠 데이터뿐(기존 07-16 블록에 fixed/work 1항목 추가·렌더 로직 `release-notes.js` 불변·cache-buster 빌드 자동주입) → 새로 Windows-browser 로 시각검증할 UI 렌더 델타 없음(검증 대상 자체가 콘텐츠 데이터라 부적용). 검증: `node --check` PASS + vm 구조검증(31 releases·07-16 블록 5항목[admin 4·work 1]·07-15 보존 7·스키마·누출0) + verify_release_notes.mjs 33/34(1 FAIL=styles.css 스크롤 정규식 pre-existing, 본 cycle 미변경). 원천 UI(작업 화면 ‘연결 테스트’ 버튼)는 원천 cycle POST-DEPLOY PB-0008 이 검증(PASS, 87cbe5d8). 릴리즈노트 실서빙은 **cron wrapper 의 web 재빌드**(inject_asset_stamp content-hash 주입) 후 서빙 확인(스킬은 로컬 commit 만 — end-state 검증은 배포 소유자 몫).
- **CHECK#13 · Environment: Windows-browser — 미수행 사유 (doc-sync-rn-0722, 2026-07-22) 릴리즈노트 콘텐츠·PB-0008 신규 렌더 델타 없음**: 변경은 `release-notes-data.js` 콘텐츠 데이터뿐(07-21 블록 1항목[improved/work] 신규·렌더 로직 `release-notes.js` 불변·cache-buster `?v=dev` 빌드 자동주입) → 새로 Windows-browser 로 시각검증할 UI 렌더 델타 없음(검증 대상 자체가 콘텐츠 데이터라 부적용). 검증: `node --check` PASS + vm 구조검증(07-21 블록 1항목[improved/work]·07-16 보존·스키마·누출0). 원천 UI(진행상황 실시간 전파)는 원천 cycle 이 검증(a999594e — `verify_run_detect_poll.mjs` 23/23 + 실 Windows Chrome 150 유휴탭 실시간 감지 실측·스크린샷 §16.6). 릴리즈노트 실서빙은 **cron wrapper 의 web 재빌드**(inject_asset_stamp content-hash 주입) 후 서빙 확인(스킬은 로컬 commit 만 — end-state 검증은 배포 소유자 몫).

### Run (2026-07-22) — shared-branch-readonly-paging: 공유/그룹·익명 공유-링크 뷰 편집 버전 읽기전용 페이징 (Major §12.3 — feature-0003 web/UI 자산+백엔드, PLAN-APPROVED) — **Environment: Windows-browser**
- **보안 단위(`tests/test_shared_branch_readonly_paging.py`, 10 PASS, mock PG)**: id-범위 술어 경계(floor/anchor inclusive, 밖=차단)·window 스코핑(범위 밖 형제 버전 카운트·sibling_ids 배제=누출 차단)·`_branch_resolve_readonly_leaf` fail-closed(범위밖·비user·없음·None 모두 None). `py_compile`(_conv_store/conversations/share/app) + `node --check`(app.js/share.js) OK.
- **Environment: Windows-browser — PRE-COMMIT 라이브 미수행 사유**: 정적 자산 baked → merge + 배포 후 서빙. **POST-DEPLOY PB-0008 양 surface 라이브 append 예정** — (a) 인앱 공유/그룹 대화 편집 버전 `< n/m >` 읽기전용 페이징, (b) '링크 공유' 익명 뷰 pager. 특히 **범위 밖 버전 미노출(누출 없음)** 실측.
- **Pass/Fail: PRE-DEPLOY 보안단위·문법 PASS · 라이브 = POST-DEPLOY**. CHECK#13 충족(웹 자산 변경에 이번 cycle Windows-browser Run·POST-DEPLOY 계획).

- **[POST-DEPLOY 2026-07-22] shared-branch-readonly-paging 배포 + 양 surface 라이브 검증 (PASS, 시각 잔여)**: PR #887 → main 622b7434 → `deploy-web.sh --web-only`(web-a/b soak PASS). 서빙 share.js `buildShareBranchPager`·app.js `branchView` 반영. **공유-링크(익명 `/api/public/share/{token}`)**: 편집 user 메시지 pager 메타(version 1/2·sibs[1269,1313])·`?branch_view=1313` 읽기전용 다른 버전 전환·`?branch_view=999999999` **fail-closed**(활성 1269 폴백). **인앱 그룹(인증 `/api/history`)**: pager 메타(window-scoped)·`&branch_view` 전환·**active_leaf 불변**(branch_view 후 기본 히스토리 원래 활성 유지=읽기전용, INV-4). **Windows-browser 시각 스크린샷 미수행 — 브리지 다운(Windows Chrome 종료·재기동 실패), §15.4.1 escape(브리지 불가 문서화)**: API end-to-end 양 surface 실측 + 보안 단위 12 PASS 로 보완. 시각 확인은 브리지 복구/사용자 브라우저 잔여.

- **CHECK#13 · Environment: Windows-browser — 미수행 사유 (doc-sync-rn-0723, 2026-07-22) 릴리즈노트 콘텐츠·PB-0008 신규 렌더 델타 없음**: 변경은 `release-notes-data.js` 콘텐츠 데이터뿐(07-22 블록 6항목[fixed 3·improved 3·work] 신규·렌더 로직 `release-notes.js` 불변·cache-buster `?v=dev` 빌드 자동주입) → 새로 Windows-browser 로 시각검증할 UI 렌더 델타 없음(검증 대상 자체가 콘텐츠 데이터라 부적용). 검증: `node --check` PASS + vm 구조검증(33 releases·07-22 블록 6항목[fixed 3·improved 3·work]·07-21 보존·상위 8블록 내림차순·스키마·누출0). 원천 UI(재답변 메시지 복구·'수정' 창 대비·말풍선 공유·상단 흐림·위치 막대·공유 편집 버전 페이징)는 각 원천 cycle POST-DEPLOY PB-0008/실측이 검증(4edb7701/5dbe7992·0ebbac8e/a8fb33d1·7a5b092a/94e2cadd·0db6fc36/109befe1·a92492e6/a70f8382·f0a32980/20562ff9; f0a32980 은 브리지 다운 §15.4.1 escape·API e2e+단위 12 보완). 릴리즈노트 실서빙은 **cron wrapper 의 web 재빌드**(inject_asset_stamp content-hash 주입) 후 서빙 확인(스킬은 로컬 commit 만 — end-state 검증은 배포 소유자 몫).

### Run (2026-07-23) — paging-scroll-preserve: 브랜치 버전 페이징 스크롤 위치 보존 (Minor §12.3 — feature-0003 web/UI 프론트, frontend-only) — **Environment: Windows-browser**
- **PRE**: `node --check` app.js/share.js OK. 스크롤 위치 보존은 layout 의존이라 jsdom 검증 부적합(scroll-restore gotcha: jsdom 은 scrollTop clamp 없이 verbatim 저장 → 실브라우저 0-clamp 미검출) → 실브라우저 실측이 정본.
- **Environment: Windows-browser — PRE-COMMIT 미수행 사유**: 정적 자산 baked → 배포 후 서빙. **POST-DEPLOY headless Chromium/Windows-browser 실측 예정**: 인앱 그룹 + 공유-링크에서 페이징(`< >`) 전후 scrollTop(공유는 window.scrollY) 델타 ≈0(맨-아래 안 튐) 측정.
- **Pass/Fail: PRE 문법 PASS · 라이브 = POST-DEPLOY**. CHECK#13 충족(웹 자산 변경·POST-DEPLOY 계획).

- **[POST-DEPLOY 2026-07-23] paging-scroll-preserve 양 surface 라이브 실측 (PASS)**: PR #889 → main 4ee7ea1d → deploy-web --web-only(soak PASS). 서빙 app.js `preserveScroll`(10)·share.js `savedY`(2) 반영. **인앱 그룹**(Windows Chrome, selectConversation open): 페이징 후 목적지 scrollable(scrollHeight 10235·maxTop 9538)인데 scrollTop=0 유지(맨아래 안 튐)·스크린샷 육안(pager `‹1/2›` 상단). **공유-링크**(짧은 버전→긴 버전 maxY 11535 scrollable): 페이징 후 window.scrollY=0 유지. 양 surface verdict=PRESERVED. layout 의존이라 실브라우저 실측이 정본(jsdom 부적합).

### Run (2026-07-23) — paging-scroll-longhistory: 긴 이력 페이징 스크롤 보존 회귀 수정 (Minor §12.3 — feature-0003 web/UI, frontend-only) — **Environment: Windows-browser**
- PRE: node --check app.js OK. 진단 근거 — 백엔드 branch_view=1289/1299 스레드·버전메타 정상(curl), 프론트 renderCount 리셋(WINDOW_INITIAL_RENDER=3)+window-soon 생략이 긴 스레드에서 브랜치 메시지(pager) 창 밖으로 밀어냄. 수정=preserveScroll 시 전체 렌더.
- Environment: Windows-browser — PRE-COMMIT 미수행(자산 baked). **POST-DEPLOY 실측 예정**: admin '간단한 덧셈 계산' 3→4 페이징 시 pager 유지 + scrollTop 보존.
- Pass/Fail: PRE 문법 PASS · 라이브=POST-DEPLOY. CHECK#13 충족.

### Run (2026-07-23) — conv-date-tree: 좌측 대화목록 날짜 그룹핑 적응형 트리(월/년 집계)·"6월 중복" 혼잡 해소 (Major §12.3 — feature-0003 web/UI 프론트, frontend-only) — **Environment: Windows-browser**
- **PRE**: `node --check` app.js OK. 그룹핑 로직은 순수 함수라 결정적 단위테스트로 정본 검증 — `_buildOwnDateTree` 복제 + now=2026-07-23 주입, 샘플 12건(오늘/어제/이번달 2/6월 3/5월 1/2025 12·11월/2024 8월/날짜미확인): **4/4 PASS** — 6월 top-level 노드 정확히 **1개**(중복 소멸)·항목 3·2025년=branch 월자식 2·__other__ 존재. 사용처 잔존 참조(_getDateGroupKey/_formatDateGroupLabel) 0.
- **Environment: Windows-browser — PRE-COMMIT 미수행 사유**: 정적 자산(app.js/styles.css)이 web 이미지에 baked → merge + `deploy-web` 재배포 후에만 서빙 자산 실측 가능(feature-0003 정적자산 동일 패턴). **POST-DEPLOY PB-0008 라이브 append 예정**: (a) 오래된 대화가 단일 "6월 (N)" 집계 노드로 통합(중복 텍스트 소멸), (b) "2025년" 연 노드 펼침→"12월/11월" 월 서브노드 들여쓰기 중첩, (c) 월/연 개수 배지 렌더, (d) 접기/펼치기 토글·pageerror 0.
- **Pass/Fail: PRE 문법+결정적 단위테스트 PASS · 라이브 = POST-DEPLOY**. CHECK#13 충족(웹 자산 변경에 이번 cycle Windows-browser Run·POST-DEPLOY 계획).

- **[POST-DEPLOY 2026-07-23] conv-date-tree 라이브 검증 (PASS, Environment: Windows-browser, AI 직접 — 실 Windows Chrome 150 via bin/win-browser.py, https://localhost/ bootstrap_admin, 라이브 0b15a0ea)**: PR #893 → main **0b15a0ea** → `deploy-web.sh --web-only`(web-a/web-b 롤링·90s soak PASS·caddy no-op·자산 스탬프 주입). **서빙 자산(curl)**: index.html→`app.js?v=066695609710`·`styles.css?v=066695609710`; 서빙 app.js 신규 심볼(`_buildOwnDateTree`/`_seedAggregateGroupsCollapsedOnce`/`_isAggregateGroupKey`/`conv-date-group-count`) 9 hit·styles.css(`conv-date-group-count/-sub/-label`) 3 hit. **배포본 함수 실행 검증(win-browser eval, 전역 `_buildOwnDateTree` 합성 12건)**: 노드=[오늘 x1, **6월 x3(단일 노드)**, 5월 x1, **2025년 >[12월,11월]**(연>월 중첩), 2024년 >[8월], 날짜 미확인 x1] — 6월 단일 노드·항목 3·2025 branch 월자식 2·2024 branch·__other__·`_isAggregateGroupKey` 6 assertion 전부 PASS. **실계정 사이드바 DOM 실측**: 7월 개별 일자 노드 + **단일 "6월"[배지 38]** + **단일 "5월"[배지 15]** — **duplicateMonthYearLabels=[]**(이전 ~10개 "6월" 중복 소멸). **토글 상호작용**: 6월 헤더 클릭 → 접힘 해제, conv-item 4→42(정확히 배지 38건 등장) = 배지 정확성·상호작용·단일 집계 노드 확증. **시각 스크린샷**: scratchpad/conv-date-tree-live.png(사이드바 단일 6월/5월 집계 노드·개수 배지 정합 렌더). pageerror 0.
- **Pass/Fail: PASS** (CHECK#13 충족 — POST-DEPLOY 라이브 실측 완료. 중복 "6월" 혼잡 해소·월/연 집계·연>월 중첩·개수 배지·토글 전부 라이브 확증).

### Run (2026-07-23) — folder-privacy: 폴더 크로스-계정 노출 차단(admin.js PERMISSION_DEPENDENCIES folder.*.any deps 제거) (Critical §12.3 — cross-cut 정본 feature-0024) — **Environment: Windows-browser**
- **PRE**: `node --check` app.js/admin.js OK · dependency-map 20 passed(folder own 2개만·전부 실 code) · route-parity 라우트 수 불변(217).
- **Environment: Windows-browser — PRE-COMMIT 미수행 사유**: admin.js 변경은 `PERMISSION_DEPENDENCIES` 데이터(권한 의존 트리)에서 folder.*.any 2 엔트리 제거뿐 — 신규 UI 렌더 델타 없음(그리드는 PERMISSION_DEFINITIONS 기준 자동 반영, folder.*.any 는 정의에서도 제거돼 그리드에서 자연 소거). 실제 동작 변경(폴더 크로스-계정 격리)은 백엔드 owner-scope 이며 정적 자산 baked → **POST-DEPLOY 실측**: 계정1(admin) `GET /api/folders` 가 계정10 소유 folder(id 5) 미포함 + admin 콘솔 권한 그리드 folder.*.any 부재.
- **Pass/Fail: PRE PASS · 라이브 = POST-DEPLOY**. CHECK#13 충족(웹 자산 변경·POST-DEPLOY 계획).

### Run (2026-07-23) — graph-node-reveal: "🎯 이 노드로 이동" 미렌더 노드 부모 활성화 노출 (Minor §12.3 — feature-0003 web/UI 자산, frontend-only, 정본 feature-0016 TASK/MODIFY/REPORT graph-node-reveal) — **Environment: Windows-browser**
- **헤드리스 결정론 실증**: 신규 `tests/headless/test_graph_reveal.js` **17 PASS** — 실제 소스에서 `_metaGraphRevealNode` 본문을 추출(사본 아님·소스 결합)해 확장 함수를 test double 로 주입: ① 이미 렌더 fast-path(확장 호출 0) ② 컬럼·스키마 접힘 → 스키마 펼침 후 소속 테이블 컬럼 펼침(정확히 2회·순서) ③ 테이블·스키마 접힘 → 스키마 1회만(컬럼 미호출) ④ 이미 펼친 스키마 → 컬럼만 ⑤ 타 데이터소스(scope 불일치) → 즉시 false·확장 0(교차-scope 오염 방지) ⑥ 함수(Routine, 2세그) → 스키마 1회 ⑦ 활성화해도 끝내 미렌더 → false(호출측 조상 승격 폴백). `node --check --input-type=module` PASS(graph-ctxmenu.js·graph-core.js·graph-state.js).
- **설계 안전성 실측**: 부모 체인 활성화는 신규 그래프-모델 로직 0 — 기존 검증된 async 확장 op `_metaGraphExpandSchema`/`_metaGraphToggleColumns`(각기 `_opSeq` bump·busy·`schemaLoading`/`_metaTableHasCols` 중복 가드)를 **순차 await** 로 재사용. 버튼 핸들러가 async 로 바뀌어도 연타는 기존 가드(schemaExpanded 멤버십·schemaLoading·hasCols)가 중복 fetch 차단. PixiJS 렌더러라 §65/§67 뷰포트 컬링 비활성 → 부모 펼침 후 대상 노드 확실히 renderedIds 방출(`_metaRenderedIdFor` 참). 기존 차단 메시지 "이 노드가 현재 화면에 없습니다…" 제거·잔존 0.
- **Environment: Windows-browser — pre-commit 라이브 미수행 사유**: 정적 자산(ES module)이 web 이미지에 baked → 서빙본에 반영하려면 merge + `deploy-web` 재배포 선행(§57·§65·§67·graph-focus-selected 등 동일 패턴). 실 카메라 팬·스키마/컬럼 펼침 애니메이션은 PixiJS 인스턴스(`_metaGraph.graph`) 의존이라 WSL headless 미재현(오케스트레이션 로직만 격리검증). 캐시버스터는 `?v=dev` 고정 + 빌드 inject_asset_stamp 자동주입(수기 bump 금지).
- **POST-DEPLOY win-browser 육안 검증(TX.5, 예정)**: 그래프 로그인(https://localhost/admin, switchTab('graph')) → **접힌 스키마 소속 테이블/함수, 또는 미펼침 테이블의 컬럼**을 (검색·관계행 등으로) 상세 패널에 띄운 뒤 카드 헤더 `🎯 이 노드로 이동` 클릭 → ① 차단 메시지 미노출(사용자 불편 해소 실증) ② 부모 스키마·(컬럼이면)테이블 자동 펼침 ③ 대상 노드가 화면에 노출·뷰포트 중앙 팬·선택 강조 ④ 상태줄 "→ <노드명> 로 카메라 이동" ⑤ 타 데이터소스 대상 시 소속 상위 객체로 팬 + 검색 유도 안내(graceful) ⑥ pageerror 0. **[POST-DEPLOY 갱신 예정]** 배포 후 자산 curl 확증(`_metaGraphRevealNode` 서빙) + win-browser 육안 PASS append.
- **Pass/Fail: pre-commit 정적·헤드리스 PASS(node --check + test_graph_reveal 17) · 라이브 = POST-DEPLOY**. CHECK#13 충족(웹 자산 변경에 이번 cycle Windows-browser Run·POST-DEPLOY 계획·pre-commit 미수행 사유 기록).

### Run (2026-07-23) — folder-ux: 폴더 UX 6개 개선(무프롬프트·인라인·설정/이동 모달·DnD) (Major §12.3 — cross-cut 정본 feature-0024) — **Environment: Windows-browser**
- **PRE**: node --check app.js OK. 프론트 전용(기존 폴더 API 재사용).
- **Environment: Windows-browser — PRE-COMMIT 미수행 사유**: 정적 자산 baked → merge+deploy 후 서빙. **POST-DEPLOY PB-0008 실측**: 무프롬프트 생성+인라인편집·설정 모달(지침/삭제)·인라인 이름변경·이동 모달(검색/정렬)·DnD(대화↔폴더·폴더↔폴더·root).
- **Pass/Fail: PRE PASS · 라이브 = POST-DEPLOY**. CHECK#13 충족.

### Run (2026-07-23) — analysis-completeness: 'DB 전체 AI 능동 분석' 프론트 2건 — stale 클러스터 병합 수정 + 전체 재분석 경로 (Major §12.3 — feature-0003 web/UI 자산 graph-ctxmenu.js, 정본 feature-0016 TASK/MODIFY/REPORT 20260723T1830-analysis-completeness) — **Environment: Windows-browser**
- **정적·단위 실증**: `node --check --input-type=module` PASS(graph-ctxmenu.js). 백엔드 동반 변경(node_analysis/semantic_cluster/metadata_graph)은 컨테이너 pytest 전체(0002+0003) PASS + 타깃 40 PASS. §18.8 적대 리뷰가 RC3 의 null-clear 안전성을 **전 API 공급원 실사**로 확증(neighborhood/search 는 cluster 필드 미포함→보존, scope_roots/schema_tables 만 항상 포함→서버 정본 값 반영 — 허위 null clear 경로 없음) + RC4 연타 가드(_analyzePending 전 구간 유지) 확인.
- **Environment: Windows-browser — pre-commit 라이브 미수행 사유**: 정적 자산(ES module)이 web 이미지에 baked → 서빙본 반영은 merge + `deploy-web` 재배포 선행(graph-node-reveal 등 동일 패턴). '전체 재분석' confirm 은 window.confirm(네이티브 다이얼로그)이라 headless 로 실 UX 검증 불가. 캐시버스터 `?v=dev` 고정 + 빌드 inject_asset_stamp 자동주입(수기 bump 금지).
- **POST-DEPLOY win-browser 육안 검증(TAC.8, 예정)**: 그래프 로그인 → mysql-local/log_v2 스키마 클러스터 상세 → 'DB 전체 AI 능동 분석' 클릭 → ① "분석 대상 없음" 차단 대신 "전체 재분석" confirm(이번 실행 수치·상한 안내) ② 진행 패널 가동·컬럼 잡 생성 확대(>10, PG node_analysis_jobs Column 카운트) ③ run 완료 후 ≤15분 재클러스터·라벨 갱신(PG rag_objects)·AGE 투영 → 그래프 재로드 시 밴드 갱신·stale 밴드 소멸 ④ 클러스터 상세 패널 그룹 ↔ 캔버스 밴드 정합 ⑤ pageerror 0. **[POST-DEPLOY 갱신 예정]**
- **Pass/Fail: pre-commit 정적·단위 PASS · 라이브 = POST-DEPLOY**. CHECK#13 충족(웹 자산 변경에 이번 cycle Windows-browser Run·POST-DEPLOY 계획·pre-commit 미수행 사유 기록).
- **[POST-DEPLOY 갱신 2026-07-23] PB-0008 Windows-browser 라이브 실측 PASS**: PR #911 main 병합(6600a682) → make deploy-web 무중단 롤링(web-a/b·워커 6600a682, soak PASS) → 신자산 서빙 curl 확증(전체 재분석/forceAll 심볼 4건). 실 Windows Chrome 실측(mysql-local/log_v2): **① '전체 재분석' confirm PASS** — "테이블 18개 · 함수/프로시저 14개는 모두 분석 완료… 이번 실행 32개"(2차 dry_run 수치) 캡처, 차단 메시지 미노출 → run a0fa57bc 시작(진행 패널 가동) **② 컬럼 잡 175개**(>10, run 237/237 done·failed 0) + column_descriptions 175행(introspect) **③ run 완료 후 신선도 재클러스터**(mark 20:44)·AGE 즉시 투영 → 그래프 재로드: 분석 기반 새 밴드 4종 렌더 **④ 캔버스 밴드 ↔ 클러스터 상세 패널 그룹 라벨·개수 완전 정합**("로그 메타데이터 카탈로그 11"·"오류·예외 감사 로그 4" 등), stale 밴드 소멸 **⑤ pageerror 0**. 스크린샷: artifacts/feature-0016-metadata-graph/20260723-analysis-completeness/01·02.png. CHECK#13 실충족.

- **CHECK#13 · Environment: Windows-browser — 미수행 사유 (doc-sync-rn-0724, 2026-07-23) 릴리즈노트 콘텐츠·PB-0008 신규 렌더 델타 없음**: 변경은 `release-notes-data.js` 콘텐츠 데이터뿐(07-23 블록 7항목[new 2·improved 4·fixed 1·work 5·admin 2] 신규·렌더 로직 `release-notes.js` 불변·cache-buster `?v=dev` 빌드 자동주입) → 새로 Windows-browser 로 시각검증할 UI 렌더 델타 없음(검증 대상 자체가 콘텐츠 데이터라 부적용). 검증: `node --check` PASS + vm 구조검증(34 releases·07-23 블록 7항목·07-22 보존·상위 8블록 내림차순·스키마·누출0). 원천 UI(대화 폴더·폴더 지침·날짜 트리·우클릭 메뉴·페이징 스크롤·추론 타임라인·DB 전체 분석)는 각 원천 cycle POST-DEPLOY PB-0008/실측이 검증(폴더 9392cf51/e3fec503/0a1378f3/1a2f2595·날짜트리 8b384b8a·우클릭 b51f93e9·페이징 fce9ab2b/5d0f8467·추론타임라인 a17fd1a7·DB분석 6da5e621). graph-node-reveal 은 자체 POST-DEPLOY PB-0008 미기록이라 릴리즈노트 제외(보류). 릴리즈노트 실서빙은 **cron wrapper 의 web 재빌드**(inject_asset_stamp content-hash 주입) 후 서빙 확인(스킬은 로컬 commit 만 — end-state 검증은 배포 소유자 몫).

### 20260724T031956-graph-emoji-color 그래프 뷰 테이블 노드 역할 이모지 검은 실루엣 렌더 수정 (Minor §12.3, 2026-07-24, feature-0003 web/UI · feature-0016 그래프 cross-cut) — **Environment: Windows-browser (PixiJS WebGL 캔버스의 색 이모지 컬러 글리프 렌더 여부는 실 GPU 래스터+OS 색 이모지 폰트가 필요해 headless/jsdom 실측 정본 아님 — de-risk=`node --check --input-type=module` PASS + 순수 유닛 `test_pixi_adapter.js` T20b 16-assert(역할 아이콘 8종+🗂 감지·평문/−/ƒ/한글 비-매칭·null 안전) + 전체 112 PASS/0 FAIL + §18.8 적대 리뷰(프론트/렌더 렌즈) + 기존 설계 seam(비-hex→Text 강등) 동형 편입 근거, 정적 자산 web 이미지 baked → 라이브 PB-0008 배포 후 잔여, visual_verification_scope: always)**
- **의도**: 분석 완료 테이블 노드의 역할 이모지(📊👤💳📜🔗⚙️📘📦)가 검은 실루엣이 아닌 **고유 컬러**로 렌더되는지, 평문 라벨(컬럼/테이블명)은 회귀 없이 그대로인지 실 Windows 브라우저에서 확인. dark 역할(stats/account/transaction/log/mapping) 칩의 이모지 색 정상 여부가 핵심.
- **PRE-COMMIT 정적·단위 (PASS)**: `node --check --input-type=module graph-renderer-pixi.js` PASS · `tests/headless/test_pixi_adapter.js` **112 PASS / 0 FAIL**(기존 96 회귀 0 + 신규 T20b hasEmoji 16). PixiJS WebGL canvas 색 이모지 실 렌더는 headless 실측 불가(정본=PB-0008) — 근본원인·수정 로직·소비처 계약은 순수 유닛+적대 리뷰로 de-risk.
- **POST-DEPLOY PB-0008 Windows-browser 라이브**: 배포(web-only, deploy_scope: included) 후 잔여 — `bin/win-browser.py` relay 로 실 Windows Chrome `https://localhost/admin` 로그인 → 그래프 뷰 진입 → 분석 완료 테이블 있는 데이터소스에서 역할 이모지 컬러 렌더 실화면 확인.
- **POST-DEPLOY PB-0008 Windows-browser 실측 — PASS (Environment: Windows-browser, 2026-07-24, 배포 c709ad3f 후, 실 Windows Chrome via `bin/win-browser.py` relay, https://localhost)**: eval "1+1"=2 relay 게이트 통과. 서빙 `/static/graph/graph-renderer-pixi.js`(54,071B)에 `hasEmoji`(2회)·게이트 `!PixiAdapterPure.hasEmoji(text)`·emoji 폰트 스택('Segoe UI Emoji'·'Noto Color Emoji'·'Apple Color Emoji') 존재 curl 확증. **핵심 실측**: 버그 유발 조건 그대로(dark 역할 labelFill=`#161b22` + emoji 폰트 스택) canvas 2D `fillText`(=PIXI.Text 내부 경로)로 역할 아이콘 9종 렌더 후 getImageData chroma 측정 — 📊 chroma=217·💳 255·📜 75·📘 177·📦 214·🗂 255 (컬러 렌더 확증), 👤·🔗·⚙️ chroma=0 (Segoe UI Emoji 가 원래 그레이스케일로 디자인한 BUST/LINK/GEAR — flat 단색 실루엣이 아닌 실제 글리프·내부 디테일 보존). 9종 전부 **flat #161b22 틴트 실루엣이 아니라 폰트 실 글리프**로 렌더 → "검은색 실루엣" 증상 해소 확인. web-a/web-b 양 replica c709ad3f soak PASS. 자동화 회귀=T20b 16-assert(전체 112 PASS).

### Run (2026-07-23) — newfolder-btn: '+ 새 폴더' 바 → '새 대화' 우측 폴더 아이콘 버튼 (Minor §12.3 — cross-cut 정본 feature-0024) — **Environment: Windows-browser**
- **PRE**: node --check app.js OK. index.html #newFolderBtn 추가·styles.css .btn-new-folder.
- **Environment: Windows-browser — PRE-COMMIT 미수행 사유**: 정적 자산 baked → merge+deploy 후 서빙. **POST-DEPLOY PB-0008**: 헤더 폴더 아이콘 노출·클릭 생성·바 제거·DnD root.
- **Pass/Fail: PRE PASS · 라이브 = POST-DEPLOY**. CHECK#13 충족.

### Run (2026-07-24) — feature-0025 워커 성능·병렬 처리 설정 서브탭 (Major §12.3 — feature-0003 web/UI 자산 admin.html/admin.js, 정본 feature-0025 TASK/FUNCTION/REVIEW) — **Environment: Windows-browser**
- **의도**: 관리 콘솔 `시스템 > 설정`에 신규 '성능·병렬 처리' 서브탭이 렌더되고, runtime_settings `performance` 그룹 10 knob 이 카테고리 4그룹(그래프 노드 분석·cluster_label·사용자 답변 처리·지식베이스 임베딩)으로 표시되며, 값 편집→commit-bar '모두 적용'→override 저장/기본값 복원·nav dirty dot·즉시/재배포 배지·조회전용 게이트(system.runtime.write 무보유)가 기존 서브탭(실행 타임아웃/모델 예산/자가 리뷰)과 정합하게 동작하는지 실 Windows 브라우저에서 확인.
- **PRE-COMMIT 정적·단위 (PASS)**: `node --check` (mjs) admin.js 구문 PASS. runtime_settings `performance` 버킷·accessor·clamp·apply_mode 단위 `test_worker_parallelism.py` 12 PASS(+runtime_settings 회귀 36 PASS). `serialize_registry({})["performance"]` 10행·타 버킷 미누출·RS_PERF_KEYS(10)==_PERF_SPECS(10) 대조.
- **Environment: Windows-browser — PRE-COMMIT 라이브 미수행 사유**: 정적 자산(admin.html/admin.js)이 web 이미지에 baked → merge + `deploy-web` 재배포 후에만 서빙 자산 실측 가능(feature-0003 정적자산 동일 패턴). 관리 콘솔 렌더는 배포된 환경에서만 확인 가능. 캐시버스터 `?v=dev` 고정 + 빌드 inject_asset_stamp content-hash 자동주입(수기 bump 금지). **POST-DEPLOY PB-0008 라이브 append 예정**: (a) 서브탭 노출·category 4그룹 렌더, (b) 값 편집→'모두 적용'→override 저장·기본값 복원, (c) nav dirty dot·즉시/재배포 배지, (d) 조회전용 게이트, (e) 이어서 동시성 override(예: 노드 분석 4·답변 3) 후 워커 재시작 → '운영 현황'의 노드분석/cluster_label/답변 처리량 증가 관측·pgbouncer 풀 소진 무경보. pageerror 0.

### 20260724T181106-brandnew-script-attachment assistant 신규 스크립트 첨부 전달 (Major §12.3, 2026-07-24, primary feature-0003 + cross-ref feature-0002) — **Environment: Windows-browser (attachment-new 블록으로 새 첨부 생성→첨부 목록·말풍선 칩 렌더→다운로드는 실 브라우저 + 배포된 ask-worker 프롬프트 + web materialize + 라이브 LLM turn 이 필요해 headless/pre-deploy 대체 불가 — de-risk=`node --check` PASS + pytest 2369 PASS(신규 test_attachment_new.py 27: parse/spans/materialize root/확장자 allowlist/RBAC/공유cap/strip/프롬프트/ask배선) + §18.8 AGENT-TEAM(security MAJOR RBAC + backend MINOR) 반영, 정적 자산 web 이미지 baked → 라이브 PB-0008 배포 후 잔여, visual_verification_scope: always)**
- **자동 검증 — PASS**: `python -m pytest`(repo-agent) feature-0002+0003 전체 **2369 passed / 2 skipped / 0 failed**. 신규 `test_attachment_new.py`: 파서 견고성·edit/new 공존 경계(test_p5)·본문내 상대태그 한계 고정(test_p6)·root INSERT(v1·RootAttachmentId=NULL)·확장자 allowlist(실행형→.txt·이중확장자 정화)·업로드 RBAC deny·공유 개수 예산·strip 안내·프롬프트 drift-proof 주입·ask 배선. `py_compile` 4파일 · `node --check app.js` PASS.
- **Environment: Windows-browser — PRE-COMMIT 라이브 미수행 사유**: attachment-new 경로는 배포된 ask-worker(신규 프롬프트 지침) + web(신규 materialize) + 실 LLM turn 이 있어야 end-to-end 발화되므로 pre-deploy/headless 로 실 UX(첨부 칩 렌더·다운로드) 검증 불가. 정적 자산(app.js)은 web 이미지 baked → merge + `deploy-web` 후 서빙 반영.
- **POST-DEPLOY PB-0008 라이브 append 예정**: (a) "스크립트를 첨부파일로 전달(답변 본문 아닌)" 요청 → assistant 가 attachment-new 로 .sql 첨부 생성, (b) 첨부 목록·assistant 말풍선에 "AI 생성" 배지 + 다운로드 칩, (c) 본문에 전체 스크립트 미노출·"📎 첨부 전달" 안내, (d) 원 마찰 대화(…f1c535ec) 동일입력 재현으로 거부 소멸 확인. pageerror 0.

## TASK-20260727T010501-doc-sync-rn-0727 — 릴리즈노트 2026-07-24 블록 (비-정책 doc-only)
- **Environment: Windows-browser (PB-0008)** — 미수행(사유): 본 변경은 사용자향 릴리즈노트 콘텐츠 데이터(`release-notes-data.js`) 8항목 + generated 갱신만이며 렌더 로직(`release-notes.js`)·제품 코드·캐시버스터(`?v=dev` 빌드 자동주입, 수기 편집 0) 무변경. 무인 cron doc_sync 라 인터랙티브 win-browser 브리지 미가동·배포=wrapper(post-merge). pre-commit 정적 검증 = `node --check`(문법) PASS + vm 구조검증(releases +1·head 8항목·이전 블록 보존·스키마·누출0). 각 항목의 실제 UI 동작은 owning feature 의 POST-DEPLOY PB-0008(Windows-browser)에서 이미 라이브 검증됨(sql 35d6453f·csv 8bf643e0·reanswer 28ec78b3·newfolder f697eddf·share-scroll 5c9d5bf2·share-rail 6290ae1e·metadata-review c7e928c8·graph-emoji 791d5761). CHECK#13 충족(웹 자산 변경=릴리즈노트 데이터, Windows-browser 미수행 사유 기록).

## TASK-20260728T010301-doc-sync-rn-0728 — 릴리즈노트 2026-07-27 블록 3항목 append (비-정책 doc-only)
- **Environment: Windows-browser (PB-0008)** — 미수행(사유): 본 변경은 사용자향 릴리즈노트 콘텐츠 데이터(`release-notes-data.js`) 3항목 append + block summary 증강만이며 렌더 로직(`release-notes.js`)·제품 코드·캐시버스터(`?v=dev` 빌드 자동주입, 수기 편집 0) 무변경. 무인 cron doc_sync 라 인터랙티브 win-browser 브리지 미가동·배포=wrapper(post-merge). 릴리즈노트 전용 render 테스트(`tests/verify_release_notes.mjs`)는 **jsdom 미설치**(env 제약)로 미실행 — render 로직 미변경이라 대상 아님. pre-commit 정적 검증 = `node --check`(문법) PASS + vm 구조검증(releases[0].date=2026-07-27·items 4→7·releases[1] 2026-07-24 보존·스키마 type/area/title/detail·enum 유효·누출0). 각 항목의 실제 UI 동작은 owning feature 의 POST-DEPLOY PB-0008(Windows-browser)에서 이미 라이브 검증됨(opus5 413703b9·share-bar 2ec5e0aa·detail-db-groups 42ee04d0). CHECK#13 충족(웹 자산 변경=릴리즈노트 데이터, Windows-browser 미수행 사유 기록).

## 20260728T160400-graph-label-lod 과도한 줌아웃 시 라벨(글자) 붕괴 최소화 + 라벨/draw 비용 관측 구조 (Minor §12.3, 2026-07-28, cross-cut 정본 feature-0016-metadata-graph) — **Environment: Windows-browser (실 Chrome 150 relay, PRE-LANDING PASS — 라벨 렌더 품질은 GPU 샘플링 의존이라 headless 가 검증 불가: 헤드리스는 방출 계약만 고정하고 품질·증상 소멸 판정은 실 브라우저가 담당, visual_verification_scope: always)**
- **자동 검증 — PASS**: 신규 `tests/headless/test_g6build_labellod.js` **36 PASS**(임계·헤더우대·col-lod 겹침·band-invariant·미니맵서명·밴드양자화 7·관측·**오독-가드 게이트 5**) + 회귀 **16 스위트 502 PASS** + PixiJS 어댑터 **190 PASS** = 합계 **728 PASS / 0 FAIL**. §18.8 codex-review 가 적발한 P2 2건(배지-단독 억제 구간 오독-가드 구멍 · 소수 폰트 임계 교차를 놓치던 정수 밴드 양자화)을 in-cycle 수정하고 신규 8건(F5~F7·H1~H5)으로 고정 — 수정 전 재현(구 구현 MISS) 확인. `node --check --input-type=module` PASS(graph-state·graph-core·graph-renderer-pixi). 캐시버스터 `?v=dev` 고정 + 빌드 inject_asset_stamp content-hash 자동주입(수기 bump 0).
- **PRE-LANDING PB-0008 (PASS)**: 라이브 이미지 격리 컨테이너에 변경 3파일 스탬프 정합 주입, `mssql-qa-idc`(스키마 135개·객체 231). ① before/after 실촬로 깨진 글자 노이즈 **완전 소멸** ② zoom 0.126 라벨 215/215·헤더 141/141·badge 135 억제 → `labelsCreated 0` ③ zoom 0.325 헤더 우대 실동작(본문 74 억제·헤더 0) ④ 상태줄 '이름표 표시 축약' 마커 노출 ⑤ **zoom 0.7713 복귀 dropped 0·labelsCreated 215·마커 소멸 = 정보 손실 0 실증** ⑥ pageerror 0.
- **POST-DEPLOY PB-0008 1-probe — PASS**(TL.10, 2026-07-28): PR #1019 → main `2a843acd` → `make deploy-web`(soak 통과) → edge `/healthz git_commit=2a843acd`. 서빙 자산(`?v=c9ce5fe33b65`)에 두 P2 수정 존재 확인 후 실 Chrome relay 로 `mssql-qa-idc`(스키마 136개) 검증 — ②~⑥ 전건 PASS + **P2 수정이 만든 두 표면 실증**: ⑦ 배지-단독 구간(zoom 0.3943·0.4929, `dropped 0`+`badgesDropped 136`)에서 오독-가드 마커 **노출**(수정 전이라면 꺼져 개수 배지 136개 무음 소실) ⑧ 라이브 밴드에 `9.5/9`·`16/10.5`·`10.5/9` 등 정수 격자로 표현 불가한 반포인트 경계값 출현. pageerror 0. 한계·부수 관측은 test-runs.d §10 에 정직 병기. deploy_scope: included — merge 후 자동 배포.
- **Pass/Fail: PASS**. CHECK#13 충족. 상세 Run: `docs/test-runs.d/20260728T160400-graph-label-lod.md`. 정본 TASK/DECISION: `unit/feature-0016-metadata-graph/docs/TASK.md` `## 20260728T1604-graph-label-lod`.

## 20260728T181000-graph-hdr-label-fit 위계 헤더 라벨을 클러스터 범위 + 화면 하한에서 파생 (Minor §12.3, 2026-07-28, cross-cut 정본 feature-0016-metadata-graph) — **Environment: Windows-browser (줌 의존 렌더 기하라 실 브라우저 카메라 필요 — headless 는 방출 계약만 고정; 정적 자산 web 이미지 baked → 라이브 PB-0008 배포 후 HF.6, visual_verification_scope: always)**
- **자동 검증 — PASS**: `test_g6build_labellod.js` **36 → 71 PASS**(신규 35 — Section I 유닛 12: 폰트 파생/박스 상한/단조/밴드 클램프/폴백 · Section J 결합 11: 실 `_metaG6Build` 방출·칩 하단 고정·**멤버 좌표 불변(reflow 0)**·CATH 동일 적용·밴드 반동 합류 · **Section K 리뷰흡수 10**: 칩 hit 영역 상한·**이웃 블록 bbox 침범 0**·폰트 유지·알약 소프트닝·zoom 1 회귀 0·products 게이트·`/h` 부재 · B5 계약 재진술 2). 헤드리스 **전 스위트 21개 910 PASS / 0 FAIL**. `node --check --input-type=module` PASS(graph-state·graph-core). 캐시버스터 `?v=dev` 고정 + 빌드 content-hash 자동주입(수기 bump 0).
- **개선 실측**: `group-hd` 억제 시작 zoom **0.3048 → 1열 0.1416 / 2열 0.0642 / 3열 이상 0.0500(줌 하한)**; 실측 개요 줌 0.2524 화면 크기 **2.65px → 2열 이상 10.5px(= base 그대로)**. `cat-hd` 는 0.2667 → 0.1405~0.0500, 3.03px → **12.0px**.
- **회귀를 테스트가 잡은 사례(기록)**: 반동 밴드에 상한 클램프를 넣지 않았을 때 기존 **F3·F7('무의미 rebuild 차단')이 실제로 FAIL** 했다 — `base/z > MAX` 부터 폰트가 z-무관인데 스텝이 계속 늘어 극단 줌아웃 휠마다 무변화 rebuild 가 걸렸다. 그 실측을 근거로 `_META_HDR_FIT_STEP_CAP` 도입.
- **POST-DEPLOY PB-0008 — PASS**(HF.6, 2026-07-28): PR #1025 → main `4ea1d83b` → `make deploy-web`(soak 통과) → edge `/healthz git_commit=4ea1d83b` + 서빙 자산(`?v=723750d86605`)에 `_metaHdrFitFont`·`GH_CHIP_MAX` 존재 확인 후 실 Chrome relay 로 `mysql-gz-qa-global`/`gunzgame`(421 객체·위계 헤더 84개) 검증 — **zoom 0.1468 에서 본문 라벨 534/587 억제(색 블록만)인데 컨텐츠 카테고리 헤더는 판독 가능하게 유지**(종전 고정 10.5px 억제 임계 0.3048 → 이 줌에서 전부 사라졌을 구간) · 제품 카테고리 밴드 헤더 동일 · `headerDropped` 0.6078~0.249 전 구간 0 · **반동 밴드 줌아웃 h2→h9 단조 · 줌인 h7→h1 대칭 복귀(stale 0)** · 칩이 위 행 블록과 무겹침(P1 수정 육안) · 알약 소프트닝 수용 가능 · pageerror 0. 한계는 test-runs.d §9 에 정직 병기.
- **Pass/Fail: PASS**(PRE-COMMIT). CHECK#13 충족. 상세 Run: `docs/test-runs.d/20260728T181000-graph-hdr-label-fit.md`. 정본: `unit/feature-0016-metadata-graph/docs/TASK.md` `## 20260728T1810-graph-hdr-label-fit`.

## TASK-20260729T010301-doc-sync-rn-0729 — 릴리즈노트 2026-07-28 블록 6항목 append (비-정책 doc-only)
- **Environment: Windows-browser (PB-0008)** — 미수행(사유): 본 변경은 사용자향 릴리즈노트 콘텐츠 데이터(`release-notes-data.js`) 6항목 append + block summary 증강만이며 렌더 로직(`release-notes.js`)·제품 코드·캐시버스터(`?v=dev` 빌드 자동주입, 수기 편집 0) 무변경. 무인 cron doc_sync 라 인터랙티브 win-browser 브리지 미가동·배포=wrapper(post-merge). 릴리즈노트 전용 render 테스트(`tests/verify_release_notes.mjs`)는 **jsdom 미설치**(env 제약)로 미실행 — render 로직 미변경이라 대상 아님. pre-commit 정적 검증 = `node --check`(문법) PASS + vm 구조검증(releases[0].date=2026-07-28·items 3→9·releases[1] 07-27 보존·스키마·enum·누출0). 각 항목의 실제 UI 동작은 owning feature 의 POST-DEPLOY PB-0008(Windows-browser)에서 이미 라이브 검증됨(역할배지 2b9693c7·이웃깊이 0bff005e·상세hover fb253fe3·모델권한 fcf22ceb 등). CHECK#13 충족(웹 자산 변경=릴리즈노트 데이터, Windows-browser 미수행 사유 기록).

## 20260729T093000-graph-hdr-label-typo 위계 헤더 라벨 재설계 — 레벨별 단일 크기 + 예약 행 완전 수용 (Minor §12.3, 2026-07-29, cross-cut 정본 feature-0016-metadata-graph) — **Environment: Windows-browser (줌 의존 렌더 기하 + 시각 품질 판정이라 실 브라우저 필요; 정적 자산 web 이미지 baked → 라이브 PB-0008 배포 후 HT.9, visual_verification_scope: always)**
- **사용자 시각 피드백 대응**: hdr-label-fit(20260728T1810) 배포 후 "디자인적으로 모범적이진 않은 것처럼 시각적으로 불편" → 라이브 확대 3× + **방출 기하 덤프**로 6개 결함 실측(형제 폰트 24.6/27.1/30.1 제각각 · 칩이 텍스트보다 큰데도 알약 `fillOpacity 0.45` · 위계 역전 · ellipsis 증가 · 팔출로 테두리 물림 · 라벨이 박스보다 주인공) → 근본 원인 = **박스별 연속 폰트 + 상방 팔출**.
- **자동 검증 — PASS**: `test_g6build_labellod.js` **72 PASS**(Section I·J·K **전면 재작성** 35건 — I: 폐기 API(`_metaHdrFitFont`) 잔재 0 · **arity 3(박스 미수용 = 형제 동일 크기의 구조 보장)** · 전 줌 스윕 위계 비역전 · 상한/단조/폴백/스텝 클램프 · J: 실 방출에서 형제 폰트 집합 크기 1 · 알약 스타일 전원 동일 · **칩이 박스 상단 위로 안 나감(팔출 0)** · 칩이 멤버 영역 무침범 · 칩 높이 ≥ 폰트(알약 수용) · 라벨 폭 ≤ 가용폭 · reflow 0 · zoom 1 회귀 0 · CATH 동형 + 부모>자식 · 밴드 반동 합류 · K: products 게이트). 헤드리스 **전 스위트 21개 940 PASS / 0 FAIL** · `node --check` PASS(2 파일). §18.8 codex-review PASS-WITH-FIXES(P1 0 · P2 1건 흡수 — 밴드 스텝 상한을 레벨 스펙에서 파생; **첫 초안 테스트가 검증점 하드코딩으로 그 결함을 놓쳤고 클램프 지점을 파생한 뒤 재현판 FAIL 확인**).
- **배포 전 기하 시각 대조(신규 기법)**: 구/신 번들의 **방출 기하를 그대로 렌더**해 나란히 비교했다 — 헤드리스가 판정 못 하는 '시각 정합성'을 GPU 없이 기하 수준에서 사전 확인하는 값싼 게이트. 증적 `artifacts/feature-0016-metadata-graph/20260729-graph-hdr-typo/geom_old_vs_new_z022.png`(+ 라이브 결함 크롭 2매).
- **개선/대가 실측**: 억제 시작 줌 `group-hd` 0.3048 → **0.1600(1.91배)** · `cat-hd` 0.2667 → **0.1333(2.00배)**. 1차 구현(0.05)보다 **후퇴**했고 이는 의도된 교환이다 — 극단 줌아웃 이득이 정확히 사용자가 지적한 불편(팔출·박스별 폰트)에서 나왔다.
- **POST-DEPLOY 잔여(HT.9)**: ① 형제 헤더 크기 일치 ② 알약이 텍스트를 감쌈 ③ 밴드 헤더 > 컨텐츠 카테고리 ④ 라벨이 박스 안(테두리 물림 0) ⑤ 잘림 감소 ⑥ pageerror 0. deploy_scope: included.
- **POST-DEPLOY PB-0008 — PASS**(HT.9, 2026-07-29): PR #1037 → main `50c5a854` → `make deploy-web` → edge `/healthz git_commit=50c5a854` + web-a/web-b `mysql-ai-web:50c5a854`, 서빙 자산(`?v=6133a5e9907a`)에 신설 `_hdrLevels` 7회 / 폐기 `_metaHdrFitFont`·`STEP_CAP` **0회** 확인 후 실 Chrome relay 로 `mysql-gz-qa-global`/`gunzgame`(421 객체·위계 헤더 84개 — HF.6 과 동일 조건) 검증 — **① 형제 헤더 전원 동일 크기**(구 24.6/27.1/30.1 편차 소멸) · **② 알약이 전 헤더에서 텍스트를 감쌈**(소프트닝 분기 없이 동일 스타일) · **③ 밴드 헤더 > 컨텐츠 카테고리**(부모 상한 24 > 자식 20) · **④ 84개 칩 전량이 예약 행 안쪽, 테두리 물림 0**(팔출 소멸) · **⑥ pageerror 0**. **밴드 불변 라이브 확증**: `h2`→`h3` 전이 후 줌아웃 하한(0.1119)까지 `h3` 고정 — 구 구현(상한 4)이라면 z≈0.4579 에서 걸렸을 헛 rebuild 가 없다(codex P2 수정). 억제 시작 줌도 예측 정합(0.1749 까지 81/84 유지 → 0.1399 에서 83 → 0.1119 전량) · 줌인 복귀 대칭(0.1526 → 0.1907, hdrDropped 83→3). **⑤ 잘림 감소는 "부분"**: 폰트 상한 64→20/24 로 폭 여유는 구조적으로 커졌으나 라이브 긴 한글 헤더에서 ellipsis 는 여전히 관측되고, 구 배포본과의 직접 대조는 불가(이미지 교체됨) — test-runs.d §6 에 정직 병기.
- **Pass/Fail: PASS**(PRE-COMMIT + POST-DEPLOY). CHECK#13 충족. 상세 Run: `docs/test-runs.d/20260729T1140-graph-hdr-typo-postdeploy.md`. 정본: `unit/feature-0016-metadata-graph/docs/TASK.md` `## 20260729T0930-graph-hdr-label-typo`.

### Run (2026-07-29) — metadata-product-scope (지식베이스 메타데이터 스코프 축 datasource → 제품) — **Environment: container(make test)**

- **PRE-COMMIT — PASS**: `make test` 전 스위트(agent 격리 컨테이너, `--no-deps` + 라이브 DB 차단
  env) PASS · ruff clean. route-parity 골든은 신규 `GET /api/admin/metadata/scopes` 1건 증분(222→223).
- **신규 커버리지**: 제품 축 전환(활성 제품 기반 scope 도출 · 같은 제품이면 활성 DS 무관 동일 scope) ·
  공유 datasource 의 제품별 scope 분리 · 골격 후보 제품 접근DB 한정 + allowlist 밖 404(introspection
  미도달) · 카탈로그 미가용 fail-closed(503) · 호출자 `datasource` override 무시 · 레거시 접근DB
  행/단일 바인딩 폴백 · MSSQL DB allowlist 대소문자 무관 + 원본 케이스 연결 · expand/contract 꼬리
  읽기 on/off · "제품 없음" vs "해소 실패" 신호 구별 · ENUM self-heal 제품 스코프 sweep(단일 DS 한정).
- **이관 dry-run(라이브 대조)**: 판정 5,405건 = single 2,004 · schema 3,126 · ambiguous 257 ·
  common 18. `--migrate --purge-ambiguous` 계획 update 5,130 / delete 257. `--verify-contract` 잔여
  5,387(이관 전이므로 정상).
- **적대 검증**: codex 적대 리뷰 10라운드 — P1 12건 + P2 3건 흡수 후 최종 P1 0건(REVIEW 표 참조).
- **POST-DEPLOY**: 라이브 이관 → contract → PB-0008 실 Windows 브라우저 시각검증 예정
  (`visual_verification_scope: always`). 결과는 `docs/test-runs.d/20260729T2130-metadata-product-scope.md` 에 append.
- **Pass/Fail: PASS**(PRE-COMMIT). 상세 Run: `docs/test-runs.d/20260729T2130-metadata-product-scope.md`.
  정본: TASK `20260729T2130-metadata-product-scope`.

### Run (2026-07-29) — metadata-product-scope POST-DEPLOY — **Environment: Windows-browser (PB-0008)**

- 배포본 `5060c9f3` 위에서 **라이브 이관(update 5,130 · delete 257 · 백업 5,387행) + contract
  (`AGENT_KB_LEGACY_DS_SCOPE_READ=0`, 잔여 레거시 0 확인)** 완료.
- PB-0008 실 Windows Chrome 검증 **PASS** — 스코프 선택기 = 제품(17건) · `KR_LIVE` 용어 85건
  렌더(7개 DS 중 1곳에 갇혀 있던 자산 회복 실증) · 공유 datasource 3제품이 각자 접근DB만
  노출(CC 17/DK 35/FH 8) + **교차 접근 404** · 이관 귀속 정확도(DK_QA 153/1,046 · WEB_QA 1,926 ·
  WEB_G_QA 879) · 부트스트랩 안내·단위 라벨 갱신.
- 증거: `artifacts/pb0008/pb0008-meta-krlive.png` · `artifacts/pb0008/pb0008-meta-bootstrap-ccqa.png`.
- **Pass/Fail: PASS**. 상세 Run: `docs/test-runs.d/20260729T2130-metadata-product-scope.md` POST-DEPLOY 절.

## TASK-20260730T010301-doc-sync-rn-0730 — 릴리즈노트 신규 2026-07-29 블록 13항목 prepend (비-정책 doc-only)
- **Environment: Windows-browser (PB-0008)** — 미수행(사유): 본 변경은 사용자향 릴리즈노트 콘텐츠 데이터(`release-notes-data.js`) 신규 date 블록 prepend + `generated` 갱신만이며 렌더 로직(`release-notes.js`)·제품 코드·캐시버스터(`?v=dev` 빌드 자동주입, 수기 편집 0) 무변경. 무인 cron doc_sync 라 인터랙티브 win-browser 브리지 미가동·배포=wrapper(post-merge). 릴리즈노트 전용 render 테스트(`tests/verify_release_notes.mjs`)는 **jsdom 미설치**(env 제약, 함정 #3c)로 미실행 — render 로직 미변경이라 대상 아님. pre-commit 정적 검증 = `node --check`(문법) PASS + 구조검증(releases[0].date=2026-07-29·13 items·releases[1] 2026-07-28 9항목 보존·스키마·enum·누출0). 각 항목의 실제 UI 동작은 owning feature 의 POST-DEPLOY(Windows-browser PB-0008)에서 이미 라이브 검증됨. CHECK#13 충족(웹 자산 변경=릴리즈노트 데이터, Windows-browser 미수행 사유 기록).

## TASK-20260731T010301-doc-sync-rn-0731 — 릴리즈노트 신규 2026-07-30 블록 8항목 prepend (비-정책 doc-only)
- **Environment: Windows-browser (PB-0008)** — 미수행(사유): 본 변경은 사용자향 릴리즈노트 콘텐츠 데이터(`release-notes-data.js`)의 신규 date 블록 prepend + `generated` 갱신뿐이고 렌더러(`release-notes.js`)·HTML·CSS·백엔드 무변경이라 화면 렌더 경로가 바뀌지 않는다. 데이터 정합은 `node --check` + vm 구조검증(블록/항목 수·스키마·enum·내부용어 누출)으로 대체. jsdom DOM 테스트는 이 실행 env 에 jsdom 미설치(컨테이너 전용).

## 20260803T1549-aiops-taxonomy-unmapped — `AI 운영 현황 > 운영 현황` 미분류 활동 3종 재배치 (Minor §12.3, 2026-08-03)
- Run 기록 정본: `docs/test-runs.d/20260803T1549-aiops-taxonomy-unmapped.md` (§5.3 fragment).
- **Environment: pytest** — `test_ai_ops.py` 22 passed(신규 2 포함) · 전체 스위트 EXIT=0 · ruff PASS.
- **Environment: Windows-browser (PB-0008)** — **POST-DEPLOY PASS** (배포 c0c6800f, 실 Chrome 150 relay, https://localhost/admin). 운영 현황 pane 에서 '미분류 활동' 그룹 소멸(텍스트 "미분류" 0회)·인사이트 분석 하위 3행 편입·최근 활동 피드 작업명 노출·기존 카테고리 무회귀. 증거 `artifacts/pb0008/20260803-aiops-taxonomy-unmapped.png`. 상세는 fragment §4.

## TASK-20260804T010301-doc-sync-rn-0804 — 릴리즈노트 신규 2026-08-03·2026-07-31 블록 prepend (비-정책 doc-only)
- **Environment: Windows-browser (PB-0008)** — 미수행(사유): 본 변경은 사용자향 릴리즈노트 콘텐츠 데이터(`release-notes-data.js`) 신규 date 블록 prepend + `generated` 갱신만이며 렌더 로직(`release-notes.js`)·제품 코드·캐시버스터(`?v=dev` 빌드 자동주입, 수기 편집 0) 무변경. 무인 cron doc_sync 라 인터랙티브 win-browser 브리지 미가동·배포=wrapper(post-merge). 릴리즈노트 전용 render 테스트(`tests/verify_release_notes.mjs`)는 **jsdom 미설치**(env 제약)로 미실행 — render 로직 미변경이라 대상 아님. pre-commit 정적 검증 = `node --check`(문법) PASS + 구조검증(releases[0].date=2026-08-03 7항목 · releases[1]=2026-07-31 3항목 · 기존 39 블록 보존 · 스키마·enum·summary·누출0). 각 항목의 실제 UI 동작은 owning feature 의 POST-DEPLOY(Windows-browser PB-0008)에서 이미 라이브 검증됨. CHECK#13 충족(웹 자산 변경=릴리즈노트 데이터, Windows-browser 미수행 사유 기록).

## 20260804T0458-share-join-btn-visibility — 공유 링크 '대화에 참여' 버튼 노출 조건 확대 (Minor §12.3, 2026-08-04)
- Run 기록 정본: `docs/test-runs.d/20260804T0458-share-join-btn-visibility.md` (§5.3 fragment).
- **Environment: pytest** — 신규 `test_share_join_btn_visibility.py` **9 passed** · 회귀 스코프(`-k "share or fork or member or join"`) **98 passed** · `node --check share.js` PASS · ruff PASS. 전체 스위트 동시 실행에서 `test_shutdown_finalizer.py::test_shutdown_finalizer_marks_this_process_processing` 1건 실패했으나 **단독 재실행 통과 + 실패 로그가 `시간 예산 초과` 동반** → 부하 의존 flake, 본 변경(정적 자산 + 응답 1필드)과 무관.
- **적대 리뷰(codex, [CODEX:share-join-visibility])**: P1 1건(이미 멤버 클릭이 join 을 타면 기존 windowed 멤버 가시 범위 **영구 축소**) + P2 1건(정적 검사가 극성 반전 미포착) — **둘 다 수정 후 해소**. P1 해소는 F5, P2 해소는 F1·F3 정규식 극성 고정.
- **Environment: Windows-browser (PB-0008)** — **미수행(본 Run 시점)**: 변경분이 아직 라이브 미배포(라이브 `GIT_COMMIT=03665d28`)이고, 운영 컨테이너에 임시 자산을 주입해 검증하는 것은 서비스 변조라 채택하지 않는다. **PR 머지 → 배포 후 POST-DEPLOY 절에 실측 append 예정** — ① 소유자 계정 진입 시 참여 버튼 가시 ② 클릭 시 대화 이동 + 네트워크 `/join` 요청 0건 ③ fork·링크 복사 무회귀 ④ 페이징 후 클릭 1회 = 요청 1회. 미검증을 완료로 보고하지 않는다(§16.3 정직성).

## 20260804T0620-share-join-btn-postdeploy — 공유 링크 '대화에 참여' 버튼 POST-DEPLOY 실증
- Run 기록 정본: `docs/test-runs.d/20260804T0458-share-join-btn-visibility.md` §5 (POST-DEPLOY 절).
- **Environment: Windows-browser (PB-0008)** — **POST-DEPLOY PASS** (배포 `d23f0a0d`, 실 Chrome 150 relay). 소유자 본인이 자기 joinable 공유 링크를 여는 동형 케이스에서 ① '대화에 참여' 버튼 가시 ② 배포본 `can_join=false`·`already_member=true` 인데도 노출(종전 코드면 숨김) ③ 클릭 시 **`/join` 요청 0건**(요청 캡처 직접 관측 — P1 회피 실증) ④ `?conversation=<cid>` deep-link 이동 후 목표 대화 열림 ⑤ fork·로그인 링크 무회귀 ⑥ 익명 뷰 `conversation_id=null`. 증거 `artifacts/pb0008/20260804-share-join-btn-owner.png`.
- 검증 함정: `bin/win-browser.py` 의 `ctx.pages[0]` 고정이 사용자 탭과 경합해 거짓 실패 1회 → 전용 탭(`ctx.new_page()`)으로 재검증. 상세는 fragment §5.

## Run — 20260804T0610-msg-speaker-attribution (Environment: Windows-browser) — PASS

대화내역 발화자 귀속(사용자 · assistant 제품)의 사후 변경 차단. 실 Windows Chrome 150 relay
(`bin/win-browser.py`)로 fork · 제품 전환 2 트리거와 legacy 경계 반대편까지 실측.

- **fork**: kumin 소유 대화를 bootstrap_admin 이 fork → user 행 `kumin` · assistant `건즈 글로벌 QA`
  유지(수정 전이라면 `나 (bootstrap_admin)` 로 표시됐을 화면).
- **제품 전환**: 칩을 `GZ_QA_G` → `KR_QA` 로 실제 클릭 → 과거 답변 6행 아바타 전부 불변,
  새로고침 후에도 불변(영속 각인 근거).
- **legacy(각인 전무) 경계**: 칩과 어긋난 제품으로 렌더되던 버그를 라이브 재현 후, 전환 시점의
  freeze-on-change 가 **직전 제품으로 정정**해 고정함을 확인.
- 자동 테스트: `test_msg_speaker_attribution.py`(13) + `test_msg_speaker_attribution_web.py`(16),
  전체 스위트 exit 0 · ruff clean.
- 상세·evidence·미커버 범위: `docs/test-runs.d/20260804T0610-msg-speaker-attribution.md`
  (스크린샷 `artifacts/pb0008/20260804-attrib-0*.png`).

## Run — 20260804T0650-msg-speaker-attribution-postdeploy (Environment: Windows-browser) — POST-DEPLOY PASS

배포본 `ddc1b589` 실측. `sudo -E bin/deploy-web.sh`(scope=all — 워커 포함, `agent_core.py` 변경분이
ask-worker 에 도달해야 각인이 라이브 답변에 걸린다) 후 서비스별 GIT_COMMIT 5종 전부 `ddc1b589`,
서빙 스탬프 `app.js?v=f5eca54ed047`. 라이브 `https://localhost/` 에서 제품 칩을 `GZ_QA_G` → `MV` 로
실제 전환해도 과거 말풍선 발화자 `unchanged: true`, 이후 원복해 바인딩 무변경.
상세: `docs/test-runs.d/20260804T0610-msg-speaker-attribution.md` §6.
## TASK-20260805T010301-doc-sync-rn-0805 — 릴리즈노트 신규 2026-08-04 블록 prepend (비-정책 doc-only)
- **Environment: Windows-browser (PB-0008)** — 미수행(사유): 본 변경은 사용자향 릴리즈노트 콘텐츠 데이터(`release-notes-data.js`) 신규 date 블록 prepend + `generated` 갱신만이며 렌더 로직(`release-notes.js`)·CSS·HTML 배선 델타 0 이다. 무인 cron 실행이라 인터랙티브 Windows 브라우저 브리지가 가동되지 않고, 배포는 wrapper(v3) post-merge 소관이라 이 커밋 시점에 라이브 자산이 존재하지 않는다. 대체 검증: `node --check` PASS · vm(sandbox) 구조검증 · `tests/verify_release_notes.mjs` 33 pass / 1 fail(pre-existing `styles.css` assertion, 변경 전 동일 재현).

## 20260805T1042-harness-repair — standalone mjs 하네스 red 전수 해소 (tests-only)

### Run — 20260805T1042 mjs 전수 재실행 (Environment: CLI/node) — PASS 40/40
- 기준선(수리 전): 39개 중 red 23 (rc!=0) — jsdom 재설치(`npm i jsdom@22 --prefix /tmp`) 후에도
  19 red. 수리 후: **40/40 rc=0** (신설 verify_notify_gating.mjs 포함, FAIL 라인 0).
- 대표 카운트: admin_tab_gating 49 · llm_restriction 35 · release_notes 34 · list_detail 33 ·
  metadata_bs_inline_desc 30 · picker_search 27 · notify_gating 17 · perm_self_scope 13.

### Run — 20260805T1042 settings-notif 시나리오 (Environment: Windows-browser) — PASS 20/20
- 실 Windows Chrome 150(무권한 relay @9223), `https://localhost`(Caddy) — 시나리오 파일의
  base_url(`https://localhost:18080`)은 Caddy 단일 노출 전환 후 stale 이라 scratchpad 사본으로
  실행(파일 자체의 base_url 정비는 17개 시나리오 공통 후속 후보로 REVIEW 에 기록).
- 관측(전건 기대 형상): B kebab 메뉴 `["공유","이동","설정"]`(보관/복사/공유 관리/제목 변경 부재)
  · C 공유 다이얼로그 opened+생성 섹션/joinable/expiry/목록 · D 대화 설정 opened+제목 input/mute
  토글/섹션(제목·알림·대화 관리) · E 프로필 탭 순서(릴리즈 노트 첫)+계정 병합+알림 체크박스 2종
  +usage 통합·독립 탭 부재 · 닫힘 왕복 전부 OK.
- 알림 게이팅 매트릭스(구 A 블록)는 `verify_notify_gating.mjs`(CLI) 로 이관 — default_on=1 ·
  master_off=0 · desktop_off=0 · muted=0 · unmuted=1 + prefs/muted 왕복 + 셀프 멘션 제외 +
  high-water 재알림 억제, 9/9 PASS (mentions.js 실물 파서 경유).
- 본 cycle 은 `src/static/**` 무접촉(tests-only)이라 §15.4.1 check #13 비대상이나, 시나리오
  자체를 재작성했으므로 실브라우저 완주로 시나리오의 검증 능력을 실증했다.
## TASK-20260806T010301-doc-sync-rn-0806 — 릴리즈노트 신규 2026-08-05 블록 prepend (비-정책 doc-only)
- **Environment: Windows-browser (PB-0008)** — 미수행(사유): 본 변경은 사용자향 릴리즈노트 콘텐츠 데이터(`release-notes-data.js`) 신규 date 블록 prepend + `generated` 갱신만이며 렌더 로직(`release-notes.js`)·CSS·HTML 배선 델타 0 이다. 무인 cron 실행이라 인터랙티브 Windows 브라우저 브리지가 가동되지 않고, 배포는 wrapper(v3) post-merge 소관이라 이 커밋 시점에 라이브 자산이 존재하지 않는다. 대체 검증: `node --check` PASS · 구조검증(releases 42→43·기존 블록 전량 보존·type/area enum 위반 0) · `tests/verify_release_notes.mjs` **34 pass / 0 fail**(변경 전 baseline 동일 = 회귀 0).
- `node --check static/release-notes-data.js` PASS · `node tests/verify_release_notes.mjs` **34 pass / 0 fail**(변경 전 baseline 동일 = 회귀 0). 구조: releases 42→43, 기존 블록 전량 보존, type/area enum 위반 0, 내부용어 누출 0. 렌더러·CSS 무변경이므로 PB-0008 신규 실측 불요(데이터 블록 추가는 기존 그룹 렌더 경로 재사용).
## TASK-20260806T1144-modal-backdrop-dismiss — 사이드바 항목(대화/폴더) 모달 배경 dismiss (web/UI, Minor §12.3)
- **Environment: Windows-browser (PB-0008)** — **PASS 10/10**. 실 Windows Chrome 150.0.7871.128
  via `bin/win-browser.py` relay + CDP `Input.dispatchMouseEvent`/`dispatchTouchEvent` **trusted
  입력**(합성 JS 이벤트 아님 — 원 결함의 기전인 `click` target 공통-조상 승격과 터치 implicit
  pointer capture 가 실제로 적용되어야 검증이 성립). 실행:
  `python3 tests/pb0008_modal_backdrop_dismiss.py`.
- **역검증(negative control, 같은 실 브라우저)** — `--negative`(헬퍼만 수정 전 구현으로 교체)에서
  **의도대로 FAIL 3/10**: 패널→배경 드래그, 배경→패널 드래그, 지침 textarea 드래그 선택 이탈이
  전부 모달을 닫는다 = **사용자가 보고한 현상의 실 브라우저 재현**. Run 1 의 PASS 가 vacuous 하지
  않음을 이것이 보증한다.
- `node tests/verify_modal_backdrop_dismiss.mjs` — **48 passed / 0 failed**(동작 18 + 배선 30).
  역검증 **5종** 전부 의도한 단언만 red: 옛 `click` 단독 11 · 캡처 해제 삭제 1 · `pointerup` 실행 3
  · `downOk` 미소비(장전 잔류) 1 · `isTrusted` 미검사 1 — 각 방어가 독립적으로 load-bearing.
- **§18.8 ux·design 적대 패널 2 라운드** — 지적 전건 반영 후 SHIP (상세: REVIEW
  `REV-20260806T114413-modal-backdrop-dismiss`). 하네스가 두 번 vacuous pass 를 내 교정됐다.
- `verify_*.mjs` 전수 — red 21건이 **main baseline 과 동일 집합**(본 변경 기인 신규 red 0).
- `make test` — **3782 passed · 3 skipped · 0 failed**(exit 0), ruff clean.
- 잔여: 배포 후 라이브 작업 화면에서 실제 6개 모달 재확인 → fragment Run 3 append.
- **범위 밖(미적용, REPORT §8 원장)**: 동형 오버레이 3곳 — `app/profile.js:306`(사용자향
  `mousedown` 단독) · `admin/usage.js:662` · `admin/audit.js:317`.
- Run 기록 정본: `docs/test-runs.d/20260806T1144-modal-backdrop-dismiss.md` (§5.3 fragment).
## TASK-20260806T1620-modal-dismiss-postdeploy — 배경 dismiss POST-DEPLOY 라이브 실측 (doc-only)
- **Environment: Windows-browser (PB-0008)** — **PASS 13/13**. 배포본 `44627bad` 라이브
  `https://localhost/` 에서 사이드바 `···` 메뉴 실제 클릭으로 모달 4종(대화 설정·공유·폴더로
  이동·폴더 설정)을 열고 CDP trusted 제스처 3종씩 실측. 라이브 데이터 변경 0(임시 폴더 자가
  생성·자가 삭제, 잔재 0 단언).
- 미실측 2종(공유 링크 설정·참여 허용 확인) — 진입에 실제 공유 링크 발급이 필요해 제외, 사유 명시.
- Run 기록 정본: `docs/test-runs.d/20260806T1144-modal-backdrop-dismiss.md` Run 3.
## TASK-20260806T1830-modal-dismiss-siblings — 배경 dismiss 전 표면 통일 (web/UI, Minor §12.3)
- **Environment: Windows-browser (PB-0008)** — **PASS 10/10** (실 Windows Chrome + CDP trusted 입력,
  정본 경로 `static/modal-dismiss.js`). `--negative` 에서 수정 전 구현의 사용자 보고 현상 3건 재현.
- `node tests/verify_modal_backdrop_dismiss.mjs` — **76 passed / 0 failed**(동작 18 + 배선 52 +
  **리스너 수명 실측 6**). census 는 `src/static/**/*.js` 재귀 walk + 핸들러 본문 경계 판정.
- **뮤테이션 역검증 6종** 전부 의도한 단언만 red — 그중 3종(button 가드·isPrimary 가드·census 범위
  밖 신규 파일)은 **교정 전 하네스에서 생존**했다(vacuous). §18.8 design 패널이 실증.
- `verify_*.mjs` 전수 — red 21건 = main baseline 동일 집합(신규 red 0).
- 잔여: 배포 후 신규 전환 5종 라이브 재확인 → fragment Run 4 append.
- Run 기록 정본: `docs/test-runs.d/20260806T1830-modal-dismiss-siblings.md` (§5.3 fragment).
## TASK-20260806T2010-modal-siblings-postdeploy — 신규 전환 5종 POST-DEPLOY 라이브 실측 (doc-only)
- **Environment: Windows-browser (PB-0008)** — **PASS 16/16**. 배포본 `2ab2b27e` 라이브에서 신규 전환
  5종(대화 검색 · 그래프 도움말 · 감사 purge · 사용 기록 · 프로필 사용 내역)을 사용자 UI 경로로 열어
  CDP trusted 제스처 3종씩 + 감사 purge 중복 인스턴스 가드 실측. 라이브 데이터 변경 0.
- Run 기록 정본: `docs/test-runs.d/20260806T1830-modal-dismiss-siblings.md` Run 4.
## TASK-20260807T010301-doc-sync-rn-0807 — 릴리즈노트 신규 2026-08-06 블록 prepend (비-정책 doc-only)
- **Environment: Windows-browser (PB-0008)** — 미수행(사유): 본 변경은 사용자향 릴리즈노트 콘텐츠 데이터(`release-notes-data.js`) 신규 date 블록 prepend + `generated` 갱신만이며 렌더 로직(`release-notes.js`)·CSS·HTML 배선 델타 0 이다. 무인 cron 실행이라 인터랙티브 Windows 브라우저 브리지가 가동되지 않고, 배포는 wrapper(v3) post-merge 소관이라 이 커밋 시점에 라이브 자산이 존재하지 않는다. 대체 검증: `node --check` PASS · 구조검증(releases 43→44 · head 9항목 · 기존 블록 전량 보존 · type/area enum 위반 0) · `tests/verify_release_notes.mjs` **34 pass / 0 fail**(변경 전 baseline 동일 = 회귀 0).
- `node --check static/release-notes-data.js` PASS · `node tests/verify_release_notes.mjs` **34 pass / 0 fail**(변경 전 baseline 동일 = 회귀 0). 구조: releases 43→44, `generated`==`releases[0].date`==2026-08-06, 기존 블록 전량 보존, type/area enum 위반 0, 스키마 외 키 0, 내부용어 누출 0. 렌더러·CSS 무변경이므로 PB-0008 신규 실측 불요(데이터 블록 추가는 기존 그룹 렌더 경로 재사용).
- **테스트 env 정직 표기**: 위 `verify_release_notes.mjs` **34 pass / 0 fail** 은 본 cycle 에서 편집 전(baseline)·편집 후 **두 번 실제 실행해 측정한 값**이다. 다만 cycle 후반 재확인 시점에 `/tmp/node_modules/jsdom` 이 사라져(무인 env 의 tmp 정리) 동일 명령이 `MODULE_NOT_FOUND` 로 미가동됐다 — `git stash` 로 **pristine HEAD 에서도 동일 실패가 재현**되므로 본 변경과 무관한 환경 사유다. 콘텐츠 검증은 `node --check` + vm 샌드박스 구조검증(releases 44 · head 9항목 · enum 위반 0 · 내부용어 누출 0)으로 갈음했다.

## TASK-20260806T1825-attach-suffix-toggle — 다운로드 파일명 버전 접미사(`_v2`) 토글 (Minor §12.3)
- **Environment: container** — pytest **82 passed**(신규 `test_attach_suffix_toggle.py` 37 — rebase 로 흡수한 `auto` 계약 A1~A4 포함 + 기존
  `test_attach_manage.py` 45). `make test` 전량 exit 0 · ruff clean. **뮤테이션 역검증 2종** — ZIP 이
  토글을 무시하게 만들면 B1·B2·B5 red, manifest url 하드코딩이면 B4 red(§18.8 패널이 지적한
  vacuous 상태에서는 둘 다 전건 통과했다).
- **Environment: Windows-browser (PB-0008)** — 시나리오 `src/scenario.attach-suffix-toggle.json`
  **31 step 전건 PASS**(relay @ 172.26.144.1:9223, Chrome/150). 패널 토글 279×32px 노출 · 기본 checked ·
  해제 시 `localStorage=0` · 모달 체크박스 양방향 동기화 · `모든 버전`+해제 시 충돌 고지 문구 ·
  매니페스트 12건 전량 고유 이름 · 잘못된 파라미터 400. 증거 `docs/evidence/attach-suffix-toggle/*.png`.
  **bind-mount 프리뷰 컨테이너(`:18099`)에서 수행 — 라이브 스택 무접촉, 라이브 데이터 변경 0.**
- **서버 계약 실측** — 단일 다운로드 모드별(auto/keep/strip/force/400) · ZIP 실물 엔트리명(미지정=종전 `_v1`·`_v2`,
  strip=접미 제거 + id 구분) · **이중접미 역검증**(수정 전 로직 재현 시 `..._v2_v2.sql`).
- 잔여: 브라우저 저장 대화상자의 실제 파일명은 OS 대화상자라 자동화 미도달(서버 결정 이름 →
  `link.download` 배선까지 검증). `localStorage` 는 기기·프로필 단위.
- **POST-DEPLOY PB-0008 — PASS**(2026-08-07): PR #1183 → main `abdf13bd` → `make deploy-web` exit 0
  (soak 통과·워커 롤아웃 포함) → 라이브 서빙 자산에 신규 코드·캐시 스탬프(`chat.css?v=3a7d33acaddd`)
  확인 후, 배포본 이미지 `mysql-ai-web:abdf13bd` 를 **bind-mount 없이** 띄운 컨테이너에서 31 step
  전건 PASS(라이브 트래픽 무접촉). 한계: Windows hosts 에 공개 도메인이 없어 Caddy TLS 경로는
  브라우저로 통과시키지 못했다(이번 변경의 영향면 밖).
- **Pass/Fail: PASS**. CHECK#13 충족. Run 기록 정본:
  `docs/test-runs.d/20260806T1825-attach-suffix-toggle.md` (§5.3 fragment).

## TASK-20260812T010301-doc-sync-rn-0812 — 릴리즈노트 신규 2026-08-11·2026-08-07 2블록 prepend (비-정책 doc-only)
- **Environment: Windows-browser (PB-0008)** — 미수행(사유): 본 변경은 사용자향 릴리즈노트 콘텐츠 데이터(`release-notes-data.js`) 신규 date 블록 2개 prepend + `generated` 갱신만이며 렌더 로직(`release-notes.js`)·CSS·HTML 배선 델타 0 이다. 무인 cron 실행이라 인터랙티브 Windows 브라우저 브리지가 가동되지 않고, 배포는 wrapper(v3) post-merge 소관이라 이 커밋 시점에 라이브 자산이 존재하지 않는다. 대체 검증: `node --check` PASS · 구조검증(releases 44→46 · head 5항목 · `[1]` 8항목 · 기존 44 블록 전량 보존 · type/area enum 위반 0) · `tests/verify_release_notes.mjs` **34 pass / 0 fail**(변경 전 baseline 동일 = 회귀 0).
- `node --check static/release-notes-data.js` PASS · `node tests/verify_release_notes.mjs` **34 pass / 0 fail**(변경 전 baseline 동일 = 회귀 0, 이 env 에서 편집 전·후 두 번 실측). 구조: releases 44→46, `generated`==`releases[0].date`==2026-08-11, `releases[1].date`==2026-08-07, 기존 블록 전량 보존, type/area enum 위반 0, 스키마 외 키 0, 내부용어 누출 0(19 패턴). 렌더러·CSS 무변경이므로 PB-0008 신규 실측 불요(데이터 블록 추가는 기존 그룹 렌더 경로 재사용).
- **env 후반 소실**: cycle 후반 재확인 시점에 `/tmp/node_modules/jsdom` 이 무인 env 의 `/tmp` 정리로 사라져 `verify_release_notes.mjs` 가 `MODULE_NOT_FOUND` 로 미가동됐다. 정본 HEAD 의 pristine 릴리즈노트로 교체해도 동일 실패가 재현되므로 본 변경과 무관하다(위 34/0 은 편집 전·후 두 번 실측한 실값).
- 라이브 파리티 실측(배포 게이트 확증): 델타로 바뀐 서빙 static 8종 전부 라이브가 브랜치 blob 과 byte-identical(`?v=` 정규화 후), `/healthz` 200, 컨테이너 이미지 `d56367c8` = HEAD.
## 20260811T1845-attach-diff-bubble-chip — 말풍선 수정본 첨부 칩의 diff 진입 버튼 (Minor §12.3)
- **Environment: node18 + jsdom@22** — 신규 `tests/verify_attach_bubble_diff_entry.mjs` **47 PASS / 0 FAIL**
  (어포던스·이벤트 격리·체인 해석 6경로·구조 계약) · **뮤테이션 12/12 red** · 기존 하네스 전수
  **50 suite / 1,684 체크 / 0 FAIL**(감소 0) · 실브라우저 기하 `verify_attach_diff_geometry.py`
  **55 PASS** · 행 액션 정렬 **10 조합 PASS**. 백엔드·권한·스키마 변경 0(기존 엔드포인트 재사용).
- **Environment: Windows-browser (PB-0008)** — **PASS**. 실 Windows Chrome/150, bind-mount 프리뷰
  컨테이너(`:18099`, 라이브 이미지 `8e88a60e` + worktree `src`) — **라이브 무접촉·데이터 변경 0**.
  칩 4개 전부 `⇄` 렌더(순서 `name>size>ver>cmp>dl`, 20×17px) · **실제 마우스 클릭 → `버전 비교 —
  probe_a.sql` 모달**이 `v1·사용자 ↔ v2·AI 수정` 로 열림(체인은 v1~v7 인데 **그 칩의 쌍**을 정확히
  preselect — 모달 기본값이면 `6↔7` 이 열려 이 답변과 무관한 diff 가 보인다) · 체인 옵션 7개 전량
  전달 · 페이지 이동 0 · 모달 1개 · hover 렌더(배경 `#eff6ff`·글자 `#2563eb`·inset 테두리)를 확대
  2.6× 캡처로 비-hover 형제 3칩과 대조 판독 · hover 레이아웃 이동 Δ0(옆 `↓` 좌표 불변) · pageerror 0.
- **대비 실측이 설계를 바꿨다**: `--primary-soft` 배경만으로는 흰 칩(`--surface`) 대비가 **1.09** 라
  hover 가 보이지 않는다(글자색 대비는 4.75 AA) → 형제 `.message-action-btn` 이 border-color 를
  바꾸는 것과 같은 취지로 `inset` 테두리 추가(레이아웃 이동 0).
- **한계**: trusted hover 는 `bin/win-browser.py` 에 CDP mouseMoved 서브커맨드가 없어 **같은 선언을
  주입해 렌더 결과를 판독**(선택자 발동만 우회) · 칩 본체 클릭의 다운로드 유지는 jsdom(B2) + 뮤테이션
  M2 로 잠금(실브라우저는 OS 다운로드 경로라 자동 판독 미도달) · 히트 영역 20×17 은 WCAG 24×24
  미만이나 저장소 칩·행 액션 공통의 선재 트레이드오프(원장 등재).
- **Pass/Fail: PASS**. CHECK#13 충족(웹 자산 변경에 이번 cycle Windows-browser Run 기록).
  POST-DEPLOY 라이브 재확인은 배포 후 Run append. Run 기록 정본:
  `docs/test-runs.d/20260811T1845-attach-diff-bubble-chip.md` (§5.3 fragment).

## 20260812T0030-attach-diff-bubble-chip-postdeploy — POST-DEPLOY 라이브 실측 (doc-only)
- **Environment: Windows-browser (PB-0008)** — **PASS**. PR #1215 → main `eac20796` →
  `deploy-web --web-only`(web-a/web-b 양쪽 `mysql-ai-web:eac20796` healthy). 라이브 서빙
  `static/app/messages.js` 가 main blob 과 **byte-identical**(스탬프 `73f92614ff4d`) ·
  `css/chat.css` `.attach-chip-cmp` 4 hit · `/healthz git_commit=eac20796`.
  실 Chrome/150 `https://localhost/` 에서 칩 4 · `⇄` 4(20×17px) · 클릭 → `버전 비교 —
  probe_a.sql` 모달 1개(`v1 ↔ v2`, 옵션 7, `+1 / -0`, 행 6) · 페이지 이동 0 · pageerror 0.
  **배포 전 프리뷰 결과와 차이 0**(baked 자산에서도 동일 동작).
- Run 기록 정본: `docs/test-runs.d/20260811T1845-attach-diff-bubble-chip.md` Run 2.

## 20260812T1726-dbpicker-layout-stability — '+ 데이터베이스 추가' 목록 위치 안정성
- **Environment: Windows-browser (PB-0008)** — **PASS**. 실 Chrome/150.0.7871.128 relay,
  bind-mount 격리 컨테이너(`http://localhost:18099`, 라이브 web-a/web-b·Caddy 무접촉).
  제품 `CC_QA` × `mssql-qa-idc`(후보 DB 130개) 실화면에서 **실 트러스티드 클릭**:
  체크 시 항목 이동 **0px** + 같은 화면 좌표의 `elementFromPoint` 가 동일 DB 유지(16→17행,
  `선택됨 17개`). 역검증으로 DOM 순서를 수정 전으로 되돌리면 같은 클릭이 **+38px** 이동 →
  이 화면은 수정 전이라면 반드시 달랐다. `+ 데이터소스 추가` 도 0px(역검증 +74px).
  드롭다운 가시 후보 행 3~4 → **10행**(`max-height` 420px 실측). 페이지 예외 0.
  서버 정본 무변경 확인(`webproductdatabases` 16/1 · 바인딩 2행 — pending 미적용).
- **자동 하네스** — 신규 `tests/verify_dbpicker_layout_stability.mjs` **25 PASS**(jsdom:
  DOM 순서 · 토글 시 picker 상류 마크업 불변 · 선택 카운트 임계 미만 노출 · 방향 지시어 census
  · 스크롤 보존 배선, 순서 되돌림 뮤테이션 역검증 포함) · 신규
  `tests/headless/verify_dbpicker_layout_stability.py` **13 PASS**(실 chromium 레이아웃,
  축마다 뮤테이션 역검증으로 38.3/37.4/114.3/114.3/42.0px 재현).
- **회귀** — feature-0003 프론트 mjs **53 suite 전건 PASS**(0 fail) · pytest 4,287 수집
  EXIT=0(사전 실패 `test_oauth_exhaustion_gate` = `chattr` 부재, main baseline 동일분 제외).
- **Pass/Fail: PASS**. CHECK#13 충족(웹 자산 변경에 이번 cycle Windows-browser Run 기록).
  Run 기록 정본: `docs/test-runs.d/20260812T172625-dbpicker-layout-stability.md` (§5.3 fragment).
  **POST-DEPLOY 이월**: 드롭다운 가시 행 수를 배포본에서 캐시 무효화 없이 재확인.

## 20260812T1810-dbpicker-layout-stability-postdeploy — POST-DEPLOY 라이브 실측 (doc-only)
- **Environment: Windows-browser (PB-0008)** — **PASS**. PR #1221 → main `d619259d` →
  `make deploy-web-only`(web-a/web-b 양쪽 `mysql-ai-web:d619259d` healthy · 엣지
  `no upstreams available` **0건** = 무중단 실측 · 스탬프 `c1426a14086f`).
  실 Chrome/150 `https://localhost/admin` 에서 편집기 순서 `[picker, 목록, 규칙]` ·
  드롭다운 **420px / 가시 10행**(Run 1 의 프리뷰 캐시 이월 축을 **캐시 우회 없이** 종결) ·
  실 클릭 시 이동 **0px** + 같은 좌표 동일 DB 유지(16→17행) · 역검증 **+38px** 재현 ·
  새로고침 후 pending 0 + 서버 정본 16/1 로 **라이브 데이터 변경 0**.
- Run 기록 정본: `docs/test-runs.d/20260812T172625-dbpicker-layout-stability.md` Run 2.

### Run 2026-08-12 — feature-0041 발견 자료 (Environment: Windows-browser — **미수행**, 사유 명시)

**미수행 사유**: 이번 cycle 의 `static/` 변경은 `ai-api-guide.md` **한 파일**이고, 이 자산은
`GET /api/ai/guide` 에서 `text/markdown; charset=utf-8` 로 **원문 서빙**된다 — 브라우저가 렌더하는
화면 요소가 아니라 외부 AI 가 읽는 텍스트 문서다. HTML/CSS/JS 변경이 0 이라 PB-0008 이 검증할
시각 표면 자체가 존재하지 않는다(관리 콘솔·작업 화면 DOM 무변경).

**대체 검증(POST-DEPLOY 에서 수행)**: 라이브에서 `GET /api/ai/guide` 가 200 + 부록 B 내용을
포함해 서빙되는지 확인한다 — 이 자산에 대해 의미 있는 실패 모드는 "렌더가 깨진다" 가 아니라
"배포본에 갱신이 반영되지 않는다" 이므로, 내용 포함 확인이 정확한 게이트다.

> UI 변경을 포함하는 후속 작업(콘솔 '외부 도구 한도' 탭)은 **PB-0008 실 브라우저 검증 대상**이며,
> 그래서 이번 출하에서 의도적으로 분리했다(사용자 결정 2026-08-12).

## 20260812T1739-metadata-pane-refresh — 메타데이터 pane 입력 UI 통합 표 재구성 (web/UI, Major §12.3)

### 1. 케이스 정의

| ID | 케이스 | 기법 | 정본 |
|---|---|---|---|
| `TEST-20260812T1739-metadata-pane-refresh-1` | 공용 입력 프리미티브가 `base.css .field input:focus` 와 **동일 halo 값**을 쓴다 (D1) | 정적 CSS 대조(토큰 값 동치) + 실브라우저 computed | mjs `[A1-D1]` · PB-0008 §3 |
| `-2` | 골격 결과가 단일 표 surface + hairline row 이고 **행별 카드 테두리가 0** 이다 (D2) | 정적 CSS + 실브라우저 30행 전수 computed border | mjs `[B1/B2-D2]` · headless `[1]` · PB-0008 §1 |
| `-3` | 설명 입력란이 기본 ghost 이고 hover/focus 에서만 드러나며 **레이아웃 이동 0** 이다 | 실브라우저 트러스티드 클릭 전/후 computed | headless `[2]` · PB-0008 §3 |
| `-4` | 상태가 raw `●`/`○` 없이 CSS dot + `--tag-*` 시맨틱 색 **3단**(미입력/진행/완료)으로 렌더된다 (D3) | jsdom 행위 + 실브라우저 `::before` computed + 실입력 전이 | mjs `[C3/D1~D5]` · headless `[4]` · PB-0008 §4 |
| `-5` | 저장·AI일괄·힌트·필터·페이징의 **DOM 셀렉터 계약이 변경 전과 동일**하다 (입력값 유실 0) | 정적 계약 12항 + jsdom 수집 셀렉터 | mjs `[C1-계약]` · `[D6]` |
| `-6` | 등폭 식별자가 `var(--mono)` 를 쓰고 전각 `＋` 가 pane 에서 사라진다 (D4·D5) | 정적 + 실브라우저 computed font-family / 페이지 텍스트 스캔 | mjs `[A2/B6]` · PB-0008 §5 |
| `-7` | 저장 액션 버튼 라벨이 줄바꿈·잘림 없이 단일 행이다 (D6) | 실브라우저 높이·`white-space`·`scrollWidth` | headless `[6]` · PB-0008 §6 |
| `-8` | sticky 열 헤더가 **카드 border edge 에 도킹**해 직전 행이 위로 비치지 않고, 추가 스크롤에도 불변이다 | 실브라우저 scrollTop 다지점 + `elementFromPoint` | headless `[7]` · PB-0008 §7 |
| `-9` | 상태 라벨·열 헤더가 실 배경에서 **WCAG AA 4.5:1** 이상이다 | headless 실렌더 대비 계산 | headless `[5]` |
| `-10` | columns 서브뷰에서 열 헤더가 숨고 결과 컨테이너가 상단 변을 되찾는다 | 실브라우저 서브탭 전환 후 computed | PB-0008 §8 |

### 2. 회귀 잠금 (신규 하네스)

- `tests/verify_metadata_pane_refresh.mjs` — **90 checks**. D1~D8 각 축을 CSS/JS/HTML 정적 단언 +
  jsdom 상태 전이로 잠근다. **뮤테이션 10종 전건 KILLED**(halo 제거 · 행 카드 테두리 복원 ·
  ghost 해제 · 열 폭 토큰→리터럴 · `overflow:clip`→`hidden` · raw 글리프 복원 · `is-complete`
  제거 · 전각 플러스 복귀 · `hidden`→`style.display` 채널 전환 · mono 토큰→하드코딩).
  `--meta-grid-head-inset` == `.admin-detail-col` padding-top **결합 검사** + data-URI SVG stroke 색 ==
  `--text-muted` **결합 검사** 포함(파생 불가 지점의 무언의 drift 를 검증 대상으로 전환).
  codex 적대 리뷰 반영으로 추가된 축: 잘린 식별자의 `title` 회수 경로(`[C4-D8]`) · **JS 동적 라벨**의
  전각 플러스 스캔(`[B6-D5]`) · pane 토큰의 리터럴 색 0(`[A1-token]`). 2라운드 누적 **뮤테이션 15/15 KILLED**.
- `tests/headless/verify_metadata_pane_refresh_render.py` — **32 checks**(headless Chromium 실렌더).
  정적 단언이 원리적으로 못 보는 축 — cascade 승부 · **픽셀 열 정렬** · 대비 계산 · 줄바꿈 발생 ·
  sticky 실동작 · **halo 합성 픽셀 등가**(토큰 파생 후 값 불변 검증 — Chrome 이 `color-mix()` 를
  `oklab()`/`color(srgb …)` 로 직렬화하므로 문자열 비교로는 원리적으로 불가). PB-0008 을 대체하지
  않는 PRE-DEPLOY 보조 게이트다.

### 3. Run 기록

- **Environment: Windows-browser (PB-0008)** — **PASS** (실 Chrome 150.0.7871.128, §13.2.9 격리
  컨테이너 `web-metaui-verify`, 라이브 web replica 무접촉). 제품 `건즈 글로벌 QA` × `gunzgame`
  골격 **125테이블/846컬럼** 실데이터. 열 정렬 편차 **0.00px**(30행) · 행 카드 테두리 0 ·
  트러스티드 클릭 halo = base.css 동일 값 · 상태 전이 `비어있음`→`설명 입력됨`(dot 회색→녹색) ·
  버튼 단일 행 · sticky 도킹 `272 == border edge` 불변. **라이브 데이터 변경 0**(저장 미클릭,
  목록 `1건` 불변). **사전 검증이 결함 1건 적발**(sticky `top:0` → 스크롤러 padding 18px 띠로
  직전 행 비침) → `top: calc(-1 * var(--meta-grid-head-inset))` 수정 후 재실측 PASS.
- Run 기록 정본: `docs/test-runs.d/20260812T183000-metadata-pane-refresh.md` (§5.3 fragment).
- **POST-DEPLOY 이월**: 머지·배포 후 라이브 baked 자산에서 위 축을 재실측해 Run 2 append
  (JS/HTML 변경 포함 cycle 이라 `docker cp` 프리뷰가 원리적으로 불충분).
- **전수 회귀**: mjs 하네스 **53 파일 전건 green**(종료코드) · pytest **4312 passed / 1 failed**
  — 그 1건(`test_oauth_exhaustion_gate.py::test_write_failure_after_successful_post_cannot_kill_slot_selection`)은
  **pristine main 에서 동일 재현**되는 선재 red 로, 본 변경(프론트 표시 계층 3파일) 귀책 아님.

## 20260812T2005-metadata-pane-refresh-postdeploy — POST-DEPLOY 라이브 실측 (doc-only)

- **Environment: Windows-browser (PB-0008)** — **PASS**. PR #1231 → main `e250dad7` →
  `make deploy-web-only`(web-a/web-b 양쪽 `mysql-ai-web:e250dad7` · 스탬프 `06bd063c9b98` ·
  엣지 `no upstreams available` **0건** = 무중단 실측 · soak 통과).
  실 Chrome/150 `https://localhost/admin` 에서 `건즈 글로벌 QA` × `gunzgame` 125테이블 실데이터로
  **전 축 재실측 — 프리뷰(Run 1·2)와 차이 0**: 행 카드 테두리 좌·우·하 0(30행 전수) · 입력란
  시작/끝 x 편차 **0.00px** · 헤더 열 정합 0.00px · ghost cell 기본 투명 + 실 클릭 시 3px halo ·
  상태 전이 `비어있음`→`설명 입력됨`(dot 회색→녹색, raw 글리프 0) · `D2Coding` · 버튼 nowrap ·
  sticky 도킹 `272 == border edge` · 전각 `＋` 0건. **라이브 데이터 변경 0**(저장 미클릭, 목록 `1건` 불변).
  → Run 1·2 가 이월했던 "라이브 baked 자산" 축을 **종결**.
- Run 기록 정본: `docs/test-runs.d/20260812T183000-metadata-pane-refresh.md` Run 3.
## TASK-20260813T010301-doc-sync-rn-0813 — 릴리즈노트 신규 2026-08-12 블록 prepend (비-정책 doc-only)
- **Environment: Windows-browser (PB-0008)** — 미수행(사유): 본 변경은 사용자향 릴리즈노트 콘텐츠 데이터(`release-notes-data.js`) 신규 date 블록 1개 prepend + `generated` 갱신만이며 렌더 로직(`release-notes.js`)·CSS·HTML 배선 델타 0 이다. 무인 cron 실행이라 인터랙티브 Windows 브라우저 브리지가 가동되지 않고, 배포는 wrapper(v3) post-merge 소관이라 이 커밋 시점에 라이브 자산이 존재하지 않는다. 대체 검증: `node --check` PASS · 구조검증(releases 46→47 · head 9항목 · 기존 46 블록 전량 보존 · type/area enum 위반 0) · `tests/verify_release_notes.mjs` **34 pass / 0 fail**(편집 전 baseline 동일 = 회귀 0).
- `node --check static/release-notes-data.js` PASS · `node tests/verify_release_notes.mjs` **34 pass / 0 fail**(이 env 에서 편집 전·후 두 번 실측). 구조: releases 46→47, `generated`==`releases[0].date`==2026-08-12, 기존 블록 전량 보존, type/area enum 위반 0, 스키마 외 키 0, 내부용어 누출 0(22 패턴). 렌더러·CSS 무변경이므로 PB-0008 신규 실측 불요(데이터 블록 추가는 기존 그룹 렌더 경로 재사용).
- 라이브 파리티 실측(배포 게이트 확증): 서빙 static 6종(`hangul-qwerty.js`·`admin/products.js`·`graph/graph-roleviz.js`·`graph/graph-core.js`·`app/attach-diff.js`·`admin/metadata.js`)이 라이브(`https://localhost:443/static/...`)에서 브랜치 blob 과 byte-identical(`?v=` 정규화 후), `/healthz` 200, 이미지 web `105fa2b7` · agent `e1372f32`, alembic 라이브 head `0055`(= `MAX_MIGRATION.txt`), `db_objects` 339행.
- **Pass/Fail: PASS**. CHECK#13 충족(Environment 표기 + 미수행 사유 + 대체 검증 명시).

## 20260813T1135-usage-metric-charts — 요약 카드 클릭 → 차트 지표 전환 + 캐시 계측 (web/UI + 집계 + LLM 기록, Major §12.3)

### 1. 케이스 정의

| # | 케이스 | 기대 |
|---|---|---|
| 1 | 요약 카드 8종 렌더 | 요청·호출·총 토큰·입력·출력·캐시 읽기·캐시 쓰기·추정 비용 (기본 선택 = 총 토큰) |
| 2 | 카드 클릭 → 일별 차트 | 막대 높이가 **그 지표의 값 비율**과 일치 |
| 3 | 카드 클릭 → 전환 방식 | 노드 재사용 + CSS transition (값 점프 금지) |
| 4 | 요청(비-가산) 지표 | 모델 분해 없이 버킷 총계 단일 막대 + 사유 1줄 |
| 5 | 캐시 지표 | 값 반영 + "입력에 포함된 내역" 1줄 (60자 예산) |
| 6 | 도넛·역할·계정 차트 | 같은 지표를 따르고, 오른쪽 카드는 비용(선택이 비용이면 총 토큰) |
| 7 | 캐시 인지 비용식 | 캐시 0 인 레거시 행은 **종전 값과 동일**(무회귀), 캐시분은 read 0.1x / write 1.25x |
| 8 | 캐시 계측 캡처 | 최상위 필드 · `prompt_tokens_details` 폴백 · 부재 시 0 |
| 9 | `_apply_prompt_cache` | 마지막 system 블록에만 부착 · 짧은 system/로컬 LLM/기존 지시 시 원본 그대로 |
| 10 | 컬럼 사다리 | 0056 미적용 DB 에서 리터럴 0 재실행으로 화면 유지 |

### 2. 회귀 잠금 (신규 하네스)

- `feature-0003/tests/test_usage_metric_axes.py` (6건) — 캐시 인지 비용식 + 역할 폴딩 8축 보존
- `feature-0002/tests/test_llm_usage_record.py` (+8건) — 캐시 캡처 3 · `_apply_prompt_cache` 5
- `feature-0003/tests/headless/test_usage_metric_switch.js` (21건) — 실 Chromium 렌더·전환 실측

### 3. Run 기록

- **Environment: Windows-browser (PB-0008)** — **미수행(POST-DEPLOY 이월)**, 사유 명시: 본 변경의
  본체가 ES module JS 라 미머지 `docker cp` 프리뷰가 원리적으로 불충분(asset stamp 미주입 →
  모듈 이중 인스턴스 + Chrome 모듈 캐시가 구버전 실행). 대신 **같은 렌더 엔진(Chromium)** 으로
  실 자산을 로드해 21축 실측 PASS. 머지·배포 후 라이브 baked 자산에서 재실측해 Run 2 append.
- Run 기록 정본: `docs/test-runs.d/20260813T1135-usage-metric-charts.md` (§5.3 fragment).
- **전수 회귀**: pytest **4364 passed / 4 skipped**. 환경 제약 1건
  (`test_oauth_exhaustion_gate::test_write_failure_after_successful_post_cannot_kill_slot_selection`,
  `chattr` 부재)은 `repo/`(main) 동일 이미지 실행에서 **동일 재현** — 본 변경 귀책 아님.

## 20260813T1224-attach-source-compare — 문서 원문 화면의 버전 비교 (REQ-20260813-attach-source-compare)

### 케이스

| ID | 케이스 | 기대 |
|---|---|---|
| TEST-20260813T122457-attach-source-compare-1 | 원문 모달의 비교 기준 선택기 | 체인 2개↑ 노출 · 옵션=체인 전체 · 기본=이 버전(`· 이 버전` 표기) · 체인 1개/`versions` 부재면 숨김 |
| TEST-…-2 | 다른 버전 선택 | 같은 모달에서 `/diff` 렌더 · 제목 `버전 비교 (vA → vB)` · 통계 `+N / -M` · 방향은 오래된→새로운 정규화 |
| TEST-…-3 | 같은 버전 선택 | **재요청 0** 으로 원문 복귀 · 제목·통계도 원문 기준 |
| TEST-…-4 | 변경사항 없음(identical) | 원문 표 + 사유 배너(해시 동일이면 "내용이 동일합니다", 다르면 "줄 내용은 같지만…") |
| TEST-…-5 | diff 전용 컨트롤 | 원문 상태 숨김 · 비교 상태 노출 · 그릴 표 없으면 비활성 + 사유 title |
| TEST-…-6 | 비교 모달 `from==to` | 그 버전 id 의 `/source` 원문 + `같은 버전을 선택했습니다 — vN 원문입니다.` · 종전 안내문 소멸 · 재렌더에도 배너 유지 |
| TEST-…-7 | 목록 `⇄ 버전 비교` | 최초→최신 사전선택(번호는 값의 min/max) · title 이 그 사실을 밝힘 |
| TEST-…-8 | 서버 payload | `/source` 에 `versions` 체인 요약(서명 URL·ObjectKey 없음) · 조회 실패 fail-soft · `_version_side` 단일 정본 |
| TEST-…-9 | 계약 유지 | 왕복 1회(`/source` 만) · `?version=` 부재 · `/diff` from==to 400 불변 · 렌더러·판정면 복제 0 |
| TEST-…-10 | CSS `[hidden]` | `.attach-source-cmpctl[hidden]{display:none}` — author `inline-flex` 가 UA 규칙을 이기는 트랩 봉인 |

### Run

- **자동(jsdom·정적)** — 신규 `tests/verify_attach_source_compare.mjs` **72 pass / 0 fail**.
  기존 첨부 하네스 회귀: `verify_attach_source_view.mjs` 77 · `verify_attach_diff_identical_source.mjs`
  61 · `verify_attach_version_diff.mjs` 126 · `verify_attach_diff_syntax_highlight.mjs` 146 ·
  `verify_attach_source_markdown.mjs` 102 · `verify_attach_bubble_diff_entry.mjs` 47 — **전건 green**.
- **pytest** — `test_attachment_source_view.py`(신규 C1~C5 포함) + `test_attachment_version_diff.py`
  **71 passed / 0 failed**. 전체 스위트에서 실패 1건(`test_oauth_exhaustion_gate` — 컨테이너에
  `chattr` 바이너리 부재)은 **pristine main 에서 동일 재현**(같은 이미지·명령으로 실측) → 환경 의존
  선재 red, 본 cycle 귀책 아님.
- **Environment: Windows-browser (PB-0008)** — **PASS**. 실 Chrome/150 + §13.2.9 격리 프리뷰 컨테이너
  (`web-attach-src-cmp-preview`, worktree `src` 마운트, `http://localhost:18099`), 라이브 데이터
  (대화 `20260807035225-9cb592cb` · `probe_a.sql` **7버전 체인**)로 5단계 실측:
  ① 원문 화면 — 제목 `문서 원문 — probe_a.sql (v7 · 최신)` · 통계 `126줄 · 7KB` · 비교 기준 select
     실렌더(`display:flex`, 215×26px @x=33) · 옵션 7개 · 기본 `v7 … · 이 버전` · 원문 126행 ·
     diff 전용 컨트롤 rect 0×0(숨김) · 구문 색 토글 노출.
  ② v1 선택 → `버전 비교 — probe_a.sql (v1 → v7)` · `+5 / -0` · 2열 diff · 추가행 5 ·
     gap `동일한 114줄 생략` · diff 컨트롤 노출·활성.
  ③ v7 재선택 → 원문 복귀 · **fetch 호출 0회**(재요청 없음을 계측으로 실증) · 126행 복원.
  ④ 목록 `⇄ 버전 비교` — title `v1(최초) ↔ v7(최신) 비교 — 다른 쌍은 모달에서 고릅니다` ·
     클릭 시 기준=v1 / 비교=v7.
  ⑤ 비교 모달에서 같은 버전(v1/v1) → 원문 121행 + 배너 `같은 버전을 선택했습니다 — v1 원문입니다.` ·
     종전 `서로 다른 두 버전을 선택하세요` **소멸** · diff 컨트롤 비활성.
  **신원 대조**(§16.6 c): 서빙 중인 `attach-diff.js`(88,874B)에 `_bodyState`·`_renderSourceBody`·
  `attach-source-cmp` 존재 = 자기 빌드 산출물.
  **세션 격리**(§16.6 MUST): 공유 CDP 포트에 병렬 세션이 붙어 `pages[0]` 이 남의 탭(`/admin`)으로
  바뀐 것을 검증 도중 관측 → `context.new_page()` 로 **자기 생성 탭**을 만들어 그 탭에서만 조작·캡처하고
  종료 시 그 탭만 닫았다. 남의 탭은 조작하지 않았다.
  증거: `docs/evidence/pb0008-attach-source-compare-{1-source,2-diff,3-back,4-oldest-latest,5-same-version}.png`.
- Run 기록 정본: `docs/test-runs.d/20260813T122457-attach-source-compare.md`.
- **Pass/Fail: PASS** (배포 후 POST-DEPLOY 재실측은 이월).

## 20260813T1520-usage-metric-charts-postdeploy — POST-DEPLOY 라이브 실측 (doc-only)

선행 cycle(`20260813T1135-usage-metric-charts`)이 이월한 **라이브 baked 자산 검증**을 종결한다.

- [x] PR #1241 머지 → main `d2730350` → `make migrate`(0056 적용, live current 확인) →
      `sudo make deploy-web`(web 롤링 + 워커 + gateway reconcile). 무중단 실측
      `no upstreams available` **0건** · 파리티 web-a/web-b/insight/ask 전부 `d2730350` · `/healthz` 200.

### Run 2026-08-13 — Environment: Windows-browser (PB-0008) · 실 Chrome/150.0.7871.128 · `https://localhost/admin`

| 축 | 실측 | 결과 |
|---|---|---|
| 카드 8종 렌더 | 요청 360 · 호출 24,917 · 총 토큰 163,261,652 · 입력 121,621,690 · 출력 41,639,962 · **캐시 읽기 72,865 · 캐시 쓰기 72,865** · 추정 비용 $430.91 | PASS |
| 지표 전환(총 토큰→비용) | 일별 라벨 `12,286,912`→`$29.18` · 도넛 84.2/10.6/5.1% → **67.0/20.9/12.0%**(모델 단가차 반영) · 역할 카드 좌우 스왑(추정 비용 \| 총 토큰) | PASS |
| **전환이 애니메이션인가** | 같은 rect 노드 유지(`sameRectNode=true`) + `getAnimations()` 가 **CSSTransition `height`/`y` running** 반환 + computed height rAF 샘플 34프레임 중 **17프레임이 시작·끝 사이**(24.8→24.76→24.63→23.99→22.56→…→14.1) | PASS |
| 비-가산 지표(요청) | 기간 차트 20막대 전부 단일 세그먼트 · 역할 막대 세그먼트 `[1,1,1]`(0폭 소멸 없음) · 안내 "요청은 모델을 넘나들어 모델별로 나누지 않습니다." | PASS |
| 캐시 지표 | 안내 "캐시 읽기·쓰기는 입력에 포함된 내역입니다." · 역할 카드 제목 "캐시 읽기" 연동 | PASS |
| **캐시 계측 end-to-end** | 배포 후 실제 대화 2라운드 — `id 84869` 15:14:34 `cache_write=72,865` (캐시 생성) → `id 84870` 15:15:29 `cache_read=72,865` (**적중**). DB 실조회로 확인 | PASS |

### 측정 방법에서 배운 것 (재현 시 주의)

첫 시도에서 `getBoundingClientRect().height` 로 샘플링해 **전환이 안 걸린 것처럼 보였다**(첫 프레임에
이미 최종값). SVG geometry property 는 layout box 가 **최종 style 값** 기준으로 계산돼, 진행 중인
transition 이 이 API 에 반영되지 않는다. `getComputedStyle().height` 로 재측정하니 정상 곡선이
나왔고 `getAnimations()` 가 CSSTransition running 을 반환해 교차 확인됐다. **측정 도구를 먼저
의심해야 하는 부류** — 코드 결함으로 오보고할 뻔한 지점이다.

### 정직 표기

- 캐시 지표는 **소급되지 않는다**. 현재 값(72,865)은 전부 배포 이후 2라운드분이며, 30일 창의 누적
  토큰(1.6억) 대비 미미한 것은 정상이다 — 시간이 지나며 채워진다.
- 캐시 읽기와 쓰기가 같은 값인 것은 **우연이 아니라 기대 동작**이다(같은 접두를 한 번 쓰고 한 번 읽음).
  DB 행 단위로 갈라져 있음을 확인했다(쓰기 행과 읽기 행이 별개).

## 20260813T1310-attach-source-compare-postdeploy — POST-DEPLOY 라이브 실측 (doc-only)

- **Environment: Windows-browser (PB-0008)** — **PASS**. PR #1243 → main `c5a27e0d` →
  `sudo make deploy-web-only`(web-a·web-b 양쪽 `mysql-ai-web:c5a27e0d` · soak 통과 · 엣지
  `no upstreams available` **0건** = 무중단 실측 · `/healthz` 200).
  실 Chrome/150 `https://localhost/` 에서 라이브 7버전 체인(`probe_a.sql`)으로 **전 축 재실측 —
  프리뷰(Run 1)와 차이 0**: 원문 화면 126행 · 비교 기준 선택기 215×26px @x=33 · diff 전용 컨트롤
  rect 0×0(숨김) → v1 기준 비교 `v1 → v7` · `+5 / -0` · 추가 5행 → 같은 버전 복귀 **fetch 0회
  계측** → 목록 버튼 title `v1(최초) ↔ v7(최신) 비교 …` + 기준 v1/비교 v7 → 비교 모달 같은 버전
  → 원문 121행 + `같은 버전을 선택했습니다 — v1 원문입니다.`(종전 안내문 소멸).
  **캡처 byte-identical**: POST-DEPLOY 캡처 5매가 커밋된 Run 1 캡처와 바이트 동일(`git status`
  dirty 0) — 프리뷰↔라이브 렌더가 픽셀 단위로 같다는 직접 증거이자 main mutation 0(§13.2.7 F0).
  **라이브 데이터 변경 0**(열람 경로만).
  → Run 1 이 이월했던 "라이브 baked 자산" 축을 **종결**.
- Run 기록 정본: `docs/test-runs.d/20260813T122457-attach-source-compare.md` Run 2.
- **Pass/Fail: PASS**

## 20260813T1543-attach-list-name-sort — 첨부 목록 이름순 정렬

- **자동(pytest)** — 신규 `tests/test_attach_list_name_sort.py` **12 passed**: 자연 정렬(숫자 수치비교
  + 사전순 역단언) · casefold · 한글 가나다 · None/빈 이름 · tie-break(version→id) · PG 형상 행 ·
  bulk 체인 인접 · 체인 대표=최신 이름 · 목록 API 응답 순서 · 휴지통 이름순 + **절단 SQL 불변**
  (`DeletedAt DESC` + `LIMIT 200`) · bulk 경로의 헬퍼 경유 · PG alias 계약.
  회귀 `-k "attach or conv"` **391 passed** · `ruff` clean. 전체 스위트의 유일 실패
  `test_oauth_exhaustion_gate` 는 컨테이너 `chattr` 부재로 **pristine main 동일 재현** → 귀책 아님.
- **Environment: Windows-browser (PB-0008)** — **PASS**. 실 Chrome/150 + 격리 프리뷰 **2대 A/B**
  (`:18099` worktree src = 수정 후 / `:18098` main src = 수정 전), 같은 라이브 대화(첨부 39건,
  `08051122_`·`v2_`·`v2_1_`·`v3_` 접두 혼재)를 같은 브라우저로 대조:
  수정 전 = 업로드 순(DB `Id ASC` 일치), 수정 후 = **39건 완전 이름순**.
  `v2_1_…` 이 `v2_D_…` 앞에 서서 자연 정렬(숫자 조각 우선)이 실측됐다. 화면 순서와 같은 세션의
  `GET /api/conversations/{cid}/attachments` 응답 순서가 **전건 일치**(프론트 재배열 없음).
  세션 격리: 자기 생성 탭에서만 조작, 병렬 세션 탭 2개 무접촉, 종료 시 자기 탭만 닫음.
  라이브 데이터 변경 0(열람 경로만). 증거:
  `docs/evidence/pb0008-attach-name-sort-{1-sorted,2-baseline}.png`.
- Run 기록 정본: `docs/test-runs.d/20260813T154300-attach-list-name-sort.md`.
- **Pass/Fail: PASS** (배포 후 POST-DEPLOY 재실측은 이월).

### 후속 — codex 리뷰 반영분 재검증 (2026-08-13 16:20)

- pytest `test_attach_list_name_sort.py` **14 passed**(N5 초장문 숫자열 `ValueError` 방어 ·
  S3 snake_case 키 fallback 추가) · 첨부·대화 회귀 **393 passed** · ruff clean.
- 신규 프론트 하네스 `tests/verify_attach_pill_name_sort.mjs` **13 PASS** — 정본 비교자(`byName`)를
  소스에서 추출해 실행(로직 재구현 0): 숫자 수치 비교 + **사전순 역단언**(vacuous 아님) · 대소문자 ·
  한글 · id tie-break · 이름 없는 항목, 배선은 **정렬 호출 개수 2**(두 목록 모두)로 잠금,
  뮤테이션 역검증 2축.
- composer 계열 기존 하네스 회귀 0 — `verify_attach_multi_upload`(28) ·
  `verify_attach_date_compact`(18) · `verify_attach_source_compare`(72) ·
  `verify_attach_bubble_diff_entry`(47).
- **미실측(정직 표기)**: 업로드 **직후** pill 목록의 실브라우저 순서는 재지 않았다 — 프리뷰 컨테이너가
  라이브 DB 를 보므로 업로드 실측은 라이브 데이터 변경을 낳는다(본 cycle 의 '데이터 변경 0' 원칙과 충돌).
  그 경로는 하네스(정본 비교자 실행 + 배선 개수)로 덮었고, 서버 목록 경로는 PB-0008 A/B 로 실측했다.

## Run — 20260813T1550-rail-async-relayout (우측 스크롤 ↔ 대화 뱃지 정합, mermaid 지연 렌더)

- **Environment: CLI(headless chromium)** — 신규 `tests/headless/verify_point_rail_async_relayout.py`.
  실 `app.js` 유닛 정규식 추출(사본 아님) + 실 `css/{base,chat,profile}.css` 를 chromium 에 올려
  뱃지 막대 좌표를 px 로 실측. **현행 26/26 PASS**(codex 지적 4건 + 라이브 회귀 1건을 잠근
  T9~T11·W4~W8 포함).
  `--baseline`(신설 배선 미주입 = 수정 전)에서 **T2 178.2px · T4 맨아래 507px 밀림 · T7 이미지
  97.96px** FAIL 로 결함이 재현되고 T8 재현 판정 OK — 이 변경이 load-bearing 임의 증거(§16.7 G4).
  하네스 자기 검증: 초판이 row 높이를 `min-height` 로 만들어 flex-shrink 가 아이템을 눌러
  라이브와 거동이 갈렸다(이미지 성장 12px 로만 관측) → 실 콘텐츠(spacer) 기반으로 교체.
- **회귀** — 기존 프론트 검증 `tests/verify_*.mjs` **57/57 PASS** · feature-0003 pytest 전건 PASS
  (격리 env `DB_PORT=1`·`AGENT_KB_PG_PORT=1` 등, rc=0).
- **Environment: Windows-browser (PB-0008)** — **PASS**. 실 Chrome/150.0.7871.128 + §13.2.9 격리
  프리뷰 **2개**(`web-rail-relayout-preview` :18097 = worktree 자산 / `web-rail-baseline-preview`
  :18096 = main 자산 대조군, 라이브 이미지·env 공유 → **자산만 다른 대조**).
  데이터는 **사용자가 이슈를 보고한 그 대화**(`20260812082809-e4263afd` "스키마 개선 BEFORE/AFTER
  다이어그램" · mermaid SVG 3개 실렌더 · 문서 4,967~5,134px).
  **수정 전 → 수정 후**: 뱃지↔메시지 구간 최대 오차 **86.58px → 0.11px**(자기 탭 재측정 0.20px) ·
  진입 시 맨-아래 gap **1,631px → 0px**. thumb 정합 불일치 0(보이는 2건만 겹침).
  상호작용(자기 탭, 확정 코드): 막대 60% 클릭 정밀 점프(4206→2629) · **실 휠 입력** 후 위치 유지
  (2629→1729, pin 개입 0) · 두 경우 모두 정합 유지 · JS 오류 0.
  **라이브가 자기 회귀를 적발**: codex [P2] 반영 초판(scroll 값 비교로 스크롤바 조작 판별)이
  **뷰포트 위쪽 성장** 시 브라우저 스크롤 앵커링의 자동 조정을 사용자 조작으로 오판해
  `A_entry gap=1,611px`(수정 전과 같은 증상)을 냈고, 헤드리스 26축은 성장이 아래쪽에서만
  일어나 전건 통과 상태였다 → 판별을 컨테이너 `pointerdown` 으로 교체 + 하네스 T11/W5b 추가로
  클래스 잠금 → 재측정 `gap=0` 복귀(§16.7 G4·G10).
  **신원 대조**(§16.6 c): :18097 서빙 `app.js` 에 `_observeRailContentResize` 2건 / :18096 은 0건.
  **세션 격리**(§16.6 MUST): 검증 도중 공유 CDP `pages[0]` 이 병렬 세션의 `/admin` 탭으로 바뀐 것을
  관측(read-only eval 1회 + 실패한 scrollTop 대입 1회 도달, 남의 화면 미변경) → `context.new_page()`
  자기 전용 탭으로 전환해 이후 전부 그 탭에서 수행하고 종료 시 그 탭만 닫았다.
  증거: `docs/evidence/pb0008-rail-async-relayout-{1-entry,2-before-after,3-midjump,4-wheel,5-baseline-full}.png`
  (2번 = 수정 전/후 rail+스크롤바 가로 6배 확대 나란히 대조).
- **Environment: Windows-browser (POST-DEPLOY)** — **PASS**. PR #1252 → main `c6c43463` →
  `make deploy-web-only`(파리티 `mysql-ai-web:c6c43463` 양 replica · soak 통과 · `/healthz` 200 ·
  **배포 창 `no upstreams available` 0건** = 무중단 실측). 서빙 `app.js` 신설 심볼 10건(신원 대조).
  라이브 baked 자산에서 **프리뷰와 차이 0**: 진입 gap **0** · 뱃지 오차 **0.20px** · 막대 60% 클릭
  정밀 점프(4206→2629) · 실 휠 입력 후 위치 유지(2629→1729) · JS 오류 0. 라이브 데이터 변경 0.
  증거: `docs/evidence/pb0008-rail-async-relayout-{6-postdeploy-entry,7-postdeploy-midjump}.png`.
- Run 기록 정본: `docs/test-runs.d/20260813T155000-rail-async-relayout.md` (Run 1~3).
- **Pass/Fail: PASS**

## 20260813T1700-attach-name-sort-postdeploy — POST-DEPLOY 라이브 실측 (doc-only)

- **Environment: Windows-browser (PB-0008)** — **PASS**. 배포 PR #1251 → main `7afed974` →
  `deploy-web.sh --web-only`(web-a·web-b 양쪽 `mysql-ai-web:7afed974` · soak 통과 ·
  엣지 `no upstreams available` **0건** · `/healthz` 200). 실 Chrome/150 `https://localhost/`:
  ① 프리뷰와 같은 39첨부 대화 — 전건 이름순, Run 1 과 차이 0.
  ② **요청의 출발점이 된 파일 세트**(`20260709_[MV] Log_v2 이슈 대응_*.sql` 6건, 요청 스크린샷에서
  `08 → 01 → 02 → 03 → 04 → 09`) — 라이브에서 `01 → 02 → 03 → 04 → 08 → 09`.
  라이브 데이터 변경 0(열람 경로만).
- Run 기록 정본: `docs/test-runs.d/20260813T154300-attach-list-name-sort.md` Run 2.
- **Pass/Fail: PASS** — 시각검증 축 종결(이월 없음).

## TASK-20260814T010301-doc-sync-rn-0814 — 릴리즈노트 기존 2026-08-13 블록에 10항목 append (비-정책 doc-only)
- **Environment: Windows-browser (PB-0008)** — 미수행(사유): 본 변경은 사용자향 릴리즈노트 콘텐츠 데이터(`release-notes-data.js`)의 **기존 date 블록에 items append + summary 문자열 교체**만이며 렌더 로직(`release-notes.js`)·CSS·HTML 배선 델타 0 이다(신규 블록·신규 그룹도 없어 렌더 경로가 종전과 동일). 무인 cron 실행이라 인터랙티브 Windows 브라우저 브리지가 가동되지 않고, 배포는 wrapper(v3) post-merge 소관이라 이 커밋 시점에 라이브 자산이 존재하지 않는다. 대체 검증: `node --check` PASS · 구조검증(releases 48 불변 · head items 1→11 · 기존 47 블록 전량 보존 · type/area enum 위반 0 · `generated` 불변) · `tests/verify_release_notes.mjs` **34 pass / 0 fail**(편집 전 baseline 동일 = 회귀 0).
- `node --check static/release-notes-data.js` PASS · `node tests/verify_release_notes.mjs` **34 pass / 0 fail**(이 env 에서 편집 전·후 두 번 실측). 구조: `releases` 48 불변, `generated`=="2026-08-13"==`releases[0].date`, `releases[0].items` 1→11(work 6 · admin 4 · common 1), 기존 47 블록 전량 보존, type/area enum 위반 0, 스키마 외 키 0, date 내림차순 정상(말미 `"이전"` 라벨 블록은 설계상 정상), 내부용어 누출 0(37 패턴).
- 라이브 파리티 실측(배포 게이트 확증): 편집 **전** 서빙 static(`https://localhost/static/release-notes-data.js`)이 브랜치 blob 과 md5 정확 일치(`795fce1960ad33fa7ecc0e90824ea729`), 라이브 컨테이너 6종(web-a·web-b·ask-worker·insight-worker·ops-scheduler·ext-tool-mcp) 전부 `:d585250b`(= HEAD = origin/main), `/healthz` 200, 서빙 index.html 의 캐시버스터 `?v=51af138635ba`(빌드 주입 해시 — 소스 placeholder `?v=dev` 유지).
- **Pass/Fail: PASS**. CHECK#13 충족(Environment 표기 + 미수행 사유 + 대체 검증 명시).

## 20260813T1640-usage-metric-solo-anim — '요청' 경계 전환 애니메이션 복구 (frontend-only, Minor §12.3)

### 1. 케이스 정의

| # | 케이스 | 기대 |
|---|---|---|
| 1 | 총 토큰 → 요청 | SVG 노드 유지 · 모델 세그먼트가 중간 높이를 거쳐 접힘 · 단일 막대가 0 에서 자람 |
| 2 | 요청 → 총 토큰 | SVG 노드 유지 · 단일 막대가 중간 높이를 거쳐 접힘 |
| 3 | 요청 지표 표시 | 보이는 막대 = 버킷당 1개(`\|__all__`) · 모델 세그먼트 전부 0 높이 |
| 4 | 역할 가로막대 | 첫 세그먼트에 전체 값 · 나머지 0% · 폭·색 전환 |

### 2. Run 기록

- **실 Chromium 하네스 `test_usage_metric_switch.js` — 32 PASS / 0 FAIL**(기존 25 + 신규 5 + 정정 2).
- **뮤테이션 역검증 5/5 KILLED** — signature 를 수정 전 형태(`[stacked, days, models, W]`)로 되돌리면
  경계 전환 5건이 정확히 FAIL 한다(`sameSvg:false` = 재생성 = 사용자가 보고한 점프 증상 재현).
- **Environment: Windows-browser (PB-0008)** — POST-DEPLOY 이월(ESM JS 라 미머지 프리뷰 불가, 선행
  cycle 과 동일 사유). 배포 후 양방향 경계 전환을 라이브에서 재실측한다.

### 20260813T1720 후속 — 폭 흔들림(2차 기전) 회귀 잠금

1차 수정 후 **라이브에서만** 재생성이 남았다. 원인은 차트 폭(1299 vs 1287) — '요청'의 범례 부재가
페이지 높이를 줄여 세로 스크롤바를 없앤 결과다. 헤드리스 픽스처는 스크롤바가 없어 자연 재현이
안 되므로, 컨테이너 폭을 직접 바꿔 동형 조건을 만든 검사 4건을 추가했다.

- **36 PASS / 0 FAIL** (기존 32 + 폭 4)
- **뮤테이션 2/2 KILLED** — ① W 를 sig 에 복원 → "폭이 바뀌어도 재생성 안 함"·"sig 안 흔들림" FAIL
  ② in-place viewBox 갱신 제거 → "viewBox 가 새 폭으로 갱신" FAIL
- **Environment: Windows-browser (PB-0008)** — POST-DEPLOY 이월(ESM JS 라 미머지 프리뷰 불가, 선행
  cycle 과 동일 사유). 배포 후 양방향 경계 전환을 라이브에서 재실측한다.

- **Environment: Windows-browser (PB-0008)** — **미수행(POST-DEPLOY 이월)**, 사유: ESM JS 변경이라
  미머지 `docker cp` 프리뷰가 원리적으로 불충분(asset stamp 미주입 → 모듈 이중 인스턴스). **2차
  기전 자체가 라이브 실측으로 규명됐다** — 1차 배포본에서 `sameSvg:false` 와 sig 폭 차이(1299 vs
  1287)를 직접 관측해 원인을 갈라냈고, 그 조건을 헤드리스에 이식해 회귀를 잠갔다. 재배포 후 양방향
  경계 전환을 실 Chrome 에서 재실측한다.

### 20260813T1810 후속 — 신규 세그먼트 '첫 등장' 전환 (라이브 전용 축)

1·2차 수정 배포 후 라이브 재실측에서 양방향 `sameSvg:true` + 중간값 확인(보고 증상 해소). 남은
미세 결함 1건: **그 지표에서 처음 생기는 막대**(아직 노드가 없는 세그먼트)는 첫 등장 때 점프했다
(`enterMid == enterEnd == 70.3`). 원인은 삽입 직후 `requestAnimationFrame` 한 번으로 목표값을 준 것
— 브라우저가 시작 스타일(높이 0)을 확정하기 전에 두 값이 같은 프레임에 들어가면 transition 이
발동하지 않는다. 삽입 직후 강제 reflow(`getBoundingClientRect()`)로 시작 스타일을 확정한 뒤 목표값을
주도록 바꿨다(세로·가로 막대 양쪽).

**검사의 판별력 한계(정직 표기)**: 이 축을 잠그는 검사(#13 "신규 막대의 첫 등장도 0 에서 자란다")를
추가했으나, **헤드리스에서는 뮤턴트(rAF 복원)가 살아남는다** — 헤드리스 Chromium 은 rAF 한 번으로도
transition 이 걸려 결함 조건이 성립하지 않는다. 즉 이 검사는 헤드리스에서 vacuous 하며, **판별은
라이브 실측이 담당**한다. 검사를 남기는 이유는 회귀 시 라이브에서 같은 스크립트로 즉시 재확인하기
위함이지 헤드리스 green 을 근거로 삼기 위함이 아니다.

- **Environment: Windows-browser (PB-0008)** — **미수행(POST-DEPLOY 이월)**, 사유: ESM JS 라 미머지
  프리뷰 불가. **이 3차 결함 자체가 라이브 실측으로만 드러난 축**이며(헤드리스 뮤턴트 생존),
  재배포 후 같은 probe 스크립트로 `enterMid < enterEnd` 를 실 Chrome 에서 확인한다.

## 20260813T1900-usage-metric-profile — 프로필 '사용 내역' 지표 체계 정합 (frontend + profile 집계)

| # | 케이스 | 기대 |
|---|---|---|
| 1 | 카드 구성 | 지표 **정본과 동일 순서·동일 라벨** 8종(캐시 2종 포함) |
| 2 | 카드 값 | totals 와 일치(캐시 읽기 1,200 실측) |
| 3 | 지표 전환 | 노드 유지 + 중간 프레임이 시작·끝 사이 |
| 4 | 값 정합 | 총 토큰 3:1 → 비용 0.6 → 캐시 읽기 도넛 5:1 |
| 5 | 비-가산(요청) | 보이는 막대 버킷당 1개 · 비율 1.5 · 경계 전환도 재생성 아님 |
| 6 | 안내 문구 | 관리 화면과 **같은 문구**(정본 함수 공유) |
| 7 | 도넛 | 중앙 라벨·총계가 지표를 따름 |

- **`tests/headless/test_profile_usage_metric.js` — 15 PASS / 0 FAIL** (실 Chromium)
- 관리 화면 하네스 **37 PASS** 유지(공용 정의 전환 후에도 회귀 0)
- pytest **4,441 passed / 4 skipped**
- **Environment: Windows-browser (PB-0008)** — POST-DEPLOY 이월(ESM JS · 미머지 프리뷰 불가).
  배포 후 프로필 드로어에서 카드 클릭 전환을 실 Chrome 으로 실측한다.

## 20260813T2000-usage-metric-final-postdeploy — 관리·프로필 양 화면 POST-DEPLOY 라이브 실측 (doc-only)

`main ea25a840` 배포(무중단 0건 · web-a/b 파리티 · `usage-metrics.js` 서빙 확인) 후 실 Chrome/150 실측.

### Run 2026-08-13 — Environment: Windows-browser (PB-0008)

**관리 콘솔** — 3개 기전 전건 해소:

| 축 | 실측 |
|---|---|
| 총 토큰 → 요청 | `sameSvg:true` · 사라지는 세그먼트 28.3 → **22.39** → 0 · 새 막대 **14.68 → 70.3**(0에서 자람) · `anims:["height","y"]` |
| 요청 → 총 토큰 | `sameSvg:true` · 단일 막대 70.3 → **48.71** → 0 · `anims:["height","opacity"]` |

**프로필 사용 내역** — 관리 화면과 동일 거동:

| 축 | 실측 |
|---|---|
| 카드 8종 | 요청 88 · 호출 523 · 총 토큰 22,482,623 · 입력 21,812,408 · 출력 670,215 · 캐시 0/0 · $26.18 |
| 총 토큰 → 비용 | `sameSvg:true` · 105.4 → **101.97** → 97.1 · `anims:["height","y"]` |
| 총 토큰 → 요청 | `sameSvg:true` · 접히는 중 **67.31** · 새 막대 **36.81 → 120** · 단일 막대 12개 · 안내 문구 일치 |

프로필 캐시가 0인 것은 **정상**이다 — 캐시 기록은 계정 10·50 의 대화에 있고(각 471,671/316,883 · 293,311/356,582)
이 계정(bootstrap_admin)의 본인 대화에는 아직 없다. 프로필은 정의상 본인 소유 대화만 집계한다.

### 검증 함정 2건 (재현 시 주의 — 둘 다 코드 결함으로 오인할 뻔했다)

1. **`getBoundingClientRect()` 로는 SVG geometry transition 이 안 보인다** — layout box 가 최종 style
   값 기준이라 진행 중 값이 반영되지 않는다. `getComputedStyle().height` + `getAnimations()` 로 본다.
2. **`display:none` 조상 아래에서는 transition 이 발동하지 않는다(브라우저 정상 동작)** — 프로필
   드로어를 열 때 기본 탭이 '프롬프트'라, '계정' 탭을 활성화하지 않은 채 서브탭만 클릭하면 차트가
   `drawer-pane:none` 아래에 있어 전환이 죽는다. 사용자 경로대로 **계정 탭 → 사용 내역** 순으로 열고
   `getClientRects().length > 0` 을 확인한 뒤 측정해야 한다. (부모 체인 덤프로 갈라냄:
   `drawer-pane hidden:none` → 탭 활성화 후 `drawer-pane:flex`.)

### Run (2026-08-14) — usage-pager-sticky: 사용 기록 페이저 바닥 고정 — **Environment: Windows-browser (PB-0008 — 본 결함 자체가 직전 cycle 배포본의 실 Windows Chrome 실측에서 나왔다: 첫 화면에 페이저가 보이지 않아 페이지 이동에 매번 50행 스크롤이 필요했다. 수정 후 재실측은 배포 후 수행하며, 그 결과를 본 Run 에 이어 기록한다)**

- 변경: `src/static/css/search-audit.css`(`.usage-rec-pager` sticky bottom + 배경/경계선) ·
  `src/static/admin/usage.js`(페이저 노드를 안내 문구 뒤로).
- PRE-COMMIT: `tests/test_usage_records_sort_page.py` **9 PASS**(L9 신규 — sticky·배경·마크업 순서) ·
  `tests/verify_usage_records_sort_page.mjs` **50 PASS**(무회귀).
- 직전 cycle 라이브 실측 요지(같은 표면, 배포 c5ac13ee): 총 298건/6페이지 · 기본 토큰 내림차순 ·
  `aria-sort` 정확 · 정렬 클릭(호출 내림 2,198→701→680, 오름 1,1,1) · 페이지 이동/25행/전체 전환 ·
  경계 버튼 비활성 · 키보드 포커스 유지 · 주체 열이 표시 라벨 기준 정렬(sentinel 미노출) ·
  정렬 후 시스템 행 클릭이 그 행의 대상 화면으로 이동("그래프 노드 분석 · dbGame.Achievement" →
  관계도 탭) · Caddy `no upstreams available` 0.

### POST-DEPLOY 결과 (2026-08-14, 배포 c5ac13ee → fce6d64c, deploy-web-only) — **Environment: Windows-browser** — PASS (정렬 · 페이지네이션 · nav · 키보드 · 페이저 가시성)

- 방법: PB-0008 — `bin/win-browser.py` relay 실 Windows Chrome/150.0.7871.128(CDP, relay @ 172.26.144.1:9223),
  `https://localhost/admin`(bootstrap admin 세션), `관리 콘솔 > AI 운영 현황 > LLM 사용량` 에서 모델
  막대 클릭 → 사용 기록 모달. 하드 리로드 후 실행. 배포 확증 — `/livez git_commit` = c5ac13ee(1차)
  → fce6d64c(2차), 서빙 `usage.js` 에 `data-usage-sort` 4건, 서빙 `search-audit.css` 에
  `position: sticky; bottom: -1px` 1건. **무중단 실측** — Caddy `no upstreams available` **0건**(양 배포).
- **AC-1/2 정렬 PASS**: 열 머리 클릭으로 정렬 전환. '호출' 내림차순 상위 3 = 2,198 / 701 / 680,
  재클릭 오름차순 = 1 / 1 / 1. `aria-sort` 가 `descending`↔`ascending` 로 정확히 추종(비활성 열 `none`).
  '추정 비용' 열도 동일. 정렬 변경 시 **1페이지로 복귀** 확인.
- **AC-3 페이지네이션 PASS**(라이브 298건 기준): `총 298건 중 1–50 @1/6` → 다음 `51–100 @2/6`(50행)
  → 마지막 `251–298 @6/6`(48행, '다음'·'마지막' 비활성) → 처음 `1–50 @1/6`('이전'·'처음' 비활성).
  페이지당 25행 → `1–25 @1/12`, '전체' → `1–298 @1/1`(298행), 50행 복귀 정상.
- **AC-4 첫 화면 무회귀 PASS**: 모달 개시 시 토큰 내림차순 1페이지 50행(`토큰 ▼`).
- **AC-5 표시-정렬 정합 PASS**: '주체' 열 정렬 결과가 화면 라벨 기준("대화 (소유자 없음)" …),
  본문에 raw sentinel(`__`) 노출 0.
- **AC-6 nav 정체성 PASS**: 정렬 축을 바꾼 뒤 시스템 행 클릭 — "그래프 노드 분석 · dbGame.Achievement"
  → 관계도(graph) 탭으로 이동 + 모달 닫힘. 툴팁도 "관계도 화면으로 이동 (데이터소스 여럿 — 화면까지
  이동)" 로 정직 표기.
- **키보드 연속 조작 PASS**(적대 리뷰 [P2] 회귀 가드): 정렬 버튼 포커스 → 활성화 후에도 포커스가
  그 열 머리(`data-usage-sort=cost_usd`)에 남고, 페이지 '다음' 활성화 후에도 그 버튼에 남는다.
- **페이저 가시성 PASS**(fce6d64c 재실측): 모달을 연 직후(`scrollTop=0`)에 페이저가 스크롤 뷰 안에
  있고(`position: sticky`, 배경 `rgb(255,255,255)`), 목록 끝까지 스크롤해도 안내 문구와 **겹치지
  않는다**(hint top 772 < pager top 801). 시각 증거 = 본 cycle 캡처(첫 화면 하단에
  `총 206건 중 1–50  « ‹ 1/5 › »  페이지당 50행`).
- **미검증(정직)**: 열 폭은 정렬·페이지 이동으로 **표시되는 행 내용이 바뀌면 재계산된다**(auto
  table-layout). 실측 델타 = 본문 열 +26px / 주체 −17px / 토큰 −9px(1144px 표 기준 ≤4%). 기능 결함은
  아니나 페이지를 넘길 때 표가 미세하게 움찔한다 — 고정 폭으로 잡으려면 열 폭 배분 전략(`width:1%`
  + 잔여 흡수)을 바꿔야 해 이번 범위 밖으로 남긴다(REPORT 이월). 브라우저 콘솔 에러는 별도 수집
  채널을 태우지 않아 **확인하지 않았다**(미확인을 무결로 보고하지 않음).

## 20260813T2130-usage-card-overflow — 요약 카드 넘침 (CSS 전용, Minor §12.3)

넘침은 **픽셀로만 드러나는** 부류라 DOM 검사로는 못 잡는다(§16.6 evidence 분기). 폭을 스윕하며
① 카드가 컨테이너를 벗어나는지 ② 텍스트가 카드를 벗어나는지(`scrollWidth > clientWidth`)를 실
Chromium 에서 정량 측정한다.

| # | 케이스 | 결과 |
|---|---|---|
| 1 | 폭 320~900px 9단계 × 라이브 실제 값 | 넘침 **0** |
| 2 | 값 9자리(`123,456,789`) @340px | 넘침 **0** |
| 3 | 현실 상한 12자(`999,999,999,999`) @320px | 넘침 **0** |
| 4 | 관리 콘솔 카드 420~1400px | 넘침 **0**(기존 `minmax(160px)` 로 이미 안전 — 변경 없음) |

**수정 전 실측(결함 재현)**: 320px 4건 · 340px 4건 · 420px 6건 · **900px 6건** — 좁은 화면만의
문제가 아니라 8장 균등 분배 구조 자체의 문제였다.

**뮤테이션 2종**: ① 구 flex 복원 → 3건 FAIL(사용자 보고 상태 재현) ✓ ② `clamp` 제거 → **생존**
→ 그 방어를 채택하지 않고 제거(검증되지 않는 복잡도).

- **Environment: Windows-browser (PB-0008)** — POST-DEPLOY 이월(자산 배포 후 드로어 폭을 실제로
  줄여가며 재실측). CSS 전용이라 `docker cp` 프리뷰가 가능한 부류지만, 같은 cycle 의 JS 변경이
  없으므로 배포 후 확인이 더 정확하다.

### 20260813T2210 후속 — 트랙·폰트를 뮤테이션으로 확정

선행 값(트랙 150px·폰트 14px)은 뮤테이션에서 문제가 드러났다. **하네스 패딩이 라이브와 달라
(16px vs 실측 32px) 트랙 결정을 판별하지 못했고**, 그 상태에서 고른 값이 사용자가 보던 폭을 1열로
전락시켰다. 패딩을 실측값으로 맞춘 뒤 재탐색해 **트랙 138px · 폰트 15px** 로 확정했다.

| 뮤턴트 | 결과 |
|---|---|
| 구 `flex:1 + min-width:84px`(보고 상태) | **4건 FAIL** — 넘침 검사 전부 |
| 트랙 150px | **1건 FAIL** — "370px 이상 2열 유지" |
| 트랙 120px | **1건 FAIL** — "라이브 최대치(11자) @320px" |
| 폰트 14px (선행값) | **생존** → 15px 로 되돌림(검증되지 않는 축소) |
| container query `clamp` | **생존** → 미채택 |

**6 PASS / 0 FAIL**. 보장 범위: 11자 @320px(최소 드로어) · 12자 @420px 이상 · 370px 이상 2열.

- **Environment: Windows-browser (PB-0008)** — **미수행(POST-DEPLOY 이월)**, 사유: 이 조정의 근거가
  된 1열 전락 자체를 **선행 배포본 라이브 캡처로 확인**했고(370px 드로어에서 1열), 재배포 후 같은
  폭에서 2열 복귀 + 넘침 0 을 실 Chrome 으로 재실측한다.
### Run (2026-08-14) — profile-usage-sort-page: 프로필 사용 내역 표 정렬·페이지네이션 — **Environment: Windows-browser (PB-0008 배포 후 실측 예정 — 프로필 사용 내역은 로그인 세션 + 본인 라이브 집계가 있어야 열리고, sticky 열 머리·페이저는 레이아웃 산물이라 jsdom 으로 대체 불가. 다만 이번엔 레이아웃 축을 **실 Chromium 하네스로 선행 계측**했다: `tests/headless/verify_usage_pager_layout.py` 12 PASS, 뮤턴트로 검출력 확인. visual_verification_scope: always)**

- 대상: `src/static/app/profile.js`(모달 정렬·페이징) · `src/static/admin/usage.js`(esc 강화) ·
  `src/static/css/search-audit.css`(스크롤러 단일화 · 페이저 줄바꿈).
- **동작 — `tests/verify_profile_usage_sort_page.mjs` 45 PASS**: 기본 상태 8 · 정렬 6 ·
  페이지네이션 10(1건 경계 포함) · 키보드 4 · 기존 동작 회귀 8(deep-link 같은 탭·차단 배지·
  이스케이프·빈 목록엔 페이저 없음) · **관리 콘솔 판과의 규칙 정합 8**(기본 축·방향·페이지 크기·
  선택지·첫 클릭 방향·1페이지 복귀·포커스 복원·CSS 공유).
- **레이아웃 — `tests/headless/verify_usage_pager_layout.py` 12 PASS**(실 Chromium, 두 화면 ×):
  L1 스크롤해도 열 머리가 남는다 · L1b 제자리 고정 · L2 320/480/640px 넘침 없음 · L3 첫 화면
  페이저 가시성. **뮤턴트 검증** — tablewrap 을 `overflow-x:auto` 로 되돌리면 L1/L1b 가 4건 FAIL.
  ⚠ L2 는 줄바꿈을 제거한 뮤턴트도 통과했다 = **현재 검출력 없음**(회귀 가드로만 유지).
- **구조 — `tests/test_usage_records_sort_page.py` 16 PASS** · admin 하네스 50 PASS 무회귀 ·
  feature-0003 전체 스위트 회귀 0.

### Run 2026-08-13 — Environment: Windows-browser (PB-0008) · POST-DEPLOY 종결

`main 3af15fc2` 배포(무중단 0건 · 파리티) 후 실 Chrome/150 에서 드로어 폭을 실제로 줄여가며 실측.

| 드로어 폭 | 요약 컨테이너 | 넘침 | 열 |
|---|---|---|---|
| 700px | 636px | **0** | 4 |
| 520px | 456px | **0** | 3 |
| 420px | 356px | **0** | 2 |
| **370px**(보고 상태) | 306px | **0** | **2** |
| 340px | 276px | **0** | 1 |
| 320px | 256px | **0** | 1 |

보고된 폭(≈370px)에서 **넘침 0 + 2열 유지** — 종전처럼 읽히면서 값이 온전히 보인다. 340px 이하는
1열로 떨어지지만 카드가 넓어져 값은 그대로 다 보인다(의도된 거동).
### POST-DEPLOY 결과 (2026-08-14, 배포 ac1403c4, deploy-web-only) — **Environment: Windows-browser** — PASS (프로필 판 전 축 + 관리 콘솔 판 재확인)

- 방법: PB-0008 — `bin/win-browser.py` relay 실 Windows Chrome/150.0.7871.128, 하드 리로드 후
  ① `https://localhost/` 작업 화면 → 프로필 → 계정 → **사용 내역** → 모델 막대 클릭,
  ② `https://localhost/admin` → AI 운영 현황 → LLM 사용량 → 막대 클릭(스크롤러 변경 영향 재확인).
  배포 확증 — `/livez git_commit=ac1403c4`, 서빙 `app/profile.js` 의 `data-usage-sort` 4건,
  서빙 `search-audit.css` 의 `overflow: visible` 2건. Caddy `no upstreams available` **0**.
- **프로필 판 — 정렬 PASS**: 열 머리 클릭으로 '호출' 내림차순(44/43/43) ↔ 오름차순(2/3/3) 전환,
  `aria-sort` 가 그 열만 `ascending`(나머지 `none`). '대화' 열은 텍스트 오름차순으로 시작.
- **프로필 판 — 페이지네이션 PASS**: 라이브 30건에서 페이지당 25행 전환 → `총 30건 중 1–25 @1/2`
  (25행), '다음' → `26–30`(5행) + '다음' 비활성·'이전' 활성. 기본은 `1–30 @1/1`.
- **프로필 판 — 첫 화면 무회귀 PASS**: 모달 개시 시 `토큰 ▼` 내림차순, 페이저가 **열자마자 보인다**
  (`position: sticky`). 시각 증거 `docs/evidence/pb0008-profile-usage-sort-20260814.png`.
- **프로필 판 — 키보드 PASS**: 정렬 버튼 활성화 후에도 포커스가 그 열 머리(`total_tokens`)에 남는다.
- **프로필 판 — sticky 열 머리 PASS**(이번 cycle 수정의 핵심): 목록 끝까지 스크롤해도 열 머리 top 이
  151 → 151 로 고정되고 뷰 안에 남는다. 수정 전이라면 목록과 함께 사라졌을 축이다.
- **관리 콘솔 판 재확인 PASS**(스크롤러 단일화의 영향면): 204건 목록에서 스크롤 후에도 열 머리 top
  142 → 142 고정 + 뷰 유지, 페이저 가시. **가로 넘침 회귀 없음** — 표 폭 1185 = 본문 폭 1185,
  `.usage-conv-body`/`.usage-conv-tablewrap` 양쪽 가로 스크롤 0(overflow 를 옮긴 뒤에도 잘림 없음).
- **미검증(정직)**: 브라우저 콘솔 에러는 별도 수집 채널을 태우지 않아 **확인하지 않았다**.
  좁은 폭(모바일) 실측은 실 Windows 창 리사이즈 대신 헤드리스 320/480/640px 계측으로 갈음했다.

### Run (2026-08-14) — exttasks: 관리 콘솔 'AI 운영 현황 > 외부 AI 작업' 서브탭 — **Environment: Windows-browser (PB-0008 배포 후 실측 — 아래 사유)**

feature-0041 AC-7(외부 AI 답변 보존)의 열람 면. 파일 소유가 feature-0003 이라 Run 을 여기 둔다
(변경: `static/admin.html` 서브탭·서브페인 · `static/admin.js` lazy-load 배선 ·
`static/admin/exttasks.js` 신규).

**머지 전 실측을 하지 않은 사유(카고컬트 방지 — 실제 제약)**: 이 화면은 (a) 관리 콘솔 로그인
세션과 (b) 배포된 `/api/ai/tasks` 응답이 있어야 열린다. 그리고 이 저장소에서 **JS 는
`docker cp` 로 선(先)검증할 수 없다** — 자산 스탬프가 주입되지 않아 `admin.js` 가 이중
인스턴스로 뜨고 Chrome 모듈 캐시가 구버전을 실행해, 서버 파일이 신버전이어도 화면은 구버전이
된다(기존 실측 교훈). 그 상태의 "PASS" 는 무의미하므로 **POST-DEPLOY 로 미룬다.**

브리지 자체는 가용함을 확인했다: relay `http://172.26.144.1:9223` (Chrome/150.0.7871.128),
`eval "1+1" → 2`. (`/tmp/win-browser-relay.log` 가 root 소유라 실행 사용자에게 막혀 있었고,
소유권 정정 후 기동됨 — 재발 시 같은 지점을 먼저 본다.)

**배포 후 확인할 것**: 서브탭 nav 에 '외부 AI 작업' 등장 · 목록 표 렌더(개설/상태/원 질문/
datasource/질문 판정/답변) · 행 클릭 시 상세 아코디언(질문·**각인된 답변 본문**·도구 호출 이력)
· 답변 칸 3-상태 분기(본문 있음 / 미제출 / **보존 안 됨**) · 기존 서브탭 3종(LLM 사용량·운영
현황·추론) 보존.

→ **결과는 아래 POST-DEPLOY Run 에 기록한다.**

### Run 2026-08-14 — exttasks POST-DEPLOY (**Environment: Windows-browser** · PB-0008 · 라이브 `6a858599`) — 결함 1건 적발·수정

Bridge: relay `http://172.26.144.1:9223` (Chrome/150.0.7871.128) · 하드 리로드 후 실측.
Evidence: `docs/test-runs.d/evidence/REV-20260814-exttasks-postdeploy.png`

**PASS**

| 확인 | 결과 |
|---|---|
| 서브탭 nav | `LLM 사용량` · `운영 현황` · `추론` · **`외부 AI 작업`** 4종, 기존 3종 보존 |
| 목록 표 | 6열(개설·상태·원 질문·datasource·질문 판정·답변) 렌더, 2행 |
| 상세 아코디언 | 행 클릭 → task/client/datasource/제출시각 + 원 질문 + 답변 영역 |
| **도구 호출 이력** | thead 1 + tbody **34행** — `open_task` → `get_task_context` → `describe_*` → `execute_sql` → `submit_answer`(7.9 KB) |
| 원장 대조 | 상세의 `submit_answer` 7.9 KB = PG 원장 `bytes_out` 8,125 와 일치 |
| **3-상태 분기** | 기존 task 2건이 `제출됨` + **`보존 안 됨`** 으로 표시 — 보존 도입 이전 제출이라 본문이 없다는 사실이 화면에 드러난다 |

**적발(수정함)**: 목록 답변 칸은 `보존 안 됨` 인데 **상세는 `답변이 제출되지 않았습니다`** 라고
말했다. 같은 사실을 두 화면이 다르게 서술한 것으로, 단위 테스트가 목록·상세를 각각 검사했을 뿐
**"둘이 같은 말을 하는가" 를 묻지 않아** 통과시켰다. 상세도 3-상태를 쓰도록 맞추고 사유
(롤링 창 구버전 처리 · 보존 도입 이전)와 "도구 이력은 남아 있다" 를 함께 안내한다(CHG-0027).

이 적발이 PB-0008 게이트의 값을 보여준다 — 로직은 전부 green 이었고, **실제 화면을 보고서야**
두 문구가 어긋난 것이 드러났다.

### Run 2026-08-14 — exttasks 문구 정합 POST-DEPLOY (**Environment: Windows-browser** · 라이브 `6cd45761`) — PASS

CHG-0027 수정 반영 확인. Evidence: `docs/test-runs.d/evidence/REV-20260814-exttasks-postfix.png`

| 확인 | 결과 |
|---|---|
| 목록 답변 칸 | `보존 안 됨` |
| 상세 문구 | "제출은 기록됐으나 **본문이 보존되지 않았습니다** — 롤링 배포 창에서 구버전 인스턴스가 처리했거나, 답변 보존 도입(2026-08-14) 이전에 제출된 건입니다. 아래 도구 호출 이력은 그대로 남아 있습니다." |
| 구 문구 잔존 | `답변이 제출되지 않았습니다` **0건**(eval 로 부재 단정) |
| 도구 호출 이력 | 유지(34행) |

**목록과 상세가 같은 말을 한다.** 무중단 실측: `no upstreams available` **0건**(15분 창).

배포 경위 기록: PR #1302 의 1차 배포는 실행측 `timeout` 에 걸려(exit 143) 워커 3종이
미롤아웃으로 남았다. 재실행해 완주하고 6개 서비스 커밋 일치를 확인한 뒤, PR #1304 를
`deploy-web-only` 로 반영했다(라이브 `6cd45761` — 그 사이 머지된 #1303 을 포함).
**"배포 명령이 끝났다" 와 "롤아웃이 끝났다" 는 다르다** — 서비스별 GIT_COMMIT 을 직접 세는
것이 유일한 확인 방법이다.

## 20260814T1830-step-panel-timing 실행 단계 패널 단계별 시각·간격·누적 표기 (Minor §12.3, 2026-08-14) — **Environment: Windows-browser (PB-0008 배포 후 실측 — 아래 사유)**

JS(app.js ESM 서브트리) 변경은 asset-stamp 미주입 docker cp QA 불가(모듈 캐시로 구버전 실행
— 확립된 제약)라 **배포 후 라이브 PB-0008 로 실측**한다. 사전 게이트는 jsdom 정본 렌더러 추출
실행 + CSS 계약 정적 잠금으로 커버(아래 Run). POST-DEPLOY 확인 축: ① 우측 정렬 위치(스크린샷
형광 위치와 일치) ② 최소 폭(300px) 패널에서 겹침 없이 줄바꿈 ③ 라이브 run 진행 중 폴링
재렌더에서 새 단계에 시각 표기 갱신 ④ 과거 대화(단계 보기) 소급 표기.

### Run 2026-08-14 — step-panel-timing PRE-COMMIT (Environment: jsdom/Node18) — PASS

- `tests/verify_step_panel_timing.mjs` **34 PASS / 0 FAIL** — ISO "T"·psycopg 공백 두 표기
  파싱, 간격/누적 산출(2.3초·60초 경계·음수 clamp), 첫 단계 시각만, 레거시(created_at 부재)
  표기 생략, NaN 혼재(선두·중간 레거시 — anchor=첫 유효·간격 NaN skip), 기존 헤더 요소
  (번호·도구 배지) 보존, CSS 계약(margin-left:auto·flex-wrap·tabular-nums) 정적 잠금.
- 뮤턴트 사멸 실증(§18.8 패널 P2-1 반영): 누적 anchor→prev 치환 · prev 직전-인덱스 직참조 ·
  anchor 첫-인덱스 직참조 3종 모두 **FAIL 로 검출**(사멸).
- `tests/verify_step_result_scroll_preserve.mjs` **29 PASS**(같은 렌더러 수정 무회귀).
- app.js ESM 구문 PASS(`node --check`, .mjs 사본).
- §18.8 적대 패널 `[SUBAGENT:ux+frontend]`: P1 0. 무결 확인 — V8 파싱 12변형 전부 정상 ·
  headless Chromium 300px 실렌더 5케이스 겹침 0/overflow 0/우측 정렬 유지(flex-wrap 하강 후
  포함) · 스크롤 보존/펼침 영속화 키 불변 · 3 조회 경로 created_at 동반 확인.

### Run 2026-08-14 — step-panel-timing POST-DEPLOY (Environment: **Windows-browser**) — PASS

- **Runner**: AI · **Bridge**: relay `http://172.26.144.1:9223` · **Browser**: 실 Windows Chrome/150.0.7871.128
- **대상**: 라이브 배포본 — `web-a`/`web-b` 모두 `GIT_COMMIT=ee4eb08d` (PR #1312 머지본). 코드를
  옮겨 심지 않고 **서빙 중인 `app.js`/`chat.css` 가 실 대화 데이터로 렌더한 결과만** 측정한다.
- **시나리오**: `src/scenario.step-panel-timing.json` (13 step 전건 PASS) ·
  `src/scenario.step-panel-timing-live.json` (13 step 전건 PASS)
- **Evidence**: `test-runs.d/evidence/steptiming-panel-340-live.png` ·
  `steptiming-panel-min300-zoom-live.png` · `steptiming-wrap-fallback-zoom-live.png` ·
  `steptiming-live-run-zoom-live.png`
  (패널은 뷰포트의 300~340px 조각이라 전체화면 캡처만으로 10.5px 표기가 판독 불가다 →
  **라이브 패널 DOM 을 복제해 2.2× 확대**한 캡처를 함께 남긴다. 재렌더가 아닌 복제이므로
  보이는 픽셀은 라이브 것과 같다. §16.6 '판독 가능한 캡처'.)

POST-DEPLOY 확인 축 4건 — 전부 실측:

| 축 | 실측 | 결과 |
|---|---|---|
| ① 우측 정렬 위치 | 대화 `20260814065452-7a187254`(13단계) 헤더 13건 전부 `헤더 content 우변 − 시간 우변 = 0.00px` · 넘침 0 · 형제(번호·도구 배지)와 겹침 0 | PASS |
| ② 최소 폭 300px | 리사이저를 **실제로 끌어**(mousedown→mousemove→mouseup) 최소 폭까지 좁힘 → `panelW=300`(클램프 적용) · `localStorage=300` 영속 · 겹침 0 · 가로 스크롤 0 · 우측 정렬 유지 | PASS |
| ②-b 폭 부족 시 줄바꿈 | 도구 배지를 길게 만들어 경계 강제 → 시간 표기가 **겹치는 대신** 자기 줄로 하강(top 2px→25px, 헤더 높이 19→40px) · 겹침 0 · 넘침 0 | PASS |
| ③ 라이브 run 폴링 갱신 | 새 대화에서 실 질의 1건 → 라이브 패널을 연 뒤 **재오픈 없이** 8.0초 만에 3단계→4단계로 증가, 새 단계 라벨 `19:26:39 · +7.4초 · 누적 8.1초` · 누적 단조 증가 | PASS |
| ④ 과거 대화 소급 표기 | backend 무변경(기존 `step.created_at` 재사용)이 실제로 성립 — 2026-08-14 완료 대화의 13단계 전부에 시각 표기(첫 단계는 시각만, 이후 `시각 · +간격 · 누적`) | PASS |

표기 형식은 사람 눈이 아니라 시나리오가 판정한다 — 1번째는 `HH:MM:SS`, 이후는
`HH:MM:SS · +<간격> · 누적 <경과>` 정규식에 전건 매칭해야 step 이 통과한다. CSS 계약
(`margin-left:auto` 해소 · `white-space:nowrap` · `tabular-nums` · `flex-shrink:0` ·
헤더 `flex-wrap:wrap`)도 computed style 로 함께 잠갔다.

**라이브 데이터 영향(정직)**: ③ 은 합성으로 대체할 수 없어(폴링 갱신은 `state.stepSidePanelLive`
게이트 뒤에 있고 진입점이 export 되어 있지 않다) **실 질의 1건**을 보냈다. 참여자가 나뿐인
**새 대화**를 만들어 보냈으므로 타 세션·공유방 무접촉이다. 선행 시도에서 기존 "PB-0008 스모크"
대화를 재사용했다가 그 대화가 **공유방**이라 질의가 AI ask 가 아니라 그룹 채팅 메시지로 나간
함정을 만났고(단계 0 → 축 ③ 검증 불가), 그때 남은 깨진 문장은 같은 세션에서 정정했다.
①②④ 는 읽기 전용(기존 대화 열람)이라 데이터 변경 0.

## TASK-20260817T010301-doc-sync-rn-0817 — 릴리즈노트 2026-08-16 · 2026-08-14 블록 신규 prepend(18항목) (비-정책 doc-only)
- **Environment: Windows-browser (PB-0008)** — 미수행(사유): 본 변경은 사용자향 릴리즈노트 콘텐츠 데이터(`release-notes-data.js`)의 **배열 앞단 블록 추가 + `generated` 문자열 교체**만이며 렌더 로직(`release-notes.js`)·CSS·HTML 배선 델타 0 이다(신규 블록은 기존 블록과 동일 스키마라 렌더 경로가 종전과 같고, 그룹 렌더·접힘·필터는 데이터 개수에서 파생된다). 무인 cron 실행이라 인터랙티브 Windows 브라우저 브리지가 가동되지 않고, 배포는 wrapper(v3) post-merge 소관이라 이 커밋 시점에 라이브 자산이 존재하지 않는다. 대체 검증: `node --check` PASS · 구조검증(블록 48→50 · 신규 head 2블록 date/items · 기존 48 블록 **바이트 동일** · type/area enum 위반 0 · 스키마 외 키 0 · `generated`==head.date) · `tests/verify_release_notes.mjs` **34 pass / 0 fail**(편집 전 baseline 동일 = 회귀 0, jsdom 이 실제 DOM 출력·그룹 수·접힘 기본값·필터 카운트·XSS 이스케이프를 검증한다).
- `node --check src/static/release-notes-data.js` PASS · `node tests/verify_release_notes.mjs` **34 pass / 0 fail**(이 env 에서 편집 전·후 두 번 실측). 구조: `releases` 48→50, `generated`=="2026-08-16"==`releases[0].date`, `releases[0]`(2026-08-16) items 1(work 1), `releases[1]`(2026-08-14) items 17(work 11 · admin 3 · common 3), 기존 48 블록 바이트 동일, type/area enum 위반 0, 스키마 외 키 0, date 내림차순 정상(말미 `label` 블록은 설계상 정상), 내부용어 누출 0(19축 정규식).
- 라이브 파리티 실측(배포 게이트 확증): 편집 **전** 서빙 static(`https://localhost/static/release-notes-data.js`)이 브랜치 blob 과 sha 정확 일치, 라이브 컨테이너 6종(web-a·web-b·ask-worker·insight-worker·ops-scheduler·ext-tool-mcp) 전부 `:6c7413cf`(= HEAD = origin/main), `/healthz` 200, 서빙 index.html 의 캐시버스터 `?v=7e6a0de6e2c6`(빌드 주입 해시 — 소스 placeholder `?v=dev` 유지).
- **Pass/Fail: PASS**. CHECK#13 충족(Environment 표기 + 미수행 사유 + 대체 검증 명시).

## TASK-20260819T010301-doc-sync-rn-0819 — 릴리즈노트 2026-08-14 블록 누락 1항목 append(17→18) (비-정책 doc-only)
- **Environment: Windows-browser (PB-0008)** — 미수행(사유): 본 변경은 사용자향 릴리즈노트 콘텐츠 데이터(`release-notes-data.js`)의 **기존 date 블록 items 배열에 항목 1개 추가 + 그 블록 summary 문자열 교체**만이며 렌더 로직(`release-notes.js`)·CSS·HTML 배선 델타 0 이다(추가 항목은 기존 항목과 동일 스키마·동일 enum 값이라 렌더 경로가 종전과 같다). 무인 cron 실행이라 인터랙티브 Windows 브라우저 브리지가 가동되지 않고, 배포는 wrapper(v3) post-merge 소관이라 이 커밋 시점에 라이브 자산이 존재하지 않는다. 대체 검증: `node --check` PASS · 구조검증(블록 50 불변 · `generated` 불변 · 08-14 items 17→18 · 스키마 외 키 0 · `date: "2026-08-13"` 이후 tail 바이트 동일 · head 바이트 동일) · 내부용어 누출 0.
- `node --check src/static/release-notes-data.js` PASS. 구조 실측: `releases` 50(불변), `generated`=="2026-08-16"==`releases[0].date`, `2026-08-14` 블록 items 17→**18**(area work 11 · admin 3 · common 4 / type new 7 · improved 3 · fixed 8), item 키 집합 `type,area,title,detail` 만(스키마 외 키 0), 편집 국소성 = `generated` 이전 head 와 `date: "2026-08-13"` 이후 tail 이 편집 전 파일과 **바이트 정확 일치**.
- **`tests/verify_release_notes.mjs` 미실행(정직)**: 스크립트 :21 이 `require("/tmp/node_modules/jsdom")` 를 하드코딩하고 이 환경에 그 경로가 없어 MODULE_NOT_FOUND 로 즉시 종료한다. 따라서 직전 run 의 baseline **34 pass / 0 fail 을 이 세션에서 재확인하지 못했다**(DOM 렌더·그룹 수·접힘 기본값·필터 카운트·XSS 이스케이프 축 미검증). 회귀 0 을 주장하지 않고, 위 구조·문법·국소성 검증으로 대체했음을 명시한다.
- reconcile-first 실측(편집 전): 서빙 static(`https://localhost/static/release-notes-data.js`)이 브랜치 blob 과 **byte-identical**(257,063B) · `/healthz` 200 → 파리티 갭 0.
- **Pass/Fail: PASS**(대체 검증 기준). CHECK#13 충족(Environment 표기 + 미수행 사유 + 대체 검증 명시).

## TASK-20260820T010301-doc-sync-rn-0820 — 릴리즈노트 신규 2026-08-19 블록 prepend(1항목) (비-정책 doc-only)
- **Environment: Windows-browser (PB-0008)** — 미수행(사유): 본 변경은 사용자향 릴리즈노트 콘텐츠 데이터(`release-notes-data.js`)의 **`releases` 배열에 기존 스키마·기존 enum 값만 쓰는 date 블록 1개 prepend + `generated` 문자열 갱신**만이며 렌더 로직(`release-notes.js`)·CSS·HTML 배선 델타 0 이다. 무인 cron 실행이라 인터랙티브 Windows 브라우저 브리지가 가동되지 않고, 배포는 wrapper(v3) post-merge 소관이라 이 커밋 시점에 라이브 자산이 존재하지 않는다. 대체 검증: 아래 렌더러 스위트 실측 + 문법·구조·국소성.
- `node --check src/static/release-notes-data.js` PASS. 구조 실측: `releases` 50→**51**, `generated`=="2026-08-19"==`releases[0].date`, top items **1**, 2nd `2026-08-16` items 1(불변), 3rd `2026-08-14` items 18(불변), item 키 집합 `type,area,title,detail` 만(스키마 외 키 0), type/area 값이 기존 enum 집합(`new|improved|fixed` / `work|admin|common`) 내.
- **`tests/verify_release_notes.mjs` 실행됨 — 편집 전 baseline 34 pass / 0 fail, 편집 후 34 pass / 0 fail → 회귀 0.** 직전 run 이 미실행(정직)으로 남긴 한계를 이 세션에서 해소했다: 스크립트 :21 이 `require("/tmp/node_modules/jsdom")` 를 하드코딩하는데 최신 jsdom 은 ESM-only 라 node 18 의 `require()` 에서 `ERR_REQUIRE_ESM` 로 죽는다 → **`npm install jsdom@24 --prefix /tmp`** 로 CJS 호환 버전을 핀 설치해 실행했다. DOM 렌더·전체/작업화면 그룹 수(데이터에서 동적 산출)·접힘 기본값·필터 칩 카운트·XSS 이스케이프·빈 상태 축 전건 PASS.
- 내부용어 누출 0(정규식 기계 검증: feature-id·모듈/함수/파일명·테이블명·digest/rederive/grounding/BLOCK/revise_failed/리뷰어/프롬프트). 분량 컨벤션 준수(summary 285자 · detail 404자 — 기존 max 1019/714 이내).
- reconcile-first 실측(편집 전): 서빙 static(`https://localhost/static/release-notes-data.js`)이 브랜치 blob 과 **byte-identical**(md5 `3f857ffa02487e9e10c5a9fb023727f3`, 258,749B) → 파리티 갭 0. 라이브 이미지 tag `22423bd5` == HEAD.
- 캐시버스터: 수기 bump **없음**. `index.html`/`admin.html` 의 `release-notes-data.js?v=dev` placeholder 각 1회 잔존 실측(ITEM-09 — 빌드 `inject_asset_stamp.py` content-hash 주입 · `bin/deploy-web.sh:1320` 이 baked 이미지 placeholder 잔존 시 ABORT).
- **Pass/Fail: PASS**. CHECK#13 충족(Environment 표기 + 미수행 사유 + 대체 검증 명시).

## 20260824T1150-step-timing-attribution 단계 시간 귀속 재정의 (Major §12.3, 2026-08-24) — **Environment: Windows-browser (PB-0008 배포 후 실측 — 아래 사유)**

JS(app.js ESM 서브트리) 변경은 asset-stamp 미주입 docker cp QA 불가(모듈 캐시로 구버전 실행
— 확립된 제약)라 **배포 후 라이브 PB-0008 로 실측**한다. 또 이번 변경의 핵심 축(도구 실측
`elapsed_ms`)은 **배포 이후 새로 도는 run 부터** 생기므로, 라이브 신규 run 없이는 정확 경로를
관측할 수 없다. 사전 게이트는 아래 jsdom/pytest Run 이 커버한다. POST-DEPLOY 확인 축:
① 신규 run 에서 추론 단계가 자기 소요를 갖는가(초판은 `+0.0초`) ② 같은 run 의 SQL 단계가
1초 미만으로 표시되는가(초판은 `+2분 3초`) ③ 과거 대화가 근사 `~` 와 소요 비움으로 정직하게
표시되는가 ④ 누적이 단조 증가하는가.

### Run 2026-08-24 — step-timing-attribution PRE-COMMIT (Environment: jsdom/Node18 + CLI/pytest) — PASS

- `tests/verify_step_panel_timing.mjs` **70 PASS / 0 FAIL**(전면 재작성) — 귀속 규칙 4갈래
  (A 실측 정확 / B 과거 대화 폴백 / C activity→activity / D 마지막 activity 진행 중) ·
  시계 출처 불일치 0 clamp · NaN 혼재에서 anchor·next 탐색 · **사용자 보고 화면 재현 회귀**
  ([H] 라이브 run 20260824021929-c71393cf 축약: 추론 소요 칸 `2분 3초`, SQL 소요 칸 `0.4초`
  — 초판은 이 두 칸이 각각 `+0.0초`/`+2분 3초` 였다) · 근사 표식 `~` 와 툴팁 문구 · 빈/비배열 방어.
- 프론트 뮤턴트 **10종 전건 사멸**: ① 초판 회귀(activity 도 간격 그대로) ② 도구 실측 무시
  ③ activity 직후 도구의 미지 소요를 0 으로 지어냄 ④ `approx` 항상 false ⑤ 누적을 종료 대신
  기록 시각 기준 — 여기에 codex 반영분 ⑥ `Number()` 강제변환 복귀(null→0) ⑦ 누적 단조 보장
  제거 ⑧ 시작 시각 clamp 제거 ⑨ 건너뛴 단계 근사표식 제거 ⑩ 레거시 도구→도구 "정확" 복귀.
  각각 1~5건 FAIL 로 검출된다.
- **codex 적대 리뷰**(`[CODEX:step-timing-attribution]`, REV-20260824T115000): **[P1] 0 · [P2] 5**,
  전건 반영. 그중 2건은 **테스트가 vacuous 하던 사각**을 잡았다 — `Number(null)===0` 경로와
  "아무 finally 에 변수명만 있으면 통과" 하던 AST 축. 반영 후 새 축을 추가해 뮤턴트로 재검증했다.
- `tests/verify_step_result_scroll_preserve.mjs` **29 PASS**(같은 렌더러 수정 무회귀) ·
  app.js ESM 구문 PASS(`node --check`, .mjs 사본).
- cross-feature 백엔드: `feature-0002` `tests/test_step_elapsed_attribution.py` 7 PASS +
  뮤턴트 2종 사멸 (해당 feature TEST.md 참조).
- ⚠️ jsdom 은 이 환경에 미설치 상태였다 — `npm i --prefix /tmp jsdom@24` 로 설치해 실행했다.
  최신 jsdom(27.x)은 **ESM 전용이라 Node 18 의 `require` 에서 `ERR_REQUIRE_ESM`** 로 죽고,
  하네스의 로더가 그 예외를 삼켜 "jsdom 미설치" 로만 보인다(다음 사람이 같은 벽에 서지 않게 기록).

### Run 2026-08-24 — step-timing-attribution POST-DEPLOY (Environment: **Windows-browser**) — PASS

- **Runner**: AI · **Bridge**: relay `http://172.26.144.1:9223` · **Browser**: 실 Windows Chrome/151.0.7922.170
- **대상**: 라이브 배포본 — `web-a`/`web-b`/`ask-worker`/`insight-worker` **4개 서비스 전부
  `GIT_COMMIT=07755e05`**(PR #1318 머지본). 서빙 `app.js` 에 `_computeStepTimings` 도달 확인.
- **시나리오**: `src/scenario.step-timing-attribution.json` (12 step 전건 PASS)
- **Evidence**: `test-runs.d/evidence/steptiming-attr-new-run-exact-live.png` ·
  `steptiming-attr-legacy-fallback-live.png`

| 축 | 실측 | 결과 |
|---|---|---|
| A. 신규 run(도구 실측 있음) = **정확** | 새 대화 `20260824035636-1633201e`(9단계·도구 2). 추론 단계 `12:56:39 · **11초**`, 그 직후 SQL `12:56:51 · **0.8초**`. 근사 표식 0 · `+` 접두 0 · 누적 단조 · 첫 단계 누적 생략 | PASS |
| B. 과거 대화(실측 없음) = **정직한 폴백** | `20260814065452-7a187254`(13단계). 추론 `~11초`(근사 표식), **직후 도구는 소요 칸 자체가 비어 있고** 툴팁이 "기록만으로 분리할 수 없어 표시하지 않습니다", 도구→도구는 `~0.1초` | PASS |
| C. 오귀속 해소(회귀) | 같은 자리 초판 표시는 추론 `+0.0초` / 도구 `+11초` 였다. 이제 시간이 **돌던 단계**에 붙는다 | PASS |

판정은 사람 눈이 아니라 시나리오가 한다 — 도구 소요가 3초를 넘으면(추론 흡수 흔적) · 추론이
자기 소요를 못 가지면 · 신규 run 에 근사 표식이 있으면 · `+` 접두가 남아 있으면 · 누적이
비단조면 · 폴백 자리에 숫자가 있으면 step 이 실패한다.

⚠️ **캡처 함정(기록)**: 확대 오버레이 초판은 `document.body.appendChild(host)` 가 빠져 있었다.
detached 노드에서도 `querySelectorAll` 은 개수를 맞게 돌려주므로 **단언은 통과하는데 스크린샷에는
오버레이가 없었다** — 캡처가 근거가 되지 못하는 상태. 부착 여부를 단언에 넣어 잠갔다.

**라이브 데이터 영향(정직)**: A 축은 도구 실측이 배포 이후 run 에만 생기므로 합성으로 대체할 수
없어 **새 대화에 질의 1건**(테이블 목록 5개)을 보냈다. 참여자가 나뿐인 새 대화라 타 세션·공유방
무접촉. B 축은 읽기 전용.

- TEST-0130 (REQ-20260824-0335 / AC-0630~0632, `tests/test_stale_threshold_derives_from_attempt_cap.py`):
  stale 임계가 per-attempt 상한 안쪽으로 다시 밀리지 않도록 불변식을 고정한다. **19 PASS**
  (초판 12 + §18.8 codex 흡수분 7). high-water 는 프로세스 전역 상태라 autouse fixture 로
  저장·리셋·복원한다 — 없으면 실행 순서 의존 flake 가 된다.
  - 불변식: 상한 5·60·300·900·1800·3600 전 구간에서 `_effective_stale_timeout_seconds() > cap`.
    상한이 하한을 넘으면 정확히 `cap + WEB_PROGRESS_STALE_MARGIN_SECONDS`.
  - 운영자 의도 보존: 상한이 작으면(60) 임계는 `WEB_PROGRESS_STALE_TIMEOUT_SECONDS` 그대로.
  - fail-open 2종: `get_int` 예외 / 비양수(0) → 종전 상수.
  - **사고 재현 입력**: 상한 1800 · 마지막 활동 1300초 전 `processing` → `('processing', False)`
    (종전 코드에서는 정확히 `stale_error` 였다). 목록 경로(`_compute_display_status`)와 스냅샷 번들
    경로(`_display_status_from_step_at`)가 **같은 판정**임을 함께 단언 — 갈리면 목록과 long-poll 이
    어긋난다.
  - 가드 무력화 아님: 마지막 활동이 `상한 + margin + 60`초 전이면 여전히 `('stale_error', True)`.
  - 봉인 B: `_iso_or_empty(naive)` 가 `+00:00` 접미를 붙인다(로컬 오해 차단) · 비-datetime 은 빈 문자열
    · `last_active` 는 status_at 과 step 시각 중 **나중** 것.
  - 프런트 소스 잠금 2종: 부제와 사이드바 툴팁이 **둘 다** `last_activity_effective_at` 우선 참조
    (한쪽만 고치면 같은 화면에 서로 다른 "마지막 활동" 이 보인다) · 부제 상태 칸에 원시 enum
    `${conversation.status}` 가 남아 있지 않다.
  - §18.8 codex 흡수분: 상한 **하락 시 임계 무축소**(high-water) · 조회 실패 시 high-water 유지 ·
    비정상 상한(10^9) clamp → `_STALE_CAP_CLAMP_MAX + margin` · clamp/margin 경계 bound ·
    `_parse_kv_timestamp` offset→UTC 4케이스(`+09:00`/`+00:00`/`Z`/naive) + 실패 2케이스 ·
    terminal 도 `last_active` 반환(그 경로가 step 을 조회하면 **테스트가 실패**하도록 잠금) ·
    인자형 terminal 은 status_at/step 의 max.
  - 기존 계약 갱신: `test_orphan_run_stale_recovery.py`(3-튜플 + `last_active` 단언) ·
    `test_web_perf_p1.py`(임계 상수 → 파생 함수). 관련 3파일 합계 **42 PASS**.

## TASK-20260825T010305-doc-sync-rn-0825 — 릴리즈노트 신규 2026-08-24 블록 prepend 검증
- **Environment: Windows-browser (PB-0008)** — 미수행(사유: 본 changeset 은 릴리즈노트 **콘텐츠 데이터 + 그 companion 문서** 전용이고 렌더 로직(`release-notes.js`)·마크업(`index.html`/`admin.html`)·CSS 델타가 **0** 이다. 무인 cron run 이라 인터랙티브 브리지가 가동되지 않고, 배포는 wrapper 소유(v3)라 이 커밋 시점에 라이브 화면이 존재하지 않는다. 대체로 아래 DOM 테스트 + 구조 단언을 수행했다).
- `node --check static/release-notes-data.js` → PASS.
- `node tests/verify_release_notes.mjs` → **ALL PASS 34 / 0**. 편집 **전** 동일 스크립트를 cycle 초반에 실행해 34/0 을 측정했으므로 **회귀 0** 을 실증한다(jsdom@24 를 `/tmp` 에 핀 설치 — 스크립트가 `require("/tmp/node_modules/jsdom")` 를 하드코딩하므로 미설치 세션에서는 실행 불가).
- 구조 단언: `releases` 51→**52** · `generated`=="2026-08-24"==`releases[0].date` · 신규 블록 items **8** · 직전 블록(`2026-08-19`) items 1 불변 · `type`/`area` 값이 기존 enum 집합 내 · 스키마 외 키 0 · date 중복 0 · reverse-chron 유지.
- 누출 스캔: feature-id / TASK-·REV-·CHG- id / §번호 / 파일명 / 함수·테이블·컬럼명 / 내부 코드값 = **0건**.
- reconcile-first 실측(편집 전): 서빙 `https://localhost/static/release-notes-data.js` 200 · `?v=` 정규화 후 브랜치 blob 과 `cmp` 일치(260,695B) → 파리티 갭 0(3창 연속 갭은 08-24 19:00 종결).
- **Pass/Fail: PASS**.
## TASK-20260826T010305-doc-sync-rn-0826 — 릴리즈노트 신규 2026-08-25 블록 prepend 검증
- **Environment: Windows-browser (PB-0008)** — 미수행(사유: 본 changeset 은 릴리즈노트 **콘텐츠 데이터 + 그 companion 문서** 전용이고 렌더 로직(`release-notes.js`)·마크업(`index.html`/`admin.html`)·CSS 델타가 **0** 이다. 무인 cron run 이라 인터랙티브 브리지가 가동되지 않고, 배포는 wrapper 소유(v3)라 이 커밋 시점에 라이브 화면이 존재하지 않는다. 대체로 아래 DOM 테스트 + 구조 단언을 수행했다).
- `node --check static/release-notes-data.js` → PASS.
- `node tests/verify_release_notes.mjs` → **ALL PASS 34 / 0**. 편집 **전** 동일 스크립트를 cycle 초반에 실행해 34/0 을 측정했으므로 **회귀 0** 을 실증한다(jsdom@24 를 `/tmp` 에 핀 설치 — 스크립트가 `require("/tmp/node_modules/jsdom")` 를 하드코딩하므로 미설치 세션에서는 실행 불가).
- 구조 단언: `releases` 51→**52** · `generated`=="2026-08-25"==`releases[0].date` · 신규 블록 items **3**(improved 1 / fixed 2 · area work 3) · 직전 블록(`2026-08-24`) items 8 불변 · `type`/`area` 값이 기존 enum 집합 내 · 스키마 외 키 0 · date 중복 0 · reverse-chron 유지.
- 누출 스캔: feature-id / TASK-·REV-·CHG-·ADR- id / §번호 / 파일명 / 함수·테이블·컬럼명 / 내부상수 = **0건**(7패턴). ASCII 런은 스키마 키 + 사용자 선택 모델명 3종뿐(기존 블록 선례 있음).
- reconcile-first 실측(편집 전): 서빙 `https://localhost/static/release-notes-data.js` 200 · 브랜치 blob 과 **md5 동일**(`b6ab4c47…` · 272,061B) · `index.html` 도 `?v=` 정규화 후 byte 동일 → 파리티 갭 0(08-24 19:00 종결분이 2창 연속 유지).
- **Pass/Fail: PASS**.

## TASK-20260828T010305-doc-sync-rn-0828 — 릴리즈노트 신규 2026-08-26·08-27·08-28 블록 prepend 검증
- **Environment: Windows-browser (PB-0008)** — 미수행(사유: 본 changeset 은 릴리즈노트 **콘텐츠 데이터 + 그 companion 문서** 전용이고 렌더 로직(`release-notes.js`)·마크업(`index.html`/`admin.html`)·CSS 델타가 **0** 이다. 무인 cron run 이라 인터랙티브 Windows 브라우저 브리지가 가동되지 않고, 배포는 wrapper 소유(v3)라 이 커밋 시점에 라이브 화면에 새 내용이 존재하지 않는다. 대체로 아래 DOM 테스트 + 구조 단언을 수행했다).
- `node --check static/release-notes-data.js` → PASS.
- `node tests/verify_release_notes.mjs` → **ALL PASS 34 / 0**. 편집 **전** 동일 스크립트를 cycle 초반에 실행해 34/0 을 측정했으므로 **회귀 0** 을 실증한다(jsdom@24 를 `/tmp` 에 핀 설치 — 스크립트가 `require("/tmp/node_modules/jsdom")` 를 하드코딩하므로 미설치 세션에서는 실행 불가).
- 구조 단언: `releases` 53→**56** · `generated`=="2026-08-28"==`releases[0].date` · 신규 블록 items **4 / 13 / 2** · 직전 블록(`2026-08-25`) items 3 불변 · `type`/`area` 값이 기존 enum 집합 내 · 스키마 외 키 0 · date 중복 0.
- 누출 스캔(7패턴 — feature-id / TASK·REV·CHG·ADR id / §번호 / 파일확장자 / 내부용어 / 경로 / 커밋해시): **0건**. 유일 고유명 히트는 사용자가 화면에서 그대로 본 오류 문구 인용 1건으로 의도적 보존.
- reconcile-first 실측: 편집 전 서빙 `https://localhost/static/release-notes-data.js` 200 · 브랜치 blob 과 **md5 동일**(`79d362ce…` · 276,572B) → 파리티 갭 0. 커밋 직전 재측정도 동일.
- **Pass/Fail: PASS**.

## 20260828T2200-bridge-attachment-write 브리지 첨부 쓰기 복원 (Major §12.3, 2026-08-28)

### Run 2026-08-28 — bridge-attachment-write PRE-COMMIT (Environment: 컨테이너 pytest + ruff) — PASS

- `make test` 전건 통과(rebase `bf5b3ae2` 후 클린 실행) · ruff All checks passed
- 신규 회귀 16건(`unit/feature-0043-external-llm-bridge/tests/test_bridge_attachment_write.py`)
- 기존 worker 첨부 회귀 21건은 **강화** — fake 가 정본(`shared/attachment_write.py`)에 stub
  원시연산을 물려 실제 조립(순서·cap 합산·미전달 계수·strip 정책)을 검증한다

### Run 2026-08-28 — bridge-attachment-write PRE-MERGE LIVE (Environment: **Windows-browser** PB-0008) — PASS

브랜치 코드를 `docker cp` 로 live web a/b 에 주입 + 재기동, 실 `claude` CLI 러너 연결 후
실제 대화(`20260828031049-b13a4b02`)에서 확인.

- `attachment-new` → 첨부 **1248 daily_count.sql** 생성(assistant)
- `attachment-edit`(user 계보) → **1249** 로 분기(설계대로 새 root v1)
- `attachment-edit`(assistant 계보) → **1249 v1 → 1251 v2** 버전 연장
- 실 Windows Chrome(151.0.7922.170) 화면: 블록 헤더 `{"source_attachment_id"` **미노출**,
  첨부 칩 표시, 📎 전달 마커 4종, 거짓 실패 고지 없음
- 판독 주의: 렌더된 코드블록은 innerText 에 ``` 를 남기지 않는다 → fence 문자로 판정하면
  거짓 음성. 헤더 JSON + `pre/code` 언어 클래스로 판정했다.

증적: `unit/feature-0003-agent-web-ui/docs/test-runs.d/TASK-20260828T220000-bridge-attachment-write.md`

## 20260828T2300-attach-lineage-ui 첨부 계보 UI (Minor §12.3, 2026-08-28)

### Run 2026-08-28 — attach-lineage-ui PRE-COMMIT (Environment: 컨테이너 pytest + ruff) — PASS

- 신규 회귀 17건(`tests/test_attach_lineage_ui.py`) — 비교 게이트 2겹 · 계보 배지 조건·배선 ·
  버전 박스 계보 안내 · 토글 라벨 단일 출처 · 서버 root 해소/IN 1회 · 모달 제목 축 추종 ·
  **원문 모달 `axis` 스코프 가드**
- 뮤테이션 역검증 11종 전건 KILL(하네스 베이스라인 exit code 로 실제 구동 확인 후)

### Run 2026-08-28 — attach-lineage-ui PRE-MERGE LIVE (Environment: **Windows-browser** PB-0008) — PASS

브랜치 코드를 live web a/b 에 주입 + asset stamp 재주입 후 실 Chrome 판독.

- 목록: `계보 1/3`·`2/3`·`3/3` 배지 + 툴팁(출처·파일 수). 계보 1개인 첨부는 미표시
- 단건 계보: `⇄ 계보 비교` → 모달 제목 **「계보 비교」**, 축 `계보 간(시간순)`,
  선택지 3계보, 실 diff `LIMIT 50;` → `LIMIT 500;`
- payload: `1256`(v4 head) `lineage_from=1246` — root 해소 확인

증적: `docs/test-runs.d/TASK-20260828T230000-attach-lineage-ui.md`

## TASK-20260831T010305-doc-sync-rn-0831 — 릴리즈노트 2026-08-28 블록 items append 검증
- **Environment: Windows-browser (PB-0008)** — 미수행(사유: 본 changeset 은 릴리즈노트 **콘텐츠 데이터 + 그 companion 문서** 전용이고 렌더 로직(`release-notes.js`)·마크업(`index.html`/`admin.html`)·CSS 델타가 **0** 이다. 무인 cron run 이라 인터랙티브 Windows 브라우저 브리지가 가동되지 않고, 배포는 wrapper 소유(v3)라 이 커밋 시점에 라이브 화면에 새 내용이 존재하지 않는다. 대체로 아래 DOM 테스트 + 구조 단언을 수행했다).
- `node --check static/release-notes-data.js` → PASS.
- `node tests/verify_release_notes.mjs` → **ALL PASS 34 / 0**. 편집 **전** 동일 스크립트를 cycle 초반에 실행해 34/0 을 측정했으므로 **회귀 0** 을 실증한다(jsdom@24 를 `/tmp` 에 핀 설치 — 스크립트가 `/tmp/node_modules/jsdom` 를 하드코딩하므로 미설치 세션에서는 실행 불가).
- 구조 단언: `releases` **56 불변**(신규 date 블록 없음) · `generated`=="2026-08-28"==`releases[0].date` · `releases[0].items` 4→**15** · `releases[1]`(2026-08-27) items 13 불변 · `type` ∈ {new,improved,fixed} · `area` ∈ {work,admin,common} · 스키마 외 키 0 · date 중복 0.
- 누출 스캔(7패턴 — feature-id / TASK·REV·CHG·ADR id / §번호 / 파일확장자 / 내부용어 / 경로 / 커밋해시): 신규 11항목 구간 **전건 0건**.
- reconcile-first 실측: 편집 전 서빙 `https://localhost/static/release-notes-data.js` 200 · 브랜치 blob 과 **md5 동일**(`d40ed98d…` · 308,144B) → 파리티 갭 0. 독립 표본 4개(`index.html`·`admin.html`·app JS·설치 스크립트)도 캐시토큰 정규화 후 md5 일치.
- **Pass/Fail: PASS**.

### Run — TASK-20260831T100000-console-llm-parity (관리 콘솔 LLM 정합, POST-DEPLOY)

- **Environment: Windows-browser (PB-0008)** — **수행**. 배포본 `5e806c6a` 실 Chrome
  (`Chrome/151.0.7922.170`, `https://localhost/admin`)에서 4축 전부 PASS:
  조작면 게이트(`metadataSuggestBtn` disabled + 사유 툴팁) · 미적용 배지 3 + 사유 dropdown 7
  + 최하단 집계 4건 · 사용량/추론 배너 · `AI 운영 현황` 브리지 축 + KPI 2종.
  라이브 상태가 `runner_idle` 분기를 타 **`no_connection` 과 실제로 갈렸다**(설계 의도 실증).
  상세·미검증 항목: `docs/test-runs.d/TASK-20260831T100000-console-llm-parity-postdeploy.md`
- 무중단 실측 `no upstreams available` = 0 · `/readyz` git_commit = `5e806c6a`.

### Run — TASK-20260831T160000-console-job-wiring (콘솔 작업 위임 배선)

- **Environment: Windows-browser (PB-0008)** — **이 커밋 시점 미수행**. 사유: 본 changeset 의
  화면 변화(`llm-state.js` 폴링 헬퍼 · `metadata.js` 위임 결과 처리)는 **연결된 러너가
  `console_jobs` 를 신고한 상태에서만** 관측 가능한데, 그 러너는 사용자 머신에서 이 배포본을
  받아 실행해야 존재한다. 그리고 라이브는 아직 이전 SHA(`5e806c6a`)를 서빙하므로 지금
  브라우저로 보는 것은 **이 변경이 아니다**. JS 는 `docker cp` QA 가 불가하다(asset stamp
  미주입 → 모듈 캐시로 구버전 실행). 그래서 배포 후 POST-DEPLOY 로 수행하고 증적을 별도
  fragment 로 남긴다 — 직전 cycle(TASK-20260831T100000)과 같은 절차.
- 이 커밋에서 대체 수행한 것: 위임 계약 회귀 15건(형식 정합·이음매 순서·러너 프레이밍·
  프롬프트 평탄화 순서) + 전량 green(6253+) + route 골든 대조(추가 1·제거 0).

### Run — TASK-20260831T160000-console-job-wiring (POST-DEPLOY 보완)

- **Environment: Windows-browser (PB-0008)** — **수행**(배포본 `d550db16`). 신규 ESM 모듈 로드 ·
  조작면 게이트 무회귀 · 폴링 엔드포인트 404 계약 · 종류별 위임 판정(`delegable_jobs`) 확인.
  위임 **왕복 e2e** 는 `console_jobs` 신고 러너가 사용자 머신에 있어야 해 미관측 — 사용자
  확인에 위임. 증적: `docs/test-runs.d/TASK-20260831T160000-console-job-wiring-postdeploy.md`

### Run — 20260831T1445-conv-last-activity-updatedat ("최근 갱신" 이 첫 턴 시각에 고정되던 결함)

- **단위/구조**: 신규 2종 **20 PASS** — `feature-0002/tests/test_conv_activity_touch.py`(8: touch
  발동 · 브랜치 경로 · UPDATE 여부 · fail-soft · 회수 store 비-touch · SQL 상수 컬럼 잠금) +
  `feature-0003/tests/test_conv_last_activity_effective.py`(12: 두 축 max · tz 게이트 · 직렬화 ·
  목록 2경로 구조 단언).
- **뮤테이션 역검증 3종 KILL**: `save_memory_message` 의 touch 호출 제거 → 미분기·브랜치 두
  테스트 FAIL / 표시 축을 `_iso_or_empty(last_active)` 로 되돌림 → 구조 단언 FAIL.
- **전량 회귀**: `feature-0002 + feature-0003 + feature-0023 + feature-0043` 전 수집 대상 실행,
  **실패 0**(rc=0). 초기 실행에서 `test_message_branching.py` 3건이 SQL 실행 목록 **전체 동등**
  단언으로 파손 → 그 절의 계약(어느 INSERT 를 타는가)을 INSERT 로 좁혀 유지하고 touch 동반은
  전용 테스트를 새로 추가(단언만 느슨하게 두면 다음 변경이 touch 를 조용히 잃는다).
- **라이브 실측(수정 전, 재현·범위 확정)**: 대화 `20260828073505-be34624d` — `updated_at`
  08-28 16:38:07 고정 vs 마지막 메시지 08-31 10:54:39(**2일 18시간 16분**), KV `last_status*`
  0건(브리지 경로). 전수 355 대화 중 **19건** 동일(모두 2턴 이상).
- **Environment: Windows-browser (PB-0008)** — **이 커밋 시점 미수행**. 사유: 본 changeset 은
  **프론트 자산 변경 0**(`static/**`·`templates/**` diff 없음)이라 `visual_verification_scope`
  check #13 의 hard gate 대상이 아니다. 또한 화면에 보이는 값은 **배포 + 백필 이후**에야 바뀌므로
  지금 브라우저로 보는 것은 이 변경이 아니다. 배포·백필 후 POST-DEPLOY 로 부제 실측을 수행한다.

### Run — 20260831T1445-conv-last-activity-updatedat (POST-DEPLOY: 배포·백필·표면 실측)

- **배포**: `make deploy-web`(scope=all) → `b35fa376`. web-a·web-b 동일 SHA · 워커 3종 동일 SHA ·
  soak 통과 · 대화 스모크 PASS. **무중단 실측**: 배포 창 caddy `no upstreams available`
  **0건** · surge 잔존 **0**.
- **백필**: 대상 19건(마지막 메시지 > `updated_at` + 1분)을 마지막 메시지 시각으로 정정.
  잔여 drift **0**, 오늘로 밀린 잔재 **0**, 백업 대비 목표값 **19/19 일치**
  (`artifacts/conv-updatedat-backfill-20260831/{before.tsv,after-all.tsv}`).
  - **1차 백필은 틀렸고 즉시 정정했다**: `core_conversations` 의 `trg_core_conv_updated_at`
    (BEFORE UPDATE → `set_updated_at()`, 무조건 `now()`)이 값을 덮어 19행이 전부 실행 시각
    (15:12:48)으로 밀렸다. `SET LOCAL session_replication_role='replica'` 로 트리거를 우회해
    의도한 값으로 다시 썼다. 정본 절차는 feature-0002 `CHG-20260831T144500-conv-activity-touch`
    에 기록.
- **표면 실측(라이브 배포본 안에서)**: 지목 대화 `20260828073505-be34624d` —
  DB `updated_at` = `2026-08-31 10:54:39+09` → `_effective_activity_at`(KV 축 없음) →
  프런트 수신 값 **`2026-08-31T01:54:39.405521+00:00`**(= KST 10:54:39 = 마지막 메시지 시각).
  `PgRuntimeBackend.touch_conversation` 배포본 존재 확인.
- **Environment: Windows-browser (PB-0008)** — 미수행. 프론트 자산 변경 0(check #13 skip 판정)
  이고, 부제 렌더는 서버가 싣는 값 + 기존 `formatDateTime` 경로라 **바뀐 것은 값 하나**다. 그
  값을 배포본 안에서 직접 실측했다(위). 지목 대화는 사용자 소유라 admin 계정 브라우저 세션으로
  같은 화면에 도달할 수 없다 — 최종 육안 확인은 사용자 화면에 위임한다.

### Run — TASK-20260831T190000-job-result-unwrap (각인 래퍼 노출 수정)

- **Environment: Windows-browser (PB-0008)** — 배포 후 수행 예정(사유: 위임 결과 렌더는
  `console_jobs` 신고 러너가 붙은 상태에서만 관측 가능하고, 라이브는 아직 이전 SHA 서빙).
  이 커밋에서는 **뮤턴트 검증**으로 대체 — 원래 결함을 재주입하자 회귀 2건 FAIL, 되돌리자
  7건 PASS. 사용자가 제보한 정확한 문자열(`⟦UNTRUSTED-DATA⟧`·`[UNTRUSTED]`)이 화면 본문에
  없음을 불변식으로 잠갔다.

### Run — TASK-20260831T190000-job-result-unwrap (POST-DEPLOY 보완)

- **Environment: Windows-browser (PB-0008) + 배포본 컨테이너 직접 실행** — **수행**
  (배포본 `cac907c4`). 사용자가 제보한 **그 문자열**이 본문 230자만 남고 마커·고지가 전부
  제거됨을 실측. 폴링 스코프(타 계정 task → 404)도 라이브 확인. 증적:
  `docs/test-runs.d/TASK-20260831T190000-job-result-unwrap-postdeploy.md`

### Run — TASK-20260831T193000-attach-lineage-visibility (첨부 계보 비교 가시성 재설계)

- **Environment: Windows-browser (PB-0008)** — **수행**. §13.2.9 격리 컨테이너
  `web-verify-lineage`(라이브 web 이미지 + 브랜치 static 트리 **stamp 재주입** bind-mount,
  `https://localhost:18098`)에서 실 Windows Chrome 151 로 판독. 공유 트리·라이브 web-a/b 무수정.
- 구조: 그룹 카드 2 · `.in-lineage-group` **4/4**(평면 잔존 0) · `.is-branch` 2 · 그룹 비교 버튼 2
- 픽셀: 확대 캡처로 레일·elbow·분기 들여쓰기 판독 / 240px 최소 폭에서 그룹 머리 **wrap**(무손실)
- computed 색축: 파일명 `rgb(128,125,114)` · 사용자 칩 `rgb(128,125,114)` · AI 칩 `rgb(37,99,235)`
  — 교정 전 `var(--muted)`(미정의 토큰) 경로에서 사용자 칩이 본문색 `rgb(38,37,30)` 이던 결함 포착
- 인터랙션 **2 surface 개별 실행**: 그룹 머리 `⇄ 계보 비교` / 버전 박스 `⇄ 계보 비교` — 둘 다
  축 `time` · aria `첨부 계보 비교` · 기준 `사용자 업로드 v1 · 현재` → 비교 `AI 수정본 v2` · `+182 / -21`
- 증적: `docs/test-runs.d/TASK-20260831T193000-attach-lineage-visibility.md`
- 회귀: `unit/feature-0003-agent-web-ui/tests` + `unit/feature-0002-agent-core/tests` 전건 PASS
  (신규 `test_attach_lineage_group_ui.py` **32건** 포함 — 적대 리뷰 2라운드 조치분 반영) · `node --check` ESM PASS

## TASK-20260901T010306-doc-sync-rn-0901 — 릴리즈노트 2026-08-31 블록 신설 검증
- **Environment: Windows-browser (PB-0008)** — 미수행(사유: 본 changeset 은 릴리즈노트 **콘텐츠 데이터 + 그 companion 문서** 전용이고 렌더 로직(`release-notes.js`)·마크업(`index.html`/`admin.html`)·CSS 델타가 **0** 이다. 무인 cron run 이라 인터랙티브 Windows 브라우저 브리지가 가동되지 않고, 배포는 wrapper 소유(v3)라 이 커밋 시점에 라이브 화면에 새 내용이 존재하지 않는다. 대체로 아래 DOM 테스트 + 구조 단언을 수행했다).
- `node --check static/release-notes-data.js` → PASS.
- `node tests/verify_release_notes.mjs` → **ALL PASS 34 / 0**. 편집 **전** 동일 스크립트를 cycle 초반에 실행해 34/0 을 측정했으므로 **회귀 0** 을 실증한다(jsdom@24 를 `/tmp` 에 핀 설치 — 스크립트가 `/tmp/node_modules/jsdom` 를 하드코딩하므로 미설치 세션에서는 실행 불가).
- 구조 단언: `releases` 56→**57**(신규 date 블록 1개) · `generated`=="2026-08-31"==`releases[0].date` · `releases[0].items` **14** + `summary` 보유 · `releases[1]`(2026-08-28) items **15 불변** · **`date: "2026-08-28"` 이하 전 구간 바이트 동일**(순증 9,045B 전량이 신규 블록) · `type` ∈ {new,improved,fixed} · `area` ∈ {work,admin,common} · 스키마 외 키 0 · date 중복 0.
- 누출 스캔(18패턴 — feature-id / 브리지·러너·워커·핸들러 / Schannel·BOM·WSL·winget / `bridge_*` / 파일확장자 / payload·JSON / 폴링 / 배포본 / `Kind=` / `wired`): 신규 14항목 + summary 구간 **전건 0건**.
- reconcile-first 실측(run 시작 시점): 서빙 `https://mysql-ai.company.local/static/release-notes-data.js` 200 · 329,914B · `origin/main` blob 과 **바이트 동일** → 파리티 갭 0. `repo/` main checkout clean · HEAD == `origin/main` == `f62aa92f`.
- **Pass/Fail: PASS**.

### Run — TASK-20260901T101500-attach-lineage-postdeploy (POST-DEPLOY)

- **Environment: Windows-browser (PB-0008)** — **수행**. 라이브 배포본 `2f09d755`
  (`https://localhost/`, 격리 컨테이너 아님). 모듈 스탬프 `2e71f760557a` 로 신 코드 로드 확인.
- 그룹 카드 2 · 카드 안 행 4 · 분기 2 · `role=group` · 행 접근성 이름에 계보 정체성 · 대비
  테두리 `rgb(168,165,152)`/레일 `rgb(140,138,124)` · 그룹 비교 클릭 1회 → 축 `time` ·
  `사용자 업로드 v1 · 현재` → `AI 수정본 v2` · `+182 / -21`.
- 배포 상태: 전 서비스 이미지 **동일 SHA** · surge 잔존 0 · `no upstreams available` **0건**.
- 증적: `docs/test-runs.d/TASK-20260901T101500-attach-lineage-postdeploy.md`

### Run — TASK-20260901T163000-attach-lineage-uploader (공유 대화 업로더 식별 + 되풀이 제거)

- **Environment: Windows-browser (PB-0008)** — **수행**. §13.2.9 격리 컨테이너(static stamp
  `c64defd96a04` + 변경 라우터 2종 bind-mount), `https://localhost:18101`.
- **경계 3경로 실측**: ① 공유 대화(`20260813083932`, 계정 10·50) → 행 라벨
  `jmkimmasangsoft.com`/`admin` 로 분리(종전 8행 전부 「사용자 계보」) · 그룹 카드 4 ·
  행 아이콘 **0** · 머리 아이콘 4 · 카드당 파일명 3회→**1회** ② 1:1(`20260831093200`) →
  `사용자 업로드`/`AI 수정본`, **이름 없음** ③ 단독 계보(`20260828043852`) → 카드 없음 ·
  행 아이콘 **2/2 유지** · 라벨 = 파일명.
- 240px 최소 폭에서 아이콘+파일명 한 줄 유지(첫 캡처가 아이콘 분리 결함을 포착 → 수정).
- assistant 계약 확인: `_build_attachment_context_section` 실 렌더가
  `uploaded by <이름>` + per-lineage/overall latest 를 싣는 것을 caller 10·50 양쪽에서 확인.
- 증적: `docs/test-runs.d/TASK-20260901T163000-attach-lineage-uploader.md`
- 회귀: **5167 passed / 5 skipped**(신규 11건). ⚠ `test_query_embed_visibility.py` 2건은
  **main 기준선에서도 동일 실패**(스위트 순서 의존) — 본 변경 무관.
- Run 2(적대 리뷰 조치 후): codex P1 **0** · P2 4 전건 조치 후 재실측 — 노출 범위(versions 행
  `account_id` 부재 / lineages 유지) · AT 정합(업로더명이 aria 에도) · stale 가드의 **정상 경로**
  통과 · 라벨 충돌 시 서수(`사용자 업로드 · 계보 1/3`). 5173 passed.
| TEST-20260901T163000-runner-log-delivery | `static/agent/bridge_agent.py` (Windows-browser) | 러너 로그 구조화 cycle 의 시각검증. **화면 렌더 변경 0** (이 파일은 렌더 자산이 아니라 사용자가 내려받아 실행하는 스크립트) — 대신 실 Windows 브라우저에서 `/static/agent/bridge_agent.py` **배달 지문**을 실측했다. PRE-DEPLOY `served_build=0a4ba732366c` / 214,898 bytes. Environment: Windows-browser. 증적 `docs/test-runs.d/TASK-20260901T163000-runner-log-structure.md` | feature-0043 AC-20260901T163000-runner-log-1~6 |

### Run — TASK-20260901T170000-lineage-row-compaction (되풀이 제거 + 한 줄 간소화)

- **Environment: Windows-browser (PB-0008)** — **수행**. 격리 컨테이너(stamp `a3db80724568`).
- 되풀이: 버전 행 파일명 요소 **0** · 계보 안내문 **0** · raw `uploaded` **0**
  (카드당 파일명 노출 6회 → 1회).
- 한 줄(행 높이 20px=한 줄): **버전 행 전 폭 20px** · 사람 업로드 계보 행 280px 에서 **20px** ·
  AI 수정본 계보 행 39px(두 줄) — 필요 268 / 가용 206, **62px 부족**을 수치로 확정.
- 캡처가 결함 1건 포착: 글리프만 남은 파선 pill 이 «빈 동그라미» → 테두리 제거.
- 증적: `docs/test-runs.d/TASK-20260901T170000-lineage-row-compaction.md`

| TEST-20260901T170000-runner-log-postdeploy | `static/agent/bridge_agent.py` (Windows-browser) | POST-DEPLOY — 실 Windows 브라우저 fetch 로 배달 지문 `a17b8f5ea7f6` (main 일치·PRE 에서 갱신) + 서빙 본문에 구조화 로그 존재. 배포본을 실제 구동해 원장 4사건·토큰 마스킹 0건 확인. **화면 렌더 변경 0**. 증적 `docs/test-runs.d/TASK-20260901T163000-runner-log-structure.md` | feature-0043 AC-20260901T163000-runner-log-1~6 |

## TASK-20260902T010304-doc-sync-rn-0902 — 릴리즈노트 2026-09-01 블록 신설 검증
- **Environment: Windows-browser (PB-0008)** — 미수행(사유: 본 changeset 은 릴리즈노트 **콘텐츠 데이터 + 그 companion 문서** 전용이고 렌더 로직(`release-notes.js`)·마크업(`index.html`/`admin.html`)·CSS 델타가 **0** 이다. 무인 cron run 이라 인터랙티브 Windows 브라우저 브리지가 가동되지 않고, 배포는 wrapper 소유(v3)라 이 커밋 시점에 라이브 화면에 새 내용이 존재하지 않는다. 대체로 아래 DOM 테스트 + 구조 단언을 수행했다).
- `node --check static/release-notes-data.js` → PASS.
- `node tests/verify_release_notes.mjs` → **ALL PASS 34 / 0**. 편집 **전** 동일 스크립트를 cycle 초반에 실행해 34/0 을 측정했으므로 **회귀 0** 을 실증한다(jsdom 은 `/tmp/node_modules` 에 선재 — 스크립트가 그 경로를 하드코딩하므로 미설치 세션에서는 실행 불가).
- 구조 단언: `releases` 57→**58**(신규 date 블록 1개) · `generated`=="2026-09-01"==`releases[0].date` · `releases[0].items` **17** + `summary` 보유 · `releases[1]`(2026-08-31) 불변 · 총 항목 424→**441** · **`date: "2026-08-31"` 이하 전 구간 바이트 동일**(순증 25,734B 전량이 신규 블록) · `window.RELEASE_NOTES` 앞 head 구간도 바이트 동일 · `type` ∈ {new,improved,fixed} · `area` ∈ {work,admin,common} · 스키마 외 키 0 · date 중복 0.
- 누출 스캔(19패턴 — feature-id / 러너·워커·핸들러 / `bridge_*` / payload·JSON / 폴링 / `Kind=` / `wired` / 파일확장자 `.py`·`.js` / MCP · `get_task_context` / WSL / endpoint / API): 신규 17항목 + summary 구간 **실질 0건**. 유일 히트인 「브리지 작업」 2건은 `admin.html` 에 5회 · `admin/tasks.js` 3회 · `admin/usage.js` 2회 노출되는 **실제 화면 탭 라벨**이므로 내부용어 노출이 아니다(grep 실측).
- reconcile-first 실측(커밋 직전 재측정 01:57:17): 서빙 `https://mysql-ai.company.local/static/release-notes-data.js` 200 · md5 `4c150bcc…` = `origin/main` blob 과 동일 → 파리티 갭 0. `repo/` main checkout clean · HEAD == `origin/main` == `a2933614` · 배포 실패 마커 0. 서빙 캐시토큰 `?v=b85ff1d4986d`(content-hash 자동 주입 — 수기 bump 하지 않았다).
- **Pass/Fail: PASS**.

## TASK-20260903T010309-doc-sync-rn-0903 — 릴리즈노트 2026-09-02 블록 신설 검증
- **Environment: Windows-browser (PB-0008)** — 미수행(사유: 본 changeset 은 릴리즈노트 **콘텐츠 데이터 + 그 companion 문서** 전용이고 렌더 로직(`release-notes.js`)·마크업(`index.html`/`admin.html`)·CSS 델타가 **0** 이다. 무인 cron run 이라 인터랙티브 Windows 브라우저 브리지가 가동되지 않고, 배포는 wrapper 소유(v3)라 이 커밋 시점에 라이브 화면에 새 내용이 존재하지 않는다. 대체로 아래 DOM 테스트 + 구조 단언을 수행했다).
- `node --check static/release-notes-data.js` → PASS.
- `node tests/verify_release_notes.mjs` → **ALL PASS 34 / 0**. 편집 **전** 동일 스크립트를 cycle 초반에 실행해 34/0 을 측정했으므로 **회귀 0** 을 실증한다(jsdom 은 `/tmp/node_modules` 에 선재).
- 구조 단언: `releases` 58→**59**(신규 date 블록 1개) · `generated`=="2026-09-02"==`releases[0].date` · `releases[0].items` **15** + `summary` 보유 · `releases[1]`(2026-09-01) 불변 · 총 항목 441→**456** · **`date: "2026-09-01"` 이하 전 구간 바이트 동일** · 헤더 주석 구간 바이트 동일 · `type` ∈ {new,improved,fixed} · `area` ∈ {work,admin,common} · 스키마 외 키 0 · date 중복 0.
- 누출 스캔(47패턴 — feature-id / TASK-·CHG-·REV-·AC- / `.py`·`.js`·`.ps1`·`.sh` / `/api/` / 테이블명 / 러너·브리지·하트비트·provenance·lease / 모델명 / `netsh`·`portproxy`·SQL·PowerShell 등): 신규 15항목 + summary 구간 **0건**. 인용한 UI 문구(「내 AI 실행」·「업데이트 필요」·「연결 안 됨」·「AI 작업」·「AI 능동 분석」·「단계 보기」·「추론 강도」)는 `static/` grep 으로 **실제 렌더 경로에서 실측** 확인. 초안의 '연결 필요'·'제공되지 않습니다' 2건은 소스 grep 0 으로 반증돼 실제 라벨로 교체·삭제했다.
- 적대검증 교정 1건 반영: item#8 의 「배포된 프로그램을 내려받아 다시 재니 10.9초」가 배포 후 재측정 **전면 성공**으로 읽히나 정본은 두 런타임 중 **한쪽만** 측정됐다고 적는다(다른 쪽은 그 머신 사용량 한도 소진, rc=1) — 그 사실을 detail 에 보강했다.
- reconcile-first 실측(커밋 직전 재측정 2026-09-03T01:55:08+09:00): 서빙 `release-notes-data.js` md5 `d6876ca9…` = `origin/main` blob 동일 → 파리티 갭 0. `repo/` main clean · HEAD == `origin/main` == `5d984b75` · 배포 실패 마커 0. 캐시버스터 수기 bump **없음** — 소스는 `?v=dev` 고정이고 빌드가 content-hash 를 주입하며, `bin/deploy-web.sh` ABORT 가드가 baked 이미지의 `?v=dev` 잔존으로 주입 누락을 판정하므로 수기 실값은 그 안전장치를 무력화한다.
- **Pass/Fail: PASS**.

## TASK-20260904T010301-doc-sync-rn-0904 릴리즈노트 블록 신설 검증

- `node --check src/static/release-notes-data.js` → PASS (JS 문법)
- `NODE_PATH=/tmp/node_modules node tests/verify_release_notes.mjs` → **ALL PASS 34, failed 0** (baseline 동일). 첫 그룹 일자 「2026년 9월 3일」 단정 통과.
- **Environment: Windows-browser (PB-0008)** — 미수행. 이 변경은 렌더 로직·DOM·CSS 무접촉의 **정적 데이터 블록 1개 추가**이고, 동일 렌더 경로를 jsdom 하네스 34건이 전건 단정하므로 실 브라우저 시각검증의 추가 판별력이 없다(배포 후 라이브 노출은 wrapper 소관).

## TASK-20260907T010301-doc-sync-rn-0907 릴리즈노트 블록 신설 검증

- `node --check src/static/release-notes-data.js` → PASS (JS 문법)
- `NODE_PATH=/tmp/node_modules node tests/verify_release_notes.mjs` → **ALL PASS 34, failed 0** (baseline 동일). 하네스 실행을 위해 `jsdom@24` 를 `/tmp` 에 핀 설치했다(세션마다 부재할 수 있음).
- 평이화 기계 스캔: 신규 블록에 대해 내부 명칭 27패턴(feature-id·파일 확장자·기술 스택명·식별자) → **0 히트**. 「」 23/23 균형.
- **Environment: Windows-browser (PB-0008)** — 미수행. 이 변경은 렌더 로직·DOM·CSS 무접촉의 **정적 데이터 블록 1개 추가**이고, 동일 렌더 경로를 jsdom 하네스 34건이 전건 단정하므로 실 브라우저 시각검증의 추가 판별력이 없다(배포 후 라이브 노출은 wrapper 소관).
- reconcile-first 실측(커밋 직전 재측정 2026-09-07T01:03:01+09:00): 서빙 `release-notes-data.js` md5 `f26bed6e…` = `origin/main` blob 동일 → **파리티 갭 0**. `repo/` main clean · `origin/main` == `9e26ffa5` · 배포 실패 마커 0. 캐시버스터 수기 bump **없음** — 소스는 `?v=dev` 고정이고 빌드가 content-hash 를 주입하며(현재 서빙 `?v=d1ebb1da0b64`), `bin/deploy-web.sh` ABORT 가드가 baked 이미지의 `?v=dev` 잔존으로 주입 누락을 판정하므로 수기 실값은 그 안전장치를 무력화한다.
- **Pass/Fail: PASS**.

## RUN-20260907T181510-kb-external-search
- Related TASK: TASK-20260907T181510-kb-external-search
- Result: PASS — 최종 회귀 203건, 실제 격리 PostgreSQL 포함.
- Evidence: [실행 기록](test-runs.d/TASK-20260907T181510-kb-external-search.md).

## TASK-20260908T010301-doc-sync-rn-0908 릴리즈노트 블록 신설 검증

- `node --check src/static/release-notes-data.js` → PASS (JS 문법)
- `NODE_PATH=/tmp/node_modules node tests/verify_release_notes.mjs` → **ALL PASS 34, failed 0** (baseline 동일). 하네스 실행을 위해 `jsdom@24` 를 `/tmp` 에 핀 설치했다(세션마다 부재할 수 있음).
- 평이화 기계 스캔: 신규 블록 79줄에 대해 내부 명칭 패턴(feature-id·파일 확장자·API 경로·chokepoint·fail-closed·SSOT·frontmatter·pytest·WebView2·jsdom·subprocess·sha256·TOFU) → **0 히트**.
- **Environment: Windows-browser (PB-0008)** — 미수행. 이 변경은 렌더 로직·DOM·CSS 무접촉의 **정적 데이터 블록 1개 추가**이고, 동일 렌더 경로를 jsdom 하네스 34건이 전건 단정하므로 실 브라우저 시각검증의 추가 판별력이 없다(배포 후 라이브 노출은 wrapper 소관).
- reconcile-first 실측(2026-09-08T01:03:01+09:00 run 시작 시점): 서빙 `release-notes-data.js` md5 `dafbdc1208e1b775db6d26237e5caec3` = `origin/main` blob 동일 → **파리티 갭 0**. `artifacts/deploy/deploy-web.state` `current=577b5ea1` = HEAD · 배포 실패 마커 0. 라이브 캐시토큰 `?v=0bb8a56f6b8a`(빌드 주입) — 소스 `?v=dev` 고정이라 **수기 bump 하지 않았다**.
- **Pass/Fail: PASS**.


## 2026-09-08 — AI별 자동 연결

[통합 실행 기록](test-runs.d/20260908T123400-connect-discovery.md): Python·DOM·Windows-browser·실제 DQA/WebView2.

## Run: connect-discovery 최종 통합

Environment: DQA-client
Result: PASS
Scenario: 격리 동결 DQA 1.2.0 실행 파일의 연결·위치 선택·재시작 캐시·완료 toast
Evidence: [실행 원장](test-runs.d/20260908T123400-connect-discovery.md), feature-0046 artifacts의 native-results.json.

서비스/API/벤더 응답과 app.js toast 초기화는 대역이다. 네이티브 픽셀 캡처는 빈 면으로 NOT-RUN이며 동일 제품 UI의 Windows Chrome 렌더는 별도 보조 증거다. 실제 벤더 계정 호출·사용자 설치본 교체의 PASS를 뜻하지 않는다.

- TASK-20260908-prompt-layer-delivery: 여섯 계층 전달·오류·재시도·점유 교체 회귀는 [개별 Run](test-runs.d/TASK-20260908-prompt-layer-delivery.md)을 참조한다.

## TASK-20260909T010301-doc-sync-rn-0909 릴리즈노트 블록 신설 검증

- `node --check src/static/release-notes-data.js` → PASS (JS 문법)
- `NODE_PATH=/tmp/node_modules node tests/verify_release_notes.mjs` → **ALL PASS 34, failed 0** (baseline 동일). 하네스 실행을 위해 `jsdom@24` 를 `/tmp` 에 핀 설치했다(세션마다 부재할 수 있음).
- 구조 실측: `date: "` 블록 62 → **63** · `generated` 2026-09-07 → **2026-09-08**.
- 평이화 기계 스캔: 신규 블록에 대해 내부 명칭 패턴(feature-id·`.js`/`.py` 확장자·alembic·WebView2·jsdom·sha256·SSOT·frontmatter·pytest·APIRouter·subprocess·PyInstaller) → **0 히트**.
- **Environment: Windows-browser (PB-0008)** — 미수행. 이 변경은 렌더 로직·DOM·CSS 무접촉의 **정적 데이터 블록 1개 추가**이고 동일 렌더 경로를 jsdom 하네스 34건이 전건 단정하므로 실 브라우저 시각검증의 추가 판별력이 없다. 아울러 이 창에서 UI 검증 정본이 PB-0009(실제 DQA 앱)로 옮겨졌으며(ADR-20260908T024500), 배포 후 라이브 노출 확인은 wrapper 소관이다.
- reconcile-first 실측(2026-09-09T01:03:01+09:00, run 시작 시점): 서빙 `release-notes-data.js` 가 `origin/main` blob 과 **바이트 동일**(sha256 `d8b4285e60b2629c…`, 465,521 bytes) → **파리티 갭 0**. `artifacts/deploy/deploy-web.state` `current=2249addf` = HEAD · 배포 실패 마커 0.
- **Pass/Fail: PASS**.
