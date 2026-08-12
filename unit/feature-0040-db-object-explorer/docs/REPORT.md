---
doc_type: REPORT
feature_id: feature-0040-db-object-explorer
status: active
edit_policy: rewrite
source_of_truth: false
updated_at: 2026-08-12
---

# Report

## 1. 현재 상태

**코드·단위검증 완료 / 라이브 시각검증·배포 미수행.**

assistant 가 트리거·이벤트·SQL Server Agent 작업·뷰·시노님·시퀀스를 탐색하는 도구 2종
(`search_db_objects`·`describe_db_object`)과, 같은 객체를 그래프 뷰에 배치·참조·분석
대상으로 편입하는 경로(SSOT → AGE 투영 → 렌더·필터·상세 → 능동 분석 시드)를 구현했다.

## 2. 무엇이 문제였나

구조 탐색 도구가 테이블·컬럼·인덱스·FK·루틴까지만 있었다. 그 밖의 객체를 물으면 모델이
카탈로그를 손으로 SELECT 하다 `sql_guard`(SELECT-only·`sys` 차단)에 막히거나, 막히지
않더라도 SQL Server 카탈로그의 DB 스코프 특성 때문에 0행을 받아 **"없다" 로 오단정**했다.
그래프 뷰도 AGE vlabel 7종에 이런 객체가 아예 없었다.

## 3. 어떻게 풀었나 — 역할 축

벤더 객체명이 아니라 **역할**(view/trigger/schedule/alias/generator + 기존 routine)을 고정
축으로 두고, `Dialect` 하위클래스가 자기 방언의 구현체를 매핑한다. 신규 DBMS 는 매핑만
선언하면 도구·그래프·프롬프트 어휘가 그대로 재사용된다.

**핵심 안전장치는 지원상태 4종**이다. `UNSUPPORTED`(개념 부재)를 0행으로 뭉개지 않고,
`PRIVILEGED`(권한 의존)는 결과와 같은 응답에 모호성을 고지하며, `DELEGATED`(전용 도구
있음)는 거부 대신 재라우팅한다.

## 4. 검증 결과

- 신규 77건(pytest 56 + headless 21) PASS.
- 회귀: agent-core 2851 · web-ui 1383 · headless 1179 단언 — **회귀 0**.
- 유일 실패는 pre-existing 환경 결함(컨테이너에 `chattr` 부재, 미변경 main 에서 동일 재현).
- 상세·역검증은 TEST.md §3.

## 5. 남은 리스크 / 후속

| 항목 | 상태 | 비고 |
|---|---|---|
| **라이브 시각검증(PB-0008)** | **미수행** | 자산 baked + SSOT 데이터 미충전 → 배포 후 POST-DEPLOY 필수. TEST.md 에 체크리스트 |
| 배포 | 미수행 | 마이그레이션 0054 적용 필요 |
| change-reanalysis 3축 | 이연 | 현 스냅샷 2축(테이블·루틴). `inventory_sink` 는 이미 지원 — 호출부만 바꾸면 됨 |
| PostgreSQL/Oracle 방언 | 미구현 | 역할 축·API 는 수용 가능하게 설계 |
| Agent 작업 OS 레벨 단계 | 의도적 제외 | `database_name` 빈 단계(CmdExec/PowerShell)는 제품 경계 밖 — fail-closed + caveat 고지 |

## 6. 비용 영향 (사용자 축2 결정 반영)

역할 객체가 AI 능동 분석 시드에 포함되므로 **스키마당 분석 대상 수가 늘어난다**. 사용자가
비용을 명시 수용했으나, 기존 상한(`AGENT_NODE_ANALYSIS_SCHEMA_CAP`)은 그대로 적용되며
시드 순서가 테이블 → 루틴 → 객체라 cap 절단 시 객체가 먼저 탈락한다(기존 동작 보존).

**정량 추정을 하지 않았다** — 라이브 스키마별 역할 객체 수를 실측하지 않았으므로 증가분을
수치로 말할 수 없다. 배포 후 `db_objects` 행 수로 확인해야 한다(§16.7 G7-b: 표본 없는
정량 주장을 하지 않는다).

## 7. Git 동기화 결과

- 커밋: (아래 커밋 시 기입)
- verify-completion: TASK.md Completion Checklist 참조
- Push / main 병합: PR 경유

## 8. 개선 제안 (기록만)

- `sys.synonyms` 대상 마스킹 로직이 dialect SQL 안 `CASE` 3중 중복 — 뷰 함수로 추출 가능.
- headless 그래프 테스트의 인자 규약이 파일마다 달라(번들/모듈/CSS/admin.js) 일괄 실행
  스크립트가 없다. 본 cycle 에서 그것 때문에 4건을 실패로 오분류할 뻔했다 — 러너 스크립트
  1개를 두면 재발하지 않는다.
