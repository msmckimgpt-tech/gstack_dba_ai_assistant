---
doc_type: ANCHOR
feature_id: feature-0027-perf-latency-p0
created_at: 2026-07-28T01:00:00Z
status: active
edit_policy: mixed
source_of_truth: true
---

# ANCHOR: feature-0027-perf-latency-p0

## §1. 외부 관점 요약
- "왜 topic/용어 수집을 뒤로 미뤘나? 기능 제거 아닌가?" — 제거가 아니라 **시점 이동**이다.
  실행 내용·귀속(scope)·게이트는 동일하고, 사용자가 답변을 기다리는 구간에서만 빠진다.
- "버퍼풀 1G 는 왜 2G 가 아닌가?" — 컨테이너 3g 한도에서 실사용 ~1.1G + cgroup page cache
  귀속을 고려한 보수 1차값. 히트율 실측(perf-snapshot §8) 후 추가 상향을 판단한다.
- "immutable 1년 캐시가 배포 후 stale 을 만들지 않나?" — **`?v=` stamp 를 실은 요청에만**
  immutable 을 부여한다(쿼리 매처, §18.8 qa B1 정정). vendor(marked/purify)·로고 등 무버전
  참조가 실재하므로 경로 전체 immutable 은 보안 패치 고착 위험 — unstamped 자산은 종전
  ETag/304 동작을 유지한다.

## §2. 대안 분기
- **큐레이션을 백그라운드 스레드로 fire-and-forget** (속도 우선 페르소나): 더 빠르지만
  datasource ContextVar 가 스레드 경계에서 소실돼 용어/ENUM 이 'common' 스코프로 오염될
  위험 — 기각. terminal-후 동기 실행(같은 스레드·명시 캡처)이 격리 보존.
- **red-team 리뷰 제거/게이팅 상향** (지연 최소화 페르소나): -46s 즉효지만 revised 21/89
  실측 = 품질 기여 실재 — 자율 범위 밖, 사용자 결정 포인트로 표면화만.
- **web 커넥션 풀 동시 도입** (일괄 처리 페르소나): 효과 크지만 blast radius(웹 전 요청)가
  본 cycle 의 검증 예산을 초과 — 별도 slice 로 분리.

## §3. 가정된 사용 시나리오
DBA 가 질문을 던지면: 답변이 (평균) 25~35초 더 일찍 도착하고, 주제(topic)는 수 초 뒤
사이드바 폴링에서 갱신된다. 관리자는 배포 전후 `bin/perf-snapshot.sh` 두 장을 대조해
§2(run_avg)·§3c(터미널 후 큐레이션)·§8(버퍼풀 히트율) 수치로 개선을 정량 확인한다.
첫 화면 로드는 압축+캐시로 사내 무선에서도 체감 단축된다.

## §4. 외부 검증 로그
<!-- append-only. source: human:<name> 만 허용. -->
