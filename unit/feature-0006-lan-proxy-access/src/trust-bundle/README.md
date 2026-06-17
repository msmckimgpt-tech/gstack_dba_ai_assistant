# Trust bundle (테스터 Root CA 원클릭 설치)

feature-0006-lan-proxy-access / TASK-20260617T083954-ai-claude-trust-bundle. 테스터가 PC 마다 수동으로 인증서를 옮기지
않도록, web 서버가 `http://<host>/trust/` 에서 제공하는 설치 번들의 **템플릿** 디렉토리.

## 구성

- `index.html.tmpl` — OS 감지 다운로드 페이지 (지문 대조 안내 포함)
- `install-trust-windows.bat.tmpl` — Windows 단일 자가완결 설치 파일 (인증서 임베드 +
  자가-상승 + `certutil -addstore -f Root`)
- `install-trust-macos.command.tmpl` — macOS 단일 설치 파일 (`security add-trusted-cert`)

템플릿 placeholder: `__PUBLIC_HOST__`, `__ROOTCA_SHA256__`(콜론 표기),
`__ROOTCA_SHA256_HEX__`(검증용), `__ROOTCA_B64__`(PEM base64).

## 빌드 / 갱신

```bash
bash bin/tls-internal-ca.sh      # Root CA + leaf (멱등) — 먼저
bash bin/trust-bundle.sh         # templates → artifacts/trust-bundle/ 조립
sudo docker compose up -d --no-deps caddy   # 반영 (mount)
```

`bin/trust-bundle.sh` 가 `artifacts/certs/rootCA.pem` 를 읽어 지문/​base64 를 주입하고
`artifacts/trust-bundle/{index.html, install-trust-windows.bat,
install-trust-macos.command, rootCA.crt}` 를 생성한다. (`tls-internal-ca.sh` 가 끝에서
자동 호출하므로 인증서 갱신 시 번들도 함께 갱신된다.)

## 보안 (신뢰 부트스트랩)

Root CA 최초 배포는 채널 무결성이 본질적 한계다 (HTTP·HTTPS 무관 — 미설치 상태라
암호학적 신뢰가 없음). 완화:

1. 번들은 Root CA **SHA-256 지문**을 페이지·스크립트에 노출하고, 설치 스크립트가 설치
   전 지문을 재검증한다.
2. **운영자는 지문을 신뢰 채널(사내 메신저·구두·인쇄)로 공유**해 테스터가 대조하도록
   안내한다. 지문 불일치 시 설치 중단.
3. 사내 LAN 가정 (SECURITY.md §9.7). 외부/미신뢰 LAN 노출 시 §7.2/§9.7 보완 선행.

개인키(`rootCA-key.pem`)는 번들에 포함하지 않는다 — `rootCA.crt`(공개) 만.
