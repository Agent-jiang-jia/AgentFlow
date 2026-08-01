# AgentFlow V1 实施计划

## 总体原则

- 严格按 Phase 1 到 Phase 7 顺序开发，不提前实现后续能力。
- 每一阶段只在前一阶段验收通过后开始。
- API、Service、Repository 分层；数据库结构只通过 Alembic 变更。
- 每阶段同步更新 `TASKS.md` 和 `PROGRESS.md`。

## Phase 1：项目脚手架、配置、数据库和健康检查

**目标**

- 建立 FastAPI 与 React 工程。
- 集中管理环境配置、CORS 和 JSON 日志。
- 建立 SQLAlchemy 2、SQLite、Alembic 和首个六表迁移。
- 实现并展示真实的 `GET /health`。

**依赖**：PRD 和设计文档完成。

**主要文件**

- `backend/app/main.py`
- `backend/app/core/*`
- `backend/app/db/*`
- `backend/app/api/health.py`
- `backend/alembic/*`
- `backend/tests/*`
- `frontend/src/*`
- 前后端工程配置与 `.env.example`

**测试**

- Alembic 从空库升级到 `head`。
- `pytest`、Ruff、mypy。
- ESLint、`tsc --noEmit`、Vite production build。
- FastAPI 导入和健康接口成功/数据库失败测试。

**验收**

- 后端可启动，`GET /health` 对可用数据库返回 200。
- 首个迁移创建六张业务表及关键索引。
- 前端可启动并显示真实后端连接状态。
- 全部 Phase 1 检查通过，无后续业务接口实现。

## Phase 2：会话 CRUD、消息持久化和普通流式对话

**目标**

- 实现线程创建、列表、详情、删除和消息查询。
- 保存用户/助手消息，接入固定单模型普通对话。
- 通过 POST + SSE 流式传输纯文本，不调用工具。
- 首轮成功后按首条用户消息截取生成标题。

**依赖**：Phase 1。

**主要文件**

- `backend/app/api/threads.py`、`chat.py`
- `backend/app/services/thread_service.py`、`chat_service.py`
- `backend/app/db/repositories/*`
- `backend/app/schemas/thread.py`、`message.py`、`chat.py`
- `frontend/src/api/*`、基础聊天组件和 Zustand store

**测试**

- 会话 CRUD、级联删除、消息顺序和跨线程隔离。
- 普通聊天 SSE 顺序、模型失败和 409 并发限制。
- 前端流解析单元测试、lint、类型检查和 build。

**验收**

- 多会话及至少 20 轮上下文可工作。
- 刷新/重启后会话和消息恢复。
- 流式回复可见，失败不创建虚假助手成功消息。

## Phase 3：LangGraph Agent Loop 和测试工具

**目标**

- 建立单 Agent 的 `assistant`/`tools` 循环。
- 实现 Tool Registry、Pydantic 参数校验、调用记录。
- 使用 `get_current_time` 验证完整工具闭环。
- 实现最大循环、重复调用和基础超时控制。

**依赖**：Phase 2。

**主要文件**

- `backend/app/agent/*`
- `backend/app/tools/base.py`、`registry.py`、`executor.py`
- `backend/app/tools/get_current_time.py`
- Agent、工具和 SSE 测试；前端工具状态卡片

**测试**

- 直接回答、单次工具、多次顺序工具、参数错误、超时、重复和循环上限。

**验收**

- 模型可自主调用测试工具并基于结果完成回答。
- 所有工具调用与 run 状态持久化。
- 不存在子 Agent 或子任务并发。

## Phase 4：web_search 和 web_fetch

**目标**

- 接入一个配置化搜索供应商。
- 使用 httpx、readability-lxml、BeautifulSoup4 读取和清洗网页。
- 实施请求前及重定向后的 SSRF 校验。
- 保存实际使用来源并在最终回答展示。

**依赖**：Phase 3。

**主要文件**

- `backend/app/tools/web_search.py`、`web_fetch.py`
- `backend/app/core/security.py`
- 搜索服务、来源 Repository 和安全测试

**测试**

- 中英文搜索、去重、限制、超时与供应商失败。
- 公网 URL、私网/回环/元数据/非 HTTP 拒绝、重定向复检。
- 正文提取、截断和来源保存。

**验收**

- 联网搜索和网页总结可完成；失败网页不使 run 崩溃。
- SSRF 测试通过，响应不泄露内部信息。

## Phase 5：文件上传、解析、list_files 和 read_file

**目标**

- 实现 PDF、DOCX、TXT、MD、CSV 上传、校验和同步解析。
- 建立线程目录隔离和安全文件名。
- 实现 `list_files` 与只基于 `file_id` 的 `read_file`。
- 扫描 PDF 明确标为 `unsupported_ocr`。

**依赖**：Phase 4。

**主要文件**

- `backend/app/api/files.py`
- `backend/app/parsers/*`
- `backend/app/storage/*`
- `backend/app/services/file_service.py`、`parser_service.py`
- 前端上传和文件列表的最小界面

**测试**

- 格式、MIME、大小、空文件、路径穿越和 Windows 保留名。
- 各支持格式解析、编码回退、CSV 500 行限制、OCR 不支持。
- 跨线程读取拒绝与路径不泄露。

**验收**

- 上传后可见真实解析状态，Agent 能安全读取。
- 不同线程文件完全隔离。

## Phase 6：write_file、Artifact 和完整 Web 工作台

**目标**

- 实现安全的 `write_file`、Artifact 列表、预览和下载。
- 完成三栏工作台、Markdown/GFM、代码高亮和文件面板。
- HTML 使用受限 iframe，生成后立即处理 `artifact_created`。

**依赖**：Phase 5。

**主要文件**

- `backend/app/tools/write_file.py`
- `backend/app/api/artifacts.py`
- `backend/app/services/artifact_service.py`
- `frontend/src/components/*`、`pages/Workspace.tsx`、store

**测试**

- 扩展名、文件名、重名、大小限制、跨目录写入拒绝。
- 预览 Content-Type、安全头、下载和前端 Artifact 流程。

**验收**

- Agent 可生成、预览和下载所有允许类型。
- 完整工作台满足 PRD，但不含任何禁用功能。

## Phase 7：安全、异常处理、自动化测试和文档完善

**目标**

- 对全链路安全、断连、失败补偿和恢复行为收口。
- 完善端到端测试、运行文档和运维排错说明。
- 验证 PRD 全部 V1 验收场景。

**依赖**：Phase 6。

**主要文件**

- 全部安全/异常相关模块
- `backend/tests/integration/*`
- 前端测试与根 `README.md`
- 所有设计、任务和进度文档

**测试**

- PRD 端到端场景、SSE 断连、进程重启、迁移重放。
- SSRF、路径穿越、跨线程访问、HTML 沙箱和敏感信息检查。
- 后端全套静态检查/测试和前端 lint/typecheck/build。

**验收**

- 全部 V1 验收标准有自动化或明确的人工验证证据。
- 从全新环境按 README 可启动，无未说明 TODO、空实现或跳过测试。

