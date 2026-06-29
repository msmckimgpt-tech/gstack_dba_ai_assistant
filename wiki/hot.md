---
doc_type: WIKI_HOT_CACHE
last_updated: 2026-06-29
---

# Hot Cache

## Last Updated
2026-06-29

## Key Recent Facts
- 메타데이터 부트스트랩 MSSQL database 차원 수정(feature-0003, 06-29): "테이블 설명 > 스키마 골격 가져오기"가 MSSQL 에서 `database=None`→중립 tempdb(shared/db.py `_connect_mssql` 보안 기본값) 임시테이블(`#…`)을 노출하던 "테이블 명칭 모두 오류" 근본 수정. 부트스트랩 unit 엔진분기(MySQL=schema/MSSQL=database via `list_server_databases`, 시스템 DB·스키마·센티넬 필터), MSSQL 선택 DB 연결 평탄수집(저장 schema_name=database — 4계층→3-키, 사용자 결정), suggest grounding 동일분기, 프론트 '데이터베이스/스키마' 라벨, `.admin-meta-bootstrap-result` max-height 제거(패널 내부 잘림 해소, 테이블·컬럼 공통). AI 자동완성은 기구현·깨진 골격에 grounding 해 무력화됐던 것. REQ-20260629T114221.
- 용어사전 대화 자율등록+역할분리+유사어(feature-0002/0003, 06-29): 대화에서 용어 자율 등록 + 등록·검토 역할 분리 + 유사어 참조(관리 콘솔 메타데이터 거버넌스, 마이그 0023, ADR-20260629T101500). 용어 검토 큐는 용어사전 하위 2차 보기 탭으로 중첩(admin IA).
- 답변 피드백 답변당 고유화(feature-0003/0002, 06-29): 답변당 사용자별 고유 👍/👎 1개 강제(마이그 0021/0022 + 고유성 키 id_space 보강) — 새로고침·대화 전환 후 중복 부여 차단.
- 첨부 wrong-bubble 엣지 하드닝(feature-0003, 06-29): 첨부 영속 레이어 매칭 키에 `message_id_space` 추가(ec39a60). 정상 display 경로 동작 동일 — fork/마이그 cross-space 엣지 하드닝.
- feature-0012 web-router-modularization 토대(06-29, PR#456): feature-0003 `app.py` 도메인별 `APIRouter` 점진 분할 토대 — route-parity 안전망 + 의존성 audit(P5b, behavior-neutral).
- 제품 선택 chip 처리 중 항상 활성화(feature-0003, 06-26): 답변 생성 중에도 composer 제품 선택 chip 변경 가능 — turn-immutability 3계층 가드 완화. 제품은 enqueue 시 캡처 → in-flight 답변 비오염, 변경은 다음 요청부터. RBAC/스키마 무변경. ADR-WEB-0006.
- assistant 요청 2번 중복 처리 차단(feature-0003/0002, 06-26): 워커모드 `/api/ask` long-poll 끊김 후 재전송 시 ask_job 2개 → 2회 처리되던 결함을 enqueue 멱등화(dedup NOT EXISTS + 기존 run attach)로 차단. 후속 PG AmbiguousParameter 회귀는 dedup 전용 파라미터+alias 격리로 해소.

## Recent Changes
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
- 잔여 doc drift: `concepts/nl2sql-flywheel.md` §2 가 ITEM-08/ITEM-11 출시 미반영(stale) — 후속 doc_sync 1회 필요.
