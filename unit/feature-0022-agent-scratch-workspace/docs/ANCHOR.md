---
doc_type: ANCHOR
feature_id: feature-0022-agent-scratch-workspace
created_at: 2026-07-21T07:22:46Z
status: active
edit_policy: mixed
source_of_truth: true
---

# ANCHOR: feature-0022-agent-scratch-workspace — Agent PG Scratch Workspace

## §1. 외부 관점 요약
이 시스템의 데이터 접근 태세는 철저히 **read-only** 다(sql_guard 는 외부 데이터소스에 대해
단일 SELECT/CTE 만 허용). 처음 코드를 보는 사람은 "assistant 에게 PG 쓰기·DDL 자율성을
준다고? 그럼 read-only 원칙이 깨지는 것 아닌가?" 라고 의문을 가질 수 있다. 답: 자율 쓰기는
**전용 DB(`agent_scratch`)로 완전히 격리된 sandbox 안에서만** 일어나고, 그 role 은 KB·web·
외부 datasource 에 물리적으로 도달할 수 없다. 외부 데이터 접근은 여전히 기존 read-only
게이트를 그대로 통과해야만 반입되므로, "완전 자율"은 sandbox 경계 안으로 한정된 자율이다.

## §2. 대안 분기
- **Alt-A: postgres_fdw/dblink 물리 federation.** 페르소나: 실시간 cross-DB 조인이 잦은
  분석 플랫폼. 안 고른 이유: 확장 설치에 superuser 필요·외부 소스로의 상시 물리 연결이 새
  egress·신뢰경계를 만든다. 반입(materialize)→PG 내 JOIN 이 기존 read-only 게이트를 재사용해
  경계 추가가 0.
- **Alt-B: agent_kb 안 전용 스키마 재사용(별 DB 아님).** 페르소나: 인프라를 늘리기 싫은 최소
  구성 팀. 안 고른 이유: role grant 누출·search_path 사고 시 KB 테이블에 도달할 위험. 별 DB +
  CONNECT 격리가 "완전 자율"을 안전하게 담는 유일한 강한 경계(ADR-SCRATCH-0001).
- **Alt-C: 전역 공유 작업공간(대화 무관).** 페르소나: 단일 사용자 데스크톱 도구. 안 고른 이유:
  다중 사용자·공유 대화에서 반입 데이터가 대화 간 혼재→datasource 가시성/window 격리가 깨짐.

## §3. 가정된 사용 시나리오
운영 DBA 가 assistant 에게 "게임 로그 DB(MySQL)의 최근 결제 유저와 회계 DB(MSSQL)의 환불
내역을 대조해줘" 라고 묻는다. 두 데이터는 엔진이 달라 한 쿼리로 JOIN 할 수 없다. assistant 는
`scratch_import` 로 각 소스에서 (이미 볼 수 있는 범위의) 데이터를 PG 작업공간에 반입하고,
`scratch_sql` 로 PG 안에서 JOIN 해 대조 결과를 답한다. 대화가 끝나고 24시간이 지나면 그
작업공간은 자동으로 비워져, 민감 데이터가 임시 영역에 남지 않는다. 6개월 후 이 코드를 보는
동료는 "왜 반입→PG JOIN 인가"를 §1·§2 로 이해한다.

## §4. 외부 검증 로그 (append-only)
(엔트리 없음 — 일반 TASK cycle 완료 조건은 아님. 활성화/라이브 검증 시 human 이 append.)
