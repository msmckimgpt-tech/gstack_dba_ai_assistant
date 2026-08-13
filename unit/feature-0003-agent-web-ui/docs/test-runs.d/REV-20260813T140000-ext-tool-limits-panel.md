---
run_at: 2026-08-13T14:00:00+09:00
session: ai/claude/feature-0041-external-ai-tool-surface
scope: feature-0041 외부 AI 도구 상한 — 관리 콘솔 전용 패널 분리
verdict: PASS (결함 적발 → 수정)
---

# Run — 외부 AI 도구 상한 패널 (PB-0008)

- **Environment**: Windows-browser
- **Runner**: AI
- **Bridge**: relay · `http://172.26.144.1:9223` (Chrome/150.0.7871.128)
- **대상**: `https://mysql-ai.company.local/admin` (라이브 `34376206`)
- **Evidence**: `evidence/REV-20260813T-ext-tool-panel-before.png`

## 1. 무엇을 잡았나 (수정 전 실측)

배포 후 실제 화면에서 확인한 결과, feature-0041 이 추가한 상한 4종이 **전용 섹션이 아니라
'실행 타임아웃' 패널 안의 카테고리**로 렌더되고 있었다. 문서에는 `시스템 > 설정 > 외부 AI 도구`
섹션이 있는 것처럼 적혀 있었으므로 **문서가 사실을 앞질러 있었다.**

실측 DOM (설정 → 실행 타임아웃 패널의 카테고리 소제목):

```
["쿼리·에이전트 실행", "인사이트·플랜", "지식베이스", "DB 연결",
 "커넥션 상태 프로브", "MCP", "작업공간(스크래치)", "대화 폴더", "외부 AI 도구"]
```

설정 서브탭 nav 실측: `["prompts","runtime-timeouts","model-thinking-budgets","redteam-review","performance-parallelism"]`
— `ext-tool-limits` **없음**.

원인: `shared/runtime_settings.py` 의 payload 빌더가 그룹별 버킷을 하드코딩하고 **미분류는
`timeouts` 로 흘려보낸다.** 그룹 상수(`GROUP_EXT_TOOL`)만 추가하고 버킷 분기를 안 하면 UI 는
조용히 기타 취급한다 — 그룹 추가는 **스펙·버킷·패널 3곳 계약**이다.

## 2. 조치

- payload 에 `ext_tool` 전용 버킷 신설
- `admin.html` 에 패널 `ext-tool-limits` + 서브탭 nav 추가
- `admin/settings.js` 에 `mountExtToolLimitsPanel`/`renderExtToolLimits` + 재렌더 훅
- `admin.js` 미저장 dot 을 해당 서브탭으로 라우팅(`RS_EXT_TOOL_KEYS`)
- 회귀 4건 + 뮤테이션 2종(버킷 분기 제거 · 미러 키 누락) KILL 확인

## 3. 수정 후 재검증 (라이브 `feadc089`, 동일 브리지)

- **Evidence**: `evidence/REV-20260813T-ext-tool-panel-after.png`

| # | 항목 | 결과 |
|---|---|---|
| 1 | 설정 서브탭 nav 에 `ext-tool-limits` 등장 | ✅ (`["prompts","runtime-timeouts","model-thinking-budgets","redteam-review","performance-parallelism","ext-tool-limits"]`) |
| 2 | 패널 가시(`extToolLimitsMount.offsetParent !== null`) | ✅ |
| 3 | 행 4개 · 라벨·단위·기본값·'즉시 반영' 배지 렌더 | ✅ (분당 호출 120회/분 · 시간당 행수 200000행 · 시간당 바이트 67108864바이트 · 미제출 20개) |
| 4 | **'실행 타임아웃' 패널에서 '외부 AI 도구' 카테고리 사라짐** | ✅ (`stillMixed: false`) |
| 5 | 기존 타임아웃 카테고리 8종 보존 | ✅ |

**Verdict: PASS** — 결함을 화면에서 잡고, 수정 후 같은 화면에서 확인했다.

## 4. 남은 미검증 (정직 표기)

이 Run 은 **콘솔 설정 화면**만 다룬다. feature-0041 의 인증 전 구간 e2e(브라우저 인가 →
토큰 교환 → 도구 호출 → 제출)는 사람 로그인·동의가 필요해 별도이며,
`unit/feature-0041-external-ai-tool-surface/docs/E2E_RUNBOOK.md` 로 남아 있다.
