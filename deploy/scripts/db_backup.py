#!/usr/bin/env python3
"""PM-System 数据库一键备份脚本（内网 Windows，无需 pg_dump 也能跑）。

用法：
    python db_backup.py [--output-dir DIR] [--keep N] [--env PATH]

特性：
  * 优先用 pg_dump（若装 PostgreSQL 客户端），输出 .sql（含 schema+数据+序列）
  * 无 pg_dump 时用 SQLAlchemy 兜底全库导出（schema+数据+setval，恢复见文件头注释）
  * 支持按 --keep N 保留最近 N 份，自动清理旧备份
  * 退出码：0 成功，非 0 失败（可用于计划任务告警）
"""
from __future__ import annotations

import argparse
import glob
import os
import subprocess
import sys
from datetime import datetime

ROOT = os.path.dirname(os.path.abspath(__file__))


def load_env(env_path: str) -> None:
    """把 backend/.env 的键值读进环境变量（不覆盖已有环境变量）。"""
    if not os.path.isfile(env_path):
        return
    with open(env_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())


def find_pg_dump() -> str | None:
    """先 PATH，再常见 Windows PostgreSQL 安装目录。"""
    from shutil import which
    found = which("pg_dump")
    if found:
        return found
    if sys.platform == "win32":
        for pat in (r"C:\Program Files\PostgreSQL\*\bin\pg_dump.exe",
                    r"C:\Program Files (x86)\PostgreSQL\*\bin\pg_dump.exe"):
            hits = sorted(glob.glob(pat))
            if hits:
                return hits[-1]
    return None


def sqlalchemy_dump(outfile: str, database_url: str) -> None:
    """无 pg_dump 兜底：用 SQLAlchemy 反射导出全库**数据 + 序列**为 SQL（不含建表语句）。

    恢复路径（幂等）：
      1) 在空库上 `alembic upgrade head` 重建全部表/索引/约束（schema 完整）
      2) `psql -f 本文件` 插入数据 + setval 重置序列
    不导 CREATE TABLE（alembic 负责建表）；混合导出在已存在表上会失败。
    """
    import json as _json
    import sqlalchemy as sa
    from sqlalchemy.orm import Session

    engine = sa.create_engine(database_url)
    meta = sa.MetaData()
    meta.reflect(bind=engine)

    def lit(value, column):
        if value is None:
            return "NULL"
        if isinstance(value, (dict, list)):
            return "'" + _json.dumps(value, ensure_ascii=False, default=str).replace("'", "''") + "'"
        proc = column.type.literal_processor(engine.dialect)
        if proc is not None:
            try:
                return proc(value)
            except Exception:
                pass
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, (int, float)):
            return str(value)
        return "'" + str(value).replace("'", "''") + "'"

    lines = ["-- PM-System SQLAlchemy 兜底备份（无 pg_dump，仅数据 + 序列）",
             "-- 恢复：先 alembic upgrade head 建表，再 psql -f 本文件插入数据",
             "SET session_replication_role = replica;", ""]
    with Session(engine) as db:
        for table in meta.sorted_tables:
            rows = db.execute(table.select()).mappings().all()
            if not rows:
                continue
            collist = ", ".join(f'"{c}"' for c in table.columns.keys())
            lines.append(f"-- {table.name}（{len(rows)} 行）")
            for row in rows:
                vals = [lit(row[c], table.columns[c]) for c in table.columns.keys()]
                lines.append(f'INSERT INTO "{table.name}" ({collist}) VALUES ({", ".join(vals)});')
            pk = table.primary_key.columns.keys()
            if len(pk) == 1:
                lines.append(f"SELECT setval(pg_get_serial_sequence('{table.name}', '{pk[0]}'), "
                             f"COALESCE((SELECT MAX({pk[0]}) FROM {table.name}), 1));")
            lines.append("")
    lines.append("SET session_replication_role = DEFAULT;")
    with open(outfile, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def main() -> int:
    parser = argparse.ArgumentParser(description="PM-System 数据库一键备份")
    parser.add_argument("--output-dir", default=None, help="备份目录（默认 backend/.env 的 BACKUP_DIR，或 ./data/backups）")
    parser.add_argument("--keep", type=int, default=14, help="保留最近 N 份（默认 14）")
    parser.add_argument("--env", default=os.path.join(ROOT, "..", "backend", ".env"), help="backend/.env 路径")
    args = parser.parse_args()

    env_path = os.path.abspath(args.env)
    load_env(env_path)
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print(f"[ERROR] 未找到 DATABASE_URL（检查 {env_path}）", file=sys.stderr)
        return 2

    output_dir = args.output_dir or os.environ.get("BACKUP_DIR") or os.path.join(os.path.dirname(os.path.dirname(ROOT)), "data", "backups")
    output_dir = os.path.abspath(output_dir)
    os.makedirs(output_dir, exist_ok=True)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    pg_dump = find_pg_dump()
    plain_url = db_url.replace("postgresql+psycopg2://", "postgresql://")

    try:
        if pg_dump:
            outfile = os.path.join(output_dir, f"db_{ts}.sql")
            print(f"[INFO] 使用 pg_dump：{pg_dump}")
            subprocess.run([pg_dump, plain_url, "-f", outfile], check=True, capture_output=True, timeout=600)
        else:
            outfile = os.path.join(output_dir, f"db_{ts}_fallback.sql")
            print("[INFO] 未找到 pg_dump，使用 SQLAlchemy 兜底导出")
            sqlalchemy_dump(outfile, db_url)
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] pg_dump 备份失败：{e.stderr.decode(errors='ignore')[:300]}", file=sys.stderr)
        return 1
    except Exception as e:  # noqa: BLE001
        print(f"[ERROR] 备份失败：{e}", file=sys.stderr)
        return 1

    size = os.path.getsize(outfile)
    print(f"[OK] 备份完成：{outfile}（{size} 字节）")

    # 清理旧备份（保留最近 keep 份；仅清理脚本生成的 db_*.sql 前缀文件，勿放同名手工归档到该目录）
    files = sorted(
        [os.path.join(output_dir, f) for f in os.listdir(output_dir) if f.startswith("db_") and f.endswith(".sql")],
        key=os.path.getmtime,
    )
    excess = len(files) - args.keep
    if excess > 0:
        for old in files[:excess]:
            try:
                os.remove(old)
                print(f"[INFO] 清理旧备份：{os.path.basename(old)}")
            except OSError as e:
                print(f"[WARN] 清理失败 {old}：{e}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
