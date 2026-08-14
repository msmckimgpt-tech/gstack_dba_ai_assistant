---
doc_type: REVIEW
feature_id: feature-0022-agent-scratch-workspace
status: active
edit_policy: append
source_of_truth: true
---

# Review

## REV-20260721T073500-agent-scratch-workspace [SUBAGENT: security] — Verdict: PASS (after fixes)

**Scope**: feature-0022 agent PG scratch workspace — 격리·권한 경계 적대적 보안 리뷰
(§18.8, fresh-context subagent, 목표=결함 적발). 대상: scratch.py(guard·materialize·run_sql·
reaper) · agent_scratch_schema.sql · scratch-pg-bootstrap.sh · tools.py scratch 핸들러 4종 ·
db._pg_connect_scratch · config AGENT_SCRATCH_*.

**핵심 발견 → 조치**:
- **[BLOCK] CREATE FUNCTION 문자열 본문 우회** — 초기 denylist guard 는 `Create` 노드를 통과시켜,
  함수 본문(문자열 리터럴)에 은닉된 cross-대화 스키마 read/write/drop 이 가능했다(모든 s_* 가 동일
  role 소유 → 대화 격리 붕괴). → **guard 를 allowlist 로 반전**: 허용 root(Select/With/SetOp/
  Insert/Update/Delete/TruncateTable + CREATE·DROP 은 kind∈{TABLE,INDEX}) 만 통과, FUNCTION/
  PROCEDURE/VIEW/TRIGGER/DO/CALL/EXTENSION/Command 전면 거부. CTAS/INSERT 본문의 cross-schema
  참조는 AST 로 노출돼 차단. **FIXED + 회귀 테스트**(test_guard_blocks_function_body_bypass 등).
- **[HIGH] pg_catalog 무자격 참조 열거** — `SELECT FROM pg_class/pg_namespace` 로 타 대화 스키마/
  컬럼 열거 가능(무자격이라 db-qualifier 검사 우회). → 테이블명·함수명 **`pg_` 접두 전면 차단**
  + materialize 도 pg_ 접두 반입 테이블명 회피. **FIXED + 회귀 테스트**(test_guard_blocks_pg_catalog_enumeration).
- **[MEDIUM] CONNECT 격리 문서 과장** — "grant 0 → 물리적 도달 불가"는 부정확(role 은 PUBLIC 멤버
  라 sibling DB CONNECT 잔존; 현 시점 미악용). → 문서를 실제 메커니즘(non-superuser + dbname 고정
  + PG cross-DB 불가 + 무-grant)으로 정정 + `--harden-kb-isolation` 을 sibling DB(agent_runtime/
  agent_memory/web) 로 확대(opt-in). **FIXED**.
- **[MEDIUM] scratch_import heavy-query 게이트 누락** — execute_sql 의 AGENT_QUERY_GUARD_MODE 부하
  게이트가 없어 대량 반입 우회 가능. → scratch_import 에 동일 게이트(gate 차단/warn 경고 +
  confirm_heavy override) 추가. **FIXED**.
- **[LOW]** 약한 기본 비밀번호(opt-in·경고 뒤)·_rt fail-open 방향(OFF 기본=fail-safe) — 조치 불요.

**리뷰어가 확인한 막혀 있는 벡터**: 직접 cross-schema/cross-DB 참조(모든 분기 db/catalog 검사),
다중문, materialize 식별자 주입(sql.Identifier+_safe_ident), search_path pin, reaper DROP 대상
s_* 정규식 한정, conversation_id ContextVar finally 해제(스레드 재사용 stale 없음), enabled 기본
OFF 이중 게이트.

**잔여(accepted with mitigation)**: 모든 s_* 가 동일 role 소유 → PG 레벨 대화 격리 부재. 현재는
scratch_guard(allowlist)+search_path 가 격리를 강제한다. 근본 강화(대화별 전용 role)는 TASK-0013
후속으로 이월(DECISIONS ADR-SCRATCH-0002 잔여 위험 항목).

**검증**: test_scratch.py 20건 PASS(하드닝 guard 회귀 5건 포함). feature-0002/0003 전체 회귀 0.

## REV-20260721T090000-scratch-guidance [SKIPPED: minor] — Verdict: PASS
**Scope**: follow-up — (a) scratch 사용 guidance 프롬프트 주입(`_SCRATCH_WORKSPACE_GUIDANCE`, 활성 시
조건부·비활성 무증가) (b) bin/scratch-pg-bootstrap.sh superuser 결함 수정(전용 superuser override +
unix 소켓 trust 연결).
**왜 SKIPPED(패널 생략)**: 신규 런타임 공격 표면 0 — (a) 는 프롬프트 텍스트(도구 실행 게이트·scratch_guard
불변, 이미 REV-…073500 에서 적대 검증 완료), (b) 는 운영 bootstrap 스크립트의 연결 자격 해석 수정
(런타임 데이터 경로 무관, superuser 소켓 trust 는 기존 kb bootstrap 과 동형). Minor·behavior-additive.
**검증**: test_scratch.py 21건 PASS(guidance sanity 포함), feature-0002/0003 회귀 0, bash -n PASS,
활성화 라이브 스모크(별도).

## REV-20260721T093000-scratch-runsql-fix [SKIPPED: minor-bugfix] — Verdict: PASS
**Scope**: 라이브 활성화 스모크가 적발한 `run_sql` 버그 수정 — `SET statement_timeout = %s`(psycopg
파라미터)를 PostgreSQL 이 불허(SET 값 바인딩 불가)해 모든 scratch_sql 이 실패하던 것을 int 인라인
(`_statement_timeout_sql()`)으로 수정.
**왜 SKIPPED**: 단일 SQL 구문 버그 수정 — 신규 공격 표면 0(int() 강제 인라인, 주입 불가), scratch_guard/
격리/materialize 불변. 라이브 psql 시퀀스로 수정 검증(SET+JOIN 정상) + placeholder-free 회귀 테스트.
**검증**: test_scratch.py 22건 PASS, agent_scratch_rw 직접 `SET statement_timeout=30000`+JOIN 정상,
배포 후 라이브 end-to-end 재스모크로 최종 확인.

## REV-20260722T022416-scratch-sql-table [SKIPPED: minor-ux] — Verdict: PASS
**Scope**: 라이브 사용 피드백 — `scratch_sql` 결과셋 출력이 plain-text(` | ` 나열)라 기존 execute_sql
표 형식과 불일치. `_format_result_sets`(execute_sql 표 포매터) 재사용으로 통일 + 죽은 `_fmt_scratch_rows` 제거.
**왜 SKIPPED**: 출력 문자열 포맷 변경만 — 데이터 경로·scratch_guard·격리·권한 불변, 신규 공격 표면 0.
동일 포매터 재사용이라 절단/미리보기 캡 정책도 execute_sql 과 자동 일치.
**검증**: test_scratch.py 23건 PASS(표 마크다운 회귀 포함), 샘플 출력 육안 확인(`| col |`+구분선+footer),
배포 후 라이브 재확인.

## REV-20260814T031500-scratch-fork-carryover [SKIPPED:session-policy-no-subagent] — Verdict: PASS
**Scope**: 대화 분기 시 assistant 작업공간(scratch) 유실 구조 결함 해소 — 분기 3 경로 공통 이월
(`clone_workspace`, 독립 CTAS 복사) + 작업공간 실제 상태의 매-턴 프롬프트 주입. ADR-SCRATCH-0005.
**왜 SKIPPED**: 본 세션은 사용자 환경 지침으로 subagent(Agent tool) 호출이 금지되어 §18.8 검증
패널을 돌릴 수 없다. 대신 아래를 인간 검토 가능한 형태로 남긴다.
**보안 경계 자기 검토 (패널 대체)**:
- **이월 범위**: 교차계정(공유 링크 fork)·부분 구간 분기 포함 **전 경로 이월**. 이는 AI 판단이
  아니라 **사용자 결정**이다 — AI 초안은 "동일계정 + 전체 분기" fail-closed 안이었고, 원본 소유자
  datasource 권한으로 반입된 데이터가 forker 계정으로 넘어가는 권한 상승 소지를 우려로 제시했다.
  사용자는 "공유 링크 기능 자체가 사실상 권한의 수동적 상승이며 링크를 생성한 대화 소유자의 책임"
  으로 판단해 전 경로 이월을 지시했다(2026-08-14). 이 결정의 잔여 위험은 **수용된 위험**이다:
  공유 링크를 만든 소유자가 자기 작업공간 데이터까지 위임한 것으로 간주된다.
- **완화**: (a) `share.fork` 감사에 이월 **건수** 기록(추적성, 내용 비노출) (b) 운영자 전역 차단
  스위치 `AGENT_SCRATCH_FORK_CARRYOVER=0` (c) 이월은 governed 반입으로 이미 작업공간에 있던
  데이터만 대상 — 새 datasource 도달 경로는 생기지 않는다(scratch role 은 여전히 `agent_scratch`
  DB 밖 무-grant, ADR-SCRATCH-0001 격리 불변).
- **격리 불변 확인**: 이월은 `scratch_guard` 를 우회하지 않는다 — guard 는 assistant 가 부르는
  `scratch_sql` 의 검문소이고, 이월은 서버 코드가 고정 식별자(`sql.Identifier`)로 수행하는
  스키마-간 복사다. 사용자 입력이 SQL 로 들어가는 지점이 없다(테이블명은 PG 카탈로그에서 읽은 값).
  복사 방향(원본→분기본)을 단위 테스트가 고정해 역방향(원본 오염) 회귀를 차단한다.
- **폭주/DoS**: 이월은 캡 3종(테이블 수·총 행수 20만·시간 예산 10s)과 문당 timeout 아래 동작하고,
  초과분은 조용히 버리지 않고 `truncated`/`skipped_detail` 로 드러낸다. 분기 응답 지연 상한이
  시간 예산으로 고정된다.
- **fail-soft 방향성**: 이월 실패는 분기를 깨지 않는다(첨부 복사와 동일 fail-open). 실패 시 분기본은
  빈 작업공간으로 시작하고, 주입되는 상태 문구가 assistant 에게 재반입을 지시하므로 **조용한 오답이
  아니라 정직한 재작업**으로 수렴한다.
**검증**: test_scratch.py 38건 PASS(신규 13건 — 복사 방향·캡·부분 실패·fail-soft·상태 문구),
feature-0003 전체 회귀 RC=0, feature-0002 전체는 pre-existing 환경 실패 3건(`chattr` 부재)만 —
main 체크아웃 동일 이미지 실행으로 귀책 판별 완료. 라이브 분기 e2e 는 배포 후(TASK-...-live).
