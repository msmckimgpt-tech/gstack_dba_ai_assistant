---
run_at: 2026-08-12T18:30:00+09:00
session: ai/claude/feature-0003-attach-md-highlight
scope: unit/feature-0003-agent-web-ui/src/static/code-highlight.js (+ css/base.css·css/chat.css 주석)
verdict: PASS  # 하네스 146 PASS + PB-0008 실 Windows Chrome/150 PASS + codex P1 0건 (2026-08-12)
---

### Run (2026-08-12) — attach-md-highlight: 첨부 `.md` 구문 하이라이트 — **Environment: Windows-browser**

#### 1. 사용자 요청

> 프로젝트 내 서비스에서, 첨부파일 중 '.md' 파일에 대한 포멧도 내부적으로 처리할 수 있도록
> 구성해주세요.

선행 cycle(`20260806T1853-attach-diff-syntax`)이 `code-highlight.js` 헤더에 남긴 예고
("1차 범위는 SQL + 구조화 데이터이며 Python·JS·Shell·**Markdown** 등은 같은 자리에 추가한다")
의 Markdown 분을 실행한 것이다. "내부적으로" = 이 모듈의 설계 원칙인 **vendor 무추가 경량
토크나이저**(외부 하이라이터 라이브러리 없음)를 그대로 따른다.

#### 2. 범위 확정 — 서버 쪽은 이미 열려 있었다

요청 문구가 "포맷 처리" 라 서버 파이프라인부터 훑었고, `.md` 가 막혀 있는 지점은 **한 곳뿐**이었다:

| 표면 | `.md` 상태 | 조치 |
|---|---|---|
| `routers/conversations.py` `_EXTENSION_KIND_MAP` | `md`·`markdown` → `text` (기존) | 무변경 |
| `_MIME_KIND_HINTS` `text/markdown` | `text` (기존) | 무변경 |
| `_VERSION_DIFF_TEXT_KINDS` = `("text","csv")` | 도달 (기존) | 무변경 |
| 원문 보기 `ATTACH_SOURCE_VIEWABLE_KINDS` | 도달 (기존) | 무변경 |
| `_ASSISTANT_NEW_ALLOWED_EXT` | `md`/`markdown` 포함 (기존) | 무변경 |
| **`static/code-highlight.js` `LANGS`** | **미등록 → 무색 평문** | **본 cycle** |

즉 `.md` 첨부는 이미 업로드·인라인·diff·원문 보기까지 되지만 화면에서 **구조가 산문과 같은
색**이었다. 백엔드·라우터·RBAC·스키마·마이그레이션 변경 **0**.

#### 3. 검증 — 자동 하네스

`unit/feature-0003-agent-web-ui/tests/verify_attach_diff_syntax_highlight.mjs` (Node18 + jsdom@22)

```
OK — 146 passed, 0 failed        (선행 113 → +33: A15~A19 · B37~B55 · D8 · H13~H14 · I3~I4
                                  + codex 적대 리뷰 회귀분 B47b/B47c/B47d/I3b)
```

- **A15~A19 판정**: `.md`/`.markdown` → `md`, 대문자·경로·쿼리 꼬리, **서버 지도에 없는
  별칭(`mdx`/`mdown`)은 미등록**(거짓 도달 주장 금지), 라벨 `Markdown`, 기존 확장자 무탈취.
- **B37~B50 토큰 계약**: 제목(줄 전체 keyword) · 리스트 마커/체크박스 · 강조/인라인코드 ·
  인용/fence(+info string) · 구분선/setext · 표 파이프(delim)/정렬행 · 링크(라벨 func /
  URL string / 대괄호 punct) · 이미지 · 자동링크 · 참조정의(key).
- **B51~B55 오색 금지(negative)**: `snake_case`·`__dunder__` 미강조(`_강조_` 의도적 미지원) ·
  `2 * 3 * 4` 미강조 · 산문 속 `-`/`#` 비구조 · 백슬래시 이스케이프 · **순수 산문 줄 = 토큰 1개**.
- **C1/C2 무손실**: 표본 22건 + fuzz **1,400건** (알파벳에 `~|+` 추가) 전부 byte 동일.
- **D8 XSS**: `[클릭](javascript:…)`·`<img onerror>` 를 포함한 줄에서 anchor/img/script **0**,
  span 만 생성, 원문 텍스트 보존.
- **H13/H14 어포던스 배선**(§16.7 G3): `README.md` 첨부로 **실제 diff 모달을 몰아** 셀이 칠해지고
  토글 라벨이 `Markdown 구문 색` 으로 뜨는지 + 본문 무손실.
- **I1~I4 비용**: 적대 입력 최악 `0.723ms/line`(<1.0) · 성장률 `1.98×`(<3.0) ·
  I3 "토큰 4,000개 방출" 이 공통 바닥(csv) 대비 **0.07×** · I3b 병리 파이프 줄 토큰 **1개**(csv 4,000) ·
  I4 산문 920자가 **토큰 1개 0.002ms**.

형제 하네스 회귀 0 — `verify_attach_source_view.mjs` 77 PASS · `verify_attach_version_diff.mjs`
125 PASS · `verify_attach_diff_identical_source.mjs` 61 PASS.

#### 3b. 적대 리뷰 (§18.8 — codex 채널, `[CODEX:attach-md-highlight]`)

세션의 상위 우선순위 도구 제약(Agent tool 무단 호출 금지) 하에서 §18.8.2 의 "제약 없는 채널
우선" 을 따라 `codex exec -s read-only` 로 staged diff 를 적대 리뷰했다. **[P1] 0건 → GATE PASS**,
[P2] 3건 전부 처리:

| # | 지적 | 판정 | 조치 |
|---|---|---|---|
| P2-1 | `\|` 마다 span 생성 → 병리 입력에서 DOM 노드 폭증(4,000자 → span 4,000개) | **유효** | `\|+` 로 연속 파이프를 한 토큰으로 묶음. 실제 표는 파이프가 붙어 있지 않아 **화면 무변경**, 병리 입력은 토큰 1개(0.83ms → 0.058ms). 회귀 잠금 B47d·I3b |
| P2-2 | 표 정렬행 판정 과대 — `- \|` 도 매칭돼 리스트 항목이 줄 전체 회색 | **유효(실 오색)** | 셀 문법(`:?-+:?`) 확인 + "선두 `\|` 없으면 2셀 이상" 요구로 축소. 회귀 잠금 B47b·B47c, PB-0008 캡처 L27 에 실물 포함 |
| P2-3 | 시나리오가 배포 모듈 대신 토크나이저 사본을 주입 → 배포본 로드·배선 실패에도 PASS(fail-open) | **유효(증거 한계)** | 시나리오에 **배포본 실물 probe** step 추가(`import('/static/code-highlight.js')` 후 `LANGS.md` 유무 보고). 배포 전 실측 `has_md:false · langs:sql,json,yaml,xml,csv,tsv` 로 baseline 확보 — 배포 후 같은 시나리오 재실행이 `has_md:true · detect_readme:"md"` 로 뒤집혀야 한다(POST-DEPLOY 축). 배선 축 자체는 jsdom H13/H14 가 **실 모듈 + 실 `attach-diff.js` 렌더 경로**로 별도 커버 |

#### 4. 검증 — PB-0008 실 Windows 브라우저 (완료 hard gate)

- **Runner**: AI (`bin/win-browser.py run --scenario
  unit/feature-0003-agent-web-ui/src/scenario.attach-md-highlight.json`)
- **Bridge**: `relay` · endpoint `http://172.26.144.1:9243` · Chrome/150.0.7871.128
- **세션 격리(§16.6 v3.44.0 MUST)**: 공유 기본 포트/프로파일을 쓰지 않았다 —
  `WIN_BROWSER_CDP_PORT=9242` · `WIN_BROWSER_RELAY_PORT=9243` ·
  `WIN_BROWSER_PROFILE=C:\Users\mckim\AppData\Local\win-browser-cdp-mdhl-ae8acab5` 로
  **이 세션이 직접 띄운 인스턴스**(`launch` 응답 `"reused": false`)에서만 조작했다.
  evidence identity 는 주입 마커 `md-highlight-pb0008-ae8acab5` 로 대조한다(§16.6 (c)).
- **대상**: `https://localhost/` (배포된 `css/base.css`·`css/chat.css` 실 스타일시트) 위에
  **이번 cycle 의 토크나이저**를 주입해 `table.attach-diff-table.is-source` +
  `td.attach-diff-code` 실 구조로 30행 markdown 표본 렌더. 라이브 데이터 변경 **0**(합성 DOM만).
- **배포본 baseline (step 3 probe)**: `served_module=loaded` · **`has_md=false`** ·
  `langs=sql,json,yaml,xml,csv,tsv` — 이번 변경이 아직 라이브에 없음을 실물로 확인(POST-DEPLOY
  재실행 시 `has_md=true`·`detect_readme="md"` 로 뒤집혀야 한다).
- **결과** (step 4 eval 반환):
  `lossless=true` · `rows=31` · `tokenSpans=46` · `foreignTags=0` ·
  `cssLoaded=#7c3aed`(배포 CSS 도달 확인) ·
  실측 computed 색 = keyword `rgb(124,58,237)`/600 · type `rgb(21,94,117)` ·
  string `rgb(146,64,14)` · func `rgb(29,78,216)` · key `rgb(3,105,161)` ·
  comment `rgb(90,88,82)` · punct `rgb(98,95,85)` · delim `rgb(98,95,85)`/**700** ·
  bool `rgb(124,58,237)` — 전부 `base.css` 정본과 일치.
- **Evidence** (판독 가능 확대 캡처 — 전체화면 축소본만으로 마치지 않음, §16.6):
  - `artifacts/pb0008/attach-md-highlight/01_md_highlight.png` — 30행 개관
  - `artifacts/pb0008/attach-md-highlight/02_md_zoom_head.png` — zoom 2.2 상단(1~20행)
  - `artifacts/pb0008/attach-md-highlight/03_md_zoom_tail.png` — zoom 2.2 하단(7~30행)
- **육안 판정 (PASS)**: 제목(L1/L6/L16) 보라 굵게 · 인라인코드(`` `orders` ``) 앰버 ·
  링크 라벨 파랑 + URL 앰버 · 표 파이프 굵은 회색 + **정렬행 전체 회색** · `**PK**`·
  `~~deprecated~~` 청록 · 인용 `>` 회색 + fence ` ```sql ` 회색+`sql` 청록 · `---` 회색 ·
  `- [x]`/`- [ ]` 마커 회색 + 체크박스 보라 · **L27 `- | 는 …` 이 리스트 마커 + 파이프로 갈리고
  줄 전체 회색이 아님**(codex P2-2 수정 실물 확인) · **L29 산문의 `2 * 3 * 4`·`snake_case`·
  `#hashtag` 전부 무색**(오색 0) · `[ref]:` 라벨 파랑.
- **시각 불변식(§16.7 G9-a)**: 형제 행 크기 균일 · 위계 비역전(제목 > 산문) · 긴 줄이
  `pre-wrap` 으로 접히며 컨테이너 팔출 0 · 가로 스크롤 0.

#### 5. 알려진 한계 (정직 표기)

- **fenced code block 내부**: 라인 독립 판정이라 여는/닫는 ``` 사이의 줄도 markdown 규칙으로
  읽힌다(캡처 L19 의 SQL 은 markdown 표식이 없어 무색으로 떨어져 무해했지만, 코드 안
  `# comment`·`- item` 은 각각 제목색·마커색을 받는다). SQL 의 여러 줄 주석과 **같은 성격의
  기존 절충**이며(모듈 헤더 "라인 독립 토큰화"), 상태를 이어붙이면 맥락 축약 뷰에서 색이
  통째로 어긋난다.
- **`_강조_` 미지원**: 의도적. 이 화면에 오는 `.md` 는 DB·SQL 문서가 다수라 `snake_case`·
  `__dunder__` 가 흔하고, 인식하면 **없는 강조를 만든다**("무색 > 오색").
- **대괄호 중첩 라벨**(`[see [1]](u)`)은 무색으로 떨어진다 — 성능 방어(라벨에서 `[` 제외)의
  대가이며 손실은 없다.
- **라이브 `.md` 첨부 실물 대조는 배포 후 잔여**: 본 Run 은 배포된 CSS + 실 DOM 구조 위의
  주입 렌더이며(step 3 probe 가 배포본에 아직 md 가 **없음**을 명시적으로 기록한다),
  "배포된 ESM 이 실제로 로드·배선되는가" 는 배포 후에만 확인 가능하다. POST-DEPLOY 로 ①
  같은 시나리오 재실행(step 3 probe 가 `has_md:true` 로 뒤집힘) ② 실제 `.md` 첨부의 원문
  보기 화면 1건 확인을 이월한다(본 fragment 에 Run append).

#### 6. 정리

`python3 bin/win-browser.py down` 으로 **본 드라이버가 띄운 인스턴스만** 종료(사용자 일반
브라우저 보존). 전용 프로파일이므로 다른 세션 탭에 무접촉.
