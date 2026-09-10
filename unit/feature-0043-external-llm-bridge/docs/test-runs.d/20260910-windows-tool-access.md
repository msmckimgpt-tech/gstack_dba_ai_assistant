---
run_at: 2026-09-10T19:26:00+09:00
session: codex-01a08abe-186f-7561-a843-a15553b3d093
scope: [windows-native-codex, dqa-read-tools, ca, sessions]
verdict: code-pass-external-retry-pending
---

# TASK-20260910-windows-tool-access

- 신고 계정27/jgkim2, task t_GXzGR8J9ufgd3AaK, 대화20260910094426-1db05c23. 접수18:48:09/제출18:52:30 KST, codex/gpt-5.6-sol/high. 당시 Windows runner bca92fb72419, ai_ready1. 서버의 접수·제출은 성공했으나 답변은 CreateProcess blocked by policy로 HTTP 미실행을 알렸다. 클라이언트 원본 CLI 로그 미보유로 세부 정책 원인은 미확정.
- baseline native Windows Codex0.153.4 + 기존 read-only DQA host profile은 진단 표식 셸 실행 성공(16.47초). 이 개발 머신은 외부 PC와 같지 않으므로 정책 차단 재현으로 세지 않는다.
- 신규 회귀 최초 RED는 helper/인자 부재12건, 원격 정책 재현과 구분한다. 최종 최종 집중77 PASS, bridge+MCP2200개 수집/2199 PASS/1 skipped, exit0. PYTHONPATH를 Makefile과 동일하게 지정하고 루트 conftest의 DB/PG/스냅샷 격리를 적용했다. 최초 전체 collection은 oauth_store 경로 누락으로 실패했고 올바른 경로 설정 후 통과했다.
- ruff 변경 Python 및 git diff --check PASS. 잘못된 토큰과 cross-task 인가 회귀는 기존 MCP/REST suite 포함. 실제 타 계정 live 도구 호출은 수행하지 않았다.

Environment: Windows-native-Codex
Result: PASS
Scenario: 셸 도구 비활성 상태에서 실제 DQA HTTPS MCP 호출
Build: Codex0.153.4 / gpt-5.6-sol/low / 수정 runner
Evidence: compose_prompt→ask_local_ai→native codex.exe, features.shell_tool=false, required MCP. 진단용 무효 토큰으로 get_tool_catalog1회, HTTP401/유효하지 않거나 만료된 토큰 응답,17.76초. 정상 인증 조회 성공으로 세지 않는다.

Environment: DQA-client
Result: NOT-RUN
Scenario: jgkim2 외부 머신에서 원 FGT 요청 재실행
Reason: 해당 외부 PC의 WebView2·원본 CLI 로그에 직접 접근할 수 없다. 서버 task·runner heartbeat와 이 개발 머신의 native Codex 검증으로 구분했다. 관리 MCP deny와 외부 PC의 정상 FGT 결과는 미확인이다.

## 재현 도구

`tests/windows/verify_native_codex_mcp.py`를 native Windows Python으로 실행한다. --runner(빌드한 bridge_agent.py), --codex(실제 exe), --ca, --out, --base(DQA HTTPS)를 지정하면 무효 토큰401과 MCP event/셸 event 수를 검증한다. 토큰은 합성 고정값이며 실제 계정 토큰을 받지 않는다. 별도 --fixture-key/--fixture-cert는 CA가 발급한 SAN IP:127.0.0.1·CA:false 서버 인증서와 로컬 TLS 합성 도구로 정상 도구 결과 경로를 검사한다. 이 스크립트는 실제 AI 사용량을 소비하며 설치 DQA UI 검증을 대체하지 않는다.

## 출하

진행 중. 사용자 전역 정책에 따라 PR 생성은 별도 확인 후 수행한다. wrapper FIRST_REQUEST.md의 기존 deploy_scope included 범위로 web-only 배포한다. main/worktree AGENTS.md SHA256 21286d42d52a987af6bed233fb5c050b429ddfa77d33b4979fea3acb4a17fdef.

Environment: Windows-native-Codex-fixture
Result: PASS
Scenario: 셸 비활성 + 정상 TLS + catalog/read 왕복
Build: Codex0.153.4 / gpt-5.6-sol/low / 수정 runner
Evidence: 재현 스크립트로 실제 MCP event2(get_tool_catalog→run_read_tool), shell event0, 매번 생성하는 무작위 schema 표식이 답변에 도달,30.66초. 로컬 HTTPS 모의 서버의 모든 요청은 합성 토큰 일치. 실 DB 조회/외부 계정 확인과 구분한다.
Limit: 초기 모의 서버가 CA:true 루트 인증서를 서버 인증서로 사용해 Codex TLS 초기화가 거절됐다. 올바른 CA:false leaf로 수정 후 PASS. TLS 검증 우회나 Windows 인증서 저장소 변경 없음.

- 최종 CA 호환성: 기존 CA:false pinned cert 및 OpenSSL TRUSTED CERTIFICATE(목적 제약 포함)를 보존하며 private key 제외. 마지막 집중77 PASS(1.46초), 신규 CA-format 테스트 포함. [Codex 공식 CA 처리 소스](https://github.com/openai/codex/blob/main/codex-rs/http-client/src/custom_ca.rs)의 두 PEM label 계약과 대조했다.

## 최종 QA 확인 및 측정 정정

QA 3차에서 새 검증 도구가 model/effort kwargs로 명령을 재생성하여 shell_tool=false/ephemeral 인자를 잃는 high 결함을 발견했다. 앞선17.20초·15.92초 원격401 및23.72초 fixture는 셸 미사용만 입증한다. 이 결과를 셸 비활성화 근거로 쓰던 서술을 정정했다.

모델·추론 값을 argv에 직접 넣고 실제 _run_cli_cancelable 직전 두 인자를 단정하는 구조로 바꿨다. 제품 코드는 변경하지 않았다. 재실행은 fixture30.66초/MCP2/shell0와 remote17.76초/MCP1/shell0 모두 PASS, launch_flags_verified=true. 별도 수정확인1회(§18.8(a))에서 QA 최종 P1=0 PASS. artifacts/windows-tool-access-20260910/{fixture-verified-result,remote-verified-result}.json.
