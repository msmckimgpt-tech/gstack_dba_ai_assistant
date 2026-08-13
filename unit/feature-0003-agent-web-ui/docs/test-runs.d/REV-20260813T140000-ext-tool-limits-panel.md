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

## 3. 수정 후 재검증

동일 절차로 배포 후 재실행 — 아래 §4 에 결과를 append 한다.
