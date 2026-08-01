"""Thread CRUD and message history API."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status

from app.api.dependencies import get_thread_service
from app.schemas.message import MessagePage
from app.schemas.thread import ThreadCreate, ThreadPage, ThreadResponse
from app.services.thread_service import ThreadService

router = APIRouter(prefix="/api/threads", tags=["threads"])


@router.post("", response_model=ThreadResponse, status_code=status.HTTP_201_CREATED)
def create_thread(
    service: Annotated[ThreadService, Depends(get_thread_service)],
    request: ThreadCreate | None = None,
) -> ThreadResponse:
    """Create a persisted local conversation."""
    return service.create(request)


@router.get("", response_model=ThreadPage)
def list_threads(
    service: Annotated[ThreadService, Depends(get_thread_service)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> ThreadPage:
    """List conversations by descending activity time."""
    return service.list(page=page, page_size=page_size)


@router.get("/{thread_id}", response_model=ThreadResponse)
def get_thread(
    thread_id: str,
    service: Annotated[ThreadService, Depends(get_thread_service)],
) -> ThreadResponse:
    """Return one conversation."""
    return service.get(thread_id)


@router.get("/{thread_id}/messages", response_model=MessagePage)
def list_messages(
    thread_id: str,
    service: Annotated[ThreadService, Depends(get_thread_service)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> MessagePage:
    """Return an ordered page of persisted messages."""
    return service.list_messages(thread_id=thread_id, page=page, page_size=page_size)


@router.delete("/{thread_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_thread(
    thread_id: str,
    service: Annotated[ThreadService, Depends(get_thread_service)],
) -> Response:
    """Delete one inactive conversation and its directory."""
    service.delete(thread_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
