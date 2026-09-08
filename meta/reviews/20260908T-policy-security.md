### 1. Blocking issues

(no findings)

PS-01~PS-04는 수정 후 재검토했다. 아래 범위와 한계에서 남은 차단 항목은 없다.

### 2. Cross-domain concerns

(no findings)

**PS-01 — 해결: conversation_audit 앞단의 재승인 분기 잔존**

- Evidence: 최초 검토에서는 새 Phase 8이 기존 승인을 인정해도 입력 `--unattended`가 Minor-only, 드레인 설명이 단계별 PR/deploy 게이트, 의사코드가 `consent_drain()`을 요구했다. Phase 7의 Major→human-decision/report-only 및 ledger 재검토 금지도 남아 있었다. 최종 텍스트에서 해당 분기가 현재 승인 범위 대조로 바뀌고 새 지시·승인·근거·정책 변화 시 재triage하도록 수정됐음을 확인했다.
- Location: `.claude/commands/_dqa/conversation_audit.md:46`, `:54`, `:63`, `:242`, `:246`, `:248`, `:249`; `.codex/commands/_dqa/conversation_audit.md`의 대응 구간.
- Reason: 명시 위임된 Major 작업도 구현 단계 전에 다시 멈출 수 있어 AC-2와 맞지 않았다. 이는 정책 문서의 실행 흐름 문제이며 제품 인증 코드 변경이 아니다.
- Action: 두 command의 입력·의사코드·triage·ledger와 실제 승인 판정을 정합화했다. 두 파일의 최종 바이트 동일성과 잔존 표현 부재를 확인했다.

**PS-02 — 해결: Claude submodule의 후속 Policy Prime Gate가 전체 재독을 되살리는 경로**

- Evidence: 고정 gitlink `43ed907d1e56139f8c9dc704719b3afdcc053017`의 `entry.md:568–596`는 존재하는 Phase 2 문서의 AI 판단 생략을 차단하고 전체 read-only rows를 재실행한다. 최초 소비자 override는 Phase 2 본문 전체 적재만 언급했다. 최종 `CLAUDE.md`는 Phase 6 gate에도 같은 §10.1 읽기 집합을 적용하고 `skipped-not-applicable`이 누락이 아님을 명시한다.
- Location: `CLAUDE.md:20–24`, `AGENTS.md` §10.1; 외부 `.claude/commands/_template/entry.md`의 Policy Prime Gate.
- Reason: 읽기 정책을 좁혀도 후속 검증이 옛 목록을 요구하면 AC-3가 닫히지 않는다. 외부 submodule을 직접 고치지 않고 소비자 정본의 적용 범위를 명시하는 해결이 적절하다.
- Action: gate까지 override하는 문구를 확인했다. 이 worktree의 submodule은 미초기화 상태이므로 원본 내용은 공유 main의 초기화된 submodule에서 읽고 HEAD가 gitlink와 같음을 확인했다. Claude 하네스에서 실제 새 세션을 실행한 검증은 아니다.

**PS-03 — 해결: DQA 정책 뒤의 브라우저 도구 강제 문구**

- Evidence: 새 §16.6 앞부분은 DQA 대상과 가용 도구를 기준으로 했으나, 같은 절 뒤에 `/browse` MCP 미사용 금지·host-side real-browser 필수·모든 UI의 스크린샷 필수가 남아 있었다. 최종 문구는 실제 연결 대상 및 존재/동작과 픽셀 변경의 증거를 구별한다.
- Location: `AGENTS.md` §15.4.1·16.1·16.2·16.6, `playbooks/PB-0009-dqa-client-verification.md` 실행 §1.
- Reason: 특정 도구 호출 방식 때문에 앱 검증이 거절되거나 일반 브라우저를 불필요하게 실행하는 경로였다. FUNCTION 전체 재독으로 오해될 문구도 해당 변경 절로 한정해야 새 읽기 병목이 생기지 않는다.
- Action: 도구 강제와 무조건 캡처 요구를 제거하고 PB-0009의 해당 절 읽기를 확인했다. 프로젝트 설정·CLAUDE·PB-0008/0009·wrapper 진입 문서가 같은 사용자 결정을 가리킨다.

**PS-04 — 해결: 서로 다른 Run의 결과 결합 및 DQA FAIL 은폐**

- Evidence: 처음에는 동일 fragment의 다른 환경 PASS를 DQA에 붙일 수 있었다. 이를 고친 다음에도 DQA PASS(모달 열기) 뒤 DQA FAIL(연결 동작)을 둔 실제 전체 gate의 격리 Bats fixture가 FAIL을 내지 않았다. 최종 parser는 Environment별 결과를 묶고 모든 fragment를 확인한다. 같은 파일의 명시적으로 동일한 Scenario 재검증만 최신 결과로 바꾸며, 다른 시나리오·미기재 Run·별도 파일의 실패/미실행은 보존한다.
- Location: `bin/verify-completion.sh`의 `visual_run_evidence_kind()`·`check_13_visual_verification()`; `bin/tests/agent_compatibility_gate.bats`의 CHECK13 회귀.
- Reason: 한 시나리오의 성공이 다른 미해결 사용자 흐름 실패를 덮어서는 안 된다. 현재 Run의 기록 검증과 실제 앱 실행의 진실성 판정도 구분해야 한다.
- Action: 수정 후 `bats --filter CHECK13 bin/tests/agent_compatibility_gate.bats`를 최종 스냅샷에서 독립 실행해 **20건 PASS**. 같은 파일/다른 fragment PASS 차용·DQA FAIL 은폐·미실행 은폐·과거 Run 재사용의 음성 대조와 native UI 5개 경로 귀속, 같은 Scenario의 FAIL→수정→PASS 및 PASS→FAIL을 포함한다.

**검토 범위와 수행한 확인**

- 기준: `76a76ddd` 대비 현재 변경 및 `meta/TASK.md`의 AC-1~5. 검토 대상은 AGENTS·CLAUDE·CONTRIBUTING·PROJECT·Codex CONTEXT/entry·양 conversation_audit와 CONTEXT 생성 소스다. 원본 개발 대화 근거는 `docs/improvements/delegation-friction-20260908/EVIDENCE.md`를 사용했다.
- Critical 보호: §7.1은 포괄 위탁만으로 위험 승인을 추론하지 않으며 §12의 인증/인가·파괴적 데이터·PII·외부 비용·보안 저하·어려운 롤백 보호를 유지한다. conversation_audit의 읽기 전용 대화 데이터·비밀 비노출·보안 가드 회귀 금지도 유지한다.
- 기존 승인: 현재 요청과 동일 세션의 실제 승인을 기록으로 연결하고 선택적 `PLAN-APPROVED` 마커 부재를 승인 부재로 오판하지 않게 한다. 신규 승인이나 Critical 승인을 만들어 내라는 규정은 없다.
- 재개 출처: §22.12의 현재 직접 사용자 `continue`와 과거 대화·도구 출력·board 게시물의 동일 문자열을 구별한다. 다른 세션을 임의 재개하거나 자동 예약을 새로 허용하지 않는다.
- 격리: §13.2.1의 자율 worktree 생성은 본인 위임 작업에 한정하며 공유 main 편집·다른 작업자 변경·공개 commit 재작성 권한을 확장하지 않는다.
- 생성기 정합: AST로 추출한 `bin/codex-environment-install.py`의 `CONTEXT`와 `.codex/CONTEXT.md`가 동일하다. 설치기의 기존 target Codex command 우선 순서가 consumer entry 보완을 덮어쓰지 않음을 읽기 검토했다. 설치·계정 설정 변경은 실행하지 않았다.
- 문서 구조: 추가된 § 참조에서 현행 AGENTS heading으로 해석되지 않는 항목 없음. 검토 문서의 코드 fence 균형과 지정 파일 `git diff --check` 확인. AGENTS 번호 heading 중복은 baseline `§22.3.1` 2개에서 현행 0개로 줄었으며 새 중복은 없다.
- 이 검토는 운영 DB·배포·실제 앱 사용자 흐름·cycle-finalize 전체 구현의 정확성을 검증하지 않는다. 인용된 보안 사고를 현재 런타임 변경으로 분류하거나 전체 보안 패널을 추가 요구하지 않았다.

**추가 사용자 결정에 따른 재검토 (2026-09-08)**

- DQA 사용 경로: 실제 Windows `DQAConnect.exe` PID 27660 및 직접 자식 WebView2, 같은 PID의 127.0.0.1:10513 LISTEN을 읽기 전용 조회했다. 설치 파일은 `C:\Users\mckim\AppData\Local\Programs\DQA Connect\DQAConnect.exe`다. `window.py`의 edgechromium 내장 창과 일치한다.
- 실측 한계: 당시 조회한 앱은 최소화됐고 WebView2 디버깅 포트가 없으며 UIAutomation 루트의 자식이 조회되지 않았다. 프로세스·포트 존재를 화면/연결 PASS로 보지 않는다. 앱 종료·재시작·창 복원·설치·실제 질의는 수행하지 않았다. 상세 미검증은 initiative REPORT에 별도 기록한다.
- 주 경로/보조 경로: `PROJECT.md`의 `primary_ui_surface: dqa-client`, PB-0009가 주 경로, PB-0008은 일반 브라우저 호환 경로다. 과거 Windows-browser 라벨의 실제 설치본 증거는 보존하되 새 실행으로 승격하지 않는다. 변경에 따라 화면·연결·창/트레이·업데이트 검증을 선택하며 문구 변경마다 재설치·AI 질의·별도 브라우저를 요구하지 않는다.
- wrapper 확인: `/root/download/docker/mysql_ai_delegated_dev/FIRST_REQUEST.md`의 DQA/PB-0009·§10.1·`deploy-web.sh --web-only` 참조를 읽었다. 실제 현재 SHA는 아래 표와 같고 `/tmp/delegation-wrapper-change.json`의 after와 일치한다. before SHA는 변경 기록에서만 읽었으며 원문을 독립 보존·대조한 검증은 아니다. wrapper 변경은 Git changeset 밖이다.
- 초기 좁은 코드 검토: 합류 전 `test_handoff_seam.py`·`test_web_shell.py` **92건 PASS**. 최종 source 차이와 재검증은 아래 ec913f94 합류 후 항목으로 대체한다. 실제 JS 핸들러를 Node VM에서 실행하며 네트워크·스킴 이동은 fixture로 격리되어 DQA 앱이나 유료 AI를 실행하지 않는다.
- DQA 분기 한계: 실제 모달 핸들러의 clientBridge 분기에서 실행 버튼 숨김·토큰 미발급·스킴 미이동을 검사한다. 별도 강제 autoLaunch fixture에서도 스킴 이동 0을 확인했다. 이는 현재 앱 프로세스의 OS 스킴 처리·인증·실제 연결 성공을 증명하지 않는다.
- gate 범위: 같은 changeset의 환경/결과 기록을 검증하고 앱 미실행/브라우저 보조는 WARN으로 남긴다. 기존 native window/appwindow/gui/tray/bridge는 감지하지만 신규 파일/installer 의미를 자동 추론하지 않는다. 사용자 흐름 완결성과 기록 진실성은 독립 리뷰 범위다. `bash -n bin/verify-completion.sh`, `git diff --check`, 양 command·생성 CONTEXT 정합을 재확인했다.

**origin/main ec913f94 합류 후 최종 코드 재검토**

- 기준: 원격 17개 commit 합류 중 해결된 지정 코드 및 PB-0009만 다시 읽었다. 전체 정책 재독·전체 런타임 보안 검토를 수행했다는 주장은 아니다. 병렬 문서 충돌 해결은 다른 검토자의 범위다.
- 보존: 원격의 `MSG_RELAUNCH_NO_UPDATE`와 트레이 `[업데이트 확인]` 안내는 그대로다. 원격 대비 제품 JS 변화는 autoLaunch 일반 실패의 삭제된 명령/`[연결 준비]` 참조를 실제 `[내 AI 실행]` 안내로 바꾼 한 곳과 관련 주석뿐이다.
- native 메뉴: 새 `_embedded_update_menu_labels()`는 실제 `_start_embedded_tray()`로 메뉴를 구성하고 `menu()`·`dispatch()`를 실행해 해당 항목의 enabled/action과 `_update_flow(bridge)` 워커 배선을 대조한다. Win32 시작 및 워커 실행은 stub으로 격리한다. 문자열 allowlist만 넓혀 트레이를 인정한 검사가 아니며, 실제 아이콘·업데이트 설치 PASS도 아니다.
- 실행 검증: 합류본의 `test_handoff_seam.py`, `test_web_shell.py`, 원격의 `test_relaunch_dead_end.py`를 함께 독립 실행해 **107건 PASS**(collect-only 107 확인). 원격 트레이 안내 계약·새 실패 안내·DQA 내부 미실행 대조를 함께 보존한다. check #13은 별도로 **20건 PASS**; `bash -n`과 지정 파일 `git diff --check`도 통과했다.
- 같은 Scenario의 실패 후 실제 성공을 마지막 Run으로 기록할 수 있어, 과거 실패 증거를 삭제해야 gate를 통과하는 병목을 피한다. PB-0009는 같은 파일/Environment/Scenario 반복 및 실패 원인·해소·재검증 증거를 요구한다. parser는 기록을 분류하며 그 증거의 진실성은 자동 판단하지 않는다.
- 마지막 정책 보완: §12.3·§16.6의 접근 획득은 자기 검증 인스턴스/승인된 운영 배포와 기존 사용자 앱 보존으로 한정한다. 일반 브라우저 세션 격리는 PB-0008을 사용할 때만 적용한다. 히스토리 검증은 변경 대상 클라이언트가 실제 노출하는 뒤로/앞으로 기능에 한정하며 새 기능이나 특정 `/browse` 도구를 요구하지 않는다. 측정 대상·상태·척도 일치 요구는 유지한다.
- 실제 사용자 DQA 클라이언트 검증은 여전히 **NOT-RUN**이다. 현재 실행 앱을 종료·재시작하거나 일반 브라우저로 대체해 PASS를 선언하지 않았다.

### 3. Challenge to current spec

(no findings)

현재 요청의 목표는 반복 마찰을 줄이는 것이다. 적용 규칙을 한 곳으로 모으고 실제 위험·현재 승인·대표 소비 경로를 기준으로 판단하는 방향은 대화 근거와 맞는다. 이번 수정에서 새 승인 마커 강제, 모든 문서 전체 재독, 과거 사고 키워드만을 근거로 한 리뷰 확대를 추가하지 않은 점을 확인했다.

§12.2 안의 과거 배포 기본값 설명처럼 명시적으로 superseded 처리된 기존 서술까지 모두 정리됐다는 결론은 내리지 않는다. 이번 범위에서 수정한 활성 entry·PROJECT·persona가 §16.5.1을 정본으로 참조하는 것을 확인한 판단이다.

### 4. Verdict

PASS — 지정 정책·security 정합과 추가 DQA 정책/check #13/JS 하네스 검토에서 남은 차단 항목 없음. PS-01~PS-04 수정 후 해당 경로를 재검토했다. 아래 새 SHA 범위의 판단이며 실제 DQA 앱 사용자 흐름 PASS, 전체 테스트 완료, 배포·랜딩 완료를 뜻하지 않는다.

초기 검토에서 PASS한 파일 내용 SHA-256(추가 DQA 변경 이전):

| 파일 | SHA-256 |
|---|---|
| `AGENTS.md` | `9bd9afea3898b5d1093725a5c41cc61defc98cb8b80fd35597ea27c27b9949d6` |
| `CLAUDE.md` | `503f11d8d3b02f07186159664f6123a2ac41decf9d9903d93f62555c01bd24fb` |
| `CONTRIBUTING.md` | `5d1c658bb4dfb71346500ce1fa9c45c85e1bb37b7f39dbd8dc973b56fc380005` |
| `docs/PROJECT.md` | `72db7e7baa692526a65db6b95a20fc645ed6a177e134b4229e3f4aee987b0ee2` |
| `.codex/CONTEXT.md` | `415cf7099c7c9b05cc7844341c7210780e4e5c1e91a0132f79f115530b02fc48` |
| `.codex/commands/_template/entry.md` | `c886fa8e5f87fe932283ce2e7dfb0b90c52f81bc9b8e91a72a62916d97fffe23` |
| `.claude/commands/_dqa/conversation_audit.md` | `381100c344e461e0580d85480c0050a635c0114ad0c76b3f4f8485d782d776ff` |
| `.codex/commands/_dqa/conversation_audit.md` | `381100c344e461e0580d85480c0050a635c0114ad0c76b3f4f8485d782d776ff` |
| `bin/codex-environment-install.py` | `d8f1596fc52c2a6e539246d86f7eab636a2c4c27f8a539d9ff46a7f8ef591524` |

추가 DQA 재검토 스냅샷 SHA-256(ec913f94 합류 전; 아래 코드 재검토 표가 해당 파일을 갱신):

| 파일 | SHA-256 |
|---|---|
| `AGENTS.md` | `c6d411c381d17fd39393b69ea8b72c3bd44a35baac6181b754af737980437862` |
| `CLAUDE.md` | `936382ee366d95c472326aeadae9c456d89f3273de39d04a6f6e4c63fb8d0bd6` |
| `CONTRIBUTING.md` | `5d1c658bb4dfb71346500ce1fa9c45c85e1bb37b7f39dbd8dc973b56fc380005` |
| `docs/PROJECT.md` | `b1ccf78ae451988cadee06ceada66419bde17f5573aca2498da46c356052ab92` |
| `.codex/CONTEXT.md` | `415cf7099c7c9b05cc7844341c7210780e4e5c1e91a0132f79f115530b02fc48` |
| `.codex/commands/_template/entry.md` | `c886fa8e5f87fe932283ce2e7dfb0b90c52f81bc9b8e91a72a62916d97fffe23` |
| `.claude/commands/_dqa/conversation_audit.md` | `381100c344e461e0580d85480c0050a635c0114ad0c76b3f4f8485d782d776ff` |
| `.codex/commands/_dqa/conversation_audit.md` | `381100c344e461e0580d85480c0050a635c0114ad0c76b3f4f8485d782d776ff` |
| `bin/codex-environment-install.py` | `d8f1596fc52c2a6e539246d86f7eab636a2c4c27f8a539d9ff46a7f8ef591524` |
| `docs/ARCHITECTURE.md` | `122258ad40d93a195dd99f2ef19d30b49abb9b27160a369e53970e564f5fe920` |
| `docs/DECISIONS.md` | `df164c8291f2d49c85ca2bfaed6134048ff295c4b03b187ba46b38dacbc495f0` |
| `meta/TASK.md` | `f5092050109f5731a331816dc17e9fae7f82f66857d3f930322c11696cdf7ff0` |
| `playbooks/PB-0008-windows-browser-verification.md` | `a46812b32cbb7ba7c47c678c76f89caed4af8acfd862a9f074f22ef1b51737d3` |
| `playbooks/PB-0009-dqa-client-verification.md` | `a9003884f35df64d6e6b7a28e237314429add344772e2be1b2b88e80291651aa` |
| `playbooks/README.md` | `bfd675dbad9aa2399e07afae1b0a1832060a009f268ba5353df13a56f62966f9` |
| `bin/verify-completion.sh` | `5ed09053fa1e1064e24c1d208e7e939143c03881793b000a5a8a321ddef315f7` |
| `bin/tests/agent_compatibility_gate.bats` | `0de956c26bad33e75da3f614705315d95644271d212a857ebccffa6cdaa50110` |
| `unit/feature-0046-native-client/tests/test_handoff_seam.py` | `829550474c50a2a145185b1a537e5dcd63db67935af11fca4b2bc376d8c9d991` |
| `unit/feature-0046-native-client/tests/test_web_shell.py` | `2a01fc23f44707697073f8d91e115688520bb2a137047d0460453c74640081d1` |
| `unit/feature-0003-agent-web-ui/src/static/app/connect-modal.js` | `ad1461789be9c10864a57a7cb0a1fe2652d0105d8c98ebec9c4a46498d72654d` |
| `/root/download/docker/mysql_ai_delegated_dev/FIRST_REQUEST.md` | `31fd755decf2ff1621c998998620072f12fa30b029a1ac8e08b438a6b7429764` |

ec913f94 합류 후 지정 코드·테스트·PB-0009 최종 재검토 SHA-256:

| 파일 | SHA-256 |
|---|---|
| `unit/feature-0003-agent-web-ui/src/static/app/connect-modal.js` | `aa1efc170ec450ae945cc411b9d4d0a24c097ee7c695cbe08b86e84a25b0b955` |
| `unit/feature-0046-native-client/tests/test_handoff_seam.py` | `ca12da70e3af5999086ecfc6c0939d8c1071e68a434d49dfc493ec65e52c3166` |
| `unit/feature-0046-native-client/tests/test_web_shell.py` | `2a01fc23f44707697073f8d91e115688520bb2a137047d0460453c74640081d1` |
| `unit/feature-0043-external-llm-bridge/tests/test_relaunch_dead_end.py` | `7f7b72f2f9e8222f1e63f14270ef87baa21102a6d17fc278c938e05bd4c1e0af` |
| `bin/verify-completion.sh` | `76ec622e6d5ca49d672c9556e0cc49738f1113bcee153373d666fc00c54aaa90` |
| `bin/tests/agent_compatibility_gate.bats` | `0e5aba8056947560f4a86fd7c6856b57e8ca67e3cac28f7ab5cd6cb4a77fa872` |
| `playbooks/PB-0009-dqa-client-verification.md` | `7fc2cc687570ac46454509e6c596f164024b43234f56209dc77ddd2d3ceb87a5` |

마지막 §12.3·§16.6 인접 문구 재검토 후 `AGENTS.md` SHA-256: `f80456d9b88a6303b5b394bed5ea350734dcc9c198a4332f4c15b7e568034b48`.
