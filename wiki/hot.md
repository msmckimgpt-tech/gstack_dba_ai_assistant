---
doc_type: WIKI_HOT_CACHE
last_updated: 2026-09-01
---

# Hot Cache

## Last Updated
2026-09-01

## Key Recent Facts
- 우측 오버레이 사이드 패널(첨부·실행 단계·프로필)은 **한 번에 하나만** 열린다. 등록부 `static/app/side-panels.js` 가 choke point 이며 DOM 을 직접 감추지 않는다 — 티커 정지·backdrop 내림이 «닫기» 의 일부라 소유 모듈 close 를 호출한다.

## Recent Changes
- (09-01) `app/side-panels.js`(신규) + `app.js`·`profile.js`·`composer.js` 배선 · CI 구조 가드(DOM 전수 대조) · PB-0008 14 step
- (08-31) 관리 콘솔 위임 · 실행 단계 추론 구간 · 대화 「최근 갱신」 고정 해소

## Active Threads
- 「프로필 열린 상태에서 첨부 열기」는 backdrop 이 클릭을 먹어 실 브라우저 도달 불가 — jsdom 계약으로만 잠김.
