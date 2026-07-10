---
doc_type: WIKI_ARTICLE
scope: project
status: active
edit_policy: ai-maintained
source_of_truth: false
template_version: v3.13.0
domain: [architecture, wiki]
ai_read_priority: 7
wiki_role: article
wiki_name: project
confidence: high
maturity: substantial
ai_generated: true
sources:
  - ../../docs/ARCHITECTURE.md
  - ../../docs/PROJECT.md
  - ../../docs/CODEBASE_MAP.md
---

# Architecture — Overview

| 항목 | 값 |
|---|---|
| 분류 | `#wiki/article` |
| 정본 | [[../../docs/ARCHITECTURE\|docs/ARCHITECTURE.md]] |
| Wiki layer | mirror (graph 입구) |
| Feature 수 | 17 (feature-0001 ~ feature-0017; feature-0016 은 metadata-graph + zd-pg-pause-caddy 2 슬라이스) |

## 목차

1. [개요](#1-개요)
2. [상세](#2-상세)
     - [2.1 책임 분리 (정본 §2)](#21-책임-분리-정본-2)
     - [2.2 기능 단위 구조 (정본 §3)](#22-기능-단위-구조-정본-3)
     - [2.3 현재 기능 맵 (정본 §4)](#23-현재-기능-맵-정본-4)
     - [2.4 기능 간 의존성 (정본 §6)](#24-기능-간-의존성-정본-6)
3. [특징](#3-특징)
4. [관련 문서](#4-관련-문서)
5. [둘러보기](#5-둘러보기)
6. [외부 link](#6-외부-link)
- [분류](#분류)

## 1. 개요

저장소는 **공통 정책 영역 / 기능 영역 / 공통 코드 영역 / 산출물 영역** 4 layer 로 분리되어, 기능별 소유권을 명확히 하면서도 단일 docker-compose 로 실행 가능하다. 정본은 [[../../docs/ARCHITECTURE|docs/ARCHITECTURE.md]] §1 — 본 노트는 그 mirror.

## 2. 상세

### 2.1 책임 분리 (정본 §2)

| Layer | 위치 | 책임 |
|---|---|---|
| 공통 정책 | `AGENTS.md`, `docs/*.md` | 프로젝트 전반 규칙·제약·용어·보안 기준 |
| 기능 영역 | `unit/<feature-id>/{src,tests,docs}/` | 기능별 코드·테스트·명세·이력·리뷰·보고 |
| 공통 코드 | `shared/` | 여러 기능에서 공통 사용하는 코드 (필요 시) |
| 산출물 | `../../artifacts/*` (repo 외부) | 빌드 결과, 로그, MySQL 데이터, 세션, 인증서 |

### 2.2 기능 단위 구조 (정본 §3)

각 feature 는 다음 sub-tree 를 갖는다:

```
unit/feature-NNNN-<purpose>/
├── src/      # 기능 구현
├── tests/    # 기능 테스트
└── docs/     # FUNCTION/TASK/REPORT/MODIFY/REVIEW/ANCHOR/...
```

### 2.3 현재 기능 맵 (정본 §4)

| Feature ID | 책임 |
|---|---|
| [[../Features/feature-0001-platform-runtime\|feature-0001-platform-runtime]] | MySQL/DAB 설정 + replica 연결 |
| [[../Features/feature-0002-agent-core\|feature-0002-agent-core]] | agent CLI / core / KB Postgres |
| [[../Features/feature-0003-agent-web-ui\|feature-0003-agent-web-ui]] | FastAPI Web UI + audit subsystem |
| [[../Features/feature-0004-browser-automation\|feature-0004-browser-automation]] | Playwright browser service |
| [[../Features/feature-0005-qa-mcp\|feature-0005-qa-mcp]] | MCP / QA scripts |
| [[../Features/feature-0006-lan-proxy-access\|feature-0006-lan-proxy-access]] | Caddy TLS + Windows LAN proxy |
| [[../Features/feature-0007-bedrock-llm-provider\|feature-0007-bedrock-llm-provider]] | AWS Bedrock (Claude) gateway |
| [[../Features/feature-0008-windows-browser-testing\|feature-0008-windows-browser-testing]] | 실제 Windows 브라우저 AI 자동 검증 (PB-0008) |
| [[../Features/feature-0009-group-conversation\|feature-0009-group-conversation]] | 그룹 대화 — 멤버십 · `@assistant` 멘션 · 열람≠발화 분리 |
| [[../Features/feature-0010-google-drive-integration\|feature-0010-google-drive-integration]] | Google Drive 연동 토대 — 계정별 OAuth 암호화 + MCP seam (비활성) |
| [[../Features/feature-0011-shared-extraction\|feature-0011-shared-extraction]] | 공통 코드 `shared/` 점진 추출 (P5a — model_catalog·config·db alias) |
| [[../Features/feature-0012-web-router-modularization\|feature-0012-web-router-modularization]] | web `app.py` 도메인별 `APIRouter` 분할 (P5b — route 핸들러 전량 추출 완료: 148→21 도메인 라우터, byte-동치 behavior-neutral) |
| [[../Features/feature-0013-relationship-diagrams\|feature-0013-relationship-diagrams]] | flow/관계 질문에 mermaid 다이어그램 답변 + `table_relationships` 관계 저장소 (FK introspection·대화 JOIN 학습) |
| [[../Features/feature-0014-zero-downtime-deploy\|feature-0014-zero-downtime-deploy]] | web 무중단 롤링 배포 — Caddy LB(web-a/web-b) + `bin/deploy-web.sh`(자동 롤백) + `/livez`·`/readyz` + :18080 폐기 |
| [[../Features/feature-0015-zd-hygiene-backup\|feature-0015-zd-hygiene-backup]] | 백엔드/DB 무중단 위생 — insight-worker graceful + MySQL online-DDL 게이트 + 백업·복원 리허설 cron |
| [[../Features/feature-0016-metadata-graph\|feature-0016-metadata-graph]] | 메타데이터 지식그래프 — 관계형 SSOT→AGE `metadata_kb` 투영 + 관리콘솔 그래프 뷰 + `graph_navigate` AI 도구 (cutover 라이브 완료 · 07-01 WebGL·암묵 관계 추론·AI 능동 분석·권한 5분할) |
| [[../Features/feature-0016-zd-pg-pause-caddy\|feature-0016-zd-pg-pause-caddy]] | PG 재시작 무중단화 — pgbouncer PAUSE 래퍼 + deploy-web.sh Caddyfile reconcile |
| [[../Features/feature-0017-deploy-build-gate\|feature-0017-deploy-build-gate]] | 배포 스파인 빌드 게이트 false-failure 수정 (snap-docker metadata-race 이미지 정합 검증) |

### 2.4 기능 간 의존성 (정본 §6)

| Feature | 의존 대상 | 유형 | 비고 |
|---|---|---|---|
| feature-0003 | feature-0002 | uses | Web UI → core import |
| feature-0003 | feature-0006 | uses | `_get_client_ip` 가 Caddy `trust_forwarded_for` 의존 |
| feature-0004 | feature-0001 | uses | 운영 런타임 공유 |
| feature-0005 | feature-0001, feature-0002, feature-0004 | uses | Compose + agent + browser smoke |
| feature-0006 | feature-0001 | uses | Web/TLS 운영 자산 공유 |
| feature-0007 | feature-0002, feature-0003 | uses | LLM 호출 단일 진입점 통합 |
| feature-0009 | feature-0003, feature-0002 | uses | Web UI(공유·첨부·avatar) + ask_jobs 큐(`@assistant`) 위 그룹 대화 |
| feature-0010 | feature-0003, feature-0002 | uses | 인증/라우트 app.py 인라인 + `cred_crypto` 토큰 암호화 |
| feature-0011 | feature-0002, feature-0003 | uses | 공통 모듈 `shared/` 추출 + import 재배선 (모듈 alias shim) |
| feature-0012 | feature-0003 | uses | `app.py` 도메인별 `APIRouter` 분할 — route 핸들러 전량 추출 완료(21 도메인 라우터, behavior-neutral) |
| feature-0013 | feature-0002, feature-0003 | uses | 발화 가이던스·관계 저장소·introspection·JOIN 학습은 feature-0002, mermaid 웹 렌더는 feature-0003 (cross-cut) |
| feature-0014 | feature-0003, feature-0006 | uses | 무중단 롤링 = web `/livez`·`/readyz`·SSE 카운터(0003) + Caddy LB·active health·:443 단일(0006) |
| feature-0015 | feature-0002 | uses | insight-worker graceful 핸들러가 feature-0002 `modules/insight.py` 거주 |
| feature-0016-metadata-graph | feature-0002, feature-0003, feature-0013, feature-0014 | uses | 동기화·투영·`graph_navigate`·introspection=0002, 그래프 뷰=0003, 관계 저장소=0013 재사용, AGE 이미지 cutover=0014 무중단 정합 |
| feature-0016-zd-pg-pause-caddy | feature-0002, feature-0006 | uses | pg-restart=0002 PG/pgbouncer, reconcile_caddy=0006 Caddyfile |
| feature-0017 | feature-0014 | extends | feature-0014 배포 스파인 build_image 게이트 보강 |

의존 유형 어휘 (`requires` / `uses` / `extends`) 정본은 ARCHITECTURE.md §6.

## 3. 특징

- **source of truth 원칙** (정본 §5): 동일 사실을 여러 문서에 중복 확정하지 않는다. FUNCTION/TASK/REPORT/MODIFY/REVIEW/DECISIONS/STATUS 의 각 책임이 분리됨.
- **runtime artifacts 외부화**: 로그·세션·MySQL data 가 `../../artifacts/` 로 분리되어 git 추적 대상 아님.
- **AI 위임 친화**: AI 가 작업 시 `AGENTS.md` 우선 read + 각 feature 의 `docs/` 자동 참조.
- **멀티 데이터소스 (2026-06)**: data plane 이 단일 MySQL → N 개 데이터소스 (MySQL·MSSQL) 로 일반화. dialect 추상화 + envelope 암호화 registry + DB-단위 접근. 상세 [[Data-Flow]] §2.5 · [[../concepts/multi-datasource]].
- **storage 단일화 (2026-05-27)**: agent runtime + KB 모두 Postgres 단독 (`agent_kb`/`agent_runtime`). MySQL 은 `web*` 18 테이블만 (Phase 3 대상). [[../Decisions/ADR-0027-agent-runtime-pg-schema]] · [[../Decisions/ADR-0028-runtime-mysql-cleanup]].
- **그룹 대화 + 보안 보강 (2026-06-19~23)**: 단일 owner 대화 → 멤버십 기반(feature-0009, **열람 ≠ 발화** RBAC 분리). 사용자 보안 보강 6종(공유 만료·로그인 제한·감사 변조방지·LLM 한도·인젝션 방지·2FA) 완료. [[../Features/feature-0009-group-conversation]] · [[../../docs/SECURITY|SECURITY.md]].
- **NL→SQL 정확도 flywheel (2026-06)**: 평가 harness + 샘플쿼리 few-shot(pgvector) + self-reflection + 용어/ENUM 사전. [[../concepts/nl2sql-flywheel]].
- **메타데이터 거버넌스 + 토대 확장 (2026-06-24)**: ITEM-11 관리 콘솔 메타데이터 거버넌스(용어·ENUM·테이블/컬럼 설명·주입·AI 자동완성)로 NL→SQL 컨텍스트 강화. feature-0010 Google Drive 연동 토대(계정별 OAuth 암호화 + MCP seam, 비활성). feature-0011 공통 코드 `shared/` 점진 추출(P5a). [[../Features/feature-0011-shared-extraction]].
- **피드백 고유화 · 용어사전 자율등록 · router 분할 토대 (2026-06-29)**: 답변 피드백(👍/👎) 답변당 고유화(새로고침·전환 후 중복 차단). 관리 콘솔 용어사전 대화 자율등록(역할 분리·유사어·검토 큐 + 용어 검토 큐 IA 중첩). feature-0012 web `app.py` 도메인별 `APIRouter` 점진 분할 토대(P5b — route-parity 안전망 + 의존성 audit, behavior-neutral). [[../Features/feature-0012-web-router-modularization]].
- **관계 다이어그램 신규 · 메타데이터/공유 화면 정리 (2026-06-29)**: feature-0013 관계 다이어그램 — assistant 가 flow/관계 질문에 mermaid(ER·flowchart)로 답하고 `table_relationships` 관계 저장소(FK introspection·대화 JOIN 학습, alembic 0024)로 지속 학습(PB-0008 라이브 PASS). 메타데이터 스키마 골격 화면 접기·검색·페이지네이션·여백 압축, 공유 대화 뷰 mermaid 렌더·전체폭 반응형·스크롤 가이드, 용어사전 역할 선택 단일화. [[../Features/feature-0013-relationship-diagrams]].
- **무중단 배포·운영 위생 + 메타데이터 지식그래프 (2026-06-30)**: web 무중단 롤링 배포(Caddy LB web-a/web-b 2-replica·자동 롤백·:18080 폐기→:443 단일, feature-0014) + 백엔드/DB 위생(insight graceful·MySQL online-DDL·백업 복원 리허설, feature-0015) + PG 재시작 무중단화(pgbouncer PAUSE 래퍼, feature-0016-zd-pg-pause-caddy) + 배포 빌드게이트 false-failure 수정(feature-0017). 관리콘솔 메타데이터를 Apache AGE 지식그래프(관계형 SSOT→`metadata_kb` 투영)로 승급 + 그래프 뷰·`graph_navigate` AI 도구(feature-0016-metadata-graph, cutover 라이브 완료). [[../Features/feature-0016-metadata-graph]].
- **그래프 뷰 진화 + 라우터 모듈화 완료 (2026-07-01)**: feature-0016 메타데이터 그래프 뷰가 canvas→WebGL 렌더러 전환(프레임레이트 근본 대응)·암묵(FK 미선언) 관계 추론+자기교정 엔진(추정=점선/신뢰=실선, ADR-002)·AI 능동 분석 앵커-상대 관련도 게이팅+실시간 진행 패널·ERD 컬럼 ordinal·메타데이터 탭 권한 5분할(B안)로 대폭 성숙. feature-0012 web `app.py` 148 route 핸들러 전량을 21개 도메인 `APIRouter` 로 byte-동치 추출 완료(behavior-neutral, batch1-3 라이브 배포). [[../Features/feature-0016-metadata-graph]] · [[../Features/feature-0012-web-router-modularization]].

## 4. 관련 문서

- [[Data-Flow]] — 데이터 흐름 다이어그램
- [[Module-Map]] — 디렉토리 ↔ 책임 매핑
- [[../../docs/PROJECT|docs/PROJECT.md]]
- [[../../docs/ARCHITECTURE|docs/ARCHITECTURE.md]] (정본)

## 5. 둘러보기

- 상위: [[../Index|Index]] · [[../overview|overview]]
- sibling: [[Data-Flow]] · [[Module-Map]]
- 관련 ADR: [[../Decisions/ADR-0012-feature-unit-restructure]] · [[../Decisions/ADR-0013-shared-runtime-separation]] · [[../Decisions/ADR-0016-template-v3]]

## 6. 외부 link

- 없음 (모두 repo 안 정본)

## 분류

`#wiki/article` · `#confidence/high` · `#maturity/substantial`
