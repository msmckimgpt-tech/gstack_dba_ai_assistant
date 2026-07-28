# codex review (adversarial) — graph-hop-budget · 4 rounds

- Agent: codex-cli 0.145.0 (model gpt-5.6-luna, reasoning xhigh, sandbox read-only)
- Command: `codex review --base origin/main` (repo 접근 있는 독립 리뷰어 — subagent 아님)
- Scope: 미커밋 changeset vs origin/main (backend metadata_graph.neighborhood + web routers/static)
- Gate: codex P1 = GATE. R2·R3·R4 에서 **P1 0건**.

## Round 1

```
The patch improves hop prioritization but can still silently omit relationship edges and can discard the parent table needed to render selected relationship columns when the node budget is exhausted.

Full review comments:

- [P1] Reserve a node slot for backfilled parent tables — unit/feature-0002-agent-core/src/modules/metadata_graph.py:1993-1997
  When a depth-2+ REFERENCES result selects a target Column but the candidate loop has already filled the 300-node cap, this loop breaks before adding that Column's parent Table. `graph-core.js` only renders columns when their parent Table is present, so the selected relationship column and its edge become invisible exactly on capped graphs; reserve space for required parent tables or rank them with the candidates.

- [P2] Report truncation caused by the edge-query limit — unit/feature-0002-agent-core/src/modules/metadata_graph.py:1913-1913
  When a frontier has more than `_NEIGHBOR_NODE_CAP * 4` matching edges, this global `LIMIT` truncates the UNION before candidates are ranked, potentially dropping later REFERENCES or ROUTINE_USES edges. Because `truncated` is only set when the node cap is reached, the API can return an incomplete graph with `truncated: false`, making the new priority and completeness warning inaccurate; track this query truncation or remove the silent limit.
```

## Round 2

```
The patch improves hop budgeting and truncation reporting, but stale broken edges can consume the new priority budget, edge overflow is not deterministically prioritized, and the UI can incorrectly omit the relation-less expansion notice.

Full review comments:

- [P2] Exclude broken edges from the priority pool — unit/feature-0002-agent-core/src/modules/metadata_graph.py:1943-1943
  When stale `broken` `REFERENCES` or `ROUTINE_USES` rows remain until the next sync, their endpoints are still added to `rel_gids` here and receive priority, but the edges are discarded later by the `estatus == "broken"` check. With enough such rows, invalid neighbors consume the cap and displace valid tables or columns, so filter broken edges before assigning relation priority.

- [P2] Preserve priority ordering before the edge fetch limit — unit/feature-0002-agent-core/src/modules/metadata_graph.py:1921-1921
  When a frontier has more than `_EDGE_FETCH_CAP` matching edges, this global `LIMIT` is applied without an `ORDER BY` before `rel_gids` and label priorities are computed. PostgreSQL can therefore return an arbitrary subset that omits important relationship edges, making the claimed deterministic relationship-first selection untrue and potentially dropping useful neighbors despite the later sorting.

- [P2] Detect relation-less expansion beyond the first hop — unit/feature-0003-agent-web-ui/src/static/graph/graph-ctxmenu.js:1245-1245
  When a node has a direct relationship edge at hop 1 but no relationship edges at later hops, this check sees the hop-1 edge and suppresses the hint even though the requested 2-hop/3-hop result adds nothing. Track only edges discovered beyond hop 1, or return explicit expansion metadata, so users are told when the selected depth produces the same graph.
```

## Round 3

```
The hop filtering direction is reasonable, but the new truncation and expansion signals can report false states, and capped parent or stale-edge selection is not fully deterministic or priority-safe.

Full review comments:

- [P2] Detect edge truncation with a cap-plus-one fetch — unit/feature-0002-agent-core/src/modules/metadata_graph.py:1940-1942
  When a hop returns exactly `_EDGE_FETCH_CAP` rows, the `LIMIT` has not shown that any rows were omitted, but `len(_edge_rows) >= _EDGE_FETCH_CAP` still marks the response as truncated. Complete neighborhoods at the boundary will therefore display a false partial-results warning; fetch one extra row or otherwise distinguish overflow before setting the flag.

- [P2] Do not infer relation loss from node-count deltas — unit/feature-0003-agent-web-ui/src/static/graph/graph-ctxmenu.js:1251-1254
  For depth greater than one, zero newly added nodes is treated as proof that no relation was expandable. A later hop can still add an edge between already discovered nodes, such as a self-referential column pair, and a cap can stop the loop before the later hop is even attempted; both cases incorrectly produce the “1-hop identical/no relations” message. Track per-hop edge additions and completion, or suppress this hint when the traversal is truncated.

- [P2] Order parent backfills before enforcing the cap — unit/feature-0002-agent-core/src/modules/metadata_graph.py:2034-2038
  When more distinct related columns need parent tables than the reserved slots, `_prows` is consumed in database-return order because neither this query nor the preceding `DISTINCT` query specifies an order. Which parent tables survive the cap can therefore vary with PostgreSQL's plan or physical row order, violating the documented graphid tie-break and producing different partial graphs for the same anchor and depth. Sort by graphid before applying the cap.

- [P2] Exclude broken edges before applying the edge cap — unit/feature-0002-agent-core/src/modules/metadata_graph.py:1929-1933
  In the stale-edge scenario this change explicitly handles, broken relation rows still receive SQL priority `0`; `is_rel` removes their endpoints from `rel_gids` only after the `LIMIT` has already discarded later rows. If enough stale broken rows fill the fetch cap, valid `REFERENCES` or `ROUTINE_USES` edges are never considered and are lost despite the later candidate-tier fix. Filter or deprioritize broken rows before applying the cap.
```

## Round 4

```
The patch improves hop prioritization but still allows broken relationships to influence returned nodes and budget allocation. It also misreports truncation in legacy-response scenarios and can unnecessarily discard valid relation endpoints near the cap.

Full review comments:

- [P2] Exclude broken endpoints before Column parent backfill — unit/feature-0002-agent-core/src/modules/metadata_graph.py:2034-2035
  When a `REFERENCES` row has `status='broken'`, the edge is discarded later, but this branch still adds its Column graphid to `new_col_gids`; the following `HAS_COLUMN` lookup then backfills and returns the parent Table and synthetic edge. During the sync window, a broken relationship can therefore make unrelated nodes appear in the 2-hop graph and suppress the “no relation” hint. Only columns reached through non-broken relation edges should be backfilled.

- [P2] Keep broken edges out of the fetch budget — unit/feature-0002-agent-core/src/modules/metadata_graph.py:1943-1947
  When a frontier has more than `_EDGE_FETCH_CAP` incident edges and many broken relation rows, relation labels still receive `prio=0`, so broken rows `(prio=0, brk=1)` sort ahead of valid hierarchy rows `(prio=1, brk=0)`. The limit can therefore be filled with edges that Python immediately drops, hiding valid neighbors; broken rows should sort after valid hierarchy edges or be excluded before applying the cap.

- [P2] Base the parent reserve on unresolved parents — unit/feature-0002-agent-core/src/modules/metadata_graph.py:2015-2018
  At hop 2 or later, `_rel_col_n` counts every relation Column and `_cap` is compared against the cumulative `seen_nodes` count, even when the Column’s parent Table is already in `gid2key`. If only one result slot remains, the reserve makes `_cap` equal the current count and drops a valid relation endpoint despite no parent slot being needed. Reserve capacity only for unresolved parent Tables.

- [P2] Preserve accurate warnings for legacy truncated responses — unit/feature-0003-agent-web-ui/src/static/graph/graph-ctxmenu.js:1816-1824
  During a rolling deployment with an older backend, `data.truncated` can be true while `truncated_hop` is absent. This code maps that to hop 0 and then reports it as a 2-hop truncation, claiming direct lists are complete even when a depth-1 response was cut at the direct-neighbor cap. Use the requested depth or retain a generic legacy warning when hop metadata is missing.
```

