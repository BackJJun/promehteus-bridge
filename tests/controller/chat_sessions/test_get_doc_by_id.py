import pytest

from src.db.connection.db_async_postgre import Connection


# python -m pytest -s .\tests\controller\chat_sessions\test_get_doc_by_id.py


@pytest.mark.asyncio
async def test_example(auth_client):
    """

    """
    session_list = await Connection.execute_all("""
        SELECT *
        FROM chat_session_info
    """)

    for s in session_list:
        print(s['workspace_directory'])

    assert True
