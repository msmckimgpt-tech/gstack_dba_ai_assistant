---
run_at: 2026-09-08T14:20:00+09:00
session: claude ai/claude/feature-0003-step-tool-syntax-leak
scope: 실행 단계 패널 — 도구 호출 표기 노출 제거 (제목 + 배지 + 사유)
verdict: PASS
---

# Run — TASK-20260908T125500-step-tool-syntax-leak

대상 revision: base `d81325ff` (origin/main) + 본 cycle 변경.

## Run — DQA 클라이언트 실측 (PB-0009)

Environment: DQA-client
Result: NOT-RUN
Scenario: 실행 단계 패널을 열어 `search_tables`·`describe_table` 단계의 배지와 제목이 각각
「테이블 찾기」·「테이블 구조」와 한국어 파생 문구(백틱 없이)로 보이는지 확인
Build: DQAConnect.exe (실행 중, PID 24840) + 서버 web-a/b `1bddbfc1` (배포 전)
Evidence: 실행 확인 `tasklist.exe` — `DQAConnect.exe` 1 · `msedgewebview2.exe` 6.
`Win32Process.CommandLine` 실측: WebView2 인자에 `--remote-debugging-port` **없음**
(`--user-data-dir="C:\Users\...\.dqa-connect\window\EBWebView" --embedded-browser-webview=1`).
`NETSTAT -ano` 로 DQAConnect.exe(24840)가 여는 유일한 리스너는 `127.0.0.1:63817` 이며,
`/json/version` 프로브가 **405** 를 반환해 CDP 엔드포인트가 아니라 로컬 브리지 HTTP 임을 확인.
Reason: 현재 DQA 앱은 자기 WebView2 에 디버깅 포트를 열지 않아 앱 DOM 조작 경로가 없다.
PB-0009 3번 항목에 따라 포트를 추정하거나 일반 브라우저에 붙어 DQA 검증이라고 보고하지 않으며,
검증 편의로 사용자가 쓰고 있는 앱을 종료·재실행하지 않는다.
Alternative: 아래 「라이브 원장 전건 재생」이 **클라이언트가 실제로 받는 문자열**을 9,759행에
대해 측정하고(클라이언트는 그 값을 `textContent` 로 그린다), 「배지·제목 행위 하네스」가 배포되는
`app.js` 의 실제 함수를 실행해 배지·제목·백틱 제거를 확인한다.
Next: 서버 배포 후 같은 Scenario 로 재검증한다(같은 파일에 Run 추가). 앱에 디버깅 경로가
없으므로 배지·제목은 **사람 관찰 + 캡처**로 확인하고, 그 전까지 이 항목은 PASS 가 아니다.

## Run — 라이브 원장 전건 재생 (9,759행, before/after)

Environment: CLI
Result: PASS
Scenario: 라이브 `agent_runtime.steps` **전 행**을 새 표시 이음매(`_step_display_narration`)에
통과시켜 ① 버려지는 정상 문구 ② 잔존 유출 ③ 사유 손실을 센다
Evidence:

```
TOTAL_ROWS=9759
DROPPED_WORK=19       (인자 매핑 리터럴 14 + 도구 이름 언급 5)
DROPPED_REASON=0
LEAKED_AFTER=0
DROPPED by work_source: {'external-ai': 18, 'llm': 1}
```

대표 변환(모두 `work_source=derived`):

```
search_tables {'keyword': 'masangsoft_eos_token'}                      → `masangsoft_eos_token` 관련 테이블을 찾는다
describe_table {'schema_name': 'coupon', 'table_name': 'dbo.T_COUPON'} → `coupon`.`dbo.T_COUPON` 구조를 확인한다
search_tables가 보고한 정확 대소문자(GamePlay)로 테이블 접근 테스트      → `log_v2.TF_Log_02_GamePlay` 데이터를 집계한다
```

**초판 대비**: 같은 재생에서 초판 규칙은 **412행**을 버렸고 그중 정상 제목이 **394행(96%)**
이었다. 규칙 (c) 폐기 후 버려지는 행은 19건이며, 그중 14건은 인자 매핑 리터럴을 담은
명백한 도구 표기이고 5건은 도구 이름을 문장 안에 담은 것이다(마지막 예시가 그 형태 —
§16.8 B-2(a) 상 이름 자체가 노출 대상이라 버리고 파생으로 대체하는 것이 의도한 동작이다).
Limit: 읽기 전용 SELECT 만 수행했고 라이브 데이터를 바꾸지 않았다. 이 재생은 **표시 산출**을
측정한 것이며, 실제 브라우저 렌더(배지 폭·줄바꿈)는 위 DQA-client Run 의 범위다.

## Run — 배지·제목 행위 하네스 (프런트)

Environment: Node-vm
Result: PASS
Scenario: 배포되는 `src/static/app.js` 의 `toolLabel`/`stepTitleText` 를 실제로 실행해
알려진 도구의 한국어 라벨, 미지 도구의 식별자 비노출, 제목 폴백의 식별자 비노출,
마크다운 백틱 제거, 인자 리터럴 심층 방어를 확인
Evidence: `node tests/verify_step_title_no_tool_syntax.mjs` → **15항목 전건 PASS (rc=0)**.
음성 대조군 — 이번에 없앤 두 폴백(배지의 식별자 반환 · 제목의 intent/tool 폴백)을 주입한
사본에 같은 하네스를 태워 **8 FAIL (rc=1)** 실증.
Wiring: `test_l8_behaviour_harness_runs` 가 pytest 에서 이 하네스를 호출한다. `make test` 는
node 가 없으면 **설치한다**(`Makefile` 의 `apt-get install -y nodejs` + `node --version || exit 1`)
— 따라서 CI 에서 실제로 실행되며, node 부재는 skip 이 아니라 **실패**로 처리한다 (§16.7 G15-b).
Limit: DOM 을 거치지 않는 순수 함수 실행이다. 실제 패널 렌더는 위 DQA-client Run 의 범위다.

## Run — 단위·정적 검증

Environment: CLI
Result: PASS
Scenario: `make test` 와 동일한 pytest 집합 + ruff
Evidence: 신규 `tests/test_step_tool_syntax_leak.py` **55건 PASS**(적대 인자 벡터 · census 전
도구 × 저장문구 3형태의 진행/완료 동치 · 전각·제로폭 우회 · 결함 주입 대조군 4종 포함).
전체 집합(`make test` 와 동일 경로 + node 설치)은 **선재 실패 7건**을 포함하는데,
`origin/main`(`d81325ff`) **원본 트리에 같은 명령을 돌려 같은 7건이 동일하게 실패**함을
확인했다 — 본 cycle 대비 **차집합 0**(회귀 아님). 해당 7건은
`test_share_redaction_invariant.py` 이며 단독 실행 시에는 통과한다(전 집합 실행에서만 나는
테스트 오염이고 main 에 이미 있다). node 없이 돌리면 `feature-0046` 12건이 추가로 실패하는데
`make test` 는 node 를 설치하므로 CI 조건에서는 나타나지 않는다.
ruff `All checks passed!`.
Limit: 이 워크트리에 jsdom 이 있으면 `test_side_panel_exclusive::test_s6` 가 행위 하네스를
실행해 **선재 실패 2건**(프로필 open C3)을 낸다 — `git show HEAD:` 로 main 판 자산을 되돌려도
같은 결과라 이 cycle 의 회귀가 아니다. `make test` 컨테이너에는 jsdom 이 없어 그 테스트는
문서 gap 경로를 타므로 위 7건 목록에 나타나지 않는다.

## Run — 최신 main 흡수 후 재검증

Environment: CLI
Result: PASS
Scenario: `origin/main` **46커밋**(cdd414e3)을 병합한 뒤 같은 시험 집합을 재실행
Evidence: **8,267건 / 실패 2 / errors 0 / skipped 17**. 실패 2건은
`test_route_parity_p5b::test_route_table_matches_golden_snapshot`(route 269→271)과
`test_bridge_interrupt_stream::test_cancel_channel_adds_no_new_tool`(명시 도구 라우트 7→8)이며,
**pristine `origin/main`(cdd414e3) 원본 트리에서 같은 2건이 동일하게 실패**함을 확인했다 —
다른 세션이 라우트를 추가하며 골든 스냅샷·개수 단언을 갱신하지 않은 선재 결함이고 본 cycle 대비
**차집합 0**이다. 병합 전 본 브랜치 단독 실행은 8,143건 **전량 PASS** 였다. ruff clean.
§16.4 해결 결과 검증(MUST): 충돌 3건(FUNCTION·REPORT·TASK, 전부 «양쪽 말미 append»)을 양측
보존으로 해소한 뒤 **양쪽 부모 대비 유실 파일 0건**(`--diff-filter=D` 각각 0), 이 cycle 의 핵심
심볼 6종 생존, main 이 추가한 신규 파일 153건 생존, main 고유 변경분 대표 3파일 병합본 == main.

## 적대 검증 (§18.8)

Environment: CLI
Result: PASS
Scenario: subagent 패널 4(backend·security·qa·ux-design) + codex 경량 채널, 라운드 2회
Evidence: **라운드 1 — 4명 전원 BLOCK** + codex P1·P2. 뿌리는 하나였다: 초판 판정기의 「선두
식별자」 규칙이 라이브에서 오탐 96%(412행 중 394행). 설계를 census 기반으로 재작성하고 단일
표시 이음매를 도입했다.
**라운드 2(확인 라운드) — backend·security CONCERN / qa·ux BLOCK.** 라운드 1 P1 은 10건 중
9건 CLOSED, `intent` 1건이 PARTIAL 이었다. 라운드 2 가 **내 수정이 만든 신규 결함 2건**을
잡았다: ① 「렌더러 전수」를 선언한 가드의 모수가 `app.js` 한 파일이라 `app/progress.js` 회귀가
무증상 통과 ② 폴백 제목이 라벨을 되풀이해 「테이블 구조 · 테이블 구조 단계」. 그 밖에 census
폴백 무조건 합산(테스트가 실패할 수 없게 됨) · 사유 파생의 정직성 · `_code_only` 의 꼬리/블록
주석 미제거 · scratch 문구의 인자 무시 · 활동 툴팁 백틱 · 라벨 어휘 2종을 함께 닫았다.
§18.8 수렴 계약 (a) 대로 **수정한 라운드는 종결 근거가 아니다** — 라운드 3 확인이 남아 있다.
원장은 `docs/REVIEW.md` REV-20260908T131500-* / REV-20260908T142000-*.

## 미검증·한계 (숨기지 않는다)

- **DQA 앱 화면 실측 미수행** — 위 사유(디버깅 포트 부재). 배포 후 재검증 전까지 「사용자
  화면에서 확인했다」로 보고하지 않는다.
- **배지 폭은 headless Chromium 실렌더로 측정했다**(라운드 2 재측정) — 340px 에서 30종 전건
  헤더 1행, 300px + 최장 시각 문구에서는 예외 2종(`describe_routine`·`search_routines`, 각
  74.8px)만 시각 요소가 2행이고 비예외 최대 65.3px 는 전건 1행이다. 그 2종은 어휘를 훼손하지
  않기 위해 예산을 넘긴 채 두었다(`_LABEL_BUDGET_EXEMPT` + 사유 등재). 배지 자체는
  `white-space:nowrap` 이라 접히지 않는다. ⚠ `_LABEL_BUDGET = 6` 은 **글자 수**이지 폭이 아니다
  — 「SQL 실행」(59.8px)과 「테이블 목록」(65.3px)이 같은 6자다. 다음 라벨 작성자를 오도하지
  않도록 실 폭 가드로의 승격을 후속으로 남긴다.
- **도구 이름을 문장 안에 담은 정상 제목 5건도 버려진다** — 대체는 파생 문구다. 이름 자체가
  노출 대상이라는 판단(§16.8 B-2(a))에 따른 의도한 교환이며, 손실이 아니라 치환이다.
