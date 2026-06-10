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
