---
doc_type: WIKI_ENTITY
scope: project
status: active
edit_policy: ai-maintained
source_of_truth: false
template_version: v3.13.0
domain: [wiki, entity, playwright, browser]
ai_read_priority: 8
wiki_role: article
wiki_name: project
confidence: high
maturity: draft
ai_generated: true
entity_type: tool
aliases: [Playwright Python]
tags: [playwright, browser, automation]
---

# Playwright

| 항목 | 값 |
|---|---|
| 분류 | `#wiki/entity` |
| 유형 | tool (OSS, browser automation) |
| 본 프로젝트 사용 | feature-0004 의 browser service 핵심 |

## 1. 개요

Microsoft 의 browser 자동화 라이브러리. 본 프로젝트는 FastAPI + Playwright single container 로 HTTP API 기반 세션 제어 + 스크린샷 + DOM 검증 service 를 제공.

## 2. 상세

### 2.1 본 프로젝트 사용

- `src/app.py` = FastAPI + Playwright 서비스
- `src/ctl.py` = CLI 제어 (HTTP API 호출)
- `make browser-*` 인터페이스

### 2.2 산출물

- 스크린샷: `../../artifacts/shared/out/browser/*.png`
- 로그: `docker compose logs browser`

### 2.3 본 프로젝트와의 관계

- TASK-0058: `make browser-up` 이 `dc-build` 가드 패턴 적용 (buildx provenance race 차단)
- feature-0005 QA / MCP 가 browser smoke 검증에 의존

## 3. 특징

- session-based 다중 동시 제어
- HTTP API + CLI 분리
- 408 timeout / 404 세션 미존재

## 4. 인용 source

- [[../Features/feature-0004-browser-automation]]

## 5. 관련 entity

- 없음

## 6. 관련 concept

- 없음

## 7. 외부 link

- [Playwright Python](https://playwright.dev/python/)
- [Playwright GitHub](https://github.com/microsoft/playwright)

## 8. 분류

`#wiki/entity` · `#entity_type/tool` · `#confidence/high`
