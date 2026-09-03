# TASK-20260903T210000 — 연결 칩 CSS 가 dark-mode 블록에 갇혀 있었다

- verdict: PASS (PRE-DEPLOY)
- 적발 경로: 실 Windows 브라우저(PB-0008) + `getComputedStyle`

## 1. **Environment: Windows-browser** — 실 브라우저 실측 (결함 적발 경로)

Run: `bin/win-browser.py goto --url https://localhost/` → `eval --script` (PB-0008,
실 Windows Chrome · 라이트 모드). 이 결함은 **이 경로만이** 적발할 수 있었다 — 자동
문자열 축은 "규칙이 파일에 있다" 만 증명하고, 그것이 이번 결함을 놓친 정확한 한계였다.

배포 `0d641ea8` 직후, 러너를 「확인 중」 상태로 만든 뒤 (`ai_ready=null`, `listening=true`):

```json
{"http":200,"logged_in":true,"has_ai_ready_key":true,
 "ai_ready":null,"listening":true,
 "chip":{"text":"확인 중","state":"checking",
         "title":"연결된 AI 가 답할 수 있는지 확인하는 중입니다. 러너는 실행 중이지만 …"}}
```

여기까지는 통과 — API·JS 배선은 정상이다. 그런데 색을 재자:

```json
{"checking":{"state":"checking","text":"확인 중",
             "color":"rgb(0, 0, 0)","bg":"rgba(0, 0, 0, 0)","before":"none"},
 "on_for_comparison":{"color":"rgb(21, 128, 61)","bg":"rgba(21, 128, 61, 0.08)"}}
```

`checking` 은 **무스타일**이고 `on` 은 정상이다. 규칙이 적용되지 않았다.

## 2. 지점 특정

| 관측 | 값 |
|---|---|
| 서빙 CSS 에 규칙 존재 | `data-state="checking"` **3건** (컨테이너 파일·HTTP 응답 모두) |
| 브라우저가 fetch 한 CSS | 같은 3건 (`cache: no-store` 포함) |
| **브라우저가 파싱한 스타일시트의 `checking` 셀렉터** | **0건** |
| 파싱된 마지막 규칙 | `@media (prefers-color-scheme: dark) { .ai-conn[data-state="on"] …` |

⇒ 그 `@media` 의 **닫는 `}` 가 없다.** 그 뒤 모든 칩 규칙이 dark-mode 전용이 됐다.
브라우저는 라이트 모드(`matchMedia("(prefers-color-scheme: dark)").matches === false`).

**선재 결함**: `idle`(대기 안 함)·`stale`(업데이트 필요)도 같은 블록 안에 있었다 —
「확인 중」이 들어오기 전부터 라이트 모드에서 무스타일이었다.

## 3. 수정 후 정적 실측

```
파일 최종 중괄호 깊이: 0        (0 이어야 정상)
무조건(깊이0) 규칙: {'on': 2, 'off': 2, 'idle': 2, 'stale': 2, 'checking': 2}
조건부(media) 규칙: {'on': 1, 'off': 1, 'idle': 1, 'stale': 1, 'checking': 1}
기본 규칙 없이 조건부만 있는 상태: 없음
```

## 4. 테스트

```
$ pytest unit/feature-0003-agent-web-ui/tests/test_conn_chip_css_scope.py
9 passed in 0.06s
```

⭐ **결손 재주입** — 닫는 `}` 를 다시 제거하고 두 테스트 집합을 돌렸다:

| 테스트 집합 | 결과 | 뜻 |
|---|---|---|
| 신규 `test_conn_chip_css_scope.py` | **5 failed**, 4 passed | 이 결함을 잡는다 |
| 직전 cycle `test_ai_ready_surfaced.py` | **19 passed** | 문자열 검사는 **눈이 없었다** |

두 번째 줄이 이 cycle 의 요지다 — 「규칙이 파일에 있다」는 「규칙이 적용된다」가 아니다.

## 5. 판정축 정정 (자기검증에서 잡은 것)

초판 검사는 「`@media` 안에 칩 규칙이 있으면 결함」이었다. 그러자 **정당한 dark-mode
덮어쓰기 5건이 전부 결함으로 신고**됐다 — 항진 검사다. 축을 「각 상태가 **무조건 규칙**을
갖는가」로 바로잡았다.

## 6. 남긴 미검증

- 이 검사는 정적이라 **캐스케이드 덮어쓰기**(더 구체적인 셀렉터가 색을 바꾸는 경우)는
  잡지 못한다. 그 축은 실 렌더 실측이 담당한다.
- POST-DEPLOY 실 브라우저 재측정은 배포 후 별 조각으로 기록한다.
