---
doc_type: WIKI_FEATURE_CARD
scope: feature
status: active
edit_policy: ai-maintained
source_of_truth: false
template_version: v3.12.0
domain: [feature, wiki]
ai_read_priority: 7
wiki_role: feature_card
wiki_name: project
confidence: high
maturity: substantial
ai_generated: true
feature_id: feature-0046-native-client
linked_unit: unit/feature-0046-native-client
created: 2026-09-03
sources:
  - ../../unit/feature-0046-native-client/docs/FUNCTION.md
  - ../../unit/feature-0046-native-client/docs/ANCHOR.md
---

# feature-0046-native-client — Windows 네이티브 클라이언트

## 1. 한 줄

사용자가 **터미널을 열지 않고** 자기 AI 를 이 서비스에 연결한다. `bridge_setup.ps1`(669행)이
하던 일을 **같은 계약으로** 하되 껍데기를 GUI 로 바꾼 것.

## 2. 왜

`docs/improvements/onboarding-accessibility/RESEARCH.md` §9.1 — 연결을 우리가 만든 배포물로
구현하고 런타임·설치 UX·설정 UI·업데이트 채널을 전부 자체 구현해 **넷 모두가 마찰**이 됐다.

## 3. 핵심 제약

- **로그인은 「위임」이 아니라 「대행 실행」** — 벤더 공식 명령을 subprocess 로 띄우고 종료코드만
  본다. 토큰 미접촉. 2026년에 3사가 구독 OAuth 제3자 사용을 차단했고 Google 은 유료 구독자
  계정을 정지했다.
- **배포 형식 = 설치 마법사 + 런타임 동봉** (사용자 결정 2026-09-03, 정본 §P0-J) — 포터블 단일
  exe(`--onefile`)를 버리고 Inno Setup per-user 설치기 + `--onedir` + 공식 임베더블 CPython 을
  앱 폴더 옆에 두는 형식으로 옮겼다. ⚠ **동봉하는 것은 인터프리터지 러너가 아니다** — 러너는
  여전히 서버에서 받아 체크섬 대조한다(동봉하면 서버 배포와 클라이언트 배포가 갈려 「고쳤는데
  그대로」가 재발한다). 동결 exe 의 `sys.executable` 은 파이썬이 아니라 앱 실행 파일 자신이라
  종전 배포본은 러너를 실행하지 못했다(실측 exit=2 → 화면엔 「연결 확인에 실패했습니다(코드 2)」).
- **AI 는 Windows 와 WSL 양쪽에서 찾는다** (정본 §P0-K) — 첫 자리에서 멈추면 쓸 수 있는 것이
  있는데도 「없다」가 된다(사용자 제보: 「기존에 쓰던 LLM 접근 수단(WSL)에 진입할 수 없다」).
  WSL 런타임은 러너가 이미 가진 `--cmd 'my-ai -p {prompt}'` 계약으로 넘긴다 — **러너를 고치지
  않는다**. ⚠ 대가: `--cmd` 경로는 능력을 신고하지 않아 웹의 「답할 AI 있음」이 ❌ 로 남는다
  (답변은 정상으로 오간다).
- **인증 상태는 가용성의 증거가 아니다** (정본 §P0-L) — `auth status` 만 보고 「연결할 준비가
  되었습니다」라 하던 판정이 실측에서 틀렸다(로그인돼 있는데 답을 받지 못하는 런타임이 있었다).
  `verify_answers()` 가 실제로 한 번 물어보고 화면·선택은 `usable`(설치됨 + 답함)만 본다.
  ⚠ 이 호출은 사용자의 AI 사용량을 쓴다. 질문 인자는 런타임마다 다르다(`codex` 는 `exec` 하위명령).
- **웹의 인계를 딥링크로 받는다** (정본 §P0-M/§P0-O/§P0-P) —
  `dqa-connect://start?token=…&base=…&ca_sha256=…&agent_sha256=…`. 종전엔 토큰만 실렸다(그
  딥링크는 셸 설치본용이고 그 경로는 설치 때 서버 주소와 CA 를 디스크에 심는다) — 네이티브
  클라이언트에는 그 사전 상태가 없어 **「연결 정보가 없습니다」만 떴다**. 조립은 정본
  `shared/dqa_identity.scheme_url()` 한 곳이고, 서버 주소는 처음 연결한 곳으로 **TOFU 고정**해
  다른 주소가 오면 두 주소를 나란히 보여 주고 묻는다(물을 수 없으면 「아니오」로 읽는다).
- **웹은 클라이언트를 주 경로로 보인다** (정본 §P0-Q/§P0-R) — 터미널 1·2·3단계는 접는다.
  ⚠ **없애지 않는다** — 연결 프로그램을 설치하지 않은 사용자에게는 그것이 유일한 길이고,
  실행 실패 안내가 「1단계 명령」으로 되돌려 보내므로 접힌 블록을 자동으로 펼친다. `/ai/connect`
  에는 [내 AI 실행] 버튼을 **실재시켰다** — 문구만 바꾸고 버튼을 안 넣어 사용자가 없는 것을
  찾게 만든 결함을 실제로 냈다(2026-09-03).
- **Windows 우선 · 미서명** (사용자 결정 2026-09-03). 코드 서명은 조직 결정 대기이고,
  SmartScreen 경고는 설치 마법사 전환으로 **설치 1회**로 줄었다(단일 exe 를 매번 실행하던
  종전보다 나아진 점이다).

## 4. 실측 (2026-09-03, 실 Windows)

claude 를 PATH 밖 `.local\bin` 에서 감지 · JSON 로그인 판정 · tkinter 구성 ·
PyInstaller exe 9.17MB 빌드·실행. 실측이 결함 1건 적발(windowed 빌드의 `print()` 멈춤).

이어진 실 실행 검증이 결함 3건을 더 적발했다 — 진입점 상대 임포트로 **exe 실행 불가**(정본
§P0-G) · CA 지문 서버 봉투(대문자·콜론) 미수용으로 **연결 자체가 불가능**(§P0-H) · 빌드
스크립트 CP949 크래시(§P0-I). 그 뒤 무인 설치 후 동봉 런타임으로 러너 `--check` **exit=0**
(종전 exit=2) · GUI 실구동으로 「연결됨」 도달 + 서버 `first_heartbeat` 적재 · Windows+WSL
전수 탐지 **1개 → 3개** · 웹 → 스킴 → 클라이언트 전 경로(PB-0008, 배포 `c4e6684c`)를 실측했다.
뮤테이션은 10/10 · 9/9 KILL.

**아직 못 본 것**: 동결 앱 내부 버튼 클릭 검증(배경 조작 불가 — 별도 수단 필요) · gemini
로그인 명령 실측(그래서 gemini 는 「감지·안내」로 강등) · 연결 주체를 웹에서 클라이언트로
완전 이동(클라이언트가 스스로 토큰 취득) · 코드 서명 · 자동 업데이트 · 로그온 자동시작.

## 5. 정본

`unit/feature-0046-native-client/docs/{FUNCTION,TASK,ANCHOR,REPORT,REVIEW}.md`

## 6. 관련

- 러너·스킴·연결 화면의 기능 정본: [[feature-0043-external-llm-bridge]]
- 연결 흐름 mirror: [[../Flows/External-AI-Bridge]] §2.4
