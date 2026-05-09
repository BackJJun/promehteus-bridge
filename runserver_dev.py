import uvicorn
# 개발 환경용
# from fastapi_mcp import FastApiMCP

from src.app import app

if __name__ == '__main__':
    # 시작 로그 출력
    # uvicorn 로그 설정을 None으로 해서 loguru로 로그가 처리되도록 함

    # 개발 환경용
    # mcp = FastApiMCP(
    #     app,
    #     name="sp mcp",
    #     # describe_all_responses=True,  # Include all possible response schemas
    #     # describe_full_response_schema=True,  # Include full JSON schema in descriptions,
    #     # include_operations=["register_new_model"],
    #     include_tags=["studio_tool_llm"]
    # )
    # mcp.mount()

    port = 12345
    print(f"run port = {port}")
    uvicorn.run(app=app,
                host='0.0.0.0',
                port=port,
                access_log=False  # 각 요청에 대해 fastapi가 남기는 로그 off
                )
