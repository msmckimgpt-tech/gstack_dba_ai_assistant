---
doc_type: WIKI_FEATURE_CARD
scope: feature
status: draft
edit_policy: ai-maintained
source_of_truth: false
template_version: v3.12.0
domain: [feature, wiki, testing]
ai_read_priority: 7
wiki_role: feature_card
wiki_name: project
confidence: high
maturity: draft
ai_generated: true
feature_id: feature-0008-windows-browser-testing
linked_unit: unit/feature-0008-windows-browser-testing
sources:
  - ../../unit/feature-0008-windows-browser-testing/docs/FUNCTION.md
---

# Feature — Windows 브라우저 테스트 (AI 자동 구동)

> Feature 의 *사람용 입구*. 정본은 [[../../unit/feature-0008-windows-browser-testing/docs/FUNCTION|unit/feature-0008-windows-browser-testing/docs/FUNCTION.md]].

## 목차

1. [한 줄 요약](#1-한-줄-요약)
2. [상태](#2-상태)
3. [책임 경계](#3-책임-경계)
4. [관련 정본](#4-관련-정본)
5. [관련 노트](#5-관련-노트)
6. [Open questions / 미해결](#6-open-questions--미해결)
7. [변경 이력 (이 카드)](#7-변경-이력-이-카드)

## 1. 한 줄 요약

> AI 가 WSL 에서 실제 Windows 브라우저를 CDP 로 자동 구동해 웹/UI 를 검증한다 — CLI·WSL-headless 의 사용자 관점 괴리를 차단.

## 2. 상태

- **단계**: draft
- **마지막 갱신**: 2026-06-04
- **AI 작업자**: claude (ai/claude/feature-0008-windows-browser-testing)

## 3. 책임 경계

- 입력: 검증 대상 URL(기본 localhost:18080), 시나리오 JSON, 환경변수(`WIN_BROWSER_*`).
- 출력: 1줄 JSON 결과 + 실제 Windows 브라우저 스크린샷 + TEST.md §3 `Environment: Windows-browser` Run.
- side-effect: 전용 프로필로 Windows Chrome/Edge 기동(`down` 으로 정리), NAT 모드 시 1회 portproxy relay(관리자).

## 4. 관련 정본

- [[../../unit/feature-0008-windows-browser-testing/docs/FUNCTION|FUNCTION.md]] — 기능 정본
- [[../../unit/feature-0008-windows-browser-testing/docs/TASK|TASK.md]] — 작업 컨텍스트
- [[../../unit/feature-0008-windows-browser-testing/docs/TEST|TEST.md]] — 테스트 케이스·실행 이력
- [[../../playbooks/PB-0008-windows-browser-verification|PB-0008]] — 검증 절차
- `bin/win-browser.py`, `bin/win-browser-setup.ps1`, `bin/WIN-BROWSER-SETUP.md` — 도구·setup
- AGENTS.md §15.4.1 (게이트), DECISIONS ADR-0029

## 5. 관련 노트

- [[../Architecture/Module-Map|Module Map]] — bin/ 도구 위치
- [[../Decisions/_Index|Decisions MOC]] — ADR-0029
- feature-0003-agent-web-ui (검증 대상), feature-0004-browser-automation (headless 보조)

## 6. Open questions / 미해결

- 실 Windows 브라우저 CDP wire end-to-end (브리지 1회 setup 후 첫 Windows-browser run — TEST.md §4).
- check #13 의 strict(MUST) 격상 시점 (현재 WARN-only v1).
- 세션 단위 ephemeral 브리지 자동화.

## 7. 변경 이력 (이 카드)

> append-only. 정본 변경은 `unit/feature-0008-windows-browser-testing/docs/MODIFY.md` 에.

- 2026-06-04: 초안 작성 (feature 도입과 함께).
