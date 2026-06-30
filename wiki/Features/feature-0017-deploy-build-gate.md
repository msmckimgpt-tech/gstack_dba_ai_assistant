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
maturity: minimal
ai_generated: true
feature_id: feature-0017-deploy-build-gate
linked_unit: unit/feature-0017-deploy-build-gate
created: 2026-06-30
sources:
  - ../../unit/feature-0017-deploy-build-gate/docs/FUNCTION.md
---

# Feature — deploy 빌드 게이트 snap-docker race 수정

> 정본은 [[../../unit/feature-0017-deploy-build-gate/docs/FUNCTION|FUNCTION.md]].

## 1. 한 줄 요약
무중단 배포 스파인(`bin/deploy-web.sh`)의 빌드 게이트가 snap-docker metadata-file race(이미지는 정상
빌드되나 compose 가 /tmp metadata 못 읽어 EXIT 1)로 **모든 web 배포를 false-failure 차단**하던 버그를,
이미지 존재+GIT_COMMIT 정합 검증으로 수정.

## 2. 상태
- **단계**: review — 격리 검증(positive/negative) 완료. 라이브 end-to-end 는 머지 후 deploy-web.sh 실행.
- **마지막 갱신**: 2026-06-30 · claude / Human(PLAN-APPROVED).

## 3. 책임 경계
- (in) compose build exit code + 로그 + 산출 이미지 → (out) 이미지 정상 시 통과(EXIT≠0+metadata-race
  마커면 양성무시), 진짜 실패 ABORT. swap/rollback/soak 무변경.

## 4. 관련 정본
- [[../../unit/feature-0017-deploy-build-gate/docs/FUNCTION|FUNCTION.md]] · [[../../unit/feature-0017-deploy-build-gate/docs/TASK|TASK.md]] · [[../../unit/feature-0017-deploy-build-gate/docs/ANCHOR|ANCHOR.md]]

## 5. 관련 노트
- [[feature-0014-zero-downtime-deploy]] — deploy-web.sh(본 게이트가 거주) · [[feature-0006-lan-proxy-access]]

## 6. Open questions / 후속
- snap docker → apt docker-ce 이전(근본 환경 정비, 시스템/admin 영역 — 사용자 결정).

## 7. 변경 이력 (이 카드)
- 2026-06-30: 초안(게이트 수정 반영).
