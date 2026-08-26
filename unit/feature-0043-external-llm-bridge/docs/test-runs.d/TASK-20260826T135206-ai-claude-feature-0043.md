---
run_at: 2026-08-26T14:20:00+09:00
session: ai/claude/feature-0043-external-llm-bridge
scope: Step A(게이트·설정 자물쇠) · Step B 백엔드(스키마·도구 2종·ask 분기) · Step C(러너)
verdict: PASS (단위) / 잔여 — 프론트·PB-0008·도달성 probe 미수행
---

# Run — feature-0043 Step A·B·C 단위 검증

Environment: container (`make test` 하네스) + 로컬 pytest (게이트·러너 스위트)

## 결과

| 스위트 | 결과 | 비고 |
|---|---|---|
| `unit/feature-0043-external-llm-bridge/tests` | **29 passed** | 게이트 24 · 러너 5 |
| `test_llm_edge_free_routing` + `test_meta_llm_edge_free` + `test_conversation_answer_no_edge_alias` | **31 passed** | 전환 분기 가드 적용 후 |
| `unit/feature-0002-agent-core/tests` | 신규 실패 0 | `test_scratch.py` 6 + `test_attachment_delivery_tool.py` 2 는 **main 에서도 동일 실패**하는 환경성 baseline (로컬 pytest 의 `No module named 'app'` 계열) |
| 컨테이너 `make test` (1차) | 1 failed | `test_route_parity_p5b::test_route_table_matches_golden_snapshot` — 신규 라우트 2건으로 인한 **의도된 drift**. golden 을 컨테이너 하네스에서 재생성(249→252 routes) |

## 확인한 사실 (증거)

- `litellm_config.yaml`: 활성 `os.environ/ANTHROPIC_API_KEY` 참조 **0건**, 활성 `model_list` = `titan-embed` **1건**, YAML 파싱 정상.
- `_get_llm_client()`: 계정 alias 14종 전건 `None` + **게이트 경유 단정**(`note_server_llm_blocked` 호출 확인).
- 역검증: 게이트를 열면(`AGENT_SERVER_LLM_ENABLED=1`) 차단 경로를 타지 않는다 — 위 결과가 게이트를 실제로 측정했음을 보인다.
- `agent_core._run_agent_core`: 게이트 호출이 `client = OpenAI(` **앞**에 위치(소스 인덱스 비교).
- `bridge_runner.py`: AST import 전수 → `sys.stdlib_module_names` 밖 **0건**.
- 편집한 7개 파일 AST 구문 검증 통과.
- `bin/gen-routemap.py` 재생성 완료 (249 routes / 29 modules).

## 미수행 (정직 표기)

- **PB-0008 실 Windows 브라우저 시각검증** — 프론트 대기/폴링 구현과 함께 수행해야 의미가 있어 미착수.
  `visual_verification_scope: always` 이므로 웹 자산 변경 시 필수이며, 현 cycle 은 아직 웹 자산(static)을 수정하지 않았다.
- **`reachability_scope: included` 도달성 1-probe** — 웹 질문 → 개인 AI 처리 → 답변 렌더 end-to-end.
  컴포넌트 health 로 갈음하지 않는다.
