"""Phase 5 file API, isolation, and Agent tool-loop tests."""

import json
from collections.abc import AsyncIterator, Sequence
from io import BytesIO
from typing import cast
from zipfile import ZipFile

import fitz  # type: ignore[import-untyped]  # PyMuPDF has no typing metadata.
import pytest
from app.core.config import Settings
from app.db.database import Database
from app.db.models.file import File
from app.main import create_app
from app.services.model_client import ModelStreamChunk, ModelToolCallDelta
from app.tools.base import ToolDefinition
from httpx import ASGITransport, AsyncClient
from langchain_core.messages import BaseMessage, ToolMessage
from sqlalchemy import func, select


def parse_sse(body: str) -> list[dict[str, object]]:
    """Decode test SSE frames into JSON payloads."""
    events: list[dict[str, object]] = []
    for frame in body.strip().split("\n\n"):
        data_line = next(line for line in frame.splitlines() if line.startswith("data: "))
        payload = json.loads(data_line.removeprefix("data: "))
        assert isinstance(payload, dict)
        events.append(payload)
    return events


def tool_chunk(call_id: str, name: str, arguments: dict[str, object]) -> ModelToolCallDelta:
    """Create one complete model function call."""
    return ModelToolCallDelta(
        index=0,
        provider_id=call_id,
        name=name,
        arguments=json.dumps(arguments, ensure_ascii=False, separators=(",", ":")),
    )


class FileReadingModel:
    """List files, read the upload, then answer from the actual ToolMessage."""

    def __init__(self, file_id: str) -> None:
        self.file_id = file_id
        self.call_count = 0

    async def stream(
        self,
        messages: Sequence[BaseMessage],
        tools: Sequence[ToolDefinition],
    ) -> AsyncIterator[ModelStreamChunk]:
        names = {tool.name for tool in tools}
        assert {"list_files", "read_file"}.issubset(names)
        if self.call_count == 0:
            self.call_count += 1
            yield ModelStreamChunk(tool_calls=(tool_chunk("list-call", "list_files", {}),))
            return
        if self.call_count == 1:
            assert isinstance(messages[-1], ToolMessage)
            assert self.file_id in str(messages[-1].content)
            self.call_count += 1
            yield ModelStreamChunk(
                tool_calls=(
                    tool_chunk(
                        "read-call",
                        "read_file",
                        {"file_id": self.file_id, "max_chars": 2_000},
                    ),
                )
            )
            return
        assert isinstance(messages[-1], ToolMessage)
        assert "真实上传内容" in str(messages[-1].content)
        self.call_count += 1
        yield ModelStreamChunk(content="已读取并分析上传文件。")


class ForeignFileModel:
    """Attempt a foreign read so the tool boundary can be observed."""

    def __init__(self, file_id: str) -> None:
        self.file_id = file_id
        self.call_count = 0

    async def stream(
        self,
        messages: Sequence[BaseMessage],
        tools: Sequence[ToolDefinition],
    ) -> AsyncIterator[ModelStreamChunk]:
        assert any(tool.name == "read_file" for tool in tools)
        if self.call_count == 0:
            self.call_count += 1
            yield ModelStreamChunk(
                tool_calls=(tool_chunk("foreign-read", "read_file", {"file_id": self.file_id}),)
            )
            return
        assert isinstance(messages[-1], ToolMessage)
        assert "FILE_ACCESS_DENIED" in str(messages[-1].content)
        self.call_count += 1
        yield ModelStreamChunk(content="无法读取其他会话的文件。")


@pytest.mark.anyio
async def test_txt_upload_lists_gets_and_cascade_deletes(
    migrated_settings: Settings,
) -> None:
    """A successful upload creates isolated source/parsed files and safe metadata."""
    app = create_app(migrated_settings)
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client,
    ):
        thread_id = (await client.post("/api/threads")).json()["id"]
        uploaded = await client.post(
            f"/api/threads/{thread_id}/files",
            files={"file": ("资料.txt", "真实上传内容\n第二行".encode(), "text/plain")},
        )
        payload = uploaded.json()["file"]
        listing = await client.get(f"/api/threads/{thread_id}/files")
        upload_only = await client.get(
            f"/api/threads/{thread_id}/files", params={"category": "upload"}
        )
        detail = await client.get(f"/api/threads/{thread_id}/files/{payload['id']}")

        assert uploaded.status_code == 201
        assert payload["parse_status"] == "success"
        assert payload["parsed_file_id"] is not None
        assert "stored_path" not in uploaded.text
        assert listing.json()["total"] == 2
        assert upload_only.json()["total"] == 1
        assert detail.json() == payload

        thread_root = migrated_settings.resolved_data_dir / "threads" / thread_id
        upload_paths = list((thread_root / "uploads").iterdir())
        parsed_paths = list((thread_root / "parsed").iterdir())
        assert len(upload_paths) == len(parsed_paths) == 1
        assert upload_paths[0].name.startswith(f"{payload['id']}_")
        assert parsed_paths[0].name.startswith(f"{payload['parsed_file_id']}_")
        assert "真实上传内容" in parsed_paths[0].read_text(encoding="utf-8")

        deleted = await client.delete(f"/api/threads/{thread_id}/files/{payload['id']}")
        assert deleted.status_code == 204
        assert not upload_paths[0].exists()
        assert not parsed_paths[0].exists()
        assert (await client.get(f"/api/threads/{thread_id}/files")).json()["total"] == 0


@pytest.mark.anyio
async def test_upload_validation_size_empty_mime_and_actual_format(
    migrated_settings: Settings,
) -> None:
    """Unsafe name, type mismatch, empty content, and size overflow fail safely."""
    app = create_app(migrated_settings.model_copy(update={"max_upload_size_mb": 1}))
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client,
    ):
        thread_id = (await client.post("/api/threads")).json()["id"]
        cases = [
            (("../secret.txt", b"content", "text/plain"), 400, "INVALID_FILENAME"),
            (("CON.txt", b"content", "text/plain"), 400, "INVALID_FILENAME"),
            (("notes.exe", b"content", "application/octet-stream"), 415, "FILE_TYPE_UNSUPPORTED"),
            (("fake.pdf", b"not a pdf", "application/pdf"), 415, "FILE_TYPE_UNSUPPORTED"),
            (("notes.txt", b"content", "application/pdf"), 415, "FILE_TYPE_UNSUPPORTED"),
            (("empty.txt", b"", "text/plain"), 500, "FILE_PARSE_FAILED"),
            (("large.txt", b"x" * (1024 * 1024 + 1), "text/plain"), 413, "FILE_TOO_LARGE"),
        ]
        for file_tuple, expected_status, expected_code in cases:
            response = await client.post(
                f"/api/threads/{thread_id}/files",
                files={"file": file_tuple},
            )
            assert response.status_code == expected_status
            assert response.json()["error"]["code"] == expected_code
            assert str(migrated_settings.resolved_data_dir) not in response.text

        assert (await client.get(f"/api/threads/{thread_id}/files")).json()["total"] == 0


@pytest.mark.anyio
async def test_scanned_pdf_is_preserved_with_unsupported_ocr_status(
    migrated_settings: Settings,
) -> None:
    """A page-bearing blank PDF is not represented as successfully parsed text."""
    document = fitz.open()
    document.new_page()
    payload = document.tobytes()
    document.close()
    app = create_app(migrated_settings)
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client,
    ):
        thread_id = (await client.post("/api/threads")).json()["id"]
        response = await client.post(
            f"/api/threads/{thread_id}/files",
            files={"file": ("scan.pdf", payload, "application/pdf")},
        )
        listing = await client.get(f"/api/threads/{thread_id}/files")
    assert response.status_code == 201
    assert response.json()["file"]["parse_status"] == "unsupported_ocr"
    assert response.json()["file"]["parsed_file_id"] is None
    assert listing.json()["total"] == 1


@pytest.mark.anyio
async def test_parse_failure_keeps_safe_failed_metadata(migrated_settings: Settings) -> None:
    """A structurally identified but unreadable DOCX remains visible as a failed upload."""
    archive_bytes = BytesIO()
    with ZipFile(archive_bytes, "w") as archive:
        archive.writestr("[Content_Types].xml", "not valid package XML")
        archive.writestr("word/document.xml", "not valid document XML")

    app = create_app(migrated_settings)
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client,
    ):
        thread_id = (await client.post("/api/threads")).json()["id"]
        response = await client.post(
            f"/api/threads/{thread_id}/files",
            files={
                "file": (
                    "broken.docx",
                    archive_bytes.getvalue(),
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                )
            },
        )
        listing = await client.get(f"/api/threads/{thread_id}/files", params={"category": "upload"})

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "FILE_PARSE_FAILED"
    assert listing.json()["total"] == 1
    failed = listing.json()["items"][0]
    assert failed["parse_status"] == "failed"
    assert failed["parse_error"] == "文件解析失败"
    assert failed["parsed_file_id"] is None
    assert str(migrated_settings.resolved_data_dir) not in response.text


@pytest.mark.anyio
async def test_cross_thread_metadata_and_agent_read_are_denied(
    migrated_settings: Settings,
) -> None:
    """A foreign opaque ID yields access denied without exposing content or ownership."""
    app = create_app(migrated_settings)
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client,
    ):
        owner = (await client.post("/api/threads")).json()["id"]
        other = (await client.post("/api/threads")).json()["id"]
        upload = await client.post(
            f"/api/threads/{owner}/files",
            files={"file": ("private.txt", b"confidential-value", "text/plain")},
        )
        file_id = upload.json()["file"]["id"]
        detail = await client.get(f"/api/threads/{other}/files/{file_id}")
        attached = await client.post(
            f"/api/threads/{other}/chat/stream",
            json={"message": "读取文件", "file_ids": [file_id]},
        )
        app.state.model_client = ForeignFileModel(file_id)
        tool_attempt = await client.post(
            f"/api/threads/{other}/chat/stream",
            json={"message": "尝试读取指定文件"},
        )
    assert detail.status_code == 403
    assert detail.json()["error"]["code"] == "FILE_ACCESS_DENIED"
    assert attached.status_code == 403
    assert "confidential-value" not in attached.text
    assert owner not in attached.text
    events = parse_sse(tool_attempt.text)
    result = next(event for event in events if event["event"] == "tool_result")
    assert cast(dict[str, object], result["data"])["error"] == {
        "code": "FILE_ACCESS_DENIED",
        "message": "无权访问该文件",
        "retryable": False,
    }
    assert "confidential-value" not in tool_attempt.text
    assert str(migrated_settings.resolved_data_dir) not in tool_attempt.text


@pytest.mark.anyio
async def test_agent_lists_and_reads_uploaded_file_through_full_loop(
    migrated_settings: Settings,
) -> None:
    """The Phase 5 tools return parsed content to the model and only summaries to SSE."""
    app = create_app(migrated_settings)
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client,
    ):
        thread_id = (await client.post("/api/threads")).json()["id"]
        upload = await client.post(
            f"/api/threads/{thread_id}/files",
            files={"file": ("analysis.txt", b"real content placeholder", "text/plain")},
        )
        file_id = upload.json()["file"]["id"]
        parsed_id = upload.json()["file"]["parsed_file_id"]
        parsed_path = next(
            (migrated_settings.resolved_data_dir / "threads" / thread_id / "parsed").iterdir()
        )
        parsed_path.write_text("# 文件: analysis.txt\n\n真实上传内容\n", encoding="utf-8")
        app.state.model_client = FileReadingModel(file_id)
        response = await client.post(
            f"/api/threads/{thread_id}/chat/stream",
            json={"message": "请分析这个文件", "file_ids": [file_id]},
        )
        events = parse_sse(response.text)

    assert response.status_code == 200
    assert [event["event"] for event in events].count("tool_start") == 2
    results = [event for event in events if event["event"] == "tool_result"]
    assert all(cast(dict[str, object], event["data"])["success"] is True for event in results)
    assert "真实上传内容" not in response.text
    assert str(parsed_path) not in response.text
    assert parsed_id not in response.text
    assert cast(dict[str, object], events[-1]["data"])["status"] == "success"

    database = cast(Database, app.state.database)
    with database.session_factory() as session:
        assert session.scalar(select(func.count()).select_from(File)) == 2
