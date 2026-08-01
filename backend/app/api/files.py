"""Thread-owned upload and file metadata API."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, UploadFile, status
from fastapi import File as FormFile

from app.api.dependencies import get_file_service
from app.schemas.file import FileCategoryFilter, FilePage, FileResponse, FileUploadResponse
from app.services.file_service import FileService

router = APIRouter(prefix="/api/threads/{thread_id}/files", tags=["files"])


@router.post("", response_model=FileUploadResponse, status_code=status.HTTP_201_CREATED)
def upload_file(
    thread_id: str,
    file: Annotated[UploadFile, FormFile()],
    service: Annotated[FileService, Depends(get_file_service)],
) -> FileUploadResponse:
    """Upload and synchronously parse one supported file."""
    result = service.upload(
        thread_id=thread_id,
        filename=file.filename,
        mime_type=file.content_type,
        stream=file.file,
    )
    return FileUploadResponse(file=result)


@router.get("", response_model=FilePage)
def list_files(
    thread_id: str,
    service: Annotated[FileService, Depends(get_file_service)],
    category: Annotated[FileCategoryFilter, Query()] = "all",
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> FilePage:
    """List safe file metadata for one thread."""
    return service.list_page(
        thread_id=thread_id,
        category=category,
        page=page,
        page_size=page_size,
    )


@router.get("/{file_id}", response_model=FileResponse)
def get_file(
    thread_id: str,
    file_id: str,
    service: Annotated[FileService, Depends(get_file_service)],
) -> FileResponse:
    """Return one thread-owned file metadata record."""
    return service.get(thread_id=thread_id, file_id=file_id)


@router.delete("/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_file(
    thread_id: str,
    file_id: str,
    service: Annotated[FileService, Depends(get_file_service)],
) -> Response:
    """Delete an upload and its parsed derivative from metadata and disk."""
    service.delete(thread_id=thread_id, file_id=file_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
