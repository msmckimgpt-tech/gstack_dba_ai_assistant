---
doc_type: TEST
feature_id: feature-0022-agent-scratch-workspace
status: active
edit_policy: append
source_of_truth: true
---

# Test

## 1. Test Contract
- **성공 조건**: (a) scratch guard 가 대화 스키마 밖 참조·cross-DB·위험 구문(COPY/SET)·위험
  함수·다중문을 차단하고 정상 DDL/DML/JOIN 은 통과. (b) 반입 타입 추론이 값 표본에서 올바른 PG
  타입을 도출. (c) 스키마명이 결정론적·안전(`s_<24hex>`). (d) 기능이 기본 OFF — 비활성 시 도구
  미노출. (e) 활성 시 4 도구 노출.
- **실패 모드**: guard 우회(cross-schema 누출)·타입 오추론으로 INSERT 실패·비활성인데 도구 노출.
- **복구 동작**: reaper 가 TTL 초과 스키마 DROP(자기치유); 전역 캡 도달 시 만료분 선정리 후 재확인.

## 2. Unit Tests (`tests/test_scratch.py` — feature-0002 tests 에 거주)
15 케이스, 라이브 DB 불필요(sqlglot 만):
- `schema_for` 결정론·형식·빈값 None.
- `infer_pg_type` — bigint/double/boolean/timestamptz/text·혼합·전부-null·bool+int.
- `_safe_ident`/`_dedupe_idents` — 식별자 안전화·선두숫자 fallback·63 캡·중복 제거.
- `scratch_guard` — 작업공간 조작 허용(SELECT/JOIN/CREATE/INSERT/UPDATE/DELETE/DROP/CTE/자기스키마
  자격) · cross-schema 차단(public/_scratch_admin/pg_catalog/information_schema/타-스키마) ·
  cross-DB catalog 차단 · 다중문 차단 · COPY/SET 차단 · 위험함수(pg_read_file/dblink/pg_sleep)
  차단 · 빈/파싱불가 deny.
- `enabled()` 기본 OFF · 비활성 시 `scratch_tool_defs()`=[] · 활성 시 4 도구 노출.

### Run log
- Run 2026-07-21 | Environment: docker(mysql-ai-agent:current) pytest | Result: **PASS (15/15)**
  — `test_scratch.py` 전건 통과. 회귀 대조: feature-0002 전체 RC=0, feature-0003 전체 RC=0.

## 3. Live / Integration (활성화 시 — deferred, TASK-0011)
- bootstrap→enable 후 라이브 e2e: 두 datasource 반입→`scratch_sql` JOIN→결과 확인→TTL 만료
  reaper DROP 확인. 대화 A/B 격리(A 스키마에서 B 테이블 SELECT 불가) 라이브 확인.
- **Environment: 백엔드/무-UI** — 본 cycle 은 web static/template/html/js/css 변경 0 이므로
  Windows-browser 시각검증(PB-0008, visual_verification_scope) 대상 아님(N/A).

## 4. Notes
- psycopg 미설치 dev 환경에서도 순수 로직·guard 는 검증 가능(모듈 lazy import). materialize/
  run_sql/reaper 의 라이브 PG 경로는 활성화 cycle 에서 검증.
