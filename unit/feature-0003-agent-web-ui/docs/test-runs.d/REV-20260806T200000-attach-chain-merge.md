---
run_at: 2026-08-06T20:00:00+09:00
session: ai/claude/attach-chain-merge
scope: feature-0003-agent-web-ui — 분열 첨부 체인 병합 도구 + 첨부 날짜 compact 표기
verdict: PASS (단위·하네스) / 라이브 적용·PB-0008 은 배포 후
---

### REV-20260806T200000-attach-chain-merge 분열 체인 병합 + 첨부 날짜 compact (Critical §12.3, 2026-08-06)

- 무엇: (1) 이름이 갈라져 여러 체인으로 쪼개진 기존 첨부를 하나의 버전 체인으로 병합하는 도구
  (2) 첨부 목록·버전 이력에 첨부 시각을 compact 하게 표기.

#### Run 1 — 라이브 dry-run (Environment: CLI, 2026-08-06, 읽기 전용)

`python /tmp/attach_chain_merge.py`(web-a 컨테이너, `--apply` 없음):

```
[attach-chain-merge] 범위=전체 · 활성 첨부 780 row 검사
  변경 대상: 155 row / 62 논리파일 / 14 대화
  #98  'P_gunzgame_Game_AccountAttendence.sql' v1(root=None) → v1(root=None, superseded=Y)
  #109 'P_gunzgame_Game_AccountAttendence.sql' v1(root=None) → v2(root=98,  superseded=Y)
  #119 'P_gunzgame_Game_AccountAttendence.sql' v1(root=None) → v3(root=98,  superseded=N)
```

- 최근 7일 한정 시: 25 논리파일 / 67 row / 4 대화.
- 제외 그룹 **0** — 사용자가 직접 `_v<n>` 이름으로 올린 케이스는 실측상 존재하지 않았다.
- **쓰기 0** — dry-run 은 SELECT 만 수행한다.

#### Run 2 — 병합 로직 단위 (Environment: CLI, 2026-08-06)

`pytest tests/test_attach_chain_merge.py` → **17 passed**

| 축 | 내용 |
|---|---|
| C1 | `base_name` — `_v<n>` 접미만 제거, 내부 `v2`·`a_v2_b` 는 보존 |
| C2 | 이미 정합한 체인은 **계획 0 row**(무의미 write 없음) |
| C3 | assistant 편집본(이름만 다름)이 원본 체인으로 흡수 + HMAC 재계산 |
| C4 | 재업로드로 생긴 새 root 가 원 체인으로 재결합(v1→v2→v3) |
| C5 | `SupersededAt` = 다음 버전의 CreatedAt · **live 정확히 1건** |
| C6 | 사용자가 직접 `_v<n>` 로 올린 그룹 제외 / C6b 제외 규칙이 과하지 않음(base 있으면 병합) |
| C7 | `--days` 범위 밖 그룹 제외 |
| C8 | 대화·계정 경계를 넘어 합치지 않음 |
| C9 | **2단계 UPDATE 순서**(오프셋 전부 → 최종 전부) · 오프셋이 기존 MAX 초과 · row 마다 상이 |
| C9b | 중간 실패 시 **전체 롤백**(부분 적용 잔존 0) |

#### Run 3 — 날짜 표기 하네스 (Environment: jsdom/Node, 2026-08-06)

`node tests/verify_attach_date_compact.mjs` → **18 passed**
(포맷 6: 오늘 `14:20` / 올해 `8/6` / 지난해 `25/8/6` / 잘못된 값 빈 문자열 / title 2 ·
**시간대 3**: 오프셋 없는 값의 시:분 보존 · 마이크로초 6자리 파싱 · `Z` 부착 시 어긋남 ·
배선 6 · **뮤테이션 역검증 3**: `Z` 부착 · 오늘 분기 제거 · 목록 배선 제거를 모두 검출)

**시간대 실측 근거**: 18:50 업로드 첨부의 `CreatedAt` 이 `2026-08-06 18:50:29`, MySQL `NOW()` 가
`19:04`(KST), `UTC_TIMESTAMP()` 가 `10:04`, 컨테이너 `TZ=Asia/Seoul`. 즉 `created_at` 은 로컬
naive 이므로 그대로 파싱해야 한다.

#### Run 4 — 전 스위트 회귀 (Environment: CLI, 2026-08-06)

격리 컨테이너(`--network none`)에서 feature-0002/0003/0023 전 스위트 **exit 0 · 실패 0**,
전수 mjs **46 스위트 통과**.

#### 라이브 적용 · PB-0008 — **PENDING(배포 후)**

병합은 라이브 첨부 메타데이터를 다시 쓰므로 코드 배포 후 수행한다:

1. `--apply` 실행 → 스냅샷 JSON + 롤백 SQL 생성 확인 → 사후 재검증 **잔여 0**
2. 병합된 대화의 목록에서 같은 파일이 **한 줄 + "버전 N개 ▾"** 로 보이는지 실측
3. 메타줄에 compact 시각이 보이고 hover title 이 전체 시각인지
4. 버전 이력 행에 버전별 시각이 보이는지
5. 구버전 다운로드 파일명에 `_v<n>` 이 붙는지(선행 cycle AC-AMU-5 회귀 확인)

**Environment: Windows-browser — DEFERRED(배포 후)**: 정적 자산이 web 이미지에 baked 되고
병합 결과는 라이브 DB 에서만 재현되므로, 미머지 상태에서는 두 층을 함께 띄울 수 없다.
