---
run_at: 2026-08-03T17:30:00+09:00
session: ai/claude/feature-0016-visual-postdeploy
scope: band-visual-fit POST-DEPLOY 육안 재검증 + label-canon 전량 전환 측정(E.12)
verdict: PASS
---

# Run — PB-0008 POST-DEPLOY 육안 재검증 (Environment: Windows-browser)

- 대상: 배포본 `a17f769b`(PR #1118 머지), 자산 스탬프 `admin.js?v=06d62a46ff8a`.
  Runner: AI (`bin/win-browser.py` relay, CDP 9222 / relay 9223).
- **서빙 baked 2중 확인**: `repo-web-a-1` 컨테이너에서
  `grep -c "labelMaxWidth: w - 10" graph-roleviz.js` = **2**(테이블+루틴) ·
  `grep -c 'f.startsWith("nm:")' graph-simgroups.js` = **0**.
- 대상 데이터: 수정 전 Run(`20260731T0300-band-visual-fit.md`)과 **같은** 데이터소스·스키마·노드
  (`mssql-dk-dev` / `dk_game_integrate` / `FN_GetKeyIDToInventoryType` 경유).

## F1 — 싱글턴 밴드 소멸

| | 수정 전 | 수정 후 |
|---|---|---|
| 싱글턴 밴드 | `…integrateunion·1` `spget…·1` `spupdate…·1` **3개** | **0개** |
| `기타` 밴드 | 7 | **10** |

세 노드(`spGetDominionSkill`·`spProcessIntegrateU…`·`spUpdateDominionS…`)가 `기타` 로 흡수됐다
(7 + 3 = 10). 기계 어간 라벨이 한국어 의미 라벨 옆에 서는 분류 체계 붕괴가 사라졌다.

## F2 — 칩 라벨이 알약 안으로

| | 수정 전 | 수정 후 |
|---|---|---|
| 렌더 | 아이콘이 알약 **왼쪽 밖**, 글자 여백 0, 말줄임표가 **오른쪽 밖** | 아이콘·글자·말줄임표 전부 **알약 안**, 우측 여백 확보 |
| 예시 | `spGetIntegrateConnectInfo`(경계 초과) | `spGetIntegrateConne…`(더 일찍 절단) |
| 측정 | `spGetGuildRankingAl…` 우여백 **−3px** | 같은 노드 **+14px** |

`labelMaxWidth` 176 → `w - 10`(폭 150 기준 **140**)의 산술적 효과와 일치한다.

**측정 한계(정직 표기)**: 알약 경계 안티에일리어싱 때문에 픽셀 계측이 ±1px 노이즈를 갖는다 —
짧은 이름에서도 ±1px "초과" 가 찍힌다. 그 해상도로는 판정할 수 없어, 확정 근거는 ① 같은 배율
확대 비교(육안) ② 코드상 예산 산술 ③ 노이즈를 넘는 단일 관측(−3 → +14) 셋으로 삼는다.

## E.12 — label-canon 전량 전환 측정

최대 scope(`mssql-06656002eda6`)가 cadence 로 **08-03 11:41** 전환되어 전 scope 가 신 로직이다.

| 지표 | 기준선(07-31 02:00) | 현재 |
|---|---|---|
| 전역 루틴 **밴드** | 2,703 | **2,703** (완전 불변) |
| 전역 루틴 **라벨 종수** | 1,648 | **1,279** (−22.4%) |
| `우편 시스템` | 5밴드 | **0** |
| `메일시스템`(공백 없음) | 1밴드 | **0** |

**밴드가 1개도 변하지 않은 채 어휘만 22.4% 줄었다** — 설계 의도(병합 없이 이름만 통일)가 전역
규모에서 성립한다. 사용자가 지적한 `우편 시스템` 은 소멸했고 메일 도메인은 24밴드/272멤버로
`메일` 어휘에 수렴했다.

**남은 것(정직 표기)**: `우편`(1밴드·3멤버)·`우편·아이템 관리`(1밴드·12멤버)가 남아 있고,
`아이템거래`(공백 없음)도 1밴드 잔존한다. 통일 규칙이 **다른 스키마**의 이웃만 보므로, 같은
스키마 안에 짝이 없거나 스키마-내 충돌 가드에 걸린 경우는 그대로 남는다 — 설계상 예상되는 잔여다.

- Evidence: `artifacts/shared/win-browser-shots-visual-postdeploy/`
  (`01_after_bands.png` — F1 소멸 · `02_chip_before_after.png` — F2 전/후 동일 배율)
- 정리: 라이브 조작은 읽기·뷰 상태 전용(검색·관계선 토글). 검증 후 관계선 표시를 원복하고
  `win-browser.py down` 으로 드라이버 인스턴스만 종료. 콘솔 오류 0.
