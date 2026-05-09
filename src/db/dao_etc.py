from src.db.connection.db_async_postgre import Connection


async def select_now():
    """현재 DB 시각 리턴"""
    return await Connection.execute_one_val("""        
        SELECT now()        
    """, )
