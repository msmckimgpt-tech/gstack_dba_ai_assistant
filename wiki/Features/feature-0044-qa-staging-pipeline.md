---
doc_type: WIKI_FEATURE_CARD
scope: feature
status: draft
edit_policy: ai-maintained
source_of_truth: false
template_version: v3.12.0
domain: [feature, wiki]
ai_read_priority: 7
wiki_role: feature_card
wiki_name: project
confidence: high
maturity: draft
ai_generated: true
feature_id: feature-0044-qa-staging-pipeline
linked_unit: unit/feature-0044-qa-staging-pipeline
sources:
  - ../../unit/feature-0044-qa-staging-pipeline/docs/FUNCTION.md
  - ../../unit/feature-0044-qa-staging-pipeline/docs/CICD_DESIGN.md
---

# Feature — QA 스테이징 파이프라인 (격리망 CI/CD)

> Feature 의 *사람용 입구*. 정본은 [[../../unit/feature-0044-qa-staging-pipeline/docs/FUNCTION|unit/feature-0044-qa-staging-pipeline/docs/FUNCTION.md]],
> 전 과정 설계는 [[../../unit/feature-0044-qa-staging-pipeline/docs/CICD_DESIGN|CICD_DESIGN.md]].

## 목차

1. [한 줄 요약](#1-한-줄-요약)
2. [상태](#2-상태)
3. [책임 경계](#3-책임-경계)
4. [관련 정본](#4-관련-정본)
5. [관련 노트](#5-관련-노트)
6. [Open questions / 미해결](#6-open-questions--미해결)
7. [변경 이력 (이 카드)](#7-변경-이력-이-카드)

## 1. 한 줄 요약

라이브 배포 전 관문으로 격리망 QA 머신을 세우고, 사내 GitLab CI 에서 **한 번 빌드한 이미지
다이제스트**를 QA·라이브가 각자 **당겨서(pull)** 배포하며, 승격은 재빌드가 아니라 태그 이동으로
처리하는 CI/CD 파이프라인.

## 2. 상태

- **단계**: draft (설계 제안 완료 — 구현 착수는 사용자 승인 대기)
- **마지막 갱신**: 2026-08-26
- **AI 작업자**: claude / feature-0044 cycle

## 3. 책임 경계

- **입력**: 릴리즈 태그(annotated) · 릴리즈 매니페스트(이미지 다이제스트·alembic head·env 키 목록·
  MCP API/러너 버전) · 사내 registry/PyPI 미러 · read-only deploy key · 라이브 백업 산출물
- **출력**: 사내 registry 의 다이제스트 고정 이미지 세트 · QA 가동 스택 · 스모크 리포트 ·
  `promote/<tag>` 승격 태그(= 라이브 배포 입력)
- **side-effect**: QA 머신에 **마스킹 없는 라이브 복제본**이 적재된다 → QA 머신이 운영 등급
  자산이 되며 접근통제·감사·백업·폐기가 라이브와 동일해야 한다

## 4. 관련 정본

- [[../../unit/feature-0044-qa-staging-pipeline/docs/FUNCTION|FUNCTION.md]] — 범위·계약·AC
- [[../../unit/feature-0044-qa-staging-pipeline/docs/CICD_DESIGN|CICD_DESIGN.md]] — 전 과정 절차·근거
- [[../../unit/feature-0044-qa-staging-pipeline/docs/TASK|TASK.md]] — Phase 0~7 태스크
- [[../../unit/feature-0044-qa-staging-pipeline/docs/ANCHOR|ANCHOR.md]] — 대안 4안과 미채택 사유

## 5. 관련 노트

- [[feature-0014-zero-downtime-deploy]] — 무중단 배포 스파인 (본 feature 가 확장하는 대상)
- [[feature-0020-zd-deploy-all]] — 전 배포 대상 커버리지
- [[feature-0041-external-ai-tool-surface]] — MCP 도구 표면 (배포 완료 판정의 검증 대상)
- `feature-0043-external-llm-bridge` — 서버 LLM 차단 + pull 브리지 (QA 시크릿 표면 축소 근거).
  진행 중 미머지 worktree 라 wiki 카드 미생성 — 머지 시 카드 링크로 승격
- [[../Architecture/Module-Map|Module Map]] · [[../Decisions/_Index|Decisions MOC]]

## 6. Open questions / 미해결

- 사내 GitLab 의 인터넷 아웃바운드 가능 여부 (미러 자동/수동을 가름)
- 사내 컨테이너 레지스트리 · PyPI/apt 미러 존재 여부
- VPN DNS 의 `WEB_PUBLIC_HOST` 해석 + 사내 CA 발급 (MCP 접근의 전제 조건)
- 마스킹 없는 라이브 데이터 반출의 승인 주체·경로
- QA 머신 스펙 (23서비스 스택 + 로컬 임베딩)
- 라이브의 최종 위치 (현재 개발 머신과 동일 호스트)

## 7. 변경 이력 (이 카드)

> append-only. 정본 변경은 `unit/feature-0044-qa-staging-pipeline/docs/MODIFY.md` 에.

- 2026-08-26: 초안 작성 — 설계 제안 cycle(Phase 0) 동반 생성
