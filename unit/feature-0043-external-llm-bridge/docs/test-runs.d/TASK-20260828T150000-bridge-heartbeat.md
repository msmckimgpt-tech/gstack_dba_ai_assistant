---
run_at: 2026-08-28T15:40:00+09:00
session: ai/claude/feature-0043-bridge-heartbeat
scope: 연결 지속(하트비트 · 토큰/세션 슬라이딩 · listening 2축) + 로그아웃 시 러너 자동 종료
verdict: PASS (컨테이너 단위 + 뮤테이션 9/9 KILL) / 잔여 — 배포 후 PB-0008 실화면 · 라이브 지속 실측
---

# Run — feature-0043 연결 지속 + 자동 종료

Environment: container (`make test` 하네스, `repo-unittest` 격리 프로젝트)

## 결과

| 스위트 | 결과 |
|---|---|
| `make test` 전체 (7 feature 스위트 + ruff) | **EXIT=0** (실패 0 · ruff All checks passed) |
| `unit/feature-0043-external-llm-bridge/tests` | **491 passed** (신규 `test_bridge_heartbeat.py` 38건 포함) |
| `test_route_parity_p5b` | golden 재생성 후 PASS — drift 는 신규 라우트 **1건**(`POST /api/ai/bridge_heartbeat`)뿐, 제거 0 |
| `bin/gen-routemap.py` | 재생성 (257 routes / 29 modules) |

## 뮤테이션 역검증 — 9종 전건 KILL

계약을 **실제로 깨서** 테스트가 잡는지 확인했다(적용 여부는 diff 로 검사 — no-op 치환은 자기충족).

| # | 뮤턴트 | 잡은 테스트 |
|---|---|---|
| M1 | `heartbeat` 가 resolver 를 건너뛴다(로그아웃 무시) | `hb-no-resurrect` **5건(동작)** + extends/targets/resolver |
| M2 | `GREATEST` 제거(만료 앞당김) | `hb-no-inversion` |
| M3 | `LEAST(…, s.ExpiresAt)` 제거(세션 초과 연장) | `hb-no-inversion` |
| M4 | `account_is_listening` 에서 하트비트 축 제거 | `listening-2axis` |
| M5 | 최근성 조건 없이 '대기 중' 판정 | `hb-predicate` |
| M6 | 401 에서 `shutdown_after_drain` 미호출 | `shutdown` (main 배선) |
| M7 | 진행 중 등록을 스레드 시작 뒤로(경합 창) | `shutdown` (등록 순서) |
| M8 | 유예 무시하고 즉시 취소 | `shutdown` (진행 중 대기) |
| M9 | 하트비트 스레드가 1회만 돈다 | `runner-thread` (실패 후 생존) |

**M1 이 소스검사에만 걸린 것이 아니다** — 파라미터화된 동작 테스트 5건(로그아웃·세션만료·토큰폐기·
토큰만료·refresh)이 함께 죽었다. 가짜 커서로 `heartbeat()` 를 실제 구동하기 때문이다.

## 하네스 고장을 실패로 승격 (1차 오판 기록)

1차 실행은 9종이 **전부 '생존'** 으로 나왔다. 원인은 코드가 아니라 하네스였다 — 컨테이너에
`pytest` 가 없어 출력이 `No module named pytest` 였고, "failed" 가 없으니 스크립트가 그것을
생존으로 읽었다. **신호 없음을 성공으로 읽는 판정은 언제나 이 방향으로 틀린다.**
`passed|failed` 어느 신호도 없으면 `HARNESS-BROKEN` 으로 크게 실패하도록 고친 뒤 재실행했다.

## 확인한 사실 (증거)

- 신규 라우트는 정확히 1건이고 제거된 라우트는 0건(골든 diff 로 확인) — 도구 표면 수는 불변이라
  P0-I 계약(가이드 열거·`capabilities`·수 대조)이 흔들리지 않는다.
- 러너 정본/배포본 sha256 일치(`test_served_runner_is_identical_to_canonical` + 자체 단정).
- 편집한 7개 파일 AST 구문 검증 통과.
- 러너 stdlib 전용 계약 유지 — 추가 import 없음(`threading`·`time`·`os` 는 기존).

## 미수행 (정직 표기)

- **PB-0008 실 Windows 브라우저 시각검증** — `visual_verification_scope: always` 대상이다
  (`static/agent/bridge_agent.py` 가 웹 자산 경로에 있고, `/ai/connect` 지시문 **문구가 바뀌었다**).
  이 문구가 화면에 실제로 도달했는지는 배포 후에만 확인할 수 있다 — 직전 cycle
  (TASK-20260828T120000)에서 "소스는 green 인데 화면에는 옛 문안" 이 정확히 이 형태로 드러났다.
- **지속성 라이브 실측** — 러너를 12시간 이상 띄워 두고 끊기지 않는지, 로그아웃 시 러너가
  스스로 종료하는지. 시간이 흘러야 관측되는 성질이라 단위 테스트로는 대체되지 않는다.
- **세션 슬라이딩의 절대 상한(90일)** — 경계 도달까지 90일이 필요해 라이브 관측 불가.
  SQL 이 상한을 계산하는지는 값으로 단정했다.
