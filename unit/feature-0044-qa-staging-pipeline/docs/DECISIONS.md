---
doc_type: FEATURE_DECISIONS
feature_id: feature-0044-qa-staging-pipeline
status: active
edit_policy: append-only
source_of_truth: true
---

# Feature Decisions

## ADR-20260826T140000-build-once-pull-promote
- Status: proposed (사용자 승인 대기)
- Date: 2026-08-26
- Context: 라이브 배포 전 관문으로 격리망 QA 머신을 도입한다. QA 머신은 VPN 경유로만 접근
  가능하고 아웃바운드는 사내 저장소만 허용된다. 현행 배포 스파인 `bin/deploy-web.sh` 는
  **배포 대상 호스트에서** `git checkout origin/main` + `docker build` 를 수행하는데, 이
  전제가 격리망에서 성립하지 않는다. 사내 미러를 붙여 대상 호스트에서 빌드하더라도, 의존성
  lock 없이는 미러가 시점에 따라 다른 버전을 주므로 개발 머신 이미지와 QA 이미지가 다른
  바이트가 된다 — 그러면 QA 단계 자체의 의미(검증한 것이 배포된다)가 사라진다.
- Decision: **build once, deploy many + pull-based CD + 태그 승격** 3원칙을 채택한다.
  1. 빌드는 사내 GitLab CI 한 곳에서만 수행하고, 산출물을 사내 registry 에 push 한다.
     QA·라이브는 **이미지 다이제스트**로 pull 만 한다(태그가 아니라 다이제스트 — 태그는 이동한다).
  2. 배포는 QA·라이브가 각자 폴링해 당긴다. 개발망이 VPN 너머로 밀지 않는다.
  3. 승격은 재빌드가 아니라 `qa/<tag>` → `promote/<tag>` 태그 이동이다.
  현행 무중단 스파인(롤링·pre-drain·soak·last-good 롤백)은 **유지**하고 이미지 획득 경로만
  교체한다 — 스파인이 이미 `docker-compose.deploy-pin.yml` 로 이미지를 고정하므로 확장
  지점이 존재한다(`--from-manifest`).
- Consequences:
  - (+) dev·QA·live 가 같은 바이트를 쓴다는 것이 다이제스트로 **증명 가능**해진다.
  - (+) 인바운드 방화벽 구멍이 불필요하고, 배포 자격증명이 개발망에 상주하지 않는다.
  - (+) 롤백이 빨라진다 — 이전 다이제스트 이미지가 로컬에 남아 재빌드가 없다.
  - (−) **폐쇄망 빌드 재현성 확보(Phase 1)가 선행 필수**다: Dockerfile `FROM` 파라미터화,
    pip 사내 미러 + 해시 고정, compose 외부 이미지 8종의 미러화와 패치 버전 핀. 실작업량의
    대부분이 여기 있다.
  - (−) 원격이 둘(GitHub 개발 / GitLab 배포)이 되어 정본 규율이 필요하다. QA deploy key 를
    read-only 로 두어 구조적으로 차단한다.
  - (−) 릴리즈 매니페스트라는 새 산출물의 관리 비용이 생긴다. 대신 그 파일이 preflight 의
    검사 기준이 되어 "env 키 누락으로 부분 기동" 같은 실패를 배포 전에 막는다.
- Supersedes: 없음 (현행 로컬 빌드 경로는 제거하지 않고 개발 머신용 fallback 으로 보존)
- Superseded By: —

## ADR-20260826T140100-completion-by-mcp-reachability
- Status: proposed (사용자 승인 대기)
- Date: 2026-08-26
- Context: 이 서비스의 사용자 진입 경로는 웹 화면이 아니라 **개인 머신 AI 런타임의 MCP 연결**
  (feature-0041 도구 표면 + feature-0043 pull 브리지)이다. 컨테이너가 전부 healthy 여도
  VPN DNS 가 `WEB_PUBLIC_HOST` 를 못 풀거나, MCP 클라이언트가 TLS 를 신뢰하지 않거나,
  OAuth discovery 엔드포인트가 404 면 사용자는 진입 자체를 못 한다. 컴포넌트 health 로 완료를
  선언하면 "기동은 됐는데 못 쓴다" 는 재보고가 발생한다(AGENTS.md §16.3 bring-up/access
  완료 기준이 지적하는 바로 그 패턴).
- Decision: 배포 완료 판정에 **사용자 진입 경로 도달성**을 포함한다.
  - 자동: `/livez`·`/readyz` + **OAuth discovery 2종**(`/.well-known/oauth-protected-resource`,
    `/.well-known/oauth-authorization-server`) + `/api/ai/mcp` 프로토콜 응답 + 대화 경로 스모크
    + 브리지 `list_open_requests` 왕복.
  - 수동: VPN 밖 사용자 머신에서 MCP 연결 → 브라우저 OAuth 완주 → 도구 1회 호출 → 웹 렌더 확인.
  - 자동 스모크 실패 시 배포를 롤백하고 **승격 태그를 붙이지 않는 것**으로 라이브를 보호한다.
- Consequences:
  - (+) "배포 성공인데 아무도 못 쓴다" 를 구조적으로 차단한다.
  - (+) TLS·VPN DNS 같은 인프라 의존 조건의 결손이 배포 시점에 드러난다(나중에 사용자 신고로
    드러나지 않는다).
  - (−) 수동 QA 축이 남는다 — OAuth 브라우저 완주는 VPN 밖 실제 클라이언트에서만 검증 가능해
    자동화로 대체할 수 없다.
  - (−) 사내 CA 서명 인증서가 사실상 필수가 된다. MCP 클라이언트에는 브라우저의 예외 승인
    버튼이 없어 self-signed 면 연결 자체가 실패한다.
- Supersedes: 없음
- Superseded By: —
- Note (2026-08-27): 사내 CA 발급 가능으로 확정되어 (−) 항목의 부담이 해소됐다. 결정 본문은 유효.

## ADR-20260827T090000-registry-free-artifact-relay
- Status: proposed (사용자 승인 대기)
- Date: 2026-08-27
- Context: ADR-20260826T140000 은 "사내 GitLab + Container Registry 가 있다" 는 전제로
  build-once + pull 을 설계했다. 실제 확인 결과 **사내 git 저장소도 컨테이너 레지스트리도
  없고**, 구축한다면 SVN 기반이며 그마저 "릴리즈 산출물 저장소" 용도다. 즉 `docker pull`
  이라는 표준 전달 수단이 존재하지 않는다. 그렇다고 각 머신이 각자 빌드하면 폐쇄망 재현성
  문제로 되돌아간다 — **전달 수단이 없다는 것이 각자 빌드하라는 뜻은 아니다.**
- Decision: **레지스트리 없는 산출물 릴레이**를 채택한다.
  1. `docker save | zstd` 로 이미지 tar 를 만들고, 매니페스트에 **`sha256`(전송 무결성)** 과
     **`image_id`(설치 등가성)** 를 함께 기록한다. 두 값이 레지스트리의 digest 보증을 대신한다.
  2. 산출물은 SVN `releases/<tag>/` 에 두고, 대상 머신은 read-only 로 당긴다.
  3. 승격은 git 태그가 아니라 `promoted/current.json` 갱신이다.
  4. 매니페스트에 **`transport` 필드**를 두어 이미지 획득을 함수 하나로 격리한다 —
     미래에 레지스트리가 생기면 빌드 스크립트와 매니페스트만 바뀌고 배포 러너·deploy-web.sh
     는 무변경으로 전환된다.
  5. 빌드는 `bin/release-build.sh` **한 스크립트**로 고정한다. 지금은 개발 머신, 차후 사내
     빌드 서버 — 이관은 "다른 머신에서 같은 스크립트 실행" 이 전부이며, 이관 시 같은 커밋의
     산출물 등가성을 1회 검증한다(`built_by` 필드로 추적).
- Consequences:
  - (+) 레지스트리 구축을 QA 도입의 선행 조건에서 제거해 일정이 인프라 과제에 묶이지 않는다.
  - (+) `image_id` 대조로 "설치된 이미지가 빌드한 그것인가" 를 레지스트리 없이도 답할 수 있다.
  - (+) 롤백 시 이전 이미지가 로컬에 남아 재빌드가 없다(현행 로컬 빌드 모드보다 빠르다).
  - (−) **SVN 은 삭제해도 이력 blob 이 남아** 이미지 tar 를 매 릴리즈 커밋하면 저장소가 단조
    증가한다. 안 A(매니페스트만 SVN + tar 는 파일서버)를 권장하되, 안 B 를 택하면 증가량을
    사전 계산해야 한다 — **사용자 결정 필요**.
  - (−) 전달 채널이 표준이 아니므로 러너가 무결성 검증을 직접 해야 한다(레지스트리라면 공짜).
    그 대신 검증 실패 시 **재시도하지 않고 중단**한다 — 신원 불일치는 재시도로 낫지 않는다.
- Supersedes: ADR-20260826T140000-build-once-pull-promote 의 **전달 수단**(Registry pull →
  tar 릴레이)과 **빌드 실행처**(GitLab CI → release-build.sh), **승격 표현**(git 태그 →
  promoted/current.json). 원 ADR 의 3원칙(build once / pull / 재빌드 없는 승격)은 유효하다.
- Superseded By: —

## ADR-20260827T090100-live-host-separation
- Status: proposed (사용자 승인 대기)
- Date: 2026-08-27
- Context: 현재 라이브는 개발 머신과 **같은 WSL 호스트**에서 돈다(20 vCPU / 39GB / GTX 1660
  SUPER). QA 머신을 도입하면서 라이브를 그대로 두면, QA 는 pull 기반 표준 경로를 쓰고
  라이브만 "개발 머신에서 로컬 빌드" 라는 예외 경로를 평생 유지해야 한다. 예외 경로는
  검증되지 않은 채 남고, 개발 활동(빌드·테스트·worktree)이 서빙 자원과 경합한다.
- Decision: **QA 와 함께 라이브도 전용 호스트로 분리**한다(사용자 결정). 그 결과 QA·라이브는
  **같은 부트스트랩 절차·같은 배포 러너·같은 스크립트**를 쓰고 **채널 이름만** 다르다
  (`--channel qa` / `--channel promoted`).
  이전 순서는 **QA 먼저**다 — 같은 절차를 라이브에 적용하기 전에 QA 에서 한 번 실증한다.
  데이터 이전은 무중단이 아니므로 90GB 규모 복원 소요를 리허설로 실측해 전환 창을 산정하고,
  현행 호스트를 최소 1주 보존해 DNS 되돌림 경로를 남긴다.
- Consequences:
  - (+) 예외 경로가 사라진다. QA 에서 검증한 절차가 곧 라이브 절차다.
  - (+) 개발 활동과 서빙이 자원·장애 면에서 분리된다.
  - (+) 라이브 머신도 사내 CA·VPN DNS·SOPS 시크릿 등 QA 와 동일 통제를 받는다.
  - (−) 하드웨어가 2대 필요하다(QA + 라이브). GPU 선택(§6.3)이 비용에 직접 영향을 준다.
  - (−) 1회 전환 창(서비스 중단)이 발생한다. 데이터 이전이 포함되므로 무중단이 불가능하다.
  - (−) 이전 직후 한동안은 되돌림 경로(현행 호스트) 유지 비용이 든다.
- Supersedes: 없음 (ADR-20260826T140000 은 라이브 위치를 "별개 결정" 으로 남겼고, 본 ADR 이
  그 빈칸을 채운다)
- Superseded By: —

## ADR-20260827T100000-gpu-free-by-local-llm-retirement
- Status: proposed (사용자 승인 대기)
- Date: 2026-08-27
- Context: rev.2 는 GPU 를 "스펙의 결정 변수" 로 두고 A/B/C 선택을 요청했다. 근거는 임베딩
  (`bge-m3`)이 `embed-ollama` 컨테이너에 GPU 상주(`OLLAMA_KEEP_ALIVE: -1`)한다는 실측이었다.
  사용자 답변은 선택지 중 하나가 아니라 **전제 자체의 변경**이었다 — "로컬 LLM 은 더 이상
  사용되지 않아야 하며, 임베딩도 전용 계정으로 사내 MCP 를 호출하는 방식으로 이관한다."
  요청에 따라 코드로 실태를 확인한 결과: **대화·보조 chat LLM(gemma/edge)은 이미 제거됐고
  (2026-07-30 edge-free + feature-0043 fail-closed 차단), 임베딩 한 축만 남아 있으며 그것이
  유일한 GPU 소비자**다.
- Decision: QA·라이브 스펙을 **GPU 불요** 기준으로 산정한다(8~12 vCPU / 32GB / 400GB NVMe).
  단 임베딩 이관은 본 feature 의 범위가 아니므로, 그 완료를 **QA 세팅의 선행 조건**으로
  명시하고 순서 권고를 남긴다 — **이관 먼저 → QA 세팅**.
  이관의 기술 제약 2가지를 설계서에 기록한다: ① 벡터 차원 **1024 유지 필수**
  (`AGENT_KB_EMBEDDING_DIM` · `texts.embedding vector(1024)` — 다르면 스키마 마이그레이션 +
  전량 재임베딩) ② 전송 계약이 OpenAI 호환 `/v1/embeddings` 면 litellm alias 한 줄 교체로
  **앱 무변경**, 순수 MCP 도구 호출이면 어댑터가 필요하다(litellm 앞단 프록시 권장).
- Consequences:
  - (+) 하드웨어 비용에서 가장 큰 단일 항목(GPU 2장)이 사라진다.
  - (+) 서비스 23 → 22, RAM −2GB, 디스크 −4.6GB, 상시 최대 CPU 소비원 제거.
  - (+) 앱 코드가 alias 이름만 참조하므로 이관의 코드 변경 면이 작다(소비처 3경로 무변경 가능).
  - (−) **사내 임베딩 MCP 가 KB 기능(검색·분석·샘플)의 SPOF** 가 된다. 가용성·타임아웃·
    degrade 동작을 이관 시 함께 정해야 한다.
  - (−) feature-0043 이 확립한 "LLM 자격증명을 어느 대상에도 두지 않는다" 에 **임베딩 전용
    계정이라는 예외**가 생긴다. 범위(임베딩 전용·최소 권한)를 명시하고 SOPS 에 포함한다.
  - (−) **순서 제약**: 이관 전에 QA 를 세우면 GPU 투입(비용) 또는 CPU 기준 타임아웃 재조정
    (공수)이 필요하고, 이관 후 그것을 되돌려야 한다. 그 사이 QA 의 성능 검증은 최종 구성을
    대표하지 못한다.
- Supersedes: rev.2 의 "GPU = 결정 변수 A/B/C" 제시를 대체한다(선택이 아니라 전제 변경).
- Superseded By: —

## ADR-20260827T100100-svn-manifest-only-fileserver-tar
- Status: proposed (사용자 승인 대기)
- Date: 2026-08-27
- Context: rev.2 는 SVN 이 삭제해도 리비전 이력에 blob 을 남긴다는 특성 때문에 이미지 tar 를
  어디에 둘지를 안 A/B 로 제시했다. 사용자가 **안 A** 를 선택했다.
- Decision: **SVN 은 매니페스트·시크릿 암호문·스크립트(텍스트)만** 담고, 이미지 tar 는
  **사내 파일서버**에 둔다. 매니페스트의 각 이미지 항목이 `url` + `sha256` 으로 두 저장소를
  잇는다. 파일서버는 최근 N 세대(권장 5)만 유지하고 그 이전은 삭제하되, **롤백 대상인
  last-good 세대는 반드시 남긴다**.
- Consequences:
  - (+) SVN 저장소가 텍스트만 담아 가볍게 유지되고 checkout 이 빠르다.
  - (+) 오래된 tar 를 파일서버에서 그냥 삭제해 용량을 회수할 수 있다(SVN 이었다면 불가).
  - (+) "그때 무엇을 배포했는가" 는 매니페스트가 영구 보존하므로 tar 가 사라져도 답할 수 있다.
  - (−) 전달 채널이 둘(SVN + 파일서버)이 되어 자격증명·경로 규약이 하나 더 필요하다.
  - (−) tar 가 삭제된 릴리즈로 되돌아가려면 재빌드가 필요하다 — 보관 세대 수가 곧 무재빌드
    롤백 가능 범위다.
- Supersedes: ADR-20260827T090000 의 산출물 배치(SVN 단일) 부분을 구체화한다.
- Superseded By: —
