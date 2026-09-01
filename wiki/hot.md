---
doc_type: WIKI_HOT_CACHE
last_updated: 2026-09-01
---

# Hot Cache

## Last Updated
2026-09-01

## Key Recent Facts
- 우측 오버레이 사이드 패널(첨부·실행 단계·프로필)은 **한 번에 하나만** 열린다. 등록부 `static/app/side-panels.js` 가 choke point 이며 DOM 을 직접 감추지 않는다 — 티커 정지·backdrop 내림이 «닫기» 의 일부라 소유 모듈 close 를 호출한다.
- 연결 칩은 컴포저를 떠나 **사이드바 프로필 행**으로 갔다. 자리 판단은 폭 임계값이 아니라 **계정 이름 길이**가 한다.

## Recent Changes
- (09-01) `app/side-panels.js`(신규) + `app.js`·`profile.js`·`composer.js` 배선 · 접근성 `inert` 동기화 · PB-0008 16 step
- (09-01) 연결 칩 이동 · 관리 콘솔 위임 · 실행 단계 추론 구간 · 대화 「최근 갱신」 고정 해소

## Active Threads
- 「프로필 열린 상태에서 첨부 열기」는 backdrop 이 클릭을 먹어 실 브라우저 도달 불가 — jsdom 계약으로만 잠김.
