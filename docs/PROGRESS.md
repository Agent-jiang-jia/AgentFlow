# AgentFlow 开发进度

## 2026-07-31 — 需求分析与 Phase 1

### 完成任务

- 完整阅读 `docs/PRD.md`。
- 结构化读取 `docs/Mini DeerFlow V1 需求与技术设计.docx` 的正文、表格和页眉页脚。
- 确认 PRD 为唯一正式需求基准并记录冲突/缺省决策。
- 创建架构、实施计划、API、数据库、SSE 和任务设计文档。
- 创建根目录长期约束 `AGENTS.md`。
- 完成 FastAPI、配置、CORS、JSON 日志、统一异常和真实数据库健康检查。
- 完成 SQLAlchemy 六表模型、SQLite 连接设置、Alembic 首迁移和迁移测试。
- 完成 React/Vite/严格 TypeScript/Ant Design 基础页和真实健康状态展示。
- 完成环境示例、PowerShell README、Git 忽略和前后端依赖锁定。

### 修改文件

- `AGENTS.md`
- `docs/ARCHITECTURE.md`
- `docs/IMPLEMENTATION_PLAN.md`
- `docs/API_SPEC.md`
- `docs/DATABASE_DESIGN.md`
- `docs/SSE_PROTOCOL.md`
- `docs/TASKS.md`
- `docs/PROGRESS.md`
- `README.md`、`.gitignore`
- `backend/pyproject.toml`、`.env.example`
- `backend/app/**`
- `backend/alembic.ini`、`backend/alembic/**`
- `backend/tests/**`
- `frontend/package.json`、`package-lock.json`、`.env.example`
- `frontend/src/**` 和 Vite/TypeScript/ESLint 配置

### 执行命令

- `Get-Content docs/PRD.md -Raw -Encoding UTF8`
- 使用 bundled Python + `python-docx` 提取 Word 正文、表格和页眉页脚。
- 使用文档技能的 `render_docx.py` 尝试渲染 Word。
- `codegraph init -i`
- `conda create --prefix .\backend\.venv python=3.12 pip -y`
- `backend\.venv\python.exe -s -m pip install -e ".[dev]"`
- `npm install`
- `python -m alembic upgrade head`、`alembic current`、`alembic check`
- `python -m pytest`
- `python -m ruff format --check .`、`python -m ruff check .`
- `python -m mypy app tests`
- `npm run lint`、`npm run typecheck`、`npm run build`
- `npm audit --audit-level=high`

### 测试结果

- PRD 读取成功。
- Word 结构化提取成功，共读取 628 个正文段落、2 个表格和 1 个 section。
- Word 视觉渲染未执行成功：源文档缺少标准页尺寸节属性，且本机无
  LibreOffice/`soffice`；已按文档技能规则改用结构化审阅。
- Python 3.12.13 隔离环境安装成功，固定后端依赖可导入。
- Alembic 从空库创建六张业务表和版本表成功；连续执行 `upgrade head` 幂等；
  `current` 为 `20260731_0001 (head)`；`alembic check` 无模型漂移。
- pytest：5 个测试全部通过，覆盖健康成功/数据库失败、CORS、SQLite 外键和空库迁移。
- Ruff：29 个文件格式检查及 lint 全部通过。
- mypy：27 个源文件严格类型检查通过。
- 前端 ESLint、TypeScript 检查和 production build 全部通过。
- npm audit：0 个漏洞。
- Vite build 有一个非阻塞提示：Ant Design 基础包使主 JS chunk 约 576 kB（gzip
  约 187 kB）；不影响 Phase 1 验收，后续完整工作台阶段按页面边界拆包。

### 遗留问题

- Word 补充文档未完成视觉渲染 QA，原因见上；需求正文和表格已完整结构化读取。
- 前端 production build 的主 chunk 大小提示待 Phase 6 工作台组件形成后按页面/
  功能边界处理，当前不通过提高阈值掩盖提示。

### 下一阶段

- Phase 2 将实现会话 CRUD、消息持久化和不带工具调用的普通流式对话；本次未开始。

## 2026-08-01 — Phase 1 严格审查与修复

### 完成任务

- 重新完整阅读 `AGENTS.md`、`docs/PRD.md` 和七份 Phase 1 设计/跟踪文档。
- 审查依赖、源码、配置和 OpenAPI；确认只存在 `/health` 业务路径，未引入 Redis、
  Celery、Docker 沙箱、RAG、MCP、多 Agent 或其他禁止能力。
- 修复 FastAPI lifespan 异常退出时可能跳过数据库连接池释放的问题。
- 修复 CORS 来源规范化未去除首尾空白的问题。
- 将 API 测试置于真实 lifespan 上下文内，并补充异常关闭、未配置来源拒绝、配置
  示例完整性、相对路径、SQLite PRAGMA 和 Session 回滚测试。
- 为 `VITE_API_BASE_URL` 增加显式 TypeScript 类型，并规范化空白及多个尾部斜杠。
- 实测 Uvicorn、Vite 开发服务器、真实 `/health` 请求和自定义前端环境变量构建。

### 修改文件

- `backend/app/main.py`
- `backend/app/core/config.py`
- `backend/tests/conftest.py`
- `backend/tests/api/test_health.py`
- `backend/tests/db/test_database.py`
- `backend/tests/core/test_config.py`
- `frontend/src/api/health.ts`
- `frontend/src/vite-env.d.ts`
- `docs/TASKS.md`
- `docs/PROGRESS.md`

### 执行命令

- `python -m pytest`
- `python -m ruff format --check .`
- `python -m ruff check .`
- `python -m mypy app tests`
- `python -m pip check`
- `python -m alembic upgrade head`
- `python -m alembic current`
- `python -m alembic check`
- 使用 `AGENTFLOW_DATABASE_PATH` 指向空临时数据库执行 `alembic upgrade head`
- 启动 Uvicorn 后真实请求 `GET /health`
- `npm ls --depth=0`
- `npm audit --audit-level=high`
- `npm run lint`
- `npm run typecheck`
- `npm run build`
- 启动 Vite 开发服务器并真实请求首页
- 使用自定义 `VITE_API_BASE_URL` 构建并检查构建产物
- 使用 `rg` 检查禁止能力、占位实现、疑似密钥和硬编码用户路径

### 测试结果

- pytest：11 个测试全部通过；有效覆盖健康成功/数据库失败、CORS 允许与拒绝、
  lifespan 异常清理、配置示例、相对路径、SQLite 连接设置、Session 回滚和空库迁移。
- Ruff：30 个文件格式检查通过，lint 全部通过。
- mypy：28 个源文件严格类型检查通过。
- Alembic：默认库为 `20260731_0001 (head)`，无模型漂移；空临时数据库成功创建
  `threads`、`messages`、`runs`、`tool_calls`、`files`、`sources` 和版本表。
- SQLite：实测 `foreign_keys=1`、`journal_mode=wal`、`busy_timeout=5000`。
- Uvicorn：真实 `/health` 返回 HTTP 200、数据库状态 `ok` 和请求 ID。
- 前端：ESLint、TypeScript 检查、默认 production build 和自定义 API 地址 build
  全部通过；Vite 开发服务器真实返回 HTTP 200。
- 依赖：`pip check` 无损坏依赖；`npm audit` 为 0 个漏洞。
- 范围与安全扫描：未发现禁止功能、真实 API Key、硬编码用户绝对路径、无说明
  `pass`、`TODO`、空实现或跳过测试。

### 遗留问题

- Vite production build 仍有 Ant Design 主 JS chunk 约 576 kB（gzip 约 187 kB）的
  非阻塞提示；继续留到 Phase 6 按真实页面边界拆包，不提高阈值掩盖提示。
- 当前工作目录没有 `.git` 元数据，无法通过 Git 状态或历史核验变更来源；已完成
  源码静态扫描和 `.gitignore` 内容审查。

### 下一阶段

- Phase 2 计划保持为会话 CRUD、消息持久化和普通流式对话；本次未实现任何
  Phase 2 功能。

## 2026-08-01 — Phase 2 会话与普通流式对话

### 完成任务

- 实现会话创建、分页列表、详情、消息列表和删除 API，保持 API、Service、
  Repository 分层。
- 创建线程时生成 `uploads`、`parsed`、`outputs` 固定目录；删除时先暂存目录，
  数据库提交失败可恢复，成功后清理目录。
- 实现线程内严格递增消息序号、分页历史、完整普通对话上下文和跨线程隔离。
- 使用现有 runs 活动部分唯一索引和 `BEGIN IMMEDIATE` 写事务实现同线程 409
  并发限制，无数据库结构变化。
- 实现固定 OpenAI-compatible `chat/completions` 流式客户端；模型地址、密钥、
  名称和超时全部来自集中配置。
- 实现 POST SSE 的 `run_start`、`assistant_start`、`assistant_delta`、
  `assistant_end`、`run_end` 和 `error`；事件 ID、事件名和完整负载一致。
- 模型失败时保留用户消息、将 run 标记为 failed、不创建虚假助手消息；流取消时
  将 run 标记为 cancelled。
- 首次成功对话按第一条用户消息生成不超过 30 字的简单标题。
- 完成 Zustand 权威状态同步、Fetch ReadableStream SSE 客户端、事件去重和分块
  UTF-8/CRLF 解析。
- 将 Phase 1 状态页升级为 Phase 2 基础双栏聊天工作台，支持创建、切换、删除、
  恢复会话、Markdown/GFM、代码高亮、流式状态、错误和移动端布局。
- 更新 README 的 Phase 2 状态、模型配置和前端测试命令。

### 主要修改文件

- `backend/app/api/threads.py`、`backend/app/api/chat.py`
- `backend/app/services/thread_service.py`、`chat_service.py`、`model_client.py`
- `backend/app/db/repositories/*`
- `backend/app/storage/thread_storage.py`
- `backend/app/schemas/thread.py`、`message.py`、`chat.py`、`pagination.py`
- `backend/tests/api/test_threads.py`、`test_chat.py`
- `backend/tests/services/test_model_client.py`
- `backend/tests/storage/test_thread_storage.py`
- `frontend/src/api/*`、`stores/workspaceStore.ts`、`utils/sse.ts`
- `frontend/src/components/*`、`App.tsx`、`styles.css`
- `frontend/src/utils/sse.test.ts`
- `README.md`、后端和前端环境/依赖配置

### 执行命令

- `python -m ruff format --check .`
- `python -m ruff check .`
- `python -m mypy app tests`
- `python -m pytest`
- `python -s -m pip check`
- 使用隔离临时数据库执行 `alembic upgrade head`、`current`、`check` 和表/索引检查
- `npm run test`
- `npm run lint`
- `npm run typecheck`
- `npm run build`
- `npm audit --audit-level=high`
- 使用隔离临时数据库启动 Uvicorn 和 Vite，进行桌面与 390px 移动端浏览器验证
- 使用 `rg` 检查占位实现、跳过测试、密钥、绝对路径、固定线程 ID 和禁止能力

### 测试结果

- pytest：25 个测试全部通过，覆盖会话 CRUD、目录生命周期、级联删除、消息排序、
  20 轮上下文、跨线程隔离、SSE 顺序、模型成功/失败、流关闭取消、活动 run 409、
  模型协议和 Windows 路径边界。
- Ruff：49 个文件格式检查和 lint 全部通过。
- mypy：47 个源文件严格类型检查通过。
- Alembic：空临时数据库升级到 `20260731_0001 (head)`；六张业务表、版本表和
  `uq_runs_active_thread` 均存在；`alembic check` 无模型漂移。本阶段未修改表结构，
  因此未创建新 revision。
- Python 隔离环境 `python -s -m pip check` 无损坏依赖。未加 `-s` 时，本机用户级
  site-packages 中与项目无关的残缺包会污染结果，已确认项目解释器在禁用用户包后
  只加载 `.venv` 依赖。
- Vitest：3 个 SSE 分块解析测试全部通过，覆盖多字节 UTF-8、CRLF 跨块、多行 data
  和非法 JSON。
- 前端 ESLint、严格 TypeScript 和 production build 全部通过；npm audit 为
  0 个漏洞。
- 浏览器实测：新建会话、运行中禁用、模型未配置安全失败、失败用户消息刷新恢复、
  桌面布局和 390px 移动布局均符合预期；修复了 QA 中发现的两处 Ant Design 弃用
  警告。

### 遗留问题

- 未配置真实外部模型凭据，因此没有对特定第三方供应商做在线调用；已通过
  httpx MockTransport 验证 OpenAI-compatible 请求、鉴权、上下文和流式增量协议，
  并通过完整 API 集成测试验证成功与失败链路。
- production build 主 JS chunk 约 862 kB（gzip 约 276 kB），Vite 仍给出超过
  500 kB 提示。Phase 2 的 Markdown、代码高亮和 Ant Design 进入主包后体积上升；
  继续按既定计划在 Phase 6 根据完整工作台页面/功能边界拆包，不提高阈值掩盖提示。

### 下一阶段

- Phase 3 将实现 Tool Registry、`get_current_time` 测试工具、LangGraph 单 Agent
  顺序工具循环，以及循环/重复/超时保护和公开工具状态；本次未提前实现。

## 2026-08-01 — Phase 3 LangGraph 单 Agent 工具循环

### 完成任务

- 建立统一 Tool Registry，支持唯一注册、精确查找、模型工具描述、Pydantic v2
  参数模型和公开参数白名单。
- 实现临时验证工具 `get_current_time`，使用 `UTC` 或数字 UTC offset，避免依赖
  Windows 不稳定的 IANA 时区数据。
- 将固定 OpenAI-compatible 客户端升级为流式文本与 function/tool call 增量解析，
  并支持 assistant tool call 和 `ToolMessage` 的后续请求序列化。
- 使用 LangGraph 建立单一 `assistant`/`tools` 状态图；模型请求的多个工具严格按
  顺序执行，工具结构化结果作为 LangChain `ToolMessage` 返回同一模型。
- 实现最大模型循环、规范化参数重复检测和 `asyncio.timeout` 工具超时保护；参数
  错误、未知工具、重复、超时和内部异常均转换为安全工具结果，不中断服务进程。
- 完成 `tool_calls` 的 running/success/failed/timeout/rejected 生命周期持久化，
  保存安全参数、结构化结果、起止时间和非负耗时；run 保存真实 loop count 和
  `max_loops_reached` 终态。
- 扩展 SSE `tool_start`/`tool_result`，只发送白名单状态、公开参数和安全摘要，不
  发送完整工具结果、堆栈、绝对路径或模型思维链。
- 在现有工作台中增加工具执行轨迹卡片，按 run 和调用顺序展示执行中、完成、失败、
  超时和阻止状态；未知或畸形事件不会破坏已知事件处理。
- 更新 README 的 Phase 3 状态、模型工具调用要求和循环/超时配置说明。

### 主要修改文件

- `backend/app/agent/runtime.py`
- `backend/app/tools/base.py`、`registry.py`、`executor.py`
- `backend/app/tools/get_current_time.py`
- `backend/app/services/model_client.py`、`chat_service.py`
- `backend/app/db/repositories/tool_call_repository.py`
- `backend/tests/api/test_chat.py`
- `backend/tests/services/test_model_client.py`
- `backend/tests/tools/test_registry.py`
- `frontend/src/components/ToolStatusLedger.tsx`
- `frontend/src/stores/workspaceStore.ts`
- `frontend/src/utils/toolActivity.ts` 及测试
- `frontend/src/types/api.ts`、`styles.css`
- `README.md`、`docs/TASKS.md`、`docs/PROGRESS.md`

### 执行命令

- `python -m ruff format --check .`
- `python -m ruff check .`
- `python -m mypy app tests`
- `python -m pytest`
- `python -s -m pip check`
- 使用独立临时空数据库执行 `alembic upgrade head`、`current`、`check`，并检查
  七张表和 `tool_calls` 三个索引。
- `npm run test`
- `npm run lint`
- `npm run typecheck`
- `npm run build`
- `npm audit --audit-level=high`
- 使用 `rg` 检查占位实现、跳过测试、疑似密钥、绝对路径、固定线程 ID 和禁止能力。
- `git diff --check`

### 测试结果

- pytest：33 个测试全部通过；新增覆盖直接回答、单次工具闭环、未知工具拒绝、参数
  错误后修正、连续重复阻止、最大循环终止、同一模型轮次多工具顺序执行、工具超时、
  工具异常、工具记录持久化和真实 loop count。
- Ruff：58 个文件格式检查与 lint 全部通过。
- mypy：56 个源文件严格类型检查通过。
- Alembic：空临时数据库升级到 `20260731_0001 (head)`，`alembic check` 无模型
  漂移；`tool_calls` 表及 run/thread/tool_name 三个既有索引均存在。本阶段复用已
  批准的 V1 表结构，没有数据库结构变化，因此未创建新 revision。
- Vitest：2 个测试文件、5 个测试全部通过；新增覆盖工具开始/结果的安全投影和畸形
  事件忽略。
- 前端 ESLint、严格 TypeScript 和 production build 全部通过；npm audit 为
  0 个漏洞。
- 范围与安全扫描：未发现新增 TODO、`pass`、`NotImplementedError`、跳过测试、
  真实密钥、硬编码用户绝对路径、固定生产 thread ID 或 Phase 4+ 禁止能力。

### 遗留问题

- 未配置真实外部模型凭据，因此未对特定第三方供应商在线验证流式 tool calling；
  已通过 httpx MockTransport 验证兼容请求、分块函数参数、ToolMessage 和文本增量，
  并通过完整 API 集成测试验证工具循环与失败路径。
- production build 主 JS chunk 约 866 kB（gzip 约 278 kB），Vite 仍给出超过
  500 kB 提示。维持既定 Phase 6 页面/功能边界拆包计划，不提高阈值掩盖提示。

### 下一阶段

- Phase 4 将实现配置化 `web_search`、安全 `web_fetch`、SSRF 与重定向复检以及
  来源持久化；本次未实现任何 Phase 4 能力。

## 2026-08-01 — Phase 4 联网搜索、网页读取与来源展示

### 完成任务

- 选择 Tavily 作为 V1 单一配置化搜索供应商，通过 `httpx` HTTP API 实现
  `web_search`；支持中英文查询、默认 5/最多 10 条、URL 规范化、过滤和去重。
- 实现 `web_fetch` 的 HTML 下载、字节上限、媒体类型校验、最多 5 次手动重定向、
  readability-lxml 主体抽取、BeautifulSoup 清洗、正文规范化和字符截断。
- 实现公网 HTTP(S) URL 校验：拒绝凭据、非 HTTP 协议、localhost、回环、私网、
  链路本地、元数据地址、保留/非全局地址和混合 DNS 结果；每次重定向前重新解析。
- 为可预期 Web 失败增加稳定的 `URL_NOT_ALLOWED`、`WEB_SEARCH_FAILED` 和
  `WEB_FETCH_FAILED` 工具结果，失败结果返回模型继续处理，不使 run 崩溃。
- 实现来源 Repository/Service，按 `(run_id, url)` 去重；同一 URL 从搜索结果被
  实际抓取后升级为 `web_page`，并写入既有 `sources` 表。
- 将来源同步写入助手消息 `metadata.sources` 和 `assistant_end.sources`，前端可在
  流式完成后及刷新恢复后展示安全链接、标题和摘要。
- 对 `web_fetch` 的 SSE 参数采用更严格白名单，不公开 URL，避免受限地址出现在
  公开事件；网页正文始终只进入模型 ToolMessage，不进入 SSE。
- 使用隔离数据库和本地生产构建完成桌面/390px 窄屏浏览器验证；发现并修复长英文
  来源标题导致窄屏横向溢出的问题，浏览器控制台无错误或警告。
- 更新 README、环境配置示例、API/SSE 契约、架构决策、任务和进度文档。

### 主要修改文件

- `backend/app/core/security.py`、`config.py`
- `backend/app/services/web_search_service.py`、`web_fetch_service.py`、
  `source_service.py`
- `backend/app/tools/web_search.py`、`web_fetch.py`、Tool Registry/Executor
- `backend/app/db/repositories/source_repository.py`
- `backend/app/services/chat_service.py`、`api/dependencies.py`、`main.py`
- `backend/tests/api/test_web_tools.py`
- `backend/tests/core/test_security.py`
- `backend/tests/services/test_web_search_service.py`、`test_web_fetch_service.py`
- `frontend/src/components/SourceReferences.tsx`、`MessageTimeline.tsx`
- `frontend/src/utils/sources.ts` 及测试、store、类型和样式
- `README.md`、`.env.example` 和 Phase 4 设计/跟踪文档

### 执行命令

- `python -m pytest`
- `python -m ruff format --check .`
- `python -m ruff check .`
- `python -m mypy app tests`
- `python -s -m pip check`
- 使用独立空数据库执行 `alembic upgrade head`、`current`、`check`，检查七张表、
  `sources` 索引和 `(run_id, url)` 唯一约束。
- `npm run test`、`npm run lint`、`npm run typecheck`、`npm run build`
- `npm audit --audit-level=high`
- 使用隔离数据库启动 Uvicorn，并以 production build 完成桌面和 390px 窄屏验证。
- 使用 `rg` 检查占位实现、跳过测试、疑似密钥、绝对路径、固定线程 ID 和 Phase 5+
  业务实现；执行 `git diff --check`。

### 测试结果

- pytest：54 个测试全部通过；新增覆盖中英文搜索、结果限制/过滤/去重、配置和供应商
  失败、正文清洗/截断、下载字节上限、非 HTML、私网/回环/元数据/非 HTTP 拒绝、
  混合 DNS、重定向复检、工具失败继续执行、来源去重升级、SSE 和历史恢复。
- Ruff：69 个文件格式检查与 lint 全部通过；mypy：67 个源文件严格检查通过。
- Alembic：空数据库升级到 `20260731_0001 (head)`，无模型漂移；本阶段复用初始
  `sources` 表和约束，没有数据库结构变化，因此未创建新 revision。
- Vitest：3 个测试文件、7 个测试全部通过；ESLint、严格 TypeScript 和 production
  build 全部通过；npm audit 为 0 个漏洞。
- 浏览器实测：桌面和 390px 窄屏均能恢复并展示来源；长标题正确省略，摘要受限，
  无横向溢出，外链具备 `noopener`/`noreferrer`，控制台无错误或警告。
- 范围与安全扫描：未发现新增 TODO、`pass`、`NotImplementedError`、跳过测试、
  真实密钥、硬编码用户绝对路径、固定生产 thread ID 或 Phase 5+ 业务能力。

### 遗留问题

- 未配置真实 Tavily 与模型凭据，因此未进行第三方在线调用；已使用真实 `httpx`
  请求/响应路径的 MockTransport 验证供应商协议，并通过完整 API 工具循环集成测试。
- production build 主 JS chunk 约 868 kB（gzip 约 278 kB），仍有超过 500 kB 的
  非阻塞提示；继续按既定 Phase 6 完整工作台边界拆包，不提高阈值掩盖提示。

### 下一阶段

- Phase 5 将实现文件上传校验、PDF/DOCX/TXT/Markdown/CSV 解析、线程目录隔离、
  `list_files`/`read_file` 和最小前端文件列表；本次未实现任何 Phase 5 能力。

## 2026-08-01 — Phase 5 文件上传、解析与安全读取

### 完成任务

- 实现 `POST/GET/DELETE /api/threads/{thread_id}/files` 和文件详情 API，响应不包含
  `stored_path`，跨会话已存在文件统一返回 `FILE_ACCESS_DENIED`。
- 实现跨平台文件名校验，覆盖路径分隔符、路径穿越、控制字符、Windows 保留名、
  非法字符、尾随点/空格、扩展名、声明 MIME、实际 PDF/DOCX 格式和空文件。
- 使用按块读取限制上传大小，实际文件名采用 `{file_id}_{safe_filename}`，所有路径
  同时验证规范 UUID、数据库 `thread_id` 归属和解析后仍位于线程固定目录。
- 建立 Parser Registry；PDF 按页提取，扫描件标记 `unsupported_ocr`；DOCX 提取
  标题、段落、列表和表格；TXT/Markdown 支持 UTF-8、GB18030、Big5；CSV 统计总行数
  并限制为前 500 行；统一生成有上限的 UTF-8 Markdown。
- 解析失败保留上传源文件与安全失败元数据，不创建虚假 parsed 文件；删除上传源文件
  时通过暂存/回滚补偿同步删除关联解析文件和元数据。
- 实现 `list_files` 和只接受规范 `file_id` 的 `read_file`，支持行窗口、字符上限、
  截断标识和二进制上传自动读取解析版本；完整工具结果仅进入 `ToolMessage`，SSE 只
  展示安全摘要。
- 聊天 `file_ids` 现在验证真实线程归属，并仅向模型上下文加入逻辑 ID，不暴露路径。
- 前端增加横向最小文件台，支持多选后逐个上传、真实解析状态、大小/类型展示、删除、
  会话切换恢复和失败后权威列表刷新；未实现 Phase 6 的第三栏、Artifact 或预览下载。
- 使用 `frontend-design` 保持现有执行账本视觉体系，并用真实浏览器验证桌面和 390px
  窄屏上传/删除流程。
- 更新 README、环境示例、API 契约、任务和进度文档。

### 主要修改文件

- `backend/app/api/files.py`、`schemas/file.py`
- `backend/app/services/file_service.py`、`parser_service.py`
- `backend/app/storage/file_storage.py`、`filename.py`
- `backend/app/parsers/*`
- `backend/app/db/repositories/file_repository.py`
- `backend/app/tools/list_files.py`、`read_file.py`、Tool Registry/依赖注入
- `backend/app/services/chat_service.py`
- `backend/tests/api/test_files.py`、`tests/parsers/*`、`tests/storage/test_filename.py`
- `frontend/src/api/files.ts`、`components/FileShelf.tsx`
- `frontend/src/stores/workspaceStore.ts`、类型、样式和 API 测试
- `README.md`、`.env.example`、`docs/API_SPEC.md`、`docs/TASKS.md`、
  `docs/PROGRESS.md`

### 执行命令

- `python -m pytest`
- `python -m ruff format --check .`、`python -m ruff check .`
- `python -m mypy app tests`、`python -s -m pip check`
- 使用独立空数据库执行 `alembic upgrade head`、`current`、`check`，并检查 `files`
  表和 `ix_files_thread_category_created` 索引。
- `npm run test`、`npm run lint`、`npm run typecheck`、`npm run build`
- `npm audit --audit-level=high`
- 使用隔离数据库启动 Uvicorn/Vite，在桌面与 390px 视口上传、解析和删除真实
  Markdown 文件，并检查 DOM、横向溢出和浏览器控制台。
- 使用 `rg` 检查占位实现、跳过测试、疑似密钥、绝对路径、固定线程 ID 和敏感字段；
  执行 `git diff --check`。

### 测试结果

- pytest：最终 78 个测试全部通过；Phase 5 新增覆盖文件名、MIME/实际格式、空文件、
  大小、五类解析、中文编码、CSV 500 行、扫描 PDF、解析失败状态、文件 CRUD、磁盘
  级联、聊天附件归属、完整 list/read 工具循环和跨会话工具读取拒绝。
- Ruff 格式检查和 lint 全部通过；mypy 严格检查全部通过；项目隔离环境依赖完整。
- Alembic：空数据库升级到 `20260731_0001 (head)`，七张表及文件索引存在，
  `alembic check` 无模型漂移；本阶段复用初始 `files` 表，没有数据库结构变化。
- Vitest：4 个测试文件、10 个测试全部通过；ESLint、严格 TypeScript 和 production
  build 全部通过；npm audit 为 0 个漏洞。
- 浏览器实测：上传 `README.md` 后显示真实大小、MD 类型和“解析完成”，删除后恢复
  空态；390px 下 `scrollWidth=innerWidth=390`，无横向溢出，控制台无错误或警告。
- 安全扫描未发现新增 TODO、`pass`、`NotImplementedError`、跳过测试、真实密钥、
  硬编码用户绝对路径或固定生产 `thread_id`；PyMuPDF 缺少 typing metadata 的三处
  `type: ignore[import-untyped]` 均有明确注释。

### 遗留问题

- 未配置真实外部模型凭据，因此未做第三方模型在线文件工具调用；已通过完整脚本模型
  集成测试验证 `list_files → read_file → ToolMessage → 最终回答` 的真实持久化链路。
- production build 主 JS chunk 约 875 kB（gzip 约 280 kB），仍有超过 500 kB 的
  非阻塞提示；继续在 Phase 6 完整工作台形成后按真实页面/功能边界拆包，不提高阈值。
- pytest 仍显示 Starlette 对旧 422 常量的一条第三方弃用提示，来源于依赖内部异常
  处理路径，不影响请求行为或本阶段验收。

### 下一阶段

- Phase 6 计划实现安全 `write_file`、Artifact 列表/预览/下载和完整三栏工作台；
  本次未提前实现任何 Phase 6 业务能力。

## 2026-08-01 — Phase 6 安全文件生成、Artifact 与完整工作台

### 完成任务

- 实现 `write_file`，只接受叶子文件名、UTF-8 正文和可选描述；支持 V1 规定的十种
  扩展名，拒绝绝对路径、分隔符、`..`、Windows 保留名和未授权类型。
- 生成内容只写入当前线程 `outputs`，按 UTF-8 字节执行配置化大小限制；真实文件名
  使用服务端 `file_id` 前缀，可见同名文件自动生成 `(2)` 等后缀且不覆盖已有成果。
- 新增 Artifact Service 与列表、预览、下载 API；所有访问同时校验 `thread_id`、
  `file_id`、category 和受控路径，跨线程返回 `FILE_ACCESS_DENIED`，响应不含绝对路径。
- 为 Markdown、TXT、JSON、CSV、Python、JavaScript、TypeScript、YAML 和 HTML 返回
  正确预览类型；HTML 响应设置严格 CSP，下载使用安全 `Content-Disposition`，全部
  响应设置 `nosniff` 和 `no-store`。
- 将 `write_file` 注册到单 Agent 顺序工具循环；内容不会写入公开工具参数、SSE 或
  工具结果，写入和元数据提交完成后按 `tool_start → artifact_created → tool_result`
  顺序发送安全事件。
- 前端建立独立 Artifact API 与运行时形状检查；会话切换、刷新、上传、删除和聊天
  结束均恢复权威列表，收到 `artifact_created` 后立即刷新生成成果。
- 完成会话、聊天、交付台三栏工作台；右栏分离上传资料和生成成果，支持预览、下载、
  删除，Markdown/GFM、代码、JSON、CSV 表格、纯文本和 HTML 沙箱均有对应预览。
- 使用 React lazy 边界拆分完整工作台与 Artifact 预览，production build 最大 chunk
  从 Phase 5 的约 875 kB 降至约 417 kB，不提高 Vite 告警阈值。
- 修复已有上传超限分支使用不存在的 Starlette 413 常量问题，并保留原错误码和行为。
- 更新 README、任务与进度文档；未实现 Phase 7 的异常/恢复收口或其他后续能力。

### 主要修改文件

- `backend/app/services/artifact_service.py`、`storage/file_storage.py`、
  `storage/filename.py`
- `backend/app/tools/write_file.py`、`tools/__init__.py`
- `backend/app/api/artifacts.py`、`api/dependencies.py`、`main.py`
- `backend/app/services/chat_service.py`、文件 Schema/Repository/Service
- `backend/tests/api/test_artifacts.py`
- `frontend/src/pages/Workspace.tsx`
- `frontend/src/components/ArtifactPanel.tsx`、`ArtifactPreview.tsx`、`FileShelf.tsx`
- `frontend/src/api/artifacts.ts`、Zustand store、共享类型和 CSV 工具
- `frontend/src/styles.css`、`App.tsx`
- `README.md`、`docs/TASKS.md`、`docs/PROGRESS.md`

### 执行命令

- `python -m pytest`
- `python -m ruff format --check .`、`python -m ruff check .`
- `python -m mypy app tests`、`python -s -m pip check`
- 使用独立空数据库执行 `alembic upgrade head`、`current` 和 `check`。
- `npm run test`、`npm run lint`、`npm run typecheck`、`npm run build`
- `npm audit --audit-level=high`
- 使用隔离数据库和 production build 启动 Uvicorn/Vite，在 1280px 与 390px 视口
  检查三栏/堆叠布局、Artifact 恢复、Markdown/CSV/HTML 预览、HTML 沙箱和控制台。
- 使用 `rg` 检查占位实现、跳过测试、疑似密钥、绝对路径、固定线程 ID 和禁止能力；
  执行 `git diff --check`。

### 测试结果

- pytest：81 个测试全部通过；Phase 6 新增覆盖完整 `write_file` Agent Loop、事件
  顺序、正文不泄露、十种类型、非法文件名/类型、UTF-8 字节大小、同名处理、跨线程
  拒绝、列表、预览/下载 Content-Type、安全头和工具参数持久化。
- Ruff 格式检查和 lint 全部通过；mypy 对 90 个源文件严格检查通过；项目隔离环境
  依赖完整。
- Alembic：空数据库升级到 `20260731_0001 (head)`，`alembic check` 无模型漂移；
  本阶段复用既有 `files` 表及 `description` 字段，没有数据库结构变化。
- Vitest：6 个测试文件、14 个测试全部通过；ESLint、严格 TypeScript 和 production
  build 全部通过；最大 chunk 约 417 kB（gzip 约 129 kB），无超限提示。
- 浏览器实测：1280px 为 270/656/330 三栏，390px 无横向溢出；HTML iframe 的
  `sandbox` 为空权限集且脚本未执行，CSV 表格正确，控制台无错误或警告。
- 隔离浏览器数据与日志目录在验收后删除，不包含开发数据，删除后不可恢复。

### 遗留问题

- 未配置真实外部模型凭据，因此未做第三方模型在线 `write_file` 调用；已通过完整脚本
  模型、ToolMessage、SSE、数据库和文件系统集成测试验证真实生成闭环。
- pytest 仍显示本机用户级 `pytest-asyncio` 的默认 fixture loop scope 弃用提示；
  项目隔离依赖与测试行为不受影响，本阶段未通过改动无关测试配置掩盖提示。

### 下一阶段

- Phase 7 将按计划收口全链路异常、断连、失败补偿、安全测试、E2E 和发布文档；
  本次未提前实现任何 Phase 7 能力。
