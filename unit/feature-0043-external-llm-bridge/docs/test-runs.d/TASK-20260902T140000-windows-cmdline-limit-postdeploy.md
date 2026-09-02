---
run_at: 2026-09-02T13:50:00+09:00
session: ai/claude-corp/feature-0043-winargv-postdeploy
scope: TASK-20260902T140000 POST-DEPLOY 실측 (배포 66769688)
verdict: PASS
---

# Run — TASK-20260902T140000 POST-DEPLOY 실측

배포 `66769688` (`make deploy-web`, scope=all). 이 cycle 의 수정은 **사용자가 내려받는
러너**에 실리므로, 「머지됐다」가 아니라 **「그 사용자가 받는 바이트가 고쳐졌는가」**를
배포본에서 실측한다.

## Environment

- 라이브 스택 (Caddy :443 · `mysql-ai-web:66769688` / `mysql-ai-agent:66769688`)
- 검증 대상은 **엣지에서 내려받은 실제 바이트**(`https://<host>/static/agent/bridge_agent.py`)
- **Environment: Windows-browser — 미수행(사유)**: 이 cycle 은 웹 자산(html/css/js/template)
  변경 **0건**이다(러너는 파이썬, 배포본은 `.gitignore` 빌드 산출물). 브라우저 렌더 표면이
  없어 PB-0008 대상이 아니다.

## 1. 배포 무중단·전 서비스 SHA 일치

| 항목 | 결과 |
|---|---|
| 서비스별 실물 이미지 태그 | web-a · web-b · ext-tool-mcp-a · ext-tool-mcp-b · insight-worker · ask-worker · ops-scheduler = **전부 `66769688`** (healthy) |
| 엣지 `/healthz` | **200** |
| caddy `no upstreams available` (배포 창 25분) | **0건** (무중단 실측) |
| RestartCount (web·mcp 4종) | **전부 0** |
| `ask-worker-surge` 잔존 | **0** (정리 완료) |
| Caddyfile reconcile | 무변경(sha 일치) — caddy 무접촉, blip 0 |
| gateway reconcile | 드리프트 없음 — 무접촉 |
| 워커 드레인 | ask-worker 본체 drained(7s) · surge drained(4s) — 진행 중 왕복 완주 |
| 대화 경로 스모크 | **PASS** (전환 모드 — 서버 계정 LLM 차단 확인) |

## 2. 사용자가 받는 러너에 수정이 도달했는가

```
GET https://<host>/static/agent/bridge_agent.py      → 200, 287,505 bytes
sha256(내려받은 바이트)  = 0c814862bea2c72e…
sha256(이미지 산출물)     = 0c814862bea2c72e…        ← 일치
```

수정 심볼 전건 존재: `_fit_cmdline`(3) · `stdin_ok`(6) · `_WIN_CMDLINE_MAX`(2) ·
`system_channel_fits`(3) · `_CMDLINE_OVERFLOW_MSG`(2) · `reason_out`(13).

## 3. ⭐ 심볼 존재가 아니라 **동작**을 배포본으로 실측

「방어를 넣었다」와 「방어가 성립한다」는 다르다. 그래서 **내려받은 그 바이트를 모듈로
적재**해 라이브에서 실측한 크기(지침 34,962 · 질문 3,494 → 접힌 본문 38,456)로 돌렸다.

| # | 축 | 관측값 | 기대 |
|---|---|---|---|
| 1 | Windows 예산 | **30,719** | 실측 상한 32,767 미만 ✓ |
| 2 | 34,962자 지침의 시스템 채널 적합 | **False** | 본문으로 접는다 ✓ |
| 3 | 38,456자 본문 전달 경로 | **`stdin`** · argv 에 본문 없음 | ✓ |
| 4 | 자식이 실제로 읽은 stdin 길이 | **38,456** (`GOT:38456`) | 전달 완주 ✓ |
| 5 | stdin 미지원 런타임(gemini) | **`overflow`** | 예외 대신 정직한 실패 ✓ |
| 6 | POSIX 예산에서 같은 지침 | **True** (채널 유지) | 무회귀 ✓ |

배포본이 낸 로그도 함께 관측했다 — 폴백이 **조용하지 않다**:

```
WARN  ai.cmdline.stdin    runtime=claude budget=30719 cmd_chars=38486 prompt_chars=38456
      | 명령줄이 이 운영체제의 상한을 넘어 질문을 표준입력으로 전달합니다.
ERROR ai.cmdline.overflow runtime=gemini budget=30719 stdin_ok=False
      | 명령줄이 이 운영체제의 상한을 넘었고 줄일 방법이 없습니다.
```

즉 배포 전 그 계정의 **모든** 질문을 죽이던 `[WinError 206]` 경로가, 배포본에서는
① 지침을 본문으로 접고 ② 질문을 stdin 으로 넘겨 **실행에 도달**한다.

## 4. 닫지 못한 것 (정직 표기)

- **그 사용자 머신의 실 왕복은 미관측**이다. 러너는 사용자 머신의 파일이므로 **새 사본을
  받아 재기동**해야 이 수정이 발효한다(서버가 그 파일을 바꿀 통로는 없다 —
  `TASK-20260902T120000` §2 와 같은 부트스트랩 한계). 검증 목적으로 그 머신의 브리지 상태를
  갈아엎지 않았다.
- **그 머신 `claude` 로그인 만료**: 같은 창에서 `ai.fail … "OAuth access token has expired.
  Re-authenticate to continue."` 를 관측했다. 사용자 자격증명 영역이라 이 cycle 이 고치지
  않으며, 재로그인 전에는 답변 품질이 회복되지 않는다. 이 cycle 이 한 것은 그 사유가
  **협상 실패 로그에 남게** 만든 것이다(종전에는 4분 기다린 끝에 사유 없는 「답을 받지
  못했습니다」뿐이었다).
- **기동 침묵 제거의 라이브 실증**: 단위(협상 게이트를 붙잡은 채 대기 도달 확인)와 뮤테이션
  으로 잠갔으나, 실 머신에서 `run.start → run.ready` 간격이 실제로 줄어드는 것은 위 재기동
  이후에 관측된다.
