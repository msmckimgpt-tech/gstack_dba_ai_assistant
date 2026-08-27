---
doc_type: WIKI_FEATURE_CARD
scope: feature
status: active
edit_policy: ai-maintained
source_of_truth: false
template_version: v3.12.0
domain: [feature, wiki]
ai_read_priority: 7
wiki_role: feature_card
wiki_name: project
confidence: high
maturity: substantial
ai_generated: true
feature_id: feature-0043-external-llm-bridge
linked_unit: unit/feature-0043-external-llm-bridge
created: 2026-08-26
sources:
  - ../../unit/feature-0043-external-llm-bridge/docs/FUNCTION.md
  - ../../unit/feature-0043-external-llm-bridge/docs/REPORT.md
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
                          ↓ 개인 머신 AI 가 블로킹 대기(wait_for_request · 폴링 아님)
              list_open_requests → claim_request (점유·30분 lease)
                          ↓ 개인 계정 LLM 이 추론 + 기존 도구로 DB 조회
              submit_answer → 원 대화에 답변 저장 → 화면이 SSE 로 자동 갱신(폴링은 폴백)
```

## 알아둘 것

- **push 가 아니라 pull.** MCP `sampling` 은 프로토콜 2026-07-28 에서 폐기됐고(SEP-2577)
  Claude Code 가 미지원이라(anthropics/claude-code#1785) 서버→클라이언트 push 경로가 없다.
- **차단은 두 겹.** `shared/llm_gate.py`(코드 기본값 = 차단)가 정본, `litellm_config.yaml`
  alias 주석이 두 번째 자물쇠. 되돌리려면 **둘 다** 풀어야 한다.
- **로컬 임베딩은 살아 있다.** `titan-embed`(bge-m3)는 계정과 무관하고 KB 검색이 의존한다.
- **무설치.** 주 경로는 `https://<host>/api/ai/mcp` 를 AI 클라이언트에 URL+토큰으로 등록하는 것뿐.
  보조 러너 `bridge_runner.py` 도 Python 표준 라이브러리만 쓴다.
- **폴링이 아니라 블로킹 대기.** `wait_for_request` 가 질문이 들어오는 그 순간 반환한다(55초 상한 ·
  만료는 오류가 아니라 200 + `timed_out: true`). 주기 폴링은 인지 지연이 사람마다 달라 '환경 차이'
  가 되므로 금지다. 자리를 비워도 처리하려면 상주 러너 `bridge_agent.py`(stdlib 전용 단일 파일 ·
  워커 기본 2개)를 띄우며, 지시문에서 이것이 **권장 기본 경로**다.
- **08-27~28 후속 19 cycle 로 사용감 패리티에 수렴.** 인증 축 `mat_` 단일화 · 연결 상태 상시 표시 ·
  인터럽트/맥락 전환/SSE 진행 스트리밍 · 미연결 질문 보관과 이어받기 · 대화 제목 2단 · 온보딩
  지시문의 **서버 단일 조립** · 취소 tight loop 해소. 라이브 배포 `d511d95c`.
- **아직 못 본 것.** 취소 후 `submit_answer` 409 집행과 진행 **단계** 실시간 표시는 도구를 실제
  호출하는 개인 AI 로만 확인할 수 있어 미검증이다.
- **한계.** 개인 머신 AI 가 꺼져 있으면 답이 오지 않는다. UI 는 이를 대기 상태로 정직하게 표시한다.

## 관련

- 정본: `unit/feature-0043-external-llm-bridge/docs/{FUNCTION,TASK,ANCHOR,REPORT}.md`
- 도구 표면: [[feature-0041-external-ai-tool-surface]]
- 위협모델: `docs/SECURITY.md` §49
