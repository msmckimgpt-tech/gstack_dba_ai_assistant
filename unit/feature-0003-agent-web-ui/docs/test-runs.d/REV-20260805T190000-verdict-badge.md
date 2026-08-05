### REV-20260805T190000-verdict-badge 노드 상세 판정 배지 (Minor §12.3, 2026-08-05, feature-0036 ← feature-0003 web/UI) — **Environment: Windows-browser — DEFERRED(배포 후)**

- 무엇: 그래프 뷰 노드 상세의 'AI 능동 분석' 박스에, 그 분석문의 사실성 판정을 배지 + 근거 한 줄로
  표시한다(`supported` / `contradicted` / `unverifiable`). 백엔드가 **현재 분석문 해시와 일치하는
  판정만** 싣기 때문에, 미판정·판정 실패·분석문 갱신 직후에는 아무것도 그리지 않는다.
- 기대(라이브 실측 항목):
  1. 판정이 있는 테이블 노드를 열면 역할 칩 아래에 판정 배지가 보이고, 그 아래 근거 한 줄이 보인다.
  2. `contradicted` 는 채움 배지(주황 #D55E00·흰 글자), `supported`/`unverifiable` 은 테두리 배지 —
     역할 칩(채움)과 시각적으로 구분된다.
  3. 판정이 없는 노드에는 배지도 근거도 **없다**(빈 자리·깨진 마크업 없음).
  4. 요약·관계·활용·주의 기존 4행이 그대로 렌더된다(회귀 없음).
- **PB-0008 Windows-browser 라이브 실측 — DEFERRED(배포 후)**: 그래프 정적 자산(`graph-ctxmenu.js`)이
  web 이미지에 baked 되고 판정 필드는 배포된 백엔드(`node_analysis.get_node_analysis`)에서 오므로,
  미머지 상태에서는 라이브 무접촉으로 두 층을 함께 띄울 수 없다. 배포 후 실 Windows Chrome via
  `bin/win-browser.py` relay + 로그인 세션에서 위 1~4를 실측하고 본 fragment 에 Run 을 append 한다.
- de-risk (배포 전 확보한 근거):
  - ESM `node --check` PASS (`graph-ctxmenu.js`).
  - 백엔드 계약 단위 테스트 8건 PASS — 해시 일치 시 노출 / **불일치 시 미노출** / 판정 부재 시 키 부재 /
    조회 실패 시 상세 패널 정상 / savepoint / 프론트 렌더 분기·이스케이프 소스 단정.
  - 렌더는 기존 `admin-meta-graph-badge` + `admin-meta-graph-muted` 클래스 재사용(신규 CSS 0) —
    바로 위 역할 칩과 동일 구조라 레이아웃 회귀면이 좁다.
  - 조건부 렌더가 `res.verdict && V[res.verdict.verdict]` 단일 게이트라, 필드 부재 시 기존 화면과
    byte-동치(추가 노드 0).
- Pass/Fail: **PASS(코드/유닛 범위)** — 라이브 시각 실측은 배포 후 잔여. Runner: AI.

- **PB-0008 Windows-browser 라이브 실측 — PASS** (Environment: Windows-browser, 2026-08-05, 실 Windows
  Chrome via `bin/win-browser.py` relay, 배포본 `2a1089eb`, `https://localhost/admin` 로그인 세션):
  1. **판정 있는 노드에 배지 + 근거** — `mysql-ddae8975d793:log_v2.tf_log_09_league_result`(stage 1)에서
     `⚠ 표본 통계와 어긋남` 배지 + `판정 근거 — LeaguePoint_New 최댓값이 1244로 분석에서 명시한
     '0~1238 범위' 클레임과 어긋납니다.` 렌더 확인. tooltip = "표본 통계와 대조 · 증거 수집 단계 1 ·
     2026-08-05 18:48". 증적: `evidence/verdict-badge-stage1-live.png`.
  2. **역할 칩과 시각 구분** — 같은 박스에서 역할 칩(`📜 로그·이력`, 채움 #E69F00)과 판정 배지
     (`--tag-danger-*` 연한 배경 + 진한 글자)가 명확히 구분됨(스크린샷). 적대 패널이 지적한
     "같은 색·같은 모양 두 배지" 상태가 해소된 것을 실화면에서 확인.
  3. **stage 분기** — `mssql-ee7d238cd884:masangsoftweb.masangsoft_documents`(stage 0)에서
     `⚠ 구조와 어긋남` + tooltip "표본 없이 구조만 대조(컬럼명·타입·행수 추정) · 증거 수집 단계 0".
     `masangsoftweb.NX_PLAY_LOG`(supported·stage 0)는 `구조와 모순 없음`. 라벨이 대조 기준을
     구분해 말하는 것을 실측(ADR-0036-10 의 핵심 요구).
  4. **판정 없는 노드** — `masangsoftweb.Creator_Sponsorship`(분석 있음·판정 없음)에서 판정 배지 0개,
     `AI 표본 대조 판정` 라벨 없음, `판정 근거` 없음, **빈 `<p>` 0개**, 나머지 5개 문단(역할·요약·
     관계·활용·주의) 정상 렌더 — 회귀 없음.
- Pass/Fail: **PASS** (실 Windows 브라우저 4항목 실측 + 스크린샷). Runner: AI.
