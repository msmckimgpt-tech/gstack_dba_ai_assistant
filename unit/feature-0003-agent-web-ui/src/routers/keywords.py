"""feature-0012 P5b Final — keywords 도메인 APIRouter (410 stub: Keyword Management 제거됨).

router 추출 파이프라인의 첫 proof(가장 trivial — 인증·의존 없음, _json_error 만 app 에서 import).
경로/메서드/응답(410 {"error": ...})은 app.py 정의와 byte-동일 — route-parity 골든 불변.
"""
from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app import _json_error

INCLUDE_ORDER = 110  # 등록 순서 고정 — 2026-07-10 현행 include 순서 스냅샷 (ITEM-05, 순서 변경 금지)
router = APIRouter()


@router.get("/api/keywords")
def list_keywords_removed(*_args, **_kwargs) -> JSONResponse:
    return _json_error("Keyword Management는 제거되었습니다.", 410)


@router.post("/api/keywords")
def upsert_keyword_removed(*_args, **_kwargs) -> JSONResponse:
    return _json_error("Keyword Management는 제거되었습니다.", 410)


@router.delete("/api/keywords/{keyword_id}")
def delete_keyword_removed(keyword_id: int) -> JSONResponse:
    _ = keyword_id
    return _json_error("Keyword Management는 제거되었습니다.", 410)


@router.get("/api/keywords/categories")
def keyword_categories_removed() -> JSONResponse:
    return _json_error("Keyword Management는 제거되었습니다.", 410)
