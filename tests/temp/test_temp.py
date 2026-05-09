import pytest

from src.db.connection.db_async_postgre import Connection


# python -m pytest -s .\tests\temp


@pytest.mark.asyncio
async def test_example(auth_client):
    """

    """
    chat_data_list = await Connection.execute_all("""
        SELECT message_index, message_data
        FROM chat_history_info
        WHERE chat_id = 68
        AND  message_index in (0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10)
    """)

    for c in chat_data_list:
        print(c)

    assert True
