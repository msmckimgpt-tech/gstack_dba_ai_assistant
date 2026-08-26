---
doc_type: WIKI_HOT_CACHE
last_updated: 2026-08-27
---

# Hot Cache

## Last Updated
2026-08-27

## Key Recent Facts
- **feature-0043 라이브 전환 완료(`0b2b4435`)** — 서버 보유 Claude 계정(claude-corp/root)으로는 더 이상 추론하지 않는다. 차단은 두 겹이고 **코드(`shared/llm_gate.py`)가 정본**(기본값=차단), `litellm_config.yaml` alias 주석이 두 번째 자물쇠. 되돌리려면 둘 다 푼다. 로컬 임베딩(bge-m3)만 살아 있다.
- 웹 대화 질문은 `WebAiTasks`(`Origin='web'`) 대기 작업이 되고 개인 머신 AI 가 `list_open_requests`→`claim_request`→`submit_answer` 로 처리한다. **push(MCP sampling)는 폐기+Claude Code 미지원**이라 pull 이다.
- codex 2라운드에서 P1 11건 — 대부분 배선/상태전이(어댑터 미등록·쿼터에 막힘·`selectConversation` no-op 로 화면 미갱신·권한 미재검증). 회귀는 배선 25 + 상태/장애/권한 17.

## Recent Changes
- `shared/llm_gate.py`(신규) · `modules/llm._get_llm_client`·`agent_core._run_agent_core` 게이트 · `litellm_config.yaml` alias 14종 주석
- `routers/ai_tools.py`(도구 2종·`bridge_status`·권한 재검증·lease) · `routers/conversations.py`(ask 분기) · `static/app/composer.js`(폴링) · `bridge_runner.py`(stdlib 전용)
- `bin/smoke-conversation.sh` 모드 인지형으로 수정 — 전환이 배포 게이트의 전제를 깼다

## Active Threads
- PR #1352(스모크 전제) 병합 → gateway reconcile 완결. 현재도 앱 게이트가 정본이라 계정 미사용.
- **PB-0008 화면 시각검증 미수행** — win-browser 브리지가 이 환경에서 불가(`win_host` 오판). 해소 후 대기 말풍선→폴링→답변 렌더 확인 필요.
