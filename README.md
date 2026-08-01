# AgentFlow

AgentFlow V1 是面向单用户、本地部署的轻量级单 Agent Web 工作台。本仓库当前只
完成 Phase 1：工程脚手架、集中配置、SQLite/Alembic、健康检查和前端连接状态页。
尚未实现会话、聊天、Agent、Web 搜索或文件业务接口。

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

## 前端安装与启动

打开另一个 PowerShell，回到仓库根目录：

```powershell
Set-Location frontend
Copy-Item .env.example .env
npm install
npm run dev
```

访问 `http://127.0.0.1:5173`。页面会请求真实的后端健康接口并显示连接状态。

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
npm run build
Set-Location ..
```

## 配置

后端配置使用 `AGENTFLOW_` 前缀并从 `backend\.env` 读取；前端使用
`VITE_API_BASE_URL`。示例文件不包含真实密钥。相对数据库和数据路径均相对于
`backend` 目录解析，因此从不同工作目录启动结果一致。

设计和后续阶段计划见 `docs`。任何后续开发都应先阅读根目录 `AGENTS.md`。
