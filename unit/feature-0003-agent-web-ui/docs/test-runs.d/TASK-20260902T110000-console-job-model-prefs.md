---
doc_type: TEST_RUN
feature_id: feature-0003-agent-web-ui
task_id: TASK-20260902T110000-console-job-model-prefs
edit_policy: append-only
---

# TEST-20260902T110000-pb0008-predeploy — PRE-DEPLOY baseline (Windows-browser)

- **Environment: Windows-browser** (`bin/win-browser.py`, PB-0008 · 실 Windows Chrome)
- 대상: `https://localhost/` (Caddy :443 · 배포본 `5128b97e`)
- 시각: 2026-09-02

## 무엇을 고정했나

이 cycle 이 추가하는 표면이 **배포본에 아직 없다**는 사실을 먼저 실측해 둔다. POST-DEPLOY 실측이
「원래 있던 것을 봤다」가 되지 않으려면 이 baseline 이 필요하다.

| 관측 | 결과 |
|---|---|
| 페이지 도달 | `status=200` · title `DQA — Database Query Assistant` |
| 프로필 drawer DOM | `#profileDrawer` 존재 (종전 구조 정상) |
| **「AI 작업」 탭** `[data-profile-tab="ai-jobs"]` | **없음** (`false`) |
| **`GET /api/profile/console-jobs`** | **404** |

## 남은 것 (POST-DEPLOY 에서 실측)

1. 프로필 > **AI 작업** 탭이 렌더되고 항목 6종(그래프 AI 능동 분석 · 메타데이터 자동완성 단건/
   일괄 · 시스템 프롬프트 자동작성 · 테이블 인사이트 배치 · 클러스터 라벨링)이 보이는가.
2. 모델·등급을 저장하면 `GET` 이 그 값을 되돌려 주고, 능동 분석 dispatch 가 그 값으로 나가는가
   (러너 로그 `kind=job` 의 `model`·`effort`).
3. 러너가 못 주는 모델을 골랐을 때 **위임이 거절되고 사유가 화면에 도달**하는가 — 설정 실수로
   분석이 멈추는 방향이라 이 경로는 반드시 눈으로 확인한다.
