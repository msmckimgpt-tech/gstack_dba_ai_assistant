# GitHub Automation

## 개요
- 이 저장소의 자동화는 공개 PR 기준으로 **이슈당 하나의 `issue/*` 브랜치**를 사용한다.
- 여러 AI가 병렬 작업할 수 있지만, 내부 병렬 작업 브랜치는 로컬/worktree 전용이다.
- 지원되는 provider 는 `claude` 하나이며, Claude Code GitHub Action (`anthropics/claude-code-action@v1`) 으로 실행된다.
- 정본 흐름은 `Issue -> Branch -> PR -> Status Checks -> GitHub auto-merge` 이다.
- 공개 PR 브랜치는 항상 `issue/<번호>-<short-slug>`를 사용한다.
- 내부 병렬 작업 브랜치는 `ai/<agent-id>/<issue-number>/<slice>` 형식을 사용하며, PR head로 직접 사용하지 않는다.

## Provider 선택
- 우선순위 1: Issue 또는 PR 라벨 `agent:claude`
- 우선순위 2: 저장소 변수 `AI_PROVIDER_DEFAULT`
- 우선순위 3: 기본값 `claude`
- `agent:claude` 외의 `agent:*` 라벨(예: `agent:codex`)이 붙은 경우 정책 오류로 처리한다.

## 워크플로
- `ai-triage.yml`: 저장소 신호를 읽고 필요 시 autonomous issue 1건 생성
- `ai-execute.yml`: 실행 가능 이슈를 공개 `issue/*` 브랜치/PR로 전개
- `ai-review.yml`: 활성 provider가 PR 검토 수행
- `policy-contract.yml`: 브랜치/PR/자동병합 계약과 문서-자동화 정합성 검증
- `owner-agent-report.yml`: 현재 PR의 활성 provider와 위험 요약 게시
- `selfhosted-runtime-smoke.yml`: self-hosted Linux runner에서 런타임 검증 수행

## 라벨 계약
- provider: `agent:claude`
- source: `source:human`, `source:autonomous`
- status: `status:ready`, `status:in-progress`, `status:in-review`, `status:blocked`
- merge: `automerge:candidate`, `risk:manual`, `needs-followup`

`status:ready`는 권장 라벨이다.
- Issue Template과 `ai-triage`는 기본값으로 이 라벨을 붙일 수 있다.
- `ai-execute`의 필수 gate는 타입 라벨(`feature`, `bug`, `task`)과 차단 상태 부재다.
- 실행이 시작되면 `status:ready`는 제거되고 `status:in-progress`로 전환된다.

## 필수 Secrets / Variables
- Secrets
  - `CLAUDE_CODE_OAUTH_TOKEN` — 로컬에서 `claude setup-token` 으로 발급한 Claude Pro/Max OAuth 토큰. 만료 시 주기적 갱신이 필요하다.
- Variables
  - `AI_PROVIDER_DEFAULT` — 선택. 설정하지 않으면 `.github/automation-contract.json` 의 기본값(`claude`)이 사용된다.
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

`policy-contract` 체크 안에는 다음 검증이 포함된다.
- 공개 PR 브랜치 규칙 검증 (`issue/*`)
- PR 제목 / `closes #<issue>` 규칙 검증
- `.env` 제외 검증
- 커밋 제목 형식 검증 (`type(scope): summary (#issue)`)
- `.github/automation-contract.json`과 문서/스크립트 정합성 검증

## 자동 이슈 생성 기준
- `ai-triage`는 한 번에 최대 1개 이슈만 생성한다.
- 이슈 본문에 `<!-- ai-fingerprint:... -->` 를 넣어 중복 생성을 방지한다.
- `source:autonomous` 열린 이슈 수가 `AI_AUTONOMOUS_OPEN_ISSUE_LIMIT` 이상이면 새 이슈를 만들지 않는다.
