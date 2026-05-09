# 3. 배포(Docker) 환경 구성

운영 환경(혹은 개발계 배포 서버)에 올라가는 도커 컨테이너화 정보입니다.

## 3.1 Dockerfile 구조
루트에 위치한 `Dockerfile`은 `python:3.13-slim` 기반으로 구성되어 있습니다. 플러그인의 처리 속도를 최적화 하고 보안을 유지하기 위해 최소한의 패키지만 올려둡니다.

**주요 도커 구성 포인트:**
- **의존성(OS):** 내부 소스코드 보안 컴파일 및 `bearer` 구동을 위해 `gcc`, `curl`, `git` 등이 레이어상에 인스톨됩니다. 서버 타임존은 `Asia/Seoul`로 고정합니다.
- **소스 복사 (난독화 적용):** 개발망 소스(`src/`)만 통째로 올리는 게 아니라, **보안 난독화를 마친 폴더(`pyarmor_runtime_000000/`)를 포함하여 카피**합니다. 이는 난독화 절차가 로컬/CI에서 먼저 일어난 다음에 런타임에 이 빌드된 코드를 넘기는 방식임을 뜻합니다.
- **외부 설정(Config):** 민감한 `config.json` 정보는 이미지 안에 굽지 않습니다. Docker Volume (Mount)을 사용해 호스트 머신의 경로(`/var/lib/docker/volumes/prometheus-ide/config.json`)를 컨테이너 안에 읽기 전용(`:ro`)으로 덮어씁니다.

## 3.2 로컬/테스트 서버 런타임 예시 (Docker Run)
실제로 사내 서버 머신 위에 띄워질 때 실행 명령어 예시입니다. 포트는 12345번을 사용합니다.
```bash
docker run -d \
  -v /var/lib/docker/volumes/prometheus-ide/config.json:/app/config.json:ro \
  -p 12345:12345 \
  --name prometheus-ide-server \
  prometheus-ide-server:latest
```

## 3.3 백엔드 추론 모델 런타임 (vLLM)
백엔드 앱(`/app` 컨테이너)이 실제로 AI 추론 연산을 넘기는 GPU 인프라의 vLLM 실행은 아래와 같은 구성의 파라미터를 사용하여 따로 데몬(nohup)으로 구동됩니다.
- 모델: `openai/gpt-oss-120b` (예시)
- 파라미터 튜닝: `--tensor-parallel-size 2`, `--max-model-len 16384`
- 툴 파서 통제: `--enable-auto-tool-choice`, `--tool-call-parser hermes` 등이 부여되어 있습니다. (이 때문에 특정 플러그인 Provider의 Tool parsing 오류가 간헐적으로 발생할 수 있습니다. `07_known_issues_and_todos.md` 참고)
