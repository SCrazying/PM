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
- 必须检查数据库兼容性，禁止上线后数据库不兼容，数据丢失。