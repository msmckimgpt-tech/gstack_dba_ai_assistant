---
doc_type: WIKI_FEATURE_CARD
feature_id: feature-0043-external-llm-bridge
status: active
---

# feature-0043 — 서버 계정 LLM 차단 + 웹 대화 pull 브리지

## 한 줄

서비스가 보유한 Claude 계정으로는 더 이상 추론하지 않고, 웹 대화 질문을 **각 사용자의 개인 머신
AI 런타임**이 자기 계정 LLM 으로 처리한다.

## 왜

2026-08-07 `claude-corp` 7일 쿼터가 100% 소진돼 서비스가 멈췄다. 계정을 늘리는 대신 **추론 주체를
뒤집는다** — 서버는 도구·컨텍스트·데이터만 제공하고 토큰은 사용자 구독이 부담한다.

## 어떻게 (한눈에)

```
[웹 대화창] 질문 → WebAiTasks(Origin='web', 대기)  → "내 AI 가 처리 중" 말풍선
                          ↓ 개인 머신 AI 가 MCP/REST 로 폴링
              list_open_requests → claim_request (점유·30분 lease)
                          ↓ 개인 계정 LLM 이 추론 + 기존 도구로 DB 조회
              submit_answer → 원 대화에 답변 저장 → 화면이 폴링으로 자동 갱신
```

## 알아둘 것

- **push 가 아니라 pull.** MCP `sampling` 은 프로토콜 2026-07-28 에서 폐기됐고(SEP-2577)
  Claude Code 가 미지원이라(anthropics/claude-code#1785) 서버→클라이언트 push 경로가 없다.
- **차단은 두 겹.** `shared/llm_gate.py`(코드 기본값 = 차단)가 정본, `litellm_config.yaml`
  alias 주석이 두 번째 자물쇠. 되돌리려면 **둘 다** 풀어야 한다.
- **로컬 임베딩은 살아 있다.** `titan-embed`(bge-m3)는 계정과 무관하고 KB 검색이 의존한다.
- **무설치.** 주 경로는 `https://<host>/api/ai/mcp` 를 AI 클라이언트에 URL+토큰으로 등록하는 것뿐.
  보조 러너 `bridge_runner.py` 도 Python 표준 라이브러리만 쓴다.
- **한계.** 개인 머신 AI 가 꺼져 있으면 답이 오지 않는다. UI 는 이를 대기 상태로 정직하게 표시한다.

## 관련

- 정본: `unit/feature-0043-external-llm-bridge/docs/{FUNCTION,TASK,ANCHOR,REPORT}.md`
- 도구 표면: [[feature-0041-external-ai-tool-surface]]
- 위협모델: `docs/SECURITY.md` §49
