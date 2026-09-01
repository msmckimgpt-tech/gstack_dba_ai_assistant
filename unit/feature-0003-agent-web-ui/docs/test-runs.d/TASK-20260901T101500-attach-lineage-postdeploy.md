---
run_at: 2026-09-01T10:15:00+09:00
session: ai/claude/feature-0003-attach-lineage-postdeploy
scope: 첨부 계보 비교 가시성 재설계 — POST-DEPLOY 라이브 배포본 검증
verdict: PASS
---

## Run — POST-DEPLOY (라이브 배포본 `2f09d755`)

- Date: 2026-09-01 · Environment: **Windows-browser** (PB-0008) · Target: **라이브** `https://localhost/`
  (Caddy :443 단일 진입, 격리 컨테이너 아님)
- 배포: PR #1452 머지(`fb911048`) → `make deploy-web` → 후속 main(`2f09d755`)까지 포함해 스파인 완주
- Result: **PASS**

### 배포 상태 (feature-0014 RUNBOOK §10 체크리스트)

| 항목 | 실측 |
|---|---|
| [2] 서비스별 이미지 SHA 일치 | web-a·web-b·insight·ask·ops-scheduler·ext-tool-mcp-a/b **전부 `2f09d755`** |
| [2b] surge 잔존 | **0** |
| [5] 무중단 (`no upstreams available`) | **0건** |
| [3] 서빙 스탬프 | `2e71f760557a` — 서빙 composer.js 에 `attach-lineage-group` **6건** |
| [1b] 대화 스모크 | PASS (스파인 로그) |

### [4] 실 사용자 표면 — 배포본에서 재확인

| 관측 | 값 |
|---|---|
| 모듈 스탬프(브라우저가 실제 로드) | `2e71f760557a` |
| 그룹 카드 / 카드 안 행 / 분기 | **2 / 4 / 2** |
| 카드 접근성 | `role="group"` · `IMMEDIATE_LEAVE_MEMBER.sql — 같은 이름의 계보 2개` |
| 행 접근성 이름 | `…(사용자 계보, 2개 중 1번째) 원문 보기` / `…(AI 계보, 갈라져 나옴, 2개 중 2번째) 원문 보기` |
| 대비 | 테두리 `rgb(168,165,152)` · 레일 `rgb(140,138,124)` |
| 그룹 비교 클릭 1회 | aria `첨부 계보 비교` · 축 **`time`** · `사용자 업로드 v1 · 현재` → `AI 수정본 v2` · `+182 / -21` |

렌더 텍스트(배포본): `IMMEDIATE_LEAVE_MEMBER.sql / 계보 2 / ⇄ 계보 비교` → `사용자 계보` ·
`v2 · AI 수정` `⤷ AI 계보` `9KB · +8KB`. 스크린샷 `postdeploy.png`.

## 배포 중 관측한 인프라 조건 (본 변경과 무관, 기록용)

- **Caddy `docker exec` 파손** — `procReady not received`. `deploy-web` preflight 가 이를
  **rootCA 불일치로 오진**해 `ABORT` 시켰다(기존 기록과 동일 함정). `docker restart repo-caddy-1`
  로 복구 후 스파인 완주. Caddy 자체는 그 시점에도 정상 서빙 중이었다(`/healthz` 200).
- **GitHub Actions 전 저장소 red** — 결제/지출한도 정지로 job 이 시작조차 못 한다(step 0개·3초
  failure). `main` 브랜치 런도 동일해 이 변경에 대한 신호가 아니다. PR #1452 는 사용자 승인 후
  머지했고, CLEAN 게이트의 취지는 로컬 5000 passed + 라이브 재검증으로 대체했다.
  ⚠ **결제 조치 전까지 CI 게이트는 무력** — 다음 cycle 들도 같은 판단을 반복하게 된다.
