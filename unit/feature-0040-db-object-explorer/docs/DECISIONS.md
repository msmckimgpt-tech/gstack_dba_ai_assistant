---
doc_type: DECISIONS
feature_id: feature-0040-db-object-explorer
status: active
edit_policy: append-only
source_of_truth: true
---

# Decisions

## ADR-20260812T030000-db-object-role-axis — 벤더 객체명이 아닌 **역할**을 분류 축으로 채택

- **맥락**: 사용자가 "궁극적으로 모든 DB 시스템에 대응 · 수행되는 역할에 따라 분류" 를 지시.
- **결정**: `view`/`trigger`/`schedule`/`alias`/`generator`(+기존 `routine`) 6역할을 고정
  축으로 두고, `Dialect` 하위클래스가 자기 방언의 구현체를 매핑한다.
- **근거**: 벤더축은 DBMS×객체로 도구가 곱해지고, 같은 역할의 객체가 이름만 달라 모델이
  "이 DB 엔 이벤트가 없다"(실제로는 Agent 작업으로 존재) 로 오판한다.
- **결과**: 도구 표면 2개 고정. 신규 DBMS = `Dialect` 하위클래스 매핑 선언만.

## ADR-20260812T030100-db-object-support-states — 지원상태 4종 (미지원 ≠ 부재)

- **맥락**: `FR-false-absence-zero-row-catalog-scope` 가 관측한 허위 부재가 역할 단위로
  재발할 수 있다(MySQL 에 시노님 개념 자체가 없어 0행).
- **결정**: `SUPPORTED`/`UNSUPPORTED`/`PRIVILEGED`/`DELEGATED` 4상태를 타입 레벨로 두고,
  안내문 생성을 `db_object_roles` 단일 지점이 소유한다.
- **근거**: 호출측이 각자 문구를 지으면 그중 하나가 반드시 "없습니다" 로 새고, 그 한 번이
  곧 허위 부재다.
- **결과**: `DELEGATED` 는 base 클래스가 `OWNED_ELSEWHERE` 로 선점 처리 — 하위클래스가
  누락해도 거짓이 나올 수 없다(초판 결함의 구조적 봉인).

## ADR-DBOBJ-0001 (ADR-20260812T030200-routine-stays-in-routine-objects) — `routine` 은 이관하지 않는다

- **맥락**: taxonomy 는 6역할을 선언하지만 저장은 `routine_objects`(0034)와 `db_objects`(0054)
  두 테이블로 나뉜다.
- **결정**: `routine` 의 저장·투영은 기존 경로가 계속 소유하고, 본 기능은 나머지 5역할만
  수집한다.
- **근거**: 이관의 이득은 개념적 정결함뿐이고, 대가는 라이브에서 검증된 그래프 투영·
  능동 분석·크로스-DB 참조 파싱을 관통하는 회귀 위험이다.
- **결과**: 경계를 `OWNED_ELSEWHERE` + `DELEGATED` 로 명시해 두 벌 관리의 함정을 차단.

## ADR-20260812T030300-object-on-vs-object-uses — 소유 관계를 별 엣지로 분리

- **결정**: 트리거의 대상 테이블·별칭의 대상은 `OBJECT_ON`(파선), 정의가 참조하는 테이블은
  `OBJECT_USES`(실선)로 **분리 투영**한다.
- **근거**: 합치면 "이 테이블에 뭐가 걸려 있나" 를 답할 수 없다 — 그 테이블을 읽기만 하는
  다른 객체와 구별 불가가 된다.
- **결과**: 그래프 집계 키에도 엣지 타입을 포함해 루틴 사용선과 병합되지 않게 했다.

## ADR-20260812T030400-msdb-narrow-read — Agent 작업은 고정 질의 한 곳으로만 읽는다

- **맥락**: `msdb` 는 `system_databases()` 소속으로 freeform 하드 차단 대상인데, Agent 작업
  메타데이터가 거기 있다.
- **결정**: `MSSQLDialect._agent_jobs_sql` **단일 함수**가 4개 뷰의 고정 조인·고정 컬럼
  투영으로만 읽고, 외부 입력은 `keyword`/`name`/`allow_dbs`/`schema` 로 제한한다. 제품
  경계는 단계의 `database_name` ∈ 허용 DB 로 강제하며 빈 목록은 fail-closed.
- **근거**: freeform 의 msdb 차단을 유지하면서 필요한 메타데이터만 여는 최소 표면.
- **결과**: `database_name` 이 빈 단계(CmdExec/PowerShell 등 OS 레벨)는 자동 제외되며,
  그 사실을 caveat 으로 고지해 부재로 오독되지 않게 한다.
