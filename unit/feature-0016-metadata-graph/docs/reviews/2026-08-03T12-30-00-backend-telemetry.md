---
doc_type: REVIEW_ARTIFACT
feature_id: feature-0016-metadata-graph
agent: backend
timestamp: 2026-08-03T12:30:00+09:00
trigger: code change (insight_worker telemetry) — 승인 없는 자동 LLM 지출 경로의 관측 수단
verdict: BLOCK
---

# 적대 리뷰 (backend) — 계측 도달 규약 (change-reanalysis POST-DEPLOY 보정)

> 흡수 내역은 REVIEW.md REV-20260803T123000 및 TASK.md TCR.11a 참조.

### 1. Blocking issues

**B1 (high) — 같은 클래스의 결함이 자동 LLM 지출 경로에 그대로 살아 있다: `coverage_seeded` 미등재**

- **Evidence**: `_seed_coverage_targets` 가 `report["coverage_seeded"] = int(report.get("coverage_seeded", 0)) + seeded` 로 기록한다(`reason="coverage_priority"` — change-reanalysis 와 **같은** 사람-confirm 없는 자동 LLM 지출 경로, feature-0035 ITEM-11). 저장소 전체 grep 결과 `coverage_seeded` 는 insight.py:659(사이클 cap 누산), insight.py:690(기록), test_analysis_planner.py:238(소스 텍스트 assert) 세 곳뿐이고 payload allow-list(insight.py:3403–3446)에는 없다. cycle report 의 유일한 sink 는 insight.py:3502 `append_log_line("insight_worker", json.dumps(payload, ensure_ascii=False))` 이므로 이 카운터는 운영자에게 도달하지 않는다. 신규 테스트의 두 정규식은 `auto_reanalysis_\w+` 로 prefix-scope 되어 있어 구조적으로 이 키를 볼 수 없다.
- **Location**: `unit/feature-0002-agent-core/src/modules/insight.py:690`
- **Reason**: 이번 보정의 명시적 전제는 "allow-list 미등재 = 승인 없는 자동 LLM 지출이 무음이 된다" 이고, `coverage_seeded` 는 정확히 그 전제에 해당하는 두 번째 자동 지출 경로다. `absorbed`/`axis_dropped` 만 고치고 같은 함수 파일 안의 동일 결함을 남기면 보정은 증상 2건 처리에 그치고, MODIFY.md 가 주장하는 "재발 방지 장치가 본체" 라는 서술이 실제로는 성립하지 않는다. 게다가 신규 테스트가 이 키를 볼 수 없으므로 다음 관측 때도 같은 방식으로 발견될 수밖에 없다.
- **Action**: payload allow-list 에 `"coverage_seeded": int(scan_report.get("coverage_seeded", 0) or 0)` 를 등재하고, 회귀 테스트의 prefix scope 를 `auto_reanalysis_` 에서 "per-schema `report` 에 기록되는 모든 스칼라 키" 로 넓힌다(deny-list 방식으로 의도적 비노출 키만 예외 등록). 최소한 `coverage_seeded` 를 테스트 대상 prefix 목록에 추가할 것.

**B2 (high) — FUNCTION.md 가 관측 계약으로 선언한 카운터 4개가 payload 에 도달하지 않는다**

- **Evidence**: per-schema `report` 에 기록되지만 `scan_report` 에서 다시 읽히지 않는 리터럴 키를 전수 추출한 결과 6개 — `coverage_seeded`(690), `relationships_introspected`(1787), `relationships_inferred`(1826), `routines_introspected`(1873), `insight_llm_calls`(2303), `tables_fanout`(2354). 이 중 4개는 문서가 관측 수단으로 명시한다: `unit/feature-0002-agent-core/docs/FUNCTION.md:28` "관측: `source_meta.table_family` + report `insight_llm_calls`/`tables_fanout`", `unit/feature-0013-relationship-diagrams/docs/FUNCTION.md:120` "insight cycle telemetry: `relationships_introspected` …", `unit/feature-0016-metadata-graph/docs/FUNCTION.md:174` "implicit-edges (insight report): `relationships_inferred`". 6개 모두 payload dict(3403–3468) 어디에도 없고 다른 dump 경로도 없다(전 파일에서 report/scan_report 를 직렬화하는 지점은 3502 한 곳).
- **Location**: `unit/feature-0002-agent-core/src/modules/insight.py:2303`
- **Reason**: `insight_llm_calls` 는 실제 LLM 호출 수, 즉 비용 신호다. `tables_fanout` 은 그룹화(2026-07-03 Major 결정)가 실제로 LLM 을 아끼고 있는지의 유일한 수치다. 두 값 모두 문서가 "관측된다" 고 선언한 상태로 도달하지 않으므로, 이번 cycle 이 `absorbed` 에서 겪은 것과 동일한 "문서는 관측 가능하다고 말하는데 실제로는 무음" 상태가 최소 4건 더 존재한다. 이번 보정이 이 클래스를 봉인했다고 문서에 기록하면 그 기록 자체가 사실과 다르다.
- **Action**: 6개 키를 payload 에 일괄 등재하거나(권장 — 전부 int 카운터라 병합 규약과 정합), 등재하지 않을 키는 FUNCTION.md 의 관측 서술을 정정한다. 어느 쪽이든 이번 cycle 의 TASK.md/MODIFY.md 에 "동일 클래스 잔존 N건" 을 명시해 다음 관측이 같은 발견을 반복하지 않게 한다.

**B3 (high) — 회귀 테스트가 등재를 잃는 현실적 3가지 방식 중 2가지를 PASS 시킨다 (거짓 안심)**

- **Evidence**: 소스에 대해 테스트와 동일한 정규식을 적용해 mutation 3종을 실측했다. ① 등재 1줄 **삭제** → `missing=['auto_reanalysis_absorbed']` → FAIL(주장대로 동작). ② 같은 줄을 `#` 로 **주석 처리** → `missing=[]` → **PASS**. ③ 등재를 payload 밖 지역변수로 이동(`_absorbed = int(scan_report.get("auto_reanalysis_absorbed", 0) or 0)`) → `missing=[]` → **PASS**. ③ 은 가상이 아니라 같은 파일의 기존 관용구다(insight.py:3385 `_db_failed = int(scan_report.get("db_failed", 0) or 0)` — payload 아닌 status 판정용). 또한 `recorded` 정규식은 리터럴 subscript 대입만 잡는데 이 파일은 이미 변수 키 기록을 쓴다(insight.py:1843 `report[_rk] = int(report.get(_rk, 0)) + …`, insight.py:3240 `scan_report[_reason_counter] = …`); 반대로 `exposed` 정규식은 리터럴 `.get("…")` 만 잡는데 payload 는 이미 변수 노출을 쓴다(insight.py:3467 `payload[_pk] = int(scan_report.get(_pk, 0) or 0)`) — 올바르게 노출된 키가 **거짓 FAIL** 로 잡히는 방향의 구멍이다.
- **Location**: `unit/feature-0002-agent-core/tests/test_node_analysis_change_reanalysis.py:862`
- **Reason**: 이 테스트는 "payload 에 도달함" 이 아니라 "파일 어딘가에 두 문자열이 함께 존재함" 을 검사한다. 주석 처리는 기능을 일시 비활성화하는 가장 흔한 방식이고, 지역변수 추출은 이 파일의 실제 관용구이며, 변수 키 기록/노출도 이미 이 파일에 존재한다. mutation 검사를 "1줄 제거" 한 가지로만 돌린 탓에 방어 범위가 실제보다 넓게 보고됐고, MODIFY.md 는 이 장치를 "보정의 본체" 로 규정한다. 방어가 절반만 성립하는 장치를 본체로 기록하면 다음 계측 추가 때 같은 무음이 재발하면서도 CI 는 녹색이다.
- **Action**: 소스 텍스트가 아닌 **런타임 payload 키 집합**을 검사한다 — `append_log_line` 을 monkeypatch 하고 `scan_report` 를 전 report 키로 시드한 뒤 `run_insight_cycle` 을 1회 돌려 `recorded_keys <= set(payload)` 를 assert. 텍스트 검사를 유지해야 한다면 최소한 (a) 매칭 전 주석·docstring 을 제거하고, (b) `exposed` 를 `payload.update({ … })` 리터럴 블록 범위로 한정하며, (c) 변수 키 기록/노출 idiom 을 탐지해 발견 시 명시적으로 실패(수동 확인 요구)시킨다.

### 2. Cross-domain concerns

**C1 (medium) — `shadow`·`unknown` status 는 어떤 카운터도 올리지 않는다. 이번 cycle 의 라이브 실증이 정확히 그 상태를 밟았다**

- **Evidence**: `_AUTO_BLOCKED_STATUSES = frozenset({"ineligible","cooldown","busy","disabled","noop"})`(insight.py:638) 이고 `_auto_note_status` 는 `runs` 를 `status=="running"` 에만, `blocked` 를 위 집합에만 올린다(insight.py:710–712). `enqueue_change_analysis` 는 `status="shadow"` 를 반환하며(node_analysis.py:1233) 호출부는 `status or "unknown"` 을 넘긴다(insight.py:590). 두 값 모두 어느 집합에도 없다. `test_shadow_status_measures_without_advancing_snapshot`(테스트 583–595)도 `candidates` 만 assert 하고 blocked/shadow 카운터는 검사하지 않는다. 그런데 TEST.md:1101–1104 의 3-state 표는 `CAP=-1 → status='shadow'` 를 PASS 로 기록한다.
- **Location**: `unit/feature-0002-agent-core/src/modules/insight.py:638`
- **Reason**: insight.py:637 의 주석은 blocked 를 "무발동 status — 운영자가 '왜 안 도는가'를 수치로 본다" 로 정의하는데, shadow 는 무발동이면서 그 집계에서 빠져 있다. shadow 는 "비용 0 으로 후보 규모를 관측" 하기 위한 모드인데 정작 payload 는 `candidates>0 / seeded=0 / runs=0 / blocked=0` 을 내보내며, 이는 "enqueue 가 빈 status 를 돌려주고 조용히 실패" 와 구별되지 않는다. 안전 모드가 실제로 걸려 있는지를 텔레메트리로 확인할 수 없다.
- **Action**: `_AUTO_BLOCKED_STATUSES` 에 `"shadow"` 를 넣거나(간단) 별도 `auto_reanalysis_shadow` 카운터를 두고 payload 에 등재한다. `"unknown"` 은 정상 상태가 아니므로 별도 오류 카운터로 집계해 malformed enqueue 응답이 조용히 묻히지 않게 한다.

**C2 (medium) — `auto_reanalysis_failed` WARN 에 카운터가 없어 `candidates == 0` 이 "정상 무변경" 과 "매 사이클 예외" 를 구별하지 못한다 — TEST.md 최상단 행이 바로 그 값에 근거한다**

- **Evidence**: `_auto_reanalyze_structure_changes` 전체가 `except Exception: log.warning("auto_reanalysis_failed schema=%s", schema_key, exc_info=True)`(insight.py:633–634)로 감싸여 있고, 이 핸들러에는 `report[...]` 기록이 전혀 없다. 한편 TEST.md:1086 은 `| **오탐(변경 없을 때 미발동)** | auto_reanalysis_candidates = 0 — 08-03 최신 사이클까지 전 구간 0 | PASS |` 로 이 값을 최우선 판정 근거로 삼는다. 신규 회귀 테스트는 여기에 도움이 되지 않는다 — "기록된 것이 도달한다" 만 보장하고 "일어난 일이 기록된다" 는 보장하지 않기 때문이다.
- **Location**: `unit/feature-0002-agent-core/src/modules/insight.py:634`
- **Reason**: 자격 스키마에서 KV 파손·import 실패·드라이버 예외가 매 사이클 발생해도 payload 는 `candidates=0, seeded=0` 으로 "건강한 무변경" 과 동일하게 보인다. 실제 관측에서 `SchemaAuto` 4 run 과 `blocked` 112 가 있어 경로 전체가 죽지는 않았음이 간접 증명되지만, 그것은 **일부 스키마의 지속 예외** 를 배제하지 못한다. 이 무음 축이 남아 있는 한 "오탐 0" 은 관측이 아니라 추론이다.
- **Action**: 예외 핸들러에 `report["auto_reanalysis_errors"] = int(report.get("auto_reanalysis_errors", 0)) + 1` 을 추가하고 payload 에 등재한다(신규 회귀 테스트가 자동으로 커버). TEST.md 의 오탐 행은 "candidates 0 **且** errors 0" 으로 조건을 명시하거나, 현행 근거가 4 run + blocked 112 라는 간접 liveness 임을 각주로 남긴다.

**C3 (low) — 문서 정합: 예산 회계 행이 자기 데이터가 반증하는 등식을 주장하고, 3-state 실증의 범위 한정이 TASK.md 에만 누락됐다**

- **Evidence**: `TEST.md:1093` 은 `| 예산 회계 | \`enqueued == done == node_budget\` (40/40 · 20/20 · 4/4 · 3/4) — ratchet·초과 지출 없음 | PASS |` 인데, 네 번째 쌍 `3/4` 는 `== node_budget` 을 위반한다. 오타가 아니라 실데이터다 — 40+20+4+3 = 67 로 같은 표의 "잡 67건" 행과 정확히 일치한다. 참 불변식은 `enqueued == done` 과 `enqueued <= node_budget` 두 개다. 또한 TEST.md 의 범위 한정 인용문("상시 구동 중인 워커 프로세스가 TTL 만료 후 … 관측하지 않았다")과 MODIFY.md 의 "실증 범위의 한계(워커 상시 프로세스의 TTL 반영은 미관측)" 는 caveat 를 달지만, `TASK.md:2591` 의 체크박스는 "**라이브 3-state 정지 스위치 실증**(50→0 `disabled`→-1 `shadow`→원복, 스냅샷 바이트 일치)" 로 무조건 서술한다.
- **Location**: `unit/feature-0016-metadata-graph/docs/TEST.md:1093`
- **Reason**: TASK.md 체크박스는 이후 cycle 이 가장 먼저 훑는 요약면이라, 여기서 caveat 가 빠지면 "상시 워커의 라이브 전환이 실증됐다" 로 승계된다. 예산 등식은 더 직접적이다 — 운영자·후속 리뷰어가 `enqueued == node_budget` 을 불변식으로 받아들이면 정상인 `3/4` 를 회계 결함으로 오진하거나, 반대로 진짜 ratchet 을 이 등식으로 검출하려다 놓친다.
- **Action**: 예산 행을 `enqueued == done` · `enqueued <= node_budget` 두 불변식으로 분리 서술하고 `3/4` 가 미소진 케이스임을 한 줄 덧붙인다. TASK.md TCR.11 체크박스에 "(범위: 새 프로세스 읽기 실증 — 상시 워커 TTL 반영 미관측, TEST.md 참조)" 를 삽입한다.

**C4 (low) — 보정 범위 밖의 파일 모드 변경이 diff 에 섞여 있다**

- **Evidence**: `git diff` 헤더가 `old mode 100755 / new mode 100644` 를 포함한다. 인덱스는 `git ls-files -s` 기준 `100755`, 작업본은 `-rw-rw-r--` 로 실행 비트가 떨어졌다. 같은 디렉터리의 다른 모듈은 100644 37개 / 100755 13개로 혼재해 있어 이 변경이 정규화 의도인지 사고인지 diff 만으로는 판별되지 않는다. `insight.py` 는 `agent_core.py:6709` 의 `from modules.insight import run_insight_worker_loop` 로만 로드되므로 기능 영향은 없다.
- **Location**: `unit/feature-0002-agent-core/src/modules/insight.py:1`
- **Reason**: "비파괴 계측 2줄 추가" 로 등급 Minor 를 주장하는 cycle 의 diff 에 의도 미기재 메타데이터 변경이 섞이면, 등급 판정과 diff 의 자기설명성이 어긋난다. 파일 모드는 리뷰에서 가장 쉽게 지나치는 축이라 여기서 걸러 두는 편이 낫다.
- **Action**: 의도한 정규화면 MODIFY.md CHG 에 한 줄 명기하고, 아니면 `git update-index --chmod=+x` 로 100755 를 복원해 diff 를 코드 2곳으로 한정한다.

### 3. Challenge to current spec

**allow-list 는 원인이지 무대가 아니다.** 이번 보정은 "명시 allow-list 라 등재를 빠뜨리면 무음" 이라는 진단을 정확히 내려 놓고, 해법으로 allow-list 를 유지한 채 그 위에 정규식 감시자를 얹었다. 두 층 모두 사람의 규율에 의존한다는 점은 같고(등재 기억 → 정규식 관용구 준수), 실측이 보여준 결과는 감시자가 실제 유실 방식 3종 중 2종을 통과시킨다는 것이다(B3). 그리고 감시자가 보호하지 못한 영역에는 이미 6개의 고아 카운터가 있다(B1·B2). 더 근본적인 방향은 **역전**이다 — `scan_report` 의 스칼라(int/float/bool) 전량을 payload 로 흘리고, 제외할 키만 짧은 deny-list 로 명시하는 것. 그러면 "기록했다 ⇒ 도달한다" 가 규약이 아니라 구조가 되고, 새 계측을 추가하는 사람은 아무것도 기억하지 않아도 된다. 병합 규약(`int/float 합산 · bool OR · 그 외 덮어쓰기`, insight.py:3185–3190)이 이미 스칼라만 안전하게 다루도록 설계돼 있어 이 역전과 자연스럽게 맞물린다. payload 크기나 PII 가 allow-list 의 진짜 이유라면 그 이유를 코드 주석에 명시해야 한다 — 현재 주석은 "여기 등재하지 않으면 도달하지 않는다" 는 **결과**만 말하고 왜 allow-list 여야 하는지는 말하지 않으며, 그래서 이 설계 결정이 재검토 대상인지 아닌지 다음 사람이 판단할 수 없다.

**질문 1(등재의 정합성)에 대한 답은 긍정이다.** 두 키 모두 `int(scan_report.get(k, 0) or 0)` 로 형제 키와 동일한 형태이고, 기록도 `report[k] = int(report.get(k, 0)) + n` 형태의 순수 int 누산이라 datasource 순회 합산 규약과 어긋나지 않는다(`_auto_note_status` docstring 이 명시적으로 경계하는 dict 저장을 피했다). 소비처 파손 여지도 없다 — payload 의 유일한 sink 는 JSON 한 줄이고, `_insight_worker_axis`(admin_console.py:589 경유)는 heartbeat KV 를 읽지 이 로그를 파싱하지 않는다. 컨테이너 이미지에서 실행한 결과 해당 테스트 파일 **51 PASS**, 변경 2파일 `ruff check --no-cache` clean. 즉 등재 자체는 문제가 없고, 문제는 등재가 **덜 됐다는 것**(B1·B2)과 **지킴이가 약하다는 것**(B3)이다.

**질문 4(라이브 실증이 증명하는 것)를 코드로 확정해 둔다.** 실증이 증명한 것은 "스냅샷 파일 override → 워커 컨테이너 내 프로세스가 그 값을 읽음 → `enqueue_change_analysis` 게이트가 `disabled`/`shadow` 로 전환" 까지다. 증명하지 않은 것은 상시 워커가 10초 TTL 만료 후 스스로 전환되는 것이고, TEST.md 는 이를 정직하게 적어 두었다(TASK.md 만 누락 — C3). 다만 문서가 "3-state" 를 하나의 스위치로 묶어 부르는 것은 코드와 어긋난다: cap 0/-1 은 `auto_setting_int`(node_analysis.py:1121)가 호출 시점에 `runtime_settings` 를 읽으므로 진짜 라이브지만, `insight.py:526` 의 선행 게이트 `if not AGENT_NODE_ANALYSIS_AUTO_ON_CHANGE` 는 `shared/config.py:1526` 에서 import 시점에 굳는 star-import 상수 — `auto_setting_int` docstring 이 "import 시점 상수로 읽으면 이 조절이 반영되지 않는다" 며 스스로 경계한 바로 그 형태다. 그러므로 **env 문자열 3-state 는 재배포가 필요하고 cap 정수 3-state 만 라이브**다. 문서는 이 비대칭을 명시해야 한다. 사고 시 운영자가 env 쪽을 만지면 "즉시 정지" 가 성립하지 않는다.

**부수 관찰 두 가지.** 첫째, TEST.md:1095 의 "116 스키마 중 **112 blocked**, 자격 보유 13" 은 표면상 112+13=125>116 이라 읽는 사람이 멈춘다. 자격 보유 13 중 일부가 cooldown/busy/noop 로 blocked 에 합산됐다면 정합하지만, 그 해석이 표에 없다 — 한 줄 보강이 필요하다. 둘째, 이번 보정은 `absorbed` 를 payload 집계로만 노출하고 **per-schema 로그 라인은 추가하지 않았다**. `_auto_note_status` 는 status 변화 시 `auto_reanalysis schema=… status=…` 를 남기지만 absorbed 는 여기 실리지 않으므로, TCR.11b 가 답하려는 "어느 샤드가 언제 흡수됐는가" 는 사이클 총합 증분에서 역산해야 한다. 하루 경계 관측이 목적이라면 `_auto_note_status` 의 msg 포맷에 `absorbed=%s` 를 한 필드 추가하는 편이 TCR.11b 를 실제로 판정 가능하게 만든다.

### 4. Verdict

BLOCK