# AgentFlow V1 SSE 协议

## 1. 传输方式

聊天使用 `POST /api/threads/{thread_id}/chat/stream`，前端通过 Fetch
`ReadableStream` 读取 `text/event-stream`。Phase 1 只定义协议，不实现聊天流。

每个事件使用标准 SSE 帧：

```text
id: evt_uuid
event: assistant_delta
data: {"event_id":"evt_uuid","event":"assistant_delta","thread_id":"thread_uuid","run_id":"run_uuid","timestamp":"2026-07-31T15:00:00Z","data":{"content":"正在"}}

```

- 每帧以空行结束。
- `data` 必须是单行 UTF-8 JSON；换行由 JSON 转义。
- SSE `id` 与负载中的 `event_id` 相同。
- 服务端发送的事件名与负载 `event` 相同。

## 2. 通用事件结构

```json
{
  "event_id": "evt_uuid",
  "event": "assistant_delta",
  "thread_id": "thread_uuid",
  "run_id": "run_uuid",
  "timestamp": "2026-07-31T15:00:00Z",
  "data": {}
}
```

同一连接中的事件按生成顺序发送。客户端对已处理的 `event_id` 去重。V1 不承诺
断线重放；断线后客户端通过线程消息和运行记录恢复权威状态。

## 3. 事件定义

### `run_start`

一轮执行已创建并进入运行态，是正常流的第一个事件。

```json
{"status":"running"}
```

### `assistant_start`

助手消息开始生成。一次 run 可以在工具调用前后出现多个模型生成片段，但 V1 对外
只维护一个最终助手消息 ID。

```json
{"message_id":"message_uuid"}
```

### `assistant_delta`

仅包含新产生的文本增量，不重复累计全文。

```json
{"message_id":"message_uuid","content":"正在"}
```

增量可以为空以外的任意 Unicode 文本；客户端按接收顺序拼接。

### `tool_start`

工具开始执行。参数必须经过安全化，不能包含 API Key、服务器路径或大段文件正文。

```json
{
  "tool_call_id":"call_id",
  "tool_name":"web_search",
  "display_name":"正在搜索互联网",
  "arguments":{"query":"Agent 技术趋势"}
}
```

公开 `display_name` 只允许映射为 PRD 中的工具状态，不包含思维链。

### `tool_result`

工具完成、失败、超时或被拒绝。只发送摘要，不发送完整网页/文件正文。

```json
{
  "tool_call_id":"call_id",
  "tool_name":"web_search",
  "success":true,
  "status":"success",
  "summary":"找到 5 条结果",
  "error":null
}
```

失败时 `success=false`，`error` 使用统一安全错误对象：

```json
{"code":"WEB_FETCH_FAILED","message":"网页读取失败","retryable":true}
```

### `artifact_created`

Artifact 已完成写入并持久化。

```json
{
  "file_id":"file_uuid",
  "filename":"分析报告.md",
  "description":"联网研究报告",
  "preview_url":"/api/threads/thread_uuid/artifacts/file_uuid/preview",
  "download_url":"/api/threads/thread_uuid/artifacts/file_uuid/download"
}
```

生成正文不进入该事件；事件只在输出文件和元数据均写入成功后发送。

### `assistant_end`

最终助手消息已完成并持久化。`content` 是权威完整文本，用于校正客户端增量拼接。

```json
{
  "message_id":"message_uuid",
  "content":"完整最终回答",
  "sources":[
    {
      "title":"页面标题",
      "url":"https://example.com/article",
      "snippet":"安全摘要",
      "source_type":"web_page"
    }
  ]
}
```

`sources` 只包含本次 run 的 `web_search`/`web_fetch` 实际结果，并与助手消息
`metadata.sources` 同步持久化；没有来源时为空数组。URL 为经过规范化的 HTTP(S)
地址，不包含服务器路径或内部网络地址。

失败且没有有效助手回答时不发送虚假的 `assistant_end`。

### `run_end`

run 已进入终态，正常情况下是最后一个事件。

```json
{"status":"success","loop_count":3}
```

`status` 为 `success`、`failed`、`cancelled` 或 `max_loops_reached`。

### `error`

模型、工具、流、数据库或服务发生可公开的错误。

```json
{
  "code":"MODEL_REQUEST_FAILED",
  "message":"模型服务暂时不可用",
  "retryable":true,
  "details":{}
}
```

工具级失败通常先发 `tool_result`，Agent 可继续；终止 run 的错误发送 `error`，
随后尽可能发送对应失败状态的 `run_end`。

## 4. 典型顺序

直接回答：

```text
run_start → assistant_start → assistant_delta* → assistant_end → run_end
```

一次工具调用：

```text
run_start → assistant_start → tool_start → tool_result
→ assistant_delta* → assistant_end → run_end
```

Artifact：

```text
... → tool_start(write_file) → artifact_created → tool_result
→ assistant_delta* → assistant_end → run_end
```

终止错误：

```text
run_start → ... → error → run_end(status=failed)
```

## 5. 断连与安全

- 客户端取消读取不代表模型已成功；后端捕获断连并更新 run 终态。
- 断连取消正在执行的工具时，该工具记录以安全失败状态终结；如果进程在更新前退出，
  下次启动恢复会终结工具调用并将 run 标记为 `cancelled`。
- 不通过 SSE 发送完整工具结果、网页正文、文件内容、堆栈或绝对路径。
- 响应设置禁止缓存和代理缓冲的头。
- 前端遇到未知事件应忽略并记录，不中断已知事件解析。
- JSON 解析失败时前端显示协议错误并重新加载该线程的权威历史。
