---
doc_type: AI_AGENT_POINTER
scope: project
status: active
lifecycle: reference
source_of_truth: false
sources: [AGENTS.md]
---

# Claude Code Notes

- 이 저장소의 공식 에이전트 운영 규칙은 `./AGENTS.md`를 따릅니다.
- 이 문서는 별도 정책 문서가 아니며, `AGENTS.md`와 `docs/*`를 참조하여 따릅니다.
- 본 저장소는 gstack 스킬(`~/.claude/skills/gstack/`) 과 공존하며, 스킬 호출 시에도 `AGENTS.md` / `CONTRIBUTING.md` / `docs/*` / `unit/feature-NNNN/docs/*` 의 governance 가 우선 적용됩니다.
- gstack 의 `/ship`, `/review`, `/qa`, `/investigate` 등 스킬을 사용할 때는 `CONTRIBUTING.md §5` 커밋 규칙과 `AGENTS.md §16.3` 명시 경로 스테이징 규칙을 따릅니다.
- 기능 진행 이력과 작업 기록은 gstack 의 `TODOS.md` / `CHANGELOG.md` 가 아닌 기존 `docs/STATUS.md` + `unit/feature-NNNN/docs/TASK.md` + `unit/feature-NNNN/docs/REPORT.md` 에 기록합니다. `TODOS.md` 는 feature 단위로 귀속되지 않은 repo-level 보류 아이템만 추적합니다.

## 공통 진입·재개 계약

- Claude와 Codex 모두 `AGENTS.md §10.1`의 목차→공통 필수 절→작업별 추가 절 순서로 읽는다.
  `.claude/commands/_template`는 외부 submodule이다. 그 entry Phase 2의 «본문 전체 누적»은
  소비자 정본 §10.1로 대체한다. Phase 6 Policy Prime Gate도 같은 읽기 집합에 적용한다.
  작업과 무관한 절의 `skipped-not-applicable`은 누락이 아니며, gate를 충족하려고 전체를 재독하지 않는다.
- 위임된 변경 작업은 `AGENTS.md §13.2.1`에 따라 격리 후 같은 세션에서 수행한다.
  직접 사용자 재개와 무인 wakeup을 구분한다(§22.12). 하네스별 지원 도구만 사용한다.
- 현재 요청·세션에서 승인한 범위를 재질문하지 않는다. 위험 승인과 commit/PR/배포 절차는
  각각 §12·7.1, §16.5.1을 따른다. 사용 가능한 대체 검증 채널은 작업자가 선택한다.

## Skill routing

gstack 스킬이 본 저장소 맥락과 충돌하지 않는 경우에 한해, 사용자의 요청이 다음 패턴과 맞으면 Skill 툴을 통해 해당 스킬을 호출한다. 판단이 모호하면 `AGENTS.md`에 따라 해당 작업에 필요한 도구를 선택해 진행한다. 도구 선택만을 위해 재승인을 요청하지 않는다.

**프로젝트 전용 `/_dqa` 지속 개선 파이프라인** (gstack 외, project-owned, `.claude/commands/_dqa/README.md`):
- 개선 발굴 (웹+상용/사내서비스+운영 리서치) → `/_dqa:improve_research` (사람 호출)
- 정합성 6축 review + 종속성 로드맵화 → `/_dqa:improve_listup` (AI 자율 호출)
- 로드맵 항목 구현 (worktree cycle, 스케줄 가능) → `/_dqa:improve_cycle` (사람 호출)
- 머지 작업↔문서(정책문서·wiki·릴리즈노트) drift 정합 (maintenance, 스케줄 가능) → `/_dqa:doc_sync` (사람 호출·예약, 파이프라인 단계 아님)
- 라이브 대화(그룹·1:1) 마찰 진단·수정·출하 (명시 신호 + 암묵 이탈 뉘앙스, maintenance, 스케줄 가능) → `/_dqa:conversation_audit` (사람 호출·예약, 파이프라인 단계 아님 / 위험 승인=§12·7.1, PR·deploy=§16.5.1)
- 기간별 개발 진척을 비전문가 포함 상부보고 발표자료로 재구성 (reporting, 스케줄 가능) → `/_dqa:report_deck "YYYY-MM-DD ~ YYYY-MM-DD"` (사람 호출·예약, 파이프라인 단계 아님 / 자기검증 통과 시 commit→push→PR 병합 필수 autoland · 배포·외부발송 안 함)
- 산출물: `docs/improvements/<initiative>/{RESEARCH,ROADMAP}.md` · 대화 마찰 원장 `docs/improvements/conversation-audit/FRICTION_LEDGER.md` · 발표자료 `docs/presentation/<범위>/<버전>/{deck.html,SCRIPT.md,EVIDENCE.md}` · fit-review subagent `improve-fit-reviewer`

- 제품 아이디어 / "이거 만들 가치가 있나" / 브레인스토밍 → `/office-hours`
- 전략 · scope · "더 크게 생각해 보자" · 방향 리뷰 → `/plan-ceo-review`
- 아키텍처 · "이 설계 말 되나" · 엔지니어링 리뷰 → `/plan-eng-review`
- 설계 리뷰(구현 전) → `/plan-design-review`
- 라이브 사이트 시각 감사 → `/design-review`
- 개발자 경험 리뷰(계획 단계) → `/plan-devex-review`
- 개발자 경험 실측 감사 → `/devex-review`
- 전체 리뷰 파이프라인 → `/autoplan`
- 버그 · 에러 · "왜 안 돼" · 근본 원인 분석 → `/investigate`
- 사이트/기능 QA · "이거 작동하나" → `/qa` (리포트만: `/qa-only`)
- PR / diff 사전 리뷰 → `/review`
- 코드 리뷰 · 2차 의견 → `/codex`
- ship/merge/PR 생성 → `/ship`
- merge + deploy + 검증 → `/land-and-deploy`
- 배포 구성 세팅 → `/setup-deploy`
- 배포 후 모니터링 → `/canary`
- 릴리스 후 문서 갱신 → `/document-release`
- 주간 retro → `/retro`
- 보안 감사 · OWASP · 위협 모델 → `/cso`
- 진행 상태 저장 / 복원 → `/context-save` / `/context-restore`
- 편집 범위 제한 → `/freeze` / `/unfreeze` / `/guard` / `/careful`
- PDF 문서 출력 → `/make-pdf`
- DQA 서비스 UI 검증 → **PB-0009** + 실제 DQA 클라이언트(WebView2/로컬 브리지). `AGENTS.md §15.4.1`을 따른다. 일반 Windows 브라우저는 보조 호환 검증이며 필수 완료 경로가 아니다.
- 보조 브라우저 호환 검증이 필요한 경우 → `bin/win-browser.py`/PB-0008 또는 가용 브라우저 도구. 실제 DQA 앱 검증으로 기록하지 않는다.
- WSL 내부 headless 브라우저 QA(보조) → `/connect-chrome` + `/browse`
- 인증 쿠키 임포트 → `/setup-browser-cookies`
- 성능 회귀 감지 → `/benchmark`
- 모델 벤치마크 → `/benchmark-models`
- 코드 품질 대시보드 → `/health`
- gstack 학습 히스토리 → `/learn`
- 질문 민감도 튜닝 → `/plan-tune`
- gstack 버전 업그레이드 → `/gstack-upgrade`

본 저장소는 feature 중심 구조이므로, 스킬이 `/ship` 이나 `/review` 로 PR 을 다룰 때는 `CONTRIBUTING.md` 의 브랜치/커밋 규칙(`<type>(<scope>): 요약 (#<issue>)` + `TASK-NNNN` 접미)을 우선 적용한다.

Codex 사용자는 `.codex/commands/` 및 `AGENTS.md` 의 Codex command compatibility
정책을 따른다. `.claude/commands/` 는 Claude 전용 entrypoint 로 유지한다.

<!-- agent-compatibility -->
Claude와 Codex는 같은 프로젝트를 함께 지원합니다. 상대 환경·세션 발견 및 인계는 `.agents/ENVIRONMENT.md`를 참조하세요. 현재 작업의 정본은 계속 `AGENTS.md`와 기능 문서입니다.
