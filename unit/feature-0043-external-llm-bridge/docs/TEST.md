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

| TEST-20260828T193000-blanks | `compose_launch_commands` | probe 명령에 `BRIDGE_PROBED_*` 빈칸이 **실재**한다(기본 명령에는 없다) | AC-20260828T193000-ai-assisted-setup-1 |
| TEST-20260828T193000-samescript | `compose_launch_commands` | 조사 경로와 기본 경로가 같은 스크립트를 부른다 | AC-20260828T193000-ai-assisted-setup-1 |
| TEST-20260828T193000-allowlist | `bridge_setup.sh` | `--cmd`·`--base`·`--token`·`--ca`·`--once`·`--check` 차단(통째로) | AC-20260828T193000-ai-assisted-setup-2 |
| TEST-20260828T193000-numeric | `bridge_setup.sh` | 축별 타입·범위(`.` · `1..2` · `999999999` · `1.5` 거부) | AC-20260828T193000-ai-assisted-setup-2 |
| TEST-20260828T193000-aiwhitelist | `bridge_setup.sh` | `rm`·`sh`·`curl` 등 PATH 실행 파일 거부, 알려진 CLI 만 | AC-20260828T193000-ai-assisted-setup-3 |
| TEST-20260828T193000-stderr | `bridge_setup.sh` | 거른 사실이 stderr 로 **도달**한다(명령치환에 안 먹힘) | AC-20260828T193000-ai-assisted-setup-4 |
| TEST-20260828T193000-realargv | `bridge_setup.sh` | `set --` 로 실제 argv 전개 검사(문자열 포함이 아니라) | AC-20260828T193000-ai-assisted-setup-2 |
| TEST-20260828T193000-humanwins | `bridge_setup.sh` | 사람 칸이 뒤에 와서 이긴다 · 사람 칸은 무검증 유지 | AC-20260828T193000-ai-assisted-setup-5 |
| TEST-20260828T193000-parity | `bridge_setup.{sh,ps1}` | 두 판이 같은 칸·같은 allowlist·같은 python 순서 | AC-20260828T193000-ai-assisted-setup-6 |
| TEST-20260828T193000-nodelegate | 지시문 | 대조·명령형태·판정 위임 금지 + `BRIDGE_ARGS` 선 긋기 | AC-20260828T193000-ai-assisted-setup-7 |
| TEST-20260828T193000-uihonest | `index.html`·`ai-connect.html` | "결과가 같다" 단정 없음 + 비결정성 고지 | AC-20260828T193000-ai-assisted-setup-8 |

| TEST-20260831T110000-partial | `probe_runtime_caps` | 축 하나가 비어도 **모델은 남는다**(부분 성공 ≠ 실패) + `effort_probed` 표지 | AC-20260831T110000-runtime-caps-restore-1 |
| TEST-20260831T110000-reask | `_settle_effort_axis` | 1차에서 빠진 축을 **좁게 다시 물어** 되살린다(실측 경로) | AC-20260831T110000-runtime-caps-restore-1 |
| TEST-20260831T110000-helpgate | `_settle_effort_axis` | 내장 표 짝은 **`--help` 로 실재 확인** 후에만 · 없으면 비움 · 못 읽으면 채택 안 함 | AC-20260831T110000-runtime-caps-restore-2 |
| TEST-20260831T110000-aiwins | `_settle_effort_axis` | AI 가 "지정 불가" 로 명확히 답하면 내장 표로 덮지 않는다 | AC-20260831T110000-runtime-caps-restore-2 |
| TEST-20260831T110000-boundary | `_help_mentions_flag` | `--effort` 가 `--effort-level` 에 부분일치하지 않는다 · None(모름) 과 False(없음) 구분 | AC-20260831T110000-runtime-caps-restore-2 |
| TEST-20260831T110000-unsettled | `_caps_axis_unsettled` | `effort: null` 이 뭉갠 두 사실을 가른다(구 캐시만 재확정) | AC-20260831T110000-runtime-caps-restore-3 |
| TEST-20260831T110000-reprobe | `detect_runtimes` | 미확정 캐시는 **축만** 재확정 · 새 결과가 캐시를 **이긴다** · 표지가 남는다 | AC-20260831T110000-runtime-caps-restore-3 |
| TEST-20260831T110000-marker | `sanitize_caps` | 확정 표지가 캐시 로드에서 살아남는다(매 기동 재질의 방지) | AC-20260831T110000-runtime-caps-restore-3 |
| TEST-20260831T110000-applied | `handle_one` | **반영된** 지정도 답변에 밝힌다 · 무지정에는 붙이지 않는다 · 제목 분리 뒤 | AC-20260831T110000-runtime-caps-restore-6 |
| TEST-20260831T110000-noalias | `/api/ask` 브리지 분기 | 무지정 요청이 **무지정으로** 적재된다(AST — 조건 반전까지) | AC-20260831T110000-runtime-caps-restore-4 |
| TEST-20260831T110000-explicit | `model_explicit` | 명시 판정이 **원본 요청 본문**을 본다(폴백된 값에서 파생되면 항상 참) | AC-20260831T110000-runtime-caps-restore-4 |
| TEST-20260831T110000-acctdef | `get_api_vault_options` | 계정 기본값이 시작점이 되되 **신고 목록 안일 때만** · 등급은 고른 모델의 런타임으로 대조 | AC-20260831T110000-runtime-caps-restore-5 |
| TEST-20260831T110000-defsafe | `get_api_vault_options` | 기본값 조회 실패가 **러너 목록을 비우지 않는다**(회귀로 발견) | AC-20260831T110000-runtime-caps-restore-5 |
| TEST-20260831T110000-axisonly | `set_account_bridge_defaults` | 한 축만 바꾼 요청이 다른 축 기본값을 지우지 않는다 | AC-20260831T110000-runtime-caps-restore-5 |

| TEST-20260831T170000-nofallback | `detect_runtimes` | 답한 적 없는 런타임은 **신고하지 않는다**(내장 모델 이름 폴백 제거) | AC-20260831T170000-model-tree-1 |
| TEST-20260831T170000-ollama | `detect_runtimes` | ollama 는 예외 — 실조회 결과라 그대로 신고 | AC-20260831T170000-model-tree-1 |
| TEST-20260831T170000-invoke | `build_cmd` | 모델 목록은 빼도 **호출법은 남아** 실행이 가능하다 | AC-20260831T170000-model-tree-2 |
| TEST-20260831T170000-retry | `detect_runtimes` | 표 안 CLI 도 한 번 더 묻는다 · 재시도가 deadline 을 넘기지 않는다 | AC-20260831T170000-model-tree-3 |
| TEST-20260831T170000-generation | `_RUNTIME_SPECS` | 표의 codex 모델이 실측 세대다(폐기 `gpt-5.1-*` 부재) | AC-20260831T170000-model-tree-1 |
| TEST-20260831T170000-tree | `_renderComposerModelMenu` | 플랫폼별 머리글 + 하위 항목 · 머리글은 버튼이 아니다 · 그룹 없으면 flat | AC-20260831T170000-model-tree-4 |
| TEST-20260831T170000-treecss | `chat.css` | 머리글이 항목과 시각적으로 구분된다(스타일 없는 클래스가 아니다) | AC-20260831T170000-model-tree-4 |
| TEST-20260831T170000-nonote | `handle_one` | 정상 답변 본문에 모델·등급을 쓰지 않는다 · **미반영 고지는 남는다** | AC-20260831T170000-model-tree-5 |

| TEST-20260831T183000-fingerprint | `_self_build` | 러너가 **자기 파일** 지문을 신고한다(파일이 바뀌면 지문도 바뀐다) | AC-20260831T183000-runner-version-sync-1 |
| TEST-20260831T183000-hbcarry | `Api.heartbeat` | 지문·버전을 **매번** 싣는다(두 축 모두) | AC-20260831T183000-runner-version-sync-1 |
| TEST-20260831T183000-once | `start_heartbeat` | 구버전 경고는 세션당 한 번 · 다음 행동까지 말한다 | AC-20260831T183000-runner-version-sync-2 |
| TEST-20260831T183000-compare | `_deployed_runner_build`·`_runner_update_hint` | 배포본과 대조 · **양쪽을 다 알 때만** 판정(미신고를 구버전으로 단정하지 않음) | AC-20260831T183000-runner-version-sync-2 |
| TEST-20260831T183000-status | `connect_status` | 프런트는 불리언 하나만 읽는다 · 듣고 있을 때만 판정 · 실패가 거짓 경고가 되지 않음 | AC-20260831T183000-runner-version-sync-2 |
| TEST-20260831T183000-chip | `connect-modal.js`·CSS | 칩이 정상과 **구분되는** 상태를 보인다 · 서버 값이 칩까지 배선됨 | AC-20260831T183000-runner-version-sync-3 |
| TEST-20260831T183000-recatalog | `app.js` 게이트 콜백 | 잠금이 풀리면 **카탈로그를 먼저 다시 받고** 그린다(순서 고정) | AC-20260831T183000-runner-version-sync-4 |

## 3. Run 기록

Run 기록은 `docs/test-runs.d/` 의 항목당 1파일로 작성한다 (AGENTS.md §5.3 fragment 규약).

| TEST-20260901T140000-cc-compose | `claimed_client_value` | 인스턴스를 새기되 **미신고 러너는 종전 값 그대로** · 잘릴 땐 인스턴스를 지킨다 | AC-20260901T140000-orphan-claim-reclaim-1 |
| TEST-20260901T140000-cc-sanitize | `claimed_client_value` | 영숫자 아닌 인스턴스는 무시 — `LIKE` 메타문자가 회수 범위를 넓히지 못한다 | AC-20260901T140000-orphan-claim-reclaim-1 |
| TEST-20260901T140000-release-scope | `release_runner_instance_claims` | 경계 = **점유자**(`ClaimedBy`) · `open` · 미제출 · 상태 불변 · 커밋됨 | AC-20260901T140000-orphan-claim-reclaim-2 |
| TEST-20260901T140000-release-noop | `release_runner_instance_claims` | 빈·무효 신고는 **SQL 을 한 줄도 쏘지 않는다**(빈 목록이 「전부」로 번역되지 않음) | AC-20260901T140000-orphan-claim-reclaim-2 |
| TEST-20260901T140000-release-nomatch | `release_runner_instance_claims` | 0건 매칭이면 UPDATE 를 건너뛴다(무조건절 사고 차단) | AC-20260901T140000-orphan-claim-reclaim-2 |
| TEST-20260901T140000-phase-fresh | `_bridge_phase` (실구동) | 진행 신호가 신선하면 `working` — 임계 직전까지 | AC-20260901T140000-orphan-claim-reclaim-3 |
| TEST-20260901T140000-phase-stalled | `_bridge_phase` (실구동) | 임계를 넘으면 `stalled` — 「가져갔다」와 「진행한다」를 가른다 | AC-20260901T140000-orphan-claim-reclaim-3 |
| TEST-20260901T140000-phase-unknown | `_bridge_phase` (실구동) | 판정 불가는 `working` 유지(관측 못 한 것을 「멈췄다」로 단정 안 함) | AC-20260901T140000-orphan-claim-reclaim-3 |
| TEST-20260901T140000-phase-terminal | `_bridge_phase` (실구동) | 종결(`canceled`·`expired`·`done`)이 무진행보다 앞선다 | AC-20260901T140000-orphan-claim-reclaim-3 |
| TEST-20260901T140000-threshold | `BRIDGE_NO_PROGRESS_SEC` | 임계가 **정상 무도구 최대치(621초) < x < lease(1800초)** 안에 있다 | AC-20260901T140000-orphan-claim-reclaim-3 |
| TEST-20260901T140000-wiring | `ai_tools.py` | 폴링·스트리밍 **두 호출부** 모두 판정 인자·후행 고지를 탄다(전송 방식이 화면을 바꾸지 않게) | AC-20260901T140000-orphan-claim-reclaim-4 |
| TEST-20260901T140000-cancel-prefix | `wait_for_request` | 취소 통보 대조가 **앞자리 비교** — 인스턴스가 붙어도 통보가 끊기지 않는다 | AC-20260901T140000-orphan-claim-reclaim-5 |
| TEST-20260901T140000-runner | `bridge_agent.py` | 발급·점유 각인·첫 신호 사망신고·종료 세 갈래(`atexit`+`SIGTERM`) 배선 | AC-20260901T140000-orphan-claim-reclaim-2 |
| TEST-20260901T140000-confkeep | `save_conf` | 설정 전체 재작성이 `runner_instance` 를 **이어 나른다**(잃으면 회수가 조용히 죽는다) | AC-20260901T140000-orphan-claim-reclaim-2 |
| TEST-20260901T140000-front | `_applyBridgePhase` | `stalled` 에 이력을 다시 읽고 **종결로 다루지 않는다**(러너가 켜지면 답이 온다) | AC-20260901T140000-orphan-claim-reclaim-4 |

| TEST-20260901T140000-pb0008 | 라이브 화면 (Windows-browser) | PRE-DEPLOY baseline — 배포본에 무진행 축 0건 · 제보 대화 말풍선 6건 실측 · 별건(인젝션 거부) 발견. 증적 `test-runs.d/TASK-20260901T140000-orphan-claim-reclaim.md` | AC-20260901T140000-orphan-claim-reclaim-4 |
