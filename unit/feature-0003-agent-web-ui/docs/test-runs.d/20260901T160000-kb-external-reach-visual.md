---
run_at: 2026-09-01T15:00:00+09:00
session: ai/claude/kb-external-reach
scope: PB-0008 시각검증 — 전역 상속 4축 노출 + KB grounding 도달 (20260901T160000-kb-external-reach)
verdict: PASS
---

### Run 1 — 미머지 브랜치 라이브 무접촉 기동 (Environment: docker bind-mount, 라이브 web 무변경)
- 라이브 이미지(`mysql-ai-web:786815f2`)를 그대로 쓰고 **브랜치 소스만 bind-mount** 한 별도
  컨테이너 `web-verify-kbreach`(포트 18099, `repo_dbnet`). 공유 이미지를 **다시 빌드하지 않는다** —
  덮어쓰면 라이브가 내 코드로 바뀌고, 그 상태의 관측은 「배포 전 검증」이 아니다.
  - `.../src/static` → `/app/web/static:ro`
  - `.../src/routers` → `/app/web/routers:ro`
  - `.../feature-0002/src/modules` → `/app/modules:ro`
- `Application startup complete` 확인.

### Run 2 — API 계약 실측 (Environment: Windows-browser, 실제 Chrome + 로그인 세션)
- `bin/win-browser.py session-check` → `authenticated=true, username=bootstrap_admin, role=admin`.
- 5개 엔드포인트를 `scope_key=product.dk_qa` 로 호출한 결과:

  | 축 | count | inherited_count | inherited_error |
  |---|---|---|---|
  | 용어사전 | 23 | 7 | — (0057 cycle 필드) |
  | ENUM | 9 | **9** | false |
  | 테이블 설명 | 153 | 0 | false |
  | 컬럼 설명 | 1,046 | 0 | false |
  | 샘플쿼리 | 0 | 0 | false |

- `scope_key=common` 에서는 5축 전부 `inherited_count=0` — **자기 자신을 상속분으로 다시 세지
  않는다**(중복 표시 방지).
- ⚠ **테이블/컬럼/샘플의 0 은 배선 실패가 아니라 데이터 현실이다**. PG 실측:
  `table_descriptions` 는 `product.dk_qa` 153 · `product.gz_qa_g` 1 뿐이고 `common` **0행**,
  `column_descriptions`·`sample_queries` 도 `common` **0행**. 즉 상속할 것이 아직 없다.
  배선 자체는 뮤턴트 M4/M7 이 지키고, ENUM 축이 라이브에서 9건으로 실증한다.

### Run 3 — 콘솔 시각검증 (Environment: Windows-browser, 실제 Chrome 화면)
- 관리 콘솔 → 메타데이터 → 제품 `DK온라인 - QA` → **ENUM 코드사전**:
  `9건` · `.is-inherited` **9행** · 배지 문구 **「전역 상속 · 여기서 편집 불가」** 렌더 확인.
  종전 이 표면은 상속분이 **0건**이었다(배지 렌더가 `sub === "glossary"` 블록 안에 갇혀 있었다).
- 5개 하위탭 순회 — 렌더 오류/빈 경고 없음:
  용어사전 23건(상속 7) · ENUM 9건(상속 9) · 테이블 153건 · 컬럼 1,046건 · 샘플 0건(정상 안내).
- 증적: `evidence/20260901T160000-kb-external-reach-enum-inherited.png`

### Run 4 — 미수행분 (정직)
- **`inherited_error` 경고 배너의 화면 렌더**: 라이브에서 상속분 조회를 실패시킬 안전한 수단이
  없어 화면 관측을 못 했다. 서버 계약(`inherited_error: true` + 목록 200 유지)과 프론트 분기는
  단위 테스트 3건 + 뮤턴트 M7 로 잠갔다.
- **F1(`get_task_context`) 라이브 왕복**: MCP 토큰이 필요한 브리지 경로라 이 컨테이너에서
  단독 관측이 안 된다. 배포 후 실사용 turn 에서 관측한다.

---

## POST-DEPLOY (배포 `5a4d49fc`, 2026-09-01 18:1x KST)

### Run 5 — 배포 판정
- `git log` 머지 커밋 `5a4d49fc` = PR #1493 · CI SUCCESS · MERGEABLE/CLEAN.
- 컨테이너 실물 태그: `web-a`·`web-b` = `mysql-ai-web:5a4d49fc`,
  `insight-worker`·`ask-worker`·`ops-scheduler`·`ext-tool-mcp-a/b` = `mysql-ai-agent:5a4d49fc`.
  (state 파일이 아니라 `docker compose ps` 실물로 확인 — 부분 완료 0.)
- 대화 경로 스모크 PASS · surge 잔존 0 ·
  **`caddy` `no upstreams available` = 0건**(배포 창 20분) → 엣지 무중단 실측.

### Run 6 — 라이브 시각검증 (Environment: Windows-browser, `https://localhost` = 배포본)
- 관리 콘솔 → 메타데이터 → `DK온라인 - QA` → ENUM 코드사전:
  `9건` · `.is-inherited` **9행** · 배지 **「전역 상속 · 여기서 편집 불가」**.
  bind-mount 사전검증(Run 3)과 **동일 결과** — 배포본에서 재현됨.

### Run 7 — F2 배선 실물 확인 (배포된 이미지 안에서 소스 검사)
- `insight-worker` 컨테이너 `GIT_COMMIT=5a4d49fc`.
- `inspect.getsource(_seed_coverage_targets)` 기준 **주석 제외** 실제 호출 순서:
  `55: _collect_priority_stats(...)` → `57: _na.enqueue_change_analysis(...)`
  → 수집이 게이트보다 **앞**이다.
- `run_insight_cycle` payload 템플릿에 `"stats_collect_attempted": 0` 존재.
- 라이브 knob: `analysis_planner.enabled=True`(seed 3 / cycle 9) · `metadata_stats.enabled=True`.
- ⚠ **자기 검증 함정 1건 기록**: 처음엔 `src.index('_collect_priority_stats') <
  src.index('enqueue_change_analysis')` 로 순서를 봤는데 **False** 가 나왔다. 코드가 아니라
  검사가 틀렸다 — 내가 그 위에 쓴 **주석**이 `enqueue_change_analysis` 를 먼저 언급하기
  때문이다. 문자열 인덱스로 호출 순서를 판정하면 주석·독스트링이 답을 바꾼다.

### Run 8 — F2 실효 관측 (Environment: 배포된 insight-worker 컨테이너 안에서 라이브 구동) — **PASS**
- 배포 시점 `metadata_table_stats` **243행** / `metadata_column_stats` **2,252행**,
  둘 다 `collected_at` 최신값 **2026-08-26 14:09**(= 전환일에 멈춘 그대로 — 이 cycle 이 고치는 결함).
- 배포 후 20분간 자연 유입은 0이었다. 원인은 코드가 아니라 **호출 조건**이다:
  `_seed_coverage_targets` 는 「구조 변경이 **없는**」 사이클의 else 분기에서만 불리고, 그
  앞에 성공한 datasource 스캔이 필요한데 라이브 datasource 다수가 접속 실패 상태였다
  (`insight_datasource_scan_failed` — 이 cycle 과 무관한 기존 환경 문제).
- **그래서 기다리는 대신 같은 경로를 배포본에서 직접 구동했다**:

      planner.select_priority_targets(cur, 'mssql-06656002eda6', 'atum2_db_1', cycle_limit())
        → 9개 대상 반환
      insight._collect_priority_stats('mssql-06656002eda6', targets, report)
        → 반환 9 · report = {'stats_collect_attempted': 9}

- 결과 **PASS**:

  | 지표 | 배포 직후 | 구동 후 |
  |---|---|---|
  | `metadata_table_stats` | 243 | **252** |
  | `metadata_column_stats` | 2,252 | **2,392** |
  | `collected_at` 최신 | 2026-08-26 14:09 | **2026-09-01 18:26** |

  **전환일(2026-08-26) 이후 처음으로 L0 증거가 쌓였다** — 게이트가 여전히 닫혀 있는 상태에서다
  (`[llm-gate] 서버 계정 LLM 호출 차단` 로그 동시 관측). 이것이 F2 의 계약이다.
- ⚠ **남는 사실(정직)**: 자율 사이클에서의 유입은 datasource 접속이 회복되고 「구조 변경 없는」
  사이클이 돌아야 관측된다. 여기서 증명한 것은 **수집 경로가 게이트와 무관하게 작동한다**는
  것이고, 그 경로가 얼마나 자주 불리는지는 별개 축이다(F6 — 산출 없는 스캔 구간 — 이 그것을 다룬다).
