---
run_at: 2026-09-02T14:05:00+09:00
session: ai/claude/feature-0043-ai-jobs-perm-gate
scope: 프로필 'AI 작업' 탭 — 계정 권한으로 항목 추리기 (TASK-20260902T160000)
verdict: PASS (PRE-DEPLOY 결함 재현 + POST-DEPLOY 전 항목 확인)
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

## 2. POST-DEPLOY — 수정 확인 (배포 `2a910ddb`)

- **Environment: Windows-browser** (동일 브리지·동일 격리 프로필). 배포 완료 후 수행 —
  §16.3 deploy-backed 완료 기준(cycle-finalize → main 기반 재배포 → 검증) 순서 준수.
- 배포 검증: 전 서비스 SHA `2a910ddb`(web 2 · ext-tool-mcp 2 · insight/ask/ops 3) ·
  `/healthz` **200** · `no upstreams available` **0건** · surge 잔존 **0** ·
  RestartCount **전 서비스 0** · Caddyfile 무변경(blip 0).

### 2-a. 권한별 노출 — **결함 해소 확정**

| 계정 | 역할 | 항목 수 | kinds |
|---|---|---|---|
| `bootstrap_admin` | admin | **6** (무회귀) | metadata_suggest · metadata_bulk · node_analysis · prompt_generate · insight_summary · cluster_label |
| `dqa_permgate_probe` | operator | **3** | prompt_generate · insight_summary · cluster_label |

화면 실측(operator): `rowCount: 3`, 이름 = 「시스템 프롬프트 자동작성 · 테이블 인사이트 배치 ·
클러스터 라벨링」. 스크린샷 `artifacts/permgate-20260902/after-operator-ai-jobs.png`
(BEFORE `before-operator-ai-jobs.png` 와 대조 — 메타데이터 2행·그래프 분석 1행이 사라졌다).

빈 상태 UI 는 이 계정에서 발동하지 않았다(`emptyMsg: false` · 저장 버튼 활성) — 항목이 3개
있으므로 **정상**이다. 0-항목 경로는 단위 테스트가 덮는다(라이브에서 0 을 만들려면 권한 요구가
없는 3종까지 없애야 하는데 그런 계정은 존재하지 않는다 — 그 사실 자체가 설계 의도다).

### 2-b. fail-open 차단 — 숨긴 종류는 저장되지 않는다

operator 로 `{"jobs": {"node_analysis": …, "cluster_label": …}}` PUT:

```
200 {"saved": true, "jobs": {"cluster_label": {"model":"claude:haiku","effort":"low"}}}
재조회 kinds = [prompt_generate, insight_summary, cluster_label]   ← node_analysis 없음
```

숨긴 종류는 **저장도 응답도 되지 않았다**. 가시 종류(`cluster_label`)만 반영됐다.

### 2-c. 입력 검증 — 깨진 본문과 「의도한 비우기」가 갈린다

| 본문 | 결과 |
|---|---|
| `{"nope": 1}` (jobs 키 부재) | **400** |
| `not-json` (파싱 실패) | **400** |
| `{"jobs": {}}` ([모두 기본값] 후 저장) | **200** + 비우기 |

### 2-d. ⭐ 비가시 항목 보존 — 권한 회수·재부여 왕복으로 증명

실제 시나리오(권한이 빠졌다가 돌아오는 경우)를 라이브로 재현했다:

1. admin 이 probe 에 `metadata.graph.analyze` **부여** → probe 목록 **4행**(node_analysis 등장)
2. probe 가 `node_analysis = claude:haiku / high` **저장** (200)
3. admin 이 권한 **회수** → probe 목록 **3행**(node_analysis 사라짐)
4. probe 가 화면 그대로 **저장**(`{"jobs": {}}` — 「모두 기본값」 상당) → 200
5. admin 이 권한 **재부여** → probe 목록 4행 · `node_analysis` = **`claude:haiku` / `high`**

→ **숨겨진 동안의 저장이 그 설정을 지우지 않았다.** 이 왕복이 없으면 4단계에서 조용히
증발했을 것이고, 사용자는 화면에 없던 값이라 알아채지 못한다.

### 2-e. admin 저장 경로 무회귀

admin 이 `metadata_bulk = claude:haiku / medium` 저장 → 200, 재조회 6행 유지·값 반영.

**POST-DEPLOY 판정: 전 항목 PASS.**

## 3. 잔류물 (§16.6 (f))

- `dqa_permgate_probe`(id 54) — **정리 완료**: 권한 override 제거 + `is_active: false`
  (응답으로 확인). 계정 행 자체는 남긴다 — 감사 원장(`WebAuditEvents`)이 이 id 를 참조하므로
  삭제하면 그 이력이 끊긴다(이 저장소 관례). 그 계정이 남긴 `ConsoleJobPrefs` 도 함께 남는다.
- 실 사용자 계정·데이터는 **하나도 건드리지 않았다**. 검증에 쓴 자원은 전부 이 세션이 제품
  경로로 만든 것이다(§16.6 (d)).
- 검증 중 admin 세션을 한 번 로그아웃했다가 `win-browser.py session-login` 으로 복구했다
  (`bootstrap_admin` 재인증 확인). 다른 사용자 세션은 건드리지 않았다.
