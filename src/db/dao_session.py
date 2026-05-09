from src.db.connection.db_async_postgre import Connection


async def select_session_by_user_id_and_session_id(session_id, user_id):
    """session_id와 user"""
    return await Connection.execute_one("""
        SELECT *
        FROM chat_session_info
        WHERE session_id = $1 AND user_id = $2
    """, (session_id, user_id))



async def select_user_session_list(user_id, limit, offset):
    """유저의 세션 목록 조회 페이징 처리"""
    return await Connection.execute_all("""
            SELECT 
                session_id,
                title,
                date_created,
                workspace_directory
            FROM chat_session_info
            WHERE user_id = $1 AND is_deleted = FALSE
            ORDER BY date_created DESC
            LIMIT $2 OFFSET $3
    """, (user_id, limit, offset))


async def update_session_data(title, workspace_directory, session_id, user_id):
    """세션 정보 수정"""
    return await Connection.execute("""
        UPDATE chat_session_info 
        SET title = $1, 
            workspace_directory = $2, 
            updated_at = CURRENT_TIMESTAMP
        WHERE session_id = $3 AND user_id = $4
        RETURNING chat_id
    """, (title, workspace_directory, session_id, user_id))


async def insert_session_data(title, workspace_directory, session_id, user_id):
    """세션 정보 업데이트"""
    return await Connection.execute_one_val("""
        INSERT INTO chat_session_info (session_id, user_id, title, workspace_directory)
        VALUES ($1, $2, $3, $4)
        RETURNING chat_id
    """, (session_id, user_id, title, workspace_directory))


async def delete_session(session_id, user_id):
    """세션을 삭제 처리(소프트 삭제)"""
    return await Connection.execute("""        
        UPDATE chat_session_info
        SET is_deleted = TRUE
        WHERE session_id = $1 AND user_id = $2
    """, (session_id, user_id))


async def select_last_session_by_user_id_and_workspace_directory(workspace_directory, user_id):
    return await Connection.execute_one("""        
        SELECT l.*, c.title
        FROM chat_last_session l
        JOIN chat_session_info c
        ON l.session_id = c.session_id
        WHERE l.workspace_directory = $1 AND l.user_id = $2
    """, (workspace_directory, user_id))