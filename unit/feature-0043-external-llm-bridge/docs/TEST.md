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
| TEST-20260828T070000-cancel-single-source | `shared/bridge_tasks.py` · 두 라우터 | 취소 술어가 shared 에만 정의 · 라우터는 참조만 · 웹 라우터에 취소 SQL ≤1벌 | AC-59 |
| TEST-20260828T070000-cancel-two-branches | `cancel_bridge_tasks` | 미점유 DELETE / 점유 `canceled` · lease 판정 경유 · 계정 스코프 · 대상 미지정 시 no-op | AC-60 |
| TEST-20260828T070000-cancel-wiring | `cancel_request` | 브리지 취소 호출 + 말풍선 갱신 + **서버 run 취소보다 앞**(그쪽 실패가 이쪽을 삼키지 않게) | AC-58 |
| TEST-20260828T070000-cancel-failure-surfaced | `cancelCurrentRun` | `bridge_cancel_failed` 반영 + 감시 정리(`abandonBridgeTasks`) | AC-58 |
| TEST-20260828T070000-supersede | `_enqueue_web_bridge_task` | 이전 대기 대체 · `exclude_task_id` · **적재 성공 뒤** 실행 · 결과 전파 | AC-62 |
| TEST-20260828T070000-supersede-frontend | `handleBridgePending` | 대체 task 감시를 **새 폴러보다 먼저** 끊는다 | AC-62 |
| TEST-20260828T070000-cancel-channel | `wait_for_request` | 취소로도 즉시 반환 · `canceled_task_ids` · 점유자 스코프 · **명시 도구 7종 불변** | AC-63 |
| TEST-20260828T070000-submit-409 | `submit_answer` | 취소된 task 409 · 판정이 각인·저장 **앞** | AC-61 |
| TEST-20260828T070000-stream-counted | `bridge_stream` | `_counted_stream` 경유(배포 pre-drain 계량) · SSE 헤더 · 버퍼링 차단 | AC-64 |
| TEST-20260828T070000-stream-bounded | `bridge_stream` | 55초 서버 고정 상한 · `reconnect` 프레임 · 클라이언트가 대기시간 지정 불가 | AC-64 |
| TEST-20260828T070000-stream-auth-first | `bridge_stream` | 인증·소유 확인이 스트림 오픈 **앞**(그 뒤면 401/403 불가) · 계정 스코프 · 끊김 감지 | AC-64 |
| TEST-20260828T070000-stream-transient | `_bridge_stream_snapshot` | DB 장애를 '취소됨'(None)으로 오인하지 않는다 | AC-64 |
| TEST-20260828T070000-live-steps | `_bridge_live_steps` | 원장 출처 · `reason_text` 부재(지어내지 않음) · 진행도구 필터 공유 | AC-64 |
| TEST-20260828T070000-phase-order | `_bridge_phase` | `canceled` 가 `working` 보다 앞(아니면 취소가 영원히 '처리 중') · 5종 · 두 소비처 공용 | AC-64 |
| TEST-20260828T070000-stop-button | `renderComposer` · sendBtn 핸들러 | 브리지 대기 중 중단 버튼 노출 · 렌더와 클릭이 **같은 술어** | AC-58 |
| TEST-20260828T070000-no-send-block | `_bridgePendingHere` · `sendPrompt` | 브리지 대기를 in-flight 로 승격하지 않는다(대기 중 새 질문이 막히지 않게) | AC-58 |
| TEST-20260828T070000-runner-parallel | `bridge_agent.py` | 기본 동시 처리 · 세마포어 상한 · **자리 확보가 서버 질의보다 앞**(tight loop 방지) | AC-65 |
| TEST-20260828T070000-runner-cancel | `bridge_agent.py` | 취소 원장 락 보호 · `Popen`+kill · 실행 중·제출 직전 2회 확인 · 취소≠실패 구분 | AC-65 |
| TEST-20260828T070000-runner-claim-site | `handle_one` | 점유는 대기 루프에서(워커로 미루면 같은 task 반복 수신) | AC-65 |
| TEST-20260828T070000-runner-once | `main` | `--once` 가 워커 완료를 기다린다(daemon 스레드 조기 종료 방지) | AC-65 |
| TEST-20260828T070000-fallback | `_pollBridgeAnswer` | SSE 실패 시 폴링 폴백 · 두 경로가 같은 렌더·4xx 판정 | AC-64 |

| TEST-20260828T150000-hb-extends | `oauth_store.heartbeat` | 유효 토큰 → 연장 UPDATE 1회 · `LastHeartbeatAt` 기록 · 응답에 주기/수명 | AC-66 |
| TEST-20260828T150000-hb-no-resurrect | `oauth_store.heartbeat` | 로그아웃·세션만료·토큰폐기·토큰만료·refresh **5종 전건** UPDATE 미발행 | AC-66 |
| TEST-20260828T150000-hb-no-inversion | `oauth_store.heartbeat` | `GREATEST`(만료 앞당김 금지) · `LEAST(…, s.ExpiresAt)`(세션 초과 금지) · 대상 토큰 1행 | AC-66 |
| TEST-20260828T150000-hb-predicate | `account_is_heartbeating` | 살아있음 술어 + 최근성 동시 요구 · 창 경계 양측 · 계정 0 은 조회조차 안 함 | AC-67 |
| TEST-20260828T150000-hb-single-predicate | `oauth_store` | 두 판정이 `_LIVE_TOKEN_PREDICATE` 하나를 공유(복제본 금지) | AC-67 |
| TEST-20260828T150000-listening-2axis | `account_is_listening` | 하트비트 축이 원장보다 **먼저**(일하는 중 오판 방지) · 원장 폴백 유지 | AC-67 |
| TEST-20260828T150000-endpoint | `/api/ai/bridge_heartbeat` | 같은 토큰 해석기 경유 · 도구 목록 밖 · 원장 미기록 · 기록 실패가 연결을 끊지 않음 | AC-66 |
| TEST-20260828T150000-runner-thread | `start_heartbeat` | 가짜 Api 로 **실제 루프 구동** · 실패(0·401) 후 생존 · 주기 하한 · daemon · `main` 배선 | AC-68 |
| TEST-20260828T150000-session-slide | `web_context` | 활동 시 만료 슬라이딩 · 절대 상한 ≥ 무활동 창 · throttle 유지 · CreatedAt NULL 방어 | AC-69 |
| TEST-20260828T150000-shutdown | `shutdown_after_drain` · `ActiveTasks` | 유휴 즉시 종료 / 진행 중 대기 후 종료 / 유예 초과 시 취소 · 유예는 절대시각 · 401 배선 · 등록 경합 방지 | AC-70 |
| TEST-20260828T150000-schema | `_ensure_bridge_heartbeat_schema` | 컬럼 보장이 fast/slow 양 경로 · ALTER 실패가 catchup 을 세우지 않음 | AC-66 |
| TEST-20260828T170000-specs | `_RUNTIME_SPECS` | 새 플랫폼이 표 1항목으로 닫히는가 — label·argv·model·effort 키 전수 · 등급목록↔플래그 동반 | AC-71 |
| TEST-20260828T170000-detect | `detect_runtimes` | 설치된 것만 신고 · `--ai` 제한 · 오타는 제한 무시 · 모델 0개 런타임 제외 · ollama 실조회 | AC-71 |
| TEST-20260828T170000-report-loop | `start_heartbeat` | 능력을 **매번** 싣는다(루프 안) · `--cmd` 사용자는 신고 안 함 | AC-71 |
| TEST-20260828T170000-build-cmd | `build_cmd` | 런타임별 실제 인자 · 플래그가 프롬프트 **앞** · 등급 플래그 없는 런타임은 인자 미생성 | AC-72 |
| TEST-20260828T170000-reject | `build_cmd` (파라미터 11종) | 표 밖 값 거부 — 옵션 위장 · 셸 메타문자 · 경로순회 · 타 런타임 모델 · 구 서버 alias | AC-72 |
| TEST-20260828T170000-runtime-switch | `handle_one` | 서버 지정 런타임은 표 대조 + PATH 실재 확인 후에만 사용 | AC-72 |
| TEST-20260828T170000-sanitize | `_sanitize_runtimes` | 미신고(None)/빈신고([]) 구분 · 이름 문자집합 · 어긋난 항목만 폐기 · 라벨 1줄 · 개수 상한 · 정상 신고 무손상 | AC-73 |
| TEST-20260828T170000-caps-store | `set_runner_capabilities` · `account_runner_capabilities` | 값 변경 시에만 쓰기(NULL 분기 포함) · 술어가 하트비트와 동일 · 최근 1건 · 깨진 JSON 방어 | AC-73 |
| TEST-20260828T170000-catalog | `/api/api-vault/options` | 삼중 계약 — 신고없음 hidden / 신고있음 visible+`runtime:model`+런타임별 등급 / 조회실패 추측금지 / 게이트 해제 복원 | AC-74 |
| TEST-20260828T170000-persist | `_enqueue_web_bridge_task` · `_split_runtime_model` | 세 컬럼 적재 · 호출부 전달 · 런타임:모델 짝 가르기(접두 없으면 런타임 미생성) | AC-74 |
| TEST-20260828T170000-claim | `claim_request` | `requested` 3값 전달 · 출처가 요청시점 각인(`WebAiTasks`)인가 | AC-74 |
| TEST-20260828T170000-hydration | `_bridge_model_offered` | 복원이 지금 신고된 목록과 대조 · 조회 실패는 복원 안 함 | AC-74 |
| TEST-20260828T170000-composer | `composer.js` | 등급 목록이 신고 출처 · `model_selector_source` 명시값 판정 · 모델 변경 시 등급 재렌더 · 목록 내 폴백 | AC-75 |
| TEST-20260828T170000-copies | 러너 2사본 | 정본과 배포본 바이트 일치(사용자 sha256 대조가 성립하는가) | AC-71 |
| TEST-20260828T230000-optin | `detect_runtimes` | 질의는 **명시할 때만**(기본 off) — 켜지 않으면 AI 호출 0 | AC-76 |
| TEST-20260828T230000-lenient | `_extract_json`·`_coerce_options` | 코드펜스·머리말·맺음말·문자열배열·name/id 키·매핑 형태 7종 수용 | AC-76 |
| TEST-20260828T230000-shape | `_coerce_options` | 관대해도 모양은 본다 — 옵션 위장·공백·빈 값 거부 | AC-77 |
| TEST-20260828T230000-flagshape | `_coerce_flag` | 배열·문자열·`=`형 수용 · 치환자리 없음·공백 토큰 거부 8종 | AC-77 |
| TEST-20260828T230000-noleak | `detect_runtimes` | **플래그가 신고에 실리지 않는다**(키 4개만) — 신뢰 경계 | AC-77 |
| TEST-20260828T230000-cache | `save_conf`·`main` | 질의 결과 캐시 · 미질의 실행이 캐시를 지우지 않음 · `--refresh-caps` | AC-76 |
| TEST-20260828T230000-fallback | `detect_runtimes` | 질의 실패 시 내장 표 폴백(화면이 비지 않는다) | AC-76 |
| TEST-20260828T230000-unknown | `detect_runtimes`·`build_cmd` | 표 밖 CLI 질의(두 호출 형태) + 통한 형태로 실제 조립 | AC-78 |
| TEST-20260828T230000-probewins | `build_cmd` | AI 가 답한 플래그가 내장 표를 이긴다(codex `--model` vs 표 `-m`) | AC-78 |
| TEST-20260828T230000-timeout | `_CAPS_PROBE_TIMEOUT_SEC` | `float(env or N)` 함정으로 0 이 되지 않는다(실측 codex 112s) | AC-76 |
| TEST-20260828T230000-parallel | `detect_runtimes` | 여러 CLI 를 동시에 묻는다(순차면 응답시간의 합) | AC-76 |

| TEST-20260828T171500-strictmcp | `build_cmd` | claude 호출에 `--strict-mcp-config` 가 **실제로 실린다**(표가 아니라 조립 결과) | AC-20260828T171500-tool-permission-friction-1 |
| TEST-20260828T171500-flagpos | `build_cmd` | 모델·등급 선택 경로에서도 플래그가 프롬프트 **앞**에 남는다 | AC-20260828T171500-tool-permission-friction-1 |
| TEST-20260828T171500-noconfig | `build_cmd` | `--mcp-config` 미동반 — 배제가 교체로 바뀌지 않는다 | AC-20260828T171500-tool-permission-friction-1 |
| TEST-20260828T171500-nobypass | `_RUNTIME_SPECS` | 어떤 런타임에도 권한 우회 플래그가 없다(보안 계약 회귀 잠금) | AC-20260828T171500-tool-permission-friction-2 |
| TEST-20260828T171500-noask | `compose_prompt` | 승인 요구 금지 + **이유**(사용자가 승인 절차에 접근 불가) | AC-20260828T171500-tool-permission-friction-4 |
| TEST-20260828T171500-onfail | `compose_prompt` | 실패 시 대체 행동(실패 사실 기재 + 확인 범위까지 답) | AC-20260828T171500-tool-permission-friction-4 |
| TEST-20260828T171500-onecred | `compose_prompt` | 토큰 단일화 + 교차 계정 위험 고지 | AC-20260828T171500-tool-permission-friction-4 |
| TEST-20260828T171500-allpaths | `compose_prompt` | 첨부·이전대화·지침·scope 어느 조합에도 계약이 실린다 | AC-20260828T171500-tool-permission-friction-4 |

| TEST-20260828T171500-reopen | `_coerce_flag` | 학습 플래그로 MCP·권한·도구·샌드박스 축을 되열 수 없다(11종) | AC-20260828T171500-tool-permission-friction-3 |
| TEST-20260828T171500-legit | `_coerce_flag` | 정당한 모델·등급 플래그는 그대로 통과(codex `-c model_reasoning_effort=` 포함) | AC-20260828T171500-tool-permission-friction-3 |
| TEST-20260828T171500-customwarn | `_warn_custom_cmd_without_mcp_isolation` | `--cmd` claude 에 배제가 없으면 1회 경고 · 오발 없음 | AC-20260828T171500-tool-permission-friction-6 |
| TEST-20260828T171500-keepmcp | `_KEEP_MCP` | 탈출구 존재 + 기본값은 배제 | AC-20260828T171500-tool-permission-friction-6 |
| TEST-20260828T171500-annotate | `annotate_approval_request` | 라이브 원문 4종 감지 + 결재 도메인 정상 답변 무손상 | AC-20260828T171500-tool-permission-friction-5 |
| TEST-20260828T171500-wiring | `handle_one` | 감지가 제출 경로에 배선 · 제목 분리 **뒤** | AC-20260828T171500-tool-permission-friction-5 |
| TEST-20260828T171500-clicheck | `_ensure_strict_mcp_supported` | 확인 실패 시 플래그 유지(드러나는 실패 우선) | AC-20260828T171500-tool-permission-friction-7 |

## 3. Run 기록

Run 기록은 `docs/test-runs.d/` 의 항목당 1파일로 작성한다 (AGENTS.md §5.3 fragment 규약).
