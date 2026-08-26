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
> 전 과정 설계는 [[../../unit/feature-0044-qa-staging-pipeline/docs/CICD_DESIGN|CICD_DESIGN.md]] (rev.2).

## 목차

1. [한 줄 요약](#1-한-줄-요약)
2. [상태](#2-상태)
3. [책임 경계](#3-책임-경계)
4. [관련 정본](#4-관련-정본)
5. [관련 노트](#5-관련-노트)
6. [Open questions / 미해결](#6-open-questions--미해결)
7. [변경 이력 (이 카드)](#7-변경-이력-이-카드)

## 1. 한 줄 요약

라이브 배포 전 관문으로 격리망 QA 머신을 세우고 라이브까지 전용 호스트로 분리하면서,
**한 번 빌드한 이미지를 tar 로 릴레이**해 QA·라이브가 각자 당겨 설치하고, 승격은 재빌드가
아니라 매니페스트 표식으로 처리하는 CI/CD 파이프라인.

## 2. 상태

- **단계**: draft (설계 rev.3 확정 — 구현 착수는 사용자 승인 대기)
- **마지막 갱신**: 2026-08-27
- **AI 작업자**: claude / feature-0044 cycle (rev.1 08-26 · rev.2·rev.3 08-27)

## 3. 책임 경계

- **입력**: 릴리즈 태그(annotated) · 릴리즈 매니페스트(이미지 `sha256`+`image_id` ·
  `git_commit` · alembic head · env 키 목록 · MCP API/러너 버전) · 베이스 이미지 tar ·
  SVN read-only 자격증명 · SOPS age 키 · 라이브 백업 산출물
- **출력**: `releases/<tag>/` 산출물 디렉토리 · 대상 머신 가동 스택 · QA 스모크 리포트 ·
  `promoted/current.json`(라이브 배포의 유일한 입력)
- **side-effect**: QA 머신에 **마스킹 없는 라이브 복제본**이 적재된다 → QA 머신이 운영 등급
  자산이 되며 접근통제·감사·백업·폐기가 라이브와 동일해야 한다. 라이브 호스트 이전 시
  **1회 전환 창**(서비스 중단)이 발생한다

## 4. 관련 정본

- [[../../unit/feature-0044-qa-staging-pipeline/docs/FUNCTION|FUNCTION.md]] — 범위·전제 10축·AC 10항
- [[../../unit/feature-0044-qa-staging-pipeline/docs/CICD_DESIGN|CICD_DESIGN.md]] — 전 과정 절차·근거·권장 스펙
- [[../../unit/feature-0044-qa-staging-pipeline/docs/TASK|TASK.md]] — Phase 0~7 태스크
- [[../../unit/feature-0044-qa-staging-pipeline/docs/DECISIONS|DECISIONS.md]] — ADR 4건
- [[../../unit/feature-0044-qa-staging-pipeline/docs/ANCHOR|ANCHOR.md]] — 대안 6안과 미채택 사유

## 5. 관련 노트

- [[feature-0014-zero-downtime-deploy]] — 무중단 배포 스파인 (본 feature 가 확장하는 대상)
- [[feature-0020-zd-deploy-all]] — 전 배포 대상 커버리지
- [[feature-0041-external-ai-tool-surface]] — MCP 도구 표면 (배포 완료 판정의 검증 대상)
- [[feature-0043-external-llm-bridge]] — 서버 LLM 차단 + pull 브리지 (QA 시크릿 표면 축소 근거)
- [[../Architecture/Module-Map|Module Map]] · [[../Decisions/_Index|Decisions MOC]]

## 6. Open questions / 미해결

**미확인 전제 1건**
- 사내 PyPI/apt 미러 유무 — 있으면 index 치환, 없으면 오프라인 wheel 번들

**외부 의존 1건** (본 feature 범위 밖이나 일정·스펙에 영향)
- **임베딩 사내 MCP 이관** — 로컬 LLM 은 임베딩 한 축만 남았고 그것이 유일한 GPU 소비자다.
  이관이 QA 세팅보다 먼저 끝나면 GPU 없이 산정·구매 가능. 확인할 것: 벡터 차원 1024 유지 ·
  전송 계약(OpenAI 호환이면 alias 한 줄, 순수 MCP 면 어댑터) · 가용성/타임아웃 계약 ·
  임베딩 전용 계정의 시크릿 예외 범위

> rev.2 에서 열려 있던 결정 2건은 해소됐다 — SVN 용량 정책 **안 A**, GPU **불요**.

## 7. 변경 이력 (이 카드)

> append-only. 정본 변경은 `unit/feature-0044-qa-staging-pipeline/docs/MODIFY.md` 에.

- 2026-08-26: 초안 작성 — 설계 제안 rev.1 cycle 동반 생성
- 2026-08-27: rev.2 반영 — 전제 2건이 뒤집혀(사내 저장소·레지스트리 부재 / 라이브 분리 확정)
  전달 수단을 tar 릴레이로 재설계하고 권장 스펙을 실측 산출
- 2026-08-27: rev.3 반영 — 로컬 LLM 실측(chat 축 이미 제거 · 임베딩만 잔존 = 유일 GPU 소비자)
  으로 **GPU 요구 소거**, 스펙 하향(8~12 vCPU / 32GB / 400GB), SVN 안 A 확정, §9 이관 절 신설
