---
run_at: 2026-09-01T16:50:00+09:00
session: ai/claude/feature-0043-cli-failure-postdeploy
scope: 실패 사유 소실 해소 POST-DEPLOY 실측 (배포 4521a7e1)
verdict: PASS (배포 도달 5/5) — 사용자 왕복 1건은 러너 갱신 후로 이월
---

# Run — 실패 사유 소실 해소 POST-DEPLOY 실측

대상 배포: `4521a7e1` (`make deploy-web`, scope=all).

## 1. 배포 게이트

| # | 확인 | 결과 |
|---|---|---|
| D1 | 7서비스 이미지 SHA 일치 (web-a/b · ask-worker · insight-worker · ops-scheduler · ext-tool-mcp-a/b) | **PASS** — 전부 `4521a7e1` |
| D2 | edge `/healthz` = `4521a7e1` · `mysql_ok` · `pg_ok` | **PASS** |
| D3 | 무중단 실측 — caddy `no upstreams available` (기대 0) | **PASS** — **0건** |
| D4 | surge 잔존 (기대 없음) · quiesce drained | **PASS** — 잔존 0 · 본체 4s / surge 3s |
| D5 | 대화 경로 스모크 | **PASS** (feature-0043 전환 모드 게이트) |

## 2. 배포 실물 런타임 실증 ⭐

`curl https://<host>/static/agent/bridge_agent.py` (http=200, 255,102 bytes) 로 **서빙되는 사본**을
받아 검증했다(소스 트리가 아니라 배포 실물).

| # | 확인 | 결과 |
|---|---|---|
| R1 | 서빙 사본 md5 = **배포 SHA 의 블롭** md5 (`af124d73…`) | **PASS** |
| R2 | 봉인 심볼 적재 — `describe_cli_failure` · `_FAILURE_HINTS` · `_STDERR_NOISE` · `_redact_secrets` · `stdout_tail` | **PASS** (11 참조) |
| R3 | 서빙 사본을 그대로 import 해 **라이브 실측 입력**(stdout=한도 안내 / stderr=stdin 경고)을 투입 | **PASS** — 아래 문장 생성 |

```
AI 가 오류로 끝났습니다(exit 1). 연결된 AI 가 남긴 사유: You've hit your session limit
· resets 5:30pm (Asia/Seoul)

연결된 AI 의 사용 한도에 걸렸습니다. 위에 적힌 초기화 시각이 지난 뒤 같은 질문을 다시
보내면 처리됩니다(질문은 그대로 다시 보내면 됩니다).
```

종전 같은 입력의 출력은 `AI 가 오류로 끝났습니다(exit 1):` — 콜론 뒤가 빈 문장이었다.
**사용자가 받게 될 문장이 배포본에서 실제로 생성된다**는 것이 이 항목의 실증 내용이다.

## 3. 사용자 확인 이월 (1건)

러너는 **사용자 머신 파일**이라 서버 배포가 갱신하지 못한다. 사용자가 화면의 「연결 준비」를
다시 눌러 최신 사본을 받아야 이 수정이 그 사람의 다음 실패에서 발효한다(불일치 상태는 서버가
`stale_build` 로 표시). 그 이후의 실제 실패 1회가 라이브 확인 지점이며, 원장 재측정 축은
`WebAiTasks` 중 `Answer LIKE '%오류로 끝났습니다%'` 이면서 **사유 자리가 빈** 건수
(배포 시점 기준선 = 전 기간 **5건 / 100%**).
