---
doc_type: WIKI_OVERVIEW
scope: project
status: active
edit_policy: ai-maintained
source_of_truth: false
template_version: v3.13.0
domain: [navigation, wiki, synthesis]
ai_read_priority: 7
wiki_role: article
wiki_name: project
confidence: high
maturity: substantial
ai_generated: true
sources:
  - ../docs/PROJECT.md
  - ../docs/ARCHITECTURE.md
  - ../docs/DECISIONS.md
  - ../docs/STATUS.md
  - ./Index.md
---

# Wiki — Overview (living synthesis)

| 항목 | 값 |
|---|---|
| 분류 | `#wiki/overview` |
| 프로젝트 | MySQL DBA AI Assistant (`mysql_ai_delegated_dev`) |
| 정본 sources | [[../docs/PROJECT\|PROJECT]] · [[../docs/ARCHITECTURE\|ARCHITECTURE]] · [[../docs/DECISIONS\|DECISIONS]] · [[../docs/STATUS\|STATUS]] |
| Wiki layer | mirror (single page synthesis) |

## 목차

1. [개요](#1-개요)
2. [상세](#2-상세)
     - [2.1 핵심 영역](#21-핵심-영역)
     - [2.2 핵심 결정 (ADR)](#22-핵심-결정-adr)
     - [2.3 데이터 흐름](#23-데이터-흐름)
     - [2.4 진행 중인 흐름](#24-진행-중인-흐름)
3. [외부 source 합성](#3-외부-source-합성)
     - [3.1 인용 source](#31-인용-source)
     - [3.2 합성된 결론](#32-합성된-결론)
     - [3.3 미해결 contradiction](#33-미해결-contradiction)
4. [알려진 한계](#4-알려진-한계)
5. [다음 단계](#5-다음-단계)
6. [관련 문서](#6-관련-문서)
7. [둘러보기](#7-둘러보기)
8. [외부 link](#8-외부-link)
- [분류](#분류)

## 1. 개요

본 프로젝트는 **기존 `mysql_ai` 운영 자산을 AI 위임 개발 (`ai_delegated_dev`) 템플릿 구조로 이관한 실행형 사본** 이다. 자연어 입력 → LLM tool-call loop → **N 개 데이터소스 (MySQL·MSSQL)** 에 대한 read-only DBA 작업 자동화를 23 개 feature unit 디렉토리(feature 넘버 0001~0023 — feature-0016 은 metadata-graph + zd-pg-pause-caddy 2 슬라이스라 디렉토리 2개, feature-0018 은 디렉토리 없는 슬라이스로 feature-0003 에 코드 거주) + 단일 docker-compose 로 제공한다. 정책 정본 (`AGENTS.md`) + 도메인 정본 (`docs/`) + 기능 정본 (`unit/<id>/docs/`) 의 3-tier 문서 체계로 다중 AI 가 동시에 작업 가능.

> **2026-06 현재**: 초기 단일 MySQL replica → **멀티 데이터소스** (dialect 추상화 + envelope 암호화 registry + DB-단위 접근) 로 일반화. agent runtime + KB 는 Postgres 단독 정본 (2026-05-27 이관 완료). agent 실행은 ask-worker out-of-process 큐로 cutover.
> **2026-06-19~23**: ① **사용자 보안 보강 6종** (공유 링크 만료·로그인 시도 제한·감사 변조방지·LLM 사용량 한도·프롬프트 인젝션 방지·2단계 인증) 전체 완료 — [[../docs/SECURITY|SECURITY.md]] §7.2·§12~§15. ② **그룹 대화** (feature-0009) — 멤버십·`@assistant` 멘션·열람≠발화 분리·라이브 UX. ③ **NL→SQL 정확도 flywheel** (eval harness·샘플쿼리 few-shot·self-reflection·용어/ENUM 사전) — `docs/improvements/dba-ai-nl2sql/ROADMAP.md`.
> **2026-06-24**: ④ **관리 콘솔 메타데이터 거버넌스** (용어·ENUM·테이블/컬럼 설명·AI 자동완성, ITEM-11) 로 NL→SQL 컨텍스트 강화. ⑤ **feature-0010 Google Drive 연동 토대** — 계정별 OAuth 토큰 암호화 저장 + MCP 구성 seam (연동 미수행·비활성 scaffold). ⑥ **feature-0011 `shared/` 공통 코드 추출** (P5a — `model_catalog`·`config`·`db` 모듈 alias, `make test` 회귀 0).
> **2026-06-25**: ⑦ **그룹 대화 라이브 UX 확장** (feature-0009) — 사이드바 안 읽음/@멘션 배지(read cursor)·메시지 좌우 정렬·owner 멤버 추방/차단/해제·참가자 per-message 제품 선택·처리 중 composer 비잠금/1:1 인터럽트 재요청. ⑧ **관리 콘솔 프롬프트 자동화** (feature-0003) — 역할 '전체 제품 프롬프트'·프로필 '제품별 프롬프트' AI 자동 작성·제품 분석률 95% 시 제품프롬프트 자동완성·규칙 자동추가 DB insight 커버리지 UI·'지식베이스' 메뉴 재편. ⑨ **feature-0011 `shared/` 추출 P5a Step5 완료** — config·db·conn_health·datasources 소비처 마이그레이션 + alias shim 4종 전량 제거(회귀 0). ⑩ **안정성** — init "준비" 임베딩 지연 회귀 해소·요청량 한도 메시지 주체(서비스/계정) 구분·그룹 동시 처리 고착/입력 블로킹 해소·datasource 회로차단 안내 문구 명확화.
> **2026-06-26**: ⑪ **제품 선택 chip 처리 중 항상 활성화** (feature-0003) — composer 제품 선택 chip 을 "요청 처리 중" 에도 항상 활성·사용 가능하게(TASK-0047 turn-immutability 의 3계층 가드 — 프론트 시각 disable·프론트 reject·백엔드 PATCH 409 — 일괄 완화). 제품은 `/api/ask` enqueue 시 캡처되어 in-flight 답변은 비오염, 변경은 다음 요청부터 반영. RBAC/스키마/엔드포인트 무변경(timing 가드만 제거). ADR-WEB-0006. ⑫ **assistant 요청 2번 중복 처리 차단** (feature-0003/0002) — 워커모드 `/api/ask` 의 long-poll 연결이 web 재배포로 끊겨 사용자가 재전송하면 동일 페이로드 ask_job 2개 → 요청·답변 2회 처리되던 결함을 enqueue 멱등화(dedup NOT EXISTS + 활성 중복 시 기존 run attach) + app.js status 복구 재시도로 차단. 배포 검증 중 적발된 PG AmbiguousParameter 회귀(워커모드 신규 `/api/ask` 500)는 dedup 전용 파라미터+alias 격리로 해소.
> **2026-06-29**: ⑬ **답변 피드백 답변당 고유화** (feature-0003/0002) — 답변당 사용자별 고유 👍/👎 1개 강제 (마이그 0021/0022 + id_space 보강), 새로고침·대화 전환 후 중복 부여 차단. ⑭ **용어사전 대화 자율등록 + 역할 분리 + 유사어 참조** (feature-0002/0003, 관리 콘솔, 마이그 0023, ADR-20260629T101500) — 대화에서 용어를 자율 등록하고 등록·검토 역할을 분리하며 유사어를 참조. ⑮ **용어 검토 큐 IA 중첩** (admin) — 용어 검토 큐를 용어사전 하위 2차 보기 탭으로 중첩. ⑯ **첨부 wrong-bubble 엣지 하드닝** (feature-0003) — 첨부 영속 레이어 매칭 키에 `message_id_space` 추가 (정상 display 경로 동작 동일, fork/마이그 cross-space 엣지 하드닝). ⑰ **feature-0012 web-router-modularization 토대** — feature-0003 `app.py` 도메인별 `APIRouter` 점진 분할의 route-parity 안전망 + 의존성 audit (P5b, behavior-neutral 리팩터 토대). ⑱ **feature-0013 관계 다이어그램 (신규)** — assistant 가 flow/관계/구조 질문에 **mermaid 다이어그램**(ER·flowchart)으로 답하고, `table_relationships` 관계 저장소(FK introspection·대화 JOIN 학습, alembic 0024)로 관계를 지속 학습 (cross-cut: feature-0002 발화·저장소 / feature-0003 웹 렌더, PB-0008 라이브 PASS·배포 완료). ⑲ **메타데이터·공유 대화 화면 정리** (feature-0003) — 스키마 골격 결과 패널 접기·검색·페이지네이션·여백 압축(metadata-bs-collapse/flexclip/paging), 공유 대화 뷰 mermaid 렌더·전체폭 반응형·스크롤 가이드 뱃지(share-mermaid-responsive·point-scroll), 용어사전 역할 선택 UI 단일화·역할 미표시 수정(glossary-role-single-ui/fieldname-fix), 새 대화 사이드바 중복 제거(new-conv-dedup), diff 답변 누출 줄번호 정규화(diff-lineno-leak).
> **2026-06-30**: ⑳ **feature-0016 메타데이터 지식그래프 (신규, 대형)** — 관리콘솔 메타데이터(테이블·컬럼 설명)를 평면 나열에서 **탐색 가능한 지식그래프**로 승급. 관계형 테이블을 SSOT 로 두고 Apache AGE(PostgreSQL openCypher 확장)의 `metadata_kb` 그래프를 **재생성 가능한 투영**으로 동기화해, 관리콘솔 **그래프 뷰**(Cytoscape·fcose 카테고리 클러스터링·관련도 사이징·이웃조회 60x 인덱스)·검색·AI(`graph_navigate` tool, 8K 테이블 컨텍스트 초과 해소)가 같은 그래프를 공유. 커스텀 PG16 이미지(pgvector+pg_trgm+AGE 공존, alembic 0025) **운영 cutover 라이브 완료**(데이터 무손상, 무중단 롤링). per-datasource 투영(rag_objects ~21 ds·8,122 테이블)+scope 격리. cross-cut 코드 거주 feature-0002(코어·tool·insight)·0003(admin 그래프뷰). [[Features/feature-0016-metadata-graph]]. (※ feature-0016 번호는 metadata-graph 와 zd-pg-pause-caddy 두 슬라이스가 공유 — 사람 결정 보류.) ㉑ **메타데이터 관리 화면 정리** (feature-0003, frontend-only) — 스키마 설명 패널 list-detail 2단 재구성·데이터소스 선택 단일화(헤더 스코프 상속)·테이블 설명 인라인 입력(평면화·정렬)·스키마 가져오기 시 기존 설명 prefill+변경분만 저장. ㉒ **무중단 배포·운영 위생군** (feature-0014/0015/0016-zd/0017) — web 무중단 롤링 배포(Caddy LB web-a/web-b·자동 롤백·:18080 폐기→:443 단일)·insight-worker graceful 종료+MySQL online-DDL 게이트+백업 복원 리허설 cron·PG 재시작 무중단화(pgbouncer PAUSE 래퍼)·배포 빌드게이트 false-failure 수정. 라이브 컷오버/실증 완료. ㉓ **질문 의도 이해·끈기 개선** (feature-0002) — 능동 해석 지침을 1:1·그룹 모두에 주입(과도 재질문·스키마 추측 후 give-up·datasource 드리프트 억제)+식별자 대소문자 보존.
> **2026-07-01**: ㉔ **그래프 뷰 대규모 진화** (feature-0016) — 렌더러 canvas→**WebGL** 전환(대규모 스키마 프레임레이트 근본 대응)·**암묵(FK 미선언) 관계 추론+자기교정 엔진**(이름·구조 휴리스틱 추정 엣지=점선 → 대화 JOIN 관찰·프로브로 신뢰=실선 승격/파단=숨김, alembic 0026, ADR-002)·**AI 능동 분석**(앵커-상대 관련도 게이팅 ADR-003·alembic 0029 + 실시간 진행 패널)·ERD 컬럼 ordinal 세로배치(alembic 0027)·다수 그래프 UX/렌더 수정. ㉕ **메타데이터 탭 권한 5분할** (feature-0003, B안·Critical) — 단일 `kb.ingest.manual` 우산 권한을 `metadata.{glossary,enum,table,column}.manage`+`graph.read` 로 세분(담당자별 개별 위임, 비파괴·가역·마이그 0). ㉖ **feature-0012 라우터 모듈화 완료** — web `app.py` 148 route 핸들러 전량을 21개 도메인 `APIRouter` 로 byte-동치 추출(app.py ~29K→18,917줄, behavior-neutral, batch1-3 라이브 배포). ㉗ **좌측 대화 전환 방어** (feature-0003) — 대화 선택 시 대화창 미표시 방어 하드닝(convswitch opacity). [[Features/feature-0016-metadata-graph]] · [[Features/feature-0012-web-router-modularization]].
> **2026-07-02**: ㉘ **그래프 뷰 후속 진화** (feature-0016) — 렌더링 엔진 **Cytoscape(WebGL)→AntV G6 v5(Canvas) 전면 교체**(ADR-004, 07-01 WebGL 전환을 대체하는 대형 기반 교체)+클러스터 다열 masonry/shelf-packing·**노드/스키마카드 우클릭 상세 상호작용**(kind별 컨텍스트 메뉴·관계 상세 패널 방향/신뢰·추정 w/근거/조인컬럼·중심 보기 지속 칩)·**초기 진입 가시성**(스키마-우선+줌클램프+미니맵)·검색 스키마 카드 badge 매칭·노드 펼침 논블로킹(ADR-005)·프리즈 잔존 해소(setData rebuild, ADR-006)·더블클릭 카메라 앵커-중심 애니 팬(ADR-008)·**추정/신뢰 관계 자기교정 파이프라인 미가동 근본수정**(config `__all__` 누락 NameError 로 insight 처리가 3일 조용히 정지했던 결함 포함 4중 원인 해소, ADR-007)·그래프 분석 전용 모델 claude-haiku 분리. ㉙ **AI 운영 관제 패널** (feature-0003, 신규) — `/api/admin/ai-ops` AI 운영 현황(관제) admin 화면 + LLM 계측 확장(main agent latency·최근 활동 cursor 페이징)·감사 화면 정리(카테고리 순서·툴팁·최근활동 상세 확장)·메타데이터(지식베이스) 권한 종속관계 그룹 게이트 계층화·최근활동 sentinel 대화 링크·첨부 개수 배지 stale 수정. [[Features/feature-0016-metadata-graph]] · [[Features/feature-0003-agent-web-ui]].
> **2026-07-03**: ㉚ **그래프 뷰 진화 2차** (feature-0016) — 관계 기반 배치(스키마 seriation·군집·barycenter, ADR-012)·유사 속성 그룹 영역화(affix family 휴리스틱+배경박스, ADR-013)·**제품(Products) 단위 카테고리 개요**(질의시점 MySQL SSOT 합성·AGE 미저장·마이그 0, ADR-014)·**자유 배치 persistence**(결정론 배치 위 드래그 offset 레이어, ADR-015)·**AI 분석 완료 노드 역할 시각 표식**(8종·Okabe-Ito 색·아이콘·범례, node-role-viz ADR-010, alembic 0031)·접힌 상태 관계 표시·상세 관계 컬럼 아코디언·중간버튼 카메라 팬+종속 드래그·더블클릭 팬 지연 제거(ADR-011)·운영현황 LLM target 관측(alembic 0032). ㉛ **데이터소스 평균 연결 응답 시간 + AI 운영 현황 지연 지표 재정의** (feature-0003) — 데이터소스 상세에 최근 N회 평균 연결 응답 시간(ds-avg-latency, conn_health 이동평균 재사용·추가 probe 0, PB-0008 PASS)·AI 운영 현황 지연(p50/p95)을 호출 왕복→단계 간 간격(step_gap_ms)으로 재정의(aiops-ttft, alembic 0033). ㉜ **공유 링크 참여 알림** (feature-0009) — 공유 링크로 새 멤버 참여 시 대화 내 '참여 알림' pill + 기존 멤버 unread(가입자 제외, LLM 히스토리 배제, 마이그 0). ㉝ **insight 안정성·부하 분산** (feature-0002/0007) — 동일구조 샤드 그룹화(대표 1회 LLM+형제 LLM-free 전파)·healthcheck false-negative 해소·probe 격리/scan skip/batched graph sync(TASK-0308)·insight LLM 요청-레벨 fallback(claude-corp→root→edge). [[Features/feature-0016-metadata-graph]] · [[Features/feature-0003-agent-web-ui]] · [[Features/feature-0009-group-conversation]].
> **2026-07-04**: ㉞ **그래프 뷰 대폭 확장** (feature-0016) — 의미 임베딩 클러스터링(bge-m3·kNN+union-find, Phase C·ADR-018·alembic 0035)·**크로스-데이터소스 관계**(시그니처 임베딩 후보+신뢰 게이팅, Phase B·ADR-019·alembic 0036·마젠타 점선)·카테고리 그룹(sim-group) 드래그/접기/리사이즈(ADR-020)·그래프 UX 7건(상세 nav·관계 단/더블·범례 3탭·중복분석 방어·ds 라벨)·z-order 의미 정합(`_METZ` bake, FUNCTION §13)·관계도 최상위 탭 분리+검색 부드러운 하이라이트. ㉟ **멤버 가시성 window 공유** (feature-0009, Critical) — '여기부터/여기까지'로 공유가 `[from,to]` window 만 노출하고 가려진 구간을 참여자 뷰·LLM recall·fork 전부에서 물리 배제(SECURITY §21/§21.4, alembic 0037, additive). ㊱ **말풍선 ☰ 메뉴 통합** (feature-0003) — 말풍선 액션(샘플 등록·분기·공유·'AI 로 고치기')을 kebab ☰ 로 통합(👍/👎만 외부). ㊲ **용도별 LLM 라우팅 분리** (feature-0007) — insight 주말/야간 gemma 고착 해소(대화·능동분석=항상 claude / 배치 insight=시각 기반, refresh/keepalive cron 24/7). [[Features/feature-0016-metadata-graph]] · [[Features/feature-0009-group-conversation]].
> **2026-07-06**: ㊳ **대화 화면 추론 강도 선택** (feature-0003) — composer '+' 메뉴 "추론 강도" 4단계(낮음/일반/높음/매우 높음)·대화별 영구 저장·요청 단위 thinking budget override(일반=alias 기본), reasoning-effort Major·PB-0008 PASS. ㊴ **함수·프로시저 노드 + DB 단위 AI 능동 분석** (feature-0016) — `routine_objects` SSOT+AGE `Routine` 노드+정의 파싱 참조 엣지(alembic 0034)·전 ds routine backfill·DB(스키마) 단위 'AI 능동 분석'(재귀 0 보장·비용 가드, FUNCTION §15)·그래프 상세 nav/kind 필터/검색 보존/파라미터 수직(FUNCTION §16, graph-navfilter). [[Features/feature-0003-agent-web-ui]] · [[Features/feature-0016-metadata-graph]].
> **2026-07-07**: ㊵ **런타임 설정 콘솔** (feature-0018, 신규 슬라이스 — 코드 거주 feature-0003/0002) — 관리 콘솔 시스템>설정에서 실행 타임아웃·모델별 추론 예산 조정·저장·live/restart 하이브리드 반영(`WebRuntimeSettings`·`admin_settings` 라우터·`system.runtime.read/write` RBAC+audit·`shared/runtime_settings.py` resolver, env-fallback). runtime-settings Major·PB-0008 PASS. **추론 강도별 예산**(낮음/높음/매우 높음, `reasoning_budget` low/high/max·'일반'=no-override) + pane UI 재설계(정렬 grid+commit-bar) 후속(d9516aee·a2fe4103). ㊶ **제품 카테고리 밴드 + 크로스-DB 관계 일반화** (feature-0016 §55) — 관계도 제품 카테고리 밴드(CAT/CATH/CATX)·크로스-DB 관계 일반화(xschema)·관계 수동 큐레이션(trust/break)·DB 단위 분석 재귀 전개·refine-not-override·back-refine(ADR-021, alembic 0038, PB-0008 PASS). **§56 후속**(ADR-022~023, 마이그 0) — 크로스-DB 루틴 참조 sync 근본수정(SAVEPOINT 행 격리·워터마크 게이트·ROUTINE_USES 채택·backfill/MSSQL label 정규화·케이스변형 멱등 회수, RC1~5)+§55 화살표 데이터흐름/능동분석 툴팁 정합, POST-DEPLOY e2e(크로스 1,041·case_purged 6,320·워터마크 전진). ㊷ **대화 답변 안정성** (feature-0002) — 대화 답변 경로 edge(gemma) 폴백 완전 차단(맥락 손실 해소, conv-audit FR-edge-fallback). ㊸ **지식베이스 채택 인박스 + ENUM 대화 자율수집 + 콘솔 IA 통합** (feature-0002/0003) — 대화 자율수집(용어+ENUM)을 통합 '채택 인박스'로 재구성(용어사전 0021/0023 대칭 ENUM 코드사전 신설·`kb.enum.curate`·alembic 0039·신뢰도/상태별 채택·거부·되돌리기+pending 배지) + 콘솔 IA 통합(채택 인박스·샘플 검수 최상위 탭→각 사전 하위 {목록/검토 큐} 2차 보기·5서브뷰 디자인 폴리시, UI 단독). [[Features/feature-0016-metadata-graph]] · [[Features/feature-0003-agent-web-ui]] · [[Features/feature-0002-agent-core]].
> **2026-07-08**: ㊹ **그래프 뷰 접힘 카드 연결선·상대 하이라이트·크로스 구분·LOD + 분석 기반 제품 분류 제안** (feature-0016 §57~59) — 관계도 스키마 카드 접힘 상태에서도 **연결선**(SCHEMA_REF 질의시점 1-hop 집계·렌더 3단 승격 컬럼→테이블→카드)·선택 노드 **상대 하이라이트**(1-hop 선명·나머지 dim)·크로스-DB ROUTINE_USES **마젠타** 색 구분·**중간 줌 LOD**(엣지 스파게티 축약, ADR-024)·스키마 골격 가져오기 MSSQL 라벨 케이스 정합(§58)·**분석 기반 제품 분류 'AI 제안→사람 승인'**(카테고리 밴드 매핑을 이름 규칙→분석 신호로 개선하되 접근 allowlist 자동기록 금지 위해 Pending-only 스테이징·환각 3중 게이트·데몬 기본 OFF, ADR-025 §59). 전건 POST-DEPLOY 라이브 실증. ㊺ **메타데이터 콘솔 UX·폴리시 + 제품 분류 승인 UI** (feature-0003) — 검토/검수 큐 행 클릭→우측 read-only 상세(선택 불가 해소)·ENUM "+코드 추가" pre-fill·샘플 검수 큐 mermaid 렌더·목록 가독성 + 디자인 폴리시 5건(필 위계·nesting·배지 accent) + 제품 관리 "✨ AI 분류 제안" 승인/거부 UI. [[Features/feature-0016-metadata-graph]] · [[Features/feature-0003-agent-web-ui]] · [[Features/feature-0002-agent-core]].
> **2026-07-09~10**: ㊻ **그래프 뷰 대규모 성능·UX 진화 (§57.4~76)** (feature-0016) — 상대 하이라이트 신뢰성 완결(즉시·정확 점등·오-침강/dim 고착·유령 관계선 잔상 해소, §57.4~9·§64·§66, ADR-026~028)·대규모 성능·정리(스키마 펼침 세로폭주 해소 ADR-028·컬럼/뷰포트 컬링 ADR-029/032+컬링 노드 참조/상호작용 보존 ADR-037·배치정렬 위상서명 메모이즈 ADR-035·미니맵 전체이미지 재사용 ADR-036·극단 줌아웃 집계 카드는 §67 폐기 ADR-033)·상세 패널 사용관계 read/write 분리+관계행/미렌더 컬럼 카메라 이동+컬럼 선택(§68~72/§75)·상단 툴바 3존 통합+줌/상태 플로팅 오버레이·엣지 중간(휠)버튼 팬(§62)·AI 능동 분석 caveats 계약 재설계(§69/ADR-034 — 형식적 자기-불평 제거·실위험만; **T69.5 완수 07-13 PR #744·cc_data_main 715/715**). ㊼ **응답 지연 타임아웃 복구 모달 제거 + 추론 예산 상한 확대** (feature-0003/0018) — 작업 화면에서 화면 전체를 덮던 타임아웃 복구 모달 제거·모달/토스트 없는 조용한 자동 재연결(배포 4b6919ec·PB-0008 PASS) + (07-09) 관리 콘솔 모델별 추론 예산 상한 native 확대(Sonnet 128K·Haiku 64K)+추론↔본문 비율 슬라이더(feature-0018 코드 거주). ㊽ **MSSQL 인증 실패 순회 조기 skip + datasource cooldown** (feature-0002 §12.3) — insight 순회에서 MSSQL 로그인 실패(18456)를 조기 skip + datasource cooldown(기본 600s)으로 실패 로그인 반복·로그·I/O 억제(회복력; DB/객체별 권한거부는 로그인 성공이라 순회 계속, 마이그·경계 0). [[Features/feature-0016-metadata-graph]] · [[Features/feature-0003-agent-web-ui]] · [[Features/feature-0002-agent-core]].
> **2026-07-12**: ㊾ **web 라우터 모듈화 완결** (feature-0012, behavior-neutral 내부 리팩터) — feature-0003 `app.py` 모놀리스(~29K/148 route)를 **21개 도메인 `APIRouter` 로 byte-동치 전량 추출**(app.py→18,917줄, 잔여 `@app` 0) + ITEM-10(`web_context` 헬퍼 추출·모듈분리 -81%) + ITEM-11(잔여 인라인 authn DEFER 핸들러 실leak 13 DI-rework·keep-inline 정당 37 명시분류) 완료(라이브 4c203f9c, route-parity 골든 불변·프로덕션 응답 실측 동일). 브라우저 로그인 QA 사용자 사인오프 이관. 잔여 initiative ITEM-09(그래프 CSS/JS 세분화·외부 브랜치 blocked). [[Features/feature-0012-web-router-modularization]] · [[Features/feature-0003-agent-web-ui]].
> **2026-07-13**: ㊿ **그래프 렌더러 PixiJS v8 전면 교체 + 콘텐츠 밴드 + 메시지 편집 신규** — feature-0016 그래프 렌더 엔진을 노드 다수 팬(카메라 이동) 버벅임 근본 해소를 위해 **AntV G6 v5(Canvas)→PixiJS v8(WebGL) 전면 교체**(엔진-중립 SceneAdapter seam·GPU 상주 씬·G6 폴백 토글, §78)+미니맵 클램프/드래그·scene diff 오브젝트 풀(§79)·라벨 Text→BitmapText(§80·렌더 157ms→0.03ms)·상세 패널 하위 항목 hover 시각 효과(§81) — 대형 스키마(409 객체) 팬 60fps vsync 라이브 PB-0008 PASS. 카테고리 밴드 **'컨텐츠 단위' 그룹핑 실동작화**(mig 0040·DB단위 클러스터·함수/프로시저 합동·LLM 라벨·mutual-kNN)+p2(가짜 밴드 소멸·연관 밴드 인접). feature-0003 — 첨부 **사용자 재업로드 버전 관리**(해시 대조 체인·assistant diff 인지)·작업화면 데이터소스 **'연결 테스트' 버튼**·**그래프 뷰 권한 분리**(`metadata.graph.read` 를 '메타데이터 관리' 묶음에서 독립, Critical). feature-0002 — **describe_routine 도구**(저장 프로시저/함수 정의 조회)·**sql_guard read-only shape 과차단 보정**(최상위 UNION·읽기전용 SHOW 허용). **feature-0019 메시지 편집 (신규)** — 사용자가 보낸 메시지 수정(1:1=단순/요청 분기 재답변 `< n/m >`·공유=단순만), Phase 1 대화 내부 브랜치 트리 백엔드 기반(마이그 0041). [[Features/feature-0016-metadata-graph]] · [[Features/feature-0003-agent-web-ui]] · [[Features/feature-0002-agent-core]] · [[Features/feature-0019-message-editing]].
> **2026-07-14**: (51) **메시지 편집 Phase 1+2 완성·라이브 + 무중단 배포 커버리지 + 그래프/작업화면 UX + 답변 정확도** — **메시지 편집**(feature-0019) 사용자가 보낸 메시지 수정 완성·라이브(1:1=단순 수정 / 요청사항 수정 시 브랜치 재답변 `< n/m >` 페이징, 공유·그룹=단순 수정만·@assistant 호출 메시지 잠금; Phase 1+2 머지·마이그 0041·PB-0008). **feature-0020 무중단 배포 커버리지 완성**(내부) — deploy 스파인이 워커(insight/ask) 자동 롤아웃·bedrock-gateway surge replica 무중단 교체·caddy/alembic stale-image 가드까지 포괄. **그래프 뷰 UX**(feature-0003) — 첫 입장 조작 도움말 팝업·제품 카테고리 밴드 우클릭 메뉴·'AI 능동 분석 실행' 권한 분리(신규 하위 권한 `metadata.graph.analyze` 를 조회 `graph.read` 에서 독립, Critical §12.3). **작업 화면**(feature-0003) — 애니메이션 효과 on/off 설정·프로필 '계정' 탭 세분화(계정/알림/UI/사용 내역)·펼친 '결과 보기' 스크롤 보존. **답변 정확도**(feature-0002) — MySQL 시스템 변수(@@) 읽기 과차단 해소·첨부↔실DB grounding 모순·대소문자 false-missing 봉인·MSSQL cross-DB 발견(검색·describe)·첨부 갱신 새 버전 전달. [[Features/feature-0019-message-editing]] · [[Features/feature-0020-zd-deploy-all]] · [[Features/feature-0003-agent-web-ui]] · [[Features/feature-0002-agent-core]].
> **2026-07-15**: (52) **assistant 자가 적대(red-team) 리뷰 (feature-0021, 신규·Major) + 그래프 상세·우클릭·엣지 정합 + 권한 원자화 + ENUM 묶음 큐 + 답변 정확도** — **feature-0021 (신규)**: 답변을 전달하기 전 별도 fresh-context 리뷰어가 grounding·SQL·권한·완전성·정직성 5축으로 자가 적대(red-team) 검증(BLOCK 만 수정 유발·높음+ 재검증·전 경로 fail-open) + [세션,제품] 메모리 노트(`/shared/agent-notes` TTL) + 관리 콘솔 'AI 추론' 탭(`console.reasoning.read`), Claude Code find→verify·auto-memory·progressive disclosure 이식(alembic 0042, unit DECISIONS ADR-20260715T140000~2). **그래프 뷰**(feature-0003) — 클러스터 상세에 함수·프로시저 컨텐츠 카테고리 포함·전체 출력·카테고리별 접기(collapsible)·우클릭 3대상(스키마↔제품카테고리↔sim-group) hit-test/band-wins 정합·드래그 관계선 추종+per-frame 최적화. **권한**(feature-0003) — 권한 '접근' 카테고리 계층 재구성 + 최소 단위 원자화(추가/수정/삭제 분리)·레거시 묶음 grid 숨김(Critical). **ENUM**(feature-0003) — 코드사전 검토 큐 구조 묶음 승인 체크리스트+일괄 등록. **답변 정확도**(feature-0002) — 첨부↔실DB 커버리지 결정론 봉인(check_table_coverage)·스키마명 대소문자 drift 0행 봉인·model alias 누출 Bedrock 400 봉인·LLM 헬스 probe 오탐/throttle 수정. [[Features/feature-0021-redteam-review]] · [[Features/feature-0003-agent-web-ui]] · [[Features/feature-0002-agent-core]].
> **2026-07-21**: (53) **assistant PG 자율 작업공간 (feature-0022, 신규·Major) + 진행상황 실시간 전파 (feature-0003)** — **feature-0022 (신규)**: assistant 가 전용 PG DB `agent_scratch`(전용 role NOSUPERUSER·CONNECT 격리·대화별 스키마 `s_<hash>`)에서 외부 데이터소스 데이터를 governed 반입(execute_sql 신뢰경계 재사용)해 **cross-source JOIN·집계**, 도구 4종(scratch_import/sql/list/reset)·scratch_guard allowlist(파괴적 쓰기는 격리된 scratch DB 로만 한정·함수/뷰/pg_ 거부)·시간기반 TTL reaper(기본 24h) — 2026-07-21 라이브 활성(bootstrap+`AGENT_SCRATCH_ENABLED=1`·스모크 PASS; 기본값 OFF 게이트; 잔여=cross-source JOIN e2e 실증·관측 UI·대화별 role 승격 TASK-0011~13; feature-local ADR-SCRATCH-0001~0004). **진행상황 실시간 전파**(feature-0003) — 그룹/모니터링 대화를 열어둔 유휴 관찰자에게 타 사용자 assistant 진행상황·답변이 재로드·전환 없이 실시간 표시(frontend-only run-감지·백엔드 무변경·PB-0008 라이브). [[Features/feature-0022-agent-scratch-workspace]] · [[Features/feature-0003-agent-web-ui]].
> **2026-07-22**: (54) **외부 AI용 Conversation API 접근 (feature-0023, 신규·Critical)** — 외부 AI 가 세션 쿠키 없이 **Bearer API 토큰**으로 작업 화면 대화(`/api/ask` 등)를 호출하고, 그 대화를 **MCP 서버**로 tool 화(tool 4종). 토큰은 해시 저장·scope allowlist(`conversation.*`+`product.access.*`) ∩ 계정권한 · `*.any`/관리 네임스페이스 **절대 denylist**(scope 무관 → 관리 콘솔 원천 차단) · 저권한 서비스 계정 귀속으로 심층방어, 발급/폐기는 콘솔 밖 CLI(`bin/api-token-issue.sh`, web-a/web-b 자동감지). 2026-07-22 배포·라이브 e2e 통과(토큰→/api/ask 200·admin 403·무토큰 401·배포 66a48870 soak PASS)·단위 17 PASS·§18.8 적대 보안 리뷰(REV-20260722-0002 HIGH-1/2 수정). 코드 거주 feature-0003(web 인증·라우터)·feature-0002(agent_core ask), MCP 서버=feature-0023 unit. [[Features/feature-0023-conversation-api-access]] · [[Features/feature-0003-agent-web-ui]] · [[Features/feature-0002-agent-core]].

## 2. 상세

### 2.1 핵심 영역

| Feature | 책임 | 카드 |
|---|---|---|
| feature-0001-platform-runtime | MySQL 8.0 / DAB 설정, SQL 유틸리티, replica 연결 정책, redo log 1 GiB | [[Features/feature-0001-platform-runtime\|카드]] |
| feature-0002-agent-core | agent core / 멀티 데이터소스(MySQL·MSSQL) / dialect / Postgres KB / insight worker | [[Features/feature-0002-agent-core\|카드]] |
| feature-0003-agent-web-ui | FastAPI Web UI + 관리콘솔(데이터소스·대시보드·LLM사용량) + audit + 첨부 + ask-worker | [[Features/feature-0003-agent-web-ui\|카드]] |
| feature-0004-browser-automation | Playwright 기반 browser 자동화 service | [[Features/feature-0004-browser-automation\|카드]] |
| feature-0005-qa-mcp | MCP test + QA script | [[Features/feature-0005-qa-mcp\|카드]] |
| feature-0006-lan-proxy-access | Caddy TLS + Windows LAN proxy + `X-Forwarded-For` trust 정책 | [[Features/feature-0006-lan-proxy-access\|카드]] |
| feature-0007-bedrock-llm-provider | AWS Bedrock (Claude) gateway + per-user OpenAI key 폐기 | [[Features/feature-0007-bedrock-llm-provider\|카드]] |
| feature-0008-windows-browser-testing | 실제 Windows 브라우저 AI 자동 검증 (PB-0008 · ADR-0029) | [[Features/feature-0008-windows-browser-testing\|카드]] |
| feature-0009-group-conversation | 그룹 대화 — 멤버십·`@assistant` 멘션·열람≠발화 분리·라이브 UX | [[Features/feature-0009-group-conversation\|카드]] |
| feature-0010-google-drive-integration | 계정별 Google Drive 연동 토대 — OAuth 토큰 암호화 + MCP 구성 seam (비활성 scaffold) | [[Features/feature-0010-google-drive-integration\|카드]] |
| feature-0011-shared-extraction | 공통 코드 `shared/` 추출 리팩터 (model_catalog·config·db·conn_health·datasources) | [[Features/feature-0011-shared-extraction\|카드]] |
| feature-0012-web-router-modularization | feature-0003 `app.py` 도메인별 `APIRouter` 점진 분할 토대 (P5b — route-parity 안전망 + 의존성 audit, behavior-neutral) | [[Features/feature-0012-web-router-modularization\|카드]] |
| feature-0013-relationship-diagrams | flow/관계 질문에 mermaid 다이어그램 답변 + `table_relationships` 관계 저장소 (FK introspection·대화 JOIN 학습) | [[Features/feature-0013-relationship-diagrams\|카드]] |
| feature-0014-zero-downtime-deploy | web 무중단 롤링 배포 — Caddy LB(web-a/web-b) 뒤 2-replica 한 번에 하나씩 재시작 + 배포 스파인 `bin/deploy-web.sh`(자동 롤백·:18080 폐기→:443 단일) | [[Features/feature-0014-zero-downtime-deploy\|카드]] |
| feature-0015-zd-hygiene-backup | 백엔드/DB 무중단 위생 — insight-worker graceful 종료 + MySQL online-DDL 게이트 + 백업·복원 리허설 cron | [[Features/feature-0015-zd-hygiene-backup\|카드]] |
| feature-0016-metadata-graph | 메타데이터 지식그래프 — 관계형 SSOT→AGE `metadata_kb` 투영 + 관리콘솔 그래프 뷰(검색·이웃) + `graph_navigate` AI 도구 | [[Features/feature-0016-metadata-graph\|카드]] |
| feature-0016-zd-pg-pause-caddy | PG 재시작 무중단화 — pgbouncer PAUSE 래퍼(`pg-restart.sh`) + deploy-web.sh Caddyfile reconcile | [[Features/feature-0016-zd-pg-pause-caddy\|카드]] |
| feature-0017-deploy-build-gate | 배포 스파인 빌드 게이트 false-failure 수정 — 이미지 정합 검증(snap-docker metadata-race) | [[Features/feature-0017-deploy-build-gate\|카드]] |
| feature-0019-message-editing | 메시지 편집 — 1:1 대화 내부 브랜치 트리(단순 수정 / 요청 수정 분기 재답변 `< n/m >`) + 공유(그룹) 단순 수정(@assistant 잠금) · Phase 1+2 라이브 | [[Features/feature-0019-message-editing\|카드]] |
| feature-0020-zd-deploy-all | 무중단 배포 커버리지 — deploy 스파인(`bin/deploy-web.sh`) 확장: 워커(insight/ask) 자동 롤아웃 + bedrock-gateway surge replica 무중단 교체 + caddy/alembic stale-image 가드 | [[Features/feature-0020-zd-deploy-all\|카드]] |
| feature-0021-redteam-review | assistant 답변 자가 적대(red-team) 리뷰 — 답변 전달 전 fresh-context 5축 검증(grounding/SQL/권한/완전성/정직성·강도 게이팅·fail-open) + [세션,제품] 메모리 노트(TTL) + 관리 콘솔 'AI 추론' 탭 (코드 거주 0002/0003/shared) | [[Features/feature-0021-redteam-review\|카드]] |
| feature-0022-agent-scratch-workspace | assistant PG 자율 작업공간 — 전용 DB `agent_scratch`(대화별 격리 스키마)에서 외부 데이터소스 반입·cross-source JOIN·TTL(기본 24h) + scratch_guard allowlist (2026-07-21 라이브 활성·기본값 OFF 게이트·코드 거주 0002/shared) | [[Features/feature-0022-agent-scratch-workspace\|카드]] |
| feature-0023-conversation-api-access | 외부 AI용 Conversation API — 세션 쿠키 없이 **Bearer 토큰**으로 대화 API(`/api/ask`) 호출 + 대화를 tool 화하는 MCP 서버(tool 4종) · scope allowlist ∩ 계정권한 · 관리 네임스페이스 절대 denylist(→ 관리 콘솔 차단) (2026-07-22 배포·라이브 e2e 통과·코드 거주 0003/0002) | [[Features/feature-0023-conversation-api-access\|카드]] |

### 2.2 핵심 결정 (ADR)

23-feature 위에 다음 결정이 누적되어 현재 시스템을 형성한다:

- **ADR-0019** ([[Decisions/ADR-0019-web-audit-events|mirror]]) — `WebAuditEvents` 단일 테이블 + `record_audit_event` dispatcher + 16 endpoint hook + 4 RBAC 권한
- **ADR-0021** ([[Decisions/ADR-0021-kb-postgres-rbac|mirror]]) — KB Postgres 분리 + `agent_kb_rw` / `agent_kb_ro` 2-layer RBAC
- **ADR-0024** ([[Decisions/ADR-0024-postgres-database-isolation|mirror]]) — 단일 Postgres cluster + 별 database (`agent_kb` / `agent_drag`)
- **ADR-0025** ([[Decisions/ADR-0025-m5-cleanup|mirror]]) — M5 cleanup 14-day window + Stage A/B/C boundary
- **ADR-0026** ([[Decisions/ADR-0026-bedrock-llm-provider|mirror]]) — per-user OpenAI key → service-managed AWS Bedrock (Seoul region)
- **ADR-0027** ([[Decisions/ADR-0027-agent-runtime-pg-schema|mirror]]) — agent_runtime Postgres schema 설계 + search_path 전역 변경 금지 + AR-M4 read cutover
- **ADR-0028** ([[Decisions/ADR-0028-runtime-mysql-cleanup|mirror]]) — runtime 6 테이블 MySQL cleanup 14-day window + Stage A/B/C (Phase 2 완료 2026-05-27)
- **ADR-0029** ([[Decisions/ADR-0029-windows-browser-testing|mirror]]) — 실제 Windows 브라우저 AI 자동 검증 (PB-0008, feature-0008)
- **ADR-0030** ([[Decisions/ADR-0030-ssrf-guard-toggle|mirror]]) — datasource SSRF 사설망 경계 env 토글 (Major 보안 저하, 사용자 승인)
- **ADR-0022 / ADR-0023 / ADR-0025-pgvector** — TASK-0094 첨부 multi-cycle: MinIO storage + sandbox MySQL user 4종 + PGVector
- **Unit-level 설계** — 멀티 데이터소스 (ADR-CORE-0002/03/04) · fork hybrid (ADR-WEB-0005) · ask-worker (ADR-WEB-0004) 는 unit `DECISIONS.md` 정본 ([[Decisions/_Index#21-unit-level-설계-결정-repo-adr-와-별개|MOC §2.1]]).

[[Decisions/_Index|전체 Decisions MOC]] 참조.

### 2.3 데이터 흐름

```
User → Caddy/web (TLS) → FastAPI (feature-0003)
                              ├→ MySQL agent_memory (web* RBAC/audit/auth)
                              ├→ MinIO (첨부 storage)
                              └→ /api/ask → ask_jobs 큐 → ask-worker
                                    └→ agent loop (feature-0002)
                                          ├→ Bedrock gateway → Claude (feature-0007)
                                          ├→ Postgres agent_kb (KB + runtime, pgvector)
                                          └→ 데이터소스 N (MySQL·MSSQL, registry+allowlist+dialect)
```

> **2026-05-27**: agent runtime state (`agent*` 10 테이블) 가 MySQL → Postgres 이관 완료. MySQL `agent_memory` 에는 `web*` 18 테이블만 잔존.
> **2026-06**: data plane 이 멀티 데이터소스 (MySQL·MSSQL) 로 일반화 + ask-worker 큐 cutover.

자세한 그림과 trust boundary 는 [[Architecture/Data-Flow|Data Flow]] 참조.

### 2.4 진행 중인 흐름 / 최근 완료

- **사용자 보안 보강 6종 (2026-06-19, 전체 완료)** — ① 공유 링크 시간 기반 만료 (SECURITY §7.2) · ② 로그인 시도 제한 (계정 잠금 + IP throttle, §12) · ③ 감사 로그 변조방지 (SHA-256 해시 체인 + 검증 + off-DB 앵커, §13) · ④ LLM 사용량 한도 (역할 기본 + 계정 특수, daily/monthly, 사전 게이트 429 fail-open, §SECURITY §6) · ⑤ AI 프롬프트 인젝션 방지 (datamarking + 명령-계층, §14) · ⑥ 2단계 인증 (TOTP, self-service + 관리자 해제, §15). 전건 outside-voice 적대 보안 리뷰 통과. [[../docs/SECURITY|SECURITY.md]].
- **그룹 대화 (feature-0009, 2026-06-19~23)** — 한 대화에 여러 멤버 + `@assistant` 멘션. **열람 ≠ 발화** 권한 분리 (멤버는 datasource 권한 없이 열람만, `@assistant` 발화는 발신자 RBAC 게이트). 공유 링크 '참여 허용'으로 join 일원화. 라이브 UX (적응형 폴링·`@`멘션 자동완성·발신자 Identicon 아바타·피멘션 알림+하이라이트) 배포 완료. S5(run cap·actor 귀속)·S6(스레드) deferred. [[Features/feature-0009-group-conversation|카드]].
- **NL→SQL 정확도 flywheel (2026-06-19~23, 진행 중)** — `dba-ai-nl2sql` ROADMAP 드레인: ITEM-01 평가 harness(RAGAS+LLM-judge) · ITEM-02+03 샘플쿼리 few-shot 저장소(pgvector, datasource-scoped, 예시-only 주입) · ITEM-04 데이터소스 비즈니스 컨텍스트 필드 · ITEM-07 self-reflection 자가수정 루프 · ITEM-10 용어/ENUM 코드사전. 효과 A/B 는 임베딩(titan) 복구 후 harness 측정. [[concepts/nl2sql-flywheel]] · `docs/improvements/dba-ai-nl2sql/ROADMAP.md`.
- **insight-worker 병목 진단·수정 (TASK-0305, 2026-06-23)** — "제품 DB 파악 진전 없음" 2축 분리: 축A 커버리지(RO 로그인 per-DB GRANT 누락 → 운영 GRANT 가 1차 해결) · 축B 처리량(fingerprint casefold·force_scan 진전기반 backoff·실패사유 telemetry). [[concepts/insight-worker]].
- **멀티 데이터소스 (2026-06)** — Stage 1 P1 (multi-MySQL) + datasource registry 암호화 (TASK-0205) + DB-단위 접근 (TASK-0206) + datasource-aware insight (TASK-0219) 배포·라이브검증 완료. MSSQL 실연결 검증 (제품90). 다음 = Stage 2 MSSQL 전면 / P2 UI. [[concepts/multi-datasource]].
- **데이터소스 연결 격리 + 연결상태 3색 (2026-06)** — per-datasource **circuit breaker** (TASK-0247, `AGENT_DB_CONNECT_TIMEOUT_SEC` 10s 로 단일 직렬 ask-worker starvation 차단) + insight-worker 연결 회복력 (TASK-0255) + `conn_health` 모니터의 **3-state 분류 (정상 #16a34a / 불안정 #dc2626 / 끊김 #6b7280)** 가 작업화면·관리콘솔 양면에 노출 (TASK-0250/0261/0282). 느린 타-리전 datasource 도 작업화면 사용 가능 (`should_fast_fail` = down 한정). [[concepts/datasource-registry]].
- **데이터소스 라벨/키 분리 → Id surrogate (TASK-0277)** — `DatasourceKey` (rename 가능 라벨) 바인딩이 rename 시 고아되던 결함을 stable `WebDatasources.Id` surrogate FK 로 근본수정 (3 테이블 DatasourceId backfill + Id-구동 cascade rename). [[concepts/datasource-registry]].
- **첨부 메타 MySQL → PG cutover (TASK-0279)** — 첨부 4 테이블을 MySQL `agent_memory` → PG `core_attachments` (+부속) 로 cutover (읽기 전환·MySQL 쓰기 롤백안전망). id 권위 = MySQL, dual-write fail-soft, backfill `--verify` diff=0 게이트.
- **관리 콘솔 성숙 (2026-06)** — 대시보드 위젯화·CloudWatch (TASK-0210/0218), LLM 사용량 대시보드 (TASK-0163~0202), 제품 insight 완료율·DB별 파악내용 (TASK-0223/0242/0243), 권한 편집기 점진적 공개 + 단일열 tree (TASK-0257~0270), 보관 대화 탭 정합 (TASK-0277), 제품 아이콘 편집 오버레이 (TASK-0283).
- **답변 diff 블록 (TASK-0256)** — assistant 가 첨부/쿼리 리뷰·편집 시 변경을 markdown ```diff 블록으로 제시 + 웹 UI 가 라인별 +/- 색 렌더 (`enhanceDiffBlocks`). 프롬프트 자동작성 SSE 스트리밍 (TASK-0233/0254, stick-to-bottom).
- **ask-worker out-of-process (2026-06)** — `ask_jobs` 큐 + ask-worker 서비스 cutover (TASK-0169). orphan-on-redeploy 제거 + 요청 즉시 취소/재요청 (TASK-0241). [[concepts/ask-worker-queue]].
- **storage Postgres 단일화 (완료 2026-05-27)** — KB (Phase 1, ADR-0021/0025) + runtime (Phase 2, ADR-0027/0028) 이관 완료. 첨부 메타 (TASK-0279) 까지 PG 로 이동. 잔여 = `web*` RBAC/audit/auth 테이블.
- **자동화 폐기 → 수동 PR 흐름** — ADR-0018 (`ai-*` 워크플로 폐기, 단순화).

## 3. 외부 source 합성

### 3.1 인용 source

본 vault 의 *템플릿 패턴* 자체는 다음 외부 source 에 매핑되어 있다 (`AGENTS.md §21.10` 출처 표 정본):

- [Karpathy LLM Wiki gist](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f) (33k stars) — raw / wiki / schema 3-layer
- [SamurAIGPT/llm-wiki-agent](https://github.com/SamurAIGPT/llm-wiki-agent) (2.7k) — `wiki-ingest` 10-step / `wiki-query` 4-step / `wiki-lint` 6-category
- [AgriciDaniel/claude-obsidian](https://github.com/AgriciDaniel/claude-obsidian) (5.5k) — vault skeleton
- [namu.wiki 편집지침](https://namu.wiki/w/%EB%82%98%EB%AC%B4%EC%9C%84%ED%82%A4:%ED%8E%B8%EC%A7%91%EC%A7%80%EC%B9%A8/%EC%9D%BC%EB%B0%98%20%EB%AC%B8%EC%84%9C) — namu-style 사람 facing 형식

`wiki/sources/` 디렉토리는 도메인 source summary 누적 영역이며 현재는 placeholder (raw/ 큐레이션 시 ingest 예정).

### 3.2 합성된 결론

> 합성: 본 프로젝트는 *기존 운영 자산의 구조 이관* 으로 시작 (ADR-0012~0014) → *Plan-Review-Execute + playbook 도입* (ADR-0016) → *GitHub 자동화 폐기 + 단순 PR 흐름* (ADR-0018) → *audit subsystem + KB Postgres 분리 + Bedrock 통합* (ADR-0019/0021/0026) → *첨부 multi-cycle* (ADR-0022/0023/0025) → *storage Postgres 단일화* (ADR-0027/0028, 2026-05) → *멀티 데이터소스 (MySQL·MSSQL) + envelope 암호화 registry + DB-단위 접근* (ADR-CORE-*, 2026-06) → *관리 콘솔 성숙 + ask-worker out-of-process* 로 진화했다. 단일 MySQL DBA 도구에서 **다중 엔진 데이터소스 분석 플랫폼**으로 범위가 확장된 것이 2026-06 의 핵심 서사.

### 3.3 미해결 contradiction

- ADR-0025 가 정본 `docs/DECISIONS.md` 안에 *두 entry* 로 존재 (M5 cleanup, 2026-05-22 + PGVector attachment RAG, 2026-05-21) — wiki mirror 는 `ADR-0025-m5-cleanup` 과 `ADR-0025-pgvector-attachment-rag` 두 page 로 분리해 양쪽 정본 참조 보존.

## 4. 알려진 한계

- *통합 테스트 자동화 부재* — `repo/tests/integration/` 가 구조만 갖춤. ([[../docs/ARCHITECTURE|ARCHITECTURE §7]])
- *Bedrock model deprecation drift* — `litellm_config.yaml` 의 versioned model ID 가 AWS rotation 에 끌려간다 (ADR-0026 Consequences).
- *MSSQL synonym/view = GRANT hard boundary* — DB-단위 allowlist 가 synonym/view 의 underlying object 까지 강제하지 못함 (accepted-risk, [[concepts/db-level-access]]).
- *SSRF 사설망 경계 OFF* — 운영이 `AGENT_DATASOURCE_SSRF_GUARD_ENABLED=0` (사내 사설망 전제). 메타데이터 IP 는 하드차단 유지 ([[Decisions/ADR-0030-ssrf-guard-toggle]]).
- *wiki layer 의 stale risk* — 정본 변경 시 mirror 가 자동 update 되지 않는다. v3.13.0 의 `check #12` 는 WARN-only. (본 갱신이 2026-06-16 → **2026-06-23** drift 를 해소 — 그룹 대화 feature-0009·보안 6종·NL2SQL flywheel 반영.)
- *보안 hardening — 사용자 보강 6종 완료 (2026-06-19)* — 로그인 시도 제한·2단계 인증(TOTP)·공유 링크 만료·LLM 사용량 한도·감사 변조방지·프롬프트 인젝션 방지 구현 완료 ([[../docs/SECURITY|SECURITY.md]] §6·§7.2·§12~§15). 잔여 위협모델(예: 분산 botnet·LLM 인젝션 확률적 완화 한계)은 SECURITY.md 에 정직 기록.

## 5. 다음 단계

- **NL→SQL flywheel 후속** — ITEM-05 하이브리드 검색 · ITEM-06 reranker · ITEM-08 fix-with-AI · ITEM-09 heavy-query plan+approve · ITEM-11 거버넌스 포탈(샘플 등록 UI) · ITEM-12 retrieval tuning. 효과는 ITEM-01 harness 로 측정 게이트. [[concepts/nl2sql-flywheel]].
- **그룹 대화 S5/S6** — per-conversation run cap·`llm_usage` actor 귀속·LLM 화자 라벨(S5) → 풀 스레드 UI + 스레드별 run 병렬화(S6). [[Features/feature-0009-group-conversation|카드]].
- **멀티 데이터소스 Stage 2 / P2** — MSSQL 전면 (§9/§10 합격선) + datasource UI (P2). [[concepts/multi-datasource]].
- **메인 loop tier 라우팅** — LLM 사용량 대시보드 follow-up: 메인 추론의 edge/auto tier 라우팅 부재 (현재 claude 만). [[Decisions/ADR-0026-bedrock-llm-provider]].
- **Phase 3 web\* 이관** — `web*` 18 테이블 (RBAC/audit/auth) Postgres 이관 (미진행).
- **Sprint 4 D RAG** — `agent_drag` namespace + PGVector compose service 추가 (ADR-0024 / ADR-0025-pgvector).

## 6. 관련 문서

- [[wiki/Index|Index — MOC]]
- [[wiki/Architecture/Overview|Architecture Overview]]
- [[wiki/Features/_Index|Features MOC]]
- [[wiki/Decisions/_Index|Decisions MOC]]

## 7. 둘러보기

- 상위: [[wiki/Index|Index]]
- 하위 영역: [[wiki/Architecture/Overview]] · [[wiki/Features/_Index]] · [[wiki/Decisions/_Index]] · [[wiki/concepts/_Index]] · [[wiki/entities/_Index]] · [[wiki/Glossary/_Index]]
- sibling: [[wiki/Log|Log.md]] · [[wiki/README]]

## 8. 외부 link

- [Karpathy LLM Wiki gist](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)
- [namu.wiki 편집지침](https://namu.wiki/w/%EB%82%98%EB%AC%B4%EC%9C%84%ED%82%A4:%ED%8E%B8%EC%A7%91%EC%A7%80%EC%B9%A8/%EC%9D%BC%EB%B0%98%20%EB%AC%B8%EC%84%9C)
- [AWS Bedrock Anthropic models — Seoul region](https://docs.aws.amazon.com/bedrock/latest/userguide/models-supported.html)

## 분류

`#wiki/overview` · `#status/active` · `#confidence/high` · `#maturity/substantial`
