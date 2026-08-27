---
run_at: 2026-08-28T06:50:00+09:00
session: ai/claude/feature-0043-bridge-stream-interrupt
scope: 브리지 인터럽트·맥락 전환·진행 스트리밍의 웹 UI 변경 (composer.js · app.js · chat.css)
verdict: 브리지 복구 PASS · 배포 도달 PASS · **앱 내부 동작은 미검증**(로그인 자격증명 부재)
---

# Run — 인터럽트·진행 스트리밍 UI

Environment: **Windows-browser** (실 Windows Chrome/151.0.7922.170 · CDP relay · `bin/win-browser.py`)

## 이번 Run 의 핵심 — PB-0008 브리지 근본원인 수정

이 저장소의 PB-0008 은 여러 cycle 동안 "브리지 setup 불가" 로 기록돼 왔다. **원인을 찾아 고쳤고
이제 동작한다.**

`bin/win-browser.py` 의 `win_host_ip()` 가 `/etc/resolv.conf` 의 **첫 nameserver** 를 Windows
host 로 썼다. WSL 자동 생성 구성에서는 그 값이 곧 Windows host 라 맞았지만, 이 머신은 공용
DNS(`8.8.8.8`)를 직접 넣어 두어 **공용 IP 를 Windows host 로 오판**했다.

증상이 오래 숨은 이유: relay 가 `"relay started (8.8.8.8:9223 -> 127.0.0.1:9222)"` 로
**성공을 보고**하고 CDP 연결만 조용히 실패했다. 성공 로그가 원인을 가렸다.

수정(`bin/win-browser.py`):
- 기본 게이트웨이(`ip route show default`)를 **먼저** 보고, **사설 IP 만** 받는다.
- 공용 IP 를 돌려주느니 `None` 으로 정직하게 실패한다 — `None` 은 "못 찾았다" 지만
  공용 IP 는 *성공한 것처럼 보이는 relay* 를 만들어 원인을 숨긴다.
- `WIN_BROWSER_HOST` env 탈출구 추가.

```
$ python3 bin/win-browser.py doctor
{"ok": true, "win_host": "172.26.144.1", "bridge_mode": "relay",
 "endpoint": "http://172.26.144.1:9223", "cdp_version": "Chrome/151.0.7922.170", "issues": []}

$ python3 bin/win-browser.py launch --url https://mysql-ai.company.local/
{"ok": true, "navigated": {"status": 200, "title": "DQA — Database Query Assistant"}}
```

증적: `artifacts/pb0008-20260828/live-before.png` — 배포 전 라이브 화면(비교 기준선)

## 이번 UI 변경의 검증 상태

| 항목 | 결과 |
|---|---|
| 브라우저 브리지 동작 | **PASS** |
| 라이브 화면 도달(전송계층 + 앱) | **PASS** — 200 · 정상 title |
| `composer.js` · `app.js` ESM 구문 | **PASS** (`node --check`) |
| 이번 cycle 의 화면 동작 | **미검증 — post-deploy 수행** |

바뀐 화면(중단 버튼 노출 · 취소/대체 말풍선 · 진행 단계 표시 · SSE 재접속)은 **이 브랜치에만
있고 라이브에는 없다.** 배포 전에는 관측할 대상 자체가 존재하지 않으므로, 지금 "PASS" 라고
쓰면 검증하지 않은 것을 검증했다고 말하는 것이 된다.

`deploy_scope: included` 이므로 순서는 **머지 → 배포 → POST-DEPLOY PB-0008** 이다
(feature-0043 TASK.md §5 Next Action 과 동일). 배포 직후 수행 항목:

1. 전용 새 대화에서 질문 전송 → 대기 말풍선 + **중단 버튼 노출**
2. 중단 클릭 → 말풍선이 취소 안내로 변경 → **새로고침 후에도 유지**
3. 대기 중 새 질문 전송 → 이전 말풍선이 '대체됨' 으로 변경
4. 개인 AI 점유 → **조사 단계가 답변 도착 전에** 표시
5. 55초 경과 → SSE 재접속이 끊김 없이 이어지고 `/livez` 의 `active_streams` 가 0 으로 복귀

> **주의(§16.3 bring-up/access)**: 위 1~5 는 "컴포넌트가 떴다" 가 아니라 **사용자 도달성**
> 검증이다. 둘을 섞어 적지 않는다.

**이번에는 "브리지 불가" 가 사유가 아니다.** 사유는 오직 "대상 코드가 아직 라이브에 없다" 이고,
그것은 배포로 해소된다.

Cross-ref: `unit/feature-0043-external-llm-bridge/docs/test-runs.d/TASK-20260828T070000-ai-claude-feature-0043.md`


---

# POST-DEPLOY 실측 (2026-08-28, `e8465ccb` 배포 후)

배포가 끝난 뒤 같은 브리지로 라이브를 다시 확인했다.

## PASS — 배포가 사용자에게 도달했다

| 항목 | 결과 |
|---|---|
| 브라우저 브리지 | Chrome/151.0.7922.170 · CDP relay 정상 |
| 라이브 진입 | `https://mysql-ai.company.local/` → **200** · `DQA — Database Query Assistant` |
| **서빙 자산에 신규 코드 도달** | 캐시 스탬프 `642756f9181f` 의 `composer.js` 에서 `_bridgePendingHere` · `_streamBridgeStatus` · `abandonBridgeTasks` · `bridge-live-steps` · `/api/ai/bridge_stream` **전 5종 확인** |
| **신규 SSE 라우트 존재 + 인증 선행** | `GET /api/ai/bridge_stream?task_id=…` → **401** 이고 `content-type: application/json`(SSE 아님) |
| 전 서비스 이미지 SHA | `web-a/web-b`=`mysql-ai-web:e8465ccb` · `ask/insight-worker·ops-scheduler·ext-tool-mcp`=`mysql-ai-agent:e8465ccb` |
| 대화 경로 스모크 | PASS(전환 모드 — 서버 계정 LLM 차단 확인) |
| surge 잔존 | 0 |
| 엣지 무중단 | `no upstreams available` **0건**(배포 창 12분) |

**401 + `application/json` 은 우연이 아니라 계약 확인이다.** 인증을 스트림 오픈 **뒤**에 했다면
이미 200 + SSE 헤더가 나간 뒤라 401 을 돌려줄 수 없고 `content-type` 도 `text/event-stream`
이었을 것이다. 코드에 그렇게 써 두었고(`test_stream_authenticates_before_opening`), 라이브가
그대로 동작한다.

## 미검증 — 앱 내부 동작 (자격증명 필요)

브라우저 세션이 **로그인되어 있지 않다**(`authOverlay` 표시 · `/api/session` 의 `user: null`).
컴포저 DOM 은 존재하지만 오버레이 뒤에 있어, 다음 5개는 **관측하지 못했다**:

1. 대기 중 **중단 버튼 노출**
2. 중단 → 말풍선이 취소 안내로 변경 → 새로고침 유지
3. 재전송 → 이전 말풍선 '대체됨'
4. 점유 중 **조사 단계가 답변 전에** 표시
5. 55초 후 SSE 재접속 · `active_streams` 0 복귀

자격증명을 추측하거나 우회하지 않았다. 이 5개는 **사용자 로그인 세션에서 수행해야 한다** —
로그인 후 같은 브리지(`bin/win-browser.py`)로 즉시 검증 가능하다(브리지는 이제 동작한다).

> 정직 표기: 위 PASS 항목들은 "부품이 제자리에 있고 배포가 도달했다" 까지다.
> **"화면이 의도대로 움직인다" 는 별개 주장이며 아직 하지 않았다.**
