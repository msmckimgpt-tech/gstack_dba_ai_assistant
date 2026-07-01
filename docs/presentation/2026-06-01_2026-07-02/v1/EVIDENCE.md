---
doc_type: PRESENTATION_EVIDENCE
range: 2026-06-01 ~ 2026-07-02
version: v1
created_at: 2026-07-02
companion: ./deck.html
---

# 근거·확인필요 원장 — 2026-06-01 ~ 2026-07-02 v1

> 발표 본문(deck.html)·스크립트(SCRIPT.md)의 모든 주장은 여기서 추적된다. 확인필요(§2) 항목은 발표 시
> "완료/개선"으로 단정하지 말고 "진행 중 / 예정 / 확인 필요"로 정직하게 표현한다.
> 수집 채널: ①git(main 반영분, baseline 44d42997@2026-05-29) ②정책·릴리즈노트 ③unit feature 기록 ④개발 세션 transcript(보조). ⑤이전 기간 발표자료 = 기간 스코프 report_deck 산출물 없음(제품 소개용 index.html/practitioner.html 만 존재 — 성격 다름).
> 커밋 해시는 추적용 내부 참고이며 발표 본문 비노출. 민감값(계정·비밀번호·토큰·접속좌표)은 원장에도 비노출.

## 1. 확인된 주장 (근거 있음)

### E-001 · 이 기간 main 반영 작업 = 16개 논리 단위 (개발·머지 완료)
- **kind**: git
- **ref**: `git log origin/main --since=2026-06-01 --until=2026-07-02` — 1,084 커밋, TASK-0128~0307 + TASK-20260619~. feature-0002/0003/0006/0009/0010/0012/0014/0015/0016.
- **status**: 확인 (단, "머지 완료" = 개발 완료. "라이브 배포·효과"는 항목별로 §2 참조.)
- **note**: baseline 2026-05-29(44d42997) 대비 전량 신규. "완료"는 main 반영 기준이며 배포 완료와 구분.

### E-002 · 멀티 데이터소스(MySQL+MSSQL) 확대 + 데이터소스 레지스트리(암호화) + DB 단위 접근제어
- **kind**: git / unit-doc
- **ref**: feature-0002/0003, TASK-0187~0250; 커밋 26e2117a(멀티 datasource P1)·a203a3e0(레지스트리 backend). 연결 상태 3단계(정상/불안정/끊김), 자격증명 봉투 암호화, 제품→데이터소스→DB allowlist.
- **status**: 확인 (머지)
- **note**: 자격증명 값은 비노출(암호화 저장 사실만). MSSQL dialect·4-part 함수·시스템DB 가드 포함.

### E-003 · NL→SQL 정확도 기반: 평가 harness + 샘플쿼리 flywheel + 용어/ENUM 사전 + 하이브리드 검색
- **kind**: git / unit-doc / policy-doc
- **ref**: feature-0002/0010, TASK-20260619T014034·20260623T191241; 커밋 cedd1b7d(평가 harness). ROADMAP ITEM-02/03, Self-Reflection 루프, 벡터+키워드 score fusion, 용어사전 자율등록(ITEM-11)·mig 0023. DECISIONS ADR-0021/ADR-20260629T101500.
- **status**: 확인 (머지)
- **note**: **정확도 "향상 수치"는 미제시 → U-006.** 여기서 확인되는 것은 "정확도 향상을 위한 수단(평가·환류·사전)이 도입됨"까지.

### E-004 · 보안 6대 강화 (2단계 인증·OAuth 기초·프롬프트 주입 방어·감사 해시체인·로그인 시도 제한·사용량 한도)
- **kind**: git / unit-doc
- **ref**: feature-0003/0006, TASK-0296~0300; 커밋 a9effd6a. TOTP(self-service+관리자 해제), Google OAuth 기초, datamarking+명령계층 주입 방어, 감사 해시체인·검증·앵커, 계정잠금·IP throttle, 역할/계정 quota(quota.read/manage).
- **status**: 확인 (머지)
- **note**: 각 기능의 **재발방지 "효과"·라이브 적용은 확인필요(U-005)**. 여기서 확인은 "기능이 개발·머지됨".

### E-005 · 내부 HTTPS (자체 Root CA) + Caddy :443 정식 진입 전환
- **kind**: git / unit-doc
- **ref**: feature-0006, TASK-0296~0299; 커밋 716dd07a(caddy 502 해소). 사내 Root CA 신뢰로 self-signed 경고 제거, 테스터 원클릭 설치 번들·/trust 서빙.
- **status**: 확인 (머지)

### E-006 · 그룹 대화 협업 (멤버십·@멘션·열람≠발화 게이트·실시간 UX)
- **kind**: git / unit-doc / dev-transcript(보조)
- **ref**: feature-0009, TASK-20260619T023140; 커밋 b33e9ad9. S1~S4 멤버십/멘션 파서/발화 게이트, 적응형 폴링·피멘션 알림, alembic 0012.
- **status**: 확인 (머지)
- **note**: "열람≠발화" granular RBAC 설계 과정은 transcript(86454e24)에도 근거 — 보조.

### E-007 · 답변 리뷰(diff 블록) + 첨부 버전 관리
- **kind**: git / unit-doc
- **ref**: feature-0003, TASK-0256~0287; 커밋 bef6eb0a. assistant 답변 markdown diff(줄번호 old|new, 복사 시 마커 제외), 첨부 수정→새 버전 materialize·버전 배지.
- **status**: 확인 (머지)

### E-008 · 권한 편집기 progressive disclosure + RBAC 결함 수정
- **kind**: git / unit-doc
- **ref**: feature-0003, TASK-0257~0303; 커밋 a8a18982. 게이트 미충족 시 세부 권한 숨김, 계정·역할 2축 분리, self-scope 편집 차단, 권한 회수 미반영 4종 수정, 감사 .own actor-only.
- **status**: 확인 (머지)

### E-009 · LLM 사용량 대시보드 + AI 운영 현황 패널 (관리 콘솔) — 배포됨
- **kind**: git / unit-doc / release-note
- **ref**: feature-0003; LLM 사용량 차트화(TASK-0165·0176~0184, console.usage.read). AI 운영 패널 PR#526(2026-07-02, c5e259db, console.aiops.read, PG latency_ms 컬럼). 회귀 스위트 16+20+28 통과(unit REPORT).
- **status**: 확인 (머지 + 배포 2026-07-02)
- **note**: 계측 범위 정직 표기 — chat 4경로 계측 가능, embedding/provider probe는 구조적 불가(read-time cost 계산 유지).

### E-010 · 메타데이터 지식그래프 (PostgreSQL + Apache AGE) — Phase 0~5 라이브 cutover
- **kind**: unit-doc / release-note / git
- **ref**: feature-0016 REPORT Phase 0~5; PR#477(2026-06-30, cutover), rag_objects 8,122 테이블 투영 + 추론 엣지, graph WAL 복제, alembic 0025~0026. **이웃 조회 60x 개선(9454→151ms depth1 / 18564→300ms depth2)** — 원인 vertex properties 인덱스 부재→GIN/btree 추가, unit REPORT 실측.
- **status**: 확인 (배포 2026-06-30 + AGE 60x는 unit 실측)
- **note**: **그래프 UI WebGL FPS(10→60) 수치는 U-003(확인필요).** 60x는 DB 이웃조회(서버측 실측)이고 FPS는 브라우저 렌더(headless 재현 불가)로 구분.

### E-011 · 무중단 배포 (Caddy 2-replica web-a/web-b 롤링) — 라이브 cutover + zero-502 실증
- **kind**: unit-doc / release-note / git / dev-transcript(보조)
- **ref**: feature-0014 REPORT/RUNBOOK; PR#475(2026-06-30, d980e24), Caddy LB+active health+retry, `bin/deploy-web.sh`(flock·migrate-lint 게이트·SSE pre-drain). **롤링 부하 104건 200 OK, max 0.27s(zero 502)** — RELEASE_NOTES 라이브 실증. `:18080` 직접문 폐기→Caddy :443 단일.
- **status**: 확인 (배포 2026-06-30 + zero-502 부하 실증)
- **note**: **자동롤백·SSE pre-drain·무인 scoped-sudoers 경로는 U-004(확인필요).**

### E-012 · 웹 라우터 모듈화 (148 route → 21 도메인 APIRouter, app.py 37% 축소) — 배포됨
- **kind**: unit-doc / release-note / git
- **ref**: feature-0012 REPORT Phase 0~Final; PR#506/513/516(2026-07-01). app.py 29,111→18,917줄(-10,194), DI seam 선행, byte-동치 검증, route-parity 골든. 라이브 bare-name 500 3건 즉시 수정(ruff F821 전수).
- **status**: 확인 (배포 2026-07-01, 프로덕션 응답 byte-동치 + route-parity)
- **note**: route-parity 수치가 채널마다 192/194로 상이(경미) → U-008. **브라우저 로그인 QA 미수행 → U-002.** batch4 잔여 재배포 검증 후속(경미).

### E-013 · 질문 처리 일꾼(out-of-process) + 웹 비동기화
- **kind**: git / unit-doc
- **ref**: TASK-0148·0169; 커밋 1320bcac. ask_jobs 큐 + ask-worker 아웃프로세스, 웹 비동기 핸들러 30건 오프로드(이벤트 루프 블로킹 해소), readiness gate(tz 버그 수정).
- **status**: 확인 (머지)
- **note**: "웹 재배포해도 진행 중 작업 생존" 서사의 코드 근거. 라이브 효과는 무중단 배포(E-011)와 함께.

### E-014 · PostgreSQL near-zero 재시작 (pgbouncer PAUSE/RESUME) — 라이브 무에러
- **kind**: release-note / dev-transcript(보조) / git
- **ref**: feature-0016-zd-pg-pause-caddy; RELEASE_NOTES 06-30. **PG 재시작 중 RW OK=134 / ERR=0**, RESUME 후 paused DB=0, MAX_QUERY_WAIT 14s(큐 지연만). 커밋 73c424d0.
- **status**: 확인 (라이브 무에러 실증)

### E-015 · 백업 갭 정비 + 복원 리허설
- **kind**: release-note / unit-doc
- **ref**: feature-0015; RELEASE_NOTES 06-30. 복원 PASS(agent_kb 250M / agent_memory 32M, PG 34·MySQL 29 테이블), orphan rehearsal DB 0. `bin/backup.sh`·`restore-rehearsal.sh`·`install-backup-cron.sh`.
- **status**: 확인 (복원 리허설 PASS = 테스트 완료)
- **note**: **정기 cron 라이브 설치는 U-001(배포 대기).** 리허설 PASS ≠ 운영 설치.

---

## 2. 확인 필요 (근거 부족·불일치·단정 위험)

### U-001 · feature-0015 무중단 보조(graceful 종료·MySQL DDL 온라인 게이트·백업 cron)의 라이브 배포
- **왜 확인필요**: 배포 미확인 — unit REPORT 상 "코드 완성 + 정적 검증 PASS, 라이브 검증 미수행(배포 시)". 배포 대기(⏳).
- **가진 것 / 없는 것**: 코드·정적검증 있음 / insight-worker graceful recreate 관찰·복원 cron 라이브 설치 없음.
- **확인 방법**: 운영자 배포 후 graceful 로그·cron 설치 확인.

### U-002 · PB-0008 실 Windows 브라우저 시각검증 (그래프 뷰·메타 list-detail·그룹 UI·AI 운영 패널·라우터 로그인 QA)
- **왜 확인필요**: 화면자료 미확보 + 일부 "배포 후 예정". headless 로 실 화면·인터랙션 재현 불가.
- **가진 것 / 없는 것**: 일부 라이브 스크린샷 기록(그래프 노드 이웃 등) 있음 / 전체 시각 QA·로그인 게이트 실호출 없음.
- **확인 방법**: `bin/win-browser.py`+PB-0008 로 실 화면 검증(발표 전 권장).

### U-003 · 그래프 뷰 WebGL 렌더 FPS 개선 수치 (canvas-2D "10fps → 60fps" 주장)
- **왜 확인필요**: 수치 미측정(실측) — 설계·transcript 근거이나 headless 재현 불가. (DB 이웃조회 60x[E-010]와 별개 — 이건 브라우저 렌더.)
- **가진 것 / 없는 것**: WebGL 전환·설계 근거 있음 / 실 FPS 계측 결과 없음.
- **확인 방법**: 실 브라우저 성능 프로파일 계측.

### U-004 · 무중단 배포 자동롤백 + SSE pre-drain + 무인 scoped-sudoers 경로
- **왜 확인필요**: 미검증 — 설계·스크립트는 있으나 라이브 자동롤백/SSE 배수 실측 미수행.
- **확인 방법**: 배포 리허설에서 실패 주입 → 자동롤백·SSE 무손실 관찰.

### U-005 · 6월 전반 기능(멀티 데이터소스·NL→SQL 수단·보안 6대·그룹대화·답변diff·권한편집기)의 라이브 배포 완료·운영 효과
- **왜 확인필요**: git 머지=확인(E-002~E-008)이나, 이들 초기 기능의 **라이브 배포 완료 시점·운영 효과**는 이번 수집 범위의 RELEASE_NOTES 에서 개별 확인되지 않음(후반부 0012/0014/0016/0003 만 배포 확인). 보수적으로 "머지=완료, 배포/효과=확인필요".
- **가진 것 / 없는 것**: 머지·테스트 근거 있음 / 항목별 배포 timestamp·운영 지표 없음.
- **확인 방법**: STATUS.md·배포 로그·운영 지표로 항목별 배포·효과 확인.

### U-006 · NL→SQL 정확도 "향상" 수치
- **왜 확인필요**: 수치 미측정 — 평가 harness·flywheel·사전은 도입(E-003)됐으나 "정확도 X%→Y%" 개선 수치는 문서에 없음.
- **확인 방법**: 평가 harness 결과(before/after)로 정량 확인.

### U-007 · transcript 단독 의사결정 (그래프 rebase 판단·라우터 DI 전략·그룹 RBAC granular 설계)
- **왜 확인필요**: 개발 세션 transcript 에만 상세 기록(a5c50e43·86454e24). git/문서로 결과(코드·PR)는 확인되나 "의사결정 과정"은 보조 근거.
- **확인 방법**: 발표 시 결과(코드·PR)만 사실로, 과정 서사는 "개발 기록 기준"으로 표현.

### U-008 · 문서 간 경미한 불일치
- **왜 확인필요**: (a) route-parity 골든 수치가 채널마다 192/194 상이(경미, 시점차 추정). (b) feature-0016 번호 충돌 — `metadata-graph` + `zd-pg-pause-caddy` 2 슬라이스가 0016 공유(문서에 명시, 사람 결정 보류). (c) "1,084 커밋"은 큰 수 — 다수가 자잘한 후속·머지 커밋으로 16 단위에 흡수됨(단위 수와 커밋 수는 다른 축).
- **확인 방법**: 발표 전 최신 STATUS·route-parity 재확인.

---

## 3. 특별 주의 항목 (단정 절대 금지 — 위 §1/§2 분류 요약)
- **실제 배포 여부**: 확인=0009 관리패널(07-02)·0012(07-01)·0014·0016·PG-pause(06-30). 확인필요=0015(U-001), 6월 전반 기능(U-005).
- **테스트 결과**: 확인=make test 1313 pass·route-parity·백업 복원 PASS·회귀 스위트. 확인필요=PB-0008 실 브라우저(U-002)·로그인 QA.
- **성능 개선 수치**: 확인=AGE 이웃조회 60x(서버 실측)·무중단 부하 zero-502 104건. 확인필요=그래프 FPS 10→60(U-003)·NL→SQL 정확도(U-006).
- **장애 재발방지 효과**: 감사 해시체인·로그인 제한·주입 방어는 개발됨(E-004), 실효(재발 방지 입증)는 확인필요(U-005).
- **화면 변경 전후 자료**: 실측 스크린샷 대부분 미확보 → deck 은 비교표·구조도·흐름도 재구성("실측 화면 미확보(도식 재구성)" 배지).
- **문서-코드 불일치**: U-008(route-parity 192/194·feature-0016 번호 충돌).
