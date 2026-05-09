# Dockerfile - 운영 환경 배포용 (난독화 하는 버전)
FROM python:3.13-slim

# 작업 디렉토리 설정
WORKDIR /app

# 타임존 환경 변수 설정 (KST)
ENV TZ=Asia/Seoul

# 시스템 패키지 업데이트 및 필요한 도구 설치
RUN apt-get update && apt-get install -y \
    gcc \
    curl \
    git \
    tzdata \
    && ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone \
    && rm -rf /var/lib/apt/lists/*

# 필요한 디렉토리 생성
RUN mkdir -p /app/temp /app/logs

# Python 의존성 파일 복사 및 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 애플리케이션 코드 복사
COPY src/ ./src/
COPY runserver.py .
COPY config.py .
# 난독화시 아래 폴더도 복사해야함
COPY pyarmor_runtime_000000/ ./pyarmor_runtime_000000/
# 볼륨 포인트 정의
VOLUME ["/app/temp", "/app/logs"]

# 포트 노출
EXPOSE 12345

# 애플리케이션 실행
CMD ["python", "runserver.py"]