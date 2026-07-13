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
        "code": "console.usage.read",
        "label": "LLM 사용량 조회",
        "description": "LLM 토큰 사용량/비용 집계를 조회할 수 있다 (운영자 전용).",
        "group": "console",
    },
    {
        # TASK-AIOPS: AI 운영 관제 패널(관리 콘솔 > 감사 > AI 운영 현황) 조회 권한. 운영 민감
        # 정보(워커 상태·provider 헬스·AI 활동 계측)라 admin 한정 — admin seed(=set(PERMISSION_CODES))
        # 자동 부여 + 아래 _ensure_seed_roles catchup 으로 기존 admin row backfill.
        # operator/sales/dba/pending 미부여 (least-privilege).
        "code": "console.aiops.read",
        "label": "AI 운영 현황 조회",
        "description": "AI 운영 관제 패널(워커 상태·provider 헬스·AI 활동 계측)을 조회할 수 있다 (운영자 전용).",
        "group": "console",
    },
    {
        # TASK-0228: insight-worker 가 생성한 schema/table 분석(fact/rag/fingerprint)을
        # 접근 가능 데이터베이스(DB) 단위로 초기화(삭제)한다. 잘못 분석된 내용을 되돌릴 수단.
        # **파괴적** — audit.purge 와 동급으로 admin 한정 (admin seed = set(PERMISSION_CODES)
        # 자동 부여, operator/sales/pending 미부여). dry-run 미리보기 + typed-confirm + self-audit.
        "code": "insight.reset",
        "label": "insight 분석 초기화",
        "description": "접근 가능 데이터베이스 단위로 insight 분석 결과(fact/rag/fingerprint)를 삭제할 수 있다. 다음 worker cycle 에 자동 재분석된다. 시작/완료는 self-audit 으로 기록된다 (운영자 전용).",
        "group": "console",
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
        "description": "메타데이터 탭의 모든 편집 기능(용어사전·ENUM·테이블 설명·컬럼 설명 관리)을 한 번에 부여하는 묶음 권한이다. 세부 기능만 선택적으로 부여하려면 아래 개별 metadata.*.manage 권한을 사용한다(이 묶음을 보유하면 4종 편집 권한을 모두 보유한 것과 동일하게 동작한다). 그래프 뷰 조회(metadata.graph.read)는 별도 최상위 탭으로 분리되어 이 묶음에 포함되지 않는다 — 그래프 뷰 접근은 metadata.graph.read 로 개별 부여한다(graph-perm-split, 사용자 결정 2026-07-13).",
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
    {
        "code": "metadata.glossary.manage",
        "label": "용어사전 관리",
        "description": "용어사전(도메인 용어↔정의) 항목과 유사어 참조를 등록/수정/삭제할 수 있다. 등록 내용은 질문/스키마 매칭 시 프롬프트에 주입되어 답변 정확도에 직접 영향한다(도메인 전문가/큐레이터 전용).",
        "group": "kb",
    },
    {
        "code": "metadata.enum.manage",
        "label": "ENUM 코드사전 관리",
        "description": "ENUM 코드사전(컬럼 코드↔라벨) 항목을 등록/수정/삭제할 수 있다. 등록 내용은 질문/스키마 매칭 시 프롬프트에 주입되어 답변 정확도에 직접 영향한다.",
        "group": "kb",
    },
    {
        "code": "metadata.table.manage",
        "label": "테이블 설명 관리",
        "description": "테이블 설명을 등록/수정/삭제하고 스키마 골격 가져오기(부트스트랩)를 사용할 수 있다. 등록 내용은 질문/스키마 매칭 시 프롬프트에 주입되어 답변 정확도에 직접 영향한다.",
        "group": "kb",
    },
    {
        "code": "metadata.column.manage",
        "label": "컬럼 설명 관리",
        "description": "컬럼 설명을 등록/수정/삭제할 수 있다. 등록 내용은 질문/스키마 매칭 시 프롬프트에 주입되어 답변 정확도에 직접 영향한다.",
        "group": "kb",
    },
    {
        "code": "metadata.graph.read",
        "label": "그래프 뷰 조회",
        "description": "지식베이스 그래프 뷰 탭(테이블/컬럼/관계/용어 탐색·검색)을 조회하고, 그래프 뷰의 내장 AI 능동 분석을 실행할 수 있다. 그래프 뷰는 별도 최상위 탭으로, 이 권한은 '메타데이터 관리' 묶음(kb.ingest.manual) 및 개별 편집 권한과 독립적으로 부여된다(graph-perm-split 2026-07-13). 읽기 중심 탐색 권한.",
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
        "code": "conversation.archive.read.any",
        "label": "보관 대화 조회",
        "description": "모든 계정의 보관된(삭제 처리된) 대화를 오용 방지 목적으로 조회할 수 있다.",
        "group": "conversation_any",
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
        "code": "product.read",
        "label": "제품 조회",
        "description": "관리 콘솔에서 제품(Product) 구성(목록·접근 DB·데이터소스 바인딩 현황)을 조회할 수 있다.",
        "group": "product",
    },
    {
        "code": "product.manage",
        "label": "제품 관리",
        "description": "제품(Product) 생성/수정/삭제 및 접근 DB 스키마, 제품 시스템 프롬프트를 관리할 수 있다.",
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
        "code": "datasource.manage",
        "label": "데이터소스 관리",
        "description": "데이터소스를 생성/수정/삭제하고 연결 테스트를 수행할 수 있다(자격증명 암호화 저장).",
        "group": "datasource",
    },
    # TASK-0073 Phase A3 (REQ-20260519-0001, Critical §12.3): audit 권한 4건.
    # `.own` 은 모든 role (dba 포함) auto-grant — 본인이 actor 인 audit row 조회(TASK-0293 Actor-only).
    # `.any` 는 admin/dba — 전체 계정 audit row 조회 (`.any` superset semantics 정합).
    # `.export` 는 admin/dba — CSV / JSON dump 가능 (PII bulk export).
    # `.purge` 는 admin only — retention 초과 chunked PK 삭제 (자가 audit 동반).
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

# graph-perm-split(Critical §12.3, 사용자 결정 2026-07-13): 그래프 뷰 권한을 메타데이터 관리 묶음 함의에서
#   분리하면서, **분리 시점의 기존 묶음 보유 principal 의 그래프 접근을 1회 backfill 로 보존**하기 위한 마커 키.
#   WebSchemaMigrations 에 이 키가 있으면 backfill 완료 → 재실행 안 함(멱등 guard). 매 startup 무조건 재실행 시
#   분리 이후 새로 묶음을 받은 역할까지 graph.read 를 자동 획득해 분리가 무력화되므로 반드시 1회만 수행한다.
_GRAPH_PERM_SPLIT_MIGRATION_KEY = "graph-perm-split-v1"


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
    # graph-panel-perms(task4): 레거시 묶음 `kb.ingest.manual` 함의 — effective 로 묶음 보유 시 세부 metadata.*
    #   권한을 자동 부여한다(비파괴 하위호환). 단 해당 세부 권한이 명시 DENY 오버라이드된 경우는 존중(least-privilege).
    if permissions.get("kb.ingest.manual"):
        for code in _METADATA_MANUAL_IMPLIES:
            if code not in permissions:
                continue
            if _normalize_override_value((overrides or {}).get(code)) == OVERRIDE_DENY:
                continue
            permissions[code] = True
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
                item["label"],
                item["description"],
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
        return {str(code): bool(value) for code, value in cached.items()}
    return _empty_permission_map()

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

def _get_authenticated_account(conn, request: Request) -> dict[str, Any] | None:
    token = _sanitize_session_id(request.cookies.get(SESSION_COOKIE, ""))
    if not token:
        return None
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
