---
run_at: 2026-08-14T12:00:00+09:00
session: ai/claude/feature-0041-external-ai-tool-surface
scope: feature-0041 인가 완료 화면(/ai/oauth/callback)
verdict: PASS
---

# Run — 인가 완료 화면 (PB-0008, 머지 전)

- **Environment**: Windows-browser · **Runner**: AI
- **Bridge**: relay · `http://172.26.144.1:9223` (Chrome/150.0.7871.128)
- **대상**: 브랜치 코드 bind-mount 격리 컨테이너 `https://mysql-ai.company.local:18443`
- **Evidence**: `evidence/REV-20260814T-callback-{approved,denied}.png`

## 왜 만들었나

사용자가 인가 후 뜬 화면(`OK - callback captured. You may close this tab.`)에 거부감을 보고했다.
그 화면은 **우리 것이 아니라** 클라이언트 쪽 콜백 서버가 그린 것이다 — 자동 연결이 막혀 있어
(DCR 결함) 외부 세션이 콜백 서버를 손으로 만들었고, 그 평문 응답이 사용자에게 보였다.

근본 원인(DCR)은 별도로 고쳤다. 다만 **자체 콜백 서버가 없는 연동**은 앞으로도 계속 생기므로,
`redirect_uri` 로 등록할 수 있는 화면을 우리가 제공한다.

## 실측

| # | 입력 | 결과 |
|---|---|---|
| 1 | `?code=mao_TESTCODE…` | 200 · 제목 "연결 완료" · **승인 화면** · 코드 표시 · [코드 복사] · 60초/1회용·공유금지 경고 ✅ |
| 2 | `?error=access_denied` | 200 · **거부 화면** · "요청을 거부했습니다." + 원시 값 ✅ |
| 3 | 인자 없음 | 200 · 안내 화면(직접 열 필요 없음 + `/ai/connect` 링크) ✅ |

세 분기 모두 같은 정적 자산이며 서버는 아무 상태도 만들지 않는다(코드는 URL 에만 존재).
PKCE 때문에 `code_verifier` 없이는 코드를 교환할 수 없으나, 사람이 **남에게 넘기는** 경로는
남으므로 그 경고를 화면에 뒀다.
