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

---

# TEST-20260902T123000-pb0008-postdeploy-1 — POST-DEPLOY 실측 (Windows-browser) · **결함 적발**

- **Environment: Windows-browser** (`bin/win-browser.py`, PB-0008)
- 대상: 배포본 `20e90688` · `https://localhost/`

## 결과

| 축 | 관측 | 판정 |
|---|---|---|
| 스키마 (AC-5) | `WebAccounts` 에 `ConsoleJobPrefs`·`BridgeDefaultModel`·`BridgeDefaultEffort` 생성 확인 | **PASS** — 라이브에 없던 두 컬럼도 함께 복구 |
| API 도달 | `GET /api/profile/console-jobs` → 200 · 항목 6종 · `PUT` 왕복 저장/조회 일치 | **PASS** |
| 서버 판정 (배포본 코드 + 라이브 러너 신고) | A 고른 모델 보유 → `blocked=False` `sent=claude:haiku` `effort='medium'` / B 미보유 → **`blocked=True` `can_take=False`** / C 등급 미보유 → `blocked=False` `effort=''` + `unmet` / D 미설정 → 경량 폴백 `blocked=False` | **PASS** — 제보 증상(등급 미송출·조용한 상위 폴백)이 해소됨을 배포본에서 확인 |
| **화면 렌더** | 탭은 열리는데 `rowCount:0`, box 내용 「설정을 불러오지 못했습니다」 | **FAIL — 결함 적발** |

## 적발한 결함

같은 창에서 `fetch("/api/profile/console-jobs")` 를 직접 부르면 **200 + 정상 JSON** 이 온다.
즉 서버는 멀쩡했고, 프런트가 `apiFetch` 의 반환을 **Response 로 오인**해 `res.json()` 을
불러 정상 응답에서 예외가 났다. catch 가 그것을 안내 문구로 바꿔 **서버 로그에도 단위
테스트에도 흔적이 남지 않았다** — 실 브라우저 왕복만이 볼 수 있는 부류다.

→ `CHG-20260902T123000` 에서 수정 + 소비 계약을 번들 전역에 정적으로 잠금.

## 남은 것

수정 배포 후 재실측 — 항목 6종 렌더 · 저장 왕복 · 「고른 모델 미보유」 사유 표시.

---

# TEST-20260902T130000-pb0008-postdeploy-2 — 수정 배포 후 재실측 (Windows-browser) · **PASS**

- **Environment: Windows-browser** (`bin/win-browser.py`, PB-0008)
- 대상: 배포본 `5c02495f` (web-a·web-b 양쪽 교체 확인)

## 결과

| 축 | 관측 | 판정 |
|---|---|---|
| 항목 렌더 | `rowCount: 6` — 메타데이터 자동완성(단건/일괄) · **그래프 AI 능동 분석** · 시스템 프롬프트 자동작성 · 테이블 인사이트 배치 · 클러스터 라벨링 | **PASS**(직전 실측 0개 → 6개) |
| 저장값 복원 | `naModel: claude:haiku` · `naEffort: medium` | **PASS** |
| 러너 부재 시 보존 | 선택지가 `["", "claude:haiku"]` — 러너 신고가 없어도 **저장값을 지우지 않고** 유지 | **PASS**(설계대로) |
| 사유 표시 | `.ai-jobs-warn` 1건 + meta 「지금 듣고 있는 AI 가 없어 선택지를 불러오지 못했습니다. 저장된 설정은 그대로 유지됩니다.」 | **PASS** |
| UI 저장 왕복 | 저장 버튼 클릭 → 토스트 「AI 작업 설정을 저장했습니다.」 → 재조회 후 값 유지 | **PASS** |

## 이 실측이 확인한 것

직전 실측이 적발한 결함(`apiFetch` 소비 계약 위반 → 정상 200 에서 예외 → 항목 0개)이
`CHG-20260902T123000` 으로 해소됐음을 **같은 경로에서** 확인했다. 서버 판정 축은
`TEST-20260902T123000-pb0008-postdeploy-1` 에서 이미 PASS(고른 모델·등급 송출 · 미보유 거절 ·
미설정 무회귀).

## 남은 것 (정직 표기)

- 이 계정(bootstrap_admin)의 러너 토큰이 만료돼 **러너가 연결된 상태의 선택지 렌더**는 이번
  창에서 재현하지 못했다. 서버 판정은 살아 있는 러너(account 10)의 실 신고로 검증했고,
  화면 축은 「러너 없음」 상태의 보존·안내만 실측했다.
- **실제 능동 분석 실행이 고른 모델·등급으로 dispatch 되는지**(러너 로그 `kind=job` 의
  `model`·`effort`)는 사용자 러너가 연결된 다음 실행에서 확인된다 — 서버가 보내는 값은
  배포본 코드로 실측 완료(`sent=claude:haiku effort='medium'`).
