"""Plain streaming chat API."""

from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.api.dependencies import get_chat_service
from app.schemas.chat import ChatRequest
from app.services.chat_service import ChatService

router = APIRouter(prefix="/api/threads", tags=["chat"])


@router.post("/{thread_id}/chat/stream")
def stream_chat(
    thread_id: str,
    request: ChatRequest,
    service: Annotated[ChatService, Depends(get_chat_service)],
) -> StreamingResponse:
    """Persist user input and stream a direct model response over SSE."""
    prepared = service.prepare(thread_id=thread_id, request=request)
    return StreamingResponse(
        service.stream(prepared),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
