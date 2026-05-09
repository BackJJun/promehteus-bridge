import logging
import os
import random
import string
import uuid
import sys
import time
import json
from contextvars import ContextVar
from jose import jwt
from jose.exceptions import JWTError

from fastapi import FastAPI, Request
from loguru import logger
from starlette.middleware.base import BaseHTTPMiddleware

# 요청 ID를 저장할 context variable
request_id_contextvar = ContextVar("request_id", default="N/A")
# 사용자 ID를 저장할 context variable
user_id_contextvar = ContextVar("user_id", default="N/A")

# 요청
exclusion_list = [
    "/notifications/count"
]


# 현재 요청의 ID를 가져오는 함수
def get_request_id():
    return request_id_contextvar.get()


# 현재 사용자 ID를 가져오는 함수
def get_user_id():
    return user_id_contextvar.get()


# 로그 메시지에 요청 ID와 사용자 ID를 추가하는 로직
def request_id_filter(record):
    record["extra"].update({
        "request_id": get_request_id(),
        "user_id": get_user_id()
    })
    return record


# 기본 로거 설정
logger.remove()  # 기본 핸들러 제거

LOG_DIR = "logs"
LOG_FORMAT = "{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {extra[request_id]} | {extra[user_id]} | {function} : {message}"
os.makedirs(LOG_DIR, exist_ok=True)

# 콘솔 로깅 설정 - 개발 중에는 DEBUG 레벨로 설정
logger.add(
    sys.stderr,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <magenta>{extra[request_id]}</magenta> | <yellow>{extra[user_id]}</yellow> | <cyan>{function}</cyan> : <level>{message}</level>",
    level="DEBUG",  # DEBUG로 변경하여 더 많은 로그 확인
    filter=request_id_filter
)

logger.add(
    os.path.join(LOG_DIR, "{time:YYYY-MM-DD}.log"),
    format=LOG_FORMAT,
    level="DEBUG",
    rotation="00:00",
    encoding="utf-8",
    filter=request_id_filter,
)


# uvicorn 로그 인터셉터 클래스
class InterceptHandler(logging.Handler):
    def emit(self, record):
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        frame, depth = logging.currentframe(), 2
        while frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )


# 쿠키에서 사용자 ID 추출
def extract_user_id_from_cookie(request: Request):
    # 쿠키 값 가져오기
    # cookies = request.cookies
    # access_token = cookies.get(ACCESS_TOKEN_COOKIE_NAME)
    #
    # if not access_token:
    #     return "N/A"

    try:
        # JWT 토큰 디코딩
        # payload = jwt.decode(access_token, SECRET_KEY, algorithms=["HS256"])
        # user_id = payload.get("user_id")
        # return user_id if user_id else "N/A"
        return "user_id"
    except JWTError:
        return "N/A"
    except Exception:
        return "N/A"


# 통합된 요청 ID 및 로깅 미들웨어
class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # 요청 헤더에 X-Request-ID가 있으면 사용, 없으면 새로 생성
        # request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        # request_id = str(uuid.uuid4())
        request_id = ''.join(random.choices(string.ascii_letters + string.digits, k=8))

        # 요청 ID를 context에 저장
        request_id_contextvar.set(request_id)

        # 쿠키에서 사용자 ID 추출
        user_id = extract_user_id_from_cookie(request)
        user_id_contextvar.set(user_id)

        # 시작 시간 기록
        start_time = time.time()

        if request.url.path not in exclusion_list:
            logger.info(f"요청 시작: {request.method} {request.url.path}{request.url.query and f'?{request.url.query}'}")
            # logger.info(f"access_token exists={True if request.cookies.get('access_token') else False}")

        try:
            # 실제 요청 처리
            response = await call_next(request)

            # 응답 시간 계산
            process_time = (time.time() - start_time) * 1000

            # 응답 로깅
            if request.url.path not in exclusion_list:
                logger.info(
                    f"요청 완료 {request.method} {request.url.path} - Status: {response.status_code} - Time: {process_time:.2f}ms")

            # 응답 헤더에 요청 ID 추가
            # response.headers["X-Request-ID"] = request_id

            return response
        except Exception as exc:
            # 예외 발생 시 로깅
            process_time = (time.time() - start_time) * 1000
            logger.error(
                f"Error processing request: {request.method} {request.url.path} - Time: {process_time:.2f}ms - Error: {str(exc)}")
            raise
        finally:
            # context를 리셋하지 않고 요청이 끝날 때까지 유지
            # 요청 처리가 완료된 후에도 로깅에서 ID를 계속 사용할 수 있도록 함
            pass


def setup_logging():
    # 기본 Python 로거를 loguru로 리디렉션
    logging.root.handlers = [InterceptHandler()]
    logging.root.setLevel(logging.INFO)

    # Uvicorn 관련 로거 설정
    for name in logging.root.manager.loggerDict.keys():
        if name.startswith("uvicorn") or name.startswith("fastapi"):
            logging_logger = logging.getLogger(name)
            logging_logger.handlers = [InterceptHandler()]
            logging_logger.propagate = False
            logging_logger.setLevel(logging.DEBUG)

    logger.debug("셋업 로깅 실행 완료")


def setup_app_logging(app: FastAPI):
    # 로깅 설정 초기화
    setup_logging()

    app.add_middleware(RequestIDMiddleware)

    logger.info("FastAPI 애플리케이션 로깅 설정 완료")


# 컨트롤러에서 현재 요청 ID와 사용자 ID를 가져와 로그에 포함하는 헬퍼 함수
def log_with_context_info(level, message):
    request_id = get_request_id()
    user_id = get_user_id()
    getattr(logger, level)(f"{message} (ID: {request_id}, User: {user_id})")
