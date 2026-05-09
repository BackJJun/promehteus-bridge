from src.db.connection.db_async_postgre import Connection


async def select_models():
    """모든 LLM 모델 조회"""
    return await Connection.execute_all("""        
        SELECT id, model_id, model_name, model_class, model_provider,
               model_roles, api_base_url, is_active, open_source_yn, 
               default_model, disable_agent_mode, max_tokens
        FROM model_info
        WHERE is_active = true        
    """)


async def select_model_by_model_id(model_id):
    """LLM 조회"""
    return await Connection.execute_one("""        
        SELECT *
        FROM model_info
        WHERE model_id = $1
    """, (model_id,))


async def select_default_model():
    """기본 사용 LLM 조회"""
    return await Connection.execute_one("""        
        SELECT *
        FROM model_info
        WHERE default_model = 'y'
    """, )

