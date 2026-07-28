"""web_context — app.py 에서 추출한 leaf helper (feature-0012 P5b Final).

P5b 의 목표는 28K-line app.py 모놀리스를 도메인 router + 공유 컨텍스트 모듈로 분할하는 것이다.
본 모듈은 그 첫 공유-컨텍스트 조각으로, **app-internal 의존이 전혀 없는 순수 leaf helper** 만
담는다.

INVARIANT: 본 모듈은 `from app import` 를 **절대 포함하지 않는다**(단방향 app → web_context
edge 만 유지 → 순환 import 불가). stdlib-only 로 유지한다. app.py 는 본 심볼들을 다시
`from web_context import ...` 로 재가져와 모듈 전역에 rebind 한다 — 따라서 app.py 내 기존
호출부(bare name)와 테스트의 `monkeypatch.setattr(app, ...)` 가 모두 그대로 동작한다(behavior-neutral).
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import ipaddress
import json
import logging
from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
import secrets
from typing import Any, Iterable
import re
import sys

from fastapi import Request

# model-access-rbac(2026-07-28): 모델 접근 권한 코드 namespace 의 SSOT. `shared/` 는 web_context 를
# import 하지 않으므로 단방향(web_context → shared) 이고 순환이 없다 — 기존 shared 소비 패턴과 동일.
from shared import model_catalog

# app.py 의 AGENT_MODE(L91)와 동일 표현식의 env-mirror — web_context 를 app-free 로 유지하기
# 위함(_parse_trusted_proxies 의 prod/staging fail-loud 분기가 참조). 둘 다 import 시점에 같은
# 환경변수를 읽어 동일 값을 갖는다(파생 상수, 결정적). app 의 startup-validation 블록은 app 의
# AGENT_MODE 를 계속 사용한다.
AGENT_MODE = os.getenv("AGENT_MODE", "").strip().lower()


def _sanitize_session_id(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_-]", "", value or "")
    if cleaned:
        return cleaned[:64]
    return ""


def _hash_session_token(token: str) -> str:
    return hashlib.sha256(str(token or "").encode("utf-8")).hexdigest()


# ── feature-0023 (REQ-20260722-conversation-api-access): Bearer API 토큰 ───────────
def _sanitize_api_token(value: str) -> str:
    """API 토큰 정규화. url-safe 문자([A-Za-z0-9_-])만 허용, 128자 상한.

    발급 CLI 는 `matk_` + secrets.token_urlsafe(...) 로 이 charset 만 생성하므로
    정상 토큰에는 no-op 이고, garbage/injection 입력만 걸러낸다(세션 쿠키
    `_sanitize_session_id` 와 동형 — 단 API 토큰은 더 길어 128자 허용)."""
    cleaned = re.sub(r"[^A-Za-z0-9_-]", "", value or "")
    return cleaned[:128]


def _extract_bearer_token(request: Request) -> str:
    """`Authorization: Bearer <token>` 헤더에서 토큰 추출·정규화. 없거나 형식 불일치면 ''."""
    raw = str(request.headers.get("authorization", "") or "")
    if not raw:
        return ""
    parts = raw.split(None, 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return ""
    return _sanitize_api_token(parts[1].strip())


def _parse_token_scopes(raw) -> list[str] | None:
    """WebApiTokens.Scopes(콤마구분 권한 접두 allowlist) 파싱.

    NULL/빈 문자열 → None (= scope 무제한, 서비스 계정 권한 전체). 그 외 → 정규화된
    접두 리스트(예: ["conversation.", "product.access."]). 접두가 '.' 로 끝나면 그
    네임스페이스 전체를 허용(conversation. → conversation.*)."""
    if not raw:
        return None
    items = [s.strip() for s in str(raw).split(",")]
    items = [s for s in items if s]
    return items or None


def _permission_in_token_scopes(permission: str, scopes: list[str]) -> bool:
    """permission 코드가 토큰 scope allowlist 중 하나에 매칭되면 True.

    - 정확 일치(`conversation.ask` == `conversation.ask`)
    - 네임스페이스 접두 일치(scope 가 '.' 로 끝나면 startswith): `conversation.` 은
      `conversation.ask`/`conversation.create`/… 전부 허용.

    ⚠️ 이 allowlist 는 positive 필터일 뿐 최종 결정이 아니다 — `_account_permissions` 가
    이 위에 **절대 denylist**(`_api_token_permission_denied`)를 AND 로 얹어, allowlist 를
    통과하더라도 `*.any`·관리 네임스페이스는 무조건 차단한다(REV-20260722 HIGH-1)."""
    for s in scopes:
        if not s:
            continue
        if permission == s:
            return True
        if s.endswith(".") and permission.startswith(s):
            return True
    return False


# feature-0023 (REV-20260722 HIGH-1/HIGH-2): API 토큰 인증의 **절대 denylist**.
# scope allowlist·서비스 계정 권한과 무관하게 항상 차단한다 — "관리 콘솔/교차계정 절대 불가"를
# scope 문자열이 아니라 코드 구조로 못박는다. allowlist 가 `conversation.` 이라 통과시킨
# `conversation.list.any`·`conversation.archive.read.any`(group=audit) 같은 교차계정/관리
# 코드를 여기서 무조건 죽인다. scope=None(빈 토큰)이어도 이 floor 는 항상 적용된다.
_API_TOKEN_HARD_DENY_PREFIXES = (
    "console.", "audit.", "account.", "role.", "permission",
    "system.", "system", "quota.", "insight.", "datasource.",
    "metadata.", "kb.", "graph.",
    # product 는 접근(product.access.*)만 허용하고 관리(manage/read/create/delete)는 차단.
    "product.manage", "product.read", "product.create", "product.delete",
)
# 토큰 Scopes 가 NULL/빈 값일 때 적용할 **안전 기본 allowlist**(fail-closed — 무제한 금지).
#
# feature-0023 conversation-quality-controls(2026-07-28): `folder.` 추가 — 외부 AI 가 대화 품질을
# 조정하는 축 중 하나가 **폴더별 커스텀 지침**(feature-0024, ask 시 `compose_system_prompt` 에
# 주입되는 시스템 프롬프트)이기 때문이다(사용자 결정 — 조정 범위 최대). 안전성 근거:
#   - `folder.*` 는 `folder.list.own` / `folder.manage.own` **2개뿐이고 둘 다 `.own`** 이다
#     (`folder.*.any` 는 feature-0024 privacy 슬라이스에서 폐지 — 크로스-계정 폴더 노출 차단).
#   - 폴더 스토어가 owner-scope 를 강제하고 `restore_folders` IDOR 도 봉인돼 있어, 이 접두가
#     여는 표면은 **토큰 계정 자신의 폴더**로 닫혀 있다.
#   - 아래 `_api_token_permission_denied` 의 `.any` 절대 차단은 그대로 얹히므로, 훗날 누군가
#     `folder.*.any` 를 되살려도 토큰 경로에서는 여전히 죽는다(방어 이중화).
# 이 상수는 **Scopes 가 비어 있는 토큰**에만 적용된다 — 이미 발급돼 `conversation.,product.access.`
# 가 저장된 토큰은 영향받지 않는다(무회귀). 기존 토큰에 폴더 축을 열려면 재발급이 필요하다.
_API_TOKEN_SAFE_DEFAULT_SCOPES = ("conversation.", "product.access.", "folder.")


def _api_token_permission_denied(code: str) -> bool:
    """api_token 인증이 절대 exercise 못 하는 권한(관리/교차계정)이면 True.

    - `*.any` 로 끝나는 모든 교차계정 권한(다른 계정 대화 열람/삭제/감사 등).
    - `_API_TOKEN_HARD_DENY_PREFIXES` 로 시작하는 관리 네임스페이스."""
    if code.endswith(".any"):
        return True
    for p in _API_TOKEN_HARD_DENY_PREFIXES:
        if code.startswith(p):
            return True
    return False


_TrustedNetwork = ipaddress.IPv4Network | ipaddress.IPv6Network


def _parse_trusted_proxies(raw: str) -> tuple[_TrustedNetwork, ...]:
    items: list[_TrustedNetwork] = []
    bad: list[str] = []
    for token in (raw or "").split(","):
        token = token.strip()
        if not token:
            continue
        try:
            items.append(ipaddress.ip_network(token, strict=False))
        except ValueError:
            bad.append(token)
    if bad:
        if AGENT_MODE in {"prod", "staging"}:
            raise RuntimeError(
                f"WEB_TRUSTED_PROXIES: invalid CIDR(s) in {AGENT_MODE}: {bad}"
            )
        print(
            f"[startup] WARNING: WEB_TRUSTED_PROXIES contains invalid CIDR(s) (skipped): {bad}",
            file=sys.stderr,
        )
    return tuple(items)


WEB_TRUSTED_PROXIES = _parse_trusted_proxies(os.getenv("WEB_TRUSTED_PROXIES", ""))


def _is_trusted_proxy(host: str) -> bool:
    if not host or not WEB_TRUSTED_PROXIES:
        return False
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False
    return any(ip in network for network in WEB_TRUSTED_PROXIES)


def _get_client_ip(request: Request) -> str:
    direct_ip = (request.client.host if request.client else "") or ""
    if direct_ip and _is_trusted_proxy(direct_ip):
        forwarded = request.headers.get("x-forwarded-for", "").strip()
        if forwarded:
            first = forwarded.split(",")[0].strip()
            try:
                ipaddress.ip_address(first)
            except ValueError:
                return direct_ip
            return first
    return direct_ip


# ── ITEM-10 inc3 (parallel-work-structure): 세션 쿠키 + RBAC 권한 카탈로그 ──
# app.py 에서 byte-동치 이동. 순수(app 의존 0 — conn 은 인자 주입). 소비처는 app.py 상단
# rebind 로 기존 이름 유지(routers 의 app.X 동적참조·테스트 monkeypatch 보존).

SESSION_COOKIE = "mysql_ai_session"

PERMISSION_DEFINITIONS = (
    {
        "code": "console.access",
        "label": "관리 콘솔 접근",
        "description": "관리 콘솔 화면에 접근할 수 있다.",
        "group": "console",
    },
    {
        "code": "console.manage",
        "label": "관리 콘솔 수정",
        "description": "관리 콘솔에서 변경 작업을 수행할 수 있다.",
        "group": "console",
    },
    {
        # TASK-0136 (#11): LLM 토큰/비용 사용량 조회. 운영·비용 민감 정보 → admin 한정
        # (admin seed = set(PERMISSION_CODES) 로 자동 부여, operator/sales/pending 미부여).
        # perm-category-hier(Critical §12.3, 2026-07-14): 관리 콘솔 '감사' 카테고리의 'LLM 사용량' 탭
        # 조회 권한이므로 group 을 console→audit 로 재배치(표시 분류만 — code·enforcement 불변).
        "code": "console.usage.read",
        "label": "LLM 사용량 조회",
        "description": "LLM 토큰 사용량/비용 집계를 조회할 수 있다 (운영자 전용).",
        "group": "audit",
    },
    {
        # TASK-AIOPS: AI 운영 관제 패널(관리 콘솔 > 감사 > AI 운영 현황) 조회 권한. 운영 민감
        # 정보(워커 상태·provider 헬스·AI 활동 계측)라 admin 한정 — admin seed(=set(PERMISSION_CODES))
        # 자동 부여 + 아래 _ensure_seed_roles catchup 으로 기존 admin row backfill.
        # operator/sales/dba/pending 미부여 (least-privilege).
        # perm-category-hier(2026-07-14): '감사' 카테고리의 'AI 운영 현황' 탭 조회 권한이므로
        # group 을 console→audit 로 재배치(표시 분류만 — code·enforcement 불변).
        "code": "console.aiops.read",
        "label": "AI 운영 현황 조회",
        "description": "AI 운영 관제 패널(워커 상태·provider 헬스·AI 활동 계측)을 조회할 수 있다 (운영자 전용).",
        "group": "audit",
    },
    {
        # TASK-0228: insight-worker 가 생성한 schema/table 분석(fact/rag/fingerprint)을
        # 접근 가능 데이터베이스(DB) 단위로 초기화(삭제)한다. 잘못 분석된 내용을 되돌릴 수단.
        # **파괴적** — audit.purge 와 동급으로 admin 한정 (admin seed = set(PERMISSION_CODES)
        # 자동 부여, operator/sales/pending 미부여). dry-run 미리보기 + typed-confirm + self-audit.
        # perm-category-hier(2026-07-14): 실행 표면이 제품 상세(insight-reset 버튼,
        # routers/admin_products.py)이므로 group 을 console→product 로 재배치 — '제품' 카테고리의
        # 작동 권한(표시 분류만, code·enforcement 불변).
        "code": "insight.reset",
        "label": "insight 분석 초기화",
        "description": "접근 가능 데이터베이스 단위로 insight 분석 결과(fact/rag/fingerprint)를 삭제할 수 있다. 다음 worker cycle 에 자동 재분석된다. 시작/완료는 self-audit 으로 기록된다 (운영자 전용).",
        "group": "product",
    },
    # perm-category-hier(Critical §12.3, 사용자 승인 A안 2026-07-14): 관리 콘솔 좌측 nav 카테고리
    # (계정/제품/감사/지식베이스/시스템) 단위의 최상위 '접근'(=카테고리 조회 게이트) 권한 5종.
    # 카테고리 내 모든 권한(탭 조회·추가/수정/삭제·승인/작동)은 이 접근 권한 하위로 종속된다
    # (UI 계층 admin.js PERMISSION_DEPENDENCIES + 탭 노출 ADMIN_TAB_CATEGORY_ACCESS AND 게이트).
    # 백엔드 엔드포인트 enforcement 는 기존(console.access + 세부 권한) 유지 — 접근 권한은 nav
    # 노출·부여 계층 규율이다. 기존 배포는 _backfill_console_category_access_v1 1회 backfill 로
    # 접근 무손실(console.access + 카테고리 내 세부 권한 보유 principal 에 자동 부여).
    {
        "code": "console.account.access",
        "label": "계정 접근",
        "description": "관리 콘솔의 '계정' 카테고리(계정·역할 탭)에 접근할 수 있다. 카테고리 최상위 조회 게이트 — 계정/역할/LLM 사용 한도의 세부 권한은 이 권한 하위로 종속된다.",
        "group": "account",
    },
    {
        "code": "account.read",
        "label": "계정 조회",
        "description": "계정 목록과 상세 정보를 조회할 수 있다.",
        "group": "account",
    },
    {
        "code": "account.update",
        "label": "계정 수정",
        "description": "계정 상태를 수정하는 요청을 보낼 수 있다.",
        "group": "account",
    },
    {
        "code": "account.delete",
        "label": "계정 삭제",
        "description": "계정을 소프트 삭제할 수 있다.",
        "group": "account",
    },
    {
        "code": "account.activate",
        "label": "계정 활성화",
        "description": "비활성 계정을 다시 활성화할 수 있다.",
        "group": "account",
    },
    {
        "code": "account.deactivate",
        "label": "계정 비활성화",
        "description": "계정 로그인을 차단할 수 있다.",
        "group": "account",
    },
    {
        "code": "account.role.assign",
        "label": "역할 부여/변경",
        "description": "계정의 primary role을 변경할 수 있다.",
        "group": "account",
    },
    {
        "code": "account.permission.override.manage",
        "label": "권한 override 관리",
        "description": "계정별 권한 override를 설정할 수 있다.",
        "group": "account",
    },
    {
        "code": "role.read",
        "label": "역할 조회",
        "description": "역할 목록과 권한 배치를 조회할 수 있다.",
        "group": "role",
    },
    {
        "code": "role.create",
        "label": "역할 생성",
        "description": "새 역할을 생성할 수 있다.",
        "group": "role",
    },
    {
        "code": "role.update",
        "label": "역할 수정",
        "description": "역할의 표시명, 설명, 상태를 수정할 수 있다.",
        "group": "role",
    },
    {
        "code": "role.delete",
        "label": "역할 삭제",
        "description": "미사용 역할을 삭제할 수 있다.",
        "group": "role",
    },
    {
        "code": "role.permission.manage",
        "label": "역할 권한 배치",
        "description": "역할에 부여할 권한을 수정할 수 있다.",
        "group": "role",
    },
    {
        # TASK-20260623T030418-quota-rbac-permission (REQ-20260623-0332, AC-0610):
        # LLM 토큰 사용 한도 전용 권한 — 역할별 기본·계정별 특수 한도의 "조회". console.usage.read
        # (사용량/비용 *집계* 조회)와 별개로, 한도 *설정값* 의 열람을 분리 위임한다.
        # quota.read 가 그룹 게이트(console.access 하위)이며, 한도 섹션 표시·직렬화 노출의 기준.
        "code": "quota.read",
        "label": "LLM 사용 한도 조회",
        "description": "역할별 기본 / 계정별 특수 LLM 토큰 사용 한도를 조회할 수 있다.",
        "group": "quota",
    },
    {
        # TASK-20260623T030418-quota-rbac-permission (AC-0610): 한도 "조절"(설정·해제).
        # 조회(quota.read) 선행 — 조회 없이 조절 불가(PERMISSION_DEPENDENCIES quota.manage→quota.read).
        "code": "quota.manage",
        "label": "LLM 사용 한도 조절",
        "description": "역할별 기본 / 계정별 특수 LLM 토큰 사용 한도를 설정하거나 해제할 수 있다. 조회 권한이 선행되어야 한다.",
        "group": "quota",
    },
    {
        # perm-category-hier(2026-07-14): '지식베이스' 카테고리(메타데이터·그래프 뷰 탭) 최상위 접근 게이트.
        "code": "console.kb.access",
        "label": "지식베이스 접근",
        "description": "관리 콘솔의 '지식베이스' 카테고리(메타데이터·그래프 뷰 탭)에 접근할 수 있다. 카테고리 최상위 조회 게이트 — 메타데이터 관리/검수·그래프 뷰의 세부 권한은 이 권한 하위로 종속된다.",
        "group": "kb",
    },
    {
        # TASK-20260623T090440-sample-feedback-curation (ROADMAP dba-ai-nl2sql ITEM-03, AC-0612):
        # 피드백 → 샘플쿼리 KB 환류 flywheel 의 검수 권한. 사용자 답변 피드백(👍/👎/"샘플 등록")으로
        # 적재된 sample_feedback(pending) 큐를 검토해 sample_queries(approved)로 승급(promote)하거나
        # 거부(reject)할 수 있다. 승급은 KB(검색 정확도)에 직접 영향 → poisoning 방어상 명시 검수만
        # 허용(자동학습 금지). 도메인 전문가/검수자 한정 권한 — console.access 하위(관리 콘솔 진입 필요).
        # admin seed(=set(PERMISSION_CODES)) 자동 보유. operator/sales/pending 미부여(least-privilege).
        "code": "kb.sample.curate",
        "label": "샘플 검수/승급",
        "description": "답변 피드백으로 적재된 샘플쿼리 후보(pending)를 검토해 KB(sample_queries)로 승급하거나 거부할 수 있다. 승급은 검색 정확도에 직접 영향하므로 명시 검수만 허용된다 (도메인 전문가/검수자 전용).",
        "group": "kb",
    },
    {
        # TASK-20260624-item11-metadata-glossary-enum (ROADMAP dba-ai-nl2sql ITEM-11 MVP-1):
        # 메타데이터 거버넌스 — 용어사전(kb_glossary) / ENUM 코드사전(enum_dictionary) 의 수동
        # 등록·편집·삭제 권한. 등록 내용은 질문/스키마 매칭 시 프롬프트에 주입되어 **검색·답변
        # 정확도에 직접 영향**(KB poisoning 면) → 명시 권한 보유자만 편집(자동학습 없음). 도메인
        # 전문가/큐레이터 한정. console.access 하위(관리 콘솔 진입 필요). admin seed(=set(PERMISSION_CODES))
        # 자동 보유 + 기존 admin row 는 _ensure_seed_roles catchup 으로 retroactive 부여.
        # operator/sales/pending 미부여(least-privilege).
        "code": "kb.ingest.manual",
        "label": "메타데이터 관리 (전체 묶음)",
        "description": "메타데이터 탭의 편집 기능(용어사전·ENUM·테이블 설명·컬럼 설명 관리)을 한 번에 부여하는 묶음 권한이다(개별 metadata.*.manage 로 세분 부여 가능). 그래프 뷰 조회(metadata.graph.read)는 별도 최상위 탭으로 분리되어 이 묶음에 포함되지 않으며, 그래프 뷰 접근은 개별 부여한다(graph-perm-split 2026-07-13).",
        "group": "kb",
    },
    # graph-panel-perms(task4, Critical §12.3): 메타데이터 탭 세부 권한 — 기존 단일 `kb.ingest.manual`
    # 묶음을 기능별로 분리(B안, 사용자 결정 2026-07-01)해 용어사전/ENUM/테이블/컬럼 관리와 그래프 뷰 조회를
    # 개별 위임 가능하게 한다. 하위호환: `kb.ingest.manual` 보유자는 _apply_permission_overrides 의
    # 함의(_METADATA_MANUAL_IMPLIES)로 편집 4종을 effective 로 자동 보유 → 기존 배포 무손실(비파괴·가역).
    # 모두 console.access 하위(관리 콘솔 진입 필요). admin seed(=set(PERMISSION_CODES)) 자동 보유 + 기존
    # admin row 는 _ensure_seed_roles catchup 으로 retroactive 부여. operator/sales/pending 미부여(least-privilege).
    #
    # graph-perm-split(Critical §12.3, 사용자 결정 2026-07-13): 그래프 뷰가 별도 최상위 탭(feature-0016 §45)으로
    #   분리됨에 따라 metadata.graph.read 를 위 함의(_METADATA_MANUAL_IMPLIES)에서 제거해 "메타데이터 관리"
    #   묶음과 권한도 분리한다. 편집 4종(glossary/enum/table/column)만 묶음이 함의하고, 그래프 뷰 조회는
    #   독립 권한이 된다. 기존 배포에서 묶음 보유로 그래프에 접근하던 principal 은 _backfill_graph_perm_split_v1
    #   1회 backfill(멱등 guard)로 metadata.graph.read 를 명시 부여받아 접근을 잃지 않는다(B안 = 접근 보존).
    # perm-atomic-split(Critical §12.3, 사용자 승인 2026-07-15): 사전 4종의 묶음 `.manage` 를
    #   원자 단위 {read(조회)/create(추가)/update(수정)/delete(삭제)} 로 분리. `.manage` 는 레거시
    #   묶음으로 코드·함의(_PERMISSION_BUNDLE_IMPLIES)만 유지하고 권한 grid 에서는 숨긴다
    #   (LEGACY_BUNDLE_PERMISSIONS — 기존 grant 하위호환·신규 부여는 원자 단위만).
    {
        "code": "metadata.glossary.manage",
        "label": "용어사전 관리",
        "description": "[레거시 묶음] 용어사전 조회/추가/수정/삭제를 한 번에 부여한다. 신규 부여는 원자 단위(metadata.glossary.read/create/update/delete)를 사용한다.",
        "group": "kb",
    },
    {
        "code": "metadata.glossary.read",
        "label": "용어사전 조회",
        "description": "용어사전(도메인 용어↔정의) 항목과 유사어 참조를 조회할 수 있다. 용어사전 서브탭 진입 게이트.",
        "group": "kb",
    },
    {
        "code": "metadata.glossary.create",
        "label": "용어사전 추가",
        "description": "용어사전 항목을 신규 등록할 수 있다. 등록 내용은 질문/스키마 매칭 시 프롬프트에 주입되어 답변 정확도에 직접 영향한다.",
        "group": "kb",
    },
    {
        "code": "metadata.glossary.update",
        "label": "용어사전 수정",
        "description": "용어사전 항목과 유사어 참조를 수정할 수 있다(AI 자동완성 제안 포함). 답변 정확도에 직접 영향한다.",
        "group": "kb",
    },
    {
        "code": "metadata.glossary.delete",
        "label": "용어사전 삭제",
        "description": "용어사전 항목을 삭제할 수 있다.",
        "group": "kb",
    },
    {
        "code": "metadata.enum.manage",
        "label": "ENUM 코드사전 관리",
        "description": "[레거시 묶음] ENUM 코드사전 조회/추가/수정/삭제를 한 번에 부여한다. 신규 부여는 원자 단위(metadata.enum.read/create/update/delete)를 사용한다.",
        "group": "kb",
    },
    {
        "code": "metadata.enum.read",
        "label": "ENUM 코드사전 조회",
        "description": "ENUM 코드사전(컬럼 코드↔라벨) 항목을 조회할 수 있다. ENUM 서브탭 진입 게이트.",
        "group": "kb",
    },
    {
        "code": "metadata.enum.create",
        "label": "ENUM 코드사전 추가",
        "description": "ENUM 코드사전 항목을 신규 등록할 수 있다. 등록 내용은 질문/스키마 매칭 시 프롬프트에 주입되어 답변 정확도에 직접 영향한다.",
        "group": "kb",
    },
    {
        "code": "metadata.enum.update",
        "label": "ENUM 코드사전 수정",
        "description": "ENUM 코드사전 항목을 수정할 수 있다(AI 자동완성 제안 포함).",
        "group": "kb",
    },
    {
        "code": "metadata.enum.delete",
        "label": "ENUM 코드사전 삭제",
        "description": "ENUM 코드사전 항목을 삭제할 수 있다.",
        "group": "kb",
    },
    {
        "code": "metadata.table.manage",
        "label": "테이블 설명 관리",
        "description": "[레거시 묶음] 테이블 설명 조회/추가/수정/삭제·스키마 골격 가져오기를 한 번에 부여한다. 신규 부여는 원자 단위(metadata.table.read/create/update/delete)를 사용한다.",
        "group": "kb",
    },
    {
        "code": "metadata.table.read",
        "label": "테이블 설명 조회",
        "description": "테이블 설명 항목을 조회할 수 있다. 테이블 설명 서브탭 진입 게이트.",
        "group": "kb",
    },
    {
        "code": "metadata.table.create",
        "label": "테이블 설명 추가",
        "description": "테이블 설명을 신규 등록할 수 있다. 스키마 골격 가져오기(부트스트랩)는 추가+수정 권한을 함께 요구한다.",
        "group": "kb",
    },
    {
        "code": "metadata.table.update",
        "label": "테이블 설명 수정",
        "description": "테이블 설명을 수정할 수 있다(AI 자동완성·부트스트랩 설명 생성·그래프 관계 큐레이션 포함).",
        "group": "kb",
    },
    {
        "code": "metadata.table.delete",
        "label": "테이블 설명 삭제",
        "description": "테이블 설명 항목을 삭제할 수 있다.",
        "group": "kb",
    },
    {
        "code": "metadata.column.manage",
        "label": "컬럼 설명 관리",
        "description": "[레거시 묶음] 컬럼 설명 조회/추가/수정/삭제를 한 번에 부여한다. 신규 부여는 원자 단위(metadata.column.read/create/update/delete)를 사용한다.",
        "group": "kb",
    },
    {
        "code": "metadata.column.read",
        "label": "컬럼 설명 조회",
        "description": "컬럼 설명 항목을 조회할 수 있다. 컬럼 설명 서브탭 진입 게이트.",
        "group": "kb",
    },
    {
        "code": "metadata.column.create",
        "label": "컬럼 설명 추가",
        "description": "컬럼 설명을 신규 등록할 수 있다. 등록 내용은 질문/스키마 매칭 시 프롬프트에 주입되어 답변 정확도에 직접 영향한다.",
        "group": "kb",
    },
    {
        "code": "metadata.column.update",
        "label": "컬럼 설명 수정",
        "description": "컬럼 설명을 수정할 수 있다(AI 자동완성 제안 포함).",
        "group": "kb",
    },
    {
        "code": "metadata.column.delete",
        "label": "컬럼 설명 삭제",
        "description": "컬럼 설명 항목을 삭제할 수 있다.",
        "group": "kb",
    },
    {
        "code": "metadata.graph.read",
        "label": "그래프 뷰 조회",
        "description": "지식베이스 그래프 뷰 탭(테이블/컬럼/관계/용어 탐색·검색)을 조회하고 AI 능동 분석 결과·진행 상태를 열람할 수 있다. 별도 최상위 탭으로 '메타데이터 관리' 묶음과 독립 부여된다(graph-perm-split 2026-07-13). 읽기 중심 탐색 권한 — AI 능동 분석 '실행'은 하위 권한 metadata.graph.analyze 로 분리된다(graph-analyze-perm 2026-07-14).",
        "group": "kb",
    },
    {
        # graph-analyze-perm(Critical §12.3, 사용자 결정 2026-07-14): 그래프 뷰의 AI 능동 분석 '실행'을
        #   조회(metadata.graph.read)에서 분리한 하위 권한. 노드 단위(POST /graph/analyze)·DB(스키마) 단위
        #   (POST /graph/analyze-schema) 능동 분석 트리거를 게이트한다. 분석은 LLM 을 호출하고 KB(노드 분석
        #   결과·역할 분류)를 갱신하며 비용을 유발하는 특권 동작이라 조회와 분리(least-privilege). 조회 상태·결과
        #   열람은 graph.read 유지. UI 종속(admin.js PERMISSION_DEPENDENCIES)은 graph.read 를 부모로 둔다
        #   (조회 없이 실행 무의미 — progressive disclosure). admin seed(=set(PERMISSION_CODES)) 자동 보유 +
        #   기존 admin row 는 _ensure_seed_roles catchup 으로 retroactive 부여(필수 — 미보정 시 기존 admin 이
        #   능동 분석 버튼을 잃는다). operator/sales/pending 미부여. graph.read 보유자에게 일괄 backfill 하지
        #   않는다(A안 = 최소권한, 명시 부여 — 요청 취지 "실행 권한 분리 + 무권한 시 버튼 미표시").
        "code": "metadata.graph.analyze",
        "label": "그래프 AI 능동 분석 실행",
        "description": "그래프 뷰에서 AI 능동 분석(노드 단위·DB 스키마 단위)을 실행할 수 있다. 실행은 LLM 을 호출해 테이블/컬럼/관계를 자동 분석하고 지식베이스를 갱신하며 비용을 유발하므로, 그래프 뷰 조회(metadata.graph.read)와 분리된 실행 전용 권한이다. 이 권한이 없으면 능동 분석 버튼·메뉴가 표시되지 않는다.",
        "group": "kb",
    },
    {
        # 용어사전 대화 자율등록(0021): 대화 답변에서 LLM 이 추론한 용어 후보의 검토/큐레이션 권한.
        # 하이브리드 자동승급 — 고신뢰도는 자동 등록(source='auto', 되돌리기 가능), 저신뢰도는
        # 검토 큐(glossary_feedback.status='pending')에 적재된다. 이 권한 보유자는 큐를 검토해
        # 용어사전(kb_glossary)으로 승급(promote)하거나 거부(reject·되돌리기)할 수 있다. 승급/자동등록은
        # 검색·답변 정확도에 직접 영향(poisoning 면) → 검수자 한정. admin seed(=set(PERMISSION_CODES))
        # 자동 보유 + 기존 admin row 는 _ensure_seed_roles catchup 으로 retroactive 부여. operator/sales/
        # pending 미부여(least-privilege). kb.sample.curate(샘플 검수)와 동급 큐레이션 권한.
        "code": "kb.glossary.curate",
        "label": "용어사전 검수/승급",
        "description": "대화에서 자동 제안된 용어 후보(검토 큐)를 검토해 용어사전으로 승급하거나 거부(자동 등록분 되돌리기)할 수 있다. 승급·자동 등록은 답변 정확도에 직접 영향하므로 명시 검수만 허용된다 (도메인 전문가/검수자 전용).",
        "group": "kb",
    },
    {
        # ENUM 코드사전 대화 자율수집(0039): 대화 답변에서 LLM 이 추론한 (table.column) 코드↔라벨 후보의
        # 검토/큐레이션 권한. 하이브리드 자동승급 — 고신뢰도는 자동 등록(source='auto', 되돌리기 가능),
        # 저신뢰도는 검토 큐(enum_feedback.status='pending')에 적재된다. 이 권한 보유자는 큐를 검토해
        # ENUM 코드사전(enum_dictionary)으로 승급(promote)하거나 거부(reject·되돌리기)할 수 있다. 승급/
        # 자동등록은 검색·답변 정확도에 직접 영향(poisoning 면) → 검수자 한정. kb.glossary.curate(용어
        # 검수)와 동급 큐레이션 권한. admin seed(=set(PERMISSION_CODES)) 자동 보유 + 기존 admin row 는
        # _ensure_seed_roles catchup 으로 retroactive 부여. operator/sales/pending 미부여(least-privilege).
        "code": "kb.enum.curate",
        "label": "ENUM 코드사전 검수/승급",
        "description": "대화에서 자동 제안된 ENUM 코드↔라벨 후보(검토 큐)를 검토해 ENUM 코드사전으로 승급하거나 거부(자동 등록분 되돌리기)할 수 있다. 승급·자동 등록은 답변 정확도에 직접 영향하므로 명시 검수만 허용된다 (도메인 전문가/검수자 전용).",
        "group": "kb",
    },
    {
        "code": "conversation.create",
        "label": "대화 생성",
        "description": "새 대화를 생성할 수 있다.",
        "group": "conversation_own",
    },
    {
        "code": "conversation.ask",
        "label": "대화 요청 실행",
        "description": "자신의 대화에 새 요청을 보낼 수 있다.",
        "group": "conversation_own",
    },
    {
        "code": "conversation.list.own",
        "label": "내 대화 목록 조회",
        "description": "자신의 대화 목록을 볼 수 있다.",
        "group": "conversation_own",
    },
    {
        "code": "conversation.list.any",
        "label": "전체 대화 목록 조회",
        "description": "모든 계정의 대화 목록을 볼 수 있다.",
        "group": "conversation_any",
    },
    {
        "code": "conversation.read.own",
        "label": "내 대화 내용 조회",
        "description": "자신의 대화 내용과 진행 상태를 볼 수 있다.",
        "group": "conversation_own",
    },
    {
        "code": "conversation.read.any",
        "label": "전체 대화 내용 조회",
        "description": "모든 계정의 대화 내용과 진행 상태를 볼 수 있다.",
        "group": "conversation_any",
    },
    {
        "code": "conversation.file.read.own",
        "label": "내 대화 파일 조회",
        "description": "자신의 대화 결과 파일을 내려받을 수 있다.",
        "group": "conversation_own",
    },
    {
        "code": "conversation.file.read.any",
        "label": "전체 대화 파일 조회",
        "description": "모든 계정의 대화 결과 파일을 내려받을 수 있다.",
        "group": "conversation_any",
    },
    {
        "code": "conversation.rename.own",
        "label": "내 대화 제목 변경",
        "description": "자신의 대화 제목을 변경할 수 있다.",
        "group": "conversation_own",
    },
    {
        "code": "conversation.rename.any",
        "label": "전체 대화 제목 변경",
        "description": "모든 계정의 대화 제목을 변경할 수 있다.",
        "group": "conversation_any",
    },
    {
        "code": "conversation.delete.own",
        "label": "내 대화 삭제",
        "description": "자신의 대화를 삭제할 수 있다.",
        "group": "conversation_own",
    },
    {
        "code": "conversation.delete.any",
        "label": "전체 대화 삭제",
        "description": "모든 계정의 대화를 삭제할 수 있다.",
        "group": "conversation_any",
    },
    {
        # TASK-0273: "삭제" 가 soft-archive(보관)로 전환됨에 따라, 보관된 대화를 오용 방지
        # 목적으로 조회하는 전용 권한(감사). 일반 대화 읽기(conversation.read.any)와 분리.
        # perm-category-hier(2026-07-14): 유일한 표면이 관리 콘솔 '감사 > 보관 대화' 탭이므로
        # group 을 conversation_any→audit 로 재배치 — '감사' 카테고리의 탭 조회 권한
        # (표시 분류만, code·enforcement 불변).
        "code": "conversation.archive.read.any",
        "label": "보관 대화 조회",
        "description": "모든 계정의 보관된(삭제 처리된) 대화를 오용 방지 목적으로 조회할 수 있다.",
        "group": "audit",
    },
    {
        "code": "conversation.cancel.own",
        "label": "내 대화 중단",
        "description": "자신의 처리 중 대화를 중단할 수 있다.",
        "group": "conversation_own",
    },
    {
        "code": "conversation.cancel.any",
        "label": "전체 대화 중단",
        "description": "모든 계정의 처리 중 대화를 중단할 수 있다.",
        "group": "conversation_any",
    },
    {
        "code": "conversation.finalize.own",
        "label": "내 대화 즉시답변",
        "description": "자신의 처리 중 대화에 즉시답변을 요청할 수 있다.",
        "group": "conversation_own",
    },
    {
        "code": "conversation.finalize.any",
        "label": "전체 대화 즉시답변",
        "description": "모든 계정의 처리 중 대화에 즉시답변을 요청할 수 있다.",
        "group": "conversation_any",
    },
    {
        "code": "conversation.share.create",
        "label": "대화 공유 링크 생성",
        "description": "자신의 대화를 anonymous 접근 가능한 공유 링크로 발급하거나 취소할 수 있다.",
        "group": "conversation_own",
    },
    {
        # feature-0009-group-conversation (CSO F2/AR-1): 멤버는 대화 전체(권한 멤버가
        # 생성한 datasource 쿼리 결과·SQL 포함)를 열람하므로, 초대 자체가 데이터 노출
        # 행위다. owner 만(또는 본 권한 보유자) 멤버를 관리할 수 있게 게이트한다.
        "code": "conversation.member.manage",
        "label": "그룹 대화 멤버 관리",
        "description": "자신이 소유한 그룹 대화에 멤버를 초대하거나 제거할 수 있다. 초대된 멤버는 대화 전체(쿼리 결과 포함)를 열람하게 되므로, 초대는 데이터 노출 행위다.",
        "group": "conversation_own",
    },
    {
        "code": "conversation.duplicate.own",
        "label": "내 대화 복사",
        "description": "자신이 소유한 대화의 메시지/첨부/SQL 결과 전체를 본 계정 소유의 새 대화로 복제할 수 있다.",
        "group": "conversation_own",
    },
    {
        "code": "conversation.duplicate.any",
        "label": "전체 대화 복사",
        "description": "타 사용자가 소유한 대화까지 본 계정 소유의 새 대화로 복제할 수 있다.",
        "group": "conversation_any",
    },
    # TASK-0094 Sprint 1 Phase 3 (REQ-20260521-0001, Critical §12.3): 첨부 기능 RBAC.
    # BRIEFING §5.2 1~4 row — Cycle 0 의 upload / read 권한 4 코드. group="conversation"
    # (대화 흐름의 일부). attachment group 은 TASK-0161 에서 execute_sql_on.* 제거 후
    # 현재 비어 있다(권한 0 — admin.js 가 빈 group 자동 제외). D21 (R-F14): pending 은
    # read.own 만 — bytes download 는 Phase 5 의
    # `/api/attachments/{id}/content` endpoint 에서 application-level deny.
    {
        "code": "conversation.attachment.upload.own",
        "label": "내 대화 첨부 업로드",
        "description": "자신의 대화에 파일 (CSV/XLSX/PDF/이미지) 을 첨부할 수 있다. MIME / size cap 이 적용된다.",
        "group": "conversation_own",
    },
    {
        # TASK-0161: enforce 됨(_account_can_access_attachment, 업로드 엔드포인트가 권위적 게이트)이나
        # composer 가 비소유 대화 업로드를 차단해 UI 진입점이 없는 *의도적 latent* admin 역량.
        # 거짓 컨트롤 아님 — UI 신설은 product 결정 시에만(관리자가 타 계정 대화에 콘텐츠 주입은 민감).
        "code": "conversation.attachment.upload.any",
        "label": "전체 대화 첨부 업로드",
        "description": "모든 계정의 대화에 첨부를 업로드할 수 있다. 운영자 한정.",
        "group": "conversation_any",
    },
    {
        "code": "conversation.attachment.read.own",
        "label": "내 대화 첨부 조회",
        "description": "자신의 대화에 첨부된 파일 metadata + 본문 (사내망 signed URL 다운로드) 을 조회할 수 있다. pending 계정은 metadata 만 (D21 — bytes 는 승인 후).",
        "group": "conversation_own",
    },
    {
        "code": "conversation.attachment.read.any",
        "label": "전체 대화 첨부 조회",
        "description": "모든 계정의 대화 첨부를 조회할 수 있다. 운영자 한정.",
        "group": "conversation_any",
    },
    # feature-0024-conversation-folders: 대화 폴더(프로젝트) 권한. 폴더는 **엄격한 개인**
    # 오버레이라 own 권한만 둔다(folder.*.any 크로스-계정 권한 폐지 — 프라이버시 수정).
    {
        "code": "folder.list.own",
        "label": "내 폴더 조회",
        "description": "자신의 대화 폴더 트리를 볼 수 있다.",
        "group": "conversation_own",
    },
    {
        "code": "folder.manage.own",
        "label": "내 폴더 관리",
        "description": "자신의 대화 폴더를 만들고 이름변경·삭제·이동하고, 접근 가능한 대화를 자신의 폴더에 배정할 수 있다.",
        "group": "conversation_own",
    },
    # TASK-0161: attachment.execute_sql_on.own/.any 제거 (거짓 컨트롤).
    #   TASK-0094 Sprint 1 Phase 12 가 이를 defense-in-depth 의 RBAC 층으로 정의했으나
    #   enforce 가 한 번도 배선되지 않아(권한 체크 호출처 0) 관리 권한 그리드의 두 체크박스가
    #   무동작이었다 — 끄더라도 첨부 sandbox SQL 이 차단되지 않아 잘못된 보안 안심을 줌.
    #   첨부 sandbox SQL 의 *실제* 게이트는: (1) tools._ACTIVE_SCHEMA_ALLOWLIST(요청별 계정-
    #   스코프 allowlist, TASK-0132 IDOR fix) + (2) agent_ro/attachment_reader DB 유저 최소권한
    #   + (3) sql_guard AST 가드. 이 권한 제거 후에도 위 3중 방어선은 그대로 유효(런타임
    #   동작 무변경 — 교차계정 경로는 이미 계정-스코프 allowlist 가 차단). 기존 DB
    #   WebRolePermissions 행은 _cleanup_deprecated_role_permissions 가 멱등 정리한다.
    # TASK-0288: 제품 권한을 read/manage 2단으로 분리(사용자 결정 2026-06-16).
    # `product.read` = 관리 콘솔에서 제품 구성(목록·접근DB·바인딩) **조회**.
    # `product.manage` = 제품 구성 **수정**(생성/삭제/스키마/프롬프트). manage ⊇ read (superset).
    # 작업 화면에서 제품으로 요청을 보내는 권한은 별개 축 — 동적 `product.access.<key>`
    # (group='product_access'). 두 축은 enforcement·권한 편집기 그룹 모두 분리한다.
    {
        # perm-category-hier(2026-07-14): '제품' 카테고리(제품·데이터소스 탭) 최상위 접근 게이트.
        "code": "console.product.access",
        "label": "제품 접근",
        "description": "관리 콘솔의 '제품' 카테고리(제품·데이터소스 탭)에 접근할 수 있다. 카테고리 최상위 조회 게이트 — 제품/데이터소스의 세부 권한은 이 권한 하위로 종속된다.",
        "group": "product",
    },
    {
        "code": "product.read",
        "label": "제품 조회",
        "description": "관리 콘솔에서 제품(Product) 구성(목록·접근 DB·데이터소스 바인딩 현황)을 조회할 수 있다.",
        "group": "product",
    },
    {
        # perm-atomic-split(2026-07-15): 레거시 묶음 — 코드·함의 유지, grid 숨김. 신규 부여는 원자 단위.
        "code": "product.manage",
        "label": "제품 관리",
        "description": "[레거시 묶음] 제품 조회/생성/수정/삭제를 한 번에 부여한다. 신규 부여는 원자 단위(product.read/create/update/delete)를 사용한다.",
        "group": "product",
    },
    {
        "code": "product.create",
        "label": "제품 생성",
        "description": "제품(Product)을 신규 생성할 수 있다.",
        "group": "product",
    },
    {
        "code": "product.update",
        "label": "제품 수정",
        "description": "제품 구성(기본 정보·아이콘·접근 DB 스키마·데이터소스 바인딩·DB 규칙·AI 분류 제안 반영·제품 프롬프트 생성)을 수정할 수 있다.",
        "group": "product",
    },
    {
        "code": "product.delete",
        "label": "제품 삭제",
        "description": "제품을 삭제할 수 있다.",
        "group": "product",
    },
    {
        "code": "system_prompt.manage.role.any",
        "label": "역할/계정 시스템 프롬프트 관리",
        "description": "모든 역할 또는 다른 계정의 시스템 프롬프트를 수정할 수 있다. 본인 계정의 프롬프트는 이 권한 없이도 수정 가능하다.",
        "group": "product",
    },
    # TASK-0288 (REQ-20260616-0288, Critical §12.3): 데이터소스 전용 권한 2건.
    # 기존엔 datasource 조회/관리가 console.access / console.manage 만으로 게이팅돼,
    # 콘솔 진입권만 있으면 datasource 목록(좌표·바인딩 현황)이 무조건 노출되고 탭도
    # 숨길 수 없었다(전용 권한 부재). read/manage 2단 분리 — `.read` 는 목록·구성 조회,
    # `.manage` 는 생성/수정/삭제/연결테스트. admin auto-grant(set(PERMISSION_CODES)) +
    # _ensure_seed_roles catchup(아래)으로 기존 배포 admin 역할 backfill.
    {
        "code": "datasource.read",
        "label": "데이터소스 조회",
        "description": "등록된 데이터소스 목록과 구성(엔진/호스트/바인딩 현황, 비밀번호 제외)을 조회할 수 있다.",
        "group": "datasource",
    },
    {
        # perm-atomic-split(2026-07-15): 레거시 묶음 — 코드·함의 유지, grid 숨김. 신규 부여는 원자 단위.
        "code": "datasource.manage",
        "label": "데이터소스 관리",
        "description": "[레거시 묶음] 데이터소스 조회/생성/수정/삭제/연결 테스트를 한 번에 부여한다. 신규 부여는 원자 단위(datasource.read/create/update/delete/test)를 사용한다.",
        "group": "datasource",
    },
    {
        "code": "datasource.create",
        "label": "데이터소스 생성",
        "description": "데이터소스를 신규 등록할 수 있다(자격증명 암호화 저장).",
        "group": "datasource",
    },
    {
        "code": "datasource.update",
        "label": "데이터소스 수정",
        "description": "데이터소스 구성(좌표·라벨·자격증명)을 수정할 수 있다.",
        "group": "datasource",
    },
    {
        "code": "datasource.delete",
        "label": "데이터소스 삭제",
        "description": "데이터소스를 삭제할 수 있다.",
        "group": "datasource",
    },
    {
        # 연결 테스트 = 작동 권한(좌표/자격증명 검증 프로브 — 상태 변경 없음). 작업 화면
        # 데이터소스 '연결 테스트' 버튼(ds-conn-test)도 본 권한을 사용한다.
        "code": "datasource.test",
        "label": "데이터소스 연결 테스트",
        "description": "등록된 데이터소스에 연결 테스트(프로브)를 실행할 수 있다. 구성 변경 없이 연결성만 검증한다.",
        "group": "datasource",
    },
    # TASK-0073 Phase A3 (REQ-20260519-0001, Critical §12.3): audit 권한 4건.
    # `.own` 은 모든 role (dba 포함) auto-grant — 본인이 actor 인 audit row 조회(TASK-0293 Actor-only).
    # `.any` 는 admin/dba — 전체 계정 audit row 조회 (`.any` superset semantics 정합).
    # `.export` 는 admin/dba — CSV / JSON dump 가능 (PII bulk export).
    # `.purge` 는 admin only — retention 초과 chunked PK 삭제 (자가 audit 동반).
    {
        # perm-category-hier(2026-07-14): '감사' 카테고리(감사 로그·보관 대화·LLM 사용량·AI 운영 현황
        # 4개 탭) 최상위 접근 게이트. 4개 탭의 조회 권한(audit.read.own/any·conversation.archive.read.any·
        # console.usage.read·console.aiops.read)이 전부 이 권한 하위로 종속된다.
        "code": "console.audit.access",
        "label": "감사 접근",
        "description": "관리 콘솔의 '감사' 카테고리(감사 로그·보관 대화·LLM 사용량·AI 운영 현황 탭)에 접근할 수 있다. 카테고리 최상위 조회 게이트 — 각 탭의 조회/내보내기/삭제 권한은 이 권한 하위로 종속된다.",
        "group": "audit",
    },
    {
        "code": "audit.read.own",
        "label": "내 감사 로그 조회",
        "description": "자신이 actor 인 audit 이벤트 또는 자신을 target 으로 한 admin 이벤트를 조회할 수 있다.",
        "group": "audit",
    },
    {
        "code": "audit.read.any",
        "label": "전체 감사 로그 조회",
        "description": "모든 계정의 audit 이벤트를 조회할 수 있다 (PII 노출 — 관리 정책 기반).",
        "group": "audit",
    },
    {
        "code": "audit.export",
        "label": "감사 로그 CSV/JSON 내보내기",
        "description": "audit 이벤트를 CSV / JSON 으로 dump 할 수 있다. 감사 외부 검토용. masked field 정책은 변경되지 않음.",
        "group": "audit",
    },
    {
        "code": "audit.purge",
        "label": "감사 로그 retention 삭제",
        "description": "retention 초과 audit 이벤트를 chunked PK 삭제할 수 있다. 시작/완료 이벤트는 self-audit 으로 기록된다.",
        "group": "audit",
    },
    # TASK-0095 (REQ-20260521-0002, Major §12.3): GLOBAL system prompt layer.
    # `settings` 그룹은 신규 `설정` 탭 (확장성 — 차후 기타 운영 항목 추가 대비) 의 권한 묶음.
    # admin only auto-grant. 다른 role 은 admin 콘솔에서 explicit override.
    {
        # perm-category-hier(2026-07-14): '시스템' 카테고리(설정 탭) 최상위 접근 게이트.
        "code": "console.system.access",
        "label": "시스템 접근",
        "description": "관리 콘솔의 '시스템' 카테고리(설정 탭)에 접근할 수 있다. 카테고리 최상위 조회 게이트 — 전역 시스템 프롬프트/런타임 설정의 조회·수정 권한은 이 권한 하위로 종속된다.",
        "group": "settings",
    },
    {
        "code": "system_prompt.global.read",
        "label": "전역 시스템 프롬프트 조회",
        "description": "모든 대화의 최상위 base 가 되는 전역 시스템 프롬프트 본문을 조회할 수 있다.",
        "group": "settings",
    },
    {
        "code": "system_prompt.global.write",
        "label": "전역 시스템 프롬프트 수정",
        "description": "전역 시스템 프롬프트를 수정/삭제할 수 있다. 모든 LLM 응답에 영향이 가는 권한이므로 운영자 한정.",
        "group": "settings",
    },
    # feature-0018 (REQ runtime-settings): 관리 콘솔 `시스템 > 설정` 의 운영 값(실행 타임아웃,
    # 모델별 thinking budget) 조회/수정 권한. settings 그룹 정합 — admin only auto-grant,
    # 다른 role 은 콘솔에서 explicit override. write 는 서비스 응답 지연·비용에 직접 영향.
    {
        "code": "system.runtime.read",
        "label": "런타임 설정 조회",
        "description": "실행 타임아웃·모델별 추론 예산 등 assistant 운영 값을 조회할 수 있다.",
        "group": "settings",
    },
    {
        "code": "system.runtime.write",
        "label": "런타임 설정 수정",
        "description": "실행 타임아웃·모델별 추론 예산을 수정/초기화할 수 있다. 서비스 응답 지연·비용에 직접 영향이 가므로 운영자 한정.",
        "group": "settings",
    },
    # feature-0021: 관리 콘솔 `감사 > AI 추론` read-only 조회 권한 — 답변 자가 적대(red-team)
    # 리뷰 활동·판정과 세션/제품 메모리 노트 현황(관측·감사 데이터). 조회 전용이라 write 페어
    # 없음. admin only auto-grant (least-privilege). console-ia(2026-07-16): 카테고리 감사로
    # 재배치(AI 운영 현황과 나란히) + 지침/스킬 조회는 system_prompt.global.read 로 분리.
    {
        "code": "console.reasoning.read",
        "label": "AI 추론 활동 조회",
        "description": "답변 자가 적대(red-team) 리뷰 활동·판정과 세션/제품 메모리 노트 현황을 조회할 수 있다.",
        "group": "audit",
    },
)
PERMISSION_CODES = tuple(item["code"] for item in PERMISSION_DEFINITIONS)
PERMISSION_DEFINITION_MAP = {item["code"]: item for item in PERMISSION_DEFINITIONS}

# graph-panel-perms(task4): 레거시 묶음 권한 `kb.ingest.manual` 이 함의하는 세부 권한 집합.
#   _apply_permission_overrides 가 effective map 에서 묶음 보유자에게 아래 편집 4종을 자동 부여(개별 DENY 오버라이드는 존중).
#   기존 배포 무손실(비파괴·가역) — DB 마이그레이션 없이 하위호환. 묶음 보유 principal(역할/계정 오버라이드) 전부 커버.
# graph-perm-split(Critical §12.3, 2026-07-13): metadata.graph.read 를 본 함의에서 제거 — 그래프 뷰가
#   별도 최상위 탭으로 분리됨에 따라 "메타데이터 관리" 묶음이 더 이상 그래프 뷰 접근을 자동 함의하지 않는다.
#   분리 시점의 기존 묶음 보유 principal 의 그래프 접근은 _backfill_graph_perm_split_v1(1회 멱등 backfill)로 보존.
_METADATA_MANUAL_IMPLIES = (
    "metadata.glossary.manage",
    "metadata.enum.manage",
    "metadata.table.manage",
    "metadata.column.manage",
)

# perm-atomic-split(Critical §12.3, 사용자 승인 2026-07-15): 묶음(레거시) → 원자 단위 함의 맵.
#   _apply_permission_overrides 가 effective map 에서 묶음 보유자에게 원자 단위를 transitive 로
#   자동 부여한다(kb.ingest.manual → 4 manage → 각 read/create/update/delete). 개별 DENY 오버라이드
#   존중(least-privilege). manage 는 read 도 함의(기존 read/manage superset 의미론 정합 — TASK-0288).
_PERMISSION_BUNDLE_IMPLIES = {
    "kb.ingest.manual": _METADATA_MANUAL_IMPLIES,
    "metadata.glossary.manage": (
        "metadata.glossary.read", "metadata.glossary.create",
        "metadata.glossary.update", "metadata.glossary.delete",
    ),
    "metadata.enum.manage": (
        "metadata.enum.read", "metadata.enum.create",
        "metadata.enum.update", "metadata.enum.delete",
    ),
    "metadata.table.manage": (
        "metadata.table.read", "metadata.table.create",
        "metadata.table.update", "metadata.table.delete",
    ),
    "metadata.column.manage": (
        "metadata.column.read", "metadata.column.create",
        "metadata.column.update", "metadata.column.delete",
    ),
    "product.manage": (
        "product.read", "product.create", "product.update", "product.delete",
    ),
    "datasource.manage": (
        "datasource.read", "datasource.create", "datasource.update",
        "datasource.delete", "datasource.test",
    ),
}

# perm-atomic-split: 권한 grid(관리 콘솔 역할/override 편집기 + 작업 화면 자기 조회)에서 숨기는
#   레거시 묶음 코드. 코드·enforcement 함의·기존 grant 는 유지(하위호환 안전망)하되 화면에는
#   원자 단위만 노출한다 — admin.js/app.js 의 동명 상수와 정합(test 가 parity 검증).
LEGACY_BUNDLE_PERMISSIONS = (
    "kb.ingest.manual",
    "metadata.glossary.manage",
    "metadata.enum.manage",
    "metadata.table.manage",
    "metadata.column.manage",
    "product.manage",
    "datasource.manage",
)

# graph-perm-split(Critical §12.3, 사용자 결정 2026-07-13): 그래프 뷰 권한을 메타데이터 관리 묶음 함의에서
#   분리하면서, **분리 시점의 기존 묶음 보유 principal 의 그래프 접근을 1회 backfill 로 보존**하기 위한 마커 키.
#   WebSchemaMigrations 에 이 키가 있으면 backfill 완료 → 재실행 안 함(멱등 guard). 매 startup 무조건 재실행 시
#   분리 이후 새로 묶음을 받은 역할까지 graph.read 를 자동 획득해 분리가 무력화되므로 반드시 1회만 수행한다.
_GRAPH_PERM_SPLIT_MIGRATION_KEY = "graph-perm-split-v1"

# perm-category-hier(Critical §12.3, 사용자 승인 A안 2026-07-14): 관리 콘솔 nav 카테고리별 최상위
#   '접근'(조회 게이트) 권한 → 그 카테고리에 속한 세부 권한(탭 조회·추가/수정/삭제·승인/작동) 목록.
#   용도: (1) _backfill_console_category_access_v1 — 기존 배포에서 console.access + 세부 권한 보유
#   principal 에 접근 권한을 1회 자동 부여(접근 무손실), (2) 테스트의 카탈로그 정합 검증.
#   admin.js 의 PERMISSION_DEPENDENCIES(UI 계층)·ADMIN_TAB_CATEGORY_ACCESS(탭 게이트)와 정합 유지.
_CONSOLE_CATEGORY_ACCESS_LEAVES = {
    "console.account.access": (
        "account.read", "account.update", "account.delete", "account.activate",
        "account.deactivate", "account.role.assign", "account.permission.override.manage",
        "role.read", "role.create", "role.update", "role.delete", "role.permission.manage",
        "quota.read", "quota.manage",
    ),
    "console.product.access": (
        "product.read", "product.create", "product.update", "product.delete",
        "system_prompt.manage.role.any", "insight.reset",
        "datasource.read", "datasource.create", "datasource.update", "datasource.delete",
        "datasource.test",
    ),
    "console.audit.access": (
        "audit.read.own", "audit.read.any", "audit.export", "audit.purge",
        "conversation.archive.read.any", "console.usage.read", "console.aiops.read",
        # feature-0021 console-ia: AI 추론(red-team 리뷰 활동·메모리 노트) 은 감사 관측 데이터.
        "console.reasoning.read",
    ),
    "console.kb.access": (
        # perm-atomic-split(2026-07-15): 레거시 묶음(kb.ingest.manual·metadata.*.manage)은 grid 숨김·
        # FE 종속 트리 제외라 본 맵에서도 제외 — 원자 단위가 카테고리 leaves(M5 계약).
        "metadata.glossary.read", "metadata.glossary.create", "metadata.glossary.update", "metadata.glossary.delete",
        "metadata.enum.read", "metadata.enum.create", "metadata.enum.update", "metadata.enum.delete",
        "metadata.table.read", "metadata.table.create", "metadata.table.update", "metadata.table.delete",
        "metadata.column.read", "metadata.column.create", "metadata.column.update", "metadata.column.delete",
        "metadata.graph.read", "metadata.graph.analyze",
        "kb.sample.curate", "kb.glossary.curate", "kb.enum.curate",
    ),
    "console.system.access": (
        "system_prompt.global.read", "system_prompt.global.write",
        "system.runtime.read", "system.runtime.write",
    ),
}

# perm-category-hier: 1회 backfill 멱등 마커 키(WebSchemaMigrations). graph-perm-split 과 동일 규약 —
#   매 startup 재실행 시 backfill 이후 새로 세부 권한만 받은 역할까지 접근 권한을 자동 획득해
#   계층 게이트가 무력화되므로 정확히 1회만 수행한다.
_CONSOLE_CATEGORY_ACCESS_MIGRATION_KEY = "console-category-access-v1"

# perm-atomic-split: 묶음→원자 단위 explicit 전개 1회 backfill 마커. 묶음 보유 principal 이
#   권한 grid 에서 원자 단위 체크 상태로 보이도록 explicit grant 로 고정한다(런타임 함의는 안전망).
#   1회 규약 근거는 위와 동일 — 단, 묶음은 grid 숨김이라 분리 이후 신규 묶음 부여 경로가 없어
#   재실행 위험 자체가 작다(방어적 1회 유지).
_ATOMIC_PERM_SPLIT_MIGRATION_KEY = "atomic-perm-split-v1"
# feature-0024-conversation-folders: 대화 폴더는 대화를 만들 수 있는 모든 역할이 개인 단위로
# 쓰는 일반 기능이다(사용자 결정 2026-07-23). 도입 시 기존 배포의 conversation.create 보유
# 역할에 folder.list.own/folder.manage.own 을 1회 backfill 로 부여한다.
_FOLDER_PERMS_BROADEN_MIGRATION_KEY = "folder-perms-broaden-v1"


# TASK-0052 Phase 1A: RBAC catalog 를 인자로 받는 형태로 변경 (기본값은 정적 PERMISSION_DEFINITIONS).
# Phase 1B 에서 _resolve_permission_catalog(conn) 가 WebPermissions 의 IsDynamic=1 row 까지 합쳐
# 동적 catalog 를 반환하도록 확장 예정. 본 refactor 자체는 동작 변경 없음.
def _resolve_permission_catalog(conn=None) -> tuple[list[dict[str, Any]], set[str], dict[str, dict[str, Any]]]:
    """현재 effective permission catalog 를 (definitions, codes_set, code_map) 형태로 반환.

    Phase 1B 부터: conn 이 주어지면 정적 PERMISSION_DEFINITIONS + WebPermissions 의 IsDynamic=1 row 를
    union 해서 반환한다. conn 이 None 이면 기존 정적 결과만 (테스트/bootstrap-time 안전망).

    동적 row 는 product CRUD 가 관리하는 `product.access.<product_key>` 형태이며
    GroupName='product_access'(TASK-0288: 작업 화면 제품 사용 — 관리 콘솔 제품 관리 'product'와 분리),
    IsDynamic=1, ProductId=<WebProducts.Id>.
    """
    static_defs = list(PERMISSION_DEFINITIONS)
    static_codes = set(PERMISSION_CODES)
    static_map = dict(PERMISSION_DEFINITION_MAP)
    if conn is None:
        return static_defs, static_codes, static_map
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute(
            """
SELECT Code, Label, Description, GroupName, ProductId
FROM WebPermissions
WHERE IsDynamic = 1
ORDER BY GroupName, Code
            """
        )
        dynamic_rows = cur.fetchall() or []
        cur.close()
    except Exception:
        # WebPermissions IsDynamic 컬럼이 아직 없거나 (legacy) DB error 시 정적 결과로 graceful fallback.
        return static_defs, static_codes, static_map
    if not dynamic_rows:
        return static_defs, static_codes, static_map
    merged_defs = list(static_defs)
    merged_codes = set(static_codes)
    merged_map = dict(static_map)
    for row in dynamic_rows:
        code = str(row.get("Code") or "").strip()
        if not code or code in merged_codes:
            continue
        item = {
            "code": code,
            "label": str(row.get("Label") or code),
            "description": str(row.get("Description") or ""),
            "group": str(row.get("GroupName") or "product"),
            "is_dynamic": True,
            "product_id": int(row.get("ProductId") or 0) or None,
        }
        merged_defs.append(item)
        merged_codes.add(code)
        merged_map[code] = item
    return merged_defs, merged_codes, merged_map


# ── ITEM-10 inc4: 권한 오버라이드/계정 행 빌더 (순수 — conn 인자 주입) ──
# app.py 에서 byte-동치 이동. _decorate_account_rows → _load_role_permission_codes/
# _load_account_override_values/_resolve_permission_catalog/_apply_permission_overrides
# 폐포가 전부 본 모듈 안에서 닫힌다(app 의존 0).

OVERRIDE_ALLOW = "allow"
OVERRIDE_DENY = "deny"
OVERRIDE_INHERIT = "inherit"


def _empty_permission_map(catalog_codes: Iterable[str] | None = None) -> dict[str, bool]:
    """TASK-0052 Phase 1A: catalog_codes 인자가 None 이면 정적 PERMISSION_CODES 사용 (기존 동작)."""
    codes = catalog_codes if catalog_codes is not None else PERMISSION_CODES
    return {code: False for code in codes}


def _normalize_override_value(value: Any) -> str:
    text = str(value or "").strip().lower()
    if text == OVERRIDE_ALLOW:
        return OVERRIDE_ALLOW
    if text == OVERRIDE_DENY:
        return OVERRIDE_DENY
    return OVERRIDE_INHERIT


def _apply_permission_overrides(
    base_codes: set[str] | None,
    overrides: dict[str, str] | None = None,
    *,
    catalog_codes: Iterable[str] | None = None,
) -> dict[str, bool]:
    """TASK-0052 Phase 1A: catalog_codes 가 주어지면 그 catalog 기반으로 map 을 build."""
    permissions = _empty_permission_map(catalog_codes)
    for code in base_codes or set():
        if code in permissions:
            permissions[code] = True
    for code, value in (overrides or {}).items():
        if code not in permissions:
            continue
        normalized = _normalize_override_value(value)
        if normalized == OVERRIDE_ALLOW:
            permissions[code] = True
        elif normalized == OVERRIDE_DENY:
            permissions[code] = False
    # graph-panel-perms(task4) → perm-atomic-split(2026-07-15) 일반화: 레거시 묶음 함의 —
    #   effective 로 묶음 보유 시 원자 단위를 transitive 로 자동 부여(kb.ingest.manual → 4 manage →
    #   각 read/create/update/delete). 개별 DENY 오버라이드는 존중(least-privilege). fixpoint 루프는
    #   묶음 체인 깊이(2)만큼만 실제 반복되고 변화 없으면 즉시 종료한다.
    changed = True
    while changed:
        changed = False
        for bundle, implied in _PERMISSION_BUNDLE_IMPLIES.items():
            if not permissions.get(bundle):
                continue
            for code in implied:
                if code not in permissions or permissions[code]:
                    continue
                if _normalize_override_value((overrides or {}).get(code)) == OVERRIDE_DENY:
                    continue
                permissions[code] = True
                changed = True
    return permissions


def _fetch_account_rows(
    conn,
    where_sql: str,
    params: tuple[Any, ...] = (),
    *,
    include_password: bool = False,
    include_legacy: bool = False,
    order_sql: str = "",
    limit_sql: str = "",
) -> list[dict[str, Any]]:
    password_select = ", a.PasswordHash AS password_hash" if include_password else ""
    legacy_select = (
        """
    ,
    a.Role AS legacy_role,
    a.CanSendRequest AS legacy_can_send_request,
    a.CanCancelRequest AS legacy_can_cancel_request,
    a.CanFinalizeRequest AS legacy_can_finalize_request,
    a.CanDeleteConversation AS legacy_can_delete_conversation,
    a.CanClearConversations AS legacy_can_clear_conversations
        """
        if include_legacy
        else ""
    )
    cur = conn.cursor(dictionary=True)
    cur.execute(
        f"""
SELECT
    a.Id AS id,
    a.Username AS username,
    a.IsActive AS is_active,
    a.CreatedAt AS created_at,
    a.ApprovedAt AS approved_at,
    a.ApprovedByAccountId AS approved_by_account_id,
    a.LastLoginAt AS last_login_at,
    a.LastConversationId AS last_conversation_id,
    a.RoleId AS role_id,
    a.DeletedAt AS deleted_at,
    a.DeletedByAccountId AS deleted_by_account_id,
    COALESCE(a.MustChangePassword, 0) AS must_change_password,
    COALESCE(a.FailedLoginAttempts, 0) AS failed_login_attempts,
    a.LockedUntilAt AS locked_until_at,
    (a.LockedUntilAt IS NOT NULL AND a.LockedUntilAt > NOW()) AS is_locked,
    COALESCE((SELECT t.Enabled FROM WebAccountTotp t WHERE t.AccountId = a.Id LIMIT 1), 0) AS totp_enabled,
    (SELECT q.TokenLimit FROM WebAccountTokenQuotas q WHERE q.AccountId = a.Id AND q.QuotaType='daily' LIMIT 1) AS quota_daily,
    (SELECT q.TokenLimit FROM WebAccountTokenQuotas q WHERE q.AccountId = a.Id AND q.QuotaType='monthly' LIMIT 1) AS quota_monthly,
    a.AvatarObjectKey AS avatar_object_key,
    a.Email AS email,
    a.AuthProvider AS auth_provider,
    a.OAuthSubject AS oauth_subject,
    r.RoleKey AS role_key,
    r.Name AS role_name,
    r.Description AS role_description,
    r.IsActive AS role_is_active,
    r.IsDefaultSignup AS role_is_default_signup
    {legacy_select}
    {password_select}
FROM WebAccounts a
LEFT JOIN WebRoles r
  ON r.Id = a.RoleId
WHERE {where_sql}
{order_sql}
{limit_sql}
        """,
        params,
    )
    rows = cur.fetchall() or []
    cur.close()
    return rows


def _load_role_permission_codes(conn, role_ids: list[int]) -> dict[int, set[str]]:
    if not role_ids:
        return {}
    placeholders = ",".join(["%s"] * len(role_ids))
    cur = conn.cursor()
    cur.execute(
        f"""
SELECT rp.RoleId, p.Code
FROM WebRolePermissions rp
JOIN WebPermissions p
  ON p.Id = rp.PermissionId
JOIN WebRoles r
  ON r.Id = rp.RoleId
WHERE rp.RoleId IN ({placeholders}) AND r.IsActive = 1
        """,
        tuple(role_ids),
    )
    rows = cur.fetchall() or []
    cur.close()
    mapping: dict[int, set[str]] = {}
    for role_id, code in rows:
        mapping.setdefault(int(role_id), set()).add(str(code))
    return mapping


def _load_account_override_values(conn, account_ids: list[int]) -> dict[int, dict[str, str]]:
    if not account_ids:
        return {}
    placeholders = ",".join(["%s"] * len(account_ids))
    cur = conn.cursor()
    cur.execute(
        f"""
SELECT ao.AccountId, p.Code, ao.OverrideValue
FROM WebAccountPermissionOverrides ao
JOIN WebPermissions p
  ON p.Id = ao.PermissionId
WHERE ao.AccountId IN ({placeholders})
        """,
        tuple(account_ids),
    )
    rows = cur.fetchall() or []
    cur.close()
    mapping: dict[int, dict[str, str]] = {}
    for account_id, code, value in rows:
        mapping.setdefault(int(account_id), {})[str(code)] = _normalize_override_value(value)
    return mapping


def _decorate_account_rows(conn, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not rows:
        return rows
    role_ids = sorted({int(row.get("role_id") or 0) for row in rows if int(row.get("role_id") or 0) > 0})
    account_ids = [int(row.get("id") or 0) for row in rows if int(row.get("id") or 0) > 0]
    role_permission_map = _load_role_permission_codes(conn, role_ids)
    override_map = _load_account_override_values(conn, account_ids)
    # TASK-0052 Phase 1B: catalog 를 conn 으로 한 번 조회 후 모든 row 에 재사용 (N+1 회피).
    _catalog_defs, catalog_codes, _catalog_map = _resolve_permission_catalog(conn)
    for row in rows:
        account_id = int(row.get("id") or 0)
        role_id = int(row.get("role_id") or 0)
        overrides = override_map.get(account_id, {})
        permissions = _apply_permission_overrides(
            role_permission_map.get(role_id, set()),
            overrides,
            catalog_codes=catalog_codes,
        )
        row["permission_overrides"] = overrides
        row["permissions"] = permissions
    return rows


# ── ITEM-10 b2: 검증 정규식·인증 파라미터·RBAC seed 롤 (순수 leaf) ──
# app.py 에서 byte-동치 이동(상단 rebind 소비 — INVARIANT 동일).

ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
CONTROL_RE = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")
MODEL_RE = re.compile(r"^[A-Za-z0-9._:/-]{1,64}$")
USERNAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{2,63}$")
ROLE_KEY_RE = re.compile(r"^[a-z][a-z0-9_.-]{2,63}$")

SEED_ROLE_DEFINITIONS = (
    {
        "key": "pending",
        "name": "Pending",
        "description": "승인 전 조회 전용 계정",
        "is_default_signup": True,
        "permissions": {
            "conversation.list.own",
            "conversation.read.own",
            # TASK-0073 Phase A3: 모든 role 에 audit.read.own auto-grant
            # (self filter — 본인이 actor 인 이벤트 조회, TASK-0293 Actor-only).
            "audit.read.own",
            # TASK-0094 Sprint 1 Phase 3 (D21, R-F14): pending 은 read.own 만.
            # upload 거부 + bytes download 는 application-level (Phase 5 endpoint) 차단.
            "conversation.attachment.read.own",
        },
    },
    {
        "key": "operator",
        "name": "Operator",
        "description": "일반 작업 계정",
        "is_default_signup": False,
        "permissions": {
            "conversation.create",
            "conversation.ask",
            "conversation.list.own",
            "conversation.read.own",
            "conversation.file.read.own",
            "conversation.rename.own",
            "conversation.delete.own",
            "conversation.cancel.own",
            "conversation.finalize.own",
            "conversation.share.create",
            "conversation.duplicate.own",
            # TASK-0073 Phase A3: 모든 role audit.read.own auto-grant.
            "audit.read.own",
            # TASK-0094 Sprint 1 Phase 3: 첨부 upload/read own.
            "conversation.attachment.upload.own",
            "conversation.attachment.read.own",
            # TASK-0161: attachment.execute_sql_on.own 시드 제거 (거짓 컨트롤 — 실제 게이트는 allowlist+attachment_reader+sql_guard).
            # feature-0024-conversation-folders: 대화 폴더 개인 사용(conversation.create 보유 역할).
            "folder.list.own",
            "folder.manage.own",
        },
    },
    {
        "key": "sales",
        "name": "사업팀",
        "description": "게임 사업팀 pilot 계정 — 단순 조회/집계 자가서비스. ad-hoc 심층 분석은 DBA 팀으로 이관",
        "is_default_signup": False,
        "permissions": {
            "conversation.create",
            "conversation.ask",
            "conversation.list.own",
            "conversation.read.own",
            "conversation.file.read.own",
            "conversation.rename.own",
            "conversation.delete.own",
            "conversation.cancel.own",
            "conversation.finalize.own",
            "conversation.share.create",
            "conversation.duplicate.own",
            # TASK-0073 Phase A3: 모든 role audit.read.own auto-grant.
            "audit.read.own",
            # TASK-0094 Sprint 1 Phase 3: 첨부 upload/read own.
            "conversation.attachment.upload.own",
            "conversation.attachment.read.own",
            # TASK-0161: attachment.execute_sql_on.own 시드 제거 (거짓 컨트롤).
            # feature-0024-conversation-folders: 대화 폴더 개인 사용(conversation.create 보유 역할).
            "folder.list.own",
            "folder.manage.own",
        },
    },
    {
        "key": "admin",
        "name": "Admin",
        "description": "관리 콘솔과 전체 대화 관리 권한을 가진 계정",
        "is_default_signup": False,
        "permissions": set(PERMISSION_CODES),
    },
)

PASSWORD_HASH_ITERATIONS = max(100_000, int(os.getenv("WEB_PASSWORD_HASH_ITERATIONS", "310000")))
AUTH_SESSION_DAYS = max(1, int(os.getenv("WEB_AUTH_SESSION_DAYS", "14")))


def _seed_role_definition(role_key: str) -> dict[str, Any] | None:
    for item in SEED_ROLE_DEFINITIONS:
        if item["key"] == role_key:
            return item
    return None


def _seed_role_codes(role_key: str) -> set[str]:
    item = _seed_role_definition(role_key)
    if not item:
        return set()
    return set(item["permissions"])


# ── ITEM-10 b3: 세션쿠키·패스워드·TOTP 클러스터 ──
# app.py 에서 byte-동치 이동. top-level 은 여전히 app-free; _totp_dek 계열의
# `from modules import cred_crypto` / `from shared import datasources` 는 **함수-지역
# lazy import**(import 시점 무의존·역방향 참조 없음 — INVARIANT 의 무순환 취지 유지).

def _get_session_id(request: Request) -> tuple[str, bool, str]:
    client_ip = _get_client_ip(request)
    existing = _sanitize_session_id(request.cookies.get(SESSION_COOKIE, ""))
    if existing:
        return existing, False, client_ip
    return secrets.token_hex(32), True, client_ip


def _request_is_https(request: Request) -> bool:
    forwarded_proto = request.headers.get("x-forwarded-proto", "").split(",")[0].strip().lower()
    if forwarded_proto:
        return forwarded_proto == "https"
    return str(request.url.scheme or "").lower() == "https"


def _set_session_cookie(response: Any, request: Request, session_id: str) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        session_id,
        httponly=True,
        samesite="lax",
        secure=_request_is_https(request),
    )


def _clear_session_cookie(response: Any, request: Request) -> None:
    response.delete_cookie(
        SESSION_COOKIE,
        httponly=True,
        samesite="lax",
        secure=_request_is_https(request),
    )


# (P5b 이동 당시 app.py 쪽 marker 가 딸려온 잔재 — 본 파일이 정본. ITEM-10 b3 패널 NIT 정리)


def _sanitize_username(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]", "", str(value or "").strip())[:64]


def _is_valid_username(value: str) -> bool:
    return bool(USERNAME_RE.match(str(value or "").strip()))


def _is_valid_password(password: str) -> bool:
    text = str(password or "")
    if len(text) < 10 or len(text) > 128:
        return False
    if CONTROL_RE.search(text):
        return False
    return True


def _hash_password(password: str, salt: bytes | None = None) -> str:
    if not _is_valid_password(password):
        raise ValueError("invalid password")
    salt = salt or os.urandom(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        PASSWORD_HASH_ITERATIONS,
    )
    return (
        f"pbkdf2_sha256${PASSWORD_HASH_ITERATIONS}$"
        f"{base64.b64encode(salt).decode('ascii')}$"
        f"{base64.b64encode(digest).decode('ascii')}"
    )


def _verify_password(password: str, stored_hash: str) -> bool:
    try:
        algorithm, iterations_raw, salt_b64, digest_b64 = str(stored_hash or "").split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        iterations = max(1, int(iterations_raw))
        salt = _b64decode(salt_b64)
        expected = _b64decode(digest_b64)
        if not salt or not expected:
            return False
    except Exception:
        return False
    actual = hashlib.pbkdf2_hmac(
        "sha256",
        str(password or "").encode("utf-8"),
        salt,
        iterations,
    )
    return hmac.compare_digest(actual, expected)


# =============================================================================
# TASK-20260619T040000-two-factor-auth (보안 ⑥, Critical §12.3): 2단계 인증 (TOTP, RFC 6238).
# secret 은 cred_crypto(DEK/KEK, AAD=totp:{account_id})로 암호화 저장. 로그인 pending token 은
# DEK-HMAC 서명(stateless, 5분 TTL). 백업코드는 sha256 해시(1회용). pyotp 미사용(stdlib).
# 사용자 opt-in(self-service 켜기/끄기) + 관리자 강제 해제(분실 복구). 기본 미설정=2FA 미사용(무회귀).
# =============================================================================
_TOTP_STEP = 30
_TOTP_DIGITS = 6
_TOTP_DRIFT_WINDOW = 1            # ±1 step (시계 drift 허용)
_TOTP_PENDING_TTL = 300          # 로그인 pending token 유효 5분
_TOTP_BACKUP_CODE_COUNT = 10
_TOTP_AAD_PREFIX = "totp:"


def _totp_generate_secret() -> str:
    """base32 TOTP secret (160-bit) 생성."""
    import base64 as _b64
    return _b64.b32encode(os.urandom(20)).decode("ascii").rstrip("=")


def _totp_code_at(secret_b32: str, ts: float) -> str:
    import base64 as _b64
    import struct as _st
    pad = "=" * ((8 - len(secret_b32) % 8) % 8)
    key = _b64.b32decode(secret_b32.upper() + pad, casefold=True)
    counter = int(ts // _TOTP_STEP)
    h = hmac.new(key, _st.pack(">Q", counter), hashlib.sha1).digest()
    o = h[-1] & 0x0F
    val = (_st.unpack(">I", h[o:o + 4])[0] & 0x7FFFFFFF) % (10 ** _TOTP_DIGITS)
    return str(val).zfill(_TOTP_DIGITS)


def _totp_verify(secret_b32: str, code: str, ts: "float | None" = None) -> bool:
    import time as _t
    code = str(code or "").strip().replace(" ", "")
    if not code.isdigit() or len(code) != _TOTP_DIGITS:
        return False
    now = ts if ts is not None else _t.time()
    for drift in range(-_TOTP_DRIFT_WINDOW, _TOTP_DRIFT_WINDOW + 1):
        try:
            if hmac.compare_digest(_totp_code_at(secret_b32, now + drift * _TOTP_STEP), code):
                return True
        except Exception:
            return False
    return False


def _totp_otpauth_uri(secret_b32: str, username: str, issuer: str = "DQA") -> str:
    from urllib.parse import quote
    label = quote(f"{issuer}:{username}")
    return (f"otpauth://totp/{label}?secret={secret_b32}&issuer={quote(issuer)}"
            f"&digits={_TOTP_DIGITS}&period={_TOTP_STEP}")


def _totp_dek(conn):
    """(_cc, ver, dek) 또는 None. KEK 미설정/DEK 부재 시 None(2FA 불가)."""
    try:
        from modules import cred_crypto as _cc
        from shared import datasources as _dsr
    except Exception:
        return None
    if not _cc.enc_available():
        return None
    try:
        got = _dsr.ensure_dek(conn)
    except Exception:
        return None
    if not got:
        return None
    ver, dek = got
    return (_cc, int(ver), dek)


def _totp_encrypt_secret(conn, account_id: int, secret_b32: str) -> "tuple[str, int] | None":
    d = _totp_dek(conn)
    if not d:
        return None
    _cc, ver, dek = d
    try:
        return (_cc.encrypt_password(dek, secret_b32, f"{_TOTP_AAD_PREFIX}{int(account_id)}"), ver)
    except Exception:
        return None


def _totp_decrypt_secret(conn, account_id: int, enc: str, version: int) -> "str | None":
    try:
        from modules import cred_crypto as _cc
        from shared import datasources as _dsr
    except Exception:
        return None
    try:
        got = _dsr.get_dek(conn, int(version))
    except Exception:
        return None
    if not got:
        return None
    _ver, dek = got
    try:
        return _cc.decrypt_password(dek, enc, f"{_TOTP_AAD_PREFIX}{int(account_id)}")
    except Exception:
        return None


def _totp_load(conn, account_id: int) -> "dict | None":
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute(
            "SELECT AccountId, SecretEnc, EncryptionVersion, Enabled, BackupCodesJson "
            "FROM WebAccountTotp WHERE AccountId = %s LIMIT 1",
            (int(account_id),),
        )
        return cur.fetchone()
    except Exception:
        return None
    finally:
        cur.close()


def _totp_is_enabled(conn, account_id: int) -> bool:
    row = _totp_load(conn, account_id)
    return bool(row and int(row.get("Enabled") or 0) == 1)


def _totp_backup_hash(code: str) -> str:
    return hashlib.sha256(str(code or "").strip().upper().replace("-", "").encode("utf-8")).hexdigest()


def _totp_generate_backup_codes(n: int = _TOTP_BACKUP_CODE_COUNT) -> list[str]:
    import base64 as _b64
    return [_b64.b32encode(os.urandom(6)).decode("ascii").rstrip("=")[:10] for _ in range(n)]


def _totp_consume_backup_code(conn, account_id: int, code: str) -> bool:
    """백업 코드 1회용 소비. 일치 시 used 마킹 후 True.

    outside-voice MINOR 흡수: read-modify-write 를 `SELECT ... FOR UPDATE` 명시 tx 로 감싸
    동시 로그인이 같은 백업코드를 중복 소비하는 race 를 차단(원자적 1회용 보장).
    """
    target = _totp_backup_hash(code)
    started = False
    try:
        conn.start_transaction()
        started = True
    except Exception:
        started = False  # 이미 tx 중이면 기존 tx 안에서 FOR UPDATE 로 락.
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT BackupCodesJson FROM WebAccountTotp WHERE AccountId = %s FOR UPDATE",
            (int(account_id),),
        )
        r = cur.fetchone()
        if not r or not r[0]:
            if started:
                conn.commit()
            return False
        codes = json.loads(r[0])
        matched = False
        for c in codes:
            if (not c.get("used")) and hmac.compare_digest(str(c.get("hash") or ""), target):
                c["used"] = True
                matched = True
                break
        if not matched:
            if started:
                conn.commit()
            return False
        cur.execute(
            "UPDATE WebAccountTotp SET BackupCodesJson = %s WHERE AccountId = %s",
            (json.dumps(codes), int(account_id)),
        )
        if started:
            conn.commit()
        return True
    except Exception:
        if started:
            try:
                conn.rollback()
            except Exception:
                pass
        return False
    finally:
        cur.close()


def _totp_pending_token(conn, account_id: int) -> "str | None":
    """로그인 1단계(비밀번호) 통과 후 TOTP 대기용 stateless 서명 토큰(DEK-HMAC, TTL)."""
    import time as _t
    import base64 as _b64
    d = _totp_dek(conn)
    if not d:
        return None
    _cc, _ver, dek = d
    exp = int(_t.time()) + _TOTP_PENDING_TTL
    payload = f"{int(account_id)}:{exp}"
    sig = hmac.new(dek, payload.encode("utf-8"), hashlib.sha256).hexdigest()
    return _b64.urlsafe_b64encode(f"{payload}:{sig}".encode("utf-8")).decode("ascii")


def _totp_verify_pending_token(conn, token: str) -> "int | None":
    """pending token 검증 → account_id (만료/위조 시 None)."""
    import time as _t
    import base64 as _b64
    try:
        raw = _b64.urlsafe_b64decode(str(token or "").encode("ascii")).decode("utf-8")
        aid_s, exp_s, sig = raw.split(":", 2)
        aid, exp = int(aid_s), int(exp_s)
    except Exception:
        return None
    if exp < int(_t.time()):
        return None
    d = _totp_dek(conn)
    if not d:
        return None
    _cc, _ver, dek = d
    expect = hmac.new(dek, f"{aid}:{exp}".encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expect, str(sig)):
        return None
    return aid


def _b64decode(text: str) -> bytes:
    if not text:
        return b""
    try:
        padding = "=" * (-len(text) % 4)
        return base64.b64decode(text + padding)
    except Exception:
        return b""


# ── ITEM-10 b4: 세션 경로·출력 정규화·내부메시지 판정·미디어 URL 빌더 (순수 leaf) ──
# app.py 에서 byte-동치 이동(상단 rebind). SESSION_DIR mkdir 부작용은 본 모듈 import
# 시점(app 상단, 종전 정의 위치보다 앞)으로 이동 — 동일 프로세스 내 선행 보장이라 무해.

SESSION_DIR = Path(os.getenv("WEB_SESSION_DIR", "/shared/web_sessions"))
SESSION_DIR.mkdir(parents=True, exist_ok=True)

INTERNAL_MEMORY_PREFIXES = (
    "파일 탐색 완료",
    "대화 검색 완료",
    "파일 읽기 완료",
    "자동 탐색 완료",
)
PLACEHOLDER_TOPICS = {"", "(미설정)", "새 대화"}


def _strip_ansi(text: str) -> str:
    return ANSI_RE.sub("", text or "")


def _normalize_output(text: str) -> str:
    cleaned = _strip_ansi(text or "")
    cleaned = cleaned.replace("\r\n", "\n").replace("\r", "\n")
    cleaned = CONTROL_RE.sub("", cleaned)
    return cleaned


def _should_mark_internal_message(content: str) -> bool:
    if not content:
        return False
    stripped = content.strip()
    for prefix in INTERNAL_MEMORY_PREFIXES:
        if stripped.startswith(prefix):
            return True
    # tool_notes JSON (LLM 도구 호출 시 생성) 필터링
    if stripped.startswith("{") and stripped.endswith("}"):
        try:
            payload = json.loads(stripped)
            if isinstance(payload, dict) and "tool_notes" in payload:
                return True
        except (json.JSONDecodeError, ValueError):
            pass
    return False


def _is_internal_message(role: str, content: str, meta_json: str | None) -> bool:
    if str(role or "").lower() != "assistant":
        return False
    if meta_json:
        try:
            meta = json.loads(meta_json)
            if isinstance(meta, dict) and meta.get("internal"):
                return True
        except Exception:
            pass
    return _should_mark_internal_message(content)


def _unwrap_followup_user_request(text: str) -> str:
    current = str(text or "").strip()
    if not current:
        return ""
    for _ in range(4):
        if "[이어받기 컨텍스트]" not in current:
            break
        marker = current.find("[이어받기 컨텍스트]")
        if marker >= 0:
            current = current[marker:].strip()
        if not current.startswith("[이어받기 컨텍스트]"):
            break
        match = re.search(r"\[사용자 요청\]\s*(.+)$", current, flags=re.IGNORECASE | re.DOTALL)
        if not match:
            break
        next_value = str(match.group(1) or "").strip()
        if not next_value:
            break
        current = next_value
    current = re.sub(r"\[이어받기 컨텍스트\]", " ", current, flags=re.IGNORECASE)
    current = re.sub(r"\[사용자 요청\]", " ", current, flags=re.IGNORECASE)
    current = re.sub(r"\b의도\s*:", " ", current, flags=re.IGNORECASE)
    current = re.sub(r"\b제약\s*:", " ", current, flags=re.IGNORECASE)
    current = re.sub(r"\s+", " ", current).strip()
    return current


def _avatar_url_for(account_id: int, object_key: "str | None") -> "str | None":
    """아바타 이미지 API URL(같은 출처 bytes 서빙) + 캐시버스터. 미설정 시 None(프론트 Identicon)."""
    if not object_key or account_id <= 0:
        return None
    import hashlib as _hl
    v = _hl.sha256(str(object_key).encode("utf-8")).hexdigest()[:12]
    return f"/api/avatars/{account_id}?v={v}"


def _product_icon_url_for(product_id: int, object_key: "str | None") -> "str | None":
    """제품 아이콘 이미지 API URL + 캐시버스터. 미설정 시 None(프론트 Identicon/기본)."""
    if not object_key or product_id <= 0:
        return None
    import hashlib as _hl
    v = _hl.sha256(str(object_key).encode("utf-8")).hexdigest()[:12]
    return f"/api/products/{product_id}/icon?v={v}"


def _role_icon_url_for(role_id: int, object_key: "str | None") -> "str | None":
    """TASK-0293: 역할 아이콘 이미지 API URL + 캐시버스터. 미설정 시 None(프론트 Identicon).

    제품/아바타(_product_icon_url_for / _avatar_url_for) 와 동형 — object key 해시를
    캐시버스터로 붙여 같은 출처 bytes 서빙 URL 을 만든다.
    """
    if not object_key or role_id <= 0:
        return None
    import hashlib as _hl
    v = _hl.sha256(str(object_key).encode("utf-8")).hexdigest()[:12]
    return f"/api/roles/{role_id}/icon?v={v}"


def _account_conv_file(account_id: int) -> str:
    return str(SESSION_DIR / f"conversation_id.account-{int(account_id)}")


def _conv_file(session_id: str) -> str:
    return str(SESSION_DIR / f"conversation_id.{session_id}")


# ── ITEM-10 b5: 대화 id IO·권한/역할 id 맵·계정 로더·인증 세션 발급·RBAC seed 부트스트랩 ──
# app.py 에서 byte-동치 이동(상단 rebind — AST end_lineno 경계). 폐포는 본 모듈 내 또는 conn 주입.

def _read_conversation_id(path: str) -> str:
    try:
        return Path(path).read_text(encoding="utf-8").strip()
    except Exception:
        return ""

def _write_conversation_id(path: str, conversation_id: str) -> None:
    try:
        Path(path).write_text(str(conversation_id or "").strip(), encoding="utf-8")
    except Exception:
        # best-effort: 현재 대화 포인터 파일 기록 실패는 동작을 막지 않는다 (fail-open).
        logging.getLogger(__name__).warning(
            "_write_conversation_id: persist failed (conversation_id=%s)",
            conversation_id, exc_info=True,
        )

def _permission_id_map(conn) -> dict[str, int]:
    cur = conn.cursor()
    cur.execute("SELECT Id, Code FROM WebPermissions")
    rows = cur.fetchall() or []
    cur.close()
    return {str(code): int(permission_id) for permission_id, code in rows}

def _role_id_map(conn) -> dict[str, int]:
    cur = conn.cursor()
    cur.execute("SELECT Id, RoleKey FROM WebRoles")
    rows = cur.fetchall() or []
    cur.close()
    return {str(role_key): int(role_id) for role_id, role_key in rows}

def _load_account_by_id(conn, account_id: int) -> dict[str, Any] | None:
    rows = _fetch_account_rows(
        conn,
        "a.Id = %s",
        (int(account_id),),
        include_password=False,
        limit_sql="LIMIT 1",
    )
    rows = _decorate_account_rows(conn, rows)
    return rows[0] if rows else None

def _load_account_by_username(conn, username: str) -> dict[str, Any] | None:
    rows = _fetch_account_rows(
        conn,
        "a.Username = %s",
        (username,),
        include_password=True,
        limit_sql="LIMIT 1",
    )
    rows = _decorate_account_rows(conn, rows)
    return rows[0] if rows else None

def _issue_auth_session(conn, account_id: int, request: Request) -> str:
    token = secrets.token_hex(32)
    client_ip = _get_client_ip(request)
    user_agent = str(request.headers.get("user-agent", "") or "")[:255]
    expires_at = datetime.now(timezone.utc) + timedelta(days=AUTH_SESSION_DAYS)
    cur = conn.cursor()
    cur.execute(
        """
INSERT INTO WebAuthSessions (
    AccountId,
    SessionTokenHash,
    RemoteAddr,
    UserAgent,
    ExpiresAt
) VALUES (%s, %s, %s, %s, %s)
        """,
        (
            int(account_id),
            _hash_session_token(token),
            client_ip,
            user_agent,
            expires_at.strftime("%Y-%m-%d %H:%M:%S"),
        ),
    )
    cur.execute(
        "UPDATE WebAccounts SET LastLoginAt = CURRENT_TIMESTAMP WHERE Id = %s",
        (int(account_id),),
    )
    cur.close()
    return token

def _is_safe_model_name(value: str) -> bool:
    text = str(value or "").strip()
    if not text:
        return False
    if len(text) > 64:
        return False
    if not MODEL_RE.match(text):
        return False
    return True

def _create_role_with_permissions(
    conn,
    role_key: str,
    *,
    name: str,
    description: str,
    is_active: bool,
    is_default_signup: bool,
    permission_codes: set[str] | None = None,
) -> int:
    cur = conn.cursor()
    cur.execute(
        """
INSERT INTO WebRoles (RoleKey, Name, Description, IsActive, IsDefaultSignup)
VALUES (%s, %s, %s, %s, %s)
        """,
        (
            role_key,
            name,
            description,
            int(is_active),
            int(is_default_signup),
        ),
    )
    role_id = int(cur.lastrowid or 0)
    permission_map = _permission_id_map(conn)
    for code in sorted(permission_codes or set()):
        permission_id = int(permission_map.get(code) or 0)
        if permission_id <= 0:
            continue
        cur.execute(
            """
INSERT IGNORE INTO WebRolePermissions (RoleId, PermissionId)
VALUES (%s, %s)
            """,
            (role_id, permission_id),
        )
    cur.close()
    return role_id

def _ensure_permission_catalog(conn) -> None:
    cur = conn.cursor()
    for item in PERMISSION_DEFINITIONS:
        # graph-perm-descfix(2026-07-13): Label/Description 를 컬럼 길이(VARCHAR(128)/VARCHAR(255))로
        #   방어적 클립한다. 미클립 시 정의의 description 이 255 자를 초과하면 이 INSERT 가 1406(Data too
        #   long)으로 던지고, 본 함수를 감싸는 _ensure_seed_catchup(fast path)이 통째로 skip 되어
        #   _ensure_seed_roles·permission backfill·기타 부트스트랩 catchup 이 전부 미실행된다(단일 긴 문자열이
        #   전 부트스트랩을 차단하는 fragility — graph-perm-split 배포에서 kb.ingest.manual 설명 301 자로 실측).
        label = str(item["label"])[:128]
        description = str(item["description"])[:255]
        cur.execute(
            """
INSERT INTO WebPermissions (Code, Label, Description, GroupName)
VALUES (%s, %s, %s, %s)
ON DUPLICATE KEY UPDATE
    Label = VALUES(Label),
    Description = VALUES(Description),
    GroupName = VALUES(GroupName)
            """,
            (
                item["code"],
                label,
                description,
                item["group"],
            ),
        )
    cur.close()

def _ensure_default_signup_role(conn) -> None:
    cur = conn.cursor()
    cur.execute(
        """
SELECT Id, RoleKey
FROM WebRoles
WHERE IsActive = 1
ORDER BY IsDefaultSignup DESC, Id ASC
        """
    )
    rows = cur.fetchall() or []
    if not rows:
        cur.close()
        return
    default_row = next((row for row in rows if int(row[0] or 0) > 0 and str(row[1] or "")), None)
    chosen_id = int(default_row[0]) if default_row else int(rows[0][0] or 0)
    pending_id = next((int(role_id) for role_id, role_key in rows if str(role_key) == "pending"), 0)
    if pending_id > 0:
        chosen_id = pending_id
    cur.execute("UPDATE WebRoles SET IsDefaultSignup = 0 WHERE Id <> %s", (chosen_id,))
    cur.execute("UPDATE WebRoles SET IsDefaultSignup = 1 WHERE Id = %s", (chosen_id,))
    cur.close()

def _ensure_seed_roles(conn) -> None:
    role_map = _role_id_map(conn)
    for seed in SEED_ROLE_DEFINITIONS:
        if seed["key"] in role_map:
            continue
        _create_role_with_permissions(
            conn,
            seed["key"],
            name=seed["name"],
            description=seed["description"],
            is_active=True,
            is_default_signup=bool(seed["is_default_signup"]),
            permission_codes=set(seed["permissions"]),
        )
    _ensure_default_signup_role(conn)
    # 기존 admin role 에 신규 권한(product.manage, system_prompt.manage.role.any) 보정
    cur = conn.cursor()
    cur.execute("SELECT Id FROM WebRoles WHERE RoleKey = %s LIMIT 1", ("admin",))
    admin_row = cur.fetchone()
    cur.close()
    if admin_row:
        admin_role_id = int(admin_row[0] or 0)
        permission_map = _permission_id_map(conn)
        cur = conn.cursor()
        for code in (
            "product.manage",
            "system_prompt.manage.role.any",
            "conversation.share.create",
            "conversation.duplicate.own",
            "conversation.duplicate.any",
            # TASK-0073 Phase A3: admin 의 audit 권한 4건 catchup (모든 audit 권한 grant).
            "audit.read.own",
            "audit.read.any",
            "audit.export",
            "audit.purge",
            # TASK-0095: admin 의 전역 시스템 프롬프트 read/write 2건 catchup.
            "system_prompt.global.read",
            "system_prompt.global.write",
            # TASK-0094 Sprint 1 Phase 3: admin 의 첨부 4건 catchup (upload/read × own/any).
            "conversation.attachment.upload.own",
            "conversation.attachment.upload.any",
            "conversation.attachment.read.own",
            "conversation.attachment.read.any",
            # TASK-0161: admin 의 attachment.execute_sql_on.own/.any catchup 제거 (거짓 컨트롤).
            # TASK-0136 (#11): admin 의 LLM 사용량 조회 권한 catchup (운영자 전용 비용 가시성).
            "console.usage.read",
            # TASK-0228: admin 의 insight 분석 초기화 권한 catchup (파괴적 — 운영자 전용).
            "insight.reset",
            # TASK-0273: admin 의 보관 대화 조회 권한 catchup (오용 방지 감사 — 운영자 전용).
            "conversation.archive.read.any",
            # TASK-0288: admin 의 데이터소스 read/manage + 제품 read catchup. **필수** —
            # 미보정 시 신규 게이트 적용 후 기존 admin 역할이 datasource 관리권/제품 조회권을
            # 잃는다(lockout). product.manage 는 기존 catchup 에 이미 포함됨.
            "datasource.read",
            "datasource.manage",
            "product.read",
            # TASK-20260623T030418-quota-rbac-permission: admin 의 LLM 사용 한도 조회/조절 catchup. **필수** —
            # 한도 게이트를 console.manage→quota.read/manage 로 전환했으므로, 기존 배포 admin 역할이
            # 본 catchup 없이는 한도 조회·조절권을 잃는다(lockout, PB-0008 적발). 신규 권한은 role 생성
            # 시 seed=set(PERMISSION_CODES)로만 부여되어 기존 admin row 에는 retroactive 미적용.
            "quota.read",
            "quota.manage",
            # TASK-20260624-item11-metadata-glossary-enum (ITEM-11 MVP-1): admin 의 메타데이터 수동
            # 등록/편집 권한 catchup. **필수** — 신규 권한은 role 생성 시 seed=set(PERMISSION_CODES)로만
            # 부여되어 기존 배포 admin row 에는 retroactive 미적용. 미보정 시 콘솔에 메타데이터 탭이
            # 노출되지 않는다(kb.ingest.manual 게이트).
            "kb.ingest.manual",
            # graph-panel-perms(task4): 메타데이터 세부 권한(B안 분리) admin catchup. **필수** — 신규 권한은
            # role 생성 시 seed 로만 부여되어 기존 배포 admin row 에는 미적용. (묶음 함의로 effective 보유되나,
            # grid 표시·명시 부여 정합을 위해 explicit catchup.)
            "metadata.glossary.manage",
            "metadata.enum.manage",
            "metadata.table.manage",
            "metadata.column.manage",
            "metadata.graph.read",
            # graph-analyze-perm(Critical §12.3, 2026-07-14): admin 의 그래프 AI 능동 분석 실행 권한 catchup.
            # **필수** — 신규 권한은 role 생성 시 seed 로만 부여되어 기존 배포 admin row 에는 미적용. 미보정 시
            # 기존 admin 이 그래프 뷰의 '능동 분석' 버튼·메뉴를 잃는다(lockout — graph.read 가 더 이상 실행을
            # 함의하지 않으므로). operator/sales/pending 미부여(least-privilege).
            "metadata.graph.analyze",
            # TASK-AIOPS: admin 의 AI 운영 현황 조회 권한 catchup. **필수** — 신규 권한은 role 생성 시
            # seed=set(PERMISSION_CODES)로만 부여되어 기존 배포 admin row 에는 retroactive 미적용.
            # 미보정 시 기존 admin 이 AI 운영 현황 탭을 못 본다(lockout, PB-0008 적발). operator/sales/dba 미부여.
            "console.aiops.read",
            # TASK-20260707-kb-candidate-adoption (§18.8 보안 렌즈 MEDIUM 적발): 대화 자율수집 검수 권한
            # catchup. **필수** — 이 3건은 role 생성 seed(=set(PERMISSION_CODES))로만 부여되고 기존
            # 배포 admin row 에는 retroactive 미적용이라, catchup 없이는 기존 admin 이 "채택 인박스"
            # (kb.glossary.curate ∪ kb.enum.curate 게이트)·"샘플 검수"(kb.sample.curate) 탭·API 를 403 으로
            # 잃는다(fail-closed lockout). kb.glossary.curate/kb.sample.curate 는 도입 cycle 에서 본 목록
            # 보정이 누락됐던 잠재 gap 을 함께 해소(INSERT IGNORE 멱등이라 이미 보유 시 무해).
            "kb.glossary.curate",
            "kb.sample.curate",
            "kb.enum.curate",
            # feature-0018(런타임 설정, main 병합분): admin 의 런타임 설정(실행 타임아웃·모델 추론 예산)
            # read/write 2건 catchup. **필수** — 신규 권한은 role 생성 시 seed=set(PERMISSION_CODES)로만
            # 부여되어 기존 배포 admin row 에는 retroactive 미적용. 미보정 시 기존 admin 이 `시스템 > 설정`
            # 의 신규 항목을 못 본다(lockout). operator/sales/dba 미부여(least-privilege).
            "system.runtime.read",
            "system.runtime.write",
            # perm-category-hier(Critical §12.3, 2026-07-14): admin 의 카테고리 접근 권한 5종 catchup.
            # **필수** — 신규 권한은 role 생성 시 seed=set(PERMISSION_CODES)로만 부여되어 기존 배포
            # admin row 에는 retroactive 미적용. 미보정 시 탭 게이트(ADMIN_TAB_CATEGORY_ACCESS AND)
            # 적용 후 기존 admin 이 콘솔 전 카테고리를 잃는다(lockout). 커스텀 역할은
            # _backfill_console_category_access_v1 이 1회 보정(접근 무손실).
            "console.account.access",
            "console.product.access",
            "console.audit.access",
            "console.kb.access",
            "console.system.access",
            # perm-atomic-split(Critical §12.3, 2026-07-15): admin 의 원자 단위 23종 catchup.
            # **필수** — 신규 권한은 role 생성 시 seed 로만 부여되어 기존 배포 admin row 미적용.
            # 엔드포인트 enforcement 가 원자 단위로 전환되므로 미보정 시 admin lockout(런타임
            # 함의가 안전망이나 explicit 부여로 grid 표시·저장 정합 확보).
            "metadata.glossary.read", "metadata.glossary.create", "metadata.glossary.update", "metadata.glossary.delete",
            "metadata.enum.read", "metadata.enum.create", "metadata.enum.update", "metadata.enum.delete",
            "metadata.table.read", "metadata.table.create", "metadata.table.update", "metadata.table.delete",
            "metadata.column.read", "metadata.column.create", "metadata.column.update", "metadata.column.delete",
            "product.create", "product.update", "product.delete",
            "datasource.create", "datasource.update", "datasource.delete", "datasource.test",
            # feature-0021(redteam-review): admin 의 AI 추론 구조 조회 catchup. **필수** — 신규 권한은
            # role 생성 시 seed=set(PERMISSION_CODES)로만 부여되어 기존 배포 admin row 에는 retroactive
            # 미적용. 미보정 시 기존 admin 이 `감사 > AI 추론` 탭을 못 본다(lockout). 타 역할 미부여.
            "console.reasoning.read",
            # feature-0024-conversation-folders: admin 의 대화 폴더 권한 catchup. **필수** —
            # 신규 권한은 role 생성 시 seed=set(PERMISSION_CODES)로만 부여되어 기존 배포 admin row
            # 에는 retroactive 미적용. 미보정 시 기존 admin 이 폴더 조회·관리(사이드바 폴더 UI·
            # /api/folders)를 잃는다(fail-closed lockout). 폴더는 **엄격한 개인** 오버레이라 own 만
            # 존재(folder.*.any 폐지 — 프라이버시). operator/sales/dba/pending 미부여(least-privilege).
            "folder.list.own",
            "folder.manage.own",
        ):
            permission_id = int(permission_map.get(code) or 0)
            if permission_id <= 0:
                continue
            cur.execute(
                """
INSERT IGNORE INTO WebRolePermissions (RoleId, PermissionId)
VALUES (%s, %s)
                """,
                (admin_role_id, permission_id),
            )
        cur.close()
    # REQ-20260514-0001 / REQ-20260518-0001 / TASK-0073 Phase A3: operator/sales role 에 신규 권한 catchup.
    # sales 권한 정합 (대화 생성·실행 가능한 role 은 자기 대화 삭제도 가능해야 한다):
    #   conversation.delete.own 을 sales catchup 에 추가 (기존 operator 는 이미 보유, INSERT IGNORE 로 안전).
    cur = conn.cursor()
    cur.execute("SELECT Id FROM WebRoles WHERE RoleKey IN ('operator', 'sales')")
    role_rows = cur.fetchall() or []
    cur.close()
    if role_rows:
        permission_map = _permission_id_map(conn)
        catchup_codes = (
            "conversation.share.create",
            "conversation.duplicate.own",
            # 대화 생성·실행 role 의 자기 대화 삭제 권한 (sales 정합 fix).
            "conversation.delete.own",
            # TASK-0073 Phase A3: 모든 role 에 audit.read.own auto-grant.
            "audit.read.own",
            # TASK-0094 Sprint 1 Phase 3: operator/sales 의 첨부 upload/read own.
            "conversation.attachment.upload.own",
            "conversation.attachment.read.own",
            # TASK-0161: operator/sales 의 attachment.execute_sql_on.own catchup 제거 (거짓 컨트롤).
        )
        catchup_pids = [
            int(permission_map.get(code) or 0)
            for code in catchup_codes
        ]
        cur = conn.cursor()
        for row in role_rows:
            role_id = int((row[0] if isinstance(row, (list, tuple)) else row.get("Id")) or 0)
            if role_id <= 0:
                continue
            for pid in catchup_pids:
                if pid <= 0:
                    continue
                cur.execute(
                    "INSERT IGNORE INTO WebRolePermissions (RoleId, PermissionId) VALUES (%s, %s)",
                    (role_id, pid),
                )
        cur.close()
    # TASK-0073 Phase A3 (Eng review E9): dba role catchup. SEED_ROLE_DEFINITIONS 에는
    # 부재하나 DB 에 수동 INSERT 된 경우가 존재 (TASK-0060 5 role list 참조). dba 가
    # 있으면 audit.read.own + .any + .export 3 code grant (.purge 는 admin only).
    cur = conn.cursor()
    cur.execute("SELECT Id FROM WebRoles WHERE RoleKey = 'dba' LIMIT 1")
    dba_row = cur.fetchone()
    cur.close()
    if dba_row:
        dba_role_id = int(dba_row[0] or 0)
        if dba_role_id > 0:
            permission_map = _permission_id_map(conn)
            cur = conn.cursor()
            for code in (
                "audit.read.own",
                "audit.read.any",
                "audit.export",
                # TASK-0094 Sprint 1 Phase 3: dba 도 첨부 read.own catchup (운영 모니터링 자격).
                "conversation.attachment.read.own",
                # perm-category-hier(2026-07-14): dba 는 감사 모니터링 role — 감사 카테고리 접근 게이트
                # 동반 부여(콘솔 진입권 console.access 이 없으면 inert, 있으면 감사 탭 노출 보존).
                "console.audit.access",
            ):
                pid = int(permission_map.get(code) or 0)
                if pid <= 0:
                    continue
                cur.execute(
                    "INSERT IGNORE INTO WebRolePermissions (RoleId, PermissionId) VALUES (%s, %s)",
                    (dba_role_id, pid),
                )
            cur.close()
    # TASK-0073 Phase A3: pending role 에도 audit.read.own catchup.
    cur = conn.cursor()
    cur.execute("SELECT Id FROM WebRoles WHERE RoleKey = 'pending' LIMIT 1")
    pending_row = cur.fetchone()
    cur.close()
    if pending_row:
        pending_role_id = int(pending_row[0] or 0)
        if pending_role_id > 0:
            permission_map = _permission_id_map(conn)
            cur = conn.cursor()
            # TASK-0094 Sprint 1 Phase 3 (D21, R-F14): pending 은 audit.read.own +
            # conversation.attachment.read.own (metadata only — bytes download 는 Phase 5
            # endpoint 의 application-level deny). upload 권한 없음.
            for code in ("audit.read.own", "conversation.attachment.read.own"):
                pid = int(permission_map.get(code) or 0)
                if pid <= 0:
                    continue
                cur.execute(
                    "INSERT IGNORE INTO WebRolePermissions (RoleId, PermissionId) VALUES (%s, %s)",
                    (pending_role_id, pid),
                )
            cur.close()
    # 폐기 권한 정리 catchup (기존 DB 에 남아 있는 레코드 제거 — idempotent DELETE IGNORE 패턴).
    # 1) conversation.suggestions.read: PERMISSION_DEFINITIONS 에서 제거됨 (conversation.ask 에 내포).
    #    모든 롤에서 WebRolePermissions 행 삭제.
    # 2) conversation.file.read.own: pending 롤은 조회 전용(read-only) 의도 — 결과 파일 다운로드 불필요.
    #    pending 롤에서만 WebRolePermissions 행 삭제.
    _cleanup_deprecated_role_permissions(conn)
    # TASK-0164: 위에서 링크가 제거된 완전-폐기 권한의 고아 WebPermissions catalog 행도 정리.
    _prune_orphaned_permission_catalog(conn)
    # graph-perm-split(Critical §12.3, 2026-07-13): 그래프 뷰 권한을 메타데이터 관리 묶음에서 분리하며,
    #   분리 시점의 기존 묶음 보유 principal 의 그래프 접근을 1회 backfill 로 보존(B안 = 접근 보존, 비파괴).
    _backfill_graph_perm_split_v1(conn)
    # perm-atomic-split(Critical §12.3, 2026-07-15): 묶음(manage·kb.ingest.manual) 보유 principal 에
    #   원자 단위(read/create/update/delete 등)를 explicit 전개 — grid 표시 정합 + 접근 무손실.
    #   **console-category-access-v1 보다 먼저** 실행해 fresh install 에서 묶음-only role 도 원자
    #   단위를 얻은 뒤 카테고리 접근 backfill 의 leaves 판정(원자 기준)에 걸리게 한다(순서 계약).
    _backfill_atomic_perm_split_v1(conn)
    # perm-category-hier(Critical §12.3, 2026-07-14): 카테고리 접근 권한 5종 도입 시점의 기존 principal
    #   접근을 1회 backfill 로 보존(console.access + 카테고리 세부 권한 보유자에 접근 권한 자동 부여).
    _backfill_console_category_access_v1(conn)
    # feature-0024-conversation-folders(사용자 결정 2026-07-23): conversation.create 보유 역할 전체에
    #   folder.list.own/folder.manage.own 을 1회 backfill 로 부여(폴더=대화 만드는 모두의 개인 기능).
    _backfill_folder_perms_v1(conn)


def _backfill_folder_perms_v1(conn) -> None:
    """feature-0024(사용자 결정 2026-07-23) — 대화 폴더는 대화를 만들 수 있는 모든 역할의 개인 기능.

    도입 시점의 기존 배포에서 `conversation.create` 를 명시 보유한 **모든 역할**에
    `folder.list.own` + `folder.manage.own` 을 1회 부여한다. SEED_ROLE_DEFINITIONS 는 operator/sales
    신규 시드만 커버하므로, 배포 전용 역할(dba/dev_server/dos_web/usermanager 등 시드 밖)은 본 동적
    backfill 이 conversation.create 보유 여부로 커버한다(역할명 하드코딩 없이 미래 역할도 자동 포함).

    **1회 guard**(WebSchemaMigrations 마커): 매 startup 무조건 실행하면 admin 이 특정 역할의 폴더
    권한을 의도적으로 회수해도 재기동마다 재부여돼 admin 통제를 무력화하므로, 정확히 1회만 부여하고
    마커를 남긴다(이후 역할별 부여/회수는 콘솔 admin 통제 — folder.*.own 은 conversation 카테고리
    그리드에 노출). best-effort — 마커 실패 시 다음 startup 재시도(INSERT IGNORE 라 무해).
    graph-perm-split 와 동일 규약: fast/slow 양 경로 호출 대비 마커 테이블 IF NOT EXISTS 자족 보장.
    """
    try:
        cur = conn.cursor()
        cur.execute(
            """
CREATE TABLE IF NOT EXISTS WebSchemaMigrations (
    MigrationKey VARCHAR(191) NOT NULL PRIMARY KEY,
    AppliedAt DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """
        )
        cur.execute(
            "SELECT 1 FROM WebSchemaMigrations WHERE MigrationKey = %s LIMIT 1",
            (_FOLDER_PERMS_BROADEN_MIGRATION_KEY,),
        )
        already = cur.fetchone()
        cur.close()
    except Exception:
        return
    if already:
        return
    permission_map = _permission_id_map(conn)
    conv_create_pid = int(permission_map.get("conversation.create") or 0)
    list_pid = int(permission_map.get("folder.list.own") or 0)
    manage_pid = int(permission_map.get("folder.manage.own") or 0)
    if conv_create_pid > 0 and list_pid > 0 and manage_pid > 0:
        cur = conn.cursor()
        # conversation.create 를 명시 보유한 역할에 folder.list.own + folder.manage.own 부여(멱등).
        for target_pid in (list_pid, manage_pid):
            cur.execute(
                """
INSERT IGNORE INTO WebRolePermissions (RoleId, PermissionId)
SELECT DISTINCT rp.RoleId, %s
FROM WebRolePermissions rp
WHERE rp.PermissionId = %s
                """,
                (target_pid, conv_create_pid),
            )
        cur.close()
    # 마커 기록(멱등) — 권한 id 미해석 시엔 마커 미기록으로 다음 startup 재시도.
    if conv_create_pid > 0 and list_pid > 0 and manage_pid > 0:
        try:
            cur = conn.cursor()
            cur.execute(
                "INSERT IGNORE INTO WebSchemaMigrations (MigrationKey) VALUES (%s)",
                (_FOLDER_PERMS_BROADEN_MIGRATION_KEY,),
            )
            cur.close()
        except Exception:
            pass


def _backfill_graph_perm_split_v1(conn) -> None:
    """graph-perm-split(Critical §12.3, 사용자 결정 2026-07-13) — 1회성 접근 보존 backfill.

    그래프 뷰 권한 `metadata.graph.read` 를 "메타데이터 관리" 묶음(`kb.ingest.manual`)의 함의
    (`_METADATA_MANUAL_IMPLIES`)에서 제거하면, 그동안 묶음 보유만으로 그래프에 접근하던 기존 배포의
    principal(역할/계정 오버라이드)이 접근을 잃는다. 이를 막기 위해 **분리 전환 시점에 한 번만** 다음을
    수행해 그때의 effective 접근을 명시 grant 로 고정한다(B안 = 접근 보존).

    - 대상 1 (역할): `kb.ingest.manual` 을 명시 보유한 role 에 `metadata.graph.read` role 권한 부여.
    - 대상 2 (계정 오버라이드): `kb.ingest.manual` 에 ALLOW 오버라이드를 가졌고 `metadata.graph.read` 에는
      아직 오버라이드가 없는 account 에 `metadata.graph.read` ALLOW 오버라이드 부여. (graph.read 에 명시
      DENY 를 이미 둔 account 는 대상 아님 — least-privilege 존중, 기존 함의도 DENY 를 존중했음.)

    **멱등 1회 guard**: WebSchemaMigrations 에 `_GRAPH_PERM_SPLIT_MIGRATION_KEY` 마커가 있으면 skip.
    매 startup 무조건 실행하면 분리 이후 새로 묶음을 받은 역할까지 graph.read 를 자동 획득해 분리가
    무력화되므로, 정확히 1회만 수행하고 마커를 남긴다. 전 과정은 best-effort — 마커 테이블 부재 등으로
    실패하면(예: 일부 테스트 컨텍스트) 조용히 skip 하고, 마커 미기록 시 다음 startup 에 재시도한다
    (INSERT IGNORE 라 재시도 무해).
    """
    try:
        cur = conn.cursor()
        # 마커 테이블 자족 보장 — 운영 재기동은 slow path(_ensure_web_tables)를 안 타고 fast path
        # (_ensure_seed_catchup)만 타는데, WebSchemaMigrations DDL 은 slow path 에만 있다. 본 함수가
        # _ensure_seed_roles 를 통해 fast/slow 양 경로에서 호출되므로, 마커 테이블을 직접 IF NOT EXISTS
        # 로 보장해 경로 독립적으로 동작시킨다(미보장 시 fast path 에서 SELECT 예외→backfill 영구 skip→
        # 기존 묶음 보유자 그래프 접근 상실이라는 접근보존 위반이 운영 배포에서 조용히 발생).
        cur.execute(
            """
CREATE TABLE IF NOT EXISTS WebSchemaMigrations (
    MigrationKey VARCHAR(191) NOT NULL PRIMARY KEY,
    AppliedAt DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """
        )
        cur.execute(
            "SELECT 1 FROM WebSchemaMigrations WHERE MigrationKey = %s LIMIT 1",
            (_GRAPH_PERM_SPLIT_MIGRATION_KEY,),
        )
        already = cur.fetchone()
        cur.close()
    except Exception:
        # 마커 테이블 생성/조회 실패(DB error 등) — 이번 startup 에서는 안전하게 skip (다음 startup 재시도).
        return
    if already:
        return
    permission_map = _permission_id_map(conn)
    bundle_pid = int(permission_map.get("kb.ingest.manual") or 0)
    graph_pid = int(permission_map.get("metadata.graph.read") or 0)
    if bundle_pid > 0 and graph_pid > 0:
        cur = conn.cursor()
        # 대상 1 — 역할 backfill: 묶음 보유 role 에 graph.read 명시 부여.
        cur.execute(
            """
INSERT IGNORE INTO WebRolePermissions (RoleId, PermissionId)
SELECT rp.RoleId, %s
FROM WebRolePermissions rp
WHERE rp.PermissionId = %s
            """,
            (graph_pid, bundle_pid),
        )
        # 대상 2 — 계정 오버라이드 backfill: 묶음 ALLOW override 보유 + graph.read override 부재 account.
        cur.execute(
            """
INSERT IGNORE INTO WebAccountPermissionOverrides (AccountId, PermissionId, OverrideValue)
SELECT ao.AccountId, %s, 'allow'
FROM WebAccountPermissionOverrides ao
WHERE ao.PermissionId = %s
  AND LOWER(ao.OverrideValue) = 'allow'
  AND NOT EXISTS (
    SELECT 1 FROM WebAccountPermissionOverrides ao2
    WHERE ao2.AccountId = ao.AccountId AND ao2.PermissionId = %s
  )
            """,
            (graph_pid, bundle_pid, graph_pid),
        )
        # 대상 3 — 과잉부여 방지(접근 상태 고정): role 이 묶음을 보유(→위 대상1 로 graph.read 명시 부여됨)하지만
        #   계정이 묶음을 DENY override 로 끈 account 는, 분리 전에는 묶음이 꺼져 graph 도 함의되지 않아 접근이 없었다.
        #   대상1 이 role 에 graph.read 를 준 뒤로는 이 account 가 graph.read override 없이 접근을 새로 얻게 되므로,
        #   graph.read override 부재 시 graph.read DENY override 를 부여해 분리 전 effective(=그래프 없음)를 고정한다.
        #   (기존 함의도 묶음 DENY 를 존중해 graph 를 안 줬음 — 동치 보존. graph.read override 가 이미 있으면 존중.)
        cur.execute(
            """
INSERT IGNORE INTO WebAccountPermissionOverrides (AccountId, PermissionId, OverrideValue)
SELECT ao.AccountId, %s, 'deny'
FROM WebAccountPermissionOverrides ao
JOIN WebAccounts acc ON acc.Id = ao.AccountId
JOIN WebRolePermissions rp ON rp.RoleId = acc.RoleId AND rp.PermissionId = %s
WHERE ao.PermissionId = %s
  AND LOWER(ao.OverrideValue) = 'deny'
  AND NOT EXISTS (
    SELECT 1 FROM WebAccountPermissionOverrides ao2
    WHERE ao2.AccountId = ao.AccountId AND ao2.PermissionId = %s
  )
            """,
            (graph_pid, bundle_pid, bundle_pid, graph_pid),
        )
        cur.close()
        # 마커 기록 — **backfill 본문이 실제 실행된 경우에만** 1회 완료 표시(재실행 방지). FINDING-B(보안리뷰):
        #   bundle_pid/graph_pid 부재로 위 본문을 건너뛴 상태에서 마커를 남기면, 마커만 "done" 인 채 backfill 은
        #   영구 미실행 → 전원 접근 상실 오기록이 된다. catalog hydrate 가 _ensure_seed_roles 앞이라 정상경로에선
        #   pid 가 항상 존재하나, 방어적으로 마커 기록을 body 실행(if 블록)에 결합해 다음 startup 재시도를 보장한다.
        try:
            cur = conn.cursor()
            cur.execute(
                "INSERT IGNORE INTO WebSchemaMigrations (MigrationKey) VALUES (%s)",
                (_GRAPH_PERM_SPLIT_MIGRATION_KEY,),
            )
            cur.close()
        except Exception:
            # 마커 기록 실패 — 다음 startup 재시도(INSERT IGNORE 라 backfill 재적용 무해).
            pass


def _backfill_atomic_perm_split_v1(conn) -> None:
    """perm-atomic-split(Critical §12.3, 사용자 승인 2026-07-15) — 묶음→원자 단위 1회 explicit 전개.

    묶음 권한(metadata.*.manage·kb.ingest.manual·product.manage·datasource.manage)을 grid 에서
    숨기고 원자 단위(read/create/update/delete/test)로 분리함에 따라, 기존 묶음 보유 principal 의
    부여 상태를 원자 단위 explicit grant 로 고정한다. 런타임 함의(_PERMISSION_BUNDLE_IMPLIES)가
    effective 접근을 이미 보존하지만, grid 는 explicit grant 기준 표시라 backfill 없이는 묶음
    보유 role 의 원자 체크박스가 비어 보인다(관리자 혼란 + 저장 시 소실 위험).

    - 대상 1 (역할): 묶음 명시 보유 role 에 그 묶음의 transitive 원자 집합 부여.
    - 대상 2 (계정 오버라이드): 묶음 ALLOW override 계정에 원자 ALLOW override(부재 시).
    - 대상 3 (계정 오버라이드×역할): 묶음 DENY override + 역할이 묶음 보유 → 원자 DENY override
      (부재 시) — 분리 전 effective(묶음 꺼짐=원자 없음)를 고정(graph-perm-split 대상3 동형).

    멱등 1회 guard: WebSchemaMigrations `_ATOMIC_PERM_SPLIT_MIGRATION_KEY`. best-effort —
    실패 시 조용히 skip, 마커 미기록이면 다음 startup 재시도(INSERT IGNORE 무해).
    """
    try:
        cur = conn.cursor()
        cur.execute(
            """
CREATE TABLE IF NOT EXISTS WebSchemaMigrations (
    MigrationKey VARCHAR(191) NOT NULL PRIMARY KEY,
    AppliedAt DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """
        )
        cur.execute(
            "SELECT 1 FROM WebSchemaMigrations WHERE MigrationKey = %s LIMIT 1",
            (_ATOMIC_PERM_SPLIT_MIGRATION_KEY,),
        )
        already = cur.fetchone()
        cur.close()
    except Exception:
        return
    if already:
        return
    # transitive 전개(kb.ingest.manual → manage 4종 → 각 원자) — 묶음별 최종 원자 집합으로 평탄화.
    def _expand(bundle: str) -> set[str]:
        out: set[str] = set()
        stack = list(_PERMISSION_BUNDLE_IMPLIES.get(bundle, ()))
        while stack:
            code = stack.pop()
            if code in out:
                continue
            out.add(code)
            stack.extend(_PERMISSION_BUNDLE_IMPLIES.get(code, ()))
        return out

    permission_map = _permission_id_map(conn)
    plan: list[tuple[int, list[int]]] = []  # (bundle_pid, atomic_pids)
    for bundle in _PERMISSION_BUNDLE_IMPLIES:
        bundle_pid = int(permission_map.get(bundle) or 0)
        atomic_pids = [int(permission_map.get(c) or 0) for c in sorted(_expand(bundle))]
        atomic_pids = [pid for pid in atomic_pids if pid > 0]
        if bundle_pid <= 0 or not atomic_pids:
            # 원자 카탈로그 미hydrate — 마커 없이 반환(다음 startup 재시도, FINDING-B 규약).
            return
        plan.append((bundle_pid, atomic_pids))
    cur = conn.cursor()
    for bundle_pid, atomic_pids in plan:
        for atomic_pid in atomic_pids:
            # 대상 1 — 역할: 묶음 보유 role 에 원자 부여.
            cur.execute(
                """
INSERT IGNORE INTO WebRolePermissions (RoleId, PermissionId)
SELECT rp.RoleId, %s FROM WebRolePermissions rp WHERE rp.PermissionId = %s
                """,
                (atomic_pid, bundle_pid),
            )
            # 대상 2 — 계정 오버라이드: 묶음 ALLOW → 원자 ALLOW(부재 시).
            cur.execute(
                """
INSERT IGNORE INTO WebAccountPermissionOverrides (AccountId, PermissionId, OverrideValue)
SELECT ao.AccountId, %s, 'allow'
FROM WebAccountPermissionOverrides ao
WHERE ao.PermissionId = %s AND LOWER(ao.OverrideValue) = 'allow'
  AND NOT EXISTS (
    SELECT 1 FROM WebAccountPermissionOverrides ao2
    WHERE ao2.AccountId = ao.AccountId AND ao2.PermissionId = %s
  )
                """,
                (atomic_pid, bundle_pid, atomic_pid),
            )
            # 대상 3 — 묶음 DENY override + 역할 묶음 보유 → 원자 DENY(부재 시): 분리 전 effective 고정.
            cur.execute(
                """
INSERT IGNORE INTO WebAccountPermissionOverrides (AccountId, PermissionId, OverrideValue)
SELECT ao.AccountId, %s, 'deny'
FROM WebAccountPermissionOverrides ao
JOIN WebAccounts acc ON acc.Id = ao.AccountId
JOIN WebRolePermissions rp ON rp.RoleId = acc.RoleId AND rp.PermissionId = %s
WHERE ao.PermissionId = %s AND LOWER(ao.OverrideValue) = 'deny'
  AND NOT EXISTS (
    SELECT 1 FROM WebAccountPermissionOverrides ao2
    WHERE ao2.AccountId = ao.AccountId AND ao2.PermissionId = %s
  )
                """,
                (atomic_pid, bundle_pid, bundle_pid, atomic_pid),
            )
    cur.close()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT IGNORE INTO WebSchemaMigrations (MigrationKey) VALUES (%s)",
            (_ATOMIC_PERM_SPLIT_MIGRATION_KEY,),
        )
        cur.close()
    except Exception:
        pass


def _backfill_console_category_access_v1(conn) -> None:
    """perm-category-hier(Critical §12.3, 사용자 승인 A안 2026-07-14) — 1회성 접근 보존 backfill.

    관리 콘솔 nav 카테고리별 최상위 '접근' 권한 5종(_CONSOLE_CATEGORY_ACCESS_LEAVES 키)을 도입하고
    프론트 탭 노출을 "카테고리 접근 AND 탭 권한"(ADMIN_TAB_CATEGORY_ACCESS)으로 전환하면, 그동안
    console.access + 세부 권한만으로 탭을 보던 기존 배포 principal 이 nav 노출을 잃는다. 이를 막기
    위해 **도입 시점에 한 번만** 그때의 effective 노출을 명시 grant 로 고정한다(접근 무손실).

    - 대상 1 (역할): console.access 와 카테고리 세부 권한을 모두 명시 보유한 role 에 그 카테고리의
      접근 권한을 부여. (console.access 없는 role — operator/sales/pending 의 audit.read.own 등 —
      은 오늘도 콘솔 진입 불가이므로 부여하지 않는다: least-privilege 보존.)
    - 대상 2 (계정 오버라이드): 카테고리 세부 권한에 ALLOW 오버라이드를 가졌고 접근 권한에는 아직
      오버라이드가 없는 account 에 접근 권한 ALLOW 오버라이드 부여.
    - 대상 3 (계정 오버라이드×역할): console.access 를 ALLOW 오버라이드로 얻고 세부 권한은 역할에서
      받는 account — role 이 console.access 미보유라 대상 1 에서 빠지는 조합 — 에 접근 권한 ALLOW
      오버라이드 부여(오늘 탭이 보이던 상태 보존).

    분리 전 카테고리 접근이 없던 principal(콘솔 진입 불가·세부 권한 전무)은 부여 대상이 아니다.
    **멱등 1회 guard**: WebSchemaMigrations 의 _CONSOLE_CATEGORY_ACCESS_MIGRATION_KEY 마커. 매 startup
    재실행 시 backfill 이후 새로 세부 권한만 받은 역할까지 접근 권한을 자동 획득해 계층 게이트가
    무력화되므로 정확히 1회만 수행한다(graph-perm-split-v1 과 동일 규약). best-effort — 실패 시 조용히
    skip 하고 마커 미기록이면 다음 startup 재시도(INSERT IGNORE 라 재시도 무해).
    """
    try:
        cur = conn.cursor()
        # 마커 테이블 자족 보장 — fast path(_ensure_seed_catchup)는 slow path 의 DDL 을 안 타므로
        # 직접 IF NOT EXISTS 로 보장(graph-perm-split-v1 과 동일 — 미보장 시 backfill 영구 skip 위험).
        cur.execute(
            """
CREATE TABLE IF NOT EXISTS WebSchemaMigrations (
    MigrationKey VARCHAR(191) NOT NULL PRIMARY KEY,
    AppliedAt DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """
        )
        cur.execute(
            "SELECT 1 FROM WebSchemaMigrations WHERE MigrationKey = %s LIMIT 1",
            (_CONSOLE_CATEGORY_ACCESS_MIGRATION_KEY,),
        )
        already = cur.fetchone()
        cur.close()
    except Exception:
        # 마커 테이블 생성/조회 실패(DB error 등) — 이번 startup 은 안전하게 skip(다음 startup 재시도).
        return
    if already:
        return
    permission_map = _permission_id_map(conn)
    console_pid = int(permission_map.get("console.access") or 0)
    # 접근 권한 5종 pid 가 전부 hydrate 되어 있어야 본문 실행 — 부분 실행 후 마커를 남기면 남은
    # 카테고리는 영구 미보정이 된다(FINDING-B 규약: 마커는 본문이 전부 실행된 경우에만 기록).
    access_pids = {
        code: int(permission_map.get(code) or 0)
        for code in _CONSOLE_CATEGORY_ACCESS_LEAVES
    }
    if console_pid <= 0 or any(pid <= 0 for pid in access_pids.values()):
        return
    cur = conn.cursor()
    for access_code, leaf_codes in _CONSOLE_CATEGORY_ACCESS_LEAVES.items():
        access_pid = access_pids[access_code]
        leaf_pids = [int(permission_map.get(code) or 0) for code in leaf_codes]
        leaf_pids = [pid for pid in leaf_pids if pid > 0]
        if not leaf_pids:
            continue
        leaf_ph = ", ".join(["%s"] * len(leaf_pids))
        # 대상 1 — 역할: console.access + 카테고리 세부 권한 보유 role 에 접근 권한 부여.
        cur.execute(
            f"""
INSERT IGNORE INTO WebRolePermissions (RoleId, PermissionId)
SELECT DISTINCT rp.RoleId, %s
FROM WebRolePermissions rp
JOIN WebRolePermissions rc ON rc.RoleId = rp.RoleId AND rc.PermissionId = %s
WHERE rp.PermissionId IN ({leaf_ph})
            """,
            (access_pid, console_pid, *leaf_pids),
        )
        # 대상 2 — 계정 오버라이드: 세부 권한 ALLOW override 보유 + 접근 권한 override 부재.
        cur.execute(
            f"""
INSERT IGNORE INTO WebAccountPermissionOverrides (AccountId, PermissionId, OverrideValue)
SELECT DISTINCT ao.AccountId, %s, 'allow'
FROM WebAccountPermissionOverrides ao
WHERE ao.PermissionId IN ({leaf_ph})
  AND LOWER(ao.OverrideValue) = 'allow'
  AND NOT EXISTS (
    SELECT 1 FROM WebAccountPermissionOverrides ao2
    WHERE ao2.AccountId = ao.AccountId AND ao2.PermissionId = %s
  )
            """,
            (access_pid, *leaf_pids, access_pid),
        )
        # 대상 3 — console.access ALLOW override + 역할이 세부 권한 보유(role 은 console.access 미보유
        #   가능) + 접근 권한 override 부재. 오늘 "override 진입 + 역할 세부 권한" 으로 탭이 보이던
        #   조합의 노출 보존.
        cur.execute(
            f"""
INSERT IGNORE INTO WebAccountPermissionOverrides (AccountId, PermissionId, OverrideValue)
SELECT DISTINCT ao.AccountId, %s, 'allow'
FROM WebAccountPermissionOverrides ao
JOIN WebAccounts acc ON acc.Id = ao.AccountId
JOIN WebRolePermissions rp ON rp.RoleId = acc.RoleId AND rp.PermissionId IN ({leaf_ph})
WHERE ao.PermissionId = %s
  AND LOWER(ao.OverrideValue) = 'allow'
  AND NOT EXISTS (
    SELECT 1 FROM WebAccountPermissionOverrides ao2
    WHERE ao2.AccountId = ao.AccountId AND ao2.PermissionId = %s
  )
            """,
            (access_pid, *leaf_pids, console_pid, access_pid),
        )
    cur.close()
    # 마커 기록 — 본문(5 카테고리 전부)이 실행된 경우에만 1회 완료 표시(graph-perm-split FINDING-B 규약).
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT IGNORE INTO WebSchemaMigrations (MigrationKey) VALUES (%s)",
            (_CONSOLE_CATEGORY_ACCESS_MIGRATION_KEY,),
        )
        cur.close()
    except Exception:
        # 마커 기록 실패 — 다음 startup 재시도(INSERT IGNORE 라 backfill 재적용 무해).
        pass


def _cleanup_deprecated_role_permissions(conn) -> None:
    """폐기/정리된 권한을 기존 WebRolePermissions 에서 제거한다 (idempotent)."""
    cur = conn.cursor()
    # 삭제 대상 (code, role_key | None=전체 롤) 쌍 목록.
    removals = [
        ("conversation.suggestions.read", None),         # 전체 롤에서 제거
        ("conversation.file.read.own",    "pending"),    # pending 롤에서만 제거
        # TASK-0161: 거짓 컨트롤 권한 — enforce 미배선(실제 게이트는 allowlist+attachment_reader+sql_guard).
        ("attachment.execute_sql_on.own", None),         # 전체 롤에서 제거
        ("attachment.execute_sql_on.any", None),         # 전체 롤에서 제거
    ]
    for perm_code, role_key in removals:
        cur.execute("SELECT Id FROM WebPermissions WHERE Code = %s LIMIT 1", (perm_code,))
        perm_row = cur.fetchone()
        if not perm_row:
            continue
        perm_id = int(perm_row[0] or 0)
        if perm_id <= 0:
            continue
        if role_key is None:
            cur.execute(
                "DELETE FROM WebRolePermissions WHERE PermissionId = %s",
                (perm_id,),
            )
        else:
            cur.execute("SELECT Id FROM WebRoles WHERE RoleKey = %s LIMIT 1", (role_key,))
            role_row = cur.fetchone()
            if not role_row:
                continue
            role_id = int(role_row[0] or 0)
            if role_id <= 0:
                continue
            cur.execute(
                "DELETE FROM WebRolePermissions WHERE RoleId = %s AND PermissionId = %s",
                (role_id, perm_id),
            )
    cur.close()

def _prune_orphaned_permission_catalog(conn) -> None:
    """TASK-0164: 완전 폐기된(코드가 PERMISSION_DEFINITIONS 에서 사라진) 권한의 고아
    WebPermissions catalog 행을 제거한다 (idempotent, 가드).

    `_cleanup_deprecated_role_permissions` 가 WebRolePermissions 링크를 먼저 지운 뒤
    호출된다. 어떤 롤/계정도 참조하지 않을 때만 catalog 행을 삭제한다(WebRolePermissions
    + WebAccountPermissionOverrides 둘 다 0 참조 가드). FK 제약은 없으나 논리적 순서
    (링크 먼저 → catalog) + 가드로 고아만 제거. 그리드는 PERMISSION_DEFINITIONS 기반이라
    행 잔존도 무해하지만 카탈로그 정합을 위해 정리한다. (역할별 부분 제거 권한
    `conversation.file.read.own` 은 다른 롤에 live 라 prune 대상 아님.)
    """
    prune_codes = [
        "conversation.suggestions.read",   # TASK-0124 폐기
        "attachment.execute_sql_on.own",   # TASK-0161 폐기 (거짓 컨트롤)
        "attachment.execute_sql_on.any",   # TASK-0161 폐기 (거짓 컨트롤)
    ]
    cur = conn.cursor()
    try:
        for perm_code in prune_codes:
            cur.execute("SELECT Id FROM WebPermissions WHERE Code = %s LIMIT 1", (perm_code,))
            row = cur.fetchone()
            if not row:
                continue
            perm_id = int(row[0] or 0)
            if perm_id <= 0:
                continue
            cur.execute("SELECT COUNT(*) FROM WebRolePermissions WHERE PermissionId = %s", (perm_id,))
            if int((cur.fetchone() or [0])[0] or 0) > 0:
                continue  # 아직 롤이 참조 — catalog 보존
            cur.execute("SELECT COUNT(*) FROM WebAccountPermissionOverrides WHERE PermissionId = %s", (perm_id,))
            if int((cur.fetchone() or [0])[0] or 0) > 0:
                continue  # 계정 override 가 참조 — catalog 보존
            cur.execute("DELETE FROM WebPermissions WHERE Id = %s", (perm_id,))
    finally:
        cur.close()

SEED_PRODUCT_DEFINITIONS = (
    {
        "product_key": "KR",
        "name": "Korea",
        "description": "국내 서비스 DB 묶음 (dbgame, dblog, dbauth).",
        "is_default": True,
        "is_active": True,
        "sort_order": 10,
        "databases": [
            {"schema_name": "dbgame", "description": "게임 메타 데이터", "sort_order": 10},
            {"schema_name": "dblog", "description": "전투/이벤트 로그", "sort_order": 20},
            {"schema_name": "dbauth", "description": "계정/인증", "sort_order": 30},
        ],
    },
)

def _ensure_seed_products(conn) -> None:
    cur = conn.cursor()
    cur.execute("SELECT ProductKey FROM WebProducts")
    existing_keys = {str(row[0]) for row in cur.fetchall() or []}
    cur.close()
    if any(seed["product_key"] in existing_keys for seed in SEED_PRODUCT_DEFINITIONS):
        return
    for seed in SEED_PRODUCT_DEFINITIONS:
        if seed["product_key"] in existing_keys:
            continue
        cur = conn.cursor()
        cur.execute(
            """
INSERT INTO WebProducts (ProductKey, Name, Description, IsActive, IsDefault, SortOrder)
VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (
                seed["product_key"],
                seed["name"],
                seed.get("description", ""),
                1 if seed.get("is_active", True) else 0,
                1 if seed.get("is_default", False) else 0,
                int(seed.get("sort_order", 100)),
            ),
        )
        product_id = int(cur.lastrowid or 0)
        cur.close()
        if product_id <= 0:
            continue
        cur = conn.cursor()
        for db in seed.get("databases", []):
            cur.execute(
                """
INSERT IGNORE INTO WebProductDatabases (ProductId, SchemaName, Description, SortOrder)
VALUES (%s, %s, %s, %s)
                """,
                (
                    product_id,
                    str(db["schema_name"]),
                    str(db.get("description", "")),
                    int(db.get("sort_order", 100)),
                ),
            )
        cur.close()


# ── ITEM-10 b6-A: 계정/권한 read-model (적대 분석 판정표 Batch A — retarget 0 검증) ──
# 규칙(판정표 명문화): 테스트가 app-패치하는 심볼을 본 모듈 내부에서 bare-name 호출하는
# 함수를 새로 들여올 때는 패치-관통(우회) 여부를 반드시 사전 census 로 확인한다.
# _account_has_permission(app-패치 11×)의 현행 패치 경로는 직렬화/quota-strip 을 통과하지
# 않음을 전수 확인 — co-move 안전.

def _legacy_permission_codes_from_row(row: dict[str, Any] | None) -> set[str]:
    if not row:
        return set()
    role_key = str(row.get("legacy_role") or row.get("role") or "").strip().lower()
    if role_key == "admin":
        return set(PERMISSION_CODES)
    codes = {
        "conversation.list.own",
        "conversation.read.own",
        "conversation.file.read.own",
    }
    if role_key == "operator":
        if bool(row.get("legacy_can_send_request")):
            codes.update({"conversation.create", "conversation.ask"})
        if bool(row.get("legacy_can_cancel_request")):
            codes.add("conversation.cancel.own")
        if bool(row.get("legacy_can_finalize_request")):
            codes.add("conversation.finalize.own")
        if bool(row.get("legacy_can_delete_conversation")):
            codes.add("conversation.delete.own")
    return codes

def _account_permissions(account: dict[str, Any] | None) -> dict[str, bool]:
    if not account:
        return _empty_permission_map()
    cached = account.get("permissions")
    if isinstance(cached, dict):
        # TASK-0052 Phase 1B: cached map 은 _decorate_account_rows 에서 dynamic catalog 로 빌드됐으므로
        # 그대로 dict() 복사해 dynamic codes (e.g. product.access.<key>) 도 보존한다.
        # 기존엔 `for code in PERMISSION_CODES` 로 iterate 해 dynamic codes 가 silently drop 됐다.
        perms = {str(code): bool(value) for code, value in cached.items()}
    else:
        perms = _empty_permission_map()
    # feature-0023 (REQ-20260722-conversation-api-access): API 토큰 인증 시 유효 권한을
    # 두 겹으로 제약한다(단일 choke-point — _account_has_permission·_account_has_any_permission·
    # _account_has_product_access·직접 .get 소비처가 모두 존중).
    #   (1) positive allowlist: 토큰 Scopes(또는 NULL 이면 안전 기본값 — REV-20260722 HIGH-2,
    #       무제한 금지 fail-closed).
    #   (2) absolute denylist: scope·계정 권한과 무관하게 `*.any`·관리 네임스페이스는 무조건
    #       False(REV-20260722 HIGH-1). allowlist 가 `conversation.` 이라 새어든
    #       conversation.list.any·conversation.archive.read.any(group=audit) 를 여기서 봉인.
    # → 서비스 계정이 관리/교차계정 권한을 보유해도, 토큰이 어떤 scope 여도 관리 콘솔 접근 불가.
    if account.get("_auth_via") == "api_token":
        scopes = account.get("_token_scopes")
        allow = scopes if scopes is not None else list(_API_TOKEN_SAFE_DEFAULT_SCOPES)
        perms = {
            code: (
                bool(granted)
                # model-access-rbac(2026-07-28): `model.access.*` 는 **scope allowlist 면제**.
                # 근거: scope 는 "토큰이 어떤 *동작*을 할 수 있나"(conversation./product.access.)를
                # 제한하는 축이고, 모델 tier 는 **서비스 계정의 역할 권한**이 정하는 별 축이다.
                # 면제하지 않으면 (a) 이미 발급된 토큰(Scopes='conversation.' 등)이 전부
                # `/api/ask` 403 으로 죽고(feature-0023 외부 AI 경로 파손), (b) 모델을 추가할
                # 때마다 기존 토큰 scope 문자열을 일괄 재발급해야 한다. 면제해도 통제는 유지된다 —
                # `bool(granted)`(서비스 계정 역할이 그 모델을 보유해야 함) + 아래 절대 denylist +
                # `/api/ask` 게이트가 그대로 적용되므로, 저권한 서비스 계정에서 opus 를 해제하면
                # 토큰도 opus 를 못 쓴다.
                and (
                    model_catalog.is_model_permission_code(code)
                    or _permission_in_token_scopes(code, allow)
                )
                and not _api_token_permission_denied(code)
            )
            for code, granted in perms.items()
        }
    return perms

def _account_has_permission(account: dict[str, Any] | None, permission: str) -> bool:
    permissions = _account_permissions(account)
    return bool(permissions.get(permission))

def _account_has_any_permission(account: dict[str, Any] | None, *permissions: str) -> bool:
    """주어진 권한 중 하나라도 보유하면 True. read/manage superset 게이팅에 사용
    (TASK-0288: GET 조회는 `.read` 또는 `.manage` 보유 시 허용 — manage ⊇ read)."""
    perms = _account_permissions(account)
    return any(bool(perms.get(code)) for code in permissions)

def _role_payload(account: dict[str, Any] | None) -> dict[str, Any] | None:
    role_id = int(account.get("role_id") or 0) if account else 0
    if role_id <= 0:
        return None
    return {
        "id": role_id,
        "key": str(account.get("role_key") or ""),
        "name": str(account.get("role_name") or ""),
        "description": str(account.get("role_description") or ""),
        "is_active": bool(account.get("role_is_active", True)),
        "is_default_signup": bool(account.get("role_is_default_signup")),
    }

def _serialize_account(
    account: dict[str, Any] | None,
    *,
    include_permissions: bool = False,
) -> dict[str, Any] | None:
    """계정 정보를 응답 payload 로 직렬화한다.

    TASK-0098 (REQ-20260522-0002, Critical §12.3): default `False` — 7 self callsite
    (bootstrap, signup, login, GET `/api/auth/me`, PATCH `/api/auth/me` 2 곳) 가
    default 호출 → raw permission map 노출 차단. admin-context 3 callsite
    (`_list_accounts_for_admin`, admin account update, 신규 `/api/admin/me`) 는
    `include_permissions=True` 명시. `role` 객체는 self 응답에도 유지.

    `console_access` 플래그: TASK-0098 단순화로 인해 frontend can() 가 항상 true
    를 반환하게 되어 관리 콘솔 버튼이 모든 사용자에게 노출되는 이슈 수정.
    permissions 전체 노출 없이 UI gate 에 필요한 최소 정보만 제공한다.
    """
    if not account:
        return None
    payload: dict[str, Any] = {
        "id": int(account.get("id") or 0),
        "username": str(account.get("username") or ""),
        "role": _role_payload(account),
        "is_active": bool(account.get("is_active")),
        "deleted_at": str(account.get("deleted_at") or "") or None,
        "deleted_by_account_id": int(account.get("deleted_by_account_id") or 0) or None,
        "created_at": str(account.get("created_at") or "") or None,
        "approved_at": str(account.get("approved_at") or "") or None,
        "last_login_at": str(account.get("last_login_at") or "") or None,
        "last_conversation_id": str(account.get("last_conversation_id") or ""),
        # TASK-0061 Phase 6 (REQ-20260515-0008 / AC-0095): 다음 로그인 시 비밀번호 강제 변경.
        "must_change_password": bool(account.get("must_change_password")),
        # TASK-20260619T021356-login-attempt-limit (보안 ②): 로그인 실패 잠금 상태(DB NOW() 기준 is_locked).
        # admin UI 가 잠금 배지/해제 버튼 노출에 사용. locked_until=자동 해제 시각.
        "is_locked": bool(account.get("is_locked")),
        "locked_until": str(account.get("locked_until_at") or "") or None,
        # TASK-20260619T040000-two-factor-auth (보안 ⑥): 2FA 활성 여부(프로필 토글 + admin 배지/해제).
        "totp_enabled": bool(account.get("totp_enabled")),
        # UI gate 전용 최소 플래그 — permissions 전체 노출 없이 관리 콘솔 접근 여부만 전달.
        "console_access": _account_has_permission(account, "console.access"),
        # TASK-0268: 아바타 이미지 URL. 설정 시 /api/avatars/<id>(같은 출처 bytes 서빙) +
        # object key 해시 캐시버스터. NULL=미설정 → 프론트가 Identicon 렌더.
        "avatar_url": _avatar_url_for(int(account.get("id") or 0), account.get("avatar_object_key")),
        # TASK-20260619T034522-oauth-google-foundation: OAuth 편입 식별. email(연동 시 채워짐, 없으면 None)
        # 과 auth_provider("google" 등, 없으면 None — 로컬 계정). 민감 토큰/secret 은 비노출.
        "email": str(account.get("email") or "") or None,
        "auth_provider": str(account.get("auth_provider") or "") or None,
    }
    if include_permissions:
        payload["permissions"] = _account_permissions(account)
        # 실패 횟수는 admin-context 에만 노출(자기 세션 /api/auth/me 비노출 — outside-voice NIT 흡수).
        payload["failed_login_attempts"] = int(account.get("failed_login_attempts") or 0)
        # TASK-20260623T014626-quota-ui-relocate: 계정 특수 LLM 토큰 한도(override, null=역할 기본 상속). admin 계정 상세 편집용.
        # TASK-20260623T030418-quota-rbac-permission: 노출은 actor 의 quota.read 가 있을 때만
        #   (_strip_quota_fields_if_unpermitted 가 엔드포인트에서 strip). 직렬화는 값을 싣되, 게이트는 호출측.
        payload["quota_daily"] = int(account["quota_daily"]) if account.get("quota_daily") is not None else None
        payload["quota_monthly"] = int(account["quota_monthly"]) if account.get("quota_monthly") is not None else None
    return payload

def _strip_quota_fields_if_unpermitted(payload, actor):
    """TASK-20260623T030418-quota-rbac-permission: actor 가 quota.read 미보유 시
    직렬화에서 LLM 한도 필드(quota_daily/quota_monthly)를 제거한다(노출 차단, defense-in-depth).
    payload 는 dict(단건) 또는 list[dict]. quota.read 보유 시 무변경 후 그대로 반환."""
    if _account_has_permission(actor, "quota.read"):
        return payload
    items = payload if isinstance(payload, list) else [payload]
    for item in items:
        if isinstance(item, dict):
            item.pop("quota_daily", None)
            item.pop("quota_monthly", None)
    return payload


# ── ITEM-10 b6-B: 제품 접근 클러스터 (판정표 Batch B — retarget 0 검증) ──
# _product_permission_code 의 app-패치 1×(test_auto_role_prompt:180) 인터셉트 지점은
# app-잔류 함수(_assemble_role_prompt_llm_request) 내부 — 관통 무영향 전수 확인.

def _account_has_product_access(
    account: dict[str, Any] | None,
    product_id_or_key,
    *,
    conn=None,
) -> bool:
    """TASK-0052 Phase 1B: 계정이 특정 제품에 접근 가능한지 검사.

    `product_id_or_key`:
        - int / int 문자열  → WebProducts.Id. conn 가 주어지면 WebProducts 에서 ProductKey 조회 후 판단.
                              conn 가 None 인데 int 만 주어진 경우 False (안전한 fallback).
        - str (대문자 ProductKey) → 그대로 lowercase 변환 후 권한 코드 lookup.
    `account` 가 None 이거나 permissions cache 에 동적 코드가 없으면 False.

    이 헬퍼는 G1-G8 가드 (briefing §3.4) 의 단일 진입점이며, 모든 mutation 경로에서 호출된다.
    """
    if not account:
        return False
    permissions = _account_permissions(account)
    raw = product_id_or_key
    product_key: str = ""
    # int 입력 처리
    try:
        product_id_int = int(raw)  # type: ignore[arg-type]
    except Exception:
        product_id_int = 0
    if product_id_int > 0 and not isinstance(raw, str):
        # int 가 들어왔으면 conn 으로 ProductKey 조회.
        if conn is None:
            return False
        try:
            cur = conn.cursor()
            cur.execute("SELECT ProductKey FROM WebProducts WHERE Id = %s LIMIT 1", (product_id_int,))
            row = cur.fetchone()
            cur.close()
        except Exception:
            return False
        if not row or not row[0]:
            return False
        product_key = str(row[0])
    else:
        # 문자열 입력 (ProductKey 직접) 또는 str 형태의 숫자
        if isinstance(raw, str) and raw.strip():
            stripped = raw.strip()
            if stripped.isdigit():
                # str(숫자) 케이스 — int 로 처리
                if conn is None:
                    return False
                try:
                    cur = conn.cursor()
                    cur.execute(
                        "SELECT ProductKey FROM WebProducts WHERE Id = %s LIMIT 1",
                        (int(stripped),),
                    )
                    row = cur.fetchone()
                    cur.close()
                except Exception:
                    return False
                if not row or not row[0]:
                    return False
                product_key = str(row[0])
            else:
                product_key = stripped
        else:
            return False
    code = _product_permission_code(product_key)
    return bool(permissions.get(code))

def _filter_products_for_account_access(
    account: dict[str, Any] | None,
    products: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """TASK-0295: 작업 화면 제품 목록을 계정의 `product.access.<key>` 권한으로 필터.

    역할(role)에 특정 제품 접근 권한이 없으면 작업 화면 대화창 picker 에서 해당 제품을
    제외한다. 기존에는 `/api/ask`·`/api/new_conversation` 등 mutation 경로 8곳이 이미
    `_account_has_product_access` 로 403 게이트하지만 목록 표시만 게이트가 빠져 있어,
    요청이 차단되는 제품이 picker 에는 그대로 노출됐다 (표시-enforcement 불일치).

    - product_key 기반 lookup 이라 conn 불필요 (account.permissions 캐시만 사용).
    - 작업 화면 경로(`/api/session`, `/api/auth/me`) 전용. 관리 콘솔 제품 목록
      (`_list_products(include_inactive=True)`)에는 적용하지 않는다 — 관리 권한은
      product.read/manage 축으로 별도 게이트된다 (TASK-0288 2축 분리).
    """
    if not account:
        return []
    out: list[dict[str, Any]] = []
    for p in products:
        product_key = p.get("product_key")
        if product_key and _account_has_product_access(account, product_key):
            out.append(p)
    return out

def _coerce_default_product_id(default_pid, products: list[dict[str, Any]]) -> int:
    """TASK-0295: default_product_id 가 접근 가능 목록 밖이면 첫 접근 가능 제품으로 보정.

    작업 화면 제품 목록이 권한으로 필터된 뒤, 시스템 기본 제품(IsDefault)이 해당 계정의
    접근 가능 목록에 없을 수 있다 (default 제품 접근 권한도 회수된 경우). 그 경우 프론트가
    존재하지 않는 제품을 자동 선택하지 않도록 첫 접근 가능 제품으로 보정하고, 접근 가능한
    제품이 하나도 없으면 0(없음)을 반환한다.
    """
    try:
        pid = int(default_pid or 0)
    except Exception:
        pid = 0
    accessible_ids = {int(p.get("id") or 0) for p in products}
    if pid and pid in accessible_ids:
        return pid
    if products:
        return int(products[0].get("id") or 0)
    return 0

def _account_has_model_access(
    account: dict[str, Any] | None,
    model: str | None,
    *,
    conn=None,
) -> bool:
    """model-access-rbac(2026-07-28): 계정이 특정 LLM 모델을 **선택**할 수 있는지 검사.

    `product.access.<key>` 게이트(`_account_has_product_access`)의 모델 축 대응물이며,
    `/api/ask` 단일 choke-point + `/api/session` 카탈로그 필터의 공통 판정 함수다.

    판정 순서:
      1. `account` 없음 → False (미인증은 애초에 상위 `_require_account` 가 차단).
      2. 카탈로그에 없는 model → **판정 대상 아님** → True. 허용 여부는 기존
         `_is_allowed_api_model`(400) 이 판정하는 별 축이라, 여기서 False 를 주면 같은 실패에
         403/400 두 갈래 메시지가 생겨 진단이 흐려진다. 게이트는 "선택 가능한 모델" 에만 적용.
      3. 계정이 `model.access.<value>` 보유 → True.
      4. 미보유 + **그 권한 row 가 아직 DB 에 등록되지 않음** → True + WARNING 로그.
         부트스트랩이 아직 seed 하지 않은 창(신규 배포 첫 요청·DB degraded)에서 strict-deny 하면
         **모든 대화가 403** 이 된다 — 게이트 미설치 상태를 "전원 차단" 으로 해석하는 것이 훨씬 큰
         사고이고, 사용자 결정("전부 기본 부여")과도 어긋난다. 이 경로는 조용히 넘기지 않고
         WARNING 을 남겨 관측 가능하게 한다.
      5. 미보유 + row 등록됨 → **False** (관리자가 명시 해제한 상태 — fail-closed).

    `conn` 은 4번 판정(row 등록 여부)에만 쓰인다. `conn=None` 이면 row 확인이 불가하므로
    **보수적으로 3번까지만 보고 미보유 시 False** — 인증된 경로는 항상 conn 을 갖고 있고,
    conn 없는 호출측이 게이트를 우회하지 못하게 한다.
    """
    if not account:
        return False
    name = str(model or "").strip()
    if not name:
        return False
    # (2) 카탈로그 밖 model — 본 게이트의 판정 대상 아님 (_is_allowed_api_model 이 400 으로 처리).
    if not model_catalog.is_allowed_api_model(name):
        return True
    code = model_catalog.model_permission_code(name)
    if not code:
        return True
    permissions = _account_permissions(account)
    if bool(permissions.get(code)):
        return True  # (3) 명시 보유
    # (4) 게이트 미설치(부트스트랩 지연/degraded) 판별 — 등록 안 된 권한으로 전원 차단 방지.
    if conn is not None:
        try:
            cur = conn.cursor()
            cur.execute("SELECT 1 FROM WebPermissions WHERE Code = %s LIMIT 1", (code,))
            registered = cur.fetchone() is not None
            cur.close()
        except Exception:
            # DB 조회 실패 — 등록 여부를 알 수 없다. 게이트 미설치일 수도 있어 통과시키되 시끄럽게 남긴다.
            logging.getLogger(__name__).warning(
                "model-access: WebPermissions 조회 실패로 모델 게이트 판정 불가 — 통과 처리 (model=%s code=%s)",
                name, code,
            )
            return True
        if not registered:
            logging.getLogger(__name__).warning(
                "model-access: 권한 row 미등록 상태에서 모델 요청 — 게이트 미설치로 보고 통과 "
                "(model=%s code=%s). 부트스트랩이 _ensure_model_access_permissions 를 수행했는지 확인.",
                name, code,
            )
            return True
    # (5) row 는 등록됐고 계정은 미보유 → 관리자가 해제한 것. fail-closed.
    return False


def _filter_models_for_account_access(
    account: dict[str, Any] | None,
    models: list[dict[str, Any]],
    *,
    conn=None,
) -> list[dict[str, Any]]:
    """model-access-rbac: `/api/session` 이 내려주는 모델 카탈로그를 계정 권한으로 필터.

    `_filter_products_for_account_access`(제품 목록 필터)와 동형 — 표시와 집행을 함께 닫는다
    (선택기에 안 보이는 모델을 서버가 거부하고, 서버가 거부할 모델을 선택기에 안 보인다).

    **전부 필터되면 필터 전 목록을 그대로 반환**한다: 관리자가 실수로 한 역할의 모든 모델을
    해제하면 그 사용자는 모델 선택기가 빈 채로 대화를 아예 못 하게 되는데, 그 상태를 조용한
    빈 목록으로 만들면 원인 파악이 어렵다(프론트는 "로딩 중" 으로 보인다). 집행은 `/api/ask`
    게이트가 여전히 담당하므로 **표시만 관대**하게 두고 WARNING 을 남긴다(display-permissive ·
    backend-enforced — 프론트 `can()` 규약과 동일 원칙).
    """
    if not account or not models:
        return models
    allowed = [
        m for m in models
        if _account_has_model_access(account, str((m or {}).get("value") or ""), conn=conn)
    ]
    if not allowed:
        logging.getLogger(__name__).warning(
            "model-access: 계정의 선택 가능 모델이 0개 — 표시는 필터 전 목록을 유지한다 "
            "(집행은 /api/ask 게이트가 담당). account_id=%s",
            (account or {}).get("id"),
        )
        return models
    return allowed


def _product_permission_code(product_key: str) -> str:
    """TASK-0052 Phase 1B: product_key 를 lowercase 권한 코드 namespace 로 변환.

    `product_key` 는 `^[A-Z][A-Z0-9_]{0,31}$` 정규식. permission code 는 lowercase + dot.
    e.g. "KR" → "product.access.kr" / "MY_NEW" → "product.access.my_new".
    """
    return f"product.access.{str(product_key or '').strip().lower()}"


# ── ITEM-10 b6-C: 인증 read·감사 actor 조립 (판정표 Batch C) ──
# **이동 영구 금지 목록**(판정표 — 어기면 app-패치가 무증상 우회): _require_account ·
# _optional_account · get_current_account · get_optional_account · _audit_admin_mutation ·
# _audit_user_action · _metadata_audit · _connect_memory · _account_can_access_conversation.
# 이들은 app.py 의 종국 역할(runtime hub·DI seam·패치-단일점)의 일부로 영구 잔류한다.

def _get_account_by_api_token(conn, request: Request) -> dict[str, Any] | None:
    """feature-0023 (REQ-20260722-conversation-api-access): Bearer API 토큰으로 서비스
    계정을 해석한다(세션 쿠키 fallback — 프로그래매틱 접근 전용).

    - 토큰 원문은 SHA-256 해시로만 대조(WebApiTokens.TokenHash) — 원문 미저장.
    - not revoked + (무기한 OR 미만료) 만 유효. 만료/폐기/미존재는 None(미인증).
    - 유효 시 계정 dict 에 `_auth_via="api_token"` + `_token_scopes` 부착 → 다운스트림
      `_account_permissions` 가 scope 로 유효 권한을 교집합(관리 엔드포인트 원천 차단).
    - fail-closed: 조회/파싱 예외는 None(우회 금지). 브루트포스 잠금 대상 아님(고엔트로피).
    """
    token = _extract_bearer_token(request)
    if not token:
        return None
    token_hash = _hash_session_token(token)
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute(
            """
SELECT Id, AccountId, Scopes
FROM WebApiTokens
WHERE TokenHash = %s
  AND RevokedAt IS NULL
  AND (ExpiresAt IS NULL OR ExpiresAt > CURRENT_TIMESTAMP)
LIMIT 1
            """,
            (token_hash,),
        )
        trow = cur.fetchone()
        cur.close()
    except Exception:
        return None
    if not trow:
        return None
    account_id = trow.get("AccountId")
    if account_id is None:
        return None
    rows = _fetch_account_rows(
        conn,
        "a.Id = %s AND a.IsActive = 1 AND a.DeletedAt IS NULL",
        (int(account_id),),
        include_password=False,
        limit_sql="LIMIT 1",
    )
    rows = _decorate_account_rows(conn, rows)
    row = rows[0] if rows else None
    if not row:
        return None
    row["_auth_via"] = "api_token"
    row["_token_id"] = trow.get("Id")
    row["_token_scopes"] = _parse_token_scopes(trow.get("Scopes"))
    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE WebApiTokens SET LastUsedAt = CURRENT_TIMESTAMP WHERE Id = %s",
            (trow.get("Id"),),
        )
        cur.close()
    except Exception:
        pass
    return row


def _get_authenticated_account(conn, request: Request) -> dict[str, Any] | None:
    token = _sanitize_session_id(request.cookies.get(SESSION_COOKIE, ""))
    if token:
        rows = _fetch_account_rows(
            conn,
            """
a.Id = (
    SELECT s.AccountId
    FROM WebAuthSessions s
    WHERE s.SessionTokenHash = %s
      AND s.IsRevoked = 0
      AND s.ExpiresAt > CURRENT_TIMESTAMP
    LIMIT 1
)
AND a.IsActive = 1
AND a.DeletedAt IS NULL
            """,
            (_hash_session_token(token),),
            include_password=False,
            limit_sql="LIMIT 1",
        )
        rows = _decorate_account_rows(conn, rows)
        row = rows[0] if rows else None
        if row:
            cur = conn.cursor()
            cur.execute(
                """
UPDATE WebAuthSessions
SET LastSeenAt = CURRENT_TIMESTAMP,
    RemoteAddr = %s,
    UserAgent = %s
WHERE SessionTokenHash = %s
                """,
                (
                    _get_client_ip(request),
                    str(request.headers.get("user-agent", "") or "")[:255],
                    _hash_session_token(token),
                ),
            )
            cur.close()
            return row
    # feature-0023: 유효 세션 쿠키가 없으면 Bearer API 토큰 fallback(프로그래매틱 접근).
    # 쿠키가 유효하면 위에서 이미 반환됐으므로 사람 세션은 무회귀(토큰 경로 미발동).
    return _get_account_by_api_token(conn, request)

def _build_actor_from_request(
    request: Request | None,
    account: dict | None,
    *,
    actor_type: str = "account",
) -> dict:
    """Phase A1 helper: actor dict 조립 (caller 가 record_audit_event 에 전달).

    actor_type='anonymous' 시 account NULL 허용. request None 시 remote_addr/user_agent NULL.
    TASK-0072 `_log_search_activity` 의 호출 패턴 답습 — caller 가 직접 조립.
    """
    actor: dict[str, Any] = {"actor_type": actor_type}
    if account:
        actor["account_id"] = account.get("Id") or account.get("id")
        actor["role_id"] = account.get("RoleId") or account.get("role_id")
        actor["username"] = account.get("Username") or account.get("username")
    if request is not None:
        try:
            actor["remote_addr"] = _get_client_ip(request)
        except Exception:
            actor["remote_addr"] = None
        try:
            actor["user_agent"] = request.headers.get("user-agent", "")
        except Exception:
            actor["user_agent"] = None
        try:
            actor["session_id"] = _sanitize_session_id(
                request.cookies.get(SESSION_COOKIE, "")
            )
        except Exception:
            actor["session_id"] = None
    return actor
