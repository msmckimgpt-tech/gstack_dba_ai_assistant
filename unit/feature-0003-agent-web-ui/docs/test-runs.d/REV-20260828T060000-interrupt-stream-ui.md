---
run_at: 2026-08-28T06:50:00+09:00
session: ai/claude/feature-0043-bridge-stream-interrupt
scope: 브리지 인터럽트·맥락 전환·진행 스트리밍의 웹 UI 변경 (composer.js · app.js · chat.css)
verdict: 브리지 **복구 PASS** / 이번 UI 변경은 **post-deploy 검증 예정**(대상 코드가 아직 라이브에 없음)
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
