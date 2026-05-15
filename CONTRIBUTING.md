# Contributing

## 1. 기본 원칙
- 이 저장소의 정본 작업 루트는 현재 디렉토리(`.`)이다.
- 로컬 전용 파일인 `.env`는 Git에 올리지 않는다.
- 작업은 GitHub Issue를 기준으로 나누고, 구현은 브랜치와 PR로 병합한다.
- 구현 전에 `AGENTS.md`, `README.md`, 관련 feature 문서를 먼저 읽는다.
- AI 작업자는 완료 가능한 cycle의 commit/push 결정을 사용자에게 위임하지 않고 `AGENTS.md §16.5`에 따라 수행한다.
- GitHub 자동화 기준은 `docs/GITHUB_AUTOMATION.md`를 따른다.

## 2. 원격 연결
- 원격 저장소: `git@github.com:msmckimgpt-tech/ai_desk_mysql.git`
- SSH 키: `~/.ssh/mckim_wsl`
- 권장 설정:

```bash
export GIT_SSH_COMMAND='ssh -i ~/.ssh/mckim_wsl -o IdentitiesOnly=yes'
```

### 2.1 병렬 AI 브랜치 전략

두 개 이상의 AI가 동시에 작업하는 경우, 내부 작업 브랜치와 공개 PR 브랜치를 분리한다.

- **내부 병렬 브랜치:** `ai/<agent-id>/<issue-number>/<slice>`
- **공개 PR 브랜치:** `issue/<issue-number>-<short-slug>`
- **Worktree 격리 (권장):**
  ```bash
  git worktree add ../worktrees/issue-12 -b ai/claude/12/browser-cleanup
  ```
- 내부 병렬 브랜치는 로컬/worktree 전용이며, PR head로 직접 사용하지 않는다.
- 작업 완료 후 공개 `issue/*` 브랜치에 통합하고 PR을 갱신한 뒤 worktree를 제거한다.
- 동일 shared 모듈을 두 AI가 동시에 수정하는 것은 금지한다.
- 프로젝트 수준 문서(STATUS.md, ARCHITECTURE.md 등)는 공개 `issue/*` 브랜치 통합 시에만 갱신한다.
- 상세 규칙은 `AGENTS.md` §13.2를 참조한다.

## 3. 작업 흐름
1. GitHub Issue를 생성한다.
2. 필요하면 `agent:claude` 라벨로 provider를 명시한다 (현재 지원 provider 는 `claude` 하나).
3. 이슈에 `feature`, `bug`, `task` 중 하나의 타입 라벨이 있고 차단 상태가 없으면 활성 provider가 브랜치와 PR을 생성한다.
4. `status:ready`는 권장 라벨이며, Issue Template과 `ai-triage`가 기본값으로 붙일 수 있지만 실행의 필수 gate는 아니다.
5. PR에서 `policy-contract`, `owner-agent-report`, `ai-review`, `selfhosted-runtime-smoke`를 통과한다.
6. `risk:manual`이 없으면 GitHub auto-merge 후보가 된다.
7. 병합 후 Issue를 종료한다.

## 4. 브랜치 / PR 규칙
- 공개 PR 브랜치: `issue/<issue-number>-<short-slug>`
- 내부 병렬 브랜치: `ai/<agent-id>/<issue-number>/<slice>` (로컬/worktree 전용, PR 금지)
- 내부 작업 브랜치 (`feat/*`, `chore/*`, `ai/*`) 는 공개 `issue/*` 브랜치로 통합한 뒤 PR 을 연다.
- PR 제목은 다음 두 형식 중 하나를 사용한다 (`automation-contract.json#pull_requests.title_regex`):
  - `#<issue-number> <summary>` — 사람이 GitHub UI 에서 짧게 작성할 때.
  - `<type>(<scope>): <summary> (#<issue-number>)` — `gh pr create` 가 first commit subject 를 그대로 PR 제목으로 채울 때 (§5.2 commit 형식과 동일).
  - 두 형식 모두에서 `closes #<issue-number>` 는 PR 본문에 반드시 포함한다.
- `main`에는 직접 push 하지 않는다.

예시:

```bash
git switch main
git pull --ff-only origin main
git switch -c issue/12-fix-browser-session-cleanup
```

## 5. 커밋 메시지 규칙

### 5.1 형식
커밋 메시지는 **제목 + 빈 줄 + 본문** 구조를 따른다.

```
<type>(<scope>): 작업 내용 한 줄 요약 (#<issue-number>)

- 상세 변경사항 1
- 상세 변경사항 2
- 상세 변경사항 3
```

### 5.2 제목 (subject line)
- `<type>(<scope>): <요약> (#<issue-number>)` 형식을 사용한다.
- 커밋 유형(`type`): `feat`, `fix`, `docs`, `refactor`, `test`, `chore`
- 범위(`scope`): 기능 ID (예: `feature-0001`) 또는 `project`, `shared`
- 범위를 안전하게 특정할 수 없으면 `project`를 기본 scope로 사용한다.
- 요약은 무엇을 했는지 한 줄로 명확히 작성한다.

### 5.3 본문 (body)
- 제목 아래 빈 줄을 하나 두고 불릿(`-`) 목록으로 상세 내용을 작성한다.
- 각 불릿은 코드 변경, 문서 갱신, 설정 변경 등 구체적 작업 단위를 기술한다.
- 사소한 변경(오타 수정, 단일 파일 변경 등)은 본문을 생략할 수 있다.

### 5.4 예시
```
feat(feature-0002): agent-core 세션 관리 개선 (#12)

- src/session_manager.py: 타임아웃 기반 세션 정리 로직 추가
- tests/test_session.py: 만료 세션 정리 시나리오 테스트 작성
- docs/FUNCTION.md: 세션 타임아웃 파라미터 명세 갱신
```

## 6. 이슈 작성 규칙
- 이슈 타입은 `feature`, `bug`, `task`만 사용한다.
- 아래 항목은 항상 채운다.
  - 목표/배경
  - 대상 feature 또는 경로
  - 성공 기준
  - 검증 방법
  - 제약사항
  - 참고 로그/문서 위치
- 사람 손으로 만든 이슈는 `source:human`, 자동 생성 이슈는 `source:autonomous`를 사용한다.
- 자동 실행 기본 provider는 저장소 변수 `AI_PROVIDER_DEFAULT`를 따르며, 특정 이슈에서만 `agent:*` 라벨로 override 한다.

## 7. PR 작성 규칙
- PR 본문에는 변경 요약, 검증 결과, 리스크, 문서 갱신 여부를 포함한다.
- 실행 검증을 못 했다면 이유를 적는다.
- follow-up이 필요한 항목은 숨기지 않고 남긴다.

## 8. AI 작업 기준
- 활성 provider는 Issue 내용을 작업 계약으로 사용한다.
- 브랜치 이름과 PR 제목은 이슈 번호를 기준으로 맞춘다.
- 공개 브랜치는 항상 `issue/*`를 사용하고, 내부 `ai/*` 브랜치는 로컬/worktree에서만 사용한다.
- 이슈에 검증 방법이 없으면 먼저 문서와 로그를 확인해 보완한다.
- 작업 후 `README.md`, `docs/STATUS.md`, `docs/GITHUB_AUTOMATION.md`, feature 문서가 현실과 어긋나지 않는지 확인한다.
- 한 이슈와 한 PR에는 하나의 provider만 활성화한다.
- `AGENTS.md`의 Git 동기화 절차에 따라 Git 커밋 및 동기화를 수행한다.
  - **항상**: §5 커밋 메시지 규칙에 따라 커밋한다.
  - **공개 동기화 조건 충족 시**: 원격 `issue/*` 브랜치 push 및 PR 생성/갱신까지 수행한다.

## 9. GitHub 저장소 권장 설정
- 기본 브랜치는 `main`으로 유지한다.
- 가능하면 branch protection을 켠다.
- 최소 권장값:
  - direct push 제한
  - PR merge 기준 사용
  - required status checks: `policy-contract`, `owner-agent-report`, `ai-review`, `selfhosted-runtime-smoke`
  - auto-merge 활성화
  - stale branch 자동 정리는 선택
