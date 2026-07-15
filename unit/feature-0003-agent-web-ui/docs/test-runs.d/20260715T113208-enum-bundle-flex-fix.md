---
run_at: 2026-07-15T11:32:08+09:00
session: enum-bundle-flex-fix (ai/claude/feature-0003-enum-bundle-flex-fix)
scope: ENUM 검토 큐 묶음 카드 flex 압축 붕괴 수정 — .admin-meta-bundle flex-shrink:0 (feature-0003 web/UI CSS 전용, enum-review-bundle POST-DEPLOY PB-0008 적발 후속)
verdict: PASS (라이브 근본원인 확정 + 수정 라이브 주입 검증; 재배포 자산 POST-DEPLOY 재검증 예정)
---

### Run (2026-07-15) — ENUM 검토 큐 묶음 카드 flex 압축 수정 — **Environment: Windows-browser (AI 직접 — 실 Windows Chrome via bin/win-browser.py relay @ 172.26.144.1:9223) + styles.css 정적**

- **적발 경위(enum-review-bundle POST-DEPLOY PB-0008)**: 배포본(f6cb0b14) `/admin` > 지식베이스 > 메타데이터 > ENUM 코드사전 > 검토 큐에서, DOM 에는 묶음 8개(`.admin-meta-bundle`)가 존재하고 내용(loc·code·label·체크박스·마스터·등록 버튼)도 정확했으나(eval 로 확인), **카드 렌더 높이가 12px 로 붕괴**(스크린샷상 회색 바)되어 사용자에게 내용이 보이지 않음.
- **근본원인(라이브 CDP 측정)**: `#metadataList` = `overflow-y:auto` + `flex-direction:column`(getBoundingClientRect height 373px — 높이 제약 스크롤 컨테이너). `.admin-meta-bundle` = 기본 `flex-shrink:1` → 8개 카드가 flex 압축. 카드 내부(head 65 + list 38 + foot 61 = 164px)는 정상 높이지만, 카드 자신은 12px 로 눌리고 `overflow:hidden` 이 넘친 내용을 클리핑 → sliver. 기존 flat-list `.admin-meta-row` 는 `overflow:hidden` 부재로 압축돼도 내용이 보여 미발현이던 것이 신규 카드에서 발현.
- **수정(1파일, CSS 1선언)**: `styles.css` `.admin-meta-bundle` 에 `flex-shrink: 0` — 카드가 자연(내용) 높이를 유지하고, 다건 시 목록은 `#metadataList` 컨테이너가 스크롤한다.
- **라이브 주입 검증(win-browser eval)**: `.admin-meta-bundle{flex-shrink:0}` 주입 전 카드 rect **12px** → 주입 후 **166px**(내용 전체 노출). 다른 규칙·JS·DOM 무변경.
- **§18.8**: CSS 1선언 레이아웃 전용 → 패널 skip(REVIEW `[SKIPPED:...]`, 적대 자가검토 refute).
- 결과: **PASS**(근본원인 라이브 확정 + 수정 효과 라이브 실증). **재배포 자산 최종 검증은 본 fix 배포 후 append**(카드 정상 높이·묶음 8개·전체 승인/일부 해제 토글·등록·pageerror 0).

- **[POST-DEPLOY 갱신 2026-07-15] 재배포 자산 라이브 PASS (Environment: Windows-browser, AI 직접 — 실 Windows Chrome via bin/win-browser.py relay, bootstrap_admin)**: PR #817 머지(a3c69103) → deploy-web --web-only soak PASS. `/healthz` git_commit=**a3c69103**·mysql_ok·pg_ok. 서빙 `styles.css` 스탬프 갱신(**62c4b695387d**) + 규칙 정규식 추출로 `.admin-meta-bundle { … flex-shrink: 0 }` 배포 확증. **배포본 런타임(win-browser eval, 주입 없이)**: ENUM 검토 큐 묶음 8개 카드 높이 **[166,166,166,205,166,166,298,166]**(전부 자연 높이·최소 166px — 12px sliver 완전 해소)·`.admin-meta-bundle` computed `flex-shrink=0`·목록 컨테이너 스크롤(scrollHeight 1770 > clientHeight 373)·내용/등록/마스터 정상·pageError 0. 스크린샷 육안(묶음 카드 정상 렌더: 전체 승인 마스터·`0→성공`·`등록 (1)`, scratchpad/enum-review-bundle-fixed.png). → **재배포 자산 실증 PASS**.
