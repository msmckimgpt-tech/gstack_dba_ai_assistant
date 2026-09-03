---
doc_type: WIKI_HOT_CACHE
last_updated: 2026-09-04
---

# Hot Cache

## Last Updated
2026-09-04

## Key Recent Facts
- **터미널 없이 연결하는 Windows 네이티브 클라이언트가 있다** — feature-0046(신규, 2026-09-03). `bridge_setup.ps1` 이 하던 일을 **같은 계약·같은 중단 지점**으로 수행하고 껍데기만 GUI(tkinter). ⚠ **미서명**(SmartScreen 2클릭 감수, 사용자 결정) · **Windows 우선**(macOS 는 경고가 아니라 차단이라 범위 밖) · 배포 형식은 설치 마법사 + **인터프리터** 동봉(러너는 동봉하지 않고 서버에서 받아 sha256 대조 — 동봉하면 배포가 갈린다).
- **로그인은 「위임」이 아니라 「대행 실행」이다** — 벤더 공식 명령을 subprocess 로 띄우고 종료코드만 본다. 토큰 미접촉. 2026년에 3사가 구독 OAuth 제3자 사용을 차단했다.
- **개인 머신 클라이언트 이름은 `DQA Connect` / 스킴 `dqa-connect` / 역-DNS `com.masangsoft.dqa-connect`** (2026-09-03 개명, 정본 `shared/dqa_identity.py`). ⚠ 스킴을 `dqa` 로 줄이지 않는다 — URL 에 세션 토큰이 실리고 스킴은 **마지막 등록자 승** 머신 전역 네임스페이스다. MCP 키는 로컬이라 짧게(`dqa`). **하드 컷오버** — 옛 스킴 미등록, setup 재실행이 옛 홈·옛 핸들러를 지운다.
- **연결 상태는 3상태다** — 「모른다」를 「정상」으로 말하지 않는다. ⚠ 다만 **게이트 축의 fail-open 은 의도된 것**(`ai_blocked()` — 조회 실패 시 연결됨으로 간주)이고 표시 축과 별개다. 두 축을 섞어 「fail-open 은 폐기됐다」로 읽으면 오정정한다.
- **브리지 러너의 정본은 `src/agent/` 모듈군(20)이고, 배포되는 단일 파일은 «빌드 산출물»이다.** 소스만 고치면 **배포는 성공하고 러너 다운로드만 404** — 배포 스크립트가 하드 게이트를 건다.
- **KB 근거는 도구 호출이 아니라 «자동 주입»으로 도달한다** — `claim_request` 응답의 `kb_context`/`kb_notes`. ⚠ 배치가 러너 `compose_prompt` 에 있어 **구버전 러너에는 안 실린다**.
- **기능 동작 순서도는 `wiki/Flows/` 에 있다.** `Architecture/Data-Flow` 는 컴포넌트 축, Flows 5문서가 사용자 행위 축. 정본은 `docs/`·`unit/<id>/docs/`, Flows 는 mirror.
- 우측 오버레이 사이드 패널(첨부·실행 단계·프로필)은 **한 번에 하나만** — 등록부 `static/app/side-panels.js` 가 choke point.
- **나가는 프롬프트는 신뢰등급 3구획**(수행할 작업 / 참고 맥락 / 비신뢰 데이터).

## Recent Changes
- (09-04) doc_sync — 신규 feature-0046 색인 배선(self-add 카드가 **orphan** 이었다) · feature 카운트 45→46 **7표면** · `shared/*.py` 18→19 2색인 · 릴리즈노트 09-03 블록 신설
- (09-03) Windows 네이티브 클라이언트 초판(ROADMAP ITEM-08) · 클라이언트 명칭 개명 + 명칭 SSOT · 연결 퍼널 계측(ITEM-00) · 연결 상태 3상태 · 아픈 러너 즉시 응답(150초→체감 0초) · 응답없는 AI 무한대기 폐쇄 · 연결 단계 체크리스트(ITEM-03·ITEM-06) · SPIKE-02 판정(conditional-go)
- (09-02) 러너 19모듈 분할 + 배포본 이중화 제거 · 러너 자기 갱신 + 런처 CA 핀 · Windows 명령줄 상한/cp949 · 능력 질의 가드(66→6.6초) · KB 근거 자동 주입 · `wiki/Flows/` 신설

## Active Threads
- ⚠ **`docs/SECURITY.md` 가 feature-0046 의 두 공격 표면을 모른다** — 미서명 exe 배포·로그인 대행 실행·러너 수신 / `dqa-connect://` 딥링크에 실리는 세션 베어러 토큰 + 마지막-등록자-승 스킴 + 하드 컷오버. 09-04 doc_sync 가 §50·§51 신설을 제안했으나 적대 검증이 §49.3 과의 상호작용 결함을 지목해 fail-closed 보류. **다음 창 최우선.**
- **정본 내부모순 — feature-0046 빌드 플래그**: `FUNCTION.md` §5 는 `--onefile --windowed`, 같은 파일 §P0-J 와 `TASK.md` 는 `--onedir` 전환 완료. 미러는 최신을 따랐다.
- **연결 체크리스트 단계 수 불일치**: 정본 `TASK.md` 는 「5단계」, `_connect_steps.py` 의 `key` 는 **4개**.
- **개명·클라이언트의 라이브 미검증** — 실 OS 핸들러 재등록·옛 잔재 삭제는 사용자 머신 setup 재실행 후에만 관측된다. macOS 경로는 실측 수단 부재.
- **ITEM-08 후속 미완** — 자동시작·자동 업데이트·벤더 설치기 실행.
- 「프로필 열린 상태에서 첨부 열기」는 backdrop 이 클릭을 먹어 실 브라우저 도달 불가 — jsdom 계약으로만 잠김.
- **취소 후 `submit_answer` 409 집행 미검증** — 러너가 제출 전에 하차하므로 그 경로에 닿지 않는다.
- **동기 inproc 경로(`_ask_impl`)의 첨부 쓰기는 세 번째 구현** — `shared/attachment_write.py` 합치기는 별도 cycle.
- **feature-0043 합본 테스트 14건·feature-0003 7건은 선재 order-dependent flake** (main 과 차집합 0, 격리 실행 PASS).
