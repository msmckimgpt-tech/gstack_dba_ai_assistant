---
doc_type: DECISIONS
feature_id: feature-0043-external-llm-bridge
status: active
edit_policy: append-only
source_of_truth: true
---

# Decisions

## ADR-20260826T135206-pull-bridge-over-sampling — 역방향 호출을 push(MCP sampling)가 아닌 pull 로 구현

- **상태**: accepted
- **맥락**: 사용자 요구(2026-08-26) — "웹 대화 화면을 통한 요청이, 역방향으로 각 개인 머신의 LLM을
  호출할 수 있도록". 직관적 구현은 서버가 클라이언트에 추론을 요청하는 MCP `sampling/createMessage` 다.
- **조사 결과 (두 가지 독립 사실)**:
  1. sampling 은 **프로토콜 `2026-07-28` 에서 폐기**됐다(SEP-2577). 스펙 문구: *"New implementations
     **SHOULD NOT** adopt it; existing implementations **SHOULD** migrate to integrating directly with
     LLM provider APIs."* 최소 12개월 후 제거 대상이다.
  2. **Claude Code 는 미지원**이다 — anthropics/claude-code#1785 가 2025-06-08 이래 open 이며 구현이 없다.
     (요청 내용이 정확히 "Claude Max 구독으로 MCP 서버 추론 비용을 옮기자" — 이 feature 의 동기와 같다.)
- **결정**: 표준 tools 기반 **pull** 로 구현한다. 웹 질문을 `WebAiTasks` 대기 작업으로 적재하고
  개인 머신 AI 가 `list_open_requests` → `claim_request` → `submit_answer` 로 가져간다.
- **근거**: 채택했다면 (a) 오늘 동작하지 않고 (b) 내일 제거될 기능 위에 제품 주경로를 얹게 된다.
  pull 은 모든 MCP 클라이언트가 지원하는 tools 만 쓰므로 호환성 문제도 폐기 위험도 없다.
- **대가**: push 의 즉시성을 잃는다(폴링 지연). 그리고 개인 머신 AI 가 꺼져 있으면 답이 오지 않는다 —
  이는 sampling 을 썼어도 동일했을 문제다(클라이언트가 연결돼 있어야 push 도 성립).

## ADR-20260826T135207-gate-default-blocked — 차단을 코드 기본값으로 (설정이 아니라)

- **상태**: accepted
- **맥락**: "root/claude-corp 계정을 LLM으로 사용하는 부분을 모두 주석처리" 요구. 자연스러운 구현은
  `litellm_config.yaml` 과 `.env` 의 alias·변수를 주석 처리하는 것이다.
- **결정**: 설정 주석은 **두 번째 자물쇠**로 두고, **첫 번째이자 정본은 코드 게이트**
  (`shared/llm_gate.py`, 기본값 = 차단)로 한다.
- **근거**: `.env` 는 gitignore 대상이고 `config/` 는 배포에 포함되지 않는다(운영 실측 —
  `mysql-data-ops-deploy-live-verify` 계열 교훈). 설정이 정본이면 **"설정이 실리지 않은 환경에서
  잠금이 풀리는"** 뒤집힌 안전성이 생긴다. 잊으면 잠기는 쪽으로 실패해야 한다.
- **부수 효과**: 설정만 주석하면 호출이 401/404 로 지저분하게 죽는다. 게이트가 앞에 있으면 앱이 먼저
  **정직한 사유**를 내고 사용자에게 안내를 보여줄 수 있다.
- **되돌리기**: 두 자물쇠를 모두 풀어야 열린다(env 1개 + 주석 해제) — 의도된 이중화.

## ADR-20260826T135208-transition-contract-not-skip — 기존 alias 계약 테스트를 skip 하지 않고 이중 계약으로

- **상태**: accepted
- **맥락**: `test_llm_edge_free_routing` · `test_meta_llm_edge_free` ·
  `test_conversation_answer_no_edge_alias` 의 10개 테스트가 "계정 alias 체인이 존재하고 edge-free 다"
  를 잠근다(2026-07-30 라이브 장애 회귀 방어). alias 주석으로 전제가 사라져 전건 실패했다.
- **기각한 대안**: `pytest.skip` 으로 전환 환경에서 넘기기. 그러면 그 계약은 전환된 환경에서
  **영원히 검사되지 않고**, 되돌린 뒤 skip 조건을 잘못 건드리면 조용히 통과한다(vacuous pass —
  `test-env-override-skip-vacuous-pass` 계열 함정).
- **결정**: `_alias_transition.transition_contract_holds()` 로 **조건부 이중 계약**을 만든다.
  alias 활성이면 원 계약을, 비활성이면 대체 계약("활성 계정 라우팅이 정말로 0")을 단정한다.
- **효과**: 어느 상태에서든 무언가를 실제로 검사하고, 되돌리는 순간 원 방어가 자동 복원된다.
  누가 alias 만 주석하고 `fallbacks` 를 남기면 대체 계약이 잡는다.

## ADR-20260826T135209-no-install-client — 개인 머신 무설치 계약

- **상태**: accepted
- **맥락**: 사용자 결정(2026-08-26) — "개인 머신에서 서비스를 작동시키는 환경적인 제한이 최소화되어야
  합니다. 별도의 종속 패키지 설치없이, API를 통한 서비스 제공이 가능한 형태로."
- **결정**: 세 경로 모두 설치를 요구하지 않는다.
  1. **주 경로**: `https://<host>/api/ai/mcp` — HTTP/SSE MCP 를 서버가 호스팅하므로 클라이언트는 URL+토큰 등록만.
  2. **REST**: `/api/ai/*` — `curl` 만으로 전 구간 가능.
  3. **보조 러너**: `bridge_runner.py` 단일 파일, **표준 라이브러리만** import.
- **강제 방법**: `test_bridge_runner_stdlib.py` 가 **AST 로** import 를 전수 검사하고
  `sys.stdlib_module_names` 밖 모듈이 0건임을 단정한다. 문자열 스캔이 아니라 AST 인 이유는 주석·
  docstring 의 설명용 언급과 실제 import 를 구분하기 위해서다. allowlist 를 손으로 적지 않는 이유는
  새 import 추가 시 명단 갱신을 잊어 계약이 조용히 느슨해지는 것을 막기 위해서다.
- **기각**: feature-0041 의 stdio MCP 어댑터 재사용 — `pip install mcp` 가 필요해 계약 위반.
