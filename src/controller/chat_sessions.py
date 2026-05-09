"""Chat session CRUD endpoints."""
import json
import traceback
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from loguru import logger
from pydantic import BaseModel

from src.auth.auth import User, get_current_user
from src.db import dao_session, dao_session_history

session_router = APIRouter(tags=["chat_sessions"])


class ChatMessage(BaseModel):
    role: str
    content: Any


class HistoryItem(BaseModel):
    message: ChatMessage


class SessionSaveRequest(BaseModel):
    sessionId: str
    title: str
    workspaceDirectory: str
    history: List[Dict[str, Any]]


class SessionMetadata(BaseModel):
    sessionId: str
    title: str
    dateCreated: str
    workspaceDirectory: str


class SessionListResponse(BaseModel):
    sessions: List[SessionMetadata]


class SessionDetailResponse(BaseModel):
    sessionId: Optional[str]
    title: Optional[str]
    workspaceDirectory: Optional[str]
    history: List[Dict[str, Any]]


class SuccessResponse(BaseModel):
    status: str
    sessionId: Optional[str] = None


def _extract_message_preview(content: Any) -> Optional[str]:
    if isinstance(content, str):
        return content

    if not isinstance(content, list):
        return None

    text_parts: list[str] = []
    image_count = 0

    for part in content:
        if not isinstance(part, dict):
            continue

        part_type = part.get("type")
        if part_type == "text" and part.get("text"):
            text_parts.append(str(part["text"]))
        elif part_type in {"image", "image_url", "imageUrl"}:
            image_count += 1

    preview = "\n".join(text_parts).strip()
    if preview:
        return preview
    if image_count:
        return f"[images: {image_count}]"
    return None


@session_router.post("/api/sessions", response_model=SuccessResponse)
async def save_session(
    session_request: SessionSaveRequest,
    http_request: Request,
    current_user: User = Depends(get_current_user),
):
    user_id = current_user.user_id

    logger.info(f"[Save Session] User ID: {user_id}")
    logger.info(f"[Save Session] Session ID: {session_request.sessionId}")
    logger.info(f"[Save Session] Title: {session_request.title}")
    logger.info(f"[Save Session] workspaceDirectory: {session_request.workspaceDirectory}")
    logger.info(f"[Save Session] History count: {len(session_request.history)}")
    question_list = [r for r in session_request.history if r.get("message", {}).get("role") == "user"]
    last_question_preview = (
        _extract_message_preview(question_list[-1].get("message", {}).get("content"))
        if question_list
        else None
    )
    logger.info(f"[Save Session] history last question: {last_question_preview}")

    try:
        chat_id = await dao_session.upsert_session_data(
            session_request.title,
            session_request.workspaceDirectory,
            session_request.sessionId,
            user_id,
        )

        if chat_id is None:
            raise HTTPException(status_code=409, detail="Session ID already exists for another user")

        await dao_session_history.merge_session_history(
            session_request.history,
            chat_id,
            new_session=False,
        )

        await dao_session_history.merge_last_session_info(
            user_id,
            session_request.workspaceDirectory,
            session_request.sessionId,
        )

        return SuccessResponse(status="success", sessionId=session_request.sessionId)

    except HTTPException:
        raise
    except Exception as e:
        print(traceback.format_exc())
        logger.error(f"[Save Session Error] {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@session_router.get("/api/sessions", response_model=SessionListResponse)
async def list_sessions(
    http_request: Request,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
):
    user_id = current_user.user_id
    sessions = await dao_session.select_user_session_list(user_id, limit, offset)

    logger.info(f"[List Sessions] User ID: {user_id}, Limit: {limit}, Offset: {offset}")

    session_metadata = [
        SessionMetadata(
            sessionId=row["session_id"],
            title=row["title"],
            dateCreated=str(row["date_created"]),
            workspaceDirectory=row["workspace_directory"],
        )
        for row in sessions
    ]

    logger.info(f"sessions length={len(session_metadata)}")
    return SessionListResponse(sessions=session_metadata)


@session_router.get("/api/sessions/{session_id}", response_model=SessionDetailResponse)
async def get_session(
    session_id: str,
    http_request: Request,
    current_user: User = Depends(get_current_user),
):
    try:
        user_id = current_user.user_id
        logger.info(f"[Get Session] User ID: {user_id}, Session ID: {session_id}")

        session = await dao_session.select_session_by_user_id_and_session_id(session_id, user_id)
        if not session:
            logger.warning(f"[Get Session] Session ID: {session_id}, User ID: {user_id} not found")
            raise HTTPException(status_code=404, detail="Session not found")

        history_list = await dao_session_history.select_session_history_list(user_id, session_id)

        return SessionDetailResponse(
            sessionId=session_id,
            title=session["title"],
            workspaceDirectory=session["workspace_directory"],
            history=[json.loads(row["message_data"]) for row in history_list],
        )

    except HTTPException:
        raise
    except Exception as e:
        print(traceback.format_exc())
        logger.error(f"[Get Session Error] {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@session_router.get("/api/sessions/last/data", response_model=SessionDetailResponse)
async def get_last_session(
    http_request: Request,
    workspace_directory: str = Query(...),
    current_user: User = Depends(get_current_user),
):
    try:
        user_id = current_user.user_id
        logger.info(f"[Get Session] User ID: {user_id}, workspace_directory: {workspace_directory}")

        session = await dao_session.select_last_session_by_user_id_and_workspace_directory(
            workspace_directory,
            user_id,
        )

        logger.info(f"session={session}")

        if not session:
            return SessionDetailResponse(
                sessionId=None,
                title="",
                workspaceDirectory=None,
                history=[],
            )

        session_id = session["session_id"]
        history_list = await dao_session_history.select_session_history_list(user_id, session_id)

        return SessionDetailResponse(
            sessionId=session_id,
            title=session["title"],
            workspaceDirectory=session["workspace_directory"],
            history=[json.loads(row["message_data"]) for row in history_list],
        )

    except HTTPException:
        raise
    except Exception as e:
        print(traceback.format_exc())
        logger.error(f"[Get Session Error] {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@session_router.delete("/api/sessions/{session_id}", response_model=SuccessResponse)
async def delete_session(
    session_id: str,
    http_request: Request,
    current_user: User = Depends(get_current_user),
):
    try:
        user_id = current_user.user_id
        await dao_session.delete_session(session_id, user_id)
        logger.info(f"[Delete Session] User ID: {user_id}, Session ID: {session_id}")
        return SuccessResponse(status="success")

    except HTTPException:
        raise
    except Exception as e:
        logger.info(f"[Delete Session Error] {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@session_router.delete("/api/sessions", response_model=SuccessResponse)
async def clear_all_sessions(
    http_request: Request,
    current_user: User = Depends(get_current_user),
):
    try:
        user_id = current_user.user_id
        logger.info(f"[Clear All Sessions] User ID: {user_id}")
        return SuccessResponse(status="success")

    except Exception as e:
        logger.error(f"[Clear All Sessions Error] {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
