# AgentFlow V1 产品需求文档

## 1. 文档信息

| 项目 | 内容 |
|---|---|
| 项目名称 | AgentFlow |
| 产品版本 | V1.0 |
| 项目类型 | 轻量级通用 Agent Web 工作台 |
| 使用方式 | 单用户、本地部署 |
| 文档状态 | 已确认，可进入开发 |
| 需求基准 | 本文件为 V1 唯一正式需求基准 |
| 最后更新时间 | 2026-07-31 |

---

## 2. 项目背景

DeerFlow 是一个包含主 Agent、子 Agent、Skills、MCP、沙箱、长期记忆、文件系统、多模型和多渠道接入等能力的完整超级智能体框架。

AgentFlow V1 不追求复制 DeerFlow 的全部功能，而是保留其最核心、最可落地的执行闭环：

```text
用户输入
  → 大模型理解任务
  → 大模型判断是否需要调用工具
  → 系统执行搜索、网页读取或文件工具
  → 工具结果返回给大模型
  → 大模型继续分析
  → 生成最终回答或文件
  → 保存会话、消息、文件和执行记录
```

第一版目标是完成一个结构清晰、能够真实运行、便于后续扩展的单 Agent 系统。

---

## 3. 项目目标

AgentFlow V1 必须实现以下六个核心模块：

1. 对话与流式输出
2. 单主 Agent 工具调用循环
3. Web 搜索与网页正文读取
4. 文件上传、解析、读取与生成
5. SQLite 会话持久化
6. 简单 Web 工作台

最终用户应能够完成以下任务：

- 与 Agent 进行多轮对话
- 搜索互联网信息
- 读取网页正文
- 上传并分析 PDF、DOCX、TXT、Markdown、CSV
- 让 Agent 生成 Markdown、HTML、CSV、JSON 和代码文件
- 查看 Agent 的工具执行状态
- 查看和下载生成文件
- 关闭并重启服务后恢复历史会话和文件

---

## 4. 产品定位

AgentFlow V1 是一个轻量级单 Agent 工作台，不是完整的多 Agent 平台，也不是 RAG 知识库系统。

第一版重点验证：

- Agent Loop 是否稳定
- 工具调用是否可靠
- 搜索和网页读取是否可用
- 文件上传和读取是否安全
- 文件生成是否可交付
- 会话和执行记录是否可持久化
- 前后端交互是否顺畅

---

## 5. 目标用户

第一版面向本地单用户使用。

典型用户包括：

- 需要进行资料检索和总结的用户
- 需要分析 PDF、DOCX、CSV 的用户
- 需要生成报告、代码或结构化文件的用户
- 希望体验 Agent 工具调用流程的开发者
- 希望在此基础上继续扩展多 Agent、Skills 或 MCP 的开发者

---

## 6. 核心用户场景

### 6.1 普通多轮对话

用户创建会话并输入：

```text
请介绍一下什么是 Agent Loop。
```

系统应：

1. 保存用户消息。
2. 加载当前会话历史。
3. 调用大模型。
4. 不调用工具。
5. 流式返回回答。
6. 保存助手消息。
7. 更新会话更新时间。

### 6.2 联网研究

用户输入：

```text
搜索近期 Agent 框架的发展情况，并生成一份 Markdown 报告。
```

系统应：

1. 调用 `web_search`。
2. 根据搜索结果调用 `web_fetch`。
3. 保存实际使用的来源。
4. 模型整理资料。
5. 调用 `write_file` 生成 Markdown 报告。
6. 前端展示生成文件。
7. 最终回答中展示报告入口和参考来源。

### 6.3 文档分析

用户上传：

```text
requirements.docx
```

然后输入：

```text
分析这个需求文档，整理功能模块和风险点，并生成报告。
```

系统应：

1. 保存原始 DOCX。
2. 将 DOCX 解析为统一文本或 Markdown。
3. Agent 调用 `list_files`。
4. Agent 调用 `read_file`。
5. Agent 分析文件内容。
6. Agent 调用 `write_file`。
7. 前端展示生成的报告。
8. 会话、文件和工具记录持久化。

### 6.4 指定网页总结

用户输入：

```text
总结这个网页：https://example.com/article
```

系统应：

1. 校验 URL。
2. 调用 `web_fetch`。
3. 提取网页标题和正文。
4. 清洗无关内容。
5. 将正文返回给模型。
6. 模型生成总结。
7. 保存来源。

### 6.5 网页访问失败

Agent 调用 `web_fetch` 时网页无法访问。

系统应：

1. 返回结构化工具错误。
2. 保存失败工具记录。
3. 将错误返回给模型。
4. 模型可以选择其他来源或向用户说明。
5. 整个会话不得崩溃。

### 6.6 扫描版 PDF

用户上传无法提取文本的扫描版 PDF。

系统应：

1. 保存原始 PDF。
2. 尝试提取文本。
3. 检测到有效文本过少。
4. 将解析状态标记为 `unsupported_ocr`。
5. 明确提示第一版不支持 OCR。
6. 不得将空白解析结果交给模型冒充有效内容。

### 6.7 会话恢复

用户完成一次文档分析后关闭服务。

重新启动服务后，应恢复：

- 会话标题
- 用户消息
- Agent 回复
- 上传文件
- 解析文件
- 生成文件
- 工具调用记录
- 来源信息

### 6.8 跨会话文件隔离

会话 A 中的 Agent 尝试读取会话 B 的文件。

系统应：

1. 校验文件所属 `thread_id`。
2. 拒绝访问。
3. 返回 `FILE_ACCESS_DENIED`。
4. 不返回真实服务器路径。
5. 不泄露文件内容。

---

# 7. V1 功能范围

## 7.1 对话与流式输出

### 7.1.1 新建会话

用户可以创建新的聊天会话。

系统应：

- 为每个会话生成唯一 `thread_id`
- 默认标题为“新会话”
- 保存创建时间和更新时间
- 创建独立线程目录
- 将会话写入 SQLite

### 7.1.2 历史会话

用户可以：

- 查看历史会话列表
- 按更新时间倒序排列
- 点击会话重新打开
- 查看全部历史消息
- 删除指定会话

删除会话时，应同步删除：

- 会话记录
- 消息记录
- Agent 运行记录
- 工具调用记录
- 来源记录
- 文件元数据
- 当前会话对应的本地文件目录

### 7.1.3 多轮上下文

系统必须支持多轮上下文对话。

每次发送消息时：

- 加载当前会话历史消息
- 按消息顺序构建上下文
- 将上下文发送给模型
- 不同会话之间完全隔离

第一版至少支持 20 轮连续对话。

### 7.1.4 流式回复

模型回答必须流式展示。

前端至少支持以下事件：

- `run_start`
- `assistant_start`
- `assistant_delta`
- `tool_start`
- `tool_result`
- `artifact_created`
- `assistant_end`
- `run_end`
- `error`

### 7.1.5 工具执行状态

前端可以展示以下公开状态：

- 正在分析问题
- 正在搜索互联网
- 正在读取网页
- 正在查看上传文件
- 正在生成文件
- 文件已生成
- 工具执行失败

第一版不得展示模型私有思维链。

### 7.1.6 同一会话并发限制

当某个会话正在执行任务时：

- 前端禁止重复发送
- 后端禁止同一个 `thread_id` 同时存在两个运行中的任务
- 重复请求返回 HTTP 409
- 不同会话可以独立执行

### 7.1.7 模型异常处理

当模型调用失败时：

- 后端服务不得崩溃
- 当前 run 标记为 `failed`
- 前端展示明确错误
- 已保存的用户消息不得丢失
- 不创建虚假的助手成功消息

### 7.1.8 会话标题

第一版支持简单标题生成。

规则：

- 默认标题为“新会话”
- 首轮对话成功后，根据首条用户消息生成标题
- 可采用截取首条消息前若干字符的简单规则
- 第一版不要求额外调用模型生成标题

---

## 7.2 单主 Agent 工具调用循环

### 7.2.1 单 Agent 架构

第一版只实现一个主 Agent。

不实现：

- 子 Agent
- 多 Agent 协同
- Agent 动态创建
- Agent 角色管理
- 并行子任务
- 主从 Agent 编排

### 7.2.2 Agent 执行流程

```text
用户消息
  → 调用大模型
  → 模型判断是否调用工具
  → 无工具调用：生成最终回复
  → 有工具调用：执行工具
  → 工具结果作为 ToolMessage 返回模型
  → 再次调用模型
  → 直到生成最终回复
```

### 7.2.3 内置工具

第一版必须实现：

- `web_search`
- `web_fetch`
- `list_files`
- `read_file`
- `write_file`

开发 Agent Loop 时可以临时增加测试工具：

- `get_current_time`

测试工具仅用于验证工具调用闭环，不属于最终产品核心功能。

### 7.2.4 Tool Registry

系统应提供统一的 Tool Registry，用于：

- 注册工具
- 根据名称查找工具
- 读取工具描述
- 获取参数模型
- 校验工具参数
- 执行工具
- 返回统一结果

### 7.2.5 工具参数校验

所有工具参数必须使用 Pydantic 模型校验。

参数不合法时：

- 不执行工具
- 返回结构化错误
- 将错误作为工具结果返回 Agent
- Agent 可以修正参数后重试

### 7.2.6 工具执行记录

每次工具调用必须保存：

- `tool_call_id`
- `run_id`
- `thread_id`
- 工具名称
- 输入参数
- 执行状态
- 执行结果摘要
- 错误原因
- 开始时间
- 结束时间
- 执行耗时

### 7.2.7 最大循环次数

单次任务必须限制 Agent Loop 次数。

默认建议：

```text
MAX_AGENT_LOOPS = 10
```

达到上限时：

- 停止继续调用工具
- 将 run 状态标记为 `max_loops_reached`
- 向用户说明任务执行步骤过多
- 不得无限循环

### 7.2.8 重复工具调用检测

重复调用依据：

```text
工具名称 + 规范化后的工具参数
```

当 Agent 连续多次调用相同工具和相同参数时：

- 阻止继续执行
- 返回重复调用错误
- 保存对应工具调用记录
- Agent 可以调整参数或结束任务

### 7.2.9 工具超时

每个工具必须设置超时时间。

超时后：

- 终止当前工具执行
- 保存超时状态
- 返回结构化错误
- Agent 可以选择其他方案
- 整个任务不得永久挂起

### 7.2.10 工具异常

工具内部发生异常时：

- 捕获异常
- 记录日志
- 保存失败记录
- 转换为 ToolMessage
- 不向前端泄露堆栈和绝对路径
- 不导致 FastAPI 进程崩溃

---

## 7.3 Web 搜索与网页读取

### 7.3.1 Web 搜索工具

系统应实现 `web_search`。

输入参数：

- `query`
- `max_results`

输出字段：

- `title`
- `url`
- `snippet`

要求：

- 支持中文和英文关键词
- 默认返回 5 条
- 最多返回 10 条
- 过滤没有 URL 的结果
- URL 去重
- 搜索失败返回结构化错误
- 工具内部不生成最终总结
- 搜索供应商通过配置提供
- API Key 不得硬编码

### 7.3.2 网页读取工具

系统应实现 `web_fetch`。

输入参数：

- `url`
- `max_chars`

要求：

- 仅允许 HTTP 和 HTTPS
- 下载网页 HTML
- 提取网页标题
- 提取主要正文
- 去除脚本、样式、导航栏和无关内容
- 对超长内容进行截断
- 返回是否被截断
- 请求失败时返回明确错误
- 请求超时时返回明确错误

### 7.3.3 URL 安全

`web_fetch` 必须防止 SSRF。

禁止访问：

- `localhost`
- `127.0.0.1`
- `0.0.0.0`
- IPv6 回环地址
- 私有网络 IP
- 链路本地地址
- 云服务元数据地址
- `file://`
- `ftp://`
- 非 HTTP 协议

重定向后的最终地址必须重新校验。

### 7.3.4 来源记录

系统使用搜索和网页工具时，应保存实际使用的来源：

- 标题
- URL
- 摘要
- 来源类型
- `run_id`
- `thread_id`
- 创建时间

最终回答应展示实际使用的参考来源。

### 7.3.5 不实现的网页能力

第一版不实现：

- 浏览器自动点击
- 网页登录
- Cookie 管理
- 验证码识别
- JavaScript 页面交互
- 递归爬虫
- 全站爬取
- 浏览器自动化

---

## 7.4 文件上传、解析、读取和生成

### 7.4.1 支持上传格式

第一版支持：

- PDF
- DOCX
- TXT
- Markdown
- CSV

允许扩展名：

```text
.pdf
.docx
.txt
.md
.csv
```

### 7.4.2 不支持格式

第一版不支持：

- PPTX
- XLSX
- 图片 OCR
- 音频
- 视频
- 压缩包
- 可执行文件
- 扫描版 PDF OCR
- 图片理解

### 7.4.3 文件上传校验

上传时必须校验：

- `thread_id` 是否存在
- 文件扩展名
- MIME 类型
- 文件大小
- 文件名是否合法
- 是否存在路径穿越字符
- 文件是否为空

建议默认限制：

```text
MAX_UPLOAD_SIZE_MB = 20
```

限制必须支持通过配置修改。

### 7.4.4 文件目录隔离

每个会话拥有独立目录：

```text
data/
└── threads/
    └── {thread_id}/
        ├── uploads/
        ├── parsed/
        └── outputs/
```

说明：

- `uploads`：原始上传文件
- `parsed`：解析后的统一文本
- `outputs`：Agent 生成文件

不同 `thread_id` 之间不得互相访问文件。

### 7.4.5 文件保存名称

实际存储名称不得只使用原始文件名。

建议格式：

```text
{file_id}_{safe_filename}
```

必须处理：

- 同名文件
- 中文文件名
- 空格
- 特殊字符
- 路径穿越字符
- Windows 保留文件名
- Windows 路径兼容问题

### 7.4.6 统一解析结果

无论上传何种格式，都应转换成统一的文本或 Markdown。

示例：

```text
uploads/合同.docx
parsed/合同.md
```

解析文件与原始文件之间必须建立关联。

### 7.4.7 PDF 解析

使用 PyMuPDF 提取文本。

输出格式示例：

```markdown
# 文件：example.pdf

## 第 1 页

页面文本

## 第 2 页

页面文本
```

如果 PDF 有页面但有效文本过少：

- `parse_status = unsupported_ocr`
- 返回明确提示
- 不生成虚假解析内容

### 7.4.8 DOCX 解析

使用 `python-docx`。

至少提取：

- 标题
- 普通段落
- 列表
- 表格

表格尽量转换为 Markdown 表格。

### 7.4.9 CSV 解析

CSV 解析应：

- 尝试检测常见编码
- 读取列名
- 统计总行数
- 默认最多读取前 500 行
- 标记是否截断
- 转换为 Markdown 表格或结构化文本

### 7.4.10 TXT 和 Markdown 解析

应：

- 优先使用 UTF-8
- 失败后尝试常见中文编码
- 统一转换为 UTF-8
- 保留原始段落结构
- 限制最大解析字符数

### 7.4.11 文件列表工具

系统应实现 `list_files`。

Agent 可以查看当前会话中的：

- 原始上传文件
- 解析文件
- 生成文件
- 文件 ID
- 文件名
- 文件类型
- 解析状态
- 文件大小

### 7.4.12 文件读取工具

系统应实现 `read_file`。

要求：

- 只接收 `file_id`
- 不接收任意绝对路径
- 校验文件属于当前 `thread_id`
- 二进制文件优先读取解析版本
- 支持最大字符数
- 支持按行读取
- 超长内容返回 `truncated`
- 不向模型暴露真实服务器路径

### 7.4.13 文件生成工具

系统应实现 `write_file`。

支持生成：

- Markdown
- TXT
- HTML
- CSV
- JSON
- Python
- JavaScript
- TypeScript
- YAML

允许扩展名：

```text
.md
.txt
.html
.csv
.json
.py
.js
.ts
.yaml
.yml
```

要求：

- 只能写入当前线程 `outputs`
- 禁止绝对路径
- 禁止 `..`
- 禁止 `/`
- 禁止 `\`
- 自动处理重名文件
- 保存文件元数据
- 生成后发送 `artifact_created`
- 不允许覆盖当前线程之外的文件

建议默认限制：

```text
MAX_ARTIFACT_SIZE_MB = 5
```

### 7.4.14 文件预览

前端支持：

| 文件类型 | 预览方式 |
|---|---|
| Markdown | Markdown 渲染 |
| TXT | 纯文本 |
| JSON | 格式化 JSON |
| CSV | 表格 |
| Python | 代码高亮 |
| JavaScript | 代码高亮 |
| TypeScript | 代码高亮 |
| YAML | 代码高亮 |
| HTML | 受限 iframe |

HTML 不得直接插入主页面 DOM。

---

## 7.5 会话持久化

### 7.5.1 数据库

第一版使用 SQLite。

数据库至少保存：

- `threads`
- `messages`
- `runs`
- `tool_calls`
- `files`
- `sources`

### 7.5.2 threads

至少包含：

- `id`
- `title`
- `status`
- `created_at`
- `updated_at`

### 7.5.3 messages

至少包含：

- `id`
- `thread_id`
- `run_id`
- `role`
- `content`
- `message_type`
- `metadata`
- `sequence_number`
- `created_at`

消息角色：

- `user`
- `assistant`
- `tool`
- `system`

消息类型：

- `text`
- `tool_call`
- `tool_result`
- `error`

### 7.5.4 runs

每次用户发送消息时创建一个 run。

状态至少包括：

- `pending`
- `running`
- `success`
- `failed`
- `cancelled`
- `max_loops_reached`

### 7.5.5 tool_calls

保存：

- 工具名称
- 参数
- 结果
- 状态
- 错误
- 耗时
- 开始时间
- 结束时间

### 7.5.6 files

保存：

- 原始文件
- 解析文件
- 生成文件
- 文件关联关系
- MIME 类型
- 文件大小
- 解析状态
- 文件路径
- 创建时间

### 7.5.7 sources

保存：

- 标题
- URL
- 摘要
- 来源类型
- 所属 run
- 所属 thread

### 7.5.8 服务重启恢复

服务重新启动后，必须恢复：

- 历史会话
- 历史消息
- 上传文件
- 解析结果
- Agent 生成文件
- 工具调用记录
- 来源信息

---

## 7.6 简单 Web 工作台

### 7.6.1 页面布局

页面采用三栏布局：

```text
左侧：历史会话
中间：聊天区域
右侧：文件与 Artifact
底部：输入框和上传按钮
```

### 7.6.2 左侧会话栏

支持：

- 新建会话
- 历史会话列表
- 当前会话高亮
- 显示标题
- 显示更新时间
- 切换会话
- 删除会话

### 7.6.3 中间聊天区

支持：

- 用户消息
- Agent 消息
- Markdown
- GFM 表格
- 代码高亮
- 流式文本
- 工具状态卡片
- 错误提示
- 自动滚动
- 历史消息恢复

### 7.6.4 底部输入区

支持：

- 多行文本输入
- Enter 发送
- Shift+Enter 换行
- 文件选择
- 已选择文件展示
- 发送按钮
- Agent 运行时禁止重复发送

### 7.6.5 右侧文件面板

分为：

- 上传文件
- 生成文件

支持：

- 文件名
- 文件大小
- 文件类型
- 解析状态
- 预览
- 下载
- 删除

### 7.6.6 流式交互

前端使用：

```text
POST + Fetch ReadableStream
```

不使用只支持 GET 的原生 EventSource 作为聊天请求方式。

---

# 8. 接口范围

## 8.1 健康检查

```text
GET /health
```

## 8.2 会话接口

```text
POST   /api/threads
GET    /api/threads
GET    /api/threads/{thread_id}
GET    /api/threads/{thread_id}/messages
DELETE /api/threads/{thread_id}
```

## 8.3 聊天接口

```text
POST /api/threads/{thread_id}/chat/stream
```

使用 POST 请求和流式响应。

## 8.4 文件接口

```text
POST   /api/threads/{thread_id}/files
GET    /api/threads/{thread_id}/files
GET    /api/threads/{thread_id}/files/{file_id}
DELETE /api/threads/{thread_id}/files/{file_id}
```

## 8.5 Artifact 接口

```text
GET /api/threads/{thread_id}/artifacts
GET /api/threads/{thread_id}/artifacts/{file_id}/preview
GET /api/threads/{thread_id}/artifacts/{file_id}/download
```

具体请求、响应和错误格式在 `docs/API_SPEC.md` 中定义。

---

# 9. SSE 事件范围

所有事件统一包含：

- `event_id`
- `event`
- `thread_id`
- `run_id`
- `timestamp`
- `data`

V1 事件：

### `run_start`

表示一轮执行开始。

### `assistant_start`

表示助手消息开始生成。

### `assistant_delta`

表示助手文本增量。

### `tool_start`

表示工具开始执行。

### `tool_result`

表示工具执行完成或失败。

### `artifact_created`

表示生成了文件。

### `assistant_end`

表示助手最终消息完成。

### `run_end`

表示整轮执行结束。

### `error`

表示发生模型、工具、流式或服务错误。

具体事件结构在 `docs/SSE_PROTOCOL.md` 中定义。

---

# 10. 错误码范围

第一版至少定义：

- `THREAD_NOT_FOUND`
- `THREAD_BUSY`
- `MESSAGE_EMPTY`
- `MODEL_REQUEST_FAILED`
- `MAX_AGENT_LOOPS_REACHED`
- `TOOL_NOT_FOUND`
- `TOOL_ARGUMENT_INVALID`
- `TOOL_EXECUTION_FAILED`
- `TOOL_TIMEOUT`
- `DUPLICATE_TOOL_CALL`
- `FILE_NOT_FOUND`
- `FILE_ACCESS_DENIED`
- `FILE_TYPE_UNSUPPORTED`
- `FILE_TOO_LARGE`
- `FILE_PARSE_FAILED`
- `OCR_NOT_SUPPORTED`
- `INVALID_FILENAME`
- `ARTIFACT_TOO_LARGE`
- `URL_NOT_ALLOWED`
- `WEB_SEARCH_FAILED`
- `WEB_FETCH_FAILED`
- `INTERNAL_ERROR`

错误响应不得泄露：

- 服务器绝对路径
- Python 堆栈
- API Key
- 数据库连接信息
- 内部网络地址

---

# 11. 非功能需求

## 11.1 安全性

系统必须防止：

- 路径穿越
- 跨会话文件访问
- 任意文件读取
- 任意文件写入
- SSRF
- 不安全 HTML 执行
- 非法文件上传
- API Key 硬编码
- 服务器绝对路径泄露
- SQL 注入
- 任意协议访问

## 11.2 稳定性

系统必须保证：

- 工具异常不导致服务崩溃
- 模型异常不导致历史消息丢失
- SSE 断开后 run 状态正确更新
- 达到最大循环次数后停止
- 同一会话不能并发执行多个任务
- 删除会话时数据库和文件保持一致
- 失败任务保留错误记录
- 文件解析失败不影响其他文件

## 11.3 可维护性

代码要求：

- 模块职责清晰
- API、Service、Repository 分层
- Tool Registry 统一管理工具
- Parser Registry 统一管理文件解析器
- 使用 Pydantic 定义请求和工具参数
- 使用 SQLAlchemy 2 管理数据库
- 使用 Alembic 管理迁移
- 核心逻辑必须有测试
- 不得使用空实现冒充完成
- 不得通过删除测试让检查通过

## 11.4 Windows 兼容性

项目必须能在 Windows 10/11 本地运行。

要求：

- 路径使用 `pathlib.Path`
- 不依赖 Linux 专用 Shell 命令
- 启动命令兼容 PowerShell
- 文件名处理兼容 Windows
- 不硬编码 `/tmp`
- 不硬编码 Linux 目录
- 文档中提供 Windows 启动说明

## 11.5 性能要求

第一版不追求大规模并发，但应满足：

- 会话列表普通查询响应小于 1 秒
- 文件列表普通查询响应小于 1 秒
- 普通流式对话应尽快返回首个事件
- 文件上传大小默认不超过 20 MB
- 单个 Artifact 默认不超过 5 MB
- 网页抓取和工具执行必须设置超时
- 超长网页和文件内容必须截断

## 11.6 配置管理

以下内容通过环境变量或配置文件提供：

- 模型 API 地址
- 模型 API Key
- 模型名称
- 搜索 API Key
- 数据库路径
- 数据目录
- 上传大小限制
- Artifact 大小限制
- Agent 最大循环次数
- 工具超时时间
- 网页抓取超时时间
- CORS 地址
- 日志级别

密钥不得提交到 Git。

---

# 12. 固定技术栈

## 12.1 后端

- Python 3.12
- FastAPI
- Uvicorn
- LangGraph
- LangChain
- Pydantic v2
- SQLAlchemy 2
- Alembic
- SQLite
- httpx
- BeautifulSoup4
- readability-lxml
- PyMuPDF
- python-docx
- pandas
- pytest

## 12.2 前端

- React
- Vite
- TypeScript
- Ant Design
- Zustand
- React Markdown
- remark-gfm
- rehype-highlight
- Fetch ReadableStream

## 12.3 存储

- SQLite：结构化数据
- 本地文件系统：上传文件、解析文件和生成文件

---

# 13. V1 明确不实现

以下内容不属于 V1：

- 多 Agent
- 子 Agent
- 子任务并发
- Plan/Todo
- Skills 系统
- MCP
- 长期记忆
- Docker 沙箱
- Kubernetes
- Redis
- Celery
- RAG
- 向量数据库
- Embedding
- Reranker
- OCR
- 图片理解
- PPTX 解析
- XLSX 复杂解析
- 浏览器自动化
- 网页登录
- 验证码
- 音频生成
- 视频生成
- 图片生成
- PPT 生成
- 用户注册
- 用户登录
- 权限系统
- 多租户
- 飞书接入
- Slack 接入
- Telegram 接入
- 多模型动态切换
- 分布式部署
- 微服务拆分

开发过程中不得擅自添加以上功能。

---

# 14. 开发阶段

V1 固定拆分为以下阶段：

## Phase 1

项目脚手架、配置、数据库和健康检查。

## Phase 2

会话 CRUD、消息持久化和普通流式对话。

## Phase 3

LangGraph Agent Loop、Tool Registry 和测试工具。

## Phase 4

`web_search` 和 `web_fetch`。

## Phase 5

文件上传、解析、`list_files` 和 `read_file`。

## Phase 6

`write_file`、Artifact 和完整 Web 工作台。

## Phase 7

安全、异常处理、自动化测试和文档完善。

不得提前开发后续 Phase。

---

# 15. V1 验收标准

## 15.1 对话

- 可以创建多个会话
- 不同会话消息互相隔离
- 支持至少 20 轮多轮对话
- 模型回复流式展示
- 页面刷新后消息存在
- 服务重启后会话存在
- 模型失败时有明确提示
- 同一会话不能同时执行两个任务

## 15.2 Agent Loop

- 普通问题可以直接回答
- 需要工具时模型可以自主调用
- 工具结果能返回模型
- 一轮任务可以连续调用多个工具
- 达到最大循环次数后安全停止
- 重复工具调用被阻止
- 工具异常不会导致服务崩溃
- 工具调用记录持久化

## 15.3 搜索与网页

- 能根据关键词搜索
- 能读取网页正文
- 能处理网页访问失败
- 能保存来源
- 最终回答展示来源
- SSRF 测试通过
- 重定向后的 URL 会再次检查

## 15.4 文件

- 能上传 PDF、DOCX、TXT、MD、CSV
- 能生成解析文件
- Agent 能读取上传文件
- 扫描 PDF 有明确提示
- 不同会话不能互相读取文件
- Agent 能生成 Markdown、HTML、CSV、JSON 和代码文件
- 用户能预览和下载生成文件
- 文件名和路径安全测试通过

## 15.5 持久化

- 会话写入 SQLite
- 消息写入 SQLite
- run 写入 SQLite
- tool_call 写入 SQLite
- 文件元数据写入 SQLite
- 来源写入 SQLite
- 服务重启后数据不丢失

## 15.6 Web 工作台

- 有历史会话栏
- 有聊天区域
- 有输入框
- 有文件上传
- 有文件和 Artifact 面板
- 支持 Markdown
- 支持代码高亮
- 支持流式状态
- 支持预览和下载
- 运行中禁止重复发送

## 15.7 工程质量

- 后端测试通过
- 前端 lint 通过
- TypeScript 检查通过
- 前端 production build 通过
- Alembic 可以从空数据库执行
- README 启动命令真实有效
- 不存在未说明的 `pass`
- 不存在假实现
- 不存在硬编码密钥
- 不存在跨线程数据泄露

---

# 16. V1 完成定义

当以下端到端场景全部通过时，AgentFlow V1 视为完成。

## 16.1 普通对话

```text
创建会话
→ 发送问题
→ 模型流式回答
→ 刷新页面
→ 历史消息恢复
```

## 16.2 联网报告

```text
发送联网研究任务
→ web_search
→ web_fetch
→ 模型整理资料
→ write_file 生成报告
→ 前端预览和下载
→ 最终回答展示来源
```

## 16.3 上传文档分析

```text
上传 DOCX 或 PDF
→ 系统解析
→ Agent 读取文件
→ Agent 分析文档
→ Agent 生成 Markdown 报告
→ 前端展示 Artifact
→ 服务重启后数据仍存在
```

## 16.4 异常恢复

```text
工具或模型失败
→ 错误被记录
→ 前端显示错误
→ 服务不崩溃
→ 其他会话仍可正常使用
```

## 16.5 安全隔离

```text
会话 A 尝试读取会话 B 文件
→ 后端拒绝
→ 返回 FILE_ACCESS_DENIED
→ 不泄露路径和内容
```

---

# 17. 后续版本规划

## V1.1

- 上下文自动摘要
- 大文件分段读取
- 用户主动取消任务
- 模型失败重试
- 多模型选择

## V1.2

- 简单长期记忆
- Skills 目录
- XLSX 解析
- PPTX 解析
- 图片理解

## V2

- 子 Agent
- Plan/Todo
- MCP
- Docker 沙箱
- 多用户和权限

以上后续版本不属于当前 V1 开发范围。
