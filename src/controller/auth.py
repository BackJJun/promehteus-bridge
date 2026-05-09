from fastapi import APIRouter, HTTPException, Cookie, Request
from loguru import logger
from pydantic import BaseModel
from starlette.responses import Response, JSONResponse

from src.auth.auth import read_access_token, keycloak_login, keycloak_refresh_token
from src.db.dao_user import select_user_language_by_email
from src.util.token_read import print_exp_from_payload

auth_router = APIRouter(tags=["auth"])


class LoginData(BaseModel):
    username: str
    password: str


@auth_router.post("/login")
async def login(
        login_data: LoginData,
        response: Response
):
    """로그인 요청을 키클록을 통해 처리"""

    logger.info(f"로그인 요청옴!! username={login_data.username}, password={login_data.password}")

    # 키클록 로그인 처리
    res_json = await keycloak_login(login_data.username, login_data.password)

    # 액세스 토큰에서 데이터읽음
    payload = await read_access_token(res_json['access_token'])

    # 토큰 유효시간을 출력해봄(확인용)
    print_exp_from_payload(payload)

    language = payload.get('locale') or payload.get('language') or payload.get('lang')
    try:
        user_language = await select_user_language_by_email(payload['email'])
        if user_language:
            language = user_language
    except Exception as e:
        logger.warning(f"Failed to load user language: {e}")

    response = JSONResponse(content={
        "message": f"로그인 성공",
        "user_name": payload['preferred_username'],
        "user_email": payload['email'],
        "language": language,
        "access_token": res_json['access_token'],
        "refresh_token": res_json['refresh_token'],
    })

    return response


@auth_router.post("/refresh")
async def refresh_token_function(
        request: Request,
):
    logger.info(f"request={request}")

    request_body = await request.json()

    logger.info(f"request.headers str={str(request.headers)}")
    logger.info(f'request.cookies={request.cookies}')
    logger.info(f"request.body()={request_body}")

    refresh_token = request_body['refresh_token']

    # 키클록 리프레시 토큰 처리
    res_json = await keycloak_refresh_token(refresh_token)

    return JSONResponse(content={
        "access_token": res_json['access_token'],
        "refresh_token": res_json.get('refresh_token'),
    })

