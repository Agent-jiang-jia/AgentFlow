# AgentFlow V1 API 规范

## 1. 通用约定

- API 基础地址由部署环境决定，业务接口统一使用 `/api` 前缀。
- 请求和响应使用 UTF-8 JSON；文件上传使用 `multipart/form-data`。
- 时间使用 ISO 8601 UTC（示例：`2026-07-31T15:00:00Z`）。
- ID 为服务端生成的 UUID 字符串，客户端将其作为不透明值处理。
- 分页从 1 开始，默认 `page=1&page_size=20`，`page_size` 最大 100。
- 除下载和 SSE 外，成功响应直接返回资源或分页对象。
- Phase 1 只实现 `GET /health`；其余接口均为后续 Phase 的计划契约。

## 2. 健康检查

### `GET /health`（Phase 1）

成功 `200`：

```json
{
  "status": "healthy",
  "service": "agentflow-api",
  "version": "0.1.0",
  "database": "ok"
}
```

数据库不可用时返回 `503` 和统一错误响应。健康检查执行轻量 `SELECT 1`，
不创建或修改数据库结构。

## 3. 会话接口（Phase 2）

### `POST /api/threads`

请求体可省略；也可提供：

```json
{"title": "新会话"}
```

`title` 去除首尾空白后长度为 1 到 200。成功返回 `201`：

```json
{
  "id": "thread_uuid",
  "title": "新会话",
  "status": "active",
  "created_at": "2026-07-31T15:00:00Z",
  "updated_at": "2026-07-31T15:00:00Z"
}
```

副作用：创建数据库记录和线程的 `uploads`、`parsed`、`outputs` 目录。

### `GET /api/threads`

查询参数：`page`、`page_size`。按 `updated_at DESC, id DESC` 排序。

```json
{
  "items": [],
  "page": 1,
  "page_size": 20,
  "total": 0
}
```

### `GET /api/threads/{thread_id}`

返回单个线程。不存在返回 `404 THREAD_NOT_FOUND`。

### `GET /api/threads/{thread_id}/messages`

查询参数：`page`、`page_size`，按 `sequence_number ASC` 返回。

```json
{
  "items": [
    {
      "id": "message_uuid",
      "thread_id": "thread_uuid",
      "run_id": null,
      "role": "user",
      "content": "你好",
      "message_type": "text",
      "metadata": {},
      "sequence_number": 1,
      "created_at": "2026-07-31T15:00:00Z"
    }
  ],
  "page": 1,
  "page_size": 20,
  "total": 1
}
```

助手消息使用 `metadata.sources` 恢复该 run 实际使用的联网来源；无来源消息返回空
对象。`source_type` 为 `search` 或 `web_page`，同一 run 的相同规范化 URL 只展示
一次，成功抓取后优先展示 `web_page` 信息。

### `DELETE /api/threads/{thread_id}`

成功返回 `204`。运行中的线程返回 `409 THREAD_BUSY`。删除数据库关联记录与线程
目录；不存在返回 `404 THREAD_NOT_FOUND`。

## 4. 流式聊天接口（Phase 2/3）

### `POST /api/threads/{thread_id}/chat/stream`

请求：

```json
{
  "message": "根据上传文件生成报告",
  "file_ids": ["file_uuid"]
}
```

- `message` 去除首尾空白后长度 1 到 20,000。
- `file_ids` 默认空列表，去重后最多 20 个，且必须属于当前线程。
- 同一线程已有 `pending` 或 `running` run 时返回 `409 THREAD_BUSY`。
- 成功响应为 `200 Content-Type: text/event-stream; charset=utf-8`。
- 禁止缓存，建议 `Cache-Control: no-cache` 和 `X-Accel-Buffering: no`。

事件结构见 `docs/SSE_PROTOCOL.md`。在首个 SSE 事件发出之前发现的 HTTP 级错误
使用统一 JSON 错误；流开始后的错误使用 `error` 事件，并尽可能以 `run_end` 收尾。

## 5. 文件接口（Phase 5）

### `POST /api/threads/{thread_id}/files`

`multipart/form-data`，字段 `file`，每次请求上传一个文件。客户端上传多个文件时
逐个请求。支持 `.pdf`、`.docx`、`.txt`、`.md`、`.csv`。

成功返回 `201`：

```json
{
  "file": {
    "id": "file_uuid",
    "thread_id": "thread_uuid",
    "source_file_id": null,
    "category": "upload",
    "original_name": "需求.pdf",
    "extension": ".pdf",
    "mime_type": "application/pdf",
    "size_bytes": 1024,
    "parse_status": "success",
    "parsed_file_id": "parsed_file_uuid",
    "created_at": "2026-07-31T15:00:00Z"
  }
}
```

解析可在请求内同步完成。扫描 PDF 返回成功的上传资源，但
`parse_status=unsupported_ocr`，并提供不支持 OCR 的安全提示。

### `GET /api/threads/{thread_id}/files`

查询参数：`category=all|upload|parsed|artifact`（默认 `all`）、`page`、
`page_size`。只返回当前线程元数据，不返回 `stored_path`。

### `GET /api/threads/{thread_id}/files/{file_id}`

返回文件元数据。文件不存在返回 `FILE_NOT_FOUND`；存在但不属于当前线程统一返回
`403 FILE_ACCESS_DENIED`，不得泄露其真实归属。

### `DELETE /api/threads/{thread_id}/files/{file_id}`

成功返回 `204`。删除元数据及受控文件；上传源文件删除时同步删除关联解析文件。

## 6. Artifact 接口（Phase 6）

### `GET /api/threads/{thread_id}/artifacts`

返回当前线程中 `category=artifact` 的分页文件列表。

### `GET /api/threads/{thread_id}/artifacts/{file_id}/preview`

- Markdown/TXT/JSON/代码/YAML：返回 UTF-8 文本及正确 Content-Type。
- CSV：返回 UTF-8 CSV，由前端解析为表格。
- HTML：返回 `text/html`，同时设置严格 CSP；前端仅放入带 `sandbox` 的 iframe。
- 不支持预览的类型返回 `415 FILE_TYPE_UNSUPPORTED`。

### `GET /api/threads/{thread_id}/artifacts/{file_id}/download`

以附件下载，使用安全的 `Content-Disposition`。响应不暴露服务器文件路径。

## 7. 统一错误响应

```json
{
  "error": {
    "code": "THREAD_NOT_FOUND",
    "message": "会话不存在",
    "retryable": false,
    "details": {},
    "request_id": "request_uuid"
  }
}
```

- `code`：稳定机器码。
- `message`：可向用户展示的安全文本。
- `retryable`：客户端是否可在不修改请求的情况下重试。
- `details`：可选、安全、结构化字段；生产响应不包含堆栈、路径、密钥或数据库信息。
- `request_id`：用于关联日志，不等同于 run ID。

### 状态码映射

| HTTP | 错误码 |
|---|---|
| 400 | `MESSAGE_EMPTY`, `INVALID_FILENAME`, `URL_NOT_ALLOWED` |
| 403 | `FILE_ACCESS_DENIED` |
| 404 | `THREAD_NOT_FOUND`, `FILE_NOT_FOUND`, `TOOL_NOT_FOUND` |
| 409 | `THREAD_BUSY`, `DUPLICATE_TOOL_CALL` |
| 413 | `FILE_TOO_LARGE`, `ARTIFACT_TOO_LARGE` |
| 415 | `FILE_TYPE_UNSUPPORTED` |
| 422 | `TOOL_ARGUMENT_INVALID` 或请求模型校验失败 |
| 500 | `FILE_PARSE_FAILED`, `TOOL_EXECUTION_FAILED`, `INTERNAL_ERROR` |
| 502 | `MODEL_REQUEST_FAILED`, `WEB_SEARCH_FAILED`, `WEB_FETCH_FAILED` |
| 503 | `DATABASE_UNAVAILABLE` |
| 504 | `TOOL_TIMEOUT` |

`MAX_AGENT_LOOPS_REACHED` 和 `OCR_NOT_SUPPORTED` 通常作为成功流中的结构化业务
结果/SSE 错误，不用于覆盖已经开始的 HTTP 200 流。

V1 正式错误码集合：

`THREAD_NOT_FOUND`、`THREAD_BUSY`、`MESSAGE_EMPTY`、`MODEL_REQUEST_FAILED`、
`MAX_AGENT_LOOPS_REACHED`、`TOOL_NOT_FOUND`、`TOOL_ARGUMENT_INVALID`、
`TOOL_EXECUTION_FAILED`、`TOOL_TIMEOUT`、`DUPLICATE_TOOL_CALL`、
`FILE_NOT_FOUND`、`FILE_ACCESS_DENIED`、`FILE_TYPE_UNSUPPORTED`、
`FILE_TOO_LARGE`、`FILE_PARSE_FAILED`、`OCR_NOT_SUPPORTED`、
`INVALID_FILENAME`、`ARTIFACT_TOO_LARGE`、`URL_NOT_ALLOWED`、
`WEB_SEARCH_FAILED`、`WEB_FETCH_FAILED`、`DATABASE_UNAVAILABLE`、
`REQUEST_VALIDATION_ERROR`、`INTERNAL_ERROR`。
