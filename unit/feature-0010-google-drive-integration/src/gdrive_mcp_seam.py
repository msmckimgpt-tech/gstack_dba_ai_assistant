"""Google Drive MCP per-account 토큰 주입 seam (feature-0010 — TASK-20260623T190000-gdrive-foundation).

상태: SCAFFOLD / SEAM SPEC (연동 미수행). 본 모듈은 "각 계정이 본인 Drive 에 연결" 을 가능케 하는
멀티테넌트 MCP 호출 경로의 **계약(contract)** 을 실행 가능한 형태로 명세한다. 현재 cycle 은 이 seam 을
런타임에 연결하지 않는다 — 에이전트 hot-path(modules/mcp_client.py, feature-0002)는 무수정이며,
본 모듈은 활성화 cycle 에서 그 자리에 끼울 어댑터의 형태를 고정한다.

왜 별도 seam 인가 (DECISIONS.md ADR-gdrive-seam-A 정본):
  DBHub/SQL MCP 는 단일 자격증명(서비스 DSN) 서버다. Drive 는 "계정마다 자기 토큰" 이라 단일
  자격증명 모델이 맞지 않는다. 선택지:
    (A) 호출 시 토큰 주입  — 공유 Drive MCP 서버를 상태 비저장으로 두고, 에이전트가 호출 때
        인증된 계정의 access_token 을 Authorization 헤더(또는 인자)로 전달. ← 채택(멀티테넌트 표준).
    (B) 계정별 서버 세션   — 계정마다 토큰으로 초기화한 세션/프로세스. 무겁고 수명관리 복잡.
    (C) 서비스계정 위임    — Workspace 도메인 전체 위임. 사내 단일 도메인 한정, 임의 Gmail 불가.
  seam(A)는 access_token 평문이 에이전트 프로세스 메모리에만 잠깐 존재하고 디스크/로그에 남지 않게
  한다. 토큰 복호는 요청 처리 시점에 1회, 사용 후 폐기.

활성화 cycle 의 TODO (SECURITY.md §16):
  - access_token 만료 시 refresh_token 으로 회전(refresh_access_token 미구현 — 아래 NotImplementedError).
  - Authorization 헤더가 MCP 서버 로그/트레이스에 남지 않도록 마스킹.
  - scope 최소권한(drive.readonly) 확인 + 승격 시 사람 재승인.
"""
from __future__ import annotations

from typing import Any, Optional

# app.py(feature-0003)의 저장측과 동일 규약 — 단일 정본으로 유지한다.
GDRIVE_PROVIDER = "google_drive"
GDRIVE_AAD_PREFIX = "gdrive:"


class GDriveTokenUnavailable(Exception):
    """계정이 Drive 미연결이거나 토큰 복호 불가(DEK 부재/AAD 불일치). caller 가 fail-closed."""


def load_account_drive_access_token(mem_conn, account_id: int) -> Optional[str]:
    """계정의 저장된 Drive access_token 평문을 복호해 반환(없으면 None).

    app.py 의 _gdrive_store_tokens 가 쓴 암호문을 cred_crypto(AAD=gdrive:{account_id})로 복호한다.
    저장측과 본 함수가 AAD/Provider 규약을 공유하는 것이 핵심 계약이다.

    NOTE(토대 단계): 만료 검사/refresh 회전은 refresh_access_token() 책임이며 본 cycle 미구현.
    여기서는 저장된 access_token 을 그대로 반환만 한다(만료 토큰도 그대로 — 활성화 cycle 에서 보강).
    """
    try:
        from modules import cred_crypto as _cc  # feature-0002 unified ns (활성화 시 동일 컨테이너)
        from shared import datasources as _dsr
    except Exception as exc:  # pragma: no cover - 토대 단계에선 이 경로가 런타임 미도달
        raise GDriveTokenUnavailable(f"crypto modules unavailable: {exc}") from None
    if not _cc.enc_available():
        raise GDriveTokenUnavailable("encryption(KEK) not configured")

    cur = mem_conn.cursor(dictionary=True)
    try:
        cur.execute(
            "SELECT AccessTokenEnc, EncryptionVersion, IsConnected, RevokedAt "
            "FROM WebGoogleDriveTokens WHERE AccountId = %s AND Provider = %s LIMIT 1",
            (int(account_id), GDRIVE_PROVIDER),
        )
        row = cur.fetchone()
    finally:
        cur.close()
    if not row or int(row.get("IsConnected") or 0) != 1 or row.get("RevokedAt"):
        return None
    enc = row.get("AccessTokenEnc")
    if not enc:
        return None
    got = _dsr.get_dek(mem_conn, int(row.get("EncryptionVersion") or 0))
    if not got:
        raise GDriveTokenUnavailable("DEK version unavailable")
    _ver, dek = got
    try:
        return _cc.decrypt_password(dek, str(enc), f"{GDRIVE_AAD_PREFIX}{int(account_id)}")
    except Exception:
        raise GDriveTokenUnavailable("token decrypt failed (AAD/key mismatch)") from None


def build_gdrive_mcp_headers(access_token: str) -> "dict[str, str]":
    """seam(A) 계약: Drive MCP 서버로 보낼 per-call 인증 헤더. Bearer access_token.

    에이전트의 MCP 클라이언트가 tools/call 직전 본 헤더를 합성해 주입한다(상태 비저장 서버).
    """
    return {"Authorization": f"Bearer {str(access_token)}"}


def refresh_access_token(mem_conn, account_id: int) -> str:
    """만료된 access_token 을 refresh_token 으로 회전(저장 갱신 포함).

    토대 단계 미구현 — 활성화 cycle 에서 Google token endpoint(grant_type=refresh_token) 백채널
    호출 + _gdrive_store_tokens 재저장으로 완성한다(SECURITY.md §16 강화 TODO).
    """
    raise NotImplementedError(
        "refresh_access_token: feature-0010 활성화 cycle 에서 구현 (토대 단계는 seam 명세만)."
    )


def inject_for_call(mem_conn, account_id: int, base_headers: "Optional[dict[str, Any]]" = None) -> "dict[str, Any]":
    """편의 어댑터: 계정 토큰 복호 → MCP 호출 헤더 합성. 미연결/복호불가 시 GDriveTokenUnavailable.

    활성화 cycle 에서 mcp_client 의 tools/call 직전에 호출될 단일 진입점(seam A 의 코드 자리표).
    """
    token = load_account_drive_access_token(mem_conn, account_id)
    if not token:
        raise GDriveTokenUnavailable(f"account {account_id} has no connected Google Drive")
    headers = dict(base_headers or {})
    headers.update(build_gdrive_mcp_headers(token))
    return headers
