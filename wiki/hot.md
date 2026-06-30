---
doc_type: WIKI_HOT_CACHE
last_updated: 2026-06-30
---

# Hot Cache

## Last Updated
2026-06-30

## Key Recent Facts
- feature-0016 메타데이터 지식그래프 신규(06-30, 대형, PR#477/#479/#480/#482/#484): 관리콘솔 메타데이터를 Apache AGE(openCypher) `metadata_kb` 그래프(관계형 SSOT 의 재생성 가능 투영)로 승급 — 그래프 뷰(Cytoscape·fcose 클러스터링·관련도 사이징·이웃 60x 인덱스)·검색·`graph_navigate` AI 도구(8K 테이블 컨텍스트 초과 해소). 커스텀 PG16 이미지(pgvector+pg_trgm+AGE, alembic 0025) cutover 라이브 완료(데이터 무손상·무중단 롤링). per-datasource 투영(~21 ds/8,122 테이블). 엣지 희소(게임 DB FK 미선언) — 노드 그래프·그룹핑 즉시 가치. cross-cut 0002(코어·tool)·0003(admin UI). ※번호 0016 은 metadata-graph + zd-pg-pause-caddy 2 슬라이스 공유(사람 결정 보류).
- web 무중단 배포·운영 위생군 라이브 완료(06-30, feature-0014/0015/0016-zd/0017): web 무중단 롤링 배포(Caddy LB web-a/web-b·자동 롤백·:18080 폐기→:443 단일, 0014) + insight-worker graceful 종료·MySQL online-DDL 게이트·백업 복원 리허설 cron(0015) + PG 재시작 무중단화 pgbouncer PAUSE 래퍼(0016-zd, RW 무에러 실증) + 배포 빌드게이트 snap-docker metadata-race false-failure 수정(0017, 전 web 배포 차단 해소).
- 메타데이터 관리 화면 정리(feature-0003, 06-30, frontend-only): 스키마 설명 패널 list-detail 2단 재구성·데이터소스 선택 단일화(헤더 스코프 상속)·테이블 설명 인라인 입력(평면화·정렬)·스키마 가져오기 시 기존 설명 prefill+변경분만 저장. 질문 의도 이해·끈기 개선(feature-0002, 능동 해석 지침 1:1·그룹 주입+식별자 대소문자 보존).
- feature-0013 관계 다이어그램 신규(06-29, PR#462/#469): assistant 가 flow/관계/구조 질문에 mermaid(ER·flowchart)로 사용자 DB 구조를 답함 — 웹 UI mermaid 렌더(vendor v10.9.3, sanitize-후 `securityLevel:'strict'` + graceful fallback), `_MERMAID_DIAGRAM_GUIDANCE` 발화(feature-0002), `table_relationships` 관계 저장소(alembic 0024 — FK introspection·대화 JOIN 학습) + knowledge digest 주입. 후속 mermaid render orphan/erDiagram "Syntax error" 봉인(rd-h2/h3), PB-0008 라이브 검증 PASS·배포 완료(rd-h6). cross-cut 코드 거주 feature-0002·0003.
- 메타데이터·공유 대화 화면 정리(feature-0003, 06-29 저녁): 스키마 골격 결과 패널 페이지네이션(`META_BS_PAGE_SIZE=30`, 가시성 윈도우 — 저장/AI일괄 전체수집 불변식 유지)·여백 압축(metadata-bs-paging), flex-shrink 클리핑 수정(metadata-bs-flexclip). 공유 대화 뷰 mermaid 렌더 + 전체폭 반응형(share-mermaid-responsive) + 스크롤바 가이드 뱃지·클릭 스크롤 단축 EaseOutExpo(point-scroll-easeoutexpo). 용어사전 역할 선택 UI 단일화 + 역할 미표시(필드명 role_key→key) 수정(glossary-role-single-ui/fieldname-fix). 새 대화 첫 전송 사이드바 중복 제거(new-conv-dedup). diff 답변 누출 줄번호 prefix 정규화(diff-lineno-leak).
- 메타데이터 부트스트랩 결과 패널 접기+검색 재설계 + 잘림 cache-buster 수정(feature-0003, 06-29): 직전 mssql-db 수정의 460px 캡 제거가 배포는 됐으나 `admin.html` 의 `styles.css?v=`/`admin.js?v=` cache-buster 미bump 로 브라우저가 stale CSS 를 계속 로드 → "여전히 잘림". cache-buster bump(→20260629-metadata-bs-collapse)로 해소. 또 수백 테이블을 전부 펼쳐 평면 렌더하던 여백 과다를 **테이블별 기본 접힘 한 줄 헤더(caret+이름+입력상태 힌트) + 테이블명 검색/필터 + 모두펼치기/접기** 로 재설계(사용자 결정). 접기·필터는 시각 토글만 — 입력값 DOM 보존, 저장·AI 일괄생성이 전체 수집(회귀 0). 서브탭 전환 재렌더 mode 불일치(pre-existing)는 follow-up. metadata-bs-collapse.
- 메타데이터 부트스트랩 MSSQL database 차원 수정(feature-0003, 06-29): "테이블 설명 > 스키마 골격 가져오기"가 MSSQL 에서 `database=None`→중립 tempdb(shared/db.py `_connect_mssql` 보안 기본값) 임시테이블(`#…`)을 노출하던 "테이블 명칭 모두 오류" 근본 수정. 부트스트랩 unit 엔진분기(MySQL=schema/MSSQL=database via `list_server_databases`, 시스템 DB·스키마·센티넬 필터), MSSQL 선택 DB 연결 평탄수집(저장 schema_name=database — 4계층→3-키, 사용자 결정), suggest grounding 동일분기, 프론트 '데이터베이스/스키마' 라벨, `.admin-meta-bootstrap-result` max-height 제거(패널 내부 잘림 해소, 테이블·컬럼 공통). AI 자동완성은 기구현·깨진 골격에 grounding 해 무력화됐던 것. REQ-20260629T114221.
- 용어사전 대화 자율등록+역할분리+유사어(feature-0002/0003, 06-29): 대화에서 용어 자율 등록 + 등록·검토 역할 분리 + 유사어 참조(관리 콘솔 메타데이터 거버넌스, 마이그 0023, ADR-20260629T101500). 용어 검토 큐는 용어사전 하위 2차 보기 탭으로 중첩(admin IA).
- 답변 피드백 답변당 고유화(feature-0003/0002, 06-29): 답변당 사용자별 고유 👍/👎 1개 강제(마이그 0021/0022 + 고유성 키 id_space 보강) — 새로고침·대화 전환 후 중복 부여 차단.
- 첨부 wrong-bubble 엣지 하드닝(feature-0003, 06-29): 첨부 영속 레이어 매칭 키에 `message_id_space` 추가(ec39a60). 정상 display 경로 동작 동일 — fork/마이그 cross-space 엣지 하드닝.
- feature-0012 web-router-modularization 토대(06-29, PR#456): feature-0003 `app.py` 도메인별 `APIRouter` 점진 분할 토대 — route-parity 안전망 + 의존성 audit(P5b, behavior-neutral).
- 제품 선택 chip 처리 중 항상 활성화(feature-0003, 06-26): 답변 생성 중에도 composer 제품 선택 chip 변경 가능 — turn-immutability 3계층 가드 완화. 제품은 enqueue 시 캡처 → in-flight 답변 비오염, 변경은 다음 요청부터. RBAC/스키마 무변경. ADR-WEB-0006.
- assistant 요청 2번 중복 처리 차단(feature-0003/0002, 06-26): 워커모드 `/api/ask` long-poll 끊김 후 재전송 시 ask_job 2개 → 2회 처리되던 결함을 enqueue 멱등화(dedup NOT EXISTS + 기존 run attach)로 차단. 후속 PG AmbiguousParameter 회귀는 dedup 전용 파라미터+alias 격리로 해소.

## Recent Changes
- doc_sync 06-30(2305): 06-30 10:31 직전 sync 이후 머지 backfill — feature-0016-metadata-graph 전 문서 누락분 신설(STATUS 행·ARCHITECTURE §4/§6·wiki 카드/_Index/overview/Architecture Overview·SECURITY §19 그래프 질의면 색인) + 무중단군(0014/0015/0016-zd/0017) STATUS/ARCHITECTURE §6 의존맵·docs/RELEASE_NOTES 운영자 블록 + feature-0002/0003 06-30 행 + feature 카운트 13→17(디렉토리 18) 5곳 정합. 동반 operational: 릴리즈노트 06-30 블록 10항목 + cache-buster bump(20260630b-rn-0630).
- doc_sync 06-30: 06-29 13:35 직전 sync 이후 머지분 정합 — feature 카운트 12→13(Index/_Index/overview/Architecture Overview)·ARCHITECTURE/overview 기능맵·의존맵 feature-0013 행·STATUS §5 카운트·feature-0013 카드 reality(stub→active, PB-0008 PASS)·`concepts/nl2sql-flywheel.md` §2 ITEM-08/11 출시 반영. 동반: 릴리즈노트 06-29 블록 6항목 추가(3→9) + cache-buster bump(20260630-rn-0630) → web 재배포.
- 제품 chip 처리 중 항상 활성화(f049fee, 06-26): 처리 중 제품 선택을 막던 3계층 가드(`renderProductChip` 시각 disable·`setActiveProduct` busy reject·`update_conversation_product` PATCH 409) 제거 — chip 항상 활성, 변경은 다음 요청부터(in-flight 답변은 enqueue 시 캡처된 product 로 실행). RBAC/스키마 0 변경. ADR-WEB-0006.
- ask-dedup-idempotency(0818b0a·3595ea3, 06-26): `enqueue_ask_job(dedup_message=...)` INSERT NOT EXISTS(`_ACTIVE_SLOT_PREDICATE` 재사용·stale 제외)+`find_active_dup_ask_job` 로 활성 중복이면 새 job·sentinel 없이 기존 run attach; app.js `/api/ask` 실패 시 status 복구 0.7s×3 재시도. 배포 검증 중 dedup NOT EXISTS 가 INSERT SELECT(varchar)와 파라미터 공유 → AmbiguousParameter 로 워커모드 신규 `/api/ask` 전부 500 회귀 → 전용 파라미터 + 테이블 alias `d` 격리로 수정.
- shared/ P5a Step5 완료: 4개 alias shim(model_catalog 제외 config·db·conn_health·datasources) 소비처를 `shared.*` 로 직접 마이그레이션 후 `modules/*` shim 전량 제거.
- 그룹 대화 06-25: 안 읽음/@멘션 배지·메시지 좌우 정렬·owner 멤버 추방/차단(앞선 06-24 참여자 roster·보관 설정팝업·참여자 나가기·'참여 허용' owner-only 게이트 위에).
- 그룹 대화 06-25 잔여(doc_sync): 참가자 per-message 제품 선택·발화(PR#440)·처리 중 composer 비잠금/1:1 인터럽트 재요청/그룹 중복차단(PR#438·#444)·@assistant 발신자 표시 정정(PR#437)·datasource 회로차단 사용자 안내 문구 분리(PR#439, feature-0002).
- 그룹 대화 06-25 후속(gc-optimistic-sender-attrib, 머지): optimistic(전송 직후) 발신자 표시 정정 — 비-owner 참가자 메시지가 처리 중 동안 owner 로 잘못 표시되던 깜빡임 제거(`_selfSenderMeta()`를 optimistic 2지점에 부여). frontend display-only.
- 그룹 대화 06-25 잔여(doc_sync, sync a29a2f0 이후): ① 안 읽음 배지 미감소 최종 근본원인 해소 — 읽음 커서/unread 집계가 `core_messages.id` 공간인데 FE 가 보낸 `last_read_message_id` 는 표시 store `messages.id` 공간이라 disjoint → 핸들러가 requested 무시·항상 `MAX(core_messages.id)` 로 전진(read-idspace-fix). 선행 read 500(`modules.db`→`shared.db`)·읽음 커서 전진 누락(refreshWorkspace/재선택)·입력창 즉시 클리어 보정 포함. ② 공유 대화 join 불가 수정 — PG named-param 타입 모순(AmbiguousParameter) 해소(group_members). ③ assistant SQL dialect 교정(MySQL DS T-SQL thrashing 차단 `_MYSQL_DIALECT_GUIDANCE`)+그룹 히스토리 발신자 맥락 라벨 `[이름]:`(feature-0002). ④ 좌측 대화 전환 크로스페이드(fade-out/in + 가속·reduced-motion no-op, frontend).

## Active Threads
- feature-0011 P5a 잔여: Step6(feature 단위 Dockerfile 분리, Critical — Windows 브라우저 완료 게이트). app.py router 분할은 P5b 별도.
- feature-0010 활성화 cycle 이월: 라이브 토큰교환·refresh 회전·Google revoke·설정 UI·mcp_client seam 배선.
- insight-worker(TASK-0305) GRANT 적용 · NL2SQL few-shot A/B.
- baseline 추적: `test_product_delete_block_conv.py` 2건 clean main 에서도 실패(admin_delete_product 404) — feature-0003 소관.
