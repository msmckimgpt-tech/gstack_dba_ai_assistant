import asyncio
import os
import re
import time
import uuid
from typing import Any
from urllib.parse import urlparse

from fastapi import Body, FastAPI, HTTPException
from fastapi.responses import JSONResponse
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

BROWSER_HEADLESS = os.getenv("BROWSER_HEADLESS", "1").strip().lower() in ("1", "true", "yes")
BROWSER_TIMEOUT_MS = int(os.getenv("BROWSER_TIMEOUT_MS", "15000"))
BROWSER_ALLOW_FILE = os.getenv("BROWSER_ALLOW_FILE", "0").strip().lower() in ("1", "true", "yes")
SCREENSHOT_DIR = os.getenv("BROWSER_SCREENSHOT_DIR", "/shared/out/browser")

app = FastAPI(title="browser-controller")

_playwright = None
_browser = None
_sessions: dict[str, dict[str, Any]] = {}
_sessions_lock = asyncio.Lock()


def _safe_url(url: str) -> str:
    url = str(url or "").strip()
    if not url:
        raise HTTPException(status_code=400, detail="url required")
    parsed = urlparse(url)
    if parsed.scheme in ("http", "https"):
        return url
    if parsed.scheme == "file" and BROWSER_ALLOW_FILE:
        return url
    raise HTTPException(status_code=400, detail="unsupported url scheme")


def _ensure_dir(path: str) -> None:
    if path:
        os.makedirs(path, exist_ok=True)


def _session_payload(session_id: str) -> dict[str, Any]:
    return {"session_id": session_id}


def _get_session(session_id: str) -> dict[str, Any]:
    session = _sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="session not found")
    return session


def _filter_headers(value: Any) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    allowed = {"x-forwarded-for", "user-agent", "accept-language"}
    headers: dict[str, str] = {}
    for key, val in value.items():
        name = str(key or "").strip().lower()
        if name and name in allowed and val is not None:
            headers[name] = str(val)
    return headers


@app.on_event("startup")
async def startup() -> None:
    global _playwright, _browser
    _ensure_dir(SCREENSHOT_DIR)
    _playwright = await async_playwright().start()
    _browser = await _playwright.chromium.launch(headless=BROWSER_HEADLESS)


@app.on_event("shutdown")
async def shutdown() -> None:
    global _playwright, _browser
    for session_id in list(_sessions.keys()):
        try:
            await close_session(session_id)
        except Exception:
            pass
    if _browser:
        await _browser.close()
    if _playwright:
        await _playwright.stop()


@app.get("/healthz")
async def healthz() -> JSONResponse:
    return JSONResponse({"ok": True})


@app.post("/session")
async def create_session(payload: dict[str, Any] = Body(default_factory=dict)) -> JSONResponse:
    if _browser is None:
        raise HTTPException(status_code=500, detail="browser not ready")
    headers = _filter_headers(payload.get("headers"))
    ip_override = str(payload.get("ip", "")).strip()
    if ip_override and "x-forwarded-for" not in headers:
        headers["x-forwarded-for"] = ip_override
    session_id = uuid.uuid4().hex[:16]
    context = await _browser.new_context(
        extra_http_headers=headers or None,
        ignore_https_errors=True,
    )
    page = await context.new_page()
    async with _sessions_lock:
        _sessions[session_id] = {
            "context": context,
            "page": page,
            "created_at": time.time(),
            "lock": asyncio.Lock(),
        }
    return JSONResponse(_session_payload(session_id))


async def close_session(session_id: str) -> None:
    session = _get_session(session_id)
    async with session["lock"]:
        try:
            await session["page"].close()
        except Exception:
            pass
        try:
            await session["context"].close()
        except Exception:
            pass
    async with _sessions_lock:
        _sessions.pop(session_id, None)


@app.post("/close")
async def close_endpoint(payload: dict[str, Any]) -> JSONResponse:
    session_id = str(payload.get("session_id", "")).strip()
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id required")
    await close_session(session_id)
    return JSONResponse({"session_id": session_id, "ok": True})


@app.post("/goto")
async def goto(payload: dict[str, Any]) -> JSONResponse:
    session_id = str(payload.get("session_id", "")).strip()
    url = _safe_url(payload.get("url"))
    timeout_ms = int(payload.get("timeout_ms") or BROWSER_TIMEOUT_MS)
    session = _get_session(session_id)
    async with session["lock"]:
        try:
            resp = await session["page"].goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
        except PlaywrightTimeoutError:
            raise HTTPException(status_code=408, detail="navigation timeout")
    status = resp.status if resp else None
    title = await session["page"].title()
    return JSONResponse({"session_id": session_id, "url": url, "status": status, "title": title})


@app.post("/click")
async def click(payload: dict[str, Any]) -> JSONResponse:
    session_id = str(payload.get("session_id", "")).strip()
    selector = str(payload.get("selector", "")).strip()
    if not selector:
        raise HTTPException(status_code=400, detail="selector required")
    timeout_ms = int(payload.get("timeout_ms") or BROWSER_TIMEOUT_MS)
    session = _get_session(session_id)
    async with session["lock"]:
        try:
            await session["page"].click(selector, timeout=timeout_ms)
        except PlaywrightTimeoutError:
            raise HTTPException(status_code=408, detail="click timeout")
    return JSONResponse({"session_id": session_id, "ok": True})


@app.post("/type")
async def type_text(payload: dict[str, Any]) -> JSONResponse:
    session_id = str(payload.get("session_id", "")).strip()
    selector = str(payload.get("selector", "")).strip()
    text = str(payload.get("text", ""))
    if not selector:
        raise HTTPException(status_code=400, detail="selector required")
    timeout_ms = int(payload.get("timeout_ms") or BROWSER_TIMEOUT_MS)
    clear_first = bool(payload.get("clear", True))
    delay_ms = int(payload.get("delay_ms") or 0)
    session = _get_session(session_id)
    async with session["lock"]:
        try:
            if clear_first:
                await session["page"].fill(selector, "", timeout=timeout_ms)
            if text:
                await session["page"].type(selector, text, delay=delay_ms, timeout=timeout_ms)
        except PlaywrightTimeoutError:
            raise HTTPException(status_code=408, detail="type timeout")
    return JSONResponse({"session_id": session_id, "ok": True})


@app.post("/set_value")
async def set_value(payload: dict[str, Any]) -> JSONResponse:
    session_id = str(payload.get("session_id", "")).strip()
    selector = str(payload.get("selector", "")).strip()
    value = str(payload.get("value", payload.get("text", "")))
    if not selector:
        raise HTTPException(status_code=400, detail="selector required")
    timeout_ms = int(payload.get("timeout_ms") or BROWSER_TIMEOUT_MS)
    session = _get_session(session_id)
    async with session["lock"]:
        try:
            await session["page"].fill(selector, value, timeout=timeout_ms)
        except PlaywrightTimeoutError:
            raise HTTPException(status_code=408, detail="set_value timeout")
    return JSONResponse({"session_id": session_id, "ok": True})


@app.post("/eval")
async def eval_script(payload: dict[str, Any]) -> JSONResponse:
    session_id = str(payload.get("session_id", "")).strip()
    script = str(payload.get("script", payload.get("expression", payload.get("text", ""))))
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id required")
    if not script:
        raise HTTPException(status_code=400, detail="script required")
    timeout_ms = int(payload.get("timeout_ms") or BROWSER_TIMEOUT_MS)
    session = _get_session(session_id)
    async with session["lock"]:
        try:
            result = await asyncio.wait_for(session["page"].evaluate(script), timeout=timeout_ms / 1000)
        except asyncio.TimeoutError:
            raise HTTPException(status_code=408, detail="eval timeout")
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"eval error: {exc}")
    return JSONResponse({"session_id": session_id, "result": result})


@app.post("/press")
async def press_key(payload: dict[str, Any]) -> JSONResponse:
    session_id = str(payload.get("session_id", "")).strip()
    key = str(payload.get("key", "")).strip()
    selector = str(payload.get("selector", "")).strip()
    if not key:
        raise HTTPException(status_code=400, detail="key required")
    timeout_ms = int(payload.get("timeout_ms") or BROWSER_TIMEOUT_MS)
    session = _get_session(session_id)
    async with session["lock"]:
        try:
            if selector:
                await session["page"].press(selector, key, timeout=timeout_ms)
            else:
                await session["page"].keyboard.press(key)
        except PlaywrightTimeoutError:
            raise HTTPException(status_code=408, detail="press timeout")
    return JSONResponse({"session_id": session_id, "ok": True})


@app.post("/hover")
async def hover(payload: dict[str, Any]) -> JSONResponse:
    session_id = str(payload.get("session_id", "")).strip()
    selector = str(payload.get("selector", "")).strip()
    if not selector:
        raise HTTPException(status_code=400, detail="selector required")
    timeout_ms = int(payload.get("timeout_ms") or BROWSER_TIMEOUT_MS)
    session = _get_session(session_id)
    async with session["lock"]:
        try:
            await session["page"].hover(selector, timeout=timeout_ms)
        except PlaywrightTimeoutError:
            raise HTTPException(status_code=408, detail="hover timeout")
    return JSONResponse({"session_id": session_id, "ok": True})


@app.post("/mousedown")
async def mouse_down(payload: dict[str, Any]) -> JSONResponse:
    session_id = str(payload.get("session_id", "")).strip()
    selector = str(payload.get("selector", "")).strip()
    button = str(payload.get("button", "left")).strip() or "left"
    timeout_ms = int(payload.get("timeout_ms") or BROWSER_TIMEOUT_MS)
    session = _get_session(session_id)
    async with session["lock"]:
        try:
            if selector:
                await session["page"].hover(selector, timeout=timeout_ms)
            await session["page"].mouse.down(button=button)
        except PlaywrightTimeoutError:
            raise HTTPException(status_code=408, detail="mousedown timeout")
    return JSONResponse({"session_id": session_id, "ok": True})


@app.post("/mouseup")
async def mouse_up(payload: dict[str, Any]) -> JSONResponse:
    session_id = str(payload.get("session_id", "")).strip()
    selector = str(payload.get("selector", "")).strip()
    button = str(payload.get("button", "left")).strip() or "left"
    timeout_ms = int(payload.get("timeout_ms") or BROWSER_TIMEOUT_MS)
    session = _get_session(session_id)
    async with session["lock"]:
        try:
            if selector:
                await session["page"].hover(selector, timeout=timeout_ms)
            await session["page"].mouse.up(button=button)
        except PlaywrightTimeoutError:
            raise HTTPException(status_code=408, detail="mouseup timeout")
    return JSONResponse({"session_id": session_id, "ok": True})


@app.post("/scroll")
async def scroll(payload: dict[str, Any]) -> JSONResponse:
    session_id = str(payload.get("session_id", "")).strip()
    delta_x = int(payload.get("delta_x") or 0)
    delta_y = int(payload.get("delta_y") or 0)
    session = _get_session(session_id)
    async with session["lock"]:
        await session["page"].mouse.wheel(delta_x, delta_y)
    return JSONResponse({"session_id": session_id, "ok": True, "delta_x": delta_x, "delta_y": delta_y})

@app.post("/wait_for")
async def wait_for(payload: dict[str, Any]) -> JSONResponse:
    session_id = str(payload.get("session_id", "")).strip()
    selector = str(payload.get("selector", "")).strip()
    timeout_ms = int(payload.get("timeout_ms") or BROWSER_TIMEOUT_MS)
    session = _get_session(session_id)
    async with session["lock"]:
        try:
            if selector:
                await session["page"].wait_for_selector(selector, timeout=timeout_ms)
            else:
                await session["page"].wait_for_timeout(timeout_ms)
        except PlaywrightTimeoutError:
            raise HTTPException(status_code=408, detail="wait timeout")
    return JSONResponse({"session_id": session_id, "ok": True})


@app.post("/text")
async def get_text(payload: dict[str, Any]) -> JSONResponse:
    session_id = str(payload.get("session_id", "")).strip()
    selector = str(payload.get("selector", "")).strip()
    if not selector:
        raise HTTPException(status_code=400, detail="selector required")
    timeout_ms = int(payload.get("timeout_ms") or BROWSER_TIMEOUT_MS)
    session = _get_session(session_id)
    async with session["lock"]:
        try:
            if selector.lower() in ("title", "head > title"):
                text = await session["page"].title()
            else:
                await session["page"].wait_for_selector(selector, timeout=timeout_ms)
                text = await session["page"].text_content(selector)
        except PlaywrightTimeoutError:
            raise HTTPException(status_code=408, detail="text timeout")
    return JSONResponse({"session_id": session_id, "text": text or ""})


@app.post("/html")
async def get_html(payload: dict[str, Any]) -> JSONResponse:
    session_id = str(payload.get("session_id", "")).strip()
    session = _get_session(session_id)
    async with session["lock"]:
        html = await session["page"].content()
    return JSONResponse({"session_id": session_id, "html": html})


@app.post("/screenshot")
async def screenshot(payload: dict[str, Any]) -> JSONResponse:
    session_id = str(payload.get("session_id", "")).strip()
    full_page = bool(payload.get("full_page", True))
    path = str(payload.get("path", "")).strip()
    if not path:
        ts = time.strftime("%Y%m%d_%H%M%S")
        path = os.path.join(SCREENSHOT_DIR, f"{session_id}_{ts}.png")
    if not path.startswith("/"):
        path = os.path.join(SCREENSHOT_DIR, path)
    _ensure_dir(os.path.dirname(path))
    session = _get_session(session_id)
    async with session["lock"]:
        await session["page"].screenshot(path=path, full_page=full_page)
    return JSONResponse({"session_id": session_id, "path": path})
