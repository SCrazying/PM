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
    # 去掉事务控制（engine 自动提交），按语句拆分执行；整行注释跳过，忽略注释内的分号
    stmts, current = [], []
    for raw_line in sql.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("--"):
            continue
        if line.strip().upper() in ("BEGIN", "COMMIT"):
            continue
        current.append(raw_line)
        # 语句结束判定：去掉行内注释后以 ; 结尾
        code = line.split("--")[0].rstrip()
        if code.endswith(";"):
            stmts.append("\n".join(current))
            current = []
    if current:
        stmts.append("\n".join(current))
    try:
        with engine.begin() as conn:
            for s in stmts:
                if not s.strip():
                    continue
                conn.execute(text(s))
        logger.info("种子数据执行完成（SQLAlchemy）")
        return 0
    except Exception as e:  # noqa: BLE001
        logger.error("seed.sql 执行失败：%s", e)
        return 1


if __name__ == "__main__":
    sys.exit(run())
