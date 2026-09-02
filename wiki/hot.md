---
doc_type: WIKI_HOT_CACHE
last_updated: 2026-09-02
---

# Hot Cache

## Last Updated
2026-09-02

## Key Recent Facts
- **기능 동작 순서도는 `wiki/Flows/` 에 있다.** `Architecture/Data-Flow` 는 컴포넌트 축의 한 장짜리 흐름이고, 그 아래 층(사용자 행위 축)이 Flows 5문서다 — 로그인·인증 / 외부 AI 연계 / 보안 처리 / 화면 UI·UX / 세부 기능. 정본은 `docs/`·`unit/<id>/docs/` 이고 Flows 는 mirror다.
- 우측 오버레이 사이드 패널(첨부·실행 단계·프로필)은 **한 번에 하나만** 열린다. 등록부 `static/app/side-panels.js` 가 choke point 이며 DOM 을 직접 감추지 않는다 — 소유 모듈 close 를 호출한다.
- **러너끼리 다툴 때의 축은 「연결 순서」다**(토큰 발급 Id). 지문은 안내 라벨로만 남고, 양쪽 모두 하트비트 이력이 있을 때만 다투며 계정이 다르면 예외다.
- **나가는 프롬프트는 신뢰등급 3구획**(수행할 작업 / 참고 맥락 / 비신뢰 데이터). 각인·canary·`[SCOPE]` 는 전량 유지, 토큰은 환경변수로.
- **지식베이스가 외부 AI 에 도달한다** — `get_task_context` 1층 → 5층(용어사전·ENUM·테이블/컬럼·샘플쿼리 + 관계). product scope 는 그 task 의 `ProductId` 로만 해석.

## Recent Changes
- (09-02) `wiki/Flows/` 신설 — MOC + 5문서, mermaid 47블록(headless Chromium `mermaid.parse()` 전건 PASS) · `Index.md` §2.2.1 · `Data-Flow` 역할 분담 배선
- (09-01) `app/side-panels.js`(신규) 배선 · 접근성 `inert` 동기화 · 연결 칩 사이드바 이동 · 브리지 러너 우선순위/프롬프트 구획/로그 2-sink · `get_task_context` 5층 · 인증서 만료 감시
- (08-31) 관리 콘솔 위임(Kind 축) · 실행 단계 추론 구간 · 대화 「최근 갱신」 고정 해소

## Active Threads
- 「프로필 열린 상태에서 첨부 열기」는 backdrop 이 클릭을 먹어 실 브라우저 도달 불가 — jsdom 계약으로만 잠김.
- **macOS URL 스킴 핸들러 등록 미실측**(WSL+Windows 조합만 실측 완료) — 정본 feature-0043 `REPORT.md`.
- **취소 후 `submit_answer` 409 집행 미검증** — 러너가 제출 전에 하차하므로(설계대로) 그 경로에 닿지 않는다.
- **동기 inproc 경로(`_ask_impl`)의 첨부 쓰기는 세 번째 구현** — `shared/attachment_write.py` 로 합치는 것은 별도 cycle.
- **`.env` 위생** — `AGENT_*_MODEL` 계열은 게이트가 차단선을 쥐어 무해하나 운영자 직접 주석 권장(AI 읽기·수정 불가).
