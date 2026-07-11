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

import hashlib
import ipaddress
import os
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
        "description": "메타데이터 탭의 모든 세부 기능(용어사전·ENUM·테이블 설명·컬럼 설명 관리 + 그래프 뷰 조회)을 한 번에 부여하는 묶음 권한이다. 세부 기능만 선택적으로 부여하려면 아래 개별 metadata.* 권한을 사용한다(이 묶음을 보유하면 개별 권한을 모두 보유한 것과 동일하게 동작한다).",
        "group": "kb",
    },
    # graph-panel-perms(task4, Critical §12.3): 메타데이터 탭 세부 권한 — 기존 단일 `kb.ingest.manual`
    # 묶음을 기능별로 분리(B안, 사용자 결정 2026-07-01)해 용어사전/ENUM/테이블/컬럼 관리와 그래프 뷰 조회를
    # 개별 위임 가능하게 한다. 하위호환: `kb.ingest.manual` 보유자는 _apply_permission_overrides 의
    # 함의(_METADATA_MANUAL_IMPLIES)로 아래 5개를 effective 로 자동 보유 → 기존 배포 무손실(비파괴·가역).
    # 모두 console.access 하위(관리 콘솔 진입 필요). admin seed(=set(PERMISSION_CODES)) 자동 보유 + 기존
    # admin row 는 _ensure_seed_roles catchup 으로 retroactive 부여. operator/sales/pending 미부여(least-privilege).
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
        "label": "메타데이터 그래프 뷰 조회",
        "description": "메타데이터 지식그래프 뷰(테이블/컬럼/관계/용어 탐색·검색)를 조회하고, 그래프 뷰의 내장 AI 능동 분석을 실행할 수 있다. 읽기 중심 탐색 권한으로, 개별 메타데이터 항목 편집 권한과 분리된다.",
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
#   _apply_permission_overrides 가 effective map 에서 묶음 보유자에게 아래 5개를 자동 부여(개별 DENY 오버라이드는 존중).
#   기존 배포 무손실(비파괴·가역) — DB 마이그레이션 없이 하위호환. 묶음 보유 principal(역할/계정 오버라이드) 전부 커버.
_METADATA_MANUAL_IMPLIES = (
    "metadata.glossary.manage",
    "metadata.enum.manage",
    "metadata.table.manage",
    "metadata.column.manage",
    "metadata.graph.read",
)


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
