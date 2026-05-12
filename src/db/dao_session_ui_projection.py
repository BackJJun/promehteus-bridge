import json
from typing import Any, Dict, List, Optional

import asyncpg

from src.db.connection.db_async_postgre import Connection


async def replace_session_ui_messages(
    chat_id: int,
    view_version: int,
    ui_messages: List[Dict[str, Any]],
    source_message_count: int,
    source_updated_at: Optional[Any],
    build_status: str = "success",
    error_message: Optional[str] = None,
):
    """Replace the derived UI projection snapshot for a chat/version."""

    async def _transaction_callback(connection: asyncpg.Connection):
        await connection.execute("SELECT pg_advisory_xact_lock($1)", chat_id)

        await connection.execute(
            """
            DELETE FROM chat_ui_message_info
            WHERE chat_id = $1 AND view_version = $2
            """,
            chat_id,
            view_version,
        )

        rows = [
            (
                chat_id,
                idx,
                message.get("sourceStartIndex"),
                message.get("sourceEndIndex"),
                message["messageType"],
                message.get("displayRole"),
                json.dumps(message.get("messageData", {}), ensure_ascii=False),
                view_version,
            )
            for idx, message in enumerate(ui_messages)
        ]

        if rows:
            await connection.executemany(
                """
                INSERT INTO chat_ui_message_info (
                    chat_id,
                    ui_message_index,
                    source_start_index,
                    source_end_index,
                    message_type,
                    display_role,
                    message_data,
                    view_version
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb, $8)
                """,
                rows,
            )

        await connection.execute(
            """
            INSERT INTO chat_ui_projection_info (
                chat_id,
                view_version,
                source_message_count,
                source_updated_at,
                build_status,
                error_message,
                built_at
            )
            VALUES ($1, $2, $3, $4, $5, $6, CURRENT_TIMESTAMP)
            ON CONFLICT (chat_id, view_version)
            DO UPDATE
            SET
                source_message_count = EXCLUDED.source_message_count,
                source_updated_at = EXCLUDED.source_updated_at,
                build_status = EXCLUDED.build_status,
                error_message = EXCLUDED.error_message,
                built_at = CURRENT_TIMESTAMP
            """,
            chat_id,
            view_version,
            source_message_count,
            source_updated_at,
            build_status,
            error_message,
        )

    return await Connection.execute_transaction(_transaction_callback)


async def select_session_ui_messages(user_id, session_id, view_version: int):
    return await Connection.execute_all(
        """
        SELECT
            ui.ui_message_index,
            ui.source_start_index,
            ui.source_end_index,
            ui.message_type,
            ui.display_role,
            ui.message_data,
            ui.view_version
        FROM chat_ui_message_info ui
        WHERE ui.chat_id = (
            SELECT chat_id FROM chat_session_info
            WHERE session_id = $1 AND user_id = $2
        )
        AND ui.view_version = $3
        ORDER BY ui.ui_message_index ASC
        """,
        (session_id, user_id, view_version),
    )


async def select_session_ui_projection(user_id, session_id, view_version: int):
    return await Connection.execute_one(
        """
        SELECT
            projection.chat_id,
            projection.view_version,
            projection.source_message_count,
            projection.source_updated_at,
            projection.build_status,
            projection.error_message,
            projection.built_at
        FROM chat_ui_projection_info projection
        WHERE projection.chat_id = (
            SELECT chat_id FROM chat_session_info
            WHERE session_id = $1 AND user_id = $2
        )
        AND projection.view_version = $3
        """,
        (session_id, user_id, view_version),
    )


async def select_chat_source_state(user_id, session_id):
    return await Connection.execute_one(
        """
        SELECT
            session.chat_id,
            COUNT(history.id)::INT AS source_message_count,
            MAX(history.updated_at) AS source_updated_at
        FROM chat_session_info session
        LEFT JOIN chat_history_info history ON history.chat_id = session.chat_id
        WHERE session.session_id = $1 AND session.user_id = $2
        GROUP BY session.chat_id
        """,
        (session_id, user_id),
    )

