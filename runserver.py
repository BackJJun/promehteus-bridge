import uvicorn

from src.app import app

if __name__ == '__main__':
    port = 12345
    print(f"run port = {port}")

    # 문서(스웨거) 못 보게 처리
    app.docs_url = None
    app.redoc_url = None
    app.openapi_url = None

    uvicorn.run(app=app,
                host='0.0.0.0',
                port=port,
                access_log=False  # 각 요청에 대해 fastapi가 남기는 로그 off
                )
