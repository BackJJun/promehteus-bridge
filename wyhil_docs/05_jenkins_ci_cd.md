# 5. 사내 Jenkins CI/CD 파이프라인

사내 망의 `Dev110` (가칭) 인프라에서 소스코드를 받아 난독화하고 컨테이너를 갈아끼우는 자동화 파이프라인(Jenkinsfile) 구조입니다.
프로젝트 루트에 있는 `젠킨스.txt` 파일에 파이프라인 코드로 반영되어 있습니다. 이 코드는 Jenkins에서 `Pipeline script`로 동작합니다.

## 5.1 파이프라인 흐름 요약 (Stages)

1. **Checkout Source Code:**
   Bitbucket 저장소(예: `crux-continue-server.git`)에서 최신 `main` 브랜치를 소스코드 에이전트로 내려받습니다.
2. **Remove Old Container:**
   현재 12345 포트를 점유하며 돌아가고 있는 기존 도커 컨테이너(`prometheus-plg-server-container`)를 `docker stop`, `docker rm` 하여 강제 종료 및 삭제시킵니다.
   _주의: 무중단 배포(Zero-downtime) 구성이 아니기 때문에, 이 스크이지 동안 서버 접속 단절이 일시적으로 발생합니다._

3. **Obfuscate Source Code on Dev110:**
   도커 이미지를 굽기 전에, 로컬 에이전트 머신 상에서 `chmod +x obfuscate.sh` 이후 쉘 파일 `./obfuscate.sh`를 실행하여 앞서 말씀드린 **난독화(PyArmor)** 파이프라인을 돌립니다. (의존성: 에이전트 자체에 Python 3.13 Venv 가 설치되어 있어야 동작함).

4. **Prepare Host Directories:**
   도커가 런타임에 참조할 로컬 서버(`dev110`) 호스트 볼륨 디렉토리를 체크합니다.

5. **Build Docker Image:**
   난독화 세트가 포함된 디렉토리 내에서 `docker build`를 실행해 `prometheus-plg-server:latest` 이미지를 생성합니다.

6. **Run Docker Container:**
   백그라운드(`-d`) 노드로 도커를 포트 매핑(`12345:12345`) 하여 실행시킵니다. 이때 `--add-host host.docker.internal:192.168.14.110` 와 민감 환경변수 `config.json` 마운트를 삽입하여 자체 네트워크간 연결되도록 합니다.

7. **Health Check:**
   `sleep 10` 지연 시간 이후에 프로세스 목록이나 로그(마지막 20줄)를 확인하여 서버가 즉사하지 않았는지 체킹한 후 Success 마크를 달고 종료합니다.

## 5.2 백엔드 파이프라인 연동 간 주의점

- 젠킨스 에이전트(`label 'dev110'`) 자체가 도커 빌더이자, 실제 호스트 서버 역할을 겸비하는 것으로 보입니다. 다른 원격계 서버로 배포가 필요하다면 SSH Publisher 플러그인 등으로 배포 단계를 변경해야 합니다.

젠킨슨 => dev.wyhil.com:18000 => 프로메테우스 - PLG-SERVER-dev110 빌드 및 배포
다른 곳 설치 시 : 젠킨슨 -> 프로메테우스 -> PLG-SERVER-dev110 빌드 및 배포 -> 구성 -> tiggers -> pipeline 4번까지
개발환경일 시 : 그냥 진행

docker image file은 docker 내부에 생성
wyhil / 5748
