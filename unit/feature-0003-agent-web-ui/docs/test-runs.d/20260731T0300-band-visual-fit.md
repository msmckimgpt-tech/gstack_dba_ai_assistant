---
run_at: 2026-07-31T03:00:00+09:00
session: ai/claude/feature-0016-band-visual-fit
scope: 그래프 밴드·칩 시각 정합 육안검증 — 싱글턴 밴드 / 루틴 칩 라벨 넘침
verdict: FAIL→FIX (결함 2건 발견·수정, 픽셀 재확인은 배포 후)
---

# Run — PB-0008 육안검증 (Environment: Windows-browser)

- 대상: 라이브 배포본 `97af7d27`(내 직전 배포 `4d5e6678` 포함 확인 — `git merge-base --is-ancestor`),
  자산 스탬프 `admin.js?v=6e6be998cb12`. Runner: AI (`bin/win-browser.py` relay,
  Chrome/150.0.7871.128, CDP 9222 / relay 9223).
- 대상 데이터: 데이터소스 `mssql-dk-dev`(`mssql-ba175631e9fc`) · 스키마 `dk_game_integrate`.

## 발견 (수정함)

| # | 결함 | 관측 | 원인 |
|---|---|---|---|
| F1 | 멤버 1개짜리 밴드 | `…integrateunion·1` `spget…·1` `spupdate…·1` 3개가 `경매 거래·46` 과 같은 헤더·테두리·토글로 나란히 섬. 상세 패널 그룹 목록에도 동일 노출 | `graph-simgroups.js` 싱글턴 흡수가 `nm:` 을 예외로 둠 — 근거였던 "2차 attach 로 커질 수 있어" 가 이미 끝난 단계 |
| F2 | 긴 이름이 알약 밖으로 | 아이콘이 알약 **왼쪽 밖**, 글자 여백 0, 말줄임표가 **오른쪽 밖**(짧은 이름은 정상 여백) | `_metaRoutineStyle.labelMaxWidth` 하드코딩 **176** vs 폭 `min(190, TW+rel*40)`(=150) → 26px 초과. §45 가 테이블만 `w-10` 으로 고치고 루틴 누락 |

## 정합 확인 (PASS)

| 항목 | 결과 |
|---|---|
| 패널 ↔ 캔버스 SSOT | 컨텍스트 메뉴 `컨텐츠 카테고리 / 경매 거래 · 테이블 46` = 캔버스 `경매 거래 · 46` = 패널 그룹 목록 **일치** |
| 스키마 간 어휘 통일 | 검색 패널에 서로 다른 스키마의 두 밴드가 모두 `🏷 인벤토리 관리` — 병합 없이 이름만 통일된 의도한 모습 |
| 밴드 라벨 방향 말줄임 | `tok…`/`…tok` 은 **의도된 범위 신호**(코드 확인) — 결함 아님. 처음 불일치로 적었다가 철회 |

## 측정 방법과 버린 시도 (정직 표기)

픽셀 계측을 세 번 실패했다 — ① 측정 창 경계를 텍스트 끝으로 오독 ② `±60px` 창이 옆 노드 글자를
주워 짧은 이름까지 "넘침" 판정 ③ 배경색(248,244,239)이 흰색 임계를 통과. **관계선을 끈 뒤**
(씬 객체 168→106) 배경이 정리되고서야 pill 폭이 일정한 값(~109px 화면좌표)으로 잡혔다. 그전 수치는
전부 폐기했고, 최종 판정은 **같은 배율 확대 비교(육안)** 로 했다.

- Evidence(4매): `artifacts/shared/win-browser-shots-band-visual-fit/`
  (`01_live_bands.png` · `02_singleton_bands_zoom.png` — F1 · `03_chip_overflow_compare.png` — F2
  긴/짧은 이름 동일 배율 비교 · `04_edges_off_measurement.png` — 관계선 제거 상태)
- 정리: 라이브 조작은 **읽기·뷰 상태 전용**(검색·관계선 토글·컨텍스트 메뉴 열람, 서버 mutation 0).
- **한계**: 이 Run 은 수정 **전** 상태의 실측이다. 수정본의 픽셀 확인은 배포 후 별도 Run 으로 남긴다.
