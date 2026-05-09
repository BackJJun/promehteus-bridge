from src.db.connection.db_async_postgre import Connection


async def select_user_language_by_email(user_email: str):
    return await Connection.execute_one_val("""
        SELECT lang
        FROM usr_user_info
        WHERE lower(user_email) = lower($1)
        LIMIT 1
    """, (user_email,))
