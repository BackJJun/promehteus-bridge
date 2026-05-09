import json
from typing import List

import asyncpg

from src.db.connection.db_async_postgre import Connection


async def merge_session_history(history_list: List, chat_id, new_session: bool):
    """Persist the full session history snapshot for a chat.

    Writes for the same chat are serialized with a transaction-level advisory
    lock. Each message index is upserted, then rows beyond the current snapshot
    are removed. This avoids duplicate key failures when a session save is
    retried or two saves overlap.
    """

    async def _transaction_callback(connection: asyncpg.Connection):
        await connection.execute("SELECT pg_advisory_xact_lock($1)", chat_id)

        rows = [(chat_id, idx, json.dumps(history)) for idx, history in enumerate(history_list)]
        if rows:
            await connection.executemany("""
                INSERT INTO chat_history_info (chat_id, message_index, message_data)
                VALUES ($1, $2, $3::jsonb)
                ON CONFLICT (chat_id, message_index)
                DO UPDATE
                SET
                    message_data = EXCLUDED.message_data,
                    updated_at = CURRENT_TIMESTAMP
            """, rows)

        await connection.execute("""
            DELETE FROM chat_history_info
            WHERE chat_id = $1 AND message_index >= $2
        """, chat_id, len(history_list))

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
