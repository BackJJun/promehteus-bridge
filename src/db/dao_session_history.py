import json
from typing import List

import asyncpg
from cryptography.hazmat.primitives.keywrap import aes_key_wrap
from loguru import logger

from src.db.connection.db_async_postgre import Connection


async def merge_session_history(history_list: List, chat_id, new_session: bool):
    """세션 히스토리(실제 내용)을 넣음, 세 세션이 아니면 기존것을 지우고 넣음"""

    async def _transaction_callback(connection: asyncpg.Connection):
        if not new_session:
            await connection.execute("""DELETE FROM chat_history_info WHERE chat_id = $1 """,
                                     chat_id)

        for idx, history in enumerate(history_list):
            await connection.execute("""
                INSERT INTO chat_history_info (chat_id, message_index, message_data)
                VALUES ($1, $2, $3::jsonb)
            """, chat_id, idx, json.dumps(history))

    return await Connection.execute_transaction(_transaction_callback)


async def select_session_history_list(user_id, session_id):
    return await Connection.execute_all("""
        SELECT 
            message_index,
            message_data
        FROM chat_history_info
        WHERE chat_id = (
            SELECT chat_id FROM chat_session_info
            WHERE session_id = $1 AND user_id = $2
        )
        ORDER BY message_index ASC
    """, (session_id, user_id))


async def merge_last_session_info(user_id, workspace_directory, session_id):
    return await Connection.execute("""
        INSERT INTO chat_last_session (
            user_id,
            workspace_directory,
            session_id
        )
        VALUES (
            $1,
            $2,
            $3
        )
        ON CONFLICT (user_id, workspace_directory)
        DO UPDATE
        SET
            session_id = EXCLUDED.session_id,
            updated_at = CURRENT_TIMESTAMP;
        
            """, (user_id, workspace_directory, session_id))
