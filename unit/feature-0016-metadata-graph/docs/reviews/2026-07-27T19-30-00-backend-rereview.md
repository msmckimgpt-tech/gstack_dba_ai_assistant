---
doc_type: REVIEW_ARTIFACT
feature_id: feature-0016-metadata-graph
agent: backend
timestamp: 2026-07-27T19:30:00+09:00
trigger: schema/스키마 · migration/마이그레이션 · query/쿼리 keyword matched (change-reanalysis 자동 LLM 지출 경로)
verdict: BLOCK
---

# 적대 리뷰 (backend 재검증) — change-reanalysis 2라운드

> 1라운드 BLOCK(B1~B7·C1~C4) 흡수 후의 재검증. 흡수 내역은 TASK.md '리뷰 흡수' 표 2라운드(S1~S12) 참조.
> 본 아티팩트는 리뷰어 응답을 오케스트레이터 컨텍스트에서 전사한 것이다(세션 로그 flush 이전 시점).

### 1. Blocking issues

**B1 (critical) — 날짜/번호 샤드 테이블의 일상적 신설이 승인 없는 LLM run 을 매일 낳는다: 2026-07-03 사용자 결정으로 도입된 "샤드는 대표 1개만 LLM" 비용 정책을 자동 경로가 통째로 우회한다**
- **Evidence**: `_auto_structure_inventory` 는 `current_table_fps` 를 **원본 그대로** 인벤토리로 삼고(`insight.py:379-402`), `_auto_structure_changes` 는 스냅샷에 키가 없는 항목을 전부 후보로 만든다(`insight.py:406-425`). 그런데 같은 스캔의 insight 본체는 **똑같은 `current_table_fps`** 로 `_build_table_groups` 를 만들어(`insight.py:151-168`, 호출 `insight.py:2027-2028`) `(base_stem, fp)` 그룹의 대표 1개만 LLM 을 태우고 형제 샤드는 `table_group_insight:<fp>:<stem>` KV 상속으로 발행한다(`insight.py:2149`, `:2173`). 이 정책의 근거는 config 주석에 명문화돼 있다 — "날짜 샤드(daily_league_ranking_1_20250727, _20250726 …) 수백 개를 개별 LLM 분석하던 낭비 제거(사용자 결정 2026-07-03)"(`shared/config.py:1110-1118`, 기본 ON). 그리고 전파 발행된 샤드도 `rag_objects`(object_type='table') 를 통해 AGE Table 정점으로 투영되므로(`metadata_graph.py:629-641`) `schema_table_keys` 에 잡혀 자동 시드 자격을 갖는다.
- **Location**: `unit/feature-0002-agent-core/src/modules/insight.py:379`
- **Reason**: log_v2 류 일별 샤드 로그 DB 는 매일 수십 개 테이블이 새로 생긴다. 그 테이블들은 **구조가 직전 샤드와 완전히 동일**(fp 동일)해서 분석 가치가 0 이지만, 스냅샷 대조는 "이름이 새 키" 라는 이유로 전부 '신규' 로 판정한다. 결과: 쿨다운 창(1800s)마다 cap(50)개 시드 × `node_budget = 시드×4` 재귀 전개가 사람 승인 없이 무기한 반복되고, 새 샤드가 매일 생기므로 **수렴하지 않는다**. 이것은 스냅샷 재설계(B1 흡수)로 막히는 오탐이 아니다 — 스냅샷은 "진짜 신규" 로 정확히 판정하고 있고, 문제는 이 제품이 이미 "샤드 신설은 LLM 을 태우지 않는다" 를 사용자 결정으로 확정해 두었는데 승인 없는 새 경로가 그 결정을 되돌린다는 점이다. 직전 리뷰 B1 이 지적한 "사람이 한 번 승인한 비용을 승인 없이 재지출" 이 형태만 바꿔 재발했다.
- **Action**: 후보 산출에서 `_table_group_sig`/`_build_table_groups` 를 재사용해, 신규 테이블의 `(base_stem, fp)` 서명이 **이미 스냅샷에 존재하는 형제와 같으면 후보에서 제외**한다(그룹당 최대 1개 대표만 시드). 최소한 `AGENT_INSIGHT_TABLE_GROUPING_ENABLED` 가 켜진 스키마에서는 그룹 멤버 신설을 '구조 변동' 으로 승격하지 않고, 스냅샷에는 담되 후보에서만 빼서 재탐지도 없게 한다.

**B2 (high) — `all_table_names` 가 일시적으로 0 이면 테이블 축 스냅샷이 통째로 비워지고, 복귀 사이클에 구조가 전혀 안 바뀐 전 테이블이 '신규' 로 폭발한다 (축별 baseline 플래그가 이 전이를 덮지 못한다)**
- **Evidence**: 테이블 0 분기가 `current_table_fps={}` + `include_tables=True` 로 호출한다(`insight.py:1878-1886`). 그러면 삭제 반영 경로가 `next_t = {k: v for k, v in snap["t"].items() if k in inventory["t"]}` = `{}` 로 축을 비우고(`insight.py:511`), `tb` 는 `bool(snap["tb"]) or include_tables` = True 로 남는다(`insight.py:513-515`). 따라서 다음 사이클의 `t_new_baseline = include_tables and not snap.get("tb")`(`insight.py:470`)는 False → **축 baseline 재확립이 발동하지 않고** 전 테이블이 곧장 후보가 된다. `all_table_names` 는 `information_schema.TABLES` 단일 조회 결과일 뿐 실패/성공 구분이 없다(`insight.py:1556-1567`).
- **Location**: `unit/feature-0002-agent-core/src/modules/insight.py:1878`
- **Reason**: 이 제품군은 xtrabackup·mysqlsh 복원 도구를 같은 리포에서 운영한다 — `DROP DATABASE`→`CREATE DATABASE`→import 창, 권한 회수/재부여, 대형 DDL 마이그레이션 중간 상태에서 `information_schema.TABLES` 가 0행을 반환하는 창이 실재한다. force_scan(`missing` 스키마 또는 pending repair) 상태에서는 스캔이 6h 게이트를 건너뛰고 8초 tick 마다 돌므로(`insight.py:1475-1487`) 그 창에 걸릴 확률이 낮지 않다. 걸리면 복원 완료 후 **직전과 바이트 단위로 동일한 구조**의 수백 테이블 전체가 자동 재분석 대상이 되어, cap 50/쿨다운 1800s 로 수 시간에 걸쳐 전량 재지출된다. 루틴 축은 `"routines" in _rt_sink` 라는 "관측 신뢰 가능" 신호로 이 클래스를 막았는데(`routines.py:289-295`), 테이블 축만 그 대칭 방어가 없다.
- **Action**: 테이블 축에도 루틴 축과 동형의 신뢰 신호를 둔다 — `information_schema.TABLES` 조회 성공 여부를 별도 플래그로 넘기고, "이전 스냅샷에 테이블이 있는데 이번 관측이 0" 이면 `include_tables=False` 로 축을 보존한다. 추가로 삭제 비율 임계(예: 직전 대비 소실 >50%)를 두어 초과 시 스냅샷 전진을 보류하고 `auto_reanalysis_blocked` 계측만 남긴다.

**B3 (high) — 구조 스냅샷 blob 이 `load_kv_all` 전량 덤프 경로에 올라타 스캔당 5회 증폭되고, 자격 없는 스키마·datasource 에도 무조건 적재된다 (§82 풀·대역 소진 클래스의 재발)**
- **Evidence**: `_load_stored_fingerprints`/`_load_kv_prefix_map` 는 PG 경로에서 `load_kv_all` 로 대화의 **KV 전 행(key + value)** 을 끌어와 파이썬에서 prefix 필터한다(`kb_scope.py:470-492`, SQL `runtime_backend.py:184-187`, `:722-725`). 한 스캔이 이 경로를 5회 탄다(`insight.py:1496-1497`, `:1505-1506`, `:1511`). 새 `na_struct_snap:` 값은 32자 지문이 아니라 **스키마 전 테이블 맵 JSON**(테이블 수천 개면 수백 KB/스키마)이다(`insight.py:368-377`). 그리고 baseline 저장은 자격 판정(`schema_analysis_completed`)보다 **앞**에서 무조건 일어난다(`insight.py:465-469` → 자격은 `node_analysis.py:1088` 에서야 조회). `_load_auto_snapshot` 의 `load_memory_kv` 는 호출마다 PG RO 커넥션을 새로 열고 닫는다(`runtime_backend.py:959-974`, `:995-1021`).
- **Location**: `unit/feature-0002-agent-core/src/modules/kb_scope.py:470`
- **Reason**: force_scan 상태에서 스캔은 8초 tick 마다 돈다(`insight.py:1475-1487`). 그때마다 (모든 datasource · 모든 스키마 스냅샷의 합계 바이트) × 5 가 PG→워커로 전송·JSON 파싱되고, 스키마 수만큼 RO 커넥션이 새로 열린다(MAX_SCHEMAS 20 → 20 conn/tick/datasource). 직전 리뷰 C4 가 "노드당 커넥션" 을 지적해 "스키마당 1건" 으로 줄였지만, 값의 크기가 수십~수백 배로 커지고 호출이 tick 축으로 상시화되어 총량은 개선되지 않았을 수 있다. 게다가 자동 재분석이 **영원히 발동할 수 없는** 미자격 스키마(사용자가 전체 분석을 한 적 없는 DB)의 스냅샷까지 전부 이 비용에 참여한다.
- **Action**: (a) 스냅샷을 `agent_runtime.kv` 가 아닌 전용 테이블로 옮기거나, 최소한 `key LIKE 'na_struct_snap:%'` 서버측 필터 전용 조회를 추가해 `load_kv_all` 덤프에서 제외한다. (b) baseline 저장을 `schema_analysis_completed` 통과 스키마로 제한한다(미자격 스키마는 계측만 — 자격 획득 시 첫 사이클이 baseline 이 되므로 오탐도 늘지 않는다). (c) 스캔 시작 시 스냅샷을 prefix 조회 1회로 일괄 로드해 스키마당 커넥션 open/close 를 없앤다.

**B4 (medium) — cap 절단 순서가 테이블 우선으로 고정돼, 테이블 후보가 상시 cap 을 채우는 DB 에서는 "프로시저/함수 정의 변경" 축이 영구히 기아 상태가 된다**
- **Evidence**: `_auto_structure_changes` 는 테이블 후보를 먼저, 루틴 후보를 뒤에 append 한다(`insight.py:416-424`). `enqueue_change_analysis` 는 그 순서를 보존한 채 `present = [k for k in keys if k in meta]`(`node_analysis.py:1106`) → `targets = present[:cap_v]`(`node_analysis.py:1113`) 로 앞에서부터 자른다. 미시드 후보는 스냅샷이 전진하지 않아(`insight.py:517-518`) **다음 사이클에도 같은 순서로 리스트 머리를 다시 점유**한다.
- **Location**: `unit/feature-0002-agent-core/src/modules/node_analysis.py:1106`
- **Reason**: B1 의 샤드 유입이나 대규모 마이그레이션처럼 테이블 후보가 지속적으로 cap(50) 이상인 스키마에서는 루틴 후보가 절대 `targets` 에 들어가지 못한다. 사용자 요청의 3축(테이블 신규 · 컬럼 구성 변경 · **프로시저/함수 정의 변경**) 중 한 축이 가장 바쁜 DB 에서 실동작하지 않고, 그 사실이 telemetry 에도 드러나지 않는다(`auto_reanalysis_candidates` 는 축 구분 없는 단일 카운터, `insight.py:475-477`). 라이브 검증 계획 TCR.11 도 프로시저 변경을 "한산한 DB 에서 1건" 으로만 확인하므로 이 기아를 잡지 못한다.
- **Action**: cap 을 축별로 분배하거나(예: 루틴에 최소 몫 보장), `present` 를 축 라운드로빈으로 인터리브한 뒤 절단한다. 계측도 `auto_reanalysis_candidates_tables` / `_routines` 로 분리해 어느 축이 절단되는지 관측 가능하게 한다.

### 2. Cross-domain concerns

**C1 — 자동 경로가 수동 경로와 다른 `scope_key` 정규화를 써서 `only_missing` 중복 제거가 깨지고, 같은 노드에 이중 LLM 지출이 난다**
- **Evidence**: 수동 enqueue 라우터는 `scope_key = ....strip().lower()` 로 **소문자화**해 넘긴다(`admin_metadata.py:1943`) → 수동 run/jobs 는 `scope_key='kr_live'` 로 적재된다. 반면 자동 경로는 `sk = get_active_datasource() or "common"`(`insight.py:1615`)의 **원형**을 그대로 run·jobs 에 넣는다(`node_analysis.py:1145-1151`, `_insert_seed_jobs` `node_analysis.py:1165-1195`). `enqueue_schema_analysis(only_missing=True)` 의 중복 제거는 `get_scope_analysis_status(sk)` 의 `scope_key=%s` **정확 일치** 집계에 의존한다(`node_analysis.py:2041-2056`, 호출 `node_analysis.py:822-828`).
- **Location**: `unit/feature-0003-agent-web-ui/src/routers/admin_metadata.py:1943`
- **Reason**: 대소문자가 섞인 datasource key(`KR_LIVE` 같은 `.env` 레거시 라벨 — 이 코드 자신이 `schema_analysis_completed` 에서 그 존재를 전제로 `IN (sk, sk.lower())` 를 넣었다, `node_analysis.py:995-999`)에서는 자동 run 의 jobs 가 수동 경로의 `done_keys` 에 잡히지 않는다. 그 결과 사용자가 'DB 전체 AI 능동 분석' 을 누르면 자동 경로가 **이미 분석해 비용을 지불한 노드를 전부 다시** 시드한다. 반대 방향으로는 마커·역할 표식·`column_descriptions` SSOT 가 두 개의 scope 로 갈라진다. 자격 판정만 대소문자를 흡수하고 **쓰기 측 정규화는 흡수하지 않은** 반쪽 수정이다.
- **Action**: 자동 경로도 run/jobs 적재 시 `sk.lower()` 로 통일하거나(그래프 조회는 원형 유지), 반대로 라우터의 `.lower()` 를 제거해 한쪽으로 수렴시킨다. 어느 쪽이든 `enqueue_change_analysis` 가 쓰는 scope 와 `get_scope_analysis_status` 가 읽는 scope 가 동일함을 단위 테스트로 고정한다.

**C2 — 운영자가 이미 큐잉된 자동 작업을 볼 수도 취소할 수도 없다(CAP=0 은 신규 run 만 막는다)**
- **Evidence**: `_auto_enabled()` 의 라이브 스위치는 `auto_setting_int("AGENT_NODE_ANALYSIS_AUTO_CHANGE_CAP", 50) > 0` 뿐이고(`node_analysis.py:945-950`), 이는 `enqueue_change_analysis` 진입부에서 신규 run 생성만 차단한다(`node_analysis.py:1035-1036`). 이미 적재된 `node_analysis_jobs` 는 `process_pending` 이 계속 claim 해 LLM 을 호출한다(`node_analysis.py:1254-1267` — 잡 선택에 run 종류·root_label 조건 없음). 이번 diff 는 `unit/feature-0003-agent-web-ui/src/routers/` 를 한 줄도 건드리지 않아 `root_label='SchemaAuto'` run 목록·취소 엔드포인트가 여전히 없다.
- **Location**: `unit/feature-0002-agent-core/src/modules/node_analysis.py:945`
- **Reason**: 직전 리뷰 C1 이 요구한 두 가지(라이브 OFF + 목록/취소) 중 앞쪽만 반영됐다. B1·B2 가 라이브에서 발현해 수천 pending 잡이 쌓인 상황에서 운영자가 CAP=0 을 눌러도 **이미 예약된 지출은 전부 집행**된다. 자동 run 은 사용자 화면에도 주황 '분석중' 마커로만 나타나고 출처·run_id 를 알 수 없어, 사용자는 자신이 시작하지 않은 분석을 중단할 수단이 없다.
- **Action**: `root_label='SchemaAuto'` run 조회 + `DELETE FROM node_analysis_jobs WHERE run_id=... AND status='pending'` + run `status='cancelled'` 관리 엔드포인트를 함께 낸다. 최소한 CAP=0 일 때 `process_pending` 이 `SchemaAuto` run 의 pending 잡을 drain 하지 않고 보류하도록 게이트를 하나 더 둔다.

**C3 — shadow 모드는 라이브 조절이 불가능하고, `enqueue_change_analysis` 자체에는 shadow 게이트가 없다**
- **Evidence**: shadow 판정은 `str(getattr(_cfg_mod(), "AGENT_NODE_ANALYSIS_AUTO_ON_CHANGE_MODE", "1")) == "shadow"`(`insight.py:479`)인데, `_cfg_mod()` 가 돌려주는 `shared.config` 의 그 속성은 import 시점 env 스냅샷이다(`shared/config.py:1259-1263`) — 호출 시점 조회처럼 보이지만 값은 프로세스 수명 동안 불변이고 `runtime_settings` 에도 미등록이다(`shared/runtime_settings.py:863-887` 는 cap·쿨다운 2종만 등재). 한편 `_auto_enabled()`(`node_analysis.py:945`)는 `AGENT_NODE_ANALYSIS_AUTO_ON_CHANGE` 가 `"shadow"` 여도 truthy 로 읽어 True 를 반환하므로, enqueue 함수는 shadow 를 전혀 모른다.
- **Location**: `unit/feature-0002-agent-core/src/modules/insight.py:479`
- **Reason**: "배포 직후 shadow 로 규모 측정 후 정상 전환" 이라는 TCR.11 계획을 실행하려면 **매 전환마다 재배포**가 필요하다 — 폭주가 관측됐을 때 shadow 로 되돌리는 것도 재배포다. 또 shadow 를 우회하는 진입점(`enqueue_change_analysis` 직접 호출, 향후 라우터/백필)이 열려 있어 안전 모드가 호출자 규율에만 의존한다. 안전 모드의 보증 지점이 잘못된 계층에 있다.
- **Action**: 3-state 를 `runtime_settings` 문자열 스펙으로 노출(또는 `AUTO_CHANGE_CAP` 에 `-1 = shadow` 규약 부여)해 라이브 전환 가능하게 하고, shadow 판정을 `enqueue_change_analysis` 안으로 내려 `status='shadow'` 를 반환하도록 한다(호출자는 `seeded_keys` 가 비므로 스냅샷 전진 로직 변경 불요).

**C4 — 테스트가 실제 배선을 한 줄도 통과시키지 않아, B2·B3 같은 call-site 결함에 구조적으로 눈이 멀다**
- **Evidence**: 스냅샷 테스트는 전부 `_run(...)` 헬퍼로 `_auto_reanalyze_structure_changes` 를 **직접** 호출하며 `include_tables`/`include_routines` 를 손으로 지정한다(`tests/test_node_analysis_change_reanalysis.py:333-339`). 즉 `include_tables=bool(current_table_fps)`(`insight.py:1936`), `include_routines=_auto_routines_dialect_ok and "routines" in _rt_sink`(`insight.py:1937`), 그리고 문제의 `not all_table_names` 분기(`insight.py:1878-1886`)는 어떤 테스트도 실행하지 않는다. 라이브 정지 스위치 테스트(`:154-165`)도 autouse fixture 가 `na.auto_setting_int` 를 config 직독 lambda 로 갈아끼워(`tests/...:87-105`) `runtime_settings.get_int` 경로를 우회한다.
- **Location**: `unit/feature-0002-agent-core/tests/test_node_analysis_change_reanalysis.py:333`
- **Reason**: 이 기능의 위험은 판정 함수 내부 로직이 아니라 **"insight 스캔이 어떤 상황에서 어떤 플래그로 그 함수를 부르는가"** 에 거의 전부 있다. 31 PASS 는 "규칙이 규칙대로 동작한다" 만 증명하고 "규칙에 넘어가는 입력이 실제로 신뢰 가능한가" 는 증명하지 않는다 — B2 는 정확히 그 틈에서 나온다. 또 `AGENT_NODE_ANALYSIS_AUTO_CHANGE_CAP=0` 이 라이브 정지로 동작하는지도 실경로로는 미검증이라, MODIFY.md 가 근거로 든 "⑤ 재배포 없이 라이브 정지" 주장이 테스트로 뒷받침되지 않는다.
- **Action**: `_scan_instance_schema_insights` 를 fake db_conn(information_schema 응답 주입)으로 구동하는 배선 테스트를 추가한다 — 최소 3케이스: (a) 테이블 목록이 일시 0 → 다음 사이클에 후보 0 (b) 지문 계산 부분 실패 → 스냅샷 미소실 (c) 루틴 introspect 미발화 tick 에서 루틴 축 보존. `auto_setting_int` 는 monkeypatch 하지 말고 `runtime_settings` override 파일을 실제로 심어 CAP=0 을 검증한다.

### 3. Challenge to current spec

직전 라운드의 지적은 성실히 흡수됐다. 전용 스냅샷(B1)·busy no-op(B2)·과반 자격(B3)·행 단위 시드 try(B7)·확정 `enqueued`(B7)·시드 전멸 시 run DELETE(B7)·cap 0 라이브 스위치(C1)·후보 산출의 try 내부 이동(C3)·스키마당 KV 1건(C4)은 코드상 실재하고 판정 순서(자격→busy→쿨다운→AGE)도 비용 관점에서 옳다. 질문 2("무제한 증식 통로")에 대해서는, append 경로 제거로 `(scope, root_key)` 당 생성률이 쿨다운 창당 1 run 으로 하드 바운드됐고 8초 tick 하에서도 그 상한은 깨지지 않는다 — 이 축은 실제로 봉인됐다고 본다. 질문 3(부분 갱신 누락)도 "시드 성공분만 전진 + 미시드는 후보 유지" 조합이 결정적 순서(`ORDER BY TABLE_NAME`)와 맞물려 누락 0 · 유한 수렴을 만든다.

문제는 남은 위험이 **"오탐" 이 아니라 "정탐인데 비용이 정당화되지 않는" 쪽으로 이동했다**는 점이다(B1). 스냅샷은 새 샤드를 정확히 '신규' 로 판정한다. 그러나 이 제품은 2026-07-03 사용자 결정으로 "동일 구조 샤드는 대표 1개만 LLM" 을 이미 확정했고, 그 결정의 근거는 지금 자동 경로가 재현하려는 바로 그 비용이다. 즉 변경 감지원을 바꾸는 것만으로는 부족했고, **비용 정책의 단위(개별 테이블 vs 구조 family)** 까지 기존 파이프라인과 맞췄어야 했다. 스냅샷 키를 테이블명이 아니라 `(base_stem, fp)` 그룹 서명으로 두면 B1 과 스냅샷 팽창(B3)이 동시에 줄어든다 — 재설계 비용도 크지 않다.

두 번째 도전: **`include_*` 플래그의 신뢰 모델이 축마다 비대칭**이다. 루틴 축은 "관측을 신뢰할 수 있는가" 를 `"routines" in _rt_sink` 라는 명시 신호로 표현했는데(좋은 설계), 테이블 축은 `bool(current_table_fps)` 라는 **결과의 비어있음** 으로 대신했다. 비어있음은 "관측 실패" 와 "진짜 0" 을 구분하지 못하고, `not all_table_names` 분기는 그 둘을 아예 후자로 단정한다(B2). 축별 baseline 플래그(`tb`/`rb`)라는 새 개념을 도입한 이상, "축이 켜져 있지만 이번 관측을 믿을 수 없다" 라는 **세 번째 상태**까지 모델에 넣어야 대칭이 완성된다. 지금은 루틴 축만 3-상태이고 테이블 축은 2-상태다.

세 번째: TCR.11 의 "구조를 전혀 바꾸지 않고 2 사이클 → candidates 0" 검증은 방향이 옳지만 **관측 창이 너무 짧다**. B1 은 하루 경계에서, B2 는 복원/마이그레이션 창에서만 드러나므로 2 사이클로는 둘 다 통과한다. shadow 모드를 **최소 1 영업일(샤드 생성 경계를 포함하는 기간)** 돌려 `auto_reanalysis_candidates` 의 일별 추이를 보는 것이 이 기능의 진짜 게이트다. 그리고 그 기간 동안 shadow→on 전환에 재배포가 필요하다는 점(C3)이 계획 자체를 실행 불가능하게 만들므로, C3 는 검증 계획의 선행 조건이다.

### 4. Verdict

BLOCK
