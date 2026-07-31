"""feature-0033-analysis-synthesis — L2 클러스터 합성 요약 단위 테스트.

검증 축:
  A(캐시 계약): 멤버셋 + L1 지문 + L0 지문 + **라벨** 일치일 때만 캐시 적중. 하나라도 다르면 재생성.
     (라벨은 label-canon 2026-07-31 에 추가 — 요약 프롬프트가 label 을 입력으로 받으므로
      라벨이 바뀌면 요약문이 낡는다.)
  B(결정적 정렬): 입력 순서가 달라도 같은 버전 지문 — 정렬이 빠지면 캐시가 오적중한다.
  C(비용 유계): pass 당 생성 상한 · 배치 크기 · LLM 실패 시 부분 성공 유지.
  D(불변식): 요약이 클러스터링 시그니처에 유입되지 않는다(유입되면 재임베딩 순환).
  E(정직성): 근거가 된 멤버 수(analyzed_count)를 저장한다.
"""
import pytest

from modules import semantic_cluster as sc


class _Cur:
    def __init__(self, cached_rows=None, evidence_rows=None):
        self.cached_rows = cached_rows or []
        self.evidence_rows = evidence_rows or []
        self.executed = []
        self._last = []

    def execute(self, sql, params=None):
        self.executed.append((" ".join(sql.split()), params))
        if "FROM cluster_summaries" in sql:
            self._last = self.cached_rows
        elif "FROM metadata_table_stats" in sql:
            self._last = self.evidence_rows
        else:
            self._last = []

    def fetchall(self):
        return self._last

    def fetchone(self):
        return self._last[0] if self._last else None

    def close(self):
        pass


def _cluster(mhash="h1", l1="v1", ev="e1", members=4, analyzed=2, label="몬스터 스폰"):
    return {"mhash": mhash, "cluster_id": 0, "label": label,
            "names": [f"t{i}" for i in range(members)],
            "analyses": ["이 테이블은 몬스터 스폰 정의를 담는다."] * analyzed,
            "member_count": members, "analyzed_count": analyzed,
            "l1_version": l1, "evidence_version": ev}


@pytest.fixture(autouse=True)
def _enabled(monkeypatch):
    monkeypatch.setattr(sc, "_summary_enabled", lambda: True)
    monkeypatch.setattr(sc, "_ds_display_label", lambda cur, k: "ds")


# ── B: 결정적 정렬 ───────────────────────────────────────────────────────────
def test_version_hash_is_order_independent():
    """입력 순서가 달라도 같은 지문이어야 한다 — 정렬이 빠지면 같은 클러스터가 pass 마다 다른
    버전을 받아 캐시가 매번 미스 나고 요약이 무한 재생성된다."""
    a = sc._version_hash(["b", "a", "c"])
    b = sc._version_hash(["c", "b", "a"])
    assert a == b and a != ""


def test_version_hash_changes_with_content():
    assert sc._version_hash(["a", "b"]) != sc._version_hash(["a", "c"])


def test_version_hash_empty_is_empty_string():
    assert sc._version_hash([]) == "" and sc._version_hash(["", None]) == ""


def test_member_set_hash_is_order_independent():
    assert sc._member_set_hash(["k2", "k1"]) == sc._member_set_hash(["k1", "k2"])


# ── A: 캐시 계약 (3중 일치) ──────────────────────────────────────────────────
def _run(monkeypatch, cur, clusters, llm_result=None, capture=None):
    calls = []

    def _fake_summary(payload, scope_key=None):
        calls.append(payload)
        if llm_result is not None:
            return llm_result
        return {"summaries": [{"idx": j, "summary": "몬스터 스폰 정의를 담는 묶음이다. 운영 조정 시 조회한다."}
                              for j in range(len(payload["clusters"]))]}

    import modules.llm as _llm
    monkeypatch.setattr(_llm, "llm_cluster_summary", _fake_summary, raising=False)
    puts = []
    # _summary_put 은 저장 성공 여부를 bool 로 돌려준다(codex P2) — stub 도 그 계약을 지킨다.
    monkeypatch.setattr(sc, "_summary_put",
                        lambda cur_, sk, sn, cl, summary, model: (puts.append((cl, summary)), True)[1])
    made = sc._llm_cluster_summaries(cur, "ds1", "app", clusters)
    if capture is not None:
        capture["calls"] = calls
        capture["puts"] = puts
    return made, calls, puts


def test_cache_hit_when_all_three_versions_match(monkeypatch):
    cur = _Cur(cached_rows=[("h1", "기존 요약", "v1", "e1", "몬스터 스폰")])
    made, calls, _ = _run(monkeypatch, cur, [_cluster(mhash="h1", l1="v1", ev="e1")])
    assert made == 0 and calls == [], "3중 일치인데 재생성했다"


def test_cache_miss_when_l1_version_changed(monkeypatch):
    """분석문(L1)이 갱신되면 요약도 낡은 것이다."""
    cur = _Cur(cached_rows=[("h1", "기존 요약", "v_old", "e1", "몬스터 스폰")])
    made, calls, _ = _run(monkeypatch, cur, [_cluster(mhash="h1", l1="v_new", ev="e1")])
    assert made == 1 and len(calls) == 1


def test_cache_miss_when_evidence_version_changed(monkeypatch):
    """증거(L0)가 갱신되면 요약도 낡은 것이다 — 증거 변경이 요약에 전파되는 유일한 경로."""
    cur = _Cur(cached_rows=[("h1", "기존 요약", "v1", "e_old", "몬스터 스폰")])
    made, calls, _ = _run(monkeypatch, cur, [_cluster(mhash="h1", l1="v1", ev="e_new")])
    assert made == 1 and len(calls) == 1


def test_cache_miss_when_label_changed(monkeypatch):
    """라벨이 바뀌면 요약도 낡은 것이다 — label-canon(2026-07-31) §18.8 codex P1.

    스키마 간 어휘 통일이 라벨만 바꾸는데, 종전 캐시 키(멤버셋+L1+L0)에는 라벨이 없어
    **기존 요약이 옛 어휘로 영구히 남았다**(밴드는 `거래 시스템`, 요약문은 `거래 처리`).
    생성 시점을 통일 이후로 옮긴 것만으로는 신규분만 고쳐진다."""
    cur = _Cur(cached_rows=[("h1", "기존 요약", "v1", "e1", "거래 처리")])
    made, calls, _ = _run(monkeypatch, cur, [_cluster(mhash="h1", l1="v1", ev="e1", label="거래 시스템")])
    assert made == 1 and len(calls) == 1, "라벨이 바뀌었는데 요약을 재생성하지 않았다"


def test_cache_miss_when_member_set_changed(monkeypatch):
    """멤버가 바뀌면 다른 클러스터다 — 저장된 해시가 없으므로 미스."""
    cur = _Cur(cached_rows=[("h_other", "기존 요약", "v1", "e1", "몬스터 스폰")])
    made, calls, _ = _run(monkeypatch, cur, [_cluster(mhash="h1", l1="v1", ev="e1")])
    assert made == 1


def test_cache_query_failure_falls_back_to_regenerate(monkeypatch):
    """캐시 조회 실패(테이블 부재 등)는 전량 미스로 — 요약이 없는 편이 낫지 잘못된 캐시는 안 된다."""
    class _Boom(_Cur):
        def execute(self, sql, params=None):
            if "FROM cluster_summaries" in sql:
                raise RuntimeError("relation does not exist")
            super().execute(sql, params)

    made, _calls, _ = _run(monkeypatch, _Boom(), [_cluster()])
    assert made == 1


# ── C: 비용 유계 ────────────────────────────────────────────────────────────
def test_pass_generation_cap(monkeypatch):
    """pass 당 상한 — 818개 클러스터를 첫 실행에 전부 만들지 않는다."""
    clusters = [_cluster(mhash=f"h{i}") for i in range(sc._SUMMARY_MAX_PER_PASS + 25)]
    made, calls, _ = _run(monkeypatch, _Cur(), clusters)
    assert made == sc._SUMMARY_MAX_PER_PASS
    total_in_payload = sum(len(c["clusters"]) for c in calls)
    assert total_in_payload == sc._SUMMARY_MAX_PER_PASS


def test_batch_size_is_small_enough_for_long_answers(monkeypatch):
    """라벨용 배치(40)는 요약엔 과다하다 — 응답이 길어 잘린다."""
    assert 1 < sc._SUMMARY_CLUSTERS_PER_CALL <= 8
    clusters = [_cluster(mhash=f"h{i}") for i in range(13)]
    _made, calls, _ = _run(monkeypatch, _Cur(), clusters)
    assert all(len(c["clusters"]) <= sc._SUMMARY_CLUSTERS_PER_CALL for c in calls)


def test_larger_clusters_are_summarized_first(monkeypatch):
    """상한에 걸릴 때 도메인 파악 기여가 큰 큰 클러스터부터. 동률은 해시 순(결정적)."""
    clusters = [_cluster(mhash=f"h{i}", members=i + 1) for i in range(sc._SUMMARY_MAX_PER_PASS + 5)]
    _made, calls, puts = _run(monkeypatch, _Cur(), clusters)
    picked = [cl["member_count"] for cl, _s in puts]
    assert min(picked) > 5, "작은 클러스터가 큰 것보다 먼저 선택됐다"


def test_llm_failure_keeps_partial_progress(monkeypatch):
    """배치 도중 LLM 실패 시 앞서 성공한 요약은 유지하고 그 pass 만 중단한다."""
    seq = [None]

    def _flaky(payload, scope_key=None):
        if seq[0] is None:
            seq[0] = 1
            return {"summaries": [{"idx": j, "summary": "충분히 긴 한국어 요약 문장이다. 운영에서 쓴다."}
                                  for j in range(len(payload["clusters"]))]}
        return None

    import modules.llm as _llm
    monkeypatch.setattr(_llm, "llm_cluster_summary", _flaky, raising=False)
    puts = []
    monkeypatch.setattr(sc, "_summary_put", lambda *a: (puts.append(a), True)[1])
    clusters = [_cluster(mhash=f"h{i}") for i in range(sc._SUMMARY_CLUSTERS_PER_CALL * 3)]
    made = sc._llm_cluster_summaries(_Cur(), "ds1", "app", clusters)
    assert made == sc._SUMMARY_CLUSTERS_PER_CALL and len(puts) == made


def test_thin_response_is_not_stored(monkeypatch):
    """빈약한 응답을 저장하면 캐시가 적중해 영원히 그 상태로 굳는다."""
    made, _calls, puts = _run(monkeypatch, _Cur(), [_cluster()],
                              llm_result={"summaries": [{"idx": 0, "summary": "짧음"}]})
    assert made == 0 and puts == []


def test_disabled_switch_skips_everything(monkeypatch):
    monkeypatch.setattr(sc, "_summary_enabled", lambda: False)
    made, calls, _ = _run(monkeypatch, _Cur(), [_cluster()])
    assert made == 0 and calls == []


# ── E: 정직성 ───────────────────────────────────────────────────────────────
def test_payload_carries_coverage_counts(monkeypatch):
    """멤버 20개 중 3개만 분석이 있는 것과 20개 다 있는 것은 신뢰도가 전혀 다르다."""
    _made, calls, puts = _run(monkeypatch, _Cur(), [_cluster(members=20, analyzed=3)])
    c = calls[0]["clusters"][0]
    assert c["member_count"] == 20 and c["analyzed_count"] == 3
    stored_cl = puts[0][0]
    assert stored_cl["analyzed_count"] == 3 and stored_cl["member_count"] == 20


def test_payload_caps_members_and_analyses(monkeypatch):
    big = _cluster(members=200, analyzed=50)
    _made, calls, _ = _run(monkeypatch, _Cur(), [big])
    c = calls[0]["clusters"][0]
    assert len(c["members"]) <= sc._SUMMARY_MEMBERS_CAP
    assert len(c["analyses"]) <= sc._SUMMARY_ANALYSES_CAP


# ── D: 시그니처 미유입 불변식 ────────────────────────────────────────────────
def test_summary_never_enters_the_clustering_signature():
    """요약이 시그니처에 들어가면 요약 갱신 → 재임베딩 → 재클러스터 → 요약 갱신의 순환이 된다.

    시그니처 빌더가 요약 텍스트를 인자로도 받지 않고 결과에 포함하지도 않음을 단정한다."""
    import inspect
    src = inspect.getsource(sc.build_table_signature_text)
    for forbidden in ("cluster_summaries", "summary", "_llm_cluster_summaries"):
        assert forbidden not in src, f"시그니처 빌더가 {forbidden} 를 참조한다 — 순환 위험"
    sig = inspect.signature(sc.build_table_signature_text)
    assert "summary" not in sig.parameters


def test_evidence_versions_is_failsoft_without_stats_table():
    class _NoTable(_Cur):
        def execute(self, sql, params=None):
            raise RuntimeError("relation \"metadata_table_stats\" does not exist")

    assert sc._evidence_versions(_NoTable(), "ds1", "app") == {}


# ── codex 리뷰 회귀 방지 ─────────────────────────────────────────────────────
def test_remaining_caps_across_schema_loop(monkeypatch):
    """상한은 pass 전체 기준이다 — 이 함수는 effective-schema 루프 안에서 불리므로 스키마마다
    상한을 새로 주면 총량이 스키마 수만큼 곱해진다(라이브 스키마 수백 개 → 비용 폭주, codex P1)."""
    clusters = [_cluster(mhash=f"h{i}") for i in range(30)]
    made, _calls, _ = _run(monkeypatch, _Cur(), clusters)   # remaining 미지정 = 기본 상한
    assert made == 30

    # 이미 38개를 쓴 pass 라면 남은 2개만 만들어야 한다.
    import modules.llm as _llm
    monkeypatch.setattr(_llm, "llm_cluster_summary",
                        lambda payload, scope_key=None: {
                            "summaries": [{"idx": j, "summary": "충분히 긴 한국어 요약 문장이다. 운영에 쓴다."}
                                          for j in range(len(payload["clusters"]))]},
                        raising=False)
    monkeypatch.setattr(sc, "_summary_put", lambda *a: True)
    made2 = sc._llm_cluster_summaries(_Cur(), "ds1", "app", clusters, remaining=2)
    assert made2 == 2

    assert sc._llm_cluster_summaries(_Cur(), "ds1", "app", clusters, remaining=0) == 0


def test_failed_store_is_not_counted_as_made(monkeypatch):
    """저장 실패를 성공으로 세면 캐시는 계속 미스인데 보고는 성공이라, 다음 pass 마다 같은
    요약을 다시 만든다(조용한 반복 비용, codex P2)."""
    import modules.llm as _llm
    monkeypatch.setattr(_llm, "llm_cluster_summary",
                        lambda payload, scope_key=None: {
                            "summaries": [{"idx": j, "summary": "충분히 긴 한국어 요약 문장이다. 운영에 쓴다."}
                                          for j in range(len(payload["clusters"]))]},
                        raising=False)
    monkeypatch.setattr(sc, "_summary_put", lambda *a: False)   # 저장 실패
    assert sc._llm_cluster_summaries(_Cur(), "ds1", "app", [_cluster()]) == 0


def test_version_hash_encoding_is_injective():
    """구분자 충돌 방지 — 개행 결합은 서로 다른 집합을 같은 지문으로 만든다(codex P2)."""
    assert sc._version_hash(["a\nb", "c"]) != sc._version_hash(["a", "b\nc"])
    assert sc._version_hash(["ab", "c"]) != sc._version_hash(["a", "bc"])


def test_reads_and_writes_use_savepoint():
    """신규 테이블이 없는 배포 창에서 SELECT 실패가 트랜잭션을 abort 시키면, 뒤따르는 라벨
    역기록 UPDATE 가 전부 깨진다 — "요약 실패가 클러스터링을 막지 않는다"가 무너진다(codex P2)."""
    class _SpyCur(_Cur):
        def __init__(self):
            super().__init__()
            self.savepoints = 0

        def execute(self, sql, params=None):
            if "SAVEPOINT" in sql.upper():
                self.savepoints += 1
                return
            super().execute(sql, params)

    c1 = _SpyCur()
    sc._evidence_versions(c1, "ds1", "app")
    assert c1.savepoints >= 1

    c2 = _SpyCur()
    sc._summary_cache(c2, "ds1", "app", ["h1"])
    assert c2.savepoints >= 1


def test_token_budget_is_rechecked_per_batch(monkeypatch):
    """예산을 pass 진입 시 1회만 보면 긴 pass 도중 소진돼도 끝까지 호출한다 — 상한이 있으나
    마나가 된다(codex P1). `acquire("llm")` 은 동시성 슬롯일 뿐 누적 소비와 무관한 축이다."""
    import shared.llm_budget as lb
    seen = {"n": 0}

    def _allowed():
        seen["n"] += 1
        return seen["n"] <= 1        # 첫 배치만 허용

    monkeypatch.setattr(lb, "allowed", _allowed)
    import modules.llm as _llm
    monkeypatch.setattr(_llm, "llm_cluster_summary",
                        lambda payload, scope_key=None: {
                            "summaries": [{"idx": j, "summary": "충분히 긴 한국어 요약 문장이다. 운영에 쓴다."}
                                          for j in range(len(payload["clusters"]))]},
                        raising=False)
    monkeypatch.setattr(sc, "_summary_put", lambda *a: True)
    clusters = [_cluster(mhash=f"h{i}") for i in range(sc._SUMMARY_CLUSTERS_PER_CALL * 3)]
    made = sc._llm_cluster_summaries(_Cur(), "ds1", "app", clusters)
    assert made == sc._SUMMARY_CLUSTERS_PER_CALL, "예산 소진 후에도 계속 호출했다"
    assert seen["n"] >= 2, "배치마다 예산을 다시 보지 않았다"


def test_evidence_versions_keys_are_casefolded():
    """증거 테이블명과 멤버명의 대소문자가 어긋나면 매칭이 늘 실패해 evidence_version 이 영구히
    ""가 되고, L0 변경이 요약에 전파되는 유일한 경로가 조용히 죽는다(codex P1)."""
    import datetime as _dt

    class _C(_Cur):
        def execute(self, sql, params=None):
            if "SAVEPOINT" in sql.upper():
                return
            self._last = [("CharacterItem", _dt.datetime(2026, 7, 30))]

    out = sc._evidence_versions(_C(), "ds1", "app")
    assert "characteritem" in out, f"casefold 정규화가 없다: {list(out)}"
