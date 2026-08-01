# AgentFlow V1 发布验收记录

## 1. 验收范围

本记录对应 `docs/PRD.md` 第 15、16 节和 Phase 7 的完成定义。验收以自动化测试、
静态检查、空库迁移和真实浏览器人工检查组成。外部模型与 Tavily 凭据不进入仓库，
第三方协议通过真实 HTTP 客户端路径和受控测试服务验证。

## 2. V1 完成定义

| 场景 | 证据 | 结论 |
|---|---|---|
| 普通对话 | `tests/integration/test_v1_workflow.py` 覆盖创建会话、SSE 增量、成功消息持久化和进程重启恢复 | 通过 |
| 联网报告 | `test_web_tools.py`、`test_web_search_service.py`、`test_web_fetch_service.py` 覆盖 search/fetch、来源、失败继续和 SSRF；完整工作流覆盖 `write_file` 与 Artifact 交付 | 通过 |
| 上传文档分析 | 完整工作流真实上传 Markdown，经 `list_files → read_file → write_file` 生成、预览、下载并重启恢复；各 Parser 独立覆盖 PDF/DOCX/TXT/MD/CSV | 通过 |
| 异常恢复 | chat、tool executor 与 recovery tests 覆盖模型失败、工具异常/超时/取消、SSE 关闭、进程遗留状态和删除事务补偿 | 通过 |
| 安全隔离 | 文件、Artifact、完整工作流和 storage tests 覆盖跨会话拒绝、路径穿越、Windows 文件名、受控路径及响应不泄露 | 通过 |

## 3. 验收标准映射

| 类别 | 自动化或人工证据 | 结论 |
|---|---|---|
| 对话 | 会话 CRUD、20 轮上下文、SSE 顺序、409 并发、失败与断连测试；前端权威回读测试 | 通过 |
| Agent Loop | 直接回答、一次/多次顺序工具、参数错误、重复、超时、异常、取消和最大循环测试 | 通过 |
| 搜索与网页 | 中英文、限制、去重、正文、截断、来源、超时、重定向复检、DNS 混合结果与连接对端复检 | 通过 |
| 文件 | 五类解析、OCR 状态、MIME/实际格式、大小、编码、CSV 500 行、list/read/write、同名与跨会话测试 | 通过 |
| 持久化 | 六张业务表迁移；完整工作流关闭首个 app 后以新 app 恢复会话、消息、文件和 Artifact | 通过 |
| Web 工作台 | 前端 SSE/API/状态恢复测试；Phase 6 在 1280px 与 390px 真实浏览器验证三栏/堆叠、预览、下载和 HTML 脚本不执行 | 通过 |
| 工程质量 | pytest、Ruff、mypy、Vitest、ESLint、TypeScript、production build、依赖检查、空库迁移与源码扫描 | 通过 |

## 4. 安全验收

- URL 仅允许公网 HTTP(S)，拒绝凭据、localhost、回环、私网、链路本地、元数据、
  非全局地址、混合 DNS 和非 HTTP 协议。
- 每次重定向重新校验 URL；建立连接后再次校验实际 socket peer，关闭 DNS 重绑定
  的解析与连接竞态。
- 文件访问同时校验数据库 `thread_id`/`file_id`、固定目录类型、规范 UUID 和解析后
  路径归属；模型不能提交服务器路径。
- 删除操作先暂存文件系统对象，再提交数据库；启动恢复根据权威元数据决定恢复或
  清理，并移除无元数据的服务端受控文件。
- HTML 预览响应使用严格 CSP、`nosniff`、`no-store`；前端 iframe 使用空权限
  `sandbox`。Markdown/HTML 不直接成为主页面 DOM 中的可执行脚本。
- API 请求 ID 由服务端生成。验证错误、SSE 与普通错误响应不反射密钥、绝对路径、
  堆栈、数据库连接信息或完整工具正文。

## 5. 发布门禁命令

从仓库根目录按 PowerShell 执行：

```powershell
Set-Location backend
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m mypy app tests
.\.venv\Scripts\python.exe -s -m pip check
.\.venv\Scripts\python.exe -m alembic current
.\.venv\Scripts\python.exe -m alembic check
Set-Location ..\frontend
npm run test
npm run lint
npm run typecheck
npm run build
npm audit --audit-level=high
```

Conda 前缀环境使用 `backend\.venv\python.exe`。空库迁移还需在独立临时目录执行
`alembic upgrade head`，确认版本为 `20260731_0001 (head)`，业务表和关键索引存在。

## 6. 外部服务边界

发布验收环境未保存真实模型或 Tavily 密钥，因此不把某一家第三方服务的在线可用性
伪报为项目测试结果。模型与搜索的鉴权、请求体、流式增量、tool calling、错误映射和
来源持久化均通过 `httpx` 真实请求栈的受控 transport 覆盖。部署者配置凭据后，仍应
执行一次普通对话、一次 Tavily 搜索和一次联网 Artifact 报告作为环境冒烟测试。
