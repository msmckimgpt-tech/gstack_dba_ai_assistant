# 테스터용 HTTPS 신뢰 설정 가이드 (Root CA 1회 설치)

> feature-0006-lan-proxy-access / TASK-0296·0298.
> 브라우저의 **"안전하지 않은 연결 / 주의 요함"** 경고를 없애기 위한 1회 설정이다.

## ⭐ 가장 쉬운 방법 — 웹 다운로드 페이지 (TASK-0298)

대부분의 테스터는 이 한 페이지면 됩니다:

**`http://mysql-ai.company.local/trust/`** 접속 → 사용하는 OS 의 설치 파일 받기 → 실행(승인 1회).

- Windows: `install-trust-windows.bat` 더블클릭 → 관리자 "예".
- macOS: `install-trust-macos.command` 더블클릭 → 비밀번호.
- 페이지에 표시된 **SHA-256 지문**이 운영자가 알려준 값과 같은지 확인하세요(가로채기 방지).
- 페이지는 **평문 HTTP** 라 아직 인증서를 안 깔아도 경고 없이 열립니다.

> 아래 §1~§4 는 위 방법이 막히거나 수동/Firefox 설치가 필요할 때의 상세 절차입니다.

---

## 왜 경고가 뜨나

서버는 사내 자체 **Root CA** 로 서명한 인증서로 HTTPS 를 제공한다. 이 Root CA 는
공개 CA(예: Let's Encrypt)가 아니라 사내 전용이라, 브라우저/OS 가 기본으로 신뢰하지
않는다. **Root CA 인증서(`rootCA.pem`)를 PC 신뢰 저장소에 한 번만 설치**하면 그 뒤로는
경고 없이 정상 자물쇠가 표시된다.

- 설치 대상은 **Root CA 1개** 뿐이다 (개별 서버 인증서가 아님).
- 서버 인증서(leaf)는 만료 시 서버에서 자동 교체되며, **테스터는 재설치할 필요가 없다**
  (Root CA 가 그대로 유지되기 때문). Root CA 유효기간은 10년이다.
- **`rootCA.pem` 만 배포**한다. `rootCA-key.pem`(개인키)은 절대 배포하지 않는다.

---

## 0. 준비: 서버 접속 경로

브라우저 주소는 **인증서에 등록된 이름/IP** 와 정확히 일치해야 한다 (불일치 시 이름이
달라 다시 경고가 뜬다). 등록된 접속 주소:

| 접속 방식 | 주소 | 비고 |
|---|---|---|
| 도메인 (권장) | `https://mysql-ai.company.local:18080` | 이름 해석 설정 필요 (아래) |
| IP 직접 | `https://112.185.196.20:18080` | 이름 해석 없이 바로 접속 |

> 포트는 현재 `18080` 이다 (web 직접 TLS). Caddy 프록시(`:443`)를 켜는 운영 구성에서는
> 포트 없이 `https://mysql-ai.company.local` 로 접속한다 — 운영자 안내를 따른다.

### 도메인 이름 해석 (hosts 파일)

사내 DNS 에 `mysql-ai.company.local` 이 등록돼 있지 않으면, 각 테스터 PC 의 hosts 파일에
한 줄 추가한다 (`<서버-IP>` 는 운영자가 알려주는 서버의 실제 접속 IP):

- **Windows** — 관리자 권한 메모장으로 `C:\Windows\System32\drivers\etc\hosts` 열고 추가:
  ```
  <서버-IP>   mysql-ai.company.local
  ```
- **macOS / Linux** — `sudo nano /etc/hosts` 후 같은 줄 추가.

IP 로 바로 접속(`https://112.185.196.20:18080`)할 경우 hosts 설정은 생략 가능하다
(인증서에 해당 IP 가 SAN 으로 포함돼 있다).

---

## 1. Windows 설치

운영자에게 받은 `rootCA.pem` 을 PC 에 저장한 뒤, **둘 중 하나**:

### 방법 A — 명령 한 줄 (관리자 PowerShell/CMD, 권장)
```cmd
certutil -addstore -f Root C:\path\to\rootCA.pem
```
`Root` 저장소(신뢰할 수 있는 루트 인증 기관)에 추가된다. 성공 시 "CertUtil: -addstore
명령이 성공적으로 완료되었습니다" 출력.

### 방법 B — GUI
1. `rootCA.pem` 더블클릭 → **인증서 설치**.
2. 저장소 위치: **로컬 컴퓨터**(전체 사용자) 또는 **현재 사용자**.
3. "인증서를 다음 저장소에 모두 저장" → **찾아보기** → **신뢰할 수 있는 루트 인증 기관** 선택.
4. 마침 → 보안 경고 "예".

> Chrome / Edge 는 Windows 의 이 저장소를 그대로 사용한다. 설치 후 **브라우저 완전 종료
> 후 재시작**.

---

## 2. macOS 설치

1. `rootCA.pem` 더블클릭 → **키체인 접근**이 열리며 "로그인" 또는 "시스템" 키체인에 추가.
2. 키체인 접근에서 방금 추가된 **mysql-ai Internal Root CA** 더블클릭.
3. **신뢰** 펼치기 → "이 인증서 사용 시" → **항상 신뢰**.
4. 창 닫고 암호 입력해 저장.

> Chrome / Safari 는 시스템 키체인을 사용한다. 설치 후 브라우저 재시작.

---

## 3. Firefox (별도 신뢰 저장소 — 모든 OS 공통)

Firefox 는 OS 저장소를 쓰지 않고 자체 저장소를 쓴다. Firefox 사용 시 추가로:

1. `about:preferences#privacy` → 맨 아래 **인증서** → **인증서 보기**.
2. **인증 기관(Authorities)** 탭 → **가져오기** → `rootCA.pem` 선택.
3. **"이 인증 기관이 웹사이트를 식별하도록 신뢰"** 체크 → 확인.

> (선택) Firefox 가 OS 저장소를 자동 사용하게 하려면 `about:config` 에서
> `security.enterprise_roots.enabled` 를 `true` 로 둔다 (사내 정책에 맞게).

---

## 4. 확인

설치 후 `https://mysql-ai.company.local:18080` (또는 IP 주소) 접속 →
**경고 없이 자물쇠 정상** 표시되면 성공. 인증서 정보의 발급자가
`mysql-ai Internal Root CA` 로 보인다.

여전히 경고가 뜨면:
- 브라우저를 완전히 종료 후 재시작했는지 (캐시된 인증서 상태).
- 접속 주소가 인증서 등록 이름/IP 와 일치하는지 (예: `localhost` 가 아니라 등록된 도메인/IP).
- Firefox 면 §3 의 자체 저장소 등록을 했는지.

---

## 운영자 메모

- Root CA / leaf 발급·갱신: 서버에서 `bash bin/tls-internal-ca.sh` 실행 후
  `sudo docker compose up -d --no-deps web`. Root CA 는 멱등 재사용(테스터 재설치 불필요),
  leaf 만 갱신된다.
- 배포 파일: `artifacts/certs/rootCA.pem` (이것만 테스터에게 전달).
- 개인키(`rootCA-key.pem`, `<host>/privkey.pem`)는 서버 밖으로 내보내지 않는다.
- 외부 인터넷/미신뢰 LAN 노출 시에는 `docs/SECURITY.md §7.2 / §9.7` 의 보완 조치를
  함께 검토한다.
