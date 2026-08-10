# 项目管理系统（PM-System）

> 内网 · 组内轻量项目管理工具 —— 替代 Excel，内置华为 TR 评审流程，支持项目级多人进展自动汇总周报、项目看板、AI 绩效总结。

## 技术栈
- **前端**：Vue 3 + Vite + Element Plus + Pinia
- **后端**：Python 3.11 + FastAPI + SQLAlchemy 2 + Alembic
- **数据库**：PostgreSQL 14+
- **部署**：Docker / docker-compose（首选）或 离线原生部署（无 Docker）

## 目录结构
```
PM/
├── backend/            # FastAPI 后端
│   ├── app/
│   │   ├── api/v1/     # 路由（M1+ 逐步挂载）
│   │   ├── core/       # 配置/日志/响应/异常/安全/依赖/数据库
│   │   ├── models/     # ORM 模型（M1）
│   │   ├── schemas/    # Pydantic Schema（M1）
│   │   ├── repositories/ # 数据访问 + 软删过滤（M1）
│   │   ├── services/   # 应用服务（M1）
│   │   ├── engines/    # 汇总/看板/流转/AI 引擎（M2/M3）
│   │   ├── main.py     # 应用入口
│   │   └── seed.py     # 种子数据执行
│   ├── alembic/        # 数据库迁移
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/           # Vue3 前端
│   └── src/{api,router,store,views,layout,components}
├── db/
│   ├── schema.sql      # 建库脚本（21 表）
│   └── seed.sql        # 种子数据（内置 TR1~TR6 + 管理员 + 默认配置）
├── deploy/
│   ├── nginx/          # Nginx 配置
│   ├── scripts/        # install/backup/restore/prepare_offline/systemd
│   └── offline/        # 离线物料
├── docker-compose.yml  # 一键部署
└── doc/                # 策划/架构/任务/导入映射 文档
```

## 快速开始（开发）

### 一键启动（推荐）
```powershell
# Windows PowerShell（推荐，UTF-8 BOM 脚本）
powershell -ExecutionPolicy Bypass -File .\start-dev.ps1
# 或右键 start-dev.ps1 →“使用 PowerShell 运行”
```
也支持：`start-dev.bat`（cmd 双击）／ `bash start-dev.sh`（Git Bash / Linux）。

脚本自动完成：创建/检查后端 venv 与依赖 → 生成 .env → 执行数据库迁移 → 启动后端(8001) → 安装/启动前端(5173)。
访问：前端 http://localhost:5173 ｜ 后端 http://127.0.0.1:8001/docs ｜ 默认账号 **admin / admin123**

### 手动启动
#### 后端
```bash
cd backend
python3.11 -m venv venv && source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements-dev.txt
cp .env.example .env            # 修改 DATABASE_URL / JWT_SECRET
# 启动 PostgreSQL 并建库后：
alembic upgrade head
python -m app.seed              # 首次：写入内置 TR 模板/管理员/配置
uvicorn app.main:app --reload --port 8001   # http://127.0.0.1:8001/docs
```

#### 前端
```bash
cd frontend
npm install
npm run dev                     # http://localhost:5173（已配置 /api 代理到 8001）
```

## 部署（生产，两种方式）
详见 [doc/部署手册.md](doc/部署手册.md)。
- **Docker**：`docker compose up -d`
- **离线/原生**（内网无 Docker，Windows 数据库初始化）：`powershell -ExecutionPolicy Bypass -File deploy/scripts/init_db.ps1`（幂等建用户/库 → 迁移建表 → 写入种子数据）

## 当前进度
- [x] M0 工程基座（骨架 + 部署脚本）
- [x] M1 核心闭环（认证/项目/自选TR节点/任务/总览）
- [x] M2 进展与看板（多人进展/周报/看板/评审流转/通知）
- [x] M3 绩效与完善（AI 绩效/Excel 导入/模板配置/备份）
- [x] M4 节点完成更新（完成度 + 负责人直接完成节点）
- [x] M5 台账导入导出（固定角色 SE/TPM/TL-FO/CodeReview + 角色单元格换行导出/解析导入）
- [x] M6 节点子节点（TR 节点下动态拆分子节点，可完成状态更新，周会视图当前节点下显示并点击完成）
- [x] M7 项目状态手动配置（未开始/进行中/延期/已完成/暂停，列表内联编辑）+ 健康度下线 + **归档并入已完成（去重）**
- [x] **V1.0.2**：完成度仅统计一级节点（修复子节点拉低）/ **MinIO 对象存储项目资料**（详情页资料上传下载，存储后端可切换）/ **Python 备份·恢复·定时任务脚本** / 周会视图**设置面板**（仅显示今日进展 + **今日目标列**（昨日报的明日计划））/ 本周台账**按列启用状态导出**
- [x] **v0.3（内网版）**：工作台**月度日历视图**（最近进展按月选天，今日已填报可直接改）/ 项目详情**风险管理**（单独添加/删除/关闭）/ 周目标**任意周查看编辑**（周次下拉含前几周、动态并入有数据的周）/ **日历方式选周**（dayjs 周一起始）/ 全站弹窗加大 / 看板风险可点击跳项目 + 机型筛选 / 项目资料下载授权修复 / attachment.mime_type 修复（迁移 0013）/ 完成度与子节点保留修复

> 全部里程碑已完成，端到端在真实 PostgreSQL 上验证通过。

## 功能总览
| 模块 | 功能 |
|---|---|
| 项目看板 | **可视化看板**：统计卡片 + 状态分布条 + 待关注项目（节点超期）+ 未关闭风险 + **昨日进展/今日计划缺报面板** + 状态列看板（拖拽换状态）+ 机型筛选，**进入自动加载** |
| 项目管理 | 新建/编辑/删除（二次确认，进回收站）+ **项目状态手动配置（列表内联编辑，已完成即终态）** + **多行描述** + **机型下拉选择** + **立项自选 TR 节点** + 成员角色（**SE/TPM 单选、TL/FO/CodeReview 多选**） |
| 项目详情 | TR 节点进度条 + 节点任务看板 + **节点子节点（添加/完成/截止）** + **评审流转 + 整改闭环** + 完成度（一级节点）+ 周目标（可绑定负责人）+ 进展时间线 + **项目资料（MinIO 上传/下载/分类）** |
| 工作台 | 今日待填报 + 项目级进展填报（多人/关联任务/风险） |
| 周会视图 | **按项目 / 按人 双视图** + **设置面板**（列显示/隐藏 + **仅显示今日进展**）+ **今日目标列（昨日报的明日计划）** + 周目标条目**可绑定负责人** + **本周台账导出按列启用状态（与视图一致）** + **筛选持久化与重置** |
| 数据备份 | 系统管理页手动备份 + **一键备份脚本**（`deploy/scripts/db_backup.py`，pg_dump 优先/无则 SQLAlchemy 兜底，自动清理旧份）+ **Windows 定时任务注册/卸载脚本** + **恢复脚本** |
| 个人绩效 | 月/季/年工作汇总 + **AI 自动生成绩效总结**（可编辑/导出/看依据，无 AI 时模板降级） |
| 系统管理 | 用户 / **机型管理** / TR 模板 / **Excel 台账导入与导出** / 系统配置 / **数据备份（pg_dump，缺失时 SQLAlchemy 兜底导出）** |

## 文档
| 文档 | 说明 |
|---|---|
| [doc/项目管理系统-策划书.md](doc/项目管理系统-策划书.md) | 需求基线 V2.3 |
| [doc/项目管理系统-架构设计文档.md](doc/项目管理系统-架构设计文档.md) | 架构设计 V1.2 |
| [doc/开发任务拆解.md](doc/开发任务拆解.md) | 任务与排期 |
| [doc/Excel导入映射.md](doc/Excel导入映射.md) | 历史 Excel 迁移规则 |
| [doc/部署手册.md](doc/部署手册.md) | Docker 与离线部署 |
