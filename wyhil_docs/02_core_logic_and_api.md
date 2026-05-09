# 2. 핵심 API 및 주요 로직 (Core API & Logic)

`crux-prometheus-bridge` 서버 안에서 담당하는 주요 비즈니스 흐름을 정리합니다. 이 내용은 IDE 플러그인에서 날아온 HTTP API를 파싱하고 사내 내부 모델(vLLM) 등에 매핑하는 로직 등에 대한 내용입니다.

## 2.1 채팅 및 코드 생성 API (`/v1/chat/completions`)
플러그인 클라이언트에서 입력된 질문 혹은 IDE가 컨텍스트를 모아서 보내는 채팅 메인 엔드포인트입니다.
- **특징:** 클라이언트 단에서 "안녕?" 이라는 짧은 질문을 쳐도, 컨텍스트 스캔 및 내부 로직에 의해 최소 두 번의 요청이 오게끔 설계되어 있습니다. 로그나 호출 통계를 모니터링하실 때 이중 호출로 오해하지 않도록 주의하세요.
- **연동 모델:** 뒷단의 사내 GPU 인프라에 띄워진 vLLM(예: `openai/gpt-oss-120b`)으로 Langchain/직접호출 방식을 통해 포워딩합니다. 

## 2.2 소스코드 보안 분석 API (`/scan`)
사용자가 코드를 저장(On-Save)하거나 스캔 커맨드를 실행하면 트리거되어 소스코드를 분석합니다.
- **분석 도구:** 서버 내부 `src/static/secure_check/bin/bearer` 바이너리를 활용해 정적 분석(SAST) 로직을 돌립니다. (의존성: Git 패키지가 OS/Docker 내에 설치되어 있어야 정상 동작합니다)
- **주의사항:** Jenkins 배포나 특정 리눅스 환경에서 `Permission denied` 에러가 난다면, 해당 폴더의 베어러(bearer) 파일에 실행 권한(`chmod 755`)이 누락된 것이므로 인프라 세팅 시 유의해야 합니다.

## 2.3 Keycloak 인증 로직 (Auth)
서버에 접근하는 모든 플러그인 통신은 커스텀 Keycloak 연동 토큰 기반 인증을 사용합니다.
- Realm 설정에서 세팅된 **Access Token Lifespan (유효시간 5분=300초)** 에 따라 플러그인이 API를 찔렀을 때 401(Unauthorized) 응답을 줄 수 있습니다.
- 백엔드는 401을 내리며, 플러그인(client) 측이 이것을 인지하고 자동으로 **Refresh API**를 호출해 세션을 연장한 뒤에 이전 요청을 재시도(Retry) 하도록 플로우가 짜여 있습니다.
- 인증 SSO 연결 설정은 Keycloak Admin Console -> Realm Settings -> Session / Tokens 탭을 구성하여 조절합니다.

## 2.4 서버 초기화 시퀀스 (Startup Lifespan / `app.py`)
컨테이너(혹은 프로세스) 구동 시, 트래픽을 받기 전에 `src/app.py` 의 `lifespan` 훅을 통해 무결성을 체크합니다.
- **Keycloak 헬스체크:** 가장 먼저 Keycloak 서버 연동이 정상인지 확인하며, 실패 시 서버 구동 자체를 중지(RuntimeError)시킵니다.
- **DB 커넥션 풀 생성:** 헬스체크 통과 이후 비동기 트래픽 처리를 위한 Postgres DB Connection Pool을 즉시 초기화하여 응답 속도를 확보합니다.

## 2.5 리눅스 종속 도구 개발 구성 (Remote - SSH)
`/scan` 기능의 정적 분석 도구인 `Bearer`는 **리눅스 OS 환경에서만 동작하는 바이너리**입니다.
- 개발 환경이 Windows나 Mac이라면 에러가 유발되거나 실행되지 않을 수 있습니다.
- 이 특정 소스 보완 스캔 기능을 수정하고 테스트할 때는 변경 사항을 젠킨스 및 CI 없이 사전에 디버깅하기 위해 **VSCode의 `Remote - SSH` 확장 기능**을 사용하여 실제 구동될 리눅스 테스트 서버 인스턴스에 접속해서 원격지 위에서 코드를 직접 수정하며 개발하는 방식을 권장합니다.
