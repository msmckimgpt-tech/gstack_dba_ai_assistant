---
doc_type: WIKI_HOT_CACHE
last_updated: 2026-06-25
---

# Hot Cache

## Last Updated
2026-06-25

## Key Recent Facts
- 그룹 대화 라이브 UX 확장(feature-0009, 06-25): 사이드바 안 읽음/@멘션 배지(read cursor, REQ-GC-R8 · alembic 0019) · 메시지 좌우 정렬(내 메시지 우측, 상대/`@assistant` 좌측) · 공유 팝업 owner 멤버 추방/차단/해제(kick/ban/unban, hover 액션) · 참가자 per-message 제품 선택(REQ-GC-R7, 발신자 RBAC) · 처리 중 composer 비잠금/1:1 인터럽트 재요청/그룹 @assistant 중복차단.
- 관리 콘솔 프롬프트 자동화(feature-0003, 06-25): 역할 '전체 제품 프롬프트' · 프로필 '제품별 프롬프트' AI 자동 작성 + 제품 분석률 95% 도달 시 제품프롬프트 1회 자동완성 + 규칙 자동추가 DB 의 insight 분석여부·완료율 UI + '지식베이스' 메뉴 그룹 재편.
- feature-0011 `shared/` 추출 P5a Step1~5c 완료(06-25): model_catalog·config·db·conn_health·datasources 소비처 마이그레이션 + alias shim 4종 전량 제거(make test 회귀 0). 잔여 Step6(feature 단위 Dockerfile 분리).
- 안정성(06-25): init "준비" 임베딩 지연 회귀 해소(전용 embed-ollama + 캐싱 + fast-timeout) · 요청량 한도 메시지 주체 구분(서비스 자체 한도 vs 계정 한도, 문구만).
- 관리 콘솔 메타데이터 거버넌스(ITEM-11, feature-0003/0002): 용어·ENUM CRUD + 테이블/컬럼 설명·주입·부트스트랩 + 샘플 admin + 5 서브뷰 AI 자동완성. NL→SQL 컨텍스트 강화.
- feature-0010(토대, 06-23): 계정별 Google Drive OAuth 토큰 암호화 저장 + MCP seam A. 연동 미수행/비활성.

## Recent Changes
- shared/ P5a Step5 완료: 4개 alias shim(model_catalog 제외 config·db·conn_health·datasources) 소비처를 `shared.*` 로 직접 마이그레이션 후 `modules/*` shim 전량 제거.
- 그룹 대화 06-25: 안 읽음/@멘션 배지·메시지 좌우 정렬·owner 멤버 추방/차단(앞선 06-24 참여자 roster·보관 설정팝업·참여자 나가기·'참여 허용' owner-only 게이트 위에).
- 그룹 대화 06-25 잔여(doc_sync): 참가자 per-message 제품 선택·발화(PR#440)·처리 중 composer 비잠금/1:1 인터럽트 재요청/그룹 중복차단(PR#438·#444)·@assistant 발신자 표시 정정(PR#437)·datasource 회로차단 사용자 안내 문구 분리(PR#439, feature-0002).
- 그룹 대화 06-25 후속(gc-optimistic-sender-attrib, 미머지): optimistic(전송 직후) 발신자 표시 정정 — 비-owner 참가자 메시지가 처리 중 동안 owner 로 잘못 표시되던 깜빡임 제거(`_selfSenderMeta()`를 optimistic 2지점에 부여). frontend display-only.

## Active Threads
- feature-0011 P5a 잔여: Step6(feature 단위 Dockerfile 분리, Critical — Windows 브라우저 완료 게이트). app.py router 분할은 P5b 별도.
- feature-0010 활성화 cycle 이월: 라이브 토큰교환·refresh 회전·Google revoke·설정 UI·mcp_client seam 배선.
- insight-worker(TASK-0305) GRANT 적용 · NL2SQL few-shot A/B.
- baseline 추적: `test_product_delete_block_conv.py` 2건 clean main 에서도 실패(admin_delete_product 404) — feature-0003 소관.
- 잔여 doc drift: `concepts/nl2sql-flywheel.md` §2 가 ITEM-08/ITEM-11 출시 미반영(stale) — 후속 doc_sync 1회 필요.
