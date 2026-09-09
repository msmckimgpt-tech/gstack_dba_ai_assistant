---
doc_type: ARCHITECTURE
scope: project
status: active
edit_policy: rewrite
source_of_truth: true
template_version: v3.54.2
domain: [architecture]
ai_read_priority: 4
---

# Architecture

현재 구조·책임·의존성을 찾는 입구다. 작업 회차/검증 로그는 unit 문서에서 읽는다.
[2026-09-08 정리 전 전체 상세](./archive/delegation-friction-20260908/README.md)는
과거 증거이며 현재 상태·정책·승인의 정본이 아니다.

## 1. 전체 구조
저장소는 크게 다음 영역으로 나뉜다.

- 공통 정책: `../AGENTS.md`, `./*`
- 기능 단위 구현: `../unit/<feature-id>/`
- 공통 코드: `../shared/`
- 파생 산출물: `../../artifacts/*`
- 환경값 정본 의미: `../.env` (원본 루트 `.env` 의미 유지)

## 2. 책임 분리
### 공통 정책 영역
프로젝트 전반에 적용되는 규칙, 제약, 용어, 보안 기준을 정의한다.

### 기능 영역
기능별 코드, 테스트, 명세, 변경 이력, 리뷰, 보고를 관리한다.

### 공통 코드 영역 (shared/)
여러 기능이 공유하는 config/db/모델 목록·런타임 설정·예산·제품 식별 정본을 둔다.
공통 모듈 승격은 AGENTS.md §17을 따른다.

### 산출물 영역
빌드 결과, 로그, MySQL 데이터, 세션 파일, 인증서 등 런타임 파생 결과를 저장한다.

## 3. 기능 단위 구조 원칙
각 기능은 아래 하위 구조를 가진다.
- `src/` : 기능 구현
- `tests/` : 기능 테스트
- `docs/` : 기능 문서

코드 탐색은 [CODEBASE_MAP](./CODEBASE_MAP.md)과 해당 FUNCTION에서 시작한다.
계획·추적만 소유하는 initiative unit(예: 0012·0038)의 이름을 실제 코드 위치로 가정하지 않는다.
브리지 러너 원본은 `unit/feature-0043-external-llm-bridge/src/agent/` 모듈군이다.
단일 `bridge_agent.py`와 웹 `static/agent/` 배포본은 2026-09-02부터 빌드 생성물이므로
직접 편집·커밋 대상이 아니다. 네이티브 클라이언트는 이 러너를 동봉하지 않고 검증 후 내려받는다.

## 4. 현재 기능 맵

책임과 계약의 입구만 기록한다. **기능 상태/날짜는 [STATUS](./STATUS.md), 현재 명세는
각 FUNCTION, 진행·잔여 검증은 TASK/REPORT가 정본**이다. initiative unit의 문서 위치와
실제 코드 거주지는 다를 수 있으므로 §6을 함께 확인한다.

| 기능 ID | 책임·핵심 경계 | 명세 정본 |
|---|---|---|
| feature-0001-platform-runtime | MySQL 설정·DAB 설정·SQL 유틸리티. | [FUNCTION](../unit/feature-0001-platform-runtime/docs/FUNCTION.md) |
| feature-0002-agent-core | 에이전트 CLI·코어·SQL 도구·KB·대화 저장 및 워커. 외부 브리지와 내부 경로가 사용하는 도구·접지 공통 구현. | [FUNCTION](../unit/feature-0002-agent-core/docs/FUNCTION.md) |
| feature-0003-agent-web-ui | FastAPI 웹·인증/권한·대화/관리 라우터·정적 자산. 기능별 라우터와 web_context 경계를 사용한다. | [FUNCTION](../unit/feature-0003-agent-web-ui/docs/FUNCTION.md) |
| feature-0004-browser-automation | Playwright 브라우저 제어. WSL headless 보조 검증. | [FUNCTION](../unit/feature-0004-browser-automation/docs/FUNCTION.md) |
| feature-0005-qa-mcp | MCP 테스트와 QA 스크립트. | [FUNCTION](../unit/feature-0005-qa-mcp/docs/FUNCTION.md) |
| feature-0006-lan-proxy-access | Caddy TLS/LAN 진입·Windows 포트프록시·인증서 감시. 전달 IP 신뢰 경계, CA 부트스트랩, 엣지 보안 헤더는 SECURITY §7·9. | [FUNCTION](../unit/feature-0006-lan-proxy-access/docs/FUNCTION.md) |
| feature-0007-bedrock-llm-provider | LLM gateway/provider 배선. 2026-09-07 로컬 LLM 폐기, 임베딩 기본 비활성. gateway·롤백용 볼륨 보존 범위는 ADR-20260907T175000-local-llm-decommission-scope-boundary. | [FUNCTION](../unit/feature-0007-bedrock-llm-provider/docs/FUNCTION.md) |
| feature-0008-windows-browser-testing | PB-0008 일반 Windows 브라우저 보조 호환 검증. 주 사용 경로 DQA 앱 검증은 PB-0009. | [FUNCTION](../unit/feature-0008-windows-browser-testing/docs/FUNCTION.md) |
| feature-0009-group-conversation | 그룹 멤버십·멘션·공유. 열람/발화 권한 분리와 멤버 가시성 [from,to] window 격리(SECURITY §21). | [FUNCTION](../unit/feature-0009-group-conversation/docs/FUNCTION.md) |
| feature-0010-google-drive-integration | 계정별 Google Drive OAuth 토큰 암호화·라우트·MCP seam. 연동 미수행/기본 비활성(SECURITY §17). | [FUNCTION](../unit/feature-0010-google-drive-integration/docs/FUNCTION.md) |
| feature-0011-shared-extraction | shared/ 공통 모듈 추출. 기존 import·monkeypatch를 보존하는 모듈 alias shim. | [FUNCTION](../unit/feature-0011-shared-extraction/docs/FUNCTION.md) |
| feature-0012-web-router-modularization | feature-0003의 APIRouter/web_context 분할 initiative. 구현은 완료된 경계이며 프론트 후속은 feature-0038이 승계. | [FUNCTION](../unit/feature-0012-web-router-modularization/docs/FUNCTION.md) |
| feature-0013-relationship-diagrams | 관계 저장소·관계 질문 안내·Mermaid 렌더. sanitize 후 strict 렌더와 graceful fallback. | [FUNCTION](../unit/feature-0013-relationship-diagrams/docs/FUNCTION.md) |
| feature-0014-zero-downtime-deploy | 웹 2-replica 무중단 배포 스파인. 직렬화·expand/contract·드레인·엣지 복귀 확인·soak·last-good 롤백. 배포 완료를 `bin/lib/ui-release.sh` 가 원자 게시(`/srv/ui-release:ro`, REQ-20260909-deploy-refresh)하고, 프록시 점검은 Caddy 내부 자식이 아니라 격리 프로세스로 실행한다(REQ-20260909-caddy-probe · REQ-20260909-edge-probe-process-lifecycle). | [FUNCTION](../unit/feature-0014-zero-downtime-deploy/docs/FUNCTION.md) |
| feature-0015-zd-hygiene-backup | 워커 graceful 종료·MySQL online-DDL 린트·백업 범위·복원 리허설. 단일 호스트 HA/DB 엔진 무중단은 범위 밖. | [FUNCTION](../unit/feature-0015-zd-hygiene-backup/docs/FUNCTION.md) |
| feature-0016-metadata-graph | 관계형 SSOT를 AGE metadata_kb 그래프로 재생성 가능한 투영. 그래프 API·탐색 UI·노드 분석 연계; 투영은 원본 저장소가 아니다. | [FUNCTION](../unit/feature-0016-metadata-graph/docs/FUNCTION.md) |
| feature-0016-zd-pg-pause-caddy | PG config/minor 재시작 PAUSE→재생성→RESUME(trap 보장). Caddyfile 변경만 검증 후 재생성; major/HA 범위 밖. | [FUNCTION](../unit/feature-0016-zd-pg-pause-caddy/docs/FUNCTION.md) |
| feature-0017-deploy-build-gate | 배포 build_image 이미지/commit 라벨 정합 게이트. 알려진 metadata-race만 제한 허용하고 실제 빌드 실패는 차단. | [FUNCTION](../unit/feature-0017-deploy-build-gate/docs/FUNCTION.md) |
| feature-0019-message-editing | append-only 대화의 편집·브랜치 트리. 본인 발신만 편집, 공유 가시성 fail-closed, 그룹 멘션 발화 편집 잠금. | [FUNCTION](../unit/feature-0019-message-editing/docs/FUNCTION.md) |
| feature-0020-zd-deploy-all | 웹 배포 스파인을 워커·gateway·Caddy로 확장. 이미지 pin·graceful drain·surge·health·last-good 롤백. | [FUNCTION](../unit/feature-0020-zd-deploy-all/docs/FUNCTION.md) |
| feature-0021-redteam-review | 답변 전달 전 적대 리뷰·수정·재검증·감사 원장. 미해소를 통과로 오인하지 않는 수렴 판정. | [FUNCTION](../unit/feature-0021-redteam-review/docs/FUNCTION.md) |
| feature-0022-agent-scratch-workspace | 전용 PG agent_scratch의 대화별 작업공간. governed 반입·SQL allowlist·TTL·분기 이월, 매 턴 실재 테이블 우선(SECURITY §24). | [FUNCTION](../unit/feature-0022-agent-scratch-workspace/docs/FUNCTION.md) |
| feature-0023-conversation-api-access | Conversation API Bearer 인증·scope∩권한·절대 denylist. 쿠키 우선; 서버 LLM 차단으로 ask 실행은 제한됨. | [FUNCTION](../unit/feature-0023-conversation-api-access/docs/FUNCTION.md) |
| feature-0024-conversation-folders | 대화 폴더·이동·지침. own-only 계정 격리, 폴더 삭제 시 대화 보존, 깊이/순환 제한(SECURITY §26). | [FUNCTION](../unit/feature-0024-conversation-folders/docs/FUNCTION.md) |
| feature-0025-worker-parallelism | 워커 병렬도·페이싱·공유 자원 예산. 기본 동시성 1, LLM/DS 예산·전용 연결·lease fencing으로 공유 자원을 보호. | [FUNCTION](../unit/feature-0025-worker-parallelism/docs/FUNCTION.md) |
| feature-0026-perf-observability | HTTP·DB 연결·LLM·답변 단계·그래프 sync 계측과 perf-snapshot. 측정은 additive/fail-open. | [FUNCTION](../unit/feature-0026-perf-observability/docs/FUNCTION.md) |
| feature-0027-perf-latency-p0 | 측정 기반 지연 개선: terminal 뒤 큐레이션·RO 연결 공유·MySQL 버퍼풀·gzip/static cache. 품질 영향 축은 별도 결정. | [FUNCTION](../unit/feature-0027-perf-latency-p0/docs/FUNCTION.md) |
| feature-0028-web-perf | 웹 long-poll 비동기 이관·스냅샷 연결 번들·권한 TTL·세션 touch throttle·opt-in DB 풀. 응답/인가 계약 유지. | [FUNCTION](../unit/feature-0028-web-perf/docs/FUNCTION.md) |
| feature-0029-graph-churn | 값 무변경 updated_at 억제·상태 히스테리시스·프로브 부활 금지·중복 MERGE 제거. 그래프 신선도 보존. | [FUNCTION](../unit/feature-0029-graph-churn/docs/FUNCTION.md) |
| feature-0030-ask-timeout-extension | 사용자 확인 후 해당 run만 타임아웃 연장. run_id 짝 검증, per-call 900초 상한·중단 경로 유지; 외부 API에는 확인 프롬프트 없음. | [FUNCTION](../unit/feature-0030-ask-timeout-extension/docs/FUNCTION.md) |
| feature-0031-analysis-grounding | L0 통계 수집→L1 분석 증거 주입. 원시값/문자열 min-max 배제, COUNT(*) 전수 스캔 금지, ds 예산·단계별 부하 상한. | [FUNCTION](../unit/feature-0031-analysis-grounding/docs/FUNCTION.md) |
| feature-0032-llm-token-budget | 백그라운드 LLM rolling 24h 토큰 예산. 사용자 대기 호출 면제; 조회 실패 fail-open, 일부 insight는 계량만 하고 차단하지 않음. | [FUNCTION](../unit/feature-0032-llm-token-budget/docs/FUNCTION.md) |
| feature-0033-analysis-synthesis | 클러스터 L2 요약. 멤버셋·분석·증거 3중 지문 캐시; 요약을 클러스터 시그니처로 역주입 금지, 근거 커버리지 병기. | [FUNCTION](../unit/feature-0033-analysis-synthesis/docs/FUNCTION.md) |
| feature-0034-analysis-consumption | 사전 계산 L2 요약의 대화 grounding 소비. 요청 경로 합성/추가 LLM 호출 0, RO 조회·untrusted-data 각인·fail-soft. | [FUNCTION](../unit/feature-0034-analysis-consumption/docs/FUNCTION.md) |
| feature-0035-analysis-planner | LLM 없는 결정적 중요도/파티션 축약으로 미분석 테이블을 기존 분석 큐에 시드. 기존 자격·cap·쿨다운 게이트 재사용. | [FUNCTION](../unit/feature-0035-analysis-planner/docs/FUNCTION.md) |
| feature-0036-analysis-verification | 분석문과 L0 실측 대조: supported/contradicted/unverifiable. 실패는 검증됨이 아니며 자체 판정→증거 순환을 차단. | [FUNCTION](../unit/feature-0036-analysis-verification/docs/FUNCTION.md) |
| feature-0037-domain-synthesis | 요청 기반 L3 도메인 합성. 요청/생성 분리, 사전 전량 생성·답변 경로 합성 금지, L2 집합 지문으로 재생성. | [FUNCTION](../unit/feature-0037-domain-synthesis/docs/FUNCTION.md) |
| feature-0038-frontend-modularization | feature-0003 프론트 모듈화 initiative. 코드 거주지는 static/ 유지, behavior-neutral 추출·빌드 asset-stamp·브라우저 검증. | [FUNCTION](../unit/feature-0038-frontend-modularization/docs/FUNCTION.md) |
| feature-0039-ops-scheduler | ops-scheduler 컨테이너의 백업·복원 리허설·그래프 sync 4잡. 스케줄=compose OPS_SCHED_*; PG16 client·flock inode 공유. | [FUNCTION](../unit/feature-0039-ops-scheduler/docs/FUNCTION.md) |
| feature-0040-db-object-explorer | 역할 기반 DB 객체 6종 taxonomy·방언 매핑·탐색·그래프 투영. routine 저장은 routine_objects 유지(SECURITY §45). | [FUNCTION](../unit/feature-0040-db-object-explorer/docs/FUNCTION.md) |
| feature-0041-external-ai-tool-surface | 외부 AI 도구 표면·OAuth/PKCE·RBAC·감사. 익명=static contract, SQL 가드 재사용, 외부 task는 WebAiTasks 소유(SECURITY §44). | [FUNCTION](../unit/feature-0041-external-ai-tool-surface/docs/FUNCTION.md) |
| feature-0042-analysis-dedup | 분석 워커 LLM 경제성 조사·검증 판정. 런타임 구현 0건; dedup slug와 달리 현재 범위는 FUNCTION §1. | [FUNCTION](../unit/feature-0042-analysis-dedup/docs/FUNCTION.md) |
| feature-0043-external-llm-bridge | 서버 계정 LLM fail-closed 차단과 개인 머신 pull 브리지. 도구/인증/원장은 0041 재사용, 사용자 LLM 자격증명 무보관(SECURITY §49). | [FUNCTION](../unit/feature-0043-external-llm-bridge/docs/FUNCTION.md) |
| feature-0044-qa-staging-pipeline | 격리망 QA→라이브 build-once/deploy-many CI/CD 설계 rev.3. 구현 승인 대기; QA 데이터 운영 등급·임베딩 MCP 이관 선행. | [FUNCTION](../unit/feature-0044-qa-staging-pipeline/docs/FUNCTION.md) |
| feature-0045-zd-bridge-continuity | 브리지 대기/진행 분리·비대칭 드레인·MCP 롤링·claim lease 만료·러너 재연결 백오프. 대기는 교대, 진행 왕복은 완주. | [FUNCTION](../unit/feature-0045-zd-bridge-continuity/docs/FUNCTION.md) |
| feature-0046-native-client | 서비스의 주 사용 클라이언트(사용자 결정 2026-09-08). WebView2/트레이·loopback nonce/origin 경계·CA DER/러너 SHA 검증, 실제 릴리스 확인 후 광고. 1.3.0 부터 설치는 `versions/<버전>-<설치번호>` 슬롯에 배치하고 `active-slot.txt` 원자 교체로 다음 실행부터 적용한다(실행 중 앱·자식 러너 미종료). | [FUNCTION](../unit/feature-0046-native-client/docs/FUNCTION.md) |

## 5. source of truth 원칙
동일한 사실을 여러 문서에 중복 확정하지 않는다.
- 기능의 현재 동작: `FUNCTION.md`
- 작업 진행 상태: `TASK.md`
- 최근 진행 요약: `REPORT.md`
- 변경 기록: `MODIFY.md`
- 판단 근거: `REVIEW.md`
- 의사결정: `DECISIONS.md`
- 프로젝트 전체 현황: `STATUS.md`

## 6. 기능 간 의존성 맵
| 기능 ID | 의존 대상 | 의존 유형 | 비고 |
|---------|----------|----------|------|
| feature-0003-agent-web-ui | feature-0002-agent-core | uses | core import, Caddy forwarded-IP trust 설정은 SECURITY §9.7. |
| feature-0003-agent-web-ui | feature-0006-lan-proxy-access | uses | core import, Caddy forwarded-IP trust 설정은 SECURITY §9.7. |
| feature-0003-agent-web-ui | feature-0014-zero-downtime-deploy | uses | 0014 `bin/lib/ui-release.sh` 완료 게시(`/srv/ui-release:ro`)를 `/api/ui-release`(`ui_release.py`)가 읽어 대화 화면을 자동 갱신. 소비 계약 = 0003 REQ-20260909-deploy-refresh. |
| feature-0004-browser-automation | feature-0001-platform-runtime | uses | 운영 런타임과 함께 구동. |
| feature-0005-qa-mcp | feature-0001-platform-runtime | uses | Compose·환경값, 코어/MCP 모드와 브라우저 smoke 대상. |
| feature-0005-qa-mcp | feature-0002-agent-core | uses | Compose·환경값, 코어/MCP 모드와 브라우저 smoke 대상. |
| feature-0005-qa-mcp | feature-0004-browser-automation | uses | Compose·환경값, 코어/MCP 모드와 브라우저 smoke 대상. |
| feature-0006-lan-proxy-access | feature-0001-platform-runtime | uses | Web/TLS 운영 자산 공유. |
| feature-0007-bedrock-llm-provider | feature-0002-agent-core, feature-0003-agent-web-ui | uses | 코어·웹의 LLM 단일 진입점 배선. |
| feature-0008-windows-browser-testing | feature-0003-agent-web-ui, feature-0004-browser-automation | uses | 0003 웹이 실제 Windows 검증 대상, 0004는 WSL headless 보조(PB-0008). |
| feature-0009-group-conversation | feature-0003-agent-web-ui, feature-0002-agent-core | uses | 0003 멤버십/공유/첨부·0002 mentions 및 ask_jobs 큐. |
| feature-0010-google-drive-integration | feature-0003-agent-web-ui, feature-0002-agent-core | uses | 0003 인증/라우트/DDL·0002 cred_crypto/DEK. MCP seam 활성화는 별도 cycle. |
| feature-0011-shared-extraction | feature-0002-agent-core, feature-0003-agent-web-ui | uses | 0002·0003 공통 모듈을 shared/로 추출; 기존 import는 alias shim으로 보존. |
| feature-0012-web-router-modularization | feature-0003-agent-web-ui | uses | 실제 라우터·web_context 구현은 0003; 0012는 initiative 문서 홈. |
| feature-0013-relationship-diagrams | feature-0002-agent-core, feature-0003-agent-web-ui | uses | 0002 관계 저장/FK introspection/JOIN 학습·발화 가이드, 0003 Mermaid 렌더. |
| feature-0014-zero-downtime-deploy | feature-0003-agent-web-ui, feature-0006-lan-proxy-access | uses | 0003 /livez·/readyz·SSE 카운터; 0006 Caddy LB/active health/passive fails. fail_duration < EDGE_AVAIL_TIMEOUT 게이트. |
| feature-0015-zd-hygiene-backup | feature-0002-agent-core | uses | 0002 insight SIGTERM graceful; DDL 린트·백업/복원 진입점은 repo bin/. |
| feature-0016-metadata-graph | feature-0002-agent-core, feature-0003-agent-web-ui, feature-0013-relationship-diagrams, feature-0014-zero-downtime-deploy | uses | 0002 투영/graph_navigate, 0003 그래프 UI, 0013 관계 입력. AGE PG 이미지 cutover는 0014 롤백/replica 계약. |
| feature-0016-zd-pg-pause-caddy | feature-0002-agent-core, feature-0006-lan-proxy-access | uses | 0002 Postgres/PgBouncer transaction-mode·ADMIN_USERS; 0006 Caddyfile 재생성. |
| feature-0017-deploy-build-gate | feature-0014-zero-downtime-deploy | extends | 0014 bin/deploy-web.sh build_image의 이미지 정합 게이트 확장. |
| feature-0019-message-editing | feature-0003-agent-web-ui, feature-0002-agent-core | uses | 0003 conversations/프론트; 0002 additive 브랜치 마이그레이션·runtime schema·recall active-path·쓰기 체이닝. |
| feature-0020-zd-deploy-all | feature-0014-zero-downtime-deploy, feature-0015-zd-hygiene-backup, feature-0002-agent-core, feature-0007-bedrock-llm-provider | extends | 0014 배포 스파인 + 0015 graceful/lease requeue. 0002 agent 이미지·0007 gateway compose/config 재사용. |
| feature-0021-redteam-review | feature-0002-agent-core, feature-0003-agent-web-ui | uses | 0002 redteam/agent_notes/guidance_registry·코어 훅, 0003 admin_reasoning, shared/runtime_settings. |
| feature-0022-agent-scratch-workspace | feature-0002-agent-core, feature-0003-agent-web-ui | uses | 0002 scratch/도구/TTL/실재 상태 주입; 0003 분기·공유 이월/audit. 반입은 execute_sql 가드, 설정·연결은 shared/. |
| feature-0023-conversation-api-access | feature-0003-agent-web-ui, feature-0002-agent-core, feature-0005-qa-mcp | uses | 0003 web_context 권한/토큰·bootstrap DDL/audit; 0002 run_agent; 0005 MCP 패턴. CLI는 bin/api-token-issue.sh. |
| feature-0024-conversation-folders | feature-0002-agent-core, feature-0003-agent-web-ui, feature-0009-group-conversation | uses | 0003 folders/스토어/RBAC/UI; 0002 지침·마이그레이션; 0009 그룹멤버+대화 열람 게이트, shared/ 설정. |
| feature-0025-worker-parallelism | feature-0002-agent-core, feature-0003-agent-web-ui | uses | 0002 워커/전용 conn·0003 관리 UI, shared/resource_budget·runtime_settings; DS 및 LLM 공유 예산(0018 설정 슬라이스 재사용). |
| feature-0026-perf-observability | feature-0002-agent-core, feature-0003-agent-web-ui, feature-0006-lan-proxy-access | uses | 0002 llm/core/insight/graph, 0003 HTTP/DB 계측, 0006 Caddy log; shared/perf_counters와 bin/perf-snapshot.sh. |
| feature-0027-perf-latency-p0 | feature-0002-agent-core, feature-0001-platform-runtime, feature-0006-lan-proxy-access, feature-0026-perf-observability | uses | 0002 terminal 후 큐레이션·grounding RO; 0001 MySQL cnf; 0006 gzip/static; 0026 측정 근거. |
| feature-0028-web-perf | feature-0003-agent-web-ui, feature-0002-agent-core, feature-0026-perf-observability | uses | 0003 conversations/_conv_store/web_context/admin_products; 0002 ask-worker 결과 계약; 0026 db_per_req 전후 측정. |
| feature-0029-graph-churn | feature-0002-agent-core, feature-0016-metadata-graph, feature-0026-perf-observability | uses | 0002 relationships/metadata_graph·0046 트리거, 0016 투영 최적화, 0026 관측. 무변경 행만 억제·가역 마이그레이션. |
| feature-0030-ask-timeout-extension | feature-0002-agent-core, feature-0003-agent-web-ui | uses | 0002 run 예산/KV/run_id·per-call 900s; 0003 /api/extend·상태 스냅샷·권한/프론트. 실패는 409/503 fail-closed. |
| feature-0031-analysis-grounding | feature-0002-agent-core, feature-0016-metadata-graph, feature-0025-worker-parallelism | uses | 0002 metadata_stats·node_analysis evidence·0050; 0016 분석 워크로드; 0025 acquire(ds). 통계는 클러스터 시그니처에 유입 금지. |
| feature-0032-llm-token-budget | feature-0002-agent-core, feature-0003-agent-web-ui | uses | shared/llm_budget, 0002 claim 전 node_analysis·cluster·classify 3게이트, 0003 llm_usage 관측/콘솔. 사용자 호출 면제. |
| feature-0033-analysis-synthesis | feature-0002-agent-core, feature-0016-metadata-graph, feature-0031-analysis-grounding, feature-0032-llm-token-budget, feature-0025-worker-parallelism | uses | 0002 semantic_cluster/llm·0051; 0016 멤버셋, 0031 evidence 지문, 0032 토큰·0025 acquire(llm) 게이트. |
| feature-0034-analysis-consumption | feature-0002-agent-core, feature-0033-analysis-synthesis | uses | 0002 cluster_context·core grounding; 0033 사전 생성 요약. RO statement_timeout 1500ms SET/RESET, 실패 시 생략. |
| feature-0035-analysis-planner | feature-0002-agent-core, feature-0016-metadata-graph, feature-0032-llm-token-budget | uses | 0002 analysis_planner/insight; 0016 enqueue_change_analysis 기존 자격·busy·cap·쿨다운; 0032 비용 게이트. |
| feature-0036-analysis-verification | feature-0002-agent-core, feature-0031-analysis-grounding, feature-0016-metadata-graph, feature-0032-llm-token-budget, feature-0025-worker-parallelism, feature-0003-agent-web-ui | uses | 0002 analysis_verify/llm/insight·0052; 0031 L0 증거, 0016 분석문, 0032·0025 비용 게이트, 0003 그래프 판정 배지. |
| feature-0037-domain-synthesis | feature-0002-agent-core, feature-0033-analysis-synthesis, feature-0034-analysis-consumption, feature-0032-llm-token-budget, feature-0025-worker-parallelism | uses | 0002 domain_synthesis/llm/insight·0053; 0033 L2 입력, 0034 요청·주입; 0032·0025 비용. 요청 UPSERT는 별도 RW 연결. |
| feature-0041-external-ai-tool-surface | feature-0023-conversation-api-access, feature-0003-agent-web-ui, feature-0002-agent-core, feature-0031-analysis-grounding, feature-0033-analysis-synthesis, feature-0037-domain-synthesis, feature-0005-qa-mcp, feature-0021-redteam-review, feature-0006-lan-proxy-access | uses | 0023 발견/API 네임스페이스·0005 MCP, 0003 OAuth/RBAC/원장, 0002 도구/SQL 가드, 0031·0033·0037 접지, 0021 review_answer, 0006 MCP 엣지. |
| feature-0038-frontend-modularization | feature-0003-agent-web-ui, feature-0012-web-router-modularization, feature-0014-zero-downtime-deploy | uses | 코드 전부 0003 static/; 0012 분할 패턴; 0014 asset-stamp/soak/롤백. 백엔드 분할 재착수·번들러 도입 없음. |
| feature-0039-ops-scheduler | feature-0002-agent-core, feature-0015-zd-hygiene-backup, feature-0016-metadata-graph, feature-0020-zd-deploy-all | uses | 0002 이미지/scripts·PGDG16 client, 0015 백업/복원/보존, 0016 graph sync+flock(호스트 routine-backfill 공유), 0020 롤아웃. |
| feature-0040-db-object-explorer | feature-0016-metadata-graph, feature-0002-agent-core, feature-0003-agent-web-ui | uses | 0016 AGE/그래프·분석 시드, 0002 db_object_roles/db_objects/dialects/tools·0054, 0003 그래프 자산. routine 저장=0016 routine_objects. |
| feature-0042-analysis-dedup | feature-0002-agent-core, feature-0007-bedrock-llm-provider, feature-0036-analysis-verification, feature-0031-analysis-grounding, feature-0016-metadata-graph | uses | 읽기 전용 관측 의존: 0002 llm_usage/jobs, 0007 gateway, 0036 verdicts, 0031 stats·0016 분석. 구현은 별도 cycle. |
| feature-0043-external-llm-bridge | feature-0041-external-ai-tool-surface, feature-0003-agent-web-ui, feature-0002-agent-core, feature-0007-bedrock-llm-provider, feature-0023-conversation-api-access | uses | 0041 ai_tools 인증/원장/각인, shared/llm_gate는 0002·0003 진입에서 호출; 0007 alias 잠금. 0023 ask 계약 유지·서버 LLM 실행 차단. |
| feature-0044-qa-staging-pipeline | feature-0014-zero-downtime-deploy, feature-0020-zd-deploy-all, feature-0041-external-ai-tool-surface, feature-0043-external-llm-bridge | uses | 설계만 존재. 0014·0020 배포 스파인 유지/이미지 획득만 교체 예정. 0041·0043을 통한 VPN 밖 MCP 왕복이 완료 조건. |
| feature-0045-zd-bridge-continuity | feature-0014-zero-downtime-deploy, feature-0020-zd-deploy-all, feature-0003-agent-web-ui, feature-0043-external-llm-bridge, feature-0041-external-ai-tool-surface, feature-0006-lan-proxy-access | extends | 0014·0020 deploy/quiesce 스파인, 0003 bridge_drain/internal API, 0043 claim/재연결, 0041 MCP stateless HTTP, 0006 MCP LB. |
| feature-0046-native-client | feature-0043-external-llm-bridge, feature-0003-agent-web-ui, feature-0006-lan-proxy-access | uses | 0043 러너를 0003에서 다운로드·sha256 대조; shared/dqa_identity·_RUNTIME_SPECS 정본. 0006 CA를 DER 확인 후 프로세스 한정 신뢰. |

### 의존 유형 정의
- `requires`: 대상 기능이 완성되어야 구현 가능
- `uses`: 대상 기능의 API/인터페이스를 사용하지만 독립 개발 가능
- `extends`: 대상 기능을 확장하는 관계

## 7. KB Postgres 데이터 경로

### 7.1 현재 검색 진입점

현재 읽기 진입점은 `modules/kb_retrieval.py`의 RAG document/object 로더다(§7.7).
과거 T1의 `_load_top_facts_pg()`·`_build_knowledge_payload()` 최적화 기록은
후속 TASK-0150에서 해당 경로가 제거됐으므로 현행 호출 경로로 사용하지 않는다.

### 7.2 스키마 최적화 (T2)
- `agent_memory_facts`: regular VIEW → **MATERIALIZED VIEW** (CONCURRENTLY refresh 지원)
- `category_join_hints_json`: TEXT → **JSONB** + GIN index
- `texts.embedding`: partial ivfflat index (WHERE embedding IS NOT NULL)

### 7.3 인프라 최적화 (T3)
- PgBouncer transaction-mode sidecar (`edoburu/pgbouncer`, `pgbouncer:5432`)
- PostgreSQL 서버 파라미터 전면 조정 (shared_buffers, WAL, checkpoint 등)
- `pg_stat_statements` + `kb_slow_queries` view + autovacuum scale_factor=0

### 7.4 Lock / 캐시 최적화 (T4)
- Advisory lock: MySQL GET_LOCK → `pg_try_advisory_lock(hashtext(name))`
- 캐시 무효화: TTL 폴링 → `kb_invalidations` 테이블 + `pg_notify` groundwork
- `_is_refresh_due()` PG 무효화 플래그 연동

### 7.5 Replica 분리 (T5)
- `postgres-replica` streaming replica 서비스 (profile: replica)
- `AGENT_KB_PG_HOST_RO` / `AGENT_KB_PG_PORT_RO` 환경변수로 read-only 라우팅

### 7.6 KB 모듈 레이어 구조

코드는 `unit/feature-0002-agent-core/src/modules/`에 있다.

| 모듈 | 책임 |
|---|---|
| `modules/kb_scope.py` | scope SQL clause (`_scope_filter_sql`, STRICT/INCL_NULL), PII 마스킹, 에러 분류, 요청 유사도, advisory lock(MySQL/PG), schema/search cache key, refresh 무효화 |
| `modules/kb_retrieval.py` | RAG document/object 검색(`_load_rag_documents_for_request*`/`_load_rag_objects_for_request*`), 쿼리 임베딩(벡터)·trigram 읽기, fact 텍스트 로딩(`_load_fact_text`/`_trim_fact_text`), insight 존재 로더(`_load_existing_schema_insights`/`_load_existing_table_insight_map`) (TASK-0150: planner 경로 전용이던 `_build_knowledge_payload`·`_load_top_facts*`·prompt 선택/retrieval-depth/schema-meta cache helper 죽은 subtree 제거) |
| `modules/kb_write.py` | fact/rag upsert(`_upsert_fact`), dual-write 미러, global publish, KB entry 영속화, step-trace (TASK-0150: 죽은 `_plan_zero_result_diagnostic` 제거) |

- 의존 방향은 단방향: `kb_scope`(leaf) ← `kb_retrieval` ← `kb_write`. 순환 없음.
- `modules/knowledge.py` 는 **얇은 facade** 로 남아 세 모듈의 모든 top-level 심볼(public
  `__all__` + private `_helper`) 을 re-export 한다. 기존 `from modules.knowledge import X`
  / `knowledge.X` 소비처(agent_core·insight·schema·render·sql_ops·domain·utils·db·llm·
  kb_backend·tests) blast-radius 0. 기존 public/private import 호환을 유지한다.
- cross-module 이름은 `modules/__init__.py` 의 주입 메커니즘으로 런타임 해석된다(기존과 동일).
  facade 는 추가로 세 모듈 함수의 `__globals__` 를 단일 facade 네임스페이스로 재바인딩해,
  분할 전처럼 `monkeypatch.setattr(knowledge, "_helper", ...)` 가 호출 함수 내부 조회까지
  전파되는 test seam 을 보존한다(코드 객체 자체는 불변).

### 7.7 KB 검색 파이프라인 (벡터 + trigram, 활성)
`AGENT_KB_READ_BACKEND=postgres` 시 read 경로는 다음 순서로 동작한다. (read-only 는
`agent_kb_ro` least-privilege role `_pg_connect_ro()` 사용 — RW role bypass 금지.)

- **rag_documents** (`_load_rag_documents_for_request` → `_load_rag_documents_for_request_pg`):
  1. `_embed_query_vector()` 로 쿼리 임베딩. ⚠ **2026-09-07 로컬 LLM 폐기 이후
     `AGENT_KB_EMBEDDING_MODEL` 기본값은 빈 값**이고, 철거된 로컬 alias 는
     `normalize_kb_embedding_model()` 이 잔존 env 와 무관하게 비활성으로 읽는다 — 따라서
     라이브에서 이 단계는 호출 전에 `None` 을 반환하고 아래 2 로 곧장 내려간다. 임베딩
     제공자를 복구해 값을 지정하면 성공 시 `PgKbBackend.search_rag_documents_vector()`
     (pgvector, 한국어 의미검색)로 흐른다.
  2. 임베딩 미설정/실패 또는 벡터 결과 없음(미임베딩 row) → `search_rag_documents()`
     **pg_trgm trigram similarity** fallback.
- **rag_objects** (`_load_rag_objects_for_request` → `_load_rag_objects_for_request_pg`):
  `PgKbBackend.search_rag_objects()` 로 D0–D3 스키마/객체 routing 근거 제공.
- **fail-soft fallback (라이브 경로)**: 위 PG 경로가 예외/PG 미가용 시, 동일 함수가
  `conn` 기반 MySQL-dialect SQL 로 fallthrough 한다. cutover 미완 구간의 안전망으로
  **여전히 도달 가능** — 따라서 dead code 가 아니다 (TASK-0142 에서 보존). 이미 사장된
  MySQL 전용 분기는 선행 TASK-0127/0135 에서 제거 완료.

## 8. 검증·확장 원칙

- 실행 경로는 `Makefile`의 `test`와 `pyproject.toml`의 `testpaths`, 기능 시나리오는 각 `docs/TEST.md`가 정본이다.
- 구조/기동 점검만으로 기능 완료를 판정하지 않는다. UI 변경은 PB-0009에 따라 실제 DQA 클라이언트의 해당 화면·동작을 검증한다. 일반 브라우저는 보조 경로다.
- 공통 통합 테스트의 위치/승격은 실제 실행 경로와 함께 결정한다. 없는 자동화를 완료 게이트로 가정하지 않는다.


- 기능 간 공통성이 반복되면 공통 모듈로 승격을 검토한다.
- 구조 변경이 필요한 경우 프로젝트 수준 `DECISIONS.md`에 남긴다.

## 9. artifacts 조직 규칙
`/artifacts/`는 재생성 가능한 파생 결과물을 저장한다.

### 9.1 디렉토리 구조
```
artifacts/
├── build/              # 빌드 산출물
├── reports/            # 생성된 보고서
├── exports/            # 내보내기 파일
├── tmp/                # 임시 파일
└── <feature-id>/       # 기능별 산출물 (검증 결과, 로그 등)
    └── <timestamp>/    # 실행 시점별 격리
```

### 9.2 규칙
- artifacts는 git 추적 대상이 아니다 (repo 외부에 위치).
- 기능별 산출물은 `<feature-id>/` 하위에 타임스탬프 디렉토리로 격리한다.
- 빌드/테스트 산출물은 재생성 가능해야 하며, source of truth가 아니다.
- 공유 런타임 데이터(로그, 세션 등)는 `artifacts/shared/`에 둔다.
- `.gitkeep` 파일로 디렉토리 구조를 유지한다.

## 10. Agent Board — 세션 간 게시판 (v3.53.0)
<!-- agent-board:arch:v1 -->

프로젝트 단위의 **파일 기반 조정면**. `<wrapper>/board/`(git 밖)에 1 게시물 = 1 파일(`channels/**/<id>.md`, JSON frontmatter + markdown)로
쌓이고, 각 AI 세션의 lifecycle hook(`bin/hooks/board-hook.sh`)이 다음 이벤트에서 «내 cursor 이후 게시물» 을 비신뢰 wrapper 로
컨텍스트에 주입한다. 데몬은 없다. 구성 요소:

| 요소 | 역할 |
|---|---|
| `bin/board.sh` | CLI 진입점 — 서브커맨드 dispatch 만 |
| `bin/lib/board_core.sh` | bash 함수 라이브러리 — 인자 검증·프로세스 오케스트레이션·exit code 매핑. board_root 아래 경로를 coreutils 에 넘기지 않는다 |
| `bin/lib/board_fs.py` | **board_root 아래의 모든 파일 접근** — dir-fd + `openat(O_NOFOLLOW)`, `O_EXCL` 생성, `os.link` no-replace publish, flock, JSON frontmatter(중복 키 거부), 2상태 원장·admission, deliver(gate→scan→budget→wrapper→emit→commit), init 소유권 표, 조상 git exclude, gc, doctor |
| `bin/hooks/codex-board-hook.py` | Codex 어댑터 — 실제 session id·이벤트 계약, 신뢰한 로컬 hook 등록을 사용 |
| `bin/hooks/board-hook.sh` | Claude Code 어댑터 — stdin 을 넘기며 `exec board.sh …` 로 자기 프로세스를 대체. 어떤 입력에도 exit 0, `decision` 없음 |
| `<board>/board.json` | 수치 정본(예산·rate·TTL·상한). 운영자 소유 0644 — 일반 writer 는 읽기만 |

정책은 AGENTS.md §22.15. Claude와 Codex의 어댑터는 별도로 존재하며, 실제 hook 등록/신뢰·세션 이벤트를 확인해 사용한다. 어댑터 파일 존재만으로 현재 등록·동작 중이라고 판정하지 않는다. Gemini 지원은 이 문서에서 확인하지 않았다.
