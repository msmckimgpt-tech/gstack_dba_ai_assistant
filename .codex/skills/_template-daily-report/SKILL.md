---
name: _template-daily-report
description: "특정 날짜(기본 오늘)에 현재 소비자 프로젝트의 git 저장소 로그에서 진행한 작업을 수집해 TASK 단위로 묶고 시간대(10–13 / 13–16 / 16–19)로 나눠 보고서용 한 줄 목록으로 출력 (작업·산출물 중심 — 검증·증적 등 내부 진행 절차는 제외; 보고일 경계 19:00 — 전날 야간분은 익일 10–13 의 '전날(19:00 이후)' 하위 섹션으로 이월; 시간대별 섹션엔 제품 기능 개발만, 도구·스킬·템플릿·문서·인프라 등 기능 개발 외 항목은 최하단 별첨으로 분리; 시간대 내부에서 유사/범위별 TASK 가 몰리면 카테고리 하위헤더로 묶어 가시성 확보)"
generated_by: codex-environment-install
managed_body_sha256: 86cd47f6973ff3d8bd70bdb8c56eb9c39d88ae977006962dacaa96a725274ca5
---

Read `.codex/CONTEXT.md` from the current policy root, then follow `.codex/commands/_template/daily-report.md`. Resolve the policy root from `repo/AGENTS.md` when launched in the wrapper, otherwise from `AGENTS.md`. Use the current user arguments as `$ARGUMENTS`.
