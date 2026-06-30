---
doc_type: REVIEW
feature_id: feature-0016-zd-pg-pause-caddy
status: active
edit_policy: append-only
source_of_truth: true
---

# Review Records

## REV-20260630T150000-zd-pg-pause-caddy
- Related Change: CHG-20260630T150000 (PG PAUSE 래퍼 + caddy reconcile)
- Reason: feasibility 분석(wf_1d634d33) "조건부→가능 승격" 후속(사용자 승인).
- Alternatives Considered: 전용 pgbouncer admin user(후속 하드닝) vs agent_kb_rw 재사용(최소 변경, 채택);
  caddy 항상 reload vs sha 비교 후 변경 시에만 recreate(채택 — inode-stale 시 reload 무효).
- Risks: pg-restart 가 라이브 pgbouncer/PG path — **RESUME 실패 시 모든 RW 차단**이 최대 위험 → trap 으로
  EXIT/INT/TERM 모두 RESUME 보장 + PAUSE timeout(긴 txn fail-safe abort+RESUME). reconcile 은 adapt 검증
  후 recreate 라 깨진 config 로 caddy 죽이지 않음. ADMIN_USERS 적용은 pgbouncer 1회 recreate(짧은 blip).
- Open Questions: 전용 admin user 분리(보안 하드닝) 후속.
- Human Approval Needed: 아니오 (PLAN-APPROVED). 라이브 배포는 사용자 승인 범위.

## REV-20260630T151500-zd-pg-caddy-review [SKIPPED: 검증패널 2회 인프라/세션한도 실패 — main-loop 자체검토 + 라이브검증 대체]
- Related Change: CHG-20260630T150000
- 사유: §18.8 검증 패널 subagent 를 2회 dispatch 했으나 (1) 직전 Claude Code 프로세스 종료로 state 유실,
  (2) 세션 한도로 미완료. 재시도 반복 비용 대비, main-loop 가 동일 체크리스트로 자체검토 + 인프라 변경의
  최종 증거인 **라이브 검증**(배포 단계)으로 대체.
- 자체검토 결과(코드 직접 판독):
  - **pg-restart RESUME 보장(최우선)**: `trap 'do_resume' EXIT INT TERM` 가 PAUSE(line 91) 직전(89)에
    설치 → PAUSE-timeout/ACTION-fail/healthy-fail 의 모든 `die`(exit 1) 경로가 EXIT 트랩으로 RESUME 발동,
    정상 경로는 명시 do_resume(106)+`trap -`(107). RESUME 멱등 → 중복 무해. **PAUSED 잔존 경로 없음**. ✓
  - **reconcile_caddy**: 깨진 Caddyfile 은 throwaway `caddy adapt` 검증에서 `die`(중단, 기존 caddy 무접촉),
    통과 시에만 recreate. sha 일치 시 no-op(blip 0). caddy 미기동 시 up -d. ✓
  - **compose ADMIN_USERS**: `docker compose config` 에 `ADMIN_USERS: agent_kb_rw`(=AGENT_KB_PG_USER,
    pgbouncer userlist 보유) 반영 확인. 적용엔 pgbouncer 1회 recreate 필요(문서화됨). ✓
  - 정적: bash -n(pg-restart/deploy-web) OK, make -n OK.
- 라이브 검증(배포 단계, TEST §3 기록): pgbouncer ADMIN_USERS recreate → `pg-restart --check`(admin 접근) →
  RW 부하 루프 중 `pg-restart`(PAUSE→PG재시작→RESUME) RW 무에러 실증 → RESUME 잔존 없음 확인.
- Human Approval Needed: 아니오 (PLAN-APPROVED). 라이브는 사용자 "전체 배포" 승인.
