---
run_at: 2026-09-08T10:10:00+09:00
session: ai/claude/feature-0043-live-model-list-record
scope: 배포 후 라이브 종단 — 카탈로그 → 서버 → 사용자 화면에 모델 목록 도달
verdict: PASS
---

### Run (2026-09-08) — 배포본 종단 실측 — **Environment: Windows-browser (설치본 앱 창 + CDP)**

배포 `067e4a58` · 러너 배포본 지문 `f37a629e2003`(직전 `ee0453d7c445`).

#### 1. 사용자 계정(`admin`, AccountId=10) — 러너 기동부터 화면까지

러너를 **설치본과 같은 방식**으로 띄웠다(DQA Connect 동봉 런타임 + `--ai codex` +
`--base https://112.185.196.20`). 토큰은 앱 창의 사용자 세션이 `/api/ai/connect/token` 으로
발급했고, 값은 임시 파일로만 옮겨 프로세스 인자·로그·대화 어디에도 남기지 않았다.

| 시각 | `RunnerCapabilities` | 비고 |
|---|---|---|
| 기동 직전 | `[]` (2바이트) | 토큰 312 — 15시간 전 자기갱신 이후 정지 |
| +7초 | `[]` (2바이트) | 토큰 317 첫 하트비트 |
| **+30초** | **591바이트** | codex 7종 + 등급 4단계 |

신고 내용: `gpt-6-astra` · `gpt-5.6-sol` · `gpt-5.6-terra` · `gpt-5.6-luna` · `gpt-5.5` ·
`gpt-5.4-mini` · `gpt-5.3-codex-spark` / 등급 `low`·`medium`·`high`·`xhigh`.

서버 응답(`/api/api-vault/options`, 앱 창의 사용자 세션): `model_selector: "visible"` ·
`model_selector_source: "runner"` · 7종 · `default_model: "codex:gpt-6-astra"`.

**앱 창 화면**(사용자 본인 계정·본인 대화 트리): `+` 메뉴에 「모델: GPT-6-Astra」·
「추론 강도: 높음」이 있고, 모델 메뉴가 `CODEX` 그룹 7종을 렌더한다.
안내 문단(`#composerActionsSelectorNote`) **없음**, 칩 「대기 중」 2문단 툴팁,
`.sidebar-profile` bottom **781** ↔ `.composer-wrap` bottom **781** 일치.
Evidence: `/tmp/win-browser-shots/shot_20260908_101041.png`.

#### 2. 검증 계정(`bootstrap_admin`, AccountId=1) — 같은 경로 재현

같은 절차로 codex 러너를 띄워 caps 591바이트 · 화면 7종을 확인했다(스크린샷
`step_13_20260907_190206.png`). 검증 종료 후 그 러너는 정지했다.

#### 3. 독립 확인 — 손대지 않은 다른 사용자

`AccountId=27` 의 러너는 **우리가 아무것도 하지 않았는데** 새 빌드로 자기갱신해
`RunnerCapabilities` 465바이트를 신고하고 있었다. 배포가 그 경로로도 도달한다는
독립 증거다(우리 손이 닿은 계정만 되는 것이 아니다).

### 부수 관측 — 자기갱신이 러너를 죽일 수 있다 (미해결, §8 기록)

배포 시각 러너 두 대가 **11ms 간격**으로 같은 파일(`~/.dqa-connect/bridge_agent.py`)을
교체하며 `os.execv` 했고(`18:38:41.813` · `.824`), 그중 **codex 러너만 `run.start` 를 내지
못한 채 사라졌다**. 나머지 한 대는 정상 재기동했다. 클라이언트에는 러너 감시·재기동 로직이
없어(소스 검색 0건) 스스로 복구되지 않았고, 사용자 계정은 **약 15시간** 연결이 끊긴 채였다.
상세·처방은 `REPORT.md §8`.

### 정리

디버깅 포트는 측정 동안만 열었고 클라이언트를 **정상 실행으로 되돌렸다**(CDP 닫힘 확인).
임시 스크립트·프로브 디렉토리 제거. 남은 러너는 사용자 계정 1대(정상)다.
