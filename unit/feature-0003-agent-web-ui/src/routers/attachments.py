"""feature-0012 P5b Final — attachments 도메인 APIRouter (첨부파일 조회/다운로드).

uniform `import app`+`app.X` 동적참조(app 헬퍼/상수 + DI seam) → monkeypatch·override 보존.
핸들러-사용 stdlib/fastapi 심볼은 로컬 import. 순환 안전(맨 끝 include_router). 경로/메서드/응답 byte-동치.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter
from fastapi import Depends
from fastapi import Request
from fastapi.responses import JSONResponse
from typing import Any

import app

INCLUDE_ORDER = 150  # 등록 순서 고정 — 2026-07-10 현행 include 순서 스냅샷 (ITEM-05, 순서 변경 금지)
router = APIRouter()


@router.get("/api/attachments/{attachment_id}")
def get_attachment_metadata(attachment_id: int, request: Request) -> JSONResponse:
    """첨부 metadata + signed URL re-issue (사내망 다운로드 전용). D21 pending 은
    metadata 만, signed URL 미발급."""
    try:
        from web.modules import storage_minio
    except Exception as exc:
        return app._json_error(f"storage 모듈 import 실패: {exc}", 500)

    try:
        conn = app._connect_memory()
    except Exception:
        return app._json_error("db connection failed", 500)

    try:
        account, error = app._require_account(request, conn)
        if error:
            return error
        row = app._load_attachment_row(conn, attachment_id)
        if not app._account_can_access_attachment(
            conn,
            account,
            row,
            "conversation.attachment.read.own",
            "conversation.attachment.read.any",
        ):
            return app._json_error("첨부를 찾을 수 없거나 접근 권한이 없습니다.", 404)

        signed_url: str | None = None
        if not app._account_is_pending(account):
            try:
                signed_url = storage_minio.generate_presigned_get(
                    str(row.get("ObjectKey") or ""),
                    response_filename=str(row.get("OriginalFilename") or ""),
                )
            except (storage_minio.StorageConfigError, storage_minio.StorageOperationError):
                signed_url = None

        payload = app._serialize_attachment_for_api(
            row,
            include_signed_url=bool(signed_url),
            signed_url=signed_url,
        )
        # D21 metadata-only 마커 — frontend 가 사용자에게 안내.
        if app._account_is_pending(account):
            payload["bytes_access_denied"] = True
            payload["bytes_access_denied_reason"] = "승인 대기 계정은 첨부 본문을 다운로드할 수 없습니다."
        return JSONResponse(payload)
    finally:
        conn.close()

@router.get("/api/attachments/{attachment_id}/download")
def download_attachment(attachment_id: int, request: Request, version_suffix: str = "auto"):
    """TASK-0284: 첨부 본문을 web FastAPI 가 직접 프록시 스트리밍한다.

    배경: presigned(signed) URL 은 MinIO 내부 endpoint(`minio:9000`) 호스트가 박혀 외부 머신
    브라우저가 열 수 없었다(사용자 보고: 외부에서 다운로드 불가). ADR-0022 설계 의도("MinIO 는
    compose 내부망만 노출, 외부는 web 을 통해 다운로드")를 본 라우트가 구현한다 — 같은 출처(앱
    도메인)로 본문을 내려주므로 앱에 접근 가능한 외부 머신이면 다운로드된다.

    권한은 get_attachment_metadata 와 동형(`_account_can_access_attachment` own/any), 승인 대기
    계정은 본문 차단(D21). 보안: 원본 mime 대신 octet-stream + `Content-Disposition: attachment`
    + nosniff 로 inline 렌더/XSS 를 차단한다(이미지 서빙 12710 의 nosniff 선례 동형).

    REQ-20260806-attach-suffix-toggle: `version_suffix=keep|strip|force` 로 파일명의 버전
    접미사(`_v2`)를 뗄지 붙일지 고른다(기본 `auto` = v2 이상에만 부착 = 기존 동작). 규칙은 일괄 다운로드와 공용
    (`app._download_filename_with_version`)이라 같은 범위에서는 어느 버튼으로 받아도 이름이
    같다(전 버전 일괄 다운로드만 버전 구분을 위해 `force` 를 기본으로 쓴다)."""
    mode = app._normalize_version_suffix_mode(version_suffix, default="auto")
    try:
        from web.modules import storage_minio
    except Exception as exc:
        return app._json_error(f"storage 모듈 import 실패: {exc}", 500)

    try:
        conn = app._connect_memory()
    except Exception:
        return app._json_error("db connection failed", 500)

    try:
        account, error = app._require_account(request, conn)
        if error:
            return error
        # 파라미터 오류는 **인증 뒤에** 알린다 — 미인증 요청이 401 대신 400 을 받으면
        # 인증 경계보다 입력 검증이 먼저 말을 하는 셈이다(§18.8 security 패널 P3).
        if not mode:
            return app._json_error("version_suffix 는 auto, keep, strip, force 중 하나여야 합니다.", 400)
        row = app._load_attachment_row(conn, attachment_id)
        if not app._account_can_access_attachment(
            conn,
            account,
            row,
            "conversation.attachment.read.own",
            "conversation.attachment.read.any",
        ):
            return app._json_error("첨부를 찾을 수 없거나 접근 권한이 없습니다.", 404)
        if app._account_is_pending(account):
            return app._json_error("승인 대기 계정은 첨부 본문을 다운로드할 수 없습니다.", 403)
        object_key = str((row or {}).get("ObjectKey") or "")
        if not object_key:
            return app._json_error("첨부 본문을 찾을 수 없습니다.", 404)
        try:
            data = storage_minio.get_object_bytes(object_key)
        except (storage_minio.StorageConfigError, storage_minio.StorageOperationError):
            return app._json_error("첨부 본문을 가져올 수 없습니다.", 502)

        from starlette.responses import Response as _Resp
        from urllib.parse import quote as _quote
        import re as _re
        filename = str((row or {}).get("OriginalFilename") or "download")
        # 경로 성분·제어문자 제거 — ZIP 경로(`_zip_entry_name`)와 **같은 정제**를 여기서도 한다.
        # 헤더 소비자가 브라우저면 UA 가 `download` 값을 정규화해 주지만, 스크립트로 저장하는
        # 소비자에겐 그 보호가 없다(§18.8 security 패널 P3 — 방어심층 비대칭 해소).
        filename = filename.replace("\\", "/").split("/")[-1]
        filename = _re.sub(r"[\x00-\x1f\x7f]", "", filename).strip().lstrip(".") or "download"
        # attach-multi-upload: 저장 파일명은 버전 체인 정합을 위해 원본명을 승계하므로
        # (`_materialize_assistant_attachment_edits` 주석 참조 — 이름이 갈리면 체인이 분열),
        # v2 이상은 **응답 파일명에만** 버전 접미를 붙여 로컬 최신본 덮어쓰기를 막는다.
        # 그 규칙이 곧 `auto` 이며 미지정 시 기본이다 — 접미를 원치 않는 사용자는
        # `version_suffix=strip` 으로 끈다(REQ-20260806-attach-suffix-toggle).
        # 규칙 적용은 인가 통과 **후** — 이름 계산이 존재 여부를 흘리지 않는다.
        filename = app._download_filename_with_version(
            filename, int((row or {}).get("VersionNumber") or 1), mode) or "download"
        # Content-Disposition: ASCII fallback + RFC5987 비-ASCII(UTF-8) filename*.
        # REV-20260616-0291 MINOR 흡수: 따옴표 + 모든 비출력 제어문자(CR/LF 포함)를 제거해 헤더
        # 인젝션을 차단(OriginalFilename 은 업로드 시 .strip() 만 거쳐 CRLF 가 남을 수 있음).
        # filename*(아래)는 percent-encoding 이라 이미 안전하나, ascii_fallback 도 방어적으로 정제한다.
        ascii_fallback = filename.encode("ascii", "ignore").decode("ascii").replace('"', "")
        ascii_fallback = "".join(c for c in ascii_fallback if c.isprintable()).strip() or "download"
        disposition = (
            f'attachment; filename="{ascii_fallback}"; '
            f"filename*=UTF-8''{_quote(filename, safe='')}"
        )
        return _Resp(
            content=data,
            media_type="application/octet-stream",
            headers={
                "Content-Disposition": disposition,
                # 프론트는 fetch+blob 으로 저장하므로(TASK-0287) `<a download>` 이름을 스스로
                # 정해야 하고, 그러면 Content-Disposition 은 무시된다 — 두 이름이 어긋나지
                # 않도록 최종 파일명을 별도 헤더(percent-encoded UTF-8)로도 준다. 이름 규칙의
                # 권위는 서버 한 곳이고, 프론트는 버전 번호를 몰라도 된다(말풍선 칩처럼
                # version_number 가 없는 호출부가 있다).
                "X-Attachment-Download-Name": _quote(filename, safe=""),
                "X-Content-Type-Options": "nosniff",
                "Cache-Control": "private, no-store",
            },
        )
    finally:
        conn.close()

@router.get("/api/attachments/{attachment_id}/versions")
def get_attachment_versions(attachment_id: int, request: Request) -> JSONResponse:
    """TASK-0274: 첨부의 버전 체인 전체(구버전 포함) 조회.

    attachment_id 는 체인 내 어느 버전이든 가능 — 그 root 를 찾아 전체 체인을 반환한다.
    권한은 기준 첨부의 read.{own,any} 재사용(버전은 같은 conversation·account 귀속).
    각 버전에 signed_url(사내망 다운로드, pending 제외) 동봉. 응답은 VersionNumber ASC.
    """
    try:
        from web.modules import storage_minio
    except Exception as exc:
        return app._json_error(f"storage 모듈 import 실패: {exc}", 500)
    try:
        conn = app._connect_memory()
    except Exception:
        return app._json_error("db connection failed", 500)
    try:
        account, error = app._require_account(request, conn)
        if error:
            return error
        base = app._load_attachment_row(conn, attachment_id)
        if not app._account_can_access_attachment(
            conn, account, base,
            "conversation.attachment.read.own",
            "conversation.attachment.read.any",
        ):
            return app._json_error("첨부를 찾을 수 없거나 접근 권한이 없습니다.", 404)

        root_id = int(base.get("RootAttachmentId") or 0) or int(base.get("Id") or 0)
        # TASK-0277: read cutover — PG 우선(권한은 위 _account_can_access_attachment 로 이미 게이트),
        # PG read 실패 시 MySQL 폴백. REQ-20260806-attach-version-diff 에서 diff 엔드포인트와
        # **같은 체인 로더**(`_load_attachment_version_chain`)를 공유하도록 추출 — 목록과 비교가
        # 서로 다른 체인 집합을 보는 비대칭을 구조적으로 없앤다. `scope_row` 로 체인의
        # conversation/account 스코프도 데이터로 재확인한다(기준 첨부 게이트의 전제 강제).
        rows = app._load_attachment_version_chain(conn, root_id, scope_row=base)

        is_pending = app._account_is_pending(account)
        # REQ-20260806-attach-manage: 버전 행의 삭제 어포던스도 서버 판정을 따른다
        # (목록과 동일 술어 — §16.7 G6 표시-집행 정합).
        gate = _manage_gate_for_conversation(conn, account, str(base.get("ConversationId") or ""))
        versions: list[dict[str, Any]] = []
        for row in rows:
            d = dict(row)
            signed_url = None
            if not is_pending:
                try:
                    signed_url = storage_minio.generate_presigned_get(
                        str(d.get("ObjectKey") or ""),
                        response_filename=str(d.get("OriginalFilename") or ""),
                    )
                except (storage_minio.StorageConfigError, storage_minio.StorageOperationError):
                    signed_url = None
            ser = app._serialize_attachment_for_api(
                d, include_signed_url=bool(signed_url), signed_url=signed_url)
            ser["can_manage"] = bool(gate(d))
            versions.append(ser)

        # REQ-20260814-attach-version-branching: 두 번째 비교 축(**시간순**). assistant 수정본이
        # 별도 계보로 분기하므로 같은 파일명에 계보가 여럿 공존한다. `versions` 만 주면 소비자는
        # 자기 체인만 보고 "이게 이 파일의 최신" 이라고 말하게 된다 — 다른 계보에 더 나중 버전이
        # 있어도 모른다. 계보 head 를 시간순으로 함께 실어 두 축을 모두 표현할 수 있게 한다.
        lineages: list[dict[str, Any]] = []
        try:
            heads = app._load_filename_lineage_heads(
                conn, str(base.get("ConversationId") or ""), str(base.get("OriginalFilename") or ""))
            for h in heads:
                _h_root = int(h.get("RootAttachmentId") or 0) or int(h.get("Id") or 0)
                _meta = app._meta_json_to_dict(h.get("MetaJson"))
                lineages.append({
                    "root_attachment_id": _h_root,
                    "head_attachment_id": int(h.get("Id") or 0),
                    "version_number": int(h.get("VersionNumber") or 1),
                    "created_by_role": str(h.get("CreatedByRole") or "user"),
                    "is_assistant_generated": str(h.get("CreatedByRole") or "user") == "assistant",
                    "account_id": int(h.get("AccountId") or 0),
                    # 첨부 시각은 UTC 저장 — 전송도 UTC 임을 명시한다(같은 계약 공유).
                    "created_at": app._iso_utc_z(h.get("CreatedAt")),
                    "branched_from_attachment_id": int(_meta.get("branch_of_attachment_id") or 0) or None,
                    "is_current_lineage": _h_root == root_id,
                })
        except Exception:
            logging.getLogger(__name__).warning(
                "get_attachment_versions: 계보 목록 해소 실패 (id=%s) — versions 만 반환",
                attachment_id, exc_info=True)
            lineages = []

        return JSONResponse({
            "root_attachment_id": root_id,
            "versions": versions,
            # 시간순 정렬(최신 우선). 계보가 1개뿐이면 자기 자신만 들어온다.
            "lineages": lineages,
        })
    finally:
        conn.close()

# 첨부 **본문**을 싣는 응답의 공통 헤더. `download_attachment` 가 같은 이유로 쓰는 것과 동일하다 —
# 노출되는 데이터가 같은데 JSON 으로 감쌌다는 이유만으로 저장 정책이 사라지면 공용 단말의 디스크
# 캐시에 본문이 남는다(로그아웃 후 뒤로가기·URL 재입력으로 재노출, §18.8 security).
_BODY_VIEW_HEADERS = {
    "Cache-Control": "private, no-store",
    "X-Content-Type-Options": "nosniff",
}


def _version_side(row: dict[str, Any]) -> dict[str, Any]:
    """버전 한 행의 **식별·메타** 요약. `/source` 의 `version`·`versions` 와 `/diff` 의
    `from`·`to` 가 같은 형식을 쓴다.

    한 함수로 둔 이유: 프론트가 이 dict 들을 같은 헬퍼(`_versionLabel`)로 라벨링하고 같은
    `<select>` 에 넣는다. 형식이 갈리면 어느 화면에서는 "AI 수정" 이 뜨고 다른 화면에서는
    안 뜨는 비대칭이 생기며, 그 비대칭은 필드 하나가 조용히 빠지는 방식으로 나타난다
    (이 저장소가 반복 관측한 "규칙 두 벌" 결함 기전).

    **ObjectKey·서명 URL 은 싣지 않는다** — 선택기는 무엇을 고를지만 알면 되고, 다운로드
    경로는 `/versions` 가 따로 담당한다(그쪽은 버전마다 presign 을 만든다).
    """
    created = row.get("CreatedAt")
    return {
        "id": int(row.get("Id") or 0),
        "version_number": int(row.get("VersionNumber") or 1),
        "created_by_role": str(row.get("CreatedByRole") or "user"),
        "created_at": created.isoformat() if hasattr(created, "isoformat") else (
            str(created) if created else None),
        "size": int(row.get("SizeBytes") or 0),
        "sha256": str(row.get("Sha256") or ""),
        "kind": str(row.get("Kind") or ""),
        "original_filename": str(row.get("OriginalFilename") or ""),
        "is_latest": not bool(row.get("SupersededAt")),
    }


@router.get("/api/attachments/{attachment_id}/source")
def get_attachment_source(attachment_id: int, request: Request) -> JSONResponse:
    """REQ-20260807T-attach-source-view: 첨부 **한 버전의 본문 원문** 조회.

    사용자 요청: "별도로 추가된 버전이 없는 첨부파일 또한, 클릭했을 때 문서 원문이 출력되도록"
    (2026-08-07). 버전이 하나뿐인 첨부에는 비교할 짝이 없어 `/diff` 를 쓸 수 없다 — 그 엔드포인트는
    두 버전을 요구하고 `from==to` 를 400 으로 막는다(존재 여부 oracle 방지 계약의 일부).

    **버전 선택 파라미터를 두지 않는다**: 체인의 각 버전은 자기 행·자기 `Id` 를 가지므로
    (`RootAttachmentId` + `VersionNumber` 구조) 경로의 id 하나로 버전이 이미 특정된다.
    `?version=` 을 얹으면 같은 대상을 가리키는 식별 경로가 둘이 되고, 그 중 하나만 스코프 검사를
    통과하는 비대칭이 생길 수 있다. 구버전 원문은 그 버전의 id 로 호출한다.

    **체인 요약(`versions`)을 함께 싣는다** (REQ-20260813-attach-source-compare, 사용자 요청
    2026-08-13: "문서 원문 화면에서도 버전 간 비교를 수행할 수 있도록"). 원문 화면의 비교 기준
    선택기가 쓴다. `/versions` 를 따로 부르지 않는 이유는 두 가지다:
      - 그 엔드포인트는 버전마다 MinIO presign 을 만든다(다운로드용). 선택기에는 쓰이지 않는
        비용이며, 체인이 길면 왕복 1회에 presign N회가 실린다.
      - 원문 모달의 요청이 `/source` **한 번**이라는 기존 계약(테스트 A8)을 지킨다 — 왕복을
        늘리지 않고 같은 게이트 안에서 답한다.
    노출 범위는 `/versions` 응답의 **부분집합**(번호·시각·작성 주체·크기·해시)이고 서명 URL 은
    빠진다 — 이미 통과한 read 게이트가 체인 전체를 덮는다(`_load_attachment_version_chain` 의
    `scope_row` 재확인 포함).

    권한·게이트는 `/diff` 와 **동형**이다 — 본문 bytes 를 그대로 노출하기 때문이다:
      - 기준 첨부의 `conversation.attachment.read.{own,any}` 재사용 (**신규 권한 코드 0**)
      - **D21 pending 게이트**: 승인 대기 계정은 403 (metadata 조회가 아니라 **다운로드**와 동형.
        이 게이트가 없으면 원문 보기가 bytes-deny 의 우회 경로가 된다.)

    바이너리(xlsx/pdf/image/other)는 줄 단위 표시가 무의미하므로 `viewable=false` +
    메타(크기·sha256·시각·작성 주체)로 강등해 답한다 — 조용히 빈 본문을 주지 않는다.
    """
    try:
        from web.modules import storage_minio
    except Exception as exc:
        return app._json_error(f"storage 모듈 import 실패: {exc}", 500)

    try:
        conn = app._connect_memory()
    except Exception:
        return app._json_error("db connection failed", 500)
    try:
        account, error = app._require_account(request, conn)
        if error:
            return error
        base = app._load_attachment_row(conn, attachment_id)
        if not app._account_can_access_attachment(
            conn, account, base,
            "conversation.attachment.read.own",
            "conversation.attachment.read.any",
        ):
            return app._json_error("첨부를 찾을 수 없거나 접근 권한이 없습니다.", 404)
        # D21 — 원문 보기는 본문 노출이므로 다운로드와 동일 등급으로 막는다(위 docstring 참조).
        if app._account_is_pending(account):
            return app._json_error("승인 대기 계정은 첨부 본문을 볼 수 없습니다.", 403)
        # per-account rate limit — 트리거가 **목록 행 클릭**이라 마찰이 0 에 가깝고, 모달은 열 때마다
        # 재요청한다(클라이언트 캐시 없음). 다운로드는 나가는 바이트가 자연 제동을 걸지만 이 경로는
        # 앞부분만 보내므로 그 제동이 없다(§18.8 security).
        if not app._search_rate_limit_check(
            int(account.get("id") or 0), max_per_min=30, scope=app.RATE_SCOPE_ATTACHMENT_SOURCE,
        ):
            return app._json_rate_limited(
                "첨부 원문 조회가 너무 잦습니다.",
                app._rate_limit_retry_after(
                    int(account.get("id") or 0), app.RATE_SCOPE_ATTACHMENT_SOURCE),
            )

        row = base
        root_id = int(row.get("RootAttachmentId") or 0) or int(row.get("Id") or 0)
        payload: dict[str, Any] = {
            "attachment_id": int(row.get("Id") or 0),
            "root_attachment_id": root_id,
            "filename": str(row.get("OriginalFilename") or ""),
            "version": _version_side(row),
        }
        # 체인 요약 — 원문 화면의 비교 기준 선택기용(위 docstring 참조). 조회 실패는 **비교
        # 기능만 없애고 원문은 그대로 준다**(fail-soft): 원문 보기가 이 조회에 종속되면 체인
        # 쿼리 한 번의 실패가 "내용을 볼 수 없음" 으로 번진다. 프론트는 `versions` 가 2개
        # 미만이면 선택기를 숨기므로, 빈 배열이 곧 종전 동작이다.
        try:
            payload["versions"] = [
                _version_side(r)
                for r in app._load_attachment_version_chain(conn, root_id, scope_row=base)
            ]
        except Exception:
            logging.getLogger(__name__).warning(
                "get_attachment_source: version chain load failed (root=%s)", root_id,
                exc_info=True)
            payload["versions"] = []

        if str(row.get("Kind") or "") not in tuple(app._VERSION_DIFF_TEXT_KINDS):
            payload.update({"viewable": False, "reason": "binary"})
            return JSONResponse(payload, headers=_BODY_VIEW_HEADERS)

        object_key = str(row.get("ObjectKey") or "")
        if not object_key:
            # 데이터 결손을 저장소 장애(503)로 오분류하지 않는다 — `download_attachment` 와 동형.
            return app._json_error("첨부 본문을 찾을 수 없습니다.", 404)

        cap = int(app._ASSISTANT_EDIT_SIZE_CAP_BYTES)
        try:
            # **ranged read** — 화면에 앞부분(cap)만 보여 주므로 전체를 메모리로 올리지 않는다.
            raw = storage_minio.get_object_head_bytes(object_key, max_bytes=cap)
        except (storage_minio.StorageConfigError, storage_minio.StorageOperationError):
            logging.getLogger(__name__).warning(
                "get_attachment_source: object read failed (id=%s)", row.get("Id"), exc_info=True)
            # `error` 를 함께 싣는 이유: 프론트 `apiFetch` 는 non-2xx 를 throw 하고 메시지를
            # `payload.error || payload.detail || statusText` 로 고른다. 이 키가 없으면 사용자는
            # 영문 `Service Unavailable`(HTTP/2 면 빈 문자열)을 보게 되고, 렌더 쪽에 준비해 둔
            # 한국어 사유는 **도달 불가**가 된다(§18.8 ux 지적).
            payload.update({
                "viewable": False,
                "reason": "source_unavailable",
                "error": "원본 파일을 읽을 수 없어 원문을 표시하지 못했습니다.",
            })
            return JSONResponse(payload, status_code=503, headers=_BODY_VIEW_HEADERS)

        # 절단 판정은 **정본 크기**로 한다 — ranged read 는 정확히 cap 만큼 오므로
        # `len(raw) > cap` 는 영원히 거짓이 된다(무음 절단이 될 뻔한 자리).
        source_truncated = int(row.get("SizeBytes") or 0) > cap
        view = app._build_source_view(
            raw[:cap].decode("utf-8", "replace"), source_truncated=source_truncated)
        payload.update({
            "viewable": True,
            "rows": view["rows"],
            "stats": view["stats"],
            # 절단 2종을 각각 표면화한다 — 어느 쪽이 잘렸는지 모르면 사용자가 앞부분을 전체로
            # 오인한다(§16.7 G9-b, `/diff` 와 동일 계약).
            "truncated": {"source": source_truncated, "rows": bool(view["truncated"]["rows"])},
            "caps": {"source_bytes": cap, "rows": int(app._VERSION_DIFF_ROW_CAP)},
        })
        return JSONResponse(payload, headers=_BODY_VIEW_HEADERS)
    finally:
        conn.close()

@router.get("/api/attachments/{attachment_id}/diff")
def get_attachment_version_diff(attachment_id: int, request: Request) -> JSONResponse:
    """REQ-20260806-attach-version-diff: 같은 버전 체인의 **임의 두 버전** 본문 비교.

    `MetaJson.version_diff`(업로드 시점 계산분)는 **직전↔신규 1쌍**만 담으므로 v1↔v3 같은
    다단계 비교에는 답이 없다. 본 엔드포인트는 두 버전의 MinIO 원본을 그때그때 읽어
    비교한다(저장 없음 — 어떤 쌍이든 대칭적으로 답한다).

    Query:
      - `from_version`(필수), `to_version`(필수) — 같은 체인 안의 VersionNumber.
      - `context`(선택) — 변경 지점 주변 맥락 줄 수(기본 3). `full` 이면 전체 맥락.

    권한: 기준 첨부의 `conversation.attachment.read.{own,any}` 재사용 — **신규 권한 코드 0**.
    체인 밖 버전 번호는 400 이 아니라 404 로 답한다(존재 여부 oracle 방지 —
    SECURITY.md §8.2.1 의 "매칭 여부가 곧 존재 여부를 답한다" 와 같은 계열).

    **D21 pending 게이트 (필수)**: diff 행은 파일 **본문**을 그대로 담는다. 따라서 승인 대기
    계정에 대한 판정은 metadata 조회(`get_attachment_metadata` — signed URL 만 보류)가 아니라
    **본문 다운로드**(`download_attachment` — 403)와 동형이어야 한다. 이 게이트가 없으면
    diff 가 D21 bytes-deny 의 우회 경로가 된다.

    바이너리(xlsx/pdf/image/other)는 줄 diff 가 무의미하므로 `comparable=false` +
    메타 비교(크기·sha256·시각·작성 주체)로 강등해 답한다 — 조용히 빈 diff 를 주지 않는다.
    """
    try:
        from web.modules import storage_minio
    except Exception as exc:
        return app._json_error(f"storage 모듈 import 실패: {exc}", 500)

    raw_from = (request.query_params.get("from_version") or "").strip()
    raw_to = (request.query_params.get("to_version") or "").strip()
    if not raw_from or not raw_to:
        return app._json_error("from_version / to_version 이 필요합니다.", 400)
    try:
        from_version = int(raw_from)
        to_version = int(raw_to)
    except (TypeError, ValueError):
        return app._json_error("from_version / to_version 은 정수여야 합니다.", 400)
    if from_version == to_version:
        return app._json_error("서로 다른 두 버전을 지정해야 합니다.", 400)

    raw_ctx = (request.query_params.get("context") or "").strip().lower()
    if raw_ctx in ("full", "all"):
        context_lines: int | None = None
    elif raw_ctx:
        try:
            context_lines = max(0, min(200, int(raw_ctx)))
        except (TypeError, ValueError):
            return app._json_error("context 는 정수 또는 'full' 이어야 합니다.", 400)
    else:
        context_lines = app._VERSION_DIFF_CONTEXT_DEFAULT

    try:
        conn = app._connect_memory()
    except Exception:
        return app._json_error("db connection failed", 500)
    try:
        account, error = app._require_account(request, conn)
        if error:
            return error
        base = app._load_attachment_row(conn, attachment_id)
        if not app._account_can_access_attachment(
            conn, account, base,
            "conversation.attachment.read.own",
            "conversation.attachment.read.any",
        ):
            return app._json_error("첨부를 찾을 수 없거나 접근 권한이 없습니다.", 404)
        # D21 — diff 는 본문 노출이므로 다운로드와 동일 등급으로 막는다(위 docstring 참조).
        if app._account_is_pending(account):
            return app._json_error("승인 대기 계정은 첨부 본문을 비교할 수 없습니다.", 403)

        root_id = int(base.get("RootAttachmentId") or 0) or int(base.get("Id") or 0)
        chain = app._load_attachment_version_chain(conn, root_id, scope_row=base)
        by_version = {int(r.get("VersionNumber") or 1): r for r in chain}
        left = by_version.get(from_version)
        right = by_version.get(to_version)
        if not left or not right:
            return app._json_error("지정한 버전을 찾을 수 없습니다.", 404)

        payload: dict[str, Any] = {
            "root_attachment_id": root_id,
            "filename": str(right.get("OriginalFilename") or left.get("OriginalFilename") or ""),
            # 형식 정본은 모듈 레벨 `_version_side` — `/source` 의 `version`·`versions` 와 공유한다
            # (nested 사본이던 것을 REQ-20260813-attach-source-compare 에서 승격. 원문 화면의
            #  선택기가 `/source` 의 체인과 `/diff` 의 from/to 를 같은 라벨러로 다루므로, 형식이
            #  두 벌이면 필드 하나가 조용히 빠지는 방식으로 어긋난다).
            "from": _version_side(left),
            "to": _version_side(right),
        }

        text_kinds = tuple(app._VERSION_DIFF_TEXT_KINDS)
        left_kind = str(left.get("Kind") or "")
        right_kind = str(right.get("Kind") or "")
        if left_kind not in text_kinds or right_kind not in text_kinds:
            payload.update({
                "comparable": False,
                "reason": "binary",
                "identical": (str(left.get("Sha256") or "") == str(right.get("Sha256") or "")
                              and bool(left.get("Sha256"))),
            })
            return JSONResponse(payload)

        cap = int(app._ASSISTANT_EDIT_SIZE_CAP_BYTES)
        sides: dict[str, str] = {}
        truncated_sides: dict[str, bool] = {}
        for key, row in (("from", left), ("to", right)):
            try:
                raw = storage_minio.get_object_bytes(str(row.get("ObjectKey") or ""))
            except Exception:
                logging.getLogger(__name__).warning(
                    "get_attachment_version_diff: object read failed (id=%s)",
                    row.get("Id"), exc_info=True)
                # 위 `/source` 와 같은 이유로 `error` 동봉 — 503 은 apiFetch 가 throw 하므로
                # 이 키가 없으면 사용자는 영문 상태 문자열을 본다(선행 결함, 같은 cycle 에서 정정).
                payload.update({
                    "comparable": False,
                    "reason": "source_unavailable",
                    "error": "원본 파일을 읽을 수 없어 내용을 비교하지 못했습니다.",
                })
                return JSONResponse(payload, status_code=503)
            truncated_sides[key] = len(raw) > cap
            sides[key] = raw[:cap].decode("utf-8", "replace")

        view = app._build_version_diff_view(
            sides["from"],
            sides["to"],
            left_version=from_version,
            right_version=to_version,
            filename=str(payload["filename"] or "file"),
            context_lines=context_lines,
        )
        payload.update({
            "comparable": True,
            "context_lines": context_lines,
            "unified_diff": view["unified"],
            "rows": view["rows"],
            "stats": view["stats"],
            "identical": bool(view["stats"]["identical"]),
            # 절단 4종을 각각 표면화한다 — 어느 쪽이 잘렸는지 모르면 사용자가 diff 를
            # 전체로 오인한다(§16.7 G9-b). 앞의 3종은 **내용** 절단, `intraline` 은
            # **정밀도** 절단(줄 단위 차이는 온전하고 글자 단위 마크만 생략)이라 성질이 다르므로
            # 프론트 문구도 달리 간다.
            "truncated": {
                "from_source": bool(truncated_sides.get("from")),
                "to_source": bool(truncated_sides.get("to")),
                "rows": bool(view["truncated"]["rows"]),
                "intraline": bool(view["truncated"].get("intraline")),
            },
            "caps": {"source_bytes": cap, "rows": int(app._VERSION_DIFF_ROW_CAP)},
        })
        return JSONResponse(payload)
    finally:
        conn.close()

@router.delete("/api/attachments/{attachment_id}")
def delete_attachment(
    attachment_id: int,
    request: Request,
    scope: str = "version",
    account=Depends(app.get_current_account),
    conn=Depends(app.get_conn),
) -> JSONResponse:
    """첨부 soft-delete (D6 user delete_reason). MinIO 객체 실삭제는 Phase 9
    reconciliation worker 가 retention 만료 후 처리.

    REQ-20260806-attach-manage:
      - `scope=version`(기본) — 지정한 **그 버전 한 건**만. 최신본이었으면 직전
        미삭제 버전을 최신으로 승격한다(D5) — 승격하지 않으면 체인 전체가 목록에서
        사라져 "이 버전만 삭제" 가 성립하지 않는다.
      - `scope=chain` — 그 첨부가 속한 **버전 체인 전량**. 목록에서 첨부가 사라진다.

    권한은 `_account_can_manage_attachment`(D3) — 종전 `_account_can_access_attachment`
    는 그룹 멤버 전원을 통과시켜 제3자가 남의 첨부를 지울 수 있었다.
    """
    scope_norm = _normalize_scope(scope)
    if scope_norm is None:
        return app._json_error("scope 는 version 또는 chain 이어야 합니다.", 400)

    row = _load_attachment_row_mysql(conn, attachment_id)
    if not _account_can_manage_attachment(conn, account, row):
        return app._json_error("첨부를 찾을 수 없거나 삭제 권한이 없습니다.", 404)

    root_id = _root_id_of(row)
    # 삭제 UPDATE 와 승격 UPDATE 는 한 트랜잭션이어야 한다 — 사이가 벌어지면 최신본만
    # 지운 체인이 목록에서 통째로 사라지는 중간 상태가 커밋된다.
    in_tx = _begin_tx(conn)
    try:
        if scope_norm == "chain":
            targets = [
                int(r.get("Id") or 0)
                for r in _load_attachment_chain(conn, root_id, for_update=in_tx)
                if not r.get("DeletePending") and not r.get("DeletedAt")
            ]
        else:
            targets = [] if row.get("DeletePending") else [int(attachment_id)]
        targets = [t for t in targets if t > 0]

        if not targets:
            # 이미 전부 soft-deleted — idempotent 응답 (종전 단일 삭제의 already_pending 계약 보존).
            if in_tx:
                conn.rollback()
            return JSONResponse(
                {
                    "ok": True,
                    "delete_reason": str(row.get("DeleteReason") or "user"),
                    "already_pending": True,
                    "scope": scope_norm,
                    "deleted_ids": [],
                    "deleted_count": 0,
                }
            )

        before_snapshot = app._serialize_attachment_for_audit(row)
        placeholders = ",".join(["%s"] * len(targets))
        cur = conn.cursor()
        try:
            cur.execute(
                f"""
                UPDATE WebConversationAttachments
                SET DeletePending = 1, DeleteReason = 'user', DeletedAt = UTC_TIMESTAMP(6)
                WHERE Id IN ({placeholders}) AND DeletePending = 0
                """,
                tuple(targets),
            )
            updated = int(cur.rowcount or 0)
        finally:
            cur.close()

        if updated <= 0:
            if in_tx:
                conn.rollback()
            return app._json_error("삭제 처리 실패 (이미 처리됨)", 409)

        # D5 — 최신본을 지웠으면 남은 미삭제 버전 중 최신을 승격한다. chain 삭제로 남은
        # 행이 없으면 no-op(None).
        promoted_id = _promote_latest_version(conn, root_id, lock=in_tx)
        conn.commit()
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        logging.getLogger(__name__).warning(
            "delete_attachment failed (attachment_id=%s, scope=%s)", attachment_id, scope_norm,
            exc_info=True)
        return app._json_error("삭제 처리 중 오류가 발생했습니다.", 500)

    # TASK-0277: dual-write — soft-delete(DeletePending/DeletedAt) 상태를 PG 로 미러(flag-gated, fail-soft).
    # 승격으로 SupersededAt 이 바뀐 행도 함께 미러해야 PG read 경로의 목록이 어긋나지 않는다.
    _mirror_chain(conn, root_id, targets)

    # audit dispatch.
    try:
        app._audit_user_action(
            conn,
            request,
            account,
            action="attachment.delete",
            resource_type="attachment",
            resource_id=str(attachment_id),
            request_ctx={
                **before_snapshot,
                "delete_reason": "user",
                "scope": scope_norm,
                "deleted_ids": targets,
                "deleted_count": updated,
                "promoted_id": promoted_id,
            },
        )
    except Exception:
        # fail-open: attachment.delete audit dispatch 실패는 삭제 응답을 막지 않으나 가시화.
        logging.getLogger(__name__).warning(
            "delete_attachment: delete audit dispatch failed (attachment_id=%s)",
            attachment_id, exc_info=True,
        )

    return JSONResponse({
        "ok": True,
        "delete_reason": "user",
        "scope": scope_norm,
        "deleted_ids": targets,
        "deleted_count": updated,
        "promoted_id": promoted_id,
    })


@router.post("/api/attachments/{attachment_id}/restore")
def restore_attachment(
    attachment_id: int,
    request: Request,
    scope: str = "version",
    account=Depends(app.get_current_account),
    conn=Depends(app.get_conn),
) -> JSONResponse:
    """REQ-20260806-attach-manage: soft-delete 된 첨부를 retention 창 안에서 되살린다.

    복구 가능 조건 — ① `DeletePending=1` ② reconciliation worker 가 아직 실 객체를
    지우지 않음(`UploadStatus <> 'deleted'`) ③ retention 미만료
    (`DeletedAt > now - ATTACHMENT_RECON_RETENTION_DAYS`). 셋 중 하나라도 어긋나면
    그 행은 대상에서 빠지고, 대상이 하나도 없으면 409 로 사유를 알린다 — 조용히
    "성공" 을 돌려주면 사용자는 복구됐다고 믿는다.

    권한은 삭제와 동일(`_account_can_manage_attachment`). `scope` 의미도 삭제와 대칭.
    """
    scope_norm = _normalize_scope(scope)
    if scope_norm is None:
        return app._json_error("scope 는 version 또는 chain 이어야 합니다.", 400)

    row = _load_attachment_row_mysql(conn, attachment_id)
    if not _account_can_manage_attachment(conn, account, row):
        return app._json_error("첨부를 찾을 수 없거나 복구 권한이 없습니다.", 404)

    root_id = _root_id_of(row)
    in_tx = _begin_tx(conn)
    try:
        candidates = (
            _load_attachment_chain(conn, root_id, include_deleted=True, for_update=in_tx)
            if scope_norm == "chain"
            else [row]
        )
        targets = [int(r.get("Id") or 0) for r in candidates if _is_restorable(r)]
        targets = [t for t in targets if t > 0]

        if not targets:
            if in_tx:
                conn.rollback()
            return app._json_error(
                "복구할 수 있는 첨부가 없습니다 — 이미 사용 중이거나 보관 기간이 지나 삭제되었습니다.",
                409,
            )

        placeholders = ",".join(["%s"] * len(targets))
        cur = conn.cursor()
        try:
            # WHERE 절이 `_is_restorable` 의 판정을 SQL 로 한 번 더 건다 — 판정과 실행
            # 사이에 worker 가 상태를 바꿨어도 되돌리면 안 되는 행은 갱신되지 않는다.
            cur.execute(
                f"""
                UPDATE WebConversationAttachments
                SET DeletePending = 0, DeleteReason = NULL, DeletedAt = NULL
                WHERE Id IN ({placeholders})
                  AND DeletePending = 1
                  AND DeleteReason = %s
                  AND UploadStatus <> 'deleted'
                  AND DeletedAt > UTC_TIMESTAMP(6) - INTERVAL %s DAY
                """,
                (*targets, _USER_DELETE_REASON, _retention_days()),
            )
            restored = int(cur.rowcount or 0)
        finally:
            cur.close()

        if restored <= 0:
            if in_tx:
                conn.rollback()
            return app._json_error("복구 처리 실패 (이미 처리됨)", 409)

        # 되살아난 행이 체인의 최신이 될 수 있다 — 승격을 다시 계산한다.
        promoted_id = _promote_latest_version(conn, root_id, lock=in_tx)
        conn.commit()
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        logging.getLogger(__name__).warning(
            "restore_attachment failed (attachment_id=%s, scope=%s)", attachment_id, scope_norm,
            exc_info=True)
        return app._json_error("복구 처리 중 오류가 발생했습니다.", 500)

    _mirror_chain(conn, root_id, targets)

    try:
        app._audit_user_action(
            conn,
            request,
            account,
            action="attachment.restore",
            resource_type="attachment",
            resource_id=str(attachment_id),
            request_ctx={
                "conversation_id": str(row.get("ConversationId") or ""),
                "scope": scope_norm,
                "restored_ids": targets,
                "restored_count": restored,
                "promoted_id": promoted_id,
            },
        )
    except Exception:
        logging.getLogger(__name__).warning(
            "restore_attachment: restore audit dispatch failed (attachment_id=%s)",
            attachment_id, exc_info=True,
        )

    return JSONResponse({
        "ok": True,
        "scope": scope_norm,
        "restored_ids": targets,
        "restored_count": restored,
        "promoted_id": promoted_id,
    })


# ==== feature-0012 ITEM-10 p15 — app.py 에서 이동 (2종). app 전역은 app.X 동적 참조. ====

def _account_is_pending(account: dict[str, Any] | None) -> bool:
    """D21 / R-F14 — pending role 식별. application-level bytes deny 사용."""
    return app._account_role_key(account) == "pending"

def _account_can_access_attachment(
    conn,
    account: dict[str, Any] | None,
    attachment_row: dict[str, Any] | None,
    own_permission: str,
    any_permission: str | None = None,
) -> bool:
    """`_account_can_access_conversation` 의 attachment-specific 변종.

    attachment 존재 + 본인 소유 conv 인지 확인 후 own_permission 검사. any_permission
    이 있으면 conv 소유 무관 통과. soft-deleted 첨부 (DeletedAt NOT NULL) 는 거부 —
    조회는 reconciliation worker 등 운영 path 만 (이 helper 미사용).
    """
    if not account or not attachment_row:
        return False
    if attachment_row.get("DeletedAt"):
        return False
    if any_permission and app._account_has_permission(account, any_permission):
        return True
    if not app._account_has_permission(account, own_permission):
        return False
    conversation_id = str(attachment_row.get("ConversationId") or "")
    if not conversation_id:
        return False
    acct_id = int(account["id"])
    if app._conversation_owned_by_account(conn, conversation_id, acct_id):
        return True
    # feature-0009: 그룹 대화 멤버도 첨부 접근 가능 (첨부는 전원 공유, REQ-GC-R6). LLM 맥락
    # 주입은 발신자-한정(CSO F1, S3) 으로 별도 제한 — 여기는 열람/공유 경계.
    return app._account_is_conversation_member(conversation_id, acct_id)


# ==== REQ-20260806-attach-manage — 삭제(버전 선택)·복구 공통 헬퍼 ====

# 삭제/복구 scope. version = 지정한 그 버전 한 건, chain = 버전 체인 전량.
_SCOPE_VERSION = "version"
_SCOPE_CHAIN = "chain"


def _normalize_scope(scope: str | None) -> str | None:
    """scope 쿼리 정규화. 허용 밖 값은 None → caller 가 400.

    기본값을 조용히 적용하지 않는다 — 오타(`chian`)가 "그 버전만 삭제" 로 조용히
    격하되면 사용자는 전체를 지웠다고 믿는다(§16.7 G9-c 정합).
    """
    s = str(scope or _SCOPE_VERSION).strip().lower()
    return s if s in (_SCOPE_VERSION, _SCOPE_CHAIN) else None


def _load_attachment_row_mysql(conn, attachment_id: int) -> dict[str, Any] | None:
    """삭제·복구 **판정용** 단일 행 — 항상 MySQL(첨부 정본)을 읽는다.

    `app._load_attachment_row` 는 `ATTACHMENTS_READ_BACKEND=postgres`(라이브 기본)면
    PG 미러를 읽는다. 미러가 fail-soft 로 한 번 유실돼 PG 는 `delete_pending=1`, MySQL 은
    0 인 상태가 되면, 기본 경로(`scope=version`)가 그 PG 행을 보고 "이미 삭제됨"(200
    already_pending)을 돌려주면서 **실제로는 아무것도 지우지 않는다** — 사용자는 삭제됐다고
    믿는다. 인가 판정(열람 게이트)과 달리 상태 판정은 정본이어야 한다.
    """
    if not attachment_id:
        return None
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute(
            """
            SELECT
                Id, ConversationId, AccountId, ObjectKey, OriginalFilename,
                MimeType, SizeBytes, Sha256, Kind, UploadStatus, CreatedAt,
                DeletedAt, DeletePending, DeleteReason,
                RootAttachmentId, VersionNumber, CreatedByRole, SupersededAt
            FROM WebConversationAttachments
            WHERE Id = %s
            LIMIT 1
            """,
            (int(attachment_id),),
        )
        r = cur.fetchone()
        return dict(r) if r else None
    finally:
        cur.close()


def _root_id_of(row: dict[str, Any] | None) -> int:
    """버전 체인의 root id. RootAttachmentId 가 비면 그 행 자신이 root(원본)."""
    if not row:
        return 0
    return int(row.get("RootAttachmentId") or 0) or int(row.get("Id") or 0)


def _manage_gate_for_conversation(conn, account: dict[str, Any] | None, conversation_id: str):
    """삭제·복구 인가를 **대화 단위로 1회 해석**한 뒤 행 술어를 돌려준다 (D3).

    `_account_can_access_attachment`(열람 경계)와 두 곳이 다르다:

    1. **그룹 멤버 단독은 거부**. 종전엔 열람 헬퍼를 삭제에 재사용해 업로더도 대화
       소유자도 아닌 제3자가 남의 첨부를 지울 수 있었다 — ADR-20260729T163000 이
       "별도 판단 대상" 으로 이월한 미해결 이슈이며, 삭제 UI 재도입과 함께 닫는다.
    2. **soft-deleted 행도 통과**. 복구 경로가 쓰기 때문 — 열람 헬퍼는 `DeletedAt`
       이면 거부하므로 복구에 재사용할 수 없다.

    통과 조건: `upload.any` 보유(관리·보존정책 경로) OR `upload.own` 보유 + (첨부
    업로더 본인 OR 대화 소유자).

    목록 응답의 `can_manage` 표시와 실제 집행이 **같은 코드**를 공유하도록 술어를
    반환한다 (§16.7 G6 — 표시용 판정을 따로 구현하면 두 벌이 어긋난다). 대화 소유자
    조회는 여기서 1회만 수행해 목록 렌더의 N+1 을 피한다.
    """
    if not account:
        return lambda row: False
    if app._account_has_permission(account, "conversation.attachment.upload.any"):
        return lambda row: bool(row)
    if not app._account_has_permission(account, "conversation.attachment.upload.own"):
        return lambda row: False
    acct_id = int(account["id"])
    is_owner = bool(conversation_id) and app._conversation_owned_by_account(conn, conversation_id, acct_id)
    # **현재 접근 가능한 대화**여야 한다. 업로더 조건만 보면 그룹에서 kick 당한 이탈자가
    # 자기 파일을 되살리거나 지울 수 있다 — 그 방을 볼 수 없는 사람이 그 방의 내용을
    # 바꾸는 셈이다. 열람 게이트(멤버십)와 비대칭이던 부분을 닫는다.
    if not is_owner:
        try:
            can_reach = bool(conversation_id) and app._account_is_conversation_member(
                conversation_id, acct_id)
        except Exception:
            can_reach = False  # 판정 불가 → fail-closed (파괴적 경로).
        if not can_reach:
            return lambda row: False

    def _pred(row: dict[str, Any] | None) -> bool:
        if not row:
            return False
        return bool(is_owner) or int(row.get("AccountId") or 0) == acct_id

    return _pred


def _account_can_manage_attachment(
    conn,
    account: dict[str, Any] | None,
    attachment_row: dict[str, Any] | None,
) -> bool:
    """삭제·복구 공통 인가 (D3, REQ-20260806-attach-manage). 판정은
    `_manage_gate_for_conversation` 단일 정의를 쓴다."""
    if not attachment_row:
        return False
    gate = _manage_gate_for_conversation(
        conn, account, str(attachment_row.get("ConversationId") or "")
    )
    return gate(attachment_row)


def _load_attachment_chain(
    conn, root_id: int, *, include_deleted: bool = False, for_update: bool = False
) -> list[dict[str, Any]]:
    """버전 체인 전량을 VersionNumber ASC 로. 첨부 정본은 MySQL(dual-write, TASK-0279)
    이라 삭제·복구 판정은 항상 MySQL 을 읽는다(PG mirror 는 active 목록 read 전용).

    `for_update=True` 는 `FOR UPDATE` 로 체인을 잠근다 — 두 요청이 같은 체인을 동시에
    삭제/복구하면 각자 다른 '최신' 을 계산해 **두 행이 `SupersededAt=NULL`** 이 될 수
    있고, 그러면 같은 첨부가 목록에 두 번 나온다. 트랜잭션 안에서만 의미가 있다.
    """
    if not root_id:
        return []
    where_deleted = "" if include_deleted else " AND DeletedAt IS NULL"
    lock = " FOR UPDATE" if for_update else ""
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute(
            f"""
            SELECT
                Id, ConversationId, AccountId, ObjectKey, OriginalFilename,
                MimeType, SizeBytes, Sha256, Kind, UploadStatus, CreatedAt,
                DeletedAt, DeletePending, DeleteReason,
                RootAttachmentId, VersionNumber, CreatedByRole, SupersededAt
            FROM WebConversationAttachments
            WHERE (RootAttachmentId = %s OR Id = %s){where_deleted}
            ORDER BY VersionNumber ASC, Id ASC{lock}
            """,
            (int(root_id), int(root_id)),
        )
        return [dict(r) for r in (cur.fetchall() or [])]
    finally:
        cur.close()


# 복구가 허용되는 삭제 사유. `conv_soft`(대화 soft-delete cascade)는 대화 자체의 복구
# 흐름이 담당하고, `admin_purge`/`legal`(BRIEFING D6 taxonomy)은 **되돌리면 안 되는**
# 삭제다 — 사용자 회수 경로가 그것들을 되살리면 관리·법적 삭제가 무력화된다.
_USER_DELETE_REASON = "user"


def _begin_tx(conn) -> bool:
    """명시 트랜잭션 시작. 연결이 autocommit 이면 삭제 UPDATE 와 승격 UPDATE 가 별개
    커밋이 되어, 승격이 실패하면 **최신본만 지운 체인이 목록에서 통째로 사라진다**
    (목록은 `SupersededAt IS NULL` 을 보는데 그런 행이 없어진다). 두 문장을 한 트랜잭션
    으로 묶어 그 중간 상태를 없앤다.

    반환: 트랜잭션을 실제로 열었는지(드라이버 미지원·이미 진행 중이면 False — 그 경우
    종전 동작으로 떨어지되 호출측은 흐름을 바꾸지 않는다).
    """
    try:
        conn.start_transaction()
        return True
    except Exception:
        logging.getLogger(__name__).warning(
            "_begin_tx: start_transaction unavailable — falling back to autocommit semantics",
            exc_info=True)
        return False


def _retention_days() -> int:
    """reconciliation worker 와 같은 env 를 읽는다 — 두 곳이 어긋나면 UI 가 복구
    가능하다고 표시한 것을 서버가 거부하거나 그 반대가 된다."""
    import os
    try:
        return max(1, int(os.getenv("ATTACHMENT_RECON_RETENTION_DAYS") or "30"))
    except Exception:
        return 30


def _is_restorable(row: dict[str, Any] | None) -> bool:
    """retention 창 안의 **사용자 삭제** 행인가.

    세 가지를 배제한다:
      - `DeleteReason != 'user'` — `conv_soft`(대화 삭제 cascade)는 대화 복구가 담당하고,
        `admin_purge`/`legal` 은 되돌리면 안 되는 삭제다. 사용자 회수 경로가 이것들을
        되살리면 관리·법적 삭제가 무력화된다.
      - `UploadStatus == 'deleted'` — worker 가 MinIO 객체까지 지운 종착 상태라 DB
        플래그를 되돌려도 본문이 없다.
      - retention 만료분 — worker 의 다음 사이클이 곧 가져간다.
    """
    if not row:
        return False
    if not row.get("DeletePending"):
        return False
    if str(row.get("DeleteReason") or "").lower() != _USER_DELETE_REASON:
        return False
    if str(row.get("UploadStatus") or "").lower() == "deleted":
        return False
    deleted_at = row.get("DeletedAt")
    if not deleted_at:
        # DeletePending=1 인데 DeletedAt 이 비면 worker 의 만료 판정 대상이 아니다
        # (`DeletedAt IS NOT NULL` 조건). 되살릴 수 있다.
        return True
    import datetime as _dt
    try:
        dt = deleted_at if isinstance(deleted_at, _dt.datetime) else _dt.datetime.fromisoformat(str(deleted_at))
    except Exception:
        # 파싱 불가 → 만료 여부를 단정할 수 없다. **fail-closed** — 보존정책 우회 비용이
        # 데이터 회수 편익보다 크다. UPDATE WHERE 의 retention 조건이 2차 방어이므로
        # 여기서 True 를 돌려줘도 결국 막히지만, 판정과 집행이 같은 답을 내야 한다.
        logging.getLogger(__name__).warning(
            "_is_restorable: DeletedAt parse failed → fail-closed (id=%s, value=%r)",
            row.get("Id"), deleted_at)
        return False
    if dt.tzinfo is not None:
        dt = dt.replace(tzinfo=None)
    return dt > (_dt.datetime.utcnow() - _dt.timedelta(days=_retention_days()))


def _promote_latest_version(conn, root_id: int, *, lock: bool = False) -> int | None:
    """체인의 미삭제 행 중 최신(VersionNumber 최대)을 `SupersededAt=NULL` 로 승격.

    D5 — 최신본을 지우면 직전 버전이 목록의 최신이 되어야 "이 버전만 삭제" 가
    성립한다. 복구로 더 높은 버전이 되살아난 경우도 같은 계산으로 수렴한다.
    목록 SQL(`SupersededAt IS NULL`)이 **정확히 한 행**만 보도록 나머지는 스탬프를
    채운다 — 두 행이 NULL 이면 같은 첨부가 목록에 두 번 나온다.

    반환: 승격된 행 id (미삭제 행이 없으면 None — chain 삭제 후의 정상 상태).

    **예외를 삼키지 않는다.** 승격은 삭제/복구와 같은 트랜잭션의 일부이며, 여기서
    실패했는데 삭제만 커밋되면 그 체인은 목록에서 조용히 사라진다. 호출측이 rollback
    할 수 있도록 올린다.
    """
    if not root_id:
        return None
    # 체인을 잠근 채 읽는다 — 잠그지 않으면 두 요청이 각자 다른 '최신' 을 계산해 두 행이
    # `SupersededAt=NULL` 이 될 수 있고, 그러면 목록에 같은 첨부가 두 번 나온다.
    alive = [r for r in _load_attachment_chain(conn, int(root_id), for_update=bool(lock))
             if not r.get("DeletePending")]
    if not alive:
        return None
    latest = max(alive, key=lambda r: (int(r.get("VersionNumber") or 1), int(r.get("Id") or 0)))
    latest_id = int(latest.get("Id") or 0)
    if not latest_id:
        return None
    cur = conn.cursor()
    try:
        cur.execute(
            """
            UPDATE WebConversationAttachments
            SET SupersededAt = COALESCE(SupersededAt, UTC_TIMESTAMP(6))
            WHERE (RootAttachmentId = %s OR Id = %s)
              AND DeletedAt IS NULL AND Id <> %s AND SupersededAt IS NULL
            """,
            (int(root_id), int(root_id), latest_id),
        )
        # `DeletedAt IS NULL` 가드 — 그 사이 다른 트랜잭션이 이 행을 지우고 커밋했으면
        # 삭제된 행을 current 로 승격하게 된다.
        cur.execute(
            "UPDATE WebConversationAttachments SET SupersededAt = NULL "
            "WHERE Id = %s AND DeletedAt IS NULL",
            (latest_id,),
        )
    finally:
        cur.close()
    return latest_id


def _mirror_attachment_ids(conn, attachment_ids: list[int]) -> None:
    """TASK-0277 dual-write — 상태 변경분을 PG 로 미러(flag-gated, fail-soft)."""
    ids = sorted({int(i) for i in (attachment_ids or []) if i})
    if not ids:
        return
    try:
        from web.modules import attachment_pg_mirror as _apm
        _apm.mirror_attachments(conn, ids)
    except Exception:
        logging.getLogger(__name__).warning(
            "_mirror_attachment_ids: PG mirror failed (ids=%s)", ids, exc_info=True)


def _mirror_chain(conn, root_id: int, extra_ids: list[int] | None = None) -> None:
    """체인 **전량** 을 미러한다.

    `_promote_latest_version` 은 승격 행뿐 아니라 **강등 행들**(`SupersededAt` 스탬프)도
    바꾼다. 변경분만 골라 미러하면 그 강등 행이 빠져 PG 에 `superseded_at IS NULL` 이
    둘 남고, `pg_list_conversation_attachments`(PG read 가 **라이브 기본**)가 같은 첨부를
    두 줄로 반환한다 — 이후 그 행을 건드리는 write 가 나올 때까지 영구히 어긋난다.
    업로드 supersede 경로(`conversations.py` 재업로드)가 이미 같은 규약을 쓴다.
    """
    ids = list(extra_ids or [])
    try:
        ids += [int(r.get("Id") or 0) for r in _load_attachment_chain(conn, int(root_id), include_deleted=True)]
    except Exception:
        logging.getLogger(__name__).warning(
            "_mirror_chain: chain reload failed (root_id=%s)", root_id, exc_info=True)
    _mirror_attachment_ids(conn, ids)
