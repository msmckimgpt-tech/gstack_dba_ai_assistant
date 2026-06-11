"""데이터소스 자격증명 envelope 암호화 (TASK-0205, DESIGN-datasource-registry §7).

**envelope (KEK/DEK)** — 사용자 요청 "마스터키도 DB 에 암호화 저장" 충족:
  - **KEK(루트 키)**: `.env.secret` 의 `AGENT_DATASOURCE_KEK_V<n>`(base64 32B). DB 밖 유일 비밀
    (루트 키가 DB 안에 있으면 DB 유출=전손 — 암호학적 필연). `.env`(전 service inherit) 아닌 분리 파일.
  - **DEK(작업 키)**: 랜덤 32B, KEK 로 wrap(암호화)해 DB 저장 → "마스터키가 DB 에 암호화 저장".
  - **password**: 활성 DEK 로 AESGCM 암호화(AAD=DatasourceKey).
  - 복호: KEK → DEK unwrap → password 복호. DB 만 유출 시 KEK 없어 전부 복호 불가.

본 모듈은 **순수 crypto**(DB 접근 없음). DEK 저장/조회는 modules/datasources.py 가 담당.
키 부재/cryptography 부재 시 enc_available()=False → caller 가 fail-closed(.env datasource 는 영향 없음).
"""
from __future__ import annotations

import base64
import os

try:  # cryptography 는 requirements.txt 에 있으나 방어적 import.
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM  # type: ignore
    _CRYPTO_OK = True
except Exception:  # pragma: no cover
    AESGCM = None  # type: ignore
    _CRYPTO_OK = False

_KEK_PREFIX = "AGENT_DATASOURCE_KEK_V"
_NONCE_LEN = 12


class CredCryptoError(Exception):
    """복호/wrap 실패 (키 부재·AAD 불일치·포맷 오류). caller 가 fail-closed 처리."""


def _b64d(s: str) -> bytes:
    return base64.b64decode(str(s).strip())


def _b64e(b: bytes) -> str:
    return base64.b64encode(b).decode("ascii")


def load_keks() -> "dict[int, bytes]":
    """`.env.secret` 의 버전별 KEK 맵 {version:int -> 32B key}. 32B 아닌 값은 무시."""
    out: dict[int, bytes] = {}
    for k, v in os.environ.items():
        if not k.startswith(_KEK_PREFIX):
            continue
        try:
            ver = int(k[len(_KEK_PREFIX):])
            raw = _b64d(v)
        except Exception:
            continue
        if len(raw) == 32:
            out[ver] = raw
    return out


def current_kek_version() -> "int | None":
    keks = load_keks()
    return max(keks) if keks else None


def enc_available() -> bool:
    """암호화 사용 가능 여부 — cryptography 설치 + KEK 1개 이상."""
    return _CRYPTO_OK and bool(load_keks())


def _aesgcm_encrypt(key: bytes, plain: bytes, aad: "bytes | None") -> str:
    if not _CRYPTO_OK:
        raise CredCryptoError("cryptography 미설치")
    iv = os.urandom(_NONCE_LEN)
    ct = AESGCM(key).encrypt(iv, plain, aad)
    return f"v1:{_b64e(iv)}:{_b64e(ct)}"


def _aesgcm_decrypt(key: bytes, token: str, aad: "bytes | None") -> bytes:
    if not _CRYPTO_OK:
        raise CredCryptoError("cryptography 미설치")
    parts = str(token or "").split(":")
    if len(parts) != 3 or parts[0] != "v1":
        raise CredCryptoError("토큰 포맷 오류")
    try:
        iv = _b64d(parts[1])
        ct = _b64d(parts[2])
        return AESGCM(key).decrypt(iv, ct, aad)
    except Exception as exc:  # InvalidTag(AAD/키 불일치) 등
        raise CredCryptoError(f"복호 실패: {type(exc).__name__}") from None


# ── DEK envelope (KEK 로 wrap/unwrap) ────────────────────────────────────────
def generate_dek() -> bytes:
    return os.urandom(32)


def wrap_dek(dek: bytes, kek_version: int) -> str:
    """DEK 를 지정 버전 KEK 로 암호화. AAD='dek'."""
    keks = load_keks()
    kek = keks.get(int(kek_version))
    if kek is None:
        raise CredCryptoError(f"KEK v{kek_version} 부재")
    return _aesgcm_encrypt(kek, dek, b"dek")


def unwrap_dek(wrapped: str, kek_version: int) -> bytes:
    keks = load_keks()
    kek = keks.get(int(kek_version))
    if kek is None:
        raise CredCryptoError(f"KEK v{kek_version} 부재(로테이션 시 구 KEK 보관 필요)")
    return _aesgcm_decrypt(kek, wrapped, b"dek")


# ── datasource password (DEK 로 암호화, AAD=DatasourceKey) ────────────────────
def encrypt_password(dek: bytes, plain: str, ds_key: str) -> str:
    """password 를 DEK 로 암호화. AAD=ds_key(소문자) — 암호문 다른 datasource 로 재사용 차단."""
    return _aesgcm_encrypt(dek, str(plain).encode("utf-8"), str(ds_key).strip().lower().encode("utf-8"))


def decrypt_password(dek: bytes, token: str, ds_key: str) -> str:
    return _aesgcm_decrypt(dek, token, str(ds_key).strip().lower().encode("utf-8")).decode("utf-8")
