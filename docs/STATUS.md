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
---

# Project Status (인덱스)

프로젝트를 cross-feature 관점에서 한눈에 보는 **인덱스**다 (ADR-0031 SSOT 계약 §1 — 셀에 TASK 상세를 누적하지 않는다).

- **기능별 상세 현황 정본**: `unit/<feature>/docs/{TASK,REPORT}.md` — 본 문서는 그 요약·링크만.
- **인덱스화 이전 누적 rollup·상세 이력**: [docs/archive/STATUS_ARCHIVE.md](./archive/STATUS_ARCHIVE.md) (verbatim 보존).
- 정본 지도: [docs/DOC_REGISTRY.md](./DOC_REGISTRY.md) · SSOT 계약: [docs/DECISIONS.md](./DECISIONS.md) ADR-0031.

## 1. 기능 현황 (요약 인덱스)

| 기능 ID | 상태 | 최종 갱신 | 정본(상세) | 최근 작업 요지 |
|---|---|---|---|---|
| feature-0001-platform-runtime | in-progress | 2026-05-18 | [TASK](../unit/feature-0001-platform-runtime/docs/TASK.md) | MySQL redo log 1GiB 상향·restart policy 정렬 (TASK-0064/0059) |
| feature-0002-agent-core | in-progress | 2026-07-07 | [TASK](../unit/feature-0002-agent-core/docs/TASK.md) | init "준비" 임베딩 지연 회귀 해소(전용 embed-ollama·캐싱·fast-timeout)·요청량 한도 메시지 주체 구분·datasource 회로차단 안내 문구 분리(고장 오인 해소) / ITEM-11 메타데이터 컨텍스트·NL→SQL flywheel · 용어사전 대화 자율등록 코어(role 분리·유사어·하이브리드 자동승급, mig 0023, ADR-20260629T101500) · 답변 피드백 답변당 고유화 코어(마이그 0021/0022) · (06-30) 능동 해석 지침 modality-무관 일반화(1:1·그룹 모두 주입 — 과도 재질문·스키마 추측 후 give-up·datasource 드리프트 억제)+MySQL 식별자 대소문자 보존 안내(conv-audit FR-nl2sql, 가드 불변) · (07-03) insight-worker 안정성 — 부하 분산(probe 격리·scan skip·batched graph sync)·긴-cycle heartbeat false-negative 해소(liveness throttle)·동일구조 테이블 그룹화(대표 1회 분석+형제 LLM-free 전파)·요청레벨 LLM fallback(claude-corp→root→edge) · (07-07) 대화 답변 경로 edge(gemma) 폴백 완전 차단(conv-audit FR-edge-fallback-conversation-context-loss, 저성능 로컬모델 답변 누출→맥락 손실 해소, CHG-20260707T100640)·런타임 설정 live 배선(AGENT_TIMEOUT_SEC·MCP_TIMEOUT_SEC·모델별 thinking 예산 주입, cross-unit feature-0018) |
| feature-0003-agent-web-ui | in-progress | 2026-07-07 | [TASK](../unit/feature-0003-agent-web-ui/docs/TASK.md) | 메타데이터 부트스트랩 결과 패널 접기+검색/필터 재설계(대규모 스키마 여백 과다 해소) + 패널 잘림 잔존 cache-buster 미bump 근본수정(metadata-bs-collapse) · 메타데이터 부트스트랩 MSSQL database 차원 수정(tempdb 임시테이블→선택 DB 실테이블, 시스템 스키마/DB 필터, schema_name=DB명, 데이터베이스/스키마 라벨 분기)·테이블/컬럼 설명 패널 내부 잘림 해소(bootstrap-result max-height 제거)·테이블 설명 AI 자동완성 grounding 정상화(metadata-bootstrap-mssql-db) / 제품 선택 chip 처리 중 항상 활성화(TASK-0047 race 가드 3계층 완화, ADR-WEB-0006) · 역할/제품 프롬프트 AI 자동작성·제품 분석률 95% 제품프롬프트 자동완성·규칙 자동 추가 DB insight 커버리지 UI·지식베이스 메뉴 재편 / 메타데이터 거버넌스 포탈(ITEM-11) · 좌측 대화 전환 크로스페이드 · 워커모드 assistant 요청 2번 중복 처리 차단(enqueue 멱등화 + AmbiguousParameter 회귀 파라미터 격리, ask-dedup-idempotency, cross-cut 0002) · 용어사전 대화 자율등록 UI(역할 필터/select·검토 큐 kb.glossary.curate·유사어 참조) · 용어 검토 큐 IA 중첩(메타데이터 > 용어사전 > 용어 검토 큐 2차 보기 탭, curate-only 탭 게이트 보존) · 답변 피드백(👍/👎) 답변당 고유화(새로고침·전환 후 중복 차단, id-space) · 첨부 wrong-bubble 엣지 하드닝(message_id_space) · 용어사전 역할 선택 UI 단일화(단일 역할 컨텍스트 — 폼 select 폐기, 툴바 하나가 필터+등록대상, mis-scope 토스트 가드, glossary-role-single-ui) · 용어사전 역할 드롭다운/라벨 실제 역할 미표시 버그 수정(필드명 role_key/role_name→key/name, glossary-role-fieldname-fix) · 공유 대화 뷰 우측 스크롤바 대화 가이드 뱃지(point rail) 추가 + 가이드 뱃지 클릭 스크롤 단축(280ms)·EaseOutExpo(메인/공유 양 뷰, point-scroll-easeoutexpo) · 스키마 골격 결과 페이지네이션·여백 압축(metadata-bs-paging) · 새 대화 첫 전송 사이드바 중복 제거(new-conv-dedup) · diff 답변 누출 줄번호 prefix 정규화(diff-lineno-leak) · (06-30) 메타데이터 관리 화면 list-detail 2단 재구성·데이터소스 선택 단일화(헤더 스코프 상속)·테이블 설명 인라인 입력(평면화·행간 정렬)·스키마 가져오기 시 기존 설명 prefill+변경분만 저장 (frontend-only) · (07-01) 좌측 대화 선택 시 대화창 미표시 방어 하드닝(convswitch opacity finally 보장) · 메타데이터 그래프 뷰 UX(WebGL 외곽선 선명화·단일클릭 컬럼 펼침/접힘·상세 패널 드래그 리사이즈·접기 버튼·첫 컬럼명 가림 수정) · 메타데이터 탭 권한 세분화(kb.ingest.manual → metadata.{glossary,enum,table,column}.manage + graph.read, 비파괴 하위호환) · (07-02) AI 운영 관제 패널 신설(신규 /api/admin/ai-ops·LLM 계측 확장·최근 활동 커서 페이징·pane 세로 스크롤·시스템 sentinel 대화 링크 깨짐 수정, aiops-panel/activity-paging/scroll/conv-link-fix, cross-cut 0002 _call_llm latency 계측) · 감사 카테고리 재구성+항목 툴팁+최근활동 클릭 상세 확장(audit-nav-ux) · 메타데이터(지식베이스) 권한 종속 계층화(묶음→그룹 게이트, metadata-perm-hier) · "+" 메뉴 첨부 개수 배지 대화 전환 후 stale 수정(attach-count-scope) · (07-03) 데이터소스 상세 평균 연결 응답 시간(ds-avg-latency) · AI 운영 지연 p95 단위를 단계 간 간격으로 재정의(aiops-ttft) · (07-04) 말풍선 ☰ 통합+'여기부터 공유' 범위 UI·'AI 로 고치기'도 ☰ 로 이동(피드백 👍/👎만 외부) · (07-06) 대화 화면 사용자 지정 추론 강도 선택기(낮음/일반/높음/매우높음, reasoning-effort — 대화별 영구, PB-0008 PASS) · (07-07) 관리 콘솔 시스템>설정 런타임 설정(실행 타임아웃·모델별 추론 예산 조정·저장·live/restart 하이브리드 반영, WebRuntimeSettings·admin_settings 라우터·system.runtime.read/write 권한+audit, feature-0018 코드 거주, PB-0008 PASS) |
| feature-0004-browser-automation | in-progress | 2026-04-06 | [TASK](../unit/feature-0004-browser-automation/docs/TASK.md) | 구조 이관 완료, smoke 검증 예정 |
| feature-0005-qa-mcp | in-progress | 2026-04-06 | [TASK](../unit/feature-0005-qa-mcp/docs/TASK.md) | 스켈레톤 — MCP 기동 검증 예정 |
| feature-0006-lan-proxy-access | in-progress | 2026-04-06 | [TASK](../unit/feature-0006-lan-proxy-access/docs/TASK.md) | caddy 운영 자산 이관 완료 |
| feature-0007-bedrock-llm-provider | in-progress | 2026-07-04 | [TASK](../unit/feature-0007-bedrock-llm-provider/docs/TASK.md) | AWS Bedrock(Seoul) provider 통합, API Vault 폐기 (ADR-0022) · (07-04) insight 주말/야간 gemma 고착 해소 — 용도별 모델 라우팅 분리(interactive/insight fallback 체인 정정, llm-routing) |
| feature-0008-windows-browser-testing | review | 2026-06-04 | [TASK](../unit/feature-0008-windows-browser-testing/docs/TASK.md) | Windows 브라우저 자동 구동 + Playwright MCP (PB-0008) |
| feature-0009-group-conversation | in-progress | 2026-07-04 | [TASK](../unit/feature-0009-group-conversation/docs/TASK.md) | 안 읽은 메세지/@멘션 배지(gc-unread-badge, REQ-GC-R8 read-state, alembic 0019 + 0020 baseline backfill + read-fix 커서 전진 보정 + read-500-fix(읽음 API `POST /read` 서버 import 정정 `modules.db`→`shared.db`) + read-idspace-fix(읽음 커서·unread 집계는 core_messages.id 공간인데 FE 가 표시 store messages.id 를 보내 GREATEST 가 전진 영구 거부하던 최종 근본원인 — 핸들러가 항상 MAX(core_messages.id)로 전진) — 읽지 않은 신규만 집계, 읽으면 0) · 공유 대화 join 불가 수정(PG named-param 타입 모순 AmbiguousParameter 해소) · assistant SQL dialect 교정+발신자 맥락 라벨(MySQL T-SQL thrashing 해소, agent-core) · optimistic 발신자 표시 정정(전송 직후 owner 오표시 깜빡임 제거) · 참가자 per-message 제품 선택·발화(authz, REQ-GC-R7) · 라이브 UX(처리 중 composer 비잠금·1:1 인터럽트 재요청·그룹 @assistant 중복차단)·owner 게이트 · (07-03) 공유 링크 참여 시 '참여 알림' pill+기존 멤버 unread(gc-join-notice) · (07-04) 멤버 가시성 [from,to] window 공유 범위 — fork clip·join stamp·owner-answer 태그, SECURITY §21/§21.4 recall 봉인(share-visibility-window) (cross-cut: 0002/0003) |
| feature-0010-google-drive-integration | in-progress | 2026-06-23 | [TASK](../unit/feature-0010-google-drive-integration/docs/TASK.md) | Google Drive 연동 토대 — 계정별 OAuth 토큰 암호화 + MCP 구성 seam (연동 미수행/비활성 scaffold) |
| feature-0011-shared-extraction | in-progress | 2026-06-25 | [TASK](../unit/feature-0011-shared-extraction/docs/TASK.md) | `shared/` 공통 코드 추출 P5a Step1~5c 완료 (model_catalog·config·db·conn_health·datasources 소비처 마이그레이션 + alias shim 4종 전량 제거, make test 회귀 0); 잔여 Step6(feature Dockerfile 분리) |
| feature-0012-web-router-modularization | in-progress | 2026-07-01 | [TASK](../unit/feature-0012-web-router-modularization/docs/TASK.md) | P5b 전체추출 완료 — app.py 모놀리스 148 route 핸들러 전량을 21개 도메인 APIRouter 로 byte-동치 추출(app.py ~29K→18,917줄, 잔여 @app 라우트 0, helpers+DI seam+include_router 잔류). batch1-3 라이브 배포·검증 완료(main c031b5d); batch4(잔여 16 route)는 추출 완료·재배포 검증 후속. 잔여: web_context 헬퍼 추출·프론트(admin.js/app.js) 분할·Final 로그인 QA·batch4 재배포 (behavior-neutral 내부 리팩터) |
| feature-0013-relationship-diagrams | in-progress | 2026-06-29 | [TASK](../unit/feature-0013-relationship-diagrams/docs/TASK.md) | flow/관계 질문에 mermaid 다이어그램 답변 — 웹 UI mermaid 렌더(vendor v10.9.3, sanitize-후 strict 렌더) + `_MERMAID_DIAGRAM_GUIDANCE` 발화 + `table_relationships` 관계 저장소(FK introspection·대화 JOIN 학습, mig 0024) + knowledge digest 주입 (cross-cut: 0002/0003). 코드+단위검증 완료 + mermaid render orphan/erDiagram "Syntax error" 봉인(rd-h2/h3) + PB-0008 라이브 검증 PASS·배포 완료(rd-h6) |
| feature-0014-zero-downtime-deploy | review | 2026-06-30 | [TASK](../unit/feature-0014-zero-downtime-deploy/docs/TASK.md) | web 무중단 롤링 배포 — Caddy LB 뒤 web-a/web-b 2-replica + 배포 스파인 `bin/deploy-web.sh`(flock+origin/main coalesce·단일 scoped-sudo·TLS preflight·migrate-lint gate·one-at-a-time+SSE pre-drain·post-cutover soak 자동롤백) + `bin/migrate-lint.sh`(expand/contract AST 게이트, CONVENTIONS §12) + `/livez`·`/readyz`·SSE 카운터(app.py) + :18080 직접 문 폐기(Caddy :443 단일화). 설계+9 적대적 검증(wf_f176026a). **라이브 컷오버 완료**(web-a/web-b, zero-502 검증, health/proxy Host hotfix). (cross-cut: 0002/0003/0006) |
| feature-0015-zd-hygiene-backup | review | 2026-06-30 | [TASK](../unit/feature-0015-zd-hygiene-backup/docs/TASK.md) | 백엔드/DB 무중단 위생(feature-0014 후속, feasibility 분석 wf_1d634d33) — ① insight-worker SIGTERM graceful(`_INSIGHT_SHUTDOWN`+stop_grace 30s) ② MySQL online-DDL 게이트 `bin/mysql-ddl-lint.sh`+CONVENTIONS §13 ③ 백업 갭: 범위 명시+`bin/restore-rehearsal.sh`(throwaway 복원검증)+`bin/install-backup-cron.sh`(매일 백업/주간 리허설). **라이브 실증 완료**(insight graceful 종료·복원 리허설 PG/MySQL PASS). (cross-cut: 0001/0002) |
| feature-0016-metadata-graph | in-progress | 2026-07-07 | [TASK](../unit/feature-0016-metadata-graph/docs/TASK.md) | AGE 메타데이터 지식그래프(관계형 SSOT→`metadata_kb` 투영) + 관리콘솔 그래프 뷰(Cytoscape·fcose 클러스터링·관련도 사이징·이웃 60x 인덱스) + `graph_navigate` AI 도구(컨텍스트 초과 시 서브그래프 탐색). 커스텀 PG16 이미지(pgvector+pg_trgm+AGE) cutover **라이브 완료**(alembic 0025, primary/replica shared_preload+role search_path, 데이터 무손상). per-datasource 투영(rag_objects ~21 ds/8,122 테이블)·scope 격리. cross-cut 코드 거주 0002(metadata_graph/tools/insight)·0003(admin 그래프뷰). 잔여 T5.4 PB-0008 라이브 브라우저 검증·T5.1 eval A/B. · (07-01) 그래프 뷰 대규모 진화 — 렌더러 WebGL 전환(프레임레이트 근본 대응)·암묵(FK 미선언) 관계 추론+자기교정 엔진(alembic 0026, 추정→신뢰/파단)·AI 능동 분석 앵커-상대 관련도 게이팅(ADR-003, alembic 0029)+실시간 진행 패널·ERD 컬럼 ordinal 세로배치(alembic 0027)·메타데이터 탭 권한 5분할(B안, 인가는 feature-0003)·다수 렌더/인터랙션 수정(상세 REPORT 07-01/DECISIONS ADR-002·003). · (07-02) 렌더러 AntV G6 v5(Canvas) 교체(ADR-004, Cytoscape 폐기)·클러스터 다열 masonry+가변폭 shelf-packing·테이블 노드 펼침 논블로킹+더블클릭 프리즈 잔존 근본해소(ADR-005/006)·노드 우클릭 상세 상호작용(컨텍스트 메뉴·관계 패널·중심 보기)·초기 진입 가시성(스키마-우선+줌클램프+미니맵)·스키마 카드 우클릭 메뉴+라벨 badge 압축·검색 시 스키마 카드 badge 매칭·더블클릭 카메라 앵커-중심 애니 팬(ADR-008, 순간이동 재배치 해소)·추정/신뢰 관계 자기교정 미가동 근본수정(config __all__ 누락 NameError 로 07-01 발표 자기교정이 3일 조용히 정지했던 결함, ADR-007)·MSSQL 프로브 오류 130 전면실패 hotfix·관계 분석 전용 claude-haiku 분리(내부 모델 라우팅) — ADR-004~009 feature-local DECISIONS. · (07-03) **분석완료 노드 테이블 역할 시각표식**(node-role-viz, ADR-010) — 역할 8종 고정분류(LLM role 계약+휴리스틱 백필, alembic 0031)·칩 색(Okabe-Ito)+아이콘+범례+상세/진행 패널 역할 칩 (cross-cut: 0002/0003, dep 0013/0014) · (07-03~06) 그래프 뷰 대량 UX 진화 — 관계 추적·자유배치·유사속성 그룹·제품 카테고리·함수/프로시저 노드·의미 임베딩 클러스터링(Phase C)·크로스-ds 관계(Phase B)·z-order 정합·상세 nav/kind 필터/검색 보존 + 전 ds routine backfill·DB(스키마) 단위 AI 능동 분석(라이브 backfill·PB-0008 PASS). · (07-07 §55) 제품 카테고리 밴드(CAT/CATH/CATX 밴드별 shelf-pack·헤더 드래그·접기)+크로스-DB 관계 일반화(xschema 같은 DS 다른 DB, MSSQL 3-part 프로브·관계 수동 큐레이션 trust/break)+DB 단위 분석 재귀 전개(per-seed anchor·예산 cap)·refine-not-override·back-refine(ADR-021, alembic 0038, PB-0008 PASS). 상세·근거는 정본 unit REPORT/DECISIONS(feature-local ADR-010~021) |
| feature-0016-zd-pg-pause-caddy | review | 2026-06-30 | [TASK](../unit/feature-0016-zd-pg-pause-caddy/docs/TASK.md) | 무중단 조건부→가능 승격(feasibility wf_1d634d33) — PG pgbouncer **PAUSE 래퍼** `bin/pg-restart.sh`(PAUSE→PG재시작→RESUME, RW near-zero, RESUME trap 보장) + compose pgbouncer ADMIN_USERS + deploy-web.sh **reconcile_caddy**(Caddyfile 변경 시에만 recreate, inode-stale 대응). **라이브 실증 완료**(PG 재시작 중 RW 무에러·near-zero·큐지연만, reconcile no-op). (cross-cut: 0002 PG/0006 caddy) |
| feature-0017-deploy-build-gate | review | 2026-07-02 | [TASK](../unit/feature-0017-deploy-build-gate/docs/TASK.md) | deploy-web.sh **build+migrate 게이트** snap-docker `docker compose (build\|run)` **metadata-file race false-failure 수정** — build 게이트는 이미지 존재+GIT_COMMIT 라벨 정합 검증(EXIT≠0 은 marker+이미지정합 시만 양성무시), migrate 게이트(CHG-20260702T160000)는 1차 exit≠0 시 backoff 후 멱등 재시도로 head 도달 판정(head-anchored positive evidence, 재시도 실패=ABORT). 진짜 실패는 여전히 ABORT. 이 호스트 web 배포 false-차단 해소. (cross-cut: feature-0014 스파인) |

> **미머지 활성 worktree**: 없음 — 현행 worktree(feature-0002·0003·0009)는 모두 `ahead=0`(작업 main 병합 완료). 미머지 in-flight 작업이 생기면 표 아래 note 로만 표기하고, 병합 시 행을 갱신한다(ADR-0031 §1).
> 상세 TASK 이력을 셀에 누적하지 않는다(ADR-0031 §1) — 상세는 정본 링크의 unit TASK.md / 인덱스화 이전 분은 STATUS_ARCHIVE.md.

### 상태 값 정의
`planned`(요구 정리) · `in-progress`(구현 중) · `blocked`(승인/불명확 차단) · `review`(검토) · `done`(완료) · `deprecated`(폐기)

## 2. 기능 간 의존성 요약
[ARCHITECTURE.md](./ARCHITECTURE.md) §6 정본 참조. 요약:
- feature-0003 → feature-0002
- feature-0004 → feature-0001
- feature-0005 → feature-0001, feature-0002, feature-0004
- feature-0006 → feature-0001
- feature-0008 → feature-0003(검증대상), feature-0004(headless 보조)
- feature-0009 (cross-cut) → 코드 거주 feature-0002(mentions/group_members)·feature-0003(app.py)
- feature-0010 → feature-0003(인증/라우트 인라인), feature-0002(`modules/cred_crypto`)
- feature-0011 (refactor) → feature-0002·feature-0003 공통 코드 `shared/` 추출 (양 feature import 재배선)

## 3. 블로킹 항목
- **SSOT 통합(META-0003) Phase 3** — tracked secret 노출 종료(`.env.secret.bak-task0228` 등)는 **rotation(사용자) 선행** 필요. 근거: ADR-0031 §4 / [DOC_REGISTRY.md](./DOC_REGISTRY.md).
- 그 외: 없음.

## 4. 통합 테스트 현황
- 현재 기준: 구조/기동 검증 (`docker compose config`, `make status/web/browser-up/browser-health`, `GET /api/session`).
- 기능별 테스트 정본: `unit/<feature>/docs/TEST.md`.

## 5. 전체 진행률
- 등록 기능(main `unit/`): 17 (디렉토리 18 — feature-0016 은 metadata-graph + zd-pg-pause-caddy 2 슬라이스, 번호 충돌 — 사람 결정 보류)
- review 5 (feature-0008/0014/0015/0016-zd-pg-pause-caddy/0017) · in-progress 13 · done 0 · blocked 0
- 상세 진척·이력: 각 unit TASK.md / [STATUS_ARCHIVE.md](./archive/STATUS_ARCHIVE.md)
