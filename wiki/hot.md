---
doc_type: WIKI_HOT_CACHE
last_updated: 2026-06-25
---

# Hot Cache

## Last Updated
2026-06-25

## Key Recent Facts
- 요청량 한도 메시지 주체 구분(limit-subject-msg, 06-25): 서비스 자체 한도(KIND_THROTTLED)에서 AWS Bedrock 명칭 제거 → "서비스 자체의 요청량 한도", 계정 한도(`_check_account_token_quota`)는 "계정의 … LLM 토큰 사용 한도". 메시지 문구만(로직·429·계약 무변경).
- feature-0011 신설(P5 리팩터): 공통 코드 repo 루트 `shared/` 점진 추출. P5a Step1~3(`model_catalog`·`config`·`db`)을 `modules.X`→`shared.X` 모듈 alias 로 비파괴 이동(심볼·monkeypatch·wildcard 보존), make test 회귀 0.
- 관리 콘솔 메타데이터 거버넌스(ITEM-11, feature-0003/0002): 용어·ENUM CRUD + 테이블/컬럼 설명·주입·부트스트랩 + 샘플 admin + 5 서브뷰 AI 자동완성. NL→SQL 컨텍스트 강화.
- feature-0010(토대, 06-23): 계정별 Google Drive OAuth 토큰 암호화 저장 + MCP seam A. 연동 미수행/비활성.

## Recent Changes
- shared/__init__.py + model_catalog/config/db alias shim + Dockerfile COPY shared + Makefile PYTHONPATH(/work).
- 그룹 대화 06-24: 참여자 roster 표시·보관 설정팝업 이동·참여자 나가기·공유 '참여 허용' owner-only 게이트.

## Active Threads
- feature-0011 P5a 후속: Step4(conn_health·datasources L1 + db back-dep) → Step5(점진 마이그·shim 제거) → Step6(feature 단위 Dockerfile 분리). app.py router 분할은 P5b 별도.
- feature-0010 활성화 cycle 이월: 라이브 토큰교환·refresh 회전·Google revoke·설정 UI·mcp_client seam 배선.
- insight-worker(TASK-0305) GRANT 적용 · NL2SQL few-shot A/B.
- baseline 추적: `test_product_delete_block_conv.py` 2건 clean main 에서도 실패(admin_delete_product 404) — feature-0003 소관.
