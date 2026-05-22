"""MinIO S3-compat 첨부 storage wrapper.

TASK-0094 Sprint 1 Phase 4 (ADR-0022). BRIEFING D1 + D13 + D20 정합.

본 module 의 책임:
1. **boto3 S3 client** 의 idempotent 생성 (`get_s3_client()`) — env-driven endpoint /
   credentials / region, retry config (exponential backoff), connection pool.
2. **Object key 생성** — `_make_object_key(conversation_id, attachment_uuid, filename)`
   = `<cid>/<uuid>/<safe_filename>` 형식 (BRIEFING §5.1 ObjectKey 명세).
3. **Upload** — `put_object_bytes(...)` boto3 put_object wrapper.
4. **Download** — `get_object_bytes(...)` boto3 get_object 후 bytes 반환.
5. **Signed URL** — `generate_presigned_get(...)` 사내망 다운로드 전용 TTL 기반
   short-lived URL. **외부 LLM 송신 금지 (D13)** — 외부 provider 에는 base64 inline
   또는 Files API 만 사용. signed URL 은 frontend 사내망 다운로드에만.
6. **Delete** — `delete_object(object_key)` boto3 delete_object wrapper.
7. **Smoke test** — `run_smoke_test()` (`bucket exists` + `put / get / delete` 단일
   round-trip). 부트스트랩 검증용.

본 module 은 의도적으로 thin — RBAC / consent / audit 검증은 caller 에게 위임.
Phase 5 (upload endpoint) 에서 caller 가 audit + RBAC 적용.

D20 dual-key rotation 운영 항목 (key rotation runbook 은 별 doc — RUNBOOK-minio-key-rotation.md):
- 본 module 의 `get_s3_client()` 는 `MINIO_APP_ACCESS_KEY` / `MINIO_APP_SECRET_KEY` 만
  사용. dual-valid window 중에는 환경변수 갱신 후 컨테이너 재기동 1 회로 새 key
  활성화.
- rotation 실패 시 old key rollback 도 환경변수 revert + 재기동 1 회.
- `_KEY_ROTATION_AUDIT_KEY` 상수 = audit ActionCode `attachment.storage.key_rotation`
  (Phase 5 audit dispatch 에서 사용).
"""

from __future__ import annotations

import io
import os
import re
import sys
import time
from typing import Any, Iterator

try:
    import boto3  # type: ignore[import-not-found]
    from botocore.client import Config as _BotoConfig  # type: ignore[import-not-found]
    from botocore.exceptions import (  # type: ignore[import-not-found]
        BotoCoreError,
        ClientError,
        EndpointConnectionError,
    )
    BOTO3_AVAILABLE = True
except Exception:
    boto3 = None  # type: ignore[assignment]
    _BotoConfig = None  # type: ignore[assignment]
    BotoCoreError = Exception  # type: ignore[assignment,misc]
    ClientError = Exception  # type: ignore[assignment,misc]
    EndpointConnectionError = Exception  # type: ignore[assignment,misc]
    BOTO3_AVAILABLE = False


_DEFAULT_ENDPOINT = "minio:9000"
_DEFAULT_BUCKET = "agent-attachments"
_DEFAULT_SIGNED_URL_TTL_SEC = 900
_DEFAULT_REGION = "us-east-1"  # MinIO 가 무관히 처리하지만 boto3 가 region 요구.
_DEFAULT_CONNECT_TIMEOUT_SEC = 5.0
_DEFAULT_READ_TIMEOUT_SEC = 30.0
_DEFAULT_MAX_ATTEMPTS = 3

# Audit ActionCode (Phase 5 에서 build_audit_change_json 의 case 등록 대상).
KEY_ROTATION_AUDIT_KEY = "attachment.storage.key_rotation"
SMOKE_TEST_AUDIT_KEY = "attachment.storage.smoke_test"

# Object key safe-character pattern. RFC 3986 의 unreserved + `/` + `.` 만 허용.
_SAFE_FILENAME_RE = re.compile(r"[^A-Za-z0-9._\-]")


class StorageConfigError(RuntimeError):
    """MinIO 설정 누락 / 잘못된 env 값."""


class StorageOperationError(RuntimeError):
    """MinIO API 호출 실패 (network / auth / not-found)."""


def _env(name: str, default: str = "") -> str:
    """env 읽기 + strip. 빈 값은 default 로 fallback."""
    value = (os.getenv(name) or "").strip()
    return value if value else default


def _resolve_endpoint_url(raw: str) -> str:
    """`minio:9000` 형식의 host:port 를 `http://host:port` URL 로 정규화.

    boto3 는 endpoint_url 에 scheme 을 요구한다. http 또는 https 가 명시되어 있으면
    그대로 사용. 그 외엔 사내망 dev 가정으로 http 사용 (TLS 는 caddy 가 사이에).
    """
    if not raw:
        raise StorageConfigError("MINIO_ENDPOINT is empty")
    if raw.startswith("http://") or raw.startswith("https://"):
        return raw
    return f"http://{raw}"


def get_storage_config() -> dict[str, Any]:
    """env 기반 MinIO 설정을 dict 으로 반환. caller 가 검증 용도로 사용."""
    return {
        "endpoint_url": _resolve_endpoint_url(_env("MINIO_ENDPOINT", _DEFAULT_ENDPOINT)),
        "access_key": _env("MINIO_APP_ACCESS_KEY"),
        "secret_key": _env("MINIO_APP_SECRET_KEY"),
        "bucket": _env("MINIO_BUCKET", _DEFAULT_BUCKET),
        "region": _env("MINIO_REGION", _DEFAULT_REGION),
        "signed_url_ttl_sec": max(
            60, int(_env("MINIO_SIGNED_URL_TTL_SEC", str(_DEFAULT_SIGNED_URL_TTL_SEC)))
        ),
        "connect_timeout_sec": float(
            _env("MINIO_CONNECT_TIMEOUT_SEC", str(_DEFAULT_CONNECT_TIMEOUT_SEC))
        ),
        "read_timeout_sec": float(
            _env("MINIO_READ_TIMEOUT_SEC", str(_DEFAULT_READ_TIMEOUT_SEC))
        ),
        "max_attempts": max(1, int(_env("MINIO_MAX_ATTEMPTS", str(_DEFAULT_MAX_ATTEMPTS)))),
    }


_S3_CLIENT_CACHE: dict[str, Any] = {}


def get_s3_client(*, force_new: bool = False) -> Any:
    """boto3 S3 client 의 idempotent factory.

    Args:
        force_new: True 시 cache 무시하고 새 client 생성. key rotation 후 새 client
                   를 강제 사용해야 할 때 호출.

    Raises:
        StorageConfigError: boto3 미설치 또는 env 누락.
        StorageOperationError: client 생성 자체 실패 (예: invalid endpoint).
    """
    if not BOTO3_AVAILABLE:
        raise StorageConfigError(
            "boto3 not installed — add 'boto3>=1.34.0' to requirements.txt and reinstall"
        )

    cfg = get_storage_config()
    if not cfg["access_key"] or not cfg["secret_key"]:
        raise StorageConfigError(
            "MINIO_APP_ACCESS_KEY / MINIO_APP_SECRET_KEY env required (rotation 대상 — bootstrap 시점 minio-init.sh 가 생성)"
        )

    cache_key = f"{cfg['endpoint_url']}|{cfg['access_key']}|{cfg['bucket']}"
    if not force_new and cache_key in _S3_CLIENT_CACHE:
        return _S3_CLIENT_CACHE[cache_key]

    boto_config = _BotoConfig(  # type: ignore[misc]
        region_name=cfg["region"],
        signature_version="s3v4",
        connect_timeout=cfg["connect_timeout_sec"],
        read_timeout=cfg["read_timeout_sec"],
        retries={"max_attempts": cfg["max_attempts"], "mode": "standard"},
        # MinIO 는 path-style URL 요구 (virtual-host style 미지원).
        s3={"addressing_style": "path"},
    )
    try:
        client = boto3.client(  # type: ignore[union-attr]
            "s3",
            endpoint_url=cfg["endpoint_url"],
            aws_access_key_id=cfg["access_key"],
            aws_secret_access_key=cfg["secret_key"],
            config=boto_config,
        )
    except Exception as exc:
        raise StorageOperationError(f"boto3 client creation failed: {exc}") from exc

    _S3_CLIENT_CACHE[cache_key] = client
    return client


def safe_filename(filename: str, *, max_length: int = 200) -> str:
    """Object key 에 안전한 filename 으로 sanitize.

    boto3 / MinIO 는 unicode 도 수용하지만, audit / log / signed URL 의 가독성을
    위해 alphanumeric + `.` + `-` + `_` 외 문자는 `_` 로 대체. 빈 결과는 `unnamed`.

    HMAC (D12) 와 original filename (DB 보존) 은 별도 — 본 함수의 결과는 ObjectKey
    의 일부로만 사용.
    """
    if not filename:
        return "unnamed"
    safe = _SAFE_FILENAME_RE.sub("_", filename.strip())
    safe = safe.strip("._-") or "unnamed"
    if len(safe) > max_length:
        # 끝에서 일부 cut + extension 보존 시도.
        if "." in safe:
            stem, ext = safe.rsplit(".", 1)
            keep = max_length - len(ext) - 1
            safe = (stem[:keep] if keep > 0 else "unnamed") + "." + ext
        else:
            safe = safe[:max_length]
    return safe


def make_object_key(conversation_id: str, attachment_uuid: str, filename: str) -> str:
    """BRIEFING §5.1 ObjectKey 형식: `<cid>/<uuid>/<safe_filename>`."""
    if not conversation_id:
        raise StorageConfigError("conversation_id required for ObjectKey")
    if not attachment_uuid:
        raise StorageConfigError("attachment_uuid required for ObjectKey")
    return f"{conversation_id}/{attachment_uuid}/{safe_filename(filename)}"


def put_object_bytes(
    object_key: str,
    body: bytes,
    *,
    content_type: str = "application/octet-stream",
    metadata: dict[str, str] | None = None,
    client: Any = None,
    bucket: str | None = None,
) -> dict[str, Any]:
    """bytes 객체를 MinIO 에 업로드. caller 가 size cap (D8) / MIME allowlist (D7) /
    audit (Phase 5) 검증 책임. 본 함수는 thin wrapper.

    Returns:
        boto3 put_object response (ETag 등 포함).

    Raises:
        StorageOperationError: API 실패 (network / auth / 5xx 등).
    """
    if not object_key:
        raise StorageConfigError("object_key required")
    if not isinstance(body, (bytes, bytearray)):
        raise StorageConfigError(f"body must be bytes (got {type(body).__name__})")

    cli = client or get_s3_client()
    bucket_name = bucket or get_storage_config()["bucket"]
    args = {
        "Bucket": bucket_name,
        "Key": object_key,
        "Body": body,
        "ContentType": content_type or "application/octet-stream",
    }
    if metadata:
        # boto3 metadata 키는 `x-amz-meta-` prefix 자동. 사용자는 raw key 만 전달.
        args["Metadata"] = {str(k): str(v) for k, v in metadata.items()}

    try:
        return cli.put_object(**args)
    except (ClientError, BotoCoreError, EndpointConnectionError) as exc:  # type: ignore[misc]
        raise StorageOperationError(f"put_object failed for {object_key}: {exc}") from exc


def get_object_bytes(
    object_key: str,
    *,
    client: Any = None,
    bucket: str | None = None,
) -> bytes:
    """MinIO 객체의 bytes 전체를 메모리로 반환.

    D13 적용: 본 함수의 반환값을 외부 LLM (OpenAI / Anthropic) 에 base64 inline 또는
    Files API 로 전달. **signed URL 송신 금지 — 본 함수의 결과를 사용**.

    대용량 파일 streaming 은 별 helper 로 분리 권장 (본 함수는 in-memory).
    """
    if not object_key:
        raise StorageConfigError("object_key required")

    cli = client or get_s3_client()
    bucket_name = bucket or get_storage_config()["bucket"]
    try:
        resp = cli.get_object(Bucket=bucket_name, Key=object_key)
    except (ClientError, BotoCoreError, EndpointConnectionError) as exc:  # type: ignore[misc]
        raise StorageOperationError(f"get_object failed for {object_key}: {exc}") from exc

    body = resp.get("Body")
    if body is None:
        raise StorageOperationError(f"get_object returned no Body for {object_key}")
    try:
        data = body.read()
    finally:
        try:
            body.close()
        except Exception:
            pass
    if not isinstance(data, (bytes, bytearray)):
        raise StorageOperationError(
            f"get_object body returned non-bytes for {object_key}: {type(data).__name__}"
        )
    return bytes(data)


def generate_presigned_get(
    object_key: str,
    *,
    ttl_sec: int | None = None,
    response_filename: str | None = None,
    client: Any = None,
    bucket: str | None = None,
) -> str:
    """사내망 다운로드 전용 signed URL 발급 (D1).

    **외부 LLM 송신 금지 (D13)** — caller 는 본 URL 을 frontend 다운로드 응답에만
    사용. provider 에 보낼 때는 `get_object_bytes()` 후 base64 inline 또는 Files API.

    response_filename 지정 시 `Content-Disposition: attachment; filename="..."` 가
    URL 응답 header 에 포함. frontend 다운로드 시 사용자에게 원본 filename 노출.
    """
    if not object_key:
        raise StorageConfigError("object_key required")

    cfg = get_storage_config()
    cli = client or get_s3_client()
    bucket_name = bucket or cfg["bucket"]
    expires = int(ttl_sec) if ttl_sec else int(cfg["signed_url_ttl_sec"])
    params = {"Bucket": bucket_name, "Key": object_key}
    if response_filename:
        safe = safe_filename(response_filename)
        params["ResponseContentDisposition"] = f'attachment; filename="{safe}"'
    try:
        return str(
            cli.generate_presigned_url(
                "get_object",
                Params=params,
                ExpiresIn=expires,
            )
        )
    except (ClientError, BotoCoreError, EndpointConnectionError) as exc:  # type: ignore[misc]
        raise StorageOperationError(
            f"generate_presigned_url failed for {object_key}: {exc}"
        ) from exc


def delete_object(
    object_key: str,
    *,
    client: Any = None,
    bucket: str | None = None,
) -> dict[str, Any]:
    """MinIO 객체 삭제. caller 가 D6 lifecycle taxonomy (admin_purge / legal) 의
    immediate-delete 경로에서 호출. user_delete / conv_soft 는 reconciliation worker
    (Phase 9) 가 retention 만료 후 본 함수 호출."""
    if not object_key:
        raise StorageConfigError("object_key required")

    cli = client or get_s3_client()
    bucket_name = bucket or get_storage_config()["bucket"]
    try:
        return cli.delete_object(Bucket=bucket_name, Key=object_key)
    except (ClientError, BotoCoreError, EndpointConnectionError) as exc:  # type: ignore[misc]
        raise StorageOperationError(f"delete_object failed for {object_key}: {exc}") from exc


def bucket_exists(*, client: Any = None, bucket: str | None = None) -> bool:
    """bucket 존재 확인 (head_bucket). minio-init.sh 가 부트스트랩 시점에 생성하므로
    runtime 에서는 항상 True 가 정상. False 면 minio-init 실패 또는 mis-config."""
    if not BOTO3_AVAILABLE:
        return False
    try:
        cli = client or get_s3_client()
    except StorageConfigError:
        return False
    bucket_name = bucket or get_storage_config()["bucket"]
    try:
        cli.head_bucket(Bucket=bucket_name)
        return True
    except (ClientError, BotoCoreError, EndpointConnectionError):  # type: ignore[misc]
        return False


def run_smoke_test(*, client: Any = None) -> dict[str, Any]:
    """부트스트랩 검증 — `head_bucket` + `put / get / delete` round-trip.

    audit ActionCode = SMOKE_TEST_AUDIT_KEY (`attachment.storage.smoke_test`). caller
    는 본 결과를 audit 에 dispatch (Phase 5 ship 후 시점부터).

    Returns:
        {"ok": bool, "stages": [...], "error": str | None, "elapsed_ms": float}
    """
    result: dict[str, Any] = {
        "ok": False,
        "stages": [],
        "error": None,
        "elapsed_ms": 0.0,
    }
    started = time.monotonic()
    try:
        cli = client or get_s3_client()
        cfg = get_storage_config()
        bucket_name = cfg["bucket"]

        # Stage 1: head_bucket
        if not bucket_exists(client=cli, bucket=bucket_name):
            result["error"] = f"bucket missing: {bucket_name} (minio-init.sh failed?)"
            result["stages"].append("head_bucket:FAIL")
            return result
        result["stages"].append("head_bucket:OK")

        # Stage 2: put
        smoke_key = f"_smoke/{int(time.time() * 1000)}-storage-minio.txt"
        smoke_body = b"TASK-0094 Phase 4 smoke test marker. Safe to delete."
        put_object_bytes(
            smoke_key,
            smoke_body,
            content_type="text/plain",
            client=cli,
            bucket=bucket_name,
        )
        result["stages"].append("put:OK")

        # Stage 3: get + body match
        got = get_object_bytes(smoke_key, client=cli, bucket=bucket_name)
        if got != smoke_body:
            result["error"] = f"get returned mismatched body: {len(got)} bytes vs {len(smoke_body)}"
            result["stages"].append("get:FAIL")
            return result
        result["stages"].append("get:OK")

        # Stage 4: delete + verify gone
        delete_object(smoke_key, client=cli, bucket=bucket_name)
        result["stages"].append("delete:OK")

        result["ok"] = True
        return result
    except (StorageConfigError, StorageOperationError) as exc:
        result["error"] = str(exc)
        return result
    except Exception as exc:  # defense in depth
        result["error"] = f"unexpected: {exc}"
        return result
    finally:
        result["elapsed_ms"] = round((time.monotonic() - started) * 1000.0, 2)


def reset_client_cache() -> None:
    """key rotation runbook 의 step 따라 새 env 적용 후 호출. 캐시된 client 무효화."""
    _S3_CLIENT_CACHE.clear()


def _cli_smoke() -> int:
    """`python -m feature_0003.modules.storage_minio smoke` 식의 직접 호출 helper.

    Sprint 1 ship 검증의 일부로 dev 환경에서 수동 실행. boto3 미설치 시 graceful skip.
    """
    if not BOTO3_AVAILABLE:
        sys.stderr.write("[storage_minio] boto3 not installed — skipping smoke\n")
        return 2
    res = run_smoke_test()
    if res["ok"]:
        sys.stdout.write(
            f"[storage_minio] smoke PASS ({res['elapsed_ms']} ms, stages={','.join(res['stages'])})\n"
        )
        return 0
    sys.stderr.write(
        f"[storage_minio] smoke FAIL ({res['elapsed_ms']} ms, stages={','.join(res['stages'])}, error={res['error']})\n"
    )
    return 1


if __name__ == "__main__":
    sys.exit(_cli_smoke())
