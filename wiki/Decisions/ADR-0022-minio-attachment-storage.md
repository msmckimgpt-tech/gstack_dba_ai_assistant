---
doc_type: WIKI_ADR_MIRROR
scope: project
status: active
edit_policy: ai-maintained
source_of_truth: false
template_version: v3.13.0
domain: [architecture, wiki, storage, minio]
ai_read_priority: 7
wiki_role: adr_mirror
wiki_name: project
confidence: high
maturity: substantial
ai_generated: true
adr_id: ADR-0022
linked_canonical: ../../docs/DECISIONS.md#ADR-0022
status_adr: accepted
created: 2026-05-21
sources:
  - ../../docs/DECISIONS.md
---

# ADR-0022 — MinIO 첨부 storage 도입

| 항목 | 값 |
|---|---|
| 분류 | `#wiki/adr-mirror` |
| 정본 | [[../../docs/DECISIONS\|docs/DECISIONS.md#ADR-0022]] |
| 상태 | accepted (TASK-0094 Sprint 1 Phase 1, Critical §12.3) |
| 결정일 | 2026-05-21 |

## 1. 개요

첨부 객체 (CSV/XLSX/PDF/이미지) 의 영속 저장에 **MinIO** 단일 service 도입 — AWS S3 protocol-compat 의 self-hosted 옵션 중 docker-compose single service 가 가장 간단.

## 2. 상세

### 2.1 구성

- `minio` service (api 9000 / console 9001) + `minio-init` one-shot
- Bucket: `agent-attachments`
- Volume: `../artifacts/minio-data:/data`
- minio-init: bucket idempotent 생성 + lifecycle policy (D6 delete_reason 별 retention) + root credential 비활성화 + app 전용 access key 생성

### 2.2 외부 송신 정책 (BRIEFING D13)

- 사내망 다운로드 = signed URL 로 frontend 노출
- 외부 LLM 송신 = server-side bytes read 후 base64/files API 로 전달 (signed URL 외부 송신 금지)

### 2.3 App key rotation (D20)

dual-key rotation runbook (Phase 4 — storage wrapper 와 동시 ship). 별 cycle 의 subtask.

## 3. 평가

### 3.1 장점

- single docker service · S3 protocol compat · boto3 reuse 가능
- lifecycle / IAM 지원

### 3.2 단점

- 사내망 단일 호스트 환경에 적합 — 외부 SaaS 운영 시 AWS S3 또는 managed 옵션 재검토

## 4. Options

- AWS S3 / managed → 운영 의존 + 비용 (외부 운영 비대)
- 로컬 파일시스템 직접 mount → lifecycle / RBAC / signed URL / backup 부재
- **MinIO** (채택)

## 5. 관련 문서

- [[../../docs/DECISIONS|정본]]
- [[../Features/feature-0003-agent-web-ui]]
- [[ADR-0023-sandbox-schema-mysql-users]]

## 6. 둘러보기

- 상위: [[_Index|Decisions MOC]]
- TASK-0094 sub-decision

## 분류

`#wiki/adr-mirror` · `#status_adr/accepted` · `#domain/storage` · `#domain/attachment`
