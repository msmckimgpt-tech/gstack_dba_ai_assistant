---
doc_type: WIKI_CONCEPT
scope: project
status: active
edit_policy: ai-maintained
source_of_truth: false
template_version: v3.13.0
domain: [wiki, concept, datasource, security, encryption]
ai_read_priority: 8
wiki_role: article
wiki_name: project
confidence: high
maturity: substantial
ai_generated: true
concept_category: pattern
aliases: [datasource registry, 자격증명 암호화, envelope encryption, KEK/DEK]
tags: [datasource, security, encryption, envelope, kek, dek, ssrf]
last_updated: 2026-06-16
---

# Datasource Registry (envelope 암호화)

| 항목 | 값 |
|---|---|
| 분류 | `#wiki/concept` |
| 카테고리 | pattern |
| 정본 설계 | [[../../unit/feature-0002-agent-core/docs/DESIGN-datasource-registry\|DESIGN-datasource-registry.md]] |
| 관련 ADR | [[../Decisions/ADR-0030-ssrf-guard-toggle]] |
| 최종 갱신 | 2026-06-12 (TASK-0205 배포·라이브 e2e 완료) |

## 1. 개요

데이터소스 연결 자격증명을 `.env` 평문에서 **DB 저장 + envelope 암호화 (KEK/DEK)** 로 이관하고, 관리 콘솔에서 CRUD 가능하게 한 패턴. password 만 암호화하며(host/user 는 datasource_public 노출 허용), 평문 password 는 cache/log/API 응답 어디에도 남기지 않는다.

> **구현 현황**: TASK-0205 설계·구현·2회 outside-voice·배포·라이브 e2e (암호화→복호→실 MSSQL 12,725행) 완료. KEK base64 패딩 함정·동시세션 워킹트리 점유 함정 관측.

## 2. Envelope 암호화 (KEK/DEK)

```
KEK (32B base64 root key, .env.secret)        ← .env 와 분리 (least-privilege)
  └─ wraps DEK (32B per-version, WebDatasourceKeys 테이블)
        └─ AESGCM(password, AAD=DatasourceKey, nonce=12B per-record)
```

- **KEK**: `.env.secret` (다른 secret 과 분리). 버전 관리.
- **DEK**: 버전별 32B, KEK 로 wrap 해 `WebDatasourceKeys` 에 저장.
- **password**: DEK 로 AESGCM 암호화 (AAD = DatasourceKey, nonce = 레코드별 12B).
- **라이브러리**: `cryptography>=42.0.0` (AESGCM), envelope 로직 `cred_crypto.py`.

## 3. DB 테이블 + 해석

| 테이블 | 용도 |
|---|---|
| `WebDatasources` (MySQL agent_memory) | **Id**(surrogate PK)/DatasourceKey(rename 가능 라벨)/host/port/user/password(암호화)/default_db/engine/IsActive |
| `WebDatasourceKeys` | DEK 버전 관리 |

- **resolution**: `cfg.get_datasource(key)` → DB (`IsActive=1`) 우선, `.env` fallback 공존. **resolve 시마다 복호화** (평문 캐시 없음). delete / `IsActive=0` 즉시 무효화.
- **제품 MSSQL 참조DB**: `WebProducts.DatasourceDatabase` override (MSSQL 단일 datasource 다중 DB 시나리오). → TASK-0206 의 DB-단위 접근으로 일반화되어 별도 참조DB dropdown 은 폐지됨.
- **라벨/키 분리 → Id surrogate (TASK-0277)**: 제품 바인딩 FK 를 rename 가능한 `DatasourceKey` 에서 stable `WebDatasources.Id` 로 이전. 멀티-ds join 본체(`WebProductDatasources`)·접근DB(`WebProductDatabases`)·`WebProducts` 3 테이블에 `DatasourceId` backfill, rename 은 Id-구동 완전 cascade (라벨 rename 에도 고아 0). write = dual-write (Id+Key), read 무변경.

## 3.1 연결 격리 + 상태 모니터 (TASK-0247/0255/0282)

- **circuit breaker**: per-datasource (`scope_key` = 엔진+host+port) breaker 로 불안정 datasource 1개가 단일 직렬 ask-worker 를 점유하는 starvation 차단. `connect_with_retry` 경계서 요청당 1회 트립, half-open 은 락내 토큰. bounded `AGENT_DB_CONNECT_TIMEOUT_SEC`(10s) 로 connect timeout 을 쿼리 예산(`AGENT_TIMEOUT_SEC`)에서 분리. control-plane(memory DB) 은 breaker 미적용.
- **conn_health 3-state**: `modules/conn_health.py` 가 2-stage probe (TCP `AGENT_CONN_TCP_TIMEOUT_MS`=2000 → DB `SELECT 1`) 로 **정상**(빠름)/**불안정**(느림 ≥ `AGENT_CONN_SLOW_MS` 또는 1회 blip)/**끊김**(연속 `AGENT_CONN_DOWN_AFTER_FAILS` 실패) 분류. `should_fast_fail` = down 한정 → 느린 타-리전 datasource 도 작업화면에서 사용 가능. 작업화면(초록/빨강/회색 ●)·관리콘솔 picker(3-state) 양면 노출.

## 4. Admin API + RBAC

- POST/PATCH/DELETE datasources, `GET .../databases` (서버 DB 목록을 RO GRANT scope 로 필터, MSSQL).
- **RBAC**: `console.manage` = CRUD, `console.access` = 목록 (password 마스킹).
- 모든 변경 audit.

## 5. 보안 경계

- password 암호화만 (host/user 평문 허용). API 응답·로그·캐시에 평문 password 금지.
- **SSRF 방어**: RFC1918/링크로컬/메타데이터 IP 차단 + host allowlist (CIDR) + DNS rebinding (해석 후 IP 재검증). 운영 토글은 [[../Decisions/ADR-0030-ssrf-guard-toggle]] — 사설망 경계만 끄고 메타데이터 IP 는 항상 하드차단.
- decrypt 실패 시 DB-connect **fail-closed**.

## 6. 인용 source

- [[../../unit/feature-0002-agent-core/docs/DESIGN-datasource-registry|DESIGN-datasource-registry.md]] (정본)
- [[../Decisions/ADR-0030-ssrf-guard-toggle]]

## 7. 관련 concept

- [[multi-datasource]] · [[db-level-access]] · [[audit-subsystem]]

## 8. 관련 entity

- [[../entities/mysql]] · [[../entities/mssql]]

## 9. 외부 link

- [cryptography — AESGCM](https://cryptography.io/en/latest/hazmat/primitives/aead/)
- [Envelope encryption (AWS KMS 개념)](https://docs.aws.amazon.com/kms/latest/developerguide/concepts.html#enveloping)

## 분류

`#wiki/concept` · `#concept_category/pattern` · `#domain/security` · `#domain/encryption` · `#confidence/high`
