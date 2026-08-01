# AgentFlow

AgentFlow V1 是面向单用户、本地部署的轻量级单 Agent Web 工作台。本仓库当前完成
Phase 3：在会话与普通流式对话基础上提供 LangGraph 单 Agent 顺序工具循环、统一
Tool Registry、`get_current_time` 验证工具、工具调用持久化、循环/重复/超时保护，
以及不展示思维链的前端公开工具状态。Web 搜索和文件能力仍属于后续 Phase。

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

Phase 3 使用一个固定的、支持流式 function/tool calling 的 OpenAI-compatible
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
用户消息、将 run 标记为失败，并通过 SSE 返回安全的模型不可用提示。当前注册表只
包含 Phase 3 的 `get_current_time` 验证工具，不包含尚未开发的 Web 或文件工具。

## 前端安装与启动

打开另一个 PowerShell，回到仓库根目录：

```powershell
Set-Location frontend
Copy-Item .env.example .env
npm install
npm run dev
```

访问 `http://127.0.0.1:5173`。页面从后端恢复历史会话，聊天请求使用原生 Fetch
`ReadableStream` 消费 POST SSE。

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
