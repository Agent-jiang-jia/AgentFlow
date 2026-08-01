"""Phase 6 generated-file tool and Artifact delivery tests."""

import json
from collections.abc import AsyncIterator, Sequence
from typing import cast

import pytest
from app.core.config import Settings
from app.core.exceptions import (
    ArtifactTooLargeError,
    FileTypeUnsupportedError,
    InvalidFilenameError,
)
from app.db.database import Database
from app.db.models.tool_call import ToolCall
from app.main import create_app
from app.services.artifact_service import ARTIFACT_MIME_TYPES, ArtifactService
from app.services.model_client import ModelStreamChunk, ModelToolCallDelta
from app.storage.file_storage import FileStorage
from app.tools.base import ToolDefinition
from httpx import ASGITransport, AsyncClient
from langchain_core.messages import BaseMessage, ToolMessage
from sqlalchemy import select


def parse_sse(body: str) -> list[dict[str, object]]:
    """Decode test SSE frames into JSON payloads."""
    events: list[dict[str, object]] = []
    for frame in body.strip().split("\n\n"):
        data_line = next(line for line in frame.splitlines() if line.startswith("data: "))
        payload = json.loads(data_line.removeprefix("data: "))
        assert isinstance(payload, dict)
        events.append(payload)
    return events


class ArtifactWritingModel:
    """Generate one Markdown Artifact, then finish from its ToolMessage."""

    def __init__(self) -> None:
        self.call_count = 0

    async def stream(
        self,
        messages: Sequence[BaseMessage],
        tools: Sequence[ToolDefinition],
    ) -> AsyncIterator[ModelStreamChunk]:
        assert any(tool.name == "write_file" for tool in tools)
        if self.call_count == 0:
            self.call_count += 1
            arguments = json.dumps(
                {
                    "filename": "分析报告.md",
                    "content": "# 结论\n\n机密正文不应进入 SSE。",
                    "description": "会话分析报告",
                },
                ensure_ascii=False,
                separators=(",", ":"),
            )
            yield ModelStreamChunk(
                tool_calls=(
                    ModelToolCallDelta(
                        index=0,
                        provider_id="write-call",
                        name="write_file",
                        arguments=arguments,
                    ),
                )
            )
            return
        assert isinstance(messages[-1], ToolMessage)
        assert "分析报告.md" in str(messages[-1].content)
        self.call_count += 1
        yield ModelStreamChunk(content="报告已生成; 可在成果栏预览或下载。")


def make_artifact_service(
    database: Database,
    settings: Settings,
    *,
    max_bytes: int | None = None,
) -> ArtifactService:
    """Create a test service over the real database and controlled filesystem."""
    return ArtifactService(
        database=database,
        storage=FileStorage(settings.resolved_data_dir),
        max_artifact_bytes=max_bytes or settings.max_artifact_size_mb * 1024 * 1024,
        frame_ancestors=tuple(settings.cors_origins),
    )


@pytest.mark.anyio
async def test_write_file_emits_artifact_and_delivers_safe_preview_download(
    migrated_settings: Settings,
) -> None:
    """The full Agent loop creates metadata before its safe public SSE event."""
    app = create_app(migrated_settings)
    app.state.model_client = ArtifactWritingModel()
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client,
    ):
        thread_id = (await client.post("/api/threads")).json()["id"]
        chat = await client.post(
            f"/api/threads/{thread_id}/chat/stream",
            json={"message": "生成报告"},
        )
        events = parse_sse(chat.text)
        artifact_event = next(event for event in events if event["event"] == "artifact_created")
        artifact_data = cast(dict[str, object], artifact_event["data"])
        file_id = cast(str, artifact_data["file_id"])
        listing = await client.get(f"/api/threads/{thread_id}/artifacts")
        preview = await client.get(f"/api/threads/{thread_id}/artifacts/{file_id}/preview")
        download = await client.get(f"/api/threads/{thread_id}/artifacts/{file_id}/download")

    event_names = [event["event"] for event in events]
    assert event_names.index("tool_start") < event_names.index("artifact_created")
    assert event_names.index("artifact_created") < event_names.index("tool_result")
    assert "机密正文" not in chat.text
    assert artifact_data == {
        "file_id": file_id,
        "filename": "分析报告.md",
        "description": "会话分析报告",
        "preview_url": f"/api/threads/{thread_id}/artifacts/{file_id}/preview",
        "download_url": f"/api/threads/{thread_id}/artifacts/{file_id}/download",
    }
    assert listing.status_code == 200
    assert listing.json()["total"] == 1
    assert listing.json()["items"][0]["description"] == "会话分析报告"
    assert "stored_path" not in listing.text
    assert preview.status_code == 200
    assert preview.headers["content-type"].startswith("text/markdown")
    assert preview.headers["x-content-type-options"] == "nosniff"
    assert preview.headers["cache-control"] == "no-store"
    assert preview.text == "# 结论\n\n机密正文不应进入 SSE。"
    assert download.status_code == 200
    assert download.headers["content-disposition"].startswith("attachment;")
    assert "filename*=UTF-8''" in download.headers["content-disposition"]
    assert str(migrated_settings.resolved_data_dir) not in chat.text + listing.text

    database = cast(Database, app.state.database)
    with database.session_factory() as session:
        call = session.scalar(select(ToolCall).where(ToolCall.tool_name == "write_file"))
        assert call is not None
        assert call.arguments_json == {
            "filename": "分析报告.md",
            "description": "会话分析报告",
        }
        assert "机密正文" not in json.dumps(call.arguments_json, ensure_ascii=False)


@pytest.mark.anyio
async def test_html_preview_has_strict_csp_and_cross_thread_access_is_denied(
    migrated_settings: Settings,
) -> None:
    """HTML remains isolated and foreign Artifact identifiers reveal no ownership."""
    app = create_app(migrated_settings)
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client,
    ):
        owner = (await client.post("/api/threads")).json()["id"]
        other = (await client.post("/api/threads")).json()["id"]
        database = cast(Database, app.state.database)
        artifact = make_artifact_service(database, migrated_settings).write(
            thread_id=owner,
            filename="页面.html",
            content="<script>top.location='https://bad.example'</script><p>安全预览</p>",
            description=None,
        )
        preview = await client.get(f"/api/threads/{owner}/artifacts/{artifact.id}/preview")
        foreign = await client.get(f"/api/threads/{other}/artifacts/{artifact.id}/preview")

    policy = preview.headers["content-security-policy"]
    assert preview.headers["content-type"].startswith("text/html")
    assert "default-src 'none'" in policy
    assert "script-src" not in policy
    assert "frame-ancestors 'self' http://localhost:5173" in policy
    assert foreign.status_code == 403
    assert foreign.json()["error"]["code"] == "FILE_ACCESS_DENIED"
    assert owner not in foreign.text
    assert "安全预览" not in foreign.text


@pytest.mark.anyio
async def test_artifact_names_types_collisions_and_size_are_enforced(
    migrated_settings: Settings,
) -> None:
    """All approved types work while unsafe names, types, and byte overflow fail."""
    app = create_app(migrated_settings)
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client,
    ):
        thread_id = (await client.post("/api/threads")).json()["id"]
        database = cast(Database, app.state.database)
        service = make_artifact_service(database, migrated_settings)
        created = [
            service.write(
                thread_id=thread_id,
                filename=f"result{extension}",
                content="content",
                description=None,
            )
            for extension in ARTIFACT_MIME_TYPES
        ]
        duplicate = service.write(
            thread_id=thread_id,
            filename="result.md",
            content="new content",
            description=None,
        )
        previews = [
            await client.get(f"/api/threads/{thread_id}/artifacts/{artifact.id}/preview")
            for artifact in created
        ]
        deleted = await client.delete(f"/api/threads/{thread_id}/files/{duplicate.id}")
        remaining = await client.get(f"/api/threads/{thread_id}/artifacts")

    assert duplicate.original_name == "result (2).md"
    assert all(response.status_code == 200 for response in previews)
    assert deleted.status_code == 204
    assert remaining.json()["total"] == len(created)
    for artifact, response in zip(created, previews, strict=True):
        assert response.headers["content-type"].startswith(
            ARTIFACT_MIME_TYPES[artifact.extension or ""]
        )

    with pytest.raises(InvalidFilenameError):
        service.write(
            thread_id=thread_id,
            filename="../escape.md",
            content="blocked",
            description=None,
        )
    with pytest.raises(InvalidFilenameError):
        service.write(
            thread_id=thread_id,
            filename="CON.txt",
            content="blocked",
            description=None,
        )
    with pytest.raises(FileTypeUnsupportedError):
        service.write(
            thread_id=thread_id,
            filename="payload.exe",
            content="blocked",
            description=None,
        )
    with pytest.raises(ArtifactTooLargeError):
        make_artifact_service(database, migrated_settings, max_bytes=4).write(
            thread_id=thread_id,
            filename="large.txt",
            content="中文",
            description=None,
        )
    outputs = migrated_settings.resolved_data_dir / "threads" / thread_id / "outputs"
    assert len(list(outputs.iterdir())) == len(created)
