---
run_at: 2026-08-06T18:55:00+09:00
session: ai/claude/feature-0003-attach-suffix-toggle
scope: unit/feature-0003-agent-web-ui — routers/{_conv_store,attachments,conversations}.py · app.py · static/{index.html,app/composer.js,css/chat.css}
verdict: PASS (pytest 78 · Windows-browser 31 step · 서버 계약 실측 · §18.8 패널 3종 흡수 후 재검증)
---

### Run (2026-08-06) — attach-suffix-toggle: 다운로드 파일명 버전 접미사 토글

#### 1. 단위 테스트 — **Environment: container (agent image, --no-deps)**

`make test` 전량 PASS (exit 0, ruff clean — 패널 흡수 후 재실행 포함). 대상 파일 단독 **78 passed**
(신규 `test_attach_suffix_toggle.py` 33 + 기존 `test_attach_manage.py` 45 — 후자는
`_zip_entry_name(with_version=…)` → `mode=…` 시그니처 전환분 9곳 갱신).

| 축 | 항목 | 결과 |
|---|---|---|
| F1~F6 | 규칙 함수 keep/strip/force · 번호 불일치 보존 · idempotent · 빈값·미지 모드 통과 | PASS |
| N1~N3 | 파라미터 정규화 · 미지 값은 400 유도(기본값 격하 금지) · caller default | PASS |
| Z1~Z2 | ZIP force 이중접미 없음 · strip 시 충돌 fallback 생존 | PASS |
| E1~E4 | 단일 다운로드 두 이름(헤더·Disposition) 일치 · 기본 저장명 보존 · 400 · 일괄 기본값 종전 재현 | PASS |
| G1~G5 | 프론트 규칙 복제 부재 · ZIP/단일 공용 함수 · 두 표면 상태 공유 · manifest=ZIP 이름 함수 · 개별 저장의 매니페스트 이름 우선 | PASS |

#### 2. 서버 계약 실측 — **Environment: preview container (bind-mount, 라이브 무접촉)**

worktree 소스를 `/app/web` 으로 bind-mount 한 별도 컨테이너(`:18099`)에 라이브 web 이미지로
기동. 라이브 스택(web-a/web-b/caddy)은 무접촉.

**단일 다운로드** (첨부 id=883, 저장명 `…_08_fix_log_tables_v2.sql`, VersionNumber=2):

| version_suffix | HTTP | X-Attachment-Download-Name |
|---|---|---|
| keep(기본) | 200 | `20260709_[MV] Log_v2 이슈 대응_08_fix_log_tables_v2.sql` |
| strip | 200 | `20260709_[MV] Log_v2 이슈 대응_08_fix_log_tables.sql` |
| force | 200 | `20260709_[MV] Log_v2 이슈 대응_08_fix_log_tables_v2.sql` |
| bogus | **400** | — |

- `strip` 이 끝의 `_v2` 만 떼고 **이름 중간의 `Log_v2` 는 보존**한다 — 번호 일치 조건이
  실데이터에서 그대로 작동함을 확인(AC-5).
- `force` 가 저장명의 기존 접미를 재부여해 `_v2_v2` 가 되지 않는다(AC-4).

**ZIP 실물 엔트리명** (`scope=all`, 버전 체인 863·883):

| 요청 | 엔트리 |
|---|---|
| 미지정(종전 동작) | `…_08_fix_log_tables_v1.sql` · `…_08_fix_log_tables_v2.sql` |
| `version_suffix=strip` | `…_08_fix_log_tables.sql` · `…_08_fix_log_tables_883.sql` |

- 미지정이 종전 이름을 그대로 재현한다(AC-6 하위호환).
- strip 시 이름이 겹치면 id 구분 접미가 붙어 **무음 덮어쓰기 0**(AC-3).
- **역검증**: 수정 전 로직(`stem = f"{stem}_v{n}"` 무조건 부착)을 그대로 실행하면
  `…_08_fix_log_tables_v2_v2.sql` — 이중접미가 실재했음을 확인.

**개별 저장 매니페스트** (`scope=all&version_suffix=strip`, 12건): `download_filename`
**12건 전부 고유**. 초판에서는 중복 3쌍이 나왔고(ZIP 만 dedup), 이를 ZIP 과 같은 이름 함수로
통일해 해소했다.

#### 3. **Environment: Windows-browser** (PB-0008 **초판**, relay @ 172.26.144.1:9223, Chrome/150)

> 아래 표의 라벨·힌트 문구는 §18.8 패널 흡수 **전** 값이다 — 최종 문구와 재실행 결과는 §5.

시나리오 `src/scenario.attach-suffix-toggle.json` — **31 step 전건 PASS**.
증거: `docs/evidence/attach-suffix-toggle/0{1..6}_*.png`

| # | 항목 | 실측 |
|---|---|---|
| T1 | 패널 토글이 첨부 목록 위에 보인다 | PASS `279×32px`, 라벨 `다운로드 파일명에 버전 표시(_v2) 포함` |
| T2 | 기본값 = 포함 | PASS `checked=true` |
| T4 | 해제가 브라우저에 기억된다 | PASS `localStorage=0` |
| T5 | 모달 체크박스가 패널 상태를 그대로 반영 | PASS `modalChecked=false, matchesPanel=true` |
| T6 | 끈 상태 + 모든 버전 → 충돌 고지 | PASS `이름이 겹치는 파일에는 구분 번호가 붙습니다` |
| T8 | 모달에서 다시 켜면 **패널도 따라간다**(역방향) | PASS `panelChecked=true, localStorage=1, hint=""` |
| T9 | 매니페스트 이름 strip/force | PASS 12건/12 고유 · force 는 `_v1`·`_v2`·`_v3` |
| T10 | 잘못된 파라미터 | PASS `400` |

**캡처 판독으로 잡은 것**: 모달의 토글이 위 두 라디오 그룹과 **같은 테두리 박스** 외형이라
"셋 중 하나를 고르는" 세 번째 그룹처럼 읽혔다. 테두리를 벗고 구분선 아래로 내렸다. 첫 수정은
화면에 반영되지 않았는데, 원인은 캐시가 아니라 **CSS 소스 순서** — `.attach-manage-suffix` 를
`.attach-manage-choice` 보다 **앞**에 두어 같은 특이성에서 뒤 규칙에 덮이고 있었다.

#### 4. 잔여 (정직 표기)

- 실제 **브라우저 저장 대화상자의 파일명**은 확인하지 않았다(자동화가 OS 대화상자에 닿지 못함).
  검증한 것은 서버가 정한 이름(`X-Attachment-Download-Name`)과 프론트가 그것을 `link.download`
  에 싣는 경로까지다.
- 시나리오의 로그인은 폼 타이핑이 브리지에서 값 주입에 실패해 `/api/auth/login` 호출로
  대체했다. 검증 대상이 로그인이 아니므로 안정 경로를 택했다. `authHidden` 판정은 goto 직후
  시점이라 실행마다 흔들리며, 이후 조작(패널 열기·모달)이 성공하는 것이 로그인 상태의 실증이다.
- `localStorage` 는 기기·브라우저 프로필 단위 — 다른 기기에서는 기본값(포함)으로 시작한다.

#### 5. §18.8 패널 흡수 후 재검증 (2026-08-06 19:30~)

codex 채널 할당량 소진(8/9 리셋) → 사용자 승인 후 subagent 패널 3종. security PASS(P3 2건),
backend/qa BLOCK, ux BLOCK — 전건 흡수 후 아래를 다시 돌렸다.

**뮤테이션 역검증(신규 테스트가 실제로 결함을 잡는가)**

| 뮤턴트 | 흡수 전 | 흡수 후 |
|---|---|---|
| `_zip_entry_name(..., mode="keep")` — ZIP 이 토글을 완전히 무시 | **69건 전건 통과**(패널 실증) | **B1·B2·B5 red** |
| manifest url 의 `version_suffix` 를 `keep` 하드코딩 | 전건 통과 | **B4 red** |

**경계 회귀(선행점·끝점)** — `os.path.splitext` 전환 후 실측:
`a.`→`a.` · `a..`→`a..` · `.`→`.` (strip 이 아무것도 떼지 않는 구간에서 이름 불변) ·
`.env`(v1) force → 단일·ZIP 두 경로 모두 `env_v1`(종전 `_v1.env` / `env_v1` 불일치 해소).

**PB-0008 재실행 — 31 step 전건 PASS**

| # | 항목 | 실측 |
|---|---|---|
| T1 | 라벨이 패널·모달에서 동일 | PASS `다운로드 파일명의 버전 표시(_v2) 유지` (279×32px) |
| T6 | **두 안내가 서로를 부정하지 않는다**(P1) | PASS 토글 OFF → 라디오 힌트 `버전 표시 없이 받습니다` + 체크박스 힌트 `이름이 겹치면 파일마다 다른 번호가 덧붙습니다` |
| T6 | 충돌 안내가 SR 에 전달 | PASS `aria-live="polite"` |
| T8 | 토글 ON 복귀 시 라디오 힌트도 복귀 | PASS `파일명에 v1·v2 가 붙습니다` |
| T6/T8 | 힌트 등장·소멸에도 모달 높이 불변 | PASS `417 ↔ 416px`(종전 약 20px 변동) |

#### 6. rebase 정합 후 재검증 (2026-08-07, main `attach-multi-upload` 흡수)

main 이 단일 다운로드에 "v2 이상은 응답 파일명에만 접미 부착" 을 도입해, 그 규칙을 `auto`
모드로 흡수하고 경로 기본을 옮겼다(단일·`scope=latest`=auto, `scope=all`=force).

**단일 다운로드 모드별** (id=883, 저장명 `…_08_fix_log_tables_v2.sql`, v=2):

| version_suffix | X-Attachment-Download-Name |
|---|---|
| (미지정) · `auto` · `keep` · `force` | `…_08_fix_log_tables_v2.sql` |
| `strip` | `…_08_fix_log_tables.sql` |
| `bogus` | **400** |

**⬇ 와 ⤓ '최신 버전만' 이름 일치** — 저장명에 접미가 **없는** 사용자 재업로드 버전
(id=306 `T_gunzgame_account.sql`, v=2)으로 실측. rebase 전에는 토글 ON 이어도 단일에 접미가
붙지 않아 두 경로가 어긋났다(§18.8 backend/qa 패널 P2):

| 토글 | 단일 ⬇ | 일괄 ⤓ latest |
|---|---|---|
| ON(기본) | `T_gunzgame_account_v2.sql` | `T_gunzgame_account_v2.sql` |
| OFF(strip) | `T_gunzgame_account.sql` | `T_gunzgame_account.sql` |

**PB-0008 재실행 — 31 step 전건 PASS**(라벨 `다운로드 파일명의 버전 표시(_v2) 유지` 279×32px ·
토글 OFF 시 라디오 힌트 `버전 표시 없이 받습니다` · `aria-live=polite` · 모달 높이 417↔416px ·
매니페스트 12건 전량 고유). 프리뷰 컨테이너(`:18099`, 라이브 이미지 `00431585` + worktree
bind-mount) — 라이브 무접촉.

#### 7. POST-DEPLOY 라이브 배포본 검증 (2026-08-07, `abdf13bd`)

PR #1183 머지 → main `abdf13bd` → `make deploy-web` **exit 0**(web-a/web-b 롤링 + soak 통과 +
워커군 `mysql-ai-agent:abdf13bd` 롤아웃 + gateway 드리프트 없음).

**서빙 자산에 신규 코드 존재 확인**(라이브 `repo-web-a-1` 내부):
`static/index.html` 의 `attachSidePanelSuffixToggle` 1회 · `routers/attachments.py` 의
`_download_filename_with_version` 2회 · `static/app/composer.js` 의 `ATTACH_SUFFIX_LABEL` 2회 ·
캐시 스탬프 갱신(`chat.css?v=3a7d33acaddd`).

**PB-0008 재실행 — 31 step 전건 PASS**. 배포본 이미지 `mysql-ai-web:abdf13bd` 를 **bind-mount
없이** 그대로 띄운 검증 컨테이너(`:18099`)에서 수행 — 즉 사용자에게 서빙되는 것과 **같은 baked
자산**이다(정적 자산이 이미지에 굽히는 구조라 소스 마운트로는 이 축을 못 본다). 라이브 Caddy
트래픽 무접촉, 라이브 데이터 변경 0.

| # | 항목 | 실측 |
|---|---|---|
| T1 | 패널 토글 노출·라벨 | PASS `다운로드 파일명의 버전 표시(_v2) 유지` 279×32px |
| T5/T8 | 패널↔모달 양방향 동기화 | PASS `panelChecked=true`·`stored=1` |
| T6 | 토글 OFF 시 두 안내 정합 | PASS 라디오 `버전 표시 없이 받습니다` + 체크박스 `이름이 겹치면…` |
| T6 | SR 전달 | PASS `aria-live=polite` |
| T6/T8 | 모달 높이 안정 | PASS `417 ↔ 416px` |
| T9 | 매니페스트 이름 | PASS strip 12/12 고유 · force 12/12 고유 |
| T10 | 잘못된 파라미터 | PASS `400` |

**배포 검증 체크리스트(feature-0014 RUNBOOK §10)** [1] 배포+soak ✓ [2] 워커 롤아웃 ✓
[3] 캐시 스탬프 갱신 ✓ [4] 실 사용자 표면 PB-0008 ✓ [5] 완료 보고 가능.

**한계(정직)**: Windows hosts 에 `mysql-ai.company.local` 이 없어 공개 도메인 경로(Caddy TLS
종단)를 브라우저로 통과시키지는 못했다. 검증한 것은 **같은 배포 이미지의 web 앱**이며, Caddy
계층(TLS·라우팅)은 이번 변경의 영향면이 아니다(정적 자산·앱 라우터만 변경).
