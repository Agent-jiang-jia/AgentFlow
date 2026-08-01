# AgentFlow

AgentFlow V1 是面向单用户、本地部署的轻量级单 Agent Web 工作台。本仓库已完成
Phase 7 和 V1 发布验收：支持流式对话、顺序工具循环、联网搜索与网页读取、五类
文件上传解析，以及线程隔离的 `list_files`、`read_file`、`write_file`。Agent 生成的
Artifact 可在完整三栏工作台中即时查看、受限预览、下载和删除。

## 环境要求

- Windows 10/11
- PowerShell 7 或 Windows PowerShell
- Python 3.12
- Node.js 20.19 或更高版本
- npm 10 或更高版本

以下命令均从仓库根目录执行。

## 后端安装

```powershell
py -3.12 -m venv backend\.venv
backend\.venv\Scripts\python.exe -m pip install --upgrade pip
backend\.venv\Scripts\python.exe -m pip install -e "backend[dev]"
Copy-Item backend\.env.example backend\.env
```

如果 `py -3.12` 不可用，但已安装 Conda，可创建相同位置的 Python 3.12 环境：

```powershell
conda create --prefix .\backend\.venv python=3.12 pip -y
backend\.venv\python.exe -m pip install -e "backend[dev]"
```

标准 venv 的解释器位于 `backend\.venv\Scripts\python.exe`；Conda 前缀环境位于
`backend\.venv\python.exe`。后续命令示例以标准 venv 为准；Conda 用户替换这一段
解释器路径即可，不要求激活环境。

## 数据库迁移

```powershell
Set-Location backend
.\.venv\Scripts\python.exe -m alembic upgrade head
Set-Location ..
```

迁移会在 `backend\data\agentflow.db` 创建 V1 首个数据库结构。应用启动不会隐式
创建或修改表。

## 启动后端

```powershell
Set-Location backend
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

健康检查地址为 `http://127.0.0.1:8000/health`。

### 配置聊天模型与 Agent Loop

V1 使用一个固定的、支持流式 function/tool calling 的 OpenAI-compatible
`chat/completions` 端点。在 `backend\.env` 中配置：

```dotenv
AGENTFLOW_MODEL_API_BASE=https://provider.example/v1
AGENTFLOW_MODEL_API_KEY=replace-with-local-secret
AGENTFLOW_MODEL_NAME=replace-with-fixed-model-name
AGENTFLOW_MODEL_TIMEOUT_SECONDS=60
AGENTFLOW_MAX_AGENT_LOOPS=10
AGENTFLOW_TOOL_TIMEOUT_SECONDS=30
```

`MODEL_API_BASE` 也可直接填写以 `/chat/completions` 结尾的地址。密钥只从环境变量
读取，不要提交 `backend\.env`。未配置模型时，会话 CRUD 仍可使用；发送消息会保留
用户消息、将 run 标记为失败，并通过 SSE 返回安全的模型不可用提示。

### 配置联网搜索与网页读取

V1 使用 Tavily 作为配置化搜索供应商，通过 `httpx` 直接调用其 HTTP API：

```dotenv
AGENTFLOW_SEARCH_PROVIDER=tavily
AGENTFLOW_SEARCH_API_BASE=https://api.tavily.com/search
AGENTFLOW_SEARCH_API_KEY=replace-with-local-secret
AGENTFLOW_SEARCH_TIMEOUT_SECONDS=10
AGENTFLOW_WEB_FETCH_TIMEOUT_SECONDS=10
AGENTFLOW_WEB_FETCH_MAX_BYTES=2000000
```

搜索密钥只从环境变量读取。未配置搜索密钥时，普通对话和 `web_fetch` 仍可使用，
`web_search` 会向模型返回安全的配置错误。网页读取仅允许公网 HTTP(S) URL，并在
请求前及每次重定向后检查 DNS 解析结果；不会向 SSE 发送网页正文或受限地址。
当前注册表包含 `get_current_time`、`web_search`、`web_fetch`、`list_files`、
`read_file` 和 `write_file`。

### 配置文件上传与解析

文件上传限制和解析文本上限由环境变量集中配置：

```dotenv
AGENTFLOW_MAX_UPLOAD_SIZE_MB=20
AGENTFLOW_MAX_PARSED_CHARS=200000
```

支持 `.pdf`、`.docx`、`.txt`、`.md`、`.csv`。上传文件写入当前会话的受控目录并
同步生成统一 Markdown；扫描 PDF 会显示 `unsupported_ocr`，不会把空白解析结果交给
模型。前端文件台支持逐个上传、查看真实解析状态和删除；Agent 读取只接受 `file_id`。

### 配置 Artifact 生成与预览

生成文件大小上限由环境变量集中配置：

```dotenv
AGENTFLOW_MAX_ARTIFACT_SIZE_MB=5
```

`write_file` 支持 `.md`、`.txt`、`.html`、`.csv`、`.json`、`.py`、`.js`、`.ts`、
`.yaml` 和 `.yml`，只写入当前会话的 `outputs` 目录。同名文件自动编号，不覆盖已有
成果。HTML 通过严格 CSP 和无权限 `sandbox` iframe 预览；所有下载均使用附件响应，
API、SSE 和错误不会返回服务器文件路径。

## 异常退出与自动恢复

后端每次启动都会执行幂等恢复，但不会创建或修改数据库结构：

- 将上次进程遗留的 `pending`/`running` run 标记为 `cancelled`，释放会话运行锁。
- 将遗留的运行中工具调用标记为失败并写入安全错误摘要。
- 根据 SQLite 元数据恢复未提交删除所暂存的线程目录或文件。
- 清理数据库已提交删除后遗留的暂存项和无元数据的受控文件。
- 重建已存在会话缺失的三个固定子目录，并只在日志中记录计数。

如果元数据引用的文件已经从磁盘永久丢失，启动日志会报告 `missing_files` 数量；系统
不会伪造文件内容。此时可从备份恢复整个数据目录，或删除对应失效文件元数据。

## 前端安装与启动

打开另一个 PowerShell，回到仓库根目录：

```powershell
Set-Location frontend
Copy-Item .env.example .env
npm install
npm run dev
```

访问 `http://127.0.0.1:5173`。页面从后端恢复历史会话，聊天请求使用原生 Fetch
`ReadableStream` 消费 POST SSE。桌面端采用会话、聊天、交付台三栏布局；窄屏按相同
信息顺序堆叠显示。SSE 断开或协议异常后，前端会重新加载该会话的消息、文件和
Artifact，以后端持久化状态为准。

本地发布运行可先执行 `npm run build`，再执行：

```powershell
npm run preview -- --host 127.0.0.1 --port 5173
```

## 后端测试和静态检查

```powershell
Set-Location backend
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m mypy app tests
Set-Location ..
```

## 前端检查和生产构建

```powershell
Set-Location frontend
npm run lint
npm run typecheck
npm run test
npm run build
Set-Location ..
```

## 配置

后端配置使用 `AGENTFLOW_` 前缀并从 `backend\.env` 读取；前端使用
`VITE_API_BASE_URL`。示例文件不包含真实密钥。相对数据库和数据路径均相对于
`backend` 目录解析，因此从不同工作目录启动结果一致。

设计和后续阶段计划见 `docs`。任何后续开发都应先阅读根目录 `AGENTS.md`。

## 备份与恢复

备份前先停止后端，随后复制 `AGENTFLOW_DATA_DIR` 指向的整个目录；默认是
`backend\data`。数据库和 `threads` 文件树必须作为一个整体备份。恢复时保持后端
停止，用备份整体替换目标数据目录，确认 `.env` 中数据库与数据目录仍指向该副本，
执行 `alembic upgrade head` 后再启动服务。

## 常见问题排查

| 现象 | 检查与处理 |
|---|---|
| 启动后业务表不存在 | 在 `backend` 中执行 `python -m alembic upgrade head`；应用不会用 `create_all()` 隐式建表。 |
| 健康检查返回 503 | 检查数据库父目录是否可写、数据库路径是否误指向目录，并确认没有损坏的 SQLite 文件。 |
| 对话提示模型不可用 | 检查模型地址、固定模型名、密钥和端点是否支持流式 tool calling；密钥不得写入仓库。 |
| 搜索工具提示未配置 | 配置 Tavily 密钥；`web_fetch` 和普通对话不依赖该密钥。 |
| 重启前的会话一直显示运行中 | 正常启动会自动取消遗留 run；查看启动日志中的 `cancelled_runs`，不要手工改数据库。 |
| Artifact 或上传文件不可读取 | 查看启动日志中的 `missing_files`；从同一时间点的数据目录备份恢复，避免只恢复数据库。 |
| PDF 显示需要 OCR | V1 不支持扫描件 OCR；请上传含文本层的 PDF 或转换后的 TXT/Markdown。 |
| HTML 预览内容受限 | 这是预期安全策略；HTML 在无权限 `sandbox` iframe 和严格 CSP 下展示。 |

完整的 V1 验收项目、自动化证据和人工验证记录见
[`docs/ACCEPTANCE.md`](docs/ACCEPTANCE.md)。
