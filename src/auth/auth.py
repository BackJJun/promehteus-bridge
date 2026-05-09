from typing import Optional

import httpx
from fastapi import Depends, HTTPException, Cookie
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from loguru import logger
from pydantic import BaseModel
from starlette import status

import config

SECRET_KEY = config.SECRET_KEY
ACCESS_TOKEN_COOKIE_NAME = "access_token"
REFRESH_TOKEN_COOKIE_NAME = "refresh_token"
ALGORITHM = "RS256"

KEYCLOAK_SERVER_URL = config.KEYCLOAK_SERVER_URL
KEYCLOAK_REALM = config.KEYCLOAK_REALM
KEYCLOAK_CLIENT_ID = config.KEYCLOAK_CLIENT_ID
KEYCLOAK_CLIENT_SECRET = config.KEYCLOAK_CLIENT_SECRET

# REFRESH_TOKEN_EXPIRE_SECONDS = 24 * 60 * 60  # 24시간


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


class User(BaseModel):
    user_id: str


# async def get_token_from_cookie(access_token: Optional[str] = Cookie(None, alias=ACCESS_TOKEN_COOKIE_NAME)):
#     if not access_token:
#         raise HTTPException(
#             status_code=status.HTTP_401_UNAUTHORIZED,
#             detail="Not authenticated"
#         )
#     return access_token

async def get_token_from_bearer(token: str = Depends(oauth2_scheme)):
    return token


async def get_current_user(token: str = Depends(get_token_from_bearer)):
    """Bearer access_token으로부터 유저 정보 로드 (Keycloak JWT 그대로 사용)"""

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = await read_access_token(token)
    except JWTError as e:
        logger.error(e)
        raise credentials_exception

    user_data = {
        "user_id": payload["sub"],
    }
    return User(**user_data)


async def read_access_token(token):
    return jwt.decode(
        token,
        f"""
-----BEGIN PUBLIC KEY-----
{SECRET_KEY}
-----END PUBLIC KEY-----
            """,
        algorithms=["RS256"],
        audience="account"
    )


async def keycloak_login(username: str, password: str) -> dict:
    """키클록을 통해 로그인을 처리하고 토큰을 반환"""
    
    token_url = f"{KEYCLOAK_SERVER_URL}/realms/{KEYCLOAK_REALM}/protocol/openid-connect/token"
    
    data = {
        "grant_type": "password",
        "client_id": KEYCLOAK_CLIENT_ID,
        "client_secret": KEYCLOAK_CLIENT_SECRET,
        "username": username,
        "password": password
    }
    
    async with httpx.AsyncClient() as client:
        res = await client.post(token_url, data=data)
    
    if res.status_code != 200:
        logger.info("로그인 실패")
        logger.info(res.text)
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    logger.info("로그인 성공")
    return res.json()


async def keycloak_refresh_token(refresh_token: str) -> dict:
    """키클록을 통해 리프레시 토큰으로 새로운 액세스 토큰을 발급"""
    
    if not refresh_token:
        logger.info("리프레시 토큰이 없다")
        raise HTTPException(status_code=401, detail="Refresh token missing")
    
    token_url = f"{KEYCLOAK_SERVER_URL}/realms/{KEYCLOAK_REALM}/protocol/openid-connect/token"
    
    data = {
        "grant_type": "refresh_token",
        "client_id": KEYCLOAK_CLIENT_ID,
        "client_secret": KEYCLOAK_CLIENT_SECRET,
        "refresh_token": refresh_token
    }
    
    async with httpx.AsyncClient() as client:
        res = await client.post(token_url, data=data)
    
    if res.status_code != 200:
        logger.info("리프레시 갱신이 200이 아님")
        logger.info(f"res.json() = {res.json()}")
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    
    return res.json()


async def keycloak_health_check() -> bool:
    """키클록 서버 헬스체크(프로그램 구동시 확인)"""
    
    token_url = f"{KEYCLOAK_SERVER_URL}/realms/{KEYCLOAK_REALM}/protocol/openid-connect/token"
    
    data = {
        "grant_type": "client_credentials",
        "client_id": KEYCLOAK_CLIENT_ID,
        "client_secret": KEYCLOAK_CLIENT_SECRET
    }
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            res = await client.post(token_url, data=data)
        
        if res.status_code != 200:
            logger.error(f"Keycloak 헬스체크 실패: HTTP {res.status_code}")
            logger.error(f"응답 내용: {res.text}")
            return False
        
        logger.info("Keycloak 헬스체크 성공")
        return True
        
    except httpx.TimeoutException:
        logger.error(f"Keycloak 헬스체크 타임아웃: {token_url}")
        return False
    except httpx.RequestError as e:
        logger.error(f"Keycloak 헬스체크 요청 실패: {e}")
        return False
    except Exception as e:
        logger.error(f"Keycloak 헬스체크 예상치 못한 오류: {e}")
        return False

