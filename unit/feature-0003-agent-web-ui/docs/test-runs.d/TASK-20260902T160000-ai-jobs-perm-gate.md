---
run_at: 2026-09-02T14:05:00+09:00
session: ai/claude/feature-0043-ai-jobs-perm-gate
scope: 프로필 'AI 작업' 탭 — 계정 권한으로 항목 추리기 (TASK-20260902T160000)
verdict: PRE-DEPLOY PASS (결함 재현) / POST-DEPLOY 아래 §2
---

# TASK-20260902T160000 — 'AI 작업' 탭 권한 게이트

- **Environment: Windows-browser** (`bin/win-browser.py` + PB-0008, Chrome/151.0.7922.170,
  relay @ `http://172.26.144.1:9223`, 대상 `https://localhost/`)
- 검증 브라우저는 이 세션이 띄운 인스턴스·격리 프로필(§16.6 (a)~(c)).

## 0. 대상 계정 — 제품 경로로 만들고 역순 정리 (§16.6 (d)~(f))

권한 축은 **비-admin 계정이 있어야** 관측된다. DB 를 직접 손대지 않고 제품 경로로 만들었다:
`POST /api/auth/signup` → `dqa_permgate_probe`(id 54, 기본 가입 역할 `pending`) →
관리 API 로 `operator`(일반 사용자, id 2) 부여. 실 사용자 계정은 **하나도 건드리지 않았다**.

역순 정리는 §3 에 기록한다.

## 1. PRE-DEPLOY — 결함 재현 (수정 전 라이브)

### 1-a. 역할별 게이트 권한 보유 실측 (모집단 = 전체 역할 8종)

`GET /api/admin/roles` 의 `permission_codes` 를 `perms` 선언 6코드와 대조:

| role | 총 권한 수 | 게이트 권한 보유 |
|---|---|---|
| `admin` | 121 | 6종 전부 |
| `usermanager` (관리자) | 88 | 6종 전부 |
| `pending` · `operator` · `dba` · `dev_server` · `dos_web` · `sales` | 28~42 | **0종** |

→ **8역할 중 6역할**이 `metadata_suggest`·`metadata_bulk`·`node_analysis` 를 열 수 없다.
그런데 셋 다 화면에는 보이고 있었다(= 죽은 설정칸).

### 1-b. `operator` 계정 화면 실측 — **6행 전부 노출 (결함)**

`dqa_permgate_probe`(operator) 로 로그인 → 프로필 drawer → 'AI 작업' 탭:

```
rowCount: 6
kinds: metadata_suggest, metadata_bulk, node_analysis,
       prompt_generate, insight_summary, cluster_label
```

스크린샷: `artifacts/permgate-20260902/before-operator-ai-jobs.png` — 「메타데이터
자동완성(단건)」·「메타데이터 자동완성(일괄)」·「그래프 AI 능동 분석」이 모델·추론강도
select 와 함께 판독 가능한 크기로 렌더된다. 이 계정은 그 셋 중 어느 엔드포인트도 열 수 없다.

### 1-c. `admin` 계정 화면 실측 — 6행 (정상, 대조군)

`bootstrap_admin`(admin) 의 `GET /api/profile/console-jobs` 응답도 6종. admin 은 6종 전부를
실제로 열 수 있으므로 이것이 기대값이다 — **수정 후에도 6행이어야** fail-closed 회귀가 아니다.

**PRE-DEPLOY 판정: 결함 재현 PASS.** 두 계정의 화면이 **동일**하다는 것이 결함의 형태다.

## 2. POST-DEPLOY — 수정 확인

> 배포 후 같은 경로를 다시 밟아 아래를 채운다. 순서 근거: §16.3 deploy-backed 완료 기준
> (cycle-finalize → main 기반 재배포 → 검증). 배포 전 브랜치 빌드를 공유 라이브 컨테이너에
> 올리는 것은 §13.2.9 상 다른 5개 활성 브랜치의 checkout 을 밀어내므로 택하지 않았다.

- [ ] `operator` 계정: **3행** (시스템 프롬프트 자동작성 · 테이블 인사이트 배치 · 클러스터 라벨링)
- [ ] `admin` 계정: **6행** (무회귀 — fail-closed 아님)
- [ ] `operator` 로 숨겨진 종류를 PUT 본문에 실어 보내도 저장되지 않는다 (fail-open 차단)
- [ ] `operator` 저장 왕복 후 admin 이 자기 설정을 그대로 유지한다 (비가시 항목 보존)
- [ ] 스크린샷 2매(operator 3행 · admin 6행) 첨부

## 3. 잔류물 (§16.6 (f))

- `dqa_permgate_probe`(id 54) — POST-DEPLOY 확인 후 **비활성화**로 정리한다(계정 삭제는
  감사 원장 참조를 끊으므로 이 저장소 관례대로 비활성 처리). 정리 결과는 §2 완료 시 기록.
- 검증 중 admin 세션을 한 번 로그아웃했다가 `win-browser.py session-login` 으로 복구했다
  (`bootstrap_admin` 재인증 확인). 다른 사용자 세션은 건드리지 않았다.
