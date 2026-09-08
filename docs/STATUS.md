---
doc_type: PROJECT_STATUS
scope: project
status: active
edit_policy: rewrite
lifecycle: active
source_of_truth: true
template_version: v3.34.1
domain: [status, index]
ai_read_priority: 6
sources:
  - unit/feature-0001-platform-runtime/docs/TASK.md
  - unit/feature-0002-agent-core/docs/TASK.md
  - unit/feature-0003-agent-web-ui/docs/TASK.md
  - unit/feature-0004-browser-automation/docs/TASK.md
  - unit/feature-0005-qa-mcp/docs/TASK.md
  - unit/feature-0006-lan-proxy-access/docs/TASK.md
  - unit/feature-0007-bedrock-llm-provider/docs/TASK.md
  - unit/feature-0008-windows-browser-testing/docs/TASK.md
  - unit/feature-0009-group-conversation/docs/TASK.md
  - unit/feature-0010-google-drive-integration/docs/TASK.md
  - unit/feature-0011-shared-extraction/docs/TASK.md
  - unit/feature-0012-web-router-modularization/docs/TASK.md
  - unit/feature-0013-relationship-diagrams/docs/TASK.md
  - unit/feature-0014-zero-downtime-deploy/docs/TASK.md
  - unit/feature-0015-zd-hygiene-backup/docs/TASK.md
  - unit/feature-0016-metadata-graph/docs/TASK.md
  - unit/feature-0016-zd-pg-pause-caddy/docs/TASK.md
  - unit/feature-0017-deploy-build-gate/docs/TASK.md
  - unit/feature-0019-message-editing/docs/TASK.md
  - unit/feature-0020-zd-deploy-all/docs/TASK.md
  - unit/feature-0021-redteam-review/docs/TASK.md
  - unit/feature-0022-agent-scratch-workspace/docs/TASK.md
  - unit/feature-0023-conversation-api-access/docs/TASK.md
  - unit/feature-0024-conversation-folders/docs/TASK.md
  - unit/feature-0025-worker-parallelism/docs/TASK.md
  - unit/feature-0026-perf-observability/docs/TASK.md
  - unit/feature-0027-perf-latency-p0/docs/TASK.md
  - unit/feature-0028-web-perf/docs/TASK.md
  - unit/feature-0029-graph-churn/docs/TASK.md
  - unit/feature-0030-ask-timeout-extension/docs/TASK.md
  - unit/feature-0031-analysis-grounding/docs/TASK.md
  - unit/feature-0032-llm-token-budget/docs/TASK.md
  - unit/feature-0033-analysis-synthesis/docs/TASK.md
  - unit/feature-0034-analysis-consumption/docs/TASK.md
  - unit/feature-0035-analysis-planner/docs/TASK.md
  - unit/feature-0036-analysis-verification/docs/TASK.md
  - unit/feature-0037-domain-synthesis/docs/TASK.md
  - unit/feature-0038-frontend-modularization/docs/TASK.md
  - unit/feature-0039-ops-scheduler/docs/TASK.md
  - unit/feature-0040-db-object-explorer/docs/TASK.md
  - unit/feature-0041-external-ai-tool-surface/docs/TASK.md
  - unit/feature-0042-analysis-dedup/docs/TASK.md
  - unit/feature-0043-external-llm-bridge/docs/TASK.md
  - unit/feature-0044-qa-staging-pipeline/docs/TASK.md
  - unit/feature-0045-zd-bridge-continuity/docs/TASK.md
  - unit/feature-0046-native-client/docs/TASK.md
---

# Project Status (인덱스)

프로젝트를 기능별로 탐색하는 **현황 인덱스**다(ADR-0031 SSOT 계약 §1).
상태·날짜·TASK 링크를 유지하고 최근 요지는 짧게 표시한다. 상세 이력·검증 회차는 TASK/REPORT에서 읽는다.

- **기능별 상세 현황 정본**: `unit/<feature>/docs/{TASK,REPORT}.md` — 본 문서는 그 요약·링크만.
- **2026-09-08 정리 직전 상세 스냅샷**: [보존 원장](./archive/delegation-friction-20260908/README.md) — 과거 증거이며 현재 상태·승인의 정본이 아니다.
- **인덱스화 이전 누적 rollup·상세 이력**: [docs/archive/STATUS_ARCHIVE.md](./archive/STATUS_ARCHIVE.md) (verbatim 보존).
- 정본 지도: [docs/DOC_REGISTRY.md](./DOC_REGISTRY.md) · SSOT 계약: [docs/DECISIONS.md](./DECISIONS.md) ADR-0031.

## 1. 기능 현황 (요약 인덱스)

<!-- AI-EDITABLE:STATUS-TABLE:START -->
<!-- 이 표는 bin/gen-status.sh 생성물 — 수기 편집 금지. 상태 정본 = unit/<feature>/docs/TASK.md frontmatter(feature_status*) -->

| 기능 ID | 상태 | 최종 갱신 | 정본(상세) | 최근 작업 요지 |
|---|---|---|---|---|
| feature-0001-platform-runtime | in-progress | 2026-07-28 | [TASK](../unit/feature-0001-platform-runtime/docs/TASK.md) | 엄격한 운영 시나리오(TEST-0003) 확정 + 라이브 실측 PASS — Completion Checklist 전건 충족 |
| feature-0002-agent-core | in-progress | 2026-09-07 | [TASK](../unit/feature-0002-agent-core/docs/TASK.md) | init "준비" 임베딩 지연 회귀 해소(전용 embed-ollama·캐싱·fast-timeout)·요청량 한도 메시지 주체 구분·datasource 회로차단 안내 문구 분리(고장 오인 해소) / ITEM-11 메타데이터 컨텍스트·NL→SQL flywheel · 용어사전 대화 자율등록 코어(role… (상세는 TASK) |
| feature-0003-agent-web-ui | in-progress | 2026-09-07 | [TASK](../unit/feature-0003-agent-web-ui/docs/TASK.md) | 메타데이터 부트스트랩 결과 패널 접기+검색/필터 재설계(대규모 스키마 여백 과다 해소) + 패널 잘림 잔존 cache-buster 미bump 근본수정(metadata-bs-collapse) · 메타데이터 부트스트랩 MSSQL database 차원 수정(tempdb 임시테이블→선택 DB 실테이블, 시스… (상세는 TASK) |
| feature-0004-browser-automation | in-progress | 2026-07-28 | [TASK](../unit/feature-0004-browser-automation/docs/TASK.md) | 엄격한 브라우저 시나리오(TEST-0003) 확정 + 라이브 왕복·scheme 가드 PASS — Completion Checklist 전건 충족 |
| feature-0005-qa-mcp | in-progress | 2026-07-28 | [TASK](../unit/feature-0005-qa-mcp/docs/TASK.md) | 엄격한 QA 시나리오(TEST-0003) 확정 + MCP 왕복·실 DB 메타데이터 반환 PASS — Completion Checklist 전건 충족 |
| feature-0006-lan-proxy-access | in-progress | 2026-09-02 | [TASK](../unit/feature-0006-lan-proxy-access/docs/TASK.md) | caddy 운영 자산 이관 완료 · _get_client_ip X-Forwarded-For conditional trust(SECURITY.md §9.7) · (06-17) 사내 자체 Root CA 신뢰 배포(self-signed 탈피)·caddy :443 정식 front door·테스터 Root C… (상세는 TASK) |
| feature-0007-bedrock-llm-provider | in-progress | 2026-09-07 | [TASK](../unit/feature-0007-bedrock-llm-provider/docs/TASK.md) | AWS Bedrock(Seoul) provider 통합, API Vault 폐기 (ADR-0022) · (07-04) insight 주말/야간 gemma 고착 해소 — 용도별 모델 라우팅 분리(interactive/insight fallback 체인 정정, llm-routing) · (07-07) O… (상세는 TASK) |
| feature-0008-windows-browser-testing | review | 2026-08-28 | [TASK](../unit/feature-0008-windows-browser-testing/docs/TASK.md) | Windows 브라우저 자동 구동 + Playwright MCP (PB-0008) · (08-28) 검증용 로그인 세션 3종(session-login/session-check --require-auth/session-logout) 신설 + session-login 이 사용자 탭을 자기 것으로 오인해… (상세는 TASK) |
| feature-0009-group-conversation | in-progress | 2026-07-04 | [TASK](../unit/feature-0009-group-conversation/docs/TASK.md) | 안 읽은 메세지/@멘션 배지(gc-unread-badge, REQ-GC-R8 read-state, alembic 0019 + 0020 baseline backfill + read-fix 커서 전진 보정 + read-500-fix(읽음 API POST /read 서버 import 정정 modules.d… (상세는 TASK) |
| feature-0010-google-drive-integration | in-progress | 2026-06-23 | [TASK](../unit/feature-0010-google-drive-integration/docs/TASK.md) | Google Drive 연동 토대 — 계정별 OAuth 토큰 암호화 + MCP 구성 seam (연동 미수행/비활성 scaffold) |
| feature-0011-shared-extraction | done | 2026-08-05 | [TASK](../unit/feature-0011-shared-extraction/docs/TASK.md) | shared/ 공통 코드 추출 P5a 완결 — Step1~5c(model_catalog·config·db·conn_health·datasources 마이그레이션 + alias shim 4종 전량 제거, make test 회귀 0) + 동반 doc; Step6(feature Dockerfile 분리)는… (상세는 TASK) |
| feature-0012-web-router-modularization | review | 2026-07-12 | [TASK](../unit/feature-0012-web-router-modularization/docs/TASK.md) | P5b 전체추출 완료 — app.py 모놀리스 148 route 핸들러 전량을 21개 도메인 APIRouter 로 byte-동치 추출(app.py ~29K→18,917줄, 잔여 @app 라우트 0, helpers+DI seam+include_router 잔류). batch1-3 라이브 배포·검증 완료… (상세는 TASK) |
| feature-0013-relationship-diagrams | in-progress | 2026-06-29 | [TASK](../unit/feature-0013-relationship-diagrams/docs/TASK.md) | flow/관계 질문에 mermaid 다이어그램 답변 — 웹 UI mermaid 렌더(vendor v10.9.3, sanitize-후 strict 렌더) + _MERMAID_DIAGRAM_GUIDANCE 발화 + table_relationships 관계 저장소(FK introspection·대화 JOI… (상세는 TASK) |
| feature-0014-zero-downtime-deploy | review | 2026-08-11 | [TASK](../unit/feature-0014-zero-downtime-deploy/docs/TASK.md) | web 무중단 롤링 배포 — Caddy LB 뒤 web-a/web-b 2-replica + 배포 스파인 bin/deploy-web.sh(flock+origin/main coalesce·단일 scoped-sudo·TLS preflight·migrate-lint gate·one-at-a-time+SSE… (상세는 TASK) |
| feature-0015-zd-hygiene-backup | review | 2026-06-30 | [TASK](../unit/feature-0015-zd-hygiene-backup/docs/TASK.md) | 백엔드/DB 무중단 위생(feature-0014 후속, feasibility 분석 wf_1d634d33) — ① insight-worker SIGTERM graceful(_INSIGHT_SHUTDOWN+stop_grace 30s) ② MySQL online-DDL 게이트 bin/mysql-ddl-li… (상세는 TASK) |
| feature-0016-metadata-graph | in-progress | 2026-09-02 | [TASK](../unit/feature-0016-metadata-graph/docs/TASK.md) | AGE 메타데이터 지식그래프(관계형 SSOT→metadata_kb 투영) + 관리콘솔 그래프 뷰(Cytoscape·fcose 클러스터링·관련도 사이징·이웃 60x 인덱스) + graph_navigate AI 도구(컨텍스트 초과 시 서브그래프 탐색). 커스텀 PG16 이미지(pgvector+pg_trg… (상세는 TASK) |
| feature-0016-zd-pg-pause-caddy | review | 2026-06-30 | [TASK](../unit/feature-0016-zd-pg-pause-caddy/docs/TASK.md) | 무중단 조건부→가능 승격(feasibility wf_1d634d33) — PG pgbouncer PAUSE 래퍼 bin/pg-restart.sh(PAUSE→PG재시작→RESUME, RW near-zero, RESUME trap 보장) + compose pgbouncer ADMIN_USERS + dep… (상세는 TASK) |
| feature-0017-deploy-build-gate | review | 2026-07-02 | [TASK](../unit/feature-0017-deploy-build-gate/docs/TASK.md) | deploy-web.sh build+migrate 게이트 snap-docker docker compose (build\／run) metadata-file race false-failure 수정 — build 게이트는 이미지 존재+GIT_COMMIT 라벨 정합 검증(EXIT≠0 은 marker+이미지정… (상세는 TASK) |
| feature-0019-message-editing | in-progress | 2026-07-27 | [TASK](../unit/feature-0019-message-editing/docs/TASK.md) | 메시지 편집(ChatGPT식) Phase 1+2 완성·라이브 — 대화 내부 브랜치 트리(parent_message_id+active_leaf·비분기 fast-path·active-path recall CTE, mig 0041). 1:1=단순 수정 또는 요청사항 수정 시 분기 재답변(< n/m > 버전… (상세는 TASK) |
| feature-0020-zd-deploy-all | in-progress | 2026-07-14 | [TASK](../unit/feature-0020-zd-deploy-all/docs/TASK.md) | 무중단 배포 커버리지 완성 — deploy 스파인 확장(워커 insight/ask 자동 롤아웃 build-once mysql-ai-agent:<sha> 핀·healthy 게이트·last-good 롤백 + bedrock-gateway 드리프트 시 surge replica 무중단 교체 + caddy 이미… (상세는 TASK) |
| feature-0021-redteam-review | in-progress | 2026-08-19 | [TASK](../unit/feature-0021-redteam-review/docs/TASK.md) | (08-19) '재검증에서 해소되지 않은 지적' 잔존 전달의 비수렴 경로 3종 봉인(unresolved-convergence, 사용자 리포트) — 라이브 30일 실측(잔존 33건 중 revise_failed 25·미해소 축 grounding 47/71)으로 ① digest 예산 강등 본문-보유 첨부를… (상세는 TASK) |
| feature-0022-agent-scratch-workspace | in-progress | 2026-08-14 | [TASK](../unit/feature-0022-agent-scratch-workspace/docs/TASK.md) | assistant 자율 PG 작업공간(전용 DB agent_scratch·대화별 격리 스키마·외부 데이터소스 반입 cross-source JOIN·TTL 24h·scratch_guard allowlist) — 백엔드 코어+단위 22 PASS, 2026-07-21 라이브 활성(bootstrap+AGEN… (상세는 TASK) |
| feature-0023-conversation-api-access | in-progress | 2026-07-28 | [TASK](../unit/feature-0023-conversation-api-access/docs/TASK.md) | 외부 AI 용 Conversation API (Bearer 토큰·scope 교집합+절대 denylist·CLI 발급·MCP) + 발견 진입점(llms.txt·매니페스트·큐레이션 OpenAPI·가이드) · (07-28) 대화 품질 조정 — 외부 AI 가 모델·추론 강도·제품·폴더 커스텀 지침·첨부를 조… (상세는 TASK) |
| feature-0024-conversation-folders | in-progress | 2026-08-13 | [TASK](../unit/feature-0024-conversation-folders/docs/TASK.md) | 대화 폴더(프로젝트 워크스페이스) — 사이드바 재귀 폴더로 대화 조직/이동·폴더 삭제해도 대화 보관(soft-delete)·폴더별 커스텀 지침 ask-time 주입·런타임 조절 max-depth(깊이/순환 상한). 엄격 per-user(owner-scope) 격리 — 크로스-계정 폴더 노출 차단(Cr… (상세는 TASK) |
| feature-0025-worker-parallelism | in-progress |  | [TASK](../unit/feature-0025-worker-parallelism/docs/TASK.md) |  |
| feature-0026-perf-observability | in-progress | 2026-07-27 | [TASK](../unit/feature-0026-perf-observability/docs/TASK.md) | 성능 관측 인프라 신규 — HTTP per-route 타이밍·요청당 DB conn 카운터(admin_perf)·워커 LLM latency 백필(13 sites)·답변 파이프라인 단계 계측(redteam/post-answer/grounding)·graph-sync duration·perf-snapsho… (상세는 TASK) |
| feature-0027-perf-latency-p0 | in-progress | 2026-07-28 | [TASK](../unit/feature-0027-perf-latency-p0/docs/TASK.md) | P0 성능 개선 1차 — post-answer 큐레이션(topic/용어/ENUM LLM 3건) terminal 후 이동(체감 -25~35s)·grounding RO 단일연결·MySQL 버퍼풀 128MB→1G·Caddy gzip+immutable static (feature-0026 측정 근거, 품질 무영향 축만) |
| feature-0028-web-perf | in-progress | 2026-07-28 | [TASK](../unit/feature-0028-web-perf/docs/TASK.md) | web 계층 성능 — ask_result long-poll 워커 스레드 이관(이벤트 루프 stall 제거)·스냅샷 PG 단일연결 번들(호출당 4~5→1)·권한 카탈로그 TTL 캐시+세션 LastSeenAt throttle(인증 5왕복 완화)·web MySQL 풀 opt-in (feature-0026… (상세는 TASK) |
| feature-0029-graph-churn | in-progress | 2026-07-28 | [TASK](../unit/feature-0029-graph-churn/docs/TASK.md) | 그래프 sync churn 근절 — 값 무변경 시 updated_at 미전진(upsert·신호·트리거 alembic 0046)·status 히스테리시스(trusted/broken 왕복 차단)·프로브 broken 부활 금지·공유 정점 중복 MERGE 제거(관계당 cypher 11→1~3). 라이브 실측… (상세는 TASK) |
| feature-0030-ask-timeout-extension | in-progress | 2026-07-29 | [TASK](../unit/feature-0030-ask-timeout-extension/docs/TASK.md) | 실행 타임아웃 80% 도달 시 사용자 확인 후 그 run 한정 무제한 연장 — KV 시그널(cancel/finalize 미러링)·run 예산+LLM 타임아웃 2층 해제·컴포저 인라인 배너+백그라운드 브라우저 알림·conversation.extend.* 권한 신설 |
| feature-0031-analysis-grounding | in-progress |  | [TASK](../unit/feature-0031-analysis-grounding/docs/TASK.md) |  |
| feature-0032-llm-token-budget | in-progress |  | [TASK](../unit/feature-0032-llm-token-budget/docs/TASK.md) |  |
| feature-0033-analysis-synthesis | in-progress |  | [TASK](../unit/feature-0033-analysis-synthesis/docs/TASK.md) |  |
| feature-0034-analysis-consumption | in-progress |  | [TASK](../unit/feature-0034-analysis-consumption/docs/TASK.md) |  |
| feature-0035-analysis-planner | in-progress |  | [TASK](../unit/feature-0035-analysis-planner/docs/TASK.md) |  |
| feature-0036-analysis-verification | in-progress |  | [TASK](../unit/feature-0036-analysis-verification/docs/TASK.md) |  |
| feature-0037-domain-synthesis | in-progress |  | [TASK](../unit/feature-0037-domain-synthesis/docs/TASK.md) |  |
| feature-0038-frontend-modularization | review | 2026-08-05 | [TASK](../unit/feature-0038-frontend-modularization/docs/TASK.md) | ITEM-P5b 본편(10 cycle) + 후속 Phase A~B3 완결 — app.js 11,119→8,082줄(-27%), 4 PR(#1147~#1150) 전건 배포·POST-DEPLOY PASS |
| feature-0039-ops-scheduler | review | 2026-08-04 | [TASK](../unit/feature-0039-ops-scheduler/docs/TASK.md) | 운영 정기 잡 4종(백업·복원 리허설·AGE 그래프 sync 증분/전량)을 호스트 root crontab → ops-scheduler 컨테이너 서비스로 이관 — docker 소켓 의존 제거(= root 권한 근거 소멸)·스케줄 정본을 compose 환경변수로 이동·§82 flock 은 bind-mou… (상세는 TASK) |
| feature-0040-db-object-explorer | review |  | [TASK](../unit/feature-0040-db-object-explorer/docs/TASK.md) |  |
| feature-0041-external-ai-tool-surface | in-progress | 2026-09-01 | [TASK](../unit/feature-0041-external-ai-tool-surface/docs/TASK.md) | P0 도구 9종 + P1 execute_sql + AC-7 답변 보존·열람 라이브 배포 완료(6cd45761) · POST-DEPLOY 10회 전건 PASS · 잔여 1건 — 사람 브라우저 인가 1회가 필요한 AC-1 e2e. 외부 사용자의 AI 가 자기 계정 LLM 으로 직접 추론하며 데이터소스·R… (상세는 TASK) |
| feature-0042-analysis-dedup | done | 2026-08-14 | [TASK](../unit/feature-0042-analysis-dedup/docs/TASK.md) | 조사·검증 cycle 완결 — 런타임 코드 변경 0건, 산출물은 판정이다. 분석 워커 LLM 요청당 낭비(입력의 약 80%가 고정 시스템 프롬프트)를 회수할 수 있는지 실측 판정: batch 두 해석 전건 기각(Batches API — 전송경로 부재·구독형이라 할인가치 0·24h SLA 불일치 / 다… (상세는 TASK) |
| feature-0043-external-llm-bridge | in-progress | 2026-09-07 | [TASK](../unit/feature-0043-external-llm-bridge/docs/TASK.md) | 서버 보유 계정(claude-corp/root) LLM 호출 전면 차단 + 웹 대화 질문을 개인 머신 AI 가 처리하는 pull 브리지. 사용자 결정(2026-08-26): 추론 주체를 서버에서 각 사용자의 AI 런타임으로 옮긴다(배경: 2026-08-07 claude-corp 7일 쿼터 100% 소… (상세는 TASK) |
| feature-0044-qa-staging-pipeline | planned | 2026-08-27 | [TASK](../unit/feature-0044-qa-staging-pipeline/docs/TASK.md) | QA·라이브 분리 CI/CD 설계 rev.3 확정 (전제 13축 중 12축 결정 — SVN 안 A(매니페스트만)+파일서버 tar · docker save 릴레이 · 빌드 서버 이관 경로 · 로컬 LLM 전면 폐지로 GPU 불요, 단 임베딩 사내 MCP 이관이 QA 세팅 선행 조건). 구현 착수는 사용자 승인 대기 |
| feature-0045-zd-bridge-continuity | review | 2026-08-27 | [TASK](../unit/feature-0045-zd-bridge-continuity/docs/TASK.md) | 웹브라우저–개인 AI 브리지가 연결된 상태에서 배포가 진행돼도 그 작업이 끊기지 않게 무중단 스파인을 재구성. 배경: feature-0043 전환으로 추론 주체가 개인 머신 AI 로 넘어가면서 사용자 작업이 WebAiTasks + 브리지 왕복 위에서 일어나게 됐는데, 배포 게이트는 여전히 active… (상세는 TASK) |
| feature-0046-native-client | in-progress |  | [TASK](../unit/feature-0046-native-client/docs/TASK.md) |  |
<!-- AI-EDITABLE:STATUS-TABLE:END -->

### Worktree 확인

표는 이 체크아웃에 반영된 기능 상태다. 미머지 작업의 정본은 해당 worktree의
`unit/<feature>/docs/{TASK,REPORT}.md`다. 다른 세션의 이력이 새 실행 권한을 주지는 않는다.

이전 **2026-09-04 관측 스냅샷**(ahead > 0인 7개 worktree 및 이미 착륙한 2개 기록)은
[정리 전 STATUS](./archive/delegation-friction-20260908/STATUS-before.md)에 보존했다.
이 과거 목록을 현재 활성 목록으로 사용하지 않는다. 작업 시작 시 저장소 루트에서 확인한다:

```bash
git worktree list --porcelain
git status --short --branch
```

특정 branch의 미머지 여부는 확인한 기준 branch와 `git log <base>..<branch>`로 대조한다.
디렉토리 존재나 과거 ahead 수만으로 세션 활성·완료·정리 가능 여부를 판정하지 않는다.

### 상태 값 정의
`planned`(요구 정리) · `in-progress`(구현 중) · `blocked`(승인/불명확 차단) · `review`(검토) · `done`(완료) · `deprecated`(폐기)

## 2. 기능 간 의존성 요약

[ARCHITECTURE.md](./ARCHITECTURE.md) §6이 전체 의존 관계의 정본이다.
코드 수정 범위는 같은 문서 §4의 책임 및 기능별 FUNCTION에서 확인한다.

## 3. 블로킹 항목
- **SSOT 통합(META-0003) Phase 3** — tracked secret 노출 종료(`.env.secret.bak-task0228` 등)는 **rotation(사용자) 선행** 필요. 근거: ADR-0031 §4 / [DOC_REGISTRY.md](./DOC_REGISTRY.md).
- **feature-0041**: 기존 기록의 잔여 AC-1은 사람 브라우저 인가 1회가 필요한 e2e다. [TASK](../unit/feature-0041-external-ai-tool-surface/docs/TASK.md).
- **feature-0044**: CI/CD rev.3 설계 이후 구현 착수는 사용자 승인 대기이며, 임베딩 사내 MCP 이관이 QA 세팅 선행 조건이다. [TASK](../unit/feature-0044-qa-staging-pipeline/docs/TASK.md).
- **feature-0042 조사 후속**: ITEM-15의 `BLOCKED: verification-sample-insufficient`는 조사 완료와 별개인 후속 후보 제약이다. [TASK](../unit/feature-0042-analysis-dedup/docs/TASK.md).

위 항목은 정리 전 문서의 미해소 기록을 보존한 것이다. 기능 상태를 `blocked`로 재판정하거나
과거 승인을 새 실행 권한으로 해석하지 않는다. 착수 전에 해당 TASK에서 해소 여부를 확인한다.

## 4. 통합 테스트 현황
- 구조/기동 점검: `docker compose config`, `make status/web/browser-up/browser-health`, `GET /api/session`. 이것만으로 기능 검증을 대체하지 않는다.
- 테스트 실행 경로: `Makefile`의 `test` 및 `pyproject.toml`의 `testpaths`. 웹/UI 변경은 AGENTS.md §15.4.1의 Windows 브라우저 게이트를 적용한다.
- 기능별 테스트 정본: `unit/<feature>/docs/TEST.md`.
- 정리 전 ARCHITECTURE의 미검증 기록: feature-0025 관리 UI와 feature-0040 객체 탐색은 POST-DEPLOY PB-0008 잔여, feature-0020의 바쁜 워커 drain 완결 궤적은 미관측이다. 현재 해소 여부는 해당 TASK/TEST에서 확인한다.
- feature-0039는 과거 라이브 cutover 관측과 TASK 체크박스가 어긋났다는 기록이 있어 `review`를 유지했다. feature-0046은 첫 실 릴리스 반입/엣지 경유 검증이 잔여로 기록돼 있으며, 구현 존재만으로 배포 완료를 판정하지 않는다.

## 5. 상태별 집계
- 등록 기능: **46행 / 46개 기능 디렉토리**(2026-09-08 표 재집계). 숫자 접두 ID는 45종 — feature-0016은 metadata-graph + zd-pg-pause-caddy 2슬라이스이며 번호 충돌에 대한 사람 결정은 보류 상태다.
- review 10 (feature-0008/0012/0014/0015/0016-zd-pg-pause-caddy/0017/0038/0039/0040/0045) · in-progress 33 · done 2 (feature-0011/0042) · planned 1 (feature-0044) · blocked 0
- 합계는 완료율이 아니다. 빈 갱신일이나 요지는 TASK에 값이 없는 경우이며 날짜·완료를 추정하지 않는다.
- 상세 진척·이력: 각 unit TASK.md / [STATUS_ARCHIVE.md](./archive/STATUS_ARCHIVE.md)
