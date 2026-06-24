"""ITEM-05 KB-주석 retrieval eval set (fusion vs 2-tier A/B).

provision_kb : evalkb scope 합성 KB 멱등 적재(+ bge-m3 임베딩) / --purge 정리
retrieval_eval : fusion ON/OFF retrieval 직접 호출 → precision/recall@k A/B 리포트
golden_retrieval.yaml : 질문 + ground-truth relevant_doc_keys
"""
