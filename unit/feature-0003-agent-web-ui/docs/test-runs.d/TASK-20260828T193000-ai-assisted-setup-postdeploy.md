---
run_at: 2026-08-28T20:10:00+09:00
session: ai/claude/feature-0043-ai-assisted-setup
scope: POST-DEPLOY 시각검증 — 배포본 35f03f62
verdict: PASS
---

# Run — TASK-20260828T193000 POST-DEPLOY (PB-0008 실 Windows 브라우저)

- **일시**: 2026-08-28
- **Environment**: **Windows-browser** (`bin/win-browser.py`, Chrome/151.0.7922.170, relay)
- **대상 배포본**: `35f03f62` (web-a·web-b·워커 전 서비스 SHA 일치 · caddy blip 0)

앞 fragment 에서 "배포 전이라 라이브에 이 화면이 없다 — 배포 후 수행" 이라고 미룬 것을
여기서 완결한다.

## 전제 확인

```
doctor      : ok · bridge_mode=relay · Chrome/151.0.7922.170
session     : authenticated=true · bootstrap_admin · admin
서빙본 대조 : sha256(라이브 /static/agent/bridge_setup.sh) == sha256(정본)
              a53069389df722d9e8915fe163e45976876178be61625f33b4f1c9f9a34e4f7e
```

## `/ai/connect` 단독 페이지

[연결 준비] 클릭 후 실측:

```json
{"probeBoxHidden": false, "probeLen": 2859,
 "summaries": ["환경을 잘 모르겠다면 — AI에게 조사만 맡기기",
               "터미널을 쓸 수 없다면 — AI에게 전부 맡기기"],
 "hasBlank": true, "noIdenticalClaim": true}
```

| 확인 항목 | 결과 |
|---|---|
| 셋째 경로 블록이 뜬다 | PASS (`probeBoxHidden=false`) |
| 세 경로 순서 (①명령 → ②조사 → ③전부위임) | PASS — 명령이 먼저, 조사가 전부위임보다 앞 |
| 지시문이 실제로 실린다 | PASS (2,859자) |
| **빈칸이 명령 안에 실재** | PASS (`BRIDGE_PROBED_PY=''` 포함) |
| 「결과가 같다」 단정 없음 | PASS |
| 비결정성 고지 | PASS ("어떤 값을 고르는지는 **AI마다 다를 수 있습니다**") |
| 복사 버튼 | PASS ([조사 지시문 복사] 렌더) |

화면 판독(스크린샷 2장): 블록이 접힌 채로 뜨고, 펼치면 지시문이 스크롤 가능한 코드 박스로
보인다. `BRIDGE_PROBED_PY` · `BRIDGE_PROBED_AI` 안내와 허용 목록(claude · codex · gemini ·
ollama)이 그대로 읽힌다. `<pre>` 가 카드 폭을 넘치지 않는다.

## 대화 화면 모달 (`/`)

```json
{"modalProbeEl": true, "copyBtn": true,
 "summaries": ["환경을 잘 모르겠다면 — AI에게 조사만 맡기기",
               "터미널을 쓸 수 없다면 — AI에게 전부 맡기기"],
 "noIdentical": true, "hasDisclaimer": true}
```

두 화면의 문안이 **같다** — 한쪽만 고쳐져 어떤 사용자가 옛 안내를 받는 drift 가 없다.

## 미수행 (정직 표기)

- **실제 AI 에게 조사 지시문을 주고 러너가 뜨는 것까지**는 확인하지 못했다. 그 왕복은
  사용자가 자기 AI 에 붙여넣어야 완결된다.
- **WSL↔Windows 핸들러 교차 등록** — 미구현(후속). 이 화면에서 `_HANDLER=none` 안내는
  지시문 안에 들어 있음을 확인했다.
