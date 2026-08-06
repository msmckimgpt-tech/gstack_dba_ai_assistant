# test-run 20260807T0620 — attach-diff-unified-bg (단일열 줄 배경 소실 회귀)

**Environment: headless-chromium (실 모듈 + 실 CSS) · jsdom · Windows-browser(라이브 진단)**

## 0. 어떻게 발견했나 — 자동 축이 전부 PASS 인 상태에서

직전 cycle 은 헤드리스 44/44 · mjs 84 · pytest 26 · PB-0008 18/18 을 **모두 통과**하고 배포됐다.
그런데 배포 후 블록 하이라이트가 **사람 눈에 읽히는지** 확인하려고 확대 캡처를 떠서 보니
단일열의 변경 줄 배경이 2열보다 확연히 옅었다. "옅어 보인다" 는 인상을 그대로 두지 않고 라이브
배포본에서 computed style 을 실측했다:

| 뷰 | 행 | 내용 | `has-content` | 배경 |
|---|---|---|---|---|
| 2열 | `is-replace` L | `b` | True | `rgba(220,38,38,0.12)` ✅ |
| 2열 | `is-replace` R | `B2` | True | `rgba(22,163,74,0.12)` ✅ |
| 2열 | `is-insert` L | (빈칸) | False | `rgb(240,239,234)` ✅ 의도된 filler |
| **단일열** | `is-delete` | `b` | **False** | **`rgb(240,239,234)`** ❌ |
| **단일열** | `is-insert` | `B2` | **False** | **`rgb(240,239,234)`** ❌ |
| **단일열** | `is-delete` | `d` | **False** | **`rgb(240,239,234)`** ❌ |
| **단일열** | `is-insert` | `D2` | **False** | **`rgb(240,239,234)`** ❌ |
| **단일열** | `is-insert` | `f` | **False** | **`rgb(240,239,234)`** ❌ |

단일열의 **내용이 있는 변경 줄 전부**가 색을 잃었다. 그리고 그 자리에 들어간 색은 내가 직전
cycle 에서 **"대응 내용 없음"** 표시로 도입한 중립 filler 다 — 색이 사라진 것보다 나쁘게
**의미가 반대로 뒤집혔다**.

## 1. 원인과 기전

- **원인**: 직전 cycle 이 줄 배경을 `.attach-diff-code.has-content` 로 좁힐 때 `_renderSplit`
  에만 `has-content` 를 부여했다(line 285-286). `_renderUnified` 는 `has-block`(accent)만 붙였다.
- **기전**: 렌더러가 **둘**인데 규칙 준수를 **한쪽에서만** 확인했다.
  - 헤드리스 `B8`/`B8b` — 배경을 **2열에서만** 봤다.
  - 헤드리스 `B7` — 단일열의 **블록 구조만** 봤다(배경 아님).
  - "두 뷰가 같은 배경 규칙을 따르는가" 라는 축이 **없었다**.

## 2. 수정 (1줄) + 재발 차단 2층

```js
if (text != null) tdTxt.classList.add("has-content");
```

패딩 행(`text == null`)은 filler 를 유지한다 — 경계 양측이 각각 옳게 동작한다.

**① 동작층 — 헤드리스(실 브라우저 computed style)**

| 축 | 단정 | 실측 |
|---|---|---|
| B9 | 단일열 변경 줄이 중립 filler 가 아니다 | PASS `delete/insert 5행 전부 danger·ok` |
| B9b | 삭제=danger · 추가=ok (2열과 같은 색 어휘) | PASS `del×3 rgba(220,38,38,0.12) / ins×2 rgba(22,163,74,0.12)` |

**② 구조층 — mjs(정적 개수 대칭)**

| 축 | 단정 |
|---|---|
| A1d | `has-content` 부여 지점 ≥3 (split 2 + unified 1) |
| A1d | `has-block` 부여 지점 ≥3 |
| A1d | 단일열이 `text != null` 로 게이트 |
| A1d | CSS 에 `:not(.has-content)` filler 규칙 실재(의미 반전의 반대편) |

구조층을 둔 이유: **새 렌더러가 추가되면 동작 테스트는 그것을 모른다.** 부여 지점 개수는 어긋난다.

## 3. 뮤테이션 역검증 — 4/4 (미포착 없음)

수정(`has-content` 부여 1줄) 제거 = **배포된 결함 상태 재현**:

| 하네스 | 결과 |
|---|---|
| 헤드리스 B9 | **red** — `[{delete,'old A',rgb(240,239,234)}, {insert,'new A',rgb(240,239,234)}, …]` |
| 헤드리스 B9b | **red** — `delete=[rgb(240,239,234)×3] insert=[rgb(240,239,234)×2]` |
| mjs A1d 부여 대칭 | **red** |
| mjs A1d 게이트 형태 | **red** |

직전 cycle 은 rAF 뮤테이션이 생존했으나(정직 표기), **이번 cycle 은 미포착 뮤테이션이 없다.**

## 4. 회귀 확인

헤드리스 **46/46**(기존 44 + B9·B9b) · mjs **88 PASS**(기존 84 + A1d 4) · 전수 mjs suite OK.
2열 배경(B8/B8b) 무변경 · 블록 accent(B6/B7) 무변경 · 스크롤 보존(S1~S6) 무변경.

## 5. **Environment: Windows-browser** — 배포 후 재검증 잔여

단일열 **확대 캡처 판독**(자동 축은 "CSS 가 적용됐다" 만 증명한다 — 이번 결함을 놓친 것이
정확히 그 한계였다) + 2열 대조 + 선행 18축 회귀.
