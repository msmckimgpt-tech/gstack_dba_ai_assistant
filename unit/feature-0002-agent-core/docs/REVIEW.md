---
doc_type: REVIEW
feature_id: feature-0002-agent-core
status: active
edit_policy: append-only
source_of_truth: true
---

# Review Log

## REV-20260515-0003
- Date: 2026-05-15
- Decision: Account scope의 `ProductId IS NULL` 프롬프트도 Role scope 와 동일하게 fallback 이 아니라 항상 누적되는 공통 지침으로 해석한다. 전체 적용 순서는 `Product context → Role guidance → Account preferences → 현재 user message` 로 유지한다.
- Reason: 사용자가 의도한 구조는 Product, Role, Account, 요청이 순서대로 쌓이는 것이다. 기존 구현은 Product/Role/Account/user message 의 큰 순서는 맞았지만, Account Product 전용 프롬프트가 있으면 Account 공통 프롬프트가 누락될 수 있었다. 개인 기본 지침은 특정 Product 선택 이후에도 유지되어야 하므로 누적 방식이 맞다.
- Additional Fix: `_fetch()`가 특정 Product prompt 조회에서 miss 가 나면 공통 prompt 로 fallback 하던 동작은 Role/Account block 누적 구조에서는 중복 원인이 된다. 특정 Product 조회는 exact match 만 반환하고, 공통 조회는 별도 호출로 분리했다.
- Risk:
  - Account 공통 + Product 전용 개인 지침이 모두 있으면 prompt 길이가 증가한다. 하지만 개인 공통 지침 누락은 사용자 선호/제약 누락으로 이어져 더 위험하다.
  - 현재 사용자 요청은 system prompt 안에 복제하지 않고 마지막 `user` 메시지로 유지한다. 이는 대화형 LLM API의 역할 분리에 맞으며, 요청 원문 손상을 피한다.

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
