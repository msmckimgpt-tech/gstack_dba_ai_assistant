---
doc_type: WIKI_ENTITY
scope: project
status: active
edit_policy: ai-maintained
source_of_truth: false
template_version: v3.13.0
domain: [wiki, entity, minio, storage]
ai_read_priority: 8
wiki_role: article
wiki_name: project
confidence: high
maturity: draft
ai_generated: true
entity_type: tool
aliases: [MinIO S3-compat]
tags: [minio, s3, storage, attachment]
---

# MinIO

| 항목 | 값 |
|---|---|
| 분류 | `#wiki/entity` |
| 유형 | tool (OSS, S3-compat object storage) |
| 본 프로젝트 사용 | `agent-attachments` bucket — TASK-0094 첨부 storage |

## 1. 개요

AWS S3 protocol-compatible self-hosted object storage. 본 프로젝트는 docker-compose `minio` + `minio-init` 서비스로 도입 (ADR-0022) — 첨부 파일 (CSV/XLSX/PDF/이미지) 의 영속 저장.

## 2. 상세

### 2.1 구성

- `minio` (api 9000 / console 9001)
- `minio-init` one-shot — bucket idempotent 생성 + lifecycle policy + root credential 비활성화 + app key 생성
- Volume: `../artifacts/minio-data:/data`

### 2.2 사용 흐름

- 사내망 다운로드 = signed URL (frontend)
- 외부 LLM 송신 = server-side bytes read + base64/files API (signed URL 외부 송신 금지, BRIEFING D13)

### 2.3 app key rotation (D20)

dual-key rotation runbook — Phase 4 의 storage wrapper 와 동시 ship.

## 3. 특징

- boto3 reuse 가능 (S3 SDK)
- lifecycle policy + IAM 지원
- `.env.minio` 별도 secret 파일 (CHG-20260522-0005)

## 4. 인용 source

- [[../Features/feature-0003-agent-web-ui]]
- [[../Decisions/ADR-0022-minio-attachment-storage]]

## 5. 관련 entity

- 없음

## 6. 관련 concept

- [[../concepts/sandbox-schema-isolation]]

## 7. 외부 link

- [MinIO docs](https://min.io/docs/minio/linux/index.html)
- [MinIO GitHub](https://github.com/minio/minio)

## 8. 분류

`#wiki/entity` · `#entity_type/tool` · `#confidence/high`
