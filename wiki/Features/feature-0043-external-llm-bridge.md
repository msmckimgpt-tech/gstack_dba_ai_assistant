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
- **무설치(등록형 경로).** 등록형 경로는 `https://<host>/api/ai/mcp` 를 AI 클라이언트에 URL+토큰으로
  등록하는 것뿐이고, 러너 `bridge_agent.py`·`bridge_runner.py` 도 Python 표준 라이브러리만 쓴다.
  다만 **연결의 기본 진입점은 2026-08-28 이후 등록이 아니라 원클릭 셸 명령이다**(아래 P0-AC).
- **연결은 셸이 실행한다(2026-08-28, P0-AC/AD).** 연결 수단이 「AI 에게 지시문 붙여넣기」 하나뿐일
  때는 어떤 AI 는 MCP 로 등록하고 어떤 AI 는 러너를 안 띄워 **구축 방식이 매번 달랐다.** 기본
  진입점을 셸 명령(`bridge_setup.sh`/`.ps1`)으로 바꿔 해석층을 걷어냈고, 지시문은 지우지 않고
  `<details>` 로 접어 보조로 내렸다 — 대체가 아니라 **기본 경로의 교체**다. 셋째 길로 **환경
  판단만** 그 머신의 AI 가 `BRIDGE_PROBED_*` 네 칸을 채우고, 그 값을 스크립트가 실존·타입·범위·
  allowlist 로 다시 본다(실행 경로는 여전히 하나라 「같은 입력이면 같은 결과」가 유지된다).
  브라우저는 샌드박스라 로컬 프로세스를 못 띄우므로 재기동은 최초 1회 등록한 **URL 스킴 핸들러**를
  거치며, 그 등록물은 setup 에만 있고 러너에는 없다.
- **연결이 요청의 전제조건이다**(정본 FUNCTION §P0-AB「요청과 연결은 다른 흐름이다」 — 같은 파일에 동명 절이 3개라 제목으로 한정). `연결됨`(토큰) × `대기 중`(러너) 곱을 **서버**가
  판정한다(`compose_blocked` — 프런트가 조립하면 판정이 두 벌이 되고 갈리는 순간 느슨한 쪽이
  사용자가 보는 진실이 된다). 토큰이 없으면 `409 bridge_blocked` 로 거절하며 **아무것도 저장하지
  않는다**(유령 말풍선 방지). 사용자가 쓴 입력은 지우지 않는다.
- **폴링이 아니라 블로킹 대기.** `wait_for_request` 가 질문이 들어오는 그 순간 반환한다(55초 상한 ·
  만료는 오류가 아니라 200 + `timed_out: true`). 주기 폴링은 인지 지연이 사람마다 달라 '환경 차이'
  가 되므로 금지다. 자리를 비워도 처리하려면 상주 러너 `bridge_agent.py`(stdlib 전용 단일 파일)를
  띄우며, 지시문에서 이것이 **권장 기본 경로**다. 워커는 **1개로 시작해 수요를 따라간다**(P0-Y,
  2026-08-28 — 종전 고정 2개는 폐기): `wait_for_request` 가 돌려준 대기 질문 수가 슬롯 수를 넘으면
  그만큼 늘고(상한 `--max-workers` 기본 8 · 예측 확장 없음), 300초 넘게 쉰 슬롯을 오래된 것부터
  회수하되 **최소 1개는 남긴다**. tick 은 별도 타이머가 아니라 long-poll 반환 그 자체다.
- **08-27~28 후속 19 cycle 로 사용감 패리티에 수렴.** 인증 축 `mat_` 단일화 · 연결 상태 상시 표시 ·
  인터럽트/맥락 전환/SSE 진행 스트리밍 · 미연결 질문 보관과 이어받기 · 대화 제목 2단 · 온보딩
  지시문의 **서버 단일 조립** · 취소 tight loop 해소.
- **08-28 후반 13 cycle 이 더 있었다.** 러너가 자기 런타임·모델·추론등급을 하트비트에 실어
  **신고**하고 웹은 그것만 보여준다(서버는 이름을 하나도 모른 채 운반만 하므로 **새 런타임 지원에
  서버 배포가 필요 없다** · 신고가 없으면 선택기도 없다) · 하트비트가 도는 동안 연결은 시간으로
  끊기지 않고 **명시적 해제**(러너 종료 · 웹 로그아웃)로만 끊기며 로그아웃 시 러너는 스스로
  종료한다 · assistant 첨부 **쓰기** 복원(`shared/attachment_write.py` 단일 시퀀스 — 종전은 파일이
  v1 그대로인데 "수정했습니다" 라고 답하던 **거짓 성공**이었다) · 능력 목록을 그 AI 자신이 정한다.
  라이브 배포 `35f03f62`.
- **아직 못 본 것.** 취소 후 `submit_answer` 409 집행 — 러너는 취소를 인지해 **제출 전에 하차**
  하므로(설계대로다) 그 경로에 닿지 않고, 신호를 읽지 않는 등록형 AI 로만 재현된다. 진행 **단계**
  실시간 표시는 2026-08-28 실 LLM 검증에서 **PASS 로 해소**됐다(답변 전에 단계가 1→4→5 로 증가).
- **한계.** 개인 머신 AI 가 꺼져 있으면 답이 오지 않는다. UI 는 이를 대기 상태로 정직하게 표시한다.

## 관련

- 정본: `unit/feature-0043-external-llm-bridge/docs/{FUNCTION,TASK,ANCHOR,REPORT}.md`
- 도구 표면: [[feature-0041-external-ai-tool-surface]]
- 위협모델: `docs/SECURITY.md` §49
