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

## 5. 분기(fork) 이월 + 작업공간 상태 주입 (2026-08-14, ADR-SCRATCH-0005)

### 5.1 Test Contract
- **성공 조건**: (a) 작업공간이 있는 대화를 분기하면 분기본 스키마에 원본 테이블이 **독립 사본**
  으로 존재한다(방향: 원본→분기본). (b) 캡(테이블 수·총 행수·시간 예산) 초과분은 이월하지 않되
  그 사실을 `truncated`/`skipped_detail` 로 드러낸다. (c) 테이블 1개 실패가 나머지 이월을 막지
  않는다. (d) 이월 실패가 분기 자체(대화·문맥·첨부)를 깨지 않는다(fail-soft, 예외 미전파).
  (e) 운영자 스위치 OFF·scratch 비활성·동일 대화·원본 빈 작업공간에서는 DB 를 건드리지 않는다.
  (f) 프롬프트에 실재 테이블 목록이 주입되고, 비었으면 EMPTY + 재반입 유도, 조회 실패면 침묵.
- **실패 모드**: 복사 방향 역전(분기본→원본 = 원본 오염)·무제한 복사(디스크 폭주)·전부-아니면-전무
  이월·이월 실패가 분기를 500 으로 만듦·"조회 실패" 를 "비어 있음" 으로 오도(assistant 가 멀쩡한
  테이블을 버리고 재반입).
- **복구 동작**: 이월 실패 시 분기본은 빈 작업공간으로 시작하고, 주입된 상태 문구가 assistant 에게
  재반입을 지시한다(품질 저하 대신 정직한 재작업).

### 5.2 Unit Tests (`tests/test_scratch.py`, +13 케이스 — 라이브 DB 불필요)
fake connection 으로 이월 계약을 고정한다:
- `clone_workspace` — 정상 복사(행수 합산·복사 방향) · carryover OFF no-op(DB 미접근) ·
  동일 대화 no-op · 원본 빈 작업공간에서 **분기본 스키마 미생성**(전역 캡 미소모) · 테이블 수 캡 ·
  행 예산 소진(LIMIT 반영) · 테이블 부분 실패 후 계속 · 연결 실패 fail-soft · scratch 비활성 no-op.
- `_scratch_workspace_state_note` — 실재 테이블 목록 표기(ANALYZE 전 음수 추정치는 행수 미표기) ·
  빈 작업공간 EMPTY 선언 + `scratch_import` 재반입 유도 · 조회 실패 시 빈 문자열(침묵).

### Run log
- Run 2026-08-14 | Environment: docker(mysql-ai-agent:current) pytest | Result: **PASS (38/38)**
  — `test_scratch.py` 전건 통과(기존 25 + 신규 13). 회귀 대조: feature-0003 전체 RC=0.
  feature-0002 전체는 RC=1 이나 실패 3건(`test_attachment_delivery_tool.py::test_materialize_
  signature_contract`, `::test_bind_tool_delivered_attachments_signature_contract`,
  `test_oauth_exhaustion_gate.py::test_write_failure_after_successful_post_cannot_kill_slot_
  selection`)은 **pre-existing 환경 결함**이다 — 컨테이너에 `chattr` 부재
  (`FileNotFoundError: 'chattr'`). 귀책 판별: 동일 이미지로 **main 체크아웃(repo/)** 을 마운트해
  같은 3건을 실행했을 때 **동일하게 실패**함을 확인했다(본 cycle 변경과 무관).
- **Environment: 백엔드/무-UI** — 본 cycle 은 web static/template/html/js/css 변경 0 이므로
  Windows-browser 시각검증(PB-0008, visual_verification_scope) 대상 아님(N/A). 변경 파일은
  `modules/scratch.py`·`agent_core.py`·`routers/_conv_store.py`·`routers/share.py`·
  `shared/runtime_settings.py` 로 전부 서버 코드다.

### 5.3 Live / Integration (배포 후)
- 작업공간이 있는 대화에서 사본 만들기 → 분기 응답 `scratch_cloned > 0` → 분기본 대화에서
  `scratch_list` 가 이월 테이블을 보여주고 `scratch_sql` 로 조회 가능.
- 공유 링크 fork(교차계정) → 이월 + `share.fork` 감사에 `scratch_tables_copied` 기록 확인.
- 작업공간 없는 대화 분기 → `scratch_cloned = 0`, 프롬프트에 EMPTY 상태 주입.
