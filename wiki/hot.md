---
doc_type: WIKI_HOT_CACHE
last_updated: 2026-06-23
---

# Hot Cache

## Last Updated
2026-06-23

## Key Recent Facts
- insight-worker "DB 파악 진전 없음" 병목 = 2축: **축A 커버리지** 39 catalog DB 중 28개 RO 로그인 per-DB GRANT 누락(권한 18456/916) → 영구 스캔실패·status=degraded(서킷이 host:port 단위라 per-DB 권한실패 미격리). **1차 해결=운영 GRANT, 코드 아님**. **축B 처리량** RC3 force_scan latch + RC2 fingerprint churn 로 살아있는 DB 도 신규통찰 0.

## Recent Changes
- TASK-0305(insight.py): RC2 fingerprint casefold(VALUE 한정, 키 불변), RC3 진전기반 backoff(`_repair_backoff_active`/`_set`/`_clear`, per-scope KV — pending-only 무진전 spin 차단, 건강한 처리량·ANCHOR §3 보존), RC5 cycle summary `db_failed_{perm,circuit,other}` + 비-MSSQL ds 집계. 테스트 8 + 회귀 0, 적대 리뷰 ACCEPT. [[insight-worker]]

## Active Threads
- 배포: agent 이미지 재빌드(insight-worker baked, 마이그 없음) → 라이브 검증(db_failed 사유분포·log_v2 진동 종식·tick spacing).
- 사용자 조치(축A): RC5 배포 후 db_failed_perm 으로 GRANT 대상 특정 → bin/datasource-mssql-ro-bootstrap-multidb.sql. RC4(budget throughput) 전용 조사 deferred.
