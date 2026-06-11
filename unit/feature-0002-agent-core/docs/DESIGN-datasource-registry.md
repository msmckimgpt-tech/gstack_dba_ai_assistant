# DESIGN — DB 기반 datasource 레지스트리 (자격증명 암호화 저장) + 제품별 MSSQL 참조 DB

TASK-0205 (설계). 멀티 datasource 가 라이브로 쓰이면서, 데이터소스 정의를 `.env` 전용에서
**관리 콘솔에서 CRUD 가능한 DB 저장**으로 전환한다. 사용자 결정(2026-06-11):
1. **데이터소스 전체 CRUD (접속·비밀 포함) — `.env` 정보를 DB 저장.**
2. **MSSQL: 서버 1개 데이터소스 → 제품별 참조 DB 선택** (같은 서버의 여러 DB 를 데이터소스 중복 등록 없이).
3. "제품 카테고리"는 기존 제품 화면 지칭(카테고리 신규 아님).

> **본 문서는 설계만**. 자격증명 DB 저장은 보안-critical 이라 구현 전 outside-voice 재게이트 필수
> ([[feedback_outside_voice_for_rbac]]). 원 멀티-datasource 와 동일한 design-first 패턴.

## 1. 현재 상태 (조사 결과)

- 데이터소스 = `.env` `DS_<KEY>_*` (engine/host/port/user/**password**/default_db) → `config._parse_datasources()`
  → 모듈 로드 시 1회 `cfg.DATASOURCES` 전역 dict. password 는 DB·payload·로그 비저장(현 보안 설계).
- 제품↔데이터소스 = `WebProducts.DatasourceKey`(키만 저장). 허용 스키마 = `WebProductDatabases`.
- MSSQL 은 데이터소스당 `default_db` 1개 고정(`_connect_mssql` 이 연결 DB 고정 + cross-DB 차단, P6).
- 소비처 6 chokepoint: `agent_core._resolve_product_datasource`(DATASOURCES.get) · `db.connect/_connect_mssql/
  connect_with_retry` · `insight.run_insight_cycle` · app.py admin 3 endpoint.
- 암호화: `cryptography>=42.0.0` 보유. 참조 구현(PBKDF2-HMAC-SHA256+AESGCM, `v1:salt:iv:ct`)은
  task0034(폐기된 API vault)에 잔존 — **재사용 가능**. **앱 전역 암호화 키는 부재 → 신규 도입 필요.**
- `WebProducts` 는 MySQL `agent_memory`. 멱등 ALTER/CREATE 패턴(`try/except pass` + `_ensure_*`).

## 2. 아키텍처

### 2.1 암호화 (`modules/secrets.py` 신규)
- **AESGCM, 키는 `.env` 의 `AGENT_DATASOURCE_ENC_KEY`** (32바이트 base64, 운영자가 1회 생성). 이 **마스터 키만
  `.env` 에 남는다** — 데이터소스 자격증명 자체는 DB(암호화). 키는 DB 에 절대 저장 안 함.
- 포맷 `v{n}:<b64_iv>:<b64_ct>` (키가 이미 랜덤 32B 라 per-record salt 불필요; AESGCM nonce=12B 매번 신규).
  AAD 로 `DatasourceKey` 바인딩(암호문 재사용·키 교체 공격 방지).
- `EncryptionVersion` 컬럼으로 키 로테이션 대비. 키 부재 시 **DB 자격증명 복호 불가 → fail-closed**(그 datasource
  연결 거부, `.env` datasource 는 영향 없음).
- `encrypt_secret(plain, aad)` / `decrypt_secret(token, aad)` + `enc_available()` (키 설정 여부).

### 2.2 DB 테이블 `WebDatasources` (MySQL agent_memory)
```sql
CREATE TABLE IF NOT EXISTS WebDatasources (
  Id BIGINT AUTO_INCREMENT PRIMARY KEY,
  DatasourceKey VARCHAR(64) NOT NULL UNIQUE,    -- 소문자, `ds:` 구분자 금지(fact-key 규약)
  Engine VARCHAR(16) NOT NULL DEFAULT 'mysql',  -- mysql|mssql
  Host VARCHAR(255) NOT NULL,                   -- 평문(이미 admin UI 노출 대상 — datasource_public)
  Port INT NOT NULL,
  DbUser VARCHAR(128) NOT NULL,                 -- 평문(노출 대상). RO 유저 권고 유지
  PasswordEnc LONGBLOB NULL,                    -- **암호화** (유일 비밀)
  DefaultDb VARCHAR(128) NULL,                  -- 데이터소스 기본 참조 DB(제품이 override 가능, §2.4)
  EncryptionVersion INT NOT NULL DEFAULT 1,
  IsActive TINYINT(1) NOT NULL DEFAULT 1,
  CreatedAt DATETIME DEFAULT CURRENT_TIMESTAMP,
  UpdatedAt DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UpdatedByAccountId BIGINT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```
- **password 만 암호화**(host/port/user 는 현 `datasource_public` 도 노출 — 이 앱의 비밀 경계는 password).
- `_ensure_web_datasources_schema()` 멱등 CREATE, slow+fast 경로 호출(기존 패턴).

### 2.3 레지스트리 — `.env` + DB 병합, 멀티프로세스 reload
- **문제**: `DATASOURCES` 는 모듈 로드 1회 파싱. web 이 CRUD 해도 ask-worker/insight-worker(별 프로세스)가
  못 본다. → **DB read-through(짧은 캐시) + 소비처를 함수 경유로**.
- 신규 `cfg.get_datasource(key) -> dict|None` / `cfg.all_datasources() -> dict`:
  1. DB(`WebDatasources`, IsActive=1) 우선, 키 충돌 시 DB 우선(`.env` 는 레거시 폴백).
  2. password 복호화는 **resolve 시점**(메모리에만, 캐시에 평문 보관 X — 또는 TTL 짧게).
  3. 캐시 TTL(예: 30s) + admin write 시 `bump_version`(KV `datasources_rev`)로 즉시 무효화 → 워커가 다음
     resolve 에 reload. (멀티프로세스 정합: 버전 KV 폴링 or per-resolve 조회.)
- **소비처 전환**: `cfg.DATASOURCES.get(key)` → `cfg.get_datasource(key)` (6 chokepoint). `agent_core._resolve_
  product_datasource` 는 이미 mem_conn 보유 → DB 직접 조회 자연스러움.
- **flag 유지**: `AGENT_MULTI_DATASOURCE_ENABLED` OFF 면 전부 무시(기존 동작 0 변경).

### 2.4 제품별 MSSQL 참조 DB
- `WebProducts` 에 `DatasourceDatabase VARCHAR(128) NULL` 추가(멱등 ALTER).
- `_resolve_product_datasource(product)` 가 datasource dict 반환 시, product 의 `DatasourceDatabase` 가
  있으면 **그 값으로 `default_db` override**(MSSQL: 연결 DB; MySQL: 의미 없음 — 무시/표시만).
- cross-DB 차단(P6)은 유지: 활성 default_db 외 catalog 참조는 여전히 거부 → product 가 고른 DB 안에서만.
- **데이터소스 1개(서버+자격) → 제품 A=dk_data_release, 제품 B=GameLog_151**: 자격 중복 등록 0.

### 2.5 관리 API (feature-0003 app.py)
| endpoint | method | 권한 | 기능 |
|---|---|---|---|
| `/api/admin/datasources` | GET | console.access | 목록(password 마스킹, `has_password` bool 만) |
| `/api/admin/datasources` | POST | console.manage | 생성(key/engine/host/port/user/password/default_db) |
| `/api/admin/datasources/{key}` | PATCH | console.manage | 수정(password 미입력 시 미변경) |
| `/api/admin/datasources/{key}` | DELETE | console.manage | 삭제(바인딩된 product 있으면 거부 or force) |
| `/api/admin/datasources/{key}/test` | POST | console.access | 연결테스트(기존) |
| `/api/admin/datasources/{key}/databases` | GET | console.manage | 서버의 DB 목록(MSSQL `sys.databases`/MySQL `SHOW DATABASES`) — 제품별 DB 선택용 |
| `/api/admin/products/{id}/datasource` | PATCH | console.manage | 바인딩(기존) + `datasource_database` 동시 설정 |
- 모든 쓰기 audit(`admin.datasource.*`). password 는 응답에 **절대 미포함**.

### 2.6 관리 UI (admin.js)
- 신규 **데이터소스 관리 패널**(목록/생성/수정/삭제/연결테스트, engine 선택, password 입력=write-only).
- 제품 상세: datasource select + (MSSQL 일 때) **참조 DB select**(`/databases` 로 채움).
- 엔진 배지(mysql/mssql) 표시(P7 잔여 흡수).

## 3. 보안 (최고 위험 — outside-voice 필수)

- **자격증명 암호화**: AESGCM + `.env` 마스터 키. 마스터 키 유출 시 전 datasource 비번 노출 → 키는 `.env`(파일권한)
  + docker secret 권고. 키 부재/오류 → fail-closed(복호 불가 datasource 연결 거부).
- **password 비노출**: API 응답·로그·`datasource_public` 모두 password 제외. UI 는 write-only(재입력만, 조회 불가).
- **SSRF**: console.manage admin 이 임의 host:port 로 datasource 지정 가능 → 에이전트가 그 곳에 접속(내부망 스캔
  표면). admin 은 신뢰 주체(console.manage)나, **명시 위험으로 문서화** + (옵션) host allowlist/사설망 차단 정책.
- **RO 자격 원칙 유지**: DB user 는 여전히 최소권한 RO 권고(강제 못 함 — N-2 와 동일). P6 의 sql_guard/allowlist/
  cross-DB 가 2차 방어. DB 저장이 이 경계를 약화하지 않음(키만 → 좌표+암호비번, 게이트 동일).
- **RBAC**: datasource CRUD = `console.manage`(자격증명 쓰기 = 고권한). 조회는 console.access(password 제외).
- **감사**: 생성/수정/삭제/바인딩 전부 audit + UpdatedByAccountId.
- **마이그레이션**: 기존 `.env` datasource(winsql 등)는 그대로 동작(레거시 폴백). 운영자가 admin "DB로 가져오기"로
  이전 가능. `.env` 제거는 선택.

## 4. 단계 (phasing)
- **A (foundation, 보안-critical)**: `modules/secrets.py`(AESGCM) + `WebDatasources` 테이블 + `cfg.get_datasource/
  all_datasources`(DB+env 병합·캐시·reload) + 소비처 6 전환 + flag/legacy 보존. **outside-voice 보안 재게이트.**
- **B (admin CRUD)**: datasource CRUD API + admin UI 패널 + audit.
- **C (제품별 MSSQL DB)**: `WebProducts.DatasourceDatabase` + `/databases` endpoint + 연결 override + 제품 UI DB select.
- **D (마이그레이션·정리)**: `.env`→DB 가져오기 admin 액션 + 엔진 배지 + 문서.
- 각 단계 flag 뒤 + make test + 라이브 검증. A 가 정합의 핵심(나머지는 A 위에 UI/CRUD).

## 5. Open questions (리뷰에서 확정)
- Q1 캐시/reload 전략: per-resolve DB 조회(단순·정합) vs TTL 캐시+버전 KV(부하↓·복잡). 워커 부하 vs 정합.
- Q2 키 부재 시 신규 CRUD 차단(fail-closed) + `.env` datasource 만 동작 — 합의?
- Q3 `.env` 와 DB 동일 키 충돌 시 DB 우선 — 합의? (또는 충돌 거부)
- Q4 SSRF: host allowlist 강제 vs 문서화만(admin 신뢰).
- Q5 password 외 host/user 도 암호화? (현안: password 만 — datasource_public 노출 경계와 일치.)

## 6. Outside-voice 적대적 설계 검토 (REV-20260611-0205) — REJECT → 합격선 박제

자격증명 DB 저장은 보안 모델 변경이라 outside-voice 필수([[feedback_outside_voice_for_rbac]]). 1차 **REJECT**
(BLOCKER 3 + MAJOR 5). 구현은 아래 합격선을 **반드시** 충족해야 재게이트 통과. (방향·phasing·flag/legacy 보존은 양호 판정.)

### BLOCKER (구현 전 설계 확정 필수)
- **B1 — §2.4 override 가 P6 cross-DB 가드를 우회**: cross-DB 가드(`tools.py:121`)는 정적 `DATASOURCES[key].default_db`
  를 허용 catalog 로 읽는데, §2.4 는 연결 DB 를 product `DatasourceDatabase` 로 override → **가드 기준(정적)과 연결
  컨텍스트(override)가 분리** → product-scoped DB 격리 붕괴(어느 방향이든). **합격선**: `set_active_datasource` 에
  **effective default_db**(override 반영)를 함께 주입하고 `tools.py` 가드가 정적 dict 대신 그 값을 읽도록 단일화.
  + product 가 고른 DB 가 **RO 로그인 GRANT 범위 내**인지 fail-closed 검증(아니면 §2.4 는 RBAC 우회 경로).
- **B2 — audit 에 평문 password 누출**: `_AUDIT_MASKED_FIELDS_PASSWORD`(app.py:13359)에 `password` **부재** →
  create/patch 페이로드의 평문이 `WebAuditEvents.ChangeJson` 영구기록 + audit.export 유출(DB 암호화 목적 무효).
  **합격선**: datasource audit 는 **화이트리스트 필드만 기록**(password 애초에 미포함) + 마스크 set 에 `password` 추가
  (2차 방어) + audit row 평문 password substring 부재 회귀 테스트.
- **B3 — password 비노출 불변식 미검증**: PATCH/POST 응답 echo·`/databases`·`/test` 에러 전문·GET 의 user 노출 등
  새 출력 경로 전체가 미검증. **합격선**: password 가 닿는 **모든** 출력(GET/PATCH/POST/test/databases/로그/에러/audit)
  열거 + 각 password-free 단언. 쓰기 응답은 `has_password: bool` 만(평문 echo 금지). 전 endpoint errno/예외타입만 반환.
  byte-level 회귀 테스트.

### MAJOR (합격선)
- **M1 — chokepoint 누락**: "6 chokepoint" 에 `tools.py:121`(cross-DB 가드)·`insight.py:1584`(`DATASOURCES.items()` 순회)
  **명시 포함**. 누락 시 "연결=새 좌표, 가드/insight=옛 좌표" split-brain. insight 는 `all_datasources()` 로 전환(삭제분 미스캔).
- **M2 — reload 정합**: auth 실패(1045)는 retry 안 해 **livelock 무**(Q1 우려 과대 — 확인됨). 단 **per-resolve(또는
  ciphertext-only 캐시)** 확정 — 평문 password **캐시 금지**(메모리/코어덤프 상주 방지), **delete/IsActive=0 즉시 무효화**,
  revoke 전파 최대지연(TTL)을 SLA 로 명시.
- **M3 — SSRF 강제 차단**: 신규 `/test`·`/databases`·POST 가 임의 host:port 즉시 연결 → 메타데이터IP(169.254.169.254)·
  RFC1918 스캔·errno/타이밍 oracle. **합격선**: 문서화만 불가 — RFC1918/링크로컬/메타데이터 IP **deny + host allowlist(CIDR)
  + DNS rebinding 방어(resolve 후 IP 재검증)**. `/databases` 는 RO GRANT 허용 DB 만 반환(서버 전체 enumeration 회피).
- **M4 — 키 관리**: ① 참조구현(task0034)은 **AAD=None** + per-record PBKDF2 → 복붙 함정(설계는 AAD=DatasourceKey).
  ② AAD=DatasourceKey 면 **키 rename 시 복호 실패** → rename 금지 또는 재암호화. ③ **로테이션 미동작**: 단일 `.env` 키로는
  v1→v2 중 구키 부재로 복호 불가. **합격선**: `.env.secret`(분리 파일 — `.env` 는 §6.1 least-privilege 상 전 service inherit
  이라 마스터키 부적격)에 **버전별 키 맵**(`AGENT_DATASOURCE_ENC_KEY_V1/_V2`), decrypt 가 레코드 EncryptionVersion 으로
  키 선택. AAD 규약 명문화 + AAD=None 회귀 테스트. rename 정책 결정.
- **M5 — 키 부재가 `.env` datasource 까지 깨면 안 됨**: `get_datasource()` 가 DB 복호 예외를 throw 하면 `.env` 폴백도 못 탐.
  **합격선**: per-record try/except — "키 부재 시 DB datasource 만 개별 skip, `.env`(winsql) 정상" 3-way 계약 + 회귀 테스트.

### MINOR
- **N1**: DB 우선 silent override → 충돌 시 **fail-loud(거부) 또는 명시 경고 로그+UI 배지**(무경고 비권장).
- **N2**: DELETE — 바인딩 product 있으면 기본 거부, force 시 영향 product audit 열거(키 문자열 바인딩, FK 없음 → 고아는
  `_resolve_product_datasource` fail-closed 라 기능적 안전하나 원인 불명 UX).
- **N3**: CRUD 로 광권한(db_datareader/root) 등록 마찰↓ → POST/PATCH 시 `SHOW GRANTS`/`fn_my_permissions` 과도권한 경고 배지.
- **N4**: `IsActive=0` 토글도 reload 전파 대상 — M2 정합에 포함.

### Open questions 확정 (검토 의견 반영)
- Q1=per-resolve(또는 ciphertext-only 캐시, 평문 무캐시). Q2=키부재 3-way 계약+테스트. Q3=fail-loud/경고(silent override 비권장).
  Q4=allowlist/사설망 차단 강제. Q5=password 만 암호화 + GET 은 user **비노출 유지**(enumeration 회피, §2.2 의 user 노출 규정 철회).

### 설계 정정 (위 반영)
- §2.1: 마스터키 → **`.env.secret` 버전별 키 맵**(`_V1/_V2`), decrypt 가 EncryptionVersion 으로 선택. AAD 규약 명문화.
- §2.2: `DbUser` GET 응답 비노출(저장은 평문 OK, 출력만 마스킹). 
- §2.3: **per-resolve(평문 무캐시)** + delete/IsActive 즉시 무효화 + `.env` per-record 격리.
- §2.4: effective default_db 를 가드·연결 **단일 소유** + 선택 DB 의 GRANT-범위 fail-closed 검증.
- §2.5: 쓰기 응답 `has_password` 만 + 전 endpoint errno-only + audit 화이트리스트.
- §3: SSRF allowlist/사설망 차단 강제.

## 7. 최종 결정 (사용자 2026-06-11) — 구현 착수

- **진행**: A→D 전체 연속 구현.
- **SSRF**: 사설망(RFC1918)·링크로컬·메타데이터 IP(169.254.0.0/16) **차단 강제** + host allowlist(옵션 CIDR).
- **키 관리 = envelope 암호화 (KEK/DEK)** — "마스터키도 DB 암호화 저장" 요청 충족:
  - **KEK(루트 키)**: `.env.secret` 의 `AGENT_DATASOURCE_KEK_V<n>`(base64 32B). **DB 밖 유일 비밀**(암호학적 필연 —
    루트 키가 DB 안에 있으면 DB 유출=전손). `.env`(전 service inherit) 아닌 분리 secret 파일.
  - **DEK(작업 키)**: 랜덤 32B, **KEK 로 암호화(wrap)해 DB `WebDatasourceKeys` 저장**(KeyVersion, DekWrapped,
    KekVersion). 즉 "마스터키(DEK)가 DB 에 암호화 저장"됨.
  - **데이터소스 password**: 활성 DEK 로 AESGCM 암호화(AAD=DatasourceKey), `WebDatasources.PasswordEnc` 저장,
    `EncryptionVersion`=DEK 버전.
  - 복호: KEK(.env.secret) → DEK unwrap(DB) → password 복호. **DB 만 유출 시 KEK 없어 전부 복호 불가.**
  - 로테이션: KEK 교체 = DEK 1행 재wrap(저렴). DEK 교체 = password 재암호화(버전 증가).
- 그 외 §6 합격선(B1 effective-DB 단일화+GRANT검증, B2 audit 화이트리스트, B3 password 비노출 전경로,
  M1 chokepoint(tools.py 가드·insight 순회 포함), M2 per-resolve·평문무캐시·delete즉시무효화, M5 .env 격리,
  N1 충돌 fail-loud) 전부 충족 후 outside-voice 재게이트 → merge → 배포 → 라이브 검증.

## 8. 구현 완료 (TASK-0205, A→D)
- **A (토대)**: `cred_crypto.py`(envelope), `datasources.py`(레지스트리), `WebDatasources`/`WebDatasourceKeys`/
  `WebProducts.DatasourceDatabase`, 소비처 전환, B1 effective default_db ContextVar. 보안 테스트 8 + 골든 RC=0.
- **B (CRUD)**: API POST/PATCH/DELETE/{key}/databases + 제품 바인딩 datasource_database. B2 audit 화이트리스트,
  B3 password 비노출(GET user/pw 제외·has_password), M3 SSRF 차단. admin UI 데이터소스 관리 탭(CRUD·테스트, write-only).
- **C (제품별 DB)**: 제품 상세에 MSSQL 참조 DB select(`/databases` 채움). B1 로 가드·연결 단일 DB.
- **D**: `.env` datasource 는 레거시 코exist(DB 우선). KEK 는 `.env.secret`(compose env_file 추가). 마이그레이션은
  운영자가 CRUD UI 로 재등록(별도 마이그레이션 액션 불요 — coexist).

## 9. 구현 outside-voice 재게이트 (REV-20260611-0205-impl) — REJECT → 수정

설계 합격선(§6) 충족 여부를 코드로 재검. 핵심 crypto/registry/B1/B2/B3/M2/M4/M5/CRUD = **26/26 실측 PASS**.
BLOCKER 1 + MAJOR 2 발견 → 수정:
- **BLOCKER-1 (KEK compose 미배선 → 라이브 inert)**: `.env.secret` 를 agent-common env_file 에 추가
  (`required:false` — 미설정 환경 무해). `.env.secret.example` 제공 + `.gitignore` 에 `.env.secret`. 마스터키를
  `.env`(전 service inherit) 아닌 분리 파일에 — least-privilege(SECURITY §6.1) 정합. 라이브 `encryption_ready=true` 검증.
- **MAJOR-1 (B1 GRANT-범위 검증 미구현)**: 제품별 참조 DB override 시 그 DB 가 datasource RO 로그인 접근 범위
  (`list_server_databases`)에 속하는지 **fail-closed 검증** 추가(PATCH product datasource). RO 로그인이 못 보는 DB 는
  product 바인딩으로도 지정 불가. (DB-side GRANT 가 최종 backstop, 앱 사전검증이 2차.)
- **MAJOR-2 (SSRF DNS rebinding)**: `_ssrf_check_host` 가 검증된 IP(`pinned_ip`)를 반환하고, admin 연결
  endpoint(test/databases/제품DB검증)가 **host 재해석 없이 pinned IP 로 고정 연결** → TOCTOU rebind 차단.
  메타데이터 IP 하드차단에 Alibaba(100.100.100.200)·IPv4-mapped 추가. (런타임 에이전트 경로의 DB datasource 는
  create-time SSRF 검증 + admin-only 생성이라 잔여 표면 제한 — 런타임 IP-pin 은 후속.)
- MINOR(후속): N-1 `ds` 접두 과도차단 완화, `/databases` MSSQL GRANT-스코프 enumeration(MySQL 은 엔진 권한필터).
