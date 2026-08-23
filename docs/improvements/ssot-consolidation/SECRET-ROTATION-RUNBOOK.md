---
doc_type: RUNBOOK
initiative: ssot-consolidation
phase: 3 (secret 노출 종료)
status: active
source_of_truth: false
created_at: 2026-06-24
---

# Secret 노출 종료 런북 (Phase 3 / META-0004-secret-cleanup)

> **노출 사실**: 아래 자격증명이 `.env.bak-task0211`·`.env.bak-task0279`·`.env.bak-task0299-1781684676`·`.env.secret.bak-task0228` 에 담겨
> 외부 GitHub `origin/main` + 다수 원격 브랜치 + 머지 PR(#231/#263)에 push 됨. `git rm` 으로 과거 blob 은
> 제거되지 않으므로 **rotation 만이 노출을 무력화**한다. (적대 리뷰 BLOCKER #12)
>
> **AI 가 자율 실행하지 않는 이유**: 라이브/at-rest 데이터 보호 자격증명 + KEK re-encryption 마이그레이션
> + 외부 계정(MSSQL/AWS/GitHub). 각 단계는 사용자(또는 feature 소유 cycle)가 eyes-on 으로 수행.

## 0. 노출 자격증명 분류

| 키 | 대상 | 교체 방식 | 주체 |
|---|---|---|---|
| `MYSQL_ROOT_PASSWORD`, `DB_PASSWORD` | 로컬 MySQL 컨테이너 | `ALTER USER` (기존 볼륨) | 사용자(로컬) |
| `AGENT_KB_PG_PASSWORD`/`_RO`/`SUPERPASSWORD` | 로컬 Postgres(KB) | `ALTER ROLE ... PASSWORD` | 사용자(로컬) |
| `WEB_BOOTSTRAP_ADMIN_PASSWORD` | 앱 admin 부트스트랩 | 앱 내 비밀번호 변경(기존 계정은 WebAccounts row) | 사용자 |
| **`AGENT_DATASOURCE_KEK_V1`** | **데이터소스 KEK** | **V2 도입 + 저장 cred re-wrap (값만 교체 금지!)** | **feature-0002/0003 소유 cycle** |
| `DS_WINSQL_PASSWORD` | 외부 MSSQL 서버 | 외부 DB 에서 교체 | 사용자(외부) |
| `LOCAL_LLM_API_KEY` | LLM 게이트웨이 | 게이트웨이에서 재발급 | 사용자 |
| (AWS Bedrock) | AWS IAM | IAM 키 rotation | 사용자(외부 AWS) |

> MinIO 키(`.env.minio`)는 위 .bak 4종에 미포함 — 별도로 `git ls-files | grep -i minio` 노출 여부 확인 권장.

## 1. 로컬 DB 자격증명 rotation (스택 가동 필요)

```bash
# 새 값 생성 (예시)
NEW_MYSQL_ROOT=$(openssl rand -base64 24); NEW_DB_PW=$(openssl rand -base64 24)
# 스택 기동
make up   # 또는 docker compose up -d
# MySQL: 기존 볼륨의 비밀번호는 env 가 아니라 ALTER 로만 교체됨
docker compose exec mysql mysql -uroot -p"<현재값>" -e \
  "ALTER USER 'root'@'%' IDENTIFIED BY '${NEW_MYSQL_ROOT}'; \
   ALTER USER '<DB_USER>'@'%' IDENTIFIED BY '${NEW_DB_PW}'; FLUSH PRIVILEGES;"
# Postgres(KB): 각 role 교체
docker compose exec <pg-service> psql -U "<SUPERUSER>" -c \
  "ALTER ROLE <AGENT_KB_PG_USER> PASSWORD '<new>'; ALTER ROLE <_RO user> PASSWORD '<new>';"
# .env.secret 의 해당 키를 새 값으로 갱신 후 재기동
docker compose up -d   # --no-build
```

## 2. KEK rotation (re-encryption 마이그레이션 — 단순 교체 금지)

- `AGENT_DATASOURCE_KEK_V1` 노출 → 저장 데이터소스 cred 가 이 KEK 로 envelope 암호화됨.
- **절차**: ① `AGENT_DATASOURCE_KEK_V2` 신규 발급, ② cred_crypto re-wrap (V1 복호화 → V2 재암호화) 마이그레이션
  실행(feature-0002/0003 코드 경유), ③ 검증 후 V1 폐기. **값만 바꾸면 전 데이터소스 접근 소실.**
- → 별도 feature 소유 cycle 로 진행 권장(데이터 마이그레이션 = §12 사람 승인 + 백업 선행).

## 3. 외부 자격증명
- `DS_WINSQL_PASSWORD`: 외부 MSSQL 에서 교체 → `.env.secret` 갱신.
- `LOCAL_LLM_API_KEY` / AWS Bedrock IAM: 각 서비스 콘솔에서 재발급 → `.env.secret`/AWS profile 갱신.

## 4. 저장소 위생 (rotation 완료 후 — AI 가 직접 수행 가능)
```bash
git rm --cached .env.bak-task0211 .env.bak-task0279 .env.bak-task0299-1781684676 .env.secret.bak-task0228
# .gitignore 에 글롭 추가:  .env*.bak*   *.bak-task*   *.secret.bak*
# 검증 (성공기준):
git ls-files | grep -iE '\.env\..*(bak|secret)|\.bak-task' | grep -v '\.example$'   # → 0건
```
> 이 변경은 root config(.gitignore/.env.bak) 라 verify-completion 이 operational mode 로 분류됨 →
> feature-0001-platform-runtime(런타임 config 소유) cycle 또는 META-0004 에 unit 스캐폴딩 부여로 게이트 통과.

## 5. GitHub 노출 후속 (외부 — 사용자)
- 저장소 Settings → **Secret scanning + Push Protection** 활성화.
- (선택, 고비용) history rewrite(`git filter-repo`) — 원격 브랜치 56개 + 머지 PR force-push 영향 runbook 동반 별도 작업.
  rotation 이 완료되면 과거 blob 의 값은 무력화되므로 history rewrite 는 우선순위 하향.

## 6. 완료 게이트 (Phase 3)
- [ ] rotation 폐기 증빙(모든 노출 키 교체 + 옛 값 무효)
- [ ] `git ls-files | grep -iE '\.env\..*(bak|secret)|\.bak-task'` → 0건 (+ .gitignore 글롭)
- [ ] `bash bin/ssot-lint.sh --check secret` → 0건
- [ ] GitHub Push Protection 활성
- [ ] verify-completion check #9 (REVIEW.md) + §12 승인 기록
