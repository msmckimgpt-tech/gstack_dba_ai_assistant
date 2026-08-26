---
doc_type: DESIGN
feature_id: feature-0044-qa-staging-pipeline
status: draft
edit_policy: rewrite
source_of_truth: true
---

# QA 머신 CI/CD 설계 제안서 (rev.3 — 전제 전건 확정)

> 범위·계약·비범위의 정본은 [FUNCTION.md](./FUNCTION.md). 본 문서는 **전 과정의 절차·근거·
> 트레이드오프**를 담는다. 구현 전 제안 단계이며, 사용자 검토 후 TASK 로 분해한다.
>
> **rev.2 (2026-08-27)**: 초판(rev.1)은 "사내 GitLab + Container Registry 가 이미 있다" 는
> 전제로 작성됐으나 실제로는 **둘 다 없고**, 만든다면 SVN 기반이라는 사실이 확인되어
> 3·4단계를 재설계했다.
>
> **rev.3 (2026-08-27)**: SVN 용량 정책이 안 A 로 확정되고, **로컬 LLM 전면 폐지 방침**
> (임베딩까지 사내 MCP 로 이관)이 확인되어 GPU 요구가 사라졌다. 다만 그 이관이 QA 세팅의
> **선행 조건**이 되므로 §9 를 신설해 현황과 제약을 기록했다. 변경 요지는 §0.2·§0.3 참조.

---

## 0. 요약

### 0.1 세 문장

1. **빌드는 한 곳에서 한 번만** 하고, 산출물(이미지 tar)은 **sha256 으로 신원이 고정된 채**
   QA·라이브로 옮겨진다. 레지스트리가 없어도 "검증한 바이트가 배포된다" 는 계약은 성립한다.
2. **배포는 대상 머신이 당긴다(pull).** SVN 산출물 저장소를 폴링해 자기가 가져와 설치하므로
   VPN 인바운드 구멍이 필요 없고, 승격은 재빌드가 아니라 **매니페스트에 승격 표식을 다는 일**이다.
3. **완료 판정은 컨테이너 health 가 아니라 사용자 진입 경로**다. 이 서비스는 MCP 로 쓰이므로,
   VPN 밖 사용자 머신에서 OAuth 완주 + 도구 왕복이 되어야 "올라갔다"고 말한다.

### 0.2 확정 전제 (사용자 결정)

| # | 축 | 결정 | 설계 귀결 |
|---|---|---|---|
| 1 | QA망 개방도 | 사내 저장소만 (인터넷 차단) | 베이스 이미지·패키지를 전부 미리 확보해야 함. QA 빌드 불가 |
| 2 | 사내 git 저장소 | **없음.** 필요 시 **SVN** 구축 예정 | GitLab CI 전제 폐기 → **릴리즈 빌드 스크립트** + SVN 산출물 저장소 |
| 3 | SVN 역할 | **릴리즈 산출물 저장소만** (git 은 개발 정본 유지) | 정본 이원화 없음. SVN 은 "버전된 파일서버" |
| 4 | 컨테이너 레지스트리 | **없음** | `docker save` tar 릴레이 + sha256/이미지 ID 대조로 신원 고정 |
| 5 | 패키지 미러(PyPI/apt) | **미확인** | 2안 병기 — 미러 있으면 index 치환, 없으면 wheel 번들 |
| 6 | 빌드 주체 | 개발 머신 임시 → **차후 사내 빌드 서버로 이관** | 빌드 절차를 **스크립트 1개**로 고정해 이관 비용을 0 에 수렴시킴 |
| 7 | VPN DNS | 도메인 해석 가능/설정 가능 | `WEB_PUBLIC_HOST` 그대로 사용. OAuth 리다이렉트 자연 동작 |
| 8 | TLS | **사내 CA 서명** | MCP 클라이언트가 추가 설정 없이 접속. `/trust/` CA 배포 절차 불요 |
| 9 | QA 데이터 | 라이브 복제본 그대로 (마스킹 없음), **반출 승인 불요** | QA 머신을 **운영 등급**으로 취급. 통제는 절차가 아니라 설정으로 |
| 10 | 라이브 위치 | **QA 와 함께 전용 호스트로 분리** | QA·라이브가 **같은 러너·같은 스크립트**를 쓰고 채널만 다름 |
| 11 | SVN 용량 정책 | **안 A** — 매니페스트·설정·스크립트만 SVN, 이미지 tar 는 사내 파일서버 | SVN 저장소가 가볍게 유지됨. 오래된 tar 는 파일서버에서 삭제 가능 |
| 12 | 로컬 LLM | **전면 미사용** — 임베딩까지 사내 MCP 로 이관 예정 | **GPU 불요** → 스펙 하향. 단 이관 완료가 QA 세팅의 **선행 조건** (§9) |
| 13 | 임베딩 MCP 위치 | **사내 망 내부** | 아웃바운드 예외 불요. 대신 **사내 서비스 의존**이 KB 기능의 새 SPOF |

10번 결정이 설계를 단순하게 만든다. 라이브가 개발 머신에 남았다면 "라이브만 예외 경로" 를
평생 유지해야 했지만, 분리하면 **QA 와 라이브는 채널 이름만 다른 동일 구성**이 된다.

12번 결정은 스펙을 낮추지만 **순서 제약을 만든다** — 임베딩이 아직 로컬(GPU 상주)인 채로
QA 를 세우면 GPU 없는 머신에서 임베딩이 CPU 로 떨어져 타임아웃 cliff 위험이 생긴다. §9 참조.

### 0.3 rev.1 대비 변경점

| 영역 | rev.1 | rev.2 |
|---|---|---|
| CI 실행처 | 사내 GitLab CI 5스테이지 | **`bin/release-build.sh` 1개** (개발 머신 → 빌드 서버 이관) |
| 이미지 전달 | GitLab Container Registry pull | **`docker save` tar + sha256 대조 + `docker load`** |
| 산출물 저장소 | Registry + git 태그 | **SVN `/releases/<tag>/`** (+ 대용량은 파일서버, §3.4 경고) |
| 승격 표현 | `promote/<tag>` git 태그 | **`/promoted/current.json`** (SVN) |
| 라이브 | 현행 호스트 유지 (별개 결정) | **전용 호스트로 분리** — QA 와 동일 절차 |
| 스펙 | 미정 | **§6 권장 스펙 산출** (실측 근거) |

### 0.3.1 rev.2 → rev.3

| 영역 | rev.2 | rev.3 |
|---|---|---|
| SVN 용량 | 안 A/B 선택 필요 | **안 A 확정** — 매니페스트만 SVN, tar 는 파일서버 |
| GPU | 결정 변수 (A/B/C 선택 필요) | **불요** — 로컬 LLM 전면 폐지 방침 |
| 스펙 | 16 vCPU / 48GB / 500GB / GPU | **8~12 vCPU / 32GB / 400GB / GPU 없음** |
| 임베딩 | 로컬 bge-m3(GPU 상주) 전제 | **사내 MCP 이관** — §9 신설(현황·제약·선행 조건) |
| 서비스 구성 | 23개 | `embed-ollama` 제외 **22개** (이관 완료 후) |

---

## 1. 현재 상태와, QA 를 그대로 얹으면 깨지는 지점

### 1.1 현행 (as-is)

| 축 | 현재 |
|---|---|
| 개발·라이브 위치 | 동일 WSL 호스트(20 vCPU / 39GB RAM / GTX 1660 SUPER 6GB) |
| 소스 정본 | GitHub `msmckimgpt-tech/gstack_dba_ai_assistant` |
| CI | GitHub Actions `ci.yml` — pytest(차단) · ruff(비차단) · migrate-lint · ROUTEMAP/codenav gate |
| CD | `sudo -E bin/deploy-web.sh` — `origin/main` HEAD 를 **로컬에서 build** → `:<sha>` 로 pin → 무중단 롤링 + soak + last-good 자동 롤백 |
| 레지스트리 | **없음** (로컬 이미지 스토어) |
| 시크릿 | `.env` · `.env.mysql` · `.env.postgres` · `.env.secret` · `.env.llm` · `.env.minio` — git 미포함 |
| 서비스 | compose 23개 · 런타임 데이터 90GB · 임베딩은 **GPU 상주**(bge-m3) |

배포 스파인은 성숙하다 — flock 직렬화, 프로덕션 file-set 격리, TLS preflight, migrate-lint
hard gate, build-once 핀, one-at-a-time + pre-drain, post-cutover soak, 자동 롤백.
**이 스파인은 유지한다.** 바꾸는 것은 "이미지를 어디서 얻는가" 하나다.

### 1.2 깨지는 지점 4가지

**(a) 대상 호스트 빌드가 성립하지 않는다.**
현행 CD 의 첫 단계는 대상 호스트의 `docker build` 다. QA 는 인터넷이 막혀 `FROM
python:3.11-slim` 도 `pip install` 도 나가지 못한다. 미러를 붙여도 lock 없이는 시점에 따라
다른 버전을 받아 개발 머신과 **다른 바이트**가 된다 — "dev 에서는 되는데 QA 에서 안 된다"가
재현 불가능한 형태로 생긴다.

**(b) 이미지를 옮길 표준 경로가 없다.**
레지스트리가 없으므로 `docker pull` 이라는 표준 전달 수단이 없다. 그렇다고 각 머신이 각자
빌드하면 (a) 로 되돌아간다. **전달 수단이 없다는 것이 곧 각자 빌드하라는 뜻은 아니다** —
tar + 체크섬이 레지스트리의 역할을 대신할 수 있다.

**(c) QA 머신이 운영 등급 자산이 된다.**
라이브 복제본을 마스킹 없이 적재하므로 QA 는 이름만 QA 이고 데이터는 운영이다. QA 는
성격상 계정이 헐거워지기 쉬운데(공용 테스트 계정, 단순 비밀번호), 그 순간 전체에서 가장
약한 고리가 된다. 반출 승인이 불요하다는 것은 **옮겨도 된다**는 뜻이지 **아무렇게나 둬도
된다**는 뜻이 아니다.

**(d) "올라갔다"의 정의가 다르다.**
사용자는 웹 화면이 아니라 **자기 머신의 AI 런타임(MCP)** 으로 쓴다. 컨테이너가 healthy 여도
VPN DNS·사내 CA·OAuth discovery 중 하나만 어긋나면 진입 자체를 못 한다. 컴포넌트 health 로
완료를 선언하면 "기동은 됐는데 못 쓴다" 는 재보고가 발생한다.

---

## 2. 목표 구조 (to-be)

```
 빌드 머신                     SVN 산출물 저장소            QA 머신              라이브 머신
 (지금: 개발 WSL              /releases/<tag>/            (격리망, VPN)        (신규 분리)
  차후: 사내 빌드서버)         ├ manifest.json
      │                        ├ images/*.tar.zst          채널: qa            채널: promoted
  worktree cycle               ├ env/*.enc                      │                    │
      │                        └ scripts/                       │                    │
   PR → main ──(GitHub Actions PR 게이트)                       │                    │
      │                              ▲                          │                    │
  릴리즈 태그 v2026.08.27-1          │                          │                    │
      │                              │                          │                    │
  bin/release-build.sh ──────────────┘                          │                    │
   ① test  (컨테이너 pytest + 게이트)                           │                    │
   ② build (사내 미러/wheel 번들 · GIT_COMMIT 주입)             │                    │
   ③ save  (docker save | zstd → tar)                           │                    │
   ④ sign  (sha256 + manifest.json)                             │                    │
   ⑤ push  (svn import)                                         │                    │
                                                                 │                    │
                                              bin/release-agent.sh (동일 스크립트)     │
                                                svn up 폴링 → sha256 재대조            │
                                                → docker load → 이미지 ID 대조         │
                                                → preflight → deploy-web.sh            │
                                                   --from-manifest                     │
                                                → 롤링 + soak → 자동 스모크 6종        │
                                                         │                             │
                                              수동 QA (VPN 밖 사용자 머신 MCP 왕복)     │
                                                         │                             │
                                           /promoted/current.json 갱신 ────────────────┘
                                              (라이브는 이 파일만 본다)
```

### 2.1 다섯 가지 원칙

1. **한 번 빌드, 어디서나 배포** — 이미지 tar 의 sha256 과 load 후 이미지 ID 가 dev→QA→live 를
   관통하는 단일 신원. 재빌드는 그 등가성을 깨뜨린다.
2. **대상이 당긴다(pull)** — 인바운드 방화벽 구멍 불필요, 배포 자격증명이 빌드 머신에 없어도 됨,
   대상 장애가 빌드 쪽으로 전파되지 않음.
3. **승격은 재빌드가 아니라 표식** — `/promoted/current.json` 갱신. 사람이 승인하는 대상이
   "코드"가 아니라 "검증된 산출물"이다.
4. **QA 머신 = 운영 등급** — 데이터가 운영이므로 통제도 운영. 이름으로 등급을 정하지 않는다.
5. **완료 = 사용자 진입 경로 도달성** — health 가 아니라 MCP 왕복 (AGENTS.md §16.3).

### 2.2 검토했으나 택하지 않은 대안

| 대안 | 페르소나 | 채택하지 않은 이유 |
|---|---|---|
| **A. 각 머신에서 빌드** | 전달 인프라를 만들기 싫은 팀 | §1.2(a). 폐쇄망 빌드 재현성이 성립하지 않고 "검증한 바이트 ≠ 배포한 바이트" 가 된다 |
| **B. 빌드 머신이 대상에 push** | 스크립트로 끝내려는 팀 | 배포 자격증명·인바운드 경로가 빌드 머신에 상주. 빌드 머신 침해가 곧 운영 데이터 접근. 사용자 결정(SVN 경유)과도 어긋남 |
| **C. 레지스트리 먼저 구축** | 장기 정석을 원하는 팀 | 방향은 옳으나 QA 도입 일정 앞에 인프라 과제를 하나 더 얹는다. **§3.5 의 추상화로 나중에 무비용 전환**할 수 있게 설계했다 |
| **D. SVN 을 소스 미러로도 사용** | 사내 표준이 SVN 인 조직 | git↔svn 변환이 상시 필요하고 브랜치·머지 이력이 단순화되어 사실상 정본이 둘이 된다. 사용자 결정(산출물 저장소만)과 정합 |
| **E. Kubernetes + ArgoCD** | 다중 노드 플랫폼 팀 | 단일 호스트 23서비스 규모에 과도. 다만 **pull + 선언적 매니페스트**라는 GitOps 핵심은 채택 |

---

## 3. 단계별 상세

### 단계 0 — 저장소 지형 정리 (선행 1회)

**정본 규칙**
- **GitHub = 개발 정본.** PR·리뷰·CI 게이트는 지금 그대로. 변경 없음.
- **SVN = 산출물 저장소.** 소스를 넣지 않는다. 넣는 것은 빌드 결과와 그 설명뿐이다.

**SVN 레이아웃**
```
svn://<사내>/ai-assistant-releases/
├── releases/
│   ├── v2026.08.27-1/
│   │   ├── manifest.json          # 계약서 (§3.3)
│   │   ├── images/                # (§3.4 — 용량 경고 참조)
│   │   │   ├── web.tar.zst
│   │   │   └── agent.tar.zst
│   │   ├── env/                   # SOPS 암호문만
│   │   │   ├── qa.env.enc
│   │   │   └── live.env.enc
│   │   └── scripts/
│   │       └── release-agent.sh   # 이 릴리즈를 설치하는 스크립트 (동봉)
│   └── v2026.08.28-1/
└── promoted/
    └── current.json               # 라이브가 보는 유일한 파일
```

**접근 권한**
- 빌드 머신: `releases/` **쓰기**
- QA 머신: 전체 **읽기 전용**
- 라이브 머신: 전체 **읽기 전용**
- 승격자(사람 또는 QA 러너): `promoted/current.json` **쓰기**

읽기 전용을 구조적으로 강제하는 이유는 "QA 에서 급히 고친 것이 저장소에만 남는" 최악의
상황을 만들지 않기 위해서다.

---

### 단계 1 — 폐쇄망 빌드 재현성 (**작업량의 대부분**)

지금 Dockerfile·compose 는 공개 인터넷을 전제한다. 이 단계를 통과하지 못하면 뒤가 전부
성립하지 않는다.

**1-a. 베이스 이미지 확보 — 레지스트리가 없으므로 tar 로**

레지스트리가 없으니 "사내 미러에서 pull" 이 불가능하다. 베이스 이미지도 **빌드 머신이
한 번 받아서 보관**하고, 빌드는 로컬 이미지 스토어를 쓴다.

```bash
# 최초 1회 (인터넷 되는 곳에서) — 버전을 반드시 고정
docker pull python:3.11-slim
docker save python:3.11-slim | zstd -T0 > base/python-3.11-slim.tar.zst
sha256sum base/*.tar.zst > base/SHA256SUMS
```

compose 의 외부 이미지도 같은 취급이다. **현행에서 이동 태그를 쓰는 것들을 먼저 고정해야
한다** — 아래는 실제 참조 실측:

| 서비스 | 현행 참조 | 위험 | 조치 |
|---|---|---|---|
| `embed-ollama` | **`ollama/ollama:latest`** | 최상 — `latest` 는 언제든 바뀐다 | 패치 버전 핀 후 tar 보관 |
| `caddy` | **`caddy:2`** | 높음 — major 태그는 이동한다 | `caddy:2.x.y` 핀 |
| `postgres`(KB) | `${KB_PG_IMAGE:-pgvector/pgvector:pg16}` (라이브는 커스텀 `kb-pg-age:pg16`) | 중 — 커스텀 이미지의 재현 경로가 문서화돼 있지 않음 | **CI 산출물로 승격**해 매 릴리즈 tar 에 포함 |
| `mcp`(dbhub) | `bytebase/dbhub:${DBHUB_IMAGE_TAG}` | 중 | 태그 실값 고정 + tar |
| `mysql` · `minio` · `pgbouncer` · `litellm` | 각 공개 이미지 | 중 | 패치 핀 + tar |

> `caddy:2` 나 `ollama:latest` 를 그대로 두면 QA 와 라이브가 서로 다른 시점에 받은 **다른
> 이미지**를 쓰게 된다. 이런 차이는 증상이 늦게·이상하게 나타난다.

**1-b. 패키지 소스 — 미러 유무 2안 (미확인 축)**

사내 PyPI/apt 미러 존재 여부가 아직 확인되지 않았다. 어느 쪽이든 **버전/해시 고정은 공통
필수**이고, 다른 것은 소스 지정 방식뿐이다.

*안 A — 미러 있음 (선호)*
```dockerfile
ARG PIP_INDEX_URL=https://<사내 PyPI 미러>/simple
ARG PIP_TRUSTED_HOST=<사내 미러 호스트>
RUN pip install --no-cache-dir --require-hashes -r requirements.txt
```

*안 B — 미러 없음 (오프라인 wheel 번들)*
```bash
# 빌드 머신에서 1회 (인터넷 가능 시점)
pip download -r requirements.txt -d vendor/wheels --platform manylinux2014_x86_64 \
    --python-version 311 --only-binary=:all:
# Dockerfile
COPY vendor/wheels /wheels
RUN pip install --no-index --find-links=/wheels -r requirements.txt
```
안 B 는 동작하지만 의존성 갱신마다 수작업이 붙는다. 미러가 확인되면 안 A 로 전환한다
(Dockerfile 은 두 경로를 모두 지원하도록 `ARG` 로 분기).

**1-c. 검증 — 이 단계의 종료 조건**

개발 머신에서 **네트워크를 끊고**(또는 사내 미러만 허용하는 네임스페이스에서) 전체 빌드가
성공해야 한다. 통과하지 못하면 QA 에서도 실패한다. 이것이 Phase 1 의 유일한 합격 판정이다.

---

### 단계 2 — 릴리즈 컷 (개발 머신)

`main` 이 배포 가능 상태가 되면 **annotated 태그**를 자른다.

```bash
git tag -a v2026.08.27-1 -m "release: <요약>

포함 PR: #1340 #1344 #1345 #1346
마이그레이션: alembic 0041 (expand only)
주의: ext-tool-mcp 재기동 필요"
git push origin main --follow-tags
```

- 형식 `v<YYYY.MM.DD>-<seq>` — 날짜 기반이 사내 커뮤니케이션에 유리하다(semver 는 "무엇이
  breaking 인가" 합의 비용이 드는데, 내부 서비스에는 과하다).
- 태그 메시지가 릴리즈 노트 초안이며 `docs/RELEASE_NOTES.md` 와 연결된다.
- **커밋 규칙(`CONTRIBUTING.md §5`)은 변경 없음.** 릴리즈 태그는 커밋 축과 직교한다.
- SVN 에는 태그를 넣지 않는다. SVN 이 받는 것은 그 태그로 빌드한 **결과물**이다.

---

### 단계 3 — 릴리즈 빌드 (`bin/release-build.sh`)

**설계의 핵심은 "이 절차가 스크립트 1개"라는 것**이다. 지금은 개발 머신에서 돌고 나중에
사내 빌드 서버에서 돌지만, **같은 스크립트가 같은 커밋에서 같은 산출물을 낸다**. 이관은
"다른 머신에서 같은 스크립트를 실행" 이 전부다.

```bash
sudo -E bin/release-build.sh --tag v2026.08.27-1
```

**5 단계**

| # | 단계 | 내용 |
|---|---|---|
| ① | test | `make test` (컨테이너 pytest + ruff) + `migrate-lint --heads` + `gen-routemap --check` + `codenav-lint` — GitHub Actions 게이트와 동일 집합을 **빌드 머신 로컬에서** 재실행 |
| ② | build | 단계 1 파라미터로 `mysql-ai-web` · `mysql-ai-agent` (+ 커스텀 KB PG) 빌드. **`--build-arg GIT_COMMIT=$(git rev-parse HEAD)` 필수** |
| ③ | save | `docker save <img> \| zstd -T0 -19 > images/<name>.tar.zst` |
| ④ | sign | 각 tar 의 sha256 + `docker image inspect --format '{{.Id}}'` 를 매니페스트에 기록 |
| ⑤ | push | `svn import` 로 `releases/<tag>/` 생성 (기존 디렉토리 있으면 거부 — 릴리즈는 불변) |

②의 `GIT_COMMIT` 주입이 빠지면 배포 완결 판정(컨테이너에서 `GIT_COMMIT` 을 다시 읽어
전부 도달했는지 확인하는 현행 방식)이 무너진다.

**왜 GitHub Actions 만으로 부족한가**: Actions 러너는 인터넷이 열린 ubuntu-latest 라
"사내 의존성만으로 빌드되는가"를 검증하지 못한다. ①을 빌드 머신에서 다시 도는 것은 중복이
아니라 **환경 검증**이다.

#### 3.3 릴리즈 매니페스트 — 배포의 계약서

```json
{
  "release": "v2026.08.27-1",
  "git_commit": "0b2b4435...",
  "built_at": "2026-08-27T02:10:00Z",
  "built_by": "dev-wsl-01",
  "images": [
    { "service": "web",   "file": "images/web.tar.zst",
      "sha256": "b3f1...", "image_id": "sha256:9a2c...", "tag": "mysql-ai-web:0b2b4435" },
    { "service": "agent", "file": "images/agent.tar.zst",
      "sha256": "77de...", "image_id": "sha256:41bb...", "tag": "mysql-ai-agent:0b2b4435" }
  ],
  "alembic_head": "0041_xxx",
  "migration_kind": "expand-only",
  "env_keys_required": ["DB_PASSWORD", "AGENT_KB_PG_PASSWORD", "WEB_SECRET_KEY", "..."],
  "mcp_api_version": "2026-08-01",
  "bridge_runner_min_version": "0.3.0",
  "smoke_required": ["health", "edge", "oauth-discovery", "mcp-protocol", "conversation", "bridge"]
}
```

- `sha256` = 전송 무결성. `image_id` = **load 후 등가성**. 둘 다 있어야 "받은 파일이
  온전한가" 와 "설치된 이미지가 빌드한 그것인가" 를 각각 답할 수 있다.
- `env_keys_required` 는 **키 이름만**이다. 값은 들어가지 않는다. preflight 가 이 목록으로
  대상 머신의 `.env*` 를 대조해 누락을 배포 전에 잡는다.
- `bridge_runner_min_version` — 개인 머신 러너와 서버 API 의 호환 하한. 이 축이 없으면
  서버만 올라가고 사용자 머신 러너가 조용히 실패한다.

#### 3.4 SVN 용량 정책 — **안 A 확정** (사용자 결정, §0.2 #11)

**SVN 은 파일을 삭제해도 리비전 이력에 blob 이 남아 저장소 용량이 줄지 않는다.** 이미지
tar 를 매 릴리즈 커밋하면 저장소가 단조 증가하고 `svn checkout` 이 갈수록 무거워진다.
`svnadmin dump | svndumpfilter` 로 잘라낼 수는 있으나 저장소 재구축(모든 클라이언트
재체크아웃)이 필요한 파괴적 작업이다.

따라서 **역할을 나눈다**:

| 저장소 | 담는 것 | 성격 |
|---|---|---|
| **SVN** `releases/<tag>/` | `manifest.json` · `env/*.enc` · `scripts/` — 전부 **텍스트, 수십 KB** | 이력이 남아야 하는 것. "무엇을 배포했는가"의 정본 |
| **사내 파일서버** `<base>/<tag>/images/` | 이미지 tar (`*.tar.zst`, 수백 MB~GB) | 이력이 필요 없는 것. 오래된 세대는 **그냥 삭제** |

매니페스트가 두 저장소를 잇는다 — 각 이미지 항목에 `url` + `sha256` 을 담아 러너가 파일서버
에서 받아 검증한다.

```json
"images": [
  { "service": "web", "url": "https://files.<사내>/ai-assistant/v2026.08.27-1/images/web.tar.zst",
    "sha256": "b3f1...", "image_id": "sha256:9a2c...", "tag": "mysql-ai-web:0b2b4435" }
]
```

**보관 정책**: 파일서버는 최근 N 세대(권장 5)만 유지하고 그 이전은 삭제한다. SVN 의
매니페스트는 영구 보존되므로 "그때 무엇을 배포했는가" 는 tar 가 사라져도 답할 수 있다
(다만 그 릴리즈로 되돌아가려면 재빌드가 필요하다 — 롤백 대상인 last-good 세대는 반드시 남긴다).

> 전달 채널이 둘이 되는 대가로 SVN 이 가볍게 유지된다. **매니페스트가 신원의 정본**이라는
> 계약은 동일하므로, 나중에 레지스트리로 옮겨도 러너의 `acquire_images()` 만 바뀐다(§3.5).

#### 3.5 나중에 레지스트리가 생겼을 때 — 무비용 전환 설계

러너의 "이미지 획득" 단계를 **함수 하나로 격리**한다.

```bash
acquire_images() {           # 매니페스트만 보고 로컬에 이미지를 준비한다
  case "$(manifest_get transport)" in
    tar)      fetch_tar && verify_sha256 && docker load ;;
    registry) docker pull "$(manifest_get image_ref)" ;;   # 미래
  esac
  verify_image_id            # 두 경로 공통 — 설치된 이미지가 매니페스트의 그것인가
}
```

매니페스트에 `transport` 필드를 두면, 레지스트리 도입 시 **빌드 스크립트와 매니페스트만
바뀌고 배포 러너·deploy-web.sh 는 무변경**이다.

---

### 단계 4 — 대상 머신 부트스트랩 (QA·라이브 공통, 각 1회)

QA 와 라이브가 **같은 절차**를 쓴다(§0.2 결정 10의 이득). 다르게 두는 것은 채널 이름과
데이터 원천뿐이다.

**4-1. 기반 설치**
docker + compose + zstd + svn 클라이언트. 사내 apt/yum 미러가 있으면 그대로, 없으면 빌드
머신 경유 오프라인 릴레이(다운로드 → sha256 대조 → scp → 전송본 재대조 → 의존성 사전
판정 → 설치).

**4-2. 자격증명 (모두 최소권한)**
- SVN **읽기 전용** 계정
- (안 A 채택 시) 파일서버 **읽기 전용** 계정
- 쓰기 권한을 주지 않는다 — 대상 머신이 침해돼도 산출물을 오염시킬 수 없다.

**4-3. 시크릿 배치 — SOPS + age**

`.env*` 6종은 git 에 없다. 세 방식 비교:

| 방식 | 장점 | 단점 | 권장 |
|---|---|---|---|
| **SOPS + age 암호문을 SVN 에** | 산출물 저장소가 시크릿의 정본. 변경 이력·리뷰 가능. 자동화와 정합 | 도구 도입 + 키 관리 | **기본안** |
| 사내 Vault | 중앙 회전·감사 | 이 규모엔 과함. Vault 자체가 새 SPOF | 사내에 이미 있으면 |
| 수동 scp 1회 | 즉시 가능 | 회전·이력·재현성 없음. "그 머신에만 있는 값" 발생 | 초기 임시만 |

```bash
# 빌드 머신 (1회) — 대상별 키 생성, 개인키는 그 머신에만 배치
age-keygen -o qa.agekey      # → QA 머신 /etc/ai-assistant/qa.agekey (0600)
age-keygen -o live.agekey    # → 라이브 머신
sops --encrypt --age <qa-pubkey>   .env.secret > env/qa.env.secret.enc
sops --encrypt --age <live-pubkey> .env.secret > env/live.env.secret.enc

# 대상 머신 (배포 러너가 수행)
SOPS_AGE_KEY_FILE=/etc/ai-assistant/qa.agekey sops --decrypt env/qa.env.secret.enc > .env.secret
chmod 600 .env.secret
```

**LLM 자격증명은 어느 대상에도 두지 않는다.** feature-0043 이 서버측 LLM 호출을
fail-closed 로 차단하므로(`AGENT_SERVER_LLM_ENABLED=0` 이 코드 기본값) Claude 계정
자격증명이 필요 없다. 시크릿 표면이 실질적으로 줄어드는 것이 이 구조의 부수 이득이다.
(KB 임베딩은 로컬 `bge-m3`/ollama 라 계정 무관 — 그대로 동작.)

**4-4. 데이터 적재**

*QA — 라이브 복제본 (마스킹 없음, 반출 승인 불요)*
- 원천: `bin/backup.sh` 산출물 (PG `agent_kb` + MySQL `agent_memory` 논리 백업)
- 적재 검증: `bin/restore-rehearsal.sh` 재사용(이미 "최신 백업을 throwaway DB 로 복원 검증"
  하는 도구로 존재한다)
- **경유지를 최소화한다.** 라이브 → QA 직접 전송이 원칙. 빌드/개발 머신을 경유하면 그
  머신도 운영 등급이 되므로, 부득이 경유했다면 사본 삭제까지 절차에 넣는다.
- 갱신 주기를 정한다(예: 주 1회 또는 릴리즈 전). 오래된 복제본은 마이그레이션 정합을
  어긋나게 하고, 너무 잦으면 반출이 상시화된다.

*라이브 — 현행 호스트에서 이전 (§5 별도 절차)*

**4-5. TLS — 사내 CA 서명**

- 사내 CA 로 `WEB_PUBLIC_HOST` 인증서를 발급받는다. 사내 PC 는 이미 그 CA 를 신뢰하므로
  브라우저·MCP 클라이언트 모두 추가 설정이 없다.
- SAN 에 도메인 + 필요 시 IP 를 넣는다. 배포 스크립트가 이미 TLS preflight(SAN/CA/만료)를
  하므로 게이트는 재사용된다.
- 갱신 주기를 캘린더에 넣는다 — 만료는 preflight 가 잡지만, 잡히는 시점이 배포 시점이라
  배포가 없으면 만료 당일까지 모른다.
- 기존 `/trust/` rootCA 배포 경로는 **불요**해진다(제거하지는 않고 비활성 유지).

---

### 단계 5 — 배포 러너 (`bin/release-agent.sh`, QA·라이브 공통)

대상 머신에 상주하는 systemd timer 가 수행한다. **QA 와 라이브가 같은 스크립트를 쓰고
채널만 다르다.**

```bash
# QA:    bin/release-agent.sh --channel qa
# 라이브: bin/release-agent.sh --channel promoted
```

```
[10분마다]
 1. svn up (read-only)
 2. 채널의 최신 릴리즈 확인
      qa       → releases/ 중 최신 (아직 승격 안 된 것 포함)
      promoted → promoted/current.json 이 가리키는 릴리즈만
    새 릴리즈 없으면 조용히 종료
 3. manifest.json 로드 + 무결성 확인
 4. acquire_images() — tar 받아 sha256 대조 → docker load → image_id 대조
      (하나라도 불일치 시 즉시 중단. 재시도하지 않는다 — 신원 불일치는 재시도로 낫지 않는다)
 5. preflight
      - env_keys_required vs 실제 .env*   → 누락 시 중단
      - alembic head 정합                  → expand 적용 가능 여부 판정
      - TLS SAN/만료                       → 기존 게이트 재사용
      - 디스크 여유 / 이전 last-good 존재
      - (promoted 채널) 매니페스트에 QA 스모크 결과가 있는가 → 없으면 거부
 6. bin/deploy-web.sh --from-manifest <path>
      → migrate(expand) → web 롤링(one-at-a-time + pre-drain + /readyz) → soak
      → 워커 롤아웃 → gateway reconcile
 7. 자동 스모크 (§6-A)
 8. 결과 기록
      QA:    스모크 결과를 로컬 + (승격 시) 매니페스트에 첨부
      라이브: 로컬 기록 + 실패 시 알림
```

**`deploy-web.sh` 확장 지점**

현행 스크립트는 이미 `artifacts/deploy/docker-compose.deploy-pin.yml` 로 이미지를 고정한다.
즉 **"이미지를 고정해 배포한다"는 뼈대가 이미 있고, 그 이미지를 어디서 얻는가만 다르다.**

| 현행 | `--from-manifest` 모드 |
|---|---|
| `git checkout origin/main` | 매니페스트의 `git_commit` 검증만 (checkout 불필요) |
| `docker compose build <svc>` | `acquire_images()` (tar load 또는 미래의 pull) |
| pin overlay `image: repo:<sha>` | pin overlay `image: <매니페스트의 tag>` |
| last-good = 이전 로컬 태그 | last-good = 이전 릴리즈의 image_id |
| 롤링·soak·롤백 | **그대로** |

기존 로컬 빌드 경로는 제거하지 않는다 — 개발 머신에서의 빠른 반복은 여전히 유효하다.

> **롤백이 더 안전해진다**: 이전 릴리즈 이미지가 로컬에 남아 있어 재빌드 없이 즉시 복귀한다.
> 현행의 "첫 배포 이전에는 last-good 이 없다" 문제도 릴리즈 이력으로 자연 해소된다.

---

### 단계 6 — QA 검증 게이트 (승격 조건)

**6-A. 자동 스모크** (배포 직후, 대상 머신 내부에서)

| # | 검사 | 통과 기준 | 이유 |
|---|---|---|---|
| 1 | 컨테이너 health | 전 서비스 healthy + `GIT_COMMIT` 일치 | 부분 완료를 완료로 보고하지 않기 위해 |
| 2 | 엣지 도달성 | Caddy 경유 `/livez`·`/readyz` 200 | 앱 health 만 보면 엣지 격리 상태를 놓친다 |
| 3 | **OAuth discovery** | `/.well-known/oauth-protected-resource` · `/.well-known/oauth-authorization-server` 200 | **MCP 클라이언트의 인증 접근성은 표준 discovery 유무가 좌우한다.** 여기가 404 면 서비스는 멀쩡한데 사용자는 연결조차 못 한다 |
| 4 | MCP 프로토콜 | `/api/ai/mcp` 정상 전송 응답 (GET 은 406 이 정상) | 컨테이너 healthcheck 와 동일 판정식 재사용 |
| 5 | 대화 경로 | 기존 `bin/smoke-conversation.sh` 재사용 | 최근 배포 게이트에 추가된 자산 |
| 6 | 브리지 왕복 | `list_open_requests` 정상 응답 | feature-0043 pull 브리지 생존 확인 |

**6-B. 수동 QA** (VPN 밖 사용자 머신 — 자동화로 대체 불가)

1. 사용자 머신 Claude Code 에 QA MCP 엔드포인트 등록 → 연결
2. 브라우저 OAuth 로그인·동의 완주 (VPN DNS + 사내 CA 가 여기서 실증된다)
3. 도구 1회 호출 → 결과 수신
4. 웹 화면에서 해당 task 기록이 렌더되는지 확인
5. 웹/UI 변경이 포함된 릴리즈면 PB-0008 실 브라우저 시각검증

> 이 5개가 곧 "사용자가 실제로 쓸 수 있는가"의 정의다. §1.2(d) 의 재보고를 막는 유일한 장치.

**6-C. 승격**

```bash
bin/release-promote.sh --release v2026.08.27-1 --qa-smoke-result <path> --by <검증자>
# → promoted/current.json 을 갱신하고 SVN 커밋
```

```json
{
  "release": "v2026.08.27-1",
  "promoted_at": "2026-08-27T09:30:00Z",
  "promoted_by": "<검증자>",
  "qa_smoke": { "passed": 6, "of": 6, "at": "2026-08-27T09:12:00Z" },
  "manual_qa": { "by": "<검증자>", "at": "2026-08-27T09:25:00Z", "pb0008": "n/a" }
}
```

재빌드 없음. 승격의 실체는 **"이 산출물을 라이브에 허용한다"는 서명**이다.

---

### 단계 7 — 라이브 이전 + 승격 운영

**7-1. 라이브 이전 (1회, §0.2 결정 10)**

현재 라이브는 개발 머신과 같은 호스트에서 돈다. QA 와 함께 전용 호스트로 분리한다.

권장 순서 — **QA 를 먼저 세워 절차를 실증한 뒤 라이브를 옮긴다**:

| 순서 | 작업 | 비고 |
|---|---|---|
| 1 | QA 머신 구축 + 파이프라인 실증 | 같은 절차를 라이브에 쓰기 전에 QA 에서 한 번 검증 |
| 2 | 라이브 머신 구축 (단계 4 동일 절차) | 데이터는 아직 넣지 않음 |
| 3 | 라이브 데이터 이전 리허설 | `backup.sh` → 신규 호스트 복원 → `restore-rehearsal.sh` 검증. **소요 시간 실측**(90GB 규모) |
| 4 | 전환 창 공지 + 실제 이전 | 현행 정지 → 최종 백업 → 복원 → 검증 |
| 5 | DNS 전환 (`WEB_PUBLIC_HOST` → 신규 IP) | TTL 을 미리 낮춰 둔다 |
| 6 | 되돌리기 준비 | 현행 호스트를 **최소 1주 보존**(즉시 DNS 되돌림 가능) |

전환 창은 무중단이 아니다(데이터 이전이 포함되므로). 90GB 복원 소요를 3번에서 실측해
공지 시간을 정한다.

**7-2. 정상 운영 시 라이브 배포**
- 라이브 러너는 `promoted/current.json` 만 본다. QA 에서 검증한 그 산출물이 그대로 간다.
- QA 스모크 결과가 매니페스트에 없으면 거부한다(QA 우회 승격을 구조적으로 차단).
- 되돌리기: `deploy-web.sh --rollback` — 이전 릴리즈 이미지로 즉시 복귀.
- 마이그레이션은 expand/contract 규율(`migrate-lint` hard gate)이 강제되므로 **코드 롤백에
  스키마 롤백이 따라붙지 않는다.** 이 규율을 QA·라이브 양쪽에서 유지한다.

---

## 4. 짚어야 할 위험 4가지

### 위험 A — 마스킹 없는 라이브 복제본 (반출 승인은 불요하지만 통제는 필요)

결정 자체를 뒤집자는 것이 아니라, 그 선택이 **자동으로 따라오게 만드는 의무**를 명시한다.

- QA 머신의 접근통제·감사로그(`WebAuditEvents`)·백업·폐기 절차가 라이브와 동일해야 한다.
- QA 계정을 공용/단순 비밀번호로 만들지 않는다 — 사번 기반 개별 계정, `admin.console.access`
  최소 부여. QA 는 이 규율이 느슨해지기 가장 쉬운 곳이고, 데이터는 운영이다.
- 데이터 반출 표면(첨부 다운로드·CSV·대화 내보내기)이 QA 에서도 열려 있으므로 감사 대상이다.
- 백업 산출물의 보관 위치·수명도 정한다. QA 백업이 통제 밖 경로에 쌓이면 그것이 새 노출면이다.
- **점진 개선안**: 복원 후처리로 **PII 컬럼만 치환**하는 스크립트는 비용 대비 효과가 크다.
  후속 cycle 후보로 남긴다(지금 범위 밖).

### 위험 B — SVN 저장소 용량 단조 증가

§3.4 참조. SVN 은 삭제해도 이력 blob 이 남는다. 안 A(매니페스트만 SVN, tar 는 파일서버)를
권장하며, 안 B 를 택한다면 증가량을 미리 계산해 디스크를 확보한다.

### 위험 C — 빌드 머신 이관 시점의 등가성

개발 머신 → 사내 빌드 서버로 옮길 때, **같은 커밋에서 같은 이미지가 나오는지 1회 검증**한다
(두 머신에서 빌드해 `image_id` 또는 최소한 주요 레이어 digest 를 비교). 완전한 bit-reproducible
빌드는 목표가 아니지만, 등가성 확인 없이 이관하면 그 시점부터 "어느 머신에서 빌드한
릴리즈인가" 가 디버깅 변수로 남는다. 매니페스트의 `built_by` 필드가 그 추적을 돕는다.

### 위험 D — MCP 역연결의 도달성·버전 축

- feature-0043 pull 브리지는 개인 머신 → QA 방향(아웃바운드)이라 VPN 만 붙으면 동작한다.
  설계상 좋은 선택이다(서버가 사용자 머신에 접속할 필요가 없다).
- feature-0041 OAuth 는 **브라우저 리다이렉트**가 필요하다 → VPN DNS + 사내 CA 가 전제이며,
  둘 다 확보됐으므로(§0.2 결정 7·8) 이 축은 해소 예정이다.
- **개인 머신 러너(`bridge_runner.py`)의 배포·업데이트 경로도 CI/CD 범위**다. 흔히 빠뜨리는
  축이다. 릴리즈 산출물에 러너를 포함하고 매니페스트의 `bridge_runner_min_version` 으로
  서버-러너 호환을 강제한다(불일치 시 무음 실패가 아니라 명시적 버전 오류).

---

## 5. 구현 순서

의존성 순서대로, 각 단계가 독립적으로 가치를 내도록 배열했다.

| 순서 | 작업 | 왜 이 순서인가 | 규모 |
|---|---|---|---|
| **1** | **폐쇄망 빌드 재현성** (단계 1) | 이게 안 되면 뒤 전부가 성립하지 않는다. 개발 머신에서 네트워크 차단 빌드로 즉시 검증 가능 | 중~대 |
| **2** | **`release-build.sh` + 매니페스트 + `deploy-web.sh --from-manifest`** | QA 머신 없이 개발 머신에서 리허설 가능(로컬에서 save→load→배포). 배포 스파인의 확장 지점이 이미 있어 침습 적음 | 중 |
| **3** | **SVN 저장소 + `release-agent.sh`** | 1·2 가 준비돼야 의미 있는 산출물이 올라간다 | 소~중 |
| **4** | **QA 머신 구축** (단계 4) | 인프라 협의(사내 CA·DNS·하드웨어)가 병렬 필요 — **승인 즉시 착수 권장** | 대 |
| **5** | **자동 스모크 + 수동 QA 절차** (단계 6) | 앞이 되면 붙이는 일 | 중 |
| **6** | **라이브 머신 구축 + 이전** (단계 7-1) | QA 에서 절차가 실증된 뒤. 데이터 이전 리허설 포함 | 대 |
| **7** | **승격 운영 정착** (단계 7-2) | 라이브가 옮겨진 뒤 | 소 |

> **1번과 4번은 병렬 가능**하다. 4번은 하드웨어 확보·사내 CA·DNS 협의 리드타임이 있으므로
> 먼저 요청을 넣고 그 사이 1·2를 진행하는 것이 전체 일정에 유리하다.

---

## 6. 권장 스펙 (실측 근거 기반)

### 6.1 현행 실측 (2026-08-27, 개발+라이브 겸용 호스트)

| 항목 | 실측값 |
|---|---|
| CPU | 20 vCPU |
| RAM | 39GB (사용 17GB · 버퍼/캐시 14GB · 가용 21GB) |
| GPU | **NVIDIA GTX 1660 SUPER 6GB** — WSL2 패스스루로 `embed-ollama`(bge-m3) 상주 |
| 디스크 | 1007GB 중 568GB 사용 |
| 런타임 데이터 | **90GB** — `mysql-data` 65G · `backups` 12G · `postgres-data` 4.6G · `ollama` 4.6G · `postgres-replica-data` 4.2G |
| compose `mem_limit` 명시 | 14개 서비스 합 **17.5GB** (2g×5 · 3g×1 · 1g×3 · 512m×2 · 256m×2) |
| 미명시 서비스 | 9개 (web-a/b · agent · insight-worker · ask-worker(+surge) · ops-scheduler · ext-tool-mcp 등) |

### 6.2 권장 스펙 (rev.3 — 로컬 LLM 폐지 반영)

**이 호스트는 개발·빌드·라이브를 겸하고 있으므로 현행 사용량이 곧 서빙 전용 요구량은
아니다.** 아래는 **임베딩 사내 MCP 이관 완료**(§9)를 전제한 서빙 전용 기준이다.

| 항목 | 최소 | **권장** | 근거 |
|---|---|---|---|
| CPU | 6 vCPU | **8~12 vCPU** | 상시 소비 주체는 PG(AGE 그래프 쿼리)·MySQL·워커. 워커는 LLM 대기가 대부분이라 CPU 가 낮고, **임베딩 추론이 빠지면서 가장 큰 CPU 소비원이 사라진다**. 그래프 sync·분석 배치가 겹치는 순간 부하를 위해 8 이상을 권한다 |
| RAM | 24GB | **32GB** | `mem_limit` 명시 17.5GB − `embed-ollama` 2GB = 15.5GB + 미명시 9개(~6~10GB) ≈ 22~26GB. 여기에 **MySQL 65GB 데이터의 페이지 캐시** 여유를 더한다. 24GB 로도 돌지만 캐시 여유가 없어 조회 응답이 라이브와 달라진다 |
| 디스크 | 250GB | **400GB NVMe** | 데이터 90GB − ollama 4.6GB ≈ 85GB + 로컬 이미지(last-good 세대) 30~60GB + 로컬 백업 50GB + 증가 여유. `mysql-data` 가 단조 증가 중이므로 여유를 크게 |
| **GPU** | **불요** | **불요** | 로컬 LLM 전면 폐지(§0.2 #12). 임베딩이 사내 MCP 로 나가면 GPU 를 쓰는 컨테이너가 없다 |
| 네트워크 | 1Gbps | 1Gbps | 이미지 tar(수 GB) 전송 · 데이터 이전 85GB · **사내 임베딩 MCP 왕복** |

> **주의**: 위 스펙은 §9 의 이관이 **완료된 상태**를 전제한다. 이관 전에 QA 를 세우면
> `embed-ollama` 가 GPU 없는 머신에서 CPU 추론으로 떨어져 타임아웃 cliff 위험이 생긴다.

### 6.3 임베딩 이관이 스펙에 미치는 영향

로컬 임베딩(`embed-ollama` · bge-m3)은 현행 구성에서 **유일하게 GPU 를 쓰는 컨테이너**다
(`OLLAMA_KEEP_ALIVE: -1` — 축출 없는 warm 상주가 그 컨테이너의 존재 이유로 명시돼 있다).
이것이 사내 MCP 로 나가면:

| 항목 | 변화 |
|---|---|
| GPU | **필요 → 불필요** (하드웨어 비용에서 가장 큰 단일 항목 제거) |
| 서비스 수 | 23 → **22** (`embed-ollama` 제거) |
| RAM | −2GB (`mem_limit`) |
| 디스크 | −4.6GB (모델 가중치) |
| CPU | 임베딩 추론 부하 제거 — 상시 최대 소비원이 사라짐 |
| **새 의존성** | 사내 임베딩 MCP 가 **KB 기능(검색·분석·샘플)의 SPOF** 가 된다. 그 서비스가 죽으면 KB 검색 품질이 떨어지고 백필이 멈춘다 — 가용성·타임아웃·fail 동작을 설계에 명시해야 한다 |

이관 전에 QA 를 세워야 하는 상황이라면 두 가지 중 하나다: ① QA 에도 GPU 를 넣어 현행 구성을
그대로 재현 ② GPU 없이 세우되 **CPU 기준으로 임베딩 타임아웃을 재조정**하고 성능 관련 QA
결과는 신뢰하지 않는다고 명시. 어느 쪽이든 이관 후에는 되돌려야 하므로, **이관을 먼저
끝내는 편이 총 공수가 적다**(§9.4).

### 6.4 빌드 머신 (차후 사내 빌드 서버)

| 항목 | 권장 | 근거 |
|---|---|---|
| CPU | 8 vCPU | 이미지 빌드 + `make test`(컨테이너 pytest) 병렬 |
| RAM | 16GB | 빌드 + 테스트 컨테이너 동시 기동 |
| 디스크 | 300GB | 이미지 레이어 캐시 + 릴리즈 tar 임시 + 베이스 이미지 tar 보관 |
| GPU | 불요 | 빌드·테스트에 임베딩 추론이 필요하지 않다 |
| 네트워크 | 인터넷 아웃바운드 **또는** 사내 미러 접근 | 베이스 이미지·의존성 획득 (§1) |

---

## 7. 이 설계가 현행에서 실제로 바꾸는 것

| 영역 | 현행 | 변경 후 | 침습도 |
|---|---|---|---|
| Dockerfile / compose 이미지 참조 | 공개 인터넷 직접 · 이동 태그(`caddy:2`·`ollama:latest`) | 로컬 tar 기반 + **패치 버전 핀** | **중~대 (실작업 대부분)** |
| requirements | 버전 범위 혼재 | 해시/버전 고정 (+미러 없으면 wheel 번들) | 중 |
| 배포 스파인 롤링·soak·롤백 | — | **변경 없음** | 없음 |
| `deploy-web.sh` 이미지 획득 | 로컬 build | `--from-manifest` (tar load / 미래 pull) — 기존 경로 보존 | 소~중 |
| CI | GitHub Actions only | + `release-build.sh` (빌드 머신 로컬 게이트) | 중 |
| 릴리즈 식별 | 커밋 SHA | + annotated 태그 + **매니페스트(sha256 + image_id)** | 소 |
| 산출물 전달 | (없음) | SVN `/releases/` + 파일서버(안 A) | 중 |
| 시크릿 | 호스트 수동 | SOPS 암호문 + preflight 키 대조 | 중 |
| 완료 판정 | 컨테이너 health | + OAuth discovery + MCP 왕복 | 소 |
| 라이브 위치 | 개발 머신 겸용 | **전용 호스트 분리** (1회 이전 절차) | 대 (1회) |

---

## 8. 남은 미결정 (1건)

§0.2 의 13개 축 중 12개가 확정됐다. 남은 것:

- **사내 PyPI/apt 미러 유무** — 인프라팀 확인 필요. 있으면 §1-b 안 A(index 치환), 없으면
  안 B(오프라인 wheel 번들). Dockerfile 을 `ARG` 로 양쪽 지원하게 만들어 두면 확인 전에도
  Phase 1 을 시작할 수 있고, 확인 후 값만 바꾸면 된다.

rev.2 에서 열려 있던 두 결정은 해소됐다 — SVN 용량 정책은 **안 A**(§3.4), GPU 는 **불요**
(로컬 LLM 전면 폐지, §0.2 #12). 다만 후자는 **순서 제약**을 남긴다(§9.4).

---

## 9. 로컬 LLM 폐지 현황과 임베딩 이관 (QA 세팅의 선행 조건)

사용자 방침: **"현재 프로젝트 내 더 이상 로컬 LLM 은 사용되지 않아야 한다."**
모든 LLM 처리는 외부에서 요청받고, 임베딩도 전용 계정을 웹서버가 **사내 MCP 로 직접
호출**하는 방식으로 연결할 예정이다. 아래는 2026-08-27 코드 실측 현황이다.

### 9.1 현황 — chat 축은 이미 끝났고, 임베딩 한 축이 남았다

| 축 | 상태 | 근거 |
|---|---|---|
| **대화·보조 chat LLM** (gemma / `edge-fallback`) | **이미 제거됨** | 2026-07-30 edge-free 결정으로 litellm `fallbacks` 의 edge 참조 전량 제거 + 앱 층 시각 기반 강등 기본 비활성. 나아가 feature-0043 이 서버측 chat 호출 자체를 fail-closed 로 차단 |
| **KB 임베딩** (`bge-m3` / ollama) | **여전히 활성** | `docker-compose.yml` 의 `embed-ollama` 서비스(GPU 패스스루 · `OLLAMA_KEEP_ALIVE: -1`) + `litellm_config.yaml` 의 `titan-embed` alias → `ollama/bge-m3` @ `http://embed-ollama:11434` |

즉 **로컬 LLM 은 임베딩 하나만 남았고, 그것이 유일한 GPU 소비자**다.
`shared/llm_gate.py` 도 이를 명시한다 — "비차단: KB 임베딩(로컬 bge-m3/ollama). 계정
자격증명과 무관하며 별도 클라이언트 경로를 쓴다."

### 9.2 이관이 쉬운 이유 — 앱은 alias 이름만 안다

임베딩 소비처는 3경로다:

| 경로 | 파일 | 용도 |
|---|---|---|
| 백필 워커 | `unit/feature-0002-agent-core/src/scripts/kb_embedding_worker.py` | `texts.embedding` NULL 채움 |
| 질의 임베딩 | `unit/feature-0002-agent-core/src/modules/kb_retrieval.py` | 검색어 벡터화 |
| 샘플 등록 | `unit/feature-0002-agent-core/src/modules/sample_queries.py` | NL↔SQL 샘플 |

세 경로 모두 `client.embeddings.create(model=AGENT_KB_EMBEDDING_MODEL, ...)` 형태로
**alias 이름(`titan-embed`)만 참조**하고, 실제 provider 는 `litellm_config.yaml` 이 정한다.
따라서 **새 엔드포인트가 OpenAI 호환 `/v1/embeddings` 를 노출하면 앱 코드 변경 없이
alias 정의 한 곳만 바꾸면 된다.**

### 9.3 ⚠ 이관의 두 가지 제약

**(a) 벡터 차원 1024 를 유지해야 한다.**
`AGENT_KB_EMBEDDING_DIM` 기본값이 1024 이고 `texts.embedding` 컬럼이 `vector(1024)` 다.
새 임베딩 모델의 차원이 다르면 **스키마 마이그레이션 + 전량 재임베딩**이 필요하다
(KB 규모를 감안하면 작은 작업이 아니다). 이관 대상 모델 선정 시 차원을 먼저 확인해야 한다.

**(b) 전송 계약이 `embeddings API` 인지 `MCP 도구 호출`인지 확인이 필요하다.**
- 사내 서비스가 **OpenAI 호환 `/v1/embeddings`** 를 노출한다면 → `litellm_config.yaml` 의
  `titan-embed` 정의만 교체(가장 간단, 앱 무변경).
- 순수 **MCP 도구 호출**이라면 → litellm 은 MCP 를 임베딩 provider 로 지원하지 않으므로
  **어댑터가 필요**하다. 어댑터를 두는 위치는 두 곳 중 하나다: ① litellm 앞단에 OpenAI 호환
  프록시를 세워 MCP 로 변환 ② 앱의 임베딩 호출부 3경로를 MCP 클라이언트로 교체.
  ①이 앱 무변경이라 유리하다.

### 9.4 QA 일정과의 순서 관계

이관은 **feature-0044 의 범위가 아니다**(별도 작업). 그러나 QA 스펙에 직접 영향을 주므로
순서를 정해야 한다.

| 순서 | 결과 |
|---|---|
| **이관 먼저 → QA 세팅 (권장)** | QA·라이브를 **GPU 없이** 산정·구매할 수 있다. 임베딩 타임아웃 재조정이 불필요하고, QA 가 곧 최종 구성이라 검증 결과가 그대로 유효하다 |
| QA 먼저 → 이관 나중 | QA 에 GPU 를 넣거나(비용) CPU 기준 타임아웃 재조정(공수)을 해야 하고, 이관 후 그것을 **되돌려야** 한다. 총 공수가 늘고, 그 사이 QA 의 성능 검증 결과는 최종 구성을 대표하지 못한다 |

**권장은 이관 먼저**다. 다만 이관이 지연되어 QA 를 먼저 세워야 한다면, 그 QA 는 "기능 검증
전용이며 성능·타임아웃 결과는 무효" 임을 명시하고 이관 완료 후 재검증한다.

### 9.5 이관 시 함께 정할 것

- **가용성 계약**: 사내 임베딩 MCP 가 KB 기능(검색·분석·샘플)의 SPOF 가 된다. 그 서비스가
  느려지거나 죽었을 때 ① 검색이 키워드 폴백으로 degrade 하는지 ② 백필이 멈추고 재개하는지
  ③ 타임아웃 값이 정상 지연 대비 충분히 위에 있는지(cliff 회피)를 정해야 한다.
- **전용 계정의 자격증명 관리**: 이 계정 자격증명은 **웹서버에 배치되어야 한다** — feature-0043
  이 "LLM 자격증명을 어느 대상에도 두지 않는다" 로 시크릿 표면을 줄였는데, 임베딩 계정은
  그 예외가 된다. 예외의 범위(임베딩 전용·최소 권한)를 명시하고 SOPS 파이프라인에 포함한다.
- **QA·라이브가 같은 임베딩 서비스를 공유하는가**: 공유하면 QA 트래픽이 라이브 임베딩
  서비스에 부하를 준다. 분리하면 두 벌 운영이 필요하다. 사내 서비스 운영 주체와 협의 사항.
