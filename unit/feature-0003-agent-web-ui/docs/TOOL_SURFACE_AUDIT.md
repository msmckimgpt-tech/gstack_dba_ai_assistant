# 외부 AI 도구 사용 제한 감사 — 2026-09-08

요청: GZR 쿼리 리뷰 대화의 `search_routines` HTTP404와 도구별 사용 제한 확인·개선.
근거: 대화 …8c73806a의 core message 9248, 서버 코드/기존 스키마를 직접 대조했다.
현재 프로덕션 데이터는 SELECT로만 조사했다. 사용자 원문·자격증명·DB 정의는 문서에 싣지 않는다.

## 원인과 결과

core 정적 도구 15개와 조건부 6개 중 외부 dispatcher는 7개만 제공했다.
서버 프롬프트는 내부 도구를 쓰라고 안내했고 HTTP/MCP/러너가 서로 다른 목록을 관리했다.
이번 변경은 5개 조회 도구를 연결해 12개를 제공하고, 나머지 9개는 대체 경로와 제한 사유를 명시한다.
`get_tool_catalog`와 claim/get_task_context의 `tool_catalog`가 현재 목록·인자 규격·SQL 활성 상태를 반환한다.
명시적 allowlist로 공개를 결정하고 core JSON Schema로 인자를 채운다. 새 core 도구를 자동 공개하지 않는다.
MCP는 `run_read_tool`이 현재 서버 catalog를 확인한 뒤 전체 인자를 전달한다.
서버 시스템 지침에도 계약을 추가하여 설치된 구버전 러너가 지원 목록을 알 수 있게 한다.

| core 도구 | 외부 상태 / 사용 경로 |
|---|---|
| list_schemas | 유지. database/datasource 선택 가능 |
| describe_schema | 유지. database/datasource 선택 가능 |
| describe_table | 유지. database/table_name 전달 가능 |
| search_tables | 유지. database/schema_name 전달 가능, MySQL 생략 검색 범위 보강 |
| get_foreign_keys | 유지. database/table_name 전달 가능 |
| get_table_indexes | 유지. database/table_name 전달 가능 |
| execute_sql | 유지. 단일 SELECT/CTE·운영 스위치·행수/원장·부하 가드 적용, confirm_heavy 인자 전달 가능 |
| search_routines | 신규 연결. 이름·본문 검색, 허용 DB만 검색 |
| describe_routine | 신규 연결. database/offset으로 대상 DB·본문 이어읽기 |
| search_db_objects | 신규 연결. view/trigger/schedule/alias/generator 검색 |
| describe_db_object | 신규 연결. 대상 객체 정의/속성과 offset 이어읽기 |
| explain_query | 신규 연결. 본문 실행 없이 추정 계획, 동일 단일 읽기 전용 AST 검증 선행 |
| get_sample_rows | 제한 유지. execute_sql의 제한된 SELECT로 대체(추출 예산 우회 금지) |
| check_table_coverage | 제한 유지. 내부 첨부 ContextVar 필요. read_task_attachment + describe_schema 대조 |
| graph_navigate | 제한 유지. 전역 KB 그래프 경로. 제품 범위 get_task_context(focus=...)로 대체 |
| read_attachment | 일반 dispatcher 제한 유지. 웹 task의 read_task_attachment 전용 경로 |
| update_attachment | 일반 dispatcher 제한 유지. 최종 answer의 attachment-edit + submit_answer로 저장 |
| scratch_import | 내부 첨부 분석 상태 도구, 제한 유지 |
| scratch_sql | 내부 첨부 분석 상태 도구, 제한 유지 |
| scratch_list | 내부 첨부 분석 상태 도구, 제한 유지 |
| scratch_reset | 내부 첨부 분석 상태 도구, 제한 유지 |

기존 이름별 MCP wrapper는 호환을 유지한다. wrapper가 표현하지 못하는 database/offset/confirm_heavy는
run_read_tool의 arguments로 전달한다. 웹 task 첨부 읽기는 현재 점유자·client·대화·lease 가드를 그대로 탄다.
신규 첨부는 attachment-new(JSON 헤더 filename), 갱신은 attachment-edit(JSON 헤더 source_attachment_id) 블록이다.

## 실패별 판정

- search_routines: 코드에 구현돼 있어도 외부 allowlist 누락으로 404. 현재 scoped dispatcher 도달 검증.
- update_attachment: 일반 내부 도구명과 외부 저장 경로의 차이. 없는 도구 호출 지시 대신 실제 저장 경로 전달.
- DB_NAME(): 의도적인 metadata function 차단. 금지를 해제하지 않고 검색 결과 database와 list_schemas(database=...)로 확인하도록 안내.
- 해당 대화의 task 6개를 task_id로 원장과 연결: 132호출(첨부읽기65·테이블설명36·SQL9·테이블검색6·인덱스3·스키마설명1·claim6·제출6).
  원장 outcome=ok는 HTTP 전달 상태이며 SQL 결과 안의 가드 거부까지 성공으로 해석하지 않는다.
  404는 실행 이전이라 원장에 없으므로 assistant 발언+실제 allowlist+HTTP 회귀 재현으로 원인을 확인했다.

## 노출 전 보안 결함 수정

MySQL 검색은 허용 스키마별 질의로 LIMIT 이전에 범위를 제한한다. 공백/구분자만 있는 입력도 동일 적용한다.
작업 생성 이후 제품/대화 권한 회수를 실행 시점에 다시 확인한다.
SQL Agent 검색은 반환 단계뿐 아니라 키워드 검색 단계에도 같은 DB 제한을 적용하며 DB명 리터럴을 변형하지 않는다.
실행계획 입력도 동일 readonly AST 가드를 통과해야 하므로 SHOWPLAN 해제 다중문·쓰기·금지함수는 실행 전에 거부한다.
인증 방식·OAuth scope·RBAC·데이터소스 바인딩·SQL metadata 금지는 변경하지 않았다.

## 검증 경계

집중 테스트·MCP 1/2 SDK 실행·패널 결과와 배포 검증은 test-runs.d/TASK-20260908T162000-tool-surface.md를 참조한다.
기존 첨부 수정의 배포 후 해당 대화 신규 assistant 턴은 0개다. 재발/소멸 판정 근거가 아직 없으며 이전 fixed:deployed:unverified-live를 유지한다.
새 사용자 AI 답변 생성·실제 DQA 창은 별도 실측 항목이다. 운영 대화/첨부를 변경하지 않는다.

## 배포 후 확인

PR #1635 / ca3fe660 전체 7서비스 배포 완료. 회귀717 PASS, 배포본 계약56 PASS, 실제 계정/제품 범위 catalog 조회200·미허용 datasource403·첨부 대체경로 안내를 확인했다.
실제 프로시저 검색은 누락404를 통과했지만 대상 SQL Server 접속 timeout으로500을 반환했다. 기존 버전 워커와 호스트 TCP도 동일 실패하여 배포로 인한 도구 제한과 분리했다. 네트워크/DB 서버 원인은 미확정이며 실제 정의·객체·계획 조회 성공을 주장하지 않는다.
17:19 KST 원장 재측정에서 해당 대화의 배포 후 신규 assistant0; 사용자 AI 재검증은 미수행. 상태 fixed:deployed:unverified-live.
