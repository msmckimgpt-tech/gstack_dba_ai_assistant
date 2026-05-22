---
doc_type: RUNBOOK
feature_id: feature-0003-agent-web-ui
status: active
edit_policy: rewrite
source_of_truth: true
runbook_id: minio-key-rotation
related_task: TASK-0094 Sprint 1 Phase 4 (D20 + R-F9)
---

# MinIO App Key Rotation Runbook (D20 — Dual-Key + Canary + Rollback)

본 runbook 은 ADR-0022 의 MinIO app 전용 access key (`MINIO_APP_ACCESS_KEY` /
`MINIO_APP_SECRET_KEY`) 의 안전한 rotation 절차다. BRIEFING Revision 2 의 R-F9
(Codex 2차 review finding) 흡수 정합.

**핵심 원칙**: single-key rotation 의 위험 (minio-init.sh 가 기존 key 폐기 → 전
서비스 다운) 을 dual-valid window + canary 검증 + 명시 rollback step 으로 차단.

---

## 1. 전제 조건

- ADR-0022 의 minio + minio-init 가 부트스트랩 완료 상태 (`agent-attachments`
  bucket + `attachment-app-rw` policy 존재).
- 운영자가 `.env` 파일에 접근 가능 + `docker compose` 명령 실행 가능.
- 사용자 traffic 차단 없이 rotation 진행 — dual-valid window 동안 신/구 key
  모두 동작.

---

## 2. Rotation 절차 (정상 path)

### Step 0. 사전 audit log

운영자는 rotation 시작 시점에 audit ActionCode `attachment.storage.key_rotation` 을
WebAuditEvents 에 수동 dispatch (또는 Phase 5 ship 후 자동 endpoint 호출):

```sql
INSERT INTO WebAuditEvents (Actor, ActionCode, ResourceType, ResourceId, ChangeJson, CreatedAt)
VALUES (?, 'attachment.storage.key_rotation', 'storage', 'minio',
        JSON_OBJECT('stage', 'started', 'reason', 'scheduled-rotation', 'old_key_prefix', SUBSTRING(?, 1, 8)),
        UTC_TIMESTAMP());
```

### Step 1. 새 app key 생성 (dual-valid window 시작)

`docker exec -it <minio_container> mc admin user add minio-local <NEW_ACCESS_KEY> <NEW_SECRET_KEY>`
또는 MinIO console (port 9001) 의 Users 패널에서 신규 user 추가.

신규 user 에 `attachment-app-rw` policy attach:
```bash
docker exec -it <minio_container> mc admin policy attach minio-local attachment-app-rw --user <NEW_ACCESS_KEY>
```

이 시점에서 **old key + new key 모두 활성** (dual-valid window 시작).

### Step 2. Canary 검증 (새 key 단독으로 round-trip)

새 key 의 동작을 별 임시 shell 에서 확인 (production 컨테이너에는 아직 미반영):

```bash
docker run --rm -it \
  -e MINIO_APP_ACCESS_KEY=<NEW_ACCESS_KEY> \
  -e MINIO_APP_SECRET_KEY=<NEW_SECRET_KEY> \
  -e MINIO_ENDPOINT=<host>:9000 \
  -e MINIO_BUCKET=agent-attachments \
  -v $(pwd)/unit/feature-0003-agent-web-ui/src:/app \
  -w /app \
  python:3.11 \
  bash -c "pip install -q boto3 && python -m modules.storage_minio"
```

기대 결과: `[storage_minio] smoke PASS` (`head_bucket:OK,put:OK,get:OK,delete:OK`).
FAIL 이면 Step 4 (rollback) 로 이동.

### Step 3. Production 컨테이너 재기동 (web + worker 순차)

`.env` 파일의 `MINIO_APP_ACCESS_KEY` / `MINIO_APP_SECRET_KEY` 를 신규 값으로 갱신:

```bash
# .env 직접 편집 또는 sed:
sed -i 's/^MINIO_APP_ACCESS_KEY=.*/MINIO_APP_ACCESS_KEY=<NEW>/' .env
sed -i 's/^MINIO_APP_SECRET_KEY=.*/MINIO_APP_SECRET_KEY=<NEW>/' .env
```

컨테이너 재기동 (web 먼저 1대, 5 분 후 web 추가 + worker. blue/green 환경이면
green 배포 후 traffic switch):

```bash
docker compose up -d --no-deps --force-recreate web
# 5 분 dogfooding 후:
docker compose up -d --no-deps --force-recreate insight-worker
docker compose up -d --no-deps --force-recreate agent
```

각 재기동 후 `/api/admin/health/attachment-grants` (Phase 10 ship 후) 또는 단순
`storage_minio.run_smoke_test()` 호출로 검증.

### Step 4. Old key 폐기 (dual-valid window 종료)

새 key 단독으로 24 시간 무사고 운영 확인 후 old key 삭제:

```bash
docker exec -it <minio_container> mc admin user remove minio-local <OLD_ACCESS_KEY>
```

audit dispatch:
```sql
INSERT INTO WebAuditEvents (Actor, ActionCode, ResourceType, ResourceId, ChangeJson, CreatedAt)
VALUES (?, 'attachment.storage.key_rotation', 'storage', 'minio',
        JSON_OBJECT('stage', 'completed', 'reason', 'scheduled-rotation', 'new_key_prefix', SUBSTRING(?, 1, 8)),
        UTC_TIMESTAMP());
```

---

## 3. Rollback Path (Step 2 또는 Step 3 실패 시)

### Trigger 조건

- Step 2 canary smoke 가 FAIL (head_bucket / put / get / delete 중 하나라도 stage
  에서 멈춤).
- Step 3 production 재기동 후 5 분 이내 `storage_minio` 관련 ERROR 가 stderr 또는
  health endpoint 에서 표면화.
- 사용자 upload / download 실패 보고 (`POST /api/.../attachments` 5xx, `GET
  /api/.../attachments/{id}/content` 401/403/5xx).

### Rollback 절차

1. `.env` 의 `MINIO_APP_ACCESS_KEY` / `MINIO_APP_SECRET_KEY` 를 **old 값으로 즉시
   revert** (사전에 백업한 .env.backup 활용 권장).
2. 영향받은 컨테이너 재기동 (Step 3 와 동일 순서: web → worker).
3. `storage_minio.run_smoke_test()` 호출로 old key round-trip 확인.
4. 신규 user 는 일단 유지 (Step 1 의 add 결과). 다음 rotation 시도 시 root cause
   분석 후 재시도.
5. audit dispatch:
   ```sql
   INSERT INTO WebAuditEvents (..., ChangeJson)
   VALUES (..., JSON_OBJECT('stage', 'rolled_back', 'reason', '<failure-cause>', ...));
   ```

### Rollback window 가 만료된 경우 (Step 4 후 발견)

old key 가 이미 삭제됐다면 직전 step 의 audit row 에서 timestamp 확인 후 incident
escalation. MinIO root credential 로 emergency restore (root credential 은 `.env`
의 `MINIO_ROOT_USER` / `MINIO_ROOT_PASSWORD` — 운영자만 접근 가능).

---

## 4. 자가 점검 체크리스트

- [ ] **Pre-rotation**: `.env` 의 기존 `MINIO_APP_*` 4 변수 backup (`.env.backup`
      또는 secret manager).
- [ ] **Step 1**: `mc admin user add` 명령이 success — `mc admin user list` 출력
      에 신규 user 표시.
- [ ] **Step 1**: `mc admin policy attach` 후 `mc admin user info <new>` 응답에
      `attachment-app-rw` policy 포함.
- [ ] **Step 2**: 임시 컨테이너에서 `storage_minio` smoke PASS (`head_bucket:OK,
      put:OK,get:OK,delete:OK`).
- [ ] **Step 3**: 각 production 컨테이너 재기동 후 `docker logs --tail 50` 에 권한
      error 없음.
- [ ] **Step 3**: 사용자 upload / download endpoint smoke (Phase 5 ship 후) 정상.
- [ ] **Step 4**: 24 시간 무사고 운영 확인 후 old user 삭제.
- [ ] **Step 4**: audit ActionCode `attachment.storage.key_rotation` 의 stage
      transition (`started` → `completed`) 모두 기록.

---

## 5. 자동화 가능성 (별 cycle 후보)

본 runbook 의 step 들은 향후 별 script 로 자동화 가능 (`bin/minio-key-rotate.sh`):
- Step 1 (mc admin user add)
- Step 2 (storage_minio smoke)
- Step 3 (docker compose up --force-recreate)
- Step 4 (24 시간 후 mc admin user remove)

자동화 시 fail-fast + audit dispatch + rollback trigger 가 한 script 안에서 처리.
현 Sprint 1 Phase 4 의 ship scope 외 — Phase 9 (D6 reconciliation worker) 또는
별 운영 cycle.

---

## 6. 관련 정책

- [ADR-0022](../../../docs/DECISIONS.md#adr-0022) — MinIO 도입 결정.
- BRIEFING [§17.3 R-F9](./BRIEFING-attachment-multi-cycle.md) — Codex 2차 finding
  흡수.
- [SECURITY.md §7.2](../../../docs/SECURITY.md) — 외부 배포 보완 (Sprint 1 의 docs
  갱신 묶음에서 본 runbook cross-ref 추가 예정).
- [FUNCTION AC-0205~0207](./FUNCTION.md) — Phase 1 Pre-flight 의 MinIO 부트스트랩.
- [FUNCTION AC-0223](./FUNCTION.md) — Phase 4 storage wrapper (본 cycle 시점).
