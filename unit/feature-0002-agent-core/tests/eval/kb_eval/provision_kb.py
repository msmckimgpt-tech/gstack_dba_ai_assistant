"""ITEM-05 KB-주석 retrieval eval set — 결정적 합성 KB 문서를 agent_kb(PG)에 멱등 적재.

목적: 하이브리드 검색(fusion) vs 2-tier 의 retrieval A/B 측정을 위한 고정 ground-truth KB.
ITEM-01 NL→SQL eval 자산(tests/eval/) 에 인접한 retrieval-전용 평가 자산이다.

격리:
- 모든 문서를 **eval scope (`evalkb`)** + eval conversation_id (`__evalkb__`) 로만 적재.
  운영 KB(다른 scope/conversation) 와 섞이지 않는다.
- 멱등: 동일 (conversation_id, scope_key, fact_key) upsert — 재실행 동일 상태.
- `--purge`: evalkb scope 의 rag_documents 행을 삭제(eval 종료 후 정리). texts 는 공유
  저장소라 보존(다른 scope 가 참조할 수 있어 GC 가 별도 관리; 합성 텍스트는 고아로 남아도
  무해, 운영 KB read 는 conversation/scope 로 격리됨).

임베딩: `kb_retrieval._embed_query_vector`(AGENT_KB_EMBEDDING_MODEL=titan-embed→로컬 bge-m3
1024-dim)로 각 문서 텍스트를 임베딩해 texts.embedding 에 적재 → 벡터 검색 대상이 된다.
임베딩 실패 시 그 문서는 trigram-only 가 되므로 fail-loud(적재 중단)로 측정 무결성 보장.

진입점: `python -m kb_eval.provision_kb` (PYTHONPATH 에 src + tests/eval).
"""
from __future__ import annotations

import argparse
import sys

EVAL_SCOPE = "evalkb"
EVAL_CONVERSATION_ID = "__evalkb__"
SOURCE_TYPE = "eval_synthetic"

# 12 docs — 핵심 토픽 8 + 혼동 유발(distractor) 4. fact_key 가 golden 의 ground-truth 키.
# 핵심 docs 는 의미상 분리하고, distractor 는 핵심 doc 과 의미가 겹치되 고유 키워드로만
# 변별되도록 설계해 fusion(벡터+키워드) 의 재랭킹 효과가 측정에 드러나게 한다.
EVAL_DOCS: list[dict] = [
    {
        "fact_key": "def_active_customer",
        "text": "활성 고객 정의: 최근 90일 이내에 1건 이상 주문을 완료한 고객을 활성 고객으로 본다. "
                "탈퇴(deleted_at 존재) 또는 휴면 표기된 계정은 제외한다.",
        "weight": 5,
    },
    {
        "fact_key": "order_status_codes",
        "text": "주문 상태 코드: 0=장바구니, 1=결제대기, 2=결제완료, 3=배송중, 4=배송완료, "
                "5=취소, 6=환불. 매출 집계는 상태 2 이상(결제완료 이후)만 포함한다.",
        "weight": 5,
    },
    {
        "fact_key": "revenue_definition",
        "text": "매출 정의: 결제완료 금액 합계에서 환불 금액을 차감한 순매출(net revenue)을 사용한다. "
                "쿠폰 할인은 차감 후 금액 기준이며 부가세는 제외한다.",
        "weight": 5,
    },
    {
        "fact_key": "churn_window",
        "text": "이탈(churn) 기준: 마지막 주문일로부터 180일이 경과하면 이탈 고객으로 분류한다. "
                "재구매가 발생하면 이탈 상태가 해제된다.",
        "weight": 4,
    },
    {
        "fact_key": "membership_tiers",
        "text": "멤버십 등급: 누적 구매액에 따라 BRONZE/SILVER/GOLD/VIP 4단계로 나눈다. "
                "GOLD 이상은 무료 배송과 전용 쿠폰 혜택을 받는다.",
        "weight": 4,
    },
    {
        "fact_key": "refund_policy",
        "text": "환불 정책: 배송완료 후 7일 이내 환불 요청만 자동 승인되며, 그 이후는 관리자 검토가 필요하다. "
                "환불 건은 매출 집계에서 음수로 반영된다.",
        "weight": 3,
    },
    {
        "fact_key": "product_category_map",
        "text": "상품 카테고리 매핑: 카테고리 코드 100번대는 의류, 200번대는 전자기기, 300번대는 식품이다. "
                "카테고리별 매출 리포트는 이 코드 범위를 기준으로 묶는다.",
        "weight": 3,
    },
    {
        "fact_key": "shipping_regions",
        "text": "배송 권역: 도서산간 지역(제주, 울릉도 등)은 추가 배송비가 부과되며 평균 배송 소요일이 2일 더 길다. "
                "권역 코드는 zone_code 컬럼에 저장된다.",
        "weight": 3,
    },
    # ── 혼동 유발(distractor) docs — 벡터 의미공간상 인접하나 정답이 아닌 토픽. 정답 doc 과
    #    의미가 겹쳐 벡터-only 가 오인할 수 있고, 정답 doc 의 고유 키워드(코드/숫자/고유명)로
    #    trigram 이 변별을 보탠다 → fusion 의 재랭킹 효과가 드러나는 케이스.
    {
        "fact_key": "payment_status_codes",
        "text": "결제 상태 코드: P0=미결제, P1=승인대기, P2=승인완료, P3=부분취소, P4=전체취소. "
                "주문 상태(order status)와는 별개 체계이며 PG사 응답 코드를 따른다.",
        "weight": 3,
    },
    {
        "fact_key": "delivery_status_codes",
        "text": "배송 추적 상태: D0=집화전, D1=집화완료, D2=간선상차, D3=배송출발, D4=배송완료. "
                "택배사 트래킹 API 의 상태값이며 주문 상태 코드와 혼동하지 말 것.",
        "weight": 3,
    },
    {
        "fact_key": "gross_revenue_definition",
        "text": "총매출(gross revenue) 정의: 환불·할인 차감 전 결제완료 총액. 순매출(net)과 달리 "
                "환불을 빼지 않으며 대시보드 GMV 지표에 사용된다.",
        "weight": 3,
    },
    {
        "fact_key": "dormant_account_definition",
        "text": "휴면 계정 정의: 최근 365일간 로그인·주문이 없으면 휴면으로 전환되며 마케팅 수신이 중단된다. "
                "이탈(churn)과 달리 계정 보존 상태이고 재로그인 시 즉시 해제된다.",
        "weight": 3,
    },
]


def _embed(text: str) -> list[float]:
    from modules import kb_retrieval  # type: ignore
    vec = kb_retrieval._embed_query_vector(text)
    if not vec:
        raise RuntimeError(f"임베딩 실패(빈 벡터) — gateway/모델 확인 필요. text={text[:40]!r}")
    return list(vec)


def _content_hash(fact_key: str, text: str) -> str:
    from modules.utils import _rag_content_hash  # type: ignore
    return _rag_content_hash(fact_key, text)


def _text_hash(text: str) -> str:
    from modules.utils import _text_hash as th  # type: ignore
    return th(text)


def provision() -> int:
    from shared.db import _pg_connect  # type: ignore
    from shared import config as cfg  # type: ignore

    conn = _pg_connect()
    n = 0
    try:
        with conn.cursor() as cur:
            for doc in EVAL_DOCS:
                fact_key = doc["fact_key"]
                text = " ".join(str(doc["text"]).split())
                th = _text_hash(text)
                emb = _embed(text)
                # 1) texts upsert + embedding (멱등). 임베딩 모델/차원 정합.
                cur.execute(
                    "INSERT INTO texts (text_hash, text_content, embedding, embedding_model, embedded_at) "
                    "VALUES (%s, %s, %s::vector, %s, now()) "
                    "ON CONFLICT (text_hash) DO UPDATE SET "
                    "  embedding = EXCLUDED.embedding, embedding_model = EXCLUDED.embedding_model, "
                    "  embedded_at = now()",
                    (th, text, emb, cfg.AGENT_KB_EMBEDDING_MODEL),
                )
                # 2) rag_documents upsert (evalkb scope 격리). unique 제약은
                #    (conversation_id, scope_key, fact_key, content_hash) — content_hash 는
                #    (fact_key, text) 결정적 함수라 동일 입력 재실행 시 동일 행 → 멱등.
                cur.execute(
                    "INSERT INTO rag_documents "
                    "  (conversation_id, scope_key, doc_type, fact_key, text_hash, content_hash, "
                    "   weight, source_type) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s) "
                    "ON CONFLICT (conversation_id, scope_key, fact_key, content_hash) DO UPDATE SET "
                    "  text_hash = EXCLUDED.text_hash, "
                    "  weight = GREATEST(rag_documents.weight, EXCLUDED.weight), "
                    "  updated_at = now()",
                    (
                        EVAL_CONVERSATION_ID, EVAL_SCOPE, "fact", fact_key, th,
                        _content_hash(fact_key, text), int(doc["weight"]), SOURCE_TYPE,
                    ),
                )
                n += 1
        conn.commit()
    finally:
        conn.close()
    print(f"[provision_kb] {n} docs 적재 완료 (scope={EVAL_SCOPE}, conversation={EVAL_CONVERSATION_ID})")
    return n


def purge() -> int:
    from shared.db import _pg_connect  # type: ignore

    conn = _pg_connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM rag_documents WHERE conversation_id = %s AND scope_key = %s",
                (EVAL_CONVERSATION_ID, EVAL_SCOPE),
            )
            deleted = cur.rowcount or 0
        conn.commit()
    finally:
        conn.close()
    print(f"[provision_kb] purge: {deleted} eval docs 삭제 (scope={EVAL_SCOPE})")
    return deleted


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="ITEM-05 KB retrieval eval set provisioner (evalkb scope)")
    p.add_argument("--purge", action="store_true", help="evalkb scope rag_documents 삭제(정리)")
    args = p.parse_args(argv)
    if args.purge:
        purge()
    else:
        provision()
    return 0


# ON CONFLICT 의 (conversation_id, scope_key, fact_key) unique 제약은 alembic 스키마 정본.
# 만약 제약명이 다르면 ON CONFLICT 절을 컬럼 목록으로 지정(위와 같이)해 제약 추론에 의존한다.

if __name__ == "__main__":
    sys.exit(main())
