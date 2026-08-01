# AgentFlow V1 系统架构

## 1. 架构目标与边界

AgentFlow V1 是单用户、本地部署的轻量级单 Agent Web 工作台。正式需求以
`docs/PRD.md` 为准，系统只覆盖对话与流式输出、单主 Agent 工具循环、Web
搜索与正文读取、文件上传/解析/读取/生成、SQLite 持久化和简单 Web 工作台。

V1 采用一个 React 前端、一个 FastAPI 后端、一个 SQLite 数据库和一个本地
数据目录。它不是微服务平台、任务调度平台、RAG 系统或多 Agent 框架。

## 2. 总体架构

```text
React + TypeScript + Ant Design
  ├─ REST：会话、消息、文件、Artifact
  └─ POST + Fetch ReadableStream：聊天 SSE
                     │
                     ▼
FastAPI 单体应用
  ├─ API：协议、校验、状态码、流式响应
  ├─ Service：业务编排和事务边界
  ├─ Repository：SQLAlchemy 2 数据访问
  ├─ Agent Runtime：LangGraph 单 Agent 循环
  ├─ Tool Registry：工具注册、参数校验和调用
  ├─ Parser Registry：文件格式到统一文本的转换
  └─ Storage：线程目录、文件名和路径安全
          │                         │
          ▼                         ▼
      SQLite                   本地文件系统
  结构化记录与关联          uploads/parsed/outputs
```

## 3. 前后端职责

### 3.1 前端

- 展示会话列表、消息、公开工具状态、来源、文件和 Artifact。
- 通过 REST 完成非流式资源操作。
- 通过 `POST` 请求和 `ReadableStream` 消费 SSE，不使用原生 `EventSource`。
- 维护界面状态和当前流式内容，不保存权威业务数据。
- 不展示模型私有思维链；工具结果只展示安全摘要。
- HTML Artifact 仅在受限 `iframe` 中预览。

### 3.2 后端

- 作为所有业务数据、文件访问和执行状态的权威来源。
- 校验请求、执行事务、控制同一线程并发、持久化运行记录。
- 将模型、工具、解析器和存储异常转换为稳定的公开错误。
- 负责 SSRF、路径穿越、跨线程文件访问和敏感信息泄露防护。
- 生成 SSE 事件并保证终止事件与数据库中的 run 状态一致。

API 层只处理传输协议和依赖注入，不直接编写数据库业务逻辑。

## 4. Agent Runtime 职责

Agent Runtime 在 Phase 3 引入，职责严格限定为：

- 从当前线程加载有序消息和可访问文件摘要。
- 调用绑定 V1 工具的单一模型。
- 根据模型的 tool call 在 `assistant` 与 `tools` 两个 LangGraph 节点间循环。
- 执行工具参数校验、超时、重复调用检测和最大 10 次循环保护。
- 将工具结果作为 `ToolMessage` 返回模型。
- 发出公开 SSE 事件并保存 run、消息和工具调用记录。

Runtime 不创建子 Agent，不并行拆分子任务，不提供 Plan/Todo、Skills、MCP、
长期记忆或动态模型切换。

## 5. 数据库和文件系统职责

### 5.1 SQLite

SQLite 保存 `threads`、`messages`、`runs`、`tool_calls`、`files`、`sources`。
数据库保存关联、状态和相对存储路径，不保存上传文件或 Artifact 正文。
数据库结构只由 Alembic 迁移管理，应用启动不调用 `create_all()`。

### 5.2 本地文件系统

数据根目录默认是 `backend/data`，可通过环境变量覆盖。数据库文件和线程文件
目录分别为：

```text
data/
├── agentflow.db
└── threads/
    └── {thread_id}/
        ├── uploads/
        ├── parsed/
        └── outputs/
```

数据库中的 `stored_path` 使用相对于数据根目录的 POSIX 风格路径，便于迁移，
运行时再由 `pathlib.Path` 解析。任何来自请求或模型的值都不能直接拼接为路径。

## 6. 目录隔离方案

- `thread_id` 和 `file_id` 由后端生成，使用 UUID 字符串。
- 每个线程只能访问 `data/threads/{thread_id}` 下的三个固定子目录。
- 实际文件名使用 `{file_id}_{safe_filename}`，保留用户可见原名作为元数据。
- 读取工具只接收 `file_id`；写入工具只接收不含目录分隔符的文件名。
- 每次文件访问同时校验数据库所属 `thread_id` 和解析后的路径仍位于线程目录。
- API、SSE 和错误响应只返回逻辑 ID、原始文件名和 API URL，不返回服务器路径。
- 删除线程时由 Service 协调数据库事务和线程目录删除；具体失败补偿在 Phase 7
  完善并测试。

## 7. 模块依赖关系

```text
main
 ├─ core.config / core.logging / core.exceptions
 ├─ api
 │   └─ services
 │       ├─ repositories ── db.models / db.database
 │       ├─ agent ── tools
 │       ├─ parsers
 │       └─ storage
 └─ middleware
```

依赖只从外层指向内层。Repository 不依赖 API；Tool 和 Parser 不直接操作前端
协议；Storage 不查询业务数据。Phase 1 只落地配置、日志、异常、数据库基础、
数据模型、迁移和健康检查所需的最小模块。

## 8. 请求调用链

### 8.1 Phase 1 健康检查

```text
GET /health
→ health API
→ database health service
→ SELECT 1
→ 200 healthy 或 503 DATABASE_UNAVAILABLE
```

### 8.2 V1 完整聊天链（后续 Phase）

```text
POST /api/threads/{thread_id}/chat/stream
→ 校验线程、消息和线程运行锁
→ 保存 user message，创建 run
→ 发送 run_start
→ LangGraph assistant
   ├─ 无工具：流式回答
   └─ 有工具：记录并执行工具 → ToolMessage → assistant
→ 保存 assistant message / files / sources / tool_calls
→ 发送 assistant_end、run_end
→ 释放线程运行锁
```

## 9. 最简单可靠的技术决策

- 单进程 FastAPI 单体应用，使用同步 SQLAlchemy Session；Agent 与网络工具保持
  异步，避免为本地 SQLite 引入不必要的异步数据库驱动。
- SQLite 启用 foreign keys、busy timeout 和 WAL；数据库连接使用短事务。
- 同一线程运行互斥最终由数据库部分唯一索引和 Service 层共同保证。
- 时间统一以 UTC 保存和传输，前端按本地时区显示。
- 标识符使用 UUID 字符串；JSON 字段使用 SQLAlchemy `JSON` 类型。
- 配置由 Pydantic Settings 从环境变量和 `backend/.env` 读取。
- 日志使用 Python 标准库输出单行 JSON，不引入独立日志基础设施。
- Phase 1 健康状态页只显示真实后端状态，不使用静态假数据。

## 10. 不拆分微服务的原因

V1 是单用户本地应用，任务量和并发量有限。微服务会额外引入服务发现、网络故障、
跨服务事务、部署编排和可观测性成本，却不能提升当前六个模块的验收价值。单体内
清晰分层已经能隔离 API、Agent、工具、解析、数据和存储职责，也保留了未来按真实
瓶颈拆分的可能。因此 V1 明确不进行微服务或分布式部署。

## 11. 已识别的需求冲突与遗漏

- Word 文档暂定项目名为 MiniAgent，PRD 的正式名称是 AgentFlow；采用 AgentFlow。
- Word 建议 Axios，固定前端技术栈和 PRD 明确使用 Fetch ReadableStream；不引入 Axios。
- Word 的 Phase 1 验收提到“数据库自动初始化”，正式实现解释为从空库执行 Alembic，
  不在应用启动时隐式建表。
- PRD 未规定健康响应结构、分页错误细节、时间格式和 ID 格式；分别采用本文与
  `API_SPEC.md` 中的最小约定。
- PRD 要求删除线程同时删除数据库和文件，但两者无法形成原子事务；Phase 6/7 使用
  Service 编排和可重试清理，Phase 1 只定义策略。
- PRD 未指定搜索供应商和模型兼容协议；模型采用固定 OpenAI-compatible 协议，
  Phase 4 选择 Tavily 作为单一配置化搜索供应商，端点和密钥均来自环境变量，调用
  仅使用固定技术栈中的 `httpx`。
