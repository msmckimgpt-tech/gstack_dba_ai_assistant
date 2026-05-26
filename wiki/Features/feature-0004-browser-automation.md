---
doc_type: WIKI_FEATURE_CARD
scope: feature
status: active
edit_policy: ai-maintained
source_of_truth: false
template_version: v3.13.0
domain: [feature, wiki, browser, playwright]
ai_read_priority: 7
wiki_role: feature_card
wiki_name: project
confidence: high
maturity: draft
ai_generated: true
feature_id: feature-0004-browser-automation
linked_unit: unit/feature-0004-browser-automation
created: 2026-05-26
sources:
  - ../../unit/feature-0004-browser-automation/docs/FUNCTION.md
---

# Feature — Browser Automation

| 항목 | 값 |
|---|---|
| 분류 | `#wiki/feature-card` |
| feature_id | feature-0004-browser-automation |
| 상태 | active |
| 정본 | [[../../unit/feature-0004-browser-automation/docs/FUNCTION\|FUNCTION.md]] |
| 영역 | Playwright HTTP 제어 service · CLI · 스크린샷 |

## 1. 개요

**Playwright** 기반 browser 자동화 service + CLI 제어 (`ctl.py`). 세션 기반 HTTP API 로 페이지 조작 / 스크린샷 / DOM 검증 등을 수행한다.

## 2. 상세

### 2.1 책임 경계

- **입력**: `BROWSER_*` 환경값, 루트 Makefile 의 `browser-*` 명령
- **출력**: 브라우저 HTTP 제어 API, 세션 기반 자동화 동작, 스크린샷 파일
- **side-effect**: `../../artifacts/shared/out/browser/*.png` 저장

### 2.2 주요 흐름 (FUNCTION §7)

1. `browser` 서비스가 Playwright 기동
2. `ctl.py` 가 HTTP API 로 세션 제어
3. 스크린샷·결과를 `/shared/out/browser` 저장

### 2.3 에러 처리

- 세션 미존재 → 404
- 페이지 타임아웃 → 408

## 3. 특징

- FastAPI + Playwright single container
- `make browser-up` 이 `dc-build` 가드 패턴 적용 (TASK-0058 — buildx provenance race 차단)
- session-based — 다중 동시 제어 가능

## 4. 사용법

```bash
make browser-up       # service 기동
make browser-status   # 세션 상태
make browser-shot URL=https://example.com   # 스크린샷
```

## 5. 책임 영역과 dependency

### 5.1 내부 의존

- [[feature-0001-platform-runtime]] — 운영 런타임 공유

### 5.2 본 feature 를 의존하는 feature

- [[feature-0005-qa-mcp]] — 브라우저 제어 smoke 검증

## 6. 관련 정본

- [[../../unit/feature-0004-browser-automation/docs/FUNCTION|FUNCTION.md]]

## 7. 관련 노트

- [[../Architecture/Module-Map]]

## 8. 둘러보기

- 상위: [[_Index|Features MOC]]
- sibling: [[feature-0005-qa-mcp]] · [[feature-0001-platform-runtime]]

## 9. 외부 link

- [Playwright Python](https://playwright.dev/python/)

## 분류

`#wiki/feature-card` · `#confidence/high` · `#maturity/draft` · `#domain/browser`
