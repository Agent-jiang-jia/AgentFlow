# AgentFlow V1 任务清单

状态只允许：`TODO`、`IN_PROGRESS`、`DONE`、`BLOCKED`。

| 任务编号 | Phase | 任务说明 | 涉及文件 | 前置依赖 | 验收标准 | 测试方式 | 状态 |
|---|---:|---|---|---|---|---|---|
| P0-01 | 0 | 阅读 PRD 与 Word，记录边界、冲突和决策 | `docs/*` | 无 | 正式基准与补充材料已审阅 | 文档人工核对 | DONE |
| P0-02 | 0 | 创建架构、计划、API、数据库、SSE 文档 | `docs/ARCHITECTURE.md` 等 | P0-01 | 七份指定文档结构完整 | 文档链接和章节核对 | DONE |
| P0-03 | 0 | 创建长期工程约束 | `AGENTS.md` | P0-01 | 包含用户要求的 18 类约束 | 文档人工核对 | DONE |
| P1-01 | 1 | 后端脚手架与依赖配置 | `backend/pyproject.toml`, `backend/app/*` | P0-03 | Python 3.12 工程可安装、导入 | 安装、Ruff、mypy | DONE |
| P1-02 | 1 | 配置、CORS、JSON 日志与统一异常 | `backend/app/core/*`, `main.py` | P1-01 | `.env` 生效，错误不泄密 | pytest、静态检查 | DONE |
| P1-03 | 1 | SQLAlchemy 2 与 SQLite 基础 | `backend/app/db/*` | P1-01 | 可连接 SQLite，启用外键 | pytest | DONE |
| P1-04 | 1 | Alembic 与首个六表迁移 | `backend/alembic/*`, `alembic.ini` | P1-03 | 空库升级到 head 且六表存在 | Alembic、pytest | DONE |
| P1-05 | 1 | 健康检查接口 | `backend/app/api/health.py` | P1-02, P1-03 | 正常 200、DB 故障 503 | pytest | DONE |
| P1-06 | 1 | 前端 Vite/React/TS/Ant Design 脚手架 | `frontend/*` | P0-03 | strict TS，基础页可构建 | lint、typecheck、build | DONE |
| P1-07 | 1 | 前端真实健康状态展示 | `frontend/src/*` | P1-05, P1-06 | 显示连接中/正常/异常 | lint、typecheck、build | DONE |
| P1-08 | 1 | README、环境示例和 Git 忽略 | `README.md`, `.gitignore`, `.env.example` | P1-01, P1-06 | PowerShell 命令可执行 | 按文档执行 | DONE |
| P1-09 | 1 | Phase 1 全套验证与进度记录 | `docs/PROGRESS.md`, `TASKS.md` | P1-01..08 | 所有要求命令有真实结果 | 全套命令 | DONE |
| P1-10 | 1 | Phase 1 严格审查与基础设施修复 | 后端生命周期/配置/测试、前端环境类型 | P1-01..09 | 无范围扩张，生命周期、配置、迁移和启动均实测通过 | 全套门禁与真实服务探测 | DONE |
| P2-01 | 2 | 会话 CRUD 与线程目录 | 后端 API/Service/Repository | Phase 1 | CRUD、排序、级联清理正确 | pytest | DONE |
| P2-02 | 2 | 消息持久化与 20 轮上下文 | 消息 Repository/Service | P2-01 | 顺序和线程隔离正确 | pytest | DONE |
| P2-03 | 2 | 普通模型流式对话和标题 | chat API/Service、SSE | P2-02 | 不调用工具即可流式对话 | pytest、集成测试 | DONE |
| P2-04 | 2 | 基础聊天前端 | 前端 API/store/components | P2-03 | 可创建、切换并恢复对话 | lint、typecheck、build | DONE |
| P3-01 | 3 | Tool Registry 与测试工具 | `app/tools/*` | Phase 2 | 注册、校验、调用闭环 | pytest | TODO |
| P3-02 | 3 | LangGraph 单 Agent 循环 | `app/agent/*` | P3-01 | 工具结果返回模型 | pytest | TODO |
| P3-03 | 3 | 循环/重复/超时保护和工具记录 | Agent/Service/Repository | P3-02 | 保护和持久化正确 | pytest | TODO |
| P3-04 | 3 | 前端工具公开状态 | 前端组件/store | P3-02 | 不展示思维链 | 前端检查 | TODO |
| P4-01 | 4 | `web_search` | 工具与搜索服务 | Phase 3 | 中英文、限制、去重可用 | pytest、集成测试 | TODO |
| P4-02 | 4 | `web_fetch` 与正文清洗 | 工具与抓取服务 | P4-01 | 正文、截断、错误可用 | pytest | TODO |
| P4-03 | 4 | SSRF 与重定向复检 | security/web_fetch | P4-02 | 私网等全部拒绝 | 安全测试 | TODO |
| P4-04 | 4 | 来源持久化和展示 | Repository/前端 | P4-01 | 只展示实际使用来源 | 集成测试 | TODO |
| P5-01 | 5 | 上传校验和线程目录隔离 | 文件 API/Storage | Phase 4 | 格式、MIME、大小和路径安全 | pytest | TODO |
| P5-02 | 5 | 五类文件解析 | `app/parsers/*` | P5-01 | 统一文本、OCR 状态正确 | 解析测试 | TODO |
| P5-03 | 5 | `list_files`/`read_file` | 工具/Service | P5-02 | 仅 file_id、跨线程拒绝 | pytest | TODO |
| P5-04 | 5 | 前端上传和文件列表 | 前端组件/store | P5-01 | 展示真实解析状态 | 前端检查 | TODO |
| P6-01 | 6 | `write_file` 安全生成 | 工具/Storage/Service | Phase 5 | 类型、路径、大小、重名正确 | pytest | TODO |
| P6-02 | 6 | Artifact 列表、预览、下载 | API/Service | P6-01 | 安全预览下载 | pytest | TODO |
| P6-03 | 6 | 完整三栏 Web 工作台 | 前端页面/组件 | P6-02 | 满足 PRD 工作台范围 | lint、build、人工验收 | TODO |
| P7-01 | 7 | 全链路异常、断连和恢复 | 后端核心模块 | Phase 6 | 失败状态一致且可恢复 | 集成测试 | TODO |
| P7-02 | 7 | 安全测试收口 | 安全/文件/Web/HTML | P7-01 | PRD 安全项通过 | 安全测试 | TODO |
| P7-03 | 7 | E2E、文档和发布验收 | 全项目 | P7-02 | V1 完成定义全部通过 | 全套自动/人工验证 | TODO |
