"""
    테스트 실행전 fixture(테스트 준비물)을 설정함,
    conftest.py 파일 이름을 pytest가 인식함(파일명 수정하지 말것)
    모든 테스트에 적용됨

    scope 설명:
        session: 전체 테스트 세션당 하나
        module: 테스트 파일당 하나
        function (기본값): 각 테스트마다 새로 생성

"""
from datetime import datetime, timezone, timedelta

import pytest
import asyncio
import uuid
from httpx import AsyncClient, ASGITransport
from asgi_lifespan import LifespanManager
from jose import jwt

from src.app import app

ADMIN_USER_ID = "admin"
TENANT_USER_ID = "test-admin"
NORMAL_USER_ID = "test-user"


# 2. 전역 Base Client (비동기 + Lifespan 제어)
@pytest.fixture(scope="function")
async def base_client():
    """
    LifespanManager를 통해 앱 시작(DB연결) -> 테스트 -> 앱 종료(DB해제)를
    비동기 컨텍스트 안에서 안전하게 처리합니다.
    """
    # LifespanManager가 app의 lifespan(DB pool 생성)을 트리거합니다.
    async with LifespanManager(app) as manager:
        # ASGITransport를 사용하여 비동기적으로 앱과 통신합니다.
        async with AsyncClient(transport=ASGITransport(app=manager.app), base_url="http://test") as client:
            yield client


# 3. 인증 Client (비동기)
@pytest.fixture(scope="function")
async def auth_client(base_client, request):
    """
    하나의 통합 인증 client fixture.

    - parametrize가 있으면 request.param 사용
    - parametrize가 없으면 default = "normal" (또는 원하는 기본값)
    """

    # ⭐ parametrize 없이 사용될 때 기본 user type 지정
    user_type = getattr(request, "param", "normal")

    user_map = {
        "normal": NORMAL_USER_ID,
        "tenant": TENANT_USER_ID,
        "admin": ADMIN_USER_ID,
        "no_auth": None,
    }

    user_id = user_map.get(user_type)

    # 매 테스트마다 쿠키 초기화
    base_client.cookies.clear()

    # 무인증 클라이언트
    if user_id is None:
        return base_client

    # 인증 클라이언트

    # base_client.cookies.set("access_token", )
    ref_value = str(uuid.uuid4()).replace('-', '')[:10]

    data = {
        "user_id": "aa"
    }

    expires_delta = timedelta(seconds=900)
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + expires_delta
    to_encode.update({"exp": expire})

    access_token = jwt.encode(to_encode, "b753910f695cfe6b26c326dee8fd1496818931fea43ad261b6fa245cc31c7550", algorithm="HS256")

    base_client.cookies.set("access_token", access_token)
    return base_client
