---
run_at: 2026-09-02T16:00:00+09:00
session: ai/root/graph-sync-retract (POST-DEPLOY)
scope: sync 용어 회수 단계 — 라이브 실증 (20260902T140000-graph-sync-retract)
verdict: PASS
---

### Run 1 — 단위 + 뮤테이션
- `test_graph_glossary_retract.py` **10 passed**.
- 뮤테이션 **7/7 KILL**(baseline green 확인 후): 증분 가드 제거 · 미배선 · 투영보다 앞 ·
  키 생성기 불일치 · scope 필터 제거 · 이스케이프 우회 · 카운터 초기화 제거.
- codex P3 조치 후 3건 추가(JSON 파싱 · 파싱 실패 skip · 카운터) → 총 10건.

### Run 2 — 컨테이너 전건
`make test` rc=0 · FAILED 0 · ruff clean (P3 조치 후 재실행 포함).

### Run 3 — **라이브 실증** (배포 `3e26527c`, Environment: 배포된 insight-worker 컨테이너)

배포본에 회수 단계가 실렸는지 먼저 확인:
`'_run_step("kb_glossary_retract"' in inspect.getsource(sync_graph)` → **True**.

**의도적 유령 정점을 심어** 회수를 실증했다 — 관측만으로는 「지울 게 없어서 0」과
「단계가 안 돌아서 0」이 구별되지 않는다.

    CREATE (g:GlossaryTerm {key:'product.gz_qa_g:term:__RETRACT_PROBE__', …})
    → kb_glossary 에는 0건, 그래프에만 1건 (638 → 639)

**전건 sync**(`scope_key='product.gz_qa_g'`, `since=None`):

| 지표 | 값 |
|---|---|
| `glossary` (투영) | 199 |
| **`glossary_retracted`** | **1** |
| `glossary_retract_skipped` | `''` |
| `glossary_retract_unparsed` | 0 |
| `errors` | 0 |

검증:

| 검사 | 결과 |
|---|---|
| 유령 프로브 | **제거됨(0건)** |
| GZ_QA_G 정상 용어 | 그래프 **199 = DB 199** (손실 0) |
| 전체 | 그래프 **638 = DB 638** |

### Run 4 — 증분 가드 실증 (가장 위험한 지점)
같은 scope 에 `since=2026-09-02T00:00` 으로 **증분** 실행:

| 지표 | 값 |
|---|---|
| `glossary` (투영) | 2 |
| **`glossary_retracted`** | **0** |
| **`glossary_retract_skipped`** | **`'incremental'`** |
| 실행 후 GZ_QA_G 용어 | **199 (전건 보존)** |

증분에서 회수가 돌았다면 「그 시각 이후 변경분」 2건만 live 로 보고 **나머지 197건을 지웠을
것**이다. 가드가 그것을 막았고, 건너뛴 사실이 payload 에 남는다.

### 남긴 것 (정직)
- **용어 축만** 회수한다. 물리 스키마 축(Table·Column·Routine)은 원본 판정이 달라 운영 DB
  조회가 필요하고, 접속 실패를 「없다」로 오판하면 멀쩡한 정점을 지운다.
- codex P2(조회~삭제 비원자성)는 미해소 — 창이 좁고 다음 full sync 가 재투영한다(REVIEW §3).
