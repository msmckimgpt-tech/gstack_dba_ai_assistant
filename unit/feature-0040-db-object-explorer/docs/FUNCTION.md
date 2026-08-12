---
doc_type: FUNCTION
feature_id: feature-0040-db-object-explorer
status: active
edit_policy: rewrite
source_of_truth: true
---

# Function

## 1. Summary

assistant 가 DB 내부 구조를 탐색할 때 **테이블·컬럼·인덱스·FK·루틴 외의 실제 객체**
— 트리거, 이벤트/SQL Server Agent 작업, 뷰, 시노님, 시퀀스 — 를 조회할 수 있는 도구를
제공하고, 같은 객체를 **그래프 뷰에도 배치·참조·분석 대상으로 편입**한다.

핵심 설계는 **역할(role) 기반 분류**다. 벤더마다 같은 일을 하는 객체의 이름이 다르므로
(시간표 자동 실행 = MySQL `EVENT` / SQL Server `Agent Job` / PostgreSQL `pg_cron` /
Oracle `DBMS_SCHEDULER`), 벤더 객체명을 축으로 삼으면 DBMS 를 추가할 때마다 도구·그래프·
프롬프트의 어휘가 갈라진다. 역할을 고정 축으로 두고 벤더 객체를 그 역할의 구현체로
매핑하면, 축이 DBMS 수와 무관하게 유지되고 신규 DBMS 는 `Dialect` 하위클래스가 매핑만
선언하면 된다.

## 2. Goal

- REQ-20260812-db-object-explorer: assistant 가 트리거·이벤트·Agent 작업 등 실제 DB 객체를
  탐색할 수 있는 도구를 제공한다.
- REQ-20260812-db-object-graph: 그 객체들을 그래프 뷰에서 배치·참조·분석할 수 있게 한다.

### 완료 판정 기준 (Done when)

- [x] 역할 미지정으로 `search_db_objects` 를 호출하면 지원되는 전 역할이 한 번에 열거된다.
- [x] MySQL 에 `alias` 를 물으면 "0건" 이 아니라 "이 DBMS 에 개념이 없음" 으로 응답한다.
- [x] `routine` 을 물으면 "지원하지 않음" 이 아니라 `search_routines` 로 재라우팅된다.
- [x] 권한 의존 역할(트리거·이벤트·Agent 작업)은 결과 유무와 무관하게 권한 모호성을 고지한다.
- [x] 그래프 뷰에서 역할 객체가 스키마 클러스터에 테이블·루틴과 나란히 렌더된다.
- [x] 역할별 표시 토글(뷰/트리거/예약/별칭/시퀀스)이 노드와 그 엣지를 함께 숨긴다.
- [x] 트리거의 대상 테이블은 `OBJECT_ON`(소유), 정의 참조는 `OBJECT_USES` 로 **구분** 투영된다.
- [x] DB 단위 AI 능동 분석 시드에 역할 객체가 포함된다.

## 3. In Scope

- **역할 taxonomy** (`modules/db_object_roles.py`) — 6역할 선언 + 지원상태 4상태
  (`SUPPORTED` / `UNSUPPORTED` / `PRIVILEGED` / `DELEGATED`) + 벤더·한국어 어휘 정규화.
- **방언 매핑** (`modules/dialects.py`) — MySQL·SQL Server 의 역할별 카탈로그 질의.
- **assistant 도구** — `search_db_objects`(열거·검색) · `describe_db_object`(정의·속성).
- **SSOT** — `db_objects` 테이블(alembic 0054) + `modules/db_objects.py` introspection.
- **그래프 투영** — AGE vlabel `DbObject` + elabel `HAS_OBJECT`/`OBJECT_USES`/`OBJECT_ON`.
- **그래프 뷰 UI** — 구리 칩·역할 아이콘·역할별 kind 필터·상세 패널 속성·범례.
- **AI 능동 분석 편입** — 스키마 단위 시드에 역할 객체 포함(사용자 결정 2026-08-12 축2).

## 4. Out of Scope

- **`routine` 의 저장 이관** — feature-0016 ADR-016 의 `routine_objects` 가 계속 소유한다.
  taxonomy 는 6역할을 선언하되 저장은 두 테이블로 나뉜다(ADR-DBOBJ-0001).
- **change-reanalysis 3축 확장** — 변경 감지 스냅샷은 테이블·루틴 2축 모델이라 역할 객체
  축 추가는 스냅샷 스키마·신뢰 판정 동반 변경이 필요하다. 후속 cycle 로 이연(TASK §2 잔여).
- **PostgreSQL·Oracle 방언 구현** — 역할 축과 `Dialect` API 는 이미 그것을 수용하도록
  설계됐으나, 실제 하위클래스는 그 DBMS 를 지원하는 시점에 추가한다.
- **DDL 변경 제안·실행** — 본 기능은 read-only 탐색·표시 전용이다.

## 5. Inputs

- 데이터소스 카탈로그(read-only): MySQL `information_schema.{VIEWS,TRIGGERS,EVENTS}`,
  SQL Server `sys.{views,triggers,synonyms,sequences,sql_modules,trigger_events}` +
  `msdb.dbo.{sysjobs,sysjobsteps,sysjobschedules,sysschedules}`.
- 제품 접근 allowlist(서버 스코프 객체의 경계 필터).

## 6. Outputs

- 도구 응답(마크다운 표 + 정의 본문 + 필수 고지).
- `db_objects` SSOT 행 · AGE `DbObject` 정점/엣지 · 그래프 뷰 노드·엣지·상세 패널.

## 7. Behavior

### 7.1 역할 6종과 방언 매핑

| role | 수행하는 일 | MySQL | SQL Server |
|---|---|---|---|
| `routine` | 호출되어 실행 | PROCEDURE/FUNCTION *(전용 도구)* | 동일 *(전용 도구)* |
| `view` | 저장된 질의가 테이블처럼 조회됨 | VIEW | VIEW |
| `trigger` | 데이터/DDL 변경에 반응해 자동 실행 | TRIGGER | DML/DDL TRIGGER |
| `schedule` | 시간표에 따라 자동 실행 | EVENT | **Agent Job** |
| `alias` | 다른 객체를 가리키는 이름 | (없음) | SYNONYM |
| `generator` | 값을 순차 생성 | (없음)¹ | SEQUENCE |

¹ `AUTO_INCREMENT` 는 컬럼 속성이지 독립 객체가 아니다.

### 7.2 지원상태 4종 — 미지원 ≠ 부재 (핵심 불변식)

| 상태 | 의미 | 응답 |
|---|---|---|
| `SUPPORTED` | 조회 가능 | 0행 = 진짜 0개 |
| `UNSUPPORTED` | 이 DBMS 에 개념 자체가 없음 | **"0건" 이 아니라 "해당 없음"** |
| `PRIVILEGED` | 권한에 따라 보이는 범위가 다름 | 결과와 **같은 응답**에 모호성 고지 |
| `DELEGATED` | 지원되나 전용 도구가 따로 있음 | 거부가 아니라 그 도구로 재라우팅 |

이 구분이 본 기능의 존재 이유다 — 구분하지 않으면 "MySQL 에 시노님이 0건" 을 모델이
"이 DB 에 시노님이 없다" 로 서술한다(`FR-false-absence-zero-row-catalog-scope` 와 동형).

### 7.3 SQL Server Agent 작업의 두 가지 비대칭

1. **저장 위치가 DB 밖** — 작업은 `msdb`(시스템 DB, freeform 하드 차단 대상)에 있다.
   구조화 도구는 `Dialect._agent_jobs_sql` 한 곳에서 **컬럼 투영·조인·필터를 코드로 고정**해
   읽는다. freeform 의 `msdb` 차단은 불변이며 이 경로가 우회로가 되지 않는다.
2. **제품 경계 귀속** — 작업 자체엔 소속 DB 가 없고 **단계의 `database_name`** 이 대상이다.
   허용 DB 를 대상으로 하는 단계가 있는 작업만 노출하고 그 DB 를 schema 슬롯에 넣는다.
   `database_name` 이 빈 단계(CmdExec/PowerShell 등 OS 레벨)는 매칭되지 않아 **자동 제외**
   되며(fail-closed), 그 사실을 도구가 caveat 으로 고지한다.

### 7.4 그래프 투영 — OBJECT_ON 과 OBJECT_USES 의 분리

- `OBJECT_ON` (파선) — 트리거가 **걸린** 테이블 · 별칭의 **대상** 객체.
- `OBJECT_USES` (실선) — 정의가 **참조**하는 테이블(read/write).

합치면 "이 테이블에 뭐가 걸려 있나" 를 답할 수 없다 — 그 테이블을 읽기만 하는 다른
객체와 구별 불가가 되기 때문이다.

## 8. Constraints

- **read-only**. 카탈로그 조회만 하며 DDL/DML 을 수행하지 않는다.
- 스키마 접근 경계는 기존 구조화 도구와 동일(`_struct_schema_access_error` ·
  `_mssql_pin_gate` · 허용 DB 목록). 내부 DB(`agent_memory`)는 allowlist 무관 영구 차단.
- **별칭 대상 마스킹** — 시노님의 `base_object_name` 이 허용 범위 밖 DB·원격 서버를
  가리키면 **이름을 노출하지 않는다**(존재만 알린다). `sys.synonyms` 가 freeform
  화이트리스트에서 제외된 사유를 구조화 경로에서도 지킨다.
- 수집(SSOT)과 조회(도구)는 **의존이 분리**돼 있다 — `AGENT_DB_OBJECT_INTROSPECT_ENABLED=0`
  이어도 도구는 라이브 카탈로그를 직접 보므로 계속 동작한다.

## 9. Errors

- 조회 실패(권한·연결)는 **"없음" 으로 보고하지 않는다** — "미확인" 으로 명시한다.
- 표시 상한 포화는 "더 있습니다" 로 표면화한다(무음 절단 금지, §16.7 G9-b).
- 정의 본문이 비면 "권한 없을 수 있음 / **정의가 비어 있다는 뜻이 아님**" 을 명시한다.

## 10. Dependencies

- feature-0016 (metadata-graph) — AGE 그래프·그래프 뷰·node_analysis.
- feature-0002 (agent-core) — 도구 레이어·dialect·insight worker (코드 거주).
- feature-0003 (agent-web-ui) — 그래프 뷰 프론트 자산 (코드 거주).

## 11. Open Questions

- change-reanalysis 3축 확장 시점(현재 2축 — 위 Out of Scope 참조).
- PostgreSQL 방언 추가 시 `RULE`·`EVENT TRIGGER` 를 `trigger` 역할에 합칠지, 별 역할로
  분리할지 — 실제 지원 시점에 결정.

## 12. Pre-approved Changes

- 비파괴 스키마 추가(신규 테이블·AGE 라벨)는 사전 승인 범위.
- deploy_scope 는 `FIRST_REQUEST.md` 전역 선언(`included`)을 따른다.
