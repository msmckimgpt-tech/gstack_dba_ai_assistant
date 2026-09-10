# Native Windows Codex MCP 검증

이 검증은 실제 Codex 모델을 호출한다. 설치 DQA UI나 외부 PC의 관리 정책 검증을 대체하지 않는다. 사용자 CLI 설정·로그인·인증서 저장소를 바꾸지 않는다. 상태·출력은 --out 옆 runner-state에 격리한다.

1. `make bridge-agent`로 배포 runner를 생성한다.
2. 검증 스크립트와 runner를 Windows 임시 폴더에 복사한다.
3. Windows Python으로 다음 명령을 실행한다(각 경로는 실제 설치 위치로 치환).

```powershell
python verify_native_codex_mcp.py --runner .\bridge_agent.py --codex C:\Apps\codex.exe --base https://dqa.example --ca C:\DQA\rootCA.crt --out .\remote-result.json
```

무효 진단 토큰을 사용해 실제 HTTP401·MCP event1 이상·shell event0을 검사한다. 정상 계정 토큰은 입력받거나 저장하지 않는다.

정상 도구 결과 검증은 로컬 TLS fixture를 사용한다. 별도 테스트 CA로 SAN IP:127.0.0.1, basicConstraints CA:FALSE, extendedKeyUsage serverAuth인 서버 인증서를 발급한다. 루트 CA 자체를 서버 leaf로 사용하면 TLS가 거절된다.

```powershell
python verify_native_codex_mcp.py --runner .\bridge_agent.py --codex C:\Apps\codex.exe --ca .\ca.pem --fixture-cert .\server.pem --fixture-key .\server.key --out .\fixture-result.json
```

MCP catalog→run_read_tool 두 실제 event, shell0 및 무작위 모의 schema 값의 답변 도달을 검사한다. 실제 DQA/DB 데이터는 조회하지 않는다. 임시 key·인증서는 검증 뒤 삭제한다.
