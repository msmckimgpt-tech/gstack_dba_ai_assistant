# Run — TASK-20260828T240000-connect-gate · POST-DEPLOY (배포본 `3ba31141`)

- **일시**: 2026-08-28
- **Environment**: **Windows-browser** (PB-0008) — **라이브 배포본** `https://localhost`
- **대상**: 머지·배포 후 실제 사용자 표면 (feature-0014 RUNBOOK §10 체크리스트 [1]~[5])

## 배포 체크리스트

| # | 항목 | 결과 |
|---|---|---|
| 1 | web-a·web-b 가 대상 SHA + soak | PASS — `mysql-ai-web:3ba31141` ×2 |
| 1b | 대화 경로 스모크 | PASS (전환 모드 — 서버 LLM 차단 확인) |
| 2 | 워커 롤아웃 | PASS — ask/insight/ext-tool-mcp-a·b 전부 `mysql-ai-agent:3ba31141` |
| 2b | surge 잔존 | 0 (정리됨) |
| 3 | 캐시 무효화 | PASS — `chat.css?v=5a61d991458e` (placeholder 아님) |
| 4 | 실 사용자 표면 | PASS (아래) |
| 5 | 무중단 실측 | **`no upstreams available` 0건** |

## [4] 실 사용자 표면 — 라이브 배포본

```
gate            표시됨 · "내 AI가 실행 중이 아닙니다"
inputDisabled   true
conn            "AI 대기 안 함"
footer          flex          ← 연결 칩이 실제로 보인다(이번 cycle 수정분)
status          {connected:true, listening:false, bridge_mode:true, compose_blocked:true}
```

연결 모달:

```
modalOpen        true
launchBtnShown   true          ← [내 AI 실행] (protocol URL 존재)
cmdFirstLine     iwr -UseBasicParsing -Uri 'http://<host>/static/agent/bridge_setup.ps1' …
hasCaSha         true
hasAgentSha      true
```

## 엣지 평문 카브아웃 — 범위가 의도대로 좁은가

```
http://<host>/static/agent/bridge_setup.sh    200   ← 부트스트랩 데드락 해소
http://<host>/static/agent/bridge_setup.ps1   200
http://<host>/static/app.js                   301 → https://…   ← 그 외는 그대로
```

`/static/*` 를 통째로 열지 않았다는 것이 실측으로 확인된다.

## 무결성 값이 **서빙본과 일치**하는가

명령이 싣는 값과 사용자가 실제로 받는 파일을 대조했다 — 이 둘이 갈리면 체크섬은 안전장치가
아니라 오경보 장치가 된다(러너에서 같은 이유로 해시 일치를 테스트로 강제한다).

```
서빙본  sha256(GET /static/agent/bridge_setup.ps1)
        4c8fd4319deaa907f1de1f448102e8ec21aee5bd8a76c0440d7a534eecd19a62
명령    -ne '4C8FD4319DEAA907F1DE1F448102E8EC21AEE5BD8A76C0440D7A534EECD19A62'
        → 일치
```

## 미수행 (정직 표기)

- **실 러너 기동 → 잠금 해제 → 질문 왕복** — 사용자 머신의 AI CLI + 새 `mat_` 토큰이 필요해
  AI 가 무인으로 완결할 수 없다. 화면 거동(`compose_blocked:false` 도착 시 잠금 해제)은
  머지 전 실 브라우저에서 구동해 확인했다(형제 fragment 참조).
- **프로토콜 핸들러 등록·기동** — 같은 사유. 3 OS 분기의 실행 결과는 사용자 확인 항목.
