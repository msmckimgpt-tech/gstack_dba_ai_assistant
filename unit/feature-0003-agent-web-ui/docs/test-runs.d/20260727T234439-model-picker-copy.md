---
run_at: 2026-07-27T23:44:39+09:00
session: ai/claude/feature-0003-model-picker-copy
scope: [composer-model-picker, copy, layout, word-break]
verdict: PASS (PRE-COMMIT Windows-browser 실측 — 2줄→1줄·중복 배지 제거·keep-all / POST-DEPLOY 재확인 예정)
---

### Run (2026-07-27) — model-picker-copy (모델 선택기 중복 문자열 제거 + 설명 축약) — **Environment: Windows-browser (PB-0008)**

cycle: `ai/claude/feature-0003-model-picker-copy` · 사용자 지적("모델을 선택하는 화면에서 부자연스러운
줄바꿈 … 겹치는 문자열을 제거하고 의미 또한 간단명료하게 축약").

- **Runner**: AI · **Bridge**: relay @ `http://172.26.144.1:9223` · **Browser**: 실 Windows Chrome/150.0.7871.115
- **대상**: `https://localhost/` 컴포저 '+' → '모델' 메뉴 (로그인 `bootstrap_admin`), 서빙 배포본 870e1496

- **BEFORE 실측(배포본, 실 styles.css)** — 메뉴 폭 360px / desc 폭 326px, `word-break: normal`:

  | 행 | desc | 길이 | 렌더 줄 수 |
  |---|---|---|---|
  | claude-opus | `Anthropic Claude Opus (frontier 최상위, 장기 추론·에이전트 작업)` | 51자 | **2줄** ← 문제 |
  | claude-sonnet | `Anthropic Claude Sonnet (frontier, 최고 품질)` | 41자 | 1줄 |
  | claude-haiku | `Anthropic Claude Haiku (가성비, 기본값)` | 33자 | 1줄 |

  세 행 모두 `Claude` 배지 표시 — label(`claude-opus`)·배지(`Claude`)·desc(`Anthropic Claude Opus`)가
  같은 단어를 **3중 반복**. `frontier` 는 opus·sonnet 2행 중복.

- **AFTER 실측(같은 브라우저·같은 실 CSS 위에 변경안 적용)**:

  | 행 | desc | 길이 | 렌더 줄 수 | 배지 |
  |---|---|---|---|---|
  | claude-opus | `최상위 성능 · 장기 추론과 복잡한 분석` | 22자 | **1줄** | 생략 |
  | claude-sonnet | `고성능 · 품질과 속도의 균형` | 16자 | **1줄** | 생략 |
  | claude-haiku | `빠르고 경제적 · 기본값` | 13자 | **1줄** | 생략 |

  `word-break: keep-all` 적용 확인. 메뉴 높이 209px → **192px**.
  Evidence: `docs/evidence/model-picker-copy-after-sim-20260727.png`

- **변경 3지점**:
  1. `shared/model_catalog.py` — 3개 `description` 을 label·배지와 겹치지 않는 **차별점만** 담아 축약.
     세 tier 가 나란히 보이는 UI 라 동일 축(성능 등급 · 용도)으로 병렬 서술.
  2. `app.js \_renderComposerModelMenu` — label 이 group 명으로 시작하면 배지 **조건부 생략**
     (무조건 제거 아님 — Local LLM 등 provider 혼재 카탈로그에서는 배지가 그대로 살아 구분 기능 유지).
  3. `styles.css .composer-model-item-desc` — `word-break: keep-all`. 한국어 기본 규칙은 음절 사이
     어디서나 끊겨 단어 중간에서 갈라진다(BEFORE 실측). 문구를 줄인 것과 **별개의 근본 가드** —
     폭이 좁아지거나 문구가 길어져도 어절 경계에서만 끊긴다.

- **회귀**: feature-0002+0003 전체 pytest **rc=0**(fail/error 0) · `node --check app.js` OK.
  값(`value`)·라우팅·권한·저장 대화 무변경 — 표시 문자열과 CSS 1속성만.
- **POST-DEPLOY 재확인 대상**: 배포본에서 동일 1줄 렌더 + 배지 생략 육안 확인.
- **Notes**: §18.8 subagent 패널은 본 세션의 사용자 환경 정책(Agent tool 미허용)으로 미수행 —
  REVIEW 에 `[SKIPPED:session-policy-no-subagent]` 로 사유·대체검증 명시.
