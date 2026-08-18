---
doc_type: WIKI_FEATURE_CARD
scope: feature
status: active
edit_policy: ai-maintained
source_of_truth: false
template_version: v3.12.0
domain: [feature, wiki]
ai_read_priority: 7
wiki_role: feature_card
wiki_name: project
confidence: high
maturity: substantial
ai_generated: true
feature_id: feature-0040-db-object-explorer
linked_unit: unit/feature-0040-db-object-explorer
sources:
  - ../../unit/feature-0040-db-object-explorer/docs/FUNCTION.md
---

| 항목 | 값 |
|---|---|
| 기능 ID | feature-0040-db-object-explorer |
| 상태 | review (코드·실브라우저 검증 완료 / 배포 전) |
| 도입 | 2026-08-12 |
| 정본 | [[feature-0040-db-object-explorer]] `unit/feature-0040-db-object-explorer/docs/` |
| 코드 거주 | feature-0002(도구·수집·투영) · feature-0003(그래프 뷰) |

# feature-0040 역할 기반 DB 객체 탐색

## 1. 개요

assistant 가 **트리거·이벤트·SQL Server Agent 작업·뷰·시노님·시퀀스**를 탐색하는 도구를
제공하고, 같은 객체를 그래프 뷰에 배치·참조·분석 대상으로 편입한 기능. 벤더 객체명이 아니라
**역할(role)** 을 분류 축으로 삼아 DBMS 확장에 열려 있다.

## 2. 상세

### 2.1 역할 6종

| role | 하는 일 | MySQL | SQL Server |
|---|---|---|---|
| routine | 호출되어 실행 | PROCEDURE/FUNCTION | 동일 |
| view | 저장된 질의가 테이블처럼 조회 | VIEW | VIEW |
| trigger | 데이터 변경에 반응해 자동 실행 | TRIGGER | DML/DDL TRIGGER |
| schedule | 시간표에 따라 자동 실행 | EVENT | Agent Job |
| alias | 다른 객체를 가리키는 이름 | (없음) | SYNONYM |
| generator | 값을 순차 생성 | (없음) | SEQUENCE |

### 2.2 지원상태 4종 — 미지원 ≠ 부재

`SUPPORTED` / `UNSUPPORTED`(개념 부재) / `PRIVILEGED`(권한 의존) / `DELEGATED`(전용 도구).
0행을 "없다" 로 서술하는 허위 부재를 타입 레벨에서 차단한다.

## 3. 특징

- 도구 2종 고정 — `search_db_objects`(역할 생략 시 전 역할 개관) · `describe_db_object`.
- 그래프: `DbObject` 정점 + `OBJECT_USES`(참조·실선) / `OBJECT_ON`(소유·파선) 분리.
- `msdb` 접근은 `_agent_jobs_sql` **한 함수**의 고정 질의로만(freeform 차단 불변).

## n. 관련 문서

- [[feature-0016-metadata-graph]] — 그래프 인프라·AGE 투영
- [[feature-0002-agent-core]] — 도구·dialect·insight
- [[feature-0003-agent-web-ui]] — 그래프 뷰 자산

## 분류

#wiki/feature #status/review #confidence/high
