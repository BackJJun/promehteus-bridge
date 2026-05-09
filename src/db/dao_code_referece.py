from src.db.connection.db_async_postgre import Connection


async def select_code_reference_by_id():
    return await Connection.execute_all(
        """
        SELECT doc_id, doc_name
        FROM code_doc_reference_info
        """
    )


async def select_code_reference_detail_by_doc_id(doc_id: str):
    return await Connection.execute_one(
        """
        SELECT
            i.doc_id,
            i.doc_name,
            COALESCE(
                STRING_AGG(c.content, E'\\n' ORDER BY c.chunk_index),
                ''
            ) AS content
        FROM code_doc_reference_info i
        LEFT JOIN code_doc_reference_chunks c
            ON i.doc_id = c.doc_id
        WHERE i.doc_id = $1
        GROUP BY i.doc_id, i.doc_name
        """,
        (doc_id,)
    )
