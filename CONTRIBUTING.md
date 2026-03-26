# Contributing

## 1. 기본 원칙
- 이 저장소의 정본 작업 루트는 현재 디렉토리(`.`)이다.
- 로컬 전용 파일인 `.env`는 Git에 올리지 않는다.
- 작업은 GitHub Issue를 기준으로 나누고, 구현은 브랜치와 PR로 병합한다.
- 구현 전에 `AGENTS.md`, `README.md`, 관련 feature 문서를 먼저 읽는다.

## 2. 원격 연결
- 원격 저장소: `git@github.com:msmckimgpt-tech/ai_desk_mysql.git`
- SSH 키: `~/.ssh/mckim_wsl`
- 권장 설정:

```bash
export GIT_SSH_COMMAND='ssh -i ~/.ssh/mckim_wsl -o IdentitiesOnly=yes'
```

## 3. 작업 흐름
1. GitHub Issue를 생성한다.
2. 이슈 번호를 기준으로 브랜치를 만든다.
3. 구현과 문서 갱신을 함께 수행한다.
4. PR을 열고 검증 결과와 리스크를 적는다.
5. 리뷰 후 `main`에 병합한다.
6. Issue를 종료한다.

## 4. 브랜치 / PR 규칙
- 브랜치 이름: `issue/<issue-number>-<short-slug>`
- PR 제목: `#<issue-number> <summary>`
- `main`에는 직접 push 하지 않는다.

예시:

```bash
git switch main
git pull --ff-only origin main
git switch -c issue/12-fix-browser-session-cleanup
```

## 5. 이슈 작성 규칙
- 이슈 타입은 `feature`, `bug`, `task`만 사용한다.
- 아래 항목은 항상 채운다.
  - 목표/배경
  - 대상 feature 또는 경로
  - 성공 기준
  - 검증 방법
  - 제약사항
  - 참고 로그/문서 위치

## 6. PR 작성 규칙
- PR 본문에는 변경 요약, 검증 결과, 리스크, 문서 갱신 여부를 포함한다.
- 실행 검증을 못 했다면 이유를 적는다.
- follow-up이 필요한 항목은 숨기지 않고 남긴다.

## 7. Codex 작업 기준
- Codex는 Issue 내용을 작업 계약으로 사용한다.
- 브랜치 이름과 PR 제목은 이슈 번호를 기준으로 맞춘다.
- 이슈에 검증 방법이 없으면 먼저 문서와 로그를 확인해 보완한다.
- 작업 후 `README.md`, `docs/STATUS.md`, feature 문서가 현실과 어긋나지 않는지 확인한다.

## 8. GitHub 저장소 권장 설정
- 기본 브랜치는 `main`으로 유지한다.
- 가능하면 branch protection을 켠다.
- 최소 권장값:
  - direct push 제한
  - PR merge 기준 사용
  - stale branch 자동 정리는 선택
