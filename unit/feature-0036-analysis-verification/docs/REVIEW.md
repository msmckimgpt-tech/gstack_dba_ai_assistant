---
doc_type: REVIEW
feature_id: feature-0036-analysis-verification
status: active
edit_policy: append-only
source_of_truth: true
---

# Review Records

## REV-20260731T122000-analysis-verification [CODEX: 반영 완료]

- **Related Change:** feature-0036 분석문 사실성 판정층 (CHG-20260731T121000).
- **Panel:** `codex exec` 적대 리뷰(fresh-context, 스테이징 diff 직접 판독).
- **반증 요청 가설:** ① 판정 실패가 "검증됨"으로 기록되는 경로 ② 잘못된 대조(조인 어긋남·실패한
  증거) ③ 비용 폭주 ④ 워커 파손 ⑤ 판정 행 무한 증식.

### codex 지적과 처리

| # | 지적 | 판정 | 조치 |
|---|---|---|---|
| C1 | **`c` 미정의** — insight 배선이 그 스코프에 없는 변수를 넘겨 판정 pass 가 **아예 동작하지 않는다** | **유효(P1)** | `run_verification_pass(conn=None)` 로 바꿔 자체 agent_kb 연결을 열게 함(`process_pending` 과 동형). insight 는 인자 없이 호출. 회귀 테스트 2건 |
| C2 | **재판정 안 됨** — 저장 PK 는 `(scope, node, analysis_hash)` 인데 대상 조회는 해시를 비교하지 않고 "판정 행이 있으면 제외" 한다. **문서에 적은 '분석 갱신 시 자연히 미검증' 계약과 정반대** | **유효(P1)** | LEFT JOIN 으로 이전 판정 해시를 가져와 파이썬에서 비교. 저장 시 같은 노드의 다른 해시 행을 삭제해 **노드당 1행** 유지(무한 증식·중복 판정도 함께 해소) |
| C3 | **증거 error race** — 대상 조회는 `m.error IS NULL` 을 보지만 evidence 재조회는 보지 않아, 두 쿼리 사이에 수집 실패가 기록되면 **실패한 통계로 판정**한다 | **유효(P1)** | evidence 조회에도 `error IS NULL` |
| C4 | **근거 없이 `supported` 저장** — `{"verdict":"supported"}` 만 와도 기록된다. 프롬프트는 reason 을 필수로 요구하는데 코드가 강제하지 않는다 | **유효(P1)** | `reason` 이 비면 판정을 버린다. 재확인할 수 없는 확인 도장이 이 층의 최악의 실패다 |
| C5 | 동시 워커 중복 판정(claim/lock 없음) | **허용(P2)** | insight tick 은 advisory lock 아래 돌고, 중복이 나도 upsert 라 데이터는 일관된다. 낭비는 pass 상한(20)으로 유계다. claim 도입은 복잡도 대비 이득이 작다 |
| C6 | 예산 모듈 import 실패 시 fail-open + `limit` 인자가 상한 우회 | **유효(P2)** | 둘 다 수정 — 예산 모듈 부재는 **중단**(ADR-0036-02), `limit` 은 `min(configured, limit)` |

### Verdict

SHIP — P1 4건·P2 1건 수정, P2 1건은 근거를 들어 허용으로 기록.

### 스스로 짚는 점

C1 은 **배선이 통째로 죽어 있었다**. 테스트 38건이 모듈 내부를 촘촘히 덮었지만 `insight.py` 의
호출 한 줄이 정의되지 않은 변수를 쓴다는 사실은 잡지 못했다 — 모듈 테스트가 배선을 보증하지
않는다. 이후 `test_insight_calls_pass_without_undefined_variable` 로 그 축을 추가했다.

그리고 `cursor()` 를 try 밖에 두는 실수를 **네 번째** 반복했다(feature-0031·0033·0034·0036).
이번엔 자체 테스트가 먼저 잡았지만, 이 패턴은 이제 체크리스트에 넣을 만하다:
**자원 획득(connect/cursor)은 언제나 try 안**.

### 남긴 리스크

- 판정 대상이 현재 7건 수준이다(증거 커버리지 제약). 플래너(feature-0035)가 커버리지를 채운
  뒤에야 이 층이 실질 값을 한다.
- 판정 결과의 콘솔 표시·grounding 반영은 후속 범위다. 지금은 저장까지.

---

## REV-20260805T160000-analysis-verify-loop [SUBAGENT:backend] — 반려 → 반영 완료

**대상**: 판정 순환 수정 diff (`analysis_verify.pending_targets` · telemetry).
**방법**: 라이브 read-only 쿼리 + EXPLAIN ANALYZE + 테스트 실행.

- **[P1] `DISTINCT ON` tie-break 이 `updated_at DESC`** — 이 저장소가 이미 기각한 "최신 done" 기준.
  `node_analysis.py:2554` 가 `id DESC` 를 정본으로 못박아 뒀다(모든 UPDATE 가 updated_at 트리거를
  올려 과거 run 이 최신으로 역전). 라이브에서 두 기준이 갈리는 노드 **13개, 전부 분석문 텍스트 상이**.
  → 판정 대상과 상세 패널이 다른 문장을 가리키고, 화면에 보이는 최신 분석문은 영영 미판정.
  **반영**: 내부 정렬 `j.id DESC` (+ fan-out 대비 `m.stage DESC`).
- **[P1] 재판정 starvation** — "미판정 우선" 첫 키가 갱신된 분석문을 미판정 집합 뒤 + stage 뒤로 두 겹
  강등시켜, 완충(limit×5) 밖에서 ADR-0036-04 계약이 조용히 죽는다.
  **반영**: `ORDER BY t.verdict_at ASC NULLS FIRST` 라운드로빈. (해시 술어를 SQL 로 내리는 대안은
  Python/SQL 해시 정의 이중화 = drift 위험이라 미채택 — 라운드로빈으로 같은 목적 달성.)
- **[P1] `rejudged` 가 저장 성공만 센다** — LLM 콜을 태우고 판정에 실패하는 경로가 계기판에 안 보인다.
  실패 노드는 미판정으로 남아 큐 선두를 계속 물어 자기증폭. **반영**: `attempted` 카운터 + 연속 실패
  상한(5).
- **[P2] 원인 오귀속** — 중복 done 행은 back-refine 이 아니라 **별개 분석 run** 산물(다세대 노드 489개
  전부 run_id 상이). 틀린 전제가 대안 기각 근거로 쓰였다. **반영**: 코드 주석·ADR·FUNCTION·REPORT·
  TASK·LEARNINGS 정정.
- **[P2] advisory lock 밖 실행** — 행 단위 claim 이 없어 워커 증설 시 콜이 워커 수만큼 중복되고,
  그 중복은 `rejudged` 에도 안 잡힌다. **반영**: `if lock_acquired:` 안으로 이동.
- **[P2] join fan-out 시 얕은 stage 선택 위험** — **반영**: 내부 정렬에 `m.stage DESC` tie-break.
- 건전 판정: SQL 문법·의미, 불리언 정렬 방향, 순환 폐쇄(구 192행→신 92행), fail-soft 계약 무훼손,
  telemetry 하위호환, 커밋 경로.

## REV-20260805T160500-analysis-verify-loop [SUBAGENT:qa] — 반려 → 반영 완료

**대상**: 동 diff 의 테스트 검출력. **방법**: 변이 테스트 11건(9건이 41 테스트를 전부 통과).

- **[P1] SQL 유효성 미검증** — 서브쿼리 select 한 항목만 지워도 런타임 `column does not exist` 인데
  fail-soft 가 삼켜 `skipped="no_targets"` 로 위장한다(기능 영구 사망 + 건강해 보이는 텔레메트리).
  **반영**: env-gated 실 PG 통합 테스트 추가. 라이브 1회 실행으로 vacuous 아님 확인(92행/92노드).
- **[P1] SELECT 컬럼 순서 미검증** — `stage` ↔ `analysis_hash` 를 맞바꾸는 한 줄 변이가 전 테스트
  통과. 그 변이는 해시 비교를 **절대 성립하지 않게** 만들어 순환을 그대로 복구시킨다.
  **반영**: 컬럼 목록 ↔ 언팩 변수 이름 단위 대조 테스트.
- **[P1] `rejudged` 가 운영자에게 도달하지 않음** — `scan_report["analysis_verify"]` 는 dict 라
  `_telemetry_sweep` 스칼라 필터가 통째로 버린다. 같은 실패가 이 워커에서 **이미 두 번** 있었고
  주석까지 남아 있다(세 번째 재발 직전). **반영**: payload allow-list 등재 + 등재 고정 테스트 +
  `checked or attempted` 로 기록 조건 완화.
- **[P2]** DISTINCT ON 주석화 변이 통과 → 주석 제거 후 검사. **[P2]** rejudged 위치 미고정 →
  저장 실패·같은 해시 skip 두 경우 단정. **[P2]** 완충 배수 미검증 → params 단정.
  **[P2]** stage 정렬 위치 약화 → 2차 키로 고정. **[P2]** 중복 테스트 2건 → 1건 정리.
- 건전 판정: 수정 자체는 라이브에서 옳다(윈도우 92행 중 skip 89 / 미판정 1 / 정당 재판정 2 —
  구 쿼리는 미판정 0 / 재판정 9). mock 분기는 여전히 유효하고 빗나가면 fail-loud.
- 미해결(정직 표기): 순환을 **행동 수준**으로 재현하는 단위 테스트는 현 mock 구조에서 원리적으로
  불가(저장이 다음 pass 대상 집합을 바꾸는 것이 mock 에 없음). env-gated PG 통합 테스트가 그 자리를
  대신하나 CI 기본 실행에는 포함되지 않는다.

## REV-20260805T193000-verdict-surfacing [SUBAGENT:ux] — 반려 → 반영 완료

**대상**: 판정 배지 표시(P1 cycle). **방법**: 팔레트 규약·CSS 대비 계산·범례 구조 대조.

- **[P1] `✓ 증거와 부합` 이 "이 분석은 옳다"로 읽힌다** — 같은 패널에 이미 "신뢰 관계(FK·검증)"라는
  **결정적 사실** 배지가 있어 혼동이 커지고, 실패한 판정은 기록되지 않으므로(생존편향) 화면에 뜨는
  것은 판정자가 자신 있었던 부분집합이다. **반영**: `✓` 제거, 라벨을 "모순 없음"으로 약화.
- **[P1] ADR-0036-09 가 선언한 "색 계열 분리"가 코드에 없다** — 실제로는 역할 팔레트를 그대로
  재사용해, `config`(#D55E00) 역할 칩 + `contradicted` 배지가 같은 색·같은 클래스·같은 간격으로
  연달아 붙는다(경보가 카테고리 태그로 읽힘). **반영**: 상태 태그 시스템(`--tag-*`)으로 교체.
- **[P1] 세 배지 전부 대비 4.5:1 미달** — #009E73 3.42:1(팔레트가 "4.5 미달"이라 라벨을 뒤집어
  구제한 바로 그 값), #D55E00 3.87:1, #8b949e 3.08:1(이 저장소 값도 아님 — 도달 불가 fallback).
  **반영**: `--tag-*` 가 4.3~5.7:1 을 보증.
- **[P2] "배지 없음 = 미판정"을 화면이 안 가르친다** → 범례에 판정 3종 + 그 규칙 추가.
- **[P2] 근거 문장이 라벨 없는 유일한 문단 + 500자 clamp 없음** → `판정 근거 —` 라벨 + 200자 접기
  (전문 tooltip).
- **[P2] `evidence_stage`·`created_at` 을 계산·직렬화해 놓고 프론트가 버린다** → tooltip 노출.
- **[P2] 로그/UI 어휘 드리프트** → 로그를 UI 어휘로 통일.
- 건전 판정: 빈 상태 마크업(잔여 `<p>`·여백 없음), fail-closed(미등록 verdict 미렌더), 이스케이프,
  필드 부재 시 기존 화면과 동치, 색맹 안전성 자체(실패는 hue 가 아니라 명도 축).

## REV-20260805T193500-verdict-surfacing [SUBAGENT:backend-security] — 반려 → 반영 완료

**대상**: 동 cycle 의 백엔드 계약. **방법**: 라이브 양방향 실증 + 변이 테스트.

- **[P1] 판정의 나머지 절반(증거)을 고정하지 않는다** — `analysis_hash` 는 분석문만 덮고
  `metadata_table_stats` 는 테이블당 1행이 제자리 갱신된다. 해시가 같으면 skip 하므로 **한 번
  판정되면 증거가 아무리 깊어져도 다시 판정되지 않는다**. 라이브: 판정 95건 중 **82건이 stage 0**,
  그리고 stage 0 증거에는 측정값이 전무하다(83 테이블 전부 `sampled_rows=0`, 691 컬럼 전부
  distinct/null_ratio/min/pattern 없음). 이 cycle 이 그 잠재 속성을 사용자 대면 확인 도장으로
  바꾸는 변경이라 여기서 막아야 한다. **반영**: 저장된 `evidence_stage` < 현재 stage 면 재판정
  (ADR-0036-10) + 라벨이 stage 0 을 "구조와 모순 없음"으로 구분.
- **[P2] `_savepoint` 가 웹 경로에서 보장된 no-op 이고 노드 클릭마다 PG 서버 로그에 ERROR** —
  autocommit 이라 SAVEPOINT 가 항상 실패한다. 문서·위험표·테스트는 다른 메커니즘을 주장했다.
  **반영**: autocommit 가드(모든 호출자 이득) + 그 동작을 테스트로 고정.
- **[P2] 테스트가 조회 조건의 scope/node 를 고정하지 않는다** — WHERE 를 해시 단독으로 바꾼 변이가
  백엔드 6건을 전부 통과했다. **반영**: `verdict_params` 3요소 전부 단정.
- **[P2] Table 이 아닌 노드에도 조회가 나간다** — 라이브 done 행의 79%가 Column/Routine.
  **반영**: `node_label='Table'` 가드 + 테스트.
- **[P2] 800자 clip 이 "판정자가 읽은 것"과 "해시가 덮는 것"을 분리** — 현재는 잠재(최대 250자).
  **반영**: ADR-0036-10 에 남은 창으로 명시.
- **[P2] 문서 nit**: FUNCTION.md 의 "전부 해시 일치"는 움직이는 수량의 스냅샷. **반영**: 재분석 중
  일시 불일치 → 자동 회복을 실증으로 기술.
- 건전 판정(라이브 실증): 해시 정합 95/95 양방향, 행 선택 수렴 0 divergence(2,052 노드), 트랜잭션
  오염 경로 없음(autocommit + fetchone 이 savepoint 안 + cursor 획득이 try 안), 주입·교차 스코프
  누출 없음(12,169/12,169 행이 scope prefix 일치), 비용 0.42ms/클릭.
