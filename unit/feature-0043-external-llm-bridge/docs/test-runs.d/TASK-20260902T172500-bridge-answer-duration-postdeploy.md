---
run_at: 2026-09-02T18:05:00+09:00
session: ai/claude/feature-0043-duration-postdeploy
scope: 총 수행시간 각인 POST-DEPLOY 실측 (배포 ec649a6e) + 라이브에서 드러난 표시 중복 제거
verdict: PASS (라이브 end-to-end 확인 — 실 답변 2건 각인, 원장 시각과 일치)
---

# Run — 총 수행시간 각인 POST-DEPLOY 실측 (배포 `ec649a6e`)

Environment: 라이브(`https://localhost` · web-a/web-b · 사용자 머신 브리지 러너 연결 상태) +
container pytest

## 배포 검증

| 축 | 결과 |
|---|---|
| 서비스별 이미지 SHA | `web-a`·`web-b`·`ask-worker`·`insight-worker`·`ext-tool-mcp-a/b` 전부 **`ec649a6e`** |
| `no upstreams available` (15분) | **0건** |
| surge 잔존 | **0** |
| `/healthz` | **200** |
| 대화 경로 스모크 | PASS (전환 모드 — 서버 LLM 차단 확인) |
| 서빙 컨테이너 심볼 | `/app/web/routers/ai_tools.py` 에 신규 심볼 **5 hits** |

## 라이브 end-to-end — 실 답변 2건이 각인됐다

배포 후 사용자 머신 러너가 제출한 **실제 대화 답변**이다(합성 아님):

| 메시지 | task | 각인 `duration_ms` | `duration_breakdown` |
|---|---|---|---|
| 2623 (17:51:39) | `t_ljISMyrEYAKLRjEm` | 140000.0 | `{total:140000, queued:40000, inference:100000}` |
| 2621 (17:50:30) | `t_53RRgSSv6nhfJVsf` | 36000.0 | `{total:36000, queued:0, inference:36000}` |
| 2619 (17:12:44, 배포 전) | — | **없음** | — |

원장(`WebAiTasks`) 시각과 대조 — **정확히 일치**:

```
t_ljISMyrEYAKLRjEm  created 17:51:39  claimed 17:52:19  submitted 17:53:59  → total 140s / wait 40s
t_53RRgSSv6nhfJVsf  created 17:50:30  claimed 17:50:30  submitted 17:51:06  → total  36s / wait  0s
```

배포 전 답변(2619)에 각인이 없고 배포 후 두 건에 있다 — 경계가 배포 시점과 일치하므로
「이 수정 덕분」임을 말할 수 있다(대조군 역할).

배포본 코드를 라이브 DB 의 task 4건에 직접 호출해서도 확인했다(읽기전용, 저장 없음) —
`j_*` job task 들에 대해 각각 13000/9000/8000/7000ms 산출.

## 라이브에서 드러난 두 사실

**① 표시 중복** — 대기가 0 인 답변(2621)의 분해는 실행 한 구간뿐이고 그 값이 총량과 같다.
프런트는 분해를 괄호로 덧붙이므로 화면에 `36초 (추론 36초)` 로 같은 숫자가 두 번 나온다.
정보가 0인 괄호다. **조치**: 가를 것이 없으면(대기가 프런트 표시 임계 250ms 미만이거나 없음)
`duration_breakdown` 을 **싣지 않는다** — 프런트 무변경으로 `36초` 만 표시된다. 서버·프런트
임계가 갈리지 않도록 `app.js` 의 숫자를 읽어 대조하는 테스트를 함께 뒀다.

**② 초 해상도가 상한** — `WebAiTasks` 의 세 시각은 `DATETIME`(소수부 없음)이라
`TIMESTAMPDIFF(MICROSECOND, …)` 를 써도 소수부가 0 이다(실측 140000.0 · 36000.0 — 전부
1000ms 배수). 서버 LLM 경로는 `perf_counter` 기반이라 밀리초까지 정확하지만 이쪽은 원장에서
파생하므로 그 이상을 주장할 수 없다. 총 수행시간 표시에는 충분하며, 더 필요해지면 컬럼을
`DATETIME(3)` 으로 올리는 별건이다. docstring 에 한계로 명시했다.

## 단위

- `test_bridge_answer_duration.py` **22 passed** (기존 18 + 임계 정합·표시 가능 대기·즉시 점유 4건).
- 관련 스위트(feature-0003 · 0043) 실패 0.

## 미수행 (정직 표기)

- **PB-0008 실 브라우저 캡처** — 웹 자산 변경 0(백엔드 각인만)이라 check #13 대상 표면이 없다.
  화면 표시는 DB 각인값 + 프런트 표시 게이트(`durationMs > 0`)·임계 정합 테스트로 확인했다.
  픽셀 캡처는 하지 않았으므로 「눈으로 봤다」고 적지 않는다.
- 과거 104건 소급 각인 안 함(전 cycle 결정 유지).
