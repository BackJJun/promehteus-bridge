## 프로그램 소개

IDE 플러그인에서 오는 요청을 처리하는 서버  

- PYTHON 3.13
- postgresql
- Keycloak
- langchain

---

## 배포 필수 대상
- src   
- config.json
- config.py
- runserver.py

---

## 키클록 인증 토큰

Keycloak Admin Console에 로그인
Realm 설정으로 이동

왼쪽 메뉴에서 설정하려는 Realm을 선택
"Realm Settings" 메뉴 클릭


1. 액세스 토큰 설정   
Tokens 탭 선택
"Tokens" 탭을 클릭하면 토큰 관련 설정을 볼 수 있습니다

주요 설정 항목:
Access Token Lifespan: 액세스 토큰 유효 시간 (현재 300초 = 5분)

2. 리프레시 토큰 설정
Session 탭 선택
SSO Session Idle, SSO Session Max을 설정함

---

## 채팅 요청은 최소 두번 요청한다 (/v1/chat/completions)
클라이언트(컨티뉴)에서 채팅 입력 시 요청이 두번오게끔 되어 있다
예를들어 안녕? 이런 간단한 질문도 총 두번의 요청에 의해 처리되게끔
클라이언트에 구현되어 있다.

---

## VLLM 실행 예시

```
nohup python3 -m vllm.entrypoints.openai.api_server \
    --model openai/gpt-oss-120b \
    --tensor-parallel-size 2 \
    --port 8001 \
    --max-model-len 16384  \
    --gpu-memory-utilization 0.85 \
    --enable-auto-tool-choice \
    --tool-call-parser hermes \
    --chat-template ./templates/tool_chat_template_hermes.jinja \
    --no-enable-prefix-caching &
```

--- 

## 도커런 예시
```
docker run  \
-v /var/lib/docker/volumes/prometheus-ide/config.json:/app/config.json:ro \
-p 12345:12345 \
prometheus-ide-server
```


--- 

## 시큐리티 체크 관련 (소스코드 보안 체크)

- 요청경로 /scan에 해당하는 기능으로 소스코드 보안 분석을 한다  

- 아래 깃허브를 참조  
https://github.com/bearer/bearer

- 실행시 bearer 파일 권한이 없을수 있음 (chmod 755 src/static/secure_check/bin/bearer)
- 도커 환경에서 실행 시 `git` 패키지가 설치되어 있어야 정상 동작함 (Dockerfile에 git 설치 필수)



