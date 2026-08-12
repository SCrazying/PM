# 项目概要
技术栈：前端 Vue 3 + Vite + Element Plus + Pinia；后端 Python 3.11 + FastAPI + SQLAlchemy 2 + Alembic；数据库 PostgreSQL 14+
验证：仓库无自动化测试用例，改动后需手动冒烟（后端 /health、前端关键页面走查）

# 全局约定
- 禁止用 em dash，中文用全角破折号
- 金额相关计算一律用"分"，禁止浮点数
- 组件文件用 named export，不用 default export
- 使用中文对话
- 先输出方案
- 开发完成代码后，如果UT无问题，直接提交git
- 完成代码后，需要核实是否真的开发完成，如果没有就继续开发。
- 如果有远端分支，直接推送代码。
- 完成后自动打包

# 数据库兼容约束（红线，不可违反）
- 任何表结构变更（增删列、改类型、加索引/约束/默认值）必须新增 alembic 增量迁移（挂当前 head 0014，下一个 0015），禁止只改 db/schema.sql 不迁移；schema.sql 仅是建库脚本镜像，实际以 alembic 迁移链为准
- 禁止对生产库直接执行手工 ALTER/DDL；迁移上线前必须在本地真实 PostgreSQL（pmtestdb）跑通 upgrade 并验证数据无损
- 迁移必须幂等、可回滚（downgrade 齐全），含 has_table/has_column 保护，避免部分执行后重跑报错
- 软删兼容的唯一约束一律用部分唯一索引（WHERE NOT is_deleted）；涉及 NULL 语义用表达式索引（如 COALESCE(project_node_id, 0)）
- 主键统一 BIGSERIAL；外键默认 ON DELETE RESTRICT，关联数据清理由应用层按依赖顺序处理
- 数据丢失红线：加 NOT NULL 列必须带默认值或先回填；类型变更不得截断丢值；删列/删表必须先确认生产无依赖（如 0009_drop_archived 先确认再删）
- 大数据量 DML（清理/回填）必须分批执行（参考审计清理每批 5000 条），避免长锁表
- 纯逻辑/配置改动（不改表）不要求迁移，但需评估是否影响存量数据读取