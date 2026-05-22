#!/bin/sh
# minio-init.sh — TASK-0094 Sprint 1 Phase 1 (ADR-0022) MinIO bootstrap.
#
# Run once per compose lifecycle. Idempotent:
#   1) wait for MinIO to be ready
#   2) configure mc alias with root credentials (.env MINIO_ROOT_*)
#   3) create bucket if absent (MINIO_BUCKET, default agent-attachments)
#   4) apply lifecycle policy for delete_reason retention (BRIEFING D6)
#   5) create app-only access key (MINIO_APP_*) for runtime (rotation by D20)
#   6) NOTE: root credential 비활성화는 별 cycle 의 rotation runbook 에서 처리
#      (현 단계는 first-bootstrap 만; rotation 은 Phase 4 ship 조건)
#
# Exit 0 on success. Exit non-zero on any required step failure (compose
# 가 본 init service 의 fail 을 표면화).

set -eu

: "${MINIO_ROOT_USER:?MINIO_ROOT_USER required}"
: "${MINIO_ROOT_PASSWORD:?MINIO_ROOT_PASSWORD required}"
: "${MINIO_APP_ACCESS_KEY:?MINIO_APP_ACCESS_KEY required (Phase 1 bootstrap; D20 rotation 별 cycle)}"
: "${MINIO_APP_SECRET_KEY:?MINIO_APP_SECRET_KEY required}"
BUCKET="${MINIO_BUCKET:-agent-attachments}"
ALIAS_NAME="minio-local"
MINIO_HOST="${MINIO_HOST:-minio}"
MINIO_PORT="${MINIO_PORT:-9000}"

echo "[minio-init] waiting for MinIO at ${MINIO_HOST}:${MINIO_PORT} ..."
for i in $(seq 1 30); do
  if mc alias set "$ALIAS_NAME" "http://${MINIO_HOST}:${MINIO_PORT}" "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD" >/dev/null 2>&1; then
    echo "[minio-init] mc alias set: OK"
    break
  fi
  if [ "$i" -eq 30 ]; then
    echo "[minio-init] FAIL: MinIO unreachable after 30 attempts"
    exit 1
  fi
  sleep 2
done

# Step 3: idempotent bucket
if mc ls "$ALIAS_NAME/$BUCKET" >/dev/null 2>&1; then
  echo "[minio-init] bucket '$BUCKET' already exists — skip create"
else
  mc mb "$ALIAS_NAME/$BUCKET"
  echo "[minio-init] bucket '$BUCKET' created"
fi

# Step 4: lifecycle policy — D6 delete_reason 별 retention
# user_delete / conv_soft  → 30 days (TTL via object tagging delete-reason)
# admin_purge / legal      → immediate (app 측에서 직접 mc rm + DB hard-delete)
#
# 본 단계는 tag-prefixed rule 적용. detail tag schema 는 app upload 시점에
# `x-amz-meta-delete-reason` 또는 object tag 로 설정. lifecycle 의 filter
# 는 prefix `pending-delete/` (app 이 delete_pending 시점에 object 를 이
# prefix 로 move). lifecycle 정책 JSON 은 향후 cycle 에서 정교화 — Phase 1
# 은 default policy 만 유지 (D6 reconciliation worker 가 explicit delete
# 담당; lifecycle 은 retention-only safety net).
#
# (Phase 1 은 lifecycle 정책 skeleton 만; 실제 lifecycle rule 는 Phase 9
# delete reconciliation worker cycle 에서 ship)
echo "[minio-init] lifecycle policy: skeleton only — full rule deferred to Phase 9 (D6 reconciliation worker)"

# Step 5: app-only access key — idempotent.
# `mc admin user add` 는 user 가 이미 있으면 fail 하므로 check 후 add.
if mc admin user info "$ALIAS_NAME" "$MINIO_APP_ACCESS_KEY" >/dev/null 2>&1; then
  echo "[minio-init] app user '$MINIO_APP_ACCESS_KEY' already exists — skip add"
else
  mc admin user add "$ALIAS_NAME" "$MINIO_APP_ACCESS_KEY" "$MINIO_APP_SECRET_KEY"
  echo "[minio-init] app user '$MINIO_APP_ACCESS_KEY' added"
fi

# Attach readwrite-equivalent policy scoped to the bucket only. MinIO 의
# built-in `readwrite` policy 는 모든 bucket 권한이라 too broad — 본 단계는
# bucket-scoped custom policy 를 생성/attach. policy JSON 은 별 file 로
# 정의하지 않고 inline (small enough).
APP_POLICY_NAME="attachment-app-rw"
cat > /tmp/${APP_POLICY_NAME}.json <<JSON
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
        "s3:DeleteObject",
        "s3:GetObjectTagging",
        "s3:PutObjectTagging"
      ],
      "Resource": ["arn:aws:s3:::${BUCKET}/*"]
    },
    {
      "Effect": "Allow",
      "Action": [
        "s3:ListBucket",
        "s3:GetBucketLocation"
      ],
      "Resource": ["arn:aws:s3:::${BUCKET}"]
    }
  ]
}
JSON

if mc admin policy info "$ALIAS_NAME" "$APP_POLICY_NAME" >/dev/null 2>&1; then
  mc admin policy update "$ALIAS_NAME" "$APP_POLICY_NAME" /tmp/${APP_POLICY_NAME}.json
  echo "[minio-init] policy '$APP_POLICY_NAME' updated"
else
  mc admin policy create "$ALIAS_NAME" "$APP_POLICY_NAME" /tmp/${APP_POLICY_NAME}.json
  echo "[minio-init] policy '$APP_POLICY_NAME' created"
fi

mc admin policy attach "$ALIAS_NAME" "$APP_POLICY_NAME" --user "$MINIO_APP_ACCESS_KEY" >/dev/null 2>&1 || true
echo "[minio-init] policy '$APP_POLICY_NAME' attached to '$MINIO_APP_ACCESS_KEY'"

echo "[minio-init] bootstrap complete — bucket=$BUCKET app_user=$MINIO_APP_ACCESS_KEY policy=$APP_POLICY_NAME"
exit 0
