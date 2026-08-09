#!/usr/bin/env python3
"""PM-System 数据库一键恢复脚本（内网 Windows）。

用法：
    python db_restore.py --file backups/db_20260810_120000.sql [--env PATH]

说明：
  * 默认恢复来源是 .sql（pg_dump 或兜底导出），用 psql 执行；
  * 如目标库已有数据，会先提示确认（除非 --yes）；
  * 没有 psql 时无法恢复 pg_dump 格式（请安装 PostgreSQL 客户端或先在空库上执行）。
  * 退出码：0 成功，非 0 失败。
"""
from __future__ import annotations

import argparse
import glob
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))


def load_env(env_path: str) -> None:
    if not os.path.isfile(env_path):
        return
    with open(env_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())


def find_psql() -> str | None:
    from shutil import which
    found = which("psql")
    if found:
        return found
    if sys.platform == "win32":
        for pat in (r"C:\Program Files\PostgreSQL\*\bin\psql.exe",
                    r"C:\Program Files (x86)\PostgreSQL\*\bin\psql.exe"):
            hits = sorted(glob.glob(pat))
            if hits:
                return hits[-1]
    return None


def parse_db_url(url: str) -> dict:
    """postgresql[+driver]://user:pass@host:port/db 拆成 psql 参数。"""
    u = url.replace("postgresql+psycopg2://", "postgresql://")
    from urllib.parse import urlparse
    p = urlparse(u)
    return {
        "host": p.hostname or "127.0.0.1",
        "port": str(p.port or 5432),
        "user": p.username or "pm",
        "password": p.password or "",
        "db": (p.path or "").lstrip("/"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="PM-System 数据库一键恢复")
    parser.add_argument("--file", required=True, help="备份文件路径（.sql）")
    parser.add_argument("--env", default=os.path.join(ROOT, "..", "backend", ".env"), help="backend/.env 路径")
    parser.add_argument("--yes", action="store_true", help="跳过确认（脚本/计划任务用）")
    args = parser.parse_args()

    env_path = os.path.abspath(args.env)
    load_env(env_path)
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print(f"[ERROR] 未找到 DATABASE_URL（检查 {env_path}）", file=sys.stderr)
        return 2

    if not os.path.isfile(args.file):
        print(f"[ERROR] 备份文件不存在：{args.file}", file=sys.stderr)
        return 2

    psql = find_psql()
    if not psql:
        print("[ERROR] 未找到 psql，无法恢复 .sql 备份。请安装 PostgreSQL 客户端后重试。", file=sys.stderr)
        return 2

    cfg = parse_db_url(db_url)
    print(f"[WARN] 将恢复数据库 {cfg['db']}@{cfg['host']}:{cfg['port']}（来源 {os.path.basename(args.file)}）")
    if not args.yes:
        ans = input("确认恢复？现有数据可能被覆盖/合并。输入 yes 继续：").strip()
        if ans != "yes":
            print("[INFO] 已取消")
            return 3

    env = dict(os.environ)
    if cfg["password"]:
        env["PGPASSWORD"] = cfg["password"]
    try:
        subprocess.run(
            [psql, "-h", cfg["host"], "-p", cfg["port"], "-U", cfg["user"], "-d", cfg["db"], "-v", "ON_ERROR_STOP=1", "-f", args.file],
            check=True, env=env,
        )
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] 恢复失败（psql 退出码 {e.returncode}）", file=sys.stderr)
        return 1

    print(f"[OK] 恢复完成：{os.path.basename(args.file)} → {cfg['db']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
