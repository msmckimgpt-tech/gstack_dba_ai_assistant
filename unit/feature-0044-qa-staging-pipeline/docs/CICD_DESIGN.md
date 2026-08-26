---
doc_type: DESIGN
feature_id: feature-0044-qa-staging-pipeline
status: draft
edit_policy: rewrite
source_of_truth: true
---

# QA 머신 CI/CD 설계 제안서

> 범위·계약·비범위의 정본은 [FUNCTION.md](./FUNCTION.md). 본 문서는 **전 과정의 절차·근거·
> 트레이드오프**를 담는다. 아직 구현 전 제안 단계이며, 사용자 검토 후 TASK 로 분해한다.

---

## 0. 요약 — 세 문장

1. **빌드는 사내 GitLab CI 한 곳에서만** 하고, QA·라이브는 같은 이미지 다이제스트를 당겨
   쓰기만 한다. QA 머신이 인터넷에 못 나가므로 대상 호스트 빌드는 성립하지 않고, 설령
   된다 해도 "빌드한 것"과 "검증한 것"이 달라진다.
2. **배포는 QA 가 당긴다(pull).** 개발망이 VPN 너머로 밀어넣지 않는다 — 방화벽 인바운드가
   불필요하고, 승격이 재빌드가 아니라 태그 이동이 된다.
3. **완료 판정은 컨테이너 health 가 아니라 사용자 진입 경로**다. 이 서비스는 MCP 로 쓰이므로,
   VPN 밖 사용자 머신에서 OAuth 완주 + 도구 왕복이 되어야 "올라갔다"고 말한다.

---

## 1. 현재 상태와, QA 를 그대로 얹으면 깨지는 지점

### 1.1 현행 (as-is)

| 축 | 현재 |
|---|---|
| 개발·라이브 위치 | 동일 WSL 호스트. `repo/` 에서 개발하고 같은 호스트의 compose 스택이 서빙 |
| 소스 정본 | GitHub `msmckimgpt-tech/gstack_dba_ai_assistant` |
| CI | GitHub Actions `ci.yml` — pytest(차단) · ruff(비차단) · migrate-lint · ROUTEMAP/codenav gate |
| CD | `sudo -E bin/deploy-web.sh` — `origin/main` HEAD 를 **로컬에서 docker build** → `mysql-ai-web:<sha>` / `mysql-ai-agent:<sha>` 로 pin → 무중단 롤링 + soak + last-good 자동 롤백 |
| 이미지 레지스트리 | **없음**(로컬 이미지 스토어) |
| 시크릿 | `.env` · `.env.mysql` · `.env.postgres` · `.env.secret` · `.env.llm` · `.env.minio` 등 — git 미포함, 호스트에만 존재 |
| 서비스 | compose 23개(데이터·워커·웹/엣지·LLM·MCP) |

배포 스파인 자체는 성숙하다 — flock 직렬화, 프로덕션 file-set 격리, TLS preflight,
migrate-lint hard gate, build-once 핀, one-at-a-time + pre-drain, post-cutover soak,
자동 롤백까지 이미 있다. **이 스파인을 버리는 설계는 하지 않는다.** 빌드 소스만 바꾼다.

### 1.2 QA 머신을 얹을 때 깨지는 지점 4가지

**(a) 대상 호스트 빌드가 성립하지 않는다.**
현행 CD 의 첫 단계는 대상 호스트에서의 `docker build` 다. QA 머신은 인터넷이 막혀 있어
`FROM python:3.11-slim` 도, `pip install` 도 나가지 못한다. 사내 미러를 붙여도 문제가 남는다 —
미러는 시점에 따라 다른 버전을 주므로 개발 머신에서 빌드한 이미지와 QA 에서 빌드한 이미지가
**다른 바이트**가 된다. "dev 에서는 되는데 QA 에서 안 된다"가 재현 불가능한 형태로 생긴다.

**(b) 정본이 둘이 된다.**
GitHub(개발) + 사내 GitLab(배포) 두 원격이 생기는 순간 "지금 QA 에 올라간 것이 무엇인가"의
단일 답이 사라진다. 특히 QA 에서 급히 고친 코드가 GitLab 에만 남는 상황이 최악이다.

**(c) QA 머신이 운영 등급 자산이 된다.**
라이브 복제본을 마스킹 없이 적재하기로 결정했으므로, QA 머신은 이름만 QA 이고 데이터는
운영이다. QA 는 성격상 계정이 헐거워지기 쉬운데(공용 테스트 계정, 단순 비밀번호), 그 순간
전체 시스템에서 가장 약한 고리가 된다.

**(d) "올라갔다"의 정의가 다르다.**
사용자가 웹 화면이 아니라 **자기 머신의 AI 런타임(MCP)** 으로 쓴다. 컨테이너가 healthy 여도
VPN DNS 가 `WEB_PUBLIC_HOST` 를 못 풀거나, TLS 를 클라이언트가 신뢰하지 않거나, OAuth
discovery 가 404 면 사용자는 진입조차 못 한다. 컴포넌트 health 로 완료 선언하면
"기동은 됐는데 못 쓴다"는 재보고가 발생한다.

---

## 2. 목표 구조 (to-be)

```
 개발망 (WSL)              사내 GitLab                   QA 머신(격리망)          라이브
──────────────           ─────────────────           ──────────────────      ────────────
 worktree cycle
      │
   PR → main   ──(GitHub Actions: PR 게이트)
      │
  릴리즈 태그 v2026.08.27-1
      │
      ├──push──▶ github (개발 정본)
      └──push──▶ gitlab (배포 정본, 미러)
                       │
                  [GitLab CI · 사내 러너]
                   1) test   (ci.yml 이식)
                   2) build  (사내 미러 기반)
                   3) scan   (취약점)
                   4) push   → GitLab Registry
                   5) manifest 발행 (digest 고정)
                       │
                    태그 채널: qa/v2026.08.27-1
                       │
                       ├───────(QA 가 폴링해 pull)──────▶ preflight
                       │                                     │
                       │                                  deploy-web.sh
                       │                                  --from-manifest
                       │                                     │
                       │                                  롤링 + soak
                       │                                     │
                       │◀──── 스모크 결과 되보고 ────────────┤
                       │                                     │
                       │                            수동 QA (VPN 밖 사용자 머신
                       │                            Claude Code → MCP 왕복)
                       │                                     │
                    태그 채널: promote/v2026.08.27-1 ◀───────┘
                       │
                       └───────(라이브가 폴링해 pull, 동일 digest)──────────▶ 롤링 + soak
```

### 2.1 다섯 가지 원칙

1. **한 번 빌드, 어디서나 배포** — 이미지 다이제스트가 dev→QA→live 를 관통하는 단일 신원.
   QA 에서 검증한 바이트가 라이브로 간다. 재빌드는 그 등가성을 깨뜨린다.
2. **QA 는 당기기만 한다(pull-based CD)** — 인바운드 방화벽 구멍 불필요, QA 장애가 개발망에
   전파되지 않음, 배포 자격증명이 개발망에 없어도 됨.
3. **승격은 재빌드가 아니라 태그 이동** — `qa/<tag>` → `promote/<tag>`. 사람이 승인하는 대상이
   "코드"가 아니라 "검증된 산출물"이 된다.
4. **QA 머신 = 운영 등급** — 데이터가 운영이므로 통제도 운영. 이름으로 등급을 정하지 않는다.
5. **완료 = 사용자 진입 경로 도달성** — health 가 아니라 MCP 왕복. (AGENTS.md §16.3)

### 2.2 왜 이 구조인가 — 검토했으나 택하지 않은 대안

| 대안 | 페르소나 | 채택하지 않은 이유 |
|---|---|---|
| **A. 소스만 미러하고 QA 에서 빌드** | 인프라 추가 없이 최소 변경을 원하는 팀 | §1.2(a). 폐쇄망에서 빌드 재현성이 성립하지 않고, "검증한 바이트 ≠ 배포한 바이트" 가 된다. 사내 미러를 붙여도 lock 없이는 시점 의존 |
| **B. 개발 머신이 VPN 붙어 QA 로 push (push-based)** | 파이프라인 도구 없이 스크립트로 끝내려는 팀 | 인바운드 경로·배포 자격증명이 개발망에 상주. 개발 머신이 QA 배포 권한을 들고 있는 구조는 개발 머신 침해가 곧 운영 데이터 접근이 된다. 사용자 답변(사내 GitLab 경유)과도 어긋남 |
| **C. Kubernetes + ArgoCD (GitOps)** | 다중 노드·다중 환경을 운영하는 플랫폼 팀 | 단일 호스트 23서비스 규모에 오케스트레이터 도입은 QA 도입과 독립된 큰 결정. 현행 compose 스파인의 무중단·롤백이 이미 실증됨. 다만 **pull + 선언적 매니페스트라는 GitOps 의 핵심 아이디어는 채택**한다 |
| **D. 라이브를 QA 로 겸용 (별도 QA 없음)** | 리소스가 빠듯한 팀 | 사용자가 이미 QA 머신 도입을 결정. MCP 표면이 외부 AI 런타임에 열리는 만큼 검증 없는 직행은 위험 |

---

## 3. 단계별 상세

### 단계 0 — 저장소 지형 정리 (선행 1회)

**정본 규칙**
- **GitHub = 개발 정본.** PR·리뷰·CI 게이트는 지금 그대로.
- **사내 GitLab = 배포 정본이자 미러.** 직접 커밋 금지, `main` 은 미러 전용 보호 브랜치.

**미러 방향**
사내 GitLab 이 인터넷에 나갈 수 있다면 GitLab 의 pull mirroring 이 가장 손이 덜 간다.
그러나 그 전제를 두지 않는 것이 안전하므로 **개발 머신이 미러 주체**인 방식을 기본안으로 한다:

```bash
git remote add gitlab <사내 GitLab SSH URL>
git push gitlab main --follow-tags
```

- 단방향만 허용한다. 양방향 동기화는 충돌 시 어느 쪽이 정본인지 사라지게 만든다.
- QA 머신의 deploy key 는 **read-only** 로 발급한다. "QA 에서 고쳐서 GitLab 에만 올라간 코드"를
  구조적으로 불가능하게 만드는 장치다.

**결정 필요**: 사내 GitLab 의 인터넷 아웃바운드 가능 여부 → 가능하면 pull mirror(자동),
불가하면 개발 머신 push(수동 1줄 또는 릴리즈 스크립트에 포함).

---

### 단계 1 — 이미지 공급망 폐쇄망 대응 (**작업량의 대부분**)

이 단계가 실제 손이 가장 많이 가는 곳이다. 지금 Dockerfile·compose 는 공개 인터넷을 전제한다.

**1-a. 베이스 이미지 파라미터화**

```dockerfile
ARG BASE_REGISTRY=registry.<사내도메인>/mirror
FROM ${BASE_REGISTRY}/python:3.11-slim
```

compose 의 외부 이미지도 동일하게 변수화한다 (현재 하드코딩 또는 부분 변수):

| 서비스 | 현행 참조 | 조치 |
|---|---|---|
| `caddy` | `caddy:2` | `${BASE_REGISTRY}/caddy:2.x.y` — **major 태그 금지, 패치까지 핀** |
| `postgres`(KB) | `${KB_PG_IMAGE:-pgvector/pgvector:pg16}` (라이브는 커스텀 `kb-pg-age:pg16`) | 커스텀 이미지를 CI 산출물로 승격해 registry 에 push |
| `mysql` · `minio` · `pgbouncer` · `embed-ollama` · `bedrock-gateway`(litellm) | 각 공개 이미지 | 사내 registry 미러 등록 + 패치 핀 |
| `mcp`(dbhub) | `bytebase/dbhub:${DBHUB_IMAGE_TAG}` | 동일 |

> `caddy:2` 처럼 움직이는 태그를 그대로 두면, QA 와 라이브가 서로 다른 시점에 pull 해
> **다른 caddy** 를 쓰게 된다. 이런 종류의 차이는 증상이 늦게·이상하게 나타난다.

**1-b. 패키지 소스 고정**

```dockerfile
ARG PIP_INDEX_URL=https://<사내 PyPI 미러>/simple
ARG PIP_TRUSTED_HOST=<사내 미러 호스트>
RUN pip install --no-cache-dir --require-hashes -r requirements.txt
```

- `requirements*.txt` 를 **해시 고정**한다(`pip-compile --generate-hashes` 등).
- apt 를 쓰는 레이어가 있으면 사내 apt 미러로 sources.list 치환.
- 해시 고정이 부담스러우면 최소한 **정확한 버전 핀**(`==`)까지는 필수. 범위 지정(`>=`)은
  폐쇄망에서 재현성을 잃는 가장 흔한 원인이다.

**1-c. 미러 등록 목록 정본화**
사내 registry 에 미러해야 할 외부 이미지 목록 + 버전을 한 파일로 관리한다. 새 서비스를
추가할 때 이 목록 갱신을 잊으면 QA 배포가 그 시점에 깨진다.

**검증 방법**: 개발 머신에서 네트워크를 끊고(또는 사내 미러만 허용하는 네트워크 네임스페이스에서)
전체 빌드가 성공하는지 확인한다. 이것을 통과하지 못하면 QA 에서도 실패한다.

---

### 단계 2 — 릴리즈 컷 (개발망)

`main` 이 배포 가능 상태가 되면 **annotated 태그**를 자른다.

```bash
git tag -a v2026.08.27-1 -m "release: <요약>

포함 PR: #1340 #1344 #1345 #1346
마이그레이션: alembic 0041 (expand only)
주의: ext-tool-mcp 재기동 필요"
git push origin  main --follow-tags
git push gitlab  main --follow-tags
```

- 태그 형식 `v<YYYY.MM.DD>-<seq>` — 날짜 기반이 사내 커뮤니케이션에 유리하다
  (semver 는 "무엇이 breaking 인가"에 합의가 필요한데, 내부 서비스에는 과한 비용).
- 태그 메시지가 곧 릴리즈 노트 초안이며 `docs/RELEASE_NOTES.md` 와 연결된다.
- **커밋 규칙(`CONTRIBUTING.md §5`)은 변경 없음.** 릴리즈 태그는 커밋 축과 직교하는 별개 축이다.

---

### 단계 3 — GitLab CI: 빌드·검증·발행 (사내망)

`.gitlab-ci.yml` 신설. 5 스테이지.

```yaml
stages: [test, build, scan, publish, manifest]
```

**3-1. `test`** — GitHub Actions `ci.yml` 의 게이트를 **이식**한다:
pytest · ruff · AgentMemory raw SQL 가드 · `migrate-lint --self-test --heads` ·
`gen-routemap.py --check` · `codenav-lint.sh`.

> 중복이 아니라 **이중화**다. GitHub 게이트는 "PR 이 main 에 들어가도 되는가", GitLab 게이트는
> "이 릴리즈를 사내 환경에서 빌드·배포해도 되는가"를 묻는다. 사내 러너에서 도는 것 자체가
> "사내 의존성 미러만으로 재현되는가"의 검증이다.

**3-2. `build`** — 단계 1 의 파라미터로 `mysql-ai-web` · `mysql-ai-agent` (+ 커스텀 KB PG 등)
빌드. `--build-arg GIT_COMMIT=$CI_COMMIT_SHA` 를 주입한다(현행 배포 완결 판정이 컨테이너의
`GIT_COMMIT` 을 다시 읽는 방식이라, 이 주입이 빠지면 판정이 무너진다).

**3-3. `scan`** — 이미지 취약점 스캔(사내 DB 미러 기준). 라이브 복제본 데이터를 다루는
호스트에 올라갈 이미지이므로 생략하지 않는다. 초기에는 비차단으로 두고 baseline 을 쌓은 뒤
Critical 만 차단으로 승격하는 순서를 권한다(ruff 를 비차단으로 도입한 것과 같은 방식).

**3-4. `publish`** — GitLab Container Registry 에 `:<sha>` 와 `:<tag>` 로 push.
push 결과의 **다이제스트를 캡처**한다(태그는 이동할 수 있고 다이제스트는 불변).

**3-5. `manifest`** — 릴리즈 매니페스트 발행. 이 파일이 배포의 계약서다.

```json
{
  "release": "v2026.08.27-1",
  "git_commit": "c23dc3318a73...",
  "built_at": "2026-08-27T02:10:00Z",
  "images": {
    "web":     "registry.<사내>/mysql-ai-web@sha256:...",
    "agent":   "registry.<사내>/mysql-ai-agent@sha256:...",
    "caddy":   "registry.<사내>/mirror/caddy@sha256:...",
    "kb-pg":   "registry.<사내>/kb-pg-age@sha256:..."
  },
  "alembic_head": "0041_xxx",
  "migration_kind": "expand-only",
  "env_keys_required": ["DB_PASSWORD", "AGENT_KB_PG_PASSWORD", "WEB_SECRET_KEY", "..."],
  "mcp_api_version": "2026-08-01",
  "bridge_runner_min_version": "0.3.0",
  "smoke_required": ["health", "oauth-discovery", "mcp-roundtrip", "conversation"]
}
```

- `env_keys_required` 는 **키 이름만**이다. 값은 절대 들어가지 않는다. QA·라이브 preflight 가
  이 목록으로 자기 `.env*` 를 대조해 누락을 배포 전에 잡는다.
- `bridge_runner_min_version` — 개인 머신 러너와 서버 API 의 호환 하한. 이 축을 빼면
  서버만 올라가고 사용자 머신 러너가 조용히 실패하는 상황이 생긴다.

---

### 단계 4 — QA 머신 부트스트랩 (1회, 오프라인)

**4-1. 기반 설치**
docker + compose. 사내 apt/yum 미러가 있으면 그대로, 없으면 개발 머신 경유 오프라인 릴레이
(사내 다른 QA 호스트에서 이미 쓰는 절차 — 다운로드 → sha256 대조 → scp → 전송본 재대조 →
의존성 사전 판정 → 설치).

**4-2. 자격증명 (모두 최소권한)**
- GitLab **read-only deploy key** (repo clone 용)
- Registry **read-only 토큰** (image pull 용)
- 두 자격증명 모두 쓰기 권한을 주지 않는다 — QA 머신이 침해돼도 소스·이미지를 오염시킬 수 없다.

**4-3. 시크릿 배치 — 가장 손이 많이 가는 지점**

`.env*` 6종은 git 에 없다. 세 가지 방식의 비교:

| 방식 | 장점 | 단점 | 권장 |
|---|---|---|---|
| **SOPS + age 암호화 커밋** | 저장소가 시크릿의 정본이 됨. 변경 이력·리뷰 가능. 배포 자동화와 정합 | 도구 도입 + 키 관리 학습 곡선 | **기본안** |
| 사내 Vault | 중앙 회전·감사 | 이 규모엔 과함. Vault 자체가 새 SPOF | 사내에 이미 있으면 채택 |
| 수동 scp 1회 | 즉시 가능 | 회전·이력·재현성 없음. "그 머신에만 있는 값"이 생김 | 초기 임시만 |

기본안 절차:
```bash
# 개발 머신 (1회): QA용 키 생성 → 공개키로 암호화해 저장소에 커밋
age-keygen -o qa.agekey                     # 개인키는 QA 머신에만 배치
sops --encrypt --age <pubkey> .env.secret > env/qa/.env.secret.enc
git add env/qa/.env.secret.enc              # 암호문만 커밋

# QA 머신: 복호화 (배포 러너가 수행)
SOPS_AGE_KEY_FILE=/etc/qa.agekey sops --decrypt env/qa/.env.secret.enc > .env.secret
chmod 600 .env.secret
```

**LLM 자격증명은 QA 에 두지 않는다.** feature-0043 이 서버측 LLM 호출을 fail-closed 로
차단하므로(`AGENT_SERVER_LLM_ENABLED=0` 이 코드 기본값) QA 머신에 Claude 계정 자격증명이
필요 없다. 시크릿 표면이 실질적으로 줄어드는 게 이번 구조의 부수 이득이다.
(KB 임베딩은 로컬 `bge-m3`/ollama 라 계정 무관 — 그대로 동작.)

**4-4. 데이터 적재 (라이브 복제본, 마스킹 없음)**

- 원천: `bin/backup.sh` 산출물 — PG `agent_kb` + MySQL `agent_memory` 논리 백업.
- 적재 검증: `bin/restore-rehearsal.sh` 가 이미 "최신 백업을 throwaway DB 로 복원 검증"하는
  도구로 존재한다. QA 적재를 이 도구의 실사용 사례로 삼는다.
- **반출 경로를 통제한다.** 라이브 → 개발 머신 → QA 로 옮기면 개발 머신도 운영 등급이 된다.
  가능하면 라이브 → QA 직접 전송(또는 통제된 파일서버 1홉)으로 구성하고, 경유지에 남은
  사본은 삭제 절차까지 문서화한다.
- 갱신 주기를 정한다(예: 주 1회 또는 릴리즈 전). 오래된 복제본은 마이그레이션 정합을
  어긋나게 만들고, 너무 잦으면 반출이 상시화된다.

**4-5. TLS — MCP 클라이언트 때문에 특히 중요**

- **사내 CA 서명 인증서를 우선한다.** 브라우저는 예외 승인 버튼이 있지만 MCP 클라이언트
  (Claude Code 등)는 없다 — self-signed 면 연결 자체가 실패한다.
- 사내 CA 발급이 불가하면 기존 `/trust/` rootCA 배포 경로를 쓰되, 사용자 머신에 CA 를
  설치하는 절차가 온보딩 문서에 반드시 들어가야 한다.
- SAN 에 `WEB_PUBLIC_HOST` 와 QA 머신 IP 를 모두 넣는다. 배포 스크립트가 이미 TLS preflight
  (SAN/CA/만료)를 하므로 게이트는 재사용된다.
- VPN DNS 가 `WEB_PUBLIC_HOST` 를 QA IP 로 해석해야 한다 — **인프라 담당과 사전 합의 필요**.

---

### 단계 5 — QA 배포 (pull-based CD)

QA 머신에 상주하는 systemd timer(또는 cron)가 수행한다.

```
[10분마다]
 1. git fetch --tags (read-only)          # 사내 GitLab
 2. qa/* 채널의 최신 태그 확인 → 새 릴리즈 없으면 종료(무변경 로그도 남기지 않음)
 3. 매니페스트 로드 + 서명/체크섬 검증
 4. docker pull <digest> ...              # 태그가 아니라 다이제스트로
 5. preflight
      - env_keys_required vs 실제 .env*  → 누락 시 중단
      - alembic head 정합                 → 불일치 시 expand 적용 가능 여부 판정
      - TLS SAN/만료                      → 기존 게이트 재사용
      - 디스크 여유 / 이전 last-good 존재
 6. bin/deploy-web.sh --from-manifest <path>
      → migrate(expand) → web 롤링(one-at-a-time + pre-drain + /readyz)
      → soak → 워커 롤아웃 → gateway reconcile
 7. 자동 스모크(단계 6)
 8. 결과를 GitLab 에 되보고 (commit status API 또는 릴리즈 코멘트)
```

**`deploy-web.sh` 확장 지점**

현행 스크립트는 이미 `artifacts/deploy/docker-compose.deploy-pin.yml` 로 이미지를 고정하는
구조다. 즉 **"이미지를 고정해 배포한다"는 뼈대가 이미 있고, 그 이미지를 어디서 얻는가만
다르다.** 따라서 확장은 침습적이지 않다:

| 현행 | registry 모드 |
|---|---|
| `git checkout origin/main` | 매니페스트의 `git_commit` 검증만 (checkout 불필요) |
| `docker compose build <svc>` | `docker pull <digest>` |
| pin overlay 에 `image: repo:<sha>` | pin overlay 에 `image: registry/...@sha256:...` |
| last-good = 이전 로컬 태그 | last-good = 이전 다이제스트 |
| 롤링·soak·롤백 | **그대로** |

플래그 형태: `--from-manifest <path>` (또는 `DEPLOY_IMAGE_SOURCE=registry`).
기존 로컬 빌드 경로는 제거하지 않고 남긴다 — 개발 머신에서의 빠른 반복은 여전히 유효하다.

> **롤백이 더 안전해진다**: registry 모드에서는 이전 다이제스트 이미지가 로컬에 남아 있어
> 재빌드 없이 즉시 복귀한다. 현행 로컬 빌드 모드의 "첫 배포 이전에는 last-good 이 없다"
> 문제도 매니페스트 이력으로 자연 해소된다.

---

### 단계 6 — QA 검증 게이트 (승격 조건)

**6-A. 자동 스모크** (배포 직후, QA 머신 내부에서 실행)

| # | 검사 | 통과 기준 | 이유 |
|---|---|---|---|
| 1 | 컨테이너 health | 전 서비스 healthy + `GIT_COMMIT` 일치 | 부분 완료를 완료로 보고하지 않기 위해(현행 스파인 정책) |
| 2 | 엣지 도달성 | Caddy 경유 `/livez`·`/readyz` 200 | 앱 health 만 보면 엣지 격리 상태를 놓친다 |
| 3 | **OAuth discovery** | `/.well-known/oauth-protected-resource` · `/.well-known/oauth-authorization-server` 200 | **MCP 클라이언트의 인증 접근성은 표준 discovery 유무가 좌우한다.** 여기가 404 면 서비스는 멀쩡한데 사용자는 연결조차 못 한다 |
| 4 | MCP 프로토콜 응답 | `/api/ai/mcp` 가 정상 전송 응답(GET 은 406 이 정상) | 컨테이너 healthcheck 와 동일 판정식 재사용 |
| 5 | 대화 경로 | 기존 deploy-conversation-smoke 재사용 | 최근 배포 게이트에 추가된 자산 |
| 6 | 브리지 왕복 | `list_open_requests` 정상 응답 | feature-0043 pull 브리지가 살아있는지 |

**6-B. 수동 QA** (VPN 밖 사용자 머신 — 자동화로 대체 불가한 축)

1. 사용자 머신 Claude Code 에 QA MCP 엔드포인트 등록 → 연결
2. 브라우저 OAuth 로그인·동의 완주 (VPN DNS + 사내 CA 신뢰가 여기서 실증된다)
3. 도구 1회 호출 → 결과 수신
4. 웹 화면에서 해당 task 기록이 렌더되는지 확인
5. 웹/UI 변경이 포함된 릴리즈면 PB-0008 실 브라우저 시각검증

> 이 5개가 곧 "사용자가 실제로 쓸 수 있는가"의 정의다. §1.2(d) 의 재보고를 막는 유일한 장치.

**6-C. 승격**

```bash
git tag -a promote/v2026.08.27-1 -m "QA 통과: 스모크 6/6, 수동 QA <검증자>/<일시>"
git push gitlab promote/v2026.08.27-1
```

재빌드 없음. 승격의 실체는 **"이 다이제스트를 라이브에 허용한다"는 서명**이다.

---

### 단계 7 — 라이브 승격 및 되돌리기

- 라이브 러너는 `promote/*` 채널만 본다. 같은 매니페스트, 같은 다이제스트를 pull 한다.
- 라이브 러너는 매니페스트에 **QA 스모크 결과가 기록돼 있는지 확인**하고, 없으면 거부한다
  (QA 를 우회한 승격을 구조적으로 막는다).
- 배포 절차는 QA 와 동일(단계 5). 같은 스크립트, 같은 게이트.
- 되돌리기: `deploy-web.sh --rollback` — 이전 다이제스트로 즉시 복귀.
- 마이그레이션은 expand/contract 규율(`migrate-lint` hard gate)이 이미 강제되므로
  **코드 롤백에 스키마 롤백이 따라붙지 않는다.** 이 규율을 QA·라이브 양쪽에서 유지한다.

---

## 4. 짚어야 할 위험 3가지

### 위험 A — 마스킹 없는 라이브 복제본의 비용

결정 자체를 뒤집자는 것이 아니라, 그 선택이 **자동으로 따라오게 만드는 의무**를 명시한다.

- QA 머신의 접근통제·감사로그(`WebAuditEvents`)·백업·폐기 절차가 라이브와 동일해야 한다.
- QA 계정을 공용/단순 비밀번호로 만들지 않는다 — 실제 사번 기반 개별 계정, `admin.console.access`
  최소 부여. QA 는 이 규율이 느슨해지기 가장 쉬운 곳이고, 데이터는 운영이다.
- 데이터 반출 표면(첨부 다운로드·CSV 반출·대화 내보내기)이 QA 에서도 열려 있음을 인지하고
  감사 대상에 포함한다.
- **점진적 개선안**: 지금 전면 마스킹은 범위 밖이지만, 복원 후처리로 **PII 컬럼만 치환**하는
  스크립트는 비용 대비 효과가 크다. 후속 cycle 후보로 남긴다.

### 위험 B — 이중 원격의 정본 혼선

- GitLab `main` 은 미러이므로 force-push 로 덮어써질 수 있다. GitLab 에 직접 커밋하면 조용히 사라진다.
- 방어: QA deploy key **read-only**, GitLab `main`·태그 보호 설정, "GitLab 에 직접 커밋 금지"를
  `CONTRIBUTING.md` 에 명문화.
- 릴리즈 태그는 **GitHub 과 GitLab 양쪽에 같은 이름으로** 존재해야 추적이 끊기지 않는다.

### 위험 C — MCP 역연결의 도달성·버전 축

- feature-0043 pull 브리지는 개인 머신 → QA 방향(아웃바운드)이라 VPN 만 붙으면 동작한다.
  설계상 좋은 선택이다(서버가 사용자 머신에 접속할 필요가 없다).
- 그러나 feature-0041 OAuth 는 **브라우저 리다이렉트**가 필요하다 → 사용자 머신의 브라우저가
  `WEB_PUBLIC_HOST` 를 해석·도달·신뢰해야 한다. VPN DNS + 사내 CA 가 전제 조건이며,
  이것이 안 되면 배포는 성공인데 아무도 못 쓴다.
- **개인 머신 러너(`bridge_runner.py`)의 배포·업데이트 경로도 CI/CD 범위**다. 흔히 빠뜨리는
  축이다. GitLab 릴리즈 아티팩트로 배포하고, 매니페스트의 `bridge_runner_min_version` 으로
  서버-러너 호환을 강제한다(불일치 시 무음 실패가 아니라 명시적 버전 오류).

---

## 5. 구현 순서 제안 (무엇부터 하는가)

의존성 순서대로, 각 단계가 독립적으로 가치를 내도록 배열했다.

| 순서 | 작업 | 왜 이 순서인가 | 규모 |
|---|---|---|---|
| **1** | **폐쇄망 빌드 재현성** (단계 1) — 베이스 이미지·pip 미러화 + 버전 핀 | 이게 안 되면 뒤 전부가 성립하지 않는다. 개발 머신에서 네트워크 차단 빌드로 즉시 검증 가능 | 중~대 |
| **2** | **릴리즈 매니페스트 + `deploy-web.sh --from-manifest`** | QA 머신 없이도 개발 머신에서 검증 가능(로컬 registry 로 리허설). 배포 스파인의 확장 지점이 이미 있어 침습 적음 | 중 |
| **3** | **사내 GitLab 미러 + CI 파이프라인** | 1·2 가 준비돼야 CI 가 의미 있는 산출물을 만든다 | 중 |
| **4** | **QA 머신 부트스트랩** (단계 4) — 설치·시크릿·데이터·TLS | 인프라 협의(VPN DNS·사내 CA·데이터 반출 승인)가 병렬로 필요하므로 **지금 착수해도 좋은 유일한 선행 항목** | 대 |
| **5** | **pull 러너 + 자동 스모크** (단계 5·6-A) | 앞이 다 되면 붙이는 일 | 중 |
| **6** | **수동 QA 절차 + 온보딩 문서** (단계 6-B) | 사용자 머신 설정(CA·VPN·러너)이 포함되므로 문서가 산출물 | 소~중 |
| **7** | **라이브 승격 경로 전환** (단계 7) | QA 가 안정적으로 돈 뒤 | 소 |

> **1번과 4번은 병렬 가능하다.** 4번은 인프라 담당과의 협의 리드타임이 있으므로 먼저 요청을
> 넣어두고, 그 사이 1·2를 진행하는 것이 전체 일정에 유리하다.

---

## 6. 미결정 사항 (사용자·인프라 확인 필요)

1. **사내 GitLab 의 인터넷 아웃바운드** — 가능하면 GitHub→GitLab pull mirror 자동화, 불가하면
   개발 머신 push 방식.
2. **사내 컨테이너 레지스트리** — GitLab Container Registry 를 쓸 수 있는지, 별도 Harbor 등이
   있는지. 없으면 registry 자체를 세우는 작업이 선행된다.
3. **사내 PyPI/apt 미러 유무** — 없으면 오프라인 wheel 번들을 이미지 빌드 컨텍스트에 담는
   방식으로 대체(가능하나 유지보수 비용 증가).
4. **VPN DNS 로 `WEB_PUBLIC_HOST` 해석 가능 여부** + **사내 CA 발급 가능 여부** — MCP 접근의
   전제 조건.
5. **라이브 데이터 반출 승인 주체·경로** — 마스킹 없는 복제본 이동은 승인이 필요한 행위일 수 있다.
6. **QA 머신 스펙** — 현행 23서비스 스택(PG+pgvector+AGE, MySQL, MinIO, ollama 임베딩)을
   감당할 CPU/RAM/디스크. 특히 `bge-m3` 임베딩은 GPU 없으면 느리다(기능 검증은 가능).
7. **라이브의 최종 위치** — 현재 개발 머신과 동일 호스트다. QA 도입을 계기로 라이브도 별도
   호스트로 분리할지는 별개 결정이며, 본 설계는 두 경우 모두 수용한다.

---

## 7. 이 설계가 현행에서 실제로 바꾸는 것 (요약)

| 영역 | 현행 | 변경 후 | 침습도 |
|---|---|---|---|
| Dockerfile / compose 이미지 참조 | 공개 인터넷 직접 | 사내 미러 변수 + 버전 핀 | **중~대 (실작업 대부분)** |
| requirements | 버전 범위 혼재 | 해시/버전 고정 | 중 |
| 배포 스파인 롤링·soak·롤백 | — | **변경 없음** | 없음 |
| `deploy-web.sh` 이미지 획득 | 로컬 build | `--from-manifest` 로 pull (기존 경로 보존) | 소~중 |
| CI | GitHub Actions only | + GitLab CI(릴리즈 축) | 중 |
| 릴리즈 식별 | 커밋 SHA | + annotated 태그 + 매니페스트 | 소 |
| 시크릿 | 호스트 수동 | SOPS 암호화 커밋 + preflight 대조 | 중 |
| 완료 판정 | 컨테이너 health | + OAuth discovery + MCP 왕복 | 소 |
