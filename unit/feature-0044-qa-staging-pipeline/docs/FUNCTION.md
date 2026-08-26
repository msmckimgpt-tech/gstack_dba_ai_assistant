---
doc_type: FUNCTION
feature_id: feature-0044-qa-staging-pipeline
status: draft
edit_policy: rewrite
source_of_truth: true
---

# Function

## 1. Summary

라이브 배포 전 단계로 **격리망 QA 머신**을 세우고, 라이브까지 전용 호스트로 분리하면서,
빌드 머신 → SVN 산출물 저장소 → QA → 라이브로 이어지는 **단방향 승격형 CI/CD 파이프라인**을
구성한다.

핵심 전환은 세 가지다.

1. **빌드 위치의 이동** — 현행 `bin/deploy-web.sh` 는 배포 대상 호스트에서 `git checkout
   origin/main` + `docker build` 를 수행한다. QA 는 사내 저장소만 도달 가능하므로 대상 호스트
   빌드가 성립하지 않는다. 빌드는 한 곳(`bin/release-build.sh`)에서 하고, QA·라이브는
   **같은 산출물을 설치하기만** 한다(build once, deploy many).
2. **전달 수단의 대체** — 사내 컨테이너 레지스트리가 없으므로 `docker pull` 이라는 표준
   경로가 없다. `docker save` tar + **sha256(전송 무결성) + image_id(설치 등가성)** 2중 대조가
   레지스트리의 신원 보증 역할을 대신한다.
3. **배포 방향의 역전** — 빌드 머신이 대상에 밀어넣는 대신 대상이 SVN 을 폴링해 당겨온다.
   VPN 인바운드 구멍이 필요 없고, 승격은 재빌드가 아니라 **매니페스트 표식**이 된다.

사용자의 서비스 접근 경로가 MCP 연결/역연결(feature-0041 도구 표면 + feature-0043 pull
브리지)이므로, 본 파이프라인의 **완료 기준은 컨테이너 health 가 아니라 VPN 밖 사용자
머신에서의 MCP 왕복 성공**이다(AGENTS.md §16.3 bring-up/access 완료 기준).

상세 절차·명령·다이어그램의 정본은 [CICD_DESIGN.md](./CICD_DESIGN.md) 이며, 본 문서는
범위·계약·비범위를 정의한다.

## 2. Goal

- REQ-20260826-qa-staging-pipeline: 격리망 QA 머신을 라이브 승격 전 필수 관문으로 세우고,
  라이브를 전용 호스트로 분리하며, 빌드→QA→라이브를 관통하는 단일 산출물 신원 기반의
  재현 가능한 배포 경로를 구성한다. 대상 머신은 아웃바운드로 사내 저장소만 사용하며,
  배포·검증·되돌리기가 사람의 수동 조작 없이 재현된다.

### 2.1 확정 전제 (사용자 결정, 2026-08-26 ~ 08-27)

| # | 축 | 결정 | 파생 제약 |
|---|---|---|---|
| 1 | QA망 개방도 | **사내 저장소만** (인터넷 차단) | 베이스 이미지·패키지 사전 확보 필수. QA 빌드 금지 |
| 2 | 사내 git 저장소 | **없음** — 필요 시 **SVN** 구축 예정 | GitLab CI 전제 폐기 → 릴리즈 빌드 스크립트 1개 |
| 3 | SVN 역할 | **릴리즈 산출물 저장소만** | git(GitHub)이 개발 정본. 정본 이원화 없음 |
| 4 | 컨테이너 레지스트리 | **없음** | `docker save` tar + sha256/image_id 2중 대조 |
| 5 | 패키지 미러 | **미확인** (남은 유일한 미결정) | Dockerfile 을 `ARG` 로 2안 지원 (미러 index / wheel 번들) |
| 6 | 빌드 주체 | 개발 머신 임시 → **차후 사내 빌드 서버 이관** | 빌드 절차를 스크립트 1개로 고정, 이관 시 등가성 1회 검증 |
| 7 | VPN DNS | **도메인 해석 가능** | `WEB_PUBLIC_HOST` 그대로. OAuth 리다이렉트 자연 동작 |
| 8 | TLS | **사내 CA 서명** | MCP 클라이언트 추가 설정 불요. `/trust/` CA 배포 경로 불요 |
| 9 | QA 데이터 | 라이브 복제본 그대로, **반출 승인 불요** | QA 머신을 **운영 등급**으로 취급 (통제는 설정으로) |
| 10 | 라이브 위치 | **QA 와 함께 전용 호스트로 분리** | QA·라이브가 같은 러너·같은 스크립트, 채널만 다름 |

## 3. In Scope

### P0-A. 폐쇄망 빌드 재현성 (선행 필수)
- 모든 `Dockerfile` 의 `FROM` 을 `${BASE_REGISTRY}` 로 파라미터화하고, 베이스 이미지를
  빌드 머신이 1회 확보해 tar 로 보관한다(레지스트리 부재).
- pip 설치를 `ARG` 로 2안 지원 — 사내 미러 index 또는 오프라인 wheel 번들. 어느 쪽이든
  `requirements*.txt` **버전/해시 고정**은 공통 필수.
- compose 외부 이미지의 **이동 태그 제거** — 실측 확인된 `ollama/ollama:latest` ·
  `caddy:2` 를 포함해 패치 버전까지 핀하고 tar 로 보관. 커스텀 `kb-pg-age:pg16` 은 릴리즈
  산출물로 승격.
- 종료 조건: **네트워크 차단 상태에서 전체 빌드 성공**.

### P0-B. 릴리즈 빌드 + 매니페스트
- `bin/release-build.sh` 신설 — test → build → save → sign → push 5단계. 개발 머신과
  사내 빌드 서버에서 **동일하게 동작**해 이관 비용을 0 에 수렴시킨다.
- ②build 에 `--build-arg GIT_COMMIT=$(git rev-parse HEAD)` 주입 필수(배포 완결 판정이
  컨테이너의 `GIT_COMMIT` 재확인에 의존).
- **릴리즈 매니페스트** — 이미지별 `sha256`(전송 무결성) + `image_id`(설치 등가성) + tag ·
  `git_commit` · `built_by` · alembic head · `.env` **키 목록(값 아님)** · MCP API 버전 ·
  러너 호환 하한 · 필수 스모크 목록.
- `transport` 필드로 **획득 경로를 추상화** — 미래에 레지스트리가 생기면 빌드 스크립트와
  매니페스트만 바뀌고 배포 러너는 무변경.

### P0-C. SVN 산출물 저장소
- 레이아웃 `releases/<tag>/{manifest.json, images/, env/, scripts/}` + `promoted/current.json`.
- 권한: 빌드 머신 쓰기 / QA·라이브 **읽기 전용** / 승격자만 `promoted` 쓰기.
- **용량 정책 결정 필요** — SVN 은 삭제해도 이력 blob 이 남는다. 안 A(매니페스트만 SVN,
  tar 는 파일서버 · 권장) / 안 B(tar 까지 SVN · 증가량 사전 계산 필요).

### P0-D. 대상 머신 부트스트랩 (QA·라이브 공통)
- 오프라인 기반 설치 + read-only 자격증명.
- **시크릿**: SOPS+age 암호문을 산출물 저장소에, 복호화 키만 대상 머신에 1회 배치.
  매니페스트 키 목록과 실제 배치를 preflight 로 대조.
- **LLM 자격증명 미배치** — feature-0043 서버측 LLM 차단이 코드 기본값이라 어느 대상에도
  Claude 계정 자격증명이 필요 없다(KB 임베딩은 로컬 bge-m3 라 계정 무관).
- **데이터**: QA 는 라이브 복제본(`bin/backup.sh` → `bin/restore-rehearsal.sh` 로 적재 검증),
  경유지 최소화 + 사본 삭제 절차.
- **TLS**: 사내 CA 서명 인증서 + SAN 검증 + 갱신 주기 관리.

### P0-E. 배포 러너 (pull-based, QA·라이브 공통)
- `bin/release-agent.sh --channel {qa|promoted}` — systemd timer 상주. svn up 폴링 →
  매니페스트 로드 → tar 획득·sha256 대조 → `docker load` → **image_id 대조** → preflight →
  배포 → 스모크 → 결과 기록.
- `bin/deploy-web.sh --from-manifest` 확장 — 빌드 단계를 건너뛰고 매니페스트 이미지로 pin
  overlay 구성. **롤링·pre-drain·soak·last-good 롤백은 그대로 재사용**(현행 스크립트가 이미
  pin overlay 로 이미지를 고정하므로 확장 지점이 존재).
- preflight fail-closed: env 키 누락 · alembic head 불일치 · TLS 만료 · 디스크 · (promoted
  채널) QA 스모크 결과 부재.

### P0-F. 검증 게이트 + 승격
- **자동 스모크 6종**: health(+GIT_COMMIT) · 엣지 `/livez`·`/readyz` · **OAuth discovery 2종** ·
  `/api/ai/mcp` 프로토콜 · 대화 경로(`bin/smoke-conversation.sh` 재사용) · 브리지
  `list_open_requests` 왕복.
- **수동 QA**: VPN 밖 사용자 머신에서 MCP 연결 → 브라우저 OAuth 완주 → 도구 호출 → 웹 렌더.
  웹/UI 변경 시 PB-0008 시각검증.
- `bin/release-promote.sh` — `promoted/current.json` 갱신(재빌드 없음). 라이브 러너는 이
  파일만 보고, QA 스모크 결과가 없으면 거부한다.

### P0-G. 라이브 호스트 분리 (1회)
- QA 로 절차를 실증한 뒤 라이브 머신 구축 → **데이터 이전 리허설(90GB 규모 소요 실측)** →
  전환 창 공지 → 이전 → DNS 전환 → 현행 호스트 1주 보존(즉시 되돌림 가능).

## 4. Out of Scope

- **QA 데이터 마스킹 파이프라인** — 사용자 결정으로 복제본을 그대로 사용한다. 대신 그 선택의
  귀결(QA = 운영 등급)을 §9 와 SECURITY 정합 항목에 명시한다. PII 컬럼 한정 마스킹은 후속 후보.
- **컨테이너 레지스트리 구축** — 지금은 tar 릴레이. 다만 `transport` 추상화로 미래 도입 시
  러너 무변경 전환을 보장한다.
- **SVN 을 소스 미러로 사용** — 사용자 결정(산출물 저장소만). git↔svn 변환 상시화·정본 이원화 회피.
- **Kubernetes·ArgoCD 등 오케스트레이터 도입** — 단일 호스트 23서비스 규모에 과도. pull +
  선언적 매니페스트라는 핵심 아이디어만 채택.
- **GitHub 개발 흐름 변경** — PR·리뷰·Actions 게이트는 그대로.
- **VPN·방화벽 정책 자체의 설계** — 인프라 담당 영역. 필요한 도달성 요구사항만 명세한다.
- **feature-0041/0043 의 기능 변경** — 검증 대상으로 사용할 뿐 동작을 바꾸지 않는다.

## 5. Inputs

- 릴리즈 태그(annotated) · 포함 PR 목록
- 릴리즈 매니페스트(이미지 sha256/image_id · git_commit · alembic head · env 키 목록 ·
  API/러너 버전 · 필수 스모크)
- 베이스 이미지 tar + 의존성(미러 index 또는 wheel 번들)
- SVN read-only 자격증명 · SOPS age 키
- 라이브 백업 산출물(PG dump + MySQL dump)

## 6. Outputs

- 릴리즈 디렉토리 `releases/<tag>/` (매니페스트 · 이미지 tar · 시크릿 암호문 · 설치 스크립트)
- 대상 머신의 가동 스택 + 배포 상태 파일(`artifacts/deploy/deploy-web.state` 동형)
- QA 스모크 리포트 (6종 결과)
- `promoted/current.json` — 라이브 배포의 유일한 입력
- 실패 시: 자동 롤백(이전 릴리즈 이미지) + 사유 기록

## 7. Main Flow

1. `main` 머지 완료 → 릴리즈 태그 `v<날짜>-<seq>` 생성 → GitHub push
2. 빌드 머신에서 `bin/release-build.sh --tag <tag>`: test → build → save → sign → SVN push
3. QA 러너(`--channel qa`)가 새 릴리즈 감지 → 매니페스트 fetch → tar 획득 → sha256 대조 →
   `docker load` → image_id 대조
4. preflight: env 키 대조 · alembic head · TLS · 디스크 · last-good
5. `deploy-web.sh --from-manifest` → migrate(expand) → 무중단 롤링 → soak
6. 자동 스모크 6종 → 결과 기록
7. 수동 QA(사용자 머신 MCP 왕복 + 화면) 통과 → `release-promote.sh` 로 `promoted/current.json` 갱신
8. 라이브 러너(`--channel promoted`)가 동일 산출물로 3~6 반복 (QA 스모크 결과 부재 시 거부)

## 8. Edge Cases

- 베이스 이미지/의존성 미확보 → 빌드 단계 **즉시 실패**(대체 소스 자동 탐색 금지 — 조용한
  소스 대체가 QA 와 라이브의 바이트를 다르게 만든다)
- tar sha256 또는 image_id 불일치 → **중단, 재시도 없음**(신원 불일치는 재시도로 낫지 않는다)
- 대상 머신이 SVN 도달 불가 → 배포 스킵 + 알림. 마지막 성공 상태 유지(fail-closed)
- 매니페스트 env 키가 대상에 없음 → preflight 차단(배포 시작 안 함, 부분 기동 금지)
- alembic head 불일치(QA 복제본이 더 오래됨) → expand 적용 후 진행, contract 는 별도 cycle
- `promoted/current.json` 이 QA 미검증 릴리즈를 가리킴 → 라이브 러너가 스모크 결과 유무로 거부
- 빌드 머신 이관 후 산출물 불일치 → `built_by` 필드로 추적, 등가성 검증 재실행
- 개인 머신 러너 버전이 서버 API 와 불일치 → 명시적 버전 오류(무음 실패 금지)
- SVN 저장소 용량 임계 도달 → §3.4 정책에 따라 대응(안 A 면 파일서버 정리, 안 B 면 계획된 증설)

## 9. Error Handling

- 모든 게이트는 **fail-closed**. "일단 올리고 본다" 경로를 두지 않는다 — QA·라이브 모두
  운영 등급 데이터를 담고 있어 부분 기동 상태가 곧 노출면이다.
- 배포 실패 시 `deploy-web.sh --rollback` 이 이전 릴리즈 이미지로 복귀한다. tar 모드에서는
  이전 이미지가 로컬에 남아 재빌드 없이 즉시 복귀 가능하다.
- 스모크 실패는 배포를 롤백하되 **승격하지 않는 것**으로 라이브를 보호한다.
- **알려진 한계**: QA 데이터가 마스킹되지 않았으므로 QA 에서의 데이터 열람·반출은 라이브와
  동일한 감사 대상이다. 이 파이프라인은 그 사실을 제거하지 않고 명시할 뿐이다.
- **알려진 한계 2**: GPU 미탑재 QA 에서는 임베딩이 CPU 로 떨어져 성능·타임아웃 관련 검증
  결과가 라이브를 대표하지 못한다(CICD_DESIGN §6.3).

## 10. Acceptance Criteria

- AC-1: QA·라이브에서 `docker build` 없이 배포가 완료된다(산출물은 릴리즈 저장소에서만 온다).
- AC-2: 빌드·QA·라이브가 사용하는 이미지의 **sha256 과 image_id 가 매니페스트와 일치**함을
  대조 확인할 수 있다.
- AC-3: 배포는 인바운드 접속 없이 대상 머신의 pull 만으로 완결된다.
- AC-4: 배포 완료 판정에 OAuth discovery 2종 + MCP 도구 왕복이 포함되며, 실패 시 승격이 차단된다.
- AC-5: 시크릿은 저장소에 평문으로 존재하지 않고, 매니페스트 키 목록과 실제 배치가 preflight
  로 대조된다.
- AC-6: 임의 릴리즈에 대해 QA→라이브 승격이 **재빌드 없이** 매니페스트 표식만으로 수행된다.
- AC-7: 대상 머신에 LLM 계정 자격증명이 배치되지 않은 상태로 전 기능 QA 가 가능하다.
- AC-8: 네트워크 차단 상태에서 전체 이미지 빌드가 성공한다(폐쇄망 재현성).
- AC-9: 빌드 주체를 개발 머신 → 빌드 서버로 옮겼을 때 같은 커밋이 등가 산출물을 낸다.
- AC-10: 라이브 이전 후 `WEB_PUBLIC_HOST` 로 사용자 진입 경로가 동작하고, 되돌림 경로
  (현행 호스트 + DNS)가 최소 1주 유지된다.

## 11. 관련 문서

- 상세 설계·절차: [CICD_DESIGN.md](./CICD_DESIGN.md) (rev.2)
- 배포 스파인 정본: `unit/feature-0014-zero-downtime-deploy/docs/FUNCTION.md` ·
  `unit/feature-0020-zd-deploy-all/docs/FUNCTION.md`
- MCP 도구 표면: `unit/feature-0041-external-ai-tool-surface/docs/FUNCTION.md`
- 서버 LLM 차단 + pull 브리지: `unit/feature-0043-external-llm-bridge/docs/FUNCTION.md`
- 완료 기준: `AGENTS.md` §16.1~§16.3 · 보안 정합: `docs/SECURITY.md`
