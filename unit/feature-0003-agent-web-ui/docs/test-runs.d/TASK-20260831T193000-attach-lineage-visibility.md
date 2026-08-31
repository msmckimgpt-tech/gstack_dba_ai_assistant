---
run_at: 2026-08-31T19:30:00+09:00
session: ai/claude/feature-0003-attach-lineage-viz
scope: 첨부 계보 비교 가시성 재설계 (그룹 카드 · 분기 레일 · 그룹 레벨 비교 · 정체성 칩 · 크기 델타)
verdict: PASS
---

## Run — TASK-20260831T193000-attach-lineage-visibility (PRE-DEPLOY 라이브)

- Date: 2026-08-31
- Environment: **Windows-browser** (PB-0008, `bin/win-browser.py` + 실 Windows Chrome 151)
- Target: 격리 검증 컨테이너 `web-verify-lineage` — 라이브 web 이미지 `mysql-ai-web:current`
  + **브랜치 static 트리를 stamp 재주입 후 bind-mount** (`/var/tmp/attach-lineage-static`,
  stamp `4162a8293d1c`), `https://localhost:18098`
- 데이터: 라이브 대화 `20260831093200-02b3d60e` — 같은 파일명에 계보 2개씩 실재
  (`IMMEDIATE_LEAVE_MEMBER.sql` · `ND_MIGRATION_RESET.sql`)
- Result: **PASS**

> **왜 격리 컨테이너인가**: JS 변경은 `docker cp` QA 가 성립하지 않는다(asset stamp 미주입 →
> HTML 은 `?v=<hash>`, 주입한 모듈은 `?v=dev` → **같은 모듈이 두 URL 로 이중 인스턴스화**).
> 그래서 브랜치 static 트리에 `inject_asset_stamp.py` 를 **실제로 돌려** 프로덕션과 같은
> 스탬프 경로를 재현했고, 새 스탬프가 곧 캐시 무효화라 Chrome 모듈 캐시 오염도 함께 배제된다.
> 공유 트리(`repo/`)·라이브 web-a/b 는 **건드리지 않았다**(§13.2.9 격리 경로).
>
> ⚠ 첫 시도(스탬프 미주입 bind-mount)는 Chrome 모듈 캐시가 **구버전을 실행**해 `groups: 0`
> 이 나왔다. 그 관측을 "미구현" 으로 읽지 않고 캐시 축을 갈라낸 것이 이 Run 의 전제다.

## 1. 구조 실측 (DOM)

| 관측 | 값 |
|---|---|
| `.attach-lineage-group` (그룹 카드) | **2** |
| `.attach-list-entry` | 4 |
| `.attach-list-entry.in-lineage-group` | **4** (전건이 카드 안 — 평면 잔존 0) |
| `.attach-list-entry.is-branch` | **2** (갈라져 나온 계보만) |
| `.attach-lineage-group-cmp` (그룹 비교) | **2** |

렌더 텍스트(발췌):

```
IMMEDIATE_LEAVE_MEMBER.sql   계보 2   ⇄ 계보 비교
  📎 IMMEDIATE_LEAVE_MEMBER.sql  [사용자 계보]
     1KB · 18:32 · uploaded · 상세 ▾
  📎 IMMEDIATE_LEAVE_MEMBER.sql  [v2 · AI 수정] [⤷ AI 계보]
     9KB · +8KB · 19:01 · uploaded · 버전 2개 ▾
```

## 2. 픽셀 실측 (시각 캡처 — §16.6 픽셀-클래스)

레이아웃·정렬·들여쓰기 변경이므로 element 상태로 대체하지 않고 **판독 가능한 캡처**를 확보했다
(전체화면 캡처는 패널이 작아 판독 불가 → DOM 복제 2.2~2.6배 확대 캡처로 escalate).

- `lineage-final.png` — 실 패널 자연 폭. 그룹 카드가 두 계보를 감싸고, 무관한 파일과 시각적으로
  분리된다. 펼친 버전 박스도 카드 안에 중첩된다.
- `lineage-zoom.png` / `lineage-zoom2.png` — 확대. 레일(세로줄) + elbow(가지)가 실제로 그려지고,
  분기 계보가 한 단 들여쓰기된다. 240px 최소 폭에서 그룹 머리는 **잘리지 않고 2줄로 접힌다**.

### 경계 양측 (§16.7 G4)

| 경계축 | 아래쪽 | 위쪽 |
|---|---|---|
| 계보 수 | 1개 → 카드 없음(평면 유지, 종전과 동일) | 2개 → 카드 + 레일 + 그룹 비교 |
| 패널 폭 | 240px(최소) → 머리 wrap, 버튼 무손실 | 자연 폭 → 1줄 |
| 계보 내 버전 수 | 1 → 토글 `상세 ▾` | 2 → 토글 `버전 2개 ▾` |

## 3. 색축 실측 (computed)

| 요소 | computed color |
|---|---|
| 그룹 안 파일명 | `rgb(128,125,114)` (낮춤) |
| 사용자 계보 칩 | `rgb(128,125,114)` (중립) |
| AI 계보 칩 | `rgb(37,99,235)` (파랑) |

> 이 실측이 **결함 1건을 잡았다**: 인접 규칙이 쓰던 `var(--muted)` 는 이 저장소에 정의되지
> 않은 토큰이라 조용히 무시됐고, 사용자 계보 칩이 본문색(`rgb(38,37,30)`) 그대로 렌더돼
> AI 칩과의 색 대비가 성립하지 않았다. CSS 를 읽는 것만으로는 드러나지 않는다 — computed
> 실측이 유일한 backstop. `--text-muted` 로 교정 후 재실측해 위 값을 얻었다.

## 4. 인터랙션 실측 (§16.6 — 복수 surface 개별 실행)

### surface ① 그룹 머리 `⇄ 계보 비교` (신규)

클릭 1회 → 모달:

| 관측 | 값 |
|---|---|
| `aria-label` | `첨부 계보 비교` |
| 제목 | `계보 비교 — IMMEDIATE_LEAVE_MEMBER.sql` |
| 활성 축 | **`time`** (계보 간(시간순)) |
| 기준 / 비교 | `사용자 업로드 v1 · 현재` / `AI 수정본 v2` |
| diff 통계 | `+182 / -21` (실 내용 차이) |

계보를 **펼치지 않고** 한 번에 착지한다(종전 2단계). 축이 `time` 인 것이 핵심 — 이 계보에
버전이 여럿이면 종전 기본값은 버전 축이라, 계보를 보러 눌러도 버전 화면이 떴다.

### surface ② 버전 박스 안 `⇄ 계보 비교` (기존, 회귀 확인)

`상세 ▾` → 박스 렌더 → 버튼 클릭 → 축 `time` · 제목 `계보 비교` · `+182 / -21`. 종전 동작 유지.
박스의 계보 안내는 압축된 문구로 렌더: `사용자가 올린 계보 · 파일 1개 · 다른 계보 1개`.

## 5. 회귀

- pytest `unit/feature-0003-agent-web-ui/tests` + `unit/feature-0002-agent-core/tests` **전건 PASS**
  (신규 `test_attach_lineage_group_ui.py` 18건 포함, 선행 `test_attach_lineage_ui.py` 무수정 통과)
- `node --check` (ESM) — `composer.js` · `attach-diff.js` PASS

## 6. 잔여

- POST-DEPLOY 재확인은 배포 후 별도 Run 으로 기록한다(본 Run 은 PRE-DEPLOY 격리 실측).
- 크기 델타는 **바이트 차이**이며 내용 차이가 아니다 — 문구·title 이 그 경계를 밝히고, 실제
  내용 차이는 비교 모달의 `+N / -N` 이 담당한다.

---

## Run 2 — 적대 리뷰(codex) 조치 후 재실측 (PRE-DEPLOY 라이브)

- Date: 2026-08-31 · Environment: **Windows-browser** (PB-0008), 같은 격리 컨테이너
  (stamp `c9174638b56c` 로 재주입)
- Result: **PASS**

1라운드 codex 지적(P1 1 · P2 6 · P3 2)을 조치한 뒤, **선언이 아니라 성립**을 라이브에서 다시 쟀다.

| 조치 | 라이브 실측값 |
|---|---|
| 카드 접근성 그룹 | `role="group"` · aria-label `IMMEDIATE_LEAVE_MEMBER.sql — 같은 이름의 계보 2개` |
| 분기 표식(데이터 기반) | `.is-branch` **2** — 서수가 아니라 `_originId > 0` 로 판정 |
| 행 접근성 이름 | `…(사용자 계보, 2개 중 1번째) 원문 보기` / `…(AI 계보, 갈라져 나옴, 2개 중 2번째) 원문 보기` |
| 토글 상태 노출 | `aria-expanded` **false → true → false** (열기·닫기 왕복 실측) |
| 대비 — 카드 테두리 | `rgb(168,165,152)` = `#a8a598` (종전 `#e6e5e0`, 카드 배경 대비 **1.10:1**) |
| 대비 — 레일/elbow | `rgb(140,138,124)` = `#8c8a7c` (카드 대비 **3.02:1**, 2px) |
| 대비 — 정체성 칩 | `rgb(90,88,82)` = `#5a5852` (흰 배경 **7.11:1**) |
| 대비 — 낮춘 파일명 | `rgb(107,105,96)` = `#6b6960` (**5.51:1**, 종전 `#807d72` 는 4.12:1 로 AA 미달) |

- 픽셀 재확인(`lineage-final2.png`, 2.4배): 레일·elbow 가 배경에서 분리돼 보이고, 분기 계보의
  들여쓰기와 파선 칩이 판독된다. 위계는 **파일명(낮춤) < 정체성 칩(승격)** 으로 뒤집혔다.
- 회귀: pytest `feature-0003` + `feature-0002` **4986 passed / 5 skipped** · `node --check` PASS
- 새 회귀 9건 추가(총 28건) — 각 조치를 **구조로** 잠금(§16.7 G10): 분기 판정이 서수로 되돌아가는
  것 · 계보수 title 의 파생 주장 · stale 가드 순서 · `role=group` · 행 접근성 이름 · `aria-expanded`
  3지점 · 미상 크기의 `|| 0` 흡수 · 대비 floor.

---

## Run 3 — 적대 리뷰 2라운드 조치 후 재실측 (PRE-DEPLOY 라이브)

- Date: 2026-08-31 · Environment: **Windows-browser** (PB-0008)
- Target: 격리 컨테이너 `web-verify-lineage` — static(stamp `52b44e6b53f8`) **+ 변경된 라우터
  2종**(`attachments.py`·`_conv_store.py`) bind-mount. 2R 조치는 백엔드도 건드리므로 static 만
  주입해서는 검증이 성립하지 않는다.
- Result: **PASS**

### P1-1 — 계보 축 부재 시 조용한 격하 차단 (양측 실증)

| 경우 | 관측 |
|---|---|
| 정상 (`lineages` 2건) | 모달 **열림** · 축 `time` · 제목 `계보 비교` · `+182 / -21` |
| 해소 실패 재현 (fetch 스텁으로 `lineages: []`) | 모달 **미개봉** · 토스트 「계보 정보를 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.」 |

종전이라면 두 번째 경우에 **버전 비교**가 조용히 열렸다 — 사용자가 누른 것과 열리는 것이 다른
조용한 오답. 이제 못 하면 못 한다고 말한다.

### P1-2 — 무음 절단 차단 (경계 양측 실증, §16.7 G4)

로더 직접 호출(컨테이너 안 `_load_filename_lineage_heads`):

| limit | heads | `_lineage_heads_truncated` |
|---|---|---|
| 1 | 1 | **True** |
| 2 | 2 | False |
| 20 | 2 | False |

응답: `/api/attachments/1259/versions` → `{"lineages": 2, "lineages_truncated": false}`.
모달: `lineages_truncated: true` 재현 시 「계보가 많아 최근 20개만 나열합니다」(`role="status"`,
`offsetParent` 실재 = 실제 렌더) 표시. 종전에는 20개에서 말없이 잘려, 카드가 「계보 21」을
말하는데 선택지는 20개뿐인 상태를 사용자가 알 길이 없었다.

### 회귀

pytest `feature-0003`+`feature-0002`+`feature-0023` **4997 passed / 5 skipped** ·
`node --check` (composer/attach-diff) PASS · `ast.parse` (attachments/_conv_store) PASS.
