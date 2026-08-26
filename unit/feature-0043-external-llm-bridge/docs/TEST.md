---
doc_type: TEST
feature_id: feature-0043-external-llm-bridge
status: active
edit_policy: mixed
source_of_truth: true
---

# Test

## 1. 테스트 전략

이 feature 가 방어해야 하는 것은 두 가지이고, 둘 다 "함수가 잘 동작한다" 로는 부족하다.

1. **차단이 기본값이고, 그 차단이 실제 호출 경로 위에 있다.** 게이트 함수만 검사하면 아무도 그것을
   부르지 않는 배선 끊김을 놓친다. 그래서 `_get_llm_client()` 가 `None` 을 반환할 때
   **게이트를 경유했다는 사실**까지 단정한다 — 자격증명 부재로 우연히 `None` 인 것과 구분되지 않으면
   vacuous pass 다. 역방향(게이트를 열면 차단 경로를 타지 않는다)도 함께 본다.
2. **무설치 계약이 코드로 강제된다.** 러너의 import 를 AST 로 전수 검사한다(문자열 스캔은 주석 속
   설명과 실제 import 를 구분하지 못한다).

## 2. 테스트 케이스

| ID | 대상 | 검증 | AC |
|---|---|---|---|
| TEST-20260826T135206-gate-default | `server_llm_enabled()` | env 부재 시 False. truthy 6종 True / non-truthy 6종 False | AC-1 |
| TEST-20260826T135206-gate-wiring-1 | `_get_llm_client()` | 계정 alias 14종 전건 `None` **+ 게이트 경유 단정** | AC-1 |
| TEST-20260826T135206-gate-wiring-2 | `_get_llm_client()` | 게이트 개방 시 차단 경로 미경유 (뮤테이션 역검증) | AC-1 |
| TEST-20260826T135206-gate-wiring-3 | `agent_core._run_agent_core` | 게이트 호출 + 사유 전달 + **클라이언트 생성부보다 앞** | AC-1 |
| TEST-20260826T135206-honest-fail | `note_server_llm_blocked()` | 로그 기록 · caller별 throttle · 사용자 문구에 내부 식별자 부재 | AC-8 |
| TEST-20260826T135206-config-lock | `litellm_config.yaml` | 활성 `ANTHROPIC_API_KEY` 참조 0 · 활성 chat alias 0 · YAML 유효 · 되돌리기 문서화 | AC-2 |
| TEST-20260826T135206-embedding-kept | `litellm_config.yaml` | `titan-embed` 활성 유지 (부수 피해 방지) | AC-7 |
| TEST-20260826T135206-runner-stdlib | `bridge_runner.py` | AST import 전수 → `sys.stdlib_module_names` 밖 0건 · `mcp` 부재 · TLS 검증 무력화 스위치 부재 | AC-9 |
| TEST-20260826T135206-alias-transition | 기존 alias 계약 3파일 | 전환 상태에서 대체 계약 단정, 되돌리면 원 계약 복원 | — |

## 3. Run 기록

Run 기록은 `docs/test-runs.d/` 의 항목당 1파일로 작성한다 (AGENTS.md §5.3 fragment 규약).
