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
