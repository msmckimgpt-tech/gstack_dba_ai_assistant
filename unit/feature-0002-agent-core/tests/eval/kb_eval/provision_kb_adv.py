"""ITEM-05 **적대적(adversarial)** KB retrieval eval set — fusion 의 가치가 드러나는 corpus.

배경: 기존 evalkb(provision_kb.py)는 깨끗한 합성 KB 라 bge-m3 가 정답을 항상 1위(MRR=1.0)에
두어 fusion 의 headroom 이 0 → NEUTRAL 이었다. fusion(벡터+trigram)의 실제 가치는 **임베더가
약한 케이스**다: 질문에 rare exact token(컬럼명·상태코드·약어·코드 식별자)이 있고 정답 doc 이
그 토큰을 정확히 포함하나, 의미상 더 가까워 보이는 distractor(그 토큰 없음)가 순수 벡터에서
더 높이/비슷하게 랭크되는 경우. 이때 trigram 이 exact-token 매칭을 잡아 fusion 이 정답을 끌어올린다.

설계 원칙(공정성):
- 정답 doc 은 질문의 rare exact token 을 **자연스럽게** 포함(질문 문장 그대로 복붙 금지).
- 같은 토픽의 distractor 1~2개는 그 토큰 없이 의미만 유사 → 벡터가 정답보다 높이/비슷하게 랭크.
- 한국어 도메인 + 코드/약어 혼합(실제 DBA 질의 유사). 토큰을 정답에만 심되 현실적 rare-token
  공유 수준으로(인위적 trigram 조작 금지).

격리: evalkb_adv scope + __evalkb_adv__ conversation. 운영 KB 무관, --purge 정리.
임베딩: bge-m3(AGENT_KB_EMBEDDING_MODEL=titan-embed→로컬 1024-dim). 실패 시 fail-loud.

진입점: `python -m kb_eval.provision_kb_adv [--purge]`
"""
from __future__ import annotations

import argparse
import sys

EVAL_SCOPE = "evalkb_adv"
EVAL_CONVERSATION_ID = "__evalkb_adv__"
SOURCE_TYPE = "eval_adv_synthetic"

# ── 적대적 corpus: 14 docs. 각 토픽은 (정답 doc + rare-token-없는 distractor 1~2개) 로 구성.
#    rare exact token 을 **정답 doc 에만** 심되, distractor 는 그 토큰 없이 의미만 겹치게 해
#    벡터가 distractor 를 정답 위/근처로 올리도록 한다(자연스러운 under-rank 유발).
EVAL_DOCS: list[dict] = [
    # ── 토픽 A: 활성 사용자 집계 컬럼 (rare token: is_active_flag) ───────────────
    {
        "fact_key": "is_active_flag_def",
        # 정답: 컬럼명 is_active_flag 를 정확히 포함. MAU/DAU 집계 컬럼.
        "text": "사용자 활성 여부는 users 테이블의 is_active_flag 컬럼으로 판정한다. "
                "MAU·DAU 같은 활성 사용자 집계는 이 플래그가 1인 행만 센다. 탈퇴·정지 계정은 0이다.",
        "weight": 3,
    },
    {
        "fact_key": "active_user_narrative",
        # distractor: '활성 사용자/접속/재방문' 의미는 짙으나 is_active_flag 컬럼명은 없음.
        #            벡터가 '활성 사용자' 질문에 이 서술형 doc 을 정답보다 가깝게 볼 수 있음.
        "text": "활성 사용자란 최근 한 달 안에 서비스에 접속해 의미 있는 행동을 한 회원을 말한다. "
                "재방문율과 잔존율을 높이려면 활성 사용자층을 두텁게 유지하는 운영이 중요하다.",
        "weight": 3,
    },

    # ── 토픽 B: 주문 취소 상태 코드 (rare token: ORD_CANCELLED) ──────────────────
    {
        "fact_key": "order_status_enum",
        # 정답: 상태 enum 문자열 ORD_CANCELLED 를 정확히 포함.
        "text": "주문 상태값 enum: ORD_PENDING(결제대기), ORD_PAID(결제완료), ORD_SHIPPED(배송중), "
                "ORD_DELIVERED(배송완료), ORD_CANCELLED(취소). 매출 집계는 ORD_PAID 이후 상태만 포함한다.",
        "weight": 3,
    },
    {
        "fact_key": "cancellation_policy_prose",
        # distractor: '주문 취소' 의미 짙음(환불·취소 사유)이나 ORD_CANCELLED enum 값은 없음.
        "text": "주문 취소는 배송 시작 전까지 고객이 직접 요청할 수 있으며, 결제 수단에 따라 환불에 "
                "최대 영업일 3일이 걸린다. 단순 변심 취소가 반복되면 패널티가 부과될 수 있다.",
        "weight": 3,
    },

    # ── 토픽 C: 결제 트랜잭션 상태 (rare token: txn_status) ─────────────────────
    {
        "fact_key": "txn_status_column",
        # 정답: 컬럼명 txn_status 정확 포함 + 값 의미.
        "text": "결제 트랜잭션의 진행 단계는 payments 테이블 txn_status 컬럼에 저장한다. "
                "값은 0=요청, 1=승인, 2=정산완료, 3=실패, 4=망취소이며 정산 리포트는 txn_status=2만 집계한다.",
        "weight": 3,
    },
    {
        "fact_key": "payment_flow_prose",
        # distractor: '결제 상태/승인/정산' 의미 짙으나 txn_status 컬럼명 없음. PG 응답 서술.
        "text": "결제는 카드사 승인을 받은 뒤 익일 정산 배치에서 가맹점 정산이 이뤄진다. "
                "승인과 정산은 별개 단계라 승인됐다고 바로 정산되는 것은 아니며 실패 시 망취소가 발생한다.",
        "weight": 3,
    },

    # ── 토픽 D: MAU 집계 정의 (rare token: MAU) — 약어 OOV ──────────────────────
    {
        "fact_key": "mau_definition",
        # 정답: 약어 MAU 정확 포함 + 집계식.
        "text": "MAU 는 월간 활성 사용자 수로, 해당 월에 1회 이상 로그인 또는 주문한 고유 user_id 의 수다. "
                "중복 제거(distinct) 후 카운트하며 마케팅 KPI 대시보드의 핵심 지표다.",
        "weight": 3,
    },
    {
        "fact_key": "monthly_engagement_prose",
        # distractor: '월간 사용자/참여도' 의미 짙으나 'MAU' 약어 토큰은 없음.
        "text": "월간 사용자 참여도는 한 달 동안 얼마나 많은 회원이 꾸준히 들어와 활동했는지를 보는 지표다. "
                "한 번 보고 떠나는 사용자보다 반복 방문하는 사용자가 많을수록 건강한 서비스로 본다.",
        "weight": 3,
    },

    # ── 토픽 E: 배송 추적 단계 코드 (rare token: D3) — 코드 식별자 ───────────────
    {
        "fact_key": "delivery_tracking_codes",
        # 정답: 코드 D3 정확 포함.
        "text": "배송 추적 단계 코드: D0=집화전, D1=집화완료, D2=간선이동, D3=배송출발, D4=배송완료. "
                "고객 알림 톡은 D3 시점에 자동 발송된다. 택배사 API status 값과 매핑된다.",
        "weight": 3,
    },
    {
        "fact_key": "shipping_journey_prose",
        # distractor: '배송 출발/단계' 의미 짙으나 'D3' 코드 없음.
        "text": "상품은 물류창고에서 출고된 뒤 간선 차량으로 지역 허브를 거쳐 고객에게 배송된다. "
                "배송이 출발하면 보통 하루 안에 도착하며 도서산간은 더 오래 걸린다.",
        "weight": 3,
    },

    # ── 토픽 F: 환불 처리 코드 (rare token: RFND_PARTIAL) ───────────────────────
    {
        "fact_key": "refund_status_enum",
        # 정답: enum RFND_PARTIAL 정확 포함.
        "text": "환불 상태 enum: RFND_NONE(없음), RFND_REQUESTED(요청), RFND_PARTIAL(부분환불), "
                "RFND_FULL(전액환불). 부분환불 RFND_PARTIAL 은 일부 품목만 반품된 주문에 적용된다.",
        "weight": 3,
    },
    {
        "fact_key": "refund_handling_prose",
        # distractor: '환불/반품 처리' 의미 짙으나 RFND_PARTIAL enum 없음.
        "text": "고객이 여러 품목 중 일부만 반품하면 반품된 품목 금액만 돌려주고 나머지는 유지한다. "
                "전체 반품과 달리 배송비 환불 여부는 사유에 따라 달라진다.",
        "weight": 3,
    },

    # ── 토픽 G: 멤버십 등급(혼합 한/영 + 고유명) — 비적대 대조(벡터가 잘 맞춰야) ──
    {
        "fact_key": "membership_grade_table",
        "text": "멤버십 등급: BRONZE/SILVER/GOLD/VIP 4단계로 누적 구매액 기준 산정. "
                "GOLD 이상은 무료배송과 전용쿠폰을 받고 VIP 는 전담 상담을 제공한다.",
        "weight": 3,
    },
    {
        "fact_key": "loyalty_program_prose",
        # 약한 distractor: '등급/혜택' 일반론. GOLD/VIP 고유명 없음.
        "text": "등급제 로열티 프로그램은 많이 구매한 고객에게 더 큰 혜택을 주어 재구매를 유도한다. "
                "상위 등급일수록 배송·쿠폰·상담 혜택이 커지는 구조가 일반적이다.",
        "weight": 3,
    },

    # ═══════════════════════════════════════════════════════════════════════════
    # v2 — **opaque-code 적대**: 식별자가 의미 없는 코드(에러코드·배치ID·약어 충돌)라
    #   bge-m3 가 코드를 거의 노이즈로 임베딩 → 벡터가 코드를 변별 못 함. 대신 distractor 가
    #   질문의 자연어(설명·증상)와 더 많이 겹치게 해 벡터가 distractor 를 정답 위로 올린다.
    #   정답·distractor 는 코드 외 prose 가 거의 평행(동일 토픽) → 코드가 유일한 변별자.
    #   trigram 만 코드 exact-match → fusion 이 끌어올리는지 측정.
    # ═══════════════════════════════════════════════════════════════════════════

    # 토픽 H: 배치 에러코드 (opaque: E5021). distractor 가 '배치 실패 원인' 설명을 더 풍부히.
    {
        "fact_key": "batch_error_e5021",
        # 정답: 코드 E5021 정확 + 짧은 설명.
        "text": "야간 정산 배치 로그에 E5021 이 찍히면 원천 테이블 잠금 타임아웃이다. "
                "재시도 큐로 자동 재실행되며 3회 실패 시 운영자에게 알림이 간다.",
        "weight": 3,
    },
    {
        "fact_key": "batch_failure_generic",
        # distractor: '배치 실패/타임아웃/재시도' 자연어가 질문과 더 많이 겹침. E5021 없음.
        "text": "정산 배치가 실패하는 가장 흔한 원인은 원천 테이블에 다른 트랜잭션이 오래 락을 "
                "잡고 있어 타임아웃이 나는 경우다. 이럴 땐 보통 자동 재시도로 해결되지만 "
                "반복되면 잠금을 유발한 쿼리를 찾아 튜닝해야 하고 운영자 확인이 필요하다.",
        "weight": 3,
    },

    # 토픽 I: 약어 충돌 (opaque: CTR — click-through vs contract). distractor 가 '전환/클릭'
    #   자연어로 더 가깝게. 정답은 'CTR' 정의(계약 수, contract count)로 약어 의미 충돌 유발.
    {
        "fact_key": "ctr_contract_metric",
        # 정답: CTR 을 '계약 건수(contract)' 사내 약어로 정의 — 외부 통념(클릭률)과 충돌.
        "text": "사내 지표 CTR 은 click-through 가 아니라 contract 의 약자로, 기간 내 신규 체결된 "
                "계약 건수를 뜻한다. 영업팀 대시보드에서 월별 CTR 추이를 본다.",
        "weight": 3,
    },
    {
        "fact_key": "clickthrough_rate_prose",
        # distractor: 질문이 '지표/비율/전환' 뉘앙스면 벡터가 일반적 클릭률 설명을 더 가깝게 봄.
        "text": "광고나 배너의 성과는 노출 대비 클릭이 얼마나 일어났는지의 비율로 측정한다. "
                "이 전환 지표가 높을수록 소재가 사용자 관심을 끈다고 해석한다.",
        "weight": 3,
    },

    # 토픽 J: 피처 플래그 키 (opaque: ff_new_checkout_v3). distractor 가 '새 결제 플로우'
    #   자연어로 더 가깝게. 정답은 정확한 플래그 키 문자열 보유.
    {
        "fact_key": "feature_flag_checkout_v3",
        # 정답: 플래그 키 ff_new_checkout_v3 정확 포함.
        "text": "신규 결제 화면 노출은 ff_new_checkout_v3 플래그로 제어한다. on 이면 단일 페이지 "
                "결제, off 면 기존 다단계 결제가 뜬다. 점진 배포 비율은 설정 콘솔에서 조정한다.",
        "weight": 3,
    },
    {
        "fact_key": "new_checkout_flow_prose",
        # distractor: '새 결제 플로우/단일 페이지' 자연어가 질문과 더 겹침. 플래그 키 없음.
        "text": "새 결제 플로우는 여러 단계로 나뉘던 주문 과정을 한 화면에 모아 이탈을 줄이도록 "
                "개편한 것이다. 일부 사용자에게만 먼저 보여 주고 성과를 본 뒤 전체로 확대한다.",
        "weight": 3,
    },

    # ═══════════════════════════════════════════════════════════════════════════
    # v3 — **검증된 vector-miss 적대**: 직접 cosine 측정으로 distractor 가 정답을 능가함을
    #   사전 확인한 케이스. 정답 doc = 코드/식별자 + '한 문장 설명'(현실적 짧은 KB 항목),
    #   distractor = 질문 증상 자연어를 풍부히 풀어 쓴 prose(코드 없음). bge-m3 cosine 에서
    #   distractor 가 정답보다 높거나 거의 같다 → 순수 벡터가 정답을 under-rank. trigram 의
    #   코드 exact-match 가 정답을 끌어올려 fusion 이 재랭킹하는지를 측정(공정: 코드를 정답에만,
    #   질문 문장 복붙 아님).
    # ═══════════════════════════════════════════════════════════════════════════

    # 토픽 K: PG 타임아웃 에러코드 (검증: code+desc 0.726 < rich distractor 0.761)
    {
        "fact_key": "err_pg_timeout_def",
        # 정답: 코드 + 한 문장(현실적 KB 항목 길이). distractor 보다 vector 낮게 측정됨.
        "text": "ERR_PG_TIMEOUT 는 결제 게이트웨이(PG) 응답 지연으로 승인이 시간 내 안 떨어진 경우다. "
                "재시도하거나 PG 상태를 확인해야 한다.",
        "weight": 3,
    },
    {
        "fact_key": "payment_stuck_prose",
        # distractor: 질문의 증상 자연어('결제 끊김/승인 지연/네트워크')를 풍부히 풀어 씀. 코드 없음.
        "text": "결제가 진행 중간에 자꾸 끊기고 카드사 승인이 제때 떨어지지 않는 문제는 보통 결제 "
                "게이트웨이 응답이 늦어지거나 네트워크가 불안정할 때 발생한다. 승인 대기가 길어지면 "
                "사용자는 결제가 멈춘 것처럼 느끼고 재시도하다가 중복 결제가 생기기도 한다.",
        "weight": 3,
    },

    # 토픽 L: 재고 동기화 잡 ID (opaque: SYNC_INV_07). distractor 가 '재고 안 맞음/동기화 지연'
    #   증상을 풍부히 풀어 query 와 더 겹치게.
    {
        "fact_key": "inv_sync_job_def",
        # 정답: 잡 ID + 한 문장.
        "text": "재고 수량 불일치는 야간 동기화 잡 SYNC_INV_07 이 실패하면 발생한다. 이 잡을 수동 "
                "재실행하면 창고 실수량과 판매 가능 수량이 다시 맞춰진다.",
        "weight": 3,
    },
    {
        "fact_key": "stock_mismatch_prose",
        # distractor: '재고가 안 맞다/판매 수량 차이/동기화' 증상 자연어 풍부. 잡 ID 없음.
        "text": "화면에 보이는 판매 가능 수량과 창고의 실제 재고가 서로 맞지 않는 일이 가끔 생긴다. "
                "보통 밤사이 수량을 맞추는 동기화 과정이 제대로 끝나지 않았을 때 이런 차이가 나며, "
                "주문이 몰리는 시간대에 특히 눈에 띈다.",
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
                cur.execute(
                    "INSERT INTO texts (text_hash, text_content, embedding, embedding_model, embedded_at) "
                    "VALUES (%s, %s, %s::vector, %s, now()) "
                    "ON CONFLICT (text_hash) DO UPDATE SET "
                    "  embedding = EXCLUDED.embedding, embedding_model = EXCLUDED.embedding_model, "
                    "  embedded_at = now()",
                    (th, text, emb, cfg.AGENT_KB_EMBEDDING_MODEL),
                )
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
    print(f"[provision_kb_adv] {n} docs 적재 완료 (scope={EVAL_SCOPE}, conversation={EVAL_CONVERSATION_ID})")
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
    print(f"[provision_kb_adv] purge: {deleted} adv eval docs 삭제 (scope={EVAL_SCOPE})")
    return deleted


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="ITEM-05 적대적 KB retrieval eval set provisioner (evalkb_adv scope)")
    p.add_argument("--purge", action="store_true", help="evalkb_adv scope rag_documents 삭제(정리)")
    args = p.parse_args(argv)
    if args.purge:
        purge()
    else:
        provision()
    return 0


if __name__ == "__main__":
    sys.exit(main())
