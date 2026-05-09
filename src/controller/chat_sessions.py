"""채팅 데이터 CRUD"""
import json
import traceback

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from typing import List, Optional, Dict, Any

from httpx import request
from loguru import logger
from pydantic import BaseModel
from datetime import datetime
import uuid

import src.db.dao_session_history
from src.auth.auth import User, get_current_user
from src.db import dao_session, dao_session_history

session_router = APIRouter(tags=["chat_sessions"])


# ==================== Request/Response Models ====================

class ChatMessage(BaseModel):
    """채팅 메시지 구조"""
    role: str
    content: str
    # 추가 필드들은 message_data에 포함


class HistoryItem(BaseModel):
    """히스토리 아이템 구조"""
    message: ChatMessage
    # 기타 메타데이터


class SessionSaveRequest(BaseModel):
    """세션 저장 요청"""
    sessionId: str
    title: str
    workspaceDirectory: str
    history: List[Dict[str, Any]]  # HistoryItem 배열


class SessionMetadata(BaseModel):
    """세션 메타데이터 응답"""
    sessionId: str
    title: str
    dateCreated: str  # ISO 8601 format
    workspaceDirectory: str


class SessionListResponse(BaseModel):
    """세션 목록 응답"""
    sessions: List[SessionMetadata]


class SessionDetailResponse(BaseModel):
    """세션 상세 응답"""
    sessionId: Optional[str]
    title: Optional[str]
    workspaceDirectory: Optional[str]
    history: List[Dict[str, Any]]


class SuccessResponse(BaseModel):
    """성공 응답"""
    status: str
    sessionId: Optional[str] = None


# ==================== Dependency ====================


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


# ==================== Endpoints ====================

@session_router.post("/api/sessions", response_model=SuccessResponse)
async def save_session(
        session_request: SessionSaveRequest,
        http_request: Request,
        current_user: User = Depends(get_current_user)
):
    """
    세션 저장 또는 업데이트

    - 새 세션이면 생성
    - 기존 세션이면 업데이트
    - 히스토리 전체를 교체

    Parameters:
    - sessionId: 세션 고유 ID (UUID)
    - title: 채팅 제목
    - workspaceDirectory: 작업 디렉토리 경로
    - history: 채팅 메시지 배열

    Returns:
    - status: "success"
    - sessionId: 저장된 세션 ID
    """

    user_id = current_user.user_id

    logger.info(f"[Save Session] User ID: {user_id}")
    logger.info(f"[Save Session] Session ID: {session_request.sessionId}")
    logger.info(f"[Save Session] Title: {session_request.title}")
    logger.info(f"[Save Session] workspaceDirectory: {session_request.workspaceDirectory}")
    logger.info(f"[Save Session] History count: {len(session_request.history)}")
    question_list = [r for r in session_request.history if r.get("message", {}).get("role") == 'user']
    last_question_preview = (
        _extract_message_preview(question_list[-1].get("message", {}).get("content"))
        if question_list
        else None
    )
    logger.info(f"[Save Session] history last question: {last_question_preview}")

    try:

        # 1. 존재하는 세션인지 메타 데이터 조회
        session = await dao_session.select_session_by_user_id_and_session_id(session_request.sessionId, user_id)

        # 2. 메타 데이터 있으면 UPDATE, 없으면 INSERT
        if session:
            chat_id = session['chat_id']
            new_session = False
            await dao_session.update_session_data(session_request.title,
                                                  session_request.workspaceDirectory,
                                                  session_request.sessionId,
                                                  user_id)
        else:
            new_session = True
            # 새로 생성시 chat_id는 DB로 부터 생성된것을 사용
            chat_id = await dao_session.insert_session_data(session_request.title,
                                                            session_request.workspaceDirectory,
                                                            session_request.sessionId,
                                                            user_id)

        # 3. 채팅 히스토리 인서트
        await dao_session_history.merge_session_history(session_request.history,
                                                        chat_id, new_session=new_session)

        # 4. 마지막 세션 데이터 저장 (작업 이어하기 용도)
        await dao_session_history.merge_last_session_info(user_id, session_request.workspaceDirectory, session_request.sessionId)

        return SuccessResponse(
            status="success",
            sessionId=session_request.sessionId
        )

    except Exception as e:
        print(traceback.format_exc())
        logger.error(f"[Save Session Error] {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@session_router.get("/api/sessions", response_model=SessionListResponse)
async def list_sessions(
        http_request: Request,
        limit: int = Query(100, ge=1, le=1000),
        offset: int = Query(0, ge=0),
        current_user: User = Depends(get_current_user)
):
    """
    세션 목록 조회

    Parameters:
    - limit: 최대 조회 개수 (기본: 100)
    - offset: 시작 위치 (기본: 0)

    Returns:
    - sessions: 세션 메타데이터 배열 (최신순)
    """
    # user_id = '7c01e7e1-7f2c-4f7a-b9cf-5f1a1d8700c4'
    user_id = current_user.user_id

    sessions = await dao_session.select_user_session_list(user_id, limit, offset)

    logger.info(f"[List Sessions] User ID: {user_id}, Limit: {limit}, Offset: {offset}")

    sessions = [
        SessionMetadata(
            sessionId=row['session_id'],
            title=row['title'],
            dateCreated=str(row['date_created']),
            workspaceDirectory=row['workspace_directory']
        )
        for row in sessions
    ]

    logger.info(f"sessions length={len(sessions)}")

    return SessionListResponse(sessions=sessions)


@session_router.get("/api/sessions/{session_id}", response_model=SessionDetailResponse)
async def get_session(
        session_id: str,
        http_request: Request,
        current_user: User = Depends(get_current_user)
):
    """
    특정 세션 상세 조회

    Parameters:
    - session_id: 세션 ID

    Returns:
    - sessionId: 세션 ID
    - title: 채팅 제목
    - workspaceDirectory: 작업 디렉토리
    - history: 전체 채팅 메시지 배열
    """
    try:
        user_id = current_user.user_id
        logger.info(f"[Get Session] User ID: {user_id}, Session ID: {session_id}")

        # 1. chat_sessions 테이블에서 session_id와 user_id로 조회
        session = await  dao_session.select_session_by_user_id_and_session_id(session_id, user_id)
        # 2. 없으면 404 에러
        if not session:
            logger.warning(f"[Get Session] Session ID: {session_id}, User ID: {user_id} not found")
            raise HTTPException(status_code=404, detail="Session not found")
        # 3. chat_history 테이블에서 해당 세션의 메시지들을 message_index 순으로 조회
        history_list = await dao_session_history.select_session_history_list(user_id, session_id)

        return SessionDetailResponse(
            sessionId=session_id,
            title=session["title"],
            workspaceDirectory=session["workspace_directory"],
            history=[
                json.loads(row["message_data"])
                for row in history_list
            ]
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
        workspace_directory: str = Query,
        current_user: User = Depends(get_current_user)
):
    """
    마지막 세션 조회(작업 디렉토리 기준)

    Parameters:
    - workspace_directory: 작업 디렉토리

    Returns:
    - sessionId: 세션 ID
    - title: 채팅 제목
    - workspaceDirectory: 작업 디렉토리
    - history: 전체 채팅 메시지 배열
    """
    try:

        user_id = current_user.user_id
        logger.info(f"[Get Session] User ID: {user_id}, workspace_directory: {workspace_directory}")

        # 1. chat_sessions 테이블에서 session_id와 user_id로 조회
        session = await  dao_session.select_last_session_by_user_id_and_workspace_directory(workspace_directory, user_id)

        logger.info(f"session={session}")

        if not session:
            return SessionDetailResponse(
                sessionId=None,
                title='',
                workspaceDirectory=None,
                history=[]
            )
        # 3. chat_history 테이블에서 해당 세션의 메시지들을 message_index 순으로 조회
        session_id = session['session_id']
        history_list = await dao_session_history.select_session_history_list(user_id, session_id)

        return SessionDetailResponse(
            sessionId=session_id,
            title=session["title"],
            workspaceDirectory=session["workspace_directory"],
            history=[
                json.loads(row["message_data"])
                for row in history_list
            ]
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
        current_user: User = Depends(get_current_user)
):
    """
    세션 삭제 (소프트 삭제)

    Parameters:
    - session_id: 삭제할 세션 ID

    Returns:
    - status: "success"
    """
    try:
        user_id = current_user.user_id

        await dao_session.delete_session(session_id, user_id)

        logger.info(f"[Delete Session] User ID: {user_id}, Session ID: {session_id}")

        # 세션이 없으면 404
        # raise HTTPException(status_code=404, detail="Session not found")

        return SuccessResponse(status="success")

    except HTTPException:
        raise
    except Exception as e:
        logger.info(f"[Delete Session Error] {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@session_router.delete("/api/sessions", response_model=SuccessResponse)
async def clear_all_sessions(
        http_request: Request,
        current_user: User = Depends(get_current_user)
):
    """
    모든 세션 삭제 (소프트 삭제)

    Returns:
    - status: "success"
    """
    try:
        user_id = current_user.user_id

        # TODO: 데이터베이스 업데이트 로직
        # UPDATE chat_sessions
        # SET is_deleted = TRUE
        # WHERE user_id = ?

        logger.info(f"[Clear All Sessions] User ID: {user_id}")

        return SuccessResponse(status="success")

    except Exception as e:
        logger.error(f"[Clear All Sessions Error] {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
