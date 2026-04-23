---
doc_type: PROJECT_STATUS
scope: project
status: active
edit_policy: rewrite
source_of_truth: true
---

# Project Status

프로젝트 전체 현황을 한눈에 파악하기 위한 문서이다.

> 2026-04-23: origin 을 `git@github.com:msmckimgpt-tech/gstack_dba_ai_assistant.git` 으로 전환하고 gstack 스킬 워크플로우와 공존하는 체계로 마이그레이션했다 (`CLAUDE.md §Skill routing`, 신설 `TODOS.md`). feature 단위 작업 기록은 기존 `unit/feature-NNNN/docs/*` 그대로 유지하며, gstack 스킬 호출 시에도 `AGENTS.md` / `CONTRIBUTING.md` 가 우선 적용된다.

## 1. 기능 현황

| 기능 ID | 상태 | 담당 | 최종 갱신 | 비고 |
|---------|------|------|----------|------|
| feature-0001-platform-runtime | in-progress | AI | 2026-04-15 | MySQL runtime 경계 유지, 내장 Local LLM bootstrap 제거 |
| feature-0002-agent-core | in-progress | AI | 2026-04-15 | 외부 `local_llm` gateway 소비 계약 정리 |
| feature-0003-agent-web-ui | in-progress | AI | 2026-04-22 | TASK-0041 클라이언트 타임아웃 Attach/Resume(ask_status/ask_result 엔드포인트 + 브라우저 복구 다이얼로그 + runner attach), TASK-0040 SQL whitelist 정규식 context-aware 2-stage 재작성, TASK-0034 Q4/Q5 재수행 완료 |
| feature-0004-browser-automation | in-progress | AI | 2026-04-06 | 구조 이관 완료, smoke 검증 예정 |
| feature-0005-qa-mcp | in-progress | AI | 2026-04-06 | 포트 28000 점유 해소 확인, MCP 기동 검증 예정 |
| feature-0006-lan-proxy-access | in-progress | AI | 2026-04-06 | 운영 자산 이관 완료 |

### 상태 값 정의
- `planned`: 요구사항 정리 단계
- `in-progress`: 구현 진행 중
- `blocked`: 승인 대기 또는 불명확성으로 차단
- `done`: 완료
- `deprecated`: 폐기

## 2. 기능 간 의존성 요약
ARCHITECTURE.md §6 참조. 현재 등록된 의존 관계:
- `feature-0003-agent-web-ui` uses `feature-0002-agent-core`
- `feature-0004-browser-automation` uses `feature-0001-platform-runtime`
- `feature-0005-qa-mcp` uses `feature-0001-platform-runtime`, `feature-0002-agent-core`, `feature-0004-browser-automation`
- `feature-0006-lan-proxy-access` uses `feature-0001-platform-runtime`

## 3. 블로킹 항목
현재 사람 승인 또는 확인이 필요한 항목:
- 없음
- ~~호스트 포트 `28000`을 외부 컨테이너 `mysql-ai-mcp`가 사용 중이라 `feature-0005-qa-mcp`의 `make start`/`mcp` 단독 기동 검증이 차단됨~~ → 2026-04-06 포트 미사용 확인, 차단 해소

## 4. 통합 테스트 현황
- 통합 테스트 대상 기능 쌍: 향후 엄격 시나리오 정의 후 확정
- 최근 통합 테스트 실행: 2026-03-26 구조/기동 검증
- 현재 기준: 구조/기동 검증만 적용
- 확인 완료: `docker compose config`, `make status`, `make web`, `make browser-up`, `make browser-health`, `GET /api/session`
- 차단됨: `make mcp-test`(MCP 기동 검증 예정)
- 2026-04-15 갱신: 현재 repo 내부 Local LLM runtime 제거 작업을 반영했고, 외부 provider 계약 기준으로 문서와 실행 경로를 정리

## 5. 전체 진행률
- 총 기능 수: 6
- 완료: 0
- 진행 중: 6
- 차단: 0
