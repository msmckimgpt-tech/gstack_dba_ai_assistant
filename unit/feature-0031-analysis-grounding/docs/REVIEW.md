---
doc_type: REVIEW
feature_id: feature-0031-analysis-grounding
status: active
edit_policy: append-only
source_of_truth: true
---

# Review Records

## REV-20260730T063000-analysis-grounding [CODEX: 반영 완료]

- **Related Change:** feature-0031 노드 분석 접지 — 통계 증거층(L0) + payload 주입(L1)
  (CHG-20260730T060000).
- **Panel:** `codex exec` 적대 리뷰(fresh-context, 스테이징 diff 직접 판독) + 자체 사전 점검.
  세션 정책상 Agent tool 을 쓰지 않으므로 T0 cycle 들과 동일한 codex CLI 경로를 사용했다.
- **반증 요청 가설:** ① 원시값 유출 경로 ② `ds` 슬롯 누수 ③ SQL 인젝션·식별자 인용
  ④ thin 재정의의 back-refine 물량 역효과 ⑤ 승격 정책 경계(naive/aware·시간창·상한)
  ⑥ alembic 0050 live 안전성·GRANT·downgrade.

### 자체 사전 점검에서 잡은 것 (리뷰 전 수정)

| # | 결함 | 조치 |
|---|---|---|
| S1 | **트랜잭션 오염** — 이 모듈은 노드 분석과 같은 PG 커넥션을 쓴다. 마이그레이션 전 배포 창에서 신규 테이블 SELECT 가 실패하면 psycopg 가 트랜잭션을 abort 시켜 **뒤따르는 노드 분석 쿼리가 전부 깨진다**. "수집 실패가 분석을 막지 않는다"는 계약이 통째로 무너지는 경로 | 모든 읽기·쓰기를 `_savepoint(c)` 로 감쌈. 회귀 테스트 2건 |
| S2 | **실패 시 기존 통계 소실** — 수집 실패 경로가 전체 행을 재작성해 직전까지 유효했던 row_count_est·PK·인덱스를 NULL 로 덮었다 | `_mark_error()` 분리 — 실패는 `error`·`collected_at` 만 갱신 |
| S3 | **예외 문자열 저장** — 드라이버 오류 메시지에 조회한 값이 실려 오는 경우가 있어(제약 위반·타입 변환) 원시값 유출 경로가 된다 | 예외 **종류**(`type(exc).__name__`)만 기록. 테스트가 값 미포함을 단정 |

### codex 지적과 처리

| # | 지적 | 판정 | 조치 |
|---|---|---|---|
| C1 | **시간창이 UTC 기준으로 판정됨** — `plan_stage` 가 UTC `now` 를 `stage_ceiling` 에 넘겨 08:00 KST 를 야간으로, 00:00 KST 를 주간으로 오판. KST 업무시간에 Stage 2/3 승격이 열린다 | **유효(P1)** | `stage_ceiling()` 을 인자 없이 호출해 서버 로컬 시각으로 판정. 회귀 테스트 추가 |
| C2 | **MSSQL `OBJECT_ID` 식별자 오류** — 우리 규약에서 `schema` 는 스키마가 아니라 effective DB 인데 `"<schema>.<table>"` 을 넘겨 MSSQL 이 schema.object 로 해석 → row count·FK·인덱스가 전부 NULL | **유효(P1)** | 3곳 모두 테이블명만 전달(`_introspect_table_columns` 규약과 동형) |
| C3 | 예산 게이트를 수동 `__enter__`/`__exit__` 로 제어 — `__enter__` 가 예외를 내면 반납이 빠진다(현 구현은 예외를 흡수하나 구조적으로 취약) | **유효(P2)** | `collect_table` 래퍼 / `_collect_table_inner` 본체로 분리하고 `with` 로만 잡음(ADR-0025-07 정합) |
| C4 | `_EMPTY_PHRASES` 가 **정확 일치만** 처리 — "연결 정보 없음." · "연결 정보가 없습니다" 는 충족으로 계산된다 | **유효(P2)** | 어미·구두점 변형을 흡수하는 `_EMPTY_RE` 로 교체. 변형 11종 파라미터 테스트 |
| C5 | thin 재정의가 back-refine 물량을 **증가**시킬 수 있다(summary 만 길고 관계·활용이 빈 분석이 새로 재-pending) | **부분 반박** | 그 조건은 종전 판정에서도 thin 이었다(`not rel and not usage`) — 신규 유입이 아니다. 반대로 종전에는 summary<120 이 무조건 thin 이었고 실측 평균이 94자라 **정상 분석 대부분이 thin** 이었다. 하한을 20자로 내리고 role 을 충족 항목에 넣었으므로 순 효과는 **감소**다. 다만 C4 는 실제로 물량에 영향을 주므로 반영했다 |
| C6 | downgrade 가 통계 전체를 삭제한다 | **의도된 설계** | 파생 데이터이고 재수집 가능하다. `alembic_version` 롤백 시 evidence 가 사라지면 분석은 증거 없이 진행되는 종전 동작으로 되돌아간다(fail-soft) — 데이터 손실이 아니라 캐시 소실이다 |
| — | SQL 인젝션 | **없음(확인)** | `_quote_ident` 화이트리스트 · LIMIT/TOP 은 내부 고정 Stage 값 · 카탈로그 조건은 파라미터 바인딩 |
| — | GRANT · migrate-lint · head | **통과(확인)** | |

### Verdict

SHIP — P1 2건(C1·C2) 및 자체 발견 3건(S1~S3) in-cycle 수정, P2 2건(C3·C4) 반영, 1건(C5) 근거를
들어 부분 반박, 1건(C6) 의도된 설계로 기록. 수정 후 `COMPOSE_PROJECT_NAME=repo make test` 재실행.

### 남긴 리스크 (배포 후 실측 대상)

- thin 판정 변경의 실제 물량 효과는 라이브 분포에 달렸다. 배포 후 `node_analysis_jobs` 의
  `pass_no>0` 증가 추이를 확인한다(`REFINE_MAX=30`/run 캡은 유지).
- Stage 승격은 24시간 뒤에야 첫 관측이 가능하다(`metadata_table_stats.stage`).
