---
doc_type: WIKI_HOT_CACHE
last_updated: 2026-09-03
---

# Hot Cache

## Last Updated
2026-09-03

## Key Recent Facts
- **개인 머신 클라이언트 이름은 `DQA Connect` / 스킴 `dqa-connect` / 역-DNS `com.masangsoft.dqa-connect`** (2026-09-03 개명, 정본 `shared/dqa_identity.py`). 이름에 구현 형태(`bridge`·`runner`)를 넣지 않은 것은 ROADMAP ITEM-08 이 스킴을 재사용하며 러너를 클라이언트로 갈아치우기 때문. ⚠ 스킴을 `dqa` 로 줄이지 않는다 — URL 에 세션 토큰이 실리고 스킴은 머신 전역 선착 아닌 **마지막 등록자 승** 네임스페이스다. 반면 MCP 키는 로컬이라 짧게(`dqa` → `mcp__dqa__*`). **하드 컷오버** — 옛 스킴 미등록, setup 재실행이 옛 홈·옛 핸들러를 지운다.
- **브리지 러너의 정본은 `src/agent/` 모듈군(19)이고, 배포되는 단일 파일은 «빌드 산출물»이다.** 소스를 고치고 배포본을 안 만들면 **배포는 성공하고 러너 다운로드만 404** — 배포 스크립트가 하드 게이트를 건다.
- **KB 근거는 도구 호출이 아니라 «자동 주입»으로 도달한다** — `claim_request` 응답의 `kb_context`/`kb_notes`. ⚠ 배치가 러너 `compose_prompt` 에 있어 **구버전 러너에는 안 실린다**.
- **기능 동작 순서도는 `wiki/Flows/` 에 있다.** `Architecture/Data-Flow` 는 컴포넌트 축, Flows 5문서가 사용자 행위 축. 정본은 `docs/`·`unit/<id>/docs/`, Flows 는 mirror.
- 우측 오버레이 사이드 패널(첨부·실행 단계·프로필)은 **한 번에 하나만** — 등록부 `static/app/side-panels.js` 가 choke point.
- **러너끼리 다툴 때의 축은 「연결 순서」다**(토큰 발급 Id). 계정이 다르면 예외.
- **나가는 프롬프트는 신뢰등급 3구획**(수행할 작업 / 참고 맥락 / 비신뢰 데이터).

## Recent Changes
- (09-03) 클라이언트 명칭 개명 + 명칭 SSOT(`shared/dqa_identity.py`) + 대조 테스트 8건(주입 10종 KILL) · 옛 잔재 정리 로직 · 루트 stale `bridge_setup.sh` 제거 · 연결 퍼널 계측(ITEM-00) · SPIKE-02 네이티브 클라이언트 판정(conditional-go, Tauri+PyInstaller)
- (09-02) 러너 19모듈 분할 + 배포본 이중화 제거 · 러너 자기 갱신 + 런처 CA 핀 · Windows 명령줄 상한/cp949 · 능력 질의 가드(66→6.6초) · KB 근거 자동 주입 · 포트프록시 멱등화 · 그래프 용어 회수
- (09-02) `wiki/Flows/` 신설 — MOC + 5문서, mermaid 47블록 전건 PASS

## Active Threads
- **개명의 라이브 미검증** — 실 OS 핸들러 재등록·옛 잔재 삭제는 사용자 머신 setup 재실행 후에만 관측된다. macOS 경로는 실측 수단 부재.
- 「프로필 열린 상태에서 첨부 열기」는 backdrop 이 클릭을 먹어 실 브라우저 도달 불가 — jsdom 계약으로만 잠김.
- **취소 후 `submit_answer` 409 집행 미검증** — 러너가 제출 전에 하차하므로 그 경로에 닿지 않는다.
- **동기 inproc 경로(`_ask_impl`)의 첨부 쓰기는 세 번째 구현** — `shared/attachment_write.py` 합치기는 별도 cycle.
- **ITEM-08(네이티브 클라이언트)은 코드 서명 미확보로 blocked** — 서명 불가 시 사내 MDM 이 유일 대안.
- **feature-0043 합본 테스트 14건·feature-0003 7건은 선재 order-dependent flake** (main 과 차집합 0, 격리 실행 PASS).
