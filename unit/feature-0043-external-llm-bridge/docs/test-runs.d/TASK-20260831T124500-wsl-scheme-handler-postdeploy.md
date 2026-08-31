---
run_at: 2026-08-31T15:30:00+09:00
session: ai/claude/feature-0043-wsl-postdeploy
scope: "[내 AI 실행] 핸들러 교정 — 라이브 배포본 POST-DEPLOY 검증"
verdict: PASS
---

# Run — TASK-20260831T124500 POST-DEPLOY (배포본 `b35fa376`)

- **Environment**: **Windows-browser** (PB-0008) — **라이브** `https://localhost/`
- **전제**: `f1f24f27`(이번 변경)가 `b35fa376` 의 조상임을 `git merge-base --is-ancestor` 로 확인

머지는 코드 통합이지 배포가 아니다(§16.3 deploy-backed 완료 기준). 사전 검증은 격리 인스턴스
(`:18099`)에서 했으므로, **사용자가 실제로 받는 배포본**에서 한 번 더 본다.

## 배포 실측

| 항목 | 값 |
|---|---|
| web-a / web-b 이미지·`GIT_COMMIT` | `mysql-ai-web:b35fa376` / `b35fa376` (양쪽 일치) |
| `https://localhost/healthz` | 200 |
| caddy `no upstreams available` (최근 15분) | **0** — 이번 배포 창은 실제로 무중단 |
| 서빙 `static/app/connect-modal.js` 에 `_LAUNCH_DEADLINE_MS` | 존재 |
| 서빙 `static/agent/bridge_setup.sh` 에 `register_handler_windows` | 존재 |
| 로드된 자산 스탬프 | `app.js?v=850c823184f8` |

## 화면 (라이브)

| 단계 | 관측 |
|---|---|
| 게이트 패널 `[내 AI 실행하기]` | 모달 열림 (칩 `AI 대기 안 함`) |
| `[연결 준비]` | "준비했습니다. 이 창을 닫으면 다시 볼 수 없습니다." |
| `[내 AI 실행]` 직후 | "실행을 요청했습니다. 내 AI가 응답하는지 확인하는 중…" (**성공색 아님**) |
| ~45초 후 | `data-kind=error` · "아직 응답이 없습니다. 이 컴퓨터에 실행 핸들러가 없거…" · 버튼 재활성 |
| 문구·명령 동시 가시 | `statusVisible=true` (`statusTop 784` < 뷰포트 889) · `cmdVisible=true` |

배포 전(격리 인스턴스)과 **동일 거동**. 종전 배포본이 이 자리에서 「실행을 요청했습니다」를
성공색으로 띄우고 끝났던 것과 대비된다.

## 미검증 (정직 표기)

- **핸들러가 실제로 러너를 띄우는 경로**는 이 검증에 없다 — 검증 시점의 이 머신에는 스킴
  핸들러가 등록돼 있지 않다(사전 검증에 쓴 프로브 등록은 **원복**했다). 등록→기동 왕복은
  사전 검증에서 OS 수준으로 3/3 확인했고(`test-runs.d/TASK-20260831T124500-wsl-scheme-handler.md`
  §2), 라이브에서 관측한 것은 **그 반대편** — 핸들러가 없을 때 사용자가 막다른 길에 갇히지
  않는다는 것이다.
- **사용자 실 머신 재확인**은 남는다: 설치 명령 재실행 → `[내 AI 실행]` → 크롬 확인창 허용 →
  상태 표시가 `내 AI 대기 중` 으로 전환.
