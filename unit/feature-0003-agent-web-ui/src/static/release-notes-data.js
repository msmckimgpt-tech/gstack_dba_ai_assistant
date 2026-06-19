/*
 * release-notes-data.js — 릴리즈 노트 콘텐츠 (정적 큐레이션 · 읽기 전용)
 *
 * 이 파일은 "데이터"입니다. 새 업데이트가 배포되면 맨 위(releases[0])에 새 일자
 * 블록을 추가하세요. 렌더링/접기/탐색 로직은 release-notes.js 가 담당하므로 이
 * 파일은 손대지 않아도 됩니다.
 *
 * 작성 원칙 (사용자 요청):
 *   - 일반 사용자가 바로 이해할 수 있는 단순하고 명시적인 문장으로 풉니다.
 *   - 화면에 그대로 나타나는 변화는 본문에 그대로 적어도 됩니다.
 *   - 내부 동작(로직·네트워크·보안 처리 방법 등)은 노출하지 않고 "안정성/보안
 *     개선" 수준으로만 간략히 적습니다.
 *
 * 항목 스키마:
 *   { type: "new" | "improved" | "fixed",   // 새 기능 / 개선 / 수정
 *     area: "work" | "admin" | "common",     // 작업 화면 / 관리 콘솔 / 공통
 *     title: "한 줄 요약",
 *     detail: "선택 — 한두 문장 부연" }
 */
window.RELEASE_NOTES = {
  generated: "2026-06-19",
  releases: [
    {
      date: "2026-06-19",
      summary: "AI 사용이 일시 제한될 때 화면 안내",
      items: [
        {
          type: "new",
          area: "work",
          title: "AI 사용이 일시적으로 제한될 때 화면에서 바로 확인",
          detail: "외부 요인으로 AI 응답 생성이 일시적으로 제한되면, 입력창 위 안내와 상태 표시 · 대화 속 안내로 제한 사실과 사유를 바로 확인할 수 있습니다. 제한이 풀리면 안내는 자동으로 사라집니다.",
        },
      ],
    },
    {
      date: "2026-06-18",
      summary: "데이터소스 · 제품 선택 화면 사용성 개선",
      items: [
        {
          type: "new",
          area: "work",
          title: "제품 선택 드롭다운에서 이름으로 바로 검색",
          detail: "제품이 많아도 이름 일부만 입력하면 빠르게 찾아 선택할 수 있습니다.",
        },
        {
          type: "improved",
          area: "work",
          title: "대화 목록 첫 진입 시 가장 최근 날짜만 펼쳐 표시",
          detail: "좌측 대화 목록을 처음 열면 최근 날짜 그룹만 펼쳐지고 나머지는 접혀 있어 한눈에 보기 편합니다.",
        },
        {
          type: "new",
          area: "admin",
          title: "데이터베이스 추가 시 검색 + 여러 항목 한 번에 선택",
          detail: "‘+ 데이터베이스 추가’ 목록에서 이름으로 거르고, 여러 개를 한꺼번에 선택할 수 있습니다.",
        },
        {
          type: "new",
          area: "admin",
          title: "데이터소스 엔진 선택을 아이콘 드롭다운으로",
          detail: "새 데이터소스를 추가할 때 엔진(MySQL / SQL Server)을 아이콘과 함께 고를 수 있습니다.",
        },
        {
          type: "new",
          area: "admin",
          title: "데이터소스 목록에 엔진 종류 아이콘 표시",
        },
        {
          type: "new",
          area: "admin",
          title: "제품의 접근 가능 DB 목록 접기 + 기본 접힘",
          detail: "DB가 많은 제품도 목록을 접어 둘 수 있어 화면이 깔끔해집니다.",
        },
        {
          type: "new",
          area: "admin",
          title: "역할 · 제품 목록에 활성 / 비활성 필터",
        },
      ],
    },
    {
      date: "2026-06-17",
      summary: "권한 보호 강화 · 제품 일괄 관리 수정",
      items: [
        {
          type: "fixed",
          area: "admin",
          title: "제품을 한꺼번에 삭제해도 적용되지 않던 문제 수정",
          detail: "여러 제품을 선택해 일괄 삭제할 때 실제로 반영되도록 고치고, 변경 목록이 즉시 갱신되도록 했습니다.",
        },
        {
          type: "improved",
          area: "admin",
          title: "본인이 갖지 않은 권한은 다른 계정 · 역할에 부여 불가",
          detail: "권한을 편집할 때 자신이 보유하지 않은 권한은 보이지 않으며 부여할 수 없습니다. (보안 강화)",
        },
        {
          type: "new",
          area: "work",
          title: "작업 화면 제품 목록을 접근 권한에 맞춰 표시",
          detail: "역할에 허용된 제품만 제품 선택 목록에 나타납니다.",
        },
        {
          type: "new",
          area: "admin",
          title: "계정 · 역할에도 프로필 아이콘(이미지) 지정",
          detail: "사용자 프로필처럼 계정과 역할에도 아이콘 이미지를 올리거나 바꿀 수 있습니다.",
        },
        {
          type: "fixed",
          area: "admin",
          title: "제품 목록 항목 글꼴 크기 정합",
        },
        {
          type: "improved",
          area: "common",
          title: "사내 접속 보안(HTTPS) 및 데이터베이스 연결 안정성 개선",
          detail: "내부 동작 개선이라 화면 변화는 크지 않습니다.",
        },
      ],
    },
    {
      date: "2026-06-16",
      summary: "수행 시간 정직 표시 · 권한 회수 정확화 · 첨부 개선",
      items: [
        {
          type: "improved",
          area: "work",
          title: "대화 수행 시간을 실제 걸린 시간으로 정직하게 표시",
          detail: "대기 · 준비 · 추론 단계까지 포함한 실제 소요 시간을 보여주고, 진행 중 동작을 더 투명하게 표시합니다.",
        },
        {
          type: "fixed",
          area: "admin",
          title: "권한을 회수해도 일부 화면 · 데이터에 접근되던 문제 수정",
          detail: "권한을 회수하면 관련 화면과 데이터 접근이 즉시 함께 차단됩니다.",
        },
        {
          type: "fixed",
          area: "admin",
          title: "계정 개수 배지를 활성 계정만 집계",
        },
        {
          type: "new",
          area: "work",
          title: "첨부 파일 수정본을 변경점(diff)만 전달",
          detail: "AI가 첨부 파일을 고쳐 줄 때 전체 본문 대신 바뀐 부분만, 어떤 파일인지 명시해 전달합니다.",
        },
        {
          type: "new",
          area: "work",
          title: "첨부 파일 버전 현황 표시",
          detail: "첨부 목록의 버전 배지와 말풍선의 첨부 칩으로 어떤 버전인지 확인할 수 있습니다.",
        },
        {
          type: "fixed",
          area: "work",
          title: "말풍선의 첨부 파일 다운로드 실패 수정",
        },
        {
          type: "new",
          area: "work",
          title: "좌측 사이드바 너비를 드래그로 조절",
          detail: "대화 목록 사이드바 경계를 끌어 폭을 조절할 수 있고, 더블클릭하면 기본값으로 돌아갑니다.",
        },
        {
          type: "improved",
          area: "work",
          title: "데이터소스 연결 상태를 3단계(정상 / 불안정 / 끊김)로 표시",
        },
      ],
    },
    {
      date: "2026-06-15",
      summary: "첨부 버전 관리 · 답변 변경점(diff) · 대화 보관 · 권한 편집기 개편",
      items: [
        {
          type: "new",
          area: "work",
          title: "첨부 파일을 수정하면 새 버전으로 저장 · 버전 관리",
        },
        {
          type: "new",
          area: "work",
          title: "AI 답변의 변경 제안을 변경점(diff) 블록으로 표시",
          detail: "리뷰 시 무엇이 바뀌었는지 줄번호와 함께 색으로 구분해 보여 주고, 복사 시 줄번호 · 마커는 제외됩니다.",
        },
        {
          type: "new",
          area: "admin",
          title: "대화 삭제를 ‘보관(아카이브)’으로 전환 + 관리자 조회",
          detail: "삭제한 대화를 보관 상태로 두어 관리자가 조회하거나 맥락으로 참조할 수 있습니다.",
        },
        {
          type: "new",
          area: "admin",
          title: "관리 콘솔 ‘보관 대화’ 탭 추가",
        },
        {
          type: "improved",
          area: "admin",
          title: "계정 · 역할 권한 편집기를 단계 공개 트리로 개편",
          detail: "권한을 한 화면에 펼쳐 놓는 대신 관련 권한을 단계적으로 펼쳐 보는 구조로 정리해 가독성을 높였습니다.",
        },
        {
          type: "new",
          area: "common",
          title: "사용자 · 제품 · 계정 · 역할 프로필 아이콘(이미지 + 기본 아이콘)",
        },
        {
          type: "new",
          area: "work",
          title: "LLM 사용량 차트에 마우스 올리면 비용 표시 · 클릭 시 기여 대화 목록",
        },
        {
          type: "new",
          area: "work",
          title: "제품 선택 드롭다운에 데이터소스 연결 상태 배지",
        },
        {
          type: "fixed",
          area: "work",
          title: "결과 표 ◀ ▶ 전환 시 화면이 튀던 문제 수정",
        },
        {
          type: "fixed",
          area: "work",
          title: "프로필 첫 진입 시 ‘제품 범위’가 비어 있던 문제 수정",
        },
        {
          type: "new",
          area: "work",
          title: "첨부 파일 목록 사이드 패널 너비 조절",
        },
      ],
    },
    {
      date: "2026-06-12",
      summary: "데이터소스 관리 표준화 · 프롬프트 실시간 자동 작성 · 요청 취소 즉시 처리",
      items: [
        {
          type: "new",
          area: "admin",
          title: "데이터소스 관리 화면 표준화(목록–상세) + 수정 · 삭제",
        },
        {
          type: "new",
          area: "work",
          title: "제품 프롬프트 ‘자동 작성’을 실시간 글자 스트리밍으로",
          detail: "자동 작성 결과가 한 번에 나타나지 않고 작성되는 대로 실시간으로 표시됩니다.",
        },
        {
          type: "new",
          area: "work",
          title: "입력창에서 Shift + Enter 로 줄바꿈",
        },
        {
          type: "fixed",
          area: "work",
          title: "요청 취소를 즉시 처리 + 취소 직후 바로 재요청 가능",
        },
        {
          type: "new",
          area: "admin",
          title: "‘+ 데이터소스 추가’ 목록에 연결 상태 표시 + 정렬 정리",
        },
        {
          type: "new",
          area: "admin",
          title: "제품별 분석(인사이트) 완료율 표시",
        },
        {
          type: "fixed",
          area: "work",
          title: "새 대화 첫 메시지의 작업 단계 진행 상황 실시간 표시",
        },
      ],
    },
    {
      date: "2026-06-11",
      summary: "여러 데이터베이스 연결 · 관리 콘솔 대시보드 개편",
      items: [
        {
          type: "new",
          area: "admin",
          title: "한 제품이 여러 데이터베이스(MySQL · SQL Server)를 참조",
          detail: "제품 하나에 여러 데이터소스를 연결해 함께 조회할 수 있습니다.",
        },
        {
          type: "new",
          area: "admin",
          title: "데이터소스(접속 정보) 관리 화면 추가",
        },
        {
          type: "improved",
          area: "admin",
          title: "관리 콘솔 대시보드를 보기 쉬운 위젯 그리드로 재구성",
          detail: "주요 지표를 카드 형태로 모아 보고, 표시 항목과 순서를 사용자별로 바꿀 수 있습니다.",
        },
        {
          type: "improved",
          area: "work",
          title: "제품 프롬프트 자동 작성 품질 강화",
        },
      ],
    },
    {
      date: "2026-06-10",
      summary: "LLM 사용량 대시보드 · 실행 단계 근거 표시",
      items: [
        {
          type: "new",
          area: "work",
          title: "LLM 사용량 화면을 차트 대시보드로 개편",
          detail: "토큰 사용량과 추정 비용을 일별 · 모델별 차트로 보여 줍니다.",
        },
        {
          type: "new",
          area: "work",
          title: "실행 단계마다 ‘왜 이 동작을 했는지’ 근거 표시",
        },
        {
          type: "new",
          area: "work",
          title: "실행 단계 사이드 패널에 결과 표 표시 + 패널 너비 조절",
        },
        {
          type: "new",
          area: "work",
          title: "말풍선 시각 옆에 응답 소요 시간 표시",
        },
        {
          type: "fixed",
          area: "work",
          title: "날짜 기준 캘린더로 대화 구간 이동 복구",
        },
        {
          type: "improved",
          area: "work",
          title: "공유한 대화 페이지의 가독성 디자인 개선",
        },
      ],
    },
    {
      date: "2026-06-09",
      summary: "대화 분기 복원 · 무거운 쿼리 자가 규제 · 결과 표 우선 표시",
      items: [
        {
          type: "new",
          area: "work",
          title: "대화 분기(이어 만들기) 시 이전 문맥과 첨부 복원",
        },
        {
          type: "new",
          area: "work",
          title: "무거운 쿼리를 미리 점검해 스스로 부담을 조절",
          detail: "실행 부하가 큰 조회는 사전에 점검하여 과도한 부하를 방지합니다.",
        },
        {
          type: "new",
          area: "work",
          title: "쿼리 결과 표를 먼저 보여 주고 SQL은 토글로",
        },
        {
          type: "improved",
          area: "work",
          title: "장시간 · 대용량 요청 처리 안정성 개선",
        },
      ],
    },
    {
      date: "2026-06-08",
      summary: "요청 중단 버튼 · 전체 행 미리보기 · 숨은 기능 진입점 정리",
      items: [
        {
          type: "new",
          area: "work",
          title: "요청 처리 중에는 전송 버튼이 ‘중단’ 버튼으로 바뀜",
        },
        {
          type: "new",
          area: "work",
          title: "‘전체 N행 미리보기’를 화면 안에서 바로 표로 불러오기",
        },
        {
          type: "new",
          area: "work",
          title: "메뉴에서 찾기 어렵던 기능(공유 관리 등)에 진입점 추가",
        },
        {
          type: "fixed",
          area: "work",
          title: "진행 중인 말풍선이 다른 대화로 새어 나오던 문제 수정",
        },
      ],
    },
    {
      date: "2026-06-04",
      summary: "DB 조회 정확도 개선 · 화면 UX 정리",
      items: [
        {
          type: "improved",
          area: "work",
          title: "DB 조회 정확도 개선 · 잘못된 답변 감소",
        },
        {
          type: "improved",
          area: "work",
          title: "화면 전환 깜빡임 · 스크롤 등 잔잔한 사용성 개선",
        },
        {
          type: "improved",
          area: "common",
          title: "데이터 저장 및 시스템 안정성 개선",
          detail: "내부 동작 개선이라 화면 변화는 없습니다.",
        },
      ],
    },
    {
      date: "이전",
      label: "그 이전 주요 업데이트",
      summary: "관리 콘솔 · 권한 · 대화 공유 · 첨부 등 기반 기능",
      items: [
        {
          type: "new",
          area: "admin",
          title: "관리 콘솔 — 계정 · 역할 · 권한 관리",
          detail: "계정과 역할을 만들고 세부 권한을 부여 · 회수할 수 있습니다.",
        },
        {
          type: "new",
          area: "admin",
          title: "감사 로그 — 주요 변경 이력 조회",
        },
        {
          type: "new",
          area: "admin",
          title: "제품 · 전역 프롬프트 관리",
        },
        {
          type: "new",
          area: "work",
          title: "대화 공유 — 링크로 대화 결과 공유",
        },
        {
          type: "new",
          area: "work",
          title: "파일 첨부 — 대화에 파일을 올려 함께 분석",
        },
        {
          type: "new",
          area: "work",
          title: "AI 데이터베이스 질의 — 자연어로 묻고 결과를 표로 확인",
        },
      ],
    },
  ],
};
