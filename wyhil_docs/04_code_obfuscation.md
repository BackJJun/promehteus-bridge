# 4. 소스코드 난독화 (Obfuscation) 프로세스

`crux-prometheus-bridge` 서버(AI Proxy)는 플러그인 로직을 감추거나 사내망 보안 정책 상 소스코드가 평문으로 배포되는 것을 막기 위해 **PyArmor** 기반의 난독화(Obfuscation) 프로세스를 가지고 있습니다.

## 4.1 난독화 개요 및 동작 순서
코드 난독화는 Jenkins 등에서 도커 리눅스 이미지를 말기 `직전`에 파이썬 가상환경에서 동작합니다.

1. 난독화 전용 메인 스크립트인 `obfuscate.sh` (혹은 윈도우용 `.bat`) 가 실행됩니다.
2. 스크립트는 내부적으로 분리된 파이썬 가상환경 (`obfuscation-venv3.13`) 을 호스트(Dev110 등)상에서 Activate 합니다.
3. `/scan` API를 동작하게 만드는 바이너리 폴더(`src/static/secure_check/bin`) 내부 권한 에러를 막기 위해 `chmod -R 755` 권한 설정을 주입합니다.
4. 본격적으로 `obfuscate_app.py` 툴을 콜하여 내부의 `src/` 핵심 파이썬 로직들을 변환하고 컴파일합니다.
5. 암호화된 `pyarmor_runtime_000000/` 라이브러리가 산출됩니다.

이후 도커 빌드(`Dockerfile`)에서는 난독화된 런타임 모듈들을 `/app` 환경 내부로 복사하여, 실제 실행파일인 `runserver.py`는 읽기 불가능한 코드로 비즈니스 흐름을 처리하게 됩니다.

## 4.2 실행 및 확인 지점 (Troubleshooting)
배포 시 뭔가 난독화 모듈 의존성 에러가 발생한다면, 보통 아래 두 지점을 점검합니다.
- `obfuscation.log`: 난독화 과정이 기록되는 로그. 여기서 에러가 없는지 확인.
- 프로젝트 내 `obfuscate_app.py` 에 정의된 제외 목록(Ignore list). 특정 리소스 폴더나 스웨거 관련 세팅이 너무 꼬이면 난독화 코드에서 런타임 크래쉬가 날 수 있어 점검이 필요합니다.
