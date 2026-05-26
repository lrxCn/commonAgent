# 81 - 演示平台 Phase 0a：Back 数据库、迁移与种子

## 建议执行模型

- 模型：GPT-5 或同档强编码模型
- Reasoning：medium
- 原因：需设计 SQLAlchemy 模型、Alembic 迁移与种子数据，并与 PRD 表结构对齐；不涉及 Agent graph 改造。

## 新窗口执行规则

1. 先读根目录 `AGENTS.md`、`README.md`、`docs/progress.md` 和本任务卡。
2. 阅读 PRD：[demo-admin-console.md](../prd/demo-admin-console.md) 模块二、数据模型、环境与本地运行。
3. 核对任务 01–80 已完成；本任务为演示平台首批，无 81+ 前置依赖。
4. 对比当前模型和 reasoning 与本节建议；不一致或未知时先告知用户并等待确认，除非用户明确要求继续。
5. 只实现本任务范围，不顺手做 Session 认证或 Front。
6. 按验证方案测试；通过后更新 `docs/progress.md`。
7. 不要自动 push，除非用户明确要求。

## 依赖

无（演示平台起点）

## 背景

演示平台需要在 Back 使用独立库 `common_agent_back`（与 Agent Postgres **同实例、不同库**）。本任务建立 ORM、迁移与种子，为后续认证、CRUD、KB meta、chat_threads 提供基础。

## 目标

- Back 接入 `DATABASE_URL` → `common_agent_back`。
- Alembic 初始迁移：`roles`、`users`、`user_roles`（**无 `is_primary`**）、`students`、`kb_document_meta`、`chat_threads`。
- 种子：`role-admin`、`role-sales`、`role-support`；用户 `admin`（密码由 `ADMIN_SEED_PASSWORD` 默认 `123456`）；可选 `alice`/`bob`；示例学生 2–3 条。
- `admin` 绑定 `role-admin`，`is_admin=true`，种子逻辑保证不可删（删除约束可在 86 强化）。

## 范围

| 模块 | 变更 |
|------|------|
| `back/` | SQLAlchemy 2.x models、session 工厂、Alembic |
| `back/.env.example` / `back/.env` | `DATABASE_URL`、`ADMIN_SEED_PASSWORD` 等（与实现同步） |
| `back/README` 或根 README 小节 | 仅注明库名与迁移命令（完整演示说明留 **92**） |

## 实施步骤

1. 在 `back/` 增加 `pyproject`/`requirements` 依赖：`sqlalchemy`、`alembic`、`psycopg`（或 async 方案与项目一致）、`bcrypt`（为 82 预留）。
2. 按 PRD 定义表字段与联合主键（`kb_document_meta`: `doc_id` + `role_id`）。
3. 编写 `alembic upgrade head` 与 seed 脚本（CLI 或 startup hook，需可重复运行于空库）。
4. 为 `role_id` 预留格式校验常量/工具（`role-[a-z0-9-]+`），供 86 复用。

## 验证方案

```bash
cd back && uv run pytest tests/test_demo_database.py -v
# 期望：迁移可跑、种子角色/用户/学生存在；admin 有 role-admin
```

若本地无 Postgres，测试可用 SQLite 内存或 pytest fixture 模拟，并在任务备注中说明跳过项。

## 非范围

- Cookie Session、`/api/auth/*`（**82**）
- Vue Front（**83–84**）
- Agent `role_ids[]`（**87**）
- KB ingest 双写（**89**）

## 完成标准

- [ ] `alembic upgrade head` 在空库成功。
- [ ] 种子三类角色与 admin 用户可查询。
- [ ] pytest 覆盖表存在与种子关键行。
- [ ] `docs/progress.md` **81** → `✅`。

## 进度更新

`docs/progress.md` **81** → 实现完成后改为 `✅`；建议下一步 **82**。
