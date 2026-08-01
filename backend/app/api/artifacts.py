"""Generated Artifact listing, preview, and download API."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response

from app.api.dependencies import get_artifact_service
from app.schemas.file import FilePage
from app.services.artifact_service import ArtifactContent, ArtifactService

router = APIRouter(prefix="/api/threads/{thread_id}/artifacts", tags=["artifacts"])


@router.get("", response_model=FilePage)
def list_artifacts(
    thread_id: str,
    service: Annotated[ArtifactService, Depends(get_artifact_service)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> FilePage:
    """List safe generated-file metadata for one thread."""
    return service.list_page(thread_id=thread_id, page=page, page_size=page_size)


def _artifact_response(result: ArtifactContent) -> Response:
    headers = {
        "Content-Disposition": result.content_disposition,
        "X-Content-Type-Options": "nosniff",
        "Cache-Control": "no-store",
    }
    if result.content_security_policy is not None:
        headers["Content-Security-Policy"] = result.content_security_policy
    return Response(content=result.content, media_type=result.content_type, headers=headers)


@router.get("/{file_id}/preview")
def preview_artifact(
    thread_id: str,
    file_id: str,
    service: Annotated[ArtifactService, Depends(get_artifact_service)],
) -> Response:
    """Return one previewable generated file with hardened response headers."""
    return _artifact_response(service.preview(thread_id=thread_id, file_id=file_id))


@router.get("/{file_id}/download")
def download_artifact(
    thread_id: str,
    file_id: str,
    service: Annotated[ArtifactService, Depends(get_artifact_service)],
) -> Response:
    """Return one generated file as a safe attachment."""
    return _artifact_response(service.download(thread_id=thread_id, file_id=file_id))
