---
run_at: 2026-09-02T15:20:00+09:00
session: ai/claude-corp/feature-0043-child-io-postdeploy
scope: TASK-20260902T160000 POST-DEPLOY 실측 (배포 1e394a14) — 실 Windows cp949 대조
verdict: PASS
---

# Run — TASK-20260902T160000 POST-DEPLOY 실측

배포 `1e394a14` (`make deploy-web`, scope=all). 이 cycle 의 결함은 **한국어 Windows 로케일에서만**
나타나므로, 「머지·배포됐다」가 아니라 **그 로케일에서 배포본이 실제로 동작하는가**를 잰다.

## Environment

- 라이브 스택 (`mysql-ai-web:1e394a14` / `mysql-ai-agent:1e394a14`)
- **검증 대상 = 엣지에서 내려받은 배포본 바이트**를 사용자 머신에서 그 로케일로 실행
- **Environment: Windows-browser — 미수행(사유)**: 웹 자산(html/css/js/template) 변경 0건.
  러너는 파이썬이고 배포본은 `.gitignore` 빌드 산출물이라 브라우저 렌더 표면이 없다.

## 1. 배포 무중단·전 서비스 SHA 일치

| 항목 | 결과 |
|---|---|
| 서비스별 실물 이미지 | web-a·web-b·mcp-a·mcp-b·insight-worker·ask-worker·ops-scheduler = **전부 `1e394a14`** (healthy) |
| 엣지 `/healthz` | **200** |
| caddy `no upstreams available` (15분) | **0건** |
| 대화 경로 스모크 | **PASS** |
| 배포 스크립트 결론 | `배포 완료: 1e394a14 (scope=all — soak + 대화 스모크 통과)` |

## 2. 서빙되는 러너에 수정이 실렸는가

```
GET https://<host>/static/agent/bridge_agent.py   → 200, 306,768 bytes
CHILD_TEXT_IO(6) · pump_exc(5) · ai.io_fail(1) · _fit_cmdline(3) · try_self_update(1)
```

## 3. ⭐ 실 Windows(cp949) 대조 검증 — 이 cycle 의 정본 증거

내려받은 **배포본 바이트**를 사용자 머신에서 그대로 적재해 라이브 실측 크기로 돌렸다.

```
locale.getencoding() = cp949                                  ← 결함 조건
CHILD_TEXT_IO = {'text': True, 'encoding': 'utf-8', 'errors': 'replace'}
payload = 40,000자 (U+27E6 포함, 라이브 39,014자 대역)

_run_cli_cancelable  ok=True → "LEN:40000 MARK:yes 한글⟦끝⟧"   ← PASS
  · 본문 40,000자 전량 도달   · U+27E6 보존   · 자식의 UTF-8 한글 무손상 왕복

대조군(수정 전 `text=True`): UnicodeEncodeError                ← 라이브에서 죽던 그 지점
```

**대조군이 load-bearing 이다** — 그것 없이는 「PASS 가 이 수정 덕분」임을 말할 수 없다. 같은
머신·같은 로케일·같은 payload 에서 수정 전은 죽고 수정 후는 통과한다.

## 4. 함께 확인한 형제 cycle 산물

배포본에 `try_self_update` + 기능 신고 `self_update` 가 포함돼 있다(형제 세션 #1522). 즉 사용자가
**이번 한 번만** 새 사본을 받아 재기동하면, 이후 러너 갱신은 자동으로 이뤄진다. 병합 시
`selfupdate.py` 가 전 구간 **바이너리 모드**(`rb`/`wb`/`ast.parse(bytes)`)임을 확인해 본 cycle 의
인코딩 축과 상호작용이 없음을 검증했다(병합 변형 점검).

## 5. 닫지 못한 것 (정직 표기)

- **사용자 머신의 실 대화 왕복은 미관측**이다. 러너는 사용자 머신의 파일이므로 새 사본을 받아
  재기동해야 이 수정이 발효한다. 검증 목적으로 그 머신의 브리지 상태를 갈아엎지 않았다.
- **그 머신 `claude` 인증**: 이번 수정으로 요청이 `claude.exe` 에 **도달**하지만, 그 CLI 는
  로그인 만료 상태다(12:35 `401 OAuth access token has expired` · 14:16 능력 협상
  `TimeoutExpired`). 재로그인 전에는 정상 답변이 아니라 `_FAILURE_HINTS` 의
  「연결된 AI 에 로그인돼 있지 않습니다」 안내가 표시된다 — 사용자 조작 영역.
  즉 **이 cycle 이 보장하는 것은 «파이프라인이 AI 에 도달하고 실패 사유가 정직하게 표시된다»
  까지**이고, 「정상 답변이 온다」는 그 인증에 달려 있다.
