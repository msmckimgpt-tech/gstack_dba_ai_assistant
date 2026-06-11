---
doc_type: DECISIONS
feature_id: feature-0002-agent-core
status: active
edit_policy: append-only
source_of_truth: true
---

# Feature Decisions

## ADR-CORE-0001
- Date: 2026-03-26
- Decision: import 구조를 유지하기 위해 agent 이미지는 core와 web-ui 코드를 함께 포함한다
- Consequence: 실행 안정성은 높지만 build context가 루트 경로를 사용한다

## ADR-CORE-0002
- Date: 2026-06-10 (멀티 datasource 설계 cycle)
- Context: assistant(`execute_sql` 도구)·insight_worker 가 **단일 MySQL** 만 분석한다. "단일 MySQL" 가정이 3계층(드라이버 `db.connect()`→`mysql.connector`, 단일 전역 DB_* env, tools.py·insight.py 의 MySQL 방언 직접 생성)에 하드코딩됨. 사용자는 **여러 datasource(엔진: MySQL·MSSQL) 동시 운용**(대화/질의별 선택)을 원한다. MSSQL(T-SQL)은 식별자 인용(대괄호)·TOP·`sys.*` 카탈로그·EXPLAIN 부재 등 방언이 크게 달라 설정 토글이 아닌 구조 변경이며, 데이터 접근 경계·자격증명·RBAC·SQL guard 를 모두 건드리는 **Critical**(§12.3).
- Options: (A) 네이티브 dialect-adapter — `Dialect` ABC + MySQL/MSSQL 2종 구현, db.py 드라이버 디스패치, sql_guard 에 sqlglot dialect 주입. 기능 패리티(EXPLAIN 게이트·풀·RO 라우팅·CSV 미리보기) 유지, 고비용. (B) dbhub MCP 경유 — 드라이버는 쉽게 풀리나 본 프로젝트의 보안 게이트(SQL guard·EXPLAIN·RO·차단스키마)를 우회 → 분석 주경로 부적합. (C) 즉시 구현 — Critical 인데 설계 없이 코딩, 비권장.
- Decision: **A(네이티브 dialect-adapter) 채택 + 설계만 먼저**(사용자 결정 2026-06-10). `docs/DESIGN-multi-datasource.md` 에 datasource 레지스트리·드라이버 디스패치·Dialect 인터페이스·SQL guard 멀티방언·LLM grounding 주입·insight per-datasource·RBAC/시크릿·6단계 롤아웃을 기록. **구현 안 함** — 자체 다중 cycle + `/plan-eng-review` + RBAC outside-voice 통과 후 단계 착수(ask-worker ADR-WEB-0004 와 동일 "설계 먼저" 패턴). 유리한 전제: 제어/데이터 평면 seam(`db_str != MEMORY_DB`)·sqlglot 멀티방언 guard·시그니처 기반 풀 키·데이터평면 RO 유저 패턴이 이미 존재.
- Consequence: 멀티엔진 분석 경로의 구조가 정본화돼 단계 구현이 가능. 미해결(plan-review 확정 대상): MSSQL 드라이버(pyodbc vs pymssql), 시크릿 전략(.env named vs app 암호화), SQLAlchemy Core 채택 범위, MSSQL 부하게이트(추정계획 파싱 vs LIMIT+timeout fail-safe), 대화 중 datasource 전환 허용. 구현 전까지 단일 MySQL 동작 무변경.

## ADR-CORE-0003
- Date: 2026-06-10 (멀티 datasource 롤아웃 시퀀싱 결정)
- Context: TASK-0183 의 plan-eng-review + Codex cross-model 리뷰(REV-20260610-0183)가 ADR-CORE-0002 설계의 P0~P6 롤아웃에서 세 가지 시퀀싱 결정을 미해결로 남김(DESIGN §4 Q6/Q7/Q8): (Q6) P1 을 MySQL-only 로 먼저 vs MySQL+MSSQL 동시, (Q7) 보안경계를 연결 디스패치보다 먼저 vs 나중(Codex-4 BLOCKER), (Q8) 전체 scope 한 번에 vs 더 싼 경로(Codex-9). 플러밍(레지스트리/바인딩/RBAC)과 MSSQL 방언+보안 재작성은 실패 모드가 전혀 다름.
- Options: (Q6/Q8) multi-MySQL 먼저 / MySQL+MSSQL 동시 / MSSQL 별 서비스. (Q7) 보안경계 연결과 동시 / admin-only flag 후 RBAC.
- Decision (사용자 결정 2026-06-10): **(Q6/Q8) multi-MySQL 먼저** — Stage 1(P1~P3)은 MySQL 전용 멀티-datasource(레지스트리·바인딩·RBAC·UI·insight), MSSQL 방언/보안은 Stage 2(P4~P7, RBAC outside-voice 재게이트)로 분리(= Codex-9 더 싼 경로). **(Q7) 보안경계 연결과 동시(security-first)** — datasource 접근 RBAC + datasource-스코프 allowlist + per-datasource RO 자격증명이 연결 디스패치와 같은 증분(P1)에. flag 는 권한검사를 대체하지 않음(Codex-4). admin-only flag 우회안 기각.
- Consequence: DESIGN §5 가 Stage 1(multi-MySQL, 방언/MSSQL 보안 재작성 위험 0) + Stage 2(MSSQL, Critical) 로 재구성. 첫 출하가 "여러 MySQL 타깃"이라는 사용자 가치를 빠르게 전달하며, MSSQL 의 Critical 보안 재작성은 격리된 별 cycle 로. Stage 1 도 datasource 선택이 인가 결정이므로 보안경계 동반. 잔여 미해결(Stage 2 진입 시): §4 Q1~Q5(MSSQL 드라이버·시크릿·SQLAlchemy·부하게이트·대화중 전환).

## ADR-CORE-0004
- Date: 2026-06-11 (멀티 datasource 1:N — 제품 ↔ 여러 datasource, TASK-0230)
- Context: ADR-CORE-0002/0003 이후 멀티 datasource(여러 엔진)는 구현됐으나 **product ↔ datasource 는 1:1**(`WebProducts.DatasourceKey` 단일 컬럼)이었다. 사용자 요청 = 한 제품이 **여러 datasource·DB 를 참조**해 assistant 가 한 질문에서 교차 조회. 이는 설계 문서에 없던 새 차원이며, datasource 접근 경계(= 인가 결정)를 datasource 별로 분리해야 하는 Critical 작업.
- Options: 런타임 노출 방식 — (A) 자동 union 스캔(전 datasource fan-out, N배 비용·교차노출 위험), (B) 대화별 단일 datasource 선택기(안전하나 한 질문 교차 불가), (C) **LLM 이 tool 인자로 datasource 선택**(진짜 교차 참조, 구현 최대). 바인딩 저장 — 기존 `DatasourceKey` 컬럼 확장(JSON) vs **정규화 join 테이블**.
- Decision (사용자 결정 2026-06-11): **전체 구현 + (C) LLM tool 선택** 채택. ① 바인딩 = `WebProductDatasources(ProductId, DatasourceKey, IsPrimary, SortOrder)` 정규화 join 테이블 — `WebProducts.DatasourceKey` 는 **primary 포인터로 유지**(기존 resolve/insight 경로 무수정·하위호환). 단일 바인딩(0~1)은 기존 단일 경로 byte-identical. ② 런타임 = `_DatasourceRouter`(tools.py) 가 tool 호출마다 datasource 를 선택해 **연결·스키마 allowlist·dialect 를 단일 라벨로 lockstep 활성화**(격리 불변식). ③ 접근DB(`WebProductDatabases`)에 `DatasourceKey` 차원 추가 — datasource 별 allowlist 격리(A 의 DB 가 B 컨텍스트로 안 샘). ④ 제품 프롬프트 자동작성 + 런타임 grounding 이 모든 바인딩 datasource 의 DB 인지(사용자 추가 요청). flag `AGENT_MULTI_DATASOURCE_ENABLED` 뒤 shadow.
- Consequence: 한 제품이 여러 datasource(MySQL/MSSQL 혼합 가능)를 참조하고 assistant 가 한 대화에서 교차 분석. 격리는 ContextVar(allowlist·engine) 를 datasource 별로 단일 단위 전환하는 것으로 보장 — outside-voice 적대 리뷰(REV-20260611-0230) 가 cross-datasource leak 없음 확인(연결·allowlist 단일 라벨 활성·tool 순차·게이트는 항상 활성 datasource 것), fail-closed 폴백(차원 컬럼 부재 시 접근 0)으로 partial-migration leak 차단. datasource 간 직접 JOIN 은 불가(각각 조회 후 결과 합산). 잔여: 멀티 바인딩 제품 라이브 end-to-end(운영자), datasource 간 페더레이션 쿼리(범위 외).
