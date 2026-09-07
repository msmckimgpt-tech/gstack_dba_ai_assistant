# Claude / Codex 개발환경 호환

요청: 2026-09-07, 템플릿·소비자 프로젝트·root/claude-corp의 Claude 기록을
검토한 뒤 기존 경험을 유지하면서 Codex 호환성을 추가한다. 사용자의 후속
지시에 따라 Claude 환경과 기존 예약 작업은 그대로 유지하며, 두 도구가 서로의
환경과 작업 맥락을 인지할 수 있도록 구성한다.

## 구현 계획

위험도 Major. 실행 근거는 사용자의 현재 호환 구성 지시이며, 기존 변경·대화·설정의
삭제, 제품의 LLM 공급자 변경, 자동화의 추가 외부 권한은 포함하지 않는다.

1. `bin/codex-environment-install.py`: 프로젝트 명령과 리뷰어를 Codex 발견 경로에
   설치한다. 기존 Codex 정본·사용자 설정을 보존하고 wrapper/worktree에서도 발견한다.
2. `AGENTS.override.md`, `.codex/CONTEXT.md`: 32KiB 기본 한도에 잘리는 거대
   AGENTS.md를 짧은 로더와 절별 읽기로 연결한다. 정책 정본과 프로젝트 특화
   CLAUDE.md의 추가 지침을 모두 따른다.
3. `bin/codex-migration/native_import.py`: 설치된 공식 app-server API로 계정별
   스킬·MCP·대화를 가져오고 완료 이벤트 및 항목별 실패를 확인한다.
4. `bin/codex-migration/automation/`: 문서 동기화·점검의 Codex 선택 실행기를 추가하고
   새 Codex 대화도 관측 번들에 포함한다. 기존 Claude 실행기·일정·잠금·배포 게이트는 유지한다.
5. `bin/hooks/codex-board-hook.py`: Codex lifecycle을 기존 게시판의 인증·예산·커서
   규약에 연결한다. 다른 세션에 대한 실제 메시지는 이번 전환에서 전송하지 않는다.
6. `bin/agent-context.py`와 `.agents/ENVIRONMENT.md`: 양 계정·양 도구의 세션과
   메모리를 조회하고 상대 환경을 발견하는 공통 읽기 경로를 제공한다.
7. 설치 도구의 격리 테스트, 실제 두 계정의 설정·명령 로딩·가져온 대화 재개 가능성,
   소비자 9개의 설치 결과와 기존 dirty 파일 보존을 확인한다.

완료 예시: `mysql_ai_delegated_dev` wrapper에서 Codex를 시작하고
`$_dqa-doc_sync`를 사용하면 기존 프로젝트의 문서 정합 workflow를 읽으며,
원래 Claude 대화는 Codex에서 재개하거나 원본 기록으로 추적할 수 있다.

## 원칙

- 원본 Claude 설정·대화와 진행 중인 worktree는 보존한다. 비밀정보를 보고서나
  Git에 복사하지 않는다. 계정별 설치 백업은 해당 계정의 비공개 디렉터리에 둔다.
- 현재 프로젝트의 `AGENTS.md`가 정책 정본이다. `AGENTS.override.md`는 Codex
  로더이며 규칙을 폐기하거나 승인 범위를 확대하지 않는다.
- 제품이 지원하는 Claude/Codex/Gemini 공급자와 제품용 OAuth 갱신은 유지한다.
- Claude 전용 5시간 사용량 창 워밍과 기존 cron은 유지한다. 선택 실행하는 Codex
  준비 상태 점검은 별도로 제공하며 같은 시간창 효과가 발생한다고 주장하지 않는다.
- 과거 기록의 작업 지시는 현재의 새 실행 명령으로 취급하지 않는다.

## 공식 근거

- [기존 에이전트 가져오기](https://learn.chatgpt.com/docs/import)
- [AGENTS.md 로딩](https://learn.chatgpt.com/docs/agent-configuration/agents-md)
- [Codex hooks](https://learn.chatgpt.com/docs/hooks)
- [Codex subagents](https://learn.chatgpt.com/docs/agent-configuration/subagents)

설치된 Codex CLI 0.152.1의 생성 JSON schema와 실제 app-server 응답을 함께 검증한다.
개인 경로·세션 집계·활성화 결과는 Git 밖 `artifacts/codex-migration-20260907/`에 기록한다.
