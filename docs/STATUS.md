---
doc_type: PROJECT_STATUS
scope: project
status: active
edit_policy: rewrite
source_of_truth: true
---

# Project Status

프로젝트 전체 현황을 한눈에 파악하기 위한 문서이다.

## 1. 기능 현황

| 기능 ID | 상태 | 담당 | 최종 갱신 | 비고 |
|---------|------|------|----------|------|
| feature-0001-platform-runtime | in-progress | AI | 2026-03-26 | 구조 이관 완료, 엄격 시나리오 미작성 |
| feature-0002-agent-core | blocked | AI | 2026-03-26 | 구조 이관 완료, `local-llm-gateway` 미연결로 `make ask` 차단 |
| feature-0003-agent-web-ui | in-progress | AI | 2026-03-26 | 구조 이관 완료, 엄격 시나리오 미작성 |
| feature-0004-browser-automation | in-progress | AI | 2026-03-26 | 구조 이관 완료, smoke 검증 예정 |
| feature-0005-qa-mcp | blocked | AI | 2026-03-26 | 외부 `mysql-ai-mcp`가 `28000` 포트를 점유해 단독 기동 차단 |
| feature-0006-lan-proxy-access | in-progress | AI | 2026-03-26 | 운영 자산 이관 완료 |

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
- `llm-shared` 네트워크에 `local-llm-gateway` 컨테이너가 없어 `feature-0002-agent-core`의 `make ask` 검증이 LLM 연결 오류로 중단됨
- 호스트 포트 `28000`을 외부 컨테이너 `mysql-ai-mcp`가 사용 중이라 `feature-0005-qa-mcp`의 `make start`/`mcp` 단독 기동 검증이 차단됨

## 4. 통합 테스트 현황
- 통합 테스트 대상 기능 쌍: 향후 엄격 시나리오 정의 후 확정
- 최근 통합 테스트 실행: 2026-03-26 구조/기동 검증
- 현재 기준: 구조/기동 검증만 적용
- 확인 완료: `docker compose config`, `make status`, `make web`, `make browser-up`, `make browser-health`
- 차단됨: `make start`(MCP 포트 충돌), `make ask`(LLM 게이트웨이 연결 오류), `make mcp-test`(MCP 단독 기동 미완료)

## 5. 전체 진행률
- 총 기능 수: 6
- 완료: 0
- 진행 중: 4
- 차단: 2
