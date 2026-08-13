"""M3 路由：个人汇总/AI 总结、附件、配置、TR 模板管理、备份、导出。"""
import csv
import glob
import io
import json
import os
import shutil
import subprocess
import sys
from datetime import date, datetime, time, timedelta

from fastapi import APIRouter, Depends, Query, UploadFile, File, Form
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.deps import get_current_user, require_admin, require_self_or_admin
from app.core.responses import BizException, ForbiddenError, NotFoundError, ok, page_result
from app.core.storage import get_storage
from app.engines.ai_engine import AiService
from app.models.misc import Attachment, AuditLog, Config
from app.models.project import Project, ProjectMember, TrTemplate, TrTemplateNode
from app.models.user import User
from app.schemas.project import RecycleBatchIn
from app.services.audit_service import cleanup_expired, record_audit
from app.services.personal_service import PersonalService
from app.services.project_service import ProjectService

router = APIRouter()


# ---------- 个人汇总 / AI 总结 ----------
@router.get("/personal/{user_id}/summary")
def personal_summary(user_id: int, period: str = Query("month"), date_: date = Query(None, alias="date"),
                     user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    require_self_or_admin(user_id, user)
    ref = date_ or date.today()
    return ok(PersonalService(db).summary(user_id, period, ref))


@router.get("/personal/{user_id}/ai-summary")
def get_ai_summary(user_id: int, period: str = Query("month"), date_: date = Query(None, alias="date"),
                   user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    require_self_or_admin(user_id, user)
    ref = date_ or date.today()
    row = AiService(db).get(user_id, period, ref)
    if not row:
        return ok(None)
    return ok({"id": row.id, "content": row.edited_content or row.content, "raw_content": row.content,
               "status": row.status, "model": row.model, "error": row.error,
               "source_snapshot": row.source_snapshot,
               "period_start": row.period_start, "period_end": row.period_end})


@router.post("/personal/{user_id}/ai-summary")
def gen_ai_summary(user_id: int, body: dict, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    require_self_or_admin(user_id, user)
    period = body.get("period", "month")
    ref = date.fromisoformat(body["date"]) if body.get("date") else date.today()
    row = AiService(db).generate(user_id, period, ref, user["user_id"])
    record_audit(db, user["user_id"], "create", "ai_summary", str(row.id),
                 {"user_id": user_id, "period": period, "status": row.status})
    return ok({"id": row.id, "status": row.status, "model": row.model}, message="已生成")


@router.put("/ai-summaries/{sid}")
def edit_ai_summary(sid: int, body: dict, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    row = AiService(db).edit(sid, body.get("edited_content", ""), user)
    record_audit(db, user["user_id"], "update", "ai_summary", str(sid))
    return ok({"id": row.id, "status": row.status}, message="已保存")


# ---------- 附件 ----------
ALLOWED_EXT = set((os.environ.get("ATTACH_EXT") or
                   "pdf,doc,docx,xls,xlsx,ppt,pptx,txt,md,png,jpg,jpeg,zip").split(","))


def _save_upload(file: UploadFile, content: bytes) -> str:
    """存储到当前后端（本地磁盘 / MinIO），返回 file_path。

    存储键只用随机 UUID + 消毒后的扩展名，不掺原始文件名——原始文件名可能含
    路径分隔符（`../`、反斜杠）等穿越字符，直接拼进键名会经 LocalStorage 的
    join 写出 UPLOAD_DIR 之外（CWE-22）。原始文件名仅存 DB 展示用，不进文件路径。
    """
    import re
    import uuid
    # 扩展名只保留字母数字（上传前已过 ALLOWED_EXT 白名单，这里再做纵深消毒）
    ext = (file.filename.rsplit(".", 1)[-1] if file.filename else "") or ""
    ext = re.sub(r"[^A-Za-z0-9]", "", ext)
    key = f"{uuid.uuid4().hex}.{ext}" if ext else uuid.uuid4().hex
    return get_storage().put(key, content)


def _check_project_access(db: Session, project_id: int, user: dict) -> None:
    """校验调用者是项目成员/负责人/admin（附件读/下载等，与上传侧对称）。

    附件上传已校验成员，读/下载若不校验则任意登录用户可枚举并下载任意项目的
    资料文件（IDOR）。"""
    project = db.get(Project, project_id)
    if not project or project.is_deleted:
        raise NotFoundError("项目不存在")
    if user["role"] == "admin" or project.owner_id == user["user_id"]:
        return
    member = db.execute(
        select(ProjectMember).where(
            ProjectMember.project_id == project_id, ProjectMember.user_id == user["user_id"],
            ProjectMember.is_deleted.is_(False))
    ).scalar_one_or_none()
    if not member:
        raise ForbiddenError("仅项目成员/负责人可查看资料")


@router.post("/attachments")
async def upload_attachment(project_id: int = Form(...), project_node_id: int = Form(None),
                            task_id: int = Form(None), review_id: int = Form(None),
                            category: str = Form(None),
                            file: UploadFile = File(...),
                            user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    if not (project_node_id or task_id or review_id or category):
        raise BizException("附件须关联节点/任务/评审之一，或指定资料分类")
    # 校验项目存在 + 上传权限（admin/负责人/成员）
    project = db.get(Project, project_id)
    if not project or project.is_deleted:
        raise NotFoundError("项目不存在")
    if not (user["role"] == "admin" or project.owner_id == user["user_id"] or db.execute(
        select(ProjectMember).where(
            ProjectMember.project_id == project_id, ProjectMember.user_id == user["user_id"],
            ProjectMember.is_deleted.is_(False))
    ).scalar_one_or_none()):
        raise ForbiddenError("仅项目成员/负责人可上传资料")
    ext = (file.filename.rsplit(".", 1)[-1] or "").lower()
    if ext not in ALLOWED_EXT:
        raise BizException(f"不支持的文件类型 .{ext}")
    # 读前按 Content-Length 预检，拒绝超大文件整读进内存
    limit = settings.ATTACHMENT_MAX_MB * 1024 * 1024
    if file.size and file.size > limit:
        raise BizException(f"文件超过 {settings.ATTACHMENT_MAX_MB}MB")
    content = await file.read()
    if len(content) > limit:
        raise BizException(f"文件超过 {settings.ATTACHMENT_MAX_MB}MB")

    fpath = _save_upload(file, content)
    att = Attachment(project_id=project_id, project_node_id=project_node_id, task_id=task_id,
                     review_id=review_id, category=category, file_name=file.filename, file_path=fpath,
                     file_size=len(content), mime_type=file.content_type, uploaded_by=user["user_id"])
    db.add(att)
    db.commit()
    db.refresh(att)
    record_audit(db, user["user_id"], "create", "attachment", str(att.id),
                 {"project_id": project_id, "file": att.file_name, "category": category, "size": att.file_size})
    return ok({"id": att.id, "file_name": att.file_name}, message="上传成功")


@router.get("/projects/{project_id}/attachments")
def list_attachments(project_id: int, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """项目资料/附件列表（含上传人姓名）。仅项目成员/负责人/admin 可看。"""
    _check_project_access(db, project_id, user)
    rows = db.execute(
        select(Attachment, User.display_name)
        .join(User, User.id == Attachment.uploaded_by, isouter=True)
        .where(Attachment.project_id == project_id, Attachment.is_deleted.is_(False))
        .order_by(Attachment.uploaded_at.desc())
    ).all()
    return ok([{
        "id": a.id, "file_name": a.file_name, "file_size": a.file_size, "mime_type": a.mime_type,
        "category": a.category, "project_node_id": a.project_node_id, "task_id": a.task_id,
        "review_id": a.review_id, "uploaded_by": a.uploaded_by, "uploaded_by_name": uname,
        "uploaded_at": a.uploaded_at.isoformat() if a.uploaded_at else None,
    } for a, uname in rows])


@router.get("/attachments/{aid}/download")
def download_attachment(aid: int, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    att = db.get(Attachment, aid)
    if not att or att.is_deleted:
        raise NotFoundError("附件不存在")
    _check_project_access(db, att.project_id, user)  # 与上传对称，防越权下载（IDOR）
    try:
        path = get_storage().get_path(att.file_path)
    except Exception:  # noqa: BLE001  MinIO 下载失败/对象缺失
        raise NotFoundError("附件文件缺失")
    if not os.path.exists(path):
        raise NotFoundError("附件文件缺失")
    record_audit(db, user["user_id"], "export", "attachment", str(aid),
                 {"project_id": att.project_id, "file": att.file_name})
    return FileResponse(path, filename=att.file_name)


@router.delete("/attachments/{aid}")
def delete_attachment(aid: int, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """删除附件（软删）：上传人 / 项目负责人 / 管理员。"""
    att = db.get(Attachment, aid)
    if not att or att.is_deleted:
        raise NotFoundError("附件不存在")
    project = db.get(Project, att.project_id)
    if not (user["role"] == "admin" or (project and project.owner_id == user["user_id"])
            or att.uploaded_by == user["user_id"]):
        raise ForbiddenError("仅上传人/负责人/管理员可删除")
    att.is_deleted = True
    from datetime import datetime, timezone
    att.deleted_at = datetime.now(timezone.utc)
    db.commit()
    get_storage().delete(att.file_path)
    record_audit(db, user["user_id"], "delete", "attachment", str(aid),
                 {"project_id": att.project_id, "file": att.file_name})
    return ok(message="已删除")


# ---------- 配置 ----------
SENSITIVE_KEYS = {"ai.api_key_ref"}


@router.get("/config")
def list_config(user: dict = Depends(require_admin), db: Session = Depends(get_db)):
    rows = db.execute(select(Config)).scalars().all()
    out = []
    for c in rows:
        val = c.value
        if c.key in SENSITIVE_KEYS or "key" in c.key.lower():
            val = "***" if c.value else ""
        out.append({"key": c.key, "value": val, "description": c.description})
    return ok(out)


@router.put("/config/{key}")
def set_config(key: str, body: dict, user: dict = Depends(require_admin), db: Session = Depends(get_db)):
    row = db.get(Config, key)
    if not row:
        row = Config(key=key)
        db.add(row)
    row.value = body.get("value")
    db.commit()
    record_audit(db, user["user_id"], "config_change", "config", key)
    return ok(message="已保存")


# ---------- 机型管理（管理端维护，供新建/编辑项目下拉）----------
@router.get("/machine-models")
def list_machine_models(user: dict = Depends(require_admin), db: Session = Depends(get_db)):
    from app.models.misc import MachineModel
    managed = db.execute(
        select(MachineModel).where(MachineModel.is_deleted.is_(False)).order_by(MachineModel.name)
    ).scalars().all()
    used = ProjectService(db).list_machine_options()
    registered = {m.name for m in managed}
    rows = [{"id": m.id, "name": m.name, "source": "registered"} for m in managed]
    rows += [{"id": None, "name": u, "source": "used"} for u in used if u not in registered]
    return ok(rows)


@router.post("/machine-models")
def create_machine_model(body: dict, user: dict = Depends(require_admin), db: Session = Depends(get_db)):
    from datetime import datetime, timezone
    from app.models.misc import MachineModel
    name = (body.get("name") or "").strip()
    if not name:
        raise BizException("机型名称不能为空", code=400, http_status=400)
    old = db.execute(select(MachineModel).where(MachineModel.name == name)).scalar_one_or_none()
    if old and not old.is_deleted:
        raise BizException("机型已存在", code=409, http_status=409)
    if old:
        old.is_deleted = False
        old.deleted_at = None
        m = old
    else:
        m = MachineModel(name=name)
        db.add(m)
    db.commit()
    db.refresh(m)
    record_audit(db, user["user_id"], "create", "machine_model", str(m.id), {"name": name})
    return ok({"id": m.id, "name": m.name}, message="已添加")


@router.delete("/machine-models/{mid}")
def delete_machine_model(mid: int, user: dict = Depends(require_admin), db: Session = Depends(get_db)):
    from datetime import datetime, timezone
    from app.models.misc import MachineModel
    m = db.get(MachineModel, mid)
    if not m or m.is_deleted:
        raise NotFoundError("机型不存在")
    m.is_deleted = True
    m.deleted_at = datetime.now(timezone.utc)
    db.commit()
    record_audit(db, user["user_id"], "delete", "machine_model", str(mid), {"name": m.name})
    return ok(message="已删除")


# ---------- TR 模板管理 ----------
@router.post("/tr-templates")
def create_template(body: dict, user: dict = Depends(require_admin), db: Session = Depends(get_db)):
    from app.models.project import TrTemplateSubnode
    tpl = TrTemplate(name=body["name"], description=body.get("description"), is_builtin=False)
    db.add(tpl)
    db.flush()
    for i, n in enumerate(body.get("nodes", []), start=1):
        node = TrTemplateNode(template_id=tpl.id, node_key=n["node_key"], name=n["name"],
                              sequence=n.get("sequence", i), review_focus=n.get("review_focus"))
        db.add(node)
        db.flush()
        for j, sn in enumerate(n.get("subnodes", []), start=1):
            sn_name = (sn.get("name") if isinstance(sn, dict) else sn) or ""
            if sn_name.strip():
                db.add(TrTemplateSubnode(template_node_id=node.id, name=str(sn_name).strip(), sequence=j))
    db.commit()
    record_audit(db, user["user_id"], "create", "tr_template", str(tpl.id), {"name": tpl.name})
    return ok({"id": tpl.id}, message="模板已创建")


@router.put("/tr-templates/{tid}")
def update_template(tid: int, body: dict, user: dict = Depends(require_admin), db: Session = Depends(get_db)):
    tpl = db.get(TrTemplate, tid)
    if not tpl:
        raise NotFoundError("模板不存在")
    if tpl.is_builtin and body.get("name") and body["name"] != tpl.name:
        raise BizException("内置模板不可改名")
    if body.get("status"):
        tpl.status = body["status"]
    if body.get("description") is not None:
        tpl.description = body["description"]
    db.commit()
    record_audit(db, user["user_id"], "update", "tr_template", str(tid), {"status": tpl.status})
    return ok(message="已更新")


# ---------- Excel 导入 ----------
@router.post("/import/excel/preview")
async def import_preview(file: UploadFile = File(...), user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    from app.services.import_service import ImportService
    # 读前/读后双重限流：任意登录用户可 POST 超大文件触发整读进内存（内存 DoS）
    limit = settings.ATTACHMENT_MAX_MB * 1024 * 1024
    if file.size and file.size > limit:
        raise BizException(f"文件超过 {settings.ATTACHMENT_MAX_MB}MB")
    content = await file.read()
    if len(content) > limit:
        raise BizException(f"文件超过 {settings.ATTACHMENT_MAX_MB}MB")
    result = ImportService(db).preview(content)
    return ok(result)


@router.post("/import/excel/confirm")
def import_confirm(body: dict, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    from app.services.import_service import ImportService
    result = ImportService(db).confirm(body.get("projects", []), user["user_id"])
    record_audit(db, user["user_id"], "import", "project", None, {"created": result["created"], "failed": len(result["failed"])})
    return ok(result, message=f"导入完成：成功 {result['created']} 个")


# ---------- 备份 ----------
def _find_pg_dump() -> str | None:
    """查找 pg_dump：先 PATH，再常见 Windows PostgreSQL 安装目录。"""
    found = shutil.which("pg_dump")
    if found:
        return found
    if sys.platform == "win32":
        for pat in (r"C:\Program Files\PostgreSQL\*\bin\pg_dump.exe",
                    r"C:\Program Files (x86)\PostgreSQL\*\bin\pg_dump.exe"):
            hits = glob.glob(pat)
            if hits:
                return hits[0]
    return None


def _sql_literal(value, column, dialect) -> str:
    """把 Python 值转成 SQL 字面量（配合兜底备份导出）。"""
    if value is None:
        return "NULL"
    if isinstance(value, (dict, list)):
        return "'" + json.dumps(value, ensure_ascii=False, default=str).replace("'", "''") + "'"
    proc = column.type.literal_processor(dialect)
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


def _sqlalchemy_dump(db: Session, outfile: str) -> None:
    """无 pg_dump 时的兜底备份：按 ORM 元数据导出全库 schema + 数据 + 序列为 SQL。
    恢复方式：psql -f 该文件（需在空库上执行，INSERT 前请先建好同名表）。"""
    import sqlalchemy as sa
    from app.models.base import Base
    dialect = db.get_bind().dialect
    lines = ["-- PM-System SQLAlchemy 兜底备份（无 pg_dump）", "SET session_replication_role = replica;", ""]
    for table in Base.metadata.sorted_tables:
        lines.append(str(sa.schema.CreateTable(table).compile(dialect=dialect)) + ";")
        rows = db.execute(table.select()).mappings().all()
        if rows:
            collist = ", ".join(table.columns.keys())
            for row in rows:
                vals = [_sql_literal(row[c], table.columns[c], dialect) for c in table.columns.keys()]
                lines.append(f"INSERT INTO {table.name} ({collist}) VALUES ({', '.join(vals)});")
        pk = table.primary_key.columns.keys()
        if pk and len(pk) == 1:
            lines.append(f"SELECT setval(pg_get_serial_sequence('{table.name}', '{pk[0]}'), "
                         f"COALESCE((SELECT MAX({pk[0]}) FROM {table.name}), 1));")
        lines.append("")
    lines.append("SET session_replication_role = DEFAULT;")
    with open(outfile, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


@router.post("/backup")
def trigger_backup(user: dict = Depends(require_admin), db: Session = Depends(get_db)):
    os.makedirs(settings.BACKUP_DIR, exist_ok=True)
    from datetime import datetime
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    url = settings.DATABASE_URL.replace("postgresql+psycopg2://", "postgresql://")
    pg_dump = _find_pg_dump()
    if pg_dump:
        outfile = os.path.join(settings.BACKUP_DIR, f"db_{ts}.sql")
        try:
            subprocess.run([pg_dump, url, "-f", outfile], check=True, capture_output=True, timeout=180)
        except subprocess.CalledProcessError as e:
            raise BizException(f"备份失败：{e.stderr.decode(errors='ignore')[:200]}")
    else:
        # 无 pg_dump：SQLAlchemy 全库兜底导出
        outfile = os.path.join(settings.BACKUP_DIR, f"db_{ts}_fallback.sql")
        try:
            _sqlalchemy_dump(db, outfile)
        except Exception as e:
            raise BizException(f"备份失败：{e}")
    record_audit(db, user["user_id"], "backup", "system", ts)
    return ok({"file": os.path.basename(outfile)}, message="备份完成")


@router.get("/backups")
def list_backups(user: dict = Depends(require_admin)):
    if not os.path.isdir(settings.BACKUP_DIR):
        return ok([])
    files = sorted([f for f in os.listdir(settings.BACKUP_DIR) if f.startswith("db_")], reverse=True)
    return ok([{"file": f, "size": os.path.getsize(os.path.join(settings.BACKUP_DIR, f))} for f in files])


# ---------- 审计日志（操作记录，V1.0.3）----------
@router.get("/admin/audit-logs")
def list_audit_logs(actor: str | None = None, action: str | None = None, target_type: str | None = None,
                    target_id: str | None = None, date_from: date | None = None, date_to: date | None = None,
                    page: int = Query(1, ge=1), size: int = Query(20, ge=1, le=100),
                    user: dict = Depends(require_admin), db: Session = Depends(get_db)):
    """操作日志查询：按操作者/动作/目标类型/目标id/时间过滤，分页（含操作者姓名）。"""
    q = select(AuditLog, User.display_name).join(User, User.id == AuditLog.actor_id, isouter=True)
    if actor:
        q = q.where(or_(User.display_name.ilike(f"%{actor}%"), User.username.ilike(f"%{actor}%")))
    if action:
        q = q.where(AuditLog.action == action)
    if target_type:
        q = q.where(AuditLog.target_type == target_type)
    if target_id:
        q = q.where(AuditLog.target_id == target_id)
    if date_from:
        q = q.where(AuditLog.created_at >= datetime.combine(date_from, time.min))
    if date_to:
        q = q.where(AuditLog.created_at < datetime.combine(date_to + timedelta(days=1), time.min))
    total = db.execute(select(func.count()).select_from(q.subquery())).scalar_one()
    rows = db.execute(q.order_by(AuditLog.id.desc()).offset((page - 1) * size).limit(size)).all()
    items = [{
        "id": log.id, "time": log.created_at.isoformat() if log.created_at else None,
        "actor_id": log.actor_id, "actor_name": uname, "action": log.action,
        "target_type": log.target_type, "target_id": log.target_id, "detail": log.detail, "ip": log.ip,
    } for log, uname in rows]
    return page_result(items, total, page, size)


@router.get("/admin/audit-meta")
def audit_meta(user: dict = Depends(require_admin), db: Session = Depends(get_db)):
    """操作日志的可用 action / target_type 去重列表（供前端筛选下拉）。"""
    actions = [r[0] for r in db.execute(select(AuditLog.action).distinct()).all()]
    target_types = [r[0] for r in db.execute(select(AuditLog.target_type).distinct()).all()]
    return ok({"actions": actions, "target_types": [t for t in target_types if t]})


@router.post("/admin/audit-logs/cleanup")
def cleanup_audit_logs(user: dict = Depends(require_admin), db: Session = Depends(get_db)):
    """手动清理过期审计日志（按保留期配置）。"""
    n = cleanup_expired(db)
    record_audit(db, user["user_id"], "delete", "audit_log", None, {"deleted": n})
    return ok({"deleted": n}, message=f"已清理 {n} 条过期日志")


@router.get("/admin/audit-logs/export")
def export_audit_logs(actor: str | None = None, action: str | None = None, target_type: str | None = None,
                      target_id: str | None = None, date_from: date | None = None, date_to: date | None = None,
                      user: dict = Depends(require_admin), db: Session = Depends(get_db)):
    """操作日志导出 CSV（按当前过滤条件全量）。"""
    q = select(AuditLog, User.display_name).join(User, User.id == AuditLog.actor_id, isouter=True)
    if actor:
        q = q.where(or_(User.display_name.ilike(f"%{actor}%"), User.username.ilike(f"%{actor}%")))
    if action:
        q = q.where(AuditLog.action == action)
    if target_type:
        q = q.where(AuditLog.target_type == target_type)
    if target_id:
        q = q.where(AuditLog.target_id == target_id)
    if date_from:
        q = q.where(AuditLog.created_at >= datetime.combine(date_from, time.min))
    if date_to:
        q = q.where(AuditLog.created_at < datetime.combine(date_to + timedelta(days=1), time.min))
    # 导出上限保护：避免日志量巨大时一次拉全量 OOM（如需全部可缩小日期范围分批导出）
    rows = db.execute(q.order_by(AuditLog.id.desc()).limit(50000)).all()

    def _csv_safe(v):
        """CSV 注入防护：以 = + - @ \\t \\r 开头的单元格加 ' 前缀（OWASP 要求），防 Excel 当公式执行。"""
        s = str(v) if v is not None else ""
        return ("'" + s) if s and s[0] in "=+-@\t\r" else s

    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["时间", "操作者", "动作", "对象类型", "对象ID", "IP", "详情"])
    for log, uname in rows:
        detail = json.dumps(log.detail, ensure_ascii=False) if log.detail else ""
        w.writerow([
            log.created_at.strftime("%Y-%m-%d %H:%M:%S") if log.created_at else "",
            _csv_safe(uname), _csv_safe(log.action), _csv_safe(log.target_type), _csv_safe(log.target_id),
            _csv_safe(log.ip), _csv_safe(detail),
        ])
    return StreamingResponse(
        iter([buf.getvalue().encode("utf-8-sig")]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=audit_logs.csv"},
    )


# ---------- 回收站（假删除项目：恢复 / 彻底删除）----------
@router.get("/admin/recycle-bin")
def recycle_bin(page: int = Query(1, ge=1), size: int = Query(20, ge=1, le=100),
                user: dict = Depends(require_admin), db: Session = Depends(get_db)):
    items, total = ProjectService(db).list_deleted_projects(page, size)
    return page_result(items, total, page, size)


@router.post("/admin/recycle-bin/restore")
def recycle_restore(body: RecycleBatchIn, user: dict = Depends(require_admin), db: Session = Depends(get_db)):
    n = ProjectService(db).restore_projects(body.project_ids)
    # target_id 避免批量 join 超 64 字符：只存首尾标识，完整列表放 detail
    ids = body.project_ids
    tid = str(ids[0]) if ids else None
    if len(ids) > 1:
        tid = f"{ids[0]}..{ids[-1]}" if len(f"{ids[0]}..{ids[-1]}") <= 60 else f"{ids[0]}.."
    record_audit(db, user["user_id"], "restore", "project", tid, {"count": n, "ids": ids})
    return ok(message=f"已恢复 {n} 个项目")


@router.post("/admin/recycle-bin/purge")
def recycle_purge(body: RecycleBatchIn, user: dict = Depends(require_admin), db: Session = Depends(get_db)):
    n = ProjectService(db).purge_projects(body.project_ids)
    ids = body.project_ids
    tid = str(ids[0]) if ids else None
    if len(ids) > 1:
        tid = f"{ids[0]}..{ids[-1]}" if len(f"{ids[0]}..{ids[-1]}") <= 60 else f"{ids[0]}.."
    record_audit(db, user["user_id"], "purge", "project", tid, {"count": n, "ids": ids})
    return ok(message=f"已彻底删除 {n} 个项目")
