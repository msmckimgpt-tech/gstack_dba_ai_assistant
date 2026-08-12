---
run_at: 2026-08-12T20:30:00+09:00
session: ai/claude/feature-0003-attach-md-render
scope: unit/feature-0003-agent-web-ui/src/static/app/attach-diff.js (+ css/chat.css)
verdict: PASS  # 하네스 99 PASS(실 vendor) + 뮤테이션 전건 KILL + codex 6라운드 P1 7건 전건 반영 + PB-0008 PASS(하드 단언)
---

### Run (2026-08-12) — attach-md-render: 첨부 `.md` 를 **마크다운 문서로 렌더** — **Environment: Windows-browser**

#### 1. 사용자 요청 — 선행 cycle 의 오해석 정정

> 요구사항이 잘 못 구현되었습니다. 구문 색이 아니라, 실제 마크다운 구성으로 출력되도록
> 구현해주세요.

선행 cycle `20260812T1830-attach-md-highlight` 는 같은 요청("`.md` 포맷도 내부적으로 처리")을
**구문 하이라이트**로 처리했다. 사용자가 원한 것은 "포맷을 색으로 구분" 이 아니라 **"포맷대로
보여 달라"** — 제목이 제목으로, 표가 표로, 목록이 목록으로 보이는 것이었다. 본 cycle 이 그 정정이다.

**선행 작업을 되돌리지는 않았다**: 구문 색은 원문 보기 토글을 끈 상태와 변경이 있는 diff 화면에서
계속 쓰인다(그 화면들은 **줄 대조**가 목적이라 렌더하면 기능 자체가 사라진다). 즉 두 기능은
같은 화면의 두 모드이지 대체 관계가 아니다.

#### 2. 무엇을 만들었나

- **`_renderSource` 에 마크다운 경로**: `opts.md` 면 원문 줄 표 대신 렌더된 문서를 그린다.
  두 모달(원문 보기 · 버전 비교의 identical 화면)이 같은 함수를 쓰므로 **같은 파일이 두 화면에서
  다르게 보이지 않는다**(이 모듈의 기존 계약).
- **파이프라인 신규 제작 0**: 답변 말풍선과 **같은** `markdownToHtml`
  (`marked.parse` → enhance(diff/sql/attachment-edit/mermaid) → `DOMPurify.sanitize`)을 그대로
  import 한다. 파이프라인을 두 벌 두면 한쪽만 갱신되는 것이 이 모듈이 반복 기록한 결함 기전이다.
- **토글**: `마크다운으로 보기`(기본 켬, `localStorage attachSourceMarkdown`). 끄면 종전 원문 표.
  렌더 중에는 구문 색 토글을 **숨긴다**(칠할 원문 줄이 화면에 없어 거짓 어포던스가 된다).
- **첨부 전용 보안 하드닝** (아래 §4).
- **CSS**: `.attach-source-md` 는 `.message-content` 를 함께 붙여 타이포·코드블록·표를 상속하고,
  문서 뷰에만 필요한 것(h1~h3 위계·h4~h6·blockquote·hr·task 목록·표 wrap)만 얹는다.

#### 3. 검증 — 자동 하네스

신규 `tests/verify_attach_source_markdown.mjs` — **스텁이 아니라 배포되는 vendor 를 실제로 로드**한다
(`marked.umd.js` + `purify.min.js` 를 jsdom `runScripts:"dangerously"` window 에서 평가).
렌더 계약과 보안 경계는 그 두 라이브러리의 실제 동작이 곧 정본이라, 스텁으로는 검증이 성립하지 않는다.

```
OK — 102 passed, 0 failed       (초판 66 → codex 적대 리뷰 6라운드 반영분 +36)
```

- **A 토글 판정**(8): `.md` 만 노출 · 기본 켬 · 렌더 중 구문색 토글 숨김 · `.sql` 무회귀 ·
  바이너리/빈 문서/조회 실패에서 미노출.
- **B 렌더 계약**(12): `#`→`h1` · `##`→`h2` · 표→`table`/`th`/`td`(+전용 wrap) · `-`→`ul>li` ·
  `**`→`strong` · `` ` ``→`code` · `>`→`blockquote` · `---`→`hr` · fence→`pre>code` ·
  **마크다운 마커가 화면 텍스트에 남지 않음**(남으면 렌더 실패).
- **C 내용 보존**(5): 의미 단위 9개 전부 잔존 · 원문 복귀 시 **byte 무손실** · 구문색 토글 복귀.
- **D XSS**(7): `<script>`·`<iframe>` 0 · 인라인 핸들러 0 · `javascript:` 링크 0 · 전역 오염 0 ·
  모듈에 문자열 조립 `innerHTML` 경로 없음(sanitize 결과만 주입).
- **E 원격 리소스**(8): 교차 출처 이미지 DOM 잔존 0 · 차단 칩 노출 · 같은 출처/`data:` 유지 ·
  외부 링크 `target=_blank`+`rel="noopener noreferrer nofollow"` · 내부 링크 무변경 · 배너 표면화.
- **F 폴백**(5): 라이브러리 미로드 시 **빈 화면이 아니라** 원문 표 + 사유 배너 · 폴백 시 토글이
  화면과 일치(체크 해제 + 구문색 토글 복귀) · **저장값은 불변**(실패로 인한 강등은 사용자의
  선택이 아니므로 다음 열람에 재시도).
- **E2 우회 벡터**(18): `srcset`·`poster`·CSS `url()`·`form/input`·`svg/image`·`iframe/object/embed`·
  **프로토콜 상대 URL**(`//evil`) · **inert 파싱 구조 단언** · 첨부 전용 프로필 적용 ·
  **하드닝 단독 호출**(프로필을 우회해 들어온 조각을 2차 방어선이 잡는지 — 죽은 방어선 금지) ·
  출처 판정 단위 계약 · **mermaid 미렌더 + 코드블록 강등**.
- **G 실구동**(8): 토글 전환·영속·재오픈 복원 · **변경이 있는 diff 화면에는 토글 미노출**(줄 대조
  보존) · identical 화면은 노출+렌더 · 두 모달 저장 키 공유.
- **H CSS 배선**(8): 규칙 존재 · 위계 수치 · 주석 균형 + 셀렉터 산문 누출 0(2026-08-07 실적발 축).

**뮤테이션 역검증 7/7 KILL** — 렌더 경로 제거 · 원격 차단 제거 · `rel` 제거 · 폴백 배너 제거 ·
diff 배타 제거 · **inert template 제거(라이브 innerHTML 복귀)** · **첨부 sanitize 프로필 제거** ·
**URL 속성 축소** · **프로토콜 상대 판정 되돌림** · **폴백 토글 동기화 제거** ·
**mermaid 렌더 복원** · **mermaid 코드블록 환원 제거** · **라이브 `container.innerHTML` 주입 추가** ·
**task 글리프 변환 제거** 를 각각 넣으면 해당 축이 red.

> ⚠️ **뮤테이션이 살아남아 고친 것 3건(기록)**: ① URL 속성 축소(`["src"]`)가 통과했다 — sanitize
> 프로필이 입력을 먼저 지워서 2차 방어선이 **한 번도 실행되지 않는 죽은 코드**였다 → 하드닝을
> **직접 호출**하는 축(E2-12~14) 신설. ② mermaid 코드블록 환원 제거가 통과했다 — 하네스가
> `enhanceMermaidBlocks` 를 로드하지 않아 `.mermaid-block` 이 애초에 생기지 않았다(vacuous) →
> `mermaid-render.js` 의 실 헬퍼를 물리고 전제 단언(E2-16a) 추가. ③ `container.innerHTML` 주입이
> 통과했다 — 구조 검사가 특정 문자열만 배제했다 → **함수 본문의 모든 `.innerHTML` 대입 대상을
> 열거**하는 검사로 교체(D7). 뮤테이션이 살아남는 것은 코드가 아니라 **검사의 결함** 신호다.

**형제 하네스 회귀 0** — source-view 77 · version-diff 125 · identical-source 61 ·
syntax-highlight 146 전건 PASS.

#### 4. 보안 — 첨부는 사용자가 올린 임의 바이트다

답변 말풍선(LLM 산출물)과 같은 sanitize 를 거치지만, 그것만으로 닫히지 않는 축이 하나 있다:
**원격 리소스 fetch**. `![](https://attacker/track.gif)` 한 줄이면 그 문서를 여는 **모든 그룹
멤버**의 IP·열람 시각이 업로더가 고른 서버로 새어 나간다 — 스크립트 실행이 아니라 **로드 자체가
신호**라 DOMPurify 는 막지 않는다. 응답 헤더의 CSP 는 현재 `content-security-policy-report-only`
(실측)라 **브라우저가 차단해 주지 않는다**(보고만 한다).

그래서 sanitize **이후** DOM 에서 직접 중립화한다:

| 대상 | 처리 |
|---|---|
| 교차 출처 `img/video/audio/source/track` | 로드하지 않고 URL 을 텍스트 칩으로 대체 + 건수 배너 |
| `iframe`/`object`/`embed` | 출처 무관 제거(첨부는 문서다) |
| **`data:image/` 만 로드 허용** | 인라인이라 네트워크 요청이 없다 |
| **같은 출처 이미지도 차단** | "같은 출처면 안전" 은 틀렸다 — 이 앱엔 GET 만으로 상태가 움직이는 인증 엔드포인트가 있어 `![](/api/ai/oauth/authorize?redirect_uri=…)` 한 줄이면 **열람자 세션으로 인가 코드가 발급**된다(codex 4R [P1]). 교차 출처는 정보 유출, 같은 출처는 **권한 행사**다 |
| 교차 출처 `<a>` | 클릭 가능 유지 + `target=_blank` + `rel="noopener noreferrer nofollow"` (판정은 문자열이 아니라 **resolve 된 origin** — `//evil` 도 외부) |
| **사용자 HTML 의 `class`/`id`** | 렌더러가 만든 클래스(`language-*`·`sql-*`·`diff-*`·`mermaid-*`)만 통과 — 두면 `<div class="share-mgr-backdrop">` 한 줄로 앱 모달 스타일(`position:fixed; z-index:9999`)을 얻어 **UI 를 위장**한다. `id` 는 전량 제거(앱 요소 충돌·DOM clobbering) |
| **같은 출처 `<a>`** | **비활성화 + URL 텍스트 노출** — 클릭 한 번으로 **열람자 권한**이 쓰인다(oauth authorize 등). 문서 내 앵커(`#절`)·`mailto:` 는 예외 |
| `style` 속성 · `form`/`input`/`button` | 첨부 전용 sanitize 프로필에서 **제거** (CSS `url()` 비콘 · 인증 앱 위 피싱) |
| `srcset`·`poster`·`data`·`xlink:href` | URL 을 실어 나르는 **모든** 속성 검사 (`src` 하나만 보면 우회된다) |
| ```` ```mermaid ```` | **렌더하지 않고 코드블록으로 강등** — 렌더는 하드닝 **이후** 라이브 DOM 에 SVG 를 넣고, `themeCSS` 지시자로 외부 `url()` 을 심을 수 있다 |

**숨기지 않는다** — 무엇이 있었는지는 사용자가 알아야 하므로 URL 을 텍스트로 보여 준다.
칩 텍스트는 `textContent` 로만 넣는다(하드닝이 새 XSS 경로가 되지 않게).

**⚠️ 순서가 방어의 본체다**: 초판은 살아 있는 노드에 sanitize 결과를 먹여 파싱한 **뒤** 원격
미디어를 지웠는데, 브라우저는 **파싱 시점에 이미 요청을 시작**한다 — 최종 DOM 에서 지워도 비콘은
나간 뒤다(codex 적대 리뷰 [P1], 이 기능의 목적 자체를 무효화하던 결함). 지금은 `<template>`
(browsing context 없는 별도 문서 — 리소스를 가져오지 않는다)에서 중립화한 **뒤에** 라이브 DOM 으로
옮기므로 교차 출처 요청이 **한 번도 발생하지 않는다**.

**같은 출처 링크도 비활성화한다(5R [P1])** — 링크는 미디어와 **위험 방향이 반대**다. 교차 출처
링크에는 우리 세션 쿠키가 가지 않지만, 같은 출처 링크는 **클릭 한 번으로 열람자 권한을 쓴다**:
`[정상 문서](/api/ai/oauth/authorize?client_id=…&redirect_uri=https://evil/cb)` 처럼 라벨로 가리면
인가 코드가 공격자에게 간다. 첨부 문서가 이 앱 엔드포인트로 딥링크할 정당한 이유가 없으므로
비활성화하고 URL 을 텍스트로 노출한다. 문서 내 앵커(`#절`)와 `mailto:` 는 남긴다.

**GFM 작업 목록은 글리프로 보존**: `input` 을 프로필에서 막으면 `- [x]`/`- [ ]` 의 **체크 상태가
조용히 사라져** 두 항목이 같아 보인다(codex 3R [P1] — 요청한 기능 자체의 회귀). strict sanitize
**전에** inert template 에서 체크박스를 비대화형 글리프(`☑`/`☐`)로 치환해 상태는 살리고 상호작용
요소는 없앤다.

#### 5. 검증 — PB-0008 실 Windows 브라우저 (완료 hard gate)

- **Runner**: AI (`bin/win-browser.py run --scenario
  unit/feature-0003-agent-web-ui/src/scenario.attach-md-render.json`)
- **Bridge**: `relay` · `http://172.26.144.1:9243` · Chrome/150.0.7871.128
- **세션 격리(§16.6 v3.44.0 MUST)**: 전용 CDP 포트 9242 · 전용 프로파일
  `win-browser-cdp-mdhl-ae8acab5` · `launch` 응답 `reused:false` — 이 세션이 띄운 인스턴스만 조작.
  evidence identity 는 주입 마커 `md-render2-pb0008-ae8acab5` 로 대조.
- **대상 — 정본 구현을 그대로 실행한다**: `https://localhost/` 에서 **배포된 `app.js` 의
  `markdownToHtml`** 과 **배포된 `chat.css`** 위에, 이번 cycle 의 신규 CSS 블록 +
  `app/attach-diff.js` 에서 **잘라 온 `_renderMarkdownInto`·`_hardenRenderedMarkdown`·
  `_ATTACH_SANITIZE`·출처 판정 4함수**를 그대로 실행한다. 라이브 데이터 변경 **0**(합성 문서만).

  > ⚠️ **초판 시나리오는 증거로 성립하지 않았다(기록)**: 하드닝만 잘라 오고 렌더는 손으로
  > `md.innerHTML = markdownToHtml(SRC)` 라고 다시 썼는데, 그것은 정확히 codex [P1] 이 지적한
  > **옛 취약 구현**이다 — 즉 "고친 코드" 가 아니라 "고치기 전 코드" 를 촬영하고 있었다.
  > 정본 함수를 잘라 쓰도록 재작성 후 재실행했다(codex 3R [P2]).

- **실측** (정본 `_renderMarkdownInto` 반환 + DOM 계측):
  `renderOk=true` · `blockedMedia=2` · **`deadLinks=1`** · **`appLinksLeft=0`** · `h1=1 h2=3 h3=1 h4=1` · **`tableWrapped=1`** ·
  `li=5` · `strong=2` · `del=1` · `pre=2` · `blockquote=1` · `hr=1` ·
  **`tasks=2 tasksChecked=1`**(GFM 체크 상태 보존 — 3R [P1] 수정 확인) ·
  **`mermaidCode=1 mermaidSvg=0`**(코드블록 강등 — 2R [P1] 수정 확인) ·
  **`inputs=0`**(input·form·style·iframe 합계) · **`remoteImgs=0`** · `blockedChips=1` ·
  **`remoteAttrLeaks=[]`**(모달 body **전체**에서 자동요청 속성의 외부 출처 0) ·
  외부링크 `rel="noopener noreferrer nofollow"` ·
  위계 `h1 20px > h2 17px > h3 15px > p 14px`(**hierarchyOk=true**) · **`markersGone=true`**.
- **Evidence**: `artifacts/pb0008/attach-md-render/01_md_render.png`(전문) ·
  `02_md_render_tail.png`.
- **육안 판정 (PASS)**: 제목 위계가 밑줄과 크기로 갈리고 · **표가 실제 표**(헤더 음영·셀 테두리)로 ·
  인라인 코드가 칩으로 · `**PK**` 굵게 · `~~deprecated~~` 취소선으로 · 인용이 좌측 바로 ·
  ```` ```sql ```` 가 **다크 코드블록 + 구문색**으로 · ```` ```mermaid ```` 는 **다이어그램이 아닌
  코드블록**으로 · **`☑ 인덱스 점검 완료` / `☐ 파티셔닝 검토`** 로 체크 상태가 갈리고 ·
  중첩/순서 목록이 각각의 서식으로 · 외부 이미지 자리에 차단 칩(URL 노출) + 상단 경고 배너 ·
  `style`·`form`/`input` 은 흔적 없이 제거(문단 텍스트만 남음) · 산문의 `2 * 3 * 4`·`snake_case`·
  `#hashtag` 는 그대로 평문.
- **캡처 함정 1건(기록)**: 초판 캡처가 화면 전체 흐림으로 나와 서식·대비를 **판독할 수 없었다** —
  원인은 앱 진입 시 `body` 의 `page-fade-in` 애니메이션 도중 촬영. 시나리오에 애니메이션 종료 대기
  step 을 넣어 해소했고(재현 가능), 흐린 캡처를 근거로 PASS 선언하지 않았다(§16.6 "판독 가능한
  캡처" — 다운그레이드 금지).

#### 6. 남은 것 (정직 표기)

- **라이브 `.md` 첨부를 실제로 열어 본 대조는 POST-DEPLOY 이월**. 본 Run 은 배포된 markdown
  파이프라인 + 배포된 CSS 위의 렌더이고, 신규 `attach-diff.js` 배선은 하네스 G 축이
  **실 모듈로** 구동해 덮는다. 조합(배포된 모듈 → 실 첨부 → 화면)은 배포 후 확인한다.
- **fenced code block 안의 markdown 오색**(선행 cycle의 알려진 한계)은 이 화면에서는 **사라진다** —
  렌더 뷰에서 fence 내부는 `<pre><code>` 로 나가므로 markdown 규칙이 적용되지 않는다. 원문 보기로
  전환했을 때만 그 한계가 남는다.
- **mermaid 다이어그램은 첨부 화면에서 렌더하지 않는다**(코드블록으로 표시). 대화 말풍선에서는
  종전대로 렌더된다 — 그쪽 입력은 LLM 산출물이고, 첨부는 임의 업로드라 적대성이 다르다.
  사용자가 첨부 `.md` 의 다이어그램을 그림으로 봐야 한다면 별 cycle 에서 **생성 SVG 를 inert DOM
  에서 재정화**하는 경로를 설계해야 한다(REPORT §8 원장 후보).
- **codex 적대 리뷰 4라운드에서 [P1] 5건**이 나왔고 전건 반영했다: ① URL 속성 `src` 만 검사 ·
  프로토콜 상대 URL 우회 ② 라이브 DOM 선파싱(비콘 선행) ③ 공용 sanitize 프로필의 `style`/`form`
  허용 ④ mermaid 후처리 우회 ⑤ **같은 출처 이미지 허용 → 자동 GET-CSRF**(oauth authorize) ⑥ **같은 출처 링크 클릭 → 권한 사용** ⑦ **사용자 클래스가 앱 CSS 를 빌려 UI 위장**(`style` 을 막아도 클래스로 같은 일이 된다). ②·④·⑤·⑥·⑦ 은
  **이 기능의 목적 자체를 무효화**하거나 새 공격면을 여는 결함이었다.
- **PB-0008 이 이제 스스로 판정한다**: 초판은 "컨테이너가 보이는가" 만 보고 반환 수치는 사람이
  읽었다 — 측정이 실패해도 PASS 할 수 있었다(codex 4R [P2]). 지금은 기대값 대조를 eval 안에서
  수행하고 어긋나면 **throw** 해 그 step 이 실패한다.
- **하네스가 과잉 차단도 잡았다(기록)**: `srcset` 용 콤마 분할을 모든 URL 속성에 적용해
  `data:image/png;base64,AAAA` 가 콤마에서 쪼개져 **인라인 이미지까지 차단**되던 버그를 E4 가
  적발했다. 콤마 분할은 `srcset` 에만 적용하도록 좁혔다.

---

### Run (2026-08-12, POST-DEPLOY) — 배포본 `105fa2b7` 실측 — **Environment: Windows-browser**

배포(`bin/deploy-web.sh --web-only`, web-a/web-b `GIT_COMMIT=105fa2b7`, 엣지
`no upstreams available` **0건 = 실 무중단**) 직후, §6 에 선언한 잔여 중 **배포본 도달 축**을 닫는다.

라이브 페이지에서 **배포된 실제 모듈**(`import('/static/app/attach-diff.js')`)과 서빙
`chat.css` 를 직접 조회해 신규 배선이 도달했는지 단정했다(어긋나면 throw):

| 축 | 결과 |
|---|---|
| `_renderMarkdownInto` 존재 | ✓ |
| **inert `<template>` 파싱**(`tpl.innerHTML = safe`) | ✓ |
| 첨부 전용 sanitize 프로필 `_ATTACH_SANITIZE` | ✓ |
| 렌더러 클래스 allowlist `_RENDERER_CLASS_RE` | ✓ |
| 미디어 `data:` 한정 `_mediaLoadAllowed` | ✓ |
| 같은 출처 링크 비활성화 `deadLinks` | ✓ |
| **`_renderMarkdownInto` 안에 mermaid 렌더 호출 없음** | ✓ |
| `chat.css` 의 `.attach-source-md` · `.attach-source-md-task` 규칙 | ✓ |
| `openAttachmentSourceModal` export | ✓ (function) |

세션 격리: 전용 CDP 포트 9242 · 전용 프로파일 · `reused:false`. 검증 종료 후
`win-browser.py down` 으로 본 드라이버 인스턴스만 종료.

#### 남은 미실측 (정직 표기)

- **라이브 `.md` 첨부를 실 계정으로 열어 본 조합 대조는 하지 않았다** — 라이브 `.md` 첨부 3건은
  타 사용자 대화에 속해 열람 자체가 남의 데이터 접근이다. 경로의 조각들(배포본 모듈 도달 · 정본
  구현의 실 브라우저 렌더 · 실 모듈 배선 하네스 G축)은 각각 실측했고, **조합만 미실측**이다.
- **브라우저의 실제 네트워크 요청 발생 여부**는 계측하지 못했다(win-browser.py 가 CDP Network
  도메인을 노출하지 않는다). 방어는 **구조**(inert `<template>` 파싱 — 요청이 일어날 수 있는
  시점 자체가 없음)와 **최종 DOM 속성 census**(자동요청 속성의 외부 출처 0)로 확인했다.
  요청 계측이 필요하면 CDP Network 이벤트를 수집하는 별 도구 축이 필요하다.
