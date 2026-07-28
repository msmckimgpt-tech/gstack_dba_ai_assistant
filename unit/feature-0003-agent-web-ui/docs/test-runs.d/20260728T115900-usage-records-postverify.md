---
run_at: 2026-07-28T11:59:00+09:00
session: ai/claude/feature-0003-usage-records-postverify
scope: [usage-records, post-deploy, pb0008, column-layout, responsive, actor-labels]
verdict: PASS (선행 cycle 이관 2건 전부 종결 / 열 폭 결함 1건 발견·수정)
---

### Run (2026-07-28) — '사용 기록' **POST-DEPLOY** 종결 — **Environment: Windows-browser (PB-0008)**

배포본 `6d7fe391` (PR #984 머지 → `bin/deploy-web.sh` 무중단 롤아웃, soak 통과, web-a/web-b +
insight-worker/ask-worker `6d7fe391`). 접속 `https://localhost/admin` (200, Chrome/150).

**전제 확인**: 서빙 자산의 stamp 정합 —
`admin.html: admin.js?v=7fc11a708399` == `graph/graph-core.js: admin.js?v=7fc11a708399`
→ admin.js **단일 모듈 인스턴스**. 선행 cycle 의 미확정 사유(2 인스턴스)가 배포본엔 부재함을 확인.

#### ① 주체 열 3분기 — PASS (선행 cycle 이관분)

모델 도넛 클릭 → 시스템 200행 실측:

| 표기 | 건수 | 의미 |
|---|---|---|
| `인사이트 워커` / `요청 처리 워커` | 다수 | 예약 sentinel → 사람이 읽는 워커명 |
| `삭제된 대화` | 5 | 비-sentinel 이나 `core_conversations` 부재 → **링크 없음**(404 방지), 원 id 는 title |
| `대화 (소유자 없음)` | 1 | 실재하나 owner NULL → `/?conversation=` 링크 부여 |
| raw hex id 노출 | **0** | 종전 `20260723090821-4bb4a9ae` 등 노출 → 완전 해소 |

#### ② 열 폭 / 줄바꿈 — **결함 발견 → 수정 → PASS**

사용자 보고("본문 열 과도 줄바꿈")의 잔존을 배포본에서 실측:

```
before: wrapW 1144 / tableW  763 / 본문 열 239px / 단일행 15/20
after : wrapW 1144 / tableW 1144 / 본문 열 620px / 단일행 18/20   (가로 클리핑 없음)
열 폭: 구분 58 · 본문 620 · 주체 150 · 호출 38 · 토큰 66 · 비용 63 · 최근사용 148
```

- **RC**: 공용 `.admin-usage-table { max-width: 640px }` 가 이 테이블에도 적용 → auto table-layout
  이 테이블을 min-content 로 수축 → 잔여 폭 자체가 없어 `width:1%`/반응형 확장이 무력화.
- **수정**: `.usage-conv-modal .usage-conv-table { width:100%; max-width:none }` + 본문 열 `width:100%`.
- 잔여 2행(48px)은 시스템 행의 **의도된 2줄 구조**(작업·대상 / 이동 안내)이지 줄바꿈 붕괴가 아니다.

#### ③ 반응형 — PASS

뷰포트 1249px → 모달 1199px (**96%**, `min(1240px, 96vw)` 규칙대로). 고정폭 아님.
가로 스크롤바 미발생, 전체 일시(`2026. 7. 28. 오전 10:47:46`) 잘림 없음.

#### ④ 회귀 — PASS

대화 행(83건) 제목·소유자·링크 정상, 시스템 행과 토큰 순 병합 정렬 유지. 모달 제목
`claude-haiku-4 · 사용 기록`. 증적: `docs/evidence/pb0008-usage-records-postdeploy-20260728.png`.

**Verdict: PASS** — 선행 cycle 이 이관한 2건 전부 종결. 사용자 요청 6개 축(시스템 편입 ·
'사용 기록' 명칭 · 작업/객체 인지 · 클릭 이동 · 줄바꿈 해소 · 반응형 확장) 라이브 확정.
