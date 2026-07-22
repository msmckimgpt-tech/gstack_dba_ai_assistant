---
doc_type: WIKI_INDEX
scope: project
status: active
edit_policy: ai-maintained
source_of_truth: false
template_version: v3.13.0
domain: [navigation, wiki]
ai_read_priority: 7
wiki_role: index
wiki_name: project
confidence: high
maturity: substantial
ai_generated: true
sources:
  - ../../docs/ARCHITECTURE.md
  - ../../docs/STATUS.md
---

# Features — MOC

| 항목 | 값 |
|---|---|
| 분류 | `#wiki/index` |
| 정본 영역 | `unit/feature-NNNN-<purpose>/docs/FUNCTION.md` |
| Feature 수 | 23 active |
| Wiki layer | mirror (입구점) |

## 목차

1. [개요](#1-개요)
2. [Active features](#2-active-features)
3. [Archived / completed](#3-archived--completed)
4. [Skeleton](#4-skeleton)
5. [관련 문서](#5-관련-문서)
6. [둘러보기](#6-둘러보기)
7. [외부 link](#7-외부-link)
- [분류](#분류)

## 1. 개요

23 개 feature 카드(feature-0016 은 metadata-graph + zd-pg-pause-caddy 2 슬라이스, feature-0018 은 카드 없는 슬라이스로 feature-0003 코드 거주)의 *사람용 카드* 입구. 정본은 `unit/<id>/docs/FUNCTION.md`. AI 가 새 feature 를 생성할 때마다 본 MOC 에 1줄 entry 추가 + `Features/<feature-slug>.md` 동반 (`AGENTS.md §21` 의무).

## 2. Active features

| Feature | 상태 | 책임 한 줄 | 카드 | 정본 |
|---|---|---|---|---|
| feature-0001-platform-runtime | active | MySQL/DAB · replica 연결 · redo log 1 GiB | [[feature-0001-platform-runtime]] | `unit/feature-0001-platform-runtime/docs/FUNCTION.md` |
| feature-0002-agent-core | active | agent core · 멀티 데이터소스(MySQL·MSSQL) · KB Postgres · insight worker | [[feature-0002-agent-core]] | `unit/feature-0002-agent-core/docs/FUNCTION.md` |
| feature-0003-agent-web-ui | active | FastAPI Web UI · 관리콘솔(데이터소스·대시보드) · audit · 첨부 · ask-worker | [[feature-0003-agent-web-ui]] | `unit/feature-0003-agent-web-ui/docs/FUNCTION.md` |
| feature-0004-browser-automation | active | Playwright HTTP 제어 service | [[feature-0004-browser-automation]] | `unit/feature-0004-browser-automation/docs/FUNCTION.md` |
| feature-0005-qa-mcp | active | MCP 연결 검증 · QA 보조 | [[feature-0005-qa-mcp]] | `unit/feature-0005-qa-mcp/docs/FUNCTION.md` |
| feature-0006-lan-proxy-access | active | Caddy TLS · Windows LAN proxy · XFF trust | [[feature-0006-lan-proxy-access]] | `unit/feature-0006-lan-proxy-access/docs/FUNCTION.md` |
| feature-0007-bedrock-llm-provider | active | AWS Bedrock (Claude) gateway · API Vault 폐기 | [[feature-0007-bedrock-llm-provider]] | `unit/feature-0007-bedrock-llm-provider/docs/FUNCTION.md` |
| feature-0008-windows-browser-testing | active | 실제 Windows 브라우저 AI 자동 검증 (PB-0008 · ADR-0029) | [[feature-0008-windows-browser-testing]] | `unit/feature-0008-windows-browser-testing/docs/FUNCTION.md` |
| feature-0009-group-conversation | active | 그룹 대화 — 멤버십·@assistant 멘션·열람≠발화 분리·라이브 UX | [[feature-0009-group-conversation]] | `unit/feature-0009-group-conversation/docs/FUNCTION.md` |
| feature-0010-google-drive-integration | active (토대) | Google Drive 연동 토대 — 계정별 OAuth 토큰 암호화 저장 + MCP 구성 seam (연동 미수행/비활성) | [[feature-0010-google-drive-integration]] | `unit/feature-0010-google-drive-integration/docs/FUNCTION.md` |
| feature-0011-shared-extraction | active (리팩터) | 공통 코드 `shared/` 점진 추출 — model_catalog·config·db 모듈 alias (P5a, 회귀 0) | [[feature-0011-shared-extraction]] | `unit/feature-0011-shared-extraction/docs/FUNCTION.md` |
| feature-0012-web-router-modularization | active | feature-0003 `app.py` 도메인별 `APIRouter` 분할 — route 핸들러 전량 추출 완료(148→21 도메인 라우터, byte-동치, P5b behavior-neutral) | [[feature-0012-web-router-modularization]] | `unit/feature-0012-web-router-modularization/docs/FUNCTION.md` |
| feature-0013-relationship-diagrams | active | flow/관계 질문에 mermaid 다이어그램 답변 + 관계 저장소(FK introspection·대화 JOIN 학습) | [[feature-0013-relationship-diagrams]] | `unit/feature-0013-relationship-diagrams/docs/FUNCTION.md` |
| feature-0014-zero-downtime-deploy | review | web 무중단 롤링 배포 — Caddy LB(web-a/web-b) + `bin/deploy-web.sh`(flock·coalesce·TLS preflight·migrate-lint·one-at-a-time+SSE pre-drain·soak 자동롤백) + `/livez`·`/readyz` + :18080 폐기 | [[feature-0014-zero-downtime-deploy]] | `unit/feature-0014-zero-downtime-deploy/docs/FUNCTION.md` |
| feature-0015-zd-hygiene-backup | review | 백엔드/DB 무중단 위생(0014 후속) — insight-worker graceful + MySQL online-DDL 게이트(`mysql-ddl-lint`) + 백업 복원 리허설(`restore-rehearsal`)+cron | [[feature-0015-zd-hygiene-backup]] | `unit/feature-0015-zd-hygiene-backup/docs/FUNCTION.md` |
| feature-0016-metadata-graph | in-progress | AGE 메타데이터 지식그래프(관계형 SSOT→`metadata_kb` 투영) + 관리콘솔 그래프 뷰(PixiJS v8 WebGL) + `graph_navigate` AI 도구 — cutover 라이브 완료 + (07-01) WebGL 렌더러·암묵(FK 미선언) 관계 추론·AI 능동 분석·메타데이터 탭 권한 5분할 + (07-13) 렌더러 PixiJS v8 전면 교체·콘텐츠 밴드 그룹핑 | [[feature-0016-metadata-graph]] | `unit/feature-0016-metadata-graph/docs/FUNCTION.md` |
| feature-0016-zd-pg-pause-caddy | review | PG pgbouncer PAUSE 래퍼(`pg-restart.sh`, near-zero PG 재시작) + deploy-web.sh Caddyfile reconcile(변경 시 caddy recreate) | [[feature-0016-zd-pg-pause-caddy]] | `unit/feature-0016-zd-pg-pause-caddy/docs/FUNCTION.md` |
| feature-0017-deploy-build-gate | review | deploy-web.sh 빌드 게이트 snap-docker metadata-file race false-failure 수정(이미지 정합 검증) | [[feature-0017-deploy-build-gate]] | `unit/feature-0017-deploy-build-gate/docs/FUNCTION.md` |
| feature-0019-message-editing | in-progress | 메시지 편집 — 1:1 대화 내부 브랜치 트리(단순 수정 / 요청 수정=분기 재답변 `< n/m >` 페이징)·공유(그룹)=단순 수정만 · Phase 1+2 라이브(마이그 0041·PB-0008) | [[feature-0019-message-editing]] | `unit/feature-0019-message-editing/docs/FUNCTION.md` |
| feature-0020-zd-deploy-all | in-progress | 무중단 배포 커버리지 완성 — 워커(insight/ask) 자동 롤아웃·bedrock-gateway surge 무중단 교체·caddy 이미지 드리프트·alembic stale-image 가드 (deploy 스파인 확장) | [[feature-0020-zd-deploy-all]] | `unit/feature-0020-zd-deploy-all/docs/FUNCTION.md` |
| feature-0021-redteam-review | in-progress | assistant 답변 자가 적대(red-team) 리뷰 — fresh-context 5축 검증(find→revise→verify·강도 게이팅·fail-open)+[세션,제품] 메모리 노트(TTL)+콘솔 'AI 추론' 탭 (Claude Code 패턴 이식, 코드 거주 0002/0003/shared) | [[feature-0021-redteam-review]] | `unit/feature-0021-redteam-review/docs/FUNCTION.md` |
| feature-0022-agent-scratch-workspace | in-progress | assistant PG 자율 작업공간 — 전용 DB `agent_scratch`(대화별 격리 스키마)에서 외부 데이터소스 반입·cross-source JOIN·TTL(24h 기본) 정리·scratch_guard allowlist (2026-07-21 라이브 활성·기본값 OFF 게이트 · 코드 거주 0002/shared) | [[feature-0022-agent-scratch-workspace]] | `unit/feature-0022-agent-scratch-workspace/docs/FUNCTION.md` |
| feature-0023-conversation-api-access | in-progress | 외부 AI용 Conversation API — 세션 쿠키 없이 **Bearer 토큰**으로 대화 API(`/api/ask` 등) 호출 + 대화를 tool 화하는 MCP 서버(tool 4종) · scope allowlist(`conversation.*`+`product.access.*`) ∩ 계정권한 · `*.any`/관리 네임스페이스 절대 denylist → 관리 콘솔 차단 (2026-07-22 배포·라이브 e2e 통과: 토큰→/api/ask 200·admin 403·무토큰 401 · 코드 거주 0003/0002) | [[feature-0023-conversation-api-access]] | `unit/feature-0023-conversation-api-access/docs/FUNCTION.md` |

## 3. Archived / completed

| Feature | 종료 | 카드 |
|---|---|---|
| (없음) | — | — |

## 4. Skeleton

- [[_template-card]] — 새 feature 추가 시 복제할 카드 형식
- [[../_templates/feature-card]] — Obsidian Templater 호환 노트 템플릿

## 5. 관련 문서

- [[../Architecture/Module-Map|Module Map]] — feature 가 어디에 위치하는지
- [[../Decisions/_Index|Decisions MOC]] — feature 관련 ADR
- [[../../docs/STATUS|docs/STATUS.md]] (정본 — 진행률)
- [[../../docs/ARCHITECTURE|docs/ARCHITECTURE.md]] §4 (정본 — 기능 맵)

## 6. 둘러보기

- 상위: [[../Index|Index]]
- sibling: [[../Decisions/_Index]] · [[../Architecture/Overview]]

## 7. 외부 link

- 없음

## 분류

`#wiki/index` · `#confidence/high` · `#maturity/substantial`
