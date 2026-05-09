# 1. 서버 개요 및 아키텍처 (Overview)

## 개요 
이 프로젝트는 사내 IDE 플러그인(`crux-prometheus-plg`)에서 넘어오는 사용자 채팅, 코드 자동완성, 보안 검사 요청을 중앙에서 프록시(Proxy)하여 처리하는 **AI Proxy 서버(`crux-prometheus-bridge`)**입니다.

사내 보안 통제 및 인프라 정책을 준수하기 위해 사용자의 모든 요청은 이 서버를 거치게 되며, 서버에서 인증(Keycloak), 프롬프트 전처리, 권한 모니터링을 거친 후 내부 LLM(vLLM 기반 모델 등)으로 API를 라우팅하게 됩니다.

## 기술 스택 (Tech Stack)
- **언어 및 프레임워크:** Python 3.13, FastAPI (Uvicorn `runserver.py`)
- **데이터베이스:** PostgreSQL (`init_database.sql` 등)
- **인증 인가:** Keycloak 
- **LLM/AI 연동:** Langchain, vLLM

## 서버 디렉토리 구조 및 핵심 파일
이 프로젝트 디렉토리의 주요 폴더별 역할은 다음과 같습니다.

```text
crux-prometheus-bridge/
├── src/                # ✨ 서버 비즈니스 로직 (Controller, DB 연동, Auth 등)
│   ├── app.py          # FastAPI 애플리케이션 초기화 (Keycloak 헬스체크, DB 커넥션 풀 적용)
│   ├── auth/           # Keycloak 인증 처리 미들웨어 및 로직
│   ├── controller/     # API 엔드포인트 라우터 모음
│   ├── llm_provider/   # 각 LLM(vLLM, OpenAI 등) 과의 통신 인터페이스 모음
│   └── static/         # 보안 정적 분석 바이너리(Bearer) 등 리소스 위치
├── runserver.py        # 서버 실행 엔트리포인트 (포트 12345, Swagger 접근 차단 적용)
├── runserver_dev.py    # 로컬 개발용 엔트리포인트
├── config.json/py      # 서버 환경변수 및 세팅 로드
├── requirements.txt    # 서버 구동 필수 패키지 목록
├── Dockerfile          # 운영 배포용 도커 빌드 스펙 (난독화된 코드를 로드)
├── 젠킨스.txt          # 사내 Jenkins CI/CD 파이프라인 스크립트 (Jenkinsfile)
└── obfuscate_app.py    # PyArmor를 이용한 파이썬 소스 난독화 메인 스크립트 (.sh, .bat 포함)
```

## 서버 주요 특징
- 보안 목적상 Swagger 기능(`docs_url`, `redoc_url`)은 비활성화 되어 있습니다.
- 사내 인트라넷 운영망 배포 시, `src/` 전체 코드를 바로 쓰지 않고 **PyArmor 난독화** 절차를 거친 후 런타임에 로드하게끔 구성되어 있습니다.
