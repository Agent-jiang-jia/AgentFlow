# AgentFlow V1 数据库设计

## 1. 通用约定

- 数据库：SQLite，由 SQLAlchemy 2 访问，由 Alembic 独占结构变更。
- 表名、列名和索引名使用 snake_case。
- 主键使用服务端生成的 UUID 字符串。
- 时间在应用层使用 UTC；迁移的默认值使用 `CURRENT_TIMESTAMP` 作为兜底。
- JSON 数据使用 SQLAlchemy `JSON`，在 SQLite 中持久化为 JSON 文本。
- 每个连接启用 `PRAGMA foreign_keys=ON`、`busy_timeout`；文件数据库启用 WAL。
- 应用启动不调用 `metadata.create_all()`。

## 2. `threads`

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `id` | VARCHAR(36) | PK | thread UUID |
| `title` | VARCHAR(200) | NOT NULL | 默认“新会话” |
| `status` | VARCHAR(20) | NOT NULL, default `active` | `active` |
| `created_at` | DATETIME | NOT NULL | 创建时间 |
| `updated_at` | DATETIME | NOT NULL | 最后消息/资源变更时间 |

索引：`updated_at`，用于历史会话倒序查询。

删除：删除线程时数据库级联删除其余五表记录；Service 同时清理线程文件目录。

## 3. `runs`

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `id` | VARCHAR(36) | PK | run UUID |
| `thread_id` | VARCHAR(36) | FK threads, NOT NULL | 所属线程 |
| `status` | VARCHAR(20) | NOT NULL | pending/running/success/failed/cancelled/max_loops_reached |
| `user_message_id` | VARCHAR(36) | NULL | 触发 run 的消息逻辑引用 |
| `assistant_message_id` | VARCHAR(36) | NULL | 最终助手消息逻辑引用 |
| `loop_count` | INTEGER | NOT NULL, default 0 | Agent 调用轮数 |
| `error_code` | VARCHAR(100) | NULL | 公开错误码 |
| `error_message` | TEXT | NULL | 安全错误摘要 |
| `started_at` | DATETIME | NOT NULL | 开始时间 |
| `finished_at` | DATETIME | NULL | 结束时间 |

索引：

- `(thread_id, started_at)`：线程运行历史。
- 对 `status IN ('pending','running')` 的 `thread_id` 建唯一部分索引，数据库层
  防止同一线程有两个活动 run。

`user_message_id`/`assistant_message_id` 不设物理外键，避免 runs 与 messages 的
循环建表依赖；Phase 2 的 Service 在事务内维护其有效性。

删除：线程删除时级联删除 runs。

## 4. `messages`

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `id` | VARCHAR(36) | PK | message UUID |
| `thread_id` | VARCHAR(36) | FK threads, NOT NULL | 所属线程 |
| `run_id` | VARCHAR(36) | FK runs, NULL | 所属执行轮次 |
| `role` | VARCHAR(20) | NOT NULL | user/assistant/tool/system |
| `content` | TEXT | NOT NULL | 消息正文 |
| `message_type` | VARCHAR(30) | NOT NULL, default `text` | text/tool_call/tool_result/error |
| `metadata_json` | JSON | NOT NULL, default `{}` | 安全扩展元数据 |
| `sequence_number` | INTEGER | NOT NULL | 线程内严格递增序号 |
| `created_at` | DATETIME | NOT NULL | 创建时间 |

索引与约束：

- `UNIQUE(thread_id, sequence_number)` 保证消息顺序不重复。
- `(thread_id, created_at)` 支持历史查询。
- `run_id` 普通索引支持一次执行的消息查询。

删除：线程删除时级联；单独删除 run 时 `run_id` 置空，以保留对话历史。

## 5. `tool_calls`

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `id` | VARCHAR(100) | PK | 模型 tool call ID 或服务端 ID |
| `run_id` | VARCHAR(36) | FK runs, NOT NULL | 所属 run |
| `thread_id` | VARCHAR(36) | FK threads, NOT NULL | 冗余所属线程，便于隔离查询 |
| `tool_name` | VARCHAR(100) | NOT NULL | 工具注册名 |
| `arguments_json` | JSON | NOT NULL | 已校验/安全化参数 |
| `result_json` | JSON | NULL | 结构化结果或安全摘要 |
| `status` | VARCHAR(20) | NOT NULL | pending/running/success/failed/timeout/rejected |
| `error_message` | TEXT | NULL | 安全错误摘要 |
| `duration_ms` | INTEGER | NULL | 非负耗时 |
| `started_at` | DATETIME | NOT NULL | 开始时间 |
| `finished_at` | DATETIME | NULL | 结束时间 |

索引：`(run_id, started_at)`、`(thread_id, started_at)`、`tool_name`。

删除：run 或 thread 删除时级联。

## 6. `files`

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `id` | VARCHAR(36) | PK | file UUID |
| `thread_id` | VARCHAR(36) | FK threads, NOT NULL | 所属线程 |
| `source_file_id` | VARCHAR(36) | self FK, NULL | 解析文件对应的原始文件 |
| `category` | VARCHAR(20) | NOT NULL | upload/parsed/artifact |
| `original_name` | VARCHAR(255) | NOT NULL | 用户可见文件名 |
| `stored_name` | VARCHAR(255) | NOT NULL | 安全实际文件名 |
| `stored_path` | TEXT | NOT NULL | 相对数据根目录的路径 |
| `extension` | VARCHAR(30) | NULL | 小写扩展名，含点 |
| `mime_type` | VARCHAR(100) | NULL | 已验证 MIME |
| `size_bytes` | INTEGER | NOT NULL | 非负文件大小 |
| `parse_status` | VARCHAR(30) | NULL | pending/processing/success/failed/unsupported/unsupported_ocr |
| `parse_error` | TEXT | NULL | 安全解析错误 |
| `description` | TEXT | NULL | Artifact 描述 |
| `created_at` | DATETIME | NOT NULL | 创建时间 |

约束与索引：

- `UNIQUE(thread_id, stored_path)` 防止线程内路径元数据冲突。
- `(thread_id, category, created_at)` 支持文件/Artifact 列表。
- `source_file_id` 索引支持原始/解析文件关联。
- `size_bytes >= 0` 检查约束。

删除：线程删除时级联；原始文件删除时关联解析记录级联删除。Service 负责同步删除
对应受控本地文件。

## 7. `sources`

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `id` | VARCHAR(36) | PK | source UUID |
| `run_id` | VARCHAR(36) | FK runs, NOT NULL | 实际使用来源的 run |
| `thread_id` | VARCHAR(36) | FK threads, NOT NULL | 所属线程 |
| `title` | TEXT | NULL | 页面标题 |
| `url` | TEXT | NOT NULL | 最终校验后的 HTTP(S) URL |
| `snippet` | TEXT | NULL | 安全摘要 |
| `source_type` | VARCHAR(30) | NOT NULL | search/web_page |
| `created_at` | DATETIME | NOT NULL | 创建时间 |

索引与约束：

- `UNIQUE(run_id, url)` 防止同一 run 重复保存来源。
- `(thread_id, created_at)` 支持历史恢复。

删除：run 或 thread 删除时级联。

## 8. 关联关系

```text
threads 1 ── * runs
threads 1 ── * messages
threads 1 ── * tool_calls
threads 1 ── * files
threads 1 ── * sources
runs    1 ── * messages   (run_id 可空)
runs    1 ── * tool_calls
runs    1 ── * sources
files   1 ── * files      (source_file_id，自关联)
```

冗余的 `thread_id` 必须与父 run 所属线程一致，该跨表一致性由 Service 写入逻辑
验证；它换取了简单、安全的线程隔离查询。

## 9. 迁移规范

- 初始迁移一次创建六表、外键、检查约束和索引。
- 每次模型变更必须生成新的 Alembic revision，禁止修改已应用迁移。
- 升级前后运行 `alembic upgrade head` 和迁移测试。
- 破坏性迁移必须在文档说明备份、数据转换和降级策略。
- SQLite 批量表变更使用 Alembic batch mode。

