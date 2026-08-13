---
run_at: 2026-08-13T18:00:00+09:00
session: ai/claude/feature-0041-external-ai-tool-surface
scope: feature-0041 인증 접근성 — 동의 화면 · 표준 discovery · 연결 페이지
verdict: PASS (결함 2건 적발 → 수정 → 재확인)
---

# Run — 외부 AI 인증 화면 (PB-0008, **머지 전** 검증)

- **Environment**: Windows-browser
- **Runner**: AI
- **Bridge**: relay · `http://172.26.144.1:9223` (Chrome/150.0.7871.128)
- **대상**: 브랜치 코드를 bind-mount 한 격리 컨테이너 `https://mysql-ai.company.local:18443`
  (라이브 무접촉 — 인증 화면이라 배포 후 확인은 순서가 틀리다)
- **Evidence**: `evidence/REV-20260813T-consent-screen.png` ·
  `evidence/REV-20260813T-connect-issued.png`

## 1. 브라우저가 잡은 결함 2건

| # | 증상 | 원인 | 조치 |
|---|---|---|---|
| 1 | `/ai/connect` 가 "상태를 확인하지 못했습니다 … not valid JSON" | `app.get_conn` 은 memory DB 실패를 **흡수해 `conn=None` 을 yield** 하는데(app.py 계약) 새 라우트가 분기하지 않아 `AttributeError` → **500** | conn 가드 7곳(`oauth_as` 전 라우트 + `require_ai_token` 503) |
| 2 | 토큰 발급 후 "유효기간 **약 0시간**" | `ACCESS_TTL_SEC`=15분을 시간 단위로 반올림 | 콘솔 토큰 수명을 **남은 세션 수명**(상한 12h)으로, 표시 단위를 값에 맞춤 |

2번은 표시 문제로 보였지만 실제로는 **기능이 성립하지 않는 상태**였다 — 15분짜리 토큰을
설정 파일에 붙여넣게 하는 것은 쓸 수 없는 기능을 준 것과 같다.

## 2. 수정 후 실측

| # | 항목 | 결과 |
|---|---|---|
| 1 | `GET /ai/connect` | 200 · "bootstrap_admin 계정으로 외부 AI 를 연결합니다" · 자동/수동 두 경로 표시 |
| 2 | 토큰 발급 버튼 | "발급했습니다 — 유효기간 **약 12시간**, 로그아웃하면 그 전에도 즉시 무효" · 설정 JSON 10줄 렌더(`Bearer mat_…` 포함) |
| 3 | 미로그인 `authorize` | **302 → `/?next=…`** (기존 `/login` 404 해소) |
| 4 | 로그인 상태 `authorize` | **동의 화면 200** — 클라이언트 `pb0008-consent-probe` · 계정 · `데이터 조회 (읽기 전용) — data.read` · 돌아갈 곳 `127.0.0.1:8765` · 범위/비용/해지 고지 3줄 |
| 5 | **[허용]** 클릭 | `http://127.0.0.1:8765/cb?code=…&state=pb0008` 로 이동(수신자 없음 → 연결 오류 화면 = 기대 동작) |
| 6 | 서버측 결과 | `WebOAuthGrants` 에 인가코드 1건(`scopes=data.read`) · **consent nonce 소비 1행**(단일 사용) · 콘솔 토큰 만료 = 발급 +12h |
| 7 | discovery 4경로 · 401 `WWW-Authenticate` | 전부 200 / 헤더에 `resource_metadata=…` 포함 |

## 3. 정리

검증이 라이브 DB 에 남긴 것(probe client 1 · 인가코드 1 · 콘솔 토큰 2)은 전부 revoke 했다.
격리 컨테이너와 브라우저 인스턴스도 종료했다.
