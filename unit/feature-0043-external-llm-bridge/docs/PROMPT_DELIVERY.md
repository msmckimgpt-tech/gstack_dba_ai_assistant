# DQA 다계층 프롬프트 전달 감사

2026-09-08 · TASK-20260908-prompt-layer-delivery

| 순서 | 사용자 설정 | 실제 조회 |
|---|---|---|
| 1 | 서비스 전역 | WebSystemPrompts Scope=global, 세 ID NULL; 미설정은 SYSTEM_PROMPT |
| 2 | Product 개별 | Scope=product, 요청 ProductId |
| 3 | 역할 전역 | Scope=role, 요청 RoleId, ProductId NULL |
| 4 | 역할 제품별 | Scope=role, 요청 RoleId와 ProductId |
| 5 | 계정 개인 프로필 전역 | Scope=account, 인증 AccountId, ProductId NULL |
| 6 | 계정 개인 프로필 제품별 | Scope=account, 인증 AccountId와 ProductId |

개인 프로필 저장 API는 `routers/auth.py::me_put_system_prompt`이며 전역/제품 모두 같은 account scope다. 제품 미선택(auto)에는 1·3·5만 적용한다. 미설정 행은 누락 오류가 아니다. 여섯 계층 뒤에는 기존 폴더 지침·첨부·코드 강제 지침이 추가된다. 계층의 누적 순서와 모델 제공자의 system/developer/user 우선순위는 다른 축이다.

경로: DQA의 `/api/ask` → `conversations.py::_enqueue_web_bridge_task`에 제품·역할 저장 → `ai_tools.py::claim_request`가 인증 계정과 함께 `_bridge_system_prompt` 호출 → `agent_core.compose_system_prompt` → claim JSON `system_prompt` → 러너 `compose_prompt`/`handle_one` → `ask_local_ai`.

수정 전에는 전역/제품/역할/개인 지침의 DB 조회 예외가 빈 설정처럼 흡수됐고, 제품 표시명 조회 실패도 제품 지침을 건너뛰게 했다. 이제 bridge는 strict 조회를 사용하고 실패를 503으로 반환한다. 기존 사용자 대기 말풍선에 원인을 기록하며 5초 비동기 간격으로 재시도한다. 지연 후 정리는 최초 ClaimedClient를 NULL-safe로 대조해 새 러너의 점유를 건드리지 않는다. 기존 bootstrap/in-process의 non-strict 기본 동작은 보존한다.

| 러너 경로 | 전달 방식 | 검증 범위 |
|---|---|---|
| Claude, 지원·명령줄 길이 충족 | --append-system-prompt | 시스템 인자에 여섯 계층 1회, 본문 중복 없음 |
| Codex·custom·시스템 인자 미지원 | user 본문 앞 | 여섯 계층과 순서·전체 문자열 보존 |
| Windows 길이 초과 | 위 본문을 stdin으로 전달 | 6만 자 이상 한국어를 최종 프로세스 호출 경계까지 보존 |

`system_prompt` 필드명만으로 실제 시스템 역할을 보장하지 않는다. Codex 및 본문 폴백의 지침은 user 메시지에 실린다. 모델이 서로 충돌하는 지침을 어떻게 따르는지는 전달 테스트로 보장할 수 없다. 전체 지침을 provider 기본 system으로 교체하면 기존 도구·안전 규약이 바뀌므로 이 감사에서는 기존 채널 계약을 유지했다.

참고한 현재 공식 옵션: [Claude CLI](https://code.claude.com/docs/en/cli-reference)는 append-system-prompt-file을 제공하고, [Codex 설정](https://learn.chatgpt.com/docs/config-file/config-reference)은 developer_instructions를 제공한다. 설치된 CLI는 Claude 2.1.258/Codex 0.153.4. 파일 전달을 기본값으로 바꾸지는 않았다(Windows/WSL 경로 및 기존 사용자 지침을 보존하는 별도 실행 계약 검증 필요).

진단은 서버 `bridge.system_prompt`의 task/chars/sha256와 러너 `task.dispatch`의 system_chars/system_sha256/system_delivery를 비교한다. 프롬프트 원문·SQL 오류 문자열·토큰을 로그에 추가하지 않는다. 새 필드는 러너가 갱신된 뒤부터 기록된다. 정상 본문 폴백을 미전달로 기록하지 않는다.

실행 증거와 미검증 경계는 [Run](test-runs.d/TASK-20260908-prompt-layer-delivery.md)에 있다. 라이브 사용자 지침을 바꾸거나 외부 LLM 질의를 새로 실행하지 않았다. DQA 실제 화면 장애/회복 시나리오는 현재 CDP 미개방으로 NOT-RUN이다.
