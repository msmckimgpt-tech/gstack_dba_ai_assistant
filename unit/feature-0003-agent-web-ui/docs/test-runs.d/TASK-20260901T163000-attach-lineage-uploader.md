---
run_at: 2026-09-01T16:30:00+09:00
session: ai/claude/feature-0003-lineage-uploader-identity
scope: 공유 대화 계보 업로더 식별 + 그룹 카드 되풀이 제거 + assistant 계보 인지 확인
verdict: PASS
---

## Run — TASK-20260901T163000-attach-lineage-uploader (PRE-DEPLOY 라이브)

- Date: 2026-09-01 · Environment: **Windows-browser** (PB-0008)
- Target: §13.2.9 격리 컨테이너 `web-verify-lineage` — static(stamp `c64defd96a04`) +
  변경 라우터 2종(`conversations.py`·`_conv_store.py`) bind-mount, `https://localhost:18101`
  (공유 트리·라이브 web-a/b 무수정)
- Result: **PASS**

## 0. 먼저 확인한 것 — assistant 는 이미 알고 있었다

사용자 3번째 질문("assistant 가 각 계보의 현황을 파악할 수 있는지")을 **코드 읽기가 아니라 실제
프롬프트 렌더**로 확인했다. 라이브 대화 `20260813083932-46763d6e`(계정 10·50) 에 대해
`_build_attachment_context_section` 을 직접 호출:

```
## FILE VERSION LINEAGES — 같은 파일명, 서로 다른 버전 계보
- "P_gunzgame_Game_CheatSuspectReportInsert.sql" — 2 lineages:
    • uploaded by jmkimmasangsoft.com — v2 (attachment_id=1149, 2026-08-13 08:57)
    • uploaded by admin — v1 (attachment_id=1150, 2026-08-13 09:23)  ← overall latest (newest by time)
```

caller 를 10 / 50 으로 바꿔 각각 렌더해도 동일하게 **업로더 이름으로 계보를 가른다**.
per-lineage latest ↔ overall latest 두 축과 타 멤버 read-only 경계도 함께 실린다.

⭐ **따라서 결함은 「모델이 모른다」가 아니라 「같은 사실이 화면에 도달하지 않는다」였다.**
목록 payload 가 `AccountId` 를 직렬화에서 버려, 화면은 사람이 올린 계보를 전부 「사용자 계보」로
뭉뚱그리고 있었다.

## 1. 공유 대화 — 계보가 이름으로 갈린다 (사용자 지적 ①)

대화 `20260813083932-46763d6e` (`is_group=t`, 계정 10·50 동명 계보 4쌍):

| 관측 | 값 |
|---|---|
| 그룹 카드 | **4** |
| 행 라벨 | `jmkimmasangsoft.com` · `admin` · `jmkimmasangsoft.com` · `admin` … |

종전에는 이 8행이 전부 「사용자 계보」였다 — **글자 하나 다르지 않았다**. 이제 화면이
프롬프트와 같은 사실을 말한다.

## 2. 되풀이 제거 (사용자 지적 ②)

| 관측 | 종전 | 지금 |
|---|---|---|
| 그룹 안 행 아이콘(`.attach-list-item-icon`) | 계보 수만큼 | **0** |
| 카드 머리 아이콘(`.attach-lineage-group-icon`) | 없음 | **4** (카드당 1) |
| 카드 하나에 실린 파일명 | 3회(머리 1 + 행 2) | **1회**(머리) |

렌더:
```
📎 P_gunzgame_Game_CheatSuspectReportInsert.sql   계보 2   ⇄ 계보 비교
   jmkimmasangsoft.com  v2    2KB · 8/13 · uploaded · 버전 2개 ▾   ⬇ 🗑
   admin                      2KB · 8/13 · uploaded · 상세 ▾       ⬇ 🗑
```

⚠ **지운 것은 화면 문구뿐이다** — 파일명은 행 `title`·`aria-label`·「원문 보기」 클릭 대상에
그대로 남아 어포던스·AT 가 깎이지 않는다(회귀로 잠금).

### 픽셀 (§16.6 픽셀-클래스)

- `shared-lineage.png` — 첫 시도. **결함 1건 포착**: 카드 머리가 접힐 때 아이콘만 자기 줄로
  떨어져 파일명과 분리됐다. 아이콘+파일명을 한 덩어리(`.attach-lineage-group-title`,
  `min-width: 0`)로 묶어 수정.
- `shared-lineage2.png` — 수정 후 **240px 최소 폭**에서 아이콘+파일명이 한 줄에 붙어 있고
  칩(`계보 2`·`⇄ 계보 비교`)만 다음 줄로 접힌다(잘림 0).

## 3. 경계 양측 (§16.7 G4)

| 경계축 | 아래쪽 | 위쪽 |
|---|---|---|
| 대화 종류 | **1:1** (`20260831093200-02b3d60e`) → 라벨 `사용자 업로드` / `AI 수정본` — **이름 없음** (업로더가 늘 자기 자신이라 정보 0) | **공유** (`20260813083932`) → `jmkimmasangsoft.com` / `admin` |
| 계보 수 | **1개** (`20260828043852-8ef56c75`) → 카드 없음 · 행 아이콘 **2/2 유지** · 라벨 = **파일명** | 2개 → 카드 + 머리 아이콘 + 정체성 라벨 |

즉 **되풀이 제거는 그룹 안에서만** 발동하고, 단독 첨부의 종전 화면은 그대로다.

## 4. 회귀

- pytest `feature-0003`+`feature-0002`+`feature-0023` — **5167 passed / 5 skipped**,
  신규 `test_attach_lineage_uploader.py` **11건** 포함
- `node --check`(composer) · `ast.parse`(라우터 2종) PASS

### ⚠ 기존 실패 2건 — 본 변경과 무관 (기준선 대조로 확인)

`test_query_embed_visibility.py::test_snapshot_section_consumes_the_flag` ·
`::test_config_records_the_input_length_dependence` 가 **전체 스위트 실행에서만** 실패한다
(단독 실행은 9 passed). **같은 이미지로 `main`(`afcd1a42`) 를 그대로 돌려도 동일하게 실패** 하므로
본 cycle 의 회귀가 아니다.

기전: 앞서 도는 web-ui 테스트들이 `sys.modules` 에 스텁 모듈을 주입하고 정리하지 않아
(`test_attach_chain_merge.py` 의 `ModuleType("app")` 등), 뒤따르는 agent-core 테스트의
`Path(agent_core.__file__).resolve().parents[3]` 가 얕은 경로를 짚어 `IndexError` 를 낸다.
**CI 가 결제 정지로 멈춰 있어 이 실패가 드러나지 않고 있다** — 별도 cycle 대상으로 남긴다.

---

## Run 2 — 적대 리뷰(codex) 조치 후 재실측 (PRE-DEPLOY 라이브)

- Date: 2026-09-01 · Environment: **Windows-browser** (PB-0008), 같은 격리 컨테이너
  (static stamp `db56993f9922` + 변경 라우터 2종 재주입)
- Result: **PASS** — codex P1 **0** · P2 4 · P3 1 전건 조치

| 지적 | 라이브 실측 |
|---|---|
| P2-1 노출 범위 | `/api/attachments/1149/versions` → `versions[0].account_id` **부재**(공유 serializer 오염 제거) · `lineages[0].account_id` **유지**(기존 노출 불변) · 목록만 `account_id`+`uploader_username="admin"` |
| P2-2 AT 정합 | aria `…(jmkimmasangsoft.com, 2개 중 1번째) 원문 보기` / `…(admin, 2개 중 2번째) …` — 화면 라벨과 같은 출처 |
| P2-3 stale | 가드 추가 **후에도** 공유 대화 정상 렌더(그룹 4 · 행 아이콘 0 · 라벨 분리) — 차단만이 아니라 **정상 경로 통과**를 확인 |
| P2-4 라벨 충돌 | 응답 스텁(동일 업로더 3계보)으로 실 렌더 경로 구동 → `사용자 업로드 · 계보 1/3 · 2/3 · 3/3`, aria `(사용자 업로드, 3개 중 N번째)` |

> 충돌 분기를 스텁으로 확인한 이유: 라이브에 «공유 대화 + 동일 업로더 + 동명 3계보» 조합이
> 없다(동명 5계보 대화 `20260814032233` 은 1:1 이며 이 계정 목록에 노출되지 않아 도달 불가).
> 라이브 데이터를 만들지 않고 **실 브라우저의 실 렌더 코드**로 그 분기만 구동했다.

## 회귀

pytest `feature-0003`+`feature-0002`+`feature-0023` **5173 passed / 5 skipped**(신규 17건) ·
`node --check` · `ast.parse` PASS.
⚠ `test_query_embed_visibility.py` 2건은 **main 기준선에서도 동일 실패** — 본 변경 무관.
