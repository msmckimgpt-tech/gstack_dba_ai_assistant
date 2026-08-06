---
run_at: 2026-08-07T03:20:00+09:00
session: ai/claude/attach-chain-live-dup
scope: feature-0003-agent-web-ui — 라이브 체인 병합 적용 · PG 미러 수리 · live 중복 정리 · 날짜 표기 검증
verdict: PASS
---

### REV-20260807T032000-attach-chain-live-dup 라이브 병합 적용 + 미러 수리 (Critical §12.3, 2026-08-07)

#### Run 1 — 라이브 병합 적용 (Environment: CLI, 배포본 `832aaec5` → 서빙 `6a3b1a97`)

```
[attach-chain-merge] 범위=전체 · 활성 첨부 780 row 검사
  변경 대상: 155 row / 62 논리파일 / 14 대화
스냅샷: /tmp/attach-chain-merge-20260807T031507.json (+ .rollback.sql)
적용: 155 row
사후 검증: 잔여 변경 대상 0 row (0 이어야 정상)
```

스냅샷·롤백 SQL 을 `artifacts/attach-chain-merge/` 로 회수(컨테이너 재시작 소실 방지).

#### Run 2 — PG 미러 충돌 적발·수리 (Environment: CLI)

적용 중 `attachment_pg_mirror` 가 **UNIQUE 위반**을 fail-soft 로 삼켰다:
`duplicate key value violates unique constraint "uq_core_attachments_version_chain"
DETAIL: Key (root_attachment_id, version_number)=(699, 4) already exists`.

**MySQL↔PG 대조로만 드러났다** — 스크립트의 사후 검증은 MySQL 기준이라 "잔여 0" 을 보고했고,
미러 호출도 예외를 내지 않았다. 대조 결과 **29 row 가 옛 상태로 잔존**(라이브 목록 read 는 PG 우선).

수리: 영향 **대화 전체**(4 대화 129 row)의 PG `version_number` 를 오프셋으로 선이동 → MySQL 정본으로
재미러. 같은 회피를 `mirror()` 에 흡수해 재발을 막았다.

| 지표 | 수리 전 | 수리 후 |
|---|---|---|
| MySQL 활성 / PG 활성 | 780 / 779 | **780 / 780** |
| MySQL↔PG 불일치 | 29 | **0** |

#### Run 3 — 선재 live 중복 적발·수리 (Environment: CLI)

정합 검증에서 **체인당 live>1 이 1건** 남았다 — `P_gunzgame_Game_MasangCreatorsGetByAID.sql`
(root=802 의 v1·v2 가 둘 다 `SupersededAt IS NULL`). root·이름이 같아 분열 조건에 안 걸리던
**선재 결함**(업로드 경로 supersede 누락). 판정 조건에 `live>1` 을 추가해 1 row 적용.

최종: **MySQL 체인당 live>1 : 0 · PG 체인당 live>1 : 0**.

#### Run 4 — pytest (Environment: CLI)

`test_attach_chain_merge.py` **19 passed**(C10 live 중복 수리 · C10b 조건이 정합 체인을 건드리지
않는지 반대 검증 신규).

#### Run 5 — PB-0008 실 Windows Chrome (Environment: Windows-browser, 2026-08-07)

대화 `20260806052006-3f48cbb7`(`구 로그 테이블 DROP 유지 결정`) **읽기 전용 열람**으로 실측:

| # | 항목 | 실측 |
|---|---|---|
| V1 | 목록 행 수 | **22행** (병합 전 31행 = 원본 22 + assistant `_v2` 9) |
| V1 | 중복 파일명 | **[] (0건)** — 같은 파일이 여러 줄로 뜨지 않는다 |
| V3 | 버전 토글 | `버전 3개 ▾` · `버전 2개 ▾` — 합쳐진 체인이 이력으로 접근 가능(**데이터 손실 0**) |
| V2 | 날짜 칩 | **22/22 표시**, 값 `8/6`(올해 형식) |
| V4 | 버전 이력 시각 | `사용자 · 8/6 · 최신` / `AI 수정 · 8/6` / `사용자 · 8/6` |
| V4·V5 | title 전체 시각 | `2026-08-06 15:34` · `14:48` · `14:20` — **실제 업로드 시각과 일치**(9시간 어긋남 없음 = 시간대 판단 정확) |

시각 캡처: `artifacts/pb0008-attach-chain-merge/{01_merged_list_with_dates,02_version_history_dates}.png`
— 우측 패널에 `2KB · 8/6 · uploaded` 메타줄과 `v3` 배지 + 펼친 버전 이력(v3/v2/v1 각 시각)이 판독된다.

**라이브 데이터 경계**: 본 Run 은 **조회만** 수행했다(로그인 후 deep-link 진입 + 패널 열기 + 버전
토글). 쓰기는 Run 1~3 의 승인된 병합뿐이며, 그 대상·결과는 스냅샷과 롤백 SQL 로 되돌릴 수 있다.
