---
doc_type: WIKI_HOT_CACHE
last_updated: 2026-09-03
---

# Hot Cache

## Last Updated
2026-09-03

## Key Recent Facts
- **브리지 러너의 정본은 `src/agent/` 모듈군(분할 시 18 · 자기 갱신 추가로 현재 19)이고, 배포되는 단일 파일은 «빌드 산출물»이다**(2026-09-02). 정본과 바이트 동일한 배포 사본을 49/49 커밋이 함께 고치던 충돌 표면을 없앤 결과이며, 생성물 4개는 git 추적에서 빠졌다 — 소스를 고쳤는데 배포본을 안 만들면 **배포는 성공하고 러너 다운로드만 404** 가 되므로 배포 스크립트가 하드 게이트를 건다.
- **KB 근거는 도구 호출이 아니라 «자동 주입»으로 도달한다** — `claim_request` 응답의 `kb_context`/`kb_notes`. 5층으로 넓힌 `get_task_context` 는 라이브에서 0 기여였다(AI 가 그 도구를 한 번도 부르지 않았다). ⚠ 배치가 러너 `compose_prompt` 에 있어 **구버전 러너에는 안 실린다**.
- **기능 동작 순서도는 `wiki/Flows/` 에 있다.** `Architecture/Data-Flow` 는 컴포넌트 축의 한 장짜리 흐름이고, 그 아래 층(사용자 행위 축)이 Flows 5문서다 — 로그인·인증 / 외부 AI 연계 / 보안 처리 / 화면 UI·UX / 세부 기능. 정본은 `docs/`·`unit/<id>/docs/` 이고 Flows 는 mirror다.
- 우측 오버레이 사이드 패널(첨부·실행 단계·프로필)은 **한 번에 하나만** 열린다. 등록부 `static/app/side-panels.js` 가 choke point 이며 DOM 을 직접 감추지 않는다 — 소유 모듈 close 를 호출한다.
- **러너끼리 다툴 때의 축은 「연결 순서」다**(토큰 발급 Id). 지문은 안내 라벨로만 남고, 양쪽 모두 하트비트 이력이 있을 때만 다투며 계정이 다르면 예외다.
- **나가는 프롬프트는 신뢰등급 3구획**(수행할 작업 / 참고 맥락 / 비신뢰 데이터). 각인·canary·`[SCOPE]` 는 전량 유지, 토큰은 환경변수로.

## Recent Changes
- (09-02) 러너 18모듈 분할 + 배포본 이중화 제거(빌드 게이트) · 러너 자기 갱신 + 런처 CA 핀 · Windows 명령줄 상한/기동 침묵/`cp949` 자식 입출력 · 능력 질의 도구 금지 가드(66→6.6초)와 추론축 `--help` 복구 · 답변 총 수행시간 각인 복구 · KB 근거 자동 주입 · 포트프록시 멱등화(5분 절단 해소) · 그래프 용어 회수 단계 · 사이드바 상태 배지 배선
- (09-02) `wiki/Flows/` 신설 — MOC + 5문서, mermaid 47블록(headless Chromium `mermaid.parse()` 전건 PASS) · `Index.md` §2.2.1 · `Data-Flow` 역할 분담 배선
- (09-01) `app/side-panels.js`(신규) 배선 · 접근성 `inert` 동기화 · 연결 칩 사이드바 이동 · 브리지 러너 우선순위/프롬프트 구획/로그 2-sink · `get_task_context` 5층 · 인증서 만료 감시

## Active Threads
- 「프로필 열린 상태에서 첨부 열기」는 backdrop 이 클릭을 먹어 실 브라우저 도달 불가 — jsdom 계약으로만 잠김.
- **macOS URL 스킴 핸들러 등록 미실측**(WSL+Windows 조합만 실측 완료) — 정본 feature-0043 `REPORT.md`.
- **취소 후 `submit_answer` 409 집행 미검증** — 러너가 제출 전에 하차하므로(설계대로) 그 경로에 닿지 않는다.
- **동기 inproc 경로(`_ask_impl`)의 첨부 쓰기는 세 번째 구현** — `shared/attachment_write.py` 로 합치는 것은 별도 cycle.
- **`.env` 위생** — `AGENT_*_MODEL` 계열은 게이트가 차단선을 쥐어 무해하나 운영자 직접 주석 권장(AI 읽기·수정 불가).
- **claude·codex 외 CLI 의 능력 질의 지연은 미측정** — 도구 금지 가드는 프롬프트 수준이라 CLI 무관하게 적용되지만 실제 감소폭은 모르고, 질의 전용 인자는 codex 에만 있다(정본 feature-0043 `REPORT.md` §11-D).
- **AI CLI 허용목록 정본 동기화(ITEM-05)는 POST-DEPLOY 라이브 실측 미수행** — 웹 자산 변경 0 이라 다음 배포 빌드에 반영된다(정본 feature-0043 `TASK.md` TASK-20260902T193000).
