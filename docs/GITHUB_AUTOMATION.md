# GitHub Automation

## 개요
- 이 저장소의 자동화는 공개 PR 기준으로 **이슈당 하나의 `issue/*` 브랜치**를 사용한다.
- 여러 AI가 병렬 작업할 수 있지만, 내부 병렬 작업 브랜치는 로컬/worktree 전용이다.
- 지원되는 provider 는 `claude` 하나이며, **self-hosted runner 에 설치된 공식 `claude` CLI 를 직접 호출**한다. `anthropics/claude-code-action@v1` 은 사용하지 않는다 (Anthropic 이 2026-02 이후 Pro/Max OAuth 토큰을 서버 측에서 거부하기 때문).
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
- Secrets — 현재 Claude 경로는 self-hosted runner 의 로컬 `~/.claude/` 자격 증명을 사용하므로 **API key / OAuth 토큰 시크릿이 필요 없다.**
- Variables
  - `AI_PROVIDER_DEFAULT` — 선택. 설정하지 않으면 `.github/automation-contract.json` 의 기본값(`claude`)이 사용된다.
  - `AI_AUTONOMOUS_OPEN_ISSUE_LIMIT` 기본 권장값 `3`

## Self-hosted runner 기준
- Linux/WSL 기반
- Docker와 `make` 사용 가능
- `make start`, `make ask`, `make web`, `make browser-up`, `make browser-health` 실행 가능
- 런타임 충돌 방지를 위해 self-hosted smoke는 저장소 단위 concurrency 로 직렬화한다.
- **Image 빌드 책임**: `selfhosted-runtime-smoke.yml` 은 `make start` 가 내부적으로 `docker compose build` 를 수행하므로 image 사전 빌드를 운영자에게 요구하지 않는다. PR 의 Dockerfile / build context 변경이 매번 검증된다. 워크플로 env 블록의 `COMPOSE_PROJECT_NAME=repo` 가 image 이름을 workspace 디렉토리와 분리해 `Makefile:77-80` 의 `repo-*` 검증과 일치시킨다 — workspace 가 `_work/<repo>/<repo>` 형태여도 image 는 `repo-agent` 등으로 안정 생성된다.
- **`.env` provisioning**: 워크플로는 runner-local `.env` 파일을 PR 워크스페이스로 복사한 뒤 smoke 를 실행한다. 기본 경로는 `~/.mysql_ai_smoke.env` 이며 저장소 var `SMOKE_ENV_PATH` 로 override 가능하다. 운영자가 이 파일에 실제 LLM / DB 자격 증명을 provision 한다 (저장소에 commit 하지 않는다). 파일이 없으면 워크플로는 `.env.example` 로 fallback 하지만 `make ask` 등 LLM 의존 step 은 실패할 수 있다.
- **Runner user 는 반드시 non-root** — claude CLI 의 `--permission-mode bypassPermissions` 는 내부적으로 `--dangerously-skip-permissions` 로 매핑되며, uid 0 (root/sudo) 에서 실행하면 보안상 거부되어 `ai-review.yml` 의 `Run Claude review` step 이 즉시 exit 1 한다 (관측 사례: PR #6 / run 25545926914). systemd 서비스로 등록할 때 `./svc.sh install <runner-user>` 의 `<runner-user>` 를 root 가 아닌 별도 user 로 지정해야 한다.
- **Claude CLI 요구사항**: `claude --version` 이 동작해야 하며, **runner user 계정** (위의 non-root user) 으로 `claude /status` 가 "Login method: Claude Pro/Max account" 를 반환하는 상태여야 한다. AI Triage/Execute/Review 워크플로는 runner user 의 `~/.claude/` 자격 증명을 그대로 사용한다 — runner user 를 변경하면 새 home 에서 `claude login` 을 다시 수행해야 한다.
- **러너 온라인 유지**: `ai-triage.yml` 은 스케줄 실행 (`cron: "17 */6 * * *"`) 이므로 해당 시간대에 runner 가 오프라인이면 실행이 지연되거나 timeout 된다. systemd 서비스 또는 WSL 자동 시작 스크립트 등으로 runner 프로세스를 상시 유지하는 것을 권장한다.

### 러너 셋업 (요약)
1. **non-root user 준비** — root 가 아닌 dedicated user (예: `runner`, `gh-runner`) 를 미리 만들어 두고 docker / make 가 해당 user 로 실행 가능하도록 docker 그룹에 추가한다 (`usermod -aG docker <runner-user>`).
2. `https://github.com/msmckimgpt-tech/gstack_dba_ai_assistant/settings/actions/runners/new` 에서 Linux x64 runner 등록 스크립트 확인.
3. 해당 user 의 home (예: `/home/<runner-user>/actions-runner/`) 에 설치.
4. `./config.sh --url https://github.com/msmckimgpt-tech/gstack_dba_ai_assistant --token <register-token> --labels self-hosted,linux --unattended` (해당 user 로 실행).
5. 서비스로 설치: `sudo ./svc.sh install <runner-user> && sudo ./svc.sh start` — `<runner-user>` 인자에 **반드시 non-root user 이름** 을 명시. 빠뜨리면 systemd 가 root 로 기동한다.
6. **runner user 계정에서 `claude login`** 수행 — `claude --version` 동작 확인 + `~/.claude/.credentials.json` 생성 확인.
7. `gh api /repos/msmckimgpt-tech/gstack_dba_ai_assistant/actions/runners` 로 등록 여부 확인.
8. 첫 PR 또는 `gh workflow run ai-review.yml` 로 Diagnose Claude CLI environment step 이 PASS 하는지 확인 (`runner uid: <0 이외의 숫자>` 가 `$GITHUB_STEP_SUMMARY` 에 노출되어야 한다).
9. **Smoke `.env` provision**: runner user 계정에 `~/.mysql_ai_smoke.env` 를 작성한다 (모드 600 권장). repo 의 `.env.example` 을 base 로 OPENAI_API_KEY / DB 비밀번호 등 실제 자격 증명을 채운다. 다른 경로를 쓰려면 GitHub repo settings 의 Variables 에 `SMOKE_ENV_PATH` 를 절대 경로로 등록한다.
10. `llm-shared` docker network 가 runner 에 존재해야 한다 (`docker network ls | grep llm-shared`). 없으면 `/root/download/docker/local_llm` 의 provider 부터 기동한다 — `Makefile:36-40` 의 `check-llm-network` 가 fail-loud 로 차단한다.

### 기존 root runner 마이그레이션 절차
이미 root 로 systemd service 를 등록한 환경에서는 아래 순서로 전환한다.

```bash
# 1. 기존 root service 정지/제거
cd /root/actions-runner
sudo ./svc.sh stop
sudo ./svc.sh uninstall
./config.sh remove --token <removal-token>   # GitHub UI 의 runner 페이지에서 발급

# 2. non-root user 로 재설치
sudo useradd -m -s /bin/bash gh-runner   # 이미 있다면 skip
sudo usermod -aG docker gh-runner
sudo -iu gh-runner
mkdir -p ~/actions-runner && cd ~/actions-runner
# (위 §러너 셋업 4 ~ 8 반복)

# 3. claude login 재수행 (gh-runner 계정 home 에서)
claude login
claude /status   # "Login method: Claude Pro/Max account" 확인
```

마이그레이션 직후 PR 한 건을 reopen 또는 trivial commit push 로 ai-review 를 1회 강제 실행해 Diagnose step 에서 `runner uid` 가 0 이 아닌지 확인한다. 0 이면 systemd unit 의 `User=` 가 여전히 root 임 — `systemctl cat actions.runner.*.service` 로 검증.

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
- 공개 PR 브랜치 규칙 검증 (`issue/*`) — 내부 `feat/*`, `chore/*`, `ai/*` 브랜치는 공개 `issue/*` 브랜치로 통합 후에만 PR head 가 될 수 있다 (`AGENTS.md §13.2`, §16.5 Step 5.1).
- PR 제목 / `closes #<issue>` 규칙 검증 — 제목은 `#<issue> <summary>` 또는 `<type>(<scope>): <summary> (#<issue>)` 두 형식 모두 허용 (`automation-contract.json#pull_requests.title_regex_forms`). 두 형식 모두에서 branch 의 issue 번호와 title 의 issue 번호가 일치해야 한다.
- `.env` 제외 검증
- 커밋 제목 형식 검증 (`type(scope): summary (#issue)`)
- `.github/automation-contract.json`과 문서/스크립트 정합성 검증

### 내부 브랜치 통합 절차

`gh pr create` 를 내부 `feat/*` / `chore/*` / `ai/*` 브랜치에서 직접 실행하면 `policy-contract` 의 branch 규칙 단계에서 fail 한다. 통합 절차는 다음과 같다.

```bash
# 1. 내부 브랜치에서 작업 완료 (예: feat/add-foo)
git switch feat/add-foo

# 2. 공개 issue/* 브랜치 생성 (이슈 번호에 맞춰)
git switch -c issue/<n>-<short-slug>

# 3. 필요 시 origin/main 에 rebase
git fetch origin && git rebase origin/main

# 4. push 및 PR 생성
git push -u origin issue/<n>-<short-slug>
gh pr create --title "<type>(<scope>): <summary> (#<n>)" --body "... closes #<n> ..."
```

## 자동 이슈 생성 기준
- `ai-triage`는 한 번에 최대 1개 이슈만 생성한다.
- 이슈 본문에 `<!-- ai-fingerprint:... -->` 를 넣어 중복 생성을 방지한다.
- `source:autonomous` 열린 이슈 수가 `AI_AUTONOMOUS_OPEN_ISSUE_LIMIT` 이상이면 새 이슈를 만들지 않는다.
