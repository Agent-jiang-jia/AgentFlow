# AgentFlow 工程约束

本文件适用于仓库根目录及所有子目录。后续 Codex 任务必须遵守。

## 1. 项目目标

开发 AgentFlow V1：单用户、本地部署的轻量级单主 Agent Web 工作台。核心闭环为
用户输入、模型判断、顺序工具调用、模型继续执行、返回回答或文件、持久化记录。

## 2. 固定技术栈

- 后端：Python 3.12、FastAPI、Uvicorn、LangGraph、LangChain、Pydantic v2、
  SQLAlchemy 2、Alembic、SQLite、httpx、BeautifulSoup4、readability-lxml、
  PyMuPDF、python-docx、pandas、pytest。
- 前端：React、Vite、TypeScript、Ant Design、Zustand、React Markdown、
  remark-gfm、rehype-highlight、Fetch ReadableStream。
- 存储：SQLite 保存结构化数据；本地文件系统保存 uploads、parsed、outputs。

不得擅自替换固定技术栈或引入无需求依据的中间件。

## 3. V1 功能边界

只实现：

1. 对话与流式输出。
2. 单主 Agent 工具调用循环。
3. Web 搜索与网页正文读取。
4. 文件上传、解析、读取和生成。
5. SQLite 会话持久化。
6. 简单 Web 工作台。

正式需求以 `docs/PRD.md` 为准；Word 文档仅在 PRD 不完整时辅助理解，不得扩展范围。

## 4. 禁止实现

不得实现多 Agent、子 Agent、子任务并发、Plan/Todo、Skills、MCP、长期用户记忆、
Docker 沙箱、Kubernetes、Redis、Celery、RAG、向量数据库、Embedding、Reranker、
OCR、图片理解、PPTX 解析、XLSX 复杂解析、浏览器自动化、网页登录、验证码、用户
注册/登录、权限、多租户、飞书/Slack/Telegram、多模型动态切换、微服务和分布式部署。

## 5. 后端目录规范

- `app/api`：HTTP/SSE 协议与依赖注入。
- `app/services`：业务编排、事务和跨资源一致性。
- `app/db/models`：SQLAlchemy 模型。
- `app/db/repositories`：数据访问，不返回 HTTP 响应。
- `app/agent`：LangGraph 单 Agent runtime。
- `app/tools`：Tool Registry 和五个 V1 工具。
- `app/parsers`：文件 Parser Registry。
- `app/storage`：受控路径、文件名与本地文件操作。
- `app/schemas`：Pydantic 请求、响应、事件模型。
- `app/core`：配置、日志、异常、错误码和通用安全。

API 层不得直接编写数据库业务逻辑。只创建当前 Phase 实际需要的包和文件，不批量
创建空占位。

## 6. 前端目录规范

- `src/api`：HTTP 与 SSE 客户端。
- `src/components`：可复用组件。
- `src/hooks`：交互逻辑。
- `src/stores`：Zustand 状态。
- `src/pages`：页面级组合。
- `src/types`：共享 TypeScript 类型。
- `src/utils`：无副作用工具函数。

组件不得绕过 API 层硬编码服务数据；权威状态来自后端。

## 7. Python 编码规范

- 所有函数、方法和类属性使用类型注解。
- 使用 Pydantic v2、SQLAlchemy 2.x 和当前非弃用 API。
- 使用 `pathlib.Path`；不硬编码系统绝对路径或 `/tmp`。
- 配置集中管理，不在业务模块散落环境变量读取。
- 清晰分层，保持函数单一职责；公开行为使用 docstring。
- 使用 Ruff 格式化/检查和 mypy 严格检查。
- 不使用裸 `except`；公开错误必须转换为安全异常。

## 8. TypeScript 编码规范

- 启用 `strict`，不得使用 `any` 逃避检查。
- 确有必要使用不安全类型时，采用 `unknown`、类型守卫并在代码注释说明。
- React 使用函数组件和 Hooks，副作用放在 `useEffect` 或封装 hook。
- API 响应先定义类型并进行必要的运行时形状检查。
- 聊天流使用原生 Fetch ReadableStream，不使用 EventSource 或 Axios 替代。
- 每次修改后运行 ESLint、TypeScript 检查和 production build。

## 9. 数据库迁移规范

- 所有结构变化必须有 Alembic revision。
- 应用启动不得调用 `Base.metadata.create_all()` 代替迁移。
- 已应用迁移不得重写；创建新迁移向前演进。
- SQLite 迁移考虑 batch mode、外键和降级。
- 每次迁移必须从空数据库运行 `alembic upgrade head` 并测试目标表/索引。

## 10. 文件安全规范

- 任何文件访问都同时校验 `thread_id`、`file_id` 和最终路径归属。
- 模型和客户端不得传入任意绝对路径。
- 文件名校验路径穿越、分隔符、Windows 保留名、空名和非法字符。
- 实际保存名使用服务端 ID 前缀；不得仅以原名保存或静默覆盖。
- 响应、SSE 和错误不得泄露绝对路径、文件内容、密钥或内部网络地址。
- HTML 只能在受限 iframe 预览；Web fetch 必须防 SSRF 并复检重定向。

## 11. 测试要求

- 核心逻辑、API、数据库迁移、安全边界和失败路径必须有测试。
- 后端运行 pytest、Ruff 和 mypy；前端运行 lint、typecheck 和 production build。
- 测试使用临时目录/数据库，不污染开发数据。
- 测试必须验证真实行为，不得用无意义 mock 掩盖错误。
- 未实际验证的任务不得标记 DONE。

## 12. Windows 兼容要求

- 支持 Windows 10/11 和 PowerShell。
- 文档命令使用 PowerShell 语法，不依赖 Bash。
- 路径全部通过 `pathlib.Path` 和平台 API 处理。
- 不依赖 Linux 专用命令、文件权限语义或目录。
- 文件名处理必须覆盖 Windows 保留名、反斜杠和大小写问题。

## 13. 每次任务开始前必须阅读

依次阅读：

1. `AGENTS.md`
2. `docs/PRD.md`
3. `docs/ARCHITECTURE.md`
4. `docs/IMPLEMENTATION_PLAN.md`
5. `docs/API_SPEC.md`
6. `docs/DATABASE_DESIGN.md`
7. `docs/SSE_PROTOCOL.md`
8. `docs/TASKS.md`
9. `docs/PROGRESS.md`

并检查当前 Git 状态，保留用户已有修改。

## 14. 每次任务结束后必须检查

- 运行当前 Phase 要求的后端和前端测试、静态检查与构建。
- 若有数据库变更，从空数据库执行迁移。
- 搜索并说明新增的 `TODO`、`pass`、跳过测试和临时实现；无正当理由必须清除。
- 检查密钥、绝对路径、固定 `thread_id` 和敏感错误泄露。
- 更新 `docs/TASKS.md` 与 `docs/PROGRESS.md`，只标记已验证工作。
- 确认没有提前实现下一 Phase。

## 15. 禁止伪造检查结果

不得通过删除测试、降低断言、添加无意义 mock、`skip`/`xfail` 或关闭 lint/type
规则让检查通过。失败时必须定位并修复本次变更导致的问题，随后重新运行。

## 16. 禁止空实现

不得留下未说明的 `pass`、`TODO`、`NotImplementedError`、空函数、空组件或固定成功
返回来冒充能力。计划中的后续 Phase 只写入设计文档，不在代码中创建假接口。

## 17. 禁止硬编码

不得硬编码 API Key、密码、令牌、系统绝对路径、数据库连接秘密或固定
`thread_id`。非敏感默认值集中放在配置模型中，密钥只来自环境变量且不得提交。

## 18. Phase 纪律

每次只实现用户明确指定的 Phase。不得以“架构完整”“提前铺路”为由实现后续
业务能力。跨 Phase 的表结构或协议可以按已批准设计先定义，但不得创建可调用的
假业务接口。阶段完成后只列出下一阶段计划，不主动开始。

