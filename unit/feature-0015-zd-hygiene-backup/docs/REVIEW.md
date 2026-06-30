---
doc_type: REVIEW
feature_id: feature-0015-zd-hygiene-backup
status: active
edit_policy: append-only
source_of_truth: true
---

# Review Records

## REV-20260630T140000-zd-hygiene-backup
- Related Change: CHG-20260630T140000 (①②⑤ 무중단 위생 + 백업)
- Reason: feature-0014 후속. 무중단 feasibility 분석(wf_1d634d33)이 "단일 호스트·1인 사용자에선 HA 가
  아니라 데이터 보존이 진짜 위험, 코드·expand 무중단은 이미 됨, 남은 가치는 저비용 위생작업" 으로 결론 →
  사용자가 ①②⑤ 승인.
- Alternatives Considered: HA(멀티노드/failover) 불채택(replica 동일 호스트라 흉내, ROI 음). 기존 ALTER
  retrofit 불채택(try/except 멱등가드 + LOCK=NONE silent-skip 위험 → diff-mode grandfather).
- Risks: ① graceful 은 cycle 경계 종료라 mid-LLM cycle 은 grace(30s) 초과 시 SIGKILL — 단 쓰기 멱등이
  backstop. ② lint 는 휴리스틱(스키마 비수식 ALTER) — escape 제공. ⑤ restore-rehearsal 은 DB 복원 —
  프로덕션 미접촉(throwaway DB only)이 핵심 안전 요건. cron 은 호스트 변경.
- Open Questions: ③ pgbouncer PAUSE 래퍼·PITR 는 후속.
- Human Approval Needed: 아니오 (PLAN-APPROVED 2026-06-30). 배포(insight recreate + cron)는 사용자
  "전체 배포" 승인 범위 + 라이브 사용자 1명.

## REV-20260630T140500-zd-hygiene-panel [AGENT-TEAM: backend+safety]
- Related Change: CHG-20260630T140000 (구현 diff 검증 패널 — §18.8)
- Panel: 독립 리뷰어가 staged diff 를 **실 백업 포맷**(artifacts/backups/20260602_153014)에 대조 검증.
- Verdict: **must-fix 없음.** 최우선 관심사 충족 — restore-rehearsal.sh 가 프로덕션 agent_kb/agent_memory 를
  훼손 불가함이 실증됨:
  - MySQL: 실 덤프의 자기-타겟 라인은 `CREATE DATABASE`/`USE agent_memory` 2개뿐(col0), sed strip 후
    잔존 `agent_memory` 는 전부 inert 주석. 스키마 수식 `agent_memory.table` 참조 0 → 모든 statement 가
    throwaway DB 로. PG: 덤프에 CREATE/DROP/ALTER DATABASE·\connect 없음 → psql -d $PG_TMP 로 격리.
    cleanup trap 이 CREATE 전 설정 + DROP IF EXISTS → orphan 없음. pipefail 로 실패 rc=1.
  - insight graceful: `import signal as _signal` 별칭이 지역변수 `signal`(2316) 충돌을 정확히 회피(ask.py
    와의 필수 차이), main-thread 등록, 잔여 time.sleep 은 daemon 백필 스레드뿐. 정확.
  - mysql-ddl-lint: self-test 4/4, set -e/while-read 안전. install-backup-cron: 멱등·무관항목 보존·--remove OK.
  - compose stop_grace_period 30s: 유효·정위치.
- 반영(should-fix/note):
  - [should] restore-rehearsal PG 복원에 `-v ON_ERROR_STOP=1` 추가 → 부분 복원 실패 탐지(안전성 아닌 탐지 갭). **반영**.
  - [note] mysql-ddl-lint 단일-라인 검사 → online 절은 ALTER 와 같은 라인에 두라는 주석 추가(스크립트+CONVENTIONS §13). **반영**.
  - [note] `--all` lineno-in-content 는 cosmetic(advisory 모드) — 미수정.
- Human Approval Needed: 아니오(코드 정합, PLAN-APPROVED). 배포는 사용자 "전체 배포" 승인.
