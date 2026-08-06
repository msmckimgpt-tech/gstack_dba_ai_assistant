---
run_at: 2026-08-06T23:20:00+09:00
session: ai/claude-corp/feature-0003-attach-version-diff
scope: unit/feature-0003-agent-web-ui (routers/attachments·routers/_conv_store·static/app/attach-diff·static/app/composer·static/css/chat)
verdict: PASS (CLI·headless) / DEFERRED (Windows-browser — 아래 §4)
---

### Run (2026-08-06) — attach-version-diff: 첨부 버전 임의 쌍 diff 비교 화면

#### 1. 대상

`GET /api/attachments/{attachment_id}/diff`(신설) + `app/attach-diff.js` 전용 모달 +
`composer.js` 진입점 2종 + `css/chat.css`. 요청: 첨부 버전 간 diff 비교 화면(직전/직후 + **여러
단계 차이**).

#### 2. pytest — **Environment: CLI**

| 축 | 케이스 | 결과 |
|---|---|---|
| 체인 로더 | V1 MySQL 폴백 SQL 계약(soft-delete 제외·체인 스코프·ASC) · V2 PG 미러 우선(MySQL cursor 0회) | PASS |
| diff 뷰 | B1 insert/delete/replace 좌우 정렬 · B2 uneven replace 패딩 · B3 맥락 축약 + 생략 줄 수 · B4 전체 맥락 · B5 행 상한 절단 flag · B6 identical 이 축약·상한과 무관 | PASS |
| 엔드포인트 | E1 인접 쌍 · **E2 다단계(v1↔v3)에서 중간 버전 원본 미조회** · E3 from==to 400 · E4 파라미터 400 3종 · E5 체인 밖 404(oracle 차단) · E6 무권한 404 · E7 바이너리 메타 강등(원본 미조회) · E8 원본 cap 절단 표면화 · E9 조회 실패 503 · E10 context=full · E11 목록·비교 동일 체인 로더 | PASS |
| 보안(자체 적발) | **E12 D21 승인대기 403 + 원본 0회 조회** · **E13 체인 스코프 밖 행 제외(fail-closed)** · **E14 두 엔드포인트 모두 scope_row 전달** | PASS |

- 신규 **22건** PASS. 전수 회귀 `unit/feature-0002-agent-core/tests` +
  `unit/feature-0003-agent-web-ui/tests` + `unit/feature-0023-conversation-api-access/tests`
  = **3,806 passed · 3 skipped · 0 failed**(exit 0).
- **뮤테이션 역검증 7/7** — 각 뮤테이션이 의도한 단언만 red:
  ① 체인 밖 404→400 강등 → E5 · ② 맥락 축약 무력화 → B3·E10 · ③ 행 상한 무력화 → B5 ·
  ④ D21 게이트 제거 → E12 · ⑤ `/versions` 의 `scope_row` 누락 → E14 · ⑥ 스코프 필터 무력화 → E13.

#### 3. 헤드리스 프론트 — **Environment: WSL-headless (jsdom)**

`tests/verify_attach_version_diff.mjs` — 정본 렌더 함수를 추출해 jsdom 위에서 **실행**:
2열 4셀 구조·좌우 side 클래스·delete 의 빈 줄번호 · gap 의 생략 줄 수 문구·colSpan · 단일열
`-`/`+` 분해 · 절단 배너 2종(cap 크기·상한 행수 명시) · identical 은 빈 표 대신 안내 · 바이너리
메타표 · 원본 조회 실패 문구 구분 · 배선 8건 · 계약 9건(?v=dev · primitive · seq 가드 ·
innerHTML 부재 · CSS 클래스 실재) = **57건 PASS**.

전수 mjs **44 suite OK / 0 fail**(기존 43 + 신규 1 — 회귀 0).
`acorn-globals` 자유 식별자 **0**(신규 모듈). `codenav-lint` OK. `gen-routemap --check` 정합.
route 골든 parity: added 1 / removed 0 / order drift 0.

#### 4. **Environment: Windows-browser** — 배포 후로 이연 (미수행 사유 명시)

**미수행이며, 그 사실을 완료로 오인 보고하지 않는다.** 본 cycle 변경에는 신규 JS 모듈
(`static/app/attach-diff.js`)이 포함되고, 이 저장소에서 **JS 는 배포 전 `docker cp` 사전 QA 가
불가능**하다 — ① 미머지 파일을 web 컨테이너에 복사하면 빌드의 `inject_asset_stamp.py` 가 주입하는
content-hash 스탬프가 없어 import specifier 가 `?v=dev` 로 남고, ② 그 결과 같은 모듈이 두 URL 로
**이중 인스턴스화**되며, ③ Chrome 모듈 캐시가 구버전을 계속 실행한다(auto-memory
`project-pb0008-live-access-localhost443` 실측). 따라서 시각검증은 **머지·배포 후** 서빙본에서
수행하는 것이 유일하게 유효한 경로다(feature-0038 Cycle 2~10 이 같은 판단으로 POST-DEPLOY
PB-0008 을 완료 게이트로 삼았다).

**따라서 현 시점 미검증 축**: 모달의 레이아웃·정렬·간격·줄바꿈·overflow, 2열 표의 실제 가독성,
좁은 폭 폴백. jsdom 은 픽셀·레이아웃을 보지 못한다(§16.6 픽셀-클래스 변경은 판독 가능한 시각
캡처 필수).

**배포 후 수행할 항목** (완료 시 본 fragment 에 Run append):
1. 첨부 패널 → "버전 N개 ▾" → **"⇄ 버전 비교"** 클릭 시 모달이 열리고 기본 선택이 직전↔최신.
2. from/to 선택기로 **다단계 쌍**(v1↔v3 이상) 선택 → diff 갱신 + `+N/-N` 통계 표시.
3. 구버전 행의 `⇄` 로 그 버전↔최신 직행. 최신 행에는 `⇄` 없음.
4. **2열 ↔ 단일열 토글** — 같은 비교 결과의 두 표현(네트워크 재요청 0, DevTools 확인).
5. "동일한 줄도 모두 보기" 켬/끔 → gap 행 소멸/복귀.
6. 좌우 2열의 줄번호 정렬·긴 줄 줄바꿈·가로 스크롤이 모달 안에서만 발생(본문 폭 붕괴 없음).
7. 바이너리 첨부(xlsx/pdf) 비교 → 메타표 강등 렌더.
8. ESC · `×` · 배경 dismiss(누름+뗌 모두 배경) 3경로.
9. 판독 가능한 시각 캡처 첨부(전체화면 축소본 아님 — element-screenshot/clip).
