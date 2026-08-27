---
run_at: 2026-08-28T06:40:00+09:00
session: ai/claude/feature-0043-bridge-stream-interrupt
scope: 인터럽트 · 맥락 전환(supersede) · 진행 스트리밍(SSE) · 병렬 러너
verdict: PASS (단위·구조) / 잔여 — PB-0008 화면 시각검증 · 라이브 도달성 probe
---

# Run — 인터럽트 · 맥락 전환 · 진행 스트리밍 · 병렬

Environment: container (`make test` 하네스) + 로컬 pytest

## 결과

| 스위트 | 결과 |
|---|---|
| `unit/feature-0043-external-llm-bridge/tests` | **236 passed** (신규 `test_bridge_interrupt_stream.py` 25건 포함) |
| `unit/feature-0041-external-ai-tool-surface/tests` | **326 passed** |
| 컨테이너 `make test` (전체) | **exit 0** · 실패 0 |
| `ruff check` (참고용) | All checks passed |
| 편집 Python 3파일 · 러너 AST | 통과 |
| `composer.js` · `app.js` ESM `node --check` | 통과 |
| 러너 정본 ↔ 배포본 sha256 | 일치 (`b4b2d6c2…`) |
| 라우트 골든 재생성 | 255 → 256 (신규 `/api/ai/bridge_stream` **1건만**) |
| `bin/gen-routemap.py` | 재생성 (253 routes / 29 modules) |

## 이 Run 이 실제로 확인한 것 / 하지 않은 것

**확인함** — 배선·순서·경계가 소스에 존재한다. 이 feature 의 반복 결함이 "로직은 맞는데
연결이 끊긴" 형태였으므로(P0-E·P0-I), 단정 대상도 계산이 아니라 배선이다:

- 취소 술어가 `shared/bridge_tasks.py` **한 곳에만** 정의되고 두 라우터가 참조만 한다.
- `/api/cancel` 의 브리지 취소가 **서버 run 취소보다 앞**에 있다(뒤면 KV 실패가 삼킨다).
- supersede 가 **적재 성공 뒤**에 돈다(앞이면 적재 실패 시 이전 질문까지 잃는다).
- `submit_answer` 의 취소 판정이 **각인·저장 앞**에 있다(뒤면 취소된 답변을 보존한다).
- `bridge_stream` 의 인증이 **스트림 오픈 앞**에 있다(뒤면 401/403 을 못 돌려준다).
- `_bridge_phase` 에서 `canceled` 가 `working` 보다 앞이다(뒤면 취소가 영원히 '처리 중').
- 러너의 `slots.acquire()` 가 `wait_for_request` 앞이다(뒤면 tight loop).

**확인하지 않음** — 화면이 의도대로 움직이는지는 별개 주장이다:

- 대기 중 중단 버튼이 실제로 렌더되는지 (PB-0008)
- SSE 가 엣지(Caddy)를 지나 브라우저까지 도달하는지 — 다만 같은 조합(`_sse_pack` ·
  `_counted_stream` · `X-Accel-Buffering: no`)이 프롬프트 자동작성에서 이미 프로덕션 동작 중이다.
- 55초 상한 후 재접속이 끊김 없이 이어지는지
- 러너의 병렬·취소가 실제 AI 런타임에서 동작하는지 (개인 머신 필요)

## PB-0008 — 브리지가 살아났다 (근본원인 수정)

Environment: Windows-browser (실 Windows Chrome/151.0.7922.170 · CDP relay)

이전 cycle 들이 PB-0008 을 "브리지 setup 불가" 로 기록해 온 **근본원인을 찾아 고쳤다.**

`bin/win-browser.py` 의 `win_host_ip()` 가 `/etc/resolv.conf` 의 **첫 nameserver** 를 그대로
Windows host 로 썼다. WSL 이 resolv.conf 를 자동 생성하는 기본 구성에서는 그 값이 곧 Windows
host 라 잘 맞았지만, 이 머신은 공용 DNS(`8.8.8.8`)를 직접 넣어 두었다 → **`8.8.8.8` 을
Windows host 로 오판**.

증상이 고약했던 이유: relay 는 `"relay started (8.8.8.8:9223 -> 127.0.0.1:9222)"` 라고
**성공을 보고**하고 CDP 연결만 조용히 실패했다(`bridge_unreachable`). 성공 로그가 원인을 가렸다.

수정: 기본 게이트웨이(`ip route show default`)를 **먼저** 보고, **사설 IP 만** 받는다.
공용 IP 를 돌려주느니 `None` 으로 정직하게 실패하는 편이 낫다 — `None` 은 "못 찾았다" 지만
공용 IP 는 *성공한 것처럼 보이는 relay* 를 만든다. `WIN_BROWSER_HOST` 탈출구도 추가.

```
$ python3 bin/win-browser.py doctor
{"ok": true, "win_host": "172.26.144.1", "bridge_mode": "relay",
 "endpoint": "http://172.26.144.1:9223", "cdp_version": "Chrome/151.0.7922.170", "issues": []}

$ python3 bin/win-browser.py launch --url https://mysql-ai.company.local/
{"ok": true, "navigated": {"status": 200, "title": "DQA — Database Query Assistant"}}
```

증적: `artifacts/pb0008-20260828/live-before.png` (배포 전 라이브 화면 = 비교 기준선)

## 이번 화면 변경의 검증 상태 — **post-deploy 수행**

| 항목 | 상태 |
|---|---|
| 브리지 동작 | **PASS** — 위 실측 |
| 라이브 화면 도달 | **PASS** — 200 · 정상 title |
| 이번 cycle 의 UI 변경 | **미검증** — 아래 |

이번 cycle 이 바꾼 화면(중단 버튼 노출 · 취소 말풍선 · 진행 단계 표시 · SSE 재접속)은
**이 브랜치에만 있고 라이브에는 없다.** 배포 전에는 관측할 대상 자체가 존재하지 않는다.

`deploy_scope: included` 이므로 순서는 TASK.md §5 Next Action 이 정한 그대로다 —
**머지 → 배포 → POST-DEPLOY PB-0008**. 배포 직후 다음을 수행하고 이 fragment 를 갱신한다:

1. 전용 새 대화에서 질문 전송 → 대기 말풍선 + **중단 버튼 노출** 확인
2. 중단 클릭 → 말풍선이 취소 안내로 변경 → **새로고침 후에도 유지** 확인
3. 재전송(대기 중 새 질문) → 이전 말풍선이 '대체됨' 으로 변경 확인
4. 개인 AI 연결 상태에서 점유 → **조사 단계가 답변 전에** 표시되는지 확인
5. 55초 경과 후 SSE 재접속이 끊김 없이 이어지는지 (`/livez` 의 `active_streams` 복귀 확인)

**이번에는 "브리지 불가" 가 사유가 아니다** — 브리지는 동작한다. 사유는 오직 "대상 코드가
아직 라이브에 없다" 이고, 그것은 배포로 해소된다.

## 마찰 기록 — 계약이 검사 범위 밖으로 나간다

기존 계약 테스트 **8건**이 이번 리팩터링에 무더기로 깨졌다. 계약 자체는 전부 살아 있었고,
**검사 범위 밖으로 나간** 것이었다:

| 방식 | 깨진 이유 |
|---|---|
| `text[i:i+2500]` 고정 윈도 2건 | 함수가 분해되자 계약이 윈도 밖으로 나감 |
| `_func_source(...)` 안의 문자열 4건 | 판정이 상위 헬퍼로 올라감(`_bridge_phase` 등) |
| `"timed_out": True` 상수 단정 1건 | 상수가 조건(`not canceled`)이 됨 |
| `capture_output=True` 1건 | 취소 kill 을 위해 `Popen`+PIPE 로 바뀜 |

**더 나쁜 방향은 조용한 쪽이다.** 범위가 좁아져도 green 이면 아무도 모른다. 실제로 이번에
새로 쓴 `_js_func` 헬퍼가 파라미터 구조분해의 `{` 를 본문으로 오인해 함수를 한 줄로 자를 뻔했고
(계약 미검사인데 통과), 다른 단정이 먼저 실패해서 드러났다. 경계는 **문법으로** 잡는다.

갱신한 계약은 전부 **약화가 아니라 강화**다 — 예: 국면 판정 테스트는 이제 두 소비처
(폴링·스트리밍)가 같은 함수를 쓰는지까지 본다.
