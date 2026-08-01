"""V1 API-to-database-to-filesystem acceptance workflow."""

import json
from collections.abc import AsyncIterator, Sequence
from typing import cast

import pytest
from app.core.config import Settings
from app.db.database import Database
from app.main import create_app
from app.services.model_client import ModelStreamChunk, ModelToolCallDelta
from app.services.recovery_service import RecoveryReport
from app.tools.base import ToolDefinition
from httpx import ASGITransport, AsyncClient
from langchain_core.messages import BaseMessage, ToolMessage


class WorkflowModel:
    """Deterministic external-model boundary for one complete V1 workflow."""

    def __init__(self) -> None:
        self.turn = 0
        self.file_id: str | None = None

    async def stream(
        self,
        messages: Sequence[BaseMessage],
        tools: Sequence[ToolDefinition],
    ) -> AsyncIterator[ModelStreamChunk]:
        assert {tool.name for tool in tools}.issuperset({"list_files", "read_file", "write_file"})
        self.turn += 1
        if self.turn == 1:
            yield ModelStreamChunk(content="Agent Loop ")
            yield ModelStreamChunk(content="可顺序执行工具。")
            return
        if self.turn == 2:
            yield self._tool_call("call-list", "list_files", {})
            return
        if self.turn == 3:
            assert isinstance(messages[-1], ToolMessage)
            assert self.file_id is not None and self.file_id in str(messages[-1].content)
            yield self._tool_call(
                "call-read",
                "read_file",
                {"file_id": self.file_id, "start_line": 1, "max_lines": 100},
            )
            return
        if self.turn == 4:
            assert isinstance(messages[-1], ToolMessage)
            assert "Alpha requirement" in str(messages[-1].content)
            yield self._tool_call(
                "call-write",
                "write_file",
                {
                    "filename": "analysis.md",
                    "content": "# Analysis\n\n- Alpha requirement verified.\n",
                    "description": "V1 integration report",
                },
            )
            return
        if self.turn == 5:
            assert isinstance(messages[-1], ToolMessage)
            assert "analysis.md" in str(messages[-1].content)
            yield ModelStreamChunk(content="分析完成。报告已生成。")
            return
        raise AssertionError("Unexpected model turn")

    @staticmethod
    def _tool_call(call_id: str, name: str, arguments: dict[str, object]) -> ModelStreamChunk:
        return ModelStreamChunk(
            tool_calls=(
                ModelToolCallDelta(
                    index=0,
                    provider_id=call_id,
                    name=name,
                    arguments=json.dumps(arguments, ensure_ascii=False),
                ),
            )
        )


@pytest.mark.anyio
async def test_complete_v1_workflow_survives_process_restart(
    migrated_settings: Settings,
) -> None:
    """Chat, file analysis, Artifact delivery, isolation, and restart form one closure."""
    model = WorkflowModel()
    app = create_app(migrated_settings)
    app.state.model_client = model
    thread_id: str
    file_id: str
    artifact_id: str

    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client,
    ):
        thread_id = (await client.post("/api/threads")).json()["id"]
        direct = await client.post(
            f"/api/threads/{thread_id}/chat/stream",
            json={"message": "什么是 Agent Loop?"},
        )
        assert direct.status_code == 200
        assert "assistant_delta" in direct.text
        assert '"status":"success"' in direct.text

        upload = await client.post(
            f"/api/threads/{thread_id}/files",
            files={"file": ("requirements.md", b"# Scope\n\nAlpha requirement\n", "text/markdown")},
        )
        assert upload.status_code == 201
        file_id = upload.json()["file"]["id"]
        model.file_id = file_id

        analysis = await client.post(
            f"/api/threads/{thread_id}/chat/stream",
            json={"message": "读取上传文件并生成分析报告", "file_ids": [file_id]},
        )
        assert analysis.status_code == 200
        assert analysis.text.index("tool_start") < analysis.text.index("artifact_created")
        assert "分析完成" in analysis.text
        assert '"status":"success"' in analysis.text

        artifacts = await client.get(f"/api/threads/{thread_id}/artifacts")
        assert artifacts.status_code == 200
        artifact = artifacts.json()["items"][0]
        artifact_id = artifact["id"]
        assert artifact["original_name"] == "analysis.md"
        preview = await client.get(f"/api/threads/{thread_id}/artifacts/{artifact_id}/preview")
        download = await client.get(f"/api/threads/{thread_id}/artifacts/{artifact_id}/download")
        assert preview.status_code == download.status_code == 200
        assert "Alpha requirement verified" in preview.text
        assert download.headers["content-disposition"].startswith("attachment;")

        other_thread_id = (await client.post("/api/threads")).json()["id"]
        denied = await client.get(f"/api/threads/{other_thread_id}/files/{file_id}")
        assert denied.status_code == 403
        assert denied.json()["error"]["code"] == "FILE_ACCESS_DENIED"
        assert migrated_settings.resolved_data_dir.as_posix() not in denied.text

    restarted = create_app(migrated_settings)
    async with (
        restarted.router.lifespan_context(restarted),
        AsyncClient(
            transport=ASGITransport(app=restarted),
            base_url="http://test",
        ) as client,
    ):
        report = cast(RecoveryReport, restarted.state.recovery_report)
        assert report.schema_ready is True
        assert report.cancelled_runs == 0
        assert report.failed_tool_calls == 0
        threads = await client.get("/api/threads")
        messages = await client.get(f"/api/threads/{thread_id}/messages?page_size=100")
        files = await client.get(f"/api/threads/{thread_id}/files?page_size=100")
        artifacts = await client.get(f"/api/threads/{thread_id}/artifacts")
        download = await client.get(f"/api/threads/{thread_id}/artifacts/{artifact_id}/download")
        assert threads.status_code == messages.status_code == files.status_code == 200
        assert artifacts.status_code == download.status_code == 200
        assert len(messages.json()["items"]) == 4
        assert any(item["id"] == file_id for item in files.json()["items"])
        assert artifacts.json()["items"][0]["id"] == artifact_id
        assert "Alpha requirement verified" in download.text

        database = cast(Database, restarted.state.database)
        assert database.is_healthy() is True
