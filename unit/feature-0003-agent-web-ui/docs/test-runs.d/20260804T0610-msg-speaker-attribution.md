---
run_at: 2026-08-04T15:34:00+09:00
session: ai/claude/feature-0003-msg-attribution
scope: 대화내역 발화자 귀속(사용자·assistant 제품) 사후 변경 차단 — fork · 제품 전환 2 트리거
verdict: PASS (Environment: Windows-browser, 실 Chrome 150 relay)
---

# Run — PB-0008 시각검증 (Environment: Windows-browser)

**환경**: `bin/win-browser.py` relay → Windows Chrome/150.0.7871.128. 검증 대상은 미머지 브랜치
코드라, 라이브 web 이미지(`mysql-ai-web:d23f0a0d`)에 변경 5파일만 bind-mount 한 **격리 컨테이너**
(`web-verify`, `https://localhost:18099`, repo_dbnet, TLS=라이브 cert)를 띄워 실측했다. 라이브
web-a/web-b 는 무접촉. 검증 종료 후 컨테이너 제거.

## 1. fork 트리거 — 원저자 발화자 보존

- 원본 `20260804051001-774ada22` (소유자 **kumin**, 12 메시지) 을 **bootstrap_admin** 으로 열람.
  - BEFORE: user 행 `kumin`, assistant 아바타 `건즈 글로벌 QA`.
  - evidence: `artifacts/pb0008/20260804-attrib-01-source-kumin.png`
- `POST /api/fork_conversation` → fork `20260804063055-ff73a181` (copied=12, core=55, att=26),
  **소유자 bootstrap_admin**.
  - AFTER: user 행 여전히 `kumin`, assistant 여전히 `건즈 글로벌 QA`.
  - evidence: `20260804-attrib-02-fork-kumin-preserved.png`
- **회귀 기준(수정 전 동작)**: fork 는 owner 가 복제자로 바뀌므로 `isOwn=true` → 폴백이
  `나 (bootstrap_admin)` 를 렌더했다. 즉 이 화면은 수정 전이라면 반드시 달랐다.
- 각인 실측 (`/api/history` meta): user = `{sender_username:"kumin", sender_account_id:34,
  attribution_inferred:true}` · assistant = `{product_id:119, product_key:"GZ_QA_G",
  product_mode:"pinned", product_name:"건즈 글로벌 QA", attribution_inferred:true}`.

## 2. 제품 전환 트리거 — 과거 발화자 불변

- fork 본에서 제품 칩을 **실제 클릭**해 `GZ_QA_G` → `(KR_QA) 킹스레이드 - 국내 QA` 전환.
- 전환 직후: 과거 assistant 6행 전부 `건즈 글로벌 QA` **유지**(칩만 KR_QA).
  - evidence: `20260804-attrib-03-fork-before-switch.png` / `20260804-attrib-04-fork-after-switch-unchanged.png`
- 새로고침(deep-link 재진입) 후에도 동일 — 표시가 아니라 **영속 각인** 이 근거임을 확인.
  - evidence: `20260804-attrib-05-fork-after-reload-unchanged.png`
- **판독 가능 캡처**(§16.6 캡처 escalate — 말풍선 본문을 접어 발화자 행만 노출):
  `20260804-attrib-09-fork-speaker-rows-readable.png` — 헤더 `소유자 bootstrap_admin`,
  user 6행 전부 `kumin`, assistant 6행 전부 동일 제품 아바타, 컴포저 칩 `KR_QA`.
  한 장에서 "현재 대화 설정 ≠ 과거 발화자" 가 동시에 보인다.

## 3. 경계 반대편 (§16.7 G4) — legacy 미각인 대화의 freeze-on-change

- `20260803081201-969946a2` (bootstrap_admin 소유, 각인 전무: `attrib {}` 실측 확인).
- BEFORE: 컴포저 칩이 `KR_QA` 인 상태에서 assistant 아바타가 **`킹스레이드 - 국내 QA`** 로 렌더 —
  대화의 실제 바인딩(GZ_QA_G)과 다른, **버그 그 자체의 라이브 재현**.
  - evidence: `20260804-attrib-06-legacy-before-KRQA-wrong.png`
- 제품을 `(MV) 마이크로볼츠` 로 전환 → 과거 답변이 새 제품이 아니라 **직전 제품
  `건즈 글로벌 QA` 로 정정**되어 고정. 각인 실측: `{product_id:119, product_key:"GZ_QA_G",
  product_mode:"pinned", product_name:"건즈 글로벌 QA", attribution_inferred:true}`.
  - evidence: `20260804-attrib-07-legacy-after-switch-frozen-GZQAG.png`
- 원래 제품(`GZ_QA_G`)으로 되돌린 뒤에도 불변 — 바인딩 원상복구, 각인만 남음.
  - evidence: `20260804-attrib-08-legacy-restored.png`

## 4. 데이터 영향

- 생성한 fork 테스트 대화는 검증 후 `POST /api/delete_conversation` 으로 삭제(archived).
- legacy 대화는 제품 바인딩을 전환→원복해 **최종 바인딩 무변경**, 메시지 meta 에 올바른 귀속만 추가.
- 라이브 web/워커 컨테이너 무접촉.

## 5. 미커버 (정직 표기)

- **auto 모드 답변**(`product_mode:"auto"` → "AI" 배지 확정)은 단위 테스트로만 검증했고 라이브
  실측은 하지 않았다 — auto 대화에 새 답변을 생성하려면 라이브 LLM 호출이 필요해 본 검증 범위
  밖으로 두었다. 각인은 코드경로가 동일(`_answer_product_attribution`)하고 렌더 분기는
  `test_assistant_speaker_resolver_prefers_stamp_over_live_product` 가 고정한다.
- **그룹 대화 다중 발신자**의 fork 후 표시는 미실측(원본 소유자 1인 대화로 검증). 그룹 발신자는
  종전부터 `sender_username` 이 각인돼 있어 본 변경의 영향면이 아니다.
