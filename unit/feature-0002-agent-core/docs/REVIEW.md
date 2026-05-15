---
doc_type: REVIEW
feature_id: feature-0002-agent-core
status: active
edit_policy: append-only
source_of_truth: true
---

# Review Log

## REV-20260515-0002
- Date: 2026-05-15
- Decision: Role scope의 `ProductId IS NULL` 프롬프트를 fallback 전용이 아니라 항상 누적되는 공통 지침으로 해석한다.
- Reason: 관리 콘솔의 Role detail 에서 "전 Product 공통"으로 입력한 지침은 특정 Product 선택 이후에도 역할 전체의 기본 행동 규칙으로 적용되어야 한다. 기존 구현은 Role×Product 프롬프트가 있으면 공통 지침을 버렸기 때문에 UI 문구와 런타임 의미가 어긋났다.
- Alternatives:
  - 기존 fallback 유지: 특정 Product별 세부 지침이 생기는 순간 Role 기본 지침이 사라져 사용자 의도와 불일치한다.
  - Product prompt에 Role 공통 내용을 복제: 중복 진실이 생기고 Role 변경 시 모든 Product prompt를 수정해야 하므로 거부.
- Risk:
  - Role 공통 지침이 길어지면 모든 pinned Product 대화의 시스템 프롬프트가 늘어난다. 다만 역할 지침은 운영 정책 성격이라 누락 비용이 중복 비용보다 크다.
  - account scope는 기존 우선순위/ fallback 의미를 유지했다. 이번 요청은 Role의 `전 Product 공통` 동작에 한정된다.

## REV-20260326-0001
- Date: 2026-03-26
- Decision: agent 이미지는 core feature Dockerfile에서 web-ui feature 소스를 함께 복사한다
- Reason: import 경로를 깨지 않으면서 기능 소유권을 분리하기 위함
- Risk: 이미지 빌드 경로가 루트 context에 의존한다
