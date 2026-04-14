# GitHub Automation

## 개요
- 이 저장소의 자동화는 "동시에 여러 AI를 병렬 투입"하지 않는다.
- 한 시점에는 하나의 provider만 활성화하며, provider는 `codex` 또는 `claude` 중 하나다.
- 정본 흐름은 `Issue -> Branch -> PR -> Status Checks -> GitHub auto-merge` 이다.

## Provider 선택
- 우선순위 1: Issue 또는 PR 라벨 `agent:codex`, `agent:claude`
- 우선순위 2: 저장소 변수 `AI_PROVIDER_DEFAULT`
- 우선순위 3: 기본값 `codex`
- 한 Issue 또는 PR에 두 provider 라벨을 동시에 붙이면 정책 오류로 처리한다.

## 워크플로
- `ai-triage.yml`: 저장소 신호를 읽고 필요 시 autonomous issue 1건 생성
- `ai-execute.yml`: ready 상태의 이슈를 브랜치/PR로 전개
- `ai-review.yml`: 활성 provider가 PR 검토 수행
- `policy-contract.yml`: 브랜치/PR/자동병합 계약 검증
- `owner-agent-report.yml`: 현재 PR의 활성 provider와 위험 요약 게시
- `selfhosted-runtime-smoke.yml`: self-hosted Linux runner에서 런타임 검증 수행

## 라벨 계약
- provider: `agent:codex`, `agent:claude`
- source: `source:human`, `source:autonomous`
- status: `status:ready`, `status:in-progress`, `status:in-review`, `status:blocked`
- merge: `automerge:candidate`, `risk:manual`, `needs-followup`

## 필수 Secrets / Variables
- Secrets
  - `OPENAI_API_KEY`
  - `ANTHROPIC_API_KEY`
- Variables
  - `AI_PROVIDER_DEFAULT`
  - `AI_AUTONOMOUS_OPEN_ISSUE_LIMIT` 기본 권장값 `3`

## Self-hosted runner 기준
- Linux/WSL 기반
- Docker와 `make` 사용 가능
- `make start`, `make ask`, `make web`, `make browser-up`, `make browser-health` 실행 가능
- 런타임 충돌 방지를 위해 self-hosted smoke는 저장소 단위 concurrency 로 직렬화한다.

## Branch protection 권장값
- Require pull request before merging
- Require status checks before merging
- Require conversation resolution before merging
- Dismiss stale approvals
- Require approval of the most recent reviewable push
- Do not allow bypassing the above settings
- Allow auto-merge
- private 저장소 플랜 제약으로 branch protection 또는 auto-merge API 적용이 막힐 수 있다.
- 이 경우 워크플로와 라벨 계약은 그대로 유지하고, GitHub 플랜 또는 저장소 공개 상태가 바뀐 뒤 보호 규칙을 다시 활성화한다.

## Required status checks
- `policy-contract`
- `selfhosted-runtime-smoke`
- `ai-review`
- `owner-agent-report`

## 자동 이슈 생성 기준
- `ai-triage`는 한 번에 최대 1개 이슈만 생성한다.
- 이슈 본문에 `<!-- ai-fingerprint:... -->` 를 넣어 중복 생성을 방지한다.
- `source:autonomous` 열린 이슈 수가 `AI_AUTONOMOUS_OPEN_ISSUE_LIMIT` 이상이면 새 이슈를 만들지 않는다.
