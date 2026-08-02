"""种子数据：执行 db/seed.sql 中的初始数据（内置 TR 模板 + 管理员 + 默认配置）。
在 Docker 启动或离线 install 时调用；幂等（seed.sql 内用 ON CONFLICT）。"""
import os
import subprocess
import sys

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("pm.seed")

SEED_FILE = os.path.join(os.path.dirname(__file__), "..", "..", "db", "seed.sql")


def run() -> int:
    if not os.path.exists(SEED_FILE):
        logger.warning("seed.sql 未找到：%s（跳过）", SEED_FILE)
        return 0
    # 用 psql 执行 seed.sql（DATABASE_URL 转为 psql 连接串）
    url = settings.DATABASE_URL.replace("postgresql+psycopg2://", "postgresql://")
    try:
        subprocess.run(["psql", url, "-f", SEED_FILE, "-v", "ON_ERROR_STOP=0"], check=True)
        logger.info("种子数据执行完成")
        return 0
    except FileNotFoundError:
        logger.warning("未检测到 psql，改用 SQLAlchemy 执行 seed.sql")
        return _run_via_sqlalchemy()
    except subprocess.CalledProcessError as e:
        logger.error("seed.sql 执行失败：%s", e)
        return 1


def _run_via_sqlalchemy() -> int:
    from sqlalchemy import text

    from app.core.database import engine

    with open(SEED_FILE, encoding="utf-8") as f:
        sql = f.read()
    # 去掉事务控制（engine 自动提交），按语句拆分执行
    stmts = [s.strip() for s in sql.replace("BEGIN;", "").replace("COMMIT;", "").split(";") if s.strip()]
    try:
        with engine.begin() as conn:
            for s in stmts:
                conn.execute(text(s))
        logger.info("种子数据执行完成（SQLAlchemy）")
        return 0
    except Exception as e:  # noqa: BLE001
        logger.error("seed.sql 执行失败：%s", e)
        return 1


if __name__ == "__main__":
    sys.exit(run())
